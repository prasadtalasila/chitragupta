"""What a `.tex` draft's own preview changes, so it shows what the thesis
will show (#1164, #1120; plans/1120-1164-tex-preview.md).

A thesis-chapter fragment is LaTeX, and its `tex`/`pdf` preview is the
only place its author sees it typeset before building the thesis.
Pandoc's LaTeX reader lost four things on the way, each with exit 0:

- **the figure.** It followed `\\input{figures/x.tex}` and dropped the
  `tikzpicture` inside. Reading with `latex+raw_tex` leaves the `\\input`
  for LuaLaTeX, which reads the file through `TEXINPUTS` and the #823
  read fence as it does for a Markdown draft's figures. Only for a
  LaTeX-bound output: md, html and docx swap a figure for its ASCII twin
  (`_figures._substitute_ascii_for_tikz`), and a raw `\\ref` would print
  there as text.
- **absolute column widths.** `p{2.6cm}` became `l`, before any filter
  sees the table, so the source is rewritten first: a fraction of
  `\\linewidth`, which the reader keeps.
- **heading numbers.** The template left headings unnumbered while
  pandoc resolved `\\ref` to a number. Under `raw_tex` LaTeX resolves
  the `\\ref`, and `--number-sections` numbers the headings from the
  same counters.
- **the references heading.** A Markdown draft writes its own
  `## References`; a fragment has none, so the preview names the list.

What `raw_tex` costs, accepted by the owner: a command pandoc does not
know now reaches LuaLaTeX, so a command defined only in the thesis's
preamble stops the pdf. `preamble_file` is the remedy, an optional file
beside the draft modelled on the book's `content/specs/<book>/preamble.tex`,
and `undefined_command_hint` names it.

It also costs every alignment or size declaration pandoc does not keep
inside its group (`\\centering`, `\\small`, ...): `raw_tex` keeps it as
raw TeX of its own. In a figure, pandoc then sets two `0.45\\linewidth`
minipages, an empty one and the picture. In a table float, or a
`{\\centering ...}` group, or a `center` block, pandoc drops the group,
so the declaration centres or shrinks every later paragraph (measured,
pandoc 3.1.11; the table on a real thesis chapter). So the preview's
copy drops a declaration inside any group or environment, and keeps a
top-level one, which changes the rest of the thesis too.

A width is rewritten only in a spec whose every column is `p`, `m` or
`b`: once any column has a width, pandoc gives an `l`, `c` or `r` column
zero width, so `lp{6cm}` would print its first column a letter wide.

Left alone: `em`/`ex` widths, whose size depends on the thesis's font;
a `*{n}{...}` spec; every Markdown draft; and every `--fragment` render,
which is the deliverable and never had a reader problem.
"""

import re
import sys
from pathlib import Path

from chitragupta import config
from chitragupta.page import ARTICLE
from chitragupta.render_output._figures import _TEX_FORMATS
from chitragupta.render_output._paths import _MARKDOWN_SUFFIXES

_TITLE = ["--metadata", "reference-section-title=References"]

# A table environment, and how many braced arguments come before its
# column spec: `tabular*` and `tabularx` take a width first.
_TABLE_RE = re.compile(r"\\begin\{(tabular\*?|tabularx|longtable)\}")
_WIDTH_FIRST = {"tabular*", "tabularx"}
# A `p`/`m`/`b` column's width in an absolute unit, and pt per unit.
_COLUMN_RE = re.compile(r"([pmb])\{\s*(\d+(?:\.\d+)?|\.\d+)\s*(cm|mm|in|pt|bp)\s*\}")
_PT = {"cm": 28.4528, "mm": 2.84528, "in": 72.27, "pt": 1.0, "bp": 1.00375}

# The declarations that change every paragraph after them until their
# group ends, and a control word or symbol.
_DECLARATIONS = frozenset(
    "centering raggedright raggedleft tiny scriptsize footnotesize small "
    "normalsize large Large LARGE huge Huge".split()
)
_CONTROL_RE = re.compile(r"\\([A-Za-z]+|.)", re.DOTALL)
# A spec's decorations, which name no column: `>{...}`, `<{...}`,
# `@{...}`, `!{...}`, and rules.
_DECORATION = "<>@!"

# TeX's report of an undefined command; the line after it is the context,
# whose last control sequence is the one TeX stopped on: `l.4 Plain \\todo`,
# or `<argument> see \\citep` for one inside another command's argument.
_UNDEFINED_RE = re.compile(r"! Undefined control sequence\.[ \t]*\n(?P<line>[^\n]*)")
_NAME_RE = re.compile(r"\\([A-Za-z@]+)")
_CITE_COMMANDS = frozenset({"cite", "citep", "citet", "citealp", "citeauthor"})


def is_tex_draft(input_path: Path) -> bool:
    """Whether the draft is LaTeX rather than Markdown."""
    return input_path.suffix.lower() not in _MARKDOWN_SUFFIXES


def preamble_file(input_path: Path) -> Path | None:
    """The author's preamble for this draft's preview:
    `<stem>.preamble.tex` beside it, else a `preamble.tex` its
    directory's chapters share, else `None`.

    Raises `OutsideContentDir` for one that is a symlink out of the
    draft's directory: pandoc reads the file it is handed with no fence
    and inlines it into the preview's preamble, so the figures' #823
    rule (`_assets._refuse_escaping_refs`) applies here too.
    """
    for candidate in (
        input_path.with_name(f"{input_path.stem}.preamble.tex"),
        input_path.with_name("preamble.tex"),
    ):
        if not candidate.is_file():
            continue
        if not config.resolves_inside(candidate, input_path.parent):
            raise config.OutsideContentDir(
                f"{candidate} resolves outside {input_path.parent} through a symlink. "
                "pandoc would read it wherever it points; copy the file into the "
                "draft's directory instead."
            )
        return candidate
    return None


def rewrite(text: str, input_path: Path, output_format: str, fragment: bool) -> str:
    """The text pandoc reads for a `.tex` draft's non-fragment render;
    `text` itself for anything else."""
    if fragment or not is_tex_draft(input_path):
        return text
    text = widths_as_fractions(text, ARTICLE.text_width_pt)
    if output_format in _TEX_FORMATS:
        text = without_grouped_declarations(text)
    return text


def pandoc_args(input_path: Path, output_format: str, fragment: bool) -> list[str]:
    """What pandoc is told for a `.tex` draft's non-fragment render."""
    if fragment or not is_tex_draft(input_path):
        return []
    args = list(_TITLE)
    if output_format in _TEX_FORMATS:
        args += ["-f", "latex+raw_tex", "--number-sections"]
        preamble = preamble_file(input_path)
        if preamble is not None:
            # Named, so a shared `preamble.tex` is never loaded silently.
            print(f"[preamble] {preamble}", file=sys.stderr)
            args += ["--include-in-header", str(preamble)]
    return args


def widths_as_fractions(text: str, text_width_pt: float) -> str:
    """Every absolute `p`/`m`/`b` width in a table's column spec, as a
    fraction of `\\linewidth` against `text_width_pt`."""
    out, done = [], 0
    for match in _TABLE_RE.finditer(text):
        span = _spec_span(text, match.end(), match.group(1) in _WIDTH_FIRST)
        if span is None:
            continue
        start, end = span
        if not _only_paragraph_columns(text[start:end]):
            continue
        spec = _COLUMN_RE.sub(lambda m: _fraction(m, text_width_pt), text[start:end])
        out += [text[done:start], spec]
        done = end
    return "".join(out) + text[done:]


def without_grouped_declarations(text: str) -> str:
    """Every alignment or size declaration inside a brace group or an
    environment removed, with the spaces after it but never a newline. A
    top-level one, an escaped character and a comment are left as written."""
    out, depth, i = [], 0, 0
    while i < len(text):
        char = text[i]
        if char == "%":
            end = text.find("\n", i)
            end = len(text) if end < 0 else end
            out.append(text[i:end])
            i = end
        elif char == "\\":
            match = _CONTROL_RE.match(text, i)
            name = match.group(1) if match else ""
            depth += {"begin": 1, "end": -1}.get(name, 0)
            i = match.end() if match else i + 1
            if name in _DECLARATIONS and depth > 0:
                while i < len(text) and text[i] in " \t":
                    i += 1
            else:
                out.append(match.group(0) if match else char)
        else:
            depth = max(0, depth + {"{": 1, "}": -1}.get(char, 0))
            out.append(char)
            i += 1
    return "".join(out)


def undefined_command_hint(stderr: str | None, input_arg: str) -> str:
    r"""Where to define the command a `.tex` preview stopped on, or "".

    One the thesis's preamble defines is undefined here, where none of
    that preamble is loaded, and the remedy is the author's preamble
    file, which no skill writes for them: the line says so, because it is
    what an agent reads at the moment it would. A citation command is the
    exception: inside a command pandoc keeps raw it is never resolved,
    and defining it would print a key, so the hint says to move it.
    """
    path = Path(input_arg)
    if "Undefined control sequence" not in (stderr or "") or not is_tex_draft(path):
        return ""
    match = _UNDEFINED_RE.search(stderr or "")
    names = _NAME_RE.findall(match.group("line")) if match else []
    if names and names[-1] in _CITE_COMMANDS:
        return (
            f"\n[preamble] \\{names[-1]} sits inside a command pandoc does not know, so "
            "the preview leaves it unresolved: move the citation out of that command."
        )
    command = f"\\{names[-1]}" if names else "the undefined command"
    return (
        f"\n[preamble] The preview loads none of your thesis's preamble: define {command} "
        f"in {path.with_name(f'{path.stem}.preamble.tex')} (or in a preamble.tex beside "
        "the draft, shared by its chapters). The author writes it from their thesis's "
        "own preamble; an agent reports this line and leaves the file alone."
    )


def _only_paragraph_columns(spec: str) -> bool:
    """Whether every column `spec` names is `p`, `m` or `b`: decorations
    and rules skipped, a column's own argument skipped, and a `*{n}{...}`
    repeat read as not."""
    columns, i = set(), 0
    while i < len(spec):
        char = spec[i]
        if char in _DECORATION or char.isalpha():
            if char.isalpha():
                columns.add(char)
            i = _skip_group(spec, i + 1, "{", "}") or len(spec)
        elif char in "| \t\n":
            i += 1
        else:
            return False
    return bool(columns) and columns <= set("pmb")


def _fraction(match: re.Match[str], text_width_pt: float) -> str:
    column, number, unit = match.groups()
    return f"{column}{{{float(number) * _PT[unit] / text_width_pt:.4f}\\linewidth}}"


def _spec_span(text: str, i: int, width_first: bool) -> tuple[int, int] | None:
    """Where the column spec's content is, from just after
    `\\begin{env}`: past a width argument and a `[pos]`, then a braced
    group. `None` where a group is left open or the spec is missing."""
    if width_first:
        i = _skip_group(text, i, "{", "}")
    i = _skip_group(text, i, "[", "]")
    i = _skip_space(text, i)
    if i is None or i >= len(text) or text[i] != "{":
        return None
    end = _group_end(text, i, "{", "}")
    return None if end is None else (i + 1, end - 1)


def _skip_group(text: str, i: int | None, opener: str, closer: str) -> int | None:
    """Past an optional group opening at `i` (after space)."""
    i = _skip_space(text, i)
    if i is None or i >= len(text) or text[i] != opener:
        return i
    return _group_end(text, i, opener, closer)


def _skip_space(text: str, i: int | None) -> int | None:
    while i is not None and i < len(text) and text[i].isspace():
        i += 1
    return i


def _group_end(text: str, i: int, opener: str, closer: str) -> int | None:
    """The offset just past the group opening at `i`, or `None`."""
    depth = 0
    for j in range(i, len(text)):
        depth += (text[j] == opener) - (text[j] == closer)
        if not depth:
            return j + 1
    return None

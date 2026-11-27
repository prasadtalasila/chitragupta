"""What a `.tex` draft's own preview changes, so it shows what the thesis
will show (#1164, #1120; plans/1120-1164-tex-preview.md).

Pandoc's LaTeX reader silently lost four things, fixed here:

- **the figure**: `latex+raw_tex` leaves `\\input` for LuaLaTeX (LaTeX-bound
  output only; other formats get the ASCII twin).
- **absolute column widths**: `p{2.6cm}` became `l`, so widths are rewritten as
  fractions of `\\linewidth` first, only where every column is `p`/`m`/`b`
  (pandoc zero-widths `l`/`c`/`r` beside a width column).
- **heading numbers**: `--number-sections` matches LaTeX's `\\ref` numbers.
- **the references heading**, which a fragment lacks.

`raw_tex` costs, accepted by the owner: a thesis-only command stops the pdf
(remedy: `preamble_file`); and grouped declarations (`\\centering`, `\\small`)
leak to every later paragraph (pandoc 3.1.11), so the preview drops those
inside groups. `em`/`ex` widths, `*{n}{...}`, Markdown drafts and `--fragment`
renders are left alone.
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
_COLUMN_RE = re.compile(r"([pmb])\{\s*(\d+(?:\.\d+)?|\.\d+)\s*(cm|mm|in|pt|bp)\s*\}")
_PT = {"cm": 28.4528, "mm": 2.84528, "in": 72.27, "pt": 1.0, "bp": 1.00375}

_DECLARATIONS = frozenset(
    "centering raggedright raggedleft tiny scriptsize footnotesize small "
    "normalsize large Large LARGE huge Huge".split()
)
_CONTROL_RE = re.compile(r"\\([A-Za-z]+|.)", re.DOTALL)
_DECORATION = "<>@!"

# TeX's undefined-command report; the next line's last control sequence is the
# culprit: `l.4 Plain \\todo`, or `<argument> see \\citep` inside an argument.
_UNDEFINED_RE = re.compile(r"! Undefined control sequence\.[ \t]*\n(?P<line>[^\n]*)")
_NAME_RE = re.compile(r"\\([A-Za-z@]+)")
_CITE_COMMANDS = frozenset({"cite", "citep", "citet", "citealp", "citeauthor"})


def is_tex_draft(input_path: Path) -> bool:
    return input_path.suffix.lower() not in _MARKDOWN_SUFFIXES


def preamble_file(input_path: Path) -> Path | None:
    """The author's preamble for this preview: `<stem>.preamble.tex`, else a
    shared `preamble.tex` in its directory, else `None`.

    Raises `OutsideContentDir` for a symlink out of the draft's directory:
    pandoc inlines it unfenced, so the #823 rule applies here too.
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
    """The text pandoc reads for a `.tex` non-fragment render; else `text`."""
    if fragment or not is_tex_draft(input_path):
        return text
    text = widths_as_fractions(text, ARTICLE.text_width_pt)
    if output_format in _TEX_FORMATS:
        text = without_grouped_declarations(text)
    return text


def pandoc_args(input_path: Path, output_format: str, fragment: bool) -> list[str]:
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
    """Absolute `p`/`m`/`b` column widths as fractions of `\\linewidth`."""
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
    """Every grouped alignment or size declaration removed, with trailing spaces
    but never a newline. Top-level ones, escapes and comments are kept."""
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

    The remedy is the author's preamble file, which no skill writes, so the
    line says so. A citation command is the exception: kept raw it is never
    resolved, so the hint says to move it.
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
    """Whether every column is `p`, `m` or `b`; a `*{n}{...}` repeat reads as not."""
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
    """The column spec's content span after `\\begin{env}`, past a width
    argument and `[pos]`; `None` if open or missing."""
    if width_first:
        i = _skip_group(text, i, "{", "}")
    i = _skip_group(text, i, "[", "]")
    i = _skip_space(text, i)
    if i is None or i >= len(text) or text[i] != "{":
        return None
    end = _group_end(text, i, "{", "}")
    return None if end is None else (i + 1, end - 1)


def _skip_group(text: str, i: int | None, opener: str, closer: str) -> int | None:
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

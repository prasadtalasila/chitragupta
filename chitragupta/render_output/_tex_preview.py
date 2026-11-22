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
and `_cli._undefined_command_hint` names it.

It also costs a figure's own `\\centering`: `raw_tex` keeps it as a
block of its own, and pandoc then sets the figure as two `0.45\\linewidth`
minipages, an empty one and the picture (measured, pandoc 3.1.11).
Without it, pandoc writes its own `\\centering` and keeps one block, so
the preview's copy drops it.

Left alone: `em`/`ex` widths, whose size depends on the thesis's font;
every Markdown draft; and every `--fragment` render, which is the
deliverable and never had a reader problem.
"""

import re
from pathlib import Path

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

_FIGURE_RE = re.compile(r"(\\begin\{(figure\*?)\})(.*?)(\\end\{\2\})", re.DOTALL)
_CENTERING_RE = re.compile(r"\\centering(?![A-Za-z])\s*")


def is_tex_draft(input_path: Path) -> bool:
    """Whether the draft is LaTeX rather than Markdown."""
    return input_path.suffix.lower() not in _MARKDOWN_SUFFIXES


def preamble_file(input_path: Path) -> Path | None:
    """The author's preamble for this draft's preview:
    `<stem>.preamble.tex` beside it, else a `preamble.tex` its
    directory's chapters share, else `None`."""
    for candidate in (
        input_path.with_name(f"{input_path.stem}.preamble.tex"),
        input_path.with_name("preamble.tex"),
    ):
        if candidate.is_file():
            return candidate
    return None


def rewrite(text: str, input_path: Path, output_format: str, fragment: bool) -> str:
    """The text pandoc reads for a `.tex` draft's non-fragment render;
    `text` itself for anything else."""
    if fragment or not is_tex_draft(input_path):
        return text
    text = widths_as_fractions(text, ARTICLE.text_width_pt)
    if output_format in _TEX_FORMATS:
        text = without_lone_centering(text)
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
        spec = _COLUMN_RE.sub(lambda m: _fraction(m, text_width_pt), text[start:end])
        out += [text[done:start], spec]
        done = end
    return "".join(out) + text[done:]


def without_lone_centering(text: str) -> str:
    """Every figure's own `\\centering` removed, with the space after it."""
    return _FIGURE_RE.sub(
        lambda m: m.group(1) + _CENTERING_RE.sub("", m.group(3)) + m.group(4), text
    )


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

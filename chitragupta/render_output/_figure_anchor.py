r"""A hidden mark at each figure in a pdf render, so its page can be read back (#1052).

Each figure gets a PDF named destination `cgfig:<base>`, which `pdfinfo -dests`
lists with its page: pandoc deletes the log, a `\typeout` in a float runs when
built not placed, and hyperref's `figure.N` names shift. It adds nothing visible.

The mark goes after the figure in the same paragraph: before it, it would sit
alone in the vertical list and remove a possible page break. `\unskip` first
drops the trailing space. `\input` and mark travel in one ```{=latex}``` block
because pandoc escapes braces of unknown commands in Markdown text.

Markdown drafts and pdf output only: pandoc's LaTeX reader would print the mark,
and pdfLaTeX has no `\pdfextension`.
"""

import re

PREFIX = "cgfig:"

# A base TeX can read inside `name{...}` (no brace, `#`, `%`, backslash). Anything
# else gets no mark, and so no page picture, rather than a mark that breaks the render.
_SAFE_BASE_RE = re.compile(r"[\w./-]+")

# One line of `pdfinfo -dests`: `   2 [ XYZ  103  609 null ] "cgfig:figures/flow"`.
_DEST_RE = re.compile(r'^\s*(?P<page>\d+)\s+\[[^\]]*\]\s+"' + PREFIX + r'(?P<base>.*)"\s*$', re.M)


def figure_block(ref: str, base: str, marked: bool) -> str:
    """The figure's own paragraph, centred, as one raw block: `\\input{ref}`,
    then the mark for `base` when `marked` and the base can carry one.

    Centred for captioned and uncaptioned figures alike (#1085): nothing else
    set `\\centering`. The group keeps it to this paragraph.
    """
    mark = ""
    if marked and _SAFE_BASE_RE.fullmatch(base):
        mark = f"\\unskip\\pdfextension dest name{{{PREFIX}{base}}} xyz\\relax"
    return f"```{{=latex}}\n{{\\centering\\input{{{ref}}}{mark}\\par}}\n```\n"


def pages(dests: str) -> dict[str, int]:
    """`{base: page}` for every mark in `pdfinfo -dests` output."""
    return {match["base"]: int(match["page"]) for match in _DEST_RE.finditer(dests)}

r"""A hidden mark at each figure in a pdf render, so the page a figure
printed on can be read back from the PDF (#1052).

`chitragupta figure look --draft` and `draft render` write a PNG of the
page that holds each figure. Nothing else in a PDF says which page that
is: pandoc deletes the engine's log, a `\typeout` of the page inside a
float runs when the float is built rather than placed, and hyperref's
own `figure.N` destination is named by a number that moves whenever a
figure is added earlier. So each figure gets a PDF named destination,
`cgfig:<base>`, named by the marker's own base, which `pdfinfo -dests`
lists with its page. A destination is a jump target, not a bookmark: it
adds nothing to a viewer's outline and nothing to the page.

**After the figure, in the same paragraph, never before it.** Before,
it would sit alone in the main vertical list, with no glue between it
and the paragraph above, and so remove the page break TeX could have
taken there: the layout would move. Inside the figure's own paragraph
it rides on the figure's last line, which is on the figure's page. The
`\unskip` first does what TeX's own paragraph end does to a trailing
space, which a mark after it would otherwise stop.

**One raw block, `\input` and mark together.** Pandoc escapes the braces
of a command it does not know when it meets it in Markdown text, so the
mark has to travel in a ` ```{=latex} ` block, which pandoc copies to
the writer verbatim; and a block of its own would end the figure's
paragraph before the mark.

**Markdown drafts only, pdf output only.** A `.tex` draft reaches pandoc
through its LaTeX reader, which turns a command it does not know into
text; a mark there would print. A `tex` output may be compiled with
pdfLaTeX, where `\pdfextension` does not exist.
"""

import re

PREFIX = "cgfig:"

# A base that can sit inside `name{...}` as written: no brace, `#`, `%`
# or backslash for TeX to act on. Anything else gets no mark, and so no
# page picture, rather than a mark that breaks the render.
_SAFE_BASE_RE = re.compile(r"[\w./-]+")

# One line of `pdfinfo -dests`: `   2 [ XYZ  103  609 null ] "cgfig:figures/flow"`.
_DEST_RE = re.compile(r'^\s*(?P<page>\d+)\s+\[[^\]]*\]\s+"' + PREFIX + r'(?P<base>.*)"\s*$', re.M)


def anchored_input(ref: str, base: str) -> str:
    """`\\input{ref}` followed by the mark for `base`, as one raw block;
    the bare `\\input` line for a base a mark cannot carry."""
    if not _SAFE_BASE_RE.fullmatch(base):
        return f"\\input{{{ref}}}\n"
    mark = f"\\unskip\\pdfextension dest name{{{PREFIX}{base}}} xyz\\relax"
    return f"```{{=latex}}\n\\input{{{ref}}}{mark}\n```\n"


def pages(dests: str) -> dict[str, int]:
    """`{base: page}` for every mark in `pdfinfo -dests` output."""
    return {match["base"]: int(match["page"]) for match in _DEST_RE.finditer(dests)}

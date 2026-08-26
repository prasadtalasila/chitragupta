"""Issue 411: a captioned figure's number, and the reference that reads it.

Split from `chitragupta/render_output/_figures.py`'s own concern -- that
module switches a figure marker to the form an output format can draw;
this one wraps that substitution with a caption, so LaTeX's own counter
numbers the float instead of a hand-typed `\\thefigure`.

A Markdown draft writes the marker, then its caption directly below it --
no blank line between, the same adjacency §11's `<!-- single-source: -->`
and §13's table caption+marker pair both use. The marker line is captured
whole (`marker`) so `substitute_captions` can hand it, byte-identical, to
`_figures`'s own marker-content substitution, which still finds and
resolves it afterwards -- this module wraps around that substitution
rather than replacing it, and deliberately does not import it: the two
run in a fixed order (`__init__.py`'s `_substituted`), not a call chain.

An *uncaptioned* figure marker -- §10's accepted case -- carries no
`Figure` at all: it has no caption for a reader or a `figureref` to point
at, the same way `_tables.tables()` only returns a table that has both a
caption and an id.
"""

import re
from typing import NamedTuple

from chitragupta.render_output._tables import line_of

# The formats that go through LaTeX, and so the only ones with a `figure`
# counter to defer numbering to. Deliberately a second copy of
# `_figures._TEX_FORMATS`/`_tables._LATEX_BOUND` rather than an import of
# either: `_tables.py`'s own comment already states why the project keeps
# these independent -- each module's reason for caring is different, and
# one could legitimately change without the others.
_LATEX_BOUND = {"tex", "latex", "pdf"}

# The caption line is excluded from starting with `<!--`, `%` or `#`, so
# two figures placed back to back with no blank line between them do not
# read the second one's marker as the first one's caption.
_FIGURE_CAPTION_PAIR_RE = re.compile(
    r"^(?P<marker><!--[ \t]*figure:[ \t]*(?P<ref>\S+)[ \t]*-->)[ \t]*\n"
    r"[ \t]*(?P<caption>(?!<!--|%|#)\S.*?)[ \t]*$",
    re.MULTILINE,
)

# The inline reference, mirroring `_tables._REF_RE` -- it sits inside a
# sentence rather than on a line of its own, standing in for the whole
# noun phrase "Figure N".
_FIGUREREF_RE = re.compile(r"<!--[ \t]*figureref:[ \t]*(?P<id>\S+?)[ \t]*-->")


class Figure(NamedTuple):
    """One declared, captioned figure: its id, its caption, the number it
    takes in a format that has to be told, and where its marker sits."""

    id: str
    caption: str
    number: int
    line: int


def _figure_id(ref: str) -> str:
    """The id a `figure:` marker's value names, derived rather than
    written: `figures/delivery-modes` names the id `delivery-modes`,
    exactly the base name `docs/TIKZ-STYLE.md`'s own `\\label{fig:...}`
    convention already uses."""
    return ref.rsplit("/", 1)[-1]


def figures(text: str) -> "list[Figure]":
    """Every captioned figure in `text`, numbered in document order.

    Document order is LaTeX's own counting order for the `figure`
    environments this module goes on to emit, which is what keeps the
    number this module writes for `md`/`docx`/`html` and the number LaTeX
    assigns for `pdf` pointing at the same figure.
    """
    return [
        Figure(_figure_id(m.group("ref")), m.group("caption"), number, line_of(text, m.start()))
        for number, m in enumerate(_FIGURE_CAPTION_PAIR_RE.finditer(text), start=1)
    ]


def references(text: str) -> "list[tuple[str, int]]":
    """Every `figureref` marker in `text`, as (id, 1-based line)."""
    return [(m.group("id"), line_of(text, m.start())) for m in _FIGUREREF_RE.finditer(text)]


def _caption_wrap_for(figure: "Figure", marker: str, output_format: str) -> str:
    """What a `[marker, caption]` pair becomes in `output_format`.

    LaTeX-bound output wraps the untouched marker in a `figure` float with
    a real `\\caption`/`\\label`, so LaTeX's own counter numbers it -- no
    `\\thefigure` is ever written, unlike the hand-authored float this
    replaces. Everything else has no counter to defer to, so the number is
    written here, the same reasoning `_tables._caption_for` uses for `md`.
    """
    if output_format in _LATEX_BOUND:
        return (
            f"\\begin{{figure}}\n{marker}\n"
            f"\\caption{{{figure.caption}}}\n\\label{{fig:{figure.id}}}\n\\end{{figure}}"
        )
    return f"{marker}\n**Figure {figure.number}:** {figure.caption}"


def substitute_captions(text: str, output_format: str) -> str:
    """`text` with every `[marker, caption]` pair wrapped for `output_format`.

    The marker line itself is left exactly as it was inside the wrapper,
    so `_figures._with_figures_for`'s own substitution still finds and
    resolves it afterwards -- this is a pass that runs *before* it, not a
    replacement for it. An uncaptioned marker does not match the pair
    regex at all and is untouched, preserving §10's accepted uncaptioned
    case.
    """
    declared = iter(figures(text))

    def replace(match: "re.Match[str]") -> str:
        return _caption_wrap_for(next(declared), match.group("marker"), output_format)

    return _FIGURE_CAPTION_PAIR_RE.sub(replace, text)


def _figureref_for(figure: "Figure | None", raw: str, output_format: str) -> str:
    """The phrase a `figureref` marker expands to, or `raw` unchanged if
    the id it names is not a captioned figure -- an unresolvable reference
    is reported by `warnings`, not silently deleted from a sentence."""
    if figure is None:
        return raw
    if output_format in _LATEX_BOUND:
        return f"`Figure~\\ref{{fig:{figure.id}}}`{{=latex}}"
    return f"Figure {figure.number}"


def substitute_refs(text: str, output_format: str) -> str:
    """`text` with every `figureref` marker resolved for `output_format`.

    A `figureref` naming an id no *captioned* figure declares -- including
    one naming a figure that exists but carries no caption -- is left
    exactly as written, the same non-destructive rule `_tables.substitute`
    uses for an unresolvable `tableref`.
    """
    by_id = {figure.id: figure for figure in figures(text)}

    def replace(match: "re.Match[str]") -> str:
        return _figureref_for(by_id.get(match.group("id")), match.group(0), output_format)

    return _FIGUREREF_RE.sub(replace, text)


def warnings(text: str) -> "list[str]":
    """A captioned figure's id, and a `figureref` naming one -- mirroring
    `_tables.warnings`'s duplicate-id and unknown-ref checks. A `.tex`
    fragment carries neither marker, so both are empty there."""
    declared_ids = [figure.id for figure in figures(text)]
    found = [
        f"`{figure_id}` is declared by more than one figure"
        for figure_id in sorted(set(declared_ids))
        if declared_ids.count(figure_id) > 1
    ]
    found += [
        f"`{ref}` is referred to but no figure declares it"
        for ref in sorted({ref for ref, _ in references(text)} - set(declared_ids))
    ]
    return found

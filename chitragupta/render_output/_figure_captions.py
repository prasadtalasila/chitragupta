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

An *uncaptioned* figure marker carries no `Figure` at all: it has no
caption for a reader or a `figureref` to point at, the same way
`_tables.tables()` only returns a table that has both a caption and an
id. §10 used to accept that state; since #421 it does not, and
`chitragupta/style_figures.py` reports it. **Nothing here changed with
that amendment** -- an uncaptioned marker renders exactly as it always
did, and the standard moved without the renderer moving.
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

    Issue 494: an earlier revision spelled the LaTeX-bound branch as one
    `\\begin{figure}...\\end{figure}` block with the caption interpolated
    straight into `\\caption{...}`. Pandoc's raw-TeX passthrough reads a
    `\\begin{env}...\\end{env}` span as one opaque, byte-identical block --
    the same mechanism `_figures.py`'s own `\\input{...}` markers rely on
    -- so everything between those two commands, caption included, reached
    pdflatex unparsed and unescaped: `&` broke the compile, `%` truncated
    the rest of the line including the `\\label`, and `[@key]` reached the
    PDF as literal, unresolved text. `_tables._caption_for` never has this
    problem, because a table's caption is pandoc's own native caption
    syntax, not text glued inside a hand-written raw block.

    The fix mirrors that: `\\begin{figure}` and `\\end{figure}` are each
    their own explicit raw block (a fenced ` ```{=latex} ` block, pandoc's
    own syntax for "copy this verbatim to the writer"), so neither one
    reads ahead for a matching partner and swallows what sits between them.
    The caption itself is ordinary pandoc Markdown -- Pandoc-processed,
    citations and all -- with only the `\\caption{`/`}\\label{fig:...}`
    wrapper injected as raw *inline* spans (the same
    `` `...`{=latex} `` idiom `_figureref_for` below already uses), so it
    survives the Markdown reader as `\\caption{...}` around whatever the
    caption actually says rather than around its literal source text.
    """
    if output_format in _LATEX_BOUND:
        caption_line = (
            f"`\\caption{{`{{=latex}}{figure.caption}`}}\\label{{fig:{figure.id}}}`{{=latex}}"
        )
        return (
            "```{=latex}\n\\begin{figure}\n```\n"
            f"{marker}\n\n"
            f"{caption_line}\n\n"
            "```{=latex}\n\\end{figure}\n```"
        )
    return f"{marker}\n**Figure {figure.number}:** {figure.caption}"


def substitute_captions(
    text: str, output_format: str, declared: "list[Figure] | None" = None
) -> str:
    """`text` with every `[marker, caption]` pair wrapped for `output_format`.

    The marker line itself is left exactly as it was inside the wrapper,
    so `_figures._with_figures_for`'s own substitution still finds and
    resolves it afterwards -- this is a pass that runs *before* it, not a
    replacement for it. An uncaptioned marker does not match the pair
    regex at all and is untouched -- unchanged by #421, which made that
    state a `draft style` finding without changing what it renders as.

    `declared` lets a caller hand in a list already computed from `text`
    before any substitution touched it -- `__init__.py`'s `_substituted`
    does, because `substitute_refs` also needs that same pristine list
    rather than one recomputed off text `substitute_captions` has already
    rewritten (see that function's own docstring for why recomputing is
    wrong). Left `None`, this call is self-contained, which is what every
    direct test of this function relies on.
    """
    figs = figures(text) if declared is None else declared
    remaining = iter(figs)

    def replace(match: "re.Match[str]") -> str:
        return _caption_wrap_for(next(remaining), match.group("marker"), output_format)

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


def substitute_refs(text: str, output_format: str, declared: "list[Figure] | None" = None) -> str:
    """`text` with every `figureref` marker resolved for `output_format`.

    A `figureref` naming an id no *captioned* figure declares -- including
    one naming a figure that exists but carries no caption -- is left
    exactly as written, the same non-destructive rule `_tables.substitute`
    uses for an unresolvable `tableref`.

    `declared`, as in `substitute_captions`, lets a caller pin the figure
    list to the text as it stood before either substitution ran. This
    matters here for a subtler reason than in that function: recomputing
    `figures()` off text `substitute_captions` has *already* rewritten
    would scan already-wrapped `\\caption{...}`/`**Figure N:**` lines for
    a *new* marker/caption pair, corrupting the very numbering this
    module exists to get right. Left `None`, this call is self-contained.
    """
    by_id = {figure.id: figure for figure in (figures(text) if declared is None else declared)}

    def replace(match: "re.Match[str]") -> str:
        return _figureref_for(by_id.get(match.group("id")), match.group(0), output_format)

    return _FIGUREREF_RE.sub(replace, text)


def _continuation_line(text: str, match: "re.Match[str]") -> str | None:
    """The line right after `match`'s caption, if it looks like the same
    prose paragraph continuing rather than a new block.

    `_FIGURE_CAPTION_PAIR_RE` takes any non-blank line under a marker as
    the caption (m-59): a paragraph that was never meant to be a caption
    at all -- one that just happens to start right under the marker, with
    no blank line separating them, the ordinary Markdown shape for a
    wrapped sentence -- has its first line silently read as a one-line
    caption while its second line is left as ordinary text directly
    beneath it. A non-blank line immediately following the caption is
    this shape's symptom: it means the "caption" may really be the first
    line of a longer paragraph, not a deliberate one-line caption. A
    following line that starts a new marker, heading or comment is a
    deliberate abutment, not this; excluded the same way the caption
    group itself excludes them.
    """
    rest = text[match.end() :]
    if not rest.startswith("\n"):
        return None
    line = rest[1:].split("\n", 1)[0]
    stripped = line.strip()
    if stripped and not line.lstrip().startswith(("<!--", "%", "#")):
        return stripped
    return None


def warnings(text: str) -> "list[str]":
    """A captioned figure's id, and a `figureref` naming one -- mirroring
    `_tables.warnings`'s duplicate-id and unknown-ref checks. A `.tex`
    fragment carries neither marker, so both are empty there."""
    declared = figures(text)
    declared_ids = [figure.id for figure in declared]
    found = [
        f"`{figure_id}` is declared by more than one figure"
        for figure_id in sorted(set(declared_ids))
        if declared_ids.count(figure_id) > 1
    ]
    found += [
        f"`{ref}` is referred to but no figure declares it"
        for ref in sorted({ref for ref, _ in references(text)} - set(declared_ids))
    ]
    found += [
        f"`{figure.id}`'s caption is immediately followed by a non-blank line "
        f'("{continuation}") -- the caption may really be the first line of that '
        "paragraph, not a deliberate one-line caption; add a blank line after the "
        "marker if it should be uncaptioned, or after the caption if it should stay "
        "one line"
        for figure, match in zip(declared, _FIGURE_CAPTION_PAIR_RE.finditer(text))
        if (continuation := _continuation_line(text, match)) is not None
    ]
    return found

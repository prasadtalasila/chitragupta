"""Issue 411: a captioned figure's number, and the reference that reads it.

`_figures.py` swaps a marker for drawable content; this wraps it with a
caption so LaTeX's counter numbers the float. The caption sits directly
below the marker (no blank line, like §11 and §13). The marker line is kept
byte-identical so `_figures` still resolves it afterwards; the two run in a
fixed order (`_substituted`), so this does not import it.

An uncaptioned marker yields no `Figure`; `chitragupta/style_figures.py`
reports it (#421), and it renders as it always did.
"""

import re
from typing import NamedTuple

from chitragupta.render_output._tables import line_of

# Formats with a LaTeX `figure` counter; a deliberate copy, not an import (see
# `_tables.py` for why these sets stay independent).
_LATEX_BOUND = {"tex", "latex", "pdf"}

# The caption line may not start with `<!--`, `%` or `#`, so back-to-back figures
# do not read the second marker as the first one's caption.
_FIGURE_CAPTION_PAIR_RE = re.compile(
    r"^(?P<marker><!--[ \t]*figure:[ \t]*(?P<ref>\S+)[ \t]*-->)[ \t]*\n"
    r"[ \t]*(?P<caption>(?!<!--|%|#)\S.*?)[ \t]*$",
    re.MULTILINE,
)

# Inline, standing in for the noun phrase "Figure N".
_FIGUREREF_RE = re.compile(r"<!--[ \t]*figureref:[ \t]*(?P<id>\S+?)[ \t]*-->")


class Figure(NamedTuple):
    """One declared, captioned figure: its id, its caption, the number it
    takes in a format that has to be told, and where its marker sits."""

    id: str
    caption: str
    number: int
    line: int


def _figure_id(ref: str) -> str:
    """`figures/delivery-modes` -> `delivery-modes`, matching
    `docs/TIKZ-STYLE.md`'s `\\label{fig:...}` convention."""
    return ref.rsplit("/", 1)[-1]


def figures(text: str) -> "list[Figure]":
    """Every captioned figure in `text`, numbered in document order, which is
    LaTeX's counting order, so written and LaTeX numbers agree.
    """
    return [
        Figure(_figure_id(m.group("ref")), m.group("caption"), number, line_of(text, m.start()))
        for number, m in enumerate(_FIGURE_CAPTION_PAIR_RE.finditer(text), start=1)
    ]


def references(text: str) -> "list[tuple[str, int]]":
    return [(m.group("id"), line_of(text, m.start())) for m in _FIGUREREF_RE.finditer(text)]


def _caption_wrap_for(figure: "Figure", marker: str, output_format: str) -> str:
    """What a `[marker, caption]` pair becomes in `output_format`.

    LaTeX-bound: a `figure` float with a real `\\caption`/`\\label`. Elsewhere
    the number is written here, as `_tables._caption_for` does for `md`.

    `\\begin{figure}` and `\\end{figure}` are separate ```{=latex}``` blocks,
    and the `\\caption{`/`}\\label{}` wrapper is raw inline spans, so the
    caption itself stays Markdown. One raw `begin...end` block passed the
    caption to TeX unparsed: `&` broke it, `%` ate the `\\label`, `[@key]`
    stayed literal (#494).
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

    The marker line stays intact for `_figures._with_figures_for`, which runs
    after this. `declared` lets `_substituted` pass the list computed from the
    pristine text (see `substitute_refs`); `None` computes it here.
    """
    figs = figures(text) if declared is None else declared
    remaining = iter(figs)

    def replace(match: "re.Match[str]") -> str:
        return _caption_wrap_for(next(remaining), match.group("marker"), output_format)

    return _FIGURE_CAPTION_PAIR_RE.sub(replace, text)


def _figureref_for(figure: "Figure | None", raw: str, output_format: str) -> str:
    """The phrase a `figureref` expands to, or `raw` unchanged if the id is not
    a captioned figure: `warnings` reports it rather than deleting it."""
    if figure is None:
        return raw
    if output_format in _LATEX_BOUND:
        return f"`Figure~\\ref{{fig:{figure.id}}}`{{=latex}}"
    return f"Figure {figure.number}"


def substitute_refs(text: str, output_format: str, declared: "list[Figure] | None" = None) -> str:
    """`text` with every `figureref` marker resolved for `output_format`.

    An unresolvable `figureref` is left as written, as `_tables.substitute`
    does. `declared` matters here: recomputing `figures()` off text
    `substitute_captions` already rewrote would find new false pairs and
    corrupt the numbering.
    """
    by_id = {figure.id: figure for figure in (figures(text) if declared is None else declared)}

    def replace(match: "re.Match[str]") -> str:
        return _figureref_for(by_id.get(match.group("id")), match.group(0), output_format)

    return _FIGUREREF_RE.sub(replace, text)


def _continuation_line(text: str, match: "re.Match[str]") -> str | None:
    """The line right after `match`'s caption, if it looks like the same
    prose paragraph continuing rather than a new block.

    The pair regex takes any non-blank line under a marker as the caption
    (m-59), so a wrapped paragraph loses its first line to a caption. A
    following non-blank line is the symptom; a new marker, heading or
    comment is a deliberate abutment, excluded as the caption group does.
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
    """Duplicate figure ids and unknown `figureref`s, as `_tables.warnings`.
    A `.tex` fragment carries neither marker."""
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

"""`k1-stroke` and `k2-text`: whether a figure's lines and labels can be
seen against what lies behind them (#1055).

WCAG 2's thresholds (`_colour.py`): a box's border and a connector clear
3:1, text clears 4.5:1, and large text (14pt bold, 18pt) clears 3:1.
Every colour is the probe's (`review/figure_layout/_paint.py`): what pgf
stroked and filled with, and what each run of a node's glyphs was set
in, so a colour reached through a style, a `#1` argument, a `\\colorlet`
or a macro is the colour measured. The fix is nearly always a rename:
draw in `cg<Hue>Line`, write in `cg<Hue>Text`.

**The ground** is one colour, found one way. A box's text and border are
measured against its own fill; a box with none, against the innermost
filled box that contains it (a zone card, usually); with none of those,
white. A connector is measured against the innermost filled box that
contains both its ends, or white.

Three limits, stated rather than guessed at: a translucent fill is read
as opaque, a shadow is not a ground, and a connector that crosses a
third zone on its way is measured against the ground of its ends. Lines
that join no two nodes (an axis, a plot, a `pic`'s outline) are not
measured; the report already counts them.
"""

import re

from chitragupta.figure._colour import LINE, RGB, WHITE, contrast, hex_code, mix, text_threshold
from chitragupta.figure._connector_check import unconnectable
from chitragupta.figure._connectors import LABEL_PREFIX, connectors
from chitragupta.figure._overlap import shown_as
from chitragupta.figure._rules import Finding
from chitragupta.review.figure_layout import Box, Drawn, DrawnNode, FigureResult, contains
from chitragupta.review.figure_layout._paint import Paint

CONTRAST = ("k1-stroke", "k2-text")

# `\definecolor{name}{HTML}{RRGGBB}` and `\colorlet{name}{expr}`, read
# only to *name* a colour the probe measured in a finding, never to
# measure it.
_DEFINE_RE = re.compile(r"\\definecolor\{(\w+)\}\{HTML\}\{([0-9A-Fa-f]{6})\}")
_COLORLET_RE = re.compile(r"\\colorlet\{(\w+)\}\{(\w+)(?:!(\d+)(?:!(\w+))?)?\}")


def contrast_check(
    source: str, figure: FigureResult, pictures: int
) -> tuple[list[Finding], list[tuple[str, str]]]:
    """k1 and k2, or each listed as not measured where the probe's lines
    and boxes are not in one frame: the connector rules' reasons."""
    why = unconnectable(source, figure, pictures)
    if why:
        return [], [(rule, why) for rule in CONTRAST]
    return contrast_rules(source, figure.drawn), []


def contrast_rules(source: str, drawn: Drawn) -> list[Finding]:
    """k1 and k2 over every node and connector the probe drew."""
    names = colour_names(source)
    filled = {name: node for name, node in drawn.nodes.items() if node.fill is not None}
    cons, _ = connectors(drawn)
    tags = {label: f"tag on {con.name}" for con in cons for label in con.line.labels}
    found = []
    for name, node in drawn.nodes.items():
        target = tags.get(name) or _target(name, node)
        ground = _node_ground(node, filled, names)
        found += _text(target, node, ground, names)
        if _border(node):
            found += _stroke("border", target, node.stroke, ground, names)
    seen = set()
    for con in cons:
        # Subpaths of one line repeat it; another line between the
        # same pair, in another colour, is its own measurement.
        key = (con.name, con.line.stroke and hex_code(con.line.stroke.colour))
        if con.line.stroke is None or key in seen:
            continue
        seen.add(key)
        ends = (drawn.nodes[con.start].box, drawn.nodes[con.end].box)
        ground = _ground(ends, {con.start, con.end}, filled, names)
        found += _stroke("line", con.name, con.line.stroke, ground, names)
    return found


def _target(name: str, node: DrawnNode) -> str:
    """A node's name, or its centre where TikZ named it internally (an
    unnamed `fit`'s `tikz@f@1`), which the source never says."""
    return shown_as(f"{LABEL_PREFIX}{name}" if "@" in name else name, node)


def _border(node: DrawnNode) -> bool:
    """Whether `node` has a border to see: one drawn in its own fill's
    colour (a step badge's disc) draws no line between them."""
    if node.stroke is None:
        return False
    return node.fill is None or hex_code(node.stroke.colour) != hex_code(node.fill.colour)


def colour_names(source: str) -> dict[str, str]:
    """`{#RRGGBB: name}` for every colour the figure defines by HTML code
    or `\\colorlet`s from those, white included. The first name of a hex
    wins, so a palette name is kept over a later alias."""
    palette: dict[str, RGB] = {"white": WHITE}
    for name, code in _DEFINE_RE.findall(source):
        palette[name] = tuple(int(code[i : i + 2], 16) / 255 for i in (0, 2, 4))
    for name, base, share, other in _COLORLET_RE.findall(source):
        if base in palette and (not other or other in palette):
            ratio = int(share) / 100 if share else 1.0
            palette[name] = mix(palette[base], palette.get(other, WHITE), ratio)
    names: dict[str, str] = {}
    for name, colour in palette.items():
        names.setdefault(hex_code(colour), name)
    return names


def _node_ground(
    node: DrawnNode, filled: dict[str, DrawnNode], names: dict[str, str]
) -> tuple[RGB, str]:
    if node.fill is not None:
        return node.fill.colour, f"fill {_shown(node.fill, names)}"
    return _ground((node.box,), {node.name}, filled, names)


def _ground(
    boxes: tuple[Box, ...], ends: set[str], filled: dict[str, DrawnNode], names: dict[str, str]
) -> tuple[RGB, str]:
    """`(colour, how it is described)` of the innermost filled box that
    holds every one of `boxes`, other than the nodes `ends` themselves."""
    holders = [
        node
        for name, node in filled.items()
        if name not in ends
        and not name.startswith(LABEL_PREFIX)
        and all(contains(node.box, box) for box in boxes)
    ]
    if not holders:
        return WHITE, "white"
    holder = min(holders, key=lambda node: _area(node.box))
    return holder.fill.colour, f"{holder.name}'s fill {_shown(holder.fill, names)}"


def _text(
    target: str, node: DrawnNode, ground: tuple[RGB, str], names: dict[str, str]
) -> list[Finding]:
    """One k2 finding per colour of `node`'s text that does not clear its
    threshold. Runs of one colour at several sizes report the worst."""
    failing: dict[RGB, tuple[float, float]] = {}
    for run in node.runs:
        ratio, needs = contrast(run.colour, ground[0]), text_threshold(run.size_pt, run.bold)
        if ratio < needs and needs - ratio > _shortfall(failing.get(run.colour)):
            failing[run.colour] = (ratio, needs)
    return [
        Finding("k2-text", target, _measured("text", _name(colour, names), ground, ratio, needs))
        for colour, (ratio, needs) in failing.items()
    ]


def _shortfall(pair: tuple[float, float] | None) -> float:
    return -1.0 if pair is None else pair[1] - pair[0]


def _stroke(
    what: str, target: str, paint: Paint, ground: tuple[RGB, str], names: dict[str, str]
) -> list[Finding]:
    ratio = contrast(paint.colour, ground[0])
    if ratio >= LINE:
        return []
    return [
        Finding("k1-stroke", target, _measured(what, _shown(paint, names), ground, ratio, LINE))
    ]


def _shown(paint: Paint, names: dict[str, str]) -> str:
    """A colour as the figure wrote it, unless that was through a macro
    (`\\c Text` from a `\\foreach`), which says nothing out of context."""
    if paint.written and "\\" not in paint.written:
        return paint.written
    return _name(paint.colour, names)


def _measured(what: str, shown: str, ground: tuple[RGB, str], ratio: float, needs: float) -> str:
    return f"{what} {shown} on {ground[1]}: {ratio:.2f}:1, needs {needs:g}:1"


def _name(colour: RGB, names: dict[str, str]) -> str:
    code = hex_code(colour)
    return names.get(code) or code


def _area(box: Box) -> float:
    return (box[2] - box[0]) * (box[3] - box[1])

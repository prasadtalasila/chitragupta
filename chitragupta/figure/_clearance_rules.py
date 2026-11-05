"""Clearance rules over a figure's connectors (#1054): `c2-tag-clearance`,
`c5-transit` and `c6-tag-covered`.

A tag is an unnamed node TikZ made on a connector's path: a named one is
a node in its own right (a `child`, or `\\draw ... node (m) {}`), which a
line touches by design. A tag is measured by its text box, where the
reader sees it, because its node box touches its line by construction:
`above`, `left` and the rest anchor the box edge on the line, and 141 of
the 160 tags in this repository's figures sat at 0.0mm by that measure
(`plans/fig-xii-figure-drawer-v3.md`, "What the 2c spike found").

The gap is measured to the ink (#1113): the stroke's edge, half its
width off the centreline, and the outline of any arrowhead on the line.
From the centreline, a house tag 1mm off it passed while its glyphs
touched a 0.85pt stroke, and a tag beside a head was measured as if
the head were not there.
"""

import math

from chitragupta.figure._connectors import (
    LABEL_PREFIX,
    MM,
    Connector,
    point_segment,
    segment_box_gap,
    segments,
    shown_as,
    shrink,
    solid,
    zones,
)
from chitragupta.figure._rules import RULES, Finding
from chitragupta.review.figure_layout import (
    Box,
    Drawn,
    DrawnLine,
    DrawnNode,
    Point,
    contains,
    intersects,
)

# c2: a tag's text this close to its line's ink reads as on it, and
# this far from it reads as belonging to nothing. The house `cgtag` sets
# its text 1.5mm off the centreline, about 1.35mm off a 0.85pt stroke.
_ON_LINE_MM = 1.0
_FLOATING_MM = 3.0

# c5: how far into a box a line may reach before it crosses it, so a line
# that grazes a frame is not a transit. c6 uses `review figure`'s own
# overlap test, `intersects`, and its 1pt tolerance.
_TRANSIT_PT = 1.0

# c5: a node under this in both dimensions is a marker set on the line
# (a dot on a number line, `gain-as-fraction.tex`), not a box it crosses.
_MARKER_MM = 2.0


def tag_clearance(cons: list[Connector], drawn: Drawn) -> list[Finding]:
    """`c2-tag-clearance`: a tag's text under 1mm or over 3mm from its
    own line's ink."""
    found = []
    for con in cons:
        for box, how in _tags(con, drawn):
            gap = _ink_gap(con.line, box)
            if gap < _ON_LINE_MM * MM or gap > _FLOATING_MM * MM:
                found.append(
                    Finding(
                        "c2-tag-clearance", con.name, f"tag {gap / MM:.1f}mm from its line{how}"
                    )
                )
    return found


def transit(cons: list[Connector], drawn: Drawn, layout: str | None = None) -> list[Finding]:
    """`c5-transit`: a connector crossing a node that is neither of its
    ends. A zone containing either end is not counted, nor is a tag. A
    layout the rule exempts is not evaluated."""
    if layout in RULES["c5-transit"].exempt:
        return []
    nodes = solid(drawn)
    hidden = _unframed_zones(nodes)
    found = []
    for con in cons:
        ends = (nodes[con.start].box, nodes[con.end].box)
        for name, node in nodes.items():
            if (
                name in (con.start, con.end)
                or name in hidden
                or any(contains(node.box, end) for end in ends)
                or _is_marker(node.box)
            ):
                continue
            inner = shrink(node.box, _TRANSIT_PT)
            if any(segment_box_gap(p, q, inner) == 0 for p, q in segments(con.line.points)):
                found.append(Finding("c5-transit", con.name, f"crosses {shown_as(name, node)}"))
    return found


def tag_covered(cons: list[Connector], drawn: Drawn) -> list[Finding]:
    """`c6-tag-covered`: a connector's tag overlapping a node. A zone
    containing the tag is not counted."""
    nodes = solid(drawn)
    hidden = _unframed_zones(nodes)
    found = []
    for con in cons:
        for box, _ in _tags(con, drawn):
            for name, node in nodes.items():
                if name not in hidden and not contains(node.box, box) and intersects(box, node.box):
                    under = f"tag under {shown_as(name, node)}"
                    found.append(Finding("c6-tag-covered", con.name, under))
    return found


def _ink_gap(line: DrawnLine, box: Box) -> float:
    """From `box` to the nearest ink of `line`: its stroke, half its
    width either side of the centreline, or an arrowhead the tag sits
    beside. Beside, not merely near: a head counts only where the tag's
    text and the head share a stretch of the line, so a midway tag on a
    short edge whose corner comes close to a head's barb is not a tag
    on the head (#1113's review)."""
    pieces = segments(line.points)
    stroke = min(segment_box_gap(p, q, box) for p, q in pieces)
    gaps = [max(0.0, stroke - line.width / 2)]
    for head in line.heads:
        outline = _hull(head)
        if _beside(box, outline, pieces):
            gaps.append(min(segment_box_gap(p, q, box) for p, q in zip(outline, outline[1:])))
    return min(gaps)


def _beside(box: Box, outline: list[Point], pieces: list[tuple[Point, Point]]) -> bool:
    """Whether `box` and the head `outline` overlap along the stretch of
    line the head sits on: both projected onto that segment's direction."""
    cx = sum(x for x, _ in outline) / len(outline)
    cy = sum(y for _, y in outline) / len(outline)
    p, q = min(pieces, key=lambda piece: point_segment((cx, cy), *piece))
    length = math.hypot(q[0] - p[0], q[1] - p[1]) or 1.0
    ux, uy = (q[0] - p[0]) / length, (q[1] - p[1]) / length
    corners = [(box[0], box[1]), (box[0], box[3]), (box[2], box[1]), (box[2], box[3])]
    tag = [x * ux + y * uy for x, y in corners]
    head = [x * ux + y * uy for x, y in outline]
    return max(min(tag), min(head)) < min(max(tag), max(head))


def _hull(points: tuple[Point, ...]) -> list[Point]:
    """The convex hull of `points`, closed (first point repeated), by
    Andrew's monotone chain: pgf logs a tip's hull points in no promised
    order, and joining them as logged could cut across the head."""
    ordered = sorted(set(points))
    if len(ordered) < 3:
        return ordered + ordered[:1]

    def half(chain: list[Point]) -> list[Point]:
        out: list[Point] = []
        for point in chain:
            while len(out) > 1 and _turn(out[-2], out[-1], point) <= 0:
                out.pop()
            out.append(point)
        return out[:-1]

    hull = half(ordered) + half(ordered[::-1])
    return hull + hull[:1]


def _turn(o: Point, a: Point, b: Point) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _tags(con: Connector, drawn: Drawn) -> list[tuple[Box, str]]:
    """`(box, note)` per tag on the connector: its text box, or its node
    box, noted, where its shape has no `text` anchor. A tag turned
    other than a quarter (`sloped` on a slanted line) is skipped: its
    boxes, read square to the page, are not where it was set. One on an
    upright line is turned a quarter and measured (#1064)."""
    tags = []
    for name in con.line.labels:
        node = drawn.nodes.get(name)
        if node is None or not name.startswith(LABEL_PREFIX) or node.rotated:
            continue
        tags.append((node.text_box, "") if node.text_box else (node.box, " (node box)"))
    return tags


def _unframed_zones(nodes: dict[str, DrawnNode]) -> set[str]:
    """Groups with no frame (an undrawn `fit`), which nothing is hidden
    behind or covered by (`data-flow-test.tex`)."""
    return {name for name in zones(nodes) if not nodes[name].framed}


def _is_marker(box: Box) -> bool:
    return box[2] - box[0] < _MARKER_MM * MM and box[3] - box[1] < _MARKER_MM * MM

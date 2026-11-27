"""Clearance rules over a figure's connectors (#1054): `c2-tag-clearance`,
`c5-transit` and `c6-tag-covered`.

A tag is an unnamed node on a connector's path (a named one is a node in its
own right). It is measured by its text box: its node box touches the line by
construction (141 of 160 tags measured 0.0mm, plans/fig-xii-figure-drawer-v3.md).
The gap is to the ink (#1113): the stroke's edge and any arrowhead outline,
not the centreline, which passed tags whose glyphs touched the stroke.
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

# c2: closer than this to its line's ink reads as on it, farther as belonging to
# nothing. The house `cgtag` sits ~1.35mm off a 0.85pt stroke.
_ON_LINE_MM = 1.0
_FLOATING_MM = 3.0

# c5: how far a line may reach into a box before it crosses it (grazing is not a
# transit). c6 uses `review figure`'s `intersects` and its 1pt tolerance.
_TRANSIT_PT = 1.0

# c5: a node under this in both dimensions is a marker on the line (a dot on a
# number line), not a box it crosses.
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
    """`c5-transit`: a connector crossing a node that is neither of its ends,
    excluding zones containing an end, tags, and exempt layouts."""
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
    """`c6-tag-covered`: a connector's tag overlapping a node. A zone holding the
    tag is not counted, but a card is, since it hides the tag (#1163)."""
    nodes = solid(drawn)
    groups = zones(nodes)
    hidden = _unframed_zones(nodes)
    found = []
    for con in cons:
        for box, _ in _tags(con, drawn):
            for name, node in nodes.items():
                held = name in groups and contains(node.box, box)
                if name not in hidden and not held and intersects(box, node.box):
                    under = f"tag under {shown_as(name, node)}"
                    found.append(Finding("c6-tag-covered", con.name, under))
    return found


def _ink_gap(line: DrawnLine, box: Box) -> float:
    """From `box` to `line`'s nearest ink: the stroke's edge or an arrowhead the
    tag sits *beside* (sharing a stretch of line), so a corner near a barb on a
    short edge does not count (#1113)."""
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
    """The closed convex hull of `points` (Andrew's monotone chain): pgf logs a
    tip's hull points in no promised order."""
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
    """`(box, note)` per tag: its text box, or its node box (noted) without a
    `text` anchor. Tags turned other than a quarter are skipped, as their boxes
    read square to the page are wrong (#1064)."""
    tags = []
    for name in con.line.labels:
        node = drawn.nodes.get(name)
        if node is None or not name.startswith(LABEL_PREFIX) or node.rotated:
            continue
        tags.append((node.text_box, "") if node.text_box else (node.box, " (node box)"))
    return tags


def _unframed_zones(nodes: dict[str, DrawnNode]) -> set[str]:
    """Unframed groups (an undrawn `fit`), which nothing is hidden behind."""
    return {name for name in zones(nodes) if not nodes[name].framed}


def _is_marker(box: Box) -> bool:
    return box[2] - box[0] < _MARKER_MM * MM and box[3] - box[1] < _MARKER_MM * MM

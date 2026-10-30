"""Connectors: the drawn lines that run between two nodes (#1054).

The connector rules measure lines TikZ drew (`review/figure_layout/
_drawn.py`), and a line is a connector when its two ends touch two
different nodes. Everything else that was stroked (an axis, a plotted
curve, a bus line, a self-loop) is returned beside them, so the report can
say how many lines the rules did not check rather than pass them
silently.

All coordinates are pt, as the probe reports them.
"""

import math
from dataclasses import dataclass

from chitragupta.review.figure_layout import (
    Box,
    Drawn,
    DrawnLine,
    DrawnNode,
    Point,
    contains,
)

MM = 72.27 / 25.4

# How close an end must be to a node's box to attach to it. A line TikZ
# ends at a node's border lands on it to rounding; 1.5pt also takes in the
# half line width a border anchor sits outside the frame.
ATTACH_PT = 1.5

# Below this, in either dimension, a box is a point or a hairline: a
# `coordinate`, or a node with no text and no minimum size.
_DEGENERATE_PT = 0.5

# TikZ's unnamed nodes, named by the probe. They are labels and stray
# text, never something a line connects.
LABEL_PREFIX = "cgu-"


@dataclass(frozen=True)
class Connector:
    """`name` is how a finding shows it: its ends `shown_as`."""

    line: DrawnLine
    start: str
    end: str
    name: str


def solid(drawn: Drawn) -> dict[str, DrawnNode]:
    """The nodes a line can connect: named, not a coordinate, not
    degenerate."""
    return {
        name: node
        for name, node in drawn.nodes.items()
        if not name.startswith(LABEL_PREFIX)
        and node.shape != "coordinate"
        and node.box[2] - node.box[0] > _DEGENERATE_PT
        and node.box[3] - node.box[1] > _DEGENERATE_PT
    }


def attach(point: Point, nodes: dict[str, DrawnNode]) -> str | None:
    """The node `point` ends on: the smallest box within `ATTACH_PT`, so
    an end inside a zone card attaches to the member it touches, not the
    card around it."""
    hits = [node for node in nodes.values() if _within(point, node.box, ATTACH_PT)]
    if not hits:
        return None
    return min(hits, key=lambda node: _area(node.box)).name


def connectors(drawn: Drawn) -> tuple[list[Connector], list[DrawnLine]]:
    """`(connectors, every other stroked line)`, in drawing order."""
    nodes = solid(drawn)
    found, loose = [], []
    for line in drawn.lines:
        start, end = attach(line.points[0], nodes), attach(line.points[-1], nodes)
        if start and end and start != end:
            name = f"{shown_as(start, nodes[start])}->{shown_as(end, nodes[end])}"
            found.append(Connector(line, start, end, name))
        else:
            loose.append(line)
    return found, loose


def shown_as(name: str, node: DrawnNode) -> str:
    """A node's name in a finding: its own, or its centre where no source
    says it. That is an unnamed node, and one TikZ named itself,
    `tikz@f@<n>`: a pin, an `alias`, an unnamed node before `edge` or
    `child`, an unnamed `fit` (#1087)."""
    if not name.startswith(LABEL_PREFIX) and "@" not in name:
        return name
    x = (node.box[0] + node.box[2]) / 2
    y = (node.box[1] + node.box[3]) / 2
    return f"({x / MM:.1f},{y / MM:.1f})"


def zones(nodes: dict[str, DrawnNode]) -> set[str]:
    """The nodes that contain another: zone cards and `fit` groups."""
    return {
        name
        for name, node in nodes.items()
        if any(
            other is not node
            and _area(other.box) < _area(node.box)
            and contains(node.box, other.box)
            for other in nodes.values()
        )
    }


def segments(points: tuple[Point, ...]) -> list[tuple[Point, Point]]:
    return list(zip(points, points[1:]))


def shrink(box: Box, by: float) -> Box:
    return (box[0] + by, box[1] + by, box[2] - by, box[3] - by)


def segment_box_gap(p: Point, q: Point, box: Box) -> float:
    """The shortest distance between segment `pq` and `box`; 0 where
    they meet."""
    if _clips(p, q, box):
        return 0.0
    corners = [(box[0], box[1]), (box[0], box[3]), (box[2], box[1]), (box[2], box[3])]
    return min([point_box(p, box), point_box(q, box)] + [point_segment(c, p, q) for c in corners])


def point_segment(c: Point, p: Point, q: Point) -> float:
    """The distance from `c` to segment `pq`."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    length = dx * dx + dy * dy
    t = (
        0.0
        if length == 0
        else max(0.0, min(1.0, ((c[0] - p[0]) * dx + (c[1] - p[1]) * dy) / length))
    )
    return math.hypot(c[0] - (p[0] + t * dx), c[1] - (p[1] + t * dy))


def _clips(p: Point, q: Point, box: Box) -> bool:
    """Whether segment `pq` meets `box` (Liang-Barsky)."""
    low, high = 0.0, 1.0
    dx, dy = q[0] - p[0], q[1] - p[1]
    for step, gap in (
        (-dx, p[0] - box[0]),
        (dx, box[2] - p[0]),
        (-dy, p[1] - box[1]),
        (dy, box[3] - p[1]),
    ):
        if step == 0:
            if gap < 0:
                return False
            continue
        t = gap / step
        if step < 0:
            low = max(low, t)
        else:
            high = min(high, t)
        if low > high:
            return False
    return True


def point_box(point: Point, box: Box) -> float:
    dx = max(box[0] - point[0], 0.0, point[0] - box[2])
    dy = max(box[1] - point[1], 0.0, point[1] - box[3])
    return math.hypot(dx, dy)


def _within(point: Point, box: Box, tolerance: float) -> bool:
    return point_box(point, box) <= tolerance


def _area(box: Box) -> float:
    return (box[2] - box[0]) * (box[3] - box[1])

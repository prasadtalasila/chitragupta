"""Routing rules over a figure's connectors (#1054): `c1-orthogonal`,
`c3-coincident`, `c4-attach` and `c7-dangling-tip`.

Each reports a measurement in millimetres and never a verdict on the
figure as a whole, the way `figure check`'s other rules do. Thresholds
are the v3 plan's (`plans/fig-xii-figure-drawer-v3.md`, "Connector
rules"), held or moved by the bench in `bench/RESULTS.md`.
"""

import math
from itertools import combinations

from chitragupta.figure._connectors import (
    ATTACH_PT,
    MM,
    Connector,
    attach,
    point_box,
    point_segment,
    segments,
    shown_as,
    solid,
    zones,
)
from chitragupta.figure._rules import RULES, Finding
from chitragupta.review.figure_layout import Box, Drawn, DrawnLine, DrawnNode, Point

# c3: how far apart two parallel segments may be and still be one line,
# and how long they may run together.
_COLLINEAR_PT = 0.5
_SHARED_MM = 2.0

# c4: how far a lone end may sit off its side's midpoint, how far several
# may sit off even spacing, and how close two may come. The lone end's
# 1mm (the v3 plan said 0.5mm) is c1's: a line c1 accepts as level may be
# up to 1mm off, and so lands up to 1mm off one midpoint (bench/RESULTS.md).
_MIDPOINT_MM = 1.0
_SPACING_MM = 1.0
_APART_MM = 2.0

# c7: how close a tip must come to a node or a line to land on it. An
# arrow that points at a line often stops just short of it on purpose.
_LANDS_MM = 1.0

# Shapes with no flat sides, which c4 cannot measure.
ROUND = frozenset(
    {"circle", "ellipse", "circle split", "diamond", "regular polygon", "star", "cloud"}
)


def orthogonal(cons: list[Connector], layout: str | None) -> list[Finding]:
    """`c1-orthogonal`: a connector between nodes off by more than 1mm in
    both x and y is an elbow. A straight diagonal piece, or a curve, is
    not. A layout the rule exempts is not evaluated."""
    if layout in RULES["c1-orthogonal"].exempt:
        return []
    found = []
    for con in cons:
        (x0, y0), (x1, y1) = con.line.points[0], con.line.points[-1]
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        if dx > MM and dy > MM and (con.line.curved or _has_diagonal(con.line)):
            found.append(
                Finding(
                    "c1-orthogonal",
                    con.name,
                    f"off by {dx / MM:.1f}mm in x and {dy / MM:.1f}mm in y",
                )
            )
    return found


def _has_diagonal(line: DrawnLine) -> bool:
    return any(abs(q[0] - p[0]) > MM and abs(q[1] - p[1]) > MM for p, q in segments(line.points))


def coincident(cons: list[Connector]) -> list[Finding]:
    """`c3-coincident`: two connectors running together for more than
    2mm, so one hides the other. Two that share an end point are a trunk
    that forks or merges (`retrieval.tex`), which the reader follows."""
    found = []
    for one, other in combinations(cons, 2):
        if _share_an_end(one.line, other.line):
            continue
        shared = sum(
            _overlap(s, t) for s in segments(one.line.points) for t in segments(other.line.points)
        )
        if shared > _SHARED_MM * MM:
            found.append(
                Finding("c3-coincident", f"{one.name}+{other.name}", f"share {shared / MM:.1f}mm")
            )
    return found


def _share_an_end(one: DrawnLine, other: DrawnLine) -> bool:
    ends = (one.points[0], one.points[-1])
    return any(
        math.dist(a, b) <= ATTACH_PT for a in ends for b in (other.points[0], other.points[-1])
    )


def _overlap(s: tuple[Point, Point], t: tuple[Point, Point]) -> float:
    """How long two segments lie along one another (0 unless parallel and
    within `_COLLINEAR_PT`)."""
    (p, q), (r, u) = s, t
    length = math.dist(p, q)
    if length == 0 or math.dist(r, u) == 0:
        return 0.0
    if max(point_segment(r, p, q), point_segment(u, p, q)) > _COLLINEAR_PT:
        return 0.0
    dx, dy = (q[0] - p[0]) / length, (q[1] - p[1]) / length
    a = (r[0] - p[0]) * dx + (r[1] - p[1]) * dy
    b = (u[0] - p[0]) * dx + (u[1] - p[1]) * dy
    return max(0.0, min(max(a, b), length) - max(min(a, b), 0.0))


def attach_points(
    cons: list[Connector], nodes: dict[str, DrawnNode], layout: str | None = None
) -> tuple[list[Finding], list[str]]:
    """`c4-attach`: `(findings, round nodes not measured)`.

    A lone end on a side sits at its midpoint; N ends sit at `L*k/(N+1)`
    and at least 2mm apart. The side is the one the end is nearest.

    Only a straight connector's end whose last piece meets its side square
    on is measured: an edge arriving at an angle, or bent, lands off the
    midpoint by geometry, which is `c1-orthogonal`'s finding or a `bend`'s
    construction rather than a second defect. Ends at one point (a trunk)
    count once, a zone's ends are not measured (a line into a group is
    not attaching to a side), and a layout `c1` exempts is exempt here
    too."""
    if layout in RULES["c4-attach"].exempt:
        return [], []
    sides: dict[tuple[str, str], tuple[float, list[float]]] = {}
    round_nodes: list[str] = []
    groups = zones(nodes)
    for con in (con for con in cons if not con.line.curved):
        for name, at, near in _ends(con):
            if name in groups:
                continue
            if nodes[name].shape in ROUND:
                shown = shown_as(name, nodes[name])
                round_nodes += [] if shown in round_nodes else [shown]
                continue
            measured = _square_end(nodes[name].box, at, near)
            if measured:
                side, position, length = measured
                sides.setdefault((name, side), (length, []))[1].append(position)
    found = []
    for (name, side), (length, positions) in sides.items():
        problem = _spacing(_distinct(sorted(positions)), length)
        if problem:
            found.append(Finding("c4-attach", f"{shown_as(name, nodes[name])}.{side}", problem))
    return found, round_nodes


def _distinct(positions: list[float]) -> list[float]:
    """Sorted positions with those within `ATTACH_PT` of the last kept
    one dropped: ends at one point are a trunk, and count once."""
    kept = positions[:1]
    for position in positions[1:]:
        if position - kept[-1] > ATTACH_PT:
            kept.append(position)
    return kept


def _ends(con: Connector) -> list[tuple[str, Point, Point]]:
    """`(node, end point, the next distinct point along the line)` for
    both ends of a connector."""
    points = con.line.points
    first = next((p for p in points[1:] if p != points[0]), points[0])
    last = next((p for p in reversed(points[:-1]) if p != points[-1]), points[-1])
    return [(con.start, points[0], first), (con.end, points[-1], last)]


def _square_end(box: Box, at: Point, near: Point) -> tuple[str, float, float] | None:
    """The end's side, position and side length, or `None` where the
    piece meeting it is not square to it within 1mm."""
    side, position, length = _side(box, at)
    off = abs(near[1] - at[1]) if side in ("west", "east") else abs(near[0] - at[0])
    return (side, position, length) if off <= MM else None


def _side(box: Box, point: Point) -> tuple[str, float, float]:
    """`(side, position along it, its length)` for the side `point` is
    nearest."""
    w, s, e, n = box
    x, y = point
    distances = {"west": abs(x - w), "east": abs(x - e), "south": abs(y - s), "north": abs(y - n)}
    side = min(distances, key=distances.get)
    if side in ("west", "east"):
        return side, y - s, n - s
    return side, x - w, e - w


def _spacing(positions: list[float], length: float) -> str:
    """What is wrong with these ends' spacing along a side, or `""`."""
    count = len(positions)
    if count == 1:
        off = abs(positions[0] - length / 2)
        return f"1 end {off / MM:.1f}mm off the side's midpoint" if off > _MIDPOINT_MM * MM else ""
    worst = max(abs(p - length * k / (count + 1)) for k, p in enumerate(positions, start=1))
    closest = min(b - a for a, b in zip(positions, positions[1:]))
    problems = []
    if worst > _SPACING_MM * MM:
        problems.append(f"{count} ends up to {worst / MM:.1f}mm off even spacing")
    if closest < _APART_MM * MM:
        problems.append(f"{count} ends {closest / MM:.1f}mm apart")
    return "; ".join(problems)


def dangling(drawn: Drawn) -> list[Finding]:
    """`c7-dangling-tip`: an arrow that leaves a node and whose tip lands
    on no node (a label or note included, a coordinate not) and on no
    other line, within 1mm.

    Only an arrow that leaves a node: an axis points along itself and a
    dimension line's tips mark its extent, so neither points at a thing
    (`value-ladder.tex`, `four-timestamps.tex`)."""
    boxes = [node.box for node in drawn.nodes.values() if node.shape != "coordinate"]
    nodes = solid(drawn)
    found = []
    for line in drawn.lines:
        start, end = line.points[0], line.points[-1]
        for point, tip, other_end in ((start, line.start_tip, end), (end, line.end_tip, start)):
            if tip and attach(other_end, nodes) and not _lands(point, line, drawn.lines, boxes):
                found.append(
                    Finding(
                        "c7-dangling-tip",
                        f"({point[0] / MM:.1f},{point[1] / MM:.1f})",
                        "arrow tip lands on no node or line",
                    )
                )
    return found


def _lands(point: Point, line: DrawnLine, lines: list[DrawnLine], boxes: list[Box]) -> bool:
    if any(point_box(point, box) <= _LANDS_MM * MM for box in boxes):
        return True
    return any(
        point_segment(point, p, q) <= _LANDS_MM * MM
        for other in lines
        if other is not line
        for p, q in segments(other.points)
    )

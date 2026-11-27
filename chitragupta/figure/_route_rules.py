"""Routing rules over a figure's connectors (#1054): `c1-orthogonal`,
`c3-coincident`, `c4-attach` and `c7-dangling-tip`.

Each reports a measurement in mm, never a verdict. Thresholds are
`plans/fig-xii-figure-drawer-v3.md`'s, held or moved by `bench/RESULTS.md`.
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

# c4: lone-end offset from the midpoint, offset from even spacing, minimum gap.
# The lone end's 1mm (not the plan's 0.5mm) matches c1's level tolerance
# (bench/RESULTS.md).
_MIDPOINT_MM = 1.0
_SPACING_MM = 1.0
_APART_MM = 2.0

# c7: how close a tip must come to land; arrows at a line often stop short on purpose.
_LANDS_MM = 1.0

# Shapes with no flat sides, which c4 cannot measure.
ROUND = frozenset(
    {"circle", "ellipse", "circle split", "diamond", "regular polygon", "star", "cloud"}
)


def orthogonal(cons: list[Connector], layout: str | None) -> list[Finding]:
    """`c1-orthogonal`: a connector off by more than 1mm in both x and y is an
    elbow; straight diagonals and curves are not. Exempt layouts are skipped."""
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
    """`c3-coincident`: two connectors running together over 2mm, one hiding
    the other. A shared-end pair is excused only when both leave the shared
    stretch (a fork or merge); one lying on the other end to end is
    reported (#1163)."""
    found = []
    for one, other in combinations(cons, 2):
        shared = sum(
            _overlap(s, t) for s in segments(one.line.points) for t in segments(other.line.points)
        )
        if shared <= _SHARED_MM * MM:
            continue
        if not _share_an_end(one.line, other.line):
            found.append(
                Finding("c3-coincident", f"{one.name}+{other.name}", f"share {shared / MM:.1f}mm")
            )
            continue
        left, right = _length(one.line) - shared, _length(other.line) - shared
        if min(left, right) > _SHARED_MM * MM:
            continue
        lying, under = (one, other) if left < right else (other, one)
        found.append(
            Finding(
                "c3-coincident",
                f"{one.name}+{other.name}",
                f"{lying.name} lies wholly on {under.name}",
            )
        )
    return found


def _share_an_end(one: DrawnLine, other: DrawnLine) -> bool:
    ends = (one.points[0], one.points[-1])
    return any(
        math.dist(a, b) <= ATTACH_PT for a in ends for b in (other.points[0], other.points[-1])
    )


def _length(line: DrawnLine) -> float:
    return sum(math.dist(p, q) for p, q in segments(line.points))


def _overlap(s: tuple[Point, Point], t: tuple[Point, Point]) -> float:
    """How long two segments lie along one another: 0 unless both ends of `t`
    are within `_COLLINEAR_PT` of the *line* through `s` (so order does not
    matter, #1163), then the length of `t`'s projection onto `s`."""
    (p, q), (r, u) = s, t
    length = math.dist(p, q)
    if length == 0 or math.dist(r, u) == 0:
        return 0.0
    dx, dy = (q[0] - p[0]) / length, (q[1] - p[1]) / length

    def off(point: Point) -> float:
        return abs((point[0] - p[0]) * dy - (point[1] - p[1]) * dx)

    if max(off(r), off(u)) > _COLLINEAR_PT:
        return 0.0
    a = (r[0] - p[0]) * dx + (r[1] - p[1]) * dy
    b = (u[0] - p[0]) * dx + (u[1] - p[1]) * dy
    return max(0.0, min(max(a, b), length) - max(min(a, b), 0.0))


def attach_points(
    cons: list[Connector], nodes: dict[str, DrawnNode], layout: str | None = None
) -> tuple[list[Finding], list[str]]:
    """`c4-attach`: `(findings, round nodes not measured)`.

    A lone end sits at its side's midpoint; N ends at `L*k/(N+1)`, at least 2mm
    apart. Only straight ends meeting their side square on are measured: an
    angled or bent arrival is c1's finding or a `bend`'s geometry. Trunk ends
    count once; zone ends and c1-exempt layouts are skipped."""
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
    """`(node, end point, next distinct point along the line)` for both ends."""
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
    """`(side, position along it, its length)` for the side `point` is nearest."""
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
    """`c7-dangling-tip`: an arrow leaving a node whose tip lands within 1mm of
    no node (labels count, coordinates do not) and no other line. Only arrows
    leaving a node: axes and dimension lines point at nothing."""
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

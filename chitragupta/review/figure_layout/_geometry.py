"""The geometry checks: pure arithmetic over parsed node boxes.

Needs no toolchain, so it tests on CI's Windows leg without TeX.
`overlaps()` and `protrudes()` are binary; `emptiness()` is a continuous
proportion R3 forbids anything unattended from optimising, kept a
separate function so no caller treats it as a verdict.
"""

import math

# `current bounding box` is read like a node but contains every node, so
# every node-iterating check must exclude it.
BBOX_NAME = "current bounding box"

# Touching, not colliding, and a "tight" bbox: TeX rounds to ~1e-5pt and
# TikZ's bbox sits ~0.2pt inside the outermost anchors, so exact
# comparison would report every figure.
_TOLERANCE_PT = 1.0

# Generous: ordinary layered diagrams have real row gaps; this is for one
# element stranded far above the rest.
_PROTRUSION_BAND_FRACTION = 1 / 3

Box = tuple[float, float, float, float]
Point = tuple[float, float]

_CURVE_STEPS = 8


def _without_bbox(boxes: dict[str, Box]) -> dict[str, Box]:
    return {name: box for name, box in boxes.items() if name != BBOX_NAME}


def overlaps(boxes: dict[str, Box]) -> list[tuple[str, str]]:
    """Every pair of nodes whose boxes *partially* intersect.

    Edge-to-edge touching (`_TOLERANCE_PT`) and containment are not
    collisions: a zone wholly containing its children is the
    `backgrounds` idiom docs/TIKZ-STYLE.md recommends.
    """
    nodes = sorted(_without_bbox(boxes).items())
    found = []
    for index, (name, box) in enumerate(nodes):
        for other_name, other in nodes[index + 1 :]:
            if intersects(box, other) and not _either_contains(box, other):
                found.append((name, other_name))
    return found


def intersects(one: Box, other: Box) -> bool:
    """Whether two boxes overlap on *both* axes; one axis alone would
    report every vertically stacked layout."""
    ax1, ay1, ax2, ay2 = one
    bx1, by1, bx2, by2 = other
    x_overlap = min(ax2, bx2) - max(ax1, bx1)
    y_overlap = min(ay2, by2) - max(ay1, by1)
    return x_overlap > _TOLERANCE_PT and y_overlap > _TOLERANCE_PT


def _either_contains(one: Box, other: Box) -> bool:
    return contains(one, other) or contains(other, one)


def contains(outer: Box, inner: Box) -> bool:
    """Whether `outer` encloses `inner`, to `_TOLERANCE_PT`; shared with
    `figure check`'s connector rules (#1054) so a zone is one thing to both."""
    ox1, oy1, ox2, oy2 = outer
    ix1, iy1, ix2, iy2 = inner
    return (
        ox1 - ix1 <= _TOLERANCE_PT
        and oy1 - iy1 <= _TOLERANCE_PT
        and ix2 - ox2 <= _TOLERANCE_PT
        and iy2 - oy2 <= _TOLERANCE_PT
    )


def leaves(boxes: dict[str, Box]) -> list[str]:
    """The nodes enclosing no other node (#1057): a zone's area would call
    a sprawling zoned figure full."""
    nodes = _without_bbox(boxes)
    return [
        name
        for name, box in nodes.items()
        if not any(contains(box, other) for key, other in nodes.items() if key != name)
    ]


def edge_gap(one: Box, other: Box) -> float | None:
    """Nearest-point distance between two boxes joined by an edge.

    `None` where there is no gap for an arrow to cross: a zero-area box,
    containment, or intersection (`overlaps()` reports that).
    """
    if not (_area(one) and _area(other)):
        return None
    if _either_contains(one, other) or intersects(one, other):
        return None
    ax1, ay1, ax2, ay2 = one
    bx1, by1, bx2, by2 = other
    dx = max(bx1 - ax2, ax1 - bx2, 0.0)
    dy = max(by1 - ay2, ay1 - by2, 0.0)
    return math.hypot(dx, dy)


def _area(box: Box) -> float:
    x1, y1, x2, y2 = box
    return (x2 - x1) * (y2 - y1)


def protrudes(boxes: dict[str, Box]) -> bool:
    """Whether the figure has a tall empty band across its full width.

    docs/TIKZ-STYLE.md's veto: LaTeX sets a figure as a rectangle, so one
    element sticking up wastes the space beside it. Measured as the
    largest empty horizontal band, not bbox against the node union: the
    protruding element is usually a node, so the union already contains
    it and nothing would be reported. The bbox is a boundary so stray
    non-node content counts too. Vertical only: horizontal gaps make up
    pipelines and hub-and-spoke layouts.
    """
    if BBOX_NAME not in boxes:
        return False
    _, by1, _, by2 = boxes[BBOX_NAME]
    height = by2 - by1
    if height <= 0:
        return False
    bands = sorted((box[1], box[3]) for box in _without_bbox(boxes).values())
    if not bands:
        return False
    largest_gap, reach = 0.0, by1
    for low, high in [*bands, (by2, by2)]:
        largest_gap = max(largest_gap, low - reach)
        reach = max(reach, high)
    return largest_gap / height > _PROTRUSION_BAND_FRACTION


def emptiness(boxes: dict[str, Box]) -> float | None:
    """Proportion of the picture's bounding box no node occupies.

    **Continuous, and therefore human-read only** (R3): consumed by
    nothing. Overlapping nodes double-count, which is acceptable because
    `overlaps()` reports them. `None` when the picture has no extent (0.0
    would read as "perfectly packed") or names no nodes (an all-`\\draw`
    figure would read "100% empty").
    """
    if BBOX_NAME not in boxes:
        return None
    nodes = _without_bbox(boxes)
    if not nodes:
        return None
    bx1, by1, bx2, by2 = boxes[BBOX_NAME]
    bbox_area = (bx2 - bx1) * (by2 - by1)
    if bbox_area <= 0:
        return None
    filled = sum((x2 - x1) * (y2 - y1) for x1, y1, x2, y2 in nodes.values())
    return max(0.0, 1.0 - filled / bbox_area)


def subpaths(segments: list[tuple[str, Point]]) -> list[tuple[list[Point], bool]]:
    """`[(points, curved)]`, one per subpath of two points or more, from
    logged `(op, point)` segments; curves flattened, rectangles dropped."""
    pieces: list[tuple[list[Point], bool]] = []
    points: list[Point] = []
    curved, supports, rectangle = False, [], False
    for op, point in segments:
        if op in ("M", "R"):
            if len(points) > 1 and not rectangle:
                pieces.append((points, curved))
            points, curved, supports, rectangle = [point], False, [], op == "R"
        elif op == "L":
            points.append(point)
        elif op == "Z":
            points.append(points[0])
        elif op == "C":
            supports.append(point)
            if len(supports) == 3:
                points += _bezier(points[-1], supports[0], supports[1], supports[2])
                curved, supports = True, []
    if len(points) > 1 and not rectangle:
        pieces.append((points, curved))
    return pieces


def _bezier(p0: Point, p1: Point, p2: Point, p3: Point) -> list[Point]:
    """A cubic Bézier as `_CURVE_STEPS` straight pieces, `p0` excluded."""
    out = []
    for step in range(1, _CURVE_STEPS + 1):
        t = step / _CURVE_STEPS
        u = 1 - t
        out.append(
            (
                u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
            )
        )
    return out

"""The geometry checks: pure arithmetic over parsed node boxes.

Separated from `_probe.py` because none of this needs a toolchain. A box
is four floats however it was obtained, so every rule here is testable
without `pdflatex` on the host -- which is most of what makes this aid's
own test suite runnable on CI's Windows leg, where no TeX is installed.

Three checks live here, and **one of them is not like the others**:
`overlaps()` and `protrudes()` are binary, and `emptiness()` is a
continuous proportion that docs/AUTO-IMPROVEMENT.md's R3 forbids anything
unattended from optimising. The report labels which is which; this module
keeps them separate functions so a caller cannot accidentally treat the
proportion as a verdict.
"""


# The name the picture's own bounding box is reported under. TikZ's
# `current bounding box` is a real pseudo-node, so it is read through the
# identical mechanism as a real node -- but it is not one, and every
# check that iterates nodes has to exclude it (it contains all of them by
# construction, so an overlap check including it reports every node).
BBOX_NAME = "current bounding box"

# Two boxes closer than this in either axis are treated as touching
# rather than colliding, and a bounding box within this of the node union
# is treated as tight. TeX rounds to ~1e-5pt, and TikZ's own bounding box
# sits a fraction inside the outermost node anchors (measured: 0.2pt on
# this host), so an exact comparison would report every figure.
_TOLERANCE_PT = 1.0

# An empty horizontal band taller than this fraction of the figure is
# reported as protrusion. A third is deliberately generous: an ordinary
# layered diagram leaves real gaps between its rows, and this check
# exists for the figure with one element stranded far above the rest,
# not for the one with comfortable row spacing.
_PROTRUSION_BAND_FRACTION = 1 / 3

Box = tuple[float, float, float, float]

def _without_bbox(boxes: dict[str, Box]) -> dict[str, Box]:
    """`boxes` minus the picture's own extent -- the real nodes only."""
    return {name: box for name, box in boxes.items() if name != BBOX_NAME}


def overlaps(boxes: dict[str, Box]) -> list[tuple[str, str]]:
    """Every pair of nodes whose boxes intersect, in a stable order.

    Binary, and the one geometry check safe for anything to act on: two
    boxes either intersect or they do not. Touching edge-to-edge is not
    an overlap -- that is a layout decision, not a collision -- so the
    comparison carries `_TOLERANCE_PT`.
    """
    nodes = sorted(_without_bbox(boxes).items())
    found = []
    for index, (name, box) in enumerate(nodes):
        for other_name, other in nodes[index + 1:]:
            if _intersects(box, other):
                found.append((name, other_name))
    return found


def _intersects(one: Box, other: Box) -> bool:
    """Whether two boxes overlap on *both* axes.

    Both, not either: two nodes sharing an x range but stacked vertically
    are an ordinary layered layout, and checking one axis alone would
    report every one of them.
    """
    ax1, ay1, ax2, ay2 = one
    bx1, by1, bx2, by2 = other
    x_overlap = min(ax2, bx2) - max(ax1, bx1)
    y_overlap = min(ay2, by2) - max(ay1, by1)
    return x_overlap > _TOLERANCE_PT and y_overlap > _TOLERANCE_PT


def _union(boxes: dict[str, Box]) -> Box | None:
    """The smallest box containing every node."""
    nodes = _without_bbox(boxes)
    if not nodes:
        return None
    return (
        min(box[0] for box in nodes.values()), min(box[1] for box in nodes.values()),
        max(box[2] for box in nodes.values()), max(box[3] for box in nodes.values()),
    )


def protrudes(boxes: dict[str, Box]) -> bool:
    """Whether the figure has a tall empty band across its full width.

    docs/TIKZ-STYLE.md's LaTeX-specific veto, as arithmetic: LaTeX sets a
    figure as a rectangular box, so one element sticking out above the
    main block forces surrounding text to wrap around the highest point
    and wastes every inch of vertical space beside it.

    **Measured as the largest empty horizontal band**, not as the
    bounding box against the union of node boxes. The union is what the
    roadmap first proposed and it does not work: where the protruding
    element is itself a node -- the usual case, and the one the veto
    describes -- the union already contains it, so the two agree exactly
    and nothing is ever reported. A gap is what the defect actually is.

    One mechanism covers both shapes of it, which is why the bounding box
    is included as a boundary: a band between two nodes catches a
    protruding node, and a band between the outermost node and the
    picture's own edge catches non-node content (a stray path, a label
    placed outside every node) reaching past them.

    **Vertical only, deliberately.** The veto is about vertical space,
    and horizontal gaps are load-bearing in half of docs/TIKZ-STYLE.md's
    own layout metaphors -- a pipeline and a hub-and-spoke are *made* of
    them, so checking x would report the metaphors the standard
    recommends.
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

    **Continuous, and therefore human-read only.**
    docs/AUTO-IMPROVEMENT.md's R3 forbids a continuous score from being
    the thing an unattended loop optimises, so this is reported, labelled
    as advisory, and consumed by nothing. A figure with generous
    whitespace is not thereby a worse figure -- which is exactly why no
    machine gets to drive this number down.

    The node area is summed, so overlapping nodes are double-counted and
    the emptiness comes out slightly low. Acceptable precisely because
    overlap is reported independently by `overlaps()`: a figure clean
    enough to pass that check has no double-counted area left to distort
    this one.

    `None` where the picture has no extent to be empty of -- reporting
    0.0 there would read as "perfectly packed".
    """
    if BBOX_NAME not in boxes:
        return None
    bx1, by1, bx2, by2 = boxes[BBOX_NAME]
    bbox_area = (bx2 - bx1) * (by2 - by1)
    if bbox_area <= 0:
        return None
    filled = sum(
        (x2 - x1) * (y2 - y1) for x1, y1, x2, y2 in _without_bbox(boxes).values()
    )
    return max(0.0, 1.0 - filled / bbox_area)

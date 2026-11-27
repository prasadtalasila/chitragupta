"""`node-overlap` over every node TikZ drew (#1054).

`review figure` only measures nodes the source names, missing macro-drawn or
unnamed text; the probe logs every node, so `overlaps()` runs over all. An
unnamed node is named by its centre in mm.

Left out, since a reader sees no collision: a tag on a line (`c6-tag-covered`'s),
a node turned other than a quarter (#1064), a round node under 7mm (a
`\\cgstep` badge or a dot), and an unframed empty or grouping node.
"""

from chitragupta.figure._connectors import MM, shown_as, zones
from chitragupta.figure._route_rules import ROUND
from chitragupta.review.figure_layout import Drawn, DrawnNode, overlaps


# The house badge is a 5.8mm disc; an automaton's state is far larger.
_BADGE_MM = 7.0


def drawn_overlaps(drawn: Drawn) -> list[tuple[str, str]]:
    tags = {name for line in drawn.lines for name in line.labels}
    groups = zones(drawn.nodes)
    boxes = {
        shown_as(name, node): node.box
        for name, node in drawn.nodes.items()
        if name not in tags and _is_ink(name, node, groups)
    }
    return overlaps(boxes)


def _is_ink(name: str, node: DrawnNode, groups: set[str]) -> bool:
    if node.shape == "coordinate" or node.rotated or is_badge(node):
        return False
    if node.framed:
        return True
    has_text = node.text_box is not None and node.text_box[2] > node.text_box[0]
    return has_text and name not in groups


def is_badge(node: DrawnNode) -> bool:
    """A round node under 7mm: a step badge, or a dot on a line."""
    width, height = node.box[2] - node.box[0], node.box[3] - node.box[1]
    return node.shape in ROUND and max(width, height) < _BADGE_MM * MM

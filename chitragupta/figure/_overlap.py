"""`node-overlap` over every node TikZ drew (#1054).

`review figure` measures the nodes a figure's source names, which misses
text drawn by a macro or left unnamed: `architecture.tex`'s zone titles
ran into each other and nothing reported it. `figure check`'s probe now
logs every node, so the same test, `review figure`'s own `overlaps()`,
runs over all of them. An unnamed node is named in a finding by its
centre, `(x,y)` in mm, as `c7-dangling-tip` names a point.

Four kinds of node are left out, each because a reader sees no
collision: a tag on a drawn line (that is `c6-tag-covered`'s), a node
turned other than a quarter (its box, read square to the page, is not
where it was set; a quarter turn is measured, #1064), a
round node under 7mm (a step badge `\\cgstep` sets over a node's corner on
purpose, or a dot on a line), and an unframed node with no text or that
only groups others (a placeholder, an undrawn `fit`).
"""

from chitragupta.figure._connectors import MM, shown_as, zones
from chitragupta.figure._route_rules import ROUND
from chitragupta.review.figure_layout import Drawn, DrawnNode, overlaps


# The house badge is a 5.8mm disc; an automaton's state is far larger.
_BADGE_MM = 7.0


def drawn_overlaps(drawn: Drawn) -> list[tuple[str, str]]:
    """Every pair of drawn nodes whose boxes partially intersect."""
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

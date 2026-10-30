"""Clearance rules over a figure's connectors (#1054): `c2-tag-clearance`,
`c5-transit` and `c6-tag-covered`.

A tag is an unnamed node TikZ made on a connector's path: a named one is
a node in its own right (a `child`, or `\\draw ... node (m) {}`), which a
line touches by design. A tag is measured by its text box, where the
reader sees it, because its node box touches its line by construction:
`above`, `left` and the rest anchor the box edge on the line, and 141 of
the 160 tags in this repository's figures sat at 0.0mm by that measure
(`plans/fig-xii-figure-drawer-v3.md`, "What the 2c spike found").
"""

from chitragupta.figure._connectors import (
    LABEL_PREFIX,
    MM,
    Connector,
    segment_box_gap,
    segments,
    shown_as,
    shrink,
    solid,
    zones,
)
from chitragupta.figure._rules import RULES, Finding
from chitragupta.review.figure_layout import Box, Drawn, DrawnNode, contains, intersects

# c2: a tag's text this close to its line reads as on it, and this far
# from it reads as belonging to nothing.
_ON_LINE_MM = 0.8
_FLOATING_MM = 3.0

# c5: how far into a box a line may reach before it crosses it, so a line
# that grazes a frame is not a transit. c6 uses `review figure`'s own
# overlap test, `intersects`, and its 1pt tolerance.
_TRANSIT_PT = 1.0

# c5: a node under this in both dimensions is a marker set on the line
# (a dot on a number line, `gain-as-fraction.tex`), not a box it crosses.
_MARKER_MM = 2.0


def tag_clearance(cons: list[Connector], drawn: Drawn) -> list[Finding]:
    """`c2-tag-clearance`: a tag's text under 0.8mm or over 3mm from its
    own line."""
    found = []
    for con in cons:
        for box, how in _tags(con, drawn):
            gap = min(segment_box_gap(p, q, box) for p, q in segments(con.line.points))
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

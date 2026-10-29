"""Builders for synthetic drawn figures, shared by the connector tests.

Coordinates are pt, as the probe reports them. A node's text box, where
a test needs one, is given explicitly.
"""

from chitragupta.review.figure_layout import Drawn, DrawnLine, DrawnNode


def node(
    name,
    box,
    *,
    shape="rectangle",
    text_box=None,
    framed=True,
    rotated=False,
    fill=None,
    stroke=None,
    runs=(),
):
    """`fill` and `stroke` are `Paint`s and `runs` `TextRun`s (#1055)."""
    return DrawnNode(
        name,
        shape,
        tuple(float(v) for v in box),
        text_box,
        framed,
        rotated,
        fill=fill,
        stroke=stroke,
        runs=tuple(runs),
    )


def line(*points, start_tip=False, end_tip=False, labels=(), curved=False, index=1, stroke=None):
    return DrawnLine(
        index=index,
        points=tuple((float(x), float(y)) for x, y in points),
        curved=curved,
        start_tip=start_tip,
        end_tip=end_tip,
        labels=tuple(labels),
        stroke=stroke,
    )


def drawn(nodes, lines):
    return Drawn(nodes={n.name: n for n in nodes}, lines=list(lines))

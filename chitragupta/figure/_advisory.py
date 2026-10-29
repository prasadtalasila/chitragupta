"""`figure check`'s advisory size reports (#1057): how tall the figure
is, how much of it is empty, how many nodes and edges it has, each
beside its layout's reference range, and any arrow too short to read.

**Read, never resolved, allowed or capped.** FIGURE-ROADMAP VI.3: a
bare count means little, so each number sits beside what the layout's
scaffold and exemplars measure (`_layout.py`), and a range "does not
authorise a finding when a figure exceeds it". A forty-cell DP trace is
not over budget. So the four range reports print whatever the number,
in words that describe and never judge, and the reader decides. Only
`size-squash` reports a pair it found, because a too-short arrow is a
defect of the pair, not a property of the figure.

Every number is read back from the probe's boxes and the source parser's
edge list; nothing here places anything.
"""

import re

from chitragupta.figure._layout import RangeRow, span
from chitragupta.figure._rules import Finding
from chitragupta.review.figure_layout import (
    BBOX_NAME,
    Box,
    FigureResult,
    edge_gap,
    leaves,
)

# The render's text height: the 12pt A4 1in page the layout reference
# tables already divide by (`tests/test_tikz_scaffolds.py`).
TEXT_HEIGHT_PT = 700.0

# An arrow under 3mm reads as a tick, not a direction (the v3 plan's
# threshold). Measured edge to edge; benched over the scaffolds, the
# exemplars and the reference book's 49 figures in plans/1057.
SQUASH_PT = 3 * 72.27 / 25.4

# The rules that need the compiled boxes, listed as not measured with the
# caller's reason when there are none.
GEOMETRY = ("size-height", "size-slack", "size-squash")

NO_AREA = "the picture has no area"
_NO_NODES = "the figure names no node"

# A leading option group on a path coordinate, `[xshift=2mm]a.south`: a
# shifted point on node `a`, so the node is what the arrow leaves.
_LEADING_OPTION_RE = re.compile(r"^\[[^\]]*\]\s*")


def advise(
    figure: FigureResult, layout: str, rows: list[RangeRow] | None, unmeasurable: str
) -> tuple[list[Finding], list[tuple[str, str]]]:
    """`(reports, not_measured)` for one figure, in registry order.

    `layout` is the name the figure declared (or `--layout` gave), `rows`
    its reference file's rows or `None` where it has none, and
    `unmeasurable` why the boxes cannot be read, or `""` where they can.
    The counts are read from source, so they print either way."""
    reports: list[Finding] = []
    not_measured: list[tuple[str, str]] = []
    if unmeasurable:
        not_measured += [(rule, unmeasurable) for rule in GEOMETRY]
    else:
        reports, not_measured = _measured(figure, layout, rows)
    nodes, edges = len(figure.declared), len(figure.edges)
    reports.append(
        Finding(
            "budget-nodes", "figure", f"{_count(nodes, 'node')}; {_beside(layout, rows, 'nodes')}"
        )
    )
    reports.append(
        Finding(
            "budget-edges", "figure", f"{_count(edges, 'edge')}; {_beside(layout, rows, 'edges')}"
        )
    )
    return reports, not_measured


def _measured(
    figure: FigureResult, layout: str, rows: list[RangeRow] | None
) -> tuple[list[Finding], list[tuple[str, str]]]:
    """Height, slack and squash, from boxes known to be there."""
    boxes = figure.boxes
    x1, y1, x2, y2 = boxes[BBOX_NAME]
    width, height = x2 - x1, y2 - y1
    reports, not_measured = [], []
    if width * height <= 0:
        not_measured += [("size-height", NO_AREA), ("size-slack", NO_AREA)]
    else:
        share = height / TEXT_HEIGHT_PT
        reports.append(
            Finding(
                "size-height",
                "figure",
                f"{share:.2f} of the text height ({height:.0f}pt); "
                f"{_beside(layout, rows, 'height')}",
            )
        )
        if len(boxes) == 1:
            not_measured.append(("size-slack", _NO_NODES))
        else:
            reports.append(
                Finding(
                    "size-slack",
                    "figure",
                    f"{slack(boxes):.2f}; {_beside(layout, rows, 'slack')}",
                )
            )
    squashed, unreadable = _squashed(boxes, figure.edges)
    reports += squashed
    if unreadable:
        shown = ", ".join(f"{one} -> {other}" for one, other in unreadable)
        not_measured.append(
            ("size-squash", f"{_count(len(unreadable), 'edge')} {_ends(unreadable)}: {shown}")
        )
    return reports, not_measured


def slack(boxes: dict[str, Box]) -> float:
    """The share of the picture no leaf node fills, zone cards excluded:
    the reference tables' definition, so a figure and its reference are
    measured alike. Overlapping leaves are double-counted; `node-overlap`
    reports them."""
    x1, y1, x2, y2 = boxes[BBOX_NAME]
    filled = sum(_area(boxes[name]) for name in leaves(boxes))
    return 1 - filled / ((x2 - x1) * (y2 - y1))


def _squashed(
    boxes: dict[str, Box], edges: list[tuple[str, str]]
) -> tuple[list[Finding], list[tuple[str, str]]]:
    """Each joined pair under `SQUASH_PT` apart, once, and the edges
    with an end that names no measured node."""
    gaps: dict[tuple[str, str], float] = {}
    unreadable = []
    for one, other in edges:
        ends = _node(one, boxes), _node(other, boxes)
        if None in ends:
            unreadable.append((one, other))
            continue
        gap = edge_gap(boxes[ends[0]], boxes[ends[1]]) if ends[0] != ends[1] else None
        if gap is not None:
            gaps[tuple(sorted(ends))] = gap
    found = [
        Finding(
            "size-squash", f"{a}+{b}", f"{gap / SQUASH_PT * 3:.1f}mm apart edge to edge, under 3mm"
        )
        for (a, b), gap in sorted(gaps.items())
        if gap < SQUASH_PT
    ]
    return found, unreadable


def _node(token: str, boxes: dict[str, Box]) -> str | None:
    """The measured node a path coordinate names, anchor and leading
    option set aside, or `None`."""
    token = _LEADING_OPTION_RE.sub("", token)
    for name in (token, token.rsplit(".", 1)[0]):
        if name in boxes and name != BBOX_NAME:
            return name
    return None


def _beside(layout: str, rows: list[RangeRow] | None, column: str) -> str:
    """The reference a number is read beside, or why there is none."""
    if not layout:
        return "no layout declared (`% cg-layout:` or --layout)"
    if rows is None:
        return f"layout `{layout}` has no reference file"
    if not rows:
        return f"the `{layout}` reference file has no measured rows"
    low, high = span(rows, column)
    shown = (lambda v: f"{v:g}") if column in ("nodes", "edges") else (lambda v: f"{v:.2f}")
    return f"{layout} reference {shown(low)}" + ("" if low == high else f" to {shown(high)}")


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def _ends(unreadable: list) -> str:
    return "ends at no measured node" if len(unreadable) == 1 else "end at no measured node"


def _area(box: Box) -> float:
    x1, y1, x2, y2 = box
    return (x2 - x1) * (y2 - y1)

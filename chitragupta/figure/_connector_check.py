"""The connector rules, `c1` to `c7`, as `figure check` runs them (#1054).

The rules themselves are `_route_rules.py` and `_clearance_rules.py`.
"""

from chitragupta._tex_comments import strip_comments
from chitragupta.figure._clearance_rules import tag_clearance, tag_covered, transit
from chitragupta.figure._connectors import connectors, solid
from chitragupta.figure._route_rules import attach_points, coincident, dangling, orthogonal
from chitragupta.figure._rules import RULES, Finding
from chitragupta.review.figure_layout import FigureResult

CONNECTOR = tuple(rule for rule in RULES if rule.startswith("c") and rule[1].isdigit())

# Why the connector rules alone could not run: lines and node boxes must share a
# frame, and `transform canvas` or an earlier picture's nodes break that.
NO_DRAWN = "the probe reported no drawn lines"
CANVAS = "the figure uses `transform canvas`, which moves lines out of the nodes' frame"
_SEVERAL = "{} tikzpictures; their nodes are not in one frame"


def connector_rules(
    source: str, figure: FigureResult, layout: str, pictures: int
) -> tuple[list[Finding], list[tuple[str, str]]]:
    """c1 to c7 over what the probe drew, or each listed as not measured
    with the reason. `pictures` is the file's `tikzpicture` count."""
    why = unconnectable(source, figure, pictures)
    if why:
        return [], [(rule, why) for rule in CONNECTOR]
    drawn = figure.drawn
    cons, _ = connectors(drawn)
    attached, round_nodes = attach_points(cons, solid(drawn), layout)
    found = (
        orthogonal(cons, layout)
        + tag_clearance(cons, drawn)
        + coincident(cons)
        + attached
        + transit(cons, drawn, layout)
        + tag_covered(cons, drawn)
        + dangling(drawn)
    )
    if not round_nodes:
        return found, []
    return found, [("c4-attach", f"round nodes, which have no sides: {', '.join(round_nodes)}")]


def unconnectable(source: str, figure: FigureResult, pictures: int) -> str:
    """Why the connector rules cannot run on this figure, or `""`. k1 and
    k2 read the same lines and boxes, so share it (#1055)."""
    if figure.drawn is None:
        return NO_DRAWN
    if pictures > 1:
        return _SEVERAL.format(pictures)
    if "transform canvas" in strip_comments(source):
        return CANVAS
    return ""

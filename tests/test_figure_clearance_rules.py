"""Clearance rules c2, c5 and c6 over synthetic drawn figures (#1054).

Coordinates are pt; 1mm is about 2.85pt. A tag is an unnamed node on a
connector's path, and its text box is what a reader sees, so the tests
give one explicitly.
"""

from chitragupta.figure._clearance_rules import tag_clearance, tag_covered, transit
from chitragupta.figure._connectors import MM, connectors
from tests.figure_drawn_fixtures import drawn, line, node

A = node("a", (0, 0, 40, 20))
B = node("b", (100, 0, 140, 20))


def _tag(name, text_box, *, frame=None):
    """A tag whose node box is its text box padded by 1pt."""
    x1, y1, x2, y2 = text_box
    return node(name, frame or (x1 - 1, y1 - 1, x2 + 1, y2 + 1), text_box=text_box)


def _figure(*extra_nodes, tags=("cgu-1",), points=((40, 10), (100, 10))):
    nodes = [A, B, *extra_nodes]
    figure = drawn(nodes, [line(*points, labels=tags)])
    return figure, connectors(figure)[0]


class TestTagClearance:
    def test_c2_fires_on_a_tag_touching_its_line(self):
        """TikZ's `above` puts the node box on the line; the text sits a
        point clear, which a reader reads as touching."""
        figure, cons = _figure(_tag("cgu-1", (60, 11, 80, 18)))

        (finding,) = tag_clearance(cons, figure)

        assert (finding.rule, finding.target) == ("c2-tag-clearance", "a->b")
        assert finding.measurement == f"tag {1 / MM:.1f}mm from its line"

    def test_c2_fires_on_a_tag_floating_away(self):
        figure, cons = _figure(_tag("cgu-1", (60, 10 + 5 * MM, 80, 30)))

        (finding,) = tag_clearance(cons, figure)

        assert finding.measurement == "tag 5.0mm from its line"

    def test_c2_holds_on_a_tag_1_5mm_beside_its_line(self):
        figure, cons = _figure(_tag("cgu-1", (60, 10 + 1.5 * MM, 80, 25)))

        assert tag_clearance(cons, figure) == []

    def test_c2_holds_on_a_line_with_no_tag(self):
        figure, cons = _figure(tags=())

        assert tag_clearance(cons, figure) == []

    def test_c2_holds_on_a_named_node_made_on_the_path(self):
        """A `child` node, or `\\draw ... node (m) {}`, is a node, not a
        tag: the tree's edge touches it by design."""
        figure, cons = _figure(_tag("m", (60, 8, 80, 12)), tags=("m",))

        assert tag_clearance(cons, figure) == []

    def test_c2_measures_a_tag_with_no_text_box_by_its_node_box(self):
        figure, cons = _figure(node("cgu-1", (60, 10, 80, 18), shape="coordinate"))

        (finding,) = tag_clearance(cons, figure)

        assert finding.measurement == "tag 0.0mm from its line (node box)"


class TestTransit:
    def test_c5_fires_on_a_line_through_a_third_node(self):
        figure, cons = _figure(node("c", (60, 0, 80, 20)), tags=())

        (finding,) = transit(cons, figure)

        assert (finding.rule, finding.target, finding.measurement) == (
            "c5-transit",
            "a->b",
            "crosses c",
        )

    def test_c5_holds_through_a_zone_containing_an_end(self):
        figure, cons = _figure(node("zone", (-10, -10, 60, 30)), tags=())

        assert transit(cons, figure) == []

    def test_c5_holds_through_its_own_tag(self):
        figure, cons = _figure(_tag("cgu-1", (60, 5, 80, 15)))

        assert transit(cons, figure) == []

    def test_c5_holds_across_a_lifeline_in_a_sequence(self):
        """A message that skips the middle lifeline is the diagram's
        grammar, not a line through a box."""
        figure, cons = _figure(node("c", (68, 0, 74, 20)), tags=())

        assert transit(cons, figure, "sequence") == []

    def test_c5_holds_grazing_a_box_within_1pt(self):
        figure, cons = _figure(node("c", (60, 10.5, 80, 30)), tags=())

        assert transit(cons, figure) == []


class TestTagCovered:
    def test_c6_fires_on_a_tag_over_a_node(self):
        figure, cons = _figure(node("c", (70, 12, 90, 30)), _tag("cgu-1", (60, 13, 80, 18)))

        (finding,) = tag_covered(cons, figure)

        assert (finding.rule, finding.target, finding.measurement) == (
            "c6-tag-covered",
            "a->b",
            "tag under c",
        )

    def test_c6_holds_on_a_tag_inside_its_zone(self):
        figure, cons = _figure(node("zone", (-10, -10, 150, 40)), _tag("cgu-1", (60, 13, 80, 18)))

        assert tag_covered(cons, figure) == []

    def test_c6_holds_on_a_tag_clear_of_every_node(self):
        figure, cons = _figure(_tag("cgu-1", (60, 13, 80, 18)))

        assert tag_covered(cons, figure) == []


def test_c5_holds_through_a_marker_dot():
    """`gain-as-fraction.tex`: a dot placed on a number line is on it."""
    figure, cons = _figure(node("dot", (68, 8, 72, 12), shape="circle"), tags=())

    assert transit(cons, figure) == []


def test_c5_holds_through_an_unframed_group():
    """An undrawn `fit` around a node hides nothing a line could cross."""
    group = node("group", (60, 0, 80, 35), framed=False)
    member = node("m", (65, 25, 75, 30))
    figure, cons = _figure(group, member, tags=())

    assert transit(cons, figure) == []


def test_c5_fires_through_an_unframed_node_with_text():
    """An unframed annotation is still words a line would run through."""
    figure, cons = _figure(node("note", (60, 0, 80, 20), framed=False), tags=())

    assert [f.measurement for f in transit(cons, figure)] == ["crosses note"]


def test_c6_holds_under_an_unframed_group():
    """`data-flow-test.tex`: a tag past the edge of an undrawn `fit`."""
    panel = node("panel", (70, 12, 90, 30), framed=False)
    member = node("q", (75, 22, 85, 28))
    figure, cons = _figure(panel, member, _tag("cgu-1", (60, 13, 80, 18)))

    assert tag_covered(cons, figure) == []


def test_c2_and_c6_skip_a_sloped_tag():
    """`twin-pgm.tex`: a sloped tag's unrotated text box is not where it
    was set."""
    tag = node("cgu-1", (60, 9, 80, 18), text_box=(60, 9, 80, 18), rotated=True)
    figure, cons = _figure(node("c", (70, 12, 90, 30)), tag)

    assert tag_clearance(cons, figure) == [] and tag_covered(cons, figure) == []

"""Connectors: the drawn lines that run between two nodes (#1054).

Synthetic `Drawn` figures, in pt, so the geometry is checked without
TeX. `tests/figure_drawn_fixtures.py` builds them.
"""

import pytest

from chitragupta.figure._connectors import (
    MM,
    attach,
    connectors,
    segment_box_gap,
    solid,
    zones,
)
from tests.figure_drawn_fixtures import drawn, line, node


def test_a_line_between_two_boxes_is_a_connector():
    figure = drawn(
        [node("a", (0, 0, 20, 10)), node("b", (60, 0, 80, 10))],
        [line((20, 5), (60, 5))],
    )

    (connector,), loose = connectors(figure)

    assert (connector.start, connector.end, connector.name) == ("a", "b", "a->b")
    assert loose == []


def test_a_node_tikz_named_itself_still_connects_and_is_shown_by_position():
    """`\\node {A} edge (b);` makes TikZ name `A` `tikz@f@1`. It is still
    the line's end, but no source says that name, so a finding names it
    by its centre, as an unnamed node is (#1087)."""
    figure = drawn(
        [node("tikz@f@1", (0, 0, 20, 10)), node("b", (60, 0, 80, 10))],
        [line((20, 5), (60, 5))],
    )

    (connector,), _ = connectors(figure)

    assert (connector.start, connector.end) == ("tikz@f@1", "b")
    assert connector.name == f"({10 / MM:.1f},{5 / MM:.1f})->b"


def test_an_end_inside_a_zone_attaches_to_the_member_not_the_zone():
    zone = node("zone", (-10, -10, 100, 40))
    figure = drawn(
        [zone, node("a", (0, 0, 20, 10)), node("b", (60, 0, 80, 10))],
        [line((20, 5), (60, 5))],
    )

    (connector,), _ = connectors(figure)

    assert (connector.start, connector.end) == ("a", "b")


def test_a_line_to_a_coordinate_is_not_a_connector():
    figure = drawn(
        [node("a", (0, 0, 20, 10)), node("p", (60, 5, 60, 5), shape="coordinate")],
        [line((20, 5), (60, 5))],
    )

    cons, loose = connectors(figure)

    assert cons == [] and len(loose) == 1


def test_a_label_is_not_an_end():
    """A tag on the line is a node too, but nothing connects to it."""
    figure = drawn(
        [node("a", (0, 0, 20, 10)), node("cgu-1", (55, 0, 70, 10))],
        [line((20, 5), (60, 5))],
    )

    cons, loose = connectors(figure)

    assert cons == [] and len(loose) == 1


def test_a_self_loop_is_not_a_connector():
    figure = drawn([node("a", (0, 0, 20, 10))], [line((5, 10), (10, 30), (15, 10))])

    cons, loose = connectors(figure)

    assert cons == [] and len(loose) == 1


def test_an_end_within_the_tolerance_attaches():
    nodes = solid(drawn([node("a", (0, 0, 20, 10))], []))

    assert attach((21.4, 5), nodes) == "a"
    assert attach((21.6, 5), nodes) is None


def test_solid_drops_degenerate_boxes():
    figure = drawn([node("a", (0, 0, 20, 10)), node("thin", (0, 0, 0.2, 10))], [])

    assert set(solid(figure)) == {"a"}


def test_the_gap_from_a_crossing_segment_is_zero():
    assert segment_box_gap((-10, 5), (30, 5), (0, 0, 20, 10)) == 0.0


def test_the_gap_to_a_box_beside_a_segment_is_the_perpendicular_distance():
    assert segment_box_gap((0, 15), (20, 15), (0, 0, 20, 10)) == pytest.approx(5.0)


def test_the_gap_past_a_corner_is_the_corner_distance():
    assert segment_box_gap((23, 14), (30, 20), (0, 0, 20, 10)) == pytest.approx(5.0)


def test_the_gap_from_a_zero_length_segment_is_its_point_distance():
    """A path can repeat a point; pgf logs it as a segment of length 0."""
    assert segment_box_gap((23, 14), (23, 14), (0, 0, 20, 10)) == pytest.approx(5.0)


def test_a_title_covering_a_coordinate_is_not_a_zone():
    """A point inside a box does not make the box a group: a title that
    happened to cover the `band` coordinate was taken for a zone card,
    and `node-overlap` then skipped it (#1064)."""
    title = node(
        "busy-t",
        (-18.7, -37.1, 55.7, -23.2),
        framed=False,
        text_box=(-18.7, -37.1, 55.7, -23.2),
    )
    band = node("band", (0, -30.2, 0, -30.2), shape="coordinate")

    assert zones({n.name: n for n in (title, band)}) == set()


def test_a_card_holding_a_title_and_a_coordinate_is_still_a_zone():
    card = node("quiet", (39.7, -42.0, 302.8, -18.3))
    title = node("quiet-t", (156.9, -36.9, 185.6, -23.4), framed=False)
    band = node("band", (100, -30.2, 100, -30.2), shape="coordinate")

    assert zones({n.name: n for n in (card, title, band)}) == {"quiet"}

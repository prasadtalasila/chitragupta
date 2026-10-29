"""Connectors: the drawn lines that run between two nodes (#1054).

Synthetic `Drawn` figures, in pt, so the geometry is checked without
TeX. `tests/figure_drawn_fixtures.py` builds them.
"""

import pytest

from chitragupta.figure._connectors import (
    attach,
    connectors,
    segment_box_gap,
    solid,
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

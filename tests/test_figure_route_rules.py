"""Routing rules c1, c3, c4 and c7 over synthetic drawn figures (#1054).

Coordinates are pt; 1mm is about 2.85pt. Most tests are must-not-fire
cases, because a rule that fires on a sound figure teaches an author to
allow it rather than read it.
"""

from chitragupta.figure._connectors import MM, connectors
from chitragupta.figure._route_rules import attach_points, coincident, dangling, orthogonal
from tests.figure_drawn_fixtures import drawn, line, node

A = node("a", (0, 0, 40, 20))
B = node("b", (100, 0, 140, 20))
HIGH_B = node("b", (100, 60, 140, 80))


def _cons(nodes, lines):
    return connectors(drawn(nodes, lines))[0]


class TestOrthogonal:
    def test_c1_fires_on_a_diagonal_straight_connector(self):
        (finding,) = orthogonal(_cons([A, HIGH_B], [line((40, 10), (100, 70))]), None)

        assert (finding.rule, finding.target) == ("c1-orthogonal", "a->b")
        assert finding.measurement == "off by 21.1mm in x and 21.1mm in y"

    def test_c1_fires_on_a_bent_connector_between_offset_nodes(self):
        bent = line((40, 10), (80, 30), (100, 70), curved=True)

        assert orthogonal(_cons([A, HIGH_B], [bent]), None)

    def test_c1_holds_on_an_elbow(self):
        elbow = line((20, 20), (20, 70), (100, 70))

        assert orthogonal(_cons([A, HIGH_B], [elbow]), None) == []

    def test_c1_holds_on_a_curve_between_level_nodes(self):
        bent = line((40, 10), (70, 20), (100, 10), curved=True)

        assert orthogonal(_cons([A, B], [bent]), None) == []

    def test_c1_holds_in_an_exempt_layout(self):
        diagonal = line((40, 10), (100, 70))

        assert orthogonal(_cons([A, HIGH_B], [diagonal]), "hub-and-spoke-network") == []

    def test_c1_holds_within_1mm_of_level(self):
        nearly = line((40, 10), (100, 10 + 0.9 * MM))

        assert orthogonal(_cons([A, B], [nearly]), None) == []


class TestCoincident:
    C = node("c", (50, 40, 70, 60))
    D = node("d", (60, -50, 80, -30))

    def _crossing(self, run, *, repeat=False):
        """`c->d`, down onto `a->b`'s line, along it for `run` pt, then
        on down."""
        middle = [(60, 10), (60, 10)] if repeat else [(60, 10)]
        return line((60, 40), *middle, (60 + run, 10), (60 + run, -30), index=2)

    def test_c3_fires_on_two_connectors_sharing_3mm(self):
        cons = _cons([A, B, self.C, self.D], [line((40, 10), (100, 10)), self._crossing(3 * MM)])

        (finding,) = coincident(cons)

        assert (finding.rule, finding.target) == ("c3-coincident", "a->b+c->d")
        assert finding.measurement == "share 3.0mm"

    def test_c3_holds_on_a_legitimate_crossing(self):
        D = node("d", (60, -40, 80, -30))
        E = node("e", (60, 40, 80, 50))
        cons = _cons([A, B, D, E], [line((40, 10), (100, 10)), line((70, -30), (70, 40), index=2)])

        assert coincident(cons) == []

    def test_c3_holds_on_parallel_lines_2pt_apart(self):
        C = node("c", (100, 40, 140, 60))
        cons = _cons(
            [A, B, C],
            [line((40, 8), (100, 8)), line((40, 12), (70, 12), (70, 50), (100, 50), index=2)],
        )

        assert coincident(cons) == []

    def test_c3_holds_on_a_shared_stretch_under_2mm(self):
        cons = _cons([A, B, self.C, self.D], [line((40, 10), (100, 10)), self._crossing(1.5 * MM)])

        assert coincident(cons) == []

    def test_c3_ignores_a_zero_length_segment(self):
        """pgf can log a repeated point; it shares nothing with anything."""
        cons = _cons(
            [A, B, self.C, self.D],
            [line((40, 10), (100, 10)), self._crossing(3 * MM, repeat=True)],
        )

        (finding,) = coincident(cons)

        assert finding.measurement == "share 3.0mm"


class TestAttach:
    def test_c4_fires_on_a_lone_end_off_centre(self):
        """`b`'s west side runs from y=0 to y=20; its midpoint is 10."""
        cons = _cons([A, B], [line((40, 10), (70, 10), (70, 10 + 2 * MM), (100, 10 + 2 * MM))])

        findings, round_nodes = attach_points(cons, drawn([A, B], []).nodes)

        (finding,) = findings
        assert (finding.rule, finding.target) == ("c4-attach", "b.west")
        assert finding.measurement == "1 end 2.0mm off the side's midpoint"
        assert round_nodes == []

    def test_c4_fires_on_two_ends_crowded(self):
        C = node("c", (100, -60, 140, -40))
        cons = _cons(
            [A, B, C],
            [
                line((40, 9), (70, 9), (70, 10), (100, 10)),
                line((40, 11), (70, 11), (70, -50), (100, -50), index=2),
            ],
        )

        findings, _ = attach_points(cons, drawn([A, B, C], []).nodes)

        assert [f.target for f in findings] == ["a.east"]
        assert "0.7mm apart" in findings[0].measurement

    def test_c4_holds_on_evenly_spaced_ends(self):
        C = node("c", (100, -60, 140, -40))
        D = node("d", (100, 60, 140, 80))
        tall = node("a", (0, 0, 40, 40))
        third = 40 / 4
        cons = _cons(
            [tall, B, C, D],
            [
                line((40, third), (100, -50)),
                line((40, 2 * third), (100, 10), index=2),
                line((40, 3 * third), (100, 70), index=3),
            ],
        )

        findings, _ = attach_points(cons, drawn([tall, B, C, D], []).nodes)

        assert [f for f in findings if f.target == "a.east"] == []

    def test_c4_holds_on_a_centred_lone_end(self):
        cons = _cons([A, B], [line((40, 10), (100, 10))])

        assert attach_points(cons, drawn([A, B], []).nodes) == ([], [])

    def test_c4_does_not_measure_a_round_node(self):
        circle = node("b", (100, -10, 140, 30), shape="circle")
        cons = _cons([A, circle], [line((40, 10), (102, 15))])

        findings, round_nodes = attach_points(cons, drawn([A, circle], []).nodes)

        assert findings == [] and round_nodes == ["b"]


class TestDangling:
    def test_c7_fires_on_a_tip_ending_in_empty_space(self):
        """`paper-twin-loop.tex`'s defect: the arrow stops at `b`'s height
        but well to its side."""
        figure = drawn([A, HIGH_B], [line((20, 20), (20, 60), end_tip=True)])

        (finding,) = dangling(figure)

        assert (finding.rule, finding.measurement) == (
            "c7-dangling-tip",
            "arrow tip lands on no node or line",
        )
        assert finding.target == f"({20 / MM:.1f},{60 / MM:.1f})"

    def test_c7_holds_on_a_tip_on_a_node(self):
        figure = drawn([A, B], [line((40, 10), (100, 10), end_tip=True)])

        assert dangling(figure) == []

    def test_c7_holds_on_a_tip_on_a_bus_line(self):
        bus = line((0, 50), (140, 50), index=2)
        figure = drawn([A], [line((20, 20), (20, 50), end_tip=True), bus])

        assert dangling(figure) == []

    def test_c7_holds_on_a_tip_on_a_label(self):
        """An arrow pointing at a note: the note is a node, unnamed."""
        note = node("cgu-1", (20, 58, 60, 70))
        figure = drawn([A, note], [line((20, 20), (20, 58), end_tip=True)])

        assert dangling(figure) == []

    def test_c7_holds_on_a_tipless_end(self):
        figure = drawn([A], [line((20, 20), (20, 60))])

        assert dangling(figure) == []

    def test_c7_reads_a_start_tip_too(self):
        figure = drawn([A], [line((20, 60), (20, 20), start_tip=True)])

        assert len(dangling(figure)) == 1


class TestEdgeCases:
    def test_c4_measures_an_end_on_a_top_side_along_x(self):
        """`b`'s south side runs from x=100 to x=140; its midpoint is 120."""
        cons = _cons([A, HIGH_B], [line((20, 20), (20, 40), (110, 40), (110, 60))])

        findings, _ = attach_points(cons, drawn([A, HIGH_B], []).nodes)

        assert [(f.target, f.measurement) for f in findings] == [
            ("b.south", f"1 end {10 / MM:.1f}mm off the side's midpoint")
        ]

    def test_c4_fires_on_ends_spread_unevenly_but_far_apart(self):
        tall = node("a", (0, 0, 40, 60))
        C = node("c", (100, -60, 140, -40))
        cons = _cons(
            [tall, B, C],
            [
                line((40, 5), (70, 5), (70, 10), (100, 10)),
                line((40, 25), (70, 25), (70, -50), (100, -50), index=2),
            ],
        )

        findings, _ = attach_points(cons, drawn([tall, B, C], []).nodes)

        (finding,) = [f for f in findings if f.target == "a.east"]
        assert finding.measurement == f"2 ends up to {15 / MM:.1f}mm off even spacing"


class TestBenchedShapes:
    """Must-not-fire shapes the bench over the repository's figures found
    (bench/RESULTS.md, 2026-10-29), each read in the rendered figure."""

    def test_c3_holds_on_a_fork_from_one_point(self):
        """`retrieval.tex`: one trunk leaves the query and splits."""
        C = node("c", (100, 40, 140, 60))
        cons = _cons(
            [A, B, C],
            [
                line((40, 10), (60, 10), (60, 5), (100, 5)),
                line((40, 10), (60, 10), (60, 50), (100, 50), index=2),
            ],
        )

        assert coincident(cons) == []

    def test_c4_holds_on_the_ends_of_a_fork(self):
        C = node("c", (100, 40, 140, 60))
        cons = _cons(
            [A, B, C],
            [
                line((40, 10), (60, 10), (60, 10), (100, 10)),
                line((40, 10), (60, 10), (60, 50), (100, 50), index=2),
            ],
        )

        findings, _ = attach_points(cons, drawn([A, B, C], []).nodes)

        assert [f for f in findings if f.target == "a.east"] == []

    def test_c4_holds_on_a_diagonal_end(self):
        """An edge arriving at an angle lands off the midpoint by
        geometry; that is c1's finding, not a second one."""
        cons = _cons([A, HIGH_B], [line((40, 10), (110, 60))])

        findings, _ = attach_points(cons, drawn([A, HIGH_B], []).nodes)

        assert [f.target for f in findings] == []

    def test_c4_holds_on_a_bent_end(self):
        """`control-loop.tex`: a `bend` leaves its side off-centre by
        construction."""
        bent = line((40, 6), (70, 0), (100, 6), curved=True)
        cons = _cons([A, B], [bent])

        assert attach_points(cons, drawn([A, B], []).nodes) == ([], [])

    def test_c4_holds_in_an_exempt_layout(self):
        cons = _cons([A, B], [line((40, 2), (100, 2))])

        assert attach_points(cons, drawn([A, B], []).nodes, "hub-and-spoke-network") == ([], [])

    def test_c4_holds_on_lifelines_in_a_sequence(self):
        """`sequence.tex`: messages meet a lifeline at heights time sets,
        not at even spacing along its side. The same lines in a pipeline
        fire on both lifelines."""
        lifelines = [node("one", (0, 0, 6, 200)), node("two", (100, 0, 106, 200))]
        messages = [line((6, y), (100, y)) for y in (150, 160, 185)]
        cons = _cons(lifelines, messages)
        nodes = drawn(lifelines, []).nodes

        assert attach_points(cons, nodes, "sequence") == ([], [])
        assert [f.target for f in attach_points(cons, nodes, "pipeline")[0]] == [
            "one.east",
            "two.west",
        ]

    def test_c7_holds_on_an_axis_arrow(self):
        """`value-ladder.tex`: an axis points along itself, at nothing."""
        figure = drawn([A], [line((0, -20), (0, 100), end_tip=True)])

        assert dangling(figure) == []

    def test_c7_holds_on_a_dimension_arrow(self):
        """`four-timestamps.tex`: a two-headed measurement line."""
        figure = drawn([A], [line((0, -30), (140, -30), start_tip=True, end_tip=True)])

        assert dangling(figure) == []

    def test_c7_holds_on_an_arrow_pointing_at_a_line_from_under_1mm(self):
        """`residual-doses.tex`: a node's arrow stops just short of the
        axis it points at."""
        axis = line((0, 50), (140, 50), index=2)
        figure = drawn([A], [line((20, 20), (20, 50 - 0.9 * MM), end_tip=True), axis])

        assert dangling(figure) == []


class TestBenchedTolerances:
    def test_c4_holds_on_a_bend_whose_last_piece_is_nearly_square(self):
        """A flattened curve's last piece is short, and can sit within
        1mm of square to its side while the bend still lands off-centre."""
        bent = line((40, 3), (50, 0.5), (90, 0.5), (100, 3), curved=True)
        cons = _cons([A, B], [bent])

        assert attach_points(cons, drawn([A, B], []).nodes) == ([], [])

    def test_c4_holds_on_a_lone_end_under_1mm_off_centre(self):
        """c1 accepts a line up to 1mm off level, which lands up to 1mm
        off one midpoint; c4 must not report what c1 accepts."""
        cons = _cons([A, B], [line((40, 10), (100, 10 + 0.9 * MM))])

        assert attach_points(cons, drawn([A, B], []).nodes) == ([], [])


def test_c4_does_not_measure_a_zone():
    """`pctrl-blocks.tex`: a line into a group ends on its card, not on a
    node's side."""
    zone = node("zone", (90, -20, 160, 40))
    inner = node("b", (100, 0, 140, 20))
    cons = _cons([A, zone, inner], [line((40, 10), (70, 10), (70, 35), (90, 35))])

    findings, _ = attach_points(cons, drawn([A, zone, inner], []).nodes)

    assert findings == []

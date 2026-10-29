"""`figure check`'s advisory size reports (#1057): height, slack and the
two counts beside the layout's reference range, and an arrow too short
to read. All five are read, never resolved, allowed or capped.

Evaluated over hand-built `FigureResult`s, so this runs on every host.
"""

from pathlib import Path

import pytest

from chitragupta.figure import _advisory
from chitragupta.figure._layout import RangeRow
from chitragupta.figure._rules import RULES
from chitragupta.review.figure_layout import BBOX_NAME, FigureResult

ROWS = [
    RangeRow("assets/tikz/pipeline.tex", 5, 3, 0.68, 0.10, 0.55),
    RangeRow("assets/tikz/exemplars/rag-stages.tex", 11, 4, 1.09, 0.35, 0.71),
]
ADVISORY = ["size-height", "size-slack", "size-squash", "budget-nodes", "budget-edges"]


def _figure(boxes=None, edges=(), declared=None, picture=(0.0, 0.0, 200.0, 70.0)):
    """Two 20x20 nodes 60pt apart on a 200x70pt picture, unless told
    otherwise."""
    boxes = dict(
        boxes if boxes is not None else {"a": (0.0, 0.0, 20.0, 20.0), "b": (80.0, 0.0, 100.0, 20.0)}
    )
    names = list(boxes)
    boxes[BBOX_NAME] = picture
    return FigureResult(
        path=Path("fig.tex"),
        boxes=boxes,
        edges=list(edges),
        declared=names if declared is None else declared,
        input_width=picture[2] - picture[0],
    )


def _advise(figure=None, layout="pipeline", rows=ROWS, unmeasurable="", source=""):
    return _advisory.advise(figure or _figure(), source, layout, rows, unmeasurable)


def _by_rule(reports):
    return {report.rule: report for report in reports}


class TestTheRulesAreAdvisory:
    @pytest.mark.parametrize("rule", ADVISORY)
    def test_registered_figure_or_element_advisory_and_not_allowable(self, rule):
        assert RULES[rule].cls == "advisory"
        assert RULES[rule].allowable is False

    def test_squash_names_a_pair_and_the_rest_the_figure(self):
        assert [RULES[rule].scope for rule in ADVISORY] == [
            "figure",
            "figure",
            "element",
            "figure",
            "figure",
        ]


class TestBesideTheReference:
    def test_each_report_carries_the_layouts_range(self):
        figure = _figure(edges=[("a", "b")], declared=["a", "b", "c"])

        reports = _by_rule(_advise(figure)[0])

        assert reports["size-height"].measurement == (
            "0.10 of the text height (70pt); pipeline reference 0.10 to 0.35"
        )
        assert reports["size-slack"].measurement == "0.94; pipeline reference 0.55 to 0.71"
        assert reports["budget-nodes"].measurement == "3 nodes; pipeline reference 5 to 11"
        assert reports["budget-edges"].measurement == "1 edge; pipeline reference 3 to 4"

    def test_a_reference_of_one_row_is_one_number(self):
        reports = _by_rule(_advise(rows=ROWS[:1])[0])

        assert reports["budget-edges"].measurement == "0 edges; pipeline reference 3"

    def test_a_figure_far_outside_the_range_is_described_not_judged(self):
        """VI.3: a forty-cell DP trace is not over budget. No word of
        the report says over, under, too or exceeds."""
        figure = _figure(declared=[f"n{i}" for i in range(40)])

        text = " ".join(report.measurement for report in _advise(figure)[0])

        assert "40 nodes; pipeline reference 5 to 11" in text
        for verdict in ("over", "under", "too", "exceed", "outside", "budget"):
            assert verdict not in text

    def test_no_layout_declared_prints_bare_numbers_and_says_so(self):
        reports = _by_rule(_advise(layout="", rows=None)[0])

        assert reports["budget-nodes"].measurement == (
            "2 nodes; no layout declared (`% cg-layout:` or --layout)"
        )

    def test_a_layout_with_no_reference_file_says_so(self):
        reports = _by_rule(_advise(layout="quadrant", rows=None)[0])

        assert reports["size-slack"].measurement.endswith(
            "; layout `quadrant` has no reference file"
        )

    def test_a_reference_file_with_no_rows_says_so(self):
        reports = _by_rule(_advise(rows=[])[0])

        assert reports["size-height"].measurement.endswith(
            "; the `pipeline` reference file has no measured rows"
        )

    def test_the_reports_come_in_registry_order(self):
        boxes = {"a": (0.0, 0.0, 20.0, 20.0), "b": (22.0, 0.0, 40.0, 20.0)}

        reports, _ = _advise(_figure(boxes=boxes, edges=[("a", "b")]))

        assert [report.rule for report in reports] == ADVISORY


class TestSlack:
    def test_a_zone_card_is_not_filled_area(self):
        boxes = {
            "zone": (0.0, 0.0, 100.0, 70.0),
            "a": (10.0, 10.0, 30.0, 30.0),
            "b": (50.0, 10.0, 70.0, 30.0),
        }

        reports = _by_rule(_advise(_figure(boxes=boxes, picture=(0.0, 0.0, 100.0, 70.0)))[0])

        assert reports["size-slack"].measurement.startswith(f"{1 - 800 / 7000:.2f};")

    def test_a_figure_with_no_nodes_has_no_slack(self):
        reports, not_measured = _advise(_figure(boxes={}, declared=[]))

        assert "size-slack" not in _by_rule(reports)
        assert ("size-slack", "the figure names no node") in not_measured

    def test_a_picture_with_no_area_has_no_height_share_either(self):
        reports, not_measured = _advise(_figure(picture=(0.0, 0.0, 0.0, 0.0)))

        assert {"size-height", "size-slack"}.isdisjoint(_by_rule(reports))
        assert ("size-height", _advisory.NO_AREA) in not_measured
        assert ("size-slack", _advisory.NO_AREA) in not_measured


class TestSquash:
    def _squash(self, boxes, edges):
        reports, not_measured = _advise(_figure(boxes=boxes, edges=edges))
        return [r for r in reports if r.rule == "size-squash"], not_measured

    def test_two_joined_nodes_under_3mm_apart_squash(self):
        boxes = {"a": (0.0, 0.0, 20.0, 20.0), "b": (25.0, 0.0, 45.0, 20.0)}

        found, _ = self._squash(boxes, [("b", "a")])

        assert [(r.target, r.measurement) for r in found] == [
            ("a+b", "1.8mm apart edge to edge, under 3mm")
        ]

    def test_3mm_apart_does_not(self):
        boxes = {"a": (0.0, 0.0, 20.0, 20.0), "b": (20.0 + _advisory.SQUASH_PT, 0.0, 60.0, 20.0)}

        assert self._squash(boxes, [("a", "b")])[0] == []

    def test_close_nodes_with_no_edge_between_them_do_not(self):
        """A dense grid of cells is a layout, not a short arrow."""
        boxes = {"a": (0.0, 0.0, 20.0, 20.0), "b": (21.0, 0.0, 41.0, 20.0)}

        assert self._squash(boxes, [])[0] == []

    def test_an_anchor_or_a_leading_option_still_names_the_node(self):
        boxes = {"a": (0.0, 0.0, 20.0, 20.0), "b": (25.0, 0.0, 45.0, 20.0)}

        found, not_measured = self._squash(boxes, [("a.east", "[xshift=2mm]b.west")])

        assert [r.target for r in found] == ["a+b"]
        assert not_measured == []

    def test_a_pair_drawn_twice_is_reported_once(self):
        boxes = {"a": (0.0, 0.0, 20.0, 20.0), "b": (25.0, 0.0, 45.0, 20.0)}

        found, _ = self._squash(boxes, [("a", "b"), ("b.south", "a.south")])

        assert len(found) == 1

    @pytest.mark.parametrize(
        ("boxes", "edge"),
        [
            ({"a": (0.0, 0.0, 20.0, 20.0)}, ("a.east", "a")),
            ({"a": (0.0, 0.0, 20.0, 20.0), "p": (22.0, 5.0, 22.0, 5.0)}, ("a", "p")),
            ({"zone": (0.0, 0.0, 90.0, 60.0), "a": (5.0, 5.0, 20.0, 20.0)}, ("zone", "a")),
            ({"a": (0.0, 0.0, 20.0, 20.0), "b": (10.0, 10.0, 30.0, 30.0)}, ("a", "b")),
        ],
        ids=["self-edge", "coordinate", "zone-and-child", "overlapping"],
    )
    def test_what_has_no_arrow_to_read_does_not(self, boxes, edge):
        assert self._squash(boxes, [edge])[0] == []

    def test_an_edge_to_no_measured_node_is_listed_not_skipped(self):
        found, not_measured = self._squash(None, [("a", "b"), ("chan -| a.west", "b")])

        assert found == []
        assert not_measured == [
            ("size-squash", "1 edge ends at no measured node: chan -| a.west -> b")
        ]

    def test_a_name_the_probe_did_not_measure_is_listed(self):
        found, not_measured = self._squash(None, [("a", "ghost.west"), ("ghost", "b")])

        assert found == []
        assert not_measured == [
            ("size-squash", "2 edges end at no measured node: a -> ghost.west, ghost -> b")
        ]

    @pytest.mark.parametrize("token", ["b.north |- a", "a -| b.west", "$(a)!0.5!(b)$"])
    def test_a_point_built_from_two_nodes_is_not_one_of_them(self, token):
        """`(b.north |- a)` is at `a`'s height under `b`: it is neither
        node, so measuring it as `b` would be a guess (#1057 review)."""
        boxes = {"a": (0.0, 0.0, 20.0, 20.0), "b": (25.0, 0.0, 45.0, 20.0)}

        found, not_measured = self._squash(boxes, [("a", token)])

        assert found == []
        assert [rule for rule, _ in not_measured] == ["size-squash"]

    def test_a_named_label_on_a_path_is_not_an_end_of_it(self):
        """`edge_list` pairs consecutive tokens, so a named mid-path label
        reads as two edges, `a -> l` and `l -> b`. Neither is an arrow;
        the path is listed, not guessed at (#1057 review)."""
        boxes = {
            "a": (0.0, 0.0, 20.0, 20.0),
            "l": (22.0, 22.0, 30.0, 30.0),
            "b": (46.0, 0.0, 66.0, 20.0),
        }
        source = "\\draw[->] (a) -- node[midway, above] (l) {x} (b);\n"
        reports, not_measured = _advise(
            _figure(boxes=boxes, edges=[("a", "l"), ("l", "b")]), source=source
        )

        assert "size-squash" not in [r.rule for r in reports]
        assert not_measured == [
            (
                "size-squash",
                "2 edges sit on a path with `edge` or a named node, "
                "so what it joins is not read: a -> l, l -> b",
            )
        ]

    def test_an_edge_chain_is_not_read_as_spoke_to_spoke(self):
        boxes = {
            "hub": (0.0, 0.0, 20.0, 20.0),
            "s1": (60.0, 0.0, 80.0, 20.0),
            "s2": (82.0, 0.0, 102.0, 20.0),
        }
        source = "\\draw (hub) edge (s1) edge (s2);\n"

        reports, not_measured = _advise(
            _figure(boxes=boxes, edges=[("hub", "s1"), ("s1", "s2")]), source=source
        )

        assert "size-squash" not in [r.rule for r in reports]
        assert not_measured[0][1].startswith("2 edges sit on a path with `edge`")

    def test_a_plain_path_beside_an_unreadable_one_is_still_measured(self):
        boxes = {"a": (0.0, 0.0, 20.0, 20.0), "b": (25.0, 0.0, 45.0, 20.0)}
        source = "\\draw (a) -- (b);\n\\draw (b) edge (a);\n"

        reports, _ = _advise(_figure(boxes=boxes, edges=[("a", "b"), ("b", "a")]), source=source)

        assert [r.target for r in reports if r.rule == "size-squash"] == ["a+b"]


class TestWhatCannotBeMeasured:
    def test_an_empty_pictures_placeholder_extent_is_no_area(self):
        """TikZ reports an empty picture as (16000,16000,-16000,-16000):
        both sides negative, so their product is positive (#1057 review)."""
        figure = _figure(boxes={}, declared=[], picture=(16000.0, 16000.0, -16000.0, -16000.0))

        reports, not_measured = _advise(figure)

        assert "size-height" not in [r.rule for r in reports]
        assert ("size-height", _advisory.NO_AREA) in not_measured

    def test_no_geometry_leaves_the_counts_only(self):
        figure = FigureResult(path=Path("fig.tex"), declared=["a"], edges=[("a", "b")])

        reports, not_measured = _advise(figure, unmeasurable="the figure does not compile")

        assert [r.rule for r in reports] == ["budget-nodes", "budget-edges"]
        assert not_measured == [
            ("size-height", "the figure does not compile"),
            ("size-slack", "the figure does not compile"),
            ("size-squash", "the figure does not compile"),
        ]

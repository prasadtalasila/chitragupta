"""`chitragupta figure check` (#1053): the rules it evaluates and how an
allow changes what it reports.

Rule evaluation is tested over hand-built `FigureResult`s, so it runs on
every host. The end-to-end cases under `TestAgainstRealLualatex` compile
real fixture figures and self-skip where TeX is missing.
"""

import inspect
import json
import os
from pathlib import Path

import pytest

from chitragupta.figure import __main__ as cli
from chitragupta.figure import _advisory, _check, _check_report, _connector_check
from chitragupta.figure._focal import cgkey_nodes
from chitragupta.render_output import render
from chitragupta.render_output import MissingBinary
from chitragupta.review.figure_layout import BBOX_NAME, Drawn, FigureResult
from tests.conftest import needs_tikz, run_python
from chitragupta.figure._connectors import MM
from tests.figure_drawn_fixtures import drawn, line, node

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "figure" / "check"
ONE_PICTURE = "\\begin{tikzpicture}[cg]\n\\node[cgbox] (a) {A};\n\\end{tikzpicture}%\n"
# Its ASCII twin, so the twin rules (#1056) are quiet unless a test asks.
ONE_TWIN = "+---+\n| A |\n+---+\n"


def _measured(width=300.0, input_width=None, **fields):
    """A compiled figure whose picture is `width` wide, and only as tall
    as its node so nothing protrudes. It drew nothing the connector
    rules could measure, unless `drawn` says otherwise."""
    boxes = {"a": (0.0, 0.0, 10.0, 10.0), BBOX_NAME: (0.0, 0.0, width, 12.0)}
    fields.setdefault("declared", ["a"])
    fields.setdefault("drawn", Drawn())
    return FigureResult(
        path=Path("fig.tex"),
        boxes=boxes,
        input_width=width if input_width is None else input_width,
        **fields,
    )


def _evaluate(source=ONE_PICTURE, figure=None, width_pt=453.0):
    return _check.evaluate(source, figure or _measured(), width_pt)


def _rules(findings):
    return [finding.rule for finding in findings]


class TestDefaultWidth:
    def test_it_is_the_renders_a4_text_width_with_1in_margins(self):
        """453pt is (8.27in - 2in) * 72.27pt/in; pinned to the render's
        own defaults so a change to either is caught here."""
        defaults = inspect.signature(render).parameters
        assert defaults["papersize"].default == "a4"
        assert defaults["margin"].default == "1in"
        assert _check.DEFAULT_WIDTH_PT == pytest.approx((210 / 25.4 - 2) * 72.27, abs=0.5)


class TestSizeWidth:
    def test_a_picture_wider_than_the_target_fires(self):
        findings, _ = _evaluate(figure=_measured(width=475.24))

        [finding] = findings
        assert (finding.rule, finding.target) == ("size-width", "figure")
        assert finding.measurement == "475.2pt wide, target 453.0pt"

    def test_a_picture_within_texs_own_hfuzz_does_not(self):
        findings, _ = _evaluate(figure=_measured(width=453.09))

        assert findings == []

    def test_the_target_is_the_one_asked_for(self):
        findings, _ = _evaluate(figure=_measured(width=400.0), width_pt=345.0)

        assert _rules(findings) == ["size-width"]

    def test_several_pictures_are_measured_as_the_whole_input(self):
        """Panels set side by side are what a reader sees, and the last
        picture's own box is only one panel."""
        source = ONE_PICTURE + "\\hfill\n" + ONE_PICTURE
        findings, _ = _evaluate(source, _measured(width=200.0, input_width=470.0))

        [finding] = findings
        assert finding.measurement == "470.0pt wide (whole input, 2 pictures), target 453.0pt"

    def test_a_file_with_no_picture_is_not_measured(self):
        """`check()` does not compile such a file (the probe has no
        picture to sit in), so every geometry rule is listed instead."""
        figure = FigureResult(path=Path("fig.tex"), skipped=_check.NO_PICTURE)
        findings, not_measured = _evaluate("\\tikz \\node (a) {A};\n", figure)

        assert findings == []
        assert [rule for rule, _ in not_measured] == list(_check.GEOMETRY)
        assert {why for _, why in not_measured} == {_check.NO_PICTURE}

    def test_a_picture_whose_extent_was_not_printed_is_not_measured(self):
        """The last `\\end{tikzpicture}` inside a macro body that never
        runs: the compile succeeds and prints no bounding box."""
        figure = _measured()
        del figure.boxes[BBOX_NAME]

        findings, not_measured = _evaluate(figure=figure)

        assert findings == []
        assert not_measured == [(rule, _check.NO_EXTENT) for rule in _check.GEOMETRY]


class TestSizeStray:
    def test_a_box_wider_than_its_picture_fires(self):
        findings, _ = _evaluate(figure=_measured(width=307.3, input_width=320.4))

        [finding] = findings
        assert finding.rule == "size-stray"
        assert finding.measurement == "13.1pt stray (input 320.4pt, picture 307.3pt)"

    def test_half_a_point_is_rounding_not_stray(self):
        findings, _ = _evaluate(figure=_measured(width=307.3, input_width=307.7))

        assert findings == []

    def test_several_pictures_are_not_measured_for_stray(self):
        source = ONE_PICTURE + ONE_PICTURE
        findings, not_measured = _evaluate(source, _measured(width=200.0, input_width=420.0))

        assert "size-stray" not in _rules(findings)
        assert ("size-stray", "2 tikzpictures; panels and their spacing are not stray") in (
            not_measured
        )


class TestFocalCount:
    @pytest.mark.parametrize(
        ("body", "named"),
        [
            ("\\node[cgkey] (a) {A};\n\\node[cgkey, right=of a] (b) {B};\n", "a, b"),
            ("\\node (a) [cgkey] {A};\n\\node[cgkey] {B};\n", "a, (unnamed)"),
            ("\\draw (0,0) node[cgkey] (a) {A} -- (1,0) node[cgkey] (b) {B};\n", "a, b"),
            ("\\node[label={[red]above:x}, cgkey] (a) {A};\n\\node[cgkey] (b) {B};\n", "a, b"),
            ("\\node at (0,0) [cgkey] (a) {A};\n\\node (b) at (1,0) [cgkey] {B};\n", "a, b"),
            # An accented state is an accent too (#1062).
            ("\\node[cgkeystate] (a) {A};\n\\node[cgkeystate] (b) {B};\n", "a, b"),
            ("\\node[cgkey] (a) {A};\n\\node[cgkeystate] (b) {B};\n", "a, b"),
        ],
    )
    def test_two_accented_nodes_fire(self, body, named):
        findings, _ = _evaluate(f"\\begin{{tikzpicture}}\n{body}\\end{{tikzpicture}}\n")

        [finding] = findings
        assert finding.rule == "focal-count"
        assert finding.measurement == f"2 accented nodes: {named}"

    @pytest.mark.parametrize(
        "body",
        [
            "\\node[cgkey] (a) {A};\n\\node[cgbox] (b) {B};\n",
            "\\node[cgkey] (a) {A};\n% \\node[cgkey] (b) {B};\n",
            "\\node[cgkey] (a) {A};\n\\node[cgkeyish] (b) {B};\n",
            "\\node[cgkey] (a) {A};\n\\node[cgkeystateish] (b) {B};\n",
            "\\node[cgkeystate] (a) {A};\n\\node[my-cgkeystate] (b) {B};\n",
            "\\node[cgbox] (a) {a cgkey in the label};\n\\node[cgkey] (b) {B};\n",
            "\\node[cgkey] at (cgkey) {A};\n\\node (b) [cgbox] {B};\n",
        ],
    )
    def test_one_accented_node_does_not(self, body):
        findings, _ = _evaluate(f"\\begin{{tikzpicture}}\n{body}\\end{{tikzpicture}}\n")

        assert findings == []

    def test_a_declaration_cut_off_before_its_label_is_still_read(self):
        """The scanner runs to the end of the text rather than past it."""
        assert cgkey_nodes("\\node[cgkey] (a)") == ["a"]

    def test_the_house_blocks_own_style_definition_is_not_a_node(self):
        house = (REPO_ROOT / "assets" / "tikz" / "cg-figstyle.tex").read_text(encoding="utf-8")

        findings, _ = _evaluate(house + ONE_PICTURE)

        assert findings == []


class TestExistingFindings:
    def test_each_review_figure_finding_maps_to_its_rule_and_target(self):
        # `drawn=None`: the named boxes `review figure` reads, which is
        # where an overlap comes from when the probe drew nothing.
        figure = _measured(
            overlong=[("a", 17)],
            stranded=["3,2"],
            by_hand=["\\tikz@library@fit@loaded"],
            drawn=None,
        )
        figure.boxes["b"] = (5.0, 5.0, 15.0, 15.0)

        findings, _ = _evaluate(figure=figure)

        assert [(f.rule, f.target, f.measurement) for f in findings] == [
            ("loads-library-by-hand", "figure", "\\tikz@library@fit@loaded"),
            ("node-overlap", "a+b", "boxes intersect"),
            ("node-text-overload", "a", "17 words (over 15)"),
            ("stranded-arrowhead", "(3,2)", "arrowhead lands mid-line"),
        ]

    def test_protrusion_and_an_unnamed_figure_map_to_figure_rules(self):
        figure = _measured(declared=[])
        figure.boxes = {"x": (0.0, 0.0, 10.0, 2.0), BBOX_NAME: (0.0, 0.0, 300.0, 100.0)}
        figure.declared = ["x"]
        protruding, _ = _evaluate(figure=figure)
        unnamed, _ = _evaluate(figure=_measured(declared=[]))

        assert _rules(protruding) == ["content-protrusion"]
        assert _rules(unnamed) == ["nothing-measurable"]

    def test_a_figure_that_does_not_compile_still_gets_its_source_rules(self):
        figure = FigureResult(path=Path("fig.tex"), overlong=[("a", 20)], failed="! Missing }")
        source = "\\begin{tikzpicture}\n\\node[cgkey] (a) {A};\\node[cgkey] (b) {B};\n"

        findings, not_measured = _evaluate(source, figure)

        assert _rules(findings) == ["does-not-compile", "focal-count", "node-text-overload"]
        assert findings[0].measurement == "! Missing }"
        assert ("size-width", "the figure does not compile") in not_measured
        assert ("size-stray", "the figure does not compile") in not_measured


class TestTwinAgreement:
    """#1056: the twin rules ride in `apply()` beside every other rule.
    What they read and compare is tests/test_figure_twin.py's."""

    def test_no_twin_is_a_finding_and_the_comparisons_are_not_measured(self):
        result = _check.apply(Path("figures/flow.tex"), 453.0, _measured(), ONE_PICTURE)

        assert [(f.rule, f.measurement) for f in result.findings] == [
            ("twin-missing", "no flow.txt beside the figure")
        ]
        assert [why for rule, why in result.not_measured if rule.startswith("t")] == ["no twin"] * 3

    def test_a_missing_twin_cannot_be_allowed(self):
        source = "% cg-allow: twin-missing -- the PDF is all anyone reads\n" + ONE_PICTURE

        result = _check.apply(Path("fig.tex"), 453.0, _measured(), source)

        assert _rules(result.findings) == ["twin-missing"]
        assert [bad.problem for bad in result.malformed] == ["cannot be allowed"]

    def test_a_figure_that_does_not_compile_is_still_compared(self):
        figure = FigureResult(path=Path("fig.tex"), failed="! Missing }")

        result = _check.apply(Path("fig.tex"), 453.0, figure, ONE_PICTURE, twin="[ B ]")

        assert _rules(result.findings) == ["does-not-compile", "t1-labels"]

    def test_the_twin_rules_report_in_registry_order(self):
        source = "\\node (a) {(a) A};\\node (b) {(b) B};" + ONE_PICTURE

        result = _check.apply(Path("fig.tex"), 453.0, _measured(), source, twin="(a) A")

        assert _rules(result.findings) == ["t1-labels", "t3-panels"]

    def test_the_twin_beside_the_figure_is_read(self, tmp_path):
        path = tmp_path / "fig.tex"
        path.with_suffix(".txt").write_bytes(b"[ A ]\xff\n")

        assert _check._twin_text(path) == "[ A ]\ufffd\n"
        assert _check._twin_text(tmp_path / "other.tex") is None


class TestAllows:
    def test_an_honoured_allow_moves_its_finding_out_of_the_findings(self):
        source = "% cg-allow: size-width -- five stages compared\n" + ONE_PICTURE
        result = _check.apply(Path("fig.tex"), 453.0, _measured(width=475.0), source, twin=ONE_TWIN)

        assert result.findings == []
        [(allow, measurement)] = result.allowed
        assert allow.reason == "five stages compared"
        assert measurement == "475.0pt wide, target 453.0pt"

    def test_an_allow_for_a_rule_that_no_longer_fires_is_stale(self):
        source = "% cg-allow: size-width -- wide on purpose\n" + ONE_PICTURE
        result = _check.apply(Path("fig.tex"), 453.0, _measured(), source, twin=ONE_TWIN)

        assert result.allowed == []
        [(allow, why)] = result.stale
        assert allow.rule == "size-width" and why == "no longer fires"

    def test_a_second_allow_for_the_same_rule_sees_the_same_finding(self):
        source = (
            "% cg-allow: size-width -- one reason\n% cg-allow: size-width -- another\n"
            + ONE_PICTURE
        )
        result = _check.apply(Path("fig.tex"), 453.0, _measured(width=475.0), source, twin=ONE_TWIN)

        assert [measured for _, measured in result.allowed] == [
            "475.0pt wide, target 453.0pt",
            "475.0pt wide, target 453.0pt",
        ]

    def test_an_element_allow_sets_aside_its_own_target_only(self):
        source = "% cg-allow: node-overlap b+a -- on purpose\n" + ONE_PICTURE
        figure = _measured(drawn=None)
        figure.boxes["b"] = (5.0, 5.0, 15.0, 15.0)
        figure.boxes["c"] = (8.0, 8.0, 18.0, 18.0)

        result = _check.apply(Path("fig.tex"), 453.0, figure, source, twin=ONE_TWIN)

        assert [f.target for f in result.findings] == ["a+c", "b+c"]
        assert [(allow.target, measured) for allow, measured in result.allowed] == [
            ("b+a", "boxes intersect")
        ]

    def test_an_allow_naming_a_node_that_is_not_drawn_is_stale(self):
        source = "% cg-allow: c1-orthogonal twin->decide -- a loop\n" + ONE_PICTURE
        figure = _measured(drawn=drawn([node("a", (0, 0, 10, 10))], []))

        result = _check.apply(Path("fig.tex"), 453.0, figure, source, twin=ONE_TWIN)

        assert [why for _, why in result.stale] == ["no node named twin"]

    def test_an_allow_for_a_rule_that_could_not_run_is_unchecked(self):
        source = "% cg-allow: k2-text a -- pale on purpose\n" + ONE_PICTURE
        figure = FigureResult(path=Path("fig.tex"), failed="! Missing }")

        result = _check.apply(Path("fig.tex"), 453.0, figure, source, twin=ONE_TWIN)

        assert [why for _, why in result.unchecked] == ["the figure does not compile"]
        assert result.stale == []

    def test_a_malformed_allow_honours_nothing(self):
        source = "% cg-allow: size-width\n" + ONE_PICTURE
        result = _check.apply(Path("fig.tex"), 453.0, _measured(width=475.0), source, twin=ONE_TWIN)

        assert _rules(result.findings) == ["size-width"]
        assert [bad.problem for bad in result.malformed] == ["no reason"]


@needs_tikz
class TestAgainstRealLualatex:
    """The fixtures under tests/fixtures/figure/check/, a firing and a
    clean one per rule, compiled for real."""

    @pytest.mark.parametrize(
        ("fixture", "rule"),
        [("wide", "size-width"), ("stray", "size-stray"), ("two-keys", "focal-count")],
    )
    def test_the_firing_fixture_fires(self, fixture, rule):
        result = _check.check(FIXTURES / f"{fixture}.tex", _check.DEFAULT_WIDTH_PT)

        assert _rules(result.findings) == [rule]

    @pytest.mark.parametrize("fixture", ["narrow", "tight", "one-key", "two-pictures"])
    def test_the_clean_fixture_is_clean(self, fixture):
        result = _check.check(FIXTURES / f"{fixture}.tex", _check.DEFAULT_WIDTH_PT)

        assert result.findings == []

    def test_a_file_with_no_picture_environment_is_not_a_compile_failure(self, tmp_path):
        path = tmp_path / "fig.tex"
        path.write_text("\\tikz \\draw (0,0) -- (1,1);%\n", encoding="utf-8")
        path.with_suffix(".txt").write_text("o-------o\n", encoding="utf-8")

        result = _check.check(path, _check.DEFAULT_WIDTH_PT)

        assert result.findings == []
        assert [rule for rule, _ in result.not_measured] == [
            *_check.GEOMETRY,
            *_advisory.GEOMETRY,
        ]

    def test_a_picture_only_inside_a_macro_body_does_not_crash(self, tmp_path):
        path = tmp_path / "fig.tex"
        path.write_text(
            "\\newcommand{\\cgcheckicon}{\\begin{tikzpicture}\\node (i) {i};"
            "\\end{tikzpicture}}%\n\\tikz \\node[draw] (a) {A};%\n",
            encoding="utf-8",
        )

        result = _check.check(path, _check.DEFAULT_WIDTH_PT)

        assert ("size-width", _check.NO_EXTENT) in result.not_measured

    def test_a_figure_without_its_twin_is_reported(self, tmp_path):
        path = tmp_path / "fig.tex"
        path.write_text((FIXTURES / "narrow.tex").read_text(encoding="utf-8"), encoding="utf-8")

        result = _check.check(path, _check.DEFAULT_WIDTH_PT)

        assert _rules(result.findings) == ["twin-missing"]
        assert result.findings[0].measurement == "no fig.txt beside the figure"

    def test_a_twin_that_disagrees_is_reported(self, tmp_path):
        path = tmp_path / "fig.tex"
        path.write_text((FIXTURES / "narrow.tex").read_text(encoding="utf-8"), encoding="utf-8")
        path.with_suffix(".txt").write_text("[ Left ] --> [ Rite ]\n", encoding="utf-8")

        result = _check.check(path, _check.DEFAULT_WIDTH_PT)

        assert [(f.rule, f.target) for f in result.findings] == [("t1-labels", "right")]

    def test_two_pictures_say_why_stray_was_not_measured(self):
        result = _check.check(FIXTURES / "two-pictures.tex", _check.DEFAULT_WIDTH_PT)

        assert [rule for rule, _ in result.not_measured] == [
            "size-stray",
            *_check.CONNECTOR,
            *_check.CONTRAST,
            *_advisory.GEOMETRY,
        ]
        assert _rules(result.advisory) == ["budget-nodes", "budget-edges"]

    def test_an_allowed_overflow_is_listed_not_found(self):
        result = _check.check(FIXTURES / "allowed-wide.tex", _check.DEFAULT_WIDTH_PT)

        assert result.findings == []
        assert [allow.rule for allow, _ in result.allowed] == ["size-width"]

    def test_an_allowed_overlap_is_set_aside_for_its_pair_only(self):
        result = _check.check(FIXTURES / "allowed-overlap.tex", _check.DEFAULT_WIDTH_PT)

        assert [(f.rule, f.target) for f in result.findings] == [("node-overlap", "note+pot")]
        assert [allow.target for allow, _ in result.allowed] == ["pot+legend"]
        assert result.stale == [] and result.unchecked == []

    def test_an_allow_for_a_node_that_is_gone_is_stale(self):
        result = _check.check(FIXTURES / "stale-overlap.tex", _check.DEFAULT_WIDTH_PT)

        assert result.findings == [] and result.allowed == []
        assert [why for _, why in result.stale] == ["no node named legend"]

    def test_a_wide_exemplar_overflows_a_narrower_target(self):
        """`rag-stages` fits the render's 453pt since #1050 (411.5pt) but
        not the article class's 345pt, so a real house figure still pins
        the firing case at a narrower target, as `--width 345` asks for."""
        path = REPO_ROOT / "assets" / "tikz" / "exemplars" / "rag-stages.tex"

        result = _check.check(path, 345.0)

        assert "size-width" in _rules(result.findings)

    @pytest.mark.parametrize(
        "name",
        [
            "pipeline",
            "zoned-spine",
            "branching-tree",
            "hub-and-spoke-network",
            "map",
            "control-loop",
            "layered-stack",
            "state-machine",
            "comparison",
            "sequence",
        ],
    )
    def test_every_scaffold_compiles_boxed_with_one_focal_node_and_no_stray(self, name):
        result = _check.check(
            REPO_ROOT / "assets" / "tikz" / f"{name}.tex", _check.DEFAULT_WIDTH_PT
        )

        assert not {
            "does-not-compile",
            "focal-count",
            "size-stray",
            "size-width",
            # The bench left control-loop's `output` tag 0.6mm from its
            # bend; a scaffold is copied, so it starts a figure clean.
            "c2-tag-clearance",
        } & set(_rules(result.findings))


def _result(**fields):
    """A `CheckResult` over the 300pt `_measured()` figure."""
    source = fields.pop("source", ONE_PICTURE)
    figure = fields.pop("figure", _measured())
    twin = fields.pop("twin", ONE_TWIN)
    return _check.apply(Path("figures/flow.tex"), 453.0, figure, source, twin=twin)


class TestTextReport:
    def test_a_clean_figure_says_it_is_not_a_verdict(self):
        report = _check_report.format_text(_result())

        assert report.splitlines()[0] == str(Path("figures/flow.tex"))
        assert "No findings. This is not a verdict on the figure." in report
        assert report.splitlines()[-1].startswith("figure check: 0 findings, 0 allowed")

    def test_one_line_per_finding_names_rule_target_and_measurement(self):
        figure = _measured(width=475.0, overlong=[("a", 17)])

        lines = _check_report.format_text(_result(figure=figure)).splitlines()

        assert lines[1].split() == ["size-width", "figure", "475.0pt", "wide,", "target", "453.0pt"]
        assert lines[2].split()[:3] == ["node-text-overload", "a", "17"]
        assert "No findings" not in "\n".join(lines)
        assert lines[-1].startswith("figure check: 2 findings, ")

    def test_one_finding_is_counted_in_the_singular(self):
        report = _check_report.format_text(_result(figure=_measured(width=475.0)))

        assert report.splitlines()[-1].startswith("figure check: 1 finding, ")

    def test_every_allow_outcome_has_its_own_section(self):
        source = (
            "% cg-allow: size-width -- compared at full width\n"
            "% cg-allow: focal-count -- two keys on purpose\n"
            '% cg-allow: k2-text "tag on a->b" -- greyed on purpose\n'
            "% cg-allow: size-width\n" + ONE_PICTURE + ONE_PICTURE
        )
        figure = _measured(width=200.0, input_width=475.0)

        report = _check_report.format_text(_result(source=source, figure=figure))

        assert "\nallowed\n" in report
        assert (
            "pt wide (whole input, 2 pictures), target 453.0pt -- compared at full width (line 1)"
            in report
        )
        assert "\nstale allows\n" in report
        assert "no longer fires -- two keys on purpose (line 2)" in report
        assert "\nunchecked allows\n" in report
        assert '"tag on a->b"' in report and "-- greyed on purpose (line 3)" in report
        assert "\nmalformed allows\n  line 4: % cg-allow: size-width  (no reason)" in report
        assert report.splitlines()[-1] == (
            "figure check: 0 findings, 1 allowed, 1 stale, 1 unchecked, 1 malformed"
        )

    def test_a_target_with_a_space_is_printed_as_an_allow_must_write_it(self):
        assert _check_report._quoted("tag on a->b") == '"tag on a->b"'
        assert _check_report._quoted('"Raw PDF"') == '"Raw PDF"'
        assert _check_report._quoted("a+b") == "a+b"

    def test_what_was_not_measured_and_the_diagnostics_are_kept_apart(self):
        source = ONE_PICTURE + ONE_PICTURE
        figure = _measured(width=200.0, input_width=420.0, edges=[("a", "b")])

        report = _check_report.format_text(_result(source=source, figure=figure))

        assert "\nnot measured\n  size-stray: 2 tikzpictures" in report
        assert "\ndiagnostics (not findings)\n" in report
        assert "edges (confirm against the prose): a -> b" in report
        assert "advisory, human-read only -- nothing consumes this" in report

    def test_a_figure_that_does_not_compile_reports_no_geometry_at_all(self):
        figure = FigureResult(path=Path("fig.tex"), failed="! Missing }")

        report = _check_report.format_text(_result(figure=figure))

        assert "does-not-compile" in report and "! Missing }" in report
        assert "\nnot measured\n  nothing-measurable: the figure does not compile" in report
        assert "empty" not in report

    def test_declared_names_that_were_not_measured_are_a_diagnostic(self):
        figure = _measured(declared=["a", "ghost"])

        report = _check_report.format_text(_result(figure=figure))

        assert "declared but not measured: ghost" in report


class TestJsonPayload:
    def test_it_carries_the_same_content_as_the_text(self):
        source = (
            "% cg-allow: size-width -- compared at full width\n"
            "% cg-allow: node-overlap a+b -- on purpose\n"
            "% cg-allow: nope -- typo\n" + ONE_PICTURE + ONE_PICTURE
        )
        figure = _measured(width=200.0, input_width=470.0, overlong=[("a", 17)])

        body = _check_report.payload(_result(source=source, figure=figure))

        assert body["figure"] == str(Path("figures/flow.tex")) and body["width_pt"] == 453.0
        assert body["findings"] == [
            {
                "rule": "node-text-overload",
                "class": "objective",
                "scope": "element",
                "target": "a",
                "measurement": "17 words (over 15)",
            }
        ]
        assert body["allowed"] == [
            {
                "rule": "size-width",
                "target": "",
                "reason": "compared at full width",
                "line": 1,
                "measurement": "470.0pt wide (whole input, 2 pictures), target 453.0pt",
            }
        ]
        assert body["stale"] == [
            {
                "rule": "node-overlap",
                "target": "a+b",
                "reason": "on purpose",
                "line": 2,
                "why": "no node named b",
            }
        ]
        assert body["unchecked"] == []
        assert body["malformed"] == [
            {"line": 3, "text": "% cg-allow: nope -- typo", "problem": "unknown rule `nope`"}
        ]
        assert body["not_measured"][0]["rule"] == "size-stray"
        assert body["diagnostics"]["empty_fraction_note"].startswith("advisory")
        assert set(body["diagnostics"]) == {
            "edges",
            "empty_fraction",
            "empty_fraction_note",
            "names_unmeasured",
            "lines_not_between_nodes",
        }


class TestCli:
    def test_a_missing_file_is_a_usage_error(self, tmp_path, capsys):
        assert cli.main(["check", str(tmp_path / "absent.tex")]) == 2
        assert "not a readable" in capsys.readouterr().err

    def test_a_host_without_lualatex_checks_nothing_and_exits_2(
        self, tmp_path, monkeypatch, capsys
    ):
        path = tmp_path / "fig.tex"
        path.write_text(ONE_PICTURE, encoding="utf-8")

        def _missing(binary):
            raise MissingBinary(f"'{binary}' is not on PATH.")

        monkeypatch.setattr(cli, "_require", _missing)

        assert cli.main(["check", str(path)]) == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "lualatex" in captured.err and "chitragupta doctor" in captured.err

    @pytest.mark.parametrize(
        "content", [b"\\node (a) {caf\xe9};\n", b"\\begin{tikzpicture}\\end{tikzpicture}\n"]
    )
    def test_a_file_that_cannot_be_read_as_utf8_is_a_usage_error(self, tmp_path, capsys, content):
        path = tmp_path / "fig.tex"
        path.write_bytes(content)
        if b"caf" not in content:
            path.chmod(0)
            if os.access(path, os.R_OK):  # root, or Windows, still reads it
                pytest.skip("this user can read a mode-000 file")

        assert cli.main(["check", str(path)]) == 2
        assert "not a readable" in capsys.readouterr().err

    def test_a_directory_is_a_usage_error(self, tmp_path, capsys):
        assert cli.main(["check", str(tmp_path)]) == 2
        assert "not a readable" in capsys.readouterr().err

    def test_a_positive_width_is_taken_in_points(self):
        assert cli.build_parser().parse_args(["check", "f.tex", "--width", "345.5"]).width == 345.5

    @pytest.mark.parametrize("width", ["0", "-3", "wide", "nan", "inf"])
    def test_a_width_that_is_not_a_positive_number_is_a_usage_error(self, tmp_path, width):
        with pytest.raises(SystemExit) as exit_info:
            cli.main(["check", str(tmp_path / "fig.tex"), "--width", width])

        assert exit_info.value.code == 2

    @needs_tikz
    def test_it_exits_0_whatever_it_finds(self, capsys):
        assert cli.main(["check", str(FIXTURES / "wide.tex")]) == 0
        assert "size-width" in capsys.readouterr().out

    @needs_tikz
    def test_json_and_a_narrower_target_are_honoured(self, capsys):
        assert cli.main(["check", str(FIXTURES / "narrow.tex"), "--width", "100", "--json"]) == 0
        body = json.loads(capsys.readouterr().out)
        assert body["width_pt"] == 100.0
        assert [finding["rule"] for finding in body["findings"]] == ["size-width"]

    @needs_tikz
    def test_the_front_door_reaches_it(self):
        result = run_python(
            "-m", "chitragupta", "figure", "check", str(FIXTURES / "tight.tex"), check=False
        )

        assert result.returncode == 0, result.stderr
        assert "No findings" in result.stdout


class TestAdvisorySizeReports:
    """#1057: the size reports ride beside the findings, never in them."""

    def test_the_figures_own_layout_line_picks_the_reference(self):
        result = _result(source="% cg-layout: pipeline\n" + ONE_PICTURE)

        assert result.layout == "pipeline"
        assert "pipeline reference" in result.advisory[-1].measurement

    def test_the_caller_can_name_the_layout_instead(self):
        source = "% cg-layout: pipeline\n" + ONE_PICTURE

        result = _check.apply(Path("fig.tex"), 453.0, _measured(), source, "control-loop", ONE_TWIN)

        assert result.layout == "control-loop"
        assert "control-loop reference" in result.advisory[-1].measurement

    def test_no_layout_still_reports_the_numbers(self):
        result = _result()

        assert result.layout == ""
        assert _rules(result.advisory) == [
            "size-height",
            "size-slack",
            "budget-nodes",
            "budget-edges",
        ]
        assert result.findings == []

    def test_an_advisory_rule_cannot_be_allowed(self):
        result = _result(source="% cg-allow: size-slack -- roomy on purpose\n" + ONE_PICTURE)

        assert [(bad.problem) for bad in result.malformed] == ["cannot be allowed"]
        assert "size-slack" in _rules(result.advisory)


class TestAdvisoryReport:
    def test_the_text_has_its_own_section_and_still_says_no_findings(self):
        report = _check_report.format_text(_result(source="% cg-layout: pipeline\n" + ONE_PICTURE))

        assert "\nadvisory (read; never resolved, allowed or capped)\n  size-height" in report
        assert "budget-nodes          figure     1 node; pipeline reference" in report
        assert "No findings. This is not a verdict on the figure." in report

    def test_json_carries_the_layout_and_the_advisory_reports(self):
        body = _check_report.payload(_result(source="% cg-layout: pipeline\n" + ONE_PICTURE))

        assert body["layout"] == "pipeline"
        assert body["findings"] == []
        assert body["advisory"][0] == {
            "rule": "size-height",
            "class": "advisory",
            "scope": "figure",
            "target": "figure",
            "measurement": body["advisory"][0]["measurement"],
        }
        assert [entry["rule"] for entry in body["advisory"]] == [
            "size-height",
            "size-slack",
            "budget-nodes",
            "budget-edges",
        ]

    def test_json_says_null_for_no_layout(self):
        assert _check_report.payload(_result())["layout"] is None


class TestLayoutFlag:
    def test_a_layout_with_a_reference_file_is_taken(self):
        args = cli.build_parser().parse_args(["check", "f.tex", "--layout", "pipeline"])

        assert args.layout == "pipeline"

    def test_the_default_is_the_figures_own_line(self):
        assert cli.build_parser().parse_args(["check", "f.tex"]).layout == ""

    def test_a_layout_with_no_reference_file_is_a_usage_error(self, tmp_path):
        with pytest.raises(SystemExit) as exit_info:
            cli.main(["check", str(tmp_path / "fig.tex"), "--layout", "no-such-layout"])

        assert exit_info.value.code == 2

    @needs_tikz
    def test_it_reaches_the_report(self, capsys):
        assert cli.main(["check", str(FIXTURES / "tight.tex"), "--layout", "map"]) == 0
        assert "map reference" in capsys.readouterr().out


@needs_tikz
class TestAdvisoryAgainstRealLualatex:
    @pytest.mark.parametrize(
        "name",
        [
            "pipeline",
            "zoned-spine",
            "branching-tree",
            "hub-and-spoke-network",
            "map",
            "control-loop",
            "layered-stack",
            "state-machine",
            "comparison",
            "sequence",
        ],
    )
    def test_every_scaffold_reads_its_own_reference_and_squashes_nothing(self, name):
        result = _check.check(
            REPO_ROOT / "assets" / "tikz" / f"{name}.tex", _check.DEFAULT_WIDTH_PT
        )

        assert result.layout == name
        assert "size-squash" not in _rules(result.advisory)
        assert all(f"{name} reference" in r.measurement for r in result.advisory)

    def test_a_short_arrow_squashes(self):
        result = _check.check(FIXTURES / "squash.tex", _check.DEFAULT_WIDTH_PT)

        squashed = [r for r in result.advisory if r.rule == "size-squash"]
        assert [r.target for r in squashed] == ["a+b"]
        assert result.findings == []


A = node("a", (0, 0, 40, 20))
HIGH_B = node("b", (100, 60, 140, 80))


class TestConnectorRules:
    """#1054: the connector rules run over what the probe drew, and say
    why wherever they could not."""

    def test_they_report_from_the_drawn_lines(self):
        figure = _measured(drawn=drawn([A, HIGH_B], [line((40, 10), (100, 70))]))

        findings, _ = _evaluate(figure=figure)

        assert "c1-orthogonal" in _rules(findings)

    def test_a_declared_layout_exempts_its_rules(self):
        figure = _measured(drawn=drawn([A, HIGH_B], [line((40, 10), (100, 70))]))

        findings, _ = _evaluate("% cg-layout: hub-and-spoke-network\n" + ONE_PICTURE, figure)

        assert "c1-orthogonal" not in _rules(findings)

    def test_they_are_not_measured_without_drawn_lines(self):
        _, not_measured = _evaluate(figure=_measured(drawn=None))

        assert [(rule, why) for rule, why in not_measured] == [
            (rule, _connector_check.NO_DRAWN) for rule in (*_check.CONNECTOR, *_check.CONTRAST)
        ]

    def test_they_are_not_measured_for_several_pictures(self):
        """Nodes from an earlier picture are not in the last one's frame."""
        _, not_measured = _evaluate(ONE_PICTURE + ONE_PICTURE, _measured(input_width=320.0))

        assert ("c5-transit", "2 tikzpictures; their nodes are not in one frame") in not_measured

    def test_they_are_not_measured_under_transform_canvas(self):
        source = ONE_PICTURE.replace("[cg]", "[cg,transform canvas={scale=0.8}]")

        _, not_measured = _evaluate(source)

        assert ("c1-orthogonal", _connector_check.CANVAS) in not_measured

    def test_a_round_node_is_listed_as_not_measured_for_c4(self):
        circle = node("b", (100, 0, 140, 20), shape="circle")
        figure = _measured(drawn=drawn([A, circle], [line((40, 10), (100, 10))]))

        _, not_measured = _evaluate(figure=figure)

        assert not_measured == [("c4-attach", "round nodes, which have no sides: b")]

    def test_every_connector_rule_is_a_geometry_rule(self):
        assert set(_check.CONNECTOR) <= set(_check.GEOMETRY)

    def test_k1_and_k2_are_geometry_rules(self):
        """A figure that does not compile has no colours to read (#1055)."""
        assert set(_check.CONTRAST) <= set(_check.GEOMETRY)

    def test_the_report_counts_the_lines_not_between_nodes(self):
        axis = line((0, -10), (200, -10))
        figure = _measured(drawn=drawn([A], [axis]))
        result = _result(figure=figure)

        report = _check_report.format_text(result)
        body = _check_report.payload(result)

        assert "lines not between two nodes, not checked by c1 to c7: 1" in report
        assert body["diagnostics"]["lines_not_between_nodes"] == 1

    def test_no_drawn_figure_has_no_line_count(self):
        result = _result(figure=_measured(drawn=None))

        assert "lines not between" not in _check_report.format_text(result)
        assert _check_report.payload(result)["diagnostics"]["lines_not_between_nodes"] is None


@needs_tikz
class TestConnectorRulesAgainstRealLualatex:
    def test_the_dangling_fixture_fires_c7_and_c2(self):
        """`paper-twin-loop.tex`'s defects, cut down: an arrow stopping
        beside the box it points at, and a tag set on its line."""
        result = _check.check(FIXTURES / "dangling.tex", _check.DEFAULT_WIDTH_PT)

        rules = _rules(result.findings)
        assert "c7-dangling-tip" in rules and "c2-tag-clearance" in rules

    def test_lifelines_fire_no_connector_rule_in_a_sequence(self):
        """Many messages meeting one lifeline, and one skipping a lifeline,
        are a sequence's grammar (#1063). The same figure read as a
        pipeline fires both, so the exemption is what holds it clean."""
        path = FIXTURES / "lifelines.tex"

        assert not set(_check.CONNECTOR) & set(_rules(_check.check(path, 453.0).findings))
        as_pipeline = _rules(_check.check(path, 453.0, "pipeline").findings)
        assert {"c4-attach", "c5-transit"} <= set(as_pipeline)

    def test_a_clean_two_node_figure_fires_no_connector_rule(self):
        result = _check.check(FIXTURES / "narrow.tex", _check.DEFAULT_WIDTH_PT)

        assert not set(_check.CONNECTOR) & set(_rules(result.findings))
        assert result.not_measured == []


class TestOverlapOfEveryDrawnNode:
    """`node-overlap` in `figure check` measures every node TikZ drew, not
    only the ones the source names: `architecture.tex`'s zone titles,
    unnamed and drawn by a macro, ran into each other unreported."""

    @staticmethod
    def _overlaps(*nodes, lines=()):
        figure = _measured(drawn=drawn(list(nodes), list(lines)))
        findings, _ = _evaluate(figure=figure)
        return [f.target for f in findings if f.rule == "node-overlap"]

    def test_two_unnamed_titles_that_collide_are_reported_by_position(self):
        first = node("cgu-1", (0, 0, 100, 14), text_box=(2, 2, 98, 12))
        second = node("cgu-2", (80, 0, 140, 14), text_box=(82, 2, 138, 12))

        assert self._overlaps(first, second) == [
            f"({50 / MM:.1f},{7 / MM:.1f})+({110 / MM:.1f},{7 / MM:.1f})"
        ]

    def test_a_node_tikz_named_itself_is_reported_by_position(self):
        """A pin is `tikz@f@<n>` inside TikZ, which no source says (#1087)."""
        pin = node("tikz@f@1", (30, 5, 70, 25))

        shown = f"({50 / MM:.1f},{15 / MM:.1f})"

        assert self._overlaps(node("a", (0, 0, 40, 20)), pin) == [f"{shown}+a"]

    def test_a_named_pair_is_reported_by_name(self):
        assert self._overlaps(node("a", (0, 0, 40, 20)), node("b", (30, 5, 70, 25))) == ["a+b"]

    def test_a_tag_on_a_line_is_left_to_c6(self):
        a, b = node("a", (0, 0, 40, 20)), node("b", (100, 0, 140, 20))
        tag = node("cgu-1", (30, 5, 60, 15), text_box=(31, 6, 59, 14))
        on_line = line((40, 10), (100, 10), labels=("cgu-1",))

        assert self._overlaps(a, b, tag, lines=[on_line]) == []

    def test_a_zone_around_its_members_is_not_an_overlap(self):
        zone = node("zone", (-10, -10, 60, 30))

        assert self._overlaps(zone, node("a", (0, 0, 40, 20))) == []

    def test_an_empty_unframed_node_overlaps_nothing(self):
        """A `\\node (p) {};` with no frame is a placeholder, not ink."""
        empty = node("cgu-1", (30, 5, 50, 15), text_box=(40, 10, 40, 10), framed=False)

        assert self._overlaps(node("a", (0, 0, 40, 20)), empty) == []

    def test_a_step_badge_on_a_node_is_not_an_overlap(self):
        """`\\cgstep` sets a 5.8mm disc over a node's corner on purpose
        (`rag-stages.tex`, `architecture.tex`)."""
        badge = node("cgu-1", (-8, 12, 9.3, 29.3), shape="circle", text_box=(-2, 18, 2, 23))

        assert self._overlaps(node("a", (0, 0, 40, 20)), badge) == []

    def test_a_large_circle_over_a_node_is_still_an_overlap(self):
        state = node("s", (30, 5, 70, 45), shape="circle")

        assert self._overlaps(node("a", (0, 0, 40, 20)), state) == ["a+s"]

    def test_without_drawn_lines_the_named_boxes_are_used(self):
        figure = _measured(drawn=None, overlong=[])
        figure.boxes.update({"b": (5.0, 5.0, 15.0, 15.0)})
        figure.boxes["a"] = (0.0, 0.0, 10.0, 10.0)
        figure.declared = ["a", "b"]

        findings, _ = _evaluate(figure=figure)

        assert [f.target for f in findings if f.rule == "node-overlap"] == ["a+b"]


@needs_tikz
def test_colliding_unnamed_titles_are_found_in_a_real_figure(tmp_path):
    path = tmp_path / "fig.tex"
    path.write_text(
        "\\begin{tikzpicture}\n"
        "\\node[draw] (a) at (0,0) {A};\n"
        "\\node at (0,1) {Deterministic -- no model is called};\n"
        "\\node at (2.5,1) {Generative};\n"
        "\\end{tikzpicture}%\n",
        encoding="utf-8",
    )

    result = _check.check(path, _check.DEFAULT_WIDTH_PT)

    assert [f.rule for f in result.findings if f.rule == "node-overlap"] == ["node-overlap"]


@needs_tikz
def test_a_node_tikz_named_itself_is_never_shown_by_that_name(tmp_path):
    """An unnamed node followed by `edge` is `tikz@f@1` inside TikZ. The
    line through `c` is still reported, with that end named by its
    centre (#1087)."""
    path = tmp_path / "fig.tex"
    path.write_text(
        "\\begin{tikzpicture}\n"
        "\\node[draw] (b) at (3,0) {B};\n"
        "\\node[draw] at (0,0) {A} edge[->] (b);\n"
        "\\node[draw] (c) at (1.5,0) {C};\n"
        "\\end{tikzpicture}%\n",
        encoding="utf-8",
    )

    findings = _check.check(path, _check.DEFAULT_WIDTH_PT).findings

    (transit,) = [f for f in findings if f.rule == "c5-transit"]
    assert transit.target.startswith("(") and transit.target.endswith(")->b")
    assert not [f for f in findings if "@" in f.target + f.measurement]

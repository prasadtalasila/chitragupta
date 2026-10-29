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
from chitragupta.figure import _advisory, _check, _check_report
from chitragupta.figure._focal import cgkey_nodes
from chitragupta.render_output import render
from chitragupta.render_output import MissingBinary
from chitragupta.review.figure_layout import BBOX_NAME, FigureResult
from tests.conftest import needs_tikz, run_python

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "figure" / "check"
ONE_PICTURE = "\\begin{tikzpicture}[cg]\n\\node[cgbox] (a) {A};\n\\end{tikzpicture}%\n"


def _measured(width=300.0, input_width=None, **fields):
    """A compiled figure whose picture is `width` wide, and only as tall
    as its node so nothing protrudes."""
    boxes = {"a": (0.0, 0.0, 10.0, 10.0), BBOX_NAME: (0.0, 0.0, width, 12.0)}
    fields.setdefault("declared", ["a"])
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
        ],
    )
    def test_two_accented_nodes_fire(self, body, named):
        findings, _ = _evaluate(f"\\begin{{tikzpicture}}\n{body}\\end{{tikzpicture}}\n")

        [finding] = findings
        assert finding.rule == "focal-count"
        assert finding.measurement == f"2 cgkey nodes: {named}"

    @pytest.mark.parametrize(
        "body",
        [
            "\\node[cgkey] (a) {A};\n\\node[cgbox] (b) {B};\n",
            "\\node[cgkey] (a) {A};\n% \\node[cgkey] (b) {B};\n",
            "\\node[cgkey] (a) {A};\n\\node[cgkeyish] (b) {B};\n",
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
        figure = _measured(
            overlong=[("a", 17)],
            stranded=["3,2"],
            by_hand=["\\tikz@library@fit@loaded"],
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


class TestAllows:
    def test_an_honoured_allow_moves_its_finding_out_of_the_findings(self):
        source = "% cg-allow: size-width -- five stages compared\n" + ONE_PICTURE
        result = _check.apply(Path("fig.tex"), 453.0, _measured(width=475.0), source)

        assert result.findings == []
        [(allow, measurement)] = result.allowed
        assert allow.reason == "five stages compared"
        assert measurement == "475.0pt wide, target 453.0pt"

    def test_an_allow_for_a_rule_that_did_not_fire_is_still_listed(self):
        source = "% cg-allow: size-width -- wide on purpose\n" + ONE_PICTURE
        result = _check.apply(Path("fig.tex"), 453.0, _measured(), source)

        [(allow, measurement)] = result.allowed
        assert allow.rule == "size-width" and measurement is None

    def test_a_second_allow_for_the_same_rule_sees_the_same_finding(self):
        source = (
            "% cg-allow: size-width -- one reason\n% cg-allow: size-width -- another\n"
            + ONE_PICTURE
        )
        result = _check.apply(Path("fig.tex"), 453.0, _measured(width=475.0), source)

        assert [measured for _, measured in result.allowed] == [
            "475.0pt wide, target 453.0pt",
            "475.0pt wide, target 453.0pt",
        ]

    def test_a_deferred_allow_leaves_its_finding_in_place(self):
        source = "% cg-allow: node-overlap a+b -- on purpose\n" + ONE_PICTURE
        figure = _measured()
        figure.boxes["b"] = (5.0, 5.0, 15.0, 15.0)

        result = _check.apply(Path("fig.tex"), 453.0, figure, source)

        assert _rules(result.findings) == ["node-overlap"]
        assert [allow.target for allow in result.deferred] == ["a+b"]

    def test_a_malformed_allow_honours_nothing(self):
        source = "% cg-allow: size-width\n" + ONE_PICTURE
        result = _check.apply(Path("fig.tex"), 453.0, _measured(width=475.0), source)

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

    def test_two_pictures_say_why_stray_was_not_measured(self):
        result = _check.check(FIXTURES / "two-pictures.tex", _check.DEFAULT_WIDTH_PT)

        assert [rule for rule, _ in result.not_measured] == ["size-stray", *_advisory.GEOMETRY]
        assert _rules(result.advisory) == ["budget-nodes", "budget-edges"]

    def test_an_allowed_overflow_is_listed_not_found(self):
        result = _check.check(FIXTURES / "allowed-wide.tex", _check.DEFAULT_WIDTH_PT)

        assert result.findings == []
        assert [allow.rule for allow, _ in result.allowed] == ["size-width"]

    def test_the_wide_exemplar_overflows_the_text_width(self):
        """`rag-stages` is 1.09 of the text width in the render's fonts
        (#1037's measurement; #1050 owns the fix), so a real house
        figure pins the firing case too."""
        path = REPO_ROOT / "assets" / "tikz" / "exemplars" / "rag-stages.tex"

        result = _check.check(path, _check.DEFAULT_WIDTH_PT)

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
        ],
    )
    def test_every_scaffold_compiles_boxed_with_one_focal_node_and_no_stray(self, name):
        result = _check.check(
            REPO_ROOT / "assets" / "tikz" / f"{name}.tex", _check.DEFAULT_WIDTH_PT
        )

        assert not {"does-not-compile", "focal-count", "size-stray", "size-width"} & set(
            _rules(result.findings)
        )


def _result(**fields):
    """A `CheckResult` over the 300pt `_measured()` figure."""
    source = fields.pop("source", ONE_PICTURE)
    figure = fields.pop("figure", _measured())
    return _check.apply(Path("figures/flow.tex"), 453.0, figure, source)


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
            "% cg-allow: node-overlap a+b -- the legend sits on purpose\n"
            "% cg-allow: size-width\n" + ONE_PICTURE
        )

        report = _check_report.format_text(_result(source=source, figure=_measured(width=475.0)))

        assert "\nallowed\n" in report
        assert "475.0pt wide, target 453.0pt -- compared at full width (line 1)" in report
        assert "did not fire -- two keys on purpose (line 2)" in report
        assert "\nnot honoured until #1058\n" in report
        assert "node-overlap" in report and "-- the legend sits on purpose (line 3)" in report
        assert "\nmalformed allows\n  line 4: % cg-allow: size-width  (no reason)" in report
        assert report.splitlines()[-1] == (
            "figure check: 0 findings, 2 allowed, 1 deferred, 1 malformed"
        )

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
        assert body["deferred"] == [
            {"rule": "node-overlap", "target": "a+b", "reason": "on purpose", "line": 2}
        ]
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

        result = _check.apply(Path("fig.tex"), 453.0, _measured(), source, "control-loop")

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

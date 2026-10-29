"""Twin agreement (#1056): what `figure check` reads from a figure's
source to compare against its ASCII twin, and the four rules it reports.

Source only, so nothing here needs TeX. The pairs under
tests/fixtures/figure/twin/ are the rules' both polarities as files.
"""

from pathlib import Path

import pytest

from chitragupta.figure import _twin
from chitragupta.figure._twin import Text

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "figure" / "twin"

BLOCK = (
    "% >>> chitragupta figure style v4 -- copy of assets/tikz/cg-figstyle.tex, do not edit <<<\n"
    "\\providecommand{\\cgzonelabel}[3]{%\n"
    "  \\node[cgzonetitle=#2] at (#1.north west) {#3};}%\n"
    "\\tikzset{cg/.style={}}%\n"
    "% >>> end chitragupta figure style <<<\n"
)


def _picture(body: str) -> str:
    return BLOCK + "\\begin{tikzpicture}[cg]\n" + body + "\n\\end{tikzpicture}%\n"


def _rules(findings) -> list[str]:
    return [finding.rule for finding in findings]


class TestPlain:
    def test_a_line_break_splits_the_label_and_a_spacing_is_dropped(self):
        assert _twin.plain(r"\textbf{Plan}\\[2pt]the gloss") == ["Plan", "the gloss"]

    def test_maths_is_dropped(self):
        assert _twin.plain(r"$x_1$ state") == ["state"]
        assert _twin.plain(r"estimate \(\hat{x}\)") == ["estimate"]

    def test_maths_straight_after_a_line_break_is_dropped(self):
        assert _twin.plain(r"innovation\\$z - C\hat{x}$") == ["innovation"]

    def test_a_label_of_maths_alone_is_empty(self):
        assert _twin.plain("$x$") == []

    def test_spaces_and_escaped_characters_read_as_printed(self):
        assert _twin.plain(r"A~B\,C \& D\_e 50\%") == ["A B C & D_e 50%"]

    def test_a_colour_argument_is_not_text(self):
        assert _twin.plain(r"\textcolor{cgMuteText}{quiet}") == ["quiet"]

    def test_a_two_tier_label_is_a_name_over_a_gloss(self):
        assert _twin.plain(r"\cglab{Plan}{a gloss}") == ["Plan", "a gloss"]

    def test_a_loop_variable_alone_is_empty(self):
        assert _twin.plain(r"\x") == []


class TestWords:
    def test_words_are_lower_cased_alphanumeric_runs(self):
        assert _twin.words("CS-IO404 4-channel relay, x_1") == {
            "cs",
            "io404",
            "4",
            "channel",
            "relay",
            "x",
            "1",
        }


class TestNames:
    def test_a_name_is_the_labels_first_line(self):
        source = _picture(r"\node[cgbox] (relay) {CS-IO404\\4-channel relay};")

        assert _twin.names(source) == [Text("relay", "CS-IO404")]

    def test_a_two_tier_labels_gloss_is_not_a_name(self):
        source = _picture(r"\node[cgbox] (plan) {\cglab{Plan}{what to do next}};")

        assert _twin.names(source) == [Text("plan", "Plan")]

    def test_zone_titles_and_legend_text_are_names(self):
        source = _picture(
            "\\cgzonelabel{fixed}{cgFlow}{Deterministic}\n"
            "\\cglegenditem{lg}{0,0}{cgFlow}{data flow}"
        )

        assert _twin.names(source) == [Text("fixed", "Deterministic"), Text("lg", "data flow")]

    def test_an_unnamed_node_is_named_by_its_text(self):
        source = _picture(r"\node[cgnote] at (0,0) {a note};")

        assert _twin.names(source) == [Text("a note", "a note")]

    @pytest.mark.parametrize("label", ["", "$x_1$", r"\x", "  "])
    def test_a_label_with_no_text_is_not_a_name(self, label):
        assert _twin.names(_picture(f"\\node (a) {{{label}}};")) == []

    def test_a_label_carrying_a_loop_variable_is_not_compared(self):
        """Each pass sets a different label (`e1`, `e2`), so the text in
        the source is none of them."""
        source = _picture(
            "\\foreach \\n/\\x in {1/0, 2/1} {\\node (s\\n) at (\\x,0) {e\\n};}\n\\node (k) {Kept};"
        )

        assert _twin.names(source) == [Text("k", "Kept")]

    def test_nothing_is_read_from_the_house_block(self):
        assert _twin.names(_picture("")) == []

    def test_a_figure_with_no_house_block_is_read_whole(self):
        assert _twin.names(r"\node (a) {Alpha};") == [Text("a", "Alpha")]

    def test_a_tree_child_is_a_name_not_a_tag(self):
        source = _picture(r"\node (r) {Root} child { node (c) {Child} };")

        assert _twin.names(source) == [Text("r", "Root"), Text("c", "Child")]
        assert _twin.tags(source) == []

    def test_options_nest_and_may_follow_the_name(self):
        source = _picture(r"\node (k) [label={[red]above:x}, cgkey] at (1,0) {Key};")

        assert _twin.names(source) == [Text("k", "Key")]

    def test_a_declaration_cut_off_before_its_label_is_skipped(self):
        assert _twin.names(r"\node (a) [draw]") == []

    def test_a_label_left_open_runs_to_the_end(self):
        assert _twin.names(r"\node (a) {Alpha") == [Text("a", "Alpha")]

    def test_a_statement_that_ends_before_a_label_is_skipped(self):
        assert _twin.names(r"\node (a) [draw]; \node (b) {Beta};") == [Text("b", "Beta")]

    def test_spaced_macro_arguments_are_read(self):
        source = "\\cgzonelabel {fixed}\n  {cgFlow} {Deterministic}"

        assert _twin.names(source) == [Text("fixed", "Deterministic")]

    def test_a_macro_definition_outside_a_house_block_is_not_a_name(self):
        source = (
            "\\providecommand{\\cgzonelabel}[3]{%\n"
            "  \\node[cgzonetitle=#2] at (#1.north west) {#3};}%\n"
            "\\cgzonelabel{fixed}{cgFlow}{#1}\n\\cgzonelabel{fixed}{cgFlow}\n"
        )

        assert _twin.names(source) == []

    def test_a_node_whose_name_never_closes_is_skipped(self):
        assert _twin.names(r"\node (a {Alpha};") == []


class TestTags:
    def test_a_node_on_a_draw_is_a_tag_between_its_ends(self):
        source = _picture(r"\draw[cgedge] (plant) to[bend right=12] node[cgtag] {output} (sensor);")

        assert _twin.tags(source) == [Text("plant->sensor", "output")]
        assert _twin.names(source) == []

    def test_anchors_and_any_style_still_name_the_ends(self):
        source = _picture(
            r"\draw[->] (relay.south) -- (pump.north) node[midway,right] {12 V switched};"
        )

        assert _twin.tags(source) == [Text("relay->pump", "12 V switched")]

    def test_every_line_of_a_tag_is_compared(self):
        source = _picture(r"\draw (a) -- node {sensor\\readings} (b);")

        assert _twin.tags(source) == [Text("a->b", "sensor"), Text("a->b", "readings")]

    def test_a_tag_on_a_path_between_points_is_named_by_its_text(self):
        source = _picture(r"\path (0,0) -- node {gap} (1,0);")

        assert _twin.tags(source) == [Text("gap", "gap")]

    def test_a_semicolon_inside_a_tag_does_not_end_the_path(self):
        source = _picture(r"\draw (a) -- node {in; out} (b);")

        assert _twin.tags(source) == [Text("a->b", "in; out")]

    def test_an_edge_operators_tag_is_a_tag(self):
        source = _picture(r"\draw (hub) edge node {ask} (s1);")

        assert _twin.tags(source) == [Text("hub->s1", "ask")]


class TestPanels:
    def test_letters_opening_a_label_line_are_the_tex_panels(self):
        source = _picture(
            "\\node (a) {(a) three lumps\\\\(not a panel)};\n"
            "\\node at (0,1) {(b) a mesh};\n\\node (c) {see (c) below};"
        )

        assert _twin.panels_tex(source) == {"a", "b"}

    def test_a_twins_panels_are_its_standalone_letter_tokens(self):
        assert _twin.panels_twin("( x_3 )  f(x)  (a) lumps   (b) mesh  (ab)") == {"a", "b"}


class TestAgree:
    def test_an_agreeing_pair_finds_nothing(self):
        source = _picture(
            "\\node (p) {(a) Plant};\n\\node (s) {Sensor};\n\\draw (p) -- node {output} (s);"
        )

        assert _twin.agree(source, "(a) [plant] --output--> [SENSOR]", "f.txt") == ([], [])

    def test_a_renamed_box_names_the_words_the_twin_lacks(self):
        source = _picture(r"\node (relay) {4-channel relay};")

        findings, _ = _twin.agree(source, "[ 4-ch relay ]", "f.txt")

        assert [(f.rule, f.target, f.measurement) for f in findings] == [
            ("t1-labels", "relay", 'missing "channel"')
        ]

    def test_a_tag_left_out_of_the_twin_fires(self):
        source = _picture("\\node (a) {A};\\node (b) {B};\\draw (a) -- node {reads} (b);")

        findings, _ = _twin.agree(source, "[A] ----> [B]", "f.txt")

        assert [(f.rule, f.target, f.measurement) for f in findings] == [
            ("t2-tags", "a->b", 'missing "reads"')
        ]

    def test_panel_letters_that_differ_fire_once_for_the_figure(self):
        source = _picture("\\node (a) {(a) one};\\node (b) {(b) two};")

        findings, _ = _twin.agree(source, "(a) one   two", "f.txt")

        assert [(f.rule, f.target, f.measurement) for f in findings] == [
            ("t3-panels", "figure", "tex (a), (b); twin (a)")
        ]

    def test_a_twin_with_no_panels_says_so(self):
        source = _picture("\\node (a) {(a) one};")

        findings, _ = _twin.agree(source, "one", "f.txt")

        assert findings[-1].measurement == "tex (a); twin none"

    def test_no_twin_is_one_finding_and_the_comparisons_are_not_measured(self):
        source = _picture(r"\node (a) {A};")

        findings, not_measured = _twin.agree(source, None, "flow.txt")

        assert [(f.rule, f.target, f.measurement) for f in findings] == [
            ("twin-missing", "figure", "no flow.txt beside the figure")
        ]
        assert not_measured == [
            ("t1-labels", _twin.NO_TWIN),
            ("t2-tags", _twin.NO_TWIN),
            ("t3-panels", _twin.NO_TWIN),
        ]

    def test_an_empty_twin_fires_once_per_name(self):
        source = _picture("\\node (a) {Alpha};\\node (b) {Beta};")

        findings, _ = _twin.agree(source, "", "f.txt")

        assert _rules(findings) == ["t1-labels", "t1-labels"]


class TestFixtures:
    @pytest.mark.parametrize(
        ("fixture", "rule"),
        [("renamed", "t1-labels"), ("untagged", "t2-tags"), ("panels", "t3-panels")],
    )
    def test_the_firing_pair_fires_its_rule_and_only_it(self, fixture, rule):
        tex = FIXTURES / f"{fixture}.tex"
        twin = tex.with_suffix(".txt").read_text(encoding="utf-8")

        findings, not_measured = _twin.agree(tex.read_text(encoding="utf-8"), twin, "f.txt")

        assert set(_rules(findings)) == {rule}
        assert not_measured == []

    def test_the_agreeing_pair_is_clean(self):
        tex = FIXTURES / "agrees.tex"
        twin = tex.with_suffix(".txt").read_text(encoding="utf-8")

        assert _twin.agree(tex.read_text(encoding="utf-8"), twin, "f.txt") == ([], [])

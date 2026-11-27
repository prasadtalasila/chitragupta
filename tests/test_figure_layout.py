import json
import subprocess
from pathlib import Path

import pytest

from chitragupta import review, tex_engine
from chitragupta.review import figure_layout
from chitragupta.review.figure_layout import _probe
from tests.conftest import needs_tikz


class TestFiguresIn:
    def test_finds_a_markdown_drafts_marked_figure(self, tmp_path):
        (tmp_path / "figures").mkdir()
        figure = tmp_path / "figures" / "flow.tex"
        figure.write_text(
            "\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}\n", encoding="utf-8"
        )
        draft = tmp_path / "survey.md"
        draft.write_text("Text.\n\n<!-- figure: figures/flow -->\n\nMore.\n", encoding="utf-8")

        assert figure_layout.figures_in(draft) == [figure]

    def test_drops_a_marker_naming_a_file_that_is_not_there(self, tmp_path):
        draft = tmp_path / "survey.md"
        draft.write_text("<!-- figure: figures/missing -->\n", encoding="utf-8")

        assert figure_layout.figures_in(draft) == []

    def test_finds_a_tex_fragments_real_input(self, tmp_path):
        (tmp_path / "figures").mkdir()
        figure = tmp_path / "figures" / "arch.tex"
        figure.write_text(
            "\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}\n", encoding="utf-8"
        )
        draft = tmp_path / "chapter.tex"
        draft.write_text("\\input{figures/arch.tex}\n%figure: figures/arch\n", encoding="utf-8")

        assert figure_layout.figures_in(draft) == [figure]

    def test_a_draft_with_no_figures_yields_nothing(self, tmp_path):
        draft = tmp_path / "survey.md"
        draft.write_text("Prose only, no figure at all.\n", encoding="utf-8")

        assert figure_layout.figures_in(draft) == []


class TestNodeText:
    def test_a_thirty_word_node_is_reported(self):
        words = " ".join(f"word{n}" for n in range(30))
        source = f"\\begin{{tikzpicture}}\\node (a) {{{words}}};\\end{{tikzpicture}}"

        overlong = figure_layout.overlong_nodes(source)

        assert [name for name, _ in overlong] == ["a"]
        assert overlong[0][1] == 30

    def test_a_five_word_node_is_not(self):
        source = "\\begin{tikzpicture}\\node (a) {one two three four five};\\end{tikzpicture}"

        assert figure_layout.overlong_nodes(source) == []

    def test_exactly_fifteen_words_is_not_reported(self):
        words = " ".join(f"word{n}" for n in range(15))
        source = f"\\begin{{tikzpicture}}\\node (a) {{{words}}};\\end{{tikzpicture}}"

        assert figure_layout.overlong_nodes(source) == []

    def test_a_styled_node_still_parses(self):
        words = " ".join(f"word{n}" for n in range(20))
        source = f"\\node[draw, fill=blue!10] (a) at (0,0) {{{words}}};"

        assert [name for name, _ in figure_layout.overlong_nodes(source)] == ["a"]

    def test_latex_markup_in_a_label_is_not_counted_as_words(self):
        source = "\\node (a) {\\textbf{alpha} \\emph{beta} gamma};"

        assert figure_layout.overlong_nodes(source) == []

    def test_a_commented_out_node_is_not_measured(self):
        words = " ".join(f"word{n}" for n in range(20))
        source = f"% \\node (old) {{{words}}};\n\\node (a) {{short}};\n"

        assert figure_layout.overlong_nodes(source) == []

    def test_a_child_syntax_nodes_label_is_measured(self):
        words = " ".join(f"word{n}" for n in range(20))
        source = f"\\node (root) {{root}} child {{ node (leaf) {{{words}}} }};"

        assert [name for name, _ in figure_layout.overlong_nodes(source)] == ["leaf"]


class TestEdgeList:
    def test_a_three_node_chain(self):
        source = "\\draw (a) -- (b) -- (c);"

        assert figure_layout.edge_list(source) == [("a", "b"), ("b", "c")]

    def test_separate_draw_statements(self):
        source = "\\draw (a) -- (b);\n\\draw (b) -- (c);\n"

        assert figure_layout.edge_list(source) == [("a", "b"), ("b", "c")]

    def test_an_arrow_is_an_edge_like_any_other(self):
        source = "\\draw[->] (a) -- (b);"

        assert figure_layout.edge_list(source) == [("a", "b")]

    def test_bare_coordinates_are_not_nodes(self):
        source = "\\draw (0,0) -- (2,0);"

        assert figure_layout.edge_list(source) == []

    def test_a_foreach_loop_variable_is_not_a_node(self):
        source = "\\foreach \\p in {A,...,F} \\draw (\\p)--(\\q);"

        assert figure_layout.edge_list(source) == []

    def test_a_path_statement_counts_too(self):
        source = "\\path (a) edge (b);"

        assert figure_layout.edge_list(source) == [("a", "b")]

    def test_a_figure_with_no_edges(self):
        source = "\\node (a) {A};\n\\node (b) {B};\n"

        assert figure_layout.edge_list(source) == []

    def test_a_commented_out_draw_is_not_an_edge(self):
        source = "% \\draw (a) -- (ghost);\n\\draw (a) -- (b);\n"

        assert figure_layout.edge_list(source) == [("a", "b")]


class TestEdgeListLimits:
    def test_an_anchor_rides_along_rather_than_being_stripped(self):
        assert figure_layout.edge_list("\\draw (a.south) -- (b.north);") == [("a.south", "b.north")]

    def test_an_edge_drawn_by_a_wrapping_library_is_invisible(self):
        assert figure_layout.edge_list("\\graph { a -> b };") == []

    def test_a_to_with_options_is_still_an_edge(self):
        assert figure_layout.edge_list("\\draw (a) to[bend left] (b);") == [("a", "b")]


class TestStrandedArrowheads:
    def test_the_defect_from_the_issue(self):
        source = "\\draw[->] (46,36) -- (46,44);\n\\draw[->] (46,32) -- (46,36);\n"

        assert figure_layout.stranded_arrowheads(source) == ["46,36"]

    def test_a_chain_through_a_named_node_is_not_a_finding(self):
        source = "\\draw[->] (intake) -- (parse);\n\\draw[->] (parse) -- (index);\n"

        assert figure_layout.stranded_arrowheads(source) == []

    def test_the_last_piece_alone_carrying_the_head_is_the_fix(self):
        source = "\\draw[->] (46,36) -- (46,44);\n\\draw (46,32) -- (46,36);\n"

        assert figure_layout.stranded_arrowheads(source) == []

    def test_two_arrows_converging_on_one_point_are_not_a_finding(self):
        source = "\\draw[->] (0,0) -- (46,36);\n\\draw[->] (90,0) -- (46,36);\n"

        assert figure_layout.stranded_arrowheads(source) == []

    def test_whitespace_in_a_coordinate_does_not_hide_the_junction(self):
        source = "\\draw[->] (46, 36) -- (46,44);\n\\draw[->] (46,32) -- (46,36);\n"

        assert figure_layout.stranded_arrowheads(source) == ["46,36"]

    def test_a_head_at_the_start_only_is_not_a_finding(self):
        source = "\\draw[<-] (46,36) -- (46,44);\n\\draw[<-] (46,32) -- (46,36);\n"

        assert figure_layout.stranded_arrowheads(source) == []

    def test_a_perpendicular_bend_strands_a_head_just_as_a_straight_run_does(self):
        source = "\\draw[->,dashed] (70,32) -- (72,32);\n\\draw[->] (72,32) -- (72,36);\n"

        assert figure_layout.stranded_arrowheads(source) == ["72,32"]

    def test_two_dimension_bars_sharing_a_boundary_are_not_a_finding(self):
        source = (
            "\\draw[<->] (10,-7) -- (55,-7) node[midway,above] {detection gap};\n"
            "\\draw[<->] (55,-7) -- (95,-7) node[midway,above] {response gap};\n"
        )

        assert figure_layout.stranded_arrowheads(source) == []

    def test_a_curve_continuing_out_of_an_arrowhead_is_a_finding(self):
        source = (
            "\\draw[->] (90,10) -- (90,34) node[anchor=south east] {state};\n"
            "\\draw[thick] (90,34) .. controls (100,32) and (106,22) .. (124,18);\n"
        )

        assert figure_layout.stranded_arrowheads(source) == ["90,34"]

    def test_a_coordinate_inside_the_option_group_is_not_the_paths_first_point(self):
        source = "\\draw[->] (46,32) -- (46,36);\n\\draw[shift={(1,0)}] (46,36) -- (46,44);\n"

        assert figure_layout.stranded_arrowheads(source) == ["46,36"]

    def test_a_double_headed_arrow_strands_its_end_head_too(self):
        source = "\\draw[<->] (46,32) -- (46,36);\n\\draw (46,36) -- (46,44);\n"

        assert figure_layout.stranded_arrowheads(source) == ["46,36"]

    def test_a_commented_out_segment_does_not_strand_anything(self):
        source = "\\draw[->] (46,32) -- (46,36);\n% \\draw (46,36) -- (46,44);\n"

        assert figure_layout.stranded_arrowheads(source) == []

    def test_one_junction_is_reported_once(self):
        source = (
            "\\draw[->] (0,0) -- (46,36);\n"
            "\\draw[->] (90,0) -- (46,36);\n"
            "\\draw (46,36) -- (46,44);\n"
        )

        assert figure_layout.stranded_arrowheads(source) == ["46,36"]

    def test_an_arrows_meta_tip_specification_is_recognised(self):
        source = "\\draw[-{Stealth}] (46,32) -- (46,36);\n\\draw (46,36) -- (46,44);\n"

        assert figure_layout.stranded_arrowheads(source) == ["46,36"]


class TestStrandedArrowheadLimits:
    def test_an_option_group_left_open_is_skipped(self):
        source = "\\draw[-> (46,32) -- (46,36);\n\\draw (46,36) -- (46,44);\n"

        assert figure_layout.stranded_arrowheads(source) == []

    def test_a_path_statement_with_no_points_at_all_is_skipped(self):
        source = "\\draw[->] grid;\n\\draw[->] (46,32) -- (46,36);\n"

        assert figure_layout.stranded_arrowheads(source) == []

    def test_a_reversed_continuation_is_not_recognised(self):
        source = "\\draw[->] (46,32) -- (46,36);\n\\draw (46,44) -- (46,36);\n"

        assert figure_layout.stranded_arrowheads(source) == []


class TestScaffold:
    def test_it_is_article_not_standalone(self):
        scaffold = figure_layout.scaffold("\\node (a) {A};", ["a"])

        assert "{article}" in scaffold
        assert "standalone" not in scaffold

    def test_it_uses_the_public_coordinate_accessor(self):
        scaffold = figure_layout.scaffold("\\node (a) {A};", ["a"])

        assert "\\pgfgetlastxy" in scaffold
        assert "\\pgf@x" not in scaffold

    def test_it_probes_the_pictures_own_bounding_box(self):
        scaffold = figure_layout.scaffold("\\node (a) {A};", ["a"])

        assert "current bounding box" in scaffold

    def test_it_sets_type_as_the_pdf_render_does(self):
        scaffold = figure_layout.scaffold("\\node (a) {A};", ["a"])

        assert "\\documentclass[12pt]{article}" in scaffold
        assert "\\setmainfont{STIX Two Text}" in scaffold

    def test_a_box_is_read_from_its_four_sides(self):
        scaffold = figure_layout.scaffold("\\node (a) {A};", ["a"])

        assert "\\cgsides{a}" in scaffold
        for side in ("west", "east", "south", "north"):
            assert f"{{#1}}{{{side}}}" in scaffold
        assert "{south west}" not in scaffold

    def test_a_name_spelled_with_a_macro_is_declared_but_not_probed(self):
        source = "\\foreach \\i in {1,2} { \\node (s\\i) at (\\i,0) {S}; }\n\\node (a) {A};\n"

        names = figure_layout.node_names(source)
        scaffold = figure_layout.scaffold(source, names)

        assert names == ["s\\i", "a"]
        assert "\\cgsides{a}" in scaffold
        assert "\\cgsides{s\\i}" not in scaffold


class TestProbePlacement:
    def test_node_names_finds_every_named_node(self):
        source = "\\node (a) {A};\n\\node[draw] (b) at (1,0) {B};\n"

        assert figure_layout.node_names(source) == ["a", "b"]

    def test_node_names_ignores_an_unnamed_node(self):
        assert figure_layout.node_names("\\node {just a label};\n") == []

    def test_a_node_named_only_in_a_comment_is_not_probed(self):
        source = "% see \\node (ghost) for how this works\n\\node (a) {A};\n"

        assert figure_layout.node_names(source) == ["a"]

    def test_an_escaped_percent_does_not_start_a_comment(self):
        source = "\\node (pct) {50\\% of runs}; \\node (b) {B};\n"

        assert figure_layout.node_names(source) == ["pct", "b"]

    def test_node_names_finds_a_child_syntaxs_names(self):
        source = (
            "\\node (root) {root}\n"
            "  child { node (left) {L} }\n"
            "  child { node[draw] (right) {R} };\n"
        )

        assert figure_layout.node_names(source) == ["root", "left", "right"]

    def test_a_mid_path_label_node_is_found_too(self):
        source = "\\draw (a) -- node (mid) {label} (b);\n"

        assert figure_layout.node_names(source) == ["mid"]

    def test_the_word_node_inside_a_label_is_not_a_declaration(self):
        source = "\\node (a) {a node (of sorts)};\n"

        assert figure_layout.node_names(source) == ["a"]

    def test_a_name_inside_a_macro_definition_is_not_probed(self):
        source = (
            "\\providecommand{\\cglegenditem}[4]{%\n"
            "  \\node[cgswatch=#3] (#1) at (#2) {};\n"
            "  \\node[cglegendtext, right=1.6mm of #1] (#1-t) {#4};}\n"
            "\\node (a) {A};\n"
        )

        assert figure_layout.node_names(source) == ["a"]

    def test_probes_go_inside_the_picture_not_after_it(self):
        source = "\\begin{tikzpicture}\n\\node (a) {A};\n\\end{tikzpicture}\n"

        built = figure_layout.scaffold(source, ["a"])
        before_end = built[: built.index("\\end{tikzpicture}")]

        assert "CGBOX a" in before_end

    def test_the_last_picture_is_the_one_measured(self):
        source = (
            "\\begin{tikzpicture}\n\\node (a) {A};\n\\end{tikzpicture}\n"
            "\\begin{tikzpicture}\n\\node (b) {B};\n\\end{tikzpicture}\n"
        )

        built = figure_layout.scaffold(source, ["a", "b"])

        assert built.index("CGBOX a") > built.index("\\node (b)")

    def test_cgbox_lines_parse_out_of_a_log(self):
        log = (
            "This is pdfTeX, Version 3.14\n"
            "CGBOX a -42.87912pt -7.97742pt 42.87912pt 7.97742pt\n"
            "CGBOX current bounding box -20.0pt -10.0pt 60.0pt 10.0pt\n"
            "Output written on probe.pdf\n"
        )

        boxes = figure_layout.parse_boxes(log)

        assert boxes["a"] == (-42.87912, -7.97742, 42.87912, 7.97742)
        assert boxes[figure_layout.BBOX_NAME] == (-20.0, -10.0, 60.0, 10.0)

    def test_a_log_with_no_cgbox_lines_parses_to_nothing(self):
        assert figure_layout.parse_boxes("pdfTeX ran and said nothing\n") == {}

    def test_a_figure_with_no_picture_at_all_still_builds(self):
        built = figure_layout.scaffold("% just a comment\n", [])

        assert "\\begin{document}" in built


@pytest.mark.usefixtures("programs_on_path")
class TestMaxPrintLineEnv:
    def test_the_subprocess_env_sets_a_generous_max_print_line(self, tmp_path, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(kwargs)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(_probe, "_run", fake_run)
        figure = tmp_path / "fig.tex"
        figure.write_text(
            "\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}\n", encoding="utf-8"
        )

        figure_layout.node_boxes(figure)

        assert len(calls) == 1
        env = calls[0].get("env")
        assert env is not None
        assert int(env["max_print_line"]) >= 1000

    def test_the_rest_of_the_hosts_environment_still_reaches_pdflatex(self, tmp_path, monkeypatch):
        monkeypatch.setenv("A_MARKER_ONLY_THE_HOST_SETS", "yes")
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(kwargs)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(_probe, "_run", fake_run)
        figure = tmp_path / "fig.tex"
        figure.write_text(
            "\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}\n", encoding="utf-8"
        )

        figure_layout.node_boxes(figure)

        assert calls[0]["env"]["A_MARKER_ONLY_THE_HOST_SETS"] == "yes"


@pytest.mark.usefixtures("programs_on_path")
class TestProbeTexHardening:
    def _run(self, tmp_path, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(_probe, "_run", fake_run)
        figure = tmp_path / "fig.tex"
        figure.write_text(
            "\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}\n", encoding="utf-8"
        )
        figure_layout.node_boxes(figure)
        assert len(calls) == 1
        return calls[0]

    def test_shell_escape_is_off(self, tmp_path, monkeypatch):
        cmd, _ = self._run(tmp_path, monkeypatch)
        assert "-no-shell-escape" in cmd

    def test_it_compiles_with_lualatex_as_the_pdf_render_does(self, tmp_path, monkeypatch):
        cmd, _ = self._run(tmp_path, monkeypatch)
        assert Path(cmd[0]).name == "lualatex"

    def test_reads_are_paranoid_even_if_the_host_says_otherwise(self, tmp_path, monkeypatch):
        monkeypatch.setenv("openin_any", "a")
        _, kwargs = self._run(tmp_path, monkeypatch)
        assert kwargs["env"]["openin_any"] == "r"

    def test_it_loads_the_same_read_fence_as_the_pdf_render(self, tmp_path, monkeypatch):
        cmd, _ = self._run(tmp_path, monkeypatch)
        assert f"--lua={tex_engine.READ_FENCE}" in cmd


@pytest.mark.slow
@needs_tikz
class TestProbeAgainstRealLualatex:
    def test_cgbox_lines_parse_into_boxes(self, tmp_path):
        figure = tmp_path / "fig.tex"
        figure.write_text(
            "\\begin{tikzpicture}\n"
            "\\node (a) at (0,0) {A};\n"
            "\\node (b) at (3,0) {B};\n"
            "\\end{tikzpicture}\n",
            encoding="utf-8",
        )

        boxes = figure_layout.node_boxes(figure)

        assert set(boxes) >= {"a", "b"}
        for name in ("a", "b"):
            x1, y1, x2, y2 = boxes[name]
            assert x1 < x2 and y1 < y2, f"{name} has a degenerate box"

    def test_a_circle_is_measured_at_its_diameter(self, tmp_path):
        figure = tmp_path / "fig.tex"
        figure.write_text(
            "\\begin{tikzpicture}\n"
            "\\node[circle,draw,minimum size=2cm,inner sep=0pt] (c) at (0,0) {};\n"
            "\\end{tikzpicture}\n",
            encoding="utf-8",
        )

        x1, y1, x2, y2 = figure_layout.node_boxes(figure)["c"]

        two_cm = 2 * 72.27 / 2.54
        assert x2 - x1 == pytest.approx(two_cm, abs=1.0)
        assert y2 - y1 == pytest.approx(two_cm, abs=1.0)

    def test_the_picture_bounding_box_is_reported_too(self, tmp_path):
        figure = tmp_path / "fig.tex"
        figure.write_text(
            "\\begin{tikzpicture}\n\\node (a) at (0,0) {A};\n\\end{tikzpicture}\n",
            encoding="utf-8",
        )

        boxes = figure_layout.node_boxes(figure)

        assert figure_layout.BBOX_NAME in boxes

    def test_a_figure_defining_a_node_macro_compiles_and_is_measured(self, tmp_path):
        figure = tmp_path / "fig.tex"
        figure.write_text(
            "\\providecommand{\\cgtestmark}[1]{\\node (#1) at (0,1) {#1};}\n"
            "\\begin{tikzpicture}\n"
            "\\node (a) at (0,0) {A};\n"
            "\\cgtestmark{m}\n"
            "\\end{tikzpicture}\n",
            encoding="utf-8",
        )

        boxes = figure_layout.node_boxes(figure)

        assert set(boxes) == {"a", figure_layout.BBOX_NAME}

    def test_compiling_does_not_litter_beside_the_figure(self, tmp_path):
        figure = tmp_path / "fig.tex"
        figure.write_text(
            "\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}\n", encoding="utf-8"
        )

        figure_layout.node_boxes(figure)

        assert sorted(p.name for p in tmp_path.iterdir()) == ["fig.tex"]

    def test_a_label_only_unicode_fonts_set_is_measured(self, tmp_path):
        figure = tmp_path / "fig.tex"
        figure.write_text(
            "\\begin{tikzpicture}\\node (a) {x \u2264 y, \u03b1};\\end{tikzpicture}\n",
            encoding="utf-8",
        )

        assert "a" in figure_layout.node_boxes(figure)

    def test_a_figure_that_does_not_compile_raises_rather_than_returning_junk(self, tmp_path):
        figure = tmp_path / "broken.tex"
        figure.write_text("\\begin{tikzpicture}\n\\node (a) {\n", encoding="utf-8")

        with pytest.raises(figure_layout.FigureCompileError):
            figure_layout.node_boxes(figure)


class TestOverlap:
    def test_overlapping_boxes_are_reported(self):
        boxes = {"a": (0.0, 0.0, 40.0, 10.0), "b": (20.0, 0.0, 60.0, 10.0)}

        assert figure_layout.overlaps(boxes) == [("a", "b")]

    def test_spaced_boxes_are_not(self):
        boxes = {"a": (0.0, 0.0, 10.0, 10.0), "b": (50.0, 0.0, 60.0, 10.0)}

        assert figure_layout.overlaps(boxes) == []

    def test_boxes_that_only_touch_are_not_overlapping(self):
        boxes = {"a": (0.0, 0.0, 10.0, 10.0), "b": (10.0, 0.0, 20.0, 10.0)}

        assert figure_layout.overlaps(boxes) == []

    def test_separated_vertically_is_not_an_overlap(self):
        boxes = {"a": (0.0, 0.0, 40.0, 10.0), "b": (0.0, 50.0, 40.0, 60.0)}

        assert figure_layout.overlaps(boxes) == []

    def test_a_zone_node_containing_its_children_is_not_an_overlap(self):
        boxes = {
            "control-plane": (0.0, 0.0, 300.0, 100.0),
            "auth": (20.0, 20.0, 80.0, 60.0),
            "registry": (120.0, 20.0, 180.0, 60.0),
        }

        assert figure_layout.overlaps(boxes) == []

    def test_a_genuine_partial_collision_is_still_reported(self):
        boxes = {"a": (0.0, 0.0, 40.0, 20.0), "b": (20.0, 10.0, 60.0, 30.0)}

        assert figure_layout.overlaps(boxes) == [("a", "b")]

    def test_the_picture_bounding_box_is_not_an_overlap_candidate(self):
        boxes = {
            "a": (0.0, 0.0, 10.0, 10.0),
            figure_layout.BBOX_NAME: (-1.0, -1.0, 11.0, 11.0),
        }

        assert figure_layout.overlaps(boxes) == []


class TestProtrusionAndEmptiness:
    def test_a_node_protruding_past_the_others_is_reported(self):
        boxes = {
            "a": (0.0, 0.0, 40.0, 10.0),
            "b": (0.0, 12.0, 40.0, 22.0),
            "spike": (0.0, 200.0, 5.0, 210.0),
            figure_layout.BBOX_NAME: (0.0, 0.0, 40.0, 210.0),
        }

        assert figure_layout.protrudes(boxes) is True

    def test_non_node_content_reaching_past_every_node_is_reported(self):
        boxes = {
            "a": (0.0, 0.0, 40.0, 10.0),
            "b": (0.0, 12.0, 40.0, 22.0),
            figure_layout.BBOX_NAME: (0.0, 0.0, 40.0, 200.0),
        }

        assert figure_layout.protrudes(boxes) is True

    def test_a_layered_diagram_with_ordinary_row_spacing_is_not_reported(self):
        boxes = {
            "a": (0.0, 0.0, 40.0, 10.0),
            "b": (0.0, 20.0, 40.0, 30.0),
            "c": (0.0, 40.0, 40.0, 50.0),
            figure_layout.BBOX_NAME: (0.0, 0.0, 40.0, 50.0),
        }

        assert figure_layout.protrudes(boxes) is False

    def test_a_compact_figure_does_not_protrude(self):
        boxes = {
            "a": (0.0, 0.0, 40.0, 10.0),
            "b": (0.0, 12.0, 40.0, 22.0),
            figure_layout.BBOX_NAME: (0.0, 0.0, 40.0, 22.0),
        }

        assert figure_layout.protrudes(boxes) is False

    def test_emptiness_is_a_proportion_between_zero_and_one(self):
        boxes = {
            "a": (0.0, 0.0, 10.0, 10.0),
            figure_layout.BBOX_NAME: (0.0, 0.0, 20.0, 10.0),
        }

        assert figure_layout.emptiness(boxes) == pytest.approx(0.5)

    def test_emptiness_of_a_figure_with_no_room_to_spare_is_zero(self):
        boxes = {
            "a": (0.0, 0.0, 10.0, 10.0),
            figure_layout.BBOX_NAME: (0.0, 0.0, 10.0, 10.0),
        }

        assert figure_layout.emptiness(boxes) == pytest.approx(0.0)

    def test_a_degenerate_bounding_box_gives_no_proportion(self):
        boxes = {figure_layout.BBOX_NAME: (0.0, 0.0, 0.0, 0.0)}

        assert figure_layout.emptiness(boxes) is None

    def test_a_zero_area_bounding_box_with_nodes_gives_no_proportion(self):
        boxes = {"a": (0.0, 0.0, 10.0, 10.0), figure_layout.BBOX_NAME: (0.0, 0.0, 0.0, 0.0)}

        assert figure_layout.emptiness(boxes) is None

    def test_a_figure_with_no_named_nodes_gives_no_proportion(self):
        boxes = {figure_layout.BBOX_NAME: (0.0, 0.0, 100.0, 100.0)}

        assert figure_layout.emptiness(boxes) is None


def _draft_with_figure(tmp_path, body: str, name: str = "flow"):
    (tmp_path / "figures").mkdir(exist_ok=True)
    (tmp_path / "figures" / f"{name}.tex").write_text(body, encoding="utf-8")
    draft = tmp_path / "survey.md"
    existing = draft.read_text(encoding="utf-8") if draft.exists() else "Prose.\n"
    draft.write_text(f"{existing}\n<!-- figure: figures/{name} -->\n", encoding="utf-8")
    return draft


class TestCheckDraft:
    def test_a_draft_with_no_figures_reports_nothing(self, tmp_path):
        draft = tmp_path / "survey.md"
        draft.write_text("No figures at all.\n", encoding="utf-8")

        assert figure_layout.check_draft(draft) == []

    def test_static_checks_run_without_any_compile(self, tmp_path, monkeypatch):
        def _no_tikz():
            raise figure_layout.MissingBinary("tikz.sty is not installed")

        monkeypatch.setattr(figure_layout, "_require_tikz", _no_tikz)
        words = " ".join(f"word{n}" for n in range(30))
        draft = _draft_with_figure(tmp_path, f"\\node (a) {{{words}}};\n\\draw (a) -- (b);\n")

        results = figure_layout.check_draft(draft)

        assert len(results) == 1
        assert results[0].overlong == [("a", 30)]
        assert results[0].edges == [("a", "b")]
        assert results[0].boxes is None
        assert results[0].skipped

    def test_a_host_with_no_lualatex_skips_geometry_rather_than_crashing(
        self, tmp_path, monkeypatch
    ):
        def _no_lualatex(binary):
            raise figure_layout.MissingBinary(f"'{binary}' is not on PATH.")

        monkeypatch.setattr(figure_layout, "_require", _no_lualatex)
        draft = _draft_with_figure(tmp_path, "\\node (a) {A};\n")

        results = figure_layout.check_draft(draft)

        assert results[0].boxes is None
        assert "lualatex" in results[0].skipped

    @pytest.mark.slow
    @needs_tikz
    def test_a_broken_figure_does_not_stop_the_others(self, tmp_path):
        _draft_with_figure(tmp_path, "\\begin{tikzpicture}\n\\node (a) {\n", name="broken")
        draft = _draft_with_figure(
            tmp_path,
            "\\begin{tikzpicture}\n\\node (b) at (0,0) {B};\n\\end{tikzpicture}\n",
            name="fine",
        )

        results = {r.path.stem: r for r in figure_layout.check_draft(draft)}

        assert results["broken"].failed is not None
        assert results["fine"].failed is None
        assert results["fine"].boxes is not None

    @pytest.mark.slow
    @needs_tikz
    def test_overlapping_nodes_are_found_end_to_end(self, tmp_path):
        draft = _draft_with_figure(
            tmp_path,
            "\\begin{tikzpicture}\n"
            "\\node (a) at (0,0) {A long label here};\n"
            "\\node (b) at (0.3,0) {Another long label};\n"
            "\\end{tikzpicture}\n",
        )

        results = figure_layout.check_draft(draft)

        assert results[0].overlapping == [("a", "b")]


class TestMeasurability:
    def test_a_figure_that_names_no_node_measured_nothing(self):
        result = figure_layout.FigureResult(path=Path("flow.tex"), boxes={})

        assert result.nothing_measurable is True
        assert result.has_findings is True

    def test_a_figure_with_a_measured_node_did_measure_something(self):
        result = figure_layout.FigureResult(
            path=Path("flow.tex"), declared=["a"], boxes={"a": (0.0, 0.0, 1.0, 1.0)}
        )

        assert result.nothing_measurable is False
        assert result.unmeasured == []

    def test_an_uncompiled_figure_makes_no_claim_either_way(self):
        skipped = figure_layout.FigureResult(path=Path("f.tex"), skipped="no tikz.sty")
        failed = figure_layout.FigureResult(path=Path("f.tex"), failed="! Missing $ inserted.")

        assert skipped.nothing_measurable is False
        assert failed.nothing_measurable is False

    def test_a_name_that_did_not_come_back_is_reported(self):
        result = figure_layout.FigureResult(
            path=Path("tree.tex"),
            declared=["source", "batch", "live"],
            boxes={"source": (0.0, 0.0, 1.0, 1.0)},
        )

        assert result.unmeasured == ["batch", "live"]
        assert result.nothing_measurable is False

    def test_the_pictures_own_bounding_box_does_not_count_as_a_measured_node(self):
        result = figure_layout.FigureResult(
            path=Path("flow.tex"), boxes={figure_layout.BBOX_NAME: (0.0, 0.0, 10.0, 10.0)}
        )

        assert result.nothing_measurable is True

    def test_check_draft_records_what_the_figure_declared(self, tmp_path, monkeypatch):
        def _no_tikz():
            raise figure_layout.MissingBinary("tikz.sty is not installed")

        monkeypatch.setattr(figure_layout, "_require_tikz", _no_tikz)
        draft = _draft_with_figure(tmp_path, "\\node (a) at (0,0) {A};\n\\node (b) at (2,0) {B};\n")

        assert figure_layout.check_draft(draft)[0].declared == ["a", "b"]

    @pytest.mark.slow
    @needs_tikz
    def test_an_anonymous_figure_is_reported_as_unmeasurable_end_to_end(self, tmp_path):
        draft = _draft_with_figure(
            tmp_path,
            "\\begin{tikzpicture}\n\\draw (0,0) rectangle (2,1);\n\\end{tikzpicture}\n",
        )

        result = figure_layout.check_draft(draft)[0]

        assert result.failed is None
        assert result.nothing_measurable is True


class TestMeasurabilityReport:
    def test_the_text_report_no_longer_calls_an_unmeasured_figure_clean(self, tmp_path):
        results = [figure_layout.FigureResult(path=tmp_path / "figures" / "quiet.tex", boxes={})]

        text = figure_layout.format_report(tmp_path / "s.md", results)

        assert "No layout findings" not in text
        assert "quiet.tex" in text
        assert "names no node" in text

    def test_a_genuinely_clean_figure_still_says_it_is_not_a_verdict(self, tmp_path):
        results = [
            figure_layout.FigureResult(
                path=tmp_path / "figures" / "flow.tex",
                declared=["a"],
                boxes={
                    "a": (0.0, 0.0, 10.0, 10.0),
                    figure_layout.BBOX_NAME: (0.0, 0.0, 11.0, 11.0),
                },
            )
        ]

        text = figure_layout.format_report(tmp_path / "s.md", results)

        assert "No layout findings" in text
        assert "not a verdict" in text

    def test_unmeasurability_is_a_finding_in_the_json(self, tmp_path):
        results = [figure_layout.FigureResult(path=tmp_path / "figures" / "quiet.tex", boxes={})]

        body = figure_layout.payload(tmp_path / "s.md", results, "cmd")

        assert [f["kind"] for f in body["findings"]] == ["nothing-measurable"]

    def test_the_unmeasured_names_are_a_diagnostic_and_never_a_finding(self, tmp_path):
        results = [
            figure_layout.FigureResult(
                path=tmp_path / "figures" / "tree.tex",
                declared=["source", "batch"],
                boxes={
                    "source": (0.0, 0.0, 2.0, 2.0),
                    figure_layout.BBOX_NAME: (0.0, 0.0, 2.0, 2.0),
                },
            )
        ]

        body = figure_layout.payload(tmp_path / "s.md", results, "cmd")

        assert body["figures"][0]["names_declared"] == ["source", "batch"]
        assert body["figures"][0]["names_unmeasured"] == ["batch"]
        assert body["findings"] == []

    def test_an_unmeasured_name_is_printed_beside_the_findings_it_undermines(self, tmp_path):
        results = [
            figure_layout.FigureResult(
                path=tmp_path / "figures" / "tree.tex",
                declared=["source", "batch", "live"],
                boxes={
                    "source": (0.0, 0.0, 10.0, 10.0),
                    figure_layout.BBOX_NAME: (0.0, 0.0, 10.0, 300.0),
                },
            )
        ]

        text = figure_layout.format_report(tmp_path / "s.md", results)

        assert "protrudes" in text
        assert "declared but not measured: `batch`, `live`" in text

    def test_the_shipped_geometry_checked_key_keeps_its_meaning(self, tmp_path):
        results = [figure_layout.FigureResult(path=tmp_path / "figures" / "quiet.tex", boxes={})]

        figures = figure_layout.payload(tmp_path / "s.md", results, "cmd")["figures"]

        assert figures[0]["geometry_checked"] is True
        assert figures[0]["names_declared"] == []

    def test_the_markdown_says_it_too(self, tmp_path):
        results = [figure_layout.FigureResult(path=tmp_path / "figures" / "quiet.tex", boxes={})]

        body = figure_layout.render_markdown(tmp_path / "s.md", results, "cmd")

        assert "names no node" in body
        assert "Nothing to report" not in body

    def test_a_stranded_arrowhead_reaches_the_text_and_the_findings(self, tmp_path):
        results = [
            figure_layout.FigureResult(
                path=tmp_path / "figures" / "flow.tex",
                stranded=["46,36"],
            )
        ]

        text = figure_layout.format_report(tmp_path / "s.md", results)
        findings = figure_layout.payload(tmp_path / "s.md", results, "cmd")["findings"]

        assert "46,36" in text
        assert findings == [
            {
                "figure": str(tmp_path / "figures" / "flow.tex"),
                "kind": "stranded-arrowhead",
                "at": "46,36",
            }
        ]

    def test_check_draft_finds_a_stranded_arrowhead_without_any_compile(
        self, tmp_path, monkeypatch
    ):
        def _no_tikz():
            raise figure_layout.MissingBinary("tikz.sty is not installed")

        monkeypatch.setattr(figure_layout, "_require_tikz", _no_tikz)
        draft = _draft_with_figure(
            tmp_path, "\\draw[->] (46,36) -- (46,44);\n\\draw[->] (46,32) -- (46,36);\n"
        )

        assert figure_layout.check_draft(draft)[0].stranded == ["46,36"]


class TestLoadsLibraryByHand:
    def test_a_plain_load_is_fine(self):
        assert figure_layout.loads_library_by_hand(r"\usetikzlibrary{positioning}") == []

    def test_clearing_the_loaded_flag(self):
        source = r"\expandafter\let\csname tikz@library@positioning@loaded\endcsname\relax"

        assert figure_layout.loads_library_by_hand(source) == ["tikz@library@positioning@loaded"]

    def test_touching_the_node_reset_hook(self):
        assert figure_layout.loads_library_by_hand(r"\let\savedhook\tikz@node@reset@hook") == [
            "tikz@node@reset@hook"
        ]

    def test_both_generations_in_one_file(self):
        source = "\\csname tikz@library@fit@loaded\\endcsname\n\\let\\s\\tikz@node@reset@hook\n"

        assert figure_layout.loads_library_by_hand(source) == [
            "tikz@library@fit@loaded",
            "tikz@node@reset@hook",
        ]

    def test_a_dotted_library_name(self):
        source = r"\csname tikz@library@arrows.meta@loaded\endcsname"

        assert figure_layout.loads_library_by_hand(source) == ["tikz@library@arrows.meta@loaded"]

    def test_a_repeat_is_named_once(self):
        source = "\\tikz@node@reset@hook\n\\tikz@node@reset@hook\n"

        assert figure_layout.loads_library_by_hand(source) == ["tikz@node@reset@hook"]

    def test_a_commented_out_workaround_is_not_flagged(self):
        assert figure_layout.loads_library_by_hand("% \\tikz@node@reset@hook") == []

    def test_it_counts_as_a_finding(self, tmp_path):
        result = figure_layout.FigureResult(
            path=tmp_path / "figures" / "flow.tex", by_hand=["tikz@node@reset@hook"]
        )

        assert result.has_findings

    def test_it_reaches_the_text_and_the_findings(self, tmp_path):
        results = [
            figure_layout.FigureResult(
                path=tmp_path / "figures" / "flow.tex",
                by_hand=["tikz@node@reset@hook"],
            )
        ]

        text = figure_layout.format_report(tmp_path / "s.md", results)
        findings = figure_layout.payload(tmp_path / "s.md", results, "cmd")["findings"]

        assert "tikz@node@reset@hook" in text
        assert "preamble" in text
        assert findings == [
            {
                "figure": str(tmp_path / "figures" / "flow.tex"),
                "kind": "loads-library-by-hand",
                "internal": "tikz@node@reset@hook",
            }
        ]

    def test_check_draft_finds_one_without_any_compile(self, tmp_path, monkeypatch):
        def _no_tikz():
            raise figure_layout.MissingBinary("tikz.sty is not installed")

        monkeypatch.setattr(figure_layout, "_require_tikz", _no_tikz)
        draft = _draft_with_figure(
            tmp_path, "\\let\\saved\\tikz@node@reset@hook\n\\node (a) {A};\n"
        )

        assert figure_layout.check_draft(draft)[0].by_hand == ["tikz@node@reset@hook"]


class TestReport:
    def test_a_clean_draft_says_so(self, tmp_path):
        draft = tmp_path / "survey.md"
        draft.write_text("No figures.\n", encoding="utf-8")

        text = figure_layout.format_report(draft, [])

        assert "no figures" in text.lower()

    def test_the_continuous_score_is_labelled_as_advisory(self, tmp_path):
        draft = tmp_path / "survey.md"
        result = figure_layout.FigureResult(
            path=tmp_path / "figures" / "flow.tex",
            declared=["a"],
            boxes={"a": (0.0, 0.0, 10.0, 10.0), figure_layout.BBOX_NAME: (0.0, 0.0, 20.0, 10.0)},
        )

        text = figure_layout.format_report(draft, [result])

        assert "human-read only" in text
        assert "50" in text

    def test_two_runs_over_an_unchanged_draft_are_byte_identical(self, tmp_path):
        draft = _draft_with_figure(tmp_path, "\\node (a) {A};\n\\draw (a) -- (b);\n")
        results = figure_layout.check_draft(draft)

        assert figure_layout.format_report(draft, results) == figure_layout.format_report(
            draft, results
        )

    def test_the_json_payload_carries_the_reviews_envelope(self, tmp_path, isolated_config):
        from chitragupta import config

        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("No figures.\n", encoding="utf-8")

        payload = figure_layout.payload(draft, [], "cmd")

        assert payload["aid"] == "figure"
        assert "notice" in payload and "version" in payload
        assert payload["findings"] == []


class TestCli:
    def test_it_exits_zero_even_with_findings(self, tmp_path, isolated_config, capsys):
        from chitragupta import config

        config.DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        words = " ".join(f"word{n}" for n in range(30))
        draft = _draft_with_figure(config.DRAFTS_DIR, f"\\node (a) {{{words}}};\n")

        code = figure_layout.main([str(draft)])

        assert code == 0
        assert "30 words" in capsys.readouterr().out

    def test_a_missing_draft_exits_one(self, tmp_path, isolated_config, capsys):
        code = figure_layout.main([str(tmp_path / "nope.md")])

        assert code == 1

    def test_json_prints_the_payload(self, isolated_config, capsys):
        from chitragupta import config

        config.DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        draft = _draft_with_figure(config.DRAFTS_DIR, "\\node (a) {A};\n")

        code = figure_layout.main([str(draft), "--json"])

        assert code == 0
        assert json.loads(capsys.readouterr().out)["aid"] == "figure"

    def test_write_files_the_report_and_its_json_sibling(self, isolated_config):
        from chitragupta import config

        config.DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        draft = _draft_with_figure(config.DRAFTS_DIR, "\\node (a) {A};\n")

        assert figure_layout.main([str(draft), "--write", "--formats", "md"]) == 0
        assert review.report_path(draft, "figure").exists()
        assert review.report_path(draft, "figure", "json").exists()

    def test_flags_hang_off_a_parser_the_entry_point_supplies(self):
        import argparse

        sub = argparse.ArgumentParser().add_subparsers().add_parser("figure")
        figure_layout.build_parser(sub)

        args = sub.parse_args(["draft.md", "--json"])

        assert args.draft == "draft.md" and args.json is True

    def test_the_recorded_command_carries_the_flags_used(self, tmp_path):
        command = figure_layout._command(tmp_path / "d.md", True, True)

        assert "--json" in command and "--write" in command


class TestMarkdownReport:
    def test_it_names_every_figure_it_checked(self, tmp_path):
        results = [figure_layout.FigureResult(path=tmp_path / "figures" / "flow.tex")]

        body = figure_layout.render_markdown(tmp_path / "s.md", results, "cmd")

        assert "flow.tex" in body
        assert "edge list" in body.lower()

    def test_a_draft_with_no_figures_says_so(self, tmp_path):
        body = figure_layout.render_markdown(tmp_path / "s.md", [], "cmd")

        assert "No figures found" in body

    def test_a_failed_compile_reaches_both_the_text_and_the_findings(self, tmp_path):
        results = [
            figure_layout.FigureResult(
                path=tmp_path / "figures" / "broken.tex",
                failed="! Missing $ inserted.",
            )
        ]

        text = figure_layout.format_report(tmp_path / "s.md", results)
        findings = figure_layout.payload(tmp_path / "s.md", results, "cmd")["findings"]

        assert "does not compile" in text
        assert [f["kind"] for f in findings] == ["does-not-compile"]

    def test_the_emptiness_proportion_is_never_a_finding(self, tmp_path):
        results = [
            figure_layout.FigureResult(
                path=tmp_path / "figures" / "flow.tex",
                declared=["a"],
                boxes={
                    "a": (0.0, 0.0, 5.0, 5.0),
                    figure_layout.BBOX_NAME: (0.0, 0.0, 100.0, 100.0),
                },
            )
        ]

        body = figure_layout.payload(tmp_path / "s.md", results, "cmd")

        assert body["figures"][0]["empty_fraction"] > 0.9
        assert not any("empt" in f["kind"] for f in body["findings"])

    def test_protrusion_and_overlap_do_become_findings(self, tmp_path):
        results = [
            figure_layout.FigureResult(
                path=tmp_path / "figures" / "flow.tex",
                declared=["a", "b"],
                boxes={
                    "a": (0.0, 0.0, 40.0, 10.0),
                    "b": (20.0, 0.0, 60.0, 10.0),
                    figure_layout.BBOX_NAME: (0.0, 0.0, 60.0, 300.0),
                },
            )
        ]

        kinds = {
            f["kind"] for f in figure_layout.payload(tmp_path / "s.md", results, "cmd")["findings"]
        }

        assert kinds == {"node-overlap", "content-protrusion"}

    def test_overlap_and_protrusion_are_named_in_the_printed_text(self, tmp_path):
        results = [
            figure_layout.FigureResult(
                path=tmp_path / "figures" / "flow.tex",
                declared=["a", "b"],
                boxes={
                    "a": (0.0, 0.0, 40.0, 10.0),
                    "b": (20.0, 0.0, 60.0, 10.0),
                    figure_layout.BBOX_NAME: (0.0, 0.0, 60.0, 300.0),
                },
            )
        ]

        text = figure_layout.format_report(tmp_path / "s.md", results)

        assert "overlap" in text
        assert "protrudes" in text

    def test_a_figure_with_nothing_to_say_gets_no_empty_heading(self, tmp_path):
        results = [figure_layout.FigureResult(path=tmp_path / "figures" / "quiet.tex")]

        text = figure_layout.format_report(tmp_path / "s.md", results)

        assert "quiet.tex" not in text
        assert "No layout findings" in text

    def test_the_markdown_still_names_a_figure_it_had_nothing_to_say_about(self, tmp_path):
        results = [figure_layout.FigureResult(path=tmp_path / "figures" / "quiet.tex")]

        body = figure_layout.render_markdown(tmp_path / "s.md", results, "cmd")

        assert "quiet.tex" in body
        assert "Nothing to report" in body

    def test_a_clean_figure_says_it_is_not_a_verdict(self, tmp_path):
        results = [
            figure_layout.FigureResult(
                path=tmp_path / "figures" / "flow.tex",
                declared=["a"],
                boxes={
                    "a": (0.0, 0.0, 10.0, 10.0),
                    figure_layout.BBOX_NAME: (0.0, 0.0, 11.0, 11.0),
                },
            )
        ]

        text = figure_layout.format_report(tmp_path / "s.md", results)

        assert "not a verdict" in text

    def test_a_skipped_host_is_reported_rather_than_silently_dropped(self, tmp_path):
        results = [
            figure_layout.FigureResult(
                path=tmp_path / "figures" / "flow.tex",
                skipped="tikz.sty is not installed",
            )
        ]

        text = figure_layout.format_report(tmp_path / "s.md", results)

        assert "geometry not checked" in text
        assert (
            figure_layout.payload(tmp_path / "s.md", results, "cmd")["figures"][0][
                "geometry_checked"
            ]
            is False
        )


class TestGeometryEdgeCases:
    def test_a_figure_with_no_nodes_at_all_does_not_protrude(self):
        assert figure_layout.protrudes({figure_layout.BBOX_NAME: (0.0, 0.0, 10.0, 10.0)}) is False

    def test_geometry_without_a_bounding_box_is_not_judged(self):
        boxes = {"a": (0.0, 0.0, 10.0, 10.0)}

        assert figure_layout.protrudes(boxes) is False
        assert figure_layout.emptiness(boxes) is None

    def test_a_zero_height_bounding_box_does_not_protrude(self):
        assert (
            figure_layout.protrudes(
                {
                    "a": (0.0, 0.0, 10.0, 0.0),
                    figure_layout.BBOX_NAME: (0.0, 0.0, 10.0, 0.0),
                }
            )
            is False
        )


class TestCompileErrorDetail:
    def test_it_reports_the_first_tex_error_line(self):
        log = "This is pdfTeX\n! Undefined control sequence.\n! Emergency stop.\n"

        assert figure_layout._probe._compile_error_detail(log) == "! Undefined control sequence."

    def test_a_failure_with_no_error_line_still_says_something(self):
        assert "without reporting" in figure_layout._probe._compile_error_detail("")


class TestBoxedScaffold:
    SOURCE = (
        "\\usetikzlibrary{positioning,fit}%\n\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}"
    )

    def test_the_default_scaffold_neither_preloads_nor_boxes(self):
        scaffold = figure_layout.scaffold(self.SOURCE, ["a"])

        preamble = scaffold.split("\\begin{document}")[0]
        assert "\\usetikzlibrary" not in preamble
        assert "CGWIDTH" not in scaffold and "cgfigbox" not in scaffold

    def test_a_boxed_scaffold_preloads_the_figures_own_libraries(self):
        scaffold = figure_layout.scaffold(self.SOURCE, ["a"], boxed=True)

        preamble = scaffold.split("\\begin{document}")[0]
        assert "\\usepackage{tikz}\n\\usetikzlibrary{positioning,fit}\n" in preamble

    def test_a_boxed_scaffold_of_a_figure_loading_nothing_loads_nothing(self):
        scaffold = figure_layout.scaffold("\\node (a) {A};", ["a"], boxed=True)

        assert "\\usetikzlibrary" not in scaffold

    def test_a_boxed_scaffold_reports_the_box_width_and_ships_the_box(self):
        scaffold = figure_layout.scaffold(self.SOURCE, ["a"], boxed=True)

        body = scaffold.split("\\begin{document}")[1]
        assert (
            body.index("\\setbox\\cgfigbox=\\hbox") < body.index("CGWIDTH") < body.index("\\usebox")
        )

    def test_the_box_width_parses_back(self):
        assert _probe.parse_input_width("x\nCGWIDTH 307.25pt\ny\n") == 307.25

    def test_a_log_without_a_box_width_has_none(self):
        assert _probe.parse_input_width("CGBOX a 0pt 0pt 1pt 1pt\n") is None


class TestCheckFigure:
    def test_a_skipped_host_runs_the_static_checks_only(self, tmp_path):
        path = tmp_path / "fig.tex"
        path.write_text("\\node (a) {A};\n\\draw (a) -- (b);\n", encoding="utf-8")

        result = figure_layout.check_figure(path, "no lualatex here")

        assert result.edges == [("a", "b")]
        assert result.declared == ["a"]
        assert result.boxes is None and result.input_width is None
        assert result.skipped == "no lualatex here"

    @pytest.mark.slow
    @needs_tikz
    def test_an_unboxed_check_measures_no_input_width(self, tmp_path):
        path = tmp_path / "fig.tex"
        path.write_text(
            "\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}%\n", encoding="utf-8"
        )

        result = figure_layout.check_figure(path, "")

        assert "a" in result.boxes and result.input_width is None

    @pytest.mark.slow
    @needs_tikz
    def test_a_tight_figures_box_is_as_wide_as_its_picture(self, tmp_path):
        path = tmp_path / "fig.tex"
        path.write_text(
            "\\usetikzlibrary{positioning}%\n"
            "\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}%\n",
            encoding="utf-8",
        )

        result = figure_layout.check_figure(path, "", boxed=True)

        x1, _, x2, _ = result.boxes[figure_layout.BBOX_NAME]
        assert result.input_width == pytest.approx(x2 - x1, abs=0.5)

    @pytest.mark.slow
    @needs_tikz
    def test_a_line_end_outside_the_picture_widens_the_box(self, tmp_path):
        path = tmp_path / "fig.tex"
        path.write_text(
            "\\newcommand{\\cgteststray}{}\n"
            "\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}%\n",
            encoding="utf-8",
        )

        result = figure_layout.check_figure(path, "", boxed=True)

        x1, _, x2, _ = result.boxes[figure_layout.BBOX_NAME]
        assert result.input_width > (x2 - x1) + 1.0

    @pytest.mark.slow
    @needs_tikz
    def test_a_line_end_after_the_picture_widens_the_box_too(self, tmp_path):
        path = tmp_path / "fig.tex"
        path.write_text("\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}\n", encoding="utf-8")

        result = figure_layout.check_figure(path, "", boxed=True)

        x1, _, x2, _ = result.boxes[figure_layout.BBOX_NAME]
        assert result.input_width > (x2 - x1) + 1.0

    @pytest.mark.slow
    @needs_tikz
    def test_a_matrix_compiles_inside_the_box(self, tmp_path):
        path = tmp_path / "fig.tex"
        path.write_text(
            "\\usetikzlibrary{matrix}%\n"
            "\\begin{tikzpicture}\n"
            "\\matrix[matrix of nodes] (m) { \\node (a) {A}; & \\node (b) {B}; \\\\ };\n"
            "\\end{tikzpicture}%\n",
            encoding="utf-8",
        )

        result = figure_layout.check_figure(path, "", boxed=True)

        assert result.failed is None and {"a", "b"} <= set(result.boxes)

    @pytest.mark.slow
    @needs_tikz
    def test_a_figure_that_does_not_compile_is_a_finding(self, tmp_path):
        path = tmp_path / "fig.tex"
        path.write_text("\\begin{tikzpicture}\n\\node (a) {\n", encoding="utf-8")

        result = figure_layout.check_figure(path, "", boxed=True)

        assert result.failed and result.boxes is None

    LOOP = (
        "\\begin{tikzpicture}\n"
        "\\foreach \\i in {1,2} { \\node (s\\i) at (\\i,0) {S}; }\n"
        "\\node (a) at (0,1) {A};\n"
        "\\end{tikzpicture}%\n"
    )

    @pytest.mark.slow
    @needs_tikz
    def test_a_loop_named_node_compiles_and_is_measured_from_what_tikz_drew(self, tmp_path):
        path = tmp_path / "fig.tex"
        path.write_text(self.LOOP, encoding="utf-8")

        result = figure_layout.check_figure(path, "", boxed=True)

        assert result.failed is None
        assert result.unmeasured == []
        assert result.declared == ["s1", "s2", "a"]

    @pytest.mark.slow
    @needs_tikz
    def test_without_the_hook_a_loop_named_node_is_reported_unmeasured(self, tmp_path):
        path = tmp_path / "fig.tex"
        path.write_text(self.LOOP, encoding="utf-8")

        result = figure_layout.check_figure(path, "")

        assert result.failed is None
        assert result.unmeasured == ["s\\i"]


class TestLeavesAndEdgeGap:
    def test_a_zone_is_not_a_leaf_and_its_children_are(self):
        boxes = {
            "zone": (0.0, 0.0, 100.0, 50.0),
            "a": (10.0, 10.0, 30.0, 20.0),
            "b": (50.0, 10.0, 70.0, 20.0),
            "far": (200.0, 0.0, 210.0, 10.0),
            figure_layout.BBOX_NAME: (0.0, 0.0, 210.0, 50.0),
        }

        assert sorted(figure_layout.leaves(boxes)) == ["a", "b", "far"]

    def test_two_nodes_side_by_side_are_both_leaves(self):
        boxes = {"a": (0.0, 0.0, 10.0, 10.0), "b": (10.0, 0.0, 20.0, 10.0)}

        assert sorted(figure_layout.leaves(boxes)) == ["a", "b"]

    def test_the_gap_is_edge_to_edge_along_one_axis(self):
        assert figure_layout.edge_gap((0.0, 0.0, 10.0, 10.0), (14.0, 2.0, 24.0, 8.0)) == 4.0

    def test_a_diagonal_gap_is_the_corner_to_corner_distance(self):
        gap = figure_layout.edge_gap((0.0, 0.0, 10.0, 10.0), (13.0, 14.0, 20.0, 20.0))

        assert gap == pytest.approx(5.0)

    def test_touching_boxes_are_zero_apart(self):
        assert figure_layout.edge_gap((0.0, 0.0, 10.0, 10.0), (10.0, 0.0, 20.0, 10.0)) == 0.0

    @pytest.mark.parametrize(
        "other",
        [
            (5.0, 5.0, 15.0, 15.0),  # intersects: node-overlap's to report
            (2.0, 2.0, 8.0, 8.0),  # inside: a zone and its child
            (20.0, 5.0, 20.0, 5.0),  # a coordinate: a point, not a node
        ],
        ids=["intersecting", "enclosed", "zero-area"],
    )
    def test_there_is_no_gap_to_measure(self, other):
        assert figure_layout.edge_gap((0.0, 0.0, 10.0, 10.0), other) is None


class TestAmbiguousEdges:
    def test_an_edge_chain_is_ambiguous(self):
        source = "\\draw (hub) edge (s1) edge (s2);\n"

        assert figure_layout.ambiguous_edges(source) == [("hub", "s1"), ("s1", "s2")]

    @pytest.mark.parametrize(
        "label", ["node[midway, above] (l) {x}", "node (l) {x}", "node (l) [above] {x}"]
    )
    def test_a_named_node_on_a_path_is_ambiguous(self, label):
        source = f"\\draw (a) -- {label} (b);\n"

        assert figure_layout.ambiguous_edges(source) == [("a", "l"), ("l", "b")]

    @pytest.mark.parametrize(
        "source",
        [
            "\\draw[cgedge] (a) -- (b);\n",
            "\\draw (a) -- node[above] {f(x)} (b);\n",
            "\\node (a) {A};\n\\node (b) [right=of a] {B};\n\\draw (a) -- (b);\n",
        ],
        ids=["house-edge-style", "unnamed-label", "node-statements"],
    )
    def test_a_plain_path_is_not(self, source):
        assert figure_layout.ambiguous_edges(source) == []

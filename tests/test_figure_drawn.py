"""The lines and nodes `figure check`'s probe reports from TeX (#1054).

`assets/latex/cg-figure-probe.tex` logs what TikZ drew; `parse_drawn`
reads it. The parse tests feed the log grammar directly, so they run
without TeX; the ones marked `needs_tikz` compile a real figure.
"""

import pytest

from chitragupta.review import figure_layout
from chitragupta.review.figure_layout._drawn import parse_drawn
from chitragupta.review.figure_layout._paint import Paint, TextRun
from tests.conftest import needs_tikz


def _log(*lines: str) -> str:
    return "\n".join(lines) + "\n"


class TestParse:
    def test_a_straight_line_parses_with_its_tips(self):
        drawn = parse_drawn(
            _log(
                "CGPATH 1 E 0 1 draw,",
                "CGSEG 1 M 0.0 0.0",
                "CGSEG 1 L 10.0 0.0",
            )
        )

        (line,) = drawn.lines
        assert line.points == ((0.0, 0.0), (10.0, 0.0))
        assert (line.start_tip, line.end_tip, line.curved) == (False, True, False)

    def test_a_curve_is_flattened_and_marked_curved(self):
        drawn = parse_drawn(
            _log(
                "CGPATH 1 E 0 0 draw,",
                "CGSEG 1 M 0.0 0.0",
                "CGSEG 1 C 0.0 10.0",
                "CGSEG 1 C 10.0 10.0",
                "CGSEG 1 C 10.0 0.0",
            )
        )

        (line,) = drawn.lines
        assert line.curved
        assert line.points[0] == (0.0, 0.0) and line.points[-1] == (10.0, 0.0)
        assert len(line.points) > 4
        assert max(y for _, y in line.points) == pytest.approx(7.5)

    def test_a_node_frame_is_not_a_line(self):
        drawn = parse_drawn(
            _log(
                "CGNODE 0.0pt 0.0pt 0.0pt rectangle/a",
                "CGPATH 1 N 0 0 fill,draw,",
                "CGSEG 1 R -5.0 -5.0",
                "CGSEG 1 S 10.0 10.0",
            )
        )

        assert drawn.lines == []

    def test_a_rectangle_in_a_drawn_path_is_not_a_line(self):
        """`\\draw (0,0) rectangle (1,1)` is a frame or a zone, never a
        connector."""
        drawn = parse_drawn(
            _log("CGPATH 1 E 0 0 draw,", "CGSEG 1 R 0.0 0.0", "CGSEG 1 S 10.0 10.0")
        )

        assert drawn.lines == []

    def test_a_path_that_is_not_stroked_is_not_a_line(self):
        drawn = parse_drawn(_log("CGPATH 1 E 0 0 fill,", "CGSEG 1 M 0.0 0.0", "CGSEG 1 L 10.0 0.0"))

        assert drawn.lines == []

    def test_each_subpath_is_its_own_line_with_the_tips_at_the_ends(self):
        """pgf draws a path's start tip on its first subpath and its end
        tip on its last."""
        drawn = parse_drawn(
            _log(
                "CGPATH 1 E 1 1 draw,",
                "CGSEG 1 M 0.0 0.0",
                "CGSEG 1 L 10.0 0.0",
                "CGSEG 1 M 0.0 5.0",
                "CGSEG 1 L 10.0 5.0",
            )
        )

        first, last = drawn.lines
        assert (first.start_tip, first.end_tip) == (True, False)
        assert (last.start_tip, last.end_tip) == (False, True)

    def test_a_closed_path_returns_to_its_start(self):
        drawn = parse_drawn(
            _log(
                "CGPATH 1 E 0 0 draw,",
                "CGSEG 1 M 0.0 0.0",
                "CGSEG 1 L 10.0 0.0",
                "CGSEG 1 L 10.0 10.0",
                "CGSEG 1 Z 0.0 0.0",
            )
        )

        assert drawn.lines[0].points[-1] == (0.0, 0.0)

    def test_nodes_logged_before_a_path_are_its_labels(self):
        drawn = parse_drawn(
            _log(
                "CGNODE 10.0pt 5.0pt 1.0pt rectangle/cgu-1",
                "CGPATH 1 N 0 0 fill,",
                "CGPATH 2 E 0 1 draw,",
                "CGSEG 2 M 0.0 0.0",
                "CGSEG 2 L 40.0 0.0",
            )
        )

        assert drawn.lines[0].labels == ("cgu-1",)

    def test_a_standalone_node_is_no_ones_label(self):
        """A `\\node` statement is a path of its own, empty, which
        consumes it; the `\\draw` after it gets no label."""
        drawn = parse_drawn(
            _log(
                "CGNODE 10.0pt 5.0pt 1.0pt rectangle/a",
                "CGPATH 1 E 0 0 ",
                "CGPATH 2 E 0 1 draw,",
                "CGSEG 2 M 0.0 0.0",
                "CGSEG 2 L 40.0 0.0",
            )
        )

        assert drawn.lines[0].labels == ()

    def test_a_text_box_comes_from_the_text_anchor(self):
        """A label with neither fill nor draw has no frame to read, so
        its text box comes from where TikZ set the text: the `text`
        anchor, at the left end of the baseline."""
        drawn = parse_drawn(
            _log(
                "CGNODE 20.0pt 6.0pt 2.0pt rectangle/cgu-1",
                "CGNB -3.0 -5.0 23.0 9.0 0.0 0.0 0.0 0.0 cgu-1",
            )
        )

        node = drawn.nodes["cgu-1"]
        assert node.shape == "rectangle"
        assert node.box == (-3.0, -5.0, 23.0, 9.0)
        assert node.text_box == (0.0, -2.0, 20.0, 6.0)

    def test_a_shape_with_no_text_anchor_has_no_text_box(self):
        drawn = parse_drawn(
            _log("CGNODE 0.0pt 0.0pt 0.0pt coordinate/p", "CGNB 1.0 2.0 1.0 2.0 - - 0.0 0.0 p")
        )

        assert drawn.nodes["p"].text_box is None

    @pytest.mark.parametrize(
        ("turn", "text_box"),
        [("1.0 -1.0", (-6.0, 0.0, 2.0, 20.0)), ("-1.0 1.0", (-2.0, -20.0, 6.0, 0.0))],
    )
    def test_a_quarter_turned_text_box_is_turned_about_its_anchor(self, turn, text_box):
        """`rotate=90` reads bottom to top and `rotate=-90` top to bottom;
        both are measured, and neither is set aside (#1064)."""
        drawn = parse_drawn(
            _log(
                "CGNODE 20.0pt 6.0pt 2.0pt rectangle/e3-n",
                f"CGNB -7.0 -1.0 3.0 21.0 0.0 0.0 {turn} e3-n",
            )
        )

        node = drawn.nodes["e3-n"]
        assert node.rotated is False
        assert node.text_box == text_box

    @pytest.mark.parametrize("turn", ["0.70711 -0.70711", "2.0 -2.0"])
    def test_a_slanted_or_scaled_turn_is_still_set_aside(self, turn):
        drawn = parse_drawn(
            _log("CGNODE 20.0pt 6.0pt 2.0pt rectangle/t", f"CGNB 0 0 10 10 0.0 0.0 {turn} t")
        )

        assert drawn.nodes["t"].rotated is True

    def test_no_hook_lines_is_none(self):
        assert parse_drawn("CGBOX a 0.0pt 0.0pt 1.0pt 1.0pt\n") is None


class TestScaffold:
    def test_the_boxed_probe_carries_the_hook(self):
        scaffold = figure_layout.scaffold("\\node (a) {A};", ["a"], boxed=True)

        assert "\\cgdumpnodes" in scaffold
        assert "\\let\\cgoldusepath\\pgfusepath" in scaffold

    def test_the_unboxed_probe_carries_no_hook(self):
        """`review figure`'s compile is not instrumented: wrapping two
        pgf internals is `figure check`'s risk to carry, not its."""
        scaffold = figure_layout.scaffold("\\node (a) {A};", ["a"])

        assert "\\cgdumpnodes" not in scaffold
        assert "cgoldusepath" not in scaffold


class TestColours:
    """`CGPAINT`, `CGTEXT` and `CGTEXTCOLOR` (#1055), `_paint.py`'s."""

    def test_a_line_carries_what_it_was_stroked_in(self):
        drawn = parse_drawn(
            _log(
                "CGPAINT 1 0.3,0.7,0.9 0,0,0 cgAux|",
                "CGPATH 1 E 0 1 draw,",
                "CGSEG 1 M 0.0 0.0",
                "CGSEG 1 L 10.0 0.0",
            )
        )

        (line,) = drawn.lines
        assert line.stroke == Paint((0.3, 0.7, 0.9), "cgAux")

    def test_a_frame_gives_its_node_both_colours(self):
        drawn = parse_drawn(
            _log(
                "CGNODE 0.0pt 0.0pt 0.0pt rectangle/a",
                "CGPAINT 1 0.3,0.7,0.9 0.9,0.9,0.9 cgAux|cgAux!10",
                "CGPATH 1 N 0 0 fill,draw,",
                "CGNB 0 0 10 10 - - 0 0 a",
            )
        )

        node = drawn.nodes["a"]
        assert node.stroke == Paint((0.3, 0.7, 0.9), "cgAux")
        assert node.fill == Paint((0.9, 0.9, 0.9), "cgAux!10")

    def test_the_last_painted_node_path_is_the_frame(self):
        """`cgsoft`'s shadow paths come first, in greys."""
        drawn = parse_drawn(
            _log(
                "CGNODE 0.0pt 0.0pt 0.0pt rectangle/a",
                "CGPAINT 1 0.2,0.2,0.2 0.2,0.2,0.2 cgFlowLine|cgFlow!7",
                "CGPATH 1 N 0 0 fill",
                "CGPAINT 2 0,0.4,0.7 0.9,0.96,0.98 cgFlowLine|cgFlow!7",
                "CGPATH 2 N 0 0 fill,draw,",
                "CGNB 0 0 10 10 - - 0 0 a",
            )
        )

        assert drawn.nodes["a"].fill.colour == (0.9, 0.96, 0.98)

    def test_a_frame_only_drawn_has_no_fill(self):
        drawn = parse_drawn(
            _log(
                "CGNODE 0.0pt 0.0pt 0.0pt rectangle/a",
                "CGPAINT 1 0,0,0 0,0,0 |",
                "CGPATH 1 N 0 0 draw,",
                "CGNB 0 0 10 10 - - 0 0 a",
            )
        )

        node = drawn.nodes["a"]
        assert (node.stroke, node.fill) == (Paint((0.0, 0.0, 0.0), ""), None)

    def test_a_frame_only_filled_has_no_stroke(self):
        drawn = parse_drawn(
            _log(
                "CGNODE 0.0pt 0.0pt 0.0pt rectangle/a",
                "CGPAINT 1 0,0,0 1,1,1 |white",
                "CGPATH 1 N 0 0 fill,",
                "CGNB 0 0 10 10 - - 0 0 a",
            )
        )

        assert drawn.nodes["a"].stroke is None

    def test_an_unframed_node_has_no_colours(self):
        drawn = parse_drawn(
            _log("CGNODE 0.0pt 0.0pt 0.0pt rectangle/a", "CGNB 0 0 10 10 - - 0 0 a")
        )

        assert (drawn.nodes["a"].stroke, drawn.nodes["a"].fill) == (None, None)

    def test_a_log_without_paint_leaves_a_frame_uncoloured(self):
        """#1054's grammar alone, as a fixture written before #1055."""
        drawn = parse_drawn(
            _log(
                "CGNODE 0.0pt 0.0pt 0.0pt rectangle/a",
                "CGPATH 1 N 0 0 fill,draw,",
                "CGNB 0 0 10 10 - - 0 0 a",
            )
        )

        assert drawn.nodes["a"].fill is None and drawn.nodes["a"].framed

    def test_text_runs_and_the_text_key_reach_their_node(self):
        """A name with a space survives: it comes last."""
        drawn = parse_drawn(
            _log(
                "CGTEXT 0.1,0.1,0.1 12.00 1 12 data store",
                "CGTEXT 0.4,0.4,0.4 12.00 0 9 data store",
                "CGTEXTCOLOR cgInk|data store",
                "CGNODE 0.0pt 0.0pt 0.0pt rectangle/data store",
                "CGNB 0 0 10 10 - - 0 0 data store",
            )
        )

        node = drawn.nodes["data store"]
        assert node.runs == (
            TextRun((0.1, 0.1, 0.1), 12.0, True, 12),
            TextRun((0.4, 0.4, 0.4), 12.0, False, 9),
        )
        assert node.text_written == "cgInk"


@needs_tikz
class TestAgainstRealLualatex:
    def test_the_boxed_probe_reports_drawn_lines(self, tmp_path):
        """An elbow from `a`'s top to `b`'s left, with a tag: the end
        TikZ computed comes back exact, and the tag is the line's."""
        path = tmp_path / "fig.tex"
        path.write_text(
            "\\begin{tikzpicture}\n"
            "\\node[draw] (a) at (0,0) {A};\n"
            "\\node[draw] (b) at (3,2) {B};\n"
            "\\draw[->] (a.north) |- node[above,pos=0.75] {go} (b.west);\n"
            "\\end{tikzpicture}%\n",
            encoding="utf-8",
        )

        drawn = figure_layout.check_figure(path, "", boxed=True).drawn

        (line,) = drawn.lines
        a, b = drawn.nodes["a"].box, drawn.nodes["b"].box
        assert line.points[0] == pytest.approx(((a[0] + a[2]) / 2, a[3]), abs=0.01)
        assert line.points[-1] == pytest.approx((b[0], (b[1] + b[3]) / 2), abs=0.01)
        assert len(line.points) == 3 and line.end_tip and not line.start_tip
        (label,) = line.labels
        assert drawn.nodes[label].text_box is not None

    def test_a_loop_drawn_edge_is_reported_once_per_pass(self, tmp_path):
        path = tmp_path / "fig.tex"
        path.write_text(
            "\\begin{tikzpicture}\n"
            "\\foreach \\i in {1,2,3} {\n"
            "  \\node[draw] (s\\i) at (\\i*2,0) {S};\n"
            "  \\node[draw] (t\\i) at (\\i*2,-2) {T};\n"
            "  \\draw[->] (s\\i) -- (t\\i);\n"
            "}\n"
            "\\end{tikzpicture}%\n",
            encoding="utf-8",
        )

        drawn = figure_layout.check_figure(path, "", boxed=True).drawn

        assert len(drawn.lines) == 3
        assert {"s1", "s2", "s3", "t1", "t2", "t3"} <= set(drawn.nodes)

    def test_review_figures_compile_reports_no_drawn_lines(self, tmp_path):
        path = tmp_path / "fig.tex"
        path.write_text(
            "\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}%\n", encoding="utf-8"
        )

        assert figure_layout.check_figure(path, "").drawn is None


class TestVisibilityAndRotation:
    """What the connector rules need to know about a node beyond its box
    (#1054's bench): whether a reader can see it, and whether it is
    turned."""

    def test_a_node_with_a_drawn_frame_is_framed(self):
        drawn = parse_drawn(
            _log(
                "CGNODE 0.0pt 0.0pt 0.0pt rectangle/a",
                "CGPATH 1 N 0 0 draw,",
                "CGSEG 1 R 0.0 0.0",
                "CGSEG 1 S 10.0 10.0",
                "CGNB 0.0 0.0 10.0 10.0 - - 0.0 0.0 a",
            )
        )

        assert drawn.nodes["a"].framed

    def test_text_alone_is_not_a_frame(self):
        drawn = parse_drawn(
            _log("CGNODE 8.0pt 5.0pt 1.0pt rectangle/a", "CGNB 0.0 0.0 10.0 10.0 1.0 2.0 0.0 0.0 a")
        )

        assert not drawn.nodes["a"].framed

    def test_a_fit_node_with_no_frame_is_unframed(self):
        drawn = parse_drawn(
            _log(
                "CGNODE 0.0pt 0.0pt 0.0pt rectangle/zone",
                "CGPATH 1 N 0 0 ",
                "CGNB 0.0 0.0 90.0 30.0 - - 0.0 0.0 zone",
            )
        )

        assert not drawn.nodes["zone"].framed

    def test_a_frame_belongs_only_to_the_node_it_was_drawn_for(self):
        drawn = parse_drawn(
            _log(
                "CGNODE 0.0pt 0.0pt 0.0pt rectangle/a",
                "CGPATH 1 N 0 0 fill,",
                "CGPATH 2 E 0 0 ",
                "CGNODE 0.0pt 0.0pt 0.0pt rectangle/b",
                "CGNB 0.0 0.0 1.0 1.0 - - 0.0 0.0 a",
                "CGNB 0.0 0.0 1.0 1.0 - - 0.0 0.0 b",
            )
        )

        assert drawn.nodes["a"].framed and not drawn.nodes["b"].framed

    def test_a_turned_node_is_rotated(self):
        drawn = parse_drawn(
            _log(
                "CGNODE 8.0pt 5.0pt 1.0pt rectangle/t",
                "CGNB 0.0 0.0 1.0 1.0 0.0 0.0 0.70711 -0.70711 t",
            )
        )

        assert drawn.nodes["t"].rotated


@needs_tikz
class TestVisibilityAndRotationAgainstRealLualatex:
    def test_a_sloped_tag_is_rotated_and_a_bare_fit_is_unframed(self, tmp_path):
        path = tmp_path / "fig.tex"
        path.write_text(
            "\\usetikzlibrary{fit}%\n"
            "\\begin{tikzpicture}\n"
            "\\node[draw] (a) at (0,0) {A};\n"
            "\\node[draw] (b) at (3,2) {B};\n"
            "\\draw (a) -- node[sloped,above] {up} (b);\n"
            "\\node[fit=(a)(b),draw=none] (group) {};\n"
            "\\end{tikzpicture}%\n",
            encoding="utf-8",
        )

        drawn = figure_layout.check_figure(path, "", boxed=True).drawn

        (tag,) = drawn.lines[0].labels
        assert drawn.nodes[tag].rotated and not drawn.nodes["a"].rotated
        assert drawn.nodes["a"].framed and not drawn.nodes["group"].framed


class TestNamesWithSpaces:
    """Fable review, #1054: a shape or node name with a space in it
    (`circle split`, `regular polygon`, `(data store)`) shifted every
    field after it, and `figure check` crashed. Names now come last."""

    def test_a_shape_name_with_a_space_parses(self):
        drawn = parse_drawn(
            _log(
                "CGNODE 8.0pt 5.0pt 1.0pt circle split/a",
                "CGNB 0.0 0.0 10.0 10.0 1.0 2.0 0.0 0.0 a",
            )
        )

        assert drawn.nodes["a"].shape == "circle split"

    def test_a_node_name_with_a_space_parses(self):
        drawn = parse_drawn(
            _log(
                "CGNODE 8.0pt 5.0pt 1.0pt rectangle/data store",
                "CGNB 0.0 0.0 10.0 10.0 - - 0.0 0.0 data store",
            )
        )

        assert drawn.nodes["data store"].box == (0.0, 0.0, 10.0, 10.0)


@needs_tikz
def test_spaced_shape_and_node_names_compile_and_measure(tmp_path):
    path = tmp_path / "fig.tex"
    path.write_text(
        "\\usetikzlibrary{shapes.multipart,shapes.geometric}%\n"
        "\\begin{tikzpicture}\n"
        "\\node[draw,circle split] (a) at (0,0) {A \\nodepart{lower} B};\n"
        "\\node[draw,regular polygon,regular polygon sides=5] (p) at (3,0) {P};\n"
        "\\node[draw] (data store) at (6,0) {D};\n"
        "\\draw[->] (a) -- (p);\n"
        "\\draw[->] (p) -- (data store);\n"
        "\\end{tikzpicture}%\n",
        encoding="utf-8",
    )

    drawn = figure_layout.check_figure(path, "", boxed=True).drawn

    assert drawn.nodes["a"].shape == "circle split"
    assert drawn.nodes["p"].shape == "regular polygon"
    assert "data store" in drawn.nodes and len(drawn.lines) == 2

    def test_the_probe_reports_colours_as_xcolor_resolves_them(self, tmp_path):
        """#1055. pgf's own stroke colour goes stale under `[draw, red]`,
        so the frame must come out red; the text's runs must see
        `text=`, `\\textcolor` inside a macro, and `\\textbf`."""
        path = tmp_path / "fig.tex"
        path.write_text(
            "\\definecolor{hot}{HTML}{D55E00}%\n"
            "\\newcommand{\\warm}[1]{\\textcolor{hot}{#1}}%\n"
            "\\begin{tikzpicture}\n"
            "\\node[fill=hot!10, text=hot, draw=blue] (a) at (0,0) {ab};\n"
            "\\node[draw, red] (b) at (3,0) {x \\warm{yz} \\textbf{w}};\n"
            "\\draw[->, draw=hot] (a) -- (b);\n"
            "\\end{tikzpicture}%\n",
            encoding="utf-8",
        )

        drawn = figure_layout.check_figure(path, "", boxed=True).drawn

        a, b = drawn.nodes["a"], drawn.nodes["b"]
        assert a.fill.written == "hot!10"
        assert a.fill.colour == pytest.approx((0.98353, 0.93686, 0.9), abs=1e-3)
        assert (a.stroke.colour, a.text_written) == ((0.0, 0.0, 1.0), "hot")
        assert [run.colour for run in a.runs] == [pytest.approx((0.8353, 0.36864, 0.0), abs=1e-3)]
        assert b.stroke.colour == (1.0, 0.0, 0.0) and b.fill is None
        hot = [run for run in b.runs if run.colour[1] > 0.3 and run.colour[0] < 0.9]
        assert [(run.glyphs, run.bold) for run in hot] == [(2, False)]
        assert any(run.bold and run.colour == (1.0, 0.0, 0.0) for run in b.runs)
        assert {run.size_pt for run in b.runs} == {12.0}
        (line,) = drawn.lines
        assert line.stroke.written == "hot"

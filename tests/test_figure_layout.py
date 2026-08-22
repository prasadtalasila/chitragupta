"""chitragupta/review/figure_layout.py: the deterministic TikZ layout check.

The fourth review-layer aid (#314, docs/FEATURE-ROADMAP.md's D2, planned
in plans/d2-tikz-layout-check.md). Advisory like the other three: it
reports and never blocks, and exits 0 whatever it finds.

Two kinds of test here, and the split is the module's own:

- **Static checks** -- node text length and the edge list -- parse the
  figure's own source and need no toolchain at all, so those tests run
  everywhere.
- **Geometry checks** -- overlap, protrusion, corner emptiness -- need a
  real `pdflatex` with `tikz.sty`, and are marked to self-skip without
  one. They are the reason the plan says "reproduce the probe before
  writing code": the `CGBOX` line format those tests pin is the single
  assumption the whole aid rests on, so it is pinned against a real
  compile rather than a fixture.
"""

import shutil
import subprocess

import pytest

from chitragupta.review import figure_layout


def _has_tikz() -> bool:
    """Whether this host can compile a TikZ figure at all.

    The same two facts `render_output/_figures.py::_require_tikz()`
    checks, asked here as a boolean so the geometry tests can skip
    rather than fail on a host without TeX Live -- CI's Windows leg
    installs no `os-deps`, and the render tests there already self-skip
    for exactly this reason.
    """
    if shutil.which("pdflatex") is None or shutil.which("kpsewhich") is None:
        return False
    probe = subprocess.run(["kpsewhich", "tikz.sty"], capture_output=True, check=False)
    return probe.returncode == 0


needs_tikz = pytest.mark.skipif(not _has_tikz(), reason="needs pdflatex with tikz.sty")


class TestFiguresIn:
    """Which figure files a draft actually references.

    Deliberately not a second parser: this reuses
    `render_output/_figures.py`'s `_figure_refs()`/`_resolve_sibling()`,
    which already own the `figure:` marker and `\\input{...}`
    conventions for the renderer. These tests pin that the reuse is
    wired up right, not that those functions work -- that is
    tests/test_render_output_figures.py's job.
    """

    def test_finds_a_markdown_drafts_marked_figure(self, tmp_path):
        (tmp_path / "figures").mkdir()
        figure = tmp_path / "figures" / "flow.tex"
        figure.write_text("\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}\n",
                          encoding="utf-8")
        draft = tmp_path / "survey.md"
        draft.write_text("Text.\n\n<!-- figure: figures/flow -->\n\nMore.\n",
                         encoding="utf-8")

        assert figure_layout.figures_in(draft) == [figure]

    def test_drops_a_marker_naming_a_file_that_is_not_there(self, tmp_path):
        """A dangling marker is `render_output`'s finding to report, not
        this aid's to crash on -- there is nothing to check the geometry
        of."""
        draft = tmp_path / "survey.md"
        draft.write_text("<!-- figure: figures/missing -->\n", encoding="utf-8")

        assert figure_layout.figures_in(draft) == []

    def test_finds_a_tex_fragments_real_input(self, tmp_path):
        """`thesis-chapter-writer`'s fragment keeps its TikZ inline via a
        real `\\input`, not a marker -- the one genre that differs, and
        the aid has to see its figures too."""
        (tmp_path / "figures").mkdir()
        figure = tmp_path / "figures" / "arch.tex"
        figure.write_text("\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}\n",
                          encoding="utf-8")
        draft = tmp_path / "chapter.tex"
        draft.write_text("\\input{figures/arch.tex}\n%figure: figures/arch\n",
                         encoding="utf-8")

        assert figure_layout.figures_in(draft) == [figure]

    def test_a_draft_with_no_figures_yields_nothing(self, tmp_path):
        draft = tmp_path / "survey.md"
        draft.write_text("Prose only, no figure at all.\n", encoding="utf-8")

        assert figure_layout.figures_in(draft) == []


class TestNodeText:
    """docs/TIKZ-STYLE.md's conciseness rule, as arithmetic: a node whose
    label runs past 15 words is too long for a box.

    No `pdflatex` anywhere in this class -- word count is a property of
    the source, so this check runs on a host with no TeX at all.
    """

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
        """The rule is "past about fifteen", so fifteen itself passes --
        pinned because an off-by-one here is invisible in prose."""
        words = " ".join(f"word{n}" for n in range(15))
        source = f"\\begin{{tikzpicture}}\\node (a) {{{words}}};\\end{{tikzpicture}}"

        assert figure_layout.overlong_nodes(source) == []

    def test_a_styled_node_still_parses(self):
        """`\\node[draw, fill=blue!10] (a) at (0,0) {...}` is the ordinary
        shape a real figure uses, not the bare `\\node (a) {...}`."""
        words = " ".join(f"word{n}" for n in range(20))
        source = f"\\node[draw, fill=blue!10] (a) at (0,0) {{{words}}};"

        assert [name for name, _ in figure_layout.overlong_nodes(source)] == ["a"]

    def test_latex_markup_in_a_label_is_not_counted_as_words(self):
        """`\\textbf{x}` is one word to a reader; counting the control
        sequence separately would flag figures that are actually fine."""
        source = "\\node (a) {\\textbf{alpha} \\emph{beta} gamma};"

        assert figure_layout.overlong_nodes(source) == []


class TestEdgeList:
    """The faithfulness check: what the figure claims connects to what.

    Reported for a human to confirm against the prose, never judged --
    nothing here knows which edges *should* exist.
    """

    def test_a_three_node_chain(self):
        source = "\\draw (a) -- (b) -- (c);"

        assert figure_layout.edge_list(source) == [("a", "b"), ("b", "c")]

    def test_separate_draw_statements(self):
        source = "\\draw (a) -- (b);\n\\draw (b) -- (c);\n"

        assert figure_layout.edge_list(source) == [("a", "b"), ("b", "c")]

    def test_an_arrow_is_an_edge_like_any_other(self):
        """`->` vs `--` is a rendering difference; both are the same
        claim about what connects to what."""
        source = "\\draw[->] (a) -- (b);"

        assert figure_layout.edge_list(source) == [("a", "b")]

    def test_bare_coordinates_are_not_nodes(self):
        """`\\draw (0,0) -- (2,0);` is a line, not an edge between two
        named things -- reporting `0,0 -> 2,0` would be noise."""
        source = "\\draw (0,0) -- (2,0);"

        assert figure_layout.edge_list(source) == []

    def test_a_path_statement_counts_too(self):
        source = "\\path (a) edge (b);"

        assert figure_layout.edge_list(source) == [("a", "b")]

    def test_a_figure_with_no_edges(self):
        source = "\\node (a) {A};\n\\node (b) {B};\n"

        assert figure_layout.edge_list(source) == []


class TestScaffold:
    """The document each figure is compiled inside.

    Two properties are load-bearing and both are asserted rather than
    left to a reader of the emitted string: it is `article`-based, and
    it reads coordinates through pgf's public accessor.
    """

    def test_it_is_article_not_standalone(self):
        """`standalone.cls` is texlive-latex-extra; `tikz.sty` is
        texlive-pictures. Building on standalone would depend on a
        package `_require_tikz()` never checks -- the exact bug #226
        was."""
        scaffold = figure_layout.scaffold("\\node (a) {A};", ["a"])

        assert "\\documentclass{article}" in scaffold
        assert "standalone" not in scaffold

    def test_it_uses_the_public_coordinate_accessor(self):
        """Raw `\\pgf@x` needs `\\makeatletter`, and without it degrades
        to literal text plus 'Undefined control sequence' while still
        exiting 0 -- a silent wrong answer, which is worse than a loud
        one."""
        scaffold = figure_layout.scaffold("\\node (a) {A};", ["a"])

        assert "\\pgfgetlastxy" in scaffold
        assert "\\pgf@x" not in scaffold

    def test_it_probes_the_pictures_own_bounding_box(self):
        """Protrusion and corner emptiness both need the picture-wide
        box, which is TikZ's `current bounding box` pseudo-node."""
        scaffold = figure_layout.scaffold("\\node (a) {A};", ["a"])

        assert "current bounding box" in scaffold


@needs_tikz
class TestProbeAgainstRealPdflatex:
    """The one assumption everything else rests on, pinned against a real
    compile rather than a fixture -- plans/d2-tikz-layout-check.md's own
    instruction, and what caught the `standalone`/`\\makeatletter`
    problems in the first place.
    """

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

    def test_the_picture_bounding_box_is_reported_too(self, tmp_path):
        figure = tmp_path / "fig.tex"
        figure.write_text(
            "\\begin{tikzpicture}\n\\node (a) at (0,0) {A};\n\\end{tikzpicture}\n",
            encoding="utf-8",
        )

        boxes = figure_layout.node_boxes(figure)

        assert figure_layout.BBOX_NAME in boxes

    def test_compiling_does_not_litter_beside_the_figure(self, tmp_path):
        """A review aid that leaves .aux/.log/.pdf files next to a
        user's draft is a bug, not a side effect worth having."""
        figure = tmp_path / "fig.tex"
        figure.write_text(
            "\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}\n", encoding="utf-8"
        )

        figure_layout.node_boxes(figure)

        assert sorted(p.name for p in tmp_path.iterdir()) == ["fig.tex"]

    def test_a_figure_that_does_not_compile_raises_rather_than_returning_junk(
        self, tmp_path
    ):
        figure = tmp_path / "broken.tex"
        figure.write_text("\\begin{tikzpicture}\n\\node (a) {\n", encoding="utf-8")

        with pytest.raises(figure_layout.FigureCompileError):
            figure_layout.node_boxes(figure)


class TestOverlap:
    """Pairwise box intersection. Pure arithmetic over parsed boxes, so
    no compile is needed to test the rule itself."""

    def test_overlapping_boxes_are_reported(self):
        boxes = {"a": (0.0, 0.0, 40.0, 10.0), "b": (20.0, 0.0, 60.0, 10.0)}

        assert figure_layout.overlaps(boxes) == [("a", "b")]

    def test_spaced_boxes_are_not(self):
        boxes = {"a": (0.0, 0.0, 10.0, 10.0), "b": (50.0, 0.0, 60.0, 10.0)}

        assert figure_layout.overlaps(boxes) == []

    def test_boxes_that_only_touch_are_not_overlapping(self):
        """Edge-to-edge is a design choice, not a collision."""
        boxes = {"a": (0.0, 0.0, 10.0, 10.0), "b": (10.0, 0.0, 20.0, 10.0)}

        assert figure_layout.overlaps(boxes) == []

    def test_separated_vertically_is_not_an_overlap(self):
        """Same x range, different y -- a stacked layout, not a
        collision. Checking x alone would report every layered figure."""
        boxes = {"a": (0.0, 0.0, 40.0, 10.0), "b": (0.0, 50.0, 40.0, 60.0)}

        assert figure_layout.overlaps(boxes) == []

    def test_the_picture_bounding_box_is_not_an_overlap_candidate(self):
        """It contains every node by construction, so including it would
        report an overlap against each one."""
        boxes = {
            "a": (0.0, 0.0, 10.0, 10.0),
            figure_layout.BBOX_NAME: (-1.0, -1.0, 11.0, 11.0),
        }

        assert figure_layout.overlaps(boxes) == []


class TestProtrusionAndEmptiness:
    def test_a_node_protruding_past_the_others_is_reported(self):
        """docs/TIKZ-STYLE.md's LaTeX-specific veto: an element sticking
        out above the main block makes surrounding text wrap around the
        highest point."""
        boxes = {
            "a": (0.0, 0.0, 40.0, 10.0),
            "b": (0.0, 12.0, 40.0, 22.0),
            "spike": (0.0, 200.0, 5.0, 210.0),
            figure_layout.BBOX_NAME: (0.0, 0.0, 40.0, 210.0),
        }

        assert figure_layout.protrudes(boxes) is True

    def test_non_node_content_reaching_past_every_node_is_reported(self):
        """The other shape of the same defect: a stray path or a label
        outside every node stretches the picture's box past them. The
        gap between the topmost node and the picture's own edge is what
        catches it, so one mechanism covers both."""
        boxes = {
            "a": (0.0, 0.0, 40.0, 10.0),
            "b": (0.0, 12.0, 40.0, 22.0),
            figure_layout.BBOX_NAME: (0.0, 0.0, 40.0, 200.0),
        }

        assert figure_layout.protrudes(boxes) is True

    def test_a_layered_diagram_with_ordinary_row_spacing_is_not_reported(self):
        """Three stacked rows with real gaps between them is what the
        layered-stack metaphor looks like -- reporting it would make the
        check fire on the layouts docs/TIKZ-STYLE.md recommends."""
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
        """A figure with no drawn extent has no meaningful emptiness --
        reporting 0.0 would read as "perfectly packed"."""
        boxes = {figure_layout.BBOX_NAME: (0.0, 0.0, 0.0, 0.0)}

        assert figure_layout.emptiness(boxes) is None

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

import json
import shutil
import subprocess

import pytest

from chitragupta import review
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
        figure.write_text(
            "\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}\n", encoding="utf-8"
        )
        draft = tmp_path / "survey.md"
        draft.write_text("Text.\n\n<!-- figure: figures/flow -->\n\nMore.\n", encoding="utf-8")

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


class TestEdgeListLimits:
    """What the regex costs, pinned rather than left in prose.

    This extraction is a regex over TikZ, not a parser of it, and this is
    the one check where that matters most: the list is read as *what the
    figure claims*, so a wrong entry is worse than a missing one. These
    tests exist so the boundary is a decision on record -- if one starts
    failing, the extraction got better and the docstring in
    `_source.py::edge_list` needs updating with it.
    """

    def test_an_anchor_rides_along_rather_than_being_stripped(self):
        """`a.south` is reported as-is. Stripping to `a` would be a guess
        about which side of the dot is a node name."""
        assert figure_layout.edge_list("\\draw (a.south) -- (b.north);") == [("a.south", "b.north")]

    def test_an_edge_drawn_by_a_wrapping_library_is_invisible(self):
        """`\\graph` never writes `\\draw`, so the list comes back
        silently short rather than wrong -- indistinguishable from a
        figure with no edges at all."""
        assert figure_layout.edge_list("\\graph { a -> b };") == []

    def test_a_to_with_options_is_still_an_edge(self):
        assert figure_layout.edge_list("\\draw (a) to[bend left] (b);") == [("a", "b")]


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


class TestProbePlacement:
    """Where the probes are spliced in, and which nodes get probed.

    Pure string work, so these run on a host with no TeX -- which is the
    point: they were previously exercised only through the compile
    tests, so CI's Windows leg measured them as uncovered even though
    nothing here needs a toolchain.
    """

    def test_node_names_finds_every_named_node(self):
        source = "\\node (a) {A};\n\\node[draw] (b) at (1,0) {B};\n"

        assert figure_layout.node_names(source) == ["a", "b"]

    def test_node_names_ignores_an_unnamed_node(self):
        """A node with no `(name)` cannot be probed -- `\\pgfpointanchor`
        has nothing to ask for."""
        assert figure_layout.node_names("\\node {just a label};\n") == []

    def test_probes_go_inside_the_picture_not_after_it(self):
        """`current bounding box` belongs to the picture being built, so
        a probe placed after `\\end{tikzpicture}` measures an empty one.
        That bug reported every real figure as 100% empty."""
        source = "\\begin{tikzpicture}\n\\node (a) {A};\n\\end{tikzpicture}\n"

        built = figure_layout.scaffold(source, ["a"])
        before_end = built[: built.index("\\end{tikzpicture}")]

        assert "CGBOX a" in before_end

    def test_the_last_picture_is_the_one_measured(self):
        """A figure built from several pictures is measured as the whole
        thing a reader sees, not as its first component."""
        source = (
            "\\begin{tikzpicture}\n\\node (a) {A};\n\\end{tikzpicture}\n"
            "\\begin{tikzpicture}\n\\node (b) {B};\n\\end{tikzpicture}\n"
        )

        built = figure_layout.scaffold(source, ["a", "b"])

        assert built.index("CGBOX a") > built.index("\\node (b)")

    def test_cgbox_lines_parse_out_of_a_log(self):
        """The format the whole aid rests on, parsed here from a literal
        log so the parser is measured on any host. The compile test
        pins the same format against a *real* pdflatex run, which is
        what stops this fixture from drifting into fiction."""
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
        """Nothing to measure, but the scaffold must not raise -- the
        honest answer for a figure file that draws no picture is an empty
        result, not a crash."""
        built = figure_layout.scaffold("% just a comment\n", [])

        assert "\\begin{document}" in built


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

    def test_a_figure_that_does_not_compile_raises_rather_than_returning_junk(self, tmp_path):
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

    def test_a_zone_node_containing_its_children_is_not_an_overlap(self):
        """Found by running this over the repository's own drafts: a
        two-zone architecture figure reported eight "overlaps", every one
        a labelled zone containing the nodes it exists to group. Zones
        via the `backgrounds` layer are what docs/TIKZ-STYLE.md
        *recommends*, so reporting them would fire on the standard's own
        advice."""
        boxes = {
            "control-plane": (0.0, 0.0, 300.0, 100.0),
            "auth": (20.0, 20.0, 80.0, 60.0),
            "registry": (120.0, 20.0, 180.0, 60.0),
        }

        assert figure_layout.overlaps(boxes) == []

    def test_a_genuine_partial_collision_is_still_reported(self):
        """The exclusion above must not swallow the real defect: two
        boxes crossing each other, neither containing the other."""
        boxes = {"a": (0.0, 0.0, 40.0, 20.0), "b": (20.0, 10.0, 60.0, 30.0)}

        assert figure_layout.overlaps(boxes) == [("a", "b")]

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

    def test_a_zero_area_bounding_box_with_nodes_gives_no_proportion(self):
        """A picture whose extent collapsed but which still defines
        nodes -- the division would be by zero, so there is no
        proportion to report."""
        boxes = {"a": (0.0, 0.0, 10.0, 10.0), figure_layout.BBOX_NAME: (0.0, 0.0, 0.0, 0.0)}

        assert figure_layout.emptiness(boxes) is None

    def test_a_figure_with_no_named_nodes_gives_no_proportion(self):
        """Found by running this over the repository's own drafts: a
        figure drawn entirely from `\\draw` paths and `\\foreach` bodies
        names no nodes, so the arithmetic called a visibly full picture
        "100% empty". That is an artefact, and a percentage invites
        someone to act on it."""
        boxes = {figure_layout.BBOX_NAME: (0.0, 0.0, 100.0, 100.0)}

        assert figure_layout.emptiness(boxes) is None


def _draft_with_figure(tmp_path, body: str, name: str = "flow"):
    """A Markdown draft plus the one figure it marks, under `tmp_path`."""
    (tmp_path / "figures").mkdir(exist_ok=True)
    (tmp_path / "figures" / f"{name}.tex").write_text(body, encoding="utf-8")
    draft = tmp_path / "survey.md"
    existing = draft.read_text(encoding="utf-8") if draft.exists() else "Prose.\n"
    draft.write_text(f"{existing}\n<!-- figure: figures/{name} -->\n", encoding="utf-8")
    return draft


class TestCheckDraft:
    """The whole-draft pass: every figure, every check, one result."""

    def test_a_draft_with_no_figures_reports_nothing(self, tmp_path):
        draft = tmp_path / "survey.md"
        draft.write_text("No figures at all.\n", encoding="utf-8")

        assert figure_layout.check_draft(draft) == []

    def test_static_checks_run_without_any_compile(self, tmp_path, monkeypatch):
        """The point of the source/geometry split: a host with no TeX
        still gets the node-length and edge-list checks.

        Asserts only that *something* was skipped and said so, not which
        binary was missing. Two separate absences reach here -- no
        `pdflatex`, and no `tikz.sty` -- and pinning the message to one
        of them made this fail on a host missing the *other*, which is
        CI's Windows leg.
        """

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

    def test_a_host_with_no_pdflatex_skips_geometry_rather_than_crashing(
        self, tmp_path, monkeypatch
    ):
        """`_require_tikz()` says nothing where `kpsewhich` is absent, by
        design, so probing it alone let a host with no TeX at all reach
        the `subprocess` call and die on `FileNotFoundError`. CI's
        Windows leg is that host, and this is the regression test for
        what it caught."""

        def _no_pdflatex(binary):
            raise figure_layout.MissingBinary(f"'{binary}' is not on PATH.")

        monkeypatch.setattr(figure_layout, "_require", _no_pdflatex)
        draft = _draft_with_figure(tmp_path, "\\node (a) {A};\n")

        results = figure_layout.check_draft(draft)

        assert results[0].boxes is None
        assert "pdflatex" in results[0].skipped

    @needs_tikz
    def test_a_broken_figure_does_not_stop_the_others(self, tmp_path):
        """The failure policy that matters: one bad figure is a finding,
        and every other figure is still checked."""
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

    @needs_tikz
    def test_overlapping_nodes_are_found_end_to_end(self, tmp_path):
        """The roadmap's own probe, reproduced by the suite rather than
        by hand -- two nodes placed close enough to collide."""
        draft = _draft_with_figure(
            tmp_path,
            "\\begin{tikzpicture}\n"
            "\\node (a) at (0,0) {A long label here};\n"
            "\\node (b) at (0.3,0) {Another long label};\n"
            "\\end{tikzpicture}\n",
        )

        results = figure_layout.check_draft(draft)

        assert results[0].overlapping == [("a", "b")]


class TestReport:
    def test_a_clean_draft_says_so(self, tmp_path):
        draft = tmp_path / "survey.md"
        draft.write_text("No figures.\n", encoding="utf-8")

        text = figure_layout.format_report(draft, [])

        assert "no figures" in text.lower()

    def test_the_continuous_score_is_labelled_as_advisory(self, tmp_path):
        """R3: a proportion must never read as a verdict. If this label
        goes missing, the number starts looking like something to
        optimise."""
        draft = tmp_path / "survey.md"
        result = figure_layout.FigureResult(
            path=tmp_path / "figures" / "flow.tex",
            boxes={"a": (0.0, 0.0, 10.0, 10.0), figure_layout.BBOX_NAME: (0.0, 0.0, 20.0, 10.0)},
        )

        text = figure_layout.format_report(draft, [result])

        assert "human-read only" in text
        assert "50" in text

    def test_two_runs_over_an_unchanged_draft_are_byte_identical(self, tmp_path):
        """No timestamp anywhere, the review layer's standing rule -- so
        a report kept beside a draft diffs cleanly across revisions."""
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
        """Advisory, always. An aid that fails a build is a gate, and
        this project has exactly one of those.

        The finding itself is asserted, not just the exit code: "exits 0"
        is also what an aid that found nothing does, so without the
        second assertion this would pass just as happily against a
        checker that had silently stopped checking.
        """
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
        """`review/__main__.py` creates the `figure` subparser and passes
        it in, so the flags are declared once here and never restated
        there. The standalone path (`parser is None`) is what `main()`
        uses; both have to work."""
        import argparse

        sub = argparse.ArgumentParser().add_subparsers().add_parser("figure")
        figure_layout.build_parser(sub)

        args = sub.parse_args(["draft.md", "--json"])

        assert args.draft == "draft.md" and args.json is True

    def test_the_recorded_command_carries_the_flags_used(self, tmp_path):
        """A report read months later has to say how it was produced."""
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
        """R3, asserted rather than trusted: the proportion rides in the
        per-figure section, never in `findings`, because a number in a
        findings array is a number something will try to close."""
        results = [
            figure_layout.FigureResult(
                path=tmp_path / "figures" / "flow.tex",
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
        """The text report is what a reviewer actually reads at the
        terminal, so both binary geometry findings have to reach it and
        not only the JSON."""
        results = [
            figure_layout.FigureResult(
                path=tmp_path / "figures" / "flow.tex",
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
        """Found running this over real drafts: a figure drawn from
        `\\draw` paths alone has no nodes, no edges between named things
        and no proportion, and printing a bare `path:` line for it was
        most of the output while carrying none of the information."""
        results = [
            figure_layout.FigureResult(
                path=tmp_path / "figures" / "quiet.tex",
                boxes={},
            )
        ]

        text = figure_layout.format_report(tmp_path / "s.md", results)

        assert "quiet.tex" not in text
        assert "No layout findings" in text

    def test_the_markdown_still_names_a_figure_it_had_nothing_to_say_about(self, tmp_path):
        """The opposite rule to the text report's, deliberately: a filed
        report is read as a record of what was checked, so a figure
        silently absent reads as one never looked at."""
        results = [
            figure_layout.FigureResult(
                path=tmp_path / "figures" / "quiet.tex",
                boxes={},
            )
        ]

        body = figure_layout.render_markdown(tmp_path / "s.md", results, "cmd")

        assert "quiet.tex" in body
        assert "Nothing to report" in body

    def test_a_clean_figure_says_it_is_not_a_verdict(self, tmp_path):
        """An aid reporting nothing must not read as a pass."""
        results = [
            figure_layout.FigureResult(
                path=tmp_path / "figures" / "flow.tex",
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
        """Every check that needs the picture's extent returns a
        no-answer rather than guessing one."""
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
        """pdflatex can exit non-zero without a `!` line -- an empty
        detail would make the finding unreadable."""
        assert "without reporting" in figure_layout._probe._compile_error_detail("")

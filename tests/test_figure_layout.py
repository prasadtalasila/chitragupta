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

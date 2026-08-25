"""docs/TIKZ-STYLE.md's panelled-figure example, checked rather than claimed.

#396 asks for sub-captions on a figure's sub-figures. The answer that
document gives is a drawn label node per panel -- `(a) <title>`, `(b)`,
and on for as many panels as the figure has -- rather than the
`subcaption` package, which cannot be loaded from a figure file and
would fail in the one preamble this project does not own (a user's own
thesis, which `thesis-chapter-writer` writes a fragment for).

Guidance that ships a worked example owes a check that the example still
works, and this file is it. Three things it guards:

- **The example is read out of the document**, not restated here, the
  same way `tests/test_tikz_scaffolds.py` reads the metaphor table. An
  edit to the fence is checked; a copy kept here would drift instead.
- **Three panels, not two.** The issue's own wording says "two
  sub-figures" and the rule is deliberately not bounded by two, so the
  example that stands for it letters `(a)` to `(c)`. A two-panel example
  would pass a letter check that says nothing about a third panel.
- **Zero findings has to be earned.** `review figure` measures a node's
  geometry only where the source names it, so a picture naming nothing
  reports nothing and reads like a clean figure. The example is asserted
  to have every name it declares come back measured, exactly as the
  scaffolds are.

What is *not* here is a general "does this figure letter its panels"
check over arbitrary figures. Panel count is not recoverable from a
picture: the aid sees only named nodes -- 1 of the 43 figures in this
repository's own drafted book names any -- and "no edge crosses the
gutter" is not what a panel is, since a figure may draw an arrow from
one panel to another. The letters below are asserted against a known
example, which is a different and much weaker claim.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from chitragupta.review import figure_layout

REPO_ROOT = Path(__file__).resolve().parent.parent
STYLE_DOC = REPO_ROOT / "docs" / "TIKZ-STYLE.md"

# The panelled-figure section, found by its heading rather than by
# position, and the first `latex` fence inside it. Anchored on the
# heading's words rather than its emoji: an emoji is the kind of thing a
# doc pass changes without meaning to touch this test.
_SECTION_RE = re.compile(r"^##\s+\S*\s*Panels in one figure.*$", re.MULTILINE)
_NEXT_HEADING_RE = re.compile(r"^##\s", re.MULTILINE)
_FENCE_RE = re.compile(r"```latex\n(?P<body>.*?)```", re.DOTALL)

# `(a) polled`, `(b) pushed`, ... -- the label node text the section
# requires, in the order the source declares them.
_LABEL_RE = re.compile(r"\{\((?P<letter>[a-z])\)\s[^}]*\}")

EXPECTED_PANELS = 3


def _panel_example() -> str:
    """The worked example docs/TIKZ-STYLE.md's panel section carries.

    The search is bounded at the *next* `##` heading rather than run to
    the end of the file. Unbounded, a section that lost its example would
    quietly pick up the next section's fence and every assertion below
    would go on passing against the wrong picture -- the same
    vacuous-pass failure this file's docstring describes for a figure
    that names no node.
    """
    doc = STYLE_DOC.read_text(encoding="utf-8")
    section = _SECTION_RE.search(doc)
    assert section is not None, "docs/TIKZ-STYLE.md has no panelled-figure section"
    following = _NEXT_HEADING_RE.search(doc, section.end())
    body = doc[section.end() : following.start() if following else len(doc)]
    fence = _FENCE_RE.search(body)
    assert fence is not None, "the panelled-figure section carries no ```latex example"
    return fence.group("body")


def _has_tikz() -> bool:
    """Whether this host can compile a TikZ figure at all.

    The same probe `tests/test_tikz_scaffolds.py` uses, and for the same
    reason: CI's Windows leg installs no `os-deps`, so the geometry half
    of this file has to self-skip rather than fail there.
    """
    if shutil.which("pdflatex") is None or shutil.which("kpsewhich") is None:
        return False
    probe = subprocess.run(["kpsewhich", "tikz.sty"], capture_output=True, check=False)
    return probe.returncode == 0


needs_tikz = pytest.mark.skipif(not _has_tikz(), reason="needs pdflatex with tikz.sty")


@pytest.fixture(name="example")
def _example() -> str:
    return _panel_example()


@pytest.fixture(name="example_figure")
def _example_figure(example, tmp_path) -> Path:
    """The example on disk, beside a draft that marks it -- which is how
    `check_draft` resolves a figure, and how an author reaches it."""
    figures = tmp_path / "figures"
    figures.mkdir()
    figure = figures / "panels.tex"
    figure.write_text(example, encoding="utf-8")
    (figures / "panels.txt").write_text("(a)   (b)   (c)\n", encoding="utf-8")
    (tmp_path / "draft.md").write_text(
        "Prose.\n\n<!-- figure: figures/panels -->\n", encoding="utf-8"
    )
    return figure


class TestTheExampleWasActuallyFound:
    """The non-vacuous-scan guard every doc-reading test here owes.

    A doc pass that renamed the heading or reflowed the fence would make
    `_panel_example` return something inert, and an inert string passes
    several of the assertions below for the wrong reason.
    """

    def test_it_is_a_picture(self, example):
        assert "\\begin{tikzpicture}" in example

    def test_it_is_wrapped_in_a_float_with_a_caption(self, example):
        """The section says a captioned figure carries its own float --
        the renderer injects a bare `\\input` and no float of its own."""
        assert "\\begin{figure}" in example
        assert "\\caption{" in example


class TestEverySourceProperty:
    """What can be checked without a toolchain, so it runs everywhere."""

    def test_it_carries_its_own_usetikzlibrary_line(self, example):
        """The renderer's preamble loads `tikz` and no library, so an
        example relying on `positioning`/`fit` and not loading it would
        fail the whole render rather than just itself."""
        assert "\\usetikzlibrary{" in example

    def test_it_names_the_nodes_it_draws(self, example):
        assert figure_layout.node_names(example)

    def test_no_node_text_past_the_conciseness_line(self, example):
        assert figure_layout.overlong_nodes(example) == []

    def test_every_panel_is_lettered_consecutively_from_a(self, example):
        """More than two panels, lettered in source order with no gap.

        Hard-coding three is right *here* and would be wrong as a general
        check -- see this module's docstring. The point of three is that
        it cannot be satisfied by a rule that only understands pairs.
        """
        letters = [match.group("letter") for match in _LABEL_RE.finditer(example)]

        assert len(letters) == EXPECTED_PANELS
        assert letters == [chr(ord("a") + index) for index in range(EXPECTED_PANELS)]

    def test_no_subcaption_package(self, example):
        """`\\usepackage` is preamble-only, and one preamble a figure
        reaches is the user's own thesis. The section rejects the package
        outright; an example reaching for it would teach the opposite."""
        assert "subcaption" not in example
        assert "\\usepackage" not in example


@needs_tikz
class TestEveryGeometryProperty:
    """The half that needs a real `pdflatex`."""

    def test_it_compiles_and_measures_every_name_it_declares(self, example, example_figure):
        """Zero findings, earned rather than vacuous -- see this module's
        docstring."""
        boxes = figure_layout.node_boxes(example_figure)
        measured = set(boxes) - {figure_layout.BBOX_NAME}

        assert measured == set(figure_layout.node_names(example))

    def test_no_two_panels_collide(self, example_figure):
        assert figure_layout.overlaps(figure_layout.node_boxes(example_figure)) == []

    def test_nothing_protrudes(self, example_figure):
        assert figure_layout.protrudes(figure_layout.node_boxes(example_figure)) is False


@needs_tikz
class TestThroughTheDocumentedCommand:
    """The example checked the way an author actually reaches it.

    Everything above calls the library's own functions. This goes through
    `check_draft()`, which is what `python -m chitragupta.review figure
    <draft>` runs -- and which resolves a figure only beside the draft
    that marks it.
    """

    def test_the_example_reports_no_finding(self, example_figure):
        results = figure_layout.check_draft(example_figure.parent.parent / "draft.md")

        assert len(results) == 1
        assert results[0].skipped == ""
        assert results[0].failed is None
        assert results[0].overlong == []
        assert figure_layout.overlaps(results[0].boxes) == []
        assert figure_layout.protrudes(results[0].boxes) is False

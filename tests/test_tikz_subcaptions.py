import re
from pathlib import Path

import pytest

from chitragupta.review import figure_layout
from tests.conftest import needs_tikz

REPO_ROOT = Path(__file__).resolve().parent.parent
STYLE_DOC = REPO_ROOT / "docs" / "TIKZ-STYLE.md"

_SECTION_RE = re.compile(r"^##\s+\S*\s*Panels in one figure.*$", re.MULTILINE)
_NEXT_HEADING_RE = re.compile(r"^##\s", re.MULTILINE)
_FENCE_RE = re.compile(r"```latex\n(?P<body>.*?)```", re.DOTALL)

_LABEL_RE = re.compile(r"\{\((?P<letter>[a-z])\)\s[^}]*\}")

EXPECTED_PANELS = 3


def _panel_example() -> str:
    doc = STYLE_DOC.read_text(encoding="utf-8")
    section = _SECTION_RE.search(doc)
    assert section is not None, "docs/TIKZ-STYLE.md has no panelled-figure section"
    following = _NEXT_HEADING_RE.search(doc, section.end())
    body = doc[section.end() : following.start() if following else len(doc)]
    fence = _FENCE_RE.search(body)
    assert fence is not None, "the panelled-figure section carries no ```latex example"
    return fence.group("body")


@pytest.fixture(name="example")
def _example() -> str:
    return _panel_example()


@pytest.fixture(name="example_figure")
def _example_figure(example, tmp_path) -> Path:
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
    def test_it_is_a_picture(self, example):
        assert "\\begin{tikzpicture}" in example

    def test_it_is_wrapped_in_a_float_with_a_caption(self, example):
        assert "\\begin{figure}" in example
        assert "\\caption{" in example


class TestEverySourceProperty:
    def test_it_carries_its_own_usetikzlibrary_line(self, example):
        assert "\\usetikzlibrary{" in example

    def test_it_names_the_nodes_it_draws(self, example):
        assert figure_layout.node_names(example)

    def test_no_node_text_past_the_conciseness_line(self, example):
        assert figure_layout.overlong_nodes(example) == []

    def test_every_panel_is_lettered_consecutively_from_a(self, example):
        letters = [match.group("letter") for match in _LABEL_RE.finditer(example)]

        assert len(letters) == EXPECTED_PANELS
        assert letters == [chr(ord("a") + index) for index in range(EXPECTED_PANELS)]

    def test_no_subcaption_package(self, example):
        assert "subcaption" not in example
        assert "\\usepackage" not in example


@pytest.mark.slow
@needs_tikz
class TestEveryGeometryProperty:
    def test_it_compiles_and_measures_every_name_it_declares(self, example, example_figure):
        boxes = figure_layout.node_boxes(example_figure)
        measured = set(boxes) - {figure_layout.BBOX_NAME}

        assert measured == set(figure_layout.node_names(example))

    def test_no_two_panels_collide(self, example_figure):
        assert figure_layout.overlaps(figure_layout.node_boxes(example_figure)) == []

    def test_nothing_protrudes(self, example_figure):
        assert figure_layout.protrudes(figure_layout.node_boxes(example_figure)) is False


@pytest.mark.slow
@needs_tikz
class TestThroughTheDocumentedCommand:
    def test_the_example_reports_no_finding(self, example_figure):
        results = figure_layout.check_draft(example_figure.parent.parent / "draft.md")

        assert len(results) == 1
        assert results[0].skipped == ""
        assert results[0].failed is None
        assert results[0].overlong == []
        assert figure_layout.overlaps(results[0].boxes) == []
        assert figure_layout.protrudes(results[0].boxes) is False

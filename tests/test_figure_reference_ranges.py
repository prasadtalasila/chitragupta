"""A figure's layout and its reference ranges (#1057): the
`% cg-layout:` line and the layout file's `## Reference ranges` table,
as `figure check` reads them."""

from pathlib import Path

import pytest

from chitragupta.figure import _layout

REPO_ROOT = Path(__file__).resolve().parent.parent
LAYOUTS = REPO_ROOT / ".claude" / "skills" / "figure-drawer" / "references" / "layouts"

TABLE = """\
## Reference ranges

| Source | Nodes | Edges | Width | Height | Slack |
| --- | --- | --- | --- | --- | --- |
| `assets/tikz/pipeline.tex` | 5 | 3 | 0.68 | 0.10 | 0.55 |
| `assets/tikz/exemplars/rag-stages.tex` | 11 | 4 | 1.09 | 0.35 | 0.71 |
"""


class TestDeclaredLayout:
    def test_a_full_line_comment_names_the_layout(self):
        assert _layout.declared_layout("% cg-layout: pipeline\n\\begin{tikzpicture}") == "pipeline"

    def test_leading_space_and_doubled_percent_are_a_comment_still(self):
        assert _layout.declared_layout("  %% cg-layout:   control-loop  \n") == "control-loop"

    def test_none_declared_is_empty(self):
        assert _layout.declared_layout("\\begin{tikzpicture}\\end{tikzpicture}\n") == ""

    def test_a_trailing_comment_on_a_drawing_line_does_not_count(self):
        """The same stance as `% cg-allow:`: a line of its own, so it is
        not deleted along with the drawing line it trails."""
        assert _layout.declared_layout("\\node (a) {A}; % cg-layout: pipeline\n") == ""

    def test_the_first_line_wins(self):
        source = "% cg-layout: map\n% cg-layout: pipeline\n"

        assert _layout.declared_layout(source) == "map"

    def test_an_empty_name_is_none(self):
        assert _layout.declared_layout("% cg-layout:\n") == ""


class TestRangeRows:
    def test_every_measured_row_is_read(self):
        rows = _layout.range_rows(TABLE)

        assert rows == [
            _layout.RangeRow("assets/tikz/pipeline.tex", 5, 3, 0.68, 0.10, 0.55),
            _layout.RangeRow("assets/tikz/exemplars/rag-stages.tex", 11, 4, 1.09, 0.35, 0.71),
        ]

    def test_the_header_and_rule_rows_are_not_rows(self):
        assert _layout.range_rows("| Source | Nodes |\n| --- | --- |\n") == []


class TestReference:
    def test_a_layout_with_a_file_has_its_rows(self):
        rows = _layout.reference("pipeline")

        assert "assets/tikz/pipeline.tex" in [row.source for row in rows]

    @pytest.mark.parametrize("name", ["", "no-such-layout", "../patterns", "a/b"])
    def test_a_name_with_no_file_has_none(self, name):
        assert _layout.reference(name) is None

    def test_the_names_are_the_files_present(self):
        assert _layout.layout_names() == sorted(path.stem for path in LAYOUTS.glob("*.md"))
        assert "pipeline" in _layout.layout_names()

    def test_the_directory_is_the_shipped_skill_references(self):
        assert _layout.LAYOUT_DIR.resolve() == LAYOUTS.resolve()


class TestSpan:
    def test_it_is_the_lowest_and_highest_row(self):
        rows = _layout.range_rows(TABLE)

        assert _layout.span(rows, "nodes") == (5, 11)
        assert _layout.span(rows, "height") == (0.10, 0.35)

from pathlib import Path

from chitragupta import style_figures


def draft_with(body: str, tmp_path: Path) -> Path:
    path = tmp_path / "tutorial.md"
    path.write_text(body, encoding="utf-8")
    return path


CAPTIONED = "<!-- figure: figures/fig1 -->\nOne reading path.\n"


def rules(findings: list[dict]) -> list[str]:
    return [finding["rule"] for finding in findings]


class TestNoCaption:
    def test_an_uncaptioned_marker_is_reported(self, tmp_path):
        body = "# S\n\n<!-- figure: figures/x -->\n\nSome prose after a blank line.\n"
        found = style_figures.findings(draft_with(body, tmp_path))
        assert "chitragupta.FigureNoCaption" in rules(found)

    def test_it_is_reported_at_the_marker_line_and_names_the_id(self, tmp_path):
        body = "# S\n\n<!-- figure: figures/x -->\n\nSome prose after a blank line.\n"
        found = [
            f
            for f in style_figures.findings(draft_with(body, tmp_path))
            if f["rule"] == "chitragupta.FigureNoCaption"
        ]
        assert (found[0]["line"], found[0]["match"]) == (3, "x")

    def test_adding_the_caption_clears_it(self, tmp_path):
        body = f"# S\n\nAs <!-- figureref: fig1 --> shows.\n\n{CAPTIONED}"
        assert "chitragupta.FigureNoCaption" not in rules(
            style_figures.findings(draft_with(body, tmp_path))
        )

    def test_an_uncaptioned_marker_inside_a_fence_is_not_a_figure(self, tmp_path):
        body = "# S\n\nLike this:\n\n```markdown\n<!-- figure: figures/x -->\n```\n"
        assert style_figures.findings(draft_with(body, tmp_path)) == []

    def test_an_uncaptioned_marker_is_still_unreferenced_only_once(self, tmp_path):
        body = "# S\n\n<!-- figure: figures/x -->\n\nProse.\n"
        assert rules(style_figures.findings(draft_with(body, tmp_path))) == [
            "chitragupta.FigureNoCaption"
        ]


class TestUncapturedAndCleanCases:
    def test_a_referenced_captioned_figure_reports_nothing(self, tmp_path):
        body = f"# S\n\nAs <!-- figureref: fig1 --> shows.\n\n{CAPTIONED}"
        assert style_figures.findings(draft_with(body, tmp_path)) == []

    def test_a_draft_with_no_figure_reports_nothing(self, tmp_path):
        assert style_figures.findings(draft_with("# S\n\nJust prose.\n", tmp_path)) == []


class TestFencedExamplesAreNotFigures:
    def test_a_fenced_marker_example_reports_nothing(self, tmp_path):
        body = f"# S\n\nLike this:\n\n```markdown\n{CAPTIONED}```\n"
        assert style_figures.findings(draft_with(body, tmp_path)) == []

    def test_a_real_figure_after_a_fenced_one_still_reports_at_its_own_line(self, tmp_path):
        body = f"# S\n\n```markdown\n{CAPTIONED}```\n\n{CAPTIONED}"
        found = style_figures.findings(draft_with(body, tmp_path))
        assert rules(found) == ["chitragupta.FigureUnreferenced"]
        assert found[0]["line"] == 8  # blanking preserves every line number


class TestIds:
    def test_two_figures_claiming_one_id(self, tmp_path):
        body = f"# S\n\nAs <!-- figureref: fig1 --> shows.\n\n{CAPTIONED}\n{CAPTIONED}"
        assert "chitragupta.FigureDuplicateId" in rules(
            style_figures.findings(draft_with(body, tmp_path))
        )

    def test_an_id_that_is_not_kebab_case(self, tmp_path):
        body = (
            "# S\n\nAs <!-- figureref: Fig_One --> shows.\n\n<!-- figure: figures/Fig_One -->\nC.\n"
        )
        assert "chitragupta.FigureMalformedId" in rules(
            style_figures.findings(draft_with(body, tmp_path))
        )

    def test_a_reference_to_an_id_no_figure_declares(self, tmp_path):
        body = (
            f"# S\n\nAs <!-- figureref: ghost --> and <!-- figureref: fig1 --> too.\n\n{CAPTIONED}"
        )
        found = style_figures.findings(draft_with(body, tmp_path))
        assert rules(found) == ["chitragupta.FigureUnknownRef"]
        assert found[0]["match"] == "ghost"


class TestUnreferenced:
    def test_a_figure_no_sentence_points_at(self, tmp_path):
        body = f"# S\n\nProse that never mentions it.\n\n{CAPTIONED}"
        found = style_figures.findings(draft_with(body, tmp_path))
        assert rules(found) == ["chitragupta.FigureUnreferenced"]
        assert found[0]["match"] == "fig1"
        assert "explain" in found[0]["message"]


class TestReferencedOutsideItsSection:
    def test_the_only_reference_sits_in_another_section(self, tmp_path):
        body = f"## One\n\nAs <!-- figureref: fig1 --> shows.\n\n## Two\n\n{CAPTIONED}"
        found = style_figures.findings(draft_with(body, tmp_path))
        assert rules(found) == ["chitragupta.FigureRefOutsideSection"]

    def test_a_reference_in_the_same_section_is_clean(self, tmp_path):
        body = f"## One\n\nProse.\n\n## Two\n\nAs <!-- figureref: fig1 -->.\n\n{CAPTIONED}"
        assert style_figures.findings(draft_with(body, tmp_path)) == []

    def test_a_draft_with_no_headings_at_all_has_one_section(self, tmp_path):
        body = f"As <!-- figureref: fig1 --> shows.\n\n{CAPTIONED}"
        assert style_figures.findings(draft_with(body, tmp_path)) == []


class TestFindingShape:
    def test_every_finding_carries_what_the_report_prints(self, tmp_path):
        found = style_figures.findings(draft_with(f"# S\n\n{CAPTIONED}", tmp_path))
        assert set(found[0]) == {"rule", "match", "line", "message", "severity", "count", "repair"}
        assert found[0]["count"] == 1
        assert found[0]["severity"] == "suggestion"

    def test_a_latex_fragment_is_left_to_its_own_numbering(self, tmp_path):
        fragment = tmp_path / "chapter.tex"
        fragment.write_text(
            "\\begin{figure}\n\\input{figures/x.tex}\n\\caption{X}\\label{fig:x}\n\\end{figure}\n",
            encoding="utf-8",
        )
        assert style_figures.findings(fragment) == []


class TestMessagesCiteTheFiguresFile:
    def test_every_cited_section_names_the_figures_file(self, tmp_path):
        body = f"# S\n\n<!-- figure: figures/x -->\n\nSome prose after a blank line.\n\n{CAPTIONED}"
        found = style_figures.findings(draft_with(body, tmp_path))
        assert set(rules(found)) == {
            "chitragupta.FigureNoCaption",
            "chitragupta.FigureUnreferenced",
        }
        for finding in found:
            assert "(docs/writing-standards/figures.md §10)." in finding["message"], finding

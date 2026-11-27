from chitragupta import style_equations
from tests.conftest import draft_with

EQUATION = "<!-- equation: energy -->\n<!-- math -->\n```\nE = m * c^2\n```\n"


def rules(findings: list[dict]) -> list[str]:
    return [finding["rule"] for finding in findings]


class TestOrphanMarker:
    def test_a_marker_with_no_math_block_is_reported(self, tmp_path):
        body = "# S\n\n<!-- equation: bare -->\n\nprose, no math marker\n"
        found = style_equations.findings(draft_with(body, tmp_path))
        assert rules(found) == ["chitragupta.EquationOrphanMarker"]

    def test_a_well_formed_equation_is_not_orphaned(self, tmp_path):
        body = f"# S\n\nAs <!-- equationref: energy --> shows.\n\n{EQUATION}"
        assert style_equations.findings(draft_with(body, tmp_path)) == []

    def test_a_draft_with_no_equation_marker_reports_nothing(self, tmp_path):
        assert style_equations.findings(draft_with("# S\n\nJust prose.\n", tmp_path)) == []

    def test_an_unmarked_math_block_is_not_a_finding(self, tmp_path):
        body = "# S\n\n<!-- math -->\n```\nx = 1\n```\n"
        assert style_equations.findings(draft_with(body, tmp_path)) == []


class TestFencedExamplesAreReadAsReal:
    def test_a_documented_example_is_read_as_a_real_equation(self, tmp_path):
        body = f"# S\n\nLike this:\n\n{EQUATION}"
        found = style_equations.findings(draft_with(body, tmp_path))
        assert "chitragupta.EquationUnreferenced" in rules(found)


class TestIds:
    def test_two_equations_claiming_one_id(self, tmp_path):
        body = f"# S\n\nAs <!-- equationref: energy --> shows.\n\n{EQUATION}\n{EQUATION}"
        assert "chitragupta.EquationDuplicateId" in rules(
            style_equations.findings(draft_with(body, tmp_path))
        )

    def test_an_id_that_is_not_kebab_case(self, tmp_path):
        body = (
            "# S\n\nAs <!-- equationref: Energy_1 --> shows.\n\n"
            "<!-- equation: Energy_1 -->\n<!-- math -->\n```\nE = m * c^2\n```\n"
        )
        assert "chitragupta.EquationMalformedId" in rules(
            style_equations.findings(draft_with(body, tmp_path))
        )

    def test_a_reference_to_an_id_no_equation_declares(self, tmp_path):
        body = (
            f"# S\n\nAs <!-- equationref: ghost --> shows, and "
            f"<!-- equationref: energy --> too.\n\n{EQUATION}"
        )
        found = style_equations.findings(draft_with(body, tmp_path))
        assert rules(found) == ["chitragupta.EquationUnknownRef"]
        assert found[0]["match"] == "ghost"


class TestUnreferenced:
    def test_an_equation_no_sentence_points_at(self, tmp_path):
        body = f"# S\n\nProse that never mentions it.\n\n{EQUATION}"
        found = style_equations.findings(draft_with(body, tmp_path))
        assert rules(found) == ["chitragupta.EquationUnreferenced"]
        assert found[0]["match"] == "energy"
        assert "explain" in found[0]["message"]


class TestReferencedOutsideItsSection:
    def test_the_only_reference_sits_in_another_section(self, tmp_path):
        body = f"## One\n\nAs <!-- equationref: energy --> shows.\n\n## Two\n\n{EQUATION}"
        found = style_equations.findings(draft_with(body, tmp_path))
        assert rules(found) == ["chitragupta.EquationRefOutsideSection"]

    def test_a_reference_in_the_same_section_is_clean(self, tmp_path):
        body = f"## One\n\nProse.\n\n## Two\n\nAs <!-- equationref: energy --> shows.\n\n{EQUATION}"
        assert style_equations.findings(draft_with(body, tmp_path)) == []

    def test_a_draft_with_no_headings_at_all_has_one_section(self, tmp_path):
        body = f"As <!-- equationref: energy --> shows.\n\n{EQUATION}"
        assert style_equations.findings(draft_with(body, tmp_path)) == []


class TestFindingShape:
    def test_every_finding_carries_what_the_report_prints(self, tmp_path):
        body = "# S\n\n<!-- equation: bare -->\n\nno block\n"
        found = style_equations.findings(draft_with(body, tmp_path))
        assert set(found[0]) == {"rule", "match", "line", "message", "severity", "count", "repair"}
        assert found[0]["count"] == 1
        assert found[0]["severity"] == "suggestion"

    def test_a_latex_fragment_is_left_to_its_own_numbering(self, tmp_path):
        fragment = tmp_path / "chapter.tex"
        fragment.write_text("\\[E = mc^2\\]\n", encoding="utf-8")
        assert style_equations.findings(fragment) == []

"""chitragupta/style_tables.py: the table findings `draft style` reports.

Beside `tests/test_style_acronym_drift.py`, the other finding in that
command computed in Python rather than by Vale.

The discriminating tests are `TestUnreferenced` and
`TestReferencedOutsideItsSection`: they are what issue 395's second half
asks for -- a table the prose never reads -- and they are the reason
this module exists rather than the renderer's own `warnings()` being
enough. The renderer sees a marker that cannot resolve; only this sees a
table nobody explains.
"""

from pathlib import Path

from chitragupta import style_tables


def draft_with(body: str, tmp_path: Path) -> Path:
    path = tmp_path / "survey.md"
    path.write_text(body, encoding="utf-8")
    return path


TABLE = "| Starting point | Core idea |\n|---|---|\n| DTaaS | One platform |\n"
CAPTION = ": Where to start when building a first twin.\n<!-- table: start-here -->\n"


def rules(findings: list[dict]) -> list[str]:
    return [finding["rule"] for finding in findings]


class TestNoCaption:
    def test_a_bare_pipe_table_is_reported(self, tmp_path):
        # The state every draft in content/drafts/ is in today.
        found = style_tables.findings(draft_with(f"# S\n\n{TABLE}", tmp_path))
        assert rules(found) == ["chitragupta.TableNoCaption"]
        assert found[0]["line"] == 3

    def test_a_captioned_marked_table_is_not(self, tmp_path):
        body = f"# S\n\nAs <!-- tableref: start-here --> shows.\n\n{TABLE}\n{CAPTION}"
        assert style_tables.findings(draft_with(body, tmp_path)) == []

    def test_a_draft_with_no_table_reports_nothing(self, tmp_path):
        assert style_tables.findings(draft_with("# S\n\nJust prose.\n", tmp_path)) == []

    def test_a_bare_table_above_a_captioned_one_is_still_reported(self, tmp_path):
        # The caption search is bounded by the next table: unbounded, the
        # bare table would borrow the second table's caption and this
        # draft would report nothing at all.
        body = f"# S\n\n{TABLE}\nAs <!-- tableref: start-here --> shows.\n\n{TABLE}\n{CAPTION}"
        found = style_tables.findings(draft_with(body, tmp_path))
        assert rules(found) == ["chitragupta.TableNoCaption"]
        assert found[0]["match"] == "| Starting point | Core idea |"


class TestFencedExamplesAreNotTables:
    """A draft showing a table as an example is not a draft with a table.

    `tutorial-writer` and `textbook-chapter-writer` both put Markdown
    source in fences, and this section's own markup is the likeliest
    thing a draft about this pipeline would show. Reported, it is one
    false finding per example on a report whose whole value is its
    signal-to-noise ratio.
    """

    def test_a_fenced_table_example_reports_nothing(self, tmp_path):
        body = f"# S\n\nLike this:\n\n```markdown\n{TABLE}```\n"
        assert style_tables.findings(draft_with(body, tmp_path)) == []

    def test_a_real_table_after_a_fenced_one_still_reports_at_its_own_line(self, tmp_path):
        body = f"# S\n\n```markdown\n{TABLE}```\n\n{TABLE}"
        found = style_tables.findings(draft_with(body, tmp_path))
        assert rules(found) == ["chitragupta.TableNoCaption"]
        assert found[0]["line"] == 9  # blanking preserves every line number


class TestNoId:
    def test_a_caption_without_a_marker_is_a_different_finding(self, tmp_path):
        # Narrower than NoCaption, and reported instead of it: the author
        # wrote the caption and stopped, so "add a caption" is the wrong
        # thing to tell them.
        body = f"# S\n\n{TABLE}\n: Where to start.\n"
        found = style_tables.findings(draft_with(body, tmp_path))
        assert rules(found) == ["chitragupta.TableNoId"]


class TestIds:
    def test_two_tables_claiming_one_id(self, tmp_path):
        body = f"# S\n\nAs <!-- tableref: start-here --> shows.\n\n{TABLE}\n{CAPTION}\n{TABLE}\n{CAPTION}"
        assert "chitragupta.TableDuplicateId" in rules(
            style_tables.findings(draft_with(body, tmp_path))
        )

    def test_an_id_that_is_not_kebab_case(self, tmp_path):
        body = f"# S\n\nAs <!-- tableref: Start Here --> shows.\n\n{TABLE}\n: C.\n<!-- table: Start_Here -->\n"
        assert "chitragupta.TableMalformedId" in rules(
            style_tables.findings(draft_with(body, tmp_path))
        )

    def test_a_reference_to_an_id_no_table_declares(self, tmp_path):
        body = f"# S\n\nAs <!-- tableref: ghost --> shows, and <!-- tableref: start-here --> too.\n\n{TABLE}\n{CAPTION}"
        found = style_tables.findings(draft_with(body, tmp_path))
        assert rules(found) == ["chitragupta.TableUnknownRef"]
        assert found[0]["match"] == "ghost"


class TestUnreferenced:
    def test_a_table_no_sentence_points_at(self, tmp_path):
        body = f"# S\n\nProse that never mentions it.\n\n{TABLE}\n{CAPTION}"
        found = style_tables.findings(draft_with(body, tmp_path))
        assert rules(found) == ["chitragupta.TableUnreferenced"]
        assert found[0]["match"] == "start-here"
        assert "explain" in found[0]["message"]


class TestReferencedOutsideItsSection:
    def test_the_only_reference_sits_in_another_section(self, tmp_path):
        body = f"## One\n\nAs <!-- tableref: start-here --> shows.\n\n## Two\n\n{TABLE}\n{CAPTION}"
        found = style_tables.findings(draft_with(body, tmp_path))
        assert rules(found) == ["chitragupta.TableRefOutsideSection"]

    def test_a_reference_in_the_same_section_is_clean(self, tmp_path):
        body = f"## One\n\nProse.\n\n## Two\n\nAs <!-- tableref: start-here --> shows.\n\n{TABLE}\n{CAPTION}"
        assert style_tables.findings(draft_with(body, tmp_path)) == []

    def test_a_draft_with_no_headings_at_all_has_one_section(self, tmp_path):
        body = f"As <!-- tableref: start-here --> shows.\n\n{TABLE}\n{CAPTION}"
        assert style_tables.findings(draft_with(body, tmp_path)) == []


class TestFindingShape:
    def test_every_finding_carries_what_the_report_prints(self, tmp_path):
        found = style_tables.findings(draft_with(f"# S\n\n{TABLE}", tmp_path))
        assert set(found[0]) == {"rule", "match", "line", "message", "severity", "count"}
        assert found[0]["count"] == 1
        assert found[0]["severity"] == "suggestion"

    def test_a_latex_fragment_is_left_to_its_own_numbering(self, tmp_path):
        # WRITING-STANDARDS.md §13's carve-out: a .tex fragment writes a
        # real \\begin{table} the consuming thesis numbers.
        fragment = tmp_path / "chapter.tex"
        fragment.write_text(
            "\\begin{table}\n\\caption{X}\\label{tab:x}\n\\end{table}\n", encoding="utf-8"
        )
        assert style_tables.findings(fragment) == []

import pytest

from chitragupta import config, dossier
from chitragupta.dossier import _outline


@pytest.fixture
def draft(isolated_config):
    path = config.DRAFTS_DIR / "dt-for-engineers" / "survey.md"
    path.parent.mkdir(parents=True)
    path.write_text("# A survey\n\n## 1. First\n\ntext\n")
    return path


class TestParse:
    def test_a_brief_only_section(self):
        result = _outline.parse(
            "## Failure modes\n\nbrief: Focus on timestep mismatch.\n\n"
            "queries:\n- failure modes co-simulation\n"
        )
        section = result.sections["Failure modes"]
        assert section.brief == "Focus on timestep mismatch."
        assert section.claims == []
        assert section.queries == ["failure modes co-simulation"]
        assert result.problems == []

    def test_a_claim_only_section(self):
        result = _outline.parse(
            "## Why calibration matters\n\nclaim: Calibration dominates prediction error.\n"
        )
        section = result.sections["Why calibration matters"]
        assert section.brief == ""
        assert section.claims == ["Calibration dominates prediction error."]
        assert result.problems == []

    def test_brief_and_claim_combine(self):
        result = _outline.parse(
            "## Family 3: hybrid\n\n"
            "brief: Cover three distinct strategies, not one blur.\n\n"
            "claim: None of the three is universally superior.\n"
        )
        section = result.sections["Family 3: hybrid"]
        assert section.brief == "Cover three distinct strategies, not one blur."
        assert section.claims == ["None of the three is universally superior."]

    def test_multiple_claim_blocks(self):
        result = _outline.parse(
            "## Section\n\nclaim: First assertion.\n\nclaim: Second assertion.\n"
        )
        assert result.sections["Section"].claims == [
            "First assertion.",
            "Second assertion.",
        ]

    def test_a_multi_paragraph_brief(self):
        result = _outline.parse(
            "## Section\n\nbrief: First paragraph.\n\nStill the brief, second paragraph.\n"
        )
        assert result.sections["Section"].brief == (
            "First paragraph.\n\nStill the brief, second paragraph."
        )

    def test_a_section_with_no_queries_is_valid(self):
        result = _outline.parse("## Before you start\n\nbrief: Set expectations only.\n")
        assert result.sections["Before you start"].queries == []
        assert result.problems == []

    def test_a_section_with_neither_brief_nor_claim_is_a_problem(self):
        result = _outline.parse("## Empty section\n\nqueries:\n- something\n")
        assert len(result.problems) == 1
        assert result.problems[0].heading == "Empty section"
        assert "neither a brief" in result.problems[0].problem

    def test_a_second_brief_block_is_a_problem(self):
        result = _outline.parse(
            "## Section\n\nbrief: First.\n\nbrief: Second, which should not be allowed.\n"
        )
        assert any("more than one brief" in p.problem for p in result.problems)

    def test_a_non_bullet_line_under_queries_is_a_problem(self):
        result = _outline.parse("## Section\n\nbrief: text\n\nqueries:\nnot a bullet\n")
        assert any("expects a `- ` bullet" in p.problem for p in result.problems)

    def test_an_empty_brief_mid_edit_is_not_a_problem(self):
        result = _outline.parse("## Section\n\nbrief:\n")
        assert result.sections["Section"].brief == ""
        assert any("neither a brief" in p.problem for p in result.problems)

    def test_deeper_heading_levels_are_sections_too(self):
        result = _outline.parse("### 4.5.1 Corrected physics\n\nbrief: text\n")
        assert "4.5.1 Corrected physics" in result.sections

    def test_a_comment_before_the_first_heading_is_ignored(self):
        result = _outline.parse("<!-- notes to self -->\n\n## Section\n\nbrief: text\n")
        assert list(result.sections) == ["Section"]

    def test_a_multi_line_comment_is_ignored_entirely(self):
        result = _outline.parse(
            "<!-- Some notes.\n"
            "     ## Not a real heading\n"
            "     brief: not a real brief either\n"
            "-->\n\n"
            "## Real section\n\nbrief: real content\n"
        )
        assert list(result.sections) == ["Real section"]
        assert result.problems == []

    def test_the_shipped_outline_template_parses_clean(self):
        from chitragupta.dossier._create import _OUTLINE_TEMPLATE

        result = _outline.parse(_OUTLINE_TEMPLATE)
        assert result.sections == {}
        assert result.problems == []

    def test_a_comment_inside_a_brief_contributes_no_text(self):
        result = _outline.parse(
            "## Section\n\nbrief: before.\n<!-- an aside -->\nstill the brief.\n"
        )
        assert "aside" not in result.sections["Section"].brief
        assert "before." in result.sections["Section"].brief
        assert "still the brief." in result.sections["Section"].brief

    def test_an_unrecognised_line_is_a_problem(self):
        result = _outline.parse("## Section\n\nrandom prose with no label\n")
        assert any("unrecognised line" in p.problem for p in result.problems)

    def test_a_second_paragraph_of_an_open_brief_is_not_unrecognised(self):
        result = _outline.parse("## Section\n\nbrief: text\n\nmore text, same brief\n")
        assert result.sections["Section"].brief == "text\n\nmore text, same brief"
        assert result.problems == []

    def test_empty_text_parses_to_nothing(self):
        result = _outline.parse("")
        assert result.sections == {}
        assert result.problems == []

    def test_a_blank_line_under_queries_is_not_a_problem(self):
        result = _outline.parse("## Section\n\nbrief: text\n\nqueries:\n- one\n\n- two\n")
        assert result.sections["Section"].queries == ["one", "two"]
        assert result.problems == []


class TestDeclaredVsActual:
    def test_no_outline_file_reports_nothing_declared(self, draft):
        dossier.init(draft, "survey")
        drift = _outline.declared_vs_actual(dossier.dossier_dir(draft))
        assert drift.sections == {}
        assert drift.extended == []

    def test_a_declared_query_that_ran_is_reported_run(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "timestep mismatch", 5, 5, 100, origin="declared")
        outline_ = _outline.parse(
            "## Failure modes\n\nbrief: text\n\nqueries:\n- timestep mismatch\n"
        )
        drift = _outline.declared_vs_actual(dossier.dossier_dir(draft), outline_)
        assert drift.sections["Failure modes"].run == ["timestep mismatch"]
        assert drift.sections["Failure modes"].not_run == []

    def test_a_declared_query_never_run_is_reported_not_run(self, draft):
        dossier.init(draft, "survey")
        outline_ = _outline.parse(
            "## Failure modes\n\nbrief: text\n\nqueries:\n- timestep mismatch\n"
        )
        drift = _outline.declared_vs_actual(dossier.dossier_dir(draft), outline_)
        assert drift.sections["Failure modes"].not_run == ["timestep mismatch"]
        assert drift.sections["Failure modes"].run == []

    def test_a_declared_query_that_returned_nothing_is_reported_run_empty(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "timestep mismatch", 5, 0, 0, origin="declared")
        outline_ = _outline.parse(
            "## Failure modes\n\nbrief: text\n\nqueries:\n- timestep mismatch\n"
        )
        drift = _outline.declared_vs_actual(dossier.dossier_dir(draft), outline_)
        assert drift.sections["Failure modes"].run == ["timestep mismatch"]
        assert drift.sections["Failure modes"].run_empty == ["timestep mismatch"]
        assert drift.sections["Failure modes"].not_run == []

    def test_a_declared_query_that_returned_something_is_not_run_empty(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "timestep mismatch", 5, 5, 100, origin="declared")
        outline_ = _outline.parse(
            "## Failure modes\n\nbrief: text\n\nqueries:\n- timestep mismatch\n"
        )
        drift = _outline.declared_vs_actual(dossier.dossier_dir(draft), outline_)
        assert drift.sections["Failure modes"].run_empty == []

    def test_a_query_answered_after_an_empty_first_call_is_not_run_empty(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "timestep mismatch", 5, 0, 0, origin="declared")
        dossier.log_retrieval(draft, "search", "timestep mismatch", 5, 4, 900, origin="declared")
        outline_ = _outline.parse(
            "## Failure modes\n\nbrief: text\n\nqueries:\n- timestep mismatch\n"
        )
        drift = _outline.declared_vs_actual(dossier.dossier_dir(draft), outline_)
        assert drift.sections["Failure modes"].run == ["timestep mismatch"]
        assert drift.sections["Failure modes"].run_empty == []

    def test_a_query_never_run_is_not_reported_run_empty(self, draft):
        dossier.init(draft, "survey")
        outline_ = _outline.parse(
            "## Failure modes\n\nbrief: text\n\nqueries:\n- timestep mismatch\n"
        )
        drift = _outline.declared_vs_actual(dossier.dossier_dir(draft), outline_)
        assert drift.sections["Failure modes"].not_run == ["timestep mismatch"]
        assert drift.sections["Failure modes"].run_empty == []

    def test_a_regrounded_query_that_returned_nothing_is_run_empty(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "timestep mismatch", 5, 0, 0, origin="reground")
        outline_ = _outline.parse(
            "## Failure modes\n\nbrief: text\n\nqueries:\n- timestep mismatch\n"
        )
        drift = _outline.declared_vs_actual(dossier.dossier_dir(draft), outline_)
        assert drift.sections["Failure modes"].run == ["timestep mismatch"]
        assert drift.sections["Failure modes"].run_empty == ["timestep mismatch"]

    def test_an_extended_query_is_reported_flat_not_per_section(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "surrogate model twin", 5, 5, 100, origin="extended")
        outline_ = _outline.parse("## Family 3\n\nbrief: text\n\nqueries:\n- corrected physics\n")
        drift = _outline.declared_vs_actual(dossier.dossier_dir(draft), outline_)
        assert drift.extended == ["surrogate model twin"]
        assert drift.sections["Family 3"].not_run == ["corrected physics"]

    def test_an_unspecified_origin_call_is_neither_run_nor_extended(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "timestep mismatch", 5, 5, 100)
        outline_ = _outline.parse(
            "## Failure modes\n\nbrief: text\n\nqueries:\n- timestep mismatch\n"
        )
        drift = _outline.declared_vs_actual(dossier.dossier_dir(draft), outline_)
        assert drift.sections["Failure modes"].not_run == ["timestep mismatch"]
        assert drift.extended == []

    def test_a_regrounded_query_is_reported_run_and_regrounded(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "timestep mismatch", 5, 5, 100, origin="reground")
        outline_ = _outline.parse(
            "## Failure modes\n\nbrief: text\n\nqueries:\n- timestep mismatch\n"
        )
        drift = _outline.declared_vs_actual(dossier.dossier_dir(draft), outline_)
        assert drift.sections["Failure modes"].run == ["timestep mismatch"]
        assert drift.sections["Failure modes"].not_run == []
        assert drift.regrounded == ["timestep mismatch"]

    def test_regrounded_is_reported_flat_not_per_section(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "surrogate model twin", 5, 5, 100, origin="reground")
        outline_ = _outline.parse("## Family 3\n\nbrief: text\n\nqueries:\n- corrected physics\n")
        drift = _outline.declared_vs_actual(dossier.dossier_dir(draft), outline_)
        assert drift.regrounded == ["surrogate model twin"]
        assert drift.sections["Family 3"].not_run == ["corrected physics"]

    def test_an_unspecified_origin_is_still_neither_run_nor_regrounded(self, draft):
        dossier.init(draft, "survey")
        dossier.log_retrieval(draft, "search", "timestep mismatch", 5, 5, 100)
        outline_ = _outline.parse(
            "## Failure modes\n\nbrief: text\n\nqueries:\n- timestep mismatch\n"
        )
        drift = _outline.declared_vs_actual(dossier.dossier_dir(draft), outline_)
        assert drift.sections["Failure modes"].not_run == ["timestep mismatch"]
        assert drift.regrounded == []

    def test_a_claim_only_section_with_no_queries_still_appears_in_drift(self, draft):
        dossier.init(draft, "survey")
        outline_ = _outline.parse(
            "## Why calibration matters\n\nclaim: Calibration dominates prediction error.\n"
        )
        drift = _outline.declared_vs_actual(dossier.dossier_dir(draft), outline_)
        assert "Why calibration matters" in drift.sections
        assert drift.sections["Why calibration matters"].run == []
        assert drift.sections["Why calibration matters"].not_run == []

    def test_reads_the_dossiers_own_outline_file_when_none_is_passed(self, draft):
        dossier.init(draft, "survey")
        path = dossier.dossier_dir(draft) / "outline.md"
        path.write_text("## Failure modes\n\nbrief: text\n\nqueries:\n- timestep mismatch\n")
        dossier.log_retrieval(draft, "search", "timestep mismatch", 5, 5, 100, origin="declared")
        drift = _outline.declared_vs_actual(dossier.dossier_dir(draft))
        assert drift.sections["Failure modes"].run == ["timestep mismatch"]


class TestOutlineCli:
    def test_no_outline_file_exits_nonzero(self, draft, capsys):
        dossier.init(draft, "survey")
        assert dossier.main(["outline", str(draft)]) == 1
        assert "No outline.md" in capsys.readouterr().err

    def test_prints_the_parsed_sections(self, draft, capsys):
        dossier.init(draft, "survey")
        path = dossier.dossier_dir(draft) / "outline.md"
        path.write_text("## Failure modes\n\nbrief: Focus on timestep mismatch.\n")
        assert dossier.main(["outline", str(draft)]) == 0
        out = capsys.readouterr().out
        assert "Failure modes" in out
        assert "Focus on timestep mismatch." in out

    def test_prints_claims_and_queries_for_a_brief_less_section(self, draft, capsys):
        dossier.init(draft, "survey")
        path = dossier.dossier_dir(draft) / "outline.md"
        path.write_text(
            "## Why calibration matters\n\nclaim: Calibration dominates error.\n\n"
            "queries:\n- calibration error\n"
        )
        assert dossier.main(["outline", str(draft)]) == 0
        out = capsys.readouterr().out
        assert "claim: Calibration dominates error." in out
        assert "query: calibration error" in out

    def test_check_suppresses_the_printed_sections(self, draft, capsys):
        dossier.init(draft, "survey")
        path = dossier.dossier_dir(draft) / "outline.md"
        path.write_text("## Failure modes\n\nbrief: text\n")
        assert dossier.main(["outline", str(draft), "--check"]) == 0
        assert "Failure modes" not in capsys.readouterr().out

    def test_a_malformed_file_exits_nonzero_and_reports_why(self, draft, capsys):
        dossier.init(draft, "survey")
        path = dossier.dossier_dir(draft) / "outline.md"
        path.write_text("## Empty section\n\nqueries:\n- something\n")
        assert dossier.main(["outline", str(draft)]) == 1
        assert "neither a brief" in capsys.readouterr().err

    def test_the_freshly_created_skeleton_passes_check(self, draft, capsys):
        assert dossier.main(["init", str(draft), "--genre", "survey", "--outline"]) == 0
        assert dossier.main(["outline", str(draft), "--check"]) == 0
        assert "0 section(s), 0 problem(s)" in capsys.readouterr().err


class TestTheTitleLineIsNotASection:
    def test_a_leading_level_one_title_is_not_a_section(self):
        result = _outline.parse(
            "# Survey outline\n\n## Failure modes\n\nbrief: Focus on timestep mismatch.\n"
        )
        assert list(result.sections) == ["Failure modes"]
        assert result.problems == []

    def test_level_two_and_deeper_are_still_sections(self):
        result = _outline.parse("## Failure modes\n\nbrief: One.\n\n### Sub-case\n\nbrief: Two.\n")
        assert list(result.sections) == ["Failure modes", "Sub-case"]
        assert result.problems == []

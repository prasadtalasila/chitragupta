from pathlib import Path

from chitragupta import style_typeset
from tests.conftest import draft_with

WIDE = "x" * (style_typeset.MAX_CODE_COLUMNS + 1)
FITS = "x" * style_typeset.MAX_CODE_COLUMNS
URL = "https://github.com/INTO-CPS-Association/plant-controller"


def rules(findings: list[dict]) -> list[str]:
    return [finding["rule"] for finding in findings]


class TestWideCodeLine:
    def test_a_line_over_the_limit_is_reported(self, tmp_path):
        found = style_typeset.findings(draft_with(f"# S\n\n```\n{WIDE}\n```\n", tmp_path))
        assert rules(found) == ["chitragupta.WideCodeLine"]
        assert found[0]["line"] == 4

    def test_a_line_exactly_at_the_limit_is_not(self, tmp_path):
        assert style_typeset.findings(draft_with(f"# S\n\n```\n{FITS}\n```\n", tmp_path)) == []

    def test_the_fence_delimiters_are_not_content(self, tmp_path):
        body = f"# S\n\n```{'p' * 200}\n{FITS}\n```\n"
        assert style_typeset.findings(draft_with(body, tmp_path)) == []

    def test_the_message_names_the_actual_width(self, tmp_path):
        found = style_typeset.findings(draft_with(f"# S\n\n```\n{WIDE}\n```\n", tmp_path))
        assert f"{len(WIDE)} columns wide" in found[0]["message"]

    def test_a_tilde_fence_counts_too(self, tmp_path):
        body = f"# S\n\n~~~\n{WIDE}\n~~~\n"
        assert rules(style_typeset.findings(draft_with(body, tmp_path))) == [
            "chitragupta.WideCodeLine"
        ]

    def test_a_long_prose_line_is_not_a_finding(self, tmp_path):
        assert style_typeset.findings(draft_with(f"# S\n\n{WIDE} and more.\n", tmp_path)) == []


class TestBareUrl:
    def test_an_unmarked_url_in_prose_is_reported(self, tmp_path):
        found = style_typeset.findings(draft_with(f"# S\n\nSee {URL} for more.\n", tmp_path))
        assert rules(found) == ["chitragupta.BareUrl"]
        assert found[0]["line"] == 3

    def test_a_markdown_link_is_not(self, tmp_path):
        body = f"# S\n\nSee [the controller repo]({URL}) for more.\n"
        assert style_typeset.findings(draft_with(body, tmp_path)) == []

    def test_a_reference_style_definition_is_not(self, tmp_path):
        body = f"# S\n\nSee [the repo][r].\n\n[r]: {URL}\n"
        assert style_typeset.findings(draft_with(body, tmp_path)) == []

    def test_an_autolink_is_still_a_bare_url(self, tmp_path):
        found = style_typeset.findings(draft_with(f"# S\n\nSee <{URL}>.\n", tmp_path))
        assert rules(found) == ["chitragupta.BareUrl"]

    def test_the_reported_match_excludes_the_sentences_punctuation(self, tmp_path):
        body = f"# S\n\nSee {URL}. Then <{URL}>. Then ({URL}).\n"
        found = style_typeset.findings(draft_with(body, tmp_path))
        assert [f["match"] for f in found] == [URL, URL, URL]

    def test_a_trailing_slash_is_part_of_the_url(self, tmp_path):
        found = style_typeset.findings(
            draft_with("# S\n\nSee https://example.com/ now.\n", tmp_path)
        )
        assert [f["match"] for f in found] == ["https://example.com/"]


class TestACodeSpanIsNotAutomaticallyProse:
    def test_a_span_that_is_only_a_url_is_reported(self, tmp_path):
        found = style_typeset.findings(draft_with(f"# S\n\nSpend time with `{URL}`.\n", tmp_path))
        assert rules(found) == ["chitragupta.BareUrl"]

    def test_a_span_holding_a_command_is_left_alone(self, tmp_path):
        body = f"# S\n\nRun `curl {URL}` first.\n"
        assert style_typeset.findings(draft_with(body, tmp_path)) == []

    def test_a_url_inside_a_fence_is_left_alone(self, tmp_path):
        body = f"# S\n\n```\ncurl {URL}\n```\n"
        assert style_typeset.findings(draft_with(body, tmp_path)) == []


class TestExemptions:
    def test_a_url_in_a_block_quotation_is_not_reported(self, tmp_path):
        assert style_typeset.findings(draft_with(f"# S\n\n> As they say, {URL}\n", tmp_path)) == []

    def test_a_url_in_the_references_section_is_not_reported(self, tmp_path):
        body = f"# S\n\nProse.\n\n## References\n\n[1] A. Author, {URL}\n"
        assert style_typeset.findings(draft_with(body, tmp_path)) == []

    def test_a_further_reading_heading_counts_as_references(self, tmp_path):
        body = f"# S\n\nProse.\n\n## Further reading\n\n[1] A. Author, {URL}\n"
        assert style_typeset.findings(draft_with(body, tmp_path)) == []

    def test_a_url_after_the_references_section_ends_is_reported_again(self, tmp_path):
        body = f"# S\n\n## References\n\n[1] A. Author.\n\n## Appendix\n\nSee {URL}.\n"
        assert rules(style_typeset.findings(draft_with(body, tmp_path))) == ["chitragupta.BareUrl"]


class TestATexFragmentGetsTheWidthCheckOnly:
    def _tex(self, body: str, tmp_path: Path) -> Path:
        path = tmp_path / "chapter.tex"
        path.write_text(body, encoding="utf-8")
        return path

    def test_a_wide_verbatim_line_is_reported(self, tmp_path):
        body = f"\\section{{S}}\n\n\\begin{{verbatim}}\n{WIDE}\n\\end{{verbatim}}\n"
        found = style_typeset.findings(self._tex(body, tmp_path))
        assert rules(found) == ["chitragupta.WideCodeLine"]
        assert found[0]["line"] == 4

    def test_the_message_names_the_preamble_this_pipeline_cannot_change(self, tmp_path):
        body = f"\\section{{S}}\n\n\\begin{{verbatim}}\n{WIDE}\n\\end{{verbatim}}\n"
        found = style_typeset.findings(self._tex(body, tmp_path))
        assert "preamble this pipeline may not change" in found[0]["message"]

    def test_a_fitting_verbatim_line_is_not(self, tmp_path):
        body = f"\\section{{S}}\n\n\\begin{{verbatim}}\n{FITS}\n\\end{{verbatim}}\n"
        assert style_typeset.findings(self._tex(body, tmp_path)) == []

    def test_lstlisting_counts_too(self, tmp_path):
        body = f"\\section{{S}}\n\n\\begin{{lstlisting}}\n{WIDE}\n\\end{{lstlisting}}\n"
        assert rules(style_typeset.findings(self._tex(body, tmp_path))) == [
            "chitragupta.WideCodeLine"
        ]

    def test_a_bare_url_in_tex_prose_is_not_reported(self, tmp_path):
        assert style_typeset.findings(self._tex(f"\\section{{S}}\n\nSee {URL}.\n", tmp_path)) == []

    def test_wide_prose_in_tex_is_not_a_finding(self, tmp_path):
        assert (
            style_typeset.findings(self._tex(f"\\section{{S}}\n\n{WIDE} more.\n", tmp_path)) == []
        )


class TestScope:
    def test_a_draft_with_neither_problem_reports_nothing(self, tmp_path):
        body = f"# S\n\nSee [the repo]({URL}).\n\n```\n{FITS}\n```\n"
        assert style_typeset.findings(draft_with(body, tmp_path)) == []

    def test_findings_are_ordered_by_line(self, tmp_path):
        body = f"# S\n\n```\n{WIDE}\n```\n\nThen see {URL}.\n"
        found = style_typeset.findings(draft_with(body, tmp_path))
        assert [f["line"] for f in found] == sorted(f["line"] for f in found)
        assert len(found) == 2

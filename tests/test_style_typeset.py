"""chitragupta/style_typeset.py: the typesetting findings `draft style` reports.

Beside `tests/test_style_tables.py` and its siblings, the fifth finding
in that command computed in Python rather than by Vale.

The discriminating tests are `TestExemptions` and
`TestACodeSpanIsNotAutomaticallyProse`: the first is what
docs/WRITING-STANDARDS.md §9's quoted-span carve-out asks for, and the
second is the distinction the bare-URL rule turns on -- a code span that
*is* a URL is a URL being shown to a reader, and one that merely
contains a URL is a command whose text a link would corrupt.

`MAX_CODE_COLUMNS` is read from the module rather than written as a
literal here: it was measured from `pdflatex` at two geometries, and a
test asserting its value in a second place would just be a copy to keep
in step.
"""

from pathlib import Path

from chitragupta import style_typeset

WIDE = "x" * (style_typeset.MAX_CODE_COLUMNS + 1)
FITS = "x" * style_typeset.MAX_CODE_COLUMNS
URL = "https://github.com/INTO-CPS-Association/plant-controller"


def draft_with(body: str, tmp_path: Path) -> Path:
    path = tmp_path / "survey.md"
    path.write_text(body, encoding="utf-8")
    return path


def rules(findings: list[dict]) -> list[str]:
    return [finding["rule"] for finding in findings]


class TestWideCodeLine:
    def test_a_line_over_the_limit_is_reported(self, tmp_path):
        found = style_typeset.findings(draft_with(f"# S\n\n```\n{WIDE}\n```\n", tmp_path))
        assert rules(found) == ["chitragupta.WideCodeLine"]
        assert found[0]["line"] == 4

    def test_a_line_exactly_at_the_limit_is_not(self, tmp_path):
        # The boundary is the whole point of the number: this width was
        # measured to fit, so reporting it would be a false finding on
        # every draft that sits at the limit deliberately.
        assert style_typeset.findings(draft_with(f"# S\n\n```\n{FITS}\n```\n", tmp_path)) == []

    def test_the_fence_delimiters_are_not_content(self, tmp_path):
        # An info string can be any length -- it never renders -- so a
        # long one must not be measured as if it were a code line.
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
        # Prose reflows; only a verbatim line cannot. Reporting prose
        # width would fire on every draft that does not hard-wrap.
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
        # `<url>` is clickable but still shows the reader a raw URL,
        # which is the half of §14 this rule is about.
        found = style_typeset.findings(draft_with(f"# S\n\nSee <{URL}>.\n", tmp_path))
        assert rules(found) == ["chitragupta.BareUrl"]

    def test_the_reported_match_excludes_the_sentences_punctuation(self, tmp_path):
        # A finding that misquotes the URL it is about is one an author
        # has to read twice; `\\S+` swallowed the `>` and the full stop.
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
        # The real case: chapter 1 of this project's own book showed the
        # repo URL this way, and a link reads better than monospace.
        found = style_typeset.findings(draft_with(f"# S\n\nSpend time with `{URL}`.\n", tmp_path))
        assert rules(found) == ["chitragupta.BareUrl"]

    def test_a_span_holding_a_command_is_left_alone(self, tmp_path):
        # Rewriting this as a link would corrupt the command it prints.
        body = f"# S\n\nRun `curl {URL}` first.\n"
        assert style_typeset.findings(draft_with(body, tmp_path)) == []

    def test_a_url_inside_a_fence_is_left_alone(self, tmp_path):
        body = f"# S\n\n```\ncurl {URL}\n```\n"
        assert style_typeset.findings(draft_with(body, tmp_path)) == []


class TestExemptions:
    """docs/WRITING-STANDARDS.md §9: quoted spans are exempt from every
    row, and this module has two of them to honour -- kept in step with
    `assets/vale/vale.ini`'s `BlockIgnores`, which excludes the same
    regions from every Vale rule."""

    def test_a_url_in_a_block_quotation_is_not_reported(self, tmp_path):
        # A draft quotes its sources by construction; the source's own
        # text is not this draft's to rewrite.
        assert style_typeset.findings(draft_with(f"# S\n\n> As they say, {URL}\n", tmp_path)) == []

    def test_a_url_in_the_references_section_is_not_reported(self, tmp_path):
        # references.py splices bibliography URLs out of the ledger.
        body = f"# S\n\nProse.\n\n## References\n\n[1] A. Author, {URL}\n"
        assert style_typeset.findings(draft_with(body, tmp_path)) == []

    def test_a_further_reading_heading_counts_as_references(self, tmp_path):
        body = f"# S\n\nProse.\n\n## Further reading\n\n[1] A. Author, {URL}\n"
        assert style_typeset.findings(draft_with(body, tmp_path)) == []

    def test_a_url_after_the_references_section_ends_is_reported_again(self, tmp_path):
        # The exemption is the section, not the rest of the file.
        body = f"# S\n\n## References\n\n[1] A. Author.\n\n## Appendix\n\nSee {URL}.\n"
        assert rules(style_typeset.findings(draft_with(body, tmp_path))) == ["chitragupta.BareUrl"]


class TestScope:
    def test_a_tex_fragment_is_out_of_scope(self, tmp_path):
        # Same carve-out style_tables.py and style_figures.py make: a
        # .tex fragment writes \\begin{verbatim} and \\href{}, neither of
        # which is the markup checked here.
        path = tmp_path / "chapter.tex"
        path.write_text(f"\\section{{S}}\n\nSee {URL}.\n", encoding="utf-8")
        assert style_typeset.findings(path) == []

    def test_a_draft_with_neither_problem_reports_nothing(self, tmp_path):
        body = f"# S\n\nSee [the repo]({URL}).\n\n```\n{FITS}\n```\n"
        assert style_typeset.findings(draft_with(body, tmp_path)) == []

    def test_findings_are_ordered_by_line(self, tmp_path):
        body = f"# S\n\n```\n{WIDE}\n```\n\nThen see {URL}.\n"
        found = style_typeset.findings(draft_with(body, tmp_path))
        assert [f["line"] for f in found] == sorted(f["line"] for f in found)
        assert len(found) == 2

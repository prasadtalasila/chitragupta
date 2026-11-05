"""chitragupta/style_bare_citekeys.py: a ledger citekey printed raw (#1119).

The negatives are the measured ones: over 77 real drafts a plain token
match found 786 bare keys and 785 were the References section's
`` [n] entry `key` `` labels or keys inside `<!-- single-source -->`
comments, neither of which a reader ever sees.
"""

import pytest

from chitragupta import ledger, style_bare_citekeys
from tests.conftest import add_citable, draft_with, make_reference

RULE = "chitragupta.BareCitekey"


@pytest.fixture
def corpus(ledger_con):
    for key in ("gil_survey_2024", "obaidat_hubcap_2022", "doe_2024", "doe_2024-1", "smith"):
        add_citable(ledger_con, key)
    ledger.upsert_reference(ledger_con, make_reference(citekey="web_page_2024"))
    return ledger_con


def found(draft):
    return [(f["line"], f["match"], f["repair"]) for f in style_bare_citekeys.findings(draft)]


class TestTheIssuesDraft:
    def test_a_dropped_at_and_a_code_span_are_both_reported(self, corpus, tmp_path):
        draft = draft_with(
            "# Bare key scratch\n\n"
            "The open-source frameworks gil_survey_2024 evaluates are listed in "
            "Table 1 [@gil_survey_2024].\n\n"
            "The corpus holds a duplicate, `obaidat_hubcap_2022`.\n",
            tmp_path,
        )
        assert found(draft) == [
            (3, "gil_survey_2024", "edit"),
            (5, "obaidat_hubcap_2022", "review"),
        ]

    def test_the_prose_repair_names_the_ieee_citation_to_write(self, corpus, tmp_path):
        draft = draft_with("Frameworks gil_survey_2024 evaluates.\n", tmp_path)
        (finding,) = style_bare_citekeys.findings(draft)
        assert finding["rule"] == RULE
        assert "[@gil_survey_2024]" in finding["message"]

    def test_the_code_span_message_points_at_revisions_md(self, corpus, tmp_path):
        draft = draft_with("A duplicate, `obaidat_hubcap_2022`.\n", tmp_path)
        (finding,) = style_bare_citekeys.findings(draft)
        assert "revisions.md" in finding["message"]


class TestWhatAReaderNeverSees:
    @pytest.mark.parametrize(
        "body",
        [
            "Cited [@gil_survey_2024].\n",
            "As @gil_survey_2024 shows.\n",
            "Cited [-@gil_survey_2024].\n",
            "Cited [see @gil_survey_2024, p. 3; @doe_2024].\n",
            "Braced @{gil_survey_2024}.\n",
            "Raw \\citep{gil_survey_2024}.\n",
            "<!-- single-source: only gil_survey_2024 in this packet -->\nProse.\n",
            "<!-- single-source: only `gil_survey_2024` here -->\nProse.\n",
            "```\npython -m chitragupta.draft gate gil_survey_2024\n```\n",
            "A [link](https://example.org/gil_survey_2024) here.\n",
            "A smith walked in.\n",
        ],
    )
    def test_nothing_is_reported(self, corpus, tmp_path, body):
        assert found(draft_with(body, tmp_path)) == []

    def test_the_references_sections_labels_are_not_reported(self, corpus, tmp_path):
        draft = draft_with(
            "# Survey\n\nCited [@gil_survey_2024].\n\n## 12. References\n\n"
            '[1] J. Gil, "A Survey," 2024. `gil_survey_2024`\n\n'
            "## Appendix\n\nThe duplicate obaidat_hubcap_2022.\n",
            tmp_path,
        )
        assert found(draft) == [(11, "obaidat_hubcap_2022", "edit")]

    def test_a_key_is_not_found_inside_a_longer_one(self, corpus, tmp_path):
        draft = draft_with("See doe_2024-1 here.\n", tmp_path)
        assert found(draft) == [(1, "doe_2024-1", "edit")]

    def test_an_emphasised_key_is_still_reported(self, corpus, tmp_path):
        # PANDOC_KEY may open with `*`, so `*doe_2024*` matched as
        # `*doe_2024` and was never looked up (final review).
        draft = draft_with("Emphasis *doe_2024* and **gil_survey_2024**.\n", tmp_path)
        assert found(draft) == [(1, "doe_2024", "edit"), (1, "gil_survey_2024", "edit")]

    def test_a_word_that_only_starts_like_a_key_is_not_one(self, corpus, tmp_path):
        assert found(draft_with("The doe_2024_draft file.\n", tmp_path)) == []


class TestAKeyThatCannotBeCited:
    def test_an_unparsed_key_in_prose_is_left_to_a_person(self, corpus, tmp_path):
        draft = draft_with("The page web_page_2024 says so.\n", tmp_path)
        (finding,) = style_bare_citekeys.findings(draft)
        assert finding["repair"] == "review"
        assert "status no_pdf" in finding["message"]
        assert "[@web_page_2024]" not in finding["message"]


class TestATexUnit:
    def test_an_escaped_key_in_prose_is_reported_with_citep(self, corpus, tmp_path):
        draft = tmp_path / "chapter.tex"
        draft.write_text(
            "Intro.\n% gil_survey_2024 in a comment\n"
            "The frameworks gil\\_survey\\_2024 evaluates \\citep{doe_2024}.\n"
        )
        (finding,) = style_bare_citekeys.findings(draft)
        assert (finding["line"], finding["match"], finding["repair"]) == (
            3,
            "gil_survey_2024",
            "edit",
        )
        assert "\\citep{gil_survey_2024}" in finding["message"]

    def test_a_texttt_key_is_the_code_span_case(self, corpus, tmp_path):
        draft = tmp_path / "chapter.tex"
        draft.write_text("A duplicate, \\texttt{obaidat\\_hubcap\\_2022}.\n")
        assert found(draft) == [(1, "obaidat_hubcap_2022", "review")]


class TestNoLedger:
    def test_no_ledger_gives_no_findings(self, isolated_config, tmp_path):
        assert found(draft_with("Frameworks gil_survey_2024 evaluates.\n", tmp_path)) == []

import re

import pytest

from chitragupta import ledger, overlap_index, overlap_source_text
from tests.conftest import parsed_text
from tests.conftest import make_reference


def _parsed(ledger_con, tmp_path, citekey, text):
    pdf = tmp_path / f"{citekey}.pdf"
    pdf.write_bytes(b"%PDF-1.4 dummy")
    parsed = parsed_text(citekey, text)
    ledger.upsert_reference(ledger_con, make_reference(citekey=citekey, pdf_path=str(pdf)))
    ledger.mark_parsed(ledger_con, citekey, parsed)


class TestTheTokenisationMatchesTheIndexs:
    @pytest.mark.parametrize(
        "text",
        [
            "Configuration data is sent to the machine's DT via its HTTP Adapter.",
            'MiXeD-case, punctuation--heavy; e.g. "quoted" text and 3rd numerals.',
            "Section VI-A, IEEE 802.11, ISO/IEC 23247-1.",
            "",
            "!!! --- ...",
            "trailing whitespace   \n\n and newlines\t",
        ],
    )
    def test_it_agrees_with_norm_token_for_token(self, text):
        raw = [m.group().lower() for m in overlap_source_text._RAW_WORD.finditer(text)]
        assert raw == overlap_index._norm(text)

    def test_the_indexs_own_word_pattern_would_not_do(self):
        assert overlap_index.WORD.findall("Configuration") == ["onfiguration"]
        assert [m.group() for m in overlap_source_text._RAW_WORD.finditer("Configuration")] == [
            "Configuration"
        ]


class TestRecoveringAPassage:
    def test_it_returns_the_documents_own_text_not_a_normalised_form(self, ledger_con, tmp_path):
        _parsed(ledger_con, tmp_path, "src_2024", "Alpha beta, the machine's DT gamma delta.")

        assert overlap_source_text.source_span("src_2024", 2, 6) == "the machine's DT"

    def test_a_single_token_range_works(self, ledger_con, tmp_path):
        _parsed(ledger_con, tmp_path, "src_2024", "Alpha Beta Gamma.")
        assert overlap_source_text.source_span("src_2024", 1, 2) == "Beta"

    def test_positions_are_global_across_pages_not_reset_per_page(self, ledger_con, tmp_path):
        _parsed(ledger_con, tmp_path, "src_2024", "one two three\ffour five six")
        assert overlap_source_text.source_span("src_2024", 3, 5) == "four five"

    def test_a_range_straddling_a_page_break_returns_both_sides(self, ledger_con, tmp_path):
        _parsed(ledger_con, tmp_path, "src_2024", "one two three\ffour five six")
        assert overlap_source_text.source_span("src_2024", 1, 5) == "two three four five"

    def test_a_range_running_past_the_end_returns_the_prefix_that_exists(
        self, ledger_con, tmp_path
    ):
        _parsed(ledger_con, tmp_path, "src_2024", "one two three")
        assert overlap_source_text.source_span("src_2024", 1, 99) == "two three"


class TestWhenThereIsNothingToReturn:
    def test_an_unknown_citekey_is_none(self, ledger_con, tmp_path):
        _parsed(ledger_con, tmp_path, "src_2024", "one two three")
        assert overlap_source_text.source_span("absent_2024", 0, 2) is None

    def test_no_ledger_at_all_is_none(self, isolated_config):
        assert overlap_source_text.source_span("src_2024", 0, 2) is None

    def test_a_range_entirely_past_the_document_is_none(self, ledger_con, tmp_path):
        _parsed(ledger_con, tmp_path, "src_2024", "one two three")
        assert overlap_source_text.source_span("src_2024", 50, 60) is None

    def test_an_empty_or_inverted_range_is_none(self, ledger_con, tmp_path):
        _parsed(ledger_con, tmp_path, "src_2024", "one two three")
        assert overlap_source_text.source_span("src_2024", 2, 2) is None
        assert overlap_source_text.source_span("src_2024", 3, 1) is None

    def test_a_document_with_no_words_is_none(self, ledger_con, tmp_path):
        _parsed(ledger_con, tmp_path, "src_2024", "--- !!! ...")
        assert overlap_source_text.source_span("src_2024", 0, 3) is None


class TestTheCache:
    def test_one_parse_per_citekey_per_process(self, ledger_con, tmp_path, monkeypatch):
        _parsed(ledger_con, tmp_path, "src_2024", "one two three four")
        reads = self._counted_reads(monkeypatch)

        for _ in range(5):
            assert overlap_source_text.source_span("src_2024", 0, 2) == "one two"

        assert len(reads) == 1

    def test_reparsed_text_under_the_same_citekey_is_not_served_stale(
        self, ledger_con, tmp_path, monkeypatch
    ):
        _parsed(ledger_con, tmp_path, "src_2024", "one two three")
        assert overlap_source_text.source_span("src_2024", 0, 2) == "one two"

        _parsed(ledger_con, tmp_path, "src_2024", "ALPHA BETA GAMMA")

        assert overlap_source_text.source_span("src_2024", 0, 2) == "ALPHA BETA"

    def test_an_unchanged_source_is_still_only_parsed_once(self, ledger_con, tmp_path, monkeypatch):
        _parsed(ledger_con, tmp_path, "src_2024", "one two three four")
        assert overlap_source_text.source_span("src_2024", 0, 2) == "one two"
        reads = self._counted_reads(monkeypatch)

        assert overlap_source_text.source_span("src_2024", 2, 4) == "three four"

        assert reads == []

    def _counted_reads(self, monkeypatch):
        reads = []
        original = overlap_index._pages_from_parsed_text
        monkeypatch.setattr(
            overlap_index,
            "_pages_from_parsed_text",
            lambda path: (reads.append(path), original(path))[1],
        )
        return reads


class TestAgainstTheRealTokenStream:
    def test_a_span_recovered_by_position_matches_the_index_tokenisation(
        self, ledger_con, tmp_path
    ):
        text = "The shadowing function of the DT validates the request, as detailed in VI-A."
        _parsed(ledger_con, tmp_path, "src_2024", text)
        tokens = overlap_index._norm(text)

        recovered = overlap_source_text.source_span("src_2024", 4, 9)

        assert overlap_index._norm(recovered) == tokens[4:9]
        assert recovered == "the DT validates the request"
        assert re.search(r"[A-Z]", recovered)

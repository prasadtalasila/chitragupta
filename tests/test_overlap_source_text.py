"""`overlap_source_text.source_span` -- the source document's own text
behind a range of global token positions.

The lexical tiers index a document as one continuous normalised word
stream and keep only positions; this is what turns a position back into
something a reader can be shown beside the draft.
"""

import re

import pytest

from chitragupta import ledger, overlap_index, overlap_source_text
from tests.conftest import make_reference


def _parsed(ledger_con, tmp_path, citekey, text):
    pdf = tmp_path / f"{citekey}.pdf"
    pdf.write_bytes(b"%PDF-1.4 dummy")
    parsed = tmp_path / f"{citekey}.txt"
    parsed.write_text(text, encoding="utf-8")
    ledger.upsert_reference(ledger_con, make_reference(citekey=citekey, pdf_path=str(pdf)))
    ledger.mark_parsed(ledger_con, citekey, parsed)


class TestTheTokenisationMatchesTheIndexs:
    """The whole module rests on this: a second tokeniser is used, so it
    has to partition every string exactly the way `overlap_index._norm`
    does, or a position means a different word here than it does in the
    index and the wrong passage is returned -- silently, and looking
    entirely plausible.
    """

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
        """`overlap_index.WORD` is `[a-z0-9]+` and is only ever applied to
        already-lowercased text. Against raw text it does not merely miss
        a capital, it *splits* on one -- which is why this module carries
        its own pattern rather than importing that one."""
        assert overlap_index.WORD.findall("Configuration") == ["onfiguration"]
        assert [m.group() for m in overlap_source_text._RAW_WORD.finditer("Configuration")] == [
            "Configuration"
        ]


class TestRecoveringAPassage:
    def test_it_returns_the_documents_own_text_not_a_normalised_form(self, ledger_con, tmp_path):
        _parsed(ledger_con, tmp_path, "src_2024", "Alpha beta, the machine's DT gamma delta.")

        # tokens: alpha(0) beta(1) the(2) machine(3) s(4) dt(5) gamma(6)
        assert overlap_source_text.source_span("src_2024", 2, 6) == "the machine's DT"

    def test_a_single_token_range_works(self, ledger_con, tmp_path):
        _parsed(ledger_con, tmp_path, "src_2024", "Alpha Beta Gamma.")
        assert overlap_source_text.source_span("src_2024", 1, 2) == "Beta"

    def test_positions_are_global_across_pages_not_reset_per_page(self, ledger_con, tmp_path):
        """`overlap_index._build_fingerprint` tokenises the whole document
        as one stream and never resets at a form feed, so a caller's
        position is global. Counting per page here would return a
        different passage for every position past page one."""
        _parsed(ledger_con, tmp_path, "src_2024", "one two three\ffour five six")
        assert overlap_source_text.source_span("src_2024", 3, 5) == "four five"

    def test_a_range_straddling_a_page_break_returns_both_sides(self, ledger_con, tmp_path):
        """Picking one side would truncate the passage the reader is
        being asked to compare against."""
        _parsed(ledger_con, tmp_path, "src_2024", "one two three\ffour five six")
        assert overlap_source_text.source_span("src_2024", 1, 5) == "two three four five"

    def test_a_range_running_past_the_end_returns_the_prefix_that_exists(
        self, ledger_con, tmp_path
    ):
        _parsed(ledger_con, tmp_path, "src_2024", "one two three")
        assert overlap_source_text.source_span("src_2024", 1, 99) == "two three"


class TestWhenThereIsNothingToReturn:
    """`None` for every failure, never `""`: an empty string renders as a
    source passage that exists and is blank, which is a different and
    false claim.
    """

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
        """A draft with forty findings against one source would otherwise
        re-read and re-tokenise the whole parsed text forty times."""
        _parsed(ledger_con, tmp_path, "src_2024", "one two three four")
        reads = self._counted_reads(monkeypatch)

        for _ in range(5):
            assert overlap_source_text.source_span("src_2024", 0, 2) == "one two"

        assert len(reads) == 1

    def test_reparsed_text_under_the_same_citekey_is_not_served_stale(
        self, ledger_con, tmp_path, monkeypatch
    ):
        """`sync --reparse` and a `[parser].backend` switch both rewrite
        `content/parsed/<citekey>.txt` without touching the PDF, so a
        cache keyed on the citekey alone would keep serving spans into
        text that no longer exists -- the same failure `overlap_index`'s
        own doc cache keys against `(pdf_hash, size, mtime_ns)` to
        avoid."""
        _parsed(ledger_con, tmp_path, "src_2024", "one two three")
        assert overlap_source_text.source_span("src_2024", 0, 2) == "one two"

        _parsed(ledger_con, tmp_path, "src_2024", "ALPHA BETA GAMMA")

        assert overlap_source_text.source_span("src_2024", 0, 2) == "ALPHA BETA"

    def test_an_unchanged_source_is_still_only_parsed_once(self, ledger_con, tmp_path, monkeypatch):
        """The validity key must not defeat the cache it guards: the
        common case is many findings against one untouched source."""
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
        """End to end, without hardcoding indices: normalise the whole
        document the way the index does, pick a range, and check the
        recovered text normalises back to exactly those tokens.
        """
        text = "The shadowing function of the DT validates the request, as detailed in VI-A."
        _parsed(ledger_con, tmp_path, "src_2024", text)
        tokens = overlap_index._norm(text)

        recovered = overlap_source_text.source_span("src_2024", 4, 9)

        assert overlap_index._norm(recovered) == tokens[4:9]
        # And it is the real text, not the normalised stream re-joined.
        assert recovered == "the DT validates the request"
        assert re.search(r"[A-Z]", recovered)

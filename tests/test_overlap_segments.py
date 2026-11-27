import json
import re

import pytest

from chitragupta import config, overlap_segments
from chitragupta.review import verbatim_check as vc
from tests.conftest import add_citable, make_reference


def segments(text, mapping):
    words, _ = vc._tokenize_draft(text)
    found, _unmatched = overlap_segments.draft_sections(
        text, [(w.char, w.char_end) for w in words], mapping
    )
    return found


class TestDraftSections:
    def test_a_section_carries_the_citekeys_its_dossier_records(self):
        text = "# Title\n\nBody prose here, several words long.\n"
        [section] = segments(text, {"Title": ["smith_2024"]})
        assert section.title == "Title"
        assert section.citekeys == ["smith_2024"]

    def test_a_section_with_no_recorded_citekeys_is_dropped(self):
        text = "# Kept\n\nProse.\n\n# Dropped\n\nMore prose.\n"
        titles = [s.title for s in segments(text, {"Kept": ["smith_2024"]})]
        assert titles == ["Kept"]

    def test_a_heading_the_dossier_does_not_name_is_dropped(self):
        text = "# Renamed Since\n\nProse.\n"
        assert segments(text, {"Old Name": ["smith_2024"]}) == []

    def test_word_offsets_index_the_scans_own_word_stream(self):
        text = "# Title\n\nAlpha beta gamma delta epsilon.\n"
        [section] = segments(text, {"Title": ["k_2024"]})
        words, _ = vc._tokenize_draft(text)
        word_strs = [w.text for w in words]
        [segment] = section.sentences
        assert word_strs[segment.word_start : segment.word_end] == [
            "alpha",
            "beta",
            "gamma",
            "delta",
            "epsilon",
        ]

    def test_prose_and_the_bullets_under_it_are_separate_segments(self):
        text = (
            "# Title\n\nA claim about the thing that follows below.\n\n"
            "- **Decision:** run, adjust, or stop\n"
            "- **Why it pays:** volume, always volume\n"
        )
        [section] = segments(text, {"Title": ["k_2024"]})
        assert len(section.sentences) == 3
        assert section.sentences[0].text.startswith("A claim about")

    def test_a_citation_marker_is_dropped_from_the_text_the_embedder_sees(self):
        text = "# Title\n\nA claim [@smith_2024] worth checking here.\n"
        [section] = segments(text, {"Title": ["smith_2024"]})
        assert "[@smith_2024]" not in section.sentences[0].text
        assert "A claim" in section.sentences[0].text

    def test_the_references_section_contributes_no_segments(self):
        text = (
            "# Title\n\nReal prose in the body.\n\n"
            "## References\n\n[1] A. Author, *A Title*, 2024.\n"
        )
        [section] = segments(text, {"Title": ["k_2024"], "References": ["k_2024"]})
        assert section.title == "Title"

    def test_a_long_sentence_becomes_overlapping_windows(self):
        body = " ".join(f"word{i}" for i in range(50))
        text = f"# Title\n\n{body}.\n"
        [section] = segments(text, {"Title": ["k_2024"]})
        assert len(section.sentences) > 1
        widths = {s.word_end - s.word_start for s in section.sentences}
        assert widths == {overlap_segments.WINDOW_WORDS}

    def test_the_windows_cover_the_whole_sentence_including_its_tail(self):
        body = " ".join(f"word{i}" for i in range(45))
        text = f"# Title\n\n{body}.\n"
        [section] = segments(text, {"Title": ["k_2024"]})
        first, last = section.sentences[0], section.sentences[-1]
        assert last.word_end - first.word_start == 45

    def test_a_short_sentence_is_left_whole(self):
        text = "# Title\n\nShort enough to stay in one piece.\n"
        [section] = segments(text, {"Title": ["k_2024"]})
        assert len(section.sentences) == 1

    def test_a_block_whose_words_are_all_masked_contributes_no_segment(self):
        text = "# Title\n\nReal prose here.\n\n```python\nprint('Not prose at all.')\n```\n"
        [section] = segments(text, {"Title": ["k_2024"]})
        assert all("print" not in s.text for s in section.sentences)

    def test_a_section_with_no_prose_at_all_is_dropped(self):
        text = "# Title\n\n"
        assert segments(text, {"Title": ["k_2024"]}) == []


class TestUnmatchedSections:
    def _unmatched(self, text, mapping):
        words, _ = vc._tokenize_draft(text)
        _found, unmatched = overlap_segments.draft_sections(
            text, [(w.char, w.char_end) for w in words], mapping
        )
        return unmatched

    def test_a_heading_the_dossier_does_not_name_counts_as_unmatched(self):
        text = "# Renamed Since\n\nProse.\n"
        assert self._unmatched(text, {"Old Name": ["smith_2024"]}) == 1

    def test_a_matched_heading_is_not_unmatched(self):
        text = "# Title\n\nBody prose here, several words long.\n"
        assert self._unmatched(text, {"Title": ["smith_2024"]}) == 0

    def test_only_the_unmatched_recorded_titles_are_counted(self):
        text = "# Kept\n\nProse.\n"
        mapping = {"Kept": ["k_2024"], **{f"Old {i}": ["k_2024"] for i in range(9)}}
        assert self._unmatched(text, mapping) == 9

    def test_a_section_with_no_recorded_citekeys_is_not_unmatched(self):
        text = "# Title\n\nProse.\n"
        assert self._unmatched(text, {"Title": []}) == 0

    def test_an_empty_recorded_title_with_no_matching_heading_is_still_not_unmatched(self):
        text = "# Current Heading\n\nProse.\n"
        assert self._unmatched(text, {"Old Empty Name": []}) == 0


class TestMatchedWords:
    def test_it_counts_distinct_words_not_the_sum_of_overlapping_windows(self):
        section = overlap_segments.DraftSection(
            "T",
            ["k_2024"],
            [
                overlap_segments.DraftSentence("a", 0, 20),
                overlap_segments.DraftSentence("b", 10, 30),
            ],
        )
        assert overlap_segments.matched_words(section, (0, 1)) == 30

    def test_no_matched_segments_is_zero(self):
        section = overlap_segments.DraftSection("T", ["k_2024"], [])
        assert overlap_segments.matched_words(section, ()) == 0


class TestSourceSentences:
    @pytest.fixture
    def sidecar(self, ledger_con, tmp_path):
        def write(citekey, records):
            add_citable(ledger_con, citekey)
            path = config.DOCLING_DIR / f"{citekey}.passages.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(records), encoding="utf-8")

        return write

    def test_each_segment_carries_the_page_its_passage_sits_on(self, ledger_con, sidecar):
        sidecar(
            "smith_2024",
            [
                {"text": "First claim here. Second claim here.", "label": "text", "page": 4},
            ],
        )
        found = overlap_segments.source_sentences(ledger_con, "smith_2024")
        assert [s.text for s in found] == ["First claim here.", "Second claim here."]
        assert {s.page for s in found} == {4}

    def test_a_passage_with_no_page_is_skipped(self, ledger_con, sidecar):
        sidecar(
            "smith_2024",
            [
                {"text": "Unpaged claim.", "label": "text", "page": None},
                {"text": "Paged claim.", "label": "text", "page": 2},
            ],
        )
        found = overlap_segments.source_sentences(ledger_con, "smith_2024")
        assert [s.text for s in found] == ["Paged claim."]

    def test_a_source_with_no_sidecar_yields_nothing_rather_than_page_text(
        self, ledger_con, tmp_path
    ):
        from chitragupta import ledger

        parsed = config.PARSED_DIR / "smith_2024.txt"
        parsed.parent.mkdir(parents=True, exist_ok=True)
        parsed.write_text("page one text\fpage two text", encoding="utf-8")
        ledger.upsert_reference(ledger_con, make_reference(citekey="smith_2024"))
        ledger_con.execute(
            "UPDATE items SET status = 'parsed', parsed_path = ? WHERE citekey = ?",
            (str(parsed), "smith_2024"),
        )
        assert overlap_segments.source_sentences(ledger_con, "smith_2024") == []

    def test_a_long_source_sentence_is_windowed_too(self, ledger_con, sidecar):
        body = " ".join(f"word{i}" for i in range(50))
        sidecar("smith_2024", [{"text": f"{body}.", "label": "text", "page": 1}])
        found = overlap_segments.source_sentences(ledger_con, "smith_2024")
        assert len(found) > 1
        assert all(len(s.text.split()) == overlap_segments.WINDOW_WORDS for s in found)

    def test_a_source_sentence_gets_a_tail_window_when_the_stride_does_not_divide_it(
        self, ledger_con, sidecar
    ):
        body = " ".join(f"word{i}" for i in range(45))
        sidecar("smith_2024", [{"text": f"{body}.", "label": "text", "page": 1}])
        found = overlap_segments.source_sentences(ledger_con, "smith_2024")
        assert found[-1].text.endswith("word44.")

    def test_a_citekey_that_is_not_in_the_ledger_yields_nothing(self, ledger_con):
        assert overlap_segments.source_sentences(ledger_con, "ghost_2024") == []


class TestTheWordIndexIsNotRebuiltPerSentence:
    def test_word_range_reads_the_spans_directly(self):
        spans = [(0, 3), (5, 9), (11, 14), (20, 25)]
        assert overlap_segments._word_range(spans, 0, 20) == (0, 3)
        assert overlap_segments._word_range(spans, 5, 11) == (1, 2)

    def test_an_offset_between_two_words_lands_on_the_later_one(self):
        spans = [(0, 3), (10, 13)]
        assert overlap_segments._word_range(spans, 4, 14) == (1, 2)

    def test_a_range_covering_nothing_is_empty(self):
        spans = [(0, 3), (10, 13)]
        assert overlap_segments._word_range(spans, 20, 30) == (2, 2)


class TestAHeadingOnTheFinalLine:
    def test_a_final_heading_without_a_trailing_newline_does_not_raise(self):
        text = "# Title\n\nSome prose about twins.\n\n## Final heading"
        found, unmatched = overlap_segments.draft_sections(
            text, [(0, 4)], {"Final heading": ["a_2024"]}
        )
        assert found == []
        assert unmatched == 0

    def test_a_final_heading_with_a_trailing_newline_is_unchanged(self):
        text = "# Title\n\nSome prose about twins.\n\n## Final heading\n"
        found, _unmatched = overlap_segments.draft_sections(
            text, [(0, 4)], {"Final heading": ["a_2024"]}
        )
        assert found == []

    def test_a_final_heading_that_does_have_a_body_is_still_scanned(self):
        text = "# Title\n\n## Final heading\n\nReal prose under the final heading."
        spans = [(m.start(), m.end()) for m in re.finditer(r"[A-Za-z]+", text)]
        found, _unmatched = overlap_segments.draft_sections(
            text, spans, {"Final heading": ["a_2024"]}
        )
        assert [section.title for section in found] == ["Final heading"]

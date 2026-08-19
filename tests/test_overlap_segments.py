"""chitragupta/overlap_segments.py: what a segment is on each side of tier 3's
alignment, and where in the original it sits.

Stdlib-only like the module, so the draft side is exercised through
`verbatim_check._tokenize_draft` (which is where the word stream a
segment's offsets index actually comes from -- restating it here would
be testing a copy) and the source side through a written passage
sidecar."""

import json

import pytest

from chitragupta import config, overlap_segments
from chitragupta.review import verbatim_check as vc
from tests.conftest import make_reference


def segments(text, mapping):
    words, _ = vc._tokenize_draft(text)
    return overlap_segments.draft_sections(
        text, [(w.char, w.char_end) for w in words], mapping
    )


class TestDraftSections:
    def test_a_section_carries_the_citekeys_its_dossier_records(self):
        text = "# Title\n\nBody prose here, several words long.\n"
        [section] = segments(text, {"Title": ["smith_2024"]})
        assert section.title == "Title"
        assert section.citekeys == ["smith_2024"]

    def test_a_section_with_no_recorded_citekeys_is_dropped(self):
        # Never scanned against the whole corpus instead:
        # docs/PLAGIARISM-DESIGN.md argues at length that a whole-corpus search
        # is the wrong shape here, and a silent fallback would be it.
        text = "# Kept\n\nProse.\n\n# Dropped\n\nMore prose.\n"
        titles = [s.title for s in segments(text, {"Kept": ["smith_2024"]})]
        assert titles == ["Kept"]

    def test_a_heading_the_dossier_does_not_name_is_dropped(self):
        text = "# Renamed Since\n\nProse.\n"
        assert segments(text, {"Old Name": ["smith_2024"]}) == []

    def test_word_offsets_index_the_scans_own_word_stream(self):
        # The contract that makes a tier-3 finding land in the same
        # coordinate system tiers 1 and 2 use (#131).
        text = "# Title\n\nAlpha beta gamma delta epsilon.\n"
        [section] = segments(text, {"Title": ["k_2024"]})
        words, _ = vc._tokenize_draft(text)
        word_strs = [w.text for w in words]
        [segment] = section.sentences
        assert word_strs[segment.word_start:segment.word_end] == [
            "alpha", "beta", "gamma", "delta", "epsilon"
        ]

    def test_prose_and_the_bullets_under_it_are_separate_segments(self):
        # Measured on the real book: without this, a paragraph welded to
        # the list beneath it embedded as neither, and the one
        # hand-verified organic paraphrase in chapter 1 was invisible.
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
        # `_tokenize_draft` blanks it, so its "sentences" cover no words
        # of the stream -- which is how this module keeps masked regions
        # out without knowing how they were masked.
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
        # The stride rarely divides the range exactly; without a final
        # window ending at the end, the tail is covered only by whatever
        # the last full window happened to reach.
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
        # A fenced code block is blanked by `_tokenize_draft`, so the
        # "sentence" inside it covers no word of the stream. Reaching
        # here rather than being filtered earlier is the point: this
        # module never has to know how the masking was done.
        text = (
            "# Title\n\nReal prose here.\n\n"
            "```python\nprint('Not prose at all.')\n```\n"
        )
        [section] = segments(text, {"Title": ["k_2024"]})
        assert all("print" not in s.text for s in section.sentences)

    def test_a_section_with_no_prose_at_all_is_dropped(self):
        text = "# Title\n\n"
        assert segments(text, {"Title": ["k_2024"]}) == []


class TestMatchedWords:
    def test_it_counts_distinct_words_not_the_sum_of_overlapping_windows(self):
        # Reported 60 matched words inside a 39-word span on the first
        # real run, because consecutive windows share half their words.
        section = overlap_segments.DraftSection("T", ["k_2024"], [
            overlap_segments.DraftSentence("a", 0, 20),
            overlap_segments.DraftSentence("b", 10, 30),
        ])
        assert overlap_segments.matched_words(section, (0, 1)) == 30

    def test_no_matched_segments_is_zero(self):
        section = overlap_segments.DraftSection("T", ["k_2024"], [])
        assert overlap_segments.matched_words(section, ()) == 0


class TestSourceSentences:
    @pytest.fixture
    def sidecar(self, ledger_con, tmp_path):
        def write(citekey, records):
            from chitragupta import ledger

            ledger.upsert_reference(ledger_con, make_reference(citekey=citekey))
            path = config.DOCLING_DIR / f"{citekey}.passages.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(records), encoding="utf-8")
        return write

    def test_each_segment_carries_the_page_its_passage_sits_on(self, ledger_con, sidecar):
        sidecar("smith_2024", [
            {"text": "First claim here. Second claim here.", "label": "text", "page": 4},
        ])
        found = overlap_segments.source_sentences(ledger_con, "smith_2024")
        assert [s.text for s in found] == ["First claim here.", "Second claim here."]
        assert {s.page for s in found} == {4}

    def test_a_passage_with_no_page_is_skipped(self, ledger_con, sidecar):
        # A finding reports a page a reviewer turns to; a passage that
        # cannot say which page it is on cannot support one.
        sidecar("smith_2024", [
            {"text": "Unpaged claim.", "label": "text", "page": None},
            {"text": "Paged claim.", "label": "text", "page": 2},
        ])
        found = overlap_segments.source_sentences(ledger_con, "smith_2024")
        assert [s.text for s in found] == ["Paged claim."]

    def test_a_source_with_no_sidecar_yields_nothing_rather_than_page_text(
        self, ledger_con, tmp_path
    ):
        # Rungs 3 and 4 of chitragupta/passages.py's ladder hand back whole pages
        # of `pdftotext -layout` output with `text=None`: on a two-column
        # paper every line of that splices two columns together, so a
        # sentence cut from one is a collage of two arguments.
        from chitragupta import ledger

        parsed = config.PARSED_DIR / "smith_2024.txt"
        parsed.parent.mkdir(parents=True, exist_ok=True)
        parsed.write_text("page one text\fpage two text", encoding="utf-8")
        ledger.upsert_reference(ledger_con, make_reference(citekey="smith_2024"))
        ledger_con.execute(
            "UPDATE items SET parsed_path = ? WHERE citekey = ?",
            (str(parsed), "smith_2024"),
        )
        assert overlap_segments.source_sentences(ledger_con, "smith_2024") == []

    def test_a_long_source_sentence_is_windowed_too(self, ledger_con, sidecar):
        # Both sides need it: a 40-word source sentence whose second half
        # is the restated claim has the same framing problem in the same
        # direction.
        body = " ".join(f"word{i}" for i in range(50))
        sidecar("smith_2024", [{"text": f"{body}.", "label": "text", "page": 1}])
        found = overlap_segments.source_sentences(ledger_con, "smith_2024")
        assert len(found) > 1
        assert all(len(s.text.split()) == overlap_segments.WINDOW_WORDS for s in found)

    def test_a_source_sentence_gets_a_tail_window_when_the_stride_does_not_divide_it(
        self, ledger_con, sidecar
    ):
        # Without it the tail is covered only by whatever the last full
        # window happened to reach, which is the same gap the draft side
        # closes for the same reason.
        body = " ".join(f"word{i}" for i in range(45))
        sidecar("smith_2024", [{"text": f"{body}.", "label": "text", "page": 1}])
        found = overlap_segments.source_sentences(ledger_con, "smith_2024")
        assert found[-1].text.endswith("word44.")

    def test_a_citekey_that_is_not_in_the_ledger_yields_nothing(self, ledger_con):
        assert overlap_segments.source_sentences(ledger_con, "ghost_2024") == []

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from chitragupta.review import verbatim_check as vc

from chitragupta.review.verbatim_check._scan_notes import _words_note
from chitragupta import (
    config,
    ledger,
    overlap_chroma,
    overlap_embed,
    overlap_index,
    style_exceptions,
)
from chitragupta.review.verbatim_check import _citekeys, _scan
from tests.conftest import add_parsed_item, run_python


@pytest.fixture
def fixture_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BIB_FILE_PATH", tmp_path / "bibliography.bib")
    monkeypatch.setattr(config, "PARSED_DIR", tmp_path / "content" / "parsed")
    monkeypatch.setattr(config, "LEDGER_PATH", tmp_path / "content" / "ledger.sqlite")
    return tmp_path


def ledger_pdf(citekey: str, stored: "str | None") -> None:
    config.LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = ledger.connect()
    try:
        con.execute(
            "INSERT INTO items (citekey, title, status, pdf_path, last_synced)"
            " VALUES (?, 'T', 'discovered', ?, '2026-01-01')",
            (citekey, stored),
        )
        con.commit()
    finally:
        con.close()


class TestPdfPath:
    def test_resolves_the_stored_relative_path_against_the_bib_directory(self, fixture_repo):
        pdf = fixture_repo / "pdfs" / "21" / "Smith - 2024 - Title.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b"%PDF-1.4")
        ledger_pdf("smith_2024", "pdfs/21/Smith - 2024 - Title.pdf")
        assert vc.pdf_path("smith_2024") == pdf

    def test_a_legacy_absolute_value_still_reads(self, fixture_repo):
        pdf = fixture_repo / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        ledger_pdf("smith_2024", str(pdf))
        assert vc.pdf_path("smith_2024") == pdf

    def test_resolves_relative_to_bib_file_directory_not_repo_root(self, tmp_path, monkeypatch):
        bib_dir = tmp_path / "elsewhere"
        bib_dir.mkdir()
        monkeypatch.setattr(config, "BIB_FILE_PATH", bib_dir / "bibliography.bib")
        monkeypatch.setattr(config, "LEDGER_PATH", tmp_path / "content" / "ledger.sqlite")
        pdf = bib_dir / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        ledger_pdf("smith_2024", "paper.pdf")
        assert vc.pdf_path("smith_2024") == pdf

    def test_no_pdf_recorded_returns_none(self, fixture_repo):
        ledger_pdf("smith_2024", None)
        assert vc.pdf_path("smith_2024") is None

    def test_a_recorded_pdf_missing_on_disk_returns_none(self, fixture_repo):
        ledger_pdf("smith_2024", "paper.pdf")
        assert vc.pdf_path("smith_2024") is None

    def test_a_citekey_with_no_row_returns_none(self, fixture_repo):
        ledger_pdf("other_2024", None)
        assert vc.pdf_path("smith_2024") is None

    def test_no_ledger_at_all_returns_none_rather_than_raising(self, fixture_repo):
        assert not config.LEDGER_PATH.exists()
        assert vc.pdf_path("anything_2024") is None


@pytest.mark.usefixtures("programs_on_path")
class TestPages:
    def test_falls_back_to_parsed_text_when_no_pdf(self, fixture_repo):
        config.BIB_FILE_PATH.write_text("@article{smith_2024,\n  title = {T},\n}\n")
        parsed_dir = fixture_repo / "content" / "parsed"
        parsed_dir.mkdir(parents=True)
        (parsed_dir / "smith_2024.txt").write_text("page one text\x00\x01\fpage two text")

        result = vc.pages("smith_2024")
        assert result == ["page one text  page two text"] or len(result) == 2

    def test_no_pdf_and_no_parsed_text_returns_empty(self, fixture_repo):
        config.BIB_FILE_PATH.write_text("@article{smith_2024,\n  title = {T},\n}\n")
        assert vc.pages("smith_2024") == []

    def test_a_traversal_citekey_reads_nothing_outside_parsed_dir(self, fixture_repo):
        config.BIB_FILE_PATH.write_text("@article{smith_2024,\n  title = {T},\n}\n")
        parsed_dir = fixture_repo / "content" / "parsed"
        parsed_dir.mkdir(parents=True)
        (fixture_repo / "content" / "secret.txt").write_text("must stay unread", encoding="utf-8")
        assert vc.pages("../secret") == []

    def test_parsed_fallback_respects_parsed_dir_override(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "BIB_FILE_PATH", tmp_path / "bibliography.bib")
        custom_parsed_dir = tmp_path / "custom-content" / "parsed"
        monkeypatch.setattr(config, "PARSED_DIR", custom_parsed_dir)
        custom_parsed_dir.mkdir(parents=True)
        (custom_parsed_dir / "smith_2024.txt").write_text("page one text")

        config.BIB_FILE_PATH.write_text("@article{smith_2024,\n  title = {T},\n}\n")
        assert vc.pages("smith_2024") == ["page one text"]

    def test_a_config_change_made_after_import_reaches_the_lookup(self, tmp_path, monkeypatch):
        bib = tmp_path / "bibliography.bib"
        parsed = tmp_path / "parsed"
        parsed.mkdir()
        monkeypatch.setattr(config, "BIB_FILE_PATH", bib)
        monkeypatch.setattr(config, "PARSED_DIR", parsed)
        (parsed / "smith_2024.txt").write_text("page one text", encoding="utf-8")
        bib.write_text("@article{smith_2024,\n  title = {T},\n}\n", encoding="utf-8")
        assert vc.pages("smith_2024") == ["page one text"]

    @pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext not installed")
    def test_real_pdf_via_pdftotext(self, fixture_repo):
        pandoc, pdflatex = shutil.which("pandoc"), shutil.which("pdflatex")
        if not (pandoc and pdflatex):
            pytest.skip("pandoc/pdflatex not installed")

        md = fixture_repo / "doc.md"
        md.write_text("# Title\n\nSome distinctive verbatim content here.\n")
        pdf = fixture_repo / "paper.pdf"
        subprocess.run(
            ["pandoc", str(md), "-o", str(pdf), "--pdf-engine=pdflatex"],
            check=True,
            capture_output=True,
        )

        ledger_pdf("smith_2024", "paper.pdf")
        result = vc.pages("smith_2024")
        assert any("distinctive verbatim content" in p for p in result)

    def test_a_pdftotext_failure_falls_through_to_the_parsed_text(self, fixture_repo, monkeypatch):
        pdf = fixture_repo / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 not really a pdf")
        ledger_pdf("smith_2024", "paper.pdf")
        parsed_dir = fixture_repo / "content" / "parsed"
        parsed_dir.mkdir(parents=True, exist_ok=True)
        (parsed_dir / "smith_2024.txt").write_text("the parsed fallback text")

        def refuse(*args, **kwargs):
            raise subprocess.CalledProcessError(1, "pdftotext")

        monkeypatch.setattr(vc._corpus, "_run", refuse)
        assert vc.pages("smith_2024") == ["the parsed fallback text"]

    def test_a_pdftotext_timeout_falls_through_to_the_parsed_text(self, fixture_repo, monkeypatch):
        pdf = fixture_repo / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 not really a pdf")
        ledger_pdf("smith_2024", "paper.pdf")
        parsed_dir = fixture_repo / "content" / "parsed"
        parsed_dir.mkdir(parents=True, exist_ok=True)
        (parsed_dir / "smith_2024.txt").write_text("the parsed fallback text")
        monkeypatch.setattr(vc._corpus.config, "PARSER_DOCUMENT_TIMEOUT", 7.0)
        seen = {}

        def hang(*args, **kwargs):
            seen.update(kwargs)
            raise subprocess.TimeoutExpired("pdftotext", kwargs["timeout"])

        monkeypatch.setattr(vc._corpus, "_run", hang)
        assert vc.pages("smith_2024") == ["the parsed fallback text"]
        assert seen["timeout"] == 7.0

    def test_a_missing_pdftotext_binary_falls_through_too(self, fixture_repo, monkeypatch):
        pdf = fixture_repo / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 not really a pdf")
        ledger_pdf("smith_2024", "paper.pdf")

        def refuse(*args, **kwargs):
            raise OSError("pdftotext not found")

        monkeypatch.setattr(vc._corpus, "_run", refuse)
        assert vc.pages("smith_2024") == []


class TestNorm:
    def test_tokenizes_lowercase_alnum(self):
        assert vc.norm("Hello, World! 123") == ["hello", "world", "123"]


class TestSentencesCiting:
    def test_returns_paragraphs_mentioning_citekey(self, tmp_path):
        draft = tmp_path / "draft.md"
        draft.write_text(
            "Paragraph one mentions [@smith_2024] here.\n\n"
            "Paragraph two does not.\n\n"
            "Paragraph three also cites [@smith_2024] again.\n"
        )
        result = vc.sentences_citing(str(draft), "smith_2024")
        assert len(result) == 2
        assert all("smith_2024" in p for p in result)

    def test_no_matching_paragraphs(self, tmp_path):
        draft = tmp_path / "draft.md"
        draft.write_text("Nothing relevant here.\n")
        assert vc.sentences_citing(str(draft), "smith_2024") == []

    def test_a_suffixed_sibling_does_not_match_the_bare_key(self, tmp_path):
        draft = tmp_path / "draft.md"
        draft.write_text(
            "Paragraph one cites only the suffixed sibling [@smith_2024a].\n\n"
            "Paragraph two cites the bare key [@smith_2024].\n"
        )
        result = vc.sentences_citing(str(draft), "smith_2024")
        assert len(result) == 1
        assert "Paragraph two" in result[0]

    def test_the_suffixed_sibling_itself_still_matches(self, tmp_path):
        draft = tmp_path / "draft.md"
        draft.write_text("Paragraph one cites only the suffixed sibling [@smith_2024a].\n")
        result = vc.sentences_citing(str(draft), "smith_2024a")
        assert len(result) == 1


class TestCmdOverlap:
    def test_no_source_text_when_citekey_not_in_ledger(self, isolated_config, tmp_path, capsys):
        draft = tmp_path / "draft.md"
        draft.write_text("Some claim citing smith_2024.\n")
        vc.cmd_overlap(str(draft), "smith_2024")
        out = capsys.readouterr().out
        assert "no source text for smith_2024" in out

    def test_detects_verbatim_overlap_run(self, ledger_con, tmp_path, capsys):
        shared_phrase = "the quick brown fox jumps over the lazy dog repeatedly"
        add_parsed_item(
            ledger_con, tmp_path, "smith_2024", f"Intro text. {shared_phrase}. More text."
        )

        draft = tmp_path / "draft.md"
        draft.write_text(f"As discussed [@smith_2024], {shared_phrase} in the study.\n")

        vc.cmd_overlap(str(draft), "smith_2024", n=4)
        out = capsys.readouterr().out
        assert "words, pdf p." in out

    def test_overlap_run_extending_to_end_of_sentence(self, ledger_con, tmp_path, capsys):
        shared_phrase = "the quick brown fox jumps over the lazy dog"
        add_parsed_item(ledger_con, tmp_path, "smith_2024", f"Intro text. {shared_phrase}.")

        draft = tmp_path / "draft.md"
        draft.write_text(f"As discussed [@smith_2024], {shared_phrase}\n")

        vc.cmd_overlap(str(draft), "smith_2024", n=4)
        out = capsys.readouterr().out
        assert "words, pdf p." in out

    def test_a_citation_marker_does_not_weld_the_words_around_it(
        self, ledger_con, tmp_path, capsys
    ):
        shared_phrase = "brown fox jumps over"
        add_parsed_item(ledger_con, tmp_path, "smith_2024", f"Intro. {shared_phrase}. More.")

        draft = tmp_path / "draft.md"
        draft.write_text(f"As shown, brown fox[@smith_2024]jumps over the rest.\n")

        vc.cmd_overlap(str(draft), "smith_2024", n=4)
        assert "words, pdf p." in capsys.readouterr().out

    def test_no_overlap_found(self, ledger_con, tmp_path, capsys):
        add_parsed_item(
            ledger_con, tmp_path, "smith_2024", "completely different vocabulary entirely"
        )

        draft = tmp_path / "draft.md"
        draft.write_text("An original sentence mentioning smith_2024 with unrelated words.\n")

        vc.cmd_overlap(str(draft), "smith_2024", n=8)
        out = capsys.readouterr().out
        assert "no verbatim run of >= 8 words found" in out

    def test_matches_output_captured_from_the_pre_index_implementation(
        self, ledger_con, tmp_path, capsys
    ):
        page1 = "Intro words padding here. alpha beta gamma delta epsilon continues on."
        page2 = "Unrelated content on the second page entirely different words."
        page3 = "Again we see alpha beta gamma delta reappear on a later page."
        add_parsed_item(ledger_con, tmp_path, "smith_2024", "\f".join([page1, page2, page3]))

        draft = tmp_path / "draft.md"
        draft.write_text("As shown [@smith_2024], alpha beta gamma delta is the key phrase.\n")

        vc.cmd_overlap(str(draft), "smith_2024", n=4)
        out = capsys.readouterr().out
        assert out == (
            "  [4 words, pdf p.1] alpha beta gamma delta\n"
            "      in: As shown [@smith_2024], alpha beta gamma delta is the key phrase. ...\n"
        )


class TestCmdLocate:
    def test_reports_best_matching_pages(self, fixture_repo, capsys):
        config.BIB_FILE_PATH.write_text("@article{smith_2024,\n  title = {T},\n}\n")
        parsed_dir = fixture_repo / "content" / "parsed"
        parsed_dir.mkdir(parents=True)
        (parsed_dir / "smith_2024.txt").write_text(
            "nothing relevant\fdigital twin simulation platform"
        )

        vc.cmd_locate("smith_2024", "digital twin simulation")
        out = capsys.readouterr().out
        assert "smith_2024: 2 pdf pages" in out
        assert "digital twin simulation" in out


class TestMergeRuns:
    def test_consecutive_positions_always_merge_at_gap_zero(self):
        assert vc._merge_runs([0, 1, 2, 3], gap=0, n=8) == [[0, 1, 2, 3]]

    def test_single_word_edit_merges_at_gap_one_not_gap_zero(self):
        assert vc._merge_runs([0, 9], gap=1, n=8) == [[0, 9]]
        assert vc._merge_runs([0, 9], gap=0, n=8) == [[0], [9]]

    def test_far_apart_clusters_stay_separate_even_with_gap(self):
        assert vc._merge_runs([0, 1, 50, 51], gap=2, n=8) == [[0, 1], [50, 51]]

    def test_duplicate_positions_are_deduped(self):
        assert vc._merge_runs([5, 5, 5], gap=0, n=8) == [[5]]


class TestMergeSpans:
    def test_adjacent_spans_merge(self):
        assert vc._merge_spans([(0, 5, 1), (5, 9, 1)], gap=0) == [(0, 9, [(0, 5, 1), (5, 9, 1)])]

    def test_spans_within_gap_merge(self):
        result = vc._merge_spans([(0, 5, 1), (7, 12, 1)], gap=2)
        assert result == [(0, 12, [(0, 5, 1), (7, 12, 1)])]

    def test_spans_beyond_gap_stay_separate(self):
        result = vc._merge_spans([(0, 5, 1), (20, 25, 1)], gap=2)
        assert result == [(0, 5, [(0, 5, 1)]), (20, 25, [(20, 25, 1)])]

    def test_a_single_span_is_its_own_run(self):
        assert vc._merge_spans([(3, 8, 2)], gap=1) == [(3, 8, [(3, 8, 2)])]


class TestSkipgramTierPrecision:
    def test_a_repeating_source_block_reports_one_finding_not_several(self, ledger_con, tmp_path):
        block = (
            "alpha bexo gamov delka epsilo zenith etaro thelos iotara kappor lambdo muvex"
        ).split()
        add_parsed_item(
            ledger_con,
            tmp_path,
            "cited_2024",
            " ".join(block + ["filler"] * 3 + block),
        )
        swapped = [w if i % 2 == 0 else f"z{i}" for i, w in enumerate(block)]
        draft = tmp_path / "draft.md"
        draft.write_text("[@cited_2024] " + " ".join(swapped) + " end.\n")

        findings, _min_run, _suppressed, _ = vc.scan_findings(draft, min_run=8)

        assert [f["tier"] for f in findings] == ["skip-gram"]
        assert len(findings) == len({f["id"] for f in findings})

    def test_two_unrelated_numeric_tables_do_not_match(self, ledger_con, tmp_path):
        add_parsed_item(ledger_con, tmp_path, "unrelated_2021", "1 4 2 7 3 9 0 6 5 8 2 3 8 1")
        draft = tmp_path / "draft.md"
        draft.write_text("1 0 2 1 3 5 0 2 5 4 2 9 8 7\n")

        findings, _min_run, _suppressed, _ = vc.scan_findings(draft, min_run=8)

        assert findings == []


class TestSkipgramTierSourceSide:
    def _swapped_draft(self, ledger_con, tmp_path, block, source_extra=""):
        add_parsed_item(ledger_con, tmp_path, "cited_2024", " ".join(block) + source_extra)
        swapped = [w if i % 2 == 0 else f"z{i}" for i, w in enumerate(block)]
        draft = tmp_path / "draft.md"
        draft.write_text("[@cited_2024] " + " ".join(swapped) + " end.\n")
        return draft

    def test_the_finding_carries_the_matched_source_passage(self, ledger_con, tmp_path):
        block = (
            "alpha bexo gamov delka epsilo zenith etaro thelos iotara kappor lambdo muvex"
        ).split()
        draft = self._swapped_draft(ledger_con, tmp_path, block)

        findings, _, _, _ = vc.scan_findings(draft, min_run=8)

        [found] = [f for f in findings if f["tier"] == "skip-gram"]
        assert found["source_text"] is not None
        assert "alpha" in found["source_text"]
        assert "bexo" in found["source_text"]
        assert "z1" not in found["source_text"]
        assert found["source_text"] != found["fragment"]

    def test_the_source_passage_keeps_the_documents_own_casing(self, ledger_con, tmp_path):
        block = (
            "Alpha bexo Gamov delka Epsilo zenith Etaro thelos Iotara kappor Lambdo muvex"
        ).split()
        draft = self._swapped_draft(ledger_con, tmp_path, block)

        findings, _, _, _ = vc.scan_findings(draft, min_run=8)

        [found] = [f for f in findings if f["tier"] == "skip-gram"]
        assert "Alpha" in found["source_text"]
        assert found["fragment"].islower()


class TestSkipgramTierQuoting:
    def test_a_window_straddling_the_opening_quote_mark_is_still_quoted(self, ledger_con, tmp_path):
        block = (
            "alpha bexo gamov delka epsilo zenith etaro thelos iotara kappor lambdo muvex"
        ).split()
        add_parsed_item(ledger_con, tmp_path, "cited_2024", " ".join(block))
        swapped = [w if i % 2 == 0 else f"z{i}" for i, w in enumerate(block)]
        draft = tmp_path / "draft.md"
        draft.write_text(
            "[@cited_2024] " + " ".join(swapped[:2]) + ' "' + " ".join(swapped[2:]) + '" end.\n'
        )

        findings, _min_run, _suppressed, _ = vc.scan_findings(draft, min_run=8)

        [found] = [f for f in findings if f["tier"] == "skip-gram"]
        assert found["fragment"].startswith("alpha")
        assert found["quoted"] is True


class TestQuoteCharSpans:
    def test_straight_double_quotes_detected(self):
        spans = vc._quote_char_spans('before "a quoted phrase" after')
        assert spans
        assert spans[0] == (7, 24)

    def test_curly_double_quotes_detected(self):
        spans = vc._quote_char_spans("before “a quoted phrase” after")
        assert spans

    def test_blockquote_line_detected(self):
        spans = vc._quote_char_spans("> a blockquote line\nnot a quote\n")
        assert spans
        assert spans[0][0] == 0

    def test_no_quotes_returns_empty(self):
        assert vc._quote_char_spans("nothing quoted here at all") == []

    def test_an_inch_mark_does_not_open_a_span(self):
        text = 'The pipe is 6" across. Later the author writes "a real quotation" and stops.'
        spans = vc._quote_char_spans(text)
        assert [text[start:end] for start, end in spans] == ['"a real quotation"']

    def test_a_one_character_quotation_is_its_own_span(self):
        text = 'The "A" variant was built to scale, unlike the "B" variant.'
        spans = vc._quote_char_spans(text)
        assert [text[start:end] for start, end in spans] == ['"A"', '"B"']

    def test_an_empty_quotation_is_its_own_span(self):
        text = 'Set it to "" and run it, then read "a quote".'
        spans = vc._quote_char_spans(text)
        assert [text[start:end] for start, end in spans] == ['""', '"a quote"']

    def test_a_span_does_not_cross_a_paragraph_break(self):
        text = 'He said "this was never closed.\n\nA new paragraph that must stay scannable.'
        assert vc._quote_char_spans(text) == []

    def test_a_real_quotation_spanning_two_lines_is_still_one_span(self):
        text = 'She wrote "a quotation that\nwraps across two lines" and stopped.'
        spans = vc._quote_char_spans(text)
        assert [text[start:end] for start, end in spans] == [
            '"a quotation that\nwraps across two lines"'
        ]


class TestMaskForScan:
    def test_blanks_fenced_code(self):
        text = "before\n```\n@dataclass\n```\nafter"
        masked = vc._mask_for_scan(text)
        assert "dataclass" not in masked
        assert "before" in masked
        assert "after" in masked

    def test_blanks_a_works_cited_section(self):
        text = "Prose.\n\n## Works cited\n\nSmith, Blockchain consensus.\n"
        masked = vc._mask_for_scan(text)
        assert "Smith" not in masked
        assert "Prose." in masked

    def test_blanks_inline_code(self):
        masked = vc._mask_for_scan("use `@property` here")
        assert "property" not in masked
        assert "use" in masked
        assert "here" in masked

    def test_blanks_references_section_onward(self):
        text = "Intro text here.\n\n## References\n\n[1] Some Title, Some Venue.\n"
        masked = vc._mask_for_scan(text)
        assert "Intro text here" in masked
        assert "Some Title" not in masked

    def test_no_references_section_leaves_text_untouched(self):
        text = "Just prose, no heading at all.\n"
        assert vc._mask_for_scan(text) == text

    def test_a_section_after_references_stays_scannable(self):
        text = (
            "Intro text here.\n\n"
            "## References\n\n[1] Some Title, Some Venue.\n\n"
            "## Appendix\n\nLifted prose that should still be scanned.\n"
        )
        masked = vc._mask_for_scan(text)
        assert "Some Title" not in masked
        assert "Lifted prose that should still be scanned." in masked


class TestTokenizeDraft:
    def test_flat_word_list_spans_paragraphs(self):
        text = "First paragraph words.\n\nSecond paragraph words.\n"
        words, _ = vc._tokenize_draft(text)
        assert [w.text for w in words] == [
            "first",
            "paragraph",
            "words",
            "second",
            "paragraph",
            "words",
        ]

    def test_paragraph_citekeys_tracks_citations_per_paragraph(self):
        text = "Cites [@smith_2024] here.\n\nCites nothing here.\n"
        _, paragraph_citekeys = vc._tokenize_draft(text)
        assert paragraph_citekeys == [{"smith_2024"}, set()]

    def test_citation_markers_are_not_in_the_word_stream(self):
        words, _ = vc._tokenize_draft("Text citing [@smith_2024] a source.\n")
        assert "smith_2024" not in [w.text for w in words]

    def test_words_inside_quotes_are_flagged_quoted(self):
        words, _ = vc._tokenize_draft('An unquoted word and "a quoted phrase" here.\n')
        by_text = {w.text: w.quoted for w in words}
        assert by_text["unquoted"] is False
        assert by_text["quoted"] is True

    def test_latex_cite_command_is_blanked(self):
        text = "Prior work \\citep[p.~3]{fixture_key_2000} agrees.\n"
        words, keys = vc._tokenize_draft(text, latex=True)
        assert [w.text for w in words] == ["prior", "work", "agrees"]
        assert "fixture_key_2000" in keys[0]

    def test_latex_cite_is_left_alone_without_the_flag(self):
        words, _ = vc._tokenize_draft("See \\citep{fixture_key_2000} now.\n")
        assert "2000" in [w.text for w in words]

    def test_bare_citekey_is_blanked(self):
        text = "Before fixture_key_2000 after words.\n"
        words, _ = vc._tokenize_draft(text, citekeys=frozenset({"fixture_key_2000"}))
        assert [w.text for w in words] == ["before", "after", "words"]
        after = words[1]
        assert text[after.char : after.char_end] == "after"

    def test_bare_citekey_match_is_whole_token_only(self):
        text = "x fixture_key_2000b and fixture_key_2000 end.\n"
        words, _ = vc._tokenize_draft(text, citekeys=frozenset({"fixture_key_2000"}))
        assert [w.text for w in words] == ["x", "fixture", "key", "2000b", "and", "end"]

    def test_no_ledger_means_no_keys(self, monkeypatch):
        def no_ledger():
            raise ledger.NoLedger("none")

        monkeypatch.setattr(ledger, "reading", no_ledger)
        assert _citekeys._known_citekeys() == frozenset()

    def test_known_keys_come_from_the_ledger(self, ledger_con, tmp_path):
        add_parsed_item(ledger_con, tmp_path, "fixture_key_2000", "alpha beta")
        assert "fixture_key_2000" in _citekeys._known_citekeys()


class TestProjectTerms:
    NAME = "National Institute of Standards and Technology"

    @pytest.fixture(autouse=True)
    def _isolated(self, monkeypatch):
        config.VERBATIM_ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(_citekeys, "_known_citekeys", lambda: frozenset())
        monkeypatch.setattr(_scan, "_known_citekeys", lambda: frozenset())

    def _scan(self, ledger_con, tmp_path, monkeypatch, draft_text, terms):
        monkeypatch.setattr(style_exceptions, "terms", lambda: terms)
        add_parsed_item(ledger_con, tmp_path, "cited_2024", f"{self.NAME} sets the rule")
        draft = tmp_path / "draft.md"
        draft.write_text(draft_text)
        return vc.scan_findings(draft)

    def test_declared_term_suppresses_a_run_it_accounts_for(
        self, ledger_con, tmp_path, monkeypatch
    ):
        text = f"[@cited_2024] {self.NAME} sets the rule here.\n"
        findings, _, suppressed, _ = self._scan(
            ledger_con, tmp_path, monkeypatch, text, (self.NAME,)
        )
        assert findings == []
        assert suppressed >= 1

    def test_without_the_term_the_run_is_reported(self, ledger_con, tmp_path, monkeypatch):
        text = f"[@cited_2024] {self.NAME} sets the rule here.\n"
        findings, _, suppressed, _ = self._scan(ledger_con, tmp_path, monkeypatch, text, ())
        assert findings
        assert suppressed == 0

    def test_term_across_a_line_break_is_masked(self, ledger_con, tmp_path, monkeypatch):
        text = "[@cited_2024] National Institute of\nStandards and Technology sets the rule here.\n"
        findings, _, suppressed, _ = self._scan(
            ledger_con, tmp_path, monkeypatch, text, (self.NAME,)
        )
        assert findings == []
        assert suppressed >= 1

    def test_tex_draft_cite_command_is_not_a_run(self, ledger_con, tmp_path, monkeypatch):
        monkeypatch.setattr(style_exceptions, "terms", lambda: ())
        run = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
        add_parsed_item(ledger_con, tmp_path, "cited_2024", f"{run} citep p 3 cited 2024")
        draft = tmp_path / "draft.tex"
        draft.write_text(f"Intro {run} \\citep[p.~3]{{cited_2024}}.\n")
        findings, *_ = vc.scan_findings(draft)
        assert findings
        assert all("citep" not in f["draft_text"].lower() for f in findings)


class TestParagraphs:
    def test_splits_exactly_where_the_plain_split_splits(self):
        text = "one\n\ntwo\n  \nthree"
        assert [para for _, para in vc._paragraphs(text)] == re.split(r"\n\s*\n", text)

    def test_each_paragraph_knows_where_it_starts(self):
        text = "one\n\ntwo\n  \nthree"
        for offset, para in vc._paragraphs(text):
            assert text[offset : offset + len(para)] == para

    def test_a_single_paragraph_starts_at_zero(self):
        assert vc._paragraphs("just one") == [(0, "just one")]


class TestLowerOffsets:
    def test_ascii_takes_the_identity_fast_path(self):
        lowered, offsets = vc._lower_offsets("Digital Twin")
        assert lowered == "digital twin"
        assert offsets is None

    def test_a_length_changing_character_gets_a_real_mapping(self):
        lowered, offsets = vc._lower_offsets("İstanbul")
        assert len(lowered) == 9
        assert offsets is not None
        assert offsets[0] == 0
        assert offsets[1] == 0
        assert offsets[2] == 1  # "s"

    def test_the_mapping_covers_every_character_of_the_result(self):
        lowered, offsets = vc._lower_offsets("AİB")
        assert len(offsets) == len(lowered)


class TestLineAt:
    def test_a_position_on_the_first_line_is_line_one(self):
        text = "first\nsecond\nthird"
        assert vc._line_at(vc._newline_offsets(text), 0) == 1

    def test_a_position_after_a_break_is_the_next_line(self):
        text = "first\nsecond\nthird"
        assert vc._line_at(vc._newline_offsets(text), text.index("second")) == 2
        assert vc._line_at(vc._newline_offsets(text), text.index("third")) == 3

    def test_the_newline_character_itself_belongs_to_the_line_it_ends(self):
        text = "first\nsecond"
        assert vc._line_at(vc._newline_offsets(text), text.index("\n")) == 1

    def test_a_text_with_no_breaks_is_all_line_one(self):
        text = "one single line"
        offsets = vc._newline_offsets(text)
        assert offsets == []
        assert vc._line_at(offsets, len(text) - 1) == 1

    def test_it_agrees_with_counting_newlines_at_every_position(self):
        text = "alpha\n\nbeta gamma\ndelta\n\n\nepsilon"
        offsets = vc._newline_offsets(text)
        for pos in range(len(text)):
            assert vc._line_at(offsets, pos) == text.count("\n", 0, pos) + 1


class TestDraftWordOffsets:
    def _spans(self, text):
        words, _ = vc._tokenize_draft(text)
        return [(w.text, text[w.char : w.char_end]) for w in words]

    def test_offsets_slice_the_original_casing_back_out(self):
        assert self._spans("Digital Twin here.\n") == [
            ("digital", "Digital"),
            ("twin", "Twin"),
            ("here", "here"),
        ]

    def test_offsets_survive_a_paragraph_break(self):
        assert self._spans("First para.\n\nSecond Para.\n") == [
            ("first", "First"),
            ("para", "para"),
            ("second", "Second"),
            ("para", "Para"),
        ]

    def test_offsets_survive_a_blanked_citation_marker(self):
        assert self._spans("Twins [@smith_2024] matter.\n") == [
            ("twins", "Twins"),
            ("matter", "matter"),
        ]

    def test_a_marker_with_no_space_around_it_no_longer_welds_two_words(self):
        words, _ = vc._tokenize_draft("twins[@smith_2024]matter\n")
        assert [w.text for w in words] == ["twins", "matter"]

    def test_offsets_survive_a_blanked_code_fence(self):
        text = "Before.\n\n```\nfenced code\n```\n\nAfter.\n"
        assert self._spans(text) == [("before", "Before"), ("after", "After")]

    def test_offsets_survive_a_length_changing_lowercase(self):
        assert self._spans("The İstanbul result.\n") == [
            ("the", "The"),
            ("i", "İ"),
            ("stanbul", "stanbul"),
            ("result", "result"),
        ]

    def test_the_word_stream_is_unchanged_by_carrying_offsets(self):
        text = "The İstanbul Result.\n"
        words, _ = vc._tokenize_draft(text)
        assert [w.text for w in words] == vc.norm(text)


class TestCmdScan:
    def test_planted_verbatim_run_from_cited_source_is_flagged(self, ledger_con, tmp_path, capsys):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "cited_2024",
            "alpha beta gamma delta epsilon zeta eta theta iota kappa",
        )
        draft = tmp_path / "draft.md"
        draft.write_text(
            "As shown [@cited_2024], alpha beta gamma delta epsilon zeta eta theta appears here.\n"
        )

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "cited_2024" in out
        assert "UNCITED SOURCE" not in out

    def test_one_word_edit_variant_of_the_cited_run_still_merges_at_default_gap(
        self, ledger_con, tmp_path, capsys
    ):
        source_text = (
            "one two three four five six seven eight nine ten eleven twelve "
            "thirteen fourteen fifteen sixteen seventeen eighteen"
        )
        add_parsed_item(ledger_con, tmp_path, "cited_2024", source_text)
        edited = source_text.replace("nine", "ninexx")
        draft = tmp_path / "draft.md"
        draft.write_text(f"As shown [@cited_2024], {edited} end.\n")

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "18 words" in out
        assert "17 matched" in out

    def test_planted_run_from_uncited_source_is_flagged(self, ledger_con, tmp_path, capsys):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "uncited_2024",
            "lorem ipsum dolor sit amet consectetur adipiscing elit sed do",
        )
        draft = tmp_path / "draft.md"
        draft.write_text(
            "As shown [@other_2024], lorem ipsum dolor sit amet consectetur "
            "adipiscing elit sed do appears here.\n"
        )
        add_parsed_item(ledger_con, tmp_path, "other_2024", "completely unrelated filler text")

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "uncited_2024" in out
        assert "UNCITED SOURCE" in out

    def test_planted_run_in_connective_prose_citing_nothing_is_flagged(
        self, ledger_con, tmp_path, capsys
    ):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "connective_2024",
            "the quick brown fox jumps over the lazy dog while running",
        )
        draft = tmp_path / "draft.md"
        draft.write_text(
            "Some cited claim [@other_2024].\n\n"
            "The quick brown fox jumps over the lazy dog while running fast.\n\n"
            "Another cited claim [@other_2024].\n"
        )
        add_parsed_item(ledger_con, tmp_path, "other_2024", "completely unrelated filler text")

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "connective_2024" in out
        assert "UNCITED SOURCE" in out

    def test_clean_paraphrase_does_not_flag(self, ledger_con, tmp_path, capsys):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "cited_2024",
            "structural health monitoring relies on continuous sensor data acquisition "
            "combined with periodic model recalibration to remain trustworthy",
        )
        draft = tmp_path / "draft.md"
        draft.write_text(
            "Keeping a monitoring system trustworthy over time [@cited_2024] means "
            "revisiting its parameters as fresh readings arrive, not fitting it once "
            "and walking away.\n"
        )

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "no verbatim run" in out

    def test_quoted_run_is_flagged_quoted(self, ledger_con, tmp_path, capsys):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "cited_2024",
            "alpha beta gamma delta epsilon zeta eta theta iota kappa",
        )
        draft = tmp_path / "draft.md"
        draft.write_text(
            'As [@cited_2024] puts it, "alpha beta gamma delta epsilon zeta eta theta" exactly.\n'
        )

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "quoted" in out

    def test_a_run_straddling_the_opening_quote_mark_is_still_quoted(
        self, ledger_con, tmp_path, capsys
    ):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "cited_2024",
            "alpha beta gamma delta epsilon zeta eta theta iota kappa",
        )
        draft = tmp_path / "draft.md"
        draft.write_text(
            'As [@cited_2024] puts it, alpha beta gamma "delta epsilon zeta eta theta" exactly.\n'
        )

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "quoted" in out

    def test_a_run_touching_no_quotation_at_all_is_not_quoted(self, ledger_con, tmp_path, capsys):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "cited_2024",
            "alpha beta gamma delta epsilon zeta eta theta iota kappa",
        )
        draft = tmp_path / "draft.md"
        draft.write_text(
            "As [@cited_2024] puts it, alpha beta gamma delta epsilon zeta eta theta exactly.\n"
        )

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "quoted" not in out

    def test_cites_source_checks_every_paragraph_a_run_spans(self, ledger_con, tmp_path, capsys):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "cited_2024",
            "alpha beta gamma delta epsilon zeta eta theta",
        )
        draft = tmp_path / "draft.md"
        draft.write_text(
            "This paragraph cites nothing at all but ends with alpha beta gamma delta.\n\n"
            "epsilon zeta eta theta continues here [@cited_2024] in the next paragraph.\n"
        )

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "cited_2024" in out
        assert "UNCITED SOURCE" not in out

    def test_tier_is_exact(self, ledger_con, tmp_path, capsys):
        add_parsed_item(
            ledger_con, tmp_path, "cited_2024", "alpha beta gamma delta epsilon zeta eta theta"
        )
        draft = tmp_path / "draft.md"
        draft.write_text("[@cited_2024] alpha beta gamma delta epsilon zeta eta theta end.\n")

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "tier=exact" in out

    def test_no_findings_prints_message(self, isolated_config, tmp_path, capsys):
        draft = tmp_path / "draft.md"
        draft.write_text("Nothing to see here at all.\n")

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "no verbatim run of >= 8 words found anywhere in the draft" in out

    def test_min_run_below_index_n_is_rejected(self, isolated_config, tmp_path):
        draft = tmp_path / "draft.md"
        draft.write_text("Anything.\n")

        with pytest.raises(ValueError, match="--min-run must be >="):
            vc.cmd_scan(str(draft), min_run=4)

    def test_run_shorter_than_min_run_is_filtered_out(self, ledger_con, tmp_path, capsys):
        add_parsed_item(
            ledger_con, tmp_path, "cited_2024", "alpha beta gamma delta epsilon zeta eta theta"
        )
        draft = tmp_path / "draft.md"
        draft.write_text("[@cited_2024] alpha beta gamma delta epsilon zeta eta theta end.\n")

        vc.cmd_scan(str(draft), min_run=20)
        out = capsys.readouterr().out
        assert "no verbatim run of >= 20 words found" in out

    def test_limit_truncates_findings(self, ledger_con, tmp_path, capsys):
        add_parsed_item(
            ledger_con, tmp_path, "a_2024", "alpha beta gamma delta epsilon zeta eta theta"
        )
        add_parsed_item(ledger_con, tmp_path, "b_2024", "one two three four five six seven eight")
        draft = tmp_path / "draft.md"
        draft.write_text(
            "[@a_2024] alpha beta gamma delta epsilon zeta eta theta.\n\n"
            "[@b_2024] one two three four five six seven eight.\n"
        )

        vc.cmd_scan(str(draft), limit=1)
        out = capsys.readouterr().out
        assert out.count("tier=exact") == 1

    def test_run_spanning_a_page_break_merges_into_one_finding(self, ledger_con, tmp_path, capsys):
        words = [f"w{i}" for i in range(30)]
        page1, page2 = " ".join(words[:15]), " ".join(words[15:])
        add_parsed_item(ledger_con, tmp_path, "split_2024", page1 + "\f" + page2)
        draft = tmp_path / "draft.md"
        draft.write_text(f"[@split_2024] {' '.join(words)} end.\n")

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert out.count("tier=exact") == 1
        assert "30 words" in out
        assert "pdf p.1-2" in out

    def test_page_boundary_short_remainder_is_recovered_by_the_merge(
        self, ledger_con, tmp_path, capsys
    ):
        words = [f"w{i}" for i in range(30)]
        page1, page2 = " ".join(words[:25]), " ".join(words[25:])
        add_parsed_item(ledger_con, tmp_path, "split_2024", page1 + "\f" + page2)
        draft = tmp_path / "draft.md"
        draft.write_text(f"[@split_2024] {' '.join(words)} end.\n")

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert out.count("tier=exact") == 1
        assert "30 words" in out
        assert "pdf p.1" in out
        assert "w25" in out

    def test_unrelated_matches_either_side_of_a_page_break_stay_separate(
        self, ledger_con, tmp_path, capsys
    ):
        page1 = "alpha beta gamma delta epsilon zeta eta theta"
        page2 = "iota kappa lambda mu nu xi omicron pi"
        add_parsed_item(ledger_con, tmp_path, "mixed_2024", page1 + "\f" + page2)
        draft = tmp_path / "draft.md"
        draft.write_text(
            "[@mixed_2024] alpha beta gamma delta epsilon zeta eta theta filler "
            "iota kappa lambda mu nu xi omicron pi end.\n"
        )

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert out.count("tier=exact") == 2
        assert "pdf p.1" in out
        assert "pdf p.2" in out
        assert "pdf p.1-2" not in out


class TestMaskAllowlisted:
    def test_masks_a_contiguous_occurrence(self):
        words = ["the", "internet", "of", "things", "is", "growing"]
        mask = vc._mask_allowlisted(words, [("internet", "of", "things")])
        assert mask == [False, True, True, True, False, False]

    def test_no_match_returns_all_false(self):
        words = ["alpha", "beta", "gamma"]
        assert vc._mask_allowlisted(words, [("delta", "epsilon")]) == [False, False, False]

    def test_a_phrase_longer_than_the_span_is_skipped_not_erroring(self):
        words = ["alpha", "beta"]
        assert vc._mask_allowlisted(words, [("alpha", "beta", "gamma")]) == [False, False]

    def test_an_empty_phrase_is_skipped(self):
        assert vc._mask_allowlisted(["alpha"], [()]) == [False]

    def test_overlapping_phrases_or_together_without_double_counting(self):
        words = ["alpha", "beta", "gamma"]
        mask = vc._mask_allowlisted(words, [("alpha", "beta", "gamma"), ("beta",)])
        assert mask == [True, True, True]


class TestMaskAllowlistedStemmed:
    def test_masks_a_stemmed_contiguous_occurrence(self):
        words = ["the", "internets", "of", "things", "is", "growing"]
        mask = vc._mask_allowlisted_stemmed(words, [("internet", "of", "things")])
        assert mask == [False, True, True, True, False, False]

    def test_a_phrase_that_stems_to_nothing_is_skipped(self):
        words = ["alpha", "beta"]
        assert vc._mask_allowlisted_stemmed(words, [("the", "of")]) == [False, False]

    def test_a_phrase_longer_than_the_span_is_skipped_not_erroring(self):
        words = ["alpha", "beta"]
        assert vc._mask_allowlisted_stemmed(words, [("alpha", "beta", "gamma")]) == [False, False]

    def test_no_match_returns_all_false(self):
        words = ["alpha", "beta", "gamma"]
        assert vc._mask_allowlisted_stemmed(words, [("delta", "epsilon")]) == [False, False, False]


class TestLoadAllowlistPhrases:
    def test_missing_file_returns_empty_list(self, isolated_config):
        assert vc._load_allowlist_phrases() == []

    def test_flattens_all_four_categories(self, isolated_config):
        config.VERBATIM_ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.VERBATIM_ALLOWLIST_PATH.write_text(
            'acronyms = ["IoT"]\n'
            'phrases = ["software defined networking"]\n'
            'definitions = ["A digital twin is a virtual copy."]\n'
            'paragraphs = ["Some longer boilerplate paragraph text here."]\n'
        )
        phrases = vc._load_allowlist_phrases()
        assert ("iot",) in phrases
        assert ("software", "defined", "networking") in phrases
        assert ("a", "digital", "twin", "is", "a", "virtual", "copy") in phrases
        assert ("some", "longer", "boilerplate", "paragraph", "text", "here") in phrases

    def test_a_category_that_normalizes_to_nothing_is_dropped(self, isolated_config):
        config.VERBATIM_ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.VERBATIM_ALLOWLIST_PATH.write_text('phrases = ["!!!", "alpha"]\n')
        assert vc._load_allowlist_phrases() == [("alpha",)]

    def test_missing_categories_default_to_empty(self, isolated_config):
        config.VERBATIM_ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.VERBATIM_ALLOWLIST_PATH.write_text('phrases = ["alpha"]\n')
        assert vc._load_allowlist_phrases() == [("alpha",)]

    def test_malformed_toml_raises(self, isolated_config):
        config.VERBATIM_ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.VERBATIM_ALLOWLIST_PATH.write_text("not valid toml [[[")
        with pytest.raises(ValueError, match="malformed TOML"):
            vc._load_allowlist_phrases()

    def test_an_unreadable_path_raises_valueerror_not_oserror(self, isolated_config):
        config.VERBATIM_ALLOWLIST_PATH.mkdir(parents=True, exist_ok=True)
        with pytest.raises(ValueError, match="cannot read allowlist"):
            vc._load_allowlist_phrases()

    def test_a_non_string_entry_raises(self, isolated_config):
        config.VERBATIM_ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.VERBATIM_ALLOWLIST_PATH.write_text("phrases = [1, 2]\n")
        with pytest.raises(ValueError, match="'phrases' must be a list of strings"):
            vc._load_allowlist_phrases()

    def test_an_unknown_key_raises_rather_than_loading_as_empty(self, isolated_config):
        config.VERBATIM_ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.VERBATIM_ALLOWLIST_PATH.write_text('pharses = ["alpha"]\n')
        with pytest.raises(ValueError, match=r"unknown key\(s\) \['pharses'\]"):
            vc._load_allowlist_phrases()


class TestAllowlistSuppression:
    def _write_allowlist(self, *phrases):
        config.VERBATIM_ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        joined = ", ".join(f'"{p}"' for p in phrases)
        config.VERBATIM_ALLOWLIST_PATH.write_text(f"phrases = [{joined}]\n")

    def test_a_finding_entirely_covered_by_the_allowlist_is_suppressed(
        self, ledger_con, tmp_path, capsys
    ):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "cited_2024",
            "alpha beta gamma delta epsilon zeta eta theta",
        )
        draft = tmp_path / "draft.md"
        draft.write_text("[@cited_2024] alpha beta gamma delta epsilon zeta eta theta end.\n")
        self._write_allowlist("alpha beta gamma delta epsilon zeta eta theta")

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "no verbatim run" in out
        assert "1 finding(s) suppressed by the allowlist" in out

    def test_a_short_allowlisted_phrase_inside_a_much_longer_run_does_not_suppress_it(
        self, ledger_con, tmp_path, capsys
    ):
        words = [f"w{i}" for i in range(20)]
        words[9:12] = ["alpha", "beta", "gamma"]
        source_text = " ".join(words)
        add_parsed_item(ledger_con, tmp_path, "cited_2024", source_text)
        draft = tmp_path / "draft.md"
        draft.write_text(f"[@cited_2024] {source_text} end.\n")
        self._write_allowlist("alpha beta gamma")

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "20 words" in out
        assert "suppressed" not in out

    def test_a_skipgram_finding_entirely_covered_by_the_allowlist_is_suppressed(
        self, ledger_con, tmp_path, capsys
    ):
        words = "alpha bexo gamov delka epsilo zenith etaro thelos iotara".split()
        text = " ".join(words)
        add_parsed_item(ledger_con, tmp_path, "cited_2024", text)
        draft = tmp_path / "draft.md"
        draft.write_text(f"[@cited_2024] {text} end.\n")
        self._write_allowlist(text)

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "no verbatim run" in out
        assert "suppressed by the allowlist" in out

    def test_a_malformed_allowlist_is_a_usage_error_not_a_silent_empty_list(
        self, isolated_config, tmp_path
    ):
        draft = _content_draft(tmp_path, "Anything.\n")
        config.VERBATIM_ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.VERBATIM_ALLOWLIST_PATH.write_text("not valid toml [[[")

        assert vc.main(["scan", str(draft)]) == 2


class TestBucket:
    def _finding(self, matched_words, quoted, cites_source):
        return {
            "span_words": matched_words + 100,
            "matched_words": matched_words,
            "quoted": quoted,
            "cites_source": cites_source,
        }

    def test_a_run_at_or_above_the_threshold_is_long(self):
        assert (
            vc._bucket(self._finding(vc.LONG_RUN_WORDS, quoted=False, cites_source=True)) == "long"
        )

    def test_a_run_below_the_threshold_is_short(self):
        assert (
            vc._bucket(self._finding(vc.LONG_RUN_WORDS - 1, quoted=False, cites_source=True))
            == "short"
        )

    def test_quoted_and_cited_is_the_quoted_bucket_regardless_of_length(self):
        assert vc._bucket(self._finding(50, quoted=True, cites_source=True)) == "quoted"

    def test_quoted_but_uncited_buckets_by_length_instead(self):
        assert vc._bucket(self._finding(50, quoted=True, cites_source=False)) == "long"
        assert vc._bucket(self._finding(5, quoted=True, cites_source=False)) == "short"


class TestParagraphLocator:
    def test_a_run_in_the_first_paragraph_is_paragraph_one(self, ledger_con, tmp_path):
        shared = "the quick brown fox jumps over the lazy dog repeatedly today"
        draft = _content_draft(tmp_path, f"{shared}\n")
        add_parsed_item(ledger_con, tmp_path, "src_2024", f"Intro. {shared}. More.")

        findings, _, _, _ = vc.scan_findings(str(draft))

        assert findings[0]["paragraph"] == 1
        assert findings[0]["end_paragraph"] == 1

    def test_paragraphs_are_counted_not_lines(self, ledger_con, tmp_path):
        shared = "the quick brown fox jumps over the lazy dog repeatedly today"
        body = f"First para.\n\nSecond para,\nwrapped over two lines.\n\n{shared}\n"
        draft = _content_draft(tmp_path, body)
        add_parsed_item(ledger_con, tmp_path, "src_2024", f"Intro. {shared}. More.")

        findings, _, _, _ = vc.scan_findings(str(draft))

        found = findings[0]
        assert found["paragraph"] == 3
        assert found["line"] == 6


class TestEveryRenderedSurfaceCarriesTheLocators:
    def _finding(self, **overrides):
        base = _rendered_finding("exact")
        base.update({"line": 35, "paragraph": 9, "end_paragraph": 9, "page": 7, "end_page": 7})
        base.update(overrides)
        return base

    def test_the_markdown_report(self):
        rendered = vc.render_scan_markdown(
            Path("content/drafts/t/survey.md"), [self._finding()], 8, None, "cmd"
        )
        assert "p.7" in rendered
        assert "At draft line 35, paragraph 9." in rendered

    def test_the_terminal_form(self):
        printed = vc.format_scan([self._finding()], 8)
        assert "pdf p.7, draft line 35, paragraph 9" in printed

    def test_a_multi_paragraph_run_reports_the_range(self):
        printed = vc.format_scan([self._finding(end_paragraph=10)], 8)
        assert "paragraphs 9-10" in printed

    def test_a_finding_from_a_report_predating_the_fields_degrades_key_by_key(self):
        finding = self._finding()
        del finding["paragraph"]
        del finding["end_paragraph"]
        printed = vc.format_scan([finding], 8)
        assert "draft line 35" in printed
        assert "paragraph" not in printed

    def test_no_locator_at_all_prints_no_empty_brackets(self):
        finding = self._finding()
        for key in ("line", "paragraph", "end_paragraph"):
            del finding[key]
        printed = vc.format_scan([finding], 8)
        assert "pdf p.7]" in printed
        assert "draft ," not in printed


class TestBucketTitle:
    def test_long(self):
        assert vc._bucket_title("long") == f"Long runs (>= {vc.LONG_RUN_WORDS} words of evidence)"

    def test_long_does_not_claim_the_words_were_matched(self):
        assert "matched" not in vc._bucket_title("long")

    def test_short(self):
        assert vc._bucket_title("short") == "Short runs"

    def test_quoted(self):
        assert vc._bucket_title("quoted") == "Quoted runs"


def _rendered_finding(tier, **overrides) -> dict:
    finding = {
        "citekey": "source_2024",
        "page": 7,
        "end_page": 7,
        "tier": tier,
        "span_words": 31,
        "matched_words": 31,
        "fragment": "the draft s own words flattened",
        "context": "before the draft s own words flattened after",
        "cites_source": True,
        "quoted": False,
        "score": 0.404 if tier == "embedding" else None,
        "source_text": "The source's own, differently worded sentence."
        if tier == "embedding"
        else None,
    }
    finding.update(overrides)
    return finding


class TestWordsNote:
    def test_a_deterministic_tier_reports_matched_words_unchanged(self):
        assert _words_note(_rendered_finding("exact")) == "31 words"

    def test_a_deterministic_tier_still_qualifies_a_partial_match(self):
        finding = _rendered_finding("skip-gram", span_words=40, matched_words=23)
        assert _words_note(finding) == "40 words, 23 matched"

    def test_an_embedding_finding_says_aligned_not_matched(self):
        assert _words_note(_rendered_finding("embedding")) == "31 words aligned"
        assert "matched" not in _words_note(_rendered_finding("embedding"))

    def test_an_embedding_finding_names_the_sentence_units_when_they_differ(self):
        finding = _rendered_finding("embedding", span_words=40, matched_words=23)
        assert _words_note(finding) == "40 words aligned, 23 in matched sentence(s)"


class TestBothSidesOfAnEmbeddingFinding:
    def test_a_deterministic_tier_prints_one_unlabelled_block(self):
        rendered = vc.render_scan_markdown(
            Path("content/drafts/t/survey.md"), [_rendered_finding("exact")], 8, None, "cmd"
        )
        assert "> the draft s own words flattened" in rendered
        assert "\nDraft:\n" not in rendered
        assert "\nSource:\n" not in rendered

    def test_an_embedding_finding_prints_both_sides_labelled(self):
        rendered = vc.render_scan_markdown(
            Path("content/drafts/t/survey.md"), [_rendered_finding("embedding")], 8, None, "cmd"
        )
        assert "\nDraft:\n" in rendered
        assert "\nSource:\n" in rendered
        assert rendered.index("\nDraft:\n") < rendered.index("\nSource:\n")
        assert "the draft s own words flattened" in rendered.replace("**", "")
        assert "The source's own, differently worded sentence." in rendered.replace("**", "")

    def test_a_source_passage_containing_newlines_stays_one_blockquote(self):
        finding = _rendered_finding(
            "embedding", source_text="The source's own\nwording, wrapped\n\nacross lines."
        )

        rendered = vc.render_scan_markdown(
            Path("content/drafts/t/survey.md"), [finding], 8, None, "cmd"
        )

        lines = rendered.splitlines()
        quote = lines[lines.index("Source:") + 2]
        assert quote.startswith("> ")
        assert {"wording,", "wrapped", "across", "lines."} <= set(
            quote.replace("**", "").replace("~~", "").split()
        )

    def test_the_terminal_form_prints_both_sides_too(self):
        printed = vc.format_scan([_rendered_finding("embedding")], 8)
        assert "draft:  the draft s own words flattened" in printed
        assert "source: The source's own, differently worded sentence." in printed

    def test_the_terminal_form_leaves_a_deterministic_tier_unlabelled(self):
        printed = vc.format_scan([_rendered_finding("exact")], 8)
        assert "      the draft s own words flattened" in printed
        assert "draft:" not in printed


class TestScanWrite:
    def _planted(self, ledger_con, tmp_path, name="dt/survey.md"):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "cited_2024",
            "alpha beta gamma delta epsilon zeta eta theta iota kappa",
        )
        draft = config.DRAFTS_DIR / name
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(
            "As shown [@cited_2024], alpha beta gamma delta epsilon zeta eta theta appears here.\n"
        )
        return draft

    def test_off_by_default(self, ledger_con, isolated_config, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)
        vc.cmd_scan(str(draft))
        assert not config.REVIEW_DIR.exists()

    def test_write_lands_in_the_mirrored_review_dir(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        report = config.REVIEW_DIR / "dt" / "survey.verbatim.md"
        assert report.is_file()
        text = report.read_text()
        assert "Review aid, not a gate" in text
        assert "cited_2024" in text
        assert "not a clean bill of health" in text

    def test_a_clean_draft_still_writes_a_report(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        add_parsed_item(ledger_con, tmp_path, "cited_2024", "wholly unrelated source text here")
        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("Entirely original prose that shares nothing.\n")

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        text = (config.REVIEW_DIR / "survey.verbatim.md").read_text()
        assert "No verbatim run" in text

    def test_limit_is_recorded_in_the_command_line(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), limit=1, write=True, formats=["md"])

        text = (config.REVIEW_DIR / "dt" / "survey.verbatim.md").read_text()
        assert "--limit 1" in text

    def test_the_recorded_command_regenerates_the_file(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        text = (config.REVIEW_DIR / "dt" / "survey.verbatim.md").read_text()
        assert "--write" in text

    def test_two_runs_over_unchanged_input_are_byte_identical(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)
        report = config.REVIEW_DIR / "dt" / "survey.verbatim.md"

        vc.cmd_scan(str(draft), write=True, formats=["md"])
        first = report.read_bytes()
        vc.cmd_scan(str(draft), write=True, formats=["md"])

        assert report.read_bytes() == first

    def test_a_short_run_lands_under_the_short_heading(self, ledger_con, tmp_path):
        draft = self._planted(ledger_con, tmp_path)  # an 8-word run, below LONG_RUN_WORDS

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        text = (config.REVIEW_DIR / "dt" / "survey.verbatim.md").read_text()
        assert "### Short runs" in text
        assert "### Long verbatim runs" not in text
        assert "### Quoted runs" not in text

    def test_a_long_run_lands_under_the_long_heading(self, ledger_con, tmp_path):
        source_text = " ".join(f"tok{i}" for i in range(20))
        add_parsed_item(ledger_con, tmp_path, "cited_2024", source_text)
        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(f"[@cited_2024] {source_text} end.\n")

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        text = (config.REVIEW_DIR / "survey.verbatim.md").read_text()
        assert f"### Long runs (>= {vc.LONG_RUN_WORDS} words of evidence)" in text
        assert "### Short verbatim runs" not in text

    def test_a_quoted_and_cited_run_lands_under_the_quoted_heading(self, ledger_con, tmp_path):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "cited_2024",
            "alpha beta gamma delta epsilon zeta eta theta",
        )
        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(
            'As [@cited_2024] puts it, "alpha beta gamma delta epsilon zeta eta theta" exactly.\n'
        )

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        text = (config.REVIEW_DIR / "survey.verbatim.md").read_text()
        assert "### Quoted runs" in text
        assert "### Short verbatim runs" not in text

    def test_report_names_the_allowlist_file_when_none_is_configured(self, ledger_con, tmp_path):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        text = (config.REVIEW_DIR / "dt" / "survey.verbatim.md").read_text()
        assert "Allowlist: none configured" in text

    def test_the_allowlist_path_is_shown_relative_to_the_project(
        self, ledger_con, tmp_path, monkeypatch
    ):
        draft = self._planted(ledger_con, tmp_path)
        monkeypatch.setattr(config, "PROJECT_ROOT", config.CONTENT_DIR.parent)

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        text = (config.REVIEW_DIR / "dt" / "survey.verbatim.md").read_text()
        line = next(line for line in text.splitlines() if line.startswith("- Allowlist:"))
        assert line == (
            f"- Allowlist: none configured (`{config.CONTENT_DIR.name}/verbatim_allowlist.toml`"
            " not found)"
        )

    def test_report_records_the_allowlist_path_and_suppressed_count(self, ledger_con, tmp_path):
        draft = self._planted(ledger_con, tmp_path)
        config.VERBATIM_ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.VERBATIM_ALLOWLIST_PATH.write_text(
            'phrases = ["alpha beta gamma delta epsilon zeta eta theta"]\n'
        )

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        text = (config.REVIEW_DIR / "dt" / "survey.verbatim.md").read_text()
        assert str(config.VERBATIM_ALLOWLIST_PATH) in text
        assert "1 finding(s) suppressed" in text

    def test_report_caveats_when_limit_truncated_before_bucketing(self, ledger_con, tmp_path):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), limit=1, write=True, formats=["md"])

        text = (config.REVIEW_DIR / "dt" / "survey.verbatim.md").read_text()
        assert "capped at `--limit 1`" in text

    def test_report_has_no_limit_caveat_when_limit_is_unset(self, ledger_con, tmp_path):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        text = (config.REVIEW_DIR / "dt" / "survey.verbatim.md").read_text()
        assert "capped at" not in text


class TestScanCommand:
    def test_records_the_reporting_floor(self):
        assert vc.scan_command("d.md", 8, 1, None, False, False) == (
            "python -m chitragupta.review verbatim scan d.md --min-run 8 --gap 1"
        )

    def test_records_a_limit_only_when_one_was_given(self):
        assert "--limit" not in vc.scan_command("d.md", 8, 1, None, False, False)
        assert "--limit 3" in vc.scan_command("d.md", 8, 1, 3, False, False)

    def test_records_write_and_json(self):
        command = vc.scan_command("d.md", 8, 1, None, True, True)
        assert command.endswith("--write --json")

    def test_a_draft_path_with_a_space_stays_re_runnable(self):
        assert "'my draft.md'" in vc.scan_command("my draft.md", 8, 1, None, False, False)


class TestScanPayload:
    def _planted(self, ledger_con, tmp_path):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "uncited_2024",
            "alpha beta gamma delta epsilon zeta eta theta iota kappa",
        )
        draft = tmp_path / "draft.md"
        draft.write_text(
            "Connective prose citing nobody: alpha beta gamma delta epsilon zeta eta theta.\n"
        )
        return draft

    def test_prints_valid_json_instead_of_the_text_form(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), as_json=True)

        payload = json.loads(capsys.readouterr().out)
        assert payload["aid"] == "verbatim"
        assert payload["draft"] == str(draft)
        assert [f["citekey"] for f in payload["findings"]] == ["uncited_2024"]

    def test_carries_the_reporting_floor_that_produced_it(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), min_run=9, gap=2, limit=5, as_json=True)

        payload = json.loads(capsys.readouterr().out)
        assert (payload["min_run"], payload["gap"], payload["limit"]) == (9, 2, 5)

    def test_the_default_min_run_is_reported_as_the_number_it_resolved_to(
        self, ledger_con, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), as_json=True)

        assert json.loads(capsys.readouterr().out)["min_run"] == overlap_index.DEFAULT_N

    def test_a_finding_carries_exactly_the_published_fields(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), as_json=True)

        finding = json.loads(capsys.readouterr().out)["findings"][0]
        assert list(finding) == [
            "id",
            "citekey",
            "page",
            "end_page",
            "tier",
            "span_words",
            "matched_words",
            "start",
            "line",
            "paragraph",
            "end_paragraph",
            "char_start",
            "char_end",
            "draft_text",
            "fragment",
            "context",
            "cites_source",
            "quoted",
            "score",
            "source_text",
            "names",
            "severity",
        ]

    def test_the_flags_are_booleans_not_the_printed_labels(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), as_json=True)

        out = capsys.readouterr().out
        assert "UNCITED SOURCE" not in out
        finding = json.loads(out)["findings"][0]
        assert finding["cites_source"] is False
        assert finding["quoted"] is False

    def test_a_quoted_run_from_a_cited_source_sets_both_bits(self, ledger_con, tmp_path, capsys):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "cited_2024",
            "alpha beta gamma delta epsilon zeta eta theta iota kappa",
        )
        draft = tmp_path / "draft.md"
        draft.write_text(
            'As [@cited_2024] puts it, "alpha beta gamma delta epsilon zeta eta theta" exactly.\n'
        )

        vc.cmd_scan(str(draft), as_json=True)

        finding = json.loads(capsys.readouterr().out)["findings"][0]
        assert finding["cites_source"] is True
        assert finding["quoted"] is True

    def test_it_serialises_the_same_findings_the_text_form_prints(
        self, ledger_con, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)

        findings, min_run, suppressed, _ = vc.scan_findings(str(draft))
        vc.cmd_scan(str(draft), as_json=True)
        payload = json.loads(capsys.readouterr().out)

        assert payload["suppressed"] == suppressed
        assert len(payload["findings"]) == len(findings)
        for serialised, finding in zip(payload["findings"], findings):
            assert serialised["fragment"] == finding["fragment"]
            assert serialised["span_words"] == finding["span_words"]
            assert serialised["severity"] == vc._bucket(finding)
            expected = vc._flags(finding)
            assert (not serialised["cites_source"]) == ("UNCITED SOURCE" in expected)
            assert serialised["quoted"] == ("quoted" in expected)

    def test_start_is_a_word_offset_into_the_normalised_stream(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), as_json=True)

        finding = json.loads(capsys.readouterr().out)["findings"][0]
        words, _ = vc._tokenize_draft(draft.read_text())
        start, end = finding["start"], finding["start"] + finding["span_words"]
        assert " ".join(w.text for w in words[start:end]) == finding["fragment"]


class TestFindingLocators:
    def _payload(self, draft, capsys, **kwargs):
        vc.cmd_scan(str(draft), as_json=True, **kwargs)
        return json.loads(capsys.readouterr().out)

    def _planted(self, ledger_con, tmp_path, prefix="Connective prose citing nobody: "):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "uncited_2024",
            "alpha beta gamma delta epsilon zeta eta theta iota kappa",
        )
        draft = tmp_path / "draft.md"
        draft.write_text(f"{prefix}Alpha Beta gamma delta epsilon zeta eta theta.\n")
        return draft

    def test_draft_text_slices_the_draft_as_written(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)

        finding = self._payload(draft, capsys)["findings"][0]

        text = draft.read_text()
        assert text[finding["char_start"] : finding["char_end"]] == finding["draft_text"]

    def test_draft_text_keeps_the_casing_the_normalised_fragment_lost(
        self, ledger_con, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)

        finding = self._payload(draft, capsys)["findings"][0]

        assert finding["fragment"] == "alpha beta gamma delta epsilon zeta eta theta"
        assert finding["draft_text"] == "Alpha Beta gamma delta epsilon zeta eta theta"

    def test_draft_text_keeps_a_citation_marker_sitting_inside_the_run(
        self, ledger_con, tmp_path, capsys
    ):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "cited_2024",
            "alpha beta gamma delta epsilon zeta eta theta iota kappa",
        )
        draft = tmp_path / "draft.md"
        draft.write_text("Text: alpha beta gamma [@cited_2024] delta epsilon zeta eta theta.\n")

        finding = self._payload(draft, capsys)["findings"][0]

        assert "[@cited_2024]" in finding["draft_text"]
        assert "cited_2024" not in finding["fragment"]

    def test_line_is_the_one_based_line_of_the_runs_first_word(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path, prefix="Heading line.\n\nSecond line: ")

        finding = self._payload(draft, capsys)["findings"][0]

        assert finding["line"] == 3

    def test_a_run_spanning_a_line_break_carries_the_break(self, ledger_con, tmp_path, capsys):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "uncited_2024",
            "alpha beta gamma delta epsilon zeta eta theta iota kappa",
        )
        draft = tmp_path / "draft.md"
        draft.write_text("Prose: alpha beta gamma delta\nepsilon zeta eta theta.\n")

        finding = self._payload(draft, capsys)["findings"][0]

        assert "\n" in finding["draft_text"]
        assert (
            draft.read_text()[finding["char_start"] : finding["char_end"]] == finding["draft_text"]
        )

    def test_the_span_covers_interior_punctuation_but_stops_at_the_last_word(
        self, ledger_con, tmp_path, capsys
    ):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "uncited_2024",
            "alpha beta gamma delta epsilon zeta eta theta iota kappa",
        )
        draft = tmp_path / "draft.md"
        draft.write_text('Prose: "Alpha beta-gamma, delta epsilon zeta eta theta." End.\n')

        finding = self._payload(draft, capsys)["findings"][0]

        text = draft.read_text()
        assert finding["draft_text"] == "Alpha beta-gamma, delta epsilon zeta eta theta"
        assert text[finding["char_end"] : finding["char_end"] + 2] == '."'
        assert text[finding["char_start"] - 1] == '"'

    def test_the_id_is_stable_across_an_edit_elsewhere_in_the_draft(
        self, ledger_con, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)
        before = self._payload(draft, capsys)["findings"][0]

        draft.write_text("A new opening sentence.\n\n" + draft.read_text())
        after = self._payload(draft, capsys)["findings"][0]

        assert before["id"] == after["id"]
        assert before["start"] != after["start"]

    def test_the_id_changes_when_the_matched_wording_changes(self, ledger_con, tmp_path, capsys):
        source = (
            "one two three four five six seven eight nine ten eleven twelve "
            "thirteen fourteen fifteen sixteen seventeen eighteen"
        )
        add_parsed_item(ledger_con, tmp_path, "uncited_2024", source)
        draft = tmp_path / "draft.md"
        draft.write_text(f"Prose: {source} end.\n")
        before = self._payload(draft, capsys)["findings"][0]

        draft.write_text(draft.read_text().replace(" nine ", " ninexx "))
        after = self._payload(draft, capsys)["findings"][0]

        assert before["span_words"] == after["span_words"] == 18
        assert before["id"] != after["id"]

    def test_the_id_is_a_short_hex_digest(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)

        finding = self._payload(draft, capsys)["findings"][0]

        assert re.fullmatch(r"[0-9a-f]{12}", finding["id"])

    def test_a_clean_draft_emits_an_empty_list_not_the_prose(
        self, isolated_config, tmp_path, capsys
    ):
        draft = tmp_path / "draft.md"
        draft.write_text("Nothing to see here at all.\n")

        vc.cmd_scan(str(draft), as_json=True)

        out = capsys.readouterr().out
        assert "no verbatim run" not in out
        assert json.loads(out)["findings"] == []

    def test_the_text_path_builds_no_payload(self, ledger_con, tmp_path, capsys, monkeypatch):
        draft = self._planted(ledger_con, tmp_path)

        def unexpected(*a, **k):  # never called: that is the point
            raise AssertionError("the text path built a payload")

        monkeypatch.setattr(vc._scan_cmd, "scan_payload", unexpected)

        vc.cmd_scan(str(draft))

        assert "uncited_2024" in capsys.readouterr().out

    def test_an_unscannable_request_still_raises_rather_than_emitting_json(
        self, isolated_config, tmp_path
    ):
        draft = tmp_path / "draft.md"
        draft.write_text("Anything.\n")

        with pytest.raises(ValueError, match="--min-run must be >="):
            vc.cmd_scan(str(draft), min_run=4, as_json=True)


class TestScanJsonSibling:
    def _planted(self, ledger_con, tmp_path, name="dt/survey.md"):
        add_parsed_item(
            ledger_con,
            tmp_path,
            "cited_2024",
            "alpha beta gamma delta epsilon zeta eta theta iota kappa",
        )
        draft = config.DRAFTS_DIR / name
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(
            "As shown [@cited_2024], alpha beta gamma delta epsilon zeta eta theta appears here.\n"
        )
        return draft

    def test_written_without_json_being_asked_for(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        sibling = config.REVIEW_DIR / "dt" / "survey.verbatim.json"
        assert json.loads(sibling.read_text())["findings"][0]["citekey"] == "cited_2024"

    def test_it_is_reported_like_the_report_itself(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        assert "survey.verbatim.json" in capsys.readouterr().out

    def test_stdout_stays_pure_json_when_both_flags_are_given(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md"], as_json=True)

        captured = capsys.readouterr()
        json.loads(captured.out)  # raises if the summary leaked into it
        assert "survey.verbatim.json" in captured.err

    def test_what_it_prints_is_byte_for_byte_what_it_files(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md"], as_json=True)

        printed = capsys.readouterr().out
        assert printed == (config.REVIEW_DIR / "dt" / "survey.verbatim.json").read_text()

    def test_two_runs_over_unchanged_input_are_byte_identical(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)
        sibling = config.REVIEW_DIR / "dt" / "survey.verbatim.json"

        vc.cmd_scan(str(draft), write=True, formats=["md"])
        first = sibling.read_bytes()
        vc.cmd_scan(str(draft), write=True, formats=["md"])

        assert sibling.read_bytes() == first

    def test_the_recorded_command_regenerates_the_file(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), limit=1, write=True, formats=["md"], as_json=True)

        command = json.loads(capsys.readouterr().out)["command"]
        assert "--limit 1" in command
        assert "--write" in command
        assert "--json" in command

    def test_the_report_and_its_payload_record_the_same_command(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        review_dir = config.REVIEW_DIR / "dt"
        command = json.loads((review_dir / "survey.verbatim.json").read_text())["command"]
        assert f"- Command: `{command}`" in (review_dir / "survey.verbatim.md").read_text()

    def test_naming_json_in_formats_still_yields_the_payload(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md", "json"])

        sibling = config.REVIEW_DIR / "dt" / "survey.verbatim.json"
        assert json.loads(sibling.read_text())["aid"] == "verbatim"

    def test_a_clean_draft_still_files_a_payload(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        add_parsed_item(ledger_con, tmp_path, "cited_2024", "wholly unrelated source text here")
        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("Entirely original prose that shares nothing.\n")

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        assert (
            json.loads((config.REVIEW_DIR / "survey.verbatim.json").read_text())["findings"] == []
        )

    def test_the_payload_says_it_is_not_a_verdict(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        payload = json.loads((config.REVIEW_DIR / "dt" / "survey.verbatim.json").read_text())
        assert "never a verdict" in payload["notice"]


class TestRecheck:
    SOURCE = (
        "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu "
        "nu xi omicron pi rho sigma tau upsilon"
    )
    OTHER = (
        "one two three four five six seven eight nine ten eleven twelve "
        "thirteen fourteen fifteen sixteen"
    )

    def _planted(self, ledger_con, tmp_path):
        add_parsed_item(ledger_con, tmp_path, "uncited_2024", self.SOURCE)
        add_parsed_item(ledger_con, tmp_path, "other_2024", self.OTHER)
        draft = tmp_path / "draft.md"
        draft.write_text(f"First: {self.SOURCE}.\n\nSecond: {self.OTHER}.\n")
        return draft

    def _baseline(self, draft, tmp_path, **kwargs):
        findings, min_run, suppressed, not_run = vc.scan_findings(str(draft), **kwargs)
        command = vc.scan_command(
            str(draft), min_run, kwargs.get("gap", 1), kwargs.get("limit"), False, True
        )
        payload = vc.scan_payload(
            str(draft),
            findings,
            min_run,
            kwargs.get("gap", 1),
            kwargs.get("limit"),
            suppressed,
            command,
            not_run,
        )
        path = tmp_path / "baseline.json"
        path.write_text(json.dumps(payload, indent=2))
        return path

    def _recheck(self, draft, baseline, capsys):
        vc.cmd_recheck(str(draft), str(baseline), as_json=True)
        return json.loads(capsys.readouterr().out)

    def test_an_unchanged_draft_resolves_nothing_and_breaks_nothing(
        self, ledger_con, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)

        result = self._recheck(draft, baseline, capsys)

        assert result["resolved"] == []
        assert result["new"] == []
        assert result["objective_delta"] == 0
        assert len(result["persisting"]) == 2

    def test_a_repaired_finding_reports_as_resolved(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)
        target = next(
            f
            for f in json.loads(baseline.read_text())["findings"]
            if f["citekey"] == "uncited_2024"
        )

        draft.write_text(
            draft.read_text().replace(
                target["draft_text"], "a wholly unrelated sentence of our own"
            )
        )
        result = self._recheck(draft, baseline, capsys)

        assert [f["id"] for f in result["resolved"]] == [target["id"]]
        assert target["id"] not in [f["id"] for f in result["persisting"]]
        assert result["objective_delta"] == -1

    def test_the_edit_can_be_built_from_the_baselines_own_draft_text(self, ledger_con, tmp_path):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)

        for finding in json.loads(baseline.read_text())["findings"]:
            assert finding["draft_text"] in draft.read_text()

    def test_a_rewrite_that_introduces_new_overlap_reports_it_as_new(
        self, ledger_con, tmp_path, capsys
    ):
        third = (
            "red orange yellow green blue indigo violet white black grey "
            "silver golden copper bronze"
        )
        draft = self._planted(ledger_con, tmp_path)
        add_parsed_item(ledger_con, tmp_path, "third_2024", third)
        baseline = self._baseline(draft, tmp_path)
        target = next(
            f
            for f in json.loads(baseline.read_text())["findings"]
            if f["citekey"] == "uncited_2024"
        )

        draft.write_text(draft.read_text().replace(target["draft_text"], third))
        result = self._recheck(draft, baseline, capsys)

        assert [f["id"] for f in result["resolved"]] == [target["id"]]
        assert [f["citekey"] for f in result["new"]] == ["third_2024"]
        assert result["objective_delta"] == 0

    def test_two_identical_runs_share_an_id_and_one_repair_understates(
        self, ledger_con, tmp_path, capsys
    ):
        add_parsed_item(ledger_con, tmp_path, "uncited_2024", self.SOURCE)
        draft = tmp_path / "draft.md"
        draft.write_text(f"First: {self.SOURCE}.\n\nAgain: {self.SOURCE}.\n")
        baseline = self._baseline(draft, tmp_path)
        assert len({f["id"] for f in json.loads(baseline.read_text())["findings"]}) == 1

        draft.write_text(f"First: {self.SOURCE}.\n\nAgain: nothing borrowed here.\n")
        result = self._recheck(draft, baseline, capsys)

        assert result["resolved"] == []
        assert result["objective_delta"] == -1

    def test_the_floor_comes_from_the_baseline_not_from_a_flag(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path, min_run=18, gap=2)

        result = self._recheck(draft, baseline, capsys)

        assert (result["min_run"], result["gap"]) == (18, 2)
        assert [f["citekey"] for f in result["persisting"]] == ["uncited_2024"]

    def test_objective_counts_exclude_the_quoted_bucket(self, ledger_con, tmp_path, capsys):
        add_parsed_item(ledger_con, tmp_path, "cited_2024", self.SOURCE)
        draft = tmp_path / "draft.md"
        draft.write_text(f'As [@cited_2024] has it, "{self.SOURCE}" exactly.\n')
        baseline = self._baseline(draft, tmp_path)

        result = self._recheck(draft, baseline, capsys)

        assert [f["severity"] for f in result["persisting"]] == ["quoted"]
        assert (result["objective_before"], result["objective_after"]) == (0, 0)

    def test_objective_counts_exclude_the_embedding_tier(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)
        payload = json.loads(baseline.read_text())
        embed_finding = dict(payload["findings"][0])
        embed_finding.update({"id": "synthetic-embedding-finding", "tier": "embedding"})
        payload["findings"].append(embed_finding)
        baseline.write_text(json.dumps(payload, indent=2))

        result = self._recheck(draft, baseline, capsys)

        assert result["objective_before"] == 2
        assert "synthetic-embedding-finding" in [f["id"] for f in result["resolved"]]

    def test_a_baseline_missing_tier_is_refused(self, ledger_con, tmp_path):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)
        payload = json.loads(baseline.read_text())
        for finding in payload["findings"]:
            del finding["tier"]
        baseline.write_text(json.dumps(payload, indent=2))

        with pytest.raises(ValueError) as exc:
            vc.cmd_recheck(str(draft), str(baseline))
        assert "tier" in str(exc.value)

    def test_no_drift_warning_on_an_unchanged_host(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)

        result = self._recheck(draft, baseline, capsys)

        assert result["warnings"] == []

    def test_a_baseline_recording_different_tier_availability_warns(
        self, ledger_con, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)
        payload = json.loads(baseline.read_text())
        payload["tiers_not_run"] = []
        baseline.write_text(json.dumps(payload, indent=2))

        result = self._recheck(draft, baseline, capsys)

        assert any("tier availability changed" in w for w in result["warnings"])

    def test_a_baseline_with_a_different_corpus_key_warns(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)
        payload = json.loads(baseline.read_text())
        payload["corpus_key"] = "corpus-some-other-model"
        baseline.write_text(json.dumps(payload, indent=2))

        result = self._recheck(draft, baseline, capsys)

        assert any("corpus key changed" in w for w in result["warnings"])

    def test_a_baseline_missing_tiers_not_run_is_not_treated_as_a_mismatch(
        self, ledger_con, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)
        payload = json.loads(baseline.read_text())
        del payload["tiers_not_run"]
        baseline.write_text(json.dumps(payload, indent=2))

        result = self._recheck(draft, baseline, capsys)

        assert result["warnings"] == []

    def test_a_baseline_missing_corpus_key_is_not_treated_as_a_mismatch(
        self, ledger_con, tmp_path, capsys
    ):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)
        payload = json.loads(baseline.read_text())
        del payload["corpus_key"]
        baseline.write_text(json.dumps(payload, indent=2))

        result = self._recheck(draft, baseline, capsys)

        assert result["warnings"] == []

    def test_the_text_form_prints_the_drift_warning(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)
        payload = json.loads(baseline.read_text())
        payload["corpus_key"] = "corpus-some-other-model"
        baseline.write_text(json.dumps(payload, indent=2))

        vc.cmd_recheck(str(draft), str(baseline))

        assert "warning: corpus key changed" in capsys.readouterr().out

    def test_a_capped_baseline_is_refused(self, ledger_con, tmp_path):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path, limit=1)

        with pytest.raises(ValueError) as exc:
            vc.cmd_recheck(str(draft), str(baseline))
        assert "--limit" in str(exc.value)

    def test_a_baseline_that_is_not_json_is_refused(self, ledger_con, tmp_path):
        draft = self._planted(ledger_con, tmp_path)
        baseline = tmp_path / "baseline.json"
        baseline.write_text("not json at all")

        with pytest.raises(ValueError) as exc:
            vc.cmd_recheck(str(draft), str(baseline))
        assert "not a verbatim scan payload" in str(exc.value)

    def test_a_missing_baseline_is_refused(self, ledger_con, tmp_path):
        draft = self._planted(ledger_con, tmp_path)

        with pytest.raises(ValueError) as exc:
            vc.cmd_recheck(str(draft), str(tmp_path / "nope.json"))
        assert "nope.json" in str(exc.value)

    def test_a_baseline_predating_the_locators_is_refused(self, ledger_con, tmp_path):
        draft = self._planted(ledger_con, tmp_path)
        baseline = tmp_path / "baseline.json"
        baseline.write_text(
            json.dumps(
                {
                    "aid": "verbatim",
                    "min_run": 8,
                    "gap": 1,
                    "limit": None,
                    "findings": [{"citekey": "uncited_2024", "span_words": 20, "severity": "long"}],
                }
            )
        )

        with pytest.raises(ValueError) as exc:
            vc.cmd_recheck(str(draft), str(baseline))
        assert "predates" in str(exc.value)

    def test_a_baseline_missing_its_floor_is_refused(self, ledger_con, tmp_path):
        draft = self._planted(ledger_con, tmp_path)
        baseline = tmp_path / "baseline.json"
        baseline.write_text(json.dumps({"aid": "verbatim", "limit": None, "findings": []}))

        with pytest.raises(ValueError) as exc:
            vc.cmd_recheck(str(draft), str(baseline))
        assert "predates" in str(exc.value)

    def test_an_empty_baseline_is_not_mistaken_for_an_old_one(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)
        baseline = tmp_path / "baseline.json"
        baseline.write_text(
            json.dumps({"aid": "verbatim", "min_run": 8, "gap": 1, "limit": None, "findings": []})
        )

        result = self._recheck(draft, baseline, capsys)

        assert result["objective_before"] == 0
        assert len(result["new"]) == 2

    def test_a_baseline_missing_a_field_recheck_prints_is_refused(self, ledger_con, tmp_path):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)
        payload = json.loads(baseline.read_text())
        for finding in payload["findings"]:
            del finding["end_page"]
        baseline.write_text(json.dumps(payload, indent=2))

        with pytest.raises(ValueError) as exc:
            vc.cmd_recheck(str(draft), str(baseline))
        assert "end_page" in str(exc.value)

    @pytest.mark.parametrize("key", ["min_run", "gap"])
    @pytest.mark.parametrize("value", ["8", 8.0, True, None, [8]])
    def test_a_non_int_min_run_or_gap_is_refused_not_typeerrored(
        self, ledger_con, tmp_path, key, value
    ):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)
        payload = json.loads(baseline.read_text())
        payload[key] = value
        baseline.write_text(json.dumps(payload, indent=2))

        with pytest.raises(ValueError) as exc:
            vc.cmd_recheck(str(draft), str(baseline))
        assert key in str(exc.value)

    def test_every_field_recheck_prints_is_one_scan_actually_writes(self):
        assert set(vc._BASELINE_FIELDS) <= set(vc._PAYLOAD_FIELDS) | {"severity"}

    def test_a_findings_list_of_the_wrong_shape_is_refused_not_crashed_on(
        self, ledger_con, tmp_path
    ):
        draft = self._planted(ledger_con, tmp_path)
        baseline = tmp_path / "baseline.json"
        baseline.write_text(
            json.dumps(
                {
                    "aid": "verbatim",
                    "min_run": 8,
                    "gap": 1,
                    "limit": None,
                    "findings": [42],
                }
            )
        )

        with pytest.raises(ValueError) as exc:
            vc.cmd_recheck(str(draft), str(baseline))
        assert "predates" in str(exc.value)

    def test_another_aids_payload_is_refused(self, ledger_con, tmp_path):
        draft = self._planted(ledger_con, tmp_path)
        baseline = tmp_path / "baseline.json"
        baseline.write_text(json.dumps({"aid": "coverage", "findings": []}))

        with pytest.raises(ValueError) as exc:
            vc.cmd_recheck(str(draft), str(baseline))
        assert "not a verbatim scan payload" in str(exc.value)

    def test_the_text_form_names_every_bucket_of_the_comparison(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)
        target = next(
            f
            for f in json.loads(baseline.read_text())["findings"]
            if f["citekey"] == "uncited_2024"
        )
        draft.write_text(
            draft.read_text().replace(
                target["draft_text"], "a wholly unrelated sentence of our own"
            )
        )

        vc.cmd_recheck(str(draft), str(baseline))

        out = capsys.readouterr().out
        assert "resolved (1)" in out
        assert "persisting (1)" in out
        assert "new (0)" in out
        assert target["id"] in out

    def test_the_text_form_states_the_objective_delta(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)

        vc.cmd_recheck(str(draft), str(baseline))

        assert "2 -> 2" in capsys.readouterr().out

    def _reversioned(self, draft, tmp_path, version):
        baseline = self._baseline(draft, tmp_path)
        payload = json.loads(baseline.read_text())
        payload["version"] = version
        baseline.write_text(json.dumps(payload, indent=2))
        return baseline

    def test_a_baseline_from_an_earlier_release_series_is_refused(self, ledger_con, tmp_path):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._reversioned(draft, tmp_path, "5.4.0")

        with pytest.raises(ValueError) as exc:
            vc.cmd_recheck(str(draft), str(baseline))
        assert "5.4.0" in str(exc.value)
        assert "Re-scan" in str(exc.value)

    def test_a_patch_level_difference_is_accepted_silently(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)
        current = ".".join(vc.review.version().split(".")[:2])
        baseline = self._reversioned(draft, tmp_path, f"{current}.99")

        result = self._recheck(draft, baseline, capsys)

        assert result["baseline_version"] == f"{current}.99"
        assert len(result["persisting"]) == 2

    def test_an_unknowable_version_is_not_treated_as_a_mismatch(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._reversioned(draft, tmp_path, "unknown")

        result = self._recheck(draft, baseline, capsys)

        assert result["baseline_version"] == "unknown"

    def test_a_non_string_version_is_not_treated_as_a_mismatch(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._reversioned(draft, tmp_path, 5)

        result = self._recheck(draft, baseline, capsys)

        assert result["baseline_version"] == 5

    def test_it_publishes_findings_in_the_same_shape_scan_does(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)

        result = self._recheck(draft, baseline, capsys)

        expected = list(json.loads(baseline.read_text())["findings"][0])
        for finding in result["persisting"] + result["new"]:
            assert list(finding) == expected

    def test_the_payload_carries_the_envelope_every_aid_shares(self, ledger_con, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)

        result = self._recheck(draft, baseline, capsys)

        assert result["aid"] == "verbatim"
        assert result["draft"] == str(draft)
        assert "never a verdict" in result["notice"]
        assert "recheck" in result["command"]
        assert result["baseline"] == str(baseline)


class TestBoundedInt:
    def test_casts_a_valid_value(self):
        assert vc._bounded_int(1, "--n")("12") == 12

    def test_a_non_integer_is_a_usage_error(self):
        to_int = vc._bounded_int(1, "--n")
        with pytest.raises(argparse.ArgumentTypeError) as exc:
            to_int("not-a-number")
        assert "not a valid value" in str(exc.value)

    def test_a_below_minimum_value_is_a_usage_error(self):
        to_int = vc._bounded_int(1, "--n")
        with pytest.raises(argparse.ArgumentTypeError) as exc:
            to_int("0")
        assert "--n must be >= 1" in str(exc.value)


def _content_draft(tmp_path, text, name="draft.md"):
    path = tmp_path / "content" / "drafts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class TestMainInProcess:
    def test_no_argv_prints_usage_and_exits_zero(self, capsys):
        assert vc.main([]) == 0
        assert "Usage:" in capsys.readouterr().out

    def test_dispatches_a_mode(self, isolated_config, tmp_path, capsys):
        draft = _content_draft(tmp_path, "Nothing to see here at all.\n")

        assert vc.main(["scan", str(draft)]) == 0
        assert "no verbatim run of >= 8 words found" in capsys.readouterr().out

    def test_the_json_flag_reaches_the_scan(self, isolated_config, tmp_path, capsys):
        draft = _content_draft(tmp_path, "Nothing to see here at all.\n")

        assert vc.main(["scan", str(draft), "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["findings"] == []

    def test_a_draft_outside_content_exits_one(self, isolated_config, tmp_path, capsys):
        outside = tmp_path / "not-in-content.md"
        outside.write_text("Anything.\n")

        assert vc.main(["scan", str(outside)]) == 1

    def test_dispatches_overlap(self, isolated_config, tmp_path, capsys):
        draft = _content_draft(tmp_path, "Some claim citing nonexistent_key_2024.\n")

        assert vc.main(["overlap", str(draft), "nonexistent_key_2024"]) == 0
        assert "no source text for nonexistent_key_2024" in capsys.readouterr().out

    def test_dispatches_locate_without_a_draft(self, isolated_config, capsys):
        assert vc.main(["locate", "nonexistent_key_2024", "a phrase"]) == 0
        assert "nonexistent_key_2024" in capsys.readouterr().out

    def test_dispatches_recheck(self, isolated_config, tmp_path, capsys):
        draft = _content_draft(tmp_path, "Nothing to see here at all.\n")
        baseline = tmp_path / "baseline.json"
        baseline.write_text(
            json.dumps({"aid": "verbatim", "min_run": 8, "gap": 1, "limit": None, "findings": []})
        )

        assert vc.main(["recheck", str(draft), "--baseline", str(baseline)]) == 0
        assert "objective findings (long + short): 0 -> 0 (+0)" in capsys.readouterr().out

    def test_an_unusable_baseline_exits_two(self, isolated_config, tmp_path, capsys):
        draft = _content_draft(tmp_path, "Anything.\n")
        baseline = tmp_path / "baseline.json"
        baseline.write_text(json.dumps({"aid": "verbatim", "findings": [], "limit": 5}))

        assert vc.main(["recheck", str(draft), "--baseline", str(baseline)]) == 2
        assert "--limit 5" in capsys.readouterr().err

    def test_an_unscannable_request_exits_two(self, isolated_config, tmp_path, capsys):
        draft = _content_draft(tmp_path, "Anything.\n")

        assert vc.main(["scan", str(draft), "--min-run", "4"]) == 2


class TestCliDispatch:
    def test_overlap_mode_via_subprocess(self, tmp_path):
        draft = _content_draft(tmp_path, "Some claim citing nonexistent_key_2024.\n")

        result = run_python(
            "-m",
            "chitragupta.review",
            "verbatim",
            "overlap",
            str(draft),
            "nonexistent_key_2024",
            env={**os.environ, "CONTENT_DIR": str(tmp_path / "content")},
        )
        assert result.returncode == 0
        assert "no source text for nonexistent_key_2024" in result.stdout

    def test_scan_mode_via_subprocess(self, tmp_path):
        draft = _content_draft(tmp_path, "Nothing to see here at all.\n")

        result = run_python(
            "-m",
            "chitragupta.review",
            "verbatim",
            "scan",
            str(draft),
            "--min-run",
            "8",
            "--gap",
            "1",
            env={**os.environ, "CONTENT_DIR": str(tmp_path / "content")},
        )
        assert result.returncode == 0
        assert "no verbatim run" in result.stdout

    def test_scan_json_mode_via_subprocess_prints_only_the_payload(self, tmp_path):
        draft = _content_draft(tmp_path, "Nothing to see here at all.\n")

        result = run_python(
            "-m",
            "chitragupta.review",
            "verbatim",
            "scan",
            str(draft),
            "--json",
            env={**os.environ, "CONTENT_DIR": str(tmp_path / "content")},
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["aid"] == "verbatim"

    def test_locate_needs_no_draft_and_so_skips_the_draft_check(self, tmp_path):
        result = run_python(
            "-m",
            "chitragupta.review",
            "verbatim",
            "locate",
            "nonexistent_key_2024",
            "a phrase",
            env={**os.environ, "CONTENT_DIR": str(tmp_path / "content")},
        )
        assert result.returncode == 0, result.stderr
        assert "nonexistent_key_2024" in result.stdout

    def test_a_draft_outside_the_content_dir_is_refused(self, tmp_path):
        outside = tmp_path / "outside.md"
        outside.write_text("Anything.\n")

        result = run_python(
            "-m",
            "chitragupta.review",
            "verbatim",
            "scan",
            str(outside),
            env={**os.environ, "CONTENT_DIR": str(tmp_path / "content")},
        )
        assert result.returncode == 1
        assert "outside the content directory" in result.stderr

    def test_unknown_mode_is_a_usage_error(self, tmp_path):
        result = run_python("-m", "chitragupta.review", "verbatim", "bogus-mode")
        assert result.returncode == 2
        assert "invalid choice: 'bogus-mode'" in result.stderr

    def test_no_mode_prints_this_aids_usage_and_exits_zero(self, tmp_path):
        result = run_python("-m", "chitragupta.review", "verbatim")
        assert result.returncode == 0
        assert "Usage: python -m chitragupta.review verbatim" in result.stdout

    def test_overlap_mode_missing_arguments_exits_cleanly(self, tmp_path):
        result = run_python("-m", "chitragupta.review", "verbatim", "overlap", "only-one-arg")
        assert result.returncode == 2
        assert "Usage: python -m chitragupta.review verbatim overlap" in result.stderr

    def test_scan_mode_missing_draft_exits_cleanly(self, tmp_path):
        result = run_python("-m", "chitragupta.review", "verbatim", "scan")
        assert result.returncode == 2
        assert "Usage: python -m chitragupta.review verbatim scan" in result.stderr

    def test_overlap_mode_extra_positional_argument_exits_cleanly(self, tmp_path):
        result = run_python(
            "-m", "chitragupta.review", "verbatim", "overlap", "draft.md", "citekey", "extra"
        )
        assert result.returncode == 2
        assert "unrecognized arguments: extra" in result.stderr

    def test_overlap_mode_n_below_one_exits_cleanly(self, tmp_path):
        result = run_python(
            "-m", "chitragupta.review", "verbatim", "overlap", "draft.md", "citekey", "--n", "0"
        )
        assert result.returncode == 2
        assert "--n must be >= 1" in result.stderr

    def test_scan_mode_extra_positional_argument_exits_cleanly(self, tmp_path):
        result = run_python("-m", "chitragupta.review", "verbatim", "scan", "draft.md", "extra")
        assert result.returncode == 2
        assert "unrecognized arguments: extra" in result.stderr

    def test_scan_mode_negative_gap_exits_cleanly(self, tmp_path):
        result = run_python(
            "-m", "chitragupta.review", "verbatim", "scan", "draft.md", "--gap", "-1"
        )
        assert result.returncode == 2
        assert "--gap must be >= 0" in result.stderr

    def test_scan_mode_limit_zero_exits_cleanly(self, tmp_path):
        result = run_python(
            "-m", "chitragupta.review", "verbatim", "scan", "draft.md", "--limit", "0"
        )
        assert result.returncode == 2
        assert "--limit must be >= 1" in result.stderr

    def test_scan_mode_min_run_below_index_n_exits_cleanly(self, tmp_path):
        draft = _content_draft(tmp_path, "Anything.\n")

        result = run_python(
            "-m",
            "chitragupta.review",
            "verbatim",
            "scan",
            str(draft),
            "--min-run",
            "4",
            env={**os.environ, "CONTENT_DIR": str(tmp_path / "content")},
        )
        assert result.returncode == 2
        assert "--min-run must be >=" in result.stderr

    def test_locate_mode_missing_arguments_exits_cleanly(self, tmp_path):
        result = run_python("-m", "chitragupta.review", "verbatim", "locate", "only-one-arg")
        assert result.returncode == 2
        assert "Usage: python -m chitragupta.review verbatim locate" in result.stderr


class FakeScopeEmbedder:
    def __init__(self, scores):
        self.scores = scores

    def encode(self, texts):
        return list(texts)

    def encode_lists(self, texts):
        return [[float(len(text))] for text in texts]

    def similarity(self, left, right):
        return [
            [
                max(
                    (score for (a, b), score in self.scores.items() if a in first and b in second),
                    default=0.0,
                )
                for second in right
            ]
            for first in left
        ]


@pytest.fixture
def tier3(monkeypatch, ledger_con):
    def install(scores, sections=None, missing=frozenset()):
        class FakeCollection:
            def query(self, query_embeddings, n_results, where, include=None):
                return {"metadatas": [[]], "distances": [[]]}

            def get(self, where, include=None, limit=None, offset=None):
                wanted = where["citekey"]["$in"]
                rows = [{"citekey": k} for k in wanted if k not in missing][offset or 0 :]
                return {"ids": [f"row{i}" for i in range(len(rows))], "metadatas": rows}

        scope = overlap_embed.Scope(
            sections if sections is not None else {"Section": ["source_2024"]},
            FakeCollection(),
            ledger_con,
            FakeScopeEmbedder(scores),
        )
        monkeypatch.setattr(overlap_embed, "open_scope", lambda draft: (scope, None))
        monkeypatch.setattr(style_exceptions, "terms", lambda: ())
        return scope

    return install


def _tier3_draft(text):
    path = config.DRAFTS_DIR / "topic" / "draft.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _add_sidecar(citekey, records):
    path = config.DOCLING_DIR / f"{citekey}.passages.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records), encoding="utf-8")


class TestEmbeddingTier:
    def test_a_restatement_is_reported_with_its_tier_and_score(self, ledger_con, tmp_path, tier3):
        add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
        _add_sidecar(
            "source_2024",
            [
                {
                    "text": "Firms save their return on investment while adapting to "
                    "modern technologies with minimal risk.",
                    "label": "text",
                    "page": 9,
                },
            ],
        )
        tier3({("protecting", "save their"): 0.95})
        draft = _tier3_draft(
            "# Section\n\nThe study reports a strategy of protecting profit "
            "while adopting new tooling at low exposure.\n"
        )

        findings, _min_run, _suppressed, not_run = vc.scan_findings(str(draft))

        [found] = [f for f in findings if f["tier"] == "embedding"]
        assert found["citekey"] == "source_2024"
        assert found["page"] == found["end_page"] == 9
        assert found["score"] > 0
        assert not_run == []

    def test_the_finding_locates_itself_in_the_draft_as_written(self, ledger_con, tmp_path, tier3):
        add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
        _add_sidecar(
            "source_2024",
            [
                {"text": "A restated claim about the subject.", "label": "text", "page": 2},
            ],
        )
        tier3({("protecting", "restated claim"): 0.95})
        body = "# Section\n\nThe study reports a strategy of protecting profit here.\n"
        draft = _tier3_draft(body)

        findings, _, _, _ = vc.scan_findings(str(draft))

        [found] = [f for f in findings if f["tier"] == "embedding"]
        assert body[found["char_start"] : found["char_end"]] == found["draft_text"]

    def test_the_finding_carries_the_source_passage_it_aligned_against(
        self, ledger_con, tmp_path, tier3
    ):
        add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
        _add_sidecar(
            "source_2024",
            [
                {"text": "A restated claim about the subject.", "label": "text", "page": 2},
            ],
        )
        tier3({("protecting", "restated claim"): 0.95})
        draft = _tier3_draft(
            "# Section\n\nThe study reports a strategy of protecting profit here.\n"
        )

        findings, _, _, _ = vc.scan_findings(str(draft))

        [found] = [f for f in findings if f["tier"] == "embedding"]
        assert found["source_text"] == "A restated claim about the subject."
        assert found["source_text"] != found["fragment"]

    def test_a_deterministic_tier_reports_no_separate_source_side(self, ledger_con, tmp_path):
        draft = _content_draft(
            tmp_path, "A phrase repeated verbatim from the corpus source text here.\n"
        )
        add_parsed_item(
            ledger_con,
            tmp_path,
            "source_2024",
            "A phrase repeated verbatim from the corpus source text here.",
        )

        findings, _, _, _ = vc.scan_findings(str(draft))

        assert findings
        assert all(f["source_text"] is None for f in findings)

    def test_a_passage_a_deterministic_tier_already_found_is_not_reported_twice(
        self, ledger_con, tmp_path, tier3
    ):
        shared = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
        add_parsed_item(ledger_con, tmp_path, "source_2024", shared)
        _add_sidecar(
            "source_2024",
            [
                {"text": shared + ".", "label": "text", "page": 1},
            ],
        )
        tier3({("alpha", "alpha"): 0.95})
        draft = _tier3_draft(f"# Section\n\n{shared} and then some more prose.\n")

        findings, _, _, _ = vc.scan_findings(str(draft))

        assert [f["tier"] for f in findings if f["tier"] == "embedding"] == []
        assert any(f["tier"] == "exact" for f in findings)

    def test_a_real_paraphrase_survives_the_cap_when_the_same_section_also_quotes(
        self, ledger_con, tmp_path, tier3
    ):
        shared = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
        add_parsed_item(ledger_con, tmp_path, "quoted_2024", shared)
        _add_sidecar("quoted_2024", [{"text": shared + ".", "label": "text", "page": 1}])
        add_parsed_item(ledger_con, tmp_path, "paraphrased_2024", "unrelated corpus text")
        _add_sidecar(
            "paraphrased_2024",
            [
                {
                    "text": "Firms save their return on investment while adapting to "
                    "modern technologies with minimal risk.",
                    "label": "text",
                    "page": 9,
                },
            ],
        )
        tier3(
            {("alpha", "alpha"): 0.95, ("protecting", "save their"): 0.85},
            sections={"Section": ["quoted_2024", "paraphrased_2024"]},
        )
        draft = _tier3_draft(
            f"# Section\n\n{shared} and then some more prose. The study reports a "
            "strategy of protecting profit while adopting new tooling at low "
            "exposure.\n"
        )

        findings, _, _, _ = vc.scan_findings(str(draft))

        [embed] = [f for f in findings if f["tier"] == "embedding"]
        assert embed["citekey"] == "paraphrased_2024"
        assert embed["page"] == embed["end_page"] == 9
        assert any(f["tier"] == "exact" for f in findings)

    def test_the_allowlist_suppresses_a_tier_three_finding_too(
        self, ledger_con, tmp_path, tier3, monkeypatch
    ):
        add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
        _add_sidecar(
            "source_2024",
            [
                {"text": "A restated claim about the subject.", "label": "text", "page": 2},
            ],
        )
        boilerplate = (
            "the digital twin consistency framework applies here as described in the standard"
        )
        tier3({("digital twin", "restated claim"): 0.95})
        draft = _tier3_draft(f"# Section\n\n{boilerplate}.\n")
        config.VERBATIM_ALLOWLIST_PATH.write_text(
            f'phrases = ["{boilerplate}"]\n', encoding="utf-8"
        )

        findings, _, suppressed, _ = vc.scan_findings(str(draft))

        assert [f for f in findings if f["tier"] == "embedding"] == []
        assert suppressed == 1

    def test_an_alignment_shorter_than_the_floor_is_not_reported(self, ledger_con, tmp_path, tier3):
        add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
        _add_sidecar(
            "source_2024",
            [
                {"text": "A restated claim about the subject.", "label": "text", "page": 2},
            ],
        )
        tier3({("brief", "restated claim"): 0.95})
        draft = _tier3_draft("# Section\n\nA brief note.\n")

        findings, _, suppressed, _ = vc.scan_findings(str(draft))

        assert [f for f in findings if f["tier"] == "embedding"] == []
        assert suppressed == 0

    def test_an_allowlist_that_covers_only_part_of_a_span_leaves_it_reported(
        self, ledger_con, tmp_path, tier3
    ):
        add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
        _add_sidecar(
            "source_2024",
            [
                {"text": "A restated claim about the subject.", "label": "text", "page": 2},
            ],
        )
        tier3({("digital twin", "restated claim"): 0.95})
        draft = _tier3_draft(
            "# Section\n\nthe digital twin consistency framework applies here as "
            "described in the standard.\n"
        )
        config.VERBATIM_ALLOWLIST_PATH.write_text('acronyms = ["digital twin"]\n', encoding="utf-8")

        findings, _, suppressed, _ = vc.scan_findings(str(draft))

        assert [f["tier"] for f in findings if f["tier"] == "embedding"] == ["embedding"]
        assert suppressed == 0

    def test_an_alignment_straddling_the_opening_quote_mark_is_still_quoted(
        self, ledger_con, tmp_path, tier3
    ):
        add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
        _add_sidecar(
            "source_2024",
            [
                {
                    "text": "Firms save their return on investment while adapting to "
                    "modern technologies with minimal risk.",
                    "label": "text",
                    "page": 9,
                },
            ],
        )
        tier3({("protecting", "save their"): 0.95})
        draft = _tier3_draft(
            '# Section\n\nThe study reports a strategy of "protecting profit '
            'while adopting new tooling at low exposure".\n'
        )

        findings, _min_run, _suppressed, _ = vc.scan_findings(str(draft))

        [found] = [f for f in findings if f["tier"] == "embedding"]
        assert found["fragment"].startswith("the study reports")
        assert found["quoted"] is True

    def test_an_unavailable_tier_is_named_with_its_reason_not_silently_empty(
        self, ledger_con, tmp_path
    ):
        draft = tmp_path / "draft.md"
        draft.write_text("Some prose with no dossier anywhere.\n")

        findings, _, _, not_run = vc.scan_findings(str(draft))

        assert findings == []
        assert [entry["tier"] for entry in not_run] == ["embedding"]
        assert "no dossier" in not_run[0]["reason"]

    def test_a_dossier_naming_no_section_of_this_draft_says_how_to_fix_it(
        self, ledger_con, tmp_path, tier3
    ):
        tier3({}, sections={"A Heading That Was Renamed": ["source_2024"]})
        draft = _tier3_draft("# Current Heading\n\nProse under it.\n")

        _findings, _, _, not_run = vc.scan_findings(str(draft))

        assert "sections.md" in not_run[0]["reason"]
        assert "--citekeys --write" in not_run[0]["reason"]

    def test_a_partly_renamed_dossier_still_scans_the_matched_section_and_says_so(
        self, ledger_con, tmp_path, tier3
    ):
        add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
        _add_sidecar(
            "source_2024",
            [{"text": "A restated claim about the subject.", "label": "text", "page": 2}],
        )
        tier3(
            {("protecting", "restated claim"): 0.95},
            sections={"Current Heading": ["source_2024"], "A Heading That Was Renamed": ["k_2024"]},
        )
        draft = _tier3_draft(
            "# Current Heading\n\nThe study reports a strategy of protecting profit here.\n"
        )

        findings, _, _, not_run = vc.scan_findings(str(draft))

        assert any(f["tier"] == "embedding" for f in findings)
        [entry] = [e for e in not_run if "1 of 2" in e["reason"]]
        assert entry["partial"] is True
        assert "renamed" in entry["reason"]

    def test_the_denominator_counts_every_recorded_section_not_only_the_ones_with_prose(
        self, ledger_con, tmp_path, tier3
    ):
        add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
        _add_sidecar(
            "source_2024",
            [{"text": "A restated claim about the subject.", "label": "text", "page": 2}],
        )
        tier3(
            {("protecting", "restated claim"): 0.95},
            sections={
                "Current Heading": ["source_2024"],
                "Empty Heading": ["k_2024"],
                "A Heading That Was Renamed": ["k_2024"],
            },
        )
        draft = _tier3_draft(
            "# Current Heading\n\nThe study reports a strategy of protecting profit here.\n"
            "\n# Empty Heading\n\n# Trailing\n\nMore unrelated prose.\n"
        )

        _findings, _, _, not_run = vc.scan_findings(str(draft))

        [entry] = [e for e in not_run if "section(s) the dossier's" in e["reason"]]
        assert "1 of 3" in entry["reason"]

    def test_a_cited_source_absent_from_the_collection_is_named_as_a_partial_gap(
        self, ledger_con, tmp_path, tier3
    ):
        add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
        _add_sidecar(
            "source_2024",
            [{"text": "A restated claim about the subject.", "label": "text", "page": 2}],
        )
        tier3({("protecting", "restated claim"): 0.95}, missing={"source_2024"})
        draft = _tier3_draft(
            "# Section\n\nThe study reports a strategy of protecting profit here.\n"
        )

        _findings, _, _, not_run = vc.scan_findings(str(draft))

        [entry] = [e for e in not_run if "1 cited source" in e["reason"]]
        assert entry["partial"] is True
        assert "enrich" in entry["reason"]


class TestReportingWhatDidNotRun:
    def test_the_printed_form_names_the_tier_and_the_reason(self):
        text = vc.format_scan([], 8, 0, [{"tier": "embedding", "reason": "no dossier"}])
        assert "tier embedding did not run: no dossier" in text

    def test_the_written_report_distinguishes_never_ran_from_found_nothing(self):
        incomplete = vc.render_scan_markdown(
            Path("content/drafts/d.md"),
            [],
            8,
            None,
            "cmd",
            0,
            [{"tier": "embedding", "reason": "no dossier"}],
        )
        complete = vc.render_scan_markdown(
            Path("content/drafts/d.md"),
            [],
            8,
            None,
            "cmd",
            0,
            [],
        )
        assert "this run was" in incomplete and "not complete" in incomplete
        assert "The tier that can see one did" in incomplete
        assert "not complete" not in complete
        assert "checked against all three tiers" in complete

    def test_a_partial_gap_reads_differently_from_a_tier_that_never_ran(self):
        partial = vc.render_scan_markdown(
            Path("content/drafts/d.md"),
            [],
            8,
            None,
            "cmd",
            0,
            [{"tier": "embedding", "reason": "1 of 2 section(s) ... renamed", "partial": True}],
        )
        assert "this run was" in partial and "not complete" in partial
        assert "The tier that can see one did" not in partial
        assert "1 of 2 section(s)" in partial

    def test_a_partial_entrys_bullet_line_does_not_say_did_not_run(self):
        text = vc.format_scan(
            [], 8, 0, [{"tier": "embedding", "reason": "1 of 2 renamed", "partial": True}]
        )
        assert "did not run" not in text
        assert "ran, but not against everything" in text

    def test_the_printed_form_still_says_did_not_run_for_a_tier_that_never_ran(self):
        text = vc.format_scan([], 8, 0, [{"tier": "embedding", "reason": "no dossier"}])
        assert "tier embedding did not run: no dossier" in text

    def test_the_payload_carries_what_did_not_run(self, ledger_con, tmp_path, capsys):
        draft = tmp_path / "draft.md"
        draft.write_text("Prose with no dossier anywhere at all.\n")

        vc.cmd_scan(str(draft), as_json=True)

        payload = json.loads(capsys.readouterr().out)
        assert payload["tiers_not_run"][0]["tier"] == "embedding"

    def test_the_payload_carries_the_corpus_key(self, ledger_con, tmp_path, capsys):
        draft = tmp_path / "draft.md"
        draft.write_text("Prose with no dossier anywhere at all.\n")

        vc.cmd_scan(str(draft), as_json=True)

        payload = json.loads(capsys.readouterr().out)
        assert payload["corpus_key"] == overlap_chroma.corpus_key()

    def test_a_score_rides_inside_the_tier_note_only_when_there_is_one(self):
        assert vc._tier_note({"tier": "exact", "score": None}) == "tier=exact"
        assert vc._tier_note({"tier": "embedding", "score": 0.41}) == ("tier=embedding, score=0.41")


class TestNamesHeavy:
    def test_an_organisation_name_is_names_heavy(self):
        from chitragupta.review.verbatim_check._names import names_heavy

        text = "established by the National Institute of Standards and Technology in"
        assert names_heavy(text) is True

    def test_lowercase_prose_is_not(self):
        from chitragupta.review.verbatim_check._names import names_heavy

        assert names_heavy("the model is updated from sensor data at each step") is False

    def test_sentence_initial_words_do_not_count(self):
        from chitragupta.review.verbatim_check._names import names_heavy

        assert names_heavy("Data. Models") is False

    def test_empty_is_not(self):
        from chitragupta.review.verbatim_check._names import names_heavy

        assert names_heavy("") is False

    def test_one_content_word_is_not(self):
        from chitragupta.review.verbatim_check._names import names_heavy

        assert names_heavy("of the National") is False

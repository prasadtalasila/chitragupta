"""src/review/verbatim_check.py: the review layer's verbatim-overlap,
whole-corpus scan and page-locator aid -- advisory over a finished
draft, never a gate. Reached as `python3 -m src.review verbatim <mode>`;
the module has no __main__ block of its own.

BIB/PARSED_DIR are module-level constants resolved from src.config at
import time; tests monkeypatch them directly to point at a throwaway
fixture tree. There was a REPO constant beside them until 5.0.0, when
the file moved into src/review/ and no longer needed a
Path(__file__)-derived repo root to put on sys.path."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from src.review import verbatim_check as vc
from src import config, ledger
from tests.conftest import make_reference


@pytest.fixture
def fixture_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "BIB", tmp_path / "bibliography.bib")
    monkeypatch.setattr(vc, "PARSED_DIR", tmp_path / "content" / "parsed")
    return tmp_path


class TestBibEntry:
    def test_finds_entry_by_citekey(self, fixture_repo):
        vc.BIB.write_text(
            "@article{smith_2024,\n  title = {A Paper},\n}\n"
            "@article{doe_2023,\n  title = {Another},\n}\n"
        )
        entry = vc.bib_entry("smith_2024")
        assert "smith_2024" in entry
        assert "A Paper" in entry
        assert "doe_2023" not in entry

    def test_missing_citekey_returns_empty(self, fixture_repo):
        vc.BIB.write_text("@article{smith_2024,\n  title = {A Paper},\n}\n")
        assert vc.bib_entry("nonexistent_2024") == ""

    def test_missing_bib_file_returns_empty_rather_than_raising(self, fixture_repo):
        assert not vc.BIB.exists()
        assert vc.bib_entry("anything_2024") == ""


class TestPdfPath:
    def test_resolves_pdf_from_file_field(self, fixture_repo):
        pdf = fixture_repo / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        vc.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n  file = {paper.pdf:paper.pdf:application/pdf},\n}\n"
        )
        assert vc.pdf_path("smith_2024") == pdf

    def test_multiple_attachments_picks_the_pdf(self, fixture_repo):
        pdf = fixture_repo / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        vc.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n"
            "  file = {page.html:page.html:text/html;paper.pdf:paper.pdf:application/pdf},\n}\n"
        )
        assert vc.pdf_path("smith_2024") == pdf

    def test_no_file_field_returns_none(self, fixture_repo):
        vc.BIB.write_text("@article{smith_2024,\n  title = {T},\n}\n")
        assert vc.pdf_path("smith_2024") is None

    def test_file_field_with_no_pdf_attachment_returns_none(self, fixture_repo):
        html = fixture_repo / "page.html"
        html.write_text("<html></html>")
        vc.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n"
            "  file = {page.html:page.html:text/html},\n}\n"
        )
        assert vc.pdf_path("smith_2024") is None

    def test_pdf_referenced_but_missing_on_disk_returns_none(self, fixture_repo):
        vc.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n  file = {paper.pdf:paper.pdf:application/pdf},\n}\n"
        )
        assert vc.pdf_path("smith_2024") is None

    def test_field_after_a_multiline_value_is_still_found(self, fixture_repo):
        """The second regression: bib_entry() stopped at the first "\\n}".
        A field whose closing brace sits at the start of a line -- an
        `annote` holding a URL is the real case -- truncated the entry
        there, hiding every later field including `file`. Braces are
        balanced; only the naive delimiter search was fooled. Cost 40
        papers, each of which did have a PDF on disk.
        """
        pdf = fixture_repo / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        vc.BIB.write_text(
            "@article{smith_2024,\n"
            "\ttitle = {T},\n"
            "\tannote = {codebase: https://example.invalid/x\n"
            "},\n"
            "\tfile = {paper.pdf:paper.pdf:application/pdf},\n"
            "}\n"
        )
        assert "file =" in vc.bib_entry("smith_2024")
        assert vc.pdf_path("smith_2024") == pdf

    def test_html_attachment_before_pdf_still_finds_the_pdf(self, fixture_repo):
        """Mirrors the real export: an arXiv HTML snapshot is listed
        first, the PDF second."""
        sub = fixture_repo / "pdfs" / "159"
        sub.mkdir(parents=True)
        pdf = sub / "Lu et al. - 2023 - EvoCLINICAL.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        vc.BIB.write_text(
            "@article{smith_2024,\n\tfile = {arXiv.org Snapshot:pdfs/158/2309.html:text/html;"
            "Submitted Version:pdfs/159/Lu et al. - 2023 - EvoCLINICAL.pdf:application/pdf},\n}\n"
        )
        assert vc.pdf_path("smith_2024") == pdf

    def test_unbalanced_braces_returns_what_it_has(self, fixture_repo):
        """A truncated/corrupt .bib shouldn't hang or raise -- hand back
        the remainder and let the caller find no `file` field."""
        vc.BIB.write_text("@article{smith_2024,\n\ttitle = {T},\n")
        assert vc.bib_entry("smith_2024").startswith("@article{smith_2024,")
        assert vc.pdf_path("smith_2024") is None

    def test_description_differs_from_path(self, fixture_repo):
        """The regression: this project's export writes
        `Desc.pdf:real/path.pdf:application/pdf`. Taking the first
        segment ending in `.pdf` picks the description, which only
        resolves when it coincides with the path -- as it does in a flat
        fixture dir, which is why every other test here missed this.
        Lost 196 of 501 real PDFs."""
        sub = fixture_repo / "pdfs" / "21"
        sub.mkdir(parents=True)
        pdf = sub / "Smith - 2024 - Title.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        vc.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n"
            "  file = {Smith - 2024 - Title.pdf:pdfs/21/Smith - 2024 - Title.pdf:application/pdf},\n}\n"
        )
        assert vc.pdf_path("smith_2024") == pdf

    def test_absolute_path_in_file_field(self, fixture_repo, tmp_path):
        pdf = tmp_path / "abs.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        vc.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n"
            f"  file = {{abs.pdf:{pdf}:application/pdf}},\n}}\n"
        )
        assert vc.pdf_path("smith_2024") == pdf

    def test_malformed_attachment_segment_is_skipped(self, fixture_repo):
        pdf = fixture_repo / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        vc.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n"
            "  file = {junk;paper.pdf:paper.pdf:application/pdf},\n}\n"
        )
        assert vc.pdf_path("smith_2024") == pdf

    def test_resolves_relative_to_bib_file_directory_not_repo_root(self, tmp_path, monkeypatch):
        # Regression: a relative attachment path must be anchored to
        # wherever BIB (== config.BIB_FILE_PATH, honoring a BIB_FILE
        # override) actually lives -- matching
        # src.bib_reader._resolve_pdf_path -- not the checked-out repo
        # root. A BIB_FILE pointing outside the repo used to silently fail
        # to find PDFs sitting right next to it.
        bib_dir = tmp_path / "elsewhere"
        bib_dir.mkdir()
        monkeypatch.setattr(vc, "BIB", bib_dir / "bibliography.bib")

        pdf = bib_dir / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        vc.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n  file = {paper.pdf:paper.pdf:application/pdf},\n}\n"
        )
        assert vc.pdf_path("smith_2024") == pdf


class TestPages:
    def test_falls_back_to_parsed_text_when_no_pdf(self, fixture_repo):
        vc.BIB.write_text("@article{smith_2024,\n  title = {T},\n}\n")
        parsed_dir = fixture_repo / "content" / "parsed"
        parsed_dir.mkdir(parents=True)
        (parsed_dir / "smith_2024.txt").write_text("page one text\x00\x01\fpage two text")

        result = vc.pages("smith_2024")
        assert result == ["page one text  page two text"] or len(result) == 2

    def test_no_pdf_and_no_parsed_text_returns_empty(self, fixture_repo):
        vc.BIB.write_text("@article{smith_2024,\n  title = {T},\n}\n")
        assert vc.pages("smith_2024") == []

    def test_parsed_fallback_respects_parsed_dir_override(self, tmp_path, monkeypatch):
        # Regression: the parsed-text fallback must look wherever
        # config.PARSED_DIR actually points (a CONTENT_DIR override) --
        # not at a repo-root-relative content/parsed that ignores it.
        # The REPO constant that made that mistake possible is gone as of
        # 5.0.0; this pins the behaviour that outlived it.
        monkeypatch.setattr(vc, "BIB", tmp_path / "bibliography.bib")
        custom_parsed_dir = tmp_path / "custom-content" / "parsed"
        monkeypatch.setattr(vc, "PARSED_DIR", custom_parsed_dir)
        custom_parsed_dir.mkdir(parents=True)
        (custom_parsed_dir / "smith_2024.txt").write_text("page one text")

        vc.BIB.write_text("@article{smith_2024,\n  title = {T},\n}\n")
        assert vc.pages("smith_2024") == ["page one text"]

    @pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext not installed")
    def test_real_pdf_via_pdftotext(self, fixture_repo):
        pandoc, pdflatex = shutil.which("pandoc"), shutil.which("pdflatex")
        if not (pandoc and pdflatex):
            pytest.skip("pandoc/pdflatex not installed")

        md = fixture_repo / "doc.md"
        md.write_text("# Title\n\nSome distinctive verbatim content here.\n")
        pdf = fixture_repo / "paper.pdf"
        subprocess.run(["pandoc", str(md), "-o", str(pdf), "--pdf-engine=pdflatex"], check=True, capture_output=True)

        vc.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n  file = {paper.pdf:paper.pdf:application/pdf},\n}\n"
        )
        result = vc.pages("smith_2024")
        assert any("distinctive verbatim content" in p for p in result)


class TestNorm:
    def test_tokenizes_lowercase_alnum(self):
        assert vc.norm("Hello, World! 123") == ["hello", "world", "123"]


class TestSentencesCiting:
    def test_returns_paragraphs_mentioning_citekey(self, tmp_path):
        draft = tmp_path / "draft.md"
        draft.write_text(
            "Paragraph one mentions smith_2024 here.\n\n"
            "Paragraph two does not.\n\n"
            "Paragraph three also cites smith_2024 again.\n"
        )
        result = vc.sentences_citing(str(draft), "smith_2024")
        assert len(result) == 2
        assert all("smith_2024" in p for p in result)

    def test_no_matching_paragraphs(self, tmp_path):
        draft = tmp_path / "draft.md"
        draft.write_text("Nothing relevant here.\n")
        assert vc.sentences_citing(str(draft), "smith_2024") == []


def _add_parsed_item(ledger_con, tmp_path, citekey, text, pdf_bytes=b"%PDF-1.4 dummy"):
    """A ledger row with status='parsed', a real pdf_hash, and parsed_path
    pointing at real text on disk -- what `cmd_overlap` now reads through
    src/overlap_index.py instead of pdftotext/PARSED_DIR fallback."""
    pdf = tmp_path / f"{citekey}.pdf"
    pdf.write_bytes(pdf_bytes)
    parsed = tmp_path / f"{citekey}.txt"
    parsed.write_text(text)
    ledger.upsert_reference(ledger_con, make_reference(citekey=citekey, pdf_path=str(pdf)))
    ledger.mark_parsed(ledger_con, citekey, parsed)
    return parsed


class TestCmdOverlap:
    def test_no_source_text_when_citekey_not_in_ledger(self, isolated_config, tmp_path, capsys):
        draft = tmp_path / "draft.md"
        draft.write_text("Some claim citing smith_2024.\n")
        vc.cmd_overlap(str(draft), "smith_2024")
        out = capsys.readouterr().out
        assert "no source text for smith_2024" in out

    def test_detects_verbatim_overlap_run(self, ledger_con, tmp_path, capsys):
        shared_phrase = "the quick brown fox jumps over the lazy dog repeatedly"
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", f"Intro text. {shared_phrase}. More text.")

        draft = tmp_path / "draft.md"
        draft.write_text(f"As discussed [@smith_2024], {shared_phrase} in the study.\n")

        vc.cmd_overlap(str(draft), "smith_2024", n=4)
        out = capsys.readouterr().out
        assert "words, pdf p." in out

    def test_overlap_run_extending_to_end_of_sentence(self, ledger_con, tmp_path, capsys):
        # The matching run must still be open (not yet flushed by a
        # non-matching n-gram) when the word list ends, exercising the
        # post-loop flush rather than the else-branch one.
        shared_phrase = "the quick brown fox jumps over the lazy dog"
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", f"Intro text. {shared_phrase}.")

        draft = tmp_path / "draft.md"
        draft.write_text(f"As discussed [@smith_2024], {shared_phrase}\n")

        vc.cmd_overlap(str(draft), "smith_2024", n=4)
        out = capsys.readouterr().out
        assert "words, pdf p." in out

    def test_no_overlap_found(self, ledger_con, tmp_path, capsys):
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "completely different vocabulary entirely")

        draft = tmp_path / "draft.md"
        draft.write_text("An original sentence mentioning smith_2024 with unrelated words.\n")

        vc.cmd_overlap(str(draft), "smith_2024", n=8)
        out = capsys.readouterr().out
        assert "no verbatim run of >= 8 words found" in out

    def test_matches_output_captured_from_the_pre_index_implementation(self, ledger_con, tmp_path, capsys):
        """Pinned literal output, captured from `cmd_overlap` *before* it
        was ported onto src/overlap_index.py (same fixture: a 4-gram
        shared between page 1 and page 3 of the source, to also confirm
        the ported page attribution keeps the pre-port "lowest page wins"
        behavior rather than an arbitrary posting)."""
        page1 = "Intro words padding here. alpha beta gamma delta epsilon continues on."
        page2 = "Unrelated content on the second page entirely different words."
        page3 = "Again we see alpha beta gamma delta reappear on a later page."
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "\f".join([page1, page2, page3]))

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
        vc.BIB.write_text("@article{smith_2024,\n  title = {T},\n}\n")
        parsed_dir = fixture_repo / "content" / "parsed"
        parsed_dir.mkdir(parents=True)
        (parsed_dir / "smith_2024.txt").write_text("nothing relevant\fdigital twin simulation platform")

        vc.cmd_locate("smith_2024", "digital twin simulation")
        out = capsys.readouterr().out
        assert "smith_2024: 2 pdf pages" in out
        assert "digital twin simulation" in out


class TestMergeRuns:
    def test_consecutive_positions_always_merge_at_gap_zero(self):
        assert vc._merge_runs([0, 1, 2, 3], gap=0, n=8) == [[0, 1, 2, 3]]

    def test_single_word_edit_merges_at_gap_one_not_gap_zero(self):
        # A clean anchor at 0 and the next clean anchor at n+1=9 (see
        # _merge_runs' docstring) is exactly what a single edited word
        # inside an n=8 gram produces.
        assert vc._merge_runs([0, 9], gap=1, n=8) == [[0, 9]]
        assert vc._merge_runs([0, 9], gap=0, n=8) == [[0], [9]]

    def test_far_apart_clusters_stay_separate_even_with_gap(self):
        assert vc._merge_runs([0, 1, 50, 51], gap=2, n=8) == [[0, 1], [50, 51]]

    def test_duplicate_positions_are_deduped(self):
        assert vc._merge_runs([5, 5, 5], gap=0, n=8) == [[5]]


class TestQuoteCharSpans:
    def test_straight_double_quotes_detected(self):
        spans = vc._quote_char_spans('before "a quoted phrase" after')
        assert spans and spans[0] == (7, 24)

    def test_curly_double_quotes_detected(self):
        spans = vc._quote_char_spans("before “a quoted phrase” after")
        assert spans

    def test_blockquote_line_detected(self):
        spans = vc._quote_char_spans("> a blockquote line\nnot a quote\n")
        assert spans and spans[0][0] == 0

    def test_no_quotes_returns_empty(self):
        assert vc._quote_char_spans("nothing quoted here at all") == []


class TestMaskForScan:
    def test_blanks_fenced_code(self):
        text = "before\n```\n@dataclass\n```\nafter"
        masked = vc._mask_for_scan(text)
        assert "dataclass" not in masked
        assert "before" in masked and "after" in masked

    def test_blanks_inline_code(self):
        masked = vc._mask_for_scan("use `@property` here")
        assert "property" not in masked
        assert "use" in masked and "here" in masked

    def test_blanks_references_section_onward(self):
        text = "Intro text here.\n\n## References\n\n[1] Some Title, Some Venue.\n"
        masked = vc._mask_for_scan(text)
        assert "Intro text here" in masked
        assert "Some Title" not in masked

    def test_no_references_section_leaves_text_untouched(self):
        text = "Just prose, no heading at all.\n"
        assert vc._mask_for_scan(text) == text


class TestTokenizeDraft:
    def test_flat_word_list_spans_paragraphs(self):
        text = "First paragraph words.\n\nSecond paragraph words.\n"
        words, _ = vc._tokenize_draft(text)
        assert [w.text for w in words] == ["first", "paragraph", "words", "second", "paragraph", "words"]

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


class TestCmdScan:
    def test_planted_verbatim_run_from_cited_source_is_flagged(self, ledger_con, tmp_path, capsys):
        # (a) per issue #111's fixture set.
        _add_parsed_item(
            ledger_con, tmp_path, "cited_2024",
            "alpha beta gamma delta epsilon zeta eta theta iota kappa",
        )
        draft = tmp_path / "draft.md"
        draft.write_text("As shown [@cited_2024], alpha beta gamma delta epsilon zeta eta theta appears here.\n")

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "cited_2024" in out
        assert "UNCITED SOURCE" not in out

    def test_one_word_edit_variant_of_the_cited_run_still_merges_at_default_gap(
        self, ledger_con, tmp_path, capsys
    ):
        # (a)'s gap-merge variant: a single word changed mid-run must
        # still report as one run at the default --gap, per the issue's
        # scoping comment (a single edited word is the drafts' normal
        # failure mode, being LLM-written and lightly edited).
        source_text = (
            "one two three four five six seven eight nine ten eleven twelve "
            "thirteen fourteen fifteen sixteen seventeen eighteen"
        )
        _add_parsed_item(ledger_con, tmp_path, "cited_2024", source_text)
        edited = source_text.replace("nine", "ninexx")
        draft = tmp_path / "draft.md"
        draft.write_text(f"As shown [@cited_2024], {edited} end.\n")

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "18 words" in out
        assert "17 matched" in out

    def test_planted_run_from_uncited_source_is_flagged(self, ledger_con, tmp_path, capsys):
        # (b) per issue #111's fixture set: overlap mode structurally
        # cannot see this -- it never looks at a source the paragraph
        # doesn't cite.
        _add_parsed_item(
            ledger_con, tmp_path, "uncited_2024",
            "lorem ipsum dolor sit amet consectetur adipiscing elit sed do",
        )
        draft = tmp_path / "draft.md"
        draft.write_text(
            "As shown [@other_2024], lorem ipsum dolor sit amet consectetur adipiscing elit sed do appears here.\n"
        )
        _add_parsed_item(ledger_con, tmp_path, "other_2024", "completely unrelated filler text")

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "uncited_2024" in out
        assert "UNCITED SOURCE" in out

    def test_planted_run_in_connective_prose_citing_nothing_is_flagged(
        self, ledger_con, tmp_path, capsys
    ):
        # (c) per issue #111's fixture set: reuse in a paragraph that
        # cites no one at all -- overlap mode never even runs on it.
        _add_parsed_item(
            ledger_con, tmp_path, "connective_2024",
            "the quick brown fox jumps over the lazy dog while running",
        )
        draft = tmp_path / "draft.md"
        draft.write_text(
            "Some cited claim [@other_2024].\n\n"
            "The quick brown fox jumps over the lazy dog while running fast.\n\n"
            "Another cited claim [@other_2024].\n"
        )
        _add_parsed_item(ledger_con, tmp_path, "other_2024", "completely unrelated filler text")

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "connective_2024" in out
        assert "UNCITED SOURCE" in out

    def test_clean_paraphrase_does_not_flag(self, ledger_con, tmp_path, capsys):
        # (d) per issue #111's fixture set: must stay quiet at the
        # default n=8 floor.
        _add_parsed_item(
            ledger_con, tmp_path, "cited_2024",
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
        _add_parsed_item(
            ledger_con, tmp_path, "cited_2024",
            "alpha beta gamma delta epsilon zeta eta theta iota kappa",
        )
        draft = tmp_path / "draft.md"
        draft.write_text(
            'As [@cited_2024] puts it, "alpha beta gamma delta epsilon zeta eta theta" exactly.\n'
        )

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "quoted" in out

    def test_run_only_partly_inside_quotes_is_not_flagged_quoted(self, ledger_con, tmp_path, capsys):
        # Regression: "sits inside quote delimiters" means the whole run,
        # not "at least one word of it happens to be quoted" -- a run
        # straddling a quote's opening mark used to flag `quoted` on any
        # overlap at all.
        _add_parsed_item(
            ledger_con, tmp_path, "cited_2024",
            "alpha beta gamma delta epsilon zeta eta theta iota kappa",
        )
        draft = tmp_path / "draft.md"
        draft.write_text(
            'As [@cited_2024] puts it, alpha beta gamma "delta epsilon zeta eta theta" exactly.\n'
        )

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "quoted" not in out

    def test_cites_source_checks_every_paragraph_a_run_spans(self, ledger_con, tmp_path, capsys):
        # Regression: _tokenize_draft's word stream is flat, so an 8-gram
        # run can straddle a paragraph break. cites_source used to check
        # only the run's *starting* paragraph -- here that paragraph
        # cites nothing, but the run's tail falls in a paragraph that
        # does cite the matched source, so it must not be flagged
        # UNCITED SOURCE.
        _add_parsed_item(
            ledger_con, tmp_path, "cited_2024",
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
        _add_parsed_item(ledger_con, tmp_path, "cited_2024", "alpha beta gamma delta epsilon zeta eta theta")
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
        # A real, matching 8-word run exists, but --min-run 20 asks for
        # more than that -- exercises the length-floor continue, distinct
        # from "no candidate groups existed at all".
        _add_parsed_item(ledger_con, tmp_path, "cited_2024", "alpha beta gamma delta epsilon zeta eta theta")
        draft = tmp_path / "draft.md"
        draft.write_text("[@cited_2024] alpha beta gamma delta epsilon zeta eta theta end.\n")

        vc.cmd_scan(str(draft), min_run=20)
        out = capsys.readouterr().out
        assert "no verbatim run of >= 20 words found" in out

    def test_limit_truncates_findings(self, ledger_con, tmp_path, capsys):
        _add_parsed_item(ledger_con, tmp_path, "a_2024", "alpha beta gamma delta epsilon zeta eta theta")
        _add_parsed_item(ledger_con, tmp_path, "b_2024", "one two three four five six seven eight")
        draft = tmp_path / "draft.md"
        draft.write_text(
            "[@a_2024] alpha beta gamma delta epsilon zeta eta theta.\n\n"
            "[@b_2024] one two three four five six seven eight.\n"
        )

        vc.cmd_scan(str(draft), limit=1)
        out = capsys.readouterr().out
        assert out.count("tier=exact") == 1

    def test_page_boundary_split_run_both_halves_survive_independently(
        self, ledger_con, tmp_path, capsys
    ):
        # Documented limitation (cmd_scan's docstring): a run can never
        # merge across a page break, since token_position resets to 0
        # there. A 15/15 split still clears --min-run on both sides, so
        # both report -- as two findings, not one.
        words = [f"w{i}" for i in range(30)]
        page1, page2 = " ".join(words[:15]), " ".join(words[15:])
        _add_parsed_item(ledger_con, tmp_path, "split_2024", page1 + "\f" + page2)
        draft = tmp_path / "draft.md"
        draft.write_text(f"[@split_2024] {' '.join(words)} end.\n")

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "pdf p.1" in out and "pdf p.2" in out

    def test_page_boundary_short_remainder_is_invisible(self, ledger_con, tmp_path, capsys):
        # The sharper edge of the same limitation: a 25/5 split leaves a
        # 5-word remainder alone on its page, below --min-run, so it
        # never appears at all -- not merged, not reported separately.
        words = [f"w{i}" for i in range(30)]
        page1, page2 = " ".join(words[:25]), " ".join(words[25:])
        _add_parsed_item(ledger_con, tmp_path, "split_2024", page1 + "\f" + page2)
        draft = tmp_path / "draft.md"
        draft.write_text(f"[@split_2024] {' '.join(words)} end.\n")

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "25 words" in out
        assert "w25" not in out.split("in:")[0]  # the 5-word tail never becomes its own finding


class TestScanWrite:
    """`scan --write` files the report in content/review/, mirroring the
    draft's path, so it sits beside the same draft's provenance and
    coverage reports rather than only in a terminal that gets closed."""

    def _planted(self, ledger_con, tmp_path, name="dt/survey.md"):
        _add_parsed_item(
            ledger_con, tmp_path, "cited_2024",
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

    def test_write_lands_in_the_mirrored_review_dir(self, ledger_con, isolated_config, tmp_path, capsys):
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        report = config.REVIEW_DIR / "dt" / "survey.verbatim.md"
        assert report.is_file()
        text = report.read_text()
        assert "Review aid, not a gate" in text
        assert "cited_2024" in text
        # The caveat the docs carry has to travel with the file: the exact
        # tier is the only one built, so a clean run proves less than it
        # looks like it does.
        assert "not a clean bill of health" in text

    def test_a_clean_draft_still_writes_a_report(self, ledger_con, isolated_config, tmp_path, capsys):
        """Nothing found is a finding worth keeping -- and worth diffing
        against the next revision, which is the point of writing at all."""
        _add_parsed_item(ledger_con, tmp_path, "cited_2024", "wholly unrelated source text here")
        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("Entirely original prose that shares nothing.\n")

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        text = (config.REVIEW_DIR / "survey.verbatim.md").read_text()
        assert "No verbatim run" in text

    def test_limit_is_recorded_in_the_command_line(self, ledger_con, isolated_config, tmp_path, capsys):
        """The header has to reproduce the invocation exactly: a report
        capped at one finding reads very differently from an uncapped
        one, and the difference is invisible without the flag."""
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), limit=1, write=True, formats=["md"])

        text = (config.REVIEW_DIR / "dt" / "survey.verbatim.md").read_text()
        assert "--limit 1" in text

    def test_the_recorded_command_regenerates_the_file(self, ledger_con, isolated_config, tmp_path, capsys):
        """Same as the coverage report: the header is only useful as a
        re-run if it includes the flag that produced the file."""
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        text = (config.REVIEW_DIR / "dt" / "survey.verbatim.md").read_text()
        assert "--write" in text

    def test_two_runs_over_unchanged_input_are_byte_identical(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        """No wall-clock timestamp anywhere in a report: the point of
        writing one is that it diffs cleanly against the next revision's."""
        draft = self._planted(ledger_con, tmp_path)
        report = config.REVIEW_DIR / "dt" / "survey.verbatim.md"

        vc.cmd_scan(str(draft), write=True, formats=["md"])
        first = report.read_bytes()
        vc.cmd_scan(str(draft), write=True, formats=["md"])

        assert report.read_bytes() == first


class TestBoundedInt:
    """argparse `type=` callables that reject an out-of-range value as a
    usage error rather than letting it through to be silently absorbed."""

    def test_casts_a_valid_value(self):
        assert vc._bounded_int(1, "--n")("12") == 12

    def test_a_non_integer_is_a_usage_error(self):
        with pytest.raises(argparse.ArgumentTypeError) as exc:
            vc._bounded_int(1, "--n")("not-a-number")
        assert "not a valid value" in str(exc.value)

    def test_a_below_minimum_value_is_a_usage_error(self):
        with pytest.raises(argparse.ArgumentTypeError) as exc:
            vc._bounded_int(1, "--n")("0")
        assert "--n must be >= 1" in str(exc.value)


def _content_draft(tmp_path, text, name="draft.md"):
    """A draft where the review layer will accept one, for a subprocess
    run whose CONTENT_DIR is pointed at `tmp_path / "content"`."""
    path = tmp_path / "content" / "drafts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class TestMainInProcess:
    """`main(argv)` -- the in-process entry the other two aids' tests use
    throughout (see tests/test_citation_coverage.py).

    src/review/__main__.py does not go through it: it parses with this
    module's build_parser() and calls run() with the result, so argv is
    parsed once rather than sliced and re-parsed. main() is what a caller
    holding an argv list uses instead, and it is the only path that
    reaches build_parser() with no parser to hang the modes off.
    """

    def test_no_argv_prints_usage_and_exits_zero(self, capsys):
        assert vc.main([]) == 0
        assert "usage:" in capsys.readouterr().out

    def test_dispatches_a_mode(self, isolated_config, tmp_path, capsys):
        draft = _content_draft(tmp_path, "Nothing to see here at all.\n")

        assert vc.main(["scan", str(draft)]) == 0
        assert "no verbatim run of >= 8 words found" in capsys.readouterr().out

    def test_a_draft_outside_content_exits_one(self, isolated_config, tmp_path, capsys):
        outside = tmp_path / "not-in-content.md"
        outside.write_text("Anything.\n")

        assert vc.main(["scan", str(outside)]) == 1

    def test_an_unscannable_request_exits_two(self, isolated_config, tmp_path, capsys):
        """--min-run below the index's own n-gram size: "this input can't
        be scanned as asked" is a usage error, not a finding."""
        draft = _content_draft(tmp_path, "Anything.\n")

        assert vc.main(["scan", str(draft), "--min-run", "4"]) == 2


class TestCliDispatch:
    def test_overlap_mode_via_subprocess(self, tmp_path):
        repo_root = Path(__file__).resolve().parent.parent
        draft = _content_draft(tmp_path, "Some claim citing nonexistent_key_2024.\n")

        result = subprocess.run(
            [sys.executable, "-m", "src.review", "verbatim", "overlap", str(draft), "nonexistent_key_2024"],
            cwd=str(repo_root), capture_output=True, text=True,
            env={**os.environ, "CONTENT_DIR": str(tmp_path / "content")},
        )
        assert result.returncode == 0
        assert "no source text for nonexistent_key_2024" in result.stdout

    def test_scan_mode_via_subprocess(self, tmp_path):
        # CONTENT_DIR is overridden to a throwaway directory: cmd_scan
        # always calls build_corpus_index(), which -- unlike cmd_overlap's
        # ledger_item() short-circuit -- writes content/overlap/* even for
        # an empty corpus. Without the override this would create real
        # files under the checked-out repo's own content/ directory.
        repo_root = Path(__file__).resolve().parent.parent
        draft = _content_draft(tmp_path, "Nothing to see here at all.\n")

        result = subprocess.run(
            [sys.executable, "-m", "src.review", "verbatim", "scan", str(draft), "--min-run", "8", "--gap", "1"],
            cwd=str(repo_root), capture_output=True, text=True,
            env={**os.environ, "CONTENT_DIR": str(tmp_path / "content")},
        )
        assert result.returncode == 0
        assert "no verbatim run" in result.stdout

    def test_locate_needs_no_draft_and_so_skips_the_draft_check(self, tmp_path):
        """`locate` takes a citekey and phrases, not a draft -- so it
        returns before `require_reviewable`, which has nothing to check."""
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "src.review", "verbatim", "locate",
             "nonexistent_key_2024", "a phrase"],
            cwd=str(repo_root), capture_output=True, text=True,
            env={**os.environ, "CONTENT_DIR": str(tmp_path / "content")},
        )
        assert result.returncode == 0, result.stderr
        assert "nonexistent_key_2024" in result.stdout

    def test_a_draft_outside_the_content_dir_is_refused(self, tmp_path):
        """The review layer's input rule, which this command did not
        follow until 4.0.0. Exit 1, not 2: the invocation is well
        formed, the draft is somewhere this pipeline will not read."""
        repo_root = Path(__file__).resolve().parent.parent
        outside = tmp_path / "outside.md"
        outside.write_text("Anything.\n")

        result = subprocess.run(
            [sys.executable, "-m", "src.review", "verbatim", "scan", str(outside)],
            cwd=str(repo_root), capture_output=True, text=True,
            env={**os.environ, "CONTENT_DIR": str(tmp_path / "content")},
        )
        assert result.returncode == 1
        assert "outside the content directory" in result.stderr

    def test_unknown_mode_is_a_usage_error(self, tmp_path):
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "src.review", "verbatim", "bogus-mode"],
            cwd=str(repo_root), capture_output=True, text=True,
        )
        assert result.returncode == 2
        assert "invalid choice: 'bogus-mode'" in result.stderr

    def test_no_mode_prints_this_aids_usage_and_exits_zero(self, tmp_path):
        # Regression: sys.argv[1] on an empty invocation used to raise a
        # raw IndexError, contradicting this file's own "Run with no
        # arguments to print its usage" claim (docs/CLI.md).
        #
        # `verbatim` with no mode, not the bare module: since 5.0.0 this
        # file has no __main__ block, so running it as a script cannot
        # work by design -- test_the_aid_modules_are_not_invocable pins
        # that. The claim under test is unchanged, only its spelling.
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "src.review", "verbatim"],
            cwd=str(repo_root), capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "usage: python3 -m src.review verbatim" in result.stdout

    def test_overlap_mode_missing_arguments_exits_cleanly(self, tmp_path):
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "src.review", "verbatim", "overlap", "only-one-arg"],
            cwd=str(repo_root), capture_output=True, text=True,
        )
        assert result.returncode == 2
        assert "usage: python3 -m src.review verbatim overlap" in result.stderr

    def test_scan_mode_missing_draft_exits_cleanly(self, tmp_path):
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "src.review", "verbatim", "scan"],
            cwd=str(repo_root), capture_output=True, text=True,
        )
        assert result.returncode == 2
        assert "usage: python3 -m src.review verbatim scan" in result.stderr

    def test_overlap_mode_extra_positional_argument_exits_cleanly(self, tmp_path):
        # Regression: a third positional argument used to be silently
        # ignored (only rest[0]/rest[1] were ever read) rather than
        # reported as the typo it almost certainly is.
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "src.review", "verbatim", "overlap", "draft.md", "citekey", "extra"],
            cwd=str(repo_root), capture_output=True, text=True,
        )
        assert result.returncode == 2
        assert "unrecognized arguments: extra" in result.stderr

    def test_overlap_mode_n_below_one_exits_cleanly(self, tmp_path):
        # Regression: --n 0 didn't raise -- every zero-word "window"
        # hashed to the same constant, so a corpus-wide lookup would
        # treat every draft position as a match (overlap_index.gram_hashes
        # now raises for n < 1; this is the CLI's clean-usage-error path
        # in front of that).
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "src.review", "verbatim", "overlap", "draft.md", "citekey", "--n", "0"],
            cwd=str(repo_root), capture_output=True, text=True,
        )
        assert result.returncode == 2
        assert "--n must be >= 1" in result.stderr

    def test_scan_mode_extra_positional_argument_exits_cleanly(self, tmp_path):
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "src.review", "verbatim", "scan", "draft.md", "extra"],
            cwd=str(repo_root), capture_output=True, text=True,
        )
        assert result.returncode == 2
        assert "unrecognized arguments: extra" in result.stderr

    def test_scan_mode_negative_gap_exits_cleanly(self, tmp_path):
        # Regression: a sufficiently negative --gap silently broke even a
        # pure-verbatim run's merge (_merge_runs's arithmetic degrades
        # rather than raising) instead of being reported as nonsensical.
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "src.review", "verbatim", "scan", "draft.md", "--gap", "-1"],
            cwd=str(repo_root), capture_output=True, text=True,
        )
        assert result.returncode == 2
        assert "--gap must be >= 0" in result.stderr

    def test_scan_mode_limit_zero_exits_cleanly(self, tmp_path):
        # Regression: --limit 0 silently hid every finding behind the
        # same "no verbatim run found" message a genuinely clean draft
        # prints (findings[:0] == []), rather than being reported as the
        # usage error it is.
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "src.review", "verbatim", "scan", "draft.md", "--limit", "0"],
            cwd=str(repo_root), capture_output=True, text=True,
        )
        assert result.returncode == 2
        assert "--limit must be >= 1" in result.stderr

    def test_scan_mode_min_run_below_index_n_exits_cleanly(self, tmp_path):
        # Regression: --min-run below the corpus index's own n-gram size
        # used to print the same message to stdout and return normally
        # (exit 0) instead of being reported as the usage error it is --
        # cmd_scan now raises ValueError, and this checks the CLI
        # translates that into the same stderr-plus-exit-2 shape as its
        # other malformed invocations, e.g. --gap/--limit above.
        repo_root = Path(__file__).resolve().parent.parent
        draft = _content_draft(tmp_path, "Anything.\n")

        result = subprocess.run(
            [sys.executable, "-m", "src.review", "verbatim", "scan", str(draft), "--min-run", "4"],
            cwd=str(repo_root), capture_output=True, text=True,
            env={**os.environ, "CONTENT_DIR": str(tmp_path / "content")},
        )
        assert result.returncode == 2
        assert "--min-run must be >=" in result.stderr

    def test_locate_mode_missing_arguments_exits_cleanly(self, tmp_path):
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "src.review", "verbatim", "locate", "only-one-arg"],
            cwd=str(repo_root), capture_output=True, text=True,
        )
        assert result.returncode == 2
        assert "usage: python3 -m src.review verbatim locate" in result.stderr

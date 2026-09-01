"""chitragupta/review/verbatim_check.py: the review layer's verbatim-overlap,
whole-corpus scan and page-locator aid -- advisory over a finished
draft, never a gate. Reached as `python -m chitragupta.review verbatim <mode>`;
the module has no __main__ block of its own.

BIB/PARSED_DIR are module-level constants resolved from chitragupta.config at
import time; tests monkeypatch them directly to point at a throwaway
fixture tree. There was a REPO constant beside them until 5.0.0, when
the file moved into chitragupta/review/ and no longer needed a
Path(__file__)-derived repo root to put on sys.path."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from chitragupta.review import verbatim_check as vc
from chitragupta import config, ledger, overlap_embed, overlap_index
from tests.conftest import make_reference


@pytest.fixture
def fixture_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(vc._corpus, "BIB", tmp_path / "bibliography.bib")
    monkeypatch.setattr(vc._corpus, "PARSED_DIR", tmp_path / "content" / "parsed")
    return tmp_path


class TestBibEntry:
    def test_finds_entry_by_citekey(self, fixture_repo):
        vc._corpus.BIB.write_text(
            "@article{smith_2024,\n  title = {A Paper},\n}\n"
            "@article{doe_2023,\n  title = {Another},\n}\n"
        )
        entry = vc.bib_entry("smith_2024")
        assert "smith_2024" in entry
        assert "A Paper" in entry
        assert "doe_2023" not in entry

    def test_missing_citekey_returns_empty(self, fixture_repo):
        vc._corpus.BIB.write_text("@article{smith_2024,\n  title = {A Paper},\n}\n")
        assert vc.bib_entry("nonexistent_2024") == ""

    def test_missing_bib_file_returns_empty_rather_than_raising(self, fixture_repo):
        assert not vc._corpus.BIB.exists()
        assert vc.bib_entry("anything_2024") == ""


class TestPdfPath:
    def test_resolves_pdf_from_file_field(self, fixture_repo):
        pdf = fixture_repo / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        vc._corpus.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n"
            "  file = {paper.pdf:paper.pdf:application/pdf},\n}\n"
        )
        assert vc.pdf_path("smith_2024") == pdf

    def test_multiple_attachments_picks_the_pdf(self, fixture_repo):
        pdf = fixture_repo / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        vc._corpus.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n"
            "  file = {page.html:page.html:text/html;paper.pdf:paper.pdf:application/pdf},\n}\n"
        )
        assert vc.pdf_path("smith_2024") == pdf

    def test_no_file_field_returns_none(self, fixture_repo):
        vc._corpus.BIB.write_text("@article{smith_2024,\n  title = {T},\n}\n")
        assert vc.pdf_path("smith_2024") is None

    def test_file_field_with_no_pdf_attachment_returns_none(self, fixture_repo):
        html = fixture_repo / "page.html"
        html.write_text("<html></html>")
        vc._corpus.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n  file = {page.html:page.html:text/html},\n}\n"
        )
        assert vc.pdf_path("smith_2024") is None

    def test_pdf_referenced_but_missing_on_disk_returns_none(self, fixture_repo):
        vc._corpus.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n"
            "  file = {paper.pdf:paper.pdf:application/pdf},\n}\n"
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
        vc._corpus.BIB.write_text(
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
        vc._corpus.BIB.write_text(
            "@article{smith_2024,\n\tfile = {arXiv.org Snapshot:pdfs/158/2309.html:text/html;"
            "Submitted Version:pdfs/159/Lu et al. - 2023 - EvoCLINICAL.pdf:application/pdf},\n}\n"
        )
        assert vc.pdf_path("smith_2024") == pdf

    def test_unbalanced_braces_returns_what_it_has(self, fixture_repo):
        """A truncated/corrupt .bib shouldn't hang or raise -- hand back
        the remainder and let the caller find no `file` field."""
        vc._corpus.BIB.write_text("@article{smith_2024,\n\ttitle = {T},\n")
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
        vc._corpus.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n"
            "  file = {Smith - 2024 - Title.pdf:pdfs/21/Smith - 2024 - Title.pdf"
            ":application/pdf},\n}\n"
        )
        assert vc.pdf_path("smith_2024") == pdf

    def test_absolute_path_in_file_field(self, fixture_repo, tmp_path):
        pdf = tmp_path / "abs.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        vc._corpus.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n"
            f"  file = {{abs.pdf:{pdf}:application/pdf}},\n}}\n"
        )
        assert vc.pdf_path("smith_2024") == pdf

    def test_malformed_attachment_segment_is_skipped(self, fixture_repo):
        pdf = fixture_repo / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        vc._corpus.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n"
            "  file = {junk;paper.pdf:paper.pdf:application/pdf},\n}\n"
        )
        assert vc.pdf_path("smith_2024") == pdf

    def test_resolves_relative_to_bib_file_directory_not_repo_root(self, tmp_path, monkeypatch):
        # Regression: a relative attachment path must be anchored to
        # wherever BIB (== config.BIB_FILE_PATH, honoring a BIB_FILE
        # override) actually lives -- matching
        # chitragupta.bib_reader._resolve_pdf_path -- not the checked-out repo
        # root. A BIB_FILE pointing outside the repo used to silently fail
        # to find PDFs sitting right next to it.
        bib_dir = tmp_path / "elsewhere"
        bib_dir.mkdir()
        monkeypatch.setattr(vc._corpus, "BIB", bib_dir / "bibliography.bib")

        pdf = bib_dir / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        vc._corpus.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n"
            "  file = {paper.pdf:paper.pdf:application/pdf},\n}\n"
        )
        assert vc.pdf_path("smith_2024") == pdf


class TestPages:
    def test_falls_back_to_parsed_text_when_no_pdf(self, fixture_repo):
        vc._corpus.BIB.write_text("@article{smith_2024,\n  title = {T},\n}\n")
        parsed_dir = fixture_repo / "content" / "parsed"
        parsed_dir.mkdir(parents=True)
        (parsed_dir / "smith_2024.txt").write_text("page one text\x00\x01\fpage two text")

        result = vc.pages("smith_2024")
        assert result == ["page one text  page two text"] or len(result) == 2

    def test_no_pdf_and_no_parsed_text_returns_empty(self, fixture_repo):
        vc._corpus.BIB.write_text("@article{smith_2024,\n  title = {T},\n}\n")
        assert vc.pages("smith_2024") == []

    def test_parsed_fallback_respects_parsed_dir_override(self, tmp_path, monkeypatch):
        # Regression: the parsed-text fallback must look wherever
        # config.PARSED_DIR actually points (a CONTENT_DIR override) --
        # not at a repo-root-relative content/parsed that ignores it.
        # The REPO constant that made that mistake possible is gone as of
        # 5.0.0; this pins the behaviour that outlived it.
        monkeypatch.setattr(vc._corpus, "BIB", tmp_path / "bibliography.bib")
        custom_parsed_dir = tmp_path / "custom-content" / "parsed"
        monkeypatch.setattr(vc._corpus, "PARSED_DIR", custom_parsed_dir)
        custom_parsed_dir.mkdir(parents=True)
        (custom_parsed_dir / "smith_2024.txt").write_text("page one text")

        vc._corpus.BIB.write_text("@article{smith_2024,\n  title = {T},\n}\n")
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

        vc._corpus.BIB.write_text(
            "@article{smith_2024,\n  title = {T},\n"
            "  file = {paper.pdf:paper.pdf:application/pdf},\n}\n"
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
        """#497: bare substring matching made `smith_2024` match a
        paragraph citing only the suffixed sibling `smith_2024a` -- a
        BibTeX disambiguation suffix, routine in a real export -- and
        reported overlap runs against a source that paragraph never
        cites."""
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


def _add_parsed_item(ledger_con, tmp_path, citekey, text, pdf_bytes=b"%PDF-1.4 dummy"):
    """A ledger row with status='parsed', a real pdf_hash, and parsed_path
    pointing at real text on disk -- what `cmd_overlap` now reads through
    chitragupta/overlap_index.py instead of pdftotext/PARSED_DIR fallback."""
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
        _add_parsed_item(
            ledger_con, tmp_path, "smith_2024", f"Intro text. {shared_phrase}. More text."
        )

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
        _add_parsed_item(
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
        """Pinned literal output, captured from `cmd_overlap` *before* it
        was ported onto chitragupta/overlap_index.py (same fixture: a 4-gram
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
        vc._corpus.BIB.write_text("@article{smith_2024,\n  title = {T},\n}\n")
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
        # A clean anchor at 0 and the next clean anchor at n+1=9 (see
        # _merge_runs' docstring) is exactly what a single edited word
        # inside an n=8 gram produces.
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
    """The two tier-2 defects #180 measured against a real corpus, each
    reproduced against the mechanism the issue traced them to."""

    def test_a_repeating_source_block_reports_one_finding_not_several(self, ledger_con, tmp_path):
        # The duplicate-emission mechanism, minimally: the source repeats
        # one block on one page, so the draft's single matching window
        # sits at two different `src_pos` and therefore in two different
        # `(citekey, diagonal)` groups -- which merge to the same draft
        # span against the same page, and so build the same
        # `(citekey, page, fragment)` id twice.
        #
        # The draft's odd-index words are replaced so the *exact* tier
        # cannot match (and so cannot mask the bug by suppressing tier 2
        # under `scan_findings`' containment rule); the even family
        # survives intact and does the matching.
        block = (
            "alpha bexo gamov delka epsilo zenith etaro thelos iotara kappor lambdo muvex"
        ).split()
        _add_parsed_item(
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
        # Two tables about nothing in common. Their even-index tokens
        # coincide (1 2 3 0 5 2 8) and their odd-index ones do not, which
        # is precisely the shape tier 2 is built to forgive -- and with
        # only ten distinct digit tokens to draw from, forgiving it here
        # reports a coincidence as reuse. #180 traced 97 of 125 unique
        # findings to this.
        _add_parsed_item(ledger_con, tmp_path, "unrelated_2021", "1 4 2 7 3 9 0 6 5 8 2 3 8 1")
        draft = tmp_path / "draft.md"
        draft.write_text("1 0 2 1 3 5 0 2 5 4 2 9 8 7\n")

        findings, _min_run, _suppressed, _ = vc.scan_findings(draft, min_run=8)

        assert findings == []


class TestSkipgramTierQuoting:
    """The tier-2 half of #189. Three of the 27 hand-labelled findings in
    `bench/results/2026-08-14-skipgram-precision/labels.json` are
    `attributed-quotation` -- quoted and cited, legitimate scholarship --
    and all three read `quoted: false` before this was fixed, because a
    skip-gram window is wider than the quotation it evidences and starts
    outside it."""

    def test_a_window_straddling_the_opening_quote_mark_is_still_quoted(self, ledger_con, tmp_path):
        # Same odd-index-swap construction as the precision tests above,
        # so the exact tier cannot match and mask tier 2 -- with the
        # opening mark placed after the window's first two words, which
        # is the straddle `77a6a3a6ac03` and `b1f7848c8965` both have.
        block = (
            "alpha bexo gamov delka epsilo zenith etaro thelos iotara kappor lambdo muvex"
        ).split()
        _add_parsed_item(ledger_con, tmp_path, "cited_2024", " ".join(block))
        swapped = [w if i % 2 == 0 else f"z{i}" for i, w in enumerate(block)]
        draft = tmp_path / "draft.md"
        draft.write_text(
            "[@cited_2024] " + " ".join(swapped[:2]) + ' "' + " ".join(swapped[2:]) + '" end.\n'
        )

        findings, _min_run, _suppressed, _ = vc.scan_findings(draft, min_run=8)

        [found] = [f for f in findings if f["tier"] == "skip-gram"]
        # The straddle itself, not just the flag: a fragment that began at
        # the quote mark would pass the assertion below for free.
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


class TestMaskForScan:
    def test_blanks_fenced_code(self):
        text = "before\n```\n@dataclass\n```\nafter"
        masked = vc._mask_for_scan(text)
        assert "dataclass" not in masked
        assert "before" in masked
        assert "after" in masked

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
        # M-8: masking used to run References-to-EOF, so lifted prose in
        # a post-References appendix or acknowledgments section (introduced
        # by its own heading) was unscannable and read clean.
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


class TestParagraphs:
    """`re.split(r"\\n\\s*\\n", ...)` with the offsets it throws away --
    the first of the two places `_tokenize_draft` used to lose the
    position of a word in the file it came from."""

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
    """`str.lower()` is not length-preserving for every character, and
    `char_start` slices the original text -- so the lowercased stream a
    word was found in has to be mappable back to it."""

    def test_ascii_takes_the_identity_fast_path(self):
        lowered, offsets = vc._lower_offsets("Digital Twin")
        assert lowered == "digital twin"
        assert offsets is None

    def test_a_length_changing_character_gets_a_real_mapping(self):
        # "İ" (Latin capital I with dot above) lowercases to two code
        # points, so every offset after it is shifted by one.
        lowered, offsets = vc._lower_offsets("İstanbul")
        assert len(lowered) == 9
        assert offsets is not None
        # Both code points of the lowercased "İ" map back to it.
        assert offsets[0] == 0
        assert offsets[1] == 0
        assert offsets[2] == 1  # "s"

    def test_the_mapping_covers_every_character_of_the_result(self):
        lowered, offsets = vc._lower_offsets("AİB")
        assert len(offsets) == len(lowered)


class TestLineAt:
    """1-based line numbers off one precomputed sweep of the text, rather
    than a `count("\\n", 0, pos)` per finding -- `citation_gate` already
    computes its line numbers in one forward pass for the same reason."""

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
        """The property the loop used to compute directly, pinned against
        the cheap version so the two cannot drift."""
        text = "alpha\n\nbeta gamma\ndelta\n\n\nepsilon"
        offsets = vc._newline_offsets(text)
        for pos in range(len(text)):
            assert vc._line_at(offsets, pos) == text.count("\n", 0, pos) + 1


class TestDraftWordOffsets:
    """Every word carries where it sits in the *original* text, which is
    what lets a finding be handed to `Edit` as an exact span (#129)."""

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
        """The marker is blanked, not deleted -- deleting it shifted every
        character after it, which is the second place the position of a
        word in the file was lost."""
        assert self._spans("Twins [@smith_2024] matter.\n") == [
            ("twins", "Twins"),
            ("matter", "matter"),
        ]

    def test_a_marker_with_no_space_around_it_no_longer_welds_two_words(self):
        """`word[@key]word` used to become one token, because deleting the
        marker closed the gap between them."""
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
        """The corpus index fingerprints with `WORD.findall(text.lower())`
        (chitragupta/overlap_index.py), so the draft side must tokenize the same
        way -- matching case-insensitively instead would read
        "İstanbul" as one word where the corpus reads two."""
        text = "The İstanbul Result.\n"
        words, _ = vc._tokenize_draft(text)
        assert [w.text for w in words] == vc.norm(text)


class TestCmdScan:
    def test_planted_verbatim_run_from_cited_source_is_flagged(self, ledger_con, tmp_path, capsys):
        # (a) per issue #111's fixture set.
        _add_parsed_item(
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
        _add_parsed_item(ledger_con, tmp_path, "other_2024", "completely unrelated filler text")

        vc.cmd_scan(str(draft))
        out = capsys.readouterr().out
        assert "connective_2024" in out
        assert "UNCITED SOURCE" in out

    def test_clean_paraphrase_does_not_flag(self, ledger_con, tmp_path, capsys):
        # (d) per issue #111's fixture set: must stay quiet at the
        # default n=8 floor.
        _add_parsed_item(
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
        _add_parsed_item(
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
        # The tier-1 half of #189, and the shape `f0f4fd3982b7` in the
        # #130 gate labels has: the run starts three words *before* the
        # opening mark, picking up the draft's own framing prose, so the
        # earlier whole-span reading reported `quoted: false` on a
        # correctly quoted and correctly credited passage. See
        # `_run_is_quoted` for why `any` and not a proportion of the span.
        _add_parsed_item(
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
        # The other side of `_run_is_quoted`: loosening `all` to `any`
        # must not make every finding read as a quotation.
        _add_parsed_item(
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
        # Regression: _tokenize_draft's word stream is flat, so an 8-gram
        # run can straddle a paragraph break. cites_source used to check
        # only the run's *starting* paragraph -- here that paragraph
        # cites nothing, but the run's tail falls in a paragraph that
        # does cite the matched source, so it must not be flagged
        # UNCITED SOURCE.
        _add_parsed_item(
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
        _add_parsed_item(
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
        # A real, matching 8-word run exists, but --min-run 20 asks for
        # more than that -- exercises the length-floor continue, distinct
        # from "no candidate groups existed at all".
        _add_parsed_item(
            ledger_con, tmp_path, "cited_2024", "alpha beta gamma delta epsilon zeta eta theta"
        )
        draft = tmp_path / "draft.md"
        draft.write_text("[@cited_2024] alpha beta gamma delta epsilon zeta eta theta end.\n")

        vc.cmd_scan(str(draft), min_run=20)
        out = capsys.readouterr().out
        assert "no verbatim run of >= 20 words found" in out

    def test_limit_truncates_findings(self, ledger_con, tmp_path, capsys):
        _add_parsed_item(
            ledger_con, tmp_path, "a_2024", "alpha beta gamma delta epsilon zeta eta theta"
        )
        _add_parsed_item(ledger_con, tmp_path, "b_2024", "one two three four five six seven eight")
        draft = tmp_path / "draft.md"
        draft.write_text(
            "[@a_2024] alpha beta gamma delta epsilon zeta eta theta.\n\n"
            "[@b_2024] one two three four five six seven eight.\n"
        )

        vc.cmd_scan(str(draft), limit=1)
        out = capsys.readouterr().out
        assert out.count("tier=exact") == 1

    def test_run_spanning_a_page_break_merges_into_one_finding(self, ledger_con, tmp_path, capsys):
        # #131: global (not per-page) token position means a run merges
        # across a page break instead of splitting. A 15/15 split used to
        # report as two 15-word findings; it is now one 30-word finding
        # spanning both pages.
        words = [f"w{i}" for i in range(30)]
        page1, page2 = " ".join(words[:15]), " ".join(words[15:])
        _add_parsed_item(ledger_con, tmp_path, "split_2024", page1 + "\f" + page2)
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
        # The sharper edge of the same bug, now fixed: a 25/5 split used
        # to leave the 5-word remainder alone on its page, below
        # --min-run, invisible. It is now part of the single 30-word
        # merged run, so it appears too. Page attribution stays `p.1`
        # here (not a range): page2 has only 5 words, fewer than n=8, so
        # no gram *starts* there for any posting to be attributed to --
        # the remainder is recovered by content, even though every
        # posting's start position is still on page 1.
        words = [f"w{i}" for i in range(30)]
        page1, page2 = " ".join(words[:25]), " ".join(words[25:])
        _add_parsed_item(ledger_con, tmp_path, "split_2024", page1 + "\f" + page2)
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
        # Dropping `page` from scan_findings' grouping key merges a run
        # across a real page break (above), but must not merge two
        # unrelated matches just because one lands on each side of a
        # page: they land on different diagonals (the filler word between
        # them in the draft has no counterpart in the source), so they
        # stay two findings, each attributed to its own single page.
        page1 = "alpha beta gamma delta epsilon zeta eta theta"
        page2 = "iota kappa lambda mu nu xi omicron pi"
        _add_parsed_item(ledger_con, tmp_path, "mixed_2024", page1 + "\f" + page2)
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
    """`_mask_allowlisted` in isolation -- no corpus/ledger fixtures
    needed, it's a pure function over word lists."""

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
        # A whole paragraph allowlisted alongside a phrase that also
        # occurs inside it -- both should mark the same words, which a
        # naive sum (rather than boolean OR) would double count.
        words = ["alpha", "beta", "gamma"]
        mask = vc._mask_allowlisted(words, [("alpha", "beta", "gamma"), ("beta",)])
        assert mask == [True, True, True]


class TestMaskAllowlistedStemmed:
    """`_mask_allowlisted_stemmed` -- tier 2's allowlist masking, matched
    after the same stem-and-drop-stopwords reduction as skip-gram
    hashing, not the literal words `_mask_allowlisted` compares."""

    def test_masks_a_stemmed_contiguous_occurrence(self):
        # "Internets" stems to the same root as the allowlisted
        # "internet" -- a literal-word check would miss this.
        words = ["the", "internets", "of", "things", "is", "growing"]
        mask = vc._mask_allowlisted_stemmed(words, [("internet", "of", "things")])
        assert mask == [False, True, True, True, False, False]

    def test_a_phrase_that_stems_to_nothing_is_skipped(self):
        # Every word of the phrase is a stopword, so it reduces to an
        # empty stemmed sequence -- must not match (and must not error)
        # against any span.
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
        # path.exists() is True for a directory too, so a directory at
        # this exact path reaches open() and raises IsADirectoryError (an
        # OSError) -- which must not escape as an unhandled traceback
        # instead of the usual usage-error path.
        config.VERBATIM_ALLOWLIST_PATH.mkdir(parents=True, exist_ok=True)
        with pytest.raises(ValueError, match="cannot read allowlist"):
            vc._load_allowlist_phrases()

    def test_a_non_string_entry_raises(self, isolated_config):
        config.VERBATIM_ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.VERBATIM_ALLOWLIST_PATH.write_text("phrases = [1, 2]\n")
        with pytest.raises(ValueError, match="'phrases' must be a list of strings"):
            vc._load_allowlist_phrases()

    def test_an_unknown_key_raises_rather_than_loading_as_empty(self, isolated_config):
        # A typo like `pharses` would otherwise load silently as zero
        # phrases from a category that was never checked -- exactly the
        # "policy file quietly stopped suppressing" failure this module
        # exists to avoid.
        config.VERBATIM_ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.VERBATIM_ALLOWLIST_PATH.write_text('pharses = ["alpha"]\n')
        with pytest.raises(ValueError, match=r"unknown key\(s\) \['pharses'\]"):
            vc._load_allowlist_phrases()


class TestAllowlistSuppression:
    """End to end through `cmd_scan`: the allowlist is consulted inside
    `scan_findings`, so both stdout and a written report see the same
    post-suppression findings."""

    def _write_allowlist(self, *phrases):
        config.VERBATIM_ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        joined = ", ".join(f'"{p}"' for p in phrases)
        config.VERBATIM_ALLOWLIST_PATH.write_text(f"phrases = [{joined}]\n")

    def test_a_finding_entirely_covered_by_the_allowlist_is_suppressed(
        self, ledger_con, tmp_path, capsys
    ):
        _add_parsed_item(
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
        _add_parsed_item(ledger_con, tmp_path, "cited_2024", source_text)
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
        # Nine distinct content words, none a stopword: the even family
        # (5 members, DEFAULT_N) produces exactly one skip-gram window
        # covering the whole span, and allowlisting the identical phrase
        # covers that whole span too, so what's left after masking (0
        # words) cannot clear min_run.
        words = "alpha bexo gamov delka epsilo zenith etaro thelos iotara".split()
        text = " ".join(words)
        _add_parsed_item(ledger_con, tmp_path, "cited_2024", text)
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
        # span_words is deliberately way larger than matched_words here --
        # bucketing must key off matched_words (the real evidence), not the
        # raw span a skip-gram window can stretch across (#133 review fix).
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
        # A quoted run from an uncited source is still the finding
        # `overlap` structurally cannot make -- it must not be buried
        # under the low-priority `quoted` bucket just for sitting inside
        # quote marks.
        assert vc._bucket(self._finding(50, quoted=True, cites_source=False)) == "long"
        assert vc._bucket(self._finding(5, quoted=True, cites_source=False)) == "short"


class TestBucketTitle:
    def test_long(self):
        assert vc._bucket_title("long") == f"Long runs (>= {vc.LONG_RUN_WORDS} matched words)"

    def test_short(self):
        assert vc._bucket_title("short") == "Short runs"

    def test_quoted(self):
        assert vc._bucket_title("quoted") == "Quoted runs"


class TestScanWrite:
    """`scan --write` files the report in content/review/, mirroring the
    draft's path, so it sits beside the same draft's provenance and
    coverage reports rather than only in a terminal that gets closed."""

    def _planted(self, ledger_con, tmp_path, name="dt/survey.md"):
        _add_parsed_item(
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
        # The caveat the docs carry has to travel with the file: the exact
        # tier is the only one built, so a clean run proves less than it
        # looks like it does.
        assert "not a clean bill of health" in text

    def test_a_clean_draft_still_writes_a_report(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        """Nothing found is a finding worth keeping -- and worth diffing
        against the next revision, which is the point of writing at all."""
        _add_parsed_item(ledger_con, tmp_path, "cited_2024", "wholly unrelated source text here")
        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("Entirely original prose that shares nothing.\n")

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        text = (config.REVIEW_DIR / "survey.verbatim.md").read_text()
        assert "No verbatim run" in text

    def test_limit_is_recorded_in_the_command_line(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        """The header has to reproduce the invocation exactly: a report
        capped at one finding reads very differently from an uncapped
        one, and the difference is invisible without the flag."""
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), limit=1, write=True, formats=["md"])

        text = (config.REVIEW_DIR / "dt" / "survey.verbatim.md").read_text()
        assert "--limit 1" in text

    def test_the_recorded_command_regenerates_the_file(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
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

    def test_a_short_run_lands_under_the_short_heading(self, ledger_con, tmp_path):
        draft = self._planted(ledger_con, tmp_path)  # an 8-word run, below LONG_RUN_WORDS

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        text = (config.REVIEW_DIR / "dt" / "survey.verbatim.md").read_text()
        assert "### Short runs" in text
        assert "### Long verbatim runs" not in text
        assert "### Quoted runs" not in text

    def test_a_long_run_lands_under_the_long_heading(self, ledger_con, tmp_path):
        source_text = " ".join(f"tok{i}" for i in range(20))
        _add_parsed_item(ledger_con, tmp_path, "cited_2024", source_text)
        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(f"[@cited_2024] {source_text} end.\n")

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        text = (config.REVIEW_DIR / "survey.verbatim.md").read_text()
        assert f"### Long runs (>= {vc.LONG_RUN_WORDS} matched words)" in text
        assert "### Short verbatim runs" not in text

    def test_a_quoted_and_cited_run_lands_under_the_quoted_heading(self, ledger_con, tmp_path):
        _add_parsed_item(
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
    """The invocation recorded in both the report header and the payload
    envelope. It has to describe the run that produced the file: a reader
    holding one regenerates it from this line and nothing else."""

    def test_records_the_reporting_floor(self):
        assert vc.scan_command("d.md", 8, 1, None, False, False) == (
            "python -m chitragupta.review verbatim scan d.md --min-run 8 --gap 1"
        )

    def test_records_a_limit_only_when_one_was_given(self):
        """A report capped at one finding reads very differently from an
        uncapped one, and the difference is invisible without the flag."""
        assert "--limit" not in vc.scan_command("d.md", 8, 1, None, False, False)
        assert "--limit 3" in vc.scan_command("d.md", 8, 1, 3, False, False)

    def test_records_write_and_json(self):
        command = vc.scan_command("d.md", 8, 1, None, True, True)
        assert command.endswith("--write --json")

    def test_a_draft_path_with_a_space_stays_re_runnable(self):
        """shlex.join, not " ".join: an unquoted path with a space is a
        command that reproduces nothing."""
        assert "'my draft.md'" in vc.scan_command("my draft.md", 8, 1, None, False, False)


class TestScanPayload:
    """`--json`: the findings as data, so a consumer stops regex-parsing
    the printed form (#127)."""

    def _planted(self, ledger_con, tmp_path):
        _add_parsed_item(
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
        """A findings list means nothing without the thresholds it was
        filtered by -- `[]` at --min-run 40 is not `[]` at 8."""
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), min_run=9, gap=2, limit=5, as_json=True)

        payload = json.loads(capsys.readouterr().out)
        assert (payload["min_run"], payload["gap"], payload["limit"]) == (9, 2, 5)

    def test_the_default_min_run_is_reported_as_the_number_it_resolved_to(
        self, ledger_con, tmp_path, capsys
    ):
        """`--min-run` defaults to the corpus index's own n-gram size, so
        the payload has to carry that number, not `null`."""
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), as_json=True)

        assert json.loads(capsys.readouterr().out)["min_run"] == overlap_index.DEFAULT_N

    def test_a_finding_carries_exactly_the_published_fields(self, ledger_con, tmp_path, capsys):
        """Pinned deliberately: a field added to `scan_findings`' working
        dicts for some later internal purpose must not silently become
        part of a published contract -- only `_PAYLOAD_FIELDS` plus the
        one deliberately derived addition, `severity` (#128's bucket,
        added by name in `scan_payload`, not by widening the projection)."""
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
            "char_start",
            "char_end",
            "draft_text",
            "fragment",
            "context",
            "cites_source",
            "quoted",
            "score",
            "severity",
        ]

    def test_the_flags_are_booleans_not_the_printed_labels(self, ledger_con, tmp_path, capsys):
        """The whole point of the payload: a caller that has to match
        "UNCITED SOURCE" is back to parsing display text."""
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), as_json=True)

        out = capsys.readouterr().out
        assert "UNCITED SOURCE" not in out
        finding = json.loads(out)["findings"][0]
        assert finding["cites_source"] is False
        assert finding["quoted"] is False

    def test_a_quoted_run_from_a_cited_source_sets_both_bits(self, ledger_con, tmp_path, capsys):
        """The other corner of the same two bits, so neither is pinned
        only in its `False` state."""
        _add_parsed_item(
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
        """Never a second computation: the two forms cannot disagree
        about what was found. The expected flags are derived from the
        module's own `_flags`, not hardcoded, so this stays a statement
        about agreement rather than about spelling."""
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
        """Documented in `scan_payload` and docs/CLI.md, and pinned here
        because a consumer that reads it as a character offset or a line
        number edits the wrong part of the draft."""
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), as_json=True)

        finding = json.loads(capsys.readouterr().out)["findings"][0]
        words, _ = vc._tokenize_draft(draft.read_text())
        start, end = finding["start"], finding["start"] + finding["span_words"]
        assert " ".join(w.text for w in words[start:end]) == finding["fragment"]


class TestFindingLocators:
    """`start`/`fragment` locate a run for a *reader*. These four fields
    locate it for an *editor*: `draft_text` is the passage as written, and
    it is what a remediation loop hands `Edit` as `old_string` (#129)."""

    def _payload(self, draft, capsys, **kwargs):
        vc.cmd_scan(str(draft), as_json=True, **kwargs)
        return json.loads(capsys.readouterr().out)

    def _planted(self, ledger_con, tmp_path, prefix="Connective prose citing nobody: "):
        _add_parsed_item(
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
        """The marker is absent from `fragment` and present on disk, so an
        `Edit` built from `fragment` would not match. This is the case the
        locators exist for."""
        _add_parsed_item(
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
        _add_parsed_item(
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
        """The boundary the docstring and docs/CLI.md both state, pinned
        so neither can overstate it again: interior punctuation is inside
        the span, a trailing period or closing quote is not. That is the
        behaviour a reviser wants -- a rewrite substituted for
        `draft_text` must leave the sentence's own punctuation alone."""
        _add_parsed_item(
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
        """Position-free by construction: an edit above a finding must not
        rename it, or nothing could decide whether a finding survived a
        revision (R2, docs/AUTO-IMPROVEMENT.md)."""
        draft = self._planted(ledger_con, tmp_path)
        before = self._payload(draft, capsys)["findings"][0]

        draft.write_text("A new opening sentence.\n\n" + draft.read_text())
        after = self._payload(draft, capsys)["findings"][0]

        assert before["id"] == after["id"]
        assert before["start"] != after["start"]

    def test_the_id_changes_when_the_matched_wording_changes(self, ledger_con, tmp_path, capsys):
        """A long enough run survives a one-word edit as one finding (the
        default `--gap` recovers it), so this pins that the id tracks the
        wording rather than merely the run's existence."""
        source = (
            "one two three four five six seven eight nine ten eleven twelve "
            "thirteen fourteen fifteen sixteen seventeen eighteen"
        )
        _add_parsed_item(ledger_con, tmp_path, "uncited_2024", source)
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
        """The case that most easily falls through to the text branch:
        "nothing found" is data too, and a consumer branching on it must
        not have to recognise a sentence."""
        draft = tmp_path / "draft.md"
        draft.write_text("Nothing to see here at all.\n")

        vc.cmd_scan(str(draft), as_json=True)

        out = capsys.readouterr().out
        assert "no verbatim run" not in out
        assert json.loads(out)["findings"] == []

    def test_the_text_path_builds_no_payload(self, ledger_con, tmp_path, capsys, monkeypatch):
        """A plain `scan` prints text and stops: it never pays for the
        envelope's `pyproject.toml` read or a projection per finding,
        neither of which the printed form uses."""
        draft = self._planted(ledger_con, tmp_path)

        def unexpected(*a, **k):  # pragma: no cover - the point is it is never called
            raise AssertionError("the text path built a payload")

        monkeypatch.setattr(vc._scan_cmd, "scan_payload", unexpected)

        vc.cmd_scan(str(draft))

        assert "uncited_2024" in capsys.readouterr().out

    def test_an_unscannable_request_still_raises_rather_than_emitting_json(
        self, isolated_config, tmp_path
    ):
        """`--min-run` below the index's own n-gram size is "this input
        can't be scanned as asked", not an empty findings list -- adding
        `--json` must not turn a usage error into a clean payload."""
        draft = tmp_path / "draft.md"
        draft.write_text("Anything.\n")

        with pytest.raises(ValueError, match="--min-run must be >="):
            vc.cmd_scan(str(draft), min_run=4, as_json=True)


class TestScanJsonSibling:
    """`--write` files the payload beside the Markdown report, whether or
    not `--json` was asked for: it is written for whatever reads it
    later, not for whoever ran the command."""

    def _planted(self, ledger_con, tmp_path, name="dt/survey.md"):
        _add_parsed_item(
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
        """`scan --json --write > findings.json` has to be a valid JSON
        file: the written-files summary is a note to a person and goes to
        stderr once stdout has become a payload."""
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md"], as_json=True)

        captured = capsys.readouterr()
        json.loads(captured.out)  # raises if the summary leaked into it
        assert "survey.verbatim.json" in captured.err

    def test_what_it_prints_is_byte_for_byte_what_it_files(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        """So a caller may redirect stdout or read the sibling and get
        the same bytes, rather than two formattings of one payload."""
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md"], as_json=True)

        printed = capsys.readouterr().out
        assert printed == (config.REVIEW_DIR / "dt" / "survey.verbatim.json").read_text()

    def test_two_runs_over_unchanged_input_are_byte_identical(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        """No wall-clock in the payload either: it is kept beside the
        draft and diffed against the next revision's."""
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
        """One run, one recorded invocation -- the Markdown header and
        the envelope are two views of the same file set."""
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        review_dir = config.REVIEW_DIR / "dt"
        command = json.loads((review_dir / "survey.verbatim.json").read_text())["command"]
        assert f"- Command: `{command}`" in (review_dir / "survey.verbatim.md").read_text()

    def test_naming_json_in_formats_still_yields_the_payload(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        """`--formats md,json` reads as "give me the payload too", and it
        is already written -- what it must not do is put a pandoc render
        at that path instead."""
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md", "json"])

        sibling = config.REVIEW_DIR / "dt" / "survey.verbatim.json"
        assert json.loads(sibling.read_text())["aid"] == "verbatim"

    def test_a_clean_draft_still_files_a_payload(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        """Same reason the Markdown report is written for a clean draft:
        nothing found is a finding worth diffing against next time."""
        _add_parsed_item(ledger_con, tmp_path, "cited_2024", "wholly unrelated source text here")
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
        """The layer's rule reaches the payload too: a file found on disk
        months later is the case the docs cannot reach, and no less so
        when its likeliest reader is an agent acting on it."""
        draft = self._planted(ledger_con, tmp_path)

        vc.cmd_scan(str(draft), write=True, formats=["md"])

        payload = json.loads((config.REVIEW_DIR / "dt" / "survey.verbatim.json").read_text())
        assert "never a verdict" in payload["notice"]


class TestRecheck:
    """`recheck`: one scan compared against a recorded baseline, so
    "did this edit fix the finding, and did it break anything else"
    is a decidable question rather than two reports read side by side
    (#129). Still not a gate -- it exits 0 whatever it finds."""

    SOURCE = (
        "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu "
        "nu xi omicron pi rho sigma tau upsilon"
    )
    OTHER = (
        "one two three four five six seven eight nine ten eleven twelve "
        "thirteen fourteen fifteen sixteen"
    )

    def _planted(self, ledger_con, tmp_path):
        _add_parsed_item(ledger_con, tmp_path, "uncited_2024", self.SOURCE)
        _add_parsed_item(ledger_con, tmp_path, "other_2024", self.OTHER)
        draft = tmp_path / "draft.md"
        draft.write_text(f"First: {self.SOURCE}.\n\nSecond: {self.OTHER}.\n")
        return draft

    def _baseline(self, draft, tmp_path, **kwargs):
        findings, min_run, suppressed, _ = vc.scan_findings(str(draft), **kwargs)
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
        """The loop this serves reads `draft_text` out of the baseline and
        hands it straight to `Edit` -- so it has to still match the file
        the baseline was taken from."""
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)

        for finding in json.loads(baseline.read_text())["findings"]:
            assert finding["draft_text"] in draft.read_text()

    def test_a_rewrite_that_introduces_new_overlap_reports_it_as_new(
        self, ledger_con, tmp_path, capsys
    ):
        """The R4 case: the edit resolved its own finding but lifted from
        a third source, so the objective count did not actually fall."""
        third = (
            "red orange yellow green blue indigo violet white black grey "
            "silver golden copper bronze"
        )
        draft = self._planted(ledger_con, tmp_path)
        _add_parsed_item(ledger_con, tmp_path, "third_2024", third)
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
        """Documented in `finding_id`: an acceptance test should err
        towards "not yet fixed", never towards "fixed"."""
        _add_parsed_item(ledger_con, tmp_path, "uncited_2024", self.SOURCE)
        draft = tmp_path / "draft.md"
        draft.write_text(f"First: {self.SOURCE}.\n\nAgain: {self.SOURCE}.\n")
        baseline = self._baseline(draft, tmp_path)
        assert len({f["id"] for f in json.loads(baseline.read_text())["findings"]}) == 1

        draft.write_text(f"First: {self.SOURCE}.\n\nAgain: nothing borrowed here.\n")
        result = self._recheck(draft, baseline, capsys)

        assert result["resolved"] == []
        assert result["objective_delta"] == -1

    def test_the_floor_comes_from_the_baseline_not_from_a_flag(self, ledger_con, tmp_path, capsys):
        """Two scans are only comparable at the same floor, and the
        baseline is the one that already happened."""
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path, min_run=18, gap=2)

        result = self._recheck(draft, baseline, capsys)

        assert (result["min_run"], result["gap"]) == (18, 2)
        # Only the 20-word run clears a floor of 18; the 16-word one does not.
        assert [f["citekey"] for f in result["persisting"]] == ["uncited_2024"]

    def test_objective_counts_exclude_the_quoted_bucket(self, ledger_con, tmp_path, capsys):
        """R4 counts defects. A run that is both quoted and cited is the
        one bucket that is not one."""
        _add_parsed_item(ledger_con, tmp_path, "cited_2024", self.SOURCE)
        draft = tmp_path / "draft.md"
        draft.write_text(f'As [@cited_2024] has it, "{self.SOURCE}" exactly.\n')
        baseline = self._baseline(draft, tmp_path)

        result = self._recheck(draft, baseline, capsys)

        assert [f["severity"] for f in result["persisting"]] == ["quoted"]
        assert (result["objective_before"], result["objective_after"]) == (0, 0)

    def test_a_capped_baseline_is_refused(self, ledger_con, tmp_path):
        """`--limit` truncates, so a finding absent from a capped baseline
        may never have been reported rather than never have existed --
        "new" would then be a guess."""
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
        """A payload filed by 5.5.0 sits at exactly the path the loop is
        told to look at, and has no `id` on its findings. Refused with the
        remedy rather than crashing on the missing key."""
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
        """`min_run`/`gap` are what make the two scans comparable, and
        defaulting them would compare a strict run against a lax one."""
        draft = self._planted(ledger_con, tmp_path)
        baseline = tmp_path / "baseline.json"
        baseline.write_text(json.dumps({"aid": "verbatim", "limit": None, "findings": []}))

        with pytest.raises(ValueError) as exc:
            vc.cmd_recheck(str(draft), str(baseline))
        assert "predates" in str(exc.value)

    def test_an_empty_baseline_is_not_mistaken_for_an_old_one(self, ledger_con, tmp_path, capsys):
        """ "No findings" is a legitimate baseline -- a draft repaired to
        clean, then re-checked -- and has no findings to carry an `id`."""
        draft = self._planted(ledger_con, tmp_path)
        baseline = tmp_path / "baseline.json"
        baseline.write_text(
            json.dumps({"aid": "verbatim", "min_run": 8, "gap": 1, "limit": None, "findings": []})
        )

        result = self._recheck(draft, baseline, capsys)

        assert result["objective_before"] == 0
        assert len(result["new"]) == 2

    def test_a_baseline_missing_a_field_recheck_prints_is_refused(self, ledger_con, tmp_path):
        """`resolved` findings are printed straight out of the baseline,
        never rescanned, so every field the output line reads has to be
        there. `end_page` is the live case: a payload written between
        `id` landing and #131's page range would claim the same release
        series, pass the version check, and then crash the formatter."""
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
        """`recheck_findings` hands `min_run`/`gap` straight to
        `scan_findings` uncoerced -- a hand-edited `"min_run": "8"` would
        otherwise reach `_merge_runs`' `int <= str` comparison and raise
        `TypeError`, not the clean refusal every other malformed baseline
        gets. `bool` included: it's an `int` subclass, but a word count of
        `True`/`False` should name the problem, not silently become 1/0."""
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._baseline(draft, tmp_path)
        payload = json.loads(baseline.read_text())
        payload[key] = value
        baseline.write_text(json.dumps(payload, indent=2))

        with pytest.raises(ValueError) as exc:
            vc.cmd_recheck(str(draft), str(baseline))
        assert key in str(exc.value)

    def test_every_field_recheck_prints_is_one_scan_actually_writes(self):
        """The two lists are checked against each other rather than kept
        in step by hand: a field `recheck` requires but `scan` never
        writes would refuse every baseline ever taken."""
        assert set(vc._BASELINE_FIELDS) <= set(vc._PAYLOAD_FIELDS) | {"severity"}

    def test_a_findings_list_of_the_wrong_shape_is_refused_not_crashed_on(
        self, ledger_con, tmp_path
    ):
        """`findings` holding something that is not a finding is still a
        baseline this cannot compare against, and refusing is the same
        answer as for the other four -- not a TypeError from probing a
        non-dict for a key."""
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
        """The review layer's payloads share an envelope, so a coverage
        report is JSON with a `findings` key too."""
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
        """What counts as one finding changes between releases -- a scan
        that learns to merge two runs into one produces a different `id`
        for wording nobody touched -- and a comparison across that reads
        as a repair that never happened. DEVELOPER-AGENTS.md's versioning
        rules put any such change in a minor bump at least, so the
        release series is exactly the granularity to check."""
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._reversioned(draft, tmp_path, "5.4.0")

        with pytest.raises(ValueError) as exc:
            vc.cmd_recheck(str(draft), str(baseline))
        assert "5.4.0" in str(exc.value)
        assert "Re-scan" in str(exc.value)

    def test_a_patch_level_difference_is_accepted_silently(self, ledger_con, tmp_path, capsys):
        """A patch release is defined as changing nothing about what the
        pipeline does, so a baseline from one is still comparable -- and
        refusing it would force a re-scan for no reason."""
        draft = self._planted(ledger_con, tmp_path)
        current = ".".join(vc.review.version().split(".")[:2])
        baseline = self._reversioned(draft, tmp_path, f"{current}.99")

        result = self._recheck(draft, baseline, capsys)

        assert result["baseline_version"] == f"{current}.99"
        assert len(result["persisting"]) == 2

    def test_an_unknowable_version_is_not_treated_as_a_mismatch(self, ledger_con, tmp_path, capsys):
        """`review.version()` falls back to `"unknown"` when pyproject
        cannot be read. Refusing on that would turn one unreadable file
        into a second, unrelated failure."""
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._reversioned(draft, tmp_path, "unknown")

        result = self._recheck(draft, baseline, capsys)

        assert result["baseline_version"] == "unknown"

    def test_a_non_string_version_is_not_treated_as_a_mismatch(self, ledger_con, tmp_path, capsys):
        """A hand-edited or corrupted baseline can put anything under
        `version` -- `_series` must not crash trying to `.split(".")` a
        non-string, and a malformed `version` is not this check's refusal
        to make (the shape check already covers an untrustworthy
        baseline)."""
        draft = self._planted(ledger_con, tmp_path)
        baseline = self._reversioned(draft, tmp_path, 5)

        result = self._recheck(draft, baseline, capsys)

        assert result["baseline_version"] == 5

    def test_it_publishes_findings_in_the_same_shape_scan_does(self, ledger_con, tmp_path, capsys):
        """`recheck` compares its own freshly-scanned findings against a
        baseline `scan` wrote, so the two must agree about what a
        published finding looks like -- both go through `published`."""
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
    """argparse `type=` callables that reject an out-of-range value as a
    usage error rather than letting it through to be silently absorbed."""

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
    """A draft where the review layer will accept one, for a subprocess
    run whose CONTENT_DIR is pointed at `tmp_path / "content"`."""
    path = tmp_path / "content" / "drafts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class TestMainInProcess:
    """`main(argv)` -- the in-process entry the other two aids' tests use
    throughout (see tests/test_citation_coverage.py).

    chitragupta/review/__main__.py does not go through it: it parses with this
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

    def test_the_json_flag_reaches_the_scan(self, isolated_config, tmp_path, capsys):
        """The flag is wired through `run()`, not only through
        `cmd_scan`'s keyword -- and a findings-free scan still exits 0
        with `--json`, like every other successful invocation."""
        draft = _content_draft(tmp_path, "Nothing to see here at all.\n")

        assert vc.main(["scan", str(draft), "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["findings"] == []

    def test_a_draft_outside_content_exits_one(self, isolated_config, tmp_path, capsys):
        outside = tmp_path / "not-in-content.md"
        outside.write_text("Anything.\n")

        assert vc.main(["scan", str(outside)]) == 1

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
        """--min-run below the index's own n-gram size: "this input can't
        be scanned as asked" is a usage error, not a finding."""
        draft = _content_draft(tmp_path, "Anything.\n")

        assert vc.main(["scan", str(draft), "--min-run", "4"]) == 2


class TestCliDispatch:
    def test_overlap_mode_via_subprocess(self, tmp_path):
        repo_root = Path(__file__).resolve().parent.parent
        draft = _content_draft(tmp_path, "Some claim citing nonexistent_key_2024.\n")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "chitragupta.review",
                "verbatim",
                "overlap",
                str(draft),
                "nonexistent_key_2024",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
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
            [
                sys.executable,
                "-m",
                "chitragupta.review",
                "verbatim",
                "scan",
                str(draft),
                "--min-run",
                "8",
                "--gap",
                "1",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env={**os.environ, "CONTENT_DIR": str(tmp_path / "content")},
        )
        assert result.returncode == 0
        assert "no verbatim run" in result.stdout

    def test_scan_json_mode_via_subprocess_prints_only_the_payload(self, tmp_path):
        """The property a consumer actually depends on, and the one an
        in-process capsys assertion cannot make: nothing else this
        command or its imports print reaches stdout, so
        `scan --json > findings.json` is a valid JSON file."""
        repo_root = Path(__file__).resolve().parent.parent
        draft = _content_draft(tmp_path, "Nothing to see here at all.\n")

        result = subprocess.run(
            [sys.executable, "-m", "chitragupta.review", "verbatim", "scan", str(draft), "--json"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env={**os.environ, "CONTENT_DIR": str(tmp_path / "content")},
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["aid"] == "verbatim"

    def test_locate_needs_no_draft_and_so_skips_the_draft_check(self, tmp_path):
        """`locate` takes a citekey and phrases, not a draft -- so it
        returns before `require_reviewable`, which has nothing to check."""
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "chitragupta.review",
                "verbatim",
                "locate",
                "nonexistent_key_2024",
                "a phrase",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
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
            [sys.executable, "-m", "chitragupta.review", "verbatim", "scan", str(outside)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env={**os.environ, "CONTENT_DIR": str(tmp_path / "content")},
        )
        assert result.returncode == 1
        assert "outside the content directory" in result.stderr

    def test_unknown_mode_is_a_usage_error(self, tmp_path):
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "chitragupta.review", "verbatim", "bogus-mode"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
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
            [sys.executable, "-m", "chitragupta.review", "verbatim"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "usage: python -m chitragupta.review verbatim" in result.stdout

    def test_overlap_mode_missing_arguments_exits_cleanly(self, tmp_path):
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "chitragupta.review", "verbatim", "overlap", "only-one-arg"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "usage: python -m chitragupta.review verbatim overlap" in result.stderr

    def test_scan_mode_missing_draft_exits_cleanly(self, tmp_path):
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "chitragupta.review", "verbatim", "scan"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "usage: python -m chitragupta.review verbatim scan" in result.stderr

    def test_overlap_mode_extra_positional_argument_exits_cleanly(self, tmp_path):
        # Regression: a third positional argument used to be silently
        # ignored (only rest[0]/rest[1] were ever read) rather than
        # reported as the typo it almost certainly is.
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "chitragupta.review",
                "verbatim",
                "overlap",
                "draft.md",
                "citekey",
                "extra",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
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
            [
                sys.executable,
                "-m",
                "chitragupta.review",
                "verbatim",
                "overlap",
                "draft.md",
                "citekey",
                "--n",
                "0",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "--n must be >= 1" in result.stderr

    def test_scan_mode_extra_positional_argument_exits_cleanly(self, tmp_path):
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "chitragupta.review", "verbatim", "scan", "draft.md", "extra"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "unrecognized arguments: extra" in result.stderr

    def test_scan_mode_negative_gap_exits_cleanly(self, tmp_path):
        # Regression: a sufficiently negative --gap silently broke even a
        # pure-verbatim run's merge (_merge_runs's arithmetic degrades
        # rather than raising) instead of being reported as nonsensical.
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "chitragupta.review",
                "verbatim",
                "scan",
                "draft.md",
                "--gap",
                "-1",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
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
            [
                sys.executable,
                "-m",
                "chitragupta.review",
                "verbatim",
                "scan",
                "draft.md",
                "--limit",
                "0",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
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
            [
                sys.executable,
                "-m",
                "chitragupta.review",
                "verbatim",
                "scan",
                str(draft),
                "--min-run",
                "4",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env={**os.environ, "CONTENT_DIR": str(tmp_path / "content")},
        )
        assert result.returncode == 2
        assert "--min-run must be >=" in result.stderr

    def test_locate_mode_missing_arguments_exits_cleanly(self, tmp_path):
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "chitragupta.review", "verbatim", "locate", "only-one-arg"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "usage: python -m chitragupta.review verbatim locate" in result.stderr


# ---------------------------------------------------------------------
# Tier 3 (embedding), wired into `scan`. The tier's own logic is tested
# in tests/test_overlap_embed.py; what these hold is the *wiring* --
# that a tier which cannot run says so, that one which can produces a
# finding in the shared payload shape, and that it does not re-report
# what a deterministic tier already found.
# ---------------------------------------------------------------------


class FakeScopeEmbedder:
    """`encode` is the identity and `similarity` a lookup table, so a
    test can name the pair that should align without a model."""

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
    """Put tier 3 in a state where it runs, with a scored pair supplied
    by the caller. Returns a function taking `{(draft_fragment,
    source_fragment): cosine}`."""

    def install(scores, sections=None, missing=frozenset()):
        class FakeCollection:
            def query(self, query_embeddings, n_results, where):
                return {"metadatas": [[]], "distances": [[]]}

            def get(self, where, include=None):
                # Every cited citekey is "embedded" by default -- a test
                # that wants #499's stale-collection reason opts in with
                # `missing`, so every other test here stays a clean run.
                wanted = where["citekey"]["$in"]
                return {"metadatas": [{"citekey": k} for k in wanted if k not in missing]}

        scope = overlap_embed.Scope(
            sections if sections is not None else {"Section": ["source_2024"]},
            FakeCollection(),
            ledger_con,
            FakeScopeEmbedder(scores),
        )
        monkeypatch.setattr(overlap_embed, "open_scope", lambda draft: (scope, None))
        return scope

    return install


def _tier3_draft(text):
    """A draft under `content/drafts/`, which is where a dossier can
    mirror it -- tier 3 refuses anything else."""
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
        _add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
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
        # The same `draft[char_start:char_end] == draft_text` contract
        # #129 needs from every tier, so a remediation loop can hand this
        # one to `Edit` like any other.
        _add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
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

    def test_a_passage_a_deterministic_tier_already_found_is_not_reported_twice(
        self, ledger_con, tmp_path, tier3
    ):
        # Overlap, not containment: a tier-3 alignment is a whole
        # passage and normally *contains* the exact run rather than the
        # other way round, so containment would never fire.
        shared = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
        _add_parsed_item(ledger_con, tmp_path, "source_2024", shared)
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
        # #499 (M-14): the per-section cap used to run *before* the
        # dedupe against tier 1/2, not after. A section that quotes one
        # source verbatim (the strongest alignment -- later dropped as a
        # duplicate of the exact-tier finding) and paraphrases a second
        # source elsewhere lost the real paraphrase: the cap kept the
        # verbatim alignment as the section's one slot, and only
        # afterwards was it found to duplicate tier 1 and dropped,
        # leaving nothing behind.
        shared = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
        _add_parsed_item(ledger_con, tmp_path, "quoted_2024", shared)
        _add_sidecar("quoted_2024", [{"text": shared + ".", "label": "text", "page": 1}])
        _add_parsed_item(ledger_con, tmp_path, "paraphrased_2024", "unrelated corpus text")
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
        # The verbatim quote's alignment (0.95) outscores the paraphrase's
        # (0.85), so the un-fixed cap would keep the quote's alignment and
        # discard the paraphrase before the exact-tier dedupe ever runs.
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
        _add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
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
        # `--min-run` is a reporting floor for every tier, not only the
        # two that measure a run of words.
        _add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
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
        # The same rule tier 1 follows: a real lift that merely contains
        # a defined term is not excused by the term being allowlisted.
        _add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
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
        # #189's third tier. A tier-3 alignment is a whole sentence, so it
        # is the tier *most* likely to straddle a quotation rather than
        # sit inside one -- the bug had no label of its own here only
        # because tier 3 postdates the run that found it.
        _add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
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
        # The whole reason this tier is wired in on a host that cannot
        # run it: a report of a never-checked draft must not read like a
        # report of a clean one.
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
        # #499 (M-15): a draft with some headings renamed used to scan
        # only the matched section(s) with no signal that the rest were
        # skipped -- the `not_run` mechanism only ever fired at *zero*
        # matches. "checked against all three tiers" was then simply
        # false for the unmatched sections.
        _add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
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
        # Copilot review on #499: the denominator was `unmatched +
        # len(sections)`, but `sections` drops a title-matched heading
        # that contributed no prose (empty, or only code/fences) -- so a
        # dossier recording 3 sections with one renamed and one matched
        # but empty used to report "1 of 2" instead of "1 of 3".
        _add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
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
        # #499 (M-16): a cited source with no chunks in `content/chroma/`
        # used to rank last in `shortlist` and be silently cut by the
        # cap with no signal -- the corpus grew a paper since `enrich`
        # last ran, and nothing said the tier could not see it.
        _add_parsed_item(ledger_con, tmp_path, "source_2024", "unrelated corpus text")
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
        # #499: the tier ran and the findings below are real -- the report
        # must not say "the tier that can see one did not run here" when
        # it plainly did.
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
        # Copilot review on #499: `_not_run_lines` hardcoded "did not
        # run" for every entry, contradicting the paragraph directly
        # above a partial entry's bullet, which says the tier ran.
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

    def test_a_score_rides_inside_the_tier_note_only_when_there_is_one(self):
        assert vc._tier_note({"tier": "exact", "score": None}) == "tier=exact"
        assert vc._tier_note({"tier": "embedding", "score": 0.41}) == ("tier=embedding, score=0.41")

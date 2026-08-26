"""chitragupta/review/quotation.py: does each quoted span actually appear
in the source it is attributed to?

The seventh review aid, and the first whose answer is binary. A
quotation attributed to a paper that does not contain it is the same
failure class as a fabricated citekey -- a plausible artefact with
nothing real behind it -- and the one part of that class
`chitragupta/citation_gate.py` cannot see, because the citekey is real.

These tests hold the matcher to what `plans/c3-quotation-integrity.md`
measured on 189 real quoted spans, not to what issue #383 guessed. The
issue names hyphenation, ligatures, whitespace and quotation marks;
measured, those are the small effect. The two that dominate are an
inline reference marker in the source and an elided quotation, and both
have a test here for that reason.

Advisory like the other six -- exit 0 whatever it finds, no lock, and no
draft blocked by any of it.
"""

import json
from pathlib import Path

import pytest

from chitragupta import config, dossier, review
from chitragupta.review import __main__ as review_main
from chitragupta.review import _quotation_match as match
from chitragupta.review import quotation
from tests.test_review_units import draft_at

KEY = "shao_analysis_2023"
SPAN = "four interconnected layers of domains"


def a_dossier(draft: Path, blocks: str) -> Path:
    """Write `blocks` as this draft's evidence.md, verbatim."""
    where = dossier.dossier_dir(draft)
    where.mkdir(parents=True, exist_ok=True)
    (where / dossier.EVIDENCE_MD).write_text(blocks, encoding="utf-8")
    return where


def a_source(citekey: str, *records: tuple[int, str]) -> Path:
    """A rung-2 passage sidecar: reading-ordered text with a page each."""
    path = config.PARSED_DIR / f"{citekey}.passages.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([{"text": t, "page": p, "label": "text"} for p, t in records]),
        encoding="utf-8",
    )
    return path


def a_page_level_source(citekey: str, *pages: str) -> Path:
    """A rung-3 source: form-feed-delimited text, no reading order, so
    `passages.py` refuses to give it quotable text at all."""
    path = config.PARSED_DIR / f"{citekey}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\f".join(pages), encoding="utf-8")
    return path


def a_draft(citekeys: str = f"[@{KEY}]", name: str = "survey.md") -> Path:
    draft = draft_at(name)
    draft.write_text(f"Layered twins are the norm {citekeys}.\n", encoding="utf-8")
    return draft


def block(citekey: str, quote: str, claim: str = "The standard has layers.") -> str:
    return f"## `{citekey}`\n\nrelevance: bears on layering\nclaim: {claim}\nquote: {quote}\n"


def checked(draft: Path) -> list[quotation.Checked]:
    return quotation.build_report(draft).checked


def verdict_of(draft: Path) -> str:
    return checked(draft)[0].verdict


class TestRegistration:
    def test_the_aid_is_in_both_tables(self):
        """R10's machine-checked half -- review.AIDS owns the report
        suffix, __main__.AIDS owns the subcommand, and the entry point
        raises at import if they disagree."""
        assert "quotation" in review.AIDS
        assert "quotation" in review_main.AIDS

    def test_it_files_its_report_beside_the_others(self, isolated_config):
        draft = config.DRAFTS_DIR / "dt" / "survey.md"
        assert review.report_path(draft, "quotation") == (
            config.REVIEW_DIR / "dt" / "survey.quotation.md"
        )


class TestTheUniverse:
    def test_a_pre_a2_dossier_checks_nothing(self, isolated_config):
        """No `quote:` anywhere -- which is every dossier this project
        actually has. Empty universe, no findings, exit 0."""
        draft = a_draft()
        a_dossier(draft, "# Kept evidence\n\n## `%s`\n\nSome prose.\n" % KEY)
        assert checked(draft) == []
        assert quotation.main([str(draft)]) == 0

    def test_a_legacy_support_block_is_not_a_quote(self, isolated_config):
        """It holds a raw 600-character retrieval window nobody chose as
        a quotation. `evidence_appendix` reads it as nothing at all, and
        this aid inherits that rather than checking it as though someone
        had."""
        draft = a_draft()
        a_dossier(draft, f"## `{KEY}`\n\nrelevance: x\nsupport: {SPAN}\n")
        a_source(KEY, (4, f"It has {SPAN} in it."))
        assert checked(draft) == []

    def test_a_quote_the_draft_no_longer_cites_is_not_checked(self, isolated_config):
        draft = a_draft(citekeys="[@other_paper_2020]")
        a_dossier(draft, block(KEY, SPAN))
        a_source(KEY, (4, f"It has {SPAN} in it."))
        assert checked(draft) == []


class TestFoundAndAbsent:
    def test_an_exact_span_is_found_and_its_page_reported(self, isolated_config):
        draft = a_draft()
        a_dossier(draft, block(KEY, SPAN))
        a_source(KEY, (2, "Unrelated opening."), (7, f"ISO 23247 defines {SPAN}."))
        one = checked(draft)[0]
        assert (one.verdict, one.pages, one.tier) == ("found", [7], "exact")

    def test_an_absent_span_is_a_finding(self, isolated_config):
        draft = a_draft()
        a_dossier(draft, block(KEY, "a claim this paper never makes anywhere"))
        a_source(KEY, (3, "Wholly different subject matter entirely."))
        report = quotation.build_report(draft)
        assert report.checked[0].verdict == "absent"
        assert [f["citekey"] for f in quotation.findings(report)] == [KEY]

    def test_only_absent_spans_are_findings(self, isolated_config):
        draft = a_draft(citekeys=f"[@{KEY}] [@other_paper_2020]")
        a_dossier(draft, block(KEY, SPAN) + "\n" + block("other_paper_2020", "never written"))
        a_source(KEY, (7, f"ISO 23247 defines {SPAN}."))
        a_source("other_paper_2020", (1, "Something else."))
        assert [f["citekey"] for f in quotation.findings(quotation.build_report(draft))] == [
            "other_paper_2020"
        ]

    def test_an_absent_finding_carries_a_near_miss_page(self, isolated_config):
        """A bare "not found" cannot tell a fabricated quotation from a
        lightly-edited one, and alarm fatigue is the stated risk for this
        whole class of aid."""
        draft = a_draft()
        a_dossier(draft, block(KEY, "interconnected layers of governance domains here"))
        a_source(KEY, (2, "Nothing relevant."), (9, "The interconnected governance layers."))
        one = checked(draft)[0]
        assert one.verdict == "absent"
        assert one.near_miss_page == 9
        assert one.near_miss_score > 0
        assert "concentrate on p.9" in quotation.run_text(draft)


class TestNormalisation:
    def test_a_line_wrapped_and_hyphenated_span_is_still_found(self, isolated_config):
        """`environ-\\nment` must not split into two words. This is why
        the matcher is a character stream and not the word list
        `verbatim_check._corpus.norm` produces."""
        draft = a_draft()
        a_dossier(draft, block(KEY, "the operating environment of the twin"))
        a_source(KEY, (5, "We model the operating environ-\nment of the twin closely."))
        assert checked(draft)[0].verdict == "found"

    def test_a_ligature_and_a_curly_quote_are_found(self, isolated_config):
        draft = a_draft()
        a_dossier(draft, block(KEY, 'the "fidelity" of the field model'))
        a_source(KEY, (5, "We assess the “ﬁdelity” of the ﬁeld model."))
        assert checked(draft)[0].verdict == "found"

    def test_an_inline_reference_marker_does_not_break_a_span(self, isolated_config):
        """The single biggest cause of a false finding in the 189-span
        measurement, and one issue #383 does not mention: the source
        carries `[30]` mid-sentence and a correct quotation drops it."""
        draft = a_draft()
        a_dossier(draft, block(KEY, "in different circumstances and hypotheses."))
        a_source(KEY, (2, "Used in different circumstances and hypotheses [30]. Should it fail,"))
        assert checked(draft)[0].verdict == "found"

    def test_a_bare_bracketed_word_in_the_source_is_not_stripped(self, isolated_config):
        """Only numeric bracket groups are reference markers. Stripping
        `[sic]` or `(Smith 2020)` would need parsing and could eat
        content the quote legitimately contains."""
        assert match.strip_markers("layers [30], [1, 2] and [1-3] here") == (
            "layers  ,   and   here"
        )
        assert match.strip_markers("layers [sic] here") == "layers [sic] here"


class TestElision:
    def test_an_elided_quote_whose_fragments_are_in_order_is_found(self, isolated_config):
        draft = a_draft()
        a_dossier(draft, block(KEY, "PE refers to the physical entity ... CN is the connection"))
        a_source(
            KEY,
            (
                3,
                "Here PE refers to the physical entity, VE the virtual one, "
                "and CN is the connection that ties them.",
            ),
        )
        one = checked(draft)[0]
        assert (one.verdict, one.tier) == ("found", "elided")

    def test_fragments_out_of_order_are_absent(self, isolated_config):
        """What keeps the elision tier exact rather than fuzzy. Without
        it a later reader could loosen this into a word-overlap score,
        which R3 bars from being the thing optimised."""
        draft = a_draft()
        a_dossier(draft, block(KEY, "CN is the connection ... PE refers to the physical entity"))
        a_source(
            KEY,
            (
                3,
                "Here PE refers to the physical entity, VE the virtual one, "
                "and CN is the connection that ties them.",
            ),
        )
        assert checked(draft)[0].verdict == "absent"

    def test_an_editorial_insertion_is_treated_as_an_elision(self, isolated_config):
        draft = a_draft()
        a_dossier(draft, block(KEY, "operators [who] can start developing twins in-house"))
        a_source(KEY, (8, "Small operators with low budget can start developing twins in-house."))
        assert checked(draft)[0].verdict == "found"


class TestPassageSeams:
    def test_a_span_straddling_a_seam_is_not_reported_found_on_one_page(self, isolated_config):
        """The false-`found` guard. Flattening strips every separator, so
        concatenating the document would fuse `...end of para` and
        `Beginning of...` into one stream and report a contiguous hit on
        a page the span is not on. A false `found` is worse here than a
        false `absent`: it is the outcome nobody re-reads."""
        draft = a_draft()
        a_dossier(draft, block(KEY, "the layers are fixedThe user domain sits above"))
        a_source(KEY, (4, "In ISO 23247 the layers are fixed"), (5, "The user domain sits above."))
        one = checked(draft)[0]
        assert one.tier != "exact"
        assert one.pages != [4]

    def test_a_genuine_span_across_adjacent_passages_is_found_with_both_pages(
        self, isolated_config
    ):
        draft = a_draft()
        a_dossier(draft, block(KEY, "the layers are fixed. The user domain sits above"))
        a_source(KEY, (4, "In ISO 23247 the layers are fixed."), (5, "The user domain sits above."))
        one = checked(draft)[0]
        assert (one.verdict, one.tier, one.pages) == ("found", "exact-pair", [4, 5])


class TestUnverifiable:
    def test_a_page_level_source_is_unverifiable_never_absent(self, isolated_config):
        """`pdftotext -layout` preserves a page's visual arrangement, not
        its reading order, so on a two-column paper a perfectly correct
        quotation simply is not contiguous. Reporting it `absent` would
        assert a fabrication that is not there."""
        draft = a_draft()
        a_dossier(draft, block(KEY, "a span this page-level text cannot confirm"))
        a_page_level_source(KEY, "column spliced text one", "column spliced text two")
        report = quotation.build_report(draft)
        assert report.checked[0].verdict == "unverifiable"
        assert quotation.findings(report) == []

    def test_a_source_with_no_text_at_all_is_unverifiable(self, isolated_config):
        draft = a_draft()
        a_dossier(draft, block(KEY, SPAN))
        report = quotation.build_report(draft)
        assert report.checked[0].verdict == "unverifiable"
        assert report.checked[0].reason
        assert quotation.findings(report) == []


class TestIdentity:
    def test_a_finding_id_is_stable_across_runs(self, isolated_config):
        assert quotation.finding_id(KEY, SPAN) == quotation.finding_id(KEY, SPAN)

    def test_editing_the_quote_or_reattributing_it_renames_the_finding(self, isolated_config):
        """Both halves are wanted. A repaired quote is a different
        assertion about the source and has not been checked, so it must
        not inherit its predecessor's identity."""
        assert quotation.finding_id(KEY, SPAN) != quotation.finding_id(KEY, SPAN + " here")
        assert quotation.finding_id(KEY, SPAN) != quotation.finding_id("other_2020", SPAN)


class TestOutput:
    def test_two_runs_over_an_unchanged_draft_are_byte_identical(self, isolated_config):
        """No wall-clock line anywhere -- the reason to write a report is
        that it diffs against the next revision's."""
        draft = a_draft()
        a_dossier(draft, block(KEY, SPAN))
        a_source(KEY, (7, f"ISO 23247 defines {SPAN}."))
        first = quotation.run_text(draft)
        assert first == quotation.run_text(draft)
        assert "202" not in first.split("chitragupta")[-1][:40]

    def test_json_carries_the_counts_the_tiers_and_no_timestamp(self, isolated_config):
        draft = a_draft(citekeys=f"[@{KEY}] [@other_paper_2020]")
        a_dossier(draft, block(KEY, SPAN) + "\n" + block("other_paper_2020", "never written"))
        a_source(KEY, (7, f"ISO 23247 defines {SPAN}."))
        a_source("other_paper_2020", (1, "Something else."))
        payload = quotation.quotation_payload(quotation.build_report(draft), "cmd")
        assert (payload["quotes_total"], payload["found"], payload["absent"]) == (2, 1, 1)
        assert payload["unverifiable"] == 0
        assert [c["tier"] for c in payload["quotes"] if c["verdict"] == "found"] == ["exact"]
        assert "timestamp" not in json.dumps(payload)

    def test_write_files_the_report_and_its_json_sibling(self, isolated_config):
        draft = a_draft()
        a_dossier(draft, block(KEY, SPAN))
        a_source(KEY, (7, f"ISO 23247 defines {SPAN}."))
        assert quotation.main([str(draft), "--write", "--formats", "md"]) == 0
        assert review.report_path(draft, "quotation").is_file()
        assert review.report_path(draft, "quotation", "json").is_file()


class TestRefusals:
    def test_a_missing_draft_exits_1(self, isolated_config):
        assert quotation.main([str(config.DRAFTS_DIR / "nope.md")]) == 1

    def test_a_draft_outside_content_exits_1(self, isolated_config, tmp_path):
        outside = tmp_path / "elsewhere.md"
        outside.write_text("x\n", encoding="utf-8")
        assert quotation.main([str(outside)]) == 1

    def test_it_exits_0_even_when_every_quote_is_absent(self, isolated_config):
        """Advisory, not a gate. A non-zero exit is how a gate speaks."""
        draft = a_draft()
        a_dossier(draft, block(KEY, "a claim this paper never makes"))
        a_source(KEY, (3, "Wholly different subject matter."))
        assert quotation.main([str(draft)]) == 0


class TestDegenerateInput:
    """The shapes a hand-written dossier can produce that a machine-written
    one never would. `evidence.md` is a supported hand-edited input
    everywhere else here, so none of these may raise."""

    def test_a_quote_that_flattens_to_nothing_is_absent_not_a_crash(self, isolated_config):
        draft = a_draft()
        a_dossier(draft, block(KEY, "### ---"))
        a_source(KEY, (3, "Real prose about layered architectures."))
        one = checked(draft)[0]
        assert (one.verdict, one.near_miss_page) == ("absent", None)

    def test_a_quote_of_only_stopwords_reports_no_near_miss_page(self, isolated_config):
        """`passages.distinctive` drops short words and stopwords, so
        there is nothing to score against -- and 0% on p.1 would be a
        worse answer than saying so."""
        draft = a_draft()
        a_dossier(draft, block(KEY, "of the and to be as by it"))
        a_source(KEY, (3, "Real prose about layered architectures."))
        one = checked(draft)[0]
        assert one.near_miss_page is None
        assert "appear on no page" in quotation.run_text(draft)

    def test_a_passage_with_no_page_number_still_matches(self, isolated_config):
        """A hand-edited sidecar can omit `page`, and `passages.py`
        already turns anything that is not a page a reader could turn to
        into None. A span is still found; it simply reports no page."""
        draft = a_draft()
        path = config.PARSED_DIR / f"{KEY}.passages.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([{"text": f"ISO 23247 defines {SPAN}.", "page": None}]), encoding="utf-8"
        )
        a_dossier(draft, block(KEY, SPAN))
        one = checked(draft)[0]
        assert (one.verdict, one.pages) == ("found", [])
        assert "page unknown" in quotation.run_text(draft)

    def test_a_pair_on_one_page_reports_that_page_once(self, isolated_config):
        """Two consecutive passages can share a page. `[4, 4]` would read
        as a span crossing a page boundary when it does not."""
        draft = a_draft()
        a_dossier(draft, block(KEY, "the layers are fixed. The user domain sits above"))
        a_source(KEY, (4, "In ISO 23247 the layers are fixed."), (4, "The user domain sits above."))
        one = checked(draft)[0]
        assert (one.tier, one.pages) == ("exact-pair", [4])


class TestCommandSurface:
    def test_the_recorded_command_carries_the_flags_it_was_given(self, isolated_config):
        """An empty finding list means something different depending on
        how the aid was invoked, so the header records the invocation."""
        draft = a_draft()
        assert quotation._command(draft, as_json=True, write=True).endswith("--json --write")
        assert "--json" not in quotation._command(draft, as_json=False, write=False)

    def test_the_entry_point_hangs_this_aids_flags_off_its_own_subparser(self):
        """How chitragupta/review/__main__.py reaches it: the subparser
        already exists, and the flags are declared once, here."""
        import argparse

        sub = argparse.ArgumentParser().add_subparsers().add_parser("quotation")
        assert quotation.build_parser(sub) is sub
        assert sub.parse_args(["d.md", "--json"]).json is True

    def test_json_without_write_prints_the_payload_and_writes_nothing(self, isolated_config):
        draft = a_draft()
        a_dossier(draft, block(KEY, SPAN))
        a_source(KEY, (7, f"ISO 23247 defines {SPAN}."))
        assert quotation.main([str(draft), "--json"]) == 0
        assert not review.report_path(draft, "quotation").exists()


class TestTierPrecedence:
    def test_a_contiguous_pair_match_beats_an_elided_single_one(self, isolated_config):
        """Exact is a stronger claim than elided, so every exact tier is
        tried before any elided one -- not exact-then-elided within each
        window size. A span that is genuinely contiguous across two
        passages must not be reported as an alignment around an ellipsis
        merely because one passage also happens to contain its fragments
        in order.
        """
        draft = a_draft()
        a_dossier(draft, block(KEY, "alpha beta ... gamma delta"))
        a_source(KEY, (4, "alpha beta xx gamma delta yy alpha beta"), (5, "gamma delta zz"))
        one = checked(draft)[0]
        assert (one.verdict, one.tier, one.pages) == ("found", "exact-pair", [4, 5])

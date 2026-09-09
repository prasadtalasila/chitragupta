"""chitragupta/review/claim_support.py: does the cited source actually
entail the claim citing it, per a real NLI model (stubbed here --
the module's own logic is what is under test, not the model)."""

import argparse
import json

import pytest

from chitragupta import config, entailment, ledger, review
from chitragupta.review import _claim_support_render as render
from chitragupta.review import claim_support
from chitragupta.review import __main__ as review_main


def _add_item(citekey, parsed_text=None, title="T"):
    parsed_path = None
    if parsed_text is not None:
        config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
        parsed_path = config.PARSED_DIR / f"{citekey}.txt"
        parsed_path.write_text(parsed_text, encoding="utf-8")
        parsed_path = str(parsed_path)
    con = ledger.connect()
    try:
        con.execute(
            "INSERT OR REPLACE INTO items"
            " (citekey, title, status, parsed_path, pdf_path, last_synced)"
            " VALUES (?, ?, 'parsed', ?, NULL, '2026-01-01')",
            (citekey, title, parsed_path),
        )
        con.commit()
    finally:
        con.close()


def _sidecar(citekey, records):
    config.DOCLING_DIR.mkdir(parents=True, exist_ok=True)
    (config.DOCLING_DIR / f"{citekey}.passages.json").write_text(json.dumps(records))


class FakeEntailer:
    """Scores by exact-pair table lookup -- no model anywhere."""

    def __init__(self, scores):
        self.scores = scores
        self.calls = []

    def score(self, pairs):
        self.calls.append(list(pairs))
        return [self.scores.get(pair, 0.0) for pair in pairs]


def _draft(config_dir, text):
    draft = config_dir.DRAFTS_DIR / "topic" / "draft.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text(text, encoding="utf-8")
    return draft


class TestSectionHeadingsAreNotPremises:
    """Issue #719. `_score_claim` returns `max()` over everything it is
    given, so a heading that scores well is *reported* as the claim's
    best supporting passage -- a wrong answer, not a weak one."""

    def test_a_heading_never_reaches_the_entailer(self, isolated_config):
        """Asserted on the entailer's own call log rather than on the
        winner: a test that only checked which passage won would still
        pass if the heading were scored and merely lost, which is not
        what this change claims."""
        _add_item("heading_2024")
        _sidecar(
            "heading_2024",
            [
                {"text": "3. Closing the loop", "page": 1, "label": "section_header"},
                {"text": "Twins close the control loop.", "page": 1, "label": "text"},
            ],
        )
        draft = _draft(config, "Digital twins close the loop [@heading_2024].\n")
        fake = FakeEntailer(
            {("Twins close the control loop.", "Digital twins close the loop."): 0.91}
        )
        report = claim_support.build_report(draft, fake)

        premises = [premise for call in fake.calls for premise, _claim in call]
        assert "3. Closing the loop" not in premises, premises
        assert report.findings[0].passage.text == "Twins close the control loop."

    def test_a_heading_that_would_have_won_does_not(self, isolated_config):
        """The heading is deliberately the higher-scoring pair, so a
        filter that is not actually applied fails this by reporting the
        heading as the claim's support."""
        _add_item("winner_2024")
        _sidecar(
            "winner_2024",
            [
                {"text": "Digital twins close the loop", "page": 1, "label": "section_header"},
                {"text": "The plant was instrumented in 2019.", "page": 2, "label": "text"},
            ],
        )
        draft = _draft(config, "Digital twins close the loop [@winner_2024].\n")
        fake = FakeEntailer(
            {
                ("Digital twins close the loop", "Digital twins close the loop."): 0.99,
                ("The plant was instrumented in 2019.", "Digital twins close the loop."): 0.05,
            }
        )
        report = claim_support.build_report(draft, fake)

        assert report.findings[0].passage.text == "The plant was instrumented in 2019."
        assert report.findings[0].score == pytest.approx(0.05)

    def test_an_unlabelled_passage_is_still_a_premise(self, isolated_config):
        """`passages._from_sidecar` leaves `label` None for any record
        without one -- every sidecar written before labelling. Dropping
        those would empty the premise set for those sources and move
        their citations from `scored` to `unscoreable`."""
        _add_item("unlabelled_2024")
        _sidecar("unlabelled_2024", [{"text": "Twins close the control loop.", "page": 1}])
        draft = _draft(config, "Digital twins close the loop [@unlabelled_2024].\n")
        fake = FakeEntailer(
            {("Twins close the control loop.", "Digital twins close the loop."): 0.91}
        )
        report = claim_support.build_report(draft, fake)

        assert report.unscoreable == {}
        assert report.findings[0].score == pytest.approx(0.91)

    def test_list_items_tables_and_formulae_stay(self, isolated_config):
        """Only `section_header` is filtered. A bulleted line carries a
        real assertion, and a table cell can support a numeric claim --
        dropping either would lose genuine support with no measurement
        saying it does not."""
        _add_item("kept_2024")
        _sidecar(
            "kept_2024",
            [
                {"text": "The loop closes in 40 ms.", "page": 1, "label": "list_item"},
                {"text": "latency | 40 ms", "page": 1, "label": "table"},
                {"text": "t = 40", "page": 1, "label": "formula"},
            ],
        )
        draft = _draft(config, "The loop closes in 40 ms [@kept_2024].\n")
        fake = FakeEntailer({("The loop closes in 40 ms.", "The loop closes in 40 ms"): 0.88})
        report = claim_support.build_report(draft, fake)

        premises = {premise for call in fake.calls for premise, _claim in call}
        assert premises == {"The loop closes in 40 ms.", "latency | 40 ms", "t = 40"}
        assert report.unscoreable == {}

    def test_a_source_that_is_all_headings_says_so(self, isolated_config):
        """The pre-existing "page-level only" reason would be false here:
        the source has readable text, it just has no premise in it."""
        _add_item("allheadings_2024")
        _sidecar(
            "allheadings_2024",
            [{"text": "1. Introduction", "page": 1, "label": "section_header"}],
        )
        draft = _draft(config, "Digital twins close the loop [@allheadings_2024].\n")
        fake = FakeEntailer({})
        report = claim_support.build_report(draft, fake)

        assert fake.calls == [], "a source with no premise still called the model"
        assert "section headings" in report.unscoreable["allheadings_2024"]
        assert "page-level only" not in report.unscoreable["allheadings_2024"]


class TestPremiseCap:
    """Issue #693. `_score_claim` scores one entailment pair per quotable
    passage of the cited source, measured at 725-887 pairs per citation
    (docs/PERFORMANCE.md), so the cap is what makes the pass affordable.
    Uncapped stays the default -- see the module comment for the gate."""

    def test_uncapped_by_default_every_premise_reaches_the_entailer(self, isolated_config):
        """The default is the pre-#693 behaviour exactly. Asserted so a
        cap that leaked into the default fails here rather than silently
        changing every recorded score."""
        _add_item("uncapped_2024")
        _sidecar(
            "uncapped_2024",
            [{"text": f"Passage {i} on loops.", "page": 1} for i in range(6)],
        )
        draft = _draft(config, "Digital twins close the loop [@uncapped_2024].\n")
        fake = FakeEntailer({})
        claim_support.build_report(draft, fake)

        assert len(fake.calls[0]) == 6

    def test_a_cap_sends_only_the_best_lexical_overlap(self, isolated_config):
        """The kept premise is the one sharing the claim's distinctive
        words, not the first on the page -- the ranking is what makes a
        cap survivable, so document order winning would be the bug."""
        _add_item("ranked_2024")
        _sidecar(
            "ranked_2024",
            [
                {"text": "The plant was instrumented in 2019.", "page": 1},
                {"text": "Digital twins close the control loop.", "page": 2},
            ],
        )
        draft = _draft(config, "Digital twins close the loop [@ranked_2024].\n")
        fake = FakeEntailer(
            {("Digital twins close the control loop.", "Digital twins close the loop."): 0.9}
        )
        report = claim_support.build_report(draft, fake, top_k=1)

        premises = [premise for call in fake.calls for premise, _claim in call]
        assert premises == ["Digital twins close the control loop."]
        assert report.findings[0].score == pytest.approx(0.9)

    def test_a_cap_above_the_premise_count_changes_nothing(self, isolated_config):
        _add_item("small_2024")
        _sidecar("small_2024", [{"text": "Twins close the control loop.", "page": 1}])
        draft = _draft(config, "Digital twins close the loop [@small_2024].\n")
        fake = FakeEntailer(
            {("Twins close the control loop.", "Digital twins close the loop."): 0.91}
        )
        report = claim_support.build_report(draft, fake, top_k=50)

        assert report.findings[0].score == pytest.approx(0.91)

    def test_a_heading_does_not_consume_a_slot(self, isolated_config):
        """The cap ranks what `_quotable` already kept, so a filtered
        heading cannot crowd out a real premise. Capped at 1 with the
        heading ranking highest on overlap, a cap applied *before* the
        filter would send nothing at all and report the source
        unscoreable."""
        _add_item("order_2024")
        _sidecar(
            "order_2024",
            [
                {"text": "Digital twins close the loop", "page": 1, "label": "section_header"},
                {"text": "Twins close the control loop.", "page": 2, "label": "text"},
            ],
        )
        draft = _draft(config, "Digital twins close the loop [@order_2024].\n")
        fake = FakeEntailer(
            {("Twins close the control loop.", "Digital twins close the loop."): 0.77}
        )
        report = claim_support.build_report(draft, fake, top_k=1)

        premises = [premise for call in fake.calls for premise, _claim in call]
        assert premises == ["Twins close the control loop."]
        assert report.findings[0].score == pytest.approx(0.77)

    def test_equal_overlap_breaks_the_tie_on_document_order(self, isolated_config):
        """Two premises with identical overlap must resolve the same way
        on every run, or a capped re-run reports a different best passage
        for an unchanged draft and corpus (R2's stable-identity rule)."""
        _add_item("tied_2024")
        _sidecar(
            "tied_2024",
            [
                {"text": "Twins close the loop.", "page": 1},
                {"text": "The loop is closed by twins.", "page": 2},
            ],
        )
        draft = _draft(config, "Digital twins close the loop [@tied_2024].\n")
        fake = FakeEntailer({})
        claim_support.build_report(draft, fake, top_k=1)

        premises = [premise for call in fake.calls for premise, _claim in call]
        assert premises == ["Twins close the loop."]

    def test_a_claim_with_no_distinctive_words_still_sends_a_premise(self, isolated_config):
        """`distinctive` returns nothing for an all-stopword claim, so
        every premise ties at zero overlap. The cap must still send `k`
        of them rather than an empty batch, which `_score_claim`'s
        documented no-empty-result invariant depends on."""
        _add_item("stopwords_2024")
        _sidecar(
            "stopwords_2024",
            [
                {"text": "Twins close the control loop.", "page": 1},
                {"text": "The plant was instrumented.", "page": 2},
            ],
        )
        draft = _draft(config, "It is so [@stopwords_2024].\n")
        fake = FakeEntailer({})
        report = claim_support.build_report(draft, fake, top_k=1)

        assert len(fake.calls[0]) == 1
        assert report.unscoreable == {}


class TestBuildReport:
    def test_scores_a_claim_against_its_citekeys_best_passage(self, isolated_config):
        _add_item("good_2024")
        _sidecar("good_2024", [{"text": "Twins close the control loop.", "page": 1}])
        draft = _draft(config, "Digital twins close the loop [@good_2024].\n")
        fake = FakeEntailer(
            {("Twins close the control loop.", "Digital twins close the loop."): 0.91}
        )
        report = claim_support.build_report(draft, fake)
        assert len(report.findings) == 1
        finding = report.findings[0]
        assert finding.citekey == "good_2024"
        assert finding.score == pytest.approx(0.91)
        assert finding.passage.text == "Twins close the control loop."

    def test_picks_the_higher_scoring_of_two_quotable_passages(self, isolated_config):
        """`_score_claim`'s whole reason to exist over a bare `quotable[0]`:
        given a real choice between candidates, it must pick the one the
        entailer actually scores higher -- not whichever sidecar record
        happens to sit first. The winning passage is deliberately placed
        *second* in the sidecar list, so a `scores[0]`-shaped bug (or a
        stray `min` in place of `max`) would fail this by returning the
        loser instead."""
        _add_item("twopassage_2024")
        _sidecar(
            "twopassage_2024",
            [
                {"text": "An irrelevant passage about something else.", "page": 1},
                {"text": "Twins close the control loop precisely.", "page": 2},
            ],
        )
        draft = _draft(config, "Digital twins close the loop precisely [@twopassage_2024].\n")
        fake = FakeEntailer(
            {
                (
                    "An irrelevant passage about something else.",
                    "Digital twins close the loop precisely.",
                ): 0.10,
                (
                    "Twins close the control loop precisely.",
                    "Digital twins close the loop precisely.",
                ): 0.88,
            }
        )
        report = claim_support.build_report(draft, fake)
        assert len(report.findings) == 1
        finding = report.findings[0]
        assert finding.passage.text == "Twins close the control loop precisely."
        assert finding.score == pytest.approx(0.88)
        # Both candidates must actually have been sent to the entailer --
        # an implementation that scored only the first passage (or only
        # the winner, decided some other way) would still pass the two
        # assertions above by accident if it happened to guess right.
        assert fake.calls == [
            [
                (
                    "An irrelevant passage about something else.",
                    "Digital twins close the loop precisely.",
                ),
                (
                    "Twins close the control loop precisely.",
                    "Digital twins close the loop precisely.",
                ),
            ]
        ]

    def test_a_citekey_cited_twice_fetches_its_passages_only_once(
        self, isolated_config, monkeypatch
    ):
        """The per-citekey passage cache: a draft citing the same source
        twice must not re-fetch (and, once a real Entailer is in the
        loop, re-embed) its passages a second time."""
        _add_item("shared_2024")
        _sidecar("shared_2024", [{"text": "Twins close the control loop.", "page": 1}])
        calls = []
        real_source_passages = claim_support.source_passages

        def counting(con, citekey):
            calls.append(citekey)
            return real_source_passages(con, citekey)

        monkeypatch.setattr(claim_support, "source_passages", counting)
        draft = _draft(
            config,
            "Digital twins close the loop [@shared_2024].\n\n"
            "It also logs telemetry [@shared_2024].\n",
        )
        fake = FakeEntailer(
            {
                ("Twins close the control loop.", "Digital twins close the loop."): 0.9,
                ("Twins close the control loop.", "It also logs telemetry."): 0.2,
            }
        )
        report = claim_support.build_report(draft, fake)
        assert len(report.findings) == 2
        assert calls == ["shared_2024"]


class TestUnscoreable:
    def test_a_citekey_with_no_passages_at_all_is_noted_not_scored(self, isolated_config):
        draft = _draft(config, "A claim about nothing on record [@missing_2024].\n")
        report = claim_support.build_report(draft, FakeEntailer({}))
        assert report.findings[0].score == 0.0
        assert "missing_2024" in report.unscoreable

    def test_a_citekey_with_only_page_level_passages_is_noted_not_scored(self, isolated_config):
        _add_item("pageonly_2024", parsed_text="whole page one text\fwhole page two text")
        draft = _draft(config, "A claim citing a page scan [@pageonly_2024].\n")
        report = claim_support.build_report(draft, FakeEntailer({}))
        assert report.findings[0].passage is None
        assert "pageonly_2024" in report.unscoreable


class TestOrderingAndId:
    def test_worst_scoring_claim_sorts_first(self, isolated_config):
        _add_item("weak_2024")
        _sidecar("weak_2024", [{"text": "Unrelated source text.", "page": 1}])
        _add_item("strong_2024")
        _sidecar("strong_2024", [{"text": "Twins close the loop.", "page": 1}])
        draft = _draft(
            config,
            "Weak claim here [@weak_2024]. Strong claim here [@strong_2024].\n",
        )
        fake = FakeEntailer(
            {
                ("Unrelated source text.", "Weak claim here."): 0.05,
                ("Twins close the loop.", "Strong claim here."): 0.95,
            }
        )
        report = claim_support.build_report(draft, fake)
        assert [f.citekey for f in report.findings] == ["weak_2024", "strong_2024"]


class TestFindingId:
    def test_stable_across_runs(self):
        assert claim_support.finding_id("k", "c") == claim_support.finding_id("k", "c")

    def test_differs_for_a_different_claim_on_the_same_citekey(self):
        assert claim_support.finding_id("k", "c1") != claim_support.finding_id("k", "c2")


class TestFindings:
    def test_one_dict_per_finding_no_band(self, isolated_config):
        _add_item("good_2024")
        _sidecar("good_2024", [{"text": "Twins close the loop.", "page": 1}])
        draft = _draft(config, "Digital twins close the loop [@good_2024].\n")
        fake = FakeEntailer({("Twins close the loop.", "Digital twins close the loop."): 0.9})
        found = claim_support.findings(claim_support.build_report(draft, fake))
        assert found == [
            {
                "id": claim_support.finding_id("good_2024", "Digital twins close the loop."),
                "line": 1,
                "citekey": "good_2024",
                "claim": "Digital twins close the loop.",
                "score": pytest.approx(0.9),
                "note": None,
            }
        ]


class TestRenderMarkdown:
    def test_includes_the_ranked_not_banded_caveat(self, isolated_config):
        draft = _draft(config, "No citations here.\n")
        report = claim_support.build_report(draft, FakeEntailer({}))
        text = render.render_markdown(report, "cmd", claim_support.findings(report))
        assert "ranked" in text.lower()
        assert "not a fact-check" in text.lower()

    def test_lists_a_finding_with_its_score_and_claim(self, isolated_config):
        _add_item("good_2024")
        _sidecar("good_2024", [{"text": "Twins close the loop.", "page": 1}])
        draft = _draft(config, "Digital twins close the loop [@good_2024].\n")
        fake = FakeEntailer({("Twins close the loop.", "Digital twins close the loop."): 0.9})
        report = claim_support.build_report(draft, fake)
        found = claim_support.findings(report)
        text = render.render_markdown(report, "cmd", found)
        assert "good_2024" in text
        assert "90%" in text

    def test_notes_an_unscoreable_citekey(self, isolated_config):
        draft = _draft(config, "A claim citing nothing on record [@missing_2024].\n")
        report = claim_support.build_report(draft, FakeEntailer({}))
        found = claim_support.findings(report)
        text = render.render_markdown(report, "cmd", found)
        assert "missing_2024" in text
        assert "not in the ledger" in text or "no readable text" in text
        # Real bug found while implementing this task (see task-3-report.md):
        # the brief's own `_finding_lines` printed `finding["score"]:.0%`
        # unconditionally, so an unscoreable citekey -- score 0.0 by
        # `build_report`'s own design -- rendered as "(0%)" in Findings,
        # exactly the "checked and found wanting" standing this aid's
        # module docstring says an unscoreable citekey must not carry.
        assert "(0%)" not in text

    def test_a_bare_citation_with_no_surrounding_prose_notes_missing_claim_text(
        self, isolated_config
    ):
        draft = _draft(config, "[@missing_2024]\n")
        report = claim_support.build_report(draft, FakeEntailer({}))
        found = claim_support.findings(report)
        assert found[0]["claim"] == ""
        text = render.render_markdown(report, "cmd", found)
        assert "(no claim text)" in text


class TestFormatReport:
    def test_plain_text_has_no_markdown_headings(self, isolated_config):
        draft = _draft(config, "No citations here.\n")
        report = claim_support.build_report(draft, FakeEntailer({}))
        text = render.format_report(report, claim_support.findings(report))
        assert "##" not in text

    def test_lists_a_scored_finding_with_its_percentage(self, isolated_config):
        _add_item("good_2024")
        _sidecar("good_2024", [{"text": "Twins close the loop.", "page": 1}])
        draft = _draft(config, "Digital twins close the loop [@good_2024].\n")
        fake = FakeEntailer({("Twins close the loop.", "Digital twins close the loop."): 0.9})
        report = claim_support.build_report(draft, fake)
        text = render.format_report(report, claim_support.findings(report))
        assert "90%" in text
        assert "good_2024" in text

    def test_an_unscoreable_finding_does_not_read_as_a_zero_score(self, isolated_config):
        draft = _draft(config, "A claim citing nothing on record [@missing_2024].\n")
        report = claim_support.build_report(draft, FakeEntailer({}))
        text = render.format_report(report, claim_support.findings(report))
        assert "missing_2024" in text
        assert "0%" not in text
        # `format_report` is a flat list with no summary/detail split like
        # `render_markdown`'s Markdown sections have -- a citekey's reason
        # must appear exactly once, not once per `_format_finding` line and
        # then again from a second, redundant pass over
        # `report.unscoreable` (a real duplication bug found while
        # implementing this task, see task-3-report.md).
        assert text.count("not in the ledger") == 1


class TestRegistration:
    def test_the_aid_is_in_both_tables(self):
        assert "support" in review.AIDS
        assert "support" in review_main.AIDS

    def test_it_files_its_report_beside_the_others(self, isolated_config):
        draft = config.DRAFTS_DIR / "dt" / "survey.md"
        assert review.report_path(draft, "support") == (
            config.REVIEW_DIR / "dt" / "survey.support.md"
        )


class TestCli:
    def test_run_prints_plain_text_by_default(self, isolated_config, capsys, monkeypatch):
        monkeypatch.setattr(entailment, "open_entailer", lambda: (FakeEntailer({}), None))
        draft = _draft(config, "No citations here.\n")
        args = claim_support.build_parser().parse_args([str(draft)])
        assert claim_support.run(args) == 0
        assert "Claim support" in capsys.readouterr().out

    def test_run_prints_json_and_writes(self, isolated_config, capsys, monkeypatch):
        monkeypatch.setattr(entailment, "open_entailer", lambda: (FakeEntailer({}), None))
        draft = _draft(config, "No citations here.\n")
        args = claim_support.build_parser().parse_args([str(draft), "--json", "--write"])
        assert claim_support.run(args) == 0
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert payload["aid"] == "support"
        assert (config.REVIEW_DIR / "topic" / "draft.support.json").exists()

    def test_run_json_only_prints_but_does_not_write(self, isolated_config, capsys, monkeypatch):
        """`--json` with no `--write`: still builds the command/payload
        (unlike the plain-text default path), but must not touch disk --
        the `if args.write:` branch below it must come out False."""
        monkeypatch.setattr(entailment, "open_entailer", lambda: (FakeEntailer({}), None))
        draft = _draft(config, "No citations here.\n")
        args = claim_support.build_parser().parse_args([str(draft), "--json"])
        assert claim_support.run(args) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["aid"] == "support"
        assert not (config.REVIEW_DIR / "topic" / "draft.support.json").exists()

    def test_run_exits_0_and_says_why_when_unavailable(self, isolated_config, capsys, monkeypatch):
        monkeypatch.setattr(entailment, "open_entailer", lambda: (None, "not installed"))
        draft = _draft(config, "No citations here.\n")
        args = claim_support.build_parser().parse_args([str(draft)])
        assert claim_support.run(args) == 0
        assert "not installed" in capsys.readouterr().err

    def test_run_obeys_the_configured_premise_cap(self, isolated_config, capsys, monkeypatch):
        """The CLI is the one caller that reads `SUPPORT_PREMISE_TOPK`;
        `build_report`'s own default stays uncapped so a bench arm can
        pin k per call instead of mutating this constant mid-run."""
        _add_item("clipath_2024")
        _sidecar(
            "clipath_2024",
            [{"text": f"Passage {i} on loops.", "page": 1} for i in range(5)],
        )
        fake = FakeEntailer({})
        monkeypatch.setattr(entailment, "open_entailer", lambda: (fake, None))
        monkeypatch.setattr(config, "SUPPORT_PREMISE_TOPK", 2)
        draft = _draft(config, "Digital twins close the loop [@clipath_2024].\n")
        args = claim_support.build_parser().parse_args([str(draft)])

        assert claim_support.run(args) == 0
        assert len(fake.calls[0]) == 2

    def test_run_returns_1_for_a_missing_draft(self, isolated_config, capsys):
        args = claim_support.build_parser().parse_args(["content/drafts/nope.md"])
        assert claim_support.run(args) == 1

    def test_command_records_json_and_write_flags(self, isolated_config, capsys, monkeypatch):
        """`_command`'s own reason to exist: the header/envelope must
        record a re-runnable invocation, flags included -- not just the
        bare draft path."""
        monkeypatch.setattr(entailment, "open_entailer", lambda: (FakeEntailer({}), None))
        draft = _draft(config, "No citations here.\n")
        args = claim_support.build_parser().parse_args([str(draft), "--json", "--write"])
        claim_support.run(args)
        payload = json.loads(capsys.readouterr().out)
        assert "--json" in payload["command"]
        assert "--write" in payload["command"]

    def test_scored_count_matches_the_rendered_report_when_a_bad_citekey_repeats(
        self, isolated_config
    ):
        """`report.unscoreable` is keyed by citekey, so it gains one
        entry no matter how many findings cite that same unscoreable
        citekey -- `support_payload`'s "scored" must not overcount by
        the naive `len(findings) - len(unscoreable)` in that case (it
        would read 1 here: 2 findings minus 1 unscoreable citekey).
        Built directly from a `Report`, not through the CLI, so this can
        assert the actual invariant the fix is for: the JSON's "scored"
        and the plain-text report's "N citations scored" agree, both
        derived from the same report rather than one merely plausible
        number."""
        draft = _draft(
            config,
            "A claim citing nothing on record [@missing_2024].\n\n"
            "A second claim citing the same nothing [@missing_2024].\n",
        )
        report = claim_support.build_report(draft, FakeEntailer({}))
        found = claim_support.findings(report)
        payload = claim_support.support_payload(report, "cmd")

        assert payload["scored"] == 0
        assert len(payload["unscoreable"]) == 1
        assert len(payload["findings"]) == 2
        assert f"{payload['scored']} citations scored" in render.format_report(report, found)

    def test_main_parses_argv_and_runs(self, isolated_config, capsys, monkeypatch):
        monkeypatch.setattr(entailment, "open_entailer", lambda: (FakeEntailer({}), None))
        draft = _draft(config, "No citations here.\n")
        assert claim_support.main([str(draft)]) == 0
        assert "Claim support" in capsys.readouterr().out

    def test_write_only_records_no_json_flag_and_still_writes(
        self, isolated_config, capsys, monkeypatch
    ):
        """`--write` with no `--json`: `_command`'s `as_json` branch must
        come out False here, unlike every other CLI test above, which
        always pairs `--write` with `--json`."""
        monkeypatch.setattr(entailment, "open_entailer", lambda: (FakeEntailer({}), None))
        draft = _draft(config, "No citations here.\n")
        args = claim_support.build_parser().parse_args([str(draft), "--write"])
        assert claim_support.run(args) == 0
        assert (config.REVIEW_DIR / "topic" / "draft.support.json").exists()
        payload = json.loads((config.REVIEW_DIR / "topic" / "draft.support.json").read_text())
        assert "--json" not in payload["command"]
        assert "--write" in payload["command"]

    def test_build_parser_accepts_a_parser_passed_in(self):
        """`review/__main__.py` calls `module.build_parser(sub.add_parser(...))`
        -- always with a parser already built -- so the `parser is None`
        branch (this module's own standalone `main()`) is a second path,
        not the only one."""
        parser = argparse.ArgumentParser()
        returned = claim_support.build_parser(parser)
        assert returned is parser

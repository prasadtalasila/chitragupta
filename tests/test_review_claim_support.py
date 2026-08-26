"""chitragupta/review/claim_support.py: does the cited source actually
entail the claim citing it, per a real NLI model (stubbed here --
the module's own logic is what is under test, not the model)."""

import json

import pytest

from chitragupta import config, ledger, review
from chitragupta.review import _claim_support_render as render
from chitragupta.review import claim_support


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
                ("An irrelevant passage about something else.",
                 "Digital twins close the loop precisely."),
                ("Twins close the control loop precisely.",
                 "Digital twins close the loop precisely."),
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


@pytest.fixture
def registered_aid(monkeypatch):
    """`render_markdown` calls `review.header(report.draft, "support",
    command)`, and `header()` does a bare `AIDS[aid]` lookup. Task 4 --
    not this one -- registers "support" in `review.AIDS` (and,
    indivisibly, in `review/__main__.py`'s own `AIDS`, since that
    module's import-time guard requires both to have the same keys and
    several other test files already import `review.__main__`). Adding
    the key here for real, ahead of Task 4, would either leave
    `__main__.AIDS` behind (tripping that guard for every test file
    that imports `chitragupta.review.__main__`) or require inventing
    `claim_support.build_parser` early, which is Task 4's job too. So
    this patches the key into `review.AIDS` for the tests in this file
    only -- `render_markdown` itself is unchanged and calls `header`
    exactly as Task 4 will find it."""
    monkeypatch.setitem(review.AIDS, "support", "Claim support")


class TestRenderMarkdown:
    def test_includes_the_ranked_not_banded_caveat(self, isolated_config, registered_aid):
        draft = _draft(config, "No citations here.\n")
        report = claim_support.build_report(draft, FakeEntailer({}))
        text = render.render_markdown(report, "cmd", claim_support.findings(report))
        assert "ranked" in text.lower()
        assert "not a fact-check" in text.lower()

    def test_lists_a_finding_with_its_score_and_claim(self, isolated_config, registered_aid):
        _add_item("good_2024")
        _sidecar("good_2024", [{"text": "Twins close the loop.", "page": 1}])
        draft = _draft(config, "Digital twins close the loop [@good_2024].\n")
        fake = FakeEntailer({("Twins close the loop.", "Digital twins close the loop."): 0.9})
        report = claim_support.build_report(draft, fake)
        found = claim_support.findings(report)
        text = render.render_markdown(report, "cmd", found)
        assert "good_2024" in text
        assert "90%" in text

    def test_notes_an_unscoreable_citekey(self, isolated_config, registered_aid):
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
        self, isolated_config, registered_aid
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

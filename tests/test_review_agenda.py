"""chitragupta/review/agenda/: the eighth review aid, merging the other
eight aids' `.json`, `style_check`'s prose findings, and the dossier's
drift report into one ranked, deduplicated worklist. Issue #381.
"""

import ast
import json
import os
import re
import shlex
import sqlite3
from pathlib import Path

import pytest

from chitragupta import config, dossier, review, style_check
from chitragupta.dossier import _retrieval
from chitragupta.dossier._drift import Candidate, Drift
from chitragupta.review import _registry, agenda, citation_provenance
from chitragupta.review.agenda import (
    _accept,
    _dedup,
    _identity,
    _items,
    _items_findings,
    _order,
    _recheck,
    _refresh,
    _render,
    _sources,
    _stale,
)

from tests.conftest import content_draft


def _sources_stub(**overrides) -> _sources.Sources:
    """A `Sources` bundle with every input absent by default, so a test
    overriding one aid doesn't have to spell out the other five."""
    aids = {aid: _sources.AidSource() for aid in _sources.AID_NAMES}
    aids.update(overrides.pop("aids", {}))
    style = overrides.pop("style", _sources.StyleSource())
    drift = overrides.pop("drift", _sources.DriftSource())
    uncited = overrides.pop("recorded", _sources.RecordedSource())
    assert not overrides
    return _sources.Sources(aids=aids, style=style, drift=drift, recorded=uncited)


# --------------------------------------------------------------------------
# _identity.py
# --------------------------------------------------------------------------


class TestItemId:
    def test_stable_across_calls(self):
        first = _identity.item_id("provenance", "unsupported-claim", "Intro", "a2024", "claim")
        second = _identity.item_id("provenance", "unsupported-claim", "Intro", "a2024", "claim")
        assert first == second

    def test_different_span_yields_different_id(self):
        one = _identity.item_id("provenance", "unsupported-claim", "Intro", "a2024", "claim one")
        two = _identity.item_id("provenance", "unsupported-claim", "Intro", "a2024", "claim two")
        assert one != two


class TestSectionAnchor:
    def test_none_line_has_no_anchor(self):
        assert _identity.section_anchor(dossier.sections("# Title\n\ntext\n"), None) is None

    def test_line_before_any_heading_has_no_anchor(self):
        text = "intro line\n\n# Heading\n\nbody\n"
        assert _identity.section_anchor(dossier.sections(text), 1) is None

    def test_line_inside_a_section_is_anchored(self):
        text = "# Heading\n\nbody line\n"
        assert _identity.section_anchor(dossier.sections(text), 3) == "Heading"


# --------------------------------------------------------------------------
# _sources.py
# --------------------------------------------------------------------------


class TestAidNames:
    def test_support_is_read(self):
        """#427: `support`'s findings carry no `band`, but that only ever
        ruled out `unsupported_claim_items` re-using it as a second
        source -- not `agenda` reading its `.json` at all."""
        assert "support" in _sources.AID_NAMES

    def test_excludes_exactly_agenda_and_union(self):
        """The relationship `_sources.py`'s own comment states, asserted
        rather than left to that comment (#573).

        Every existing test in this module derives its expectations
        *from* `AID_NAMES`, so before this one the tuple could fall
        behind `review.AIDS` without a single test going red -- which is
        how `union` came to be missing from it while the comment above
        it still said `agenda` was the only exclusion. An eleventh aid
        now has to decide whether `agenda` reads it.

        `union` is excluded for what its findings are about, not for
        where they live: it files `<stem>.union.json` beside a reviewable
        path like the rest, but it reads an assembled book, and a
        citekey the assembly dropped is a fact about the assembly rather
        than a sentence anyone can repair in the draft this worklist was
        asked about. The same book-not-draft ground
        docs/PERFORMANCE.md leaves it out of the draft-review cost
        figures on.
        """
        assert set(_sources.AID_NAMES) == set(review.AIDS) - {"agenda", "union"}

    def test_reads_in_the_registry_s_own_order(self):
        """The other half of that comment: "in `review.AIDS`'s own
        order". Not cosmetic -- `_render._SOURCE_LABELS` restates that
        order a third time, and the assertion below pins the two
        together."""
        read = set(_sources.AID_NAMES)
        assert _sources.AID_NAMES == tuple(aid for aid in review.AIDS if aid in read)

    def test_render_s_source_labels_are_the_registry_s_own(self):
        """`_render._SOURCE_LABELS` is a third hand-maintained copy of
        the same eight aids -- their keys *and* `review.AIDS`' own label
        strings -- and it fails harder than `AID_NAMES` does when it
        drifts: `_render.py`'s header builder does
        `agenda.sources.aids[aid]` for every key in it, so a key
        `AID_NAMES` lacks is a `KeyError` mid-report rather than a
        missing line.

        Asserted rather than deduplicated: collapsing it to a
        comprehension over `AID_NAMES` would be a change to the
        rendering path, which #573 is not about. This is the guard that
        makes that refactor safe to do later, or unnecessary.
        """
        assert _render._SOURCE_LABELS == {aid: review.AIDS[aid] for aid in _sources.AID_NAMES}
        assert tuple(_render._SOURCE_LABELS) == _sources.AID_NAMES


class TestReadAidJson:
    def test_absent_json_is_reported_unavailable(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n")
        source = _sources._read_aid_json(draft, "provenance")
        assert source == _sources.AidSource()

    def test_present_and_fresh_json_is_not_stale(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n")
        path = review.write_json(draft, "provenance", {"findings": []})
        os.utime(path, (draft.stat().st_mtime + 10, draft.stat().st_mtime + 10))

        source = _sources._read_aid_json(draft, "provenance")
        assert source.available is True
        assert source.stale is False
        assert source.data == {"findings": []}

    def test_present_but_older_json_is_stale(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n")
        path = review.write_json(draft, "provenance", {"findings": []})
        os.utime(path, (draft.stat().st_mtime - 10, draft.stat().st_mtime - 10))
        os.utime(draft, (draft.stat().st_mtime + 20, draft.stat().st_mtime + 20))

        source = _sources._read_aid_json(draft, "provenance")
        assert source.stale is True

    def test_truncated_json_degrades_to_unavailable_with_a_reason(self, isolated_config):
        """One corrupted aid sidecar must not take down the whole agenda
        (#496) -- the module docstring's "each degrading to absent"
        covers a truncated file, not only a missing one."""
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n")
        path = review.write_json(draft, "provenance", {"findings": []})
        path.write_text('{"findings": [', encoding="utf-8")

        source = _sources._read_aid_json(draft, "provenance")
        assert source.available is False
        assert source.data is None
        assert source.reason is not None


class TestReadStyle:
    def test_clean_run_is_not_partial(self, isolated_config, monkeypatch):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n")
        monkeypatch.setattr(
            _sources.style_check,
            "check",
            lambda d, override=None, propose=True: {"findings": [], "vale_error": None},
        )
        source = _sources._read_style(draft)
        assert source == _sources.StyleSource(
            available=True, partial=False, data={"findings": [], "vale_error": None}
        )

    def test_missing_vale_is_partial(self, isolated_config, monkeypatch):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n")
        monkeypatch.setattr(
            _sources.style_check,
            "check",
            lambda d, override=None, propose=True: {
                "findings": [],
                "vale_error": "vale is not on PATH",
            },
        )
        source = _sources._read_style(draft)
        assert source.partial is True


class TestReadDrift:
    def test_draft_outside_drafts_dir_has_no_dossier(self, isolated_config):
        draft = content_draft(isolated_config, "not-a-draft.md")
        draft.write_text("# Not a draft\n")
        source = _sources._read_drift(draft)
        assert source == _sources.DriftSource()

    def test_draft_under_drafts_with_no_dossier_created(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n")
        source = _sources._read_drift(draft)
        assert source == _sources.DriftSource()

    def test_dossier_without_ledger_is_corpus_unavailable(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n")
        dossier.dossier_dir(draft).mkdir(parents=True)

        source = _sources._read_drift(draft)
        assert source.available is True
        assert source.corpus_available is False

    def test_dossier_with_ledger_reports_missing_citekey(self, isolated_config, ledger_con):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n\nA claim [@gone_2024].\n")
        directory = dossier.dossier_dir(draft)
        directory.mkdir(parents=True)
        (directory / dossier.SECTIONS_MD).write_text(
            "| Section | Citekeys |\n| --- | --- |\n| Intro | `gone_2024` |\n"
        )

        source = _sources._read_drift(draft)
        assert source.available is True
        assert source.corpus_available is True
        assert source.data.missing == {"gone_2024": ["Intro"]}


class TestReadRecorded:
    """The `recorded-but-uncited` source degrades to absent on the same
    two states `_read_drift` does -- a reduced source set, never a
    refusal (#701)."""

    def test_draft_outside_drafts_dir_has_no_dossier(self, isolated_config):
        draft = content_draft(isolated_config, "not-a-draft.md")
        draft.write_text("# Not a draft\n")
        assert _sources._read_recorded(draft) == _sources.RecordedSource()

    def test_draft_under_drafts_with_no_dossier_created(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n")
        assert _sources._read_recorded(draft) == _sources.RecordedSource()

    def test_a_dossier_recording_an_uncited_citekey_reports_it(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n\nNo citations here.\n")
        directory = dossier.dossier_dir(draft)
        directory.mkdir(parents=True)
        (directory / dossier.EVIDENCE_MD).write_text(
            "## `gone_2024`\n\n- relevance: kept for a section since deleted\n",
            encoding="utf-8",
        )

        source = _sources._read_recorded(draft)
        assert source.available is True
        assert source.data == {"gone_2024": ["evidence"]}


class TestCollect:
    def test_collects_all_eight_inputs(self, isolated_config, monkeypatch):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n")
        monkeypatch.setattr(
            _sources.style_check,
            "check",
            lambda d, override=None, propose=True: {"findings": [], "vale_error": None},
        )
        sources = _sources.collect(draft)
        assert set(sources.aids) == set(_sources.AID_NAMES)
        assert sources.style.available is True
        assert sources.drift == _sources.DriftSource()

    def test_a_refresh_error_is_carried_onto_its_source_and_its_flags(
        self, isolated_config, monkeypatch
    ):
        """#893: the reason an aid raised during `--baseline`'s refresh
        rides on its `AidSource`, and from there into the filed payload's
        `sources.aids.<aid>` -- every other aid's stays `None`."""
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n")
        monkeypatch.setattr(
            _sources.style_check,
            "check",
            lambda d, override=None, propose=True: {"findings": [], "vale_error": None},
        )
        refreshed = {**dict.fromkeys(_sources.AID_NAMES, True), "support": False}
        sources = _sources.collect(draft, refreshed, {"support": "RuntimeError: boom"})
        assert sources.aids["support"].refresh_error == "RuntimeError: boom"
        assert sources.aids["support"].flags()["refresh_error"] == "RuntimeError: boom"
        assert all(sources.aids[aid].refresh_error is None for aid in _sources.AID_NAMES[:-1])


# --------------------------------------------------------------------------
# _items.py
# --------------------------------------------------------------------------


class TestMissingCitekeyItems:
    def test_no_drift_gives_no_items(self):
        assert _items.missing_citekey_items(None) == []

    def test_one_item_per_missing_citekey(self):
        drift = Drift(dossier=Path("d"), name="d", draft=None, missing={"a2024": ["Intro"]})
        items = _items.missing_citekey_items(drift)
        assert len(items) == 1
        assert items[0].cls == "missing-citekey"
        assert items[0].citekey == "a2024"
        assert items[0].section == "Intro"
        assert items[0].unattended is True
        assert items[0].detail == {"sections": ["Intro"]}

    def test_citekey_with_no_section_anchors_on_none(self):
        drift = Drift(dossier=Path("d"), name="d", draft=None, missing={"a2024": []})
        items = _items.missing_citekey_items(drift)
        assert items[0].section is None


class TestSurfacedButNeverUsedClassesAreGone:
    """`uncited-source` and `candidate` were removed from the agenda.

    Both said "the corpus holds a paper you surfaced and did not cite",
    which for a draft that makes no claim from it is the correct outcome
    rather than a finding. The aids that computed them are untouched --
    that is the point of the pair of tests below: the *inputs* that used
    to raise each class are still constructed here, in full, and the
    assertion is that the agenda no longer turns either into an item. A
    test that merely dropped the old ones would pass just as well if the
    aids had been deleted too, which is a different change from the one
    that was made.
    """

    def test_neither_class_is_in_the_class_table(self):
        assert "uncited-source" not in _items.CLASSES
        assert "candidate" not in _items.CLASSES

    def test_a_drift_candidate_raises_no_agenda_item(self):
        drift = Drift(
            dossier=Path("d"),
            name="d",
            draft=None,
            candidates=[Candidate("b2024", "A Paper", ["query one"])],
        )
        sources = _sources_stub(drift=_sources.DriftSource(available=True, data=drift))
        assert _items.all_items(sources, []) == []

    def test_an_uncited_retrieved_source_raises_no_agenda_item(self):
        coverage = _sources.AidSource(
            available=True,
            data={
                "findings": [
                    {"id": "1", "citekey": "a2024", "title": "A", "status": "uncited_candidates"}
                ]
            },
        )
        sources = _sources_stub(aids={"coverage": coverage})
        assert _items.all_items(sources, []) == []


class TestRecordedButUncitedItems:
    """Issue #701's new class: the mirror image of `missing-citekey`,
    and surfaced rather than unattended because the dossier cannot tell
    a citation the user cut from a candidate never cited at all."""

    def test_no_source_gives_no_items(self):
        assert _items.recorded_but_uncited_items(_sources.RecordedSource()) == []

    def test_one_item_per_citekey(self):
        source = _sources.RecordedSource(available=True, data={"a2024": ["evidence"]})
        items = _items.recorded_but_uncited_items(source)
        assert len(items) == 1
        item = items[0]
        assert item.cls == "recorded-but-uncited"
        assert item.citekey == "a2024"
        assert item.line is None
        assert item.section is None
        assert item.unattended is False
        assert item.detail == {"surfaces": ["evidence"]}

    def test_the_summary_names_every_surface_as_a_real_filename(self):
        """Each surface carries its own `.md`. Joining first and
        suffixing once reads "evidence, sections.md", which names a file
        that does not exist -- and a test asserting only that both words
        appear passes on it."""
        source = _sources.RecordedSource(available=True, data={"a2024": ["evidence", "sections"]})
        summary = _items.recorded_but_uncited_items(source)[0].summary
        assert "evidence.md, sections.md" in summary
        assert "evidence, sections.md" not in summary

    def test_items_are_ordered_by_citekey(self):
        source = _sources.RecordedSource(
            available=True, data={"b2024": ["evidence"], "a2024": ["evidence"]}
        )
        items = _items.recorded_but_uncited_items(source)
        assert [item.citekey for item in items] == ["a2024", "b2024"]


class TestVerbatimRunItems:
    def _finding(self, **overrides):
        base = {
            "id": "abc123",
            "citekey": "a2024",
            "line": 5,
            "span_words": 20,
            "matched_words": 20,
            "fragment": "some borrowed wording",
            "severity": "long",
            "tier": "exact",
        }
        base.update(overrides)
        return base

    def test_unavailable_source_gives_no_items(self):
        assert _items_findings.verbatim_run_items(_sources.AidSource(), []) == []

    def test_quoted_is_excluded(self):
        source = _sources.AidSource(
            available=True, data={"findings": [self._finding(severity="quoted")]}
        )
        assert _items_findings.verbatim_run_items(source, []) == []

    def test_long_is_surfaced(self):
        source = _sources.AidSource(
            available=True, data={"findings": [self._finding(severity="long")]}
        )
        items = _items_findings.verbatim_run_items(source, [])
        assert items[0].unattended is False
        assert items[0].cls == "verbatim-run"

    def test_short_is_unattended(self):
        source = _sources.AidSource(
            available=True, data={"findings": [self._finding(severity="short", matched_words=8)]}
        )
        items = _items_findings.verbatim_run_items(source, [])
        assert items[0].unattended is True

    def test_no_citekey_still_produces_a_summary(self):
        source = _sources.AidSource(
            available=True, data={"findings": [self._finding(citekey=None, severity="short")]}
        )
        items = _items_findings.verbatim_run_items(source, [])
        assert "citing" not in items[0].summary

    def test_an_ungapped_run_is_summarised_by_its_length_alone(self):
        source = _sources.AidSource(
            available=True,
            data={"findings": [self._finding(span_words=13, matched_words=13)]},
        )
        items = _items_findings.verbatim_run_items(source, [])
        assert items[0].summary == "13-word verbatim run citing `a2024`"

    def test_a_gapped_match_reports_its_span_and_its_matched_count(self):
        """A skip-gram or embedding finding matches fewer words than it
        spans, and summarising it by `matched_words` alone reads as a
        verbatim run shorter than `--min-run` -- which cannot happen and
        which no report claims: `_scan.py`'s `_matched_note` renders the
        same finding as `15 words, 6 matched`. The agenda has to agree
        with the aid it is quoting."""
        source = _sources.AidSource(
            available=True,
            data={"findings": [self._finding(span_words=15, matched_words=6)]},
        )
        items = _items_findings.verbatim_run_items(source, [])
        assert items[0].summary == "15-word verbatim run citing `a2024`, 6 matched"

    def test_an_embedding_finding_is_never_unattended_however_short(self):
        """`severity` comes from `_bucket`, which thresholds on
        `matched_words` and never looks at `tier` -- so a short embedding
        alignment arrives here indistinguishable from a short exact run.
        Marking it unattended authorises `agenda-reviser` to edit a
        passage away on the evidence of a similarity score, while
        `verbatim_check._recheck` refuses to so much as *count* that tier
        because its own docstring calls it advisory only, permanently."""
        source = _sources.AidSource(
            available=True,
            data={"findings": [self._finding(severity="short", matched_words=8, tier="embedding")]},
        )
        items = _items_findings.verbatim_run_items(source, [])
        assert items[0].unattended is False

    def test_a_short_skipgram_finding_is_still_unattended(self):
        """The gate is on the embedding tier specifically, not on
        "anything that is not exact": skip-gram is deterministic,
        reproducible from the corpus alone, and is counted by `recheck`
        like tier 1."""
        source = _sources.AidSource(
            available=True,
            data={"findings": [self._finding(severity="short", matched_words=8, tier="skip-gram")]},
        )
        items = _items_findings.verbatim_run_items(source, [])
        assert items[0].unattended is True

    def test_the_summary_names_what_the_tier_actually_found(self):
        """Calling every finding a "verbatim run" is true only of tier 1.
        A skip-gram match has words substituted and an embedding
        alignment shares no wording at all -- and the agenda must not
        make a stronger claim than the aid it quotes."""

        def summary(tier):
            source = _sources.AidSource(
                available=True, data={"findings": [self._finding(tier=tier)]}
            )
            return _items_findings.verbatim_run_items(source, [])[0].summary

        assert summary("exact").startswith("20-word verbatim run")
        assert summary("skip-gram").startswith("20-word skip-gram match")
        assert summary("embedding").startswith("20-word embedding-tier alignment")

    def test_a_report_filed_before_the_tier_field_existed_overstates_nothing(self):
        """`tier` is absent from a payload written before it existed, and
        the agenda reads reports off disk rather than recomputing them.
        The fallback is the neutral "run" -- never "verbatim run", which
        would be a claim about a tier that did not record itself."""
        finding = self._finding()
        del finding["tier"]
        source = _sources.AidSource(available=True, data={"findings": [finding]})
        items = _items_findings.verbatim_run_items(source, [])
        assert items[0].summary == "20-word run citing `a2024`"
        assert "verbatim" not in items[0].summary


class TestProseItems:
    def test_unavailable_source_gives_no_items(self):
        assert _items_findings.prose_items(_sources.StyleSource(), []) == []

    def test_finding_gets_an_item_and_a_synthesized_id(self):
        source = _sources.StyleSource(
            available=True,
            data={
                "findings": [
                    {
                        "rule": "chitragupta.Spacing",
                        "match": "  ",
                        "line": 4,
                        "message": "m",
                        "severity": "warning",
                        "count": 2,
                    }
                ]
            },
        )
        items = _items_findings.prose_items(source, [])
        assert len(items) == 1
        assert items[0].cls == "prose"
        assert items[0].line == 4
        assert items[0].detail["count"] == 2

    def test_prose_is_unattended(self):
        """Issue 421's decision. `style_check` already restricts itself to
        the decidable rules, so every prose item *is* the mechanically
        re-checkable subset the class table names -- and the repair is an
        edit to the draft, which is R1's write-set, unlike `uncited-claim`
        and `misquoted`."""
        source = _sources.StyleSource(
            available=True,
            data={
                "findings": [
                    {
                        "rule": "chitragupta.FigureNoCaption",
                        "match": "x",
                        "line": 3,
                        "message": "m",
                        "severity": "suggestion",
                        "count": 1,
                    }
                ]
            },
        )
        assert _items_findings.prose_items(source, [])[0].unattended is True

    def test_a_review_mode_finding_is_surfaced_not_unattended(self):
        """Issue 836: a rule whose right repair may be "leave it alone"
        says so with `repair="review"`, and the agenda honours it."""
        finding = {"rule": "r", "match": "x", "line": 3, "count": 1, "repair": "review"}
        source = _sources.StyleSource(available=True, data={"findings": [finding]})
        assert _items_findings.prose_items(source, [])[0].unattended is False

    def test_line_zero_is_treated_as_no_position(self):
        source = _sources.StyleSource(
            available=True,
            data={
                "findings": [
                    {
                        "rule": "r",
                        "match": "AI",
                        "line": 0,
                        "message": "m",
                        "severity": "s",
                        "count": 45,
                    }
                ]
            },
        )
        items = _items_findings.prose_items(source, [])
        assert items[0].line is None
        assert items[0].section is None


class TestProseRepairMode:
    """Issue 836, through the live path the agenda reads -- `_read_style`
    calls `style_check.check()`, so the dialect decision is exercised
    where it is made rather than by hand-setting `repair` on a finding.

    A dialect is the author's own statement only from `scope.md` or a
    `--language` flag; one resolved from the host-wide `config.toml`
    default may be wrong for this draft, and re-spelling a whole draft
    on its evidence is not a repair to make unasked."""

    @pytest.fixture
    def draft(self, isolated_config, monkeypatch):
        path = content_draft(isolated_config, "drafts/t/survey.md")
        path.write_text("# Survey\n\nWe organise the data.\n", encoding="utf-8")
        vale = [
            {"Check": "chitragupta.DialectUS", "Match": "organise", "Line": 3, "Message": "m"},
            {"Check": "chitragupta.DefectMarkers", "Match": "the", "Line": 3, "Message": "m"},
        ]
        monkeypatch.setattr(style_check, "run_vale", lambda d, lang: list(vale))
        monkeypatch.setattr(config, "STYLE_LANGUAGE", "en-US")
        return path

    @staticmethod
    def _unattended(draft) -> dict:
        items = _items_findings.prose_items(_sources._read_style(draft), [])
        return {item.summary.split(":")[0]: item.unattended for item in items}

    def test_a_config_toml_dialect_is_surfaced_not_repaired(self, draft):
        flags = self._unattended(draft)
        assert flags["chitragupta.DialectUS"] is False
        # Only the dialect rule is demoted; every other Vale rule is
        # still an edit whatever the language's source.
        assert flags["chitragupta.DefectMarkers"] is True

    def test_a_scope_md_dialect_is_unattended(self, draft):
        scope_dir = dossier.dossier_dir(draft)
        scope_dir.mkdir(parents=True, exist_ok=True)
        (scope_dir / dossier.SCOPE_MD).write_text(
            "# Scope\n\n- genre: survey\n- language: en-US\n", encoding="utf-8"
        )
        assert self._unattended(draft)["chitragupta.DialectUS"] is True

    def test_a_language_flag_dialect_is_repaired_by_edit(self, draft):
        found = style_check.check(draft, "en-US", propose=False)["findings"]
        assert {f["rule"]: f["repair"] for f in found}["chitragupta.DialectUS"] == "edit"

    def test_a_wide_code_line_is_never_unattended(self, draft, monkeypatch):
        """A tutorial's verified-to-run block may be wide on purpose (a
        long URL or literal); rewrapping it breaks what was promised to
        run, so the width is reported for a person to decide."""
        monkeypatch.setattr(style_check, "run_vale", lambda d, lang: [])
        draft.write_text(f"# Survey\n\n```\n{'x' * 90}\n```\n", encoding="utf-8")
        assert self._unattended(draft) == {"chitragupta.WideCodeLine": False}


class TestUnsupportedClaimItems:
    def _finding(self, **overrides):
        base = {
            "id": "x",
            "citekey": "a2024",
            "claim": "a claim",
            "score": 0.1,
            "band": "weak",
            "line": 3,
        }
        base.update(overrides)
        return base

    def test_unavailable_source_gives_no_items(self):
        assert _items_findings.unsupported_claim_items(_sources.AidSource(), []) == []

    def test_supported_band_is_excluded(self):
        source = _sources.AidSource(
            available=True, data={"findings": [self._finding(band="supported")]}
        )
        assert _items_findings.unsupported_claim_items(source, []) == []

    def test_weak_and_no_support_are_included(self):
        source = _sources.AidSource(
            available=True,
            data={"findings": [self._finding(band="weak"), self._finding(band="no support found")]},
        )
        items = _items_findings.unsupported_claim_items(source, [])
        assert len(items) == 2
        assert items[0].detail["claim"] == "a claim"


class TestClaimSupportItems:
    def _finding(self, **overrides):
        base = {
            "id": "x",
            "citekey": "a2024",
            "claim": "a claim",
            "score": 0.12,
            "line": 3,
            "note": None,
        }
        base.update(overrides)
        return base

    def test_unavailable_source_gives_no_items(self):
        assert _items_findings.claim_support_items(_sources.AidSource(), []) == []

    def test_scored_finding_becomes_an_item(self):
        source = _sources.AidSource(available=True, data={"findings": [self._finding()]})
        items = _items_findings.claim_support_items(source, [])
        assert len(items) == 1
        item = items[0]
        assert item.cls == "claim-support"
        assert item.citekey == "a2024"
        assert item.line == 3
        assert item.unattended is False
        assert item.detail["score"] == 0.12
        assert "not a verdict" in item.summary

    def test_unscoreable_finding_is_excluded(self):
        source = _sources.AidSource(
            available=True,
            data={"findings": [self._finding(note="no quotable passage", score=0.0)]},
        )
        assert _items_findings.claim_support_items(source, []) == []

    def test_well_supported_finding_is_still_included(self):
        """Unfiltered by design: a high score is not excluded, since a
        cutoff would claim a precision this corpus does not support --
        the same argument that keeps this aid ranked, never banded."""
        source = _sources.AidSource(available=True, data={"findings": [self._finding(score=0.97)]})
        items = _items_findings.claim_support_items(source, [])
        assert len(items) == 1


class TestUncitedClaimItems:
    def test_unavailable_source_gives_no_items(self):
        assert _items_findings.uncited_claim_items(_sources.AidSource(), []) == []

    def test_every_finding_becomes_an_item(self):
        source = _sources.AidSource(
            available=True,
            data={
                "findings": [
                    {"id": "1", "line": 2, "sentence": "A bare claim.", "block_cites": False}
                ]
            },
        )
        items = _items_findings.uncited_claim_items(source, [])
        assert len(items) == 1
        assert items[0].detail["block_cites"] is False


class TestMisquotedItems:
    def test_unavailable_source_gives_no_items(self):
        assert _items_findings.misquoted_items(_sources.AidSource()) == []

    def test_one_item_per_finding_no_line_or_section(self):
        source = _sources.AidSource(
            available=True,
            data={
                "findings": [
                    {
                        "id": "q1",
                        "citekey": "a2024",
                        "quote": "a span not in the source",
                        "near_miss_page": 3,
                        "near_miss_score": 0.4,
                    }
                ]
            },
        )
        items = _items_findings.misquoted_items(source)
        assert len(items) == 1
        item = items[0]
        assert item.cls == "misquoted"
        assert item.citekey == "a2024"
        assert item.line is None
        assert item.section is None
        assert item.unattended is False
        assert item.detail == {
            "near_miss_page": 3,
            "near_miss_score": 0.4,
            "quotation_id": "q1",
        }


class TestAllItems:
    def test_claim_support_items_are_included(self):
        sources = _sources_stub(
            aids={
                "support": _sources.AidSource(
                    available=True,
                    data={
                        "findings": [
                            {
                                "id": "1",
                                "citekey": "a2024",
                                "claim": "a claim",
                                "score": 0.2,
                                "line": 1,
                                "note": None,
                            }
                        ]
                    },
                )
            }
        )
        items = _items.all_items(sources, [])
        assert [item.cls for item in items] == ["claim-support"]

    def test_recorded_but_uncited_items_are_included(self):
        sources = _sources_stub(
            recorded=_sources.RecordedSource(available=True, data={"a2024": ["evidence"]})
        )
        items = _items.all_items(sources, [])
        assert [item.cls for item in items] == ["recorded-but-uncited"]

    def test_the_class_sorts_directly_after_missing_citekey(self):
        """Position is visibility: appended after `candidate` the class
        would render beneath every candidate item, which on a real
        draft runs to three figures (#701)."""
        assert _items.CLASSES.index("recorded-but-uncited") == (
            _items.CLASSES.index("missing-citekey") + 1
        )

    def test_synthesis_and_figure_produce_no_items(self):
        sources = _sources_stub(
            aids={
                "synthesis": _sources.AidSource(available=True, data={"findings": [{"id": "1"}]}),
                "figure": _sources.AidSource(
                    available=True, data={"findings": [{"kind": "node-overlap"}]}
                ),
            }
        )
        assert _items.all_items(sources, []) == []


# --------------------------------------------------------------------------
# _dedup.py
# --------------------------------------------------------------------------


class TestDedup:
    def test_unsupported_claim_sharing_a_missing_citekey_is_suppressed(self):
        missing = _items.Item(
            id="m1",
            cls="missing-citekey",
            section=None,
            citekey="a2024",
            line=None,
            unattended=True,
            summary="missing",
            detail={},
        )
        unsupported = _items.Item(
            id="u1",
            cls="unsupported-claim",
            section=None,
            citekey="a2024",
            line=5,
            unattended=False,
            summary="unsupported",
            detail={"claim": "the claim text"},
        )
        merged = _dedup.merge([missing, unsupported])
        assert [item.id for item in merged] == ["m1"]
        assert merged[0].detail["corroborating_claims"] == ["the claim text"]

    def test_unsupported_claim_without_a_missing_citekey_survives(self):
        unsupported = _items.Item(
            id="u1",
            cls="unsupported-claim",
            section=None,
            citekey="z2024",
            line=5,
            unattended=False,
            summary="unsupported",
            detail={"claim": "text"},
        )
        merged = _dedup.merge([unsupported])
        assert merged == [unsupported]

    def test_same_line_different_classes_cross_link_but_both_survive(self):
        one = _items.Item(
            id="v1",
            cls="verbatim-run",
            section=None,
            citekey="a2024",
            line=5,
            unattended=True,
            summary="run",
            detail={},
        )
        two = _items.Item(
            id="u1",
            cls="unsupported-claim",
            section=None,
            citekey="a2024",
            line=5,
            unattended=False,
            summary="claim",
            detail={"claim": "x"},
        )
        merged = _dedup.merge([one, two])
        assert {item.id for item in merged} == {"v1", "u1"}
        by_id = {item.id: item for item in merged}
        assert by_id["v1"].detail["also_flagged"] == [{"id": "u1", "class": "unsupported-claim"}]
        assert by_id["u1"].detail["also_flagged"] == [{"id": "v1", "class": "verbatim-run"}]

    def test_unsupported_claim_and_claim_support_cross_link_not_collapse(self):
        """#427: `support` asks the same underlying question as
        `provenance` but is deliberately not a second source for
        `unsupported-claim` -- two scorers on the same claim are two
        distinct findings, cross-linked by the same generic same-line
        mechanism every other class pair already uses, never collapsed
        into one item."""
        unsupported = _items.Item(
            id="u1",
            cls="unsupported-claim",
            section=None,
            citekey="a2024",
            line=5,
            unattended=False,
            summary="claim",
            detail={"claim": "x", "band": "weak"},
        )
        support = _items.Item(
            id="s1",
            cls="claim-support",
            section=None,
            citekey="a2024",
            line=5,
            unattended=False,
            summary="claim",
            detail={"claim": "x", "score": 0.12},
        )
        merged = _dedup.merge([unsupported, support])
        assert {item.id for item in merged} == {"u1", "s1"}
        by_id = {item.id: item for item in merged}
        assert by_id["u1"].detail["also_flagged"] == [{"id": "s1", "class": "claim-support"}]
        assert by_id["s1"].detail["also_flagged"] == [{"id": "u1", "class": "unsupported-claim"}]

    def test_no_line_means_no_cross_link(self):
        candidate = _items.Item(
            id="c1",
            cls="candidate",
            section=None,
            citekey="a2024",
            line=None,
            unattended=False,
            summary="candidate",
            detail={},
        )
        merged = _dedup.merge([candidate])
        assert "also_flagged" not in merged[0].detail

    def test_duplicate_id_collapses_defensively(self):
        one = _items.Item(
            id="dup",
            cls="candidate",
            section=None,
            citekey="a2024",
            line=None,
            unattended=False,
            summary="a",
            detail={},
        )
        two = _items.Item(
            id="dup",
            cls="candidate",
            section=None,
            citekey="b2024",
            line=None,
            unattended=False,
            summary="b",
            detail={},
        )
        assert _dedup.merge([one, two]) == [one]


# --------------------------------------------------------------------------
# _order.py
# --------------------------------------------------------------------------


class TestSeverityRank:
    def test_verbatim_long_ranks_before_short(self):
        long_item = _items.Item(
            "1", "verbatim-run", None, None, 1, False, "s", {"severity": "long"}
        )
        short_item = _items.Item(
            "2", "verbatim-run", None, None, 1, True, "s", {"severity": "short"}
        )
        assert _order.severity_rank(long_item) < _order.severity_rank(short_item)

    def test_unknown_verbatim_severity_ranks_last(self):
        item = _items.Item("1", "verbatim-run", None, None, 1, False, "s", {"severity": "???"})
        assert _order.severity_rank(item) == 2

    def test_provenance_no_support_ranks_before_weak(self):
        no_support = _items.Item(
            "1", "unsupported-claim", None, None, 1, False, "s", {"band": "no support found"}
        )
        weak = _items.Item("2", "unsupported-claim", None, None, 1, False, "s", {"band": "weak"})
        assert _order.severity_rank(no_support) < _order.severity_rank(weak)

    def test_claim_support_lower_score_ranks_first(self):
        low = _items.Item("1", "claim-support", None, None, 1, False, "s", {"score": 0.1})
        high = _items.Item("2", "claim-support", None, None, 1, False, "s", {"score": 0.9})
        assert _order.severity_rank(low) < _order.severity_rank(high)

    def test_uncited_claim_bare_ranks_before_block_cites(self):
        bare = _items.Item("1", "uncited-claim", None, None, 1, False, "s", {"block_cites": False})
        cited = _items.Item("2", "uncited-claim", None, None, 1, False, "s", {"block_cites": True})
        assert _order.severity_rank(bare) < _order.severity_rank(cited)

    def test_classes_with_no_severity_notion_rank_zero(self):
        item = _items.Item("1", "missing-citekey", None, None, None, True, "s", {})
        assert _order.severity_rank(item) == 0


class TestSort:
    def test_class_order_wins_over_input_order(self):
        last = _items.Item("c", "misquoted", None, "z", None, False, "s", {})
        missing = _items.Item("m", "missing-citekey", None, "a", None, True, "s", {})
        assert [i.id for i in _order.sort([last, missing])] == ["m", "c"]

    def test_severity_outranks_position_within_a_class(self):
        weak_early = _items.Item(
            "w", "unsupported-claim", None, None, 1, False, "s", {"band": "weak"}
        )
        no_support_late = _items.Item(
            "n", "unsupported-claim", None, None, 99, False, "s", {"band": "no support found"}
        )
        assert [i.id for i in _order.sort([weak_early, no_support_late])] == ["n", "w"]

    def test_line_tiebreak_then_id(self):
        first = _items.Item("aaa", "prose", None, None, 5, False, "s", {})
        second = _items.Item("bbb", "prose", None, None, 5, False, "s", {})
        assert [i.id for i in _order.sort([second, first])] == ["aaa", "bbb"]

    def test_misquoted_sorts_after_uncited_claim(self):
        misquoted = _items.Item("m", "misquoted", None, "a", None, False, "s", {})
        uncited_claim = _items.Item("u", "uncited-claim", None, None, 1, False, "s", {})
        ordered = [i.cls for i in _order.sort([misquoted, uncited_claim])]
        assert ordered == ["uncited-claim", "misquoted"]

    def test_claim_support_sits_between_unsupported_claim_and_uncited_claim(self):
        uncited_claim = _items.Item("s", "uncited-claim", None, "z", 9, False, "s", {})
        claim_support = _items.Item("cs", "claim-support", None, "a", 1, False, "s", {"score": 0.2})
        unsupported_claim = _items.Item(
            "uc", "unsupported-claim", None, None, 1, False, "s", {"band": "weak"}
        )
        ordered = [i.cls for i in _order.sort([uncited_claim, claim_support, unsupported_claim])]
        assert ordered == ["unsupported-claim", "claim-support", "uncited-claim"]

    def test_unpositioned_items_order_by_citekey(self):
        """`line is None` collapses to the same sort position for every
        item in the class, so citekey is what actually separates them --
        the property `misquoted` and `recorded-but-uncited` both rely on
        now that `candidate`, which used to demonstrate it, is gone."""
        z = _items.Item("z-id", "misquoted", None, "z2024", None, False, "s", {})
        a = _items.Item("a-id", "misquoted", None, "a2024", None, False, "s", {})
        assert [i.citekey for i in _order.sort([z, a])] == ["a2024", "z2024"]


# --------------------------------------------------------------------------
# _render.py
# --------------------------------------------------------------------------


class TestRenderMarkdown:
    def test_empty_agenda_says_so(self):
        rendered = _render.render_markdown(
            agenda.Agenda(
                draft=Path("content/drafts/t/survey.md"), sources=_sources_stub(), items=[]
            ),
            "python -m chitragupta.review agenda content/drafts/t/survey.md",
        )
        assert "No items" in rendered

    def test_support_is_named_in_the_sources_header(self):
        """#427: `support` is one of the aids `agenda` reads
        (`_sources.AID_NAMES`), and every aid it reads gets its own
        Sources line -- `_render._SOURCE_LABELS` has to name it too, or
        the header silently drops the one aid `--baseline` pays the most
        to refresh."""
        rendered = _render.render_markdown(
            agenda.Agenda(
                draft=Path("content/drafts/t/survey.md"), sources=_sources_stub(), items=[]
            ),
            "cmd",
        )
        assert "Claim support" in rendered

    def test_absent_stale_and_partial_sources_are_all_named(self):
        sources = _sources_stub(
            aids={
                "provenance": _sources.AidSource(available=True, stale=True, data={"findings": []}),
                "synthesis": _sources.AidSource(available=True, data={"findings": []}),
            },
            style=_sources.StyleSource(available=True, partial=True, data={"findings": []}),
            drift=_sources.DriftSource(available=True, corpus_available=False),
        )
        rendered = _render.render_markdown(
            agenda.Agenda(draft=Path("content/drafts/t/survey.md"), sources=sources, items=[]),
            "cmd",
        )
        assert "not run" in rendered  # verbatim etc, never read
        assert "**stale**" in rendered
        assert "no item class defined" in rendered
        assert "vale not on PATH" in rendered
        assert "corpus ledger is unavailable" in rendered

    def test_an_unavailable_source_with_a_reason_names_it(self):
        """A truncated aid sidecar (#496) degrades to unavailable with a
        reason -- the header should say why it was not read rather than
        the bare "not run" a genuinely missing file gets."""
        sources = _sources_stub(
            aids={
                "provenance": _sources.AidSource(
                    reason="content/review/t/survey.provenance.json: bad JSON"
                ),
            }
        )
        rendered = _render.render_markdown(
            agenda.Agenda(draft=Path("content/drafts/t/survey.md"), sources=sources, items=[]),
            "cmd",
        )
        assert "not run -- content/review/t/survey.provenance.json: bad JSON" in rendered

    def _rendered(self, source) -> str:
        sources = _sources_stub(aids={"quotation": source})
        return _render.render_markdown(
            agenda.Agenda(draft=Path("content/drafts/t/survey.md"), sources=sources, items=[]),
            "cmd",
        )

    def test_a_raised_refresh_names_its_reason_beside_not_refreshed(self):
        """#893: the earlier `.json` was read, the refresh raised -- the
        header says both, and why."""
        rendered = self._rendered(
            _sources.AidSource(
                available=True, data={}, refreshed=False, refresh_error="ValueError: bad page"
            )
        )
        assert (
            "**not refreshed** (raised: ValueError: bad page; an earlier run's findings; "
            "not counted)" in rendered
        )

    def test_a_raised_refresh_with_no_earlier_report_is_not_called_not_run(self):
        """`not run` would be false: the aid ran, and raised. With no
        earlier `.json` there are no findings to call an earlier run's."""
        rendered = self._rendered(
            _sources.AidSource(refreshed=False, refresh_error="ValueError: bad page")
        )
        assert "Quotation integrity: **not refreshed** -- raised: ValueError: bad page" in rendered
        assert "Quotation integrity: not run" not in rendered

    def test_an_unreadable_report_and_a_raised_refresh_are_both_named(self):
        rendered = self._rendered(
            _sources.AidSource(
                reason="survey.quotation.json: bad JSON",
                refreshed=False,
                refresh_error="ValueError: bad page",
            )
        )
        assert (
            "**not refreshed** -- raised: ValueError: bad page "
            "(and the earlier report is unreadable: survey.quotation.json: bad JSON)" in rendered
        )

    def test_a_refresh_that_failed_without_raising_keeps_its_wording(self):
        rendered = self._rendered(_sources.AidSource(available=True, data={}, refreshed=False))
        assert "**not refreshed** (an earlier run's findings; not counted)" in rendered
        assert "raised" not in rendered

    def test_no_dossier_is_named(self):
        rendered = _render.render_markdown(
            agenda.Agenda(
                draft=Path("content/drafts/t/survey.md"), sources=_sources_stub(), items=[]
            ),
            "cmd",
        )
        assert "no dossier for this draft" in rendered

    def test_fully_available_drift_is_named(self):
        sources = _sources_stub(drift=_sources.DriftSource(available=True, corpus_available=True))
        rendered = _render.render_markdown(
            agenda.Agenda(draft=Path("content/drafts/t/survey.md"), sources=sources, items=[]),
            "cmd",
        )
        assert "- Dossier drift: read" in rendered


class TestVerbatimPassageInTheAgenda:
    """A `verbatim-run` item carries the overlapping text under it.

    The passage is joined from the verbatim aid's *filed JSON* through
    `agenda.sources`, never from `item.detail` -- which stays thin by a
    documented decision, and whose whole contract is "look the id up in
    the raising aid's own report". This does exactly that.
    """

    def _rendered(self, finding, item_detail=None):
        item = _items.Item(
            "v1",
            "verbatim-run",
            "Intro",
            finding.get("citekey"),
            5,
            True,
            "9-word skip-gram match",
            item_detail if item_detail is not None else {"verbatim_id": finding.get("id")},
        )
        sources = _sources_stub(
            aids={"verbatim": _sources.AidSource(available=True, data={"findings": [finding]})}
        )
        return _render.render_markdown(
            agenda.Agenda(draft=Path("content/drafts/t/survey.md"), sources=sources, items=[item]),
            "cmd",
        )

    def _finding(self, **overrides):
        base = {
            "id": "abc123",
            "citekey": "a2024",
            "fragment": "the draft s own wording here",
            "source_text": None,
            "page": 7,
            "end_page": 7,
            "line": 35,
            "paragraph": 4,
            "end_paragraph": 4,
        }
        base.update(overrides)
        return base

    def test_the_json_payload_carries_the_same_locators_as_the_markdown(self):
        """Joined from the aid's filed JSON in both forms, so the two
        cannot disagree about where a finding is."""
        finding = self._finding()
        item = _items.Item(
            "v1", "verbatim-run", "Intro", "a2024", 5, True, "s", {"verbatim_id": "abc123"}
        )
        sources = _sources_stub(
            aids={"verbatim": _sources.AidSource(available=True, data={"findings": [finding]})}
        )
        built = agenda.Agenda(
            draft=Path("content/drafts/t/survey.md"), sources=sources, items=[item]
        )

        published = _render.agenda_payload(built, "cmd")["items"][0]

        assert (published["page"], published["end_page"]) == (7, 7)
        assert (published["paragraph"], published["end_paragraph"]) == (4, 4)

    def test_a_class_with_no_such_locator_publishes_the_keys_as_null(self):
        """Present rather than absent, so `prose` and `verbatim-run`
        items do not have different key sets and a consumer reading these
        positionally sees a stable shape."""
        item = _items.Item("p1", "prose", None, None, 1, True, "s", {})
        built = agenda.Agenda(
            draft=Path("content/drafts/t/survey.md"), sources=_sources_stub(), items=[item]
        )

        published = _render.agenda_payload(built, "cmd")["items"][0]

        assert published["page"] is None
        assert published["paragraph"] is None

    def test_the_locator_names_the_source_page_and_the_draft_position(self):
        """The aid's own report has carried `p.N` since it was written and
        the agenda never did -- an item said which paper and how many
        words and left the reader to open the aid's report for the only
        numbers that say where to look."""
        rendered = self._rendered(self._finding())
        assert "source p.7, draft line 35, paragraph 4" in rendered

    def test_a_run_spanning_pages_and_paragraphs_reports_both_ranges(self):
        rendered = self._rendered(self._finding(end_page=8, end_paragraph=5))
        assert "source p.7-8, draft line 35, paragraphs 4-5" in rendered

    def test_a_finding_filed_before_the_locators_existed_omits_them(self):
        """The bare agenda reads reports off disk, so a `.json` written by
        an earlier release has no `paragraph` key. The passage still
        prints; the locator names only what it actually knows."""
        finding = self._finding()
        del finding["paragraph"]
        del finding["end_paragraph"]
        del finding["page"]
        del finding["end_page"]
        rendered = self._rendered(finding)
        assert "draft line 35" in rendered
        assert "paragraph" not in rendered
        assert "source p." not in rendered
        assert "the draft s own wording here" in rendered

    def test_a_finding_with_no_locators_at_all_still_prints_its_passage(self):
        finding = self._finding()
        for key in ("page", "end_page", "line", "paragraph", "end_paragraph"):
            del finding[key]
        rendered = self._rendered(finding)
        assert "the draft s own wording here" in rendered

    def test_an_exact_finding_shows_one_passage(self):
        rendered = self._rendered(self._finding())
        assert "    > the draft s own wording here" in rendered
        assert "**source**" not in rendered

    def test_a_two_sided_finding_shows_both_marked_up(self):
        rendered = self._rendered(
            self._finding(fragment="the cat sat down", source_text="The dog sat down")
        )
        assert "**draft** -- the **cat** sat down" in rendered
        assert "**source** -- The **dog** sat down" in rendered

    def test_the_passage_is_indented_under_its_bullet(self):
        """A `>` placed flush left directly under a `- ...` bullet is not
        a blockquote inside the item -- Markdown reads it as lazy
        continuation, and it renders beside the item instead of within
        it. This is the same failure that lost every class heading but
        the first, and it is invisible in the `.md` source."""
        rendered = self._rendered(self._finding())
        quotes = [ln for ln in rendered.splitlines() if ln.lstrip().startswith(">")]
        passage = [ln for ln in quotes if "the draft s own wording" in ln]
        assert passage and all(ln.startswith("    ") for ln in passage)

    def test_a_newline_in_the_source_stays_inside_the_blockquote(self):
        rendered = self._rendered(self._finding(fragment="a b c", source_text="a\nb\n\nc"))
        assert len([ln for ln in rendered.splitlines() if "**source**" in ln]) == 1

    def test_no_passage_when_the_aids_report_lacks_the_id(self):
        """The bare agenda *reads* reports rather than running them, so a
        `.json` older than the item list can genuinely lack an id. The
        item still prints; only its passage is omitted."""
        rendered = self._rendered(self._finding(), item_detail={"verbatim_id": "not-in-report"})
        assert "`v1`" in rendered
        assert "the draft s own wording" not in rendered

    def test_no_passage_when_the_item_carries_no_id(self):
        rendered = self._rendered(self._finding(), item_detail={})
        assert "the draft s own wording" not in rendered

    def test_no_passage_when_the_aid_is_unavailable(self):
        item = _items.Item(
            "v1", "verbatim-run", None, "a2024", 5, True, "s", {"verbatim_id": "abc123"}
        )
        rendered = _render.render_markdown(
            agenda.Agenda(
                draft=Path("content/drafts/t/survey.md"),
                sources=_sources_stub(),
                items=[item],
            ),
            "cmd",
        )
        assert "`v1`" in rendered

    def test_a_finding_with_no_fragment_is_skipped(self):
        rendered = self._rendered(self._finding(fragment=""))
        assert "    >" not in rendered

    def test_other_classes_carry_no_passage(self):
        item = _items.Item("p1", "prose", None, None, 1, True, "a prose finding", {})
        rendered = _render.render_markdown(
            agenda.Agenda(
                draft=Path("content/drafts/t/survey.md"),
                sources=_sources_stub(),
                items=[item],
            ),
            "cmd",
        )
        assert "    >" not in rendered


class TestRenderMarkdownGrouping:
    def test_findings_grouped_by_class_then_severity(self):
        items = _order.sort(
            [
                _items.Item(
                    "m1", "missing-citekey", "Intro", "a2024", None, True, "missing a2024", {}
                ),
                _items.Item(
                    "m2", "missing-citekey", "Intro", "b2024", None, True, "missing b2024", {}
                ),
                _items.Item("c1", "misquoted", None, "b2024", None, False, "misquoted b2024", {}),
            ]
        )
        rendered = _render.render_markdown(
            agenda.Agenda(
                draft=Path("content/drafts/t/survey.md"), sources=_sources_stub(), items=items
            ),
            "cmd",
        )
        assert "### missing-citekey" in rendered
        assert "### misquoted" in rendered
        assert rendered.count("### missing-citekey") == 1
        assert rendered.index("### missing-citekey") < rendered.index("### misquoted")
        # A `###` line directly under a `- ...` bullet is lazy
        # continuation in Markdown, not a heading -- so every class
        # heading after the first needs a blank line before it or it is
        # swallowed into the last item of the class above, and the
        # rendered PDF shows no heading there at all.
        lines = rendered.splitlines()
        for index, line in enumerate(lines):
            if line.startswith("### ") and index:
                assert lines[index - 1] == "", f"{line!r} follows {lines[index - 1]!r}"
        assert "[unattended]" in rendered
        assert "[surfaced]" in rendered
        assert "(Intro)" in rendered


class TestAgendaPayload:
    def test_items_match_render_one_for_one(self):
        items = [
            _items.Item(
                "m1",
                "missing-citekey",
                "Intro",
                "a2024",
                None,
                True,
                "missing a2024",
                {"sections": ["Intro"]},
            ),
        ]
        payload = _render.agenda_payload(
            agenda.Agenda(
                draft=Path("content/drafts/t/survey.md"), sources=_sources_stub(), items=items
            ),
            "cmd",
        )
        assert payload["items"] == [
            {
                "id": "m1",
                "class": "missing-citekey",
                "section": "Intro",
                "citekey": "a2024",
                "line": None,
                "page": None,
                "end_page": None,
                "paragraph": None,
                "end_paragraph": None,
                "unattended": True,
                "summary": "missing a2024",
                "detail": {"sections": ["Intro"]},
            }
        ]
        assert payload["notice"]
        assert payload["aid"] == "agenda"
        assert set(payload["sources"]["aids"]) == set(_sources.AID_NAMES)

    def test_the_payload_carries_the_bound_and_the_count(self):
        """Neither is reachable from a `SKILL.md`: `PASS_BOUND` is a Python
        constant and `objective_class_count` a property, so a skill that
        could not read them off the payload would hardcode `3` in prose --
        which is what `plans/f-auto-improvement-adoption.md`'s Decision 2
        forbids, and for the reason it gives."""
        items = [
            _items.Item("m1", "missing-citekey", None, "a2024", None, True, "s", {}),
            _items.Item("p1", "prose", None, None, 3, True, "s", {}),
            _items.Item("c1", "candidate", None, "b2024", None, False, "s", {}),
        ]
        payload = _render.agenda_payload(
            agenda.Agenda(
                draft=Path("content/drafts/t/survey.md"), sources=_sources_stub(), items=items
            ),
            "cmd",
        )
        assert payload["pass_bound"] == agenda.PASS_BOUND
        assert payload["objective_class_count"] == 2

    def test_the_serialised_count_is_the_computed_one(self):
        """An additional serialisation, never a second computation -- the
        rule `agenda_payload`'s own docstring states."""
        items = [
            _items.Item("p1", "prose", None, None, 3, True, "s", {}),
            _items.Item("p2", "prose", None, None, 4, True, "s", {}),
        ]
        built = agenda.Agenda(
            draft=Path("content/drafts/t/survey.md"), sources=_sources_stub(), items=items
        )
        payload = _render.agenda_payload(built, "cmd")
        assert payload["objective_class_count"] == built.objective_class_count


# --------------------------------------------------------------------------
# _stale.py
# --------------------------------------------------------------------------


class TestStalePartition:
    """#766: an item whose draft span is gone is dropped and reported,
    never relocated onto whatever now occupies that position."""

    def test_an_item_whose_span_is_still_present_is_kept(self):
        item = _items.Item(
            "v1", "verbatim-run", "Intro", "a2024", 3, True, "s", {}, span="a borrowed run"
        )
        live, refused = _stale.partition("# Survey\n\nHere is a borrowed run.\n", [item])
        assert live == [item]
        assert refused == []

    def test_an_item_whose_span_has_changed_is_refused(self):
        item = _items.Item(
            "v1", "verbatim-run", "Intro", "a2024", 3, True, "s", {}, span="a borrowed run"
        )
        live, refused = _stale.partition("# Survey\n\nThe author rewrote this.\n", [item])
        assert live == []
        assert refused == [item]

    def test_an_item_with_no_draft_span_is_never_refused(self):
        """`missing-citekey`, `recorded-but-uncited` and `misquoted` are
        derived from the dossier, not the draft's text -- the second by
        construction names a citekey the draft does *not* cite, so a
        containment check would refuse it on every run."""
        item = _items.Item("m1", "missing-citekey", None, "a2024", None, True, "s", {})
        live, refused = _stale.partition("# Survey\n", [item])
        assert live == [item]
        assert refused == []

    def test_the_refusal_keeps_the_section_anchor(self):
        item = _items.Item("p1", "prose", "Methods", None, 7, True, "'AI' (1x)", {}, span="AI")
        _live, refused = _stale.partition("# Survey\n", [item])
        assert _stale.stale_dicts(refused) == [
            {
                "id": "p1",
                "class": "prose",
                "section": "Methods",
                "summary": "'AI' (1x)",
                "refused": "the draft text this finding was derived from is no longer present",
            }
        ]

    def test_nothing_refused_renders_no_section(self):
        assert _stale.stale_lines([]) == []

    def test_a_refusal_renders_with_its_anchor(self):
        item = _items.Item("p1", "prose", "Methods", None, 7, True, "'AI' (1x)", {}, span="AI")
        lines = _stale.stale_lines([item])
        assert "## Refused as stale" in lines
        assert any("`p1`" in line and "(Methods)" in line for line in lines)


class TestNoFuzzyRelocation:
    """#766's fourth criterion, checked rather than asserted in prose: a
    refusal that could be talked into a similarity score is not a
    refusal. Nothing in this package may import a fuzzy matcher, for the
    reason `docs/AUTO-IMPROVEMENT.md` already gives about the verbatim
    scan's embedding tier -- an edit authorised on the evidence of a
    score is exactly what the agenda refuses to do elsewhere."""

    FUZZY = ("difflib", "SequenceMatcher", "get_close_matches", "rapidfuzz", "Levenshtein")

    def test_the_skill_states_the_refusal(self):
        """The aid dropping the item protects a run that happens *after*
        the edit; the skill holds a baseline taken before it. Both halves
        are needed, so the skill's own prose is checked here rather than
        assumed -- #766's stated layer is "a rule in `agenda-reviser`,
        plus the staleness report in the aid's output"."""
        # Anchored on this test file, not on `agenda.__file__`: the
        # convention `tests/test_skill_style_check_step.py` already
        # follows, and the reason is that CI's test job does a real
        # project install, so a path walked up from the imported package
        # can land outside the checkout.
        repo_root = Path(__file__).resolve().parent.parent
        skill = (repo_root / ".claude" / "skills" / "agenda-reviser" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert "stale_spans" in skill
        assert "refused as stale" in skill.lower()
        assert "R12" in skill

    def test_the_agenda_package_imports_no_fuzzy_matcher(self):
        package = Path(agenda.__file__).parent
        offenders = {
            module.name: name
            for module in sorted(package.glob("*.py"))
            for name in self.FUZZY
            if name in module.read_text(encoding="utf-8")
        }
        assert offenders == {}


# --------------------------------------------------------------------------
# Agenda / CLI (chitragupta/review/agenda/__init__.py)
# --------------------------------------------------------------------------


class TestObjectiveClassCount:
    def test_counts_unattended_items_only(self):
        one = agenda.Agenda(
            draft=Path("d"),
            sources=_sources_stub(),
            items=[
                _items.Item("1", "missing-citekey", None, None, None, True, "s", {}),
                _items.Item("2", "candidate", None, None, None, False, "s", {}),
            ],
        )
        assert one.objective_class_count == 1

    def test_prose_counts_towards_it(self):
        """The flip in issue 421 makes `prose` the third contributor, and
        this is the number the re-run loop terminates on -- so it is
        asserted here rather than left to the flag's own test."""
        one = agenda.Agenda(
            draft=Path("d"),
            sources=_sources_stub(),
            items=[
                _items.Item("1", "missing-citekey", None, None, None, True, "s", {}),
                _items.Item("2", "prose", None, None, 3, True, "s", {}),
                _items.Item("3", "candidate", None, None, None, False, "s", {}),
            ],
        )
        assert one.objective_class_count == 2

    def test_a_not_refreshed_aids_items_do_not_count(self):
        """#837: the verbatim scan's refresh failed, so its `short` run is
        last run's evidence, not this draft's -- listed, never counted."""
        sources = _sources_stub(aids={"verbatim": _sources.AidSource(refreshed=False)})
        one = agenda.Agenda(
            draft=Path("d"),
            sources=sources,
            items=[
                _items.Item("1", "verbatim-run", None, None, 3, True, "s", {}),
                _items.Item("2", "prose", None, None, 3, True, "s", {}),
            ],
        )
        assert one.objective_class_count == 1
        assert sources.not_refreshed() == ["verbatim"]


class TestBuildAgendaAndCli:
    def _draft_with_no_dossier(self, isolated_config, monkeypatch):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n\nSome prose here.\n")
        monkeypatch.setattr(
            agenda._sources.style_check,
            "check",
            lambda d, override=None, propose=True: {"findings": [], "vale_error": None},
        )
        return draft

    def test_build_agenda_with_every_source_absent_is_empty(self, isolated_config, monkeypatch):
        draft = self._draft_with_no_dossier(isolated_config, monkeypatch)
        built = agenda.build_agenda(draft)
        assert built.items == []
        assert built.sources.drift.available is False

    def test_run_writes_md_tex_pdf_and_json(self, isolated_config, monkeypatch):
        draft = self._draft_with_no_dossier(isolated_config, monkeypatch)
        args = agenda.build_parser().parse_args([str(draft)])
        exit_code = agenda.run(args)
        assert exit_code == 0

        written = review.report_path(draft, "agenda", "md")
        assert written.is_file()
        json_path = review.report_path(draft, "agenda", "json")
        payload = json.loads(json_path.read_text())
        assert payload["aid"] == "agenda"
        assert payload["items"] == []

    def test_a_real_support_json_produces_a_claim_support_item_end_to_end(
        self, isolated_config, monkeypatch
    ):
        """#427, exercised through the real pipeline rather than a stubbed
        `AidSource`: a `.support.json` an earlier `review support --write`
        run left on disk should surface as a `claim-support` item in both
        the rendered Markdown and the JSON payload, unfiltered and
        carrying the not-a-verdict caveat."""
        draft = self._draft_with_no_dossier(isolated_config, monkeypatch)
        review.write_json(
            draft,
            "support",
            {
                "findings": [
                    {
                        "id": "f1",
                        "line": 1,
                        "citekey": "a2024",
                        "claim": "a claim",
                        "score": 0.12,
                        "note": None,
                    }
                ]
            },
        )

        built = agenda.build_agenda(draft)
        assert [item.cls for item in built.items] == ["claim-support"]
        assert "not a verdict" in built.items[0].summary

        rendered = _render.render_markdown(built, "cmd")
        assert "### claim-support" in rendered
        assert "not a verdict" in rendered

        payload = _render.agenda_payload(built, "cmd")
        assert payload["items"][0]["class"] == "claim-support"

    def test_no_write_flag_exists(self):
        parser = agenda.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["draft.md", "--write"])

    def test_json_flag_prints_payload_to_stdout(
        self, isolated_config, monkeypatch, capsys, aid_stubs
    ):
        draft = self._draft_with_no_dossier(isolated_config, monkeypatch)
        exit_code = agenda.main([str(draft), "--json"])
        assert exit_code == 0
        out = capsys.readouterr()
        payload = json.loads(out.out)
        assert payload["aid"] == "agenda"
        assert "json" in out.err  # written-files summary moved to stderr
        # The bare command never runs an aid -- --baseline is the one mode
        # that does.
        assert all(stub.calls == [] for stub in aid_stubs.values())

    def test_missing_draft_exits_one(self, isolated_config, capsys):
        exit_code = agenda.main(["content/drafts/nope.md"])
        assert exit_code == 1

    def test_two_runs_over_unchanged_input_are_byte_identical(self, isolated_config, monkeypatch):
        draft = self._draft_with_no_dossier(isolated_config, monkeypatch)
        args = agenda.build_parser().parse_args([str(draft)])
        agenda.run(args)
        json_path = review.report_path(draft, "agenda", "json")
        first = json_path.read_bytes()

        agenda.run(args)
        second = json_path.read_bytes()
        assert first == second

    def test_an_edit_between_the_aid_run_and_the_reviser_refuses_the_item(
        self, isolated_config, monkeypatch
    ):
        """#766, the whole window in one test: the aid runs, the human
        revises the very passage it found, and the next agenda drops the
        item rather than handing a reviser a repair aimed at text that is
        gone. The human's draft survives byte for byte -- `agenda` never
        writes a draft, so that assertion is the floor; the load-bearing
        ones are that the item left `items`, left the objective count, and
        is reported with its section anchor instead."""
        draft = self._draft_with_no_dossier(isolated_config, monkeypatch)
        draft.write_text("# Survey\n\n## Intro\n\nWidely regarded as the standard.\n")
        review.write_json(
            draft,
            "verbatim",
            {
                "findings": [
                    {
                        "id": "v1",
                        "line": 5,
                        "severity": "short",
                        "tier": "exact",
                        "citekey": "a2024",
                        "span_words": 6,
                        "matched_words": 6,
                        "fragment": "Widely regarded as the standard",
                        "draft_text": "Widely regarded as the standard",
                    }
                ]
            },
        )
        before = agenda.build_agenda(draft)
        assert [item.cls for item in before.items] == ["verbatim-run"]
        assert before.objective_class_count == 1
        assert before.stale == []

        revised = "# Survey\n\n## Intro\n\nMost practitioners reach for it first.\n"
        draft.write_text(revised)
        after = agenda.build_agenda(draft)

        assert after.items == []
        assert after.objective_class_count == 0
        assert [item.id for item in after.stale] == [before.items[0].id]
        assert after.stale[0].section == "Intro"

        payload = _render.agenda_payload(after, "cmd")
        assert payload["stale_spans"] == [
            {
                "id": before.items[0].id,
                "class": "verbatim-run",
                "section": "Intro",
                "summary": before.items[0].summary,
                "refused": "the draft text this finding was derived from is no longer present",
            }
        ]
        assert "## Refused as stale" in _render.render_markdown(after, "cmd")
        assert draft.read_text(encoding="utf-8") == revised

    def test_a_present_aid_json_produces_a_worklist_item(self, isolated_config, monkeypatch):
        draft = self._draft_with_no_dossier(isolated_config, monkeypatch)
        review.write_json(
            draft,
            "uncited",
            {
                "findings": [
                    {"id": "1", "line": 1, "sentence": "A bare claim.", "block_cites": False}
                ]
            },
        )
        built = agenda.build_agenda(draft)
        assert len(built.items) == 1
        assert built.items[0].cls == "uncited-claim"


# --------------------------------------------------------------------------
# _recheck.py -- the `--baseline` refresh mode (F3 Decision 6)
# --------------------------------------------------------------------------


def _item_dict(id_, cls="prose", unattended=True, summary="a finding") -> dict:
    """One `_render._item_dict`-shaped item, which is what both sides of
    `compare` are made of."""
    return {
        "id": id_,
        "class": cls,
        "section": None,
        "citekey": None,
        "line": None,
        "unattended": unattended,
        "summary": summary,
        "detail": {},
    }


class _AidStub:
    """Stands in for one aid module's `main`, recording the argv it was
    handed and optionally printing, so the stdout-capture requirement can
    be tested against something that actually pollutes stdout.

    By default it also files an empty `<stem>.<aid>.json`, which is what
    a real aid's successful refresh leaves behind and what `refresh_aids`
    checks for (#837): a stub that wrote nothing would read as a refresh
    that did not happen. `returncode` and `writes` are the two ways a
    real refresh fails -- a refusal, and `claim_support`'s exit 0 with no
    entailer installed. `raises` is the third (#893): an aid that
    raises, after any write, instead of returning at all.
    """

    def __init__(self, aid: str = "", chatter: str = "", returncode: int = 0, writes: bool = True):
        self.calls: list[list[str]] = []
        self.aid = aid
        self.chatter = chatter
        self.returncode = returncode
        self.writes = writes
        self.raises: BaseException | None = None
        # What a successful refresh files; a test that needs the aid to
        # re-find what an earlier run found sets it to that payload.
        self.payload: dict = {"findings": []}

    def __call__(self, argv):
        self.calls.append(list(argv))
        if self.chatter:
            print(self.chatter)
        if self.writes and self.aid:
            # `verbatim` is the one aid called through a subcommand.
            draft = Path(argv[1] if argv[0] == "scan" else argv[0])
            review.write_json(draft, self.aid, self.payload)
        if self.raises is not None:
            raise self.raises
        return self.returncode


@pytest.fixture
def aid_stubs(monkeypatch):
    """Every one of the eight aids' `main` replaced by a recorder.

    `refresh_aids` is tested against *what it calls*, never against real
    aid behaviour: the real eight need the enrich stack, a real corpus
    and real dossiers, none of which a unit test should depend on.
    """
    stubs = {}
    for name in _sources.AID_NAMES:
        module = _registry.AIDS[name][0]
        stub = _AidStub(name)
        monkeypatch.setattr(module, "main", stub)
        stubs[name] = stub
    return stubs


class TestOneRegistry:
    """#850: the aids are named once, in `review.AIDS`, and mapped to
    their modules once, in `review._registry.AIDS`. `_sources.AID_NAMES`,
    `_render._SOURCE_LABELS` and `_refresh`'s module map were each a
    hand-kept copy that adding an aid had to edit; each is now derived."""

    def test_no_agenda_module_restates_the_aid_list(self):
        """A dict or tuple literal naming three or more aids is a copy of
        the registry, whatever it is called."""
        names = set(review.AIDS)
        offenders = []
        for path in sorted(Path(_sources.__file__).parent.glob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                items = node.keys if isinstance(node, ast.Dict) else getattr(node, "elts", [])
                if not isinstance(node, (ast.Dict, ast.Tuple, ast.List, ast.Set)):
                    continue
                named = {i.value for i in items if isinstance(i, ast.Constant)} & names
                if len(named) >= 3:
                    offenders.append(f"{path.name}:{node.lineno}")
        assert offenders == [], f"restated aid registry at {offenders}"

    def test_refresh_runs_each_aid_through_the_registry_module(self):
        assert not hasattr(_refresh, "_AID_MODULES")
        assert all(name in _registry.AIDS for name in _sources.AID_NAMES)


class TestCoverageQueries:
    def test_draft_outside_the_drafts_dir_has_none(self, isolated_config):
        draft = content_draft(isolated_config, "elsewhere/survey.md")
        draft.write_text("# S\n")
        assert _refresh._coverage_queries(draft) == []

    def test_draft_with_no_dossier_directory_has_none(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# S\n")
        assert _refresh._coverage_queries(draft) == []

    def test_dossier_with_no_retrieval_rows_has_none(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# S\n")
        dossier.dossier_dir(draft).mkdir(parents=True)
        assert _refresh._coverage_queries(draft) == []

    def test_only_revision_markers_yields_none(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# S\n")
        _retrieval.mark_revision(draft, "shorten intro")
        assert _refresh._coverage_queries(draft) == []

    def test_recorded_queries_come_back_first_seen_first(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# S\n")
        dossier.log_retrieval(draft, "draft", "digital twin", 5, 3, 100)
        dossier.log_retrieval(draft, "draft", "co-simulation", 5, 2, 90)
        assert _refresh._coverage_queries(draft) == ["digital twin", "co-simulation"]


class TestRefreshAids:
    def _draft(self, isolated_config) -> Path:
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n\nSome prose.\n")
        return draft

    def test_every_aid_is_called_once(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        dossier.log_retrieval(draft, "draft", "digital twin", 5, 3, 100)
        _refresh.refresh_aids(draft)
        assert {name: len(stub.calls) for name, stub in aid_stubs.items()} == {
            name: 1 for name in _sources.AID_NAMES
        }

    def test_every_argv_parses_against_that_aids_real_parser(self, isolated_config, aid_stubs):
        """The stubs cannot catch an argv the real parser rejects -- the
        `--write`-on-provenance mistake is exactly that shape -- so each
        recorded argv is replayed through the aid's own `build_parser`."""
        draft = self._draft(isolated_config)
        dossier.log_retrieval(draft, "draft", "digital twin", 5, 3, 100)
        _refresh.refresh_aids(draft)
        for name, stub in aid_stubs.items():
            parsed = _registry.AIDS[name][0].build_parser().parse_args(stub.calls[0])
            assert parsed.formats == "md"
            assert getattr(parsed, "write", True) is True

    def test_provenance_is_called_without_write(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        _refresh.refresh_aids(draft)
        argv = aid_stubs["provenance"].calls[0]
        assert argv == [str(draft), "--formats", "md"]
        with pytest.raises(SystemExit):
            citation_provenance.build_parser().parse_args([*argv, "--write"])

    def test_verbatim_is_called_as_the_scan_subcommand(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        _refresh.refresh_aids(draft)
        assert aid_stubs["verbatim"].calls[0] == [
            "scan",
            str(draft),
            "--write",
            "--formats",
            "md",
        ]

    def test_the_plain_five_are_called_with_write_and_formats_md(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        _refresh.refresh_aids(draft)
        for name in ("synthesis", "figure", "uncited", "quotation", "support"):
            assert aid_stubs[name].calls[0] == [str(draft), "--write", "--formats", "md"]

    def test_coverage_gets_one_query_flag_per_recorded_query(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        dossier.log_retrieval(draft, "draft", "digital twin", 5, 3, 100)
        dossier.log_retrieval(draft, "draft", "co-simulation", 5, 2, 90)
        _refresh.refresh_aids(draft)
        assert aid_stubs["coverage"].calls[0] == [
            str(draft),
            "--query",
            "digital twin",
            "--query",
            "co-simulation",
            "--write",
            "--formats",
            "md",
        ]

    def test_coverage_is_skipped_with_no_dossier(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        _refresh.refresh_aids(draft)
        assert aid_stubs["coverage"].calls == []
        assert aid_stubs["uncited"].calls  # the other seven still ran

    def test_coverage_is_skipped_with_a_dossier_but_no_rows(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        dossier.dossier_dir(draft).mkdir(parents=True)
        _refresh.refresh_aids(draft)
        assert aid_stubs["coverage"].calls == []

    def test_coverage_is_skipped_with_only_revision_markers(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        _retrieval.mark_revision(draft, "shorten intro")
        _refresh.refresh_aids(draft)
        assert aid_stubs["coverage"].calls == []

    def test_an_aids_own_stdout_is_swallowed(self, isolated_config, monkeypatch, capsys):
        draft = self._draft(isolated_config)
        for name in _sources.AID_NAMES:
            monkeypatch.setattr(
                _registry.AIDS[name][0], "main", _AidStub(name, chatter="WROTE A FILE")
            )
        _refresh.refresh_aids(draft)
        assert "WROTE A FILE" not in capsys.readouterr().out

    def test_a_full_refresh_reports_every_aid_refreshed(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        dossier.log_retrieval(draft, "draft", "digital twin", 5, 3, 100)
        assert _refresh.refresh_aids(draft) == (dict.fromkeys(_sources.AID_NAMES, True), {})

    def test_a_skipped_coverage_is_none_not_a_failure(self, isolated_config, aid_stubs):
        """No recorded query means nothing to refresh `coverage` with --
        by design, on every draft without a dossier, so it must not read
        as a failure every cycle."""
        draft = self._draft(isolated_config)
        refreshed, _ = _refresh.refresh_aids(draft)
        assert refreshed["coverage"] is None
        assert all(refreshed[aid] for aid in _sources.AID_NAMES if aid != "coverage")

    def test_a_nonzero_exit_is_not_refreshed(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        aid_stubs["verbatim"].returncode = 1
        aid_stubs["verbatim"].writes = False
        assert _refresh.refresh_aids(draft)[0]["verbatim"] is False

    def test_a_nonzero_exit_is_not_refreshed_even_if_it_wrote(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        aid_stubs["verbatim"].returncode = 1
        assert _refresh.refresh_aids(draft)[0]["verbatim"] is False

    def test_exit_zero_writing_nothing_over_an_old_sidecar_is_not_refreshed(
        self, isolated_config, aid_stubs
    ):
        """`claim_support` with no entailer installed: exit 0, nothing
        written, last run's `.json` left in place. The exit code alone
        would call that a refresh."""
        draft = self._draft(isolated_config)
        old = review.write_json(draft, "support", {"findings": []})
        os.utime(old, (1_000_000, 1_000_000))
        aid_stubs["support"].writes = False
        assert _refresh.refresh_aids(draft)[0]["support"] is False

    def test_exit_zero_writing_nothing_and_no_sidecar_is_not_refreshed(
        self, isolated_config, aid_stubs
    ):
        draft = self._draft(isolated_config)
        aid_stubs["support"].writes = False
        assert _refresh.refresh_aids(draft)[0]["support"] is False

    def test_rewriting_an_existing_sidecar_is_refreshed(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        old = review.write_json(draft, "support", {"findings": []})
        os.utime(old, (1_000_000, 1_000_000))
        assert _refresh.refresh_aids(draft)[0]["support"] is True

    def test_an_aid_that_raises_is_not_refreshed_and_the_rest_still_run(
        self, isolated_config, aid_stubs
    ):
        """#893: one aid raising must not take the recheck down with it --
        it is recorded with its one-line reason, and every later aid in
        `AID_NAMES` is still called."""
        draft = self._draft(isolated_config)
        aid_stubs["provenance"].raises = RuntimeError("boom\nsecond line")
        refreshed, errors = _refresh.refresh_aids(draft)
        assert refreshed["provenance"] is False
        assert errors == {"provenance": "RuntimeError: boom"}
        assert all(aid_stubs[aid].calls for aid in _sources.AID_NAMES if aid != "coverage")
        assert refreshed["verbatim"] is True

    def test_an_aid_that_wrote_and_then_raised_is_still_not_refreshed(
        self, isolated_config, aid_stubs
    ):
        """The mtime moved, but an aid that raised reported no result."""
        draft = self._draft(isolated_config)
        aid_stubs["support"].raises = OSError("disk went away")
        refreshed, errors = _refresh.refresh_aids(draft)
        assert review.report_path(draft, "support", "json").is_file()
        assert refreshed["support"] is False
        assert errors["support"] == "OSError: disk went away"

    def test_a_raise_with_no_message_is_named_by_its_type(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        aid_stubs["uncited"].raises = KeyError()
        assert _refresh.refresh_aids(draft)[1] == {"uncited": "KeyError"}

    @pytest.mark.parametrize("exc", [SystemExit(2), KeyboardInterrupt()], ids=["exit", "ctrl-c"])
    def test_an_argparse_exit_or_an_interrupt_still_propagates(
        self, isolated_config, aid_stubs, exc
    ):
        """`SystemExit(2)` is what a wrong argv from `_aid_argv` looks like
        -- this module's bug, which must stay loud -- and Ctrl-C must
        still stop the run."""
        draft = self._draft(isolated_config)
        aid_stubs["quotation"].raises = exc
        with pytest.raises(type(exc)):
            _refresh.refresh_aids(draft)

    def test_a_raise_is_warned_on_stderr_and_stdout_stays_clean(
        self, isolated_config, aid_stubs, capsys
    ):
        draft = self._draft(isolated_config)
        aid_stubs["quotation"].chatter = "WROTE A FILE"
        aid_stubs["quotation"].raises = ValueError("bad page")
        _refresh.refresh_aids(draft)
        out = capsys.readouterr()
        assert out.out == ""
        assert "[warn] quotation raised during refresh: ValueError: bad page" in out.err


class TestLoadBaseline:
    def test_an_agenda_payload_round_trips(self, tmp_path):
        path = tmp_path / "b.json"
        path.write_text(json.dumps({"aid": "agenda", "items": [_item_dict("a")]}))
        assert _recheck.load_baseline(path)["items"] == [_item_dict("a")]

    def test_an_unreadable_file_names_the_path(self, tmp_path):
        # `match` is a regex, and a Windows path's backslashes are not
        # literal there -- `\U`/`\A`/etc. are escapes `re` rejects outright
        # rather than matching literally. `re.escape` is what makes an
        # arbitrary path safe to use as a `match` pattern on any host.
        path = tmp_path / "nope.json"
        with pytest.raises(ValueError, match=re.escape(str(path))):
            _recheck.load_baseline(path)

    def test_not_json_at_all_is_refused(self, tmp_path):
        path = tmp_path / "b.json"
        path.write_text("not json")
        with pytest.raises(ValueError, match="not valid JSON"):
            _recheck.load_baseline(path)

    def test_another_aids_payload_is_refused(self, tmp_path):
        path = tmp_path / "b.json"
        path.write_text(json.dumps({"aid": "coverage", "items": []}))
        with pytest.raises(ValueError, match="not an agenda payload"):
            _recheck.load_baseline(path)

    def test_a_payload_with_no_items_key_is_refused(self, tmp_path):
        path = tmp_path / "b.json"
        path.write_text(json.dumps({"aid": "agenda"}))
        with pytest.raises(ValueError, match="not an agenda payload"):
            _recheck.load_baseline(path)

    def test_json_that_is_not_an_object_is_refused(self, tmp_path):
        path = tmp_path / "b.json"
        path.write_text(json.dumps(["agenda"]))
        with pytest.raises(ValueError, match="not an agenda payload"):
            _recheck.load_baseline(path)


class TestCompare:
    def test_an_item_in_both_persists(self):
        both = [_item_dict("a")]
        resolved, persisting, new, accepted, _, _ = _recheck.compare(both, both)
        assert (resolved, persisting, new, accepted) == ([], both, [], [])

    def test_an_item_only_in_the_baseline_is_resolved(self):
        before = [_item_dict("a")]
        resolved, persisting, new, accepted, _, _ = _recheck.compare([], before)
        assert (resolved, persisting, new, accepted) == (before, [], [], [])

    def test_an_item_only_in_the_new_list_is_new(self):
        after = [_item_dict("a")]
        resolved, persisting, new, accepted, _, _ = _recheck.compare(after, [])
        assert (resolved, persisting, new, accepted) == ([], [], after, [])

    def test_an_accepted_item_is_not_reported_resolved(self):
        """Suppression removes it from the new list, so plain set
        difference would call a finding nobody repaired fixed."""
        before = [_item_dict("a", cls="uncited-claim", unattended=False)]
        resolved, _, _, accepted, _, _ = _recheck.compare([], before, {"a"})
        assert (resolved, accepted) == ([], before)

    def test_an_item_that_really_went_away_is_still_resolved(self):
        """Only the ids this run actually suppressed are passed in, so an
        accepted item whose span was edited -- and which therefore no
        longer matches anything -- reports as the repair it was."""
        before = [_item_dict("a")]
        resolved, _, _, accepted, _, _ = _recheck.compare([], before, set())
        assert (resolved, accepted) == (before, [])

    def test_objective_counts_fall_when_an_unattended_item_is_repaired(self):
        *_, before, after = _recheck.compare([], [_item_dict("a"), _item_dict("b")])
        assert (before, after) == (2, 0)

    def test_objective_counts_rise_when_an_unattended_item_appears(self):
        *_, before, after = _recheck.compare([_item_dict("a"), _item_dict("b")], [_item_dict("a")])
        assert (before, after) == (1, 2)

    def test_objective_counts_stay_flat_when_nothing_unattended_moved(self):
        surfaced = _item_dict("s", cls="candidate", unattended=False)
        *_, before, after = _recheck.compare([_item_dict("a"), surfaced], [_item_dict("a")])
        assert (before, after) == (1, 1)

    def test_surfaced_items_are_never_objective(self):
        surfaced = [_item_dict("s", cls="candidate", unattended=False)]
        *_, before, after = _recheck.compare(surfaced, surfaced)
        assert (before, after) == (0, 0)

    def test_an_unverified_aids_items_are_in_no_group_and_no_count(self):
        """#837: an aid that was not refreshed contributes no evidence
        about the current draft, so its items neither persist, resolve
        nor appear -- and are counted on neither side, or the delta would
        fall for an aid that merely failed to run."""
        run = _item_dict("v", cls="verbatim-run")
        gone = _item_dict("w", cls="verbatim-run")
        new = _item_dict("x", cls="verbatim-run")
        kept = _item_dict("p")
        resolved, persisting, appeared, accepted, before, after = _recheck.compare(
            [run, new, kept], [run, gone, kept], set(), {"verbatim"}
        )
        assert (resolved, persisting, appeared, accepted) == ([], [kept], [], [])
        assert (before, after) == (1, 1)

    def test_an_unverified_aid_leaves_other_classes_alone(self):
        run = _item_dict("v", cls="verbatim-run")
        *_, before, after = _recheck.compare([run], [run], set(), {"support"})
        assert (before, after) == (1, 1)


class TestNotRefreshed:
    def test_an_agenda_payload_names_the_aids_marked_not_refreshed(self):
        payload = {
            "sources": {
                "aids": {
                    "verbatim": {"refreshed": False},
                    "support": {"refreshed": None},
                    "uncited": {"refreshed": True},
                }
            }
        }
        assert _recheck.not_refreshed(payload) == ["verbatim"]

    def test_a_payload_without_refresh_state_names_none(self):
        """Older baselines and hand-written ones carry no `sources` at
        all; neither is evidence that any aid failed."""
        assert _recheck.not_refreshed({"aid": "agenda", "items": []}) == []
        assert _recheck.not_refreshed({"sources": {"aids": {"verbatim": {}}}}) == []

    def test_an_agenda_payload_names_each_raised_aids_reason(self):
        payload = {
            "sources": {
                "aids": {
                    "verbatim": {"refreshed": False, "refresh_error": "OSError: gone"},
                    "support": {"refreshed": False, "refresh_error": None},
                    "uncited": {"refreshed": True},
                }
            }
        }
        assert _recheck.refresh_errors(payload) == {"verbatim": "OSError: gone"}

    def test_a_payload_from_an_older_release_names_no_errors(self):
        assert _recheck.refresh_errors({"aid": "agenda", "items": []}) == {}
        assert _recheck.refresh_errors({"sources": {"aids": {"verbatim": {}}}}) == {}


class TestClassAids:
    def test_every_mapped_class_is_a_real_class_raised_by_a_real_aid(self):
        assert set(_sources.CLASS_AIDS) <= set(_items.CLASSES)
        assert set(_sources.CLASS_AIDS.values()) <= set(_sources.AID_NAMES)

    def test_the_in_process_classes_are_never_unverified(self):
        """`missing-citekey`, `recorded-but-uncited` and `prose` are
        computed in-process every run, so no refresh failure can make
        them stale."""
        assert not {"missing-citekey", "recorded-but-uncited", "prose"} & set(_sources.CLASS_AIDS)

    def test_unverified_classes_follows_the_map(self):
        assert _sources.unverified_classes(["verbatim"]) == {"verbatim-run"}
        assert _sources.unverified_classes([]) == set()


class TestRecheckPayloadAndText:
    def _groups(self):
        return (
            [_item_dict("r")],
            [_item_dict("p")],
            [_item_dict("n")],
            [_item_dict("a", cls="uncited-claim", unattended=False)],
        )

    def test_command_reproduces_the_invocation(self):
        # A plain string, not `Path(...)`: `str(Path(...))` normalises to
        # the host's own separator, and `shlex.join` quotes a backslash --
        # a literal string keeps this assertion identical on every host,
        # the same convention `test_verbatim_check.py`'s own command-string
        # tests already use.
        assert _recheck.recheck_command("content/drafts/t/s.md", "b.json") == (
            "python -m chitragupta.review agenda content/drafts/t/s.md --baseline b.json --json"
        )

    def test_payload_carries_the_envelope_the_groups_and_the_delta(self):
        payload = _recheck.recheck_payload(
            Path("content/drafts/t/s.md"), "b.json", self._groups(), (3, 1), []
        )
        assert payload["aid"] == "agenda"
        assert payload["notice"]
        assert payload["command"] == _recheck.recheck_command(
            Path("content/drafts/t/s.md"), "b.json"
        )
        assert payload["not_refreshed"] == []
        assert payload["baseline"] == "b.json"
        assert payload["objective_before"] == 3
        assert payload["objective_after"] == 1
        assert payload["objective_delta"] == -2
        assert payload["resolved"] == [_item_dict("r")]
        assert payload["persisting"] == [_item_dict("p")]
        assert payload["new"] == [_item_dict("n")]
        assert payload["accepted"] == [_item_dict("a", cls="uncited-claim", unattended=False)]

    def test_a_rising_count_gives_a_positive_delta(self):
        payload = _recheck.recheck_payload(
            Path("content/drafts/t/s.md"), "b.json", self._groups(), (1, 4), []
        )
        assert payload["objective_delta"] == 3

    def test_text_names_every_group_and_the_objective_line(self):
        text = _recheck.format_recheck("b.json", self._groups(), (3, 1))
        assert "baseline: b.json" in text
        assert "resolved (1)" in text
        assert "persisting (1)" in text
        assert "new (1)" in text
        assert "accepted (1)" in text
        assert "`r` [prose]: a finding" in text
        assert "3 -> 1 (-2)" in text

    def test_text_marks_an_empty_group(self):
        text = _recheck.format_recheck("b.json", ([], [], [], []), (0, 0))
        assert text.count("      -") == 4

    def test_payload_lists_the_aids_that_were_not_refreshed(self):
        payload = _recheck.recheck_payload(
            Path("content/drafts/t/s.md"), "b.json", self._groups(), (3, 1), ["verbatim"]
        )
        assert payload["not_refreshed"] == ["verbatim"]

    def test_text_names_the_aids_that_were_not_refreshed(self):
        text = _recheck.format_recheck("b.json", self._groups(), (3, 1), ["verbatim", "support"])
        assert "not refreshed: verbatim, support" in text

    def test_text_says_nothing_about_refreshing_when_every_aid_was(self):
        assert "not refreshed" not in _recheck.format_recheck("b.json", self._groups(), (3, 1))

    def test_payload_carries_each_raised_aids_reason_beside_the_list(self):
        """#893: `not_refreshed` stays a list of names -- agenda-reviser
        branches on membership -- and the reasons ride in a parallel key."""
        payload = _recheck.recheck_payload(
            Path("content/drafts/t/s.md"),
            "b.json",
            self._groups(),
            (3, 1),
            ["verbatim", "support"],
            {"verbatim": "OSError: gone"},
        )
        assert payload["not_refreshed"] == ["verbatim", "support"]
        assert payload["refresh_errors"] == {"verbatim": "OSError: gone"}

    def test_payload_has_an_empty_error_map_when_nothing_raised(self):
        payload = _recheck.recheck_payload(
            Path("content/drafts/t/s.md"), "b.json", self._groups(), (3, 1), []
        )
        assert payload["refresh_errors"] == {}

    def test_text_names_a_raised_aids_reason(self):
        text = _recheck.format_recheck(
            "b.json", self._groups(), (3, 1), ["verbatim", "support"], {"verbatim": "OSError: gone"}
        )
        assert "not refreshed: verbatim (raised: OSError: gone), support --" in text


@pytest.fixture
def refreshable(ledger_con):
    """A synced (if empty) ledger, which `agenda --baseline` now checks
    for before refreshing anything (#893). Kept apart from `aid_stubs`,
    which stands in for the aids rather than for this precondition, so
    `TestBaselineNeedsALedger` can stub the aids with no ledger at all."""
    return ledger_con


@pytest.mark.usefixtures("refreshable")
class TestBaselineCli:
    def _draft(self, isolated_config, monkeypatch) -> Path:
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n\nSome prose here.\n")
        monkeypatch.setattr(
            agenda._sources.style_check,
            "check",
            lambda d, override=None, propose=True: {"findings": [], "vale_error": None},
        )
        return draft

    def _baseline_file(self, tmp_path, items) -> Path:
        path = tmp_path / "baseline.agenda.json"
        path.write_text(json.dumps({"aid": "agenda", "items": items}))
        return path

    def test_baseline_defaults_to_none(self):
        assert agenda.build_parser().parse_args(["d.md"]).baseline is None

    def test_baseline_is_parsed(self):
        args = agenda.build_parser().parse_args(["d.md", "--baseline", "b.json"])
        assert args.baseline == "b.json"

    def test_a_bad_baseline_returns_two_without_refreshing(
        self, isolated_config, monkeypatch, capsys, tmp_path, aid_stubs
    ):
        draft = self._draft(isolated_config, monkeypatch)
        missing = tmp_path / "nope.json"
        exit_code = agenda.main([str(draft), "--baseline", str(missing)])
        assert exit_code == 2
        assert str(missing) in capsys.readouterr().err
        assert all(stub.calls == [] for stub in aid_stubs.values())

    def test_a_missing_draft_still_returns_one(self, isolated_config, capsys, aid_stubs):
        assert agenda.main(["content/drafts/nope.md", "--baseline", "b.json"]) == 1
        assert all(stub.calls == [] for stub in aid_stubs.values())

    def test_json_prints_the_recheck_payload_not_the_agenda(
        self, isolated_config, monkeypatch, capsys, tmp_path, aid_stubs
    ):
        draft = self._draft(isolated_config, monkeypatch)
        baseline = self._baseline_file(tmp_path, [_item_dict("gone")])
        exit_code = agenda.main([str(draft), "--baseline", str(baseline), "--json"])
        assert exit_code == 0
        out = capsys.readouterr()
        payload = json.loads(out.out)
        assert payload["resolved"] == [_item_dict("gone")]
        assert payload["persisting"] == []
        assert payload["new"] == []
        assert payload["objective_before"] == 1
        assert payload["objective_after"] == 0
        assert payload["objective_delta"] == -1
        assert payload["baseline"] == str(baseline)
        assert "--baseline" in payload["command"]
        assert "json" in out.err  # the written-files summary is still on stderr
        assert all(len(stub.calls) == 1 for stub in aid_stubs.values() if stub.calls)

    def test_json_stdout_is_only_the_payload(self, isolated_config, monkeypatch, capsys, tmp_path):
        draft = self._draft(isolated_config, monkeypatch)
        for name in _sources.AID_NAMES:
            monkeypatch.setattr(
                _registry.AIDS[name][0], "main", _AidStub(name, chatter="WROTE A FILE")
            )
        baseline = self._baseline_file(tmp_path, [])
        agenda.main([str(draft), "--baseline", str(baseline), "--json"])
        out = capsys.readouterr().out
        assert "WROTE A FILE" not in out
        json.loads(out)

    def test_without_json_the_text_and_the_summary_share_stdout(
        self, isolated_config, monkeypatch, capsys, tmp_path, aid_stubs
    ):
        draft = self._draft(isolated_config, monkeypatch)
        baseline = self._baseline_file(tmp_path, [_item_dict("gone")])
        assert agenda.main([str(draft), "--baseline", str(baseline)]) == 0
        out = capsys.readouterr()
        assert f"baseline: {baseline}" in out.out
        assert "resolved (1)" in out.out
        assert "json" in out.out
        # Nothing of the comparison itself moved to stderr -- the render
        # warnings pandoc emits there are the layer's own, not this mode's.
        assert "resolved" not in out.err

    def test_the_agenda_report_is_still_filed_under_baseline(
        self, isolated_config, monkeypatch, tmp_path, aid_stubs
    ):
        draft = self._draft(isolated_config, monkeypatch)
        baseline = self._baseline_file(tmp_path, [])
        agenda.main([str(draft), "--baseline", str(baseline)])
        assert review.report_path(draft, "agenda", "md").is_file()
        payload = json.loads(review.report_path(draft, "agenda", "json").read_text())
        assert payload["aid"] == "agenda"

    def test_the_filed_json_records_the_bare_command_so_it_can_serve_as_a_baseline(
        self, isolated_config, monkeypatch, tmp_path, aid_stubs
    ):
        """The filed `.json` *is* the next run's baseline, so its envelope
        must record a command that regenerates an agenda, not one that
        regenerates a comparison against itself."""
        draft = self._draft(isolated_config, monkeypatch)
        baseline = self._baseline_file(tmp_path, [])
        agenda.main([str(draft), "--baseline", str(baseline)])
        filed = json.loads(review.report_path(draft, "agenda", "json").read_text())
        assert "--baseline" not in filed["command"]
        # shlex.join, not an f-string: a real tmp_path draft carries the
        # host's own separator, and `_command` quotes it exactly the way
        # `shlex.join` does -- a bare f-string only matches on POSIX.
        assert filed["command"] == shlex.join(
            ["python", "-m", "chitragupta.review", "agenda", str(draft)]
        )

    def test_a_baseline_at_the_path_this_run_overwrites_is_still_compared_against(
        self, isolated_config, monkeypatch, capsys, aid_stubs
    ):
        """The natural invocation passes `<stem>.agenda.json`, which the
        run then overwrites -- loading before refreshing is what makes
        that safe, and this pins it."""
        draft = self._draft(isolated_config, monkeypatch)
        own = review.write_json(draft, "agenda", {"aid": "agenda", "items": [_item_dict("gone")]})
        agenda.main([str(draft), "--baseline", str(own), "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["resolved"] == [_item_dict("gone")]
        assert json.loads(own.read_text())["items"] == []

    def test_objective_after_equals_the_agendas_own_objective_class_count(
        self, isolated_config, monkeypatch, capsys, tmp_path, aid_stubs
    ):
        """`objective_before`/`objective_after` are only trustworthy
        against `pass_bound` if they mean exactly what
        `Agenda.objective_class_count` means."""
        draft = self._draft(isolated_config, monkeypatch)
        monkeypatch.setattr(
            agenda._sources.style_check,
            "check",
            lambda d, override=None, propose=True: {
                "findings": [{"line": 3, "rule": "chitragupta.Weasel", "message": "weasel"}],
                "vale_error": None,
            },
        )
        baseline = self._baseline_file(tmp_path, [])
        agenda.main([str(draft), "--baseline", str(baseline), "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["objective_after"] == agenda.build_agenda(draft).objective_class_count
        assert payload["objective_after"] == 1


@pytest.mark.usefixtures("refreshable")
class TestBaselineCliNotRefreshed:
    """#837: an aid whose refresh failed is named, and its items -- last
    run's, still on disk -- are never counted or compared as current."""

    RUN = "these exact borrowed words"

    def _draft(self, isolated_config, monkeypatch) -> Path:
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text(f"# Survey\n\nSome prose with {self.RUN} in it.\n")
        monkeypatch.setattr(
            agenda._sources.style_check,
            "check",
            lambda d, override=None, propose=True: {"findings": [], "vale_error": None},
        )
        # A logged query, so `coverage` runs too and a fully refreshed run
        # really has every aid refreshed.
        dossier.log_retrieval(draft, "draft", "digital twin", 5, 3, 100)
        return draft

    def _old_sidecar(self, draft, aid, finding) -> None:
        """Last run's `.json`, backdated so a same-tick rewrite cannot
        read as unchanged on a coarse-timestamp filesystem."""
        path = review.write_json(draft, aid, {"findings": [finding]})
        os.utime(path, (1_000_000, 1_000_000))

    def _short_run(self) -> dict:
        # `draft_text` is in the draft, so `_stale.partition` keeps the
        # item: the test must not pass on the span check alone.
        return {
            "id": "v1",
            "citekey": "a2024",
            "line": 3,
            "span_words": 4,
            "matched_words": 4,
            "fragment": self.RUN,
            "draft_text": self.RUN,
            "severity": "short",
            "tier": "exact",
        }

    def _baseline_file(self, tmp_path, payload) -> Path:
        path = tmp_path / "baseline.agenda.json"
        path.write_text(json.dumps(payload))
        return path

    def _recheck(self, draft, baseline, capsys) -> dict:
        assert agenda.main([str(draft), "--baseline", str(baseline), "--json"]) == 0
        return json.loads(capsys.readouterr().out)

    def test_a_fully_refreshed_run_lists_nothing(
        self, isolated_config, monkeypatch, capsys, tmp_path, aid_stubs
    ):
        draft = self._draft(isolated_config, monkeypatch)
        baseline = self._baseline_file(tmp_path, {"aid": "agenda", "items": []})
        assert self._recheck(draft, baseline, capsys)["not_refreshed"] == []

    @pytest.mark.parametrize(
        ("returncode", "writes"), [(1, False), (0, False)], ids=["exit-1", "exit-0-wrote-nothing"]
    )
    def test_a_failed_refresh_is_listed_and_its_items_are_not_counted(
        self, isolated_config, monkeypatch, capsys, tmp_path, aid_stubs, returncode, writes
    ):
        draft = self._draft(isolated_config, monkeypatch)
        self._old_sidecar(draft, "verbatim", self._short_run())
        # The stale item would count if nothing marked it: pins that the
        # assertions below are about refresh state, not the span check.
        assert agenda.build_agenda(draft).objective_class_count == 1

        aid_stubs["verbatim"].returncode = returncode
        aid_stubs["verbatim"].writes = writes
        baseline = self._baseline_file(tmp_path, {"aid": "agenda", "items": []})
        payload = self._recheck(draft, baseline, capsys)

        assert payload["not_refreshed"] == ["verbatim"]
        assert payload["objective_after"] == 0
        assert payload["new"] == []
        filed = json.loads(review.report_path(draft, "agenda", "json").read_text())
        assert filed["objective_class_count"] == 0
        assert filed["sources"]["aids"]["verbatim"]["refreshed"] is False
        # Still listed on the filed worklist, only not counted.
        assert [item["class"] for item in filed["items"]] == ["verbatim-run"]
        rendered = review.report_path(draft, "agenda", "md").read_text()
        assert "**not refreshed**" in rendered

    def test_a_stale_item_is_neither_persisting_nor_resolved(
        self, isolated_config, monkeypatch, capsys, tmp_path, aid_stubs
    ):
        claim = {"id": "c1", "citekey": "a2024", "claim": "a claim", "score": 0.1, "line": 3}
        draft = self._draft(isolated_config, monkeypatch)
        self._old_sidecar(draft, "support", claim)
        agenda.main([str(draft)])
        capsys.readouterr()
        baseline = review.report_path(draft, "agenda", "json")
        assert [item["class"] for item in json.loads(baseline.read_text())["items"]] == [
            "claim-support"
        ]

        aid_stubs["support"].writes = False
        payload = self._recheck(draft, baseline, capsys)
        assert payload["not_refreshed"] == ["support"]
        assert payload["persisting"] == []
        assert payload["resolved"] == []

    def test_a_baseline_marking_an_aid_not_refreshed_does_not_inflate_before(
        self, isolated_config, monkeypatch, capsys, tmp_path, aid_stubs
    ):
        """Excluding a failed aid from this run's side only would still
        let the baseline's stale copy of its items count in
        `objective_before` -- a fall reported for a repair nobody made."""
        draft = self._draft(isolated_config, monkeypatch)
        baseline = self._baseline_file(
            tmp_path,
            {
                "aid": "agenda",
                "sources": {"aids": {"verbatim": {"refreshed": False}}},
                "items": [_item_dict("v", cls="verbatim-run")],
            },
        )
        payload = self._recheck(draft, baseline, capsys)
        assert payload["not_refreshed"] == []
        assert payload["resolved"] == []
        assert payload["objective_before"] == 0

    def test_the_text_form_names_the_aid(
        self, isolated_config, monkeypatch, capsys, tmp_path, aid_stubs
    ):
        draft = self._draft(isolated_config, monkeypatch)
        aid_stubs["verbatim"].returncode = 1
        baseline = self._baseline_file(tmp_path, {"aid": "agenda", "items": []})
        assert agenda.main([str(draft), "--baseline", str(baseline)]) == 0
        assert "not refreshed: verbatim" in capsys.readouterr().out

    def test_an_aid_that_raises_is_recorded_and_the_recheck_completes(
        self, isolated_config, monkeypatch, capsys, tmp_path, aid_stubs
    ):
        """#893: before, the exception escaped `refresh_aids` and no
        agenda was filed at all."""
        draft = self._draft(isolated_config, monkeypatch)
        self._old_sidecar(draft, "verbatim", self._short_run())
        aid_stubs["verbatim"].raises = RuntimeError("scan blew up")
        baseline = self._baseline_file(tmp_path, {"aid": "agenda", "items": []})
        payload = self._recheck(draft, baseline, capsys)

        assert payload["not_refreshed"] == ["verbatim"]
        assert payload["refresh_errors"] == {"verbatim": "RuntimeError: scan blew up"}
        assert payload["objective_after"] == 0
        assert payload["new"] == []
        filed = json.loads(review.report_path(draft, "agenda", "json").read_text())
        assert filed["sources"]["aids"]["verbatim"]["refresh_error"] == (
            "RuntimeError: scan blew up"
        )
        assert filed["objective_class_count"] == 0
        rendered = review.report_path(draft, "agenda", "md").read_text()
        assert "raised: RuntimeError: scan blew up" in rendered


class TestBaselineNeedsALedger:
    """#893: with no ledger, or one needing a sync, `--baseline` refuses
    once, up front, with the sync instruction -- instead of every aid
    that reads the ledger raising it in turn, and before anything is
    refreshed, accepted or filed."""

    def _draft(self, isolated_config, monkeypatch) -> Path:
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n\nSome prose here.\n")
        monkeypatch.setattr(
            agenda._sources.style_check,
            "check",
            lambda d, override=None, propose=True: {"findings": [], "vale_error": None},
        )
        return draft

    def _baseline(self, tmp_path) -> Path:
        path = tmp_path / "baseline.agenda.json"
        path.write_text(json.dumps({"aid": "agenda", "items": []}))
        return path

    def _stale_ledger(self) -> None:
        # A file with `user_version` 0 is behind every migration, which
        # `read_connection` refuses as `StaleLedger`.
        config.LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        sqlite3.connect(config.LEDGER_PATH).close()

    @pytest.mark.parametrize("stale", [False, True], ids=["no-ledger", "stale-ledger"])
    def test_refuses_once_with_the_sync_instruction_and_touches_nothing(
        self, isolated_config, monkeypatch, capsys, tmp_path, aid_stubs, stale
    ):
        draft = self._draft(isolated_config, monkeypatch)
        if stale:
            self._stale_ledger()
        argv = [str(draft), "--baseline", str(self._baseline(tmp_path))]
        assert agenda.main([*argv, "--accept", "deadbeef0000"]) == 1
        err = capsys.readouterr().err
        assert err.count("python -m chitragupta.corpus sync") == 1
        assert err.startswith("[error] ")
        assert all(stub.calls == [] for stub in aid_stubs.values())
        assert not review.report_path(draft, "agenda", "json").exists()
        assert _accept.load(draft).records == []

    def test_a_bad_baseline_is_still_reported_first(
        self, isolated_config, monkeypatch, capsys, tmp_path, aid_stubs
    ):
        """A usage error costs nothing to report and is the caller's to
        fix first, so it keeps exit 2 even with no ledger."""
        draft = self._draft(isolated_config, monkeypatch)
        assert agenda.main([str(draft), "--baseline", str(tmp_path / "nope.json")]) == 2
        assert "sync" not in capsys.readouterr().err

    def test_the_bare_mode_still_runs_without_a_ledger(
        self, isolated_config, monkeypatch, capsys, aid_stubs
    ):
        """It runs no aid, and degrades a missing corpus to a header note
        -- refusing there would be a regression."""
        draft = self._draft(isolated_config, monkeypatch)
        assert agenda.main([str(draft)]) == 0
        assert review.report_path(draft, "agenda", "json").is_file()


# --------------------------------------------------------------------------
# _accept.py
# --------------------------------------------------------------------------


def _acceptable_item(item_id: str = "aaa", cls: str = "uncited-claim") -> _items.Item:
    return _items.Item(
        id=item_id,
        cls=cls,
        section="Intro",
        citekey=None,
        line=4,
        unattended=False,
        summary="a claim a person read and accepted",
    )


class TestAcceptableClasses:
    def test_the_three_judgement_classes_are_acceptable(self):
        assert set(_accept.ACCEPTABLE) == {
            "claim-support",
            "uncited-claim",
            "unsupported-claim",
        }

    def test_every_other_class_in_the_table_is_refused(self, isolated_config):
        """Derived from `_items.CLASSES` rather than a copy of it, so a
        ninth class has to decide whether it is acceptable instead of
        inheriting an answer."""
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n")
        for cls in set(_items.CLASSES) - set(_accept.ACCEPTABLE):
            item = _acceptable_item("id-" + cls, cls=cls)
            with pytest.raises(_accept.NotAcceptable, match=cls):
                _accept.accept(draft, [item], [item.id], "cmd")

    def test_the_two_defect_classes_are_named_among_the_refused(self):
        refused = set(_items.CLASSES) - set(_accept.ACCEPTABLE)
        assert {"missing-citekey", "misquoted"} <= refused


class TestAcceptRecord:
    def _draft(self, isolated_config) -> Path:
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n")
        return draft

    def test_no_record_file_yet_is_absent_not_an_error(self, isolated_config):
        source = _accept.load(self._draft(isolated_config))
        assert (source.available, source.records, source.reason) == (False, [], None)

    def test_accepting_writes_a_record_beside_the_report(self, isolated_config):
        draft = self._draft(isolated_config)
        _accept.accept(draft, [_acceptable_item()], ["aaa"], "cmd")
        path = _accept.accepted_path(draft)
        assert path.parent == review.report_dir(draft)
        payload = json.loads(path.read_text())
        assert payload["aid"] == "agenda"
        assert payload["command"] == "cmd"
        assert payload["accepted"] == [
            {
                "id": "aaa",
                "class": "uncited-claim",
                "section": "Intro",
                "citekey": None,
                "summary": "a claim a person read and accepted",
            }
        ]

    def test_an_accepted_record_reads_back(self, isolated_config):
        draft = self._draft(isolated_config)
        _accept.accept(draft, [_acceptable_item()], ["aaa"], "cmd")
        source = _accept.load(draft)
        assert source.available
        assert _accept.accepted_ids(source) == {"aaa"}

    def test_accepting_twice_records_the_item_once(self, isolated_config):
        draft = self._draft(isolated_config)
        item = _acceptable_item()
        _accept.accept(draft, [item], ["aaa"], "cmd")
        messages = _accept.accept(draft, [item], ["aaa"], "cmd")
        assert len(_accept.load(draft).records) == 1
        assert "already accepted" in messages[0]

    def test_an_unknown_id_is_refused(self, isolated_config):
        draft = self._draft(isolated_config)
        with pytest.raises(_accept.NotAcceptable, match="nope"):
            _accept.accept(draft, [_acceptable_item()], ["nope"], "cmd")

    def test_a_refused_id_writes_nothing(self, isolated_config):
        draft = self._draft(isolated_config)
        with pytest.raises(_accept.NotAcceptable):
            _accept.accept(draft, [_acceptable_item()], ["nope"], "cmd")
        assert not _accept.accepted_path(draft).is_file()

    def test_two_ids_in_one_call_are_both_recorded(self, isolated_config):
        draft = self._draft(isolated_config)
        items = [_acceptable_item("aaa"), _acceptable_item("bbb", cls="claim-support")]
        _accept.accept(draft, items, ["aaa", "bbb"], "cmd")
        assert _accept.accepted_ids(_accept.load(draft)) == {"aaa", "bbb"}

    def test_a_truncated_record_degrades_to_unreadable_with_a_reason(self, isolated_config):
        draft = self._draft(isolated_config)
        path = _accept.accepted_path(draft)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json")
        source = _accept.load(draft)
        assert (source.available, source.records) == (False, [])
        assert str(path) in source.reason

    def test_a_payload_that_is_not_an_acceptance_record_is_unreadable(self, isolated_config):
        draft = self._draft(isolated_config)
        path = _accept.accepted_path(draft)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"aid": "agenda"}))
        assert "no 'accepted' list" in _accept.load(draft).reason

    def test_a_hand_mangled_row_is_dropped_rather_than_raising(self, isolated_config):
        draft = self._draft(isolated_config)
        path = _accept.accepted_path(draft)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"accepted": ["just a string", {"id": "aaa"}]}))
        assert _accept.accepted_ids(_accept.load(draft)) == {"aaa"}

    def test_an_unreadable_record_refuses_a_new_acceptance_rather_than_overwriting_it(
        self, isolated_config
    ):
        draft = self._draft(isolated_config)
        path = _accept.accepted_path(draft)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json")
        with pytest.raises(_accept.NotAcceptable, match="unreadable"):
            _accept.accept(draft, [_acceptable_item()], ["aaa"], "cmd")
        assert path.read_text() == "{not json"


class TestPartition:
    def test_an_unaccepted_item_is_kept(self):
        items = [_acceptable_item()]
        kept, suppressed = _accept.partition(items, _accept.AcceptedSource())
        assert (kept, suppressed) == (items, [])

    def test_an_accepted_item_is_suppressed(self):
        items = [_acceptable_item()]
        source = _accept.AcceptedSource(available=True, records=[{"id": "aaa"}])
        kept, suppressed = _accept.partition(items, source)
        assert (kept, suppressed) == ([], items)

    def test_a_changed_span_brings_the_item_back(self):
        """The identity is the span hash, so an edited claim raises a new
        id, which no record matches -- the reopening mechanism, and the
        reason there is no second one."""
        source = _accept.AcceptedSource(
            available=True,
            records=[{"id": _identity.item_id("uncited", "uncited-claim", "Intro", None, "old")}],
        )
        reworded = _acceptable_item(
            _identity.item_id("uncited", "uncited-claim", "Intro", None, "new")
        )
        kept, suppressed = _accept.partition([reworded], source)
        assert (kept, suppressed) == ([reworded], [])


class TestStaleAndAcceptedDoNotOverlap:
    """R12's refusal (#766) and acceptance (#767) are two filters on one
    list, and neither change existed when the other was written.

    They cannot collide today, and this asserts *why* rather than
    restating it: only an item carrying a `span` can be refused as stale,
    and no class that carries one may be accepted.
    """

    def _every_class_with_a_span(self) -> set[str]:
        """The classes the real extractors file a `span` for, derived by
        running them rather than copied from `_stale.py`'s prose.

        Every aid gets one finding carrying a superset of the keys any
        extractor reads, so a class that starts filing a span later is
        caught here instead of silently becoming refusable.
        """
        finding = {
            "id": "f1",
            "line": 3,
            "citekey": "a2024",
            "claim": "a claim",
            "sentence": "a sentence",
            "quote": "a quote",
            "score": 0.1,
            "note": None,
            "band": "no support found",
            "severity": "short",
            "tier": "exact",
            "matched_words": 4,
            "rule": "chitragupta.Weasel",
            "message": "weasel",
            "draft_text": "a borrowed run",
            "match": "clearly",
        }
        payload = {"findings": [finding]}
        sources = _sources_stub(
            aids={
                aid: _sources.AidSource(available=True, data=payload) for aid in _sources.AID_NAMES
            },
            style=_sources.StyleSource(available=True, data={"findings": [finding]}),
        )
        sections = dossier.sections("# Intro\n\na sentence\n")
        items = _items.all_items(sources, sections)
        assert {item.cls for item in items} >= set(_accept.ACCEPTABLE)
        return {item.cls for item in items if item.span is not None}

    def test_only_verbatim_run_and_prose_carry_a_refusable_span(self):
        assert self._every_class_with_a_span() == {"verbatim-run", "prose"}

    def test_no_acceptable_class_can_be_refused_as_stale(self):
        assert self._every_class_with_a_span().isdisjoint(_accept.ACCEPTABLE)

    def test_a_stale_item_is_refused_rather_than_reported_as_suppressed(
        self, isolated_config, monkeypatch
    ):
        """The order `build_agenda` runs the two filters in, pinned
        through a hand-written record naming an item that is also stale.

        Refusal first: the item lands in `stale`, not in `suppressed`,
        and its record reads `suppressed: false`. The other order would
        claim a judgement was honoured on a finding this run declined to
        raise at all, and would drop it out of the refusal report.
        """
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n\nThe author has since rewritten this.\n")
        monkeypatch.setattr(
            agenda._sources.style_check,
            "check",
            lambda d, override=None, propose=True: {"findings": [], "vale_error": None},
        )
        review.write_json(
            draft,
            "verbatim",
            {
                "findings": [
                    {
                        "id": "v1",
                        "line": 3,
                        "citekey": "a2024",
                        "severity": "short",
                        "tier": "exact",
                        "matched_words": 4,
                        "draft_text": "a run the draft no longer carries",
                    }
                ]
            },
        )
        stale_id = agenda.build_agenda(draft).stale[0].id
        _accept.write(draft, [{"id": stale_id, "class": "verbatim-run", "summary": "s"}], "cmd")

        built = agenda.build_agenda(draft)
        assert [item.id for item in built.stale] == [stale_id]
        assert built.suppressed == []
        assert built.items == []

        payload = _render.agenda_payload(built, "cmd")
        assert [row["id"] for row in payload["stale_spans"]] == [stale_id]
        assert payload["accepted"] == [
            {"id": stale_id, "class": "verbatim-run", "summary": "s", "suppressed": False}
        ]
        rendered = _render.render_markdown(built, "cmd")
        assert "## Refused as stale" in rendered
        assert f"- `{stale_id}` [verbatim-run, not raised by this run]" in rendered

    def test_a_live_accepted_item_is_still_suppressed_when_a_stale_one_exists(
        self, isolated_config, monkeypatch
    ):
        """The two filters compose: a refusal does not stop the
        acceptance filter reaching the items that survived it."""
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n\nA claim with no citation at all.\n")
        monkeypatch.setattr(
            agenda._sources.style_check,
            "check",
            lambda d, override=None, propose=True: {"findings": [], "vale_error": None},
        )
        review.write_json(
            draft,
            "verbatim",
            {
                "findings": [
                    {
                        "id": "v1",
                        "line": 3,
                        "citekey": "a2024",
                        "severity": "short",
                        "tier": "exact",
                        "matched_words": 4,
                        "draft_text": "wording that is gone",
                    }
                ]
            },
        )
        review.write_json(
            draft,
            "uncited",
            {"findings": [{"id": "u1", "line": 3, "sentence": "A claim with no citation at all."}]},
        )
        built = agenda.build_agenda(draft)
        live = [item for item in built.items if item.cls == "uncited-claim"]
        assert len(built.stale) == 1 and len(live) == 1

        _accept.accept(draft, built.items, [live[0].id], "cmd")
        after = agenda.build_agenda(draft)
        assert [item.id for item in after.suppressed] == [live[0].id]
        assert [item.id for item in after.stale] == [built.stale[0].id]
        assert after.items == []


class TestAcceptedAgendaEndToEnd:
    """`--accept` through the real command, against a real
    `.uncited.json` an earlier aid run would have left on disk."""

    SENTENCE = "Digital twins are widely deployed in industry."

    def _draft(self, isolated_config, monkeypatch, sentence: str | None = None) -> Path:
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n\nSome prose here.\n")
        monkeypatch.setattr(
            agenda._sources.style_check,
            "check",
            lambda d, override=None, propose=True: {"findings": [], "vale_error": None},
        )
        path = review.write_json(
            draft,
            "uncited",
            {"findings": [{"id": "u1", "line": 3, "sentence": sentence or self.SENTENCE}]},
        )
        # Backdated so a `--baseline` stub's same-tick rewrite still reads
        # as a refresh (`_refresh.refresh_aids` compares mtimes, #837).
        os.utime(path, (1_000_000, 1_000_000))
        return draft

    def _only_id(self, draft: Path) -> str:
        built = agenda.build_agenda(draft)
        assert [item.cls for item in built.items] == ["uncited-claim"]
        return built.items[0].id

    def test_accepting_takes_the_item_off_the_next_worklist(
        self, isolated_config, monkeypatch, capsys
    ):
        draft = self._draft(isolated_config, monkeypatch)
        item_id = self._only_id(draft)
        assert agenda.main([str(draft), "--accept", item_id]) == 0
        assert f"accepted `{item_id}`" in capsys.readouterr().out

        built = agenda.build_agenda(draft)
        assert built.items == []
        assert [item.id for item in built.suppressed] == [item_id]

    def test_the_agenda_still_recomputes_from_the_aids(self, isolated_config, monkeypatch, capsys):
        """Nothing durable holds item state: delete the aid's report and
        the item is gone from the worklist *and* from the suppressed
        list, because it was never stored -- only its identity was."""
        draft = self._draft(isolated_config, monkeypatch)
        agenda.main([str(draft), "--accept", self._only_id(draft)])
        capsys.readouterr()
        review.report_path(draft, "uncited", "json").unlink()
        built = agenda.build_agenda(draft)
        assert (built.items, built.suppressed) == ([], [])
        assert len(built.sources.accepted.records) == 1

    def test_an_edited_span_brings_the_accepted_item_back(
        self, isolated_config, monkeypatch, capsys
    ):
        draft = self._draft(isolated_config, monkeypatch)
        agenda.main([str(draft), "--accept", self._only_id(draft)])
        capsys.readouterr()
        review.write_json(
            draft,
            "uncited",
            {"findings": [{"id": "u1", "line": 3, "sentence": "A different claim entirely."}]},
        )
        built = agenda.build_agenda(draft)
        assert [item.cls for item in built.items] == ["uncited-claim"]
        assert built.suppressed == []

    def test_the_report_lists_the_accepted_item_so_the_record_is_auditable(
        self, isolated_config, monkeypatch, capsys
    ):
        draft = self._draft(isolated_config, monkeypatch)
        item_id = self._only_id(draft)
        agenda.main([str(draft), "--accept", item_id])
        capsys.readouterr()
        rendered = review.report_path(draft, "agenda", "md").read_text()
        assert "## Accepted" in rendered
        assert f"- `{item_id}` [uncited-claim, suppressed]" in rendered
        assert "Accepted items: read, 1 recorded" in rendered

        payload = json.loads(review.report_path(draft, "agenda", "json").read_text())
        assert payload["accepted"] == [
            {
                "id": item_id,
                "class": "uncited-claim",
                "section": "Survey",
                "citekey": None,
                "summary": self.SENTENCE,
                "suppressed": True,
            }
        ]
        assert payload["sources"]["accepted"] == {"available": True, "count": 1}
        assert payload["items"] == []

    def test_a_record_that_matches_nothing_is_still_listed(
        self, isolated_config, monkeypatch, capsys
    ):
        draft = self._draft(isolated_config, monkeypatch)
        item_id = self._only_id(draft)
        agenda.main([str(draft), "--accept", item_id])
        capsys.readouterr()
        review.report_path(draft, "uncited", "json").unlink()
        built = agenda.build_agenda(draft)
        rendered = _render.render_markdown(built, "cmd")
        assert f"- `{item_id}` [uncited-claim, not raised by this run]" in rendered
        assert _render.agenda_payload(built, "cmd")["accepted"][0]["suppressed"] is False

    def test_no_record_at_all_renders_no_accepted_section(self, isolated_config, monkeypatch):
        draft = self._draft(isolated_config, monkeypatch)
        rendered = _render.render_markdown(agenda.build_agenda(draft), "cmd")
        assert "## Accepted" not in rendered
        assert "Accepted items: none recorded" in rendered

    def test_an_unreadable_record_is_named_in_the_header(self, isolated_config, monkeypatch):
        draft = self._draft(isolated_config, monkeypatch)
        _accept.accepted_path(draft).write_text("{not json")
        built = agenda.build_agenda(draft)
        rendered = _render.render_markdown(built, "cmd")
        assert "Accepted items: **unreadable**" in rendered
        assert [item.cls for item in built.items] == ["uncited-claim"]

    def test_accepting_an_already_accepted_id_says_so_rather_than_refusing(
        self, isolated_config, monkeypatch, capsys
    ):
        draft = self._draft(isolated_config, monkeypatch)
        item_id = self._only_id(draft)
        agenda.main([str(draft), "--accept", item_id])
        capsys.readouterr()
        assert agenda.main([str(draft), "--accept", item_id]) == 0
        assert "already accepted" in capsys.readouterr().out

    def test_a_defect_class_id_is_refused_with_the_usage_code(
        self, isolated_config, monkeypatch, capsys, ledger_con
    ):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n\nA claim [@gone_2024].\n")
        monkeypatch.setattr(
            agenda._sources.style_check,
            "check",
            lambda d, override=None, propose=True: {"findings": [], "vale_error": None},
        )
        directory = dossier.dossier_dir(draft)
        directory.mkdir(parents=True)
        (directory / dossier.SECTIONS_MD).write_text(
            "| Section | Citekeys |\n| --- | --- |\n| Survey | `gone_2024` |\n"
        )
        built = agenda.build_agenda(draft)
        defects = [item for item in built.items if item.cls == "missing-citekey"]
        assert defects, "the fixture must raise a defect-class item to refuse"
        assert agenda.main([str(draft), "--accept", defects[0].id]) == 2
        err = capsys.readouterr().err
        assert "cannot be accepted" in err
        assert not _accept.accepted_path(draft).is_file()

    def test_an_unknown_id_is_refused_with_the_usage_code(
        self, isolated_config, monkeypatch, capsys
    ):
        draft = self._draft(isolated_config, monkeypatch)
        assert agenda.main([str(draft), "--accept", "nosuchid"]) == 2
        assert "No agenda item `nosuchid`" in capsys.readouterr().err

    def test_accept_defaults_to_none_and_is_repeatable(self):
        assert agenda.build_parser().parse_args(["d.md"]).accept is None
        args = agenda.build_parser().parse_args(["d.md", "--accept", "a", "--accept", "b"])
        assert args.accept == ["a", "b"]

    def test_under_json_the_messages_stay_off_stdout(self, isolated_config, monkeypatch, capsys):
        draft = self._draft(isolated_config, monkeypatch)
        item_id = self._only_id(draft)
        assert agenda.main([str(draft), "--accept", item_id, "--json"]) == 0
        out = capsys.readouterr()
        json.loads(out.out)
        assert f"accepted `{item_id}`" in out.err

    def test_the_record_names_the_command_that_wrote_it(self, isolated_config, monkeypatch, capsys):
        draft = self._draft(isolated_config, monkeypatch)
        item_id = self._only_id(draft)
        agenda.main([str(draft), "--accept", item_id])
        capsys.readouterr()
        recorded = json.loads(_accept.accepted_path(draft).read_text())["command"]
        assert recorded == shlex.join(
            ["python", "-m", "chitragupta.review", "agenda", str(draft), "--accept", item_id]
        )

    def test_the_filed_report_still_records_a_command_that_regenerates_an_agenda(
        self, isolated_config, monkeypatch, capsys
    ):
        draft = self._draft(isolated_config, monkeypatch)
        agenda.main([str(draft), "--accept", self._only_id(draft)])
        capsys.readouterr()
        filed = json.loads(review.report_path(draft, "agenda", "json").read_text())
        assert "--accept" not in filed["command"]

    def test_acceptance_never_moves_the_objective_count(self, isolated_config, monkeypatch, capsys):
        """The three acceptable classes are all surfaced, so the number
        `agenda-reviser`'s loop terminates on cannot be lowered by
        accepting anything."""
        draft = self._draft(isolated_config, monkeypatch)
        before = agenda.build_agenda(draft).objective_class_count
        agenda.main([str(draft), "--accept", self._only_id(draft)])
        capsys.readouterr()
        assert agenda.build_agenda(draft).objective_class_count == before

    def test_baseline_reports_an_accepted_item_as_accepted_not_resolved(
        self, isolated_config, monkeypatch, capsys, tmp_path, aid_stubs, refreshable
    ):
        """The failure this guards is silent: suppression removes the
        item from the new list, so a set difference would call a finding
        nobody repaired resolved."""
        draft = self._draft(isolated_config, monkeypatch)
        item_id = self._only_id(draft)
        agenda.main([str(draft), "--accept", item_id])
        capsys.readouterr()
        # The refresh re-finds the accepted sentence, as a real aid would.
        aid_stubs["uncited"].payload = json.loads(
            review.report_path(draft, "uncited", "json").read_text()
        )
        baseline = tmp_path / "baseline.agenda.json"
        baseline.write_text(
            json.dumps(
                {
                    "aid": "agenda",
                    "items": [_item_dict(item_id, cls="uncited-claim", unattended=False)],
                }
            )
        )
        assert agenda.main([str(draft), "--baseline", str(baseline), "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["resolved"] == []
        assert [row["id"] for row in payload["accepted"]] == [item_id]

    def test_accepting_under_baseline_records_the_id_the_caller_could_see(
        self, isolated_config, monkeypatch, capsys, tmp_path, aid_stubs, refreshable
    ):
        """`--accept` resolves before the refresh, so an id copied off the
        report in front of the caller is always resolvable. If the refresh
        then moves the span, the record is left naming a finding that no
        longer exists -- which is the reopening property firing, not a
        bug: the acceptance was made about text the aid no longer reports,
        so the new finding is surfaced rather than silently covered."""
        draft = self._draft(isolated_config, monkeypatch)
        item_id = self._only_id(draft)
        monkeypatch.setattr(
            _refresh,
            "refresh_aids",
            lambda d: (
                review.write_json(
                    d,
                    "uncited",
                    {"findings": [{"id": "u1", "line": 3, "sentence": "A quite different claim."}]},
                )
                and (dict.fromkeys(_sources.AID_NAMES, True), {})
            ),
        )
        baseline = tmp_path / "baseline.agenda.json"
        baseline.write_text(json.dumps({"aid": "agenda", "items": []}))
        assert agenda.main([str(draft), "--accept", item_id, "--baseline", str(baseline)]) == 0

        assert _accept.accepted_ids(_accept.load(draft)) == {item_id}
        filed = json.loads(review.report_path(draft, "agenda", "json").read_text())
        assert filed["accepted"] == [
            {
                "id": item_id,
                "class": "uncited-claim",
                "section": "Survey",
                "citekey": None,
                "summary": self.SENTENCE,
                "suppressed": False,
            }
        ]
        assert [item["class"] for item in filed["items"]] == ["uncited-claim"]
        assert filed["items"][0]["id"] != item_id

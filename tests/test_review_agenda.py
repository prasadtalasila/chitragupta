"""chitragupta/review/agenda/: the eighth review aid, merging the other
eight aids' `.json`, `style_check`'s prose findings, and the dossier's
drift report into one ranked, deduplicated worklist. Issue #381.
"""

import json
import os
import re
import shlex
from pathlib import Path

import pytest

from chitragupta import dossier, review, style_check
from chitragupta.dossier import _retrieval
from chitragupta.dossier._drift import Candidate, Drift
from chitragupta.review import agenda, citation_provenance
from chitragupta.review.agenda import (
    _dedup,
    _identity,
    _items,
    _items_findings,
    _order,
    _recheck,
    _render,
    _sources,
)

from tests.conftest import content_draft


def _sources_stub(**overrides) -> _sources.Sources:
    """A `Sources` bundle with every input absent by default, so a test
    overriding one aid doesn't have to spell out the other five."""
    aids = {aid: _sources.AidSource() for aid in _sources.AID_NAMES}
    aids.update(overrides.pop("aids", {}))
    style = overrides.pop("style", _sources.StyleSource())
    drift = overrides.pop("drift", _sources.DriftSource())
    assert not overrides
    return _sources.Sources(aids=aids, style=style, drift=drift)


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


class TestReadStyle:
    def test_clean_run_is_not_partial(self, isolated_config, monkeypatch):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n")
        monkeypatch.setattr(
            _sources.style_check,
            "check",
            lambda d, override=None: {"findings": [], "vale_error": None},
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
            lambda d, override=None: {"findings": [], "vale_error": "vale is not on PATH"},
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


class TestCollect:
    def test_collects_all_eight_inputs(self, isolated_config, monkeypatch):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n")
        monkeypatch.setattr(
            _sources.style_check,
            "check",
            lambda d, override=None: {"findings": [], "vale_error": None},
        )
        sources = _sources.collect(draft)
        assert set(sources.aids) == set(_sources.AID_NAMES)
        assert sources.style.available is True
        assert sources.drift == _sources.DriftSource()


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


class TestCandidateItems:
    def test_no_drift_gives_no_items(self):
        assert _items.candidate_items(None) == []

    def test_one_item_per_candidate(self):
        drift = Drift(
            dossier=Path("d"),
            name="d",
            draft=None,
            candidates=[Candidate("b2024", "A Paper", ["query one"])],
        )
        items = _items.candidate_items(drift)
        assert len(items) == 1
        item = items[0]
        assert item.cls == "candidate"
        assert item.citekey == "b2024"
        assert item.line is None
        assert item.section is None
        assert item.unattended is False
        assert item.detail == {"queries": ["query one"]}


class TestVerbatimRunItems:
    def _finding(self, **overrides):
        base = {
            "id": "abc123",
            "citekey": "a2024",
            "line": 5,
            "matched_words": 20,
            "fragment": "some borrowed wording",
            "severity": "long",
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


class TestUncitedSourceItems:
    def test_unavailable_source_gives_no_items(self):
        assert _items_findings.uncited_source_items(_sources.AidSource()) == []

    def test_only_uncited_candidates_status_is_kept(self):
        source = _sources.AidSource(
            available=True,
            data={
                "findings": [
                    {"id": "1", "citekey": "a2024", "title": "A", "status": "uncited_candidates"},
                    {
                        "id": "2",
                        "citekey": "b2024",
                        "title": "B",
                        "status": "cited_outside_candidates",
                    },
                ]
            },
        )
        items = _items_findings.uncited_source_items(source)
        assert [item.citekey for item in items] == ["a2024"]


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
        candidate = _items.Item("c", "candidate", None, "z", None, False, "s", {})
        missing = _items.Item("m", "missing-citekey", None, "a", None, True, "s", {})
        assert [i.id for i in _order.sort([candidate, missing])] == ["m", "c"]

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

    def test_misquoted_sits_between_uncited_claim_and_candidate(self):
        candidate = _items.Item("c", "candidate", None, "z", None, False, "s", {})
        misquoted = _items.Item("m", "misquoted", None, "a", None, False, "s", {})
        uncited_claim = _items.Item("u", "uncited-claim", None, None, 1, False, "s", {})
        ordered = [i.cls for i in _order.sort([candidate, misquoted, uncited_claim])]
        assert ordered == ["uncited-claim", "misquoted", "candidate"]

    def test_claim_support_sits_between_unsupported_claim_and_uncited_source(self):
        uncited_source = _items.Item("s", "uncited-source", None, "z", None, False, "s", {})
        claim_support = _items.Item("cs", "claim-support", None, "a", 1, False, "s", {"score": 0.2})
        unsupported_claim = _items.Item(
            "uc", "unsupported-claim", None, None, 1, False, "s", {"band": "weak"}
        )
        ordered = [i.cls for i in _order.sort([uncited_source, claim_support, unsupported_claim])]
        assert ordered == ["unsupported-claim", "claim-support", "uncited-source"]

    def test_candidates_order_by_citekey(self):
        z = _items.Item("z-id", "candidate", None, "z2024", None, False, "s", {})
        a = _items.Item("a-id", "candidate", None, "a2024", None, False, "s", {})
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

    def test_findings_grouped_by_class_then_severity(self):
        items = _order.sort(
            [
                _items.Item(
                    "m1", "missing-citekey", "Intro", "a2024", None, True, "missing a2024", {}
                ),
                _items.Item(
                    "m2", "missing-citekey", "Intro", "b2024", None, True, "missing b2024", {}
                ),
                _items.Item("c1", "candidate", None, "b2024", None, False, "candidate b2024", {}),
            ]
        )
        rendered = _render.render_markdown(
            agenda.Agenda(
                draft=Path("content/drafts/t/survey.md"), sources=_sources_stub(), items=items
            ),
            "cmd",
        )
        assert "### missing-citekey" in rendered
        assert "### candidate" in rendered
        assert rendered.count("### missing-citekey") == 1
        assert rendered.index("### missing-citekey") < rendered.index("### candidate")
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


class TestBuildAgendaAndCli:
    def _draft_with_no_dossier(self, isolated_config, monkeypatch):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n\nSome prose here.\n")
        monkeypatch.setattr(
            agenda._sources.style_check,
            "check",
            lambda d, override=None: {"findings": [], "vale_error": None},
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

    def test_a_present_aid_json_produces_a_worklist_item(self, isolated_config, monkeypatch):
        draft = self._draft_with_no_dossier(isolated_config, monkeypatch)
        review.write_json(
            draft,
            "coverage",
            {
                "findings": [
                    {"id": "1", "citekey": "a2024", "title": "A", "status": "uncited_candidates"}
                ]
            },
        )
        built = agenda.build_agenda(draft)
        assert len(built.items) == 1
        assert built.items[0].cls == "uncited-source"


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
    be tested against something that actually pollutes stdout."""

    def __init__(self, chatter: str = ""):
        self.calls: list[list[str]] = []
        self.chatter = chatter

    def __call__(self, argv):
        self.calls.append(list(argv))
        if self.chatter:
            print(self.chatter)
        return 0


@pytest.fixture
def aid_stubs(monkeypatch):
    """Every one of the eight aids' `main` replaced by a recorder.

    `refresh_aids` is tested against *what it calls*, never against real
    aid behaviour: the real eight need the enrich stack, a real corpus
    and real dossiers, none of which a unit test should depend on.
    """
    stubs = {}
    for name, module in _recheck._AID_MODULES.items():
        stub = _AidStub()
        monkeypatch.setattr(module, "main", stub)
        stubs[name] = stub
    return stubs


class TestAidModules:
    def test_keys_are_exactly_the_eight_aid_names(self):
        assert tuple(_recheck._AID_MODULES) == _sources.AID_NAMES


class TestCoverageQueries:
    def test_draft_outside_the_drafts_dir_has_none(self, isolated_config):
        draft = content_draft(isolated_config, "elsewhere/survey.md")
        draft.write_text("# S\n")
        assert _recheck._coverage_queries(draft) == []

    def test_draft_with_no_dossier_directory_has_none(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# S\n")
        assert _recheck._coverage_queries(draft) == []

    def test_dossier_with_no_retrieval_rows_has_none(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# S\n")
        dossier.dossier_dir(draft).mkdir(parents=True)
        assert _recheck._coverage_queries(draft) == []

    def test_only_revision_markers_yields_none(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# S\n")
        _retrieval.mark_revision(draft, "shorten intro")
        assert _recheck._coverage_queries(draft) == []

    def test_recorded_queries_come_back_first_seen_first(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# S\n")
        dossier.log_retrieval(draft, "draft", "digital twin", 5, 3, 100)
        dossier.log_retrieval(draft, "draft", "co-simulation", 5, 2, 90)
        assert _recheck._coverage_queries(draft) == ["digital twin", "co-simulation"]


class TestRefreshAids:
    def _draft(self, isolated_config) -> Path:
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n\nSome prose.\n")
        return draft

    def test_every_aid_is_called_once(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        dossier.log_retrieval(draft, "draft", "digital twin", 5, 3, 100)
        _recheck.refresh_aids(draft)
        assert {name: len(stub.calls) for name, stub in aid_stubs.items()} == {
            name: 1 for name in _sources.AID_NAMES
        }

    def test_every_argv_parses_against_that_aids_real_parser(self, isolated_config, aid_stubs):
        """The stubs cannot catch an argv the real parser rejects -- the
        `--write`-on-provenance mistake is exactly that shape -- so each
        recorded argv is replayed through the aid's own `build_parser`."""
        draft = self._draft(isolated_config)
        dossier.log_retrieval(draft, "draft", "digital twin", 5, 3, 100)
        _recheck.refresh_aids(draft)
        for name, stub in aid_stubs.items():
            parsed = _recheck._AID_MODULES[name].build_parser().parse_args(stub.calls[0])
            assert parsed.formats == "md"
            assert getattr(parsed, "write", True) is True

    def test_provenance_is_called_without_write(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        _recheck.refresh_aids(draft)
        argv = aid_stubs["provenance"].calls[0]
        assert argv == [str(draft), "--formats", "md"]
        with pytest.raises(SystemExit):
            citation_provenance.build_parser().parse_args([*argv, "--write"])

    def test_verbatim_is_called_as_the_scan_subcommand(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        _recheck.refresh_aids(draft)
        assert aid_stubs["verbatim"].calls[0] == [
            "scan",
            str(draft),
            "--write",
            "--formats",
            "md",
        ]

    def test_the_plain_five_are_called_with_write_and_formats_md(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        _recheck.refresh_aids(draft)
        for name in ("synthesis", "figure", "uncited", "quotation", "support"):
            assert aid_stubs[name].calls[0] == [str(draft), "--write", "--formats", "md"]

    def test_coverage_gets_one_query_flag_per_recorded_query(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        dossier.log_retrieval(draft, "draft", "digital twin", 5, 3, 100)
        dossier.log_retrieval(draft, "draft", "co-simulation", 5, 2, 90)
        _recheck.refresh_aids(draft)
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
        _recheck.refresh_aids(draft)
        assert aid_stubs["coverage"].calls == []
        assert aid_stubs["uncited"].calls  # the other seven still ran

    def test_coverage_is_skipped_with_a_dossier_but_no_rows(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        dossier.dossier_dir(draft).mkdir(parents=True)
        _recheck.refresh_aids(draft)
        assert aid_stubs["coverage"].calls == []

    def test_coverage_is_skipped_with_only_revision_markers(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        _retrieval.mark_revision(draft, "shorten intro")
        _recheck.refresh_aids(draft)
        assert aid_stubs["coverage"].calls == []

    def test_an_aids_own_stdout_is_swallowed(self, isolated_config, monkeypatch, capsys):
        draft = self._draft(isolated_config)
        for module in _recheck._AID_MODULES.values():
            monkeypatch.setattr(module, "main", _AidStub(chatter="WROTE A FILE"))
        _recheck.refresh_aids(draft)
        assert "WROTE A FILE" not in capsys.readouterr().out


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
        resolved, persisting, new, _, _ = _recheck.compare(both, both)
        assert (resolved, persisting, new) == ([], both, [])

    def test_an_item_only_in_the_baseline_is_resolved(self):
        before = [_item_dict("a")]
        resolved, persisting, new, _, _ = _recheck.compare([], before)
        assert (resolved, persisting, new) == (before, [], [])

    def test_an_item_only_in_the_new_list_is_new(self):
        after = [_item_dict("a")]
        resolved, persisting, new, _, _ = _recheck.compare(after, [])
        assert (resolved, persisting, new) == ([], [], after)

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


class TestRecheckPayloadAndText:
    def _groups(self):
        return ([_item_dict("r")], [_item_dict("p")], [_item_dict("n")])

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
            Path("content/drafts/t/s.md"), "b.json", self._groups(), (3, 1), "cmd"
        )
        assert payload["aid"] == "agenda"
        assert payload["notice"]
        assert payload["command"] == "cmd"
        assert payload["baseline"] == "b.json"
        assert payload["objective_before"] == 3
        assert payload["objective_after"] == 1
        assert payload["objective_delta"] == -2
        assert payload["resolved"] == [_item_dict("r")]
        assert payload["persisting"] == [_item_dict("p")]
        assert payload["new"] == [_item_dict("n")]

    def test_a_rising_count_gives_a_positive_delta(self):
        payload = _recheck.recheck_payload(
            Path("content/drafts/t/s.md"), "b.json", self._groups(), (1, 4), "cmd"
        )
        assert payload["objective_delta"] == 3

    def test_text_names_every_group_and_the_objective_line(self):
        text = _recheck.format_recheck("b.json", self._groups(), (3, 1))
        assert "baseline: b.json" in text
        assert "resolved (1)" in text
        assert "persisting (1)" in text
        assert "new (1)" in text
        assert "`r` [prose]: a finding" in text
        assert "3 -> 1 (-2)" in text

    def test_text_marks_an_empty_group(self):
        text = _recheck.format_recheck("b.json", ([], [], []), (0, 0))
        assert text.count("      -") == 3


class TestBaselineCli:
    def _draft(self, isolated_config, monkeypatch) -> Path:
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n\nSome prose here.\n")
        monkeypatch.setattr(
            agenda._sources.style_check,
            "check",
            lambda d, override=None: {"findings": [], "vale_error": None},
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
        for module in _recheck._AID_MODULES.values():
            monkeypatch.setattr(module, "main", _AidStub(chatter="WROTE A FILE"))
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
            lambda d, override=None: {
                "findings": [{"line": 3, "rule": "chitragupta.Weasel", "message": "weasel"}],
                "vale_error": None,
            },
        )
        baseline = self._baseline_file(tmp_path, [])
        agenda.main([str(draft), "--baseline", str(baseline), "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["objective_after"] == agenda.build_agenda(draft).objective_class_count
        assert payload["objective_after"] == 1

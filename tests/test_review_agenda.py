"""chitragupta/review/agenda/: the seventh review aid, merging the other
six aids' `.json`, `style_check`'s prose findings, and the dossier's
drift report into one ranked, deduplicated worklist. Issue #381.
"""

import json
import os
from pathlib import Path

import pytest

from chitragupta import dossier, review, style_check
from chitragupta.dossier._drift import Candidate, Drift
from chitragupta.review import agenda
from chitragupta.review.agenda import (
    _dedup,
    _identity,
    _items,
    _items_findings,
    _order,
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

    def test_no_write_flag_exists(self):
        parser = agenda.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["draft.md", "--write"])

    def test_json_flag_prints_payload_to_stdout(self, isolated_config, monkeypatch, capsys):
        draft = self._draft_with_no_dossier(isolated_config, monkeypatch)
        exit_code = agenda.main([str(draft), "--json"])
        assert exit_code == 0
        out = capsys.readouterr()
        payload = json.loads(out.out)
        assert payload["aid"] == "agenda"
        assert "json" in out.err  # written-files summary moved to stderr

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

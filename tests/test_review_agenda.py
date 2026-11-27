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
from chitragupta.review import _registry, agenda, citation_provenance, quotation
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
    aids = {aid: _sources.AidSource() for aid in _sources.AID_NAMES}
    aids.update(overrides.pop("aids", {}))
    style = overrides.pop("style", _sources.StyleSource())
    drift = overrides.pop("drift", _sources.DriftSource())
    uncited = overrides.pop("recorded", _sources.RecordedSource())
    assert not overrides
    return _sources.Sources(aids=aids, style=style, drift=drift, recorded=uncited)


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


class TestAidNames:
    def test_support_is_read(self):
        assert "support" in _sources.AID_NAMES

    def test_excludes_exactly_agenda_and_union(self):
        assert set(_sources.AID_NAMES) == set(review.AIDS) - {"agenda", "union", "digest"}

    def test_reads_in_the_registry_s_own_order(self):
        read = set(_sources.AID_NAMES)
        assert _sources.AID_NAMES == tuple(aid for aid in review.AIDS if aid in read)

    def test_render_s_source_labels_are_the_registry_s_own(self):
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


class TestReadStyleBrokenExceptions:
    def test_a_broken_exceptions_file_degrades_to_unavailable_with_the_reason(
        self, isolated_config, monkeypatch
    ):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n")

        def _broken(*_args, **_kwargs):
            raise ValueError("style_exceptions.toml: malformed TOML")

        monkeypatch.setattr(_sources.style_check, "check", _broken)
        source = _sources._read_style(draft)
        assert source.available is False
        assert "style_exceptions.toml" in source.reason
        assert _items_findings.prose_items(source, []) == []

    def test_the_header_names_the_reason(self):
        sources = _sources_stub(
            style=_sources.StyleSource(reason="style_exceptions.toml: malformed TOML"),
        )
        rendered = _render.render_markdown(
            agenda.Agenda(draft=Path("content/drafts/t/survey.md"), sources=sources, items=[]),
            "cmd",
        )
        assert "Prose (style_check): not run -- style_exceptions.toml" in rendered


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

    def test_short_names_run_is_surfaced(self):
        source = _sources.AidSource(
            available=True,
            data={"findings": [self._finding(severity="short", matched_words=8, names=True)]},
        )
        assert _items_findings.verbatim_run_items(source, [])[0].unattended is False

    def test_baseline_without_names_is_unchanged(self):
        finding = self._finding(severity="short", matched_words=8)
        assert "names" not in finding
        source = _sources.AidSource(available=True, data={"findings": [finding]})
        assert _items_findings.verbatim_run_items(source, [])[0].unattended is True

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
        source = _sources.AidSource(
            available=True,
            data={"findings": [self._finding(span_words=15, matched_words=6)]},
        )
        items = _items_findings.verbatim_run_items(source, [])
        assert items[0].summary == "15-word verbatim run citing `a2024`, 6 matched"

    def test_an_embedding_finding_is_never_unattended_however_short(self):
        source = _sources.AidSource(
            available=True,
            data={"findings": [self._finding(severity="short", matched_words=8, tier="embedding")]},
        )
        items = _items_findings.verbatim_run_items(source, [])
        assert items[0].unattended is False

    def test_a_short_skipgram_finding_is_still_unattended(self):
        source = _sources.AidSource(
            available=True,
            data={"findings": [self._finding(severity="short", matched_words=8, tier="skip-gram")]},
        )
        items = _items_findings.verbatim_run_items(source, [])
        assert items[0].unattended is True

    def test_the_summary_names_what_the_tier_actually_found(self):
        def summary(tier):
            source = _sources.AidSource(
                available=True, data={"findings": [self._finding(tier=tier)]}
            )
            return _items_findings.verbatim_run_items(source, [])[0].summary

        assert summary("exact").startswith("20-word verbatim run")
        assert summary("skip-gram").startswith("20-word skip-gram match")
        assert summary("embedding").startswith("20-word embedding-tier alignment")

    def test_a_report_filed_before_the_tier_field_existed_overstates_nothing(self):
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

    @staticmethod
    def _one(**position):
        finding = {"id": "q1", "citekey": "a2024", "quote": "a span not in the source"}
        source = _sources.AidSource(available=True, data={"findings": [{**finding, **position}]})
        return _items_findings.misquoted_items(source)[0]

    def test_a_report_filed_before_several_quotes_reads_as_it_did(self):
        assert self._one().summary == (
            "`[@a2024]`'s quoted span was not found in its source: a span not in the source"
        )

    def test_a_block_with_several_quotes_names_which_one(self):
        item = self._one(index=2, of=3)
        assert "`[@a2024]`'s quoted span (quote 2 of 3) was not found" in item.summary

    def test_the_position_does_not_enter_the_identity(self):
        assert self._one().id == self._one(index=1, of=2).id

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
        z = _items.Item("z-id", "misquoted", None, "z2024", None, False, "s", {})
        a = _items.Item("a-id", "misquoted", None, "a2024", None, False, "s", {})
        assert [i.citekey for i in _order.sort([z, a])] == ["a2024", "z2024"]


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

    @staticmethod
    def _quotation_line(data):
        sources = _sources_stub(aids={"quotation": _sources.AidSource(available=True, data=data)})
        rendered = _render.render_markdown(
            agenda.Agenda(draft=Path("content/drafts/t/survey.md"), sources=sources, items=[]),
            "cmd",
        )
        return next(line for line in rendered.splitlines() if "Quotation integrity" in line)

    @pytest.mark.parametrize(
        "universe, says",
        [
            ("no-dossier", "nothing checked -- no dossier"),
            ("no-quotes", "no quote the draft cites"),
        ],
    )
    def test_a_nothing_checked_quotation_run_says_why(self, universe, says):
        line = self._quotation_line({"universe": universe, "findings": []})
        assert "nothing checked" in line and says in line

    def test_a_checked_quotation_run_reads_as_before(self):
        assert self._quotation_line({"universe": "checked", "findings": []}) == (
            "- Quotation integrity: read"
        )

    def test_a_quotation_sidecar_without_a_universe_renders_as_before(self):
        assert self._quotation_line({"findings": []}) == "- Quotation integrity: read"

    def test_the_notes_cover_every_nothing_checked_universe(self):
        assert set(_render._QUOTATION_UNIVERSE_NOTES) == set(quotation.UNIVERSES) - {"checked"}

    def test_an_unavailable_source_with_a_reason_names_it(self):
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
        item = _items.Item("p1", "prose", None, None, 1, True, "s", {})
        built = agenda.Agenda(
            draft=Path("content/drafts/t/survey.md"), sources=_sources_stub(), items=[item]
        )

        published = _render.agenda_payload(built, "cmd")["items"][0]

        assert published["page"] is None
        assert published["paragraph"] is None

    def test_the_locator_names_the_source_page_and_the_draft_position(self):
        rendered = self._rendered(self._finding())
        assert "source p.7, draft line 35, paragraph 4" in rendered

    def test_a_run_spanning_pages_and_paragraphs_reports_both_ranges(self):
        rendered = self._rendered(self._finding(end_page=8, end_paragraph=5))
        assert "source p.7-8, draft line 35, paragraphs 4-5" in rendered

    def test_a_finding_filed_before_the_locators_existed_omits_them(self):
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
        rendered = self._rendered(self._finding())
        quotes = [ln for ln in rendered.splitlines() if ln.lstrip().startswith(">")]
        passage = [ln for ln in quotes if "the draft s own wording" in ln]
        assert passage and all(ln.startswith("    ") for ln in passage)

    def test_a_newline_in_the_source_stays_inside_the_blockquote(self):
        rendered = self._rendered(self._finding(fragment="a b c", source_text="a\nb\n\nc"))
        assert len([ln for ln in rendered.splitlines() if "**source**" in ln]) == 1

    def test_no_passage_when_the_aids_report_lacks_the_id(self):
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
        items = [
            _items.Item("p1", "prose", None, None, 3, True, "s", {}),
            _items.Item("p2", "prose", None, None, 4, True, "s", {}),
        ]
        built = agenda.Agenda(
            draft=Path("content/drafts/t/survey.md"), sources=_sources_stub(), items=items
        )
        payload = _render.agenda_payload(built, "cmd")
        assert payload["objective_class_count"] == built.objective_class_count


class TestStalePartition:
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

    def test_a_rewritten_prose_sentence_is_re_derived_not_refused(
        self, isolated_config, monkeypatch
    ):
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text("# Survey\n\nWe simply start.\n\nIt simply ends.\n")

        def vale(path, language):
            lines = Path(path).read_text().splitlines()
            return [
                {"Check": "chitragupta.DefectMarkers", "Match": "simply", "Line": n}
                for n, line in enumerate(lines, start=1)
                if "simply" in line
            ]

        monkeypatch.setattr(style_check, "run_vale", vale)
        before = agenda.build_agenda(draft)
        draft.write_text("# Survey\n\nThe author rewrote this.\n\nIt simply ends.\n")
        after = agenda.build_agenda(draft)
        assert after.stale == []
        assert [(i.id, i.line) for i in after.items] == [(before.items[0].id, 5)]
        assert before.items[0].line == 3

    def test_nothing_refused_renders_no_section(self):
        assert _stale.stale_lines([]) == []

    def test_a_refusal_renders_with_its_anchor(self):
        item = _items.Item("p1", "prose", "Methods", None, 7, True, "'AI' (1x)", {}, span="AI")
        lines = _stale.stale_lines([item])
        assert "## Refused as stale" in lines
        assert any("`p1`" in line and "(Methods)" in line for line in lines)


class TestNoFuzzyRelocation:
    FUZZY = ("difflib", "SequenceMatcher", "get_close_matches", "rapidfuzz", "Levenshtein")

    def test_the_skill_states_the_refusal(self):
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


def _item_dict(id_, cls="prose", unattended=True, summary="a finding") -> dict:
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
    def __init__(self, aid: str = "", chatter: str = "", returncode: int = 0, writes: bool = True):
        self.calls: list[list[str]] = []
        self.aid = aid
        self.chatter = chatter
        self.returncode = returncode
        self.writes = writes
        self.raises: BaseException | None = None
        self.payload: dict = {"findings": []}

    def __call__(self, argv):
        self.calls.append(list(argv))
        if self.chatter:
            print(self.chatter)
        if self.writes and self.aid:
            draft = Path(argv[1] if argv[0] == "scan" else argv[0])
            review.write_json(draft, self.aid, self.payload)
        if self.raises is not None:
            raise self.raises
        return self.returncode


@pytest.fixture
def aid_stubs(monkeypatch):
    stubs = {}
    for name in _sources.AID_NAMES:
        module = _registry.AIDS[name][0]
        stub = _AidStub(name)
        monkeypatch.setattr(module, "main", stub)
        stubs[name] = stub
    return stubs


class TestOneRegistry:
    def test_no_agenda_module_restates_the_aid_list(self):
        names = set(review.AIDS)
        offenders = []
        for path in sorted(Path(_sources.__file__).parent.glob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                items = node.keys if isinstance(node, ast.Dict) else getattr(node, "elts", [])
                if not isinstance(node, (ast.Dict, ast.Tuple, ast.List, ast.Set)):
                    continue
                named = {i.value for i in items if isinstance(i, ast.Constant)} & names
                if len(named) >= 4:
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
        draft = self._draft(isolated_config)
        aid_stubs["support"].raises = OSError("disk went away")
        refreshed, errors = _refresh.refresh_aids(draft)
        assert refreshed["support"] is False
        assert errors["support"] == "OSError: disk went away"

    def test_a_sidecar_written_before_a_raise_is_put_back(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        old = review.write_json(draft, "support", {"findings": ["earlier"]})
        os.utime(old, ns=(1_000_000_000, 1_000_000_000))
        earlier = old.read_bytes()
        aid_stubs["support"].payload = {"findings": ["half-written"]}
        aid_stubs["support"].raises = OSError("disk went away")
        _refresh.refresh_aids(draft)
        assert old.read_bytes() == earlier
        assert old.stat().st_mtime_ns == 1_000_000_000

    def test_a_rewrite_that_kept_the_old_mtime_is_still_put_back(
        self, isolated_config, aid_stubs, monkeypatch
    ):
        draft = self._draft(isolated_config)
        old = review.write_json(draft, "support", {"findings": ["earlier"]})
        os.utime(old, ns=(1_000_000_000, 1_000_000_000))
        earlier = old.read_bytes()

        def same_tick_then_raise(argv):
            review.write_json(draft, "support", {"findings": ["half-written"]})
            os.utime(old, ns=(1_000_000_000, 1_000_000_000))
            raise OSError("disk went away")

        monkeypatch.setattr(_registry.AIDS["support"][0], "main", same_tick_then_raise)
        _refresh.refresh_aids(draft)
        assert old.read_bytes() == earlier

    def test_a_byte_identical_rewrite_gets_its_old_mtime_back(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        old = review.write_json(draft, "support", {"findings": []})
        os.utime(old, ns=(1_000_000_000, 1_000_000_000))
        aid_stubs["support"].raises = OSError("disk went away")
        _refresh.refresh_aids(draft)
        assert old.stat().st_mtime_ns == 1_000_000_000

    def test_a_sidecar_first_written_by_a_raising_run_is_removed(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        aid_stubs["support"].raises = OSError("disk went away")
        _refresh.refresh_aids(draft)
        assert not review.report_path(draft, "support", "json").exists()

    def test_a_raise_that_wrote_nothing_leaves_the_earlier_sidecar_alone(
        self, isolated_config, aid_stubs
    ):
        draft = self._draft(isolated_config)
        old = review.write_json(draft, "support", {"findings": ["earlier"]})
        os.utime(old, ns=(1_000_000_000, 1_000_000_000))
        aid_stubs["support"].writes = False
        aid_stubs["support"].raises = OSError("disk went away")
        _refresh.refresh_aids(draft)
        assert json.loads(old.read_text()) == {"findings": ["earlier"]}
        assert old.stat().st_mtime_ns == 1_000_000_000

    def test_a_raise_with_no_message_is_named_by_its_type(self, isolated_config, aid_stubs):
        draft = self._draft(isolated_config)
        aid_stubs["uncited"].raises = KeyError()
        assert _refresh.refresh_aids(draft)[1] == {"uncited": "KeyError"}

    @pytest.mark.parametrize("exc", [SystemExit(2), KeyboardInterrupt()], ids=["exit", "ctrl-c"])
    def test_an_argparse_exit_or_an_interrupt_still_propagates(
        self, isolated_config, aid_stubs, exc
    ):
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
        before = [_item_dict("a", cls="uncited-claim", unattended=False)]
        resolved, _, _, accepted, _, _ = _recheck.compare([], before, {"a"})
        assert (resolved, accepted) == ([], before)

    def test_an_item_that_really_went_away_is_still_resolved(self):
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

    def test_a_swap_is_visible_from_the_payload(self):
        groups = (
            [_item_dict("r")],
            [],
            [_item_dict("n"), _item_dict("s", cls="candidate", unattended=False)],
            [],
        )
        payload = _recheck.recheck_payload(
            Path("content/drafts/t/s.md"), "b.json", groups, (1, 1), []
        )
        assert payload["objective_delta"] == 0
        assert payload["objective_new"] == 1

    def test_no_unattended_arrival_gives_zero_new(self):
        groups = ([_item_dict("r")], [], [_item_dict("s", unattended=False)], [])
        payload = _recheck.recheck_payload(
            Path("content/drafts/t/s.md"), "b.json", groups, (1, 0), []
        )
        assert payload["objective_new"] == 0

    def test_text_states_the_unattended_arrivals(self):
        groups = ([_item_dict("r")], [], [_item_dict("n")], [])
        text = _recheck.format_recheck("b.json", groups, (1, 1))
        assert "1 -> 1 (+0), 1 new" in text

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

    def test_json_reports_a_swap_as_one_new_objective_item(
        self, isolated_config, monkeypatch, capsys, tmp_path, aid_stubs
    ):
        draft = self._draft(isolated_config, monkeypatch)
        finding = {"rule": "chitragupta.DefectMarkers", "match": "prose", "line": 3, "count": 1}
        monkeypatch.setattr(
            agenda._sources.style_check,
            "check",
            lambda d, override=None, propose=True: {"findings": [finding], "vale_error": None},
        )
        baseline = self._baseline_file(tmp_path, [_item_dict("gone")])
        assert agenda.main([str(draft), "--baseline", str(baseline), "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert [item["id"] for item in payload["resolved"]] == ["gone"]
        assert payload["objective_delta"] == 0
        assert payload["objective_new"] == 1

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
        draft = self._draft(isolated_config, monkeypatch)
        baseline = self._baseline_file(tmp_path, [])
        agenda.main([str(draft), "--baseline", str(baseline)])
        filed = json.loads(review.report_path(draft, "agenda", "json").read_text())
        assert "--baseline" not in filed["command"]
        assert filed["command"] == shlex.join(
            ["python", "-m", "chitragupta.review", "agenda", str(draft)]
        )

    def test_a_baseline_at_the_path_this_run_overwrites_is_still_compared_against(
        self, isolated_config, monkeypatch, capsys, aid_stubs
    ):
        draft = self._draft(isolated_config, monkeypatch)
        own = review.write_json(draft, "agenda", {"aid": "agenda", "items": [_item_dict("gone")]})
        agenda.main([str(draft), "--baseline", str(own), "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["resolved"] == [_item_dict("gone")]
        assert json.loads(own.read_text())["items"] == []

    def test_objective_after_equals_the_agendas_own_objective_class_count(
        self, isolated_config, monkeypatch, capsys, tmp_path, aid_stubs
    ):
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
    RUN = "these exact borrowed words"

    def _draft(self, isolated_config, monkeypatch) -> Path:
        draft = content_draft(isolated_config, "drafts/t/survey.md")
        draft.write_text(f"# Survey\n\nSome prose with {self.RUN} in it.\n")
        monkeypatch.setattr(
            agenda._sources.style_check,
            "check",
            lambda d, override=None, propose=True: {"findings": [], "vale_error": None},
        )
        dossier.log_retrieval(draft, "draft", "digital twin", 5, 3, 100)
        return draft

    def _old_sidecar(self, draft, aid, finding) -> None:
        path = review.write_json(draft, aid, {"findings": [finding]})
        os.utime(path, (1_000_000, 1_000_000))

    def _short_run(self) -> dict:
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
        draft = self._draft(isolated_config, monkeypatch)
        assert agenda.main([str(draft), "--baseline", str(tmp_path / "nope.json")]) == 2
        assert "sync" not in capsys.readouterr().err

    def test_the_bare_mode_still_runs_without_a_ledger(
        self, isolated_config, monkeypatch, capsys, aid_stubs
    ):
        draft = self._draft(isolated_config, monkeypatch)
        assert agenda.main([str(draft)]) == 0
        assert review.report_path(draft, "agenda", "json").is_file()


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
    def _every_class_with_a_span(self) -> set[str]:
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
        draft = self._draft(isolated_config, monkeypatch)
        before = agenda.build_agenda(draft).objective_class_count
        agenda.main([str(draft), "--accept", self._only_id(draft)])
        capsys.readouterr()
        assert agenda.build_agenda(draft).objective_class_count == before

    def test_baseline_reports_an_accepted_item_as_accepted_not_resolved(
        self, isolated_config, monkeypatch, capsys, tmp_path, aid_stubs, refreshable
    ):
        draft = self._draft(isolated_config, monkeypatch)
        item_id = self._only_id(draft)
        agenda.main([str(draft), "--accept", item_id])
        capsys.readouterr()
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

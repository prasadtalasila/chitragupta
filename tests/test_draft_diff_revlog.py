"""Tests for chitragupta/draft_diff's revision-log linking and hand-edit flag.

`entries()` and `attach()` are pure, so most tests build a short
`revisions.md` and a `ChangeReport` with hand-made `SectionChange`s. The
two `hand_edited()` tests need a real dossier, since the stamp lives in
its `scope.md`.
"""

from chitragupta import config, dossier
from chitragupta.dossier import _create, _draft_fingerprint
from chitragupta.draft_diff._compare import ChangeReport, SectionChange
from chitragupta.draft_diff._revlog import LogEntry, attach, entries, hand_edited
from chitragupta.draft_diff._views import VersionView

_LOG = """# Revisions

<!-- Append-only, newest last. 2026-01-01 inside a comment is no entry. -->

2026-08-14 -- copy-edit: British spelling throughout

Converted to en-GB.

## 2026-11-12 -- shorten §4

Cut the integration section by a third.

Sections: 4. Integrating with everything else, 5a
"""


def _view(date=""):
    return VersionView(ref="001", label="", date=date, text="", suffix=".md", figures=None)


def _report(*changes):
    return ChangeReport(
        old=_view("2026-11-01"),
        new=_view(),
        sections=list(changes),
        citekeys_added=[],
        citekeys_dropped=[],
        figures=None,
    )


def _sections():
    return [
        SectionChange("1. Background", "unchanged", 0),
        SectionChange("4. Integrating with everything else", "changed", 12),
        SectionChange("5a. A worked estimate", "added", 40),
        SectionChange("6. Outlook", "changed", 3),
        SectionChange("7. Old notes", "removed", 20),
    ]


def test_entries_parse_heading_and_plain_date_forms():
    parsed = entries(_LOG)
    assert [(e.date, e.title) for e in parsed] == [
        ("2026-08-14", "copy-edit: British spelling throughout"),
        ("2026-11-12", "shorten §4"),
    ]


def test_sections_line_is_split_on_commas():
    assert entries(_LOG)[1].sections == ["4. Integrating with everything else", "5a"]


def test_entry_without_sections_line_has_none():
    assert entries(_LOG)[0].sections == []


def test_attach_links_entry_to_named_changed_sections():
    report = _report(*_sections())
    log = [LogEntry("2026-11-12", "shorten §4", ["4. integrating with everything else "])]
    attach(report, log, "2026-11-01")
    by_title = {c.title: c.log for c in report.sections}
    assert by_title["4. Integrating with everything else"] == ["2026-11-12 shorten §4"]
    assert by_title["6. Outlook"] == []
    assert report.log_entries == ["2026-11-12 shorten §4"]
    assert report.unmatched_log_sections == []


def test_attach_matches_by_heading_number_too():
    report = _report(*_sections())
    attach(report, [LogEntry("2026-11-12", "rework", ["§4", "5A", "1"])], "2026-11-01")
    by_title = {c.title: c.log for c in report.sections}
    assert by_title["4. Integrating with everything else"] == ["2026-11-12 rework"]
    assert by_title["5a. A worked estimate"] == ["2026-11-12 rework"]
    # Named but unchanged: matched, so not reported, and nothing to attach.
    assert by_title["1. Background"] == []
    assert report.unmatched_log_sections == []


def test_attach_reports_names_matching_no_heading():
    report = _report(*_sections())
    log = [LogEntry("2026-11-12", "rework", ["9", "Conclusions", "7. Old notes", "9"])]
    attach(report, log, "2026-11-01")
    # A removed section's title is matched; it just has nowhere to attach.
    assert report.unmatched_log_sections == ["9", "Conclusions"]
    assert all(not c.log for c in report.sections)


def test_unlogged_lists_changed_sections_no_entry_names():
    report = _report(*_sections())
    attach(report, entries(_LOG), "2026-11-01")
    assert report.unlogged == ["6. Outlook"]


def test_entries_before_baseline_are_ignored():
    report = _report(*_sections())
    attach(report, entries(_LOG), "2026-11-12")  # the baseline's own day counts
    assert report.log_entries == ["2026-11-12 shorten §4"]
    late = _report(*_sections())
    attach(late, entries(_LOG), "2026-11-13")
    assert late.log_entries == []
    assert late.unlogged == [
        "4. Integrating with everything else",
        "5a. A worked estimate",
        "6. Outlook",
    ]


def test_file_baseline_attaches_nothing():
    report = _report(*_sections())
    attach(report, entries(_LOG), "")
    assert report.log_entries == []
    assert all(not c.log for c in report.sections)


def _draft():
    path = config.DRAFTS_DIR / "dt" / "survey.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Survey\n\n## 1. Background\n\nText.\n", encoding="utf-8")
    dossier.init(path, "survey")
    return path


def test_hand_edited_true_when_stamp_differs(isolated_config):
    draft = _draft()
    _draft_fingerprint.stamp(draft)
    assert not hand_edited(draft)
    draft.write_text(draft.read_text(encoding="utf-8") + "\nA hand edit.\n", encoding="utf-8")
    assert hand_edited(draft)


def test_hand_edited_false_without_a_stamp(isolated_config):
    draft = _draft()
    draft.write_text("# Survey\n\nRewritten entirely.\n", encoding="utf-8")
    assert not hand_edited(draft)


def test_revisions_template_names_the_sections_line():
    sentence = (
        'End each entry with a line "Sections: <heading>, <heading>" naming every '
        "section it changed; draft diff links entries to sections through it."
    )
    assert sentence in " ".join(_create._REVISIONS_TEMPLATE.split())
    # The template itself parses to no entries.
    assert entries(_create._REVISIONS_TEMPLATE) == []

"""Tests for chitragupta/draft_diff's change report as Markdown and JSON.

Every report here is built by hand from `SectionChange`s and
`FigureChange`s, so each test states exactly what the writer is given
and reads only what it writes.
"""

import json
import re

import pytest

from chitragupta.draft_diff._compare import ChangeReport, FigureChange, SectionChange
from chitragupta.draft_diff._report import header, to_json, to_markdown
from chitragupta.draft_diff._views import VersionView


def _view(ref="004", label="shorten §4", date="2026-11-12", text="old body"):
    return VersionView(ref=ref, label=label, date=date, text=text, suffix=".md", figures={})


def _report(**fields):
    defaults = dict(
        old=_view(),
        new=_view(ref="current draft", label="", date="", text="new body"),
        sections=[
            SectionChange("(before the first heading)", "unchanged", 0),
            SectionChange("1. Background", "changed", 12, ["2026-11-12 shorten §4"]),
            SectionChange("2. Methods", "unchanged", 0),
            SectionChange("3. Old results", "removed", 30),
            SectionChange("3. Results", "added", 40),
            SectionChange("4. Discussion", "moved", 0),
        ],
        citekeys_added=[("sample_dt_sync_2023", "3. Results")],
        citekeys_dropped=[("sample_std_interop_2021", "no longer in the corpus")],
        figures=[
            FigureChange("pipeline", "redrawn", "tikz only"),
            FigureChange("loop", "added", ""),
            FigureChange("ghost", "missing", "", "new"),
        ],
        log_entries=["2026-11-12 shorten §4"],
        unmatched_log_sections=["9. Appendix"],
        hand_edits=True,
    )
    defaults.update(fields)
    return ChangeReport(**defaults)


def _summary(markdown):
    """The summary paragraph as it renders: its soft line breaks as spaces."""
    lines = markdown.splitlines()
    return " ".join(lines[2 : lines.index("", 2)])


def _headings(markdown):
    return [line for line in markdown.splitlines() if line.startswith("#")]


def test_markdown_sections_in_order_and_summary_counts():
    markdown = to_markdown(_report())
    lines = markdown.splitlines()
    assert lines[0] == "# Changes since 004 · shorten §4 · 2026-11-12 — review copy"
    # 82 words; of the new draft's 5 sections 3 differ, and the removed
    # one is counted on its own.
    summary = (
        "82 words changed in 3 of 5 sections, 1 removed"
        " · citekeys +1 −1 · figures 1 redrawn, 1 added"
    )
    assert _summary(markdown) == summary
    assert "The draft differs from its last dossier stamp." in lines
    assert _headings(markdown) == [
        lines[0],
        "## Revision log",
        "## Sections",
        "## Citekeys",
        "## Figures",
        "## Needs a log entry",
    ]
    assert "- 2026-11-12 shorten §4" in lines
    assert "Not matched to any heading: 9. Appendix" in lines
    assert "- changed: 1. Background (12 words)" in lines
    assert "  - ↳ 2026-11-12 shorten §4" in lines
    assert "- removed: 3. Old results (30 words)" in lines
    assert "- moved: 4. Discussion" in lines
    assert "2 unchanged" in lines
    assert "2. Methods" not in markdown
    assert "- Added `sample_dt_sync_2023` in 3. Results" in lines
    assert "- Dropped `sample_std_interop_2021`: no longer in the corpus" in lines
    assert "- `pipeline`: redrawn (tikz only)" in lines
    assert "- `loop`: added" in lines
    assert "- `ghost`: missing in new" in lines
    # Needs a log entry: added and moved sections no entry names, in order.
    tail = lines[lines.index("## Needs a log entry") :]
    assert tail == ["## Needs a log entry", "", "- added: 3. Results", "- moved: 4. Discussion"]
    assert markdown.endswith("\n") and not markdown.endswith("\n\n")


def test_markdown_omits_optional_parts_and_says_none():
    report = _report(
        sections=[SectionChange("1. Background", "changed", 1, ["2026-11-12 a"])],
        citekeys_added=[],
        citekeys_dropped=[],
        figures=[],
        log_entries=[],
        unmatched_log_sections=[],
        hand_edits=False,
    )
    markdown = to_markdown(report)
    lines = markdown.splitlines()
    expected = "1 word changed in 1 of 1 sections · citekeys +0 −0 · figures 0 redrawn"
    assert _summary(markdown) == expected
    assert "The draft differs from its last dossier stamp." not in markdown
    assert "## Needs a log entry" not in markdown
    assert "Not matched" not in markdown
    assert "No entries since the baseline." in lines
    assert "No citekeys added or dropped." in lines
    assert "No figures changed." in lines
    assert "0 unchanged" not in markdown


def test_markdown_no_changes_is_two_lines():
    report = _report(
        sections=[SectionChange("1. Background", "unchanged", 0)],
        citekeys_added=[],
        citekeys_dropped=[],
        figures=[],
        log_entries=["2026-11-12 shorten §4"],
        hand_edits=True,
    )
    assert to_markdown(report) == (
        "# Changes since 004 · shorten §4 · 2026-11-12 — review copy\n\nNo changes.\n"
    )


def test_markdown_unknown_figures_says_so():
    markdown = to_markdown(_report(figures=None))
    lines = markdown.splitlines()
    expected = "82 words changed in 3 of 5 sections, 1 removed · citekeys +1 −1 · figures unknown"
    assert _summary(markdown) == expected
    figures = lines[lines.index("## Figures") :]
    assert figures[:3] == ["## Figures", "", "Baseline figures unknown."]


def test_markdown_has_no_timestamp_besides_baseline_date():
    report = _report(
        new=_view(ref="005", label="expand §2", date="2026-11-13"),
        log_entries=[],
        sections=[SectionChange("1. Background", "changed", 3)],
    )
    markdown = to_markdown(report)
    assert set(re.findall(r"\d{4}-\d{2}-\d{2}", markdown)) == {"2026-11-12"}
    assert not re.search(r"\d{1,2}:\d{2}", markdown)


def test_json_round_trips_counts_and_lists():
    report = _report()
    data = json.loads(json.dumps(to_json(report)))
    assert data["header"] == header(report)
    assert data["words_changed"] == 82
    assert data["has_changes"] is True
    assert data["unlogged"] == ["3. Results", "4. Discussion"]
    assert data["old"] == {
        "ref": "004",
        "label": "shorten §4",
        "date": "2026-11-12",
        "suffix": ".md",
    }
    assert data["new"]["ref"] == "current draft"
    assert "text" not in data["old"] and "text" not in data["new"]
    assert data["sections"][1] == {
        "title": "1. Background",
        "kind": "changed",
        "words_changed": 12,
        "log": ["2026-11-12 shorten §4"],
    }
    assert len(data["sections"]) == 6
    assert data["citekeys_added"] == [{"key": "sample_dt_sync_2023", "section": "3. Results"}]
    assert data["citekeys_dropped"] == [
        {"key": "sample_std_interop_2021", "status": "no longer in the corpus"}
    ]
    assert data["figures"][0] == {
        "name": "pipeline",
        "kind": "redrawn",
        "forms": "tikz only",
        "side": "",
    }
    assert data["log_entries"] == ["2026-11-12 shorten §4"]
    assert data["unmatched_log_sections"] == ["9. Appendix"]
    assert data["hand_edits"] is True


def test_json_unknown_figures_is_null():
    assert to_json(_report(figures=None))["figures"] is None


def test_header_forms_for_number_label_and_file():
    assert header(_report()) == "Changes since 004 · shorten §4 · 2026-11-12 — review copy"
    file_side = _view(ref="old-survey.md", label="", date="")
    assert header(_report(old=file_side)) == "Changes since old-survey.md — review copy"
    unlabelled = _view(label="")
    assert header(_report(old=unlabelled)) == "Changes since 004 · 2026-11-12 — review copy"


def test_summary_names_added_and_removed_figures_only_when_any():
    only_redrawn = _report(figures=[FigureChange("pipeline", "redrawn", "both")])
    assert _summary(to_markdown(only_redrawn)).endswith("· figures 1 redrawn")
    gone = _report(figures=[FigureChange("loop", "removed", "")])
    assert _summary(to_markdown(gone)).endswith("· figures 0 redrawn, 1 removed")


def test_summary_counts_removed_sections_apart():
    report = _report(
        sections=[
            SectionChange("A", "removed", 5),
            SectionChange("B", "removed", 4),
            SectionChange("C", "added", 10),
        ]
    )
    summary = _summary(to_markdown(report))
    assert summary.startswith("19 words changed in 1 of 1 sections, 2 removed · ")


def test_regenerated_references_sit_outside_the_count_and_the_log():
    report = _report(
        sections=[
            SectionChange("1. Background", "changed", 3),
            SectionChange("2. Methods", "unchanged", 0),
            SectionChange("References", "regenerated", 0),
        ]
    )
    markdown = to_markdown(report)
    lines = markdown.splitlines()
    assert _summary(markdown).startswith(
        "3 words changed in 1 of 2 sections, references regenerated · "
    )
    assert "- regenerated: References" in lines
    tail = lines[lines.index("## Needs a log entry") :]
    assert tail == ["## Needs a log entry", "", "- changed: 1. Background"]
    assert to_json(report)["unlogged"] == ["1. Background"]


def test_markdown_figure_only_change_counts_unchanged_sections():
    report = _report(
        sections=[SectionChange("A", "unchanged", 0), SectionChange("B", "unchanged", 0)],
        citekeys_added=[],
        citekeys_dropped=[],
    )
    markdown = to_markdown(report)
    lines = markdown.splitlines()
    assert _summary(markdown).startswith("0 words changed in 0 of 2 sections · ")
    assert lines[lines.index("## Sections") :][:3] == ["## Sections", "", "2 unchanged"]


def test_markdown_with_no_sections_says_so():
    lines = to_markdown(_report(sections=[])).splitlines()
    assert lines[lines.index("## Sections") :][:3] == ["## Sections", "", "No sections."]


# Every report shape the tests above build, for the blank-line check.
_SHAPES = [
    {},
    {"figures": None},
    {"figures": [], "citekeys_added": [], "citekeys_dropped": [], "log_entries": []},
    {"unmatched_log_sections": [], "hand_edits": False},
    {"sections": []},
    {"sections": [SectionChange("A", "unchanged", 0)], "citekeys_added": []},
    {"sections": [SectionChange("A", "removed", 5), SectionChange("C", "added", 10)]},
    {"sections": [SectionChange("1. Background", "changed", 1, ["2026-11-12 a"])]},
    {"sections": [SectionChange("A", "removed", 5), SectionChange("References", "regenerated", 0)]},
    {
        "sections": [SectionChange("A", "unchanged", 0)],
        "citekeys_added": [],
        "citekeys_dropped": [],
        "figures": [],
    },
]


@pytest.mark.parametrize("fields", _SHAPES)
def test_markdown_never_has_two_blank_lines_in_a_row(fields):
    # markdownlint's MD012; a section with an empty body is how it slips in.
    assert "\n\n\n" not in to_markdown(_report(**fields))


@pytest.mark.parametrize("fields", _SHAPES)
def test_markdown_summary_and_rows_fit_80_columns(fields):
    # markdownlint's MD013, for every line the writer itself composes; a
    # long heading title in the draft is the one thing it cannot shorten.
    assert max(map(len, to_markdown(_report(**fields)).splitlines())) <= 80

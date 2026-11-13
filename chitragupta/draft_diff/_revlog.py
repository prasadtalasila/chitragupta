"""Why a section changed: `revisions.md` entries linked to a change report.

An entry starts at a dated line, `## 2026-11-12 -- shorten §4` or the
plain `2026-08-14 -- copy-edit: ...`, and runs to the next. Its
`Sections:` line names the sections it changed, by title or by heading
number, and is what ties an entry to a `SectionChange`. An entry without
one still appears in the report's list of entries; it just explains no
section in particular.

Entries dated on the baseline's own day count as after it: a snapshot
and the revision it opened share a date, and over-inclusion is the safe
direction, since a spurious entry costs a glance and a missing one
leaves a change looking unexplained.

A hand edit is read from the draft fingerprint `dossier stamp` records,
by the same digest it records, so the two can never disagree.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from chitragupta.dossier import dossier_dir
from chitragupta.dossier._draft_fingerprint import recorded_draft_digest
from chitragupta.draft_diff._compare import ChangeReport
from chitragupta.spec import digest

_ENTRY_START = re.compile(r"^(#+\s*)?(\d{4}-\d{2}-\d{2})\s*(?:--|—|-)?\s*(.*)$")

_SECTIONS_LINE = re.compile(r"^\s*Sections:\s*(.*)$")

# A template comment is guidance, never an entry, even if it shows a date.
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

_HEADING_NUMBER = re.compile(r"^\d+[a-z]?(\.\d+)*", re.IGNORECASE)

# The kinds an entry can be attached to. A removed section has no place
# in the new draft, so naming one matches it without attaching anywhere.
_UNATTACHED_KINDS = ("unchanged", "removed")


@dataclass(frozen=True)
class LogEntry:
    date: str  # "YYYY-MM-DD"
    title: str  # the rest of the entry's first line
    sections: list[str]  # from its "Sections:" line; [] when absent


def entries(revisions_md: str) -> list[LogEntry]:
    """Every dated entry in `revisions_md`, in file order."""
    found: list[LogEntry] = []
    for line in _COMMENT.sub("", revisions_md).splitlines():
        if start := _ENTRY_START.match(line):
            found.append(LogEntry(start.group(2), start.group(3).strip(), []))
        elif found and (named := _SECTIONS_LINE.match(line)):
            names = [name.strip() for name in named.group(1).split(",")]
            found[-1].sections.extend(name for name in names if name)
    return found


def _heading_number(text: str) -> str:
    number = _HEADING_NUMBER.match(text)
    return number.group(0).casefold() if number else ""


def _names(name: str, title: str) -> bool:
    """Whether a `Sections:` name means the section titled `title`."""
    if name.casefold() == title.strip().casefold():
        return True
    number = _heading_number(name.removeprefix("§").strip())
    return bool(number) and number == _heading_number(title)


def attach(report: ChangeReport, log: list[LogEntry], since: str) -> None:
    """Link the entries dated on or after `since` to the sections they name.

    `since` is the baseline's date; a file baseline has none, so it is
    "" and nothing is attached: no date says which entries are newer.
    """
    if not since:
        return
    for entry in log:
        if entry.date < since:
            continue
        label = f"{entry.date} {entry.title}"
        report.log_entries.append(label)
        for name in entry.sections:
            named = [c for c in report.sections if _names(name, c.title)]
            if not named and name not in report.unmatched_log_sections:
                report.unmatched_log_sections.append(name)
            for change in named:
                if change.kind not in _UNATTACHED_KINDS and label not in change.log:
                    change.log.append(label)


def hand_edited(draft: Path) -> bool:
    """Whether `draft` moved since `dossier stamp` last recorded it.

    False when nothing was ever stamped: with no baseline there is no
    telling a hand edit from a revision pass.
    """
    recorded = recorded_draft_digest(dossier_dir(draft))
    return recorded is not None and recorded != digest(draft.read_text(encoding="utf-8"))

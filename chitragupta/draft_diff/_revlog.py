"""Why a section changed: `revisions.md` entries linked to a change report.

An entry runs from one dated line to the next; its `Sections:` line
ties it to sections by title or number. Entries dated on the baseline's
day count as after it: a spurious entry costs a glance, a missing one
leaves a change unexplained. Hand edits use `dossier stamp`'s own digest.
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

# The kinds an entry attaches to; a named removed section matches without
# attaching anywhere.
_UNATTACHED_KINDS = ("unchanged", "removed")


@dataclass(frozen=True)
class LogEntry:
    date: str  # "YYYY-MM-DD"
    title: str  # the rest of the entry's first line
    sections: list[str]  # from its "Sections:" line; [] when absent


def entries(revisions_md: str) -> list[LogEntry]:
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
    if name.casefold() == title.strip().casefold():
        return True
    number = _heading_number(name.removeprefix("§").strip())
    return bool(number) and number == _heading_number(title)


def attach(report: ChangeReport, log: list[LogEntry], since: str) -> None:
    """Link the entries dated on or after `since` to the sections they name.

    A file baseline has no date (""), so nothing is attached.
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

    False when never stamped: no baseline to tell edits apart.
    """
    recorded = recorded_draft_digest(dossier_dir(draft))
    return recorded is not None and recorded != digest(draft.read_text(encoding="utf-8"))

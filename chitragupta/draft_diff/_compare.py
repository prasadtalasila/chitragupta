"""The change report between two versions of a draft, computed purely.

Sections pair by (title, occurrence), the title rule the dossier keys
`sections.md` by, with the occurrence added so two sections both called
"Notes" pair first with first and second with second. A rename is
therefore a removal plus an addition: guessing renames would put a
"changed" on two sections that may share nothing.

A section is changed when its words differ, compared as whitespace
tokens, so re-wrapping a paragraph is not a change and a "changed"
section always has a non-zero word count.

`key_status` is passed in so this module never opens the ledger; the
caller says what a dropped key's standing is now.
"""

import difflib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from chitragupta.citation_gate import extract_citekeys_for
from chitragupta.draft_diff import _sections
from chitragupta.draft_diff._sections import Section
from chitragupta.draft_diff._views import FigureForms, VersionView

SectionKind = Literal["added", "removed", "moved", "changed", "unchanged"]

# The kinds a revision log entry is expected to explain.
_LOGGED_KINDS = ("added", "moved", "changed")


@dataclass
class SectionChange:
    title: str
    kind: SectionKind
    words_changed: int
    log: list[str] = field(default_factory=list)


@dataclass
class FigureChange:
    name: str
    kind: Literal["added", "removed", "redrawn", "missing"]
    forms: Literal["both", "tikz only", "ascii only", ""]
    side: str = ""  # for "missing": "old" | "new"


@dataclass
class ChangeReport:
    old: VersionView
    new: VersionView
    sections: list[SectionChange]
    citekeys_added: list[tuple[str, str]]  # (key, section title)
    citekeys_dropped: list[tuple[str, str]]  # (key, its status now)
    figures: list[FigureChange] | None  # None when either side's figures are unknown
    log_entries: list[str] = field(default_factory=list)
    unmatched_log_sections: list[str] = field(default_factory=list)
    hand_edits: bool = False

    @property
    def words_changed(self) -> int:
        return sum(change.words_changed for change in self.sections)

    @property
    def unlogged_sections(self) -> list[SectionChange]:
        """Sections added, moved or changed that no log entry names."""
        return [c for c in self.sections if c.kind in _LOGGED_KINDS and not c.log]

    @property
    def unlogged(self) -> list[str]:
        """Titles of `unlogged_sections`."""
        return [c.title for c in self.unlogged_sections]

    @property
    def has_changes(self) -> bool:
        return bool(
            any(change.kind != "unchanged" for change in self.sections)
            or self.citekeys_added
            or self.citekeys_dropped
            or self.figures
        )


def _words_changed(old: str, new: str) -> int:
    """Words on both sides of every non-equal run between `old` and `new`."""
    matcher = difflib.SequenceMatcher(None, old.split(), new.split(), autojunk=False)
    return sum(
        (i2 - i1) + (j2 - j1) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"
    )


def _lcs(old: list, new: list) -> set:
    """The keys of one longest common subsequence of `old` and `new`.

    On a tie the walk drops from `old`, so of two sections that swapped,
    the later one in the old order is the one reported moved.
    """
    table = [[0] * (len(new) + 1) for _ in range(len(old) + 1)]
    for i, a in enumerate(old):
        for j, b in enumerate(new):
            table[i + 1][j + 1] = (
                table[i][j] + 1 if a == b else max(table[i][j + 1], table[i + 1][j])
            )
    kept, i, j = set(), len(old), len(new)
    while i and j:
        if old[i - 1] == new[j - 1]:
            kept.add(old[i - 1])
            i, j = i - 1, j - 1
        elif table[i - 1][j] >= table[i][j - 1]:
            i -= 1
        else:
            j -= 1
    return kept


def _key(section: Section) -> tuple[str, int]:
    return (section.title, section.occurrence)


def _paired(old: Section, new: Section, in_order: bool) -> SectionChange:
    words = _words_changed(old.body, new.body)
    kind = "changed" if words else ("unchanged" if in_order else "moved")
    return SectionChange(new.title, kind, words)


def _removed(old: list[Section], start: int, stop: int, new_keys: set) -> list[SectionChange]:
    return [
        SectionChange(section.title, "removed", len(section.body.split()))
        for section in old[start:stop]
        if _key(section) not in new_keys
    ]


def _compare_sections(old: list[Section], new: list[Section]) -> list[SectionChange]:
    """Every section, in the new order, each removed one after its old predecessor."""
    old_index = {_key(s): index for index, s in enumerate(old)}
    new_keys = {_key(s) for s in new}
    common = [_key(s) for s in new if _key(s) in old_index]
    in_order = _lcs([_key(s) for s in old if _key(s) in new_keys], common)
    changes, next_old = [], 0
    for section in new:
        index = old_index.get(_key(section))
        if index is None:
            changes.append(SectionChange(section.title, "added", len(section.body.split())))
            continue
        if index >= next_old:
            changes.extend(_removed(old, next_old, index, new_keys))
            next_old = index + 1
        changes.append(_paired(old[index], section, _key(section) in in_order))
    changes.extend(_removed(old, next_old, len(old), new_keys))
    return changes


def _citekeys(view: VersionView) -> list[tuple[int, str]]:
    return extract_citekeys_for(Path(f"draft{view.suffix}"), view.text)


def _compare_citekeys(
    old: VersionView,
    new: VersionView,
    new_sections: list[Section],
    key_status: Callable[[str], str],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    old_keys = dict.fromkeys(key for _, key in _citekeys(old))
    new_first: dict[str, int] = {}
    for line, key in _citekeys(new):
        new_first.setdefault(key, line)
    added = [
        (key, _sections.title_at(new_sections, line))
        for key, line in new_first.items()
        if key not in old_keys
    ]
    dropped_keys = [key for key in old_keys if key not in new_first]
    return added, [(key, key_status(key)) for key in dropped_keys]


def _redrawn(old: FigureForms, new: FigureForms) -> str:
    tikz, ascii_ = old.tikz != new.tikz, old.ascii != new.ascii
    if tikz and ascii_:
        return "both"
    return "tikz only" if tikz else ("ascii only" if ascii_ else "")


def _drawn(forms: FigureForms) -> bool:
    return forms.tikz is not None or forms.ascii is not None


def _compare_figures(old: dict, new: dict) -> list[FigureChange]:
    changes = []
    for name in dict.fromkeys([*old, *new]):
        missing = [
            side
            for side, held in (("old", old), ("new", new))
            if name in held and not _drawn(held[name])
        ]
        if len(missing) == 2:
            # Undrawn on both sides is no change between them; the draft's
            # own checks are what report a figure never drawn.
            continue
        if missing:
            changes.extend(FigureChange(name, "missing", "", side) for side in missing)
        elif name not in new:
            changes.append(FigureChange(name, "removed", ""))
        elif name not in old:
            changes.append(FigureChange(name, "added", ""))
        elif forms := _redrawn(old[name], new[name]):
            changes.append(FigureChange(name, "redrawn", forms))
    return changes


def compare(old: VersionView, new: VersionView, key_status: Callable[[str], str]) -> ChangeReport:
    """What changed from `old` to `new`; `key_status(key)` says a dropped key's standing."""
    old_sections = _sections.split(old.text, old.suffix)
    new_sections = _sections.split(new.text, new.suffix)
    added, dropped = _compare_citekeys(old, new, new_sections, key_status)
    # Unknown on either side is unknown: an old figure with no new side
    # to look at is not a removal.
    known = old.figures is not None and new.figures is not None
    figures = _compare_figures(old.figures, new.figures) if known else None
    return ChangeReport(
        old=old,
        new=new,
        sections=_compare_sections(old_sections, new_sections),
        citekeys_added=added,
        citekeys_dropped=dropped,
        figures=figures,
    )

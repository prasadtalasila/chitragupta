"""Walk figure files and bring each one's house block up to date (#1013).

A walk, with no paths or through a directory named on the command line,
takes every `*.tex` directly inside a directory named `figures`: docs/WRITING-STANDARDS.md §10
puts every figure file at `content/drafts/<topic>/figures/<name>.tex`,
and a book's units nest one level deeper. A draft's own `.tex` is not a
figure, and a `tikzpicture` in its `verbatim` listing must not become a
place to stamp the block. A file named on the command line is taken as
given, which is how `assets/tikz/*.tex` is reached.

A read-only file is reported rather than replaced: `os.replace` would
swap it out on POSIX, mode and all, which is not what read-only asked.

A symlink is reported and skipped rather than followed: a write through
it would land outside the tree the user named. A file that cannot be
read or written is reported and the walk carries on to the next, the way
every aid in the review layer reports and carries on -- one unreadable
figure is never the reason the other twenty stay stale.
"""

import difflib
import os
from dataclasses import dataclass
from pathlib import Path

from chitragupta import config
from chitragupta._atomic_write import write_atomically
from chitragupta.figure._block import House, Region, State, classify, newer_than_install, stamp


@dataclass(frozen=True)
class Outcome:
    """What `sync_file` did, or in `--check` mode would do, to one file.

    `action` is one of `current`, `stamped`, `refreshed`, `missing`,
    `stale` (the last two in check mode only), `modified`, `malformed`,
    `no-picture` or `skipped`; `detail` says why, or carries the diff.
    """

    path: Path
    action: str
    detail: str = ""


def figure_files(paths: list[Path]) -> list[Path]:
    """The figure files to sync, sorted and deduplicated.

    No paths means every `figures/*.tex` under the drafts directory. A
    directory contributes every `figures/*.tex` beneath it; a file is
    taken as given.
    """
    found: set[Path] = set()
    for path in paths or [config.DRAFTS_DIR]:
        if path.is_dir():
            found.update(p for p in path.rglob("*.tex") if p.parent.name == "figures")
        elif paths:
            found.add(path)
    return sorted(found)


def _diff(region: str, house: House, name: str) -> str:
    """The edit inside a modified region, as a diff from the house block."""
    lines = difflib.unified_diff(
        house.text.splitlines(keepends=True),
        region.replace("\r\n", "\n").splitlines(keepends=True),
        fromfile=f"house block v{house.version}",
        tofile=name,
    )
    return "".join(lines)


def _read(path: Path) -> str | Outcome:
    """The file's text, or the `skipped` outcome that says why not."""
    if path.is_symlink():
        return Outcome(path, "skipped", "a symlink; sync the file it points to directly")
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return Outcome(path, "skipped", "not UTF-8")
    except OSError as exc:
        return Outcome(path, "skipped", str(exc))


def _refusal(path: Path, text: str, region: Region, house: House) -> Outcome | None:
    """The outcome for a region sync must not touch, else `None`."""
    if region.state is State.MALFORMED:
        return Outcome(path, "malformed", "markers unpaired or repeated; not touched")
    if region.state is State.MODIFIED:
        diff = _diff(text[region.start : region.end], house, path.name)
        if (region.marker_version or 0) > house.version:
            diff = newer_than_install(region, house) + "\n" + diff
        return Outcome(path, "modified", diff)
    return None


def sync_file(path: Path, house: House, *, check: bool) -> Outcome:
    """Stamp or refresh one file's block, or report why not.

    In check mode nothing is written, and a file that would be changed
    reports `missing` or `stale` instead.
    """
    text = _read(path)
    if isinstance(text, Outcome):
        return text
    region = classify(text, house)
    if region.state is State.CURRENT:
        return Outcome(path, "current")
    refusal = _refusal(path, text, region, house)
    if refusal is not None:
        return refusal
    new = stamp(text, house)
    if new is None:
        return Outcome(path, "no-picture", "no \\usetikzlibrary or tikzpicture to stamp above")
    if check:
        return Outcome(path, region.state.value)
    if not os.access(path, os.W_OK):
        return Outcome(path, "skipped", "read-only")
    try:
        write_atomically(path, new.encode("utf-8"))
    except OSError as exc:
        return Outcome(path, "skipped", str(exc))
    return Outcome(path, "stamped" if region.state is State.MISSING else "refreshed")


def run(paths: list[Path], house: House, *, check: bool) -> list[Outcome]:
    """`sync_file` over every file `figure_files(paths)` names."""
    return [sync_file(path, house, check=check) for path in figure_files(paths)]

"""Fail the test session if it wrote into the checkout's real content/ (#862).

`isolated_config` moves every path constant under tmp_path, but only for
a test that asks for it, and a test that forgets writes the user's real
retrieval index, ledger or pipeline lock -- silently, because a run that
passes leaves nothing to read. Two groups did exactly that, and the
unversioned-data scan could not see it: it looks for *reads* of
config.toml and the .bib, statically.

So this checks the effect rather than the code: a snapshot of every
path under content/ at session start, compared at session finish. That
is cheap enough to run on every session where a per-test check would
not be -- a real checkout's content/ holds thousands of parsed files --
at the cost of naming the path rather than the test. The path is
usually enough: each file there has one writer.

Size and mtime rather than a hash: a test that rewrites a file with
identical bytes has still written into a tree it had no business
touching, and a hash of a 14 MB index on every session is not free.
"""

import os
from pathlib import Path

import pytest

_BASELINE = pytest.StashKey["tuple[Path, dict[str, tuple[int, int]]]"]()


def snapshot(root: Path) -> "dict[str, tuple[int, int]]":
    """(size, mtime_ns) of every entry under `root`, keyed by its
    relative path; directories carry a trailing `/` and size -1.

    Directories are in it so an empty one left behind by a
    `mkdir(parents=True)` still counts as a change. A missing root is
    an empty snapshot, not an error: a fresh `chitragupta init` project
    has no content/ until something writes one.
    """
    entries = {}
    for dirpath, dirnames, filenames in os.walk(root):
        base = Path(dirpath)
        for name in dirnames:
            relative = (base / name).relative_to(root).as_posix() + "/"
            entries[relative] = (-1, (base / name).stat().st_mtime_ns)
        for name in filenames:
            stat = (base / name).stat()
            entries[(base / name).relative_to(root).as_posix()] = (stat.st_size, stat.st_mtime_ns)
    return entries


def changes(before: dict, after: dict) -> "list[str]":
    """Every created, deleted or modified path, sorted by path.

    A directory's own mtime moves whenever an entry is added inside it,
    so a created file would otherwise also report its parent as
    modified; only a directory created or deleted outright is named.
    """
    found = []
    for path in sorted(before.keys() | after.keys()):
        if path not in before:
            found.append(f"created {path}")
        elif path not in after:
            found.append(f"deleted {path}")
        elif before[path] != after[path] and not path.endswith("/"):
            found.append(f"modified {path}")
    return found


def record(session, root: Path) -> None:
    """Take the baseline. Called from conftest's `pytest_sessionstart`,
    before any fixture has had a chance to move `config.CONTENT_DIR`."""
    session.stash[_BASELINE] = (root, snapshot(root))


def verify(session) -> None:
    """Compare against the baseline and fail the session on any change.

    Only an otherwise-passing session is turned red: an interrupted or
    already-failing run keeps the exit code that says so, and still
    gets the paths reported.
    """
    root, before = session.stash[_BASELINE]
    found = changes(before, snapshot(root))
    if not found:
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    lines = [
        # Ends the progress-dots line, which write_line does not do here.
        "",
        f"The test session wrote into the real {root} (#862):",
        *(f"  {line}" for line in found),
        "A test that touches a config path must take the `isolated_config` fixture.",
        "If a real pipeline run was writing in this checkout at the same time, that is the cause.",
    ]
    if reporter is not None:
        for line in lines:
            reporter.write_line(line, red=True)
    if session.exitstatus == pytest.ExitCode.OK:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED

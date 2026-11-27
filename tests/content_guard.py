import os
import stat
from pathlib import Path

import pytest

_BASELINE = pytest.StashKey["tuple[Path, dict[str, tuple[int, int]]]"]()


def snapshot(root: Path) -> "dict[str, tuple[int, int]]":
    entries = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            path = Path(dirpath) / name
            try:
                info = os.lstat(path)
            except FileNotFoundError:
                continue
            relative = path.relative_to(root).as_posix()
            if stat.S_ISDIR(info.st_mode):
                entries[relative + "/"] = (-1, info.st_mtime_ns)
            else:
                entries[relative] = (info.st_size, info.st_mtime_ns)
    return entries


def changes(before: dict, after: dict) -> "list[str]":
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
    session.stash[_BASELINE] = (root, snapshot(root))


def verify(session) -> None:
    baseline = session.stash.get(_BASELINE, None)
    if baseline is None:
        return
    root, before = baseline
    found = changes(before, snapshot(root))
    if not found:
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    lines = [
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

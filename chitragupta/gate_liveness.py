"""Is the automatic gate actually running? -- asked by the gate a person or skill runs (#812).

Two silent ways a PostToolUse gate is off: a launcher that cannot start
(neither the hook nor the preflight can report it, #197; this runs on an
interpreter that demonstrably started), and a hook that never fires
(Codex skips untrusted project hooks; shell-written drafts bypass file
hooks). An unfired gate looks exactly like a pass.

For the second, a hook-invoked gate (`CHITRAGUPTA_GATE_CALLER=hook`)
records each draft's text hash under `content/.gate-seen/`, one file per
draft so parallel hooks cannot lose each other's record; a hand run warns
about a draft no hook has seen since it changed. Only where a harness is
configured. Detection, never enforcement: nothing here changes the
verdict. Standard library only.
"""

import hashlib
import os
import sys
from pathlib import Path

from chitragupta import config, hook_launchers, launcher_configs

GATE_CALLER_ENV = "CHITRAGUPTA_GATE_CALLER"
PLUGIN = ".opencode/plugins/chitragupta-gate.js"
RECORD_DIR = ".gate-seen"
DEAD_LAUNCHER = (
    "WARNING: {fault} This gate ran because something invoked it, but it is "
    "no longer running automatically after every write to a draft -- see "
    "docs/HOOKS.md."
)
UNSEEN = (
    "WARNING: no automatic gate has checked {path} since it last changed. "
    "Either it was written outside the agent's file tools (a shell command), "
    "or the harness is not running this project's hooks -- on Codex, project "
    "hooks run only once you have trusted them. This run checked it; see "
    "docs/HARNESS.md."
)


def observe(paths: list[str]) -> None:
    """Record `paths` when a hook is the caller; otherwise warn about what it missed."""
    current = {_key(p): _digest(p) for p in paths}
    records = config.CONTENT_DIR / RECORD_DIR
    if os.environ.get(GATE_CALLER_ENV) == "hook":
        for key, digest in current.items():
            if digest is not None:
                _write(records / _record_name(key), digest)
        return
    # Found as hook_launchers finds it, so a dead launcher is reported there.
    for fault in launcher_configs.faults(hook_launchers.SETTINGS.parent.parent):
        print(DEAD_LAUNCHER.format(fault=fault), file=sys.stderr)
    if not _harness_configured(config.CONTENT_DIR.parent):
        return
    for key, digest in current.items():
        if digest is not None and _read(records / _record_name(key)) != digest:
            print(UNSEEN.format(path=key), file=sys.stderr)


def _harness_configured(root: Path) -> bool:
    return bool(launcher_configs.present(root)) or (root / PLUGIN).is_file()


def _record_name(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _read(path: Path) -> "str | None":
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None  # missing or unreadable: as if no hook had ever fired


def _write(path: Path, digest: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(digest, encoding="utf-8")
    except OSError:
        # Costs only a spurious warning later; must never fail the gate.
        pass


def _key(path: str) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(config.CONTENT_DIR.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _digest(path: str) -> "str | None":
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None  # the gate itself reports a draft it cannot read

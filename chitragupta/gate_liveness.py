"""Is the automatic gate actually running? -- asked by the gate a person or skill runs (#812).

Two ways a PostToolUse gate can be off without anyone noticing, and the
hand-run gate is the one place both can be seen from:

- **A launcher that cannot start.** The hook cannot report its own
  failure to spawn, and neither can the session preflight written to
  report it, since it is launched by the same interpreter name (#197).
  This runs on an interpreter that has demonstrably started, so its
  warning survives the launcher being dead. Read from every harness's
  config (`launcher_configs`), not only Claude Code's.
- **A hook that starts fine and never fires.** Codex makes that the
  default state of a fresh project: project hooks are skipped until the
  user trusts them, and trust is recorded against the hook's hash, so
  editing a hook makes it untrusted again. A draft written through a
  shell command is never seen by any harness's file-tool hook either. An
  unfired gate looks exactly like one that passed.

For the second, the gate hook sets `CHITRAGUPTA_GATE_CALLER=hook` and the
gate records what it checked under `content/.gate-seen/`; a later run by
hand compares each draft's current text with that record and warns about
a draft no hook has seen since it last changed. One small file per draft,
named by a hash of the draft's path and holding a hash of its text, so
two hooks gating different drafts at once -- parallel subagents writing
sections -- never read and rewrite the same file and lose each other's
record. Only in a project with a
harness configured -- a launcher config or the OpenCode plugin next to
`content/` -- since elsewhere no hook was ever expected to fire.

This is detection, never enforcement: nothing here changes the gate's
verdict or exit code, and a spoofed variable or a hand-edited record
hides only this warning. Standard library only, like the gate.
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
    # The project this command runs in, found the way hook_launchers has
    # always found it, so a dead launcher is reported exactly where it was.
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
        # A record that cannot be written costs only a spurious warning on
        # the next hand run; it must never fail the gate the hook is running.
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

"""Can the hooks this repository registers actually start?

A hook whose launcher does not resolve fails **silently** (measured
2026-08-15), and the citation gate is the only automatic enforcement of
the citekey rule, so drafts would land ungated with every test passing.
`session_start_hook.py` cannot check this alone (#197): it is launched
by the interpreter name it vets. So the check lives here, where
`draft gate` can also make it.

docs/HOOKS.md's one named exception: layer 1 may read the *launcher
config*, never a payload. `faults()` also probes that an interpreter on
PATH can import the package. Imports only `programs` and
`import_probe`: `chitragupta.config` raises without a `config.toml`,
which would break the tier-1 promise and the preflight in a fresh clone.
"""

import json
import shutil
from pathlib import Path

from chitragupta import import_probe, programs


def _project_root() -> Path:
    """Where `.claude/settings.json` lives, found without importing config.

    A deliberate copy of config.py's marker walk (see the module
    docstring). Not from `__file__`: installed, that is site-packages.
    """
    for candidate in (Path.cwd().resolve(), *Path.cwd().resolve().parents):
        if (candidate / "config.toml").is_file():
            return candidate
    return Path(__file__).resolve().parent.parent


SETTINGS = _project_root() / ".claude" / "settings.json"


def faults(settings_path: Path = SETTINGS) -> list[str]:
    """Registered hook commands that cannot start, read from a settings file.

    Static: no test or CI run executes a launcher. Absent or unreadable
    settings mean nothing to check. A clean result says each launcher
    *can* start, never that the harness spawned one. Deduplicated, since
    one missing interpreter is one problem however many entries name it.
    A launcher that resolves is also probed once per program with
    `-c "import chitragupta"`, as it may not be the venv's interpreter.
    """
    try:
        events = json.loads(Path(settings_path).read_text(encoding="utf-8"))["hooks"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    found, launchers = [], []
    for entries in _items(events):
        for entry in _items(entries):
            for hook in _items(entry.get("hooks") if isinstance(entry, dict) else None):
                if not isinstance(hook, dict):
                    continue
                found.extend(_launcher_fault(hook))
                program = _program_name(hook)
                if program and program not in launchers:
                    launchers.append(program)
    env = import_probe.probe_env(settings_path)
    for program in launchers:
        if import_probe.is_python_interpreter(program) and import_probe.is_bare_command(program):
            fault = import_probe.import_fault(program, env)
            if fault:
                found.append(fault)  # pragma: no cover-windows
    return list(dict.fromkeys(found))


def _items(value) -> list:
    """Whatever `value` holds, as a list -- and nothing at all if it is the
    wrong shape.

    Each level's shape is the harness's to define; raising here used to
    silence the whole preflight report.
    """
    if isinstance(value, dict):
        return list(value.values())
    return list(value) if isinstance(value, list) else []


def _launcher_fault(hook: dict) -> list[str]:
    """One hook entry's launcher problems, in both of the two forms.

    An unbraced `$CLAUDE_PROJECT_DIR` is expanded by the shell, which on
    Windows without Git Bash is PowerShell, where it expands to nothing.
    A bare name is looked up on PATH's absolute entries, as
    `import_probe.import_fault` does (#1025); `shutil.which` passed a
    relative-entry launcher the probe then skipped.
    """
    command = hook.get("command")
    program = _program_name(hook)
    if program is None:
        return []  # nothing names a program here, so nothing can fail to start
    args = [a for a in _items(hook.get("args")) if isinstance(a, str)]
    text = " ".join([command, *args])
    found = []
    if not import_probe.is_bare_command(program):
        if not shutil.which(program):
            found.append(f"`{program}` is not an executable file, so a hook cannot start.")
    elif not programs.resolve_program(program):
        found.append(f"`{program}` is not on an absolute PATH entry, so a hook cannot start.")
    if "$CLAUDE_PROJECT_DIR" in text.replace("${CLAUDE_PROJECT_DIR}", ""):
        found.append(
            f"`{program}` uses an unbraced $CLAUDE_PROJECT_DIR, which the "
            "shell expands rather than the harness (docs/HOOKS.md)."
        )
    return found


def _program_name(hook: dict) -> str | None:
    """The program a hook entry names, or None if it names nothing:
    `command` in exec form (`args` present), else its first word."""
    command = hook.get("command")
    if not isinstance(command, str) or not command.split():
        return None
    return command if "args" in hook else command.split()[0]

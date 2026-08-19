"""Can the hooks this repository registers actually start?

A hook whose launcher does not resolve fails **silently**: measured on
2026-08-15 with a throwaway `PostToolUse` entry pairing a bogus command
with a working control hook, the control's payload arrived and the bogus
one produced nothing at all -- no error to the model, nothing findable in
a log. The citation gate is the only automatic enforcement of CLAUDE.md's
one binding rule, so that silence is the worst failure available here:
the settings file still lists the gate, its tests still pass, and drafts
land ungated.

`session_start_hook.py` was written to notice exactly that (#197), and
cannot do it alone: **it is launched by the same interpreter name it
vets.** If `python` is missing, the preflight is missing too, and the
report that was supposed to arrive never does. So the check lives here
instead, where `python -m src.draft gate` -- which every genre skill runs,
on an interpreter that has demonstrably started -- can also make it. The
preflight still calls it, and the two share this one implementation
rather than a copy.

**On the layer boundary.** docs/HOOKS.md keeps `src/` clear of the harness
and `.claude/hooks/` clear of logic. This module is the one exception the
rule now names: layer 1 may read the *launcher config*, never a payload or
an envelope. An adapter is defined by handling the harness's stdin/stdout
contract; this handles neither, and its whole output is a list of English
sentences.

Standard library only, and it imports no other `src` module on purpose:
`src.config` raises without a `config.toml`, which would break both
docs/CLI.md's tier-1 promise and the preflight's ability to run in a fresh
clone.
"""

import json
import shutil
from pathlib import Path

def _project_root() -> Path:
    """Where `.claude/settings.json` lives, found without importing config.

    A deliberate second copy of `src/config.py`'s marker walk, and the
    module docstring above says why it cannot be the first one: this
    module "imports no other `src` module on purpose", because
    `src.config` raises without a `config.toml` and that would break both
    docs/CLI.md's tier-1 promise and the preflight's ability to run in a
    fresh clone. Importing config to find the project would reintroduce
    exactly the failure this module exists to report on.

    Deriving it from `__file__` -- which is what this did while the code
    and the project were always the same directory -- stops working the
    moment the code is installed: it would look for `.claude/` inside
    `site-packages`. `.claude/` belongs to the user's project.
    """
    for candidate in (Path.cwd().resolve(), *Path.cwd().resolve().parents):
        if (candidate / "config.toml").is_file():
            return candidate
    return Path(__file__).resolve().parent.parent


SETTINGS = _project_root() / ".claude" / "settings.json"


def faults(settings_path: Path = SETTINGS) -> list[str]:
    """Registered hook commands that cannot start, read from a settings file.

    Static, because the alternative is not available: a launcher is a line
    in a config file the harness consumes, no test imports it, and CI never
    executes it. Absent or unreadable settings mean there is nothing to
    check rather than something wrong -- this is not that file's owner.

    Note what a clean result does and does not promise. It says every
    registered launcher *can* start on this host; it never says the harness
    actually spawned one. Nothing available from inside a Python process
    can say the second thing.

    Deduplicated, in first-seen order. Every hook here is launched the same
    way, so one missing interpreter is one problem however many entries
    name it -- and reporting it once per entry made the gate print the
    identical sentence twice, which reads as a defect in the reporter.
    Distinct faults still all appear: the sentence names the program.
    """
    try:
        events = json.loads(Path(settings_path).read_text(encoding="utf-8"))["hooks"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    found = []
    for entries in _items(events):
        for entry in _items(entries):
            for hook in _items(entry.get("hooks") if isinstance(entry, dict) else None):
                if isinstance(hook, dict):
                    found.extend(_launcher_fault(hook))
    return list(dict.fromkeys(found))


def _items(value) -> list:
    """Whatever `value` holds, as a list -- and nothing at all if it is the
    wrong shape.

    Every level of a settings file is checked through this, because at each
    one the shape is the harness's to define and not this module's to
    assume. A wrong shape anywhere used to raise, and since the preflight
    swallows everything to keep itself from breaking a session, the result
    was the whole report going silent -- the corpus stage and the gate
    check with it. Reporting nothing because a settings file is odd is the
    failure this check exists to notice in other hooks.
    """
    if isinstance(value, dict):
        return list(value.values())
    return list(value) if isinstance(value, list) else []


def _launcher_fault(hook: dict) -> list[str]:
    """One hook entry's launcher problems, in both of the two forms.

    Exec form (`args` present) names the program in `command`; shell form
    puts it first in a command line. An unbraced `$CLAUDE_PROJECT_DIR` is
    expanded by the shell rather than substituted by the harness, and the
    shell is PowerShell on a Windows host without Git Bash -- where that
    syntax names an undefined variable and expands to nothing.

    `shutil.which` reads *this* process's PATH, which stands in for the
    harness's only because both descend from the same shell. That is the
    limit of what a check on this side of the fence can see.
    """
    command = hook.get("command")
    if not isinstance(command, str) or not command.split():
        return []  # nothing names a program here, so nothing can fail to start
    args = [a for a in _items(hook.get("args")) if isinstance(a, str)]
    program = command if "args" in hook else command.split()[0]
    text = " ".join([command, *args])
    found = []
    if not shutil.which(program):
        found.append(f"`{program}` is not on PATH, so a hook cannot start.")
    if "$CLAUDE_PROJECT_DIR" in text.replace("${CLAUDE_PROJECT_DIR}", ""):
        found.append(f"`{program}` uses an unbraced $CLAUDE_PROJECT_DIR, which the "
                     "shell expands rather than the harness (docs/HOOKS.md).")
    return found

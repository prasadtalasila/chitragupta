"""The launcher lines in this repository's own `.claude/settings.json`.

Every other test in this suite writes a settings file into a throwaway
root, which checks the *rule* and not this repository's answer to it -- so
a hook that never spawns has always passed every test here. This file is
the exception: it reads the live settings file and asserts the four things
about it that `docs/HOOKS.md`'s launcher contract settles.

What it cannot do is start anything. The artefact under test is a config
file the harness consumes, not code the suite imports, and no test can
prove the harness spawned a hook. A green run here means the launcher
lines are the shape the contract requires; it does not mean a hook ran.

It iterates rather than naming the entries, so that a hook added later
inherits the contract instead of copying whatever line was nearest. That is
not hypothetical: the prose check's entry (#185) arrived while this was in
review and was held to it without a line being added here.
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SETTINGS = REPO_ROOT / ".claude" / "settings.json"

# docs/HOOKS.md's launcher contract: `python`, not `python3`. A CPython
# venv creates `python3` only on POSIX -- on Windows it writes `python.exe`
# alone -- and every documented invocation in this repository is already
# `python -m src.*`, so a host without it runs nothing here anyway.
INTERPRETER = "python"


def registered_hooks() -> list[tuple[str, dict]]:
    """Every hook entry in the live settings file, labelled by where it sits.

    Read at import time, so a settings file that will not parse fails
    collection loudly rather than being quietly skipped. An entry missing
    its `hooks` list is left to `test_every_registered_hook_is_covered`,
    which says something more useful than a KeyError would.
    """
    events = json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]
    return [(f"{event}[{i}][{j}]", hook)
            for event, entries in events.items()
            for i, entry in enumerate(entries)
            for j, hook in enumerate(entry.get("hooks", []))]


HOOKS = registered_hooks()
IDS = [name for name, _ in HOOKS]
ENTRIES = [hook for _, hook in HOOKS]


def test_every_registered_hook_is_covered():
    """A settings file that registered nothing would pass every assertion
    below by vacuity, which is the one way this file could lie."""
    assert len(HOOKS) >= 2


@pytest.mark.parametrize("hook", ENTRIES, ids=IDS)
class TestLauncherContract:
    def test_is_exec_form(self, hook):
        """`args` present is what makes a command hook exec form, and exec
        form is what ignores the shell -- which on a Windows host without
        Git Bash is PowerShell, where `$CLAUDE_PROJECT_DIR` is an undefined
        variable that expands to nothing."""
        assert isinstance(hook.get("args"), list)
        assert all(isinstance(a, str) for a in hook["args"])

    def test_launches_the_agreed_interpreter(self, hook):
        assert hook["command"] == INTERPRETER

    def test_every_placeholder_is_braced(self, hook):
        """Claude Code substitutes `${CLAUDE_PROJECT_DIR}` itself, into
        `command` and into each `args` element, before any shell sees it.
        The unbraced spelling asks a shell to do it instead."""
        text = " ".join([hook["command"], *hook["args"]])
        assert "$CLAUDE_PROJECT_DIR" not in text.replace("${CLAUDE_PROJECT_DIR}", "")

    def test_names_a_script_that_exists(self, hook):
        """A renamed or deleted hook script fails the same silent way a
        missing interpreter does, and is as invisible from inside a run."""
        for arg in hook["args"]:
            if "${CLAUDE_PROJECT_DIR}" in arg:
                target = Path(arg.replace("${CLAUDE_PROJECT_DIR}", str(REPO_ROOT)))
                assert target.is_file(), f"{arg} does not resolve to a file"

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
import os
import sys
import subprocess
import re
from pathlib import Path

import pytest

from tests.test_citation_gate_hook import _IS_COVERAGE_BOOTSTRAP

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
    return [
        (f"{event}[{i}][{j}]", hook)
        for event, entries in events.items()
        for i, entry in enumerate(entries)
        for j, hook in enumerate(entry.get("hooks", []))
    ]


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
        """Never the `chitragupta`/`cg` console script (#262): that depends on
        whichever venv is first on PATH, which reintroduces exactly the
        silent-launcher failure `chitragupta/hook_launchers.py` exists to
        catch (#264) -- `python <script>.py` degrades to a clear PATH
        fault instead."""
        assert hook["command"] == INTERPRETER, (
            f"hook launches {hook['command']!r}, not the agreed {INTERPRETER!r}"
        )

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


CODEX = REPO_ROOT / ".codex" / "hooks.json"


def codex_hooks() -> list[tuple[str, str, dict]]:
    """Every hook entry in the live `.codex/hooks.json`, with its matcher (#812)."""
    events = json.loads(CODEX.read_text(encoding="utf-8"))["hooks"]
    return [
        (event, entry.get("matcher", ""), hook)
        for event, entries in events.items()
        for entry in entries
        for hook in entry.get("hooks", [])
    ]


SCRIPT_RE = re.compile(r"h/'([a-z_]+\.py)'")


def codex_script(command: str) -> str:
    """The hook script a Codex launcher line runs, by name."""
    match = SCRIPT_RE.search(command)
    assert match, f"no hook script named in {command!r}"
    return match.group(1)


class TestCodexLauncher:
    """The same hooks, launched by Codex's config (#812).

    Measured on Codex 0.159.0 (docs/HARNESS.md): a hook runs in the
    session's working directory, which is wherever Codex was started, and
    Codex sets no project-directory variable. A relative
    `python .claude/hooks/<x>.py` therefore failed to start from any
    subfolder, and the draft landed ungated. So each line walks up from
    the working directory to the folder holding `.codex/hooks.json` and
    runs the hook from there, under `python -P` so the working directory
    is never on `sys.path` (#822)."""

    def test_every_hook_launches_python_safely_and_a_script_that_exists(self):
        hooks = codex_hooks()
        assert len(hooks) >= 3
        for _, _, hook in hooks:
            assert hook["command"].startswith(f"{INTERPRETER} -P -c "), hook["command"]
            script = REPO_ROOT / ".claude" / "hooks" / codex_script(hook["command"])
            assert script.is_file(), f"{script} does not exist"

    def test_the_gate_runs_on_apply_patch(self):
        gated = [
            matcher
            for event, matcher, hook in codex_hooks()
            if event == "PostToolUse" and codex_script(hook["command"]) == "citation_gate_hook.py"
        ]
        assert gated
        assert all("apply_patch" in matcher.split("|") for matcher in gated)

    def test_the_same_scripts_as_claude_code(self):
        """No hook on one harness that the other lacks, bar the code-size
        hook, which checks this repository's own code rather than a draft."""
        codex = {codex_script(h["command"]) for _, _, h in codex_hooks()}
        claude = {Path(h["args"][0]).name for h in ENTRIES} - {"code_standards_hook.py"}
        assert codex == claude

    def test_a_launcher_line_finds_its_hook_from_a_subfolder(self, tmp_path):
        """The measured failure, pinned: run the real launcher line, through
        a shell as Codex does, from two levels below the project root."""
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        (tmp_path / ".codex").mkdir()
        (tmp_path / ".codex" / "hooks.json").write_text("{}", encoding="utf-8")
        (hooks_dir / "citation_gate_hook.py").write_text(
            "import pathlib, sys\n"
            "print(pathlib.Path(__file__).parent.name, sys.path[0] == str(pathlib.Path(__file__).parent))\n",
            encoding="utf-8",
        )
        deep = tmp_path / "content" / "drafts"
        deep.mkdir(parents=True)
        command = next(
            h["command"] for _, _, h in codex_hooks() if "citation_gate_hook.py" in h["command"]
        )
        command = command.replace("python -P", f'"{sys.executable}" -P', 1)
        # Coverage's bootstrap variables are stripped for the reason
        # tests/test_citation_gate_hook.py's _IS_COVERAGE_BOOTSTRAP gives: a
        # child started outside the repo records statement-only data that
        # cannot be combined with this run's branch data.
        env = {k: v for k, v in os.environ.items() if not _IS_COVERAGE_BOOTSTRAP(k)}
        result = subprocess.run(
            command, shell=True, cwd=deep, capture_output=True, text=True, check=False, env=env
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.split() == ["hooks", "True"]

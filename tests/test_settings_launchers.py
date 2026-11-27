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

INTERPRETER = "python"


def registered_hooks() -> list[tuple[str, dict]]:
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
    assert len(HOOKS) >= 2


@pytest.mark.parametrize("hook", ENTRIES, ids=IDS)
class TestLauncherContract:
    def test_is_exec_form(self, hook):
        assert isinstance(hook.get("args"), list)
        assert all(isinstance(a, str) for a in hook["args"])

    def test_launches_the_agreed_interpreter(self, hook):
        assert hook["command"] == INTERPRETER, (
            f"hook launches {hook['command']!r}, not the agreed {INTERPRETER!r}"
        )

    def test_every_placeholder_is_braced(self, hook):
        text = " ".join([hook["command"], *hook["args"]])
        assert "$CLAUDE_PROJECT_DIR" not in text.replace("${CLAUDE_PROJECT_DIR}", "")

    def test_names_a_script_that_exists(self, hook):
        for arg in hook["args"]:
            if "${CLAUDE_PROJECT_DIR}" in arg:
                target = Path(arg.replace("${CLAUDE_PROJECT_DIR}", str(REPO_ROOT)))
                assert target.is_file(), f"{arg} does not resolve to a file"


CODEX = REPO_ROOT / ".codex" / "hooks.json"


def codex_hooks() -> list[tuple[str, str, dict]]:
    events = json.loads(CODEX.read_text(encoding="utf-8"))["hooks"]
    return [
        (event, entry.get("matcher", ""), hook)
        for event, entries in events.items()
        for entry in entries
        for hook in entry.get("hooks", [])
    ]


SCRIPT_RE = re.compile(r"h/'([a-z_]+\.py)'")


def codex_script(command: str) -> str:
    match = SCRIPT_RE.search(command)
    assert match, f"no hook script named in {command!r}"
    return match.group(1)


class TestCodexLauncher:
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
        codex = {codex_script(h["command"]) for _, _, h in codex_hooks()}
        claude = {Path(h["args"][0]).name for h in ENTRIES} - {"code_standards_hook.py"}
        assert codex == claude

    def test_a_launcher_line_finds_its_hook_from_a_subfolder(self, tmp_path):
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
        env = {k: v for k, v in os.environ.items() if not _IS_COVERAGE_BOOTSTRAP(k)}
        result = subprocess.run(
            command, shell=True, cwd=deep, capture_output=True, text=True, check=False, env=env
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.split() == ["hooks", "True"]

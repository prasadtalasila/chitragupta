"""`.claude/hooks/code_standards_hook.py`, run the way the harness runs it.

Spawned as `python <path>` with a `PostToolUse` payload on stdin, which
is what proves the contract: the branches are
`tests/test_code_standards_hook_modules.py`'s job, and that split is the
one `tests/test_hook_modules.py` states for the drafting hooks.

The temporary root holds a real copy of the hook, the scanner and the
register, for the reason `tests/test_citation_gate_hook.py` records:
`Path(__file__).resolve()` follows a symlink straight back to the real
checkout, and the point of a throwaway root is that it is not that.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_citation_gate_hook import _IS_COVERAGE_BOOTSTRAP

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = REPO_ROOT / ".claude" / "hooks"

OVER_C1 = "def f():\n" + "\n".join(f"    x{i} = {i}" for i in range(30)) + "\n"


class HookRepo:
    """A throwaway repo root with the hook, the scanner and the register."""

    def __init__(self, root: Path, with_scanner: bool = True):
        self.root = root
        hooks = root / ".claude" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HOOKS / "code_standards_hook.py", hooks / "code_standards_hook.py")
        self.hook = hooks / "code_standards_hook.py"
        if with_scanner:
            (root / "scripts").mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO_ROOT / "scripts" / "code_standards.py", root / "scripts")
            shutil.copy2(
                REPO_ROOT / "code-standards-register.toml",
                root / "code-standards-register.toml",
            )
        self.package = root / "chitragupta"
        self.package.mkdir(parents=True, exist_ok=True)
        self.env = {k: v for k, v in os.environ.items() if not _IS_COVERAGE_BOOTSTRAP(k)}

    def run(self, file_path):
        return subprocess.run(
            [sys.executable, str(self.hook)],
            input=json.dumps({"tool_input": {"file_path": str(file_path)}}),
            cwd=str(self.root),
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )


@pytest.fixture
def repo(tmp_path):
    return HookRepo(tmp_path)


class TestTheHarnessContract:
    def test_a_crossing_arrives_as_the_standard_envelope(self, repo):
        target = repo.package / "big.py"
        target.write_text(OVER_C1, encoding="utf-8")
        result = repo.run(target)
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert "C1" in payload["hookSpecificOutput"]["additionalContext"]

    def test_stdout_is_json_only(self, repo):
        """Mixing plain text with JSON on stdout destroys the payload --
        measured in `docs/HOOKS.md`'s trial 1, and the reason no hook here
        prints anything alongside its envelope."""
        target = repo.package / "big.py"
        target.write_text(OVER_C1, encoding="utf-8")
        json.loads(repo.run(target).stdout)

    def test_a_clean_file_writes_nothing_at_all(self, repo):
        target = repo.package / "small.py"
        target.write_text("def f():\n    return 1\n", encoding="utf-8")
        result = repo.run(target)
        assert (result.returncode, result.stdout) == (0, "")

    def test_it_never_blocks(self, repo):
        target = repo.package / "big.py"
        target.write_text(OVER_C1, encoding="utf-8")
        assert "decision" not in repo.run(target).stdout

    def test_a_write_outside_the_watched_roots_is_ignored(self, repo):
        target = repo.root / "notes.md"
        target.write_text("# not python\n", encoding="utf-8")
        assert repo.run(target).stdout == ""

    def test_malformed_stdin_still_exits_zero(self, repo):
        result = subprocess.run(
            [sys.executable, str(repo.hook)],
            input="{not json",
            cwd=str(repo.root),
            env=repo.env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert (result.returncode, result.stdout) == (0, "")


class TestAScaffoldedProject:
    """`chitragupta init` copies `.claude/` verbatim and scaffolds no
    `scripts/` tree, so the hook is registered where its scanner does not
    exist. It has to be inert there, not broken."""

    def test_a_missing_scanner_is_silent_and_exits_zero(self, tmp_path):
        repo = HookRepo(tmp_path, with_scanner=False)
        target = repo.package / "big.py"
        target.write_text(OVER_C1, encoding="utf-8")
        result = repo.run(target)
        assert (result.returncode, result.stdout, result.stderr) == (0, "", "")

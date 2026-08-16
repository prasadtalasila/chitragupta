""".claude/hooks/style_check_hook.py, spawned the way the harness spawns it.

`tests/test_hook_modules.py` covers this hook's branches by importing it,
which is the only way it contributes coverage. This file does the thing
that import cannot: it runs the real script as a real process, reading a
real payload off stdin, and checks the envelope the harness actually
consumes. A refactor that broke `import draft_target`, or the
`__main__` tail, or the shape of stdout would pass every module test and
fail here.

That is not hypothetical. The first version of this hook was written
without a `__main__` block: every function was correct, the module tests
would have passed, and the installed hook silently did nothing on every
write. It was caught by running it, which is what this file automates.
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


class StyleHookRepo:
    """A throwaway repo root holding a real copy of the hook and its helper.

    Both are copied rather than symlinked, for the reason
    `tests/test_citation_gate_hook.py` records: `Path(__file__).resolve()`
    follows a symlink straight back to the real checkout, and the point of
    the temporary root is that it is not that.
    """

    def __init__(self, root: Path, cfg):
        self.root = root
        hooks = root / ".claude" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        for name in ("style_check_hook.py", "draft_target.py"):
            shutil.copy2(HOOKS / name, hooks / name)
        self.hook = hooks / "style_check_hook.py"
        self.drafts = root / "content" / "drafts"
        self.drafts.mkdir(parents=True, exist_ok=True)
        self.env = {
            **{k: v for k, v in os.environ.items() if not _IS_COVERAGE_BOOTSTRAP(k)},
            "CONTENT_DIR": str(cfg.CONTENT_DIR),
            "PYTHONPATH": str(REPO_ROOT),
        }

    def run(self, file_path):
        return subprocess.run(
            [sys.executable, str(self.hook)],
            input=json.dumps({"tool_input": {"file_path": str(file_path)}}),
            cwd=str(self.root), capture_output=True, text=True, env=self.env,
            check=False,
        )

    def draft(self, name: str, text: str) -> Path:
        path = self.drafts / name
        path.write_text(text, encoding="utf-8")
        return path


@pytest.fixture
def style_hook(isolated_config, tmp_path):
    return StyleHookRepo(tmp_path, isolated_config)


class TestTheProcessContract:
    """What only a spawned process can prove."""

    def test_the_script_has_an_entry_point_and_reaches_it(self, style_hook):
        """The regression this file was written for: a hook whose functions
        are all correct and whose `__main__` tail is missing runs, exits 0,
        and does nothing at all -- indistinguishable from a clean draft."""
        assert "__main__" in (HOOKS / "style_check_hook.py").read_text(encoding="utf-8")
        draft = style_hook.draft("a.md", "Plain prose.\n")
        assert style_hook.run(draft).returncode == 0

    def test_the_helper_imports_from_the_hooks_own_directory(self, style_hook):
        """`import draft_target` works because a hook is run by absolute
        path, which puts its directory first on sys.path. No test that
        imports the module by spec can show that."""
        draft = style_hook.draft("b.md", "Plain prose.\n")
        result = style_hook.run(draft)
        assert "ModuleNotFoundError" not in result.stderr
        assert result.returncode == 0

    @pytest.mark.parametrize("payload", [
        "{not json", "[]", '{"tool_input": []}', '{"tool_input": {}}',
    ])
    def test_malformed_stdin_exits_zero_and_says_nothing(self, style_hook, payload):
        result = subprocess.run(
            [sys.executable, str(style_hook.hook)], input=payload,
            cwd=str(style_hook.root), capture_output=True, text=True,
            env=style_hook.env, check=False)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_a_write_outside_the_drafts_dir_is_ignored(self, style_hook):
        elsewhere = style_hook.root / "notes.md"
        elsewhere.write_text("obviously\n", encoding="utf-8")
        result = style_hook.run(elsewhere)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_stdout_is_one_json_document_or_nothing(self, style_hook):
        """The rule whose breach is invisible: a stray print() ahead of the
        JSON makes stdout unparseable, after which the whole payload is
        discarded in silence and the hook still looks installed."""
        draft = style_hook.draft("c.md", "Plain prose with no markers.\n")
        out = style_hook.run(draft).stdout
        if out.strip():
            json.loads(out)  # raises if anything else reached stdout

    def test_it_never_blocks_whatever_the_draft_says(self, style_hook):
        """An advisory hook has one output shape it may never emit."""
        draft = style_hook.draft(
            "d.md", "This is obviously simple and clearly easy.\n")
        result = style_hook.run(draft)
        assert result.returncode == 0
        assert "decision" not in result.stdout

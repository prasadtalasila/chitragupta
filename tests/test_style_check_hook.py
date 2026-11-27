import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_citation_gate_hook import _IS_COVERAGE_BOOTSTRAP, plant_package

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = REPO_ROOT / ".claude" / "hooks"


class StyleHookRepo:
    def __init__(self, root: Path, cfg):
        self.root = root
        hooks = root / ".claude" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        for name in ("style_check_hook.py", "draft_target.py", "safe_path.py", "patch_paths.py"):
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
            cwd=str(self.root),
            capture_output=True,
            text=True,
            env=self.env,
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
    def test_the_script_has_an_entry_point_and_reaches_it(self, style_hook):
        assert "__main__" in (HOOKS / "style_check_hook.py").read_text(encoding="utf-8")
        draft = style_hook.draft("a.md", "Plain prose.\n")
        assert style_hook.run(draft).returncode == 0

    def test_the_helper_imports_from_the_hooks_own_directory(self, style_hook):
        draft = style_hook.draft("b.md", "Plain prose.\n")
        result = style_hook.run(draft)
        assert "ModuleNotFoundError" not in result.stderr
        assert result.returncode == 0

    @pytest.mark.parametrize(
        "payload",
        [
            "{not json",
            "[]",
            '{"tool_input": []}',
            '{"tool_input": {}}',
        ],
    )
    def test_malformed_stdin_exits_zero_and_says_nothing(self, style_hook, payload):
        result = subprocess.run(
            [sys.executable, str(style_hook.hook)],
            input=payload,
            cwd=str(style_hook.root),
            capture_output=True,
            text=True,
            env=style_hook.env,
            check=False,
        )
        assert result.returncode == 0
        assert result.stdout == ""

    def test_a_write_outside_the_drafts_dir_is_ignored(self, style_hook):
        elsewhere = style_hook.root / "notes.md"
        elsewhere.write_text("obviously\n", encoding="utf-8")
        result = style_hook.run(elsewhere)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_stdout_is_one_json_document_or_nothing(self, style_hook):
        draft = style_hook.draft("c.md", "Plain prose with no markers.\n")
        out = style_hook.run(draft).stdout
        if out.strip():
            json.loads(out)  # raises if anything else reached stdout

    def test_it_never_blocks_whatever_the_draft_says(self, style_hook):
        draft = style_hook.draft("d.md", "This is obviously simple and clearly easy.\n")
        result = style_hook.run(draft)
        assert result.returncode == 0
        assert "decision" not in result.stdout

    def test_a_planted_package_in_a_scaffolded_project_is_never_imported(
        self, style_hook, tmp_path
    ):
        sentinel = tmp_path / "planted-ran"
        plant_package(style_hook.root, sentinel)
        draft = style_hook.draft("e.md", "Plain prose.\n")
        assert style_hook.run(draft).returncode == 0
        assert not sentinel.exists(), "the planted chitragupta/ was imported"

    def test_a_checkout_still_runs_its_own_package(self, style_hook, tmp_path):
        sentinel = tmp_path / "checkout-ran"
        plant_package(style_hook.root, sentinel, checkout=True)
        style_hook.env["PYTHONPATH"] = str(style_hook.root)
        draft = style_hook.draft("f.md", "Plain prose.\n")
        assert style_hook.run(draft).returncode == 0
        assert sentinel.exists()

"""The OpenCode plugin, through the real Python hook (#900).

`tests/opencode/gate.test.mjs` covers the plugin's helpers with stub hooks;
this runs those tests from pytest, so a local run cannot skip them, and
adds the one case they cannot: the plugin as OpenCode would load it,
driving the real `.claude/hooks/citation_gate_hook.py` in a throwaway
project, on a draft citing a key no ledger holds. Skipped where `node`
is absent, the way pandoc-dependent tests are skipped without pandoc.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_citation_gate_hook import _IS_COVERAGE_BOOTSTRAP

REPO_ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not installed")

DRIVER = """
import { pathToFileURL } from "node:url";
const [plugin, tool, args] = process.argv.slice(2);
const { ChitraguptaGate } = await import(pathToFileURL(plugin).href);
const hooks = await ChitraguptaGate();
const output = { output: "done" };
// The shape OpenCode 1.18.33 hands the after-hook: the call's args ride on `input`.
try {
  await hooks["tool.execute.after"]({ tool, callID: "1", args: JSON.parse(args) }, output);
  console.log(JSON.stringify({ refused: false, output: output.output }));
} catch (error) {
  console.log(JSON.stringify({ refused: true, message: error.message }));
}
"""


def test_the_helper_unit_tests_pass():
    result = subprocess.run(
        [NODE, "--test", str(REPO_ROOT / "tests" / "opencode" / "gate.test.mjs")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture
def project(tmp_path, isolated_config):
    """A throwaway project: this checkout's hooks and plugin, and a drafts dir."""
    shutil.copytree(REPO_ROOT / ".claude" / "hooks", tmp_path / ".claude" / "hooks")
    shutil.copytree(REPO_ROOT / ".opencode", tmp_path / ".opencode")
    drafts = tmp_path / "content" / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    (tmp_path / "driver.mjs").write_text(DRIVER, encoding="utf-8")
    env = {
        **{k: v for k, v in os.environ.items() if not _IS_COVERAGE_BOOTSTRAP(k)},
        "CONTENT_DIR": str(isolated_config.CONTENT_DIR),
        "PYTHONPATH": str(REPO_ROOT),
    }
    return tmp_path, env


def drive(project, tool, args) -> dict:
    root, env = project
    result = subprocess.run(
        [
            NODE,
            str(root / "driver.mjs"),
            str(root / ".opencode" / "plugins" / "chitragupta-gate.js"),
            tool,
            json.dumps(args),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=root,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_a_fabricated_key_in_a_written_draft_is_refused(project):
    # isolated_config's CONTENT_DIR is this same tmp_path/content, so the
    # gate the hook runs reads the draft the plugin names.
    root, _ = project
    draft = root / "content" / "drafts" / "bad.md"
    draft.write_text("A claim [@not_a_real_citekey_2026].\n", encoding="utf-8")
    verdict = drive(project, "write", {"filePath": str(draft)})
    assert verdict["refused"] is True
    assert "not_a_real_citekey_2026" in verdict["message"]


def test_a_write_outside_the_drafts_is_left_alone(project):
    root, _ = project
    (root / "README.md").write_text("A claim [@not_a_real_citekey_2026].\n", encoding="utf-8")
    verdict = drive(project, "write", {"filePath": str(root / "README.md")})
    assert verdict == {"refused": False, "output": "done"}


def test_a_tool_that_writes_nothing_is_not_checked(project):
    verdict = drive(project, "read", {"filePath": "content/drafts/bad.md"})
    assert verdict == {"refused": False, "output": "done"}

import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from chitragupta import ledger

from tests.conftest import _IS_COVERAGE_BOOTSTRAP, add_citable
from tests.ledger_faults import leave_hot_journal

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "citation_gate_hook.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "harness_payloads"


def run_hook(
    stdin_text: str,
    env: dict | None = None,
    cwd: Path | None = None,
    hook: Path | None = None,
    python: str | None = None,
):
    return subprocess.run(
        [python or sys.executable, str(hook or HOOK_PATH)],
        input=stdin_text,
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


def payload(file_path) -> str:
    return json.dumps({"tool_input": {"file_path": str(file_path)}})


class HookRepo:
    def __init__(self, root: Path, cfg):
        self.root = root
        self.hook = root / ".claude" / "hooks" / "citation_gate_hook.py"
        self.hook.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HOOK_PATH, self.hook)
        for helper in ("draft_target.py", "safe_path.py", "patch_paths.py"):
            shutil.copy2(HOOK_PATH.parent / helper, self.hook.parent / helper)
        self.drafts = root / "content" / "drafts"
        self.drafts.mkdir(parents=True, exist_ok=True)
        self.env = {
            **{k: v for k, v in os.environ.items() if not _IS_COVERAGE_BOOTSTRAP(k)},
            "CONTENT_DIR": str(cfg.CONTENT_DIR),
            "PYTHONPATH": str(REPO_ROOT),
        }

    def draft(self, suffix: str = ".md") -> Path:
        return self.drafts / f"hook_test_{uuid.uuid4().hex}{suffix}"

    def run(self, file_path, cwd: Path | None = None, env: dict | None = None, python=None):
        return run_hook(
            payload(file_path),
            env=env or self.env,
            cwd=cwd or self.root,
            hook=self.hook,
            python=python,
        )


def plant_package(root: Path, sentinel: Path, *, checkout: bool = False) -> None:
    pkg = root / "chitragupta"
    pkg.mkdir(exist_ok=True)
    body = f"open({str(sentinel)!r}, 'w').close()\n"
    if checkout:
        body += f"__path__.append({str(REPO_ROOT / 'chitragupta')!r})\n"
    (pkg / "__init__.py").write_text(body, encoding="utf-8")


@pytest.fixture
def hook_repo(isolated_config, tmp_path):
    return HookRepo(tmp_path, isolated_config)


class TestMalformedStdinGuard:
    def test_invalid_json_does_not_crash(self):
        result = run_hook("not valid json {{{")
        assert result.returncode == 0
        assert result.stdout.strip() == ""
        assert result.stderr == ""

    def test_empty_stdin_does_not_crash(self):
        result = run_hook("")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_json_that_is_not_an_object_does_not_crash(self):
        result = run_hook("[1, 2, 3]")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_tool_input_that_is_not_an_object_does_not_crash(self):
        result = run_hook(json.dumps({"tool_input": "not-an-object"}))
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestIgnoredPayloads:
    def test_missing_file_path_is_ignored(self):
        result = run_hook(json.dumps({"tool_input": {}}))
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_missing_tool_input_is_ignored(self):
        result = run_hook(json.dumps({}))
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_path_outside_drafts_dir_is_ignored(self):
        result = run_hook(payload(REPO_ROOT / "AGENTS.md"))
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_non_gated_extension_inside_drafts_dir_is_ignored(self, hook_repo):
        path = hook_repo.draft(suffix=".py")
        path.write_text("@dataclass\nclass Foo:\n    pass\n")
        result = hook_repo.run(path)
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestContainmentCheck:
    def test_dotdot_traversal_out_of_drafts_dir_is_rejected(self):
        traversal = REPO_ROOT / "content" / "drafts" / ".." / ".." / "AGENTS.md"
        result = run_hook(payload(traversal))
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_lookalike_path_elsewhere_on_disk_is_rejected(self, tmp_path):
        decoy_file = tmp_path / "not_this_repo" / "content" / "drafts" / "evil.md"
        decoy_file.parent.mkdir(parents=True)
        decoy_file.write_text("[@fabricated_key_not_in_ledger]\n")

        result = run_hook(payload(decoy_file))
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestPathResolution:
    def test_relative_path_is_resolved_and_gated_regardless_of_cwd(self, hook_repo, tmp_path):
        path = hook_repo.draft()
        path.write_text("No citations in this draft at all.\n")
        rel_path = path.relative_to(hook_repo.root)
        elsewhere = tmp_path / "elsewhere-cwd"
        elsewhere.mkdir()
        result = hook_repo.run(rel_path, cwd=elsewhere)
        assert result.returncode == 0
        assert result.stdout.strip() == ""  # gate ran and passed -- not silently skipped


class TestCodexPatchPayloads:
    def test_a_bad_key_in_any_patched_draft_blocks(self, hook_repo):
        clean, bad = hook_repo.draft(), hook_repo.draft()
        clean.write_text("No citations in this one.\n")
        bad.write_text("This claim cites [@not_a_real_citekey_2026].\n")
        fixture = FIXTURES / "codex_apply_patch_multi.json"
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        payload["cwd"] = str(hook_repo.root)
        payload["tool_input"]["command"] = (
            payload["tool_input"]["command"]
            .replace("content/drafts/clean.md", clean.relative_to(hook_repo.root).as_posix())
            .replace("content/drafts/multi.md", bad.relative_to(hook_repo.root).as_posix())
        )
        result = run_hook(
            json.dumps(payload), env=hook_repo.env, cwd=hook_repo.root, hook=hook_repo.hook
        )
        assert result.returncode == 0
        response = json.loads(result.stdout)
        assert response["decision"] == "block"
        assert "not_a_real_citekey_2026" in response["reason"]
        assert bad.name in response["reason"]


class TestGateEnforcement:
    def test_fabricated_citation_blocks_with_reason(self, hook_repo):
        path = hook_repo.draft()
        path.write_text("This claim cites [@totally_fabricated_key_2026].\n")
        result = hook_repo.run(path)

        assert result.returncode == 0  # the hook process itself always exits 0
        response = json.loads(result.stdout)
        assert response["decision"] == "block"
        assert "totally_fabricated_key_2026" in response["reason"]
        assert "Citation gate FAILED" in response["reason"]

    def test_an_oversize_draft_blocks_as_too_large_to_gate(self, hook_repo):
        path = hook_repo.draft()
        path.write_text("Plain prose with no citations at all.\n" * 100_001)
        result = hook_repo.run(path)

        assert result.returncode == 0
        response = json.loads(result.stdout)
        assert response["decision"] == "block"
        assert "too large to gate" in response["reason"]

    def test_verified_citation_does_not_block(self, hook_repo, ledger_con):
        add_citable(ledger_con, "smith_real_2024", title="A Real Paper")
        path = hook_repo.draft()
        path.write_text("A real, grounded claim [@smith_real_2024].\n")
        result = hook_repo.run(path)

        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_draft_with_no_citations_does_not_block(self, hook_repo):
        path = hook_repo.draft()
        path.write_text("Plain prose with no citations at all.\n")
        result = hook_repo.run(path)

        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_tex_extension_is_also_gated(self, hook_repo):
        path = hook_repo.draft(suffix=".tex")
        path.write_text(r"This claim cites \citep{totally_fabricated_key_2026}." "\n")
        result = hook_repo.run(path)

        assert result.returncode == 0
        response = json.loads(result.stdout)
        assert response["decision"] == "block"
        assert "totally_fabricated_key_2026" in response["reason"]


class TestALedgerTheGateCannotRead:
    def test_it_blocks_without_blaming_a_citekey(self, hook_repo, ledger_con, isolated_config):
        ledger_con.close()
        journal = leave_hot_journal(isolated_config.LEDGER_PATH)
        path = hook_repo.draft()
        path.write_text("This claim cites [@totally_fabricated_key_2026].\n")
        result = hook_repo.run(path)

        assert result.returncode == 0
        response = json.loads(result.stdout)
        assert response["decision"] == "block"
        reason = response["reason"]
        assert reason.startswith("The citation gate could not read the ledger")
        assert "not a bad citekey" in reason
        assert journal.name in reason  # the gate's own diagnosis, passed through
        assert "Fix the offending citekey" not in reason

    def test_its_exit_code_is_the_package_s(self):
        assert re.search(r"^GATE_COULD_NOT_RUN = (\d+)$", HOOK_PATH.read_text(), re.M).group(
            1
        ) == str(ledger.EXIT_UNREADABLE)


class TestEnvironmentFaultDistinctFromCitekeyFault:
    def test_interpreter_that_cannot_import_chitragupta_is_named_as_the_fault(
        self, hook_repo, system_python
    ):
        env = {**hook_repo.env}
        del env["PYTHONPATH"]
        probe = subprocess.run(
            [system_python, "-c", "import chitragupta"],
            env=env,
            cwd=hook_repo.root,
            capture_output=True,
        )
        if probe.returncode == 0:
            pytest.skip("system_python can import chitragupta on this host")

        path = hook_repo.draft()
        path.write_text("A claim [@some_key].\n")

        result = hook_repo.run(path, env=env, python=system_python)

        assert result.returncode == 0
        response = json.loads(result.stdout)
        assert response["decision"] == "block"  # still fails closed
        assert "could not run" in response["reason"].lower()
        assert "chitragupta" in response["reason"]
        assert "some_key" not in response["reason"]  # not blamed on the citekey
        assert "Citation gate FAILED" not in response["reason"]


class TestAPlantedPackageIsNeverImported:
    def test_a_scaffolded_project_ignores_a_planted_package(self, hook_repo, tmp_path):
        sentinel = tmp_path / "planted-ran"
        plant_package(hook_repo.root, sentinel)
        path = hook_repo.draft()
        path.write_text("This claim cites [@totally_fabricated_key_2026].\n")

        result = hook_repo.run(path)

        assert not sentinel.exists(), "the planted chitragupta/ was imported"
        assert "Citation gate FAILED" in json.loads(result.stdout)["reason"]  # the real gate

    def test_a_checkout_still_runs_its_own_package(self, hook_repo, tmp_path):
        sentinel = tmp_path / "checkout-ran"
        plant_package(hook_repo.root, sentinel, checkout=True)
        path = hook_repo.draft()
        path.write_text("This claim cites [@totally_fabricated_key_2026].\n")

        result = hook_repo.run(path, env={**hook_repo.env, "PYTHONPATH": str(hook_repo.root)})

        assert sentinel.exists(), "the checkout's own chitragupta/ was not the one run"
        assert "Citation gate FAILED" in json.loads(result.stdout)["reason"]

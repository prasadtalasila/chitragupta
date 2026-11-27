import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from chitragupta import ledger

from tests.conftest import make_reference
from tests.ledger_faults import leave_hot_journal
from tests.test_citation_gate_hook import _IS_COVERAGE_BOOTSTRAP, plant_package

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "session_start_hook.py"

EXEC_FORM_HOOK = {
    "type": "command",
    "command": "python",
    "args": ["${CLAUDE_PROJECT_DIR}/.claude/hooks/citation_gate_hook.py"],
}
SHELL_FORM_UNBRACED = {
    "type": "command",
    "command": 'python "$CLAUDE_PROJECT_DIR/.claude/hooks/citation_gate_hook.py"',
}


def settings(*hooks) -> dict:
    return {"hooks": {"PostToolUse": [{"matcher": "Write|Edit", "hooks": list(hooks)}]}}


class PreflightRepo:
    def __init__(self, root: Path, cfg):
        self.root = root
        self.hook = root / ".claude" / "hooks" / "session_start_hook.py"
        self.hook.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HOOK_PATH, self.hook)
        shutil.copy2(HOOK_PATH.parent / "safe_path.py", self.hook.parent / "safe_path.py")
        (root / "content" / "drafts").mkdir(parents=True, exist_ok=True)
        self.write_settings(settings(EXEC_FORM_HOOK))
        self.env = {
            **{k: v for k, v in os.environ.items() if not _IS_COVERAGE_BOOTSTRAP(k)},
            "CONTENT_DIR": str(cfg.CONTENT_DIR),
            "PYTHONPATH": str(REPO_ROOT),
        }

    def write_settings(self, data) -> None:
        path = self.root / ".claude" / "settings.json"
        path.write_text(data if isinstance(data, str) else json.dumps(data, indent=2))

    def stub(self, module: str, body: str) -> None:
        plant_package(self.root, self.root / ".stub-imported", checkout=True)
        (self.root / "chitragupta" / f"{module}.py").write_text(body)
        self.env["PYTHONPATH"] = str(self.root)

    def run(self, *python_args):
        return subprocess.run(
            [sys.executable, *python_args, str(self.hook)],
            input=json.dumps({"hook_event_name": "SessionStart", "source": "startup"}),
            cwd=str(self.root),
            capture_output=True,
            text=True,
            env=self.env,
        )

    @staticmethod
    def context(result) -> str:
        if not result.stdout.strip():
            return ""
        payload = json.loads(result.stdout)
        return payload["hookSpecificOutput"]["additionalContext"]


@pytest.fixture
def preflight(isolated_config, tmp_path):
    return PreflightRepo(tmp_path, isolated_config)


@pytest.fixture
def synced(preflight, ledger_con):
    ledger.upsert_reference(
        ledger_con, make_reference(citekey="smith_real_2024", title="A Real Paper")
    )
    return preflight


class TestItNeverBreaksTheSession:
    def test_exits_zero_when_everything_is_ready(self, synced):
        assert synced.run().returncode == 0

    def test_exits_zero_when_the_ledger_is_empty(self, preflight):
        assert preflight.run().returncode == 0

    def test_exits_zero_when_settings_json_is_missing(self, preflight):
        (preflight.root / ".claude" / "settings.json").unlink()
        assert preflight.run().returncode == 0

    def test_exits_zero_when_settings_json_is_unparseable(self, preflight):
        preflight.write_settings("{not json at all")
        assert preflight.run().returncode == 0

    def test_exits_zero_when_settings_json_has_no_hooks_key(self, preflight):
        preflight.write_settings({"permissions": {}})
        assert preflight.run().returncode == 0

    def test_exits_zero_when_the_corpus_layer_will_not_start(self, preflight):
        preflight.stub("corpus", "import sys\nsys.exit(1)\n")
        assert preflight.run().returncode == 0

    def test_never_emits_a_blocking_decision(self, preflight):
        result = preflight.run()
        assert "decision" not in result.stdout


class TestSilenceWhenReady:
    def test_says_nothing_when_synced_and_launchers_are_sound(self, synced):
        assert synced.run().stdout.strip() == ""

    def test_output_is_one_json_document_when_it_does_speak(self, preflight):
        result = preflight.run()
        assert json.loads(result.stdout)["hookSpecificOutput"]["hookEventName"] == "SessionStart"


class TestCorpusStageIsNotAFault:
    def test_absent_ledger_is_reported_with_the_next_command(self, preflight):
        context = PreflightRepo.context(preflight.run())
        assert "before a first sync" in context
        assert "python -m chitragupta.corpus sync" in context

    def test_present_but_empty_ledger_is_reported_too(self, preflight, ledger_con):
        assert "before a first sync" in PreflightRepo.context(preflight.run())

    def test_a_pre_sync_corpus_is_not_called_broken(self, preflight):
        assert "BROKEN" not in PreflightRepo.context(preflight.run())

    def test_a_corpus_layer_that_will_not_start_is_a_fault(self, preflight):
        preflight.stub("corpus", "import sys\nsys.exit(1)\n")
        context = PreflightRepo.context(preflight.run())
        assert "corpus layer will not start" in context
        assert "cp config.toml.example config.toml" in context


class TestGateLiveness:
    def test_a_live_gate_is_not_reported(self, synced):
        assert "fabricated citekey" not in PreflightRepo.context(synced.run())

    def test_a_gate_that_passes_a_fabricated_citekey_is_reported(self, synced):
        synced.stub("draft", "import sys\nsys.exit(0)\n")
        context = PreflightRepo.context(synced.run())
        assert "BROKEN" in context
        assert "fabricated citekey" in context

    def test_a_gate_that_fails_for_the_wrong_reason_is_not_called_live(self, synced):
        synced.stub("draft", "import sys\nsys.exit(1)\n")
        context = PreflightRepo.context(synced.run())
        assert "fabricated citekey" in context

    @pytest.mark.parametrize(
        ("code", "said"),
        [
            (1, "Traceback (most recent call last):\nsqlite3.OperationalError: boom"),
            (3, "ERROR: the citation gate could not read the ledger"),
        ],
    )
    def test_a_gate_that_could_not_run_is_not_said_to_accept(self, synced, code, said):
        synced.stub("draft", f"import sys\nsys.stderr.write({said!r})\nsys.exit({code})\n")
        context = PreflightRepo.context(synced.run())
        assert f"could not run its self-test (exit {code})" in context
        assert said.splitlines()[-1] in context
        assert "did not refuse" not in context


class TestAnUnreadableLedger:
    def test_is_reported_as_that_not_as_a_missing_config(self, synced, ledger_con, isolated_config):
        ledger_con.close()
        journal = leave_hot_journal(isolated_config.LEDGER_PATH)
        context = PreflightRepo.context(synced.run())
        assert "BROKEN: The ledger cannot be read" in context
        assert journal.name in context
        assert "cp config.toml.example" not in context


class TestLauncherFaults:
    def test_exec_form_with_a_braced_placeholder_is_clean(self, synced):
        assert synced.run().stdout.strip() == ""

    def test_unbraced_placeholder_is_reported(self, synced):
        synced.write_settings(settings(SHELL_FORM_UNBRACED))
        context = PreflightRepo.context(synced.run())
        assert "unbraced" in context

    def test_an_interpreter_not_on_path_is_reported(self, synced):
        synced.write_settings(
            settings(
                {
                    "type": "command",
                    "command": "python4.2",
                    "args": ["${CLAUDE_PROJECT_DIR}/.claude/hooks/citation_gate_hook.py"],
                }
            )
        )
        context = PreflightRepo.context(synced.run())
        assert "python4.2" in context
        assert "not on an absolute PATH entry" in context

    def test_a_shell_form_command_is_checked_by_its_first_word(self, synced):
        synced.write_settings(
            settings({"type": "command", "command": 'python4.2 "${CLAUDE_PROJECT_DIR}/x.py"'})
        )
        assert "python4.2" in PreflightRepo.context(synced.run())

    def test_a_hook_entry_with_no_command_is_ignored(self, synced):
        synced.write_settings(settings({"type": "command"}))
        assert synced.run().stdout.strip() == ""

    def test_every_registered_event_is_checked_not_just_posttooluse(self, synced):
        synced.write_settings(
            {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "python4.2"}]}]}}
        )
        assert "python4.2" in PreflightRepo.context(synced.run())


class TestImportProbeFault:
    @pytest.mark.skipif(sys.platform == "win32", reason="a shell-script interpreter")
    def test_is_reported_through_the_real_hook(self, synced, tmp_path):
        fake_bin = tmp_path / "fake-bin"
        fake_bin.mkdir()
        fake = fake_bin / "python"
        fake.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        fake.chmod(0o755)
        synced.env["PATH"] = f"{fake_bin}{os.pathsep}{synced.env['PATH']}"
        context = PreflightRepo.context(synced.run())
        assert "cannot import chitragupta" in context


class TestAPlantedPackageIsNeverImported:
    def test_a_scaffolded_project_ignores_a_planted_package(self, synced, tmp_path):
        sentinel = tmp_path / "planted-ran"
        plant_package(synced.root, sentinel)
        result = synced.run()
        assert not sentinel.exists(), "the planted chitragupta/ was imported"
        assert result.stdout.strip() == ""  # and the real checks all passed

    def test_a_checkout_still_runs_its_own_package(self, synced, tmp_path):
        sentinel = tmp_path / "checkout-ran"
        plant_package(synced.root, sentinel, checkout=True)
        synced.env["PYTHONPATH"] = str(synced.root)
        result = synced.run()
        assert sentinel.exists()
        assert result.stdout.strip() == ""


class TestNoInstalledPackageVisibleAtAll:
    def test_reports_by_name_instead_of_crashing(self, synced):
        del synced.env["PYTHONPATH"]
        result = synced.run("-S")
        assert result.returncode == 0
        context = PreflightRepo.context(result)
        assert "no installed chitragupta visible to" in context
        assert sys.executable in context
        assert "Traceback" not in result.stderr

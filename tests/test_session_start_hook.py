""".claude/hooks/session_start_hook.py: the SessionStart hook that reports
what is not yet ready, and says nothing when everything is.

Modelled on tests/test_citation_gate_hook.py, and for the same reason: the
hook is a script the harness runs, not a module the suite imports, so
`.claude/` is outside `[tool.coverage.run].source` and these tests earn
their keep behaviourally rather than by covering lines.

The hook derives its repo root from its own on-disk location, so each test
gives it one -- a `PreflightRepo` copies the hook into a tmp_path
`.claude/hooks/` and writes that root's own `.claude/settings.json`. The
hook's two child processes run with `cwd` set to that same temp root, so
`python -m chitragupta.draft` resolves through PYTHONPATH to this checkout's real
code -- unless a test deliberately shadows it with a stub package in the
temp root, which `-m` picks up from cwd first. That is how a dead gate is
simulated without breaking the real one.

The one behaviour worth stating separately, because it is the reason this
hook can exist at all: **it must work before `python -m chitragupta.corpus sync`
has ever run.** A fresh clone has no ledger, and reporting that as a
failure would fire on every first session. So an empty ledger is reported
as a stage in a normal sequence, and only a launcher that cannot start or
a gate that no longer refuses a fabricated citekey is a fault.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from chitragupta import ledger

from tests.conftest import make_reference
from tests.test_citation_gate_hook import _IS_COVERAGE_BOOTSTRAP

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
    """A throwaway repo root the preflight hook can call its own."""

    def __init__(self, root: Path, cfg):
        self.root = root
        self.hook = root / ".claude" / "hooks" / "session_start_hook.py"
        self.hook.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HOOK_PATH, self.hook)
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
        """Shadow `src.<module>` for the hook's children only.

        `python -m` puts the child's cwd first on sys.path, and the child's
        cwd is this temp root -- so a `chitragupta/` package here wins over the real
        one reached through PYTHONPATH.
        """
        pkg = self.root / "chitragupta"
        pkg.mkdir(exist_ok=True)
        (pkg / "__init__.py").touch()
        (pkg / f"{module}.py").write_text(body)

    def run(self):
        return subprocess.run(
            [sys.executable, str(self.hook)],
            input=json.dumps({"hook_event_name": "SessionStart", "source": "startup"}),
            cwd=str(self.root),
            capture_output=True,
            text=True,
            env=self.env,
        )

    @staticmethod
    def context(result) -> str:
        """The advisory text the hook delivered, or "" when it stayed silent."""
        if not result.stdout.strip():
            return ""
        payload = json.loads(result.stdout)
        return payload["hookSpecificOutput"]["additionalContext"]


@pytest.fixture
def preflight(isolated_config, tmp_path):
    return PreflightRepo(tmp_path, isolated_config)


@pytest.fixture
def synced(preflight, ledger_con):
    """A repo whose corpus layer has been synced, i.e. the ready state."""
    ledger.upsert_reference(
        ledger_con, make_reference(citekey="smith_real_2024", title="A Real Paper")
    )
    return preflight


class TestItNeverBreaksTheSession:
    """The advisory contract. A preflight that can break a session is a
    worse bug than any it reports, so every one of these asserts exit 0."""

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
    """A clean run says nothing. The channel is for what needs attention."""

    def test_says_nothing_when_synced_and_launchers_are_sound(self, synced):
        assert synced.run().stdout.strip() == ""

    def test_output_is_one_json_document_when_it_does_speak(self, preflight):
        """The rule a stray print() breaks invisibly: stdout parses, whole."""
        result = preflight.run()
        assert json.loads(result.stdout)["hookSpecificOutput"]["hookEventName"] == "SessionStart"


class TestCorpusStageIsNotAFault:
    """The case this hook was nearly wrong about: a user who has cloned the
    repo and not yet run `python -m chitragupta.corpus sync` has done nothing
    wrong, and must not be told they have."""

    def test_absent_ledger_is_reported_with_the_next_command(self, preflight):
        context = PreflightRepo.context(preflight.run())
        assert "before a first sync" in context
        assert "python -m chitragupta.corpus sync" in context

    def test_present_but_empty_ledger_is_reported_too(self, preflight, ledger_con):
        """The two pre-sync states print different sentences -- "No ledger
        at ..." when the file is absent, "... is empty" when it exists with
        no rows. Both are pre-sync, and an earlier draft of this hook
        matched only the second and stayed silent on a fresh clone."""
        assert "before a first sync" in PreflightRepo.context(preflight.run())

    def test_a_pre_sync_corpus_is_not_called_broken(self, preflight):
        assert "BROKEN" not in PreflightRepo.context(preflight.run())

    def test_a_corpus_layer_that_will_not_start_is_a_fault(self, preflight):
        preflight.stub("corpus", "import sys\nsys.exit(1)\n")
        context = PreflightRepo.context(preflight.run())
        assert "corpus layer will not start" in context
        assert "cp config.toml.example config.toml" in context


class TestGateLiveness:
    """The check that makes the hook worth its startup cost: it is the only
    thing that notices the citation gate has stopped refusing anything."""

    def test_a_live_gate_is_not_reported(self, synced):
        assert "fabricated citekey" not in PreflightRepo.context(synced.run())

    def test_a_gate_that_passes_a_fabricated_citekey_is_reported(self, synced):
        synced.stub("draft", "import sys\nsys.exit(0)\n")
        context = PreflightRepo.context(synced.run())
        assert "BROKEN" in context
        assert "fabricated citekey" in context

    def test_a_gate_that_fails_for_the_wrong_reason_is_not_called_live(self, synced):
        """Exit status alone is not enough. A gate that rejects the probe
        for its *location* would also exit non-zero, and reporting that as
        a working gate is a false reassurance -- the failure mode this
        check exists to prevent."""
        synced.stub("draft", "import sys\nsys.exit(1)\n")
        context = PreflightRepo.context(synced.run())
        assert "fabricated citekey" in context


class TestLauncherFaults:
    """Static checks over settings.json, end to end through the real hook.

    One of two detectors, not the only one. A hook that fails to start
    cannot report anything itself, and this hook is started by the same
    interpreter name it vets -- so it is silent on precisely the host where
    the gate's launcher is missing. `python -m chitragupta.draft gate` makes the
    same report from the other side of that gap (#197); the check they
    share is `chitragupta/hook_launchers.py`.
    """

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
        assert "not on PATH" in context

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
    """A launcher that resolves on PATH and still cannot import the
    package -- the failure mode a venv install adds, once `python` no
    longer guarantees `chitragupta` is on its `sys.path` (#264).

    A raising `chitragupta/__init__.py` shadowed into the temp root's cwd
    stands in for that host: `python -c "import chitragupta"` searches cwd
    ('' at sys.path[0]) before the real PYTHONPATH entry, the same
    mechanism `PreflightRepo.stub` documents for the `-m` invocations.
    """

    def test_is_reported_through_the_real_hook(self, synced):
        pkg = synced.root / "chitragupta"
        pkg.mkdir(exist_ok=True)
        (pkg / "__init__.py").write_text(
            "raise ImportError('stubbed for #264')\n", encoding="utf-8"
        )
        context = PreflightRepo.context(synced.run())
        assert "cannot import chitragupta" in context

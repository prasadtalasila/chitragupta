import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from chitragupta import ledger

from tests.conftest import load_hook

REPO_ROOT = Path(__file__).resolve().parent.parent


def completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture
def gate():
    return load_hook("citation_gate_hook")


@pytest.fixture
def preflight():
    return load_hook("session_start_hook")


@pytest.fixture
def style():
    return load_hook("style_check_hook")


def emitted(capsys) -> dict | None:
    out = capsys.readouterr().out.strip()
    return json.loads(out) if out else None


class TestCitationGateHookModule:
    @pytest.fixture
    def rooted(self, gate, tmp_path, monkeypatch):
        monkeypatch.setattr(gate.draft_target, "REPO_ROOT", tmp_path)
        (tmp_path / "content" / "drafts").mkdir(parents=True)
        return gate, tmp_path

    @staticmethod
    def feed(monkeypatch, payload) -> None:
        text = payload if isinstance(payload, str) else json.dumps(payload)
        monkeypatch.setattr(sys, "stdin", io.StringIO(text))

    @pytest.mark.parametrize(
        "payload,why",
        [
            ("{not json", "invalid JSON syntax"),
            ("[]", "valid JSON that is not an object"),
            ('{"tool_input": []}', "tool_input of the wrong shape"),
            ('{"tool_input": {}}', "no file_path at all"),
            ('{"tool_input": {"file_path": ""}}', "an empty file_path"),
        ],
    )
    def test_malformed_stdin_fails_open(self, gate, monkeypatch, capsys, payload, why):
        self.feed(monkeypatch, payload)
        assert gate.main() == 0, why
        assert emitted(capsys) is None

    TWO_DRAFTS = (
        "*** Begin Patch\n*** Update File: content/drafts/a.md\n"
        "*** Update File: content/drafts/b.md\n*** End Patch\n"
    )

    def test_every_draft_in_a_patch_is_gated_in_one_call(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        drafts = root / "content" / "drafts"
        (drafts / "a.md").write_text("x\n")
        (drafts / "b.md").write_text("y\n")
        calls = []

        def run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return completed(0)

        monkeypatch.setattr(hook.subprocess, "run", run)
        payload = {"tool_name": "apply_patch", "tool_input": {"command": self.TWO_DRAFTS}}
        self.feed(monkeypatch, {**payload, "cwd": str(root)})
        assert hook.main() == 0
        cmd, kwargs = calls[0]
        assert len(calls) == 1
        assert cmd[-2:] == [str((drafts / "a.md").resolve()), str((drafts / "b.md").resolve())]
        assert kwargs["env"][hook.GATE_CALLER_ENV] == "hook"
        assert emitted(capsys) is None

    def test_an_unreadable_patch_on_a_draft_blocks(self, rooted, monkeypatch, capsys):
        hook, _ = rooted
        patch = "*** Begin Patch\n*** Frobnicate: content/drafts/a.md\n*** End Patch\n"
        self.feed(monkeypatch, {"tool_input": {"command": patch}})
        assert hook.main() == 0
        response = emitted(capsys)
        assert response["decision"] == "block"
        assert "could not be read" in response["reason"]

    def test_the_line_bound_is_the_total_over_every_draft(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        drafts = root / "content" / "drafts"
        half = "x\n" * (hook.MAX_GATED_LINES // 2 + 1)
        (drafts / "a.md").write_text(half)
        (drafts / "b.md").write_text(half)
        self.feed(monkeypatch, {"tool_input": {"command": self.TWO_DRAFTS}, "cwd": str(root)})
        assert hook.main() == 0
        assert "too large to gate" in emitted(capsys)["reason"]

    def test_a_write_outside_the_drafts_dir_is_ignored(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        elsewhere = root / "notes.md"
        elsewhere.write_text("x")
        self.feed(monkeypatch, {"tool_input": {"file_path": str(elsewhere)}})
        assert hook.main() == 0
        assert emitted(capsys) is None

    def test_a_non_gated_suffix_is_ignored(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        draft = root / "content" / "drafts" / "notes.txt"
        draft.write_text("x")
        self.feed(monkeypatch, {"tool_input": {"file_path": str(draft)}})
        assert hook.main() == 0
        assert emitted(capsys) is None

    def test_a_relative_path_resolves_against_the_hooks_own_root(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        (root / "content" / "drafts" / "rel.md").write_text("no citations\n")
        monkeypatch.setattr(hook.subprocess, "run", lambda *a, **k: completed(0))
        self.feed(monkeypatch, {"tool_input": {"file_path": "content/drafts/rel.md"}})
        assert hook.main() == 0
        assert emitted(capsys) is None

    def test_a_passing_gate_says_nothing(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        draft = root / "content" / "drafts" / "clean.md"
        draft.write_text("Plain prose.\n")
        monkeypatch.setattr(hook.subprocess, "run", lambda *a, **k: completed(0))
        self.feed(monkeypatch, {"tool_input": {"file_path": str(draft)}})
        assert hook.main() == 0
        assert emitted(capsys) is None

    @staticmethod
    def gate_and_probe(gate_result, probe_result=None, probe_error=None):
        def run(args, **kwargs):
            if "-c" in args:
                if probe_error is not None:
                    raise probe_error
                return probe_result
            return gate_result

        return run

    def test_a_failing_gate_blocks_with_the_reason(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        draft = root / "content" / "drafts" / "bad.md"
        draft.write_text("A claim [@nope_2026].\n")
        monkeypatch.setattr(
            hook.subprocess,
            "run",
            self.gate_and_probe(completed(1, stdout="FAIL @nope_2026"), probe_result=completed(0)),
        )
        self.feed(monkeypatch, {"tool_input": {"file_path": str(draft)}})
        assert hook.main() == 0  # the hook process itself always exits 0
        response = emitted(capsys)
        assert response["decision"] == "block"
        assert "Citation gate FAILED" in response["reason"]
        assert "@nope_2026" in response["reason"]

    def test_a_gate_that_could_not_read_the_ledger_blocks_without_blaming_a_citekey(
        self, rooted, monkeypatch, capsys
    ):
        hook, root = rooted
        draft = root / "content" / "drafts" / "bad.md"
        draft.write_text("A claim [@nope_2026].\n")
        monkeypatch.setattr(
            hook.subprocess,
            "run",
            self.gate_and_probe(
                completed(3, stderr="ERROR: the citation gate could not read the ledger"),
                probe_error=AssertionError("the import probe must not run"),
            ),
        )
        self.feed(monkeypatch, {"tool_input": {"file_path": str(draft)}})
        assert hook.main() == 0
        reason = emitted(capsys)["reason"]
        assert reason.startswith("The citation gate could not read the ledger")
        assert "ERROR: the citation gate could not read the ledger" in reason
        assert "Citation gate FAILED" not in reason

    def test_an_interpreter_that_cannot_import_chitragupta_is_named_not_blamed_on_the_citekey(
        self, rooted, monkeypatch, capsys
    ):
        hook, root = rooted
        draft = root / "content" / "drafts" / "bad.md"
        draft.write_text("A claim [@nope_2026].\n")
        monkeypatch.setattr(
            hook.subprocess,
            "run",
            self.gate_and_probe(
                completed(1, stderr="ModuleNotFoundError: No module named 'chitragupta'"),
                probe_result=completed(1),
            ),
        )
        self.feed(monkeypatch, {"tool_input": {"file_path": str(draft)}})
        assert hook.main() == 0
        response = emitted(capsys)
        assert response["decision"] == "block"  # still fails closed
        assert "could not run" in response["reason"].lower()
        assert "@nope_2026" not in response["reason"]
        assert "Citation gate FAILED" not in response["reason"]

    def test_a_hung_import_probe_is_treated_as_a_broken_environment(
        self, rooted, monkeypatch, capsys
    ):
        hook, root = rooted
        draft = root / "content" / "drafts" / "bad.md"
        draft.write_text("A claim [@nope_2026].\n")
        monkeypatch.setattr(
            hook.subprocess,
            "run",
            self.gate_and_probe(
                completed(1, stdout="FAIL"),
                probe_error=hook.subprocess.TimeoutExpired(cmd="python", timeout=5.0),
            ),
        )
        self.feed(monkeypatch, {"tool_input": {"file_path": str(draft)}})
        assert hook.main() == 0
        response = emitted(capsys)
        assert response["decision"] == "block"  # still fails closed
        assert "could not run" in response["reason"].lower()
        assert "Citation gate FAILED" not in response["reason"]

    @staticmethod
    def recording(calls: list, result=None, error=None):
        def run(args, **kwargs):
            calls.append((args, kwargs))
            if error is not None:
                raise error
            return result

        return run

    def test_an_oversize_draft_blocks_without_running_the_gate(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        monkeypatch.setattr(hook, "MAX_GATED_LINES", 3)
        draft = root / "content" / "drafts" / "huge.md"
        draft.write_text("line\n" * 4)
        calls = []
        monkeypatch.setattr(hook.subprocess, "run", self.recording(calls, completed(0)))
        self.feed(monkeypatch, {"tool_input": {"file_path": str(draft)}})
        assert hook.main() == 0
        response = emitted(capsys)
        assert response["decision"] == "block"
        assert "too large to gate" in response["reason"]
        assert "4 lines" in response["reason"]
        assert calls == []  # nothing was started, so nothing can be killed

    def test_a_draft_at_the_limit_is_still_gated(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        monkeypatch.setattr(hook, "MAX_GATED_LINES", 3)
        draft = root / "content" / "drafts" / "edge.md"
        draft.write_text("line\n" * 3)
        calls = []
        monkeypatch.setattr(hook.subprocess, "run", self.recording(calls, completed(0)))
        self.feed(monkeypatch, {"tool_input": {"file_path": str(draft)}})
        assert hook.main() == 0
        assert emitted(capsys) is None
        assert len(calls) == 1
        assert calls[0][1]["timeout"] == hook.GATE_TIMEOUT

    def test_an_unreadable_draft_is_left_to_the_gate(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        missing = root / "content" / "drafts" / "gone.md"
        calls = []
        failed = completed(1, stdout="FAIL gone.md")
        monkeypatch.setattr(
            hook.subprocess, "run", self.gate_and_probe(failed, probe_result=completed(0))
        )
        monkeypatch.setattr(hook, "_line_count", lambda path: calls.append(path) or None)
        self.feed(monkeypatch, {"tool_input": {"file_path": str(missing)}})
        assert hook.main() == 0
        assert calls == [missing]
        assert "Citation gate FAILED" in emitted(capsys)["reason"]

    def test_line_count_is_none_for_an_unreadable_path(self, gate, tmp_path):
        assert gate._line_count(tmp_path / "absent.md") is None
        assert gate._line_count(tmp_path) is None  # a directory
        (tmp_path / "two.md").write_bytes(b"a\n\xff\xfe not utf-8\n")
        assert gate._line_count(tmp_path / "two.md") == 2  # counted, not decoded

    def test_a_gate_that_runs_out_of_time_blocks(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        draft = root / "content" / "drafts" / "slow.md"
        draft.write_text("A claim [@nope_2026].\n")
        calls = []
        timeout = hook.subprocess.TimeoutExpired(cmd="python", timeout=hook.GATE_TIMEOUT)
        monkeypatch.setattr(hook.subprocess, "run", self.recording(calls, error=timeout))
        self.feed(monkeypatch, {"tool_input": {"file_path": str(draft)}})
        assert hook.main() == 0
        response = emitted(capsys)
        assert response["decision"] == "block"
        assert "did not finish" in response["reason"]
        assert len(calls) == 1  # the gate, and no probe after it

    def test_the_timeouts_fit_inside_the_harness_kill(self, gate):
        assert gate.GATE_TIMEOUT + gate.IMPORT_PROBE_TIMEOUT < 30

    def test_the_import_probe_uses_the_gate_calls_own_cwd(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        draft = root / "content" / "drafts" / "bad.md"
        draft.write_text("A claim [@nope_2026].\n")
        seen_cwd = []

        def run(args, **kwargs):
            if "-c" in args:
                seen_cwd.append(kwargs.get("cwd"))
                return completed(0)
            return completed(1, stdout="FAIL @nope_2026")

        monkeypatch.setattr(hook.subprocess, "run", run)
        self.feed(monkeypatch, {"tool_input": {"file_path": str(draft)}})
        assert hook.main() == 0
        assert seen_cwd == [root]  # same root the gate call above it uses


class TestLauncherFaults:
    def test_the_configs_read_are_under_the_hooks_own_root(self, preflight, tmp_path, monkeypatch):
        monkeypatch.setattr(preflight, "REPO", tmp_path)
        seen = []
        monkeypatch.setattr(
            preflight.launcher_configs, "faults", lambda root: seen.append(root) or ["a fault"]
        )
        assert preflight.launcher_faults() == ["a fault"]
        assert seen == [tmp_path]

    def test_a_fault_is_reported_as_broken(self, preflight, monkeypatch, capsys):
        monkeypatch.setattr(
            preflight.launcher_configs,
            "faults",
            lambda root: ["`python` is not on an absolute PATH entry, so a hook cannot start."],
        )
        monkeypatch.setattr(preflight, "gate_fault", lambda: None)
        monkeypatch.setattr(preflight, "corpus_stage", lambda: None)
        assert preflight.main() == 0
        context = emitted(capsys)["hookSpecificOutput"]["additionalContext"]
        assert "BROKEN: `python` is not on an absolute PATH entry" in context

    def test_no_installed_chitragupta_is_named_rather_than_silent(self, preflight, monkeypatch):
        monkeypatch.setattr(preflight, "launcher_configs", None)
        monkeypatch.setattr(preflight.sys, "executable", "/fake/python3")
        faults = preflight.launcher_faults()
        assert len(faults) == 1
        assert "no installed chitragupta visible to /fake/python3" in faults[0]


class TestModuleImportFailsCleanly:
    def test_chitragupta_itself_missing_leaves_launcher_configs_none(self, monkeypatch):
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "chitragupta":
                raise ModuleNotFoundError("no chitragupta", name="chitragupta")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)
        preflight = load_hook("session_start_hook")
        assert preflight.launcher_configs is None

    def test_a_different_missing_module_still_crashes(self, monkeypatch):
        import chitragupta  # pylint: disable=import-outside-toplevel

        monkeypatch.setitem(sys.modules, "chitragupta.hook_launchers", None)
        monkeypatch.delitem(sys.modules, "chitragupta.launcher_configs", raising=False)
        monkeypatch.delattr(chitragupta, "launcher_configs", raising=False)
        monkeypatch.delattr(chitragupta, "hook_launchers", raising=False)
        with pytest.raises(ModuleNotFoundError, match="chitragupta.hook_launchers"):
            load_hook("session_start_hook")


class TestCorpusStage:
    def test_a_corpus_layer_that_will_not_start_is_reported(self, preflight, monkeypatch):
        monkeypatch.setattr(
            preflight, "_run", lambda *a, **k: completed(1, stderr="No config file")
        )
        assert "corpus layer will not start" in preflight.corpus_stage()

    def test_a_ledger_it_cannot_read_is_reported_with_its_cause(self, preflight, monkeypatch):
        monkeypatch.setattr(
            preflight, "_run", lambda *a, **k: completed(3, stderr="ledger.sqlite-journal ...")
        )
        stage = preflight.corpus_stage()
        assert stage.startswith("BROKEN: The ledger cannot be read")
        assert "ledger.sqlite-journal" in stage
        assert "config.toml" not in stage

    def test_its_unreadable_code_is_the_package_s(self, preflight):
        assert preflight.LEDGER_UNREADABLE == ledger.EXIT_UNREADABLE

    @pytest.mark.parametrize(
        "stdout",
        [
            "No ledger at /x/ledger.sqlite.\nRun `python -m chitragupta.corpus sync` to build it.",
            "Ledger at /x/ledger.sqlite is empty.\nRun `python -m chitragupta.corpus sync`.",
        ],
    )
    def test_both_pre_sync_states_are_reported_as_a_stage(self, preflight, monkeypatch, stdout):
        monkeypatch.setattr(preflight, "_run", lambda *a, **k: completed(0, stdout=stdout))
        stage = preflight.corpus_stage()
        assert "before a first sync" in stage
        assert "BROKEN" not in stage

    def test_a_synced_corpus_says_nothing(self, preflight, monkeypatch):
        monkeypatch.setattr(
            preflight,
            "_run",
            lambda *a, **k: completed(
                0, stdout="Ledger: /x/ledger.sqlite   (642 item(s))\n\n  497  parsed\n"
            ),
        )
        assert preflight.corpus_stage() is None


class TestGateLiveness:
    def test_a_gate_that_names_the_fabricated_key_is_live(self, preflight, monkeypatch):
        monkeypatch.setattr(
            preflight,
            "_run",
            lambda *a, **k: completed(
                1, stdout=f"FAIL @{preflight.FABRICATED} not found in ledger"
            ),
        )
        assert preflight.gate_fault() is None

    def test_a_gate_that_passes_the_probe_is_not_live(self, preflight, monkeypatch):
        monkeypatch.setattr(preflight, "_run", lambda *a, **k: completed(0, stdout="OK"))
        assert "did not refuse a fabricated citekey" in preflight.gate_fault()

    def test_a_failure_that_never_names_the_key_is_not_live(self, preflight, monkeypatch):
        monkeypatch.setattr(
            preflight,
            "_run",
            lambda *a, **k: completed(1, stderr="resolves outside the content directory"),
        )
        fault = preflight.gate_fault()
        assert "could not run its self-test (exit 1)" in fault
        assert "resolves outside the content directory" in fault

    def test_a_gate_that_could_not_read_its_ledger_is_not_said_to_accept(
        self, preflight, monkeypatch
    ):
        monkeypatch.setattr(
            preflight,
            "_run",
            lambda *a, **k: completed(3, stderr="ERROR: the citation gate could not read"),
        )
        fault = preflight.gate_fault()
        assert "could not run its self-test (exit 3)" in fault
        assert "did not refuse" not in fault

    def test_the_probe_writes_nothing_that_outlives_it(self, preflight, monkeypatch):
        seen = {}

        def capture(module, *args, **overrides):
            seen["draft"] = Path(args[-1])
            seen["content"] = Path(overrides["CONTENT_DIR"])
            return completed(1, stdout=preflight.FABRICATED)

        monkeypatch.setattr(preflight, "_run", capture)
        assert preflight.gate_fault() is None
        assert not seen["draft"].exists()
        assert REPO_ROOT not in seen["content"].parents


class TestRunAndMain:
    def test_run_really_starts_a_child(self, preflight):
        result = preflight._run("chitragupta.corpus", "ledger")
        assert result.returncode == 0

    def test_main_says_nothing_when_all_three_checks_pass(self, preflight, monkeypatch, capsys):
        monkeypatch.setattr(preflight, "launcher_faults", list)
        monkeypatch.setattr(preflight, "gate_fault", lambda: None)
        monkeypatch.setattr(preflight, "corpus_stage", lambda: None)
        assert preflight.main() == 0
        assert capsys.readouterr().out == ""

    def test_main_reports_every_note_in_one_json_document(self, preflight, monkeypatch, capsys):
        monkeypatch.setattr(preflight, "launcher_faults", lambda: ["a launcher is wrong"])
        monkeypatch.setattr(
            preflight, "gate_fault", lambda: "the gate did not refuse a fabricated citekey"
        )
        monkeypatch.setattr(preflight, "corpus_stage", lambda: "not synced yet")
        assert preflight.main() == 0
        context = emitted(capsys)["hookSpecificOutput"]["additionalContext"]
        assert "BROKEN: a launcher is wrong" in context
        assert "BROKEN: the gate did not refuse a fabricated citekey" in context
        assert "not synced yet" in context


class TestStyleCheckHookModule:
    @pytest.fixture
    def rooted(self, style, tmp_path, monkeypatch):
        monkeypatch.setattr(style.draft_target, "REPO_ROOT", tmp_path)
        (tmp_path / "content" / "drafts").mkdir(parents=True)
        return style, tmp_path

    @staticmethod
    def feed(monkeypatch, file_path) -> None:
        monkeypatch.setattr(
            sys, "stdin", io.StringIO(json.dumps({"tool_input": {"file_path": str(file_path)}}))
        )

    @staticmethod
    def checker(monkeypatch, hook, stdout):
        monkeypatch.setattr(hook.subprocess, "run", lambda *a, **k: completed(0, stdout=stdout))

    @staticmethod
    def payload(findings, language=None):
        return json.dumps(
            {
                "notice": "Review aid, not a gate.",
                "warnings": [],
                "drafts": [
                    {
                        "draft": "d.md",
                        "language": language,
                        "language_source": "nothing",
                        "findings": findings,
                        "proposed_language": None,
                    }
                ],
            }
        )

    def test_a_draft_with_findings_is_reported(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        draft = root / "content" / "drafts" / "a.md"
        draft.write_text("obviously fine\n")
        self.checker(
            monkeypatch,
            hook,
            self.payload(
                [
                    {
                        "rule": "chitragupta.DefectMarkers",
                        "match": "obviously",
                        "line": 1,
                        "message": "'obviously' is a defect marker",
                        "severity": "warning",
                        "count": 1,
                    }
                ],
                language="en-GB",
            ),
        )
        self.feed(monkeypatch, draft)
        assert hook.main() == 0
        context = emitted(capsys)["hookSpecificOutput"]["additionalContext"]
        assert "defect marker" in context
        assert "§9's decidable rules only" in context

    def test_every_draft_in_a_patch_is_checked_in_one_call(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        drafts = root / "content" / "drafts"
        (drafts / "a.md").write_text("x\n")
        (drafts / "b.md").write_text("y\n")
        calls = []
        monkeypatch.setattr(
            hook.subprocess, "run", lambda cmd, **k: calls.append(cmd) or completed(0, "{}")
        )
        patch = (
            "*** Begin Patch\n*** Update File: content/drafts/a.md\n"
            "*** Update File: content/drafts/b.md\n*** End Patch\n"
        )
        payload = {"tool_input": {"command": patch}, "cwd": str(root)}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        assert hook.main() == 0
        assert [Path(p).name for p in calls[0][-2:]] == ["a.md", "b.md"]

    def test_an_unreadable_patch_is_left_to_the_gate(self, rooted, monkeypatch, capsys):
        hook, _ = rooted
        patch = "*** Begin Patch\n*** Frobnicate: content/drafts/a.md\n*** End Patch\n"
        monkeypatch.setattr(
            sys, "stdin", io.StringIO(json.dumps({"tool_input": {"command": patch}}))
        )
        assert hook.main() == 0
        assert emitted(capsys) is None

    def test_it_never_emits_a_blocking_decision(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        draft = root / "content" / "drafts" / "b.md"
        draft.write_text("x\n")
        self.checker(
            monkeypatch,
            hook,
            self.payload(
                [
                    {
                        "rule": "r",
                        "match": "m",
                        "line": 1,
                        "message": "msg",
                        "severity": "warning",
                        "count": 1,
                    }
                ]
            ),
        )
        self.feed(monkeypatch, draft)
        hook.main()
        out = capsys.readouterr().out
        assert "decision" not in out
        assert json.loads(out)["hookSpecificOutput"]["hookEventName"] == "PostToolUse"

    def test_a_repeated_finding_carries_its_count(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        draft = root / "content" / "drafts" / "c.md"
        draft.write_text("x\n")
        self.checker(
            monkeypatch,
            hook,
            self.payload(
                [
                    {
                        "rule": "r",
                        "match": "m",
                        "line": 2,
                        "message": "msg",
                        "severity": "warning",
                        "count": 4,
                    }
                ],
                language="en-GB",
            ),
        )
        self.feed(monkeypatch, draft)
        hook.main()
        assert "(x4)" in emitted(capsys)["hookSpecificOutput"]["additionalContext"]

    def test_an_unrecorded_dialect_is_flagged_beside_the_findings(
        self, rooted, monkeypatch, capsys
    ):
        hook, root = rooted
        draft = root / "content" / "drafts" / "d.md"
        draft.write_text("x\n")
        self.checker(
            monkeypatch,
            hook,
            self.payload(
                [
                    {
                        "rule": "r",
                        "match": "m",
                        "line": 1,
                        "message": "msg",
                        "severity": "warning",
                        "count": 1,
                    }
                ],
                language=None,
            ),
        )
        self.feed(monkeypatch, draft)
        hook.main()
        assert "dialect: not checked" in emitted(capsys)["hookSpecificOutput"]["additionalContext"]

    def test_a_recorded_dialect_is_not_mentioned(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        draft = root / "content" / "drafts" / "e.md"
        draft.write_text("x\n")
        self.checker(
            monkeypatch,
            hook,
            self.payload(
                [
                    {
                        "rule": "r",
                        "match": "m",
                        "line": 1,
                        "message": "msg",
                        "severity": "warning",
                        "count": 1,
                    }
                ],
                language="en-GB",
            ),
        )
        self.feed(monkeypatch, draft)
        hook.main()
        assert (
            "dialect: not checked" not in emitted(capsys)["hookSpecificOutput"]["additionalContext"]
        )

    @pytest.mark.parametrize(
        "stdout,why",
        [
            ("", "the checker produced nothing at all"),
            ("not json", "unparseable stdout"),
            ("[]", "valid JSON of the wrong shape"),
            ('{"warnings": ["vale is not on PATH"]}', "no drafts key -- vale missing"),
            ('{"drafts": ["a bare string"]}', "a draft entry that is not a mapping"),
            ('{"drafts": [{"findings": []}]}', "a draft with no findings"),
            ('{"drafts": [{"findings": null}]}', "findings explicitly null"),
            ('{"drafts": [{"findings": ["not a mapping"]}]}', "a finding of the wrong shape"),
        ],
    )
    def test_it_stays_silent(self, rooted, monkeypatch, capsys, stdout, why):
        hook, root = rooted
        draft = root / "content" / "drafts" / "f.md"
        draft.write_text("x\n")
        self.checker(monkeypatch, hook, stdout)
        self.feed(monkeypatch, draft)
        assert hook.main() == 0, why
        assert capsys.readouterr().out == "", why

    @pytest.mark.parametrize("count", [None, "3", [], {}])
    def test_a_malformed_count_costs_one_line_not_the_whole_report(
        self, rooted, monkeypatch, capsys, count
    ):
        hook, root = rooted
        draft = root / "content" / "drafts" / "g.md"
        draft.write_text("x\n")
        self.checker(
            monkeypatch,
            hook,
            json.dumps(
                {
                    "drafts": [
                        {
                            "language": "en-GB",
                            "findings": [
                                {
                                    "rule": "r",
                                    "match": "m",
                                    "line": 1,
                                    "message": "msg",
                                    "count": count,
                                }
                            ],
                        }
                    ]
                }
            ),
        )
        self.feed(monkeypatch, draft)
        assert hook.main() == 0
        context = emitted(capsys)["hookSpecificOutput"]["additionalContext"]
        assert "msg" in context
        assert "(x" not in context

    def test_a_write_that_is_not_a_draft_never_runs_the_checker(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        elsewhere = root / "notes.md"
        elsewhere.write_text("obviously\n")

        def explode(*a, **k):
            raise AssertionError("the checker must not run for a non-draft")

        monkeypatch.setattr(hook.subprocess, "run", explode)
        self.feed(monkeypatch, elsewhere)
        assert hook.main() == 0
        assert capsys.readouterr().out == ""

    def test_a_draft_that_vanished_is_not_reported_as_clean(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        gone = root / "content" / "drafts" / "gone.md"

        def explode(*a, **k):
            raise AssertionError("the checker must not run for a missing file")

        monkeypatch.setattr(hook.subprocess, "run", explode)
        self.feed(monkeypatch, gone)
        assert hook.main() == 0
        assert capsys.readouterr().out == ""

"""The two hooks in `.claude/hooks/`, exercised as modules rather than as
scripts, so their branches are measured.

**Why this file exists beside the two subprocess test files.** A hook is
run by the harness as `python <path>`, and testing it the way it is really
run means spawning it -- which is what `tests/test_citation_gate_hook.py`
and `tests/test_session_start_hook.py` do. Those tests prove the contract:
given this stdin, the process exits 0 and writes that. What they cannot do
is report coverage. Measured before this file was written, 22 passing
subprocess tests left `session_start_hook.py` at **0.00%**, and
`citation_gate_hook.py` sat at an accidental 76.74% -- accidental because
it depended on which tests happened to inherit pytest-cov's subprocess
bootstrap rather than strip it, so the number measured the test harness
and not the hook.

Instrumenting the children instead was the obvious alternative and is
ruled out on the record: `tests/test_citation_gate_hook.py`'s
`_IS_COVERAGE_BOOTSTRAP` documents that coverage started in a child with a
different cwd records statement-only data while the parent records branch
data, and the run then dies at combine time *after* every test has passed.

So the split is deliberate, and each half does what only it can:

| | subprocess tests | this file |
|---|---|---|
| Proves | the harness contract | every branch |
| Runs the hook as | the harness does | an imported module |
| Contributes coverage | no | yes |

Neither is redundant. A refactor that broke the stdin envelope would pass
this file and fail the other two.
"""

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = REPO_ROOT / ".claude" / "hooks"


def load(name: str):
    """A fresh module object, so one test's monkeypatching cannot leak.

    `.claude/hooks` goes on `sys.path` first because a hook is run by
    absolute path in production, which puts its own directory there --
    that is what makes `import draft_target` resolve with no path
    manipulation inside the hook. Loading by spec does not reproduce it,
    so the test harness has to.
    """
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode,
                                       stdout=stdout, stderr=stderr)


@pytest.fixture
def gate():
    return load("citation_gate_hook")


@pytest.fixture
def preflight():
    return load("session_start_hook")


@pytest.fixture
def style():
    return load("style_check_hook")


def emitted(capsys) -> dict | None:
    out = capsys.readouterr().out.strip()
    return json.loads(out) if out else None


class TestCitationGateHookModule:
    """`citation_gate_hook.main()`, branch by branch.

    Since the draft-detection branches moved to `draft_target.py` this
    class covers what is left: the gate call itself and the block. The
    detection cases live in `tests/test_draft_target.py`, and are reached
    here only through the two that survive at this level -- a payload that
    names no draft, and one that does."""

    @pytest.fixture
    def rooted(self, gate, tmp_path, monkeypatch):
        """The hook, believing it lives in `tmp_path/.claude/hooks/`.

        The root now comes from `draft_target.REPO_ROOT`, so that is what
        moves. Both the hook and the helper read it at call time, which is
        what makes one patch enough.
        """
        monkeypatch.setattr(gate.draft_target, "REPO_ROOT", tmp_path)
        (tmp_path / "content" / "drafts").mkdir(parents=True)
        return gate, tmp_path

    @staticmethod
    def feed(monkeypatch, payload) -> None:
        text = payload if isinstance(payload, str) else json.dumps(payload)
        monkeypatch.setattr(sys, "stdin", io.StringIO(text))

    @pytest.mark.parametrize("payload,why", [
        ("{not json", "invalid JSON syntax"),
        ("[]", "valid JSON that is not an object"),
        ('{"tool_input": []}', "tool_input of the wrong shape"),
        ('{"tool_input": {}}', "no file_path at all"),
        ('{"tool_input": {"file_path": ""}}', "an empty file_path"),
    ])
    def test_malformed_stdin_fails_open(self, gate, monkeypatch, capsys, payload, why):
        self.feed(monkeypatch, payload)
        assert gate.main() == 0, why
        assert emitted(capsys) is None

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

    def test_a_relative_path_resolves_against_the_hooks_own_root(
            self, rooted, monkeypatch, capsys):
        """The near-miss the hook's docstring records: a substring match on
        "/content/drafts/" would skip a relative path entirely."""
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

    def test_a_failing_gate_blocks_with_the_reason(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        draft = root / "content" / "drafts" / "bad.md"
        draft.write_text("A claim [@nope_2026].\n")
        monkeypatch.setattr(hook.subprocess, "run",
                            lambda *a, **k: completed(1, stdout="FAIL @nope_2026"))
        self.feed(monkeypatch, {"tool_input": {"file_path": str(draft)}})
        assert hook.main() == 0  # the hook process itself always exits 0
        response = emitted(capsys)
        assert response["decision"] == "block"
        assert "@nope_2026" in response["reason"]


class TestLauncherFaults:
    """`session_start_hook.launcher_faults()` over a settings file it owns."""

    @pytest.fixture
    def rooted(self, preflight, tmp_path, monkeypatch):
        monkeypatch.setattr(preflight, "REPO", tmp_path)
        (tmp_path / ".claude").mkdir()
        return preflight, tmp_path

    @staticmethod
    def settings(root: Path, data) -> None:
        path = root / ".claude" / "settings.json"
        path.write_text(data if isinstance(data, str) else json.dumps(data))

    def test_absent_settings_is_not_a_fault(self, rooted):
        hook, _ = rooted
        assert hook.launcher_faults() == []

    @pytest.mark.parametrize("data,why", [
        ("{not json", "unparseable"),
        ({"permissions": {}}, "no hooks key"),
        ({"hooks": "not a mapping"}, "hooks of the wrong shape"),
    ])
    def test_unusable_settings_is_not_a_fault(self, rooted, data, why):
        hook, root = rooted
        self.settings(root, data)
        assert hook.launcher_faults() == [], why

    def test_a_sound_exec_form_launcher_is_clean(self, rooted):
        hook, root = rooted
        self.settings(root, {"hooks": {"PostToolUse": [{"hooks": [
            {"command": "python3", "args": ["${CLAUDE_PROJECT_DIR}/x.py"]}]}]}})
        assert hook.launcher_faults() == []

    def test_an_entry_with_no_hooks_list_is_skipped(self, rooted):
        hook, root = rooted
        self.settings(root, {"hooks": {"PostToolUse": [{"matcher": "Write"}]}})
        assert hook.launcher_faults() == []

    def test_an_interpreter_off_path_is_a_fault(self, rooted):
        hook, root = rooted
        self.settings(root, {"hooks": {"SessionStart": [{"hooks": [
            {"command": "python4.2", "args": ["${CLAUDE_PROJECT_DIR}/x.py"]}]}]}})
        assert "not on PATH" in hook.launcher_faults()[0]

    def test_an_unbraced_placeholder_is_a_fault(self, rooted):
        hook, root = rooted
        self.settings(root, {"hooks": {"PostToolUse": [{"hooks": [
            {"command": 'python3 "$CLAUDE_PROJECT_DIR/x.py"'}]}]}})
        assert "unbraced" in hook.launcher_faults()[0]

    def test_a_braced_placeholder_in_shell_form_is_clean(self, rooted):
        """The replace-then-search is what separates these two, and getting
        it backwards would flag every correct launcher."""
        hook, root = rooted
        self.settings(root, {"hooks": {"PostToolUse": [{"hooks": [
            {"command": 'python3 "${CLAUDE_PROJECT_DIR}/x.py"'}]}]}})
        assert hook.launcher_faults() == []

    def test_an_unbraced_placeholder_inside_args_is_a_fault(self, preflight):
        assert "unbraced" in preflight._launcher_fault(
            {"command": "python3", "args": ["$CLAUDE_PROJECT_DIR/x.py"]})[0]

    def test_an_entry_with_no_command_is_skipped(self, preflight):
        assert preflight._launcher_fault({"type": "command"}) == []

    @pytest.mark.parametrize("events,why", [
        ({"PostToolUse": {"not": "a list"}}, "an event holding a mapping"),
        ({"PostToolUse": ["a bare string"]}, "an entry that is not a mapping"),
        ({"PostToolUse": [{"hooks": "not a list"}]}, "hooks of the wrong shape"),
        ({"PostToolUse": [{"hooks": ["a bare string"]}]}, "a hook that is not a mapping"),
        ({"PostToolUse": [{"hooks": [{"command": "   "}]}]}, "a whitespace-only command"),
        ({"PostToolUse": [{"hooks": [{"command": 42}]}]}, "a command that is not a string"),
        ({"PostToolUse": [{"hooks": [{"command": "python3", "args": [7]}]}]},
         "an argument that is not a string"),
        ({"PostToolUse": [{"hooks": [{"command": "python3", "args": "not a list"}]}]},
         "args of the wrong shape"),
    ])
    def test_a_settings_file_of_any_shape_is_survivable(self, rooted, events, why):
        """Every level of this file is the harness's shape to define, not
        this hook's to assume. A raise anywhere here reaches `main`'s
        catch-all and takes the *whole* report down with it -- the corpus
        stage and the gate check included -- so the hook would go silent
        over a settings file it merely found odd."""
        hook, root = rooted
        self.settings(root, {"hooks": events})
        assert hook.launcher_faults() == [], why


class TestCorpusStage:
    """`session_start_hook.corpus_stage()`: three answers, one of which is
    not a fault."""

    def test_a_corpus_layer_that_will_not_start_is_reported(self, preflight, monkeypatch):
        monkeypatch.setattr(preflight, "_run",
                            lambda *a, **k: completed(1, stderr="No config file"))
        assert "corpus layer will not start" in preflight.corpus_stage()

    @pytest.mark.parametrize("stdout", [
        "No ledger at /x/ledger.sqlite.\nRun `python -m src.corpus sync` to build it.",
        "Ledger at /x/ledger.sqlite is empty.\nRun `python -m src.corpus sync`.",
    ])
    def test_both_pre_sync_states_are_reported_as_a_stage(
            self, preflight, monkeypatch, stdout):
        """An absent ledger and an empty one print different sentences. The
        first implementation matched only the second and stayed silent on a
        fresh clone, which is the case the hook exists to handle."""
        monkeypatch.setattr(preflight, "_run", lambda *a, **k: completed(0, stdout=stdout))
        stage = preflight.corpus_stage()
        assert "before a first sync" in stage
        assert "BROKEN" not in stage

    def test_a_synced_corpus_says_nothing(self, preflight, monkeypatch):
        monkeypatch.setattr(preflight, "_run", lambda *a, **k: completed(
            0, stdout="Ledger: /x/ledger.sqlite   (642 item(s))\n\n  497  parsed\n"))
        assert preflight.corpus_stage() is None


class TestGateLiveness:
    def test_a_gate_that_names_the_fabricated_key_is_live(self, preflight, monkeypatch):
        monkeypatch.setattr(preflight, "_run", lambda *a, **k: completed(
            1, stdout=f"FAIL @{preflight.FABRICATED} not found in ledger"))
        assert preflight.gate_is_live() is True

    def test_a_gate_that_passes_the_probe_is_not_live(self, preflight, monkeypatch):
        monkeypatch.setattr(preflight, "_run", lambda *a, **k: completed(0, stdout="OK"))
        assert preflight.gate_is_live() is False

    def test_a_failure_that_never_names_the_key_is_not_live(self, preflight, monkeypatch):
        """A gate rejecting the probe for its *location* also exits
        non-zero. Counting that as a working gate is a false reassurance."""
        monkeypatch.setattr(preflight, "_run", lambda *a, **k: completed(
            1, stderr="resolves outside the content directory"))
        assert preflight.gate_is_live() is False

    def test_the_probe_writes_nothing_that_outlives_it(self, preflight, monkeypatch):
        """The temporary tree is the point: a probe that left a draft with a
        fabricated citekey under content/ would be the one thing this
        project forbids."""
        seen = {}

        def capture(module, *args, **overrides):
            seen["draft"] = Path(args[-1])
            seen["content"] = Path(overrides["CONTENT_DIR"])
            return completed(1, stdout=preflight.FABRICATED)

        monkeypatch.setattr(preflight, "_run", capture)
        assert preflight.gate_is_live() is True
        assert not seen["draft"].exists()
        assert REPO_ROOT not in seen["content"].parents


class TestRunAndMain:
    def test_run_really_starts_a_child(self, preflight):
        """`_run` is the only place a subprocess is actually spawned, so one
        real call keeps the mocking above honest."""
        result = preflight._run("src.corpus", "ledger")
        assert result.returncode == 0

    def test_main_says_nothing_when_all_three_checks_pass(
            self, preflight, monkeypatch, capsys):
        monkeypatch.setattr(preflight, "launcher_faults", list)
        monkeypatch.setattr(preflight, "gate_is_live", lambda: True)
        monkeypatch.setattr(preflight, "corpus_stage", lambda: None)
        assert preflight.main() == 0
        assert capsys.readouterr().out == ""

    def test_main_reports_every_note_in_one_json_document(
            self, preflight, monkeypatch, capsys):
        monkeypatch.setattr(preflight, "launcher_faults", lambda: ["a launcher is wrong"])
        monkeypatch.setattr(preflight, "gate_is_live", lambda: False)
        monkeypatch.setattr(preflight, "corpus_stage", lambda: "not synced yet")
        assert preflight.main() == 0
        context = emitted(capsys)["hookSpecificOutput"]["additionalContext"]
        assert "BROKEN: a launcher is wrong" in context
        assert "did not refuse a fabricated citekey" in context
        assert "not synced yet" in context


class TestStyleCheckHookModule:
    """`style_check_hook`, the advisory half of the PostToolUse pair.

    Every case here is about *not* speaking. An advisory hook that reports
    on every write is one the reader learns to skip -- and it shares a
    matcher with the citation gate, so the attention it spends is spent on
    the gate's channel too.
    """

    @pytest.fixture
    def rooted(self, style, tmp_path, monkeypatch):
        monkeypatch.setattr(style.draft_target, "REPO_ROOT", tmp_path)
        (tmp_path / "content" / "drafts").mkdir(parents=True)
        return style, tmp_path

    @staticmethod
    def feed(monkeypatch, file_path) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(
            json.dumps({"tool_input": {"file_path": str(file_path)}})))

    @staticmethod
    def checker(monkeypatch, hook, stdout):
        monkeypatch.setattr(hook.subprocess, "run",
                            lambda *a, **k: completed(0, stdout=stdout))

    @staticmethod
    def payload(findings, language=None):
        return json.dumps({"notice": "Review aid, not a gate.", "warnings": [],
                           "drafts": [{"draft": "d.md", "language": language,
                                       "language_source": "nothing",
                                       "findings": findings,
                                       "proposed_language": None}]})

    def test_a_draft_with_findings_is_reported(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        draft = root / "content" / "drafts" / "a.md"
        draft.write_text("obviously fine\n")
        self.checker(monkeypatch, hook, self.payload(
            [{"rule": "chitragupta.DefectMarkers", "match": "obviously", "line": 1,
              "message": "'obviously' is a defect marker", "severity": "warning",
              "count": 1}], language="en-GB"))
        self.feed(monkeypatch, draft)
        assert hook.main() == 0
        context = emitted(capsys)["hookSpecificOutput"]["additionalContext"]
        assert "defect marker" in context
        assert "§9's decidable rules only" in context

    def test_it_never_emits_a_blocking_decision(self, rooted, monkeypatch, capsys):
        """The rule that separates this hook from the one beside it."""
        hook, root = rooted
        draft = root / "content" / "drafts" / "b.md"
        draft.write_text("x\n")
        self.checker(monkeypatch, hook, self.payload(
            [{"rule": "r", "match": "m", "line": 1, "message": "msg",
              "severity": "warning", "count": 1}]))
        self.feed(monkeypatch, draft)
        hook.main()
        out = capsys.readouterr().out
        assert "decision" not in out
        assert json.loads(out)["hookSpecificOutput"]["hookEventName"] == "PostToolUse"

    def test_a_repeated_finding_carries_its_count(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        draft = root / "content" / "drafts" / "c.md"
        draft.write_text("x\n")
        self.checker(monkeypatch, hook, self.payload(
            [{"rule": "r", "match": "m", "line": 2, "message": "msg",
              "severity": "warning", "count": 4}], language="en-GB"))
        self.feed(monkeypatch, draft)
        hook.main()
        assert "(x4)" in emitted(capsys)["hookSpecificOutput"]["additionalContext"]

    def test_an_unrecorded_dialect_is_flagged_beside_the_findings(
            self, rooted, monkeypatch, capsys):
        """With no `language:` line no dialect rule runs, so the list is not
        the whole picture -- the same trap the verbatim caveat prevents."""
        hook, root = rooted
        draft = root / "content" / "drafts" / "d.md"
        draft.write_text("x\n")
        self.checker(monkeypatch, hook, self.payload(
            [{"rule": "r", "match": "m", "line": 1, "message": "msg",
              "severity": "warning", "count": 1}], language=None))
        self.feed(monkeypatch, draft)
        hook.main()
        assert "dialect: not checked" in \
            emitted(capsys)["hookSpecificOutput"]["additionalContext"]

    def test_a_recorded_dialect_is_not_mentioned(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        draft = root / "content" / "drafts" / "e.md"
        draft.write_text("x\n")
        self.checker(monkeypatch, hook, self.payload(
            [{"rule": "r", "match": "m", "line": 1, "message": "msg",
              "severity": "warning", "count": 1}], language="en-GB"))
        self.feed(monkeypatch, draft)
        hook.main()
        assert "dialect: not checked" not in \
            emitted(capsys)["hookSpecificOutput"]["additionalContext"]

    @pytest.mark.parametrize("stdout,why", [
        ("", "the checker produced nothing at all"),
        ("not json", "unparseable stdout"),
        ("[]", "valid JSON of the wrong shape"),
        ('{"warnings": ["vale is not on PATH"]}', "no drafts key -- vale missing"),
        ('{"drafts": ["a bare string"]}', "a draft entry that is not a mapping"),
        ('{"drafts": [{"findings": []}]}', "a draft with no findings"),
        ('{"drafts": [{"findings": null}]}', "findings explicitly null"),
        ('{"drafts": [{"findings": ["not a mapping"]}]}', "a finding of the wrong shape"),
    ])
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
            self, rooted, monkeypatch, capsys, count):
        """Found by an OpenCodeReview pass. `None > 1` raises, and that
        exception is caught at the module tail -- so a single bad count in
        another command's output would silently cost the entire report
        rather than the one line it belongs to."""
        hook, root = rooted
        draft = root / "content" / "drafts" / "g.md"
        draft.write_text("x\n")
        self.checker(monkeypatch, hook, json.dumps({"drafts": [{
            "language": "en-GB",
            "findings": [{"rule": "r", "match": "m", "line": 1,
                          "message": "msg", "count": count}]}]}))
        self.feed(monkeypatch, draft)
        assert hook.main() == 0
        context = emitted(capsys)["hookSpecificOutput"]["additionalContext"]
        assert "msg" in context
        assert "(x" not in context

    def test_a_write_that_is_not_a_draft_never_runs_the_checker(
            self, rooted, monkeypatch, capsys):
        hook, root = rooted
        elsewhere = root / "notes.md"
        elsewhere.write_text("obviously\n")

        def explode(*a, **k):
            raise AssertionError("the checker must not run for a non-draft")

        monkeypatch.setattr(hook.subprocess, "run", explode)
        self.feed(monkeypatch, elsewhere)
        assert hook.main() == 0
        assert capsys.readouterr().out == ""

    def test_a_draft_that_vanished_is_not_reported_as_clean(
            self, rooted, monkeypatch, capsys):
        """The measured trap: `src.draft style` returns zero findings for a
        path that does not exist, because it never inspects vale's return
        code. Reporting that as a clean draft is the one thing an advisory
        check must never fake, so the hook stats the file itself."""
        hook, root = rooted
        gone = root / "content" / "drafts" / "gone.md"

        def explode(*a, **k):
            raise AssertionError("the checker must not run for a missing file")

        monkeypatch.setattr(hook.subprocess, "run", explode)
        self.feed(monkeypatch, gone)
        assert hook.main() == 0
        assert capsys.readouterr().out == ""

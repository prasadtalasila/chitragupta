import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = REPO_ROOT / ".claude" / "hooks"


def load():
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location(
        "code_standards_hook", HOOKS / "code_standards_hook.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook():
    return load()


def stdin_with(file_path):
    return io.StringIO(json.dumps({"tool_input": {"file_path": str(file_path)}}))


class TestWhichWritesItCaresAbout:
    def test_a_source_file_under_chitragupta_is_a_target(self, hook):
        target = hook.source_target(stdin_with(REPO_ROOT / "chitragupta" / "config.py"))
        assert target == REPO_ROOT / "chitragupta" / "config.py"

    def test_a_script_is_a_target(self, hook):
        target = hook.source_target(stdin_with(REPO_ROOT / "scripts" / "release.py"))
        assert target is not None

    def test_a_relative_path_is_resolved_against_the_repo_root(self, hook):
        assert hook.source_target(stdin_with("chitragupta/config.py")) is not None

    def test_a_draft_is_not_a_target(self, hook):
        assert hook.source_target(stdin_with(REPO_ROOT / "content" / "drafts" / "s.md")) is None

    def test_a_test_module_is_not_a_target(self, hook):
        assert hook.source_target(stdin_with(REPO_ROOT / "tests" / "test_config.py")) is None

    def test_a_non_python_file_is_not_a_target(self, hook):
        assert hook.source_target(stdin_with(REPO_ROOT / "docs" / "HOOKS.md")) is None

    def test_traversal_cannot_pass_for_a_source_file(self, hook):
        assert hook.source_target(stdin_with("chitragupta/../../etc/passwd")) is None

    def test_a_path_outside_the_repo_is_not_a_target(self, hook, tmp_path):
        assert hook.source_target(stdin_with(tmp_path / "m.py")) is None


class TestMalformedStdinFailsOpen:
    def test_invalid_json(self, hook):
        assert hook.source_target(io.StringIO("{not json")) is None

    def test_json_that_is_not_an_object(self, hook):
        assert hook.source_target(io.StringIO("[1, 2]")) is None

    def test_tool_input_that_is_not_a_dict(self, hook):
        assert hook.source_target(io.StringIO(json.dumps({"tool_input": "nope"}))) is None

    def test_no_file_path_at_all(self, hook):
        assert hook.source_target(io.StringIO(json.dumps({"tool_input": {}}))) is None


class TestWhatItSays:
    def test_a_clean_file_says_nothing(self, hook, monkeypatch, capsys):
        monkeypatch.setattr(hook, "source_target", lambda _: Path("chitragupta/config.py"))
        monkeypatch.setattr(hook, "_findings", lambda _: [])
        assert hook.main() == 0
        assert capsys.readouterr().out == ""

    def test_a_crossing_is_reported_in_the_standard_envelope(self, hook, monkeypatch, capsys):
        monkeypatch.setattr(hook, "source_target", lambda _: Path("chitragupta/config.py"))
        monkeypatch.setattr(
            hook,
            "_findings",
            lambda _: [{"rule": "C1", "name": "m.py::f", "count": 30, "limit": 25}],
        )
        assert hook.main() == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert "m.py::f" in payload["hookSpecificOutput"]["additionalContext"]

    def test_it_never_emits_a_block_decision(self, hook, monkeypatch, capsys):
        monkeypatch.setattr(hook, "source_target", lambda _: Path("chitragupta/config.py"))
        monkeypatch.setattr(
            hook,
            "_findings",
            lambda _: [{"rule": "C2", "name": "m.py", "count": 300, "limit": 250}],
        )
        hook.main()
        assert "decision" not in capsys.readouterr().out

    def test_a_write_it_does_not_care_about_says_nothing(self, hook, monkeypatch, capsys):
        monkeypatch.setattr(hook, "source_target", lambda _: None)
        assert hook.main() == 0
        assert capsys.readouterr().out == ""


class TestRunningTheScanner:
    def test_it_reads_the_scanner_json(self, hook, tmp_path):
        path = tmp_path / "m.py"
        path.write_text("\n".join(f"x{i} = {i}" for i in range(300)), encoding="utf-8")
        assert [f["rule"] for f in hook._findings(path)] == ["C2"]

    def test_a_missing_scanner_is_silent_not_an_error(self, hook, monkeypatch, tmp_path):
        monkeypatch.setattr(hook, "SCANNER", tmp_path / "absent.py")
        assert hook._findings(tmp_path / "m.py") == []

    def test_an_installed_project_never_launches_its_scanner(self, hook, monkeypatch):
        def launched(*args, **kwargs):
            raise AssertionError("the scanner was launched")

        monkeypatch.setattr(hook.safe_path, "installed_elsewhere", lambda root: True)
        monkeypatch.setattr(hook.subprocess, "run", launched)
        assert hook._findings(Path("m.py")) == []

    def test_unreadable_scanner_output_is_silent(self, hook, monkeypatch):
        class _Result:
            stdout = "not json"

        monkeypatch.setattr(hook.subprocess, "run", lambda *a, **k: _Result())
        assert hook._findings(Path("m.py")) == []

    def test_output_without_a_findings_list_is_silent(self, hook, monkeypatch):
        class _Result:
            stdout = json.dumps({"unexpected": True})

        monkeypatch.setattr(hook.subprocess, "run", lambda *a, **k: _Result())
        assert hook._findings(Path("m.py")) == []

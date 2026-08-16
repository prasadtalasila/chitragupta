"""`src/hook_launchers.py`: can each registered hook's launcher start?

These cases were `tests/test_hook_modules.py::TestLauncherFaults` until the
check moved out of `.claude/hooks/session_start_hook.py` and into `src/`,
so that a command the working interpreter runs -- `python -m src.draft
gate` -- can report a launcher the preflight is unable to report, because
the preflight is started by the same interpreter name it vets (#197).

Most of them are shape cases, and they matter more than they look. A raise
anywhere in reading a settings file reaches the preflight's catch-all and
takes the *whole* report down with it, so the check must find nothing
rather than raise on a file it merely finds odd.
"""

import json
from pathlib import Path

import pytest

from src import hook_launchers


@pytest.fixture
def settings(tmp_path):
    """Write a settings file, get its path back."""
    def write(data) -> Path:
        path = tmp_path / "settings.json"
        path.write_text(data if isinstance(data, str) else json.dumps(data),
                        encoding="utf-8")
        return path
    return write


class TestFaults:
    def test_absent_settings_is_not_a_fault(self, tmp_path):
        assert hook_launchers.faults(tmp_path / "nothing-here.json") == []

    @pytest.mark.parametrize("data,why", [
        ("{not json", "unparseable"),
        ({"permissions": {}}, "no hooks key"),
        ({"hooks": "not a mapping"}, "hooks of the wrong shape"),
    ])
    def test_unusable_settings_is_not_a_fault(self, settings, data, why):
        assert hook_launchers.faults(settings(data)) == [], why

    def test_a_sound_exec_form_launcher_is_clean(self, settings):
        assert hook_launchers.faults(settings({"hooks": {"PostToolUse": [{"hooks": [
            {"command": "python", "args": ["${CLAUDE_PROJECT_DIR}/x.py"]}]}]}})) == []

    def test_an_entry_with_no_hooks_list_is_skipped(self, settings):
        assert hook_launchers.faults(
            settings({"hooks": {"PostToolUse": [{"matcher": "Write"}]}})) == []

    def test_an_interpreter_off_path_is_a_fault(self, settings):
        found = hook_launchers.faults(settings({"hooks": {"SessionStart": [{"hooks": [
            {"command": "python4.2", "args": ["${CLAUDE_PROJECT_DIR}/x.py"]}]}]}}))
        assert "not on PATH" in found[0]

    def test_one_missing_interpreter_is_reported_once(self, settings):
        """Both hooks are launched the same way, so the naive version said
        the same sentence twice -- which reads as a defect in the reporter
        rather than in the launcher."""
        dead = {"command": "python4.2", "args": ["${CLAUDE_PROJECT_DIR}/x.py"]}
        found = hook_launchers.faults(settings({"hooks": {
            "PostToolUse": [{"hooks": [dead]}], "SessionStart": [{"hooks": [dead]}]}}))
        assert len(found) == 1

    def test_two_different_faults_both_survive(self, settings):
        found = hook_launchers.faults(settings({"hooks": {"PostToolUse": [{"hooks": [
            {"command": "python4.2", "args": ["${CLAUDE_PROJECT_DIR}/x.py"]},
            {"command": 'python "$CLAUDE_PROJECT_DIR/x.py"'}]}]}}))
        assert len(found) == 2

    def test_an_unbraced_placeholder_is_a_fault(self, settings):
        found = hook_launchers.faults(settings({"hooks": {"PostToolUse": [{"hooks": [
            {"command": 'python "$CLAUDE_PROJECT_DIR/x.py"'}]}]}}))
        assert "unbraced" in found[0]

    def test_a_braced_placeholder_in_shell_form_is_clean(self, settings):
        """The replace-then-search is what separates these two, and getting
        it backwards would flag every correct launcher."""
        assert hook_launchers.faults(settings({"hooks": {"PostToolUse": [{"hooks": [
            {"command": 'python "${CLAUDE_PROJECT_DIR}/x.py"'}]}]}})) == []

    def test_a_default_settings_path_is_this_repositorys_own(self):
        """`faults()` takes a path so a caller can point it at a throwaway
        tree; called bare it reads the settings file next to this code."""
        assert hook_launchers.SETTINGS == (
            Path(__file__).resolve().parent.parent / ".claude" / "settings.json")

    @pytest.mark.parametrize("events,why", [
        ({"PostToolUse": {"not": "a list"}}, "an event holding a mapping"),
        ({"PostToolUse": ["a bare string"]}, "an entry that is not a mapping"),
        ({"PostToolUse": [{"hooks": "not a list"}]}, "hooks of the wrong shape"),
        ({"PostToolUse": [{"hooks": ["a bare string"]}]}, "a hook that is not a mapping"),
        ({"PostToolUse": [{"hooks": [{"command": "   "}]}]}, "a whitespace-only command"),
        ({"PostToolUse": [{"hooks": [{"command": 42}]}]}, "a command that is not a string"),
        ({"PostToolUse": [{"hooks": [{"command": "python", "args": [7]}]}]},
         "an argument that is not a string"),
        ({"PostToolUse": [{"hooks": [{"command": "python", "args": "not a list"}]}]},
         "args of the wrong shape"),
    ])
    def test_a_settings_file_of_any_shape_is_survivable(self, settings, events, why):
        assert hook_launchers.faults(settings({"hooks": events})) == [], why


class TestOneLauncher:
    """`_launcher_fault` directly, for the two cases a whole settings file
    would only reach the long way round."""

    def test_an_unbraced_placeholder_inside_args_is_a_fault(self):
        found = hook_launchers._launcher_fault(
            {"command": "python", "args": ["$CLAUDE_PROJECT_DIR/x.py"]})
        assert "unbraced" in found[0]

    def test_an_entry_with_no_command_is_skipped(self):
        assert hook_launchers._launcher_fault({"type": "command"}) == []

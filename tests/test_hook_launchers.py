"""`chitragupta/hook_launchers.py`: can each registered hook's launcher start?

These cases were `tests/test_hook_modules.py::TestLauncherFaults` until the
check moved out of `.claude/hooks/session_start_hook.py` and into `chitragupta/`,
so that a command the working interpreter runs -- `python -m chitragupta.draft
gate` -- can report a launcher the preflight is unable to report, because
the preflight is started by the same interpreter name it vets (#197).

Most of them are shape cases, and they matter more than they look. A raise
anywhere in reading a settings file reaches the preflight's catch-all and
takes the *whole* report down with it, so the check must find nothing
rather than raise on a file it merely finds odd.
"""

import json
import stat
import sys
from pathlib import Path

import pytest

from chitragupta import hook_launchers


@pytest.fixture
def settings(tmp_path):
    """Write a settings file, get its path back."""

    def write(data) -> Path:
        path = tmp_path / "settings.json"
        path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
        return path

    return write


class TestFaults:
    def test_absent_settings_is_not_a_fault(self, tmp_path):
        assert hook_launchers.faults(tmp_path / "nothing-here.json") == []

    @pytest.mark.parametrize(
        "data,why",
        [
            ("{not json", "unparseable"),
            ({"permissions": {}}, "no hooks key"),
            ({"hooks": "not a mapping"}, "hooks of the wrong shape"),
        ],
    )
    def test_unusable_settings_is_not_a_fault(self, settings, data, why):
        assert hook_launchers.faults(settings(data)) == [], why

    def test_a_sound_exec_form_launcher_is_clean(self, settings):
        assert (
            hook_launchers.faults(
                settings(
                    {
                        "hooks": {
                            "PostToolUse": [
                                {
                                    "hooks": [
                                        {
                                            "command": "python",
                                            "args": ["${CLAUDE_PROJECT_DIR}/x.py"],
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                )
            )
            == []
        )

    def test_an_entry_with_no_hooks_list_is_skipped(self, settings):
        assert (
            hook_launchers.faults(settings({"hooks": {"PostToolUse": [{"matcher": "Write"}]}}))
            == []
        )

    def test_an_interpreter_off_path_is_a_fault(self, settings):
        found = hook_launchers.faults(
            settings(
                {
                    "hooks": {
                        "SessionStart": [
                            {
                                "hooks": [
                                    {"command": "python4.2", "args": ["${CLAUDE_PROJECT_DIR}/x.py"]}
                                ]
                            }
                        ]
                    }
                }
            )
        )
        assert "not on PATH" in found[0]

    def test_one_missing_interpreter_is_reported_once(self, settings):
        """Both hooks are launched the same way, so the naive version said
        the same sentence twice -- which reads as a defect in the reporter
        rather than in the launcher."""
        dead = {"command": "python4.2", "args": ["${CLAUDE_PROJECT_DIR}/x.py"]}
        found = hook_launchers.faults(
            settings(
                {"hooks": {"PostToolUse": [{"hooks": [dead]}], "SessionStart": [{"hooks": [dead]}]}}
            )
        )
        assert len(found) == 1

    def test_two_different_faults_both_survive(self, settings):
        found = hook_launchers.faults(
            settings(
                {
                    "hooks": {
                        "PostToolUse": [
                            {
                                "hooks": [
                                    {
                                        "command": "python4.2",
                                        "args": ["${CLAUDE_PROJECT_DIR}/x.py"],
                                    },
                                    {"command": 'python "$CLAUDE_PROJECT_DIR/x.py"'},
                                ]
                            }
                        ]
                    }
                }
            )
        )
        assert len(found) == 2

    def test_an_unbraced_placeholder_is_a_fault(self, settings):
        found = hook_launchers.faults(
            settings(
                {
                    "hooks": {
                        "PostToolUse": [
                            {"hooks": [{"command": 'python "$CLAUDE_PROJECT_DIR/x.py"'}]}
                        ]
                    }
                }
            )
        )
        assert "unbraced" in found[0]

    def test_a_braced_placeholder_in_shell_form_is_clean(self, settings):
        """The replace-then-search is what separates these two, and getting
        it backwards would flag every correct launcher."""
        assert (
            hook_launchers.faults(
                settings(
                    {
                        "hooks": {
                            "PostToolUse": [
                                {"hooks": [{"command": 'python "${CLAUDE_PROJECT_DIR}/x.py"'}]}
                            ]
                        }
                    }
                )
            )
            == []
        )

    def test_a_default_settings_path_is_this_repositorys_own(self):
        """`faults()` takes a path so a caller can point it at a throwaway
        tree; called bare it reads the settings file next to this code."""
        assert hook_launchers.SETTINGS == (
            Path(__file__).resolve().parent.parent / ".claude" / "settings.json"
        )

    @pytest.mark.parametrize(
        "events,why",
        [
            ({"PostToolUse": {"not": "a list"}}, "an event holding a mapping"),
            ({"PostToolUse": ["a bare string"]}, "an entry that is not a mapping"),
            ({"PostToolUse": [{"hooks": "not a list"}]}, "hooks of the wrong shape"),
            ({"PostToolUse": [{"hooks": ["a bare string"]}]}, "a hook that is not a mapping"),
            ({"PostToolUse": [{"hooks": [{"command": "   "}]}]}, "a whitespace-only command"),
            ({"PostToolUse": [{"hooks": [{"command": 42}]}]}, "a command that is not a string"),
            (
                {"PostToolUse": [{"hooks": [{"command": "python", "args": [7]}]}]},
                "an argument that is not a string",
            ),
            (
                {"PostToolUse": [{"hooks": [{"command": "python", "args": "not a list"}]}]},
                "args of the wrong shape",
            ),
        ],
    )
    def test_a_settings_file_of_any_shape_is_survivable(self, settings, events, why):
        assert hook_launchers.faults(settings({"hooks": events})) == [], why


class TestOneLauncher:
    """`_launcher_fault` directly, for the two cases a whole settings file
    would only reach the long way round."""

    def test_an_unbraced_placeholder_inside_args_is_a_fault(self):
        found = hook_launchers._launcher_fault(
            {"command": "python", "args": ["$CLAUDE_PROJECT_DIR/x.py"]}
        )
        assert "unbraced" in found[0]

    def test_an_entry_with_no_command_is_skipped(self):
        assert hook_launchers._launcher_fault({"type": "command"}) == []


class TestProjectRoot:
    """Where this module looks for `.claude/settings.json`.

    It cannot ask `chitragupta.config`, and the module docstring says why: that
    import raises without a `config.toml`, which would break both
    docs/CLI.md's tier-1 promise and the preflight's ability to run in a
    fresh clone. So the marker walk is deliberately duplicated here, and
    these tests pin the copy rather than trusting the original's.
    """

    def test_walks_up_to_the_marker(self, tmp_path, monkeypatch):
        (tmp_path / "config.toml").write_text("", encoding="utf-8")
        deep = tmp_path / "content" / "drafts"
        deep.mkdir(parents=True)
        monkeypatch.chdir(deep)
        assert hook_launchers._project_root() == tmp_path.resolve()

    def test_falls_back_beside_the_package_when_there_is_no_marker(self, tmp_path, monkeypatch):
        """Not a guess at some unrelated directory: the checkout it is in.

        `.claude/` belongs to the user's project, so once this code is
        installed the `__file__`-derived answer is wrong -- it would look
        inside site-packages. It stays the fallback because a checkout
        with no config.toml yet is exactly when the preflight most needs
        to run.
        """
        bare = tmp_path / "bare"
        bare.mkdir()
        monkeypatch.chdir(bare)
        expected = Path(hook_launchers.__file__).resolve().parent.parent
        assert hook_launchers._project_root() == expected


class TestImportFaultDirectly:
    """`_import_fault` on its own, for the shapes a whole settings file
    would only reach by first resolving `shutil.which` -- which is the
    caller's job, not this function's."""

    def test_a_program_that_cannot_be_spawned_at_all_is_not_a_fault(self):
        """`faults()` only calls this once `shutil.which` has already
        resolved the program, so a program that can't be spawned at all
        is `OSError` from a race (removed between the two checks) rather
        than something new to report -- the PATH check already covers it."""
        assert hook_launchers._import_fault("/nonexistent/nowhere-abcx") is None

    def test_an_interpreter_that_can_import_the_package_is_clean(self):
        assert hook_launchers._import_fault(sys.executable) is None


@pytest.fixture
def fake_interpreter(tmp_path):
    """A throwaway program that ignores its arguments and exits with a
    chosen code, optionally after a delay -- stands in for a `python` that
    starts but cannot import `chitragupta`, or one too slow to answer."""

    def make(code: int, sleep: float = 0) -> str:
        script = tmp_path / "fake-interpreter"
        script.write_text(
            f"#!/bin/sh\n{f'sleep {sleep}' if sleep else ''}\nexit {code}\n", encoding="utf-8"
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return str(script)

    return make


@pytest.mark.skipif(
    sys.platform == "win32", reason="a shebang script is not directly executable on Windows"
)
class TestImportProbeThroughFaults:
    """`faults()`'s new check, end to end through a settings file: once a
    launcher resolves on PATH, can it import `chitragupta`?"""

    def test_an_interpreter_that_cannot_import_the_package_is_a_fault(
        self, settings, fake_interpreter
    ):
        program = fake_interpreter(code=1)
        found = hook_launchers.faults(
            settings(
                {
                    "hooks": {
                        "PostToolUse": [
                            {
                                "hooks": [
                                    {"command": program, "args": ["${CLAUDE_PROJECT_DIR}/x.py"]}
                                ]
                            }
                        ]
                    }
                }
            )
        )
        assert "cannot import chitragupta" in found[0]

    def test_a_timeout_is_reported_as_a_fault_never_as_clean(
        self, settings, fake_interpreter, monkeypatch
    ):
        monkeypatch.setattr(hook_launchers, "IMPORT_PROBE_TIMEOUT", 0.05)
        program = fake_interpreter(code=0, sleep=1)
        found = hook_launchers.faults(
            settings(
                {
                    "hooks": {
                        "PostToolUse": [
                            {
                                "hooks": [
                                    {"command": program, "args": ["${CLAUDE_PROJECT_DIR}/x.py"]}
                                ]
                            }
                        ]
                    }
                }
            )
        )
        assert "did not respond" in found[0]

    def test_a_working_interpreter_adds_no_fault(self, settings):
        found = hook_launchers.faults(
            settings(
                {
                    "hooks": {
                        "PostToolUse": [
                            {
                                "hooks": [
                                    {
                                        "command": sys.executable,
                                        "args": ["${CLAUDE_PROJECT_DIR}/x.py"],
                                    }
                                ]
                            }
                        ]
                    }
                }
            )
        )
        assert found == []


class TestImportProbeIsPerDistinctProgram:
    """The probe is one subprocess per distinct launcher, not one per hook
    entry -- both because two entries naming the same program is one
    problem, not two, and because a slow probe should not multiply."""

    def test_runs_once_for_a_program_two_entries_share(self, settings, monkeypatch):
        calls = []
        monkeypatch.setattr(
            hook_launchers, "_import_fault", lambda program: calls.append(program) or None
        )
        same = {"command": sys.executable, "args": ["${CLAUDE_PROJECT_DIR}/x.py"]}
        hook_launchers.faults(
            settings(
                {"hooks": {"PostToolUse": [{"hooks": [same]}], "SessionStart": [{"hooks": [same]}]}}
            )
        )
        assert calls == [sys.executable]

    def test_never_runs_for_a_program_not_on_path(self, settings, monkeypatch):
        calls = []
        monkeypatch.setattr(
            hook_launchers, "_import_fault", lambda program: calls.append(program) or None
        )
        hook_launchers.faults(
            settings(
                {
                    "hooks": {
                        "PostToolUse": [
                            {
                                "hooks": [
                                    {"command": "python4.2", "args": ["${CLAUDE_PROJECT_DIR}/x.py"]}
                                ]
                            }
                        ]
                    }
                }
            )
        )
        assert calls == []

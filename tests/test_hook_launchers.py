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

REPO_ROOT = Path(__file__).resolve().parent.parent


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
    starts but cannot import `chitragupta`, or one too slow to answer.

    Named `python3`, and that is load-bearing since #509/m-38: the import
    probe now only runs against a program whose basename looks like a
    Python interpreter, so a stand-in called anything else would not be
    probed at all and these tests would pass vacuously.
    """

    def make(code: int, sleep: float = 0) -> str:
        script = tmp_path / "python3"
        script.write_text(
            f"#!/bin/sh\n{f'sleep {sleep}' if sleep else ''}\nexit {code}\n", encoding="utf-8"
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return str(script)

    return make


def entry_for(program: str) -> dict:
    """One PostToolUse settings payload naming `program` as its launcher."""
    return {
        "hooks": {
            "PostToolUse": [
                {"hooks": [{"command": program, "args": ["${CLAUDE_PROJECT_DIR}/x.py"]}]}
            ]
        }
    }


@pytest.mark.skipif(
    sys.platform == "win32", reason="a shebang script is not directly executable on Windows"
)
class TestImportProbeThroughFaults:
    """`faults()`'s new check, end to end through a settings file: once a
    launcher resolves on PATH, can it import `chitragupta`?

    Every case reaches its stand-in interpreter by putting its directory
    first on PATH and naming it bare, never by path -- since #637 that is
    the only route the probe will take (see
    TestTheImportProbeOnlyRunsAgainstABareName), so a path-qualified
    stand-in would make these pass vacuously."""

    def test_an_interpreter_that_cannot_import_the_package_is_a_fault(
        self, settings, fake_interpreter, monkeypatch
    ):
        program = fake_interpreter(code=1)
        monkeypatch.setenv("PATH", str(Path(program).parent), prepend=":")
        found = hook_launchers.faults(settings(entry_for("python3")))
        assert "cannot import chitragupta" in found[0]

    def test_a_timeout_is_reported_as_a_fault_never_as_clean(
        self, settings, fake_interpreter, monkeypatch
    ):
        monkeypatch.setattr(hook_launchers, "IMPORT_PROBE_TIMEOUT", 0.05)
        program = fake_interpreter(code=0, sleep=1)
        monkeypatch.setenv("PATH", str(Path(program).parent), prepend=":")
        found = hook_launchers.faults(settings(entry_for("python3")))
        assert "did not respond" in found[0]

    def test_a_working_interpreter_adds_no_fault(self, settings, tmp_path, monkeypatch):
        # A bare-named shim onto the suite's own interpreter: the probe
        # only takes bare names now, and this interpreter is the one
        # guaranteed to import chitragupta.
        shim = tmp_path / "python3"
        shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        monkeypatch.setenv("PATH", str(tmp_path), prepend=":")
        found = hook_launchers.faults(settings(entry_for("python3")))
        assert found == []


class TestTheImportProbeOnlyRunsAgainstABareName:
    """#637. The probe executes whatever program the settings file names,
    and that file was found by walking cwd's ancestors for a config.toml
    -- so inside an untrusted tree (a cloned project, /tmp), a planted
    settings.json naming `/that/tree/python3` handed an attacker's binary
    to subprocess.run with the user's privileges:
    `_is_python_interpreter` checks only the basename, and `shutil.which`
    resolves a path-qualified program as-is rather than via PATH. Only a
    bare name -- resolved against PATH, the user's own environment, which
    the walked-to directory cannot rewrite -- may be probed."""

    @pytest.mark.skipif(
        sys.platform == "win32", reason="a shebang script is not directly executable on Windows"
    )
    def test_a_path_qualified_interpreter_is_never_executed(self, settings, tmp_path):
        marker = tmp_path / "ran"
        planted = tmp_path / "python3"
        planted.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 1\n', encoding="utf-8")
        planted.chmod(planted.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        found = hook_launchers.faults(settings(entry_for(str(planted))))
        assert not marker.exists(), "the planted binary was executed"
        # It resolves and is not probed, so it contributes no fault at
        # all -- reporting less is the accepted price of not executing a
        # file merely because a directory we walked into named it.
        assert found == []

    def test_a_bare_name_resolved_from_path_is_still_probed(self, settings, monkeypatch):
        calls = []
        monkeypatch.setattr(
            hook_launchers, "_import_fault", lambda program: calls.append(program) or None
        )
        monkeypatch.setattr(hook_launchers.shutil, "which", lambda program: "/usr/bin/python3")
        hook_launchers.faults(settings(entry_for("python3")))
        assert calls == ["python3"]

    @pytest.mark.parametrize(
        "program",
        ["/usr/bin/python3", "./python3", "venv/bin/python", "C:/Py/python.exe", "..\\python.exe"],
    )
    def test_a_path_qualified_name_is_not_bare(self, program):
        assert not hook_launchers._is_bare_command(program)

    @pytest.mark.parametrize("program", ["python", "python3", "python3.12", "python.exe", "py"])
    def test_a_bare_name_is_bare(self, program):
        assert hook_launchers._is_bare_command(program)


class TestImportProbeIsPerDistinctProgram:
    """The probe is one subprocess per distinct launcher, not one per hook
    entry -- both because two entries naming the same program is one
    problem, not two, and because a slow probe should not multiply."""

    def test_runs_once_for_a_program_two_entries_share(self, settings, monkeypatch):
        calls = []
        monkeypatch.setattr(
            hook_launchers, "_import_fault", lambda program: calls.append(program) or None
        )
        monkeypatch.setattr(hook_launchers.shutil, "which", lambda program: "/usr/bin/python3")
        # Bare-named, since #637 made that the only shape the probe takes.
        same = {"command": "python3", "args": ["${CLAUDE_PROJECT_DIR}/x.py"]}
        hook_launchers.faults(
            settings(
                {"hooks": {"PostToolUse": [{"hooks": [same]}], "SessionStart": [{"hooks": [same]}]}}
            )
        )
        assert calls == ["python3"]

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


class TestTheImportProbeOnlyRunsAgainstAPython:
    """m-38 (#509). `_import_fault` runs `<program> -c "import
    chitragupta"`, which is a Python invocation and nothing else. Against
    a non-Python launcher -- `bash`, `uv`, `node` -- the program either
    rejects `-c` or runs something unrelated, exits non-zero, and gets
    reported as "cannot import chitragupta" every single session: a fault
    about the probe, not about the hook."""

    @pytest.mark.parametrize(
        "program",
        [
            "python",
            "python3",
            "python3.12",
            "/usr/bin/python3.13",
            "C:/Py/python.exe",
            "py",
            "pypy3",
        ],
    )
    def test_an_interpreter_is_probed(self, program):
        assert hook_launchers._is_python_interpreter(program)

    @pytest.mark.parametrize("program", ["bash", "/bin/sh", "uv", "node", "sh.exe"])
    def test_anything_else_is_not(self, program):
        assert not hook_launchers._is_python_interpreter(program)

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason=(
            "a shebang script is not directly executable on Windows, so "
            "`shutil.which` never resolves it and the PATH fault fires "
            "before the probe this case is about -- the same reason "
            "TestImportProbeThroughFaults skips there"
        ),
    )
    def test_a_bash_launcher_produces_no_import_fault(self, settings, tmp_path):
        """End to end, and genuinely red before the fix: `bash -c "import
        chitragupta"` exits non-zero on any host."""
        program = tmp_path / "bash"
        program.write_text("#!/bin/sh\nexit 2\n", encoding="utf-8")
        program.chmod(program.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        found = hook_launchers.faults(
            settings(
                {
                    "hooks": {
                        "PostToolUse": [
                            {
                                "hooks": [
                                    {
                                        "command": str(program),
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


class TestTheInstallScriptProvidesTheLauncher:
    """The other half of a launcher fault: who is supposed to *fix* it.

    `.claude/settings.json` names `python`, and docs/HOOKS.md records why
    that name rather than `python3` -- but on a Debian-family host without
    `python-is-python3` the name does not exist outside an activated venv,
    so every hook this repository registers fails in the one way this
    module exists to notice: silently. `faults()` above can only report
    it. `scripts/install_full_pipeline.sh` is the only thing in the tree
    positioned to prevent it, and these cases pin both halves of how it
    does so.

    Read as text rather than run: `os-deps` needs apt and root, and the
    package list is a fact about the file, not about this host.
    """

    def _script(self) -> str:
        return (REPO_ROOT / "scripts" / "install_full_pipeline.sh").read_text(encoding="utf-8")

    def test_os_deps_installs_the_launcher_name(self):
        """The direct fix, in the stage that is allowed to touch apt."""
        assert "python-is-python3" in self._script()

    def test_the_package_is_probed_before_it_is_installed(self):
        """The `libglib2.0-0t64` precedent, for the same reason it exists
        there: `apt-get install` takes no alternatives, so naming a
        package a release does not carry fails the whole stage rather
        than the one line.

        Through the *shared* `apt_has_candidate`, not a second copy of
        the probe -- adding the second caller is what turned that idiom
        into something with one home."""
        script = self._script()
        probe = script.index('apt_has_candidate "$launcher_pkg"')
        install = script.index("sudo_if_needed apt-get install")
        assert probe < install
        assert script.count("apt-cache policy") == 1, "one probe, two callers"

    def test_python_deps_reports_launcher_faults(self):
        """The load-bearing half. `os-deps` is apt/root-only and opt-in,
        so a host that ran only `python-deps` still has the fault and no
        way to hear about it."""
        script = self._script()
        assert "report_launcher_faults" in script
        assert script.index("report_launcher_faults()") < script.index("install_python_deps()"), (
            "define the helper before the stage that calls it"
        )

    def test_the_report_calls_hook_launchers_rather_than_copying_it(self):
        """`faults()` already answers both halves -- on PATH, and able to
        import the package. A second copy in shell is a second place for
        the answer to drift, which is the invariant DEVELOPER-AGENTS.md
        states for the install script generally."""
        assert "hook_launchers" in self._script()

    def test_a_launcher_fault_does_not_fail_the_install(self):
        """It is a warning about the *harness*, not about the install,
        which by that point has already succeeded. Failing here would
        make a working venv look like a broken one."""
        script = self._script()
        body = script[script.index("report_launcher_faults()") :]
        body = body[: body.index("\n}\n")]
        assert "exit 1" not in body

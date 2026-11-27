import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from chitragupta import hook_launchers, import_probe

from tests.test_citation_gate_hook import _IS_COVERAGE_BOOTSTRAP

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def installed_package_on_pythonpath(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))


@pytest.fixture
def settings(tmp_path):
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
        assert "not on an absolute PATH entry" in found[0]

    def test_one_missing_interpreter_is_reported_once(self, settings):
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
    def test_an_unbraced_placeholder_inside_args_is_a_fault(self):
        found = hook_launchers._launcher_fault(
            {"command": "python", "args": ["$CLAUDE_PROJECT_DIR/x.py"]}
        )
        assert "unbraced" in found[0]

    def test_an_entry_with_no_command_is_skipped(self):
        assert hook_launchers._launcher_fault({"type": "command"}) == []

    def test_a_path_qualified_launcher_that_is_not_there_is_a_fault(self, tmp_path):
        missing = str(tmp_path / "nowhere" / "python")
        assert hook_launchers._launcher_fault({"command": missing, "args": []}) == [
            f"`{missing}` is not an executable file, so a hook cannot start."
        ]


class TestProjectRoot:
    def test_walks_up_to_the_marker(self, tmp_path, monkeypatch):
        (tmp_path / "config.toml").write_text("", encoding="utf-8")
        deep = tmp_path / "content" / "drafts"
        deep.mkdir(parents=True)
        monkeypatch.chdir(deep)
        assert hook_launchers._project_root() == tmp_path.resolve()

    def test_falls_back_beside_the_package_when_there_is_no_marker(self, tmp_path, monkeypatch):
        bare = tmp_path / "bare"
        bare.mkdir()
        monkeypatch.chdir(bare)
        expected = Path(hook_launchers.__file__).resolve().parent.parent
        assert hook_launchers._project_root() == expected


class TestImportFaultDirectly:
    def test_a_program_that_cannot_be_spawned_at_all_is_not_a_fault(self):
        assert import_probe.import_fault("nowhere-abcx") is None

    def test_an_interpreter_that_can_import_the_package_is_clean(self, monkeypatch):
        monkeypatch.setenv("PATH", str(Path(sys.executable).parent))
        assert import_probe.import_fault(Path(sys.executable).name) is None

    def test_a_program_that_resolves_but_cannot_be_spawned_is_not_a_fault(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(hook_launchers.programs, "resolve_program", lambda name: str(tmp_path))
        assert import_probe.import_fault("python3") is None


@pytest.fixture
def fake_interpreter(tmp_path):
    def make(code: int, sleep: float = 0) -> str:
        script = tmp_path / "python3"
        script.write_text(
            f"#!/bin/sh\n{f'sleep {sleep}' if sleep else ''}\nexit {code}\n", encoding="utf-8"
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return str(script)

    return make


def _plant(stem: Path, marker: Path) -> Path:
    if sys.platform == "win32":
        path = stem.with_name(stem.name + ".bat")
        path.write_text(f'@echo off\r\ntype nul > "{marker}"\r\nexit /b 1\r\n', encoding="utf-8")
        return path
    stem.write_text(f'#!/bin/sh\n: > "{marker}"\nexit 1\n', encoding="utf-8")
    stem.chmod(stem.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return stem


def _inert(stem: Path) -> Path:
    path = stem.with_name(stem.name + ".exe") if sys.platform == "win32" else stem
    path.write_text("", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


def entry_for(program: str) -> dict:
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
        monkeypatch.setattr(import_probe, "IMPORT_PROBE_TIMEOUT", 0.05)
        program = fake_interpreter(code=0, sleep=1)
        monkeypatch.setenv("PATH", str(Path(program).parent), prepend=":")
        found = hook_launchers.faults(settings(entry_for("python3")))
        assert "did not respond" in found[0]

    def test_a_working_interpreter_adds_no_fault(self, settings, tmp_path, monkeypatch):
        shim = tmp_path / "python3"
        shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        monkeypatch.setenv("PATH", str(tmp_path), prepend=":")
        found = hook_launchers.faults(settings(entry_for("python3")))
        assert found == []


class TestTheImportProbeOnlyRunsAgainstABareName:
    def test_a_path_qualified_interpreter_is_never_executed(self, settings, tmp_path):
        marker = tmp_path / "ran"
        _plant(tmp_path / "python3", marker)
        found = hook_launchers.faults(settings(entry_for(str(tmp_path / "python3"))))
        assert not marker.exists(), "the planted binary was executed"
        assert found == []

    def test_a_python_planted_in_the_project_is_never_executed(
        self, settings, tmp_path, monkeypatch
    ):
        marker = tmp_path / "ran"
        project = tmp_path / "project"
        project.mkdir()
        _plant(project / "python", marker)
        (tmp_path / "bin").mkdir()
        _inert(tmp_path / "bin" / "python")
        monkeypatch.chdir(project)
        monkeypatch.setenv("PATH", os.pathsep.join([".", "", str(tmp_path / "bin")]))
        hook_launchers.faults(settings(entry_for("python")))
        assert not marker.exists(), "the planted binary was executed"

    def test_a_launcher_only_a_relative_path_entry_finds_is_reported_missing(
        self, settings, tmp_path, monkeypatch
    ):
        marker = tmp_path / "ran"
        (tmp_path / "relbin").mkdir()
        _plant(tmp_path / "relbin" / "python", marker)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PATH", "relbin")
        found = hook_launchers.faults(settings(entry_for("python")))
        assert found == ["`python` is not on an absolute PATH entry, so a hook cannot start."]
        assert not marker.exists(), "the relative-entry binary was executed"

    def test_the_probe_is_handed_the_absolute_path_path_resolved(
        self, settings, tmp_path, monkeypatch
    ):
        project = tmp_path / "project"
        project.mkdir()
        for name in ("python", "python.exe", "python.bat", "python.cmd"):
            planted = project / name
            planted.write_text("", encoding="utf-8")
            planted.chmod(planted.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        (tmp_path / "bin").mkdir()
        real = _inert(tmp_path / "bin" / "python")
        monkeypatch.chdir(project)
        monkeypatch.setenv("PATH", os.pathsep.join([".", "", str(tmp_path / "bin")]))
        launched = []

        def record(argv, **kwargs):  # pylint: disable=unused-argument
            launched.append(Path(argv[0]))
            return subprocess.CompletedProcess(argv, 0)

        monkeypatch.setattr(import_probe.subprocess, "run", record)
        hook_launchers.faults(settings(entry_for("python")))
        assert launched == [real]

    def test_a_bare_name_resolved_from_path_is_still_probed(self, settings, monkeypatch):
        calls = []
        monkeypatch.setattr(
            import_probe, "import_fault", lambda program, env=None: calls.append(program) or None
        )
        monkeypatch.setattr(
            hook_launchers.programs, "resolve_program", lambda program: "/usr/bin/python3"
        )
        hook_launchers.faults(settings(entry_for("python3")))
        assert calls == ["python3"]

    @pytest.mark.parametrize(
        "program",
        ["/usr/bin/python3", "./python3", "venv/bin/python", "C:/Py/python.exe", "..\\python.exe"],
    )
    def test_a_path_qualified_name_is_not_bare(self, program):
        assert not import_probe.is_bare_command(program)

    @pytest.mark.parametrize("program", ["python", "python3", "python3.12", "python.exe", "py"])
    def test_a_bare_name_is_bare(self, program):
        assert import_probe.is_bare_command(program)


class TestImportProbeIsPerDistinctProgram:
    def test_runs_once_for_a_program_two_entries_share(self, settings, monkeypatch):
        calls = []
        monkeypatch.setattr(
            import_probe, "import_fault", lambda program, env=None: calls.append(program) or None
        )
        monkeypatch.setattr(
            hook_launchers.programs, "resolve_program", lambda program: "/usr/bin/python3"
        )
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
            import_probe.subprocess, "run", lambda argv, **kwargs: calls.append(argv)
        )
        found = hook_launchers.faults(
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
        assert found == ["`python4.2` is not on an absolute PATH entry, so a hook cannot start."]


class TestTheImportProbeOnlyRunsAgainstAPython:
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
        assert import_probe.is_python_interpreter(program)

    @pytest.mark.parametrize("program", ["bash", "/bin/sh", "uv", "node", "sh.exe"])
    def test_anything_else_is_not(self, program):
        assert not import_probe.is_python_interpreter(program)

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
    def _script(self) -> str:
        return (REPO_ROOT / "scripts" / "install_full_pipeline.sh").read_text(encoding="utf-8")

    def test_os_deps_installs_the_launcher_name(self):
        assert "python-is-python3" in self._script()

    def test_the_package_is_probed_before_it_is_installed(self):
        script = self._script()
        probe = script.index('apt_has_candidate "$launcher_pkg"')
        install = script.index("sudo_if_needed apt-get install")
        assert probe < install
        assert script.count("apt-cache policy") == 1, "one probe, two callers"

    def test_python_deps_reports_launcher_faults(self):
        script = self._script()
        assert "report_launcher_faults" in script
        assert script.index("report_launcher_faults()") < script.index("install_python_deps()"), (
            "define the helper before the stage that calls it"
        )

    def test_the_report_calls_hook_launchers_rather_than_copying_it(self):
        assert "hook_launchers" in self._script()

    def test_a_launcher_fault_does_not_fail_the_install(self):
        script = self._script()
        body = script[script.index("report_launcher_faults()") :]
        body = body[: body.index("\n}\n")]
        assert "exit 1" not in body


class TestTheProbeNeverImportsAPlantedPackage:
    def test_a_checkout_keeps_its_cwd_entry(self):
        assert import_probe.probe_env(REPO_ROOT / ".claude" / "settings.json") is None

    def test_an_installed_package_project_is_probed_safe_path(self, tmp_path):
        env = import_probe.probe_env(tmp_path / ".claude" / "settings.json")
        assert env["PYTHONSAFEPATH"] == "1"
        assert env["PYTHONPATH"] == str(REPO_ROOT)  # the rest of the environment survives

    @pytest.mark.skipif(
        sys.platform == "win32", reason="probes the bare `python` a POSIX PATH resolves"
    )
    def test_a_planted_package_is_not_what_the_probe_imports(self, tmp_path, monkeypatch):
        (tmp_path / ".claude").mkdir()
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.write_text(json.dumps(entry_for(Path(sys.executable).name)), encoding="utf-8")
        sentinel = tmp_path / "planted-ran"
        (tmp_path / "chitragupta").mkdir()
        (tmp_path / "chitragupta" / "__init__.py").write_text(
            f"open({str(sentinel)!r}, 'w').close()\n", encoding="utf-8"
        )
        monkeypatch.setenv("PATH", f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}")
        for name in [k for k in os.environ if _IS_COVERAGE_BOOTSTRAP(k)]:
            monkeypatch.delenv(name)
        monkeypatch.chdir(tmp_path)

        assert hook_launchers.faults(settings_path) == []
        assert not sentinel.exists(), "the probe imported the planted chitragupta/"

import pytest

import chitragupta.install as install


class RecordedRun:
    def __init__(self, returncode=0):
        self.returncode = returncode
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        return self


class TestRefusals:
    @pytest.mark.parametrize("stage", ["python-deps", "dev-deps", "all"])
    def test_a_repo_shaped_stage_is_refused_by_name(self, stage, capsys):
        assert install.main([stage]) == 1
        err = capsys.readouterr().err
        assert stage in err
        assert install.REFUSED[stage] in err

    def test_refusal_never_touches_a_subprocess(self, monkeypatch):
        recorded = RecordedRun()
        monkeypatch.setattr(install.subprocess, "run", recorded)
        install.main(["python-deps"])
        assert recorded.calls == []


class TestOsDeps:
    def test_runs_the_shipped_script_with_the_os_deps_stage(self, monkeypatch):
        monkeypatch.setattr(install.programs, "resolve_program", lambda b: f"/usr/bin/{b}")
        recorded = RecordedRun(returncode=0)
        monkeypatch.setattr(install.subprocess, "run", recorded)
        assert install.main(["os-deps"]) == 0
        ((command, _kwargs),) = recorded.calls
        assert command == ["/usr/bin/bash", str(install.SCRIPT), "os-deps"]

    def test_states_what_it_will_run_before_running_it(self, monkeypatch, capsys):
        monkeypatch.setattr(install.programs, "resolve_program", lambda b: f"/usr/bin/{b}")
        monkeypatch.setattr(install.subprocess, "run", RecordedRun())
        install.main(["os-deps"])
        out = capsys.readouterr().out
        assert "About to run" in out
        assert "os-deps" in out

    def test_refuses_on_a_host_without_apt_get(self, monkeypatch, capsys):
        monkeypatch.setattr(install.programs, "resolve_program", lambda b: None)
        recorded = RecordedRun()
        monkeypatch.setattr(install.subprocess, "run", recorded)
        assert install.main(["os-deps"]) == 1
        assert "Debian/Ubuntu" in capsys.readouterr().err
        assert recorded.calls == []

    def test_propagates_the_script_s_exit_code(self, monkeypatch):
        monkeypatch.setattr(install.programs, "resolve_program", lambda b: f"/usr/bin/{b}")
        monkeypatch.setattr(install.subprocess, "run", RecordedRun(returncode=1))
        assert install.main(["os-deps"]) == 1


class TestEnrich:
    def test_pip_installs_the_extra_at_the_running_version(self, monkeypatch, capsys):
        monkeypatch.setattr(install.importlib.metadata, "version", lambda _dist: "6.75.1")
        monkeypatch.setattr(install.sys, "executable", "/venv/bin/python")
        recorded = RecordedRun()
        monkeypatch.setattr(install.subprocess, "run", recorded)
        assert install.main(["enrich"]) == 0
        ((command, _kwargs),) = recorded.calls
        assert command == [
            "/venv/bin/python",
            "-m",
            "pip",
            "install",
            "chitragupta-cli[enrich]==6.75.1",
        ]
        assert "About to run" in capsys.readouterr().out

    def test_a_failing_pip_is_reported_not_swallowed(self, monkeypatch):
        monkeypatch.setattr(install.importlib.metadata, "version", lambda _dist: "6.75.1")
        monkeypatch.setattr(install.subprocess, "run", RecordedRun(returncode=1))
        assert install.main(["enrich"]) == 1

    def test_a_checkout_is_refused_with_the_install_script_equivalent(self, monkeypatch, capsys):
        def not_installed(_dist):
            raise install.importlib.metadata.PackageNotFoundError

        monkeypatch.setattr(install.importlib.metadata, "version", not_installed)
        assert install.main(["enrich"]) == 1
        assert "bash scripts/install_full_pipeline.sh python-deps" in capsys.readouterr().err


class TestGpuTorch:
    def test_targets_the_running_interpreters_own_venv(self, monkeypatch, tmp_path):
        fake_python = tmp_path / "some-venv" / "bin" / "python"
        monkeypatch.setattr(install.programs, "resolve_program", lambda b: "/usr/bin/bash")
        monkeypatch.setattr(install.sys, "executable", str(fake_python))
        recorded = RecordedRun()
        monkeypatch.setattr(install.subprocess, "run", recorded)
        assert install.main(["gpu-torch"]) == 0
        ((command, kwargs),) = recorded.calls
        assert command == ["/usr/bin/bash", str(install.SCRIPT), "gpu-torch"]
        assert kwargs["env"]["CHITRAGUPTA_PYTHON"] == str(fake_python)
        assert "CHITRAGUPTA_PIP" not in kwargs["env"]

    def test_stays_inside_the_venv_when_python_is_a_symlink(self, monkeypatch, tmp_path):
        base_python = tmp_path / "usr" / "bin" / "python3.13"
        base_python.parent.mkdir(parents=True)
        base_python.touch()
        venv_python = tmp_path / "some-venv" / "bin" / "python"
        venv_python.parent.mkdir(parents=True)
        venv_python.symlink_to(base_python)
        monkeypatch.setattr(install.programs, "resolve_program", lambda b: "/usr/bin/bash")
        monkeypatch.setattr(install.sys, "executable", str(venv_python))
        recorded = RecordedRun()
        monkeypatch.setattr(install.subprocess, "run", recorded)
        assert install.main(["gpu-torch"]) == 0
        ((_command, kwargs),) = recorded.calls
        assert kwargs["env"]["CHITRAGUPTA_PYTHON"] == str(venv_python)

    def test_refuses_without_bash(self, monkeypatch, capsys):
        monkeypatch.setattr(install.programs, "resolve_program", lambda b: None)
        recorded = RecordedRun()
        monkeypatch.setattr(install.subprocess, "run", recorded)
        assert install.main(["gpu-torch"]) == 1
        assert "bash" in capsys.readouterr().err
        assert recorded.calls == []


class TestMain:
    def test_an_unknown_stage_is_rejected_by_argparse(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            install.main(["not-a-real-stage"])
        assert excinfo.value.code != 0

    def test_help_exits_zero(self):
        with pytest.raises(SystemExit) as excinfo:
            install.main(["--help"])
        assert excinfo.value.code == 0

    def test_help_does_not_print_the_module_docstring(self):
        assert install.DESCRIPTION != install.__doc__
        assert "\n\n" not in install.DESCRIPTION

    def test_help_says_which_stages_actually_run(self, capsys):
        with pytest.raises(SystemExit):
            install.main(["--help"])
        out = capsys.readouterr().out
        for stage in ("os-deps", "gpu-torch", *install.REFUSED):
            assert stage in out
        assert "refuse" in out


class TestRemedy:
    def test_names_the_shipped_command(self):
        assert install.remedy("os-deps") == "`chitragupta install os-deps`"

    @pytest.mark.parametrize("stage", ["python-deps", "nonsense"])
    def test_a_stage_that_does_not_run_is_refused(self, stage):
        with pytest.raises(ValueError):
            install.remedy(stage)


class TestEnrichRemedy:
    def test_names_the_command_for_each_project_shape(self):
        text = install.enrich_remedy()
        assert "in a git checkout, `bash scripts/install_full_pipeline.sh python-deps`" in text
        assert "in an installed project, `chitragupta install enrich`" in text

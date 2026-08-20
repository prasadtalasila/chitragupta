"""`chitragupta install os-deps|gpu-torch`: reaches
scripts/install_full_pipeline.sh's two host-only stages without ever
actually invoking apt-get or reinstalling torch in this suite -- every
subprocess call is mocked, so what is pinned here is the *dispatch*
(which stage runs what, what gets refused, what environment a real
invocation would see), not the shell script's own behaviour (which has
no test of its own, per docs/TECHNICAL-DEBT.md 3.5)."""

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
        monkeypatch.setattr(install.shutil, "which", lambda b: f"/usr/bin/{b}")
        recorded = RecordedRun(returncode=0)
        monkeypatch.setattr(install.subprocess, "run", recorded)
        assert install.main(["os-deps"]) == 0
        (command, _kwargs), = recorded.calls
        assert command == ["bash", str(install.SCRIPT), "os-deps"]

    def test_states_what_it_will_run_before_running_it(self, monkeypatch, capsys):
        monkeypatch.setattr(install.shutil, "which", lambda b: f"/usr/bin/{b}")
        monkeypatch.setattr(install.subprocess, "run", RecordedRun())
        install.main(["os-deps"])
        out = capsys.readouterr().out
        assert "About to run" in out
        assert "os-deps" in out

    def test_refuses_on_a_host_without_apt_get(self, monkeypatch, capsys):
        monkeypatch.setattr(install.shutil, "which", lambda b: None)
        recorded = RecordedRun()
        monkeypatch.setattr(install.subprocess, "run", recorded)
        assert install.main(["os-deps"]) == 1
        assert "Debian/Ubuntu" in capsys.readouterr().err
        assert recorded.calls == []

    def test_propagates_the_script_s_exit_code(self, monkeypatch):
        monkeypatch.setattr(install.shutil, "which", lambda b: f"/usr/bin/{b}")
        monkeypatch.setattr(install.subprocess, "run", RecordedRun(returncode=1))
        assert install.main(["os-deps"]) == 1


class TestGpuTorch:
    def test_targets_the_running_interpreters_own_venv(self, monkeypatch):
        monkeypatch.setattr(install.shutil, "which", lambda b: "/usr/bin/bash")
        monkeypatch.setattr(install.sys, "executable", "/opt/some-venv/bin/python")
        recorded = RecordedRun()
        monkeypatch.setattr(install.subprocess, "run", recorded)
        assert install.main(["gpu-torch"]) == 0
        (command, kwargs), = recorded.calls
        assert command == ["bash", str(install.SCRIPT), "gpu-torch"]
        assert kwargs["env"]["CHITRAGUPTA_PIP"] == "/opt/some-venv/bin/pip"
        assert kwargs["env"]["CHITRAGUPTA_PYTHON"] == "/opt/some-venv/bin/python"

    def test_refuses_without_bash(self, monkeypatch, capsys):
        monkeypatch.setattr(install.shutil, "which", lambda b: None)
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

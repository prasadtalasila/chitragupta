import os
import shutil
import subprocess
import sys

import pytest

from tests.conftest import REPO_ROOT

BASH = shutil.which("bash")
SCRIPT = REPO_ROOT / "scripts" / "install_full_pipeline.sh"

pytestmark = pytest.mark.skipif(
    BASH is None or sys.platform == "win32",
    reason="runs the POSIX install script with a fake nvidia-smi on PATH",
)


def test_a_venv_with_no_pip_module_is_named_before_any_reinstall(tmp_path):
    venv = tmp_path / "nopip"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    nvidia_smi = fake_bin / "nvidia-smi"
    nvidia_smi.write_text("#!/bin/sh\necho 'CUDA Version: 12.4'\n", encoding="utf-8")
    nvidia_smi.chmod(0o755)
    uv = fake_bin / "uv"
    uv.write_text("#!/bin/sh\necho 'fake uv: not installing' >&2\nexit 1\n", encoding="utf-8")
    uv.chmod(0o755)
    python = venv / "bin" / "python"
    env = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "CHITRAGUPTA_PYTHON": str(python),
    }
    result = subprocess.run(
        [BASH, str(SCRIPT), "gpu-torch"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert f"{python} has no pip module" in result.stderr
    assert "ensurepip" in result.stderr
    assert "Reinstalling" not in result.stdout
    assert "fake uv" not in result.stderr

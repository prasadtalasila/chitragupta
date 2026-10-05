"""`install_full_pipeline.sh gpu-torch` run for real, up to the point
where it would reinstall torch, against a venv with no pip module.

`chitragupta install gpu-torch` points the stage at `sys.executable`,
and the stage runs pip as `<python> -m pip` (#985). A venv made by
`uv venv` without `--seed`, or by `python -m venv --without-pip`, has no
pip module for that to run, and the stage used to fail there on "No
module named pip" without saying why. A fake `nvidia-smi` reporting a
CUDA ceiling is enough to reach that point: the venv has no torch, so
torch cannot see the GPU and the stage goes on to pick a wheel tag.
"""

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
    # Never the real one. Past the check, the stage's restore fallback runs
    # `poetry install --with enrich` from this checkout, and on a host
    # whose poetry has `virtualenvs.create = false` that writes the whole
    # enrich group into the user's site-packages -- which is what running
    # this test against the unfixed script did once.
    poetry = fake_bin / "poetry"
    poetry.write_text(
        "#!/bin/sh\necho 'fake poetry: not installing' >&2\nexit 1\n", encoding="utf-8"
    )
    poetry.chmod(0o755)
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
    assert "fake poetry" not in result.stderr

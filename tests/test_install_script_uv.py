"""`install_full_pipeline.sh` sets up a checkout by itself: it copies the
example config when there is none, and installs the pinned uv into the
venv it builds, so a developer runs one script after cloning rather than
three commands (`cp config.toml.example ...`, `pipx install uv`, the
script). The functions run for real, in bash, against fakes.
"""

import re
import shutil
import subprocess
import sys

import pytest

from tests.conftest import REPO_ROOT

BASH = shutil.which("bash")
SCRIPT = (REPO_ROOT / "scripts" / "install_full_pipeline.sh").read_text(encoding="utf-8")
REQUIREMENTS = REPO_ROOT / "scripts" / "uv-requirements.txt"

pytestmark = pytest.mark.skipif(
    BASH is None or sys.platform == "win32",
    reason="runs the POSIX install script's functions in bash",
)


def _function(name: str) -> str:
    return re.search(rf"{name}\(\) \{{.*?\n\}}\n", SCRIPT, re.S).group(0)


def _stage(name: str) -> str:
    start = SCRIPT.index(f"{name}() {{")
    return SCRIPT[start : SCRIPT.index("\n}\n", start)]


def _bash(snippet: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH, "-c", snippet], env=env, capture_output=True, text=True, check=False
    )


class TestTheConfigIsCopied:
    def _run(self, root):
        return _bash(
            _function("copy_config_if_absent") + "copy_config_if_absent",
            {"REPO_ROOT": str(root), "PATH": "/usr/bin:/bin"},
        )

    def test_a_missing_config_is_copied_from_the_example(self, tmp_path):
        (tmp_path / "config.toml.example").write_text("example\n", encoding="utf-8")
        assert self._run(tmp_path).returncode == 0
        assert (tmp_path / "config.toml").read_text(encoding="utf-8") == "example\n"

    def test_an_existing_config_is_left_alone(self, tmp_path):
        (tmp_path / "config.toml.example").write_text("example\n", encoding="utf-8")
        (tmp_path / "config.toml").write_text("mine\n", encoding="utf-8")
        assert self._run(tmp_path).returncode == 0
        assert (tmp_path / "config.toml").read_text(encoding="utf-8") == "mine\n"

    def test_without_an_example_nothing_is_written(self, tmp_path):
        """docker/Dockerfile copies pyproject.toml and the lock, not the
        example config, so there is nothing to copy there."""
        assert self._run(tmp_path).returncode == 0
        assert not (tmp_path / "config.toml").exists()

    @pytest.mark.parametrize("stage", ["install_python_deps", "install_dev_deps"])
    def test_both_python_stages_copy_it(self, stage):
        assert "copy_config_if_absent" in _stage(stage)


class TestUvIsInstalledIntoTheVenv:
    def _venv(self, tmp_path, pip_exit=0):
        """A fake venv whose python records the pip call and, like pip,
        puts a `uv` beside itself."""
        bin_dir = tmp_path / "venv" / "bin"
        bin_dir.mkdir(parents=True)
        python = bin_dir / "python"
        python.write_text(
            "#!/bin/sh\n"
            f'echo "$@" > "{tmp_path}/pip-args"\n'
            f'printf "#!/bin/sh\\necho uv-in-venv\\n" > "{bin_dir}/uv"; chmod +x "{bin_dir}/uv"\n'
            f"exit {pip_exit}\n",
            encoding="utf-8",
        )
        python.chmod(0o755)
        return python

    def _run(self, python):
        snippet = _function("ensure_venv_uv") + f'ensure_venv_uv "{python}"'
        return _bash(snippet, {"REPO_ROOT": str(REPO_ROOT), "PATH": "/usr/bin:/bin"})

    def test_it_pip_installs_the_pinned_uv_with_hashes_and_names_it(self, tmp_path):
        python = self._venv(tmp_path)
        result = self._run(python)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == str(python.parent / "uv")
        args = (tmp_path / "pip-args").read_text(encoding="utf-8")
        assert "-m pip install" in args
        assert "--require-hashes" in args
        assert "--only-binary :all:" in args
        assert str(REQUIREMENTS) in args

    def test_a_failed_install_fails_the_stage_and_says_why(self, tmp_path):
        result = self._run(self._venv(tmp_path, pip_exit=1))
        assert result.returncode != 0
        assert "uv-requirements.txt" in result.stderr

    @pytest.mark.parametrize("stage", ["install_python_deps", "install_dev_deps"])
    def test_both_python_stages_sync_with_the_venvs_own_uv(self, stage):
        body = _stage(stage)
        assert "ensure_venv_uv" in body
        assert "check_uv" not in body


class TestThePinnedUv:
    def test_one_requirement_with_a_hash_per_wheel(self):
        text = REQUIREMENTS.read_text(encoding="utf-8")
        assert re.findall(r"^uv==[\d.]+", text, re.M) == [
            re.search(r"^uv==[\d.]+", text, re.M).group(0)
        ]
        assert len(re.findall(r"--hash=sha256:[0-9a-f]{64}", text)) >= 10

    def test_the_workflows_pin_the_same_version(self):
        """CI, the docs build and the release install uv with pip on their
        own; a version bumped in one place and not the others would lock
        with one uv and build with another."""
        version = re.search(r"^uv==([\d.]+)", REQUIREMENTS.read_text(encoding="utf-8"), re.M).group(
            1
        )
        for workflow in ("ci.yml", "docs.yml", "release.yml"):
            text = (REPO_ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
            pins = re.findall(r"uv==([\d.]+)", text)
            assert pins and set(pins) == {version}, (workflow, pins)

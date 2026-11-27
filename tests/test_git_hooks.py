import os
import platform
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "git-hooks" / "pre-commit"

BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="no bash on PATH; git could not run the hook")

BAD_WORKFLOW = """name: w
on: push
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - run: echo "${{ github.event.head_commit.message }}"
"""

GOOD_WORKFLOW = """name: w
on: push
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - run: echo hello
"""


def fake_actionlint(bin_dir: Path, exit_code: int) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "actionlint"
    stub.write_text(f'#!/bin/sh\necho "actionlint ran: $*"\nexit {exit_code}\n', encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)


def fake_python(bin_dir: Path, exit_code: int, output: str = "") -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    output = output or "stale      figures/a.tex\nfigure sync: 1 stale"
    script = bin_dir / "fake-python"
    script.write_text(
        f'#!/usr/bin/env bash\necho "$@" > "{bin_dir.as_posix()}/python-args"\n'
        f"printf '%s\\n' '{output}'\nexit {exit_code}\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


class HookRepo:
    def __init__(self, root: Path):
        self.root = root
        subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "a@b"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "c"], cwd=root, check=True)
        hooks = root / "git-hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HOOK, hooks / "pre-commit")
        (hooks / "pre-commit").chmod(0o755)
        self.hook = hooks / "pre-commit"
        self.bin = root / "fakebin"

    def stage(self, relpath: str, body: str) -> None:
        path = self.root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        subprocess.run(["git", "add", relpath], cwd=self.root, check=True)

    def run(self, with_actionlint: "int | None" = 0, python: "Path | None" = None):
        env = dict(os.environ)
        env.pop("CHITRAGUPTA_PYTHON", None)
        if python is not None:
            env["CHITRAGUPTA_PYTHON"] = python.as_posix()
        if with_actionlint is None:
            if shutil.which("actionlint"):
                pytest.skip("actionlint is installed here; cannot test its absence")
        else:
            fake_actionlint(self.bin, with_actionlint)
            env["PATH"] = f"{self.bin}{os.pathsep}{env['PATH']}"
        return subprocess.run(
            [BASH, str(self.hook)],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )


@pytest.fixture
def repo(tmp_path):
    return HookRepo(tmp_path)


class TestItIsAShippedExecutable:
    def test_the_hook_exists_and_is_executable(self):
        assert HOOK.is_file()
        assert os.access(HOOK, os.X_OK), "git will not run a hook without the execute bit"


class TestWhenItRuns:
    def test_a_staged_workflow_is_checked(self, repo):
        repo.stage(".github/workflows/w.yml", GOOD_WORKFLOW)
        result = repo.run(with_actionlint=0)
        assert result.returncode == 0
        assert "actionlint ran" in result.stdout + result.stderr

    def test_a_failing_workflow_blocks_the_commit(self, repo):
        repo.stage(".github/workflows/w.yml", BAD_WORKFLOW)
        assert repo.run(with_actionlint=1).returncode != 0

    def test_the_block_says_how_to_bypass_it(self, repo):
        repo.stage(".github/workflows/w.yml", BAD_WORKFLOW)
        assert "--no-verify" in repo.run(with_actionlint=1).stderr

    def test_a_yaml_extension_is_checked_too(self, repo):
        repo.stage(".github/workflows/w.yaml", GOOD_WORKFLOW)
        result = repo.run(with_actionlint=0)
        assert "actionlint ran" in result.stdout + result.stderr


class TestWhenItStaysOutOfTheWay:
    def test_no_staged_workflow_means_silence(self, repo):
        repo.stage("README.md", "# hello\n")
        result = repo.run(with_actionlint=0)
        assert (result.returncode, result.stdout, result.stderr) == (0, "", "")

    def test_a_workflow_outside_dot_github_is_not_one(self, repo):
        repo.stage("compose.yml", "services: {}\n")
        assert repo.run(with_actionlint=0).stdout == ""

    def test_a_deleted_workflow_does_not_trigger_it(self, repo):
        repo.stage(".github/workflows/w.yml", GOOD_WORKFLOW)
        subprocess.run(["git", "commit", "-qm", "add", "--no-verify"], cwd=repo.root, check=True)
        subprocess.run(["git", "rm", "-q", ".github/workflows/w.yml"], cwd=repo.root, check=True)
        result = repo.run(with_actionlint=0)
        assert (result.returncode, result.stdout) == (0, "")

    def test_a_missing_actionlint_is_silence_not_a_refusal(self, repo):
        repo.stage(".github/workflows/w.yml", BAD_WORKFLOW)
        result = repo.run(with_actionlint=None)
        assert result.returncode == 0

    def test_a_missing_actionlint_says_so_once(self, repo):
        repo.stage(".github/workflows/w.yml", BAD_WORKFLOW)
        assert "actionlint" in repo.run(with_actionlint=None).stderr


class TestTheFigureCheck:
    def test_a_staged_figure_is_checked(self, repo, tmp_path):
        repo.stage("content/drafts/t/figures/a.tex", "x")
        result = repo.run(python=fake_python(tmp_path / "pybin", 0))
        args = (tmp_path / "pybin" / "python-args").read_text(encoding="utf-8")
        assert "figure sync --check content/drafts/t/figures/a.tex" in args
        assert result.returncode == 0

    def test_a_book_units_figure_is_checked(self, repo, tmp_path):
        repo.stage("content/drafts/book/unit/figures/a.tex", "x")
        repo.run(python=fake_python(tmp_path / "pybin", 0))
        args = (tmp_path / "pybin" / "python-args").read_text(encoding="utf-8")
        assert "content/drafts/book/unit/figures/a.tex" in args

    def test_a_staged_scaffold_is_checked(self, repo, tmp_path):
        repo.stage("assets/tikz/pipeline.tex", "x")
        repo.run(python=fake_python(tmp_path / "pybin", 0))
        args = (tmp_path / "pybin" / "python-args").read_text(encoding="utf-8")
        assert "assets/tikz/pipeline.tex" in args

    def test_a_stale_figure_is_reported_and_does_not_block(self, repo, tmp_path):
        repo.stage("content/drafts/t/figures/a.tex", "x")
        result = repo.run(python=fake_python(tmp_path / "pybin", 1))
        assert result.returncode == 0
        assert "figure sync" in result.stderr and "stale" in result.stderr

    def test_an_interpreter_that_cannot_run_it_is_one_line(self, repo, tmp_path):
        repo.stage("content/drafts/t/figures/a.tex", "x")
        result = repo.run(python=fake_python(tmp_path / "pybin", 2))
        assert result.returncode == 0 and "not checked" in result.stderr

    def test_a_crash_is_not_reported_as_a_stale_block(self, repo, tmp_path):
        repo.stage("content/drafts/t/figures/a.tex", "x")
        crash = "Traceback (most recent call last):\nModuleNotFoundError: No module named x"
        result = repo.run(python=fake_python(tmp_path / "pybin", 1, crash))
        assert result.returncode == 0 and "not checked" in result.stderr
        assert "not current" not in result.stderr

    def test_an_unrelated_tex_file_is_not_a_figure(self, repo, tmp_path):
        repo.stage("content/drafts/t/chapter.tex", "x")
        repo.run(python=fake_python(tmp_path / "pybin", 0))
        assert not (tmp_path / "pybin" / "python-args").exists()

    def test_the_workflow_lint_still_runs_after_it(self, repo, tmp_path):
        repo.stage("content/drafts/t/figures/a.tex", "x")
        repo.stage(".github/workflows/ci.yml", BAD_WORKFLOW)
        result = repo.run(with_actionlint=1, python=fake_python(tmp_path / "pybin", 1))
        assert result.returncode == 1  # actionlint's block, not the figure's
        assert "actionlint ran" in result.stdout + result.stderr


class TestSequencerCommits:
    @pytest.mark.parametrize(
        "marker", ["MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "REBASE_HEAD"]
    )
    def test_a_sequencer_marker_file_skips_the_hook(self, repo, marker):
        repo.stage(".github/workflows/w.yml", BAD_WORKFLOW)
        (repo.root / ".git" / marker).write_text("deadbeef\n", encoding="utf-8")
        result = repo.run(with_actionlint=1)
        assert (result.returncode, result.stdout) == (0, "")

    @pytest.mark.parametrize("marker", ["rebase-merge", "rebase-apply"])
    def test_a_sequencer_marker_directory_skips_the_hook(self, repo, marker):
        repo.stage(".github/workflows/w.yml", BAD_WORKFLOW)
        (repo.root / ".git" / marker).mkdir()
        assert repo.run(with_actionlint=1).returncode == 0


class TestTheInstallStageWiresItUp:
    def _script(self):
        return (REPO_ROOT / "scripts" / "install_full_pipeline.sh").read_text(encoding="utf-8")

    def test_dev_deps_installs_actionlint(self):
        assert "install_actionlint" in self._script()

    def test_the_version_and_digest_are_pinned(self):
        script = self._script()
        assert "ACTIONLINT_VERSION=" in script
        assert "ACTIONLINT_SHA256=" in script

    def test_the_digest_is_checked_before_the_archive_is_unpacked(self):
        script = self._script()
        check = script.index("ACTIONLINT_SHA256}")
        unpack = script.index('actionlint.tar.gz" -C')
        assert check < unpack

    def test_dev_deps_points_git_at_the_hook_directory(self):
        assert "core.hooksPath" in self._script()

    def test_there_is_a_standalone_actionlint_stage_for_ci(self):
        assert "actionlint) install_actionlint" in self._script()


class TestTheInstallStageNeverFailsTheBuild:
    def _run_stage(self, tmp_path, uname_output):
        fake = tmp_path / "bin"
        fake.mkdir(parents=True, exist_ok=True)
        stub = fake / "uname"
        stub.write_text(
            f'#!/bin/sh\ncase "$1" in -s) echo {uname_output} ;; *) echo x86_64 ;; esac\n',
            encoding="utf-8",
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ)
        env["PATH"] = f"{fake}{os.pathsep}{env['PATH']}"
        return subprocess.run(
            ["bash", str(REPO_ROOT / "scripts" / "install_full_pipeline.sh"), "actionlint"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    @pytest.mark.skipif(
        shutil.which("actionlint") is not None,
        reason="actionlint is installed here, so the stage short-circuits before the guard",
    )
    @pytest.mark.skipif(
        platform.system() != "Linux",
        reason="the stub cannot shadow uname under Git Bash; the unstubbed case below covers it",
    )
    @pytest.mark.parametrize("system", ["MINGW64_NT-10.0", "Darwin"])
    def test_a_host_with_no_pinned_build_is_a_note_not_a_failure(self, tmp_path, system):
        result = self._run_stage(tmp_path, system)
        assert result.returncode == 0, result.stderr
        assert "skipping" in result.stderr.lower()

    @pytest.mark.skipif(
        platform.system() == "Linux", reason="Linux has a pinned build; nothing to skip over"
    )
    def test_a_real_non_linux_host_gets_the_note_and_exit_zero(self):
        result = subprocess.run(
            [BASH, str(REPO_ROOT / "scripts" / "install_full_pipeline.sh"), "actionlint"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    def test_the_guard_returns_before_any_download(self):
        script = (REPO_ROOT / "scripts" / "install_full_pipeline.sh").read_text(encoding="utf-8")
        body = script[script.index("install_actionlint() {") :]
        body = body[: body.index("\ninstall_git_hooks")]
        assert body.index("uname -s") < body.index("curl")


class TestCiRunsItToo:
    def test_the_lint_job_runs_actionlint(self):
        ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        assert "actionlint" in ci

    def test_shellcheck_covers_the_hook(self):
        ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        assert "git-hooks/pre-commit" in ci

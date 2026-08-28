"""`git-hooks/pre-commit`: actionlint at the commit, not at the next CI run.

**A different mechanism from `docs/HOOKS.md`'s three.** Those are Claude
Code harness hooks: they fire on an agent's `Write`/`Edit` and can only
see what the agent wrote. This one is git's own `pre-commit`, so it sees
every path into a commit -- a human in an editor, another agent, `git
apply`, `sed`. That is the gap it exists to close, and it is why the two
mechanisms coexist rather than one replacing the other.

**It blocks, and that is not a contradiction of HOOKS.md's "exactly one
gate".** That rule is about the review layer, where a finding is a
judgement. A workflow file either parses and type-checks or it does not,
`ci.yml`'s lint job already fails on it, and blocking here only moves the
same binary verdict earlier. What the hook must never do is block when it
*cannot* tell -- an absent binary is silence, not a refusal.

Run as a subprocess throughout, because that is how git runs it, and a
hook tested only as a function is one whose exit codes were never checked.
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "git-hooks" / "pre-commit"

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
    """A stand-in on PATH, so the hook's own logic is what is measured.

    The real binary is not a test dependency: it is installed by
    `install_full_pipeline.sh dev-deps` on a developer's machine and by
    CI's lint job, and a suite that needed it would fail on every host
    that had not run either.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "actionlint"
    stub.write_text(f'#!/bin/sh\necho "actionlint ran: $*"\nexit {exit_code}\n', encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)


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

    def run(self, with_actionlint: "int | None" = 0):
        env = dict(os.environ)
        if with_actionlint is None:
            # PATH is left alone rather than emptied. Emptying it removed
            # `bash` too, so the hook exited 127 on its own shebang and
            # the test proved nothing about a missing linter. The guard
            # below is what keeps this case honest instead.
            if shutil.which("actionlint"):
                pytest.skip("actionlint is installed here; cannot test its absence")
        else:
            fake_actionlint(self.bin, with_actionlint)
            env["PATH"] = f"{self.bin}{os.pathsep}{env['PATH']}"
        # Executed directly, not via `sh`: git runs the hook file itself
        # and its `#!/usr/bin/env bash` shebang decides the interpreter.
        # Forcing `sh` here ran it under dash and failed on the process
        # substitution, which told us nothing about the hook.
        return subprocess.run(
            [str(self.hook)],
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
        """A gate with no stated escape is one people disable wholesale."""
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
        """`actionlint` reads `.github/workflows/` and nothing else, so a
        `docker-compose.yml` staged at the root is not its business."""
        repo.stage("compose.yml", "services: {}\n")
        assert repo.run(with_actionlint=0).stdout == ""

    def test_a_deleted_workflow_does_not_trigger_it(self, repo):
        """`--diff-filter=ACMR` excludes a deletion: there is nothing left
        to lint, and running on the remaining files would report findings
        the commit did not cause."""
        repo.stage(".github/workflows/w.yml", GOOD_WORKFLOW)
        subprocess.run(["git", "commit", "-qm", "add", "--no-verify"], cwd=repo.root, check=True)
        subprocess.run(["git", "rm", "-q", ".github/workflows/w.yml"], cwd=repo.root, check=True)
        result = repo.run(with_actionlint=0)
        assert (result.returncode, result.stdout) == (0, "")

    def test_a_missing_actionlint_is_silence_not_a_refusal(self, repo):
        """The install stage is opt-in (`dev-deps`), so an absent binary is
        the ordinary state of a checkout that has not run it. Blocking a
        commit because a linter is missing would be the hook failing in
        the direction that costs the most and teaches the least."""
        repo.stage(".github/workflows/w.yml", BAD_WORKFLOW)
        result = repo.run(with_actionlint=None)
        assert result.returncode == 0

    def test_a_missing_actionlint_says_so_once(self, repo):
        """Silent about findings, not about its own absence -- otherwise a
        developer believes the check ran. The same distinction
        `session_start_hook.py` draws between a fault and a stage."""
        repo.stage(".github/workflows/w.yml", BAD_WORKFLOW)
        assert "actionlint" in repo.run(with_actionlint=None).stderr


class TestSequencerCommits:
    """git runs `pre-commit` for a merge, a cherry-pick and a rebase
    continuation too, where what is staged is the *operation's result*
    rather than anything the developer typed. Linting there reports
    findings that belong to whichever commit is being replayed, on a tree
    the developer may not even have chosen yet."""

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
    """`dev-deps` is what installs the binary and points git at the hook
    directory. A hook nobody's git config knows about is inert, which is
    the failure `docs/HOOKS.md` was written for."""

    def _script(self):
        return (REPO_ROOT / "scripts" / "install_full_pipeline.sh").read_text(encoding="utf-8")

    def test_dev_deps_installs_actionlint(self):
        assert "install_actionlint" in self._script()

    def test_the_version_and_digest_are_pinned(self):
        script = self._script()
        assert "ACTIONLINT_VERSION=" in script
        assert "ACTIONLINT_SHA256=" in script

    def test_the_digest_is_checked_before_the_archive_is_unpacked(self):
        """The Vale precedent, and the reason it is stated there: this is
        a file taken from outside the distribution's archives."""
        script = self._script()
        check = script.index("ACTIONLINT_SHA256}")
        unpack = script.index('actionlint.tar.gz" -C')
        assert check < unpack

    def test_dev_deps_points_git_at_the_hook_directory(self):
        assert "core.hooksPath" in self._script()

    def test_there_is_a_standalone_actionlint_stage_for_ci(self):
        """CI's lint job wants the linter and nothing else, the same
        reason `vale` is a stage of its own."""
        assert "actionlint) install_actionlint" in self._script()


class TestTheInstallStageNeverFailsTheBuild:
    """The regression the first CI run on this branch found.

    `dev-deps` is what the Windows test leg runs to get pytest. The first
    version of `install_actionlint` called `sudo_if_needed install ...
    /usr/local/bin`, which exits 1 where it cannot elevate -- Git Bash has
    no sudo -- so the whole step died and pytest never ran. A workflow
    linter that cannot install is a reason to skip the commit hook, never
    a reason to fail the install of everything else.
    """

    def _run_stage(self, tmp_path, uname_output):
        """The `actionlint` stage with a stubbed `uname` ahead of PATH."""
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
    @pytest.mark.parametrize("system", ["MINGW64_NT-10.0", "Darwin"])
    def test_a_host_with_no_pinned_build_is_a_note_not_a_failure(self, tmp_path, system):
        result = self._run_stage(tmp_path, system)
        assert result.returncode == 0, result.stderr
        assert "skipping" in result.stderr.lower()

    def test_the_guard_returns_before_any_download(self):
        """The non-Linux path must not reach curl -- an install step that
        fetches 5.8 MB to then discard it is a slow way to do nothing."""
        script = (REPO_ROOT / "scripts" / "install_full_pipeline.sh").read_text(encoding="utf-8")
        body = script[script.index("install_actionlint() {") :]
        body = body[: body.index("\ninstall_git_hooks")]
        assert body.index("uname -s") < body.index("curl")


class TestCiRunsItToo:
    def test_the_lint_job_runs_actionlint(self):
        ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        assert "actionlint" in ci

    def test_shellcheck_covers_the_hook(self):
        """The hook is shell this repository ships and CI depends on, so it
        holds the same bar `scripts/*.sh` does -- and it is not under
        `scripts/`, so the existing glob does not reach it."""
        ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        assert "git-hooks/pre-commit" in ci

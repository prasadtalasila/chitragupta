"""`scripts/check_version_bump.py`: the check that makes a lost version bump
loud (#212).

The failure it guards is not a conflict -- conflicts are loud and get
fixed. It is the opposite: two branches picking the **same** number, which
git merges without a word, leaving `main` claiming a version that has
already been spent. That reached `main` once (#209 on top of #205) and
needed a follow-up PR to correct.

The race in `test_a_merged_but_untagged_version_is_still_caught` is why the
primary rule compares against `main` rather than against the tags. A
tag-existence test is the obvious check and is blind for the whole window
between a merge and its tag -- 34 seconds in the fastest observed case,
and open-ended when a person pushes the tag by hand.
"""

import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def check():
    spec = importlib.util.spec_from_file_location(
        "check_version_bump", REPO_ROOT / "scripts" / "check_version_bump.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestOrdering:
    """Numeric, not lexical. `5.9.0` sorts above `5.10.0` as a string, and
    that is exactly the comparison this has to get right."""

    @pytest.mark.parametrize("lower,higher", [
        ("5.9.0", "5.10.0"),
        ("5.19.0", "5.20.0"),
        ("5.9.9", "5.10.0"),
        ("4.99.0", "5.0.0"),
        ("5.19.0", "5.19.1"),
    ])
    def test_a_higher_version_sorts_higher(self, check, lower, higher):
        assert check.parse(lower) < check.parse(higher)

    def test_a_string_comparison_would_have_got_this_wrong(self, check):
        assert "5.9.0" > "5.10.0"          # the trap
        assert check.parse("5.9.0") < check.parse("5.10.0")

    def test_a_non_numeric_component_sorts_after_the_numbers(self, check):
        """Not used today; pinned so a pre-release suffix cannot silently
        compare as though it were a number."""
        assert check.parse("5.20.0") < check.parse("5.20.rc1")


class TestTheRules:
    TAGS = ("v5.18.0", "v5.19.0")

    def test_a_real_bump_passes(self, check):
        assert check.problems("5.20.0", "5.19.0", self.TAGS) == []

    def test_a_version_equal_to_main_is_the_silent_collision(self, check):
        """The case that reached main: #205 and #209 both took 5.18.0, git
        merged the identical line, and the bump vanished."""
        found = check.problems("5.19.0", "5.19.0", self.TAGS)
        assert found
        assert "another pr took that number" in found[0].lower()

    def test_a_version_below_main_is_caught(self, check):
        assert check.problems("5.18.0", "5.19.0", self.TAGS)

    def test_a_merged_but_untagged_version_is_still_caught(self, check):
        """**The race the tag check cannot see.** A PR merges 5.20.0 to
        main; its tag is not pushed yet. A second branch also on 5.20.0
        runs CI in that window: no `v5.20.0` exists, so a tag test passes
        and the collision merges anyway. Comparing against main needs no
        tag to exist."""
        found = check.problems("5.20.0", "5.20.0", self.TAGS)
        assert found, "a tag-existence check alone would have passed this"
        assert "main is already at 5.20.0" in found[0]

    def test_an_already_released_version_is_caught_by_the_tag_rule(self, check):
        """The second line, for the odd state where a tag runs ahead of
        main. Not sufficient alone, which is the whole point of the test
        above."""
        found = check.problems("5.19.0", "5.18.0", self.TAGS)
        assert any("already released as v5.19.0" in p for p in found)

    def test_both_rules_can_fire_at_once(self, check):
        assert len(check.problems("5.18.0", "5.19.0", self.TAGS)) == 2

    def test_no_tags_at_all_is_not_a_failure(self, check):
        """A fresh clone, or a fetch without `--tags`."""
        assert check.problems("5.20.0", "5.19.0", []) == []


class TestParsingPyproject:
    def test_it_reads_the_poetry_version(self, check):
        assert check.version_in('[tool.poetry]\nversion = "5.20.0"\n') == "5.20.0"


def git_repo(root: Path, base_version: str, head_version: str, tag: str | None):
    """A throwaway repository with a real commit to compare against.

    The command is exercised against real `git`, not a mock -- but against
    a repository this function built, never this checkout. An earlier
    version of these tests ran `main()` against the real repo and passed
    locally while failing in CI twice over: the `test` jobs check out
    shallow and have no `origin/main` at all, and on a `pull_request` event
    `HEAD` is the *merge* commit, so it already contains the branch's own
    bump. A test whose result depends on which refs a CI job happens to
    fetch is testing the CI job.
    """
    def run(*args):
        subprocess.run(["git", *args], cwd=root, check=True,
                       capture_output=True, text=True)

    run("init", "--quiet", "-b", "main")
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "t")
    pyproject = root / "pyproject.toml"
    pyproject.write_text(f'[tool.poetry]\nversion = "{base_version}"\n',
                         encoding="utf-8")
    run("add", "pyproject.toml")
    run("commit", "--quiet", "-m", "base")
    if tag:
        run("tag", tag)
    pyproject.write_text(f'[tool.poetry]\nversion = "{head_version}"\n',
                         encoding="utf-8")
    return root


class TestTheCommand:
    """`main()` against real git, in a repository the test built."""

    @pytest.fixture
    def in_repo(self, check, tmp_path, monkeypatch):
        def build(base, head, tag=None):
            git_repo(tmp_path, base, head, tag)
            monkeypatch.setattr(check, "REPO_ROOT", tmp_path)
            return tmp_path
        return build

    def test_a_real_bump_passes(self, check, in_repo, capsys):
        in_repo("5.19.0", "5.20.0")
        assert check.main(["--base-ref", "main"]) == 0
        assert "out-ranks" in capsys.readouterr().out

    def test_a_collision_exits_one_and_says_why(self, check, in_repo, capsys):
        in_repo("5.19.0", "5.19.0")
        assert check.main(["--base-ref", "main"]) == 1
        assert "::error::" in capsys.readouterr().err

    def test_a_released_version_is_caught_through_real_tags(self, check, in_repo,
                                                            capsys):
        in_repo("5.19.0", "5.20.0", tag="v5.20.0")
        assert check.main(["--base-ref", "main"]) == 1
        assert "already released" in capsys.readouterr().err

    def test_the_base_ref_travels_into_the_message(self, check, in_repo, capsys):
        """A passing run says what it actually compared, so a wrong ref is
        visible rather than silently reassuring."""
        in_repo("5.19.0", "5.20.0")
        assert check.main(["--base-ref", "main"]) == 0
        assert "main's" in capsys.readouterr().out


class TestItFailsReadably:
    def test_a_missing_base_ref_says_what_to_fetch(self, check, capsys):
        """Found by an OpenCodeReview pass, under its unchecked-failure
        rule: a shallow clone that never fetched the base ref would have
        surfaced as a CalledProcessError traceback, which in CI is the
        whole of what a reader sees."""
        assert check.main(["--base-ref", "refs/heads/no-such-branch"]) == 1
        assert "cannot read" in capsys.readouterr().err

    def test_git_output_is_decoded_as_utf8(self, check):
        """`text=True` alone decodes with the host locale, which is cp1252
        on CI's Windows leg -- and this reads a file out of git, not just
        tag names."""
        import inspect
        source = inspect.getsource(check._git)
        assert 'encoding="utf-8"' in source


class TestCIWiring:
    """The CI step must run on `pull_request` only.

    `ci.yml`'s `lint` job also runs `on: push: branches: [main]` (kept for
    Codecov's base-report reasons). On that event the checked-out commit
    *is* main, so the fetch step makes `origin/main` resolve to that same
    commit -- current-against-itself, always `<=`, an unconditional
    failure. Confirmed on the pushes that landed #213 and #214: both red
    at this exact step. A text scan, not a workflow run, because that's
    what would have caught it before either of those pushes -- the same
    idiom as test_codecov_upload_gate.py.
    """

    def test_the_version_bump_step_is_scoped_to_pull_request(self):
        ci_yml = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        # Steps in this job are each introduced by a `      - name:` line at
        # a fixed indent, so splitting on that marker isolates one step's
        # text without needing to reason about blank lines or comments
        # inside it -- a lookahead regex over the whole file got this
        # wrong (it skipped past blank lines into the *next* step).
        steps = re.split(r"\n(?=      - name:)", ci_yml)
        matches = [s for s in steps
                   if s.startswith("      - name: Version bump has not been lost to a collision")]
        assert matches, "ci.yml no longer has the version-bump step under this name"
        assert "if: github.event_name == 'pull_request'" in matches[0], (
            "the version-bump step lost its pull_request guard -- it will fail "
            "unconditionally on every push to main"
        )


class TestUnreleased:
    """A version on main that was never tagged.

    Not a `problems()` entry, and that distinction is the whole design:
    the state is legitimate immediately after every merge, because the
    bump lands in the PR and the tag is pushed afterwards. Failing on it
    would fail every merge. It is surfaced as a warning instead, so the
    same version quoted back across several PRs becomes noticeable.
    """

    def test_a_tagged_base_is_silent(self, check):
        assert check.unreleased("6.2.0", ["v6.1.0", "v6.2.0"]) is None

    def test_an_untagged_base_is_reported(self, check):
        found = check.unreleased("6.2.0", ["v6.1.0"])
        assert found is not None and "6.2.0" in found

    def test_it_names_the_command_that_fixes_it(self, check):
        """A warning nobody can act on is noise. This one carries the
        literal tag-and-push, the way config.py's missing-file error
        carries `cp config.toml.example config.toml`."""
        found = check.unreleased("6.2.0", ["v6.1.0"])
        assert "git tag -a v6.2.0" in found
        assert "git push origin v6.2.0" in found

    def test_no_tags_at_all_is_reported_rather_than_crashing(self, check):
        assert check.unreleased("0.1.0", []) is not None

    def test_a_prefix_match_is_not_a_tag(self, check):
        """`v6.2.0` is not released just because `v6.2.0-rc1` exists."""
        assert check.unreleased("6.2.0", ["v6.2.0-rc1"]) is not None


class TestTheWarningDoesNotGate:
    """The exit code belongs to problems(); this must never touch it."""

    def test_an_untagged_base_alone_still_exits_zero(self, check, monkeypatch, capsys):
        monkeypatch.setattr(check, "problems", lambda *a: [])
        monkeypatch.setattr(check, "unreleased", lambda *a: "a release is owed")
        monkeypatch.setattr(check, "_git", lambda *a: '[tool.poetry]\nversion = "0.0.1"\n')
        assert check.main([]) == 0
        assert "::warning::a release is owed" in capsys.readouterr().err

    def test_a_real_problem_still_exits_one(self, check, monkeypatch, capsys):
        monkeypatch.setattr(check, "problems", lambda *a: ["collision"])
        monkeypatch.setattr(check, "unreleased", lambda *a: "a release is owed")
        monkeypatch.setattr(check, "_git", lambda *a: '[tool.poetry]\nversion = "0.0.1"\n')
        assert check.main([]) == 1
        err = capsys.readouterr().err
        assert "::warning::" in err and "::error::collision" in err

    def test_a_tagged_base_emits_no_warning_at_all(self, check, monkeypatch, capsys):
        """The quiet path: nothing is owed, so nothing is said. Pinned
        because a warning that fires unconditionally is one nobody
        reads, which would defeat the point of adding it."""
        monkeypatch.setattr(check, "problems", lambda *a: [])
        monkeypatch.setattr(check, "unreleased", lambda *a: None)
        monkeypatch.setattr(check, "_git",
                            lambda *a: '[tool.poetry]\nversion = "0.0.1"\n')
        assert check.main([]) == 0
        assert "::warning::" not in capsys.readouterr().err

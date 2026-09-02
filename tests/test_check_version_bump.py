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


def not_on_pypi(_url):
    """What `_fetch_json` returns for a 404: `on_pypi`'s "not published".

    Every `main()` call below that is not itself about the PyPI rule
    passes this. It is a *definite* answer, so the run is silent and
    identical on every host -- where the real fetcher's answer depends
    both on the network being up and on whether this branch's own
    version has been released yet. `--offline` would also be quiet, but
    it skips the rule rather than exercising it.
    """
    return False


@pytest.fixture(scope="module")
def check():
    spec = importlib.util.spec_from_file_location(
        "check_version_bump", REPO_ROOT / "scripts" / "check_version_bump.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _no_real_network(check, monkeypatch):
    """Fail any test in this module that actually reaches pypi.org (#425).

    Three tests here drove `main()` with neither `--offline` nor a fake
    fetcher and so requested a real URL on every full-suite run, which
    failed once: `on_pypi` returns None on a transport hiccup, `main()`
    reports a None as a `::warning::`, and
    `test_a_tagged_base_emits_no_warning_at_all` asserts that warning is
    absent. Intermittent, and it reads as "your branch broke something."

    Four more in `TestTheCommand` reached the network too and passed
    anyway -- they assert on stdout, and the stray warning goes to
    stderr. That is why this is a fixture rather than seven fixes: the
    coupling is one call deep, invisible at the call site, and silent in
    four of the seven places it existed.

    **The trip is reported at teardown, not where it happens.** Raising
    here would be swallowed: `on_pypi` catches `Exception` broadly and
    turns it into "could not tell", which is precisely the behaviour
    that made the original bug intermittent instead of loud. So the call
    is recorded and the assertion fires after the test body -- surfacing
    as an ERROR beside a test that may itself have passed, which is why
    the message carries the fix and not just the diagnosis.

    `urlopen` is the choke point rather than `_fetch_json`, because
    `main()` binds its default at definition time: patching the module
    attribute would not reach a `main()` that has already been defined.
    `TestFetchJson` stubs `urlopen` for its own purposes afterwards, and
    monkeypatch is last-write-wins within a test.
    """
    reached = []

    def tripwire(url, *_args, **_kwargs):
        reached.append(url)
        raise check.urllib.error.URLError("the test suite does not have a network")

    monkeypatch.setattr(check.urllib.request, "urlopen", tripwire)
    yield
    assert not reached, (
        f"this test reached the network: {reached}. Every test here must "
        "stay off it -- pass `fetch=not_on_pypi` to main() for a definite "
        "'not published', or `--offline` to skip the PyPI check entirely."
    )


class TestOrdering:
    """Numeric, not lexical. `5.9.0` sorts above `5.10.0` as a string, and
    that is exactly the comparison this has to get right."""

    @pytest.mark.parametrize(
        "lower,higher",
        [
            ("5.9.0", "5.10.0"),
            ("5.19.0", "5.20.0"),
            ("5.9.9", "5.10.0"),
            ("4.99.0", "5.0.0"),
            ("5.19.0", "5.19.1"),
        ],
    )
    def test_a_higher_version_sorts_higher(self, check, lower, higher):
        assert check.parse(lower) < check.parse(higher)

    def test_a_string_comparison_would_have_got_this_wrong(self, check):
        assert "5.9.0" > "5.10.0"  # the trap
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
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)

    run("init", "--quiet", "-b", "main")
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "t")
    pyproject = root / "pyproject.toml"
    pyproject.write_text(f'[tool.poetry]\nversion = "{base_version}"\n', encoding="utf-8")
    run("add", "pyproject.toml")
    run("commit", "--quiet", "-m", "base")
    if tag:
        run("tag", tag)
    pyproject.write_text(f'[tool.poetry]\nversion = "{head_version}"\n', encoding="utf-8")
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
        assert check.main(["--base-ref", "main"], fetch=not_on_pypi) == 0
        assert "out-ranks" in capsys.readouterr().out

    def test_a_collision_exits_one_and_says_why(self, check, in_repo, capsys):
        in_repo("5.19.0", "5.19.0")
        assert check.main(["--base-ref", "main"], fetch=not_on_pypi) == 1
        assert "::error::" in capsys.readouterr().err

    def test_a_released_version_is_caught_through_real_tags(self, check, in_repo, capsys):
        in_repo("5.19.0", "5.20.0", tag="v5.20.0")
        assert check.main(["--base-ref", "main"], fetch=not_on_pypi) == 1
        assert "already released" in capsys.readouterr().err

    def test_the_base_ref_travels_into_the_message(self, check, in_repo, capsys):
        """A passing run says what it actually compared, so a wrong ref is
        visible rather than silently reassuring."""
        in_repo("5.19.0", "5.20.0")
        assert check.main(["--base-ref", "main"], fetch=not_on_pypi) == 0
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
        matches = [
            s
            for s in steps
            if s.startswith("      - name: Version bump has not been lost to a collision")
        ]
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
        assert check.main([], fetch=not_on_pypi) == 0
        assert "::warning::a release is owed" in capsys.readouterr().err

    def test_a_real_problem_still_exits_one(self, check, monkeypatch, capsys):
        monkeypatch.setattr(check, "problems", lambda *a: ["collision"])
        monkeypatch.setattr(check, "unreleased", lambda *a: "a release is owed")
        monkeypatch.setattr(check, "_git", lambda *a: '[tool.poetry]\nversion = "0.0.1"\n')
        assert check.main([], fetch=not_on_pypi) == 1
        err = capsys.readouterr().err
        assert "::warning::" in err and "::error::collision" in err

    def test_a_tagged_base_emits_no_warning_at_all(self, check, monkeypatch, capsys):
        """The quiet path: nothing is owed, so nothing is said. Pinned
        because a warning that fires unconditionally is one nobody
        reads, which would defeat the point of adding it."""
        monkeypatch.setattr(check, "problems", lambda *a: [])
        monkeypatch.setattr(check, "unreleased", lambda *a: None)
        monkeypatch.setattr(check, "_git", lambda *a: '[tool.poetry]\nversion = "0.0.1"\n')
        assert check.main([], fetch=not_on_pypi) == 0
        assert "::warning::" not in capsys.readouterr().err


class TestOnPyPI:
    """A published version is immutable: PyPI refuses a re-upload even
    after deletion, and yanking does not free the number. So this is the
    one release check that blocks -- and the one that must never block on
    a network hiccup, which is why "unknown" is a third outcome rather
    than being folded into either answer."""

    def test_a_404_means_not_published(self, check):
        assert check.on_pypi("9.9.9", lambda url: False) is False

    def test_a_payload_means_published(self, check):
        assert check.on_pypi("0.1.1", lambda url: {"info": {}}) is True

    def test_a_transport_failure_is_unknown_not_an_answer(self, check):
        def boom(url):
            raise OSError("no network")

        assert check.on_pypi("1.0.0", boom) is None

    def test_an_unreadable_body_is_unknown(self, check):
        assert check.on_pypi("1.0.0", lambda url: None) is None

    def test_it_asks_about_the_distribution_not_the_import_package(self, check):
        """`chitragupta` on PyPI is an unrelated project. Asking about it
        would report every one of our versions as taken."""
        seen = []
        check.on_pypi("1.2.3", lambda url: seen.append(url) or False)
        assert "chitragupta-cli/1.2.3" in seen[0]


class TestPyPIBlocks:
    def test_a_published_version_fails_the_check(self, check, monkeypatch, capsys):
        monkeypatch.setattr(check, "on_pypi", lambda *a: True)
        monkeypatch.setattr(check, "_git", lambda *a: '[tool.poetry]\nversion = "0.0.1"\n')
        assert check.main([]) == 1
        assert "can never be re-uploaded" in capsys.readouterr().err

    def test_an_unreachable_pypi_warns_and_continues(self, check, monkeypatch, capsys):
        monkeypatch.setattr(check, "on_pypi", lambda *a: None)
        monkeypatch.setattr(check, "problems", lambda *a: [])
        monkeypatch.setattr(check, "unreleased", lambda *a: None)
        monkeypatch.setattr(check, "_git", lambda *a: '[tool.poetry]\nversion = "0.0.1"\n')
        assert check.main([]) == 0
        assert "could not reach PyPI" in capsys.readouterr().err

    def test_offline_skips_the_network_entirely(self, check, monkeypatch, capsys):
        def boom(*_a):
            raise AssertionError("--offline must not touch the network")

        monkeypatch.setattr(check, "on_pypi", boom)
        monkeypatch.setattr(check, "problems", lambda *a: [])
        monkeypatch.setattr(check, "unreleased", lambda *a: None)
        monkeypatch.setattr(check, "_git", lambda *a: '[tool.poetry]\nversion = "0.0.1"\n')
        assert check.main(["--offline"]) == 0
        assert "could not reach PyPI" not in capsys.readouterr().err


class TestTheTestsStayOffTheNetwork:
    """`_no_real_network` and the injection point it polices (#425).

    Both halves are checked, because each fails silently without the
    other: a default swapped for a fake would leave the suite green
    while the CI run stopped asking PyPI anything, and a fixture that
    stopped being autouse would let the seven `main()` calls below drift
    back onto the network without a word.
    """

    def test_the_real_fetcher_is_still_what_ci_gets(self, check):
        """`main()`'s fetcher is injected for the tests, and must not
        become a way for the tests to disarm the check in CI.

        Nothing else here would notice, because every `main()` call in
        this module supplies its own fetcher or patches `on_pypi`. The
        same idiom as `test_git_output_is_decoded_as_utf8`: assert on
        the declaration, because the behaviour it guards is only
        observable on a host this suite is not.
        """
        import inspect

        assert inspect.signature(check.main).parameters["fetch"].default is check._fetch_json

    def test_the_tripwire_is_actually_installed(self, check):
        """The guard's own non-vacuous check, in the idiom `bench/`
        uses: a guard nothing verifies is a guard that can be deleted.

        Dropping `autouse=True` from `_no_real_network` breaks nothing
        visible -- every test still passes, on a suite quietly back on
        the network. Asserted by identity rather than by calling it,
        since a call would be *recorded* and would fail this test at
        teardown, which is the fixture reporting itself rather than
        this test checking it.
        """
        assert check.urllib.request.urlopen.__name__ == "tripwire"


class TestBlocksAMerge:
    """`blocks_a_merge`: the same rules, re-run at merge time (#560).

    The bug it exists for is the one this module's own docstring calls
    the opposite of a conflict -- and the part CI structurally cannot
    reach. `ci.yml` evaluates these rules against the merge commit
    GitHub built at `pull_request` time; another PR can merge, or push a
    tag, between that run and the merge. On #560 the colliding PR merged
    and tagged 17 seconds ahead, so `main` landed on a version already
    released against different content.
    """

    def test_it_fetches_before_it_reads_and_blocks_on_a_problem(self, check, monkeypatch, capsys):
        """The fetch has to come *first*, and that ordering is the whole
        fix: the rules read `origin/main` and the tags out of local git,
        so an unfetched read looks at a snapshot from before the merge
        or tag that causes the collision."""
        order = []
        monkeypatch.setattr(check.subprocess, "run", lambda *a, **k: order.append(("fetch", a[0])))
        monkeypatch.setattr(check, "main", lambda argv: order.append(("check", argv)) or 1)

        assert check.blocks_a_merge() is True
        assert [step for step, _ in order] == ["fetch", "check"]
        assert order[0][1][:2] == ["git", "fetch"]
        assert "--tags" in order[0][1]
        assert order[1][1] == ["--offline"]
        assert "Refusing to merge" in capsys.readouterr().out

    def test_a_sound_bump_does_not_block_and_says_nothing_extra(self, check, monkeypatch, capsys):
        monkeypatch.setattr(check.subprocess, "run", lambda *a, **k: None)
        monkeypatch.setattr(check, "main", lambda argv: 0)

        assert check.blocks_a_merge() is False
        assert "Refusing" not in capsys.readouterr().out

    def test_an_unreadable_base_ref_blocks_too(self, check, monkeypatch, capsys):
        """`main()` exits 1 for a base ref it cannot read as well as for
        a real collision, and both block. Deliberately: a merge is
        itself a network operation, so a state where this cannot tell is
        one where `gh pr merge` was not going to work either."""
        monkeypatch.setattr(check.subprocess, "run", lambda *a, **k: None)
        monkeypatch.setattr(check, "main", lambda argv: 1)

        assert check.blocks_a_merge() is True
        assert "Refusing to merge" in capsys.readouterr().out

    def test_any_other_exit_code_proceeds(self, check, monkeypatch):
        """Only 1 means "do not merge". A 2 (argparse usage) or anything
        else is not a verdict about the version, so it must not be read
        as one."""
        monkeypatch.setattr(check.subprocess, "run", lambda *a, **k: None)
        monkeypatch.setattr(check, "main", lambda argv: 2)
        assert check.blocks_a_merge() is False

    def test_a_failed_fetch_does_not_raise(self, check, monkeypatch):
        """`check=False` on the fetch, deliberately: no network, or no
        `origin`, must not turn a merge into a traceback."""
        calls = []

        def failing_run(*args, **kwargs):
            calls.append(kwargs.get("check"))
            return None

        monkeypatch.setattr(check.subprocess, "run", failing_run)
        monkeypatch.setattr(check, "main", lambda argv: 0)
        check.blocks_a_merge()
        assert calls == [False]


class TestFetchJson:
    """`_fetch_json` alone, with urlopen stubbed.

    Never reaches the network: a unit test that depends on PyPI being up
    is a test that fails for reasons having nothing to do with this code.
    The live path is exercised once, deliberately, in TestOnPyPI's
    injection point instead.
    """

    @staticmethod
    def _stub_urlopen(check, monkeypatch, result):
        import contextlib

        @contextlib.contextmanager
        def fake(_url, timeout=None):
            if isinstance(result, Exception):
                raise result
            yield result

        monkeypatch.setattr(check.urllib.request, "urlopen", fake)

    def test_a_body_is_decoded(self, check, monkeypatch):
        class Body:
            @staticmethod
            def read():
                return b'{"info": {"version": "1.0.0"}}'

        self._stub_urlopen(check, monkeypatch, Body())
        assert check._fetch_json("https://example.invalid")["info"]["version"] == "1.0.0"

    def test_a_404_is_the_answer_not_a_failure(self, check, monkeypatch):
        """Not on PyPI is exactly what this is asking, so a 404 is
        distinguished from every other error rather than lumped in."""
        err = check.urllib.error.HTTPError("u", 404, "Not Found", {}, None)
        self._stub_urlopen(check, monkeypatch, err)
        assert check._fetch_json("https://example.invalid") is False

    def test_any_other_http_status_is_unknown(self, check, monkeypatch):
        err = check.urllib.error.HTTPError("u", 503, "Unavailable", {}, None)
        self._stub_urlopen(check, monkeypatch, err)
        assert check._fetch_json("https://example.invalid") is None

    def test_a_transport_error_is_unknown(self, check, monkeypatch):
        self._stub_urlopen(check, monkeypatch, check.urllib.error.URLError("down"))
        assert check._fetch_json("https://example.invalid") is None

    def test_an_unparseable_body_is_unknown(self, check, monkeypatch):
        class Body:
            @staticmethod
            def read():
                return b"not json"

        self._stub_urlopen(check, monkeypatch, Body())
        assert check._fetch_json("https://example.invalid") is None

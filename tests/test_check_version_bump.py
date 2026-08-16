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


class TestTheCommand:
    def test_this_repository_passes_against_its_own_history(self, check, capsys):
        """Run for real, against real git output. The branch this lands on
        must out-rank main, which is the thing being asserted."""
        assert check.main([]) == 0
        assert "out-ranks" in capsys.readouterr().out

    def test_a_collision_exits_one_and_says_why(self, check, capsys, monkeypatch):
        monkeypatch.setattr(check, "_git", lambda *a: (
            '[tool.poetry]\nversion = "9.9.9"\n' if a[0] == "show" else "v9.9.9"))
        monkeypatch.setattr(check.Path, "read_text",
                            lambda *a, **k: '[tool.poetry]\nversion = "9.9.9"\n')
        assert check.main([]) == 1
        assert "::error::" in capsys.readouterr().err

    def test_the_base_ref_is_configurable(self, check, capsys):
        """CI compares against origin/main; a person checking locally may
        not have that ref, or may want to compare against another branch.
        The ref travels into the message, so a passing run says what it
        actually compared."""
        assert check.main(["--base-ref", "HEAD"]) == 0
        assert "HEAD's" in capsys.readouterr().out


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

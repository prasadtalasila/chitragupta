"""Values restated by hand in prose or in a config comment, each pinned
to the file that owns the value.

A failure here means a sentence (or a comment) has drifted from the
fact it quotes -- fix the sentence, or teach the pattern its new
wording. It does not mean CI is misconfigured: workflow-shape rules are
`tests/test_workflow_pins.py`, and the C1/C2 register's description is
`tests/test_technical_debt_scan.py`. Split by what reddens (#866), so a
docs-only PR goes red for a docs reason.
"""

import ast
import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DEBT_DOC = REPO_ROOT / "docs" / "TECHNICAL-DEBT.md"
CODE_STANDARDS_DOC = REPO_ROOT / "docs" / "CODE-STANDARDS.md"
BENCH_README = REPO_ROOT / "bench" / "README.md"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PYPROJECT_TOML = REPO_ROOT / "pyproject.toml"
PYLINTRC = REPO_ROOT / ".pylintrc"


@pytest.fixture(name="debt_doc")
def _debt_doc():
    # encoding="utf-8" explicitly: without it read_text uses the locale
    # codec, which is cp1252 on CI's Windows leg, and this document is
    # full of em dashes.
    return DEBT_DOC.read_text(encoding="utf-8")


@pytest.fixture(name="code_standards_doc")
def _code_standards_doc():
    return CODE_STANDARDS_DOC.read_text(encoding="utf-8")


@pytest.fixture(name="bench_readme")
def _bench_readme():
    return BENCH_README.read_text(encoding="utf-8")


# --- #353: the other drift-prone claims the issue asked to pin --------
#
# Each is a "now" claim -- true of the tree today, re-measured rather
# than a frozen record of a past baseline -- the same shape
# `_stated_sizes` above already pins for the C1/C2 register sizes.
# `_regex_pin` is that shape made generic, so #348 (PACKAGING.md) and
# #345 (ARCHITECTURE.md) can reuse it instead of reinventing it. Two
# claims that were once pinned here no longer are, each for the same
# reason: the debt was closed outright rather than merely re-measured,
# so there is no longer a prose figure to drift. The noqa-marker count
# is #354's (adopted `ruff`, deleted the "inert markers" section --
# `RUF100` is now the mechanism that checks the suppressed set is the
# right one). The annotation ratio is #355's (annotated every gap,
# deleted the "Type annotations" section -- `tests/test_annotation_scan.py`
# ratchets the count directly against the tree instead). The bench
# self-check count moved rather than closed: #356 turned `bench/`'s
# exclusion into a stated decision and relocated the live count from
# `docs/TECHNICAL-DEBT.md` to `bench/README.md`'s self-check section --
# still a drift-prone claim, so it is still pinned here, just against
# the new document. A second, weaker prose pin for either remaining
# closed claim would be exactly the two-debt-lists problem the
# register warns against.


def _regex_pin(pattern: re.Pattern, text: str, what: str) -> tuple[str, ...]:
    """Search `pattern` in a whitespace-normalised copy of `text` and
    return its captured groups, failing loudly rather than returning
    nothing if the sentence has been reworded past the pattern -- the
    same guarantee `_stated_sizes` gives the register-size claim, made
    reusable for the claims below and for future documents."""
    match = pattern.search(" ".join(text.split()))
    assert match, (
        f"{what} no longer states this fact in the shape this test reads "
        f"({pattern.pattern!r}). Rewording it is fine; teach this pattern "
        "the new shape in the same change, or the check silently stops "
        "running."
    )
    return match.groups()


_LINT_TARGET_QUOTE_RE = re.compile(r"pylint --rcfile=\.pylintrc ([^`]+)`")

_COVERAGE_SOURCE_QUOTE_RE = re.compile(r"source = (\[[^\]]*\])")

_BENCH_SELF_CHECK_COUNT_RE = re.compile(r"(\d+) of the (\d+) scripts here")


def _ci_lint_target() -> str:
    """The path list `ci.yml`'s lint job actually passes to pylint, read
    from the workflow rather than typed -- the source of truth both
    dangling cross-references #353 fixed were checked against."""
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    match = re.search(r"run: pylint --rcfile=\.pylintrc (\S.*\S)\s*$", text, re.MULTILINE)
    assert match, "ci.yml no longer runs pylint in the shape this test reads"
    return match.group(1)


def _pyproject_coverage_source() -> list[str]:
    """`[tool.coverage.run].source`, read from `pyproject.toml` rather
    than typed."""
    with open(PYPROJECT_TOML, "rb") as f:
        return tomllib.load(f)["tool"]["coverage"]["run"]["source"]


def _bench_self_check_counts() -> tuple[int, int]:
    """(scripts with a self_check(), total bench/*.py scripts), mirroring
    `for f in bench/*.py; do grep -q "def self_check" $f || echo $f; done`."""
    paths = sorted((REPO_ROOT / "bench").glob("*.py"))
    with_check = sum(1 for p in paths if "def self_check" in p.read_text(encoding="utf-8"))
    return with_check, len(paths)


def _assert_lint_target_matches(doc_name: str, text: str, ci_target: str) -> None:
    """Every `pylint --rcfile=.pylintrc ...` quoted in `text` must name
    `ci_target` -- the check both dangling cross-references #353 fixed
    would have caught, and that catches the next rename too."""
    quoted = _LINT_TARGET_QUOTE_RE.findall(" ".join(text.split()))
    assert quoted, (
        f"{doc_name} no longer quotes the pylint invocation in the shape "
        "this test reads (`pylint --rcfile=.pylintrc ...`)"
    )
    assert all(target.strip() == ci_target for target in quoted), (
        f"{doc_name} quotes `pylint --rcfile=.pylintrc ...` with a target "
        f"that no longer matches ci.yml's `{ci_target}`. This is the "
        "dangling-reference shape #353 fixed twice already (.pylintrc's "
        "stale section number, docs/CODE-STANDARDS.md's stale `src`)."
    )


def _assert_coverage_source_matches(doc_name: str, text: str, pyproject_source: list[str]) -> None:
    quoted = _COVERAGE_SOURCE_QUOTE_RE.findall(text)
    assert quoted, (
        f"{doc_name} no longer quotes [tool.coverage.run].source in the "
        "shape this test reads (`source = [...]`)"
    )
    for raw in quoted:
        assert ast.literal_eval(raw) == pyproject_source, (
            f"{doc_name} quotes a coverage `source` list that no longer "
            f"matches pyproject.toml's {pyproject_source!r}."
        )


class TestTheOtherDriftProneClaimsArePinned:
    """Two of the four claims #353's own "What to build" list named are
    checked here (lint target, coverage source) -- the other two (the
    annotation ratio and the noqa marker count) are #355's and #354's
    now, not this file's. The bench self-check count, a third claim
    pinned here beyond #353's original four, is also checked here
    again, relocated by #356 from `docs/TECHNICAL-DEBT.md` to
    `bench/README.md`; see the comment above."""

    def test_the_quoted_lint_target_matches_ci_everywhere_it_appears(
        self, debt_doc, code_standards_doc
    ):
        ci_target = _ci_lint_target()
        _assert_lint_target_matches("docs/TECHNICAL-DEBT.md", debt_doc, ci_target)
        _assert_lint_target_matches("docs/CODE-STANDARDS.md", code_standards_doc, ci_target)

    def test_the_quoted_coverage_source_matches_pyproject(self, bench_readme):
        _assert_coverage_source_matches(
            "bench/README.md", bench_readme, _pyproject_coverage_source()
        )

    def test_the_bench_self_check_count_matches_the_tree(self, bench_readme):
        stated = tuple(
            int(n) for n in _regex_pin(_BENCH_SELF_CHECK_COUNT_RE, bench_readme, "bench/README.md")
        )
        assert stated == _bench_self_check_counts(), (
            "bench/README.md's self-check count no longer matches bench/*.py. "
            "Re-measure rather than editing the figure by hand."
        )


class TestTheNewPinsFailLoudlyWhenReworded:
    """The same guarantee
    `test_a_reworded_size_sentence_fails_loudly_rather_than_silently`
    pins for `_stated_sizes`, extended to the new patterns above: a pin
    that silently stops matching is worse than no pin."""

    def test_a_lint_target_no_longer_quoted_fails_loudly(self):
        with pytest.raises(AssertionError, match="no longer quotes the pylint invocation"):
            _assert_lint_target_matches(
                "the doc", "prose with no invocation quoted", "chitragupta scripts"
            )

    def test_a_lint_target_quoted_with_a_stale_value_fails_loudly(self):
        with pytest.raises(AssertionError, match="no longer matches ci.yml's"):
            _assert_lint_target_matches(
                "the doc", "`pylint --rcfile=.pylintrc src scripts`", "chitragupta scripts"
            )

    def test_a_coverage_source_no_longer_quoted_fails_loudly(self):
        with pytest.raises(AssertionError, match="no longer quotes"):
            _assert_coverage_source_matches(
                "the doc", "prose with no source list quoted", ["chitragupta"]
            )

    def test_a_coverage_source_quoted_with_a_stale_value_fails_loudly(self):
        with pytest.raises(AssertionError, match="no longer matches pyproject.toml's"):
            _assert_coverage_source_matches(
                "the doc", 'source = ["src", "scripts"]', ["chitragupta", "scripts"]
            )

    def test_a_reworded_bench_self_check_count_sentence_fails_loudly(self):
        with pytest.raises(AssertionError, match="no longer states this fact"):
            _regex_pin(
                _BENCH_SELF_CHECK_COUNT_RE, "20 scripts have one, out of 22 total.", "the doc"
            )


class TestThePylintrcDoesNotDriftFromWhatItConfigures:
    """Two of #512's four config findings, each turned into the check
    that would have caught it. Both were silent: a stale claim in a
    config file is read by people, not by anything that fails. The other
    two are workflow rules, in `tests/test_workflow_pins.py`."""

    def test_the_pylintrc_python_floor_matches_the_project(self):
        """m-83: `.pylintrc` said `py-version=3.10` against a project
        pinned `^3.12`, so pylint's version-dependent checks answered for
        an interpreter this project does not support -- which *suppresses*
        findings rather than adding them."""
        pylintrc = PYLINTRC.read_text(encoding="utf-8")
        match = re.search(r"^py-version=(\d+)\.(\d+)$", pylintrc, re.MULTILINE)
        assert match, ".pylintrc no longer sets py-version in the shape this test reads"
        declared = tomllib.loads(PYPROJECT_TOML.read_text(encoding="utf-8"))
        floor = declared["tool"]["poetry"]["dependencies"]["python"]
        assert floor.lstrip("^~>=").startswith(f"{match.group(1)}.{match.group(2)}"), (
            f".pylintrc's py-version ({match.group(1)}.{match.group(2)}) does not match "
            f"pyproject.toml's python constraint ({floor}). Pylint would be checking "
            "against an interpreter this project does not support."
        )

    def test_the_pylintrc_does_not_still_call_itself_unenforced(self):
        """m-83's other half: the header said "NOT ENFORCED YET. No CI job
        runs this" while `ci.yml`'s lint job ran it at a blocking bar."""
        pylintrc = PYLINTRC.read_text(encoding="utf-8")
        assert "NOT ENFORCED" not in pylintrc
        assert "pylint --rcfile=.pylintrc" in CI_WORKFLOW.read_text(encoding="utf-8")

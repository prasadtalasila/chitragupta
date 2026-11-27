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
    return DEBT_DOC.read_text(encoding="utf-8")


@pytest.fixture(name="code_standards_doc")
def _code_standards_doc():
    return CODE_STANDARDS_DOC.read_text(encoding="utf-8")


@pytest.fixture(name="bench_readme")
def _bench_readme():
    return BENCH_README.read_text(encoding="utf-8")


def _regex_pin(pattern: re.Pattern, text: str, what: str) -> tuple[str, ...]:
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
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    match = re.search(r"run: pylint --rcfile=\.pylintrc (\S.*\S)\s*$", text, re.MULTILINE)
    assert match, "ci.yml no longer runs pylint in the shape this test reads"
    return match.group(1)


def _pyproject_coverage_source() -> list[str]:
    with open(PYPROJECT_TOML, "rb") as f:
        return tomllib.load(f)["tool"]["coverage"]["run"]["source"]


def _bench_self_check_counts() -> tuple[int, int]:
    paths = sorted((REPO_ROOT / "bench").glob("*.py"))
    with_check = sum(1 for p in paths if "def self_check" in p.read_text(encoding="utf-8"))
    return with_check, len(paths)


def _assert_lint_target_matches(doc_name: str, text: str, ci_target: str) -> None:
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
    def test_the_pylintrc_python_floor_matches_the_project(self):
        pylintrc = PYLINTRC.read_text(encoding="utf-8")
        match = re.search(r"^py-version=(\d+)\.(\d+)$", pylintrc, re.MULTILINE)
        assert match, ".pylintrc no longer sets py-version in the shape this test reads"
        declared = tomllib.loads(PYPROJECT_TOML.read_text(encoding="utf-8"))
        floor = declared["project"]["requires-python"]
        assert floor.lstrip("^~>=").startswith(f"{match.group(1)}.{match.group(2)}"), (
            f".pylintrc's py-version ({match.group(1)}.{match.group(2)}) does not match "
            f"pyproject.toml's requires-python ({floor}). Pylint would be checking "
            "against an interpreter this project does not support."
        )

    def test_the_pylintrc_does_not_still_call_itself_unenforced(self):
        pylintrc = PYLINTRC.read_text(encoding="utf-8")
        assert "NOT ENFORCED" not in pylintrc
        assert "pylint --rcfile=.pylintrc" in CI_WORKFLOW.read_text(encoding="utf-8")

import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
WINDOWS_CONFIG = REPO_ROOT / "coveragerc-windows.toml"


def _coverage_run(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)["tool"]["coverage"]["run"]


class TestTheTwoConfigsAgreeOnWhatTheyMeasure:
    def test_run_sections_are_identical(self):
        assert _coverage_run(WINDOWS_CONFIG) == _coverage_run(PYPROJECT)

    def test_windows_fail_under_matches_linux(self):
        with open(PYPROJECT, "rb") as f:
            linux_report = tomllib.load(f)["tool"]["coverage"]["report"]
        with open(WINDOWS_CONFIG, "rb") as f:
            windows_report = tomllib.load(f)["tool"]["coverage"]["report"]
        assert windows_report["fail_under"] == linux_report["fail_under"] == 100

    def test_windows_exclude_lines_is_a_strict_superset(self):
        with open(PYPROJECT, "rb") as f:
            linux_exclude = set(tomllib.load(f)["tool"]["coverage"]["report"]["exclude_lines"])
        with open(WINDOWS_CONFIG, "rb") as f:
            windows_exclude = set(tomllib.load(f)["tool"]["coverage"]["report"]["exclude_lines"])
        assert linux_exclude < windows_exclude


DEVELOPER_AGENTS = REPO_ROOT / "DEVELOPER-AGENTS.md"

_STATED_FLOOR_RE = re.compile(r"\bholds? (?:the (?:full|same) )?(\d+)\b")


def _stated_floors(text: str) -> list[int]:
    floors = [int(n) for n in _STATED_FLOOR_RE.findall(" ".join(text.split()))]
    assert floors, (
        "DEVELOPER-AGENTS.md no longer states the coverage floor in the shape "
        f"this test reads ({_STATED_FLOOR_RE.pattern!r}). Rewording it is fine; "
        "teach this pattern the new shape in the same change."
    )
    return floors


class TestTheProseStatesTheRealFloor:
    def test_developer_agents_states_the_configs_floor(self):
        with open(WINDOWS_CONFIG, "rb") as f:
            floor = tomllib.load(f)["tool"]["coverage"]["report"]["fail_under"]
        stated = _stated_floors(DEVELOPER_AGENTS.read_text(encoding="utf-8"))
        assert set(stated) == {floor}, (
            f"DEVELOPER-AGENTS.md states coverage floor(s) {stated}; both "
            f"coverage configs say fail_under = {floor}."
        )

    def test_the_pre_863_sentence_is_caught(self):
        old = (
            "Linux holds the full 100, and the Windows leg -- which installs no "
            "`os-deps` and so self-skips the render and pdf tests -- holds 95"
        )
        assert _stated_floors(old) == [100, 95]

    def test_a_reworded_sentence_fails_loudly(self):
        with pytest.raises(AssertionError, match="no longer states the coverage floor"):
            _stated_floors("Both legs are measured against one number.")


_BARE_PRAGMA = re.compile(r"#\s*pragma[:\s]?\s*no\s*" + r"cover(?!-windows)", re.IGNORECASE)
_SCANNED = ("chitragupta", "scripts", ".claude/hooks", "tests", "bench")


def test_no_bare_no_cover_pragma_is_left_in_the_tree():
    found = [
        f"{path.relative_to(REPO_ROOT)}:{n}"
        for root in _SCANNED
        for path in sorted((REPO_ROOT / root).rglob("*.py"))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if _BARE_PRAGMA.search(line)
    ]
    assert not found, "inert coverage pragma(s):\n  " + "\n  ".join(found)


@pytest.mark.parametrize(
    "comment", ["# pragma: no ", "#pragma:no ", "# pragma: no  ", "# PRAGMA: NO "]
)
def test_the_bare_pragma_pattern_sees_every_spelling_coverage_did(comment):
    assert _BARE_PRAGMA.search(f"x  {comment}" + "cover - why")


def test_the_bare_pragma_pattern_spares_the_windows_marker():
    assert not _BARE_PRAGMA.search("x  # pragma: no " + "cover-windows")

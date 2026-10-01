"""`pyproject.toml`'s `[tool.coverage.run]` and `coveragerc-windows.toml`'s
own copy must agree on everything except the one axis they are meant to
differ on (#291): CI's Windows leg excludes
lines it can never reach -- the `pandoc`/`pdflatex`/`pdftotext` call
sites `os-deps` never installs there, and separately the
`multiprocessing`-forkserver/shebang-script branches that platform lacks
outright -- via its own `[tool.coverage.report].exclude_lines` entry,
`pragma: no cover-windows`. `--cov-config` replaces
config discovery entirely rather than merging with `pyproject.toml`, so
the Windows file carries a full, independent copy of `[run]` -- exactly
the kind of duplication that drifts silently if nothing pins it, the same
shape `test_pyproject_extras.py` polices for the extras/group lists.
"""

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
        """Only [report] may differ -- [run] decides what is measured at
        all, and that must be the same set on both legs."""
        assert _coverage_run(WINDOWS_CONFIG) == _coverage_run(PYPROJECT)

    def test_windows_fail_under_matches_linux(self):
        """The whole point of #3.6: a floor lower than Linux's 100 would
        let a real, Windows-reachable regression hide under slack again."""
        with open(PYPROJECT, "rb") as f:
            linux_report = tomllib.load(f)["tool"]["coverage"]["report"]
        with open(WINDOWS_CONFIG, "rb") as f:
            windows_report = tomllib.load(f)["tool"]["coverage"]["report"]
        assert windows_report["fail_under"] == linux_report["fail_under"] == 100

    def test_windows_exclude_lines_is_a_strict_superset(self):
        """The Windows leg may exclude more (the toolchain-only pragma),
        never less -- narrowing what Linux already excludes here would be
        a silent behaviour change to the wrong file."""
        with open(PYPROJECT, "rb") as f:
            linux_exclude = set(tomllib.load(f)["tool"]["coverage"]["report"]["exclude_lines"])
        with open(WINDOWS_CONFIG, "rb") as f:
            windows_exclude = set(tomllib.load(f)["tool"]["coverage"]["report"]["exclude_lines"])
        assert linux_exclude < windows_exclude


DEVELOPER_AGENTS = REPO_ROOT / "DEVELOPER-AGENTS.md"

# "Linux holds the full 100", "the Windows leg ... holds 95", "both legs
# hold 100": every shape the coverage bullet has used to state a floor.
_STATED_FLOOR_RE = re.compile(r"\bholds? (?:the (?:full|same) )?(\d+)\b")


def _stated_floors(text: str) -> list[int]:
    """Every coverage floor `text` states in prose. Asserts it found one,
    so a rewording that drops the sentence's shape fails loudly instead
    of leaving nothing to compare."""
    floors = [int(n) for n in _STATED_FLOOR_RE.findall(" ".join(text.split()))]
    assert floors, (
        "DEVELOPER-AGENTS.md no longer states the coverage floor in the shape "
        f"this test reads ({_STATED_FLOOR_RE.pattern!r}). Rewording it is fine; "
        "teach this pattern the new shape in the same change."
    )
    return floors


class TestTheProseStatesTheRealFloor:
    """#863: the configs moved to one floor in #291, and the prose kept
    saying the Windows leg "holds 95" for months afterwards, with nothing
    to catch a reader who lowered the floor back "because the docs say so"."""

    def test_developer_agents_states_the_configs_floor(self):
        with open(WINDOWS_CONFIG, "rb") as f:
            floor = tomllib.load(f)["tool"]["coverage"]["report"]["fail_under"]
        stated = _stated_floors(DEVELOPER_AGENTS.read_text(encoding="utf-8"))
        assert set(stated) == {floor}, (
            f"DEVELOPER-AGENTS.md states coverage floor(s) {stated}; both "
            f"coverage configs say fail_under = {floor}."
        )

    def test_the_pre_863_sentence_is_caught(self):
        """The exact text #863 reported, so the pin is known to see it."""
        old = (
            "Linux holds the full 100, and the Windows leg -- which installs no "
            "`os-deps` and so self-skips the render and pdf tests -- holds 95"
        )
        assert _stated_floors(old) == [100, 95]

    def test_a_reworded_sentence_fails_loudly(self):
        with pytest.raises(AssertionError, match="no longer states the coverage floor"):
            _stated_floors("Both legs are measured against one number.")


# Coverage's own default exclusion pattern, so every spelling it would
# have honoured is caught; built from two pieces so this file does not
# match itself.
_BARE_PRAGMA = re.compile(r"#\s*pragma[:\s]?\s*no\s*" + r"cover(?!-windows)", re.IGNORECASE)
_SCANNED = ("chitragupta", "scripts", ".claude/hooks", "tests", "bench")


def test_no_bare_no_cover_pragma_is_left_in_the_tree():
    """Both configs set `exclude_lines`, which *replaces* coverage's
    default list, so a bare no-cover pragma is honoured on neither leg
    (#868): it reads as an exclusion and is not one. Under `tests/` and
    `bench/` it is inert twice over, since neither is measured."""
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

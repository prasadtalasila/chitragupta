"""`pyproject.toml`'s `[tool.coverage.run]` and `coveragerc-windows.toml`'s
own copy must agree on everything except the one axis they are meant to
differ on (`docs/TECHNICAL-DEBT.md` #3.6): CI's Windows leg excludes the
`pandoc`/`pdflatex`/`pdftotext` call sites it can never reach (`os-deps`
is apt-only there), via its own `[tool.coverage.report].exclude_lines`
entry, `pragma: no cover-windows-toolchain`. `--cov-config` replaces
config discovery entirely rather than merging with `pyproject.toml`, so
the Windows file carries a full, independent copy of `[run]` -- exactly
the kind of duplication that drifts silently if nothing pins it, the same
shape `test_pyproject_extras.py` polices for the extras/group lists.
"""

import tomllib
from pathlib import Path

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
            windows_exclude = set(
                tomllib.load(f)["tool"]["coverage"]["report"]["exclude_lines"]
            )
        assert linux_exclude < windows_exclude

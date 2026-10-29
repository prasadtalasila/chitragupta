"""The rule ids `figure check` reports are one set in three places (#1053).

A finding, a `% cg-allow:` line, docs/TIKZ-STYLE.md and the
figure-drawer skill's references/check.md all quote a rule by its id.
`chitragupta/figure/_rules.py` is the registry; this pins the two
tables to it, so a rule cannot ship only in code (no author can look it
up) or only in prose (nothing checks it). That every `SKILL.md` copy
names references/check.md is pinned in tests/test_skill_figure_step.py.
"""

import re
from pathlib import Path

import pytest

from chitragupta.figure._rules import RULES

REPO_ROOT = Path(__file__).resolve().parent.parent
TIKZ_STYLE = REPO_ROOT / "docs" / "TIKZ-STYLE.md"
CHECK_MD = REPO_ROOT / ".claude" / "skills" / "figure-drawer" / "references" / "check.md"

# A table row whose first cell is one backticked id.
_ROW_ID_RE = re.compile(r"^\| `([a-z0-9-]+)` \|", re.MULTILINE)


def table_ids(text: str, heading: str) -> set[str]:
    """The ids in the first column of the first table under `heading`."""
    section = text[text.index(heading) :]
    table = re.search(r"(?:^\|.*\n)+", section, re.MULTILINE)
    return set(_ROW_ID_RE.findall(table.group(0)))


def mismatch(found: set[str]) -> dict:
    """What `found` lacks and what it adds, against the registry."""
    return {"missing": sorted(set(RULES) - found), "extra": sorted(found - set(RULES))}


SOURCES = {
    "TIKZ-STYLE.md": (TIKZ_STYLE, "## 🔎 The rules `figure check` reports"),
    "check.md": (CHECK_MD, "## What to do with each finding"),
}


@pytest.mark.parametrize("name", SOURCES)
def test_the_table_names_exactly_the_registered_rules(name):
    path, heading = SOURCES[name]

    found = table_ids(path.read_text(encoding="utf-8"), heading)

    assert mismatch(found) == {"missing": [], "extra": []}


def test_the_comparison_catches_a_dropped_rule_and_an_invented_one():
    """The guard tested against the shape it exists to catch: the real
    TIKZ-STYLE.md table with one row dropped and one id that is not a
    rule added."""
    path, heading = SOURCES["TIKZ-STYLE.md"]
    text = path.read_text(encoding="utf-8")
    dropped = re.sub(r"^\| `focal-count` \|.*\n", "", text, flags=re.MULTILINE)
    edited = dropped.replace(
        "| `size-width` |", "| `size-wide` | figure | objective | typo |\n| `size-width` |", 1
    )

    assert mismatch(table_ids(edited, heading)) == {
        "missing": ["focal-count"],
        "extra": ["size-wide"],
    }

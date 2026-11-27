import re
from pathlib import Path

import pytest

from chitragupta.figure._rules import RULES

REPO_ROOT = Path(__file__).resolve().parent.parent
RULE_INDEX = REPO_ROOT / "docs" / "figure-checks" / "README.md"
CHECK_MD = REPO_ROOT / ".claude" / "skills" / "figure-drawer" / "references" / "check.md"

_ROW_ID_RE = re.compile(r"^\| `([a-z0-9-]+)` \|", re.MULTILINE)


def table_ids(text: str, heading: str) -> set[str]:
    section = text[text.index(heading) :]
    table = re.search(r"(?:^\|.*\n)+", section, re.MULTILINE)
    return set(_ROW_ID_RE.findall(table.group(0)))


def mismatch(found: set[str]) -> dict:
    return {"missing": sorted(set(RULES) - found), "extra": sorted(found - set(RULES))}


SOURCES = {
    "figure-checks/README.md": (RULE_INDEX, "## 📋 Every rule, and where it is explained"),
    "check.md": (CHECK_MD, "## What to do with each finding"),
}


@pytest.mark.parametrize("name", SOURCES)
def test_the_table_names_exactly_the_registered_rules(name):
    path, heading = SOURCES[name]

    found = table_ids(path.read_text(encoding="utf-8"), heading)

    assert mismatch(found) == {"missing": [], "extra": []}


def test_the_comparison_catches_a_dropped_rule_and_an_invented_one():
    path, heading = SOURCES["figure-checks/README.md"]
    text = path.read_text(encoding="utf-8")
    dropped = re.sub(r"^\| `focal-count` \|.*\n", "", text, flags=re.MULTILINE)
    edited = dropped.replace(
        "| `size-width` |", "| `size-wide` | figure | objective | typo |\n| `size-width` |", 1
    )

    assert mismatch(table_ids(edited, heading)) == {
        "missing": ["focal-count"],
        "extra": ["size-wide"],
    }

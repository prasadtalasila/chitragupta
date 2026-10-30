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


# docs/FIGURE-DRAWER.md explains the connector and contrast rules for a
# person (#1063): one `### <id>: ...` heading each, and a `**Fix.**`
# paragraph that is check.md's line for that rule, word for word.
FIGURE_DRAWER = REPO_ROOT / "docs" / "FIGURE-DRAWER.md"
_GUIDE_HEADING = "## 🔬 What `figure check` looks for in lines and colours"
_EXPLAINED_RE = re.compile(r"^### ([a-z0-9-]+): ", re.MULTILINE)
_FIX_RE = re.compile(r"^\*\*Fix\.\*\* (.+?)(?:\n\n|\Z)", re.MULTILINE | re.DOTALL)
_CHECK_ROW_RE = re.compile(r"^\| `([a-z0-9-]+)` \| [a-z]+ \| (.+) \|$", re.MULTILINE)


def guide_rules(text: str) -> dict[str, str]:
    """`{rule id: its Fix paragraph}` from the guide's section, one entry
    per `###` heading that names a rule: whitespace folded, and the
    closing full stop a table cell does not carry dropped."""
    start = text.index(_GUIDE_HEADING)
    section = text[start : text.index("\n## ", start + 1)]
    parts = _EXPLAINED_RE.split(section)[1:]
    fixes = {}
    for rule, body in zip(parts[::2], parts[1::2]):
        found = _FIX_RE.search(body)
        fixes[rule] = " ".join(found.group(1).split()).removesuffix(".") if found else ""
    return fixes


def check_fixes() -> dict[str, str]:
    """check.md's fix cell per rule, with the table's `\\|` unescaped."""
    text = CHECK_MD.read_text(encoding="utf-8")
    return {rule: fix.replace("\\|", "|") for rule, fix in _CHECK_ROW_RE.findall(text)}


def test_the_guide_explains_exactly_the_connector_and_contrast_rules():
    explained = set(guide_rules(FIGURE_DRAWER.read_text(encoding="utf-8")))

    assert explained == {rule for rule in RULES if re.fullmatch(r"[ck]\d-[a-z-]+", rule)}


def test_each_fix_in_the_guide_is_check_md_s_word_for_word():
    fixes = check_fixes()

    for rule, fix in guide_rules(FIGURE_DRAWER.read_text(encoding="utf-8")).items():
        assert fix == fixes[rule], rule


def test_a_reworded_fix_is_caught():
    """The guard against the drift it exists for: one fix paraphrased."""
    text = FIGURE_DRAWER.read_text(encoding="utf-8").replace(
        "Move the tag clear of the node it sits under.", "Move the tag away.", 1
    )

    assert guide_rules(text)["c6-tag-covered"] != check_fixes()["c6-tag-covered"]

"""The faulty and fixed figures in docs/figure-checks/ do what the pages say.

Each rule `figure check` reports has a directory under
`docs/figure-checks/examples/<rule-id>/` holding `faulty.tex` and
`fixed.tex`, with their twins. The faulty figure breaks that one rule
and no other; the fixed figure breaks none and leaves nothing
unmeasured, so "no findings" on it means every rule ran. The pages quote
each rule's fix from the skill's `references/check.md` word for word.

The figures are compiled here, so a threshold that moves fails this test
rather than leaving a page showing a defect the check no longer reports.
"""

import re
from pathlib import Path

import pytest

from chitragupta.page import ARTICLE
from chitragupta.figure import _check
from chitragupta.figure._rules import RULES
from tests.conftest import needs_tikz

REPO_ROOT = Path(__file__).resolve().parent.parent
PAGES = REPO_ROOT / "docs" / "figure-checks"
EXAMPLES = PAGES / "examples"
CHECK_MD = REPO_ROOT / ".claude" / "skills" / "figure-drawer" / "references" / "check.md"

# Advisory reports that print for every figure, a number beside a
# reference range. No figure "breaks" them, so they have no pair.
ALWAYS_REPORTED = {"size-height", "size-slack", "budget-nodes", "budget-edges"}

EXAMPLE_RULES = sorted(path.name for path in EXAMPLES.iterdir() if path.is_dir())


def test_every_rule_with_something_to_break_has_an_example():
    assert sorted(set(RULES) - ALWAYS_REPORTED) == EXAMPLE_RULES


def _check_file(rule: str, variant: str) -> _check.CheckResult:
    return _check.check(EXAMPLES / rule / f"{variant}.tex", ARTICLE.text_width_pt)


@pytest.mark.slow
@needs_tikz
@pytest.mark.parametrize("rule", EXAMPLE_RULES)
def test_the_faulty_figure_breaks_its_rule_and_no_other(rule):
    result = _check_file(rule, "faulty")

    if RULES[rule].cls == "advisory":
        assert [f.rule for f in result.findings] == []
        assert rule in {f.rule for f in result.advisory}
    else:
        assert {f.rule for f in result.findings} == {rule}


@pytest.mark.slow
@needs_tikz
@pytest.mark.parametrize("rule", EXAMPLE_RULES)
def test_the_fixed_figure_breaks_nothing_and_everything_was_measured(rule):
    result = _check_file(rule, "fixed")

    assert result.findings == []
    assert result.not_measured == []
    assert rule not in {f.rule for f in result.advisory}


# One `### \`<rule-id>\`` heading per rule across the pages, each with a
# `**Fix.**` paragraph that is check.md's cell for that rule.
_HEADING_RE = re.compile(r"^### `([a-z0-9-]+)`", re.MULTILINE)
_FIX_RE = re.compile(r"^\*\*Fix\.\*\* (.+?)(?:\n\n|\Z)", re.MULTILINE | re.DOTALL)
_CHECK_ROW_RE = re.compile(r"^\| `([a-z0-9-]+)` \| [a-z]+ \| (.+) \|$", re.MULTILINE)


def page_fixes() -> dict[str, str]:
    """`{rule id: its Fix paragraph}` over every page, whitespace folded
    and the closing full stop a table cell does not carry dropped."""
    fixes: dict[str, str] = {}
    for page in sorted(PAGES.glob("*.md")):
        parts = _HEADING_RE.split(page.read_text(encoding="utf-8"))[1:]
        for rule, body in zip(parts[::2], parts[1::2]):
            assert rule not in fixes, f"{rule} is explained twice"
            found = _FIX_RE.search(body)
            fixes[rule] = " ".join(found.group(1).split()).removesuffix(".") if found else ""
    return fixes


def check_fixes() -> dict[str, str]:
    """check.md's fix cell per rule, with the table's `\\|` unescaped."""
    text = CHECK_MD.read_text(encoding="utf-8")
    return {rule: fix.replace("\\|", "|") for rule, fix in _CHECK_ROW_RE.findall(text)}


def test_the_pages_explain_every_rule_once():
    assert sorted(page_fixes()) == sorted(RULES)


def test_each_fix_on_the_pages_is_check_md_s_word_for_word():
    expected = check_fixes()

    for rule, fix in page_fixes().items():
        assert fix == expected[rule], rule

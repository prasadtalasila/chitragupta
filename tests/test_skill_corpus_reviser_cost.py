import re
from pathlib import Path

import pytest

from tests.skill_text import collapsed

REPO_ROOT = Path(__file__).resolve().parent.parent
COPIES = (
    ".claude/skills/corpus-reviser/SKILL.md",
    ".agents/skills/corpus-reviser/SKILL.md",
    ".opencode/skills/corpus-reviser-opencode/SKILL.md",
)
_LOOP = "## The loop"
_FIRST = re.compile(r"\*\*Before step 1, say the cost sentence and put it on record\.\*\*")
_FOLLOW = re.compile(r"Follow `[^`]+/SKILL\.md`'s `## The loop`")


@pytest.mark.parametrize("copy", COPIES)
def test_the_cost_sentence_opens_the_loop(copy):
    text = collapsed((REPO_ROOT / copy).read_text(encoding="utf-8"))
    loop = text[text.index(_LOOP) :]
    first, follow = _FIRST.search(loop), _FOLLOW.search(loop)
    assert follow, f"{copy}: the loop no longer sends the model to draft-reviser's steps"
    assert first, f"{copy}: the loop does not open on the cost sentence"
    assert first.start() < follow.start(), f"{copy}: the cost sentence comes after step 1"


@pytest.mark.parametrize("copy", COPIES)
def test_nothing_may_come_before_the_cost_sentence(copy):
    text = collapsed((REPO_ROOT / copy).read_text(encoding="utf-8"))
    loop = text[text.index(_LOOP) :]
    window = loop[: _FOLLOW.search(loop).start()]
    assert "No search and no edit to the draft comes before it" in window, copy
    assert "Done when" in window, copy


@pytest.mark.parametrize("copy", COPIES)
def test_the_cost_sentence_goes_on_record_before_the_first_search(copy):
    text = collapsed((REPO_ROOT / copy).read_text(encoding="utf-8"))
    loop = text[text.index(_LOOP) :]
    window = loop[: _FOLLOW.search(loop).start()]
    assert "`revisions.md`" in window, copy
    assert "Cost stated before the first search:" in window, copy

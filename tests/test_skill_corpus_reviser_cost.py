"""corpus-reviser says what a whole-corpus pass costs as the loop's first act.

The skill has always asked for one cost sentence "before the first
search", in a section above its procedure. Its procedure then begins
"Follow draft-reviser's loop, steps 1 through 7", and a model following
steps went straight to step 1: in six benched runs the sentence came
before the first search in three, and in the closing summary in the
rest, where the user can no longer stop the pass (#1204, the bench
recorded in plans/1091-ledger-corpus-reviser.md). The instruction now
sits inside the loop, ahead of the sentence that sends the model to
draft-reviser's steps, in every harness copy.
"""

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
_FIRST = re.compile(r"\*\*Before step 1, say the cost sentence\.\*\*")
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
    assert "No search and no edit comes before it" in window, copy
    assert "Done when" in window, copy

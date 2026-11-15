"""Every skill's `SKILL.md` stays under a byte budget that only falls (#1091).

The whole file loads when a skill triggers, in each of three harness
copies, and a model skims a long one. Nothing else stops a file from
growing: every feature adds a paragraph and none takes one out. So each
skill has a cap, checked against all three copies, and the cap moves
with the file:

- a copy over its cap fails, so growth needs a visible cap raise;
- a cap more than `SLACK` bytes above the largest copy fails, so a PR
  that shrinks a skill lowers its cap in the same commit;
- a cap above the skill's target carries the reason it is still there.

Bytes, not lines: a line limit is dodged by re-wrapping, and bytes are
what a context window spends. A raise cannot be detected from the tree
alone; the reason column is what makes one visible in review.

What a shrink may move is prose: rationale and detail go to the skill's
`references/` or `.claude/skills-common/references/`, behind a pointer
that says when to read them. Every `python -m chitragupta...` command, every
marker a draft must carry and every phrase a test reads from the raw file
stay in `SKILL.md` (plans/1091-skill-shrink.md, Decision 2).
"""

import pytest

from tests.test_skill_harness_copies import ROOTS, SKILLS, folder

GENRE_TARGET = 12_000
OTHER_TARGET = 8_000
SLACK = 1_000
GENRES = {
    "survey-writer",
    "textbook-chapter-writer",
    "thesis-chapter-writer",
    "tutorial-writer",
}
_LATER = "#1091: shrinks to its target in its own PR"

# skill: (cap in bytes, why the cap is above the target, or None)
BUDGET = {
    "agenda-reviser": (29_000, f"{_LATER}; draft diff closing step (#1194)"),
    "book-assembler": (20_000, _LATER),
    "corpus-reviser": (
        11_000,
        "#1091: deduplicated from 12.8 KB; it states only how its pass differs from "
        "draft-reviser's loop, and the rest is its guardrails, routing table, three "
        "closing steps' commands and tested text (plans/1091-ledger-corpus-reviser.md)",
    ),
    "deep-research": (41_000, _LATER),
    "demo-recorder": (6_000, None),
    "draft-reviser": (
        23_000,
        "#1091: deduplicated from 29 KB; agenda-reviser and corpus-reviser follow "
        "its loop by step number, so every step stays complete inline, and the "
        "rest is commands and tested text (plans/1091-ledger-draft-reviser.md)",
    ),
    "figure-drawer": (7_000, None),
    "skill-bench": (5_000, None),
    "review-digest": (17_000, _LATER),
    "survey-writer": (
        15_000,
        "#1091: deduplicated from 32 KB; the rest is commands and tested text, "
        "and the target is a guideline (plans/1091-skill-shrink.md, Decision 1)",
    ),
    "textbook-chapter-writer": (33_000, _LATER),
    "thesis-chapter-writer": (34_000, _LATER),
    "tutorial-writer": (34_000, _LATER),
}


def target(name: str) -> int:
    return GENRE_TARGET if name in GENRES else OTHER_TARGET


def largest_copy(name: str) -> int:
    return max(len((folder(h, name) / "SKILL.md").read_bytes()) for h in ROOTS)


def test_every_skill_has_a_budget_and_no_budget_is_orphaned():
    assert sorted(BUDGET) == SKILLS


@pytest.mark.parametrize("name", SKILLS)
@pytest.mark.parametrize("harness", sorted(ROOTS))
def test_each_copy_is_under_its_cap(name, harness):
    cap, _ = BUDGET[name]
    size = len((folder(harness, name) / "SKILL.md").read_bytes())
    assert size <= cap, (
        f"{size} bytes over a cap of {cap}: move prose to references/; commands "
        "stay in SKILL.md. Or raise the cap in this table with a reason"
    )


@pytest.mark.parametrize("name", SKILLS)
def test_no_cap_keeps_more_than_the_slack(name):
    cap, _ = BUDGET[name]
    size = largest_copy(name)
    assert cap - size <= SLACK, f"lower the cap to {-(-size // 1_000) * 1_000}"


@pytest.mark.parametrize("name", SKILLS)
def test_a_cap_above_its_target_says_why(name):
    cap, reason = BUDGET[name]
    if cap > target(name):
        assert reason, f"{name}'s cap of {cap} is above its {target(name)} target"
    else:
        assert reason is None, "a cap at or under its target needs no reason"

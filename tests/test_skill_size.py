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
    "agenda-reviser": (29_000, "draft diff closing step"),
    "book-assembler": (20_000, _LATER),
    "corpus-reviser": (13_000, _LATER),
    "deep-research": (41_000, _LATER),
    "demo-recorder": (6_000, None),
    "draft-reviser": (30_000, "draft diff closing step"),
    "figure-drawer": (7_000, None),
    "review-digest": (17_000, _LATER),
    "survey-writer": (32_000, _LATER),
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
        f"{size} bytes over a cap of {cap}: move prose to references/, "
        "or raise the cap in this table with a reason"
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

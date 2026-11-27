import pytest

from tests.test_skill_harness_copies import ROOTS, SKILLS, folder

GENRE_TARGET = 12_000
OTHER_TARGET = 8_000
SLACK = 1_000
GENRES = {
    "review-digest",
    "survey-writer",
    "textbook-chapter-writer",
    "thesis-chapter-writer",
    "tutorial-writer",
}
_LATER = "#1091: shrinks to its target in its own PR"

BUDGET = {
    "agenda-reviser": (
        19_500,
        "#1174: +500 for the person-requested quote: exception. "
        "#1091: deduplicated from 28 KB; it runs unattended repairs, so every "
        "guardrail stays inline beside its command, and the rest is commands and "
        "tested text (plans/1091-ledger-agenda-reviser.md)",
    ),
    "ai-images": (5_000, None),
    "book-assembler": (
        14_000,
        "#1091: deduplicated from 20 KB into book-steps.md and latex-conventions.md; "
        "the rest is ten steps' commands, the guardrails and their pointers, and the "
        "target is a guideline (plans/1091-skill-shrink.md, Decision 1)",
    ),
    "corpus-reviser": (
        11_500,
        "#1091: deduplicated from 12.8 KB; it states only how its pass differs from "
        "draft-reviser's loop, and the rest is its guardrails, routing table, three "
        "closing steps' commands and tested text (plans/1091-ledger-corpus-reviser.md)",
    ),
    "deep-research": (
        20_000,
        "#1091: deduplicated from 41 KB against genre-steps, its agents' own files "
        "and report.md, the critique loop behind its pointer; seven phases of "
        "dispatch packets, transcription and commands remain, and the target is "
        "a guideline (plans/1091-skill-shrink.md, Decision 1)",
    ),
    "demo-recorder": (6_000, None),
    "draft-reviser": (
        23_500,
        "#1174: +500 for the person-requested quote: line. "
        "#1091: deduplicated from 29 KB; agenda-reviser and corpus-reviser follow "
        "its loop by step number, so every step stays complete inline, and the "
        "rest is commands and tested text (plans/1091-ledger-draft-reviser.md)",
    ),
    "figure-drawer": (7_500, None),
    "review-digest": (
        17_000,
        "#1091: deduplicated, then the six passages #1173 cut restored; the rest is "
        "commands, the digest format and tested text, and the target is a guideline "
        "(plans/1091-skill-shrink.md, Decision 1)",
    ),
    "skill-bench": (5_000, None),
    "survey-writer": (
        14_000,
        "#1091: deduplicated from 32 KB, then the critique loop moved behind its "
        "pointer; the rest is commands and tested text, and the target is a "
        "guideline (plans/1091-skill-shrink.md, Decision 1)",
    ),
    "textbook-chapter-writer": (
        16_000,
        "#1091: deduplicated from 32 KB, with the critique loop behind its pointer; "
        "the rest is commands, tested text and the steps an optional-citation genre "
        "adds, and the target is a guideline (plans/1091-skill-shrink.md, Decision 1)",
    ),
    "thesis-chapter-writer": (
        15_000,
        "#1091: deduplicated from 34 KB with the critique loop behind its pointer; "
        "the rest is commands, the figure stub and tested text, and the target is a "
        "guideline (plans/1091-skill-shrink.md, Decision 1)",
    ),
    "tutorial-writer": (
        17_000,
        "#1091: deduplicated from 34 KB, critique loop behind its pointer; the "
        "rest is commands, the run-it step and tested text, and the target is a "
        "guideline (plans/1091-skill-shrink.md, Decision 1)",
    ),
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

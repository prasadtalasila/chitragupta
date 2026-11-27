import re
from pathlib import Path

import pytest

from chitragupta import review
from chitragupta.draft import VERBS as DRAFT_VERBS
from tests.test_skill_harness_copies import USER_SKILLS

REPO_ROOT = Path(__file__).resolve().parent.parent
FEATURES = REPO_ROOT / "docs" / "FEATURES.md"
FEATURES_TEXT = FEATURES.read_text(encoding="utf-8")

SKILLS = USER_SKILLS

_NUMBER_WORDS = {
    1: "One",
    2: "Two",
    3: "Three",
    4: "Four",
    5: "Five",
    6: "Six",
    7: "Seven",
    8: "Eight",
    9: "Nine",
    10: "Ten",
    11: "Eleven",
    12: "Twelve",
}


class TestTheScanIsNotVacuous:
    def test_the_document_exists_and_has_content(self):
        assert len(FEATURES_TEXT) > 2000

    def test_there_are_aids_verbs_and_skills_to_check(self):
        assert len(review.AIDS) >= 3
        assert len(DRAFT_VERBS) >= 5
        assert len(SKILLS) >= 5


class TestEveryReviewAidIsListed:
    @pytest.mark.parametrize("aid", sorted(review.AIDS))
    def test_it_is_named(self, aid):
        assert f"review {aid}" in FEATURES_TEXT, (
            f"docs/FEATURES.md does not mention `review {aid}`. It is in "
            "chitragupta/review/__init__.py's AIDS, so the features document "
            "is now incomplete -- the drift #345 was filed for, one file over."
        )

    def test_the_stated_aid_count_matches(self):
        expected = _NUMBER_WORDS[len(review.AIDS)]
        assert f"{expected} advisory aids" in FEATURES_TEXT, (
            f"docs/FEATURES.md's review section should say '{expected} advisory "
            f"aids' -- AIDS has {len(review.AIDS)} entries."
        )


class TestEveryDraftingVerbIsListed:
    @pytest.mark.parametrize("verb", sorted(DRAFT_VERBS))
    def test_it_is_named(self, verb):
        assert f"draft {verb}" in FEATURES_TEXT, (
            f"docs/FEATURES.md does not mention `draft {verb}`, which "
            "chitragupta/draft.py's VERBS declares."
        )


class TestEverySkillIsListed:
    @pytest.mark.parametrize("skill", SKILLS)
    def test_it_is_named(self, skill):
        assert f"`{skill}`" in FEATURES_TEXT, (
            f"docs/FEATURES.md does not name the `{skill}` skill. Every "
            "directory under .claude/skills/ is a skill a user can trigger."
        )

    def test_the_stated_skill_count_matches(self):
        expected = _NUMBER_WORDS[len(SKILLS)]
        pattern = re.compile(rf"^### (?:[^\x00-\x7F]+ )?{expected} skills$", re.MULTILINE)
        assert pattern.search(FEATURES_TEXT), (
            f"docs/FEATURES.md's skills heading should read '### {expected} "
            f"skills' -- .claude/skills/ holds {len(SKILLS)}: "
            f"{', '.join(SKILLS)}."
        )


class TestTheDocumentRoutesRatherThanRestates:
    def test_it_links_to_the_documents_it_defers_to(self):
        for owner in (
            "CLI.md",
            "ARCHITECTURE.md",
            "GENRE.md",
            "DOSSIER.md",
            "REVIEW.md",
            "DIAGRAMS.md",
            "SOUL.md",
        ):
            assert f"({owner})" in FEATURES_TEXT or f"/{owner})" in FEATURES_TEXT, (
                f"docs/FEATURES.md no longer links to {owner}."
            )

    def test_every_relative_link_target_exists(self):
        missing = []
        for target in re.findall(r"\]\((?!https?:)([^)#]+)(?:#[^)]*)?\)", FEATURES_TEXT):
            if not (FEATURES.parent / target).resolve().exists():
                missing.append(target)
        assert not missing, f"docs/FEATURES.md links to missing files: {missing}"

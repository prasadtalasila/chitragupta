"""docs/FEATURES.md, held to the code it describes.

A comprehensive features document is the single most likely place for the
next occurrence of the bug this file's neighbours were written for: a
document restating a structure by hand and drifting from it (#345 for
`docs/ARCHITECTURE.md`, #348 for `docs/PACKAGING.md`). FEATURES.md names
every review aid, every drafting verb and every skill, so it has three
lists to go stale instead of one.

So it arrives pinned rather than trusted. The sources of truth are
`chitragupta/review/__init__.py`'s `AIDS`, `chitragupta/draft.py`'s
`VERBS`, and the `.claude/skills/` directory itself -- never a literal
retyped here.

**This checks presence and counts, not prose.** A features document is
mostly judgement about what to emphasise, and a test that pinned wording
would be one nobody could keep green. What it can check is the part that
is mechanically true or false: whether every capability the code has is
mentioned, and whether a stated total matches what it counts.
"""

import re
from pathlib import Path

import pytest

from chitragupta import review
from chitragupta.draft import VERBS as DRAFT_VERBS

REPO_ROOT = Path(__file__).resolve().parent.parent
FEATURES = REPO_ROOT / "docs" / "FEATURES.md"
FEATURES_TEXT = FEATURES.read_text(encoding="utf-8")

SKILLS = sorted(p.name for p in (REPO_ROOT / ".claude" / "skills").iterdir() if p.is_dir())

_NUMBER_WORDS = {
    1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five",
    6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
}


class TestTheScanIsNotVacuous:
    """Every list below is derived, so an empty source would make the
    whole module pass while checking nothing.
    """

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
        assert f"### {expected} skills" in FEATURES_TEXT, (
            f"docs/FEATURES.md's skills heading should read '### {expected} "
            f"skills' -- .claude/skills/ holds {len(SKILLS)}: "
            f"{', '.join(SKILLS)}."
        )


class TestTheDocumentRoutesRatherThanRestates:
    """FEATURES.md's own stated constraint, kept honest.

    It promises to name the document that owns each feature's detail. A
    features document that stopped linking out would be one that had
    started restating -- which is the failure it says it exists to avoid.
    """

    def test_it_links_to_the_documents_it_defers_to(self):
        # DOSSIER.md and REVIEW.md are the two this file most has to
        # defer to: they own the detail it used to carry inline, and a
        # FEATURES.md that stopped pointing at them would be one that had
        # started restating them again.
        for owner in ("CLI.md", "ARCHITECTURE.md", "GENRE.md", "DOSSIER.md",
                      "REVIEW.md", "DIAGRAMS.md", "SOUL.md"):
            assert f"({owner})" in FEATURES_TEXT or f"/{owner})" in FEATURES_TEXT, (
                f"docs/FEATURES.md no longer links to {owner}."
            )

    def test_every_relative_link_target_exists(self):
        # mkdocs --strict catches these at build time, but only for files
        # in the nav; this is the cheap direct check and it names the
        # missing file rather than a rendered path.
        missing = []
        for target in re.findall(r"\]\((?!https?:)([^)#]+)(?:#[^)]*)?\)", FEATURES_TEXT):
            if not (FEATURES.parent / target).resolve().exists():
                missing.append(target)
        assert not missing, f"docs/FEATURES.md links to missing files: {missing}"

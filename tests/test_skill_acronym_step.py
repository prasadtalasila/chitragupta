import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"

_GENRE_SKILLS = (
    "survey-writer",
    "thesis-chapter-writer",
    "textbook-chapter-writer",
    "tutorial-writer",
    "deep-research",
)

_MENTIONS_THE_VOCABULARY = re.compile(r"acronyms?\.toml|acronym vocabulary", re.IGNORECASE)


def test_every_genre_skill_mentions_the_acronym_vocabulary():
    missing = [
        name
        for name in _GENRE_SKILLS
        if not _MENTIONS_THE_VOCABULARY.search(
            (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
        )
    ]
    assert not missing, f"step 0 acronym-vocabulary sentence missing from: {missing}"

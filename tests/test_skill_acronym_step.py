"""Every genre skill's step 0 reads the acronym vocabulary, not only the
dialect.

#190: an author's own acronym expansions should travel from one draft to
the next the same way the dialect already does
(docs/WRITING-STANDARDS.md §8) -- a skill file edited by hand later that
drops the sentence is a silent regression this text-scan catches. It does
not exercise the loader's own behaviour; src/acronyms.py and
src/dossier.py::glossary_terms have that (tests/test_acronyms.py,
tests/test_dossier.py::TestGlossaryTerms).
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"

# The five genre-writing skills docs/GENRE.md names -- not the revision
# skills (draft-reviser, corpus-reviser, overlap-reviser), which don't
# call `dossier init` and have no step 0 of this kind.
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

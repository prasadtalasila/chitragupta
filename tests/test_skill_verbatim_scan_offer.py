"""Every drafting skill must offer the verbatim scan, and must say what
it misses in the same breath.

docs/GENRE.md states this as a shared invariant, in the same section and
the same voice as "the gate is the only exit" and "the corpus is
read-only": *"These are not per-skill choices. They are the same rules
restated in six files, and a skill that broke one would be the bug."*
Nothing enforced it. A skill file edited by hand could lose the offer,
or a new skill could land without it, and the only thing that would
notice is a reader comparing seven files by eye.

Two halves, and the second is the one worth having. The offer alone is
a command; the caveat is what stops a clean result being read as a clean
bill of health. `scan` runs two deterministic tiers of a detection stack
whose embedding tier is unbuilt (docs/PLAGIARISM.md,
docs/LADDERS.md#the-one-stack): exact runs, and skip-gram matches
tolerant of a substituted word. Genuine restatement -- reworded well
past a word swap, the reuse mode neither deterministic tier can see --
is still invisible, and the drafts these skills produce are LLM-written,
so that is the *likely* failure mode. The skill file is the only place
the drafter reads, which makes it the only place the caveat can reach
the one whose habit it is about.

A text scan over `.claude/skills/`, in the shape of
tests/test_skill_retrieval_logging.py, and for the same reason: what the
command actually does has its own tests in
tests/test_verbatim_check.py and tests/test_feature_workflows.py. This
pins only that the skills still tell anyone to run it.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
GENRE_DOC = REPO_ROOT / "docs" / "GENRE.md"

_OFFER = re.compile(r"-m src\.review verbatim scan\b")

# The caveat has to travel with the offer, not merely exist somewhere in
# the file -- a skill that mentions paraphrase in an unrelated paragraph
# has not warned the drafter about this command. Measured against all
# seven files: the furthest any caveat sits from its offer is ~600
# characters, and the offers are the last step in each file, so a
# window this size cannot reach a *different* offer's caveat.
_LOOKAHEAD_CHARS = 900
_CAVEAT = "genuine restatement is not detected"


def _skill_files():
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def _normalised(path):
    """Whitespace collapsed, because these files are hand-wrapped.

    Without this the check is really a check on where someone's editor
    broke the line: `**paraphrase is not\\n    detected**` is the same
    sentence as the unwrapped form and must not read as a missing
    caveat. That is not hypothetical -- it was the state of
    textbook-chapter-writer when this test was written.
    """
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def test_every_drafting_skill_offers_the_verbatim_scan():
    files = _skill_files()
    assert files, "expected to find SKILL.md files under .claude/skills/"

    missing = [p.parent.name for p in files if not _OFFER.search(_normalised(p))]
    assert not missing, (
        "these skills never mention `-m src.review verbatim scan`, so a draft they "
        f"produce is presented with nobody told the check exists: {missing}. "
        "docs/GENRE.md's \"What all seven have in common\" claims otherwise."
    )


def test_every_offer_says_what_the_scan_cannot_see():
    """The offer without the caveat is worse than no offer: it converts
    an open question into a false all-clear."""
    offenders = {}
    for path in _skill_files():
        text = _normalised(path)
        for match in _OFFER.finditer(text):
            window = text[match.start(): match.start() + _LOOKAHEAD_CHARS]
            if _CAVEAT not in window:
                offenders.setdefault(path.parent.name, []).append(match.start())

    assert not offenders, (
        f"`-m src.review verbatim scan` is offered without {_CAVEAT!r} nearby in "
        f"{sorted(offenders)}. Neither deterministic tier can see genuine "
        "restatement, and these drafts are LLM-written, so a clean run must "
        "never be presented as a clean bill of health -- see docs/PLAGIARISM.md."
    )


def test_genre_doc_still_speaks_for_every_skill_that_exists():
    """docs/GENRE.md says "all eight" in prose. Prose can't count.

    If a ninth skill lands, the shared-conventions section silently
    stops covering it -- and that section is where the scan offer, the
    gate and the read-only-corpus rules are stated once for all of them.
    This fails on the day the count changes, which is the day GENRE.md
    needs editing anyway.
    """
    count = len(_skill_files())
    assert count == 8, (
        f"{count} skills exist but docs/GENRE.md still says \"all eight\". "
        "Update that section -- and check the new skill carries the gate, "
        "dossier and verbatim-scan conventions it states."
    )
    assert "What all eight have in common" in GENRE_DOC.read_text(encoding="utf-8")

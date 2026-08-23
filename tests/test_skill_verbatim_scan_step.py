"""Every drafting skill must run the verbatim scan, regenerate the
section map first, and say what the scan could not check.

docs/GENRE.md states this as a shared invariant, in the same section and
the same voice as "the gate is the only exit" and "the corpus is
read-only": *"These are not per-skill choices. They are the same rules
restated in six files, and a skill that broke one would be the bug."*
Nothing enforced it. A skill file edited by hand could lose the step, or
a new skill could land without it, and the only thing that would notice
is a reader comparing nine files by eye.

**The scan runs; it is still not a gate.** Until #312 the step was an
*offer* -- "before presenting, offer this, don't run" -- so the only
defence against verbatim reuse was post-hoc and optional, and a draft
could be presented having never been scanned. What changed is who may
invoke a review aid, not what one may do: the surviving invariant is
that a finding may be read, may be invoked by a driver, and may never
block a draft. `python -m chitragupta.draft gate` remains the only gate,
and `test_no_skill_makes_the_scan_a_condition_of_presenting` below is
what keeps that true as these files are edited.

Four halves, and the last two are the ones worth having.

The **step** alone is a command. The **caveat** is what stops a clean
result being read as a clean bill of health: `scan` runs three detection
tiers (docs/PLAGIARISM.md, docs/LADDERS.md#the-one-stack) -- exact runs,
skip-gram matches tolerant of a substituted word, and an embedding tier
that does see genuine restatement.

That third tier is why the other two checks exist. It runs only where the
optional enrichment layer, the Docling passage sidecars and the draft's
own dossier are all present, which is not the state of an ordinary
checkout. So the caveat pinned below stays *conditional* rather than
absolute -- the drafts these skills produce are LLM-written, restatement
is therefore the likely failure mode, and a skill promising coverage the
reader's host cannot deliver would be worse than the unconditional
warning it replaced.

The **regeneration** is the one precondition a skill can actually fix.
Of that tier's four unavailability reasons, exactly one is in a skill's
gift: a dossier whose `sections.md` records no citekeys. `dossier
sections --citekeys --write` derives that table from the draft, so
running it immediately before the scan is what makes the tier able to
run at all -- and running it *immediately* before is what stops the table
describing the draft as it was ten steps ago.

The **`tiers_not_run` report** is what makes the remaining three
honest. A two-of-three-tier scan that reads clean is worse than no scan,
because it looks like an answer.

A text scan over `.claude/skills/`, in the shape of
tests/test_skill_retrieval_logging.py, and for the same reason: what the
command actually does has its own tests in tests/test_verbatim_check.py
and tests/test_feature_workflows.py. This pins only that the skills still
tell anyone to run it.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
GENRE_DOC = REPO_ROOT / "docs" / "GENRE.md"

_SCAN = re.compile(r"-m chitragupta\.review verbatim scan\b")

# The caveat has to travel with the command, not merely exist somewhere
# in the file -- a skill that mentions paraphrase in an unrelated
# paragraph has not warned the drafter about this command. Measured
# against all nine files: the furthest any caveat sits from a mention of
# the command is 1542 characters, in `draft-reviser`, whose step explains
# why a revision in particular invalidates the section map before it gets
# to what the scan cannot see.
_LOOKAHEAD_CHARS = 1700
_CAVEAT = "genuine restatement is only detected where the embedding tier can run"

# What the skill must report when a tier was skipped. The payload key
# itself, because that is what the reader has to be shown: paraphrasing
# it loses the reason, and the reasons are written to be read by a person
# mid-review (`overlap_embed.unavailable_reason`: "the four ways this
# tier is unavailable want four different fixes").
_TIERS = "tiers_not_run"

# `--citekeys --write` and nothing looser: the bare `dossier sections`
# form prints an outline and writes nothing, and several skills already
# use it that way for a different purpose. Only the writing form
# populates the table tier 3 reads. The gap allows the backslash line
# continuation `deep-research` wraps this command with, but not a
# backtick, so it cannot span out of one fenced block and into the next.
_REGEN = re.compile(r"-m chitragupta\.draft dossier sections[^`]{0,160}?--citekeys --write")

# **The step block is anchored on the regeneration, not on the scan.**
# Four of the nine files mention `verbatim scan` somewhere other than the
# step -- `overlap-reviser` alone does it four times, once in its own
# frontmatter description, because reading that report is its whole
# subject. Anchoring on the scan would demand a `tiers_not_run` sentence
# in a skill description, which is the wrong place for it. The
# regeneration command appears only in the step, which makes it the
# reliable anchor.
#
# Measured: the scan follows the regeneration by 86-105 characters in
# every skill, because they are two lines of one fenced block. 200 is
# that with room for a longer draft path, and far too little to reach
# anything else.
_STEP_SPAN_CHARS = 200

# From the same anchor, how far the step may run before it has said what
# it could not check. Measured max is 1303 characters (`draft-reviser`).
_STEP_TAIL_CHARS = 1700

# The clause that keeps this a review aid rather than a gate. It is the
# tripwire for the whole change: a skill that made the scan a condition
# of presenting would have promoted a review finding to a blocker, which
# the amendment did not authorise and SOUL.md forbids.
_NOT_A_CONDITION = "never a condition of presenting"

# The word the step used to be built on. Pinned as an absence so the old
# posture cannot come back one file at a time.
_OLD_OFFER = re.compile(r"Offer the verbatim scan", re.I)


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


def test_every_drafting_skill_runs_the_verbatim_scan():
    files = _skill_files()
    assert files, "expected to find SKILL.md files under .claude/skills/"

    missing = [p.parent.name for p in files if not _SCAN.search(_normalised(p))]
    assert not missing, (
        "these skills never mention `-m chitragupta.review verbatim scan`, so a draft they "
        f"produce is presented with nobody told the check exists: {missing}. "
        'docs/GENRE.md\'s "What all nine have in common" claims otherwise.'
    )


def test_no_skill_still_only_offers_the_scan():
    """#312 flipped the step from offered to run. The old heading is
    pinned as an absence because the regression is silent: a skill that
    goes back to offering still passes every other check in this file,
    and the draft it presents was never scanned."""
    offenders = sorted(p.parent.name for p in _skill_files() if _OLD_OFFER.search(_normalised(p)))
    assert not offenders, (
        f'these skills still say "Offer the verbatim scan": {offenders}. '
        'The scan runs before presenting -- see docs/GENRE.md, "The verbatim '
        'scan is run, reported, and never a gate".'
    )


def test_every_scan_says_what_it_cannot_see():
    """The step without the caveat is worse than no step: it converts an
    open question into a false all-clear."""
    offenders = {}
    for path in _skill_files():
        text = _normalised(path)
        for match in _SCAN.finditer(text):
            window = text[match.start() : match.start() + _LOOKAHEAD_CHARS]
            if _CAVEAT not in window:
                offenders.setdefault(path.parent.name, []).append(match.start())

    assert not offenders, (
        f"`-m chitragupta.review verbatim scan` appears without {_CAVEAT!r} nearby in "
        f"{sorted(offenders)}. The embedding tier is the only one that sees "
        "genuine restatement and it does not run on every host, while these "
        "drafts are LLM-written -- so a clean run must never be presented as a "
        "clean bill of health. See docs/PLAGIARISM.md."
    )


def _step_blocks(text):
    """(start, end) of each scan step, anchored on its regeneration.

    A step is the regeneration command plus what follows it, and it
    counts as a step only if the scan command comes straight after --
    which is what makes this a step rather than a `sections` call
    somewhere else in the run.
    """
    for match in _REGEN.finditer(text):
        head = text[match.start() : match.start() + _STEP_SPAN_CHARS]
        if _SCAN.search(head):
            yield match.start(), match.start() + _STEP_TAIL_CHARS


def test_every_skill_rebuilds_the_section_map_before_scanning():
    """Tier 3 reads the dossier's `sections.md`, and a skill that does
    not rebuild it scans against whatever was last written.

    This is the one of tier 3's four unavailability reasons a skill can
    do anything about, which is why it is pinned here rather than left to
    each genre. Five skills already wrote that table mid-run and four
    never wrote it at all; neither is enough, because a draft edited
    after the write is scanned against a table describing the draft
    before it.
    """
    offenders = sorted(
        path.parent.name for path in _skill_files() if not list(_step_blocks(_normalised(path)))
    )
    assert not offenders, (
        "no `dossier sections --citekeys --write` immediately before "
        f"`verbatim scan` in {offenders}. Tier 3 -- the only tier that sees "
        "genuine restatement -- compares each section against the citekeys "
        "that section's `sections.md` row records, so an unwritten or stale "
        "table silently reduces the scan to two tiers of three."
    )


def test_every_scan_step_reports_the_tiers_it_could_not_run():
    """A scan that skipped a tier and says so is evidence; one that
    skipped a tier silently is a false all-clear with a command behind
    it."""
    offenders = {}
    for path in _skill_files():
        text = _normalised(path)
        for start, end in _step_blocks(text):
            if _TIERS not in text[start:end]:
                offenders.setdefault(path.parent.name, []).append(start)

    assert not offenders, (
        f"a scan step runs without mentioning {_TIERS!r} in "
        f"{sorted(offenders)}. Three of tier 3's four unavailability reasons "
        "are not a skill's to fix, so the only honest answer is to quote the "
        "reason the scan gave and pass on the fix it names."
    )


def test_no_skill_makes_the_scan_a_condition_of_presenting():
    """The scan runs, and it still cannot block a draft.

    `chitragupta.draft gate` is the only gate. This is the sentence that
    says so in the one file a drafter actually reads, and it is the
    clause the amendment behind #312 deliberately preserved -- advisory
    versus blocking, not manual versus automatic.
    """
    offenders = sorted(
        p.parent.name
        for p in _skill_files()
        if _SCAN.search(_normalised(p)) and _NOT_A_CONDITION not in _normalised(p)
    )
    assert not offenders, (
        f"these skills run the scan without saying it is {_NOT_A_CONDITION!r}: "
        f"{offenders}. A review aid that gains a mandatory step is one careless "
        "edit away from being read as a gate; SOUL.md forbids promoting one."
    )


def test_genre_doc_still_speaks_for_every_skill_that_exists():
    """docs/GENRE.md says "all nine" in prose. Prose can't count.

    If a tenth skill lands, the shared-conventions section silently
    stops covering it -- and that section is where the scan step, the
    gate and the read-only-corpus rules are stated once for all of them.
    This fails on the day the count changes, which is the day GENRE.md
    needs editing anyway. It has already done its job once: it caught
    `book-assembler` landing in #139 while that section still said
    eight.
    """
    count = len(_skill_files())
    assert count == 9, (
        f'{count} skills exist but docs/GENRE.md still says "all nine". '
        "Update that section -- and check the new skill carries the gate, "
        "dossier and verbatim-scan conventions it states."
    )
    assert "What all nine have in common" in GENRE_DOC.read_text(encoding="utf-8")

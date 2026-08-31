"""The five genre skills must critique a draft against its evidence
packet before gating, with a single-shot repair bounded by an external,
deterministic acceptance test -- never the skill's own opinion of its
own edit.

B5 (docs/FEATURE-ROADMAP.md, plans/b5-pregate-self-feedback.md). Modeled
on tests/test_skill_verbatim_scan_step.py, which pins #312's shared step
the same way: a text scan over `.claude/skills/`, because what the
commands this step calls actually do has its own tests
(tests/test_citation_gate.py, tests/test_verbatim_check.py,
tests/test_style_check.py). This file pins only that the five skills
still tell anyone to run the step, in the shape the plan specifies.

**Five, not nine.** Unlike the verbatim scan (shared by all nine), this
step belongs only to the skills that draft fresh prose from a
`claim:`/`quote:` evidence packet: `survey-writer`,
`thesis-chapter-writer`, `textbook-chapter-writer`, `tutorial-writer`,
`deep-research`. `book-assembler` writes no prose of its own;
`draft-reviser`, `corpus-reviser` and `agenda-reviser` already
gate-and-recheck per section rather than critiquing a whole fresh
draft. `test_only_the_five_genre_skills_carry_the_step` below is what
keeps a future edit from copying the step into the wrong file by habit,
or dropping it from one of the five.

**Why the acceptance test matters more than the critique itself.** The
critique step is an inline judgement call -- nothing in this pipeline
scores it, and R3 (docs/AUTO-IMPROVEMENT.md) does not govern it. What
R3 and R4 govern is whether an edit born from that judgement call is
*kept*, and that has to be an external, deterministic count -- `gate`'s
exit code, `verbatim recheck`'s `objective_delta`, and `draft style`'s
finding count -- never the skill's own opinion that its edit is an
improvement. That is the one line separating this from A1b (declined),
so most of the tests below pin the acceptance machinery, not the prose
around it.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"

# The five skills this step belongs to -- drafting fresh prose from a
# claim:/quote: evidence packet, as distinct from a reviser (which edits
# an existing draft section by section) or book-assembler (writes no
# prose at all). docs/GENRE.md's "What all nine have in common" section
# states this same five-of-nine split in the same words.
_GENRE_SKILLS = {
    "survey-writer",
    "thesis-chapter-writer",
    "textbook-chapter-writer",
    "tutorial-writer",
    "deep-research",
}

# The four skills that must never carry this step -- checked by name,
# not merely "everything but the five," so a tenth skill landing later
# fails loudly here rather than silently joining whichever side of the
# split its file happens to sort into.
_EXCLUDED_SKILLS = {"draft-reviser", "corpus-reviser", "agenda-reviser", "book-assembler"}

_CRITIQUE = re.compile(r"[Cc]ritique against the evidence packet")

# How far the step may run from its anchor before it has said the
# acceptance test, the cap, the single-shot rule and the presenting
# clause. Measured max is 5649 characters (`deep-research`, which adds
# a paragraph distinguishing this from its own Phase 7 peer review, on
# top of the tier/decidability caveats every file carries near its two
# `verbatim scan`/`draft style` mentions). #481's two paragraphs -- the
# empty-result rule and the exhaustion report -- added ~1200 to every
# file, which is why this is 5900 rather than the 4300 it was: the
# window has to reach past them to the closing clause, or the tests
# below start passing because the sentence they check fell outside it.
_STEP_TAIL_CHARS = 5900

# The single-shot rule, stated once per step so a later edit cannot
# quietly turn this into a retry loop the way agenda-reviser's R7
# (two attempts per finding) is for a different mechanism.
_SINGLE_SHOT = "no second critique pass"

# The bound on how much work one pass may do.
_CAP = "at most three items"

# The three checks an edit must clear, all external and deterministic.
# `_GATE`/`_RECHECK`/`_STYLE` also appear in the baseline half of the
# step (taking the pre-edit count); this file only requires each to
# appear at least once, not to count occurrences, because the ordering
# test below is what actually pins the accept/revert shape.
_GATE = re.compile(r"-m chitragupta\.draft gate\b")
_RECHECK = re.compile(r"-m chitragupta\.review verbatim recheck\b")
_STYLE = re.compile(r"-m chitragupta\.draft style\b")
_SCAN = re.compile(r"-m chitragupta\.review verbatim scan\b")

# R4's count, made deterministic -- the acceptance test's load-bearing
# field. Its presence is what stops a future edit from replacing the
# check with a continuous score (the thing upstream did and R3 forbids).
_OBJECTIVE_DELTA = "objective_delta"

# The secondary sanity floor the issue keeps from upstream, and the
# sentence that has to say it is secondary -- never itself an
# acceptance criterion.
_LENGTH_FLOOR = "90% of its own"

# The logging contract: every attempt in revisions.md, never in
# rejected.md (that file is about sources turned down, not repairs that
# didn't work -- see agenda-reviser's own step 6).
_REVISIONS = "revisions.md"
_REJECTED_EXCLUDED = "Never write any of this to `rejected.md`"

# #481's A4: the empty-result rule. `_NEVER_REPOINT` is the load-bearing
# half -- "cut the sentence" alone would leave re-pointing the citation
# at an adjacent citekey open, and that is the failure the gate
# structurally cannot see, because the citekey is real. `_STATUS` is
# pinned here rather than with the report below because the ordering is
# the point: the step has to read the `no evidence` split *before* the
# repair loop, or a gap it names cannot be acted on in the same pass.
_NO_EVIDENCE = "`no evidence`"
_CUT = "cut the sentence"
_NEVER_REPOINT = "never to re-point it"
_STATUS = "dossier status"

# #481's A3: the exhaustion report. `_NO_OUTLINE` pins the absent case --
# outline.md is optional (#455), and a draft without one has no declared
# list, so the step must say nothing rather than report a vacuous
# "exhausted".
_EXHAUSTED = "declared queries are exhausted"
_NO_OUTLINE = "there is no declared list"


# The clause that keeps this a repair pass rather than a gate -- the
# same invariant test_skill_verbatim_scan_step.py pins for a different
# shared step, and for the same reason: SOUL.md forbids promoting a
# review-shaped step to a blocker.
_NOT_A_CONDITION = "never a condition of presenting"


def _skill_files():
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def _normalised(path):
    """Whitespace collapsed -- these files are hand-wrapped, and a
    phrase broken across a line by an editor is still the same
    sentence."""
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def _genre_skill_files():
    return [p for p in _skill_files() if p.parent.name in _GENRE_SKILLS]


def test_only_the_five_genre_skills_carry_the_step():
    present = {p.parent.name for p in _skill_files() if _CRITIQUE.search(_normalised(p))}
    missing = _GENRE_SKILLS - present
    extra = present - _GENRE_SKILLS
    assert not missing, (
        f"these genre skills never mention the pre-gate critique step: {sorted(missing)}. "
        "docs/GENRE.md's five-of-nine note claims otherwise."
    )
    assert not extra, (
        f"these skills carry the pre-gate critique step and should not: {sorted(extra)}. "
        "It belongs only to the five genre skills that draft fresh prose from an "
        "evidence packet -- a reviser already gate-and-rechecks per section, and "
        "book-assembler writes no prose of its own."
    )


def _step_blocks(text):
    """(start, end) of each critique step, anchored on its own heading."""
    for match in _CRITIQUE.finditer(text):
        yield match.start(), match.start() + _STEP_TAIL_CHARS


def test_every_step_names_the_evidence_packet_and_the_claim_field():
    offenders = []
    for path in _genre_skill_files():
        text = _normalised(path)
        for start, end in _step_blocks(text):
            window = text[start:end]
            if "evidence.md" not in window or "claim:" not in window:
                offenders.append(path.parent.name)
    assert not offenders, (
        f"the critique step in {sorted(offenders)} does not name both `evidence.md` and "
        "`claim:` -- without them the step has nothing to critique the draft against."
    )


def test_every_step_is_capped_and_single_shot():
    offenders = {}
    for path in _genre_skill_files():
        text = _normalised(path)
        for start, end in _step_blocks(text):
            window = text[start:end]
            missing = [phrase for phrase in (_CAP, _SINGLE_SHOT) if phrase not in window]
            if missing:
                offenders.setdefault(path.parent.name, []).extend(missing)
    assert not offenders, (
        f"the critique step is missing its bound in {offenders}. Without {_CAP!r} and "
        f"{_SINGLE_SHOT!r} stated together, a future edit could turn this into an "
        "unbounded retry loop -- exactly what the issue calls smaller than 'loop' suggests."
    )


def test_every_step_checks_gate_then_recheck_before_style_reappears():
    """The accept/revert order matters: the baseline is taken (scan,
    then style's count) before any edit, and each edit is checked
    against gate, then the verbatim recheck, before the step's closing
    clause. Conflating the per-edit gate call with the genre skill's own
    later "Gate before presenting" step is the one mistake this test
    exists to catch."""
    offenders = []
    for path in _genre_skill_files():
        text = _normalised(path)
        for start, end in _step_blocks(text):
            window = text[start:end]
            scan_m = _SCAN.search(window)
            gate_m = _GATE.search(window)
            recheck_m = _RECHECK.search(window)
            style_m = _STYLE.search(window)
            if not (scan_m and gate_m and recheck_m and style_m):
                offenders.append((path.parent.name, "missing a required command"))
                continue
            if not scan_m.start() < gate_m.start() < recheck_m.start():
                offenders.append((path.parent.name, "out of order"))
    assert not offenders, (
        f"the critique step's commands are missing or out of order in {offenders}: "
        "expected the baseline `verbatim scan` before the per-edit `gate`, before the "
        "per-edit `verbatim recheck`, all within the same step."
    )


def test_every_step_s_acceptance_test_is_external_and_deterministic():
    offenders = {}
    for path in _genre_skill_files():
        text = _normalised(path)
        for start, end in _step_blocks(text):
            window = text[start:end]
            missing = [
                phrase for phrase in (_OBJECTIVE_DELTA, _LENGTH_FLOOR) if phrase not in window
            ]
            if missing:
                offenders.setdefault(path.parent.name, []).extend(missing)
    assert not offenders, (
        f"the acceptance test is incomplete in {offenders}. `{_OBJECTIVE_DELTA}` is R4's "
        f"count made deterministic; `{_LENGTH_FLOOR}` is the secondary sanity floor the "
        "issue keeps from upstream -- dropping either reopens the self-marking objection "
        "this step exists to avoid (docs/FEATURE-ROADMAP.md's B5 entry)."
    )


def test_every_step_logs_to_revisions_md_and_never_to_rejected_md():
    offenders = {}
    for path in _genre_skill_files():
        text = _normalised(path)
        for start, end in _step_blocks(text):
            window = text[start:end]
            missing = [
                phrase for phrase in (_REVISIONS, _REJECTED_EXCLUDED) if phrase not in window
            ]
            if missing:
                offenders.setdefault(path.parent.name, []).extend(missing)
    assert not offenders, (
        f"the logging contract is incomplete in {offenders}. A repair that didn't work "
        "belongs in `revisions.md`, never in `rejected.md` -- that file is about sources "
        "turned down, not repairs that failed."
    )


def test_every_step_says_an_empty_result_means_cutting_the_sentence():
    """#481's A4. A sub-theme the corpus cannot answer is the one gap
    class whose repair is a deletion, and the clause that matters is the
    prohibition beside it: re-pointing the sentence at whichever citekey
    ranked nearest is invisible to the gate, because that citekey is
    real."""
    offenders = {}
    for path in _genre_skill_files():
        text = _normalised(path)
        for start, end in _step_blocks(text):
            window = text[start:end]
            missing = [
                phrase for phrase in (_NO_EVIDENCE, _CUT, _NEVER_REPOINT) if phrase not in window
            ]
            if missing:
                offenders.setdefault(path.parent.name, []).extend(missing)
    assert not offenders, (
        f"the empty-result rule is incomplete in {offenders}. Without it a genre skill "
        "grounds a claim the corpus cannot support on whatever ranked nearest, and the "
        "gate cannot see it -- the citekey is real."
    )


def test_every_step_reports_exhaustion_without_making_it_a_bound():
    """#481's A3. The declared query list is finite, so exhaustion is a
    real termination condition rather than a round count -- but it is a
    *report*. A step that turned it into a bound on editing would undo
    the single-shot cap this file already pins, and one that made it a
    condition of presenting would be a second gate."""
    offenders = {}
    for path in _genre_skill_files():
        text = _normalised(path)
        for start, end in _step_blocks(text):
            window = text[start:end]
            missing = [
                phrase for phrase in (_EXHAUSTED, _STATUS, _NO_OUTLINE) if phrase not in window
            ]
            if missing:
                offenders.setdefault(path.parent.name, []).extend(missing)
    assert not offenders, (
        f"the exhaustion report is incomplete in {offenders}. `{_NO_OUTLINE}` is what "
        "keeps a dossier without an outline.md from reporting a vacuous 'exhausted'; the "
        "split it reads comes from `dossier status` (#480), pinned by the test above."
    )


def test_no_genre_skill_makes_the_step_a_condition_of_presenting():
    offenders = []
    for path in _genre_skill_files():
        text = _normalised(path)
        for start, end in _step_blocks(text):
            if _NOT_A_CONDITION not in text[start:end]:
                offenders.append(path.parent.name)
    assert not offenders, (
        f"the critique step in {offenders} does not say it is {_NOT_A_CONDITION!r}. "
        "`chitragupta.draft gate` remains the only gate; a review-shaped step that gains "
        "a mandatory outcome is one careless edit away from being read as a second one."
    )

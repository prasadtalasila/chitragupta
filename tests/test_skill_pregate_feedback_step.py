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

**Five, not ten.** Unlike the verbatim scan (shared by the nine that
present a draft), this step belongs only to the skills that draft
fresh prose from a `claim:`/`quote:` evidence packet: `survey-writer`,
`thesis-chapter-writer`, `textbook-chapter-writer`, `tutorial-writer`,
`deep-research`. `book-assembler` writes no prose of its own;
`draft-reviser`, `corpus-reviser` and `agenda-reviser` already
gate-and-recheck per section rather than critiquing a whole fresh
draft. `test_only_the_five_genre_skills_carry_the_step` below is what
keeps a future edit from copying the step into the wrong file by habit,
or dropping it from one of the five. `figure-drawer` presents no draft
at all, so it carries neither this step nor the scan (#1027).

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

Since #997 the repair loop lives once, in
`.claude/skills-common/references/critique.md`, which each genre's step
names after its own opening paragraph. `test_every_genre_step_names_the_reference`
pins the pointer itself. A step comes in one of two forms, and
`_POINTER_FORM` says which:

- **Inline**: the step names the reference and also carries the loop's
  commands, which `test_every_genre_step_keeps_its_commands_in_skill_md`
  requires. `_normalised` splices the reference in where it is named
  (tests/skill_text.py), so the windows below run from the step's heading
  through the rider a model following the pointer reads.
- **Pointer**: the step keeps its heading and what its genre lists, names
  the reference, says it is not done until the loop the reference
  describes has run, and carries no command. Measured before it was
  allowed: in the SK-0c experiment (plans/1091-skill-shrink.md, PR 0c;
  docs/HARNESS.md) 12 of 12 Claude Code runs held such a step, as the
  inline arm did. Its riders are read from the step and the whole
  reference, since a window measured through a spliced reference would
  test where the reference happens to put them, not whether they are
  there.

A skill moves from inline to pointer by joining `_POINTER_FORM`, in the
PR that converts its step.
"""

import re
from pathlib import Path

from tests.skill_text import collapsed, skill_text

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
REFERENCE = ".claude/skills-common/references/critique.md"

# How far after the step's heading its genre-specific opening paragraph
# may run before the step names the reference.
_POINTER_CHARS = 2000

# The five skills this step belongs to -- drafting fresh prose from a
# claim:/quote: evidence packet, as distinct from a reviser (which edits
# an existing draft section by section) or book-assembler (writes no
# prose at all). docs/GENRE.md's "What all eleven have in common" section
# states this same five-of-eleven split in the same words.
_GENRE_SKILLS = {
    "survey-writer",
    "thesis-chapter-writer",
    "textbook-chapter-writer",
    "tutorial-writer",
    "deep-research",
}

# The genre skills whose critique step is a pointer: it names the
# reference, says it is not done until the loop has run, and carries no
# command of the loop (see the module docstring). Every other genre skill
# keeps the commands inline. Each later PR that converts a skill moves it
# here, and nothing else in this file changes.
_POINTER_FORM = {"survey-writer", "textbook-chapter-writer", "thesis-chapter-writer", "tutorial-writer"}

# The sentence that makes a pointer step hold: without it, one Claude Code
# run in 2026-10 read a bare "read critique.md and follow it" and went
# straight to the gate (docs/HARNESS.md).
_NOT_DONE_UNTIL = "not done until the loop the reference describes has run"

# Where a pointer step ends: the "Done when" sentence every step closes on.
_DONE_WHEN = re.compile(r"Done when[^.]*\.")

# The six skills that must never carry this step -- checked by name,
# not merely "everything but the five," so a twelfth skill landing later
# fails loudly here rather than silently joining whichever side of the
# split its file happens to sort into. `review-digest` copies from the
# sources rather than drafting from a `claim:`/`quote:` packet (#991),
# so the critique loop has nothing to read; `review digest` replaces it.
_EXCLUDED_SKILLS = {
    "draft-reviser",
    "corpus-reviser",
    "agenda-reviser",
    "book-assembler",
    "figure-drawer",
    "review-digest",
}

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
# Re-measured with the shared reference spliced in (#997): the furthest
# rider then sat 5252 characters from its anchor, in `deep-research`.
# Re-measured again when the reference became the loop itself, six
# numbered steps each ending on a "Done when" (#1091): the furthest
# rider, "Never write any of this to `rejected.md`", sits 6398 characters
# from `deep-research`'s anchor, so the window is 6800. It applies to
# the inline form only; a pointer-form step is read whole (below).
_STEP_TAIL_CHARS = 6800

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
    sentence -- with the shared reference spliced in where it is named."""
    return skill_text(path)


def test_every_genre_step_names_the_reference():
    """The repair loop is one file read away, so the pointer is the step."""
    offenders = []
    for path in _genre_skill_files():
        text = collapsed(path.read_text(encoding="utf-8"))
        windows = [text[m.start() : m.start() + _POINTER_CHARS] for m in _CRITIQUE.finditer(text)]
        if not any(f"`{REFERENCE}`" in w for w in windows):
            offenders.append(path.parent.name)
    assert not offenders, f"no pointer to {REFERENCE} in the critique step of {offenders}"


def _genre_skill_files():
    return [p for p in _skill_files() if p.parent.name in _GENRE_SKILLS]


def test_only_the_five_genre_skills_carry_the_step():
    present = {p.parent.name for p in _skill_files() if _CRITIQUE.search(_normalised(p))}
    missing = _GENRE_SKILLS - present
    extra = present - _GENRE_SKILLS
    assert not missing, (
        f"these genre skills never mention the pre-gate critique step: {sorted(missing)}. "
        "docs/GENRE.md's five-of-ten note claims otherwise."
    )
    assert not extra, (
        f"these skills carry the pre-gate critique step and should not: {sorted(extra)}. "
        "It belongs only to the five genre skills that draft fresh prose from an "
        "evidence packet -- a reviser already gate-and-rechecks per section, and "
        "book-assembler writes no prose of its own."
    )


def _pointer_step(path):
    """A pointer-form step's own text, from its heading to the end of its
    `Done when` sentence, whitespace collapsed and nothing spliced."""
    text = collapsed(path.read_text(encoding="utf-8"))
    start = _CRITIQUE.search(text).start()
    done = _DONE_WHEN.search(text, start)
    assert done, f"{path.parent.name}: the critique step does not end on a `Done when`"
    return text[start : done.end()]


def _reference():
    return collapsed((REPO_ROOT / REFERENCE).read_text(encoding="utf-8"))


def _windows(path):
    """The text each rider must be found in, once per step.

    Inline form: a window of `_STEP_TAIL_CHARS` from each anchor, with the
    reference spliced in where it is named. Pointer form: the step itself
    followed by the whole reference, which is what a model following the
    pointer reads, and which holds every command and rider of the loop.
    """
    if path.parent.name in _POINTER_FORM:
        return [f"{_pointer_step(path)} {_reference()}"]
    text = _normalised(path)
    return [text[m.start() : m.start() + _STEP_TAIL_CHARS] for m in _CRITIQUE.finditer(text)]


def test_the_pointer_form_names_only_genre_skills():
    assert _POINTER_FORM <= _GENRE_SKILLS, sorted(_POINTER_FORM - _GENRE_SKILLS)


def _pointer_skill_files():
    return [p for p in _genre_skill_files() if p.parent.name in _POINTER_FORM]


def test_every_pointer_step_says_it_is_not_done_until_the_loop_has_run():
    offenders = [
        p.parent.name for p in _pointer_skill_files() if _NOT_DONE_UNTIL not in _pointer_step(p)
    ]
    assert not offenders, (
        f"the pointer-form critique step in {offenders} does not say {_NOT_DONE_UNTIL!r}. "
        "That sentence is what held the step in the SK-0c runs; a bare pointer was "
        "measured being skipped."
    )


def test_no_pointer_step_carries_a_command():
    """A step half converted is neither form: its commands drift from the
    reference's, and nobody knows which copy a model follows."""
    offenders = [
        p.parent.name for p in _pointer_skill_files() if "-m chitragupta" in _pointer_step(p)
    ]
    assert not offenders, f"the pointer-form critique step still names a command in {offenders}"


def test_the_reference_holds_the_loop_s_commands_in_order():
    """What a pointer-form step leaves out, the reference must carry:
    `dossier status` before the baseline, the baseline's section map, scan
    and style, then each edit's gate and recheck."""
    text = _reference()
    order = [
        re.compile(r"-m chitragupta\.draft dossier status\b"),
        re.compile(r"-m chitragupta\.draft dossier sections <draft> --citekeys --write"),
        _SCAN,
        _STYLE,
        _GATE,
        _RECHECK,
    ]
    found = [pattern.search(text) for pattern in order]
    assert all(found), [p.pattern for p, m in zip(order, found) if not m]
    starts = [m.start() for m in found]
    assert starts == sorted(starts), "the loop's commands are out of order in the reference"


def test_every_step_names_the_evidence_packet_and_the_claim_field():
    offenders = []
    for path in _genre_skill_files():
        for window in _windows(path):
            if "evidence.md" not in window or "claim:" not in window:
                offenders.append(path.parent.name)
    assert not offenders, (
        f"the critique step in {sorted(offenders)} does not name both `evidence.md` and "
        "`claim:` -- without them the step has nothing to critique the draft against."
    )


def test_every_step_is_capped_and_single_shot():
    offenders = {}
    for path in _genre_skill_files():
        for window in _windows(path):
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
        for window in _windows(path):
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
        for window in _windows(path):
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
        for window in _windows(path):
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
        for window in _windows(path):
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
        for window in _windows(path):
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
        for window in _windows(path):
            if _NOT_A_CONDITION not in window:
                offenders.append(path.parent.name)
    assert not offenders, (
        f"the critique step in {offenders} does not say it is {_NOT_A_CONDITION!r}. "
        "`chitragupta.draft gate` remains the only gate; a review-shaped step that gains "
        "a mandatory outcome is one careless edit away from being read as a second one."
    )


def test_every_genre_step_keeps_its_commands_in_skill_md():
    """An inline-form step keeps the loop's commands in front of the
    model, not only in the reference (#997). A step that held nothing but
    a pointer was once measured being skipped outright: a non-interactive
    run read none of it and went straight to the gate. A pointer-form step
    is held instead by its not-done-until sentence, which the SK-0c runs
    measured; the tests above pin that form."""
    offenders = []
    for path in _genre_skill_files():
        if path.parent.name in _POINTER_FORM:
            continue
        text = collapsed(path.read_text(encoding="utf-8"))
        windows = [text[m.start() : m.start() + _STEP_TAIL_CHARS] for m in _CRITIQUE.finditer(text)]
        if not any(_SCAN.search(w) and _GATE.search(w) and _RECHECK.search(w) for w in windows):
            offenders.append(path.parent.name)
    assert not offenders, f"the critique step's own text names no scan/gate/recheck in {offenders}"

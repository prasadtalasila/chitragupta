import re
from pathlib import Path

from tests.skill_text import collapsed, skill_text

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
REFERENCE = ".claude/skills-common/references/critique.md"

_POINTER_CHARS = 2000

_GENRE_SKILLS = {
    "survey-writer",
    "thesis-chapter-writer",
    "textbook-chapter-writer",
    "tutorial-writer",
    "deep-research",
}

_POINTER_FORM = {
    "deep-research",
    "survey-writer",
    "textbook-chapter-writer",
    "thesis-chapter-writer",
    "tutorial-writer",
}

_NOT_DONE_UNTIL = "not done until the loop the reference describes has run"

_DONE_WHEN = re.compile(r"Done when[^.]*\.")

_EXCLUDED_SKILLS = {
    "draft-reviser",
    "corpus-reviser",
    "agenda-reviser",
    "book-assembler",
    "figure-drawer",
    "review-digest",
}

_CRITIQUE = re.compile(r"[Cc]ritique against the evidence packet")

_STEP_TAIL_CHARS = 6800

_SINGLE_SHOT = "no second critique pass"

_CAP = "at most three items"

_GATE = re.compile(r"-m chitragupta\.draft gate\b")
_RECHECK = re.compile(r"-m chitragupta\.review verbatim recheck\b")
_STYLE = re.compile(r"-m chitragupta\.draft style\b")
_SCAN = re.compile(r"-m chitragupta\.review verbatim scan\b")

_OBJECTIVE_DELTA = "objective_delta"

_LENGTH_FLOOR = "90% of its own"

_REVISIONS = "revisions.md"
_REJECTED_EXCLUDED = "Never write any of this to `rejected.md`"

_NO_EVIDENCE = "`no evidence`"
_CUT = "cut the sentence"
_NEVER_REPOINT = "never to re-point it"
_STATUS = "dossier status"

_EXHAUSTED = "declared queries are exhausted"
_NO_OUTLINE = "there is no declared list"


_NOT_A_CONDITION = "never a condition of presenting"


def _skill_files():
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def _normalised(path):
    return skill_text(path)


def test_every_genre_step_names_the_reference():
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
    text = collapsed(path.read_text(encoding="utf-8"))
    start = _CRITIQUE.search(text).start()
    done = _DONE_WHEN.search(text, start)
    assert done, f"{path.parent.name}: the critique step does not end on a `Done when`"
    return text[start : done.end()]


def _reference():
    return collapsed((REPO_ROOT / REFERENCE).read_text(encoding="utf-8"))


def _windows(path):
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
    offenders = [
        p.parent.name for p in _pointer_skill_files() if "-m chitragupta" in _pointer_step(p)
    ]
    assert not offenders, f"the pointer-form critique step still names a command in {offenders}"


def test_the_reference_holds_the_loop_s_commands_in_order():
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
    offenders = []
    for path in _genre_skill_files():
        if path.parent.name in _POINTER_FORM:
            continue
        text = collapsed(path.read_text(encoding="utf-8"))
        windows = [text[m.start() : m.start() + _STEP_TAIL_CHARS] for m in _CRITIQUE.finditer(text)]
        if not any(_SCAN.search(w) and _GATE.search(w) and _RECHECK.search(w) for w in windows):
            offenders.append(path.parent.name)
    assert not offenders, f"the critique step's own text names no scan/gate/recheck in {offenders}"

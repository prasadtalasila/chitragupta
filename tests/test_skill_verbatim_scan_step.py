import re
from pathlib import Path

from tests.skill_text import collapsed, skill_text
from tests.test_skill_harness_copies import USER_SKILLS

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
GENRE_DOC = REPO_ROOT / "docs" / "GENRE.md"
REFERENCE = ".claude/skills-common/references/verbatim-scan.md"

_POINTER_CHARS = 1200

_SCAN = re.compile(r"-m chitragupta\.review verbatim scan\b")

_LOOKAHEAD_CHARS = 2000
_CAVEAT = "genuine restatement is only detected where the embedding tier can run"

_TIERS = "tiers_not_run"

_REGEN = re.compile(r"-m chitragupta\.draft dossier sections[^`]{0,160}?--citekeys --write")

_STEP_SPAN_CHARS = 200

_STEP_TAIL_CHARS = 2000

_NOT_A_CONDITION = "never a condition of presenting"

_OLD_OFFER = re.compile(r"Offer the verbatim scan", re.I)

_HELPERS = {"figure-drawer", "review-digest", "ai-images"}


def _skill_files():
    return sorted(p for p in SKILLS_DIR.glob("*/SKILL.md") if p.parent.name in USER_SKILLS)


def _normalised(path):
    return skill_text(path)


def test_every_scan_step_names_the_reference():
    offenders = sorted(
        p.parent.name
        for p in _skill_files()
        if p.parent.name not in _HELPERS
        and not any(
            f"`{REFERENCE}`" in text[m.start() : m.start() + _POINTER_CHARS]
            for text in [collapsed(p.read_text(encoding="utf-8"))]
            for m in _SCAN.finditer(text)
        )
    )
    assert not offenders, f"no pointer to {REFERENCE} after the scan command in {offenders}"


def test_every_drafting_skill_runs_the_verbatim_scan():
    files = _skill_files()
    assert files, "expected to find SKILL.md files under .claude/skills/"

    drafting = [p for p in files if p.parent.name not in _HELPERS]
    missing = [p.parent.name for p in drafting if not _SCAN.search(_normalised(p))]
    assert not missing, (
        "these skills never mention `-m chitragupta.review verbatim scan`, so a draft they "
        f"produce is presented with nobody told the check exists: {missing}. "
        'docs/GENRE.md\'s "What all eleven have in common" claims otherwise.'
    )


def test_no_skill_still_only_offers_the_scan():
    offenders = sorted(p.parent.name for p in _skill_files() if _OLD_OFFER.search(_normalised(p)))
    assert not offenders, (
        f'these skills still say "Offer the verbatim scan": {offenders}. '
        'The scan runs before presenting -- see docs/GENRE.md, "The verbatim '
        'scan is run, reported, and never a gate".'
    )


def test_every_scan_says_what_it_cannot_see():
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
    for match in _REGEN.finditer(text):
        head = text[match.start() : match.start() + _STEP_SPAN_CHARS]
        if _SCAN.search(head):
            yield match.start(), match.start() + _STEP_TAIL_CHARS


def test_every_skill_rebuilds_the_section_map_before_scanning():
    offenders = sorted(
        path.parent.name
        for path in _skill_files()
        if path.parent.name not in _HELPERS and not list(_step_blocks(_normalised(path)))
    )
    assert not offenders, (
        "no `dossier sections --citekeys --write` immediately before "
        f"`verbatim scan` in {offenders}. Tier 3 -- the only tier that sees "
        "genuine restatement -- compares each section against the citekeys "
        "that section's `sections.md` row records, so an unwritten or stale "
        "table silently reduces the scan to two tiers of three."
    )


def test_every_scan_step_reports_the_tiers_it_could_not_run():
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
    count = len([p for p in _skill_files() if p.parent.name != "ai-images"])
    assert count == 11, (
        f'{count} skills exist but docs/GENRE.md still says "all eleven". '
        "Update that section -- and check the new skill carries the gate, "
        "dossier and verbatim-scan conventions it states."
    )
    assert "What all eleven have in common" in GENRE_DOC.read_text(encoding="utf-8")

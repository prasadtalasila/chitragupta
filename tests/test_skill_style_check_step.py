import re
from pathlib import Path

import pytest

from tests.skill_text import collapsed, expanded
from tests.test_skill_harness_copies import USER_SKILLS

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
GENRE_DOC = REPO_ROOT / "docs" / "GENRE.md"
REFERENCE = ".claude/skills-common/references/prose-check.md"

_STEP = re.compile(r"-m chitragupta\.draft style\b")

_HELPERS = {"figure-drawer", "ai-images"}
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)

_LOOKAHEAD_CHARS = 1400

_CAVEAT = "§9 marks decidable"
_NO_FIX = "fix none of them"


def _skill_files():
    return sorted(p for p in SKILLS_DIR.glob("*/SKILL.md") if p.parent.name in USER_SKILLS)


def _body(path: Path) -> str:
    text = _FRONTMATTER.sub("", path.read_text(encoding="utf-8"), count=1)
    return expanded(text)


def test_every_step_but_the_repairing_one_names_the_reference():
    offenders = []
    for path in _skill_files():
        if path.parent.name in _HELPERS | {"agenda-reviser"}:
            continue
        text = collapsed(path.read_text(encoding="utf-8"))
        windows = [text[m.start() : m.start() + _LOOKAHEAD_CHARS] for m in _STEP.finditer(text)]
        if not any(f"`{REFERENCE}`" in w for w in windows):
            offenders.append(path.parent.name)
    assert not offenders, f"no pointer to {REFERENCE} after the command in {offenders}"


def test_the_frontmatter_stripper_still_strips():
    for path in _skill_files():
        assert _body(path).lstrip().startswith("#"), (
            f"{path.parent.name}: frontmatter survived the strip, so every "
            "proximity check in this file is searching text no drafter reads"
        )


def test_every_drafting_skill_runs_the_prose_check():
    files = _skill_files()
    assert files, "expected to find SKILL.md files under .claude/skills/"
    missing = [
        p.parent.name for p in files if p.parent.name not in _HELPERS and not _STEP.search(_body(p))
    ]
    assert not missing, (
        f"these skills never mention `-m chitragupta.draft style`, so a draft they "
        f"produce is presented with nobody told the check exists: {missing}. "
        'docs/GENRE.md\'s "What all eleven have in common" claims otherwise, '
        "and #183 is the issue this leaves half-built: the hook would still "
        "report per write, but nothing would report the finished draft."
    )


@pytest.mark.parametrize(
    "literal,why",
    [
        (
            _CAVEAT,
            "a findings list without it reads as a verdict on the prose, when the "
            "check is silent on every rule WRITING-STANDARDS.md sec 9 marks a "
            "judgement -- and skips only double-quoted and block quotations",
        ),
        (
            _NO_FIX,
            "#202 kept 59 of 73 marker hits in this repository's own docs after "
            "inspecting each. A rule with that hit rate is a report, not a work "
            "list, and draft-reviser's copy-edit mode is where a change gets made "
            "and logged",
        ),
    ],
)
def test_every_step_carries_its_qualifier(literal, why):
    exempt = {"agenda-reviser"} if literal == _NO_FIX else set()
    offenders = {}
    for path in _skill_files():
        if path.parent.name in exempt:
            continue
        text = _body(path)
        for match in _STEP.finditer(text):
            window = text[match.start() : match.start() + _LOOKAHEAD_CHARS]
            if literal not in window:
                offenders.setdefault(path.parent.name, []).append(match.start())
    assert not offenders, (
        f"`-m chitragupta.draft style` appears without {literal!r} nearby in "
        f"{sorted(offenders)}. {why}. If you added a second mention of the "
        "command, carry the qualifier with it or don't name the command."
    )


def test_the_shared_conventions_doc_names_the_command():
    genre = GENRE_DOC.read_text(encoding="utf-8")
    assert "python -m chitragupta.draft style" in genre, (
        "docs/GENRE.md speaks for all eight skills and does not mention the "
        "prose check, so this test would be pinning a convention no document "
        "states"
    )

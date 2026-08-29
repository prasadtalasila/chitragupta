"""Every drafting skill runs the prose check, says what it cannot see, and
fixes nothing.

A text scan over `.claude/skills/`, in the shape of
`tests/test_skill_verbatim_scan_step.py` and for the same reason: what
the command does has its own tests. This pins only that the eight skills
still tell anyone to run it, and still carry the two things that stop the
result being misread.

**Why "fix none of them" is pinned as hard as the command itself.** #186
originally specified that the step apply the findings §9 marks
machine-actionable. It does not, and the evidence is this repository's own
prose: the first pass of the check over `docs/` produced 73 defect-marker
hits, of which #202 cut 14 and **kept 59** after inspecting each -- the
meta-uses that name the banned words, "not just" meaning *not only*,
temporal "just", and "easy to miss" where it warns rather than reassures.
A rule with that hit rate on prose written to its own standard is a report,
not a work list. So a skill reports, and `draft-reviser`'s copy-edit mode
is where a change is made and logged.

The other pinned literal is the §9 reference. Without it a findings list
reads as a verdict on prose quality, when the check is silent on every
rule §9 marks a judgement -- and silent, too, about whether a marker sits
inside a quotation, which `assets/vale/vale.ini` exempts for block quotes
and code but not for inline quotation marks.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
GENRE_DOC = REPO_ROOT / "docs" / "GENRE.md"

_STEP = re.compile(r"-m chitragupta\.draft style\b")
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)

# Measured over the eight files once they were written: the furthest either
# literal sits from its command is ~700 characters, and no file names the
# command twice, so a window this size cannot reach a different step's.
_LOOKAHEAD_CHARS = 1100

_CAVEAT = "§9 marks decidable"
_NO_FIX = "fix none of them"


def _skill_files():
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def _body(path: Path) -> str:
    """The file without its YAML frontmatter, whitespace collapsed.

    Order matters and is the trap: strip the frontmatter on the raw text,
    *then* collapse. Collapse first and `\\A---\\n` can never match, so the
    strip silently does nothing and the test still passes -- which is how a
    guard against a false positive becomes a false negative.

    The frontmatter is excluded because `description:` is router text, read
    when Claude Code decides which skill to load. "Runs the prose check" is
    not a trigger, so the descriptions say nothing about it, and a scan
    that searched them would either fail or push noise into eight
    always-loaded strings.
    """
    text = _FRONTMATTER.sub("", path.read_text(encoding="utf-8"), count=1)
    return re.sub(r"\s+", " ", text)


def test_the_frontmatter_stripper_still_strips():
    """Guards the ordering trap above: if this passes vacuously, so does
    every proximity test below it."""
    for path in _skill_files():
        assert _body(path).lstrip().startswith("#"), (
            f"{path.parent.name}: frontmatter survived the strip, so every "
            "proximity check in this file is searching text no drafter reads"
        )


def test_every_drafting_skill_runs_the_prose_check():
    files = _skill_files()
    assert files, "expected to find SKILL.md files under .claude/skills/"
    missing = [p.parent.name for p in files if not _STEP.search(_body(p))]
    assert not missing, (
        f"these skills never mention `-m chitragupta.draft style`, so a draft they "
        f"produce is presented with nobody told the check exists: {missing}. "
        'docs/GENRE.md\'s "What all eight have in common" claims otherwise, '
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
            "judgement -- and cannot tell a quotation from the draft's own voice",
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
    # `agenda-reviser` is the one exception to `_NO_FIX`: under Decision 1 of
    # plans/f3-agenda-reviser.md, a `prose` finding is unattended work for
    # that skill alone, not merely a report, so requiring "fix none of them"
    # near its own mention of the command would pin the wrong invariant for
    # it specifically. `_CAVEAT` still applies -- the check is still silent
    # on the same judgement-shaped rules for every skill, this one included.
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
    """The scan pins a rule docs/GENRE.md states; without the statement this
    test would be inventing one."""
    genre = GENRE_DOC.read_text(encoding="utf-8")
    assert "python -m chitragupta.draft style" in genre, (
        "docs/GENRE.md speaks for all eight skills and does not mention the "
        "prose check, so this test would be pinning a convention no document "
        "states"
    )

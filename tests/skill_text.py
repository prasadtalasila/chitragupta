"""A skill's text as the model reads it: `SKILL.md` plus what it points at.

Since #997 a passage several skills share lives once, in a reference
file under `.claude/skills-common/references/` or a skill's own
`references/`, and `SKILL.md` names it at the step that needs it. The
step scans (tests/test_skill_*_step.py) pin riders that must travel with
a command -- "within N characters of it" -- and a rider that moved into
a reference still travels with the command, one file read away.

`expanded()` makes that literal: each reference a text names is spliced
in right after the name, once, so a window measured from the command
reaches the rider exactly as a model following the pointer would.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_REFERENCE = re.compile(r"`(\.claude/skills(?:-common|/[^`\s/]+)/references/[^`\s]+\.md)`")


def collapsed(text: str) -> str:
    """Whitespace runs as one space: these files are hand-wrapped."""
    return re.sub(r"\s+", " ", text)


def expanded(text: str) -> str:
    """`text`, collapsed, with every reference it names spliced in after
    the name. One level only: a reference naming another is not
    followed, the way the harnesses' own guidance keeps references one
    level deep."""

    def splice(match):
        body = (REPO_ROOT / match.group(1)).read_text(encoding="utf-8")
        return f"{match.group(0)} {collapsed(body)}"

    return _REFERENCE.sub(splice, collapsed(text))


def skill_text(path: Path) -> str:
    """`expanded()` over one `SKILL.md`."""
    return expanded(path.read_text(encoding="utf-8"))

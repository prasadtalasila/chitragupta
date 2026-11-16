"""No skill file names an issue or a pull request.

A skill is an instruction a model follows now. "(#1037)" or "since #421"
is history: it tells the model nothing it can act on, costs it attention
at the step it is reading, and is true only of the day it was written.
The reason a rule exists belongs in the sentence, in words; where it
came from belongs in the commit, the plan and the docs. #1091's Decision
4 took issue numbers out of each `SKILL.md` as it was shrunk; this holds
the whole tree to it, references and agent definitions included.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOTS = (
    ".claude/skills",
    ".claude/skills-common",
    ".claude/agents",
    ".agents/skills",
    ".opencode/skills",
)
# `#1037`, never `#1` (a LaTeX macro parameter), `#-anchor` or `#1f77b4`.
_ISSUE = re.compile(r"(?<![\w&/])#\d{2,5}\b")
_LINK = re.compile(r"(?:issues|pull)/\d+|\b(?:[Ii]ssue|PR) #?\d+")


def test_no_skill_file_names_an_issue_or_a_pull_request():
    found = {}
    for root in ROOTS:
        for path in sorted((REPO_ROOT / root).rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            hits = _ISSUE.findall(text) + _LINK.findall(text)
            if hits:
                found[str(path.relative_to(REPO_ROOT))] = hits
    assert not found, f"say why in words, not by number: {found}"

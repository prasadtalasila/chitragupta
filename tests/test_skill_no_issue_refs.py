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

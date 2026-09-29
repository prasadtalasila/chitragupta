"""Every skill loads on Claude Code, Codex and OpenCode alike (#812).

All three read the Agent Skills format (https://agentskills.io): a
`SKILL.md` whose frontmatter holds a `name` matching its folder and a
`description` of at most 1,024 characters, from a fixed set of keys. Four
skills' descriptions were over that and every skill carried an unread
`tags:` key; this keeps them from growing back.
"""

import re
from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parent.parent / ".claude" / "skills"
SKILL_FILES = sorted(SKILLS.glob("*/SKILL.md"))
ALLOWED = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_DESCRIPTION = 1024


def frontmatter(path: Path) -> dict[str, str]:
    """The top-level `key: value` lines between the opening `---` pair."""
    block = path.read_text(encoding="utf-8").split("---", 2)[1]
    fields = {}
    for line in block.strip().splitlines():
        match = re.match(r"^([a-z-]+):\s*(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    return fields


def test_every_skill_is_found():
    assert len(SKILL_FILES) == 9


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.parent.name)
def test_frontmatter_follows_the_agent_skills_spec(path):
    fields = frontmatter(path)
    assert set(fields) <= ALLOWED, f"keys outside the spec: {set(fields) - ALLOWED}"
    assert fields["name"] == path.parent.name
    assert NAME_RE.match(fields["name"])
    assert 1 <= len(fields["description"]) <= MAX_DESCRIPTION, len(fields["description"])

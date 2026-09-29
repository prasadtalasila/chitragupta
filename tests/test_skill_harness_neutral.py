"""No skill prescribes one harness's tools (#812).

The skills run unchanged on Claude Code, Codex and OpenCode, whose edit,
read and checklist tools have different names -- Codex edits through
`apply_patch`, OpenCode's edit takes `oldString`. So a skill says what to
do ("edit the passage in place"), never which tool to call. Plain English
("Read the dossier", "Write the section") is fine; a backticked tool name
or a harness-only mechanism is not.

`.claude/agents/<name>.md` paths are allowed: they are files any harness
can read, which is how a skill hands a general-purpose subagent its
protocol where the named one does not exist.
"""

import re
from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parent.parent / ".claude" / "skills"
FILES = sorted([*SKILLS.glob("*/SKILL.md"), *SKILLS.glob("*/reference.md")])
FORBIDDEN = [
    r"`Edit`",
    r"`Write`",
    r"`Read`",
    r"\bTodoWrite\b",
    r"\bAgent calls?\b",
    r"in (?:a single|one) message",
    r"`old_string`",
    r"`general-purpose`",
]


@pytest.mark.parametrize("path", FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_no_skill_prescribes_one_harness_tools(path):
    text = path.read_text(encoding="utf-8")
    hits = [pattern for pattern in FORBIDDEN if re.search(pattern, text)]
    assert not hits, f"{path.parent.name}/{path.name}: {hits}"


def test_the_scan_still_has_something_to_scan():
    assert len(FILES) >= 10  # nine SKILL.md plus deep-research's reference.md

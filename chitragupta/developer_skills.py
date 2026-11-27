"""Which skills are this repository's own developer tooling (#1188).

Marked by `metadata: audience: developer` in `SKILL.md` frontmatter.
Offered in a checkout, never distributed: not scaffolded, not zipped,
and `pyproject.toml` lists the other skills one by one because an
`include`d folder cannot be excluded back out
(tests/test_developer_skills.py). Stdlib-only and import-free:
`scripts/release.py` loads this file by path.
"""

import re
from pathlib import Path

# Where each harness reads its skills (docs/HARNESS.md).
SKILL_TREES = (".claude/skills", ".agents/skills", ".opencode/skills")

# `audience: developer` under a top-level `metadata:`; `\r?` for CRLF.
_MARKER = re.compile(
    r"^metadata:[ \t]*\r?\n(?:[ \t]+.*\n)*?[ \t]+audience:[ \t]*developer[ \t]*\r?$",
    re.MULTILINE,
)


def developer_skills(root: Path) -> set[str]:
    """The skill folders under `root` marked developer-only, as POSIX
    paths relative to `root`. Only the frontmatter counts, not a body
    that describes the marker.
    """
    found = set()
    for tree in SKILL_TREES:
        for skill_md in (root / tree).glob("*/SKILL.md"):
            parts = skill_md.read_text(encoding="utf-8").split("---", 2)
            if len(parts) == 3 and _MARKER.search(parts[1]):
                found.add(skill_md.parent.relative_to(root).as_posix())
    return found


def is_developer_only(path: str, skills: set[str]) -> bool:
    """Is the POSIX relative `path` one of `skills`, or inside one?"""
    return any(path == skill or path.startswith(skill + "/") for skill in skills)

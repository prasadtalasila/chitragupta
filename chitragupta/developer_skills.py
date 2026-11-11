"""Which skills are this repository's own developer tooling (#1188).

A skill marks itself developer-only in its `SKILL.md` frontmatter:

    metadata:
      audience: developer

It sits beside the genre skills in every harness folder, so a checkout's
harness offers it with no setup, but no distribution carries it:
`chitragupta init` does not scaffold it (`chitragupta/init.py`),
`scripts/release.py` leaves it out of the zip, and `pyproject.toml`'s
`include` names every other skill folder one by one instead of the whole
harness trees, since Poetry's `exclude` cannot take a path back out of an
`include`d folder (measured; tests/test_developer_skills.py pins the
list).

Stdlib-only, and imports nothing from the package: `scripts/release.py`
loads this file by path, the way `scripts/merge_pr.py` loads its sibling.
"""

import re
from pathlib import Path

# Where each harness reads its skills (docs/HARNESS.md).
SKILL_TREES = (".claude/skills", ".agents/skills", ".opencode/skills")

# `audience: developer` indented under a top-level `metadata:` key, with
# only other indented lines between them. `\r?` so a `\r\n` checkout
# still matches.
_MARKER = re.compile(
    r"^metadata:[ \t]*\r?\n(?:[ \t]+.*\n)*?[ \t]+audience:[ \t]*developer[ \t]*\r?$",
    re.MULTILINE,
)


def developer_skills(root: Path) -> set[str]:
    """The skill folders under `root` marked developer-only, as POSIX
    paths relative to `root` (e.g. `.claude/skills/demo-recorder`).

    Only the frontmatter counts: a skill that *describes* the marker in
    its body is not marked by it.
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

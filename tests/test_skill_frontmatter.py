import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOTS = (
    REPO_ROOT / ".claude" / "skills",
    REPO_ROOT / ".agents" / "skills",
    REPO_ROOT / ".opencode" / "skills",
)
SKILL_FILES = sorted(path for root in ROOTS for path in root.glob("*/SKILL.md"))
ALLOWED = {"name", "description", "license", "compatibility", "metadata", "allowed-tools", "tags"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_DESCRIPTION = 1024


def frontmatter(path: Path) -> dict[str, str]:
    block = path.read_text(encoding="utf-8").split("---", 2)[1]
    fields = {}
    for line in block.strip().splitlines():
        match = re.match(r"^([a-z-]+):\s*(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    return fields


def test_every_copy_of_every_skill_is_found():
    assert len(SKILL_FILES) == 42


def test_the_digest_skill_exists_on_every_harness():
    assert {p.parent.name for p in SKILL_FILES} >= {"review-digest", "review-digest-opencode"}


@pytest.mark.parametrize(
    "path", SKILL_FILES, ids=lambda p: f"{p.parent.parent.parent.name}/{p.parent.name}"
)
def test_frontmatter_loads_on_every_harness(path):
    fields = frontmatter(path)
    assert set(fields) <= ALLOWED, f"keys no harness expects: {set(fields) - ALLOWED}"
    assert fields["name"] == path.parent.name
    assert NAME_RE.match(fields["name"])
    assert 1 <= len(fields["description"]) <= MAX_DESCRIPTION, len(fields["description"])


@pytest.mark.parametrize(
    "path", SKILL_FILES, ids=lambda p: f"{p.parent.parent.parent.name}/{p.parent.name}"
)
def test_frontmatter_is_valid_yaml(path):
    block = path.read_text(encoding="utf-8").split("---", 2)[1]
    parsed = yaml.safe_load(block)
    assert parsed["name"] == path.parent.name
    assert parsed["description"] == frontmatter(path)["description"]


AGENT_FILES = sorted((REPO_ROOT / ".claude" / "agents").glob("*.md"))


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.name)
def test_agent_frontmatter_is_valid_yaml(path):
    block = path.read_text(encoding="utf-8").split("---", 2)[1]
    parsed = yaml.safe_load(block)
    assert parsed["name"] == path.stem
    assert parsed["description"] == frontmatter(path)["description"]

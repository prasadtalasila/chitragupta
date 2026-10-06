"""Harness-neutral skill files exist once, under .claude/ (#997).

`SKILL.md` is the only file kept per harness. Every other file a skill
uses lives in `.claude/skills/<name>/{references,assets,scripts}/` or in
`.claude/skills-common/`, which `chitragupta init` scaffolds for every
`--agent`, and all three copies of `SKILL.md` name it by project-root
path. A file read by all three harnesses therefore names no harness's
tools and no skill: OpenCode routes to `<name>-opencode`, so a bare
skill name here would send it to a skill its config denies.
"""

import re
from pathlib import Path

import pytest

from tests.test_skill_harness_copies import FOREIGN, ROOTS, SKILLS, folder

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE = REPO_ROOT / ".claude"
NEUTRAL_DIRS = ("references", "assets", "scripts")
NAMED_PATH = re.compile(r"`(\.claude/skills(?:-common)?/[^`\s]+)`")
TOOLS = sorted(
    {word for words in FOREIGN.values() for word in words} | {"`Edit`", "`Write`", "`Read`"}
)


def neutral_files() -> list:
    """Every file outside a `SKILL.md` that a skill may point at."""
    roots = [
        CLAUDE / "skills-common",
        *(CLAUDE / "skills" / s / d for s in SKILLS for d in NEUTRAL_DIRS),
    ]
    return sorted(p for root in roots if root.is_dir() for p in root.rglob("*") if p.is_file())


def every_skill_md() -> list:
    return [folder(h, name) / "SKILL.md" for h in ROOTS for name in SKILLS]


def named_paths(text: str) -> set:
    """The `.claude/skills…` files a text names, without any `#anchor`."""
    return {REPO_ROOT / match.split("#")[0] for match in NAMED_PATH.findall(text)}


@pytest.mark.parametrize("skill_md", every_skill_md(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_every_named_path_exists(skill_md):
    missing = [p for p in named_paths(skill_md.read_text(encoding="utf-8")) if not p.exists()]
    assert not missing, missing


def test_every_neutral_file_is_named_by_some_skill():
    """A reference no `SKILL.md` names is text no model will ever read.

    Markdown only: a script is named by the reference or step that runs
    it, and an asset by the reference that uses it.
    """
    named = named_paths("".join(p.read_text(encoding="utf-8") for p in every_skill_md()))
    orphans = [p for p in neutral_files() if p.suffix == ".md" and p not in named]
    assert not orphans, orphans


@pytest.mark.parametrize("path", neutral_files(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_neutral_files_name_no_skill_or_tool(path):
    text = path.read_text(encoding="utf-8")
    hits = [w for w in TOOLS if w in text] + [s for s in SKILLS if f"`{s}`" in text]
    assert not hits, hits


@pytest.mark.parametrize("harness", ["codex", "opencode"])
@pytest.mark.parametrize("name", SKILLS)
def test_only_skill_md_is_kept_per_harness(name, harness):
    assert sorted(p.name for p in folder(harness, name).iterdir()) == ["SKILL.md"]


# Skills whose collection-scoping section points at the shared reference.
# deep-research deliberately does not scope, and the revisers inherit the
# recorded collection instead of offering one.
_SCOPING_GENRES = (
    "survey-writer",
    "thesis-chapter-writer",
    "textbook-chapter-writer",
    "tutorial-writer",
)
_SCOPING = ".claude/skills-common/references/collection-scoping.md"


@pytest.mark.parametrize("name", _SCOPING_GENRES)
def test_each_scoping_genre_points_at_the_collection_reference(name):
    text = (folder("claude", name) / "SKILL.md").read_text(encoding="utf-8")
    section = text.split("## Collection scoping", 1)[1].split("\n## ", 1)[0]
    assert f"`{_SCOPING}`" in section
    assert "ledger --collections" in section, "the one check every run makes stays in SKILL.md"


# A mode a skill enters only on some requests, a repair it makes only for
# some item classes, or reference data too long to carry in three harness
# copies, is read from a reference named in the section that needs it
# (#997).
_CONDITIONAL = (
    ("draft-reviser", "## Copy-edit mode", "copy-edit.md"),
    ("draft-reviser", "## Acronym-realignment mode", "acronyms.md"),
    ("draft-reviser", "## Re-grounding after the corpus moves", "re-grounding.md"),
    ("agenda-reviser", "### 4. Repair one item", "repair-missing-citekey.md"),
    ("agenda-reviser", "### 4. Repair one item", "repair-prose.md"),
    ("agenda-reviser", "### 4. Repair one item", "repair-verbatim-run.md"),
    ("book-assembler", "## Conventions as data", "latex-conventions.md"),
)


@pytest.mark.parametrize("name,heading,reference", _CONDITIONAL)
def test_each_conditional_section_points_at_its_reference(name, heading, reference):
    text = (folder("claude", name) / "SKILL.md").read_text(encoding="utf-8")
    section = re.split(r"\n#{2,3} ", text.split(heading, 1)[1], maxsplit=1)[0]
    assert f"`.claude/skills/{name}/references/{reference}`" in section


@pytest.mark.parametrize("skill_md", every_skill_md(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_the_first_named_path_says_it_is_from_the_project_root(skill_md):
    """Codex resolves a relative path against the skill's own folder first,
    where `.agents/skills/<name>/.claude/...` does not exist. So each skill
    says where its paths start, before or at the first one it names."""
    text = " ".join(skill_md.read_text(encoding="utf-8").split())
    first = NAMED_PATH.search(text)
    if first is None:
        return
    assert "from the project root" in text[: first.end() + 250]

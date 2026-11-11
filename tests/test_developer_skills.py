"""Developer-only skills reach no distribution (#1188).

A skill marked `audience: developer` in its frontmatter sits beside the
genre skills in every harness folder, so a checkout sees it, but neither
`chitragupta init`, the release zip nor the wheel carries it. The first
two skip what `chitragupta/developer_skills.py` finds; the wheel cannot,
because Poetry's `exclude` does not reach inside an `include`d folder,
so the last class pins `pyproject.toml`'s `include` list against this
repository's own tracked files.
"""

import subprocess
import tomllib
from pathlib import Path

import pytest

from chitragupta.developer_skills import developer_skills, is_developer_only

REPO_ROOT = Path(__file__).resolve().parent.parent

MARKED = "---\nname: {name}\ndescription: d\nmetadata:\n  audience: developer\n---\n\n# body\n"
UNMARKED = "---\nname: {name}\ndescription: d\n---\n\n# body\n"


def write_skill(root: Path, rel: str, text: str) -> None:
    (root / rel).mkdir(parents=True)
    (root / rel / "SKILL.md").write_text(text.format(name=Path(rel).name), encoding="utf-8")


class TestTheMarker:
    def test_a_marked_skill_is_found_in_every_harness_tree(self, tmp_path):
        for rel in (".claude/skills/rec", ".agents/skills/rec", ".opencode/skills/rec-opencode"):
            write_skill(tmp_path, rel, MARKED)
        assert developer_skills(tmp_path) == {
            ".claude/skills/rec",
            ".agents/skills/rec",
            ".opencode/skills/rec-opencode",
        }

    def test_an_unmarked_skill_is_not(self, tmp_path):
        write_skill(tmp_path, ".claude/skills/survey-writer", UNMARKED)
        assert developer_skills(tmp_path) == set()

    def test_a_skill_md_without_frontmatter_is_not(self, tmp_path):
        write_skill(tmp_path, ".claude/skills/survey-writer", "# survey")
        assert developer_skills(tmp_path) == set()

    def test_the_marker_counts_only_inside_the_frontmatter(self, tmp_path):
        body = UNMARKED + "\nmetadata:\n  audience: developer\n"
        write_skill(tmp_path, ".claude/skills/survey-writer", body)
        assert developer_skills(tmp_path) == set()

    def test_crlf_line_endings_still_mark(self, tmp_path):
        """A Windows checkout with `core.autocrlf` hands the file over
        with `\\r\\n`, and the skill must not start shipping there."""
        write_skill(tmp_path, ".claude/skills/rec", MARKED.replace("\n", "\r\n"))
        assert developer_skills(tmp_path) == {".claude/skills/rec"}

    def test_no_harness_trees_find_nothing(self, tmp_path):
        assert developer_skills(tmp_path) == set()


class TestIsDeveloperOnly:
    SKILLS = {".claude/skills/rec"}

    def test_a_file_inside_the_skill(self):
        assert is_developer_only(".claude/skills/rec/scripts/tour.sh", self.SKILLS)

    def test_the_skill_folder_itself(self):
        assert is_developer_only(".claude/skills/rec", self.SKILLS)

    def test_a_sibling_sharing_the_prefix_is_not(self):
        assert not is_developer_only(".claude/skills/recorder/SKILL.md", self.SKILLS)


def tracked_harness_files() -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z", ".claude", ".agents", ".opencode"],
        capture_output=True,
        check=True,
    )
    return [p for p in result.stdout.decode().split("\0") if p]


class TestThisRepository:
    def test_demo_recorder_is_developer_only_on_every_harness(self):
        assert developer_skills(REPO_ROOT) == {
            ".claude/skills/demo-recorder",
            ".agents/skills/demo-recorder",
            ".opencode/skills/demo-recorder-opencode",
        }

    def test_pyproject_ships_every_harness_file_but_the_developer_skills(self):
        """Poetry ships a file when an `include` path is the file or one
        of its folders. Measured with poetry-core 2.3.1: an `exclude`
        does not take a file back out of an `include`d folder, so a
        folder-wide `.claude` entry would ship the skill."""
        with open(REPO_ROOT / "pyproject.toml", "rb") as f:
            entries = tomllib.load(f)["tool"]["poetry"]["include"]
        paths = [entry["path"] for entry in entries]
        dev = developer_skills(REPO_ROOT)
        tracked = tracked_harness_files()
        shipped = {p for p in tracked if any(p == i or p.startswith(i + "/") for i in paths)}
        assert shipped == {p for p in tracked if not is_developer_only(p, dev)}

    @pytest.mark.parametrize("tree", [".claude", ".agents", ".opencode"])
    def test_no_include_names_a_whole_harness_tree(self, tree):
        """The shape that ships everything, named so its failure says why."""
        with open(REPO_ROOT / "pyproject.toml", "rb") as f:
            entries = tomllib.load(f)["tool"]["poetry"]["include"]
        assert tree not in [entry["path"] for entry in entries]

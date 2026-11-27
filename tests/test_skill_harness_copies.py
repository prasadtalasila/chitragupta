import json
import re
import tomllib
from pathlib import Path

import pytest

from chitragupta.developer_skills import developer_skills

REPO_ROOT = Path(__file__).resolve().parent.parent
PHRASES = tomllib.loads(
    (REPO_ROOT / "tests" / "fixtures" / "skill_harness_phrases.toml").read_text(encoding="utf-8")
)
ROOTS = {
    "claude": REPO_ROOT / ".claude" / "skills",
    "codex": REPO_ROOT / ".agents" / "skills",
    "opencode": REPO_ROOT / ".opencode" / "skills",
}
SUFFIX = {"claude": "", "codex": "", "opencode": "-opencode"}
SKILLS = sorted(p.name for p in ROOTS["claude"].iterdir() if p.is_dir())
DEVELOPER_SKILLS = {Path(p).name for p in developer_skills(REPO_ROOT) if p.startswith(".claude/")}
USER_SKILLS = [name for name in SKILLS if name not in DEVELOPER_SKILLS]
SUFFIXED = re.compile(r"\b(" + "|".join(map(re.escape, SKILLS)) + r")-opencode\b")

FOREIGN = {
    "claude": ["`apply_patch`", "`exec_command`", "`oldString`", "`todowrite`", "`task`"],
    "codex": [
        "`Edit`",
        "`Write`",
        "`Read`",
        "TodoWrite",
        "`todowrite`",
        "Agent calls",
        "`general-purpose`",
        "`old_string`",
        "`oldString`",
    ],
    "opencode": ["`Edit`", "`Write`", "`Read`", "TodoWrite", "`general-purpose`", "`old_string`"],
}


def folder(harness: str, name: str) -> Path:
    return ROOTS[harness] / f"{name}{SUFFIX[harness]}"


def collapsed(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def normalized(harness: str, text: str) -> str:
    text = collapsed(text)
    for key, entry in sorted(PHRASES.items(), key=lambda kv: -len(kv[1][harness])):
        text = text.replace(collapsed(entry[harness]), f"<<{key}>>")
    if harness == "opencode":
        text = SUFFIXED.sub(r"\1", text)
    return text


def first_difference(a: str, b: str) -> str:
    at = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    start = max(0, at - 80)
    return f"claude: ...{a[start : at + 80]}...\nother:  ...{b[start : at + 80]}..."


def test_every_skill_has_all_three_copies():
    for harness in ROOTS:
        found = sorted(p.name.removesuffix(SUFFIX[harness]) for p in ROOTS[harness].iterdir())
        assert found == SKILLS, harness


@pytest.mark.parametrize("name", SKILLS)
def test_each_copy_holds_the_same_files(name):
    files = {h: sorted(p.name for p in folder(h, name).glob("*.md")) for h in ROOTS}
    assert files["codex"] == files["claude"] == files["opencode"], files


@pytest.mark.parametrize("harness", ["codex", "opencode"])
@pytest.mark.parametrize("name", SKILLS)
def test_the_copies_differ_only_where_the_phrase_map_says(name, harness):
    for path in sorted(folder("claude", name).glob("*.md")):
        base = normalized("claude", path.read_text(encoding="utf-8"))
        other = normalized(harness, (folder(harness, name) / path.name).read_text(encoding="utf-8"))
        assert base == other, (
            f"{harness} copy of {name}/{path.name} has drifted from the Claude Code copy "
            f"outside tests/fixtures/skill_harness_phrases.toml:\n{first_difference(base, other)}"
        )


@pytest.mark.parametrize("harness", list(ROOTS))
def test_every_phrase_is_used_by_every_harness(harness):
    texts = collapsed("".join(p.read_text(encoding="utf-8") for p in ROOTS[harness].glob("*/*.md")))
    unused = [key for key, entry in PHRASES.items() if collapsed(entry[harness]) not in texts]
    assert not unused, f"{harness}: {unused}"


def test_every_phrase_names_all_three_harnesses():
    for key, entry in PHRASES.items():
        assert set(entry) == set(ROOTS), key


@pytest.mark.parametrize("harness", list(ROOTS))
@pytest.mark.parametrize("name", SKILLS)
def test_no_copy_names_another_harness_tools(name, harness):
    text = "".join(p.read_text(encoding="utf-8") for p in folder(harness, name).glob("*.md"))
    hits = [word for word in FOREIGN[harness] if word in text]
    assert not hits, f"{harness} copy of {name}: {hits}"


@pytest.mark.parametrize("name", SKILLS)
def test_the_opencode_copy_refers_to_opencode_skills(name):
    text = (folder("opencode", name) / "SKILL.md").read_text(encoding="utf-8")
    bare = [s for s in SKILLS if f"`{s}`" in text]
    assert not bare, bare


def test_opencode_denies_exactly_the_unsuffixed_names():
    config = json.loads((REPO_ROOT / ".opencode" / "opencode.json").read_text(encoding="utf-8"))
    rules = config["permission"]["skill"]
    assert rules.pop("*") == "allow"
    assert rules == {name: "deny" for name in SKILLS}


def test_a_changed_sentence_in_one_copy_is_caught():
    claude = (folder("claude", "survey-writer") / "SKILL.md").read_text(encoding="utf-8")
    codex = (folder("codex", "survey-writer") / "SKILL.md").read_text(encoding="utf-8")
    drifted = codex.replace("never a fabricated one", "ideally not a fabricated one", 1)
    assert drifted != codex
    assert normalized("claude", claude) == normalized("codex", codex)
    assert normalized("claude", claude) != normalized("codex", drifted)

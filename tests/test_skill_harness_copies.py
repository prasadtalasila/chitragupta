"""The three per-harness skill copies say the same thing (#812, #900).

Each skill exists once per harness, and each copy names that harness's
own tools, so a model reads a complete instruction at the step where it
acts:

- `.claude/skills/<name>/` for Claude Code;
- `.agents/skills/<name>/` for Codex, which reads project skills from
  nowhere else;
- `.opencode/skills/<name>-opencode/` for OpenCode, whose own names and
  `.opencode/opencode.json` deny list keep it on this copy (OpenCode keys
  skills by name and would otherwise pick among same-named copies at
  random; docs/HARNESS.md).

The copies are edited by hand. What keeps them from drifting apart is
this test: `tests/fixtures/skill_harness_phrases.toml` lists every place
they are meant to differ, each copy is normalized by replacing its own
phrases with the entry's key (and, for OpenCode, dropping the `-opencode`
suffix), and the three results must be identical. A sentence changed in
one copy and not the others fails, naming the skill, the copy and the
first line that moved.

The step scans (tests/test_skill_*_step.py) read only `.claude/skills/`:
once the copies agree here, a required step present in one is present in
all three.
"""

import json
import re
import tomllib
from pathlib import Path

import pytest

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
SUFFIXED = re.compile(r"\b(" + "|".join(map(re.escape, SKILLS)) + r")-opencode\b")

# Tool names that belong to one harness and must not appear in another's
# copy. Backticked, so ordinary English ("Read the dossier") is untouched.
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
    """`text` with every run of whitespace as one space.

    A line break inside Markdown prose carries no meaning, and a phrase
    that is longer in one harness's copy pushes that copy's paragraph onto
    different line breaks. Comparing collapsed text lets each copy wrap at
    80 columns without that reading as drift.
    """
    return re.sub(r"\s+", " ", text)


def normalized(harness: str, text: str) -> str:
    """`text` with this harness's phrases replaced by the phrase keys.

    Longest phrase first, so an entry that contains another is replaced
    whole rather than half-rewritten by the shorter one.
    """
    text = collapsed(text)
    for key, entry in sorted(PHRASES.items(), key=lambda kv: -len(kv[1][harness])):
        text = text.replace(collapsed(entry[harness]), f"<<{key}>>")
    if harness == "opencode":
        text = SUFFIXED.sub(r"\1", text)
    return text


def first_difference(a: str, b: str) -> str:
    """The first stretch where two collapsed texts part, with some context."""
    at = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    start = max(0, at - 80)
    return f"claude: ...{a[start : at + 80]}...\nother:  ...{b[start : at + 80]}..."


def test_every_skill_has_all_three_copies():
    for harness in ROOTS:
        found = sorted(p.name.removesuffix(SUFFIX[harness]) for p in ROOTS[harness].iterdir())
        assert found == SKILLS, harness


@pytest.mark.parametrize("name", SKILLS)
def test_each_copy_holds_the_same_files(name):
    files = {h: sorted(p.name for p in folder(h, name).iterdir()) for h in ROOTS}
    assert files["codex"] == files["claude"] == files["opencode"], files


@pytest.mark.parametrize("harness", ["codex", "opencode"])
@pytest.mark.parametrize("name", SKILLS)
def test_the_copies_differ_only_where_the_phrase_map_says(name, harness):
    for path in sorted(folder("claude", name).iterdir()):
        base = normalized("claude", path.read_text(encoding="utf-8"))
        other = normalized(harness, (folder(harness, name) / path.name).read_text(encoding="utf-8"))
        assert base == other, (
            f"{harness} copy of {name}/{path.name} has drifted from the Claude Code copy "
            f"outside tests/fixtures/skill_harness_phrases.toml:\n{first_difference(base, other)}"
        )


@pytest.mark.parametrize("harness", list(ROOTS))
def test_every_phrase_is_used_by_every_harness(harness):
    """A phrase no copy carries is a map entry that has gone stale."""
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
    """A backticked skill name in the OpenCode copy carries the suffix, or
    the model is sent to a skill `.opencode/opencode.json` denies."""
    text = (folder("opencode", name) / "SKILL.md").read_text(encoding="utf-8")
    bare = [s for s in SKILLS if f"`{s}`" in text]
    assert not bare, bare


def test_opencode_denies_exactly_the_unsuffixed_names():
    config = json.loads((REPO_ROOT / ".opencode" / "opencode.json").read_text(encoding="utf-8"))
    rules = config["permission"]["skill"]
    assert rules.pop("*") == "allow"
    assert rules == {name: "deny" for name in SKILLS}


def test_a_changed_sentence_in_one_copy_is_caught():
    """The test's own premise: normalizing does not hide real drift."""
    claude = (folder("claude", "survey-writer") / "SKILL.md").read_text(encoding="utf-8")
    codex = (folder("codex", "survey-writer") / "SKILL.md").read_text(encoding="utf-8")
    drifted = codex.replace("never a fabricated one", "ideally not a fabricated one", 1)
    assert drifted != codex
    assert normalized("claude", claude) == normalized("codex", codex)
    assert normalized("claude", claude) != normalized("codex", drifted)

"""`figure-drawer` is a router with a taste gate before drawing (#1048).

Each copy of its `SKILL.md` is a short list of steps, each a command or
a check. The detail lives once, in
`.claude/skills/figure-drawer/references/`, and a section that moved
there is text no model reads unless every copy still cites it. This
scan pins the citations both ways, more strictly than
tests/test_skill_references.py does for every skill (here every copy
cites every section), and the gate's place and questions. The byte cap
is tests/test_skill_size.py's (#1091). It exercises no behaviour.
"""

import re
from pathlib import Path

import pytest

from tests.skill_text import cited, numbered_sections

REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCES = REPO_ROOT / ".claude" / "skills" / "figure-drawer" / "references"
COPIES = (
    REPO_ROOT / ".claude" / "skills" / "figure-drawer" / "SKILL.md",
    REPO_ROOT / ".agents" / "skills" / "figure-drawer" / "SKILL.md",
    REPO_ROOT / ".opencode" / "skills" / "figure-drawer-opencode" / "SKILL.md",
)


def _ids(path: Path) -> str:
    return path.parent.parent.parent.name


def _text(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def _numbered_sections() -> list[tuple[str, str]]:
    """Every `## N.` section of a figure-drawer reference, as (path, N)."""
    return [s for path in sorted(REFERENCES.rglob("*.md")) for s in numbered_sections(path)]


def test_some_reference_has_numbered_sections():
    # Guards the two tests below against passing on an empty list.
    assert len(_numbered_sections()) >= 7


@pytest.mark.parametrize("copy", COPIES, ids=_ids)
def test_every_numbered_section_is_cited(copy):
    """A section moved out of `SKILL.md` keeps its link (#1048)."""
    found = cited(_text(copy))
    lost = [f"{path} §{n}" for path, n in _numbered_sections() if (path, n) not in found]
    assert not lost, lost


@pytest.mark.parametrize("copy", COPIES, ids=_ids)
def test_every_cited_section_exists(copy):
    sections = set(_numbered_sections())
    own = {c for c in cited(_text(copy)) if c[0].startswith(".claude/skills/figure-drawer/")}
    dangling = sorted(own - sections)
    assert not dangling, dangling


def test_a_citation_lists_its_sections():
    text = "`.claude/skills/figure-drawer/references/a.md` §1, §3 and §4; `x` §9"
    assert cited(text) == {
        (".claude/skills/figure-drawer/references/a.md", n) for n in ("1", "3", "4")
    }


@pytest.mark.parametrize("copy", COPIES, ids=_ids)
def test_the_taste_gate_comes_before_anything_is_written(copy):
    text = _text(copy)
    order = [
        "Pattern, then layout",
        "The taste gate",
        "kpsewhich tikz.sty",
        "chitragupta.figure new",
    ]
    at = [text.find(s) for s in order]
    assert -1 not in at and at == sorted(at), dict(zip(order, at))


@pytest.mark.parametrize("copy", COPIES, ids=_ids)
def test_the_taste_gate_asks_its_five_questions_and_can_hand_back(copy):
    text = _text(copy)
    gate = text.split("The taste gate", 1)[1].split("chitragupta.figure new", 1)[0]
    questions = (
        "a sentence or a table",
        "remove test",
        "travel together",
        "one focal node",
        "one figure or two figures",
    )
    for question in questions:
        assert question in gate, question
    assert "draw nothing" in gate
    assert "`.claude/skills/figure-drawer/references/taste.md`" in gate


@pytest.mark.parametrize("copy", COPIES, ids=_ids)
def test_figure_check_is_read_and_never_blocks(copy):
    text = _text(copy)
    step = text.split("chitragupta.figure check", 1)[1].split("chitragupta.figure look", 1)[0]
    for phrase in ("objective", "cg-allow", "advisory", "exits 2", "never blocks"):
        assert phrase in step, phrase


@pytest.mark.parametrize("copy", COPIES, ids=_ids)
def test_the_return_reports_the_gate(copy):
    text = _text(copy)
    tail = text.rsplit("**Return.**", 1)[1]
    for phrase in ("what the taste gate cut", "reported and allowed", "whether the look was done"):
        assert phrase in tail, phrase


@pytest.mark.parametrize("copy", COPIES, ids=_ids)
def test_no_hand_built_probe_comes_back(copy):
    # #1048: `figure check` compiles the figure in the render's engine and
    # fonts, so a probe document assembled by hand is a second, weaker copy.
    text = _text(copy)
    for phrase in ("lualatex probe", "run `lualatex` on it", "\\documentclass"):
        assert phrase not in text, phrase

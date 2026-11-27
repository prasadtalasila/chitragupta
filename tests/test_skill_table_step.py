import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"

_MARKDOWN_SKILLS = (
    "survey-writer",
    "textbook-chapter-writer",
    "tutorial-writer",
    "deep-research",
    "draft-reviser",
    "book-assembler",
)

_MARKER = re.compile(r"<!--\s*table:")
_REFERENCE = re.compile(r"<!--\s*tableref:")
_SECTION = re.compile(r"WRITING-STANDARDS\.md`?\s*§13|§13")


def _text(name: str) -> str:
    return (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")


def test_every_markdown_skill_names_the_table_marker():
    missing = [name for name in _MARKDOWN_SKILLS if not _MARKER.search(_text(name))]
    assert not missing, f"§13's `<!-- table: -->` marker missing from: {missing}"


def test_every_drafting_skill_names_the_reference_marker():
    drafting = [name for name in _MARKDOWN_SKILLS if name != "book-assembler"]
    missing = [name for name in drafting if not _REFERENCE.search(_text(name))]
    assert not missing, f"§13's `<!-- tableref: -->` marker missing from: {missing}"


def test_the_thesis_genre_names_the_latex_form_instead():
    text = _text("thesis-chapter-writer")
    assert "\\label{tab:" in text and "Table~\\ref{tab:" in text
    assert not _MARKER.search(text), "the thesis genre must not carry the Markdown marker"


def test_every_skill_that_writes_a_table_points_at_the_section():
    named = _MARKDOWN_SKILLS + ("thesis-chapter-writer",)
    missing = [name for name in named if not _SECTION.search(_text(name))]
    assert not missing, f"no reference to WRITING-STANDARDS.md §13 in: {missing}"

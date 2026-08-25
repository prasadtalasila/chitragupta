"""Every skill that can write a table says how a table is written.

Issue 395: before docs/WRITING-STANDARDS.md §13 existed, every genre
emitted bare pipe tables -- unnumbered in the pdf, unread by the prose.
The renderer and `python -m chitragupta.draft style` now handle a table
that carries the markers; nothing makes a skill *write* them, and a
SKILL.md edited by hand later that drops the sentence is a silent
regression back to the original defect. That is what this text-scan
catches. It exercises no behaviour: `tests/test_render_output_tables.py`
and `tests/test_style_tables.py` own that.

The split below is the substance. Four Markdown genres share one marker
vocabulary; `thesis-chapter-writer` writes real LaTeX instead, per §13's
carve-out, and asserting the marker for it would pin the opposite of what
that genre must do.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"

# Every skill that writes or revises Markdown prose containing a table.
# `book-assembler` writes no prose but composes units into one LaTeX
# document, which is where a duplicate id stops being harmless.
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
    # book-assembler composes finished units and writes no prose, so it
    # has no reason to name the reference marker -- only the id it can
    # collide.
    drafting = [name for name in _MARKDOWN_SKILLS if name != "book-assembler"]
    missing = [name for name in drafting if not _REFERENCE.search(_text(name))]
    assert not missing, f"§13's `<!-- tableref: -->` marker missing from: {missing}"


def test_the_thesis_genre_names_the_latex_form_instead():
    # §13's carve-out: the fragment is \input into the user's own thesis,
    # which numbers its tables itself. A marker there would be dropped by
    # their build.
    text = _text("thesis-chapter-writer")
    assert "\\label{tab:" in text and "Table~\\ref{tab:" in text
    assert not _MARKER.search(text), "the thesis genre must not carry the Markdown marker"


def test_every_skill_that_writes_a_table_points_at_the_section():
    named = _MARKDOWN_SKILLS + ("thesis-chapter-writer",)
    missing = [name for name in named if not _SECTION.search(_text(name))]
    assert not missing, f"no reference to WRITING-STANDARDS.md §13 in: {missing}"

"""`spec align`: does the authored chapter still match the approved outline?

What is worth pinning is the scoping rule, not the string comparison.
A spec that describes a book only at chapter granularity -- every book
retrofitted from prose written before this track -- must report nothing
and refuse nothing, because every heading its author wrote would
otherwise be an "extra" section. The check exists for a book drafted
through the real track, and has to stay silent on one that was not.
"""

from pathlib import Path

import pytest

from chitragupta import spec


# Chapter 1 is described at section level: three sections, none of them
# titled like the chapter. Chapter 2 is the retrofitted shape -- one
# section carrying the chapter's own title, which is what a book drafted
# before this track looks like after `spec init`.
SPEC = """# Composable Digital Twins

## Part I: Foundations {#part-1}

### What a twin is {#ch-what}

#### The model half {#sec-model}

Establish the model.

#### The data half {#sec-data}

Establish the link.

#### Where the two meet {#sec-meet}

Establish the join.

### What a twin costs {#ch-cost}

#### What a twin costs {#ch-cost-only}

One chapter, one unit, drafted before this outline existed.
"""

ALIGNED = """# What a twin is

## The model half

Prose.

## The data half

Prose.

## Where the two meet

Prose.
"""


@pytest.fixture
def book(isolated_config):
    path = isolated_config.DRAFTS_DIR / "twins"
    spec_file = spec.spec_path(path)
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(SPEC, encoding="utf-8")
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_chapter(book: Path, chapter_id: str, text: str, suffix: str = ".md") -> Path:
    path = book / f"{chapter_id}{suffix}"
    path.write_text(text, encoding="utf-8")
    return path


# --- the scoping rule ----------------------------------------------------


def test_a_chapter_described_only_at_chapter_level_is_not_aligned(book, capsys):
    """The retrofitted shape. Its author wrote ~40 headings under one
    declared section; reporting each as an extra would make the check the
    first thing anyone turns off."""
    write_chapter(book, "ch-cost", "# What a twin costs\n\n## Anything at all\n\nProse.\n")
    write_chapter(book, "ch-what", ALIGNED)
    assert spec.main(["align", str(book)]) == 0
    out = capsys.readouterr().out
    assert "ch-cost" in out
    assert "chapter level" in out
    assert "Anything at all" not in out


def test_a_chapter_whose_sections_match_is_aligned(book, capsys):
    write_chapter(book, "ch-what", ALIGNED)
    write_chapter(book, "ch-cost", "# What a twin costs\n")
    assert spec.main(["align", str(book)]) == 0
    assert "aligned" in capsys.readouterr().out


# --- the four findings ---------------------------------------------------


def test_a_section_in_the_spec_that_nobody_wrote_is_reported(book, capsys):
    write_chapter(book, "ch-what", ALIGNED.replace("## Where the two meet\n\nProse.\n", ""))
    write_chapter(book, "ch-cost", "# What a twin costs\n")
    assert spec.main(["align", str(book)]) == 1
    assert "not authored: Where the two meet" in capsys.readouterr().out


def test_a_section_nobody_declared_is_reported(book, capsys):
    write_chapter(book, "ch-what", ALIGNED + "\n## An afterthought\n\nProse.\n")
    write_chapter(book, "ch-cost", "# What a twin costs\n")
    assert spec.main(["align", str(book)]) == 1
    assert "not declared: An afterthought" in capsys.readouterr().out


def test_a_reworded_heading_is_reported_as_a_rename_not_two_findings(book, capsys):
    write_chapter(book, "ch-what", ALIGNED.replace("The data half", "The data half, revisited"))
    write_chapter(book, "ch-cost", "# What a twin costs\n")
    assert spec.main(["align", str(book)]) == 1
    out = capsys.readouterr().out
    assert "renamed" in out
    assert "not authored" not in out
    assert "not declared" not in out


def test_the_same_sections_in_the_wrong_order_are_reported(book, capsys):
    reordered = "# What a twin is\n\n## The data half\n\nP.\n\n## The model half\n\nP.\n\n## Where the two meet\n\nP.\n"
    write_chapter(book, "ch-what", reordered)
    write_chapter(book, "ch-cost", "# What a twin costs\n")
    assert spec.main(["align", str(book)]) == 1
    assert "out of order" in capsys.readouterr().out


# --- what it tolerates ---------------------------------------------------


def test_numbering_a_heading_is_not_a_misalignment(book, capsys):
    """`3.1 The model half` is the same section as `The model half`. A
    genre skill numbers headings; the spec does not."""
    numbered = ALIGNED.replace("## The model half", "## 3.1 The model half").replace(
        "## The data half", "## 3.2. The data half"
    )
    write_chapter(book, "ch-what", numbered)
    write_chapter(book, "ch-cost", "# What a twin costs\n")
    assert spec.main(["align", str(book)]) == 0
    assert "aligned" in capsys.readouterr().out


def test_a_latex_chapter_is_read_the_same_way(book, capsys):
    """thesis-chapter-writer emits `.tex`; `sections()` already reads
    both, so alignment must not be Markdown-only."""
    tex = (
        "\\chapter{What a twin is}\n\\section{The model half}\nP.\n"
        "\\section{The data half}\nP.\n\\section{Where the two meet}\nP.\n"
    )
    write_chapter(book, "ch-what", tex, suffix=".tex")
    write_chapter(book, "ch-cost", "# What a twin costs\n")
    assert spec.main(["align", str(book)]) == 0
    assert "aligned" in capsys.readouterr().out


def test_a_chapter_nobody_has_written_yet_is_reported_but_is_not_a_misalignment(book, capsys):
    write_chapter(book, "ch-cost", "# What a twin costs\n")
    assert spec.main(["align", str(book)]) == 1
    assert "not written yet" in capsys.readouterr().out


# --- refusals and the machine-readable form ------------------------------


def test_align_refuses_a_spec_that_does_not_parse(book, capsys):
    spec.spec_path(book).write_text("# Book\n\n## Part I\n", encoding="utf-8")
    assert spec.main(["align", str(book)]) == 1
    assert "{#id}" in capsys.readouterr().err


def test_align_as_json_is_what_a_skill_reads(book, capsys):
    import json

    write_chapter(book, "ch-what", ALIGNED + "\n## An afterthought\n\nProse.\n")
    write_chapter(book, "ch-cost", "# What a twin costs\n")
    assert spec.main(["align", str(book), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    described = [c for c in payload["chapters"] if c["id"] == "ch-what"][0]
    assert described["section_described"] is True
    assert described["not_declared"] == ["An afterthought"]
    retrofit = [c for c in payload["chapters"] if c["id"] == "ch-cost"][0]
    assert retrofit["section_described"] is False

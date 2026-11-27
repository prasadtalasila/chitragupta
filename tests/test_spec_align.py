from pathlib import Path

import pytest

from chitragupta import spec
from chitragupta.spec._align import chapter_draft


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


BOOK_SPEC = SPEC


def write_chapter(book: Path, chapter_id: str, text: str, suffix: str = ".md") -> Path:
    path = book / f"{chapter_id}{suffix}"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_chapter_described_only_at_chapter_level_is_not_aligned(book, capsys):
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


def test_numbering_a_heading_is_not_a_misalignment(book, capsys):
    numbered = ALIGNED.replace("## The model half", "## 3.1 The model half").replace(
        "## The data half", "## 3.2. The data half"
    )
    write_chapter(book, "ch-what", numbered)
    write_chapter(book, "ch-cost", "# What a twin costs\n")
    assert spec.main(["align", str(book)]) == 0
    assert "aligned" in capsys.readouterr().out


def test_a_latex_chapter_is_read_the_same_way(book, capsys):
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


@pytest.mark.parametrize("escaping", ["../../x", "a/../../b"])
def test_chapter_draft_refuses_an_id_that_leaves_the_book(book, escaping):
    with pytest.raises(spec.SpecError, match="does not resolve inside"):
        chapter_draft(book, escaping)


def test_chapter_draft_refuses_an_absolute_id(book, tmp_path):
    with pytest.raises(spec.SpecError, match="does not resolve inside"):
        chapter_draft(book, str(tmp_path / "evil"))


def test_chapter_draft_refuses_an_id_the_platform_cannot_resolve(book):
    with pytest.raises(spec.SpecError, match="does not resolve inside"):
        chapter_draft(book, "ch\x00what")


def test_a_chapter_symlinked_out_of_the_book_is_refused_by_name(book, tmp_path, capsys):
    outside = tmp_path / "elsewhere.md"
    outside.write_text(ALIGNED, encoding="utf-8")
    (book / "ch-what.md").symlink_to(outside)
    assert spec.main(["align", str(book)]) == 1
    err = capsys.readouterr().err
    assert "[error]" in err
    assert "ch-what.md" in err


def test_a_chapter_file_in_a_symlink_loop_is_refused_rather_than_crashing(book, capsys):
    (book / "ch-what.md").symlink_to(book / "loop")
    (book / "loop").symlink_to(book / "ch-what.md")
    assert spec.main(["align", str(book)]) == 1
    assert "ch-what.md" in capsys.readouterr().err

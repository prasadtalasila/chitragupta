"""`spec seed`: give each chapter a dossier outline from the signed spec.

The book spec owns the structure, the genre skills own the content
(#472). This is the handover -- it writes the chapter's section names
into that chapter's `outline.md` and stops, leaving every brief, claim
and query for the person who drafts it.

What is worth pinning is that it cannot destroy work. Seeding is safe to
re-run, and a heading somebody has already filled in is never rewritten.
"""

import pytest

from chitragupta import spec
from chitragupta.dossier import OUTLINE_MD, dossier_dir

SPEC = """# Composable Digital Twins

## Part I: Foundations {#part-1}

### What a twin is {#ch-what}

#### The model half {#sec-model}

Establish the model.

#### The data half {#sec-data}

Establish the link.

### What a twin costs {#ch-cost}

#### What a twin costs {#ch-cost-only}

One chapter, one unit, drafted before this outline existed.
"""


@pytest.fixture
def book(isolated_config):
    path = isolated_config.DRAFTS_DIR / "twins"
    spec_file = spec.spec_path(path)
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(SPEC, encoding="utf-8")
    path.mkdir(parents=True, exist_ok=True)
    return path


def outline_of(book, chapter_id):
    return dossier_dir(book / f"{chapter_id}.md") / OUTLINE_MD


def seed(book, *extra):
    return spec.main(["seed", str(book), "--genre", "textbook-chapter", *extra])


# --- the sign-off precondition -------------------------------------------


def test_seeding_refuses_an_outline_nobody_signed_off(book, capsys):
    """Seeding from a structure nobody approved is what step 2 exists to
    prevent -- it would put unapproved section names in front of an author
    as though they were settled."""
    assert seed(book) == 1
    assert "not signed off" in capsys.readouterr().err
    assert not outline_of(book, "ch-what").exists()


# --- what it writes ------------------------------------------------------


def test_seeding_writes_one_heading_per_declared_section(book, capsys):
    spec.main(["sign", str(book)])
    capsys.readouterr()
    assert seed(book) == 0
    text = outline_of(book, "ch-what").read_text(encoding="utf-8")
    assert "## The model half" in text
    assert "## The data half" in text


def test_seeding_leaves_the_brief_for_whoever_drafts_it(book):
    """Structure only. A brief the spec invented would be the book track
    writing content, which is the genre skill's job."""
    spec.main(["sign", str(book)])
    seed(book)
    text = outline_of(book, "ch-what").read_text(encoding="utf-8")
    assert "brief:" not in text.split("-->")[-1]
    assert "claim:" not in text.split("-->")[-1]


def test_a_chapter_described_only_at_chapter_level_is_not_seeded(book):
    """The retrofitted shape names no structure worth handing over."""
    spec.main(["sign", str(book)])
    seed(book)
    assert not outline_of(book, "ch-cost").exists()


# --- it cannot destroy work ----------------------------------------------


def test_seeding_twice_changes_nothing_the_second_time(book, capsys):
    spec.main(["sign", str(book)])
    seed(book)
    before = outline_of(book, "ch-what").read_text(encoding="utf-8")
    capsys.readouterr()
    assert seed(book) == 0
    assert outline_of(book, "ch-what").read_text(encoding="utf-8") == before
    assert "unchanged" in capsys.readouterr().out


def test_a_heading_somebody_filled_in_is_never_rewritten(book):
    spec.main(["sign", str(book)])
    seed(book)
    path = outline_of(book, "ch-what")
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "## The model half", "## The model half\n\nbrief: mine, hand-written."
        ),
        encoding="utf-8",
    )
    seed(book)
    assert "brief: mine, hand-written." in path.read_text(encoding="utf-8")


def test_a_section_added_to_the_spec_later_is_appended(book, capsys):
    spec.main(["sign", str(book)])
    seed(book)
    spec.spec_path(book).write_text(
        SPEC.replace(
            "### What a twin costs {#ch-cost}",
            "#### Where the two meet {#sec-meet}\n\nEstablish the join.\n\n"
            "### What a twin costs {#ch-cost}",
        ),
        encoding="utf-8",
    )
    spec.main(["sign", str(book)])
    capsys.readouterr()
    assert seed(book) == 0
    text = outline_of(book, "ch-what").read_text(encoding="utf-8")
    assert "## Where the two meet" in text
    assert text.count("## The model half") == 1


def test_appending_to_a_file_with_no_trailing_newline_does_not_glue_the_heading(book):
    """A hand-edited `outline.md` need not end in a newline, and a
    heading joined to the last line of prose is not a heading at all."""
    spec.main(["sign", str(book)])
    seed(book)
    path = outline_of(book, "ch-what")
    path.write_text("## The model half\n\nbrief: mine.", encoding="utf-8")
    spec.spec_path(book).write_text(
        SPEC.replace(
            "### What a twin costs {#ch-cost}",
            "#### Where the two meet {#sec-meet}\n\nEstablish the join.\n\n"
            "### What a twin costs {#ch-cost}",
        ),
        encoding="utf-8",
    )
    spec.main(["sign", str(book)])
    seed(book)
    # A blank line, not merely a newline: a heading on the line directly
    # below prose is what markdownlint's MD022 refuses, and what several
    # Markdown parsers decline to read as a heading at all.
    assert "brief: mine.\n\n## " in path.read_text(encoding="utf-8")
    assert "## Where the two meet" in path.read_text(encoding="utf-8")


# --- reporting -----------------------------------------------------------


def test_dry_run_says_what_it_would_write_and_writes_nothing(book, capsys):
    spec.main(["sign", str(book)])
    capsys.readouterr()
    assert seed(book, "--dry-run") == 0
    assert "would" in capsys.readouterr().out
    assert not outline_of(book, "ch-what").exists()


def test_seeding_refuses_a_spec_that_does_not_parse(book, capsys):
    spec.spec_path(book).write_text("# Book\n\n## Part I\n", encoding="utf-8")
    assert seed(book) == 1
    assert "{#id}" in capsys.readouterr().err

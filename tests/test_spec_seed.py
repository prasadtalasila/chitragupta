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


BOOK_SPEC = SPEC


def outline_of(book, chapter_id):
    return dossier_dir(book / f"{chapter_id}.md") / OUTLINE_MD


def seed(book, *extra):
    return spec.main(["seed", str(book), "--genre", "textbook-chapter", *extra])


def test_seeding_refuses_an_outline_nobody_signed_off(book, capsys):
    assert seed(book) == 1
    assert "not signed off" in capsys.readouterr().err
    assert not outline_of(book, "ch-what").exists()


def test_seeding_writes_one_heading_per_declared_section(book, capsys):
    spec.main(["sign", str(book)])
    capsys.readouterr()
    assert seed(book) == 0
    text = outline_of(book, "ch-what").read_text(encoding="utf-8")
    assert "## The model half" in text
    assert "## The data half" in text


def test_seeding_leaves_the_brief_for_whoever_drafts_it(book):
    spec.main(["sign", str(book)])
    seed(book)
    text = outline_of(book, "ch-what").read_text(encoding="utf-8")
    assert "brief:" not in text.split("-->")[-1]
    assert "claim:" not in text.split("-->")[-1]


def test_a_chapter_described_only_at_chapter_level_is_not_seeded(book):
    spec.main(["sign", str(book)])
    seed(book)
    assert not outline_of(book, "ch-cost").exists()


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
    assert "brief: mine.\n\n## " in path.read_text(encoding="utf-8")
    assert "## Where the two meet" in path.read_text(encoding="utf-8")


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


SECOND_DESCRIBED = """
### What a twin decides {#ch-decide}

#### The question {#sec-question}

Establish the question.

#### The answer {#sec-answer}

Establish the answer.
"""


def test_a_later_escaping_chapter_refuses_before_any_chapter_is_seeded(book, tmp_path, capsys):
    spec_file = spec.spec_path(book)
    spec_file.write_text(SPEC + SECOND_DESCRIBED, encoding="utf-8")
    spec.main(["sign", str(book)])
    outside = tmp_path / "elsewhere.md"
    outside.write_text("# What a twin decides\n", encoding="utf-8")
    (book / "ch-decide.md").symlink_to(outside)
    capsys.readouterr()
    assert seed(book) == 1
    assert "ch-decide.md" in capsys.readouterr().err
    assert not outline_of(book, "ch-what").exists()

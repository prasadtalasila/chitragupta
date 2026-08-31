"""What `unit accept` refuses once alignment exists, and what `status` says.

Now that a chapter is both the authored document and the acceptance unit,
the chapter being accepted is the very file `spec align` reads -- so
"these headings drifted" and "this is what you are accepting" are two
statements about one artifact rather than two.
"""

import json

import pytest

from chitragupta import spec, unit

SPEC = """# Composable Digital Twins

## Part I: Foundations {#part-1}

### What a twin is {#ch-what}

#### The model half {#sec-model}

Establish the model.

#### The data half {#sec-data}

Establish the link.

### What a twin costs {#ch-cost}

#### The bill {#sec-bill}

Who pays.

#### The savings {#sec-savings}

What comes back.
"""

CHAPTER = """# What a twin is

## The model half

A paragraph citing @smith_example_2024.

## The data half

More prose.
"""


@pytest.fixture
def book(isolated_config):
    path = isolated_config.DRAFTS_DIR / "twins"
    spec_file = spec.spec_path(path)
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(SPEC, encoding="utf-8")
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def corpus(ledger_con, make_ref):
    from chitragupta import ledger

    ledger.upsert_reference(ledger_con, make_ref(citekey="smith_example_2024"))
    ledger_con.commit()
    return ledger_con


def write(book, name, text):
    (book / f"{name}.md").write_text(text, encoding="utf-8")


def accept(book, unit_id):
    return unit.main(["accept", str(book), unit_id, "--source", "smith_example_2024"])


# --- alignment binds acceptance ------------------------------------------


def test_accept_refuses_a_chapter_whose_headings_drifted(book, corpus, capsys):
    spec.main(["sign", str(book)])
    write(book, "ch-what", CHAPTER.replace("## The data half", "## Something else entirely"))
    capsys.readouterr()
    assert accept(book, "ch-what") == 1
    assert "no longer matches the outline" in capsys.readouterr().err
    assert not unit.record_path(book, "ch-what").is_file()


def test_accept_takes_a_chapter_that_aligns(book, corpus, capsys):
    spec.main(["sign", str(book)])
    write(book, "ch-what", CHAPTER)
    capsys.readouterr()
    assert accept(book, "ch-what") == 0
    assert unit.record_path(book, "ch-what").is_file()


def test_another_chapter_being_unwritten_does_not_block_this_one(book, corpus, capsys):
    """A book is drafted chapter by chapter. `align` reports `ch-cost` as
    not written yet, and that must not hold up the chapter that is."""
    spec.main(["sign", str(book)])
    write(book, "ch-what", CHAPTER)
    capsys.readouterr()
    assert accept(book, "ch-what") == 0


def test_reordered_sections_are_named_in_the_refusal(book, corpus, capsys):
    spec.main(["sign", str(book)])
    write(
        book,
        "ch-what",
        "# What a twin is\n\n## The data half\n\nP @smith_example_2024.\n\n"
        "## The model half\n\nP.\n",
    )
    capsys.readouterr()
    assert accept(book, "ch-what") == 1
    assert "out of order" in capsys.readouterr().err


# --- status cross-reports the dossier ------------------------------------


def test_status_names_what_the_dossier_says_about_the_same_prose(book, corpus, capsys):
    spec.main(["sign", str(book)])
    write(book, "ch-what", CHAPTER)
    accept(book, "ch-what")
    capsys.readouterr()
    unit.main(["status", str(book)])
    assert "dossier: no dossier" in capsys.readouterr().out


def test_status_as_json_carries_the_same_answer(book, corpus, capsys):
    spec.main(["sign", str(book)])
    write(book, "ch-what", CHAPTER)
    accept(book, "ch-what")
    capsys.readouterr()
    unit.main(["status", str(book), "--json"])
    payload = json.loads(capsys.readouterr().out)
    entry = [u for u in payload["units"] if u["id"] == "ch-what"][0]
    assert entry["state"] == "accepted"
    assert entry["fingerprint"] == "no dossier"


def test_status_says_when_a_stamped_fingerprint_agrees(book, corpus, capsys):
    from chitragupta.dossier import _create, _draft_fingerprint

    spec.main(["sign", str(book)])
    write(book, "ch-what", CHAPTER)
    _create.init(book / "ch-what.md", "textbook-chapter")
    _draft_fingerprint.stamp(book / "ch-what.md")
    capsys.readouterr()
    unit.main(["status", str(book)])
    assert "dossier: agrees" in capsys.readouterr().out


def test_status_says_when_a_stamped_fingerprint_disagrees(book, corpus, capsys):
    from chitragupta.dossier import _create, _draft_fingerprint

    spec.main(["sign", str(book)])
    write(book, "ch-what", CHAPTER)
    _create.init(book / "ch-what.md", "textbook-chapter")
    _draft_fingerprint.stamp(book / "ch-what.md")
    write(book, "ch-what", CHAPTER.replace("More prose.", "Rewritten prose."))
    capsys.readouterr()
    unit.main(["status", str(book)])
    assert "dossier: disagrees" in capsys.readouterr().out


def test_status_says_when_a_dossier_exists_but_nobody_stamped(book, corpus, capsys):
    from chitragupta.dossier import _create

    spec.main(["sign", str(book)])
    write(book, "ch-what", CHAPTER)
    _create.init(book / "ch-what.md", "textbook-chapter")
    capsys.readouterr()
    unit.main(["status", str(book)])
    assert "dossier: not stamped" in capsys.readouterr().out


def test_status_says_when_a_stamped_draft_has_since_been_deleted(book, corpus, capsys):
    from chitragupta.dossier import _create, _draft_fingerprint

    spec.main(["sign", str(book)])
    write(book, "ch-what", CHAPTER)
    _create.init(book / "ch-what.md", "textbook-chapter")
    _draft_fingerprint.stamp(book / "ch-what.md")
    (book / "ch-what.md").unlink()
    capsys.readouterr()
    unit.main(["status", str(book)])
    assert "dossier: stamped, no draft" in capsys.readouterr().out

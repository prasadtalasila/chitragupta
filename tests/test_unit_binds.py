"""What `unit accept` refuses once alignment exists, and what `status` says.

Two completions of #472, both scoped to what a section-unit book can
already express:

- a chapter whose headings have drifted from the outline a human approved
  cannot have its units accepted -- acceptance records "this prose against
  that outline", and a drifted chapter makes that record untrue;
- `unit status` names what the *dossier* says about the same prose, so
  "stale: draft changed since accepted" stops being the whole story on a
  book where nothing was ever stamped.
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


# --- alignment binds acceptance ------------------------------------------


def test_accept_refuses_a_unit_whose_chapter_drifted(book, corpus, capsys):
    spec.main(["sign", str(book)])
    write(book, "ch-what", CHAPTER.replace("## The data half", "## Something else entirely"))
    write(book, "sec-model", "A paragraph citing @smith_example_2024.\n")
    capsys.readouterr()
    assert unit.main(["accept", str(book), "sec-model", "--source", "smith_example_2024"]) == 1
    assert "no longer matches the outline" in capsys.readouterr().err
    assert not unit.record_path(book, "sec-model").is_file()


def test_accept_takes_a_unit_whose_chapter_aligns(book, corpus, capsys):
    spec.main(["sign", str(book)])
    write(book, "ch-what", CHAPTER)
    write(book, "sec-model", "A paragraph citing @smith_example_2024.\n")
    capsys.readouterr()
    assert unit.main(["accept", str(book), "sec-model", "--source", "smith_example_2024"]) == 0
    assert unit.record_path(book, "sec-model").is_file()


def test_a_chapter_nobody_has_written_yet_does_not_block_acceptance(book, corpus, capsys):
    """`align` reports an unwritten chapter, but a book is drafted unit by
    unit -- refusing every unit until the whole chapter exists would make
    the first one impossible to accept."""
    spec.main(["sign", str(book)])
    write(book, "sec-model", "A paragraph citing @smith_example_2024.\n")
    capsys.readouterr()
    assert unit.main(["accept", str(book), "sec-model", "--source", "smith_example_2024"]) == 0


# --- status cross-reports the dossier ------------------------------------


def test_status_names_what_the_dossier_says_about_the_same_prose(book, corpus, capsys):
    spec.main(["sign", str(book)])
    write(book, "sec-model", "A paragraph citing @smith_example_2024.\n")
    unit.main(["accept", str(book), "sec-model", "--source", "smith_example_2024"])
    capsys.readouterr()
    unit.main(["status", str(book)])
    assert "dossier: no dossier" in capsys.readouterr().out


def test_status_as_json_carries_the_same_answer(book, corpus, capsys):
    spec.main(["sign", str(book)])
    write(book, "sec-model", "A paragraph citing @smith_example_2024.\n")
    unit.main(["accept", str(book), "sec-model", "--source", "smith_example_2024"])
    capsys.readouterr()
    unit.main(["status", str(book), "--json"])
    payload = json.loads(capsys.readouterr().out)
    entry = [u for u in payload["units"] if u["id"] == "sec-model"][0]
    assert entry["state"] == "accepted"
    assert entry["fingerprint"] == "no dossier"


def test_status_says_when_a_stamped_fingerprint_agrees(book, corpus, capsys):
    from chitragupta.dossier import _create, _draft_fingerprint

    spec.main(["sign", str(book)])
    write(book, "sec-model", "A paragraph citing @smith_example_2024.\n")
    _create.init(book / "sec-model.md", "textbook-chapter")
    _draft_fingerprint.stamp(book / "sec-model.md")
    capsys.readouterr()
    unit.main(["status", str(book)])
    assert "dossier: agrees" in capsys.readouterr().out


def test_status_says_when_a_stamped_fingerprint_disagrees(book, corpus, capsys):
    from chitragupta.dossier import _create, _draft_fingerprint

    spec.main(["sign", str(book)])
    write(book, "sec-model", "A paragraph citing @smith_example_2024.\n")
    _create.init(book / "sec-model.md", "textbook-chapter")
    _draft_fingerprint.stamp(book / "sec-model.md")
    write(book, "sec-model", "Rewritten, citing @smith_example_2024.\n")
    capsys.readouterr()
    unit.main(["status", str(book)])
    assert "dossier: disagrees" in capsys.readouterr().out


def test_status_says_when_a_dossier_exists_but_nobody_stamped(book, corpus, capsys):
    from chitragupta.dossier import _create

    spec.main(["sign", str(book)])
    write(book, "sec-model", "A paragraph citing @smith_example_2024.\n")
    _create.init(book / "sec-model.md", "textbook-chapter")
    capsys.readouterr()
    unit.main(["status", str(book)])
    assert "dossier: not stamped" in capsys.readouterr().out


def test_reordered_sections_are_named_in_the_refusal(book, corpus, capsys):
    spec.main(["sign", str(book)])
    write(
        book,
        "ch-what",
        "# What a twin is\n\n## The data half\n\nP.\n\n## The model half\n\nP.\n",
    )
    write(book, "sec-model", "A paragraph citing @smith_example_2024.\n")
    capsys.readouterr()
    assert unit.main(["accept", str(book), "sec-model", "--source", "smith_example_2024"]) == 1
    assert "out of order" in capsys.readouterr().err


def test_status_says_when_a_stamped_draft_has_since_been_deleted(book, corpus, capsys):
    from chitragupta.dossier import _create, _draft_fingerprint

    spec.main(["sign", str(book)])
    write(book, "sec-model", "A paragraph citing @smith_example_2024.\n")
    _create.init(book / "sec-model.md", "textbook-chapter")
    _draft_fingerprint.stamp(book / "sec-model.md")
    (book / "sec-model.md").unlink()
    capsys.readouterr()
    unit.main(["status", str(book)])
    assert "dossier: stamped, no draft" in capsys.readouterr().out

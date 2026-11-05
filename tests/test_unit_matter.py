"""Units in the front matter, the appendices and the back matter (#1137).

Three behaviours a book with a preface depends on. A chapter with no
`####` sections is a unit of its own: before #1137 it was silently no
unit at all, so a preface could never be accepted. The four generated
pages are never units, because nobody writes them. And a unit taken out
of the outline after it was accepted is listed, never deleted -- the
prose is the author's, and the record is the evidence it was approved.
"""

import json

import pytest

from chitragupta import spec, unit

OUTLINE = """# Composable Twins

- author: Prasad Talasila

## Front matter {#front}

### Preface {#preface}

Why this book exists. You write this page yourself.

## Part I {#part-i}

### What a twin costs {#ch-cost}

Declared at chapter level only.

### What a twin is {#ch-what}

#### The model half {#sec-model}

#### The data half {#sec-data}

## Appendices {#appendices}

### Installing the toolchain {#app-install}

## Back matter {#back}

### Glossary {#glossary}

### List of Symbols {#symbols}

### List of Figures {#figures}

### List of Tables {#tables}
"""


@pytest.fixture
def book(isolated_config):
    path = isolated_config.DRAFTS_DIR / "twins"
    spec_file = spec.spec_path(path)
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(OUTLINE, encoding="utf-8")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _accept(book, unit_id, text):
    (book / f"{unit_id}.md").write_text(text, encoding="utf-8")
    return unit.main(["accept", str(book), unit_id])


def test_a_chapter_with_no_sections_is_its_own_unit(book):
    ids = [entry["id"] for entry in unit.acceptance_units(book)]
    assert ids == ["preface", "ch-cost", "ch-what", "app-install"]


def test_no_generated_page_is_a_unit(book):
    ids = {entry["id"] for entry in unit.acceptance_units(book)}
    assert ids.isdisjoint(spec.GENERATED)


def test_a_hand_written_preface_is_accepted_like_any_chapter(book, example_ledger, capsys):
    spec.main(["sign", str(book)])
    assert _accept(book, "preface", "# Preface\n\nWhy I wrote this book.\n") == 0
    capsys.readouterr()
    unit.main(["status", str(book)])
    rows = {line.split()[0]: line.split()[1] for line in capsys.readouterr().out.splitlines()[:4]}
    assert rows["preface"] == "accepted"


def test_a_unit_removed_from_the_outline_is_listed_and_kept(book, example_ledger, capsys):
    spec.main(["sign", str(book)])
    assert _accept(book, "ch-cost", "# What a twin costs\n\nThe bill.\n") == 0
    spec.spec_path(book).write_text(
        OUTLINE.replace(
            "### What a twin costs {#ch-cost}\n\nDeclared at chapter level only.\n\n", ""
        ),
        encoding="utf-8",
    )
    spec.main(["sign", str(book)])
    capsys.readouterr()
    code = unit.main(["status", str(book)])
    out = capsys.readouterr().out
    assert (
        "accepted, but no longer in the outline: ch-cost (records and prose are left on disk)"
        in out
    )
    assert "ch-cost" not in out.split("unit(s) accepted")[0], "not a row of the table"
    assert code == 1, "the exit code still answers for the units the outline holds"
    assert unit.record_path(book, "ch-cost").is_file()
    assert (book / "ch-cost.md").is_file()

    unit.main(["status", str(book), "--json"])
    assert json.loads(capsys.readouterr().out)["orphaned"] == ["ch-cost"]


def test_a_book_with_no_orphans_prints_no_orphan_line(book, capsys):
    unit.main(["status", str(book)])
    assert "no longer in the outline" not in capsys.readouterr().out
    unit.main(["status", str(book), "--json"])
    assert json.loads(capsys.readouterr().out)["orphaned"] == []

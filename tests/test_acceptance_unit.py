"""The acceptance unit, now that it is not the structural one.

`spec.md` declares *structure* -- sections a human approves before any
prose exists, and what `spec align` checks a draft against. `unit accept`
records an *artifact* -- a file the citation gate can run on and whose
prose can be digested. Before #472 those coincided, because a book was
one file per section. A chapter is now one authored document with its
sections as headings inside it, so they no longer can.

The asymmetry is load-bearing rather than untidy: alignment only has
content while the outline is finer than the file. Collapsing the two in
either direction makes "did you write what you said you would?" a
question with no possible answer.

What is pinned here is that the acceptance unit follows the outline's own
granularity, so a book retrofitted from earlier prose -- one section per
chapter, carrying the chapter's title -- keeps working unchanged.
"""

import pytest

from chitragupta import spec, unit

FRESH = """# Composable Digital Twins

## Part I: Foundations {#part-1}

### What a twin is {#ch-what}

#### The model half {#sec-model}

Establish the model.

#### The data half {#sec-data}

Establish the link.
"""

RETROFIT = """# Digital Twins

## Part I {#part-1}

### Chapter 1 -- Why anyone pays {#ch-01}

#### Chapter 1 -- Why anyone pays {#01-why-anyone-pays}

One chapter, one unit, drafted before this outline existed.
"""

CHAPTER = """# What a twin is

## The model half

A paragraph citing @smith_example_2024.

## The data half

More prose.
"""


def make_book(isolated_config, text):
    path = isolated_config.DRAFTS_DIR / "twins"
    spec_file = spec.spec_path(path)
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(text, encoding="utf-8")
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def fresh(isolated_config):
    return make_book(isolated_config, FRESH)


@pytest.fixture
def retrofit(isolated_config):
    return make_book(isolated_config, RETROFIT)


@pytest.fixture
def corpus(ledger_con, make_ref):
    from chitragupta import ledger

    ledger.upsert_reference(ledger_con, make_ref(citekey="smith_example_2024"))
    ledger_con.commit()
    return ledger_con


# --- which unit gets accepted --------------------------------------------


def test_a_section_described_chapter_is_the_acceptance_unit(fresh):
    ids = [entry["id"] for entry in unit.acceptance_units(fresh)]
    assert ids == ["ch-what"]


def test_a_retrofitted_chapter_leaves_its_section_as_the_unit(retrofit):
    """The section id is the filename there, so it is still what is
    accepted -- every book drafted before this track keeps working."""
    ids = [entry["id"] for entry in unit.acceptance_units(retrofit)]
    assert ids == ["01-why-anyone-pays"]


def test_the_structural_units_are_unchanged_by_any_of_this(fresh):
    """`sections()` still answers "what does the outline declare", which
    is a different question from "what gets accepted"."""
    assert [entry["id"] for entry in unit.sections(fresh)] == ["sec-model", "sec-data"]


# --- the contract ---------------------------------------------------------


def test_a_contract_can_be_built_for_a_chapter(fresh):
    built = unit.contract(fresh, "ch-what", [])
    assert built["title"] == "What a twin is"
    assert built["draft"].endswith("twins/ch-what.md")
    assert built["ancestors"] == ["part-1"]


def test_a_structural_section_is_refused_by_name(fresh):
    with pytest.raises(unit.UnitError, match="not a unit"):
        unit.contract(fresh, "sec-model", [])


def test_a_part_is_still_refused(fresh):
    with pytest.raises(unit.UnitError, match="not a unit"):
        unit.contract(fresh, "part-1", [])


# --- sign-off resolves the unit's own chapter -----------------------------


def test_a_chapter_reads_its_own_sign_off_not_its_parts(fresh):
    """Resolved from the unit's kind. Reading "the last ancestor" would
    give the *part*, which is never a key in the approved set, so every
    chapter would report unsigned forever."""
    spec.main(["sign", str(fresh)])
    assert unit.contract(fresh, "ch-what", [])["signed_off"] is True


def test_a_retrofitted_section_still_reads_its_chapters_sign_off(retrofit):
    spec.main(["sign", str(retrofit)])
    assert unit.contract(retrofit, "01-why-anyone-pays", [])["signed_off"] is True


def test_editing_one_chapter_does_not_unsign_another(isolated_config):
    book = make_book(
        isolated_config,
        FRESH.replace(
            "#### The data half {#sec-data}\n\nEstablish the link.\n",
            "#### The data half {#sec-data}\n\nEstablish the link.\n\n"
            "### What a twin costs {#ch-cost}\n\n#### The bill {#sec-bill}\n\nWho pays.\n",
        ),
    )
    spec.main(["sign", str(book)])
    spec.spec_path(book).write_text(
        spec.spec_path(book).read_text(encoding="utf-8").replace("Who pays.", "Who pays, exactly."),
        encoding="utf-8",
    )
    assert unit.contract(book, "ch-cost", [])["signed_off"] is False
    assert unit.contract(book, "ch-what", [])["signed_off"] is True


# --- accepting a chapter --------------------------------------------------


def test_a_chapter_is_accepted_as_one_document(fresh, corpus, capsys):
    spec.main(["sign", str(fresh)])
    (fresh / "ch-what.md").write_text(CHAPTER, encoding="utf-8")
    capsys.readouterr()
    assert unit.main(["accept", str(fresh), "ch-what", "--source", "smith_example_2024"]) == 0
    assert unit.record_path(fresh, "ch-what").is_file()
    assert unit.state(fresh, "ch-what") == "accepted"


def test_status_lists_the_acceptance_units_not_the_structural_ones(fresh, capsys):
    unit.main(["status", str(fresh)])
    out = capsys.readouterr().out
    assert "ch-what" in out
    assert "sec-model" not in out

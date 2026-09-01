"""Generation units: the contract, its input digest, and acceptance.

What is worth pinning here is what makes a unit independently
regenerable: the input digest covers the spec slice *and* the sources, so
an edit to either says so; acceptance records what was accepted rather
than asserting it; and `status` can tell "never written" from "written
but not accepted" from "accepted and since changed".
"""

import json

import pytest

from chitragupta import spec, unit


GOOD_SPEC = """# Composable Digital Twins

## Part I: Foundations {#part-foundations}

### The model half {#ch-model}

Establish that a twin is a model plus a live data link.

#### What a model is {#sec-model-what}

The modelling half.

#### What it leaves out {#sec-model-limits}

The abstraction half.

### The data half {#ch-data}

Establish the link, and why it is the hard half.

#### The link {#sec-data-link}

The wiring half.

#### Its failure modes {#sec-data-fail}

The unreliable half.
"""


@pytest.fixture
def book(isolated_config):
    path = isolated_config.DRAFTS_DIR / "twins"
    spec_file = spec.spec_path(path)
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(GOOD_SPEC, encoding="utf-8")
    return path


# A second chapter, so "one chapter moved" and "the book moved" are
# distinguishable -- which is the whole of #465.
TWO_CHAPTER_SPEC = (
    GOOD_SPEC
    + """
### Chapter 2: What a twin costs {#ch-cost}

#### The bill {#sec-bill}

Establish who pays, and for which half.
"""
)


@pytest.fixture
def two_chapter_book(isolated_config):
    path = isolated_config.DRAFTS_DIR / "twins"
    spec_file = spec.spec_path(path)
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(TWO_CHAPTER_SPEC, encoding="utf-8")
    return path


def sign_off(book):
    spec.main(["sign", str(book)])


# What each chapter declares, so a written draft matches its outline.
# `unit accept` refuses a chapter whose headings drifted (#472), and this
# module is about contracts and digests rather than alignment -- a draft
# that does not match would fail every test here for the wrong reason.
DECLARED = {
    "ch-model": ("What a model is", "What it leaves out"),
    "ch-data": ("The link", "Its failure modes"),
    "ch-cost": ("The bill",),
}


def write_unit_draft(book, unit_id, body=None):
    """A chapter carrying the sections its outline declares.

    `body`, when given, replaces the prose under every heading rather than
    the whole file -- the headings have to stay for the draft to remain
    aligned with the outline it is accepted against.
    """
    prose = body or "A paragraph citing @smith_example_2024.\n"
    text = f"# {unit_id}\n\n" + "".join(
        f"## {heading}\n\n{prose}\n" for heading in DECLARED.get(unit_id, ())
    )
    path = book / f"{unit_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def corpus(ledger_con, make_ref):
    """One real ledger row, so the citation gate `accept` runs has
    something to check a citekey against."""
    from chitragupta import ledger

    ledger.upsert_reference(ledger_con, make_ref(citekey="smith_example_2024"))
    ledger_con.commit()
    return ledger_con


# --- the contract --------------------------------------------------------


def test_a_contract_carries_the_spec_slice_and_the_sources(book):
    contract = unit.contract(book, "ch-model", ["smith_example_2024"])
    assert contract["title"] == "The model half"
    assert contract["ancestors"] == ["part-foundations"]
    assert contract["brief"].startswith("Establish that a twin")
    assert contract["sources"] == ["smith_example_2024"]
    assert contract["draft"].endswith("twins/ch-model.md")


def test_only_a_section_is_a_generation_unit(book):
    """A part is not an acceptance unit -- asking for its contract is a
    mistake worth reporting, not an empty contract."""
    with pytest.raises(unit.UnitError, match="not a unit"):
        unit.contract(book, "part-foundations", [])


def test_an_unknown_unit_is_refused_by_name(book):
    with pytest.raises(unit.UnitError, match="sec-nope"):
        unit.contract(book, "sec-nope", [])


def test_a_spec_that_does_not_parse_is_refused(book):
    spec.spec_path(book).write_text("# Book\n\n## Part I\n", encoding="utf-8")
    with pytest.raises(unit.UnitError, match="does not parse"):
        unit.contract(book, "ch-model", [])


def test_a_book_with_no_outline_at_all_is_refused_by_name(isolated_config):
    with pytest.raises(unit.UnitError, match="spec init"):
        unit.contract(isolated_config.DRAFTS_DIR / "unplanned", "ch-model", [])


def test_a_book_outside_content_drafts_is_refused_by_the_cli(isolated_config, tmp_path, capsys):
    """`spec`'s own refusal, surfaced through this command rather than
    escaping as a traceback."""
    assert unit.main(["status", str(tmp_path / "elsewhere")]) == 1
    assert "not under" in capsys.readouterr().err


def test_the_input_digest_changes_when_the_brief_changes(book):
    before = unit.input_digest(unit.contract(book, "ch-model", []))
    spec.spec_path(book).write_text(
        GOOD_SPEC.replace("a live data link", "a live data link, and nothing else"),
        encoding="utf-8",
    )
    assert unit.input_digest(unit.contract(book, "ch-model", [])) != before


def test_the_input_digest_changes_when_the_sources_change(book):
    contract = unit.contract(book, "ch-model", [])
    with_source = unit.contract(book, "ch-model", ["smith_example_2024"])
    assert unit.input_digest(contract) != unit.input_digest(with_source)


def test_the_input_digest_ignores_the_order_sources_were_given_in(book):
    first = unit.contract(book, "ch-model", ["b_2020", "a_2019"])
    second = unit.contract(book, "ch-model", ["a_2019", "b_2020"])
    assert unit.input_digest(first) == unit.input_digest(second)


def test_a_units_own_prose_is_not_part_of_its_input_digest(book):
    """Inputs only. A digest that moved when the output did could never
    answer "does this unit need regenerating?"."""
    before = unit.input_digest(unit.contract(book, "ch-model", []))
    write_unit_draft(book, "ch-model")
    assert unit.input_digest(unit.contract(book, "ch-model", [])) == before


def test_a_tex_unit_is_found_where_a_md_one_would_be(book):
    (book).mkdir(parents=True, exist_ok=True)
    (book / "ch-model.tex").write_text("A fragment.\n", encoding="utf-8")
    assert unit.contract(book, "ch-model", [])["draft"].endswith(".tex")


# --- the contract command ------------------------------------------------


def test_contract_prints_the_slice_and_the_digest(book, capsys):
    assert unit.main(["contract", str(book), "ch-model"]) == 0
    out = capsys.readouterr().out
    assert "The model half" in out
    assert unit.input_digest(unit.contract(book, "ch-model", [])) in out
    assert "not signed off" in out


def test_contract_as_json_is_what_a_skill_reads(book, capsys):
    assert (
        unit.main(["contract", str(book), "ch-model", "--source", "smith_example_2024", "--json"])
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["sources"] == ["smith_example_2024"]
    assert payload["input_digest"] == unit.input_digest(
        unit.contract(book, "ch-model", ["smith_example_2024"])
    )
    assert payload["signed_off"] is False


def test_contract_refuses_a_unit_the_outline_does_not_hold(book, capsys):
    assert unit.main(["contract", str(book), "sec-nope"]) == 1
    assert "sec-nope" in capsys.readouterr().err


# --- accept --------------------------------------------------------------


def test_accept_records_the_unit_and_what_it_cites(book, corpus, capsys):
    sign_off(book)
    write_unit_draft(book, "ch-model")
    capsys.readouterr()
    assert unit.main(["accept", str(book), "ch-model", "--source", "smith_example_2024"]) == 0
    record = json.loads(unit.record_path(book, "ch-model").read_text(encoding="utf-8"))
    assert record["unit"] == "ch-model"
    assert record["citekeys"] == ["smith_example_2024"]
    assert record["sources"] == ["smith_example_2024"]
    assert record["input_digest"] == unit.input_digest(
        unit.contract(book, "ch-model", ["smith_example_2024"])
    )


def test_accept_refuses_an_outline_nobody_signed_off(book, corpus, capsys):
    write_unit_draft(book, "ch-model")
    assert unit.main(["accept", str(book), "ch-model"]) == 1
    assert "signed off" in capsys.readouterr().err
    assert not unit.record_path(book, "ch-model").exists()


def test_accept_still_works_on_a_chapter_nobody_edited(two_chapter_book, corpus, capsys):
    """Issue #465. Revising one chapter's brief used to flip `signed_off`
    for every unit in the book, so a 15-chapter book froze acceptance
    everywhere while one chapter sat half-revised."""
    book = two_chapter_book
    sign_off(book)
    write_unit_draft(book, "ch-cost")
    path = spec.spec_path(book)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "Establish that a twin is", "Establish plainly that a twin is"
        ),
        encoding="utf-8",
    )
    capsys.readouterr()
    assert unit.main(["accept", str(book), "ch-cost", "--source", "smith_example_2024"]) == 0
    assert unit.record_path(book, "ch-cost").is_file()


def test_accept_refuses_a_unit_in_the_chapter_that_was_edited(two_chapter_book, corpus, capsys):
    book = two_chapter_book
    sign_off(book)
    write_unit_draft(book, "ch-model")
    path = spec.spec_path(book)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "Establish that a twin is", "Establish plainly that a twin is"
        ),
        encoding="utf-8",
    )
    capsys.readouterr()
    assert unit.main(["accept", str(book), "ch-model"]) == 1
    assert "signed off" in capsys.readouterr().err


def test_a_book_signed_before_chapter_digests_existed_still_accepts(
    two_chapter_book, corpus, capsys
):
    """The retrofitted books on disk carry a whole-book digest and no
    chapter lines. They must keep working, and keep refusing once the
    outline moves at all -- there is nothing finer to fall back on."""
    book = two_chapter_book
    write_unit_draft(book, "ch-model")
    text = spec.spec_path(book).read_text(encoding="utf-8")
    spec.signoff_path(book).parent.mkdir(parents=True, exist_ok=True)
    spec.signoff_path(book).write_text(
        f"# Sign-off\n\n- spec digest: `{spec.digest(text)}`\n", encoding="utf-8"
    )
    capsys.readouterr()
    assert unit.main(["accept", str(book), "ch-model", "--source", "smith_example_2024"]) == 0


def test_accept_refuses_a_unit_that_has_no_draft(book, capsys):
    sign_off(book)
    capsys.readouterr()
    assert unit.main(["accept", str(book), "ch-model"]) == 1
    assert "no draft" in capsys.readouterr().err


def test_accept_refuses_a_draft_the_citation_gate_rejects(book, corpus, capsys):
    """The gate is invoked, not re-implemented: an unaccepted unit is one
    the project's one gate already refuses."""
    sign_off(book)
    write_unit_draft(book, "ch-model", "Citing @not_in_the_ledger_2030.\n")
    capsys.readouterr()
    assert unit.main(["accept", str(book), "ch-model"]) == 1
    assert "gate" in capsys.readouterr().err
    assert not unit.record_path(book, "ch-model").exists()


def test_accepting_the_same_unit_twice_writes_the_same_bytes(book, corpus):
    sign_off(book)
    write_unit_draft(book, "ch-model")
    unit.main(["accept", str(book), "ch-model"])
    first = unit.record_path(book, "ch-model").read_text(encoding="utf-8")
    unit.main(["accept", str(book), "ch-model"])
    assert unit.record_path(book, "ch-model").read_text(encoding="utf-8") == first


# --- status --------------------------------------------------------------


def test_status_reports_every_section_and_refuses_while_any_is_unwritten(book, capsys):
    sign_off(book)
    capsys.readouterr()
    assert unit.main(["status", str(book)]) == 1
    out = capsys.readouterr().out
    assert "ch-model" in out and "ch-data" in out
    assert out.count("unwritten") == 2


def test_a_written_unit_nobody_accepted_reads_as_drafted(book, capsys):
    sign_off(book)
    write_unit_draft(book, "ch-model")
    capsys.readouterr()
    assert unit.main(["status", str(book)]) == 1
    assert "drafted" in capsys.readouterr().out


def test_a_book_whose_units_are_all_accepted_passes(book, corpus, capsys):
    sign_off(book)
    for unit_id in ("ch-model", "ch-data"):
        write_unit_draft(book, unit_id)
        unit.main(["accept", str(book), unit_id])
    capsys.readouterr()
    assert unit.main(["status", str(book)]) == 0
    out = capsys.readouterr().out
    # The state is the second column; a `dossier:` one follows it (#472).
    assert [line.split()[1] for line in out.splitlines() if line.startswith("  ch-")] == [
        "accepted",
        "accepted",
    ]
    assert "2 of 2 unit(s) accepted and current." in out


def test_an_edited_brief_makes_an_accepted_unit_stale(book, corpus, capsys):
    sign_off(book)
    write_unit_draft(book, "ch-model")
    unit.main(["accept", str(book), "ch-model"])
    spec.spec_path(book).write_text(
        GOOD_SPEC.replace("a live data link", "a live data link, and nothing else"),
        encoding="utf-8",
    )
    capsys.readouterr()
    assert unit.main(["status", str(book)]) == 1
    assert "inputs changed" in capsys.readouterr().out


def test_an_edited_draft_makes_an_accepted_unit_stale(book, corpus, capsys):
    sign_off(book)
    write_unit_draft(book, "ch-model")
    unit.main(["accept", str(book), "ch-model"])
    write_unit_draft(book, "ch-model", "Rewritten, citing @smith_example_2024.\n")
    capsys.readouterr()
    assert unit.main(["status", str(book)]) == 1
    assert "changed since accepted" in capsys.readouterr().out


def test_a_deleted_draft_makes_an_accepted_unit_unwritten_again(book, corpus, capsys):
    sign_off(book)
    write_unit_draft(book, "ch-model")
    unit.main(["accept", str(book), "ch-model"])
    (book / "ch-model.md").unlink()
    capsys.readouterr()
    assert unit.main(["status", str(book)]) == 1
    assert "unwritten" in capsys.readouterr().out


def test_a_record_that_is_not_readable_json_reads_as_drafted(book, corpus, capsys):
    """Hand-edited or half-written: a record nothing can read is not
    evidence that anybody accepted anything."""
    sign_off(book)
    write_unit_draft(book, "ch-model")
    unit.main(["accept", str(book), "ch-model"])
    unit.record_path(book, "ch-model").write_text("{not json", encoding="utf-8")
    capsys.readouterr()
    assert unit.main(["status", str(book)]) == 1
    assert "drafted" in capsys.readouterr().out


def test_status_refuses_a_spec_that_does_not_parse(book, capsys):
    spec.spec_path(book).write_text("# Book\n\n## Part I\n", encoding="utf-8")
    assert unit.main(["status", str(book)]) == 1
    assert "does not parse" in capsys.readouterr().err


# --- the entry point -----------------------------------------------------


def test_the_verb_is_reachable_through_the_drafting_layers_front_door(book, capsys):
    from chitragupta import draft

    assert draft.main(["unit", "contract", str(book), "ch-model"]) == 0
    assert "The model half" in capsys.readouterr().out


def test_no_subcommand_is_a_malformed_invocation():
    with pytest.raises(SystemExit) as exit_info:
        unit.main([])
    assert exit_info.value.code == 2


# --- #506/m-69: what accept may record, and what it gated ----------------


def test_accept_refuses_a_source_that_is_not_in_the_ledger(book, corpus, capsys):
    """The permanent acceptance record names the papers a unit is
    grounded in, and `--source` went into it unchecked -- a record
    asserting grounding in a citekey no real parse ever produced, which
    is precisely what CLAUDE.md's one rule forbids."""
    sign_off(book)
    write_unit_draft(book, "ch-model")
    capsys.readouterr()
    assert unit.main(["accept", str(book), "ch-model", "--source", "invented_source_2030"]) == 1
    assert "not in the ledger" in capsys.readouterr().err
    assert not unit.record_path(book, "ch-model").exists()


def test_accept_names_every_unknown_source_not_just_the_first(book, corpus, capsys):
    sign_off(book)
    write_unit_draft(book, "ch-model")
    capsys.readouterr()
    assert (
        unit.main(
            [
                "accept",
                str(book),
                "ch-model",
                "--source",
                "invented_one_2030",
                "--source",
                "invented_two_2031",
            ]
        )
        == 1
    )
    err = capsys.readouterr().err
    assert "invented_one_2030" in err
    assert "invented_two_2031" in err


def test_accept_gates_the_very_text_it_records(book, corpus, monkeypatch, capsys):
    """The draft is read once. `accept` used to gate the *path* (the gate
    opened the file itself) and then re-read it to hash and record, so a
    write landing between the two calls produced a permanent record --
    output digest and citekeys both -- for prose the gate had never seen.
    Pinned by capturing the string the gate was actually handed and
    checking the record was computed from that same string.
    """
    from chitragupta import citation_gate

    sign_off(book)
    write_unit_draft(book, "ch-model", "Citing @smith_example_2024.\n")
    gated = []
    real = citation_gate.check_text

    def capture(path, text, known):
        gated.append(text)
        return real(path, text, known)

    monkeypatch.setattr(citation_gate, "check_text", capture)
    capsys.readouterr()
    assert unit.main(["accept", str(book), "ch-model", "--source", "smith_example_2024"]) == 0
    record = json.loads(unit.record_path(book, "ch-model").read_text(encoding="utf-8"))
    assert len(gated) == 1
    assert record["output_digest"] == spec.digest(gated[0])


def test_accept_prints_the_gates_own_verdict(book, corpus, capsys):
    """The gate is still invoked rather than re-implemented, and still
    reports in its own shape -- `report()` is the one printer, so a
    document gated in memory reads identically to `draft gate <file>`."""
    sign_off(book)
    write_unit_draft(book, "ch-model", "Citing @smith_example_2024.\n")
    capsys.readouterr()
    assert unit.main(["accept", str(book), "ch-model", "--source", "smith_example_2024"]) == 0
    assert "citation(s), all verified against the ledger." in capsys.readouterr().out

"""The three consistency registries, and what each of them can and
cannot see.

The behaviours worth pinning: the registries are built from **accepted**
units only and say how many they skipped; a cross-reference is written in
a shape the citation gate will never read as a citekey; and `check`
reports everything and exits 0, because a machine's reading of prose is
judgement however mechanical the arithmetic.
"""

import pytest

from chitragupta import citation_gate, registry, spec, unit


GOOD_SPEC = """# Composable Digital Twins

## Part I: Foundations {#part-foundations}

### Chapter 1: What a twin is {#ch-what}

#### The model half {#sec-model}

Establish the model half.

#### The data half {#sec-data}

Establish the data half.
"""


MODEL_UNIT = """- **digital twin** -- a model paired with a live data link

A twin pairs a model with a link [@smith_example_2024].

See [the data half](#sec-data) for the other half.
"""


@pytest.fixture
def book(isolated_config, ledger_con, make_ref):
    from chitragupta import ledger

    ledger.upsert_reference(ledger_con, make_ref(citekey="smith_example_2024"))
    ledger_con.commit()
    path = isolated_config.DRAFTS_DIR / "twins"
    spec_file = spec.spec_path(path)
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(GOOD_SPEC, encoding="utf-8")
    spec.main(["sign", str(path)])
    return path


def accept(book, unit_id, body):
    path = book / f"{unit_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    assert unit.main(["accept", str(book), unit_id]) == 0
    return path


# --- what each registry reads out of one unit ----------------------------


def test_a_definition_is_the_bullet_shape_the_glossary_already_uses():
    found = registry.definitions("- **digital twin** -- a model plus a live link\n")
    assert found == [("digital twin", "term", "a model plus a live link")]


def test_a_backticked_term_is_notation_rather_than_terminology():
    found = registry.definitions("- **`x_t`** -- the state at time t\n")
    assert found[0][0] == "`x_t`" and found[0][1] == "notation"


def test_a_claim_is_a_sentence_that_cites_something():
    found = registry.claims("Twins pair models with links [@smith_2024]. This does not.\n")
    assert len(found) == 1
    assert found[0][1] == ["smith_2024"]


def test_a_rendered_reference_list_is_not_a_register_of_claims():
    """Every line of a reference list cites something. Reading them as
    claims would fill the register with bibliography -- the same
    exclusion chitragupta/acronyms.py measured against the real book."""
    text = ("A real claim [@smith_2024].\n\n"
            "## References\n\n[1] Smith, J. Something [@smith_2024].\n")
    assert [claim for claim, _ in registry.claims(text)] == [
        "A real claim [@smith_2024]."]


def test_a_cross_reference_is_read_in_both_markdown_and_latex():
    assert registry.references("See [it](#sec-data).\n") == ["sec-data"]
    assert registry.references("See \\cref{sec-data} and \\ref{fig-one}.\n") == [
        "sec-data", "fig-one"]


def test_a_cross_reference_is_never_readable_as_a_citekey():
    """The one invariant, from the other side: a reference syntax the
    citation gate reads as a citekey would put a section id where only a
    real bibliography entry may go."""
    text = "See [the data half](#sec-data) and \\cref{sec-model}.\n"
    assert citation_gate.extract_citekeys(text) == []
    assert registry.references(text) == ["sec-data", "sec-model"]


def test_a_unit_may_define_its_own_anchor_for_others_to_reference():
    assert registry.labels("A figure {#fig-one}\n\n\\label{tab-two}\n") == {
        "fig-one", "tab-two"}


# --- building over accepted units ----------------------------------------


def test_the_registries_are_built_from_accepted_units_only(book):
    accept(book, "sec-model", MODEL_UNIT)
    (book / "sec-data.md").write_text("Unaccepted prose.\n", encoding="utf-8")
    built = registry.build(book)
    assert built["accepted"] == ["sec-model"]
    assert built["skipped"] == ["sec-data"]
    assert built["terms"][0]["term"] == "digital twin"
    assert built["claims"][0]["citekeys"] == ["smith_example_2024"]


def test_a_term_defined_in_two_units_is_a_finding(book):
    accept(book, "sec-model", MODEL_UNIT)
    accept(book, "sec-data", "- **digital twin** -- something else entirely\n")
    findings = registry.findings(registry.build(book))
    assert any("digital twin" in text and "sec-model" in text and "sec-data" in text
               for _, text in findings)


def test_the_same_claim_made_in_two_units_is_a_finding(book):
    accept(book, "sec-model", MODEL_UNIT)
    accept(book, "sec-data", "A twin pairs a model with a link [@smith_example_2024].\n")
    kinds = [kind for kind, _ in registry.findings(registry.build(book))]
    assert "claim" in kinds


def test_a_claim_is_matched_regardless_of_case_and_spacing(book):
    accept(book, "sec-model", MODEL_UNIT)
    accept(book, "sec-data",
           "A  TWIN pairs a model  with a link [@smith_example_2024]!\n")
    assert "claim" in [kind for kind, _ in registry.findings(registry.build(book))]


def test_a_cross_reference_to_a_unit_the_outline_holds_resolves(book):
    accept(book, "sec-model", MODEL_UNIT)
    assert registry.findings(registry.build(book)) == []


def test_a_cross_reference_to_a_chapter_resolves(book):
    """"See Chapter 1" is an ordinary cross-reference. Reporting it
    unresolved because a chapter generates no prose of its own would be a
    finding about the registry rather than about the book."""
    accept(book, "sec-model", "As \\cref{ch-what} sets out.\n")
    assert registry.findings(registry.build(book)) == []


def test_a_cross_reference_to_nothing_is_a_finding(book):
    accept(book, "sec-model", "See [the missing half](#sec-nowhere).\n")
    findings = registry.findings(registry.build(book))
    assert any(kind == "xref" and "sec-nowhere" in text for kind, text in findings)


def test_a_cross_reference_to_an_anchor_another_unit_defines_resolves(book):
    accept(book, "sec-model", "See \\cref{fig-one}.\n")
    accept(book, "sec-data", "The figure {#fig-one}\n")
    assert registry.findings(registry.build(book)) == []


# --- the commands --------------------------------------------------------


def test_build_writes_one_file_per_registry(book, capsys):
    accept(book, "sec-model", MODEL_UNIT)
    capsys.readouterr()
    assert registry.main(["build", str(book)]) == 0
    written = registry.registry_dir(book)
    assert (written / "terms.md").is_file()
    assert (written / "claims.md").is_file()
    assert (written / "xrefs.md").is_file()
    assert "digital twin" in (written / "terms.md").read_text(encoding="utf-8")
    assert "1 of 2" in capsys.readouterr().out


def test_building_twice_over_unchanged_units_writes_the_same_bytes(book):
    accept(book, "sec-model", MODEL_UNIT)
    registry.main(["build", str(book)])
    first = (registry.registry_dir(book) / "terms.md").read_text(encoding="utf-8")
    registry.main(["build", str(book)])
    assert (registry.registry_dir(book) / "terms.md").read_text(encoding="utf-8") == first


def test_check_reports_findings_and_still_exits_zero(book, capsys):
    """The line ARCHITECTURE.md draws: a check measured against a
    machine's reading of prose reports and never blocks, however
    mechanical its answer."""
    accept(book, "sec-model", "See [nothing](#sec-nowhere).\n")
    capsys.readouterr()
    assert registry.main(["check", str(book)]) == 0
    out = capsys.readouterr().out
    assert "sec-nowhere" in out
    assert "not a verdict" in out


def test_check_says_how_many_units_it_could_not_see(book, capsys):
    accept(book, "sec-model", MODEL_UNIT)
    (book / "sec-data.md").write_text("Unaccepted.\n", encoding="utf-8")
    capsys.readouterr()
    registry.main(["check", str(book)])
    assert "sec-data" in capsys.readouterr().out


def test_check_on_a_clean_book_says_so(book, capsys):
    accept(book, "sec-model", MODEL_UNIT)
    accept(book, "sec-data", "The other half.\n")
    capsys.readouterr()
    assert registry.main(["check", str(book)]) == 0
    assert "no findings" in capsys.readouterr().out


def test_an_excerpt_is_what_a_later_unit_should_be_given(book, capsys):
    accept(book, "sec-model", MODEL_UNIT)
    capsys.readouterr()
    assert registry.main(["excerpt", str(book), "sec-data"]) == 0
    out = capsys.readouterr().out
    assert "digital twin" in out
    assert "sec-model" in out


def test_an_excerpt_leaves_out_the_units_own_definitions(book, capsys):
    """A unit is not told to conform to itself -- it is told what the
    rest of the book already settled."""
    accept(book, "sec-model", MODEL_UNIT)
    capsys.readouterr()
    registry.main(["excerpt", str(book), "sec-model"])
    assert "digital twin" not in capsys.readouterr().out


def test_a_book_with_no_outline_is_refused_by_name(isolated_config, capsys):
    assert registry.main(["build", str(isolated_config.DRAFTS_DIR / "unplanned")]) == 1
    assert "spec init" in capsys.readouterr().err


def test_the_verb_is_reachable_through_the_drafting_layers_front_door(book, capsys):
    from chitragupta import draft

    accept(book, "sec-model", MODEL_UNIT)
    capsys.readouterr()
    assert draft.main(["registry", "check", str(book)]) == 0
    assert "not a verdict" in capsys.readouterr().out


def test_no_subcommand_is_a_malformed_invocation():
    with pytest.raises(SystemExit) as exit_info:
        registry.main([])
    assert exit_info.value.code == 2

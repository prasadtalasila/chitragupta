"""The three consistency registries, and what each of them can and
cannot see.

The behaviours worth pinning: the registries are built from **accepted**
units only and say how many they skipped; a cross-reference is written in
a shape the citation gate will never read as a citekey; and `check`
reports everything and exits 0, because a machine's reading of prose is
judgement however mechanical the arithmetic.
"""

import pytest

from chitragupta import citation_gate, dossier, registry, unit


GOOD_SPEC = """# Composable Digital Twins

## Part I: Foundations {#part-foundations}

### The model half {#ch-model}

Establish the model half.

#### What a model is {#sec-model-what}

The modelling half.

#### What it leaves out {#sec-model-limits}

The abstraction half.

### The data half {#ch-data}

Establish the data half.

#### The link {#sec-data-link}

The wiring half.

#### Its failure modes {#sec-data-fail}

The unreliable half.
"""


MODEL_UNIT = """A twin pairs a model with a link [@smith_example_2024].

See [the data half](#ch-data) for the other half.
"""


# conftest's `signed_book` writes and signs this as the outline.
BOOK_SPEC = GOOD_SPEC


@pytest.fixture
def book(signed_book):
    """conftest's `signed_book` under the name these tests use: every
    registry check reads a signed outline."""
    return signed_book


# What each chapter declares, so an accepted draft matches its outline.
# `unit accept` refuses a chapter whose headings drifted (#472); this
# module is about what the registries read out of accepted prose, so the
# headings are scaffolding and `body` is the part under test.
DECLARED = {
    "ch-model": ("What a model is", "What it leaves out"),
    "ch-data": ("The link", "Its failure modes"),
}


# The glossary `MODEL_UNIT`'s dossier records, for the tests that need a
# term: since #1138 the terminology registry reads `scope.md`, not prose.
MODEL_GLOSSARY = "- **digital twin** -- a model paired with a live data link"


def accept(book, unit_id, body, glossary=None, math=None, symbols=()):
    """Accept `body` as `unit_id`'s prose, under the headings its outline
    declares so the chapter stays aligned, with `glossary` (bullets) as
    its dossier's `## Glossary` when given, and `math` (ASCII -> LaTeX)
    plus `symbols` (symbol, meaning cell) as its `math.md` when given."""
    headings = "".join(f"## {heading}\n\n" for heading in DECLARED.get(unit_id, ()))
    path = book / f"{unit_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {unit_id}\n\n{headings}{body}", encoding="utf-8")
    if glossary is not None:
        write_glossary(path, glossary)
    if math is not None:
        write_math(path, math, symbols)
    assert unit.main(["accept", str(book), unit_id]) == 0
    return path


def write_math(path, mapped, symbols=()):
    """`mapped` as `path`'s math.md mapping table, `symbols` as its
    `## Symbols` (#1143)."""
    math = dossier.dossier_dir(path) / "math.md"
    math.parent.mkdir(parents=True, exist_ok=True)
    lines = ["| ASCII | LaTeX |", "| --- | --- |"]
    lines += [f"| `{ascii_}` | `{latex}` |" for ascii_, latex in mapped.items()]
    if symbols:
        lines += ["", "## Symbols", "", "| Symbol | Meaning |", "| --- | --- |"]
        lines += [f"| `{symbol}` | {meaning} |" for symbol, meaning in symbols]
    math.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_glossary(path, bullets):
    dossier.init(path, "textbook")
    scope = dossier.dossier_dir(path) / "scope.md"
    head, _, _ = scope.read_text(encoding="utf-8").partition("## Glossary")
    scope.write_text(f"{head}## Glossary\n\n{bullets}\n", encoding="utf-8")


def xref_findings(book):
    return [text for kind, text in registry.findings(registry.build(book)) if kind == "xref"]


# --- what each registry reads out of one unit ----------------------------


def test_a_term_is_read_from_the_units_glossary(book):
    accept(book, "ch-model", MODEL_UNIT, glossary=MODEL_GLOSSARY)
    (row,) = registry.build(book)["terms"]
    assert (row["term"], row["unit"]) == ("digital twin", "ch-model")
    assert row["definition"] == "a model paired with a live data link"


def test_a_definition_bullet_in_the_prose_is_not_a_term(book):
    """The pre-#1138 source, and the guard against it coming back."""
    accept(book, "ch-model", "- **digital twin** -- a model plus a live link\n", glossary="")
    assert registry.build(book)["terms"] == []


def test_a_bullet_that_is_only_a_symbol_is_no_term_and_a_finding(book):
    accept(book, "ch-model", MODEL_UNIT, glossary="- **`x_t`** -- the state at time t")
    built = registry.build(book)
    assert built["terms"] == []
    assert any(kind == "glossary" and "math.md" in text for kind, text in registry.findings(built))


def test_a_symbol_is_read_from_math_md_and_linked_to_its_term(book):
    accept(
        book,
        "ch-model",
        MODEL_UNIT,
        glossary="- **Baseline** -- the present value",
        math={"M_0": "M_0"},
        symbols=[("M_0", "**Baseline**")],
    )
    (row,) = registry.build(book)["symbols"]
    assert (row["symbol"], row["kind"], row["text"], row["unit"]) == (
        "M_0",
        "link",
        "Baseline",
        "ch-model",
    )
    assert (row["key"], row["label"]) == ("baseline|", "Baseline")


def test_a_claim_is_a_sentence_that_cites_something():
    found = registry.claims("Twins pair models with links [@smith_2024]. This does not.\n")
    assert len(found) == 1
    assert found[0][1] == ["smith_2024"]


def test_a_tex_unit_is_read_with_latex_rules(tmp_path):
    """#957: Markdown's backtick rule read the span between two LaTeX
    `quoted' phrases as inline code, and the citation inside it dropped
    out of the register."""
    (tmp_path / "ch-x.tex").write_text(
        "The `digital twin' view \\citep{smith_2024} is `neat'.\n", encoding="utf-8"
    )
    built = {"terms": [], "claims": [], "xrefs": [], "glossary": [], "no_glossary": []}
    registry._read_unit(tmp_path, "ch-x", built, set())
    assert [claim["citekeys"] for claim in built["claims"]] == [["smith_2024"]]


def test_a_rendered_reference_list_is_not_a_register_of_claims():
    """Every line of a reference list cites something. Reading them as
    claims would fill the register with bibliography -- the same
    exclusion chitragupta/acronyms.py measured against the real book."""
    text = (
        "A real claim [@smith_2024].\n\n## References\n\n[1] Smith, J. Something [@smith_2024].\n"
    )
    assert [claim for claim, _ in registry.claims(text)] == ["A real claim [@smith_2024]."]


def test_a_cross_reference_is_read_in_both_markdown_and_latex():
    assert registry.references("See [it](#ch-data).\n") == ["ch-data"]
    assert registry.references("See \\cref{ch-data} and \\ref{fig-one}.\n") == [
        "ch-data",
        "fig-one",
    ]


def test_a_cross_reference_is_never_readable_as_a_citekey():
    """The one invariant, from the other side: a reference syntax the
    citation gate reads as a citekey would put a section id where only a
    real bibliography entry may go."""
    text = "See [the data half](#ch-data) and \\cref{ch-model}.\n"
    assert citation_gate.extract_citekeys(text) == []
    assert registry.references(text) == ["ch-data", "ch-model"]


def test_a_unit_may_define_its_own_anchor_for_others_to_reference():
    assert registry.labels("A figure {#fig-one}\n\n\\label{tab-two}\n") == {"fig-one", "tab-two"}


# --- building over accepted units ----------------------------------------


def test_the_registries_are_built_from_accepted_units_only(book):
    accept(book, "ch-model", MODEL_UNIT, glossary=MODEL_GLOSSARY)
    (book / "ch-data.md").write_text("Unaccepted prose.\n", encoding="utf-8")
    built = registry.build(book)
    assert built["accepted"] == ["ch-model"]
    assert built["skipped"] == ["ch-data"]
    assert built["terms"][0]["term"] == "digital twin"
    assert built["claims"][0]["citekeys"] == ["smith_example_2024"]


def test_a_term_defined_in_two_units_is_a_finding(book):
    accept(book, "ch-model", MODEL_UNIT, glossary=MODEL_GLOSSARY)
    accept(book, "ch-data", "", glossary="- **Digital twin (DT)** -- something else entirely")
    findings = registry.findings(registry.build(book))
    assert ("term", "`digital twin` is defined more than once: ch-data, ch-model") in findings


def test_a_term_defined_twice_in_one_unit_is_a_finding(book):
    accept(
        book,
        "ch-model",
        MODEL_UNIT,
        glossary="- **Solver** -- one thing\n- **Solver** -- another",
    )
    findings = registry.findings(registry.build(book))
    assert ("term", "`Solver` is defined more than once: ch-model (2x)") in findings


def test_a_symbol_naming_two_terms_in_two_units_is_a_finding(book):
    accept(
        book,
        "ch-model",
        MODEL_UNIT,
        glossary="- **Gain** -- the controller's gain",
        math={"k": "k"},
        symbols=[("k", "**Gain**")],
    )
    accept(book, "ch-data", "", glossary="", math={"k": "k"}, symbols=[("k", "rate constant")])
    findings = registry.findings(registry.build(book))
    assert (
        "notation",
        "`k` names different things: Gain (ch-model); rate constant (ch-data)",
    ) in findings


def test_one_symbol_with_one_meaning_in_two_units_is_not_a_finding(book):
    accept(book, "ch-model", MODEL_UNIT, glossary="- **Real-time factor** (`RTF`) -- a ratio")
    accept(book, "ch-data", "", glossary="- **real-time factor** (`RTF`) -- a ratio")
    findings = registry.findings(registry.build(book))
    assert not [text for kind, text in findings if kind == "notation"]


def test_a_symbol_typeset_two_ways_is_a_finding(book):
    glossary = "- **Target moisture** -- the target"
    meaning = [("m_t", "**Target moisture**")]
    accept(book, "ch-model", MODEL_UNIT, glossary, {"m_t": r"m_\mathrm{t}"}, meaning)
    accept(book, "ch-data", "", glossary, {"m_t": "m_t"}, [("m_t", "see ch-model")])
    findings = registry.findings(registry.build(book))
    assert any(kind == "notation" and "typeset differently" in text for kind, text in findings)


def test_an_off_format_glossary_bullet_is_a_finding(book):
    accept(book, "ch-model", MODEL_UNIT, glossary="- **Residual**: the difference")
    (finding,) = registry.findings(registry.build(book))
    assert finding[0] == "glossary"
    assert "ch-model scope.md:" in finding[1] and "**Residual**:" in finding[1]


def test_a_unit_with_no_glossary_is_a_finding(book):
    accept(book, "ch-model", MODEL_UNIT)
    assert ("glossary", "ch-model has no ## Glossary in scope.md") in registry.findings(
        registry.build(book)
    )


def test_the_same_claim_made_in_two_units_is_a_finding(book):
    accept(book, "ch-model", MODEL_UNIT)
    accept(book, "ch-data", "A twin pairs a model with a link [@smith_example_2024].\n")
    kinds = [kind for kind, _ in registry.findings(registry.build(book))]
    assert "claim" in kinds


def test_a_claim_is_matched_regardless_of_case_and_spacing(book):
    accept(book, "ch-model", MODEL_UNIT)
    accept(book, "ch-data", "A  TWIN pairs a model  with a link [@smith_example_2024]!\n")
    assert "claim" in [kind for kind, _ in registry.findings(registry.build(book))]


def test_a_cross_reference_to_a_unit_the_outline_holds_resolves(book):
    accept(book, "ch-model", MODEL_UNIT)
    assert xref_findings(book) == []


def test_a_cross_reference_to_a_chapter_resolves(book):
    """ "See Chapter 1" is an ordinary cross-reference. Reporting it
    unresolved because a chapter generates no prose of its own would be a
    finding about the registry rather than about the book."""
    accept(book, "ch-model", "As \\cref{ch-data} sets out.\n")
    assert xref_findings(book) == []


def test_a_cross_reference_to_nothing_is_a_finding(book):
    accept(book, "ch-model", "See [the missing half](#sec-nowhere).\n")
    findings = registry.findings(registry.build(book))
    assert any(kind == "xref" and "sec-nowhere" in text for kind, text in findings)


def test_a_cross_reference_to_an_anchor_another_unit_defines_resolves(book):
    accept(book, "ch-model", "See \\cref{fig-one}.\n")
    accept(book, "ch-data", "The figure {#fig-one}\n")
    assert xref_findings(book) == []


# --- the commands --------------------------------------------------------


def test_build_writes_one_file_per_registry(book, capsys):
    accept(book, "ch-model", MODEL_UNIT, glossary=MODEL_GLOSSARY)
    capsys.readouterr()
    assert registry.main(["build", str(book)]) == 0
    written = registry.registry_dir(book)
    assert (written / "terms.md").is_file()
    assert (written / "claims.md").is_file()
    assert (written / "xrefs.md").is_file()
    assert "digital twin" in (written / "terms.md").read_text(encoding="utf-8")
    assert "1 of 2" in capsys.readouterr().out


def test_building_twice_over_unchanged_units_writes_the_same_bytes(book):
    accept(book, "ch-model", MODEL_UNIT, glossary=MODEL_GLOSSARY)
    registry.main(["build", str(book)])
    first = (registry.registry_dir(book) / "terms.md").read_text(encoding="utf-8")
    registry.main(["build", str(book)])
    assert (registry.registry_dir(book) / "terms.md").read_text(encoding="utf-8") == first


def test_check_reports_findings_and_still_exits_zero(book, capsys):
    """The line ARCHITECTURE.md draws: a check measured against a
    machine's reading of prose reports and never blocks, however
    mechanical its answer."""
    accept(book, "ch-model", "See [nothing](#sec-nowhere).\n")
    capsys.readouterr()
    assert registry.main(["check", str(book)]) == 0
    out = capsys.readouterr().out
    assert "sec-nowhere" in out
    assert "not a verdict" in out


def test_check_says_how_many_units_it_could_not_see(book, capsys):
    accept(book, "ch-model", MODEL_UNIT)
    (book / "ch-data.md").write_text("Unaccepted.\n", encoding="utf-8")
    capsys.readouterr()
    registry.main(["check", str(book)])
    assert "ch-data" in capsys.readouterr().out


def test_check_on_a_clean_book_says_so(book, capsys):
    accept(book, "ch-model", MODEL_UNIT, glossary=MODEL_GLOSSARY)
    accept(book, "ch-data", "The other half.\n", glossary="- **link** -- the live data feed")
    capsys.readouterr()
    assert registry.main(["check", str(book)]) == 0
    assert "no findings" in capsys.readouterr().out


def test_an_excerpt_is_what_a_later_unit_should_be_given(book, capsys):
    accept(book, "ch-model", MODEL_UNIT, glossary=MODEL_GLOSSARY)
    capsys.readouterr()
    assert registry.main(["excerpt", str(book), "ch-data"]) == 0
    out = capsys.readouterr().out
    assert "digital twin" in out
    assert "ch-model" in out


def test_an_excerpt_carries_the_other_units_symbols(book, capsys):
    accept(
        book,
        "ch-model",
        MODEL_UNIT,
        glossary="- **Baseline** -- the present value",
        math={"M_0": "M_0"},
        symbols=[("M_0", "**Baseline**")],
    )
    capsys.readouterr()
    registry.main(["excerpt", str(book), "ch-data"])
    out = capsys.readouterr().out
    assert "- **Baseline** (in ch-model) -- the present value" in out
    assert "- `M_0` (in ch-model) -- **Baseline**" in out


def test_an_excerpt_leaves_out_the_units_own_definitions(book, capsys):
    """A unit is not told to conform to itself -- it is told what the
    rest of the book already settled."""
    accept(book, "ch-model", MODEL_UNIT, glossary=MODEL_GLOSSARY)
    capsys.readouterr()
    registry.main(["excerpt", str(book), "ch-model"])
    assert "digital twin" not in capsys.readouterr().out


def test_an_excerpt_carries_an_in_prose_label_no_xref_has_reached_yet(book, capsys):
    """`excerpt()` reuses `build()`'s full anchor set -- outline ids plus
    every in-prose label `_read_unit` folds in -- rather than recomputing
    a narrower one that only counts labels some xref has already
    resolved against. `docs/WRITE-A-BOOK.md`'s own measured example has zero
    xrefs in the real book, so this is the common case, not an edge
    one."""
    accept(book, "ch-model", "A figure of the model {#fig-model}\n")
    capsys.readouterr()
    assert registry.main(["excerpt", str(book), "ch-data"]) == 0
    assert "fig-model" in capsys.readouterr().out


def test_a_book_with_no_outline_is_refused_by_name(isolated_config, capsys):
    assert registry.main(["build", str(isolated_config.DRAFTS_DIR / "unplanned")]) == 1
    assert "spec init" in capsys.readouterr().err


def test_the_verb_is_reachable_through_the_drafting_layers_front_door(book, capsys):
    from chitragupta import draft

    accept(book, "ch-model", MODEL_UNIT)
    capsys.readouterr()
    assert draft.main(["registry", "check", str(book)]) == 0
    assert "not a verdict" in capsys.readouterr().out


def test_no_subcommand_is_a_malformed_invocation():
    with pytest.raises(SystemExit) as exit_info:
        registry.main([])
    assert exit_info.value.code == 2

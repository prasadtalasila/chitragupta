"""chitragupta/registry/_symbols.py: each accepted unit's `math.md`
`## Symbols`, resolved across the book (#1143).

A bold link resolves to a glossary term in any accepted unit; `see
<unit>` resolves to that unit's row for the same symbol; the meaning key
(term or words, plus the note) is what `[notation]` and the List of
Symbols both group by.
"""

import pytest

from chitragupta import registry
from tests.test_registry import BOOK_SPEC, MODEL_UNIT, accept  # noqa: F401


@pytest.fixture
def book(signed_book):
    return signed_book


def notation(book) -> "list[str]":
    return [text for kind, text in registry.findings(registry.build(book)) if kind == "notation"]


RESIDUAL = "- **Residual** -- the difference between reading and prediction"


# --- links ---------------------------------------------------------------


def test_a_link_resolves_to_a_term_another_unit_defines(book):
    accept(book, "ch-model", MODEL_UNIT, glossary=RESIDUAL)
    accept(book, "ch-data", "", glossary="", math={"r": "r"}, symbols=[("r", "**residual**")])
    (row,) = registry.build(book)["symbols"]
    assert (row["key"], row["label"]) == ("residual|", "Residual")
    assert notation(book) == []


def test_a_link_no_glossary_defines_is_a_finding(book):
    accept(book, "ch-model", MODEL_UNIT, glossary=RESIDUAL)
    accept(book, "ch-data", "", glossary="", math={"r": "r"}, symbols=[("r", "**Residuall**")])
    assert notation(book) == [
        "ch-data math.md `r` links to **Residuall**, which no glossary in the book defines"
    ]


def test_a_note_tells_two_symbols_of_one_term_apart(book):
    accept(
        book,
        "ch-model",
        MODEL_UNIT,
        glossary="- **Moisture thresholds** -- the two readings the strategy holds between",
        math={"m_lo": "m_lo", "m_hi": "m_hi"},
        symbols=[
            ("m_lo", "**Moisture thresholds**, lower"),
            ("m_hi", "**Moisture thresholds**, upper"),
        ],
    )
    labels = {row["symbol"]: row["label"] for row in registry.build(book)["symbols"]}
    assert labels == {"m_lo": "Moisture thresholds, lower", "m_hi": "Moisture thresholds, upper"}
    assert notation(book) == []


def test_two_notes_on_one_symbol_are_two_meanings(book):
    accept(
        book,
        "ch-model",
        MODEL_UNIT,
        glossary="- **Moisture thresholds** -- the two readings",
        math={"m_lo": "m_lo"},
        symbols=[("m_lo", "**Moisture thresholds**, lower")],
    )
    accept(
        book,
        "ch-data",
        "",
        glossary="",
        math={"m_lo": "m_lo"},
        symbols=[("m_lo", "**Moisture thresholds**, low end")],
    )
    assert any("`m_lo` names different things" in text for text in notation(book))


# --- pointers --------------------------------------------------------------


def test_a_pointer_takes_its_targets_meaning(book):
    accept(
        book,
        "ch-model",
        MODEL_UNIT,
        glossary="",
        math={"T_c": "T_c"},
        symbols=[("T_c", "check interval")],
    )
    accept(book, "ch-data", "", glossary="", math={"T_c": "T_c"}, symbols=[("T_c", "see ch-model")])
    rows = registry.build(book)["symbols"]
    assert {row["key"] for row in rows} == {"check interval|"}
    assert notation(book) == []


@pytest.mark.parametrize(
    "target_symbols, expected",
    [
        ([], "has no ## Symbols row for it"),
        ([("T_c", "see ch-data")], "points on itself; point at the row that defines it"),
        ([("T_c", "**Nothing**")], "does not resolve either"),
    ],
)
def test_a_pointer_that_does_not_land_is_a_finding(book, target_symbols, expected):
    accept(book, "ch-model", MODEL_UNIT, glossary="", math={"T_c": "T_c"}, symbols=target_symbols)
    accept(book, "ch-data", "", glossary="", math={"T_c": "T_c"}, symbols=[("T_c", "see ch-model")])
    assert f"ch-data math.md `T_c` points at ch-model, which {expected}" in notation(book)


def test_a_pointer_to_a_unit_not_accepted_is_a_finding(book):
    accept(
        book,
        "ch-model",
        MODEL_UNIT,
        glossary="",
        math={"T_c": "T_c"},
        symbols=[("T_c", "see ch-data")],
    )
    assert notation(book) == [
        "ch-model math.md `T_c` points at ch-data, which is not an accepted unit"
    ]


# --- what one unit's math.md says, and its glossary ------------------------


def test_a_units_math_findings_are_prefixed_with_the_unit(book):
    accept(
        book,
        "ch-model",
        MODEL_UNIT,
        glossary="",
        math={"T_oil": "T_\\mathrm{oil}"},
        symbols=[("k", "gain")],
    )
    assert notation(book) == [
        "ch-model `T_oil` is mapped in math.md but has no meaning in its ## Symbols",
        "ch-model `k` has a meaning in ## Symbols but no row in the mapping table, "
        "so it cannot be typeset",
    ]


def test_glossary_maths_with_no_row_is_reported_and_code_is_not(book):
    accept(
        book,
        "ch-model",
        MODEL_UNIT,
        glossary="- **Saving** -- `(M_0 - M_1) * c` a year, in the `greenhouse` table; `PUT` it.",
        math={"M_0": "M_0", "M_1": "M_1", "c": "c"},
        symbols=[("M_0", "baseline"), ("M_1", "after"), ("c", "unit cost")],
    )
    (found,) = notation(book)
    assert found.startswith("ch-model glossary span `(M_0 - M_1) * c` looks like mathematics (")
    assert found.endswith("but its unit's math.md has no row for it, so it prints as code")


def test_without_a_math_md_only_the_shape_rules_judge_the_glossary(book):
    accept(
        book,
        "ch-model",
        MODEL_UNIT,
        glossary="- **Saving** -- `(M_0 - M_1) * c` a year, at step `H`.",
    )
    (found,) = notation(book)
    assert "`(M_0 - M_1) * c`" in found and "`H`" not in found


def test_a_glossary_span_with_a_row_is_quiet(book):
    accept(
        book,
        "ch-model",
        MODEL_UNIT,
        glossary="- **Saving** -- `(M_0 - M_1) * c` a year.",
        math={"(M_0 - M_1) * c": "(M_0 - M_1)\\,c"},
    )
    assert notation(book) == []


def test_the_symbols_registry_is_written(book, capsys):
    accept(
        book,
        "ch-model",
        MODEL_UNIT,
        glossary="",
        math={"m_lo": "m_lo"},
        symbols=[("m_lo", "**Moisture thresholds**, lower")],
    )
    registry.main(["build", str(book)])
    text = (registry.registry_dir(book) / "symbols.md").read_text(encoding="utf-8")
    assert "| m_lo | **Moisture thresholds**, lower | ch-model |" in text


def test_an_excerpt_leaves_out_a_row_that_settled_nothing(book, capsys):
    accept(
        book, "ch-model", MODEL_UNIT, glossary="", math={"k": "k"}, symbols=[("k", "**Nothing**")]
    )
    capsys.readouterr()
    registry.main(["excerpt", str(book), "ch-data"])
    assert "`k`" not in capsys.readouterr().out


# --- what build refuses ------------------------------------------------------


@pytest.fixture
def no_pandoc_needed(monkeypatch):
    monkeypatch.setattr("chitragupta.registry._cli.markdown_to_latex", lambda texts: list(texts))


@pytest.mark.parametrize(
    "symbols, refused",
    [
        ([("k", "**Nothing**")], True),
        ([("k", "see ch-data")], True),
        ([("k", "gain"), ("x", "state")], True),  # `x` is unmapped
        ([("k", "gain"), ("k", "rate")], True),  # malformed: two rows
        ([], False),  # a missing meaning is reported, never refused
    ],
)
def test_build_refuses_what_would_print_wrong(
    book, tmp_path, no_pandoc_needed, capsys, symbols, refused
):
    accept(
        book,
        "ch-model",
        MODEL_UNIT,
        glossary="- **Model** -- a model.",
        math={"k": "k"},
        symbols=symbols,
    )
    code = registry.main(["build", str(book), "--notation", str(tmp_path / "n.tex")])
    assert code == (1 if refused else 0)
    if refused:
        assert "no page written" in capsys.readouterr().err

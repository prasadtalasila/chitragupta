"""The index's term table and `index.toml` (#1168): what `registry build
--index` writes into `index-terms.json`, and every `index.toml` it refuses.

Pure inputs throughout -- glossary rows, linked symbols, accepted units
and a parsed `index.toml` -- so none of these needs a book on disk;
`tests/test_registry_index_cli.py` runs the command over a real one.
"""

import json

import pytest

from chitragupta.registry import _index_terms, _index_toml
from chitragupta.registry._index_terms import term_id

CH1, CH2, CH3 = "ch-one", "ch-two", "ch-three"
ACCEPTED = [CH1, CH2, CH3]


def row(term, unit=CH1):
    return {"term": term, "unit": unit}


def build(rows, doc=None, linked=None):
    return _index_terms.table(rows, linked or {}, ACCEPTED, doc or {})


def entry(data, key):
    return data["terms"][term_id(key)]


# --- the term table ------------------------------------------------------


def test_a_glossary_term_is_an_entry_with_its_defining_chapters_in_order():
    data, problems = build([row("Digital twin (DT)"), row("digital twin", CH3)])
    assert problems == []
    twin = entry(data, "digital twin")
    assert twin["glossary"] == "Digital twin"
    assert twin["defined_in"] == [CH1, CH3]
    assert twin["spellings"] == ["digital twin"]
    assert data["see"] == {"DT": term_id("digital twin")}


def test_the_id_is_the_hash_of_the_key_so_it_survives_a_new_term():
    alone, _ = build([row("Model")])
    more, _ = build([row("Aardvark"), row("Model")])
    assert term_id("model") in alone["terms"] and term_id("model") in more["terms"]
    assert term_id("model") == term_id("model") != term_id("aardvark")


def test_settings_default_and_are_overridden_by_the_file():
    data, _ = build([row("Model")])
    assert (data["min_mentions"], data["sort"], data["letter_headings"]) == (2, "word", False)
    assert data["skip_sections"] == ["Exercises", "Solutions"]
    data, _ = build([row("Model")], {"settings": {"min_mentions": 3, "sort": "letter"}})
    assert (data["min_mentions"], data["sort"]) == (3, "letter")


def test_variants_add_spellings_normalised_like_prose():
    data, _ = build([row("Analysis")], {"variants": {"analysis": ["Analyses", "re-analysis"]}})
    assert entry(data, "analysis")["spellings"] == ["analyses", "analysis", "re analysis"]


def test_restrict_replaces_the_bare_word_with_its_phrases():
    data, _ = build([row("Service")], {"restrict": {"service": ["Twin service"]}})
    assert entry(data, "service")["spellings"] == ["twin service"]


def test_a_term_holding_maths_needs_a_plain_variant():
    data, _ = build([row("`x` vector")])
    assert data["not_indexable"] == ["`x` vector"] and data["terms"] == {}
    data, _ = build([row("`x` vector")], {"variants": {"`x` vector": ["state vector"]}})
    assert entry(data, "`x` vector")["spellings"] == ["state vector"]


def test_drop_and_add():
    data, problems = build(
        [row("Model"), row("Two-question test")],
        {"drop": {"terms": ["two-question test"]}, "add": {"terms": ["Kalman filter"]}},
    )
    assert problems == []
    assert data["dropped"] == ["two-question test"]
    assert term_id("two-question test") not in data["terms"]
    kalman = entry(data, "kalman filter")
    assert (kalman["glossary"], kalman["defined_in"]) == ("Kalman filter", [])


def test_always_print_parents_and_symbols_reach_the_entry():
    doc = {
        "always": {"Stage 0": [CH2]},
        "print": {"stage 0": "Stage 0"},
        "parent": {"stage": ["stage 0"], "phase": ["Stage 0"]},
        "parent_only": {"stage": True},
    }
    data, problems = build([row("Stage 0")], doc, {(CH1, "stage 0"): ["$S_0$", "$S_0$"]})
    assert problems == []
    stage = entry(data, "stage 0")
    assert stage["always"] == [CH2] and stage["print"] == "Stage 0"
    assert stage["parents"] == ["phase", "stage"]
    assert stage["symbols"] == ["$S_0$"]
    assert data["parent_only"] == ["stage"]


def test_see_and_see_also():
    doc = {"see": {"shadow": "Digital shadow"}, "see_also": {"digital shadow": ["model"]}}
    data, problems = build([row("Digital shadow (DS)"), row("Model")], doc)
    assert problems == []
    assert data["see"] == {"DS": term_id("digital shadow"), "shadow": term_id("digital shadow")}
    assert data["see_also"] == {term_id("digital shadow"): [term_id("model")]}


def test_an_abbreviation_that_is_itself_a_term_gets_no_see_entry():
    data, _ = build([row("Digital twin (DT)"), row("DT")])
    assert data["see"] == {}


def test_a_parenthetical_that_is_no_abbreviation_gets_no_see_entry():
    data, _ = build([row("Twin (also called replica)")])
    assert data["see"] == {}


def test_dumps_is_sorted_and_stable():
    data, _ = build([row("Model"), row("Aardvark")])
    text = _index_terms.dumps(data)
    assert text == _index_terms.dumps(json.loads(text))
    assert text.endswith("\n")


# --- refusals: what names nothing ---------------------------------------


@pytest.mark.parametrize(
    "doc, expected",
    [
        ({"variants": {"ghost": ["x"]}}, '`[variants]` names "ghost"'),
        ({"print": {"ghost": "G"}}, '`[print]` names "ghost"'),
        ({"drop": {"terms": ["ghost"]}}, '`[drop]` names "ghost"'),
        ({"see_also": {"model": ["ghost"]}}, '`[see_also]` names "ghost"'),
        ({"parent": {"p": ["ghost"]}}, '`[parent]` names "ghost"'),
        ({"see": {"m": "ghost"}}, '`[see]` names "ghost"'),
        ({"add": {"terms": ["Model"]}}, '`[add]` term "Model" is already a glossary term'),
        ({"always": {"model": ["ch-nine"]}}, 'chapter "ch-nine" for "model"'),
        ({"see": {"model": "model"}}, '`[see]` source "model" is an indexed term'),
        (
            {"drop": {"terms": ["model"]}, "parent": {"p": ["model"]}},
            '`[parent]` child "model" is dropped',
        ),
        ({"parent_only": {"p": True}}, '`[parent_only]` names "p", which is not a `[parent]`'),
        (
            {"variants": {"model": ["shadow"]}, "add": {"terms": ["Shadow"]}},
            '"shadow" is a spelling of both "model" and "shadow"',
        ),
    ],
)
def test_a_reference_to_nothing_refuses(doc, expected):
    _, problems = build([row("Model")], doc)
    assert any(expected in problem for problem in problems), problems


# --- index.toml's shape ------------------------------------------------


def write(tmp_path, text):
    (tmp_path / "index.toml").write_text(text, encoding="utf-8")
    return _index_toml.read(tmp_path)


def test_no_file_is_no_exceptions(tmp_path):
    assert _index_toml.read(tmp_path) == ({}, [])


def test_the_shipped_sample_is_valid(tmp_path):
    from chitragupta import config

    sample = config.shipped("assets", "book", "index.toml").read_text(encoding="utf-8")
    doc, problems = write(tmp_path, sample)
    assert problems == []
    assert _index_toml.settings(doc) == _index_toml.DEFAULTS


def test_invalid_toml_is_one_problem(tmp_path):
    doc, problems = write(tmp_path, "[settings\n")
    assert doc == {} and len(problems) == 1 and "not valid TOML" in problems[0]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("[variant]\n", "no table `[variant]`"),
        ("settings = 3\n", "`[settings]` must be a table"),
        ("[settings]\nmin_mention = 2\n", "no key `min_mention`"),
        ("[settings]\nmin_mentions = 0\n", "`min_mentions` must be a whole number"),
        ("[settings]\nmin_mentions = true\n", "`min_mentions` must be a whole number"),
        ("[settings]\nmin_mentions = 2.5\n", "`min_mentions` must be a whole number"),
        ('[settings]\nsort = "page"\n', '`sort` must be "word" or "letter"'),
        ('[settings]\nletter_headings = "yes"\n', "`letter_headings` must be true or false"),
        ("[settings]\nskip_sections = [1]\n", "`skip_sections` must be a list"),
        ('[drop]\nterm = ["x"]\n', "`[drop]` must hold exactly `terms = [...]`"),
        ('drop = "x"\n', "`[drop]` must hold exactly"),
        ("variants = 3\n", "`[variants]` must be a table"),
        ('[variants]\nx = "y"\n', "`[variants]` entry `x` has the wrong shape: it must be a list"),
        ("[variants]\nx = []\n", "`[variants]` entry `x` has the wrong shape"),
        ("[print]\nx = 1\n", "`[print]` entry `x` has the wrong shape: it must be a string"),
        ('[parent_only]\nx = "y"\n', "it must be true or false"),
    ],
)
def test_a_wrong_shape_is_named(tmp_path, text, expected):
    _, problems = write(tmp_path, text)
    assert any(expected in problem for problem in problems), problems


def test_a_well_formed_drop_and_add_are_no_problem(tmp_path):
    doc, problems = write(tmp_path, '[drop]\nterms = ["x"]\n[add]\nterms = ["y"]\n')
    assert problems == [] and doc["drop"] == {"terms": ["x"]}


def test_a_term_defined_twice_in_one_chapter_lists_the_chapter_once():
    data, _ = build([row("Model (M)"), row("Model (MD)")])
    model = entry(data, "model")
    assert model["defined_in"] == [CH1]
    assert data["see"] == {"M": term_id("model")}


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Euler's step", "euler step"),
        ("Heun’s step", "heun step"),
        ("derived (augmented) state", "derived augmented state"),
        ("time–series — data", "time series data"),
        ("“quoted” term.", "quoted term"),
    ],
)
def test_a_spelling_is_tokenised_as_the_filter_tokenises_prose(text, expected):
    """assets/pandoc/index_terms.lua drops a possessive and edge
    punctuation and splits on dashes; a spelling that kept them could
    never match (found on the digital-twins book: "Euler's step")."""
    assert _index_terms.spelling(text) == expected


# --- found by review (#1168) ------------------------------------------------


@pytest.mark.parametrize(
    "doc, expected",
    [
        (
            {"drop": {"terms": ["shadow"]}, "see_also": {"model": ["shadow"]}},
            '"shadow" is dropped or has no plain spelling',
        ),
        (
            {"drop": {"terms": ["shadow"]}, "see": {"s": "shadow"}},
            '"shadow" is dropped or has no plain spelling',
        ),
        ({"see_also": {"model": ["`x` vector"]}}, '"`x` vector" is dropped or has no plain'),
        ({"variants": {"model": ["---"]}}, '"---" leaves no word to match'),
        ({"restrict": {"model": ["“”"]}}, '"“”" leaves no word to match'),
    ],
)
def test_a_target_or_spelling_the_index_cannot_hold_refuses(doc, expected):
    """A dropped or maths-only cross-reference target crashed `registry
    index`, and a spelling of punctuation alone crashed the filter."""
    _, problems = build([row("Model"), row("Shadow"), row("`x` vector")], doc)
    assert any(expected in problem for problem in problems), problems


def test_parent_names_match_whatever_their_case():
    doc = {"parent": {"Stage": ["stage 0"]}, "parent_only": {"stage": True}}
    data, problems = build([row("Stage 0")], doc)
    assert problems == []
    assert data["parent_only"] == ["Stage"]
    assert entry(data, "stage 0")["parents"] == ["Stage"]

"""How the index prints a term (#1168): its casing, article, symbols, sort
key, `upmendex` quoting, sub-entries and cross-references.

Pure functions over the term table and the chapters' casing counts, with
an identity converter standing in for pandoc, so none of this needs a
toolchain; `tests/test_registry_index_finish.py` runs the real one.
"""

import pytest

from chitragupta.registry import _index_entries as entries
from chitragupta.registry._index_terms import term_id


def identity(texts):
    return list(texts)


def term(glossary, **extra):
    return {"glossary": glossary, "symbols": [], "print": None, "parents": [], **extra}


# --- casing ---------------------------------------------------------------


@pytest.mark.parametrize(
    "glossary, midsentence, expected",
    [
        ("Decision", {"decision": 5}, "decision"),
        ("Markov chain", {"Markov chain": 3, "markov chain": 1}, "Markov chain"),
        ("digital twin", {"Digital Twin": 2}, "Digital Twin"),
        ("Value metric", {}, "value metric"),
        ("Value metric", {"value metric": 1, "Value metric": 1}, "value metric"),
        ("I2C", {"i2c": 0, "I2C": 4}, "I2C"),
        ("State model", {"state space model": 3}, "state model"),
        ("Black-box model", {"black box model": 2}, "black-box model"),
        ("Grey-box Model", {"grey box Model": 2}, "grey-box Model"),
        ("MODBUS RTU", {}, "MODBUS RTU"),
        ("RS-485", {}, "RS-485"),
        ("Stage 0", {}, "stage 0"),
    ],
)
def test_casing_follows_the_books_own_prose(glossary, midsentence, expected):
    """With no mid-sentence evidence, or a tie, a plainly capitalised first
    word is the glossary line's sentence capital and is lowercased
    (Chicago's default); found on the digital-twins book, where 48 of 289
    entries kept it, most because a hyphen made the counts disagree."""
    assert entries.cased(glossary, midsentence) == expected


@pytest.mark.parametrize(
    "glossary, midsentence, expected",
    [
        ("Kalman filter", {}, True),
        ("Value metric", {"value metric": 1, "Value metric": 1}, True),
        ("Decision", {"decision": 2}, False),
        ("MODBUS RTU", {}, False),
        ("digital twin", {}, False),
    ],
)
def test_a_guessed_casing_is_known(glossary, midsentence, expected):
    assert entries.guessed(glossary, midsentence) is expected


# --- printed form and sort key -----------------------------------------


def test_a_leading_article_is_inverted_and_left_out_of_the_sort():
    assert entries.printed(term("The four criteria"), {"four criteria": 2}) == "four criteria, the"
    assert entries.sort_key("The four criteria") == "four criteria"
    assert entries.printed(term("A"), {}) == "A"


def test_symbols_follow_the_term_and_print_overrides_casing():
    shown = term("State vector", symbols=["$x$", "$y$"])
    assert entries.printed(shown, {"state vector": 3}) == "state vector ($x$, $y$)"
    assert entries.printed(term("i2c", print="I²C"), {"i2c": 9}) == "I²C"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Digital twin", "digital twin"),
        ("ε-greedy", "epsilon-greedy"),
        ("$\\varepsilon$-greedy", "epsilon-greedy"),
        ("`x` vector", "x vector"),
        ("$L^2$ norm", "l^2 norm"),
        ("An  apple", "apple"),
    ],
)
def test_the_sort_key_is_plain_lowercase_text(text, expected):
    assert entries.sort_key(text) == expected


def test_quoting_escapes_upmendex_specials():
    assert entries.quote('a!b@c|d"e') == 'a"!b"@c"|d""e'


# --- the entries ----------------------------------------------------------


def table(*terms, **extra):
    return {
        "terms": {term_id(t["key"]): t for t in terms},
        "see": {},
        "see_also": {},
        "parent_only": [],
        **extra,
    }


def test_each_term_is_one_sort_at_printed_key():
    data = table({**term("Decision"), "key": "decision"})
    keys, printed = entries.keys(data, {term_id("decision"): {"decision": 2}}, identity)
    assert keys[term_id("decision")] == ["decision@decision"]
    assert printed == {term_id("decision"): "decision"}


def test_a_child_repeats_its_parents_whole_key_and_drops_the_parents_word():
    data = table(
        {**term("Stage 0", parents=["stage"]), "key": "stage 0"},
        {**term("Lean digital twin", parents=["twin, kinds of"]), "key": "lean digital twin"},
    )
    keys, _ = entries.keys(data, {}, identity)
    assert keys[term_id("stage 0")] == ["stage 0@stage 0", "stage@stage!0@0"]
    assert keys[term_id("lean digital twin")] == [
        "lean digital twin@lean digital twin",
        "twin, kinds of@twin, kinds of!lean digital twin@lean digital twin",
    ]


def test_parent_only_drops_the_top_level_entry():
    data = table({**term("Stage 0", parents=["stage"]), "key": "stage 0"}, parent_only=["stage"])
    assert entries.keys(data, {}, identity)[0][term_id("stage 0")] == ["stage@stage!0@0"]


def test_a_child_that_is_only_its_parents_word_keeps_it():
    assert entries.child("Stage", "stage") == "Stage"
    assert entries.child("digital twin", "twin") == "digital"
    assert entries.child("process model", "stage") == "process model"


def test_printed_forms_are_converted_once_each():
    seen = []

    def convert(texts):
        seen.append(list(texts))
        return [f"<{text}>" for text in texts]

    data = table({**term("A!b"), "key": "a!b"}, {**term("Model"), "key": "model"})
    keys, _ = entries.keys(data, {term_id("model"): {"model": 1}}, convert)
    assert keys[term_id("a!b")] == ['a"!b@<a"!b>']
    assert len(seen) == 1 and sorted(seen[0]) == ["a!b", "model"]


# --- cross-references ---------------------------------------------------


def test_see_and_see_also_point_at_terms_that_have_pages():
    data = table(
        {**term("Digital twin"), "key": "digital twin"},
        {**term("Model"), "key": "model"},
        {**term("Shadow"), "key": "shadow"},
        see={"DT": term_id("digital twin"), "Ghost": term_id("shadow")},
        see_also={term_id("digital twin"): [term_id("model"), term_id("shadow")]},
    )
    printed = {term_id(key): key for key in ("digital twin", "model", "shadow")}
    pages = {term_id("digital twin"): "3", term_id("model"): "5"}
    lines, dangling = entries.cross_references(data, printed, pages, identity)
    assert lines == [
        "\\indexentry{dt@DT|see{digital twin}}{3}",
        "\\indexentry{digital twin@digital twin|seealso{model}}{3}",
    ]
    assert dangling == ["Ghost", "shadow"]


def test_see_also_with_no_target_left_prints_nothing():
    data = table(
        {**term("Digital twin"), "key": "digital twin"},
        {**term("Shadow"), "key": "shadow"},
        see_also={term_id("digital twin"): [term_id("shadow")]},
    )
    printed = {term_id("digital twin"): "digital twin", term_id("shadow"): "shadow"}
    lines, dangling = entries.cross_references(
        data, printed, {term_id("digital twin"): "3"}, identity
    )
    assert lines == [] and dangling == ["shadow"]

"""The index report (#1168): `registries/index.md` and `index.json`, each
finding with the `index.toml` line that answers it. Advisory: nothing
here refuses anything."""

import json

from chitragupta.registry import _index_report as report
from chitragupta.registry._index_terms import term_id

UNITS = ["ch-1", "ch-2", "ch-3", "ch-4"]


def term(key, glossary=None, **extra):
    return {
        "key": key,
        "glossary": glossary or key,
        "spellings": [key],
        "defined_in": [],
        "always": [],
        "parents": [],
        "print": None,
        **extra,
    }


def data(*terms, **extra):
    return {
        "min_mentions": 2,
        "terms": {term_id(t["key"]): t for t in terms},
        "not_indexable": [],
        **extra,
    }


def mention(count, indexed, midsentence=None, spellings=None):
    return {
        "count": count,
        "indexed": indexed,
        "midsentence": midsentence or {},
        "spellings": spellings or {},
    }


def sidecars(**per_unit):
    return {unit: {"terms": terms} for unit, terms in per_unit.items()}


def kinds(found):
    return [finding["kind"] for finding in found]


def test_a_term_with_no_page_anywhere():
    found = report.findings(data(term("calibration offset")), {}, {}, UNITS, [])
    assert kinds(found) == ["no-locator"]
    assert found[0]["fix"] == '[drop] terms = ["calibration offset"]  # or a [variants] spelling'


def test_a_term_on_most_chapters_is_generic():
    model = term_id("model")
    side = {unit: {model: mention(5, True)} for unit in UNITS[:3]}
    found = report.findings(data(term("model")), sidecars(**side), {}, UNITS, [])
    assert kinds(found) == ["generic"]
    assert "3 of 4 chapters" in found[0]["message"]


def test_a_single_mention_below_the_threshold_suggests_always():
    twin = term_id("twin")
    side = sidecars(**{"ch-1": {twin: mention(2, True)}, "ch-2": {twin: mention(1, False)}})
    found = report.findings(data(term("twin")), side, {}, UNITS, [])
    assert kinds(found) == ["below-threshold"]
    assert found[0]["fix"] == '[always] "twin" = ["ch-2"]'


def test_mixed_casing_suggests_print():
    chain = term_id("markov chain")
    counts = {"Markov chain": 3, "markov chain": 2}
    side = sidecars(**{"ch-1": {chain: mention(5, True, counts)}})
    found = report.findings(data(term("markov chain", "Markov chain")), side, {}, UNITS, [])
    assert kinds(found) == ["mixed-case"]
    assert found[0]["fix"] == '[print] "markov chain" = "Markov chain"'


def test_casing_that_differs_only_in_number_is_not_mixed():
    chain = term_id("markov chain")
    side = sidecars(**{"ch-1": {chain: mention(2, True, {"Markov chain": 1, "Markov chains": 1})}})
    assert report.findings(data(term("markov chain")), side, {}, UNITS, []) == []


def test_three_terms_sharing_a_word_suggest_a_parent():
    names = ("stage 0", "stage 1", "stage 2")
    side = sidecars(**{"ch-1": {term_id(name): mention(2, True) for name in names}})
    found = report.findings(data(*(term(name) for name in names)), side, {}, UNITS, [])
    assert kinds(found) == ["family"]
    assert found[0]["fix"] == '[parent] "stage" = ["stage 0", "stage 1", "stage 2"]'


def test_a_family_already_under_a_parent_is_not_reported_and_articles_are_no_family():
    names = ("stage 0", "stage 1", "stage 2")
    terms = [term(name, parents=["stage"]) for name in names]
    terms += [term(f"the {word}") for word in ("map", "list", "set")]
    side = sidecars(**{"ch-1": {term_id(t["key"]): mention(2, True) for t in terms}})
    assert report.findings(data(*terms), side, {}, UNITS, []) == []


def test_an_index_toml_entry_that_matched_nothing_is_unused():
    twin = term_id("digital twin")
    doc = {"variants": {"digital twin": ["dt twin"]}, "always": {"digital twin": ["ch-3"]}}
    side = sidecars(**{"ch-1": {twin: mention(2, True, spellings={"digital twin": 2})}})
    found = report.findings(data(term("digital twin")), side, doc, UNITS, [])
    assert kinds(found) == ["unused", "unused"]
    assert {finding["fix"] for finding in found} == {
        'remove "dt twin" from [variants] "digital twin"',
        'remove "ch-3" from [always] "digital twin"',
    }


def test_maths_with_no_plain_spelling_and_dangling_see_are_reported():
    found = report.findings(data(not_indexable=["`x` vector"]), {}, {}, UNITS, ["DT"])
    assert kinds(found) == ["not-indexable", "dangling-see"]


def test_write_puts_both_files_beside_the_other_registries(tmp_path):
    twin = term_id("digital twin")
    table = data(term("digital twin", "Digital twin", defined_in=["ch-1"]))
    side = sidecars(
        **{
            "ch-1": {twin: mention(2, True, {"digital twin": 2})},
            "ch-2": {twin: mention(1, False)},
        }
    )
    found = report.findings(table, side, {}, UNITS, [])
    md, js = report.write(tmp_path, table, side, found, entries=7)
    text = md.read_text(encoding="utf-8")
    assert md.name == "index.md" and js.name == "index.json"
    assert "7 entries, 1 finding" in text
    assert "[always]" in text
    assert "| Digital twin | ch-1 (2) | ch-2 (1) |" in text
    parsed = json.loads(js.read_text(encoding="utf-8"))
    assert parsed["summary"] == {"entries": 7, "findings": 1}
    assert parsed["terms"][0]["chapters"]["ch-2"] == {"count": 1, "indexed": False}
    again, _ = report.write(tmp_path, table, side, found, entries=7)
    assert again.read_text(encoding="utf-8") == text


def test_summary_line():
    assert (
        report.summary(523, 7, "x/index.md")
        == "index: 523 entries, 7 findings -> x/index.md (+ .json)"
    )
    assert report.summary(1, 1, "i.md") == "index: 1 entry, 1 finding -> i.md (+ .json)"


def test_a_capital_lowercased_on_no_evidence_is_named_with_its_fix():
    """Right for "Ecological twin", wrong for a proper noun the prose
    never uses mid-sentence: the report names each guess."""
    kalman = term_id("kalman filter")
    side = sidecars(**{"ch-1": {kalman: mention(2, True)}})
    found = report.findings(data(term("kalman filter", "Kalman filter")), side, {}, UNITS, [])
    assert kinds(found) == ["casing-guessed"]
    assert found[0]["fix"] == '[print] "kalman filter" = "Kalman filter"  # if it is a proper noun'
    printed = data(term("kalman filter", "Kalman filter", print="Kalman filter"))
    assert report.findings(printed, side, {}, UNITS, []) == []


def test_every_fix_line_is_valid_toml_even_for_a_key_holding_latex():
    import tomllib

    key = "$\\varepsilon$-greedy"
    found = report.findings(data(not_indexable=[key]), {}, {}, UNITS, [])
    found += report.findings(data(term('a "quoted" term')), {}, {}, UNITS, [])
    for finding in found:
        line = finding["fix"].split("  #")[0]
        if line.startswith("["):
            table, _, rest = line.partition("] ")
            tomllib.loads(f"{table}]\n{rest}\n")

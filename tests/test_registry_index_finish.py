"""`registry index`'s finishing step (#1168): read the typeset book's
`book.idx` and the chapters' sidecars, write `book-index.idx` with every
id turned into a printed entry, and run `upmendex` on it.

The `.idx` lines are the shape installed hyperref writes
(`|hyperpage`, `|hyperxindexformat{\\textbf}`); the parser never names
the macro, so these are fixtures, not a contract on hyperref.
"""

import json
import shutil

import pytest

from chitragupta.registry import _index_finish as finish
from chitragupta.registry import _index_terms
from chitragupta.registry._index_terms import term_id

TWIN, MODEL = term_id("digital twin"), term_id("model")
UNITS = ["ch-one", "ch-two"]


def identity(texts):
    return list(texts)


def term(key, glossary, **extra):
    return {
        "key": key,
        "glossary": glossary,
        "symbols": [],
        "print": None,
        "parents": [],
        "spellings": [key],
        "defined_in": [],
        "always": [],
        **extra,
    }


def book(tmp_path, idx, sidecars=None, **table):
    """A rendered book directory: `index-terms.json`, `book.idx` and one
    sidecar per unit carrying the table's digest."""
    data = {
        "min_mentions": 2,
        "skip_sections": [],
        "sort": "word",
        "letter_headings": False,
        "terms": {TWIN: term("digital twin", "Digital twin"), MODEL: term("model", "Model")},
        "see": {"DT": TWIN},
        "see_also": {},
        "parent_only": [],
        "not_indexable": [],
        "dropped": [],
        **table,
    }
    terms = tmp_path / "index-terms.json"
    terms.write_text(_index_terms.dumps(data), encoding="utf-8")
    digest = finish.digest(terms)
    for unit in UNITS:
        side = (sidecars or {}).get(unit, {"terms": {}})
        side = {"unit": unit, "terms_digest": digest, **side}
        (tmp_path / f"{unit}.index.json").write_text(json.dumps(side), encoding="utf-8")
    path = tmp_path / "book.idx"
    path.write_text(idx, encoding="utf-8")
    return path


IDX = (
    f"\\indexentry{{{TWIN}|hyperxindexformat{{\\textbf}}}}{{3}}\n"
    f"\\indexentry{{{MODEL}|hyperpage}}{{5}}\n"
    f"\\indexentry{{{TWIN}|hyperpage}}{{82}}\n"
)


class Ran:
    """A stand-in for `subprocess.run` that records the argv and, when it
    succeeds, leaves the `.ind` upmendex would have written."""

    def __init__(self, returncode=0, writes=True):
        self.returncode, self.writes, self.argv, self.cwd = returncode, writes, None, None
        self.stderr = "refused\n"

    def __call__(self, argv, cwd=None, **kwargs):
        self.argv, self.cwd = argv, cwd
        if self.returncode == 0 and self.writes:
            (cwd / "book.ind").write_text("\\begin{theindex}\n", encoding="utf-8")
        return self


@pytest.fixture(autouse=True)
def upmendex_on_path(monkeypatch, request):
    if "real_upmendex" not in request.node.name:
        monkeypatch.setattr(finish.programs, "resolve_program", lambda name: f"/bin/{name}")


def test_parse_reads_ids_encaps_and_pages_with_nested_braces():
    assert finish.parse(IDX + "noise\n") == [
        (TWIN, "|hyperxindexformat{\\textbf}", "3"),
        (MODEL, "|hyperpage", "5"),
        (TWIN, "|hyperpage", "82"),
    ]
    assert finish.parse("\\indexentry{t1}{4}\n") == [("t1", "", "4")]
    assert finish.parse("\\indexentry t1\n\\indexentry{t1\n\\indexentry{t1}\n") == []


def test_ids_become_printed_entries_and_encaps_and_pages_survive(tmp_path):
    side = {
        "terms": {
            TWIN: {"count": 2, "indexed": True, "spellings": {}, "midsentence": {"digital twin": 2}}
        }
    }
    idx = book(tmp_path, IDX, {"ch-one": side})
    ran = Ran()
    result = finish.finish(idx, UNITS, identity, run=ran)
    assert result.problems == []
    written = (tmp_path / "book-index.idx").read_text(encoding="utf-8")
    assert "\\indexentry{digital twin@digital twin|hyperxindexformat{\\textbf}}{3}" in written
    assert "\\indexentry{model@model|hyperpage}{5}" in written
    assert "\\indexentry{dt@DT|see{digital twin}}{3}" in written
    assert result.entries == 3
    assert idx.read_text(encoding="utf-8") == IDX


def test_upmendex_runs_on_the_rewritten_file_with_the_style(tmp_path):
    idx = book(tmp_path, IDX, sort="letter", letter_headings=True)
    ran = Ran()
    finish.finish(idx, UNITS, identity, run=ran)
    assert ran.argv == [
        "/bin/upmendex", "-q", "-l", "-s", "book.ist", "-o", "book.ind", "-t", "book.ilg",
        "book-index.idx",
    ]  # fmt: skip
    assert ran.cwd == tmp_path
    assert "headings_flag 1" in (tmp_path / "book.ist").read_text(encoding="utf-8")


def test_word_sorting_passes_no_letter_flag_and_a_gap_between_groups(tmp_path):
    ran = Ran()
    finish.finish(book(tmp_path, IDX), UNITS, identity, run=ran)
    assert "-l" not in ran.argv
    assert "headings_flag 0" in (tmp_path / "book.ist").read_text(encoding="utf-8")


def test_an_upmendex_failure_is_a_problem_naming_its_log(tmp_path):
    (tmp_path / "book.ilg").write_text("## Error: bad\n", encoding="utf-8")
    result = finish.finish(book(tmp_path, IDX), UNITS, identity, run=Ran(1))
    assert any(
        "upmendex failed" in problem and "## Error: bad" in problem for problem in result.problems
    )


def test_an_id_the_table_does_not_hold_is_a_stale_build(tmp_path):
    idx = book(tmp_path, IDX + "\\indexentry{t00000000|hyperpage}{9}\n")
    ran = Ran()
    result = finish.finish(idx, UNITS, identity, run=ran)
    assert any("t00000000" in problem and "rebuild" in problem for problem in result.problems)
    assert ran.argv is None


def test_a_missing_or_stale_sidecar_refuses(tmp_path):
    idx = book(tmp_path, IDX)
    (tmp_path / "ch-two.index.json").unlink()
    side = json.loads((tmp_path / "ch-one.index.json").read_text(encoding="utf-8"))
    side["terms_digest"] = "0" * 40
    (tmp_path / "ch-one.index.json").write_text(json.dumps(side), encoding="utf-8")
    result = finish.finish(idx, UNITS, identity, run=Ran())
    assert any("ch-two" in problem and "--index-terms" in problem for problem in result.problems)
    assert any("ch-one" in problem and "older term table" in problem for problem in result.problems)


def test_a_missing_term_table_or_idx_refuses(tmp_path):
    result = finish.finish(tmp_path / "book.idx", UNITS, identity, run=Ran())
    assert any("index-terms.json" in problem for problem in result.problems)
    book(tmp_path, IDX).unlink()
    result = finish.finish(tmp_path / "book.idx", UNITS, identity, run=Ran())
    assert any("book.idx" in problem and "lualatex" in problem for problem in result.problems)


def test_casing_counts_from_every_chapter_are_summed(tmp_path):
    def side(counts):
        return {
            "terms": {MODEL: {"count": 1, "indexed": True, "spellings": {}, "midsentence": counts}}
        }

    idx = book(
        tmp_path, IDX, {"ch-one": side({"model": 1}), "ch-two": side({"Model": 1, "model": 1})}
    )
    finish.finish(idx, UNITS, identity, run=Ran())
    assert "{model@model|hyperpage}" in (tmp_path / "book-index.idx").read_text(encoding="utf-8")


def test_a_dangling_cross_reference_is_reported_not_printed(tmp_path):
    idx = book(tmp_path, f"\\indexentry{{{MODEL}|hyperpage}}{{5}}\n")
    result = finish.finish(idx, UNITS, identity, run=Ran())
    assert result.dangling == ["DT"]
    assert "DT" not in (tmp_path / "book-index.idx").read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("upmendex") is None, reason="upmendex not installed")
def test_the_real_upmendex_sorts_quotes_and_nests(tmp_path):
    stage = term_id("stage 0")
    table = {
        "terms": {
            TWIN: term("digital twin", "Digital twin"),
            MODEL: term("a!b", "A!b"),
            stage: term("stage 0", "Stage 0", parents=["stage"]),
        },
    }
    idx = book(
        tmp_path,
        f"\\indexentry{{{TWIN}|hyperpage}}{{3}}\n\\indexentry{{{MODEL}|hyperpage}}{{4}}\n"
        f"\\indexentry{{{stage}|hyperpage}}{{6}}\n",
        **table,
    )
    result = finish.finish(idx, UNITS, identity)
    assert result.problems == []
    ind = (tmp_path / "book.ind").read_text(encoding="utf-8")
    assert "\\item a!b, \\hyperpage{4}" in ind
    assert ind.count("\\item stage\n") == 1
    assert "\\subitem 0, \\hyperpage{6}" in ind
    assert "\\item DT, \\see{digital twin}{3}" in ind


def test_upmendex_exiting_zero_without_an_ind_is_a_failure(tmp_path):
    """What TeX Live's `openout_any = p` does to an output path it refuses."""
    result = finish.finish(book(tmp_path, IDX), UNITS, identity, run=Ran(writes=False))
    assert any(
        "upmendex failed (0)" in problem and "refused" in problem for problem in result.problems
    )


def test_no_upmendex_is_a_missing_binary(tmp_path, monkeypatch):
    monkeypatch.setattr(finish.programs, "resolve_program", lambda name: None)
    result = finish.finish(book(tmp_path, IDX), UNITS, identity, run=Ran())
    assert any(problem.startswith("[missing-binary] upmendex") for problem in result.problems)

"""chitragupta/retrieval_cache.py's read-only index builder (#1232).

`read_only_index` is the index a caller that must not write the BM25 cache
builds: `dossier status`'s drift scan, and spelling correction's
vocabulary, which every `query_terms` call can reach. The properties
pinned here are the ones a caller relies on it for: it never saves, it
reuses a cached entry only when that entry is sound, it leaves
`_load_index`'s missing-file count alone, and a second call over the same
rows pays nothing.
"""

import pytest

from chitragupta import ledger, retrieval, retrieval_cache

from tests.conftest import add_citable


@pytest.fixture
def rows(ledger_con):
    add_citable(ledger_con, "a2024", title="A Digital Twin Of A Greenhouse")
    add_citable(ledger_con, "b2024", title="Structural Health Monitoring")
    retrieval_cache._forget_cache()
    retrieval_cache._READ_ONLY_MEMO.clear()
    return ledger.all_items(ledger_con)


def counting(calls: list[str]):
    """`retrieval._tokenize_item`, recording each citekey it tokenizes."""

    def tokenize_item(row):
        calls.append(row["citekey"])
        return retrieval._tokenize_item(row)

    return tokenize_item


def test_it_never_saves_the_cache(rows, monkeypatch):
    monkeypatch.setattr(retrieval_cache, "_save_cache", lambda *_: pytest.fail("saved"))
    index = retrieval_cache.read_only_index(rows, retrieval._tokenize_item)
    assert set(index) == {"a2024", "b2024"}
    assert index["b2024"]["term_freqs"]["structural"] == 1


def test_a_sound_cached_entry_is_reused(rows, monkeypatch):
    entry = {
        "fingerprint": retrieval_cache._fingerprint(rows[0]),
        "length": 1,
        "term_freqs": {"cached": 1},
    }
    monkeypatch.setattr(retrieval_cache, "_load_cache", lambda: {rows[0]["citekey"]: entry})
    calls: list[str] = []
    index = retrieval_cache.read_only_index(rows, counting(calls))
    assert index[rows[0]["citekey"]] is entry
    assert calls == [rows[1]["citekey"]]


def test_a_malformed_cached_entry_is_retokenized(rows, monkeypatch):
    """#504's shape check, which `_load_index` applies and `_drift.py`'s
    builder did not: a matching fingerprint over a `term_freqs` that is
    not a dict costs one re-tokenization, never a crash downstream."""
    entry = {"fingerprint": retrieval_cache._fingerprint(rows[0]), "length": 1, "term_freqs": []}
    monkeypatch.setattr(retrieval_cache, "_load_cache", lambda: {rows[0]["citekey"]: entry})
    calls: list[str] = []
    index = retrieval_cache.read_only_index(rows, counting(calls))
    assert isinstance(index[rows[0]["citekey"]]["term_freqs"], dict)
    assert sorted(calls) == ["a2024", "b2024"]


def test_it_leaves_the_missing_parsed_count_alone(rows, monkeypatch):
    monkeypatch.setattr(retrieval_cache, "_MISSING_PARSED", 7)
    retrieval_cache.read_only_index(rows, retrieval._tokenize_item)
    assert retrieval_cache._MISSING_PARSED == 7


def test_unchanged_rows_are_not_tokenized_twice(rows):
    """Drift and spelling correction both build this index in one
    `dossier status`; on a cold cache the second build must be free."""
    calls: list[str] = []
    tokenize_item = counting(calls)
    first = retrieval_cache.read_only_index(rows, tokenize_item)
    second = retrieval_cache.read_only_index(rows, tokenize_item)
    assert second is first
    assert sorted(calls) == ["a2024", "b2024"]


def test_the_same_rows_in_another_order_are_not_tokenized_again(rows):
    """Drift reads its rows unordered and the vocabulary reads them by
    citekey; the memo must treat the two as one corpus."""
    calls: list[str] = []
    tokenize_item = counting(calls)
    first = retrieval_cache.read_only_index(rows, tokenize_item)
    assert retrieval_cache.read_only_index(list(reversed(rows)), tokenize_item) is first
    assert sorted(calls) == ["a2024", "b2024"]


def test_changed_rows_are_rebuilt(rows, ledger_con):
    calls: list[str] = []
    tokenize_item = counting(calls)
    retrieval_cache.read_only_index(rows, tokenize_item)
    add_citable(ledger_con, "c2024", title="Another Paper")
    index = retrieval_cache.read_only_index(ledger.all_items(ledger_con), tokenize_item)
    assert set(index) == {"a2024", "b2024", "c2024"}

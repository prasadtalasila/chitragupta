import pytest

from chitragupta import ledger, retrieval, retrieval_cache

from tests.conftest import add_citable


@pytest.fixture
def rows(ledger_con):
    add_citable(ledger_con, "a2024", title="A Digital Twin Of A Greenhouse")
    add_citable(ledger_con, "b2024", title="Structural Health Monitoring")
    retrieval_cache._forget_cache()
    return ledger.all_items(ledger_con)


def counting(calls: list[str]):
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
    calls: list[str] = []
    tokenize_item = counting(calls)
    first = retrieval_cache.read_only_index(rows, tokenize_item)
    second = retrieval_cache.read_only_index(rows, tokenize_item)
    assert second is first
    assert sorted(calls) == ["a2024", "b2024"]


def test_the_same_rows_in_another_order_are_not_tokenized_again(rows):
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

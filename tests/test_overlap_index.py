"""src/overlap_index.py: the disk-cached corpus-wide n-gram fingerprint
index that scripts/verbatim_check.py's `overlap` mode is ported onto."""

import json
from pathlib import Path

import pytest

from src import config, ledger, overlap_index

from tests.conftest import make_reference


def _add_parsed_item(ledger_con, tmp_path, citekey, text, pdf_bytes=b"%PDF-1.4 dummy"):
    """A ledger row with status='parsed', a real pdf_hash (from a
    throwaway PDF file, so upsert_reference actually computes one), and
    parsed_path pointing at real text on disk."""
    pdf = tmp_path / f"{citekey}.pdf"
    pdf.write_bytes(pdf_bytes)
    parsed = tmp_path / f"{citekey}.txt"
    parsed.write_text(text)
    ledger.upsert_reference(ledger_con, make_reference(citekey=citekey, pdf_path=str(pdf)))
    ledger.mark_parsed(ledger_con, citekey, parsed)
    return parsed


class TestGramHashes:
    def test_matches_recompute_on_the_matching_slice(self):
        words = "the quick brown fox jumps over the lazy dog repeatedly".split()
        hashes = overlap_index.gram_hashes(words, 4)
        for j in range(len(hashes)):
            assert overlap_index.gram_hashes(words[j:j + 4], 4) == [hashes[j]]

    def test_length_is_word_count_minus_n_plus_one(self):
        words = list("abcdefgh")
        assert len(overlap_index.gram_hashes(words, 3)) == len(words) - 3 + 1

    def test_fewer_words_than_n_returns_empty(self):
        assert overlap_index.gram_hashes(["a", "b"], 4) == []

    def test_deterministic_across_calls(self):
        words = "alpha beta gamma delta".split()
        assert overlap_index.gram_hashes(words, 4) == overlap_index.gram_hashes(words, 4)

    def test_different_grams_hash_differently(self):
        a = overlap_index.gram_hashes("alpha beta gamma delta".split(), 4)
        b = overlap_index.gram_hashes("wholly unrelated word sequence".split(), 4)
        assert a != b


class TestFingerprintDocument:
    def test_builds_postings_with_page_and_position(self, isolated_config, tmp_path):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("alpha beta gamma delta\ftoo short")
        fp = overlap_index.fingerprint_document("smith_2024", "hash1", str(parsed), n=4)
        assert fp.postings == [(overlap_index.gram_hashes(["alpha", "beta", "gamma", "delta"], 4)[0], 1, 0)]

    def test_cache_file_is_written(self, isolated_config, tmp_path):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("alpha beta gamma delta epsilon")
        overlap_index.fingerprint_document("smith_2024", "hash1", str(parsed), n=4)
        cache_path = config.OVERLAP_DIR / "docs" / "smith_2024.fpr"
        assert cache_path.exists()
        data = json.loads(cache_path.read_text())
        assert data["n"] == 4
        assert data["key"][0] == "hash1"

    def test_unchanged_key_reuses_cache_without_rebuilding(self, isolated_config, tmp_path, monkeypatch):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("alpha beta gamma delta epsilon")
        first = overlap_index.fingerprint_document("smith_2024", "hash1", str(parsed), n=4)

        def _boom(*a, **kw):
            raise AssertionError("should not rebuild when the cache key is unchanged")

        monkeypatch.setattr(overlap_index, "_build_fingerprint", _boom)
        second = overlap_index.fingerprint_document("smith_2024", "hash1", str(parsed), n=4)
        assert second.postings == first.postings

    def test_changed_pdf_hash_triggers_rebuild(self, isolated_config, tmp_path):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("alpha beta gamma delta epsilon")
        overlap_index.fingerprint_document("smith_2024", "hash1", str(parsed), n=4)
        rebuilt = overlap_index.fingerprint_document("smith_2024", "hash2", str(parsed), n=4)
        assert rebuilt.key[0] == "hash2"

    def test_changed_n_triggers_rebuild(self, isolated_config, tmp_path):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("alpha beta gamma delta epsilon zeta")
        fp4 = overlap_index.fingerprint_document("smith_2024", "hash1", str(parsed), n=4)
        fp3 = overlap_index.fingerprint_document("smith_2024", "hash1", str(parsed), n=3)
        assert fp4.n == 4 and fp3.n == 3
        assert len(fp3.postings) != len(fp4.postings)

    def test_corrupt_cache_json_is_rebuilt_not_fatal(self, isolated_config, tmp_path):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("alpha beta gamma delta")
        cache_path = config.OVERLAP_DIR / "docs" / "smith_2024.fpr"
        cache_path.parent.mkdir(parents=True)
        cache_path.write_text("{not valid json")
        fp = overlap_index.fingerprint_document("smith_2024", "hash1", str(parsed), n=4)
        assert len(fp.postings) == 1

    def test_non_dict_cache_content_is_treated_as_miss(self, isolated_config, tmp_path):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("alpha beta gamma delta")
        cache_path = config.OVERLAP_DIR / "docs" / "smith_2024.fpr"
        cache_path.parent.mkdir(parents=True)
        cache_path.write_text("[1, 2, 3]")
        fp = overlap_index.fingerprint_document("smith_2024", "hash1", str(parsed), n=4)
        assert len(fp.postings) == 1

    def test_non_list_postings_field_is_treated_as_miss(self, isolated_config, tmp_path):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("alpha beta gamma delta")
        key = overlap_index._fingerprint_key("hash1", str(parsed))
        cache_path = config.OVERLAP_DIR / "docs" / "smith_2024.fpr"
        cache_path.parent.mkdir(parents=True)
        cache_path.write_text(json.dumps(
            {"tokenizer_version": 1, "n": 4, "key": key, "postings": "nope"}
        ))
        fp = overlap_index.fingerprint_document("smith_2024", "hash1", str(parsed), n=4)
        assert len(fp.postings) == 1

    def test_malformed_posting_entry_is_treated_as_miss(self, isolated_config, tmp_path):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("alpha beta gamma delta")
        key = overlap_index._fingerprint_key("hash1", str(parsed))
        cache_path = config.OVERLAP_DIR / "docs" / "smith_2024.fpr"
        cache_path.parent.mkdir(parents=True)
        cache_path.write_text(json.dumps(
            {"tokenizer_version": 1, "n": 4, "key": key, "postings": [["not-an-int", 1, 0]]}
        ))
        fp = overlap_index.fingerprint_document("smith_2024", "hash1", str(parsed), n=4)
        assert len(fp.postings) == 1

    def test_missing_parsed_file_falls_back_to_null_stat_key(self, isolated_config, tmp_path):
        missing = tmp_path / "does-not-exist.txt"
        assert overlap_index._fingerprint_key("hash1", str(missing)) == ["hash1", None, None]


class TestGramsForCitekey:
    def test_min_page_wins_across_pages(self, isolated_config, tmp_path):
        page1 = "alpha beta gamma delta epsilon"
        page2 = "unrelated content here entirely"
        page3 = "alpha beta gamma delta again"
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("\f".join([page1, page2, page3]))

        grams = overlap_index.grams_for_citekey("smith_2024", "hash1", str(parsed), n=4)
        shared_hash = overlap_index.gram_hashes(["alpha", "beta", "gamma", "delta"], 4)[0]
        assert grams[shared_hash] == 1

    def test_page_shorter_than_n_contributes_nothing(self, isolated_config, tmp_path):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("only two words")
        grams = overlap_index.grams_for_citekey("smith_2024", "hash1", str(parsed), n=8)
        assert grams == {}


class TestLedgerItem:
    def test_no_ledger_file_returns_none(self, isolated_config):
        assert not config.LEDGER_PATH.exists()
        assert overlap_index.ledger_item("smith_2024") is None

    def test_unknown_citekey_returns_none(self, ledger_con):
        assert overlap_index.ledger_item("nonexistent_2024") is None

    def test_non_parsed_status_returns_none(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="smith_2024"))
        assert overlap_index.ledger_item("smith_2024") is None

    def test_null_pdf_hash_returns_none(self, ledger_con, tmp_path):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("some text")
        ledger.upsert_reference(ledger_con, make_reference(citekey="smith_2024"))
        ledger.mark_parsed(ledger_con, "smith_2024", parsed)
        assert overlap_index.ledger_item("smith_2024") is None

    def test_recorded_but_missing_file_returns_none(self, ledger_con, tmp_path):
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "some text")
        row = ledger_con.execute("SELECT parsed_path FROM items WHERE citekey = ?", ("smith_2024",)).fetchone()
        Path(row[0]).unlink()
        assert overlap_index.ledger_item("smith_2024") is None

    def test_valid_item_returns_pdf_hash_and_parsed_path(self, ledger_con, tmp_path):
        parsed = _add_parsed_item(ledger_con, tmp_path, "smith_2024", "some text")
        result = overlap_index.ledger_item("smith_2024")
        assert result is not None
        pdf_hash, parsed_path = result
        assert pdf_hash and Path(parsed_path) == parsed


class TestBuildCorpusIndex:
    def test_empty_corpus_returns_empty_index(self, isolated_config):
        index = overlap_index.build_corpus_index(n=4)
        assert index.citekeys == []
        assert len(index.grams) == 0

    def test_index_is_sorted_and_lookup_finds_a_known_gram(self, ledger_con, tmp_path):
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "alpha beta gamma delta epsilon")
        _add_parsed_item(ledger_con, tmp_path, "doe_2023", "wholly unrelated word sequence here")

        index = overlap_index.build_corpus_index(n=4)
        assert index.citekeys == ["doe_2023", "smith_2024"]
        assert list(index.grams) == sorted(index.grams)

        shared_hash = overlap_index.gram_hashes(["alpha", "beta", "gamma", "delta"], 4)[0]
        assert overlap_index.pages_for_gram(index, shared_hash) == [1]
        assert overlap_index.pages_for_gram(index, shared_hash, citekey="smith_2024") == [1]
        assert overlap_index.pages_for_gram(index, shared_hash, citekey="doe_2023") == []

    def test_recorded_but_deleted_parsed_file_is_skipped(self, ledger_con, tmp_path):
        parsed = _add_parsed_item(ledger_con, tmp_path, "smith_2024", "alpha beta gamma delta")
        parsed.unlink()
        index = overlap_index.build_corpus_index(n=4)
        assert index.citekeys == []

    def test_unchanged_corpus_is_a_full_cache_hit(self, ledger_con, tmp_path, monkeypatch):
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "alpha beta gamma delta epsilon")
        overlap_index.build_corpus_index(n=4)

        def _boom(*a, **kw):
            raise AssertionError("must not re-fingerprint an unchanged corpus")

        monkeypatch.setattr(overlap_index, "_build_fingerprint", _boom)
        second = overlap_index.build_corpus_index(n=4)
        assert second.citekeys == ["smith_2024"]

    def test_only_the_changed_document_is_refingerprinted(self, ledger_con, tmp_path, monkeypatch):
        parsed_a = _add_parsed_item(ledger_con, tmp_path, "aaa_2024", "alpha beta gamma delta")
        _add_parsed_item(ledger_con, tmp_path, "bbb_2024", "wholly unrelated words entirely")
        overlap_index.build_corpus_index(n=4)

        parsed_a.write_text("alpha beta gamma delta changed content now")
        # Force a distinct mtime so the (size, mtime_ns) half of the cache
        # key is guaranteed to change even on a filesystem with coarse
        # mtime resolution.
        import os
        st = parsed_a.stat()
        os.utime(parsed_a, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))

        calls = []
        real = overlap_index._build_fingerprint

        def _spy(citekey, *a, **kw):
            calls.append(citekey)
            return real(citekey, *a, **kw)

        monkeypatch.setattr(overlap_index, "_build_fingerprint", _spy)
        overlap_index.build_corpus_index(n=4)
        assert calls == ["aaa_2024"]

    def test_corrupt_header_json_triggers_rebuild(self, ledger_con, tmp_path):
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "alpha beta gamma delta")
        config.OVERLAP_DIR.mkdir(parents=True)
        (config.OVERLAP_DIR / "index.json").write_text("{not valid json")
        index = overlap_index.build_corpus_index(n=4)
        assert index.citekeys == ["smith_2024"]

    def test_header_not_a_dict_triggers_rebuild(self, ledger_con, tmp_path):
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "alpha beta gamma delta")
        config.OVERLAP_DIR.mkdir(parents=True)
        (config.OVERLAP_DIR / "index.json").write_text("[1, 2, 3]")
        index = overlap_index.build_corpus_index(n=4)
        assert index.citekeys == ["smith_2024"]

    def test_header_version_mismatch_triggers_rebuild(self, ledger_con, tmp_path):
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "alpha beta gamma delta")
        overlap_index.build_corpus_index(n=4)
        header_path = config.OVERLAP_DIR / "index.json"
        header = json.loads(header_path.read_text())
        header["version"] = 999
        header_path.write_text(json.dumps(header))
        index = overlap_index.build_corpus_index(n=4)
        assert index.citekeys == ["smith_2024"]

    def test_missing_index_bin_triggers_rebuild(self, ledger_con, tmp_path):
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "alpha beta gamma delta")
        overlap_index.build_corpus_index(n=4)
        (config.OVERLAP_DIR / "index.bin").unlink()
        index = overlap_index.build_corpus_index(n=4)
        assert index.citekeys == ["smith_2024"]
        assert (config.OVERLAP_DIR / "index.bin").exists()

    def test_truncated_index_bin_triggers_rebuild(self, ledger_con, tmp_path):
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "alpha beta gamma delta")
        overlap_index.build_corpus_index(n=4)
        bin_path = config.OVERLAP_DIR / "index.bin"
        bin_path.write_bytes(bin_path.read_bytes()[:-1])
        index = overlap_index.build_corpus_index(n=4)
        assert index.citekeys == ["smith_2024"]

    def test_header_citekeys_not_a_list_triggers_rebuild(self, ledger_con, tmp_path):
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "alpha beta gamma delta")
        overlap_index.build_corpus_index(n=4)
        header_path = config.OVERLAP_DIR / "index.json"
        header = json.loads(header_path.read_text())
        header["citekeys"] = "not-a-list"
        header_path.write_text(json.dumps(header))
        index = overlap_index.build_corpus_index(n=4)
        assert index.citekeys == ["smith_2024"]


class TestPagesForGram:
    def test_unknown_gram_returns_empty(self, ledger_con, tmp_path):
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "alpha beta gamma delta")
        index = overlap_index.build_corpus_index(n=4)
        assert overlap_index.pages_for_gram(index, 0xDEADBEEF) == []

    def test_a_gram_repeated_on_one_page_is_not_duplicated(self, ledger_con, tmp_path):
        # "alpha beta gamma delta" occurs twice on page 1 -- two postings,
        # same page, must collapse to one entry.
        _add_parsed_item(
            ledger_con, tmp_path, "smith_2024",
            "alpha beta gamma delta filler words alpha beta gamma delta",
        )
        index = overlap_index.build_corpus_index(n=4)
        shared_hash = overlap_index.gram_hashes(["alpha", "beta", "gamma", "delta"], 4)[0]
        assert overlap_index.pages_for_gram(index, shared_hash) == [1]

    def test_pages_are_returned_in_ascending_order(self, ledger_con, tmp_path):
        # doe_2023 sorts before smith_2024, so its posting for the shared
        # gram is merged in first -- but it's on page 2, while
        # smith_2024's (merged in second) is on page 1. Insertion order
        # alone would come back [2, 1]; pages_for_gram must still return
        # [1, 2].
        _add_parsed_item(ledger_con, tmp_path, "doe_2023", "zzz filler\falpha beta gamma delta")
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "alpha beta gamma delta\funrelated content here")

        index = overlap_index.build_corpus_index(n=4)
        shared_hash = overlap_index.gram_hashes(["alpha", "beta", "gamma", "delta"], 4)[0]
        assert overlap_index.pages_for_gram(index, shared_hash) == [1, 2]


class TestPostingsForGram:
    def test_unknown_gram_returns_empty(self, ledger_con, tmp_path):
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "alpha beta gamma delta")
        index = overlap_index.build_corpus_index(n=4)
        assert overlap_index.postings_for_gram(index, 0xDEADBEEF) == []

    def test_empty_index_returns_empty(self, isolated_config):
        index = overlap_index.build_corpus_index(n=4)
        assert overlap_index.postings_for_gram(index, 0xDEADBEEF) == []

    def test_a_single_posting_carries_citekey_page_and_position(self, ledger_con, tmp_path):
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "alpha beta gamma delta")
        index = overlap_index.build_corpus_index(n=4)
        gram_hash = overlap_index.gram_hashes(["alpha", "beta", "gamma", "delta"], 4)[0]
        assert overlap_index.postings_for_gram(index, gram_hash) == [("smith_2024", 1, 0)]

    def test_repeated_gram_on_one_page_yields_one_posting_per_occurrence(self, ledger_con, tmp_path):
        # Unlike pages_for_gram, nothing here is deduplicated: scan mode
        # needs every occurrence (and its own token_position) to align a
        # run, not just "this page has a match".
        _add_parsed_item(
            ledger_con, tmp_path, "smith_2024",
            "alpha beta gamma delta filler words alpha beta gamma delta",
        )
        index = overlap_index.build_corpus_index(n=4)
        gram_hash = overlap_index.gram_hashes(["alpha", "beta", "gamma", "delta"], 4)[0]
        postings = overlap_index.postings_for_gram(index, gram_hash)
        assert sorted(postings) == [("smith_2024", 1, 0), ("smith_2024", 1, 6)]

    def test_postings_from_multiple_citekeys_are_all_returned(self, ledger_con, tmp_path):
        _add_parsed_item(ledger_con, tmp_path, "doe_2023", "alpha beta gamma delta")
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "alpha beta gamma delta")
        index = overlap_index.build_corpus_index(n=4)
        gram_hash = overlap_index.gram_hashes(["alpha", "beta", "gamma", "delta"], 4)[0]
        postings = overlap_index.postings_for_gram(index, gram_hash)
        assert sorted(postings) == [("doe_2023", 1, 0), ("smith_2024", 1, 0)]

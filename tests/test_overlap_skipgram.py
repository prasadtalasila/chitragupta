"""src/overlap_skipgram.py: tier 2's stemmed skip-gram index -- the
disk-cached, family-split analogue of src/overlap_index.py's exact
8-gram index, built for src/review/verbatim_check.py's `_skipgram_tier_findings`.
"""

import json

from src import config, ledger, overlap_skipgram

from tests.conftest import make_reference


def _add_parsed_item(ledger_con, tmp_path, citekey, text, pdf_bytes=b"%PDF-1.4 dummy"):
    pdf = tmp_path / f"{citekey}.pdf"
    pdf.write_bytes(pdf_bytes)
    parsed = tmp_path / f"{citekey}.txt"
    parsed.write_text(text)
    ledger.upsert_reference(ledger_con, make_reference(citekey=citekey, pdf_path=str(pdf)))
    ledger.mark_parsed(ledger_con, citekey, parsed)
    return parsed


class TestStemFilter:
    def test_stopwords_are_dropped(self):
        stems, positions = overlap_skipgram.stem_filter(["the", "validation", "of", "twins"])
        assert stems == ["valid", "twin"]
        assert positions == [1, 3]

    def test_positions_index_the_original_list(self):
        words = ["digital", "the", "twin", "a", "requires"]
        stems, positions = overlap_skipgram.stem_filter(words)
        assert [words[p] for p in positions] == ["digital", "twin", "requires"]

    def test_a_purely_numeric_token_is_kept_unstemmed(self):
        stems, positions = overlap_skipgram.stem_filter(["figure", "2024", "shows"])
        assert stems == ["figur", "2024", "show"]
        assert positions == [0, 1, 2]

    def test_all_stopwords_yields_empty(self):
        assert overlap_skipgram.stem_filter(["the", "a", "of"]) == ([], [])


class TestSkipgramPostings:
    def test_identical_text_matches_on_both_families(self):
        words = "the validation of a digital twin requires continuous comparison against measurements taken from the physical asset".split()
        a = overlap_skipgram.skipgram_postings(words, overlap_skipgram.DEFAULT_N)
        b = overlap_skipgram.skipgram_postings(words, overlap_skipgram.DEFAULT_N)
        assert a == b
        assert len(a) >= 1

    def test_wholly_different_text_shares_no_hash(self):
        a = overlap_skipgram.skipgram_postings(
            "the validation of a digital twin requires continuous comparison against measurements taken from the physical asset".split(),
            overlap_skipgram.DEFAULT_N,
        )
        b = overlap_skipgram.skipgram_postings(
            "a recipe for sourdough bread needs flour water salt and patient overnight fermentation before baking".split(),
            overlap_skipgram.DEFAULT_N,
        )
        assert {h for h, _s, _e in a}.isdisjoint({h for h, _s, _e in b})

    def test_a_single_word_substitution_only_breaks_its_own_family(self):
        # The property the whole module docstring is built on: an edit
        # at original index i can only ever cost the family whose
        # parity i belongs to. Substituting the word at an EVEN index
        # (4, "digital" -> "physical") must leave every hash the ODD
        # family produced completely unchanged.
        source = "the validation of a digital twin requires continuous comparison against measurements taken from the physical asset".split()
        edited = list(source)
        edited[4] = "physical"  # even index

        n = overlap_skipgram.DEFAULT_N
        source_odd = {h for h, s, _e in overlap_skipgram.skipgram_postings(source, n) if s % 2 == 1}
        edited_odd = {h for h, s, _e in overlap_skipgram.skipgram_postings(edited, n) if s % 2 == 1}
        assert source_odd
        assert source_odd == edited_odd

    def test_a_stopword_for_content_word_swap_at_a_fixed_position_still_matches(self):
        # Regression for the bug this module's docstring documents:
        # splitting into families on the *filtered* stream (stopword
        # removal before the even/odd split) let a stopword<->content
        # change desynchronize every later position between two texts.
        # Splitting on the *original* stream first (what this module
        # does) must not.
        source = (
            "the validation of a digital twin requires continuous "
            "comparison against measurements taken from the physical asset"
        ).split()
        draft = (
            "the validation of one digital twin requires constant "
            "comparison against measurements drawn from the physical plant"
        ).split()
        n = overlap_skipgram.DEFAULT_N
        source_hashes = {h for h, _s, _e in overlap_skipgram.skipgram_postings(source, n)}
        draft_postings = overlap_skipgram.skipgram_postings(draft, n)
        assert any(h in source_hashes for h, _s, _e in draft_postings), (
            "no skip-gram survived a same-position stopword/content-word swap"
        )

    def test_start_and_end_bound_the_matched_window(self):
        words = "alpha beta gamma delta epsilon zeta eta theta iota".split()
        for gh, start, end in overlap_skipgram.skipgram_postings(words, 3):
            assert 0 <= start < end <= len(words)

    def test_too_few_family_members_yields_no_postings(self):
        # DEFAULT_N content words are needed in *one* family; four
        # distinct content words split roughly 2/2 is not enough.
        assert overlap_skipgram.skipgram_postings(
            "alpha beta gamma delta".split(), overlap_skipgram.DEFAULT_N
        ) == []


class TestNumericWindowsAreNotEvidence:
    """#180: bare numbers are an effective ~10-token vocabulary, so two
    long enough numeric tables share a skip-gram by chance alone --
    measured as 97 of 125 unique findings on the first real-corpus run.
    A window is evidence only if fewer than `MAX_NUMERIC_SHARE` of its
    stems are bare numbers.
    """

    def test_an_all_numeric_table_row_yields_no_postings(self):
        # A page-number run, or a scoring grid's row: nothing here is a
        # word, so nothing here distinguishes this document from any
        # other document with a table in it.
        assert overlap_skipgram.skipgram_postings(
            "1 4 2 7 3 9 0 6 5 8 2 3 8 1".split(), overlap_skipgram.DEFAULT_N
        ) == []

    def test_a_figure_among_content_words_still_yields_postings(self):
        # The case #180 explicitly asks to keep: "48.2 billion" quoted by
        # two papers is genuine shared wording, and a token-level "drop
        # every digit" rule would have lost it. The even family here
        # reduces to `annual reach 2 dollar fiscal across region` -- one
        # number among six words -- so every window it makes survives.
        words = ("annual revenue reached 48 2 billion dollars during the "
                 "2021 fiscal year across every regional market").split()
        starts = [s for _h, s, _e in overlap_skipgram.skipgram_postings(words, 5)]
        assert 0 in starts, "a window holding a figure among content words was dropped"

    def test_the_bar_is_fewer_than_half_the_window(self):
        # Exactly at the boundary, from both sides. Stopwords on every
        # even index leave that family empty, so each list makes exactly
        # one window, on the odd family: three numbers of five is out,
        # two is in.
        three = "the 1 the alpha the 2 the beta the 3".split()
        two = "the 1 the alpha the 2 the beta the delta".split()
        assert overlap_skipgram.skipgram_postings(three, 5) == []
        assert len(overlap_skipgram.skipgram_postings(two, 5)) == 1


class TestGradedParaphraseDetection:
    """The property #133's benchmark and its own graded fixtures pin:
    a synonym swapped at a fixed *even* stride (so every substitution
    lands on the same original-index parity) is always caught by
    whichever family that stride never touches -- however wide the
    stride gets, as long as it stays even."""

    SOURCE = (
        "the validation of a digital twin requires continuous comparison "
        "against measurements taken from the physical asset every single "
        "time an engineer wants a trustworthy answer about the system"
    ).split()

    @staticmethod
    def _swap_every_nth_word(words, stride, replacement="X"):
        edited = list(words)
        for i in range(stride - 1, len(edited), stride):
            edited[i] = f"{replacement}{i}"
        return edited

    def test_every_fourth_word_swap_is_caught(self):
        self._assert_caught(4)

    def test_every_sixth_word_swap_is_caught(self):
        self._assert_caught(6)

    def test_every_eighth_word_swap_is_caught(self):
        self._assert_caught(8)

    def test_every_tenth_word_swap_is_caught(self):
        self._assert_caught(10)

    def _assert_caught(self, stride):
        n = overlap_skipgram.DEFAULT_N
        edited = self._swap_every_nth_word(self.SOURCE, stride)
        source_hashes = {h for h, _s, _e in overlap_skipgram.skipgram_postings(self.SOURCE, n)}
        edited_postings = overlap_skipgram.skipgram_postings(edited, n)
        assert any(h in source_hashes for h, _s, _e in edited_postings), (
            f"no skip-gram survived an every-{stride}th-word swap"
        )

    def test_a_full_clean_restatement_is_not_caught(self):
        # The tier's honest boundary: genuine restatement in new
        # structure -- not a word-for-word substitution -- shares no
        # skip-gram, the same way it shares no exact 8-gram. #133 does
        # not claim to catch this; docs/PLAGIARISM-DESIGN.md's caveat still
        # applies to tier 2.
        restated = (
            "engineers routinely check that a simulated model still tracks "
            "its physical counterpart by repeatedly measuring the gap "
            "between what each one reports"
        ).split()
        n = overlap_skipgram.DEFAULT_N
        source_hashes = {h for h, _s, _e in overlap_skipgram.skipgram_postings(self.SOURCE, n)}
        restated_hashes = {h for h, _s, _e in overlap_skipgram.skipgram_postings(restated, n)}
        assert source_hashes.isdisjoint(restated_hashes)


class TestFingerprintDocument:
    def test_cache_file_is_written(self, isolated_config, tmp_path):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text(
            "the validation of a digital twin requires continuous "
            "comparison against measurements taken from physical assets"
        )
        overlap_skipgram.fingerprint_document("smith_2024", "hash1", str(parsed), n=5)
        cache_path = config.OVERLAP_DIR / "docs" / "smith_2024.skipgram.fpr"
        assert cache_path.exists()
        data = json.loads(cache_path.read_text())
        assert data["n"] == 5
        assert data["key"][0] == "hash1"

    def test_unchanged_key_reuses_cache_without_rebuilding(self, isolated_config, tmp_path, monkeypatch):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("digital twins require continuous validation against physical measurements")
        first = overlap_skipgram.fingerprint_document("smith_2024", "hash1", str(parsed), n=5)

        def _boom(*a, **kw):
            raise AssertionError("should not rebuild when the cache key is unchanged")

        monkeypatch.setattr(overlap_skipgram, "_build_fingerprint", _boom)
        second = overlap_skipgram.fingerprint_document("smith_2024", "hash1", str(parsed), n=5)
        assert second.postings == first.postings

    def test_changed_pdf_hash_triggers_rebuild(self, isolated_config, tmp_path):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("digital twins require continuous validation against physical measurements")
        overlap_skipgram.fingerprint_document("smith_2024", "hash1", str(parsed), n=5)
        second = overlap_skipgram.fingerprint_document("smith_2024", "hash2", str(parsed), n=5)
        assert second.key[0] == "hash2"

    def test_changed_n_triggers_rebuild(self, isolated_config, tmp_path):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("alpha beta gamma delta epsilon zeta eta theta iota kappa")
        fp5 = overlap_skipgram.fingerprint_document("smith_2024", "hash1", str(parsed), n=5)
        fp4 = overlap_skipgram.fingerprint_document("smith_2024", "hash1", str(parsed), n=4)
        assert fp5.n == 5
        assert fp4.n == 4

    def test_non_dict_cache_content_is_treated_as_miss(self, isolated_config, tmp_path):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("alpha beta gamma delta epsilon")
        cache_path = config.OVERLAP_DIR / "docs" / "smith_2024.skipgram.fpr"
        cache_path.parent.mkdir(parents=True)
        cache_path.write_text("[1, 2, 3]")
        fp = overlap_skipgram.fingerprint_document("smith_2024", "hash1", str(parsed), n=4)
        assert fp.n == 4

    def test_non_list_postings_field_is_treated_as_miss(self, isolated_config, tmp_path):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("alpha beta gamma delta epsilon")
        key = overlap_skipgram._fingerprint_key("hash1", str(parsed))
        cache_path = config.OVERLAP_DIR / "docs" / "smith_2024.skipgram.fpr"
        cache_path.parent.mkdir(parents=True)
        cache_path.write_text(json.dumps(
            {"tokenizer_version": overlap_skipgram._TOKENIZER_VERSION, "n": 4,
             "key": key, "postings": "nope"}
        ))
        fp = overlap_skipgram.fingerprint_document("smith_2024", "hash1", str(parsed), n=4)
        assert fp.n == 4

    def test_malformed_posting_entry_is_treated_as_miss(self, isolated_config, tmp_path):
        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("alpha beta gamma delta epsilon")
        key = overlap_skipgram._fingerprint_key("hash1", str(parsed))
        cache_path = config.OVERLAP_DIR / "docs" / "smith_2024.skipgram.fpr"
        cache_path.parent.mkdir(parents=True)
        cache_path.write_text(json.dumps(
            {"tokenizer_version": overlap_skipgram._TOKENIZER_VERSION, "n": 4, "key": key,
             "postings": [["not-an-int", 1, 0]]}
        ))
        fp = overlap_skipgram.fingerprint_document("smith_2024", "hash1", str(parsed), n=4)
        assert fp.n == 4

    def test_own_cache_file_is_independent_of_the_exact_tiers(self, isolated_config, tmp_path):
        # The whole point of a separate namespace (module docstring): a
        # stemmer/stopword-list change must never invalidate tier 1's
        # cache, and vice versa -- verified here by confirming the two
        # tiers write to two entirely different files for the same doc.
        from src import overlap_index

        parsed = tmp_path / "smith_2024.txt"
        parsed.write_text("digital twins require continuous validation against physical measurements")
        overlap_index.fingerprint_document("smith_2024", "hash1", str(parsed), n=8)
        overlap_skipgram.fingerprint_document("smith_2024", "hash1", str(parsed), n=5)
        assert (config.OVERLAP_DIR / "docs" / "smith_2024.fpr").exists()
        assert (config.OVERLAP_DIR / "docs" / "smith_2024.skipgram.fpr").exists()


class TestBuildCorpusIndex:
    def test_empty_corpus_returns_empty_index(self, isolated_config):
        index = overlap_skipgram.build_corpus_index(n=5)
        assert index.citekeys == []
        assert len(index.grams) == 0

    def test_index_is_sorted_and_lookup_finds_a_known_gram(self, ledger_con, tmp_path):
        _add_parsed_item(
            ledger_con, tmp_path, "smith_2024",
            "the validation of a digital twin requires continuous comparison "
            "against measurements taken from the physical asset",
        )
        _add_parsed_item(
            ledger_con, tmp_path, "doe_2023",
            "a recipe for sourdough bread needs flour water salt and patient "
            "overnight fermentation before baking",
        )
        index = overlap_skipgram.build_corpus_index(n=5)
        assert index.citekeys == ["doe_2023", "smith_2024"]
        assert list(index.grams) == sorted(index.grams)

    def test_unchanged_corpus_is_a_full_cache_hit(self, ledger_con, tmp_path, monkeypatch):
        _add_parsed_item(
            ledger_con, tmp_path, "smith_2024",
            "digital twins require continuous validation against physical measurements",
        )
        overlap_skipgram.build_corpus_index(n=5)

        def _boom(*a, **kw):
            raise AssertionError("must not re-fingerprint an unchanged corpus")

        monkeypatch.setattr(overlap_skipgram, "_build_fingerprint", _boom)
        second = overlap_skipgram.build_corpus_index(n=5)
        assert second.citekeys == ["smith_2024"]

    def test_header_not_a_dict_triggers_rebuild(self, ledger_con, tmp_path):
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "digital twins require continuous validation")
        overlap_skipgram.build_corpus_index(n=5)
        (config.OVERLAP_DIR / "skipgram_index.json").write_text("[1, 2, 3]")
        index = overlap_skipgram.build_corpus_index(n=5)
        assert index.citekeys == ["smith_2024"]

    def test_header_version_mismatch_triggers_rebuild(self, ledger_con, tmp_path):
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "digital twins require continuous validation")
        overlap_skipgram.build_corpus_index(n=5)
        header_path = config.OVERLAP_DIR / "skipgram_index.json"
        header = json.loads(header_path.read_text())
        header["version"] = 999
        header_path.write_text(json.dumps(header))
        index = overlap_skipgram.build_corpus_index(n=5)
        assert index.citekeys == ["smith_2024"]

    def test_header_citekeys_not_a_list_triggers_rebuild(self, ledger_con, tmp_path):
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "digital twins require continuous validation")
        overlap_skipgram.build_corpus_index(n=5)
        header_path = config.OVERLAP_DIR / "skipgram_index.json"
        header = json.loads(header_path.read_text())
        header["citekeys"] = "not-a-list"
        header_path.write_text(json.dumps(header))
        index = overlap_skipgram.build_corpus_index(n=5)
        assert index.citekeys == ["smith_2024"]

    def test_missing_index_bin_triggers_rebuild(self, ledger_con, tmp_path):
        _add_parsed_item(ledger_con, tmp_path, "smith_2024", "digital twins require continuous validation")
        overlap_skipgram.build_corpus_index(n=5)
        (config.OVERLAP_DIR / "skipgram_index.bin").unlink()
        index = overlap_skipgram.build_corpus_index(n=5)
        assert index.citekeys == ["smith_2024"]
        assert (config.OVERLAP_DIR / "skipgram_index.bin").exists()

    def test_truncated_index_bin_triggers_rebuild(self, ledger_con, tmp_path):
        # Needs an actually non-empty index.bin: five distinct content
        # words split into two families of 2-3 each never reaches
        # DEFAULT_N=5 in either family, so a *shorter* text than this
        # produces zero postings and an empty (un-truncatable) file.
        _add_parsed_item(
            ledger_con, tmp_path, "smith_2024",
            "the validation of a digital twin requires continuous comparison "
            "against measurements taken from the physical asset",
        )
        overlap_skipgram.build_corpus_index(n=5)
        bin_path = config.OVERLAP_DIR / "skipgram_index.bin"
        original = bin_path.read_bytes()
        assert original, "fixture text produced no postings -- nothing to truncate"
        bin_path.write_bytes(original[:-1])
        index = overlap_skipgram.build_corpus_index(n=5)
        assert index.citekeys == ["smith_2024"]

    def test_postings_for_gram_returns_citekey_page_position(self, ledger_con, tmp_path):
        _add_parsed_item(
            ledger_con, tmp_path, "smith_2024",
            "the validation of a digital twin requires continuous comparison "
            "against measurements taken from the physical asset",
        )
        index = overlap_skipgram.build_corpus_index(n=5)
        assert len(index.grams) > 0
        gh = index.grams[0]
        postings = overlap_skipgram.postings_for_gram(index, gh)
        assert postings
        for citekey, page, position in postings:
            assert citekey == "smith_2024"
            assert page >= 1
            assert position >= 0

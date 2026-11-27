import json
import os
from pathlib import Path

import pytest

from chitragupta import (
    acronyms,
    config,
    ledger,
    retrieval,
    retrieval_cache,
    retrieval_cli,
    retrieval_passages,
    retrieval_scoring,
    retrieval_spelling,
    retrieval_tables,
)

from tests.conftest import add_citable, make_reference, parsed_file, retrieval_cost, run_python


class TestTokenize:
    def test_lowercases_and_splits_alnum(self):
        assert retrieval._tokenize("Digital Twins ARE great") == ["digital", "twins", "great"]

    def test_drops_stopwords_and_short_words(self):
        assert retrieval._tokenize("a of on in for and to with is") == []

    def test_keeps_numbers(self):
        assert retrieval._tokenize("ISO 9001 standard") == ["iso", "9001", "standard"]

    def test_keeps_a_two_character_acronym(self):
        assert retrieval._tokenize("AI and DT for 5G networks") == ["ai", "dt", "5g", "networks"]

    def test_still_drops_a_single_character(self):
        assert retrieval._tokenize("a b c x y 1 2 3") == []

    def test_a_two_character_stopword_stays_out(self):
        assert retrieval._tokenize("of in at by on is AI") == ["ai"]


class TestShortQueryTerms:
    def test_no_short_terms_returns_empty(self):
        assert retrieval.short_query_terms("digital twin architecture") == []

    def test_a_two_character_word_is_no_longer_flagged(self):
        assert retrieval.short_query_terms("AI safety in 5G networks") == []

    def test_flags_one_character_words(self):
        assert retrieval.short_query_terms("a x y model") == ["x", "y"]

    def test_a_query_of_only_short_terms_is_entirely_flagged(self):
        assert retrieval.short_query_terms("x y z") == ["x", "y", "z"]


class TestQueryTerms:
    def test_strips_wh_words_and_a_modal(self):
        assert retrieval._query_terms("what are the failure modes of co-simulation") == [
            "failure",
            "modes",
            "co",
            "simulation",
        ]

    def test_strips_why_and_does(self):
        assert retrieval._query_terms("why does model calibration matter") == [
            "model",
            "calibration",
            "matter",
        ]

    def test_leaves_a_keyword_query_untouched(self):
        assert retrieval._query_terms("digital twin structural health monitoring") == [
            "digital",
            "twin",
            "structural",
            "health",
            "monitoring",
        ]

    def test_tokenize_itself_is_not_touched(self):
        assert retrieval._tokenize("what why how") == ["what", "why", "how"]


class TestSnippet:
    def test_centers_the_window_on_a_matching_term(self):
        text = "x" * 100 + " digital twin simulation " + "y" * 100
        snippet = retrieval._snippet(text, {"digital"}, window=20)
        assert "digital" in snippet

    def test_picks_the_window_covering_the_most_query_terms(self):
        text = "ABSTRACT twin " + "x " * 400 + " soil moisture twin controller " + "y " * 400
        snippet = retrieval._snippet(text, {"twin", "soil", "moisture"}, window=60)
        assert "soil" in snippet
        assert "moisture" in snippet

    def test_is_the_same_snippet_whatever_the_hash_seed(self):
        program = (
            "from chitragupta import retrieval;"
            "text = 'ABSTRACT twin ' + 'x '*400 + ' MIDDLE greenhouse ' "
            "+ 'y '*400 + ' END actuator ';"
            "terms = set(retrieval._tokenize('twin greenhouse actuator'));"
            "print(retrieval._snippet(text, terms, window=60))"
        )
        outputs = set()
        for seed in ("0", "1", "2", "3", "4"):
            env = {**os.environ, "PYTHONHASHSEED": seed}
            result = run_python("-c", program, env=env, check=True)
            outputs.add(result.stdout.strip())
        assert len(outputs) == 1, f"snippet varied with hash seed: {outputs}"

    def test_falls_back_to_start_of_text_when_no_term_found(self):
        text = "no matching terms here at all"
        snippet = retrieval._snippet(text, {"zzz"}, window=10)
        assert snippet == "no matchin"

    def test_fallback_snippet_also_strips_a_citation_marker(self):
        text = "no query terms appear here [3, 7] at all, just filler"
        snippet = retrieval._snippet(text, {"nonexistentterm"}, window=40)
        assert "[3, 7]" not in snippet


class TestSearch:
    def test_empty_query_returns_empty(self, ledger_con):
        assert retrieval.search("") == []

    def test_a_question_and_its_keyword_form_rank_the_same(self, ledger_con):
        add_citable(ledger_con, "a2024", title="Structural Health Monitoring")
        add_citable(ledger_con, "b2024", title="Unrelated Paper About Cats")
        add_citable(ledger_con, "c2024", title="What Is Wrong With Benchmarks What What")
        keyword_hits = [r.citekey for r in retrieval.search("structural health monitoring")]
        question_hits = [
            r.citekey for r in retrieval.search("what is structural health monitoring")
        ]
        assert keyword_hits == question_hits == ["a2024"]

    def test_a_two_character_acronym_ranks(self, ledger_con):
        add_citable(ledger_con, "a2024", title="5G Network Slicing")
        add_citable(ledger_con, "b2024", title="Unrelated Paper About Cats")
        assert [r.citekey for r in retrieval.search("5g")] == ["a2024"]

    def test_an_acronym_reaches_a_paper_that_only_spells_it_out(
        self, ledger_con, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {"DT": "digital twin"})
        add_citable(ledger_con, "a2024", title="A Digital Twin Of A Greenhouse")
        add_citable(ledger_con, "b2024", title="Unrelated Paper About Cats")
        monkeypatch.setattr(config, "ACRONYM_EXPANSION", False)
        assert retrieval.search("DT") == []
        monkeypatch.setattr(config, "ACRONYM_EXPANSION", True)
        assert [r.citekey for r in retrieval.search("DT")] == ["a2024"]

    def test_switching_expansion_off_leaves_the_ranking_alone(
        self, ledger_con, tmp_path, monkeypatch
    ):
        for citekey, title in (
            ("a2024", "A Digital Twin Of A Greenhouse"),
            ("b2024", "Twin Studies In Psychology"),
            ("c2024", "DT And Nothing Else"),
        ):
            add_citable(ledger_con, citekey, title=title)
        monkeypatch.setattr(config, "ACRONYM_EXPANSION", False)
        bare = [(r.citekey, r.score) for r in retrieval.search("DT twin", k=5)]

        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {"DT": "digital twin"})
        off = [(r.citekey, r.score) for r in retrieval.search("DT twin", k=5)]
        monkeypatch.setattr(config, "ACRONYM_EXPANSION", True)
        on = [(r.citekey, r.score) for r in retrieval.search("DT twin", k=5)]

        assert off == bare, "a vocabulary moved the ranking with expansion off"
        assert [key for key, _ in on] != [key for key, _ in off], (
            "the same vocabulary moved nothing with expansion on, so `off` proves nothing"
        )

    def test_an_added_term_scores_as_a_typed_one(self, ledger_con, monkeypatch):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {"DT": "twin"})
        add_citable(ledger_con, "typed2024", title="DT Study")
        add_citable(ledger_con, "added2024", title="Twin Study")
        scores = {r.citekey: r.score for r in retrieval.search("DT", k=5)}
        assert set(scores) == {"typed2024", "added2024"}
        assert scores["typed2024"] == pytest.approx(scores["added2024"])

    def test_the_snippet_is_cut_around_an_added_term(self, ledger_con, tmp_path, monkeypatch):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {"DT": "digital twin"})
        parsed = parsed_file("a2024")
        parsed.write_text(
            "opening matter " * 60 + "the digital twin of the greenhouse was calibrated"
        )
        add_citable(ledger_con, "a2024", title="Greenhouse")
        ledger.mark_parsed(ledger_con, "a2024", parsed)
        assert "calibrated" in retrieval.search("DT", k=1)[0].snippet

    def test_ranks_by_term_overlap_descending(self, ledger_con):
        add_citable(ledger_con, "a2024", title="Digital Twin Digital Twin Digital")
        add_citable(ledger_con, "b2024", title="Digital Twin Overview")
        add_citable(ledger_con, "c2024", title="Unrelated Paper About Cats")

        results = retrieval.search("digital twin", k=5)
        assert [r.citekey for r in results] == ["a2024", "b2024"]
        assert results[0].score > results[1].score

    def test_top_k_truncation(self, ledger_con):
        for i in range(5):
            add_citable(ledger_con, f"item{i}_2024", title="Digital Twin Paper")
        results = retrieval.search("digital twin", k=2)
        assert len(results) == 2

    @pytest.mark.parametrize("status", ["no_pdf", "discovered", "parse_failed"])
    def test_search_never_returns_an_unparsed_row(self, ledger_con, status):
        add_citable(ledger_con, "parsed_2024", title="Robotics In Practice")
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="web_2024", title="Robotics web page")
        )
        ledger_con.execute("UPDATE items SET status = ? WHERE citekey = 'web_2024'", (status,))
        ledger_con.commit()

        after = retrieval.search("robotics")
        assert [r.citekey for r in after] == ["parsed_2024"]
        assert after[0].score != 0

    def test_uses_parsed_text_when_available(self, ledger_con, tmp_path):
        parsed = parsed_file("a2024")
        parsed.write_text("this document mentions blockchain repeatedly blockchain blockchain")
        ref = make_reference(citekey="a2024", title="Unrelated Title")
        ledger.upsert_reference(ledger_con, ref)
        ledger.mark_parsed(ledger_con, "a2024", parsed)

        results = retrieval.search("blockchain")
        assert len(results) == 1
        assert results[0].citekey == "a2024"

    def test_missing_parsed_file_does_not_crash(self, ledger_con):
        ref = make_reference(citekey="a2024", title="Some Title About Robotics")
        ledger.upsert_reference(ledger_con, ref)
        ledger.mark_parsed(ledger_con, "a2024", parsed_file("does-not-exist"))

        results = retrieval.search("robotics")
        assert len(results) == 1
        assert results[0].citekey == "a2024"

    def test_only_a_parsed_row_counts_as_missing_its_text(self, ledger_con, capsys):
        ledger.upsert_reference(ledger_con, make_reference(citekey="a2024", title="Robotics"))
        ledger.upsert_reference(ledger_con, make_reference(citekey="b2024", title="Robotics Too"))
        ledger.mark_parsed(ledger_con, "b2024", parsed_file("does-not-exist"))
        retrieval.search("robotics")
        retrieval_cache.note_missing_parsed()
        assert "[note] 1 parsed source(s)" in capsys.readouterr().err
        retrieval_cache.note_missing_parsed()  # the count is taken, not kept
        assert capsys.readouterr().err == ""

    def test_undecodable_bytes_are_replaced_not_dropped(self, ledger_con):
        parsed = parsed_file("a2024")
        parsed.write_bytes(b"a na\xefve reading of robotics")
        add_citable(ledger_con, "a2024", title="Robotics")
        ledger.mark_parsed(ledger_con, "a2024", parsed)
        assert retrieval.search("nave") == []
        assert "�" in retrieval._full_text(ledger.all_items(ledger_con)[0])

    def test_parse_failed_status_does_not_serve_stale_parsed_text(self, ledger_con, tmp_path):
        parsed = parsed_file("a2024")
        parsed.write_text("this document mentions blockchain repeatedly blockchain blockchain")
        ref = make_reference(citekey="a2024", title="Unrelated Title")
        ledger.upsert_reference(ledger_con, ref)
        ledger.mark_parsed(ledger_con, "a2024", parsed)
        ledger.mark_parse_failed(ledger_con, "a2024", "corrupt pdf")

        assert retrieval.search("blockchain") == []

    def test_a_cached_hit_is_invalidated_by_a_later_parse_failure(self, ledger_con, tmp_path):
        parsed = parsed_file("a2024")
        parsed.write_text("this document mentions blockchain repeatedly blockchain blockchain")
        ref = make_reference(citekey="a2024", title="Unrelated Title")
        ledger.upsert_reference(ledger_con, ref)
        ledger.mark_parsed(ledger_con, "a2024", parsed)

        results = retrieval.search("blockchain")
        assert len(results) == 1
        assert results[0].citekey == "a2024"

        ledger.mark_parse_failed(ledger_con, "a2024", "corrupt pdf")
        assert retrieval.search("blockchain") == []

    def test_no_matching_terms_excludes_item(self, ledger_con):
        add_citable(ledger_con, "a2024", title="Completely unrelated")
        assert retrieval.search("nonexistentterm12345") == []

    def test_length_normalization_prevents_long_docs_from_winning_structurally(
        self, ledger_con, tmp_path
    ):
        short_parsed = parsed_file("short2024")
        short_parsed.write_text("Blockchain is the entire subject of this short paper.")
        long_parsed = parsed_file("long2024")
        long_parsed.write_text(
            "irrelevant filler word " * 400 + "blockchain mentioned twice blockchain here"
        )

        add_citable(ledger_con, "short2024", title="Short Paper")
        ledger.mark_parsed(ledger_con, "short2024", short_parsed)
        add_citable(ledger_con, "long2024", title="Long Paper")
        ledger.mark_parsed(ledger_con, "long2024", long_parsed)

        results = retrieval.search("blockchain")
        assert [r.citekey for r in results] == ["short2024", "long2024"]

    def test_score_is_a_float(self, ledger_con):
        add_citable(ledger_con, "a2024", title="Digital Twin")
        results = retrieval.search("digital")
        assert isinstance(results[0].score, float)

    def test_returns_at_most_one_result_per_citekey(self, ledger_con):
        for i in range(4):
            add_citable(ledger_con, f"item{i}_2024", title="Digital Twin Digital Twin")

        results = retrieval.search("digital twin", k=10)

        citekeys = [r.citekey for r in results]
        assert len(citekeys) == len(set(citekeys)) == 4


class TestIndexCaching:
    def test_cache_file_is_created_on_first_search(self, ledger_con, tmp_path):
        parsed = parsed_file("a2024")
        parsed.write_text("digital twin content")
        add_citable(ledger_con, "a2024", title="Digital Twin")
        ledger.mark_parsed(ledger_con, "a2024", parsed)

        assert not config.RETRIEVAL_INDEX_PATH.exists()
        retrieval.search("digital")
        assert config.RETRIEVAL_INDEX_PATH.exists()

    def test_second_call_does_not_reread_a_doc_outside_the_results(
        self, ledger_con, tmp_path, monkeypatch
    ):
        winner_parsed = parsed_file("winner2024")
        winner_parsed.write_text("digital twin digital twin content")
        loser_parsed = parsed_file("loser2024")
        loser_parsed.write_text("nothing related to the query at all, just filler text")

        add_citable(ledger_con, "winner2024", title="Digital Twin")
        ledger.mark_parsed(ledger_con, "winner2024", winner_parsed)
        add_citable(ledger_con, "loser2024", title="Unrelated")
        ledger.mark_parsed(ledger_con, "loser2024", loser_parsed)

        retrieval.search("digital twin", k=1)  # builds the cache

        read_calls = []
        real_read_text = Path.read_text

        def spy_read_text(self, *a, **kw):
            read_calls.append(self)
            return real_read_text(self, *a, **kw)

        monkeypatch.setattr(Path, "read_text", spy_read_text)

        results = retrieval.search("digital twin", k=1)
        assert [r.citekey for r in results] == ["winner2024"]
        assert loser_parsed not in read_calls

    def test_changed_parsed_file_content_triggers_reindex(self, ledger_con, tmp_path):
        parsed = parsed_file("a2024")
        parsed.write_text("nothing about the topic here")
        add_citable(ledger_con, "a2024", title="Some Title")
        ledger.mark_parsed(ledger_con, "a2024", parsed)
        assert retrieval.search("blockchain") == []

        parsed.write_text("blockchain blockchain blockchain")
        results = retrieval.search("blockchain")
        assert [r.citekey for r in results] == ["a2024"]

    def test_corrupt_cache_file_is_rebuilt_not_fatal(self, ledger_con, tmp_path):
        config.RETRIEVAL_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.RETRIEVAL_INDEX_PATH.write_text("{not valid json")
        add_citable(ledger_con, "a2024", title="Digital Twin")

        results = retrieval.search("digital")
        assert [r.citekey for r in results] == ["a2024"]

    def test_stale_schema_version_cache_is_rebuilt_not_trusted(self, ledger_con, tmp_path):
        config.RETRIEVAL_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.RETRIEVAL_INDEX_PATH.write_text(
            json.dumps(
                {
                    "version": 0,
                    "items": {"a2024": {"fingerprint": ["wrong"], "length": 1, "term_freqs": {}}},
                }
            )
        )
        add_citable(ledger_con, "a2024", title="Digital Twin")

        results = retrieval.search("digital")
        assert [r.citekey for r in results] == ["a2024"]

    def test_cache_that_is_valid_json_but_wrong_top_level_shape_is_rebuilt(
        self, ledger_con, tmp_path
    ):
        config.RETRIEVAL_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.RETRIEVAL_INDEX_PATH.write_text(json.dumps([1, 2, 3]))
        add_citable(ledger_con, "a2024", title="Digital Twin")

        results = retrieval.search("digital")
        assert [r.citekey for r in results] == ["a2024"]

    def test_cache_whose_items_value_is_the_wrong_shape_is_rebuilt(self, ledger_con):
        config.RETRIEVAL_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.RETRIEVAL_INDEX_PATH.write_text(
            json.dumps({"version": 1, "items": ["not", "a", "dict"]})
        )
        add_citable(ledger_con, "a2024", title="Digital Twin")

        results = retrieval.search("digital")
        assert [r.citekey for r in results] == ["a2024"]

    def test_cache_entry_for_one_citekey_that_is_the_wrong_shape_is_rebuilt(self, ledger_con):
        config.RETRIEVAL_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.RETRIEVAL_INDEX_PATH.write_text(
            json.dumps({"version": 1, "items": {"a2024": "not-a-dict"}})
        )
        add_citable(ledger_con, "a2024", title="Digital Twin")

        results = retrieval.search("digital")
        assert [r.citekey for r in results] == ["a2024"]

    def test_a_matching_fingerprint_with_missing_term_freqs_is_rebuilt(self, ledger_con):
        add_citable(ledger_con, "a2024", title="Digital Twin")
        with ledger.connection() as con:
            item = ledger.all_items(con)[0]
        fp = retrieval_cache._fingerprint(item)
        config.RETRIEVAL_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.RETRIEVAL_INDEX_PATH.write_text(
            json.dumps({"version": 1, "items": {"a2024": {"fingerprint": fp}}})
        )

        results = retrieval.search("digital")
        assert [r.citekey for r in results] == ["a2024"]

    def test_removed_citekey_is_dropped_from_the_cache(self, ledger_con):
        add_citable(ledger_con, "a2024", title="Digital Twin")
        retrieval.search("digital")
        with open(config.RETRIEVAL_INDEX_PATH) as f:
            assert "a2024" in json.load(f)["items"]

        ledger_con.execute("DELETE FROM items WHERE citekey = ?", ("a2024",))
        ledger_con.commit()
        retrieval.search("digital")
        with open(config.RETRIEVAL_INDEX_PATH) as f:
            assert "a2024" not in json.load(f)["items"]


class TestWindows:
    def test_returns_nothing_when_no_term_appears(self):
        assert retrieval._windows("nothing relevant here", {"blockchain"}, 50, 3) == []

    def test_a_term_inside_a_longer_word_is_not_an_anchor(self):
        text = "The maintainer said the detail was fair. Later, AI systems failed."
        (window,) = retrieval._windows(text, {"ai"}, 30, 1)
        assert "AI systems" in window

    def test_a_boundary_the_tokenizer_splits_on_still_anchors(self):
        text = "ai_model is the subject of this paper, at some length here"
        (window,) = retrieval._windows(text, {"ai"}, 30, 1)
        assert "ai_model" in window

    def test_a_term_inside_a_longer_word_does_not_score_a_window(self):
        text = "detail maintainer fairly said ||| soil AI ||| " + "filler " * 20
        (window,) = retrieval._windows(text, {"ai", "soil"}, 24, 1)
        assert "soil AI" in window

    def test_prefers_a_window_covering_more_distinct_terms(self):
        text = "moisture " * 20 + " ||| soil moisture sensor calibration ||| " + "moisture " * 20
        (best,) = retrieval._windows(text, {"soil", "moisture", "sensor"}, 60, 1)
        assert "soil" in best
        assert "sensor" in best

    def test_finds_a_passage_late_in_a_long_document(self):
        text = "twin " + "filler " * 6000 + "the pump is actuated by the twin controller"
        windows = retrieval._windows(text, {"pump", "actuated", "twin"}, 60, 1)
        assert "pump" in windows[0]

    def test_windows_do_not_overlap(self):
        text = "alpha " * 5 + "beta " * 200 + "alpha " * 5
        windows = retrieval._windows(text, {"alpha"}, 40, 2)
        assert len(windows) == 2
        assert windows[0] != windows[1]

    def test_returns_windows_in_document_order(self):
        text = "start marker one " + "x " * 300 + " end marker two"
        windows = retrieval._windows(text, {"marker", "start", "end"}, 40, 2)
        assert "start" in windows[0]
        assert "end" in windows[1]

    def test_respects_the_requested_count(self):
        text = ("term " + "pad " * 40) * 10
        assert len(retrieval._windows(text, {"term"}, 30, 3)) == 3

    def test_strips_a_numeric_citation_marker(self):
        text = "the result [12] shows a clear trend in the data"
        windows = retrieval._windows(text, {"result", "trend"}, 50, 1)
        assert "[12]" not in windows[0]
        assert "result" in windows[0] and "trend" in windows[0]

    def test_does_not_strip_a_non_numeric_bracket(self):
        text = "the result [Figure 2] shows a clear trend in the data here"
        windows = retrieval._windows(text, {"result", "trend"}, 50, 1)
        assert "[Figure 2]" in windows[0]


class TestWindowsExpandPipeTables:
    TABLE = (
        "Some prose before the table that mentions calibration.\n"
        "\n"
        "| Formalism | State form | Model behaviour |\n"
        "|---|---|---|\n"
        "| Difference Equations | discrete | deterministic |\n"
        "| Stochastic Differential | continuous | stochastic |\n"
        "\n"
        "Some prose after the table.\n"
    )

    def test_a_hit_inside_a_table_returns_the_whole_block(self):
        (window,) = retrieval._windows(self.TABLE, {"stochastic"}, 40, 1)
        assert "| Formalism | State form | Model behaviour |" in window
        assert "| Difference Equations | discrete | deterministic |" in window

    def test_the_block_keeps_its_row_structure(self):
        (window,) = retrieval._windows(self.TABLE, {"stochastic"}, 40, 1)
        rows = [line for line in window.split("\n") if line.startswith("|")]
        assert len(rows) == 4

    def test_a_hit_outside_a_table_is_untouched(self):
        text = "the result shows a clear trend in the data here"
        assert retrieval._windows(text, {"result", "trend"}, 50, 1) == [
            "the result shows a clear trend in the data here"
        ]

    def test_a_table_over_the_cap_keeps_its_header_row(self):
        wide = "| Name | Value |\n|---|---|\n" + "".join(
            f"| row{i} | needle |\n" for i in range(4000)
        )
        (window,) = retrieval._windows(wide, {"needle"}, 40, 1)
        assert window.startswith("| Name | Value |\n|---|---|")
        assert len(window) <= retrieval_tables._TABLE_BLOCK_MAX_CHARS

    def test_a_table_that_ends_the_document_is_still_a_block(self):
        text = "some prose beforehand\n\n| Name | Value |\n|---|---|\n| a | needle |"
        (window,) = retrieval._windows(text, {"needle"}, 20, 1)
        assert window.startswith("| Name | Value |")
        assert "| a | needle |" in window

    def test_a_hit_away_from_a_table_in_the_same_document_is_untouched(self):
        text = (
            "| Name | Value |\n|---|---|\n| a | b |\n\n"
            + "x " * 400
            + "the conclusion mentions calibration drift plainly"
        )
        (window,) = retrieval._windows(text, {"calibration", "drift"}, 60, 1)
        assert "\n" not in window
        assert "|" not in window

    def test_a_table_and_a_prose_hit_come_back_side_by_side(self):
        text = (
            "| Name | Value |\n|---|---|\n| a | needle |\n\n"
            + "x " * 400
            + "the conclusion returns to the needle question"
        )
        table, prose = retrieval._windows(text, {"needle"}, 60, 2)
        assert table.startswith("| Name | Value |\n|---|---|")
        assert "\n" not in prose

    def test_two_hits_in_one_table_collapse_to_a_single_block(self):
        rows = "".join(f"| row{i} | needle |\n" for i in range(30))
        text = "| Name | Value |\n|---|---|\n" + rows
        windows = retrieval._windows(text, {"needle"}, 60, 2)
        assert len(windows) == 1

    def test_a_lone_pipe_line_is_not_treated_as_a_table(self):
        text = "run the command | grep needle | sort and read the output"
        (window,) = retrieval._windows(text, {"needle"}, 60, 1)
        assert "\n" not in window


class TestEvidence:
    def _seed(self, con, tmp_path, text, citekey="a2024"):
        parsed = parsed_file(citekey)
        parsed.write_text(text)
        add_citable(con, citekey, title="A Paper")
        ledger.mark_parsed(con, citekey, parsed)

    def test_returns_the_supporting_passages(self, ledger_con, tmp_path):
        self._seed(
            ledger_con,
            tmp_path,
            "padding " * 100 + "simulation time must follow wall clock time" + " tail" * 50,
        )
        passages = retrieval_cli.evidence("a2024", "simulation wall clock", chars=80)
        assert any("wall clock" in p for p in passages)

    def test_reads_more_of_the_document_than_a_search_snippet(self, ledger_con, tmp_path):
        body = " ".join(f"clock segment {i} simulation" for i in range(200))
        self._seed(ledger_con, tmp_path, body)
        total = sum(len(p) for p in retrieval_cli.evidence("a2024", "clock simulation", chars=300))
        assert total > 500

    def test_an_empty_query_returns_nothing(self, ledger_con, tmp_path):
        self._seed(ledger_con, tmp_path, "some text")
        assert retrieval_cli.evidence("a2024", "the of and") == []

    def test_a_citekey_whose_pdf_never_parsed_is_refused(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="a2024", title="Robotics"))
        with pytest.raises(KeyError, match=r"a2024 has no parsed PDF \(status no_pdf\)"):
            retrieval_cli.evidence("a2024", "quantum entanglement")

    def test_parse_failed_status_does_not_serve_stale_parsed_text(self, ledger_con, tmp_path):
        self._seed(ledger_con, tmp_path, "simulation time must follow wall clock time")
        ledger.mark_parse_failed(ledger_con, "a2024", "corrupt pdf")
        with pytest.raises(KeyError, match=r"status parse_failed"):
            retrieval_cli.evidence("a2024", "wall clock")

    def test_the_title_alone_can_carry_a_match(self, ledger_con):
        add_citable(ledger_con, "a2024", title="Robotics And Control")
        assert retrieval_cli.evidence("a2024", "robotics", chars=40) != []

    def test_an_unknown_citekey_raises(self, ledger_con):
        import pytest

        with pytest.raises(KeyError, match="not in the ledger"):
            retrieval_cli.evidence("nope_2024", "anything")


class TestOneQueryOneSetOfTerms:
    QUERIES = [
        "DT fidelity",
        "digital twin fidelity",
        "what is a DT",
        "DT versus DM",
        "calibration",
        "the of and",
    ]

    @pytest.fixture
    def corpus(self, ledger_con, monkeypatch):
        monkeypatch.setattr(
            acronyms, "load_vocabulary", lambda: {"DT": "digital twin", "DM": "digital model"}
        )
        monkeypatch.setattr(config, "ACRONYM_EXPANSION", True)
        parsed = parsed_file("a2024")
        parsed.write_text(
            "opening matter " * 60 + "the digital twin of the greenhouse was calibrated"
        )
        add_citable(ledger_con, "a2024", title="Greenhouse")
        ledger.mark_parsed(ledger_con, "a2024", parsed)
        return ledger_con

    @staticmethod
    def _ranked_on(monkeypatch, run) -> "set[str] | None":
        seen = []
        real = retrieval_scoring.bm25_scores

        def spy(index, terms):
            seen.append(set(terms))
            return real(index, terms)

        monkeypatch.setattr(retrieval_scoring, "bm25_scores", spy)
        run()
        return seen[0] if seen else None

    @pytest.mark.parametrize("query", QUERIES)
    def test_evidence_windows_on_the_terms_search_ranks_on(self, corpus, monkeypatch, query):
        searched = self._ranked_on(monkeypatch, lambda: retrieval.search(query))
        windowed = []
        real = retrieval_cli._windows
        monkeypatch.setattr(
            retrieval_cli,
            "_windows",
            lambda text, terms, **kw: windowed.append(set(terms)) or real(text, terms, **kw),
        )
        retrieval_cli.evidence("a2024", query)
        assert (windowed[0] if windowed else None) == searched

    @pytest.mark.parametrize("query", QUERIES)
    def test_the_passage_unit_ranks_on_the_terms_search_ranks_on(self, corpus, monkeypatch, query):
        searched = self._ranked_on(monkeypatch, lambda: retrieval.search(query))
        passage = self._ranked_on(monkeypatch, lambda: retrieval_passages.search_passages(query))
        assert passage == searched

    @pytest.mark.parametrize("query", QUERIES)
    def test_the_drift_report_replays_the_terms_search_ranks_on(self, corpus, monkeypatch, query):
        from chitragupta.dossier import _drift

        searched = self._ranked_on(monkeypatch, lambda: retrieval.search(query))
        with ledger.reading() as con:
            rows = ledger.all_items(con)
        replayed = self._ranked_on(monkeypatch, lambda: _drift.Corpus(rows).matches([(query, "")]))
        assert replayed == searched

    def test_a_query_with_no_terms_never_reads_the_vocabulary(self, corpus, monkeypatch):
        def explode():
            raise AssertionError("read the vocabulary")

        monkeypatch.setattr(acronyms, "load_vocabulary", explode)
        assert retrieval.query_terms("what is the") == ([], [])

    def test_a_paper_search_ranks_first_on_an_acronym_has_an_evidence_window(self, corpus):
        assert [r.citekey for r in retrieval.search("DT", k=1)] == ["a2024"]
        (window,) = retrieval_cli.evidence("a2024", "DT", windows=1)
        assert "digital twin" in window

    def test_the_cli_logs_the_expansion_evidence_actually_used(self, corpus, capsys):
        from chitragupta import dossier

        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("# s\n")
        argv = ["evidence", "DT", "--citekey", "a2024", "--log", str(draft)]
        assert retrieval.main(argv) == 0
        captured = capsys.readouterr()
        assert "acronym expansion added: dt -> digital twin" in captured.err
        assert "no passage matches" not in captured.out
        row = (dossier.dossier_dir(draft) / "retrieval.md").read_text().rstrip().splitlines()[-1]
        assert [c.strip() for c in row.strip().strip("|").split("|")][8] == "dt -> digital twin"


class TestSpellingCorrection:
    @pytest.fixture
    def corpus(self, ledger_con):
        for citekey, text in (
            ("a2024", "opening matter " * 60 + "the structural model of the bridge"),
            ("b2024", "a structural health monitoring study"),
            ("c2024", "an unrelated paper about greenhouses"),
        ):
            parsed = parsed_file(citekey)
            parsed.write_text(text)
            add_citable(ledger_con, citekey, title=citekey)
            ledger.mark_parsed(ledger_con, citekey, parsed)
        return ledger_con

    @pytest.fixture
    def on(self, monkeypatch):
        monkeypatch.setattr(config, "SPELLING_CORRECTION", True)

    def test_off_a_typo_finds_nothing(self, corpus):
        assert retrieval.search("strucutral") == []

    def test_on_a_typo_reaches_the_papers_with_its_corpus_spelling(self, corpus, on):
        assert sorted(r.citekey for r in retrieval.search("strucutral")) == ["a2024", "b2024"]

    def test_off_never_builds_a_vocabulary(self, corpus, monkeypatch):
        monkeypatch.setattr(
            retrieval_spelling, "vocabulary", lambda _: pytest.fail("built a vocabulary")
        )
        for query in ("strucutral", "structural health", "what is a DT", "the of and"):
            assert all(entry.source == "acronym" for entry in retrieval.query_terms(query)[1])

    def test_evidence_windows_anchor_on_the_correction(self, corpus, on):
        (window,) = retrieval_cli.evidence("a2024", "strucutral", windows=1)
        assert "structural model" in window

    def test_the_drift_report_replays_the_correction(self, corpus, on):
        from chitragupta.dossier import _drift

        with ledger.reading() as con:
            rows = ledger.all_items(con)
        matches = _drift.Corpus(rows).matches([("strucutral", "")])
        assert sorted(matches) == ["a2024", "b2024"]

    def test_the_cli_notes_and_logs_the_correction(self, corpus, on, capsys):
        from chitragupta import dossier

        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("# s\n")
        assert retrieval.main(["search", "strucutral", "--log", str(draft)]) == 0
        captured = capsys.readouterr()
        assert "[note] spelling: searched 'structural' for 'strucutral'" in captured.err
        assert "spelling" not in captured.out
        row = (dossier.dossier_dir(draft) / "retrieval.md").read_text().rstrip().splitlines()[-1]
        assert [c.strip() for c in row.strip().strip("|").split("|")][8] == (
            "strucutral ~> structural"
        )


class TestCli:
    def _seed(self, con, tmp_path):
        parsed = parsed_file("a2024")
        parsed.write_text("padding " * 50 + "digital twin architecture patterns catalog")
        add_citable(con, "a2024", title="Twin Patterns")
        ledger.mark_parsed(con, "a2024", parsed)

    def test_search_prints_candidates_and_points_at_evidence(self, ledger_con, tmp_path, capsys):
        self._seed(ledger_con, tmp_path)
        assert retrieval.main(["search", "digital twin architecture"]) == 0
        out = capsys.readouterr().out
        assert "a2024" in out
        assert "evidence --citekey" in out
        assert "characters returned" in out

    def test_search_notes_what_acronym_expansion_added(
        self, ledger_con, tmp_path, capsys, monkeypatch
    ):
        self._seed(ledger_con, tmp_path)
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {"DT": "digital twin"})
        assert retrieval.main(["search", "DT patterns"]) == 0
        captured = capsys.readouterr()
        assert "acronym expansion added: dt -> digital twin" in captured.err
        assert "acronym expansion" not in captured.out

    def test_search_says_nothing_when_expansion_is_off(
        self, ledger_con, tmp_path, capsys, monkeypatch
    ):
        self._seed(ledger_con, tmp_path)
        monkeypatch.setattr(config, "ACRONYM_EXPANSION", False)
        assert retrieval.main(["search", "DT patterns"]) == 0
        assert "acronym expansion" not in capsys.readouterr().err

    def test_the_logged_row_records_what_was_added(self, ledger_con, tmp_path, monkeypatch):
        from chitragupta import dossier

        self._seed(ledger_con, tmp_path)
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {"DT": "digital twin"})
        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("# s\n")

        assert retrieval.main(["search", "DT patterns", "--log", str(draft)]) == 0
        logged = (dossier.dossier_dir(draft) / "retrieval.md").read_text()
        row = logged.rstrip().splitlines()[-1]
        assert [c.strip() for c in row.strip().strip("|").split("|")][8] == "dt -> digital twin"

    def test_evidence_prints_passages(self, ledger_con, tmp_path, capsys):
        self._seed(ledger_con, tmp_path)
        assert retrieval.main(["evidence", "architecture patterns", "--citekey", "a2024"]) == 0
        assert "patterns" in capsys.readouterr().out

    def test_evidence_on_an_unknown_citekey_exits_nonzero(self, ledger_con, tmp_path, capsys):
        self._seed(ledger_con, tmp_path)
        assert retrieval.main(["evidence", "x", "--citekey", "nope_2024"]) == 1
        assert "not in the ledger" in capsys.readouterr().err

    def test_evidence_strips_interrogatives_from_the_query(self, ledger_con, tmp_path):
        parsed = parsed_file("a2024")
        parsed.write_text(
            ("padding word here " * 40)
            + "architecture patterns catalog"
            + (
                " filler continues on and on beyond the window width here we go "
                "some more padding text words" * 10
            )
            + " what appears alone over here"
        )
        add_citable(ledger_con, "a2024", title="Patterns")
        ledger.mark_parsed(ledger_con, "a2024", parsed)

        with_question = retrieval_cli.evidence("a2024", "what are architecture patterns", windows=2)
        without_question = retrieval_cli.evidence("a2024", "architecture patterns", windows=2)
        assert with_question == without_question

    def test_search_says_nothing_about_parsed_text_that_is_there(
        self, ledger_con, tmp_path, capsys
    ):
        self._seed(ledger_con, tmp_path)
        assert retrieval.main(["search", "digital twin architecture"]) == 0
        assert "ranked on their title alone" not in capsys.readouterr().err

    @pytest.mark.parametrize("extra", [[], ["--y-prev", "earlier prose about twins"]])
    def test_search_notes_a_missing_parsed_file_on_every_run(
        self, ledger_con, tmp_path, capsys, extra
    ):
        self._seed(ledger_con, tmp_path)
        add_citable(ledger_con, "b2024", title="Twin Gone")
        ledger.mark_parsed(ledger_con, "b2024", parsed_file("b2024"))  # never written
        for _ in range(2):
            assert retrieval.main(["search", "digital twin", *extra]) == 0
            captured = capsys.readouterr()
            assert "[note] 1 parsed source(s)" in captured.err
            assert "chitragupta.corpus sync" in captured.err
            assert "title alone" not in captured.out

    def test_no_ledger_exits_nonzero_with_the_fix(self, isolated_config, capsys):
        assert retrieval.main(["search", "anything"]) == 1
        assert "chitragupta.corpus sync" in capsys.readouterr().err

    def test_no_results_is_not_an_error(self, ledger_con, tmp_path, capsys):
        self._seed(ledger_con, tmp_path)
        assert retrieval.main(["search", "quantum chromodynamics"]) == 0
        assert "No results." in capsys.readouterr().out

    def test_a_query_of_only_short_terms_warns_why_it_is_empty(self, ledger_con, tmp_path, capsys):
        self._seed(ledger_con, tmp_path)
        assert retrieval.main(["search", "x y"]) == 0
        err = capsys.readouterr().err
        assert "too short to search on" in err
        assert "x" in err
        assert "y" in err

    def test_a_mixed_query_still_warns_about_its_dropped_short_terms(
        self, ledger_con, tmp_path, capsys
    ):
        self._seed(ledger_con, tmp_path)
        assert retrieval.main(["search", "x digital twin architecture"]) == 0
        err = capsys.readouterr().err
        assert "too short to search on (dropped): x" in err

    def test_a_two_character_query_word_no_longer_warns(self, ledger_con, tmp_path, capsys):
        self._seed(ledger_con, tmp_path)
        assert retrieval.main(["search", "AI digital twin architecture"]) == 0
        assert "too short to search on" not in capsys.readouterr().err

    def test_a_query_with_no_short_terms_does_not_warn(self, ledger_con, tmp_path, capsys):
        self._seed(ledger_con, tmp_path)
        assert retrieval.main(["search", "digital twin architecture"]) == 0
        assert "too short to search on" not in capsys.readouterr().err

    def test_evidence_also_warns_about_a_short_term(self, ledger_con, tmp_path, capsys):
        self._seed(ledger_con, tmp_path)
        retrieval.main(["evidence", "x patterns", "--citekey", "a2024"])
        assert "too short to search on (dropped): x" in capsys.readouterr().err

    def test_evidence_with_no_matching_passage_is_not_an_error(self, ledger_con, tmp_path, capsys):
        self._seed(ledger_con, tmp_path)
        assert retrieval.main(["evidence", "quantum chromodynamics", "--citekey", "a2024"]) == 0
        out = capsys.readouterr().out
        assert "a2024: no passage matches that query" in out
        assert "no parsed text" in out

    def test_log_records_the_call_in_the_dossier(self, ledger_con, tmp_path, capsys):
        from chitragupta import dossier

        self._seed(ledger_con, tmp_path)
        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("# s\n")

        assert retrieval.main(["search", "digital twin architecture", "--log", str(draft)]) == 0
        calls, chars = retrieval_cost(dossier.dossier_dir(draft))
        assert calls == 1
        assert chars > 0
        assert "Logged to" in capsys.readouterr().out

    def test_log_records_the_collection_the_search_was_scoped_to(
        self, ledger_con, tmp_path, capsys
    ):
        from chitragupta import dossier
        from chitragupta.dossier import _retrieval

        parsed = parsed_file("a2024")
        parsed.write_text("padding " * 50 + "digital twin architecture patterns catalog")
        ledger.upsert_reference(
            ledger_con,
            make_reference(citekey="a2024", title="Twin Patterns", collections=("Digital twins",)),
        )
        ledger.mark_parsed(ledger_con, "a2024", parsed)

        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("# s\n")

        assert (
            retrieval.main(
                [
                    "search",
                    "digital twin architecture",
                    "--collection",
                    "Digital twins",
                    "--log",
                    str(draft),
                ]
            )
            == 0
        )
        assert _retrieval.recorded_queries_with_collection(dossier.dossier_dir(draft)) == [
            ("digital twin architecture", "Digital twins"),
        ]

    def test_evidence_log_records_no_collection(self, ledger_con, tmp_path, capsys):
        from chitragupta import dossier
        from chitragupta.dossier import _retrieval

        self._seed(ledger_con, tmp_path)
        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("# s\n")

        assert (
            retrieval.main(["evidence", "digital twin", "--citekey", "a2024", "--log", str(draft)])
            == 0
        )
        assert _retrieval.recorded_queries_with_collection(dossier.dossier_dir(draft)) == [
            ("digital twin", ""),
        ]

    def test_log_records_the_origin_the_search_was_declared_with(self, ledger_con, tmp_path):
        from chitragupta import dossier
        from chitragupta.dossier import _retrieval

        self._seed(ledger_con, tmp_path)
        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("# s\n")

        assert (
            retrieval.main(
                [
                    "search",
                    "digital twin architecture",
                    "--origin",
                    "declared",
                    "--log",
                    str(draft),
                ]
            )
            == 0
        )
        assert _retrieval.recorded_queries_with_origin(dossier.dossier_dir(draft)) == [
            ("digital twin architecture", "declared"),
        ]

    def test_evidence_also_takes_origin(self, ledger_con, tmp_path):
        from chitragupta import dossier
        from chitragupta.dossier import _retrieval

        self._seed(ledger_con, tmp_path)
        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("# s\n")

        assert (
            retrieval.main(
                [
                    "evidence",
                    "digital twin",
                    "--citekey",
                    "a2024",
                    "--origin",
                    "extended",
                    "--log",
                    str(draft),
                ]
            )
            == 0
        )
        assert _retrieval.recorded_queries_with_origin(dossier.dossier_dir(draft)) == [
            ("digital twin", "extended"),
        ]

    def test_an_invalid_origin_is_refused_by_argparse(self, ledger_con, tmp_path):
        with pytest.raises(SystemExit):
            retrieval.main(["search", "digital twin", "--origin", "invented"])

    def test_a_draft_outside_drafts_reports_but_does_not_fail_the_search(
        self, ledger_con, tmp_path, capsys
    ):
        self._seed(ledger_con, tmp_path)
        stray = tmp_path / "stray.md"
        stray.write_text("# s\n")
        assert retrieval.main(["search", "digital twin", "--log", str(stray)]) == 0
        captured = capsys.readouterr()
        assert "a2024" in captured.out
        assert "[not logged]" in captured.err

    def test_y_prev_widens_results_beyond_a_plain_search(self, ledger_con, tmp_path, capsys):
        self._seed(ledger_con, tmp_path)
        greenhouse = parsed_file("b2024")
        greenhouse.write_text("padding " * 50 + "greenhouse actuator calibration drifted")
        add_citable(ledger_con, "b2024", title="Greenhouse Actuator")
        ledger.mark_parsed(ledger_con, "b2024", greenhouse)

        assert (
            retrieval.main(
                [
                    "search",
                    "digital twin architecture",
                    "--y-prev",
                    "the greenhouse actuator calibration drifted overnight",
                ]
            )
            == 0
        )
        out = capsys.readouterr().out
        assert "a2024" in out
        assert "b2024" in out

    def test_y_prev_truncation_is_reported(self, ledger_con, tmp_path, capsys):
        from chitragupta import retrieval_iterative

        self._seed(ledger_con, tmp_path)
        long_prose = "digital twin " * 300
        assert retrieval.main(["search", "digital twin architecture", "--y-prev", long_prose]) == 0
        out = capsys.readouterr().out
        assert f"{retrieval_iterative.Y_PREV_MAX_CHARS} characters" in out

    def test_no_y_prev_flag_behaves_exactly_as_before(self, ledger_con, tmp_path, capsys):
        self._seed(ledger_con, tmp_path)
        assert retrieval.main(["search", "digital twin architecture"]) == 0
        assert "[note]" not in capsys.readouterr().out

    def test_log_records_reground_origin(self, ledger_con, tmp_path):
        from chitragupta import dossier
        from chitragupta.dossier import _retrieval

        self._seed(ledger_con, tmp_path)
        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("# s\n")

        assert (
            retrieval.main(
                [
                    "search",
                    "digital twin architecture",
                    "--y-prev",
                    "hand-edited prose",
                    "--log",
                    str(draft),
                    "--origin",
                    "reground",
                ]
            )
            == 0
        )
        pairs = _retrieval.recorded_queries_with_origin(dossier.dossier_dir(draft))
        assert ("digital twin architecture", "reground") in pairs

    def test_log_records_one_row_not_two_for_a_y_prev_call(self, ledger_con, tmp_path):
        from chitragupta import dossier

        self._seed(ledger_con, tmp_path)
        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("# s\n")

        retrieval.main(
            [
                "search",
                "digital twin architecture",
                "--y-prev",
                "hand-edited prose",
                "--log",
                str(draft),
                "--origin",
                "reground",
            ]
        )
        calls, _ = retrieval_cost(dossier.dossier_dir(draft))
        assert calls == 1


class TestDocsQuoteTheActualDefaults:
    def test_the_docs_quote_the_actual_defaults(self):
        cli = (config.shipped("docs", "CLI.md")).read_text(encoding="utf-8")
        chars_row = next(line for line in cli.splitlines() if "`--chars N`" in line)
        assert f"{retrieval_cli.EVIDENCE_CHARS} / 500" in chars_row

        windows_row = next(line for line in cli.splitlines() if "`--windows N`" in line)
        assert f"| {retrieval_cli.EVIDENCE_WINDOWS} |" in windows_row

        evidence_row = next(
            line for line in cli.splitlines() if '`evidence "<query>" --citekey KEY`' in line
        )
        assert f"{retrieval_cli.EVIDENCE_WINDOWS} by default" in evidence_row

        retr = (config.shipped("docs", "RETRIEVAL.md")).read_text(encoding="utf-8")
        assert (
            f"{retrieval_cli.EVIDENCE_WINDOWS} x {retrieval_cli.EVIDENCE_CHARS} characters" in retr
        )
        assert f"{retrieval_tables._TABLE_BLOCK_MAX_CHARS} characters" in " ".join(retr.split())
        for field, weight in config.RETRIEVAL_FIELD_WEIGHTS.items():
            assert f"weight_{field} = {weight}" in retr

    def test_y_prev_bound_is_pinned_in_cli_md(self):
        from chitragupta import retrieval_iterative

        cli = (config.shipped("docs", "CLI.md")).read_text(encoding="utf-8")
        y_prev_row = next(line for line in cli.splitlines() if line.startswith("| `--y-prev"))
        assert f"{retrieval_iterative.Y_PREV_MAX_CHARS} characters" in y_prev_row


class TestLogNeverFailsTheSearch:
    def _seed(self, con, tmp_path):
        parsed = parsed_file("a2024")
        parsed.write_text("padding " * 50 + "digital twin architecture patterns")
        add_citable(con, "a2024", title="Twin Patterns")
        ledger.mark_parsed(con, "a2024", parsed)

    def test_an_oserror_while_logging_is_reported_not_raised(
        self, ledger_con, tmp_path, capsys, monkeypatch
    ):
        from chitragupta import dossier

        self._seed(ledger_con, tmp_path)
        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("# s\n")

        def boom(*args, **kwargs):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(dossier, "log_retrieval", boom)

        assert retrieval.main(["search", "digital twin", "--log", str(draft)]) == 0
        captured = capsys.readouterr()
        assert "a2024" in captured.out, "the retrieval results must still be printed"
        assert "[not logged]" in captured.err
        assert "No space left on device" in captured.err


class TestTheIndexIsParsedOncePerProcess:
    def test_a_second_load_does_not_reread_the_file(self, ledger_con, tmp_path, monkeypatch):
        parsed = parsed_file("a2024")
        parsed.write_text("digital twin content", encoding="utf-8")
        add_citable(ledger_con, "a2024", title="Digital Twin")
        ledger.mark_parsed(ledger_con, "a2024", parsed)
        retrieval.search("digital")

        reads = []
        real = retrieval_cache._CACHE.read_file
        monkeypatch.setattr(retrieval_cache._CACHE, "read_file", lambda: reads.append(1) or real())
        retrieval_cache._load_cache()
        retrieval_cache._load_cache()
        assert reads == []

    def test_a_rewrite_by_this_process_is_seen_without_a_reread(self, ledger_con, tmp_path):
        config.RETRIEVAL_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        retrieval_cache._save_cache({"a2024": {"fingerprint": [], "length": 1, "term_freqs": {}}})
        assert set(retrieval_cache._load_cache()) == {"a2024"}
        retrieval_cache._save_cache({"b2024": {"fingerprint": [], "length": 1, "term_freqs": {}}})
        assert set(retrieval_cache._load_cache()) == {"b2024"}

    def test_a_rewrite_behind_this_modules_back_is_picked_up(self, isolated_config):
        config.RETRIEVAL_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        retrieval_cache._save_cache({"a2024": {"fingerprint": [], "length": 1, "term_freqs": {}}})
        assert set(retrieval_cache._load_cache()) == {"a2024"}
        config.RETRIEVAL_INDEX_PATH.write_text(
            json.dumps(
                {
                    "version": retrieval_cache._INDEX_SCHEMA_VERSION,
                    "items": {"c2024": {"fingerprint": [], "length": 1, "term_freqs": {}}},
                }
            ),
            encoding="utf-8",
        )
        retrieval_cache._forget_cache()
        assert set(retrieval_cache._load_cache()) == {"c2024"}

    def test_the_path_is_part_of_the_stamp(self, isolated_config, tmp_path, monkeypatch):
        config.RETRIEVAL_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        retrieval_cache._save_cache({"a2024": {"fingerprint": [], "length": 1, "term_freqs": {}}})
        first = retrieval_cache._CACHE.stamp()
        monkeypatch.setattr(config, "RETRIEVAL_INDEX_PATH", tmp_path / "elsewhere.json")
        assert retrieval_cache._CACHE.stamp() != first
        assert retrieval_cache._load_cache() == {}

    def test_an_absent_index_stamps_without_raising(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "RETRIEVAL_INDEX_PATH", tmp_path / "never-written.json")
        assert retrieval_cache._load_cache() == {}

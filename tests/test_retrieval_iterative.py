from chitragupta import ledger, retrieval, retrieval_iterative

from tests.conftest import add_citable, make_reference, parsed_file


class TestBoundYPrev:
    def test_short_text_is_returned_unchanged(self):
        bounded, truncated = retrieval_iterative._bound_y_prev("short prose")
        assert bounded == "short prose"
        assert truncated is False

    def test_long_text_is_cut_at_the_limit_on_a_word_boundary(self):
        text = "word " * 500  # 2499 chars once collapsed, over the 1500 default
        bounded, truncated = retrieval_iterative._bound_y_prev(text)
        assert truncated is True
        assert len(bounded) <= retrieval_iterative.Y_PREV_MAX_CHARS
        assert bounded.endswith("word")

    def test_collapses_whitespace_before_measuring(self):
        bounded, truncated = retrieval_iterative._bound_y_prev("a\n\nb   c")
        assert bounded == "a b c"
        assert truncated is False

    def test_a_single_word_over_the_limit_still_returns_something(self):
        text = "x" * 2000
        bounded, truncated = retrieval_iterative._bound_y_prev(text, limit=100)
        assert truncated is True
        assert bounded

    def test_blank_text_is_not_truncated(self):
        bounded, truncated = retrieval_iterative._bound_y_prev("   \n  ")
        assert bounded == ""
        assert truncated is False

    def test_text_exactly_at_the_limit_is_not_truncated(self):
        text = "x" * retrieval_iterative.Y_PREV_MAX_CHARS
        bounded, truncated = retrieval_iterative._bound_y_prev(text)
        assert bounded == text
        assert truncated is False


class TestSearchIterative:
    def test_blank_y_prev_skips_round_two_and_matches_plain_search(self, ledger_con):
        add_citable(ledger_con, "a2024", title="Digital Twin")
        plain = retrieval.search("digital twin")
        found, truncated = retrieval_iterative.search_iterative("digital twin", "   ")
        assert [r.citekey for r in found] == [r.citekey for r in plain]
        assert truncated is False

    def test_empty_query_with_y_prev_still_returns_nothing(self, ledger_con):
        add_citable(ledger_con, "a2024", title="Digital Twin")
        found, truncated = retrieval_iterative.search_iterative("", "digital twin prose")
        assert found == []
        assert truncated is False

    def test_round_two_surfaces_a_citekey_round_one_missed(self, ledger_con):
        add_citable(ledger_con, "a2024", title="Digital Twin Overview")
        add_citable(ledger_con, "b2024", title="Greenhouse Actuator Calibration")
        found, _ = retrieval_iterative.search_iterative(
            "digital twin", "the greenhouse actuator calibration drifted", k=5
        )
        assert {"a2024", "b2024"} <= {r.citekey for r in found}

    def test_a_citekey_in_both_rounds_is_not_duplicated(self, ledger_con):
        add_citable(ledger_con, "a2024", title="Digital Twin Digital Twin")
        found, _ = retrieval_iterative.search_iterative(
            "digital twin", "digital twin appears in the draft prose too"
        )
        citekeys = [r.citekey for r in found]
        assert citekeys.count("a2024") == 1

    def test_result_is_capped_at_k_even_after_merging_two_rounds(self, ledger_con):
        for i in range(8):
            add_citable(ledger_con, f"item{i}_2024", title="Digital Twin Paper")
        found, _ = retrieval_iterative.search_iterative(
            "digital twin", "digital twin architecture prose", k=3
        )
        assert len(found) == 3

    def test_truncated_flag_reflects_bound_y_prev(self, ledger_con):
        add_citable(ledger_con, "a2024", title="Digital Twin")
        long_prose = "digital twin " * 300
        _, truncated = retrieval_iterative.search_iterative("digital twin", long_prose)
        assert truncated is True

    def test_a_shared_citekey_keeps_its_higher_score(self, ledger_con, tmp_path):
        parsed = parsed_file("a2024")
        parsed.write_text("digital twin " * 3 + "greenhouse actuator " * 20)
        add_citable(ledger_con, "a2024", title="Twin Paper")
        ledger.mark_parsed(ledger_con, "a2024", parsed)

        round1 = retrieval.search("digital twin", k=1)
        round2 = retrieval.search("digital twin greenhouse actuator greenhouse actuator", k=1)
        assert round2[0].score > round1[0].score  # precondition: round 2 really is higher

        found, _ = retrieval_iterative.search_iterative(
            "digital twin", "greenhouse actuator greenhouse actuator", k=1
        )
        assert found[0].score == round2[0].score

    def test_a_shared_citekey_does_not_regress_when_round_two_scores_no_higher(
        self, ledger_con, tmp_path
    ):
        parsed = parsed_file("a2024")
        parsed.write_text("digital twin architecture patterns")
        add_citable(ledger_con, "a2024", title="Twin Paper")
        ledger.mark_parsed(ledger_con, "a2024", parsed)

        round1 = retrieval.search("digital twin", k=1)
        found, _ = retrieval_iterative.search_iterative(
            "digital twin", "greenhouse actuator calibration", k=1
        )
        assert found[0].citekey == "a2024"
        assert found[0].score == round1[0].score


class TestYPrevIsNeverCorrected:
    def test_round_two_corrects_the_query_and_not_the_prose(self, ledger_con, monkeypatch):
        from chitragupta import config, retrieval_scoring

        for citekey in ("a2024", "b2024"):
            parsed = parsed_file(citekey)
            parsed.write_text("a structural model that learns its offset")
            add_citable(ledger_con, citekey, title=citekey)
            ledger.mark_parsed(ledger_con, citekey, parsed)
        monkeypatch.setattr(config, "SPELLING_CORRECTION", True)
        ranked_on = []
        real = retrieval_scoring.bm25_scores
        monkeypatch.setattr(
            retrieval_scoring,
            "bm25_scores",
            lambda index, terms: ranked_on.append(set(terms)) or real(index, terms),
        )
        retrieval_iterative.search_iterative("strucutral", "the compensator earns its keep")
        round1, round2 = ranked_on
        assert "structural" in round1
        assert {"structural", "compensator", "earns"} <= round2
        assert "learns" not in round2

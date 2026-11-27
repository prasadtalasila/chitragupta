from chitragupta.passage_diff import annotate, one_line


class TestSharedWordingIsLeftBare:
    def test_identical_text_is_not_marked_at_all(self):
        draft, source = annotate("the same words", "the same words")
        assert (draft, source) == ("the same words", "the same words")

    def test_the_overlap_survives_unmarked_around_a_substitution(self):
        draft, source = annotate("the cat sat down", "the dog sat down")
        assert draft == "the **cat** sat down"
        assert source == "the **dog** sat down"


class TestNormalisationIsNotReportedAsADifference:
    def test_casing_alone_is_not_a_substitution(self):
        draft, source = annotate("configuration data", "Configuration Data")
        assert "**" not in draft
        assert "**" not in source

    def test_the_source_keeps_its_own_casing_and_punctuation(self):
        draft, source = annotate("machine s dt", "machine's DT")
        assert source == "machine's DT"

    def test_punctuation_between_matched_words_is_carried_through(self):
        _draft, source = annotate("a b c", "a, b -- c")
        assert source == "a, b -- c"


class TestEveryOpcode:
    def test_replace_marks_both_sides(self):
        draft, source = annotate("it reaches a twin", "it is sent to a twin")
        assert "**reaches**" in draft
        assert "**is sent to**" in source

    def test_a_word_only_the_draft_has_is_marked_on_the_draft(self):
        draft, source = annotate("the big red car", "the red car")
        assert draft == "the **big** red car"
        assert "**" not in source
        assert "*" not in source

    def test_a_word_only_the_source_has_is_italicised_on_the_source(self):
        draft, source = annotate("the red car", "the big red car")
        assert source == "the *big* red car"
        assert "**" not in draft


class TestRunsAreMarkedAsOnePhrase:
    def test_adjacent_changed_words_share_one_pair_of_delimiters(self):
        _draft, source = annotate("it reaches a twin", "it is sent to a twin")
        assert "**is sent to**" in source
        assert "**is** **sent** **to**" not in source

    def test_delimiters_sit_on_word_boundaries_not_around_punctuation(self):
        _draft, source = annotate("alpha gamma", "alpha beta.")
        assert "**beta**." in source


class TestLongPassages:
    def test_a_stopword_substitution_is_still_marked_past_200_words(self):
        filler = " ".join(f"word{i} the" for i in range(200))
        draft = f"{filler} the cat"
        source = f"{filler} the dog"

        marked_draft, marked_source = annotate(draft, source)

        assert "**cat**" in marked_draft
        assert "**dog**" in marked_source


class TestOneLine:
    def test_newlines_and_runs_of_space_collapse_to_one_space(self):
        assert one_line("a\nb  c\n\n  d\te") == "a b c d e"

    def test_text_already_on_one_line_is_unchanged(self):
        assert one_line("already flat") == "already flat"

    def test_leading_and_trailing_whitespace_goes(self):
        assert one_line("  padded  ") == "padded"

    def test_it_is_never_applied_to_the_stored_passage(self):
        original = "a\nb"
        assert one_line(original) == "a b"
        assert original == "a\nb"


class TestDegenerateInput:
    def test_an_empty_draft_side_marks_the_whole_source_dropped(self):
        draft, source = annotate("", "every word here is dropped")
        assert draft == ""
        assert source == "*every word here is dropped*"

    def test_an_empty_source_side_marks_the_whole_draft(self):
        draft, source = annotate("all of this is the draft's own", "")
        assert draft == "**all of this is the draft's own**"
        assert source == ""

    def test_two_empty_sides_produce_no_markup(self):
        assert annotate("", "") == ("", "")

    def test_text_with_no_words_at_all_is_returned_unchanged(self):
        assert annotate("---", "!!!") == ("---", "!!!")


class TestOnlyPortableMarkup:
    def test_no_strikeout_is_ever_emitted(self):
        draft, source = annotate("a c", "a b c")
        assert "~~" not in draft + source

    def test_the_two_marks_are_emphasis_and_strong_emphasis_only(self):
        from chitragupta import passage_diff

        assert {passage_diff._CHANGED, passage_diff._DROPPED} == {"**", "*"}

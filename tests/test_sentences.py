from chitragupta import sentences


class TestSplit:
    def test_splits_on_terminal_punctuation_before_a_capital(self):
        assert sentences.split("One thing. Then another! And a third?") == [
            "One thing.",
            "Then another!",
            "And a third?",
        ]

    def test_does_not_split_inside_the_abbreviations_these_drafts_contain(self):
        for text in (
            "See Fig. 2 for the layout.",
            "See Sect. 1.2 for detail.",
            "Written e.g. Smith or i.e. Jones.",
            "Compare cf. Brown here.",
            "Solve Eq. 4 first.",
            "Read Ref. 9 next.",
        ):
            assert len(sentences.split(text)) == 1, text

    def test_et_al_before_a_parenthesised_year_does_not_split(self):
        assert sentences.split(
            "Smith et al. (2020) found this. As Dr. Jones vs. Brown noted, so."
        ) == [
            "Smith et al. (2020) found this.",
            "As Dr. Jones vs. Brown noted, so.",
        ]

    def test_the_issue_reproduction_verbatim_no_longer_fragments(self):
        text = "Smith et al. (2020) found X. As Dr. Jones vs. Brown noted, Y."
        assert sentences.split(text) == [text]

    def test_does_not_split_after_the_citation_abbreviations(self):
        for text in (
            "Shown by Brown et al. [3] first.",
            "Taught by Prof. Green for years.",
            "Item No. (4) was lost.",
            "Quoted from pp. (12-14) of it.",
        ):
            assert len(sentences.split(text)) == 1, text

    def test_a_sentence_after_no_and_a_number_still_splits(self):
        assert sentences.split("No. 5 was first. Then came six.") == [
            "No. 5 was first.",
            "Then came six.",
        ]

    def test_al_inside_a_longer_word_still_ends_a_sentence(self):
        assert sentences.split("It was fatal. Then it stopped.") == [
            "It was fatal.",
            "Then it stopped.",
        ]

    def test_does_not_split_after_a_single_initial(self):
        assert sentences.split("Named for J. Smith and nobody else.") == [
            "Named for J. Smith and nobody else."
        ]

    def test_splits_before_a_bracket_or_parenthesis_too(self):
        assert sentences.split("A claim. [@key_2024] supports it.") == [
            "A claim.",
            "[@key_2024] supports it.",
        ]

    def test_a_text_with_no_terminator_is_one_sentence(self):
        assert sentences.split("no full stop here") == ["no full stop here"]


class TestSpans:
    def test_spans_slice_back_to_what_split_returns(self):
        text = "Hello there. This is Dr. Smith speaking. See Fig. 2 for detail. Done."
        assert [text[a:b] for a, b in sentences.spans(text)] == sentences.split(text)

    def test_offsets_index_the_original_not_a_stripped_copy(self):
        text = "\n\n  First one. Second one.\n"
        first, second = sentences.spans(text)
        assert text[first[0] : first[1]] == "First one."
        assert text[second[0] : second[1]] == "Second one."

    def test_a_whitespace_only_text_has_no_sentences(self):
        assert sentences.spans("   \n\n  ") == []

    def test_an_empty_text_has_no_sentences(self):
        assert sentences.spans("") == []

    def test_a_trailing_separator_does_not_leave_an_empty_span(self):
        spans = sentences.spans("A sentence. ")
        assert len(spans) == 1

"""chitragupta/sentences.py: the one sentence splitter, shared by the provenance
report and tier 3 of the overlap scan.

Stdlib-only and pure, so these are all direct calls -- no fixtures, no
config. The behaviour worth pinning is the pair invariant between
`split` and `spans`: two functions over one regex, and a caller that
slices `spans` back out of the text has to get what `split` returns."""

from chitragupta import sentences


class TestSplit:
    def test_splits_on_terminal_punctuation_before_a_capital(self):
        assert sentences.split("One thing. Then another! And a third?") == [
            "One thing.", "Then another!", "And a third?"
        ]

    def test_does_not_split_inside_the_abbreviations_these_drafts_contain(self):
        # The whole reason the regex carries lookbehinds: splitting at
        # "Fig." or "e.g." reintroduces the fragment problem one level
        # down, which is what `citation_provenance` wrote them for.
        for text in ("See Fig. 2 for the layout.", "See Sect. 1.2 for detail.",
                     "Written e.g. Smith or i.e. Jones.", "Compare cf. Brown here.",
                     "Solve Eq. 4 first.", "Read Ref. 9 next."):
            assert len(sentences.split(text)) == 1, text

    def test_does_not_split_after_a_single_initial(self):
        assert sentences.split("Named for J. Smith and nobody else.") == [
            "Named for J. Smith and nobody else."
        ]

    def test_splits_before_a_bracket_or_parenthesis_too(self):
        # Drafts open sentences with a citation marker, so the character
        # after the space is not always a capital letter.
        assert sentences.split("A claim. [@key_2024] supports it.") == [
            "A claim.", "[@key_2024] supports it."
        ]

    def test_a_text_with_no_terminator_is_one_sentence(self):
        assert sentences.split("no full stop here") == ["no full stop here"]


class TestSpans:
    def test_spans_slice_back_to_what_split_returns(self):
        text = "Hello there. This is Dr. Smith speaking. See Fig. 2 for detail. Done."
        assert [text[a:b] for a, b in sentences.spans(text)] == sentences.split(text)

    def test_offsets_index_the_original_not_a_stripped_copy(self):
        # The difference `split`'s own `.strip()` hides, and the reason
        # this function exists: tier 3 reports `char_start` into the file
        # as written, so an offset measured against a stripped copy would
        # be wrong by the leading whitespace for every sentence.
        text = "\n\n  First one. Second one.\n"
        first, second = sentences.spans(text)
        assert text[first[0]:first[1]] == "First one."
        assert text[second[0]:second[1]] == "Second one."

    def test_a_whitespace_only_text_has_no_sentences(self):
        assert sentences.spans("   \n\n  ") == []

    def test_an_empty_text_has_no_sentences(self):
        assert sentences.spans("") == []

    def test_a_trailing_separator_does_not_leave_an_empty_span(self):
        # `re.split` on a text ending in a separator yields a final empty
        # piece; a consumer that embedded one would be embedding "".
        spans = sentences.spans("A sentence. ")
        assert len(spans) == 1

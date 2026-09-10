"""`_scan_diff.annotate` -- the word-level markup that makes a
substitution visible without collating two paragraphs by eye.

Own module rather than a class in tests/test_verbatim_check.py: that file
is already the largest in the suite and this is a self-contained pure
function with no corpus, no ledger and no fixtures.
"""

from chitragupta.review.verbatim_check._scan_diff import annotate


class TestSharedWordingIsLeftBare:
    def test_identical_text_is_not_marked_at_all(self):
        draft, source = annotate("the same words", "the same words")
        assert (draft, source) == ("the same words", "the same words")

    def test_the_overlap_survives_unmarked_around_a_substitution(self):
        draft, source = annotate("the cat sat down", "the dog sat down")
        assert draft == "the **cat** sat down"
        assert source == "the **dog** sat down"


class TestNormalisationIsNotReportedAsADifference:
    """The draft side of a finding is normalised and the source side is
    raw. Diffing those as-is marks nearly every token as substituted --
    a highlight that looks convincing and means nothing -- so the
    comparison runs on normalised tokens while the markup lands on the
    real ones.
    """

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
    """`equal`/`replace`/`delete`/`insert`, and the translation each
    needs: `difflib` names what turns the draft into the source, which is
    the reverse of how the report reads.
    """

    def test_replace_marks_both_sides(self):
        draft, source = annotate("it reaches a twin", "it is sent to a twin")
        assert "**reaches**" in draft
        assert "**is sent to**" in source

    def test_a_word_only_the_draft_has_is_marked_on_the_draft(self):
        # difflib calls this `delete` (delete from the draft to get the
        # source); to a reader it is the draft adding a word.
        draft, source = annotate("the big red car", "the red car")
        assert draft == "the **big** red car"
        assert "**" not in source
        assert "~~" not in source

    def test_a_word_only_the_source_has_is_struck_on_the_source(self):
        # difflib calls this `insert`; to a reader the draft dropped it.
        draft, source = annotate("the red car", "the big red car")
        assert source == "the ~~big~~ red car"
        assert "**" not in draft


class TestRunsAreMarkedAsOnePhrase:
    def test_adjacent_changed_words_share_one_pair_of_delimiters(self):
        """`**is sent to**` is one substituted phrase; `**is** **sent**
        **to**` is three emphases a reader has to reassemble."""
        _draft, source = annotate("it reaches a twin", "it is sent to a twin")
        assert "**is sent to**" in source
        assert "**is** **sent** **to**" not in source

    def test_delimiters_sit_on_word_boundaries_not_around_punctuation(self):
        """`**word.**` would put the sentence's full stop inside the
        emphasis, which is both wrong and a different span from the one
        the diff found."""
        _draft, source = annotate("alpha gamma", "alpha beta.")
        assert "**beta**." in source


class TestLongPassages:
    def test_a_stopword_substitution_is_still_marked_past_200_words(self):
        """`SequenceMatcher`'s `autojunk` drops any token appearing in
        more than 1% of a sequence longer than 200 elements -- on prose
        that is every stopword, i.e. exactly the substitutions this
        markup exists to show, silently ignored on long findings and not
        on short ones. It is disabled for that reason.
        """
        filler = " ".join(f"word{i} the" for i in range(200))
        draft = f"{filler} the cat"
        source = f"{filler} the dog"

        marked_draft, marked_source = annotate(draft, source)

        assert "**cat**" in marked_draft
        assert "**dog**" in marked_source


class TestDegenerateInput:
    def test_an_empty_draft_side_strikes_the_whole_source(self):
        draft, source = annotate("", "every word here is dropped")
        assert draft == ""
        assert source == "~~every word here is dropped~~"

    def test_an_empty_source_side_marks_the_whole_draft(self):
        draft, source = annotate("all of this is the draft's own", "")
        assert draft == "**all of this is the draft's own**"
        assert source == ""

    def test_two_empty_sides_produce_no_markup(self):
        assert annotate("", "") == ("", "")

    def test_text_with_no_words_at_all_is_returned_unchanged(self):
        assert annotate("---", "!!!") == ("---", "!!!")

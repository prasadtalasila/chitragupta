"""chitragupta/porter_stemmer.py: the vendored Porter (1980) stemmer
chitragupta/overlap_skipgram.py's tier-2 skip-gram tokenizer folds inflected word
forms through before hashing."""

from chitragupta.porter_stemmer import stem


class TestStem:
    def test_plural_s_is_stripped(self):
        assert stem("cats") == "cat"

    def test_ies_becomes_i(self):
        assert stem("ponies") == "poni"

    def test_eed_only_strips_with_positive_measure(self):
        assert stem("agreed") == "agre"
        assert stem("feed") == "feed"

    def test_ing_restores_a_silent_e_after_at_bl_iz(self):
        assert stem("sizing") == "size"

    def test_ing_undoubles_a_final_consonant(self):
        assert stem("hopping") == "hop"

    def test_ing_alone_is_kept_when_the_stem_has_no_vowel(self):
        # "sing" -> stem "s" (after stripping "ing") has no vowel, so
        # step1b's `*v*` guard leaves the word untouched.
        assert stem("sing") == "sing"

    def test_derivational_suffix_reduces_to_a_root(self):
        assert stem("relational") == "relat"
        assert stem("conditional") == "condit"

    def test_step4_stops_at_the_longest_matching_suffix(self):
        # "argument" ends with both "-ment" and "-ent"; Porter's algorithm
        # selects the longest match ("-ment"), tests its measure condition
        # once, and stops there rather than falling through to "-ent" when
        # that test fails. Same for the "-ement" family below.
        assert stem("argument") == "argument"
        assert stem("agreement") == "agreement"
        assert stem("basement") == "basement"
        assert stem("casement") == "casement"

    def test_short_word_is_returned_unchanged(self):
        assert stem("as") == "as"
        assert stem("is") == "is"

    def test_deterministic_and_idempotent_on_an_already_short_stem(self):
        once = stem("controlling")
        assert stem(once) == once

    def test_unrelated_words_stem_differently(self):
        assert stem("digital") != stem("physical")

    def test_synonym_swap_does_not_converge(self):
        # Stemming folds inflection, not vocabulary -- "continuous" and
        # "constant" share no root, which is exactly why
        # chitragupta/overlap_skipgram.py's robustness against a synonym swap
        # comes from the even/odd family split, not from stemming
        # somehow unifying the two words.
        assert stem("continuous") != stem("constant")

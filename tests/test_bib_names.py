"""chitragupta/bib_names.py: the one implementation of the BibTeX author-name
grammar, and the proof that both its callers actually route through it.

The grammar's own edge cases are covered here rather than twice more;
`tests/test_bib_reader.py` and `tests/test_references.py` keep the cases
they already had, which is what makes the equivalence class at the bottom
of this file worth anything -- it is asserting agreement between two
independently-tested modules, not between two aliases of one call.
"""

import pytest

from chitragupta import bib_names, bib_reader, references_ieee


class TestSplitName:
    def test_comma_form_is_family_then_given(self):
        assert bib_names.split_name("Doe, Jane") == ("Jane", "Doe")

    def test_space_form_is_given_then_family(self):
        assert bib_names.split_name("Jane Doe") == ("Jane", "Doe")

    def test_a_single_token_is_all_family(self):
        """ "Cher" is a family name with no given name, not the reverse:
        the family name is what a bibliography sorts and prints, so a
        one-word name that landed in `first` would render as an initial
        and lose the name entirely."""
        assert bib_names.split_name("Cher") == ("", "Cher")

    def test_only_the_last_space_splits(self):
        assert bib_names.split_name("Jane Mary Doe") == ("Jane Mary", "Doe")

    def test_only_the_first_comma_splits(self):
        # BibTeX's three-part `von Last, Jr, First` form is not handled --
        # deliberately, and no more or less than before #234 moved these
        # lines. Pinned so that a later change to it is a visible one.
        assert bib_names.split_name("Doe, Jr., Jane") == ("Jr., Jane", "Doe")

    def test_whitespace_around_the_comma_is_dropped(self):
        assert bib_names.split_name("Doe ,   Jane") == ("Jane", "Doe")

    def test_an_empty_name_is_an_empty_family_name(self):
        # Reachable from `_format_name` only, which strips before the
        # brace check; `_parse_authors` drops empty segments earlier.
        assert bib_names.split_name("") == ("", "")


class TestBothCallersUseTheSharedGrammar:
    """#234's actual subject. The five lines were identical in
    `bib_reader._parse_authors` and `references_ieee._format_name`, so nothing
    was wrong with the *output* -- what was wrong was that there were two
    of them, and extending one silently left the other on the old
    reading. The ledger would then record one spelling of an author and
    the rendered bibliography print another, for the same entry.

    So these tests are about the wiring, not the answers.
    """

    _NAMES = ["Doe, Jane", "Jane Doe", "Cher", "Jane Mary Doe", "van Beethoven"]

    @pytest.mark.parametrize("name", _NAMES)
    def test_bib_reader_returns_exactly_what_the_helper_split(self, name):
        assert bib_reader._parse_authors(name) == [bib_names.split_name(name)]

    @pytest.mark.parametrize("name", _NAMES)
    def test_references_initializes_exactly_what_the_helper_split(self, name):
        first, last = bib_names.split_name(name)
        assert (
            references_ieee._format_name(name)
            == f"{references_ieee._initials(first)} {last}".strip()
        )

    @pytest.mark.parametrize("name", _NAMES)
    def test_both_modules_agree_on_the_family_name(self, name):
        """The one that would actually be visible to a reader: the family
        name is what the ledger stores and what the bibliography prints."""
        assert bib_reader._parse_authors(name)[0][1] in references_ieee._format_name(name)

    def test_extending_the_grammar_reaches_both_callers(self, monkeypatch):
        """The regression guard, and the only test here that would fail if
        either module went back to its own copy of the five lines.

        The assertions above compare each module against the helper, which
        a re-inlined copy would still satisfy for every name the two
        readings agree on -- i.e. all of them, today. Replacing the helper
        outright is what distinguishes "calls it" from "happens to match
        it", and it stands in for the real future change: teaching the
        grammar a `von` particle or a `Jr.` suffix in one place.
        """
        monkeypatch.setattr(bib_names, "split_name", lambda name: ("GIVEN", "FAMILY"))
        assert bib_reader._parse_authors("Doe, Jane") == [("GIVEN", "FAMILY")]
        assert references_ieee._format_name("Doe, Jane") == "G. FAMILY"

    def test_a_corporate_author_does_not_reach_the_shared_grammar(self, monkeypatch):
        """The brace check stayed in `references_ieee`, and this pins that
        it still short-circuits: "{IEEE Standards Association}" is one
        unit, and splitting it would print "S. Association"."""
        monkeypatch.setattr(bib_names, "split_name", lambda name: ("GIVEN", "FAMILY"))
        assert references_ieee._format_name("{IEEE Standards Association}") == (
            "IEEE Standards Association"
        )

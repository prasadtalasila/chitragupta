import pytest

from chitragupta import bib_names, bib_reader, references_ieee


class TestSplitName:
    def test_comma_form_is_family_then_given(self):
        assert bib_names.split_name("Doe, Jane") == ("Jane", "Doe")

    def test_space_form_is_given_then_family(self):
        assert bib_names.split_name("Jane Doe") == ("Jane", "Doe")

    def test_a_single_token_is_all_family(self):
        assert bib_names.split_name("Cher") == ("", "Cher")

    def test_only_the_last_space_splits(self):
        assert bib_names.split_name("Jane Mary Doe") == ("Jane Mary", "Doe")

    def test_only_the_first_comma_splits(self):
        assert bib_names.split_name("Doe, Jr., Jane") == ("Jr., Jane", "Doe")

    def test_whitespace_around_the_comma_is_dropped(self):
        assert bib_names.split_name("Doe ,   Jane") == ("Jane", "Doe")

    def test_an_empty_name_is_an_empty_family_name(self):
        assert bib_names.split_name("") == ("", "")


class TestBothCallersUseTheSharedGrammar:
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
        assert bib_reader._parse_authors(name)[0][1] in references_ieee._format_name(name)

    def test_extending_the_grammar_reaches_both_callers(self, monkeypatch):
        monkeypatch.setattr(bib_names, "split_name", lambda name: ("GIVEN", "FAMILY"))
        assert bib_reader._parse_authors("Doe, Jane") == [("GIVEN", "FAMILY")]
        assert references_ieee._format_name("Doe, Jane") == "G. FAMILY"

    def test_a_corporate_author_does_not_reach_the_shared_grammar(self, monkeypatch):
        monkeypatch.setattr(bib_names, "split_name", lambda name: ("GIVEN", "FAMILY"))
        assert references_ieee._format_name("{IEEE Standards Association}") == (
            "IEEE Standards Association"
        )

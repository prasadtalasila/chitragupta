import pytest

from chitragupta import acronyms, config, retrieval, retrieval_spelling
from chitragupta.retrieval_added import ACRONYM, SPELLING, Added, announce, describe

VOCABULARY = {"DT": "digital twin", "DM": "digital model"}


@pytest.fixture
def vocabulary(monkeypatch):
    monkeypatch.setattr(acronyms, "load_vocabulary", lambda: dict(VOCABULARY))
    monkeypatch.setattr(config, "ACRONYM_EXPANSION", True)


@pytest.fixture
def spelling(monkeypatch):
    monkeypatch.setattr(config, "SPELLING_CORRECTION", True)
    monkeypatch.setattr(
        retrieval_spelling, "vocabulary", lambda _: {"structural": 3, "digital": 9, "twin": 9}
    )


def added(query: str) -> list[Added]:
    return retrieval.query_terms(query)[1]


class TestAddedTerms:
    def test_acronyms_come_first_then_corrections(self, vocabulary, spelling):
        assert added("DT strucutral") == [
            Added("dt", "digital", ACRONYM),
            Added("dt", "twin", ACRONYM),
            Added("strucutral", "structural", SPELLING),
        ]

    def test_a_correction_joins_the_ranked_terms(self, spelling):
        assert retrieval.query_terms("strucutral health")[0] == [
            "strucutral",
            "health",
            "structural",
        ]

    def test_a_word_both_would_add_is_added_once_by_the_acronym(self, vocabulary, spelling):
        assert added("DT digitl") == [
            Added("dt", "digital", ACRONYM),
            Added("dt", "twin", ACRONYM),
        ]

    def test_an_acronym_expansion_is_never_corrected(self, monkeypatch, spelling):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {"DX": "dgital twin"})
        monkeypatch.setattr(config, "ACRONYM_EXPANSION", True)
        assert [entry.source for entry in added("DX")] == [ACRONYM, ACRONYM]

    def test_an_interrogative_is_never_added(self, monkeypatch):
        monkeypatch.setattr(config, "SPELLING_CORRECTION", True)
        monkeypatch.setattr(retrieval_spelling, "vocabulary", lambda _: {"which": 40})
        assert added("whichh model") == []

    def test_no_terms_reads_no_vocabulary(self, monkeypatch):
        monkeypatch.setattr(config, "SPELLING_CORRECTION", True)
        monkeypatch.setattr(retrieval_spelling, "vocabulary", lambda _: pytest.fail("read"))
        assert retrieval.query_terms("what is the") == ([], [])


class TestContext:
    def test_context_words_are_ranked_but_never_corrected(self, spelling):
        terms, entries = retrieval.query_terms("strucutral", context="citep digitl")
        assert terms == ["strucutral", "citep", "digitl", "structural"]
        assert entries == [Added("strucutral", "structural", SPELLING)]

    def test_context_acronyms_still_expand(self, vocabulary):
        assert added_with("fidelity", "DT") == [
            Added("dt", "digital", ACRONYM),
            Added("dt", "twin", ACRONYM),
        ]

    def test_a_correction_the_context_already_holds_is_not_added(self, spelling):
        assert added_with("strucutral", "structural") == []

    def test_with_correction_off_it_ranks_as_the_joined_string_did(self, vocabulary):
        joined = retrieval.query_terms("DT fidelity the compensator recomputes")
        split = retrieval.query_terms("DT fidelity", context="the compensator recomputes")
        assert split == joined


def added_with(query: str, context: str) -> list[Added]:
    return retrieval.query_terms(query, context=context)[1]


class TestDescribe:
    def test_nothing_added_describes_as_empty(self):
        assert describe([]) == ""

    def test_the_terms_are_grouped_under_the_acronym_that_added_them(self, vocabulary):
        assert describe(added("DT fidelity")) == "dt -> digital twin"

    def test_two_acronyms_are_separated(self, vocabulary):
        assert describe(added("DT and DM")) == "dt -> digital twin; dm -> model"

    def test_a_correction_reads_differently_from_an_acronym(self, vocabulary, spelling):
        assert describe(added("DT strucutral")) == "dt -> digital twin; strucutral ~> structural"


class TestAnnounce:
    def test_nothing_is_printed_when_nothing_is_added(self, capsys):
        assert announce([]) == ""
        assert capsys.readouterr().err == ""

    def test_the_note_names_the_acronym_and_its_terms(self, vocabulary, capsys):
        assert announce(added("DT fidelity")) == "dt -> digital twin"
        assert "acronym expansion added: dt -> digital twin" in capsys.readouterr().err

    def test_a_correction_gets_its_own_note(self, spelling, capsys):
        assert announce(added("strucutral")) == "strucutral ~> structural"
        err = capsys.readouterr().err
        assert "  [note] spelling: searched 'structural' for 'strucutral'" in err
        assert "acronym" not in err

    def test_the_notes_go_to_stderr(self, vocabulary, spelling, capsys):
        announce(added("DT strucutral"))
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err.count("[note]") == 2

"""chitragupta/retrieval_expansion.py: query-side acronym expansion (#789).

Two properties carry this file. **Off means off**: nothing is added and
no vocabulary is even read, so the ranking is the one the ranker produced
before this module existed -- pinned here at the unit level and, in
tests/test_retrieval.py, through a real `search()`. And **a typed term is
never added twice**: a word the caller wrote contributes once however
many acronyms also expand into it, so a query cannot be re-weighted by
the shape of someone's acronym file.

The vocabulary is patched rather than read from `assets/style/acronyms.toml`
in every test but one. The shipped file is five general-computing entries
and none of them expand into anything this project's corpus is about, so
testing against it would test a fixture rather than the mechanism -- and
the one test that does read it is the one asserting that the shipped
default cannot reach any vocabulary at all.
"""

import pytest

from chitragupta import acronyms, config, retrieval, retrieval_expansion

VOCABULARY = {"DT": "digital twin", "DM": "digital model", "UQ": "uncertainty quantification"}


@pytest.fixture
def vocabulary(monkeypatch):
    """The acronym table `expand` reads, and a weight that turns it on."""
    monkeypatch.setattr(acronyms, "load_vocabulary", lambda: dict(VOCABULARY))
    monkeypatch.setattr(config, "ACRONYM_EXPANSION", True)
    return VOCABULARY


def expand(query: str) -> list[tuple[str, str]]:
    """`expand` driven exactly as `search` drives it: the shipped query
    tokenizer in front, the shipped document tokenizer passed in."""
    return retrieval_expansion.expand(retrieval._query_terms(query), retrieval._tokenize)


class TestOffIsStructural:
    def test_the_shipped_default_is_on(self):
        """#789 ships this on: the vocabulary it expands from is the
        user's own file merged over a five-entry vendored floor, so a
        host that has written none gets no measurable change, and the one
        that has is the case the feature exists for."""
        assert config.ACRONYM_EXPANSION is True

    def test_nothing_is_added_when_it_is_switched_off(self, monkeypatch):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: dict(VOCABULARY))
        monkeypatch.setattr(config, "ACRONYM_EXPANSION", False)
        assert expand("DT fidelity") == []

    def test_the_vocabulary_is_never_read_when_it_is_off(self, monkeypatch):
        """Not an optimisation -- it is what makes "off" mean *off*. A
        malformed `[style].acronyms` file raises `AcronymsError`, and a
        caller who has switched expansion off must not start failing
        searches because of a file they told retrieval to ignore."""

        def explode():
            raise AssertionError("the vocabulary was read with expansion off")

        monkeypatch.setattr(acronyms, "load_vocabulary", explode)
        monkeypatch.setattr(config, "ACRONYM_EXPANSION", False)
        assert expand("DT fidelity") == []

    def test_the_shipped_vocabulary_expands_a_general_computing_acronym(self):
        """The one test that reads `assets/style/acronyms.toml` rather
        than a patched table. With the switch on by default, the shipped
        floor is what a project with no acronyms file of its own gets --
        five general-computing entries, and this is what they do."""
        assert expand("PDF parsing") == [
            ("pdf", "portable"),
            ("pdf", "document"),
            ("pdf", "format"),
        ]


class TestWhatIsAdded:
    def test_an_acronym_contributes_its_expansions_terms(self, vocabulary):
        assert expand("DT fidelity") == [("dt", "digital"), ("dt", "twin")]

    def test_a_term_that_is_no_acronym_adds_nothing(self, vocabulary):
        assert expand("fidelity of the model") == []

    def test_a_term_the_caller_typed_is_not_added_again(self, vocabulary):
        """The whole point of the guard: "digital twin DT" must not have
        `twin` demoted to the expansion weight because the acronym also
        produced it."""
        assert expand("digital twin DT") == []

    def test_two_acronyms_sharing_a_word_contribute_it_once(self, vocabulary):
        assert expand("DT versus DM") == [
            ("dt", "digital"),
            ("dt", "twin"),
            ("dm", "model"),
        ]

    def test_an_expansion_is_tokenized_the_way_the_index_was(self, monkeypatch):
        """Stopwords and the length floor apply to an expansion exactly
        as they applied to the document it has to match -- otherwise the
        added term is a string no `term_freqs` anywhere can contain."""
        monkeypatch.setattr(
            acronyms, "load_vocabulary", lambda: {"FMI": "the Functional Mock-up Interface"}
        )
        monkeypatch.setattr(config, "ACRONYM_EXPANSION", True)
        assert expand("FMI support") == [
            ("fmi", "functional"),
            ("fmi", "mock"),
            ("fmi", "up"),
            ("fmi", "interface"),
        ]

    def test_an_acronym_is_matched_case_insensitively(self, vocabulary):
        """The vocabulary writes `DT`; the query is lowercased before it
        gets here, so the fold has to happen on the vocabulary's side."""
        assert expand("dt fidelity") == expand("DT fidelity") != []

    def test_a_key_that_is_not_one_token_matches_nothing(self, monkeypatch):
        """A vocabulary is hand-written, so "I/O" and "ML ops" are both
        things an author may type. Neither can ever be a query term, so
        neither can expand -- silently, like every other unusable entry
        `acronyms.py` already drops."""
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {"I/O": "input output"})
        monkeypatch.setattr(config, "ACRONYM_EXPANSION", True)
        assert expand("I/O bound") == []

    def test_an_expansion_is_not_itself_expanded(self, monkeypatch):
        """`expand` reads the typed terms only. A vocabulary whose
        expansion contains another acronym would otherwise chain, and the
        length of a query would depend on how the file happened to be
        written."""
        monkeypatch.setattr(
            acronyms, "load_vocabulary", lambda: {"DTP": "DT platform", "DT": "digital twin"}
        )
        monkeypatch.setattr(config, "ACRONYM_EXPANSION", True)
        assert expand("DTP") == [("dtp", "dt"), ("dtp", "platform")]


class TestDescribe:
    def test_nothing_added_describes_as_empty(self):
        assert retrieval_expansion.describe([]) == ""

    def test_the_terms_are_grouped_under_the_acronym_that_added_them(self, vocabulary):
        assert retrieval_expansion.describe(expand("DT fidelity")) == "dt -> digital twin"

    def test_two_acronyms_are_separated(self, vocabulary):
        assert (
            retrieval_expansion.describe(expand("DT and DM")) == "dt -> digital twin; dm -> model"
        )


class TestAnnounce:
    def test_nothing_is_printed_when_nothing_is_added(self, capsys):
        assert retrieval_expansion.announce(["fidelity"], retrieval._tokenize) == ""
        assert capsys.readouterr().err == ""

    def test_the_note_names_the_acronym_and_its_terms(self, vocabulary, capsys):
        described = retrieval_expansion.announce(
            retrieval._query_terms("DT fidelity"), retrieval._tokenize
        )
        assert described == "dt -> digital twin"
        assert "acronym expansion added: dt -> digital twin" in capsys.readouterr().err

    def test_the_note_goes_to_stderr(self, vocabulary, capsys):
        """A genre skill parses this command's stdout as a contract; a
        note about the query is not a result."""
        retrieval_expansion.announce(retrieval._query_terms("DT"), retrieval._tokenize)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err

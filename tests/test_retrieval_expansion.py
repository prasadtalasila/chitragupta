import pytest

from chitragupta import acronyms, config, ledger, retrieval, retrieval_cli, retrieval_expansion

from tests.conftest import make_reference, parsed_file

VOCABULARY = {"DT": "digital twin", "DM": "digital model", "UQ": "uncertainty quantification"}


@pytest.fixture
def vocabulary(monkeypatch):
    monkeypatch.setattr(acronyms, "load_vocabulary", lambda: dict(VOCABULARY))
    monkeypatch.setattr(config, "ACRONYM_EXPANSION", True)
    return VOCABULARY


def expand(query: str) -> list[tuple[str, str]]:
    return retrieval_expansion.expand(retrieval._query_terms(query), retrieval._tokenize)


class TestOffIsStructural:
    def test_the_shipped_default_is_on(self):
        assert config.ACRONYM_EXPANSION is True

    def test_nothing_is_added_when_it_is_switched_off(self, monkeypatch):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: dict(VOCABULARY))
        monkeypatch.setattr(config, "ACRONYM_EXPANSION", False)
        assert expand("DT fidelity") == []

    def test_the_vocabulary_is_never_read_when_it_is_off(self, monkeypatch):
        def explode():
            raise AssertionError("the vocabulary was read with expansion off")

        monkeypatch.setattr(acronyms, "load_vocabulary", explode)
        monkeypatch.setattr(config, "ACRONYM_EXPANSION", False)
        assert expand("DT fidelity") == []

    def test_the_shipped_vocabulary_expands_a_general_computing_acronym(self):
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
        assert expand("digital twin DT") == []

    def test_two_acronyms_sharing_a_word_contribute_it_once(self, vocabulary):
        assert expand("DT versus DM") == [
            ("dt", "digital"),
            ("dt", "twin"),
            ("dm", "model"),
        ]

    def test_an_expansion_is_tokenized_the_way_the_index_was(self, monkeypatch):
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
        assert expand("dt fidelity") == expand("DT fidelity") != []

    def test_a_key_that_is_not_one_token_matches_nothing(self, monkeypatch):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {"I/O": "input output"})
        monkeypatch.setattr(config, "ACRONYM_EXPANSION", True)
        assert expand("I/O bound") == []

    def test_an_expansion_is_not_itself_expanded(self, monkeypatch):
        monkeypatch.setattr(
            acronyms, "load_vocabulary", lambda: {"DTP": "DT platform", "DT": "digital twin"}
        )
        monkeypatch.setattr(config, "ACRONYM_EXPANSION", True)
        assert expand("DTP") == [("dtp", "dt"), ("dtp", "platform")]


class TestAnUnreadableVocabularyIsSkipped:
    QUERY = "DT fidelity"

    @pytest.fixture
    def corpus(self, ledger_con, monkeypatch):
        monkeypatch.setattr(config, "ACRONYM_EXPANSION", True)
        monkeypatch.setattr(acronyms, "_NOTED", set())
        parsed = parsed_file("a2024")
        parsed.write_text("opening matter " * 60 + "the fidelity of the greenhouse twin")
        ledger.upsert_reference(ledger_con, make_reference(citekey="a2024", title="Greenhouse"))
        ledger.mark_parsed(ledger_con, "a2024", parsed)
        return ledger_con

    @pytest.fixture
    def malformed(self, corpus, monkeypatch, tmp_path):
        broken = tmp_path / "acronyms.toml"
        broken.write_text('DT = "digital twin\n', encoding="utf-8")
        monkeypatch.setattr(config, "ACRONYMS_PATH", broken)
        return broken

    @staticmethod
    def _status_all() -> int:
        from chitragupta import dossier

        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("# s\n")
        dossier.init(draft, "survey")
        for query in ("DT fidelity", "DT twin"):
            dossier.log_retrieval(draft, "search", query, 5, 5, 100)
        return dossier.main(["status", "--all"])

    @pytest.mark.parametrize(
        "run",
        [
            lambda: retrieval_cli.main(["search", "DT fidelity"]),
            lambda: retrieval_cli.main(["search", "DT fidelity", "--unit", "passage"]),
            lambda: retrieval_cli.main(["evidence", "DT fidelity", "--citekey", "a2024"]),
            _status_all,
        ],
        ids=["search", "passage-search", "evidence", "dossier-status-all"],
    )
    def test_every_consumer_exits_zero_with_one_note(self, malformed, capsys, run):
        assert run() == 0
        err = capsys.readouterr().err
        assert err.count("acronym file skipped") == 1
        assert str(malformed) in err

    def test_terms_are_those_of_a_project_with_no_user_file(self, corpus, malformed, monkeypatch):
        skipped = retrieval.query_terms(self.QUERY)
        monkeypatch.setattr(config, "ACRONYMS_PATH", malformed.with_name("absent.toml"))
        assert skipped == retrieval.query_terms(self.QUERY)

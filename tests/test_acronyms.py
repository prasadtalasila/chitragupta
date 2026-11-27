import pytest

from chitragupta import acronyms, config


class TestLoadDegradesCleanly:
    def test_an_unparseable_user_file_is_skipped_as_if_absent(self, monkeypatch, tmp_path, capsys):
        vendored = tmp_path / "vendored.toml"
        vendored.write_text('PDF = "Portable Document Format"\n', encoding="utf-8")
        bad = tmp_path / "bad.toml"
        bad.write_text('DT = "digital twin\n', encoding="utf-8")
        monkeypatch.setattr(config, "ACRONYMS_DEFAULT_PATH", vendored)
        monkeypatch.setattr(config, "ACRONYMS_PATH", bad)
        monkeypatch.setattr(acronyms, "_NOTED", set())

        assert acronyms.load_vocabulary() == {"PDF": "Portable Document Format"}
        assert acronyms.load_vocabulary() == {"PDF": "Portable Document Format"}
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err.count("acronym file skipped") == 1
        assert str(bad) in captured.err

    def test_an_unparseable_vendored_file_is_skipped_too(self, monkeypatch, tmp_path):
        bad = tmp_path / "bad.toml"
        bad.write_text("this is not = = valid toml [[[", encoding="utf-8")
        monkeypatch.setattr(config, "ACRONYMS_DEFAULT_PATH", bad)
        monkeypatch.setattr(config, "ACRONYMS_PATH", bad)
        monkeypatch.setattr(acronyms, "_NOTED", set())

        assert acronyms.load_vocabulary() == {}

    def test_a_non_string_value_is_dropped_not_raised(self, monkeypatch, tmp_path):
        vendored = tmp_path / "vendored.toml"
        vendored.write_text(
            'PDF = "Portable Document Format"\nCOUNT = 42\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(config, "ACRONYMS_DEFAULT_PATH", vendored)
        monkeypatch.setattr(config, "ACRONYMS_PATH", vendored)

        assert acronyms.load_vocabulary() == {"PDF": "Portable Document Format"}

    def test_a_non_string_value_does_not_crash_stale_expansions(self, monkeypatch, tmp_path):
        vendored = tmp_path / "vendored.toml"
        vendored.write_text("COUNT = 42\n", encoding="utf-8")
        monkeypatch.setattr(config, "ACRONYMS_DEFAULT_PATH", vendored)
        monkeypatch.setattr(config, "ACRONYMS_PATH", vendored)

        assert acronyms.stale_expansions({"COUNT (COUNT)": "Count"}) == {}


def test_defaults_to_the_vendored_file_when_no_override_is_set(monkeypatch, tmp_path):
    vendored = tmp_path / "vendored.toml"
    vendored.write_text('PDF = "Portable Document Format"\n', encoding="utf-8")
    monkeypatch.setattr(config, "ACRONYMS_DEFAULT_PATH", vendored)
    monkeypatch.setattr(config, "ACRONYMS_PATH", vendored)

    assert acronyms.load_vocabulary() == {"PDF": "Portable Document Format"}


def test_a_user_file_is_merged_over_the_vendored_one(monkeypatch, tmp_path):
    vendored = tmp_path / "vendored.toml"
    vendored.write_text(
        'PDF = "Portable Document Format"\nAPI = "Application Programming Interface"\n',
        encoding="utf-8",
    )
    user = tmp_path / "user.toml"
    user.write_text('DTaaS = "Digital Twin as a Service"\n', encoding="utf-8")
    monkeypatch.setattr(config, "ACRONYMS_DEFAULT_PATH", vendored)
    monkeypatch.setattr(config, "ACRONYMS_PATH", user)

    assert acronyms.load_vocabulary() == {
        "PDF": "Portable Document Format",
        "API": "Application Programming Interface",
        "DTaaS": "Digital Twin as a Service",
    }


def test_a_user_entry_overrides_a_vendored_entry_of_the_same_key(monkeypatch, tmp_path):
    vendored = tmp_path / "vendored.toml"
    vendored.write_text('API = "Application Programming Interface"\n', encoding="utf-8")
    user = tmp_path / "user.toml"
    user.write_text('API = "Application Programmer Interface"\n', encoding="utf-8")
    monkeypatch.setattr(config, "ACRONYMS_DEFAULT_PATH", vendored)
    monkeypatch.setattr(config, "ACRONYMS_PATH", user)

    assert acronyms.load_vocabulary() == {"API": "Application Programmer Interface"}


def test_a_user_file_that_does_not_exist_yet_is_treated_as_empty(monkeypatch, tmp_path):
    vendored = tmp_path / "vendored.toml"
    vendored.write_text('PDF = "Portable Document Format"\n', encoding="utf-8")
    monkeypatch.setattr(config, "ACRONYMS_DEFAULT_PATH", vendored)
    monkeypatch.setattr(config, "ACRONYMS_PATH", tmp_path / "not-there-yet.toml")

    assert acronyms.load_vocabulary() == {"PDF": "Portable Document Format"}


class TestRealVendoredFile:
    def test_has_the_issues_five_named_examples(self):
        vocab = acronyms.load_vocabulary()
        for term in ("PDF", "CPU", "URL", "API", "HTML"):
            assert term in vocab


class TestSuggest:
    def test_suggests_an_acronym_shaped_term_not_in_the_vocabulary(self, monkeypatch):
        monkeypatch.setattr(
            acronyms,
            "load_vocabulary",
            lambda: {"PDF": "Portable Document Format"},
        )
        glossary = {"DTaaS": "Digital Twin as a Service."}
        assert acronyms.suggest(glossary) == glossary

    def test_does_not_suggest_a_term_already_in_the_vocabulary(self, monkeypatch):
        monkeypatch.setattr(
            acronyms,
            "load_vocabulary",
            lambda: {"DTaaS": "Digital Twin as a Service"},
        )
        glossary = {"DTaaS": "Digital Twin as a Service."}
        assert acronyms.suggest(glossary) == {}

    def test_does_not_suggest_a_non_acronym_shaped_term(self, monkeypatch):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {})
        glossary = {"Twin state": "the digital object's current estimate."}
        assert acronyms.suggest(glossary) == {}

    def test_suggests_a_parenthetical_acronym_by_the_name_before_the_paren(self, monkeypatch):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {})
        glossary = {
            "Digital twin (DT)": (
                'was, in Chapter 1: "software that keeps a model of one '
                "specific physical system in step with that system's "
                "actual state, and uses it to answer questions that "
                'measurement alone cannot answer."'
            )
        }
        assert acronyms.suggest(glossary) == {"DT": "Digital twin"}

    def test_does_not_suggest_a_parenthetical_acronym_already_in_the_vocabulary(self, monkeypatch):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {"DT": "Digital twin"})
        glossary = {"Digital twin (DT)": "was, in Chapter 1: a model kept in step."}
        assert acronyms.suggest(glossary) == {}


class TestStaleExpansions:
    def test_no_findings_when_a_parenthetical_expansion_still_agrees(self, monkeypatch):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {"DT": "Digital twin"})
        glossary = {"Digital twin (DT)": "was, in Chapter 1: a model kept in step."}
        assert acronyms.stale_expansions(glossary) == {}

    def test_finds_a_parenthetical_expansion_that_has_drifted(self, monkeypatch):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {"DT": "Digital Twin System"})
        glossary = {"Digital twin (DT)": "was, in Chapter 1: a model kept in step."}
        assert acronyms.stale_expansions(glossary) == {
            "DT": ("Digital twin", "Digital Twin System")
        }

    def test_comparison_is_case_insensitive_and_ignores_trailing_punctuation(self, monkeypatch):
        monkeypatch.setattr(
            acronyms,
            "load_vocabulary",
            lambda: {"DTaaS": "Digital Twin as a Service"},
        )
        glossary = {"DTaaS": "digital twin as a service."}
        assert acronyms.stale_expansions(glossary) == {}

    def test_ignores_a_term_not_in_the_vocabulary(self, monkeypatch):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {})
        glossary = {"Digital twin (DT)": "was, in Chapter 1: a model kept in step."}
        assert acronyms.stale_expansions(glossary) == {}

    def test_ignores_a_non_acronym_shaped_term(self, monkeypatch):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {"DT": "Digital twin"})
        glossary = {"Twin state": "the digital object's current estimate."}
        assert acronyms.stale_expansions(glossary) == {}


class TestBodyCandidates:
    def test_extracts_a_simple_inline_definition(self):
        text = "The **Digital Twin Prototype (DTP)**, describing the artefact."
        assert acronyms.body_candidates(text) == {
            "Digital Twin Prototype (DTP)": "Digital Twin Prototype"
        }

    def test_excludes_everything_from_a_references_heading_onward(self):
        text = (
            "The **Digital Twin Prototype (DTP)** is introduced here.\n\n"
            "## References\n\n"
            '[1] Author, "Title," in *Some Conference (ICSA)*, 2023.\n'
        )
        assert acronyms.body_candidates(text) == {
            "Digital Twin Prototype (DTP)": "Digital Twin Prototype"
        }

    def test_a_numbered_references_heading_is_also_excluded(self):
        text = (
            "The **Digital Twin Prototype (DTP)** is introduced here.\n\n"
            "## 6.15 References\n\n"
            '[1] Author, "Title," in *Some Conference (ICSA)*, 2023.\n'
        )
        found = acronyms.body_candidates(text)
        assert "ICSA" not in "".join(found)
        assert found == {"Digital Twin Prototype (DTP)": "Digital Twin Prototype"}

    def test_a_hyphenated_word_stays_in_the_expansion(self):
        text = "The **Functional\nMock-up Interface (FMI)** is the standard."
        assert acronyms.body_candidates(text) == {
            "Functional Mock-up Interface (FMI)": "Functional Mock-up Interface"
        }

    def test_reflows_a_hard_line_wrap_inside_one_phrase(self):
        text = "the **Digital Twin\nAggregate (DTA)**, the aggregation of many."
        assert acronyms.body_candidates(text) == {
            "Digital Twin Aggregate (DTA)": "Digital Twin Aggregate"
        }

    def test_a_real_paragraph_break_is_not_reflowed_into_the_match(self):
        text = (
            "Some unrelated sentence ends here.\n\nHere is the Model Registry (MR), new paragraph."
        )
        assert acronyms.body_candidates(text) == {"Model Registry (MR)": "Model Registry"}

    def test_first_occurrence_per_acronym_wins(self):
        text = (
            "It defines the Digital Twin (DT) here. "
            "Later, the Digital Twin (DT) is mentioned again."
        )
        assert acronyms.body_candidates(text) == {"Digital Twin (DT)": "Digital Twin"}

    def test_no_matches_in_plain_prose(self):
        assert acronyms.body_candidates("Nothing here looks like an acronym.") == {}

    def test_empty_text(self):
        assert acronyms.body_candidates("") == {}

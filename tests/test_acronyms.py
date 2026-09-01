"""load_vocabulary() merges the vendored acronym floor with a user's own
file, additively -- the user's expansion wins on a shared key, and every
vendored entry the user doesn't redefine still applies. See
assets/style/README.md and GitHub issue #190.
"""

import pytest

from chitragupta import acronyms, config


class TestLoadDegradesCleanly:
    """#504, m-31: a malformed acronyms file used to propagate a raw
    tomllib.TOMLDecodeError, and a non-string expansion crashed
    stale_expansions() with AttributeError on the first .strip() call."""

    def test_unparseable_toml_raises_a_typed_error(self, monkeypatch, tmp_path):
        bad = tmp_path / "bad.toml"
        bad.write_text("this is not = = valid toml [[[", encoding="utf-8")
        monkeypatch.setattr(config, "ACRONYMS_DEFAULT_PATH", bad)
        monkeypatch.setattr(config, "ACRONYMS_PATH", bad)

        with pytest.raises(acronyms.AcronymsError, match="could not be parsed"):
            acronyms.load_vocabulary()

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

        # "COUNT" was filtered out of the vocabulary entirely, so no
        # glossary entry can be compared against it -- the crash this
        # guards against never gets the chance to happen.
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
    """No monkeypatching -- the actual assets/style/acronyms.toml this
    repo ships, matching test_config.py's TestRealConfigToml pattern for
    CSL_STYLE_PATH."""

    def test_has_the_issues_five_named_examples(self):
        vocab = acronyms.load_vocabulary()
        for term in ("PDF", "CPU", "URL", "API", "HTML"):
            assert term in vocab


class TestSuggest:
    """suggest() -- which glossary entries look like an acronym and
    aren't in the vocabulary yet. Takes a plain dict, not a draft path:
    `dossier.glossary_terms()` supplies the glossary, so this module
    never needs to import `chitragupta.dossier` (that module already imports
    this one for load_vocabulary(), and a two-way import would cycle)."""

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
        # The real shape content/dossiers/books/digital-twins-for-software-
        # engineers/02-twin-shadow-model-simulation/scope.md uses -- none of
        # this project's own 155 real glossary terms are a bare acronym.
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
    """stale_expansions() -- glossary acronyms whose recorded expansion no
    longer agrees with the current vocabulary. Same shape-recognition as
    suggest(), the opposite direction: only terms already in the
    vocabulary are worth comparing."""

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
    """body_candidates() -- acronyms defined inline in a draft's own
    prose via "Name (ACRONYM)", the same shape a glossary bullet's
    parenthetical form uses. Both fixes below are measured against the
    real 15-chapter book at
    content/dossiers/books/digital-twins-for-software-engineers, not
    assumed -- see the function's own docstring.
    """

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
        """Measured against the real book: chapter 6 defines "**Functional
        Mock-up Interface (FMI)**", and a name pattern that could not carry
        the hyphenated "Mock-up" captured only "Interface" -- which is what
        `acronyms-suggest --apply` would then have written into the author's
        own vocabulary, as a wrong expansion nobody typed."""
        text = "The **Functional\nMock-up Interface (FMI)** is the standard."
        assert acronyms.body_candidates(text) == {
            "Functional Mock-up Interface (FMI)": "Functional Mock-up Interface"
        }

    def test_reflows_a_hard_line_wrap_inside_one_phrase(self):
        # The real shape: markdown wraps prose at a fixed column, so a
        # bolded phrase can be split across two physical lines on disk.
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

"""load_vocabulary() merges the vendored acronym floor with a user's own
file, additively -- the user's expansion wins on a shared key, and every
vendored entry the user doesn't redefine still applies. See
assets/style/README.md and GitHub issue #190.
"""

from src import acronyms, config


def test_defaults_to_the_vendored_file_when_no_override_is_set(monkeypatch, tmp_path):
    vendored = tmp_path / "vendored.toml"
    vendored.write_text('PDF = "Portable Document Format"\n', encoding="utf-8")
    monkeypatch.setattr(config, "ACRONYMS_DEFAULT_PATH", vendored)
    monkeypatch.setattr(config, "ACRONYMS_PATH", vendored)

    assert acronyms.load_vocabulary() == {"PDF": "Portable Document Format"}


def test_a_user_file_is_merged_over_the_vendored_one(monkeypatch, tmp_path):
    vendored = tmp_path / "vendored.toml"
    vendored.write_text(
        'PDF = "Portable Document Format"\n'
        'API = "Application Programming Interface"\n',
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
    never needs to import `src.dossier` (that module already imports
    this one for load_vocabulary(), and a two-way import would cycle)."""

    def test_suggests_an_acronym_shaped_term_not_in_the_vocabulary(self, monkeypatch):
        monkeypatch.setattr(
            acronyms, "load_vocabulary",
            lambda: {"PDF": "Portable Document Format"},
        )
        glossary = {"DTaaS": "Digital Twin as a Service."}
        assert acronyms.suggest(glossary) == glossary

    def test_does_not_suggest_a_term_already_in_the_vocabulary(self, monkeypatch):
        monkeypatch.setattr(
            acronyms, "load_vocabulary",
            lambda: {"DTaaS": "Digital Twin as a Service"},
        )
        glossary = {"DTaaS": "Digital Twin as a Service."}
        assert acronyms.suggest(glossary) == {}

    def test_does_not_suggest_a_non_acronym_shaped_term(self, monkeypatch):
        monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {})
        glossary = {"Twin state": "the digital object's current estimate."}
        assert acronyms.suggest(glossary) == {}

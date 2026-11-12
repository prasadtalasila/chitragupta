"""The project's style-exceptions term list (#1187)."""

import pytest

from chitragupta import config, style_exceptions


@pytest.fixture
def paths(tmp_path, monkeypatch):
    exceptions = tmp_path / "style_exceptions.toml"
    acronyms = tmp_path / "acronyms.toml"
    monkeypatch.setattr(config, "STYLE_EXCEPTIONS_PATH", exceptions)
    monkeypatch.setattr(config, "ACRONYMS_PATH", acronyms)
    return exceptions, acronyms


def test_absent_file_has_no_terms(paths):
    assert style_exceptions.file_terms() == ()


def test_terms_are_read_in_order(paths):
    paths[0].write_text('terms = ["Unified Process", " Rational Rose "]\n')
    assert style_exceptions.file_terms() == ("Unified Process", "Rational Rose")


def test_missing_terms_key_is_empty(paths):
    paths[0].write_text("# nothing yet\n")
    assert style_exceptions.file_terms() == ()


@pytest.mark.parametrize(
    "body",
    ["terms = [", "trems = []", 'terms = "x"', 'terms = [""]', "terms = [1]"],
    ids=["malformed", "unknown-key", "non-list", "empty-string", "non-string"],
)
def test_bad_file_raises_naming_the_path(paths, body):
    paths[0].write_text(body)
    with pytest.raises(ValueError, match="style_exceptions.toml"):
        style_exceptions.file_terms()


def test_unreadable_file_raises(paths):
    paths[0].mkdir()
    with pytest.raises(ValueError, match="style_exceptions.toml"):
        style_exceptions.file_terms()


def test_terms_merge_the_vocabulary(paths):
    paths[1].write_text('UML = "Unified Modeling Language"\n')
    paths[0].write_text('terms = ["unified modeling language", "Rational Rose"]\n')
    found = style_exceptions.terms()
    assert [t for t in found if t.lower() == "unified modeling language"] == [
        "unified modeling language"
    ]
    assert "Rational Rose" in found
    assert "Portable Document Format" in found


def test_terms_are_longest_first(paths):
    paths[1].write_text('AB = "Alpha Beta Gamma"\n')
    paths[0].write_text('terms = ["Xy", "Longer Term"]\n')
    found = style_exceptions.terms()
    assert list(found) == sorted(found, key=len, reverse=True)
    assert found.index("Alpha Beta Gamma") < found.index("Longer Term") < found.index("Xy")

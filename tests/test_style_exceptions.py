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


def _finding(line, start, end, check="chitragupta.DialectGB"):
    return {"Check": check, "Line": line, "Span": [start, end], "Match": "x"}


@pytest.fixture
def uml(paths):
    paths[1].write_text('UML = "Unified Modeling Language"\n')


def test_dialect_finding_inside_a_term_is_dropped(uml):
    text = "The Unified Modeling Language is used.\n"
    assert style_exceptions.drop_exempt([_finding(1, 13, 20)], text) == []


def test_same_word_outside_the_term_is_kept(uml):
    text = "Modeling is not the Unified Modeling Language.\n"
    kept = style_exceptions.drop_exempt([_finding(1, 1, 8), _finding(1, 29, 36)], text)
    assert kept == [_finding(1, 1, 8)]


def test_acronyms_rule_is_never_dropped(uml):
    finding = _finding(1, 13, 20, check="chitragupta.Acronyms")
    text = "The Unified Modeling Language is used.\n"
    assert style_exceptions.drop_exempt([finding], text) == [finding]


def test_term_at_the_start_of_a_longer_word_does_not_exempt(paths):
    paths[0].write_text('terms = ["Rose"]\n')
    text = "A Rosette is not Rose.\n"
    finding = _finding(1, 3, 6)  # "Rose" inside "Rosette": needs the trailing guard
    assert style_exceptions.drop_exempt([finding], text) == [finding]


def test_term_at_the_end_of_a_longer_word_does_not_exempt(paths):
    paths[0].write_text('terms = ["Rose"]\n')
    text = "A Prose line.\n"
    finding = _finding(1, 4, 7)  # "rose" inside "Prose": needs the leading guard
    assert style_exceptions.drop_exempt([finding], text) == [finding]


def test_regex_metacharacters_in_a_term(paths):
    paths[0].write_text('terms = ["C++ Runtime"]\n')
    text = "The C++ Runtime and a CCC Runtime.\n"
    inside, outside = _finding(1, 5, 7), _finding(1, 27, 33)
    assert style_exceptions.drop_exempt([inside, outside], text) == [outside]


def test_non_ascii_before_the_term(uml):
    text = "Café and the Unified Modeling Language.\n"
    assert style_exceptions.drop_exempt([_finding(1, 22, 29)], text) == []


def test_finding_on_a_line_past_the_text_is_kept(uml):
    finding = _finding(9, 1, 3)
    assert style_exceptions.drop_exempt([finding], "one line\n") == [finding]

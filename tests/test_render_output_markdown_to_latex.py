"""`markdown_to_latex`: Markdown snippets to LaTeX in one pandoc process,
for the book's generated glossary and list of symbols (#1138)."""

import pytest

from chitragupta.render_output import _pandoc
from chitragupta.render_output._errors import ConversionError, MissingBinary
from tests.conftest import pandoc_available


@pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
def test_each_text_comes_back_in_order_as_latex():
    out = _pandoc.markdown_to_latex(["an **actual twin**", "50% & `m_t` and $M_0$"])
    assert out[0] == r"an \textbf{actual twin}"
    assert r"50\% \&" in out[1]
    assert r"\(M_0\)" in out[1]
    assert len(out) == 2


@pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
def test_a_text_of_several_paragraphs_stays_one_text():
    assert len(_pandoc.markdown_to_latex(["one\n\ntwo", "three"])) == 2


def test_no_texts_runs_no_pandoc(monkeypatch):
    monkeypatch.setattr(_pandoc, "_require", lambda binary: pytest.fail("ran pandoc"))
    assert _pandoc.markdown_to_latex([]) == []


def test_a_text_holding_the_separator_is_refused():
    with pytest.raises(ConversionError, match="separator"):
        _pandoc.markdown_to_latex([f"a {_pandoc._SEPARATOR} b"])


def test_a_missing_pandoc_is_the_render_layers_own_error(monkeypatch):
    def missing(binary):
        raise MissingBinary(f"'{binary}' is not on PATH.")

    monkeypatch.setattr(_pandoc, "_require", missing)
    with pytest.raises(MissingBinary):
        _pandoc.markdown_to_latex(["text"])


@pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
def test_a_text_that_would_continue_a_definition_list_stays_its_own():
    """A paragraph starting `: ` turns the paragraph before it into a
    definition-list term, which a bare separator paragraph would be."""
    out = _pandoc.markdown_to_latex(["first", ": second", "third"])
    assert out[0] == "first"
    assert out[2] == "third"
    assert len(out) == 3


def test_a_conversion_that_loses_a_text_is_refused(monkeypatch):
    class Result:
        stdout = "only one part"

    monkeypatch.setattr(_pandoc, "_require", lambda binary: None)
    monkeypatch.setattr(_pandoc.programs, "require_program", lambda binary: binary)
    monkeypatch.setattr(_pandoc.subprocess, "run", lambda *a, **k: Result())
    with pytest.raises(ConversionError, match="2 texts"):
        _pandoc.markdown_to_latex(["one", "two"])


def test_the_output_is_split_on_the_separator_block(monkeypatch):
    """No pandoc needed, so every leg covers the split, Windows included."""
    seen = {}

    class Result:
        stdout = f"one\n\n%{_pandoc._SEPARATOR}\n\ntwo\n"

    def run(argv, **kwargs):
        seen["input"] = kwargs["input"]
        return Result()

    monkeypatch.setattr(_pandoc, "_require", lambda binary: None)
    monkeypatch.setattr(_pandoc.programs, "require_program", lambda binary: binary)
    monkeypatch.setattr(_pandoc.subprocess, "run", run)
    assert _pandoc.markdown_to_latex(["a", "b"]) == ["one", "two"]
    assert f"```{{=latex}}\n%{_pandoc._SEPARATOR}\n```" in seen["input"]

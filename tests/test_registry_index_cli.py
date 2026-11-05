"""`registry build --index` over a real accepted book (#1168): the term
table it writes, and the `index.toml` it refuses without writing."""

import json

import pytest

from chitragupta import registry, spec
from chitragupta.registry._index_terms import term_id

# conftest's `signed_book` reads this module's BOOK_SPEC as the outline.
from tests.test_registry import BOOK_SPEC, accept  # noqa: F401


@pytest.fixture
def book(signed_book):
    return signed_book


def build_index(book, tmp_path):
    target = tmp_path / "rendered" / "index-terms.json"
    return registry.main(["build", str(book), "--index", str(target)]), target


def test_build_writes_the_term_table(book, tmp_path, capsys):
    accept(
        book,
        "ch-model",
        "",
        glossary="- **Digital twin (DT)** -- a model paired with a live link.",
        math={"M_0": "M_0"},
        symbols=[("M_0", "**Digital twin**")],
    )
    code, target = build_index(book, tmp_path)
    assert code == 0
    data = json.loads(target.read_text(encoding="utf-8"))
    twin = data["terms"][term_id("digital twin")]
    assert twin["defined_in"] == ["ch-model"]
    assert twin["symbols"] == ["$M_0$"]
    assert data["see"] == {"DT": term_id("digital twin")}
    assert f"Wrote {target}." in capsys.readouterr().out


def test_rebuilding_unchanged_units_writes_the_same_bytes(book, tmp_path):
    accept(book, "ch-model", "", glossary="- **Model** -- a description.")
    _, target = build_index(book, tmp_path)
    first = target.read_bytes()
    build_index(book, tmp_path)
    assert target.read_bytes() == first


def test_a_bad_index_toml_refuses_and_writes_nothing(book, tmp_path, capsys):
    accept(book, "ch-model", "", glossary="- **Model** -- a description.")
    (spec.spec_dir(book) / "index.toml").write_text('[variants]\nghost = ["x"]\n', encoding="utf-8")
    code, target = build_index(book, tmp_path)
    assert code == 1 and not target.exists()
    err = capsys.readouterr().err
    assert '`[variants]` names "ghost"' in err
    assert "no index-terms.json written" in err


def test_a_misshapen_index_toml_refuses_before_reading_terms(book, tmp_path, capsys):
    accept(book, "ch-model", "", glossary="- **Model** -- a description.")
    (spec.spec_dir(book) / "index.toml").write_text('[variants]\nmodel = "x"\n', encoding="utf-8")
    code, target = build_index(book, tmp_path)
    assert code == 1 and not target.exists()
    assert "wrong shape" in capsys.readouterr().err


# --- `registry index` ------------------------------------------------------


class FakeUpmendex:
    returncode, stderr = 0, ""

    def __call__(self, argv, cwd=None, **kwargs):
        (cwd / "book.ind").write_text("\\begin{theindex}\n\\end{theindex}\n", encoding="utf-8")
        return self


@pytest.fixture
def typeset(book, tmp_path, monkeypatch):
    """A book with one accepted chapter, its term table built, its sidecar
    written and a `book.idx` holding one entry, as a typeset book would."""
    from chitragupta.registry import _index_finish

    monkeypatch.setattr("chitragupta.registry._index_cli.markdown_to_latex", lambda texts: list(texts))
    monkeypatch.setattr(_index_finish.programs, "resolve_program", lambda name: f"/bin/{name}")
    monkeypatch.setattr(_index_finish.subprocess, "run", FakeUpmendex())
    accept(book, "ch-model", "", glossary="- **Digital twin** -- a model paired with a link.")
    _, terms = build_index(book, tmp_path)
    side = {
        "unit": "ch-model",
        "terms_digest": _index_finish.digest(terms),
        "terms": {
            term_id("digital twin"): {
                "count": 2,
                "indexed": True,
                "spellings": {"digital twin": 2},
                "midsentence": {"digital twin": 2},
            }
        },
    }
    (terms.parent / "ch-model.index.json").write_text(json.dumps(side), encoding="utf-8")
    idx = terms.parent / "book.idx"
    idx.write_text(f"\\indexentry{{{term_id('digital twin')}|hyperpage}}{{4}}\n", encoding="utf-8")
    return book, idx


def test_index_writes_the_ind_and_the_report(typeset, capsys):
    book, idx = typeset
    assert registry.main(["index", str(book), "--idx", str(idx)]) == 0
    assert "digital twin@digital twin|hyperpage" in (idx.parent / "book-index.idx").read_text(
        encoding="utf-8"
    )
    report = registry.registry_dir(book) / "index.md"
    assert report.is_file() and (report.parent / "index.json").is_file()
    assert f"index: 1 entry, 0 findings -> {report} (+ .json)" in capsys.readouterr().out


def test_index_refuses_a_stale_build_and_writes_no_report(typeset, capsys):
    book, idx = typeset
    (idx.parent / "ch-model.index.json").unlink()
    assert registry.main(["index", str(book), "--idx", str(idx)]) == 1
    assert "re-render it with --index-terms" in capsys.readouterr().err
    assert not (registry.registry_dir(book) / "index.md").exists()


def test_index_without_pandoc_is_a_missing_binary(typeset, monkeypatch, capsys):
    from chitragupta.render_output._errors import MissingBinary

    def missing(texts):
        raise MissingBinary("pandoc not found")

    monkeypatch.setattr("chitragupta.registry._index_cli.markdown_to_latex", missing)
    book, idx = typeset
    assert registry.main(["index", str(book), "--idx", str(idx)]) == 1
    assert "[missing-binary] pandoc not found" in capsys.readouterr().err


def test_index_with_a_failing_conversion_says_so(typeset, monkeypatch, capsys):
    from chitragupta.render_output._errors import ConversionError

    def failing(texts):
        raise ConversionError("lost a text")

    monkeypatch.setattr("chitragupta.registry._index_cli.markdown_to_latex", failing)
    book, idx = typeset
    assert registry.main(["index", str(book), "--idx", str(idx)]) == 1
    assert "[conversion] pandoc could not convert the index: lost a text" in capsys.readouterr().err


def test_index_warns_about_an_index_toml_edited_since_the_build(typeset, capsys):
    """The report reads `index.toml` again; a problem there is said, not
    swallowed, though the build already refused or accepted the table."""
    book, idx = typeset
    (spec.spec_dir(book) / "index.toml").write_text("[variant]\n", encoding="utf-8")
    assert registry.main(["index", str(book), "--idx", str(idx)]) == 0
    assert "[index] warning: `index.toml` has no table `[variant]`." in capsys.readouterr().err

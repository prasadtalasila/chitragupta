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
    (spec.spec_dir(book) / "index.toml").write_text(
        '[variants]\nghost = ["x"]\n', encoding="utf-8"
    )
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

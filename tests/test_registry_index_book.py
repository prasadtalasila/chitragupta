"""The book index end to end (#1168): two accepted chapters, their term
table, real fragment renders through the filter, a book compiled by
LuaLaTeX, `registry index`, and the last pass that prints the index.

Slow (it compiles), so CI's Linux leg skips it and the local run is the
one that holds it (DEVELOPER-AGENTS.md, "This local run is the only one
that compiles TeX"). The keys are the ones the escaping prototype on
issue 1168 tried: each would break a printed form inside `\\index{}`,
and here each is a glossary term that reaches the index through an
opaque id instead, in the body and in a footnote.
"""

import shutil
import subprocess

import pytest

from chitragupta import registry, render_output, spec
from tests.conftest import pandoc_available

# conftest's `signed_book` reads this module's BOOK_SPEC as the outline.
from tests.test_registry import BOOK_SPEC, accept  # noqa: F401

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not pandoc_available or not shutil.which("lualatex") or not shutil.which("upmendex"),
        reason="needs pandoc, lualatex and upmendex",
    ),
]

GLOSSARY = """- **Digital twin (DT)** -- a model kept in step with one system.
- **C++** -- a language.
- **R&D** -- research and development.
- **50% rule** -- a rule of thumb.
- **Markov chain** -- a memoryless process.
- **Stage 0** -- the first stage.
- **Stage 1** -- the second stage."""

MODEL = """A digital twin is defined here. The digital twin follows its plant.
We use C++ and C++ again, R&D and R&D, the 50% rule twice: the 50% rule.
Stage 0 comes first, then stage 1, then stage 1 again and stage 0 again.
"""

DATA = """Each digital twin needs data, and a digital-twin pipeline moves it.
A Markov chain models it.^[A Markov chain in a footnote, with R&D and R&D too.]
"""

BOOK = r"""\documentclass{book}
\usepackage{imakeidx}
\makeindex[noautomatic,intoc]
\usepackage[hidelinks]{hyperref}
\providecommand{\tightlist}{}
\begin{document}
\mainmatter
\input{ch-model}
\input{ch-data}
\backmatter
\printindex
\end{document}
"""


def lualatex(directory):
    run = subprocess.run(
        ["lualatex", "-interaction=nonstopmode", "book.tex"],
        cwd=directory,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stdout[-3000:]


@pytest.fixture
def book(signed_book):
    return signed_book


def test_a_two_chapter_book_prints_its_index(book, capsys):
    accept(book, "ch-model", MODEL, glossary=GLOSSARY)
    accept(book, "ch-data", DATA)
    (spec.spec_dir(book) / "index.toml").write_text(
        '[parent]\n"stage" = ["stage 0", "stage 1"]\n', encoding="utf-8"
    )
    rendered = None
    for unit in ("ch-model", "ch-data"):
        draft = book / f"{unit}.md"
        target = render_output._output_dir(draft)
        terms = target / "index-terms.json"
        if rendered is None:
            assert registry.main(["build", str(book), "--index", str(terms)]) == 0
            rendered = target
        render_output.render(draft, "tex", fragment=True, index_terms=terms)
    (rendered / "book.tex").write_text(BOOK, encoding="utf-8")
    lualatex(rendered)
    lualatex(rendered)
    capsys.readouterr()
    assert registry.main(["index", str(book), "--idx", str(rendered / "book.idx")]) == 0
    assert "index: " in capsys.readouterr().out
    lualatex(rendered)

    ind = (rendered / "book.ind").read_text(encoding="utf-8")
    for printed in ("C++", "R\\&D", "50\\% rule", "Markov chain", "digital twin"):
        assert f"\\item {printed}," in ind, printed
    assert "\\item DT, \\see{digital twin}" in ind
    assert ind.count("\\item stage\n") == 1 and "\\subitem 0," in ind
    assert "\\textbf" in ind
    text = subprocess.run(
        ["pdftotext", str(rendered / "book.pdf"), "-"], capture_output=True, text=True
    ).stdout
    assert "Index" in text and "Markov chain" in text

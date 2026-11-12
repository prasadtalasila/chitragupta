"""The back matter's running heads, compiled (#1182): an appendix with a
section, then every page `{#back}` can hold, each long enough to turn
a page, so each has pages that print a running head.

The Glossary and List of Symbols open with `\\chapter*`, which sets no
mark, so without their own `\\markboth` every page of both carried the
last appendix's chapter and section titles. The lists, bibliography
and index set their marks in LaTeX itself; they are here so a skeleton
or preamble change that loses one fails too.

Slow (it compiles), so CI's Linux leg skips it and the local run is the
one that holds it (DEVELOPER-AGENTS.md, "This local run is the only one
that compiles TeX"). Pages go through an identity converter, as in
tests/test_registry_pages.py, so it needs `lualatex` and `pdftotext`
but not pandoc.
"""

import subprocess

import pytest

from chitragupta import registry
from chitragupta.registry import _pages
from tests.conftest import lualatex_available, lualatex_book, pdftotext_available

# conftest's `signed_book` reads this module's BOOK_SPEC as the outline.
from tests.test_registry import BOOK_SPEC, accept  # noqa: F401

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not lualatex_available or not pdftotext_available,
        reason="needs lualatex and pdftotext",
    ),
]

ENTRIES = range(1, 121)

BOOK = r"""\documentclass{book}
\usepackage{longtable}
\usepackage{imakeidx}
\makeindex[noautomatic,intoc]
\usepackage[hidelinks]{hyperref}
\usepackage{cleveref}
\begin{document}
\mainmatter
\chapter{Models}\label{ch-model}
%(captions)s
\appendix\crefalias{chapter}{appendix}
\chapter{The mathematics}\label{ch-data}
\section{Further reading}
\backmatter
\input{glossary}
\input{notation}
\cleardoublepage\phantomsection\addcontentsline{toc}{chapter}{\listfigurename}\listoffigures
\cleardoublepage\phantomsection\addcontentsline{toc}{chapter}{\listtablename}\listoftables
\begin{thebibliography}{999}
%(bibliography)s
\end{thebibliography}
\printindex
\end{document}
"""

# Each page's own marker, printed on every entry, and the running head
# a page holding it must carry.
HEADS = {
    "Glossaryterm": "GLOSSARY",
    "Symbolmeaning": "LIST OF SYMBOLS",
    "Figurecaption": "LIST OF FIGURES",
    "Tablecaption": "LIST OF TABLES",
    "Bibentry": "BIBLIOGRAPHY",
    "Indexentry": "INDEX",
}

# The first page of each prints its title instead of a running head.
TITLES = (
    "Glossary",
    "List of Symbols",
    "List of Figures",
    "List of Tables",
    "Bibliography",
    "Index",
)


def write_book(directory, glossary, notation):
    (directory / "glossary.tex").write_text(glossary, encoding="utf-8")
    (directory / "notation.tex").write_text(notation, encoding="utf-8")
    captions = [
        f"\\addcontentsline{{{kind}}}{{{float_}}}{{\\protect\\numberline{{{n}}}{marker} {n:03}}}"
        for kind, float_, marker in (
            ("lof", "figure", "Figurecaption"),
            ("lot", "table", "Tablecaption"),
        )
        for n in ENTRIES
    ]
    bibliography = [f"\\bibitem{{b{n}}} Bibentry {n:03}." for n in ENTRIES]
    text = BOOK % {"captions": "\n".join(captions), "bibliography": "\n".join(bibliography)}
    (directory / "book.tex").write_text(text, encoding="utf-8")
    # `noautomatic`: `\printindex` reads the .ind as `registry index`
    # would leave it, so no indexer is needed.
    items = [f"\\item Indexentry {n:03}, {n}" for n in range(1, 2 * len(ENTRIES) + 1)]
    index = ["\\begin{theindex}", *items, "\\end{theindex}"]
    (directory / "book.ind").write_text("\n".join(index) + "\n", encoding="utf-8")


def pages_of(pdf):
    """Each page's first printed line and the rest of its text."""
    text = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True
    ).stdout
    for page in text.split("\f"):
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        if lines:
            yield lines[0], "\n".join(lines[1:])


@pytest.fixture
def book(signed_book):
    return signed_book


def test_every_back_matter_page_carries_its_own_running_head(book, tmp_path):
    accept(
        book,
        "ch-model",
        "",
        glossary="\n".join(f"- **Glossaryterm {n:03}** -- a definition." for n in ENTRIES),
        math={f"s{n}": f"s_{{{n}}}" for n in ENTRIES},
        symbols=[(f"s{n}", f"Symbolmeaning {n:03}") for n in ENTRIES],
    )
    glossary, notation = _pages.render(registry.build(book), lambda texts: list(texts))
    write_book(tmp_path, glossary, notation)
    lualatex_book(tmp_path)
    lualatex_book(tmp_path)

    seen = {marker: 0 for marker in HEADS}
    for first, body in pages_of(tmp_path / "book.pdf"):
        for marker, head in HEADS.items():
            if marker in body and first not in TITLES:
                assert head in first, f"a page of {marker} entries is headed {first!r}"
                assert "APPENDIX" not in first and "FURTHER READING" not in first
                seen[marker] += 1
    # Every page turned at least once, so each head was really checked.
    assert all(seen.values()), seen

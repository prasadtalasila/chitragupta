"""Corpus lookup: the citekey -> ledger row -> PDF/parsed-text path chain
every tier and CLI mode in this package reads from.

Split out of what was one 2357-line chitragupta/review/verbatim_check.py
(#361): the functions that read the bib file and `content/parsed/` live
here, the package root others import from -- mirroring
chitragupta/dossier/'s own root submodule.

Every location is read off `config` at call time (#854). They used to be
bound once, as module-level `BIB`/`PARSED_DIR`, which froze whichever
project was current at first import: a later `config` change -- a
`CHITRAGUPTA_PROJECT` switch, or `tests/conftest.py`'s `isolated_config`
-- never reached `verbatim locate`/`overlap`.
"""

import re

# `_run` is the one patch point for this module's external launches
# (#854), in the shape `render_output._pandoc._run_pandoc` set: a test
# fakes it here and so fakes this module's subprocess and nobody
# else's. Patching the global `subprocess.run` reached every launch in
# the process.
from subprocess import CalledProcessError, TimeoutExpired
from subprocess import run as _run
from pathlib import Path

from chitragupta import citation_gate, config, ledger, ledger_paths, programs
from chitragupta.citekey_safety import citekey_problem


def pdf_path(citekey: str) -> Path | None:
    """The PDF `sync` resolved for `citekey`, read off its ledger row.

    Not off the bib file. This used to match `@\\w+\\{key,` and
    `file = \\{...\\},` with its own regexes, a second bib parser beside
    `bib_reader`, and missed `@article{ key ,`, an unbraced or last
    `file` field and every escape the exporters write (#956), so the key
    fell back to parsed text and `locate` reported page 1 for it.
    `bib_reader` cannot be called here instead: it needs bibtexparser,
    and this aid runs on bare python. The ledger row is what `bib_reader`
    wrote, which is the same answer, the way `passages.lookup` reads it.

    Confined by `ledger_paths.pdf_file` to the bib file's directory, for
    the reason issue 821 gave: the path is handed to `pdftotext`. No
    ledger, one that needs a sync to migrate, or no row is no PDF, and
    `pages` falls back to the parsed text.
    """
    try:
        with ledger.reading() as con:
            row = con.execute("SELECT pdf_path FROM items WHERE citekey = ?", (citekey,)).fetchone()
    except ledger.NoLedger:
        return None
    confined = ledger_paths.pdf_file(row[0]) if row else None
    return confined if confined is not None and confined.is_file() else None


def _parsed_pages(citekey: str) -> list[str]:
    """The already-parsed text, split on form feeds, or `[]`.

    The citekey was extracted from a draft, and the LaTeX regex accepts
    nearly anything inside `\\cite{...}` -- validate before it becomes a
    path, or `\\citep{../secret}` reads (and the report then echoes)
    files outside the parsed directory (#638). An unsafe key cannot have
    a parse on disk anyway: the sync side has always refused to write
    one.
    """
    if citekey_problem(citekey):
        return []
    parsed = config.PARSED_DIR / f"{citekey}.txt"
    if not parsed.exists():
        return []
    # pdftotext leaves stray NUL/control bytes in some files, which
    # makes grep treat them as binary and report nothing. Strip them
    # so a false "no match" can't be mistaken for a real absence.
    raw = parsed.read_text(encoding="utf-8", errors="replace")
    return re.sub(r"[\x00-\x08\x0e-\x1f]", " ", raw).split("\f")


def pages(citekey: str) -> list[str]:
    """Return list of page texts, 1-indexed by position+1 (PDF page order).

    The PDF is preferred and `content/parsed/` is the fallback -- for a
    citekey with no PDF, and, since #516, for a PDF that cannot be read.
    `pdftotext` was run with `check=True` and no handler, so a
    poppler-less host or one corrupt file gave `verbatim locate` a
    traceback where the identical fallback was already sitting one branch
    above. A page-level answer from the parsed text is worse than one
    from the PDF and far better than a stack trace.
    """
    p = pdf_path(citekey)
    if p is None:
        return _parsed_pages(citekey)
    try:  # pragma: no cover-windows
        out = _run(
            [programs.require_program("pdftotext"), "-layout", str(p), "-"],
            capture_output=True,
            text=True,
            check=True,
            # Bounded as the sync backend is: a PDF that hangs poppler
            # wedged `verbatim locate` indefinitely (#824).
            timeout=config.PARSER_DOCUMENT_TIMEOUT,
        )
    except (  # pragma: no cover-windows
        OSError,
        CalledProcessError,
        TimeoutExpired,
    ):
        return _parsed_pages(citekey)
    return out.stdout.split("\f")  # pragma: no cover-windows


WORD = re.compile(r"[a-z0-9]+")


def norm(text: str) -> list[str]:
    return WORD.findall(text.lower())


def sentences_citing(draft: str | Path, citekey: str) -> list[str]:
    """Whole paragraphs mentioning the citekey, not just the citing sentence.

    Paraphrased-but-uncited sentences sitting next to a citation are
    exactly where borrowed wording hides, so compare the whole
    paragraph against the source.

    Membership is a real citekey match, via `citation_gate`'s own
    extractor, not a bare substring test: BibTeX disambiguation suffixes
    are routine in a real export, so `citekey in p` would also match a
    paragraph citing only the suffixed sibling `f"{citekey}a"`, reporting
    overlap runs against a source that paragraph never cites.
    """
    text = Path(draft).read_text(encoding="utf-8")
    paras = re.split(r"\n\s*\n", text)
    return [
        re.sub(r"\s+", " ", p)
        for p in paras
        if citekey in citation_gate.extract_citekeys_from_line(p)
    ]

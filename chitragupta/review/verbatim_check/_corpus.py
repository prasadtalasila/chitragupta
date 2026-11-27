"""Corpus lookup: the citekey -> ledger row -> PDF/parsed-text path chain
every tier and CLI mode in this package reads from.

Every location is read off `config` at call time (#854): module-level
bindings froze the first project imported, so a later project switch or
`isolated_config` never reached `locate`/`overlap`.
"""

import re

# `_run` is this module's one patch point for external launches (#854):
# patching the global `subprocess.run` reached every launch in the process.
from subprocess import CalledProcessError, TimeoutExpired
from subprocess import run as _run
from pathlib import Path

from chitragupta import citation_gate, config, ledger, ledger_paths, programs
from chitragupta.citekey_safety import citekey_path, citekey_problem


def pdf_path(citekey: str) -> Path | None:
    """The PDF `sync` resolved for `citekey`, read off its ledger row.

    Not a second bib parser (#956 missed spacing, unbraced fields and
    escapes); `bib_reader` needs bibtexparser and this runs on bare
    python, so read the row it wrote. Confined to the bib directory
    (#821), since the path goes to `pdftotext`. No ledger or row: None.
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

    A key from `\\cite{...}` can be nearly anything, so it is validated
    before becoming a path, or `\\citep{../secret}` reads outside (#638).
    """
    if citekey_problem(citekey):
        return []
    parsed = citekey_path(config.PARSED_DIR, citekey, ".txt")
    if not parsed.exists():
        return []
    # Stray NUL/control bytes make grep see binary and report a false
    # "no match".
    raw = parsed.read_text(encoding="utf-8", errors="replace")
    return re.sub(r"[\x00-\x08\x0e-\x1f]", " ", raw).split("\f")


def pages(citekey: str) -> list[str]:
    """Return list of page texts, 1-indexed by position+1 (PDF page order).

    The PDF first; `content/parsed/` for a citekey with no PDF or an
    unreadable one (#516), since a page-level answer beats a traceback.
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
            # Bounded: a PDF that hangs poppler wedged `locate` (#824).
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
    """Whole paragraphs citing the citekey: borrowed wording hides in
    uncited sentences beside a citation.

    A real citekey match via `citation_gate`, not a substring, or a
    paragraph citing only the suffixed sibling `{key}a` would match.
    """
    text = Path(draft).read_text(encoding="utf-8")
    paras = re.split(r"\n\s*\n", text)
    return [
        re.sub(r"\s+", " ", p)
        for p in paras
        if citekey in citation_gate.extract_citekeys_from_line(p)
    ]

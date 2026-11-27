"""Where a citekey's supporting text comes from, and whether it may be
quoted.

One ladder, tried best-first, for any consumer that needs to point at
*part* of a source rather than at the whole thing:

1. `content/docling/<citekey>.passages.json`, if the enrichment layer's
   Docling stage has run. Real reading-ordered paragraphs, semantically labelled.
2. `content/parsed/<citekey>.passages.json`, if the corpus layer parsed
   this citekey with `[parser].backend = "docling"`. Same records, from
   the same `passage_records()` below.
3. `content/parsed/<citekey>.txt` split on form feeds -- page-level only.
4. `pdftotext -layout` on the PDF the ledger recorded, same shape as (3),
   for a citekey parsed by a backend that left no page breaks.

Rungs 1 and 2 are separate files because each layer must be able to
invalidate its own sidecar without deleting the other's; rung 1 wins.

`pdftotext -layout` splices two-column pages line by line (82%-89% of
long lines on 4 of 10 sampled papers), fine for scoring but a collage
when quoted. So a page-level `Passage` carries `text=None`: the
guarantee is structural, not advisory.

The record builder and sidecar file live in `_passage_records.py` and
`_passage_sidecar.py`, re-exported here so writer and reader are found
in one place. Stdlib only, runs with bare `python`.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chitragupta import config, ledger_paths, programs
from chitragupta.citekey_safety import citekey_path, citekey_problem

# Re-exported so existing callers keep resolving; `__all__` marks the
# imports as used.
from chitragupta._passage_records import PASSAGE_LABELS, passage_records
from chitragupta._passage_sidecar import (
    SidecarUnreadable,
    clear_sidecar,
    read_records,
    sidecar_path,
    sidecar_state,
    write_sidecar,
)
from chitragupta._passage_words import distinctive

__all__ = [
    "Passage",
    "PASSAGE_LABELS",
    "SidecarUnreadable",
    "clear_sidecar",
    "corpus_passages",
    "distinctive",
    "passage_records",
    "read_records",
    "sidecar_path",
    "sidecar_state",
    "source_passages",
    "write_sidecar",
]


@dataclass
class Passage:
    """A candidate span of source text. `text` is None when the source
    couldn't be read in reading order: the passage stands for a whole page
    and must not be quoted."""

    page: int | None
    words: set[str]
    text: str | None = None
    label: str | None = None

    @property
    def quotable(self) -> bool:
        return self.text is not None


def _page_number(raw) -> int | None:
    """A sidecar's `page` as a 1-based page number, or None.

    The sidecar may be hand-edited, so anything that is not a page a
    reader could turn to becomes None. `bool` is excluded explicitly, or
    `True` would read as page 1.
    """
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 1:
        return None
    return raw


def _ledger_row(con, citekey: str) -> Any:
    row = con.execute(
        "SELECT parsed_path, pdf_path, title, status FROM items WHERE citekey = ?", (citekey,)
    ).fetchone()
    return row


# Asked before any rung (#1153): a dropped key keeps its sidecars and a
# failed re-parse keeps old text, so only a `parsed` row's files are
# current (#490). No sync hint for a missing row, which may never have
# been real.
def _not_current(row) -> str | None:
    """Why `row`'s files may not be read, or None if they may."""
    if row is None:
        return "not found in the corpus"
    if row[3] != "parsed":
        return f"status is {row[3]} -- no current parsed text"
    return None


def _from_sidecar(path: Path) -> list[Passage] | None:
    try:
        records = read_records(path)
    except SidecarUnreadable:
        # Page-level costs nothing lasting: `sync` re-parses a document
        # with an unreadable sidecar (issue 844).
        return None
    if not records:
        return None
    found = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        text = rec.get("text")
        text = text.strip() if isinstance(text, str) else ""
        if not text:
            continue
        label = rec.get("label")
        found.append(
            Passage(
                page=_page_number(rec.get("page")),
                words=distinctive(text),
                text=text,
                label=label if isinstance(label, str) else None,
            )
        )
    return found or None


def _from_pages(raw: str) -> list[Passage]:
    """One passage per form-feed-delimited page, not quotable: a window cut
    from column-spliced text would read as a quotation. A blank page is
    dropped but keeps its number, so pages match what a reader turns to.
    """
    return [
        Passage(page=i, words=distinctive(page))
        for i, page in enumerate(raw.split("\f"), 1)
        if page.strip()
    ]


# The reason is non-`None` exactly when the list is empty (#509/m-42).
def structural_passages(citekey: str) -> list[Passage] | None:
    """Rungs 1 and 2 only -- the reading-ordered, semantically labelled
    records -- or None if neither sidecar is there to read.

    For callers needing structure, such as `_abstract.py`, for which
    whole-page fallbacks would wrongly read as "no abstract". `None` keeps
    "could not read" apart from an empty result; a `pdftotext` parse
    writes no sidecar, so this is a real case.
    """
    if citekey_problem(citekey):
        return None
    # Rung 1 first: a second, independent parse, and the richer one.
    for path in (
        citekey_path(config.DOCLING_DIR, citekey, ".passages.json"),
        sidecar_path(citekey),
    ):
        sidecar = _from_sidecar(path)
        if sidecar:
            return sidecar
    return None


def corpus_passages(citekey: str) -> list[Passage] | None:
    """Rung 2 alone -- what *this* layer's own parse recorded -- for callers
    that must not move when `chitragupta.enrich` runs (the BM25 index and
    `_reference_cut.py`).
    """
    return _from_sidecar(sidecar_path(citekey))


def source_passages(con, citekey: str) -> tuple[list[Passage], str | None]:
    """Best available passages for `citekey`, plus a reason if there are
    none."""
    # Citekeys may come from a draft, where `\cite{...}` accepts nearly
    # anything, so the stem is validated before it is a path (#638).
    problem = citekey_problem(citekey)
    if problem:
        return [], f"citekey is unsafe as a filename stem: {problem}"
    row = _ledger_row(con, citekey)
    stale = _not_current(row)
    if stale:
        return [], stale
    sidecar = structural_passages(citekey)
    if sidecar:
        return sidecar, None

    # Both columns confined before either is opened (issue 821; relative,
    # #966). The PDF path is handed to `pdftotext`, so an unconfined row
    # would run a subprocess over an arbitrary host file.
    parsed_path = ledger_paths.parsed_file(row[0])
    pdf_path = ledger_paths.pdf_file(row[1])
    single_page: list[Passage] = []
    if parsed_path and parsed_path.exists():
        raw = parsed_path.read_text(encoding="utf-8", errors="replace")
        found = _from_pages(raw)
        # No form feeds yields one "page", every hit p.1: try the PDF.
        if len(found) > 1:
            return found, None
        # Held, not discarded (#509/m-42): one page at p.1 beats none when
        # rung 4 cannot do better.
        single_page = found

    if pdf_path and pdf_path.exists():
        return _from_pdf(str(pdf_path), single_page)

    if single_page:
        return single_page, None
    return [], "no parsed text with page breaks and no readable PDF"


# `single_page` is rung 3's held result, the answer whenever this rung
# cannot better it (#509/m-42).
def _from_pdf(pdf_path: str, single_page: list[Passage]) -> tuple[list[Passage], str | None]:
    """Rung 4: `pdftotext` over the PDF, falling back to `single_page`."""
    try:
        # Explicit encoding and errors: the platform codec under strict
        # handling would raise on one bad byte and end the whole report.
        out = subprocess.run(
            [programs.require_program("pdftotext"), "-layout", pdf_path, "-"],
            capture_output=True,
            check=True,
            encoding="utf-8",
            errors="replace",
            # A malformed PDF can hang poppler (#824); a timeout takes the
            # same fallback.
            timeout=config.PARSER_DOCUMENT_TIMEOUT,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        if single_page:
            return single_page, None
        return [], f"couldn't run pdftotext on the PDF ({exc})"
    from_pdf = _from_pages(out.stdout)
    if from_pdf:
        return from_pdf, None
    if single_page:
        return single_page, None
    # An empty rung 4 must still give a reason (#509/m-42); a scanned PDF
    # with no text layer is the usual way here.
    return [], "the PDF has no extractable text layer -- it may be scanned images"

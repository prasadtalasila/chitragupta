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

Rungs 1 and 2 are the same data from two independent parses, and they are
separate files rather than one because the two layers own different
directories and run on their own schedules. The corpus layer must be able
to invalidate *its* sidecar on every re-parse -- including a switch back
to `pdftotext`, which leaves no passages at all -- without deleting an
enrichment sidecar it did not write and cannot reproduce. Rung 1 wins when
both exist: the enrichment stage parses the PDF a second time, under its
own OCR and figure settings, and is the richer of the two.

The difference between (1)/(2) and (3)/(4) is not cosmetic, and it is the
reason this module exists as its own seam. `pdftotext -layout` preserves
a page's *visual* arrangement rather than its reading order, so on a
two-column paper each output line splices together two unrelated columns
-- 82%-89% of long lines on 4 of the 10 papers measured in this project's
own sample. Bag-of-words *scoring* survives that, because splicing moves
words around within a page rather than between pages. *Quoting* does not:
an excerpt cut from that text is a collage of two arguments, which is
worse than no excerpt at all because it reads as evidence.

So the guarantee is structural rather than advisory: a page-level
`Passage` carries `text=None`, and a caller that wants to quote has
nothing to quote. `quotable` reports that fact; it does not gate a field
that is sitting there anyway.

`passage_records()` is re-exported here rather than defined here since
#627 pushed this module past the 250-line ceiling -- it lives in
`chitragupta/_passage_records.py`, still stdlib-only, still the one
definition both producers share (`chitragupta/pdf_text.py` in the corpus
layer and `chitragupta/enrich/docling_parse.py` in the enrichment
layer). The reason it is reachable *through this module* is unchanged:
this module is the sidecar's reader, and writer and reader drift apart
the moment they stop being found in one place.

Extracted from chitragupta/review/citation_provenance.py, which owned this ladder when
it was the only consumer, and kept as its own seam for a second one that
has not been built yet: `chitragupta/retrieval.py` still cuts its snippets as a
character window straight out of `content/parsed/`. A snippet shown to a
drafting agent as evidence is under exactly the same constraint as a
passage shown to a reviewer, and the two should not answer "what does
this source say here?" from different text -- but today they do.

Stdlib only (sqlite3/json/subprocess), like citation_gate.py and
references.py -- runs with bare `python`, no venv. The `re` that used to
be in that list left with the stopword vocabulary; see
`chitragupta/_passage_words.py`, whose `distinctive` is re-exported here.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chitragupta import config

# Re-exported so `passages.distinctive`, `passages.passage_records` and
# `passages.PASSAGE_LABELS` keep resolving for every existing caller --
# see chitragupta/_passage_words.py and chitragupta/_passage_records.py
# for why each moved out. `__all__` names them so the imports are not
# read as unused.
from chitragupta._passage_records import PASSAGE_LABELS, passage_records
from chitragupta._passage_words import distinctive

__all__ = [
    "Passage",
    "PASSAGE_LABELS",
    "clear_sidecar",
    "distinctive",
    "passage_records",
    "sidecar_path",
    "source_passages",
    "write_sidecar",
]


@dataclass
class Passage:
    """A candidate span of source text. `text` is None when the source
    couldn't be read in reading order, in which case the passage stands
    for a whole page and must not be quoted."""

    page: int | None
    words: set[str]
    text: str | None = None
    label: str | None = None

    @property
    def quotable(self) -> bool:
        return self.text is not None


def sidecar_path(citekey: str) -> Path:
    """The corpus layer's passage sidecar for `citekey` (rung 2).

    Built from the citekey in one place, so the writer in
    `chitragupta/pdf_text.py` and the reader below cannot drift apart. The
    enrichment layer's own sidecar (rung 1) is *not* this path -- it lives
    under `config.DOCLING_DIR`, written by that layer's own parse under
    its own OCR and figure settings, so the two must not share a file
    even though they now key on the same string.
    """
    return config.PARSED_DIR / f"{citekey}.passages.json"


def write_sidecar(citekey: str, records: list[dict]) -> Path:
    path = sidecar_path(citekey)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    return path


def clear_sidecar(citekey: str) -> None:
    """Drop any corpus-layer sidecar for `citekey`.

    Called before every re-parse rather than after a failed one. A
    sidecar quotes the PDF *as parsed at the time it was written*, so it
    outlives its own truth in three ways: the backend changes to one that
    produces no passages, the parse of an edited PDF fails outright, or
    the same backend re-runs and produces different text. Removing it up
    front makes all three land on "no sidecar" instead of "last week's
    sentences, attributed to today's document".
    """
    sidecar_path(citekey).unlink(missing_ok=True)


def _page_number(raw) -> int | None:
    """A sidecar's `page` as a 1-based page number, or None.

    `passage_records` writes Docling's own `page_no` here, so the
    machine-written case is always an int -- but the file is JSON on
    disk, it may have been hand-edited, and `Passage.page` is both
    rendered straight into "p.{page}" and typed `int | None` for callers
    that store it. Anything that isn't a page number a reader could turn
    to becomes None, which the report already knows how to omit, rather
    than propagating as one.

    `bool` is excluded explicitly because it is an `int` subclass in
    Python, and `True` would otherwise report as page 1.
    """
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 1:
        return None
    return raw


def _ledger_row(con, citekey: str) -> Any:
    row = con.execute(
        "SELECT parsed_path, pdf_path, title FROM items WHERE citekey = ?", (citekey,)
    ).fetchone()
    return row


def _from_sidecar(path: Path) -> list[Passage] | None:
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        # UnicodeDecodeError alongside the other two: a sidecar truncated
        # mid-write by a killed process can split a multi-byte character,
        # which fails to decode before json ever sees it. Falling back to
        # page-level costs a re-parse at worst; raising would take down a
        # whole report over one damaged file.
        return None
    if not isinstance(records, list) or not records:
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
    """One passage per form-feed-delimited page, not quotable.

    Deliberately whole pages rather than windows within them: a window
    cut from column-spliced text reads as a quotation while being a
    collage, and there is no way to tell from the text alone which
    documents are affected.

    A blank page is dropped but still consumes its number, so a page
    reported here is the page a reader will turn to.
    """
    return [
        Passage(page=i, words=distinctive(page))
        for i, page in enumerate(raw.split("\f"), 1)
        if page.strip()
    ]


# The reason is non-`None` exactly when the list is empty, and that
# pairing is what #509/m-42 restored at both ends: a held single-page
# rung-3 result used to be dropped on the way to rung 4 and returned as
# `([], "no parsed text with page breaks and no readable PDF")` when rung
# 4 could not run -- false about the first half -- while an empty rung 4
# returned `([], None)`, no passages and no explanation at all.
def source_passages(con, citekey: str) -> tuple[list[Passage], str | None]:
    """Best available passages for `citekey`, plus a reason if there are
    none."""
    # Rung 1 before rung 2: both hold the same kind of record, but the
    # enrichment layer's is a second, independent parse of the PDF under
    # its own OCR and figure settings, so it is the richer of the two
    # whenever a run has paid for it.
    for path in (config.DOCLING_DIR / f"{citekey}.passages.json", sidecar_path(citekey)):
        sidecar = _from_sidecar(path)
        if sidecar:
            return sidecar, None

    row = _ledger_row(con, citekey)
    if row is None:
        return [], "not in the ledger -- run `python -m chitragupta.corpus sync`"

    parsed_path, pdf_path, _title = row
    single_page: list[Passage] = []
    if parsed_path and Path(parsed_path).exists():
        raw = Path(parsed_path).read_text(encoding="utf-8", errors="replace")
        found = _from_pages(raw)
        # A backend that emits no form feeds yields exactly one "page",
        # which would report every hit as p.1. Fall through to the PDF.
        # Both shipped backends do emit them, so this now catches a
        # genuinely single-page source (where rung 4 says the same thing)
        # rather than every docling parse.
        if len(found) > 1:
            return found, None
        # Held rather than discarded (#509/m-42). Falling through is right
        # only while rung 4 might still do better; when it cannot -- no
        # PDF, or pdftotext produces nothing -- returning `[]` threw away
        # real parsed text and reported "no parsed text with page breaks
        # and no readable PDF", which is false about the first half. One
        # page attributed to p.1 is a worse answer than several; it is a
        # far better one than none.
        single_page = found

    if pdf_path and Path(pdf_path).exists():
        return _from_pdf(pdf_path, single_page)

    if single_page:
        return single_page, None
    return [], "no parsed text with page breaks and no readable PDF"


# `single_page` is whatever rung 3 held -- a form-feed-free parse read as
# one page. It is the answer whenever this rung cannot better it, which is
# the half of #509/m-42 that used to return `[]` and a reason that was
# false about the parsed text it had just thrown away.
def _from_pdf(pdf_path: str, single_page: list[Passage]) -> tuple[list[Passage], str | None]:
    """Rung 4: `pdftotext` over the PDF, falling back to `single_page`."""
    try:
        # encoding/errors rather than a bare text=True: that decodes
        # with the *platform* encoding under strict error handling, so
        # a single undecodable byte anywhere in a paper -- a ligature,
        # a stray control character, anything under a C-locale host --
        # raises UnicodeDecodeError, which is not in the except clause
        # below and would take down a whole report over one PDF. Same
        # guard the parsed-text branch above already applies.
        out = subprocess.run(
            ["pdftotext", "-layout", pdf_path, "-"],
            capture_output=True,
            check=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        if single_page:
            return single_page, None
        return [], f"couldn't run pdftotext on the PDF ({exc})"
    from_pdf = _from_pages(out.stdout)
    if from_pdf:
        return from_pdf, None
    if single_page:
        return single_page, None
    # An empty rung 4 used to return `([], None)` -- no passages and no
    # reason, which every caller renders as a blank where an explanation
    # belongs (#509/m-42). pdftotext exiting 0 on a scanned PDF with no
    # text layer is the ordinary way to get here.
    return [], "the PDF has no extractable text layer -- it may be scanned images"

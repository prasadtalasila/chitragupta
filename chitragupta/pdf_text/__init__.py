"""PDF text extraction: dispatches to whichever backend config.PARSER
names (config.toml's [parser].backend, or the PARSER env var) --
"pdftotext" (default) or "docling". Both write into
the same place, content/parsed/<citekey>.txt, so every downstream
consumer (chitragupta/ledger.py, chitragupta/retrieval.py, chitragupta/review/verbatim_check/)
stays backend-agnostic; only this module needs to know which one is
configured.

pdftotext has no Python dependency (a subprocess call to poppler-utils).
Its output has native page boundaries (form-feed characters between
pages); docling's does not by default, but _extract_docling asks
for the same `\f` markers explicitly, so both backends' output in
content/parsed/ has the same shape -- see that function's docstring for
the one way the two aren't quite identical. See config.toml's [parser]
comment for the full tradeoffs (speed, OCR cost) before switching off
the default.

The dispatch is deliberately a table rather than an if/else: adding a
backend is a `_extract_*` function plus one `_EXTRACTORS` entry, and
markitdown was removed through the same seam (see docs/PDF-PARSER.md for why).

**A package since #361**, split out of what was one 1034-line module: the
extraction dispatch stays here, the docling worker pool/GPU/converter
lifecycle moved to `_sizing.py`/`_gpu.py`/`_worker.py`/`_interrupt.py`/
`_startup.py`/`_pool.py`/`_converter.py`, the two backend implementations
to `_backends.py`, and the annotated-output stream to `_annotate.py` --
the three seams the issue named, the middle one split further because it
alone was still over C2. Every name below is re-exported so
`from chitragupta import pdf_text; pdf_text.<name>` keeps reaching it
exactly as it did when this was one file.
"""

import importlib.util
import re
import shutil
from pathlib import Path

from chitragupta import config, passages


class BackendUnavailable(RuntimeError):
    """config.PARSER's backend isn't usable on this host right now."""


class MissingBinary(BackendUnavailable):
    """pdftotext specifically isn't on PATH -- kept as its own subclass
    (predates the multi-backend dispatch) rather than folded into
    MissingDependency, since chitragupta/sync.py's early history and tests
    already reference it by this name."""


class MissingDependency(BackendUnavailable):
    """docling specifically isn't installed (not on PATH --
    a Python package, via pyproject.toml's "enrich" Poetry group)."""


class ExtractionError(RuntimeError):
    """The backend ran but failed on this particular PDF."""


_INSTALL_HINT = {
    "pdftotext": (
        "'pdftotext' not found on PATH. Install poppler-utils "
        "(scripts/install_full_pipeline.sh os-deps) to extract PDF text with it."
    ),
    "docling": (
        "the 'docling' package isn't usable (not installed, or a "
        "transitive dependency is broken). Run 'poetry install --with enrich' "
        "(scripts/install_full_pipeline.sh python-deps) to extract PDF text with it."
    ),
}


def _check_parser(parser: str) -> None:
    # Deliberately left to propagate uncaught out of sync.run() rather
    # than caught-and-printed like MissingBinary/MissingDependency below:
    # this is a misconfiguration (a typo'd PARSER value), not a host
    # missing an optional dependency, and sync.run() already has the same
    # shape for the other fundamental-misconfiguration case -- a missing
    # bib file raises FileNotFoundError uncaught from bib_reader.read_library(),
    # before this function's own try block even starts.
    if parser not in config.PARSER_BACKENDS:
        raise ValueError(
            f"Unknown parser backend {parser!r} (config.toml's [parser].backend, "
            f"or the PARSER env var) -- expected one of {config.PARSER_BACKENDS}."
        )


def unavailable_reason() -> str:
    """Human-readable explanation of why config.PARSER's backend isn't
    usable right now, and how to fix it. Meaningful when is_available()
    is False, and also reused as MissingDependency's message when a
    backend's import fails despite that probe passing (a broken
    transitive dependency -- see _backends._extract_docling)."""
    _check_parser(config.PARSER)
    return _INSTALL_HINT[config.PARSER]


def is_available() -> bool:
    _check_parser(config.PARSER)
    if config.PARSER == "pdftotext":
        return shutil.which("pdftotext") is not None
    return importlib.util.find_spec(config.PARSER) is not None


# A "word" for the run-together check below. Letters only: digits and
# punctuation produce long runs legitimately (DOIs, URLs, base64-ish
# identifiers, table rules) and would otherwise dominate the count.
#
# `[^\W\d_]` is "word character, but not a digit or underscore" -- i.e.
# any Unicode letter. Spelling it `[A-Za-z]` would silently split
# accented and non-Latin words ("Schroder" + "der" out of "Schröder"),
# which both hides real fusion, since a fused run containing an accent
# gets broken into short pieces, and shrinks the token count toward
# PARSE_MIN_TOKENS on non-English documents until the guard stops
# looking at them at all.
_ALPHA_RUN = re.compile(r"[^\W\d_]+")


def run_together_ratio(text: str) -> tuple[float, int]:
    """Fraction of alphabetic tokens longer than
    config.PARSE_LONG_WORD_CHARS, plus the total token count.

    A PDF text extractor decides where the spaces go by comparing glyph
    positions against a tolerance. Set that tolerance too coarse and
    adjacent words fuse -- "isaninputtooranoutputfromafunction" -- which
    is invisible in a spot check but silently wrecks retrieval, because
    chitragupta/retrieval.py tokenizes on whitespace and can no longer match a
    query term buried inside a fused run.

    Measured on this project's own corpus: pdftotext produced 9 such
    tokens out of 113,195 (0.01%) while a since-removed backend produced
    3,647 out of 87,395 (4.17%) over the same 10 PDFs -- three orders of
    magnitude apart, so any threshold between them separates a healthy
    parse from a broken one without needing to be tuned precisely.
    """
    tokens = _ALPHA_RUN.findall(text)
    if not tokens:
        return 0.0, 0
    long_tokens = sum(1 for tok in tokens if len(tok) > config.PARSE_LONG_WORD_CHARS)
    return long_tokens / len(tokens), len(tokens)


def quality_warning(text: str) -> str | None:
    """A one-line complaint about `text`, or None if it looks fine.

    Deliberately a warning rather than an error: the extraction did
    succeed, the text is usable, and a corpus of scanned or unusual
    documents could trip this legitimately. The point is that a
    systematic regression gets *reported* by sync instead of being
    noticed by eye in a retrieval snippet weeks later.
    """
    ratio, total = run_together_ratio(text)
    if total < config.PARSE_MIN_TOKENS or ratio <= config.PARSE_LONG_WORD_RATIO:
        return None
    return (
        f"{ratio:.1%} of words are longer than {config.PARSE_LONG_WORD_CHARS} "
        f"characters ({total} words checked) -- the parser is probably losing "
        f"spaces between words, which degrades retrieval"
    )


def page_count(text: str) -> int:
    """Pages in already-extracted `text`, from the `\\f` page-break
    markers both backends write into content/parsed/<citekey>.txt --
    pdftotext natively, docling via _backends._extract_docling's
    page_break_placeholder (see that function's docstring).

    The two backends don't put `\\f` in the same places, confirmed
    against real `pdftotext -layout` output rather than assumed:
    pdftotext writes one *after* every page, including the last, so an
    N-page document ends in `\\f` and contains N of them. Docling's
    placeholder only goes *between* pages (its own docstring says so),
    so an N-page document contains N-1 and does not end in one.
    `.rstrip()` before counting erases exactly that difference -- form
    feed is whitespace, so it discards a trailing one if pdftotext wrote
    it and is a no-op if docling didn't -- leaving `count + 1` correct
    for both without this function needing to know which backend ran.

    Exact for pdftotext. An undercount for docling by however many pages
    contributed no extracted item, since those get no break -- fine for
    a throughput ratio (sync's pages/s summary line), not a page census.
    """
    return text.rstrip().count("\f") + 1


# Re-exported so `from chitragupta import pdf_text` keeps reaching every one
# of these by the same name it always has, from every file outside this
# package that used to reach a flat chitragupta/pdf_text.py this way. Position
# is load-bearing, not style: `_backends` reaches back into the two
# exceptions defined above via `from chitragupta.pdf_text import
# ExtractionError`, so it (and everything importing it) has to be
# imported after they exist -- the same ordering chitragupta/dossier/__init__.py
# uses for its own submodules. `_EXTRACTORS`/`extract_text`/`extract_one`
# below need `_extract_pdftotext`/`_extract_docling`/`annotated_output`,
# so this block comes before them rather than at the literal end of the
# file.
# pylint: disable=wrong-import-position
from chitragupta.pdf_text._annotate import annotated_output
from chitragupta.pdf_text._backends import _extract_docling, _extract_pdftotext
from chitragupta.pdf_text._converter import _reset_docling_converter, check_docling_status
from chitragupta.pdf_text._gpu import (
    _GPU_MIN_FREE_MIB, _parse_visible_devices, _visible_devices,
    cuda_is_initialised, gpu_count, usable_devices,
)
from chitragupta.pdf_text._interrupt import (
    _TERMINATE_GRACE_SECONDS, interrupt_guard, terminate_workers,
)
from chitragupta.pdf_text._pool import (
    docling_process_pool, drop_stdlib_shadowing_path_entries, process_pool_context,
)
from chitragupta.pdf_text._sizing import (
    allowed_cpus, docling_threads, resolve_workers, worker_ceiling,
)
from chitragupta.pdf_text._startup import (
    _PRELOAD_MODULES, preload_modules, prestart_pool, start_method,
)
from chitragupta.pdf_text._worker import (
    _reset_worker_device, init_worker, is_cuda_oom, worker_device,
)

_EXTRACTORS = {
    "pdftotext": _extract_pdftotext,
    "docling": _extract_docling,
}


def extract_text(pdf_path: str, citekey: str, threads: int | None = None) -> Path:
    """Extract text from a PDF into content/parsed/<citekey>.txt using
    config.PARSER's backend.

    Raises MissingBinary/MissingDependency if that backend isn't usable
    on this host (probe-and-report, like every chitragupta/enrich/* stage -- see
    render_output.MissingBinary -- rather than letting the backend's own
    not-found error surface as an uncaught traceback), or ExtractionError
    if the backend runs but fails on this particular PDF.

    A backend that resolves reading order also returns passage records,
    which are written beside the text as `<citekey>.passages.json` for
    chitragupta/passages.py to quote from. The old sidecar is dropped *before*
    the parse, not replaced after it, so the three ways one can outlive
    its truth all end at "no sidecar" rather than at stale sentences
    attributed to the current PDF: the backend changed to one that
    resolves no reading order, this parse fails outright, or the same
    backend re-runs over an edited PDF.
    """
    if not is_available():
        exc_cls = MissingBinary if config.PARSER == "pdftotext" else MissingDependency
        raise exc_cls(unavailable_reason())

    config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.PARSED_DIR / f"{citekey}.txt"
    passages.clear_sidecar(citekey)
    # Annotated here rather than in extract_one, so the serial path --
    # which runs in the parent and never reaches a pool worker -- is
    # covered by the same code as the parallel one.
    with annotated_output(citekey):
        records = _EXTRACTORS[config.PARSER](pdf_path, out_path, threads)
    # `is not None`, so a backend that resolved reading order and found no
    # prose still writes an (empty) sidecar. That keeps the file's
    # presence a reliable answer to "did a reading-order backend parse
    # this?" -- which is what chitragupta/ledger.py checks before skipping a
    # document it believes is already parsed. The ladder is unaffected: it
    # declines an empty sidecar and falls to the page-level rung.
    if records is not None:
        passages.write_sidecar(citekey, records)
    return out_path


def extract_one(job: tuple[str, str, int | None]) -> tuple[str, str | None, Exception | None]:
    """Entry point for one pool worker: (pdf_path, citekey, threads) in,
    (citekey, out_path, exception) out.

    Defined at module level, and returning the exception rather than
    raising it, because both have to survive pickling across a process
    boundary. Returning it keeps the *type* -- chitragupta/sync.py distinguishes
    ExtractionError from BackendUnavailable and reports them differently,
    which a stringified error would lose.
    """
    pdf_path, citekey, threads = job
    try:
        return citekey, str(extract_text(pdf_path, citekey, threads)), None
    except (ExtractionError, BackendUnavailable) as exc:
        return citekey, None, exc

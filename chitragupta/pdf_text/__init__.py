"""PDF text extraction: dispatches to config.PARSER's backend, "pdftotext"
(default) or "docling".

Both write content/parsed/<citekey>.txt with `\f` page markers, so every
downstream consumer stays backend-agnostic. The dispatch is a table so a
backend is one `_extract_*` function plus one `_EXTRACTORS` entry (see
docs/PDF-PARSER.md, and config.toml's [parser] comment for the tradeoffs).
A package since #361; every name below is re-exported so
`pdf_text.<name>` keeps working.
"""

import importlib.util
import re
from pathlib import Path

from chitragupta import config, install, passages, programs
from chitragupta.citekey_safety import citekey_path


class BackendUnavailable(RuntimeError):
    """config.PARSER's backend isn't usable on this host right now."""


class MissingBinary(BackendUnavailable):
    """pdftotext specifically isn't on PATH; its own subclass because
    chitragupta/sync.py and tests reference it by this name."""


class MissingDependency(BackendUnavailable):
    """docling specifically isn't installed (the "enrich" extra)."""


class ExtractionError(RuntimeError):
    """The backend ran but failed on this particular PDF."""


def write_failed(path: Path, exc: OSError) -> ExtractionError:
    """A transient ExtractionError for an OSError writing `path`.

    Disk full or permission denied is the machine, not the PDF (#842):
    raised bare it aborted sync; marked transient it is retried.
    """
    error = ExtractionError(f"could not write {path}: {exc}")
    error.transient = True
    return error


def document_failure(exc: Exception) -> ExtractionError:
    """An exception no backend promised, as this one document's failure (#962).

    Deterministic, except an `OSError` or `MemoryError`, which is the
    machine and is retried (#842). A string, not the exception, so it
    pickles back from a pool worker whatever the original was.
    """
    error = ExtractionError(f"unexpected {type(exc).__name__}: {exc}")
    if isinstance(exc, (OSError, MemoryError)):
        error.transient = True
    return error


_INSTALL_HINT = {
    "pdftotext": (
        "'pdftotext' not found on PATH. Install poppler-utils "
        f"({install.remedy('os-deps')}) to extract PDF text with it."
    ),
    "docling": (
        "the 'docling' package isn't usable (not installed, or a "
        "transitive dependency is broken). To extract PDF text with it, run, "
        f"{install.enrich_remedy()}."
    ),
}


def unavailable_reason() -> str:
    """Why config.PARSER's backend isn't usable, and how to fix it.

    Also MissingDependency's message when a backend's import fails despite
    is_available() passing (a broken transitive dependency)."""
    return _INSTALL_HINT[config.PARSER]


def is_available() -> bool:
    if config.PARSER == "pdftotext":
        return programs.resolve_program("pdftotext") is not None
    return importlib.util.find_spec(config.PARSER) is not None


# Letters only: digits and punctuation make long runs legitimately (DOIs,
# URLs, table rules). `[^\W\d_]` is any Unicode letter; `[A-Za-z]` would
# split accented words, hiding real fusion and shrinking the token count
# toward PARSE_MIN_TOKENS on non-English documents.
_ALPHA_RUN = re.compile(r"[^\W\d_]+")


def run_together_ratio(text: str) -> tuple[float, int]:
    """Fraction of alphabetic tokens longer than
    config.PARSE_LONG_WORD_CHARS, plus the total token count.

    Fused words ("isaninputtooranoutput...") silently wreck retrieval,
    which tokenizes on whitespace. On this corpus pdftotext gave 0.01%
    and a since-removed backend 4.17%, so any threshold between them
    separates healthy from broken without precise tuning.
    """
    tokens = _ALPHA_RUN.findall(text)
    if not tokens:
        return 0.0, 0
    long_tokens = sum(1 for tok in tokens if len(tok) > config.PARSE_LONG_WORD_CHARS)
    return long_tokens / len(tokens), len(tokens)


def quality_warning(text: str) -> str | None:
    """A one-line complaint about `text`, or None if it looks fine.

    A warning, not an error: the text is usable and unusual documents can
    trip it legitimately; the point is that a systematic regression gets
    reported by sync.
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
    """Pages in already-extracted `text`, from its `\\f` page-break markers.

    pdftotext writes one after every page (N), docling only between pages
    (N-1); `.rstrip()` before counting erases that difference. Docling
    undercounts pages with no extracted item -- fine for sync's pages/s
    line, not a page census.
    """
    return text.rstrip().count("\f") + 1


# Position is load-bearing: `_backends` imports the exceptions defined
# above, so this block must come after them, and before `_EXTRACTORS` and
# extract_text, which need these names. Re-exported so
# `from chitragupta import pdf_text` keeps reaching each one.
# pylint: disable=wrong-import-position
from chitragupta.pdf_text._annotate import annotated_output
from chitragupta.pdf_text._backends import _extract_docling, _extract_pdftotext
from chitragupta.pdf_text._converter import _reset_docling_converter, check_docling_status
from chitragupta.pdf_text._gpu import (
    _GPU_MIN_FREE_MIB,
    _parse_visible_devices,
    _visible_devices,
    cuda_is_initialised,
    gpu_count,
    usable_devices,
)
from chitragupta.pdf_text._interrupt import (
    _TERMINATE_GRACE_SECONDS,
    interrupt_guard,
    terminate_workers,
)
from chitragupta.pdf_text._pool import (
    docling_process_pool,
    drop_stdlib_shadowing_path_entries,
    process_pool_context,
)
from chitragupta.pdf_text._sizing import (
    allowed_cpus,
    docling_threads,
    resolve_workers,
    worker_ceiling,
)
from chitragupta.pdf_text._startup import (
    _PRELOAD_MODULES,
    preload_modules,
    prestart_pool,
    start_method,
)
from chitragupta.pdf_text._worker import (
    _reset_worker_device,
    init_worker,
    is_cuda_oom,
    worker_device,
)

_EXTRACTORS = {
    "pdftotext": _extract_pdftotext,
    "docling": _extract_docling,
}


def extract_text(pdf_path: str, citekey: str, threads: int | None = None) -> Path:
    """Extract text from a PDF into content/parsed/<citekey>.txt using
    config.PARSER's backend.

    Raises MissingBinary/MissingDependency if that backend isn't usable
    here (probe-and-report, not a traceback), or ExtractionError if it
    fails on this PDF. A reading-order backend's passage records go to
    `<citekey>.passages.json`; the old sidecar is dropped *before* the
    parse, so a backend change, a failed parse or an edited PDF all end
    at "no sidecar" rather than stale sentences.
    """
    if not is_available():
        exc_cls = MissingBinary if config.PARSER == "pdftotext" else MissingDependency
        raise exc_cls(unavailable_reason())

    out_path = citekey_path(config.PARSED_DIR, citekey, ".txt")
    # Each disk write is guarded where it happens, so an OSError from
    # anything else is not misreported as one.
    try:
        config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
        passages.clear_sidecar(citekey)
    except OSError as exc:
        raise write_failed(config.PARSED_DIR, exc) from exc
    # Annotated here so the serial path, which never reaches a pool
    # worker, is covered too. The disable is for pylint's inference:
    # config.PARSER resolves to "pdftotext", whose extractor returns None
    # on purpose (#847).
    with annotated_output(citekey):
        # pylint: disable=assignment-from-no-return
        records = _EXTRACTORS[config.PARSER](pdf_path, out_path, threads)
        # pylint: enable=assignment-from-no-return
    # `is not None`, so a reading-order backend that found no prose still
    # writes an empty sidecar: chitragupta/ledger.py checks its presence
    # before skipping a document as already parsed.
    if records is not None:
        try:
            passages.write_sidecar(citekey, records)
        except OSError as exc:
            raise write_failed(passages.sidecar_path(citekey), exc) from exc
    return out_path


def extract_one(job: tuple[str, str, int | None]) -> tuple[str, str | None, Exception | None]:
    """Entry point for one pool worker: (pdf_path, citekey, threads) in,
    (citekey, out_path, exception) out.

    Module-level and returning the exception, because both must survive
    pickling; returning keeps the *type*, which chitragupta/sync.py
    reports differently for ExtractionError and BackendUnavailable.
    """
    pdf_path, citekey, threads = job
    try:
        return citekey, str(extract_text(pdf_path, citekey, threads)), None
    except (ExtractionError, BackendUnavailable) as exc:
        return citekey, None, exc
    except Exception as exc:  # noqa: BLE001 -- the per-document boundary, see document_failure
        return citekey, None, document_failure(exc)

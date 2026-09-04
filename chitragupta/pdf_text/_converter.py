"""Building (and caching) docling's DocumentConverter, and rejecting a
conversion it only half-finished.

Split out of chitragupta/pdf_text.py (#361). Reads the current worker's
device through `_worker.worker_device()` rather than that module's
global directly -- the accessor exists precisely so a cross-module
reader never has to.

Imports `ExtractionError`/`MissingDependency`/`unavailable_reason` from
the package's own `__init__`, which is safe despite this module being
imported *from* that same `__init__` (via `_backends`): both are already
defined there before the bottom-of-file import that reaches this module
-- the same load-bearing ordering `chitragupta/dossier/__init__.py`
documents for its own submodules.
"""

from typing import Any

from chitragupta import config
from chitragupta.pdf_text import ExtractionError, MissingDependency, unavailable_reason
from chitragupta.pdf_text._worker import worker_device

# Distinct docling error messages to quote before summarising the rest.
_MAX_DOCLING_ERRORS = 3

# One converter, reused for the whole process. Docling's
# DocumentConverter keeps its `initialized_pipelines` cache on the
# *instance*, so building one per PDF re-initialises the layout, table
# and OCR models for every single document -- measured at 16.5s of cold
# start on the documented A40 host, against a corpus of 501 PDFs.
#
# Keyed by the settings that change what a converter *is*, not merely
# memoised on "was one built already": otherwise flipping config.PARSER_OCR
# (which tests do, and a user editing config.toml mid-session would) keeps
# silently serving the converter built under the old setting.
_DOCLING_CONVERTER = None
_DOCLING_CONVERTER_KEY = None


def _reset_docling_converter() -> None:
    """Drop the cached converter. Exists for tests -- module-level state
    otherwise leaks one test's fake converter into the next."""
    global _DOCLING_CONVERTER, _DOCLING_CONVERTER_KEY
    _DOCLING_CONVERTER = None
    _DOCLING_CONVERTER_KEY = None


def _docling_converter(threads: int | None = None) -> Any:
    global _DOCLING_CONVERTER, _DOCLING_CONVERTER_KEY

    device = worker_device()
    key = (
        config.PARSER_OCR,
        config.PARSER_FORMULAS,
        threads,
        device,
        config.PARSER_DOCUMENT_TIMEOUT,
    )
    if _DOCLING_CONVERTER is not None and _DOCLING_CONVERTER_KEY == key:
        return _DOCLING_CONVERTER

    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except ImportError as exc:
        raise MissingDependency(unavailable_reason()) from exc

    opts = PdfPipelineOptions()
    opts.do_ocr = config.PARSER_OCR
    # Without this, docling writes `<!-- formula-not-decoded -->` where
    # the equation was, and that marker is what lands in
    # content/parsed/*.txt -- the one artefact chitragupta/retrieval.py
    # indexes, and so the only thing a drafting skill can see. The
    # enrichment layer sets the same option from its own key; these are
    # two parses with two settings, not one setting read twice.
    opts.do_formula_enrichment = config.PARSER_FORMULAS
    # Docling checks this between pipeline stages, so it bounds a
    # pathologically slow document but will not interrupt a hard hang
    # inside one stage. On expiry it returns PARTIAL_SUCCESS rather than
    # raising -- which check_docling_status turns into an ExtractionError,
    # so the truncated text is never written.
    opts.document_timeout = config.PARSER_DOCUMENT_TIMEOUT
    if threads is not None or device is not None:
        # Only touched when a caller has worked out a thread budget or a
        # pool has claimed a GPU for this worker (i.e. when
        # [parser].workers > 1); left alone otherwise, so a default
        # single-worker run gets exactly Docling's own accelerator
        # settings and this module changes nothing about it.
        from docling.datamodel.accelerator_options import AcceleratorOptions

        kwargs = {}
        if threads is not None:
            kwargs["num_threads"] = threads
        if device is not None:
            kwargs["device"] = device
        opts.accelerator_options = AcceleratorOptions(**kwargs)
    _DOCLING_CONVERTER = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )
    _DOCLING_CONVERTER_KEY = key
    return _DOCLING_CONVERTER


# The wordings docling's two document_timeout paths actually produce:
# "Document processing timeout: exceeded 10.000s limit after ..." from
# the page-batch loop, and "document timeout exceeded" from the threaded
# pipeline. Only consulted when an error carries no FailureCategory --
# see _is_docling_timeout.
_DOCLING_TIMEOUT_PHRASES = ("document timeout", "document processing timeout")


def _is_docling_timeout(error, message: str) -> bool:
    """Did this ErrorItem come from `document_timeout` expiring?

    Read from docling's own `FailureCategory` rather than the wording,
    because the two code paths that can expire a document_timeout word
    themselves differently -- "Document processing timeout: exceeded
    ...s limit" from the page-batch loop, "document timeout exceeded"
    from the threaded pipeline -- and a third wording is one upstream
    release away.

    `.value`, not `str()`: FailureCategory is a str-Enum, so `str()`
    gives "FailureCategory.TIMEOUT" where the value it compares equal to
    is "timeout". Getting that wrong would silently classify every real
    timeout as an unreadable PDF, which is the failure this exists to
    prevent.

    The wording is consulted only when there is no category at all --
    what a docling build predating the field looks like -- rather than
    as a second opinion, so a categorised non-timeout error that happens
    to mention the word is not miscounted. Even then it matches the two
    phrases docling actually uses rather than the bare word "timeout",
    which a failure with nothing to do with `document_timeout` can
    legitimately contain (a model download giving up, say). Reporting
    one of those under "raise [parser].document_timeout" would send its
    reader to a setting that had no part in it.
    """
    category = getattr(error, "category", None)
    if category is not None:
        return getattr(category, "value", category) == "timeout"
    lowered = message.lower()
    return any(phrase in lowered for phrase in _DOCLING_TIMEOUT_PHRASES)


def check_docling_status(result) -> None:
    """Reject a conversion Docling only half-finished.

    `convert(raises_on_error=True)` -- the default -- raises only on
    FAILURE. A PARTIAL_SUCCESS returns quietly with a document that stops
    early: the page loop hit a bad page, or `document_timeout` expired.
    Without this check that truncated text is written to
    content/parsed/<citekey>.txt and the ledger records it as parsed, so
    every downstream consumer -- retrieval, the citation gate, provenance
    -- reasons about a source that silently ends at page k of n. On a
    citation-grounding pipeline that is worse than a visible failure.

    The parse-quality guard cannot stand in for this: it measures
    run-together words, not missing content, and its min_tokens floor
    makes it skip exactly the short documents truncation produces.
    """
    status = getattr(result, "status", None)
    if status is None:
        # Fail closed (#509/m-36). Treating an absent `status` as success
        # inverted this check's whole purpose: docling renaming or moving
        # the attribute would have made every PARTIAL_SUCCESS -- a
        # document that stops at page k of n -- pass silently, which is
        # the one outcome the docstring above says must never be written.
        # An upstream rename is a loud, one-line fix found on the first
        # document; a silently truncated corpus is not discoverable at all.
        raise ExtractionError(
            "docling returned a result with no `status` attribute, so a "
            "PARTIAL_SUCCESS cannot be told from a SUCCESS -- refusing to "
            "write a parse that may stop mid-document. The installed "
            "docling no longer reports status where this expects it; see "
            "chitragupta/pdf_text/_converter.py."
        )
    name = getattr(status, "name", str(status))
    if name == "SUCCESS":
        return
    # Deduplicated and capped: docling appends one error per failed page,
    # so a timeout on a 675-page book produced 675 identical copies of
    # "document timeout exceeded" in a single line. The distinct reasons
    # are the diagnostic; the repetition is noise that buries the summary
    # line after it.
    seen, ordered, timed_out = set(), [], False
    for error in getattr(result, "errors", []):
        message = str(getattr(error, "error_message", error))
        # Classified over every error, not just the ones that survive the
        # cap below: docling appends one per failed page and the timeout
        # arrives last, so a book long enough to time out is exactly the
        # case where the deciding error is off the end of the list.
        timed_out = timed_out or _is_docling_timeout(error, message)
        if message not in seen:
            seen.add(message)
            ordered.append(message)
    errors = "; ".join(ordered[:_MAX_DOCLING_ERRORS])
    if len(ordered) > _MAX_DOCLING_ERRORS:
        errors += f"; (+{len(ordered) - _MAX_DOCLING_ERRORS} more)"
    failure = ExtractionError(
        f"docling returned {name} rather than SUCCESS -- the extracted text would "
        f"be incomplete{': ' + errors if errors else ''}"
    )
    failure.timed_out = timed_out
    raise failure

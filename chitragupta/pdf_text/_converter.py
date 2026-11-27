"""Building (and caching) docling's DocumentConverter, and rejecting a
conversion it only half-finished.

Importing from the package `__init__` is safe: the names are defined there
before the import that reaches this module.
"""

from typing import Any

from chitragupta import config
from chitragupta.pdf_text import ExtractionError, MissingDependency, unavailable_reason
from chitragupta.pdf_text._worker import worker_device

_MAX_DOCLING_ERRORS = 3

# One converter per process: docling caches initialised pipelines on the
# *instance*, so one per PDF reloads every model (16.5s cold start on the
# documented A40 host). Keyed by the settings that change what a converter
# is, so flipping config.PARSER_OCR (tests do) doesn't serve a stale one.
_DOCLING_CONVERTER = None
_DOCLING_CONVERTER_KEY = None


def _reset_docling_converter() -> None:
    """Drop the cached converter, so tests don't leak a fake one."""
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
    # Without this docling writes `<!-- formula-not-decoded -->`, and that
    # lands in content/parsed/*.txt, the only text retrieval indexes. The
    # enrichment layer sets the same option from its own key (two parses).
    opts.do_formula_enrichment = config.PARSER_FORMULAS
    # Checked between stages: bounds a slow document, not a hard hang in
    # one stage. Expiry returns PARTIAL_SUCCESS, which check_docling_status
    # rejects, so truncated text is never written.
    opts.document_timeout = config.PARSER_DOCUMENT_TIMEOUT
    if threads is not None or device is not None:
        # Only when a thread budget or a claimed GPU exists ([parser].workers
        # > 1), so a single-worker run keeps docling's own accelerator settings.
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


# The wordings docling's two document_timeout paths produce; consulted
# only when an error carries no FailureCategory.
_DOCLING_TIMEOUT_PHRASES = ("document timeout", "document processing timeout")


def _is_docling_timeout(error, message: str) -> bool:
    """Did this ErrorItem come from `document_timeout` expiring?

    Read from `FailureCategory`, since docling's two timeout paths word it
    differently. `.value`, not `str()`: it is a str-Enum, and `str()` would
    classify every real timeout as an unreadable PDF. The wording is the
    fallback only when there is no category, and matches docling's two
    phrases rather than "timeout", so unrelated failures (a model download
    giving up) aren't sent to `[parser].document_timeout`.
    """
    category = getattr(error, "category", None)
    if category is not None:
        return getattr(category, "value", category) == "timeout"
    lowered = message.lower()
    return any(phrase in lowered for phrase in _DOCLING_TIMEOUT_PHRASES)


def check_docling_status(result) -> None:
    """Reject a conversion Docling only half-finished.

    `convert()` raises only on FAILURE; a PARTIAL_SUCCESS returns a
    document that stops early, which would be recorded as parsed and
    silently end at page k of n for every citation consumer. The
    parse-quality guard cannot stand in: it skips short documents.
    """
    status = getattr(result, "status", None)
    if status is None:
        # Fail closed (#509/m-36): an upstream rename of `status` would
        # otherwise pass every PARTIAL_SUCCESS silently.
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
    # Deduplicated and capped: docling appends one error per failed page
    # (675 identical timeouts on one book).
    seen, ordered, timed_out = set(), [], False
    for error in getattr(result, "errors", []):
        message = str(getattr(error, "error_message", error))
        # Classified over every error, not just the capped ones: the timeout
        # arrives last, off the end of the list for a long book.
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

"""The two extraction backends: pdftotext (a subprocess call) and docling
(the Python library, via `_converter`/`_worker`).

Importing from the package `__init__` is safe: the names are defined there
before the import that reaches this module.
"""

import subprocess
from pathlib import Path

from chitragupta import config, passages, programs
from chitragupta._atomic_write import write_atomically
from chitragupta.pdf_text import ExtractionError, write_failed
from chitragupta.pdf_text._converter import _docling_converter, check_docling_status
from chitragupta.pdf_text._worker import _demote_to_cpu, is_cuda_oom, worker_device


def _write_parsed(out_path: Path, data: bytes | str) -> None:
    """Write the parsed text whole or not at all (#894), for both backends.

    `_parse_outputs_present` takes the file's existence for a finished
    parse, so a truncated one would never be re-parsed. An `OSError` is
    the transient failure #842 defined, not a parse failure.
    """
    try:
        write_atomically(out_path, data)
    except OSError as exc:
        raise write_failed(out_path, exc) from exc


def _extract_pdftotext(pdf_path: str, out_path: Path, threads: int | None = None) -> None:
    # threads is ignored (single-threaded binary); it keeps _EXTRACTORS a
    # uniform table. Returns None, not [], meaning "no reading order":
    # `-layout` spans can splice two columns, so must not be quoted (see
    # chitragupta/passages.py). To stdout, not `out_path`, so the write is
    # atomic and a full disk is distinguishable from an unreadable PDF (#894).
    try:
        completed = subprocess.run(
            [programs.require_program("pdftotext"), "-layout", pdf_path, "-"],
            check=True,
            capture_output=True,
            # A hard kill of an external process, unlike docling's
            # cooperative between-stages check.
            timeout=config.PARSER_DOCUMENT_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        error = ExtractionError(
            f"pdftotext exceeded the {config.PARSER_DOCUMENT_TIMEOUT}s "
            "[parser].document_timeout and was killed"
        )
        # Marked, not just worded: sync reports timeouts separately, and
        # parsing the message would tie the report to this string.
        error.timed_out = True
        raise error from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        raise ExtractionError(stderr or str(exc)) from exc
    _write_parsed(out_path, completed.stdout)


def _extract_docling(pdf_path: str, out_path: Path, threads: int | None = None) -> list[dict]:
    """Writes Markdown, and returns the passages that Markdown can't carry.

    `export_to_markdown()` drops docling's per-item pages, boxes and
    labels; the returned records become
    `content/parsed/<citekey>.passages.json` (rung 2 of
    chitragupta/passages.py's ladder), written by `extract_text`.

    `page_break_placeholder="\\f"` gives the same shape as pdftotext, so
    page-splitting consumers report a real page. Docling breaks only
    *between* pages with items, so an item-less page shifts later page
    numbers; the sidecar is unaffected (it records each item's `page_no`).

    chitragupta/enrich/docling_parse.py is a separate, second parse with
    its own OCR and figure settings, not made redundant by this one.
    """
    converter = _docling_converter(threads)
    try:
        result = converter.convert(pdf_path)
        check_docling_status(result)
    except ExtractionError:
        raise
    except Exception as exc:  # docling has no narrower common exception
        # Not ruff's BLE001: it re-raises `from exc`. The converter is
        # deliberately kept: the failure is this PDF, not the models, and
        # a reload would cost the next document.
        if is_cuda_oom(exc) and worker_device() != "cpu":
            # Bounded: the retry runs on "cpu", where this branch can't be
            # taken. `None` is docling's AUTO, i.e. cuda:0.
            _demote_to_cpu()
            return _extract_docling(pdf_path, out_path, threads)
        error = ExtractionError(str(exc))
        if is_cuda_oom(exc):
            # The machine at this moment, not the PDF: retried next run.
            error.transient = True
        raise error from exc
    _write_parsed(out_path, result.document.export_to_markdown(page_break_placeholder="\f"))
    return passages.passage_records(result.document)

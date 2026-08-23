"""The two extraction backends: pdftotext (a subprocess call) and docling
(the Python library, via `_converter`/`_worker`).

Split out of chitragupta/pdf_text.py (#361). Imports `ExtractionError`
from the package's own `__init__`, which is safe despite this module
being one of the two `__init__` imports used to build `_EXTRACTORS` --
the exception is defined in `__init__.py` before that import runs, the
same load-bearing ordering `chitragupta/dossier/__init__.py` documents
for its own submodules.
"""

import subprocess
from pathlib import Path

from chitragupta import config, passages
from chitragupta.pdf_text import ExtractionError
from chitragupta.pdf_text._converter import _docling_converter, check_docling_status
from chitragupta.pdf_text._worker import _demote_to_cpu, is_cuda_oom, worker_device


def _extract_pdftotext(pdf_path: str, out_path: Path, threads: int | None = None) -> None:
    # threads is accepted and ignored: pdftotext is a single-threaded
    # external binary. The parameter exists so _EXTRACTORS stays a plain
    # uniform table rather than growing a per-backend call signature.
    #
    # Returns None -- not an empty list -- for the reason chitragupta/passages.py
    # exists: `-layout` output preserves a page's visual arrangement, so a
    # span cut from it can splice two columns together and must not be
    # quoted. The distinction matters to extract_text: None means "this
    # backend resolves no reading order", where an empty list would mean
    # "it did, and this document has no prose in it".
    try:
        subprocess.run(
            ["pdftotext", "-layout", pdf_path, str(out_path)],
            check=True,
            capture_output=True,
            text=True,
            # The one backend where a hang can genuinely be stopped:
            # this is a hard kill of an external process, not the
            # cooperative between-stages check docling offers.
            timeout=config.PARSER_DOCUMENT_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        error = ExtractionError(
            f"pdftotext exceeded the {config.PARSER_DOCUMENT_TIMEOUT}s "
            "[parser].document_timeout and was killed"
        )
        # Marked, not just worded: sync reports timeouts separately from
        # the PDFs a backend genuinely cannot read, and reading that back
        # out of the message would tie the report to this string.
        error.timed_out = True
        raise error from exc
    except subprocess.CalledProcessError as exc:
        raise ExtractionError(exc.stderr or str(exc)) from exc


def _extract_docling(pdf_path: str, out_path: Path, threads: int | None = None) -> list[dict]:
    """Writes Markdown, and returns the passages that Markdown can't carry.

    `result.document` carries per-item page numbers, bounding boxes and
    semantic labels -- 336 of 336 text items on a real 17-page paper, per
    docs/CITATION-PROVENANCE.md. `export_to_markdown()` keeps the reading
    order and drops the rest. One plain-text file per citekey is still the
    right shape for what the corpus layer owes its callers -- BM25 ranks
    text, not boxes -- so the structure leaves by a second door instead:
    the returned records become `content/parsed/<citekey>.passages.json`,
    rung 2 of `chitragupta/passages.py`'s ladder, and the caller (`extract_text`)
    writes them.

    Two things make that work, and both are one keyword each:

    `page_break_placeholder="\\f"` puts form feeds where the pages were, so
    this backend's output has the same shape as `pdftotext`'s and every
    consumer that splits on them -- the passage ladder's page-level rung,
    `chitragupta/review/verbatim_check.py` -- reports a real page instead of p.1.
    Docling emits a break *between* consecutive pages that carry items and
    none before the first, so splitting yields 1-based page numbers
    directly. A page carrying no items at all contributes no break and so
    shifts the pages after it; the sidecar is unaffected, because it
    records each item's own `page_no` rather than counting separators.
    `\\f` is whitespace, so BM25 tokenisation and `run_together_ratio` see
    exactly what they saw before.

    chitragupta/enrich/docling_parse.py is the other consumer of this library, and
    is still not made redundant by this one: it parses the PDF a second
    time under its own OCR and figure settings, and writes structured
    Markdown plus figure records that this one does not.
    """
    converter = _docling_converter(threads)
    try:
        result = converter.convert(pdf_path)
        check_docling_status(result)
    except ExtractionError:
        raise
    except Exception as exc:  # docling has no narrower common exception
        # type to catch (same reporting shape as
        # chitragupta/enrich/docling_parse.py's own parse_corpus loop).
        # Not ruff's BLE001: this block re-raises via `raise ... from exc`
        # below, which the rule's own blind-except definition exempts.
        #
        # The converter is deliberately NOT discarded here: the failure
        # is in this one PDF, not in the models, and throwing it away
        # would charge the next document a full reload for its neighbour's
        # bad luck.
        if is_cuda_oom(exc) and worker_device() != "cpu":
            # Recursion is bounded by that guard: the retry runs with
            # worker_device() == "cpu", where this branch cannot be taken
            # again. `None` is included deliberately -- it means docling's
            # own AUTO resolution, which is cuda:0, so a serial run has
            # the same card to fall off.
            _demote_to_cpu()
            return _extract_docling(pdf_path, out_path, threads)
        error = ExtractionError(str(exc))
        if is_cuda_oom(exc):
            # Caused by the machine at this moment, not by the PDF, so it
            # must come back next run rather than being written off as a
            # document that cannot be parsed.
            error.transient = True
        raise error from exc
    out_path.write_text(
        result.document.export_to_markdown(page_break_placeholder="\f"),
        encoding="utf-8",
    )
    return passages.passage_records(result.document)

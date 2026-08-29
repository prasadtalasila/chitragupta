"""The process-pool leg of Docling parsing: building the executor, the
per-worker converter cache, and the pickled unit of work a spawned
worker actually runs.

Split from `chitragupta/enrich/docling_parse.py` (#441). Unlike this
batch's other docling_parse splits, this one has a genuine dependency
back on it: `parse_one` and `_worker_converter` need `parse_doc` and
`_build_converter`, the two functions that stayed there. A plain
top-level `from chitragupta.enrich.docling_parse import ...` would
create an ordinary circular import -- `docling_parse.py` imports this
module (for `_executor_for`/`_parse_with_pool`), so importing either
module first would find the other only partially initialised.

Both imports are therefore local to the function that needs them,
deferred until the function actually runs -- by which point
`docling_parse.py`'s own top level has always already finished, in
both the process that calls `_parse_with_pool` directly and the worker
that unpickles `parse_one` and calls it fresh. `parse_one` has a second,
independent reason to keep this shape: it is pickled and re-run in a
spawned worker process, so it must stay a plain module-level function
with a fixed one-tuple signature -- passing `parse_doc` in as a
parameter, the way `chitragupta/enrich/_scope.py` passes `_say`, is not
an option here.
"""

import logging
import os
from concurrent.futures import ProcessPoolExecutor
from typing import Any

from chitragupta import config, logging_setup, pdf_text
from chitragupta.enrich._docling_cache import _save_cache
from chitragupta.enrich.corpus import CorpusDoc

logger = logging.getLogger("chitragupta.enrich.docling_parse")


class _LazyConverter:
    """One converter for the whole corpus, built on first actual use.

    Two things at once, both of which matter on a 501-PDF corpus:
    building it once means Docling's layout/table/OCR models load once
    rather than per document (16.5s of measured cold start each time),
    and deferring the build means a fully-cached run -- the common case
    for a re-run of `enrich.py --stages docling` -- never loads
    them at all.
    """

    def __init__(self) -> None:
        self._converter = None

    def convert(self, pdf_path) -> Any:
        if self._converter is None:
            from chitragupta.enrich.docling_parse import _build_converter

            self._converter = _build_converter()
        return self._converter.convert(pdf_path)


# One converter per worker *process*, not per document. A pool worker
# handles many documents over its life, and DocumentConverter keeps its
# initialized_pipelines cache on the instance -- so building one per
# document would reload Docling's layout, table and OCR models for every
# file, which is exactly the cost the serial path stopped paying in
# v0.12.0. Keyed on everything that changes what a converter *is*, so a
# changed setting can't be served a stale one.
_WORKER_CONVERTER = None
_WORKER_CONVERTER_KEY = None


def _worker_converter(threads: int | None) -> Any:
    global _WORKER_CONVERTER, _WORKER_CONVERTER_KEY
    from chitragupta.enrich.docling_parse import _build_converter

    key = (
        threads,
        pdf_text.worker_device(),
        config.PARSER_OCR,
        config.DOCLING_IMAGES,
        config.DOCLING_IMAGE_SCALE,
        config.PARSER_DOCUMENT_TIMEOUT,
    )
    if _WORKER_CONVERTER is None or _WORKER_CONVERTER_KEY != key:
        _WORKER_CONVERTER = _build_converter(threads)
        _WORKER_CONVERTER_KEY = key
    return _WORKER_CONVERTER


def _reset_worker_converter() -> None:
    """Test hook -- module state otherwise leaks between tests."""
    global _WORKER_CONVERTER, _WORKER_CONVERTER_KEY
    _WORKER_CONVERTER = None
    _WORKER_CONVERTER_KEY = None


def parse_one(job: tuple) -> tuple:
    """One worker's unit of work: (doc, threads) in, (citekey, status,
    fingerprint) out.

    Module-level and exception-free by design -- both the argument and
    the result have to survive pickling to and from a worker process, and
    an arbitrary Docling exception may not. The fingerprint travels back
    so the *parent* owns every cache write, the same way chitragupta/sync.py
    keeps every ledger write on the main process.
    """
    from chitragupta.enrich.docling_parse import _fingerprint, parse_doc

    doc, threads = job
    try:
        out_path = parse_doc(doc, cache={}, converter=_worker_converter(threads))
        return doc.citekey, f"ok: {out_path}", _fingerprint(doc)
    except Exception as exc:  # noqa: BLE001  # report per-doc, don't abort the batch
        return doc.citekey, f"error: {exc}", None


def _executor_for(workers: int) -> ProcessPoolExecutor:
    """This module's docling pool, built by the one place that knows how
    (pdf_text.docling_process_pool -- see its docstring for why the pool
    itself moved there, in #290). Kept as its own named function, rather
    than calling that helper inline at the one call site below, purely as
    the test seam `tests/test_enrich_docling_parse.py` already
    monkeypatches.
    """
    return pdf_text.docling_process_pool(
        workers, lambda msg: logging_setup.say(logger, msg, level=logging.WARNING)
    )


def _pdf_size(path: str | None) -> int:
    """Bytes, or 0 if it can't be stat'd -- only used to order work."""
    try:
        return os.path.getsize(path)
    except (OSError, TypeError):
        return 0


def _parse_with_pool(
    docs: list[CorpusDoc],
    pending: list[CorpusDoc],
    cache: dict,
    status: dict[str, str],
    workers: int,
) -> None:
    """parse_corpus's parallel leg: the cached docs adopted serially, the
    rest fanned out to a process pool. Mutates `status` and `cache` in
    place -- the caller owns saving the cache, except on interrupt, where
    this saves before re-raising so finished work survives the Ctrl+C.
    """
    from chitragupta.enrich.docling_parse import parse_doc

    threads = pdf_text.docling_threads(workers)
    # Biggest-file-first, same LPT reasoning as chitragupta/sync.py: one
    # 675-page document in this corpus would otherwise define the
    # wall clock all by itself if it were picked up last.
    jobs = [(d, threads) for d in sorted(pending, key=lambda d: -_pdf_size(d.pdf_path))]
    cached = [d for d in docs if d not in pending]
    for doc in cached:
        try:
            status[doc.citekey] = f"ok: {parse_doc(doc, cache=cache)}"
        except Exception as exc:  # noqa: BLE001 -- as below
            status[doc.citekey] = f"error: {exc}"
    # Explicit shutdown rather than `with`, for the reason chitragupta/sync.py
    # gives: the context manager waits for every queued job, so
    # Ctrl+C would drain the whole corpus before exiting.
    executor = _executor_for(workers)
    done = 0
    try:
        for citekey, doc_status, fingerprint in executor.map(parse_one, jobs):
            status[citekey] = doc_status
            if fingerprint is not None:
                cache[citekey] = fingerprint
            done += 1
            logging_setup.say(logger, f"  [{done}/{len(jobs)}] {citekey}")
    except KeyboardInterrupt:
        executor.shutdown(wait=False, cancel_futures=True)
        pdf_text.terminate_workers(executor)
        logging_setup.say(
            logger,
            f"\n  interrupted after {done}/{len(jobs)} document(s) -- "
            "parsed output is kept; re-run to continue.",
            level=logging.WARNING,
        )
        _save_cache(cache)
        raise
    finally:
        executor.shutdown(wait=False)

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
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
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

    That 16.5s no longer reproduces: on docling 2.117.0 a converter
    rebuilt per PDF costs 0.7% more than one reused for the whole run
    (bench/RESULTS.md, 2026-08-30). **Keep the reuse anyway** -- the
    second benefit above is unaffected, and the cost is a property of
    the installed docling rather than of this code.
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
    cache) out.

    Module-level and exception-free by design -- both the argument and
    the result have to survive pickling to and from a worker process, and
    an arbitrary Docling exception may not. The cache dict travels back
    rather than a fingerprint computed separately here, so the *parent*
    owns every cache write (the same way chitragupta/sync.py keeps every
    ledger write on the main process) using the fingerprint parse_doc
    itself recorded *before* it converted the PDF -- stat-before-parse,
    the same order the serial path uses, rather than fingerprinting after
    conversion where a PDF replaced mid-parse would be recorded against
    text read from the old bytes. Empty on a failed parse, since parse_doc
    only writes into it once conversion succeeds.
    """
    from chitragupta.enrich.docling_parse import parse_doc

    doc, threads = job
    cache: dict = {}
    try:
        out_path = parse_doc(doc, cache=cache, converter=_worker_converter(threads))
        return doc.citekey, f"ok: {out_path}", cache
    except Exception as exc:  # noqa: BLE001  # report per-doc, don't abort the batch
        return doc.citekey, f"error: {exc}", cache


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


def _adopt_cached(
    docs: list[CorpusDoc], pending: list[CorpusDoc], cache: dict, status: dict[str, str]
) -> None:
    """The already-cached / corpus-reused docs, parsed serially in the
    parent rather than sent to a worker. Filtered by a citekey set, not
    `d not in pending` -- that would compare whole dataclasses against
    every pending doc for every doc in the corpus, the quadratic scan
    `chitragupta.enrich.docling_parse.parse_corpus`'s own `reusable` set
    exists to avoid.
    """
    from chitragupta.enrich.docling_parse import _failure, parse_doc

    pending_keys = {d.citekey for d in pending}
    for doc in docs:
        if doc.citekey in pending_keys:
            continue
        try:
            status[doc.citekey] = f"ok: {parse_doc(doc, cache=cache)}"
        except Exception as exc:  # noqa: BLE001 -- as below
            # _failure, not `f"error: {exc}"`: a PDF-less document lands
            # here rather than in the pool (`pending` filters it out), so
            # this is the parallel leg's copy of the same classification
            # the serial loop makes -- see its comment at #586.
            status[doc.citekey] = _failure(doc, exc)


def _submit_jobs(executor, jobs: list[tuple]) -> tuple[list, Exception | None]:
    """Submit one job at a time rather than in a single list
    comprehension, so a `BrokenProcessPool` raised partway through a
    batch doesn't discard the futures already submitted -- those may
    already be running or finished, and `_drain` below must still
    collect them instead of leaking them to the dead executor.
    """
    futures = []
    broken = None
    for job in jobs:
        try:
            futures.append(executor.submit(parse_one, job))
        except BrokenProcessPool as pool_exc:
            broken = pool_exc
            break
    return futures, broken


def _drain(executor, jobs: list[tuple], cache: dict, status: dict[str, str]) -> Exception | None:
    """Submit every job and collect (citekey, status, cache) as workers
    finish, returning the pool's break (if any) for the caller to account
    for. Mutates `status` and `cache` in place.

    submit() plus as_completed() rather than map(): map yields in *input*
    order, so a biggest-first schedule (LPT, chitragupta/sync.py's own
    reasoning) would print nothing until the largest document lands even
    though smaller ones already finished -- the killed-at-399-of-501
    convention (issue #50) all over again.

    Each landed fingerprint is folded into `cache` and saved immediately,
    not left to a trailing `finally`: pdf_text.interrupt_guard's SIGINT
    handler calls os._exit without unwinding this function at all, so the
    cache has to already be on disk by the time that fires -- the same
    reason its own docstring gives for why chitragupta/sync.py's ledger
    commits synchronously per document rather than once at the end. A
    failed doc's `worker_cache` is empty (parse_one only writes into it
    once conversion succeeds), so that save is skipped rather than
    rewriting the same file for nothing.

    Not `with executor`: the context manager waits for every queued job,
    so Ctrl+C would drain the whole corpus before exiting.

    Not shared with chitragupta/sync_pool.py's own `_drain_pool` despite
    the parallel shape, for the same reason `_executor_for` above keeps
    its own copy: `chitragupta/enrich/` must not depend on the core
    entry point.
    """
    broken = None
    done = 0
    try:
        with pdf_text.interrupt_guard(executor, lambda: f"{done}/{len(jobs)} document(s) parsed"):
            futures, broken = _submit_jobs(executor, jobs)
            for future in as_completed(futures):
                try:
                    citekey, doc_status, worker_cache = future.result()
                except BrokenProcessPool as pool_exc:
                    broken = pool_exc
                    continue
                status[citekey] = doc_status
                if worker_cache:
                    cache.update(worker_cache)
                    _save_cache(cache)
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
        raise
    finally:
        executor.shutdown(wait=False)
    return broken


def _account_for_unfinished(jobs: list[tuple], status: dict[str, str], broken) -> None:
    """Fill in a failure for every job _drain didn't land a result for.

    A worker killed outright (the OOM killer is the realistic cause)
    takes the whole pool with it, and every future still in flight --
    reported once here rather than once per still-in-flight future, and
    against the documents that didn't get parsed rather than letting them
    silently vanish from `status` (#509 is what a silent drop like that
    would be).
    """
    if broken is not None:
        logging_setup.say(
            logger,
            f"WARNING a parse worker died ({broken}) -- the documents it "
            "had not finished are reported as failures below. A lower "
            "[parser].workers is the usual fix.",
            level=logging.WARNING,
        )
    for doc, _threads in jobs:
        if doc.citekey not in status:
            status[doc.citekey] = "error: parse worker died before this document was parsed"


def _parse_with_pool(
    docs: list[CorpusDoc],
    pending: list[CorpusDoc],
    cache: dict,
    status: dict[str, str],
    workers: int,
) -> None:
    """parse_corpus's parallel leg: the cached docs adopted serially, the
    rest fanned out to a process pool. Mutates `status` and `cache` in
    place.
    """
    threads = pdf_text.docling_threads(workers)
    # Biggest-file-first, same LPT reasoning as chitragupta/sync.py: one
    # 675-page document in this corpus would otherwise define the
    # wall clock all by itself if it were picked up last.
    jobs = [(d, threads) for d in sorted(pending, key=lambda d: -_pdf_size(d.pdf_path))]
    _adopt_cached(docs, pending, cache, status)
    executor = _executor_for(workers)
    broken = _drain(executor, jobs, cache, status)
    _account_for_unfinished(jobs, status, broken)

"""The process-pool leg of Docling parsing: building the executor, the
per-worker converter cache, and the pickled unit of work a spawned
worker actually runs.

`parse_doc` and `_build_converter` are imported locally inside the
functions that need them: `docling_parse.py` imports this module, so a
top-level import would be circular. `parse_one` is pickled into spawned
workers, so it must stay a plain module-level one-tuple function.
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

    Deferring means a fully-cached re-run never loads the models. The
    measured 16.5s per-build cost no longer reproduces on docling 2.117.0
    (0.7%, bench/RESULTS.md 2026-08-30); **keep the reuse anyway**, as
    that cost belongs to the installed docling.
    """

    def __init__(self) -> None:
        self._converter = None

    def convert(self, pdf_path) -> Any:
        if self._converter is None:
            from chitragupta.enrich.docling_parse import _build_converter

            self._converter = _build_converter()
        return self._converter.convert(pdf_path)


# One converter per worker *process*, not per document: the pipeline
# cache lives on the instance, so per-document builds reload every model.
# Keyed on everything that changes what a converter *is*.
_WORKER_CONVERTER = None
_WORKER_CONVERTER_KEY = None


def _worker_converter(threads: int | None) -> Any:
    global _WORKER_CONVERTER, _WORKER_CONVERTER_KEY
    from chitragupta.enrich.docling_parse import _build_converter

    # Not the image settings: since #600 the converter generates no
    # bitmaps (`_docling_crops` applies the scale); `_docling_cache`
    # still records both because they change the outputs.
    key = (
        threads,
        pdf_text.worker_device(),
        config.PARSER_OCR,
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

    Module-level and exception-free so both sides pickle. The cache dict
    travels back so the *parent* owns every cache write, using the
    fingerprint parse_doc took *before* converting (a PDF replaced
    mid-parse isn't recorded against old text). Empty on a failed parse.
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
    """This module's docling pool, via pdf_text.docling_process_pool (#290).
    Kept as the seam `tests/test_enrich_docling_parse.py` monkeypatches.
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
    `d not in pending`, to avoid a quadratic dataclass scan.
    """
    from chitragupta.enrich.docling_parse import _failure_status, parse_doc

    pending_keys = {d.citekey for d in pending}
    for doc in docs:
        if doc.citekey in pending_keys:
            continue
        try:
            status[doc.citekey] = f"ok: {parse_doc(doc, cache=cache)}"
        except Exception as exc:  # noqa: BLE001 -- as below
            # _failure_status, not `f"error: {exc}"`: a PDF-less document
            # lands here, so this mirrors the serial loop (#586, NO_PDF_SKIP).
            status[doc.citekey] = _failure_status(doc, exc)


def _submit_jobs(executor, jobs: list[tuple]) -> tuple[list, Exception | None]:
    """Submit one job at a time, so a `BrokenProcessPool` partway through
    doesn't discard futures already submitted, which `_drain` must collect.
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

    as_completed(), not map(): map yields in input order, so biggest-first
    scheduling would print nothing until the largest lands (#50). Each
    fingerprint is saved immediately, since interrupt_guard's os._exit
    skips any `finally`. Not `with executor`: it would drain the whole
    corpus on Ctrl+C. Not shared with chitragupta/sync_pool.py's
    `_drain_pool`: enrich must not depend on the core entry point.
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
        # terminate_workers before shutdown: shutdown() sets
        # executor._processes = None, leaving nothing to kill, so a wedged
        # worker hung interpreter exit (#698).
        pdf_text.terminate_workers(executor)
        executor.shutdown(wait=False, cancel_futures=True)
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


# Pool builds before giving up on what is left: each rebuild reloads the
# models, and a BrokenProcessPool doesn't name the fatal PDF, so an
# unbounded loop feeds it to fresh pools forever (#584).
_MAX_POOL_REBUILDS = 2


def _account_for_unfinished(jobs: list[tuple], status: dict[str, str], broken) -> None:
    """Fill in a failure for every job no pool landed a result for.

    A killed worker (realistically the OOM killer) takes the pool down;
    report it once, against the unparsed documents, rather than letting
    them vanish from `status` (#509).
    """
    from chitragupta.enrich.docling_parse import POOL_DEATH_ERROR

    if broken is not None:
        # States the policy, not a count of attempts this run spent.
        logging_setup.say(
            logger,
            f"WARNING a parse worker died ({broken}) -- the pool is rebuilt up to "
            f"{_MAX_POOL_REBUILDS} more time(s), narrower and smallest-first; what "
            "still did not parse is below. A lower [parser].workers is the usual fix.",
            level=logging.WARNING,
        )
    # `jobs` is only what is left after the last rebuild (#584), so no
    # `citekey not in status` guard is needed here.
    for doc, _threads in jobs:
        status[doc.citekey] = POOL_DEATH_ERROR


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
    # Biggest-file-first (LPT, as chitragupta/sync.py): a 675-page document
    # picked up last would define the wall clock alone.
    jobs = [(d, threads) for d in sorted(pending, key=lambda d: -_pdf_size(d.pdf_path))]
    _adopt_cached(docs, pending, cache, status)
    remaining = jobs
    for attempt in range(_MAX_POOL_REBUILDS + 1):
        landed_before = len(status)
        broken = _drain(_executor_for(workers), remaining, cache, status)
        remaining = [job for job in remaining if job[0].citekey not in status]
        # `attempt and` exempts the first round, which legitimately lands
        # nothing if the largest document kills it; a *rebuilt* pool that
        # lands nothing will do so again.
        if broken is None or not remaining or (attempt and len(status) == landed_before):
            break
        # Smallest-first from here: the likely killer was submitted first
        # (the largest), so the rebuilt pool banks everything else first.
        remaining.reverse()
        # Narrower too, since memory pressure is the realistic cause;
        # bottoms out at 1. `threads` stays as computed: sizing is #585's.
        workers = max(1, workers // 2)
    _account_for_unfinished(remaining, status, broken)

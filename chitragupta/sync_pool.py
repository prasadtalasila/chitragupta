"""The parse-dispatch engine: fan a batch of documents out across a
worker pool and collect each one's (out_path, exception) result (#441).

No ledger or bib awareness. Tests patch `_executor_for` and
`_parse_serial` here directly: a real process pool runs in a child
interpreter where monkeypatches don't exist.
"""

import logging
import os
from collections.abc import Callable, Iterator
from concurrent.futures import (
    FIRST_COMPLETED,
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    wait,
)
from concurrent.futures.process import BrokenProcessPool

from chitragupta import config, pdf_text

logger = logging.getLogger("chitragupta.sync")

# The (citekey, out_path, exception) triple both parse paths yield.
_ParseResult = tuple[str, str | None, Exception | None]

# Called the moment a result lands; `sync` writes the ledger row here
# (#961), so Ctrl+C or a pool failure keeps every finished parse.
OnLanded = Callable[[str, str | None, Exception | None], None]


def _executor_for(workers: int) -> ProcessPoolExecutor | ThreadPoolExecutor:
    """Processes for docling, threads for pdftotext.

    `pdftotext` is a subprocess that releases the GIL, so threads suffice;
    docling holds the GIL, so it needs processes
    (`pdf_text.docling_process_pool`, shared with `enrich/docling_parse.py`).
    """
    if config.PARSER == "docling":
        return pdf_text.docling_process_pool(workers, logger.warning)
    return ThreadPoolExecutor(max_workers=workers)


def _pdf_size(path: str) -> int:
    """Bytes, or 0 if the file can't be stat'd; only used to sort, and the
    parse reports the real error."""
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _as_they_land(futures, executor, stalled) -> Iterator[Future]:
    """Yield futures as they complete, giving up if the whole pool goes
    silent for config.PARSER_STALL_TIMEOUT.

    `wait(FIRST_COMPLETED)`, not `as_completed(timeout=)`, which measures
    total time: the signal is silence across the pool, since the slowest
    legitimate document takes 246s. Workers are terminated on the way out,
    or they would write parses for documents already reported failed and
    hold GPU memory. The unfinished are retried next run.
    """
    # A warning at half the budget, then the kill: biggest-first scheduling
    # makes a long first gap normal on a slow host, and an unwarned kill
    # would repeat every run.
    pending = set(futures)
    half = config.PARSER_STALL_TIMEOUT / 2 if config.PARSER_STALL_TIMEOUT else None
    warned = False
    while pending:
        done, pending = wait(pending, timeout=half, return_when=FIRST_COMPLETED)
        if not done and not warned and half is not None:
            warned = True
            logger.warning(
                "WARNING no completions in %.0fs; giving up at %.0fs "
                "([parser].stall_timeout). %d document(s) still running -- if "
                "this host is simply slow (CPU-only, OCR on, large scans), "
                "raise or disable that setting rather than letting the run be "
                "abandoned.",
                half,
                config.PARSER_STALL_TIMEOUT,
                len(pending),
            )
            continue
        if done:
            warned = False
        if not done:
            stalled.append(True)
            # terminate_workers before shutdown: shutdown() nulls
            # executor._processes even with wait=False, leaving nothing to
            # signal, and the wedged worker then hangs the atexit join
            # (issue #698; bench/bench_pool_rebuild.py --with-stall-arm).
            # cancel_futures stops the thread pool's queue, which
            # terminate_workers cannot reach.
            pdf_text.terminate_workers(executor)
            executor.shutdown(wait=False, cancel_futures=True)
            logger.warning(
                "WARNING no document finished in %ss ([parser].stall_timeout) -- "
                "giving up on the %d still outstanding. They are reported as "
                "failures below and retried on the next run.",
                config.PARSER_STALL_TIMEOUT,
                len(pending),
            )
            return
        yield from done


def _parse_serial(refs, on_landed: OnLanded) -> Iterator[_ParseResult]:
    """The path for [parser].workers == 1: no executor, no pickling, and
    `pdf_text.extract_text` called exactly as before."""
    for ref in refs:
        try:
            result = ref.citekey, str(pdf_text.extract_text(ref.pdf_path, ref.citekey)), None
        except (pdf_text.ExtractionError, pdf_text.BackendUnavailable) as exc:
            result = ref.citekey, None, exc
        except Exception as exc:  # noqa: BLE001 -- see pdf_text.document_failure
            result = ref.citekey, None, pdf_text.document_failure(exc)
        on_landed(*result)
        yield result


def _drain_pool(executor, jobs, stalled, on_landed: OnLanded) -> tuple[dict, Exception | None]:
    """Submit every job and collect (out_path, exc) per citekey as workers
    finish. Returns what was collected plus the pool's break, if any.

    Not `map()`, which yields in input order and would lose finished work
    to a break. Not `with executor`, whose shutdown(wait=True) made Ctrl+C
    drain the whole queue on a 501-document corpus. A future raising
    something other than a broken pool is that document's failure
    (`pdf_text.document_failure`), not the batch's.
    """
    results = {}
    broken = None
    done = 0
    try:
        with pdf_text.interrupt_guard(executor, lambda: f"{done}/{len(jobs)} document(s) parsed"):
            futures = {executor.submit(pdf_text.extract_one, job): job[1] for job in jobs}
            for future in _as_they_land(futures, executor, stalled):
                try:
                    citekey, out_path, exc = future.result()
                except BrokenProcessPool as pool_exc:
                    broken = pool_exc
                    continue
                except Exception as unexpected:  # noqa: BLE001 -- see the docstring
                    citekey, out_path = futures[future], None
                    exc = pdf_text.document_failure(unexpected)
                results[citekey] = (out_path, exc)
                on_landed(citekey, out_path, exc)
                done += 1
                # Progress on stderr, so stdout stays diffable; otherwise a
                # parallel run looks stuck for tens of minutes.
                logger.info("[%d/%d] %s", done, len(jobs), citekey)
    except BrokenProcessPool as pool_exc:
        # submit() itself raises once the pool is already known-broken.
        broken = pool_exc
    except KeyboardInterrupt:
        # terminate_workers before shutdown (see _as_they_land, #698);
        # cancel_futures drops unstarted jobs, and finished ones already
        # reached `on_landed`.
        pdf_text.terminate_workers(executor)
        executor.shutdown(wait=False, cancel_futures=True)
        logger.warning(
            "interrupted after %d/%d document(s) -- work already finished "
            "is kept; re-run to continue.",
            done,
            len(jobs),
        )
        raise
    finally:
        executor.shutdown(wait=False)
    return results, broken


def _account_for_unfinished(refs, results: dict, broken, stalled, on_landed: OnLanded) -> None:
    """Warn on a broken pool, then land a transient failure for every ref
    without a result, mutating `results`. Transient, since they never got
    a fair attempt and must be retried.
    """
    if broken is not None:
        # A worker killed outright (OOM) takes the pool with it; reported
        # per document, so the run still writes its ledger and exits nonzero.
        logger.warning(
            "WARNING a parse worker died (%s) -- the documents it had not "
            "finished are reported as failures below. A lower "
            "[parser].workers is the usual fix.",
            broken,
        )
    unfinished = (
        "gave up waiting: no document finished within "
        f"{config.PARSER_STALL_TIMEOUT}s ([parser].stall_timeout)"
        if stalled
        else "parse worker died before this document was parsed"
    )
    for ref in refs:
        if ref.citekey not in results:
            error = pdf_text.ExtractionError(unfinished)
            error.transient = True
            results[ref.citekey] = (None, error)
            on_landed(ref.citekey, None, error)


def _parse_parallel(
    refs, workers: int, threads: int | None, on_landed: OnLanded
) -> Iterator[_ParseResult]:
    """Same triples as _parse_serial, produced by `workers` at once.

    Submitted biggest-file-first (LPT): one 675-page document is 5% of the
    corpus's pages. File size, as counting pages needs a PDF library.
    """
    jobs = [
        (r.pdf_path, r.citekey, threads) for r in sorted(refs, key=lambda r: -_pdf_size(r.pdf_path))
    ]
    stalled = []
    executor = _executor_for(workers)
    results, broken = _drain_pool(executor, jobs, stalled, on_landed)
    _account_for_unfinished(refs, results, broken, stalled, on_landed)
    return ((ref.citekey, *results[ref.citekey]) for ref in refs)

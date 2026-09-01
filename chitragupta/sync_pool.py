"""The parse-dispatch engine: fan a batch of documents out across a
worker pool and collect each one's (out_path, exception) result.

Split from `chitragupta/sync.py` (#441): this is the pool-management
half -- executor choice, biggest-file-first scheduling, the
stall-timeout watchdog and the broken-pool/interrupt recovery -- with
no ledger or bib-file awareness of its own. `_parse_parallel`'s three
arguments (`refs`, `workers`, `threads`) are exactly what a caller
already has; nothing here reads `chitragupta.ledger` or
`chitragupta.bib_reader`.

This is also the seam the test suite substitutes: `_executor_for` and
`_parse_serial` are patched directly (`monkeypatch.setattr(sync_pool,
...)`), not through `chitragupta.sync`, because a real
`ProcessPoolExecutor` runs its work in a child interpreter where the
test process's monkeypatches don't exist -- the same reason
`chitragupta/enrich/_docling_pool.py` is its own module.
"""

import logging
import os
from collections.abc import Iterator
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

# The (citekey, out_path, exception) triple pdf_text.extract_one produces,
# yielded back out by both _parse_serial and _parse_parallel.
_ParseResult = tuple[str, str | None, Exception | None]


def _executor_for(workers: int) -> ProcessPoolExecutor | ThreadPoolExecutor:
    """Processes for docling, threads for pdftotext.

    The two backends want opposite things, so this is deliberately
    backend-conditional rather than one pool type for both. `pdftotext`
    is an external subprocess that releases the GIL while it runs, so a
    ThreadPoolExecutor already gets full OS-level concurrency and a
    process pool would only add pickling and spawn cost on top. `docling`
    runs in-process and holds the GIL, so threads would serialise exactly
    the work we are trying to overlap.

    The docling pool itself is pdf_text.docling_process_pool -- shared with
    chitragupta/enrich/docling_parse.py's own docling-only pool (see its
    docstring for why the GPU/start-method reasoning lives there now
    rather than duplicated here).

    Also the seam the tests substitute: a real ProcessPoolExecutor runs
    its work in a child interpreter, where the test process's
    monkeypatches don't exist.
    """
    if config.PARSER == "docling":
        return pdf_text.docling_process_pool(workers, logger.warning)
    return ThreadPoolExecutor(max_workers=workers)


def _pdf_size(path: str) -> int:
    """Bytes, or 0 if the file can't be stat'd.

    Only ever used to sort work biggest-first, so a file that vanished
    between bib resolution and here just sorts last -- the parse will
    report the real error a moment later, which is the better place for
    it.
    """
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _as_they_land(futures, executor, stalled) -> Iterator[Future]:
    """Yield futures as they complete, giving up if the whole pool goes
    silent for config.PARSER_STALL_TIMEOUT.

    `wait(..., FIRST_COMPLETED)` rather than `as_completed(timeout=...)`:
    as_completed measures its timeout from the original call, i.e. total
    elapsed, so on a long corpus it would fire on a perfectly healthy
    run. What is wanted is the gap *between* completions -- with several
    workers those arrive constantly, so silence across the entire pool is
    what distinguishes a hung worker from a merely slow document. That
    distinction matters because the slowest legitimate document in this
    corpus takes 246s, and no per-document deadline can be both above
    that and a useful hang detector.

    The workers are terminated on the way out, not merely abandoned.
    Without that, in-flight jobs keep running and write
    content/parsed/<citekey>.txt for documents this run has already
    reported as failed -- a file on disk contradicting the ledger -- and
    the processes stay alive holding GPU memory.

    Giving up here is not a data loss: the caller reports the
    unfinished documents as failures, and since v1.2.0 a failed document
    is retried on the next run rather than dropped.
    """
    # Half the budget, twice: a warning at the midpoint, then the kill.
    # The warning matters because the schedule invites a long first gap
    # -- submission is biggest-file-first, so at pool start every worker
    # is on the largest documents at once. On a slow host that gap is the
    # schedule working, not a hang, and a kill without warning would
    # repeat every run (stall-killed documents are retried identically),
    # leaving a legitimate configuration unable to ever finish.
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
            # cancel_futures drops every job the pool has not yet started
            # (thread or process). terminate_workers is the other half:
            # it kills docling's in-flight *processes*, but is a no-op for
            # the pdftotext ThreadPoolExecutor, which has no `_processes`
            # to reach -- without this cancel, its queue keeps draining
            # after this run has already reported those citekeys failed,
            # writing content/parsed/<citekey>.txt for them behind the
            # ledger's back.
            executor.shutdown(wait=False, cancel_futures=True)
            pdf_text.terminate_workers(executor)
            logger.warning(
                "WARNING no document finished in %ss ([parser].stall_timeout) -- "
                "giving up on the %d still outstanding. They are reported as "
                "failures below and retried on the next run.",
                config.PARSER_STALL_TIMEOUT,
                len(pending),
            )
            return
        yield from done


def _parse_serial(refs) -> Iterator[_ParseResult]:
    """The historical path, taken whenever [parser].workers resolves to 1.

    Deliberately not "a pool with one worker": no executor, no pickling,
    no subprocess, and pdf_text.extract_text is called with exactly the
    arguments it always was.
    """
    for ref in refs:
        try:
            yield ref.citekey, str(pdf_text.extract_text(ref.pdf_path, ref.citekey)), None
        except (pdf_text.ExtractionError, pdf_text.BackendUnavailable) as exc:
            yield ref.citekey, None, exc


def _drain_pool(executor, jobs, stalled) -> tuple[dict, Exception | None]:
    """The result-draining loop: submit every job and collect (out_path,
    exc) per citekey as workers finish. Returns whatever was collected
    before an early exit alongside the pool's break, if any -- the caller
    reports both, rather than either being lost to an interrupt or a
    broken pool.

    submit() plus _as_they_land() rather than map(): map yields in *input*
    order, so a pool that breaks while the first (largest) job is still
    running would raise before yielding the smaller jobs that had
    already finished, throwing away real work and reporting parsed
    documents as failures. _as_they_land records each result at the
    moment it lands, so a broken pool costs only what was actually in
    flight.

    Not `with executor`: the context manager's __exit__ calls
    shutdown(wait=True), and every job is submitted up front, so a
    KeyboardInterrupt would drain the *entire* remaining queue before
    exiting. Reported from real use on a 501-document corpus -- Ctrl+C
    "took forever to exit" and emitted docling teardown tracebacks from
    workers still being fed. Shutdown is therefore explicit below, with
    cancel_futures on the interrupt path.
    """
    results = {}
    broken = None
    done = 0
    try:
        with pdf_text.interrupt_guard(executor, lambda: f"{done}/{len(jobs)} document(s) parsed"):
            futures = [executor.submit(pdf_text.extract_one, job) for job in jobs]
            for future in _as_they_land(futures, executor, stalled):
                try:
                    citekey, out_path, exc = future.result()
                except BrokenProcessPool as pool_exc:
                    broken = pool_exc
                    continue
                results[citekey] = (out_path, exc)
                done += 1
                # Live progress, on stderr so stdout stays in
                # bibliography order and diffable between runs. Without
                # it a parallel run over a real corpus prints nothing for
                # tens of minutes, which is indistinguishable from being
                # stuck -- especially under docling's own OCR chatter.
                logger.info("[%d/%d] %s", done, len(jobs), citekey)
    except BrokenProcessPool as pool_exc:
        # submit() itself raises once the pool is already known-broken.
        broken = pool_exc
    except KeyboardInterrupt:
        # cancel_futures drops everything not yet started; wait=False
        # means we don't block on the handful still running. Whatever
        # finished is still recorded by the caller, so an interrupted run
        # keeps its work rather than discarding it.
        executor.shutdown(wait=False, cancel_futures=True)
        pdf_text.terminate_workers(executor)
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


def _account_for_unfinished(refs, results: dict, broken, stalled) -> None:
    """The failure accounting: warn on a broken pool, then fill in a
    transient failure for every ref _drain_pool didn't land a result for.
    Mutates `results` in place.

    Marked transient: these documents were never given a fair attempt,
    so they must come back next run. A failure the *backend* returned
    for a specific PDF is deterministic and stays that way.
    """
    if broken is not None:
        # A worker killed outright (the OOM killer is the realistic
        # cause) takes the whole pool with it, and every future still in
        # flight. Reported against the documents that didn't get parsed
        # rather than raised, so the run still writes its ledger updates,
        # its summary, and a nonzero exit code.
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


def _parse_parallel(refs, workers: int, threads: int | None) -> Iterator[_ParseResult]:
    """Same triples as _parse_serial, produced by `workers` at once.

    Submitted biggest-file-first (the LPT heuristic). One 675-page
    document in this project's own corpus is 5% of all its pages; picked
    up last it would define the wall clock single-handedly. File size
    rather than page count on purpose -- counting pages needs a PDF
    library, and the corpus layer deliberately has no such dependency.
    """
    jobs = [
        (r.pdf_path, r.citekey, threads) for r in sorted(refs, key=lambda r: -_pdf_size(r.pdf_path))
    ]
    stalled = []
    executor = _executor_for(workers)
    results, broken = _drain_pool(executor, jobs, stalled)
    _account_for_unfinished(refs, results, broken, stalled)
    return ((ref.citekey, *results[ref.citekey]) for ref in refs)

"""Exiting a running worker pool promptly and cleanly on Ctrl+C.

Split out of chitragupta/pdf_text.py (#361). Self-contained: `terminate_workers`
and `interrupt_guard` only ever call each other, never anything else in
this package.
"""

import os
import signal
import sys
from typing import NoReturn

# How long a worker gets to honour SIGTERM before being killed outright.
_TERMINATE_GRACE_SECONDS = 2.0


def terminate_workers(executor) -> None:
    """Kill the pool's worker processes outright.

    shutdown(cancel_futures=True) only drops jobs that have not started;
    the handful already running keep going, and ProcessPoolExecutor's
    atexit hook then *joins* them on the way out. With docling that is
    minutes per in-flight document, which is what "Ctrl+C took forever to
    exit" actually was.

    There is no public API for this -- ProcessPoolExecutor deliberately
    exposes no way to cancel running work -- so this reaches for
    `_processes`. Guarded with getattr because it is private and because
    a ThreadPoolExecutor (the pdftotext backend, and the tests) has no
    such attribute and needs no killing.
    """
    processes = list(getattr(executor, "_processes", {}).values())
    for process in processes:
        try:
            process.terminate()
        except Exception:  # noqa: BLE001  # already exited, or already reaped
            pass
    # SIGTERM is a request, and a worker sitting in onnxruntime or torch
    # native code does not necessarily honour it promptly -- measured 21
    # processes still alive after terminate() alone, which would leave
    # orphans holding GPU memory. Give them a moment, then insist.
    for process in processes:
        try:
            process.join(timeout=_TERMINATE_GRACE_SECONDS)
            if process.is_alive():
                process.kill()
        except Exception:  # noqa: BLE001 -- as above
            pass


class interrupt_guard:
    """Exit promptly and cleanly on Ctrl+C while a worker pool is running.

    An `except KeyboardInterrupt` around `as_completed()` does NOT work
    here, and that is the whole reason this exists. Reproduced in a
    minimal script with no docling in it: SIGINT reaches the parent, the
    result loop stops consuming, and the handler never runs -- the
    process then sits until its in-flight workers finish, which with
    docling is minutes per document. That is the reported symptom,
    "Ctrl+C took forever to exit", plus docling teardown tracebacks from
    workers still being driven.

    An explicit SIGINT handler does work: measured 0.0s to exit against
    60s+ (and counting) for the exception path. It terminates the pool's
    workers and calls os._exit, deliberately skipping interpreter
    shutdown -- ProcessPoolExecutor's atexit hook *joins* its workers,
    which is the thing being avoided. Skipping it is safe for this
    program's own state because the ledger commits incrementally and
    synchronously as each document lands: whatever finished is already on
    disk.

    Restores the previous handler on the way out, so a library caller
    that installed its own gets it back.
    """

    def __init__(self, executor, describe) -> None:
        self._executor = executor
        self._describe = describe
        self._previous = None

    def __enter__(self) -> "interrupt_guard":
        try:
            self._previous = signal.signal(signal.SIGINT, self._on_sigint)
        except ValueError:
            # Not the main thread (a test, or an embedding caller):
            # signal handling isn't available, and the pool still works.
            self._previous = None
        return self

    def __exit__(self, *exc_info) -> bool:
        if self._previous is not None:
            signal.signal(signal.SIGINT, self._previous)
        return False

    def _on_sigint(self, _signum, _frame) -> NoReturn:
        # Deliberately still a bare print, not chitragupta.sync's logger: this
        # runs inside a signal handler a couple of lines before
        # os._exit(130), and print(..., flush=True) is a call this
        # project has already measured exiting in 0.0s (see the class
        # docstring) -- not a call site to introduce the logging module's
        # own locking/formatting machinery into for a marginal gain.
        print(
            f"\n  interrupted -- {self._describe()}. Work already "
            "finished is kept; re-run to continue.",
            file=sys.stderr,
            flush=True,
        )
        terminate_workers(self._executor)
        os._exit(130)

"""Exiting a running worker pool promptly and cleanly on Ctrl+C."""

import os
import signal
import sys
from typing import NoReturn

_TERMINATE_GRACE_SECONDS = 2.0


def terminate_workers(executor) -> None:
    """Kill the pool's worker processes outright.

    shutdown(cancel_futures=True) leaves running jobs going, and the
    atexit hook then *joins* them: minutes per docling document. No public
    API cancels running work, so this reaches for private `_processes`
    (absent on a ThreadPoolExecutor). `or {}` because `shutdown()` sets it
    to None, which crashed the stall watchdog's recovery path (#726).
    """
    processes = list((getattr(executor, "_processes", None) or {}).values())
    for process in processes:
        try:
            process.terminate()
        except Exception:  # noqa: BLE001  # already exited, or already reaped
            pass
    # A worker in onnxruntime or torch native code may ignore SIGTERM (21
    # measured still alive), leaving orphans holding GPU memory; then kill.
    for process in processes:
        try:
            process.join(timeout=_TERMINATE_GRACE_SECONDS)
            if process.is_alive():
                process.kill()
        except Exception:  # noqa: BLE001 -- as above
            pass


class interrupt_guard:
    """Exit promptly and cleanly on Ctrl+C while a worker pool is running.

    `except KeyboardInterrupt` around `as_completed()` does NOT work: the
    handler never runs and the process waits for in-flight workers
    (minutes each with docling). An explicit SIGINT handler exits in 0.0s:
    it terminates the workers and calls os._exit, skipping the atexit hook
    that *joins* them. Safe because the ledger commits as each document
    lands. Restores the previous handler on the way out.
    """

    def __init__(self, executor, describe) -> None:
        self._executor = executor
        self._describe = describe
        self._previous = None

    def __enter__(self) -> "interrupt_guard":
        try:
            self._previous = signal.signal(signal.SIGINT, self._on_sigint)
        except ValueError:
            # Not the main thread: no signal handling, the pool still works.
            self._previous = None
        return self

    def __exit__(self, *exc_info) -> bool:
        if self._previous is not None:
            signal.signal(signal.SIGINT, self._previous)
        return False

    def _on_sigint(self, _signum, _frame) -> NoReturn:
        # A bare print, not sync's logger: this runs in a signal handler
        # just before os._exit(130), and print(flush=True) is measured fast.
        print(
            f"\n  interrupted -- {self._describe()}. Work already "
            "finished is kept; re-run to continue.",
            file=sys.stderr,
            flush=True,
        )
        terminate_workers(self._executor)
        os._exit(130)

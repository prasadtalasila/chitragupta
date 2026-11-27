"""One writer at a time across content/.

`sync` and enrichment both write there: overlapping runs hand each other
two versions of a re-parsed document and contend for GPUs.

The mutex is a dedicated sqlite file held under `BEGIN IMMEDIATE`,
chosen by measurement: it takes a RESERVED lock, so readers keep
working; a second taker gets SQLITE_BUSY; `kill -9` releases it at once,
so staleness needs no PID check or platform branch; and no write is
needed. Rejected: an `O_EXCL` lock file (needs per-platform stale-lock
detection), and locking the ledger itself (forces one transaction, so a
crash at 90% would lose every recorded parse).

Inherits sqlite's locking, unreliable on network filesystems, so
`content/` must be local. Serialises writers only.
"""

import json
import os
import socket
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from chitragupta import config


# Past this a run is probably wedged. Generous, as a first full parse is
# long; it changes only the wording, giving unattended callers something
# to alert on besides the normal exit 2.
_STUCK_AFTER_SECONDS = 6 * 60 * 60


class AlreadyRunning(RuntimeError):
    """Another sync or enrichment run holds the lock."""


# Distinct from 1 ("ran, and something failed"), so an unattended caller
# can tell a skipped cycle from a failure.
EXIT_ALREADY_RUNNING = 2


def _describe_holder(path) -> "tuple[int, str, str, float] | None":
    """(pid, host, started_at, age_seconds) for the current holder, or
    None if that can't be read.

    Never raises, so a refusal never becomes a traceback. The details may
    be stale, so they are advisory only.
    """
    try:
        data = json.loads(Path(str(path) + ".holder").read_text(encoding="utf-8"))
        started = datetime.fromisoformat(data["started_at"])
        return (
            data["pid"],
            data["host"],
            data["started_at"],
            (datetime.now(timezone.utc) - started).total_seconds(),
        )
    except Exception:  # noqa: BLE001 -- see docstring
        return None


def _refusal_message(path) -> str:
    base = (
        f"another sync or pipeline run is already running (it holds {path}), so "
        "this run was skipped. Nothing is lost -- the pipeline is incremental, "
        "and the next run continues from where this one would have started."
    )
    holder = _describe_holder(path)
    if holder is None:
        return base
    pid, host, started_at, age = holder
    base += f" That run: pid {pid} on {host}, started {started_at} ({age / 60:.0f} min ago)."
    if age >= _STUCK_AFTER_SECONDS:
        # A grep-able phrase for when "skipped" has stopped being benign.
        base += (
            " POSSIBLY STUCK: it has held the lock far longer than a run should "
            "take, and every run since has been skipped. Check that process is "
            "alive and making progress; the lock frees itself once it exits."
        )
    else:
        base += (
            " The lock frees itself when that run exits, including on a crash, so "
            "if you believe none is active then one really is still alive."
        )
    return base


class pipeline_lock:
    """Hold the pipeline lock for the duration of a `with` block.

    The connection is kept on the instance, not in a local: CPython would
    close a local that fell out of scope and silently release the lock.
    """

    def __init__(self, path=None) -> None:
        self._path = Path(path) if path is not None else config.PIPELINE_LOCK_PATH
        self._con = None

    def _record_holder(self) -> None:
        """Note who we are, in a plain file beside the lock.

        Not a row in the lock database: a COMMIT releases BEGIN IMMEDIATE,
        opening a window for a second holder. Best-effort, since the
        details are advisory and must never cost the lock.
        """
        try:
            self._holder_path().write_text(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "host": socket.gethostname(),
                        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    }
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _holder_path(self) -> Path:
        return self._path.with_name(self._path.name + ".holder")

    def __enter__(self) -> "pipeline_lock":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # timeout=0: sync is incremental and idempotent, so a skipped cycle
        # costs nothing. isolation_level=None so sqlite3's implicit
        # transactions cannot make BEGIN IMMEDIATE fail as nested.
        self._con = sqlite3.connect(self._path, timeout=0, isolation_level=None)
        try:
            self._con.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            self._con.close()
            self._con = None
            # By error code, not message: OperationalError also covers a
            # full disk or corrupt file, which is not "another run".
            if getattr(exc, "sqlite_errorcode", None) != sqlite3.SQLITE_BUSY:
                raise
            raise AlreadyRunning(_refusal_message(self._path)) from exc
        except Exception:
            self._con.close()
            self._con = None
            raise
        # Only once the lock is held, so the details describe the winner.
        self._record_holder()
        return self

    def __exit__(self, *exc_info) -> bool:
        if self._con is not None:
            # ROLLBACK: nothing was written. The file is never deleted:
            # Windows cannot unlink an open file, and on POSIX a recreate
            # race would give two processes locks on different inodes.
            try:
                self._con.execute("ROLLBACK")
            finally:
                self._con.close()
                self._con = None
        return False

"""Why a reader could not read the ledger: `ledger.read_connection`'s refusals.

Re-exported by `chitragupta.ledger` as `ledger.NoLedger` and friends (#1066).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from chitragupta import config

# A command that could not read the ledger checked nothing (#1066). Not 1
# (an unresolved citekey) or 2 (bad usage): "could not check" must never
# read as a verdict. The bare-python hooks restate it; tests pin both.
EXIT_UNREADABLE = 3

_SYNC = "python -m chitragupta.corpus sync"


class NoLedger(RuntimeError):
    """There is no ledger to read: `read_connection`'s refusal."""

    # The default message is what skills and the session-start hook tell
    # apart from "the ledger is empty".

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            detail
            or f"No ledger at {config.LEDGER_PATH}.\n"
            "Run `python -m chitragupta.corpus sync` to build it from your bib file."
        )


class StaleLedger(NoLedger):
    """The ledger predates this version's schema; refused wherever `NoLedger` is."""


# Keyed by `sqlite_errorname` prefix, never the message, whose wording
# SQLite does not promise. A hot journal (#1066) needs a rollback a
# `mode=ro` handle cannot do; it is reported, not healed, since rolling
# back writes the user's data (the writer's open does it;
# tests/test_ledger_read.py). A damaged file is moved aside, never deleted.
_CAUSES = (
    (
        ("SQLITE_READONLY_ROLLBACK",),
        "{journal} beside it is left over from a write that was interrupted "
        "(a killed `corpus sync`, for example), and a read-only reader cannot "
        "roll that write back.",
        f"Make sure no sync is running, then run `{_SYNC}`: it opens the ledger "
        "for writing, which rolls the interrupted write back.",
    ),
    (
        ("SQLITE_BUSY", "SQLITE_LOCKED"),
        "another process is writing to it (a running `corpus sync`, for example).",
        "Wait for that to finish, then run this again.",
    ),
    (
        ("SQLITE_NOTADB", "SQLITE_CORRUPT"),
        "it is not a SQLite database, or it is damaged.",
        f"Move it aside (keep it), then run `{_SYNC}` to rebuild it from your bib file.",
    ),
    (
        ("SQLITE_CANTOPEN", "SQLITE_PERM", "SQLITE_AUTH"),
        "SQLite could not open the file.",
        "Check that you can read it and the directory it is in, then run this again.",
    ),
)


class UnreadableLedger(NoLedger):
    """The ledger exists but SQLite will not read it; refused wherever `NoLedger` is,
    so callers print it as an `[error]` line, not a traceback.
    """

    def __init__(self, path: Path, error: sqlite3.Error) -> None:
        name = getattr(error, "sqlite_errorname", None) or ""
        journal = path.name + "-journal"
        # The fallback is SQLite's own words, kept out of `format`: a brace
        # in its message would otherwise be read as a placeholder.
        cause, fix = next(
            (
                (cause.format(journal=journal), fix)
                for prefixes, cause, fix in _CAUSES
                if name.startswith(prefixes)
            ),
            (
                f"SQLite says: {error}.",
                "Run this again; if it persists, move the ledger aside (keep it) "
                f"and run `{_SYNC}` to rebuild it from your bib file.",
            ),
        )
        super().__init__(f"The ledger at {path} exists but could not be read: {cause}\n{fix}")

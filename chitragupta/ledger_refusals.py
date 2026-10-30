"""Why a reader could not read the ledger: `ledger.read_connection`'s refusals.

Re-exported by `chitragupta.ledger`, so every caller keeps spelling them
`ledger.NoLedger` and friends. They live here only because `ledger.py`
reached the 250-code-line limit (docs/CODE-STANDARDS.md) when the third
one arrived (#1066).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from chitragupta import config

# The exit status of a command that could not read the ledger and so
# checked nothing (#1066): `draft gate` and `corpus ledger`. Not 1, which
# is the gate's verdict that a citekey is unresolved, and not 2, which is
# bad usage -- "I could not check" and "I checked and it failed" must
# never share a code, or a crash reads as a refusal. The two hooks run on
# bare python without importing this package, so each spells it as its
# own constant; tests pin both to this one.
EXIT_UNREADABLE = 3

_SYNC = "python -m chitragupta.corpus sync"


class NoLedger(RuntimeError):
    """There is no ledger to read: `read_connection`'s refusal."""

    # The default message is the two lines `corpus ledger` has always
    # printed, which the genre skills and the session-start hook tell
    # apart from "the ledger is empty".

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            detail
            or f"No ledger at {config.LEDGER_PATH}.\n"
            "Run `python -m chitragupta.corpus sync` to build it from your bib file."
        )


class StaleLedger(NoLedger):
    """The ledger predates this version's schema; refused wherever `NoLedger` is."""


# Keyed by the prefix of `sqlite3.Error.sqlite_errorname` (Python 3.11+;
# the floor is 3.12), never by the message, whose wording SQLite does not
# promise. Each row is what happened, then what to do, and `{journal}` is
# the journal's file name.
#
# The hot journal is #1066's case. Any interrupted write leaves one, and
# SQLite must roll it back before it answers even `PRAGMA user_version`,
# which a `mode=ro` handle cannot do. The refusal reports it and does not
# heal it: rolling back is a write to the user's own data, so it happens
# when they run the writer, whose read-write open does it on first touch
# (tests/test_ledger_read.py proves that, so the fix named is not a
# guess). A damaged file is moved aside, never deleted: it is the only
# copy of whatever state the user had.
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
    """The ledger exists but SQLite will not read it; refused wherever `NoLedger` is.

    A `NoLedger`, so every command that already turns that refusal into an
    `[error]` line reports this one too, rather than a raw sqlite traceback.
    Its message has the same two lines: what happened, then what to do.
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

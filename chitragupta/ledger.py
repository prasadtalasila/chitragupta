"""SQLite ledger tracking per-citekey pipeline status.

Makes `sync` incremental: a PDF is re-parsed only when its content
changed, checked by (size, mtime) first and sha256 only on a mismatch
(see upsert_reference), so an unattended no-op run does not re-hash
every PDF.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from chitragupta import config, ledger_paths, ledger_tables

# Re-exported so `ledger.upsert_reference(...)` call sites keep working (#441).
from chitragupta.ledger_upsert import upsert_reference  # noqa: F401  # pylint: disable=unused-import

# Re-exported; stored paths are relative (#966).
from chitragupta.ledger_paths import mark_parsed  # noqa: F401  # pylint: disable=unused-import

# Re-exported so `ledger.NoLedger` and the rest keep working (#1066).
from chitragupta.ledger_refusals import (  # noqa: F401  # pylint: disable=unused-import
    EXIT_UNREADABLE,
    NoLedger,
    StaleLedger,
    UnreadableLedger,
)

# A column holding a path is named `*_path` and is stored through
# `ledger_paths` (#966), never as `str(path)`;
# tests/test_ledger_relocation.py scans for both.
#
# _SCHEMA is only the original shape (version 0); every later column is a
# migration, so a new database and an old one take the same path.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    citekey TEXT PRIMARY KEY,
    item_type TEXT,
    title TEXT,
    year TEXT,
    doi TEXT,
    url TEXT,
    pdf_path TEXT,
    pdf_hash TEXT,
    status TEXT NOT NULL DEFAULT 'discovered',
    parsed_path TEXT,
    parse_error TEXT,
    last_synced TEXT NOT NULL
);
"""

# One tuple of (column, statement) pairs per schema version, tracked by
# PRAGMA user_version. Each column is still re-checked against table_info
# before running, because ADD COLUMN on an existing column raises and
# would crash every `sync`.
_MIGRATIONS: list[tuple[tuple[str | None, str], ...]] = [
    (
        # version 1: (size, mtime) for the stat-before-hash skip.
        ("pdf_size", "ALTER TABLE items ADD COLUMN pdf_size INTEGER"),
        ("pdf_mtime_ns", "ALTER TABLE items ADD COLUMN pdf_mtime_ns INTEGER"),
    ),
    (
        # version 2: a dead worker (transient, retried, or one OOM drops
        # documents for good) versus a corrupt PDF (deterministic, not
        # retried, or sync exits 1 forever and readers learn to ignore it).
        # NULL predates the column and is treated as transient.
        ("failure_kind", "ALTER TABLE items ADD COLUMN failure_kind TEXT"),
    ),
    (
        # version 3: the entry's BibTeX fields as one JSON object, for
        # references.py, which runs under bare python3 and may not read
        # bibliography.bib (only bib_reader may). NULL falls back to
        # title/year until the next sync backfills it.
        ("bib_fields", "ALTER TABLE items ADD COLUMN bib_fields TEXT"),
    ),
    (
        # version 4: Zotero collection paths as JSON
        # (chitragupta/bib_collections.py); NULL means none recorded.
        ("collections", "ALTER TABLE items ADD COLUMN collections TEXT"),
    ),
    # version 5: chitragupta-importer's collection names and recorded
    # citekey renames, and version 4's `groups` paths cleared
    # (chitragupta/ledger_tables.py).
    ledger_tables.MIGRATION,
]


def _migrate(con: sqlite3.Connection) -> None:
    (current,) = con.execute("PRAGMA user_version").fetchone()
    target = len(_MIGRATIONS)
    if current >= target:
        return
    existing_cols = {row[1] for row in con.execute("PRAGMA table_info(items)")}
    for steps in _MIGRATIONS[current:target]:
        for column, statement in steps:
            if column is None or column not in existing_cols:
                con.execute(statement)
    # No `?` binding for PRAGMA; target is our own len(), never user input.
    con.execute(f"PRAGMA user_version = {target}")


def connect() -> sqlite3.Connection:
    """The writer's connection, for `sync` alone: creates the database
    and migrates it. A reader uses `read_connection` (#843)."""
    config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.LEDGER_PATH)
    # Schema and migration in one write transaction (#843): BEGIN IMMEDIATE
    # takes the lock before user_version is read, so concurrent first
    # touches (deep-research subagents) cannot both run ALTER TABLE, and a
    # failure rolls every step back.
    con.execute("BEGIN IMMEDIATE")
    try:
        con.execute(_SCHEMA)
        _migrate(con)
        ledger_paths.normalise_legacy(con)
    except BaseException:
        con.rollback()
        con.close()
        raise
    con.commit()
    return con


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """`with ledger.connection() as con:` -- connect(), closed. A reader
    wants `reading()`."""
    con = connect()
    try:
        yield con
    finally:
        con.close()


# The one read-only opener (#843). `connect()` is wrong for a reader: it
# takes the write lock and, before any sync, creates an empty ledger.
# `mode=ro` cannot create a file. `timeout` is sqlite's default, not 0
# (#552): without WAL a reader waits out a writer's commit.
# A ledger behind `_MIGRATIONS` is refused as `StaleLedger`, not migrated
# (a reader may not write); readers say "run sync" until one sync runs.
# A file SQLite will not read is `UnreadableLedger`, never a raw
# `sqlite3.Error` (#1066).
def read_connection() -> sqlite3.Connection:
    """The ledger, read-only. Raises `NoLedger` when there is no file,
    `StaleLedger` when it needs a sync to migrate and `UnreadableLedger`
    when SQLite will not read it; creates nothing."""
    if not config.LEDGER_PATH.exists():
        raise NoLedger()
    try:
        con = sqlite3.connect(ledger_paths.read_only_uri(config.LEDGER_PATH), uri=True, timeout=5.0)
    except sqlite3.Error as exc:
        raise UnreadableLedger(config.LEDGER_PATH, exc) from exc
    try:
        (version,) = con.execute("PRAGMA user_version").fetchone()
        if version < len(_MIGRATIONS):
            raise StaleLedger(
                f"The ledger at {config.LEDGER_PATH} predates this version's schema.\n"
                "Run `python -m chitragupta.corpus sync` to migrate it."
            )
    except BaseException as exc:
        con.close()
        if isinstance(exc, sqlite3.Error):
            raise UnreadableLedger(config.LEDGER_PATH, exc) from exc
        raise
    return con


@contextmanager
def reading() -> Iterator[sqlite3.Connection]:
    """`connection()`'s shape for a reader: `read_connection()`, closed."""
    con = read_connection()
    try:
        yield con
    finally:
        con.close()


def mark_parse_failed(
    con: sqlite3.Connection, citekey: str, error: str, *, transient: bool = False
) -> None:
    """transient=True for a failure caused by the run (a dead worker, a
    stall), which is retried; the default means this PDF cannot be parsed
    and re-reading it would waste the same time again."""
    con.execute(
        "UPDATE items SET status = 'parse_failed', parse_error = ?, failure_kind = ? "
        "WHERE citekey = ?",
        (error, "transient" if transient else "deterministic", citekey),
    )
    con.commit()


def failure_counts(con: sqlite3.Connection) -> dict[str, int]:
    """{'transient': n, 'deterministic': n} over parse_failed rows.

    A NULL failure_kind counts as transient -- see _MIGRATIONS version 2.
    """
    counts = {"transient": 0, "deterministic": 0}
    for kind, n in con.execute(
        "SELECT failure_kind, count(*) FROM items WHERE status = 'parse_failed' "
        "GROUP BY failure_kind"
    ):
        counts["deterministic" if kind == "deterministic" else "transient"] += n
    return counts


# Every citekey with a row, including `no_pdf`. Not a citability test:
# that is `ledger_citable.citable_citekeys` (#1118).
def known_citekeys(con: sqlite3.Connection) -> set[str]:
    return {row[0] for row in con.execute("SELECT citekey FROM items")}


# Under SQLite's 32766 bound-variable ceiling, as chroma_paging.PAGE_SIZE.
CITEKEY_CHUNK = 30_000


def rows_for_citekeys(con: sqlite3.Connection, columns: str, citekeys: list[str]) -> list:
    """`SELECT <columns> FROM items` for every row whose citekey is in
    `citekeys`, chunked under the variable ceiling (#639).

    `columns` is a literal from this package, never external input. An
    empty list runs no query: `IN ()` is a syntax error.
    """
    rows: list = []
    for start in range(0, len(citekeys), CITEKEY_CHUNK):
        chunk = citekeys[start : start + CITEKEY_CHUNK]
        placeholders = ",".join("?" * len(chunk))
        rows.extend(
            con.execute(
                f"SELECT {columns} FROM items WHERE citekey IN ({placeholders})",
                chunk,
            )
        )
    return rows


def find_stale(con: sqlite3.Connection, seen_citekeys: set[str]) -> list[tuple[str, str | None]]:
    """Read-only: ledger rows whose citekey is no longer in the bib file.

    What `sync` reports without --remove-stale; prune_missing deletes.
    """
    rows = con.execute("SELECT citekey, parsed_path FROM items").fetchall()
    return [(citekey, parsed_path) for citekey, parsed_path in rows if citekey not in seen_citekeys]


class PruneRefused(RuntimeError):
    """The bib file yielded 0 references against a non-empty ledger. A
    distinct type so sync.py can catch it without swallowing other
    RuntimeErrors."""


def prune_missing(con: sqlite3.Connection, seen_citekeys: set[str]) -> list[tuple[str, str | None]]:
    """Removes ledger rows whose citekey is no longer in the bib file.

    Otherwise a removed citekey stays citable forever: fabrication by
    deletion. Parsed text is kept, so widening BIB_FILE again needs no
    re-parse. Only with `sync --remove-stale`.

    Refuses when the bib yields zero entries but the ledger has rows: that
    is far likelier a botched export or wrong BIB_FILE, and pruning would
    make the gate fail every citekey in every draft.
    """
    stale = find_stale(con, seen_citekeys)
    if not seen_citekeys and stale:
        # Counted, not len(stale), so the message survives a changed guard.
        (total,) = con.execute("SELECT COUNT(*) FROM items").fetchone()
        raise PruneRefused(
            f"Refusing to prune: the bib file yielded 0 references but the "
            f"ledger has {total} existing item(s). This almost always "
            "means the bib file is empty, corrupted, or misconfigured "
            "(BIB_FILE pointing at the wrong path, a truncated re-export) "
            "rather than every citekey being legitimately removed. Fix the "
            "bib file/BIB_FILE and re-run sync -- if this really is "
            "intentional, delete content/ledger.sqlite directly instead."
        )
    if stale:
        con.executemany("DELETE FROM items WHERE citekey = ?", [(k,) for k, _ in stale])
        con.commit()
    return stale


def all_items(con: sqlite3.Connection) -> list[sqlite3.Row]:
    """Every ledger row, as `sqlite3.Row`.

    The factory is set on a cursor, not the connection (#511), so another
    user's factory is never overwritten or left changed after a raise.
    """
    cursor = con.cursor()
    cursor.row_factory = sqlite3.Row
    return cursor.execute("SELECT * FROM items ORDER BY citekey").fetchall()

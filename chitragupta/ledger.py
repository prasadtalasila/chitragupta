"""SQLite ledger tracking per-citekey pipeline status.

The ledger lets `sync` be incremental: a paper is only re-parsed if its
PDF content actually changed, not on every run. Change detection is
two-stage: a cheap (size, mtime) stat comparison first, and a sha256
content hash only when that stat doesn't match what was last recorded
(or there's nothing recorded yet) -- see upsert_reference. This is the
state that makes the deterministic pipeline safe to run unattended/on a
schedule, including on a corpus large enough that re-hashing every PDF
on every no-op run would dominate the run's wall-clock time.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from chitragupta import config

# upsert_reference's own implementation, and everything it depends on,
# lives in chitragupta/ledger_upsert.py (#441) -- this module crossed the
# 250-code-line C2 limit, and that unit never touches the schema,
# migrations or the read-only queries below. Re-exported here, the same
# shape chitragupta/render_output/__init__.py already uses, so every
# existing `ledger.upsert_reference(...)` call site keeps working
# unchanged.
from chitragupta.ledger_upsert import upsert_reference  # noqa: F401  # pylint: disable=unused-import

# _SCHEMA only ever describes the *original* table shape (schema version
# 0) -- every column added since is a migration in _MIGRATIONS below, not
# an edit here. That way a brand-new database and an existing one predating
# a migration go through the exact same code path in _migrate (both start
# at user_version 0), instead of _SCHEMA silently being "current" for a
# fresh file while an existing file still needs ALTER TABLE.
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

# Ordered, one tuple of (column_name, "ADD COLUMN" statement) pairs per
# schema version -- version N is "the first N tuples have been applied".
# Tracked via PRAGMA user_version (a plain integer stored in the database
# file itself) so an already-migrated ledger -- the common case on every
# routine `sync` -- skips straight past the loop below on a single
# integer comparison. Each statement is still paired with the column name
# it adds and re-checked against PRAGMA table_info(items) before running
# (_migrate below) rather than trusted on user_version alone: user_version
# and the table's actual shape could in principle disagree (e.g. a future
# column added directly to _SCHEMA instead of here), and "ADD COLUMN" on
# a column that already exists raises, so this is what keeps that
# specific mistake from crashing every `sync` on every host instead of
# just being a no-op.
_MIGRATIONS: list[tuple[tuple[str, str], ...]] = [
    (
        # version 1: upsert_reference's stat-before-hash skip (module
        # docstring) needs somewhere to persist the (size, mtime) last
        # observed for a given PDF, so a subsequent no-op sync can compare
        # against that instead of re-reading and sha256-hashing
        # potentially gigabytes of PDF content.
        ("pdf_size", "ALTER TABLE items ADD COLUMN pdf_size INTEGER"),
        ("pdf_mtime_ns", "ALTER TABLE items ADD COLUMN pdf_mtime_ns INTEGER"),
    ),
    (
        # version 2: 'parse_failed' conflated two failures that want
        # opposite handling. A worker dying marks every in-flight
        # document failed and must be retried, or one OOM silently
        # removes them from the corpus for good; a corrupt PDF must NOT
        # be re-parsed every run, because a sync that exits 1 forever
        # trains its reader to ignore exit 1 -- which is how the next
        # real failure gets missed.
        #
        # NULL means "recorded before this distinction existed", and is
        # deliberately treated as transient: those rows predate the
        # column, and retrying one corrupt PDF once is cheaper than
        # silently abandoning a document that failed for a transient
        # reason.
        ("failure_kind", "ALTER TABLE items ADD COLUMN failure_kind TEXT"),
    ),
    (
        # version 3: the entry's own BibTeX fields, verbatim, as a JSON
        # object -- authors, journal/booktitle, volume, pages, publisher,
        # everything the title/year/doi columns above don't keep.
        #
        # chitragupta/references.py needs them to write a real bibliography entry
        # rather than just "citekey -- Title (Year)", and it may not read
        # bibliography.bib to get them: chitragupta/bib_reader.py is the only
        # module allowed to (AGENTS.md), and it needs bibtexparser, while
        # references.py runs under bare python3. One opaque JSON column
        # rather than a column per field because nothing here queries or
        # indexes them -- they are only ever read back whole, for one
        # citekey at a time, to format an entry.
        #
        # NULL means "synced before this column existed". references.py
        # falls back to the title/year columns for those rather than
        # failing, so an existing ledger keeps working until the next
        # `python -m chitragupta.corpus sync` backfills it.
        ("bib_fields", "ALTER TABLE items ADD COLUMN bib_fields TEXT"),
    ),
    (
        # version 4: Zotero collection membership, as a JSON array of normalised
        # paths (chitragupta/bib_collections.py). NULL for a row synced before
        # this column existed and for the majority of libraries, whose
        # export carries no such field at all -- both read as "no
        # collections recorded", which is what every caller already does
        # with an empty list.
        ("collections", "ALTER TABLE items ADD COLUMN collections TEXT"),
    ),
]


def _migrate(con: sqlite3.Connection) -> None:
    (current,) = con.execute("PRAGMA user_version").fetchone()
    target = len(_MIGRATIONS)
    if current >= target:
        return
    existing_cols = {row[1] for row in con.execute("PRAGMA table_info(items)")}
    for steps in _MIGRATIONS[current:target]:
        for column, statement in steps:
            if column not in existing_cols:
                con.execute(statement)
    # PRAGMA user_version doesn't accept `?` parameter binding -- target
    # is this module's own len(_MIGRATIONS), never user input.
    con.execute(f"PRAGMA user_version = {target}")


def connect() -> sqlite3.Connection:
    config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.LEDGER_PATH)
    con.execute(_SCHEMA)
    _migrate(con)
    con.commit()
    return con


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """`with ledger.connection() as con:` -- connect() plus the
    close()-in-a-finally every caller was already writing by hand at
    eight call sites (#292). Not a change to the connection's lifecycle,
    just to who writes the boilerplate.
    """
    con = connect()
    try:
        yield con
    finally:
        con.close()


def mark_parsed(con: sqlite3.Connection, citekey: str, parsed_path: Path) -> None:
    con.execute(
        "UPDATE items SET status = 'parsed', parsed_path = ?, parse_error = NULL WHERE citekey = ?",
        (str(parsed_path), citekey),
    )
    con.commit()


def mark_parse_failed(
    con: sqlite3.Connection, citekey: str, error: str, *, transient: bool = False
) -> None:
    """transient=True for a failure caused by the *run* rather than the
    document -- a dead pool worker, a stalled run. Those are retried
    automatically. The default is deterministic: the backend read this
    particular PDF and could not parse it, so re-reading it next run
    would only waste the same time again.

    Deliberately leaves parsed_path untouched: this is called for a PDF
    whose *content* is unchanged from the last successful parse (a
    changed PDF already went through upsert_reference's hash-change path,
    which clears parsed_path there -- see its docstring, M-5). Clearing
    it here too would also wipe it on a transient (retried) failure,
    where the previously parsed text is still correct and still on disk.
    """
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


def known_citekeys(con: sqlite3.Connection) -> set[str]:
    return {row[0] for row in con.execute("SELECT citekey FROM items")}


def find_stale(con: sqlite3.Connection, seen_citekeys: set[str]) -> list[tuple[str, str | None]]:
    """Read-only: ledger rows whose citekey is no longer in the bib file.

    Never deletes anything -- this is what `sync`'s default (--remove-stale
    not passed) mode calls to report what a --remove-stale run would prune,
    without taking the destructive step. See prune_missing for the version
    that actually deletes.
    """
    rows = con.execute("SELECT citekey, parsed_path FROM items").fetchall()
    return [(citekey, parsed_path) for citekey, parsed_path in rows if citekey not in seen_citekeys]


def prune_missing(con: sqlite3.Connection, seen_citekeys: set[str]) -> list[tuple[str, str | None]]:
    """Removes ledger rows whose citekey is no longer in the bib file.

    Without this, a citekey removed from bibliography.bib (the source of
    truth) stays "known" to citation_gate forever -- exactly the fabricated-
    citekey failure mode AGENTS.md's invariant exists to prevent, just
    arriving via deletion instead of invention. Returns the removed
    (citekey, parsed_path) pairs so the caller can also clean up the
    now-orphaned parsed text file, though sync.py deliberately doesn't:
    only the row is what citation_gate actually checks, and pointing
    BIB_FILE at a smaller export is a documented, routine way to narrow
    the working set (and does, intentionally, prune the rows it excludes
    when --remove-stale is passed) -- but leaving the derived text in
    place means switching BIB_FILE back to a wider export later doesn't
    force a re-parse of PDFs whose text was already extracted.

    Only called when `sync --remove-stale` is passed (default: off, see
    sync.run) -- otherwise sync calls the read-only find_stale() instead,
    so an accidental citekey drop just gets reported, not deleted, until
    the user explicitly opts in.

    Refuses (raises) rather than pruning when seen_citekeys is empty but
    the ledger already has rows: bibliography.bib is a manual export
    (AGENTS.md), and a file that exists and parses cleanly but yields
    zero entries is far more likely to be a botched re-export, a
    truncated file, or BIB_FILE pointing at the wrong path than someone
    deliberately deleting their entire library. Pruning through that
    would wipe every row in one sync run and make citation_gate report
    every citekey in every existing draft as fabricated.
    """
    stale = find_stale(con, seen_citekeys)
    if not seen_citekeys and stale:
        # Query the total row count explicitly rather than reusing
        # len(stale) -- true today only because seen_citekeys is empty
        # (every row is trivially "stale"), but the message should stay
        # accurate even if this guard's condition changes later.
        (total,) = con.execute("SELECT COUNT(*) FROM items").fetchone()
        raise RuntimeError(
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
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM items ORDER BY citekey").fetchall()
    con.row_factory = None
    return rows

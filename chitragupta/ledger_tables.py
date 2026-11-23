"""Ledger schema version 5: the importer's collection names and recorded
citekey renames (plans/1211-cg-collections-and-renames.md).

Three tables beside `items`, none keyed to an items row:

- `collection_names`: slug path -> the collection's own name, from the
  bib's `cg-collections` table. Rewritten whole on every sync, so a
  collection renamed in the reference manager shows its new name while
  its slug, and every `scope.md` that recorded it, stay the same.
- `renames`: old citekey -> new citekey, recorded by
  `chitragupta/sync_renames.py` before any prune can delete the old row,
  so the drafting layer can still find the replacement after
  `--remove-stale`. `source` says how it was learnt (`pdf_hash` match or
  the importer's `cg-renames` table) and `same_pdf` whether the two PDFs
  are byte-identical, which decides whether quotes need re-checking.
- `stale_citekeys`: the keys the last whole read of the bib no longer
  has, rewritten on every sync. A stale key's items row stays until
  `--remove-stale`, so this is how the drafting layer's `dossier status`
  knows, before the prune, that a draft cites a paper on its way out.

The migration also clears `items.collections`: version 4 stored Better
BibTeX `groups` paths there, which no longer mean anything, and a row
whose entry has left the bib would otherwise keep one forever.

Readers return `{}` on a database without these tables, as `of_row`
does for a missing column: a connection a caller opened itself should
narrow a lookup, not stop it.
"""

from __future__ import annotations

import sqlite3

# `(key, statement)` steps for ledger._MIGRATIONS. A None key runs on the
# move to this version whatever the table's shape; ledger._migrate only
# skips a step whose key names an items column that already exists.
MIGRATION: tuple[tuple[str | None, str], ...] = (
    (
        None,
        "CREATE TABLE IF NOT EXISTS collection_names "
        "(slug_path TEXT PRIMARY KEY, name TEXT NOT NULL)",
    ),
    (
        None,
        "CREATE TABLE IF NOT EXISTS renames ("
        "old TEXT PRIMARY KEY, new TEXT NOT NULL, "
        "source TEXT NOT NULL CHECK (source IN ('pdf_hash', 'cg-renames')), "
        "same_pdf INTEGER NOT NULL, seen_at TEXT NOT NULL)",
    ),
    (None, "CREATE TABLE IF NOT EXISTS stale_citekeys (citekey TEXT PRIMARY KEY)"),
    (None, "UPDATE items SET collections = NULL"),
)


def replace_collection_names(con: sqlite3.Connection, names: dict[str, str]) -> None:
    """Make `collection_names` hold exactly `names`."""
    con.execute("DELETE FROM collection_names")
    con.executemany("INSERT INTO collection_names VALUES (?, ?)", sorted(names.items()))


def replace_stale(con: sqlite3.Connection, citekeys: set[str]) -> None:
    """Make `stale_citekeys` hold exactly `citekeys`."""
    con.execute("DELETE FROM stale_citekeys")
    con.executemany("INSERT INTO stale_citekeys VALUES (?)", [(key,) for key in sorted(citekeys)])


def stale(con: sqlite3.Connection) -> set[str]:
    """The citekeys the last sync found missing from the bib."""
    return {r[0] for r in _rows(con, "SELECT citekey FROM stale_citekeys")}


def _rows(con: sqlite3.Connection, query: str) -> list:
    try:
        return con.execute(query).fetchall()
    except sqlite3.OperationalError:
        return []


def collection_names(con: sqlite3.Connection) -> dict[str, str]:
    """Slug path -> name, as the last sync recorded them."""
    return {r[0]: r[1] for r in _rows(con, "SELECT slug_path, name FROM collection_names")}


def renames(con: sqlite3.Connection) -> dict[str, tuple[str, str, bool]]:
    """Old citekey -> (new citekey, source, same_pdf)."""
    query = "SELECT old, new, source, same_pdf FROM renames"
    return {r[0]: (r[1], r[2], bool(r[3])) for r in _rows(con, query)}

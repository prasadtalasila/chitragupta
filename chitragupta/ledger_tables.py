"""Ledger schema version 5: the importer's collection names and recorded
citekey renames (plans/1211-cg-collections-and-renames.md).

- `collection_names`: slug path -> name, rewritten every sync, so a
  rename shows while every recorded slug stays valid.
- `renames`: old -> new citekey, recorded before any prune so the
  drafting layer can follow it; `same_pdf` decides whether quotes need
  re-checking.
- `stale_citekeys`: keys the last bib read lacked, so `dossier status`
  knows before `--remove-stale` that a draft cites a paper on its way out.

The migration clears `items.collections`, whose v4 `groups` paths mean
nothing now. Readers return `{}` when the tables are missing.
"""

from __future__ import annotations

import sqlite3

# Steps for ledger._MIGRATIONS; a None key always runs on the move here.
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

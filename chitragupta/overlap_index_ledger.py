"""Read-only ledger access for the overlap index -- the corpus-wide
fingerprintable set, and one item's own `(pdf_hash, parsed_path)`.

Not `ledger.connect()`, which writes and so breaks the overlap index's "no
writer lock" contract; opened through `ledger.read_connection` (#552).
"""

import sqlite3

from chitragupta import ledger, ledger_paths


def _ledger_connect_ro() -> sqlite3.Connection | None:
    """The ledger read-only, or `None` when there is none to read."""
    # A ledger needing a sync, or one SQLite will not read, is raised: this
    # feeds the verbatim check, where `None` would be a silent pass (#1066).
    try:
        return ledger.read_connection()
    except (ledger.StaleLedger, ledger.UnreadableLedger):
        raise
    except ledger.NoLedger:
        return None


def _present_path(parsed_path: str) -> str | None:
    """The absolute path of this row's parsed text, or `None` unless it
    is inside `content/parsed/` and on disk (#966).

    The confinement is issue 821's: the column is data, and every overlap
    consumer reaches `parsed_path` through here, so this is the one gate.
    """
    parsed = ledger_paths.parsed_file(parsed_path)
    return str(parsed) if parsed is not None and parsed.exists() else None


def ledger_item(citekey: str) -> "tuple[str, str] | None":
    """`(pdf_hash, parsed_path)` for one citekey whose parsed text exists,
    or `None`."""
    con = _ledger_connect_ro()
    if con is None:
        return None
    try:
        row = con.execute(
            "SELECT pdf_hash, parsed_path FROM items "
            "WHERE citekey = ? AND status = 'parsed' "
            "AND pdf_hash IS NOT NULL AND parsed_path IS NOT NULL",
            (citekey,),
        ).fetchone()
    finally:
        con.close()
    if row is None:
        return None
    pdf_hash, parsed_path = row
    present = _present_path(parsed_path)
    return None if present is None else (pdf_hash, present)


def _ledger_items() -> list[tuple[str, str, str]]:
    """`(citekey, pdf_hash, parsed_path)` for every parsed citekey whose
    text still exists on disk; a deleted file is skipped, not fingerprinted
    as empty."""
    con = _ledger_connect_ro()
    if con is None:
        return []
    try:
        rows = con.execute(
            "SELECT citekey, pdf_hash, parsed_path FROM items "
            "WHERE status = 'parsed' AND pdf_hash IS NOT NULL AND parsed_path IS NOT NULL"
        ).fetchall()
    finally:
        con.close()
    return [(ck, h, present) for ck, h, p in rows if (present := _present_path(p))]

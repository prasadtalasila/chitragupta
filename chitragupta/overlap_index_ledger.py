"""Read-only ledger access for the overlap index -- the corpus-wide
fingerprintable set, and one item's own `(pdf_hash, parsed_path)`.

Split from `chitragupta/overlap_index.py` (#441). Deliberately not
`chitragupta/ledger.py::connect()`: that runs the schema, migrations and
a commit -- a writer, which contradicts this module's "no writer lock"
contract (see `chitragupta/overlap_index.py`'s own module docstring).
Opened through `ledger.read_connection`, the one read-only opener, which
has why its `timeout` is sqlite's default rather than 0 (m-72, #552).
"""

import sqlite3

from chitragupta import ledger, ledger_paths


def _ledger_connect_ro() -> sqlite3.Connection | None:
    """The ledger read-only, or `None` when there is none to read -- the
    answer both readers below turn into "nothing fingerprintable"."""
    # A ledger needing a sync is raised, not folded into `None`: this feeds
    # the verbatim check, and "no overlap found" against a corpus that was
    # never read would be a silent pass on a copying check.
    try:
        return ledger.read_connection()
    except ledger.StaleLedger:
        raise
    except ledger.NoLedger:
        return None


def _present_path(parsed_path: str) -> str | None:
    """The absolute path of this row's parsed text, or `None` unless it
    is both inside `content/parsed/` and actually on disk. The stored
    value is relative to `content/parsed/` (#966), so consumers get the
    resolved path, which opens from any cwd.

    The confinement is issue 821's: the column is data, and a row
    repointed at a host file had that file fingerprinted, paged and
    quoted by every overlap consumer below this module. One gate rather
    than one per consumer, because `overlap_index_doc`,
    `overlap_skipgram`, `overlap_source_text` and the verbatim aid all
    reach their `parsed_path` through these two functions.
    """
    parsed = ledger_paths.parsed_file(parsed_path)
    return str(parsed) if parsed is not None and parsed.exists() else None


def ledger_item(citekey: str) -> "tuple[str, str] | None":
    """`(pdf_hash, parsed_path)` for one parsed citekey whose parsed text
    still exists on disk, or `None` if the ledger, the citekey, or the
    file is missing."""
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
    parsed text still exists on disk -- the corpus-wide fingerprintable
    set. A row the ledger calls parsed but whose file has since been
    deleted is skipped, not fingerprinted as empty."""
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

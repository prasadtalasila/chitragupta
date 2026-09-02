"""Read-only ledger access for the overlap index -- the corpus-wide
fingerprintable set, and one item's own `(pdf_hash, parsed_path)`.

Split from `chitragupta/overlap_index.py` (#441). Deliberately not
`chitragupta/ledger.py::connect()`: that runs the schema, migrations and
a commit -- a writer, which contradicts this module's "no writer lock"
contract (see `chitragupta/overlap_index.py`'s own module docstring).
Opened read-only, and with sqlite's default `timeout` rather than 0,
for the same two reasons `chitragupta/ledger_cli.py`'s own CLI
(`ledger_cli.main`) is. The ledger has no `journal_mode = WAL`, so a
reader is locked out for the length of a writer's commit, and a zero
timeout turned that short, certain window into a `SQLITE_BUSY` raised
out of whichever query this was in the middle of -- on a path a review
aid reaches while a sync may well be running (m-72, issue #552).
Waiting takes no lock, so it does not compromise the contract above.
"""

import sqlite3
from pathlib import Path

from chitragupta import config


def _ledger_connect_ro() -> "sqlite3.Connection | None":
    if not config.LEDGER_PATH.exists():
        return None
    return sqlite3.connect(f"file:{config.LEDGER_PATH}?mode=ro", uri=True, timeout=5.0)


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
    if not Path(parsed_path).exists():
        return None
    return pdf_hash, parsed_path


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
    return [(ck, h, p) for ck, h, p in rows if Path(p).exists()]

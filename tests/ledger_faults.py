"""Ledgers SQLite cannot read, made the way a real host makes them (#1066).

Real files rather than a mocked `sqlite3.OperationalError`, because what
is under test is SQLite's own refusal: a read-only handle meeting a hot
journal it would have to roll back, and a page that is not a b-tree.
"""

from pathlib import Path

from tests.conftest import run_python

# A write killed mid-transaction, which is what leaves a hot journal: a
# one-page cache forces the transaction to spill into the database file,
# which SQLite does only after the journal holding the original pages is
# on disk, and `os._exit` then skips the rollback a clean exit would run.
# Imports only the standard library, so the child runs on any interpreter.
_INTERRUPTED_WRITE = """
import os, sqlite3, sys
con = sqlite3.connect(sys.argv[1], isolation_level=None)
con.execute("PRAGMA cache_size = 1")
con.execute("BEGIN")
con.execute("CREATE TABLE interrupted (filler TEXT)")
con.executemany("INSERT INTO interrupted VALUES (?)", [("x" * 500,)] * 200)
os._exit(0)
"""


def leave_hot_journal(ledger_path: Path) -> Path:
    """Interrupt a write to the existing ledger at `ledger_path`; returns the journal."""
    run_python("-c", _INTERRUPTED_WRITE, str(ledger_path), check=True)
    journal = ledger_path.with_name(ledger_path.name + "-journal")
    assert journal.stat().st_size > 0, "the interrupted write left no journal"
    return journal


def damage_past_the_header(ledger_path: Path) -> None:
    """Overwrite every page but the first, so the schema version still reads
    and the first query on a table fails as malformed."""
    data = bytearray(ledger_path.read_bytes())
    page_size = int.from_bytes(data[16:18], "big")
    data[page_size:] = b"\xff" * (len(data) - page_size)
    ledger_path.write_bytes(bytes(data))

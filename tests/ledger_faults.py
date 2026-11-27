from pathlib import Path

from tests.conftest import run_python

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
    run_python("-c", _INTERRUPTED_WRITE, str(ledger_path), check=True)
    journal = ledger_path.with_name(ledger_path.name + "-journal")
    assert journal.stat().st_size > 0, "the interrupted write left no journal"
    return journal


def damage_past_the_header(ledger_path: Path) -> None:
    data = bytearray(ledger_path.read_bytes())
    page_size = int.from_bytes(data[16:18], "big")
    data[page_size:] = b"\xff" * (len(data) - page_size)
    ledger_path.write_bytes(bytes(data))

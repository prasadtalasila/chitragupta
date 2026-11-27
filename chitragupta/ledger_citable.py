"""Which ledger rows a draft may cite: the second half of the invariant.

A citekey must be in the human's `.bib` (a ledger row proves that) *and*
picked up by a real parse of a real PDF, which only `status = 'parsed'`
proves. Checking rows alone let `no_pdf`, `discovered` and
`parse_failed` keys pass the gate (#1118). Every reader deciding
citability (gate, render, `unit accept`, retrieval) reads it here, so
the definition cannot drift.
"""

import sqlite3

from chitragupta import ledger

# The one status meaning a real PDF was read; only `mark_parsed` writes it.
PARSED = "parsed"


def citable_citekeys(con: sqlite3.Connection) -> set[str]:
    """Every citekey whose row is `parsed`, the only rows a draft may cite."""
    return {row[0] for row in con.execute("SELECT citekey FROM items WHERE status = ?", (PARSED,))}


def unparsed_citekeys(con: sqlite3.Connection) -> dict[str, str]:
    """citekey -> status for every row that is in the ledger but not
    `parsed`, so a refusal can say why a real `.bib` entry is still not
    citable rather than calling it absent."""
    return dict(con.execute("SELECT citekey, status FROM items WHERE status <> ?", (PARSED,)))


def unparsed_on_this_host() -> dict[str, str]:
    """`unparsed_citekeys` of this host's ledger, or `{}` when there is no
    ledger it can read; for rankers outside the ledger (the embedding
    index). With no ledger, the gate still refuses the key.
    """
    try:
        with ledger.reading() as con:
            return unparsed_citekeys(con)
    except (ledger.NoLedger, ledger.StaleLedger, ledger.UnreadableLedger, sqlite3.Error):
        return {}

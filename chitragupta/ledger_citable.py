"""Which ledger rows a draft may cite: the second half of the invariant.

AGENTS.md's one rule has two halves. A citekey must be in the human's
own `.bib` export, which a ledger row proves, *and* it must have been
picked up by a real parse of a real PDF, which only `status = 'parsed'`
proves. `ledger.known_citekeys` answers the first half alone, and the
gate used it as though it answered both: a `no_pdf` web page, a
`discovered` PDF not yet read and a `parse_failed` one all passed
(#1118). Nothing in the corpus could ground a claim attributed to any of
them.

Split from `chitragupta/ledger.py`, which is at the 250-code-line cap,
and kept apart from it on purpose: `ledger` is the sync's state, and this
is the drafting layer's reading of that state. Every reader that decides
whether a key may be cited -- the gate, render's pre-gate, `unit accept`,
retrieval -- reads it here, so the definition cannot drift between them.
"""

import sqlite3

# The one status that means a real PDF was read. `ledger_paths.mark_parsed`
# is the only writer of it.
PARSED = "parsed"


def citable_citekeys(con: sqlite3.Connection) -> set[str]:
    """Every citekey whose row is `parsed`, the only rows a draft may cite."""
    return {
        row[0] for row in con.execute("SELECT citekey FROM items WHERE status = ?", (PARSED,))
    }


def unparsed_citekeys(con: sqlite3.Connection) -> dict[str, str]:
    """citekey -> status for every row that is in the ledger but not
    `parsed`, so a refusal can say why a real `.bib` entry is still not
    citable rather than calling it absent."""
    return dict(con.execute("SELECT citekey, status FROM items WHERE status <> ?", (PARSED,)))

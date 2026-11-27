"""The ledger's citekeys, for the verbatim scan to mask (#1187).

A bare citekey in prose reads as a word run no rewording removes, so the
scan blanks every key the ledger knows. No usable ledger means no keys,
not an error, as `style_bare_citekeys._ledger_keys` does.
"""

import sqlite3

from chitragupta import ledger


def _known_citekeys() -> frozenset[str]:
    # Every ledger key, parsed or not, on purpose: unlike the citable=parsed
    # rule (#1117), any key string in a draft cannot be repaired by rewording.
    try:
        with ledger.reading() as con:
            return frozenset(ledger.known_citekeys(con))
    except (ledger.NoLedger, ledger.StaleLedger, ledger.UnreadableLedger, sqlite3.Error):
        return frozenset()

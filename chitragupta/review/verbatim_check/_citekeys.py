"""The ledger's citekeys, for the verbatim scan to mask (#1187).

A bare citekey written into prose (`fixture_key_2000` outside a `[@..]`
marker) reads to the scan as a word run; no rewording of the sentence
removes it, so reporting it is noise. The scan blanks every key the
ledger knows, the way it blanks a citation marker.

Absent, stale or unreadable ledger means no keys, not an error: the scan
is a review aid and must still run on a fresh clone. This mirrors
`style_bare_citekeys._ledger_keys`.
"""

import sqlite3

from chitragupta import ledger


def _known_citekeys() -> frozenset[str]:
    try:
        with ledger.reading() as con:
            return frozenset(ledger.known_citekeys(con))
    except (ledger.NoLedger, ledger.StaleLedger, ledger.UnreadableLedger, sqlite3.Error):
        return frozenset()

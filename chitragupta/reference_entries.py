"""citekey -> formatted IEEE entry, straight from the ledger.

Below `references`, `evidence_appendix` and the corpus-layer `discover`
so none imports another (#853). Reads only the ledger, never
`bibliography.bib` (AGENTS.md: `bib_reader.py` is the sole bib reader).
"""

import json

from chitragupta import ledger
from chitragupta.references_ieee import format_entry


class MissingCitekey(KeyError):
    """A cited citekey with no ledger row (m-60). A `KeyError` subclass, so
    existing handlers still catch it, but nameable on its own."""


def entries(citekeys: list[str], con) -> dict[str, str]:
    """citekey -> its IEEE entry, without a number, for every key given.

    The one place citekeys become entries and the one place a key with no
    ledger row is refused, so a reference list and an evidence sidecar name
    sources identically. A missing row is a hard error (AGENTS.md's citekey
    invariant), never a silently dropped entry.
    """
    rows = {
        citekey: (title, year, bib_fields)
        for citekey, title, year, bib_fields in ledger.rows_for_citekeys(
            con, "citekey, title, year, bib_fields", citekeys
        )
    }
    missing = [k for k in citekeys if k not in rows]
    if missing:
        raise MissingCitekey(
            "citekey(s) cited in the draft but missing from the ledger -- "
            "run `python -m chitragupta.corpus sync`, or re-check "
            "`python -m chitragupta.draft gate` "
            f"was run and passed first: {', '.join(missing)}"
        )

    built = {}
    for key in citekeys:
        title, year, bib_fields = rows[key]
        # A pre-bib_fields row stores NULL, and bad JSON means a hand-edited
        # ledger; both fall back to title/year, and the next sync repopulates.
        try:
            fields = json.loads(bib_fields) if bib_fields else {}
        except (TypeError, ValueError):
            fields = {}
        built[key] = format_entry(key, title, year, fields)
    return built

"""citekey -> formatted IEEE entry, straight from the ledger.

The one place this project turns a set of citekeys into formatted
bibliography entries, and the one place a cited key with no ledger row
is refused. Split from `chitragupta/references.py` (#853) so the three
layers that need an entry reach it without importing each other:
`references` numbers these into a draft's References section,
`evidence_appendix` uses them as attribution lines, and the corpus-layer
`discover` shows one beside each topic member. `discover` used to import
`references` for this, which is the drafting layer's module.

Stdlib-only and reads only the ledger, never `bibliography.bib`, like
`references.py` before it (AGENTS.md: `bib_reader.py` is the sole bib
reader).
"""

import json

from chitragupta import ledger
from chitragupta.references_ieee import format_entry


class MissingCitekey(KeyError):
    """A citekey cited in a draft with no ledger row (m-60): a `KeyError`
    subclass, so every existing `except KeyError` still catches it, but a
    caller wrapping a whole pipeline can catch this one refusal by name."""


def entries(citekeys: list[str], con) -> dict[str, str]:
    """citekey -> its IEEE entry, without a number, for every key given.

    The one place this project turns a set of citekeys into formatted
    bibliography entries, and the one place a cited key with no ledger
    row is refused. `build_section` numbers what this returns;
    `chitragupta/evidence_appendix.py` uses the same entries as the
    attribution line above each quoted span, so a reference list and an
    evidence sidecar built from the same draft name their sources
    identically rather than in two spellings that could drift.

    A missing row is a hard error (AGENTS.md's citekey invariant), never
    a silently dropped entry.
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
        # A row written before the bib_fields column existed stores NULL;
        # a value that isn't valid JSON would mean a hand-edited ledger.
        # Both fall back to the title/year columns rather than failing --
        # the next `python -m chitragupta.corpus sync` repopulates either one.
        try:
            fields = json.loads(bib_fields) if bib_fields else {}
        except (TypeError, ValueError):
            fields = {}
        built[key] = format_entry(key, title, year, fields)
    return built

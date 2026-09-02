"""Encoding a `bib_reader.Reference`'s bibliographic fields into the two
JSON ledger columns: `bib_fields` and `collections`.

Split from `chitragupta/ledger_upsert.py` (issue #556), which named this
as one of its own parts in its module docstring from the day it was
created -- "the `bib_fields`/`collections` JSON encoding" -- alongside
the write path, the status transitions and the stat-before-hash check.
It is the one of the four that touches neither the connection nor the
row: pure functions from a `Reference` to a string, called once each per
upsert and by nothing else.

The split is what `docs/CODE-STANDARDS.md`'s 250-code-line ratchet is
for. `ledger_upsert.py` crossed the limit while gaining the callback
#556 needed, and the two changes before it had each bought a few lines
back by moving prose from a docstring (counted) into a comment (not
counted). A third pass at that would have been gaming a check whose
whole point is to ask "is this module holding more than one
responsibility?" -- and here the answer was already written down.

Nothing outside `ledger_upsert` imported either function, so no call
site changes and this module is deliberately not re-exported: unlike
`upsert_reference` itself, which `chitragupta/ledger.py` re-exports
because every existing caller reaches it that way, these two never had
an external caller to keep working.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Same reason chitragupta/ledger_upsert.py keeps this behind
    # TYPE_CHECKING: citation_gate.py imports chitragupta.ledger, which
    # reaches here, and must not require bibtexparser
    # (chitragupta/bib_reader.py's only dependency) just to check
    # citekeys against the ledger.
    from chitragupta.bib_reader import Reference


# Fields carried over verbatim from the BibTeX entry into the bib_fields
# column (chitragupta/ledger.py's _MIGRATIONS version 3), for chitragupta/references.py to
# format a full bibliography entry from. Deliberately a fixed allowlist
# rather than the whole entry dict: a reference manager's export carries
# per-host noise (`file` paths, `abstract`, `keywords`, timestamps,
# arbitrary `note` fields) that nothing formats and that would churn the
# ledger on every re-export. `title`/`year`/`doi` are omitted -- they have
# real columns.
_BIB_FIELDS_KEPT = (
    "author",
    "editor",
    "journal",
    "journaltitle",
    "booktitle",
    "series",
    "volume",
    "number",
    "pages",
    "publisher",
    "institution",
    "school",
    "address",
    "location",
    "edition",
    "howpublished",
    "organization",
    "eprint",
    "eprinttype",
    "archiveprefix",
    "primaryclass",
)


def collections_json(ref: Reference) -> str | None:
    """`ref`'s Zotero collection paths as a JSON array, or None for no rows.

    None rather than `"[]"` so a library exported without Better BibTeX's
    JabRef fields leaves the column NULL rather than writing an empty
    array into every row -- the two mean the same thing to a reader, and
    NULL is what a pre-migration row already holds.
    """
    return json.dumps(list(ref.collections)) if ref.collections else None


def bib_fields_json(ref: Reference) -> str | None:
    """`ref`'s formatting-relevant BibTeX fields as a JSON object.

    Returns None (SQL NULL) when the entry has none of them, so "this
    entry genuinely carries no author or venue" and "this row predates
    the column" read the same to references.py -- both fall back to the
    title/year columns, which is the same output either way.
    """
    kept = {
        key: value
        for key, value in ref.fields.items()
        if key.lower() in _BIB_FIELDS_KEPT and str(value).strip()
    }
    # sort_keys so a re-sync of an unchanged entry writes a byte-identical
    # value rather than reordering it with the export's dict order.
    return json.dumps(kept, sort_keys=True) if kept else None

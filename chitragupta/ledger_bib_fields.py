"""Encoding a `bib_reader.Reference`'s bibliographic fields into the two
JSON ledger columns: `bib_fields` and `collections`.

Split from `chitragupta/ledger_upsert.py` (issue #556): pure functions
from a `Reference` to a string, used only there, so not re-exported.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # As in ledger_upsert.py: citation_gate must not require bibtexparser.
    from chitragupta.bib_reader import Reference


# Kept for references.py to format an entry (ledger._MIGRATIONS v3). An
# allowlist, so per-host export noise (`file`, `abstract`, timestamps)
# does not churn the ledger; title/year/doi have their own columns.
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
    """`ref`'s collection slug paths as a JSON array, or None for none,
    so the column stays NULL as a pre-migration row's does.
    """
    return json.dumps(list(ref.collections)) if ref.collections else None


def bib_fields_json(ref: Reference) -> str | None:
    """`ref`'s formatting-relevant BibTeX fields as a JSON object, or None
    so "no such fields" and "predates the column" read alike.
    """
    kept = {
        key: value
        for key, value in ref.fields.items()
        if key.lower() in _BIB_FIELDS_KEPT and str(value).strip()
    }
    # sort_keys, so an unchanged entry re-syncs byte-identical.
    return json.dumps(kept, sort_keys=True) if kept else None

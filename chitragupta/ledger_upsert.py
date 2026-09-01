"""Turning a `bib_reader.Reference` into a ledger row: the write path
`chitragupta/ledger.py`'s `upsert_reference` used to hold directly.

Split from `chitragupta/ledger.py` (#441): `upsert_reference`, the
status-transition logic in `_next_status`, the PDF stat-before-hash check
(module docstring), and the `bib_fields`/`collections` JSON encoding form
one self-contained unit that never touches the schema, the migrations, or
the read-only status queries the rest of `ledger.py` still holds -- none
of it is called from anywhere else in that module.

`upsert_reference` stays reachable as `ledger.upsert_reference`, via a
module-level re-export in `ledger.py`, the same shape
`chitragupta/render_output/__init__.py` already uses for its own split:
the split is invisible to every one of this project's existing call
sites, none of which had to change.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from chitragupta import config, passages

if TYPE_CHECKING:
    # Only for the upsert_reference type hint -- citation_gate.py imports
    # chitragupta.ledger, which imports this module, and must not require
    # bibtexparser (chitragupta/bib_reader.py's only dependency) just to
    # check citekeys against the ledger.
    from chitragupta.bib_reader import Reference


def _hash_pdf(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _stat_pdf(path: str) -> tuple[int, int]:
    st = os.stat(path)
    return st.st_size, st.st_mtime_ns


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


def _collections_json(ref: Reference) -> str | None:
    """`ref`'s Zotero collection paths as a JSON array, or None for no rows.

    None rather than `"[]"` so a library exported without Better BibTeX's
    JabRef fields leaves the column NULL rather than writing an empty
    array into every row -- the two mean the same thing to a reader, and
    NULL is what a pre-migration row already holds.
    """
    return json.dumps(list(ref.collections)) if ref.collections else None


def _bib_fields_json(ref: Reference) -> str | None:
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


def _parse_outputs_present(citekey: str, parsed_path: str | None) -> bool:
    """Every file a successful parse leaves behind, not just the row.

    The ledger records *that* a parse happened. It cannot notice that the
    output has since been deleted, or that a file this project only
    started writing later was never there at all -- and either way the row
    still says "parsed", so every subsequent run skips the document and
    the gap stays open forever.

    Two things must be on disk for a citekey the ledger calls parsed:

    - the parsed text itself; and
    - the passage sidecar, when `[parser].backend` is one that resolves
      reading order. `pdf_text.extract_text` writes it for every such
      parse, empty included, so its absence means the text was produced by
      a backend (or a version of this project) that could not write one.

    That second clause is what upgrades an existing corpus: switch to
    `docling`, or install a version that keeps Docling's document model,
    and the next `sync` re-parses the documents that predate it instead of
    quietly leaving them without quotable passages. It costs one re-parse
    per affected document, once.

    Directly mirrors `chitragupta/enrich/docling_parse.py`'s `_outputs_present`,
    which exists for the same reason on the other layer's artefacts.
    """
    if not parsed_path or not Path(parsed_path).exists():
        return False
    if config.PARSER == "docling" and not passages.sidecar_path(citekey).exists():
        return False
    return True


def upsert_reference(con: sqlite3.Connection, ref: Reference, force: bool = False) -> bool:
    """Insert or update a reference's bibliographic fields.

    Returns True if the PDF content is new/changed and needs (re-)parsing.
    """
    now = datetime.now(timezone.utc).isoformat()

    row = con.execute(
        "SELECT pdf_hash, pdf_size, pdf_mtime_ns, status, failure_kind, parsed_path "
        "FROM items WHERE citekey = ?",
        (ref.citekey,),
    ).fetchone()

    pdf_size = pdf_mtime_ns = None
    pdf_hash = None
    if ref.pdf_path:
        pdf_size, pdf_mtime_ns = _stat_pdf(ref.pdf_path)
        stat_unchanged = (
            row is not None and row[0] is not None and (row[1], row[2]) == (pdf_size, pdf_mtime_ns)
        )
        # Trust an unchanged (size, mtime) instead of re-hashing -- a
        # deliberate trade-off (PR #8 review): always-hashing *would*
        # still catch a same-size edit that also preserves mtime (e.g.
        # `cp --preserve=timestamps` overwriting the file in place), which
        # this stat-first check cannot. That's judged rare enough, and
        # re-reading every PDF's bytes on every run expensive enough at
        # this corpus's scale, to accept losing that one edge case.
        pdf_hash = row[0] if stat_unchanged else _hash_pdf(ref.pdf_path)

    needs_parse = False
    if force and pdf_hash is not None:
        # `sync --reparse`: re-extract regardless of what the ledger
        # believes. The point is to recover from output that is recorded
        # as fine but isn't -- which the ledger, by definition, cannot
        # detect on its own.
        needs_parse = True
    if row is None:
        status = "discovered" if pdf_hash else "no_pdf"
        needs_parse = pdf_hash is not None
        con.execute(
            """
            INSERT INTO items
                (citekey, item_type, title, year, doi, url,
                 pdf_path, pdf_hash, pdf_size, pdf_mtime_ns, status, last_synced,
                 bib_fields, collections)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ref.citekey,
                ref.item_type,
                ref.title,
                ref.year,
                ref.doi,
                ref.url,
                ref.pdf_path,
                pdf_hash,
                pdf_size,
                pdf_mtime_ns,
                status,
                now,
                _bib_fields_json(ref),
                _collections_json(ref),
            ),
        )
    else:
        new_status, must_reparse = _next_status(row, pdf_hash, force, ref.citekey)
        needs_parse = needs_parse or must_reparse
        con.execute(
            """
            UPDATE items SET
                item_type = ?, title = ?, year = ?, doi = ?,
                url = ?, pdf_path = ?, pdf_hash = ?, pdf_size = ?, pdf_mtime_ns = ?,
                status = ?, last_synced = ?, bib_fields = ?, collections = ?
            WHERE citekey = ?
            """,
            (
                ref.item_type,
                ref.title,
                ref.year,
                ref.doi,
                ref.url,
                ref.pdf_path,
                pdf_hash,
                pdf_size,
                pdf_mtime_ns,
                new_status,
                now,
                _bib_fields_json(ref),
                _collections_json(ref),
                ref.citekey,
            ),
        )
    con.commit()
    return needs_parse


def _next_status(row, pdf_hash, force, citekey) -> tuple[str, bool]:
    """The status an existing row moves to, and whether that demands a
    re-parse beyond what `force` already decided.

    One branch for the two re-parse triggers on a byte-identical
    PDF -- outputs gone from disk, and the transient-failure
    retry below -- because their consequence is identical and
    two branches with the same body invite the implementations
    drifting apart (Sonar S1871).

    Retry a *transient* failed parse even though the PDF is
    byte-identical -- a NULL kind predates the distinction and
    counts as transient (see chitragupta/ledger.py's _MIGRATIONS version 2).
    Without this, needs_parse was true only for a new or
    changed document, so a failure stuck until the file itself
    changed -- which for a corrupt PDF is never. That was
    tolerable while failures were per-document and permanent;
    it stopped being tolerable once a worker pool could mark
    every in-flight document parse_failed on one worker's
    death. Unattended, that silently drops those documents from
    the corpus for good: each later run counts them "unchanged"
    and exits 0. A retry costs one re-parse of a genuinely bad
    PDF per run, which is visible and bounded; the alternative
    is invisible and permanent.

    A deterministic failure deliberately keeps its old status, so it is
    still counted and still makes the run exit nonzero, but it
    is not re-parsed. --reparse and editing the PDF are the two
    escape hatches for a misclassification.
    """
    old_hash, _old_size, _old_mtime_ns, old_status, old_kind, old_parsed_path = row
    if force and pdf_hash is not None:
        return "discovered", False
    if pdf_hash != old_hash:
        return ("discovered" if pdf_hash else "no_pdf"), pdf_hash is not None
    # 'discovered' rides in the same branch: it *means* "needs parsing",
    # but this path used to return needs_parse=False for it, so any run
    # that separated upsert from parse (backend unavailable, interrupt or
    # crash before the result landed) stranded the document permanently --
    # the next healthy sync counted it "unchanged" and exited 0, the
    # silent-drop failure the retry above already closed for parse_failed.
    outputs_gone = old_status == "parsed" and not _parse_outputs_present(citekey, old_parsed_path)
    transient_failure = old_status == "parse_failed" and old_kind != "deterministic"
    if pdf_hash is not None and (old_status == "discovered" or outputs_gone or transient_failure):
        return "discovered", True
    return old_status, False

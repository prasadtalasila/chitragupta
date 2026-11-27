"""Turning a `bib_reader.Reference` into a ledger row.

Split from `chitragupta/ledger.py` (#441), which re-exports
`upsert_reference`; the JSON field encoding is in
`chitragupta/ledger_bib_fields.py`.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from chitragupta import config, ledger_bib_fields, ledger_paths, passages

if TYPE_CHECKING:
    # Type hint only: citation_gate imports ledger, which imports this,
    # and must not require bibtexparser.
    from chitragupta.bib_reader import Reference

# `chitragupta.sync`, as in sync_pool.py: docs/CLI.md documents it as the
# corpus layer's logger name. Logged, because sync's stdout is a diffable
# contract.
logger = logging.getLogger("chitragupta.sync")


def _hash_pdf(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _stat_pdf(path: str) -> tuple[int, int]:
    st = os.stat(path)
    return st.st_size, st.st_mtime_ns


def _pdf_identity(ref: Reference, row, on_missing_pdf) -> tuple[int | None, int | None, str | None]:
    """`(size, mtime_ns, hash)` for this reference's PDF, or all-`None`
    when there is nothing readable behind `ref.pdf_path`."""
    if not ref.pdf_path:
        return None, None, None
    # A PDF that vanished mid-sync is recorded like a reference with no
    # file, for this run only (m-71); `pdf_path` is still written, so the
    # next sync picks it up. The `try` covers the hash too, since a
    # half-filled answer has no `_next_status` branch.
    # `on_missing_pdf` takes the exception, not a flag (#556): the cause may
    # be permission or I/O rather than absence, and
    # `sync_decide._lost_pdf_reason` tells them apart. A callback keeps the
    # policy in `sync_decide` without widening `needs_parse`.
    try:
        pdf_size, pdf_mtime_ns = _stat_pdf(ref.pdf_path)
        stat_unchanged = (
            row is not None and row[0] is not None and (row[1], row[2]) == (pdf_size, pdf_mtime_ns)
        )
        # Trust an unchanged (size, mtime) instead of re-hashing (PR #8): a
        # same-size edit that preserves mtime is missed, judged rare enough
        # against re-reading every PDF on every run.
        return pdf_size, pdf_mtime_ns, (row[0] if stat_unchanged else _hash_pdf(ref.pdf_path))
    except OSError as exc:
        logger.warning("no-pdf  %s: %s", ref.citekey, exc)
        if on_missing_pdf is not None:
            on_missing_pdf(exc)
        return None, None, None


def _parse_outputs_present(citekey: str, parsed_path: str | None) -> bool:
    """Every file a successful parse leaves behind, not just the row.

    The row cannot notice deleted output, so it would skip the document
    forever. Both the parsed text and, for a backend that resolves
    reading order, the passage sidecar must exist; a missing sidecar
    re-parses an older corpus once. Mirrors `docling_parse._outputs_present`.
    """
    # Relative to `config.PARSED_DIR` (#966). A path outside
    # `content/parsed/` reads as gone, so a relocated project heals on the
    # next sync instead of raising (#821).
    parsed = ledger_paths.parsed_file(parsed_path)
    if parsed is None or not parsed.exists():
        return False
    # An unreadable sidecar counts as gone under any backend (#844); one
    # re-parse heals it.
    state = passages.sidecar_state(passages.sidecar_path(citekey))
    return state == "ok" or (state == "absent" and config.PARSER != "docling")


def upsert_reference(
    con: sqlite3.Connection,
    ref: Reference,
    force: bool = False,
    commit: bool = True,
    on_missing_pdf=None,
) -> bool:
    """Insert or update a reference's bibliographic fields.

    Returns True if the PDF content is new/changed and needs (re-)parsing.

    `commit=False` leaves the transaction open (#511): one fsync'd
    transaction per row made a no-op sync slow and widened the windows in
    which a reader sees a half-written ledger. `on_missing_pdf` is called
    with the `OSError` for an unreadable `ref.pdf_path` (#556).
    """
    now = datetime.now(timezone.utc).isoformat()

    row = con.execute(
        "SELECT pdf_hash, pdf_size, pdf_mtime_ns, status, failure_kind, parsed_path "
        "FROM items WHERE citekey = ?",
        (ref.citekey,),
    ).fetchone()

    pdf_size, pdf_mtime_ns, pdf_hash = _pdf_identity(ref, row, on_missing_pdf)

    needs_parse = False
    if force and pdf_hash is not None:
        # `sync --reparse`: recover from output recorded as fine but not.
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
                ledger_paths.stored_pdf(ref.pdf_path),
                pdf_hash,
                pdf_size,
                pdf_mtime_ns,
                status,
                now,
                ledger_bib_fields.bib_fields_json(ref),
                ledger_bib_fields.collections_json(ref),
            ),
        )
    else:
        new_status, must_reparse = _next_status(row, pdf_hash, force, ref.citekey)
        needs_parse = needs_parse or must_reparse
        # A changed hash clears parsed_path, or stale text survives a
        # failed --reparse looking current (#490); a same-hash update keeps it.
        old_hash = row[0]
        parsed_path = None if pdf_hash != old_hash else row[5]
        con.execute(
            """
            UPDATE items SET
                item_type = ?, title = ?, year = ?, doi = ?,
                url = ?, pdf_path = ?, pdf_hash = ?, pdf_size = ?, pdf_mtime_ns = ?,
                status = ?, last_synced = ?, bib_fields = ?, collections = ?,
                parsed_path = ?
            WHERE citekey = ?
            """,
            (
                ref.item_type,
                ref.title,
                ref.year,
                ref.doi,
                ref.url,
                ledger_paths.stored_pdf(ref.pdf_path),
                pdf_hash,
                pdf_size,
                pdf_mtime_ns,
                new_status,
                now,
                ledger_bib_fields.bib_fields_json(ref),
                ledger_bib_fields.collections_json(ref),
                parsed_path,
                ref.citekey,
            ),
        )
    if commit:
        con.commit()
    return needs_parse


def _next_status(row, pdf_hash, force, citekey) -> tuple[str, bool]:
    """The status an existing row moves to, and whether that demands a
    re-parse beyond what `force` already decided.

    A *transient* failure (NULL kind included, see ledger._MIGRATIONS v2)
    is retried on a byte-identical PDF: one dead worker can mark every
    in-flight document failed, and without a retry they drop out of the
    corpus silently for good. A deterministic failure keeps its status
    and is not re-parsed; --reparse and editing the PDF are the escape
    hatches. Both triggers share one branch (Sonar S1871).
    """
    old_hash, _old_size, _old_mtime_ns, old_status, old_kind, old_parsed_path = row
    if force and pdf_hash is not None:
        return "discovered", False
    if pdf_hash != old_hash:
        return ("discovered" if pdf_hash else "no_pdf"), pdf_hash is not None
    # 'discovered' means "needs parsing": returning False stranded any
    # document whose parse was interrupted after the upsert.
    outputs_gone = old_status == "parsed" and not _parse_outputs_present(citekey, old_parsed_path)
    transient_failure = old_status == "parse_failed" and old_kind != "deterministic"
    if pdf_hash is not None and (old_status == "discovered" or outputs_gone or transient_failure):
        return "discovered", True
    return old_status, False

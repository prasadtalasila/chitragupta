"""Logging a retrieval call against a dossier, and the revision/cost
accounting built from that log.

The read side lives in `_retrieval_queries.py` (#467) and is
re-exported here so existing call sites keep working.
"""

import argparse
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from chitragupta import config
from chitragupta.dossier import RETRIEVAL_MD, _REVISION_MARKER_MODE, dossier_dir, draft_relpath
from chitragupta.dossier._create import _RETRIEVAL_TEMPLATE
from chitragupta.dossier._retrieval_queries import _retrieval_rows
from chitragupta.dossier._versions import MARK_REVISION, VersionError, take


def log_retrieval(
    draft: Path,
    mode: str,
    query: str,
    k: int,
    results: int,
    chars: int,
    collection: str | None = None,
    origin: str | None = None,
    expanded: str | None = None,
) -> Path:
    """Append one retrieval call to the dossier's `retrieval.md`.

    `collection` is the Zotero scope (#195); without it a scoped and a
    corpus-wide call wrote identical rows (#254). `expanded` is what
    acronym expansion (#789) and spelling correction (#1232) added; empty
    on old rows, which is exact. `origin` is `"declared"` or `"extended"`
    (#455); empty on old rows is a third state, not a default (see
    `recorded_queries_with_origin`). Creates the file or directory if
    missing, so no measurement is lost before `init`.

    The query is flattened onto one line: a pipe or newline would
    silently miscount rows `retrieval_cost_by_revision` reads by position.

    **Nothing here ever writes at an offset**, because parallel subagents
    can log at once. One append-mode open, template only when empty, so
    no writer overwrites another. Rejected: `exists()` then `write_text`
    (truncates, stale check) and mode `"x"` (an append between create and
    template write is lost). A duplicate header is the accepted failure:
    it loses nothing, since unparsable rows are skipped. Exactly-once
    would need a lock (docs/TOKENS.md says why not). Write atomicity is
    not claimed: a torn row costs one measurement, never another's row.
    """
    target = dossier_dir(draft)
    target.mkdir(parents=True, exist_ok=True)
    path = target / RETRIEVAL_MD
    safe_query = " ".join(query.split()).replace("|", "\\|")
    safe_collection = " ".join((collection or "").split()).replace("|", "\\|")
    safe_origin = " ".join((origin or "").split()).replace("|", "\\|")
    safe_expanded = " ".join((expanded or "").split()).replace("|", "\\|")
    # `k1`/`b` come from config, not parameters (#788): they describe the
    # ranker that ran, and a forgotten argument would write a blank cell
    # indistinguishable from an old row. Appended last, so no index moves.
    row = (
        f"| {date.today().isoformat()} | {mode} | {safe_query} | {k} | {results} | "
        f"{chars} | {safe_collection} | {safe_origin} | {safe_expanded} | "
        f"{config.RETRIEVAL_K1} | {config.RETRIEVAL_B} |\n"
    )
    with path.open("a", encoding="utf-8") as handle:
        if not handle.tell():
            handle.write(_RETRIEVAL_TEMPLATE)
        handle.write(row)
    return path


def mark_revision(draft: Path, label: str = "") -> Path:
    """Append a revision-boundary marker to the dossier's `retrieval.md`.

    Rows carry only a date, so same-day revisions would merge without
    it; `draft-reviser` calls this once per pass before any retrieval.
    Same append-only discipline as `log_retrieval`. Also snapshots the
    draft first (`_versions.take`) for `draft diff`; an unreadable store
    is warned about, never allowed to stop the pass.
    """
    if draft.is_file():
        try:
            take(draft, trigger=MARK_REVISION, revision_label=label)
        except VersionError as error:
            print(f"[warning] {error}; no snapshot taken", file=sys.stderr)
    target = dossier_dir(draft)
    target.mkdir(parents=True, exist_ok=True)
    path = target / RETRIEVAL_MD
    safe_label = " ".join(label.split()).replace("|", "\\|")
    row = (
        f"| {date.today().isoformat()} | {_REVISION_MARKER_MODE} | {safe_label} | 0 | 0 | 0 | | |\n"
    )
    with path.open("a", encoding="utf-8") as handle:
        if not handle.tell():
            handle.write(_RETRIEVAL_TEMPLATE)
        handle.write(row)
    return path


@dataclass
class RevisionCost:
    label: str
    calls: int
    chars: int


def retrieval_cost_by_revision(dossier: Path) -> list[RevisionCost]:
    """(calls, characters returned) per `mark_revision` segment.

    Boundary rows are not counted as calls. Rows before the first marker
    form an `"initial draft"` segment; unlabelled markers are numbered
    by marker order, so numbering stays stable when an empty segment is
    dropped. Empty segments are dropped. Lifetime totals are the sum of
    these (#515).
    """
    rows = _retrieval_rows(dossier)
    segments: list[RevisionCost] = []
    label = "initial draft"
    marker_index = 0
    calls = chars = 0
    for row in rows:
        if row[1] == _REVISION_MARKER_MODE:
            if calls or chars:
                segments.append(RevisionCost(label, calls, chars))
            marker_index += 1
            # Unescape the pipe `mark_revision` escaped, as for queries.
            label = row[2].replace("\\|", "|") or f"revision {marker_index}"
            calls = chars = 0
            continue
        calls += 1
        chars += int(row[5])
    if calls or chars:
        segments.append(RevisionCost(label, calls, chars))
    return segments


# Re-exported from `_retrieval_queries.py` (#467) so existing callers of
# `_retrieval.recorded_queries` and its siblings keep working.
# pylint: disable=unused-import,wrong-import-position
from chitragupta.dossier._retrieval_queries import (  # noqa: F401,E402
    recorded_queries,
    recorded_queries_with_collection,
    recorded_queries_with_evidence,
    recorded_queries_with_origin,
)

# pylint: enable=unused-import,wrong-import-position


def _cmd_mark_revision(args: argparse.Namespace) -> int:
    path = mark_revision(Path(args.draft), args.label)
    print(
        f"Marked a revision boundary in {draft_relpath(path)}"
        + (f" ({args.label!r})" if args.label else "")
        + "."
    )
    return 0

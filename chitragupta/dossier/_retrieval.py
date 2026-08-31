"""Logging a retrieval call against a dossier, and the revision/cost
accounting built from that log.

Split out of chitragupta/dossier.py (#219). `_RETRIEVAL_TEMPLATE` is imported
from `_create` rather than duplicated or promoted to `_core`, because
unlike `_SECTIONS_TEMPLATE` it has exactly one reader outside `_create`
itself (`log_retrieval`, for the same "write the header if the file
doesn't exist yet" reason every other template exists for) -- a
private name crossing one file boundary once is not the same problem
as crossing three.

The read side -- `_retrieval_rows` and the `recorded_queries` trio --
moved to `_retrieval_queries.py` (#467): #455's origin column pushed
this module back over C2, and unlike the write path and the cost
accounting below, nothing here needs those three to be defined in this
file rather than merely reachable through it. They stay importable as
`_retrieval.recorded_queries`/`_with_collection`/`_with_origin`, via the
re-export where they used to live, so no existing call site changes.
"""

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from chitragupta.dossier import RETRIEVAL_MD, _REVISION_MARKER_MODE, dossier_dir, draft_relpath
from chitragupta.dossier._create import _RETRIEVAL_TEMPLATE
from chitragupta.dossier._retrieval_queries import _retrieval_rows


def log_retrieval(
    draft: Path,
    mode: str,
    query: str,
    k: int,
    results: int,
    chars: int,
    collection: str | None = None,
    origin: str | None = None,
) -> Path:
    """Append one retrieval call to the dossier's `retrieval.md`.

    `collection` is the Zotero collection the call was scoped to
    (`retrieval.search(..., collection=...)`, #195) -- `None`/empty for a
    corpus-wide call, which is also how a row logged before this
    parameter existed reads back (#254). Without it, a scoped call and a
    corpus-wide one at the same query and `--k` wrote byte-identical
    rows, and nothing downstream could tell which had actually run.

    `origin` is `"declared"` or `"extended"` (#455) -- whether the query
    came verbatim from an `outline.md` section or was added because a
    declared section came up thin. `None`/empty for a call that named
    neither, which is also how every row logged before this parameter
    existed reads back. Unlike `collection`, that empty reading is not a
    safe default to widen into: a pre-`outline.md` call was neither
    declared nor extended, so it stays its own, third state -- see
    `recorded_queries_with_origin`.

    Creates the file if the dossier exists but predates it, and creates
    the dossier directory if a skill logged before running `init` --
    losing a measurement because the skeleton wasn't there yet would be a
    silly way to fail, and this writes nothing a later `init` would
    clobber.

    The query is flattened onto one line before it is written. A pipe
    would split the row into extra cells and a newline would split it
    into two rows -- and `retrieval_cost` reads rows positionally, so
    either one turns a logged call into a silently miscounted one rather
    than a visible error. Whitespace is collapsed with `split()`, which
    covers newlines, tabs and carriage returns together.

    **Nothing here ever writes at an offset.** That matters because
    `--log` is a flag on the retrieval CLI and a skill dispatching
    parallel subagents could hand it to all of them, so two processes
    can reach this function at once. The file is opened once, in append
    mode, and the template is written only when that open finds it
    empty -- so both the template and the row go through `O_APPEND` and
    land at whatever the end of the file is *at the time of the write*.
    A writer can therefore never overwrite what another one put there.

    Two earlier shapes could, and both are worth naming because each
    looks correct:

    - `if not path.exists(): path.write_text(TEMPLATE)` truncates, and
      the check goes stale between the two calls.
    - Creating with mode `"x"` fixes that, but publishes an empty file
      and then writes the template to it from offset 0. A second writer
      that appends a row in between has it overwritten.

    What this does *not* promise: that the template is written exactly
    once. Two writers that both find the file empty both write one, so
    the file can carry a duplicate header. That is deliberately the
    failure left in, because it loses nothing -- `retrieval_cost` skips
    any row whose last cell isn't an integer, which both the header and
    its separator are -- and `_count`'s advisory total is one high.
    Buying exactly-once would need a lock or a link-into-place dance,
    for a file whose whole point is to be cheap. See the module
    docstring, and docs/TOKENS.md for why a lock is the wrong instrument
    here.

    Write atomicity is deliberately *not* claimed. Both writes go
    through one buffered handle and may well reach the filesystem as a
    single small write -- but that is an implementation detail of how
    the template's size compares to a buffer, not behaviour to rely on:
    buffered text I/O can flush at points of its own choosing, closing
    may still issue more than one write, and POSIX does not promise that
    a write to a regular file arrives unsplit. Nothing here depends on
    any of that. `retrieval_cost` skips
    any row it cannot parse, so a torn row costs that one measurement
    and leaves every other row intact -- while a row overwritten at an
    offset would have been silently gone. The guarantee this function
    makes is the weaker, sufficient one: no writer addresses a position,
    so no writer can destroy what another wrote.
    """
    target = dossier_dir(draft)
    target.mkdir(parents=True, exist_ok=True)
    path = target / RETRIEVAL_MD
    safe_query = " ".join(query.split()).replace("|", "\\|")
    safe_collection = " ".join((collection or "").split()).replace("|", "\\|")
    safe_origin = " ".join((origin or "").split()).replace("|", "\\|")
    row = (
        f"| {date.today().isoformat()} | {mode} | {safe_query} | {k} | {results} | "
        f"{chars} | {safe_collection} | {safe_origin} |\n"
    )
    with path.open("a", encoding="utf-8") as handle:
        if not handle.tell():
            handle.write(_RETRIEVAL_TEMPLATE)
        handle.write(row)
    return path


def mark_revision(draft: Path, label: str = "") -> Path:
    """Append a revision-boundary marker to the dossier's `retrieval.md`.

    `retrieval.md` rows otherwise carry only a date (`log_retrieval` writes
    `date.today()`), and two revisions on the same day are indistinguishable
    by it. `draft-reviser`'s loop calls this once per pass, before any
    retrieval, precisely so same-day revisions don't get silently merged
    into one figure -- see `retrieval_cost_by_revision`, the reader this
    writes for.

    Shares `log_retrieval`'s append-only, no-offset-write discipline (see
    that function's docstring for why), even though nothing calls this one
    concurrently -- one write path is one fewer thing to get right twice.
    A marker with `results` and `chars` both 0 costs nothing towards
    `retrieval_cost`'s totals; it is real data only to
    `retrieval_cost_by_revision`, which reads it as a boundary rather than
    a call.
    """
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


def retrieval_cost(dossier: Path) -> tuple[int, int]:
    """(calls, characters returned) recorded in `retrieval.md`.

    Excludes `mark_revision`'s boundary rows: they record zero retrieval
    work by construction (`results` and `chars` are always 0), but without
    filtering them out here each one would still count as a "call" that
    fetched nothing, inflating this total by one per revision session.
    """
    rows = [row for row in _retrieval_rows(dossier) if row[1] != _REVISION_MARKER_MODE]
    return len(rows), sum(int(row[5]) for row in rows)


@dataclass
class RevisionCost:
    label: str
    calls: int
    chars: int


def retrieval_cost_by_revision(dossier: Path) -> list[RevisionCost]:
    """`retrieval_cost`, split at each `mark_revision` boundary.

    Rows logged before the first marker -- which is every row on a dossier
    revised before this existed, or one revised without `draft-reviser`'s
    loop -- form a leading segment labelled `"initial draft"`. Each marker
    after that starts a new segment, labelled with the text passed to
    `mark_revision` or, if none was given, `"revision N"` counted by marker
    order (so numbering stays stable even if an earlier revision logged no
    calls and is dropped below).

    A segment with no calls is dropped rather than reported as a
    zero-cost revision -- `mark-revision` costs nothing to call even when
    `draft-reviser` step 4 decides no search is needed, and a list of
    revisions padded with real ones that did nothing would obscure the
    ones that did.
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
            # `mark_revision` escapes a pipe in the label the same way
            # `log_retrieval` escapes one in a query, so the row parses;
            # unescape it back for display, same as `recorded_queries`
            # does for a query cell.
            label = row[2].replace("\\|", "|") or f"revision {marker_index}"
            calls = chars = 0
            continue
        calls += 1
        chars += int(row[5])
    if calls or chars:
        segments.append(RevisionCost(label, calls, chars))
    return segments


# `recorded_queries`, `_with_collection` and `_with_origin` moved to
# `_retrieval_queries.py` (#467) -- re-exported here, at the spot they
# used to be defined, so `_retrieval.recorded_queries` and its two
# siblings keep working for every caller this project already has
# (`_with_evidence`, #480, never lived here and is re-exported only so
# that the family reads as one from either module)
# (`chitragupta/review/agenda/_recheck.py`, `chitragupta/dossier/_drift.py`,
# `chitragupta/dossier/_outline.py`, and this module's own test suite)
# without a mechanical rename across files the split didn't otherwise
# need to touch.
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

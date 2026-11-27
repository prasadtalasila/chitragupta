"""`agenda --baseline`'s refresh: re-run the eight aids over the draft
before the rebuild, and say which of them actually refreshed.

Refreshing first is the point of `--baseline`: re-running `agenda` alone
reads pre-edit `.json` and silently reports unresolved findings resolved.
`support` is included despite its ~21-60 s model-load floor
(docs/REVIEW.md), or `claim-support` goes stale. Aid modules are looked up
in `review._registry.AIDS` at call time (#850): a top-level import would
be a cycle through `review/__main__.py`.
"""

import contextlib
import io
import os
import sys
from pathlib import Path

from chitragupta import dossier, ledger, review
from chitragupta.dossier._retrieval import recorded_queries
from chitragupta.review.agenda._sources import AID_NAMES


def _coverage_queries(draft: Path) -> list[str]:
    """The queries `coverage` is re-run with: the draft's `retrieval.md`
    rows via `recorded_queries`, revision boundary rows excluded. Empty
    when there is no dossier or no such row, and the caller then skips
    `coverage`; fabricating a query would invent exactly what this
    pipeline refuses.
    """
    try:
        directory = dossier.dossier_dir(draft)
    except dossier.DossierError:
        return []
    if not directory.is_dir():
        return []
    return recorded_queries(directory)


def _aid_argv(aid: str, draft: Path, queries: list[str]) -> list[str] | None:
    """One aid's refresh argv, or `None` for one that must be skipped.

    Everything runs at `--formats md`, saving ~2.5 s a cycle (Decision 6,
    `plans/f3-agenda-reviser.md`); stale `.tex`/`.pdf` are acceptable as
    reports are regenerable. Three aids differ, each a `SystemExit(2)` if
    wrong: `provenance` has no `--write`, `verbatim` needs `scan` first,
    and `coverage` requires `--query`. A skipped aid's existing `.json` is
    read as-is.
    """
    if aid == "provenance":
        return [str(draft), "--formats", "md"]
    if aid == "verbatim":
        return ["scan", str(draft), "--write", "--formats", "md"]
    if aid == "coverage":
        if not queries:
            return None
        flags = [flag for query in queries for flag in ("--query", query)]
        return [str(draft), *flags, "--write", "--formats", "md"]
    return [str(draft), "--write", "--formats", "md"]


def _mtime_ns(path: Path) -> int | None:
    try:
        return path.stat().st_mtime_ns
    except FileNotFoundError:
        return None


def _snapshot(path: Path) -> tuple[int | None, bytes | None]:
    """`path`'s mtime and bytes before an aid runs, or `(None, None)`."""
    try:
        return path.stat().st_mtime_ns, path.read_bytes()
    except FileNotFoundError:
        return None, None


def _restore(path: Path, snapshot: tuple[int | None, bytes | None]) -> None:
    """Put back what `_snapshot` saw, if a raising aid changed it (#916).

    A failed run's `.json` would otherwise be read as trusted by the next
    bare `agenda`; the old bytes return with their own mtime so staleness
    checks see their real age, and a file the run created is removed.
    "Changed" is bytes or mtime, since a coarse-timestamp rewrite can keep
    the old mtime.
    """
    mtime, content = snapshot
    if _snapshot(path) == snapshot:
        return
    if content is None:
        path.unlink(missing_ok=True)
        return
    path.write_bytes(content)
    os.utime(path, ns=(mtime, mtime))


# `--baseline`'s one up-front ledger check (#893), so a missing ledger is
# not caught aid by aid in `refresh_aids` (that is the mid-run fallback).
# `read_connection`, so a ledger needing a sync is refused too; the
# `[error]` line and exit 1 match `review/__main__.py`.
def ledger_refusal() -> int | None:
    """`1`, with the sync instruction on stderr, when there is no
    ledger to read or it needs a sync; `None` when there is one."""
    try:
        ledger.read_connection().close()
    except ledger.NoLedger as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    return None


def _one_line(exc: Exception) -> str:
    """`exc` as `Type: first line of its message`, or the bare type name.
    One line for the report header; the first, since `NoLedger`'s second
    line is the sync instruction `agenda.run` prints up front.
    """
    lines = str(exc).strip().splitlines()
    return f"{type(exc).__name__}: {lines[0]}" if lines else type(exc).__name__


def refresh_aids(draft: Path) -> tuple[dict[str, bool | None], dict[str, str]]:
    """Re-run the eight aids over `draft` and return
    `({aid: refreshed}, {aid: error})`, the second only for aids that raised.

    `True` means exit 0 and the `.json` (re)written by this call; `False`
    is any other outcome, including an exit 0 that wrote nothing
    (`claim_support` without the enrich stack), since the old `.json`
    would otherwise be served as this edit's findings (#837). `None` is
    `coverage` with no recorded query. "Written" is an `st_mtime_ns` change:
    a coarse filesystem can read a real refresh as not refreshed, the safe
    direction.

    Only `Exception` is caught (#893): what the aid wrote is undone
    (`_restore`) and its reason goes to the map and a stderr `[warn]`.
    `SystemExit` stays loud, since a wrong argv is this module's bug, as
    does `KeyboardInterrupt`. Each `main()`'s stdout is discarded, which
    would otherwise corrupt `--json` output.
    """
    from chitragupta.review._registry import AIDS  # cycle: see the module docstring

    queries = _coverage_queries(draft)
    refreshed: dict[str, bool | None] = {}
    errors: dict[str, str] = {}
    for aid in AID_NAMES:
        argv = _aid_argv(aid, draft, queries)
        if argv is None:
            refreshed[aid] = None
            continue
        path = review.report_path(draft, aid, "json")
        # Read for every aid: once it has raised, the old bytes are gone.
        snapshot = _snapshot(path)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                code = AIDS[aid][0].main(argv)
        except Exception as exc:  # noqa: BLE001 -- see docstring: one aid must not sink the recheck
            errors[aid] = _one_line(exc)
            _restore(path, snapshot)
            print(f"[warn] {aid} raised during refresh: {errors[aid]}", file=sys.stderr)
            refreshed[aid] = False
            continue
        refreshed[aid] = code == 0 and _mtime_ns(path) not in (None, snapshot[0])
    return refreshed, errors

"""`agenda --baseline`'s refresh: re-run the eight aids over the draft
before the rebuild, and say which of them actually refreshed.

Refreshing first is the whole point of `--baseline`, and what a skill
re-deriving this loop in prose gets wrong **silently**: a naive re-run of
`agenda` alone reads the aids' pre-edit `.json` and reports a finding
resolved that is not. `support` is one of the eight for the same reason
as the other seven -- skipping it would leave `claim-support` stale --
at the cost of its own ~21--60 s model-load floor (docs/REVIEW.md) every
call. Split out of `_recheck.py`, which keeps the comparison, when #837
made the refresh report per-aid state and the two together crossed the
250-code-line cap.

**The aid modules are looked up in `review._registry.AIDS` at call time**
(#850). `review/__main__.py` imports `chitragupta.review.agenda`, which
imports this module, so a top-level import of the registry would be a
cycle; this module used to restate the eight-entry map instead, a copy
that adding an aid had to edit. Imported inside `refresh_aids`, the
registry is reached only after every aid module has finished loading.
It costs nothing a refresh notices: under `python -m chitragupta.review`
the aids are already loaded, and otherwise loading them is milliseconds
against the seconds each aid the refresh runs takes.
"""

import contextlib
import io
from pathlib import Path

from chitragupta import dossier, review
from chitragupta.dossier._retrieval import recorded_queries
from chitragupta.review.agenda._sources import AID_NAMES


def _coverage_queries(draft: Path) -> list[str]:
    """The queries `coverage` is re-run with -- the draft's own
    `retrieval.md` rows, revision markers excluded.

    That source is `f-auto-improvement-adoption.md`'s Q5 answer, and
    already solved: `recorded_queries` deduplicates, preserves first-seen
    order, and skips `mark_revision`'s boundary rows, whose third cell
    holds a `--label` and not a query. Empty for a draft outside
    `content/drafts/`, one with no dossier directory yet, and one
    recording no non-revision row -- the degrade-rather-than-raise
    posture `_sources._read_drift` keeps. The caller then skips
    `coverage` entirely; fabricating a query to avoid that would invent
    the very thing this pipeline exists to refuse.
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

    Everything runs at `--formats md`: only three of the eight render
    beside the Markdown at all, and dropping those saves ~2.5 s a cycle
    (Decision 6 of `plans/f3-agenda-reviser.md`, measured). Each aid's
    `.tex`/`.pdf` therefore goes stale against its `.md` during a pass --
    acceptable only because reports are regenerable and untimestamped.

    Three of the eight depart from the common shape, and each is an
    argparse `SystemExit(2)` rather than quiet misbehaviour if got wrong:
    `provenance` has **no `--write` flag** (it files unconditionally, the
    convention `agenda` itself follows); `verbatim` takes a subcommand,
    so `scan` has to be argv[0]; and `coverage`'s `--query` is
    `required=True`. `None` means skip, and that aid's existing `.json`,
    if any, is read as-is by the rebuild -- like any other aid whose
    report is simply absent.
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


def refresh_aids(draft: Path) -> dict[str, bool | None]:
    """Re-run the eight aids over `draft`, so the rebuild that follows
    reads this edit's findings and not the last one's, and return
    `{aid: refreshed}` for all eight.

    `True` means the aid exited 0 **and** its `.json` was (re)written by
    this call. `False` is every other outcome of running it: a non-zero
    exit (`verbatim` and `coverage` return 1 on a refusal), or an exit 0
    that wrote nothing -- `claim_support` without the enrich stack does
    exactly that, by design. `None` is an aid deliberately not run:
    `coverage` with no recorded query to run it with.

    The exit code alone cannot carry this, which is why the value is a
    verdict rather than the raw code #837's proposal named: the silent
    case is the exit-0 one. Either way the previous run's `.json` is
    still on disk and the rebuild reads it, so without this the agenda
    would serve last run's findings as this edit's -- the failure this
    mode exists to prevent. The caller threads the map into
    `_sources.collect`, which marks each `AidSource`, and a not-refreshed
    aid's items are then left out of the objective count and the
    comparison rather than trusted.

    "Written" is an `st_mtime_ns` change (or a file appearing), compared
    before and after the call. Contents are not compared: a refresh
    finding nothing new rewrites byte-identical JSON. On a filesystem
    whose timestamps are coarser than two consecutive writes, a real
    refresh can read as not refreshed -- the safe direction, which costs
    a cycle rather than counting stale findings as current.

    **Each `main()` runs with stdout redirected into a throwaway buffer.**
    All eight print a written-files summary of their own, which under
    `agenda --baseline ... --json` would land on stdout ahead of the
    payload and corrupt a caller piping it through `json.loads`.
    Discarding it is right rather than convenient: it reports files this
    command asked for on the caller's behalf and never promised to show.
    """
    from chitragupta.review._registry import AIDS  # cycle: see the module docstring

    queries = _coverage_queries(draft)
    refreshed: dict[str, bool | None] = {}
    for aid in AID_NAMES:
        argv = _aid_argv(aid, draft, queries)
        if argv is None:
            refreshed[aid] = None
            continue
        path = review.report_path(draft, aid, "json")
        before = _mtime_ns(path)
        with contextlib.redirect_stdout(io.StringIO()):
            code = AIDS[aid][0].main(argv)
        refreshed[aid] = code == 0 and _mtime_ns(path) not in (None, before)
    return refreshed

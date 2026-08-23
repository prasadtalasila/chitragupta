"""Formatting a `Drift` (or several, for `dossier status --all`) for a
person to read, and the CLI handler that's the only caller of either.

Split out of `_drift` (#219) once the combined module was over this
project's 250-code-line cap -- computing a Drift and printing one are
genuinely separable, confirmed by `status()` in `_status.py` needing
the former and never the latter.
"""

import json

from chitragupta import config
from chitragupta.dossier import draft_relpath
from chitragupta.dossier._drift import Drift

# How many findings of one kind to print before summarising the rest.
# A drift report is read to decide what to do next, not as a manifest;
# what it must never do is truncate silently, so the remainder is always
# counted out loud.
_SHOWN = 10


def _print_drift(report: Drift) -> None:
    marker = "" if report.draft else "   (draft missing)"
    if not report.corpus_available:
        print(f"  {report.name}{marker}\n    drift unavailable -- no readable ledger.")
        return
    if report.clean:
        moved = " (corpus moved, nothing this dossier relies on)" if report.drifted else ""
        print(f"  {report.name}{marker}\n    no drift{moved}.")
        return

    print(f"  {report.name}{marker}")
    if report.missing:
        _print_capped(
            f"    {len(report.missing)} cited citekey(s) no longer in the ledger:",
            list(report.missing.items()),
            _render_missing,
        )
    if report.candidates:
        _print_capped(
            f"    {len(report.candidates)} new candidate(s) matching this "
            "dossier's recorded queries:",
            report.candidates,
            _render_candidate,
        )
    # Only alongside a real finding. On its own this is true on every
    # sweep forever, so printing it unconditionally would bury the drift
    # it is meant to help act on.
    if report.reconsider:
        _print_capped(
            f"    {len(report.reconsider)} previously rejected paper(s) these queries still reach:",
            report.reconsider,
            _render_reconsider,
        )


def _print_capped(header: str, items: list, render) -> None:
    """A listing capped at _SHOWN entries that always counts its
    remainder out loud -- the never-truncate-silently rule stated at
    _SHOWN's definition, in one place instead of three."""
    print(header)
    for item in items[:_SHOWN]:
        render(item)
    if len(items) > _SHOWN:
        print(f"      ... and {len(items) - _SHOWN} more")


def _render_missing(item) -> None:
    citekey, in_sections = item
    where = f"  cited in: {', '.join(in_sections)}" if in_sections else ""
    print(f"      {citekey}{where}")


def _render_candidate(candidate) -> None:
    title = f"  {candidate.title}" if candidate.title else ""
    print(f"      {candidate.citekey}{title}")
    print(f"        surfaced by: {'; '.join(candidate.queries)}")


def _render_reconsider(entry) -> None:
    title = f"  {entry.title}" if entry.title else ""
    print(f"      {entry.citekey}{title}")
    print(f"        rejected because: {entry.reason}")


def _cmd_status_all(reports: list[Drift], as_json: bool) -> int:
    if as_json:
        print(json.dumps({"dossiers": [r.as_dict() for r in reports]}, indent=2))
    elif not reports:
        print(f"No dossiers under {draft_relpath(config.DOSSIERS_DIR)}.")
    else:
        _print_drift_summary(reports)
    return 0


def _print_drift_summary(reports: list[Drift]) -> None:
    """The human-readable half of `status --all`: every dossier's drift,
    then the how-to-read-this coda. Split from `_cmd_status_all` so the
    command keeps one exit and one return -- this text report cannot fail,
    which is exactly why it returns nothing."""
    print(f"Corpus drift across {len(reports)} dossier(s):\n")
    for report in reports:
        _print_drift(report)
    stale = [r for r in reports if not r.clean]
    # A dossier with no readable ledger has no findings, which is not the
    # same as having none to find. Reporting it as current would be the
    # one way this command could actively mislead: "nothing to do here"
    # asserted about a check that never ran.
    unknown = [r for r in reports if not r.corpus_available]
    print()
    if unknown:
        print(
            f"  {len(unknown)} of {len(reports)} dossier(s) could not be checked: "
            f"no readable ledger at {config.LEDGER_PATH}."
        )
        print(
            "  Run `python -m chitragupta.corpus sync` to build one; until then drift is unknown,"
        )
        print("  not absent.")
    if not stale:
        if not unknown:
            print("  Every dossier is current against the corpus.")
        return
    print(f"  {len(stale)} of {len(reports)} dossier(s) have drifted.")
    print("  A missing citekey is a defect: the draft cites what the corpus no")
    print("  longer has. A candidate is a decision, not a defect -- re-search only")
    print("  if the change you are making touches a sub-theme it could bear on.")
    if any(r.reconsider for r in stale):
        print("  Candidates exclude everything in `rejected.md`; the reconsider list is")
        print("  the exception, shown with its reason so you can judge whether it holds.")
    else:
        print("  `rejected.md` was already subtracted, so nothing here was turned down before.")

"""Reads the nine inputs `agenda` merges, each degrading to "absent"
rather than raising -- the same posture every review aid already keeps
towards an optional input.

Seven are on-disk artefacts: the other aids' own `<stem>.<aid>.json`,
written by an earlier `--json`/`--write` run and read here, never
recomputed. Two have no on-disk artefact at all and are computed
in-process instead: `style_check.check()` (the `prose` class; nothing
ever calls `review.write_json` for it, since it is a drafting-layer
command, not a review aid) and `dossier.drift()` (the `missing-citekey`
and `candidate` classes).
"""

import json
from dataclasses import dataclass
from pathlib import Path

from chitragupta import dossier, review, style_check
from chitragupta.dossier._drift import Drift

# The seven existing review aids, in `review.AIDS`'s own order. Read for
# completeness -- `synthesis` and `figure` carry no item class (see
# `_items.py`) but are still named in the header as read, not silently
# dropped.
AID_NAMES = (
    "provenance",
    "verbatim",
    "coverage",
    "synthesis",
    "figure",
    "uncited",
    "quotation",
)


@dataclass
class AidSource:
    """One of the seven aids' `.json`, as `agenda` sees it.

    `stale` is a caveat on the report, never a merge signal: a finding
    from a report older than the draft may still be true, so staleness
    is named in the header and never changes which items are computed
    from `data` (see the module docstring's determinism note).
    """

    available: bool = False
    stale: bool = False
    data: dict | None = None


@dataclass
class StyleSource:
    """`style_check.check()`'s result. `partial` means Vale did not run
    (`vale_error` was set) -- `prose` is under-reported, not empty, and
    the header must say so by name since it is otherwise the most
    populous class."""

    available: bool = False
    partial: bool = False
    data: dict | None = None


@dataclass
class DriftSource:
    """The dossier's drift report. `available=False` covers both "this
    draft is not under content/drafts/" and "it is, but no dossier was
    ever created for it" -- both are the decided reduced-source-set case,
    not a refusal. `corpus_available` is a *different* absence
    (dossier exists, ledger doesn't) and is named separately."""

    available: bool = False
    corpus_available: bool = False
    data: Drift | None = None


@dataclass
class Sources:
    aids: dict[str, AidSource]
    style: StyleSource
    drift: DriftSource


def _read_aid_json(draft: Path, aid: str) -> AidSource:
    path = review.report_path(draft, aid, "json")
    if not path.is_file():
        return AidSource()
    data = json.loads(path.read_text(encoding="utf-8"))
    stale = path.stat().st_mtime < draft.stat().st_mtime
    return AidSource(available=True, stale=stale, data=data)


def _read_style(draft: Path) -> StyleSource:
    result = style_check.check(draft)
    return StyleSource(available=True, partial=bool(result["vale_error"]), data=result)


def _read_drift(draft: Path) -> DriftSource:
    try:
        directory = dossier.dossier_dir(draft)
    except dossier.DossierError:
        return DriftSource()
    if not directory.is_dir():
        return DriftSource()
    report = dossier.drift(directory)
    return DriftSource(available=True, corpus_available=report.corpus_available, data=report)


def collect(draft: Path) -> Sources:
    """Every input `agenda` reads for `draft`, each degraded rather than
    raised where it is absent."""
    return Sources(
        aids={aid: _read_aid_json(draft, aid) for aid in AID_NAMES},
        style=_read_style(draft),
        drift=_read_drift(draft),
    )

"""Reads the ten inputs `agenda` merges, each degrading to "absent"
rather than raising -- the same posture every review aid already keeps
towards an optional input.

Eight are on-disk artefacts: the other aids' own `<stem>.<aid>.json`,
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

# The review aids agenda reads, in `review.AIDS`'s own order -- not all
# of `review.AIDS`: `agenda` itself is excluded, and so is `union`.
#
# `union` reads an *assembled book* rather than a draft, and this is a
# per-draft worklist: there is no draft path to key its `.json` off, and
# a citekey dropped between a unit and the assembly is a fact about the
# assembly, not about any one unit's prose. docs/PERFORMANCE.md leaves
# it out of the draft-review cost figures on the same ground. This
# comment said "only `agenda` itself is excluded" through the release
# that made `union` the tenth aid, which is what #573 was: the sentence
# that pins the invariant down was the one thing nothing checked.
# `TestAidNames` now asserts the relationship, so an eleventh aid has to
# decide rather than inherit this silently.
#
# `support`'s
# findings carry no `band`, so `unsupported_claim_items`
# (`_items_findings.py`) cannot treat it as a second source for
# `unsupported-claim` -- but `claim_support_items` reads it as its own
# `claim-support` class instead, ranked rather than thresholded, so R3
# (docs/CODE-STANDARDS.md) is not in tension with reading it here.
# `synthesis` and `figure` carry no item class (see `_items.py`) but are
# still named in the header as read, not silently dropped.
AID_NAMES = (
    "provenance",
    "verbatim",
    "coverage",
    "synthesis",
    "figure",
    "uncited",
    "quotation",
    "support",
)


@dataclass
class AidSource:
    """One of the eight aids' `.json`, as `agenda` sees it.

    `stale` is a caveat on the report, never a merge signal: a finding
    from a report older than the draft may still be true, so staleness
    is named in the header and never changes which items are computed
    from `data` (see the module docstring's determinism note).
    """

    available: bool = False
    stale: bool = False
    data: dict | None = None
    reason: str | None = None


@dataclass
class StyleSource:
    """`style_check.check()`'s result. `partial` means Vale did not run
    (`vale_error` was set) -- `prose` is under-reported, not empty, and
    the header must say so by name because `prose` is an *unattended*
    class (issue 421): a silently short list of it under-counts
    `Agenda.objective_class_count`, which a re-run loop terminates on.

    It is not the most populous class, which this docstring claimed
    until the measurement in `plans/f3-agenda-reviser.md`: prose runs
    0--6 per draft on the four real drafts, against `candidate`'s
    7--155."""

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
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        # A truncated or hand-edited sidecar must not take the whole
        # agenda down (#496) -- this class degrades to absent like every
        # other absent input the module docstring lists, with the reason
        # carried along rather than swallowed.
        return AidSource(reason=f"{path}: {exc}")
    stale = path.stat().st_mtime < draft.stat().st_mtime
    return AidSource(available=True, stale=stale, data=data)


def _read_style(draft: Path) -> StyleSource:
    # propose=False: the agenda never reads `proposed_language` (m-73,
    # issue #495), so the two extra Vale runs `check()` would otherwise
    # spend computing it on every unset-dialect draft are pure waste here.
    result = style_check.check(draft, propose=False)
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

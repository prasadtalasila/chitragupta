"""Reads the twelve inputs `agenda` merges, each degrading to "absent"
rather than raising.

Eight are the aids' `<stem>.<aid>.json`, read, never recomputed. Three
have no artefact and are computed in-process: `style_check.check()`
(`prose`), `dossier.drift()` (`missing-citekey`, `candidate`) and
`recorded_but_uncited()`. The twelfth, the acceptance record
(`_accept.py`), raises no class; it only keeps accepted items off the
worklist.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import dossier, review, style_check
from chitragupta.dossier._draft_fingerprint import recorded_but_uncited
from chitragupta.dossier._drift import Drift
from chitragupta.review.agenda import _accept

# The aids agenda reads, in `review.AIDS` order, derived (#850) so a new aid
# is included unless named here. `TestAidNames` pins this (#573).
#
# `union` is excluded: its findings are about an assembled book, with no
# sentence to fix in the draft under review. `digest` is excluded: its
# classes mean nothing outside a digest (#991), and `--baseline` would run
# it over prose that is not one; `review-digest` works its report.
# `support` has no `band`, so it feeds its own ranked `claim-support`
# class, not `unsupported-claim` (R3). `synthesis` and `figure` yield no
# items but are named in the header as read.
AID_NAMES = tuple(aid for aid in review.AIDS if aid not in ("agenda", "union", "digest"))

# Item classes raised from an aid's `.json`, and which aid. The other three
# are computed in-process each run, so no failed refresh leaves them stale.
# `TestClassAids` pins this map.
CLASS_AIDS = {
    "verbatim-run": "verbatim",
    "unsupported-claim": "provenance",
    "claim-support": "support",
    "uncited-claim": "uncited",
    "misquoted": "quotation",
}


def unverified_classes(aids) -> set[str]:
    """The item classes whose evidence comes from one of `aids`, which a
    not-refreshed aid leaves unverified (#837)."""
    return {cls for cls, aid in CLASS_AIDS.items() if aid in aids}


@dataclass
class AidSource:
    """One of the eight aids' `.json`, as `agenda` sees it.

    `stale` (older than the draft) is a header caveat, never a merge
    signal. `refreshed` is `--baseline`'s account: `None` if not attempted,
    `False` if failed, which keeps that aid's items out of
    `Agenda.objective_class_count` (#837). `refresh_error` is the reason a
    refresh raised (#893), distinct from `reason` ("could not be read");
    both can hold at once.
    """

    available: bool = False
    stale: bool = False
    data: dict | None = None
    reason: str | None = None
    refreshed: bool | None = None
    refresh_error: str | None = None

    def flags(self) -> dict:
        return {
            "available": self.available,
            "stale": self.stale,
            "refreshed": self.refreshed,
            "refresh_error": self.refresh_error,
        }


@dataclass
class StyleSource:
    """`style_check.check()`'s result. `partial` means Vale did not run, so
    `prose`, an unattended class (issue 421), is under-reported; the header
    must say so, or `Agenda.objective_class_count` is silently short.
    """

    available: bool = False
    partial: bool = False
    data: dict | None = None
    reason: str | None = None


@dataclass
class DriftSource:
    """The dossier's drift report. `available=False` (not under
    content/drafts/, or no dossier) is a reduced source set, not a refusal;
    `corpus_available` is the separate dossier-but-no-ledger case."""

    available: bool = False
    corpus_available: bool = False
    data: Drift | None = None


@dataclass
class RecordedSource:
    """The dossier's recorded-but-uncited citekeys (#701).

    Separate from `DriftSource` because it asks whether the draft text
    still cites what the dossier records, which needs no ledger. Its
    `available=False` means what `DriftSource`'s does.
    """

    available: bool = False
    data: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class Sources:
    aids: dict[str, AidSource]
    style: StyleSource
    drift: DriftSource
    recorded: RecordedSource
    # Read here so the header can name it present, absent or unreadable;
    # defaulted so a hand-built `Sources` keeps working.
    accepted: _accept.AcceptedSource = field(default_factory=_accept.AcceptedSource)

    def not_refreshed(self) -> list[str]:
        return [aid for aid, source in self.aids.items() if source.refreshed is False]


def _read_aid_json(draft: Path, aid: str) -> AidSource:
    path = review.report_path(draft, aid, "json")
    if not path.is_file():
        return AidSource()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        # A truncated or hand-edited sidecar degrades to absent with its reason,
        # rather than taking the agenda down (#496).
        return AidSource(reason=f"{path}: {exc}")
    stale = path.stat().st_mtime < draft.stat().st_mtime
    return AidSource(available=True, stale=stale, data=data)


def _read_style(draft: Path) -> StyleSource:
    # propose=False: the agenda never reads `proposed_language` (#495), so
    # the two extra Vale runs would be waste.
    try:
        result = style_check.check(draft, propose=False)
    except ValueError as exc:
        # A broken `style_exceptions.toml` (#1187) degrades to not run, with
        # the reason, rather than crashing or reading as "no findings".
        return StyleSource(reason=str(exc))
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


def _read_recorded(draft: Path) -> RecordedSource:
    try:
        directory = dossier.dossier_dir(draft)
    except dossier.DossierError:
        return RecordedSource()
    if not directory.is_dir():
        return RecordedSource()
    return RecordedSource(available=True, data=recorded_but_uncited(draft))


def collect(
    draft: Path,
    refreshed: "dict[str, bool | None] | None" = None,
    errors: "dict[str, str] | None" = None,
) -> Sources:
    """Every input `agenda` reads for `draft`, each degraded rather than
    raised where absent. `refreshed` and `errors` are
    `_refresh.refresh_aids`' maps under `--baseline`, else `None`."""
    aids = {aid: _read_aid_json(draft, aid) for aid in AID_NAMES}
    for aid, state in (refreshed or {}).items():
        aids[aid].refreshed = state
    for aid, error in (errors or {}).items():
        aids[aid].refresh_error = error
    return Sources(
        aids=aids,
        style=_read_style(draft),
        drift=_read_drift(draft),
        recorded=_read_recorded(draft),
        accepted=_accept.load(draft),
    )

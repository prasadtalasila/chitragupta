"""`Item`, the worklist-entry type, plus the two drift-based extractors
(`missing-citekey`, `candidate`) and the `all_items` orchestrator. The
other seven classes' extractors -- reading the other aids' `.json` and
`style_check`'s findings -- are `_items_findings.py`, split out once the
two halves together crossed the 250-code-line cap.
"""

from dataclasses import dataclass, field

from chitragupta.dossier._drift import Drift
from chitragupta.dossier._sections import Section
from chitragupta.review.agenda._identity import item_id

# The item-class table's own order (docs/AUTO-IMPROVEMENT.md).
CLASSES = (
    "missing-citekey",
    "verbatim-run",
    "prose",
    "unsupported-claim",
    "claim-support",
    "uncited-source",
    "uncited-claim",
    "misquoted",
    "candidate",
)


@dataclass
class Item:
    id: str
    cls: str
    section: str | None
    citekey: str | None
    line: int | None
    unattended: bool
    summary: str
    detail: dict = field(default_factory=dict)


def missing_citekey_items(drift: Drift | None) -> list[Item]:
    """One item per citekey the draft cites that the corpus no longer
    has -- unattended, per the decided answer to the issue's open
    question. Anchored on the first of possibly several citing sections;
    the full list survives in `detail`."""
    if drift is None:
        return []
    items = []
    for citekey, section_names in sorted(drift.missing.items()):
        section = section_names[0] if section_names else None
        items.append(
            Item(
                id=item_id("drift", "missing-citekey", section, citekey, citekey),
                cls="missing-citekey",
                section=section,
                citekey=citekey,
                line=None,
                unattended=True,
                summary=f"`{citekey}` is cited but no longer in the corpus",
                detail={"sections": section_names},
            )
        )
    return items


def candidate_items(drift: Drift | None) -> list[Item]:
    """One item per paper the corpus gained that this draft's own
    recorded queries would surface. `drift.reconsider` never produces an
    item under any state: `drift()` already excludes `rejected.md`
    citekeys from `.candidates` via `cited_citekeys()`'s
    `MENTIONED_FILES`, so "a declined candidate is never re-proposed" is
    enforced by that call, not filtered here."""
    if drift is None:
        return []
    items = []
    for candidate in sorted(drift.candidates, key=lambda c: c.citekey):
        items.append(
            Item(
                id=item_id("drift", "candidate", None, candidate.citekey, candidate.citekey),
                cls="candidate",
                section=None,
                citekey=candidate.citekey,
                line=None,
                unattended=False,
                summary=f"`{candidate.citekey}` ({candidate.title}) matches this draft's "
                "own queries but is never cited",
                detail={"queries": candidate.queries},
            )
        )
    return items


def all_items(sources, sections: list[Section]) -> list[Item]:
    """Every item from every class, unordered and undeduplicated --
    `_dedup.merge` and `_order.sort` do the rest."""
    from chitragupta.review.agenda import _items_findings as f

    return [
        *missing_citekey_items(sources.drift.data),
        *f.verbatim_run_items(sources.aids["verbatim"], sections),
        *f.prose_items(sources.style, sections),
        *f.unsupported_claim_items(sources.aids["provenance"], sections),
        *f.claim_support_items(sources.aids["support"], sections),
        *f.uncited_source_items(sources.aids["coverage"]),
        *f.uncited_claim_items(sources.aids["uncited"], sections),
        *f.misquoted_items(sources.aids["quotation"]),
        *candidate_items(sources.drift.data),
    ]

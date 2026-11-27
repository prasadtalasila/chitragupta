"""`Item`, the worklist-entry type, plus the two dossier-based
extractors (`missing-citekey`, `recorded-but-uncited`) and `all_items`.
The aid-reading extractors are `_items_findings.py`.
"""

from dataclasses import dataclass, field

from chitragupta.dossier._drift import Drift
from chitragupta.dossier._sections import Section
from chitragupta.review.agenda._identity import item_id
from chitragupta.review.agenda._sources import RecordedSource

# The item-class table's own order (docs/AUTO-IMPROVEMENT.md).
#
# `uncited-source` and `candidate` were removed: not citing a surfaced
# paper is the common, correct outcome, and that volume cost a person
# triage every cycle. Coverage and `dossier status` still report them.
# `recorded-but-uncited` stays: it is an inconsistency between dossier and
# draft, not a paper someone declined.
CLASSES = (
    "missing-citekey",
    "recorded-but-uncited",
    "verbatim-run",
    "prose",
    "unsupported-claim",
    "claim-support",
    "uncited-claim",
    "misquoted",
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
    # The exact draft text this finding came from, or None; never
    # serialised, it lets `_stale.partition` refuse rewritten passages.
    span: str | None = None


def missing_citekey_items(drift: Drift | None) -> list[Item]:
    """One unattended item per cited citekey the corpus no longer has,
    anchored on the first citing section; all of them stay in `detail`."""
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


def recorded_but_uncited_items(source: RecordedSource) -> list[Item]:
    """One item per citekey the dossier records and the draft no longer
    cites, `missing-citekey` in reverse (#701).

    Surfaced, never unattended: `recorded - cited` cannot tell a deleted
    citation from a never-cited candidate, and deleting evidence unattended
    would trade staleness for loss, so the repair is a confirmed
    `dossier prune`.
    """
    items = []
    for citekey, surfaces in sorted(source.data.items()):
        items.append(
            Item(
                id=item_id("drift", "recorded-but-uncited", None, citekey, citekey),
                cls="recorded-but-uncited",
                section=None,
                citekey=citekey,
                line=None,
                unattended=False,
                # Suffixed per surface, so no "evidence, sections.md" names
                # a nonexistent file.
                summary=f"`{citekey}` is recorded in "
                f"{', '.join(f'{name}.md' for name in surfaces)} "
                "but the draft no longer cites it",
                detail={"surfaces": list(surfaces)},
            )
        )
    return items


def all_items(sources, sections: list[Section]) -> list[Item]:
    """Every item from every class, unordered and undeduplicated."""
    from chitragupta.review.agenda import _items_findings as f

    return [
        *missing_citekey_items(sources.drift.data),
        *recorded_but_uncited_items(sources.recorded),
        *f.verbatim_run_items(sources.aids["verbatim"], sections),
        *f.prose_items(sources.style, sections),
        *f.unsupported_claim_items(sources.aids["provenance"], sections),
        *f.claim_support_items(sources.aids["support"], sections),
        *f.uncited_claim_items(sources.aids["uncited"], sections),
        *f.misquoted_items(sources.aids["quotation"]),
    ]

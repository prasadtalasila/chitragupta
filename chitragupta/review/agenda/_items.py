"""`Item`, the worklist-entry type, plus the two dossier-based
extractors (`missing-citekey`, `recorded-but-uncited`) and the
`all_items` orchestrator. The other six classes' extractors -- reading
the other aids' `.json` and `style_check`'s findings -- are
`_items_findings.py`, split out once the two halves together crossed
the 250-code-line cap.
"""

from dataclasses import dataclass, field

from chitragupta.dossier._drift import Drift
from chitragupta.dossier._sections import Section
from chitragupta.review.agenda._identity import item_id
from chitragupta.review.agenda._sources import RecordedSource

# The item-class table's own order (docs/AUTO-IMPROVEMENT.md).
#
# `uncited-source` and `candidate` were both removed from this table. Each
# said some version of "the corpus holds a paper you surfaced and did not
# cite" -- `uncited-source` from the coverage aid's `uncited_candidates`,
# `candidate` from dossier drift's own recorded queries -- and for a draft
# that makes no claim from a surfaced paper, not citing it is the correct
# and overwhelmingly common outcome, not a finding. Standing on the agenda
# they were near-pure volume, and volume on a worklist is not free: it is
# read, triaged and dismissed by a person, every cycle, forever.
#
# Both aids still compute and still report them -- `citation_coverage`'s
# own `.json`/`.md` and `dossier status` are unchanged, and asking either
# directly is how you get the list now. What changed is that neither
# reaches the agenda unasked. `recorded-but-uncited` deliberately stays:
# it is the different claim that the *dossier* records a citekey the draft
# no longer cites, which is an inconsistency between two artefacts rather
# than a paper someone declined to use.
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


def recorded_but_uncited_items(source: RecordedSource) -> list[Item]:
    """One item per citekey the dossier records and the draft no longer
    cites -- `missing-citekey` read in the other direction (#701).

    **Surfaced, never unattended**, and the reason is a limit on what
    the data can say rather than caution: `recorded - cited` cannot
    distinguish "the user deleted this citation" from "a candidate was
    transcribed into `evidence.md` and never cited in the first place".
    The first wants the block removed, the second wants it left exactly
    where it is. Deleting recorded evidence unattended would trade a
    cosmetic staleness for a real loss, so the repair is
    `dossier prune`, which a person confirms.

    Sits next to `missing_citekey_items` rather than in
    `_items_findings.py` because it reads the dossier, not an aid's
    `.json` -- the same split that module's docstring already draws.
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
                # Suffixed per surface, not once after the join: two
                # surfaces read "evidence, sections.md" that way, naming
                # a file that does not exist and implying the first is
                # something other than a file.
                summary=f"`{citekey}` is recorded in "
                f"{', '.join(f'{name}.md' for name in surfaces)} "
                "but the draft no longer cites it",
                detail={"surfaces": list(surfaces)},
            )
        )
    return items


def all_items(sources, sections: list[Section]) -> list[Item]:
    """Every item from every class, unordered and undeduplicated --
    `_dedup.merge` and `_order.sort` do the rest."""
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

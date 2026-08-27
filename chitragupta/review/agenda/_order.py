"""Ordering: class first (the item-class table's own fixed order), then
#128's severity bucket within that class, then position in the draft.

No shared severity vocabulary exists across the eight aids -- `provenance`'s
`band`, `verbatim`'s `severity` bucket and so on are unrelated scales
(confirmed by grep across `chitragupta/review/`) -- so ranking within a
class is one small per-class lookup each, not one shared enum.
"""

from chitragupta.review.agenda._items import CLASSES, Item

# Worse first, mirroring #129's own bucket order.
_VERBATIM_RANK = {"long": 0, "short": 1}

# Worse first, mirroring citation_provenance's own worst-first convention.
_PROVENANCE_RANK = {"no support found": 0, "weak": 1}

# Bare-first, mirroring uncited_prose.findings()'s own sort key.
_UNCITED_CLAIM_RANK = {False: 0, True: 1}


def severity_rank(item: Item) -> int:
    """Where `item` falls within its own class's severity ordering.
    Classes with no distinct severity notion (`missing-citekey`,
    `uncited-source`, `misquoted`, `candidate`) rank everything 0 --
    position (or, lacking one, citekey) is the only thing left to sort
    by. `prose` is also a single bucket, deliberately: neither Vale's own
    `severity` string nor `count` is a documented defect-urgency scale
    worth reinterpreting here.
    """
    if item.cls == "verbatim-run":
        return _VERBATIM_RANK.get(item.detail.get("severity"), 2)
    if item.cls == "unsupported-claim":
        return _PROVENANCE_RANK.get(item.detail.get("band"), 2)
    if item.cls == "uncited-claim":
        return _UNCITED_CLAIM_RANK.get(item.detail.get("block_cites"), 1)
    return 0


def sort_key(item: Item) -> tuple:
    """A total order: class, then severity, then line (items with no
    line, e.g. `candidate`, sort after every positioned item in their
    class and tie on it -- `candidate` items order by citekey instead),
    then citekey, then `id` as the final required tiebreak -- several of
    the per-item orderings feeding into this are not unique on their own.
    """
    line = item.line if item.line is not None else 10**9
    return (CLASSES.index(item.cls), severity_rank(item), line, item.citekey or "", item.id)


def sort(items: list[Item]) -> list[Item]:
    return sorted(items, key=sort_key)

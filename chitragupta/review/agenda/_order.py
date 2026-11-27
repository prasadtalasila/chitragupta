"""Ordering: class first (the item-class table's own fixed order), then
#128's severity bucket within that class, then position in the draft.

The aids share no severity vocabulary, so ranking within a class is a
small per-class lookup, not one shared enum.
"""

from chitragupta.review.agenda._items import CLASSES, Item

# Worse first, as #129's bucket order.
_VERBATIM_RANK = {"long": 0, "short": 1}

# Worse first, as citation_provenance.
_PROVENANCE_RANK = {"no support found": 0, "weak": 1}

# Bare-first, as uncited_prose.findings()'s sort key.
_UNCITED_CLAIM_RANK = {False: 0, True: 1}


def severity_rank(item: Item) -> int | float:
    """Where `item` falls within its own class's severity ordering.

    Classes with no severity notion rank 0. `prose` is one bucket: Vale's
    `severity` is no documented urgency scale. `claim-support` ranks on its
    raw score, since a bucket would reintroduce the threshold `support`
    refuses to draw.
    """
    if item.cls == "verbatim-run":
        return _VERBATIM_RANK.get(item.detail.get("severity"), 2)
    if item.cls == "unsupported-claim":
        return _PROVENANCE_RANK.get(item.detail.get("band"), 2)
    if item.cls == "claim-support":
        return item.detail.get("score", 1.0)
    if item.cls == "uncited-claim":
        return _UNCITED_CLAIM_RANK.get(item.detail.get("block_cites"), 1)
    return 0


def sort_key(item: Item) -> tuple:
    """A total order: class, severity, line (lineless items after the
    positioned ones), citekey, then `id`, since the earlier keys tie.
    """
    line = item.line if item.line is not None else 10**9
    return (CLASSES.index(item.cls), severity_rank(item), line, item.citekey or "", item.id)


def sort(items: list[Item]) -> list[Item]:
    return sorted(items, key=sort_key)

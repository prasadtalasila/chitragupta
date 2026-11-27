"""R2's cross-signal merge: two distinct rules, not a fuzzy matcher, since
the aids' outputs hold one true-duplicate case and one
correlated-but-distinct case.
"""

from chitragupta.review.agenda._items import Item


def _suppress_missing_citekey_duplicates(items: list[Item]) -> list[Item]:
    """A citekey that left the ledger also scores 0.0 in provenance, an
    `unsupported-claim` that is a symptom, not new evidence. Drop it,
    folding its claim text into the `missing-citekey` item.
    """
    missing_by_citekey = {item.citekey: item for item in items if item.cls == "missing-citekey"}
    kept = []
    for item in items:
        if item.cls == "unsupported-claim" and item.citekey in missing_by_citekey:
            target = missing_by_citekey[item.citekey]
            target.detail.setdefault("corroborating_claims", []).append(item.detail.get("claim"))
            continue
        kept.append(item)
    return kept


def _cross_link_shared_lines(items: list[Item]) -> list[Item]:
    """Items of different classes on one line are two defects with two
    fixes: both survive, each naming the other in `detail["also_flagged"]`.
    """
    by_line: dict[int, list[Item]] = {}
    for item in items:
        if item.line is not None:
            by_line.setdefault(item.line, []).append(item)
    for line_items in by_line.values():
        for item in line_items:
            others = sorted({(other.id, other.cls) for other in line_items if other is not item})
            if others:
                item.detail["also_flagged"] = [{"id": i, "class": c} for i, c in others]
    return items


def merge(items: list[Item]) -> list[Item]:
    """Suppress true duplicates, cross-link correlated findings, then a
    defensive within-class dedup by `id` against a future extractor bug."""
    items = _suppress_missing_citekey_duplicates(items)
    items = _cross_link_shared_lines(items)
    seen: dict[str, Item] = {}
    for item in items:
        seen.setdefault(item.id, item)
    return list(seen.values())

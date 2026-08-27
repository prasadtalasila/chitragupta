"""R2's cross-signal merge: two distinct rules, not one fuzzy-matching
engine -- the issue's own framing ("this cross-signal merge is the work
no individual aid can do") turns out to have exactly one true-duplicate
case and one correlated-but-distinct case once the eight aids' own outputs
are read closely; see each function's docstring for which is which.
"""

from chitragupta.review.agenda._items import Item


def _suppress_missing_citekey_duplicates(items: list[Item]) -> list[Item]:
    """A citekey that has left the ledger makes
    `citation_provenance.source_passages` return a "not in the ledger"
    reason (`chitragupta/passages.py:290`), which scores 0.0 and bands as
    `"no support found"` -- the same missing citekey surfacing a second
    time as an apparently independent `unsupported-claim`, when it is a
    symptom of the `missing-citekey` defect, not new evidence. Drop the
    `unsupported-claim` item, folding its claim text into the surviving
    `missing-citekey` item instead of filing the same defect twice.
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
    """Two items from *different* classes on the same line (e.g. a
    verbatim-run and an unsupported-claim on the same sentence) are two
    real defects needing two different fixes -- both survive as distinct
    items, but each names the other in `detail["also_flagged"]`. This is
    the concrete, testable form of the cross-signal merge that does not
    hide either fix behind the other.
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
    """Suppress true duplicates, cross-link correlated-but-distinct
    findings, then a defensive within-class dedup by `id` -- ids should
    already be unique by construction; this guards against a future
    extractor bug rather than a case that currently occurs."""
    items = _suppress_missing_citekey_duplicates(items)
    items = _cross_link_shared_lines(items)
    seen: dict[str, Item] = {}
    for item in items:
        seen.setdefault(item.id, item)
    return list(seen.values())

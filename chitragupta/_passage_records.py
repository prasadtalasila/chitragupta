"""What both parsers write into a passage sidecar: one record per unit.

The one definition shared by `pdf_text._extract_docling` and
`docling_parse.parse_doc`; re-exported from `chitragupta/passages.py`.
Stdlib-only: the Docling document is duck-typed (`getattr`, no import).
"""

# Running heads, page numbers and captions are left out, or a claim could
# "match" a journal name repeated on every page. `formula` is in (#627): a
# decoded formula is what a quantitative claim rests on; an undecoded one
# has no text and is dropped.
PASSAGE_LABELS = frozenset({"text", "list_item", "section_header", "title", "formula"})


def passage_records(dl_doc) -> list[dict]:
    """One record per prose text item and per table: what it says and
    where it sits.

    `pdftotext -layout` splices two-column lines (82-89% of long lines),
    so excerpts become collages; Docling's reading order makes a record a
    real, quotable paragraph. The bbox is kept for a future highlight.
    """
    records = []
    for item in getattr(dl_doc, "texts", []):
        label = str(getattr(item, "label", "")).rsplit(".", maxsplit=1)[-1].lower()
        text = (getattr(item, "text", "") or "").strip()
        if label not in PASSAGE_LABELS or not text:
            continue
        records.append(_record(item, text, label))
    # Tables are in `tables`, not `texts` (#627); the markdown export keeps
    # cell text matchable and readable. An export that raises propagates:
    # a swallowed one would write a sidecar missing these units.
    for table in getattr(dl_doc, "tables", []):
        text = (table.export_to_markdown(dl_doc) or "").strip()
        caption = (
            (table.caption_text(dl_doc) or "").strip() if hasattr(table, "caption_text") else ""
        )
        # Prepend the caption, which a draft cites the table by, unless the
        # export already opens with it (real docling's does).
        if caption and not text.startswith(caption):
            text = f"{caption}\n{text}"
        if text:
            records.append(_record(table, text, "table"))
    return records


def _record(item, text: str, label: str) -> dict:
    """One sidecar record, shared by both loops so page anchors agree."""
    prov = item.prov[0] if getattr(item, "prov", None) else None
    record = {
        "text": text,
        "label": label,
        "page": getattr(prov, "page_no", None) if prov else None,
    }
    bbox = getattr(prov, "bbox", None) if prov else None
    if bbox is not None:
        record["bbox"] = [getattr(bbox, side, None) for side in ("l", "t", "r", "b")]
    return record

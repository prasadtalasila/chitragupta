"""What both parsers write into a passage sidecar: one record per unit.

Split out of `chitragupta/passages.py` when #627's table units pushed
that module past docs/CODE-STANDARDS.md's 250-line ceiling. The boundary
is real rather than arithmetic: everything here answers *what a sidecar
record is* -- the one definition both producers share, the corpus
layer's `pdf_text._extract_docling` and the enrichment layer's
`docling_parse.parse_doc` -- while everything left there answers *how a
consumer reads passages back*, sidecar or not. The records are plain
dicts and never touch `Passage`, which is what makes the cut clean.

Re-exported from `chitragupta/passages.py` (`passages.passage_records`,
`passages.PASSAGE_LABELS`), the same arrangement `distinctive` already
has via `chitragupta/_passage_words.py`, so neither writer changed an
import.

Stdlib-only, like its parent: the Docling document comes in by
duck-typing (`getattr` only, no import), which is what lets a module
with no venv dependency describe a document only a venv can build.
"""

# Docling labels each text item. Running heads, page numbers and figure
# captions are not prose a claim can be supported by, so they are left
# out of the passage sidecar -- keeping them would let a claim "match"
# a journal name repeated on all 17 pages. `formula` is in (#627): a
# *decoded* formula (Docling's formula-enrichment model writes the LaTeX
# into the item's text) is exactly the kind of content a quantitative
# claim rests on, and an undecoded one has no text and is dropped by the
# same empty-text guard as everything else.
PASSAGE_LABELS = frozenset({"text", "list_item", "section_header", "title", "formula"})


def passage_records(dl_doc) -> list[dict]:
    """One record per prose text item and per table: what it says and
    where it sits.

    This is what makes a *quotable* passage possible. `pdftotext -layout`
    preserves a page's visual arrangement rather than its reading order,
    so on a two-column paper each output line splices together two
    unrelated columns (82%-89% of long lines, measured over this
    project's own sample). Any excerpt drawn from that text is a
    two-argument collage. Docling resolves reading order, so an item here
    is a real paragraph that can be shown to a reviewer verbatim.

    The bounding box rides along because Docling already has it, and it
    is what a future click-through highlight would need; nothing in this
    repo consumes it yet.
    """
    records = []
    for item in getattr(dl_doc, "texts", []):
        label = str(getattr(item, "label", "")).rsplit(".", maxsplit=1)[-1].lower()
        text = (getattr(item, "text", "") or "").strip()
        if label not in PASSAGE_LABELS or not text:
            continue
        records.append(_record(item, text, label))
    # Tables ride in the document's own `tables` list, not `texts`, so
    # they were structurally invisible to the loop above -- which is how
    # a table dropped to its caption before #627. The markdown export
    # keeps the cell structure, so the record is both matchable (its
    # distinctive words are the cell text) and readable when a review
    # aid shows it. An export that raises is left to propagate: both
    # writers already classify a per-document failure honestly, and a
    # swallowed one here would write a sidecar missing the very units
    # this exists to carry.
    for table in getattr(dl_doc, "tables", []):
        text = (table.export_to_markdown(dl_doc) or "").strip()
        caption = (
            (table.caption_text(dl_doc) or "").strip() if hasattr(table, "caption_text") else ""
        )
        # The caption is the sentence a draft actually cites the table
        # by -- but only prepend it when the export does not already
        # open with it: real docling's export_to_markdown() includes the
        # caption itself (measured on a real IEEE paper), and prepending
        # it regardless doubled the 'TABLE I: ...' line on every table.
        if caption and not text.startswith(caption):
            text = f"{caption}\n{text}"
        if text:
            records.append(_record(table, text, "table"))
    return records


def _record(item, text: str, label: str) -> dict:
    """One sidecar record: what it says and where it sits. Shared by the
    prose and table loops so the two cannot disagree about what a page
    anchor looks like."""
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

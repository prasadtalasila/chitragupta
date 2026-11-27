"""The source document's own text behind a range of global token
positions -- the other side of a lexical-tier finding.

The indexes keep only a position in a normalised word stream; a report
needs the real casing and punctuation so a reader can see where the
source and draft differ. Tokenizing with `[A-Za-z0-9]+` then lowercasing
gives exactly `_norm`'s tokens; `WORD` itself cannot be reused, since on
raw text it splits on capitals. tests/test_overlap_source_text.py pins
the equivalence.
"""

from __future__ import annotations

import re

from chitragupta import overlap_index

# Case-preserving counterpart of `overlap_index.WORD` (see the module
# docstring for why it is not imported).
_RAW_WORD = re.compile(r"[A-Za-z0-9]+")

# citekey -> (validity key, [(page_text, [(char_start, char_end), ...])]).
# One parse per citekey per process, not per finding. Keyed on
# `overlap_index._fingerprint_key`, not the citekey: a reparse rewrites the
# text without touching the PDF. Not persisted; it is microseconds of work.
_PAGES: dict[str, tuple[list, list[tuple[str, list[tuple[int, int]]]]]] = {}


def _tokenized_pages(citekey: str) -> list[tuple[str, list[tuple[int, int]]]] | None:
    """Each page of `citekey`'s parsed text, with its tokens' character
    spans, or `None` when the ledger, the citekey or the file is gone.
    The page split is `overlap_index`'s own: another would shift every
    position and return the wrong passage silently.
    """
    item = overlap_index.ledger_item(citekey)
    if item is None:
        return None
    pdf_hash, parsed_path = item
    key = overlap_index._fingerprint_key(pdf_hash, parsed_path)
    cached = _PAGES.get(citekey)
    if cached is not None and cached[0] == key:
        return cached[1]
    pages = [
        (text, [m.span() for m in _RAW_WORD.finditer(text)])
        for text in overlap_index._pages_from_parsed_text(parsed_path)
    ]
    _PAGES[citekey] = (key, pages)
    return pages


def source_span(citekey: str, start: int, end: int) -> str | None:
    """`citekey`'s own text for the half-open global token range
    `[start, end)`, or `None` if it cannot be recovered.

    `None`, never `""`: an empty string would claim a blank source
    passage. A range across a page break joins both pages' text, since
    picking one side would truncate the passage being compared.
    """
    pages = _tokenized_pages(citekey)
    if pages is None or start >= end:
        return None

    parts = []
    offset = 0
    for text, spans in pages:
        page_start, page_end = max(start, offset), min(end, offset + len(spans))
        if page_start < page_end:
            local = [page_start - offset, page_end - offset - 1]
            parts.append(text[spans[local[0]][0] : spans[local[1]][1]])
        offset += len(spans)

    # A range past the end yields the prefix that exists; nothing at all
    # means the range missed the document.
    return " ".join(parts) if parts else None

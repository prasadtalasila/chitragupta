"""The source document's own text behind a range of global token
positions -- the other side of a lexical-tier finding.

`overlap_index.py` and `overlap_skipgram.py` both index a document as one
continuous normalised word stream: pages split on the form-feed, each
page through `_norm` (`WORD.findall(text.lower())`), concatenated, and a
posting's `token_position` is a global offset into that stream. That is
everything a *detector* needs and nothing a *reader* does -- by the time
a finding is built, the position is all that survives, and the report can
only show the draft's side of the match.

This module recovers the other side. Given a citekey and a half-open
global token range, it returns the document's own text across that range:
real casing, real punctuation, real hyphens. The report needs that rather
than the normalised stream, because the whole point of showing the source
beside the draft is to let a reader see where the two differ -- and two
normalised streams differ in fewer visible places than the real texts do.

**Why a second tokenisation is sound.** `_norm` is
`re.findall(r"[a-z0-9]+", text.lower())`; this module uses
`re.finditer(r"[A-Za-z0-9]+", text)` and lowercases each match. The two
produce the same token list, one-to-one, for any input: lowercasing the
whole string before matching `[a-z0-9]+` and matching `[A-Za-z0-9]+`
before lowercasing each match partition a string identically, since
`str.lower()` maps ASCII letters to ASCII letters and leaves every other
character (the separators) alone. `_norm` itself cannot be reused here:
it returns strings with no offsets, and `WORD` is `[a-z0-9]+` against
un-lowercased text, which does not merely miss capitals but *splits* on
them -- `"Configuration"` matches as `"onfiguration"`.
`tests/test_overlap_source_text.py` pins the equivalence directly.
"""

from __future__ import annotations

import re

from chitragupta import overlap_index

# Case-preserving counterpart of `overlap_index.WORD`. Deliberately not
# imported from there: that pattern is applied to already-lowercased text
# and would be wrong applied to raw text (see the module docstring).
_RAW_WORD = re.compile(r"[A-Za-z0-9]+")

# citekey -> (validity key, [(page_text, [(char_start, char_end), ...])]),
# pages in the order the index concatenated them. One parse per citekey
# per process: a scan asks for a span once per finding, and a draft with
# forty findings against one source would otherwise re-read and re-scan
# the whole parsed text forty times.
#
# Keyed on `overlap_index._fingerprint_key` -- `(pdf_hash, parsed size,
# mtime_ns)` -- and not on the citekey alone. `sync --reparse` and a
# `[parser].backend` switch both rewrite `content/parsed/<citekey>.txt`
# without touching the PDF, exactly as `overlap_index`'s own doc cache
# documents, so a citekey-keyed entry would keep serving spans into text
# that no longer exists. One `stat` per lookup is the whole cost of not
# having that failure mode, and it is invisible beside the read it
# guards.
#
# Not persisted, unlike the fingerprint caches: this is microseconds of
# work on a file the process is reading anyway.
_PAGES: dict[str, tuple[list, list[tuple[str, list[tuple[int, int]]]]]] = {}


def _tokenized_pages(citekey: str) -> list[tuple[str, list[tuple[int, int]]]] | None:
    """Each page of `citekey`'s parsed text, with its tokens' character
    spans -- or `None` when the ledger, the citekey or the file is gone.

    The page split and the read are `overlap_index`'s own
    (`_pages_from_parsed_text`), not a second convention: a different
    split would shift every global position and quietly return the wrong
    passage rather than failing.
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

    `None` rather than `""` for every failure -- no ledger, an unparsed
    or since-deleted source, a range past the end of the document -- and
    the caller publishes that as a `source_text` of `null`. An empty
    string would render as a source passage that exists and is blank,
    which is a different and false claim; the tiers that genuinely have
    no second side to show use `None` for exactly the same reason.

    A range that straddles a page break returns the two pages' text
    joined by a space, in page order. The alternative -- picking one side
    -- would silently truncate the passage the reader is being asked to
    compare against, which is the one thing this function exists to
    prevent.
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

    # `end` past the document's last token yields whatever prefix did
    # exist, which is still the right passage -- but nothing at all means
    # the range missed the document entirely, and there is no passage to
    # report.
    return " ".join(parts) if parts else None

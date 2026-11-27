"""The author's own abstract, lifted out of the structural passage
sidecar -- extraction, never summarisation.

`chitragupta/tldr.py`'s fallback when nobody wrote a TL;DR. No LLM call
(#401's model path was declined): a paper with no abstract says so.

Read from the sidecar, not flattened text: recall is the same, but
"stop at the next `section_header`" is structural where "stop after N
words" is a guess. Docling has no `abstract` label, so openers are
matched on their text.

The guards withhold rather than trim: a false negative costs a reader
one look at the parsed text, a false positive publishes non-abstract
text as the authors'. Each was measured on a 498-document corpus:
`MAX_LEAD_ITEMS` (genuine openers at p90 item #21; deeper matches were
class-diagram text), `MAX_BODY_ITEMS` (items, not words, so a run-on is
cut without discarding a correct abstract), and the word bounds (longest
genuine abstract 321 words; floor 40, not #401's 60, because a genuine
one had 58). Result: 318 of 498.

Stdlib only: tldr.py is a tier-1 command under bare `python3`
(docs/ARCHITECTURE.md).
"""

import re

from chitragupta import passages

# Distinct from None: "no abstract" is about the paper, "no sidecar" is
# not. Compare with `is`, never `==`: it is a `str` to keep `extract`'s
# return type narrow, and a real body is always a fresh object.
UNKNOWN = "unknown"

# The heading form, anchored at both ends ("Abstract syntax tree" is not).
_HEADING = re.compile(r"^(\d+\s*[.)]?\s*)?abstract\s*[:.—-]?$", re.I)

# The word opening a paragraph that continues into the abstract (how
# Docling emits most); the group keeps the body's first character.
_INLINE = re.compile(r"^abstract\s*[:.—-]?\s+(\S)", re.I)

# What ends an abstract when no `section_header` does. Not shared with
# enrich/keyword_extract.py's `_MARKER`: opposite purpose, and importing
# enrich would break this module's stdlib-only boundary.
_STOP = re.compile(r"^(keywords?|key words|index terms|\d*\s*\.?\s*introduction)\b", re.I)

# No `list_item`: it pulls in a following table of contents.
_PROSE = ("text", "paragraph")

MAX_LEAD_ITEMS = 40
MAX_BODY_ITEMS = 3
MIN_BODY_WORDS = 40
MAX_BODY_WORDS = 400


def _opener(found: list) -> tuple[int, list[str]] | None:
    """Where the abstract starts, as (index after the marker, body so
    far), or None if no marker sits within the lead window."""
    for i, passage in enumerate(found[:MAX_LEAD_ITEMS]):
        text = (passage.text or "").strip()
        if passage.label == "section_header" and _HEADING.match(text):
            return i + 1, []
        if _INLINE.match(text) and passage.label in (*_PROSE, "section_header"):
            return i + 1, [_INLINE.sub(r"\1", text, count=1)]
    return None


def _body(found: list, start: int, body: list[str]) -> str:
    """The paragraphs from `start` that belong to the abstract."""
    for passage in found[start:]:
        if len(body) >= MAX_BODY_ITEMS:
            break
        text = (passage.text or "").strip()
        if passage.label == "section_header" or _STOP.match(text):
            break
        # Captions and formulas are interleaved by page position, so one
        # inside the span does not end the abstract.
        if passage.label in _PROSE and text:
            body.append(text)
    return " ".join(body)


def extract_from(found: list) -> str | None:
    """The abstract in `found`, or None if these passages hold none.

    Split from `extract` for #762, whose BM25 weighting must choose the
    corpus layer's sidecar itself, without a second copy of the guards.
    Never returns `UNKNOWN`.
    """
    opener = _opener(found)
    if opener is None:
        return None
    text = _body(found, *opener)
    if not MIN_BODY_WORDS <= len(text.split()) <= MAX_BODY_WORDS:
        return None
    return text


def extract(citekey: str) -> str | None:
    """`citekey`'s abstract, None if the paper has none, or `UNKNOWN` if
    there is no structural sidecar to look in.

    Never cached: re-deriving is free and a copy could go stale.
    """
    found = passages.structural_passages(citekey)
    if found is None:
        return UNKNOWN
    return extract_from(found)

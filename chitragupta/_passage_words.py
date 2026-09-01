"""The word set a passage is matched on: which words distinguish a claim.

Split from `chitragupta/passages.py`, which was 262 code lines against
docs/CODE-STANDARDS.md's 250 ceiling and carried a register entry saying
so. The boundary is the one that module's own docstring already draws:
everything there is about *where a citekey's text comes from* -- sidecars,
the ledger, form feeds, `pdftotext` -- while this is a vocabulary, a
constant and a three-line function over it, used by that ladder's output
rather than part of finding it.

`passages.distinctive` still resolves: the name is re-exported there, the
way `chitragupta/enrich/embed_index.py` re-exports `embed_text`'s, so no
caller changes. The dependency runs one way, `passages` -> here.
"""

import re

# Lowercase alphanumeric runs, stopwords and very short words dropped, so
# matching keys off the words that actually distinguish one claim from
# another.
_WORD = re.compile(r"[a-z0-9]+")

_CORE_STOPWORDS = {
    "a",
    "an",
    "the",
    "of",
    "on",
    "in",
    "for",
    "and",
    "to",
    "with",
    "is",
    "are",
    "be",
    "this",
    "that",
    "as",
    "by",
    "from",
    "at",
}

# Shared with chitragupta/retrieval.py, which imports _CORE_STOPWORDS
# from here (this module has no drafting-layer dependents, so this is
# the direction that keeps the corpus/enrichment/review layers
# independent of drafting). Editing this constant moves retrieval.py's
# BM25 index too and needs _INDEX_SCHEMA_VERSION bumped there --
# passages.py's own extras just below are free to change on their own.
_STOPWORDS = _CORE_STOPWORDS | {
    "it",
    "its",
    "can",
    "has",
    "have",
    "was",
    "were",
    "which",
    "such",
    "these",
    "those",
    "their",
    "than",
    "then",
    "but",
    "not",
    "also",
}


def distinctive(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if len(w) > 2 and w not in _STOPWORDS}

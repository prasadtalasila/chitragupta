"""Query-side spelling correction for BM25 retrieval (#1232).

A word the corpus has never seen scores zero everywhere. With
`[retrieval].spelling_correction` on, it also searches the one corpus
word a single typing slip away.

- Add, never replace: the typed word stays, and callers announce it.
- Only unseen words of five letters or more, with no digit, so a rare
  correct term is never changed.
- Candidates must occur in two or more papers (the one-paper tail is
  mostly OCR noise); the most common wins, then alphabetical. 95.75%
  of corrections are right (bench/RESULTS.md, 2026-11-22).
- Off by default, and off is structural: `dossier status` re-ranks
  recorded queries, so turning it on can show as drift.
- The vocabulary is `retrieval_cache.read_only_index`'s, never writing
  the cache, since `dossier status` must not change what it inspects.
"""

import sqlite3
import string

from chitragupta import config, ledger, retrieval_cache
from chitragupta.ledger_citable import PARSED

MIN_LENGTH = 5
MIN_PAPERS = 2

# Keyed on the index object's identity, which `read_only_index` keeps
# while rows are unchanged; a file timestamp could miss two quick writes.
_MEMO: dict = {}


def one_slip_variants(word: str) -> set[str]:
    """Every string one deletion, adjacent swap, substitution or insertion
    of a lowercase letter away from `word`."""
    splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    letters = string.ascii_lowercase
    return (
        {a + b[1:] for a, b in splits if b}
        | {a + b[1] + b[0] + b[2:] for a, b in splits if len(b) > 1}
        | {a + c + b[1:] for a, b in splits if b for c in letters}
        | {a + c + b for a, b in splits for c in letters}
    )


def _parsed_rows() -> list[sqlite3.Row]:
    """The rows `search` ranks, read without a lock; none without a
    readable ledger, which the caller's own ledger read reports."""
    try:
        with ledger.reading() as con:
            return [row for row in ledger.all_items(con) if row["status"] == PARSED]
    except (ledger.NoLedger, sqlite3.Error):
        return []


def vocabulary(tokenize_item) -> dict[str, int]:
    """Every word in the document index, with the number of papers it is in.
    `tokenize_item` is passed in because `retrieval` imports this module.
    """
    index = retrieval_cache.read_only_index(_parsed_rows(), tokenize_item)
    if _MEMO.get("index") is not index:
        papers: dict[str, int] = {}
        for entry in index.values():
            for word in entry["term_freqs"]:
                papers[word] = papers.get(word, 0) + 1
        _MEMO.update(index=index, vocabulary=papers)
    return _MEMO["vocabulary"]


def correct(typed: list[str], tokenize_item, excluded: frozenset[str]) -> list[tuple[str, str]]:
    """`(typed word, correction)` pairs for `typed`, in query order.

    `typed` is before acronym expansion. `excluded` is
    `retrieval._INTERROGATIVES`, dropped on purpose and never added back.
    A correction already in the query, or repeated, is added once.
    """
    if not config.SPELLING_CORRECTION:
        return []
    eligible = [w for w in dict.fromkeys(typed) if len(w) >= MIN_LENGTH and w.isalpha()]
    if not eligible:
        return []
    papers = vocabulary(tokenize_item)
    present = set(typed)
    added = []
    for word in eligible:
        if word in papers:
            continue
        found = [
            v
            for v in one_slip_variants(word)
            if papers.get(v, 0) >= MIN_PAPERS and v not in excluded
        ]
        if not found:
            continue
        best = min(found, key=lambda v: (-papers[v], v))
        if best not in present:
            present.add(best)
            added.append((word, best))
    return added

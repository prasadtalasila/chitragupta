"""Query-side spelling correction for BM25 retrieval (#1232).

BM25 matches words exactly, so a query word the corpus has never seen --
`strucutral` -- scores zero for every paper, and the result says nothing
about why. With `[retrieval].spelling_correction` on, such a word also
searches for the one corpus word a single typing slip away from it.

**Add, never replace.** The typed word stays in the query. A genuine
domain term the corpus lacks is still searched as typed; a correction
only adds a word, and every caller that shows results to a person
announces it.

**Only words the corpus has never seen.** A word in even one paper is
left alone, so a rare but correct term is never changed. Words under five
letters and tokens with a digit are never corrected either: a short word
has too many neighbours, and a neighbouring number is never what was
meant.

**One slip, and the commonest word.** The candidates are the strings one
deletion, adjacent swap, substitution or insertion away from the typed
word, kept only if they are words in at least two papers -- more than
half the vocabulary appears in one paper, and that tail is mostly OCR
noise. Among them the word in the most papers wins, then the
alphabetically first. On this project's corpus 95.75% of its corrections
of synthetic typos are right, and it fixes 94.3% of the typos it can act
on (bench/RESULTS.md, 2026-11-22). What it gets wrong is mostly a typo
one slip from two real words: `aeing` could be `ageing` or `being`, and
only context could say which.

**Off is structural, as with acronym expansion.** Switched off, `correct`
returns before building a vocabulary, so ranking is what it was before
this module existed. Off by default: `dossier status` re-ranks every
recorded query with the current settings, so switching this on moves
rankings and can show as drift.

**The vocabulary is the document index's, built read-only.**
`retrieval_cache.read_only_index` over the parsed rows `search` ranks, so
a correction is always a word some paper can be matched on, and building
it never writes the cache -- `dossier status` reaches this module through
`retrieval.query_terms`, and a report must not change what it inspects.
"""

import sqlite3
import string

from chitragupta import config, ledger, retrieval_cache
from chitragupta.ledger_citable import PARSED

MIN_LENGTH = 5
MIN_PAPERS = 2

# The last vocabulary built, and the index object it was built from.
# `read_only_index` returns the same object while the rows are unchanged,
# so identity is the staleness check: a sync changes a fingerprint, the
# index is rebuilt, and so is this. A file timestamp would not do -- two
# writes milliseconds apart can share one.
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
    """The rows `search` ranks, read without a lock; none when there is no
    readable ledger -- which is no corrections, not an error, since the
    caller's own ledger read reports that case."""
    try:
        with ledger.reading() as con:
            return [row for row in ledger.all_items(con) if row["status"] == PARSED]
    except (ledger.NoLedger, sqlite3.Error):
        return []


def vocabulary(tokenize_item) -> dict[str, int]:
    """Every word in the document index, with the number of papers it is in.

    `tokenize_item` is passed in for the reason `retrieval_cache` takes
    it: `chitragupta.retrieval` imports this module.
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

    `typed` is the query's terms as `retrieval._query_terms` returns them,
    before acronym expansion: a correction is never corrected again or
    acronym-expanded, and an expansion is never corrected. `excluded` is
    `retrieval._INTERROGATIVES`, words in the index that a query drops on
    purpose and a correction must not add back. A correction already in
    the query is not added, and two typos of one word add it once.
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

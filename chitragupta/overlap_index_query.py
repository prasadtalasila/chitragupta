"""Reading a built `CorpusIndex`: which pages a gram occurs on, and every
raw posting for one.

Split from `chitragupta/overlap_index_corpus.py` (#441): a pure
lookup over a `CorpusIndex` a caller already has, with no cache,
ledger, or fingerprinting concern of its own -- the reason this is a
separate module from the one that builds the index rather than another
function in it.
"""

from bisect import bisect_left, bisect_right

from chitragupta.overlap_index_corpus import CorpusIndex


def pages_for_gram(index: CorpusIndex, gram_hash: int, citekey: "str | None" = None) -> list[int]:
    """Every distinct page in the corpus (optionally narrowed to one
    `citekey`) where `gram_hash` occurs, in ascending order -- a
    binary-search lookup into `index.grams`, which is sorted.

    Deduplicated: a gram repeated more than once on the same page (a
    second occurrence of the same phrase, or two documents sharing one
    page number) would otherwise repeat that page once per posting, which
    is not what "which pages" means to a caller.

    **Kept deliberately with no production caller** (#515). Only
    `postings_for_gram` below is called today, by `verbatim_check`'s scan
    mode, which needs `token_position`. This is the other half of the
    pair this module exists to be -- its own docstring names both
    questions -- and the two are one bisect apart: deleting this would
    leave a module answering half of what it says it answers, and the
    next caller wanting "which pages" would write the deduplication again.
    Named here rather than left looking like an oversight, which is the
    drift the report was actually about.
    """
    lo = bisect_left(index.grams, gram_hash)
    hi = bisect_right(index.grams, gram_hash, lo=lo)
    matched_pages = set()
    for i in range(lo, hi):
        if citekey is not None and index.citekeys[index.citekey_ids[i]] != citekey:
            continue
        matched_pages.add(index.pages[i])
    return sorted(matched_pages)


def postings_for_gram(index: CorpusIndex, gram_hash: int) -> list[tuple[str, int, int]]:
    """Every `(citekey, page, token_position)` posting for `gram_hash`,
    undeduped, in the same order they were merged into `index` (stable
    ties on the sort in `build_corpus_index` -- effectively citekey order,
    then page/position order).

    Unlike `pages_for_gram`, this keeps every occurrence rather than
    collapsing to distinct pages: `chitragupta/review/verbatim_check.py`'s `scan`
    mode needs `token_position` to align a run across consecutive draft
    positions, which a deduplicated page list would throw away.
    """
    lo = bisect_left(index.grams, gram_hash)
    hi = bisect_right(index.grams, gram_hash, lo=lo)
    return [
        (index.citekeys[index.citekey_ids[i]], index.pages[i], index.positions[i])
        for i in range(lo, hi)
    ]

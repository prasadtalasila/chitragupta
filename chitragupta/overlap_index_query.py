"""Reading a built `CorpusIndex`: which pages a gram occurs on, and every
raw posting for one. A pure lookup, no cache or ledger (#441).
"""

from bisect import bisect_left, bisect_right

from chitragupta.overlap_index_corpus import CorpusIndex


def pages_for_gram(index: CorpusIndex, gram_hash: int, citekey: "str | None" = None) -> list[int]:
    """Every distinct page (optionally for one `citekey`) where `gram_hash`
    occurs, ascending; deduplicated, since "which pages" should not repeat
    a page per posting.

    Kept deliberately with no production caller (#515): it is the other
    half of this module's pair, and deleting it would leave the next
    caller rewriting the deduplication.
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
    undeduped, in merge order. `verbatim_check`'s `scan` mode needs
    `token_position` to align a run, which a page list would throw away.
    """
    lo = bisect_left(index.grams, gram_hash)
    hi = bisect_right(index.grams, gram_hash, lo=lo)
    return [
        (index.citekeys[index.citekey_ids[i]], index.pages[i], index.positions[i])
        for i in range(lo, hi)
    ]

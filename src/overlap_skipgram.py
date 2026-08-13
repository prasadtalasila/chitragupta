"""Tier 2: deterministic light-paraphrase detection via stemmed skip-grams
(the CoReMo 2.1 design, Torrejon & Ramos, PAN 2013 winner on quality and
runtime -- discussion #115, docs/PLAGIARISM.md). Catches the every-few-
words synonym swap or inflection change an LLM's paraphrase leaves --
exactly what tier 1's exact 8-gram index (src/overlap_index.py) is blind
to by construction, since a single substituted word breaks every
contiguous n-gram that contains it.

**The idea.** Split the word stream into two fixed interleaved families
by *original* position -- even indices, odd indices -- before anything
else touches it, then stem and drop stopwords independently *within*
each family (`src/porter_stemmer.py`), and take ordinary contiguous
n-grams over each family's own reduced stream
(`overlap_index.gram_hashes`, reused unchanged). A single substituted
word at original position p can only ever affect the family whose parity
p belongs to; the other family's members, and therefore its stems, its
stopword membership and its n-grams, are untouched -- so at least one
family survives a lone substitution intact, the same tolerance
`_merge_runs` gives tier 1 against an edited word, bought here without a
gap-tolerant merge.

The split has to happen on the *original* stream, not on the
stopword-filtered one: if a paraphrase swaps a stopword for a content
word or vice versa at some position (`"of a digital twin"` -> `"of one
digital twin"` is exactly this, and is in this project's own pinned
paraphrase fixture, tests/test_feature_workflows.py), filtering first
and splitting the *filtered* stream's parity second would shift every
later position's family membership between the two texts by one, and
every family would stop matching from that point on -- not just at the
substitution. Splitting first pins each original word to its family
before either text's stopword pattern can diverge from the other's.

**Position bookkeeping.** Every skip-gram's reported `position` is the
original, unfiltered word-stream index of its first member -- the same
numbering `overlap_index`'s tier-1 postings use -- so `(citekey,
position)` from this module's index and from tier 1's are directly
comparable, and a caller aligning a draft against both tiers does not
need two different coordinate systems.

**Two independent caches**, mirroring `overlap_index.py`'s shape and
sharing its atomic-write and cache-validation helpers, but never its
files or its version constants: a stemmer or stopword-list change should
invalidate only this tier's cache, not force tier 1 to refingerprint the
whole corpus, and vice versa. The shared helpers
(`_parse_cached_postings`, `_parse_corpus_index_binary`) take each
tier's own `_TOKENIZER_VERSION`/`_HEADER_VERSION` as arguments rather
than reading a module global, which is what keeps that independence
intact -- they were extracted because the validate-and-parse mechanics
were otherwise identical, not because the two tiers' caches were made to
depend on each other.
`docs/<citekey>.skipgram.fpr` (own `_TOKENIZER_VERSION`) and
`skipgram_index.bin`/`skipgram_index.json` (own `_HEADER_VERSION`), all
under the same `config.OVERLAP_DIR`.

Advisory only for now (discussion #115: "start advisory, promote with
evidence") -- nothing in this module or in
`src/review/verbatim_check.py`'s tier-2 finder decides gate-eligibility;
that is a later, separate decision (issue #130), unlike tier 3
(embedding), which docs/PLAGIARISM.md rules out from ever gating, by
construction.
"""

from __future__ import annotations

import hashlib
import json
from array import array
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from itertools import accumulate
from pathlib import Path

from src import config
from src.overlap_index import (
    _atomic_write_bytes,
    _atomic_write_json,
    _fingerprint_key,
    _ledger_items,
    _pages_from_parsed_text,
    _norm,
    _parse_cached_postings,
    _parse_corpus_index_binary,
    gram_hashes,
)
from src.porter_stemmer import stem

# A content-word gram width, not a raw-word one: after stopword
# filtering, roughly two out of every five running words in English
# prose survive (function words dominate the rest), so 5 stemmed content
# words already correspond to a raw span comparable in length to tier
# 1's 8-word floor -- and demanding 8 survives even in a short paragraph
# where a family's filtered stream may not hold that many.
DEFAULT_N = 5

# Bumped whenever the stemmer, the stopword list, or the even/odd split
# below changes shape -- the whole migration for this tier's cache, same
# discipline as overlap_index._TOKENIZER_VERSION.
_TOKENIZER_VERSION = 1
_HEADER_VERSION = 1

# A short, standard English function-word list -- articles, pronouns,
# prepositions, conjunctions, auxiliary/copular verb forms, and the most
# common quantifiers/adverbs. Deliberately not exhaustive: a stopword
# that leaks through costs nothing but a slightly wider skip-gram window;
# a content word wrongly listed here would cost real recall, so the list
# stays conservative rather than reaching for completeness.
STOPWORDS = frozenset("""
a an the and or but if then else when while as of to in on at by for
with about against between into through during before after above below
from up down out off over under again further once here there all any
both each few more most other some such no nor not only own same so
than too very s t can will just don should now is am are was were be
been being have has had having do does did doing would could might
must shall this that these those it its it's he she they we you i him
her them us our your their his ours yours theirs myself yourself
himself herself itself ourselves yourselves themselves what which who
whom
""".split())


def stem_filter(words: list[str]) -> tuple[list[str], list[int]]:
    """`words` (already tokenized, lowercase `[a-z0-9]+`) reduced to
    stemmed content words, plus -- parallel -- each one's index in
    `words` itself. `stems[i]` came from `words[positions[i]]`; a purely
    numeric token stems to itself (there is nothing to strip) and is kept,
    since a shared figure or version number is still shared wording.

    Whole-stream, not family-split -- used where robustness to a
    substitution elsewhere in the text does not matter, e.g. normalizing
    a short allowlisted phrase for masking (see
    `src/review/verbatim_check.py`'s tier-2 allowlist handling), not for
    generating skip-grams themselves (`skipgram_postings`, below, which
    needs the family split for the reason the module docstring gives).
    """
    stems: list[str] = []
    positions: list[int] = []
    for i, w in enumerate(words):
        if w in STOPWORDS:
            continue
        stems.append(stem(w) if not w.isdigit() else w)
        positions.append(i)
    return stems, positions


def _families(words: list[str]) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """`words` split into its even- and odd-*original*-index families,
    each still carrying `(word, original_index)` pairs -- stopword
    filtering and stemming happen after this split, independently per
    family, per the module docstring's reasoning."""
    return (
        [(w, i) for i, w in enumerate(words) if i % 2 == 0],
        [(w, i) for i, w in enumerate(words) if i % 2 == 1],
    )


def _stem_filter_family(pairs: list[tuple[str, int]]) -> tuple[list[str], list[int]]:
    stems: list[str] = []
    positions: list[int] = []
    for w, i in pairs:
        if w in STOPWORDS:
            continue
        stems.append(stem(w) if not w.isdigit() else w)
        positions.append(i)
    return stems, positions


def skipgram_postings(words: list[str], n: int) -> list[tuple[int, int, int]]:
    """`(gram_hash, start, end)` for every skip-gram in `words` -- `words`
    already tokenized (`overlap_index._norm`/`verbatim_check.norm`).
    `start` and `end` are original indices (into `words`) of the
    skip-gram's first and last family member, `end` inclusive-plus-one
    so `words[start:end]` (once any interposed stopwords are counted
    back in) is the full span, matching tier 1's `(start, end)`
    convention in `verbatim_check.scan_findings`.

    A corpus-side caller (`_build_fingerprint`, below) keeps `start` only
    -- a document fingerprint's postings only ever need a position to
    align a diagonal against, never their own span, since a run's extent
    is always measured on the draft side. A draft-side caller
    (`src/review/verbatim_check.py`'s tier-2 finder) needs both, to
    report where a match starts and ends in the draft actually scanned.

    Order is ascending within each of the two families, families
    concatenated even-then-odd; not globally sorted by position, since a
    caller grouping by `(citekey, diagonal)` does not need it to be.
    """
    postings = []
    for pairs in _families(words):
        stems, positions = _stem_filter_family(pairs)
        for j, gh in enumerate(gram_hashes(stems, n)):
            postings.append((gh, positions[j], positions[j + n - 1] + 1))
    return postings


@dataclass
class DocSkipgramFingerprint:
    citekey: str
    key: list
    n: int
    # (gram_hash, page, position), position the *original* word-stream
    # index of the skip-gram's first stemmed word -- see module docstring.
    postings: list[tuple[int, int, int]]


def _doc_cache_path(citekey: str) -> Path:
    return config.OVERLAP_DIR / "docs" / f"{citekey}.skipgram.fpr"


def _load_doc_cache(citekey: str, key: list, n: int) -> "DocSkipgramFingerprint | None":
    try:
        with open(_doc_cache_path(citekey), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    parsed = _parse_cached_postings(data, key, n, _TOKENIZER_VERSION)
    if parsed is None:
        return None
    return DocSkipgramFingerprint(citekey=citekey, key=key, n=n, postings=parsed)


def _save_doc_cache(fp: DocSkipgramFingerprint) -> None:
    payload = {
        "tokenizer_version": _TOKENIZER_VERSION,
        "n": fp.n,
        "key": fp.key,
        "postings": [list(p) for p in fp.postings],
    }
    _atomic_write_json(_doc_cache_path(fp.citekey), payload)


def _build_fingerprint(
    citekey: str, pdf_hash: str, parsed_path: str, n: int
) -> DocSkipgramFingerprint:
    """Mirrors `overlap_index._build_fingerprint`'s page-boundary
    bookkeeping exactly, over the same per-page word lists -- only the
    posting generation (skip-grams over the stemmed, filtered stream
    instead of plain contiguous grams) differs.
    """
    page_words = [_norm(page_text) for page_text in _pages_from_parsed_text(parsed_path)]
    boundaries = list(accumulate(len(words) for words in page_words))
    words = [w for page in page_words for w in page]

    postings: list[tuple[int, int, int]] = []
    num_pages = len(boundaries)
    for gh, position, _end in skipgram_postings(words, n):
        # A fresh bisect per posting, not a shared advancing sweep like
        # tier 1's: the two families are each ascending in `position`,
        # but `skipgram_postings` yields even-family postings before
        # odd-family ones, so `position` as a whole is not monotonic
        # across this loop the way tier 1's single-stream sweep is.
        page_idx = bisect_right(boundaries, position)
        postings.append((gh, min(page_idx, max(num_pages - 1, 0)) + 1, position))
    return DocSkipgramFingerprint(
        citekey=citekey, key=_fingerprint_key(pdf_hash, parsed_path), n=n, postings=postings
    )


def fingerprint_document(
    citekey: str, pdf_hash: str, parsed_path: str, n: int = DEFAULT_N
) -> DocSkipgramFingerprint:
    key = _fingerprint_key(pdf_hash, parsed_path)
    cached = _load_doc_cache(citekey, key, n)
    if cached is not None:
        return cached
    fp = _build_fingerprint(citekey, pdf_hash, parsed_path, n)
    _save_doc_cache(fp)
    return fp


# ---------------------------------------------------------------------
# The merged corpus-wide skip-gram index -- same shape and reasoning as
# overlap_index.CorpusIndex, kept as a wholly separate pair of files (see
# module docstring) so the two tiers' caches never contend or cross-
# invalidate each other.
# ---------------------------------------------------------------------


@dataclass
class CorpusSkipgramIndex:
    n: int
    citekeys: list[str]
    grams: "array[int]"
    citekey_ids: "array[int]"
    pages: "array[int]"
    positions: "array[int]"


def _index_header_path() -> Path:
    return config.OVERLAP_DIR / "skipgram_index.json"


def _index_bin_path() -> Path:
    return config.OVERLAP_DIR / "skipgram_index.bin"


def _corpus_key(doc_keys: list[tuple[str, list]]) -> str:
    payload = json.dumps(sorted(doc_keys), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_corpus_index(n: int, corpus_key: str) -> "CorpusSkipgramIndex | None":
    try:
        with open(_index_header_path(), encoding="utf-8") as f:
            header = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    parsed = _parse_corpus_index_binary(
        header, corpus_key, n, _TOKENIZER_VERSION, _HEADER_VERSION, _index_bin_path()
    )
    if parsed is None:
        return None
    citekeys, grams, citekey_ids, pages, positions = parsed
    return CorpusSkipgramIndex(
        n=n, citekeys=citekeys, grams=grams, citekey_ids=citekey_ids,
        pages=pages, positions=positions
    )


def _save_corpus_index(index: CorpusSkipgramIndex, corpus_key: str) -> None:
    raw = (
        index.grams.tobytes()
        + index.citekey_ids.tobytes()
        + index.pages.tobytes()
        + index.positions.tobytes()
    )
    _atomic_write_bytes(_index_bin_path(), raw)
    header = {
        "version": _HEADER_VERSION,
        "tokenizer_version": _TOKENIZER_VERSION,
        "n": index.n,
        "key": corpus_key,
        "citekeys": index.citekeys,
        "count": len(index.grams),
    }
    _atomic_write_json(_index_header_path(), header)


def build_corpus_index(n: int = DEFAULT_N) -> CorpusSkipgramIndex:
    """The skip-gram analogue of `overlap_index.build_corpus_index` --
    same cache-hit/partial-rebuild behaviour, over the same ledger items,
    keyed the same way (a document's skip-gram cache is only ever stale
    for the same reasons its exact-tier one is: reparse, backend switch).
    """
    items = _ledger_items()
    doc_keys = [(citekey, _fingerprint_key(pdf_hash, parsed_path))
                for citekey, pdf_hash, parsed_path in items]
    corpus_key = _corpus_key(doc_keys)

    cached = _load_corpus_index(n, corpus_key)
    if cached is not None:
        return cached

    by_citekey = {citekey: (pdf_hash, parsed_path) for citekey, pdf_hash, parsed_path in items}
    citekeys_sorted = sorted(by_citekey)
    id_by_citekey = {citekey: i for i, citekey in enumerate(citekeys_sorted)}

    unsorted_grams: "array[int]" = array("Q")
    unsorted_citekey_ids: "array[int]" = array("I")
    unsorted_pages: "array[int]" = array("I")
    unsorted_positions: "array[int]" = array("I")
    for citekey in citekeys_sorted:
        pdf_hash, parsed_path = by_citekey[citekey]
        fp = fingerprint_document(citekey, pdf_hash, parsed_path, n)
        citekey_id = id_by_citekey[citekey]
        for gram_hash, page, position in fp.postings:
            unsorted_grams.append(gram_hash)
            unsorted_citekey_ids.append(citekey_id)
            unsorted_pages.append(page)
            unsorted_positions.append(position)

    order = sorted(range(len(unsorted_grams)), key=unsorted_grams.__getitem__)

    index = CorpusSkipgramIndex(
        n=n,
        citekeys=citekeys_sorted,
        grams=array("Q", (unsorted_grams[i] for i in order)),
        citekey_ids=array("I", (unsorted_citekey_ids[i] for i in order)),
        pages=array("I", (unsorted_pages[i] for i in order)),
        positions=array("I", (unsorted_positions[i] for i in order)),
    )
    _save_corpus_index(index, corpus_key)
    return index


def postings_for_gram(index: CorpusSkipgramIndex, gram_hash: int) -> list[tuple[str, int, int]]:
    lo = bisect_left(index.grams, gram_hash)
    hi = bisect_right(index.grams, gram_hash, lo=lo)
    return [
        (index.citekeys[index.citekey_ids[i]], index.pages[i], index.positions[i])
        for i in range(lo, hi)
    ]

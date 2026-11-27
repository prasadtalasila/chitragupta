"""Tier 2: deterministic light-paraphrase detection via stemmed skip-grams
(the CoReMo 2.1 design, Torrejon & Ramos, PAN 2013 winner on quality and
runtime -- discussion #115, docs/PLAGIARISM-DESIGN.md), catching the
synonym swaps and inflection changes that break tier 1's exact n-grams.

The word stream is split into even and odd original positions first,
then each family is stemmed and stopword-filtered and n-grammed on its
own, so a lone substitution leaves one family intact. Splitting after
filtering would shift every later word's family when a paraphrase swaps
a stopword for a content word (as in tests/test_feature_workflows.py's
fixture). Positions are original word indices, comparable with tier 1's.

Caches mirror `overlap_index.py`'s but are separate files with their own
version constants, so a stemmer change never rebuilds tier 1; the shared
helpers take each tier's versions as arguments. Advisory only (#115;
gating is #130's decision).
"""

from __future__ import annotations

import json
from array import array
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from itertools import accumulate
from pathlib import Path

from chitragupta import config
from chitragupta.citekey_safety import citekey_path
from chitragupta.overlap_index import (
    _atomic_write_bytes,
    _atomic_write_json,
    _fingerprint_key,
    _merge_corpus_index,
    _pages_from_parsed_text,
    _norm,
    _parse_cached_postings,
    _parse_corpus_index_binary,
    gram_hashes,
)
from chitragupta.porter_stemmer import stem

# Counted in content words: roughly two in five running words survive
# filtering, so 5 stems span about tier 1's 8 raw words.
DEFAULT_N = 5

# Bumped when the stemmer, stopwords or family split change; it is the
# whole cache migration. 2: #180's numeric windows; 3: #505's stemmer fix.
_TOKENIZER_VERSION = 3
_HEADER_VERSION = 1

# A window counts only if fewer than this share of its stems are bare
# numbers (at DEFAULT_N, at most 2 of 5). #180: 97 of 125 findings were
# numeric tables matching by chance over a ~10-digit vocabulary.
#
# A window rule, not a token rule: `WORD` splits "48.2" into two tokens,
# so only a window's company tells a real figure from a scoring grid, and
# dropping numbers would lose genuine shared figures. `stem_filter` is
# unchanged; it only normalizes allowlisted phrases.
MAX_NUMERIC_SHARE = 0.5

# A conservative function-word list: a leaked stopword only widens a
# window, while a wrongly listed content word costs recall.
STOPWORDS = frozenset(
    """
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
""".split()
)


def stem_filter(words: list[str]) -> tuple[list[str], list[int]]:
    """`words` (lowercase `[a-z0-9]+`) reduced to stemmed content words,
    plus each one's index in `words`. Numeric tokens are kept as-is.

    Whole-stream, not family-split: for normalizing allowlisted phrases
    in `verbatim_check`, never for generating skip-grams.
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
    """`words` split into its even- and odd-original-index families, as
    `(word, original_index)` pairs, before any filtering."""
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
    """`(gram_hash, start, end)` for every skip-gram in already-tokenized
    `words`; `start`/`end` are original indices of the first and last
    member, end-exclusive, matching tier 1's convention.

    Windows with `MAX_NUMERIC_SHARE` or more bare numbers are not emitted
    (#180); corpus and draft both go through here, so that is symmetric.
    Ascending within each family, even family first; not globally sorted.
    """
    postings = []
    for pairs in _families(words):
        stems, positions = _stem_filter_family(pairs)
        # A running count, so each window's share is a subtraction.
        numeric = list(accumulate((s.isdigit() for s in stems), initial=0))
        for j, gh in enumerate(gram_hashes(stems, n)):
            if numeric[j + n] - numeric[j] >= n * MAX_NUMERIC_SHARE:
                continue
            postings.append((gh, positions[j], positions[j + n - 1] + 1))
    return postings


@dataclass
class DocSkipgramFingerprint:
    citekey: str
    key: list
    n: int
    # (gram_hash, page, position), position the original index of the
    # first stemmed word.
    postings: list[tuple[int, int, int]]


def _doc_cache_path(citekey: str) -> Path:
    return citekey_path(config.OVERLAP_DIR / "docs", citekey, ".skipgram.fpr")


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
    """Tier 1's `_build_fingerprint` page bookkeeping, with skip-gram
    postings in place of contiguous grams."""
    page_words = [_norm(page_text) for page_text in _pages_from_parsed_text(parsed_path)]
    boundaries = list(accumulate(len(words) for words in page_words))
    words = [w for page in page_words for w in page]

    postings: list[tuple[int, int, int]] = []
    num_pages = len(boundaries)
    for gh, position, _end in skipgram_postings(words, n):
        # A bisect per posting, not tier 1's sweep: even postings precede
        # odd ones, so `position` is not monotonic here.
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
# The merged corpus-wide skip-gram index: tier 1's shape, separate files.
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
        n=n,
        citekeys=citekeys,
        grams=grams,
        citekey_ids=citekey_ids,
        pages=pages,
        positions=positions,
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
    """The skip-gram analogue of `overlap_index.build_corpus_index`, sharing
    its merge algorithm (`overlap_index._merge_corpus_index`).
    """
    return _merge_corpus_index(
        n, _load_corpus_index, fingerprint_document, CorpusSkipgramIndex, _save_corpus_index
    )


def postings_for_gram(index: CorpusSkipgramIndex, gram_hash: int) -> list[tuple[str, int, int]]:
    lo = bisect_left(index.grams, gram_hash)
    hi = bisect_right(index.grams, gram_hash, lo=lo)
    return [
        (index.citekeys[index.citekey_ids[i]], index.pages[i], index.positions[i])
        for i in range(lo, hi)
    ]

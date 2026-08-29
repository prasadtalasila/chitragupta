"""Per-document n-gram fingerprinting and its on-disk cache.

Split from `chitragupta/overlap_index.py` (#441): the whole-document
tokenize/hash/fingerprint primitive and the `docs/<citekey>.fpr` cache
that keys it, with no ledger or corpus-merging awareness of its own --
`fingerprint_document` takes exactly the three values
(`citekey`/`pdf_hash`/`parsed_path`) a caller already has.

`DEFAULT_N` and `_TOKENIZER_VERSION` live here rather than in
`chitragupta/overlap_index.py` even though `overlap_index_corpus.py`
also needs both: this module has no dependency on that one, so
`overlap_index_corpus.py` importing them from here is one-directional.
Defining them in `overlap_index.py` instead and importing back from
both submodules would recreate the exact cycle `chitragupta/enrich/
_docling_pool.py`'s docstring explains avoiding, for no benefit -- nothing
here needs anything either of the other two modules define.

`_atomic_write_json`/`_atomic_write_bytes`, `_fingerprint_key`,
`_parse_cached_postings` and `gram_hashes`/`_norm` are imported directly
by `chitragupta/overlap_skipgram.py` (tier 2) and
`chitragupta/dossier/_evidence_check.py` -- unaffected by this split,
since `chitragupta/overlap_index.py` re-exports every name that used to
live there, including these.
"""

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from itertools import accumulate
from pathlib import Path

from chitragupta import config

DEFAULT_N = 8

# Mirrors chitragupta/review/verbatim_check.py's WORD/norm -- see
# chitragupta/overlap_index.py's module docstring.
WORD = re.compile(r"[a-z0-9]+")


def _norm(text: str) -> list[str]:
    return WORD.findall(text.lower())


# Bumped for #131: `_build_fingerprint`'s postings now carry a global
# (not per-page) token position, so a stale cache from before this change
# would silently misalign every diagonal. `_load_doc_cache` and
# `overlap_index_corpus._load_corpus_index` both already gate on this
# constant, so bumping it is the whole migration -- every `.fpr`/`index.bin`
# written under the old scheme reads as a cache miss and gets rebuilt.
_TOKENIZER_VERSION = 2

# A large odd 64-bit constant (fractional part of the golden ratio, scaled
# to 64 bits -- the same mixing constant Fibonacci hashing uses) for the
# rolling hash's multiplier. Any large odd constant works; this one is a
# standard choice with no small-cycle weaknesses.
_BASE = 0x9E3779B97F4A7C15
_MASK64 = (1 << 64) - 1


def _word_hash(word: str) -> int:
    return int.from_bytes(hashlib.blake2b(word.encode("utf-8"), digest_size=8).digest(), "big")


def gram_hashes(words: list[str], n: int) -> list[int]:
    """The 64-bit rolling hash of every `n`-word window of `words`, in order.

    `gram_hashes(words, n)[j]` is the hash of `words[j:j + n]`. Returns `[]`
    when there are fewer than `n` words to form a single window.

    `n < 1` raises rather than silently misbehaving: `n == 0` doesn't
    short-circuit on the `len(words) < n` check below (every word count is
    `>= 0`), and every zero-word "window" then hashes to the same constant
    -- which would make a corpus-wide lookup treat every draft position as
    a match. `n < 0` fails even louder, with an out-of-range list index a
    few lines down, once the second loop's `word_hashes[j - 1]` runs past
    the end of `words`. Callers that let `n` come from a CLI flag should
    validate before this point and report a clean usage error; this is
    the library-level backstop for anyone calling it directly.
    """
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    if len(words) < n:
        return []
    word_hashes = [_word_hash(w) for w in words]
    base_pow = pow(_BASE, n - 1, 1 << 64)
    h = 0
    for i in range(n):
        h = (h * _BASE + word_hashes[i]) & _MASK64
    hashes = [h]
    for j in range(1, len(words) - n + 1):
        h = ((h - word_hashes[j - 1] * base_pow) * _BASE + word_hashes[j + n - 1]) & _MASK64
        hashes.append(h)
    return hashes


def _pages_from_parsed_text(parsed_path: str) -> list[str]:
    """Same convention as `chitragupta/review/verbatim_check.py::pages`'s fallback:
    strip stray control bytes, split on the form-feed page boundary."""
    raw = Path(parsed_path).read_text(encoding="utf-8", errors="replace")
    return re.sub(r"[\x00-\x08\x0e-\x1f]", " ", raw).split("\f")


def _fingerprint_key(pdf_hash: str, parsed_path: str) -> list:
    """The per-document cache-validity key: `pdf_hash` plus the parsed
    file's own (size, mtime_ns) -- see chitragupta/overlap_index.py's
    module docstring for why `pdf_hash` alone is not enough."""
    try:
        st = Path(parsed_path).stat()
    except OSError:
        return [pdf_hash, None, None]
    return [pdf_hash, st.st_size, st.st_mtime_ns]


@dataclass
class DocFingerprint:
    citekey: str
    key: list
    n: int
    # (gram_hash, page, token_position), in position order (position is
    # global across the document, so this is also page order).
    postings: list[tuple[int, int, int]]


def _doc_cache_path(citekey: str) -> Path:
    return config.OVERLAP_DIR / "docs" / f"{citekey}.fpr"


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Per-process/per-call-unique temp name, then os.replace (atomic on
    # POSIX) -- mirrors chitragupta/retrieval.py::_save_cache.
    tmp_path = path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    os.replace(tmp_path, path)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    with open(tmp_path, "wb") as f:
        f.write(data)
    os.replace(tmp_path, path)


def _parse_cached_postings(
    data: object, key: list, n: int, tokenizer_version: int
) -> "list[tuple[int, int, int]] | None":
    """The shape-and-freshness check a doc-level postings cache needs,
    shared with `overlap_skipgram.py` (tier 2): `None` for an unexpected
    shape, a tokenizer/n mismatch, or a stale key -- all cache misses,
    handled identically by both tiers.

    Shared because it was, byte for byte, the one piece of `_load_doc_cache`
    that carried no tier-specific state -- `tokenizer_version` is passed in
    rather than read off a module global for exactly that reason. The two
    tiers' cache *files* stay fully independent (own path, own version
    constant, own dataclass): sharing this validation step doesn't change
    that, since neither tier's cache key or invalidation depends on the
    other's `tokenizer_version` argument here.
    """
    if not isinstance(data, dict):
        return None
    if data.get("tokenizer_version") != tokenizer_version or data.get("n") != n:
        return None
    if data.get("key") != key:
        return None
    postings = data.get("postings")
    if not isinstance(postings, list):
        return None
    try:
        return [(int(h), int(p), int(pos)) for h, p, pos in postings]
    except (TypeError, ValueError):
        return None


def _load_doc_cache(citekey: str, key: list, n: int) -> "DocFingerprint | None":
    """`None` for any cache miss: absent file, corrupt JSON, an
    unexpected shape, a tokenizer/n mismatch, or a stale key -- all treated
    identically as "fingerprint fresh" rather than raising."""
    try:
        with open(_doc_cache_path(citekey), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    parsed_postings = _parse_cached_postings(data, key, n, _TOKENIZER_VERSION)
    if parsed_postings is None:
        return None
    return DocFingerprint(citekey=citekey, key=key, n=n, postings=parsed_postings)


def _save_doc_cache(fp: DocFingerprint) -> None:
    payload = {
        "tokenizer_version": _TOKENIZER_VERSION,
        "n": fp.n,
        "key": fp.key,
        "postings": [list(p) for p in fp.postings],
    }
    _atomic_write_json(_doc_cache_path(fp.citekey), payload)


def _build_fingerprint(citekey: str, pdf_hash: str, parsed_path: str, n: int) -> DocFingerprint:
    """Tokenizes the *whole* document as one continuous word stream, not
    page by page: a page-local word list can never produce the n-gram
    that straddles the boundary (last few words of page N + first few of
    page N+1), so per-page tokenization silently drops every gram that
    would let a run merge across a real page break. `position` is
    therefore a global word offset into the document, not reset at each
    page; `page` is still recorded per posting, attributed via the
    cumulative per-page word counts to whichever page contains the
    gram's *first* word -- the same "lowest page wins" convention
    `grams_for_citekey` already uses across documents, applied here
    across pages of one.
    """
    page_words = [_norm(page_text) for page_text in _pages_from_parsed_text(parsed_path)]
    boundaries = list(accumulate(len(words) for words in page_words))
    words = [w for page in page_words for w in page]
    postings: list[tuple[int, int, int]] = []
    # A linear sweep, not a `bisect_right` per posting: `position` is
    # ascending (`enumerate` over one document's grams in order), so
    # `page_idx` only ever advances, never needs to search backward. That
    # makes this O(#postings + #pages) instead of O(#postings * log
    # #pages) -- the same total work, just not re-done from scratch for
    # every one of a document's several-thousand postings.
    page_idx = 0
    num_pages = len(boundaries)
    for position, gram_hash in enumerate(gram_hashes(words, n)):
        while page_idx < num_pages and position >= boundaries[page_idx]:
            page_idx += 1
        postings.append((gram_hash, page_idx + 1, position))
    return DocFingerprint(
        citekey=citekey, key=_fingerprint_key(pdf_hash, parsed_path), n=n, postings=postings
    )


def fingerprint_document(
    citekey: str, pdf_hash: str, parsed_path: str, n: int = DEFAULT_N
) -> DocFingerprint:
    """One document's fingerprint -- from the on-disk cache if its
    `(pdf_hash, parsed-file stat)` key still matches, freshly built and
    cached otherwise."""
    key = _fingerprint_key(pdf_hash, parsed_path)
    cached = _load_doc_cache(citekey, key, n)
    if cached is not None:
        return cached
    fp = _build_fingerprint(citekey, pdf_hash, parsed_path, n)
    _save_doc_cache(fp)
    return fp


def grams_for_citekey(
    citekey: str, pdf_hash: str, parsed_path: str, n: int = DEFAULT_N
) -> dict[int, int]:
    """`{gram_hash: page}` for one document, the page being the *lowest*
    page the gram occurs on -- matching the pre-index `overlap` mode's
    `grams.setdefault` behavior (pages visited low to high, first write
    wins)."""
    fp = fingerprint_document(citekey, pdf_hash, parsed_path, n)
    pages: dict[int, int] = {}
    for gram_hash, page, _position in fp.postings:
        if gram_hash not in pages or page < pages[gram_hash]:
            pages[gram_hash] = page
    return pages

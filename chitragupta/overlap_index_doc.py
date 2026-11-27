"""Per-document n-gram fingerprinting and its on-disk cache (#441).

No ledger or corpus-merging awareness: `fingerprint_document` takes the
three values a caller has. `DEFAULT_N` and `_TOKENIZER_VERSION` live here
so `overlap_index_corpus.py` imports one way, with no cycle. Tier 2 and
`dossier/_evidence_check.py` import private helpers from here directly.
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
from chitragupta.citekey_safety import citekey_path

DEFAULT_N = 8

# Mirrors verbatim_check's WORD/norm; see overlap_index.py's docstring.
WORD = re.compile(r"[a-z0-9]+")


def _norm(text: str) -> list[str]:
    return WORD.findall(text.lower())


# Bumped for #131's global token positions; both cache loaders gate on
# it, so the bump is the whole migration.
_TOKENIZER_VERSION = 2

# A large odd 64-bit multiplier (the golden-ratio constant of Fibonacci
# hashing), a standard choice with no small-cycle weaknesses.
_BASE = 0x9E3779B97F4A7C15
_MASK64 = (1 << 64) - 1


def _word_hash(word: str) -> int:
    return int.from_bytes(hashlib.blake2b(word.encode("utf-8"), digest_size=8).digest(), "big")


def gram_hashes(words: list[str], n: int) -> list[int]:
    """The 64-bit rolling hash of every `n`-word window of `words`, in order.

    `gram_hashes(words, n)[j]` hashes `words[j:j + n]`; `[]` when there are
    fewer than `n` words. `n < 1` raises: `n == 0` would hash every window
    to one constant and match every draft position. CLI callers should
    validate first; this is the library backstop.
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
    """As `verbatim_check/_corpus.py::pages`' fallback: strip stray
    control bytes, split on the form-feed page boundary."""
    raw = Path(parsed_path).read_text(encoding="utf-8", errors="replace")
    return re.sub(r"[\x00-\x08\x0e-\x1f]", " ", raw).split("\f")


def _fingerprint_key(pdf_hash: str, parsed_path: str) -> list:
    """The per-document cache-validity key: `pdf_hash` plus the parsed
    file's (size, mtime_ns); see overlap_index.py's docstring for why."""
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
    # (gram_hash, page, token_position), in position (and so page) order.
    postings: list[tuple[int, int, int]]


def _doc_cache_path(citekey: str) -> Path:
    return citekey_path(config.OVERLAP_DIR / "docs", citekey, ".fpr")


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique temp name, then os.replace (atomic on POSIX).
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
    shared with tier 2: `None` for any cache miss. `tokenizer_version` is
    passed in so each tier's own cache and invalidation stay independent.
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
    """`None` for any cache miss (absent, corrupt, wrong shape or
    version, stale key), never raising."""
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
    """Tokenizes the whole document as one word stream, not page by page,
    so a gram straddling a page break exists and a run can merge across
    it. `position` is global; `page` is the page of the gram's first word.
    """
    page_words = [_norm(page_text) for page_text in _pages_from_parsed_text(parsed_path)]
    boundaries = list(accumulate(len(words) for words in page_words))
    words = [w for page in page_words for w in page]
    postings: list[tuple[int, int, int]] = []
    # A linear sweep, not a bisect per posting: positions ascend, so
    # `page_idx` only advances.
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
    """One document's fingerprint: cached while its `(pdf_hash,
    parsed-file stat)` key matches, else built and cached."""
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
    """`{gram_hash: page}` for one document, the page being the lowest the
    gram occurs on (first write wins, as the pre-index `overlap` mode did)."""
    fp = fingerprint_document(citekey, pdf_hash, parsed_path, n)
    pages: dict[int, int] = {}
    for gram_hash, page, _position in fp.postings:
        if gram_hash not in pages or page < pages[gram_hash]:
            pages[gram_hash] = page
    return pages

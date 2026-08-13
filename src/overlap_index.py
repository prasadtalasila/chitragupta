"""Corpus-wide n-gram fingerprint index, cached on disk under content/overlap/.

`src/review/verbatim_check.py`'s `overlap` mode used to fingerprint one source
per invocation, from scratch, in memory, and throw the work away: a `gram ->
page` dict rebuilt on every run, from text re-extracted by re-invoking
`pdftotext` as a subprocess. Fine for "compare this draft against this one
source"; unusable as the substrate for sliding an entire draft across every
parsed source in the corpus (the whole-draft scan mode this issue's
successor builds). This module is the fix: fingerprint each ledger item
once, cache the fingerprint keyed by that item's own change-detection
state, and merge the per-document fingerprints into one corpus-wide index a
future scan can binary-search.

Two independent caches, both under `config.OVERLAP_DIR` (gitignored,
regenerable, like every other content/ artifact):

- `docs/<citekey>.fpr` -- one document's fingerprint: every word n-gram's
  hash, its *global* token position in the document (not reset per page --
  see `_build_fingerprint`; a per-page reset used to break a maximal run
  across a page boundary, #131), and the page that position falls on, for
  attribution only. Keyed by `(pdf_hash, parsed-file size,
  parsed-file mtime_ns)` -- not `pdf_hash` alone. `pdf_hash` unchanged does
  not imply the parsed text is unchanged: `sync --reparse` and a
  `[parser].backend` switch both rewrite `content/parsed/<citekey>.txt`
  without touching the PDF (src/ledger.py's `upsert_reference`), so a
  cache keyed on `pdf_hash` alone would keep serving fingerprints of text
  that no longer exists. Same stat-first shape as
  `src/retrieval.py::_fingerprint`.
- `index.bin` + `index.json` -- every fingerprintable document's postings
  merged into one corpus-wide index: a sorted `array('Q')` of gram hashes
  with three parallel `array('I')` postings arrays (citekey id, page,
  position), binary-searched by `pages_for_gram`. `index.json`'s `key` is
  a sha256 over every (citekey, per-document key) pair currently in the
  corpus -- change any one document (or add/remove one) and the whole
  index is rebuilt, but *rebuilt* means re-merging already-cached
  per-document fingerprints (seconds), not re-fingerprinting the corpus:
  only documents whose own key changed pay `_build_fingerprint` again.

Both caches are read/written with no writer lock (`src/runlock.py`): like
`src/ledger.py`'s own read-only CLI, this must keep working while a `sync`
run is in progress, and staleness is handled by the key comparison above,
not by locking.

Tokenization mirrors `src/review/verbatim_check.py`'s `WORD`/`norm` --
lowercase `[a-z0-9]+` tokens -- so `grams_for_citekey` agrees with what
that script's `overlap` mode reported before this module existed.
Duplicated rather than imported: `src/` is the corpus layer `scripts/`
consumes, not the reverse, and this is two lines that must not drift out
of sync with the ones in `src/review/verbatim_check.py`.

A gram's hash is a 64-bit rolling polynomial hash over each word's
`blake2b` digest, deterministic across processes and runs (unlike
built-in `hash()`, which is salted per-process and could not be cached at
all). At the whole corpus's estimated ~7,000,000 grams, the birthday-bound
collision probability at 64 bits is on the order of 1e-6 -- overwhelmingly
unlikely to matter, but real: two different word-n-grams could in
principle hash equal, where the previous tuple-keyed dict compared words
exactly.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from array import array
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from itertools import accumulate
from pathlib import Path

from src import config

DEFAULT_N = 8

# Mirrors src/review/verbatim_check.py's WORD/norm -- see module docstring.
WORD = re.compile(r"[a-z0-9]+")


def _norm(text: str) -> list[str]:
    return WORD.findall(text.lower())


# Bumped for #131: `_build_fingerprint`'s postings now carry a global
# (not per-page) token position, so a stale cache from before this change
# would silently misalign every diagonal. `_load_doc_cache` and
# `_load_corpus_index` both already gate on this constant, so bumping it
# is the whole migration -- every `.fpr`/`index.bin` written under the old
# scheme reads as a cache miss and gets rebuilt.
_TOKENIZER_VERSION = 2
_HEADER_VERSION = 1

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
    """Same convention as `src/review/verbatim_check.py::pages`'s fallback:
    strip stray control bytes, split on the form-feed page boundary."""
    raw = Path(parsed_path).read_text(encoding="utf-8", errors="replace")
    return re.sub(r"[\x00-\x08\x0e-\x1f]", " ", raw).split("\f")


def _fingerprint_key(pdf_hash: str, parsed_path: str) -> list:
    """The per-document cache-validity key: `pdf_hash` plus the parsed
    file's own (size, mtime_ns) -- see module docstring for why `pdf_hash`
    alone is not enough."""
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
    # POSIX) -- mirrors src/retrieval.py::_save_cache.
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


def _load_doc_cache(citekey: str, key: list, n: int) -> "DocFingerprint | None":
    """`None` for any cache miss: absent file, corrupt JSON, an
    unexpected shape, a tokenizer/n mismatch, or a stale key -- all treated
    identically as "fingerprint fresh" rather than raising."""
    try:
        with open(_doc_cache_path(citekey), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("tokenizer_version") != _TOKENIZER_VERSION or data.get("n") != n:
        return None
    if data.get("key") != key:
        return None
    postings = data.get("postings")
    if not isinstance(postings, list):
        return None
    try:
        parsed_postings = [(int(h), int(p), int(pos)) for h, p, pos in postings]
    except (TypeError, ValueError):
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


# ---------------------------------------------------------------------
# Read-only ledger access. Deliberately not src/ledger.py::connect(): that
# runs the schema, migrations and a commit -- a writer, which contradicts
# this module's "no writer lock" contract (module docstring). Opened the
# same way src/ledger.py's own read-only CLI (`ledger.main`) does.
# ---------------------------------------------------------------------


def _ledger_connect_ro() -> "sqlite3.Connection | None":
    if not config.LEDGER_PATH.exists():
        return None
    return sqlite3.connect(f"file:{config.LEDGER_PATH}?mode=ro", uri=True, timeout=0)


def ledger_item(citekey: str) -> "tuple[str, str] | None":
    """`(pdf_hash, parsed_path)` for one parsed citekey whose parsed text
    still exists on disk, or `None` if the ledger, the citekey, or the
    file is missing."""
    con = _ledger_connect_ro()
    if con is None:
        return None
    try:
        row = con.execute(
            "SELECT pdf_hash, parsed_path FROM items "
            "WHERE citekey = ? AND status = 'parsed' "
            "AND pdf_hash IS NOT NULL AND parsed_path IS NOT NULL",
            (citekey,),
        ).fetchone()
    finally:
        con.close()
    if row is None:
        return None
    pdf_hash, parsed_path = row
    if not Path(parsed_path).exists():
        return None
    return pdf_hash, parsed_path


def _ledger_items() -> list[tuple[str, str, str]]:
    """`(citekey, pdf_hash, parsed_path)` for every parsed citekey whose
    parsed text still exists on disk -- the corpus-wide fingerprintable
    set. A row the ledger calls parsed but whose file has since been
    deleted is skipped, not fingerprinted as empty."""
    con = _ledger_connect_ro()
    if con is None:
        return []
    try:
        rows = con.execute(
            "SELECT citekey, pdf_hash, parsed_path FROM items "
            "WHERE status = 'parsed' AND pdf_hash IS NOT NULL AND parsed_path IS NOT NULL"
        ).fetchall()
    finally:
        con.close()
    return [(ck, h, p) for ck, h, p in rows if Path(p).exists()]


# ---------------------------------------------------------------------
# The merged corpus-wide index.
# ---------------------------------------------------------------------


@dataclass
class CorpusIndex:
    n: int
    citekeys: list[str]  # id -> citekey, sorted
    grams: "array[int]"  # sorted 'Q', parallel to the three below
    citekey_ids: "array[int]"  # 'I'
    pages: "array[int]"  # 'I'
    positions: "array[int]"  # 'I'


def _index_header_path() -> Path:
    return config.OVERLAP_DIR / "index.json"


def _index_bin_path() -> Path:
    return config.OVERLAP_DIR / "index.bin"


def _corpus_key(doc_keys: list[tuple[str, list]]) -> str:
    """sha256 over every (citekey, per-document key) pair, sorted by
    citekey -- changes if any document's fingerprint would change, or if
    one is added or removed."""
    payload = json.dumps(sorted(doc_keys), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_corpus_index(n: int, corpus_key: str) -> "CorpusIndex | None":
    try:
        with open(_index_header_path(), encoding="utf-8") as f:
            header = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(header, dict):
        return None
    if (
        header.get("version") != _HEADER_VERSION
        or header.get("tokenizer_version") != _TOKENIZER_VERSION
        or header.get("n") != n
        or header.get("key") != corpus_key
    ):
        return None
    citekeys = header.get("citekeys")
    count = header.get("count")
    if not isinstance(citekeys, list) or not isinstance(count, int) or count < 0:
        return None
    try:
        raw = _index_bin_path().read_bytes()
    except OSError:
        return None
    # 'Q' (grams) is 8 bytes/entry; the three 'I' postings arrays are 4
    # bytes/entry each -- a length mismatch means a truncated or otherwise
    # corrupt .bin, so rebuild rather than risk misreading it.
    expected_len = count * (8 + 4 + 4 + 4)
    if len(raw) != expected_len:
        return None
    grams: "array[int]" = array("Q")
    grams.frombytes(raw[: count * 8])
    offset = count * 8
    citekey_ids: "array[int]" = array("I")
    citekey_ids.frombytes(raw[offset:offset + count * 4])
    offset += count * 4
    pages: "array[int]" = array("I")
    pages.frombytes(raw[offset:offset + count * 4])
    offset += count * 4
    positions: "array[int]" = array("I")
    positions.frombytes(raw[offset:offset + count * 4])
    return CorpusIndex(
        n=n, citekeys=citekeys, grams=grams, citekey_ids=citekey_ids, pages=pages, positions=positions
    )


def _save_corpus_index(index: CorpusIndex, corpus_key: str) -> None:
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
    # Written after index.bin: a crash between the two leaves index.bin
    # matching the *new* corpus_key but index.json still naming the old
    # one, which _load_corpus_index reads as a plain cache miss (key
    # mismatch) and rebuilds from -- safe, just not free, same as any
    # other interrupted-write recovery in this codebase.
    _atomic_write_json(_index_header_path(), header)


def build_corpus_index(n: int = DEFAULT_N) -> CorpusIndex:
    """The merged corpus-wide index over every parsed, on-disk ledger item.

    A full cache hit (unchanged corpus) costs one JSON read and one binary
    read -- no fingerprinting at all. Otherwise, only documents whose own
    `(pdf_hash, parsed-file stat)` key changed are re-fingerprinted; every
    other document's postings come from its cached `.fpr` file, and the
    index is re-merged from all of them.
    """
    items = _ledger_items()
    doc_keys = [(citekey, _fingerprint_key(pdf_hash, parsed_path)) for citekey, pdf_hash, parsed_path in items]
    corpus_key = _corpus_key(doc_keys)

    cached = _load_corpus_index(n, corpus_key)
    if cached is not None:
        return cached

    by_citekey = {citekey: (pdf_hash, parsed_path) for citekey, pdf_hash, parsed_path in items}
    citekeys_sorted = sorted(by_citekey)
    id_by_citekey = {citekey: i for i, citekey in enumerate(citekeys_sorted)}

    # Accumulated into typed arrays, not a list of 4-tuples: at the
    # corpus's real scale (~7,000,000 grams) a Python list of boxed-int
    # tuples runs to the better part of a gigabyte, where the four
    # array('Q'/'I') columns together cost under 200MB -- close to the
    # issue's own "~100MB RAM" estimate for this index.
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

    # Sort by gram hash via an index permutation over the typed arrays,
    # rather than sorting tuples directly -- same reason as above.
    order = sorted(range(len(unsorted_grams)), key=unsorted_grams.__getitem__)

    index = CorpusIndex(
        n=n,
        citekeys=citekeys_sorted,
        grams=array("Q", (unsorted_grams[i] for i in order)),
        citekey_ids=array("I", (unsorted_citekey_ids[i] for i in order)),
        pages=array("I", (unsorted_pages[i] for i in order)),
        positions=array("I", (unsorted_positions[i] for i in order)),
    )
    _save_corpus_index(index, corpus_key)
    return index


def pages_for_gram(index: CorpusIndex, gram_hash: int, citekey: "str | None" = None) -> list[int]:
    """Every distinct page in the corpus (optionally narrowed to one
    `citekey`) where `gram_hash` occurs, in ascending order -- a
    binary-search lookup into `index.grams`, which is sorted.

    Deduplicated: a gram repeated more than once on the same page (a
    second occurrence of the same phrase, or two documents sharing one
    page number) would otherwise repeat that page once per posting, which
    is not what "which pages" means to a caller.
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
    collapsing to distinct pages: `src/review/verbatim_check.py`'s `scan`
    mode needs `token_position` to align a run across consecutive draft
    positions, which a deduplicated page list would throw away.
    """
    lo = bisect_left(index.grams, gram_hash)
    hi = bisect_right(index.grams, gram_hash, lo=lo)
    return [
        (index.citekeys[index.citekey_ids[i]], index.pages[i], index.positions[i])
        for i in range(lo, hi)
    ]

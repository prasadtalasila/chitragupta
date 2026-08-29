"""The merged corpus-wide n-gram index: `index.bin`/`index.json`, built
by merging every document's own fingerprint.

Split from `chitragupta/overlap_index.py` (#441). Depends one-way on
`chitragupta/overlap_index_doc.py` (the atomic-write helpers, the
per-document fingerprint key/builder, and the two version constants
that gate cache freshness on both tiers) and on
`chitragupta/overlap_index_ledger.py` (the corpus-wide fingerprintable
set) -- neither of those two imports anything from here, which is what
keeps this a plain acyclic import rather than a cycle.
"""

import hashlib
import json
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

from chitragupta import config
from chitragupta.overlap_index_doc import (
    DEFAULT_N,
    _atomic_write_bytes,
    _atomic_write_json,
    _fingerprint_key,
    fingerprint_document,
)
from chitragupta.overlap_index_doc import _TOKENIZER_VERSION as _DOC_TOKENIZER_VERSION
from chitragupta.overlap_index_ledger import _ledger_items

_HEADER_VERSION = 1


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


def _checked_corpus_index_header(
    header: object, corpus_key: str, n: int, tokenizer_version: int, header_version: int
) -> "tuple[list, int] | None":
    """`(citekeys, count)` if `header` is fresh, else `None`. Split out of
    `_parse_corpus_index_binary` to keep each half under the C1 statement
    limit -- see that function for why this pair is shared at all."""
    if not isinstance(header, dict):
        return None
    if (
        header.get("version") != header_version
        or header.get("tokenizer_version") != tokenizer_version
        or header.get("n") != n
        or header.get("key") != corpus_key
    ):
        return None
    citekeys = header.get("citekeys")
    count = header.get("count")
    if not isinstance(citekeys, list) or not isinstance(count, int) or count < 0:
        return None
    return citekeys, count


def _unpack_index_arrays(raw: bytes, count: int) -> "tuple[array, array, array, array] | None":
    """`(grams, citekey_ids, pages, positions)` unpacked from `raw`, the
    `.bin` file's contents -- `None` if the length doesn't match `count`
    (a truncated or otherwise corrupt `.bin`, so rebuild rather than risk
    misreading it). Split out of `_parse_corpus_index_binary` for the same
    reason as `_checked_corpus_index_header`.

    'Q' (grams) is 8 bytes/entry; the three 'I' postings arrays are 4
    bytes/entry each.
    """
    expected_len = count * (8 + 4 + 4 + 4)
    if len(raw) != expected_len:
        return None
    grams: "array[int]" = array("Q")
    grams.frombytes(raw[: count * 8])
    offset = count * 8
    citekey_ids: "array[int]" = array("I")
    citekey_ids.frombytes(raw[offset : offset + count * 4])
    offset += count * 4
    pages: "array[int]" = array("I")
    pages.frombytes(raw[offset : offset + count * 4])
    offset += count * 4
    positions: "array[int]" = array("I")
    positions.frombytes(raw[offset : offset + count * 4])
    return grams, citekey_ids, pages, positions


def _parse_corpus_index_binary(
    header: object,
    corpus_key: str,
    n: int,
    tokenizer_version: int,
    header_version: int,
    bin_path: Path,
) -> "tuple[list, array, array, array, array] | None":
    """The header-and-binary validation `_load_corpus_index` needs,
    shared with `overlap_skipgram.py` (tier 2) for the same reason
    `_parse_cached_postings` is: this is the tier-agnostic half of
    loading a `(header.json, index.bin)` pair -- version/key checks and
    the four-array binary unpack -- parameterized on the two version
    constants that actually differ per tier rather than read off a
    module global. `header_version` and `tokenizer_version` keep each
    tier's own cache-invalidation rule intact; only the parsing
    mechanics are shared.

    Returns `(citekeys, grams, citekey_ids, pages, positions)`, or
    `None` for any cache miss -- absent/unreadable `.bin`, a version or
    key mismatch, or a length that doesn't match a truncated-or-corrupt
    `.bin` -- so the caller only has to construct its own dataclass.
    """
    checked = _checked_corpus_index_header(header, corpus_key, n, tokenizer_version, header_version)
    if checked is None:
        return None
    citekeys, count = checked
    try:
        raw = bin_path.read_bytes()
    except OSError:
        return None
    unpacked = _unpack_index_arrays(raw, count)
    if unpacked is None:
        return None
    grams, citekey_ids, pages, positions = unpacked
    return citekeys, grams, citekey_ids, pages, positions


def _load_corpus_index(n: int, corpus_key: str) -> "CorpusIndex | None":
    try:
        with open(_index_header_path(), encoding="utf-8") as f:
            header = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    parsed = _parse_corpus_index_binary(
        header, corpus_key, n, _DOC_TOKENIZER_VERSION, _HEADER_VERSION, _index_bin_path()
    )
    if parsed is None:
        return None
    citekeys, grams, citekey_ids, pages, positions = parsed
    return CorpusIndex(
        n=n,
        citekeys=citekeys,
        grams=grams,
        citekey_ids=citekey_ids,
        pages=pages,
        positions=positions,
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
        "tokenizer_version": _DOC_TOKENIZER_VERSION,
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


_IndexT = TypeVar("_IndexT")


def _merge_corpus_index(
    n: int,
    load_cached: Callable[[int, str], "_IndexT | None"],
    fingerprint_fn: Callable[[str, str, str, int], object],
    index_cls: Callable[..., _IndexT],
    save_fn: Callable[[_IndexT, str], None],
) -> _IndexT:
    """The merge-and-cache algorithm `overlap_index.build_corpus_index` and
    `overlap_skipgram.build_corpus_index` share: same doc_keys/corpus_key
    computation, same typed-array accumulation over every document's
    postings, same permutation sort, same save call. Only the fingerprint
    function, on-disk cache and index dataclass genuinely differ per
    tier -- exactly the pieces a caller supplies here, rather than this
    function reading them off a module global.

    A full cache hit (unchanged corpus) costs one JSON read and one binary
    read -- no fingerprinting at all. Otherwise, only documents whose own
    `(pdf_hash, parsed-file stat)` key changed are re-fingerprinted; every
    other document's postings come from its cached `.fpr` file, and the
    index is re-merged from all of them.
    """
    items = _ledger_items()
    corpus_key = _corpus_key(
        [
            (citekey, _fingerprint_key(pdf_hash, parsed_path))
            for citekey, pdf_hash, parsed_path in items
        ]
    )
    cached = load_cached(n, corpus_key)
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
    unsorted_grams, unsorted_citekey_ids, unsorted_pages, unsorted_positions = (
        array("Q"),
        array("I"),
        array("I"),
        array("I"),
    )
    for citekey in citekeys_sorted:
        pdf_hash, parsed_path = by_citekey[citekey]
        fp = fingerprint_fn(citekey, pdf_hash, parsed_path, n)
        citekey_id = id_by_citekey[citekey]
        for gram_hash, page, position in fp.postings:
            unsorted_grams.append(gram_hash)
            unsorted_citekey_ids.append(citekey_id)
            unsorted_pages.append(page)
            unsorted_positions.append(position)

    # Sort by gram hash via an index permutation over the typed arrays,
    # rather than sorting tuples directly -- same reason as above.
    order = sorted(range(len(unsorted_grams)), key=unsorted_grams.__getitem__)

    index = index_cls(
        n=n,
        citekeys=citekeys_sorted,
        grams=array("Q", (unsorted_grams[i] for i in order)),
        citekey_ids=array("I", (unsorted_citekey_ids[i] for i in order)),
        pages=array("I", (unsorted_pages[i] for i in order)),
        positions=array("I", (unsorted_positions[i] for i in order)),
    )
    save_fn(index, corpus_key)
    return index


def build_corpus_index(n: int = DEFAULT_N) -> CorpusIndex:
    """The merged corpus-wide index over every parsed, on-disk ledger item.
    See `_merge_corpus_index` for the algorithm shared with tier 2's own
    `build_corpus_index`.
    """
    return _merge_corpus_index(
        n, _load_corpus_index, fingerprint_document, CorpusIndex, _save_corpus_index
    )

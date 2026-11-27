"""The merged corpus-wide n-gram index: `index.bin`/`index.json`, built
by merging every document's own fingerprint (#441). Imports
`overlap_index_doc` and `overlap_index_ledger`, neither of which imports
this.
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
    citekey; changes if any fingerprint would, or a document comes or goes."""
    payload = json.dumps(sorted(doc_keys), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _checked_corpus_index_header(
    header: object, corpus_key: str, n: int, tokenizer_version: int, header_version: int
) -> "tuple[list, int] | None":
    """`(citekeys, count)` if `header` is fresh, else `None`."""
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
    """`(grams, citekey_ids, pages, positions)` unpacked from the `.bin`
    contents, or `None` if the length doesn't match `count`: rebuild
    rather than misread a truncated file. 'Q' is 8 bytes, 'I' 4.
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
    """Header-and-binary validation shared with `overlap_skipgram.py`,
    parameterized on the two version constants so each tier keeps its own
    cache-invalidation rule.

    Returns `(citekeys, grams, citekey_ids, pages, positions)`, or `None`
    for any cache miss.
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
    # Written after index.bin: a crash between leaves a key mismatch,
    # which the loader reads as a cache miss and rebuilds.
    _atomic_write_json(_index_header_path(), header)


_IndexT = TypeVar("_IndexT")


def _merge_corpus_index(
    n: int,
    load_cached: Callable[[int, str], "_IndexT | None"],
    fingerprint_fn: Callable[[str, str, str, int], object],
    index_cls: Callable[..., _IndexT],
    save_fn: Callable[[_IndexT, str], None],
) -> _IndexT:
    """The merge-and-cache algorithm both tiers' `build_corpus_index`
    share; the caller supplies what differs per tier.

    A full cache hit costs one JSON and one binary read. Otherwise only
    documents whose `(pdf_hash, parsed-file stat)` changed are
    re-fingerprinted, and the index is re-merged from every `.fpr`.
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

    # Typed arrays, not 4-tuples: at ~7,000,000 grams boxed tuples near a
    # gigabyte, the four columns under 200MB.
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

    # Sorted via an index permutation over the arrays, for the same reason.
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
    """The merged corpus-wide index over every parsed, on-disk ledger item."""
    return _merge_corpus_index(
        n, _load_corpus_index, fingerprint_document, CorpusIndex, _save_corpus_index
    )

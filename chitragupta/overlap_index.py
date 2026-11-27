"""Corpus-wide n-gram fingerprint index, cached on disk under content/overlap/.

Each ledger item is fingerprinted once, cached by its own change state,
and merged into one index a scan can binary-search. Tier 2
(`overlap_skipgram.py`, #133) keeps its own cache and reuses only the
tier-agnostic parsers.

- `docs/<citekey>.fpr`: each gram's hash, its global token position (a
  per-page reset broke runs across page breaks, #131) and its page.
  Keyed by `(pdf_hash, parsed size, mtime_ns)`, not `pdf_hash` alone:
  `sync --reparse` and a backend switch rewrite the text, not the PDF.
- `index.bin` + `index.json`: the merged postings, keyed by a sha256 over
  every document key; a rebuild re-merges cached fingerprints and only
  re-fingerprints documents whose key changed.

No writer lock (`runlock.py`): this must work during a `sync`, and the
keys handle staleness. Tokenization duplicates `verbatim_check`'s
`WORD`/`norm` on purpose (the corpus layer does not import upward). Gram
hashes are 64-bit over `blake2b` digests, stable across processes unlike
`hash()`; at ~7,000,000 grams a collision is ~1e-6 likely, but possible.

Split into `overlap_index_doc`, `_ledger`, `_corpus` and `_query` (#441);
every name is re-exported here, the one import site callers and tests use.
"""

from __future__ import annotations

# pylint: disable=unused-import
from chitragupta.overlap_index_corpus import (  # noqa: F401
    _HEADER_VERSION,
    CorpusIndex,
    _checked_corpus_index_header,
    _corpus_key,
    _index_bin_path,
    _index_header_path,
    _load_corpus_index,
    _merge_corpus_index,
    _parse_corpus_index_binary,
    _save_corpus_index,
    _unpack_index_arrays,
    build_corpus_index,
)
from chitragupta.overlap_index_doc import (  # noqa: F401
    _BASE,
    _MASK64,
    _TOKENIZER_VERSION,
    DEFAULT_N,
    WORD,
    DocFingerprint,
    _atomic_write_bytes,
    _atomic_write_json,
    _build_fingerprint,
    _doc_cache_path,
    _fingerprint_key,
    _load_doc_cache,
    _norm,
    _pages_from_parsed_text,
    _parse_cached_postings,
    _save_doc_cache,
    _word_hash,
    fingerprint_document,
    gram_hashes,
    grams_for_citekey,
)
from chitragupta.overlap_index_ledger import (  # noqa: F401
    _ledger_connect_ro,
    _ledger_items,
    ledger_item,
)
from chitragupta.overlap_index_query import (  # noqa: F401
    pages_for_gram,
    postings_for_gram,
)

# pylint: enable=unused-import

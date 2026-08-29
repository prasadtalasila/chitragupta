"""Corpus-wide n-gram fingerprint index, cached on disk under content/overlap/.

`chitragupta/review/verbatim_check.py`'s `overlap` mode used to fingerprint one source
per invocation, from scratch, in memory, and throw the work away: a `gram ->
page` dict rebuilt on every run, from text re-extracted by re-invoking
`pdftotext` as a subprocess. Fine for "compare this draft against this one
source"; unusable as the substrate for sliding an entire draft across every
parsed source in the corpus (the whole-draft scan mode this issue's
successor builds). This module is the fix: fingerprint each ledger item
once, cache the fingerprint keyed by that item's own change-detection
state, and merge the per-document fingerprints into one corpus-wide index a
future scan can binary-search.

`chitragupta/overlap_skipgram.py` (tier 2, #133) mirrors this shape for its own,
fully independent cache -- own files, own `_TOKENIZER_VERSION`/
`_HEADER_VERSION` -- and imports `_parse_cached_postings` and
`_parse_corpus_index_binary` from here rather than duplicating them,
since those two are the tier-agnostic validate-and-parse mechanics with
no cache-invalidation state of their own (see their own docstrings).

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
  without touching the PDF (chitragupta/ledger.py's `upsert_reference`), so a
  cache keyed on `pdf_hash` alone would keep serving fingerprints of text
  that no longer exists. Same stat-first shape as
  `chitragupta/retrieval.py::_fingerprint`.
- `index.bin` + `index.json` -- every fingerprintable document's postings
  merged into one corpus-wide index: a sorted `array('Q')` of gram hashes
  with three parallel `array('I')` postings arrays (citekey id, page,
  position), binary-searched by `pages_for_gram`. `index.json`'s `key` is
  a sha256 over every (citekey, per-document key) pair currently in the
  corpus -- change any one document (or add/remove one) and the whole
  index is rebuilt, but *rebuilt* means re-merging already-cached
  per-document fingerprints (seconds), not re-fingerprinting the corpus:
  only documents whose own key changed pay `_build_fingerprint` again.

Both caches are read/written with no writer lock (`chitragupta/runlock.py`): like
`chitragupta/ledger.py`'s own read-only CLI, this must keep working while a `sync`
run is in progress, and staleness is handled by the key comparison above,
not by locking.

Tokenization mirrors `chitragupta/review/verbatim_check.py`'s `WORD`/`norm` --
lowercase `[a-z0-9]+` tokens -- so `grams_for_citekey` agrees with what
that script's `overlap` mode reported before this module existed.
Duplicated rather than imported: `chitragupta/` is the corpus layer `scripts/`
consumes, not the reverse, and this is two lines that must not drift out
of sync with the ones in `chitragupta/review/verbatim_check.py`.

A gram's hash is a 64-bit rolling polynomial hash over each word's
`blake2b` digest, deterministic across processes and runs (unlike
built-in `hash()`, which is salted per-process and could not be cached at
all). At the whole corpus's estimated ~7,000,000 grams, the birthday-bound
collision probability at 64 bits is on the order of 1e-6 -- overwhelmingly
unlikely to matter, but real: two different word-n-grams could in
principle hash equal, where the previous tuple-keyed dict compared words
exactly.

Split (#441) into four modules along the seams this docstring already
described -- `overlap_index_doc.py` (per-document fingerprinting and its
cache), `overlap_index_ledger.py` (read-only ledger access),
`overlap_index_corpus.py` (the merged corpus-wide index) and
`overlap_index_query.py` (reading a built index) -- with every name
re-exported here so this stays the one import site
(`from chitragupta import overlap_index`) every existing caller already
uses, including `chitragupta/overlap_skipgram.py`'s own direct imports
and the tests that reach several of these as `overlap_index.<name>`.
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

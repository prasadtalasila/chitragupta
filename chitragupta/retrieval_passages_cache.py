"""The incremental cache `chitragupta/retrieval_passages.py` builds its
passage-level BM25 index from (#441).

Kept separate from `retrieval_cache.py`: this one is invalidated by the
passage sidecar, that one by the parsed `.txt`, and that one also serves
`read_only_index`. The file plumbing is shared via `_json_cache.py` (#851).
"""

from chitragupta import _reference_cut, _tokens, config, passages
from chitragupta._json_cache import MemoisedJson
from chitragupta.retrieval import _tokenize

# What may be ranked. Headings and titles are left out: BM25's length
# normalization lets a short heading matching the query outrank every
# real paragraph (titles: #762). Tables stay, as quantitative claims rest
# on them (#627).
_INDEXED_LABELS = frozenset({"text", "list_item", "table", "formula"})

# Bumped with `retrieval_cache` on tokenizer changes (2 since #790): the
# two indexes have separate fingerprints, so a stale one would rank on old
# vocabulary. `_tokens.index_version` is joined in automatically (issue 845).
_INDEX_SCHEMA_VERSION = _tokens.index_version(2)


def _passage_stats(found: list) -> list[dict]:
    """Term frequencies for the indexable passages of one document.

    `i` is the position in `passages.corpus_passages`' list, so a caller
    can look a passage up again. Passages from the reference heading on
    are dropped (`_reference_cut`): a short, title-stuffed bibliography
    entry would outrank real prose as a passage.
    """
    cut = _reference_cut.reference_cut_index(found)
    stats = []
    for i, passage in enumerate(found if cut is None else found[:cut]):
        if passage.label not in _INDEXED_LABELS:
            continue
        tokens = _tokenize(passage.text or "")
        if len(tokens) < config.MIN_PASSAGE_TOKENS:
            continue
        freqs: dict[str, int] = {}
        for token in tokens:
            freqs[token] = freqs.get(token, 0) + 1
        stats.append({"i": i, "length": len(tokens), "term_freqs": freqs})
    return stats


def _fingerprint(item) -> list:
    """What must move before a document's passage stats are rebuilt.

    Includes the sidecar's stat, which `retrieval_cache._fingerprint`
    omits: here the sidecar is the source. `MIN_PASSAGE_TOKENS` is in too,
    as it decides what enters the index.
    """
    sidecar = passages.sidecar_path(item["citekey"])
    try:
        st = sidecar.stat()
        stamp = [True, st.st_size, st.st_mtime_ns]
    except OSError:
        stamp = [False, 0, 0]
    return [item["parsed_path"] or "", item["status"], config.MIN_PASSAGE_TOKENS, *stamp]


# Shared with the document index (#851, `_json_cache.py`): a stale memo
# can only serve an entry still matching `_fingerprint(item)`.
# `_forget_cache` is for a caller that rewrote a sidecar in-process.
_CACHE = MemoisedJson(lambda: config.RETRIEVAL_PASSAGE_INDEX_PATH, _INDEX_SCHEMA_VERSION)
_load_cache = _CACHE.load
_save_cache = _CACHE.save
_forget_cache = _CACHE.forget


def _cached_entry(entry, fp: list) -> "dict | None":
    """`entry` if it is a usable cache hit, else None. A matching
    fingerprint with a bad payload once crashed the scorer (#504/M-24)."""
    if not isinstance(entry, dict) or entry.get("fingerprint") != fp:
        return None
    if not isinstance(entry.get("passages"), list) or not isinstance(entry.get("sidecar"), bool):
        return None
    return entry


def load_index(items: list) -> "tuple[dict, int]":
    """The `(citekey, passage_index)`-keyed scoring index, and how many
    parsed items had no sidecar to contribute one.

    Only `status == 'parsed'` rows (#490): a failed re-parse leaves
    `parsed_path` naming superseded text. The one public name here, as
    `retrieval_passages.py` calls only this.
    """
    cached = _load_cache()
    current = {item["citekey"] for item in items}
    new_cache: dict = {}
    index: dict = {}
    without_sidecar = 0
    changed = bool(set(cached) - current)
    for item in items:
        if item["status"] != "parsed":
            continue
        citekey = item["citekey"]
        fp = _fingerprint(item)
        entry = _cached_entry(cached.get(citekey), fp)
        if entry is None:
            entry = _build_entry(citekey, fp)
            changed = True
        new_cache[citekey] = entry
        # `sidecar`, not `not entry["passages"]`: every passage under the
        # token floor is not a missing sidecar, and needs no re-parse.
        if not entry["sidecar"]:
            without_sidecar += 1
        for stat in entry["passages"]:
            index[(citekey, stat["i"])] = stat
    if changed:
        _save_cache(new_cache)
    return index, without_sidecar


def _build_entry(citekey: str, fp: list) -> dict:
    """One document's cache entry, read fresh from its sidecar."""
    found = passages.corpus_passages(citekey)
    return {
        "fingerprint": fp,
        "sidecar": found is not None,
        "passages": _passage_stats(found or []),
    }

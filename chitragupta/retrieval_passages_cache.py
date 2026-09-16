"""The incremental cache `chitragupta/retrieval_passages.py` builds its
passage-level BM25 index from.

Split from that module at the boundary its parent
`chitragupta/retrieval.py` already had -- `retrieval_cache.py` is the
same cut, made for the same reason (#441), and the two files sit in the
same relationship. Everything here answers *what a document's indexable
passages are and when they must be recomputed*; what is left there
answers *how a query is ranked against them*. The split was forced by
docs/CODE-STANDARDS.md's 250-line C2 limit rather than chosen, which is
the kind that belongs in the same PR.

Not shared with `retrieval_cache.py`, deliberately. The two look alike
and are invalidated by different things -- that one by the parsed `.txt`,
this one by the passage sidecar beside it -- and `chitragupta/dossier/
_drift.py` composes `retrieval_cache._load_cache`/`_fingerprint`/
`_tokenize_item` directly, so generalising them would have two callers
pulling one abstraction in opposite directions. A parallel file is the
cheaper honesty.
"""

import json
import os
import uuid

from chitragupta import _reference_cut, config, passages
from chitragupta.retrieval import _tokenize

# What may be ranked. `section_header` and `title` are in
# `passages.PASSAGE_LABELS` and deliberately not here: BM25's length
# normalization rewards a short dense match, so a three-word heading whose
# text *is* the query outscores every real paragraph in the corpus while
# being evidence of nothing. A document's title is already a field on the
# document-level path, and issue #762 is where title matching gets its
# answer. `table` and `formula` stay in -- a table is what a quantitative
# claim rests on, which is why #627 put it in the sidecar at all.
_INDEXED_LABELS = frozenset({"text", "list_item", "table", "formula"})

# 2 since #790: this index is tokenized by `retrieval._tokenize`, imported
# above, whose length floor moved from 3 to 2 -- so a byte-identical
# parsed file and an untouched sidecar now produce different passage term
# frequencies. Bumped here as well as in `retrieval_cache`, and that is
# not belt-and-braces: the two indexes are separate files with separate
# fingerprints (docs/RETRIEVAL.md says so), so invalidating one says
# nothing about the other, and a stale passage index would keep ranking
# paragraphs on the old vocabulary while the document index used the new.
_INDEX_SCHEMA_VERSION = 2


def _passage_stats(found: list) -> list[dict]:
    """Term frequencies for the indexable passages of one document.

    `i` is the passage's position in `passages.corpus_passages`' own
    returned list -- what every other consumer of that function sees --
    rather than its line in the JSON, so a caller can hold the number and
    look the passage up again.

    Passages at or after the reference heading are dropped, on the
    boundary `_reference_cut` already owns rather than a re-derived one.
    That matters more here than on the document path: a bibliography
    entry is short and stuffed with title words, so as a *passage* BM25's
    length normalization would rank it above real prose rather than
    merely adding noise to a pooled score.
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

    The sidecar's own stat is here, where `retrieval_cache._fingerprint`
    deliberately leaves it out. That omission is sound there because the
    `.txt` is the source of truth and a re-parse rewrites both; here the
    sidecar *is* the source, so a restored or hand-written one beside an
    untouched `.txt` would otherwise be invisible.

    `MIN_PASSAGE_TOKENS` is here for the same reason: it decides what
    enters the index, not merely what is returned, so an entry written
    under one value cannot be reused under another.
    """
    sidecar = passages.sidecar_path(item["citekey"])
    try:
        st = sidecar.stat()
        stamp = [True, st.st_size, st.st_mtime_ns]
    except OSError:
        stamp = [False, 0, 0]
    return [item["parsed_path"] or "", item["status"], config.MIN_PASSAGE_TOKENS, *stamp]


# (path, size, mtime_ns) -> the parsed "items" mapping, for the one file
# this process last read. One entry rather than an LRU, like the document
# index's memo: a process reads one index.
_MEMO: "tuple[tuple, dict] | None" = None


def _index_stamp() -> tuple:
    path = config.RETRIEVAL_PASSAGE_INDEX_PATH
    try:
        st = path.stat()
        return (str(path), st.st_size, st.st_mtime_ns)
    except OSError:
        return (str(path), None, None)


def _forget_cache() -> None:
    """Drop the per-process memo. For tests that write the index file
    behind this module's back, and for a caller that has rewritten a
    sidecar in the same process."""
    global _MEMO
    _MEMO = None


def _load_cache() -> dict:
    """The cached passage stats, memoized per process.

    Same arrangement, and the same safety argument, as
    `retrieval_cache._load_cache`: a stale memo can only ever serve an
    entry that still matches `_fingerprint(item)`, so it cannot serve
    superseded text.
    """
    global _MEMO
    stamp = _index_stamp()
    if _MEMO is not None and _MEMO[0] == stamp:
        return _MEMO[1]
    items = _read_cache_file()
    _MEMO = (stamp, items)
    return items


def _read_cache_file() -> dict:
    try:
        with open(config.RETRIEVAL_PASSAGE_INDEX_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict) or data.get("version") != _INDEX_SCHEMA_VERSION:
        return {}
    items = data.get("items")
    return items if isinstance(items, dict) else {}


def _save_cache(items_index: dict) -> None:
    config.RETRIEVAL_PASSAGE_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": _INDEX_SCHEMA_VERSION, "items": items_index}
    # Temp file then os.replace, for the reason the document index does
    # it: deep-research dispatches parallel subagents that may all search
    # at once, and a shared fixed temp name lets one writer's partial
    # write collide with another's.
    tmp_path = config.RETRIEVAL_PASSAGE_INDEX_PATH.with_name(
        f"{config.RETRIEVAL_PASSAGE_INDEX_PATH.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
    )
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    os.replace(tmp_path, config.RETRIEVAL_PASSAGE_INDEX_PATH)
    global _MEMO
    _MEMO = (_index_stamp(), items_index)


def _cached_entry(entry, fp: list) -> "dict | None":
    """`entry` if it is a usable cache hit, else None.

    The shape check is #504/M-24's lesson from the document path: an entry
    with a matching fingerprint but a missing or wrong-typed payload was
    reused as-is and crashed the scorer with a bare KeyError. Costing one
    re-tokenization is the cheaper answer.
    """
    if not isinstance(entry, dict) or entry.get("fingerprint") != fp:
        return None
    if not isinstance(entry.get("passages"), list) or not isinstance(entry.get("sidecar"), bool):
        return None
    return entry


def load_index(items: list) -> "tuple[dict, int]":
    """The `(citekey, passage_index)`-keyed scoring index, and how many
    parsed items had no sidecar to contribute one.

    Only `status == 'parsed'` rows are read, the guard #490 added to the
    document path: a failed re-parse or a hash-changed sync leaves
    `parsed_path` naming a superseded PDF's text, and
    `passages.clear_sidecar` will already have removed the sidecar beside
    it.

    The only name here without a leading underscore, because it is the one
    thing `retrieval_passages.py` calls. The rest is this module's own
    bookkeeping, and `_drift.py`'s reach into `retrieval_cache`'s privates
    is the arrangement not to repeat.
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
        # `sidecar`, not `not entry["passages"]`. A document whose every
        # passage fell under the token floor has a sidecar and still
        # contributes nothing, and reporting it as sidecar-less would send
        # a reader to re-parse a document that is already parsed fine.
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

"""The incremental term-frequency cache `chitragupta/retrieval.py`'s
`search` builds its BM25 index from.

Split from `chitragupta/retrieval.py` (#441): fingerprinting, the on-disk
JSON cache, and assembling the index from it are one self-contained unit
that `search` calls through `_load_index` and nothing else in that module
touches directly. `chitragupta/dossier/_drift.py` also composes
`_load_cache`/`_fingerprint`/`_tokenize_item` directly, by design (see its
own docstring) -- moving here does not change what it imports from,
`from chitragupta import retrieval_cache` instead of `retrieval`.

`_tokenize`/`_full_text` stay in `chitragupta/retrieval.py`: `search`'s own
snippet-building needs them independent of caching, so `retrieval.py`
imports `_load_index` from here (at the bottom of the file, after those
two are already defined, to avoid the circular import a top-of-file
import would make) rather than this module importing `search`.
"""

import json
import os
import uuid
from pathlib import Path

from chitragupta import config

_INDEX_SCHEMA_VERSION = 1


def _parsed_file_stat(parsed_path: str | None) -> tuple[bool, int, int]:
    if parsed_path:
        try:
            st = Path(parsed_path).stat()
            return True, st.st_size, st.st_mtime_ns
        except OSError:
            pass
    return False, 0, 0


def _fingerprint(item) -> list:
    # `status` matters as much as the file itself: a parse failure after
    # a PDF change can leave parsed_path -- and the file it names -- byte
    # identical while the row moves off 'parsed' (#490). Without it here,
    # a cache entry written before that failure keeps matching and
    # `_load_index`/`_ephemeral_index` skip `_tokenize_item` -> `_full_text`
    # entirely, serving the superseded text through the very guard meant
    # to stop that.
    exists, size, mtime_ns = _parsed_file_stat(item["parsed_path"])
    return [item["title"] or "", item["parsed_path"] or "", item["status"], exists, size, mtime_ns]


# (path, size, mtime_ns) -> the parsed "items" mapping, for the one file
# this process last read. Deliberately one entry, not an LRU: a process
# reads one index, and a dict of every index ever seen would hold the
# whole 14 MB payload per path for the life of the run.
_MEMO: "tuple[tuple, dict] | None" = None


def _index_stamp() -> tuple:
    """What identifies the on-disk index right now: its path and the two
    stat fields that move whenever it is rewritten. The path is in the key
    because `config.RETRIEVAL_INDEX_PATH` is not a constant across a test
    session, and a memo keyed on size and mtime alone could carry one
    tree's index into another's."""
    path = config.RETRIEVAL_INDEX_PATH
    try:
        st = path.stat()
        return (str(path), st.st_size, st.st_mtime_ns)
    except OSError:
        return (str(path), None, None)


def _load_cache() -> dict:
    """The cached term-frequency index, memoized per process (#511/m-74).

    `search()` json-parses this file, which is 14 MB live on the corpus
    this was measured against, and deep-research dispatches several
    parallel subagents that each call `search()` more than once. Re-parsing
    it per call is the single largest fixed cost in a retrieval run and
    buys nothing: within one process the file only changes when
    `_save_cache` writes it, and `_save_cache` refreshes the memo itself.

    Staleness across processes is bounded by more than the stamp. A
    concurrent writer that produced a byte-identical size at the same
    nanosecond is already vanishingly unlikely -- but even then, every
    entry `_load_index` reuses must still match `_fingerprint(item)`, and
    that fingerprint carries the parsed file's own size and mtime. So a
    stale memo can only ever serve an entry that is still valid; it cannot
    serve superseded text, which is the invariant #490 added and this must
    not weaken.

    The returned dict is shared, not copied. Every caller here and in
    `chitragupta/dossier/_drift.py` only reads it -- that module's own
    docstring says so ("`_load_cache` only reads") -- and copying 14 MB to
    guard against a mutation nobody makes would give back the saving.
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
        with open(config.RETRIEVAL_INDEX_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict) or data.get("version") != _INDEX_SCHEMA_VERSION:
        return {}
    items = data.get("items")
    return items if isinstance(items, dict) else {}


def _forget_cache() -> None:
    """Drop the memo. For tests that write the index file behind this
    module's back, where the stamp check is not the thing under test."""
    global _MEMO
    _MEMO = None


def _save_cache(items_index: dict) -> None:
    config.RETRIEVAL_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": _INDEX_SCHEMA_VERSION, "items": items_index}
    # Write to a per-process/per-call-unique temp file in the same
    # directory, then os.replace (atomic on POSIX) -- deep-research
    # dispatches several parallel subagents that may all call search()
    # concurrently, and a shared fixed temp filename would let one
    # writer's partial write collide with another's.
    tmp_path = config.RETRIEVAL_INDEX_PATH.with_name(
        f"{config.RETRIEVAL_INDEX_PATH.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
    )
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    os.replace(tmp_path, config.RETRIEVAL_INDEX_PATH)
    # Refresh the memo from what was just written, rather than dropping it
    # and re-parsing 14 MB on the next call. Read after `os.replace`, so
    # the stamp is the one a later `_load_cache` will compute.
    global _MEMO
    _MEMO = (_index_stamp(), items_index)


def _load_index(items: list, tokenize_item) -> dict:
    """Build the term-frequency index for `items`, reusing cached
    per-document stats for anything whose fingerprint hasn't changed.

    `tokenize_item` is passed in rather than imported so this module
    doesn't need to import `chitragupta.retrieval` back -- `retrieval.py`
    already imports `_load_index` from here, and a module needing a name
    from its own importer is exactly the shape a circular import takes.

    Any cache read/schema problem (missing file, corrupt JSON, stale
    schema version, or valid JSON in an unexpected shape -- a bare array,
    an "items"/per-citekey entry that isn't a dict) is treated as a cache
    miss -- rebuild from scratch rather than fail the search. That
    promise used to stop at the entry's own shape: a dict with a matching
    "fingerprint" but a missing or wrong-typed "term_freqs"/"length" (a
    hand-edited cache, or a future format this version predates) was
    reused as-is and crashed `_bm25_scores`'s `entry["length"]`/
    `entry["term_freqs"]` reads with a raw KeyError (#504, M-24) --
    checked here instead, so the same unexpected-shape entry costs one
    re-tokenization rather than failing the whole search.
    """
    cached = _load_cache()
    current_citekeys = {item["citekey"] for item in items}
    new_index = {}
    changed = bool(set(cached) - current_citekeys)  # stale citekeys dropped
    for item in items:
        citekey = item["citekey"]
        fp = _fingerprint(item)
        cached_entry = cached.get(citekey)
        if (
            isinstance(cached_entry, dict)
            and cached_entry.get("fingerprint") == fp
            and isinstance(cached_entry.get("term_freqs"), dict)
            and isinstance(cached_entry.get("length"), int)
        ):
            new_index[citekey] = cached_entry
        else:
            new_index[citekey] = {"fingerprint": fp, **tokenize_item(item)}
            changed = True
    if changed:
        _save_cache(new_index)
    return new_index

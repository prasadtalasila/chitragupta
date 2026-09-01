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


def _load_cache() -> dict:
    try:
        with open(config.RETRIEVAL_INDEX_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict) or data.get("version") != _INDEX_SCHEMA_VERSION:
        return {}
    items = data.get("items")
    return items if isinstance(items, dict) else {}


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

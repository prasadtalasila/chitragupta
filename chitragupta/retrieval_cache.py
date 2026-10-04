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

import sys

from chitragupta import _tokens, config, ledger_paths
from chitragupta._json_cache import MemoisedJson

# 2 since #768: every entry written before it counted the tokens of the
# document's own reference list, and nothing else in the fingerprint says
# so -- the parsed file is byte-identical, only the rule for what counts
# as its text changed. The sidecar that rule reads is deliberately *not*
# in `_fingerprint` below: `passages.clear_sidecar` runs before every
# re-parse and the same parse rewrites the `.txt`, so a sidecar cannot
# move without the parsed file's own mtime moving with it.
#
# 3 since #762: an entry written before it carries no `field_freqs`, and
# `retrieval_scoring.weighted_freq` reads a missing one as "no fields" --
# which is correct for `discover/_resolve.py`'s hand-built entries and
# wrong here, where it would silently score a cached document as though
# its title matched nothing. The parsed file is again byte-identical and
# the fingerprint again cannot say so, for the same reason as 2.
#
# 4 since #790: `retrieval._tokenize`'s length floor moved from 3 to 2,
# so a byte-identical parsed file now tokenizes differently -- every
# entry written before it is missing each two-character token's counts
# and states a `length` that is ~7% short. `_fingerprint` below is a
# statement about the *file* (size, mtime, status), which has not
# changed, so it cannot see this and nothing but this constant will
# invalidate the entry. Same shape as 2 and 3, and the third time the
# rule for what a parsed file's text counts as has moved under a
# fingerprint that only watches the file.
#
# 5 since issue 844: `retrieval._full_text` decodes with `errors="replace"`
# rather than "ignore", so a parsed file with a stray non-UTF-8 byte now
# splits the words either side of it where it used to fuse them. Same
# shape as 2-4: the file is byte-identical and only the rule moved.
#
# Since issue 845 the number covers only that kind of change, and 4's
# kind is no longer a bump at all: `_tokens.index_version` joins it to a
# digest of `_tokens.INDEX`, the floor and stopwords `retrieval._tokenize`
# reads, so editing either moves this version with nobody remembering to.
# A cache file written under the bare integer reads as another version
# and is rebuilt once.
_INDEX_SCHEMA_VERSION = _tokens.index_version(5)

# How many rows the last `_load_index` saw marked `parsed` whose parsed
# file is not on disk, so were indexed on their title alone. Held here
# rather than returned because `retrieval.search`'s return type is a
# public contract with many callers; `note_missing_parsed` takes it.
_MISSING_PARSED = 0


# Confined here as well as at `_full_text` (issue 821), and that is not
# belt-and-braces: this fingerprint is what decides whether `_full_text`
# runs at all. An entry written while the row was still trusted would go
# on matching a `(size, mtime)` taken from the outside file, so the
# leaked text would be served out of the cache by the very guard meant
# to stop it. Refusing here makes a repointed row fingerprint as
# `(False, 0, 0)` and invalidates its entry. The value is relative to
# `content/parsed/` (#966), which `parsed_file` resolves.
def _parsed_file_stat(parsed_path: str | None) -> tuple[bool, int, int]:
    parsed = ledger_paths.parsed_file(parsed_path)
    if parsed:
        try:
            st = parsed.stat()
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


# The memo, its stamp, the version check and the atomic write, shared with
# the passage index (#851, chitragupta/_json_cache.py). The names below
# are the ones this module's callers -- `_load_index`, `dossier/_drift.py`,
# the tests -- already use, bound to the shared object's own methods.
#
# Staleness across processes is bounded by more than the stamp. Every
# entry `_load_index` reuses must still match `_fingerprint(item)`, which
# carries the parsed file's own size and mtime, so a stale memo can only
# ever serve an entry that is still valid; it cannot serve superseded
# text, which is the invariant #490 added. And `_load_cache`'s dict is
# shared, not copied: `dossier/_drift.py` only reads it ("`_load_cache`
# only reads", its own docstring says).
_CACHE = MemoisedJson(lambda: config.RETRIEVAL_INDEX_PATH, _INDEX_SCHEMA_VERSION)
_load_cache = _CACHE.load
_save_cache = _CACHE.save
_forget_cache = _CACHE.forget


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
    global _MISSING_PARSED
    cached = _load_cache()
    current_citekeys = {item["citekey"] for item in items}
    new_index = {}
    changed = bool(set(cached) - current_citekeys)  # stale citekeys dropped
    _MISSING_PARSED = 0
    for item in items:
        citekey = item["citekey"]
        fp = _fingerprint(item)
        # Counted from the fingerprint, so a run served wholly from the
        # cache -- the one a missing file used to be invisible on -- still
        # counts it (issue 844). fp[2] is the status, fp[3] "file exists".
        _MISSING_PARSED += fp[2] == "parsed" and not fp[3]
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


def note_missing_parsed() -> None:
    """Print the last `_load_index`'s missing-parsed count as a note on
    stderr, then forget it, so a second call in one process cannot
    report a search that did not happen.

    On stderr beside `retrieval_cli`'s other notes: stdout is the
    contract the genre skills parse. The advice is true because
    `ledger_upsert._parse_outputs_present` reads a missing parsed file
    as "outputs gone", so the next sync re-parses it.
    """
    global _MISSING_PARSED
    count, _MISSING_PARSED = _MISSING_PARSED, 0
    if count:
        print(
            f"  [note] {count} parsed source(s) have no parsed text on disk and "
            "were ranked on their title alone; `python -m chitragupta.corpus "
            "sync` re-parses them.",
            file=sys.stderr,
        )

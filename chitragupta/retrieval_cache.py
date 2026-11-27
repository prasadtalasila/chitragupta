"""The incremental term-frequency cache `chitragupta/retrieval.py`'s
`search` builds its BM25 index from (#441).

`read_only_index` is the same assembly without the write, for callers
that must not change the cache (`dossier status`, spelling correction,
#1232). `retrieval.py` imports `_load_index` at its bottom, after
`_tokenize`/`_full_text` exist, to avoid a circular import.
"""

import sys

from chitragupta import _tokens, config, ledger_paths
from chitragupta._json_cache import MemoisedJson

# Bumped when the rule for what a parsed file's text counts as changes
# while the file stays byte-identical, which `_fingerprint` cannot see:
# 2 (#768, reference lists dropped), 3 (#762, `field_freqs`), 4 (#790,
# token floor 3 -> 2), 5 (issue 844, `errors="replace"`). Since issue 845
# `_tokens.index_version` joins a digest of the tokenizer settings, so
# those edits move it automatically.
_INDEX_SCHEMA_VERSION = _tokens.index_version(5)

# Rows marked `parsed` whose file is missing, indexed on title alone.
# Held here because `retrieval.search`'s return type is a public contract.
_MISSING_PARSED = 0


# Confined here as well as at `_full_text` (issue 821): this fingerprint
# decides whether `_full_text` runs, so a repointed row must fingerprint
# as `(False, 0, 0)` or the cache would serve the leaked text. Relative
# to `config.PARSED_DIR` (#966).
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
    # `status` too: a failed parse can leave the file identical while the
    # row leaves 'parsed' (#490), and the cache must not serve it.
    exists, size, mtime_ns = _parsed_file_stat(item["parsed_path"])
    return [item["title"] or "", item["parsed_path"] or "", item["status"], exists, size, mtime_ns]


# Shared with the passage index (#851, `_json_cache.py`), bound to the
# names callers already use. A stale memo can only serve an entry still
# matching `_fingerprint(item)`, never superseded text (#490).
_CACHE = MemoisedJson(lambda: config.RETRIEVAL_INDEX_PATH, _INDEX_SCHEMA_VERSION)
_load_cache = _CACHE.load
_save_cache = _CACHE.save
_forget_cache = _CACHE.forget


def _load_index(items: list, tokenize_item) -> dict:
    """Build the term-frequency index for `items`, reusing cached
    per-document stats for anything whose fingerprint hasn't changed.

    `tokenize_item` is passed in to avoid a circular import. Any cache
    problem, including an entry of the wrong shape (#504, M-24), is a
    cache miss: rebuild rather than fail the search.
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
        # From the fingerprint, so a fully cached run counts it too
        # (issue 844). fp[2] is the status, fp[3] "file exists".
        _MISSING_PARSED += fp[2] == "parsed" and not fp[3]
        cached_entry = cached.get(citekey)
        if _reusable(cached_entry, fp):
            new_index[citekey] = cached_entry
        else:
            new_index[citekey] = {"fingerprint": fp, **tokenize_item(item)}
            changed = True
    if changed:
        _save_cache(new_index)
    return new_index


def _reusable(entry, fingerprint: list) -> bool:
    """Whether a cached entry may stand in for tokenizing its document:
    fingerprint matches and shape is what `bm25_scores` reads (#504).
    Shared, so both builders agree."""
    return (
        isinstance(entry, dict)
        and entry.get("fingerprint") == fingerprint
        and isinstance(entry.get("term_freqs"), dict)
        and isinstance(entry.get("length"), int)
    )


# `read_only_index`'s last result, keyed on its rows: one process asks
# about one corpus, twice (drift scan, then spelling vocabulary).
_READ_ONLY_MEMO: dict = {}


def read_only_index(rows: list, tokenize_item) -> dict:
    """The BM25 index for `rows`, built in memory and never saved.

    `_load_index` saves after any sync, so a report built on it would
    change what it reports on. Reuses cache entries by `_load_index`'s
    rule; a cold cache costs one tokenization per process.
    """
    fingerprints = [_fingerprint(row) for row in rows]
    # Sorted: callers read the same rows in different orders.
    key = (
        tokenize_item,
        tuple(sorted((row["citekey"], tuple(fp)) for row, fp in zip(rows, fingerprints))),
    )
    if _READ_ONLY_MEMO.get("key") == key:
        return _READ_ONLY_MEMO["index"]
    cached = _load_cache()
    index = {}
    for row, fingerprint in zip(rows, fingerprints):
        entry = cached.get(row["citekey"])
        index[row["citekey"]] = entry if _reusable(entry, fingerprint) else tokenize_item(row)
    _READ_ONLY_MEMO.update(key=key, index=index)
    return index


def note_missing_parsed() -> None:
    """Print the last `_load_index`'s missing-parsed count as a note on
    stderr, then forget it, so a second call cannot report a search that
    did not happen. The next sync re-parses a missing file
    (`ledger_upsert._parse_outputs_present`).
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

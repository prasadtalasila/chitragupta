"""A versioned JSON file of per-item stats, memoised per process.

The plumbing both retrieval caches share (#851): `retrieval_cache.py`
keeps the document index's term frequencies in one of these,
`retrieval_passages_cache.py` the passage index's. They had a
near-verbatim copy each -- memo, stamp, version check, atomic write --
with only the path and the schema version swapped, so a fix to one had
a second place to land. What stays in each is what genuinely differs:
what an item's fingerprint is, and how an entry is rebuilt.

Stdlib-only, like both callers, so it runs under bare `python`.
"""

import json
import os
import uuid
from collections.abc import Callable
from pathlib import Path


class MemoisedJson:
    """`{"version": N, "items": {...}}` at `path()`, read at most once per
    rewrite.

    `path` is a callable, not a `Path`, because both callers' paths are
    `config` attributes read at call time -- they move between test trees,
    and `CHITRAGUPTA_PROJECT` can move them in a real run.
    """

    def __init__(self, path: Callable[[], Path], version: int | str) -> None:
        self._path = path
        self._version = version
        # (stamp, items) for the one file this process last read.
        # Deliberately one entry, not an LRU: a process reads one index,
        # and a dict of every index ever seen would hold the whole payload
        # (14 MB for the document index, measured) per path for the life
        # of the run.
        self._memo: "tuple[tuple, dict] | None" = None

    def stamp(self) -> tuple:
        """What identifies the file right now: its path and the two stat
        fields that move whenever it is rewritten. The path is in the key
        because it is not a constant across a test session, and a memo
        keyed on size and mtime alone could carry one tree's index into
        another's."""
        path = self._path()
        try:
            st = path.stat()
            return (str(path), st.st_size, st.st_mtime_ns)
        except OSError:
            return (str(path), None, None)

    def load(self) -> dict:
        """The items, parsed at most once per rewrite.

        Re-parsing per call was the single largest fixed cost in a
        retrieval run (#511/m-74), and within one process the file only
        changes when `save` writes it, which refreshes the memo itself.
        The returned dict is shared, not copied: every caller only reads
        it, and copying 14 MB to guard against a mutation nobody makes
        would give back the saving.
        """
        stamp = self.stamp()
        if self._memo is not None and self._memo[0] == stamp:
            return self._memo[1]
        items = self.read_file()
        self._memo = (stamp, items)
        return items

    def read_file(self) -> dict:
        """The items on disk, or `{}` for an absent, unreadable or
        other-version file -- each of which only means "rebuild"."""
        try:
            with open(self._path(), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict) or data.get("version") != self._version:
            return {}
        items = data.get("items")
        return items if isinstance(items, dict) else {}

    def forget(self) -> None:
        """Drop the memo. For tests that write the file behind this
        object's back, and for a caller that has rewritten an input the
        stamp cannot see."""
        self._memo = None

    def save(self, items: dict) -> None:
        """Write `items` atomically and refresh the memo from them."""
        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": self._version, "items": items}
        # A per-process/per-call-unique temp file in the same directory,
        # then os.replace (atomic on POSIX): deep-research dispatches
        # parallel subagents that may all search at once, and a shared
        # fixed temp name would let one writer's partial write collide
        # with another's.
        tmp_path = path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp_path, path)
        # Refreshed from what was just written, rather than dropped and
        # re-parsed on the next call. Stamped after `os.replace`, so the
        # stamp is the one a later `load` will compute.
        self._memo = (self.stamp(), items)

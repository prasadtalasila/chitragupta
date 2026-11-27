"""A versioned JSON file of per-item stats, memoised per process.

The plumbing both retrieval caches share (#851), so a fix lands once;
each caller keeps its fingerprint and rebuild. Stdlib-only.
"""

import json
import os
import uuid
from collections.abc import Callable
from pathlib import Path


class MemoisedJson:
    """`{"version": N, "items": {...}}` at `path()`, read at most once per
    rewrite. `path` is a callable because it is a `config` attribute read
    at call time, which tests and `CHITRAGUPTA_PROJECT` move.
    """

    def __init__(self, path: Callable[[], Path], version: int | str) -> None:
        self._path = path
        self._version = version
        # One entry, not an LRU: an index payload is ~14 MB.
        self._memo: "tuple[tuple, dict] | None" = None

    def stamp(self) -> tuple:
        """The file's path, size and mtime; the path is in the key so a
        memo cannot carry one test tree's index into another's."""
        path = self._path()
        try:
            st = path.stat()
            return (str(path), st.st_size, st.st_mtime_ns)
        except OSError:
            return (str(path), None, None)

    def load(self) -> dict:
        """The items, parsed at most once per rewrite: re-parsing was a
        retrieval run's largest fixed cost (#511). Shared, not copied;
        callers only read it.
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
        # A unique temp name, then os.replace: parallel deep-research
        # subagents may write at once.
        tmp_path = path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp_path, path)
        # Stamped after `os.replace`, so a later `load` hits the memo.
        self._memo = (self.stamp(), items)

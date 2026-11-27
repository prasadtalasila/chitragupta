"""The ledger snapshot one drift sweep shares: rows, collection names and
a throwaway BM25 index (`Corpus`). `_drift` computes the report from it.
"""

import sqlite3

from chitragupta import bib_collections, ledger, ledger_tables

# Matches `survey-writer`'s `search(sub_theme, k=15)`, so a paper is
# surfaced iff the draft's original search would have shown it.
CANDIDATE_K = 15


class Corpus:
    """The ledger read once, plus the throwaway index built from it.

    One object so a sweep pays for the read once; the index is built
    lazily, so a sweep with no logged queries never builds it.
    """

    def __init__(self, rows: list[sqlite3.Row]) -> None:
        self.rows = rows
        self.citekeys = {row["citekey"] for row in rows}
        self.titles = {row["citekey"]: row["title"] or "" for row in rows}
        self.collections = {row["citekey"]: bib_collections.of_row(row) for row in rows}
        self._index: dict | None = None
        self._names: dict[str, str] | None = None
        self._renames: dict[str, tuple[str, str, bool]] | None = None
        self._stale: set[str] | None = None

    @property
    def index(self) -> dict:
        if self._index is None:
            # Read-only: a report must not write the cache it inspects.
            from chitragupta import retrieval, retrieval_cache

            self._index = retrieval_cache.read_only_index(self.rows, retrieval._tokenize_item)
        return self._index

    @property
    def stale(self) -> set[str]:
        """The keys the last sync found gone from the bib, whose rows still
        wait for `--remove-stale`; none when the ledger cannot be read."""
        if self._stale is None:
            try:
                with ledger.reading() as con:
                    self._stale = ledger_tables.stale(con)
            except (ledger.NoLedger, sqlite3.Error):
                self._stale = set()
        return self._stale

    @property
    def renames(self) -> dict[str, tuple[str, str, bool]]:
        """The ledger's recorded citekey renames, read once; none when the
        ledger cannot be read."""
        if self._renames is None:
            try:
                with ledger.reading() as con:
                    self._renames = ledger_tables.renames(con)
            except (ledger.NoLedger, sqlite3.Error):
                self._renames = {}
        return self._renames

    @property
    def names(self) -> dict[str, str]:
        """The ledger's collection names, read once and only if a recorded
        query was scoped; none when the ledger cannot be read."""
        if self._names is None:
            try:
                with ledger.reading() as con:
                    self._names = ledger_tables.collection_names(con)
            except (ledger.NoLedger, sqlite3.Error):
                self._names = {}
        return self._names

    def resolve(
        self, queries: list[tuple[str, str]], fallback: str = ""
    ) -> tuple[list[tuple[str, str]], list[str]]:
        """The queries with each recorded collection as a slug path, and
        the recorded collections that no longer name one.

        An unresolvable collection (pre-7.0.0 `groups` path, or renamed)
        is reported, not filtered on, since an empty result reads as "no
        drift". `fallback` is `scope.md`'s current collection: the log is
        append-only, so after a re-scope the scope is used instead.
        """
        paths = [path for paths in self.collections.values() for path in paths]
        resolved, unresolved = [], []
        for query, collection in queries:
            try:
                slug = bib_collections.resolve(collection, self.names, paths) if collection else ""
            except (bib_collections.UnknownCollection, bib_collections.AmbiguousCollection):
                try:
                    resolved.append((query, bib_collections.resolve(fallback, self.names, paths)))
                    continue
                except (bib_collections.UnknownCollection, bib_collections.AmbiguousCollection):
                    pass
                if collection not in unresolved:
                    unresolved.append(collection)
                continue
            resolved.append((query, slug))
        return resolved, unresolved

    def matches(self, queries: list[tuple[str, str]], k: int = CANDIDATE_K) -> dict[str, list[str]]:
        """citekey -> the recorded queries whose top-k it would land in.

        A scoped query (#254) is filtered *before* taking top-k, as
        `retrieval.search()` does; filtering after reports the wrong k.
        Collections are precomputed per sweep, hence not shared with
        `search()`.
        """
        from chitragupta import retrieval

        hits: dict[str, list[str]] = {}
        for query, collection in queries:
            terms, _added = retrieval.query_terms(query)
            if not terms:
                continue
            scores = retrieval._bm25_scores(self.index, terms)
            if collection:
                scores = {
                    citekey: score
                    for citekey, score in scores.items()
                    if bib_collections.matches(self.collections.get(citekey, ()), collection)
                }
            # Ties broken by citekey so reruns report the same order.
            ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
            for citekey, _score in ranked:
                hits.setdefault(citekey, []).append(query)
        return hits

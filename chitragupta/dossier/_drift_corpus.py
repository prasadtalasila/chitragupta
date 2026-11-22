"""The ledger snapshot one drift sweep shares: rows, collection names and
a throwaway BM25 index (`Corpus`), split from `_drift` once resolving
recorded collections (plans/1211-cg-collections-and-renames.md) took it
over this project's 250-code-line cap. `_drift` computes a report from
it; this module only answers what the corpus holds and what a recorded
query would surface.
"""

import sqlite3

from chitragupta import bib_collections, ledger, ledger_tables

# How deep to look down each recorded query's ranking. 15 matches
# `survey-writer`'s own `search(sub_theme, k=15)`: the report should
# surface a new paper if and only if the draft's original search would
# have put it in front of the writer, and a different number here would
# quietly mean something else by "would have been considered".
CANDIDATE_K = 15


class Corpus:
    """The ledger read once, plus the throwaway index built from it.

    Held as one object so that a sweep over every dossier pays for the
    table read and the tokenization once between them all, rather than
    once each. The index is built on first use, so a sweep over dossiers
    that logged no queries never builds one at all.
    """

    def __init__(self, rows: list[sqlite3.Row]) -> None:
        self.rows = rows
        self.citekeys = {row["citekey"] for row in rows}
        self.titles = {row["citekey"]: row["title"] or "" for row in rows}
        self.collections = {row["citekey"]: bib_collections.of_row(row) for row in rows}
        self._index: dict | None = None
        self._names: dict[str, str] | None = None
        self._renames: dict[str, tuple[str, str, bool]] | None = None

    @property
    def index(self) -> dict:
        if self._index is None:
            # Read-only: a report must not write the cache it inspects.
            from chitragupta import retrieval, retrieval_cache

            self._index = retrieval_cache.read_only_index(self.rows, retrieval._tokenize_item)
        return self._index

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

    def resolve(self, queries: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], list[str]]:
        """The queries with each recorded collection as a slug path, and
        the recorded collections that no longer name one.

        A query whose collection does not resolve -- a `groups` path
        recorded before 7.0.0, or a display path a rename has moved -- is
        dropped from the candidate search and reported instead: filtering
        on it would leave nothing to find, and an empty candidate list
        reads as "no drift".
        """
        paths = [path for paths in self.collections.values() for path in paths]
        resolved, unresolved = [], []
        for query, collection in queries:
            try:
                slug = bib_collections.resolve(collection, self.names, paths) if collection else ""
            except (bib_collections.UnknownCollection, bib_collections.AmbiguousCollection):
                if collection not in unresolved:
                    unresolved.append(collection)
                continue
            resolved.append((query, slug))
        return resolved, unresolved

    def matches(self, queries: list[tuple[str, str]], k: int = CANDIDATE_K) -> dict[str, list[str]]:
        """citekey -> the recorded queries whose top-k it would land in.

        Each query carries the collection its call actually ran against
        (`recorded_queries_with_collection`, #254) -- empty for a
        corpus-wide call. A non-empty collection filters the ranking to
        that shelf *before* taking the top-k, the same order
        `chitragupta.retrieval.search()` filters in: a shelf's top-k is not
        necessarily a prefix of the whole corpus's, so filtering after
        would report the wrong k candidates for a scoped query.

        The filter itself is a second `bib_collections.matches()` call
        site rather than a shared helper with `search()`'s: `search()`
        looks a row's collections up from the ledger rows it already
        loaded for scoring, while this class precomputes `self.collections`
        once per sweep (`__init__`, beside `self.titles`) so a multi-dossier
        `status --all` pays for the lookup once rather than once per
        dossier -- two different data shapes behind the same one-line call.
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
            # Ties broken by citekey so that two runs over an unchanged
            # corpus report the same candidates in the same order.
            ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
            for citekey, _score in ranked:
                hits.setdefault(citekey, []).append(query)
        return hits

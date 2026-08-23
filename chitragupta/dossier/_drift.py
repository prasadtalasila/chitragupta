"""Whether a dossier's kept evidence and rejections still match what's
currently in the corpus -- the data model and the computation, not its
CLI report.

Split out of chitragupta/dossier.py (#219), and split again from
`_drift_report` (the print/render formatting that used to sit beside
this in one CLI handler) once it was clear the combined module would
not fit under this project's 250-code-line cap on its own. `Corpus`,
`Candidate` and `Reconsider` exist as their own dataclasses rather than
plain tuples because `drift()` builds up several of each per dossier
and a caller reading `candidate.reason` is clearer than an index into a
tuple it has to remember the shape of.

`status <draft>` answers "did the corpus move under this one draft?".
`drift`/`drift_all` answer the other half: which drafts on this machine
have gone stale, and what specifically about each. Read-only, lock-free,
and never fatal -- a missing ledger, a missing dossier file and an
unparsable row are all things to report, not to fail on.
"""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import bib_collections
from chitragupta.dossier._citekeys import (
    CITED_FILES, _citekeys_in, cited_citekeys, rejected_reasons, section_citekeys,
)
from chitragupta.dossier import (
    _corpus_rows, all_dossiers, digest, dossier_name, draft_relpath, find_draft,
    recorded_corpus,
)
from chitragupta.dossier._retrieval import recorded_queries_with_collection

# How deep to look down each recorded query's ranking. 15 matches
# `survey-writer`'s own `search(sub_theme, k=15)`: the report should
# surface a new paper if and only if the draft's original search would
# have put it in front of the writer, and a different number here would
# quietly mean something else by "would have been considered".
CANDIDATE_K = 15


def _ephemeral_index(rows: list[sqlite3.Row]) -> dict:
    """A BM25 term-frequency index built in memory and thrown away.

    `chitragupta.retrieval.search()` cannot be used here, for two reasons that
    are both about this being a *report*. It connects through
    `ledger.connect()`, which mkdirs `content/`, executes the schema and
    runs migrations -- a write connection, which is exactly what
    `_corpus_rows` avoids. And it goes through `retrieval._load_index`,
    which calls `_save_cache` whenever any document's fingerprint moved
    -- which, after the sync that caused the drift being reported, is
    guaranteed. Either one would make an inspection mutate the corpus
    layer it is inspecting.

    The index itself is not the problem, though: `_tokenize_item` and
    `_bm25_scores` are pure, and the only thing that persists in
    `retrieval` is the cache write between them. So this composes the
    same two halves and skips the middle -- seeding from the on-disk
    cache where a fingerprint still matches (`_load_cache` only reads),
    tokenizing the rest into memory, and never writing back. A warm cache
    makes this nearly free; a cold or absent one costs one tokenization
    of the corpus, paid once per scan and dropped when it returns.

    Imported lazily so that `import chitragupta.dossier` stays as cheap as the
    rest of the module -- and it stays stdlib-only either way, since
    `chitragupta.retrieval` is too.
    """
    from chitragupta import retrieval

    cached = retrieval._load_cache()
    index = {}
    for row in rows:
        entry = cached.get(row["citekey"])
        if isinstance(entry, dict) and entry.get("fingerprint") == retrieval._fingerprint(row):
            index[row["citekey"]] = entry
        else:
            index[row["citekey"]] = retrieval._tokenize_item(row)
    return index


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

    @property
    def index(self) -> dict:
        if self._index is None:
            self._index = _ephemeral_index(self.rows)
        return self._index

    def matches(
        self, queries: list[tuple[str, str]], k: int = CANDIDATE_K
    ) -> dict[str, list[str]]:
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
            terms = retrieval._tokenize(query)
            if not terms:
                continue
            scores = retrieval._bm25_scores(self.index, terms)
            if collection:
                scores = {
                    citekey: score for citekey, score in scores.items()
                    if bib_collections.matches(self.collections.get(citekey, ()), collection)
                }
            # Ties broken by citekey so that two runs over an unchanged
            # corpus report the same candidates in the same order.
            ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
            for citekey, _score in ranked:
                hits.setdefault(citekey, []).append(query)
        return hits


@dataclass
class Candidate:
    """A paper in the ledger that this dossier has never weighed, which
    one of the dossier's own recorded queries would have surfaced."""
    citekey: str
    title: str
    queries: list[str]


@dataclass
class Reconsider:
    """A paper this draft read and declined, which its queries still
    reach -- carried with the reason it was declined."""
    citekey: str
    title: str
    queries: list[str]
    reason: str


@dataclass
class Drift:
    dossier: Path
    name: str
    draft: Path | None
    corpus_available: bool = False
    recorded: tuple[int, str] | None = None
    current: tuple[int, str] | None = None
    missing: dict[str, list[str]] = field(default_factory=dict)
    candidates: list[Candidate] = field(default_factory=list)
    reconsider: list[Reconsider] = field(default_factory=list)
    unconsidered: int = 0

    @property
    def drifted(self) -> bool:
        return bool(self.recorded and self.current and self.recorded[1] != self.current[1])

    @property
    def clean(self) -> bool:
        # `reconsider` is deliberately not part of this. A rejection that
        # still matches its query was true before the corpus moved and
        # will be true on every sweep after it -- counting it as drift
        # would mark every dossier that ever declined a paper permanently
        # stale, which is exactly the signal this command exists to give.
        return not self.missing and not self.candidates

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "dossier": draft_relpath(self.dossier),
            "draft": draft_relpath(self.draft) if self.draft else None,
            "corpus_available": self.corpus_available,
            "recorded": list(self.recorded) if self.recorded else None,
            "current": list(self.current) if self.current else None,
            "drifted": self.drifted,
            "missing": self.missing,
            "candidates": [
                {"citekey": c.citekey, "title": c.title, "queries": c.queries}
                for c in self.candidates
            ],
            "reconsider": [
                {"citekey": r.citekey, "title": r.title,
                 "queries": r.queries, "reason": r.reason}
                for r in self.reconsider
            ],
            "unconsidered": self.unconsidered,
        }


def drift(dossier: Path, corpus: "Corpus | None" = None) -> Drift:
    """What has gone stale about one dossier since its draft was written.

    Two findings, and they are not the same kind of thing. A **missing**
    citekey is a defect: the draft cites a paper the corpus no longer
    has, and something has to be swapped or dropped. A **candidate** is
    an opportunity: a paper the corpus has gained that this draft's own
    recorded queries would have put in front of the writer. The first is
    work; the second is a decision, and drift is still not itself a
    reason to redraft.

    Pass `corpus` to share one ledger read and one index across a sweep;
    omit it and this reads the ledger for itself.
    """
    dossier = Path(dossier)
    if corpus is None:
        rows = _corpus_rows()
        corpus = Corpus(rows) if rows is not None else None

    report = Drift(
        dossier=dossier,
        name=dossier_name(dossier),
        draft=find_draft(dossier),
        recorded=recorded_corpus(dossier),
    )
    if corpus is None:
        return report

    report.corpus_available = True
    report.current = (len(corpus.citekeys), digest(corpus.citekeys))

    sections_citing = section_citekeys(dossier)
    cited = _citekeys_in(dossier, CITED_FILES)
    report.missing = {
        citekey: sections_citing.get(citekey, [])
        for citekey in sorted(cited - corpus.citekeys)
    }

    # Everything the dossier ever weighed -- rejections included, which is
    # the point. Re-offering a paper the draft already turned down as if
    # it were new would cost exactly the re-judging that `rejected.md`
    # exists to prevent.
    mentioned = cited_citekeys(dossier)
    report.unconsidered = len(corpus.citekeys - mentioned)

    declined = rejected_reasons(dossier)
    matched = sorted(corpus.matches(recorded_queries_with_collection(dossier)).items())
    report.candidates = [
        Candidate(citekey, corpus.titles.get(citekey, ""), queries)
        for citekey, queries in matched
        if citekey not in mentioned
    ]
    # A declined paper its queries still reach, reported separately and
    # with the reason. `cited` wins the tie: a citekey that is both cited
    # and listed as rejected is a stale `rejected.md` row, not an open
    # question, and offering it back would send a reviser to re-decide
    # something the draft already acts on.
    report.reconsider = [
        Reconsider(citekey, corpus.titles.get(citekey, ""), queries, declined[citekey])
        for citekey, queries in matched
        if citekey in declined and citekey not in cited
    ]
    return report


def drift_all() -> list[Drift]:
    """One drift report per dossier on this machine, nearest-first."""
    rows = _corpus_rows()
    corpus = Corpus(rows) if rows is not None else None
    return [drift(path, corpus) for path in all_dossiers()]

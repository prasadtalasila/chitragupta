"""BM25-ranked keyword retrieval over the shared corpus layer.

This is the default retrieval implementation genre skills call against
(AGENTS.md's "Retrieval" section) -- stdlib-only, no venv or model
download needed. `chitragupta/enrich/embed_index.py` (sentence-transformers +
Chroma/Qdrant) is a verified, working embedding-based upgrade path with
a matching `search(query, k)` shape, ready to swap in without changing
callers once BM25 stops being enough for this corpus -- that's a
deliberate call to make when it comes up, not a threshold this module
should assert a number for. It is a *replacement*, not a complement:
nothing here fuses or re-ranks the two, and a caller uses one or the
other (docs/RETRIEVAL.md).

Two boundaries worth knowing, because they're easy to assume otherwise.
This module reads the ledger's `parsed_path` -- `content/parsed/*.txt` --
and never `content/docling/`, so running the enrichment layer's Docling
stage does not change what BM25 ranks or what its snippets say; only `[parser].backend`
does. And nothing in `chitragupta/enrich/__main__.py` imports this module, so
the enrichment layer neither uses nor updates this index. `parsed_path` is
only ever read when the row's `status` is `'parsed'` (#490) -- a failed
reparse or a hash-changed sync can leave the column pointing at text a
superseded PDF produced, and `status` is what says so.

Ranking is Okapi BM25 (stdlib-only: no rank_bm25 dependency), not raw
term-frequency -- term-frequency alone has no document-length
normalization, so a long document only needs to accumulate more raw
hits than a short one to outrank it, regardless of how small a
fraction of the long document those hits represent.

Scale: a naive implementation re-reads and re-tokenizes every
document's parsed text from disk on every call, which grows linearly
with corpus size and with each document's length. Term-frequency stats
per document are cached to disk (config.RETRIEVAL_INDEX_PATH), keyed by
a cheap per-item fingerprint (parsed-file stat -- exists/size/mtime, not
content), so a call only re-tokenizes documents whose text actually
changed since the last run -- mirroring chitragupta/ledger.py's own
stat-before-hash skip logic and chitragupta/enrich/embed_index.py's embedding
cache. Building a snippet for the returned top-k still reads those
(bounded, small) documents' text fresh, since a snippet needs the real
surrounding text, not just term counts.
"""

# The paragraph above is the *cross-run* half of "Scale": what survives
# between processes, on disk. The within-run half lives in
# `retrieval_cache._load_cache`, which memoizes the parsed index per
# process on the file's `(path, size, mtime_ns)` -- 14 MB live on the
# corpus this was measured against, and `deep-research` dispatches
# several parallel subagents that each call `search()` more than once, so
# re-parsing it per call was the largest fixed cost in a retrieval run
# (#511/m-74). Said here as a comment rather than in the docstring above
# because docs/CODE-STANDARDS.md's C2 counts docstring lines and this
# module has two of headroom.

import math
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chitragupta import bib_collections, ledger, retrieval_cache
from chitragupta._passage_words import _CORE_STOPWORDS as _STOPWORDS

# Question words and question-forming auxiliaries -- rare in academic
# PDFs, so they carry high IDF and out-compete the terms a question is
# actually about. Query-side only: see _query_terms below.
# docs/CORPUS-SEARCH.md has the measurement.
_INTERROGATIVES = {
    "what",
    "why",
    "how",
    "who",
    "whom",
    "whose",
    "which",
    "when",
    "where",
    "can",
    "could",
    "would",
    "should",
    "will",
    "shall",
    "does",
    "did",
}

# Standard Okapi BM25 constants (term-frequency saturation and length
# normalization strength) -- the usual defaults, not tuned against this
# corpus specifically.
_K1 = 1.5
_B = 0.75


@dataclass
class SearchResult:
    citekey: str
    title: str
    score: float
    snippet: str


def _tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in _STOPWORDS]


def short_query_terms(query: str) -> list[str]:
    """1-2 character words in `query` dropped *only* by the length floor.

    A stopword this short ("in", "of") is excluded -- it is dropped by
    `_STOPWORDS` regardless of length, so naming it explains nothing.
    What's left is a real content word ("AI", "5G") that can never
    contribute to ranking, letting a caller (the CLI) warn instead of a
    query built from only such terms returning empty unexplained. Not
    applied to `_tokenize` itself: lowering the floor needs an index
    format change (`_INDEX_SCHEMA_VERSION`).
    """
    return [
        w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) <= 2 and w not in _STOPWORDS
    ]


def _query_terms(query: str) -> list[str]:
    """`_tokenize(query)` with interrogatives also dropped -- query-side
    only, so a document's own term frequencies and every IDF stay put."""
    return [w for w in _tokenize(query) if w not in _INTERROGATIVES]


# Occurrences of one query term that `_windows` will anchor a candidate
# window on before it stops looking for more of that term. A ceiling on
# work for a pathological document, not a quality knob: 500 anchors of one
# term already spread across the whole text, and the top few windows come
# out of scoring, not out of how many candidates were offered.
_MAX_ANCHORS_PER_TERM = 500

# Bracketed digits/commas/hyphens only, so a real citation marker
# ([12], [3, 7], [12-14]) is stripped and [Figure 2] / [sic] survive.
# 22.8% of retrieved snippets carry one of the corpus's own markers and
# nothing downstream ever needs it -- OpenScholar's remove_citations is
# the idea; not its regex, which also globally deletes every ']'.
_CITATION_MARKER = re.compile(r"\[\d+(?:\s*[,-]\s*\d+)*\]")


def _clean_window(text: str) -> str:
    """Whitespace-normalized `text` with a numeric citation marker
    stripped."""
    return " ".join(_CITATION_MARKER.sub("", text).split())


def _windows(text: str, terms: set[str], width: int, count: int) -> list[str]:
    """The `count` best-matching windows of `text`, in document order.

    Scored by how many *distinct* query terms fall inside, not by raw hit
    count, so a passage repeating one word doesn't outrank one that
    actually covers the query. Candidate windows are anchored on every
    occurrence of every term and then de-overlapped, so a passage from
    late in a long document is reachable.

    Deterministic, which matters more than it looks. `terms` is a set, and
    string hashing is randomised per process, so anything that depends on
    the order those terms come out in gives a different answer run to run.
    Nothing here does: anchors are sorted before scoring, the score is a
    count over the whole term set, and ties break on position.
    """
    lower = text.lower()
    anchors: list[int] = []
    for term in terms:
        start = lower.find(term)
        found = 0
        # Bounded per term rather than across all of them, so a book-length
        # document that says "twin" ten thousand times cannot crowd out
        # every anchor for "greenhouse". Scoring rewards distinct-term
        # coverage, so losing a term's anchors entirely would work directly
        # against what the window is chosen for -- and a shared budget
        # would pick its victim by set order, i.e. at random.
        while start != -1 and found < _MAX_ANCHORS_PER_TERM:
            anchors.append(start)
            found += 1
            start = lower.find(term, start + 1)
    if not anchors:
        return []

    scored: list[tuple[int, int, int]] = []
    half = width // 2
    for anchor in sorted(set(anchors)):
        begin = max(0, anchor - half)
        end = min(len(text), begin + width)
        window = lower[begin:end]
        hits = sum(1 for term in terms if term in window)
        scored.append((hits, begin, end))

    chosen: list[tuple[int, int]] = []
    for _, begin, end in sorted(scored, key=lambda item: (-item[0], item[1])):
        if any(begin < other_end and end > other_begin for other_begin, other_end in chosen):
            continue
        chosen.append((begin, end))
        if len(chosen) == count:
            break
    return [_clean_window(text[begin:end]) for begin, end in sorted(chosen)]


def _snippet(text: str, terms: set[str], window: int = 500) -> str:
    """The single best `window` characters of `text` for `terms`.

    This used to return the window around the *first* occurrence of
    whichever term came out of the `terms` set first -- and since string
    hashing is randomised per process, that made the same query on the
    same document return a different snippet run to run. Harmless-ish at
    a 500-character window, where you get enough context either way, and
    not harmless at all at the short windows an earlier version of this
    module rejected candidates on -- an irreproducible snippet there meant
    an irreproducible rejection (docs/REJECTION.md).

    Shared with `evidence` through `_windows`, so a snippet is the
    best-covering passage rather than an arbitrary one, and the same
    passage every run.
    """
    best = _windows(text, terms, width=window, count=1)
    if best:
        return best[0]
    return _clean_window(text[:window])


def _full_text(item: sqlite3.Row) -> str:
    text_parts = [item["title"] or ""]
    # A non-'parsed' status means parsed_path may point at a superseded
    # version's text (or none at all) -- mark_parse_failed and a
    # hash-changed re-sync both leave the column set without updating what
    # it names (#490). overlap_index_ledger.py already gates on status;
    # this was BM25 retrieval and evidence's own read serving the stale
    # text as current.
    if item["status"] == "parsed" and item["parsed_path"]:
        try:
            text_parts.append(
                Path(item["parsed_path"]).read_text(encoding="utf-8", errors="ignore")
            )
        except OSError:
            pass
    return "\n".join(text_parts)


def _tokenize_item(item: sqlite3.Row) -> dict:
    tokens = _tokenize(_full_text(item))
    return {"length": len(tokens), "term_freqs": dict(Counter(tokens))}


def _bm25_scores(index: dict, terms: list[str]) -> dict[str, float]:
    doc_count = len(index)
    if doc_count == 0:
        return {}
    avgdl = sum(entry["length"] for entry in index.values()) / doc_count

    term_set = set(terms)
    doc_freq = {
        t: sum(1 for entry in index.values() if entry["term_freqs"].get(t)) for t in term_set
    }
    idf = {t: math.log((doc_count - doc_freq[t] + 0.5) / (doc_freq[t] + 0.5) + 1) for t in term_set}

    scores: dict[str, float] = {}
    for citekey, entry in index.items():
        doc_len = entry["length"]
        norm = 1 - _B + _B * (doc_len / avgdl if avgdl else 0)
        score = 0.0
        for t in term_set:
            freq = entry["term_freqs"].get(t, 0)
            if freq == 0:
                continue
            score += idf[t] * (freq * (_K1 + 1)) / (freq + _K1 * norm)
        if score > 0:
            scores[citekey] = score
    return scores


def search(
    query: str, k: int = 5, snippet_chars: int = 500, collection: str | None = None
) -> list[SearchResult]:
    """Rank ledger items by BM25 relevance to `query`. Returns top-k.

    `collection` restricts the result to items in that Zotero collection
    or one beneath it (chitragupta/bib_collections.py), which is #195's curated
    subset: a chapter on modelling searching only the modelling shelf.
    Scoring is deliberately left corpus-wide and the filter applied to the
    ranking -- narrowing the index instead would change every IDF, so the
    same query would score differently depending on the filter, and the
    cached index could not be shared between filtered and unfiltered runs.

    `snippet_chars` defaults to enough context for a caller (e.g. a genre
    skill) to judge relevance itself before citing -- see the "Retrieve"
    step in the genre skills for why that judgment shouldn't just trust
    the score.

    One `SearchResult` per citekey, by construction rather than by a cap
    (issue #305): `scores` below is a dict keyed by citekey, so a
    document cannot contribute two entries to `ranked` no matter how
    many of its terms match. A per-citekey cap would be a no-op here --
    it is `chitragupta.enrich.embed_index.search()`, ranking individual
    chunks rather than whole documents, that needs one. Tested in
    tests/test_retrieval.py so a future chunk-level BM25 index can't
    silently lose this property.
    """
    terms = _query_terms(query)
    if not terms:
        return []

    with ledger.connection() as con:
        items = ledger.all_items(con)

    index = retrieval_cache._load_index(items, _tokenize_item)
    scores = _bm25_scores(index, terms)
    by_citekey = {item["citekey"]: item for item in items}
    if collection is not None:
        scores = {
            citekey: score
            for citekey, score in scores.items()
            if bib_collections.matches(bib_collections.of_row(by_citekey[citekey]), collection)
        }
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:k]

    term_set = set(terms)
    results = []
    for citekey, score in ranked:
        item = by_citekey[citekey]
        results.append(
            SearchResult(
                citekey=citekey,
                title=item["title"],
                score=score,
                snippet=_snippet(_full_text(item), term_set, window=snippet_chars),
            )
        )
    return results


# `evidence`, and this layer's CLI (`python -m chitragupta.draft retrieve`),
# split into chitragupta/retrieval_cli.py (#441) -- this module crossed the
# 250-code-line C2 limit, and neither `evidence` nor the CLI is needed by
# `search`/`_bm25_scores`/anything above. `_windows` and `_full_text` stay
# here (both are needed by `search`'s own snippet-building, independent
# of `evidence`), so retrieval_cli.py imports them from here rather than
# the reverse.
#
# `main` is re-exported via module `__getattr__` (PEP 562), not a plain
# `from chitragupta.retrieval_cli import main` at the bottom of the file:
# retrieval_cli.py imports `search`/`_windows`/`_full_text`/`SearchResult`
# back from this module, and `python -m chitragupta.retrieval` -- unlike
# `import chitragupta.retrieval` -- executes this file under the name
# `__main__`, a *different* module object from `chitragupta.retrieval` in
# `sys.modules`. A plain bottom-of-file import would then have
# retrieval_cli.py's own `from chitragupta.retrieval import ...` trigger a
# second, real import of this file under its actual name, which reaches
# this same line again while retrieval_cli.py is still mid-import and
# fails with "cannot import name 'main' from partially initialized
# module" -- reproduced and confirmed before landing this fix. `__getattr__`
# defers the import until `.main` is actually read, which
# `chitragupta/draft.py`'s `retrieval.main(argv)` dispatch does long after
# both modules have finished loading normally, and which a bare `-m` run
# never does at all -- so it stays the silent no-op every other flat
# verb module in this project is. (`chitragupta/spec/__init__.py`'s
# `_cli.py` split doesn't need this: a package's `__init__.py` is always
# imported under its real name first, `-m` included, so it never hits
# this trap.)
def __getattr__(name: str) -> Any:
    if name == "main":
        from chitragupta.retrieval_cli import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

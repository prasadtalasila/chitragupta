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

Two boundaries worth knowing, because they're easy to assume otherwise. This module reads
the ledger's `parsed_path` -- `content/parsed/*.txt`, plus this layer's own sidecar beside
it, read for where the reference list starts and nothing else (`_reference_cut`) -- and
never `content/docling/`, so running the enrichment layer's Docling stage does not change
what BM25 ranks or what its snippets say; only `[parser].backend`
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

import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chitragupta import (
    _reference_cut,
    bib_collections,
    ledger,
    retrieval_cache,
    retrieval_expansion,
    retrieval_scoring,
    retrieval_tables,
)
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


@dataclass
class SearchResult:
    citekey: str
    title: str
    score: float
    snippet: str


# `> 1`, not `> 2`, since #790: a two-character token is a content word
# in a technical bibliography ("AI", "DT", "5G", "ML") and the old floor
# put every one of them outside both the index and the query, so a search
# for "5G" returned nothing with no ranking it could have contributed to.
# Measured before it moved, on this project's own corpus
# (bench/RESULTS.md, 2026-09-16): on the 32 of 258 self-retrieval queries
# whose terms the floor actually changes, recall@5 goes 0.8438 -> 0.9062
# and nDCG@5 0.7335 -> 0.8130, six queries better against one worse.
# Stopping at 2 rather than 1 is measured too, not assumed: floor 1 wins
# nothing floor 2 had not already won and costs 13.5% more tokens per
# document. The stopword list is consulted independently of the length,
# so "of" and "in" stay out at either floor.
def _tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 1 and w not in _STOPWORDS]


def short_query_terms(query: str) -> list[str]:
    """Single-character words in `query` dropped *only* by the length floor.

    A stopword this short ("a") is excluded -- it is dropped by
    `_STOPWORDS` regardless of length, so naming it explains nothing.
    What's left is a word that can never contribute to ranking, letting a
    caller (the CLI) warn instead of a query built from only such terms
    returning empty unexplained.

    **One character, not two, since #790.** This used to name "AI" and
    "5G", which now rank; a warning about a word that *did* reach ranking
    is worse than no warning, because it sends the reader looking for a
    cause that is not there. The floor and this function are two readings
    of one number and have to move together.
    """
    return [
        w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) <= 1 and w not in _STOPWORDS
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
    # Matched as a *word*, not as a substring, on both halves below. This
    # was `str.find`, and #790 is what made the difference bite: the
    # tokenizer admits two-character terms now, and "ai" sits inside
    # maintainer, said, detail, fair and failed. Measured on this
    # project's corpus before the fix, 37 of 134 appearances of a
    # two-character query term in a returned snippet were substring-only
    # -- the snippet did not contain the word the reader searched for. A
    # snippet exists so a caller can judge relevance itself rather than
    # trust a score, and one anchored inside "said" cannot serve that.
    # Lookarounds over `[a-z0-9]`, and deliberately **not** `\b`: `\b` is
    # defined over `[A-Za-z0-9_]` plus Unicode letters, where `_tokenize`
    # splits on `[a-z0-9]+` alone, so the two disagree on an underscore
    # and on an accented letter. `_tokenize("ai_model")` is
    # `["ai", "model"]`, so such a document *ranks* on "ai" -- and under
    # `\b` it yielded no window at all, falling back to the paper's
    # opening 500 characters with the searched-for word nowhere in them,
    # while `evidence` returned nothing for a document it had just
    # ranked. Worse than the substring match this replaced, rather than
    # better. Written this way the boundary is the tokenizer's by
    # construction: "co" matches in "co-simulation" and not in "control",
    # exactly as the index counted it.
    patterns = {term: re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])") for term in terms}
    anchors: list[int] = []
    for pattern in patterns.values():
        # Bounded per term rather than across all of them, so a book-length
        # document that says "twin" ten thousand times cannot crowd out
        # every anchor for "greenhouse". Scoring rewards distinct-term
        # coverage, so losing a term's anchors entirely would work directly
        # against what the window is chosen for -- and a shared budget
        # would pick its victim by set order, i.e. at random.
        for found, match in enumerate(pattern.finditer(lower)):
            if found == _MAX_ANCHORS_PER_TERM:
                break
            anchors.append(match.start())
    if not anchors:
        return []

    scored: list[tuple[int, int, int]] = []
    half = width // 2
    for anchor in sorted(set(anchors)):
        begin = max(0, anchor - half)
        end = min(len(text), begin + width)
        window = lower[begin:end]
        hits = sum(1 for pattern in patterns.values() if pattern.search(window))
        scored.append((hits, begin, end))

    chosen: list[tuple[int, int]] = []
    for _, begin, end in sorted(scored, key=lambda item: (-item[0], item[1])):
        if any(begin < other_end and end > other_begin for other_begin, other_end in chosen):
            continue
        chosen.append((begin, end))
        if len(chosen) == count:
            break
    return retrieval_tables.render_windows(text, chosen, _clean_window)


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
            raw = Path(item["parsed_path"]).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            pass
        else:
            # The paper's own bibliography carries other papers' titles as
            # this one's body text; #768 and chitragupta/_reference_cut.py
            # have the measurement. Cut here rather than at index build so
            # the snippet `search` shows, the windows
            # `retrieval_cli.evidence` returns and the tokens BM25 ranks
            # are all drawn from the same text -- a snippet quoting a
            # reference list would be evidence of nothing.
            text_parts.append(_reference_cut.strip_references(raw, item["parsed_path"]))
    return "\n".join(text_parts)


def _tokenize_item(item: sqlite3.Row) -> dict:
    # `field_freqs` is what #762's weights read; `term_freqs` and
    # `length` are unchanged, so an index entry written before it existed
    # still scores -- see `_INDEX_SCHEMA_VERSION`, which is bumped anyway
    # so that no entry is *missing* the field counts a live weight needs.
    tokens = _tokenize(_full_text(item))
    fields = retrieval_scoring.field_freqs(item, _tokenize)
    return {"length": len(tokens), "term_freqs": dict(Counter(tokens)), "field_freqs": fields}


def _bm25_scores(index: dict, terms: list[str]) -> dict[str, float]:
    """Moved to `chitragupta/retrieval_scoring.py` (#762), and delegated
    to rather than re-exported: `chitragupta/dossier/_drift.py` and
    `chitragupta/discover/_resolve.py` both reach for this name, and a
    module-level alias would bind the function object at import, so a
    test patching the new module's `bm25_scores` would not reach them."""
    return retrieval_scoring.bm25_scores(index, terms)


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
    it is a ranker of sub-document units that needs one, which since
    #769 means `chitragupta.retrieval_passages.search_passages()` as
    much as `enrich.embed_index.search()`. Tested in
    tests/test_retrieval.py so this module cannot silently lose it.
    """
    terms = _query_terms(query)
    if not terms:
        return []
    # Expansion is computed from the typed terms alone and never fed
    # back through itself: an added term is not looked up as an acronym
    # in turn, so no vocabulary can expand into a second expansion. An
    # added term then scores exactly as a typed one does -- #789's own
    # sweep put full weight ahead of every fraction of it, so there is no
    # per-term weight here for a caller to set or for the ranker to read.
    added = retrieval_expansion.expand(terms, _tokenize)
    terms = terms + [token for _, token in added]

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

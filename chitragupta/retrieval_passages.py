"""BM25 whose unit is a paragraph rather than a whole document (#769).

`retrieval.search` picks a source, then shows a 500-character window
chosen by a different rule, with no page. Here the ranked object and the
displayed object are the same: a reading-ordered paragraph from the
passage sidecar, verbatim, with its page. An alternative unit, not a
replacement (`retrieve search --unit passage`).

Scores of the two units are on different scales and must never be sorted
into one list. #762's field weights are inert here by design: weighting
a paragraph for its paper's title would reintroduce the pooling this
drops (docs/CONFIG.md). Stdlib only, no venv or model.
"""

# A well-matched paper has a passage per paragraph, so this unit needs
# `config.MAX_PASSAGES_PER_SOURCE`, which `retrieval.search` (one per
# citekey) does not. No over-fetch multiplier as in `embed_index.search`:
# `bm25_scores` returns every scoring passage, so `_capped` walks the whole
# ranked list (#305's failure cannot occur).

from dataclasses import dataclass

from chitragupta import (
    collection_filter,
    config,
    ledger,
    passages,
    retrieval_passages_cache,
    retrieval_scoring,
)
from chitragupta.retrieval import query_terms


@dataclass
class PassageResult:
    """One ranked paragraph. `text` is verbatim and quotable, a real
    reading-ordered paragraph from a rung-2 sidecar."""

    citekey: str
    title: str
    score: float
    text: str
    page: int | None
    passage_index: int
    label: str | None


@dataclass
class PassageSearch:
    """`results`, plus how many parsed sources this path could not reach.

    A `pdftotext` parse leaves no sidecar and so is absent, not ranked
    low; a document-level score would be incomparable, so the gap is
    reported instead.
    """

    results: list[PassageResult]
    without_sidecar: int


def _capped(ranked: list, k: int) -> list:
    """The first `k` of `ranked` in which no citekey appears more than
    `config.MAX_PASSAGES_PER_SOURCE` times; the list is sorted, so each
    source keeps its best passages.
    """
    limit = config.MAX_PASSAGES_PER_SOURCE
    seen: dict[str, int] = {}
    kept = []
    for key, score in ranked:
        citekey = key[0]
        if seen.get(citekey, 0) >= limit:
            continue
        seen[citekey] = seen.get(citekey, 0) + 1
        kept.append((key, score))
        if len(kept) == k:
            break
    return kept


def _results(ranked: list, by_citekey: dict) -> list[PassageResult]:
    """The ranked keys resolved back to their passages.

    Re-reads each winner's sidecar, as the index holds term counts only.
    A position that no longer resolves (a re-parse landing between the
    ranking and this loop) is dropped, not raised as an IndexError.
    """
    found = []
    for (citekey, i), score in ranked:
        current = passages.corpus_passages(citekey) or []
        if i >= len(current):
            continue
        passage = current[i]
        found.append(
            PassageResult(
                citekey=citekey,
                title=by_citekey[citekey]["title"],
                score=score,
                text=passage.text,
                page=passage.page,
                passage_index=i,
                label=passage.label,
            )
        )
    return found


def search_passages(query: str, k: int = 5, collection: str | None = None) -> PassageSearch:
    """Rank the corpus's paragraphs by BM25 relevance to `query`.

    `collection` filters the ranking, not the index, as `retrieval.search`
    does: narrowing the index would change every IDF. No `snippet_chars`:
    the paragraph is returned at its own length. Deterministic: ties break
    on `(citekey, passage_index)`, never on `set` order (see
    `retrieval._windows`).
    """
    terms, _added = query_terms(query)
    if not terms:
        return PassageSearch([], 0)

    with ledger.reading() as con:
        items = ledger.all_items(con)
        members = collection_filter.members(con, items, collection)

    index, without_sidecar = retrieval_passages_cache.load_index(items)
    scores = retrieval_scoring.bm25_scores(index, terms)
    by_citekey = {item["citekey"]: item for item in items}
    if members is not None:
        scores = {key: score for key, score in scores.items() if key[0] in members}
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return PassageSearch(_results(_capped(ranked, k), by_citekey), without_sidecar)

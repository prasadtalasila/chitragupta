"""ITER-RETGEN (Shao et al., *Findings of EMNLP 2023*) with a human's own
hand-edited prose standing in for the model generation `y_{t-1}` --
FEATURE-ROADMAP.md's E4, "the draft is the query". No model writes the
query, so retrieval stays deterministic; `docs/RAG.md`'s "Stage 11:
revision" says why this sidesteps the paper's dominant failure mode.

Two rounds, never more (`docs/RAG.md`: rounds 3-7 gain about one recall
point). Merge-then-cap, unlike FlashRAG's `IRCoT`, which never truncates.
Both rounds score the whole corpus whatever `k`, so capping each round
and the merge at `k` loses no candidate.
"""

from chitragupta.retrieval import SearchResult, _query_terms, search

# Characters of section prose added to the second round's query, so a
# long section cannot swamp the sub-theme's own terms. Unmeasured, like
# EVIDENCE_CHARS: E4 asks for an explicit bound, not a benchmarked one.
Y_PREV_MAX_CHARS = 1500


def _bound_y_prev(y_prev: str, limit: int = Y_PREV_MAX_CHARS) -> tuple[str, bool]:
    """`y_prev` single-spaced and cut to at most `limit` characters, on a
    word boundary where possible. Returns `(text, truncated)` so a caller
    can say so; blank input gives `("", False)`.
    """
    flat = " ".join(y_prev.split())
    if len(flat) <= limit:
        return flat, False
    cut = flat[:limit].rsplit(" ", 1)[0]
    return cut, True


def search_iterative(
    query: str,
    y_prev: str,
    k: int = 5,
    snippet_chars: int = 500,
    collection: str | None = None,
) -> tuple[list[SearchResult], bool]:
    """Two-round retrieval: `search(query)`, then `query` again with the
    bounded `y_prev` as `context`. Merged by citekey (higher score wins),
    sorted by score then citekey, and sliced to `k`.

    Returns `(results, y_prev_truncated)`. Round 2 is skipped when
    `y_prev` bounds to nothing or `query` has no terms: prose-only
    retrieval is a different feature from E4.
    """
    round1 = search(query, k=k, snippet_chars=snippet_chars, collection=collection)
    bounded, truncated = _bound_y_prev(y_prev)
    if not bounded or not _query_terms(query):
        return round1, truncated

    # The prose goes in as `context`, not appended to the query: it is
    # ranked on, but never spelling-corrected (#1232).
    round2 = search(query, k=k, snippet_chars=snippet_chars, collection=collection, context=bounded)
    merged: dict[str, SearchResult] = {}
    for result in (*round1, *round2):
        current = merged.get(result.citekey)
        if current is None or result.score > current.score:
            merged[result.citekey] = result
    ranked = sorted(merged.values(), key=lambda r: (-r.score, r.citekey))
    return ranked[:k], truncated

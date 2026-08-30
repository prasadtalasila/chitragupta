"""ITER-RETGEN (Shao et al., *Findings of EMNLP 2023*) with a human's own
hand-edited prose standing in for the model generation the paper calls
`y_{t-1}` -- FEATURE-ROADMAP.md's E4, "the draft is the query". The
paper forms its next query by concatenating the previous generation
with the original question (`y_{t-1} || q`); no model writes it, so the
retrieval path stays deterministic. Here `y_{t-1}` is a section's own
hand-edited prose (the draft fingerprint, #454/#462, is what says it
changed), not a model's output -- see `docs/RAG.md`'s "Stage 11:
revision" for why that sidesteps the paper's own dominant failure mode
(a bad first generation entrenching a bad query).

Deliberately two rounds, never more (`docs/RAG.md`: iteration 2 gains
13.7-16.6 recall points, iterations 3-7 gain about one) -- there is no
parameter here to ask for a third. Deliberately merge-then-cap, not
FlashRAG's `IRCoT` shape, which merges two rounds with `max(old, new)`
but never truncates the result (a live crash in their own issue
tracker, per `docs/RAG.md`). Both rounds are computed against the whole
corpus by `chitragupta.retrieval.search()` regardless of `k` (`k` only
truncates the returned list, not what gets scored), so there is no
candidate loss from using the same `k` for each round and the final
cap.
"""

from chitragupta.retrieval import SearchResult, _query_terms, search

# Characters of hand-edited section prose appended to a query before a
# second retrieval round. A long section would otherwise swamp the
# sub-theme's own query terms in a bag-of-words score -- the reason
# this is an explicit, documented character cut (matching
# chitragupta/retrieval_cli.py's EVIDENCE_CHARS/EVIDENCE_WINDOWS shape)
# rather than a token limit some downstream call would apply silently.
# Unmeasured, same as EVIDENCE_CHARS: FEATURE-ROADMAP.md's E4 asks for
# an explicit bound, not a specific number backed by a benchmark.
Y_PREV_MAX_CHARS = 1500


def _bound_y_prev(y_prev: str, limit: int = Y_PREV_MAX_CHARS) -> tuple[str, bool]:
    """`y_prev` collapsed to single-spaced text and cut to at most
    `limit` characters, on a word boundary where one exists in range.

    Returns `(bounded_text, truncated)` so a caller can say so -- a
    silent clip is exactly what this replaces. Blank input (including
    whitespace-only) returns `("", False)`.
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
    """Two-round retrieval: round 1 is `search(query, ...)` unchanged;
    round 2 appends a bounded `y_prev` (`_bound_y_prev`) to `query` and
    searches again. Results are merged by citekey -- when a citekey
    scored in both rounds, the higher score wins -- re-sorted
    descending by score (ties broken on citekey, for a deterministic
    order), and sliced to `k`.

    Returns `(results, y_prev_truncated)`. Round 2 is skipped -- and
    round 1's own result returned unchanged -- whenever `y_prev` bounds
    to nothing, or `query` itself tokenizes to no terms (`_query_terms`):
    a query with no terms has no sub-theme anchor for `y_prev` to
    extend, and round 2 would be prose-only retrieval, a different
    feature from what E4 describes.
    """
    round1 = search(query, k=k, snippet_chars=snippet_chars, collection=collection)
    bounded, truncated = _bound_y_prev(y_prev)
    if not bounded or not _query_terms(query):
        return round1, truncated

    round2 = search(f"{query} {bounded}", k=k, snippet_chars=snippet_chars, collection=collection)
    merged: dict[str, SearchResult] = {}
    for result in (*round1, *round2):
        current = merged.get(result.citekey)
        if current is None or result.score > current.score:
            merged[result.citekey] = result
    ranked = sorted(merged.values(), key=lambda r: (-r.score, r.citekey))
    return ranked[:k], truncated

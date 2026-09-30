"""The cross-encoder that reorders `embed_index.search()`'s over-fetched
passages before the per-citekey cap (#380).

Its own module rather than a pair of functions inside
`embed_index.py`, for the reason docs/CODE-STANDARDS.md gives: that file
already owns building the Chroma index and querying it, and a second
model -- a different architecture, loaded from a different config key,
on a different schedule -- is a third responsibility. The 250-code-line
limit is what surfaced it; the boundary is the point.

`embed_index.search()` decides *whether* to call this (`config.RERANK`)
and *where* in its pipeline to do so. This module decides nothing about
placement and holds no state: the loaded model is cached by
`chitragupta/reranker.py`, the corpus-layer loader `discover` shares
(#853).
"""

from chitragupta import config, reranker


def rerank(query: str, hits: list[dict]) -> list[dict]:
    """`hits` reordered best-first by a cross-encoder over
    (query, passage) pairs.

    Public because `search()` is not the only sensible caller and
    because a benchmark scores this stage in isolation, but it is the
    *ordering* that is the contract here, not the model: the scorer is
    reached through `reranker.load_reranker` precisely so a test can substitute
    a stub whose ranking is known and assert on the order, without a
    model download.

    Deliberately total rather than thresholded. A cross-encoder's logit
    is unbounded and uncalibrated across models, so "keep everything
    above 0.5" would mean something different for every value of
    `rerank_model`; ranking is the only thing that transfers.
    """
    if not hits:
        return hits
    scores = reranker.load_reranker(config.RERANK_MODEL).predict(
        [(query, hit["snippet"]) for hit in hits]
    )
    return [hit for _score, hit in sorted(zip(scores, hits), key=lambda pair: -pair[0])]

"""The cross-encoder that reorders `embed_index.search()`'s over-fetched
passages before the per-citekey cap (#380).

`embed_index.search()` decides whether and where to call this; it holds
no state (the model is cached by `chitragupta/reranker.py`, #853).
"""

from chitragupta import config, reranker


def rerank(query: str, hits: list[dict]) -> list[dict]:
    """`hits` reordered best-first by a cross-encoder over
    (query, passage) pairs.

    The *ordering* is the contract, reached through
    `reranker.load_reranker` so a test can substitute a stub. Total, not
    thresholded: a cross-encoder's logit is uncalibrated across models.
    """
    if not hits:
        return hits
    scores = reranker.load_reranker(config.RERANK_MODEL).predict(
        [(query, hit["snippet"]) for hit in hits]
    )
    return [hit for _score, hit in sorted(zip(scores, hits), key=lambda pair: -pair[0])]

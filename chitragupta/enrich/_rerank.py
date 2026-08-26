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
placement and holds no state beyond the loaded model.
"""

import functools
from typing import Any

from chitragupta import config


# Cached on the model id rather than on nothing, so the cache cannot
# outlive a change to which model is configured -- and so a test can
# clear it by name. Loaded on the first reranked call, never at import:
# `enrich` is an optional extra and this module is imported by code
# paths that never search.
@functools.lru_cache(maxsize=1)
def _load_reranker(model_id: str) -> Any:
    from sentence_transformers import CrossEncoder

    try:
        return CrossEncoder(model_id)
    # Broad on purpose, and not suppressed: sentence-transformers raises
    # anything from OSError to a huggingface_hub error depending on why a
    # model id will not load, and every one of them means the same thing
    # to the user. Re-raised rather than swallowed, so BLE001 does not fire.
    except Exception as exc:
        raise RuntimeError(
            f"[enrich].rerank is on but the cross-encoder {model_id!r} could not be "
            "loaded. Set [enrich].rerank_model to a model that is available, or turn "
            "reranking off with [enrich].rerank = false."
        ) from exc


def rerank(query: str, hits: list[dict]) -> list[dict]:
    """`hits` reordered best-first by a cross-encoder over
    (query, passage) pairs.

    Public because `search()` is not the only sensible caller and
    because a benchmark scores this stage in isolation, but it is the
    *ordering* that is the contract here, not the model: the scorer is
    reached through `_load_reranker` precisely so a test can substitute
    a stub whose ranking is known and assert on the order, without a
    model download.

    Deliberately total rather than thresholded. A cross-encoder's logit
    is unbounded and uncalibrated across models, so "keep everything
    above 0.5" would mean something different for every value of
    `rerank_model`; ranking is the only thing that transfers.
    """
    if not hits:
        return hits
    scores = _load_reranker(config.RERANK_MODEL).predict([(query, hit["snippet"]) for hit in hits])
    return [hit for _score, hit in sorted(zip(scores, hits), key=lambda pair: -pair[0])]

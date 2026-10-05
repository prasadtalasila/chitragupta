"""The cross-encoder that reranks candidates, loaded once per model id.

One loader for the two layers that rerank (#853). The enrichment layer's
`enrich/_rerank.py` reorders `embed_index.search()`'s over-fetched
passages, and the corpus-layer `discover` ladder reorders its fused topic
candidates -- one model, one cache, one config key
(`[enrich].rerank_model`). It lived in `enrich/_rerank.py` as the private
`_load_reranker`, which `discover` reached into, so a rename inside the
enrichment layer could break a corpus command. Here it sits below both,
and imports flow the allowed way: enrich imports the corpus layer, never
the reverse.

Loading needs the `enrich` extra (sentence-transformers). The import is
inside `load_reranker`, so importing this module never does; a caller
without the extra gets the `ImportError` on the first load, and one
whose model will not load gets the `RuntimeError` below. `discover`
asks only with `[enrich].rerank` on, and treats either as "keep the
fused order" with a note (#977).
"""

import functools
from typing import Any


# Cached on the model id rather than on nothing, so the cache cannot
# outlive a change to which model is configured -- and so a test can
# clear it by name. Loaded on the first reranked call, never at import:
# `enrich` is an optional extra and this module is imported by code
# paths that never search.
@functools.lru_cache(maxsize=1)
def load_reranker(model_id: str) -> Any:
    """The `sentence_transformers.CrossEncoder` for `model_id`."""
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

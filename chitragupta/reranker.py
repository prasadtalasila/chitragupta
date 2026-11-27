"""The cross-encoder that reranks candidates, loaded once per model id.

Shared by `enrich/_rerank.py` and the corpus-layer `discover` ladder
(#853), and kept below both so enrich imports the corpus layer, never the
reverse. Needs the `enrich` extra; the import is inside `load_reranker`,
which raises `ImportError` or `RuntimeError`, and `discover` treats either
as "keep the fused order" (#977).
"""

import functools
from typing import Any


# Keyed on the model id so the cache cannot outlive a config change.
# Loaded on first use, never at import: `enrich` is an optional extra.
@functools.lru_cache(maxsize=1)
def load_reranker(model_id: str) -> Any:
    """The `sentence_transformers.CrossEncoder` for `model_id`."""
    from sentence_transformers import CrossEncoder

    try:
        return CrossEncoder(model_id)
        # Broad on purpose: a model that will not load raises anything from
        # OSError to a huggingface_hub error. Re-raised, so BLE001 is quiet.
    except Exception as exc:
        raise RuntimeError(
            f"[enrich].rerank is on but the cross-encoder {model_id!r} could not be "
            "loaded. Set [enrich].rerank_model to a model that is available, or turn "
            "reranking off with [enrich].rerank = false."
        ) from exc

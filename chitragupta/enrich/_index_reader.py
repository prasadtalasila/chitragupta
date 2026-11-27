"""The embedding index opened for reading: what `embed_index.search()`
queries, loaded once and never created on the way (#853).

Borrowing the writer's helper loaded a model per `search()` call (once per
claim in `review coverage`) and created an empty directory and collection,
turning "run the embed stage" into "the index found nothing". This caches
the pair and opens only what exists, saying what is missing.
"""

import functools
import logging
from typing import Any

from chitragupta import config, overlap_chroma

logger = logging.getLogger("chitragupta.enrich.embed_index")


# Keyed on both values explicitly: tests patch them and an env var can
# change them, so a key on neither would serve the first project's index
# for the whole process. `maxsize=1`: one index is searched at a time.
@functools.lru_cache(maxsize=1)
def _handles(chroma_dir: str, model_id: str) -> tuple[Any, Any]:
    """The Chroma client and embedding model for one index and model."""
    import chromadb
    from sentence_transformers import SentenceTransformer

    return chromadb.PersistentClient(path=chroma_dir), SentenceTransformer(model_id)


def open_for_search() -> "tuple[Any, Any] | None":
    """`(collection, model)` for the configured index and model, or
    `None`, with a warning naming what is missing, when the index
    directory or this model's collection does not exist."""
    if not config.CHROMA_DIR.is_dir():
        logger.warning(
            "no embedding index at %s -- run the enrich `embed` stage first", config.CHROMA_DIR
        )
        return None
    client, model = _handles(str(config.CHROMA_DIR), config.EMBEDDING_MODEL)
    collection = overlap_chroma.existing_collection(client)
    if collection is None:
        logger.warning(
            "no %s collection in %s -- run the enrich `embed` stage for this model first",
            overlap_chroma.corpus_key(),
            config.CHROMA_DIR,
        )
        return None
    return collection, model

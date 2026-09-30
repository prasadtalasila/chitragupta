"""The embedding index opened for reading: what `embed_index.search()`
queries, loaded once and never created on the way (#853).

Two defects shared one cause, `search()` borrowing the writer's
`get_client_and_model()`:

- **A model load per call.** `review coverage` calls `search()` once
  per claim, and each call built a fresh Chroma client and
  sentence-transformer -- seconds, plus a torch import, per claim. The
  pair is cached here on the two values that decide it.
- **A reader that creates what it reads.** The writer's helper `mkdir`s
  the index directory, and `get_or_create_collection` made an empty
  collection, turning "run the embed stage" into "the index found
  nothing" for every later reader. This opens only what exists, and
  says what is missing.

Its own module rather than more of `embed_index.py`, which owns
building the index and ranking a query against it and sits near
docs/CODE-STANDARDS.md's 250-code-line limit.
"""

import functools
import logging
from typing import Any

from chitragupta import config, overlap_chroma

logger = logging.getLogger("chitragupta.enrich.embed_index")


# Keyed on both values explicitly, never on nothing: they are module
# attributes of `config` that tests patch and an env var can change for
# one run, and a cache keyed on neither would serve the first project's
# model and index for the rest of the process. `maxsize=1` because a
# process searches one index at a time; a change evicts the old pair.
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

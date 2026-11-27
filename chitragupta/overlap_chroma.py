"""The only module in tier 3 that reaches the optional embedding stack.

`chromadb` and `sentence-transformers` come from the `enrich` extra. Every
other part of tier 3 (overlap_align, overlap_segments, overlap_embed) is
stdlib-only, so it is testable with no model present; only what is here
has to be probed for.
"""

from typing import Any

from chitragupta import chroma_paging, config


def optional_stack() -> tuple[Any, Any] | None:
    """`(chromadb, SentenceTransformer)`, or `None` if the enrich
    extra is not installed.

    `embed_index.get_client_and_model()` raises uncaught and `mkdir`s
    `content/chroma/`, so it cannot serve as an availability probe.
    """
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None
    return chromadb, SentenceTransformer


def built_collection(chromadb_module) -> Any:
    """The corpus collection for the configured embedding model, or
    `None` when it does not exist or is empty.

    Not `get_or_create_collection`: an empty collection would make "enrich
    never ran" look like a tier that found nothing. Not a caught
    `get_collection` either: chroma's not-found exception type has changed
    across releases. Asking what exists needs neither.
    """
    if not config.CHROMA_DIR.is_dir():
        return None
    collection = existing_collection(chromadb_module.PersistentClient(path=str(config.CHROMA_DIR)))
    return collection if collection is not None and collection.count() else None


def existing_collection(client) -> Any:
    """The configured model's collection through `client`, or `None`;
    asked, never created. Shared with `embed_index.search()` (#853).
    """
    from chitragupta.enrich import embed_index

    wanted = embed_index.collection_name()
    # chromadb 0.5 lists objects, 1.0 bare names; both handled, no pin.
    names = {getattr(existing, "name", existing) for existing in client.list_collections()}
    return client.get_collection(wanted) if wanted in names else None


def corpus_key() -> str:
    """The Chroma collection name tier 3 would read or write right now,
    without importing `chitragupta/enrich/` directly.

    Costs nothing and works without the enrich group; `recheck` records it
    so a baseline can tell a model change from an edit.
    """
    from chitragupta.enrich import embed_index

    return embed_index.collection_name()


class Embedder:
    """The sentence-transformers model, loaded on first use.

    Lazy: a scan with no dossier must not pay hundreds of MB to find it has
    nothing to do. Encoding and comparing are separate calls so each source
    is encoded once per draft, not once per citing section; they are also
    the seams a test replaces. This module never imports numpy, so a fake
    may return plain lists.
    """

    def __init__(self, model=None) -> None:
        self._model = model

    @property
    def model(self) -> Any:
        if self._model is None:
            from chitragupta.enrich import embed_index

            _client, self._model = embed_index.get_client_and_model()
        return self._model

    def encode(self, texts: list[str]) -> Any:
        # Normalized, so a dot product is the cosine.
        return self.model.encode(texts, show_progress_bar=False, normalize_embeddings=True)

    def encode_lists(self, texts: list[str]) -> list[list[float]]:
        """`encode`, as plain lists -- what `collection.query` takes."""
        return self.encode(texts).tolist()

    def similarity(self, left, right) -> list[list[float]]:
        """The cosine matrix between two already-encoded batches."""
        return (left @ right.T).tolist()


def shortlist(collection, embedder, citekeys: list[str], text: str, limit: int) -> list[str]:
    """`citekeys`, ranked by how close the collection's own chunks put
    them to `text`, capped at `limit`.

    The section is chunked and encoded once. Then one query per citekey,
    not one `$in` query (#954): Chroma ranks chunks, so one long source
    could take every slot and over-fetching only moves the threshold.
    ~5.5 ms a query on chromadb 1.5.9. Only distances are read: chunks
    carry no page, so ranking documents is all this can honestly answer.
    """
    from chitragupta.enrich import embed_index

    if len(citekeys) <= 1:
        # Nothing to rank.
        return list(citekeys)
    embeddings = embedder.encode_lists(embed_index.chunk_text(text))
    best: dict[str, float] = {}
    for citekey in citekeys:
        raw = collection.query(
            query_embeddings=embeddings,
            n_results=1,
            where={"citekey": citekey},
            include=["distances"],
        )
        # A source's distance is its nearest across the section's chunks.
        distances = [distance for row in raw["distances"] for distance in row]
        if distances:
            best[citekey] = min(distances)
    ranked = sorted(best, key=best.__getitem__)
    # A citekey with no chunk (PDF never parsed) ranks last rather than
    # vanishing, so it only takes a slot no embedded source wanted.
    ranked += [key for key in citekeys if key not in best]
    return ranked[:limit]


def absent_citekeys(collection, citekeys) -> set[str]:
    """Which of `citekeys` own no chunk in `collection` at all.

    A metadata-only `get`. `shortlist`'s capped list cannot answer this:
    an unembedded source past the cap is silently absent (#499).
    """
    if not citekeys:
        return set()
    # Sorted, since a set's order is unstable across runs. Paged: SQLite's
    # limit counts the chunks coming back, not the keys asked (#581).
    hits = chroma_paging.all_rows(
        collection, where={"citekey": {"$in": sorted(citekeys)}}, include=["metadatas"]
    )
    present = {m.get("citekey") for m in hits["metadatas"]}
    return set(citekeys) - present

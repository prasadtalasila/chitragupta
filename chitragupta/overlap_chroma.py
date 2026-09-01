"""The only module in tier 3 that reaches the optional embedding stack.

`chromadb` and `sentence-transformers` come from pyproject.toml's
`enrich` Poetry group, which a checkout need not have installed --
`chitragupta/enrich/embed_index.py` builds `content/chroma/` with them and is
the enrichment layer's own business. Tier 3 of the overlap scan
(`chitragupta/overlap_embed.py`) reads what that layer built, and this module is
the seam between them.

One module for it, deliberately, and this is the property worth keeping:
**every other part of tier 3 is stdlib-only.** The alignment
(`chitragupta/overlap_align.py`), the segmentation (`chitragupta/overlap_segments.py`)
and the tier's own policy (`chitragupta/overlap_embed.py`) all import under a
bare `python`, so all three are testable without the optional stack
present and without a fake standing in for a model. Only what is here
has to be probed for, and probing is most of what it does.

Three things live here:

- `optional_stack()`, which answers "can this host embed at all" without
  the side effects `embed_index.get_client_and_model()` has (it imports
  bare, raising `ModuleNotFoundError` uncaught, and `mkdir`s
  `content/chroma/` on the way past -- so neither "the import worked" nor
  "the directory exists" can be read off it as an availability signal).
- `built_collection()`, which answers "has the corpus actually been
  embedded under the currently configured model".
- `Embedder`, which loads the model on first use and is the two seams
  the alignment needs: encode a batch, and compare two encoded batches.
- `shortlist`, which is the only thing the built collection is used
  *for* -- ranking which of a section's cited sources are worth
  aligning against.
"""

from typing import Any

from chitragupta import config


def optional_stack() -> tuple[Any, Any] | None:
    """`(chromadb, SentenceTransformer)`, or `None` if the enrich Poetry
    group is not installed.

    `embed_index.get_client_and_model()` imports these bare and raises
    `ModuleNotFoundError` uncaught, and it `mkdir`s `content/chroma/` on
    the way past -- so neither "the import worked" nor "the directory
    exists" can be read off it as an availability signal. This is the
    probe that one is missing, in the shape `chitragupta/pdf_text.py` already
    uses for its own optional backend.
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

    `get_or_create_collection` deliberately not used: creating an empty
    collection here would turn "the enrichment layer never ran" into a
    tier that runs and finds nothing, which is the exact confusion this
    module's docstring says to avoid. Nor is `get_collection` called
    speculatively and its failure caught -- chroma's not-found exception
    type has moved between releases (`ValueError`, then
    `InvalidCollectionException`, then `NotFoundError`), so catching the
    right one is a version bet and catching every one is a blanket
    `except` over a call that can also fail for reasons worth seeing.
    Asking what exists first needs neither.
    """
    if not config.CHROMA_DIR.is_dir():
        return None
    from chitragupta.enrich import embed_index

    client = chromadb_module.PersistentClient(path=str(config.CHROMA_DIR))
    wanted = embed_index.collection_name()
    # chromadb 0.5 lists collection objects and 1.0 lists bare names;
    # both are handled here rather than pinning a client version this
    # repo does not otherwise care about.
    names = {getattr(existing, "name", existing) for existing in client.list_collections()}
    if wanted not in names:
        return None
    collection = client.get_collection(wanted)
    return collection if collection.count() else None


def corpus_key() -> str:
    """The Chroma collection name tier 3 would read or write right now --
    `embed_index.collection_name()`, exposed through this seam so a
    caller outside `chitragupta/enrich/` never imports it directly (see
    module docstring).

    Computed from `config.EMBEDDING_MODEL` alone, so it costs nothing --
    no chroma client, no installed enrich group -- and is available even
    where `built_collection()` above returns `None`. That is the point:
    `recheck` records this beside a baseline so a later comparison can
    tell "the corpus was rebuilt under a different model" from "an edit
    changed the findings", which `tier == "embedding"` alone cannot say.
    """
    from chitragupta.enrich import embed_index

    return embed_index.collection_name()


class Embedder:
    """The sentence-transformers model, loaded on first use.

    Lazy because loading it costs a few hundred megabytes and several
    seconds, and a scan whose draft has no dossier -- the ordinary case
    on a host that never ran the drafting pipeline -- must not pay that
    to find out it has nothing to do.

    **Encoding and comparing are separate calls, deliberately.** An
    earlier shape took two lists of *text* and returned a matrix, which
    read better and re-encoded every source segment once per draft
    section that cited it: on one real chapter that was 25 sections x 5
    sources x ~1200 segments of repeat work, and encoding is the whole
    cost of this tier. Splitting them lets `overlap_embed.align_draft`
    encode each source once for the whole draft and each section once for
    all its sources.

    `encode` and `similarity` are also the two seams a test replaces, so
    the alignment can be exercised over a hand-written matrix with no
    model present. Matrix multiplication is left to whatever the model
    returned (`sentence-transformers` hands back a numpy array, and `@`
    on two of those is the fast path); this module never imports numpy
    itself, which is what keeps a fake free to return plain lists.
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
        # Normalized, so a dot product *is* the cosine and the alignment
        # never divides by a norm it would otherwise recompute per cell.
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

    One `collection.query()` for the whole section, not one per citekey:
    `embed_index.search()` re-embeds a single query string at a time,
    which is right for interactive retrieval and wrong at scan scale.
    The section is chunked with the same `chunk_text()` the index was
    built with, every chunk is embedded in one `model.encode()` call, and
    all of them are queried at once.

    Only `metadata["citekey"]` is read off the hits, and the chunk text
    is discarded: chunk metadata is `{citekey, title, text_hash}` with no
    page and no offset, so nothing built on a chunk could say which page
    of the source it came from. Ranking which *documents* are worth
    aligning against is all this collection can honestly answer, and it
    is exactly what a shortlist needs.
    """
    from chitragupta.enrich import embed_index

    if len(citekeys) <= 1:
        # Nothing to rank, and a query would cost an encode to reorder a
        # list of one.
        return list(citekeys)
    chunks = embed_index.chunk_text(text)
    raw = collection.query(
        query_embeddings=embedder.encode_lists(chunks),
        n_results=limit,
        where={"citekey": {"$in": list(citekeys)}},
    )
    ranked = _ranked_citekeys(raw)
    # A citekey the collection has no chunk for -- a source in the
    # bibliography whose PDF never parsed -- ranks last rather than
    # vanishing, so the shortlist still fills up to its cap.
    ranked += [key for key in citekeys if key not in ranked]
    return ranked[:limit]


def _ranked_citekeys(raw: dict) -> list[str]:
    """Citekeys from a `collection.query` response, nearest first, each
    at its own best distance across every chunk queried."""
    best: dict[str, float] = {}
    for metadatas, distances in zip(raw["metadatas"], raw["distances"]):
        for metadata, distance in zip(metadatas, distances):
            citekey = metadata.get("citekey")
            if citekey is not None and distance < best.get(citekey, float("inf")):
                best[citekey] = distance
    return sorted(best, key=lambda key: best[key])


def absent_citekeys(collection, citekeys) -> set[str]:
    """Which of `citekeys` own no chunk in `collection` at all.

    A metadata-only `get`, not a similarity query -- the same call
    `embed_index.py`'s own upsert uses to check what is already indexed.
    `shortlist`'s ranking cannot answer this: a citekey that ranks last
    there may simply be topically distant, still with real chunks in the
    collection, and `shortlist` has no way to tell that case apart from a
    source the enrichment layer has never embedded (#499, M-16) -- the
    corpus grew a paper since `enrich` last ran, that paper never made
    the shortlist's cap, and nothing said why. This is the presence check
    that lets a caller say why, without changing how `shortlist` ranks.
    """
    if not citekeys:
        return set()
    # Sorted, not just `list()`-ed: a caller may pass a `set`, whose
    # iteration order is not insertion order and is not stable across
    # runs, and a query built from it would make `collection.gets` and
    # any log of what was asked for order-dependent for no reason.
    hits = collection.get(where={"citekey": {"$in": sorted(citekeys)}}, include=["metadatas"])
    present = {m.get("citekey") for m in hits["metadatas"]}
    return set(citekeys) - present

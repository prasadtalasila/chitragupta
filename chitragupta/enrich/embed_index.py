"""Stage 3: sentence-transformers embeddings persisted in a Chroma collection.

The embedding retrieval chitragupta/retrieval.py deferred. build_index()
is incremental: each chunk records a hash of the *text* that produced it
(not the PDF bytes, since a re-parse can change the text), unchanged docs
skip model.encode(), and a changed doc is deleted then reinserted so a
shrunk chunk count leaves no orphans (upsert never removes).
"""

import logging
import re
from typing import Any

from chitragupta import chroma_paging, config, ledger_citable, logging_setup
from chitragupta.enrich import _index_reader, _rerank
from chitragupta.enrich.corpus import CorpusDoc
from chitragupta.enrich.embed_text import chunk_text, get_text, hash_text, strip_image_refs

__all__ = [
    "chunk_text",
    "get_text",
    "hash_text",
    "strip_image_refs",
    "collection_name",
    "get_client_and_model",
    "build_index",
    "search",
]

# Fixed name, so it stays inside the "chitragupta" logger tree
# logging_setup.configure() pins (see chitragupta/sync.py).
logger = logging.getLogger("chitragupta.enrich.embed_index")

_COLLECTION_PREFIX = "corpus"


def collection_name() -> str:
    """Chroma collection name for the currently configured embedding model.

    Public so `chitragupta/overlap_embed.py` asks rather than recomputing
    the rule. Namespaced by model because dimensions differ (384 vs 768):
    a shared collection would error after a model swap, or silently serve
    the old model's vectors for unchanged text.
    """
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", config.EMBEDDING_MODEL).strip("-.")
    return f"{_COLLECTION_PREFIX}-{slug}"[:63].rstrip("-.")


def get_client_and_model() -> tuple[Any, Any]:
    import chromadb
    from sentence_transformers import SentenceTransformer

    config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    model = SentenceTransformer(config.EMBEDDING_MODEL)
    return client, model


def _refresh_stale_title(collection, doc: CorpusDoc, existing: dict) -> None:
    """Patch a corrected title into already-upserted, unchanged chunks.

    A title-only edit doesn't need a re-encode (#503, m-48); folding the
    title into the `text_hash` check would re-embed on every bib fix.
    """
    stale_titles = [m.get("title") != doc.title for m in existing["metadatas"]]
    if any(stale_titles):
        collection.update(
            ids=existing["ids"],
            metadatas=[{**m, "title": doc.title} for m in existing["metadatas"]],
        )


def _embed_doc(doc: CorpusDoc, position: int, total: int, collection, model) -> tuple[int, str]:
    """One document's slice of build_index's loop: embed-or-skip it, upsert
    if needed, and report the outcome on the line opened for it. Returns
    (n_chunks, outcome), outcome one of "embedded"/"unchanged"/"no_text".
    """
    # Bare prints, not logging_setup.say(): the citekey is written before
    # the work and the outcome appended to the same line, which a
    # whole-line log record cannot do.
    print(f"  [{position}/{total}] {doc.citekey}", end="", flush=True)

    text = get_text(doc)
    if not text:
        print(" -- no text to embed", flush=True)
        return 0, "no_text"

    text_hash = hash_text(text)
    # Queried by citekey, which every collection carries, so an index
    # built before #57 keeps working.
    existing = collection.get(where={"citekey": doc.citekey})
    if existing["ids"] and all(m.get("text_hash") == text_hash for m in existing["metadatas"]):
        _refresh_stale_title(collection, doc, existing)
        print(f" -- unchanged, {len(existing['ids'])} chunk(s)", flush=True)
        return len(existing["ids"]), "unchanged"
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    chunks = chunk_text(text)
    if not chunks:
        # Whitespace-only text: reported the same, nothing is indexed.
        print(" -- no text to embed", flush=True)
        return 0, "no_text"

    embeddings = model.encode(chunks, show_progress_bar=False).tolist()
    ids = [f"{doc.citekey}::{i}" for i in range(len(chunks))]
    metadatas = [
        {"citekey": doc.citekey, "title": doc.title, "text_hash": text_hash} for _ in chunks
    ]
    collection.upsert(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)
    print(f" -- embedded, {len(chunks)} chunk(s)", flush=True)
    return len(chunks), "embedded"


def build_index(docs: list[CorpusDoc]) -> dict[str, int]:
    """Embeds and upserts each doc's chunks, skipping docs whose text is
    unchanged since the last call. Returns {citekey: n_chunks}.

    Reports each document as it is *reached*, not as it finishes, so a
    slow document doesn't look like a hang (#50); same
    `  [done/total] <citekey>` shape as sync, flushed because a
    non-terminal stdout is block-buffered.
    """
    client, model = get_client_and_model()
    collection = client.get_or_create_collection(collection_name())

    counts = {}
    tallies = {"embedded": 0, "unchanged": 0, "no_text": 0}
    try:
        for position, doc in enumerate(docs, start=1):
            n_chunks, outcome = _embed_doc(doc, position, len(docs), collection, model)
            counts[doc.citekey] = n_chunks
            tallies[outcome] += 1
    except KeyboardInterrupt:
        # Chunks upserted so far are persisted and skipped next run, so
        # the message says an interrupted run kept its work.
        logging_setup.say(
            logger,
            f"\n  interrupted after {len(counts)}/{len(docs)} document(s) "
            "-- what is embedded is kept; re-run to continue.",
            level=logging.WARNING,
        )
        raise

    # Prune chunks of citekeys that left the ledger (#503, M-23): upsert
    # never removes them. Only after a complete pass, and never with an
    # empty `docs`, which more likely means a wrong project/cwd than a
    # corpus gone to zero. Read in pages (chitragupta/chroma_paging.py,
    # #581): one `get` is capped by SQLite's bound-variable limit. The
    # delete stays whole: chromadb chunks it internally, and pruning
    # inside the paging loop would move unread rows.
    orphaned_ids = []
    if docs:
        current_citekeys = {doc.citekey for doc in docs}
        everything = chroma_paging.all_rows(collection, include=["metadatas"])
        orphaned_ids = [
            chunk_id
            for chunk_id, metadata in zip(everything["ids"], everything["metadatas"])
            if metadata.get("citekey") not in current_citekeys
        ]
        if orphaned_ids:
            collection.delete(ids=orphaned_ids)

    logging_setup.say(
        logger,
        f"  {len(docs)} document(s): {tallies['embedded']} embedded, "
        f"{tallies['unchanged']} unchanged, {tallies['no_text']} with no text -- "
        f"{sum(counts.values())} chunk(s) in the index"
        + (
            f", {len(orphaned_ids)} orphaned chunk(s) from departed citekeys removed"
            if orphaned_ids
            else ""
        ),
    )
    return counts


def search(query: str, k: "int | None" = None, snippet_chars: int = 500) -> list[dict]:
    """Embedding search, the same shape as `chitragupta.retrieval.search()`.

    `k` defaults to `config.EMBED_TOP_K` via `None`, so a test or env var
    can change it. Every hit is citable: both searches draw on the ledger,
    and rows whose PDF is missing or unparsed are dropped (#1118).

    At most `config.EMBED_MAX_PASSAGES_PER_SOURCE` results per citekey
    (#305), applied to the over-fetched list *before* truncating to k, so
    a dominant paper's excess promotes another paper's chunk. With
    `[enrich].rerank` on, the cross-encoder reorders **before** that cap,
    never after (#380): only then can reranking change which document
    survives (orders disagree on 217 of 256 queries, `bench/RESULTS.md`
    2026-08-26; pinned by tests/test_enrich_embed_index.py). Off by
    default: 2.5x a search on GPU, 5.75x on CPU (docs/CORPUS-SEARCH.md).
    """
    opened = _index_reader.open_for_search()
    if opened is None:
        return []
    collection, model = opened
    k = config.EMBED_TOP_K if k is None else k
    query_embedding = model.encode([query], show_progress_bar=False).tolist()
    raw = collection.query(
        query_embeddings=query_embedding, n_results=k * config.EMBED_OVERFETCH_MULTIPLIER
    )

    # Built for the whole over-fetched pool, which the reranker scores.
    # The reranker therefore judges the *truncated* snippet, so
    # `snippet_chars` narrows its evidence too; deliberate, so the
    # returned text is what was ranked (bench/bench_rerank_position.py).
    hits = [
        {**metadata, "snippet": doc_text[:snippet_chars], "distance": distance}
        for doc_text, metadata, distance in zip(
            raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
        )
    ]
    # Unparsed rows' chunks outlive a status change (#1118); dropped
    # before the reranker spends anything on them.
    unparsed = ledger_citable.unparsed_on_this_host()
    hits = [hit for hit in hits if hit["citekey"] not in unparsed]
    if config.RERANK:
        hits = _rerank.rerank(query, hits)

    results = []
    per_source = {}
    for hit in hits:
        citekey = hit["citekey"]
        if per_source.get(citekey, 0) >= config.EMBED_MAX_PASSAGES_PER_SOURCE:
            continue
        per_source[citekey] = per_source.get(citekey, 0) + 1
        results.append(hit)
        if len(results) == k:
            break
    return results

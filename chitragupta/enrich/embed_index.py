"""Stage 3: sentence-transformers embeddings persisted in a Chroma collection.

This is the real embedding-based retrieval the corpus layer's
chitragupta/retrieval.py deliberately deferred (keyword overlap only, pending a
larger corpus). Needs `sentence-transformers` and `chromadb` from
pyproject.toml's "enrich" Poetry group, in a venv.

build_index() is incremental, mirroring the corpus layer's
chitragupta/ledger.py: skip reprocessing whatever hasn't detectably changed
since the last run. Here that means each chunk's stored
metadata carries a hash of the *text that produced it* (not the PDF
bytes -- Docling reprocessing the same PDF, or a manually edited parsed
.txt, can change the embedded text without the PDF itself changing), and
a doc whose current text hashes the same as what's already indexed skips
model.encode() entirely. Only genuinely new/changed docs pay the encode
cost. This also fixes a latent bug: previously, a doc whose chunk count
*shrank* between runs left its old, now-orphaned trailing chunks in
Chroma forever (upsert only ever adds/overwrites, never removes) -- an
unchanged-vs-changed check that deletes-then-reinserts on a real change
closes that gap too.
"""

import logging
import re
from typing import Any

from chitragupta import config, logging_setup
from chitragupta.enrich import _rerank
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

# Fixed name for the same reason chitragupta/sync.py pins its own: this
# module is imported, never run as __main__, but naming it here
# rather than via __name__ keeps it obvious that it must stay inside
# the "chitragupta" tree logging_setup.configure() pins to DEBUG.
logger = logging.getLogger("chitragupta.enrich.embed_index")

_COLLECTION_PREFIX = "corpus"


def collection_name() -> str:
    """Chroma collection name for the currently configured embedding model.

    Public rather than private because `chitragupta/overlap_embed.py` (tier 3 of
    the overlap scan) has to ask whether *this* model's collection has
    been built before it can say the tier is available -- and asking that
    by recomputing the name would put the namespacing rule below in two
    places, which is the one way the two could start disagreeing about
    which collection is the current one.

    Different models produce different-dimensioned vectors (e.g.
    MiniLM-L6-v2's 384 vs mpnet-base-v2's 768). A single shared collection
    would either raise a dimension-mismatch error from Chroma on the first
    upsert after a model swap, or -- since the skip logic below only keys
    off the text hash -- silently keep serving stale vectors from the old
    model for any doc whose text hasn't changed. Namespacing the collection
    by model sidesteps both: switching `embedding_model` in config.toml
    starts a fresh, empty collection instead of corrupting or stale-skipping
    the old one.
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

    Split out of `_embed_doc` to keep that function under the statement
    limit, not for reuse -- `existing` is a `get(where={"citekey": ...})`
    result computed by the caller, not something worth recomputing here.
    A title-only edit doesn't need `model.encode()` to run again (#503,
    m-48): the staleness check that reaches this function already
    compared `text_hash`, so folding the title into that comparison
    would re-embed on every bib correction for no reason.
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
    # Bare prints for this whole per-document block, not logging_setup.say():
    # the citekey is written *before* the work and the outcome is appended
    # to the same line after it, so "which document is it on right now" is
    # visible while a slow embed is still running. A log record is a whole
    # line by construction, so routing this through the logger would split
    # each document across records and withhold the citekey until its work
    # had already finished -- losing the one thing this line is for.
    print(f"  [{position}/{total}] {doc.citekey}", end="", flush=True)

    text = get_text(doc)
    if not text:
        print(" -- no text to embed", flush=True)
        return 0, "no_text"

    text_hash = hash_text(text)
    # Queried by citekey, which every collection this code has ever written
    # carries -- the retired `doc_id` key held the same value alongside it --
    # so an index built before #57 keeps working without a rebuild.
    existing = collection.get(where={"citekey": doc.citekey})
    if existing["ids"] and all(m.get("text_hash") == text_hash for m in existing["metadatas"]):
        _refresh_stale_title(collection, doc, existing)
        print(f" -- unchanged, {len(existing['ids'])} chunk(s)", flush=True)
        return len(existing["ids"]), "unchanged"
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    chunks = chunk_text(text)
    if not chunks:
        # Whitespace-only text lands here rather than above. Reported the
        # same way because it amounts to the same thing for a reader:
        # nothing of this document is in the index, and no amount of
        # waiting will change that.
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

    Reports each document as it is *reached*, not as it finishes -- see
    _embed_doc, which opens the line before `model.encode()` and closes it
    with whatever the document turned out to be. A stage that prints only
    on completion still leaves the slowest document in the corpus looking
    like a hang for as long as it takes -- and a stage that printed
    nothing at all until it returned is how issue #50 came to be filed
    against a run that was working fine, then Ctrl-C'd at 399 of 501
    documents.

    Same `  [done/total] <citekey>` shape chitragupta/sync.py and
    docling_parse.py already use for their own per-document progress, and
    flushed for the reason pdf_text.py flushes its interrupt notice:
    stdout is block-buffered when it isn't a terminal, and the tail of an
    interrupted run is exactly the part worth keeping.
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
        # Chroma has already persisted every chunk upserted so far, and
        # the next run's text-hash check skips those documents -- so an
        # interrupted run is worth something and the message says so,
        # rather than leaving the reader to guess (the same promise
        # docling_parse.py makes when its own pool is interrupted).
        logging_setup.say(
            logger,
            f"\n  interrupted after {len(counts)}/{len(docs)} document(s) "
            "-- what is embedded is kept; re-run to continue.",
            level=logging.WARNING,
        )
        raise

    # A citekey dropped from the bib (and, after re-export + sync, the
    # ledger) leaves its chunks in Chroma forever otherwise -- upsert only
    # ever adds/overwrites, never removes what a *departed* document wrote
    # (#503, M-23). This is the one place able to tell "departed" from
    # "merely unchanged": `docs` is build_corpus()'s whole current ledger,
    # so any chunk whose citekey isn't in it belongs to no document this
    # run was asked to index. Runs after the loop completes, not inside
    # it, so an interrupted run (which `raise`s above) never deletes
    # chunks on the strength of a partial pass.
    current_citekeys = {doc.citekey for doc in docs}
    everything = collection.get()
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
    """`k` defaults to `config.EMBED_TOP_K` rather than to a literal, so
    the three numbers that size this function -- how deep it fetches,
    how many chunks one citekey may own, and how many it returns -- are
    one set of settings in `config.toml` instead of one key and two
    constants. `None` rather than the value itself in the signature:
    a module-level default would be bound at import and could not be
    monkeypatched by a test or changed by an env var for one run.

    `snippet_chars` defaults to enough context for a caller to judge
    relevance itself before citing, rather than trusting distance alone.

    Deliberately the same shape as `chitragupta.retrieval.search()`, so this is a
    drop-in for it, and every hit is citable either way: both draw on the
    ledger, so a returned `citekey` always resolves against it. That is
    what restricting the corpus to the bibliography buys (see corpus.py)
    -- there is no longer any such thing as a hit a draft may not cite.

    The two do not cover quite the same *documents*, though, and a caller
    choosing between them should know which way it cuts. BM25 indexes
    each item's title whether or not it has parsed text, so a
    metadata-only entry is still findable there; `build_index` skips any
    document `get_text` returns nothing for, because there is nothing to
    embed. A bib entry whose PDF is missing or failed to parse is
    therefore searchable by title and not by meaning.

    At most `config.EMBED_MAX_PASSAGES_PER_SOURCE` of the k results come
    from any one citekey (issue #305), out of a pool of
    `k * config.EMBED_OVERFETCH_MULTIPLIER` -- unlike BM25's `search`, which is
    one-per-citekey by construction, Chroma ranks by chunk and a single
    well-matched paper can otherwise fill every slot. The cap is applied
    to the over-fetched, distance-ranked list *before* truncating to k:
    dropping a dominant paper's excess chunks promotes another paper's
    chunk into the window, where capping an already-truncated top-k
    would only shorten it. Keyed on `citekey`, not title, so two
    untitled or same-titled documents are still capped apart.

    When `[enrich].rerank` is on, a cross-encoder reorders the
    over-fetched list **before** that cap, never after (#380). The two
    rules are really one rule, which is why they are documented
    together: the cap exists so that dropping a dominant paper's excess
    chunks *promotes another paper's chunk into the window*, and a
    rerank placed after the cap can only permute chunks the bi-encoder
    already chose. Reranking first is what lets a promotion change
    **which document** survives, and `tests/test_enrich_embed_index.py`
    pins exactly that so a later refactor cannot quietly swap the order
    back -- the two orders disagree about which papers come back on 217
    of 256 real queries (`bench/RESULTS.md`, 2026-08-26).

    Off by default. It costs 2.5x a search call on a GPU and 5.75x on a
    CPU, and buys ordering rather than recall -- see
    `docs/CORPUS-SEARCH.md` before turning it on.
    """
    client, model = get_client_and_model()
    collection = client.get_or_create_collection(collection_name())
    k = config.EMBED_TOP_K if k is None else k
    query_embedding = model.encode([query], show_progress_bar=False).tolist()
    raw = collection.query(
        query_embeddings=query_embedding, n_results=k * config.EMBED_OVERFETCH_MULTIPLIER
    )

    # Built for the whole over-fetched pool, not just the kept slice,
    # because the reranker below scores the pool. Costs 20 dict merges
    # and 20 string slices against a ~12ms search call.
    #
    # Note what that makes `snippet_chars` when reranking is on: the
    # cross-encoder scores this *truncated* snippet, not the whole
    # chunk, so a small `snippet_chars` narrows what the reranker may
    # judge on as well as what the caller sees. Deliberate -- it is the
    # shape bench/bench_rerank_position.py measured, and scoring the
    # full chunk while returning a shorter one would leave the returned
    # text no longer the evidence the ranking was based on -- but it is
    # a coupling worth knowing before tuning either number.
    hits = [
        {**metadata, "snippet": doc_text[:snippet_chars], "distance": distance}
        for doc_text, metadata, distance in zip(
            raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
        )
    ]
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

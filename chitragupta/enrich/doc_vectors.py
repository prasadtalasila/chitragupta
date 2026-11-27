"""How a document becomes one vector, and the cache that keeps it.

topic_model.py clusters these vectors and topic_seeding.py scores seed
phrases against them; they must be the same vectors, or a seed report's
similarity would not explain the topic assignment beside it.
"""

import json
import os
import re

from chitragupta import config
from chitragupta.enrich import embed_index
from chitragupta.enrich.corpus import CorpusDoc


def _is_embed_entry(entry) -> bool:
    """What `document_embeddings` reads off an entry without a `.get`: a
    text hash to compare and a vector to return."""
    return (
        isinstance(entry, dict)
        and isinstance(entry.get("hash"), str)
        and isinstance(entry.get("embedding"), list)
    )


def _load_embed_cache() -> dict:
    """Load the cache; corrupt or unexpected-shape data reads as empty
    (#504, M-24), costing one re-embed rather than failing every topic
    stage. A malformed entry is dropped alone, as a miss (#979)."""
    try:
        data = json.loads(config.TOPIC_EMBED_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {citekey: entry for citekey, entry in data.items() if _is_embed_entry(entry)}


def _save_embed_cache(cache: dict) -> None:
    """Atomic write-then-replace, so a killed write leaves the previous
    cache rather than a torn file."""
    config.TOPIC_EMBED_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = config.TOPIC_EMBED_CACHE_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(cache), encoding="utf-8")
    os.replace(tmp_path, config.TOPIC_EMBED_CACHE_PATH)


def corpus_texts(docs: list[CorpusDoc]) -> dict:
    """Every doc that has text at all, by citekey. Empty docs are dropped,
    or they would cluster on their emptiness into an invented topic."""
    doc_texts = {}
    for doc in docs:
        text = embed_index.get_text(doc)
        if text:
            doc_texts[doc.citekey] = text
    return doc_texts


# Headings that mean "the paper is over", matched at the *last*
# occurrence: related work may say "References", and appendices follow.
BACK_MATTER = re.compile(r"(?im)^\s*#{1,6}\s*\**\s*(references|bibliography|works cited)\b")

# Lines with no topical content: contact details, retrieval boilerplate,
# bare page numbers and running heads.
NOISE_LINE = re.compile(
    r"(?im)^\s*(?:"
    r"\S+@\S+\.\S+"  # an email address on its own
    r"|(?:https?://|www\.|doi:|10\.\d{4}/)\S*"  # a bare URL or DOI
    r"|(?:downloaded from|licensed under|all rights reserved|"
    r"copyright|\(c\)\s*\d{4}|©).*"
    r"|\d{1,4}"  # a bare page number
    r")\s*$"
)


def content_text(text: str) -> str:
    """A document with its back matter and boilerplate removed.

    Removes only what is provably not about the paper and keeps every
    technical token (no stop-words, lowercasing or frequency filtering),
    which domain-specific topic modelling guidance warns would destroy
    multiword domain terms. The reference list must go: it made papers
    similar for citing the same work (one topic was an author cluster),
    and is a median 15% of a document. With no detectable heading (9%),
    the whole text is kept rather than guessing a boundary.
    """
    match = None
    for match in BACK_MATTER.finditer(text):
        pass  # the last one wins -- see BACK_MATTER
    if match is not None:
        text = text[: match.start()]
    return "\n".join(line for line in text.splitlines() if not NOISE_LINE.match(line))


# Bumped when the document-to-vector arithmetic changes: the text hash and
# model id don't notice such a change, so old vectors would be served.
EMBED_METHOD = "chunk-mean-content-v2"


def pooled_embedding(text: str, model) -> list[float] | None:
    """One vector for a whole document: the mean of its chunk vectors.

    **Not `model.encode(text)`**: it truncates at 512 word pieces, about
    2% of a paper here, so topics formed from front matter. A prefix is
    the wrong 2% for long documents, whose salient content is scattered
    (Koh et al., ACM Computing Surveys 55:8, 2022, Finding 4). Chunked
    with `embed_index.chunk_text`, so the split matches the Chroma index;
    unweighted mean, since chunks are near-uniform in length.
    """
    import numpy as np

    chunks = embed_index.chunk_text(content_text(text))
    if not chunks:
        return None
    return np.asarray(model.encode(chunks, show_progress_bar=False)).mean(axis=0).tolist()


def document_embeddings(doc_texts: dict, model) -> dict:
    """One whole-document vector per citekey, re-encoding only what changed.

    Shared with topic_seeding.py so seed scores and clusters use the same
    vectors. See `pooled_embedding` for what the vector means.
    """
    cache = _load_embed_cache()
    doc_hashes = {citekey: embed_index.hash_text(text) for citekey, text in doc_texts.items()}
    # Cached per model and EMBED_METHOD as well as text hash: a model swap
    # changes dimensionality, and mixed dimensions break BERTopic outright.
    stale_citekeys = [
        citekey
        for citekey in doc_texts
        if citekey not in cache
        or cache[citekey]["hash"] != doc_hashes[citekey]
        or cache[citekey].get("model") != config.EMBEDDING_MODEL
        or cache[citekey].get("method") != EMBED_METHOD
    ]
    for citekey in stale_citekeys:
        vector = pooled_embedding(doc_texts[citekey], model)
        if vector is None:
            continue
        cache[citekey] = {
            "hash": doc_hashes[citekey],
            "model": config.EMBEDDING_MODEL,
            "method": EMBED_METHOD,
            "embedding": vector,
        }
    if stale_citekeys:
        _save_embed_cache(cache)
    # No vector for a document that chunked to nothing: a zero row would
    # cluster with every empty document into an invented topic.
    return {citekey: cache[citekey]["embedding"] for citekey in doc_texts if citekey in cache}

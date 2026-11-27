"""Stage 4: BERTopic clustering over the corpus.

On a handful of documents HDBSCAN legitimately puts everything in the
outlier topic (-1): report that honestly rather than lowering
`[enrich].topic_min_cluster_size` to force clusters. Granularity is
configurable (docs/CONFIG.md has the sweep).

No genre skill consumes config.TOPICS_PATH (see DEVELOPER.md's
"`content/topics.json` has no consumer"), so don't assume a caller
depends on its shape. Clustering is whole-corpus and topic ids are not
stable between runs; only the embeddings are cached, via
`doc_vectors.document_embeddings()`. Those re-encode the same chunks
`content/chroma/` already holds: a known cost, not an oversight, since
pooling from Chroma would make this stage depend on `embed` having run.
"""

import json
from typing import Any

from chitragupta import config
from chitragupta.enrich import doc_vectors, embed_index, topic_labels
from chitragupta.enrich.corpus import CorpusDoc


def _unit(matrix) -> Any:
    """Rows scaled to unit length, so a dot product is a cosine. A zero
    row is left alone, matching nothing (no membership)."""
    import numpy as np

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms > 0)


# Recorded beside the memberships; bumped when the weight arithmetic
# changes (HDBSCAN soft clustering was v1).
MEMBERSHIP_MECHANISM = "centroid-cosine-centred-v2"


def topic_descriptors(embeddings, topics: list) -> tuple[list[int], Any, Any]:
    """One vector per emergent topic: its members' centroid, in
    mean-centred embedding space.

    **Centring is load-bearing**: in a one-subject corpus raw cosines bunch
    together (mean top-share 0.20 against 0.60 centred, over 76 topics).
    Returns `(ids, matrix)`. The outlier topic has no descriptor: -1 means
    "no topic", and would drag centroids back to the mean.
    """
    import numpy as np

    assigned = np.asarray([int(t) for t in topics])
    ids = sorted(set(assigned.tolist()) - {-1})
    centred = np.asarray(embeddings, dtype=float)
    centred = centred - centred.mean(axis=0)
    descriptors = np.array([centred[assigned == topic_id].mean(axis=0) for topic_id in ids])
    return ids, centred, descriptors


def topic_memberships(embeddings, citekeys: list, topics: list) -> "dict | None":
    """Every emergent topic each document is *about*, with its strength.

    `assignments` is **which cluster a document was put in** (density);
    `memberships` is **what the paper is about** (similarity to each
    descriptor). They can differ, but the assigned topic is **always
    present** in memberships so the file never contradicts itself.
    Descriptors replace HDBSCAN soft clustering, which reported a corpus
    known to be plural as nearly singular (1.64 topics per document
    against 5.03). Returns None when the feature is off or every document
    is an outlier.
    """
    if not config.TOPIC_DISTRIBUTION:
        return None
    ids, centred, descriptors = topic_descriptors(embeddings, topics)
    if not ids:
        return None

    similarity = _unit(centred) @ _unit(descriptors).T
    index = {topic_id: column for column, topic_id in enumerate(ids)}
    memberships = {}
    for citekey, assigned, row in zip(citekeys, (int(t) for t in topics), similarity):
        ranked = sorted(
            (
                (str(ids[column]), round(float(weight), 6))
                for column, weight in enumerate(row)
                if weight > 0.0
            ),
            key=lambda item: (-item[1], item[0]),
        )
        best = ranked[0][1] if ranked else 0.0
        kept = [pair for pair in ranked if pair[1] >= best * config.TOPIC_MEMBERSHIP_RATIO]
        kept = dict(kept[: config.TOPIC_MEMBERSHIP_MAX])
        # The assigned topic is a membership by construction (see above).
        if assigned != -1:
            kept.setdefault(str(assigned), round(float(row[index[assigned]]), 6))
        if kept:
            memberships[citekey] = dict(sorted(kept.items(), key=lambda kv: -kv[1]))
    return memberships


def _fit(texts: list, embeddings, model) -> tuple[Any, list[int]]:
    """Configure UMAP/HDBSCAN/BERTopic for a corpus of this size and fit."""
    from bertopic import BERTopic
    from hdbscan import HDBSCAN
    from umap import UMAP

    # UMAP's spectral initialization raises outright unless n_neighbors <
    # n_samples and n_components + 1 < n_samples. These clamps only ever
    # reduce config's granularity, for small-corpus correctness; a tiny
    # corpus still honestly reports mostly outliers. A hardcoded ceiling
    # that also clamped large corpora was the bug they replaced.
    n_docs = len(texts)
    umap_model = UMAP(
        n_neighbors=min(config.TOPIC_NEIGHBORS, n_docs - 1),
        n_components=min(5, max(2, n_docs - 2)),
        min_dist=0.0,
        metric="cosine",
        random_state=42,
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=max(2, min(config.TOPIC_MIN_CLUSTER_SIZE, n_docs // 2)),
        min_samples=max(1, min(config.TOPIC_MIN_SAMPLES, n_docs - 1)),
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=True,
    )

    # vectorizer_model decides only what a topic is *called*: defaults gave
    # function-word and author-name labels (see topic_labels.py).
    topic_model = BERTopic(
        embedding_model=model,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=topic_labels.vectorizer(),
        calculate_probabilities=False,
        verbose=False,
    )
    return topic_model, topic_model.fit_transform(texts, embeddings)[0]


def run_topic_model(docs: list[CorpusDoc]) -> dict:
    """Cluster the corpus into emergent topics.

    **Unseeded, always, and that is what lets a seed list be unlimited.**
    Steering with `zeroshot_topic_list` absorbed documents HDBSCAN never
    saw (nine seeds took 81 topics to 53), and enough seeds crash the fit
    inside sklearn. Seeds are matched separately by topic_seeding.py
    against the same vectors. Unseeded also keeps a real clusterer for
    `topic_memberships`.
    """
    import numpy as np

    doc_texts = doc_vectors.corpus_texts(docs)

    if len(doc_texts) < 2:
        raise ValueError(
            f"Need at least 2 documents with text to run BERTopic; got {len(doc_texts)}"
        )

    _client, model = embed_index.get_client_and_model()  # reuse the same embedding model

    cache = doc_vectors.document_embeddings(doc_texts, model)

    # Keyed off what has a vector: a document that chunked to nothing is
    # absent from the cache.
    citekeys = [citekey for citekey in doc_texts if citekey in cache]
    if len(citekeys) < 2:
        raise ValueError(
            f"Need at least 2 documents with embeddable text to run BERTopic; got {len(citekeys)}"
        )
    texts = [doc_texts[d] for d in citekeys]
    embeddings = np.array([cache[d] for d in citekeys])

    topic_model, topics = _fit(texts, embeddings, model)

    result = {
        "n_docs": len(texts),
        "assignments": dict(zip(citekeys, [int(t) for t in topics])),
        "topic_info": json.loads(topic_model.get_topic_info().to_json(orient="records")),
        # Recorded so `topic_converge.py` can refuse vectors re-embedded
        # under a different model or pooling method (#504, m-47).
        "embedding_model": config.EMBEDDING_MODEL,
        "embedding_method": doc_vectors.EMBED_METHOD,
    }
    memberships = topic_memberships(embeddings, citekeys, topics)
    if memberships is not None:
        result["memberships"] = memberships
        result["membership_mechanism"] = MEMBERSHIP_MECHANISM
    config.TOPICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.TOPICS_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result

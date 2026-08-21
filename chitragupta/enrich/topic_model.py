"""Stage 4: BERTopic clustering over the corpus.

Needs `bertopic` from pyproject.toml's "enrich" Poetry group, in a venv.
With a handful of documents HDBSCAN will legitimately put everything in
the outlier topic (-1) -- that is the correct output for a small corpus,
not a bug. Don't lower `[enrich].topic_min_cluster_size` to force
clusters into existence on a corpus too small for them; report the
outlier result honestly instead.

Granularity on a corpus that *is* large enough is a setting rather than a
constant (`topic_min_cluster_size`, `topic_min_samples`,
`topic_neighbors`). Until 6.9.0 it was neither: every parameter saturated
at n_docs >= 20, so a 497-document corpus received the values written for
a 20-document one and could not yield more than ~13 topics however far it
grew. docs/CONFIG.md has the sweep.

Unlike every other stage, this one has no downstream consumer in the
repository: nothing imports it, and no genre skill reads
config.TOPICS_PATH. `survey-writer` groups its themes by judgement over
the evidence it retrieved and says so ("With a small corpus there's no
BERTopic step"). The output is written for a human deciding what a survey
should cover. Wiring it in is a real option -- DEVELOPER.md's
"`content/topics.json` has no consumer" records what that would take and
why it hasn't been done -- but until then, don't assume a caller
somewhere depends on this file's shape.

It is also the one stage that can't be incremental, which is the reason
that matters here: clustering is whole-corpus, so one added document can
move every assignment, and topic ids are not stable between runs.

BERTopic's clustering step is inherently whole-corpus -- adding one new
document can shift every cluster assignment, so unlike
embed_index.build_index() there's no "skip this doc" option for the
clustering itself. What *is* skippable is the expensive part before it:
embedding the documents. This module caches one pooled vector per citekey
(config.TOPIC_EMBED_CACHE_PATH) keyed by text hash, embedding model *and*
pooling method, and re-embeds only what those say is stale.

That cache overlaps embed_index.py's Chroma collection more than it used
to, and the overlap is worth stating plainly rather than leaving for
someone to rediscover: since pooling arrived, both split a document with
the *same* embed_index.chunk_text() call and embed the same chunks with
the same model, so `content/chroma/` already holds every vector this
stage recomputes -- 40,741 of them for a 497-document corpus. Pooling
those instead of re-encoding would make this stage nearly free, at the
cost of making it depend on the `embed` stage having run and on a
fallback for documents Chroma lacks. That trade has not been made; the
duplicated encode is a known cost, not an oversight.
"""

import json

from chitragupta import config
from chitragupta.enrich import doc_vectors, embed_index
from chitragupta.enrich.corpus import CorpusDoc


def _soft_membership(clusterer):
    """HDBSCAN's own per-point membership strength across every cluster.

    Its own, and not a centroid distance of ours, because HDBSCAN is
    density-based: a cluster may be elongated, curved or hollow, and its
    centroid need not lie inside it. Measured on 497 real documents, a
    centroid rule agreed with HDBSCAN's own assignment for only 30-45% of
    them however the space was chosen -- a model mismatch no threshold
    fixes. This function's own numbers agree 99%.

    A seam of its own so tests can supply a matrix without a fitted
    clusterer; it is one call and holds no logic.
    """
    import hdbscan
    import numpy as np

    return np.atleast_2d(np.asarray(hdbscan.all_points_membership_vectors(clusterer)))


def topic_memberships(clusterer, citekeys: list, topics: list) -> "dict | None":
    """Every emergent topic each document belongs to, with its strength --
    or None when the question cannot be answered.

    `assignments` beside this holds what `fit_transform` returns: one
    topic id per document, which cannot express a paper genuinely about
    two things. Measured on this project's own corpus, 140 of 497
    documents belong to more than one topic and the scalar discards every
    one of those memberships.

    Three mechanisms were measured before this one, and each failed for a
    reason rather than for want of tuning:

    - BERTopic's `approximate_distribution` scores c-TF-IDF over token
      windows. On a single-domain corpus that separates almost nothing:
      every document belonged to all 7 topics at a mean top-share of 0.16
      against a uniform 0.14.
    - Cosine to cluster centroids, in the embedding space or the reduced
      one, centred or raw. Agreed with HDBSCAN's own assignment for 30-45%
      of documents -- see `_soft_membership` for why that is structural.
    - A Gaussian mixture over the reduced space returned near-certain
      single assignments: hard clustering with extra steps.

    HDBSCAN's cluster ids are **not** BERTopic's topic ids: BERTopic
    renumbers topics by size, so cluster 0 was topic 6 on the run this was
    written against. The mapping is recovered from the documents
    themselves rather than assumed, since every document carries both.
    """
    if not config.TOPIC_DISTRIBUTION:
        return None
    # A seeded run's placeholder, which has no clusters to be soft about.
    if not hasattr(clusterer, "labels_"):
        return None

    labels = [int(label) for label in clusterer.labels_]
    columns = sorted(set(labels) - {-1})
    if not columns:
        return None
    renumbered = {label: int(topic) for label, topic in zip(labels, topics)}

    soft = _soft_membership(clusterer)
    memberships = {}
    for citekey, label, row in zip(citekeys, labels, soft):
        ranked = sorted(((str(renumbered[column]), round(float(weight), 6))
                         for column, weight in zip(columns, row) if weight > 0.0),
                        key=lambda item: (-item[1], item[0]))
        if not ranked:
            continue
        best = ranked[0][1]
        kept = [pair for pair in ranked
                if pair[1] >= best * config.TOPIC_MEMBERSHIP_RATIO]
        memberships[citekey] = dict(kept[:config.TOPIC_MEMBERSHIP_MAX])
    return memberships


def _fit(texts: list, embeddings, model):
    """Configure UMAP/HDBSCAN/BERTopic for a corpus of this size and fit.

    Split out of run_topic_model() to keep it under
    docs/CODE-STANDARDS.md's 25-statement limit once the membership pass
    arrived, and the seam is a real one rather than an arithmetic
    convenience: everything here is *how* to cluster, everything left
    there is what to cluster and what to record.
    """
    from bertopic import BERTopic
    from hdbscan import HDBSCAN
    from umap import UMAP

    # UMAP's spectral initialization needs n_neighbors < n_samples or it
    # raises outright (not just a bad clustering) -- BERTopic's own
    # defaults (n_neighbors=15) assume a corpus far larger than this
    # project's current few documents. Scaling down is a correctness fix
    # for small N, not an attempt to manufacture nicer-looking clusters:
    # HDBSCAN's min_cluster_size is left low but not forced to 2, so a
    # tiny corpus still honestly reports as mostly/all outliers.
    # Spectral initialization needs n_components + 1 < n_samples (it solves
    # for n_components+1 eigenvectors of an n_samples x n_samples graph),
    # a tighter constraint than n_neighbors < n_samples alone.
    # config supplies the desired granularity; these clamps only ever
    # reduce it, and exist for the small-corpus correctness reason the
    # comment above gives. The bug they replaced was a hardcoded ceiling
    # that also clamped a large corpus -- min(15, ...) and min(10, ...)
    # never rose above 15 and 10 however many documents there were.
    n_docs = len(texts)
    umap_model = UMAP(
        n_neighbors=min(config.TOPIC_NEIGHBORS, n_docs - 1),
        n_components=min(5, max(2, n_docs - 2)),
        min_dist=0.0, metric="cosine", random_state=42,
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=max(2, min(config.TOPIC_MIN_CLUSTER_SIZE, n_docs // 2)),
        min_samples=max(1, min(config.TOPIC_MIN_SAMPLES, n_docs - 1)),
        metric="euclidean", cluster_selection_method="eom", prediction_data=True,
    )

    topic_model = BERTopic(
        embedding_model=model, umap_model=umap_model, hdbscan_model=hdbscan_model,
        calculate_probabilities=False, verbose=False,
    )
    return topic_model, topic_model.fit_transform(texts, embeddings)[0]


def run_topic_model(docs: list[CorpusDoc]) -> dict:
    """Cluster the corpus into emergent topics.

    **Unseeded, always, and that is what lets a seed list be unlimited.**
    BERTopic's `zeroshot_topic_list` used to steer this, and steering cost
    discovery: every document a seed absorbed was one HDBSCAN never saw.
    Measured on this corpus, nine seed phrases took the emergent topic
    count from 81 to 53 -- twenty-eight topics traded away for nine the
    author already knew about. Pushed further it does not merely trade,
    it breaks: enough seeds leave HDBSCAN fewer points than its own
    `min_samples` needs and the fit dies inside sklearn.

    Seeds are therefore matched separately, against these same document
    vectors, by chitragupta/enrich/topic_seeding.py. An author can now
    name a hundred topics and still get every emergent one, because the
    two answers are computed independently and joined afterwards rather
    than competing for the same documents.

    Keeping the clustering unseeded has a second effect worth naming:
    BERTopic only swaps its clusterer for a placeholder in zero-shot mode,
    so `topic_memberships` below now always has a real one to ask, and
    memberships are recorded for every run rather than only unseeded ones.
    """
    import numpy as np

    doc_texts = doc_vectors.corpus_texts(docs)

    if len(doc_texts) < 2:
        raise ValueError("Need at least 2 documents with text to run BERTopic; "
                         f"got {len(doc_texts)}")

    _client, model = embed_index.get_client_and_model()  # reuse the same embedding model

    cache = doc_vectors.document_embeddings(doc_texts, model)

    # Keyed off what actually has a vector, not off doc_texts: a document
    # whose text chunked to nothing is absent from the cache, and reading
    # doc_texts here would raise on it.
    citekeys = [citekey for citekey in doc_texts if citekey in cache]
    if len(citekeys) < 2:
        raise ValueError("Need at least 2 documents with embeddable text to run "
                         f"BERTopic; got {len(citekeys)}")
    texts = [doc_texts[d] for d in citekeys]
    embeddings = np.array([cache[d] for d in citekeys])

    topic_model, topics = _fit(texts, embeddings, model)

    result = {
        "n_docs": len(texts),
        "assignments": dict(zip(citekeys, [int(t) for t in topics])),
        "topic_info": json.loads(topic_model.get_topic_info().to_json(orient="records")),
    }
    memberships = topic_memberships(topic_model.hdbscan_model, citekeys, topics)
    if memberships is not None:
        result["memberships"] = memberships
    config.TOPICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.TOPICS_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result

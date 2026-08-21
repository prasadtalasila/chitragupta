"""Stage 4: BERTopic clustering over the corpus.

Needs `bertopic` from pyproject.toml's "enrich" Poetry group, in a venv. With a
handful of documents, HDBSCAN's default min_cluster_size (10) will
legitimately put everything in the outlier topic (-1) -- that is the
correct output for a small corpus, not a bug. Don't lower
min_cluster_size to force clusters into existence; report the outlier
result honestly and let the topic model become meaningful once the
corpus is large enough to justify it.

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
re-embedding a document's full text with model.encode(). This module
caches one whole-text embedding per citekey (config.TOPIC_EMBED_CACHE_PATH,
keyed by the same hash_text() embed_index.py uses for its own per-chunk
cache) and only calls encode() for docs whose text hash changed since the
last run, batching all of them into one encode() call rather than one per
doc. Note this cache is intentionally separate from embed_index.py's
Chroma collection: that one stores per-*chunk* embeddings for retrieval,
this one stores one whole-document embedding per doc for clustering --
different granularity, not reusable as-is between the two.
"""

import json

from chitragupta import config
from chitragupta.enrich import embed_index
from chitragupta.enrich.corpus import CorpusDoc


def _load_embed_cache() -> dict:
    if config.TOPIC_EMBED_CACHE_PATH.exists():
        return json.loads(config.TOPIC_EMBED_CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_embed_cache(cache: dict) -> None:
    config.TOPIC_EMBED_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.TOPIC_EMBED_CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")


def corpus_texts(docs: list[CorpusDoc]) -> dict:
    """Every doc that has text at all, by citekey. Docs with none are
    dropped rather than embedded as empty strings, which would cluster
    together on their emptiness and invent a topic out of missing PDFs."""
    doc_texts = {}
    for doc in docs:
        text = embed_index.get_text(doc)
        if text:
            doc_texts[doc.citekey] = text
    return doc_texts


def document_embeddings(doc_texts: dict, model) -> dict:
    """One whole-text vector per citekey, re-encoding only what changed.

    Split out of run_topic_model() so chitragupta/enrich/topic_seeding.py
    can match seed phrases against the same vectors this stage clusters.
    That sharing is the point rather than a convenience: a phrase scored
    against one embedding of a document and clustered against another
    would be two different opinions about the same corpus, and the
    similarity numbers the report prints would not explain the topic
    assignments sitting beside them.

    Note what "the document's embedding" really is: `model.encode()`
    truncates at the model's own input limit (256 word pieces for
    all-MiniLM-L6-v2, 384 for the mpnet models), so this is a vector for
    a paper's opening -- title, abstract and the start of the
    introduction -- not for its whole text. That is a reasonable proxy
    for what a paper is about, and it is not the same claim as "the
    document was embedded".
    """
    cache = _load_embed_cache()
    doc_hashes = {citekey: embed_index.hash_text(text) for citekey, text in doc_texts.items()}
    # Track which model produced each cached vector, not just the text hash
    # that produced it: swapping config.toml's embedding_model changes every
    # vector's dimensionality without changing any doc's text, and mixing
    # dimensions in the same `embeddings` array below breaks BERTopic outright.
    stale_citekeys = [
        citekey for citekey in doc_texts
        if citekey not in cache
        or cache[citekey]["hash"] != doc_hashes[citekey]
        or cache[citekey].get("model") != config.EMBEDDING_MODEL
    ]
    if stale_citekeys:
        new_vecs = model.encode([doc_texts[d] for d in stale_citekeys], show_progress_bar=False)
        for citekey, vec in zip(stale_citekeys, new_vecs):
            cache[citekey] = {
                "hash": doc_hashes[citekey],
                "model": config.EMBEDDING_MODEL,
                "embedding": vec.tolist(),
            }
        _save_embed_cache(cache)
    return {citekey: cache[citekey]["embedding"] for citekey in doc_texts}


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

    **Returns None for a seeded run, and that is not a limitation to work
    around.** With `zeroshot_topic_list` set, BERTopic replaces its
    clustering model with a `BaseCluster` placeholder carrying no
    `labels_`, so there is no fitted clusterer to ask. The two modes want
    opposite things anyway: seeding is for topics the author already
    knows, and this artefact is for the ones they do not -- which is the
    question #192 asked and the reason to run the stage unseeded.

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


def _fit(texts: list, embeddings, model, seed_phrases: tuple):
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

    # None, not [], when there are no seeds: BERTopic branches on this
    # argument being falsy to decide whether to run zero-shot assignment
    # at all, so a library with no seed file takes byte-for-byte the same
    # path it took before this feature existed. That is the bar #206 set
    # -- unchanged for the common case, not merely tolerant of it.
    #
    # The two *fully* degenerate outcomes are safe on bertopic 0.17.4,
    # checked against the real library: every document clearing the
    # threshold (nothing left for HDBSCAN at all) returns every document
    # under its seed topic, and no document clearing it returns the same
    # all-outlier result an unseeded small corpus already gives.
    #
    # The dangerous case is neither of those, and a 20-document check gave
    # false confidence about it: when *nearly* every document is assigned,
    # HDBSCAN is handed a remainder smaller than the `min_samples` its
    # KDTree query needs and dies inside sklearn. min_cluster_size here is
    # sized from the whole corpus because the remainder cannot be known
    # before the zero-shot pass runs. config.ZEROSHOT_MIN_SIMILARITY is
    # what keeps the remainder large enough, and why it is a separate,
    # much higher key than the seed report's floor -- lowering it towards
    # that floor is what reintroduces this.
    zeroshot = list(seed_phrases) or None

    topic_model = BERTopic(
        embedding_model=model, umap_model=umap_model, hdbscan_model=hdbscan_model,
        calculate_probabilities=False, verbose=False,
        zeroshot_topic_list=zeroshot,
        zeroshot_min_similarity=config.ZEROSHOT_MIN_SIMILARITY,
    )
    return topic_model, topic_model.fit_transform(texts, embeddings)[0]


def run_topic_model(docs: list[CorpusDoc], seed_phrases: tuple = ()) -> dict:
    """Cluster the corpus, optionally steered by the author's own phrases.

    `seed_phrases` non-empty turns on BERTopic's zero-shot mode: each
    phrase is embedded whole and documents close enough to one are
    assigned to it by name, with the remainder clustered as before. The
    phrase reaches BERTopic as a single string, never a term list, which
    is what keeps "structural health monitoring" one topic rather than
    three -- `seed_topic_list`, the older mechanism, matches against a
    bag-of-words vocabulary and would decompose it.

    **This half assigns each document exactly one topic**, because
    `fit_transform` returns one topic id per document and always has.
    The many-to-many view -- a paper under every phrase it matched, which
    is what a corpus grouped by hand in Zotero actually looks like --
    is chitragupta/enrich/topic_seeding.py's artefact, not this one's.
    Neither replaces the other and both read the same embeddings.
    """
    import numpy as np

    doc_texts = corpus_texts(docs)

    if len(doc_texts) < 2:
        raise ValueError("Need at least 2 documents with text to run BERTopic; "
                         f"got {len(doc_texts)}")

    _client, model = embed_index.get_client_and_model()  # reuse the same embedding model

    cache = document_embeddings(doc_texts, model)

    citekeys = list(doc_texts)
    texts = [doc_texts[d] for d in citekeys]
    embeddings = np.array([cache[d] for d in citekeys])

    topic_model, topics = _fit(texts, embeddings, model, seed_phrases)

    result = {
        "n_docs": len(texts),
        "assignments": dict(zip(citekeys, [int(t) for t in topics])),
        "topic_info": json.loads(topic_model.get_topic_info().to_json(orient="records")),
    }
    memberships = topic_memberships(topic_model.hdbscan_model, citekeys, topics)
    if memberships is not None:
        result["memberships"] = memberships
    # Recorded only when there were seeds, so an unseeded run's
    # content/topics.json is byte-identical to what this stage wrote
    # before seeding existed. A reader that finds this key knows the
    # topic names it is looking at were partly chosen by a person; one
    # that does not find it is looking at the same emergent output as
    # always, rather than at an empty list it has to interpret.
    if seed_phrases:
        result["seed_phrases"] = list(seed_phrases)
    config.TOPICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.TOPICS_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result

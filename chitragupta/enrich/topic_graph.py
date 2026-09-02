"""The topic-graph stage, sixth and last in the enrich pipeline: how
the corpus's topics relate.

(Unnumbered on purpose: the older stage docstrings carry historic
numbers with a gap at 2, so "sixth" names the position in STAGE_ORDER
without extending a numbering that no longer matches the list.)

`content/topic_set.json` answers "which papers is this topic about?".
Nothing answered "which topics sit near this one?", which is the
question a reader walking the corpus actually asks next. This stage
derives that answer and writes it to `content/topic_graph.json`, so the
tier-1 reader (`corpus discover`) never computes an edge itself.

Two typed edge families, never merged into one score, because they
answer different questions and their disagreement is itself a signal:

- **Overlap edges** are set arithmetic on shared members, kept only
  when the shared count is statistically surprising (hypergeometric
  tail against the corpus size). Each edge carries both Jaccard and the
  overlap coefficient -- Jaccard punishes a small topic nested inside a
  large one, which Theme G's rank-truncated seed topics make routine --
  and names the shared citekeys, so every edge is explainable.
- **Semantic edges** are average best-match cosine between the two
  member sets, in the same mean-centred space `topic_descriptors` uses
  and for the same measured reason. Best-match rather than
  centroid-to-centroid because HDBSCAN clusters are non-convex and a
  non-convex cluster's centroid can sit outside it. Kept only between
  mutual top-k neighbours, and each edge names its closest bridging
  pair of papers.

The artefact also stores each topic's centred centroid, the corpus
mean (so a reader can move a query embedding into the same space
without the embed cache), and an agglomerative merge tree over the
centroids for a hierarchy view. Like `converge`, this stage re-runs
nothing: it reads what the earlier stages wrote, does arithmetic, and
refuses when the recorded embedding model is not the configured one.
"""

import itertools
import json

from chitragupta import config
from chitragupta.enrich import doc_vectors, embed_index


def overlap_edges(members: dict, n_docs: int, p_value: float) -> list:
    """Co-membership edges: `{a, b, jaccard, overlap_coeff, p_value,
    shared}` for every surprisingly-overlapping pair.

    Pure set arithmetic over `{label: set_of_citekeys}` so it can be
    driven with hand-picked sets; the caller decides what a member is.
    """
    from scipy.stats import hypergeom

    edges = []
    for a, b in itertools.combinations(sorted(members), 2):
        shared = members[a] & members[b]
        if not shared:
            continue
        # The tail probability of drawing at least this many of a's
        # members when |b| papers are drawn from the corpus at random:
        # small means the overlap is affinity, not arithmetic.
        p = float(hypergeom.sf(len(shared) - 1, n_docs, len(members[a]), len(members[b])))
        if p >= p_value:
            continue
        union = members[a] | members[b]
        edges.append(
            {
                "a": a,
                "b": b,
                "jaccard": len(shared) / len(union),
                "overlap_coeff": len(shared) / min(len(members[a]), len(members[b])),
                "p_value": p,
                "shared": sorted(shared),
            }
        )
    return edges


def _best_match(rows_a, rows_b) -> "tuple[float, int, int]":
    """Symmetrised average best-match cosine between two unit-row
    matrices, plus the indices of the single closest pair."""
    cosines = rows_a @ rows_b.T
    forward = cosines.max(axis=1).mean()
    backward = cosines.max(axis=0).mean()
    # divmod on the flat argmax, not np.unravel_index: identical result
    # for a 2-D array, and pylint cannot misread a stdlib divmod the way
    # it misreads unravel_index's tuple with numpy set as ignored.
    i, j = divmod(int(cosines.argmax()), cosines.shape[1])
    return float((forward + backward) / 2), int(i), int(j)


def semantic_edges(vectors: dict, neighbors: int) -> list:
    """Semantic edges: `{a, b, similarity, bridge}` between mutual
    top-k neighbours, over `{label: {citekey: vector}}`.

    The bridge is the closest citekey pair across the edge -- the two
    papers a reader should open to see why the topics sit together.
    """
    import numpy as np

    labels = sorted(vectors)
    normalised = {}
    for label in labels:
        keys = sorted(vectors[label])
        rows = np.asarray([vectors[label][k] for k in keys], dtype=float)
        # A zero row is real, not hypothetical: in a one-document corpus
        # the centred vector is exactly zero. Dividing by its norm would
        # spread NaN through every similarity and json.dumps would emit
        # them as bare NaN tokens -- invalid JSON. A zero vector instead
        # scores 0 against everything, which is the honest answer.
        norms = np.linalg.norm(rows, axis=1, keepdims=True)
        rows = rows / np.where(norms == 0.0, 1.0, norms)
        normalised[label] = (keys, rows)

    scored = {}
    for a, b in itertools.combinations(labels, 2):
        keys_a, rows_a = normalised[a]
        keys_b, rows_b = normalised[b]
        similarity, i, j = _best_match(rows_a, rows_b)
        scored[(a, b)] = (similarity, [keys_a[i], keys_b[j]])

    # Each topic's neighbours, best first; an edge survives only when
    # each end ranks the other within its top k.
    ranked = {
        label: sorted(
            (other for other in labels if other != label),
            # `this=label` binds per iteration; a bare closure over
            # `label` would be pylint's cell-var-from-loop, and although
            # each key is consumed inside its own iteration here, the
            # explicit binding costs nothing and cannot rot into the bug.
            key=lambda other, this=label: -scored[tuple(sorted((this, other)))][0],
        )[:neighbors]
        for label in labels
    }
    return [
        {"a": a, "b": b, "similarity": similarity, "bridge": bridge}
        for (a, b), (similarity, bridge) in sorted(scored.items())
        if b in ranked[a] and a in ranked[b]
    ]


def hierarchy(labels: list, centroids: list) -> list:
    """An agglomerative merge tree over topic centroids: `{id, a, b,
    distance}` records, closest merge first, later merges free to name
    an earlier merge's id.

    Not BERTopic's `hierarchical_topics()`: that needs the fitted model
    no stage persists, and covers emergent topics only -- a centroid
    exists for every topic here, seed and emergent alike.
    """
    if len(labels) < 2:
        return []
    from scipy.cluster.hierarchy import linkage

    merges = []
    names = list(labels)
    for row in linkage(centroids, method="average", metric="cosine"):
        node = f"node-{len(merges)}"
        merges.append(
            {
                "id": node,
                "a": names[int(row[0])],
                "b": names[int(row[1])],
                "distance": float(row[2]),
            }
        )
        names.append(node)
    return merges


def build(topic_set: dict, vectors: dict, p_value: float, neighbors: int) -> dict:
    """The whole artefact, from a converged topic set and document
    vectors. Centring happens here, once, so every consumer -- edges,
    centroids, the stored corpus mean -- speaks the same space.
    """
    import numpy as np

    matrix = np.asarray(list(vectors.values()), dtype=float)
    corpus_mean = matrix.mean(axis=0) if len(matrix) else np.zeros(0)
    centred = {key: (np.asarray(vec, dtype=float) - corpus_mean) for key, vec in vectors.items()}

    members = {t["label"]: {m["citekey"] for m in t["members"]} for t in topic_set["topics"]}
    member_vectors = {
        label: {key: centred[key] for key in keys if key in centred}
        for label, keys in members.items()
    }

    nodes, labels_with_vectors, centroids = [], [], []
    for topic in topic_set["topics"]:
        vecs = member_vectors[topic["label"]]
        centroid = np.asarray(list(vecs.values())).mean(axis=0).tolist() if vecs else []
        nodes.append(
            {
                "label": topic["label"],
                "provenance": topic["provenance"],
                "size": len(members[topic["label"]]),
                "centroid": centroid,
            }
        )
        if centroid:
            labels_with_vectors.append(topic["label"])
            centroids.append(centroid)

    return {
        "model": config.EMBEDDING_MODEL,
        "n_docs": topic_set["n_docs"],
        "n_topics": len(nodes),
        "p_value": p_value,
        "neighbors": neighbors,
        "corpus_mean": corpus_mean.tolist(),
        "topics": nodes,
        "edges_overlap": overlap_edges(members, topic_set["n_docs"], p_value),
        "edges_semantic": semantic_edges(
            {label: member_vectors[label] for label in member_vectors if member_vectors[label]},
            neighbors,
        ),
        "hierarchy": hierarchy(labels_with_vectors, centroids),
    }


def run_topic_graph(docs) -> dict:
    """Derive the graph and write `content/topic_graph.json`.

    Raises when `content/topic_set.json` is absent rather than
    converging on your behalf, for the same reason `converge` refuses
    to cluster: a stage that silently did the previous stage's work
    would be a different stage wearing this one's name.
    """
    if not config.TOPIC_SET_PATH.exists():
        raise ValueError(
            f"No {config.TOPIC_SET_PATH} to graph. Run the converge stage first; "
            "this stage relates the topics it produced and creates none itself."
        )
    topic_set = json.loads(config.TOPIC_SET_PATH.read_text(encoding="utf-8"))
    # The vectors below are re-embedded under *today's* config; pairing
    # them with a topic set built under another model *or pooling
    # method* would produce plausible-looking, meaningless edges -- the
    # same trap converge documents at its own check. A topic set from
    # before the method stamp existed fails this too, deliberately:
    # "re-run converge" is cheap and certain, guessing is neither.
    if (
        topic_set.get("model") != config.EMBEDDING_MODEL
        or topic_set.get("embedding_method") != doc_vectors.EMBED_METHOD
    ):
        raise ValueError(
            f"{config.TOPIC_SET_PATH} was built under a different embedding model "
            "or method than the one configured now. Re-run the converge stage "
            "before graphing."
        )
    doc_texts = doc_vectors.corpus_texts(docs)
    _client, model = embed_index.get_client_and_model()
    vectors = doc_vectors.document_embeddings(doc_texts, model)
    result = build(topic_set, vectors, config.TOPIC_GRAPH_P_VALUE, config.TOPIC_GRAPH_NEIGHBORS)
    config.TOPIC_GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.TOPIC_GRAPH_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def run_stage(docs) -> dict:
    """`run_topic_graph()` shaped as an enrichment-stage result --
    `skipped` when converge has not run, matching every other stage's
    sequencing-mistake-is-not-an-error posture."""
    if not config.TOPIC_SET_PATH.exists():
        return {
            "status": "skipped",
            "detail": {"reason": f"no {config.TOPIC_SET_PATH}; run converge first"},
        }
    result = run_topic_graph(docs)
    return {
        "status": "ok",
        "detail": {
            "n_topics": result["n_topics"],
            "overlap_edges": len(result["edges_overlap"]),
            "semantic_edges": len(result["edges_semantic"]),
        },
    }

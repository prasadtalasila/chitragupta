"""The topic-graph stage, last in STAGE_ORDER: how the corpus's topics
relate, written to `content/topic_graph.json` so `corpus discover` never
computes an edge itself.

Two typed edge families, never merged, since their disagreement is a
signal: **overlap edges** (shared members kept only when hypergeometrically
surprising, with Jaccard and the overlap coefficient, since Jaccard
punishes a small topic nested in a large one) and **semantic edges**
(average best-match cosine in `topic_descriptors`' mean-centred space,
not centroid-to-centroid since HDBSCAN clusters are non-convex; mutual
top-k only). Also stores centred centroids, the corpus mean and a merge
tree. Re-runs nothing, and refuses a mismatched embedding model.
"""

import itertools
import json

from chitragupta import config
from chitragupta.enrich import doc_vectors, embed_index
from chitragupta.enrich.topic_brokerage import brokerage
from chitragupta.enrich.topic_mcl import communities
from chitragupta.enrich.topic_paths import next_hop_matrices


def _overlap_scan(members: dict, n_docs: int, p_value: float) -> "tuple[list, list]":
    """One pass over every sharing pair, split by the gate: the drawn
    edges, and the withheld rows `{a, b, shared, p_value}` (§7.7's
    `edges_withheld`). Withheld rows carry no strength numbers, which
    would invite reading a non-edge as an edge.
    """
    from scipy.stats import hypergeom

    edges: list = []
    withheld: list = []
    for a, b in itertools.combinations(sorted(members), 2):
        shared = members[a] & members[b]
        if not shared:
            continue
        # Small tail probability means affinity, not arithmetic.
        p = float(hypergeom.sf(len(shared) - 1, n_docs, len(members[a]), len(members[b])))
        if p >= p_value:
            withheld.append({"a": a, "b": b, "shared": sorted(shared), "p_value": p})
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
    return edges, withheld


def overlap_edges(members: dict, n_docs: int, p_value: float) -> list:
    """Co-membership edges: `{a, b, jaccard, overlap_coeff, p_value,
    shared}` for every surprisingly-overlapping pair."""
    return _overlap_scan(members, n_docs, p_value)[0]


def withheld_edges(members: dict, n_docs: int, p_value: float) -> list:
    """The pairs the gate refused: sharing papers, unsurprisingly so."""
    return _overlap_scan(members, n_docs, p_value)[1]


def _best_match(rows_a, rows_b) -> "tuple[float, int, int]":
    """Symmetrised average best-match cosine between two unit-row
    matrices, plus the indices of the single closest pair."""
    cosines = rows_a @ rows_b.T
    forward = cosines.max(axis=1).mean()
    backward = cosines.max(axis=0).mean()
    # divmod, not np.unravel_index, which pylint misreads with numpy ignored.
    i, j = divmod(int(cosines.argmax()), cosines.shape[1])
    return float((forward + backward) / 2), int(i), int(j)


def semantic_edges(vectors: dict, neighbors: int) -> list:
    """Semantic edges: `{a, b, similarity, bridge}` between mutual
    top-k neighbours, over `{label: {citekey: vector}}`; the bridge is the
    closest citekey pair across the edge.
    """
    import numpy as np

    labels = sorted(vectors)
    normalised = {}
    for label in labels:
        keys = sorted(vectors[label])
        rows = np.asarray([vectors[label][k] for k in keys], dtype=float)
        # A zero row is real (a one-document corpus centres to zero), and
        # dividing by its norm would emit NaN, which is invalid JSON.
        norms = np.linalg.norm(rows, axis=1, keepdims=True)
        rows = rows / np.where(norms == 0.0, 1.0, norms)
        normalised[label] = (keys, rows)

    scored = {}
    for a, b in itertools.combinations(labels, 2):
        keys_a, rows_a = normalised[a]
        keys_b, rows_b = normalised[b]
        similarity, i, j = _best_match(rows_a, rows_b)
        scored[(a, b)] = (similarity, [keys_a[i], keys_b[j]])

    # An edge survives only when each end ranks the other in its top k.
    ranked = {
        label: sorted(
            (other for other in labels if other != label),
            # `this=label` avoids pylint's cell-var-from-loop.
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

    Not BERTopic's `hierarchical_topics()`: it needs the unpersisted
    fitted model and covers emergent topics only.
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
    vectors. Centred once here, so every consumer speaks the same space.
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

    edges_overlap, edges_withheld = _overlap_scan(members, topic_set["n_docs"], p_value)
    edges_sem = semantic_edges(
        {label: member_vectors[label] for label in member_vectors if member_vectors[label]},
        neighbors,
    )
    analysis = brokerage([n["label"] for n in nodes], edges_overlap, edges_sem)
    for node in nodes:
        node["analysis"] = analysis[node["label"]]
    return {
        "model": config.EMBEDDING_MODEL,
        "n_docs": topic_set["n_docs"],
        "n_topics": len(nodes),
        "p_value": p_value,
        "neighbors": neighbors,
        "corpus_mean": corpus_mean.tolist(),
        "topics": nodes,
        "edges_overlap": edges_overlap,
        "edges_withheld": edges_withheld,
        "edges_semantic": semantic_edges(
            {label: member_vectors[label] for label in member_vectors if member_vectors[label]},
            neighbors,
        ),
        "hierarchy": hierarchy(labels_with_vectors, centroids),
        "communities": communities([n["label"] for n in nodes], edges_overlap, edges_sem),
        "paths": next_hop_matrices([n["label"] for n in nodes], edges_overlap, edges_sem),
    }


def run_topic_graph(docs) -> dict:
    """Derive the graph and write `content/topic_graph.json`.

    Raises when `content/topic_set.json` is absent: it never does the
    previous stage's work.
    """
    if not config.TOPIC_SET_PATH.exists():
        raise ValueError(
            f"No {config.TOPIC_SET_PATH} to graph. Run the converge stage first; "
            "this stage relates the topics it produced and creates none itself."
        )
    topic_set = json.loads(config.TOPIC_SET_PATH.read_text(encoding="utf-8"))
    # Refuse a topic set from another model *or pooling method* (or one
    # predating the method stamp): pairing gives meaningless edges, and
    # re-running converge is cheap and certain.
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
    """`run_topic_graph()` shaped as an enrichment-stage result:
    `skipped` when converge has not run."""
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

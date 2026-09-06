"""What shape is the topic graph, and does that shape survive a resample?

`chitragupta/enrich/topic_graph.py` builds one graph, at one `p_value`
and one `neighbors`, and reports only how many edges of each family it
produced. That is the right output for a stage -- the tier-1 reader
consumes edges, not statistics about them -- but it leaves three
questions #610 (B7) asks unanswered:

- **How sensitive is the edge count to the two thresholds?** An edge
  count quoted at one setting reads as a property of the corpus when it
  may be a property of `p_value = 0.05`.
- **Does the edge set reproduce?** Every edge here is derived from
  document membership, so dropping documents should perturb it. How
  much is the difference between a graph worth reading and one worth
  ignoring.
- **What are the two graph metrics the comparable work reports?**
  Average degree and average clustering coefficient (Xiang et al.)
  exist nowhere in this repository. They stay out of the *stage's*
  output deliberately -- `docs/TOPIC-DISCOVERY.md` argues a stage that
  publishes a summary statistic invites thresholding it -- so they are
  computed here instead, offline, where a number is read by a person.

Needs the "enrich" Poetry group, a synced corpus and a converged
`content/topic_set.json` (run `--stages converge` first). Reuses
`content/topic_embed_cache.json`, so a warm cache makes this minutes.
Reads those artefacts and writes only its own results file.

    CHITRAGUPTA_PROJECT=. .venv-full/bin/python \\
        bench/bench_topic_graph_shape.py --tag 2026-09-04-topic-graph
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from chitragupta import config  # noqa: E402
from chitragupta.enrich import corpus, doc_vectors, embed_index, topic_graph  # noqa: E402

P_VALUES = (0.05, 0.01, 0.001)
NEIGHBOUR_COUNTS = (3, 5, 8)
# 10% held out per resample, matching bench_topic_depth.py's bootstrap so
# the two stability numbers are read on the same scale.
HOLDOUT = 0.10


def _edge_key(edge: dict) -> tuple:
    """An edge as an unordered node pair, so two graphs are comparable
    regardless of which endpoint each stored first."""
    return tuple(sorted((edge["a"], edge["b"])))


def average_degree(edges: list, n_nodes: int) -> float:
    """Mean node degree over *all* nodes, isolated ones included.

    Counting isolated topics is the whole point of the metric here: a
    graph where three topics are densely joined and forty are alone is
    not a well-connected graph, and averaging over only the connected
    ones would report it as one.
    """
    if not n_nodes:
        return 0.0
    return round(2 * len({_edge_key(e) for e in edges}) / n_nodes, 4)


def _adjacency(edges: list) -> dict:
    adjacency: dict = {}
    for edge in edges:
        a, b = _edge_key(edge)
        if a == b:
            continue
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    return adjacency


def average_clustering(edges: list) -> float:
    """Mean local clustering coefficient over nodes of degree >= 2.

    Nodes of degree 0 or 1 have no pair of neighbours to close, so their
    coefficient is undefined rather than 0.0; averaging them in as zeros
    would report a star graph as poorly clustered when it is simply not
    a graph the metric applies to.
    """
    adjacency = _adjacency(edges)
    scores = []
    for node, neighbours in adjacency.items():
        degree = len(neighbours)
        if degree < 2:
            continue
        links = sum(
            1
            for i, first in enumerate(sorted(neighbours))
            for second in sorted(neighbours)[i + 1 :]
            if second in adjacency.get(first, ())
        )
        scores.append(2 * links / (degree * (degree - 1)))
    return round(sum(scores) / len(scores), 4) if scores else 0.0


def jaccard(left: set, right: set) -> float:
    """Set overlap, with two empty sets counted as identical (1.0)
    rather than as a division by zero. Two runs that both produced no
    edge agree completely about the graph; calling that 0.0 would read
    as maximal instability."""
    if not left and not right:
        return 1.0
    return round(len(left & right) / len(left | right), 4)


def _members(topic_set: dict, keep: "set | None" = None) -> dict:
    """`{label: {citekey}}`, optionally restricted to a kept citekey
    set. Labels left with no member survive as empty sets so the node
    count does not move with the resample -- a topic that lost every
    document is an isolated node, not a deleted one."""
    out = {}
    for topic in topic_set["topics"]:
        keys = {m["citekey"] for m in topic["members"]}
        out[topic["label"]] = keys if keep is None else keys & keep
    return out


def _centred(vectors: dict, keys: "set | None" = None) -> dict:
    """Vectors centred on their own mean, as `topic_graph.build()` does.
    Recomputed per resample rather than reusing the full corpus mean,
    because the resample's mean is what its own edges would be built
    against in a real run over that corpus."""
    import numpy as np

    chosen = {k: v for k, v in vectors.items() if keys is None or k in keys}
    if not chosen:
        return {}
    mean = np.asarray(list(chosen.values()), dtype=float).mean(axis=0)
    return {k: np.asarray(v, dtype=float) - mean for k, v in chosen.items()}


def _member_vectors(members: dict, centred: dict) -> dict:
    return {
        label: {k: centred[k] for k in keys if k in centred}
        for label, keys in members.items()
        if any(k in centred for k in keys)
    }


def measure_cell(topic_set, vectors, p_value, neighbours) -> dict:
    """One (p_value, neighbours) cell: both edge families and the two
    graph metrics, over the union of the families and over each alone."""
    members = _members(topic_set)
    centred = _centred(vectors)
    overlap = topic_graph.overlap_edges(members, topic_set["n_docs"], p_value)
    semantic = topic_graph.semantic_edges(_member_vectors(members, centred), neighbours)
    n_nodes = len(members)
    both = overlap + semantic
    return {
        "p_value": p_value,
        "neighbors": neighbours,
        "n_topics": n_nodes,
        "overlap_edges": len(overlap),
        "semantic_edges": len(semantic),
        "avg_degree_overlap": average_degree(overlap, n_nodes),
        "avg_degree_semantic": average_degree(semantic, n_nodes),
        "avg_degree_union": average_degree(both, n_nodes),
        "avg_clustering_overlap": average_clustering(overlap),
        "avg_clustering_semantic": average_clustering(semantic),
        "avg_clustering_union": average_clustering(both),
    }


def bootstrap_stability(topic_set, vectors, p_value, neighbours, repeats, seed=42) -> dict:
    """Edge-set Jaccard between the full graph and graphs built on
    resamples that drop `HOLDOUT` of the documents.

    The topic *assignment* is held fixed and only membership is thinned:
    this measures whether the edges are an artefact of a few documents,
    which is B7's question, and not whether clustering reproduces, which
    is `bench_topic_depth.py --repeats`'s.
    """
    rng = random.Random(seed)
    citekeys = sorted({k for keys in _members(topic_set).values() for k in keys})
    full = measure_edges(topic_set, vectors, p_value, neighbours, None)
    overlap_scores, semantic_scores = [], []
    for _ in range(repeats):
        keep = set(rng.sample(citekeys, int(round(len(citekeys) * (1 - HOLDOUT)))))
        resampled = measure_edges(topic_set, vectors, p_value, neighbours, keep)
        overlap_scores.append(jaccard(full["overlap"], resampled["overlap"]))
        semantic_scores.append(jaccard(full["semantic"], resampled["semantic"]))
    return {
        "repeats": repeats,
        "holdout": HOLDOUT,
        "overlap_jaccard_mean": round(sum(overlap_scores) / len(overlap_scores), 4),
        "overlap_jaccard_min": min(overlap_scores),
        "semantic_jaccard_mean": round(sum(semantic_scores) / len(semantic_scores), 4),
        "semantic_jaccard_min": min(semantic_scores),
    }


def measure_edges(topic_set, vectors, p_value, neighbours, keep) -> dict:
    """Both edge families as unordered node-pair sets, over the whole
    corpus (`keep is None`) or one resample of it."""
    members = _members(topic_set, keep)
    n_docs = topic_set["n_docs"] if keep is None else len(keep)
    centred = _centred(vectors, keep)
    overlap = topic_graph.overlap_edges(members, n_docs, p_value)
    semantic = topic_graph.semantic_edges(_member_vectors(members, centred), neighbours)
    return {
        "overlap": {_edge_key(e) for e in overlap},
        "semantic": {_edge_key(e) for e in semantic},
    }


def self_check() -> None:
    """Fabricate each aggregation's answer by hand and assert it is read.

    A triangle is the case that separates the two metrics: every node
    has degree 2 and every neighbour pair is joined, so average degree
    is 2.0 and clustering is exactly 1.0. A path over the same three
    nodes has one fewer edge and closes no triangle, so clustering
    collapses to 0.0 while average degree only falls to 1.33. A
    clustering function that silently returned the density of the graph
    would agree with the first and disagree with the second.
    """
    triangle = [{"a": "x", "b": "y"}, {"a": "y", "b": "z"}, {"a": "z", "b": "x"}]
    path = [{"a": "x", "b": "y"}, {"a": "y", "b": "z"}]
    assert average_degree(triangle, 3) == 2.0, average_degree(triangle, 3)
    assert average_clustering(triangle) == 1.0, average_clustering(triangle)
    assert average_degree(path, 3) == 1.3333, average_degree(path, 3)
    assert average_clustering(path) == 0.0, average_clustering(path)
    # An isolated node must drag the average down, or a graph of three
    # joined topics and forty lonely ones reports as well-connected.
    assert average_degree(triangle, 6) == 1.0, average_degree(triangle, 6)
    assert jaccard({("a", "b")}, {("a", "b")}) == 1.0
    assert jaccard({("a", "b")}, {("c", "d")}) == 0.0
    assert jaccard(set(), set()) == 1.0, "two edgeless graphs agree; that is not instability"


def _print_grid(rows: list) -> None:
    print(
        f"\n{'p':>7} {'nbr':>4} | {'overlap':>7} {'semantic':>8} "
        f"{'deg(o)':>7} {'deg(s)':>7} {'clu(o)':>7} {'clu(s)':>7}",
        flush=True,
    )
    for row in rows:
        print(
            f"{row['p_value']:>7} {row['neighbors']:>4} | "
            f"{row['overlap_edges']:>7} {row['semantic_edges']:>8} "
            f"{row['avg_degree_overlap']:>7} {row['avg_degree_semantic']:>7} "
            f"{row['avg_clustering_overlap']:>7} {row['avg_clustering_semantic']:>7}",
            flush=True,
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="names the results directory")
    parser.add_argument(
        "--repeats", type=int, default=20, help="bootstrap resamples per family (default: 20)"
    )
    args = parser.parse_args(argv)
    self_check()

    if not config.TOPIC_SET_PATH.exists():
        raise SystemExit(
            f"No {config.TOPIC_SET_PATH}. Run `python -m chitragupta.enrich "
            "--stages bertopic,extract-keywords,seed-topics,converge` first -- "
            "this measures a converged topic set and builds none itself."
        )
    topic_set = json.loads(config.TOPIC_SET_PATH.read_text(encoding="utf-8"))

    docs = corpus.build_corpus()
    doc_texts = doc_vectors.corpus_texts(docs)
    _client, model = embed_index.get_client_and_model()
    started = time.time()
    vectors = doc_vectors.document_embeddings(doc_texts, model)
    print(
        f"{len(vectors)} documents, {len(topic_set['topics'])} topics, "
        f"embedded in {time.time() - started:.0f}s (0s means the cache was warm)",
        flush=True,
    )

    rows = [measure_cell(topic_set, vectors, p, n) for p in P_VALUES for n in NEIGHBOUR_COUNTS]
    _print_grid(rows)

    shipped = bootstrap_stability(
        topic_set,
        vectors,
        config.TOPIC_GRAPH_P_VALUE,
        config.TOPIC_GRAPH_NEIGHBORS,
        args.repeats,
    )
    print(
        f"\nbootstrap at the shipped setting "
        f"(p={config.TOPIC_GRAPH_P_VALUE}, neighbors={config.TOPIC_GRAPH_NEIGHBORS}), "
        f"{args.repeats} resamples dropping {HOLDOUT:.0%}:",
        flush=True,
    )
    print(
        f"  overlap  edge-set Jaccard mean {shipped['overlap_jaccard_mean']} "
        f"(min {shipped['overlap_jaccard_min']})",
        flush=True,
    )
    print(
        f"  semantic edge-set Jaccard mean {shipped['semantic_jaccard_mean']} "
        f"(min {shipped['semantic_jaccard_min']})",
        flush=True,
    )

    out_dir = REPO / "bench" / "results" / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": config.EMBEDDING_MODEL,
        "n_docs": topic_set["n_docs"],
        "n_topics": len(topic_set["topics"]),
        "shipped_p_value": config.TOPIC_GRAPH_P_VALUE,
        "shipped_neighbors": config.TOPIC_GRAPH_NEIGHBORS,
        "grid": rows,
        "stability": shipped,
    }
    (out_dir / "topic_graph_shape.json").write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"\nwrote {out_dir / 'topic_graph_shape.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

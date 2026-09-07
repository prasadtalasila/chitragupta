"""Stored MCL communities for the topic graph (#712).

A numpy port of `assets/webapp/families.js`'s Markov clustering --
expand, inflate, renormalise, same self-loops, same convergence test,
same first-attractor-by-payload-order cluster reading -- run once per
edge family at every value the app's inflation slider can take (it is
integer-stepped: 1.2 to 4.0 by 0.1, 29 values), and stored in the
artefact so both surfaces read the same partitions. MCL is not in
networkx; §14 weighed a scipy loop, a pinned port of families.js, or
driving the JS through node, and this is the pinned port --
`tests/webapp/mcl_cases.json` holds the two implementations to the same
assignments, from node and from pytest, so neither can drift alone.

Partitions are stored as one cluster index per topic, aligned with the
artefact's own topic order -- compact, and the reader rebuilds the
member lists from data it already holds.
"""

MAX_ITERATIONS = 40
EPSILON = 1e-6
# The slider's own steps: `#inflation` is min=12 max=40 step=1, read as
# value/10, so this is every inflation the app can ask for.
INFLATIONS = [round(step / 10, 1) for step in range(12, 41)]

_WEIGHT_KEY = {"overlap": "overlap_coeff", "semantic": "similarity"}


def cluster(labels: list, edges: list, weight_key: str, inflation: float) -> dict:
    """One family at one inflation: `{"clusters": [...], "cluster_of":
    {...}}`, exactly families.js's cluster()."""
    import numpy as np

    n = len(labels)
    index = {label: i for i, label in enumerate(labels)}
    m = np.eye(n)
    for edge in edges:
        a, b = index.get(edge["a"]), index.get(edge["b"])
        if a is None or b is None:
            continue
        m[a, b] = m[b, a] = edge[weight_key]
    m = _normalise(m)
    for _ in range(MAX_ITERATIONS):
        nxt = _normalise((m @ m) ** inflation)
        moved = float(np.abs(nxt - m).max()) if n else 0.0
        m = nxt
        if moved < EPSILON:
            break
    return _read_clusters(m, labels)


def _normalise(m) -> "np.ndarray":
    sums = m.sum(axis=0)
    sums[sums == 0.0] = 1.0
    return m / sums


def _read_clusters(m, labels: list) -> dict:
    """First attractor by payload order takes a column; anything
    unclaimed stands alone. Deterministic, every topic in one place."""
    cluster_of: dict = {}
    clusters: list = []
    n = len(labels)
    for i in range(n):
        members = [labels[j] for j in range(n) if m[i, j] > EPSILON and labels[j] not in cluster_of]
        if not members:
            continue
        cid = f"mcl-{len(clusters)}"
        for label in members:
            cluster_of[label] = cid
        clusters.append({"id": cid, "members": members})
    for label in labels:
        if label not in cluster_of:
            cid = f"mcl-{len(clusters)}"
            cluster_of[label] = cid
            clusters.append({"id": cid, "members": [label]})
    return {"clusters": clusters, "cluster_of": cluster_of}


def communities(labels: list, edges_overlap: list, edges_semantic: list) -> dict:
    """The stored block: per family, method parameters and one
    assignment array per slider inflation, aligned with topic order."""
    out: dict = {}
    for family, edges in (("overlap", edges_overlap), ("semantic", edges_semantic)):
        partitions = {}
        for inflation in INFLATIONS:
            result = cluster(labels, edges, _WEIGHT_KEY[family], inflation)
            partitions[f"{inflation:.1f}"] = [
                int(result["cluster_of"][label].removeprefix("mcl-")) for label in labels
            ]
        out[family] = {
            "method": "mcl",
            "iterations": MAX_ITERATIONS,
            "epsilon": EPSILON,
            "weight": _WEIGHT_KEY[family],
            "partitions": partitions,
        }
    return out

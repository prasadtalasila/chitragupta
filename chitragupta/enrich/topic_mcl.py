"""Stored MCL communities for the topic graph (#712).

A numpy port of `assets/webapp/families.js`'s Markov clustering, run per
edge family at every inflation the app's slider can take, so both
surfaces read the same partitions. MCL is not in networkx; the pinned
port won over scipy or driving JS through node (§14), and
`tests/webapp/mcl_cases.json` holds both implementations to the same
assignments. Stored as one cluster index per topic, in topic order.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # the runtime import stays lazy, inside cluster()
    import numpy as np

MAX_ITERATIONS = 40
EPSILON = 1e-6
# The slider's steps: `#inflation` min=12 max=40 step=1, read as value/10.
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

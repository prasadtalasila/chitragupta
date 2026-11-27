"""Stored brokerage for the topic graph (#713).

The four per-edge-family numbers the app's topic panel shows
(`assets/webapp/ego.js` egoStats), computed here so `--json` can confirm
them. `tests/webapp/brokerage_cases.json` keeps both sides equal. Per
family, never pooled: brokering over papers and over vocabulary differ.
"""

import itertools

_WEIGHT_KEY = {"overlap": "overlap_coeff", "semantic": "similarity"}


def _family_stats(graph, label) -> dict:
    """One ego's four numbers over one family's graph. None wherever the
    arithmetic has no answer, as egoStats does, because NaN passes every
    is-a-number guard."""
    import networkx as nx

    alters = list(graph[label])
    if not alters:
        return {"degree": 0, "ego_density": None, "effective_size": 0, "constraint": None}
    among = sum(1 for i, j in itertools.combinations(alters, 2) if graph.has_edge(i, j))
    pairs = len(alters) * (len(alters) - 1) / 2
    return {
        "degree": len(alters),
        "ego_density": round(among / pairs, 6) if pairs else None,
        "effective_size": round(nx.effective_size(graph, nodes=[label], weight="weight")[label], 6),
        "constraint": round(nx.constraint(graph, nodes=[label], weight="weight")[label], 6),
    }


def brokerage(labels: list, edges_overlap: list, edges_semantic: list) -> dict:
    """`{label: {"overlap": {...}, "semantic": {...}}}` for every topic:
    the `analysis` block docs/TOPIC-DISCOVERY-GRAPH.md §2 describes, in
    its key names."""
    import networkx as nx

    out: dict = {label: {} for label in labels}
    for family, edges in (("overlap", edges_overlap), ("semantic", edges_semantic)):
        graph = nx.Graph()
        graph.add_nodes_from(labels)
        for edge in edges:
            graph.add_edge(edge["a"], edge["b"], weight=edge[_WEIGHT_KEY[family]])
        for label in labels:
            out[label][family] = _family_stats(graph, label)
    return out

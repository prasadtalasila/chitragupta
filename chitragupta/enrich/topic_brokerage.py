"""Stored brokerage for the topic graph (#713).

The app's topic panel answers "is this a theme or a bridge" with four
numbers per edge family -- neighbour count, ego density, Burt effective
size, Burt constraint (`assets/webapp/ego.js` egoStats). This module
computes the same four in the builder and `topic_graph.build` stores
them in each topic's `analysis`, so the panel reads the artefact and
`--json` can confirm every number it shows.

networkx's weighted `effective_size` and `constraint` were verified
equal to egoStats's arithmetic before this was written -- both
normalise the marginal by the alter's strongest single tie -- and
`tests/webapp/brokerage_cases.json` keeps them equal: node asserts the
browser reproduces every row, tests/test_enrich_topic_brokerage.py
asserts this side does. Per family and never pooled, for the reason
egoStats gives: a topic that brokers over shared papers but not over
vocabulary is a different animal from one that does the reverse.
"""

import itertools

_WEIGHT_KEY = {"overlap": "overlap_coeff", "semantic": "similarity"}


def _family_stats(graph, label) -> dict:
    """One ego's four numbers over one family's graph. Null (None)
    wherever the arithmetic has no answer -- the same rule egoStats
    follows, because NaN passes every is-a-number guard."""
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
    the `analysis` block docs/TOPIC-DISCOVERY-GRAPH.md §3 designs, in
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

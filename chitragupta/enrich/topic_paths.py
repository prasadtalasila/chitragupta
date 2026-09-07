"""Stored typed shortest paths for the topic graph (#714).

The app walks each edge family between two pinned topics with Dijkstra
over `1 - strength` (`assets/webapp/families.js` path()), so the strong
route wins over the short one. This module computes the same trees once
in the builder -- networkx's Dijkstra, one single-source run per topic
per family -- and stores a next-hop matrix: `next[i][j]` is the index
into that family's own edge list of i's first hop toward j, `-1` where
no path exists (an answer, not an absence), one row and column per
topic in payload order. The reader walks the matrix and resolves each
hop's evidence from the edge lists it already holds -- indices, never
inlined citekeys, which is what keeps 131x131x2 affordable.

Never a fused-family matrix: a path over both families would be a
distance nobody can interpret, and the design refuses it.
`tests/webapp/path_cases.json` pins the stored trees to families.js's
own walk, from node and from pytest.
"""

_WEIGHT_KEY = {"overlap": "overlap_coeff", "semantic": "similarity"}


def next_hop_matrices(labels: list, edges_overlap: list, edges_semantic: list) -> dict:
    import networkx as nx

    out: dict = {}
    index = {label: i for i, label in enumerate(labels)}
    for family, edges in (("overlap", edges_overlap), ("semantic", edges_semantic)):
        graph = nx.Graph()
        graph.add_nodes_from(labels)
        for i, edge in enumerate(edges):
            graph.add_edge(edge["a"], edge["b"], weight=1 - edge[_WEIGHT_KEY[family]], index=i)
        n = len(labels)
        matrix = [[-1] * n for _ in range(n)]
        for target in labels:
            # The predecessor tree rooted at the target: a source's first
            # predecessor toward the target IS its next hop, since the
            # graph is undirected and Dijkstra trees are symmetric in it.
            predecessors, _ = nx.dijkstra_predecessor_and_distance(graph, target)
            for source, towards in predecessors.items():
                if source == target or not towards:
                    continue
                matrix[index[source]][index[target]] = graph[source][towards[0]]["index"]
        out[family] = {"weight": f"1 - {_WEIGHT_KEY[family]}", "next": matrix}
    return out

"""Stored typed shortest paths for the topic graph (#714).

Dijkstra over `1 - strength` per edge family, as `assets/webapp/families.js`
path() walks it, stored as a next-hop matrix: `next[i][j]` indexes that
family's edge list, `-1` where no path exists. Indices, not inlined
citekeys, keep it affordable. Never a fused-family matrix: that distance
means nothing. `tests/webapp/path_cases.json` pins it to families.js.
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
            # In an undirected graph, the predecessor toward the target is
            # the next hop.
            predecessors, _ = nx.dijkstra_predecessor_and_distance(graph, target)
            for source, towards in predecessors.items():
                if source == target or not towards:
                    continue
                matrix[index[source]][index[target]] = graph[source][towards[0]]["index"]
        out[family] = {"weight": f"1 - {_WEIGHT_KEY[family]}", "next": matrix}
    return out

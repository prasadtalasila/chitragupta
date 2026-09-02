"""Personalised PageRank over the topic graph: rank a neighbourhood by
topology instead of concatenating per-topic lists.

Used when the resolution ladder's hybrid rung places a phrase near
*several* topics: the seeds are the matched topics, and the walk ranks
every topic by how reachable it is from them along the graph's own
edges -- MiniRAG's topology-based scoring with its LLM step deleted,
which is what makes it borrowable here. A singular resolution gets no
walk: the topic view's linked-topics lists already answer "what is next
to this one", and a one-seed walk would restate them with extra
arithmetic.

Both edge families feed the walk. They stay separate everywhere they
are *shown* because their disagreement is a signal; a random walk is
the one consumer that genuinely wants "is there any relation at all",
so an edge weighs in at the stronger of its two readings.
"""

# Standard PageRank damping. Not a config knob on purpose: at a few
# dozen nodes the ranking is insensitive to it, and a knob nobody can
# meaningfully tune is documentation debt wearing a settings key.
_DAMPING = 0.85
_ITERATIONS = 50


def _weights(graph: dict) -> dict:
    """Undirected adjacency `{label: {other: weight}}`, an edge weighing
    the stronger of its overlap and semantic readings."""
    adjacency: dict = {topic["label"]: {} for topic in graph["topics"]}
    for edge in graph["edges_overlap"]:
        weight = edge["overlap_coeff"]
        adjacency[edge["a"]][edge["b"]] = max(adjacency[edge["a"]].get(edge["b"], 0.0), weight)
        adjacency[edge["b"]][edge["a"]] = max(adjacency[edge["b"]].get(edge["a"], 0.0), weight)
    for edge in graph["edges_semantic"]:
        weight = edge["similarity"]
        adjacency[edge["a"]][edge["b"]] = max(adjacency[edge["a"]].get(edge["b"], 0.0), weight)
        adjacency[edge["b"]][edge["a"]] = max(adjacency[edge["b"]].get(edge["a"], 0.0), weight)
    return adjacency


def personalised_pagerank(graph: dict, seeds: list) -> list:
    """`[(label, score), ...]` best first, scores summing to 1.

    Power iteration with the teleport vector uniform over the seeds;
    a node with no edges hands its whole rank back to the seeds, so
    disconnected topics keep only what teleporting gives them.
    """
    adjacency = _weights(graph)
    nodes = sorted(adjacency)
    if not nodes:
        return []
    # dict.fromkeys, not a list comprehension: a duplicated seed would
    # inflate the divisor while its node still collects one teleport
    # share, quietly breaking the scores-sum-to-1 contract.
    seed_set = list(dict.fromkeys(seed for seed in seeds if seed in adjacency)) or nodes
    teleport = {node: (1.0 / len(seed_set) if node in seed_set else 0.0) for node in nodes}
    rank = dict(teleport)
    for _ in range(_ITERATIONS):
        incoming = {node: 0.0 for node in nodes}
        dangling = 0.0
        for node in nodes:
            total = sum(adjacency[node].values())
            if not total:
                dangling += rank[node]
                continue
            for other, weight in adjacency[node].items():
                incoming[other] += rank[node] * weight / total
        rank = {
            node: (1.0 - _DAMPING) * teleport[node]
            + _DAMPING * (incoming[node] + dangling * teleport[node])
            for node in nodes
        }
    return sorted(rank.items(), key=lambda pair: (-pair[1], pair[0]))

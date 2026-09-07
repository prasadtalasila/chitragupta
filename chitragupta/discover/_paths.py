"""Walking the stored path matrices (#714): the reader half.

`enrich/topic_paths.py` stored `next[i][j]` -- an index into one
family's own edge list -- and this module turns a pair of topics into
the app's own hop shape: each hop with the edge's strength and its
evidence (shared citekeys, or the bridging pair), resolved from data
the reader already holds. `labels: None` means no path in *this*
family, which is an answer, and often the interesting one.
"""

_WEIGHT_KEY = {"overlap": "overlap_coeff", "semantic": "similarity"}
_EVIDENCE_KEY = {"overlap": "shared", "semantic": "bridge"}


def walk_path(graph: dict, family: str, start: str, goal: str) -> "dict | None":
    """None when the artefact stores no matrices (an older run); the
    no-path answer when it does and says so."""
    held = graph.get("paths", {}).get(family)
    if held is None:
        return None
    labels = [t["label"] for t in graph["topics"]]
    index = {label: i for i, label in enumerate(labels)}
    edges = graph["edges_overlap" if family == "overlap" else "edges_semantic"]
    hops = []
    path = [start]
    cursor = start
    while cursor != goal:
        edge_index = held["next"][index[cursor]][index[goal]]
        if edge_index == -1:
            return {"labels": None, "hops": [], "family": family}
        edge = edges[edge_index]
        nxt = edge["b"] if edge["a"] == cursor else edge["a"]
        hops.append(
            {
                "a": cursor,
                "b": nxt,
                "family": family,
                "strength": edge[_WEIGHT_KEY[family]],
                "index": edge_index,
                "evidence": edge[_EVIDENCE_KEY[family]],
            }
        )
        path.append(nxt)
        cursor = nxt
    return {"labels": path, "hops": hops, "family": family}


def render_path(result: dict) -> str:
    family = "shared papers" if result["family"] == "overlap" else "semantic nearness"
    if result["labels"] is None:
        return (
            f"no path over {family} -- nothing links these two over this "
            "family, which is an answer, and often the interesting one"
        )
    lines = [f"path over {family}: {' -> '.join(result['labels'])}", ""]
    for hop in result["hops"]:
        lines.append(
            f"  {hop['a']} -> {hop['b']}  (strength {hop['strength']:.2f}, "
            f"via: {', '.join(hop['evidence'])})"
        )
    return "\n".join(lines)

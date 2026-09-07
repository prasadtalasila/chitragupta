"""`discover TOPIC --hops N`: the ego view's rings, as text (#716).

A port of `assets/webapp/ego.js`'s hopsFrom and reachedVia -- BFS over
both edge families, ring one typed by which family reached each
neighbour, deeper rings by distance alone (past one hop a topic is
reached by a path, and labelling a path with one family would claim how
the reader got there). `tests/webapp/hop_cases.json` pins the two
implementations to each other. A topic the roots cannot reach has no
entry at all: an absent distance is the honest answer, and the view
counts the unreached rather than drawing them far away.
"""

_FAMILY_PROSE = {
    "overlap": "via shared papers",
    "semantic": "via semantic nearness",
    "both": "via both families",
}


def _adjacency(graph: dict) -> dict:
    near: dict = {}
    for edge in graph["edges_overlap"] + graph["edges_semantic"]:
        near.setdefault(edge["a"], set()).add(edge["b"])
        near.setdefault(edge["b"], set()).add(edge["a"])
    return near


def hops_from(graph: dict, roots: list) -> dict:
    """BFS depth from the roots over both families, exactly ego.js's
    hopsFrom with both families enabled."""
    near = _adjacency(graph)
    depth = {label: 0 for label in roots}
    frontier = list(roots)
    while frontier:
        nxt = []
        for label in frontier:
            for other in sorted(near.get(label, ())):
                if other not in depth:
                    depth[other] = depth[label] + 1
                    nxt.append(other)
        frontier = nxt
    return depth

def reached_via(graph: dict, roots: list) -> dict:
    """Which family reaches each direct neighbour: overlap, semantic,
    or both -- ego.js's reachedVia."""
    pinned = set(roots)
    via: dict = {}

    def mark(label: str, family: str) -> None:
        if label in pinned:
            return
        via[label] = "both" if via.get(label) not in (None, family) else family

    for family, edges in (("overlap", graph["edges_overlap"]), ("semantic", graph["edges_semantic"])):
        for edge in edges:
            if edge["a"] in pinned:
                mark(edge["b"], family)
            if edge["b"] in pinned:
                mark(edge["a"], family)
    return via


def build_hops(graph: dict, label: str, max_hops: "int | None") -> dict:
    """The rings up to `max_hops` (None: everything reachable), plus an
    honest count of what the roots cannot reach at all."""
    depth = hops_from(graph, [label])
    via = reached_via(graph, [label])
    deepest = max(depth.values(), default=0)
    bound = deepest if max_hops is None else min(max_hops, deepest)
    rings = []
    for hop in range(1, bound + 1):
        topics = [
            {"label": other, **({"via": via[other]} if hop == 1 else {})}
            for other in sorted(depth)
            if depth[other] == hop
        ]
        rings.append({"hop": hop, "topics": topics})
    return {
        "topic": label,
        "max_hops": "all" if max_hops is None else max_hops,
        "rings": rings,
        "unreached": len(graph["topics"]) - len(depth),
    }


def render_hops(data: dict) -> str:
    lines = [f"{data['topic']} — neighbourhood by hop distance"]
    for ring in data["rings"]:
        lines += ["", f"hop {ring['hop']}:"]
        # A BFS ring inside the deepest bound is never empty, so no
        # "none at this distance" apology is needed or possible.
        for topic in ring["topics"]:
            suffix = f"  ({_FAMILY_PROSE[topic['via']]})" if "via" in topic else ""
            lines.append(f"  {topic['label']}{suffix}")
    if not data["rings"]:
        lines += ["", "no topic is reachable from here in either family"]
    if data["unreached"]:
        lines += [
            "",
            f"unreached from here: {data['unreached']} topic"
            + ("" if data["unreached"] == 1 else "s"),
        ]
    return "\n".join(lines)

"""`discover TOPIC --hops N [--family F]`: the ego view's rings, as text.

A port of `assets/webapp/ego.js`'s hopsFrom and reachedVia, pinned to it
by `tests/webapp/hop_cases.json`. Only ring one is typed by family;
deeper rings are reached by a path, which no one family describes.
Unreachable topics have no entry and are counted, not drawn far away.
`families=None` means both.
"""

BOTH = ("overlap", "semantic")

_FAMILY_PROSE = {
    "overlap": "via shared papers",
    "semantic": "via semantic nearness",
    "both": "via both families",
}

_WALK_PROSE = {
    "overlap": "shared papers",
    "semantic": "semantic nearness",
}


def _walked(families: "list | None") -> list:
    return list(families) if families else list(BOTH)


def _edges_of(graph: dict, family: str) -> list:
    return graph["edges_overlap"] if family == "overlap" else graph["edges_semantic"]


def _adjacency(graph: dict, families: "list | None" = None) -> dict:
    near: dict = {}
    for family in _walked(families):
        for edge in _edges_of(graph, family):
            near.setdefault(edge["a"], set()).add(edge["b"])
            near.setdefault(edge["b"], set()).add(edge["a"])
    return near


def hops_from(graph: dict, roots: list, families: "list | None" = None) -> dict:
    """BFS depth from the roots over the enabled families, exactly
    ego.js's hopsFrom."""
    near = _adjacency(graph, families)
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


def reached_via(graph: dict, roots: list, families: "list | None" = None) -> dict:
    """Which family reaches each direct neighbour (ego.js's reachedVia).
    A neighbour both reach types as the one walked, not "both", which
    would claim more than the view sees."""
    pinned = set(roots)
    via: dict = {}

    def mark(label: str, family: str) -> None:
        if label in pinned:
            return
        via[label] = "both" if via.get(label) not in (None, family) else family

    for family in _walked(families):
        for edge in _edges_of(graph, family):
            if edge["a"] in pinned:
                mark(edge["b"], family)
            if edge["b"] in pinned:
                mark(edge["a"], family)
    return via


def build_hops(
    graph: dict, label: str, max_hops: "int | None", families: "list | None" = None
) -> dict:
    """The rings up to `max_hops` (None: everything reachable), plus a
    count of what is unreachable. Records the families walked, so
    `--json` readers can tell which walk it was."""
    depth = hops_from(graph, [label], families)
    via = reached_via(graph, [label], families)
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
        "families": _walked(families),
        "rings": rings,
        "unreached": len(graph["topics"]) - len(depth),
    }


def _over(data: dict) -> str:
    """ " over shared papers", or nothing when both were walked: a
    qualifier on every default run is noise."""
    # `build_hops` always records them, so no fallback is needed.
    if len(data["families"]) != 1:
        return ""
    return f" over {_WALK_PROSE[data['families'][0]]}"


def render_hops(data: dict) -> str:
    lines = [f"{data['topic']} — neighbourhood by hop distance{_over(data)}"]
    for ring in data["rings"]:
        lines += ["", f"hop {ring['hop']}:"]
        # A BFS ring inside the bound is never empty.
        for topic in ring["topics"]:
            suffix = f"  ({_FAMILY_PROSE[topic['via']]})" if "via" in topic else ""
            lines.append(f"  {topic['label']}{suffix}")
    if not data["rings"]:
        reach = _over(data) or " in either family"
        lines += ["", f"no topic is reachable from here{reach}"]
    if data["unreached"]:
        lines += [
            "",
            f"unreached from here: {data['unreached']} topic"
            + ("" if data["unreached"] == 1 else "s"),
        ]
    return "\n".join(lines)

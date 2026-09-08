"""`discover TOPIC --hops N [--family F]`: the ego view's rings, as text.

A port of `assets/webapp/ego.js`'s hopsFrom and reachedVia -- BFS over
the families asked for, ring one typed by which of them reached each
neighbour, deeper rings by distance alone (past one hop a topic is
reached by a path, and labelling a path with one family would claim how
the reader got there). `tests/webapp/hop_cases.json` pins the two
implementations to each other. A topic the roots cannot reach has no
entry at all: an absent distance is the honest answer, and the view
counts the unreached rather than drawing them far away.

`families` is None everywhere the caller means both, which is what this
module always did: measuring over the union whatever the reader wanted
put a topic one shared paper plus one cosine hop away on the same ring
as a topic two shared papers out, and `--family` could not say
otherwise because it reached only `--path`.
"""

BOTH = ("overlap", "semantic")

_FAMILY_PROSE = {
    "overlap": "via shared papers",
    "semantic": "via semantic nearness",
    "both": "via both families",
}

# The same two families as the subject of a sentence about the walk
# rather than as the label on one neighbour.
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
    """Which family reaches each direct neighbour: overlap, semantic,
    or both -- ego.js's reachedVia, over the enabled families. A
    neighbour both families reach types as the one walked, not as
    "both": a verdict about an edge the view is not walking claims more
    than the view can see."""
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
    """The rings up to `max_hops` (None: everything reachable), plus an
    honest count of what the roots cannot reach at all. The payload
    records the families walked, so a reader holding the `--json` output
    can tell "two hops over shared papers" from "two hops over
    whichever family got there first"."""
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
    qualifier on every default run is noise, and its absence is what
    makes it worth reading when it is there."""
    # `build_hops` always records them, so there is nothing to guess
    # here and no fallback that a test would have to reach for.
    if len(data["families"]) != 1:
        return ""
    return f" over {_WALK_PROSE[data['families'][0]]}"


def render_hops(data: dict) -> str:
    lines = [f"{data['topic']} — neighbourhood by hop distance{_over(data)}"]
    for ring in data["rings"]:
        lines += ["", f"hop {ring['hop']}:"]
        # A BFS ring inside the deepest bound is never empty, so no
        # "none at this distance" apology is needed or possible.
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

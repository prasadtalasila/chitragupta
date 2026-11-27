"""`discover --clusters [--inflation X]`: the disagreement grid's
terminal twin (#712).

Derives families.js's two disagreement lists from the stored
`communities` partitions. Clusters nothing: an older artefact without
partitions is refused, naming the stage to re-run.
"""

import itertools

# families.js's cap: lists grow with the square of a cluster, and a silent
# cut would read as "that is all".
MAX_PAIRS = 200


def stored_partition(graph: dict, family: str, inflation: float) -> "dict | None":
    held = graph.get("communities", {}).get(family)
    assignments = (held or {}).get("partitions", {}).get(f"{inflation:.1f}")
    if assignments is None:
        return None
    labels = [t["label"] for t in graph["topics"]]
    clusters: dict = {}
    for label, cluster in zip(labels, assignments):
        clusters.setdefault(f"mcl-{cluster}", []).append(label)
    return {"clusters": clusters, "cluster_of": dict(zip(labels, assignments))}


def build_clusters(graph: dict, topic_set: dict, inflation: float) -> "dict | None":
    overlap = stored_partition(graph, "overlap", inflation)
    semantic = stored_partition(graph, "semantic", inflation)
    if overlap is None or semantic is None:
        return None
    members = {t["label"]: {m["citekey"] for m in t["members"]} for t in topic_set["topics"]}
    semantic_only: list = []
    overlap_only: list = []
    for a, b in itertools.combinations([t["label"] for t in graph["topics"]], 2):
        same_overlap = overlap["cluster_of"][a] == overlap["cluster_of"][b]
        same_semantic = semantic["cluster_of"][a] == semantic["cluster_of"][b]
        if same_overlap == same_semantic:
            continue
        pair = {"a": a, "b": b, "shared": len(members[a] & members[b])}
        (semantic_only if same_semantic else overlap_only).append(pair)
    semantic_only.sort(key=lambda p: p["shared"])
    overlap_only.sort(key=lambda p: -p["shared"])
    return {
        "inflation": inflation,
        "overlap": overlap["clusters"],
        "semantic": semantic["clusters"],
        "semantic_only": semantic_only[:MAX_PAIRS],
        "overlap_only": overlap_only[:MAX_PAIRS],
        "dropped": max(0, len(semantic_only) - MAX_PAIRS) + max(0, len(overlap_only) - MAX_PAIRS),
    }


def _pair_lines(title: str, why: str, pairs: list) -> list:
    if not pairs:
        return []
    lines = ["", f"{title} ({why}):"]
    for pair in pairs:
        count = (
            f"{pair['shared']} shared paper{'s' if pair['shared'] != 1 else ''}"
            if pair["shared"]
            else "no shared papers at all"
        )
        lines.append(f"  {pair['a']} — {pair['b']}  ({count})")
    return lines


def render_clusters(data: dict) -> str:
    lines = [
        f"clusters at inflation {data['inflation']:g}, read from the artefact",
        "",
        f"over shared papers: {len(data['overlap'])} clusters",
        f"over semantic nearness: {len(data['semantic'])} clusters",
    ]
    if not data["semantic_only"] and not data["overlap_only"]:
        lines += ["", "the two families agree about every pair at this inflation"]
    lines += _pair_lines(
        "talk alike, do not share papers",
        "one semantic cluster, different paper-sharing clusters",
        data["semantic_only"],
    )
    lines += _pair_lines(
        "share papers, talk differently",
        "one paper-sharing cluster, different semantic clusters",
        data["overlap_only"],
    )
    if data["dropped"]:
        lines += [
            "",
            f"{data['dropped']} more pair{'s are' if data['dropped'] != 1 else ' is'} "
            "not listed; the lists are capped so a large cluster cannot fill the screen",
        ]
    return "\n".join(lines)

"""`discover --groups N`: the merge-tree cut's terminal twin (#709).

The same three functions as `assets/webapp/graph.js` (cutTree,
groupLabel, thresholdForGroups) on the *stored* tree, so it derives no
partition. `tests/webapp/cut_cases.json` pins both implementations.
Reads `size` where the app reads `members.length`; the case file
carries `size` for both.
"""

from collections.abc import Callable


def group_label(members: list, sizes: dict) -> str:
    """The topic carrying the most papers leads and the rest are
    counted, never an invented name; ties alphabetical, as graph.js."""
    if len(members) == 1:
        return members[0]
    lead = min(members, key=lambda label: (-sizes.get(label, 0), label))
    return f"{lead} +{len(members) - 1}"


def _join_below(hierarchy: list, labels: list, threshold: float) -> Callable[[str], str]:
    """Union-find over the merges at or below `threshold`; returns the
    find function. A known topic label is always a leaf, since a label
    like "node-3" can collide with an internal id (as graph.js)."""
    is_leaf = set(labels)
    parent = {label: label for label in labels}

    def find(label: str) -> str:
        while parent[label] != label:
            parent[label] = parent[parent[label]]
            label = parent[label]
        return label

    under: dict = {}

    def leaves_of(name: str) -> list:
        return [name] if name in is_leaf else under.get(name, [])

    for merge in hierarchy:
        members = leaves_of(merge["a"]) + leaves_of(merge["b"])
        under[merge["id"]] = members
        if merge["distance"] <= threshold:
            for label in members:
                a, b = find(members[0]), find(label)
                if a != b:
                    parent[b] = a
    return find


def cut_tree(hierarchy: list, topics: list, threshold: float) -> dict:
    """The cut: which group each topic lands in, with the app's group ids
    and labels. The app lengthens the `cluster-` prefix past colliding
    labels (#859); these ids stay internal, so the fixed prefix stays."""
    find = _join_below(hierarchy, [t["label"] for t in topics], threshold)
    by_root: dict = {}
    group_of: dict = {}
    groups: list = []
    for topic in topics:
        root = find(topic["label"])
        group = by_root.get(root)
        if group is None:
            group = by_root[root] = {"id": f"cluster-{len(groups)}", "members": [], "label": ""}
            groups.append(group)
        group["members"].append(topic["label"])
        group_of[topic["label"]] = group["id"]
    sizes = {t["label"]: t["size"] for t in topics}
    for group in groups:
        group["label"] = group_label(group["members"], sizes)
    return {"groups": groups, "group_of": group_of}


def threshold_for_groups(hierarchy: list, topics: list, target: int) -> float:
    """The threshold yielding as close to `target` groups as the tree
    allows; an unreachable target returns the nearest cut honestly."""
    best = 0.0
    best_miss = abs(len(topics) - target)
    for merge in hierarchy:
        miss = abs(len(cut_tree(hierarchy, topics, merge["distance"])["groups"]) - target)
        if miss < best_miss:
            best_miss, best = miss, merge["distance"]
    return best


def build_groups(graph: dict, target: int) -> dict:
    """The cut nearest `target` groups: target, count actually reached,
    distance cut at, and the groups with the app's labels."""
    topics = graph["topics"]
    threshold = threshold_for_groups(graph["hierarchy"], topics, target)
    cut = cut_tree(graph["hierarchy"], topics, threshold)
    return {
        "target": target,
        "reached": len(cut["groups"]),
        "threshold": threshold,
        "groups": [{"label": g["label"], "members": g["members"]} for g in cut["groups"]],
    }


def render_groups(data: dict) -> str:
    lines = [
        f"{data['reached']} groups"
        + ("" if data["reached"] == data["target"] else f" (asked for {data['target']})")
        + f", cut at merge distance {data['threshold']:g}",
        "",
    ]
    for group in data["groups"]:
        lines.append(group["label"])
        for member in group["members"]:
            lines.append(f"  {member}")
    return "\n".join(lines)

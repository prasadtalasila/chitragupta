"""`discover --groups N`: the merge-tree cut's terminal twin (#709).

The app opens on a cut of the stored `hierarchy` and gives the reader a
resolution slider over it (`assets/webapp/graph.js`: cutTree,
groupLabel, thresholdForGroups). This module is the same three
functions on the same array -- a cut of a *stored* tree, so it derives
no partition the artefact does not already carry, and needs no contract
change. `tests/webapp/cut_cases.json` pins the two implementations to
each other: the node suite asserts graph.js reproduces every row,
tests/test_discover_groups.py asserts this module does.

One representational difference, deliberate: the app payload gives each
topic a `members` array and groupLabel reads its length, while the
graph artefact stores the count as `size` -- so the functions here read
`size`, and the shared case file carries `size` for both (the node test
synthesizes members arrays of that length).
"""


def group_label(members: list, sizes: dict) -> str:
    """The topic carrying the most papers leads and the rest are
    counted -- never a name this side invented, exactly graph.js's
    rule, ties broken alphabetically like its comparator."""
    if len(members) == 1:
        return members[0]
    lead = min(members, key=lambda label: (-sizes.get(label, 0), label))
    return f"{lead} +{len(members) - 1}"


def cut_tree(hierarchy: list, topics: list, threshold: float) -> dict:
    """Union-find over the merges at or below `threshold`, internal ids
    resolved back to the leaves underneath them. A topic could be
    labelled "node-3" and collide with an internal id, so a name that
    is a known topic label is always a leaf -- the same hardening
    graph.js carries."""
    labels = [t["label"] for t in topics]
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
    allows. The target is a target: a tree that never joins an outlying
    topic cannot reach one group, and says so by returning the nearest
    cut rather than pretending."""
    best = 0.0
    best_miss = abs(len(topics) - target)
    for merge in hierarchy:
        miss = abs(len(cut_tree(hierarchy, topics, merge["distance"])["groups"]) - target)
        if miss < best_miss:
            best_miss, best = miss, merge["distance"]
    return best


def build_groups(graph: dict, target: int) -> dict:
    """The cut nearest `target` groups, in one machine-readable shape:
    the target asked for, the count actually reached (the app is honest
    that they can differ, and so is this), the distance cut at, and the
    groups with the app's own labels."""
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

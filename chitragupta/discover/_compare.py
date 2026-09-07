"""`discover --compare A B [C ...]`: set comparison across topics (#715).

In the app this answer is the composition of chips, hop rings and
shared-paper evidence; the terminal gets it as one view -- each pair's
shared citekeys, the papers held by every named topic, the bridge
papers held by at least two (with their formatted ledger entries, which
the app payload cannot even carry), and the mutual edges of both
families with their evidence. Pure reading of `topic_set.json` members
and the stored edge lists; nothing here derives a relation.
"""

import itertools

from chitragupta.discover import _data

# The same honesty the app's paper expansion shows at its cap of three:
# a comparison over more topics than a person can hold is refused with
# the limit named, not quietly truncated.
CAP = 6


def build_compare(labels: list, graph: dict, topic_set: dict) -> dict:
    members = {
        t["label"]: {m["citekey"] for m in t["members"]}
        for t in topic_set["topics"]
        if t["label"] in labels
    }
    counts: dict = {}
    for label in labels:
        for citekey in members[label]:
            counts.setdefault(citekey, []).append(label)
    bridging = sorted(citekey for citekey, holders in counts.items() if len(holders) >= 2)
    entries = _data.entries_for(bridging)
    return {
        "topics": labels,
        "pairs": [
            {"a": a, "b": b, "shared": sorted(members[a] & members[b])}
            for a, b in itertools.combinations(labels, 2)
        ],
        "intersection": sorted(set.intersection(*(members[label] for label in labels))),
        "union": len(set.union(*(members[label] for label in labels))),
        "bridges": [
            {"citekey": citekey, "topics": counts[citekey], "entry": entries[citekey]}
            for citekey in bridging
        ],
        "edges": _mutual_edges(graph, set(labels)),
    }


def _mutual_edges(graph: dict, labels: set) -> dict:
    """Both families' edges whose two ends are both named -- each with
    its own evidence, never fused, exactly as the topic view lists
    them."""
    return {
        "overlap": [edge for edge in graph["edges_overlap"] if {edge["a"], edge["b"]} <= labels],
        "semantic": [edge for edge in graph["edges_semantic"] if {edge["a"], edge["b"]} <= labels],
    }


def render_compare(data: dict) -> str:
    lines = [" — ".join(data["topics"]), ""]
    lines.append(f"union: {data['union']} papers")
    held = ", ".join(data["intersection"]) or "none"
    lines.append(f"held by all {len(data['topics'])}: {held}")
    lines += ["", "pairwise shared papers:"]
    for pair in data["pairs"]:
        shared = f"{len(pair['shared'])}: {', '.join(pair['shared'])}" if pair["shared"] else "none"
        lines.append(f"  {pair['a']} & {pair['b']}: {shared}")
    lines += ["", "bridge papers (in two or more of the named topics):"]
    if not data["bridges"]:
        lines.append("  none")
    for bridge in data["bridges"]:
        lines.append(f"  {bridge['entry']}")
        lines.append(f"    in: {', '.join(bridge['topics'])}")
    lines += ["", "edges among the named topics:"]
    for edge in data["edges"]["overlap"]:
        lines.append(
            f"  shared members: {edge['a']} & {edge['b']}  "
            f"(overlap {edge['overlap_coeff']:.2f}, via: {', '.join(edge['shared'])})"
        )
    for edge in data["edges"]["semantic"]:
        lines.append(
            f"  semantically near: {edge['a']} & {edge['b']}  "
            f"({edge['similarity']:.2f}, bridge: {edge['bridge'][0]} <-> {edge['bridge'][1]})"
        )
    if not data["edges"]["overlap"] and not data["edges"]["semantic"]:
        lines.append("  none above the graph's floors")
    return "\n".join(lines)

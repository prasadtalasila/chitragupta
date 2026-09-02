"""The three discovery views, each built once as data and rendered
twice -- prose for a terminal, the same dict for `--json` -- so the two
outputs cannot disagree about what was found.

Rendering shows relations; it derives none. Every number and every
citekey below comes from an artefact a stage wrote or a ledger row a
sync recorded.
"""

from chitragupta.discover import _data


def build_list(graph: dict, topic_set: dict, terms: dict) -> dict:
    return {
        "n_docs": graph["n_docs"],
        "topics": [
            {
                "label": node["label"],
                "provenance": node["provenance"],
                "size": node["size"],
                "terms": terms.get(node["label"], []),
            }
            for node in graph["topics"]
        ],
        "uncovered": topic_set.get("uncovered", []),
    }


def render_list(data: dict) -> str:
    lines = [f"{len(data['topics'])} topics over {data['n_docs']} papers", ""]
    width = max((len(t["label"]) for t in data["topics"]), default=0)
    for topic in data["topics"]:
        terms = f"  [{', '.join(topic['terms'])}]" if topic["terms"] else ""
        lines.append(
            f"  {topic['label']:<{width}}  {topic['provenance']:<8} "
            f"{topic['size']:>3} papers{terms}"
        )
    if data["uncovered"]:
        lines += ["", f"uncovered by any topic: {', '.join(data['uncovered'])}"]
    return "\n".join(lines)


def _linked(graph: dict, label: str) -> dict:
    """Both edge families touching `label`, each keeping its own
    evidence -- shared citekeys on one side, the bridging pair on the
    other -- and never merged into a single score."""
    overlap = [
        {
            "label": edge["b"] if edge["a"] == label else edge["a"],
            "jaccard": edge["jaccard"],
            "overlap_coeff": edge["overlap_coeff"],
            "shared": edge["shared"],
        }
        for edge in graph["edges_overlap"]
        if label in (edge["a"], edge["b"])
    ]
    semantic = [
        {
            "label": edge["b"] if edge["a"] == label else edge["a"],
            "similarity": edge["similarity"],
            "bridge": edge["bridge"],
        }
        for edge in graph["edges_semantic"]
        if label in (edge["a"], edge["b"])
    ]
    return {"overlap": overlap, "semantic": semantic}


def _graph_node(graph: dict, label: str) -> dict:
    """The graph's node for a topic-set label, or the refusal that names
    the drift: the two artefacts are written by different stages, and one
    re-run without the other leaves labels only one of them knows."""
    node = next((t for t in graph["topics"] if t["label"] == label), None)
    if node is None:
        raise _data.MissingArtefact(
            f"topic_graph.json does not know the topic {label!r} -- the graph is "
            "stale against topic_set.json; re-run `python -m chitragupta.enrich "
            "--stages topic-graph`."
        )
    return node


def build_topic(label: str, graph: dict, topic_set: dict, terms: dict) -> dict:
    node = _graph_node(graph, label)
    members = _data.members_of(topic_set)[label]
    by_paper = _data.topics_of(topic_set)
    entries = _data.entries_for([m["citekey"] for m in members])
    return {
        "topic": {
            "label": label,
            "provenance": node["provenance"],
            "size": node["size"],
            "terms": terms.get(label, []),
        },
        "members": [
            {
                "citekey": m["citekey"],
                "score": m["score"],
                "entry": entries[m["citekey"]],
                "topics": [
                    t["label"] for t in by_paper.get(m["citekey"], []) if t["label"] != label
                ],
            }
            for m in members
        ],
        "linked": _linked(graph, label),
    }


def render_topic(data: dict) -> str:
    topic = data["topic"]
    lines = [
        f"{topic['label']}  ({topic['provenance']}, {topic['size']} papers)",
    ]
    if topic["terms"]:
        lines.append(f"terms: {', '.join(topic['terms'])}")
    lines.append("")
    for member in data["members"]:
        lines.append(f"  [{member['score']:.2f}] {member['entry']}")
        if member["topics"]:
            lines.append(f"         also in: {', '.join(member['topics'])}")
    lines += ["", "linked topics:"]
    for edge in data["linked"]["overlap"]:
        lines.append(
            f"  shared members: {edge['label']}  "
            f"(jaccard {edge['jaccard']:.2f}, overlap {edge['overlap_coeff']:.2f}, "
            f"via: {', '.join(edge['shared'])})"
        )
    for edge in data["linked"]["semantic"]:
        lines.append(
            f"  semantically near: {edge['label']}  "
            f"({edge['similarity']:.2f}, bridge: {edge['bridge'][0]} <-> {edge['bridge'][1]})"
        )
    if not data["linked"]["overlap"] and not data["linked"]["semantic"]:
        lines.append("  none above the graph's floors")
    return "\n".join(lines)


def build_paper(citekey: str, topic_set: dict) -> "dict | None":
    by_paper = _data.topics_of(topic_set)
    if citekey not in by_paper:
        return None
    entries = _data.entries_for([citekey])
    return {
        "citekey": citekey,
        "entry": entries[citekey],
        "topics": by_paper[citekey],
    }


def render_paper(data: dict) -> str:
    lines = [data["entry"], "", "topics:"]
    for topic in data["topics"]:
        lines.append(f"  [{topic['score']:.2f}] {topic['label']}")
    return "\n".join(lines)


def build_search(phrase: str, results: list, topic_set: dict) -> dict:
    """The fallback view, labelled as what it is: paper search, not a
    topic membership -- with each hit still annotated by its topics so
    the reader can step from a hit back onto the graph."""
    by_paper = _data.topics_of(topic_set)
    return {
        "resolved_via": "search",
        "query": phrase,
        "results": [
            {
                "citekey": r.citekey,
                "title": r.title,
                "score": r.score,
                "snippet": r.snippet,
                "topics": by_paper.get(r.citekey, []),
            }
            for r in results
        ],
    }


def render_search(data: dict) -> str:
    lines = [
        f"no topic matched {data['query']!r} -- falling back to paper search "
        "(these are retrieval hits, not topic memberships):",
        "",
    ]
    for result in data["results"]:
        lines.append(f"  [{result['score']:.2f}] {result['citekey']} -- {result['title']}")
        if result["topics"]:
            labels = ", ".join(t["label"] for t in result["topics"])
            lines.append(f"         topics: {labels}")
    return "\n".join(lines)

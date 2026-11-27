"""`corpus discover --html FILE`: the topic graph as one static page.

A pure renderer of the terminal views' artefacts, so it can never
disagree with `--json`; self-contained (inline payload, CSS, JS, no
network), so it keeps working from `file://`. A `--html` flag, not a
`discover graph` subcommand, which would shadow a topic labelled "graph".
"""

import json

from chitragupta import ledger
from chitragupta.discover import _data, _origin, _page_template


def build_payload(graph: dict, topic_set: dict, terms: dict) -> dict:
    """Everything the page shows, joined once: each graph node with its
    members (citekey, ledger title, score), its terms and its linked
    topics, plus both raw edge lists and the stored hierarchy."""
    titles = _titles(topic_set)
    members_by_label = _data.members_of(topic_set)
    # A node the topic set does not know is artefact drift: refuse, as the
    # terminal views do, rather than render a plausible empty page.
    strays = [n["label"] for n in graph["topics"] if n["label"] not in members_by_label]
    if strays:
        raise _data.MissingArtefact(
            f"topic_set.json does not know the topics {', '.join(sorted(strays))} -- "
            "the artefacts have drifted; re-run `python -m chitragupta.enrich "
            "--stages converge,topic-graph`."
        )
    topics = []
    for node in graph["topics"]:
        members = members_by_label[node["label"]]
        topics.append(
            {
                "label": node["label"],
                "provenance": node["provenance"],
                # Stored brokerage (#713); an older artefact has none and
                # the app computes it in the browser.
                **({"analysis": node["analysis"]} if "analysis" in node else {}),
                "terms": terms.get(node["label"], []),
                "members": [
                    {
                        "citekey": m["citekey"],
                        "title": titles.get(m["citekey"], ""),
                        "score": m["score"],
                    }
                    for m in members
                ],
                "linked": _linked(graph, node["label"]),
            }
        )
    return {
        "n_docs": graph["n_docs"],
        "topics": topics,
        "edges_overlap": graph["edges_overlap"],
        # The gate's refused pairs (#710, §7.7), so the app's absence
        # verdict reads the stage's number. .get for older artefacts.
        "edges_withheld": graph.get("edges_withheld", []),
        "edges_semantic": graph["edges_semantic"],
        "hierarchy": graph["hierarchy"],
        # Papers no topic holds (#717). .get for older artefacts.
        "uncovered": topic_set.get("uncovered", []),
        # Stored MCL partitions (#712); empty for an older artefact, and
        # the app then clusters in the browser.
        "communities": graph.get("communities", {}),
        # Stored next-hop matrices (#714), so a path is a walk; empty for
        # an older artefact, and the app runs its own Dijkstra.
        "paths": graph.get("paths", {}),
    }


def _titles(topic_set: dict) -> dict:
    citekeys = sorted({m["citekey"] for topic in topic_set["topics"] for m in topic["members"]})
    if not citekeys:
        return {}
    con = _data.read_only_connection()
    try:
        return dict(ledger.rows_for_citekeys(con, "citekey, title", citekeys))
    finally:
        con.close()


def _linked(graph: dict, label: str) -> dict:
    # Imported to keep one definition of "the edges touching X".
    from chitragupta.discover import _render  # pylint: disable=import-outside-toplevel

    return _render._linked(graph, label)


def dendrogram_order(hierarchy: list, labels: list) -> list:
    """The stored merge tree's leaf order: a depth-first walk of the
    roots, closest merges nested deepest, so neighbours are similar.

    Labels the tree omits (topics without a vector) follow in payload
    order. A known topic label is a leaf first, since merge ids
    (`node-N`) can collide with free-text labels (cf. #636). The
    template's `tree()` walks the tree again for its DOM; the order is
    computed here because the inline script is untested by coverage.
    """
    children = {merge["id"]: (merge["a"], merge["b"]) for merge in hierarchy}
    known = set(labels)
    merged = {end for merge in hierarchy for end in (merge["a"], merge["b"])}
    ordered: list = []
    seen: set = set()
    stack = [merge["id"] for merge in reversed(hierarchy) if merge["id"] not in merged]
    while stack:
        name = stack.pop()
        if name in known:
            if name not in seen:
                seen.add(name)
                ordered.append(name)
        elif name in children:
            stack.extend(reversed(children[name]))
    ordered.extend(label for label in labels if label not in seen)
    return ordered


def build_html(payload: dict) -> str:
    """The finished page. `<` is escaped in the embedded JSON so no
    title or label can close the script tag early.

    Topics are embedded in dendrogram order (the template lays them round
    the circle as received), ordered here and non-destructively, because
    `_app.build_app_payload` shares the join and draws its own layouts
    (#688).
    """
    ordered = dendrogram_order(payload["hierarchy"], [t["label"] for t in payload["topics"]])
    by_label = {topic["label"]: topic for topic in payload["topics"]}
    page = {**payload, "topics": [by_label[label] for label in ordered]}
    embedded = json.dumps(page).replace("<", "\\u003c")
    return _page_template.TEMPLATE.replace("__PAYLOAD__", embedded)


def write_page(path: str, origins: "set | None" = None) -> str:
    """Build the payload from the artefacts on disk and write the page.
    Raises `_data.MissingArtefact` for every absent input, like the
    terminal views.

    `origins` (#742) filters the artefacts before the join, so a shipped
    page is honest about its contents."""
    graph, topic_set = _origin.keep(
        _data.load_graph(), _data.load_topic_set(), origins or set(_origin.CLASSES)
    )
    terms = _data.top_terms(topic_set)
    html = build_html(build_payload(graph, topic_set, terms))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)
    return path

"""`corpus discover --html FILE`: the topic graph as one static page.

A pure renderer of the same artefacts the terminal views read -- it
derives no edge and no membership, so the page can never disagree with
`--json`. Self-contained by construction: the payload is embedded as a
JSON script tag, the CSS and JavaScript are inline in the template, and
nothing on the page references the network, so the file keeps working
from `file://` after the corpus that produced it has moved on.

The plan named this `discover graph --out`; it shipped as a `--html`
flag instead, because a positional subcommand would shadow any topic
literally labelled "graph" -- the reader's positional argument is a
free phrase, and carving reserved words out of it would be a worse
contract than a flag.
"""

import json

from chitragupta import ledger
from chitragupta.discover import _data, _page_template


def build_payload(graph: dict, topic_set: dict, terms: dict) -> dict:
    """Everything the page shows, joined once: each graph node with its
    members (citekey, ledger title, score), its terms and its linked
    topics, plus both raw edge lists and the stored hierarchy."""
    titles = _titles(topic_set)
    members_by_label = _data.members_of(topic_set)
    # A graph node the topic set does not know is artefact drift (one
    # stage re-run without the other), and the page must refuse exactly
    # as the terminal views do -- an empty member list would render a
    # plausible-looking page that disagrees with `--json`.
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
                # Stored brokerage (#713), forwarded so the panel can read
                # the artefact; an older artefact simply has none and the
                # app computes in the browser as before.
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
        # The pairs the gate refused (#710, §7.7): stored beside the
        # edges it drew, so the app's absence verdict reads the stage's
        # own number instead of recomputing it. .get because an artefact
        # from an older run predates the field.
        "edges_withheld": graph.get("edges_withheld", []),
        "edges_semantic": graph["edges_semantic"],
        "hierarchy": graph["hierarchy"],
        # The seed phrases no topic covers. The terminal list view has
        # always reported these (#717 gave the exported views the same
        # honesty); .get because an artefact from an older converge run
        # may predate the field.
        "uncovered": topic_set.get("uncovered", []),
        # The stored MCL partitions (#712), one assignment array per
        # slider inflation per family; empty for an older artefact and
        # the app then clusters in the browser as before.
        "communities": graph.get("communities", {}),
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
    # Not _render._linked re-used blindly: the page wants the same shape,
    # and importing it keeps one definition of "the edges touching X".
    from chitragupta.discover import _render  # pylint: disable=import-outside-toplevel

    return _render._linked(graph, label)


def dendrogram_order(hierarchy: list, labels: list) -> list:
    """The stored merge tree's leaf order: a depth-first walk of the
    roots (the merges nothing else merged), closest merges nested
    deepest, so adjacent positions in the result hold similar topics.

    Labels the tree does not mention keep their payload order and follow
    the leaves. That is not a fallback for a state that cannot occur:
    `topic_graph.hierarchy` is built over the topics that had a vector,
    and is empty entirely for a corpus with fewer than two of them.

    A name that is a known topic label is a leaf before it is anything
    else. Merge ids are `node-N` and a topic label is free text, so the
    two can collide -- the same class of hazard as #636's `__proto__`,
    and consulting the tree first would swallow the real topic.

    The template's `tree()` walks the same merge tree, and that is a
    deliberate second walk rather than an oversight: it builds the
    panel's collapsible DOM, which belongs in the page, while this
    returns an order, which has to be in Python because nothing executes
    the template's inline script and the coverage bar is 100%.
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
    title or label can close the script tag early -- the one injection
    route a static JSON island has.

    The topics are embedded in dendrogram leaf order, because the
    template lays them round the circle in the order it receives them.
    Ordered here rather than in `build_payload` so the order stays the
    page's own: `_app.build_app_payload` shares that join, and the app
    draws its own layouts (#688). Non-destructive for the same reason --
    a caller's payload is not the page's to reorder.
    """
    ordered = dendrogram_order(payload["hierarchy"], [t["label"] for t in payload["topics"]])
    by_label = {topic["label"]: topic for topic in payload["topics"]}
    page = {**payload, "topics": [by_label[label] for label in ordered]}
    embedded = json.dumps(page).replace("<", "\\u003c")
    return _page_template.TEMPLATE.replace("__PAYLOAD__", embedded)


def write_page(path: str) -> str:
    """Build the payload from the artefacts on disk and write the page.
    Raises `_data.MissingArtefact` for every absent input, exactly like
    the terminal views, so the CLI boundary translates it the same way."""
    graph = _data.load_graph()
    topic_set = _data.load_topic_set()
    terms = _data.top_terms(topic_set)
    html = build_html(build_payload(graph, topic_set, terms))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)
    return path

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
        "edges_semantic": graph["edges_semantic"],
        "hierarchy": graph["hierarchy"],
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


def build_html(payload: dict) -> str:
    """The finished page. `<` is escaped in the embedded JSON so no
    title or label can close the script tag early -- the one injection
    route a static JSON island has."""
    embedded = json.dumps(payload).replace("<", "\\u003c")
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

"""`discover --why A B`: why there is *no* overlap edge here.

The terminal twin of `assets/webapp/absence.js`, plus the gate's own
threshold. The tail must match `enrich/topic_graph.py`'s
`hypergeom.sf(k - 1, n_docs, |A|, |B|)` and the browser:
`tests/webapp/hypergeometric_cases.js` is the three-way contract.
stdlib `math.lgamma`, not scipy, so it answers on a base install.
"""

from math import exp, inf, lgamma

# The gate's documented default (docs/TOPIC-DISCOVERY.md), only for an
# artefact predating stored `p_value`, as absence.js assumes.
DEFAULT_THRESHOLD = 0.01


def _log_choose(n: int, k: int) -> float:
    if k < 0 or k > n:
        return -inf
    return lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1)


def survival(k: int, docs: int, a: int, b: int) -> float:
    """P(X >= k) for X hypergeometric: the chance that topics of size
    `a` and `b` share at least `k` of `docs` papers at random. Log space,
    because 171! overflows a double."""
    least = max(0, a + b - docs)
    most = min(a, b)
    if k <= least:
        return 1.0
    if k > most:
        return 0.0
    denominator = _log_choose(docs, b)
    total = 0.0
    for i in range(k, most + 1):
        total += exp(_log_choose(a, i) + _log_choose(docs - a, b - i) - denominator)
    return min(1.0, total)


def _stored_edge(graph: dict, a: str, b: str) -> dict | None:
    for edge in graph["edges_overlap"]:
        if {edge["a"], edge["b"]} == {a, b}:
            return edge
    return None


def _stored_withheld(graph: dict, a: str, b: str) -> dict | None:
    for row in graph.get("edges_withheld", []):
        if {row["a"], row["b"]} == {a, b}:
            return row
    return None


def explain(graph: dict, topic_set: dict, a: str, b: str) -> dict:
    """The verdict for one pair, in absence.js's `explain` shape plus the
    stored threshold and a named verdict. A drawn edge reports its stored
    `p`: the stage's number is the claim, and recomputing could only
    agree or lie."""
    members = {t["label"]: {m["citekey"] for m in t["members"]} for t in topic_set["topics"]}
    shared = sorted(members[a] & members[b])
    sizes = {"a": len(members[a]), "b": len(members[b])}
    docs = graph["n_docs"]
    threshold = graph.get("p_value", DEFAULT_THRESHOLD)
    edge = _stored_edge(graph, a, b)
    if edge is not None:
        p = edge["p_value"]
        verdict = "drawn"
    elif not shared:
        p = None
        verdict = "nothing-shared"
    else:
        # Prefer the stored number (#710); recompute only for older
        # artefacts, as absence.js does.
        withheld = _stored_withheld(graph, a, b)
        p = withheld["p_value"] if withheld else survival(len(shared), docs, sizes["a"], sizes["b"])
        verdict = "withheld-chance" if p >= threshold else "withheld-unexplained"
    return {
        "a": a,
        "b": b,
        "shared": shared,
        "p": p,
        "sizes": sizes,
        "docs": docs,
        "drawn": edge is not None,
        "threshold": threshold,
        "verdict": verdict,
    }


def render(data: dict) -> str:
    """The panel's three sentences (panel.js absenceHtml), plus the
    drawn case, kept separate so the readings are not run together."""
    heading = f"{data['a']} — {data['b']}\n"
    count = f"{len(data['shared'])} paper{'s' if len(data['shared']) != 1 else ''}"
    citekeys = ", ".join(data["shared"])
    if data["verdict"] == "drawn":
        return heading + (
            f"The graph carries an overlap edge between these: {count} shared"
            f" ({citekeys}), p = {data['p']:.2e} against the gate's"
            f" threshold of {data['threshold']}."
        )
    if data["verdict"] == "nothing-shared":
        return heading + (
            "These topics share no papers at all, so the overlap test had"
            " nothing to weigh. Any relation between them would have to"
            " come from the semantic family."
        )
    if data["verdict"] == "withheld-chance":
        return heading + (
            f"These share {citekeys}, but sharing {count} between topics of"
            f" size {data['sizes']['a']} and {data['sizes']['b']} in a"
            f" {data['docs']}-paper corpus is what chance predicts"
            f" (p = {data['p']:.2f}, against a threshold of"
            f" {data['threshold']}), so no edge was drawn."
        )
    return heading + (
        f"These share {citekeys} — {count} between topics of size"
        f" {data['sizes']['a']} and {data['sizes']['b']} in a"
        f" {data['docs']}-paper corpus, which chance does not readily"
        f" explain (p = {data['p']:.1e}, below the artefact's own"
        f" threshold of {data['threshold']}) — yet the graph carries no"
        " edge. The artefact disagrees with itself; it was likely built"
        " by an older run, and `chitragupta enrich` would settle it."
    )

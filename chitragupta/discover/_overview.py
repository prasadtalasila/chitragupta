"""The `--out` overview: one topic as a Markdown file a draft can grow
from.

Extractive, never abstractive: a summary asserting a claim no paper
made is the fabricated citekey's failure class (Theme G). It only
*selects* ledger entries, stage-derived links and verbatim sentences
with their citekeys; nothing is paraphrased.
"""

from typing import Any

from chitragupta import config, ledger, ledger_paths, sentences
from chitragupta.discover import _data, _resolve

# Quote count and sentence length band: shorter is fragments and page
# furniture, longer stops being quotable.
SNIPPET_COUNT = 5
_SENTENCE_BOUNDS = (40, 400)


def _load_model() -> "Any":
    """Isolated so tests fake it; the import is paid only when an
    overview is written."""
    from sentence_transformers import SentenceTransformer  # pylint: disable=import-outside-toplevel

    return SentenceTransformer(config.EMBEDDING_MODEL)


def _parsed_texts(citekeys: list) -> dict:
    # Guarded: sqlite rejects an empty "IN ()" as a syntax error.
    if not citekeys:
        return {}
    con = _data.read_only_connection()
    try:
        rows = ledger.rows_for_citekeys(con, "citekey, parsed_path", citekeys)
    finally:
        con.close()
    texts = {}
    for citekey, parsed_path in rows:
        # Relative to `config.PARSED_DIR` (#966), and confined to it before
        # it is opened -- issue 821.
        parsed = ledger_paths.parsed_file(parsed_path)
        if parsed and parsed.exists():
            texts[citekey] = parsed.read_text(encoding="utf-8")
    return texts


def _candidate_sentences(texts: dict) -> list:
    """Every member sentence inside `_SENTENCE_BOUNDS`, split by
    `chitragupta/sentences.py`'s rule (#895): a local regex lacked its
    abbreviation guards and cut "et al." citations mid-sentence."""
    low, high = _SENTENCE_BOUNDS
    return [
        (citekey, sentence)
        for citekey, text in sorted(texts.items())
        for sentence in sentences.split(text)
        if low <= len(sentence) <= high
    ]


def snippets(members: list, graph: dict, label: str) -> "list | None":
    """The topic's most representative sentences, verbatim with their
    citekeys, ranked by cosine to the centroid in the graph's centred
    space. `None` (not "no candidates") when the extra or model is
    unavailable (#977), so the caller can say what is missing."""
    from chitragupta.discover import _render  # pylint: disable=import-outside-toplevel

    centroid = _render._graph_node(graph, label).get("centroid") or []
    if not centroid:
        return []
    candidates = _candidate_sentences(_parsed_texts([m["citekey"] for m in members]))
    if not candidates:
        return []
    model, _note = _resolve.optional_model(_load_model, "snippets")
    if model is None:
        return None
    vectors = model.encode([sentence for _, sentence in candidates], show_progress_bar=False)
    scored = [
        (_data.centred_cosine(vector, graph["corpus_mean"], centroid), citekey, sentence)
        for (citekey, sentence), vector in zip(candidates, vectors)
    ]
    scored.sort(key=lambda row: (-row[0], row[1], row[2]))
    return [
        {"citekey": citekey, "sentence": sentence, "score": cosine}
        for cosine, citekey, sentence in scored[:SNIPPET_COUNT]
    ]


def _linked_lines(linked: dict) -> list:
    """The linked-topics bullet lines, both families with evidence, or
    an explicit "none"."""
    lines = [
        f"- {edge['label']} -- shared members "
        f"(jaccard {edge['jaccard']:.2f}, overlap {edge['overlap_coeff']:.2f}, "
        f"via {', '.join(edge['shared'])})"
        for edge in linked["overlap"]
    ] + [
        f"- {edge['label']} -- semantically near "
        f"({edge['similarity']:.2f}, bridge {edge['bridge'][0]} <-> {edge['bridge'][1]})"
        for edge in linked["semantic"]
    ]
    return lines or ["- none above the graph's floors"]


def build_markdown(data: dict, quoted: "list | None") -> str:
    """The overview file: the topic view's own data plus the verbatim
    snippets, in Markdown a genre skill (or a human) can quarry."""
    topic = data["topic"]
    lines = [
        f"# {topic['label']}",
        "",
        f"A {topic['provenance']} topic covering {topic['size']} papers.",
    ]
    if topic["terms"]:
        lines.append(f"Characteristic terms: {', '.join(topic['terms'])}.")
    lines += ["", "## Papers", ""]
    for member in data["members"]:
        lines.append(f"- [{member['score']:.2f}] {member['entry']}")
        if member["topics"]:
            lines.append(f"  - also in: {', '.join(member['topics'])}")
    lines += ["", "## Linked topics", "", *_linked_lines(data["linked"])]
    lines += ["", "## Representative snippets", ""]
    if quoted is None:
        lines.append(
            "Snippet selection unavailable: the enrich extra is not installed or "
            "its embedding model would not load, and quoting cannot be ranked without it."
        )
    elif not quoted:
        lines.append("No member paper has parsed text to quote from.")
    else:
        for snippet in quoted:
            lines.append(f"> {snippet['sentence']}")
            lines.append(f">   -- `{snippet['citekey']}`")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"

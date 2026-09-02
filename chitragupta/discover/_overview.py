"""The `--out` overview: one topic as a Markdown file a draft can grow
from.

Extractive, never abstractive, and that is a boundary rather than a
style: Theme G's roadmap declines abstractive topic summaries because a
summary asserting a claim no paper made is the fabricated citekey's
failure class wearing different clothes. So the overview *selects* --
member entries the ledger already holds, linked topics a stage already
derived, and representative sentences quoted verbatim from member
papers' parsed text with their citekeys attached. Nothing here is
paraphrased.
"""

import re
import sqlite3
from typing import Any

from chitragupta import config

# How many verbatim sentences the overview quotes, and the length band a
# candidate sentence must fall in -- below it fragments and page furniture
# dominate, above it block quotes stop being quotable.
SNIPPET_COUNT = 5
_SENTENCE_BOUNDS = (40, 400)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _load_model() -> "Any":
    """Isolated so tests fake it; the import is paid only when an
    overview is actually written."""
    from sentence_transformers import SentenceTransformer  # pylint: disable=import-outside-toplevel

    return SentenceTransformer(config.EMBEDDING_MODEL)


def _parsed_texts(citekeys: list) -> dict:
    con = sqlite3.connect(f"file:{config.LEDGER_PATH}?mode=ro", uri=True, timeout=5.0)
    try:
        placeholders = ",".join("?" * len(citekeys))
        rows = con.execute(
            f"SELECT citekey, parsed_path FROM items WHERE citekey IN ({placeholders})",
            citekeys,
        ).fetchall()
    finally:
        con.close()
    texts = {}
    for citekey, parsed_path in rows:
        if parsed_path and config.PROJECT_ROOT.joinpath(parsed_path).exists():
            texts[citekey] = config.PROJECT_ROOT.joinpath(parsed_path).read_text(encoding="utf-8")
    return texts


def _candidate_sentences(texts: dict) -> list:
    low, high = _SENTENCE_BOUNDS
    return [
        (citekey, sentence.strip())
        for citekey, text in sorted(texts.items())
        for sentence in _SENTENCE_SPLIT.split(text)
        if low <= len(sentence.strip()) <= high
    ]


def snippets(members: list, graph: dict, label: str) -> "list | None":
    """The topic's most representative sentences, verbatim with their
    citekeys: candidates from every member's parsed text, ranked by
    cosine to the topic centroid in the same centred space the graph
    stage stored. `None` -- distinct from "no candidates" -- when the
    enrich extra is absent, so the caller can say what is missing."""
    node = next(t for t in graph["topics"] if t["label"] == label)
    centroid = node.get("centroid") or []
    if not centroid:
        return []
    candidates = _candidate_sentences(_parsed_texts([m["citekey"] for m in members]))
    if not candidates:
        return []
    try:
        model = _load_model()
    except ImportError:
        return None
    vectors = model.encode([sentence for _, sentence in candidates], show_progress_bar=False)
    mean = graph["corpus_mean"]
    c_norm = sum(v * v for v in centroid) ** 0.5 or 1.0
    scored = []
    for (citekey, sentence), vector in zip(candidates, vectors):
        centred = [float(v) - m for v, m in zip(vector, mean)]
        norm = sum(v * v for v in centred) ** 0.5 or 1.0
        cosine = sum(a * b for a, b in zip(centred, centroid)) / (norm * c_norm)
        scored.append((cosine, citekey, sentence))
    scored.sort(key=lambda row: (-row[0], row[1], row[2]))
    return [
        {"citekey": citekey, "sentence": sentence, "score": cosine}
        for cosine, citekey, sentence in scored[:SNIPPET_COUNT]
    ]


def _linked_lines(linked: dict) -> list:
    """The linked-topics section's bullet lines, both families with
    their evidence, or the explicit "none" a reader can trust."""
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
            "Snippet selection unavailable: the enrich extra is not installed, "
            "and quoting cannot be ranked without it."
        )
    elif not quoted:
        lines.append("No member paper has parsed text to quote from.")
    else:
        for snippet in quoted:
            lines.append(f"> {snippet['sentence']}")
            lines.append(f">   -- `{snippet['citekey']}`")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"

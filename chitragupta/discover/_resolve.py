"""The resolution ladder: from a free phrase to a topic that exists.

Four rungs, best first, and the result names which one fired
(`resolved_via`), because "which mechanism answered" is the difference
between a topic membership and a plausible guess:

1. **exact** -- case-insensitive equality against topic labels.
2. **fuzzy** -- `difflib` near-match, for typos and near-forms.
3. **hybrid** -- two rankings fused by Reciprocal Rank Fusion: BM25
   over each topic's own vocabulary (label + its c-TF-IDF terms)
   beside cosine of the query's embedding against the stored topic
   centroids. RRF (Cormack et al., 2009) is rank-based, so the two
   scores never need calibrating against each other -- the reason it
   was chosen over any weighted interpolation.
4. **search** -- nothing above answered; the caller falls back to
   `chitragupta.retrieval.search()` over papers, clearly labelled.

The semantic half of rung 3 needs the enrich extra. When it is absent
the rung degrades to BM25 alone and the resolution carries a note
saying so -- the same honest-degradation posture every enrich stage's
self-probe takes, never a silent substitution.
"""

import difflib
from dataclasses import dataclass

from chitragupta import config, retrieval

# Cormack et al. (2009)'s constant. Rank-based fusion: each ranking
# contributes 1/(k + rank), so agreement between the two rankers
# dominates without either one's raw scale mattering.
RRF_K = 60

# difflib's default cutoff (0.6) accepts matches a reader would call
# wrong ("digital twin" for "digital signal"); 0.75 keeps the rung to
# typos and near-forms, which is all a *lexical* rung should claim.
_FUZZY_CUTOFF = 0.75


@dataclass
class Resolution:
    """What the ladder decided: the winning label (None when the caller
    should fall back to paper search), the rung that fired, the ranked
    runner-up labels, the winning rung's own score where it has one, and
    a note when a rung degraded."""

    label: "str | None"
    via: str
    ranked: list
    score: "float | None" = None
    note: "str | None" = None


def exact_match(phrase: str, labels) -> "str | None":
    wanted = phrase.strip().lower()
    return next((label for label in labels if label.lower() == wanted), None)


def fuzzy_match(phrase: str, labels) -> "str | None":
    lowered = {label.lower(): label for label in labels}
    close = difflib.get_close_matches(phrase.strip().lower(), lowered, n=1, cutoff=_FUZZY_CUTOFF)
    return lowered[close[0]] if close else None


def topic_vocabulary(topic_set: dict, terms: dict) -> dict:
    """One small BM25 document per topic: its label plus its c-TF-IDF
    terms. The label is what a human calls the topic; the terms are what
    the corpus calls it -- a query matching either deserves the hit."""
    return {
        topic["label"]: " ".join([topic["label"], *terms.get(topic["label"], [])])
        for topic in topic_set["topics"]
    }


def bm25_ranking(phrase: str, vocab: dict) -> list:
    """`[(label, score), ...]` best first, positive scores only --
    scored by the same tokenizer and BM25 arithmetic the retrieval layer
    uses, so a term matches a topic exactly when it would match a paper."""
    index = {
        label: {"term_freqs": _freqs(text), "length": len(retrieval._tokenize(text))}
        for label, text in vocab.items()
    }
    scores = retrieval._bm25_scores(index, retrieval._query_terms(phrase))
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))


def _freqs(text: str) -> dict:
    freqs: dict = {}
    for token in retrieval._tokenize(text):
        freqs[token] = freqs.get(token, 0) + 1
    return freqs


def _load_model():
    """Isolated so tests fake it and so the import cost is paid only
    when the ladder actually reaches the semantic rung."""
    from sentence_transformers import SentenceTransformer  # pylint: disable=import-outside-toplevel

    return SentenceTransformer(config.EMBEDDING_MODEL)


def semantic_ranking(phrase: str, graph: dict) -> list:
    """`[(label, cosine), ...]` against the stored centroids, in the
    same mean-centred space the graph stage used -- the stored
    `corpus_mean` is what moves the query there without the embed cache."""
    model = _load_model()
    vector = model.encode(phrase, show_progress_bar=False)
    query = [float(v) - m for v, m in zip(vector, graph["corpus_mean"])]
    norm = sum(v * v for v in query) ** 0.5 or 1.0
    scored = []
    for topic in graph["topics"]:
        centroid = topic.get("centroid") or []
        if not centroid:
            continue
        c_norm = sum(v * v for v in centroid) ** 0.5 or 1.0
        cosine = sum(q * c for q, c in zip(query, centroid)) / (norm * c_norm)
        scored.append((topic["label"], cosine))
    return sorted(scored, key=lambda pair: (-pair[1], pair[0]))


def rrf_fuse(rankings: list) -> list:
    """Reciprocal Rank Fusion over plain label rankings:
    `score(l) = sum over rankings of 1/(RRF_K + rank)`."""
    fused: dict = {}
    for ranking in rankings:
        for rank, label in enumerate(ranking):
            fused[label] = fused.get(label, 0.0) + 1.0 / (RRF_K + rank + 1)
    return sorted(fused.items(), key=lambda pair: (-pair[1], pair[0]))


def resolve(
    phrase: str,
    graph: dict,
    topic_set: dict,
    terms: dict,
    min_similarity: "float | None" = None,
) -> Resolution:
    """Walk the ladder. `label is None` tells the caller to fall back to
    paper search -- the ladder itself never searches papers, so the
    fallback stays visibly a different thing in the output."""
    floor = config.DISCOVER_MIN_SIMILARITY if min_similarity is None else min_similarity
    labels = [topic["label"] for topic in topic_set["topics"]]

    found = exact_match(phrase, labels)
    if found:
        return Resolution(found, "exact", [found])
    found = fuzzy_match(phrase, labels)
    if found:
        return Resolution(found, "fuzzy", [found])

    lexical = bm25_ranking(phrase, topic_vocabulary(topic_set, terms))
    note = None
    try:
        semantic = semantic_ranking(phrase, graph)
    except ImportError:
        semantic, note = (
            [],
            (
                "semantic resolution unavailable (enrich extra not installed); "
                "matched on topic vocabulary alone"
            ),
        )

    best_cosine = semantic[0][1] if semantic else None
    # The floor gates only the semantic evidence; a lexical hit on the
    # topic's own vocabulary is direct evidence regardless of geometry.
    semantically_placed = best_cosine is not None and best_cosine >= floor
    if not lexical and not semantically_placed:
        return Resolution(None, "search", [], note=note)

    fused = rrf_fuse(
        [[label for label, _ in ranking] for ranking in (lexical, semantic) if ranking]
    )
    return Resolution(
        fused[0][0], "hybrid", [label for label, _ in fused], score=best_cosine, note=note
    )

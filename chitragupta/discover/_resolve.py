"""The resolution ladder: from a free phrase to a topic that exists.

Four rungs, best first, and `resolved_via` names which fired: exact,
fuzzy (`difflib`), hybrid (BM25 over each topic's vocabulary fused with
centroid cosine by Reciprocal Rank Fusion, which is rank-based so the
scores need no calibration), then search (paper fallback, labelled).
Without the enrich extra or a loadable model (#977) a tier degrades with
a note, never a silent substitution.
"""

import difflib
from dataclasses import dataclass
from typing import Any

from chitragupta import config, reranker, retrieval
from chitragupta.discover import _data

# The standard RRF constant: each ranking contributes 1/(k + rank), so
# agreement dominates without either raw scale mattering.
RRF_K = 60

# difflib's 0.6 accepts wrong matches ("digital twin" for "digital
# signal"); 0.75 keeps the lexical rung to typos and near-forms.
_FUZZY_CUTOFF = 0.75


@dataclass
class Resolution:
    """What the ladder decided: the winning label (None means fall back
    to paper search), the rung, ranked runners-up, the rung's score and
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
    """One small BM25 document per topic: its label (what a human calls
    it) plus its c-TF-IDF terms (what the corpus calls it)."""
    return {
        topic["label"]: " ".join([topic["label"], *terms.get(topic["label"], [])])
        for topic in topic_set["topics"]
    }


def bm25_ranking(phrase: str, vocab: dict) -> list:
    """`[(label, score), ...]` best first, positive scores only, with the
    retrieval layer's tokenizer and BM25, so topic and paper matching
    agree."""
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


def _load_model() -> "Any":
    """Isolated so tests fake it and the import cost is paid only at the
    semantic rung."""
    from sentence_transformers import SentenceTransformer  # pylint: disable=import-outside-toplevel

    return SentenceTransformer(config.EMBEDDING_MODEL)


def _load_reranker() -> "Any":
    """The embed index's cross-encoder loader: one model, one cache, one
    config key (`[enrich].rerank_model`)."""
    return reranker.load_reranker(config.RERANK_MODEL)


# Loaders that already failed in this process (#1023): `lru_cache` caches
# no exception, so offline runs paid a Hub timeout per phrase. Keyed by
# loader and tier so tests start clean and the note names the right tier.
_FAILED: dict = {}


def optional_model(load, tier: str) -> "tuple[Any, str | None]":
    """`(model, None)`, or `(None, note)` naming `tier` when the model
    cannot be had (#977): `OSError` or `RuntimeError` from a missing
    checkpoint, not just `ImportError`, must not end `discover`. A
    failure is remembered for the process."""
    key = (load, tier)
    if key in _FAILED:
        return None, _FAILED[key]
    try:
        return load(), None
    except ImportError:
        _FAILED[key] = f"{tier} unavailable (enrich extra not installed)"
    # Broad on purpose: sentence-transformers raises anything from
    # OSError to a huggingface_hub error for a model it cannot load.
    except Exception as exc:  # noqa: BLE001 -- see the comment above
        # First line only: this is one line of a printed view.
        reason = str(exc).partition("\n")[0] or type(exc).__name__
        _FAILED[key] = f"{tier} unavailable (the model would not load: {reason})"
    return None, _FAILED[key]


def _rescored(phrase: str, fused: list, vocab: dict) -> "tuple[list, str | None]":
    """The fused candidate labels, reordered by a cross-encoder over
    (phrase, topic-vocabulary) pairs (a recall-then-precision cascade).

    Reorders only, never adds. With `[enrich].rerank` off the model is
    never loaded (docs/CONFIG.md); unavailable, the fused order stands
    with a note.
    """
    if not config.RERANK:
        return fused, None
    scorer, note = optional_model(_load_reranker, "reranking")
    if scorer is None:
        return fused, note
    scores = scorer.predict([(phrase, vocab.get(label, label)) for label in fused])
    # Stable: equal scores keep the fused order.
    ordered = sorted(zip(scores, fused), key=lambda pair: -pair[0])
    return [label for _score, label in ordered], None


def semantic_ranking(phrase: str, graph: dict, model: "Any") -> list:
    """`[(label, cosine), ...]` against the stored centroids, in the
    graph stage's mean-centred space via the stored `corpus_mean`."""
    vector = model.encode(phrase, show_progress_bar=False)
    scored = [
        (topic["label"], _data.centred_cosine(vector, graph["corpus_mean"], topic["centroid"]))
        for topic in graph["topics"]
        if topic.get("centroid")
    ]
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
    paper search, which the ladder never does itself so it stays
    visibly different."""
    floor = config.DISCOVER_MIN_SIMILARITY if min_similarity is None else min_similarity
    labels = [topic["label"] for topic in topic_set["topics"]]

    found = exact_match(phrase, labels)
    if found:
        return Resolution(found, "exact", [found])
    found = fuzzy_match(phrase, labels)
    if found:
        return Resolution(found, "fuzzy", [found])

    vocab = topic_vocabulary(topic_set, terms)
    lexical = bm25_ranking(phrase, vocab)
    model, note = optional_model(_load_model, "semantic resolution")
    semantic = semantic_ranking(phrase, graph, model) if model is not None else []
    if note:
        note += "; matched on topic vocabulary alone"

    best_cosine = semantic[0][1] if semantic else None
    # The floor gates only the semantic evidence; a lexical hit on the
    # topic's own vocabulary is direct evidence regardless of geometry.
    semantically_placed = best_cosine is not None and best_cosine >= floor
    if not lexical and not semantically_placed:
        return Resolution(None, "search", [], note=note)

    fused = rrf_fuse(
        [[label for label, _ in ranking] for ranking in (lexical, semantic) if ranking]
    )
    ordered, rerank_note = _rescored(phrase, [label for label, _ in fused], vocab)
    note = "; ".join(n for n in (note, rerank_note) if n) or None
    return Resolution(ordered[0], "hybrid", ordered, score=best_cosine, note=note)

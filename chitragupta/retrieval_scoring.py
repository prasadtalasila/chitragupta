"""Okapi BM25, its two free parameters (#788), and the field weights
that tilt it (#762).

`retrieval.py` owns what text an item contributes; this module owns what
that text scores. Fields are a list (`FIELDS`), so adding one is a tuple
entry and a config key. #770's `caption` and `table` fields were
declined: there are no caption records, and `table` measured a loss
(bench/RESULTS.md, 2026-09-17).

The weighted frequency is a delta on the unweighted one,
`tf~ = tf_full + SUM over fields of (w_f - 1) * tf_f`, with one
saturation on `tf~`. So a weight of 1.0 reproduces the old ranking
structurally, and fields need not partition the document (an abstract
sits inside the body). Unlike BM25F, length is not weighted: that would
move `avgdl` at any weight and lose the 1.0 baseline.

`k1` and `b` ship at the textbook 1.5/0.75 and stay configurable, since
the sweep (bench/RESULTS.md) answers only for this bibliography's length
spread. Stdlib only (docs/ARCHITECTURE.md).
"""

import math
import sqlite3

from chitragupta import _abstract, config, passages

# The weightable fields. `config.RETRIEVAL_FIELD_WEIGHTS` cannot import
# this (this module imports `config`), so tests/test_retrieval_scoring.py
# pins the two equal; a mismatch would KeyError in `field_deltas`.
FIELDS = ("title", "abstract")


def field_texts(item: sqlite3.Row) -> dict[str, str]:
    """`item`'s text for each field that has any, keyed by field name.

    A field the source cannot supply is absent, not empty: `pdftotext`,
    the default backend, writes no sidecar, so "no abstract" is ordinary
    (docs/RETRIEVAL.md). The abstract comes from rung 2, never the
    enrichment layer's rung 1: BM25 must not change when Docling runs, and
    `retrieval_cache._fingerprint` would not notice a rung-1 rewrite.
    #772 proposes reversing that with the fingerprint change it needs.
    """
    texts = {"title": item["title"] or ""}
    found = passages.corpus_passages(item["citekey"])
    abstract = _abstract.extract_from(found) if found else None
    if abstract:
        texts["abstract"] = abstract
    return texts


def field_freqs(item: sqlite3.Row, tokenize) -> dict[str, dict[str, int]]:
    """Per-field term counts for `item`, tokenized by `tokenize`, which is
    passed in because `retrieval.py` imports this module.
    """
    counts: dict[str, dict[str, int]] = {}
    for name, text in field_texts(item).items():
        freqs: dict[str, int] = {}
        for token in tokenize(text):
            freqs[token] = freqs.get(token, 0) + 1
        if freqs:
            counts[name] = freqs
    return counts


def field_deltas() -> list[tuple[str, float]]:
    """`(field, weight - 1)` for every field whose weight is not 1.0.
    Computed once per `bm25_scores` call, outside the corpus loop; empty
    at the defaults, so the seam is free when unused.
    """
    return [
        (name, config.RETRIEVAL_FIELD_WEIGHTS[name] - 1.0)
        for name in FIELDS
        if config.RETRIEVAL_FIELD_WEIGHTS[name] != 1.0
    ]


def weighted_freq(entry: dict, term: str, deltas: list[tuple[str, float]]) -> float:
    """`term`'s frequency in `entry`, tilted by `deltas`.

    An entry with no `field_freqs` scores unweighted: `discover/_resolve.py`
    builds such entries to rank topic labels, which a retrieval weight
    must not re-rank.
    """
    freq = float(entry["term_freqs"].get(term, 0))
    if not deltas:
        return freq
    fields = entry.get("field_freqs") or {}
    for name, delta in deltas:
        freq += delta * fields.get(name, {}).get(term, 0)
    # Sidecar and `.txt` normalize differently, so a field can out-count
    # the document; below weight 1 that would rank a document containing
    # the term below one without it. Clamped: no caller can fix it.
    return max(0.0, freq)


def bm25_scores(index: dict, terms: list[str]) -> dict[str, float]:
    doc_count = len(index)
    if doc_count == 0:
        return {}
    avgdl = sum(entry["length"] for entry in index.values()) / doc_count

    term_set = set(terms)
    doc_freq = {
        t: sum(1 for entry in index.values() if entry["term_freqs"].get(t)) for t in term_set
    }
    idf = {t: math.log((doc_count - doc_freq[t] + 0.5) / (doc_freq[t] + 0.5) + 1) for t in term_set}

    # Document frequency, and so IDF, is from `term_freqs` alone: a weight
    # says how much a match matters, and must not move other documents.
    deltas = field_deltas()
    # Read per call (so bench_retrieval_bm25_params.py can sweep in one
    # process), once, outside the corpus loop. docs/RETRIEVAL.md has the
    # #788 results.
    k1, b = config.RETRIEVAL_K1, config.RETRIEVAL_B
    scores: dict[str, float] = {}
    for citekey, entry in index.items():
        doc_len = entry["length"]
        norm = 1 - b + b * (doc_len / avgdl if avgdl else 0)
        score = 0.0
        for t in term_set:
            freq = weighted_freq(entry, t, deltas)
            if freq == 0:
                continue
            score += idf[t] * (freq * (k1 + 1)) / (freq + k1 * norm)
        if score > 0:
            scores[citekey] = score
    return scores

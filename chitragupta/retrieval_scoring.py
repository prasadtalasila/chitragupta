"""Okapi BM25, and the field weights that tilt it (#762).

Split from `chitragupta/retrieval.py`, which sat at exactly the
250-code-line C2 limit when field weighting arrived -- the same pressure
that produced `retrieval_cache.py` and `retrieval_cli.py` (#441). The
boundary is not only the line count, and is worth stating so the next
split lands in the same place: `retrieval.py` owns *what text an item
contributes* -- `_full_text`, the reference cut, the snippet windows --
and this module owns *what that text scores*.

**Field-list-driven rather than two named weights.** `FIELDS` below has
`title` and `abstract` today; #770 adds `caption` and `table` to the same
seam, and #772 re-points where the abstract is read from. Each of those
is then a change to one tuple and one config table rather than a fourth
and fifth scalar threaded through three functions.

**The weighted term frequency is a delta on the unweighted one:**

    tf~ = tf_full + SUM over fields of (w_f - 1) * tf_f

with one BM25 saturation applied to `tf~`, not one per field. Two
properties follow, and both are load-bearing:

- **A weight of 1.0 reproduces the previous ranking exactly**, because
  every added term is multiplied by zero. That is #762's own success
  criterion, and it is structural here rather than a number a test
  checks: `field_deltas` returns an empty list, so `weighted_freq` never
  looks at a field count at all.
- **The fields need not partition the document.** An abstract's text sits
  *inside* the parsed body, so title/abstract/body is not a partition and
  subtracting one out of another would be fragile against whitespace
  normalization and the reference cut. Adding a delta does not care.

Document length is deliberately **not** weighted, which is where this
departs from textbook BM25F. Real BM25F normalizes each field by its own
length, and doing so here would break the identity above -- `avgdl` would
move the moment any weight left 1.0, so "weight 1.0 changes nothing"
would stop being true and no measurement would have a baseline. The cost
is that a field weight raises a document's score without raising its
modelled length; the benefit is the baseline. Recorded as the deliberate
trade it is, not an oversight.

Stdlib only, like `retrieval.py` itself: this runs under bare `python3`
with no venv (docs/ARCHITECTURE.md).
"""

import math
import sqlite3

from chitragupta import _abstract, config, passages

# Standard Okapi BM25 constants (term-frequency saturation and length
# normalization strength) -- the usual defaults, not tuned against this
# corpus specifically. Issue #788 is the sweep that would change that.
_K1 = 1.5
_B = 0.75

# The fields that may carry a weight, in the order a reader should meet
# them. `config.RETRIEVAL_FIELD_WEIGHTS` lists the same names and cannot
# import this tuple -- this module imports `config`, so the dependency
# only runs one way -- which is why the two are pinned equal by a test
# (tests/test_retrieval_scoring.py) rather than by construction. Adding a
# field in one place alone reddens that test; it would otherwise raise a
# KeyError in `field_deltas` on the next search.
FIELDS = ("title", "abstract")


def field_texts(item: sqlite3.Row) -> dict[str, str]:
    """`item`'s text for each field that has any, keyed by field name.

    A field is *absent* rather than empty when the source cannot supply
    it, so `field_freqs` writes no entry and `weighted_freq` adds nothing
    -- the `pdftotext` backend writes no passage sidecar at all, and it
    is the shipped default (`[parser].backend`), so "no abstract" is the
    ordinary case rather than an error. docs/RETRIEVAL.md states which
    backend makes the abstract weight live.

    The abstract is read from `passages.corpus_passages` -- rung 2, this
    layer's own parse -- and never from `passages.structural_passages`,
    which prefers the enrichment layer's rung 1. Two invariants say so.
    `retrieval.py`'s docstring promises that running the enrichment
    layer's Docling stage does not change what BM25 ranks. And
    `retrieval_cache._fingerprint` deliberately does not stat a sidecar,
    on the argument that the corpus layer rewrites the `.txt` whenever it
    rewrites its own sidecar -- an argument that holds for rung 2 and not
    for rung 1, which the enrichment layer writes without touching
    `content/parsed/` at all. Reading rung 1 here would therefore leave a
    cached entry matching after a Docling run, serving pre-enrichment
    abstracts indefinitely with nothing to notice. #772 proposes making
    that reversal deliberately, with the fingerprint change it needs.
    """
    texts = {"title": item["title"] or ""}
    found = passages.corpus_passages(item["citekey"])
    abstract = _abstract.extract_from(found) if found else None
    if abstract:
        texts["abstract"] = abstract
    return texts


def field_freqs(item: sqlite3.Row, tokenize) -> dict[str, dict[str, int]]:
    """Per-field term counts for `item`, tokenized by `tokenize`.

    `tokenize` is passed in rather than imported: it lives in
    `retrieval.py`, which imports this module, and taking it as an
    argument is what keeps that one-directional -- the same reason
    `retrieval_cache._load_index` takes its `tokenize_item`.
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

    Computed once per `bm25_scores` call rather than per (document, term)
    pair: the loop below runs over the whole corpus, and re-reading the
    config inside it was the obvious way to make a stdlib ranker slow.
    Empty at the shipped defaults, which is what makes the whole field
    seam free when nobody has turned it on.
    """
    return [
        (name, config.RETRIEVAL_FIELD_WEIGHTS[name] - 1.0)
        for name in FIELDS
        if config.RETRIEVAL_FIELD_WEIGHTS[name] != 1.0
    ]


def weighted_freq(entry: dict, term: str, deltas: list[tuple[str, float]]) -> float:
    """`term`'s frequency in `entry`, tilted by `deltas`.

    An entry with no `field_freqs` scores exactly as it did before this
    module existed, whatever the weights say. That is not defensive
    coding: `chitragupta/discover/_resolve.py` builds synthetic index
    entries by hand -- `term_freqs` and `length`, nothing else -- to rank
    topic labels, and turning a retrieval weight up must not silently
    re-rank the topic resolver too.
    """
    freq = float(entry["term_freqs"].get(term, 0))
    if not deltas:
        return freq
    fields = entry.get("field_freqs") or {}
    for name, delta in deltas:
        freq += delta * fields.get(name, {}).get(term, 0)
    # A field's counts come from the passage sidecar and the full count
    # from the flattened `.txt`; the two normalize whitespace and
    # hyphenation differently, so a field can out-count the whole
    # document for one term. Below a weight of 1 that makes `freq`
    # negative, which BM25's saturation curve turns into a negative
    # contribution -- ranking a document that contains the term *below*
    # one that does not. Clamped rather than asserted: the mismatch is a
    # property of two parsers, not a bug a caller can fix.
    return max(0.0, freq)


def bm25_scores(
    index: dict, terms: list[str], weights: dict[str, float] | None = None
) -> dict[str, float]:
    """Okapi BM25 over `index` for `terms`, top-level score per citekey.

    `weights` (#789) multiplies one term's contribution, for a term the
    caller did not type -- `retrieval_expansion` adds an acronym's
    expansion at less than full weight. `None`, the shipped default, is
    not "a table of 1.0s": the multiplication is skipped entirely, so a
    caller who has turned expansion off runs the arithmetic this function
    ran before the parameter existed. A term `weights` does not name
    scores at 1.0, which is what makes it a table of *exceptions* rather
    than a second place the query's own terms are listed.

    Unlike a field weight, this one is a per-*term* multiplier and so
    lands outside the saturation curve rather than inside it. Putting it
    on the frequency instead would make "this term matters half as much"
    mean "pretend the document said it half as often", which saturation
    then flattens to almost no difference for any document that says it
    more than twice -- i.e. exactly the documents the expansion was
    added to reach.

    Document frequency and IDF are read from `term_freqs` alone, as they
    already were for field weights: how much a match matters is not how
    rare the term is, and an added term must not restate the corpus.
    """
    doc_count = len(index)
    if doc_count == 0:
        return {}
    avgdl = sum(entry["length"] for entry in index.values()) / doc_count

    term_set = set(terms)
    doc_freq = {
        t: sum(1 for entry in index.values() if entry["term_freqs"].get(t)) for t in term_set
    }
    idf = {t: math.log((doc_count - doc_freq[t] + 0.5) / (doc_freq[t] + 0.5) + 1) for t in term_set}

    # Document frequency, and so every IDF, is read from `term_freqs`
    # alone and never from the weighted count. A field weight says how
    # much a match *matters*, not how rare the term is across the corpus,
    # and letting it move IDF would make one document's weight change
    # every other document's score.
    deltas = field_deltas()
    scores: dict[str, float] = {}
    for citekey, entry in index.items():
        doc_len = entry["length"]
        norm = 1 - _B + _B * (doc_len / avgdl if avgdl else 0)
        score = 0.0
        for t in term_set:
            freq = weighted_freq(entry, t, deltas)
            if freq == 0:
                continue
            contribution = idf[t] * (freq * (_K1 + 1)) / (freq + _K1 * norm)
            if weights is not None:
                contribution *= weights.get(t, 1.0)
            score += contribution
        if score > 0:
            scores[citekey] = score
    return scores

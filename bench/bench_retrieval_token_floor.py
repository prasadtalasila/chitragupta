"""What lowering BM25's 1-2 character token floor (#790) does to
retrieval on this corpus -- recall *and* precision, before and after,
over every ground truth this host can build.

`chitragupta/retrieval.py::_tokenize` **used to** keep a token only if it
was longer than two characters, so "AI", "DT", "ML" and "5G" were in no
document's term frequencies and in no query's terms, and
`retrieval.short_query_terms` existed only to let the CLI *warn* about
that. #790 asked for the fix and for it to be measured rather than
assumed; this is the measurement, and **floor 2 was adopted on the
strength of it**, so the shipped tokenizer is no longer this script's
baseline arm. Nothing below changes for that -- see "Every arm is written
into this script" -- but a reader comparing an arm here against
`chitragupta/` today should expect only `floor 2` to match.

The arms, four of them, each a *pair* of tokenizers because the shipped
pipeline has two (`_tokenize` for a document, `_query_terms` for a query,
the latter also dropping interrogatives -- #453):

- **floor 3 (baseline, shipped until #790)** -- `len(w) > 2`, the rule in
  `chitragupta/` when this ran and the "before" every figure is a delta
  on.
- **floor 2 (#790, proposed -- and since adopted)** -- `len(w) > 1`. What
  the issue asked for: "AI" and "5G" become indexable and rankable. This
  is what `chitragupta/` does now.
- **floor 2, no bare numbers** -- `len(w) > 1`, except that a *newly
  admitted* token of digits alone ("4", "11") stays out. The acronym half
  of #790's case without the page-number/section-number half;
  `overlap_skipgram.stem_filter` and `bench_retrieval_stemming.
  _stem_token` both already treat a bare number as a thing to leave
  alone, so this is that same distinction asked as a question. The digit
  rule deliberately stops at the shipped floor, so this arm indexes a
  strict subset of `floor 2` and a superset of `floor 3`: dropping
  "2024" and "100" as well would vary two things at once and the arm
  would no longer be about the floor.
- **floor 1 (#790, swept)** -- `len(w) > 0`. #790 calls this "probably
  wrong and worth measuring rather than assuming", and asks for it in the
  sweep so the choice is recorded rather than asserted.

**Every arm is written into this script, the baseline included.** Same
reason `bench_retrieval_stemming.py` gives, and this script is the case
that proves it: the floor moved *because of* this measurement, so a
baseline arm that read `retrieval._tokenize` would have silently become
floor 2 and made the comparison compare nothing. `self_check` pins each
arm against a literal for that reason rather than against the shipped
tokenizer.

**Read the whole-set means with the affected-subset table beside them,
never either alone.** Most queries have no 1-2 character content word in
them at all -- 32 of this host's 258 self-retrieval rows do, at the full
keyword width -- so averaging the other 226 into the mean shrinks every
difference by roughly eight, and a real gain reads as nothing. `score_arm`
therefore reports every figure twice: over all rows, and over the rows
whose query terms actually differ between the arm and the baseline, with
the baseline re-aggregated over that same subset so the pair is a real
before and after.

**And the unaffected rows are not a control.** A query whose own terms
never change still ranks differently, because a lowered floor admits
tokens to every *document* and so grows every document's `length` --
5,479 mean tokens to 5,870 here -- which is BM25's normalization
denominator. On this corpus that is not a hypothetical: the affected
subset gains three queries at recall@1 while the whole set stays flat, so
three unaffected queries lost. `per_query_movement` counts both
populations for that reason, and `self_check` pins the whole-set count so
a future edit cannot quietly go back to counting the subset alone.

**Why precision is rank quality rather than precision@k**, unchanged from
the stemming entry's reasoning: every self-retrieval row has exactly one
relevant document, so precision@5 there is recall@5 / 5 -- the same number
twice. What a floor lowering risks is not a missing paper but junk above
the right one, so it shows as recall@1, MRR@5 and nDCG@5 moving
differently from recall@5, and as the mean document frequency of a
query's own terms rising. `--admitted` lists the tokens each lowered
floor actually lets into the index, by corpus document frequency, so a
reader can judge what was admitted instead of taking a mean on trust.

**Never touches `content/retrieval_index.json`.** Every arm builds its
index in memory from `retrieval._full_text`, the same `_tokenize_item`-
shaped per-document stats `retrieval_cache` would cache. One arm's
tokenizer written into the shared on-disk cache would corrupt real corpus
state for every later run, and that cache has no notion of an arm.

Stdlib-only and needs no GPU, like `bench_overlap.py`: it reads this
host's real `content/ledger.sqlite` and `content/parsed/` read-only, plus
`papers/bibliography.bib` through `bib_reader` for the keywords the
ledger deliberately does not store, and (for the live-logged set) a
book's dossiers.

    cp config.toml.example config.toml   # worktree only; gitignored data
    CONTENT_DIR=/workspace/git/chitragupta/content \\
      BIB_FILE=/workspace/git/chitragupta/papers/bibliography.bib \\
      .venv-full/bin/python bench/bench_retrieval_token_floor.py \\
      --only self-retrieval --admitted --tag <tag>

`--only self-retrieval` is not decoration on a host where the book's
dossiers are absent: the live-logged ground truth is built from a
restored book's own `retrieval.md` logs, which are gitignored per-host
data. `bench_retrieval_live_logs.py`'s `BENCH_BOOK_DOSSIERS` override
points at a `content/backup/<date>-content/` snapshot where one exists,
and both sets then build in one invocation. Where none exists, this
script says the set is unavailable by name rather than reporting a zero.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from chitragupta import ledger, retrieval, retrieval_scoring  # noqa: E402
from chitragupta._passage_words import _CORE_STOPWORDS  # noqa: E402
from bench_retrieval_compare import ndcg_at_k, recall_at_k  # noqa: E402
from bench_retrieval_keyword_selfretrieval import build_keyword_ground_truth  # noqa: E402
from bench_retrieval_live_logs import build_live_ground_truth  # noqa: E402

K_REPORT = 5
ADMITTED_ROWS = 25

_WORD = re.compile(r"[a-z0-9]+")

# The arm every other arm is a delta on, by label, so the comparison
# tables and `per_query_movement` cannot disagree about which is "before".
# Not called "as shipped": this measurement is what moved the shipped
# floor to 2, so that label would have been false the day after the run
# and every committed record row carries it.
BASELINE = "floor 3 (baseline, shipped until #790)"

# The floor this script's baseline arm is, as the number it is -- what
# `retrieval._tokenize` did before #790 adopted floor 2 on the strength
# of the tables below. Read by the digit rule and by `admitted_tokens` as
# well as by the baseline arm, so "newly admitted" means the same thing
# everywhere.
SHIPPED_FLOOR = 3

# The lowest floor any arm here sweeps. `admitted_tokens` reports what
# every lowered arm admits between the two, so it has to reach as far
# down as the arms do.
LOWEST_FLOOR = 1


def _floor_tokens(text: str, floor: int, numbers: bool = True) -> list[str]:
    """`retrieval._tokenize`'s rule with the length floor as a parameter.

    `floor` is the shortest token kept, so `floor=3` is the shipped
    `len(w) > 2`. `numbers=False` additionally drops a token of digits
    alone -- but only one this floor newly admits, never one the shipped
    floor already keeps.

    **That "only" is the arm's whole validity.** Dropping every bare
    number would also take out "2024", "100" and "5000", which
    `floor 3` indexes today, so the arm would differ from the baseline in
    the floor *and* in an unrelated deletion and no reading of its row
    could separate the two. Bounded at `SHIPPED_FLOOR`, it indexes a
    strict subset of `floor 2` and a strict superset of `floor 3`, which
    is what makes "the acronyms without the section numbers" a question
    the table can answer.

    The stopword list is consulted on the surface form and independently
    of the floor, exactly as the shipped rule does: `_CORE_STOPWORDS`
    holds 11 words of two characters or fewer ("of", "in", "at", ...),
    and those stay out at every floor here.
    """
    kept = []
    for word in _WORD.findall(text.lower()):
        if len(word) < floor or word in _CORE_STOPWORDS:
            continue
        if not numbers and len(word) < SHIPPED_FLOOR and word.isdigit():
            continue
        kept.append(word)
    return kept


def _query_rule(tokenize):
    """One arm's document tokenizer, as its query tokenizer.

    The query side is the document side plus dropping interrogatives, and
    conflating the two silently misreports the baseline -- the stemming
    harness shipped that bug and it moved a published figure in the fourth
    decimal (`bench_retrieval_stemming._unstemmed_query_terms` has the
    account). Built here rather than written out four times so an arm
    cannot acquire one by hand and lose the other.

    Note what this does *not* have to special-case: every word in
    `retrieval._INTERROGATIVES` is three characters or longer, so no floor
    swept here can admit one that the shipped rule drops. Asserted in
    `self_check` rather than left as a reading of the constant.
    """

    def query_terms(query: str) -> list[str]:
        return [w for w in tokenize(query) if w not in retrieval._INTERROGATIVES]

    return query_terms


def _arm(floor: int, numbers: bool = True):
    """The `(document tokenizer, query tokenizer)` pair for one floor."""
    tokenize = lambda text: _floor_tokens(text, floor, numbers)  # noqa: E731
    return tokenize, _query_rule(tokenize)


ARMS = {
    BASELINE: _arm(SHIPPED_FLOOR),
    "floor 2 (#790, proposed)": _arm(2),
    "floor 2, no bare numbers": _arm(2, numbers=False),
    "floor 1 (#790, swept)": _arm(1),
}


def build_index(items, tokenize):
    """The same per-document entry `retrieval._tokenize_item` produces, in
    memory, for one arm's tokenizer.

    `field_freqs` is carried as well as `length`/`term_freqs`, and is not
    optional since #762: `retrieval_scoring.weighted_freq` reads a
    *missing* `field_freqs` as "this document's title matched nothing", so
    an index built without it tracks the shipped scorer only while every
    `[retrieval].weight_*` is still 1.0. Built through
    `retrieval_scoring.field_freqs`, which takes the tokenizer as an
    argument, so each arm's fields are counted by that arm's own rule and
    the arm stays the tokenizer and nothing else.
    """
    index = {}
    for item in items:
        tokens = tokenize(retrieval._full_text(item))
        index[item["citekey"]] = {
            "length": len(tokens),
            "term_freqs": dict(Counter(tokens)),
            "field_freqs": retrieval_scoring.field_freqs(item, tokenize),
        }
    return index


def mrr(ranked_citekeys, relevant):
    """Reciprocal rank of the first relevant hit, 0.0 if none is ranked.

    Reported alongside recall@5 because a single-relevant ground truth
    makes precision@5 a restatement of recall@5 -- where the right answer
    sits is the only precision signal such a set carries.

    Published as **`mrr@5`**, not `mrr`: every caller here passes a list
    already cut to `K_REPORT`, so a correct answer at rank 9 scores 0.0
    exactly as one never ranked at all does. That is reciprocal rank at a
    cutoff, a smaller number than full MRR over the whole ledger, and a
    column labelled `mrr` would invite a reader to compare it with one.
    """
    for position, citekey in enumerate(ranked_citekeys, start=1):
        if citekey in relevant:
            return 1.0 / position
    return 0.0


def mean_doc_frequency(index, terms):
    """Mean number of documents in `index` that contain one of `terms`.

    The mechanism behind a precision loss rather than a symptom of it: a
    lowered floor admits terms like "we", "or" and "4", which sit in
    almost every document and so carry almost no IDF. A rise here with no
    recall gain is what "the admitted terms bought nothing and cost
    specificity" looks like.
    """
    if not terms:
        return 0.0
    counts = [sum(1 for entry in index.values() if entry["term_freqs"].get(t)) for t in set(terms)]
    return sum(counts) / len(counts)


def affected_keys(ground_truth, baseline_query_terms, arm_query_terms):
    """The ground-truth keys whose *query terms* differ between two arms.

    A floor change reaches a query only through the terms it admits to
    it, so this is the subset on which the arms can possibly disagree --
    and the subset the means must be reported over as well as the whole
    set. Comparing term lists rather than counting short words directly
    keeps this honest for the "no bare numbers" arm, where a query can
    gain one short term and not another.
    """
    return {
        row["key"]
        for row in ground_truth
        if baseline_query_terms(row["query"]) != arm_query_terms(row["query"])
    }


def _figures(rows):
    """The five published figures for a list of per-query records."""
    if not rows:
        return None
    n = len(rows)
    return {
        "n_queries": n,
        "recall@1": round(sum(r["recall@1"] for r in rows) / n, 4),
        f"recall@{K_REPORT}": round(sum(r["recall@k"] for r in rows) / n, 4),
        f"mrr@{K_REPORT}": round(sum(r["rr"] for r in rows) / n, 4),
        f"ndcg@{K_REPORT}": round(sum(r["ndcg"] for r in rows) / n, 4),
        "mean_query_term_df": round(sum(r["df"] for r in rows) / n, 1),
    }


def score_arm(label, index, tokenize, ground_truth, affected):
    """One arm's row: the four ranking figures and the mean query-term
    document frequency, over every row *and* over `affected` alone.

    A ground-truth row is `{"key", "query", "relevant"}` -- `relevant` a
    set, so the same scorer serves both ground truths: the self-retrieval
    set's one correct paper per query and the live-logged set's whole
    chapter kept-citekey set.

    `affected` is the key set from `affected_keys`; passing an empty set
    reports `None` for the subset rather than a zero, because "no query
    could move" and "every query scored zero" are different findings and
    a 0.0 in that column would read as the second.

    The per-query records are returned as well as aggregated, so a caller
    can re-aggregate the *baseline* over another arm's affected keys --
    which is the only way to state a before and an after on the same
    subset, and the baseline's own affected set is empty by construction.
    """
    per_query, ranked_by_key = [], {}
    for row in ground_truth:
        terms = tokenize(row["query"])
        scores = retrieval._bm25_scores(index, terms)
        ranked = [c for c, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]
        ranked = ranked[:K_REPORT]
        ranked_by_key[row["key"]] = ranked
        relevant = row["relevant"]
        per_query.append(
            {
                "key": row["key"],
                "recall@1": recall_at_k(ranked, relevant, 1),
                "recall@k": recall_at_k(ranked, relevant, K_REPORT),
                "rr": mrr(ranked, relevant),
                "ndcg": ndcg_at_k(ranked, relevant, K_REPORT),
                "df": mean_doc_frequency(index, terms),
            }
        )
    vocabulary = {t for entry in index.values() for t in entry["term_freqs"]}
    lengths = [entry["length"] for entry in index.values()]
    row = {
        "row": label,
        **_figures(per_query),
        "index_vocabulary": len(vocabulary),
        "mean_doc_tokens": round(sum(lengths) / len(lengths), 1),
    }
    row["affected"] = _figures([r for r in per_query if r["key"] in affected])
    return row, ranked_by_key, per_query


def per_query_movement(before, after, ground_truth, affected):
    """How many queries the change helped, hurt and left alone, by the
    rank of their own correct answer.

    A mean can hide a swap: a change that finds four papers it used to
    miss and loses four it used to find reports no movement at all
    (docs/AUTO-IMPROVEMENT.md's reading of `objective_delta` is the same
    hazard). These counts are what a mean cannot say.

    **Counted over every query, and then again over `affected` alone.**
    An earlier version of this function counted only the queries whose
    own terms the floor changed and reported the rest as "unreachable",
    on the reasoning that a query with no short word in it cannot move.
    That reasoning is wrong, and the run that used it published a
    contradiction: the affected subset gained three queries at recall@1
    while the whole set stayed flat, which is arithmetically only
    possible if three *unaffected* queries lost. They can. A lowered
    floor admits tokens to every document, so every document's `length`
    grows -- 5,479 mean tokens to 5,870 on this corpus -- and BM25
    divides by length, so the whole ranking shifts under a query that
    never changed a term. The subset counts say what the floor bought
    where it applies; the whole-set counts say what it cost everywhere
    else, and only the pair is the result.
    """

    def split(rows):
        better, worse, same = [], [], 0
        for row in rows:
            relevant = row["relevant"]
            before_rr = mrr(before.get(row["key"], []), relevant)
            after_rr = mrr(after.get(row["key"], []), relevant)
            if after_rr > before_rr:
                better.append(row["key"])
            elif after_rr < before_rr:
                worse.append(row["key"])
            else:
                same += 1
        return better, worse, same

    better, worse, same = split(ground_truth)
    sub_better, sub_worse, sub_same = split([r for r in ground_truth if r["key"] in affected])
    return {
        "better": better,
        "worse": worse,
        "unchanged": same,
        "term_affected": len(affected),
        "affected_better": sub_better,
        "affected_worse": sub_worse,
        "affected_unchanged": sub_same,
    }


def admitted_tokens(items, limit=ADMITTED_ROWS):
    """What each lowered floor actually lets into the index, by corpus
    document frequency.

    The judgement call #790 turns on, made inspectable rather than
    asserted: the issue's premise is that "short stopwords are already
    excluded by `_STOPWORDS` regardless of length, so the floor's entire
    remaining effect is to discard short *content* words". That is a
    claim about this corpus's vocabulary, and this is the measurement of
    it. `retrieval` imports the 19-word `_CORE_STOPWORDS`, not the wider
    `_STOPWORDS` in the same module, so what a lowered floor admits is
    the question rather than a foregone conclusion.

    Returns `(rows, totals)` -- every admitted token ranked by the number
    of documents carrying it, cut to `limit`, plus the counts the cut was
    drawn from, so a caller can say what the printed top-N is a top-N of.
    """
    document_frequency, in_baseline = Counter(), set()
    for item in items:
        text = retrieval._full_text(item)
        in_baseline.update(_floor_tokens(text, SHIPPED_FLOOR))
        for token in set(_floor_tokens(text, LOWEST_FLOOR)):
            document_frequency[token] += 1
    admitted = {t: df for t, df in document_frequency.items() if t not in in_baseline}
    widest = sorted(admitted.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    rows = [
        {"token": t, "document_frequency": df, "digits": t.isdigit(), "length": len(t)}
        for t, df in widest
    ]
    totals = {
        "admitted_at_floor_2": sum(1 for t in admitted if len(t) == 2),
        "admitted_at_floor_1": sum(1 for t in admitted if len(t) == 1),
        "of_those_bare_numbers": sum(1 for t in admitted if t.isdigit()),
    }
    return rows, totals


# A ground truth built from author keywords gives each query 5-10 terms.
# #790's case is a query that returns nothing or returns a ranking its own
# content words played no part in, which is a short-query failure -- so
# every arm is also scored on the same rows narrowed to their first N
# keywords: same corpus, same correct answer, less redundancy to absorb a
# term the floor dropped. `None` is the full keyword list.
QUERY_WIDTHS = (None, 3, 2, 1)


def narrow(ground_truth, keywords):
    """`ground_truth` with each query cut to its first `keywords`
    author-assigned keywords (comma-separated, as the bib field writes
    them). `None` returns the rows unchanged."""
    if keywords is None:
        return ground_truth
    narrowed = []
    for row in ground_truth:
        kept = ", ".join(k.strip() for k in row["query"].split(",")[:keywords] if k.strip())
        if kept:
            narrowed.append({**row, "query": kept})
    return narrowed


def self_retrieval_rows():
    """The author-keyword rows, in this script's row shape.

    **Biased toward the lowered-floor arms, which is the opposite of this
    set's bias in the stemming entry and has to be read that way.** The
    query is the paper's own `keywords` field and the correct answer is
    that paper, whose text usually carries those keyword strings
    verbatim. A keyword of "DT" is therefore a term the target document
    is near-certain to contain, so admitting it hands the right answer a
    match that no other arm has. A *loss* on this set is decisive; a gain
    is the bias doing its work and needs the live-logged set to confirm.
    """
    return [
        {"key": row["citekey"], "query": row["query"], "relevant": {row["citekey"]}}
        for row in build_keyword_ground_truth()
    ]


def live_logged_rows():
    """The real drafting-session queries, in this script's row shape.

    The complement to the bias above: a human typed these queries into
    `search` while writing a chapter, and the relevant set is the citekeys
    that chapter actually kept -- neither the query nor the answer was
    produced by any tokenizer, so nothing here prefers a short term that
    happens to sit in the target. Queries are free prose rather than a
    comma-separated keyword list, so `QUERY_WIDTHS` does not apply to this
    set; they are already the short, subject-naming shape #790 argues for.
    """
    return [
        {
            "key": (row["chapter"], row["query_index"]),
            "query": row["query"],
            "relevant": set(row["citekeys"]),
        }
        for row in build_live_ground_truth()
    ]


GROUND_TRUTHS = {"self-retrieval": self_retrieval_rows, "live-logged": live_logged_rows}


def self_check():
    """A fabricated difference this script's own comparison logic must see.

    The decoy corpus has one paper whose *only* distinguishing term is the
    two-character "5g" and a decoy that outranks it on everything else. So
    the shipped-floor arm must rank nothing at all for the query "5g", and
    every lowered arm must rank that paper first -- if any row disagrees,
    the arms are not the arms this script claims to measure and every
    figure below is about something else.

    What it cannot see: whether the *real* ground truths were built from
    the data they name. `build_keyword_ground_truth` and
    `build_live_ground_truth` have their own self-checks in the scripts
    that own them, and this one deliberately does not re-run them -- a
    fixture here would only prove that a fixture parses.
    """
    assert mrr(["a", "b", "c"], {"b"}) == 0.5, "relevant at rank 2 is a reciprocal rank of 1/2"
    assert mrr(["a", "b"], {"z"}) == 0.0, "no relevant item anywhere must be 0, not an error"

    # The shipped rule has to *be* what ships, on both sides, or the
    # baseline is a number about this script rather than about the
    # pipeline. Pinned against `retrieval._tokenize`/`_query_terms` on a
    # probe exercising every filter: an interrogative, a stopword, a 1-
    # and a 2-character word, a bare number and an ordinary content word.
    probe = "why does the AI model 5G in 4 situ x"
    baseline_doc, baseline_query = ARMS[BASELINE]
    # Pinned against literals, not against `retrieval._tokenize` and
    # `retrieval._query_terms`. It was a live comparison while the
    # baseline was also what shipped; the moment this measurement was
    # acted on, floor 2 became the shipped rule and the baseline arm
    # stopped being it -- permanently, since the "before" of a published
    # comparison must not move. Running the live version after the floor
    # landed aborts `main()` before any work, which is how this was
    # caught. `bench_retrieval_stemming.py` took the same treatment for
    # the same reason. The lists below are floor 3's, and are what every
    # figure in RESULTS.md's 2026-09-16 entry was computed from.
    assert baseline_doc(probe) == ["why", "does", "model", "situ"], (
        f"the shipped arm's document rule has drifted from floor 3, the rule "
        f"this script's published figures were measured against: {baseline_doc(probe)}"
    )
    assert baseline_query(probe) == ["model", "situ"], (
        f"the shipped arm's query rule has drifted from floor 3 plus dropping "
        f"interrogatives: {baseline_query(probe)}"
    )
    # Every interrogative is 3+ characters, so no floor swept here can
    # admit one. Asserted rather than read off the constant, since a
    # future two-letter addition to it would make the floors differ in
    # something other than the floor.
    assert all(len(w) >= 3 for w in retrieval._INTERROGATIVES), (
        "an interrogative of 1-2 characters would make a lowered floor differ "
        "from the baseline in interrogative handling as well as in the floor"
    )
    assert "5g" in _floor_tokens(probe, 2) and "4" not in _floor_tokens(probe, 2, numbers=False), (
        "the no-bare-numbers arm must admit 5g and refuse 4"
    )
    # The digit rule stops at the shipped floor, so the arm cannot delete
    # a number the baseline already indexes. Without this the arm varies
    # two things and its row means nothing; it read 34 affected queries
    # against floor 2's 32 before this was bounded, which is how it was
    # found.
    assert "2024" in _floor_tokens("published 2024", 2, numbers=False), (
        "the no-bare-numbers arm dropped a number the shipped floor keeps -- "
        "it is no longer a strict superset of the baseline"
    )
    assert "of" not in _floor_tokens("of the AI", 1), (
        "a stopword must stay out at every floor -- the list is consulted "
        "independently of the length"
    )

    fake_items = [
        {
            "citekey": "short_2024",
            "title": "5g and nothing else worth ranking",
            "parsed_path": None,
            "status": "parsed",
        },
        {
            "citekey": "decoy_2024",
            "title": "unrelated work on soil moisture sensors",
            "parsed_path": None,
            "status": "parsed",
        },
    ]
    query = [
        {"key": "short_2024", "query": "5g", "relevant": {"short_2024"}},
        {"key": "decoy_query", "query": "soil moisture", "relevant": {"decoy_2024"}},
    ]
    indexes = {label: build_index(fake_items, doc) for label, (doc, _q) in ARMS.items()}
    scored, movements = _score_width(indexes, query, "fixture", "all", verbose=False)
    rows = {row["row"]: row for row in scored}
    # 0.5, not 0.0: the shipped arm must find `decoy_query`'s ordinary
    # three-character terms and miss the two-character one, so the
    # fixture's own control is checked as well as its treatment.
    assert rows[BASELINE][f"recall@{K_REPORT}"] == 0.5, (
        "the shipped arm did not find exactly one of the two fixture queries -- "
        "it ranked a document whose only matching term is two characters, or it "
        "missed an ordinary one, and either way the 'before' arm is not the "
        "shipped rule"
    )
    assert rows[BASELINE]["affected"] is None, (
        "no query can be affected in the baseline arm compared with itself"
    )
    for label in ARMS:
        if label == BASELINE:
            continue
        assert rows[label][f"recall@{K_REPORT}"] == 1.0, (
            f"{label} missed a document matching on a two-character term -- "
            f"that arm is not lowering the floor"
        )
        assert rows[label]["affected"]["n_queries"] == 1, (
            f"{label} did not see the query its own floor changed: {rows[label]['affected']}"
        )
        # The before-and-after pair on the same subset, which is the claim
        # this script exists to publish: the baseline must score 0 on the
        # very rows the lowered arm scores 1 on.
        assert rows[label]["baseline_affected"][f"recall@{K_REPORT}"] == 0.0, (
            f"{label}'s 'before' figure is not the baseline's score on {label}'s "
            f"own affected rows: {rows[label]['baseline_affected']}"
        )
    for movement in movements:
        assert movement["affected_better"] == ["short_2024"], (
            f"per_query_movement did not see {movement['arm']}'s fabricated win: {movement}"
        )
        # Every query is counted, not only the one whose terms changed.
        # `decoy_query` keeps the same terms under every arm, so it can
        # only appear here if the whole set is walked -- which is what an
        # earlier version, counting the affected subset alone, did not do.
        counted = len(movement["better"]) + len(movement["worse"]) + movement["unchanged"]
        assert counted == len(query), (
            f"{movement['arm']} scored {counted} of {len(query)} queries -- a query "
            f"whose own terms did not change is still free to move, because a "
            f"lowered floor changes every document's length"
        )
        assert movement["term_affected"] == 1, (
            f"only the 5g query has terms the floor changes: {movement}"
        )
    assert len(movements) == len(ARMS) - 1, (
        f"one movement row per lowered arm, against the baseline: {len(movements)}"
    )

    index = build_index(fake_items, ARMS[BASELINE][0])
    # "soil" is in one of the two documents and "moisture" in the same
    # one, so the mean document frequency over both terms is exactly 1.0.
    assert mean_doc_frequency(index, ["soil", "moisture"]) == 1.0, mean_doc_frequency(
        index, ["soil", "moisture"]
    )

    admitted, totals = admitted_tokens(fake_items, limit=50)
    tokens = {r["token"] for r in admitted}
    assert tokens == {"5g"}, f"'5g' is the only sub-3-character non-stopword here: {tokens}"
    assert totals["admitted_at_floor_2"] == 1 and totals["of_those_bare_numbers"] == 0, totals

    narrowed = [{"key": "x", "query": "alpha, beta, gamma, delta", "relevant": {"x"}}]
    assert narrow(narrowed, 2)[0]["query"] == "alpha, beta", narrow(narrowed, 2)
    assert narrow(narrowed, None)[0]["query"] == narrowed[0]["query"], "None must not narrow"


def _score_width(indexes, ground_truth, name, width, verbose=True):
    """Every arm scored over one ground truth at one query width, plus
    each lowered arm's movement against the baseline.

    `verbose=False` is for `self_check`, whose two-document fixture would
    otherwise print four rows of ones and zeroes above the real run and
    read as part of it."""
    rows, movements, rankings, affected, by_arm = [], [], {}, {}, {}
    for label, (_doc_tokenize, query_tokenize) in ARMS.items():
        affected[label] = affected_keys(ground_truth, ARMS[BASELINE][1], query_tokenize)
        row, ranked, per_query = score_arm(
            label, indexes[label], query_tokenize, ground_truth, affected[label]
        )
        row["ground_truth"], row["query_keywords"] = name, width
        rows.append(row)
        rankings[label], by_arm[label] = ranked, (row, per_query)
    for label in ARMS:
        if label == BASELINE:
            continue
        # The "before" for this arm's own affected subset. Taken from the
        # baseline's per-query records rather than re-scored, so it is the
        # same numbers the whole-set row above was built from.
        by_arm[label][0]["baseline_affected"] = _figures(
            [r for r in by_arm[BASELINE][1] if r["key"] in affected[label]]
        )
        movement = per_query_movement(
            rankings[BASELINE], rankings[label], ground_truth, affected[label]
        )
        movement.update(arm=label, ground_truth=name, query_keywords=width)
        movements.append(movement)
        if verbose:
            print(
                f"  [{width:>3} keywords] {label}: "
                f"{len(movement['better'])} better, {len(movement['worse'])} worse, "
                f"{movement['unchanged']} unchanged over all "
                f"{len(ground_truth)}; on the {movement['term_affected']} whose terms "
                f"changed: {len(movement['affected_better'])} better, "
                f"{len(movement['affected_worse'])} worse, "
                f"{movement['affected_unchanged']} unchanged",
                flush=True,
            )
    if verbose:
        for row in rows:
            print(f"  [{width:>3} keywords] {row}", flush=True)
    return rows, movements


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", help="results/<tag>/ to write the record into")
    parser.add_argument(
        "--admitted",
        action="store_true",
        help=f"Also print the {ADMITTED_ROWS} most widespread tokens a lowered floor admits",
    )
    parser.add_argument(
        "--only",
        choices=sorted(GROUND_TRUTHS),
        help="Score against one ground truth rather than both. Both build "
        "in one run where a book's dossiers are on disk: set "
        "BENCH_BOOK_DOSSIERS (bench_retrieval_live_logs.py) so the "
        "live-logged set takes its logs from a snapshot while CONTENT_DIR "
        "still names the live ledger and parsed text",
    )
    parser.add_argument("--self-check", action="store_true", help="Run the self-check and stop")
    args = parser.parse_args(argv)

    self_check()
    if args.self_check:
        print("self-check passed")
        return 0
    if not args.tag:
        print("--tag is required", file=sys.stderr)
        return 2

    with ledger.connection() as con:
        items = ledger.all_items(con)
    # One index per arm for every set and every query width: the index
    # depends on the tokenizer, never on the query, so narrowing the
    # queries or changing ground truth must not cost a rebuild.
    indexes = {}
    for label, (doc_tokenize, _query_tokenize) in ARMS.items():
        print(f"building the {label} index over {len(items)} ledger items...", flush=True)
        indexes[label] = build_index(items, doc_tokenize)

    rows, movements = [], []
    for name in sorted(GROUND_TRUTHS):
        if args.only and name != args.only:
            continue
        # An absent input reports as absent, by name (bench/README.md's
        # rule), rather than as a traceback or as a zero. Both cases are
        # real and reachable: the live-logged set needs a restored book's
        # dossiers, gitignored per-host data that has gone missing more
        # than once, and the keyword set needs a bib export carrying
        # `keywords` fields.
        try:
            ground_truth = GROUND_TRUTHS[name]()
        except OSError as exc:
            print(f"{name}: ground truth unavailable -- {exc}", file=sys.stderr)
            return 2
        if not ground_truth:
            print(
                f"{name}: no ground-truth rows -- check CONTENT_DIR and BIB_FILE",
                file=sys.stderr,
            )
            return 2
        # Only the keyword set is a comma-separated list there is any
        # honest way to narrow; the live-logged queries are prose.
        widths = QUERY_WIDTHS if name == "self-retrieval" else (None,)
        print(f"\n{name}: {len(ground_truth)} queries", flush=True)
        for keywords in widths:
            width = "all" if keywords is None else str(keywords)
            width_rows, width_movements = _score_width(
                indexes, narrow(ground_truth, keywords), name, width
            )
            rows.extend(width_rows)
            movements.extend(width_movements)

    record = {"rows": rows, "movements": movements}
    if args.admitted:
        admitted, totals = admitted_tokens(items)
        record["admitted"] = admitted
        record["admitted_totals"] = totals
        print(
            f"\n{totals['admitted_at_floor_2']:,} tokens admitted at floor 2 and "
            f"{totals['admitted_at_floor_1']:,} more at floor 1, "
            f"{totals['of_those_bare_numbers']:,} of them bare numbers; "
            f"the {len(admitted)} most widespread:"
        )
        for entry in admitted:
            print(
                f"  {entry['token']:4} df={entry['document_frequency']:>5}"
                f"  {'number' if entry['digits'] else 'word':>6}"
            )

    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "token_floor.json"
    out_path.write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(f"\nRecord: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

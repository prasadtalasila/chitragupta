"""What stemming BM25's tokens (#787) does to retrieval on this corpus --
recall *and* precision, before and after, on both of the ground truths
this repository has.

Two arms, over the two ground truths this repository already has, for the
reason `self_retrieval_rows` and `live_logged_rows` record in full: the
256-row self-retrieval set is *biased toward the unstemmed arm* by
construction, so it could not decide this on its own, and the 96-row
live-logged set -- real queries a human typed while drafting, scored
against the citekeys that chapter kept -- has no such bias. Both are
imported from the scripts that own them rather than rebuilt here.

The arms:

- **unstemmed** -- what ships: `retrieval._tokenize`'s rule, lowercase,
  `[a-z0-9]+`, the shared stopword list and a 1-2 character floor, and
  nothing else.
- **stemmed** -- the same rule with `porter_stemmer.stem` applied to
  every surviving token, on the document side and the query side alike.

**Both arms are local to this script, and that is deliberate.** #787 was
measured and **declined** on the strength of what is below, so there is
no stemmed tokenizer in `chitragupta/` to import -- and the unstemmed
arm is written out here too rather than importing the shipped
`retrieval._tokenize`, so that a later change to the shipped tokenizer
cannot silently redefine this script's "before" and make the comparison
below unreproducible. The rule is pinned here; RESULTS.md's entry is
about these two functions.

**Why precision is reported as rank quality rather than as precision@k.**
Every row of the self-retrieval set has exactly one relevant document, so
precision@5 there is recall@5 / 5 -- the same number twice, and no answer
at all to the question #787 actually asks. What over-merging costs
(`stem("relational")` is `"relat"`, `stem("agreed")` is `"agre"`) is not
a missing document but *junk above the right one*, so it shows up as
recall@1, MRR and nDCG@5 moving differently from recall@5, and as the
mean document frequency of a query's own terms rising -- which is the
mechanism, in one number: a term that matches more documents has less
IDF to contribute. `--overmerge` lists the stem classes with the most
distinct surface forms behind them, so a reader can judge the merges
rather than take a mean on trust.

**Never touches `content/retrieval_index.json`.** Both arms build their
index in memory from `retrieval._full_text`, the same
`_tokenize_item`-shaped per-document stats `retrieval_cache` would cache
-- one arm's tokenizer written into the shared on-disk cache would
corrupt real corpus state for every later run, and the disk cache has no
notion of an arm.

Stdlib-only and needs no GPU, like `bench_overlap.py`: it reads this
host's real `content/ledger.sqlite` and `content/parsed/` read-only, plus
`papers/bibliography.bib` through `bib_reader` for the keywords the
ledger deliberately does not store, and (for the live-logged set) this
book's dossiers.

    cp /workspace/config.toml .   # worktree only; gitignored per-host data
    CONTENT_DIR=/workspace/content \\
      BIB_FILE=/workspace/papers/bibliography-groups.bib \\
      .venv-full/bin/python bench/bench_retrieval_stemming.py \\
      --only self-retrieval --overmerge --tag <tag>

The live-logged set reads this book's dossiers, which are not in the live
`content/` on this host and are in the `20260901-content` snapshot, whose
ledger's `parsed_path` column still names the live `content/parsed/`
files -- so that arm points `CONTENT_DIR` at the snapshot and gets the
same parsed text either way:

    CONTENT_DIR=/workspace/content/backup/20260901-content \\
      BIB_FILE=/workspace/papers/bibliography-groups.bib \\
      .venv-full/bin/python bench/bench_retrieval_stemming.py \\
      --only live-logged --tag <tag>
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from chitragupta import ledger, retrieval  # noqa: E402
from chitragupta._passage_words import _CORE_STOPWORDS  # noqa: E402
from chitragupta.porter_stemmer import stem  # noqa: E402
from bench_retrieval_compare import ndcg_at_k, recall_at_k  # noqa: E402
from bench_retrieval_keyword_selfretrieval import build_keyword_ground_truth  # noqa: E402
from bench_retrieval_live_logs import build_live_ground_truth  # noqa: E402

K_REPORT = 5
OVERMERGE_ROWS = 15


def _unstemmed_tokens(text: str) -> list[str]:
    """`chitragupta.retrieval._tokenize`'s rule, pinned here as this
    script's "before" arm -- see the module docstring for why it is a
    copy rather than an import."""
    return [
        w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in _CORE_STOPWORDS
    ]


def _stem_token(word: str) -> str:
    """One token's Porter stem, except that a bare number is returned as
    it is -- there is nothing to strip, and this is the same guard
    `overlap_skipgram.stem_filter` applies for the same reason."""
    return word if word.isdigit() else stem(word)


def _stemmed_tokens(text: str) -> list[str]:
    """The proposed arm: the same rule, stemmed.

    The stopword list and the length floor deliberately apply to the
    *surface* form, before stemming, and a re-attempt at #787 has to keep
    that ordering. Both lists are lists of words as a reader writes them,
    and Porter's output is not a word: `stem("this")` is "thi", so a
    stopword list consulted after stemming stops recognising it, and
    `stem("does")` is "doe", so `retrieval._INTERROGATIVES` -- which
    exists to strip exactly that auxiliary (#453) -- would silently stop
    matching and hand "does" its high IDF back.
    """
    return [_stem_token(w) for w in _unstemmed_tokens(text)]


ARMS = {
    "unstemmed (as shipped)": _unstemmed_tokens,
    "stemmed (#787, proposed)": _stemmed_tokens,
}


def build_index(items, tokenize):
    """`{citekey: {"length", "term_freqs"}}` for one arm, in memory.

    Same two fields `retrieval._tokenize_item` produces, so
    `retrieval._bm25_scores` can score it unchanged -- the arm is the
    tokenizer and nothing else.
    """
    index = {}
    for item in items:
        tokens = tokenize(retrieval._full_text(item))
        index[item["citekey"]] = {"length": len(tokens), "term_freqs": dict(Counter(tokens))}
    return index


def mrr(ranked_citekeys, relevant):
    """Reciprocal rank of the first relevant hit, 0.0 if none is ranked.

    Reported alongside recall@5 because a single-relevant ground truth
    makes precision@5 a restatement of recall@5 -- where the right answer
    sits is the only precision signal such a set carries.

    Published as **`mrr@5`**, not `mrr`, and the distinction is not a
    nicety: every caller here passes a list already cut to `K_REPORT`, so
    a correct answer at rank 9 scores 0.0 exactly as one that was never
    ranked at all does. That is reciprocal rank at a cutoff, which is a
    smaller number than full MRR over the whole ledger, and a column
    labelled `mrr` would invite a reader to compare it with one.
    """
    for position, citekey in enumerate(ranked_citekeys, start=1):
        if citekey in relevant:
            return 1.0 / position
    return 0.0


def mean_doc_frequency(index, terms):
    """Mean number of documents in `index` that contain one of `terms`.

    The mechanism behind a precision loss, rather than a symptom of it:
    stemming merges term families, so each surviving term matches more
    documents and carries less IDF. A rise here with no recall gain is
    what "the merge bought nothing and cost specificity" looks like.
    """
    if not terms:
        return 0.0
    counts = [sum(1 for entry in index.values() if entry["term_freqs"].get(t)) for t in set(terms)]
    return sum(counts) / len(counts)


def score_arm(label, index, tokenize, ground_truth):
    """One row: the four ranking figures, the mean query-term document
    frequency, and the vocabulary the arm's tokenizer produced.

    A ground-truth row is `{"key", "query", "relevant"}` -- `relevant` a
    set, so the same scorer serves both ground truths here: the
    self-retrieval set's one correct paper per query and the live-logged
    set's whole chapter kept-citekey set.
    """
    recalls_1, recalls_k, rrs, ndcgs, dfs = [], [], [], [], []
    ranked_by_key = {}
    for row in ground_truth:
        terms = tokenize(row["query"])
        scores = retrieval._bm25_scores(index, terms)
        ranked = [c for c, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]
        ranked = ranked[:K_REPORT]
        ranked_by_key[row["key"]] = ranked
        relevant = row["relevant"]
        recalls_1.append(recall_at_k(ranked, relevant, 1))
        recalls_k.append(recall_at_k(ranked, relevant, K_REPORT))
        rrs.append(mrr(ranked, relevant))
        ndcgs.append(ndcg_at_k(ranked, relevant, K_REPORT))
        dfs.append(mean_doc_frequency(index, terms))
    vocabulary = {t for entry in index.values() for t in entry["term_freqs"]}
    return {
        "row": label,
        "n_queries": len(ground_truth),
        "recall@1": round(sum(recalls_1) / len(recalls_1), 4),
        f"recall@{K_REPORT}": round(sum(recalls_k) / len(recalls_k), 4),
        f"mrr@{K_REPORT}": round(sum(rrs) / len(rrs), 4),
        f"ndcg@{K_REPORT}": round(sum(ndcgs) / len(ndcgs), 4),
        "mean_query_term_df": round(sum(dfs) / len(dfs), 1),
        "index_vocabulary": len(vocabulary),
    }, ranked_by_key


def per_query_movement(before, after, ground_truth):
    """How many queries the change helped, hurt and left alone, by the
    rank of their own correct answer.

    A mean can hide a swap: a change that finds four papers it used to
    miss and loses four it used to find reports no movement at all
    (docs/AUTO-IMPROVEMENT.md's reading of `objective_delta` is the same
    hazard). These three counts are what a mean cannot say.
    """
    better, worse, same = [], [], 0
    for row in ground_truth:
        key, relevant = row["key"], row["relevant"]
        rank_before = mrr(before.get(key, []), relevant)
        rank_after = mrr(after.get(key, []), relevant)
        if rank_after > rank_before:
            better.append(key)
        elif rank_after < rank_before:
            worse.append(key)
        else:
            same += 1
    return {"better": better, "worse": worse, "unchanged": same}


def stem_classes(items):
    """Every stem in the corpus, mapped to the surface forms that reach
    it. Returned whole so a caller can say how many classes the printed
    top-N was drawn from, and how many are merges at all -- a bare
    "widest 15" reads as if 15 were the extent of it."""
    classes = defaultdict(set)
    for item in items:
        for word in set(_unstemmed_tokens(retrieval._full_text(item))):
            classes[_stem_token(word)].add(word)
    return classes


def overmerged_classes(items, limit=OVERMERGE_ROWS):
    """Stem classes with the most distinct surface forms behind them, so
    the precision risk #787 names is inspectable rather than asserted.
    Porter is aggressive in places -- "relational" and "relate" both
    become "relat" -- and a class this wide is where a reader should
    check that the merge is one they would accept.

    Returns `(rows, total_classes, merged_classes)`, so the caller can
    print what the top-N was drawn from rather than the top-N alone.
    """
    classes = stem_classes(items)
    merged = sum(1 for forms in classes.values() if len(forms) > 1)
    widest = sorted(classes.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:limit]
    rows = [{"stem": stem, "forms": sorted(forms)} for stem, forms in widest]
    return rows, len(classes), merged


# A ground truth built from author keywords gives each query 5-10 terms,
# which is not the shape #787 argues for: its case is "a short query
# naming a subject", where "with two or three query terms there is no
# redundancy to absorb a missed match". So every arm is also scored on
# the same rows narrowed to their first N keywords -- same corpus, same
# correct answer, less redundancy. `None` is the full keyword list.
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
    """The 256 author-keyword rows, in this script's row shape.

    **Biased toward the unstemmed arm, and named here rather than left
    for a reader to notice.** The query is the paper's own `keywords`
    field and the correct answer is that paper, whose text usually
    carries those keyword strings *verbatim* -- so an exact surface match
    is favoured by construction, which is the arm that does no stemming.
    That is the reason the live-logged set below is also run, and the
    reason a negative result on this set alone would not have been enough
    to decide anything.
    """
    return [
        {"key": row["citekey"], "query": row["query"], "relevant": {row["citekey"]}}
        for row in build_keyword_ground_truth()
    ]


def live_logged_rows():
    """The 96 real drafting-session queries, in this script's row shape.

    The complement to the bias above: a human typed these queries into
    `search` while writing a chapter, and the relevant set is the
    citekeys that chapter actually kept -- neither the query nor the
    answer was produced by any tokenizer, so nothing here prefers a
    surface match. Queries are free prose and not a comma-separated
    keyword list, so `QUERY_WIDTHS` does not apply to this set; they are
    already the short, subject-naming shape #787 argues for.
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
    """A fabricated difference the two arms must actually see.

    The decoy corpus says "twins" and "modelling" and never "twin" or
    "model"; the query says the singular of both. So the unstemmed arm
    must rank nothing at all and the stemmed arm must rank the paper
    first -- if either row disagrees, the arms are not the arms this
    script claims to be measuring and every figure below is about
    something else. `mrr` and `mean_doc_frequency` are checked against
    hand-worked values for the same reason.
    """
    assert mrr(["a", "b", "c"], {"b"}) == 0.5, "relevant at rank 2 is a reciprocal rank of 1/2"
    assert mrr(["a", "b"], {"z"}) == 0.0, "no relevant item anywhere must be 0, not an error"

    fake_items = [
        {
            "citekey": "plural_2024",
            "title": "cooperating digital twins and their modelling assumptions",
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
    rows = {}
    for label, tokenize in ARMS.items():
        index = build_index(fake_items, tokenize)
        row, ranked = score_arm(
            label,
            index,
            tokenize,
            [{"key": "plural_2024", "query": "twin model", "relevant": {"plural_2024"}}],
        )
        rows[label] = (row, ranked)
    unstemmed, stemmed = rows["unstemmed (as shipped)"], rows["stemmed (#787, proposed)"]
    assert unstemmed[0][f"recall@{K_REPORT}"] == 0.0, (
        "the unstemmed arm matched a document that only says the plural -- "
        "the 'before' arm is not the shipped rule"
    )
    assert stemmed[0][f"recall@{K_REPORT}"] == 1.0, (
        "the stemmed arm missed the plural document -- the 'after' arm is not stemming"
    )
    movement = per_query_movement(
        unstemmed[1], stemmed[1], [{"key": "plural_2024", "relevant": {"plural_2024"}}]
    )
    assert movement["better"] == ["plural_2024"], (
        f"per_query_movement did not see the fabricated win: {movement}"
    )

    index = build_index(fake_items, _unstemmed_tokens)
    # "twins" is in one of the two documents, "soil" in the other, so the
    # mean document frequency over both terms is exactly 1.0.
    assert mean_doc_frequency(index, ["twins", "soil"]) == 1.0, mean_doc_frequency(
        index, ["twins", "soil"]
    )

    rows, total, merged_count = overmerged_classes(fake_items, limit=50)
    merged = {c["stem"]: c["forms"] for c in rows}
    assert merged.get("model") == ["modelling"], (
        f"overmerged_classes did not fold 'modelling' onto its stem: {merged}"
    )
    assert total == len(merged), f"every class should be reported at limit=50: {total}"
    # Nothing in the two fixtures has two surface forms sharing a stem, so
    # a non-zero merged count here would mean the counter is counting
    # classes rather than merges.
    assert merged_count == 0, f"no fixture class has two forms; got {merged_count} merges"

    rows = [{"key": "x", "query": "alpha, beta, gamma, delta", "relevant": {"x"}}]
    assert narrow(rows, 2)[0]["query"] == "alpha, beta", narrow(rows, 2)
    assert narrow(rows, None)[0]["query"] == rows[0]["query"], "None must not narrow anything"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", help="results/<tag>/ to write the record into")
    parser.add_argument(
        "--overmerge",
        action="store_true",
        help=f"Also print the {OVERMERGE_ROWS} widest stem classes in the corpus",
    )
    parser.add_argument(
        "--only",
        choices=sorted(GROUND_TRUTHS),
        help="Score against one ground truth rather than both. On this "
        "host you want this: the two sets need different CONTENT_DIR "
        "values (the live corpus, and the 20260901 snapshot that still "
        "has this book's dossiers), so neither invocation builds both",
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
    for label, tokenize in ARMS.items():
        print(f"building the {label} index over {len(items)} ledger items...", flush=True)
        indexes[label] = build_index(items, tokenize)

    rows, movements = [], []
    for name in sorted(GROUND_TRUTHS):
        if args.only and name != args.only:
            continue
        # An absent input reports as absent, by name (bench/README.md's
        # rule), rather than as a traceback or as a zero. Both cases are
        # real and reachable: the live-logged set needs this book's
        # dossiers under CONTENT_DIR -- and on this host they are only in
        # the 20260901 snapshot, so the two sets need *different*
        # CONTENT_DIR values and cannot both be built from one -- and the
        # keyword set needs a bib export carrying `keywords` fields.
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
            narrowed = narrow(ground_truth, keywords)
            width = "all" if keywords is None else str(keywords)
            rankings = {}
            for label, tokenize in ARMS.items():
                row, ranked = score_arm(label, indexes[label], tokenize, narrowed)
                row["ground_truth"] = name
                row["query_keywords"] = width
                rankings[label] = ranked
                rows.append(row)
                print(f"  [{width:>3} keywords] {row}", flush=True)
            movement = per_query_movement(
                rankings["unstemmed (as shipped)"], rankings["stemmed (#787, proposed)"], narrowed
            )
            movement.update(ground_truth=name, query_keywords=width)
            movements.append(movement)
            print(
                f"  [{width:>3} keywords] per-query: {len(movement['better'])} better, "
                f"{len(movement['worse'])} worse, {movement['unchanged']} unchanged",
                flush=True,
            )

    record = {"rows": rows, "movements": movements}
    if args.overmerge:
        widest, total, merged = overmerged_classes(items)
        record["overmerged"] = widest
        record["stem_classes"] = {"total": total, "merging_two_or_more_forms": merged}
        print(
            f"\n{total:,} stem classes, {merged:,} of them merging two or more "
            f"surface forms; the {len(widest)} widest:"
        )
        for entry in widest:
            print(f"  {entry['stem']:16} {len(entry['forms']):>3}  {', '.join(entry['forms'][:8])}")

    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "stemming.json"
    out_path.write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(f"\nRecord: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

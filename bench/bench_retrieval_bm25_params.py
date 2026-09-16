"""What Okapi BM25's two free parameters (#788) are worth on this corpus
-- `k1`, how fast a term's frequency saturates, and `b`, how strongly a
document's length is normalized -- swept against the ground truths this
repository already has, at k in {3, 5, 10}.

`chitragupta/retrieval_scoring.py` shipped them as 1.5 and 0.75 with a
comment saying in as many words that they were "the usual defaults, not
tuned against this corpus specifically". They come from TREC-era ad-hoc
retrieval over news and web collections. This corpus is neither: it is a
few hundred academic PDFs whose lengths run from a four-page paper to a
whole book, which is the regime `b` exists to handle and the one where an
inherited value is least likely to be right. This script is what turns
the comment into a measurement.

**One parameter at a time** (Ni et al.'s protocol, as everywhere else
here): every row moves `k1` with `b` at its default, or `b` with `k1` at
its default, so a change is attributable to the parameter it names rather
than to a vector. There is no interaction arm, deliberately -- the
question #788 asks is "is either default wrong for this corpus", and a
full grid would mostly be reading noise off a few hundred queries.

**Three k values rather than one.** `k1` and `b` move *where* a document
lands more often than they move whether it is found at all, so a single
recall@5 hides most of what they do: a paper pushed from rank 6 to rank 4
is invisible at k = 5 alone and visible against k = 3 and k = 10 either
side of it. nDCG at each k is reported for the same reason, and the
per-query movement counts below are what a mean cannot say -- a change
that promotes four papers and demotes four reports as no movement at all.

**Both ground truths, and an absent one is reported rather than fatal.**
The self-retrieval set (256-odd author-keyword queries, from
`bench_retrieval_keyword_selfretrieval.py`) needs `papers/bibliography.bib`
through `bib_reader`; the live-logged set (96 real `search`-mode queries a
human typed while drafting, from `bench_retrieval_live_logs.py`) needs
this book's dossiers, which are gitignored per-host data that has left
`content/dossiers/` more than once. A host with only one of them still
gets a real measurement of that one, named as such, which is why this
skips a missing set by name instead of returning 2 the way
`bench_retrieval_stemming.py` does -- that script's conclusion needed
both arms to disagree; each arm here answers for itself.

**Never touches `content/retrieval_index.json`.** The index is built in
memory from `retrieval._tokenize_item`, the same per-document entry the
shipped cache holds, for the reason `bench_retrieval_stemming.py`
records: a bench run has no business writing real corpus state. Here the
parameters do not change the index at all -- `k1` and `b` are applied at
scoring time, over term frequencies that are identical in every arm --
so one index serves the whole sweep.

**`PYTHONHASHSEED` is pinned, and it is not superstition.**
`retrieval_scoring.bm25_scores` accumulates a document's score by
iterating `set(terms)`, and a `set` of strings iterates in an order that
Python randomizes per process -- so the same query's score differs in its
last bits between runs, and a near-tie can resolve either way. Measured
here across four seeds: every arm below is identical to four decimals
**except `k1 = 0.0`**, which moved recall@3 over 0.380-0.411. That is the
expected place for it, because `k1 = 0` collapses every non-zero
frequency to 1 and so manufactures ties in bulk; it is the degenerate end
of the grid rather than a row anything rests on. Pinned so the published
table reproduces, and recorded rather than quietly pinned.

Stdlib-only and needs no GPU: it reads this host's real
`content/ledger.sqlite` and `content/parsed/` read-only, plus
`papers/bibliography.bib` and (where present) this book's dossiers.

    cp config.toml.example config.toml   # worktree only; gitignored data
    PYTHONHASHSEED=0 \\
      CONTENT_DIR=/workspace/content \\
      BIB_FILE=/workspace/papers/bibliography.bib \\
      BENCH_BOOK_DOSSIERS=/workspace/content/backup/20260901-content/dossiers/books/digital-twins-for-software-engineers \\
      .venv-full/bin/python bench/bench_retrieval_bm25_params.py --tag <tag>
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from chitragupta import config, ledger, retrieval  # noqa: E402
from bench_retrieval_compare import ndcg_at_k, recall_at_k, with_field_weights  # noqa: E402
from bench_retrieval_stemming import mrr, per_query_movement  # noqa: E402
from bench_retrieval_stemming import live_logged_rows, self_retrieval_rows  # noqa: E402

# The shipped pair, and the point every arm below is read against.
BASELINE_K1 = 1.5
BASELINE_B = 0.75

# Fine below the default and coarse above it, because the curve is not
# symmetric: `k1` between 0 and 1 is a large change in how much a
# repeated term still counts, and `k1` between 8 and 12 is a small one.
# 0.0 is the degenerate end -- presence, never frequency -- and 20.0 is
# far enough out to read the other end as the asymptote it is, since
# `freq * (k1+1) / (freq + k1 * norm)` tends to `freq / norm` as `k1`
# grows: raw term frequency with the saturation removed. A grid that
# stopped at 5.0 would have reported a rising arm with no way to say
# whether it was a peak or a limit, which was the first run's own
# result and the reason this one goes further.
K1_GRID = (0.0, 0.3, 0.6, 0.9, 1.2, 1.5, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0)
# `b` is a fraction by definition, so its grid is its whole domain: 0.25
# steps up to the midpoint, then 0.125 steps around the default, where
# the resolution is worth spending. Both ends are meaningful rather than
# pathological -- 0.0 is "ignore length entirely" and 1.0 is "normalize
# in full" -- and the length spread on this corpus is exactly what #788
# suspects the inherited 0.75 of being wrong about.
B_GRID = (0.0, 0.25, 0.5, 0.625, 0.75, 0.875, 1.0)

K_VALUES = (3, 5, 10)
K_DEEPEST = max(K_VALUES)

GROUND_TRUTHS = {"self-retrieval": self_retrieval_rows, "live-logged": live_logged_rows}


def arms():
    """`(label, k1, b)` for every row, baseline first, one parameter at a
    time. The baseline pair appears once rather than twice, so the two
    arms share a point and the table has one row per distinct setting."""
    rows = [(f"baseline: k1={BASELINE_K1}, b={BASELINE_B}", BASELINE_K1, BASELINE_B)]
    rows += [(f"k1 = {k1}", k1, BASELINE_B) for k1 in K1_GRID if k1 != BASELINE_K1]
    rows += [(f"b = {b}", BASELINE_K1, b) for b in B_GRID if b != BASELINE_B]
    return rows


def with_bm25_params(k1, b):
    """Pin both parameters *and* every field weight, not just the pair a
    row names.

    The weights are pinned for the reason `with_field_weights` records:
    an arm that let one fall through to this host's `config.toml` would
    measure whatever that host happens to set. The parameters are read by
    `retrieval_scoring.bm25_scores` at call time rather than bound at
    import, which is what makes a whole grid runnable in one process.
    """
    with_field_weights({})
    config.RETRIEVAL_K1 = k1
    config.RETRIEVAL_B = b


def build_index(items):
    """The shipped per-document entry for every ledger item, in memory.

    `retrieval._tokenize_item` rather than a local copy, because nothing
    about the tokenizer is an arm here -- unlike
    `bench_retrieval_stemming.py`, where the tokenizer *is* the arm and a
    copy is what keeps its "before" pinned. One index serves every row:
    `k1` and `b` are applied over these term frequencies, never to them.
    """
    return {item["citekey"]: retrieval._tokenize_item(item) for item in items}


def rank(index, query):
    """`query`'s best `K_DEEPEST` citekeys under whatever parameters are
    currently pinned, through the shipped query rule (`_query_terms`, so
    interrogatives are stripped exactly as `search()` strips them)."""
    scores = retrieval._bm25_scores(index, retrieval._query_terms(query))
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [citekey for citekey, _score in ranked[:K_DEEPEST]]


def score_arm(label, k1, b, index, ground_truth):
    """One row: recall and nDCG at each of `K_VALUES`, plus MRR at the
    deepest, and the rankings themselves so the caller can count how many
    individual queries moved."""
    with_bm25_params(k1, b)
    ranked_by_key = {row["key"]: rank(index, row["query"]) for row in ground_truth}
    row = {"row": label, "k1": k1, "b": b, "n_queries": len(ground_truth)}
    for k in K_VALUES:
        recalls = [recall_at_k(ranked_by_key[r["key"]], r["relevant"], k) for r in ground_truth]
        ndcgs = [ndcg_at_k(ranked_by_key[r["key"]], r["relevant"], k) for r in ground_truth]
        row[f"recall@{k}"] = round(sum(recalls) / len(recalls), 4)
        row[f"ndcg@{k}"] = round(sum(ndcgs) / len(ndcgs), 4)
    rrs = [mrr(ranked_by_key[r["key"]], r["relevant"]) for r in ground_truth]
    row[f"mrr@{K_DEEPEST}"] = round(sum(rrs) / len(rrs), 4)
    return row, ranked_by_key


def self_check():
    """A fabricated corpus where each parameter *must* change the order.

    This is the check #762's own sweep learned to write, and the reason
    is that a flat curve is the likeliest outcome here: a sweep that
    silently read no parameters at all would publish exactly the same
    table as a real null result, and no figure in it could tell them
    apart.

    `long2024` says "twin" nine times in four hundred tokens; `short2024`
    says it four times in forty. At the shipped `b = 0.75` the short
    paper wins on density; with `b = 0` there is no length normalization
    left and the nine raw mentions win instead. `k1 = 0` saturates
    immediately, so frequency stops counting at all and the two tie
    exactly -- each parameter flipping the fixture in its own direction,
    which is what says the two are wired separately rather than one dial
    read twice.
    """
    index = {
        "long2024": {"length": 400, "term_freqs": {"twin": 9}, "field_freqs": {}},
        "short2024": {"length": 40, "term_freqs": {"twin": 4}, "field_freqs": {}},
    }

    def scores(k1, b):
        with_bm25_params(k1, b)
        return retrieval._bm25_scores(index, ["twin"])

    at_default = scores(BASELINE_K1, BASELINE_B)
    assert at_default["short2024"] > at_default["long2024"], (
        "at b = 0.75 the denser short paper must win -- the fixture does not "
        "exercise length normalization, so the b arm below would measure nothing"
    )
    unnormalized = scores(BASELINE_K1, 0.0)
    assert unnormalized["long2024"] > unnormalized["short2024"], (
        "b = 0 did not remove length normalization: this script is not reading "
        "config.RETRIEVAL_B, and a flat b curve below would be an artefact"
    )
    saturated = scores(0.0, BASELINE_B)
    assert saturated["long2024"] == saturated["short2024"], (
        "k1 = 0 did not collapse frequency to presence: this script is not "
        "reading config.RETRIEVAL_K1, and a flat k1 curve below would be an artefact"
    )
    assert mrr(["a", "b"], {"b"}) == 0.5, "relevant at rank 2 is a reciprocal rank of 1/2"
    with_bm25_params(BASELINE_K1, BASELINE_B)


def available_ground_truths(only):
    """`{name: rows}` for every requested set this host can actually
    build. An absent one is named on stderr and dropped rather than
    raising or scoring as a zero (bench/README.md's rule): the
    live-logged set needs this book's dossiers, which are gitignored
    per-host data, and a host without them still gets a real measurement
    of the set it does have."""
    built = {}
    for name, builder in sorted(GROUND_TRUTHS.items()):
        if only and name != only:
            continue
        try:
            rows = builder()
        except OSError as exc:
            print(f"{name}: ground truth unavailable -- {exc}", file=sys.stderr)
            continue
        if not rows:
            print(f"{name}: no rows -- check CONTENT_DIR and BIB_FILE", file=sys.stderr)
            continue
        built[name] = rows
    return built


def sweep(index, ground_truth):
    """Every arm against one ground truth, plus how many individual
    queries each arm moved against the baseline's own rankings.

    Movement is reciprocal rank over the top `K_DEEPEST`, so a correct
    answer that moves from rank 11 to rank 12 reads as unchanged -- the
    same depth every reported figure is measured at, and stated in
    `bench/RESULTS.md` beside the column rather than left to be inferred
    from it.
    """
    rows, movements, baseline_ranked = [], [], None
    for label, k1, b in arms():
        row, ranked = score_arm(label, k1, b, index, ground_truth)
        if baseline_ranked is None:
            baseline_ranked = ranked
        movement = per_query_movement(baseline_ranked, ranked, ground_truth)
        movement["row"] = label
        rows.append(row)
        movements.append(movement)
        print(
            f"  {label:28} recall@3 {row['recall@3']}  recall@5 {row['recall@5']}  "
            f"recall@10 {row['recall@10']}  ndcg@5 {row['ndcg@5']}  "
            f"[{len(movement['better'])} better, {len(movement['worse'])} worse]",
            flush=True,
        )
    return rows, movements


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", help="results/<tag>/ to write the record into")
    parser.add_argument(
        "--only", choices=sorted(GROUND_TRUTHS), help="score against one ground truth, not both"
    )
    parser.add_argument("--self-check", action="store_true", help="run the self-check and stop")
    args = parser.parse_args(argv)

    self_check()
    if args.self_check:
        print("self-check passed")
        return 0
    if not args.tag:
        print("--tag is required", file=sys.stderr)
        return 2

    ground_truths = available_ground_truths(args.only)
    if not ground_truths:
        print("no ground truth could be built -- nothing to measure", file=sys.stderr)
        return 2

    with ledger.connection() as con:
        items = ledger.all_items(con)
    print(f"building the BM25 index over {len(items)} ledger items...", flush=True)
    index = build_index(items)

    record = {"arms": [], "movements": []}
    for name, ground_truth in ground_truths.items():
        print(f"\n{name}: {len(ground_truth)} queries", flush=True)
        rows, movements = sweep(index, ground_truth)
        for row, movement in zip(rows, movements):
            record["arms"].append({**row, "ground_truth": name})
            record["movements"].append({**movement, "ground_truth": name})

    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "bm25_params.json"
    out_path.write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(f"\nRecord: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

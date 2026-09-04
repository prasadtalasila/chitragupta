"""B5 (issue #610): does fusing BM25 with dense (MiniLM-L6) retrieval beat
BM25 alone? Answers issue #617's build/decline question -- reciprocal-rank
fusion (RRF) is the candidate default, score interpolation (convex
combination) is the comparison arm named in #617's "Alternatives
Considered" -- across all three existing retrieval ground truths, at
k in {3, 5, 10}, reporting percentage-point change against BM25 alone
one arm at a time (Ni et al.'s protocol).

**Fusion granularity: citekey, after each route's own within-route
cap/dedup, not raw chunks.** Every ground truth here scores recall/nDCG
over *citekeys* (bench_retrieval_compare.py's `collapse_to_citekeys`), so
fusing chunk-level dense hits before collapsing would optimize an order
no metric here reads. BM25 (`chitragupta.retrieval.search()`) is already
one row per citekey by construction; the dense side is collapsed with
the same `collapse_to_citekeys` bench_retrieval_compare.py's own dense
rows use, over a pool already capped at
`config.EMBED_MAX_PASSAGES_PER_SOURCE` passages per citekey
(`chitragupta.enrich.embed_index.search()`). Fusing two citekey-once
rankings can only ever produce a citekey-once result -- #617's "per-source
cap and cross-query deduplication hold after fusion" holds by
construction, not by a check added after the fact.

RRF reuses `chitragupta.discover._resolve.rrf_fuse`/`RRF_K` (Cormack et
al., 2009) rather than reimplementing it -- the same fusion the
topic-discovery ladder already runs at topic level (issue #617's own
"the mechanism exists in the codebase"). The convex arm min-max
normalizes each route's scores to [0, 1] *within that query's own
candidate pool* (BM25's raw score by its pool max; dense distance by the
pool's [min, max] span, inverted so closer is higher) and combines with
a fixed ALPHA -- documented, not tuned, since #617 asks whether fusion
helps at all, not for a calibrated weight.

Dense model is fixed to MiniLM-L6, per #617's proposed solution -- not
swept the way bench_retrieval_compare.py sweeps three drop-in models --
so EMBEDDING_MODEL is forced before any `chitragupta` import rather than
read from config.toml, which may name a different default model.

Also adds one assertion-form query template to
bench_retrieval_keyword_selfretrieval.py's query-shape sweep (E1's
`forms` dict) -- B5's other, unrelated-to-fusion ask for this issue.

    .venv-full/bin/python bench/bench_retrieval_fusion.py \\
        --drafts content/drafts/books/digital-twins-for-software-engineers \\
        --tag 2026-09-04-retrieval-fusion
"""

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

# Must happen before the first `chitragupta` import: config.EMBEDDING_MODEL
# is bound at import time, and B5 fixes the dense route to MiniLM-L6
# regardless of what config.toml names as the project default.
os.environ["EMBEDDING_MODEL"] = "sentence-transformers/all-MiniLM-L6-v2"

from chitragupta import retrieval  # noqa: E402
from chitragupta.enrich import embed_index  # noqa: E402
from chitragupta.discover._resolve import RRF_K, rrf_fuse  # noqa: E402

import bench_retrieval_ground_truth as gt_pairs  # noqa: E402
import bench_retrieval_keyword_selfretrieval as gt_self  # noqa: E402
import bench_retrieval_live_logs as gt_live  # noqa: E402
from bench_retrieval_compare import (  # noqa: E402
    K_POOL,
    collapse_to_citekeys,
    ndcg_at_k,
    recall_at_k,
)

K_SWEEP = (3, 5, 10)
ALPHA = 0.5  # equal weight between the two normalized routes


def _bm25_ranked_with_scores(query, k_pool):
    return [(r.citekey, r.score) for r in retrieval.search(query, k=k_pool)]


def _dense_ranked_with_scores(query, k_pool):
    """Collapsed to one entry per citekey with `collapse_to_citekeys`
    (imported, not reimplemented) over a pool `embed_index.search()`
    already capped per source -- see the module docstring."""
    hits = embed_index.search(query, k=k_pool)
    order = collapse_to_citekeys(hits)
    best_distance = {}
    for hit in hits:
        best_distance.setdefault(hit["citekey"], hit["distance"])
    return [(citekey, best_distance[citekey]) for citekey in order]


def convex_fuse(bm25_ranked, dense_ranked, alpha=ALPHA):
    """Score interpolation: the comparison arm named in #617's
    "Alternatives Considered", kept for exactly the reason stated
    there -- RRF needs no per-query score calibration and convex does,
    so this arm exists to show what that calibration costs or buys."""
    bm25_scores = dict(bm25_ranked)
    dense_distances = dict(dense_ranked)

    max_bm25 = max(bm25_scores.values(), default=0.0) or 1.0
    distances = list(dense_distances.values())
    min_d, max_d = (min(distances), max(distances)) if distances else (0.0, 0.0)
    span = (max_d - min_d) or 1.0

    combined = {}
    for citekey in set(bm25_scores) | set(dense_distances):
        bm25_norm = bm25_scores.get(citekey, 0.0) / max_bm25
        dense_norm = (
            1.0 - (dense_distances[citekey] - min_d) / span if citekey in dense_distances else 0.0
        )
        combined[citekey] = alpha * bm25_norm + (1 - alpha) * dense_norm
    return [citekey for citekey, _ in sorted(combined.items(), key=lambda kv: (-kv[1], kv[0]))]


def fused_rankings(query, k_pool=K_POOL):
    """One ranked citekey list per arm: BM25 alone (the baseline every
    other arm is a percentage-point change against), RRF, and convex."""
    bm25_ranked = _bm25_ranked_with_scores(query, k_pool)
    dense_ranked = _dense_ranked_with_scores(query, k_pool)
    bm25_citekeys = [citekey for citekey, _ in bm25_ranked]
    dense_citekeys = [citekey for citekey, _ in dense_ranked]
    rrf_citekeys = [label for label, _ in rrf_fuse([bm25_citekeys, dense_citekeys])]
    convex_citekeys = convex_fuse(bm25_ranked, dense_ranked)
    return {"bm25": bm25_citekeys, "rrf": rrf_citekeys, "convex": convex_citekeys}


def self_check():
    """Two synthetic single-query scenarios, no corpus or model needed --
    proving each arm sees a real difference before its number is
    believed, per bench/README.md's convention.

    (1) RRF must actually change the order BM25 alone would give, not
    pass it through: bm25 ranks a, b, c but dense ranks c, a, b -- c's
    strong dense showing must promote it ahead of b (RRF sums are
    a=1/61+1/62, b=1/62+1/64, c=1/63+1/61; c > b).

    (2) Convex must respond to a citekey BM25 never saw at all if its
    dense distance is excellent -- something a rank-only fusion expresses
    weakly (rank last-plus-one) and a real-valued one expresses directly.
    bm25 ranks a > b; b never appears in dense; c never appears in bm25
    but has the best possible dense distance. At alpha=0.5, c's score
    (0.5 * 0 + 0.5 * 1.0 = 0.5) must exceed b's (0.5 * 0.5 + 0.5 * 0 =
    0.25), promoting a citekey lexical search missed entirely above one
    it weakly matched.
    """
    assert RRF_K == 60, "self_check's hand-worked RRF sums assume RRF_K == 60"

    bm25_citekeys = ["a", "b", "c"]
    dense_citekeys = ["c", "a", "b"]
    rrf_result = [label for label, _ in rrf_fuse([bm25_citekeys, dense_citekeys])]
    assert rrf_result == ["a", "c", "b"], (
        f"RRF must promote c (dense-favoured) ahead of b (BM25 rank 2, dense-worst): {rrf_result}"
    )

    bm25_ranked = [("a", 10.0), ("b", 5.0)]
    dense_ranked = [("c", 0.0), ("a", 1.0)]
    convex_result = convex_fuse(bm25_ranked, dense_ranked)
    assert convex_result.index("c") < convex_result.index("b"), (
        "convex combination must surface a dense-only, BM25-blind citekey "
        f"above a weak BM25-only match: {convex_result}"
    )

    assert collapse_to_citekeys(
        [
            {"citekey": "x", "distance": 0.1},
            {"citekey": "x", "distance": 0.2},
            {"citekey": "y", "distance": 0.3},
        ]
    ) == ["x", "y"], (
        "dense collapse must keep first-seen (best-ranked) order, one entry per citekey"
    )


def _generic_score(ranked_by_key, rows, key_fn, relevant_fn, k):
    recalls, ndcgs, missing = [], [], 0
    for row in rows:
        ranked = ranked_by_key.get(key_fn(row))
        if ranked is None:
            missing += 1
            continue
        relevant = relevant_fn(row)
        recalls.append(recall_at_k(ranked, relevant, k))
        ndcgs.append(ndcg_at_k(ranked, relevant, k))
    return {
        "n_queries": len(rows) - missing,
        "n_missing": missing,
        "recall": round(sum(recalls) / len(recalls), 4) if recalls else None,
        "ndcg": round(sum(ndcgs) / len(ndcgs), 4) if ndcgs else None,
    }


def _live_rows(args):
    """`gt_live.BOOK_DOSSIERS` is bound at that module's import time from
    `config.CONTENT_DIR`, which this run points at the live corpus for the
    ledger and the dense index -- but the live corpus carries no
    `dossiers/books/...` any more (#606-era content churn). `--dossiers`
    points this one read at wherever a synced dossiers tree for the book
    actually is (a content/backup/ snapshot, by default), by patching the
    module constant rather than re-deriving CONTENT_DIR, since ledger
    citekeys must still resolve against the live ledger this process
    already loaded."""
    gt_live.BOOK_DOSSIERS = Path(args.dossiers)
    return gt_live.build_live_ground_truth()


GROUND_TRUTHS = {
    "self-retrieval": {
        "rows_fn": lambda args: gt_self.build_keyword_ground_truth(),
        "query_fn": lambda row: row["query"],
        "key_fn": lambda row: row["citekey"],
        "relevant_fn": lambda row: {row["citekey"]},
    },
    "drafting-pair": {
        "rows_fn": lambda args: gt_pairs.build_ground_truth(args.drafts),
        "query_fn": lambda row: row["query"],
        "key_fn": lambda row: (row["chapter"], row["line"], row["citekey"]),
        "relevant_fn": lambda row: {row["citekey"]},
    },
    "live-logged": {
        "rows_fn": lambda args: _live_rows(args),
        "query_fn": lambda row: row["query"],
        "key_fn": lambda row: (row["chapter"], row["query_index"]),
        "relevant_fn": lambda row: set(row["citekeys"]),
    },
}


def score_ground_truth(name, spec, args):
    rows = spec["rows_fn"](args)
    print(f"{name}: {len(rows)} rows", flush=True)
    ranked_by_key = {"bm25": {}, "rrf": {}, "convex": {}}
    for i, row in enumerate(rows):
        if i and i % 25 == 0:
            print(f"  {name}: {i}/{len(rows)}", flush=True)
        key = spec["key_fn"](row)
        fused = fused_rankings(spec["query_fn"](row))
        for arm in ranked_by_key:
            ranked_by_key[arm][key] = fused[arm]

    result = {"ground_truth": name, "n_rows": len(rows), "by_k": {}}
    for k in K_SWEEP:
        arm_scores = {
            arm: _generic_score(ranked_by_key[arm], rows, spec["key_fn"], spec["relevant_fn"], k)
            for arm in ranked_by_key
        }
        bm25 = arm_scores["bm25"]
        for arm in ("rrf", "convex"):
            for metric in ("recall", "ndcg"):
                base, value = bm25[metric], arm_scores[arm][metric]
                arm_scores[arm][f"{metric}_delta_pp"] = (
                    round((value - base) * 100, 2)
                    if base is not None and value is not None
                    else None
                )
        result["by_k"][k] = arm_scores
    return result


def _print_report(results):
    for result in results:
        print(f"\n{result['ground_truth']} ({result['n_rows']} rows)")
        print(f"{'k':>3}  {'arm':8}  {'n':>4}  {'recall':>7}  {'Δpp':>6}  {'ndcg':>7}  {'Δpp':>6}")
        for k, arms in sorted(result["by_k"].items()):
            for arm in ("bm25", "rrf", "convex"):
                row = arms[arm]
                print(
                    f"{k:>3}  {arm:8}  {row['n_queries']:>4}  "
                    f"{row['recall']:>7}  {row.get('recall_delta_pp', ''):>6}  "
                    f"{row['ndcg']:>7}  {row.get('ndcg_delta_pp', ''):>6}"
                )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tag", required=True, help="names bench/results/<tag>/")
    ap.add_argument(
        "--drafts",
        default=str(
            gt_live.config.CONTENT_DIR / "drafts" / "books" / "digital-twins-for-software-engineers"
        ),
        help="book used to rebuild the 48-pair drafting-pair ground truth",
    )
    ap.add_argument(
        "--dossiers",
        default=str(
            gt_live.config.CONTENT_DIR
            / "backup"
            / "20260901-content"
            / "dossiers"
            / "books"
            / "digital-twins-for-software-engineers"
        ),
        help="book dossiers tree used to rebuild the live-logged ground truth",
    )
    ap.add_argument(
        "--only",
        choices=sorted(GROUND_TRUTHS),
        nargs="+",
        default=None,
        help="run a subset of ground truths (default: all three)",
    )
    args = ap.parse_args(argv)

    self_check()

    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    out_dir.mkdir(parents=True, exist_ok=True)
    record = out_dir / "fusion.json"

    # Written after each ground truth, not once at the end: one ground
    # truth's build (e.g. drafting-pair's stale-snapshot ValueError) must
    # not cost an already-computed one its result -- the earlier full-suite
    # run losing self-retrieval's numbers to a later live-logged crash is
    # exactly the failure this guards against.
    names = args.only if args.only else sorted(GROUND_TRUTHS)
    results = []
    for name in names:
        results.append(score_ground_truth(name, GROUND_TRUTHS[name], args))
        record.write_text(json.dumps(results, indent=1), encoding="utf-8")

    _print_report(results)
    print(f"\nRecord: {record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

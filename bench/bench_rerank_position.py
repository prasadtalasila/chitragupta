"""Where a cross-encoder rerank sits relative to the per-citekey cap
(#380), measured on the shipped pipeline's own shape rather than on a
citekey-level ranking.

bench_retrieval_compare.py already scores "dense, alone and reranked"
against three ground truths, and RESULTS.md records the answer: BM25
wins. Those rows do not answer #380, for a reason worth stating before
anyone quotes them at this script. They pool 50 chunks, rerank, then
`collapse_to_citekeys(...)[:5]` -- collapsing the whole pool to distinct
papers *is* a per-citekey cap of 1, applied after the rerank, over a
pool 2.5x deeper than the shipped one. The shipped
`embed_index.search()` returns **chunks**, caps at
`EMBED_MAX_PASSAGES_PER_SOURCE` (3), and over-fetches `k * 4` (20). A
cap of 1 over 50 and a cap of 3 over 20 can disagree about which
document survives, which is precisely #380's question, so the recorded
rows cannot settle it either way.

Five arms, over the same queries:

    1. dense-shipped        pool -> cap -> truncate      (embed_index.search today)
    2. rerank-before-cap    pool -> rerank -> cap -> truncate   (#380's stated order)
    3. rerank-after-cap     pool -> cap -> truncate -> rerank   (the rejected order)
    4. bm25-shipped         retrieval.search(k)          (what drafting sessions call)
    5. bm25+rerank          retrieval.search(k*4) -> rerank -> k

Arm 5 is the row RESULTS.md's own "Not measured here" names as missing.
It is here because #380 scopes the reranker to `embed_index.py`, and a
plan should know whether reranking the retriever that actually wins
beats reranking the one that does not.

`distinct@5` is reported because it, not recall, is what #380's
motivating claim is about: "fewer passages per source is what makes
multi-source units reachable". No existing row measures it. `recall@3`
is here for the same reason -- "better ordering means fewer passages are
needed" predicts reranked recall@3 close to unreranked recall@5.

Read-only against `content/` (the bench_overlap.py precedent); writes
only under bench/results/<tag>/.

    CHITRAGUPTA_PROJECT=/workspace .venv-full/bin/python \\
        bench/bench_rerank_position.py --tag 2026-08-26-rerank-position
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(BENCH_DIR))

from chitragupta import config, retrieval  # noqa: E402
from bench_retrieval_compare import RERANK_MODEL, ndcg_at_k, collapse_to_citekeys  # noqa: E402
from bench_retrieval_keyword_selfretrieval import build_keyword_ground_truth  # noqa: E402

K_REPORT = 5
K_SHALLOW = 3  # the "fewer passages are needed" bar, per #380's compounding claim


def rerank(hits, query, scorer):
    """Best-first reorder of `hits` by `scorer` over (query, snippet).

    `scorer` is injected rather than constructed here so `self_check`
    can drive both cap positions with a stub whose ordering is known --
    the same reason #380 asks for the shipped tests to use one: the
    ordering is what is under test, not a model's judgement.
    """
    scores = scorer([(query, hit["snippet"]) for hit in hits])
    return [hit for _score, hit in sorted(zip(scores, hits), key=lambda pair: -pair[0])]


def cap_and_truncate(hits, cap, k):
    """`embed_index.search()`'s own cap-then-truncate, lifted out verbatim.

    Lifted rather than called so the three dense arms differ *only* in
    where `rerank` is applied. `_replication_matches_shipped` asserts
    this really is what ships, so an arm cannot quietly measure a
    reimplementation that drifted.
    """
    kept, per_source = [], {}
    for hit in hits:
        citekey = hit["citekey"]
        if per_source.get(citekey, 0) >= cap:
            continue
        per_source[citekey] = per_source.get(citekey, 0) + 1
        kept.append(hit)
        if len(kept) == k:
            break
    return kept


def score_arm(returned_by_query, ground_truth):
    """Metrics over what the caller is actually handed: a ranked list of
    *passages*. recall@n asks whether the correct citekey is among the
    citekeys of the first n slots -- for BM25 that is one paper per slot,
    for the dense arms it need not be, and that asymmetry is the finding
    rather than a flaw in the metric. nDCG@5 is computed on the
    de-duplicated citekey order so it stays comparable in method to the
    tables bench_retrieval_compare.py already produced.
    """
    shallow, deep, ndcgs, distincts, empties = [], [], [], [], 0
    for row in ground_truth:
        hits = returned_by_query.get(row["citekey"])
        if hits is None:
            continue
        if not hits:
            empties += 1
        citekeys = [hit["citekey"] for hit in hits]
        relevant = {row["citekey"]}
        shallow.append(1.0 if any(c in relevant for c in citekeys[:K_SHALLOW]) else 0.0)
        deep.append(1.0 if any(c in relevant for c in citekeys[:K_REPORT]) else 0.0)
        ndcgs.append(ndcg_at_k(collapse_to_citekeys(hits), relevant, K_REPORT))
        distincts.append(len(set(citekeys[:K_REPORT])))
    return {
        "n_queries": len(deep),
        "n_empty": empties,
        f"recall@{K_SHALLOW}": round(statistics.fmean(shallow), 4),
        f"recall@{K_REPORT}": round(statistics.fmean(deep), 4),
        f"ndcg@{K_REPORT}": round(statistics.fmean(ndcgs), 4),
        f"distinct@{K_REPORT}": round(statistics.fmean(distincts), 3),
    }


def compare_arms(left, right, ground_truth):
    """How often two arms hand back a different *set* of papers, how often
    merely a different order of the same set, and -- the part that
    decides how the churn may be read -- how many of those changes moved
    the correct answer in or out.

    The split is the point. If two cap positions only ever reorder the
    same papers, #380's property -- a promotion changing *which
    document* survives -- is real but unobservable on real queries, and
    the plan has to say so rather than cite a measurement it does not
    have.

    `lost`/`gained` exist because a large `set_differs` beside an
    unchanged recall has two readings that lead to opposite plans: the
    swaps traded right answers evenly (`lost` and `gained` both
    non-zero), or the churn never touched the answer at all
    (`lost == gained == 0`), which would make this ground truth blind to
    the effect rather than neutral about it. Reporting only the totals
    would let either be quoted as the other.
    """
    set_differs, order_differs, lost, gained = 0, 0, 0, 0
    for row in ground_truth:
        a = [hit["citekey"] for hit in left.get(row["citekey"], [])]
        b = [hit["citekey"] for hit in right.get(row["citekey"], [])]
        if set(a) != set(b):
            set_differs += 1
        elif a != b:
            order_differs += 1
        hit_left, hit_right = row["citekey"] in a, row["citekey"] in b
        lost += hit_left and not hit_right
        gained += hit_right and not hit_left
    total = len(ground_truth)
    return {
        "n": total,
        "set_differs": set_differs,
        "order_differs": order_differs,
        "set_differs_pct": round(100.0 * set_differs / total, 1),
        "lost": lost,
        "gained": gained,
    }


def pool_rank_profile(pools, ground_truth):
    """Where in the raw, distance-ranked pool the correct paper's best
    chunk actually sits.

    A benchmark whose answer is almost always at pool rank 1 cannot
    observe a reordering downstream of it: rank 1 survives any cap in
    any order, so every arm scores the same and the harness looks
    neutral when it is really blind. This profile is what lets the
    write-up tell those apart, and it belongs in the methodology note
    rather than in the results table.
    """
    ranks, absent = [], 0
    for pool, row in zip(pools, ground_truth):
        citekeys = collapse_to_citekeys(pool)
        if row["citekey"] in citekeys:
            ranks.append(citekeys.index(row["citekey"]) + 1)
        else:
            absent += 1
    ranks.sort()
    return {
        "n": len(ground_truth),
        "absent_from_pool": absent,
        "median_rank": statistics.median(ranks) if ranks else None,
        "at_rank_1": sum(1 for r in ranks if r == 1),
        "at_rank_1_to_3": sum(1 for r in ranks if r <= 3),
        "beyond_rank_5": sum(1 for r in ranks if r > 5),
    }


def self_check():
    """Plant a reranking that must change *which document* survives the
    cap, and assert the two arms disagree about it -- bench/'s
    convention that a script publishing a number first fabricates the
    difference it claims to detect.

    The pool is three chunks of A, then one each of B and C, ranked by
    distance. With cap=2, k=3 the shipped order keeps {A, A, B}. The
    stub scorer promotes C's only chunk and A's *third* chunk to the
    front, so reranking before the cap keeps {C, A, A} -- C is in and B
    is out. Reranking after the cap can only ever reorder {A, A, B},
    because the cap already decided the composition. A stub, not a
    model: the ordering is under test, not anyone's judgement.
    """
    pool = [
        {"citekey": "A", "snippet": "a1"},
        {"citekey": "A", "snippet": "a2"},
        {"citekey": "A", "snippet": "a3"},
        {"citekey": "B", "snippet": "b1"},
        {"citekey": "C", "snippet": "c1"},
    ]
    planted = {"c1": 9.0, "a3": 8.0, "a1": 3.0, "a2": 2.0, "b1": 1.0}

    def stub_scorer(pairs):
        return [planted[snippet] for _query, snippet in pairs]

    shipped = cap_and_truncate(pool, cap=2, k=3)
    assert [h["citekey"] for h in shipped] == ["A", "A", "B"], shipped

    before = cap_and_truncate(rerank(pool, "q", stub_scorer), cap=2, k=3)
    after = rerank(cap_and_truncate(pool, cap=2, k=3), "q", stub_scorer)
    assert [h["citekey"] for h in before] == ["C", "A", "A"], before
    assert {h["citekey"] for h in before} == {"A", "C"}
    assert {h["citekey"] for h in after} == {"A", "B"}
    assert {h["citekey"] for h in before} != {h["citekey"] for h in after}, (
        "the planted promotion did not change which document survived -- "
        "this harness cannot detect the effect it exists to measure"
    )

    ground_truth = [{"citekey": "A"}, {"citekey": "Z"}]
    scored = score_arm({"A": before, "Z": after}, ground_truth)
    assert scored[f"recall@{K_REPORT}"] == 0.5, scored
    assert scored[f"distinct@{K_REPORT}"] == 2.0, scored
    delta = compare_arms({"A": before}, {"A": after}, [{"citekey": "A"}])
    assert delta["set_differs"] == 1 and delta["order_differs"] == 0, delta
    assert delta["lost"] == 0 and delta["gained"] == 0, delta
    swap = compare_arms({"C": before}, {"C": after}, [{"citekey": "C"}])
    assert (swap["lost"], swap["gained"]) == (1, 0), (
        "a set change that drops the correct paper must be counted as a loss -- "
        "otherwise an unchanged recall cannot be told from an unobserved one"
    )
    profile = pool_rank_profile([pool], [{"citekey": "B"}])
    assert profile["median_rank"] == 2 and profile["at_rank_1"] == 0, profile


def dense_pools(queries, k):
    """The over-fetched, distance-ranked chunk list `embed_index.search()`
    works from, for every query at once.

    The over-fetch multiplier and `snippet_chars` are read from config
    rather than restated, so a change to either moves this benchmark
    with the pipeline instead of leaving it measuring last release's
    shape.
    """
    from chitragupta.enrich import embed_index

    client, model = embed_index.get_client_and_model()
    collection = client.get_or_create_collection(embed_index.collection_name())
    embeddings = model.encode(queries, show_progress_bar=True, batch_size=64).tolist()
    raw = collection.query(
        query_embeddings=embeddings, n_results=k * config.EMBED_OVERFETCH_MULTIPLIER
    )
    pools = []
    for docs, metas, distances in zip(raw["documents"], raw["metadatas"], raw["distances"]):
        pools.append(
            [
                {**meta, "snippet": doc[:500], "distance": distance}
                for doc, meta, distance in zip(docs, metas, distances)
            ]
        )
    return pools


def assert_replication_matches_shipped(pools, queries, cap, k, sample=5):
    """`cap_and_truncate` over `dense_pools` must reproduce
    `embed_index.search()` exactly, or every dense arm here is measuring
    a reimplementation rather than the pipeline. Checked on real queries
    against the real collection, because that is the only place the two
    could diverge; a sample, because each call re-encodes a query.
    """
    from chitragupta.enrich import embed_index

    for query, pool in list(zip(queries, pools))[:sample]:
        shipped = [hit["citekey"] for hit in embed_index.search(query, k=k)]
        replicated = [hit["citekey"] for hit in cap_and_truncate(pool, cap, k)]
        assert shipped == replicated, (
            f"replication drifted from embed_index.search() on {query[:60]!r}: "
            f"{shipped} != {replicated}"
        )


def bm25_pools(queries, k):
    """BM25's own over-fetched list, in the same dict shape as the dense
    pools so one `rerank` serves both arms. No cap is applied or needed:
    `retrieval.search()` is one result per citekey by construction
    (issue #305), which is exactly why arm 5 has no cap-position
    question to answer.
    """
    return [
        [
            {"citekey": r.citekey, "snippet": r.snippet, "score": r.score}
            for r in retrieval.search(query, k=k)
        ]
        for query in queries
    ]


def run(ground_truth, k, cap, rerank_model):
    queries = [row["query"] for row in ground_truth]
    citekeys = [row["citekey"] for row in ground_truth]
    from sentence_transformers import CrossEncoder

    reranker = CrossEncoder(rerank_model)
    scorer = reranker.predict

    print(f"embedding {len(queries)} queries and pooling {k * 4} chunks each ...")
    pools = dense_pools(queries, k)
    assert_replication_matches_shipped(pools, queries, cap, k)

    print("reranking the dense pools ...")
    reranked_pools = [rerank(pool, query, scorer) for query, pool in zip(queries, pools)]

    arms = {
        "1 dense-shipped (pool -> cap -> k)": [cap_and_truncate(p, cap, k) for p in pools],
        "2 dense +rerank BEFORE cap (#380)": [cap_and_truncate(p, cap, k) for p in reranked_pools],
        "3 dense +rerank AFTER cap": [
            rerank(cap_and_truncate(p, cap, k), q, scorer) for q, p in zip(queries, pools)
        ],
    }

    print(f"running BM25 over {len(queries)} queries ...")
    bm25_shallow = bm25_pools(queries, k)
    bm25_deep = bm25_pools(queries, k * 4)
    arms["4 bm25-shipped (retrieval.search)"] = bm25_shallow
    print("reranking BM25's over-fetched list ...")
    arms["5 bm25 over-fetch +rerank -> k"] = [
        rerank(pool, query, scorer)[:k] for query, pool in zip(queries, bm25_deep)
    ]

    by_arm = {name: dict(zip(citekeys, hits)) for name, hits in arms.items()}
    rows = [{"row": name, **score_arm(by_arm[name], ground_truth)} for name in arms]
    deltas = {
        "arm2 vs arm3 (rerank before vs after the cap)": compare_arms(
            by_arm["2 dense +rerank BEFORE cap (#380)"],
            by_arm["3 dense +rerank AFTER cap"],
            ground_truth,
        ),
        "arm1 vs arm2 (does reranking change what ships)": compare_arms(
            by_arm["1 dense-shipped (pool -> cap -> k)"],
            by_arm["2 dense +rerank BEFORE cap (#380)"],
            ground_truth,
        ),
        "arm4 vs arm5 (does reranking help the winner)": compare_arms(
            by_arm["4 bm25-shipped (retrieval.search)"],
            by_arm["5 bm25 over-fetch +rerank -> k"],
            ground_truth,
        ),
    }
    return rows, deltas, pool_rank_profile(pools, ground_truth)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tag", required=True, help="names bench/results/<tag>/")
    ap.add_argument("--limit", type=int, default=None, help="first N ground-truth rows only")
    ap.add_argument(
        "--rerank-model",
        default=RERANK_MODEL,
        help="cross-encoder to score (query, passage) pairs with; the default is the "
        "one bench_retrieval_compare.py already used, so its rows stay comparable",
    )
    args = ap.parse_args(argv)

    self_check()

    ground_truth = build_keyword_ground_truth()
    if args.limit:
        ground_truth = ground_truth[: args.limit]
    k, cap = K_REPORT, config.EMBED_MAX_PASSAGES_PER_SOURCE
    print(
        f"{len(ground_truth)} keyword self-retrieval queries; "
        f"k={k}, cap={cap}, model={config.EMBEDDING_MODEL}, reranker={args.rerank_model}"
    )
    rows, deltas, profile = run(ground_truth, k, cap, args.rerank_model)

    header = f"{'row':38} {'n':>4} {'r@3':>7} {'r@5':>7} {'nDCG@5':>7} {'distinct@5':>11}"
    print(f"\n{header}\n{'-' * len(header)}")
    for row in rows:
        print(
            f"{row['row']:38} {row['n_queries']:>4} "
            f"{row[f'recall@{K_SHALLOW}']:>7} {row[f'recall@{K_REPORT}']:>7} "
            f"{row[f'ndcg@{K_REPORT}']:>7} {row[f'distinct@{K_REPORT}']:>11}"
        )
    print()
    for name, delta in deltas.items():
        print(
            f"{name}: {delta['set_differs']}/{delta['n']} queries "
            f"({delta['set_differs_pct']}%) return a different set of papers, "
            f"{delta['order_differs']} differ only in order; "
            f"the correct paper was lost {delta['lost']}x, gained {delta['gained']}x"
        )
    print(
        f"\ndense pool ({k * 4} chunks): correct paper at median rank "
        f"{profile['median_rank']}, rank 1 for {profile['at_rank_1']}/{profile['n']}, "
        f"top 3 for {profile['at_rank_1_to_3']}, beyond rank 5 for "
        f"{profile['beyond_rank_5']}, absent for {profile['absent_from_pool']}"
    )

    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    out_dir.mkdir(parents=True, exist_ok=True)
    record = out_dir / "rerank_position.json"
    record.write_text(
        json.dumps(
            {
                "k": k,
                "cap": cap,
                "embedding_model": config.EMBEDDING_MODEL,
                "rerank_model": args.rerank_model,
                "rows": rows,
                "deltas": deltas,
                "dense_pool_rank_profile": profile,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"\nRecord: {record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

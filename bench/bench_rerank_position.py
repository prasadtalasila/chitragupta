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

from chitragupta import config, ledger, retrieval  # noqa: E402
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


def row_key(row):
    """What a ground-truth row is keyed on when its arm's results are
    looked up.

    A keyword self-retrieval row is one query per citekey, so the citekey
    is a key. A live-log row is one query per *chapter*, and the same
    query text occurs in more than one chapter -- so those carry their own
    `key` and this returns it rather than inventing a second convention.
    """
    return row.get("key", row.get("citekey"))


def relevant_set(row):
    """The citekeys that count as correct for one row.

    A set for both ground truths, because the live logs have no finer
    relevance than "a citekey this chapter kept" -- `retrieval.md` records
    a query's text and result count, never which citekeys came back.
    """
    return set(row["citekeys"]) if "citekeys" in row else {row["citekey"]}


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
        hits = returned_by_query.get(row_key(row))
        if hits is None:
            continue
        if not hits:
            empties += 1
        citekeys = [hit["citekey"] for hit in hits]
        relevant = relevant_set(row)
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
        a = [hit["citekey"] for hit in left.get(row_key(row), [])]
        b = [hit["citekey"] for hit in right.get(row_key(row), [])]
        if set(a) != set(b):
            set_differs += 1
        elif a != b:
            order_differs += 1
        relevant = relevant_set(row)
        hit_left = bool(relevant & set(a))
        hit_right = bool(relevant & set(b))
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
        found = [citekeys.index(c) + 1 for c in relevant_set(row) if c in citekeys]
        if found:
            ranks.append(min(found))
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


# ---------------------------------------------------------------------------
# Issue 786: what the cross-encoder is handed, rather than where it sits.
#
# Same pools, same cap, same order (rerank before the cap, per #380) --
# only the *text* of the passage side of each scored pair changes. Arm C
# is not a shipping candidate: it is the diagnostic for "the title
# dominates", which is the first of the two failure modes the issue
# names. See plans/786-title-augmented-rerank-input.md for the arms, the
# ground-truth leak this controls for, and the bar fixed before the run.
# ---------------------------------------------------------------------------


def titled(hit):
    """786's proposed passage text: the source title, then the snippet.

    Falls back to the bare snippet when the title is missing or empty --
    `metadata["title"]` is whatever the bib entry had, and an entry with
    no title is not a reason to hand the model a leading blank line.
    That fallback is also what the shipped code would have to do, so
    measuring it here measures the change as it would ship.
    """
    title = (hit.get("title") or "").strip()
    return f"{title}\n\n{hit['snippet']}" if title else hit["snippet"]


NO_RERANK = "0 no rerank (shipped default)"

RENDERS = {
    "A snippet only (shipped)": lambda hit: hit["snippet"],
    "B title + snippet (786)": titled,
    "C title only (diagnostic)": lambda hit: (hit.get("title") or "").strip() or hit["snippet"],
}


def score_pool(pool, query, scorer, render):
    """Raw cross-encoder scores for one pool under one rendering, kept
    rather than discarded: the within-document diagnostic below is about
    the *scores*, not the ordering they produce, and re-scoring to get
    them back would double the run's cost.
    """
    # `float`, not the model's own numpy scalar: these scores are written
    # into the JSON record, and a float32 is not serializable.
    return [float(score) for score in scorer([(query, render(hit)) for hit in pool])]


def order_by_scores(pool, scores):
    """`_rerank.rerank`'s sort, driven by scores computed elsewhere.

    Same expression as `rerank` above -- sorted on the negated score
    alone, so ties keep the pool's distance order via the stable sort.
    That tie behaviour is not incidental here: it is how a rendering
    that compresses scores toward each other stops reordering at all.
    """
    return [hit for _score, hit in sorted(zip(scores, pool), key=lambda pair: -pair[0])]


def within_doc_profile(pools, scores_by_pool):
    """How much a rendering lets the reranker discriminate *between chunks
    of the same paper* -- the comparison the issue's own failure mode 1 is
    about, and the one a shared title prefix cannot inform.

    No chunk-level relevance labels exist on this corpus and none are
    invented. Two label-free measures over every (query, citekey) group
    with at least two chunks in the pool:

      * the score spread (max - min), in the reranker's own units; and
      * whether the group's order is unchanged from the bi-encoder's
        distance order, which is what a compressed spread plus a stable
        sort produces.

    A fall in spread beside a rise in "order unchanged" is the
    discrimination loss happening, without needing to know which chunk
    was the right one.
    """
    spreads, unchanged, groups = [], 0, 0
    for pool, scores in zip(pools, scores_by_pool):
        by_citekey = {}
        for hit, score in zip(pool, scores):
            by_citekey.setdefault(hit["citekey"], []).append(score)
        for grouped in by_citekey.values():
            if len(grouped) < 2:
                continue
            groups += 1
            spreads.append(max(grouped) - min(grouped))
            # The pool is distance-ranked, so a group already in
            # descending-score order is one the rerank left alone.
            unchanged += all(a >= b for a, b in zip(grouped, grouped[1:]))
    return {
        "groups": groups,
        "mean_spread": round(statistics.fmean(spreads), 4) if spreads else None,
        "median_spread": round(statistics.median(spreads), 4) if spreads else None,
        "order_unchanged": unchanged,
        "order_unchanged_pct": round(100.0 * unchanged / groups, 1) if groups else None,
    }


def title_overlap(query, title):
    """Fraction of the query's terms that appear in the paper's own title,
    tokenized by `retrieval._tokenize` rather than by a second tokenizer
    invented here.

    This is the leak control. The keyword ground truth's query is the
    paper's own author-assigned keywords, and author keywords share
    vocabulary with the paper's title -- so prepending the title hands
    the model something close to a copy of the query for the correct
    document and nothing comparable for its distractors. Reporting
    B - A split at the median of this number is what tells an effect
    from an artefact of the ground truth.
    """
    terms = set(retrieval._tokenize(query))
    if not terms:
        return 0.0
    return len(terms & set(retrieval._tokenize(title or ""))) / len(terms)


def ledger_titles():
    """{citekey: title} from the ledger, for the overlap control.

    Read from the ledger rather than from the pools: a row whose correct
    paper never enters its own pool still has a title, and dropping those
    rows from the stratification would bias it toward the easy half.
    """
    return {
        row[0]: row[1] or "" for row in ledger.connect().execute("SELECT citekey, title FROM items")
    }


def budget_profile(pools, queries, tokenizer, max_length):
    """Whether a title prefix actually displaces passage text.

    The issue carries "input budget" as a risk: `snippet_chars` is the
    reranker's effective window, so a prefix spends part of it. That is
    only true if the *model's* window binds, which is a measurement, not
    an argument -- 500 characters is well inside a 512-token limit. If
    nothing is truncated under either rendering, the risk is retired with
    a number instead of carried as an open question.
    """
    lengths = {name: [] for name in RENDERS}
    for query, pool in zip(queries, pools):
        # A query whose pool came back empty is skipped rather than
        # tokenized: the batch tokenizer raises on an empty batch, and an
        # empty pool has no passage whose length could bind anyway.
        if not pool:
            continue
        for name, render in RENDERS.items():
            encoded = tokenizer([(query, render(hit)) for hit in pool])["input_ids"]
            lengths[name].extend(len(ids) for ids in encoded)
    return {
        "max_length": max_length,
        "arms": {
            name: {
                "median_tokens": round(statistics.median(values), 1),
                "max_tokens": max(values),
                "over_max_length": sum(1 for v in values if v > max_length),
            }
            for name, values in lengths.items()
        },
    }


def stratify(ground_truth, titles, by_arm, names):
    """Every arm's metrics again, over the half of the ground truth whose
    query largely appears in the correct paper's own title and over the
    half where it does not.

    This is the leak control, and it is the number that decides 786 on
    this ground truth: the keyword rows' query *is* the paper's own
    author-assigned keywords, so a title prefix hands the model something
    close to a copy of the query for the correct document and nothing
    comparable for its distractors. A gain that lives only in the
    high-overlap half is an artefact of the ground truth; one that
    survives the low-overlap half is not.

    Returns `({}, None)` for a ground truth whose rows are not
    single-citekey -- the live logs' relevant set is a whole chapter's
    kept citekeys, so "the correct paper's title" names no one title, and
    a stratification computed over an arbitrary member of the set would
    be a number with no meaning rather than a missing one.
    """
    if any("citekeys" in row for row in ground_truth):
        return {}, None
    overlaps = {
        row_key(row): title_overlap(row["query"], titles.get(row["citekey"], ""))
        for row in ground_truth
    }
    cut = statistics.median(overlaps.values())
    strata = {
        f"high overlap (>= {cut:.2f})": [r for r in ground_truth if overlaps[row_key(r)] >= cut],
        f"low overlap (< {cut:.2f})": [r for r in ground_truth if overlaps[row_key(r)] < cut],
    }
    return {
        label: [{"row": name, **score_arm(by_arm[name], rows_in)} for name in names]
        for label, rows_in in strata.items()
    }, cut


def run_input_arms(ground_truth, k, cap, rerank_model):
    """A/B/C over one set of pools, plus the leak control, the
    within-document diagnostic and the input-budget check.
    """
    from sentence_transformers import CrossEncoder

    queries = [row["query"] for row in ground_truth]
    keys = [row_key(row) for row in ground_truth]
    reranker = CrossEncoder(rerank_model)
    scorer = reranker.predict

    print(
        f"embedding {len(queries)} queries and pooling "
        f"{k * config.EMBED_OVERFETCH_MULTIPLIER} chunks each ..."
    )
    pools = dense_pools(queries, k)
    assert_replication_matches_shipped(pools, queries, cap, k)

    titles = ledger_titles()
    missing_titles = sum(
        1 for pool in pools for hit in pool if not (hit.get("title") or "").strip()
    )
    pool_hits = sum(len(pool) for pool in pools)

    arms, scores_by_arm = {}, {}
    for name, render in RENDERS.items():
        print(f"scoring {name} ...")
        # A list aligned with `pools`, not a dict keyed on the query
        # text: the live-log ground truth logs the same query in more
        # than one chapter, and a dict would silently fold those rows
        # into one.
        scored = [score_pool(pool, q, scorer, render) for q, pool in zip(queries, pools)]
        scores_by_arm[name] = scored
        arms[name] = [
            cap_and_truncate(order_by_scores(pool, scores), cap, k)
            for pool, scores in zip(pools, scored)
        ]

    # The un-reranked shipped arm, as the reference row every rendering is
    # really being asked about: `[enrich].rerank` is off by default, so
    # "does the title help arm A" is only half the question -- the other
    # half is whether either rendering beats running no reranker at all.
    arms[NO_RERANK] = [cap_and_truncate(pool, cap, k) for pool in pools]

    by_arm = {name: dict(zip(keys, hits)) for name, hits in arms.items()}
    names = [NO_RERANK] + list(RENDERS)
    rows = [{"row": name, **score_arm(by_arm[name], ground_truth)} for name in names]

    stratified, cut = stratify(ground_truth, titles, by_arm, names)

    deltas = {
        "none vs A (what reranking buys at all)": compare_arms(
            by_arm[NO_RERANK], by_arm[names[1]], ground_truth
        ),
        "none vs B (what 786 buys over no reranker)": compare_arms(
            by_arm[NO_RERANK], by_arm[names[2]], ground_truth
        ),
        "A vs B (does the title change what ships)": compare_arms(
            by_arm[names[1]], by_arm[names[2]], ground_truth
        ),
        "B vs C (has the passage stopped mattering)": compare_arms(
            by_arm[names[2]], by_arm[names[3]], ground_truth
        ),
        "A vs C (title alone against passage alone)": compare_arms(
            by_arm[names[1]], by_arm[names[3]], ground_truth
        ),
    }
    within = {name: within_doc_profile(pools, scores_by_arm[name]) for name in RENDERS}
    budget = budget_profile(pools, queries, reranker.tokenizer, reranker.max_seq_length)
    return {
        "rows": rows,
        "stratified": stratified,
        "overlap_cut": round(cut, 4) if cut is not None else None,
        "deltas": deltas,
        "within_document": within,
        "input_budget": budget,
        "pool_hits": pool_hits,
        "hits_without_title": missing_titles,
        "dense_pool_rank_profile": pool_rank_profile(pools, ground_truth),
    }


def input_arms_self_check():
    """Plant a title that must change which document survives the cap, and
    assert A and B disagree about it -- bench/'s rule that a script
    publishing a number first fabricates the difference it claims to
    detect. Also plant a rendering whose scores are flat, and assert the
    within-document diagnostic reports the collapse rather than averaging
    it away.
    """
    pool = [
        {"citekey": "A", "title": "Alpha", "snippet": "a1"},
        {"citekey": "A", "title": "Alpha", "snippet": "a2"},
        {"citekey": "A", "title": "Alpha", "snippet": "a3"},
        {"citekey": "B", "title": "Beta", "snippet": "b1"},
        {"citekey": "C", "title": "Gamma", "snippet": "c1"},
    ]
    assert titled(pool[0]) == "Alpha\n\na1", titled(pool[0])
    assert titled({"title": "  ", "snippet": "x"}) == "x"
    # Snippet-only keeps {A, A, B}; the titled rendering promotes C's one
    # chunk, so B is out and C is in -- the composition change a shared
    # prefix is supposed to be able to cause.
    planted = {"a1": 5.0, "a2": 4.0, "a3": 3.0, "b1": 2.0, "c1": 1.0, "Gamma\n\nc1": 9.0}

    def stub(pairs):
        return [planted.get(text, 0.5) for _query, text in pairs]

    kept = {}
    for name, render in RENDERS.items():
        scores = score_pool(pool, "q", stub, render)
        kept[name] = [h["citekey"] for h in cap_and_truncate(order_by_scores(pool, scores), 2, 3)]
    assert kept["A snippet only (shipped)"] == ["A", "A", "B"], kept
    assert set(kept["B title + snippet (786)"]) == {"C", "A"}, kept
    assert set(kept["A snippet only (shipped)"]) != set(kept["B title + snippet (786)"]), (
        "the planted title did not change which document survived -- this harness "
        "cannot detect the effect it exists to measure"
    )

    discriminating = within_doc_profile([pool], [[5.0, 4.0, 3.0, 2.0, 1.0]])
    assert discriminating == {
        "groups": 1,
        "mean_spread": 2.0,
        "median_spread": 2.0,
        "order_unchanged": 1,
        "order_unchanged_pct": 100.0,
    }, discriminating
    reordered = within_doc_profile([pool], [[1.0, 2.0, 3.0, 9.0, 9.0]])
    assert reordered["order_unchanged"] == 0, reordered
    flat = within_doc_profile([pool], [[1.0] * 5])
    assert flat["mean_spread"] == 0.0 and flat["order_unchanged"] == 1, flat
    assert flat["mean_spread"] < discriminating["mean_spread"], (
        "a rendering that scores every chunk of a paper alike must read as a "
        "narrower spread than one that separates them"
    )
    assert title_overlap("digital twin fidelity", "Digital twin fidelity in practice") == 1.0
    assert title_overlap("digital twin", "Unrelated survey") == 0.0
    assert title_overlap("", "anything") == 0.0


def report_input_arms(ground_truth, k, cap, args):
    """`--input-arms`'s own printing and record, kept out of `main` so the
    five-arm path it does not touch reads exactly as it did before.
    """
    result = run_input_arms(ground_truth, k, cap, args.rerank_model)
    header = f"{'row':30} {'n':>4} {'r@3':>7} {'r@5':>7} {'nDCG@5':>7} {'distinct@5':>11}"
    for label, rows in [("all queries", result["rows"])] + list(result["stratified"].items()):
        print(f"\n{label}\n{header}\n{'-' * len(header)}")
        for row in rows:
            print(
                f"{row['row']:30} {row['n_queries']:>4} "
                f"{row[f'recall@{K_SHALLOW}']:>7} {row[f'recall@{K_REPORT}']:>7} "
                f"{row[f'ndcg@{K_REPORT}']:>7} {row[f'distinct@{K_REPORT}']:>11}"
            )
    print()
    for name, delta in result["deltas"].items():
        print(
            f"{name}: {delta['set_differs']}/{delta['n']} queries "
            f"({delta['set_differs_pct']}%) return a different set of papers, "
            f"{delta['order_differs']} differ only in order; "
            f"the correct paper was lost {delta['lost']}x, gained {delta['gained']}x"
        )
    print()
    for name, within in result["within_document"].items():
        print(
            f"{name}: within-document mean spread {within['mean_spread']} "
            f"(median {within['median_spread']}), order unchanged for "
            f"{within['order_unchanged']}/{within['groups']} groups "
            f"({within['order_unchanged_pct']}%)"
        )
    budget = result["input_budget"]
    print(f"\ninput budget (model max_length {budget['max_length']}):")
    for name, tokens in budget["arms"].items():
        print(
            f"  {name}: median {tokens['median_tokens']} tokens, max "
            f"{tokens['max_tokens']}, over the limit {tokens['over_max_length']}x"
        )
    print(
        f"\n{result['hits_without_title']}/{result['pool_hits']} pooled chunks carry "
        "no usable title, and score identically under every arm"
    )
    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    out_dir.mkdir(parents=True, exist_ok=True)
    record = out_dir / "rerank_title_input.json"
    record.write_text(
        json.dumps(
            {
                "k": k,
                "cap": cap,
                "embedding_model": config.EMBEDDING_MODEL,
                "rerank_model": args.rerank_model,
                **result,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"\nRecord: {record}")
    return 0


def load_ground_truth(which):
    """`keywords` or `live`, in the one row shape this script's scorers read.

    The live-log builder is imported here rather than at module import so
    the keyword path -- which every recorded row for this script uses --
    does not start depending on a restored book being on disk. Its rows
    are keyed on `(chapter, query_index)` because the same query text was
    logged in more than one chapter, and carry a *set* of relevant
    citekeys because a chapter's kept-citekey list is the finest relevance
    those logs support.
    """
    if which == "keywords":
        return build_keyword_ground_truth()
    from bench_retrieval_live_logs import build_live_ground_truth

    return [
        {**row, "key": f"{row['chapter']}:{row['query_index']}"}
        for row in build_live_ground_truth()
    ]


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
    ap.add_argument(
        "--ground-truth",
        choices=("keywords", "live"),
        default="keywords",
        help="`keywords` (the default) is bench_retrieval_keyword_selfretrieval.py's "
        "256 self-retrieval pairs, which every row recorded for this script so far "
        "uses; `live` is bench_retrieval_live_logs.py's real logged drafting queries, "
        "whose queries no paper's own metadata wrote -- the confirmation ground truth "
        "for a title-augmentation result (see --input-arms)",
    )
    ap.add_argument(
        "--input-arms",
        action="store_true",
        help="instead of the five cap-position arms, run issue 786's three "
        "passage-rendering arms (snippet, title+snippet, title alone) over one "
        "set of pools, with the ground-truth-leak control and the "
        "within-document diagnostic -- see plans/786-title-augmented-rerank-input.md",
    )
    args = ap.parse_args(argv)

    self_check()
    input_arms_self_check()

    ground_truth = load_ground_truth(args.ground_truth)
    if args.limit:
        ground_truth = ground_truth[: args.limit]
    k, cap = K_REPORT, config.EMBED_MAX_PASSAGES_PER_SOURCE
    print(
        f"{len(ground_truth)} {args.ground_truth} queries; "
        f"k={k}, cap={cap}, model={config.EMBEDDING_MODEL}, reranker={args.rerank_model}"
    )
    if args.input_arms:
        return report_input_arms(ground_truth, k, cap, args)
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

"""What cross-encoding the over-fetched passages actually costs (#380).

bench_rerank_position.py measures whether reranking helps. It does not
time anything, and the plan in plans/b4-cross-encoder-rerank.md is
blocked on cost: a reranker runs inside a drafting loop, once per
`search()` call, so "is it affordable" is decided by the *added* latency
per call and not by the model's size on disk.

The number that matters is therefore a **ratio, not a duration**. A
reranker that adds 40ms is cheap beside a 200ms search and ruinous
beside a 5ms one, so this script times the shipped
`embed_index.search()` path -- query encode plus Chroma query -- in the
same process, on the same device, and reports the rerank stage against
it.

Three axes, because the answer differs by an order of magnitude across
each: model (the three candidates
bench_rerank_position.py scored), device (`cuda` vs `cpu` -- the enrich
extra installs torch either way, and a laptop drafting session has no
GPU), and pool depth (`k * embed_overfetch_multiplier` is 20 today, but the
pool depth is the knob someone will reach for first if reranking is
turned on).

Real queries and real passages, drawn from the corpus, because a
cross-encoder's cost is driven by token count and synthetic filler of
the same character length does not tokenize alike.

    CHITRAGUPTA_PROJECT=/workspace .venv-full/bin/python \\
        bench/bench_rerank_cost.py --tag 2026-08-26-rerank-cost
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(BENCH_DIR))

from chitragupta import config  # noqa: E402
from bench_retrieval_keyword_selfretrieval import build_keyword_ground_truth  # noqa: E402

MODELS = (
    "cross-encoder/ms-marco-MiniLM-L6-v2",
    "cross-encoder/ms-marco-MiniLM-L12-v2",
    "BAAI/bge-reranker-base",
)
POOL_DEPTHS = (5, 20, 50)
N_QUERIES = 20
REPEATS = 3
SNIPPET_CHARS = 500  # embed_index.search()'s own default


def time_it(fn, repeats=REPEATS):
    """Median wall clock of `repeats` calls **in seconds**, after one
    untimed warm-up.

    Seconds, not milliseconds, and every caller converts where it prints.
    The first draft returned milliseconds while its callers still
    multiplied by 1000 to "convert", reporting a 13ms search as 13
    seconds. Nothing looked wrong except the absolute figures -- the
    slowdown ratios carried the same error on both sides and stayed
    correct -- which is why `self_check` now pins the unit rather than
    only the timer's sensitivity.

    The warm-up is not politeness: the first CrossEncoder call pays CUDA
    context creation and lazy kernel compilation, which on this host is
    larger than every steady-state number below and would be reported as
    the cost of reranking if it were left in.
    """
    fn()
    return statistics.median([_timed(fn) for _ in range(repeats)])


def _timed(fn):
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


def self_check():
    """`time_it` must actually see a difference it is asked to measure.

    Fabricate one: a sleep of 20ms against a sleep of 5ms. If the timer
    were measuring nothing -- a warm-up that swallowed the call, a median
    over an empty list -- both would come back equal or zero, which is
    exactly the "zero that reads like a result" this convention exists
    to catch. The bar is deliberately loose (>10ms apart) so a loaded
    machine does not fail the check for the wrong reason.
    """
    slow = time_it(lambda: time.sleep(0.020), repeats=1)
    fast = time_it(lambda: time.sleep(0.005), repeats=1)
    assert slow > fast + 0.010, f"timer cannot separate 20ms from 5ms: {slow} vs {fast}"
    assert 0.015 < slow < 0.100, (
        f"time_it must return SECONDS -- a 20ms sleep came back as {slow}. "
        "Every caller multiplies by 1000 to print milliseconds, so a unit "
        "change here silently scales every published figure by 1000."
    )


def sample_workload(n_queries, max_pool):
    """`n_queries` real queries, each with `max_pool` real passages drawn
    from the corpus by the shipped dense path -- so the pairs handed to
    the cross-encoder below are the pairs it would really score."""
    from chitragupta.enrich import embed_index

    ground_truth = build_keyword_ground_truth()[:n_queries]
    queries = [row["query"] for row in ground_truth]
    client, model = embed_index.get_client_and_model()
    collection = client.get_or_create_collection(embed_index.collection_name())
    embeddings = model.encode(queries, show_progress_bar=False).tolist()
    raw = collection.query(query_embeddings=embeddings, n_results=max_pool)
    return [
        (query, [doc[:SNIPPET_CHARS] for doc in docs])
        for query, docs in zip(queries, raw["documents"])
    ]


def time_search_baseline(queries, k, device):
    """The shipped `embed_index.search()` cost per call -- query encode
    plus Chroma query -- which is what any rerank latency has to be read
    against. Timed here rather than quoted from elsewhere so both halves
    of the ratio come from the same process and the same device."""
    from chitragupta.enrich import embed_index

    client, model = embed_index.get_client_and_model()
    model.to(device)
    collection = client.get_or_create_collection(embed_index.collection_name())

    def one_pass():
        for query in queries:
            embedding = model.encode([query], show_progress_bar=False).tolist()
            collection.query(query_embeddings=embedding, n_results=k * 4)

    return time_it(one_pass) / len(queries)


def time_rerank(model_id, workload, pool, device):
    """Per-query cost of scoring `pool` (query, passage) pairs, plus the
    one-off model construction cost, which a lazy loader pays on the
    first reranked call of a session and never again."""
    from sentence_transformers import CrossEncoder

    load_start = time.perf_counter()
    reranker = CrossEncoder(model_id, device=device)
    load_ms = round(1000 * (time.perf_counter() - load_start), 1)

    batches = [[(query, passage) for passage in passages[:pool]] for query, passages in workload]

    def one_pass():
        for pairs in batches:
            reranker.predict(pairs, show_progress_bar=False)

    per_query = time_it(one_pass) / len(batches)
    return per_query, load_ms


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tag", required=True, help="names bench/results/<tag>/")
    ap.add_argument("--devices", default="cuda,cpu", help="comma-separated torch devices")
    args = ap.parse_args(argv)

    self_check()

    import torch

    devices = [d for d in args.devices.split(",") if d != "cuda" or torch.cuda.is_available()]
    workload = sample_workload(N_QUERIES, max(POOL_DEPTHS))
    queries = [query for query, _passages in workload]
    print(
        f"{len(workload)} real queries x up to {max(POOL_DEPTHS)} real passages "
        f"({SNIPPET_CHARS} chars each); median of {REPEATS} passes after a warm-up\n"
    )

    rows, baselines = [], {}
    for device in devices:
        baselines[device] = time_search_baseline(queries, k=5, device=device)
        print(f"[{device}] embed_index.search() baseline: {baselines[device] * 1000:.1f} ms/query")
    print()

    for device in devices:
        for model_id in MODELS:
            for pool in POOL_DEPTHS:
                per_query, load_ms = time_rerank(model_id, workload, pool, device)
                # Six models across two devices otherwise accumulate on the
                # card: `time_rerank`'s local goes out of scope on return,
                # but torch keeps the freed blocks in its caching allocator
                # until asked, and the later, larger models are the ones
                # that would OOM.
                if device == "cuda":
                    torch.cuda.empty_cache()
                rows.append(
                    {
                        "device": device,
                        "model": model_id,
                        "pool": pool,
                        "rerank_ms_per_query": round(per_query * 1000, 2),
                        "search_baseline_ms_per_query": round(baselines[device] * 1000, 2),
                        "slowdown_x": round((per_query + baselines[device]) / baselines[device], 2),
                        "model_load_ms": load_ms,
                    }
                )
                print(
                    f"[{device}] {model_id.rsplit('/', 1)[-1]:28} pool={pool:>2}  "
                    f"rerank {per_query * 1000:>8.1f} ms/query  "
                    f"-> {rows[-1]['slowdown_x']:>6.2f}x a search call  "
                    f"(load {load_ms:.0f} ms)"
                )

    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    out_dir.mkdir(parents=True, exist_ok=True)
    record = out_dir / "rerank_cost.json"
    record.write_text(
        json.dumps(
            {
                "n_queries": N_QUERIES,
                "repeats": REPEATS,
                "snippet_chars": SNIPPET_CHARS,
                "embedding_model": config.EMBEDDING_MODEL,
                "rows": rows,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"\nRecord: {record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

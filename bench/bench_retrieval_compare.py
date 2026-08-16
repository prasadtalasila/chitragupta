"""Retrieval quality across BM25, three drop-in dense models (each
alone and reranked), and SPECTER2 -- scored against the 48-pair ground
truth bench_retrieval_ground_truth.py recovers. Directly answers "compare
against retrieval and reranking, not bare BM25": BM25 is one row for
context, not the target every other row is measured against.

Each dense model's row runs in its own subprocess
(--dense-worker <model>), because config.EMBEDDING_MODEL is fixed at
src/config.py's import time -- three models cannot be swept by mutating
os.environ mid-process.

    .venv-full/bin/python bench/bench_retrieval_compare.py \\
        --ground-truth bench/results/2026-08-16-retrieval-ground-truth/ground_truth.json \\
        --tag 2026-08-16-retrieval-compare
"""

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from src import config, retrieval  # noqa: E402

K_REPORT = 5
K_POOL = 50  # first-pass depth offered to the reranker, per discussion #43 Sec.3
DENSE_MODELS = (
    "sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers/all-mpnet-base-v2",
    "sentence-transformers/multi-qa-mpnet-base-dot-v1",
)
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"


def recall_at_k(ranked_citekeys, relevant, k):
    return 1.0 if any(c in relevant for c in ranked_citekeys[:k]) else 0.0


def ndcg_at_k(ranked_citekeys, relevant, k):
    dcg = sum(1.0 / math.log2(i + 1) for i, c in enumerate(ranked_citekeys[:k], start=1)
              if c in relevant)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def collapse_to_citekeys(hits, key="citekey"):
    """Best-first list of hits (already ranked) to a ranked, de-duplicated
    citekey list -- a caller retrieving chunks has to collapse to
    documents before recall@k over citekeys means anything (discussion
    #43 Sec.4, "aggregate to the caller's unit")."""
    seen, out = set(), []
    for hit in hits:
        citekey = hit[key] if isinstance(hit, dict) else getattr(hit, key)
        if citekey not in seen:
            seen.add(citekey)
            out.append(citekey)
    return out


def score_rows(ranked_by_query, ground_truth):
    """{query_key: ranked_citekeys} to mean recall@K_REPORT / nDCG@K_REPORT
    over every ground-truth row that has a ranking."""
    recalls, ndcgs, missing = [], [], 0
    for row in ground_truth:
        key = (row["chapter"], row["line"], row["citekey"])
        ranked = ranked_by_query.get(key)
        if ranked is None:
            missing += 1
            continue
        relevant = {row["citekey"]}
        recalls.append(recall_at_k(ranked, relevant, K_REPORT))
        ndcgs.append(ndcg_at_k(ranked, relevant, K_REPORT))
    return {
        "n_queries": len(ground_truth) - missing,
        "n_missing": missing,
        f"recall@{K_REPORT}": round(sum(recalls) / len(recalls), 4) if recalls else None,
        f"ndcg@{K_REPORT}": round(sum(ndcgs) / len(ndcgs), 4) if ndcgs else None,
    }


def self_check():
    """ndcg_at_k against a ranking worked out by hand: relevant item at
    rank 2 of 3, one relevant item total. DCG = 1/log2(3) = 0.6309...,
    IDCG = 1/log2(2) = 1.0 (the ideal case is the same item at rank 1),
    so nDCG = 0.6309. recall@3 is 1.0 (found somewhere in top 3);
    recall@1 is 0.0 (not found in top 1)."""
    ranked, relevant = ["a", "b", "c"], {"b"}
    assert round(ndcg_at_k(ranked, relevant, 3), 4) == 0.6309, ndcg_at_k(ranked, relevant, 3)
    assert recall_at_k(ranked, relevant, 3) == 1.0
    assert recall_at_k(ranked, relevant, 1) == 0.0
    assert ndcg_at_k(ranked, {"z"}, 3) == 0.0, "no relevant item anywhere: nDCG must be 0"
    assert collapse_to_citekeys([{"citekey": "x"}, {"citekey": "x"}, {"citekey": "y"}]) == \
        ["x", "y"], "collapse_to_citekeys should de-duplicate, keeping first-seen order"


def bm25_row(ground_truth):
    ranked_by_query = {}
    for row in ground_truth:
        key = (row["chapter"], row["line"], row["citekey"])
        results = retrieval.search(row["query"], k=K_REPORT)
        ranked_by_query[key] = [r.citekey for r in results]
    return {"row": "BM25 (src/retrieval.py)", **score_rows(ranked_by_query, ground_truth)}


def _venv_python():
    """Path to the `enrich` Poetry group interpreter (chromadb,
    sentence-transformers, torch).

    Prefers this checkout's own `.venv-full`, matching every other bench
    script's documented `.venv-full/bin/python bench/...` invocation. On
    this host, though, a freshly created worktree does not carry its own
    multi-GB venv -- `.venv-full` lives once, in the checkout the
    worktree branched from -- so this falls back to that checkout,
    located the same way git itself finds it (`--git-common-dir`), rather
    than a hardcoded sibling path that would break on a different host
    layout."""
    local = REPO / ".venv-full" / "bin" / "python"
    if local.exists():
        return str(local)
    common_dir = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.strip()
    shared = (REPO / common_dir).resolve().parent / ".venv-full" / "bin" / "python"
    if shared.exists():
        return str(shared)
    raise RuntimeError(
        f"no .venv-full/bin/python at {local} or {shared} -- "
        "run `poetry install --with enrich` in one of those checkouts"
    )


def _dense_worker(ground_truth):
    """Runs inside a fresh subprocess with EMBEDDING_MODEL already set in
    its environment -- config.EMBEDDING_MODEL is read at import, so this
    function must not be called from the orchestrating process."""
    from sentence_transformers import CrossEncoder
    from src.enrich import embed_index

    reranker = CrossEncoder(RERANK_MODEL)
    dense_ranked, reranked = {}, {}
    for row in ground_truth:
        key = (row["chapter"], row["line"], row["citekey"])
        hits = embed_index.search(row["query"], k=K_POOL)
        dense_ranked[key] = collapse_to_citekeys(hits)[:K_REPORT]

        scores = reranker.predict([(row["query"], hit["snippet"]) for hit in hits])
        reranked_hits = [hit for _score, hit in
                         sorted(zip(scores, hits), key=lambda pair: -pair[0])]
        reranked[key] = collapse_to_citekeys(reranked_hits)[:K_REPORT]
    return dense_ranked, reranked


def dense_and_rerank_rows(model, ground_truth, tag):
    """Shells out to this same script in worker mode, with EMBEDDING_MODEL
    set for the subprocess -- the only way to run three different dense
    models without three different interpreter processes."""
    env = dict(os.environ, EMBEDDING_MODEL=model)
    payload_path = BENCH_DIR / "results" / tag / f"_dense_worker_{model.rsplit('/', 1)[-1]}.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [_venv_python(), str(Path(__file__)), "--dense-worker", model,
         "--ground-truth-inline", "-", "--out", str(payload_path)],
        input=json.dumps(ground_truth), env=env, cwd=str(REPO),
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"dense worker for {model} exited {result.returncode}")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    dense_ranked = {tuple(k): v for k, v in payload["dense"]}
    reranked = {tuple(k): v for k, v in payload["reranked"]}
    return (
        {"row": f"dense-only: {model}", **score_rows(dense_ranked, ground_truth)},
        {"row": f"dense+rerank: {model}", **score_rows(reranked, ground_truth)},
    )


def specter2_row(ground_truth):
    """SPECTER2 standalone: adhoc_query on the query side, proximity on
    the document side, ranked over every citekey either arm needs --
    the ground truth's own citekeys plus, if available, the wider
    corpus. Restricted to the ground truth's own citekey set here: a
    full corpus-wide SPECTER2 index is Task 5's cascade shortlist, not
    this row's job."""
    import embed_models as em

    citekeys = sorted({row["citekey"] for row in ground_truth})
    paper_vectors = em.embed_paper(citekeys)

    def cosine(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    ranked_by_query = {}
    for row in ground_truth:
        key = (row["chapter"], row["line"], row["citekey"])
        query_vector = em.embed_query(row["query"])
        ranked = sorted(citekeys, key=lambda c: -cosine(query_vector, paper_vectors[c]))
        ranked_by_query[key] = ranked[:K_REPORT]
    return {"row": "SPECTER2 (adhoc_query + proximity)", **score_rows(ranked_by_query, ground_truth)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ground-truth", help="path to a ground_truth.json from Task 1")
    ap.add_argument("--tag", help="names bench/results/<tag>/")
    ap.add_argument("--dense-worker", default=None, metavar="MODEL",
                    help=argparse.SUPPRESS)  # internal: subprocess-only
    ap.add_argument("--ground-truth-inline", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--out", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    self_check()

    if args.dense_worker:
        ground_truth = json.loads(sys.stdin.read() if args.ground_truth_inline == "-"
                                  else Path(args.ground_truth_inline).read_text(encoding="utf-8"))
        dense_ranked, reranked = _dense_worker(ground_truth)
        Path(args.out).write_text(json.dumps({
            "dense": list(dense_ranked.items()), "reranked": list(reranked.items()),
        }), encoding="utf-8")
        return 0

    if not args.ground_truth or not args.tag:
        print("--ground-truth and --tag are required outside --dense-worker mode",
              file=sys.stderr)
        return 2

    ground_truth = json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))
    rows = [bm25_row(ground_truth)]
    for model in DENSE_MODELS:
        dense, rerank = dense_and_rerank_rows(model, ground_truth, args.tag)
        rows += [dense, rerank]
    rows.append(specter2_row(ground_truth))

    print(f"\n{'row':45}  {'n':>3}  recall@{K_REPORT}  ndcg@{K_REPORT}")
    for row in rows:
        print(f"{row['row']:45}  {row['n_queries']:>3}  "
              f"{row[f'recall@{K_REPORT}']:>9}  {row[f'ndcg@{K_REPORT}']:>8}")

    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    out_dir.mkdir(parents=True, exist_ok=True)
    record = out_dir / "comparison.json"
    record.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"\nRecord: {record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Retrieval quality against ground truth from real drafting sessions,
not reconstructed after the fact.

bench_retrieval_ground_truth.py/bench_retrieval_compare.py score against
48 (query, citekey) pairs rebuilt by re-extracting claim text from a
restored book and joining it back onto committed judgments -- a real but
indirect proxy. This script uses what a drafting session actually
*logged* while it ran: every real `search`-mode query in each restored
chapter's `retrieval.md` (`chitragupta.retrieval`/`embed_index`'s own append-only
call log), scored against that chapter's real kept-citekey set
(`evidence.md`). No claim-text re-extraction, no book-restore-and-rejoin
risk -- the queries and the outcomes were both written by the real run.

Reuses the same scoring primitives and the same row set as
bench_retrieval_compare.py (recall@5/nDCG@5; BM25, three drop-in dense
models alone and reranked, SPECTER2, the SPECTER2-shortlist cascade) --
imported, not reimplemented. What's new here is only the ground truth's
shape: a chapter-level query paired with a *set* of relevant citekeys
(every citekey the chapter kept), not a single citekey a specific line
cites -- retrieval.md logs a query's text and result *count*, never
which citekeys a call returned, so per-query relevance finer than
"the whole chapter" isn't available from these logs. `recall_at_k`/
`ndcg_at_k` already score against an arbitrary-size relevant set; only
the orchestration around them (the query/relevant-set key, not
`(chapter, line, citekey)`) needed rewriting for that shape.

    .venv-full/bin/python bench/bench_retrieval_live_logs.py \\
        --tag 2026-08-16-retrieval-live-logs
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from chitragupta import config, ledger, retrieval  # noqa: E402
from bench_retrieval_compare import (  # noqa: E402
    K_REPORT, K_POOL, DENSE_MODELS, RERANK_MODEL,
    recall_at_k, ndcg_at_k, collapse_to_citekeys, _venv_python,
)

BOOK_DOSSIERS = config.CONTENT_DIR / "dossiers" / "books" / "digital-twins-for-software-engineers"

_TICK = re.compile(r"`([^`]+)`")
_SEARCH_ROW = re.compile(r"^\|\s*[\d-]+\s*\|\s*search\s*\|\s*(.+?)\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*$",
                        re.MULTILINE)


def _kept_citekeys(evidence_md_text, real_citekeys):
    """Every backtick-quoted token in evidence.md that is a real ledger
    citekey. Format-agnostic on purpose: this book's 15 chapters use two
    different evidence.md prose shapes (a `| Citekey | ... |` table in
    some, `## `citekey`` headings in others), so matching structure is
    fragile where matching "a real citekey inside backticks" is not."""
    return {tok for tok in _TICK.findall(evidence_md_text) if tok in real_citekeys}


def build_live_ground_truth():
    """One row per real `search`-mode retrieval.md query, paired with its
    chapter's real kept-citekey set. `evidence`-mode calls are excluded --
    those fetch supporting text for a citekey the session already chose,
    a different intent than "find the right paper"."""
    real_citekeys = {r[0] for r in ledger.connect().execute("SELECT citekey FROM items")}
    rows = []
    for chapter_dir in sorted(BOOK_DOSSIERS.iterdir()):
        retrieval_md = chapter_dir / "retrieval.md"
        evidence_md = chapter_dir / "evidence.md"
        if not retrieval_md.exists() or not evidence_md.exists():
            continue
        kept = _kept_citekeys(evidence_md.read_text(encoding="utf-8"), real_citekeys)
        if not kept:
            continue
        queries = _SEARCH_ROW.findall(retrieval_md.read_text(encoding="utf-8"))
        for i, query in enumerate(queries):
            rows.append({"chapter": chapter_dir.name, "query_index": i,
                        "query": query, "citekeys": sorted(kept)})
    return rows


def self_check():
    """The parser recovers exactly what a direct read of one real,
    already-inspected chapter shows: 4 search-mode queries and 17 kept
    citekeys for `09-connecting-the-physical`. Stdlib-only -- no model
    download, cheap to run before anything expensive starts."""
    rows = [r for r in build_live_ground_truth() if r["chapter"] == "09-connecting-the-physical"]
    assert len(rows) == 4, f"expected 4 search-mode queries for ch.09, got {len(rows)}"
    assert len(rows[0]["citekeys"]) == 17, (
        f"expected 17 kept citekeys for ch.09, got {len(rows[0]['citekeys'])}"
    )
    assert all(r["citekeys"] == rows[0]["citekeys"] for r in rows), (
        "every query in a chapter should share that chapter's kept-citekey set"
    )


def score_live_rows(ranked_by_query, ground_truth):
    recalls, ndcgs, missing = [], [], 0
    for row in ground_truth:
        key = (row["chapter"], row["query_index"])
        ranked = ranked_by_query.get(key)
        if ranked is None:
            missing += 1
            continue
        relevant = set(row["citekeys"])
        recalls.append(recall_at_k(ranked, relevant, K_REPORT))
        ndcgs.append(ndcg_at_k(ranked, relevant, K_REPORT))
    return {
        "n_queries": len(ground_truth) - missing,
        "n_missing": missing,
        f"recall@{K_REPORT}": round(sum(recalls) / len(recalls), 4) if recalls else None,
        f"ndcg@{K_REPORT}": round(sum(ndcgs) / len(ndcgs), 4) if ndcgs else None,
    }


def bm25_row(ground_truth):
    ranked_by_query = {}
    for row in ground_truth:
        key = (row["chapter"], row["query_index"])
        results = retrieval.search(row["query"], k=K_REPORT)
        ranked_by_query[key] = [r.citekey for r in results]
    return {"row": "BM25 (chitragupta/retrieval.py)", **score_live_rows(ranked_by_query, ground_truth)}


def _dense_worker(ground_truth):
    from sentence_transformers import CrossEncoder
    from chitragupta.enrich import embed_index

    reranker = CrossEncoder(RERANK_MODEL)
    dense_ranked, reranked = {}, {}
    for row in ground_truth:
        key = (row["chapter"], row["query_index"])
        hits = embed_index.search(row["query"], k=K_POOL)
        dense_ranked[key] = collapse_to_citekeys(hits)[:K_REPORT]

        scores = reranker.predict([(row["query"], hit["snippet"]) for hit in hits])
        reranked_hits = [hit for _score, hit in
                         sorted(zip(scores, hits), key=lambda pair: -pair[0])]
        reranked[key] = collapse_to_citekeys(reranked_hits)[:K_REPORT]
    return dense_ranked, reranked


def dense_and_rerank_rows(model, ground_truth, tag):
    env = dict(os.environ, EMBEDDING_MODEL=model)
    payload_path = BENCH_DIR / "results" / tag / f"_dense_worker_{model.rsplit('/', 1)[-1]}.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [_venv_python(), str(Path(__file__)), "--dense-worker", model,
         "--out", str(payload_path)],
        env=env, cwd=str(REPO), capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"dense worker for {model} exited {result.returncode}")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    dense_ranked = {tuple(k): v for k, v in payload["dense"]}
    reranked = {tuple(k): v for k, v in payload["reranked"]}
    return (
        {"row": f"dense-only: {model}", **score_live_rows(dense_ranked, ground_truth)},
        {"row": f"dense+rerank: {model}", **score_live_rows(reranked, ground_truth)},
    )


def specter2_row(ground_truth):
    import embed_models as em

    citekeys = sorted({c for row in ground_truth for c in row["citekeys"]})
    paper_vectors = em.embed_paper(citekeys)

    def cosine(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    ranked_by_query = {}
    for row in ground_truth:
        key = (row["chapter"], row["query_index"])
        query_vector = em.embed_query(row["query"])
        ranked = sorted(citekeys, key=lambda c: -cosine(query_vector, paper_vectors[c]))
        ranked_by_query[key] = ranked[:K_REPORT]
    return {"row": "SPECTER2 (adhoc_query + proximity)",
           **score_live_rows(ranked_by_query, ground_truth)}


def _cascade_worker(ground_truth, shortlist_size):
    import embed_models as em
    from sentence_transformers import CrossEncoder, SentenceTransformer
    from chitragupta.enrich import embed_index

    all_citekeys = [r[0] for r in ledger.connect().execute("SELECT citekey FROM items")]
    paper_vectors = em.embed_paper(all_citekeys)

    def cosine(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    client, _model = embed_index.get_client_and_model()
    collection = client.get_or_create_collection(embed_index.collection_name())
    reranker = CrossEncoder(RERANK_MODEL)
    dense_model = SentenceTransformer(embed_index.config.EMBEDDING_MODEL)

    ranked_by_query = {}
    for row in ground_truth:
        key = (row["chapter"], row["query_index"])
        query_vector = em.embed_query(row["query"])
        shortlist = sorted(all_citekeys,
                           key=lambda c: -cosine(query_vector, paper_vectors[c]))[:shortlist_size]

        query_embedding = dense_model.encode([row["query"]], show_progress_bar=False).tolist()
        raw = collection.query(query_embeddings=query_embedding, n_results=K_POOL,
                               where={"citekey": {"$in": shortlist}})
        hits = [{**meta, "snippet": doc[:500]}
               for doc, meta in zip(raw["documents"][0], raw["metadatas"][0])]
        if not hits:
            ranked_by_query[key] = []
            continue
        scores = reranker.predict([(row["query"], hit["snippet"]) for hit in hits])
        reranked_hits = [hit for _score, hit in
                         sorted(zip(scores, hits), key=lambda pair: -pair[0])]
        ranked_by_query[key] = collapse_to_citekeys(reranked_hits)[:K_REPORT]
    return ranked_by_query


def cascade_row(winning_model, ground_truth, tag, shortlist_size=50):
    env = dict(os.environ, EMBEDDING_MODEL=winning_model)
    payload_path = BENCH_DIR / "results" / tag / "_cascade_worker.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [_venv_python(), str(Path(__file__)), "--cascade-worker", winning_model,
         "--out", str(payload_path), "--shortlist-size", str(shortlist_size)],
        env=env, cwd=str(REPO), capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"cascade worker exited {result.returncode}")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    ranked_by_query = {tuple(k): v for k, v in payload["ranked"]}
    return {"row": f"cascade: SPECTER2 shortlist({shortlist_size}) -> {winning_model} +rerank",
           **score_live_rows(ranked_by_query, ground_truth)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tag", help="names bench/results/<tag>/")
    ap.add_argument("--dense-worker", default=None, metavar="MODEL", help=argparse.SUPPRESS)
    ap.add_argument("--cascade-worker", default=None, metavar="MODEL", help=argparse.SUPPRESS)
    ap.add_argument("--out", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--shortlist-size", type=int, default=50, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    self_check()
    ground_truth = build_live_ground_truth()

    if args.dense_worker:
        dense_ranked, reranked = _dense_worker(ground_truth)
        Path(args.out).write_text(json.dumps({
            "dense": [[list(k), v] for k, v in dense_ranked.items()],
            "reranked": [[list(k), v] for k, v in reranked.items()],
        }), encoding="utf-8")
        return 0

    if args.cascade_worker:
        ranked_by_query = _cascade_worker(ground_truth, args.shortlist_size)
        Path(args.out).write_text(json.dumps({
            "ranked": [[list(k), v] for k, v in ranked_by_query.items()],
        }), encoding="utf-8")
        return 0

    if not args.tag:
        print("--tag is required", file=sys.stderr)
        return 2

    print(f"{len(ground_truth)} real search-mode queries across "
          f"{len({r['chapter'] for r in ground_truth})} chapters", flush=True)

    rows = [bm25_row(ground_truth)]
    for model in DENSE_MODELS:
        dense, rerank = dense_and_rerank_rows(model, ground_truth, args.tag)
        rows += [dense, rerank]
    rows.append(specter2_row(ground_truth))

    dense_rerank_rows = [r for r in rows if r["row"].startswith("dense+rerank: ")]
    winner = max(dense_rerank_rows, key=lambda r: r[f"ndcg@{K_REPORT}"] or 0.0)
    winning_model = winner["row"].removeprefix("dense+rerank: ")
    rows.append(cascade_row(winning_model, ground_truth, args.tag))

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

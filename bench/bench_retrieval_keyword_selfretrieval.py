"""Retrieval quality against ground truth that no retrieval method built --
a fairness correction to bench_retrieval_compare.py and
bench_retrieval_live_logs.py, not a third opinion alongside them.

Both of those score against citekeys that were *kept during a real
drafting session that only ever ran BM25* (`chitragupta.retrieval.search()` is
the only retrieval tool either session's `retrieval.md` log shows in
use). A paper dense retrieval or SPECTER2 would have surfaced but BM25
never did was never shown to a human to judge -- so it can never be
scored as a hit, regardless of how good a citation it would have been.
Discussion #43's own follow-up comment names this: "a retriever that
finds what BM25 missed scores no better without new judgements."

This script sidesteps the problem instead of correcting for it: the
query for each paper is *that paper's own author-assigned keywords*
(`bibliography.bib`'s `keywords` field, present on 285 of 646 entries,
absent from `content/ledger.sqlite` by the same
"per-host noise" exclusion `chitragupta/ledger.py` applies to `abstract` -- read
via `chitragupta.bib_reader.read_library()`, the project's one sanctioned bib
parser, not a second one). The correct answer is the paper itself. No
method's search history decided that -- the paper's own author did, once,
independent of every retrieval method compared here.

Same scoring primitives as bench_retrieval_compare.py (imported, not
reimplemented). Two real differences from it, both because this
benchmark's whole point is a level pool: ground truth is restricted to
entries with parsed text (dense retrieval structurally cannot find an
unparsed entry, so including one would only ever penalize dense/SPECTER2
rows for a reason unrelated to their quality), and SPECTER2 ranks over
the *whole* 642-entry ledger here, not just the ground truth's own
citekeys -- matching what BM25 and the cascade's shortlist stage already
search, so every row answers "did you find it among everything", not a
mix of pool sizes.

    .venv-full/bin/python bench/bench_retrieval_keyword_selfretrieval.py \\
        --tag 2026-08-16-retrieval-keyword-selfretrieval
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from chitragupta import bib_reader, ledger, retrieval, retrieval_cache  # noqa: E402
from bench_retrieval_compare import (  # noqa: E402
    K_REPORT,
    K_POOL,
    DENSE_MODELS,
    RERANK_MODEL,
    recall_at_k,
    ndcg_at_k,
    collapse_to_citekeys,
    _venv_python,
)


def build_keyword_ground_truth():
    """One row per bib entry with a real `keywords` field and parsed
    text -- query is that entry's own keywords, joined; the correct
    answer is that entry's own citekey."""
    parsed_citekeys = {
        r[0]
        for r in ledger.connect().execute("SELECT citekey FROM items WHERE parsed_path IS NOT NULL")
    }
    rows = []
    for ref in bib_reader.read_library():
        keywords = ref.fields.get("keywords", "").strip()
        if not keywords or ref.citekey not in parsed_citekeys:
            continue
        rows.append({"citekey": ref.citekey, "query": keywords})
    return rows


def self_check():
    """The known sample entry (`richstein_characterizing_2024`) is
    really in the ground truth this parser builds, with its keywords
    intact -- checked against real data, not a fixture, since
    bib_reader.read_library() needs no model download and is cheap to
    run before anything expensive starts. `kapteyn_toward_nodate-1` has
    keywords but no parsed text and must NOT appear -- the one filter
    this self_check exists to prove is actually applied."""
    rows = {r["citekey"]: r for r in build_keyword_ground_truth()}
    assert "richstein_characterizing_2024" in rows, (
        "known keyword-bearing, parsed entry missing from the ground truth"
    )
    assert rows["richstein_characterizing_2024"]["query"] == (
        "archetypes, design, digital twin, structural health monitoring, "
        "structural mechanics, taxonomy, lifecycle"
    )
    assert "kapteyn_toward_nodate-1" not in rows, (
        "an entry with no parsed text made it into the ground truth -- "
        "the parsed-text filter is not being applied"
    )
    assert len(rows) == 256, f"expected 256 rows, got {len(rows)}"

    # E1's own before/after, against a fabricated 2-item index -- no
    # disk cache touched, just _tokenize_item's pure per-document stats
    # -- where "what" is the only thing that matches the decoy, so
    # stripping it must change the outcome: proof the rows below see the
    # fix, not just that they run.
    fake_items = [
        {"citekey": "real_2024", "title": "digital twin architecture", "parsed_path": None},
        {"citekey": "decoy_2024", "title": "what what what happened next", "parsed_path": None},
    ]
    index = {item["citekey"]: retrieval._tokenize_item(item) for item in fake_items}
    wrapped_hits = retrieval._bm25_scores(index, retrieval._tokenize("what is digital twin"))
    stripped_hits = retrieval._bm25_scores(index, retrieval._query_terms("what is digital twin"))
    assert "decoy_2024" in wrapped_hits, "fixture's decoy must match the unstripped query"
    assert "decoy_2024" not in stripped_hits, (
        "stripping interrogatives must drop the decoy that only matched on 'what'"
    )


def score_keyword_rows(ranked_by_query, ground_truth):
    recalls, ndcgs, missing = [], [], 0
    for row in ground_truth:
        key = row["citekey"]
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


def bm25_row(ground_truth):
    ranked_by_query = {}
    for row in ground_truth:
        results = retrieval.search(row["query"], k=K_REPORT)
        ranked_by_query[row["citekey"]] = [r.citekey for r in results]
    return {
        "row": "BM25 (chitragupta/retrieval.py)",
        **score_keyword_rows(ranked_by_query, ground_truth),
    }


def wrapped_and_stripped_rows(ground_truth):
    """E1's own recall table (docs/CORPUS-SEARCH.md), re-measured against
    whatever the corpus holds today. Goes around `search()` for the
    first two rows on purpose: `search()` now always strips
    interrogatives, so there is no longer a way to reproduce the
    pre-fix, unstripped path through the public API -- these call
    `_tokenize` directly to simulate it, exactly as `search()` itself
    did before E1.
    """
    with ledger.connection() as con:
        items = ledger.all_items(con)
    index = retrieval_cache._load_index(items, retrieval._tokenize_item)

    forms = {
        "keywords (baseline)": lambda q: retrieval._tokenize(q),
        "wrapped as a question": lambda q: retrieval._tokenize(f"what is {q}"),
        "question, interrogatives stripped": lambda q: retrieval._query_terms(f"what is {q}"),
        "keywords, interrogatives stripped": lambda q: retrieval._query_terms(q),
    }
    rows = []
    for label, terms_for in forms.items():
        ranked_by_query = {}
        for row in ground_truth:
            scores = retrieval._bm25_scores(index, terms_for(row["query"]))
            ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:K_REPORT]
            ranked_by_query[row["citekey"]] = [citekey for citekey, _ in ranked]
        rows.append(
            {
                "row": f"E1 interrogative-strip: {label}",
                **score_keyword_rows(ranked_by_query, ground_truth),
            }
        )
    return rows


def _dense_worker(ground_truth):
    from sentence_transformers import CrossEncoder
    from chitragupta.enrich import embed_index

    reranker = CrossEncoder(RERANK_MODEL)
    dense_ranked, reranked = {}, {}
    for row in ground_truth:
        key = row["citekey"]
        hits = embed_index.search(row["query"], k=K_POOL)
        dense_ranked[key] = collapse_to_citekeys(hits)[:K_REPORT]

        scores = reranker.predict([(row["query"], hit["snippet"]) for hit in hits])
        reranked_hits = [
            hit for _score, hit in sorted(zip(scores, hits), key=lambda pair: -pair[0])
        ]
        reranked[key] = collapse_to_citekeys(reranked_hits)[:K_REPORT]
    return dense_ranked, reranked


def dense_and_rerank_rows(model, ground_truth, tag):
    env = dict(os.environ, EMBEDDING_MODEL=model)
    payload_path = BENCH_DIR / "results" / tag / f"_dense_worker_{model.rsplit('/', 1)[-1]}.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [_venv_python(), str(Path(__file__)), "--dense-worker", model, "--out", str(payload_path)],
        env=env,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"dense worker for {model} exited {result.returncode}")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    dense_ranked = dict(payload["dense"])
    reranked = dict(payload["reranked"])
    return (
        {"row": f"dense-only: {model}", **score_keyword_rows(dense_ranked, ground_truth)},
        {"row": f"dense+rerank: {model}", **score_keyword_rows(reranked, ground_truth)},
    )


def specter2_row(ground_truth):
    """Ranks over the *whole* ledger (642 citekeys), not just the ground
    truth's own -- unlike bench_retrieval_compare.py's version -- so
    this row answers the same question every other row does: did you
    find it among everything, not among a pre-narrowed pool."""
    import embed_models as em

    all_citekeys = [r[0] for r in ledger.connect().execute("SELECT citekey FROM items")]
    paper_vectors = em.embed_paper(all_citekeys)

    def cosine(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    ranked_by_query = {}
    for row in ground_truth:
        query_vector = em.embed_query(row["query"])
        ranked = sorted(all_citekeys, key=lambda c: -cosine(query_vector, paper_vectors[c]))
        ranked_by_query[row["citekey"]] = ranked[:K_REPORT]
    return {
        "row": "SPECTER2 (adhoc_query + proximity, full corpus)",
        **score_keyword_rows(ranked_by_query, ground_truth),
    }


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
        query_vector = em.embed_query(row["query"])
        shortlist = sorted(all_citekeys, key=lambda c: -cosine(query_vector, paper_vectors[c]))[
            :shortlist_size
        ]

        query_embedding = dense_model.encode([row["query"]], show_progress_bar=False).tolist()
        raw = collection.query(
            query_embeddings=query_embedding,
            n_results=K_POOL,
            where={"citekey": {"$in": shortlist}},
        )
        hits = [
            {**meta, "snippet": doc[:500]}
            for doc, meta in zip(raw["documents"][0], raw["metadatas"][0])
        ]
        if not hits:
            ranked_by_query[row["citekey"]] = []
            continue
        scores = reranker.predict([(row["query"], hit["snippet"]) for hit in hits])
        reranked_hits = [
            hit for _score, hit in sorted(zip(scores, hits), key=lambda pair: -pair[0])
        ]
        ranked_by_query[row["citekey"]] = collapse_to_citekeys(reranked_hits)[:K_REPORT]
    return ranked_by_query


def cascade_row(winning_model, ground_truth, tag, shortlist_size=50):
    env = dict(os.environ, EMBEDDING_MODEL=winning_model)
    payload_path = BENCH_DIR / "results" / tag / "_cascade_worker.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            _venv_python(),
            str(Path(__file__)),
            "--cascade-worker",
            winning_model,
            "--out",
            str(payload_path),
            "--shortlist-size",
            str(shortlist_size),
        ],
        env=env,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"cascade worker exited {result.returncode}")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    ranked_by_query = dict(payload["ranked"])
    return {
        "row": f"cascade: SPECTER2 shortlist({shortlist_size}) -> {winning_model} +rerank",
        **score_keyword_rows(ranked_by_query, ground_truth),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tag", help="names bench/results/<tag>/")
    ap.add_argument("--dense-worker", default=None, metavar="MODEL", help=argparse.SUPPRESS)
    ap.add_argument("--cascade-worker", default=None, metavar="MODEL", help=argparse.SUPPRESS)
    ap.add_argument("--out", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--shortlist-size", type=int, default=50, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    self_check()
    ground_truth = build_keyword_ground_truth()

    if args.dense_worker:
        dense_ranked, reranked = _dense_worker(ground_truth)
        Path(args.out).write_text(
            json.dumps(
                {
                    "dense": list(dense_ranked.items()),
                    "reranked": list(reranked.items()),
                }
            ),
            encoding="utf-8",
        )
        return 0

    if args.cascade_worker:
        ranked_by_query = _cascade_worker(ground_truth, args.shortlist_size)
        Path(args.out).write_text(
            json.dumps({"ranked": list(ranked_by_query.items())}), encoding="utf-8"
        )
        return 0

    if not args.tag:
        print("--tag is required", file=sys.stderr)
        return 2

    print(
        f"{len(ground_truth)} keyword-bearing, parsed bib entries (self-retrieval ground truth)",
        flush=True,
    )

    rows = [bm25_row(ground_truth)] + wrapped_and_stripped_rows(ground_truth)
    for model in DENSE_MODELS:
        dense, rerank = dense_and_rerank_rows(model, ground_truth, args.tag)
        rows += [dense, rerank]
    rows.append(specter2_row(ground_truth))

    dense_rerank_rows = [r for r in rows if r["row"].startswith("dense+rerank: ")]
    winner = max(dense_rerank_rows, key=lambda r: r[f"ndcg@{K_REPORT}"] or 0.0)
    winning_model = winner["row"].removeprefix("dense+rerank: ")
    rows.append(cascade_row(winning_model, ground_truth, args.tag))

    print(f"\n{'row':50}  {'n':>3}  recall@{K_REPORT}  ndcg@{K_REPORT}")
    for row in rows:
        print(
            f"{row['row']:50}  {row['n_queries']:>3}  "
            f"{row[f'recall@{K_REPORT}']:>9}  {row[f'ndcg@{K_REPORT}']:>8}"
        )

    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    out_dir.mkdir(parents=True, exist_ok=True)
    record = out_dir / "comparison.json"
    record.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"\nRecord: {record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

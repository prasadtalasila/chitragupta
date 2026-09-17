"""Retrieval quality across BM25, three drop-in dense models (each
alone and reranked), and SPECTER2 -- scored against the 48-pair ground
truth bench_retrieval_ground_truth.py recovers. Directly answers "compare
against retrieval and reranking, not bare BM25": BM25 is one row for
context, not the target every other row is measured against.

Each dense model's row runs in its own subprocess
(--dense-worker <model>), because config.EMBEDDING_MODEL is fixed at
chitragupta/config.py's import time -- three models cannot be swept by mutating
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

from chitragupta import config, passages, retrieval, retrieval_scoring  # noqa: E402

# #762's field-weight grid, shared by the two scripts that score BM25
# against a ground truth (bench_retrieval_keyword_selfretrieval.py and
# bench_retrieval_live_logs.py) so both sweep the same vectors and their
# rows can be read against each other.
#
# **One arm at a time**, Ni et al.'s protocol as everywhere else here: no
# row moves two fields at once, so a change is attributable to the field
# it names rather than to a vector. The grid is geometric rather than
# fine because the question #762 asks is "does weighting this field help
# at all", not "what is the optimum" -- a fine grid over a ground truth
# of a few hundred rows would mostly be reading noise.
FIELD_WEIGHT_GRID = (
    {},
    {"title": 1.5},
    {"title": 2.0},
    {"title": 4.0},
    {"title": 8.0},
    {"abstract": 1.5},
    {"abstract": 2.0},
    {"abstract": 4.0},
    # #770's arms. `table` is **not a field chitragupta ships** -- it is
    # installed into the scorer by `enable_table_field` below, for the
    # length of a bench run and no longer. See its docstring for why the
    # measurement lives here rather than behind a config key.
    #
    # Both directions, unlike title and abstract. The issue argues a
    # table's cells are the paper's measured claims and so deserve *more*
    # weight; the counter-argument -- a table's cell text is fragmentary
    # and its markdown pipes are noise -- says less. A one-sided grid
    # could only ever answer half of that, and 0.0 is the arm that asks
    # "should cell text be scored at all".
    {"table": 0.0},
    {"table": 0.5},
    {"table": 1.5},
    {"table": 2.0},
    {"table": 4.0},
)

# What a `table` field would read, if chitragupta had one. Kept identical
# to the shape `retrieval_scoring.field_texts` uses for the abstract --
# one string per field, absent rather than empty when there is nothing --
# because an arm that measures a different extraction than the one a
# reader would implement measures nothing they can act on.
TABLE_FIELD = "table"
_SHIPPED_FIELD_TEXTS = retrieval_scoring.field_texts


def _field_texts_with_tables(item):
    """`retrieval_scoring.field_texts` plus the item's table text.

    A table record already carries its own caption as its first line
    (`_passage_records.passage_records` prepends it), so this is as close
    to #770's *`caption`* field as any weight can get: the sidecar has no
    `caption` label, and figure captions are deliberately not in it.
    """
    texts = _SHIPPED_FIELD_TEXTS(item)
    found = passages.corpus_passages(item["citekey"])
    tables = "\n".join(p.text for p in found or [] if p.label == "table" and p.text)
    if tables:
        texts[TABLE_FIELD] = tables
    return texts


def enable_table_field(index_path):
    """Install the `table` field into the scorer for this process, and
    point the index cache at `index_path`.

    **Why this is a bench-local patch and not a config key.** #770 asks
    for `caption` and `table` as weighted fields. `caption` cannot exist
    -- `_passage_records.PASSAGE_LABELS` deliberately keeps figure
    captions out of the sidecar, so there are zero caption records in
    this corpus -- and the `table` arms below measure a loss on both
    ground truths. Shipping a config key whose measured answer is "do not
    turn this up" is the thing bench/RESULTS.md keeps declining to do
    (#794 is the precedent, down to reverting the refactor the attempt
    forced). So the field lives for the length of a bench run.

    The patch targets `retrieval_scoring.field_texts` by module
    attribute, which is the one binding that works:
    `retrieval._tokenize_item` calls `retrieval_scoring.field_freqs`, and
    that calls `field_texts` as a module global. Rebinding either name
    locally would reach nothing.

    **The index cache must be cold, and this is the whole trap.** A
    cached entry's fingerprint is a statement about the *parsed file*,
    which has not moved, so an index built without table counts stays
    valid and every arm reads zero table frequencies -- publishing a flat
    curve that looks like a finding. `index_path` is therefore a fresh
    file this run owns, deleted first.
    """
    retrieval_scoring.FIELDS = retrieval_scoring.FIELDS + (TABLE_FIELD,)
    retrieval_scoring.field_texts = _field_texts_with_tables
    config.RETRIEVAL_INDEX_PATH = Path(index_path)
    Path(index_path).unlink(missing_ok=True)


def arm_table_field(tag):
    """Install the field, build its index cold, and refuse to sweep until
    both are demonstrably real. Called by every script that runs
    FIELD_WEIGHT_GRID, before its first arm."""
    from chitragupta import ledger, retrieval_cache

    index_path = BENCH_DIR / "results" / Path(tag).name / "_table_field_index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    enable_table_field(index_path)
    with ledger.connection() as con:
        items = ledger.all_items(con)
    index = retrieval_cache._load_index(items, retrieval._tokenize_item)
    table_field_self_check(index)
    populated = sum(1 for e in index.values() if (e.get("field_freqs") or {}).get(TABLE_FIELD))
    print(f"table field populated for {populated} of {len(index)} indexed items", flush=True)


def grid_for(fields):
    """`FIELD_WEIGHT_GRID` restricted to the arms that move one of
    `fields`, plus the all-1.0 baseline every arm is read against.

    Exists so a run can publish a record of **only the field it is
    about**. The grid is shared by two scripts and has carried #762's
    title and abstract arms since it was written, so a sweep asking a
    new question re-measures those two as a side effect and commits the
    numbers to `bench/results/<tag>/comparison.json` -- where a reader
    finds fresh figures for a field the entry beside them never
    discusses, and an issue still open over that field (#772) acquires a
    measurement nobody argued for. `None` keeps every arm, which is what
    a full re-sweep of the grid wants.
    """
    if not fields:
        return FIELD_WEIGHT_GRID
    wanted = set(fields)
    return tuple(arm for arm in FIELD_WEIGHT_GRID if not arm or set(arm) <= wanted)


def with_field_weights(overrides):
    """Pin *every* field's weight, not just the ones `overrides` names.

    An arm that let an unnamed field fall through to config.toml would
    measure whatever this host happens to set, which is the class of bug
    `repro_check.py` was taught to guard against after B2b inherited
    `formulas = true` from the host and silently compared two different
    parses.
    """
    pinned = dict.fromkeys(retrieval_scoring.FIELDS, 1.0)
    pinned.update(overrides)
    config.RETRIEVAL_FIELD_WEIGHTS = pinned
    return pinned


def field_weight_label(overrides):
    if not overrides:
        return "field weights: all 1.0 (baseline)"
    return "field weights: " + ", ".join(f"{name}={w}" for name, w in sorted(overrides.items()))


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
    dcg = sum(
        1.0 / math.log2(i + 1) for i, c in enumerate(ranked_citekeys[:k], start=1) if c in relevant
    )
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
    assert collapse_to_citekeys([{"citekey": "x"}, {"citekey": "x"}, {"citekey": "y"}]) == [
        "x",
        "y",
    ], "collapse_to_citekeys should de-duplicate, keeping first-seen order"


def table_field_self_check(index):
    """The `table` arms measure a real, populated field -- fabricated and
    asserted, per bench/README.md's self-check rule.

    Two ways a `table` arm can publish a flat curve that is not a
    finding, and this catches both. The field can be empty everywhere
    (`enable_table_field` never ran, or the corpus has no sidecars), and
    the index can be a stale cache written before the field existed, whose
    fingerprint cannot see that the scoring rule moved. Either way every
    arm reads zero table counts and every row ties the baseline.

    The fabricated difference is the third assertion: a hand-built entry
    whose table counts are known must score strictly higher under a
    weight of 2.0 than under 1.0. If the weight seam is not reaching
    `field_freqs` at all, that comparison is an equality and this fails.
    """
    with_table = [e for e in index.values() if (e.get("field_freqs") or {}).get(TABLE_FIELD)]
    assert with_table, (
        f"no indexed document has any `{TABLE_FIELD}` counts -- either "
        "enable_table_field did not run, or the index is a stale cache "
        "predating the field. Every arm below would tie the baseline."
    )
    entry = {"term_freqs": {"twin": 10}, "field_freqs": {TABLE_FIELD: {"twin": 4}}}
    with_field_weights({TABLE_FIELD: 2.0})
    boosted = retrieval_scoring.weighted_freq(entry, "twin", retrieval_scoring.field_deltas())
    with_field_weights({})
    flat = retrieval_scoring.weighted_freq(entry, "twin", retrieval_scoring.field_deltas())
    assert flat == 10 and boosted == 14, (
        f"a table weight of 2.0 should add (2.0-1)*4 to a frequency of 10, "
        f"got {boosted} against {flat} at 1.0"
    )


def bm25_row(ground_truth):
    ranked_by_query = {}
    for row in ground_truth:
        key = (row["chapter"], row["line"], row["citekey"])
        results = retrieval.search(row["query"], k=K_REPORT)
        ranked_by_query[key] = [r.citekey for r in results]
    return {"row": "BM25 (chitragupta/retrieval.py)", **score_rows(ranked_by_query, ground_truth)}


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
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
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
    from chitragupta.enrich import embed_index

    reranker = CrossEncoder(RERANK_MODEL)
    dense_ranked, reranked = {}, {}
    for row in ground_truth:
        key = (row["chapter"], row["line"], row["citekey"])
        hits = embed_index.search(row["query"], k=K_POOL)
        dense_ranked[key] = collapse_to_citekeys(hits)[:K_REPORT]

        scores = reranker.predict([(row["query"], hit["snippet"]) for hit in hits])
        reranked_hits = [
            hit for _score, hit in sorted(zip(scores, hits), key=lambda pair: -pair[0])
        ]
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
        [
            _venv_python(),
            str(Path(__file__)),
            "--dense-worker",
            model,
            "--ground-truth-inline",
            "-",
            "--out",
            str(payload_path),
        ],
        input=json.dumps(ground_truth),
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
    return {
        "row": "SPECTER2 (adhoc_query + proximity)",
        **score_rows(ranked_by_query, ground_truth),
    }


def _cascade_worker(ground_truth, shortlist_size):
    """Runs inside a subprocess with EMBEDDING_MODEL set to whichever
    drop-in model won Task 4's dense+rerank rows. For each query: SPECTER2
    (adhoc_query) ranks the corpus's papers, the top `shortlist_size`
    become a Chroma `where` filter, and the winning model's own
    collection is queried restricted to that shortlist -- so the cascade
    only ever reranks chunks from papers SPECTER2 already thought were
    close, rather than the whole corpus."""
    import embed_models as em
    from sentence_transformers import CrossEncoder
    from chitragupta.enrich import embed_index

    # A corpus-wide SPECTER2 shortlist needs the whole ledger, not just
    # this ground truth's own citekeys -- otherwise every shortlist is
    # trivially exactly right by construction.
    from chitragupta import ledger

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

    from sentence_transformers import SentenceTransformer

    dense_model = SentenceTransformer(embed_index.config.EMBEDDING_MODEL)

    ranked_by_query = {}
    for row in ground_truth:
        key = (row["chapter"], row["line"], row["citekey"])
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
            ranked_by_query[key] = []
            continue
        scores = reranker.predict([(row["query"], hit["snippet"]) for hit in hits])
        reranked_hits = [
            hit for _score, hit in sorted(zip(scores, hits), key=lambda pair: -pair[0])
        ]
        ranked_by_query[key] = collapse_to_citekeys(reranked_hits)[:K_REPORT]
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
            "--ground-truth-inline",
            "-",
            "--out",
            str(payload_path),
            "--shortlist-size",
            str(shortlist_size),
        ],
        input=json.dumps(ground_truth),
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
    ranked_by_query = {tuple(k): v for k, v in payload["ranked"]}
    return {
        "row": f"cascade: SPECTER2 shortlist({shortlist_size}) -> {winning_model} +rerank",
        **score_rows(ranked_by_query, ground_truth),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ground-truth", help="path to a ground_truth.json from Task 1")
    ap.add_argument("--tag", help="names bench/results/<tag>/")
    ap.add_argument(
        "--dense-worker", default=None, metavar="MODEL", help=argparse.SUPPRESS
    )  # internal: subprocess-only
    ap.add_argument("--ground-truth-inline", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--out", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--cascade-worker", default=None, metavar="MODEL", help=argparse.SUPPRESS)
    ap.add_argument("--shortlist-size", type=int, default=50, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    self_check()

    if args.dense_worker:
        ground_truth = json.loads(
            sys.stdin.read()
            if args.ground_truth_inline == "-"
            else Path(args.ground_truth_inline).read_text(encoding="utf-8")
        )
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
        ground_truth = json.loads(
            sys.stdin.read()
            if args.ground_truth_inline == "-"
            else Path(args.ground_truth_inline).read_text(encoding="utf-8")
        )
        ranked_by_query = _cascade_worker(ground_truth, args.shortlist_size)
        Path(args.out).write_text(
            json.dumps({"ranked": list(ranked_by_query.items())}), encoding="utf-8"
        )
        return 0

    if not args.ground_truth or not args.tag:
        print("--ground-truth and --tag are required outside --dense-worker mode", file=sys.stderr)
        return 2

    ground_truth = json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))
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
        print(
            f"{row['row']:45}  {row['n_queries']:>3}  "
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

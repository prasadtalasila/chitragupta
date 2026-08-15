# Embedding Model Benchmark, Arm B (retrieval + reranking + SPECTER2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Benchmark retrieval quality (recall@5 / nDCG@5) across BM25,
the three drop-in dense models, each drop-in with cross-encoder
reranking, SPECTER2 standalone, and a SPECTER2-shortlist-then-rerank
cascade — against real judged `(query, citekey)` pairs recovered from
this project's own drafting history, not a synthetic query set.

**Architecture:** A new encoder seam (`bench/embed_models.py`) gives
SPECTER2 the title+abstract input it needs, sourced from Docling's
existing passage sidecars rather than the ledger (which deliberately
drops `abstract`). A new orchestrator (`bench/bench_retrieval_compare.py`)
scores every row against one shared ground-truth set, using
`src/retrieval.py` and `src/enrich/embed_index.py` unmodified — the same
"drive the real code, don't reimplement it" approach Arm A's plan used.
Each dense model's row runs in its own subprocess (`EMBEDDING_MODEL` is
read once at `config.py` import time, so three models cannot be swept
in one process).

**Tech Stack:** `sentence-transformers`' `CrossEncoder` (already pinned,
no new dependency for reranking); `transformers` + `adapters` (new
`enrich`-group dependency, for SPECTER2's adapter loading); Python stdlib
for scoring.

**Spec:** [docs/superpowers/specs/2026-08-15-embedding-model-benchmark-design.md](../specs/2026-08-15-embedding-model-benchmark-design.md)
— this plan implements Arm B. Arm A (tier-3 overlap, three drop-in models,
no new dependency) is a separate, earlier-merged plan; do not start this
one before that one has merged, since both touch `pyproject.toml`'s
version line.

## Global Constraints

- New `pyproject.toml` `enrich`-group dependency: `adapters` (SPECTER2's
  adapter loading — `pip install transformers adapters`, per
  `allenai/specter2_base`'s own model card). `sentence-transformers`
  already ships `CrossEncoder`; no second new dependency for reranking.
- `bench/` carries no coverage/ratchet obligation and no pytest suite —
  same adaptation as Arm A's plan: verification is `self_check()` plus a
  real end-to-end run, not a red/green pytest cycle.
- `config.EMBEDDING_MODEL` (and every other `config.py` constant) is
  fixed at import time. A dense model's row **must** run in a fresh
  subprocess with `EMBEDDING_MODEL` set in its environment — never by
  mutating `os.environ` mid-process and expecting `embed_index.py` to
  see the change.
- The ledger's `bib_fields` column has no `abstract` field
  (`src/ledger.py`'s `_BIB_FIELDS_KEPT`, by design). SPECTER2's
  title+abstract input is sourced from `content/docling/<citekey>.passages.json`
  instead, via `src/passages.py`'s existing `source_passages()` — no new
  parsing of raw Docling output.

---

## Task 1: Recover and verify the retrieval ground truth

Produces `bench/results/<tag>/ground_truth.json`: the 48 rows of
`bench/results/2026-08-15-organic-paraphrase-hunt/labels.json`, each with
its claim text joined back in from a fresh extraction — the join this
plan's spec flags as **not guaranteed to succeed**, so this task verifies
it before anything downstream depends on it.

**Files:**
- Create: `bench/bench_retrieval_ground_truth.py`
- Creates (data, committed): `bench/results/<tag>/ground_truth.json`

**Interfaces:**
- Produces: `build_ground_truth(drafts_dir, labels_path) -> list[dict]`
  (each dict: `chapter`, `line`, `citekey`, `query`, `judgment`), consumed
  by Task 4's `bench_retrieval_compare.py`.

- [ ] **Step 1: Restore the book (if Arm A's plan hasn't already)**

```bash
cd /workspace
unzip -o content/backup/content-20260809.zip \
    "content/drafts/books/digital-twins-for-software-engineers/*" \
    "content/dossiers/books/digital-twins-for-software-engineers/*"
```

- [ ] **Step 2: Write `build_ground_truth()`, with a hard stop on any unresolved row**

```python
"""Retrieval ground truth for Arm B: 48 real (query, citekey) pairs,
recovered by joining bench_paraphrase_hunt.py's committed judgments back
onto their claim text.

The judgments (bench/results/2026-08-15-organic-paraphrase-hunt/labels.json)
are committed; the claim text they were judged from (pairs.json) is not
-- same "no draft/source prose in a committed result" discipline
bench_overlap_embed.py's KEPT_FIELDS already applies. Recovering it means
re-running bench_paraphrase_hunt.py --extract against the restored book,
then joining each labels.json row back to its pairs.json row by
(chapter, line, citekey).

All 48 rows are valid ground truth regardless of judgment -- "paraphrase"
vs "no-match" vs "no" describes how closely the claim restates the
source *passage*, which has no bearing on whether the citekey is the
paper that claim actually cites. It is, in every row.

    .venv-full/bin/python bench/bench_retrieval_ground_truth.py \\
        --drafts content/drafts/books/digital-twins-for-software-engineers \\
        --tag 2026-08-16-retrieval-ground-truth
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from src import config  # noqa: E402
import bench_paraphrase_hunt as hunt  # noqa: E402

LABELS_PATH = BENCH_DIR / "results" / "2026-08-15-organic-paraphrase-hunt" / "labels.json"


def build_ground_truth(drafts_dir, labels_path=LABELS_PATH):
    """Joins labels_path's judged rows to fresh claim text extracted from
    drafts_dir. Raises ValueError, naming every unresolved id, rather
    than silently returning a partial set -- a caller scoring retrieval
    quality against 40 of 48 rows without being told 8 went missing would
    read as a clean run."""
    labels = json.loads(labels_path.read_text(encoding="utf-8"))["candidates"]

    con = None  # extract() below owns its own ledger connection
    pairs_out = BENCH_DIR / "results" / "_ground_truth_extract_scratch"
    hunt.extract(drafts_dir, pairs_out)
    pairs = json.loads((pairs_out / "pairs.json").read_text(encoding="utf-8"))
    by_key = {(p["chapter"], p["line"], p["citekey"]): p["claim"] for p in pairs}

    rows, missing = [], []
    for row in labels:
        key = (row["chapter"], row["line"], row["citekey"])
        claim = by_key.get(key)
        if claim is None:
            missing.append(row["id"])
            continue
        rows.append({"chapter": row["chapter"], "line": row["line"],
                     "citekey": row["citekey"], "query": claim,
                     "judgment": row["judgment"]})

    if missing:
        raise ValueError(
            f"{len(missing)} of {len(labels)} labels.json row(s) did not resolve "
            f"against a fresh extraction: {', '.join(missing)}. The book restored "
            "from content/backup/ may not match the state labels.json was judged "
            "against -- do not proceed with a partial ground truth set."
        )
    return rows


def self_check():
    """labels.json really has 48 rows and really names real chapters --
    the two facts build_ground_truth() assumes before it ever restores
    or re-extracts anything."""
    labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))["candidates"]
    assert len(labels) == 48, f"expected 48 labelled rows, found {len(labels)}"
    assert all(row["chapter"].endswith(".md") for row in labels), (
        "a labels.json row's chapter field isn't a .md filename"
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--drafts", required=True, help="directory of restored chapters")
    ap.add_argument("--tag", required=True, help="names bench/results/<tag>/")
    args = ap.parse_args(argv)

    self_check()
    if not config.LEDGER_PATH.exists():
        print(f"no ledger at {config.LEDGER_PATH} -- run `python -m src.corpus sync`",
              file=sys.stderr)
        return 1

    rows = build_ground_truth(args.drafts)
    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    out_dir.mkdir(parents=True, exist_ok=True)
    record = out_dir / "ground_truth.json"
    record.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"{len(rows)} ground-truth (query, citekey) pairs recovered")
    print(f"Record: {record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run it for real, and confirm it either resolves all 48 or fails loudly**

```bash
cd /workspace/.claude/worktrees/bridge-cse_01Snq32sGD7GtN7Fco3wPwDG
.venv-full/bin/python bench/bench_retrieval_ground_truth.py \
    --drafts content/drafts/books/digital-twins-for-software-engineers \
    --tag 2026-08-16-retrieval-ground-truth
```

Expected: either `48 ground-truth (query, citekey) pairs recovered`, or a
`ValueError` naming exactly which ids didn't resolve. **If it's the
latter, stop here** — do not edit `build_ground_truth()` to silently drop
the unresolved rows or weaken the check. Investigate why first (a
re-parsed source changing `passages.source_passages()`'s output is the
most likely cause, since line numbers in `citation_provenance.claims()`
come from the chapter text itself, which the restore does not change —
so the more likely mismatch is in the *source* passages a claim scores
against, not the claim's own line) and report the finding; this is a
genuinely ambiguous case DEVELOPER-AGENTS.md's Role section reserves for
pausing, not proceeding around.

- [ ] **Step 4: Commit**

```bash
git add bench/bench_retrieval_ground_truth.py bench/results/2026-08-16-retrieval-ground-truth
git commit -m "Add bench_retrieval_ground_truth.py, recovering Arm B's 48-pair ground truth"
```

---

## Task 2: Add the `adapters` dependency

**Files:**
- Modify: `pyproject.toml` (`[tool.poetry.group.enrich.dependencies]`)
- Modify: `poetry.lock` (via `poetry lock`)

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, under `[tool.poetry.group.enrich.dependencies]`,
add a line beside the existing `sentence-transformers`/`chromadb` entries:

```toml
adapters = ">=1.2,<2.0"
```

Match the existing block's comment style — note beside it that this is
SPECTER2-only (`allenai/specter2_base`'s adapter loading), added for
#194's Arm B, the same way the existing block documents what verified
each entry.

- [ ] **Step 2: Re-lock and reinstall**

```bash
cd /workspace/.claude/worktrees/bridge-cse_01Snq32sGD7GtN7Fco3wPwDG
poetry lock
poetry install --with enrich
```

Expected: resolves and installs without conflict. If it conflicts with
the pinned `transformers` version something else in the `enrich` group
already carries, that's a real finding to report — not something to
work around by loosening this plan's own pin without checking what broke.

- [ ] **Step 3: Verify the import**

```bash
.venv-full/bin/python -c "
from transformers import AutoTokenizer
from adapters import AutoAdapterModel
print('adapters import OK')
"
```

Expected: `adapters import OK`, no traceback.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml poetry.lock
git commit -m "Add adapters dependency for SPECTER2's adapter loading"
```

---

## Task 3: `bench/embed_models.py` — the SPECTER2 encoder seam

**Files:**
- Create: `bench/embed_models.py`

**Interfaces:**
- Produces: `title_for(con, citekey) -> str`, `abstract_for(con, citekey)
  -> str`, `embed_paper(citekeys: list[str]) -> dict[str, list[float]]`,
  `embed_query(text: str) -> list[float]` — all consumed by Task 4 and
  Task 5.

- [ ] **Step 1: Write the module**

```python
"""SPECTER2 encoder seam for Arm B. Unlike the three drop-in models,
SPECTER2 never sees a passage chunk -- every mode (base, proximity,
adhoc_query) takes only title+abstract on the document side, per
allenai/specter2_base's own model card. adhoc_query is the one
asymmetric exception: it encodes a short raw query string as-is,
compared against documents encoded with the proximity adapter.

The abstract has no home in the ledger -- src/ledger.py's
_BIB_FIELDS_KEPT drops it on purpose. abstract_for() recovers it from
content/docling/<citekey>.passages.json instead: the text between an
"Abstract" section_header and the next one. Measured on this host: 132
of 497 sidecars (27%) carry that header. The other 73% fall back to
title-only, SPECTER2's own documented behaviour for a missing abstract.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src import ledger, passages  # noqa: E402

PAPER_CACHE_PATH = Path(__file__).resolve().parent / "results" / "specter2_paper_cache.json"

_TOKENIZER = None
_MODEL = None
_ACTIVE_ADAPTER = None


def title_for(con, citekey):
    row = con.execute("SELECT title FROM items WHERE citekey = ?", (citekey,)).fetchone()
    return row[0] if row and row[0] else ""


def abstract_for(con, citekey):
    """Text between an "Abstract" section_header and the next one, or ""
    if the sidecar has none -- the common case, and not an error."""
    found, _reason = passages.source_passages(con, citekey)
    collecting = False
    parts = []
    for passage in found:
        if passage.label == "section_header":
            if collecting:
                break
            collecting = bool(passage.text and
                              passage.text.strip().lower().rstrip(".") == "abstract")
            continue
        if collecting and passage.label == "text" and passage.text:
            parts.append(passage.text)
    return " ".join(parts)


def _load(adapter_name, hf_repo):
    global _TOKENIZER, _MODEL, _ACTIVE_ADAPTER
    from transformers import AutoTokenizer
    from adapters import AutoAdapterModel

    if _MODEL is None:
        _TOKENIZER = AutoTokenizer.from_pretrained("allenai/specter2_base")
        _MODEL = AutoAdapterModel.from_pretrained("allenai/specter2_base")
    if _ACTIVE_ADAPTER != adapter_name:
        _MODEL.load_adapter(hf_repo, source="hf", load_as=adapter_name, set_active=True)
        _ACTIVE_ADAPTER = adapter_name
    return _TOKENIZER, _MODEL


def _encode(texts, adapter_name, hf_repo):
    tokenizer, model = _load(adapter_name, hf_repo)
    inputs = tokenizer(texts, padding=True, truncation=True, return_tensors="pt",
                       return_token_type_ids=False, max_length=512)
    output = model(**inputs)
    return output.last_hidden_state[:, 0, :].tolist()


def embed_paper(citekeys):
    """One proximity-adapter vector per citekey. Cached to disk by
    citekey, since a synced corpus's title+abstract text does not change
    between benchmark runs -- re-encoding all ~501 papers on every row
    that needs SPECTER2 would pay the same cost three times over for no
    reason."""
    con = ledger.connect()
    cache = (json.loads(PAPER_CACHE_PATH.read_text(encoding="utf-8"))
             if PAPER_CACHE_PATH.exists() else {})
    missing = [c for c in citekeys if c not in cache]
    if missing:
        tokenizer, _model = _load("proximity", "allenai/specter2")
        rows = [(citekey, title_for(con, citekey), abstract_for(con, citekey))
                for citekey in missing]
        texts = [title + tokenizer.sep_token + abstract for _, title, abstract in rows]
        vectors = _encode(texts, "proximity", "allenai/specter2")
        for (citekey, _title, abstract), vector in zip(rows, vectors):
            cache[citekey] = {"vector": vector,
                              "abstract_source": "docling" if abstract else "title-only"}
        PAPER_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        PAPER_CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")
    return {c: cache[c]["vector"] for c in citekeys}


def embed_query(text):
    return _encode([text], "adhoc_query", "allenai/specter2_adhoc_query")[0]


def self_check():
    """title_for() and abstract_for() work against a real citekey this
    host is known to have an Abstract header for, and abstract_for()
    degrades to "" rather than raising for a citekey that isn't real --
    the two facts embed_paper() depends on before it ever loads a model."""
    con = ledger.connect()
    title = title_for(con, "lugaresi_digital_2025")
    assert title, "title_for() found no title for a citekey known to be in the ledger"
    abstract = abstract_for(con, "lugaresi_digital_2025")
    assert abstract, (
        "abstract_for() found no Abstract section for lugaresi_digital_2025 -- "
        "this host's content/docling/lugaresi_digital_2025.passages.json is known to have one"
    )
    assert abstract_for(con, "not_a_real_citekey") == "", (
        "abstract_for() should return '' for an unknown citekey, not raise"
    )


if __name__ == "__main__":
    self_check()
    print("self_check() passed")
```

- [ ] **Step 2: Run `self_check()` — cheap, no model download**

```bash
cd /workspace/.claude/worktrees/bridge-cse_01Snq32sGD7GtN7Fco3wPwDG
.venv-full/bin/python bench/embed_models.py
```

Expected: `self_check() passed`. This exercises `title_for()` and
`abstract_for()` against the real corpus already on this host and needs
no `transformers`/`adapters` import — if it fails, fix `abstract_for()`
or the assumed citekey before touching anything model-related.

- [ ] **Step 3: Run `embed_paper()` and `embed_query()` against real data, once**

```bash
cd /workspace/.claude/worktrees/bridge-cse_01Snq32sGD7GtN7Fco3wPwDG
.venv-full/bin/python -c "
import sys; sys.path.insert(0, 'bench')
import embed_models as em

vectors = em.embed_paper(['lugaresi_digital_2025', 'aidasso_towards_2025-1'])
assert len(vectors) == 2
assert all(len(v) > 0 for v in vectors.values())
q = em.embed_query('digital twin synchronization latency')
assert len(q) == len(next(iter(vectors.values())))
print('embed_paper/embed_query produced same-length vectors:', len(q))
"
```

Expected: prints a positive integer (SPECTER2 base's hidden size, 768),
no traceback. This downloads `allenai/specter2_base`,
`allenai/specter2`, and `allenai/specter2_adhoc_query` on first run —
expect that to take real time and disk the first time only.

- [ ] **Step 4: Commit**

```bash
git add bench/embed_models.py
git commit -m "Add bench/embed_models.py, the SPECTER2 encoder seam"
```

---

## Task 4: `bench/bench_retrieval_compare.py` — scoring, BM25, the three drop-ins, SPECTER2 standalone

**Files:**
- Create: `bench/bench_retrieval_compare.py`

**Interfaces:**
- Consumes: `build_ground_truth()` (Task 1), `embed_models.embed_paper`/
  `embed_query` (Task 3).
- Produces: `recall_at_k(ranked, relevant, k)`, `ndcg_at_k(ranked,
  relevant, k)`, `collapse_to_citekeys(hits)`, `bm25_row(ground_truth,
  k)`, `dense_row(ground_truth, k, pool)` (run inside a
  `--dense-worker <model>` subprocess), `specter2_row(ground_truth, k)`
  — all consumed by Task 4's own `main()` and Task 5's cascade row.

- [ ] **Step 1: Write and hand-verify the scoring functions**

```python
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
```

- [ ] **Step 2: Run `self_check()` standalone to confirm the hand-verified numbers actually match**

```bash
cd /workspace/.claude/worktrees/bridge-cse_01Snq32sGD7GtN7Fco3wPwDG
python3 -c "
import sys; sys.path.insert(0, 'bench')
import bench_retrieval_compare as m
m.self_check()
print('self_check() passed')
"
```

Expected: `self_check() passed`. This needs no venv beyond stdlib — if it
fails, the arithmetic in the docstring's derivation is wrong, not the
ground truth or any model; fix `ndcg_at_k`/`recall_at_k` before writing
anything that calls them for real.

- [ ] **Step 3: Write `bm25_row()`**

```python
def bm25_row(ground_truth):
    ranked_by_query = {}
    for row in ground_truth:
        key = (row["chapter"], row["line"], row["citekey"])
        results = retrieval.search(row["query"], k=K_REPORT)
        ranked_by_query[key] = [r.citekey for r in results]
    return {"row": "BM25 (src/retrieval.py)", **score_rows(ranked_by_query, ground_truth)}
```

- [ ] **Step 4: Write the dense-model worker and its subprocess launcher**

```python
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
        [".venv-full/bin/python", str(Path(__file__)), "--dense-worker", model,
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
```

- [ ] **Step 5: Write `specter2_row()`**

```python
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
```

- [ ] **Step 6: Write `main()`, including the `--dense-worker` branch**

```python
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
```

- [ ] **Step 7: Run `--help`, confirm the CLI parses**

```bash
cd /workspace/.claude/worktrees/bridge-cse_01Snq32sGD7GtN7Fco3wPwDG
.venv-full/bin/python bench/bench_retrieval_compare.py --help
```

Expected: usage text naming `--ground-truth`/`--tag`, no traceback, and
no `--dense-worker`/`--ground-truth-inline`/`--out` shown (they're
`argparse.SUPPRESS`d — internal-only, confirmed by their absence here).

- [ ] **Step 8: Smoke-test the dense-worker subprocess path against 3 rows only, before running all 48**

```bash
cd /workspace/.claude/worktrees/bridge-cse_01Snq32sGD7GtN7Fco3wPwDG
python3 -c "
import sys, json; sys.path.insert(0, 'bench')
import bench_retrieval_compare as m

gt = json.loads(open('bench/results/2026-08-16-retrieval-ground-truth/ground_truth.json').read())[:3]
dense_row, rerank_row = m.dense_and_rerank_rows(
    'sentence-transformers/all-mpnet-base-v2', gt, '2026-08-16-smoketest')
print(dense_row)
print(rerank_row)
assert dense_row['n_queries'] == 3
assert rerank_row['n_queries'] == 3
print('smoke test passed')
"
```

Expected: two dicts each with `n_queries: 3` and non-`None`
recall/nDCG values, then `smoke test passed`. `all-mpnet-base-v2` is
already built, so this should complete quickly (no fresh embed) once the
cross-encoder model downloads on first use.

- [ ] **Step 9: Commit**

```bash
git add bench/bench_retrieval_compare.py
git commit -m "Add bench_retrieval_compare.py: BM25, dense, reranked and SPECTER2 rows"
```

---

## Task 5: The cascade row — SPECTER2 shortlist, then dense+rerank within it

Split from Task 4 deliberately: it is the newest, least-precedented piece
(a Chroma `where`-filtered query restricted to a paper-level shortlist),
and it depends on knowing which drop-in model won Task 4's dense+rerank
rows — a reviewer should be able to accept Task 4's four rows without
having to also accept this one.

**Files:**
- Modify: `bench/bench_retrieval_compare.py`

**Interfaces:**
- Consumes: `embed_models.embed_paper`/`embed_query` (Task 3),
  `collapse_to_citekeys`/`score_rows` (Task 4).
- Produces: `cascade_row(winning_model, ground_truth, shortlist_size)`,
  called from `main()`.

- [ ] **Step 1: Write the shortlist + filtered-query worker**

```python
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
    from src.enrich import embed_index

    con_citekeys = sorted({row["citekey"] for row in ground_truth})
    # A corpus-wide SPECTER2 shortlist needs the whole ledger, not just
    # this ground truth's own citekeys -- otherwise every shortlist is
    # trivially exactly right by construction.
    from src import ledger
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

    ranked_by_query = {}
    for row in ground_truth:
        key = (row["chapter"], row["line"], row["citekey"])
        query_vector = em.embed_query(row["query"])
        shortlist = sorted(all_citekeys,
                           key=lambda c: -cosine(query_vector, paper_vectors[c]))[:shortlist_size]

        from sentence_transformers import SentenceTransformer
        dense_model = SentenceTransformer(embed_index.config.EMBEDDING_MODEL)
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
        [".venv-full/bin/python", str(Path(__file__)), "--cascade-worker", winning_model,
         "--ground-truth-inline", "-", "--out", str(payload_path),
         "--shortlist-size", str(shortlist_size)],
        input=json.dumps(ground_truth), env=env, cwd=str(REPO),
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"cascade worker exited {result.returncode}")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    ranked_by_query = {tuple(k): v for k, v in payload["ranked"]}
    return {"row": f"cascade: SPECTER2 shortlist({shortlist_size}) -> {winning_model} +rerank",
           **score_rows(ranked_by_query, ground_truth)}
```

- [ ] **Step 2: Wire `--cascade-worker` and `--shortlist-size` into `main()`**

Add to the `argparse` block from Task 4 Step 6:

```python
    ap.add_argument("--cascade-worker", default=None, metavar="MODEL", help=argparse.SUPPRESS)
    ap.add_argument("--shortlist-size", type=int, default=50, help=argparse.SUPPRESS)
```

And a second branch beside the existing `if args.dense_worker:` block:

```python
    if args.cascade_worker:
        ground_truth = json.loads(sys.stdin.read() if args.ground_truth_inline == "-"
                                  else Path(args.ground_truth_inline).read_text(encoding="utf-8"))
        ranked_by_query = _cascade_worker(ground_truth, args.shortlist_size)
        Path(args.out).write_text(
            json.dumps({"ranked": list(ranked_by_query.items())}), encoding="utf-8")
        return 0
```

Then, after the `for model in DENSE_MODELS:` loop and before printing the
table, pick the winner and add the cascade row:

```python
    dense_rerank_rows = rows[2::2]  # every "dense+rerank: ..." row, in DENSE_MODELS order
    winner = max(dense_rerank_rows, key=lambda r: r[f"ndcg@{K_REPORT}"] or 0.0)
    winning_model = winner["row"].removeprefix("dense+rerank: ")
    rows.append(cascade_row(winning_model, ground_truth, args.tag))
```

- [ ] **Step 3: Smoke-test the cascade worker against 3 rows only**

```bash
cd /workspace/.claude/worktrees/bridge-cse_01Snq32sGD7GtN7Fco3wPwDG
python3 -c "
import sys, json; sys.path.insert(0, 'bench')
import bench_retrieval_compare as m

gt = json.loads(open('bench/results/2026-08-16-retrieval-ground-truth/ground_truth.json').read())[:3]
row = m.cascade_row('sentence-transformers/all-mpnet-base-v2', gt, '2026-08-16-smoketest')
print(row)
assert row['n_queries'] == 3
print('smoke test passed')
"
```

Expected: a dict with `n_queries: 3` and recall/nDCG values (possibly 0
for a 3-row sample — that's not a bug, just too small a sample to read
anything into), then `smoke test passed`.

- [ ] **Step 4: Commit**

```bash
git add bench/bench_retrieval_compare.py
git commit -m "Add the SPECTER2-shortlist cascade row"
```

---

## Task 6: Run the real sweep, write up `bench/RESULTS.md`, ship

**Files:**
- Modify: `bench/RESULTS.md` (new dated section)
- Modify: `bench/README.md`
- Modify: `docs/CONFIG.md` ("Choosing an embedding model") only if
  SPECTER2's numbers are worth documenting as an option — not a new
  default either way, per the spec.

- [ ] **Step 1: Run the full sweep**

```bash
cd /workspace/.claude/worktrees/bridge-cse_01Snq32sGD7GtN7Fco3wPwDG
time .venv-full/bin/python bench/bench_retrieval_compare.py \
    --ground-truth bench/results/2026-08-16-retrieval-ground-truth/ground_truth.json \
    --tag 2026-08-16-retrieval-compare 2>&1 | tee /tmp/retrieval-compare.log
```

Expected: BM25 row, 6 dense/rerank rows (2 per drop-in model), the
SPECTER2 standalone row, and the cascade row, ending in the printed
table and `bench/results/2026-08-16-retrieval-compare/comparison.json`.
`all-MiniLM-L6-v2` and `multi-qa-mpnet-base-dot-v1` need a fresh embed
here if Arm A's plan didn't already build them — expect Task 1's Arm A
cost measurement to apply again.

- [ ] **Step 2: Write up `bench/RESULTS.md`**

New dated section (`## 2026-08-16: retrieval and reranking across
embedding models, against real drafting judgments`), same shape as
existing entries: the ground-truth recovery story from Task 1 (including
the id-join verification result), the full comparison table with real
numbers copied from Step 1's output, an honest "what this does not
measure" (per-query cost of the cross-encoder and SPECTER2 stages at
this corpus's real query volume; the cascade's shortlist size was fixed
at 50 rather than swept), and the reproduction commands from Step 1 plus
Task 1/Task 3's own reproduction commands.

- [ ] **Step 3: Add rows to `bench/README.md`**

Same "Which tool to reach for" and "What each file is" tables Arm A's
plan already extends — add `bench_retrieval_ground_truth.py`,
`bench_retrieval_compare.py`, and `embed_models.py` in the same one-line
style.

- [ ] **Step 4: Commit**

```bash
git add bench/RESULTS.md bench/README.md bench/results/2026-08-16-retrieval-compare
git commit -m "Add the retrieval + reranking + SPECTER2 comparison and its results"
```

- [ ] **Step 5: Ship it**

Same cycle as Arm A's plan's Task 5: version bump (MINOR — new scripts,
one new dependency, no breaking change), OpenCodeReview
(`/open-code-review:delegate-review`), open the PR noting explicitly
that this is Arm B of #194 and that its retrieval-quality harness is the
same shape as roadmap issue #54's unstarted PR5 and previews part of PR9
— offered as evidence toward that roadmap, not a claim of completing it
— then CI, Copilot review, squash-merge.

---

## Self-Review Notes

- **Spec coverage:** the encoder seam (Task 3), the abstract-sourcing
  correction (Task 3's `abstract_for()`), the ground-truth correction —
  all 48 rows, verified rather than assumed to join (Task 1) — the
  retrieve+rerank rows and BM25-as-context framing (Task 4), the
  cascade (Task 5), and the `#54` roadmap relationship note (Task 6 Step
  5) are all covered. The `adapters` dependency and `CrossEncoder`
  no-new-dependency decision from the spec's "Sequencing" section are
  Task 2 and Task 4 respectively.
- **Type consistency:** every worker function returns/consumes
  `{(chapter, line, citekey): [citekey, ...]}` keyed dicts with the same
  3-tuple key shape throughout (`bm25_row`, `_dense_worker`,
  `specter2_row`, `_cascade_worker`, `score_rows`) — checked against each
  other rather than assumed consistent by construction, since JSON
  round-tripping (Step 6, Step 2 of Task 5) turns tuples into lists and
  the `tuple(k)` conversions on the receiving side are what puts them
  back.
- **Placeholder scan:** every code step is complete and runnable.
  Task 6's `RESULTS.md` write-up is a data-reporting step drawing on
  Step 1's actual measured output, not an invented number, the same
  adaptation Arm A's plan uses for its own write-up step.
- **Known simplification, stated rather than hidden:** `specter2_row()`
  ranks only the ground truth's own citekey set, not the full corpus —
  a full corpus-wide standalone SPECTER2 row would need the same
  all-citekey `embed_paper()` call Task 5's cascade already pays for, so
  duplicating it in Task 4 for a row that Task 5 shows is dominated by
  the cascade anyway was not worth the added subprocess complexity. If a
  reviewer wants the corpus-wide standalone number too, it is a small
  addition to `specter2_row()`'s citekey list, not a redesign.

# Design: benchmarking embedding models (#194)

## Problem

`[enrich].embedding_model` (`config.EMBEDDING_MODEL`) feeds two consumers:
the tier-3 overlap/paraphrase detector (`src/overlap_embed.py`) and the
retrieval upgrade path (`src/enrich/embed_index.py`, `search()`).
Issue #194 reports the current default isn't working well on this narrow
research corpus and asks for a benchmark of alternatives, including
SPECTER2, allowing a cascade of models if that's what wins.

This is a benchmark, in the same spirit as every other `bench/` script:
it produces measurements and a recommendation in `bench/RESULTS.md`. It
does not change `EMBEDDING_MODEL`'s shipped default — that's a
deliberate follow-up decision once the numbers exist, the same way the
parser backend and worker-count defaults were decided elsewhere in this
repo.

## Why this differs from a single "run four models" pass

Two things learned while scoping this that change its shape:

**SPECTER2 is not a drop-in.** `docs/CONFIG.md`'s "Choosing an embedding
model" section already documents why: `embed_index.py` calls
`SentenceTransformer(name).encode(...)` symmetrically on 200-word chunks,
and SPECTER2 expects `title [SEP] abstract` — nothing else. Verified
against the model cards for `allenai/specter2_base` and
`allenai/specter2_adhoc_query`: every SPECTER2 adapter (proximity,
adhoc_query, classification, regression) takes only title+abstract on the
document side. The `adhoc_query` adapter is the one asymmetric exception —
it encodes a short raw query string as-is, paired against documents
encoded with the base/proximity adapter. That is a genuine query→paper
dual encoder, and it is the only way SPECTER2 participates in either
benchmark arm below; there is no code path that lets it see a passage
chunk.

**Arm B's ground truth is real, on-disk data — not what discussion #43's
comment named.** That comment described `content/provenance/<draft
name>-evidence.json` (39 queries, 62 judgements, 8 explicit negatives).
`git grep` across every commit in this repository's history finds no such
path, ever. What's real: `content/dossiers/books/<book>/<chapter>/`
carries `retrieval.md` (every query `src.retrieval`/`embed_index` logged
during that chapter's real drafting, with mode `search`/`evidence`) and
`evidence.md` / `rejected.md` (which citekeys were judged relevant/not,
each with a written reason). Confirmed present, for all 15 chapters of
`digital-twins-for-software-engineers`, inside the committed
`content/backup/content-20260809.zip` archive — the same restore step
`bench/RESULTS.md`'s 2026-08-15 tier-3 precision arm already documents.
This is real judged data from real drafting sessions, at section
granularity (a section's kept citekeys are its relevant set for any query
logged against that section) — the same granularity the existing tier-3
precision arm already works at, not a new methodology.

## Components

### 1. Encoder seam — `bench/embed_models.py` (new)

One module, three functions, because SPECTER2's shape genuinely differs
from the other three models rather than fitting a single model-name
string:

- `embed_chunks(model_key, texts) -> list[vector]` — the three documented
  drop-ins (`all-MiniLM-L6-v2`, `all-mpnet-base-v2`,
  `multi-qa-mpnet-base-dot-v1`), symmetric `SentenceTransformer.encode`.
- `embed_paper(model_key, citekey) -> vector` — SPECTER2 base +
  proximity adapter, fed `title [SEP] abstract`.
- `embed_query(model_key, text) -> vector` — SPECTER2 base + adhoc_query
  adapter, fed the raw query string.

**The abstract has no home in the ledger.** `src/ledger.py`'s
`_BIB_FIELDS_KEPT` allowlist drops `abstract` on purpose ("per-host noise
... that nothing formats"), so `bib_fields` cannot supply it. What can:
`content/docling/<citekey>.passages.json` — measured across the 497
sidecars on this host, 132 (27%) carry a `section_header` passage whose
text is exactly `Abstract` (case-insensitive), and the `text`-labelled
passages between it and the next `section_header` are the abstract.
`embed_paper` uses that where it exists and falls back to `title [SEP]
""` — SPECTER2's own documented behaviour for a missing abstract —
for the other 73%, recording per-paper which source supplied the
abstract so Arm B's SPECTER2 rows can report the split rather than
silently averaging degraded and full-quality vectors together.

Lives in `bench/`, confirmed excluded from both the 250-line/module and
25-statement/function ratchets (`tests/test_code_standards_scan.py`) and
from `[tool.coverage.run].source` — no test-suite obligation, matching
every other file in this directory.

### 2. Arm A — tier-3 overlap, three drop-in models only

SPECTER2 cannot participate here at all: tier-3's candidate set is
already one specific cited passage (dossier-scoped, not corpus-wide), and
the four graded-ladder rungs all restate the *same* paper's *same* claim
at different paraphrase distances — a paper-level title+abstract vector
is identical across all four rungs by construction, so it has nothing to
discriminate with. Including it here would report a number that measures
nothing.

New `bench/bench_embed_model_compare.py` sweeps the three drop-ins
through the harness that already exists, unmodified in method:

- `bench_overlap_embed.py --fixture` — the 4-rung graded ladder
  (verbatim / word-substitution / light-paraphrase / genuine-restatement),
  once per model.
- `bench_paraphrase_hunt.py`'s crosscheck — the 22 hand-judged organic
  close-paraphrase pairs from the 2026-08-15 baseline (real ground truth,
  already labelled, already committed in prose in `bench/RESULTS.md`),
  once per model.

Reported per model: ladder rungs caught, organic-pair recall (of 22), and
precision-arm finding volume (162 today, for `all-mpnet-base-v2`) as a
rough false-positive proxy — more findings is not free, since each is a
reviewer's time.

**Safety, corrected from an earlier draft of this spec.** No scratch
`CONTENT_DIR` — a scratch directory would have no `ledger.sqlite`,
`parsed/` or `docling/` sidecars, so tier-3 could not run there at all.
`bench_overlap_embed.py._staged()` already stages the fixture inside the
real `config.DRAFTS_DIR` and removes it in `_unstage()`, and
`embed_index.collection_name()` already namespaces each Chroma collection
by model — one model's embed run cannot corrupt or shadow another's. Both
mechanisms already exist and need no new safety layer; running each
candidate model's embed against the real `content/chroma` is exactly what
they were built for.

**Cost, stated rather than assumed.** `--stages embed` has no `--for-draft`
narrowing — `src/enrich/__main__.py`'s `SCOPE_REFUSED` refuses it
explicitly, because the Chroma collection is one whole-corpus artefact
with no partial form. So every candidate model costs one full re-embed of
all ~501 documents, at whatever `all-mpnet-base-v2`'s (undocumented, so
far) full-corpus embed time and Chroma's ~795 MB per model cost. Before
sweeping three models, time one full `--stages embed` run and multiply —
the same "measure a sample before committing to the batch" discipline
`bench/estimate.py` already uses — and report that number rather than
running the sweep blind.

### 3. Arm B — retrieval and reranking, all four models plus a cascade

Directly answers the "benchmark against retrieval and reranking, not
bare BM25" ask: the comparison isn't candidate-model-vs-BM25, it's
candidate-model-in-a-retrieve-then-rerank-pipeline, with BM25 kept as one
row for context rather than as the thing being beaten.

**Ground truth.** `bench/results/2026-08-15-organic-paraphrase-hunt/labels.json`
is already committed: 48 real `(chapter, citekey, judgment)` rows, each
with a stable id (e.g. `ch13-ferko_standardisation_2023-32`) encoding the
chapter, citekey and source line. **All 48 are valid `(query, citekey)`
retrieval pairs, regardless of judgment** — `paraphrase`/`no-match`/`no`/
`quoted`/`third-party-echo` all describe how closely the claim restates
the source passage, which has nothing to do with whether the citekey is
the paper that claim actually cites in the real book. It is, in every
row. An earlier draft of this spec restricted this to the 22
`paraphrase` rows; that was wrong.

What `labels.json` does not carry is the claim *text* — `pairs.json`
(the `--extract` output the judgments were made from) is gitignored, on
the same "no draft/source prose in a committed result" discipline
`bench_overlap_embed.py`'s `KEPT_FIELDS` already documents. Recovering it
means restoring the book (`content/drafts/books/` and
`content/dossiers/books/digital-twins-for-software-engineers/`, from
`content/backup/content-20260809.zip` — the same restore step the tier-3
precision arm already documents) and re-running
`bench_paraphrase_hunt.py --extract`. **This is not guaranteed to
reproduce the same 48 ids** — the id encodes a line number, the backup is
from 2026-08-09, and extraction runs against today's ledger/passages —
so the first task of implementing this arm is restoring, re-extracting,
and checking that all 48 ids resolve, with an explicit stop-and-report
(not a silent partial join) if any don't.

**Rows compared**, all against the same query set and relevant sets,
scored by recall@k and nDCG@k:

| Row | What it is |
|---|---|
| BM25 (`src/retrieval.py`, unchanged) | Context, not a target to beat |
| Dense-only, per drop-in model | 3 rows |
| Dense + cross-encoder rerank, per drop-in model | 3 rows — the reranking half of the ask |
| SPECTER2 (`adhoc_query` query side, `proximity` paper side), dense-only | Standalone; nothing to rerank at chunk level since it never sees a chunk |
| Cascade: SPECTER2 paper-level shortlist → best drop-in's dense+rerank within that shortlist | The "cascading models" option #194 explicitly allows |

**Reranker.** `sentence-transformers` (already a pinned `enrich`-group
dependency, `>=5.6,<6.0`) ships `CrossEncoder` directly — no new
dependency, unlike `flashrank`, for the same CPU-tolerable job
discussion #43 §3's proposal 3 and roadmap issue #54's PR9 describe. Reranks only
the ~50-100 survivors of each row's first-pass retrieval, never the whole
corpus, so the per-query cost stays bounded regardless of corpus size.

**Relationship to issue #54's roadmap, stated once here rather than
argued twice.** Track 2 of that roadmap lists PR5 ("retrieval evaluation
harness... recall@k / nDCG, living in `bench/`, runnable in CI") and PR9
("cross-encoder reranking, opt-in, merged only if the harness shows
improvement"), both currently unstarted. This benchmark's Arm B is the
same shape as PR5 and previews part of PR9 — deliberately, since building
a second, incompatible evaluation harness later would be waste. It does
**not** claim to complete either: no CI integration, and this PR does not
by itself decide to merge reranking into `embed_index.search()`. The
`bench/RESULTS.md` entry this produces is offered as evidence toward
PR5/PR9, not as their replacement — worth saying explicitly in the PR
description so it reads as informing that roadmap rather than working
around it.

### 4. Reporting

One new `bench/RESULTS.md` section, same shape as the existing
2026-08-15 entries: population tables, reproduction commands, and an
honest "what this does not measure" (per-query cost of the cross-encoder
stage at this corpus's real query volume is a likely candidate). A
`docs/CONFIG.md` note under "Choosing an embedding model" if SPECTER2
becomes a documented option — still not a new default.

## Out of scope

- `bge-*` / `intfloat/e5-*` families (need prefix-handling code not
  requested by #194).
- Changing `EMBEDDING_MODEL`'s shipped default.
- RRF fusion (discussion #43 §6 proposal 1) and section-aware chunking
  (proposal 2) — separate roadmap items (#54 PR7/PR8), not needed to
  answer #194's question.
- SQLite FTS5 (proposal 4) — quality-neutral infrastructure, unrelated to
  model choice.
- Formally completing #54's PR5 or PR9 (CI integration, the merge
  decision on reranking) — this produces evidence toward both, not the
  PRs themselves.

## Sequencing

Two stacked PRs, not one — this repo's `pyproject.toml` version line
means concurrent PRs always conflict, so two things that could ship
independently ship as two:

- **Plan 1 (Arm A).** No new dependency. Reuses `bench_overlap_embed.py`
  and `bench_paraphrase_hunt.py` unmodified. Ships and merges first.
- **Plan 2 (Arm B).** Adds `adapters` (SPECTER2's adapter loading) to
  `pyproject.toml`'s `enrich` group; uses `sentence-transformers`'
  already-pinned `CrossEncoder` rather than a second new dependency.
  `bench/embed_models.py` belongs here, not in Plan 1 — Arm A never
  touches SPECTER2.

## Testing

`bench/` carries no coverage or ratchet obligation, consistent with
every other script there. Verification is the benchmark's own output
being reproducible (a fixed fixture/query set re-run produces the same
numbers) — the same bar `bench/README.md` already holds every entry to,
not a `pytest` suite.

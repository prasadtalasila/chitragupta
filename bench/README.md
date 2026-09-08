# bench/ -- wall-clock measurement for the Docling parse path

`docs/PDF-PARSER.md` puts Docling at "~42x slower than pdftotext", measured on
5 PDFs. That is enough to choose a backend and not nearly enough to
answer "how long does a full sync of the bib corpus actually take, on
the machine in front of me, and what is the bottleneck". This directory answers that, and
keeps the answer reproducible so the parallelism work in
[PARALLELISM-PLAN.md](PARALLELISM-PLAN.md) can be checked against
measurement rather than argued from first principles.

Measured results live in [RESULTS.md](RESULTS.md); the raw per-PDF
timings behind them are in `results/<date>-<tag>/*.jsonl`.

## Running it

Needs the "enrich" Poetry group (`bash scripts/install_full_pipeline.sh
python-deps`), since it drives the real Docling stack.

`bench_drift.py` and `bench_overlap.py` are the exceptions: they measure
`chitragupta.dossier` and `chitragupta.overlap_index`/`chitragupta/review/verbatim_check.py`, all
stdlib-only, so both run under bare `python` with no corpus built and no
GPU. `bench_drift.py` generates its own throwaway corpus and never
touches `content/`; `bench_overlap.py` reads this host's real
`content/ledger.sqlite` (read-only -- see its docstring for why that is
safe here and not for `bench_drift.py`) but writes its own cache to a
throwaway directory, never the real `content/overlap/`.

`bench_collection_scope.py` is stdlib-only as well and needs no GPU, but
it is unlike every other script here in what it consumes: not a corpus
and a sample, but **two finished drafts and their dossiers** from a
two-arm run that was pre-registered before either arm was written. It
measures a drafting session after the fact rather than driving one, and
it re-runs `chitragupta.retrieval.search()` only to reconstruct what those
sessions already saw -- which is sound only while the ledger has not
moved since, so `--hashes` checks that and reports `replay_sound`.

`topic_cluster_eval.py` is stdlib-only and needs no GPU as well, and it
is the one script here with a requirement outside Python entirely:
**`node` on PATH**, because the partition it scores is the one
`assets/webapp/families.js` computes in the reader's browser. It needs a
built `content/topic_graph.json` and a gold file with `[[group]]`
records, and reports a missing `node`, artefact or gold file by name
rather than as a zero.

`bench_overlap_gate.py` and `bench_overlap_df.py` are stdlib-only too,
but unlike those two they need a **synced corpus** and a real draft to
scan: both read `content/ledger.sqlite`, `content/parsed/` and the shared
`content/overlap/` index, and neither measures wall clock at all. They
score a decision against hand-authored labels.

`bench_overlap_embed.py` is the exception to "stdlib only, no GPU", and
the only script here that is. It measures tier 3 of the overlap scan
(#134/#164), which cannot run without the `enrich` Poetry group
(`chromadb`, `sentence-transformers`, torch), a built `content/chroma/`,
the Docling passage sidecars, **and** a dossier for every draft it
scans -- so it needs a venv with that group installed, and it prints
which of those were missing rather than reporting a zero that looks like
a measurement.

```bash
# 1. Build the work lists from your own bib file (gitignored output --
#    they carry absolute PDF paths, like the bib file itself).
.venv-full/bin/python bench/make_corpus.py

# 2. Time a serial run on one GPU.
CUDA_VISIBLE_DEVICES=0 .venv-full/bin/python bench/bench_docling.py \
    --sample bench/sample16.json --out bench/results/gpu.jsonl \
    --device cuda --mode reused

# 3. Extrapolate to the whole corpus.
.venv-full/bin/python bench/estimate.py bench/results/gpu.jsonl

# 4. Measure parallel scaling (N worker processes over G GPUs).
.venv-full/bin/python bench/run_parallel.py \
    --sample bench/sample16.json --workers 8 --gpus 4 --tag w8
```

## Which tool to reach for

| Question | Tool |
|---|---|
| What does the **shipped pipeline** cost at these settings? | **`sweep_sync.py`** -- runs the real `python -m chitragupta.corpus sync` |
| How does Docling itself behave per document? | `bench_docling.py` |
| How does the workload spread across N processes and G cards? | `run_parallel.py` |
| What would the whole corpus cost, from a sample? | `estimate.py` -- **but see its docstring: it understates** |
| What does a drift sweep over every dossier cost? | **`bench_drift.py`** -- stdlib only, synthetic corpus, no GPU |
| What does `verbatim_check.py overlap`/`scan` cost, and what can `scan` see that N `overlap` calls can't? | **`bench_overlap.py`** -- stdlib only, this host's real corpus, no GPU |
| Would an `overlap_gate` (#130) block anything worth blocking, and at what span threshold? | **`bench_overlap_gate.py`** -- stdlib only, no GPU; measures **agreement with hand labels**, not cost |
| Does a gram's corpus document frequency tell field boilerplate apart from genuine reuse (#133/#134)? | **`bench_overlap_df.py`** -- stdlib only, no GPU; reuses `bench_overlap_gate.py`'s labels and adds a planted-reuse control arm |
| Does the skip-gram tier (#133) catch a synonym-swapped paraphrase, and is it precise on real prose? | **`bench_overlap_skipgram.py`** -- stdlib only, no GPU; a synthetic capability sweep needs no corpus, the precision arm needs a synced one |
| Does the embedding tier (#134/#164) catch a restatement the other two structurally cannot, and is it precise on real prose? | **`bench_overlap_embed.py`** -- the one script here that needs the `enrich` group and a built `content/chroma/`; a graded-fixture capability arm and a hand-labelled precision arm, neither a threshold sweep (this tier ranks rather than thresholds) |
| Which drop-in embedding model gives tier 3 the best recall on this corpus, at what finding-volume cost? | **`bench_embed_model_compare.py`** -- runs `bench_overlap_embed.py` and `bench_paraphrase_hunt.py` once per `docs/CONFIG.md`-documented candidate model, unmodified, via `EMBEDDING_MODEL` |
| Does BM25, a dense drop-in (alone or reranked), SPECTER2, or a SPECTER2-shortlist cascade actually find the paper a real drafting session cited? | **`bench_retrieval_compare.py`** -- needs `bench_retrieval_ground_truth.py`'s 48-pair ground truth and the `enrich` group; scores recall@5/nDCG@5 per row |
| What 48 real `(query, citekey)` pairs can retrieval quality be scored against? | `bench_retrieval_ground_truth.py` -- joins `bench_paraphrase_hunt.py`'s committed judgments back onto freshly re-extracted claim text; output is gitignored, regenerate locally |
| Does the same nine-row comparison hold against what a drafting session actually logged, not a reconstructed pair? | **`bench_retrieval_live_logs.py`** -- 96 real `search`-mode queries from the restored book's own `retrieval.md`, scored against each chapter's real `evidence.md` kept-citekey set; no book-restore-and-rejoin risk, but a coarser, chapter-level ground truth -- its nDCG@5 is not comparable in magnitude to `bench_retrieval_compare.py`'s |
| Does the same nine-row comparison hold with a ground truth no retrieval method built (the two above both score against citekeys BM25 itself surfaced)? | **`bench_retrieval_keyword_selfretrieval.py`** -- 256 real bib entries' own author-assigned `keywords`, query = the keywords, correct answer = the entry itself; needs no restored book, only `bibliography.bib` and the synced ledger |
| Does a topic set *reproduce*, or does it look settled by luck? | **`bench_topic_depth.py --repeats N`** -- adjusted Rand index between a fit and refits on 90% resamples. The values hardcoded until 6.9.0 score **0.14** |
| How many topics does this corpus divide into, at each clustering setting -- and what does the coarse setting cost? | **`bench_topic_depth.py`** -- needs the `enrich` group and a synced corpus; reuses `content/topic_embed_cache.json`, so a warm cache makes it minutes. The **outlier** column is the one to read: it *falls* as topics get finer |
| Is the topic app's MCL **inflation** default of 2.0 the right one, and what does moving it cost? | **`topic_cluster_eval.py`** -- sweeps the slider's own range and scores each partition, per edge family, against `[[group]]` records in `content/topic_gold.toml`. Needs `node` (it drives the shipped `assets/webapp/families.js` rather than re-implementing MCL) and a built `content/topic_graph.json`; no GPU, no synced ledger. The two families do not agree on a best inflation, which is the per-family design talking |
| Which mechanism can honestly say a paper belongs to more than one *emergent* topic? | **`bench_topic_membership.py`** -- scores five candidates on shape **and on agreement with the clustering they claim to describe**, which is what disqualifies three of them |
| What does scoping a draft's retrieval to a curated Zotero collection (`--collection`, #195) actually buy? | **`bench_collection_scope.py`** -- two arms of the same chapter, whole corpus vs one shelf, from the same pre-registered queries; replays each dossier's own logged queries to reconstruct what each arm surfaced. Stdlib only, no GPU, but it scores a *drafting run*, so it needs two real drafts and their dossiers to already exist |
| Does a cross-encoder rerank help, and does it matter whether it runs before or after the per-citekey cap (#380)? | **`bench_rerank_position.py`** -- needs the `enrich` group and a built `content/chroma/`; reuses `bench_retrieval_keyword_selfretrieval.py`'s 256 pairs and `bench_retrieval_compare.py`'s scoring, and measures at the **shipped** shape (chunks, cap 3, pool 20) rather than the citekey-collapsed one those rows use. Reports `distinct@5`, which is the metric #380's own motivating claim is about |
| What does cross-encoding the over-fetched passages *cost*, per `search()` call? | **`bench_rerank_cost.py`** -- needs the `enrich` group and a built `content/chroma/`; times the rerank stage against the shipped `embed_index.search()` measured in the same process, across model x device x pool depth. Reports a **slowdown ratio**, not a duration, because that is what decides affordability |
| Would a figure-similarity tier (#659) catch a draft figure redrawn from a source's, and can it tell that apart from same-field organic noise? | **`bench_figure_similarity.py`** -- needs the `enrich` group's `docling_images` crops, `sentence-transformers`/`transformers`/`torch`, and a working `pdflatex` + `pypdfium2`; measures an identity control, a cross-paper floor, recall on four graded planted TikZ fixtures against two encoders, and cost. **2026-09-04: a narrowly-scoped ship, SigLIP only, catching a label-preserving redraw and nothing past it** -- see `RESULTS.md` |
| What does surviving a dead parse worker cost, and does the narrowing pool terminate? | **`bench_pool_rebuild.py`** (#610 B3) -- SIGKILLs a real pool worker mid-parse and hands a FIFO to the stall watchdog, both in throwaway content directories. Reports a wall-clock **ratio**, the documents lost, and the pool widths as it narrowed. **Did not complete on this host** -- see `RESULTS.md`'s B3 section |
| Does the *converged* topic set reproduce, or only the emergent clustering underneath it? | **`bench_topic_converged_stability.py`** (#610 B4) -- bootstrap ARI over both, from one run of the real stages per resample. Read the **multi-membership share** first: the converged arm's partition is constructed, and the number means what it looks like only where few documents had a choice |
| How many edges does the topic graph have at other thresholds, and does the edge set survive a resample? | **`bench_topic_graph_shape.py`** (#610 B7) -- a p-value x neighbours grid, edge-set Jaccard under document bootstrap, and the two graph metrics (average degree, average clustering coefficient) the stage deliberately does not publish |
| What does a whole-file rewrite cost against a section-scoped edit, and what does the dispatch pointer really save? | **`bench_prompt_economics.py`** (#610 B8) -- characters at the documented four-per-token conversion, over every draft with a dossier. Classifies each section's zero rather than summing it, which is what separates "nothing to paste" from "nothing transcribed" |
| The instrument for rating claim support: stratified, blinded, three raters | **`bench_claim_support_labelling.py`** (#610 B9) -- builds the sheet and the key and **computes no statistic** until three humans have filled it in. `--score` then reports Fleiss' kappa, pairwise Cohen's kappa, Spearman rho and the separation medians |
| What do all **ten** review aids cost now, `union` included? | **`bench_review_cost.py`** (#610 B11) -- the same five drafts docs/PERFORMANCE.md's 2026-08-27 table used, re-timed through the real CLI, median of `--repeats`. A refused aid reports its exit status, never a fast time |
| Does the shipped keyword pipeline still reach the corpus it reached on the last snapshot? | **`bench_keyword_pipeline.py`** (#610 B14) -- the 2026-09-03e entry's four arms as one command, coverage read off the stage's own `topic_seeds.json`. Regenerates `content/keywords.toml` per arm rather than scoring whatever is on disk |

**Prefer a real measurement over an extrapolation whenever you can afford
one.** A per-page extrapolation from a 16-PDF sample understated a
measured full-corpus serial run by **41%**, and that figure was quoted as
fact across the documentation for two releases. `estimate.py` now leads
with the per-doc model (9% low) and says so.

```bash
# The whole scaling curve, from an empty ledger each time.
.venv-full/bin/python bench/sweep_sync.py --workers 1,4,8,12 --gpus 4 --tag scaling

# GPU scaling at a fixed worker count; OCR on vs off.
.venv-full/bin/python bench/sweep_sync.py --workers 12 --gpus 1,2,4 --tag gpus
.venv-full/bin/python bench/sweep_sync.py --workers 12,24 --ocr on,off --tag ocr

# See the plan without running anything (each run parses the whole corpus).
.venv-full/bin/python bench/sweep_sync.py --workers 1,12 --tag plan --dry-run
```

`sweep_sync.py` reports the **resolved** worker count, not the requested
one, and warns when they differ. That matters: `worker_ceiling()` clamps
to `allowed_cpus // 4`, so asking for 32 on a 48-CPU machine silently
gives you 12 — a trap that hid a measured 1.41x for a whole release.

## What this harness does *not* measure

`run_parallel.py` launches N **independent** worker processes, each
handed a shard and a GPU via `CUDA_VISIBLE_DEVICES`. That predates
`[parser].workers` and is deliberately a different thing from the pool
`chitragupta/sync.py` actually uses -- no shared counter, no pool initialiser, no
`start_method`. It answers "how does this workload scale across
processes and cards", not "what does the shipped pool cost".

So every **pool-level** figure in `RESULTS.md` -- worker counts,
per-worker GPU assignment, and `[parser].start_method` -- was measured
with the real `python -m chitragupta.corpus sync`, not with this harness. `sweep_sync.py`
now automates that; the equivalent by hand is:

```bash
# A/B two settings over a subset of the real corpus, three runs each.
# A fresh CONTENT_DIR per run is the point: every document must actually
# need a parse, or you are timing the ledger's skip logic instead.
for method in spawn forkserver; do
  for rep in 1 2 3; do
    rm -rf /tmp/bench-content && mkdir -p /tmp/bench-content
    /usr/bin/time -f "$method rep$rep %e s" \
      env CONTENT_DIR=/tmp/bench-content BIB_FILE=/path/to/subset.bib \
          PARSER=docling PARSER_OCR=false \
          PARSER_WORKERS=4 PARSER_START_METHOD=$method \
      .venv-full/bin/python -m chitragupta.corpus sync > /dev/null
  done
done
```

Take the **median of three**: run-to-run spread on a quiet machine was
0.3-1.0s, which is the same order as some of the effects being measured.

Build `subset.bib` by filtering your real bib file down to a
rank-stratified sample of entries -- the same reasoning as
`make_corpus.py`'s sampling. It must live in the same directory as the
PDFs it references, since `file =` paths resolve relative to the bib
file. Sampling the *smallest* N documents instead would make every run
startup-dominated by construction, which flatters exactly the change
being tested.

## What each file is

| File | Purpose |
|---|---|
| `make_corpus.py` | Resolves PDFs from `papers/bibliography.bib`, counts pages, draws rank-stratified samples |
| `bench_docling.py` | Times Docling per PDF; switches device (`cuda`/`cpu`) and converter reuse (`fresh`/`reused`) |
| `estimate.py` | Extrapolates a sample's timings to the full corpus, two ways |
| `run_parallel.py` | Runs N worker processes over G GPUs, reports aggregate throughput |
| `sweep_sync.py` | Sweeps the **real** `chitragupta.corpus sync` over worker/GPU/OCR settings -- the pool-level numbers |
| `repro_check.py` | Asks whether two runs *agree*, not what they cost: parses one subset under two GPU counts and compares text, passage spans and passage texts |
| `bench_overlap_gate.py` | Sweeps #130's gate predicate over a real book's `scan` findings and scores each candidate threshold (**T**, a run length in words) against hand-authored labels -- **tp**/**fp** being a blocked finding that is, or is not, genuine uncredited reuse; also measures what References masking is worth |
| `bench_overlap_df.py` | Asks whether the **corpus document frequency** of a run's 8-grams -- distinct citekeys in `overlap_index.postings_for_gram`, so a projection of the #110 index rather than a new artefact -- tells a field's stock phrasing apart from genuine reuse. Two arms, because the book supplies only false positives: the labelled book, and the planted-reuse fixture as the one true positive |
| `bench_overlap_skipgram.py` | Sweeps a synthetic every-Nth-word paraphrase against the skip-gram tier (#133) at a range of strides, no corpus needed; with `--drafts`, also isolates real `tier == "skip-gram"` findings and scores them against hand labels the same way `bench_overlap_gate.py` does |
| `bench_overlap_embed.py` | Runs one real corpus claim at four gradings -- verbatim, substituted in place, lightly edited, genuinely restated, each its own section of `fixtures/graded-paraphrase-of-singh-offload-2022.md` -- through the whole scan and reports which tier caught each; with `--drafts`, also isolates real `tier == "embedding"` findings and scores them against hand labels. Not a threshold sweep: tier 3 can never gate and does not threshold |
| `bench_embed_model_compare.py` | Orchestrates `bench_overlap_embed.py` and `bench_paraphrase_hunt.py --crosscheck` once per candidate model in `docs/CONFIG.md`'s "Choosing an embedding model", via `EMBEDDING_MODEL` -- neither script is modified, only invoked once per model |
| `bench_retrieval_ground_truth.py` | Recovers 48 real `(query, citekey)` pairs for Arm B (#194) by joining `bench_paraphrase_hunt.py`'s committed judgments back onto claim text re-extracted from the restored book; its own `ground_truth.json` output is gitignored -- carries claim text, same discipline as `pairs.json` |
| `bench_retrieval_compare.py` | Scores BM25, each of three dense drop-ins (alone and cross-encoder-reranked), SPECTER2 standalone, and a SPECTER2-shortlist cascade against the ground truth above, by recall@5/nDCG@5 -- each dense model and the cascade run in their own `.venv-full` subprocess since `EMBEDDING_MODEL` is fixed at `chitragupta/config.py` import time |
| `bench_retrieval_live_logs.py` | Same nine rows as `bench_retrieval_compare.py` (imports its scoring functions rather than reimplementing them), against a different ground truth: 96 real `search`-mode queries logged live in the restored book's own `retrieval.md`, each scored against its whole chapter's real kept-citekey set from `evidence.md` -- coarser than a single-citekey pair, so its nDCG@5 has a different (harsher) ideal denominator and is not comparable in magnitude to `bench_retrieval_compare.py`'s |
| `bench_retrieval_keyword_selfretrieval.py` | Same nine rows again, against a ground truth built by neither of the two scripts above: 256 real bib entries' own `keywords` field as the query, that entry's own citekey as the correct answer -- independent of what any retrieval method surfaced during drafting, since no drafting session is involved at all. Also the one script here whose `specter2_row()` ranks over the whole ledger rather than the ground truth's own citekeys, to keep every row's pool the same size |
| `bench_collection_scope.py` | What a `--collection` filter costs and buys across a real two-arm drafting run: retrieval payload from each dossier's `retrieval.md`, surfaced/selected/rejected by replaying each arm's own logged queries at its own `--k` (with and without the filter), index cost by md5 across three checkpoints, tokens windowed from the session transcript by those same checkpoints, and both arms' verbatim scans. Parameterised (`--topic`/`--arm-f`/`--arm-c`/`--collection`) so one script serves every run of the design -- the first run's copy hard-coded its paths and was never committed |
| `bench_topic_depth.py` | Sweeps `n_neighbors`/`n_components`/`min_cluster_size`/`min_samples` over the real corpus and reports topic count, outlier share, median topic size and topics-per-document. The measurement behind `[enrich].topic_min_cluster_size` and behind the finding that its hardcoded predecessor was a ceiling rather than a default |
| `bench_topic_membership.py` | Compares `approximate_distribution`, centroid cosine in two spaces, a Gaussian mixture and HDBSCAN's own soft clustering. Reports **agreement** -- whether a document's assigned topic appears in the memberships the mechanism gives it -- because a membership set that disagrees with the assignment printed beside it is describing a different clustering |
| `extract_keywords.py` | Writes `content/keywords.toml`: the corpus's own top TF-IDF terms, ranked by summed weight across every parsed document, with `content/topics.toml`'s phrases excluded so it never just echoes the hand-written list back |
| `bench_keyword_seed_topics.py` | Runs `topic_seeding.assign()` once per phrase set -- `content/topics.toml` alone, `content/keywords.toml` alone, both combined -- and reports coverage, phrase redundancy (mean pairwise Jaccard of match sets) and how much of the corpus a keyword phrase alone reaches that no hand-written phrase does |
| `embed_models.py` | The SPECTER2 encoder seam: `embed_paper()` (title+abstract, proximity adapter, disk-cached per citekey) and `embed_query()` (adhoc_query adapter) -- SPECTER2 never sees a passage chunk, unlike the three drop-in models |
| `bench_figure_similarity.py` | Whether a figure-similarity review tier (#659) could catch a draft figure redrawn from a source's: identity control, cross-paper false-positive floor (masked by paper *and* by exact byte content -- a shared book chapter or a mis-extracted publisher logo is not "independent similarity"), recall on a graded planted TikZ redraw against CLIP and SigLIP, an 8x8 average-hash prescreen, and per-crop cost. Not a threshold sweep -- this tier ranks rather than thresholds, same as tier 3 of the overlap scan |
| `topic_cluster_eval.py` | Scores the app's MCL partition against hand-written `[[group]]` records, pairwise over the gold-covered topics only, once per family per inflation across the slider's own range. The one script here that shells out to `node`: the partition scored has to be the one `assets/webapp/families.js` shows the reader, and a Python MCL beside it would be a second version of the same numbers, free to disagree |
| `results/` | Committed raw timings -- the evidence behind `RESULTS.md` |

`repro_check.py` is the odd one out here, and deliberately so: every other
script measures **cost**, it measures **agreement**. That is why it keeps
each run's output instead of discarding it, pins the CPU affinity mask
with `taskset` so `worker_ceiling()` cannot drift between arms, pins
every parse-affecting `[parser].*` setting rather than inheriting it from
the host's `config.toml`, and runs every configuration more than once --
the same-configuration pair is the control that says whether a difference
belongs to the varied axis or to the parser simply being unstable.

**Use `--repeat 5`, not the default 2, for anything you intend to quote.**
`--repeat 2` gives **one** same-configuration pair per GPU count, and one
pair is a single draw. Eight pairs at one fixed configuration have
returned 0, 1, 3, 4, 4, 4, 5 and 6 differing documents out of 300 -- so a
single pair establishes only that a difference *can* occur, and two
single pairs cannot be compared to each other. #695 reported a five-fold
rise in the rate that was exactly that comparison; `RESULTS.md`'s
"2026-09-08b (B2d)" section has the arithmetic. Sample size does not
help here: 300 documents per arm and one pair still yields one number.

Two settings it does **not** pin, and inherits and records instead:
`PARSER_DOCUMENT_TIMEOUT` and `PARSER_START_METHOD`. Neither changes what
is extracted, and neither has a defensible literal to pin to.
`unpinned_parser_settings()` refuses to run against a `[parser].*`
setting the script has never classified, so a new one stops the matrix on
its first invocation rather than silently making a record incomparable --
which is what happened to the 2026-09-07 record when `[parser].formulas`
arrived.

## `self_check()`: what a script here owes a number it publishes

**A script in `bench/` that publishes a number runs a `self_check()` from
its own `main()`, before it does any real work.** `repro_check.py`, `bench_drift.py`, `sweep_sync.py`,
`bench_embed_model_compare.py`, `bench_overlap_df.py`,
`bench_overlap_embed.py`, `bench_overlap_gate.py`,
`bench_overlap_skipgram.py`, `bench_paraphrase_hunt.py`,
`bench_claim_support.py`,
`bench_retrieval_compare.py`, `bench_retrieval_ground_truth.py`,
`bench_retrieval_keyword_selfretrieval.py`, `bench_retrieval_live_logs.py`,
`bench_retrieval_fusion.py`,
`bench_rerank_position.py`, `bench_rerank_cost.py`, `embed_models.py`,
`bench_collection_scope.py`, `bench_overlap.py`,
`bench_topic_depth.py`, `bench_topic_membership.py`,
`topic_discovery_eval.py`, `estimate.py`,
`run_parallel.py`, `extract_keywords.py` and
`bench_keyword_seed_topics.py`, `bench_figure_similarity.py`,
`topic_cluster_eval.py`, `bench_topic_graph_shape.py`,
`bench_pool_rebuild.py`, `bench_review_cost.py`,
`bench_prompt_economics.py`, `bench_topic_converged_stability.py`,
`bench_keyword_pipeline.py` and `bench_claim_support_labelling.py` each have
one -- 36 of the 38 scripts here. The
exceptions are `bench_docling.py` and `make_corpus.py`: both publish
only real, directly-observed measurements (a per-PDF timing; a corpus or
sample size) with no comparison or aggregation logic of their own that
could silently read a real difference as none. `make_corpus.py`'s
`rank_sample()` does dedup its evenly-spaced indices, but a bad dedup
shows up as a wrong number in `main()`'s own
`sample16 : N PDFs` line, not as a zero hidden behind a comparison --
the failure this convention exists to catch.

The reason is the first line of every such function: `bench/` sits
outside **all four** of the things that hold the rest of this tree --
C1/C2, coverage (`source = ["chitragupta", "scripts", ".claude/hooks"]`
in `pyproject.toml`), the release archive, and
the linter. Nothing in the test suite will ever catch a regression
in these files, so the check runs on every invocation instead. It costs
microseconds.

Each of those four is a decision, reaffirmed rather than scheduled
(#356):

- **C1/C2** -- stated and defended in
  [CODE-STANDARDS.md](../docs/CODE-STANDARDS.md#-the-binary-rules):
  one-shot analysis code whose `main()` reads top to bottom on purpose.
- **Coverage** -- `bench/` is never imported by the shipped pipeline;
  `self_check()` is the substitute regression guard this section
  describes, run on every invocation rather than once in CI.
- **The release archive** -- `bench/` is dev tooling that measures this
  checkout, not something a `pip install`ed or unzipped-release consumer
  runs (`scripts/release.py`'s `EXCLUDE_TOP_LEVEL`).
- **The linter** -- measured directly rather than assumed free: `pylint
  --rcfile=.pylintrc bench` (run alongside `chitragupta scripts
  .claude/hooks`, so imports resolve) reports **78 findings** across the
  22 files, 2026-08-23. 23 are `wrong-import-position` -- the deliberate
  `sys.path.insert(0, ...)` every script here uses to reach `chitragupta`
  from outside the package, the same pattern already carved out for
  `__init__.py` late imports elsewhere in this project. The rest are real
  mechanical residue (`use-maxsplit-arg`, `line-too-long`,
  `unspecified-encoding`, `cell-var-from-loop`, and others), the same
  categories `chitragupta/`'s own pylint adoption paid down before
  enabling the check -- see `docs/TECHNICAL-DEBT.md`'s ruff/pylint
  sections for that sequence. Enabling `bench/` here would mean landing
  that sequence -- baseline, category decisions, mechanical fixes --
  inside a PR about self-checks, which the "several small, reviewable
  PRs" rule argues against. Reopen this as its own PR if someone wants to
  spend one on it.

What it asserts is narrow and specific, and it is not "the script works":

> **Fabricate a difference this script's own comparison or aggregation
> logic is supposed to see, and assert that it sees it.**

Because the failure worth guarding against is never a crash. It is the
zero that reads like a result: a detector that compares nothing prints
what a perfectly stable run prints, a regex that stopped matching reports
`0 failed` exactly as a clean run does, and a sweep whose narrowing
silently missed prints a flat curve that reads as a finding rather than
as an absence of one. Each of those has happened here, and the third was
found by writing this convention down --
`bench_drift.py`'s subset override had reached nothing since the
`chitragupta/dossier/` split, so its three dossier counts were three
measurements of the same whole set.

Copy the shape, not the assertions: `repro_check.py`'s nine are about
Docling sidecars and belong to it alone. `bench_drift.py` fabricates a
clock and a dossier list, `sweep_sync.py` fabricates the output of a
failed `sync`. And say in the docstring what the check *cannot* see --
`sweep_sync.py`'s fixtures cannot notice `sync` rewording the lines they
are copied from, and saying so is the difference between a guard and a
false assurance.

## The two switches that matter

**`--mode fresh` vs `--mode reused`.** `DocumentConverter.initialized_pipelines`
is an *instance* attribute, so a converter built per PDF re-initialises
the layout/table/OCR models every time. `fresh` reproduces that; `reused`
builds one converter for the whole run. This is the difference the
converter-reuse work was about.

**`--device cuda` vs `--device cpu`.** Docling's `AcceleratorDevice.AUTO`
resolves to `cuda:0` whenever a GPU is present, so the default is already
`cuda` -- `cpu` is here to measure how much that is worth, which on this
corpus turned out to be less than anyone would guess.

## Reading the estimate

`estimate.py` reports two extrapolations because they disagree:

- **per-page** assumes cost is proportional to page count.
- **per-doc** fits `seconds ~= a + b * pages` and sums the prediction over
  every corpus document. The intercept `a` is real -- a 1-page PDF does
  not cost a seventeenth of a 17-page one -- so this is the more honest
  model for a corpus whose median document is 16 pages.

Treat the pair as a band, not a point estimate. Per-PDF cost varied 0.11
to 1.52 s/page across the sample, so a single number would be false
precision.

## Generated, not committed

`bench/corpus.json`, `bench/sample*.json` and `bench/par_*/` are
gitignored: they contain absolute paths into `papers/`, which is per-host
data. Regenerate them with `make_corpus.py`. The `results/*.jsonl`
timings *are* committed -- they carry citekeys and durations, no paths,
and they are the evidence the plan rests on.

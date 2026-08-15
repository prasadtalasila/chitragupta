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
`src.dossier` and `src.overlap_index`/`src/review/verbatim_check.py`, all
stdlib-only, so both run under bare `python` with no corpus built and no
GPU. `bench_drift.py` generates its own throwaway corpus and never
touches `content/`; `bench_overlap.py` reads this host's real
`content/ledger.sqlite` (read-only -- see its docstring for why that is
safe here and not for `bench_drift.py`) but writes its own cache to a
throwaway directory, never the real `content/overlap/`.

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
| What does the **shipped pipeline** cost at these settings? | **`sweep_sync.py`** -- runs the real `python -m src.corpus sync` |
| How does Docling itself behave per document? | `bench_docling.py` |
| How does the workload spread across N processes and G cards? | `run_parallel.py` |
| What would the whole corpus cost, from a sample? | `estimate.py` -- **but see its docstring: it understates** |
| What does a drift sweep over every dossier cost? | **`bench_drift.py`** -- stdlib only, synthetic corpus, no GPU |
| What does `verbatim_check.py overlap`/`scan` cost, and what can `scan` see that N `overlap` calls can't? | **`bench_overlap.py`** -- stdlib only, this host's real corpus, no GPU |
| Would an `overlap_gate` (#130) block anything worth blocking, and at what span threshold? | **`bench_overlap_gate.py`** -- stdlib only, no GPU; measures **agreement with hand labels**, not cost |
| Does a gram's corpus document frequency tell field boilerplate apart from genuine reuse (#133/#134)? | **`bench_overlap_df.py`** -- stdlib only, no GPU; reuses `bench_overlap_gate.py`'s labels and adds a planted-reuse control arm |
| Does the skip-gram tier (#133) catch a synonym-swapped paraphrase, and is it precise on real prose? | **`bench_overlap_skipgram.py`** -- stdlib only, no GPU; a synthetic capability sweep needs no corpus, the precision arm needs a synced one |
| Does the embedding tier (#134/#164) catch a restatement the other two structurally cannot, and is it precise on real prose? | **`bench_overlap_embed.py`** -- the one script here that needs the `enrich` group and a built `content/chroma/`; a graded-fixture capability arm and a hand-labelled precision arm, neither a threshold sweep (this tier ranks rather than thresholds) |

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
`src/sync.py` actually uses -- no shared counter, no pool initialiser, no
`start_method`. It answers "how does this workload scale across
processes and cards", not "what does the shipped pool cost".

So every **pool-level** figure in `RESULTS.md` -- worker counts,
per-worker GPU assignment, and `[parser].start_method` -- was measured
with the real `python -m src.corpus sync`, not with this harness. `sweep_sync.py`
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
      .venv-full/bin/python -m src.corpus sync > /dev/null
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
| `sweep_sync.py` | Sweeps the **real** `src.corpus sync` over worker/GPU/OCR settings -- the pool-level numbers |
| `repro_check.py` | Asks whether two runs *agree*, not what they cost: parses one subset under two GPU counts and compares text, passage spans and passage texts |
| `bench_overlap_gate.py` | Sweeps #130's gate predicate over a real book's `scan` findings and scores each candidate threshold (**T**, a run length in words) against hand-authored labels -- **tp**/**fp** being a blocked finding that is, or is not, genuine uncredited reuse; also measures what References masking is worth |
| `bench_overlap_df.py` | Asks whether the **corpus document frequency** of a run's 8-grams -- distinct citekeys in `overlap_index.postings_for_gram`, so a projection of the #110 index rather than a new artefact -- tells a field's stock phrasing apart from genuine reuse. Two arms, because the book supplies only false positives: the labelled book, and the planted-reuse fixture as the one true positive |
| `bench_overlap_skipgram.py` | Sweeps a synthetic every-Nth-word paraphrase against the skip-gram tier (#133) at a range of strides, no corpus needed; with `--drafts`, also isolates real `tier == "skip-gram"` findings and scores them against hand labels the same way `bench_overlap_gate.py` does |
| `bench_overlap_embed.py` | Runs one real corpus claim at four gradings -- verbatim, substituted in place, lightly edited, genuinely restated, each its own section of `fixtures/graded-paraphrase-of-singh-offload-2022.md` -- through the whole scan and reports which tier caught each; with `--drafts`, also isolates real `tier == "embedding"` findings and scores them against hand labels. Not a threshold sweep: tier 3 can never gate and does not threshold |
| `results/` | Committed raw timings -- the evidence behind `RESULTS.md` |

`repro_check.py` is the odd one out here, and deliberately so: every other
script measures **cost**, it measures **agreement**. That is why it keeps
each run's output instead of discarding it, pins the CPU affinity mask
with `taskset` so `worker_ceiling()` cannot drift between arms, and runs
every configuration twice -- the same-configuration pair is the control
that says whether a difference belongs to the varied axis or to the
parser simply being unstable. It also self-checks its own detector on
every invocation, because `bench/` sits outside CI's coverage targets and
a comparison that silently compares nothing looks exactly like a clean
result.

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

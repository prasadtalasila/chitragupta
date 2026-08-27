# Measured: what a full Docling parse of the bib corpus costs

A dated record, oldest first. Host throughout: 4x NVIDIA A40 46GB, driver
555.42.02, CUDA 12.5, 96 logical CPUs of which this container is allowed
48 (`Cpus_allowed_list: 0-23,48-71`). docling 2.117.0, torch 2.7.1+cu126.

Raw per-run data is in `results/<date>-<tag>/`. Reproduce with the
commands in [README.md](README.md).

## Which sections are current

**Read this before quoting a number.** Nothing here is deleted when a
later run overturns it -- being able to see which conclusions were wrong,
and what corrected them, is the point of the directory (see
[PARALLELISM-PLAN.md](PARALLELISM-PLAN.md)'s method). But that only works
if it is obvious which is which, so:

| Section | Standing | |
|---|---|---|
| 2026-08-02 baseline (["Wall clock"](#wall-clock), ["The GPU is not the bottleneck"](#the-gpu-is-not-the-bottleneck)) | **Superseded** | Extrapolated from a 16-PDF sample; understated the serial baseline by 41% |
| [2026-08-02: OCR costs more than the GPU saves](#2026-08-02-ocr-costs-more-than-the-gpu-saves) | **Partly superseded** | The 2.46x is a *serial sample* figure. Measured: 2.08x serial, up to 4.79x parallel. Its qualitative finding -- what OCR recovers, and in how few documents -- still stands and is not measured anywhere else |
| [2026-08-02: the converter rebuild](#2026-08-02-the-converter-rebuild), [spreading workers across the four A40s](#2026-08-02-spreading-workers-across-the-four-a40s) | Current | Superseded only in absolute wall clock, not in ratio |
| [Per-worker startup](#per-worker-startup-where-the-10s-goes-and-how-much-of-it-is-shareable) | Current | |
| [2026-08-04: the full-corpus sweep](#2026-08-04-the-full-corpus-sweep) | **Current** | The first whole-corpus measurement; corrected everything above it |
| [2026-08-04b: repeats](#2026-08-04b-repeats-and-where-the-time-goes) | **Current** | Overturned the 32-vs-48 "knee" from the single-run sweep |
| [2026-08-07: does the quotable passage survive a re-parse?](#2026-08-07-does-the-quotable-passage-survive-a-re-parse) | **Current** | Corrected "same-configuration runs reproduce exactly", which had been asserted in three documents |
| [2026-08-08: what a drift sweep costs](#2026-08-08-what-a-drift-sweep-costs) | **Current** | The first measurement of `dossier status --all`, on the real corpus |
| [2026-08-10: `overlap` and `scan` -- what the fingerprint index (#110) and the whole-draft scan (#111) actually buy](#2026-08-10-overlap-and-scan----what-the-fingerprint-index-110-and-the-whole-draft-scan-111-actually-buy) | **Partly superseded** | Its cold/warm figures still stand -- re-measured at 26.8s after #131 bumped the tokenizer version, which was expected to make them stale and did not. Its claim that `scan`'s findings are the input a gating decision would be tuned against is what the 2026-08-13 section actually tests |
| [2026-08-13: what an `overlap_gate` would block, and how much of it would be wrong (#130)](#2026-08-13-what-an-overlap_gate-would-block-and-how-much-of-it-would-be-wrong-130) | **Current** | The first false-positive measurement of the gate #130 proposes, over a real 15-chapter book. Found References masking broken for book-numbered headings (72x the gateable population) and no threshold with a true positive at any width |
| [2026-08-13b: does a gram's corpus document frequency separate boilerplate from reuse?](#2026-08-13b-does-a-grams-corpus-document-frequency-separate-boilerplate-from-reuse) | **Current** | Follows the section above, which found the discriminating feature and quantified it only partly. Measured at gram rather than finding granularity it explains 12 of 14, against that section's 8 |
| [2026-08-13: does the skip-gram tier (#133) catch what the exact tier misses?](#2026-08-13-does-the-skip-gram-tier-133-catch-what-the-exact-tier-misses) | **Current, capability arm only** | Confirms the every-Nth-word design works synthetically. Its "precision arm: not run" half is superseded by the section below, which ran it |
| [2026-08-14: tier 2's first real precision number, and the two bugs that had to be fixed to get it (#180)](#2026-08-14-tier-2s-first-real-precision-number-and-the-two-bugs-that-had-to-be-fixed-to-get-it-180) | **Current** | The precision arm the section above could not run. Two mechanical bugs accounted for 163 of 190 raw findings; on the 27 that survive, precision is 2/27 and both true positives are passages the exact tier already reports |
| [2026-08-15: does the embedding tier (#134/#164) catch what neither deterministic tier can?](#2026-08-15-does-the-embedding-tier-134164-catch-what-neither-deterministic-tier-can) | **Partly superseded** | Tier 3's first measurement. Establishes that a *sentence* is the wrong comparison unit in this corpus -- the one hand-verified organic pair scores 0.55 as a sentence against 0.59-0.61 of same-paper noise, and 0.71 windowed -- and that both organic pairs #134 names are reported. Its capability arm is a graded fixture and its two organic pairs are the ones #134 names in prose; its precision arm reports a 162-finding population and **no precision number** -- none of it is labelled. Its severity-mix figure (151 `long`/7 `short`/4 `quoted`) was flagged as stale after #189 changed how `quoted` is computed; the [2026-08-16 section](#2026-08-16-which-drop-in-embedding-model-does-tier-3-overlap-detection-see-the-most-with) re-ran the same model and corpus and found 146/7/9 -- that is the current mix |
| [2026-08-15b: the recall question, asked by reading](#2026-08-15b-the-recall-question-asked-by-reading----how-much-organic-paraphrase-does-each-tier-see) | **Current** | The only recall measurement here, and the one #134's plan assumed existed: 48 claims judged by reading each against the source it cites. 22 are close paraphrase; tier 3 is the only tier firing on 8 of them, against skip-gram's 2-of-59 measured the same way before tier 3 existed. Re-derives, by a committed script, what the 2026-08-14 session produced and did not commit |
| [2026-08-16: which drop-in embedding model does tier-3 overlap detection see the most with?](#2026-08-16-which-drop-in-embedding-model-does-tier-3-overlap-detection-see-the-most-with) | **Current** | The first cross-model comparison. All three candidates catch all four graded-ladder rungs; organic recall over the same 22 close-paraphrase pairs ranges 11/22-13/22, with `all-mpnet-base-v2` (the shipped `config.toml.example` default) ahead by 2 pairs at a middling finding-volume cost. Not a precision measurement -- see its own "what this does not measure" |
| [2026-08-16: retrieval and reranking, against real drafting judgments](#2026-08-16-retrieval-and-reranking-against-real-drafting-judgments) | **Current** | Arm B of #194. A different question than the section above: not "which embedding model does tier 3 agree with most", but "which retrieval configuration finds the citekey a real drafting session cited", scored against 48 real (query, citekey) pairs. **BM25 outright wins** every row here, dense+rerank and the SPECTER2 cascade included |
| [2026-08-16: retrieval quality against what a drafting session actually logged](#2026-08-16-retrieval-quality-against-what-a-drafting-session-actually-logged) | **Current** | Same nine rows as the section above, a different ground truth: 96 real `search`-mode queries logged live by `retrieval.md` across all 15 chapters, scored against each chapter's real kept-citekey set rather than a reconstructed single-citekey pair. **BM25 still wins on nDCG@5**, but SPECTER2 standalone has the best recall@5 here, and reranking is not uniformly helpful -- it actively hurts `all-MiniLM-L6-v2`. Its nDCG numbers are **not comparable in magnitude** to the section above's -- see the section's own methodological note before quoting one against the other |
| [2026-08-16: retrieval quality with a ground truth no retrieval method built](#2026-08-16-retrieval-quality-with-a-ground-truth-no-retrieval-method-built) | **Current** | A fairness correction, not a third opinion: the two sections above both score against citekeys a session *kept after BM25 surfaced them* -- a paper dense retrieval found that BM25 never showed a human has no way to score as a hit. This section's ground truth comes from neither: 256 real bib entries' own author-assigned keywords, query = the keywords, correct answer = that entry itself. **BM25 still wins outright** (recall@5 0.80, nDCG@5 0.73, the highest of any row in any of these three sections) -- the strongest evidence yet that the win is real, not an artifact of who built the test. But the SPECTER2 cascade, the worst row in both sections above, is here the **second-best row overall**, beating every standalone dense/rerank row -- read as a property of this section's self-retrieval task favouring paper-level similarity, not a bug fixed in the cascade's own code, which is unchanged from the sections above |
| [2026-08-26: where a cross-encoder rerank sits, relative to the per-citekey cap](#2026-08-26-where-a-cross-encoder-rerank-sits-relative-to-the-per-citekey-cap) | **Current** | Planning input for #380 (roadmap B4), at the shipped pipeline's own shape -- chunks, cap 3, pool 20 -- which none of the three sections above measure (they collapse to one chunk per paper over a pool of 50, which is a cap of 1 applied after the rerank). **The cap position is strongly observable**: moving the rerank across the cap changes which papers survive on 217 of 256 queries, and #380's stated order is the better one. But reranking is a **wash for finding the right paper** (recall@5 identical at 156/256; the answer is lost 20x and gained 20x), it does **not** move `distinct@5` at all -- so B4 does not unblock #310 -- and **reranking BM25 does not help either**, which answers the open question the first of those sections left. All three findings were re-run against `ms-marco-MiniLM-L12-v2` and `BAAI/bge-reranker-base` and survive the change of reranker |
| [2026-08-26b: what cross-encoding the over-fetched passages costs](#2026-08-26b-what-cross-encoding-the-over-fetched-passages-costs) | **Current** | The cost half of #380, which the section above deliberately left unmeasured. At the shipped pool of 20 the cheapest reranker makes an `embed_index.search()` call **2.5x** more expensive on a GPU and **5.75x** on a CPU; `bge-reranker-base`, the quality winner above, costs a full **second per call on CPU**. Read beside that section's "recall@5 unchanged", this is what makes `rerank = false` the only defensible default |
| [2026-08-27: does claim-support checking (#C2) separate supported claims from unsupported ones on this corpus?](#2026-08-27-does-claim-support-checking-c2-separate-supported-claims-from-unsupported-ones-on-this-corpus) | **Current, qualitative only** | 71 real citations scored across four real drafts; a human read of the 20 lowest- and 20 highest-scored found the dominant failure at the low end is the wrong passage being matched, not genuine non-entailment. No `labels.json`/`--crosscheck` was run, so there is no separation statistic here, only the qualitative pattern and its examples |

The user-facing summary of everything still standing is
[docs/PERFORMANCE.md](../docs/PERFORMANCE.md); the reproducibility
contract is
[docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md#-what-is-reproducible-and-what-is-not).

## The corpus

`papers/bibliography.bib` has 646 entries; 501 resolve to a PDF on disk
(94 `non_pdf_attachment`, 50 `no_file_field`, 1 `pdf_path_gone`).

| | |
|---|---|
| PDFs to parse | 501 |
| Total pages | 13,400 |
| Total bytes | 1.54 GB |
| Pages: median / mean | 16 / 26.7 |
| Pages: p90 / p95 / max | 39 / 63 / 675 |

A single 675-page document is 5% of all pages. Any scheduling that picks
it up last is bounded below by that one document.

## Wall clock

Sample: 16 PDFs at even page-rank intervals (943 pages), so the sample's
page mix mirrors the corpus's.

| Configuration | s/page | Full-corpus estimate |
|---|---|---|
| 1 process, 1 A40 | 0.43 | **1h 36m** (per-page), 1h 56m (per-doc fit) |
| 1 process, CPU only | 1.37 | 5h 05m (per-page), 5h 21m (per-doc fit) |

> **Superseded 2026-08-04.** These are *extrapolations from a 16-PDF
> sample*, and both models understate a real run. Measured directly, a
> serial full-corpus pass with OCR **on** takes 6941.4s (1h 56m) -- which
> the per-doc fit got right and the per-page model missed by 21%. With
> OCR **off** the measured figure is 3330.4s (55m 30s) against a per-page
> prediction of ~39m: **41% low**. See
> ["2026-08-04: the full-corpus sweep"](#2026-08-04-the-full-corpus-sweep).

Per-PDF cost ranged 0.11-1.52 s/page, so read those as a band of roughly
1.5-2 hours on GPU, not a point estimate.

## The GPU is not the bottleneck

Sampled with `nvidia-smi dmon` during the serial run, and confirmed
against a CPU-only run of the same PDFs:

- **GPU SM utilisation averaged ~7%** -- mostly 0%, spiking to 47%.
- **VRAM: 1.7 GB of 46 GB** (3.6%).
- **The process sat at ~300% CPU** -- 3 of the 48 allowed logical CPUs.
- **Like-for-like GPU vs CPU on the same 6 PDFs: 32.0s vs 57.4s = 1.79x.**

One Docling process leaves ~93% of one A40 idle and touches 6% of the
available CPU; three of the four GPUs are never addressed at all. The
work is CPU-bound -- PDF backend, layout post-processing, and OCR (which
runs on onnxruntime, on the CPU) -- with short GPU bursts for the layout
and table models.

That 1.79x is the entire benefit the GPU currently delivers, and it is
why this work pursued CPU-level parallelism first and GPU assignment
second.

## Three code facts behind the numbers

1. **`chitragupta/sync.py`'s parse loop is serial** -- a plain
   `for ref in references:`. Its own comment names `ProcessPoolExecutor`
   as the deferred candidate and pre-commits to the right shape (ledger
   writes stay on the main thread). The reasons it gives for deferring
   hold for the `pdftotext` default and for routine incremental syncs;
   they do not hold for a bulk Docling run.

2. **`chitragupta/pdf_text.py:_extract_docling` builds `DocumentConverter()`
   inside the function** -- once per PDF. `initialized_pipelines` is an
   instance attribute, so every document re-initialises the models.
   Measured cold start for the first converter: **16.5s**.
   `chitragupta/enrich/docling_parse.py` calls `_build_converter()` inside
   `parse_doc`, with the same effect.

3. **`AcceleratorDevice.AUTO` resolves to `cuda:0`, always**
   (`decide_device("auto") == "cuda:0"`, verified directly). A bare
   `DocumentConverter()` does use a GPU with no configuration -- but
   every process that starts picks *the same* GPU. Using all four A40s
   requires explicit device assignment; it will not happen on its own.

A fourth fact, host-specific but a live trap for worker sizing:

4. **`os.cpu_count()` reports 96 here; only 48 are allowed.** Pool sizing
   must use `len(os.sched_getaffinity(0))`. Sizing off `cpu_count()`
   would oversubscribe 2x. This already bit the benchmark run: a
   `taskset -c 24-39` invocation failed outright with `Invalid argument`.

## 2026-08-02: parallel `sync`, and the ceiling it hit

Measured 2026-08-02 with the real `python -m chitragupta.corpus sync`, not the bench
harness: 60 bib PDFs (1,166 pages), `parser.backend = "docling"`, OCR off,
via `[parser].workers`.

| workers | wall clock | speedup | efficiency |
|---|---|---|---|
| 1 | 444.4s | 1.00x | -- |
| 4 | 123.4s | **3.60x** | 90% |
| 12 | 120.3s | 3.69x | 31% |

Four workers scale almost linearly. Twelve buy essentially nothing over
four, and `nvidia-smi dmon` during that run says exactly why:

```
# gpu    sm%          <- GPU 0 pinned at 100%, GPUs 1-3 idle throughout
    0    100
    1      0
    2      0
    3      0
```

**The bottleneck has moved.** Before this work the parse was CPU-bound
and one A40 idled at ~7%. Enough CPU parallelism to saturate that GPU
turns the same workload into a *single-GPU-bound* one -- while the other
three A40s are never addressed at all, because Docling's
`AcceleratorDevice.AUTO` resolves to `cuda:0` in every worker process
(fact 3 above).

That is the argument that produced per-worker GPU assignment: the four
GPUs stopped being redundant the moment document parallelism landed. A 60-document sample already saturates one card at 12
workers, so the full 501-document corpus will too.

On smaller batches the per-worker model load dominates instead: over 8
documents, 4 workers gave 1.90x and 8 workers gave none (34.6s / 18.3s /
19.3s). Each worker pays its own cold start, so parallelism is worth
having in proportion to how much work there is -- which is why the
resolved worker count is capped by the number of documents needing a
parse.

Correctness was checked, not assumed: `content/parsed/` after a 4-worker
run is byte-identical to the serial run's, and the ledger rows match.

## 2026-08-02: OCR costs more than the GPU saves

Measured 2026-08-02 on the same 16-PDF sample and the same GPU, with
`bench_docling.py --no-ocr`. Raw timings:
`results/2026-08-02-phase0/gpu_reused_noocr.jsonl`.

| | s/page | Full corpus |
|---|---|---|
| OCR on (Docling's default) | 0.431 | ~1h 36m |
| OCR off | 0.176 | **~39m** |

**2.46x**, from one setting -- more than the 1.79x the GPU is worth.

> **Superseded 2026-08-04.** 2.46x is a *serial 16-PDF sample* figure.
> Measured end to end on the full corpus, OCR costs **2.08x serially but
> 3.91x at 12 workers and 4.79x at 24** -- it is CPU-bound, so it
> competes with the parallelism. Quoting 2.46x for a parallel run
> understates it by roughly half.
Docling's OCR runs on the CPU (RapidOCR on onnxruntime), which is a large
part of why this pipeline is CPU-bound.

### It is not free, and the cost is easy to miss

Turning OCR off changed the extracted text of **8 of the 16** documents.
That is the number to design around, not the speedup.

OCR only runs on *bitmap* regions, so what it recovers is text that
exists in the PDF as an image rather than as characters. Diffing the two
outputs, that breaks down as:

- **Publisher furniture** -- `IEEEAccess`, `DTU Library`, logos. Noise;
  losing it is an improvement.
- **Figure sub-captions** -- e.g. "(a) The system context physical block
  diagram models the boundary of the system...". Borderline.
- **Real content, on a minority of documents.** `afrin_resource_2021`
  lost **10.1%** of its characters: two complete tables, a
  three-column comparison matrix and an abbreviations list, both embedded
  as images. `perno_implementation_2022` lost a paragraph of body prose
  set in a graphical text box.

So the default is `ocr = false` (2.46x on this serial sample -- 2.08x to
4.79x measured end to end depending on worker count, see below), but it
is a trade-off rather than a free win, and the
parse-quality guard will not catch a bad choice -- it looks for
run-together words, not for content that never arrived. A corpus of scans
needs `ocr = true`; so does one where tables-as-images matter more than
parse time.

## 2026-08-02: the converter rebuild

`DocumentConverter` cold start is **16.5s** on this host, and
`initialized_pipelines` is an instance attribute -- so the pre-0.12.0
`chitragupta/pdf_text.py`, which built one converter per PDF, paid a model reload
for every document in the corpus. Both `pdf_text.py` and
`enrich/docling_parse.py` now build one converter and reuse it, and
`parse_corpus` defers the build until a document actually needs parsing,
so a fully-cached re-run loads no models at all.

## 2026-08-02: spreading workers across the four A40s

Measured 2026-08-02 with the real `python -m chitragupta.corpus sync` over the **whole
501-PDF corpus** (13,400 pages), `docling`, OCR off, 12 workers. The A/B
is the same binary either way -- `CUDA_VISIBLE_DEVICES=0` confines every
worker to one card, which is exactly the pre-v1.1.0 behaviour, since
`AcceleratorDevice.AUTO` resolves to `cuda:0` in every process.

| | wall clock |
|---|---|
| 12 workers, one A40 (`AUTO`, i.e. before this change) | 528.0s |
| 12 workers, four A40s (round-robin) | **326.2s** |
| Speedup from using the other three cards | **1.62x** |

Against the ~39-minute serial baseline, the full corpus now parses in
**5m26s -- about 7x**.

### Corpus size decides whether this is worth anything

The same change measured on a 60-document subset showed **nothing**:
122.4s at 4 workers, 123.0s at 12, with all four GPUs busy and the CPU
~85% idle. Per-worker startup -- spawn, importing torch and docling, then
loading the models -- dominates at that size, and no amount of GPU
spreading helps. It only pays once there is enough work to amortise
twelve workers' startup, which the full corpus has and a 60-document
sample does not.

This is also why the earlier reading of the 12-worker plateau as
"GPU 0 is the bottleneck" was too simple. GPU 0 *was* pinned at 100%, but
freeing it did not speed up the 60-document run at all -- the plateau
there was startup, not contention. Both effects are real; they show up at
different scales.

### Output is not bit-reproducible under concurrency

Comparing the one-GPU and four-GPU runs over all 501 documents: **6 files
differ**, by 0 to 59 bytes out of ~100KB each (under 0.06%).

The differences are not device-dependent -- parsing the same document
explicitly on `cuda:0`, `cuda:1` and `cuda:2` gives byte-identical output
every time, and repeating a run at the same worker count reproduces
exactly. What varies is Docling's element grouping inside **dense
reference blocks** under heavy concurrency: the same words, split across
list elements or lines differently.

Nothing is lost, and retrieval tokenises on runs of `[a-z0-9]` rather
than on element or line boundaries, so this does not affect BM25 ranking.
(It does affect the passage sidecar, which was not measured until
[2026-08-07](#2026-08-07-does-the-quotable-passage-survive-a-re-parse).)

**Can it be turned off?** Not from Docling. Its `PdfPipelineOptions` has
no determinism, seed or reproducibility setting of any kind (checked
against 2.117.0's full field list), and `AcceleratorOptions` exposes only
`device`, `num_threads` and `cuda_use_flash_attention2`. The only lever
is below Docling, in torch: `torch.use_deterministic_algorithms(True)`
plus `cudnn.deterministic`, set inside each worker. That is not taken
here, for two reasons -- it costs throughput on exactly the models this
pipeline spends its time in, and it raises rather than degrades when an
op has no deterministic implementation, which would turn a cosmetic
difference into a hard failure. Revisit if bit-reproducible parses ever
become a requirement rather than a nicety.

It does mean `content/parsed/` should not be expected to be
byte-identical across runs at high worker counts -- v1.0.0's
"byte-identical to serial" observation was measured over 8 documents at 4
workers, where it holds, and does not generalise to 501 documents at 12.

## Per-worker startup: where the ~10s goes, and how much of it is shareable

Measured 2026-08-03 on the same host. The question this section answers
is the one the 60-document plateau above raised: workers were spending
about ten seconds each before producing anything, so what *is* that ten
seconds, and can a different multiprocessing start method share any of
it?

### The breakdown

One cold process, timed at each stage, parsing a small PDF twice (docling
2.117.0, OCR off, `cuda:0`, warm HuggingFace cache):

| Stage | Time |
|---|---|
| `import torch` | 1.16s |
| `import docling` (the 4 modules the converter needs) | 2.08s |
| `DocumentConverter(...)` construction | 0.13s |
| First `convert()` -- Docling loads its models here | 5.17s |
| **Total before the first parsed page** | **8.5s** |
| Second `convert()` of the same PDF, models warm | 0.33s |

So of the ~8.5s: **3.2s is importing Python modules and ~5.0s is loading
models.** Only the first is even a candidate for sharing between
processes -- `initialized_pipelines` lives on the converter instance, in
whichever process built it.

Two things that looked like they might be in that 5s, and are not:

- **CUDA context creation is almost none of it.** The same first
  `convert()` on `device="cpu"` takes 6.32s of which 2.24s is the parse
  itself, i.e. ~4.1s of model load; on `cuda:1` it is 5.24s of which
  0.42s is the parse, i.e. ~4.8s. The GPU adds ~0.7s over the CPU-side
  work of reading weights and building modules.
- **HuggingFace hub lookups are not it either.** `HF_HUB_OFFLINE=1`
  changed the first convert by 0.24s.

### Does `torch.cuda.device_count()` initialise CUDA in the parent?

**No -- and the code comment that said it did was wrong.** That claim was
the stated reason `sync` used `spawn`. Checked directly against torch
2.7.1: after `torch.cuda.device_count()` returns 4,
`torch.cuda.is_initialized()` is still `False`, and a child forked from
that parent allocates on `cuda:0` without complaint. torch routes device
counting through NVML precisely to keep that safe. Only *using* a device
in the parent breaks the child, and then it breaks loudly:

```
RuntimeError: Cannot re-initialize CUDA in forked subprocess.
```

`gpu_count()` now asks `nvidia-smi --list-gpus` instead, falling back to
torch only when the driver's own tool isn't on PATH. That is not because
the torch path was unsafe on this host -- it wasn't -- but because it
made safety depend on an implementation detail of one torch version, and
because it imported 1.2s and ~200MB of torch into a parent with no other
use for it. `CUDA_VISIBLE_DEVICES` has to be applied by hand on that
path: nvidia-smi ignores it, and torch does not.

### fork is still ruled out, for a different reason

Not CUDA -- sqlite. By the time `sync` builds its pool it holds two live
sqlite connections: the run lock (`BEGIN IMMEDIATE`, deliberately never
committed) and the ledger. SQLite's own documentation says not to carry
an open connection across `fork()`, and a forked worker finalising an
inherited connection on its way out would be rolling back a transaction
belonging to a process it is not.

Measurement removed the temptation anyway. Wall clock for N processes to
each build a converter and parse one PDF, charging any parent-side
prewarm to the total:

| Workers | spawn | fork | fork, parent pre-imports | forkserver | forkserver + preload |
|---|---|---|---|---|---|
| 4 | 11.26s | 9.68s | 9.70s | 10.39s | **9.55s** |
| 12 | 13.96s | 13.25s | 13.00s | 13.41s | **12.61s** |

forkserver with a preload list is the fastest at both sizes *and* is the
only one that inherits nothing from the parent -- its server is a fresh
interpreter, launched with `spawnv_passfds`, so workers get the preloaded
modules and no sqlite connections, no CUDA context, no file descriptors.

### The result that decided the design: a shared import is a wash

The obvious reading of the breakdown is "3.2s x N workers, shared once by
forkserver". That reading is wrong, and the real `sync` says so:

| 8 documents, 4 workers | median of 3 |
|---|---|
| spawn | 22.9s |
| forkserver, preload set at pool construction | 22.4s |

Workers import **concurrently**. On a host with CPUs to spare their
imports were already overlapped, so what forkserver takes out of N
children it puts back into the one parent that runs the preload -- and
the preload blocks pool construction. Net: nothing.

What *is* serial is the preload itself. Started before the parent reads
the bibliography rather than when the pool is built, it runs during the
~2.5s that read takes:

| | 4 live workers ready at |
|---|---|
| forkserver started when the pool is built | 6.90s |
| forkserver started before the bib read | **4.40s** |

`multiprocessing.forkserver.ensure_running()` returns in ~0.02s -- it
launches the server and does not wait for its imports -- so this costs
the caller nothing but the ordering.

### End to end, on the real `sync`

Medians of three runs each, fresh `content/` every time so every document
needs a parse. Rank-stratified subsets of the bib corpus, `docling`, OCR
off, on the four-A40 host. `workers = 1` takes the serial path, which has
no pool and therefore no start method.

| Documents | Workers | spawn | forkserver | Saving |
|---|---|---|---|---|
| 8 | 1 (serial) | 46.2s | -- | -- |
| 8 | 4 | 23.1s | **21.8s** | 1.3s (5.6%) |
| 8 | 8 | 22.9s | **20.7s** | 2.2s (9.6%) |
| 60 | 1 (serial) | 383.2s | -- | -- |
| 60 | 4 | 103.6s | **101.9s** | 1.7s (1.6%) |
| 60 | 12 | 80.8s | **78.8s** | 2.0s (2.5%) |

Run-to-run spread was 0.3-1.0s, so the effect clears the noise at every
point, and it is the *same* effect at every point: a roughly constant
1.3-2.2s off pool startup. What changes with corpus size is only how much
of the total that is -- 9.6% of an 8-document run, 2.5% of a 60-document
one, and it would be well under 1% of the full 501-PDF corpus.

**So this does not make a bulk parse meaningfully faster, and it was
never going to.** The startup breakdown said so before any of these runs:
3.2s per worker, shared once, against a parse measured in minutes. What
it does help is the case the earlier measurements kept running into --
a handful of documents, where startup *is* the run.

Correctness was checked rather than assumed: over 8 documents at 4
workers, `content/parsed/` is byte-identical between the two start
methods and the ledger rows match. Ctrl+C behaviour is unchanged --
exit 130, no orphaned processes, and the same
`resource_tracker: ... leaked semaphore` warning that `spawn` already
produced (a consequence of `os._exit` skipping interpreter shutdown, not
of the start method).


## 2026-08-04: the full-corpus sweep

Measured with the real `python -m chitragupta.corpus sync` over **all 501 PDFs** rather
than a sample, on the same machine (4x A40, 48 CPUs available of 96 host
logical CPUs), repository at `92c1420` (v2.1.0). Every run started from
an empty `CONTENT_DIR` and reported 501 parsed, 0 failed. Raw records:
`results/2026-08-04-full-corpus/sweep.jsonl` -- **wall clock only.** The
CPU-busy and GPU-utilisation figures quoted below came from separate
instrumented runs on the same machine and are *not* in that file; the
resource sampler was added to `sweep_sync.py` afterwards, so
`results/2026-08-04b-repeats/sweep.jsonl` is the first record set
carrying them. Treat the timings here as reproducible from the committed
data and the utilisation figures as reported, not evidenced.

Reproduce with `bench/sweep_sync.py`, which was written for exactly this
and did not exist when the earlier sections were measured.

### It corrected the baseline, which corrected everything downstream

| | |
|---|---|
| Serial, OCR off -- **measured** | **3330.4s (55m 30s)** |
| Serial, OCR off -- per-page extrapolation (what the docs quoted) | ~39m, **41% low** |
| Serial, OCR off -- per-doc fit | ~50m 32s, 9% low |

One wrong denominator propagated into every efficiency figure in this
repository. `bench/estimate.py` now leads with the per-doc model and says
plainly that both understate.

### Worker scaling

| Workers | Wall clock | Speedup | Efficiency | |
|---|---|---|---|---|
| 1 | 3330.4s | 1.00x | -- | |
| 4 | 799.2s | 4.17x | 104% | |
| 8 | 428.6s | 7.77x | 97% | |
| 12 | 310.2s | 10.74x | 89% | the most `worker_ceiling()` allows |
| 16 | 268.1s | 12.42x | 78% | |
| 24 | 237.6s | 14.02x | 58% | |
| **32** | **220.7s** | **15.09x** | 47% | single run; see 2026-08-04b |
| 48 | 226.3s | 14.72x | 31% | single run; see 2026-08-04b |

**The clamp is costing 1.41x.** `worker_ceiling()` caps at
`allowed_cpus // 4 = 12`; the optimum is near 32. Rows above 12 required
relaxing that constant and are not reachable with a stock checkout.

`[parser].workers = 16` resolves to 12 and takes 315.9s -- the clamp
working as documented.

### The `_CPUS_PER_DOCLING_WORKER = 4` model is wrong

CPU busy during these runs, against the 48 available:

| Run | CPUs busy | of the 48 allowed |
|---|---|---|
| 16 workers | 18.7 | 39% |
| 32 workers | 34.0 | 71% |
| 24 workers, OCR on | 44.6 | **93%** |

At 32 workers the CPU is still only 71% busy. The constant came from a
single "~300% CPU" observation of one process; the optimum implies a
divisor near **1.5**.

Confirmed independently: docling's own `num_threads` barely matters.

| threads (at 12 workers) | 1 | 2 | 4 (default) | 8 |
|---|---|---|---|---|
| wall clock | 305.3s | 304.3s | 310.2s | 305.6s |

**1.9% spread -- noise.** The hypothesis that `12 workers x 4 threads`
oversubscribes 48 CPUs is disproved, and it explains why more workers
help: the threads a worker is charged for are not doing much.

### GPUs

| Workers | 1 GPU | 2 GPUs | 4 GPUs | 1->2 | 2->4 |
|---|---|---|---|---|---|
| 12 | 518.4s | 339.7s | 310.2s | 1.53x | 1.10x |
| 24 | 535.8s | 298.6s | 237.6s | **1.79x** | 1.26x |

The second card is worth far more than the third and fourth, and matters
more at higher worker counts. At 24 workers, one GPU is *slower* than at
12 -- piling workers onto a single card is counterproductive.

These agree with the 2026-08-02 phase 2 figures (528.0s / 326.2s) to
within 2-5% on a rebuilt venv, which is the cross-check that the parallel
measurements were sound and only the *baseline* was wrong.

### OCR

| Workers | OCR off | OCR on | Cost |
|---|---|---|---|
| 1 | 3330.4s | 6941.4s | 2.08x |
| 12 | 310.2s | 1213.9s | 3.91x |
| 24 | 237.6s | 1139.0s | **4.79x** |

Speedup from 1 to 24 workers: **14.02x with OCR off, 6.09x with it on.**
OCR roughly halves how well the pipeline parallelises.

### Open, not glossed

- **The OCR optimum was not found** -- swept only to 24 workers, where it
  was still improving.
- **One machine, one corpus.** Any specific replacement divisor may not
  generalise, particularly to a CPU-only machine where the GPU is doing
  none of the work.

Two questions this section used to list were answered on 2026-08-04b,
below.

## 2026-08-04b: repeats, and where the time goes

The single-run sweep above left two questions. Three runs per point, with
`sweep_sync.py` timing each run's phases, settled both. Raw records:
`results/2026-08-04b-repeats/sweep.jsonl`.

| Workers | Runs (s) | Median | Spread |
|---|---|---|---|
| 24 | 234.6, 235.0, 235.8 | 235.0s | 1.2s |
| 32 | 222.8, 223.4, 309.6 | 223.4s | **86.8s** |
| 48 | 220.4, 221.4, 227.7 | 221.4s | 7.3s |

### The 32 -> 48 "reversal" was noise

Medians put 32 and 48 **0.9% apart** — while the spread *within* the
32-worker configuration alone is 86.8s. The single-run pass had 32 at
220.7s and 48 at 226.3s and read that as a knee; with repeats the
ordering flips.

**The curve plateaus past ~32; it does not turn back up.** Single runs
cannot resolve anything in that region, which is the argument for
`--repeat`.

### What flattens the curve: startup, plus the CPU filling up

Timing each run's phases separates the three candidates:

| Workers | Startup (to 1st document) | Tail (after last) | CPU busy |
|---|---|---|---|
| 24 | 18.6s — **7.9%** | 4.9s — 2.1% | 56% |
| 32 | 21.8s — **8.9%** | 5.9s — 2.6% | 70% |
| 48 | 28.5s — **12.7%** | 7.9s — 3.6% | 78% |

- **Startup is a growing tax, not a fixed one.** Every worker pays its
  own ~8.5s model load, so the cost of standing the pool up rises with
  the pool: 7.9% of the run at 24 workers, 12.7% at 48.
- **Startup is measured as time to the first completion**, so it
  includes the fastest document's parse and overstates pure startup. Its
  growth across worker counts does not: a single parse does not slow down
  because the pool got bigger.
- **The CPU is heading for saturation** — 56% to 78% host-wide across the same
  range. Earlier the 71% figure at 32 workers was read as "the CPU is not
  the limit"; against 56% at 24 and 78% at 48 it is clearly *becoming*
  one.
- **The long-document tail is not the story**: 5-8s throughout, under 4%.

Neither cost alone explains the plateau. Together they account for it,
and both worsen with every worker added — which is why past ~32 there is
nothing left to win by adding more.

## 2026-08-07: does the *quotable passage* survive a re-parse?

Measured with `bench/repro_check.py` on the same host as the sections
above, but with **48 CPUs pinned via `taskset -c 0-23,48-71`** to match
the `Cpus_allowed_list` those sections ran under -- the container now
permits 96, which would move `worker_ceiling()` from 12 to 24 and change
`docling_threads()` underneath the comparison. Workers held at 12
throughout; GPU count is the only varied axis, 1 against 4, the same pair
that produced ["Output is not bit-reproducible under
concurrency"](#output-is-not-bit-reproducible-under-concurrency) above.
Raw records: `results/2026-08-07-passage-repro/*.json`.

### The question that section left open

That finding compared `content/parsed/<citekey>.txt` and concluded the
differences were cosmetic, on the grounds that retrieval tokenises on
whitespace. True for BM25 -- but `chitragupta/passages.py` writes **one passage
record per `dl_doc.texts` item**, and `PASSAGE_LABELS` contains
`list_item`, the element type that finding names. So the same variance
could be changing the exact span this pipeline would quote to a reviewer,
which is not cosmetic on a citation-grounding tool. Nobody had looked.

### What was run

Page-count outliers (Tukey, `Q3 + 1.5*IQR` = 49 pages) were excluded from
the n=50 and n=100 samples, then measured *separately* as their own arm:
they are the documents with the largest reference lists, so excluding
them without checking would have let the exclusion decide the result.

Each pair is compared at three levels -- file bytes, passage *spans*
(text, label, page) and passage *texts* alone -- because they do not
agree, and only the last one is a changed quotation.

| Arm | Docs | Pages | across `.txt` | across spans | across **texts** |
|---|---|---|---|---|---|
| n=50 trimmed | 50 | 848 | 0 | 0 | 0 |
| n=100 trimmed | 100 | 1683 | 1 | 1 | 1 |
| n=100 trimmed (independent repeat) | 100 | 1683 | 2 | 2 | 2 |
| outliers only | 36 | 5590 | 1 | 1 | **0** |

**Across-config, over 286 document comparisons: 4 differ in bytes
(1.4%), 4 in passage spans (1.4%), and 3 in passage *text* (1.0%).**
Consistent with the 6-of-501 (1.2%) above, so this replicates the
phenomenon rather than contradicting it. Both populations show it:
trimming was safe here, but only because the outlier arm was run.

The gap between spans and texts is the whole reason for measuring both.
Every difference in the outliers arm is a label or bounding-box change on
byte-identical text -- real instability in Docling's classification, but
**not** a changed quotation. Reporting the spans number as though it were
the text number would have overstated the finding by a third.

An earlier session on 2026-08-07, before the texts level existed, saw
6/286 bytes and 5/286 spans -- roughly twice this session's byte rate.
Two independent sessions differing about twofold at a ~1-2% base rate is
what a low-rate stochastic effect looks like, and is the same caveat as
["Power, stated plainly"](#power-stated-plainly) below. Only this
session's records are committed, because the earlier ones predate the
spans/texts split and cannot answer the question the table now asks.

### Correction: same-configuration runs do **not** reproduce exactly

The section above states that "repeating a run at the same worker count
reproduces exactly". That is false, and this is the measurement that
falsifies it: **5 of 572 same-configuration document-comparisons differ
in bytes (0.9%), 4 in passage spans (0.7%), and 2 in passage text
(0.3%)**. Every instance was at 4 GPUs; the single-GPU arm was clean in
all four samples, over 286 comparisons. A same-configuration run
therefore changes a quotable passage about once in every 300 documents --
rarer than the across-config case, and not zero.

So the axis is contention, not the *change* in contention -- a
multi-GPU run disagrees with itself. Across-config is still ~4x more
likely on text (1.0% vs 0.3%), so widening the concurrency delta does
raise the rate; it does not create the effect.

### Three mechanisms, and only one of them matters

Inspecting the kept bytes (`--keep`) separates cases that a byte-diff
would have reported identically. The excerpts below were captured from a
kept parse in the earlier session; **the committed records reproduce all
four documents independently, in the same three classes** -- which is
checkable without the bytes, since each record names the differing
citekeys at each of the three levels:

| Document | Mechanism | In the records |
|---|---|---|
| `frasheri_addressing_2023` | reference entry splits | in `texts_differ` |
| `noauthor_compilation_nodate` | two entries merge | in `texts_differ` |
| `delhibabu_synthesis_2023` | label flip, text identical | in `spans_differ`, **not** `texts_differ` |
| `zhang_digital-triplet_2024` | table regroups | in `txt_differ` only |

A fifth, `noauthor_mqtt_2018`, appeared in this session's outliers arm as
another label-only flip -- the same class, a document the earlier session
did not surface, which is what a ~1% rate over a small sample looks like.

**1. A reference entry splits or merges -- the quotation changes.** In
`frasheri_addressing_2023`, between two runs of an *identical*
configuration, one 279-character record became two:

```
- 'M. Grieves, J. Vickers, Digital twin: ... Transdisciplinary Perspectives on Co'   (279c)
+ 'M. Grieves, J. Vickers, Digital twin: ... Transdisciplinary Perspectives on Co'   (223c)
+ 'International Publishing Switzerland, 2017, pp. 85-113.'                           (55c)
```

Quoting the second version returns a reference truncated before its
publisher and page range. In `noauthor_compilation_nodate` the reverse
happened -- two records merged into one, splicing reference numbers 57
and 60 into a single passage. **This is the failure mode that matters:**
the text of a quotable passage genuinely differs between runs.

**2. A label flips inside `PASSAGE_LABELS` -- harmless, but only by
luck.** `delhibabu_synthesis_2023` kept all 540 records and identical
text; one line was classified `list_item` in the 1-GPU run and `text` in
the 4-GPU run. Both are in `PASSAGE_LABELS`, so the passage survives. A
flip *out* of that set -- to `footnote`, `caption`, `page_header` --
would delete a quotable passage outright. What makes this instance benign
is the membership of the set, not the flip.

**3. A table regroups -- the `.txt` moves, the sidecar does not.**
`zhang_digital-triplet_2024` differed in its markdown table's cell
wrapping across runs while its 184 passage records stayed byte-identical
in both text and label, because tables are not in `PASSAGE_LABELS`. This
is the one case where the older "cosmetic" reading is exactly right.

### What this means for the contract

`content/parsed/<citekey>.passages.json` is **not** reproducible under
docling, and not merely across configurations -- a multi-GPU run
disagrees with itself on the *text* of a passage at roughly 0.3% of
documents, and with a differently-configured run at roughly 1.0% (1.4%
if a label change counts). Neither `--reparse` nor a fresh clone is
guaranteed to reproduce a previously quoted span.

Unchanged by this: `pdftotext` output is byte-identical across runs, and
the ledger rows are stable except `last_synced`. See
[docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for the full artifact
table this feeds.

### Power, stated plainly

286 across-config comparisons at a ~1% rate is enough to establish that
the effect exists and reaches the passage layer. It is **not** enough to
put a tight interval on the rate, and a 0-of-50 arm is fully consistent
with a 2% rate rather than evidence of stability. The three mechanisms
are each observed once or twice; treat them as existence proofs of
distinct failure modes, not as a frequency distribution over them.

## 2026-08-08: what a drift sweep costs

`python3 -m chitragupta.dossier status --all` builds a BM25 index in memory and
throws it away, rather than calling `chitragupta.retrieval.search()` -- which
would take a write connection to the ledger and rewrite
`content/retrieval_index.json` on every scan
([docs/DRAFT-ITERATION.md](../docs/DRAFT-ITERATION.md#-why-the-new-papers-are-not-found-with-search)).
That design was argued from the shape of the code and shipped with an
unmeasured claim attached: that a warm cache makes the scan nearly free
and a cold one costs one corpus tokenization *shared across every
dossier*. This is the stopwatch.

Host: the multi-GPU machine (48 allowed CPUs, 251 GB RAM), bare
`python3` 3.12.3, no GPU involved -- `chitragupta.dossier` is stdlib-only, so
this needs no venv. Medians of 5 runs.

**These numbers predate a bug in the harness, and are on the right side
of it.** `bench_drift.py` narrows each row to `n` dossiers by overriding
`all_dossiers`, and #224 (2026-08-17) moved the name that override has to
reach when it split `chitragupta/dossier.py` into a package -- after
which every row measured the whole set, and the "dossiers swept" column
would have been fiction. This run is from 2026-08-08, nine days before
that, which its own varying-by-count numbers below confirm: a run through
the broken path prints the same figure three times. #294 fixed the
override and added the `self_check()` that would have caught it. Anything
measured with this script between those two dates should be re-run.

### The real corpus: 646 ledger rows, 47.4 MB of parsed text

`bench/bench_drift.py --real` copies this host's own
`content/ledger.sqlite` and tokenizes the real `content/parsed/*.txt`
behind it. The ledger is copied rather than opened in place because the
warm step calls the real `retrieval.search()`, which goes through
`ledger.connect()` -- a write connection that runs migrations. Timing a
scan against someone's corpus is fine; migrating it is not. Verified
byte-identical after the run.

4 logged queries per dossier:

| Dossiers swept | Cold (no index cache) | Warm (cache from a prior `search()`) |
|---|---|---|
| 1 | 2.032s | 0.218s |
| 10 | 2.036s | 0.257s |
| 50 | 2.227s | 0.436s |

**The claim holds, and this is the line that shows it.** Going from 1
dossier to 50 costs **+0.19s cold** -- about 4ms per additional dossier
against a 2.0s fixed cost. The tokenization is paid once for the sweep,
not once per dossier; had it been per-dossier, 50 dossiers would have
taken somewhere near 100s.

A warm cache is **5.1-9.3x** faster than a cold one, so "nearly free"
was fair for the warm case and optimistic for the cold one: 2.1s is not
free, it is just cheap enough to run after every sync.

Dossiers that logged no retrieval calls never build an index at all:
**0.040s for 50 dossiers**, which is the pure file-reading floor.

### Run-to-run spread, and why the marginal cost is still safe to quote

Three independent runs of the same configuration:

| | run 1 | run 2 | run 3 (the one above) | spread |
|---|---|---|---|---|
| cold, 1 dossier | 2.130s | 2.126s | 2.032s | 4.8% |
| cold, 50 dossiers | 2.364s | 2.368s | 2.227s | 6.4% |
| warm, 1 dossier | 0.218s | 0.221s | 0.218s | 1.4% |
| **paired delta, 1 -> 50 cold** | **+0.234s** | **+0.242s** | **+0.194s** | |

An earlier edition of this section quoted "about 0.5%" from the first two
runs and called the marginal cost "comfortably outside the noise". The
third run makes the first half of that wrong: cold time varies by
**~5-6%** between runs, which is ~0.1-0.14s -- the same order as the
0.19-0.24s delta being measured. Warm time is far steadier (1.4%),
because it is not dominated by re-reading and re-tokenizing 47 MB.

The conclusion survives, but only because of *how* the delta is measured.
The 1-vs-50 comparison is **paired**: both numbers come from the same
process, the same page-cache state and the same machine conditions,
seconds apart. All three runs independently produce a positive delta in a
narrow band (0.194-0.242s), which is the evidence -- not a subtraction
across separately-scheduled runs, which the 5% drift would swallow.

Quote the marginal cost from a single run's paired pair. Do not compute
it by differencing numbers from two different runs of this table.

### Synthetic corpora, as a scaling cross-check

`bench_drift.py` without `--real` generates a corpus of the same shape
(501 documents, median 16 pages at ~500 words, one 675-page book, Zipfian
vocabulary). Kept because it is the only way to vary corpus size, and
worth reading as a check on the generator: at a comparable document
count it lands within ~30% of the real corpus, which is close enough to
trust its *scaling* and not close enough to quote its absolute seconds.

| Corpus | Documents | Parsed text | Cold, 1 dossier | Cold, 50 |
|---|---|---|---|---|
| real | 646 | 47.4 MB | 2.032s | 2.227s |
| synthetic | 501 | 38.1 MB | 1.521s | 1.685s |
| synthetic | 2000 | 148.6 MB | 5.857s | 6.471s |

4.0x the documents costs 3.9x the cold time (1.521s -> 5.857s), so the
tokenization is linear in corpus size, as expected -- it reads every
parsed file once. The per-dossier marginal cost stays flat at every
size: +0.61s for 49 more dossiers at 2000 documents, ~12ms each.

### What this does not measure

- **A cold page cache.** Every run here re-read 38-149 MB that the OS
  had cached; the first sweep after a reboot pays disk for it too.
- **Another corpus's vocabulary.** One real corpus, on one topic. A
  corpus with a much larger vocabulary changes the index size, though not
  the shape of the result.
- **`--json`.** Serialization is a rounding error against tokenization
  and was not separated out.
- **Concurrency.** The scan is single-threaded and was measured on an
  otherwise-idle machine.

Reproduce:

```bash
python3 bench/bench_drift.py --dossiers 1 10 50 --repeats 5 \
    --out bench/results/<date>-drift/drift-501.json
```

## 2026-08-10: `overlap` and `scan` -- what the fingerprint index (#110) and the whole-draft scan (#111) actually buy

Both features shipped on an architectural argument (content-addressed
caching, a corpus-wide index) rather than a stopwatch. This measures both
against a real draft and this project's own real corpus, rather than the
tiny synthetic fixtures the unit test suite uses.

Host: the multi-GPU machine (48 allowed CPUs, 251 GB RAM), bare `python3`
3.13.5, no GPU involved -- `chitragupta.overlap_index` and `scripts/verbatim_check.py`
are stdlib-only. Corpus: this project's own `content/ledger.sqlite`, 497
parsed items. Draft: `bench/fixtures/cloud-computing-for-digital-twins.md`,
a genuine ~3,000-word chapter written for this measurement, citing 16 real
corpus papers.

### #110: the per-document fingerprint cache

`scripts/verbatim_check.py overlap` used to re-invoke `pdftotext -layout`
on the cited PDF and rebuild its n-gram dictionary from scratch on every
call. Measured against the 16 citekeys the draft actually cites, before
(commit 18f9f4b2, the parent of #110's merge) and after:

| | 16x `overlap` |
|---|---|
| before #110 (pdftotext subprocess, every call) | 2.379s |
| after #110, cold (.fpr cache built this run) | 0.477s (**5.0x**) |
| after #110, warm (.fpr cache from a prior run) | 0.081-0.087s (**27-29x**) |

The "before" figure is a one-time historical comparison, not something
`bench/bench_overlap.py` reproduces going forward -- the pre-#110
implementation no longer exists on `main`. Reproduce it by checking out
18f9f4b2 and timing `cmd_overlap` from `scripts/verbatim_check.py` there.

### #111: N invocations of `overlap` versus one `scan`

Before #111, the only way to approximate a whole-draft check was running
`overlap` once per citekey the draft cites -- and even that only ever
compares a paragraph against the one source it names. `scan` slides the
whole draft across the whole corpus index in one call, no citekey
argument.

`bench/bench_overlap.py --draft bench/fixtures/cloud-computing-for-digital-twins.md`,
against the real corpus, `CONTENT_DIR` pointed at this host's own
`content/`:

| | time |
|---|---|
| 16x `overlap` (warm .fpr caches, i.e. #110 already paid for) | 0.087s |
| 1x `scan`, cold corpus index (first `build_corpus_index()` ever, this host) | 27.2-27.5s |
| 1x `scan`, warm corpus index (unchanged corpus, second call) | 0.214-0.216s |

Read as a wall-clock number alone, this looks like a regression: 0.087s
for the thing #110 already made fast, versus 27s the first time anyone
runs `scan` on an unchanged 497-document corpus. That first cost is the
one-time price of merging every fingerprintable document's postings --
per-document fingerprinting is itself cached (`fingerprint_document`), so
a *second* corpus-wide build, even after every existing `overlap` call
has already populated the per-document `.fpr` cache, still pays the
merge-and-sort over ~millions of postings once. After that one-time
build, `scan` is 0.21s regardless of how many citekeys the draft cites --
the real comparison the "N invocations" framing invites is N *scan*-scale
checks against N separate `overlap` calls, and `scan` checks every
source in the corpus, not just N of them, in less time than 3 warm
`overlap` calls take.

**The number that matters is not the wall clock.** It's what each mode
can structurally see. `bench/fixtures/cloud-computing-for-digital-twins-planted-reuse.md`
is the same chapter with one added paragraph, verbatim from a real,
uncited corpus paper (`aguzzi_cloud_2020`, never mentioned anywhere else
in the draft):

```
16x overlap (one per cited source): surfaces the planted reuse? False
1x scan: surfaces the planted reuse? True
  [18 words, pdf p.1] aguzzi_cloud_2020 (tier=exact) [UNCITED SOURCE]
  [10 words, pdf p.2] aguzzi_cloud_2020 (tier=exact) [UNCITED SOURCE]
```

This is not a near-miss `overlap` could catch with a longer run or a
lower `--n` -- it is structural. `cmd_overlap(draft, citekey)` only ever
loads *that* `citekey`'s own fingerprint (`grams_for_citekey`); a source
never named in the 16 citekeys a reviewer would think to check is never
loaded at all, no matter how many times `overlap` is run. `scan` finds it
in the same 0.21s warm call as everything else, because it checks every
parsed source in the corpus against every word of the draft, not just the
sources the draft happens to cite.

### What this does not measure

- **A corpus larger than 497 documents.** The one-time `scan` build cost
  is expected to grow roughly linearly with corpus size (more documents
  to fingerprint and merge), matching `bench_drift.py`'s finding for the
  retrieval index's own cold cost -- not verified here.
- **`--gap`'s cost.** The gap-tolerant run merge is a constant-factor
  addition per diagonal group; not separated out from the rest of `scan`'s
  per-call cost.
- **Concurrency.** Both modes are single-threaded, measured on an
  otherwise-idle machine.
- **A cold page cache.** `content/ledger.sqlite` and 497 parsed text files
  were already OS-cached from prior runs on this host.

Reproduce:

```bash
CONTENT_DIR=/path/to/your/content python3 bench/bench_overlap.py \
    --draft bench/fixtures/cloud-computing-for-digital-twins.md \
    --out bench/results/<date>-overlap/overlap.json
```

## 2026-08-13: what an `overlap_gate` would block, and how much of it would be wrong (#130)

[#130](https://github.com/prasadtalasila/chitragupta/issues/130) asks
whether a long verbatim run should block a draft the way `python -m
chitragupta.draft gate` blocks an unresolvable citekey, and forbids guessing the
threshold: it is to be "tuned against real reports". This is the report.

Host: as above. Corpus: the same 497 parsed documents, `docling` backend,
no allowlist configured. Drafts: the 15 chapters of
`digital-twins-for-software-engineers` (178,077 words), restored from a
`content/` backup -- organic, LLM-written textbook prose grounded in this
corpus, with no planted reuse, which is what makes a false-positive rate
measurable at all. `bench/fixtures/` cannot serve: its reuse is planted,
so it is a true positive by construction.

### References masking decides the answer, and it was broken

`_mask_for_scan` blanks the draft's own bibliography before scanning,
because two documents citing the same paper share its title and venue
verbatim. `references.section_start` matched only single-level heading
numbers (`(?:\d+[.)]\s*)?`), so a book numbering its headings per chapter
-- `## 1.14 References` -- was never masked. All 15 chapters were
affected; the three non-book drafts, which write a bare `## References`,
were not.

| Arm | Findings | >= 15 words | Gateable |
|---|---|---|---|
| References masked (fixed) | 159 | 16 | 14 |
| References unmasked (as shipped) | 5,356 | 1,013 | 1,011 |
| References masked + allowlist | 146 | 3 | **1** |

**72x on the gateable population** (1,011 against 14; 63x on the long
bucket, 1,013 against 16), from one unanchored regex. Unmasked, chapter 1
alone produced 577 findings of which 97.7% sat in the reference list and
**100% of its long bucket** did. Every number below is from the masked
arm; the pattern is fixed in `chitragupta/references.py`.

`section_start` is also what `references apply` splices on and what
`render_output` strips, and both act destructively on the index it
returns -- so the same miss applies to them. That is read off the shared
call, not measured here; neither path was exercised.

The third arm is #130's own qualifier: its gate is *allowlist-filtered*.
Five entries -- the ISO 23247 and VanDerHorn definitions and two lines of
Kritzinger's taxonomy, committed as `candidate_allowlist.toml` -- take
the gateable population from 14 to **1**, and that one is an attributed
quotation. The mechanism meant to make a gate tolerable empties it.

### No threshold blocks anything real

Sweeping the predicate `tier in {exact, skip-gram} and span_words >= T
and not (quoted and cites_source)` over the 14 gateable findings.

Terms, used throughout this section and in the record it is read from:

- **T** -- the candidate `GATE_THRESHOLD`, a run length in words. A
  finding blocks when its `span_words` reaches T.
- **tp** (*true positive*) -- a blocked finding that is genuine
  uncredited reuse, which a reviewer would require be fixed. Blocking it
  is the gate working.
- **fp** (*false positive*) -- a blocked finding no reviewer would act
  on: a canonical definition, a standard's own wording, an attributed
  quotation. Blocking it is the gate costing someone an edit for nothing.
- **precision** -- tp / (tp + fp) among what blocks at T. How much of
  what the gate stops is worth stopping.
- **missed_tp** -- true positives that stop blocking as T rises, i.e.
  *false negatives* (fn) introduced by the threshold. Precision alone
  always flatters a high threshold; this is the cost against it.
- **gateable** -- findings the predicate could ever act on, after the
  `quoted and cites_source` exemption and the tier restriction.

| T | blocked | tp | fp | precision | drafts blocked |
|---|---|---|---|---|---|
| 15 | 14 | 0 | 14 | 0.00 | 3 |
| 20 | 8 | 0 | 8 | 0.00 | 2 |
| 25 | 3 | 0 | 3 | 0.00 | 1 |
| 29 | 2 | 0 | 2 | 0.00 | 1 |
| 30 | 0 | 0 | 0 | -- | 0 |

**Zero true positives at every threshold.** Across 178,077 words of real
prose against the 497-document corpus it was written from, the exact
tier finds no uncredited verbatim reuse -- only canonical definitions and
attributed quotations. There is no `GATE_THRESHOLD` that blocks
something worth blocking; the choice is between blocking false positives
and blocking nothing. With the allowlist applied it is starker: one
gateable finding survives in the whole book, and it is a quotation in
quote marks with its source cited.

The 16 findings reduce to seven distinct passages, dominated by two:
ISO 23247's definition of a digital twin, and VanDerHorn & Mahadevan's
consolidated definition. Both are quoted *and attributed* by several
corpus papers, verified in the parsed text -- `paredis_family_2023` puts
the ISO sentence in quote marks and names the standard;
`thelen_comprehensive_2022` p.3 writes "VanDerHorn and Mahadevan (2021)
proposed ...". The draft does the same thing and cites one source for it.

That last point is the structural finding, and `cites_source` cannot fix
it: **a definition reproduced by N corpus papers can only be cited to
one, so the other N-1 report as `UNCITED SOURCE`.** Two findings show the
sharper form -- a Kritzinger taxonomy blockquote, correctly quoted and
correctly cited to `kritzinger_digital_2018`, matched against
`barbie_toward_2024`, which reproduces the same taxonomy. It is
`quoted=true, cites_source=false`, so `_bucket` keeps it in `long` and
#130's own exemption does **not** reach it. A correctly quoted,
correctly credited passage would block.

### Span length does not separate the two populations

The zeros above understate the problem, because they could be read as
"tune T higher". The gateable false positives, in words:

```
29, 29, 28, 24, 23, 20, 20, 20, 19, 17, 16, 15, 15, 15
```

The one true positive available anywhere in this repository -- the
planted `aguzzi_cloud_2020` lift below -- is **18 words**, inside that
range rather than beyond it. So `T <= 18` catches the genuine lift and
admits nine false positives longer than it, and `T >= 30` clears every
false positive and misses the genuine lift entirely. **No threshold
admits the true positive and excludes the false ones.**

That is the finding that bears directly on #130, whose premise is that a
generous span threshold makes the gate tolerable: on this evidence the
variable it asks to be tuned does not discriminate, so no amount of
tuning produces a usable gate.

One feature does partly discriminate, and it is not span. The two large
false-positive clusters are each matched by **4 distinct citekeys** --
many corpus papers carry the same sentence because it is a definition --
where the planted true positive matches exactly **1**. It explains 8 of
the 14, and no more: the remaining four passages match a single citekey
and look like the true positive on every feature recorded here.

### The detector is not blind

A precision of 0.00 could equally mean the scan sees nothing, so the same
build was run against the planted-reuse fixture and its control:

```
planted : 3 findings, 1 at >=15w -- 18w aguzzi_cloud_2020, UNCITED SOURCE
control : 1 finding,  0 at >=15w
```

The known true positive is found and the control stays clean, so the
zeros above are a measurement rather than an absence of one.
`bench_overlap_gate.py` also runs a `self_check()` on every invocation
and refuses to print a table when the index is empty or findings are
unlabelled, for the same reason.

### What this does not measure

- **Paraphrase.** The exact tier cannot see it, and
  [PLAGIARISM-DESIGN.md](../docs/PLAGIARISM-DESIGN.md) names literal paraphrase an
  LLM's default failure mode. "Zero true positives" means zero *verbatim*
  reuse, not no borrowed wording. This is the single largest caveat: the
  tier that would gate is the tier blind to the likeliest offence.
- **Thresholds below 15 words.** Labelling covered the report bucket and
  above, so the sweep cannot say whether a gate should fire lower.
- **Reuse from outside the corpus.** Every finding is against one of 497
  parsed documents; a lift from an unparsed source is invisible.
- **Whether a blocked draft is fixable.** The `long` runs counted here
  are exactly the class `overlap-reviser` refuses to rewrite unattended,
  referring the paraphrase-or-quote choice to a person.
- **Other genres.** One book, one topic, one author's voice.
- **Cross-page runs.** #131 merges runs across a source page break.
  *Zero* of all 159 findings has `end_page > page` -- weak evidence that
  the merge rarely fires on this corpus, and no evidence at all about
  that population's false-positive rate, which remains unmeasured.

One correction to [the 2026-08-10 section](#2026-08-10-overlap-and-scan----what-the-fingerprint-index-110-and-the-whole-draft-scan-111-actually-buy):
`_TOKENIZER_VERSION` went 1 -> 2 with #131, invalidating every `.fpr`, so
a cold build now re-fingerprints rather than re-merges. Measured here at
**26.8s** for 497 documents -- unchanged against the 27.2-27.5s recorded
there. The rebuild is not the dominant cost it was expected to be.

Reproduce:

```bash
python3 bench/bench_overlap_gate.py --tag <date>-overlap-gate \
    --drafts content/drafts/books/<book-slug>
```

The labels are an input, hand-authored and committed as
`results/<date>-overlap-gate/labels.json`; the script reports any
gateable finding it cannot find a label for. The detector check above is
a one-off, not a bench tool: copy the two `bench/fixtures/`
cloud-computing drafts under `content/drafts/` and scan each.

## 2026-08-13b: does a gram's corpus document frequency separate boilerplate from reuse?

Run: `bench/bench_overlap_df.py`, record in
`results/2026-08-13-overlap-df/overlap_df.json`. Same corpus as the
section above -- 497 documents, 6,534,874 distinct 8-grams, corpus key
`25e79db2...`, tokenizer version 2, docling backend.

[The section above](#2026-08-13-what-an-overlap_gate-would-block-and-how-much-of-it-would-be-wrong-130)
ends on an unfinished observation. Having shown that span length does not
separate the two populations, it notes that one feature partly does --
"the two large false-positive clusters are each matched by **4 distinct
citekeys** ... where the planted true positive matches exactly **1**" --
and then bounds it: "It explains 8 of the 14, and no more."

That count is at *finding* granularity: how many citekeys produced a
finding for this passage. The same idea measured one level down -- for
every 8-gram in the run, how many distinct corpus documents contain it,
read straight off `overlap_index.postings_for_gram` -- explains **12 of
the 14**. Nothing new is stored to get there. Document frequency is a
projection of the index #110 already built.

### The statistic, and two artefacts that force the choice

The number reported per finding is the **median** DF over the run's
8-grams. Not the minimum, for a reason that is measurable in the table
below: a gap-merged run contains draft grams present in no source at all,
and a run reconstructed across a source page break (#131) has one window
straddling the join that matches nothing. Both put a 0 or a 1 into a
profile whose every other gram sits at 4. `f0f4fd3982b7` is the visible
case -- min 0, median 1, max 1 -- and a minimum-based rule would read that
artefact as evidence.

A second trap is worth recording because it fails silently. The grams
must be read off the finding's `fragment`, never its `draft_text`:
`fragment` is the normalised, space-joined word stream the index is keyed
on, and `draft_text` is the draft as written, newlines and hyphenation
intact. Hashing `draft_text` returns an all-zero profile that reads
exactly like "this run appears in no corpus paper" -- for a run that
demonstrably matched one. `bench_overlap_df.py::self_check` asserts
against that shape on every invocation.

### What DF suppresses, and what it costs

`median_df >= D`, over the 14 gateable findings, with the planted
`aguzzi_cloud_2020` lift as the recall arm:

```
  D  suppressed   fp  unlab  remaining  tp_lost  of_tp
  1          14   14      0          0        1      1
  2          12   12      0          2        0      1
  3          11   11      0          3        0      1
  4           8    8      0          6        0      1
  5           0    0      0         14        0      1
```

`D = 1` is degenerate -- every matched gram is in at least one document
by construction -- and is swept to show that end rather than to start
after it. `D = 4` reproduces the earlier section's 8 exactly, which is
the arithmetic check that the two measurements are the same feature at
two granularities.

**The recall arm is one finding.** "0 of 1 true positive lost" is the
truthful phrasing of the `tp_lost` column and the only one this data
supports; it is not a false-negative rate. The book contains no genuine
uncredited reuse, which is why the control fixture exists at all -- over
the book alone every row above would report a flawless rule.

### DF measures what the labeller was seeing

Grouped by the hand-authored class from the section above:

| Class | Findings | median DF |
|---|---|---|
| `canonical-definition` | 4 | 3-4 |
| `third-party-echo` | 9 | 1-4 |
| `attributed-quotation` | 3 | 1 |

The first two classes are the ones whose rationale is "many corpus papers
reproduce this", and DF finds them. The third sits at exactly 1 and DF is
blind to it -- correctly, since an attributed quotation *is* verbatim from
a single source. That population is already exempt from #130's predicate
through `quoted and cites_source`, so the two mechanisms cover disjoint
classes rather than competing.

### What this does not measure

- **A threshold.** The evidence supports "DF is the discriminating
  feature, at gram granularity" and does not support shipping a specific
  `D`. As with `_CPUS_PER_DOCLING_WORKER` in
  [PARALLELISM.md](../docs/PARALLELISM.md#-roadmap), the target is a
  region, measured on one corpus and one book.
- **Recall, at any useful sample size.** One true positive, planted.
- **Paraphrase.** Unchanged from the section above and still the largest
  caveat: DF is computed over exact-tier findings, so a rule built on it
  inherits that tier's blindness.
- **Stability under corpus change.** `index.json`'s key is a sha256 over
  every document's own change-detection key, so every DF here moves when
  a paper is added or re-parsed. A DF-based suppression is deterministic
  *given a corpus state* -- weaker than `chitragupta.draft gate`'s guarantee, and
  the same shape as #128's per-host allowlist. #130 is where that is
  priced.
- **Whether DF beats the hand allowlist.** #128's candidate allowlist
  suppresses 13 of the 16 by hand; `D = 2` suppresses 12 of the 14
  gateable ones mechanically. The two sets are not compared here.

The book scanned is the one restored from
`content/backup/content-20260809.zip`. That tree differs from the one the
gate record above was written against only below the 15-word floor -- 160
findings against 159, with the churn confined to `short` severity. The
16-finding labelled population and its ids are identical, and the record
reports `unlabelled: 0`, so both sections score against the same ground
truth.

Reproduce:

```bash
python3 bench/bench_overlap_df.py --tag <date>-overlap-df \
    --drafts content/drafts/books/<book-slug>
```

Labels are shared with `bench_overlap_gate.py` rather than duplicated --
the same findings, the same hand-authored file.

## 2026-08-13: does the skip-gram tier (#133) catch what the exact tier misses?

Discussion #115 and docs/PLAGIARISM-DESIGN.md call for "start advisory, promote
with evidence" before the skip-gram tier is trusted with anything. This
is the first evidence, and only the easier half of it.

### Capability arm: synthetic every-Nth-word paraphrase

`bench_overlap_skipgram.py` swaps a synonym at a fixed stride across a
28-word source sentence and checks whether the skip-gram tier (`n=5`
stemmed content words) still matches it against the unedited source, at
strides 2 through 14:

```
stride  caught
     2     yes
     4     yes
     6     yes
     8     yes
    10     yes
    12     yes
    14     yes
```

Every even stride is caught, matching the design: an even-stride
substitution always lands on one fixed original-index parity (odd
indices for these strides, since each is `stride - 1` and `stride` is
even), so the untouched family's skip-grams survive intact regardless of
how sparse or dense the substitutions are. `self_check()` confirms the
sweep is not vacuously "caught everything": swapping *every* word
(stride 1) is asserted to fail, since neither family survives that.

This is the same property `tests/test_overlap_skipgram.py::TestGradedParaphraseDetection`
and `tests/test_feature_workflows.py::TestVerbatimScanEndToEnd::test_lightly_paraphrased_run_is_reported_by_the_skipgram_tier`
pin as tests -- this run is the sweep across strides rather than four
fixed cases, kept here as the reproducible record.

### Precision arm: not run

**Superseded 2026-08-14.** It was run once a corpus was synced, and what
it found is in
[the #180 section](#2026-08-14-tier-2s-first-real-precision-number-and-the-two-bugs-that-had-to-be-fixed-to-get-it-180).
The paragraph below stands as the caveat that turned out to be
warranted, not as a current statement of what is unmeasured.

The harder and more important question -- how many false positives the
skip-gram tier produces on real, organic prose, the same measurement
[2026-08-13's overlap-gate section](#2026-08-13-what-an-overlap_gate-would-block-and-how-much-of-it-would-be-wrong-130)
made for the exact tier -- **was not measured**. This environment has no
`papers/` and no synced `content/ledger.sqlite`, so `bench_overlap_skipgram.py --drafts`
was never run. Do not read the clean capability sweep above as evidence
about precision: a tier that never misses a synthetic word-swap can
still flag every shared canonical definition in a real corpus, the same
way the exact tier did before References masking was fixed.

**What this does not measure**, beyond the precision arm above: embedding-
level paraphrase (tier 3, #134, unbuilt) -- restatement in genuinely new
sentence structure rather than a word-for-word swap. See docs/PLAGIARISM-DESIGN.md.

Nor is **cold-build cost** measured. `scan` now builds two corpus
indices instead of one, and `overlap_skipgram.stem()` runs pure-Python
Porter stemming over every content word in every document. Tier 1's
cold build is a measured 26.8s/497 docs (see
["2026-08-13: what an overlap_gate would block"](#2026-08-13-what-an-overlap_gate-would-block-and-how-much-of-it-would-be-wrong-130));
tier 2's is unknown and plausibly a multiple of it, since stemming has
no C-extension equivalent to tier 1's hashing here. `bench_overlap.py`
is the natural place to extend with a tier-2 timing arm later -- not
done here, so the number stays absent rather than guessed.

Reproduce:

```bash
python3 bench/bench_overlap_skipgram.py --tag <date>-skipgram-capability

# Once a corpus is synced, the arm this section could not run:
python3 bench/bench_overlap_skipgram.py --tag <date>-skipgram \
    --drafts content/drafts/books/<book-slug>
```

The capability sweep's raw output is committed at
`results/2026-08-13-skipgram-capability/skipgram_capability.json`.

## 2026-08-14: tier 2's first real precision number, and the two bugs that had to be fixed to get it (#180)

The arm the section above could not run, run -- and it does not read as
a precision measurement of the design. Two mechanical defects accounted
for **163 of the 190 raw findings** the first real-corpus run produced,
and neither is tier 2's word-swap tolerance doing its job badly.

Same host, same corpus as the [DF section](#2026-08-13b-does-a-grams-corpus-document-frequency-separate-boilerplate-from-reuse):
642 ledger items, 497 parsed, docling backend, and the same 15-chapter
digital-twins book. Tier 2 at `n=5`, `min_run` at tier 1's default 8.

### What the raw run reported, and what was wrong with it

```
             findings   what they were
raw               190
  duplicates       65   the same (citekey, page, fragment) emitted again
unique            125
  numeric          98   two unrelated numeric tables colliding by chance
surviving          27
```

**Duplicate emission.** `_skipgram_tier_findings` groups postings by
`(citekey, diagonal)`, but a finding's id is `sha256(citekey, page,
fragment)` -- no diagonal in it. A source table whose values repeat puts
the *same* draft window at several `src_pos`, so it lands in several
diagonal groups, each of which merges to the same draft span against the
same source page. One id, appended once per group. The worst single
finding was emitted **15 times**. This also inflated this benchmark's
own arithmetic: `precision_run` sums labels over the raw list, so a
duplicated finding's label counted once per copy.

**Numeric chance collision.** `stem_filter` keeps a purely numeric token
unstemmed, on the reasoning that a shared figure is still shared
wording. That is right about "48.2 billion" and wrong about a bare `2`:
with the digits 0-9 an effective ~10-token vocabulary, and this tier
tolerating a substitution in the opposite family by construction, two
long enough numeric tables share a window by chance. The population was
concentrated exactly where that predicts -- the book's own worked
arithmetic against page-number runs in spec PDFs, a systematic-review
scoring grid repeating `0/0.5/1/1.5/2/2.5/3` down its rows
(`karabey_aksakalli_deployment_2021`, 32 raw findings of its own), and a
requirement-coverage matrix of small counts
(`muller_reconfiguration_2023`, 24). Both citekeys have **no** surviving
finding after the fix.

Fixed by requiring fewer than half of a skip-gram window's stems to be
bare numbers (`overlap_skipgram.MAX_NUMERIC_SHARE`), which is a rule
about a window's company rather than about a token -- `[a-z0-9]+`
tokenization splits `48.2` into `48` and `2`, so no token-level test can
tell one from the other in the first place.

### Precision on what survives: 2 of 27

```
skip-gram findings: 27  tp: 2  fp: 25  precision: 0.0741
```

Hand-labelled in `results/2026-08-14-skipgram-precision/labels.json`,
against the same rubric as
[the gate section's labels](#2026-08-13-what-an-overlap_gate-would-block-and-how-much-of-it-would-be-wrong-130):
`tp` is reuse a reviewer would require fixing. The 25 false positives
fall into three classes, two of them already named by that section:

| Class | n | |
|---|---|---|
| `third-party-echo` | 10 | The NASA "integrated multiphysics, multiscale, probabilistic simulation" definition and ISO 23247's "fit-for-purpose digital representation", each matched against every corpus paper that reproduces it |
| `stock-phrase-echo` | 12 | The field's ordinary phrasing in its ordinary order -- one draft sentence about predictive-maintenance literature reviews matched **nine** different papers on five stemmed content words |
| `attributed-quotation` | 3 | Quoted and cited. `quoted` read false on all three at the time of this run, because the skip-gram window straddles the opening quote mark -- a real gap in the flag, not in the labelling. Fixed in #189: `quoted` now reads the quote spans as overlap rather than containment, and all three demote to the `quoted` bucket. The `tp`/`fp` labels and the precision figure above are unaffected |

**The finding that matters is about the two true positives.** Both are
passages where the draft reproduces a source's wording without quote
marks while citing it, and **the exact tier already reports both**, at
14 and 11 matched words against tier 2's 5 and 6. So on this book tier 2
found nothing tier 1 had not already found. `scan_findings` drops a
skip-gram finding only when an exact finding fully *contains* it, and
neither of these is contained -- the skip-gram window starts a word or
two earlier -- which is why they survive as separate rows.

That is not evidence tier 2 cannot work; it is one book, whose reuse
happens to be verbatim rather than paraphrased, and a tier built for
paraphrase has nothing to catch there. It is evidence that **the bar
discussion #115 sets -- "promote with evidence" -- has not been met**,
and tier 2 stays advisory. The measurement that would move it is a draft
with known light-paraphrase reuse in it, which this corpus does not
contain.

### By-product: cold and warm cost

Not the timing arm ["the section above"](#2026-08-13-does-the-skip-gram-tier-133-catch-what-the-exact-tier-misses)
asks for, and not comparable to tier 1's isolated 26.8s, since `scan`
builds *both* corpus indices: **68s cold** (497 documents fingerprinted
for both tiers, plus the 15-chapter scan) and **6.5s warm**, on the same
host under other load. Read it as an upper bound on the pair, not as
tier 2's own number.

Reproduce:

```bash
python3 bench/bench_overlap_skipgram.py --tag 2026-08-14-skipgram-precision \
    --drafts content/drafts/books/<book-slug>
```

The pre-fix run is committed alongside it at
`results/2026-08-14-skipgram-precision-before/skipgram_precision.json`
-- 190 rows, unlabelled, kept so the 190 -> 125 -> 27 arithmetic above
can be re-derived rather than taken on trust. Reproducing *it* needs the
parent commit, since the fixes are in `chitragupta/`.

## 2026-08-14b: `chitragupta.draft style` on a real 178k-word book, and the four bugs measuring it exposed (#107)

Payload: `results/2026-08-14-style-precision/style_precision.json`.
Corpus: the fifteen chapters of
`content/drafts/books/digital-twins-for-software-engineers` plus its table
of contents -- **178,511 words**, all sixteen files passing the citation
gate. Vale 3.9.1, rules as vendored at `assets/vale/`.

This is the run the plan on #107 promised before the checker shipped, and
it is the reason four things in `assets/vale/` are the way they are. Every
one was found by running against real drafts rather than fixtures.

### The dialect signal is decisive, which is the result that matters

| Checked as | Findings |
|---|---|
| `en-GB` | **5** |
| `en-US` | **400** |

An 80:1 ratio over 178k words. The book is en-GB and the checker says so
without being told -- none of the fifteen dossiers carries a `language:`
line, since all of them predate 5.12.0. That ratio is the evidence that
the rules and the exemptions are both working: a checker with sloppy
exemptions would report a few hundred either way.

### What it reports when no dialect is recorded

| Rule | Occurrences | Distinct |
|---|---|---|
| `Acronyms` | 337 | 101 |
| `Just` | 33 | 15 |
| `DefectMarkers` | 24 | 7 |

**`DefectMarkers` at 24 over 178k words is the headline for §2**: the
drafting skills are already honouring it. Zero uses of "obviously",
"simply" or "of course" in the whole book; the 24 are "clearly" twice and
"easy" the rest.

**`Acronyms` is noisy and is shipped at `suggestion` for that reason.**
101 distinct acronyms in a technical book, most of them domain vocabulary
(`FMI`, `FMU`, `OPC`, `AAS`, `MODBUS`) that the reader of *this* book
knows. The rule cannot tell those from a genuinely unexplained one without
the author's own vocabulary, which is #190. Until that lands, this rule is
a prompt rather than a finding, and the count above is what "noisy" means
in numbers.

### The four bugs this run exposed

1. **Collapsing was not optional.** "AI" appears 45 times unexpanded in
   one chapter. 337 occurrences reduce to 101 distinct findings; without
   that, the report is not read to the end.
2. **The references heading is not `## References`.** It is
   `## 3.13 References` -- a dotted section number. The exemption regex
   written from the docs matched neither, so the first run reported five
   dialect findings that were all cited paper titles. Fixing the pattern
   took `DialectGB` from 5 false positives to 0 on chapter 3.
3. **`[formats] tex = md` is load-bearing.** Without it Vale scans a
   `.tex` fragment as plain text and applies no `BlockIgnores` at all,
   reporting every word inside a `verbatim` block.
4. **Vale splits `BlockIgnores` on commas**, so `\n{2,}` fails to parse
   and Vale refuses to start. It has to be written `\n\n+`.

Bugs 2-4 are each pinned by a test in
`tests/test_style_assets_match_the_standard.py`, because all three fail
*silently* -- as zero findings, which reads as a clean draft.

### Reproducing

```bash
python -m chitragupta.draft style --json \
  content/drafts/books/digital-twins-for-software-engineers/*.md
```

The dialect columns need the rules selected by hand, since the restored
dossiers record no `language:`:

```bash
vale --config=assets/vale/vale.ini --no-exit --output=line \
  --filter='.Name != "chitragupta.DialectUS" and .Name != "chitragupta.DialectIN"' \
  content/drafts/books/digital-twins-for-software-engineers/*.md
```

The book is restored from a content backup and is gitignored, so this run
is not reproducible from a fresh clone. That is the same limitation every
corpus-dependent entry in this file has.

## 2026-08-15: does the embedding tier (#134/#164) catch what neither deterministic tier can?

The question tier 3 was built to answer, asked twice: once against a
graded fixture built from one real corpus claim, and once against the
same 15-chapter book every overlap section above uses.

**Read the two arms differently.** The capability arm is a controlled
ladder and its result is clean. The precision arm is a hand-labelled
count over one book, and this section states up front what it is *not*:
it is not the 59-candidate organic-paraphrase dataset #134's
implementation plan names as tier 3's calibration ground truth. That
dataset was produced in a session that never committed it -- the issue
comment says so at the time ("labels and raw results are local to this
session (not yet committed to a branch)") -- and it is not recoverable.
Every number below is measured against what does exist: four constructed
gradings, and the two organic pairs the plan names in prose
(`singh_digital_2023` in chapter 1, `frasheri_addressing_2023` in
chapter 5).

### The measurement the tier turns on: sentences are the wrong unit

Before any of the arms, the thing that decides whether an embedding tier
can work in this corpus at all. Take the one organic close-paraphrase
pair #134's own plan names as the acceptance check -- chapter 1
restating `singh_digital_2023`'s "save their Return on Investment (ROI)
while adapting to modern technologies with minimal risk" as "protecting
return on investment while adopting modern technology with minimal risk
and investment" -- and score it with `all-mpnet-base-v2`:

| Unit | Cosine, true pair | Cosine, unrelated sentences *of the same paper* |
|---|---|---|
| Whole sentence | **0.55** | 0.59, 0.59, 0.61 |
| ~20-word window | **0.71** | 0.40, 0.39, 0.37 |

At sentence granularity the true pair scores *below* the topical noise
of the very paper it restates, and no threshold recovers it. The cause
is framing: "A case study of a small-to-medium roll-to-roll
label-printing manufacturer reports ..." is half the draft sentence and
is pure topic, so it dominates the vector and every sentence in a paper
about that manufacturer looks equally close.

This is the concrete, sentence-level form of the warning the
[2026-08-13b document-frequency section](#2026-08-13b-does-a-grams-corpus-document-frequency-separate-boilerplate-from-reuse)
records at corpus level: in a single-field corpus, topical similarity is
high by default, so a detector has to compare something smaller than a
topic. It is why `chitragupta/overlap_segments.py` windows both sides, and it is
the single change without which none of the results below happen.

It is also why `chitragupta/overlap_embed.report` ranks rather than thresholds.
Even windowed, no cutoff separates the classes: in that same section of
chapter 1 the true pair's window scores 0.62 against the source sentence
it restates while the *opening clause of the same draft sentence* scores
0.74 against that paper's own description of its case study. Both are
that sentence leaning on that paper. A ranking puts the sentence at the
top of its section either way; a threshold has to choose, and there is
nothing to choose between.

### Capability arm: a graded ladder, four rungs

`bench/fixtures/graded-paraphrase-of-singh-offload-2022.md` restates one
real claim from `singh_offload_2022` four times, each in its own cited
section, at four distances from the original.

```
               grade  caught by
            Verbatim  exact
   Word substitution  embedding
    Light paraphrase  embedding
 Genuine restatement  embedding
```

Two things in that table are worth more than the "yes" column.

**Tier 2 catches nothing on this ladder, including the rung it was built
for.** The word-substitution grade swaps words in place -- exactly the
perturbation `chitragupta/overlap_skipgram.py`'s odd/even family split is
designed to tolerate -- and skip-gram misses it, because substituting
words also *moved* them (a six-word phrase became five). That is the
finding #134's 2026-08-14 comment reached by controlled ablation,
reproduced here as a committed fixture: the determining factor is not
how much wording changed, it is whether word *position* changed, and
real paraphrase moves words by nature.

**The verbatim rung is caught by tier 1 and not double-reported.** Tier
3 aligns it too, and `scan_findings` drops that alignment because an
exact-tier finding overlaps it. That is the check that replaced #134's
proposed low-lexical-overlap ceiling -- and the replacement is not
cosmetic. A ceiling at 0.55 threw away the **strongest alignment in the
whole fixture** (0.83, the word-substitution rung), which no
deterministic tier caught. A ceiling guesses that high wording overlap
implies another tier found it; the dedup checks.

### The two organic pairs, on the real book

The plan's own "single most important manual check": run `scan` on a
chapter with a known organic miss and confirm tier 3 catches what tiers
1 and 2 did not.

| Pair | Chapter | Reported by tier 3 |
|---|---|---|
| `singh_digital_2023` | 1 | yes, score 0.192 |
| `frasheri_addressing_2023` | 5 | yes, score 0.229 |

Both are close paraphrases of a *cited* source -- restated too closely,
not lifted from an uncredited paper -- which is the shape #134's hand
read found the organic candidates overwhelmingly take, and the only
shape tier 3 can see: it compares a section against the citekeys that
section's dossier records, so reuse from a source a section never cited
remains tier 1 and tier 2's business alone.

Neither would have been reported under a draft-wide top-N. Chapter 1's
`singh_digital_2023` alignment is the strongest in *its own section* and
nowhere near the strongest in the chapter, which is why
`SECTION_LIMIT` ranks per section: alignment scores are not comparable
across sections, because a section whose sources are written in the
draft's own register scores higher throughout than one whose sources are
equations and tables.

### Precision arm: the population, and why there is no precision number yet

Over the same 15-chapter book, with a dossier regenerated for each
chapter (`dossier sections --citekeys --write`, since the restored
dossiers predate the current `sections.md` heading convention):

| | |
|---|---|
| Embedding findings | 162, across 15 chapters and 93 distinct citekeys |
| Reporting cap | 1 alignment per section, 5 shortlisted sources per section |
| Severity mix | 151 `long`, 7 `short`, 4 `quoted` (measured before #189 changed how `quoted` is computed; re-run on the [2026-08-16 section](#2026-08-16-which-drop-in-embedding-model-does-tier-3-overlap-detection-see-the-most-with), same model and corpus, which found the current mix: 146/7/9) |
| `UNCITED SOURCE` | 8 of 162 |
| Alignment score | min 0.005, median 0.157, max 0.608 |
| Median span | 20 words |
| Allowlist suppressed | 0 |
| **Labelled** | **0 of 162** |

**Precision is `None`, and the tool says so itself** -- its integrity
check reports "162 of 162 embedding finding(s) are unlabelled" rather
than printing a ratio over an empty label set. This is the same state
[the 2026-08-13 skip-gram section](#2026-08-13-does-the-skip-gram-tier-133-catch-what-the-exact-tier-misses)
shipped in ("precision arm: not run"), for the same reason: labelling is
a hand read of every finding against its source, and it has not been
done for this population.

What *is* labelled is the two organic pairs above, both reported. Those
are two points, not a precision estimate, and nothing here should be
quoted as one.

**What labelling this population would settle**, and nothing else will:
whether the 151 `long` findings are close restatement worth a reviewer's
time or the tier re-detecting the pipeline's own retrieval step -- the
failure mode
[the document-frequency section](#2026-08-13b-does-a-grams-corpus-document-frequency-separate-boilerplate-from-reuse)
predicts for any similarity-based tier over a single-field corpus, and
the one dossier-scoping narrows rather than removes. Until that read
happens, tier 3 stays exactly where tier 2 is: advisory, on discussion
#115's "start advisory, promote with evidence" discipline, with the
evidence still owed.

### Reproducing

```bash
.venv-full/bin/python bench/bench_overlap_embed.py --fixture --tag 2026-08-15-embed

.venv-full/bin/python bench/bench_overlap_embed.py --tag 2026-08-15-embed \
  --drafts content/drafts/books/digital-twins-for-software-engineers
```

The capability arm needs the `enrich` group, a built `content/chroma/`
and the Docling sidecars, but not the book. The precision arm needs the
book, which is restored from a content backup and is gitignored -- the
same limitation every corpus-dependent entry in this file has. Both
arms stage the fixture under `content/drafts/bench-embed/` with a
generated dossier and remove it again afterwards, because tier 3 will
not scan a draft that has no dossier.

## 2026-08-15b: the recall question, asked by reading -- how much organic paraphrase does each tier see?

Every other overlap section in this file starts from what a tier
*found*. This one starts from what a reader *finds by reading* and asks
how much of it a tier saw. The two have opposite failure modes, and a
tier that reports nothing scores perfect precision on all of them.

**This re-derives, by a method that is now a committed script, what
#134's 2026-08-14 session produced by hand and did not commit.** That
session's `candidates.md` -- 59 candidates, named in #134's
implementation plan as tier 3's primary validation dataset -- existed
only in its own context. It is not recoverable, and the numbers below are
not it. They are a fresh derivation from the same book, and they are
smaller and differently biased; `bench/bench_paraphrase_hunt.py` is the
method, so the next person needing this does not start from nothing.

### Population, and the cap

| | |
|---|---|
| Citations in the 15 chapters | 866 |
| With a readable cited source, and a claim rather than a pointer | 825 |
| Skipped: further-reading pointers, bare citekey lists, unreadable source | 41 |
| Shortlisted at lexical support >= 0.5 | 128 |
| **Judged by reading** | **48** |

The 80 shortlisted but unjudged, and the 697 below the shortlist, are
not evidence of anything and are not counted below. The cap is a reading
budget, stated rather than applied silently.

### What the 48 turned out to be

| Judgment | n |
|---|---|
| **close paraphrase** of the cited source | **22** |
| `no-match` -- retrieval surfaced no corresponding passage, so nothing could be judged | 13 |
| `no` -- independent statement, or ordinary attribution of a finding | 8 |
| `quoted` -- borrowed wording inside quote marks, cited | 3 |
| `third-party-echo` -- shared wording belongs to a third party both cite (NASA's definition, the FMI standard) | 2 |

### Which tiers see the 22

| Caught by | n | share |
|---|---|---|
| `embedding` **alone** | **8** | 36% |
| `embedding` + `exact` | 5 | 23% |
| `exact` + `skip-gram` | 2 | 9% |
| `exact` alone | 1 | 5% |
| **nothing** | **6** | 27% |

**Tier 3 fires on 13 of 22, and is the only tier firing on 8.** Set that
against the same question asked before tier 3 existed: the 2026-08-14
hand read found skip-gram's unique contribution to be **2 of 59**, and
58% caught by neither tier. Both numbers move in the direction the tier
was built for -- the never-caught share falls from 58% to 27%, and the
new tier's unique contribution is an order of magnitude above the tier
it follows.

Cross-checking is at `(citekey, chapter)` granularity -- "did the scanner
find *something* for that citekey in that chapter" -- which is the
granularity the 2026-08-14 read used, so the two are comparable.

### The bias, and why 22 is a floor

Candidates are found by retrieving passages **within the cited document
only** -- the citekey already says which paper, so there is no
cross-document search and nothing here embeds anything. That is what
keeps the dataset independent of the tier it measures: build the
candidate list with the same similarity tier 3 uses and "tier 3 catches
N% of candidates" measures nothing.

The retrieval within that document is lexical, and that is the cost. For
a **genuine restatement** -- exactly the class tier 3 exists for -- the
top passages of the right paper may not include the one actually
restated, and the pair reads as `no-match` rather than as a candidate.
13 of 48 landed there. So 22 is a floor on the close paraphrase in these
48, the true share of `embedding`-only catches is probably higher rather
than lower, and no number here should be quoted as an estimate of how
much paraphrase the book contains.

### Reproducing

```bash
.venv-full/bin/python bench/bench_paraphrase_hunt.py --extract \
  --drafts content/drafts/books/digital-twins-for-software-engineers \
  --tag 2026-08-15-organic-paraphrase-hunt

# judge the pairs it writes, into labels.json, then:

.venv-full/bin/python bench/bench_paraphrase_hunt.py --crosscheck \
  --drafts content/drafts/books/digital-twins-for-software-engineers \
  --tag 2026-08-15-organic-paraphrase-hunt
```

The book is restored from `content/backup/`'s archive, which was written
by **chitragupta 3.12.0**. One thing has to be ported before any of this
runs: `sections.md` recorded section names as `1.1 / Subsection` paths
then and records the heading verbatim now, so every dossier needs
`python -m chitragupta.draft dossier sections <chapter> --citekeys --write`
first. Without it tier 3 matches no section and reports itself
unavailable -- correctly, but the run measures nothing. Everything else
in those dossiers reads unchanged, and `dossier status` confirms the
corpus digest still matches.

`candidates.md` -- the same 48 rows with the quoted draft/source pairs --
is written beside `labels.json` and is **not committed**: `bench/`'s
recorded-field rule keeps draft and source prose out of `bench/results/`,
and that file is nothing else. The script regenerates it.

## 2026-08-16: which drop-in embedding model does tier-3 overlap detection see the most with?

The two sections above measure tier 3 with one model,
`all-mpnet-base-v2`. `docs/CONFIG.md` documents three models as safe,
symmetric drop-ins for `embed_index.py`'s un-prefixed `encode()` call
(`all-MiniLM-L6-v2`, `all-mpnet-base-v2`, `multi-qa-mpnet-base-dot-v1`);
this asks whether the choice matters. `bench/bench_embed_model_compare.py`
drives `bench_overlap_embed.py` (capability + precision arms) and
`bench_paraphrase_hunt.py --crosscheck` (the 22-pair organic recall
question from 2026-08-15b) once per candidate, unmodified, via the
`EMBEDDING_MODEL` environment variable -- neither script is touched, this
is an orchestrator. SPECTER2 is not a candidate here: it embeds a whole
paper's title+abstract, and all four graded-ladder rungs below restate
the *same* paper's *same* claim, so there is nothing for it to
discriminate with (see the script's own docstring and the design spec's
Arm A section).

Host: as the sections above. `all-MiniLM-L6-v2` and `all-mpnet-base-v2`
already had a built `content/chroma/` collection on this host;
`multi-qa-mpnet-base-dot-v1` did not, so its run paid a fresh embed of
the whole corpus. Measured wall clock for the full three-model sweep,
`time`'d end to end: **29m10.838s** (398m3.689s user, 21m22.982s sys --
`torch`'s intra-op threading across the run). Read off each model's
output-directory timestamp, the three legs took roughly 4m37s
(MiniLM), 8m35s (mpnet-base), and 15m59s (multi-qa-mpnet, the one that
built a collection from scratch) -- so reproducing this on a host where
all three collections already exist should cost a small fraction of
29 minutes, not the whole figure.

### The comparison table

Printed by `main()`, and written to
`bench/results/2026-08-16-model-compare/comparison.json`:

| model | embedding findings | organic recall | grades caught |
|---|---|---|---|
| `sentence-transformers/all-MiniLM-L6-v2` | 157 | 11/22 | 4/4 |
| `sentence-transformers/all-mpnet-base-v2` | 162 | 13/22 | 4/4 |
| `sentence-transformers/multi-qa-mpnet-base-dot-v1` | 163 | 11/22 | 4/4 |

**All three candidates catch all four graded-ladder rungs**, and catch
them the same way: `Verbatim` by the exact tier, `Word substitution`/
`Light paraphrase`/`Genuine restatement` by the embedding tier, in every
one of the three per-model `embed_capability.json` records. The
2026-08-15 finding that tier 2 catches nothing on this ladder --
including the word-substitution rung it was built for -- and that the
verbatim rung is caught by tier 1 and correctly not double-reported by
tier 3, both hold for all three candidates, not only the shipped
default. Nothing about *which* embedding model runs changes what the
deterministic tiers see; that was never in question, but it is now
checked rather than assumed.

**`all-mpnet-base-v2` has the best organic recall of the three (13/22)
at a middling finding-volume cost (162, between MiniLM's 157 and
multi-qa-mpnet's 163).** That is a description of what was measured, not
a recommendation to change `EMBEDDING_MODEL`'s shipped default -- the
design spec is explicit that this benchmark produces a recommendation in
this file, not a config change, and one 15-chapter book is not enough
corpus to retire that constraint on.

### Precision arm: the same population question, three times

| model | findings | distinct citekeys | severity: long/short/quoted | `UNCITED SOURCE` | score min/median/max | median span |
|---|---|---|---|---|---|---|
| `all-MiniLM-L6-v2` | 157 | 88 | 142/7/8 | 13 | 0.000/0.165/0.569 | 20 |
| `all-mpnet-base-v2` | 162 | 93 | 146/7/9 | 8 | 0.005/0.157/0.608 | 20 |
| `multi-qa-mpnet-base-dot-v1` | 163 | 92 | 142/14/7 | 28 | 0.006/0.150/0.542 | 20 |

None of these three populations is hand-labelled -- `precision` is
`null` in every `embed_precision.json`, and each one's own integrity
check reports "N of N embedding finding(s) are unlabelled", same as
2026-08-15's baseline. **The `all-mpnet-base-v2` row above reproduces
that baseline run exactly** on every axis it reported -- 162 findings,
93 citekeys, score range 0.005-0.608, 8 `UNCITED SOURCE` -- confirming
the collection and the model are unchanged since. The one figure that
moved is the severity mix: 2026-08-15 reported 151 `long`/7 `short`/4
`quoted`, flagged at the time as measured before #189 changed how
`quoted` is computed, with "a re-run is needed to know the current mix".
This run is that re-run: **146 `long`/7 `short`/9 `quoted`** is the
current mix for `all-mpnet-base-v2`, and the open item 2026-08-15 left
is closed.

`multi-qa-mpnet-base-dot-v1` stands out on `UNCITED SOURCE` -- 28 of 163
(17%), against 8/162 (5%) for mpnet-base and 13/157 (8%) for MiniLM.
Whether that is the model surfacing genuine uncited reuse the other two
miss, or reporting weaker section-to-source alignment as `UNCITED
SOURCE` more often, is exactly the question labelling would answer and
this run does not.

### Organic recall: the same 22 pairs, three models

The 22 close-paraphrase pairs are 2026-08-15b's judged-by-reading
ground truth, copied per model (`ORGANIC_LABELS`) before each
`--crosscheck` run so one model's tier assignments never overwrite
another's.

**10 of the 22 pairs are caught by all three models**, regardless of
which one runs. Each model also catches a small number the other two
miss entirely:

| Model | Unique catch (not seen by either other model) |
|---|---|
| `all-MiniLM-L6-v2` | `mertens_continuous_2024` (chapter 14) |
| `all-mpnet-base-v2` | `hugues_twinops_2022` (ch. 6), `esterle_autonomous_2024-1` (ch. 2), `rasheed_digital_2020` (ch. 4) |
| `multi-qa-mpnet-base-dot-v1` | `alskaif_evolution_2025` (ch. 1) |

10 common + each model's unique catches accounts for all three
totals (10+1=11, 10+3=13, 10+1=11). `all-mpnet-base-v2`'s 3 unique
catches is why its 13/22 leads the other two, not a difference in the
shared 10.

### What this does not measure

- **Precision.** `embedding_findings` (157/162/163) is a volume proxy,
  not `tp`/`fp` -- none of the three models' 482 combined findings are
  hand-labelled, and that labelling is out of scope here, same as the
  2026-08-15 baseline it extends. A model that reports more findings is
  not shown to be more *right*; it is shown to fire on more sections.
- **A recommendation to change the default.** See above: the design
  spec scopes this benchmark to a recommendation recorded in this file,
  not a `config.toml.example`/`chitragupta/config.py` change.
- **`EMBEDDING_MODEL`'s other consumers.** Only the overlap-scan path
  (`embed_index.py`'s symmetric, un-prefixed `encode()`, feeding
  `overlap_embed.py`) is exercised. `chitragupta/enrich/topic_model.py` reads
  the same setting for its own embedding cache; that path is untouched
  by this sweep. `chitragupta/retrieval.py`'s search is unaffected either way --
  it is BM25, not embedding-based.
- **A second corpus or a second book.** One 15-chapter book, one bib
  corpus, one host. Whether the ranking (mpnet-base > MiniLM ~
  multi-qa-mpnet on organic recall) holds on different prose is not
  tested.
- **Cost beyond the one-time embed.** The 29m10.838s figure is
  dominated by `multi-qa-mpnet-base-dot-v1` building a `content/chroma/`
  collection from nothing; a host that already has all three built would
  see mostly the capability- and precision-arm cost, not this total.

### Reproducing

```bash
.venv-full/bin/python bench/bench_embed_model_compare.py \
    --tag 2026-08-16-model-compare
```

Needs the `enrich` Poetry group (`chromadb`, `sentence-transformers`,
torch), the restored 15-chapter book under
`content/drafts/books/digital-twins-for-software-engineers` (gitignored,
from a content backup -- see 2026-08-15's reproduction note), and
`bench/results/2026-08-15-organic-paraphrase-hunt/labels.json` on disk
(`self_check()` refuses to run without it -- it is the hand-labelled
ground truth `bench_paraphrase_hunt.py --crosscheck` needs, and is
committed). Building a Chroma collection for a model that does not
already have one is the expensive part; budget the time this section
measured, not the "few minutes" a single fresh embed alone costs.

## 2026-08-16: retrieval and reranking, against real drafting judgments

Arm B of #194, and a different question than the section above. That
section asked which embedding model tier-3 *overlap detection* agrees
with most on a graded paraphrase ladder. This one asks which retrieval
configuration -- bare BM25, a dense drop-in alone, a dense drop-in
reranked by a cross-encoder, SPECTER2 standalone, or a SPECTER2-shortlist
cascade -- actually finds the citekey a real drafting session cited, for
a real query.

### The ground truth

`bench_retrieval_ground_truth.py` (Task 1) recovers 48 real `(query,
citekey)` pairs by joining `bench_paraphrase_hunt.py`'s committed
judgments (`bench/results/2026-08-15-organic-paraphrase-hunt/labels.json`)
back onto claim text freshly re-extracted from the restored 15-chapter
book -- the query is a real drafted sentence, the citekey is the real
paper it cites in the book. **All 48 of 48 labelled rows resolved** on
the `(chapter, line, citekey)` join, with zero unresolved ids. A second,
independent check went further than the join itself: `labels.json`'s
carried-over `lexical_support` field was cross-checked against the top
lexical score re-derived from a second fresh extraction, for all 48 rows
-- **0 mismatches**, confirming the recovered `query` text is the exact
text the judgments were made against, not merely a coordinate-matching
row.

All 48 rows are valid ground truth regardless of judgment -- judgment
describes how closely the claim restates the cited *passage*, which has
no bearing on whether the citekey is the paper that claim actually cites
(it is, in every row). The 48 break down as 22 `paraphrase`, 13
`no-match`, 8 `no`, 3 `quoted`, 2 `third-party-echo`.

### What ran, and what it cost

Host: as the sections above. All three drop-in models'
`content/chroma/` collections (40,741 chunks each) already existed --
built by Arm A's own sweep -- so this run needed no fresh whole-corpus
dense re-embed. The cascade's full-corpus SPECTER2 proximity-adapter
cache (one vector per ledger citekey, 642 of 642) was likewise already
fully populated, by Task 5's own cascade smoke test -- `embed_paper()`
computes vectors for every citekey it is asked about up front regardless
of how many ground-truth queries call it, so that smoke test's 3-row
sample paid the same full-corpus pass this real 48-query run would have
otherwise paid. Reusing both caches is the caching design's intended
job, not a shortcut taken for this write-up -- but it does mean this
run's wall clock **excludes** the cost a first-ever run on a fresh host
would pay for both. The SPECTER2 cache carries a real limitation worth
flagging here, too: `embed_paper()` keys it by citekey alone -- no model
id, adapter name, or text hash, unlike `build_index()`'s own
`text_hash`-keyed cache -- so it will keep serving a stale vector after
a re-parse or corpus re-sync changes a paper's title or recovered
abstract. A future reader relying on cache reuse should delete
`bench/results/specter2_paper_cache.json` by hand after either event,
not assume it is safe to keep.

Measured wall clock, `time`'d end to end:

```bash
time /workspace/.venv-full/bin/python bench/bench_retrieval_compare.py \
    --ground-truth bench/results/2026-08-16-retrieval-ground-truth/ground_truth.json \
    --tag 2026-08-16-retrieval-compare
```

**9m51.879s** (7m44.845s user, 0m42.657s sys) -- against Arm A's own
29m10.838s for its three-model sweep, cheaper as expected since nothing
here paid a from-scratch Chroma build. Read off each dense-worker
subprocess's output-file mtime: roughly 2m14s for `all-MiniLM-L6-v2`,
2m22s for `all-mpnet-base-v2`, 2m21s for `multi-qa-mpnet-base-dot-v1`
(each leg runs 48 queries through that model's own Chroma collection,
then reranks the pooled 50 hits with `cross-encoder/ms-marco-MiniLM-L6-v2`),
and the remaining ~2m40s split between the corpus-restricted SPECTER2
standalone row (fast -- its 41-citekey pool's vectors were already
cached) and the cascade leg (48 SPECTER2-shortlisted Chroma queries, each
reranked the same way).

### The comparison table

Printed by `main()`, and written to
`bench/results/2026-08-16-retrieval-compare/comparison.json`:

| row | n | recall@5 | nDCG@5 |
|---|---|---|---|
| BM25 (`chitragupta/retrieval.py`) | 48 | **0.7708** | **0.6641** |
| dense-only: `all-MiniLM-L6-v2` | 48 | 0.5208 | 0.4407 |
| dense+rerank: `all-MiniLM-L6-v2` | 48 | 0.5208 | 0.4420 |
| dense-only: `all-mpnet-base-v2` | 48 | 0.5417 | 0.4664 |
| dense+rerank: `all-mpnet-base-v2` | 48 | 0.6042 | 0.4918 |
| dense-only: `multi-qa-mpnet-base-dot-v1` | 48 | 0.5833 | 0.4956 |
| dense+rerank: `multi-qa-mpnet-base-dot-v1` | 48 | 0.6458 | 0.5467 |
| SPECTER2 (adhoc_query + proximity) | 48 | 0.4792 | 0.4132 |
| cascade: SPECTER2 shortlist(50) -> `multi-qa-mpnet-base-dot-v1` +rerank | 48 | 0.4375 | 0.3912 |

All nine rows scored all 48 of 48 ground-truth queries -- `n_missing` is
0 throughout `comparison.json`; no row's average is over a partial
population.

**Four different candidate-pool sizes sit under the same table columns,
and only BM25 ranks over the whole ledger.** BM25 ranks over all 642
ledger entries (`chitragupta/retrieval.py`'s corpus-wide index indexes every
item's title whether or not it has parsed text -- see
`embed_index.search()`'s own docstring: a bib entry whose PDF is missing
or failed to parse is searchable by title there even though it never
entered a Chroma collection). The three dense-only/dense+rerank rows
rank over the 40,741 chunks in the full Chroma collections, but those
chunks span only **497** distinct citekeys, not 642 -- the other 145
ledger entries have no parsed text to embed, so they were never
chunked. `specter2_row()` (Task 4's own documented, deliberate
simplification) ranks only the ground truth's own 41-citekey set (the
48 rows share some citekeys) -- roughly 12x fewer candidate papers than
the dense rows' 497, roughly 15.7x fewer than BM25's 642, trivially
easier to find the right answer in by construction. **The cascade is
narrower still**: `_cascade_worker()` restricts its Chroma query to
`where={"citekey": {"$in": shortlist}}`, so it searches at most the 50
papers SPECTER2's own shortlist selected -- a pool the same order of
size as SPECTER2 standalone's, not the 497-citekey pool the plain
dense/rerank rows see. That SPECTER2 standalone still loses to every
corpus-wide row despite its much smaller haystack is, if anything, a
stronger statement about it than the raw number alone conveys -- and
the cascade losing *worse*, on a comparably narrow pool that a stronger
paper-level pre-filter (SPECTER2, not chance) chose, only sharpens the
finding below: the pre-filter itself is where the cascade loses ground,
not the reranking after it.

### What this measures, stated plainly

**BM25 wins outright, by a real margin.** recall@5 0.7708 against the
best dense/rerank row's 0.6458 (+0.125), nDCG@5 0.6641 against 0.5467
(+0.1174). This is not a close call decided by rounding. It is exactly
the question [docs/RETRIEVAL.md](../docs/RETRIEVAL.md) already poses in
prose -- "On a small, vocabulary-consistent corpus, BM25 is usually
enough -- which is why it stays the default" -- now checked against 48
real judged queries on this repository's own corpus rather than asserted
from general reasoning. The measurement agrees with the prose. Nothing
in this run argues for changing `EMBEDDING_MODEL`'s default or for
routing retrieval through a dense/rerank/cascade path in place of BM25;
if anything, it is evidence that BM25 already is the right default *for
this corpus*, not a gap this benchmark's more elaborate rows needed to
close.

**Reranking is not a uniform win across the three dense models.** It
helps `multi-qa-mpnet-base-dot-v1` meaningfully (nDCG 0.4956 ->
0.5467, +0.0511) and `all-mpnet-base-v2` meaningfully (0.4664 -> 0.4918,
+0.0254), but is close to a wash for `all-MiniLM-L6-v2` (0.4407 ->
0.4420, +0.0013) -- within noise at n=48. The cross-encoder's value
tracks how good the first-pass pool already was, not a fixed uplift a
caller can assume applies to any dense model.

**`multi-qa-mpnet-base-dot-v1` is the best-performing dense/rerank
combination**, both alone (nDCG 0.4956, ahead of the other two
dense-only rows) and reranked (nDCG 0.5467, the best of any non-BM25
row). It is the one drop-in [docs/CONFIG.md](../docs/CONFIG.md) already
describes as "trained specifically on short-query-vs-long-passage
retrieval -- the closest match to what `search()` actually does"; this
run is the first real measurement that bears that description out
rather than asserting it.

**SPECTER2 standalone underperforms every dense drop-in** -- nDCG 0.4132,
below even the weakest dense-*only* row (`all-MiniLM-L6-v2` at 0.4407),
despite ranking over a pool of roughly 12x fewer candidate papers than
the dense rows' 497 (15.7x fewer than BM25's 642 -- see the
comparability note above). This is the mismatch
[docs/CONFIG.md](../docs/CONFIG.md)'s "Not without a code change first"
section already names: SPECTER2 answers "which papers are alike", not
"which chunk answers this query". But this run cannot cleanly isolate
that mechanism from a second, real confound it does not control for:
per the committed SPECTER2 paper cache
(`bench/results/specter2_paper_cache.json`), 510 of the 642 cached
papers (79%) were encoded title-only -- `abstract_for()` found no
"Abstract" section for them -- and within the 41-paper gold pool this
row actually ranks, 31 of 41 (76%) were likewise title-only. A model
whose document side is mostly a bare title cannot be expected to
distinguish "which chunk answers this query" even in principle, so this
run is real evidence that SPECTER2 underperforms on this corpus, not
clean evidence for *why*: the model-card mismatch and the title-only
coverage gap are both live explanations, and nothing here separates
them.

**The cascade underperforms its own base model, and is the single
worst-scoring row in the table.** `multi-qa-mpnet-base-dot-v1`'s own
dense+rerank row alone scores nDCG 0.5467; restricting that same model
to a SPECTER2 paper-level top-50 shortlist first *drops* it to 0.3912
(-0.1555 nDCG, -0.2083 recall@5) -- lower even than SPECTER2 standalone's
own 0.4132. The mechanism is a hard pre-filter: when the correct paper
does not land in SPECTER2's own top-50 for a query, no amount of
downstream Chroma search or cross-encoder reranking can recover it --
the answer was removed from contention before the winning model ever
saw it. Part of that pre-filter's cost is structural, not purely a
question of SPECTER2's ranking quality: `_cascade_worker()` builds its
shortlist by ranking all 642 ledger citekeys, but 145 of those have zero
chunks in any Chroma collection (no parsed text to embed), so in
expectation roughly 11 of every 50-paper shortlist are papers the
dense/rerank stage could return nothing for regardless of how SPECTER2
ranked them. "Cascading models" is the option #194
explicitly asked this benchmark to allow for; measured here, it does
not help. This is a real negative result, not a tuning miss to soften:
the shortlist stage's false negatives cost more than its shortlisting
saves.

**No change to `docs/CONFIG.md` follows from this run.** The brief
scoped a `docs/CONFIG.md` edit to whether SPECTER2's numbers are "worth
documenting as an option" -- they are not: SPECTER2 standalone loses to
every drop-in, and the cascade loses to the drop-in it shortlists for,
so nothing measured here contradicts or extends
`docs/CONFIG.md`'s existing "Not without a code change first" framing.
That section already correctly says SPECTER2 answers a different
question than this pipeline's retrieval needs; this run confirms that
by measurement rather than revising it.

### What this does not measure

- **Per-query cost of the cross-encoder and SPECTER2 stages, at this
  corpus's real query volume.** The wall-clock figures above are
  aggregate, over 48 queries at once; no row reports a per-query
  latency, and a caller weighing whether reranking is affordable in an
  interactive drafting session has no number here to check against.
- **The cascade's shortlist size was fixed at 50, not swept.** A larger
  shortlist would put more of the correct-paper false negatives back
  into contention -- at a proportionally larger per-query Chroma-query
  and rerank cost -- and might change whether the cascade's underlying
  mechanism (described above) still dominates at, say, 100 or 200. This
  run says nothing about where that trade-off turns around, only that
  50 loses badly.
- **A recommendation to change `EMBEDDING_MODEL`'s default.** BM25
  winning this comparison is not evidence to touch
  `config.toml.example`'s embedding-model setting -- `search()` (BM25)
  and `embed_index.search()` (dense) are two different code paths a
  caller chooses between; this benchmark did not touch which one any
  genre skill calls by default.
- **A second corpus or a second book.** One 15-chapter book, 48 queries
  drawn from real drafting sessions against it, one bib corpus, one
  host. Whether BM25's win margin holds on a larger or more
  vocabulary-diverse corpus -- the exact axis
  [docs/RETRIEVAL.md](../docs/RETRIEVAL.md) names as where embeddings
  earn their cost -- is not tested here.
- **A `BM25 + rerank` row.** No such row exists here -- not a scope
  deviation, the plan never asked for one -- but BM25 is the winning row
  and reranking measurably helps two of the three dense models, so
  whether reranking BM25's own top-K would beat everything in this table
  is a real, untested combination.
- **Precision beyond recall@5/nDCG@5.** Every row is scored only against
  whether the *known-cited* paper appears in the top 5; no row is
  checked for whether its other top-5 hits would have been reasonable
  citations too (a plausible substitute paper counted as a "miss" here
  the same as an irrelevant one).

### Reproducing

```bash
# Task 1: recover the 48-pair ground truth (needs the restored book;
# not committed -- see bench_retrieval_ground_truth.py's own docstring).
/workspace/.venv-full/bin/python bench/bench_retrieval_ground_truth.py \
    --drafts content/drafts/books/digital-twins-for-software-engineers \
    --tag 2026-08-16-retrieval-ground-truth

# Task 3: exercise the SPECTER2 encoder seam on its own (self_check()
# only -- embed_paper()/embed_query() are called by the sweep itself).
/workspace/.venv-full/bin/python bench/embed_models.py

# Task 6: the real sweep -- all nine rows, all 48 queries.
/workspace/.venv-full/bin/python bench/bench_retrieval_compare.py \
    --ground-truth bench/results/2026-08-16-retrieval-ground-truth/ground_truth.json \
    --tag 2026-08-16-retrieval-compare
```

Needs the `enrich` Poetry group (`chromadb`, `sentence-transformers`,
`transformers`, `adapters`, torch) and the restored 15-chapter book (see
2026-08-15's reproduction note for the restore step). A host with none
of the three Chroma collections built, and no SPECTER2 paper-vector
cache yet, should budget for Arm A's whole-corpus dense-embed cost
*and* one whole-corpus SPECTER2 `embed_paper()` pass on top of the
9m51.879s measured here -- this run paid neither, because both were
already built by earlier tasks in this same plan.

## 2026-08-16: retrieval quality against what a drafting session actually logged

The section above answers "which retrieval configuration finds the
citekey a real drafting session cited" from ground truth *reconstructed*
after the fact -- a claim's text re-extracted from the restored book,
joined back onto a committed judgment. This section asks the same
question a different way: from what `chitragupta.retrieval`/`embed_index`
actually *logged* while the session ran, no reconstruction, no
book-restore-and-rejoin risk. Same nine rows, same scoring
(`bench_retrieval_live_logs.py` imports `recall_at_k`/`ndcg_at_k`/
`collapse_to_citekeys`/`_venv_python` from `bench_retrieval_compare.py`
rather than reimplementing them), a different ground truth shape.

### The ground truth, and why it is coarser than the section above

Every restored chapter's `retrieval.md` logs the query text, the mode
(`search`/`evidence`), and how much the call asked for and got back --
never which citekeys a call returned. So there is no per-query
`(query, citekey)` pair available from these logs the way there was from
`bench_paraphrase_hunt.py`'s citation-claim extraction. What is
available: 96 real `search`-mode queries (`evidence`-mode excluded --
that mode fetches supporting text for a citekey the session already
chose, a different intent than "find the right paper"), each paired with
its *whole chapter's* real kept-citekey set from `evidence.md` -- 15 to
45 citekeys per chapter, median 26.

`evidence.md` turned out to use two different prose formats across this
book's 15 chapters -- a `| Citekey | Used for | Supporting content |`
table in 8, `## `citekey`` headings in the other 7 (an artefact of which
chitragupta version drafted which chapter; `docs/DRAFT-ITERATION.md`
documents the current heading convention, which only half the book
predates). Matching either structure directly is fragile against a third
format nobody has seen yet. Matching "a real citekey inside backticks,
validated against the live ledger" is not: every citekey in both formats
is backtick-quoted, and cross-checking each backtick token against
`content/ledger.sqlite`'s 642 real citekeys discards anything else that
happens to be backtick-quoted in the surrounding prose (a handful of
tokens per chapter, per a live count -- see `self_check()`'s own
assertion against chapter 9, independently reproducible).

### The comparison table

| row | recall@5 | nDCG@5 |
|---|---|---|
| BM25 (`chitragupta/retrieval.py`) | 0.8542 | **0.4707** |
| dense-only: `all-MiniLM-L6-v2` | 0.8125 | 0.3499 |
| dense+rerank: `all-MiniLM-L6-v2` | 0.7292 | 0.3132 |
| dense-only: `all-mpnet-base-v2` | 0.8125 | 0.3286 |
| dense+rerank: `all-mpnet-base-v2` | 0.8021 | 0.3357 |
| dense-only: `multi-qa-mpnet-base-dot-v1` | 0.6458 | 0.2818 |
| dense+rerank: `multi-qa-mpnet-base-dot-v1` | 0.6979 | 0.2982 |
| SPECTER2 (adhoc_query + proximity) | **0.8854** | 0.3411 |
| cascade: SPECTER2 shortlist(50) -> `all-mpnet-base-v2` +rerank | 0.8125 | 0.3235 |

All nine rows scored all 96 of 96 real queries -- `n_missing` is 0
throughout `bench/results/2026-08-16-retrieval-live-logs/comparison.json`.
The cascade's winning dense+rerank model this run is `all-mpnet-base-v2`
(nDCG 0.3357, the best of the three) -- **not**
`multi-qa-mpnet-base-dot-v1`, the winner in the section above. The two
ground truths do not agree on which drop-in model reranking helps most,
which the next section reads as a real finding, not noise to average
away.

### Why these nDCG numbers are not comparable to the section above's

**This is the one number in this section a reader must not carry across
sections.** `ndcg_at_k`'s ideal (`IDCG`) is `min(len(relevant), k)` --
the best score the top `k` results could possibly earn. The section
above's ground truth has exactly one relevant citekey per query, so
`IDCG = 1` always: the ideal top-5 is "the right paper, ranked first,
anything after it." This section's relevant sets run 15-45 citekeys, so
`min(len(relevant), 5) = 5` for every one of the 96 queries: the ideal
top-5 here is "five *different* relevant citekeys, all correctly
predicted" -- a structurally harder bar, at the same `k`. An nDCG of
0.47 here and 0.66 there are not "worse" and "better" versions of the
same measurement; they come from different IDCG denominators by
construction. **Only rankings within this table's own nine rows are
meaningful**, not a cross-section comparison of the raw numbers.

recall@5 is comparable in *direction* but not in *difficulty*: with 15-45
relevant citekeys instead of 1, hitting *something* in top-5 is
mechanically easier here, which is most of why every row's recall@5 is
higher in this table than in the section above's.

### What this measures, stated plainly

**BM25 still wins on nDCG@5** (0.4707, ahead of every other row), the
same qualitative finding as the section above, now checked against a
second, independently-constructed ground truth rather than resting on
one. That agreement is worth more than either number alone: two
different ways of asking "does BM25 find what a real session needed"
reach the same answer.

**SPECTER2 standalone has the best recall@5 (0.8854), and this reads
differently than the section above's SPECTER2 result.** There, SPECTER2
underperformed every dense drop-in. Here, at chapter-level relevance
with 15-45 correct answers per query, SPECTER2's paper-level
whole-document similarity is a good match for "is this chapter's general
topic represented among the top-5" -- exactly the granularity a
paper-to-paper model is built for, and exactly the granularity this
ground truth's coarseness rewards. Its nDCG@5 (0.3411) is still below
BM25's, so it is not finding the *right* paper first any better than
that -- it is finding *a* topically-relevant paper more reliably. The
two sections' SPECTER2 results are not in tension; they are answering
"is this a good match for this corpus's retrieval, at chunk granularity"
(no) and "is this a good match at chapter-topic granularity" (better
than expected) with the same model, honestly.

**Reranking is not uniformly helpful, and for one model it actively
hurts.** `all-MiniLM-L6-v2`'s dense+rerank row scores *worse* than
dense-only on both metrics (recall 0.8125 -> 0.7292, nDCG 0.3499 ->
0.3132) -- the cross-encoder's re-ordering of the pooled 50 hits made
this ground truth's outcome worse, not better, for this model.
`all-mpnet-base-v2` gains modestly (nDCG 0.3286 -> 0.3357); `multi-qa-
mpnet-base-dot-v1` gains more (0.2818 -> 0.2982) but stays the weakest
dense row either way. The section above found reranking "close to a wash"
for MiniLM and a real gain for the other two; this section finds an
actual regression for MiniLM. Read together: reranking's value is not a
fixed property of a model, it depends on what the first-pass pool
already contained for a *particular* query set, and a caller cannot
assume a cross-encoder is a free win without checking on their own
queries.

**The cascade is unremarkable here**, unlike the section above's
sharpest finding. At 0.8125/0.3235 it sits within the pack of dense rows
rather than being the single worst row -- the hard-pre-filter mechanism
the section above identified (a correct paper missing SPECTER2's top-50
costs more than the shortlist saves) still applies, but a 15-45-citekey
relevant set is far more forgiving of losing any *one* correct paper to
the pre-filter than a single-citekey relevant set is. This does not
contradict the section above; it is the same mechanism, diluted by a
coarser ground truth that has room to absorb it.

### What this does not measure

- **Per-query relevance finer than "this chapter's whole kept-citekey
  set."** `retrieval.md` genuinely does not log which citekeys a call
  returned, so there is no way to check, from these logs alone, whether
  a specific query's top-5 contained the citekey that query's own call
  was actually *for* -- only whether it contained something the chapter
  eventually kept. A finer signal would need instrumenting `log_retrieval`
  to record result citekeys going forward; nothing here does that
  retroactively.
- **`evidence`-mode queries.** Excluded by design (see above) -- a
  second, smaller comparison scoring those against the same chapter-level
  ground truth is possible from the same restored data and was not run.
- **A recommendation to change `EMBEDDING_MODEL`'s default, or to
  restructure `evidence.md`'s two coexisting formats.** Neither follows
  from this measurement.
- **A second corpus, or a second book.** Same limitation as every section
  above it.

### Reproducing

```bash
.venv-full/bin/python bench/bench_retrieval_live_logs.py \
    --tag <date>-retrieval-live-logs
```

Needs the restored 15-chapter book (dossiers included -- `evidence.md`/
`retrieval.md`, not just the drafts) and the same `enrich` group as the
section above. This run reused all three Chroma collections and the
SPECTER2 paper-vector cache Arm A and the section above already built;
a host with neither should budget the same first-run costs documented
there.

## 2026-08-21: how deep does this corpus divide, and what can say a paper is in two topics?

Two questions from #287's topic work, on the same 497-document corpus and
the same cached document vectors: how many topics the corpus divides into
at each clustering setting, and which mechanism can honestly report a
paper as belonging to more than one of them.

Scripts: `bench_topic_depth.py`, `bench_topic_membership.py`.
Raw output: `results/2026-08-21-topic-depth/depth.json`,
`results/2026-08-21-topic-membership/membership.json`.

### Depth: the hardcoded settings were a ceiling, not a default

Until 6.9.0 the clustering parameters were computed by a formula that
saturated at `n_docs >= 20` -- `min(15, n-1)`, `min(5, max(2, n-2))`,
`max(2, min(10, n//2))` -- so a 497-document corpus was clustered with
the values written for a 20-document one, and a 5000-document corpus
would have been too. It was written as a small-corpus *correctness* fix
(UMAP's spectral initialisation fails when `n_neighbors >= n_samples`)
and only ever scaled down.

| n_neighbors | n_components | min_cluster_size | min_samples | topics | outliers | median size | topics/doc |
|---|---|---|---|---|---|---|---|
| `15` | `5` | `10` | `-` | 5 | 12% | 34 | 1.15 |
| `15` | `5` | `5` | `-` | 29 | 30% | 9 | 1.97 |
| `15` | `5` | `3` | `-` | 51 | 26% | 6 | 1.78 |
| `10` | `5` | `10` | `-` | 16 | 28% | 21 | 1.70 |
| `10` | `5` | `5` | `-` | 30 | 27% | 12 | 1.98 |
| `10` | `5` | `3` | `-` | 51 | 18% | 7 | 1.59 |
| `10` | `5` | `3` | `2` | 76 | 17% | 4 | 1.64 |
| `5` | `5` | `5` | `3` | 46 | 12% | 8 | 1.63 |
| `5` | `5` | `3` | `2` | 83 | 9% | 5 | 1.37 |
| `5` | `10` | `3` | `2` | 83 | 9% | 5 | 1.56 |

**`min_cluster_size` is the dominant lever**, and the shipped default
moves from 10 to 3 with `min_samples = 2` (the `10 / 5 / 3 / 2` row: 76
topics).

**The outlier share falls as topics get finer** -- 28% at
`min_cluster_size = 10` against 17% at the new default and 9% at the
finest setting swept. That is the finding that makes the old values a
defect rather than a preference: the coarse setting was *both*
under-clustering and discarding more of the corpus. A reader expecting
the usual granularity/coverage trade-off should note it does not appear
in this range.

**The `15 / 5 / 10` row is unstable and should not be quoted.** It
reports 5 topics with a median size of 34 here; an earlier ad-hoc sweep
of the same setting on the same corpus gave 13 topics at 27% outliers.
Nothing in the script is random -- `random_state=42` throughout -- so the
difference is upstream: that sweep predated `content_text()`, which now
removes reference lists before embedding. The lesson is the one Asta's
survey states and this file has no other instance of: **a topic model
that looks settled at one setting can move a long way on a preprocessing
change**, and none of these numbers should be treated as properties of
the corpus alone. Stability across runs and settings is measured by
nothing here; see #300.

### Membership: only one mechanism agrees with the clustering it describes

`assignments` gives one topic per document because that is all
`fit_transform` returns. Five candidates for the many-to-many view, at 76
topics:

| mechanism | topics/doc | plural | top-share | agreement | is-top |
|---|---|---|---|---|---|
| `approximate_distribution` (BERTopic's own) | 35.45 | 94% | 0.03 | 100% | 95% |
| centroid cosine, centred, embedding space | 5.03 | 92% | **0.12** | 100% | 98% |
| centroid cosine, reduced space | 9.55 | 99% | 0.04 | 100% | 99% |
| Gaussian mixture over the reduced space | 1.00 | 0% | 1.00 | 0% | 0% |
| **HDBSCAN soft clustering (shipped)** | **1.64** | 25% | **0.58** | 100% | 98% |

**top-share** is the mean share of a document's total weight taken by its
strongest topic; the uniform baseline at 76 topics is **0.01**, and a
mechanism near it is not saying anything. `approximate_distribution`
(0.03) and the reduced-space centroid rule (0.04) are close to that
floor: they assign 35 and 10 topics per document at almost equal weight,
which is a dense matrix wearing the shape of an answer. The Gaussian
mixture fails the opposite way, returning hard assignments.

That leaves HDBSCAN's own soft clustering, shipped, and the centred
centroid rule -- **and the honest reading is that the shipped choice is
the more confident one, not the more useful one.** At 1.64 topics per
document with only 25% of papers plural, it under-reports the
many-to-many structure the corpus is known to have (637 of 642 papers
under 95 hand-made Zotero collections). The centred centroid rule reports
5.03 at 92% plural while staying an order of magnitude above the uniform
floor. Changing to it is #298.

### Two corrections this section exists to record

**The first version of `bench_topic_membership.py` scored the winning
mechanism at 1% agreement.** It indexed HDBSCAN's *cluster* ids with
BERTopic's *topic* ids, and BERTopic renumbers topics by size -- cluster 0
was topic 6 on this run. The script now recovers the mapping from the
documents, each of which carries both. A benchmark that silently compares
the wrong columns looks exactly like a real negative result.

**An earlier ad-hoc measurement put centroid agreement at 30-45%.** That
was taken at 7 topics on a seeded run and does not hold at 76, where
every non-degenerate mechanism agrees 100%. Agreement discriminates in
the first regime and not the second. Quote this table, not that figure.

### What this does not measure

- **Stability.** Nothing here runs the same setting twice, and the
  `15 / 5 / 10` discrepancy above shows the numbers move under changes
  elsewhere in the pipeline. Asta's survey calls repeated resampling and
  stability checking standard practice for exactly this reason (#300).
- **Whether the topics are any good.** Every figure is a shape statistic.
  No coherence score, no topic-diversity measure, and no human judging
  whether the topics are nameable -- which is the check that would have
  caught `werner kritzinger, fraunhofer austria` being a top-three topic.
- **A second corpus or host.** One corpus, one host, one embedding model
  (`all-mpnet-base-v2`), same limitation as every section above.


## 2026-08-21b: does a topic set reproduce, and what is a paper actually about?

Two follow-ups to the section above, on the same corpus: whether a
clustering setting is *stable*, and which mechanism should say a document
belongs to more than one topic. Scripts `bench_topic_depth.py --repeats`
and `bench_topic_membership.py`; raw output under
`results/2026-08-21-topic-stability/`.

### Stability: the old default was barely repeatable

`--repeats` refits each setting on 90% bootstrap resamples and scores
agreement with the full fit by adjusted Rand index over the
document-to-topic assignment. 1.0 is an identical partition, 0.0 is
chance. HDBSCAN is deterministic given identical input, so resampling
rather than re-running is what makes the number mean anything.

| n_neighbors | min_cluster_size | min_samples | topics | outliers | stability |
|---|---|---|---|---|---|
| 15 | 10 | -- | 5 | 12% | **0.14** |
| 15 | 5 | -- | 29 | 30% | 0.72 |
| 10 | 10 | -- | 16 | 28% | 0.26 |
| 10 | 3 | -- | 51 | 18% | 0.79 |
| 10 | 3 | 2 | 76 | 17% | 0.71 |
| 5 | 5 | 3 | 46 | 12% | 0.66 |
| **5** | **3** | **2** | **83** | **9%** | **0.80** |
| 5 (n_components 10) | 3 | 2 | 83 | 9% | 0.82 |

**The coarse settings are not merely coarse -- they are unstable.** The
values hardcoded until 6.9.0 (`15`/`10`) score **0.14**: their partition
of the corpus barely survives dropping a tenth of it. That is a third
independent argument against them, after the topic count and the outlier
share, and it is the one that no amount of reading their output would
have revealed. A five-topic answer looks decisive; this says it is close
to arbitrary.

`topic_neighbors` moves from 10 to 5 on this table, which is better on
all three axes at once: 83 topics against 76, 9% of the corpus discarded
against 17%, stability 0.80 against 0.71.

`n_components = 10` scores marginally better again (0.82) but is not
configurable, and one run's 0.02 is not enough to justify making it so.

### Membership: what a paper is about, versus where it landed

Five mechanisms at 76 topics. **top-share** is the mean share of a
document's weight taken by its strongest topic; the uniform baseline is
**0.01**, and a mechanism near it is saying nothing.

| mechanism | topics/doc | plural | top-share | agreement |
|---|---|---|---|---|
| `approximate_distribution` | 35.45 | 94% | 0.03 | 100% |
| **centroid cosine, centred (now shipped)** | **5.03** | **92%** | **0.12** | 100% |
| centroid cosine, reduced space | 9.55 | 99% | 0.04 | 100% |
| Gaussian mixture | 1.00 | 0% | 1.00 | 0% |
| HDBSCAN soft (shipped before #298) | 1.64 | 25% | 0.58 | 100% |

The shipped choice changed from the last row to the second. HDBSCAN soft
clustering is the most *confident* mechanism here and the least useful:
it answers "which density region does this point occupy", and for a core
point that is nearly binary. On a library where 637 of 642 papers carry
hand-made Zotero collection labels across 95 collections, reporting 1.64
topics per paper with 25% plural is describing a plural corpus as
singular.

In the shipped configuration -- ratio 0.5, cap 8 -- that becomes **4.64
topics per paper with 92% plural**, and 1,809 memberships the single
topic id discards. The cap moved from 3 to 8 because at 3 it, rather than
the similarity, was deciding: 387 of 497 documents sat at exactly 3.

### What this still does not measure

- **Whether the topics are any good.** Every figure here is a shape or
  agreement statistic. No coherence score, no topic-diversity measure,
  and no human judging whether the topics are nameable.
- **Stability across corpus states.** `--repeats` resamples one corpus at
  one moment. The 2026-08-21 section records a setting moving from 13
  topics to 5 when preprocessing changed upstream; nothing here would
  have caught that.
- **A second corpus or host.** One corpus, one host, one embedding model.

## 2026-08-16: retrieval quality with a ground truth no retrieval method built

The two sections above both score against citekeys that reached
`evidence.md` because a real drafting session's `retrieval.md` shows
only one retrieval tool in use -- `chitragupta.retrieval.search()` (BM25). A
paper dense retrieval or SPECTER2 would have surfaced but BM25 never
did was never shown to a human to judge, so it can never be scored as a
hit in either section above, independent of how good a citation it
would have been. Discussion #43's own follow-up comment names this
exactly: *"a retriever that finds what BM25 missed scores no better
without new judgements."* Both sections above inherited that bias
uncorrected.

This section sidesteps it rather than correcting for it after the fact.
The query for each of 256 bib entries is *that entry's own
author-assigned `keywords` field* (`bibliography.bib`, read via
`chitragupta.bib_reader.read_library()` -- the project's one sanctioned bib
parser; `keywords` is absent from `content/ledger.sqlite`, dropped by
the same "per-host noise" exclusion `chitragupta/ledger.py` applies to
`abstract`). The correct answer is the entry itself. No retrieval
method's search history decided that -- the paper's own author did,
once, independent of BM25, dense retrieval, SPECTER2, and the cascade
alike.

### The ground truth

285 of 646 bib entries carry a non-empty `keywords` field. Restricted to
the 256 that also have parsed text (`parsed_path IS NOT NULL` in the
ledger): dense retrieval and SPECTER2 structurally cannot find an
unparsed entry regardless of query quality, so including one would only
ever penalize those rows for a reason unrelated to what this section
measures. A real example, unmodified: entry `richstein_characterizing_2024`'s
query is its own keyword string, `"archetypes, design, digital twin,
structural health monitoring, structural mechanics, taxonomy,
lifecycle"`; the correct answer is `richstein_characterizing_2024`
itself. `self_check()` asserts this exact pair against the real ledger
before anything expensive runs, and separately asserts a *known
excluded* entry (`kapteyn_toward_nodate-1` -- has keywords, has no
parsed text) does not leak into the ground truth, since that filter is
the one this section's fairness argument rests on.

**One deliberate difference from the two sections above, made for the
same fairness reason the ground truth itself was chosen for:** this
section's `specter2_row()` ranks over the *whole* 642-entry ledger, not
just the ground truth's own citekeys the way the two sections above's
standalone SPECTER2 row does. `_cascade_worker()`'s shortlist stage was
already full-corpus in both earlier sections -- unchanged here -- so the
only thing this fixes is the standalone row's own pool size, to match
what BM25 and the cascade already search. Every row in this table
answers "did you find it among everything."

### The comparison table

| row | recall@5 | nDCG@5 |
|---|---|---|
| BM25 (`chitragupta/retrieval.py`) | **0.8047** | **0.7314** |
| dense-only: `all-MiniLM-L6-v2` | 0.6367 | 0.5186 |
| dense+rerank: `all-MiniLM-L6-v2` | 0.6406 | 0.5354 |
| dense-only: `all-mpnet-base-v2` | 0.6367 | 0.5069 |
| dense+rerank: `all-mpnet-base-v2` | 0.6641 | 0.5592 |
| dense-only: `multi-qa-mpnet-base-dot-v1` | 0.3359 | 0.2646 |
| dense+rerank: `multi-qa-mpnet-base-dot-v1` | 0.4375 | 0.3462 |
| SPECTER2 (adhoc_query + proximity, full corpus) | 0.5195 | 0.4201 |
| cascade: SPECTER2 shortlist(50) -> `all-mpnet-base-v2` +rerank | 0.7109 | 0.6037 |

All nine rows scored all 256 of 256 queries -- `n_missing` is 0
throughout `bench/results/2026-08-16-retrieval-keyword-selfretrieval/comparison.json`.
The cascade's winning dense+rerank model this run is `all-mpnet-base-v2`
again (nDCG 0.5592, ahead of the other two), the same winner the live-log
section found and a different one than the reconstructed-ground-truth
section's `multi-qa-mpnet-base-dot-v1`.

### What this measures, stated plainly

**BM25 wins outright, and this is the strongest evidence for it of the
three sections.** recall@5 0.8047 and nDCG@5 0.7314 are both the highest
of any row in any of the three retrieval-quality sections in this file --
against a ground truth built with no retrieval method's fingerprints on
it, at more than twice the sample size of either earlier section (256
against 48 or 96). Three independently-constructed ground truths --
reconstructed claims, live session logs, and now author keywords -- all
find the same winner. That agreement, not any single number, is the
finding.

**`multi-qa-mpnet-base-dot-v1` is the *worst* dense-only row here**
(recall 0.3359, nDCG 0.2646), a reversal from the
reconstructed-ground-truth section, where it was the *best* dense/rerank
combination. The likely reason is query shape, not corpus coverage: that
model is trained specifically for short-query-vs-long-passage retrieval
(`docs/CONFIG.md` names this explicitly), and a comma-joined keyword list
is neither a short natural question nor a passage -- it is closer to
what BM25's term-overlap scoring was built for than to anything either
dense objective was trained against. `all-mpnet-base-v2`, the
general-purpose model with no retrieval-specific training assumption
about query shape, is the strongest dense-only row here (0.5069) for
the same likely reason, read in reverse.

**The SPECTER2 cascade reverses from the worst row in both sections
above to the second-best row here, and this is the section's most
surprising result.** At 0.7109/0.6037 it beats every standalone
dense/rerank row and closes roughly two-thirds of the earlier
gap to BM25 (recall@5: 0.71 against BM25's 0.80, versus 0.44/0.38 in the
two sections above). The cascade's own code did not change between
sections -- `_cascade_worker()`'s shortlist was already full-corpus
before this section existed. What changed is the task: SPECTER2 is a
paper-level similarity model, and this section's ground truth is
literally "find the paper whose own topic these keywords describe" --
close to the question SPECTER2 was trained to answer, and closer than
either earlier section's "find the specific passage that supports this
claim/query" framing. Read together with the section above's finding
that a hard pre-filter's false negatives can cost more than the
shortlist saves: that mechanism has not gone away here (SPECTER2
standalone, at 0.5195/0.4201, is still well below BM25 and below the
cascade's own base model's reranked score), but the pre-filter is
choosing from a stronger starting ranking on a task SPECTER2 is
comparatively good at, so what it excludes costs less than what it
gets right. **This is a hypothesis, not something this run isolates
directly** -- nothing here separates "the pre-filter's ranking quality
improved" from "the base model's own dense/rerank result had more room
to be helped" as the dominant cause, and both are plausible from the
numbers alone.

**No change to `docs/CONFIG.md` or `EMBEDDING_MODEL`'s default follows
from this section either**, for the same reasons the two sections above
already give.

### What this does not measure

- **Why the cascade reverses here**, beyond the hypothesis above --
  isolating "better pre-filter ranking" from "more headroom in the base
  model's score" would need running the cascade at several shortlist
  sizes and reading where the curve bends, which this run does not do
  (the section above already names shortlist-size sweeping as untested).
- **The 285 - 256 = 29 keyword-bearing entries this section drops** for
  having no parsed text. Their existence is a real, separate finding
  about the corpus (not every well-catalogued entry has a readable PDF)
  that this section does not chase further.
- **Whether `keywords` fields are representative of what a real query
  looks like.** They are short, comma-joined technical phrases an author
  or a reference manager assigned -- closer to index terms than to
  anything a drafting session or a reader would type. That is exactly
  what makes them a fair, retrieval-method-independent ground truth; it
  does not make them a realistic query distribution, and this section's
  numbers should not be read as "how retrieval performs for a typical
  user", only as "which method finds a paper from its own declared
  topic terms."
- **A second corpus, or a second book.** Same limitation as every
  section above it.

### Reproducing

```bash
.venv-full/bin/python bench/bench_retrieval_keyword_selfretrieval.py \
    --tag <date>-retrieval-keyword-selfretrieval
```

Needs `bibliography.bib` (already required for anything in this
repository), the synced ledger, and the same `enrich` group and warm
Chroma/SPECTER2 caches as the two sections above. No book restore
needed -- this section's ground truth comes entirely from the
bibliography and the ledger, not from any drafted content.

## 2026-08-18b: what `--collection` (#195) buys a real drafting run -- the `Lifecycle` replication

A second run of the design in
`bench/results/2026-08-18-collection-scope/`, against a different shelf
and a different chapter. The first run used `DT Platforms` (28 items)
and a platforms chapter; this one uses **`Lifecycle` (19 items)** and a
chapter on digital twin life cycle considerations. Same genre skill
(`textbook-chapter-writer`), same reader, same eleven-section skeleton,
same ten pre-registered queries at `--k 15 --chars 500`, same corpus
snapshot of 642 items.

Pre-registration, hashes and measurements:
`bench/results/2026-08-18-collection-scope-lifecycle/`. Everything that
follows was fixed before either arm ran, except where the addendum in
that pre-registration says otherwise.

**Provenance note.** The first run's `bench_collection_scope.py` and its
`measurements.json` exist only as uncommitted files in the main working
tree, and its `preregistration.md` only in a third worktree; none of it
is in any commit. The script here is a **parameterised rewrite** of that
one (`--topic`, `--arm-f`, `--arm-c`, `--collection`, `--hashes`,
`--session`), not a second copy. If you are landing the first run's
files, reconcile against this rather than adding a duplicate.

### The two arms

| | Arm F | Arm C |
|---|---|---|
| Retrieval | whole corpus, 642 items | `--collection "Lifecycle"`, 19 items |
| Runs | **first** | second |
| Draft | `…-full-corpus.md` | `…-life-cycle-considerations.md` |

Arm F runs first deliberately. Both arms ran inline in one session with
no subagents, so the second arm re-sends the first arm's context on
every turn and is structurally more expensive whatever it does. Any Arm
C saving measured here is therefore a **lower bound**.

The `Lifecycle` shelf's size was taken through
`bib_collections.matches()`, not by tallying exact path strings:
matching is prefix-by-segment, so a subcollection would fold into the
denominator. There are none; 19 is both counts.

### What the filter does not change: the payload

| | Arm F | Arm C |
|---|---|---|
| Queries logged | 10 | 10 |
| Retrieval payload | 73,837 chars | 73,765 chars |

**A 0.1 % difference, and that is the expected result rather than a null
one.** At a fixed `--k` the filter still returns `k` results; they are
just drawn from a smaller pool. `--collection` changes *which* papers
arrive in the drafting context, not how many characters do. Anyone
hoping the flag will cut retrieval cost at fixed `k` should stop here.
The first run measured the same thing (73,657 vs 73,848), so this is now
replicated.

### What the filter does change: selection

| | Arm F | Arm C |
|---|---|---|
| Distinct citekeys surfaced | 102 | 17 |
| Cited | 21 | 13 |
| **Selection ratio** | **0.206** | **0.765** |
| **Rejection ratio** | **0.794** | **0.235** |
| Shelf coverage | -- | 17/19 = 0.895 |

Arm F read and discarded 81 papers to keep 21. Arm C discarded 4 to keep
13. That is the feature working: the human's curation did the first
filtering pass, and the drafting run did not have to pay for it again in
judgement.

**Two cautions, both pre-registered.** Arm C's surfaced count is capped
at 19 by construction, so the ratios are comparable and the raw counts
are not. And at 19 items with `--k 15`, two queries very nearly exhaust
the shelf -- 89.5 % of it was surfaced -- so Arm C's denominator is close
to fixed while Arm F's kept growing per query. The gap is real; its
*size* is partly an artefact of a small shelf, and it was larger in this
run (0.206 → 0.765) than in the 28-item one (0.114 → 0.650) in the
direction that shelf size predicts.

### Index cost: none, and now demonstrated rather than asserted

`content/retrieval_index.json` and `content/ledger.sqlite` were md5'd at
three checkpoints -- before Arm F, between the arms, after Arm C:

| | before Arm F | between arms | after Arm C |
|---|---|---|---|
| index md5 | `1f83e471…` | `1f83e471…` | `1f83e471…` |
| ledger md5 | `d8b244c7…` | `d8b244c7…` | `d8b244c7…` |

Byte-identical throughout, at 14,134,003 bytes. `search()` scores
corpus-wide and filters the ranking, so the cache is shared by
construction and the collection-filtered arm never rebuilds it. **The
filter's index cost is zero.** The same three hashes also establish the
precondition for the replay below -- an unmoved ledger -- which the first
run could only assert.

### The papers, both ways

**Cited by both arms (4):** `kamburjan_declarative_2024`,
`noauthor_digital_2023`, `picone_harmonizing_2025`,
`tekinerdogan_systems_2020`.

**Surfaced by both (9):** the four above plus their duplicate keys, and
`liu_review_2021`, `michael_model-driven_2025`, `shangguan_triple_2022`.

Only 4 of the 30 distinct papers cited across the two arms are common to
both. The two chapters are grounded in substantially different
literature despite an identical brief and identical queries.

**What the shelf cost Arm C.** Eleven of Arm F's citations are papers
the shelf does not contain, and their absence is visible in the draft:
`anwer_developing_2025` (BOL/MOL/EOL -- Arm C has no product-life-cycle
vocabulary at all), `fitzgerald_digital_2024-1` (ISO 15288 retirement),
`honcak_mbse_2024` (a DT V-model spanning conception to
decommissioning), `grieves_digital_2017`, `milligan_infrastructure_nodate`
and `shao_use_2021` (commissioning), `pfeiffer_modeling_2024`,
`human_design_2023`, `mertens_continuous_2024` and `lehner_towards_2021`
(evolution), `thelen_comprehensive_2022-1` (retirement as an
optimisation).

**What the shelf bought Arm C.** Eight papers Arm F's whole-corpus
queries never surfaced at all: `michael_model-driven_2025`'s two-track
life-cycle figure and its bounded-purpose twin -- the single best source
either arm found for this chapter's central claim --
`frasheri_addressing_2023`, `lugaresi_digital_2025`,
`dittler_agent-based_2022`, `lu_evoclinical_2023`, `xu_pretrain_2024`,
plus two off-topic ones (`liu_novel_2019`, `xu_traversing_2023`).

That is the finding worth carrying forward. **The curated shelf is not a
subset of what the whole-corpus search finds.** BM25 over 642 items
buried papers that BM25 over 19 items ranked first, because a small pool
promotes documents that a large pool's competition suppresses. The two
arms are not "thorough" versus "cheap"; they surface genuinely different
material, and each misses something the other finds.

### Tokens

Opus 5 throughout -- **no mid-arm `/model` switch**, checked per window
against the transcript rather than assumed. This is the confound that
made the first run's arm-level totals uninterpretable, and it is absent
here.

| Window | Turns | Output tokens | Input tokens |
|---|---|---|---|
| Setup (orientation + pre-registration, shared) | 36 | 22,738 | 2,407,689 |
| Arm F -- retrieval + first draft | 18 | 31,257 | 2,593,402 |
| Arm F -- rewrite + pipeline (**quarantined**) | 19 | 40,816 | 4,085,555 |
| Arm F -- total | 36 | 71,820 | 6,499,160 |
| Arm C -- retrieval + draft + pipeline | 12 | 30,205 | 3,374,722 |

**Arm F's total is not comparable to Arm C's, and is not offered as
such.** A steering change arrived mid-run (the book supplied as a
reference could no longer be used as a content source), and Arm F paid
for a complete rewrite that Arm C never paid, because Arm C was drafted
once against the corrected brief. That window is quarantined, exactly as
extra queries are reported separately rather than folded into the
pre-registered ten.

The closest honest comparison is the first Arm F window against Arm C's:
**18 turns and 31,257 output tokens for retrieval plus one draft, versus
12 turns and 30,205 output tokens for retrieval plus one draft plus the
whole closing pipeline** -- gate, references, three renders, style check
and verbatim scan. Arm C did more, wrote more (9,742 words against
9,055), and did it in a third fewer turns, while carrying Arm F's entire
context.

Normalised by words actually drafted, **Arm F spent 3,569 output tokens
per 1,000 words against Arm C's 3,101.**

Arm F's denominator is 20,123 words, and it is worth showing because it
is easy to get wrong. Arm F emitted sections 1--6 **three** times -- the
original, a version rewritten under the first and stricter reading of
the steering, and the final one -- and sections 7--11 once, patched in
place afterwards rather than re-emitted. So the count is 5,421 (first
sections 1--6) + 3,634 (sections 7--11) + 5,534 (the discarded rewrite,
**estimated** from the final pass, which is parallel in structure and
the only recoverable proxy -- that text was overwritten in place) +
5,534 (final sections 1--6). Summing the two *assemblies* instead would
double-count sections 7--11.

One caveat on the figure itself: neither window is pure drafting output.
Both include gate, references, three renders, style and verbatim work.
This is therefore an upper bound on what drafting 1,000 words costs, not
a clean measure of it -- the turn-and-output comparison above carries the
finding with less to qualify.

Input tokens are dominated by cache reads of the other arm's context and
are not a fair arm-to-arm comparison in either direction.

### Verbatim overlap

`python -m chitragupta.review verbatim scan --json`, same tiers both times.
**All three tiers ran, including the embedding tier** -- the first run
could not run it, so this is strictly better evidence.

| | Arm F | Arm C |
|---|---|---|
| Findings | 37 | 31 |
| exact / skip-gram / embedding | 19 / 8 / 10 | 15 / 3 / 13 |
| Longest run | 40 words | 69 words |
| Tiers not run | none | none |

Neither arm is clean, and neither result is alarming on inspection: most
are close paraphrase of a source the sentence cites by name in the same
clause. Not all -- `barbie_toward_2024` matches in both arms and is cited
by neither, which is a stock-phrase collision rather than reuse, and is
the kind of finding that shows why a scan is a review aid and not a
verdict. They are nonetheless real findings and both
drafts would benefit from an `overlap-reviser` pass; a clean scan would
not have been a clean bill of health either.

The tier mix differs in a way worth noting. Arm C's findings skew to the
embedding tier and include a 69-word run, against Arm F's 40 -- Arm C
tracked its smaller source set more closely, which is what a narrow
shelf and repeated exposure to the same fifteen documents would predict.

### Draft-vs-draft overlap -- the confound, measured

Reported as a clearly-labelled extra, because the plain reading of
"overlap in both cases" is each arm against the corpus, above.

Between the two drafts: **6,176 shared 8-word runs, Jaccard 0.483, and a
longest shared run of 487 words.**

The 487-word run is not boilerplate and it is not concealed reuse: it is
**section 7's whole-of-life cost arithmetic together with the exercise
solutions that complete it** -- engineer-day tables, a break-even
derivation and its worked answer. None of that content depends on the
corpus, so neither arm had any reason to invent a second version of it,
and both were written by one session to one pre-registered skeleton.

Read the other way, a high Jaccard is the experiment's control working
rather than leaking. The skeleton, reader, word budget and queries were
pre-registered as identical, so the *only* thing that should differ
between the two chapters is the citation-grounded material -- and heavy
overlap in the arithmetic, tables and exercises is exactly what that
design predicts. The material that does differ is precisely the material
the retrieval arm touched.

**This number says nothing about the collection filter.** It says that
two chapters written to one skeleton in one session are not independent
documents, and it is the reason the corpus-facing scans above, not this,
are the headline. Two independent sessions would be needed to measure
draft-to-draft similarity attributable to the retrieval arm, and that
experiment was not run.

### What replicated, and what is new

Replicated from the 28-item run:

- Retrieval payload is unchanged by the filter (0.1 % here, 0.3 % there).
- Index cost is zero -- now shown by three hashes rather than one.
- Selection ratio rises sharply under the filter (0.11 → 0.65 there,
  0.21 → 0.76 here).
- Shelf saturation: coverage 71 % there, 89 % here, with the smaller
  shelf saturating harder as predicted.

New here:

- **A word budget and a per-1k-words normalisation**, which the first run
  lacked -- without it "fewer output tokens" cannot be told apart from
  "shorter chapter".
- **A clean token comparison with the model held fixed**, which the
  first run could not offer.
- **The embedding tier ran**, so the overlap numbers cover restatement
  and not only verbatim reuse.
- **The asymmetry finding**: the curated shelf surfaced 8 papers the
  whole-corpus arm never saw. Curation is not only a filter; it is a
  re-ranking that promotes material a larger pool suppresses.

### What this section does not measure

- **A large collection.** 19 items saturates hard. A shelf in the
  hundreds would show a smaller selection-ratio gap.
- **Whether either chapter is *better*.** This measures retrieval and
  citation behaviour, not prose quality or teaching effectiveness. The
  shelf demonstrably cost Arm C the end-of-life literature and
  demonstrably bought it the two-clock figure; which trade a reader
  prefers is not a number here.
- **Independent arms.** One session, one skeleton -- see the
  draft-vs-draft figure above.
- **An Arm F that was drafted once.** The rewrite is quarantined rather
  than absent, and a clean single-draft Arm F would be a better control.
- **Generalisation.** Two collections, two chapters, one corpus
  snapshot, one host.
- **Per-section adherence to the word budget.** The budget was
  pre-registered per section and only the *totals* were checked against
  it. Both chapters came in short of the 10,000-word target -- Arm F at
  9,168 and Arm C at 9,742 -- and no section-by-section comparison was
  made.
- **Independent figures.** Both drafts `\input` the same two figure
  files from the shared topic directory, so revising a figure for one
  arm silently changes the other arm's render.

### Reproducing

```bash
python bench/bench_collection_scope.py \
    --topic book-chapters/digital-twin-life-cycle-considerations \
    --arm-f digital-twin-life-cycle-considerations-full-corpus \
    --arm-c digital-twin-life-cycle-considerations \
    --collection Lifecycle \
    --preregistration bench/results/2026-08-18-collection-scope-lifecycle/preregistration.md \
    --hashes bench/results/2026-08-18-collection-scope-lifecycle/hashes.jsonl \
    --session ~/.claude/projects/<slug>/<session-id>.jsonl \
    --steering-at 2026-08-18T20:53:33.949Z \
    --arm-f-discarded-words 9055 \
    --out bench/results/2026-08-18-collection-scope-lifecycle/measurements.json
```

Stdlib only, no venv, no lock -- reads `content/ledger.sqlite` and
`content/retrieval_index.json` read-only and replays each dossier's own
logged queries through `chitragupta.retrieval.search()`. `--session` and
`--steering-at` are optional; omit them and every non-token figure still
reproduces. The replay reproduces identically only while the ledger is
unmoved, which `--hashes` now checks and reports as `replay_sound`
rather than leaving to the reader.

## 2026-08-19: the same `--collection` question, with the arms actually isolated

The run above (`2026-08-18b`) wrote both arms **inline in one agent
session**, and its own draft-vs-draft figure convicted it: Jaccard
**0.483**, longest shared run **487 words**. I reported that as "the
control working". That was too generous. A 487-word contiguous shared
passage is contamination whatever the skeleton says, and two of the six
measurements — tokens and draft-vs-draft overlap — were measuring the
session rather than the retrieval scope.

This run fixes the process. Each arm is written by a **separate subagent
with an empty context window**, given the task specification and its own
retrieval scope and *nothing else*: no scope statement, no section
skeleton, no query list, no prose, and no knowledge that the other arm
exists. The two were dispatched **in parallel**.

Pre-registration, predictions, hashes, run notes and measurements:
`bench/results/2026-08-19-collection-scope-lifecycle-isolated/`.

### What had to be given up to get isolation

The previous run pre-registered a shared section skeleton and a shared
ten-query list, so the arms differed in exactly one variable. **That is
impossible here**, because handing both agents a skeleton and a query
list is precisely the context being eliminated. Each agent therefore
formulated its own queries — Arm F issued 14, Arm C 9 — and derived its
own structure.

So the two runs measure different things, and both are worth having:

- **2026-08-18b** — what the filter does to retrieval, holding the
  drafting plan constant. One variable, polluted process.
- **2026-08-19** — what the filter does to a *real drafting run*, plan
  included. Honest process, more than one variable.

**Retrieval payload totals are consequently not comparable in this run**
and must be read per query.

### The five pre-registered predictions, scored

| # | Prediction | Outcome |
|---|---|---|
| 1 | Draft-vs-draft Jaccard falls well below 0.483 | **Confirmed.** 0.483 → **0.0006**; longest shared run 487 → **17 words** |
| 2 | Payload stays near-parity *per query* | **Confirmed.** 7,400 chars/query (F) vs 7,375 (C) |
| 3 | Index cost stays zero | **Confirmed.** Three identical hashes, `replay_sound: true` |
| 4 | Arm C's selection ratio stays far above Arm F's | **Confirmed.** 0.305 vs 0.889 |
| 5 | Arm C surfaces papers Arm F does not | **Confirmed, and strengthened.** 10 papers, found with *different* queries than the run that first showed 8 |

Prediction 1 is the one that mattered: **the pollution was real, and it
was the session, not the design.** Two agents writing to no shared
skeleton produced essentially disjoint prose — 16 shared 8-grams out of
~11,600 and ~13,800.

### The numbers

| | Arm F (whole corpus) | Arm C (`Lifecycle`) |
|---|---|---|
| Queries issued | 14 | 9 |
| Retrieval payload | 103,603 chars | 66,372 chars |
| Payload per query | 7,400 | 7,375 |
| Words drafted | 11,529 | 13,558 |
| Distinct citekeys surfaced | 154 | 18 |
| Cited | 47 | 16 |
| **Selection / rejection** | **0.305 / 0.695** | **0.889 / 0.111** |
| Shelf coverage | — | 18/19 = 0.947 |
| Turns | 101 | 102 |
| Output tokens | 41,573 | 55,985 |
| Output tokens / 1k words | 3,606 | **4,129** |
| Verbatim findings | 21 (all embedding) | 19 (all embedding) |
| Longest verbatim run | 50 words | 62 words |
| Tiers not run | none | none |

**The token result reverses.** In the inline run Arm C looked cheaper
per 1,000 words (3,101 vs 3,569). With isolated pools it is **dearer**
(4,129 vs 3,606). The inline figure was an artefact: the collection arm
ran second and had the whole-corpus arm's finished chapter in context to
adapt from. Removing that removes the saving. **On this evidence
`--collection` does not reduce drafting cost — it changes what the
draft is made of.**

**Only 2 papers are cited by both arms** (`frasheri_addressing_2023`,
`kamburjan_declarative_2024`), out of 61 distinct papers cited across
the two. With independent queries the two chapters are grounded in
almost entirely disjoint literature.

**The asymmetry finding replicates under harder conditions.** Ten papers
Arm C surfaced were never surfaced by Arm F — and this time the two arms
did not even share a query list, so the effect is not an artefact of one
set of query strings. BM25 over 642 items buries what BM25 over 19 items
ranks first.

**Arm C exhausted its shelf.** 18 of 19 items surfaced, 16 of them
cited — the agent's own report says it cited "every distinct work in the
collection". At that point the selection ratio is measuring shelf size,
not judgement, and the honest reading is that a 19-item shelf is too
small for `--k 15` to discriminate at all.

### Two measurement bugs found by running this

**1. `docs/TOKENS.md`'s dedup recipe undercounts subagent transcripts by
5x.** The documented recipe dedups on `requestId` and keeps the first
entry. Streaming writes several entries per request and their `usage`
objects are *partial* — only the last is final. Measured on Arm F's
transcript: 219 usage entries over 101 request ids, 70 with more than
one entry, of which **26 genuinely differ**; first-per-id summed to
8,259 output tokens against a true **41,573**.

The fix is to take the **maximum** per request id, which is safe because
every usage field is monotonic within a request. `_pool_usage` now does
this.

Scope of the damage, checked rather than assumed: the **main session**
transcript has 132 duplicated request ids but **zero** where the entries
differ, so first-per-id and max-per-id agree exactly and every figure in
the `2026-08-18b` section above is unaffected. The bug bites subagent
transcripts only — which no previous benchmark here had reason to read.

**2. A subagent's self-reported metrics drift from its own artefact.**
Arm F reported "54 distinct citekeys cited" and listed them. The draft
contains **47**. Seven listed keys (`fitzgerald_engineering_2024-1`,
`larsen_engineering_2024`, `lim_state---art_2020`,
`semeraro_digital_2021`, `shao_analysis_2023`, `shao_use_2021`,
`thelen_comprehensive_2022`) appear nowhere in it — all real ledger keys,
presumably dropped during the agent's four trimming passes without the
tally being updated.

Nothing unsound reached the draft: the gate reads the file, not the
summary, and passed on the real 47 keys and 76 instances. But **no
figure in this section is taken from an agent's report**; every one is
recomputed from disk. Any benchmark that trusts a drafting agent's own
count is measuring the agent's bookkeeping.

### A third finding, about the environment rather than the feature

`/workspace` sits at `b4b5cb0e`; this worktree at `12e6f367`, which
carries #247 and rewrites the figure contract. The two implement
**different** contracts, and the documented marker-only form silently
drops every figure under the older one — exit 0, no warning:

| Draft form | b4b5cb0e | 12e6f367 (#247) |
|---|---|---|
| Marker only + `.tex`/`.txt` (**documented**) | `\input`=0, ASCII=0 — **dropped** | `\input`=1, ASCII=1 |
| Marker + inline fence (pre-#247) | `\input`=1, ASCII=1 | `\input`=1, ASCII=**2** — duplicated |

Both arms ran under `b4b5cb0e` and both hit it; both worked around it by
inlining fences, which is why their drafts now satisfy the *old*
contract and would double-render under #247. The `2026-08-18b` drafts,
and the `digital-twin-platforms` drafts before them, were marker-only and
therefore **rendered without their figures entirely.** Not filed as an
issue: the newer contract is correct, the stale checkout is the fault.
The live hazard worth filing separately is that #247 does not warn about
the form it replaced.

### What this section does not measure

- **One variable.** Queries and structure both vary. See above.
- **Run-to-run variance.** One agent per arm, one run each. Nothing here
  separates the arm effect from ordinary variation in agent behaviour; a
  repeated arm would be needed and was not run.
- **A shelf large enough to discriminate.** 19 items, 94.7 % surfaced.
- **Chapter quality.** Both are long (11.5k and 13.6k words against a
  10k target) and neither has been read for teaching merit.
- **Equal pipeline conditions.** Both arms ran under the stale checkout,
  so the figure mechanics above apply to both — but that was luck, not
  control.

### Reproducing

```bash
python bench/bench_collection_scope.py \
    --topic book-chapters/digital-twin-life-cycle-considerations \
    --arm-f digital-twin-life-cycle-considerations-full-corpus \
    --arm-c digital-twin-life-cycle-considerations \
    --collection Lifecycle \
    --hashes bench/results/2026-08-19-collection-scope-lifecycle-isolated/hashes.jsonl \
    --arm-f-session <session>/subagents/agent-<f-id>.jsonl \
    --arm-c-session <session>/subagents/agent-<c-id>.jsonl \
    --out bench/results/2026-08-19-collection-scope-lifecycle-isolated/measurements.json
```

`--arm-f-session`/`--arm-c-session` are the isolated-arm form: one
transcript per agent, no windowing, no quarantine, no ordering caveat.

## 2026-08-19b: three conditions — scope narrow, search wide, or narrow then widen

The two runs above ask a binary question: search the whole library, or
search one curated shelf. Real practice has a third option that neither
measured — **scope narrow to draft, then widen deliberately once** — and
it is the option the tooling actually recommends, since `corpus-reviser`
exists precisely to re-search everything for a draft that already exists.

So the collection-scoped chapter was copied to a third file and put
through a whole-corpus revision pass with `corpus-reviser`, in its own
isolated agent, with the two earlier chapters declared off-limits. They
were verified byte-identical afterwards (11,529 and 13,558 words, 47 and
16 citekeys — matching the recorded measurements exactly).

Measurements: `bench/results/2026-08-19-collection-scope-lifecycle-isolated/measurements.json`.

### The three conditions

| | drafted against the whole corpus | drafted against the `Lifecycle` shelf | shelf-drafted, then revised against the whole corpus |
|---|---|---|---|
| Words | 11,529 | 13,558 | 14,114 |
| `search` calls | 14 | 9 | 23 (9 inherited + 14 in the pass) |
| `evidence` calls | 0 | 0 | 10 |
| Retrieval payload | 103,603 | 66,372 | 185,600 |
| Distinct citekeys surfaced | 154 | 18 | 152 |
| Cited | 47 | 16 | 24 |
| **Selection / rejection** | **0.31 / 0.69** | **0.89 / 0.11** | **0.16 / 0.84** |
| Turns | 101 | 102 | 65 |
| Output tokens | 41,573 | 55,985 | **9,689** |
| Verbatim findings | 21 (all embedding) | 19 (all embedding) | 19 (all embedding) |
| Tiers not run | none | none | none |

### What the revision pass actually did

It changed **9 citations out of 16**, and the direction is the
interesting part.

**Added 9.** Six of them — `anwer_developing_2025`,
`thelen_comprehensive_2022-1`, `niederer_scaling_2021`,
`zampetti_continuous_2023`, `alcaraz_digital_2022`,
`beaumont_towards_2025` — are papers the **whole-corpus draft also found
independently**. The widening pass rediscovered, on its own queries,
two-thirds of what the shelf had been hiding. Three more
(`alskaif_evolution_2025`, `perno_implementation_2022`,
`semeraro_digital_2021`) were found by *neither* of the first two
chapters.

**Dropped 1**, and it is the right one. `noauthor_digital_2023` is an
author-less `@misc` whose bibliography entry carries the corpus owner's
own note: *"potentially low quality non-peer reviewed. Find better
references."* Both earlier chapters leaned on it for the same
188-paper phase-distribution claim. The revision cut the claim rather
than re-homing it, and replaced the underlying point with two
peer-reviewed sources. Nothing in the pipeline flagged that paper —
`annote` is not read by the gate — so this was the reviser's judgement,
not a check firing.

It also corrected two **scope justifications** rather than the scope
itself: the draft had excluded security and standards on the grounds
that "the sources barely touch" them, which the wider corpus shows to be
false. The exclusions stayed — that would have been a scope change the
task forbade — but they now read as editorial choice rather than as a
claim about the literature. That distinction is the kind of thing only a
whole-corpus pass can surface, because the scoped draft had no way to
know it was wrong.

### Source convergence without prose convergence

Pairwise draft overlap, shared 8-word runs:

| Pair | Jaccard | Longest shared run |
|---|---|---|
| whole-corpus vs shelf-scoped | 0.0006 | 17 words |
| whole-corpus vs shelf-then-revised | 0.0006 | 17 words |
| shelf-scoped vs shelf-then-revised | 0.934 | 8,615 words |

The third row is high **by construction** — that draft is a copy of the
second that was then edited, so the figure measures how much the revision
changed (about 7 % of the text), not independence.

The first two rows are the finding. **The revision moved the draft's
sources toward the whole-corpus chapter without moving its prose at all**
— identical 0.0006 before and after. Six shared citations were added and
the shared wording did not budge. Retrieval scope determines what a
chapter is grounded in; it does not determine what a chapter says. Two
agents given the same sources still write different documents, and the
benchmark can only see the first half of that.

### Cost

The revision pass cost **9,689 output tokens over 65 turns** — 17 % of
what drafting the scoped chapter cost, and 23 % of the whole-corpus
chapter — to recover six of the shelf's nine misses and drop the weakest
source in the draft. As a repair, that is cheap.

As a *strategy* it is not, and the total says so plainly: scoped drafting
plus revision is 65,674 output tokens against 41,573 for drafting against
the whole corpus once. **Narrow-then-widen costs about 58 % more output
than simply searching wide from the start.** It buys a different
artefact — three sources neither other chapter found, and a
deliberately-recorded scope justification — not a cheaper one.

The retrieval payload tells the same story from the other side: 185,600
characters across the scoped draft and its revision, against 103,603 for
the whole-corpus draft. Scoping saves payload only until you widen; then
you pay for the shelf and the library both.

### The selection ratio inverts, and it is not a regression

0.89 → 0.16 looks alarming and is an artefact of the denominator.

The scoped draft cited 16 of the 18 papers it saw because a 19-item shelf
with `--k 15` shows you nearly everything it has. After widening, the
same draft has seen 152 distinct papers and cites 24 of them. Nothing got
worse: the numerator went **up** (16 → 24) while the denominator went up
nine-fold.

This is the clearest evidence in these three runs that **selection ratio
measures pool size, not judgement**, and should never be read as a
quality score on its own. It is only interpretable against a fixed pool.

### Method note: the log cannot tell you what it was scoped to

The revised draft's `retrieval.md` holds 23 `search` rows: 9 inherited
from the scoped draft and 14 from the widening pass. **Nothing in the log
distinguishes them** — it records the query, the `--k` and the payload
size, but not the collection (#254). Replaying it correctly needed the
split supplied from outside, as `--arm-r-inherited-scoped-rows 9`, on the
strength of knowing how the file was made.

That is provenance standing in for a missing column, and it only worked
here because this run created the copy itself. For any draft whose
history someone else made, the scope of its past retrieval is
unrecoverable. #254 is the fix.

### What this section does not measure

- **Whether the revised chapter is better.** It is better *sourced* — nine
  citation changes, all defensible on inspection. Nobody has read the
  three chapters for teaching quality, and the revised one is now 14,114
  words against a 10,000-word target, which is the worst overshoot of the
  three.
- **A second revision pass.** Diminishing returns are untested.
- **Revision of the whole-corpus draft.** The fourth cell of the design —
  wide-drafted then re-revised — was not run, so "the revision found six
  of the misses" is not separable from "a second pass finds more
  regardless of the first pass's scope".
- **Run-to-run variance.** One agent per condition, one run each.

## 2026-08-26: where a cross-encoder rerank sits, relative to the per-citekey cap

Planning input for #380 (roadmap B4), run before any of that issue's code
was designed. #380 says the interesting part is not the library call but
**where the rerank sits**: over-fetch, then rerank, then cap per citekey,
then truncate to `k` -- because reranking after the cap orders a list
whose composition the bi-encoder already decided. This section measures
whether that distinction is observable on real queries, and what
reranking buys at the shipped pipeline's own shape.

### Why the existing rows could not answer this

[The 2026-08-16 sections above](#2026-08-16-retrieval-and-reranking-against-real-drafting-judgments)
already score "a dense drop-in, alone and reranked", and they are not
being re-run or contradicted here. They cannot settle #380's question,
for a reason worth stating before anyone quotes them at it: those rows
pool 50 chunks, rerank, then `collapse_to_citekeys(...)[:5]`. Collapsing
the whole pool to distinct papers **is** a per-citekey cap of 1, applied
*after* the rerank, over a pool 2.5x deeper than the shipped one. The
shipped `embed_index.search()` returns **chunks**, caps at
`embed_max_passages_per_source` (3), and over-fetches `k * 4` = 20. A cap
of 1 over 50 and a cap of 3 over 20 can disagree about which document
survives, which is exactly what #380 asks about.

### The arms

`bench/bench_rerank_position.py`, five arms over one query set:

| Arm | Order |
| --- | --- |
| 1 dense-shipped | pool -> cap -> truncate (`embed_index.search()` today) |
| 2 dense +rerank **before** cap | pool -> rerank -> cap -> truncate (**#380's stated order**) |
| 3 dense +rerank **after** cap | pool -> cap -> truncate -> rerank (the order #380 rejects) |
| 4 bm25-shipped | `retrieval.search(k)` -- what the genre skills actually call |
| 5 bm25 over-fetch +rerank | `retrieval.search(k*4)` -> rerank -> `k` |

Arm 5 is the row the 2026-08-16 section's own "What this does not
measure" names as missing -- *"whether reranking BM25's own top-K would
beat everything in this table is a real, untested combination"*.

`cap_and_truncate` is `embed_index.search()`'s cap loop lifted out
verbatim, so the three dense arms differ *only* in where `rerank` is
applied; `assert_replication_matches_shipped` asserts on real queries
that arm 1 reproduces `embed_index.search()` exactly, so no arm can
quietly measure a reimplementation that drifted.

### The ground truth, and why this one

`bench_retrieval_keyword_selfretrieval.py`'s 256 pairs, imported rather
than rebuilt: query = a bib entry's own author-assigned `keywords`,
correct answer = that entry itself. Chosen over the 48-pair drafting
ground truth because it needs only `bibliography.bib` and the synced
ledger -- no restored book, no rejoin -- and because no retrieval method
built it. Host and corpus as the sections above: 642 ledger items, 497
parsed, `content/chroma/` at 40,741 chunks,
`sentence-transformers/all-mpnet-base-v2`, `k` = 5, cap = 3, reranker
`cross-encoder/ms-marco-MiniLM-L6-v2`.

### The table

| row | n | recall@3 | recall@5 | nDCG@5 | distinct@5 |
|---|---|---|---|---|---|
| 1 dense-shipped (pool -> cap -> k) | 256 | 0.5039 | 0.6094 | 0.4949 | 3.590 |
| 2 dense +rerank **before** cap (#380) | 256 | **0.5430** | 0.6094 | **0.5281** | 3.574 |
| 3 dense +rerank **after** cap | 256 | 0.5273 | 0.6094 | 0.4962 | 3.590 |
| 4 bm25-shipped (`retrieval.search`) | 256 | **0.7695** | **0.8047** | **0.7321** | **5.000** |
| 5 bm25 over-fetch +rerank -> k | 256 | 0.7500 | 0.7930 | 0.6886 | 5.000 |

`recall@3` and `distinct@5` are here because they, not `recall@5`, are
what #380's motivating claim is about -- "better-ordered passages mean
fewer passages are needed", and "fewer passages per source is what makes
multi-source units reachable". No existing row measures either.

### Is the cap position observable at all? Yes, and strongly

Arm 2 against arm 3: **217 of 256 queries (84.8%) return a different set
of papers**, and a further 20 differ only in order. So #380's concern is
not theoretical on this corpus -- moving the rerank across the cap
changes *which documents* survive on five queries in six.

**Arm 2 is also the better of the two orders**, which is the first thing
here that supports the issue as written: nDCG@5 0.5281 against 0.4962,
recall@3 139/256 against 135/256. The order #380 specifies is the one to
build, and now for a measured reason rather than only an argued one.

### But the churn is a wash for finding the right paper

Arm 1 against arm 2 is the same 217/256 set churn -- and **recall@5 is
bit-identical at 156/256**. The reason is not that the benchmark cannot
see the effect; it is that the effect cancels. The correct paper is
**lost 20 times and gained 20 times**. Reranking is genuinely swapping
right answers out and in, in equal number.

That distinction was worth spending a second run on, because an
unchanged recall beside an 85% set change has two readings that lead to
opposite plans -- the swaps traded evenly, or the churn never touched
the answer -- and only one of them is a finding. The pool-rank profile
confirms the metric has room to see it: the correct paper sits at
**median rank 2** in the 20-chunk pool, at rank 1 for only 92 of 256, in
the top 3 for 141, beyond rank 5 for 24, and **absent from the pool
entirely for 69 (27%)**. It is not a benchmark whose answer is always at
rank 1.

Where reranking does pay is shallower in the list: **recall@3 rises from
129/256 to 139/256, ten queries.** That is the one place "fewer passages
are needed" gets support, and it is modest.

The 27% absent figure sets a ceiling worth recording separately: dense
retrieval's best possible recall@5 here is 187/256 (0.7305) no matter
what reranks it, because the other 69 answers never enter the pool. The
shipped arm reaches 156. A deeper `_OVERFETCH_MULTIPLIER` is a different
lever than a reranker, and this section does not test it.

### `distinct@5` does not move, and that is the clearest result

3.590 -> 3.574 is **four slots across 256 queries**. Zero, not "slightly
worse".

It is worth seeing why this is structural rather than a near-miss. With
cap = 3 and `k` = 5, `distinct@5` can only lie in {2, 3, 4, 5}, and the
cap is what puts it there. Reranking reshuffles *within* the same cap
regime, so it cannot change source diversity; only
`embed_max_passages_per_source` or `k` can. **B4 therefore does not
unblock #310's multi-source units**, which is the compounding claim
#380 leads with. That conclusion does not depend on the lost/gained
question above.

### Reranking the retriever that actually wins does not help either

Arm 4 against arm 5 answers the 2026-08-16 section's own open question.
Stated as query counts, because the rate differences are small: recall@5
206 -> 203 (**three queries**), recall@3 197 -> 192 (**five queries**).
Those are too small to call a regression. The ordering metric is the
only clear signal, and it moves against reranking: **nDCG@5 0.7321 ->
0.6886**. The correct paper is lost 15 times and gained 12.

So: no improvement from reranking BM25, and the one metric with a clear
direction is negative.

BM25 also holds `distinct@5` at a perfect 5.000 by construction -- it is
one result per citekey (#305), so it has no cap-position question to
answer at all.

### Three rerankers, because one model is not a finding

Every number above is `cross-encoder/ms-marco-MiniLM-L6-v2`, trained on
MS MARCO web search rather than on scientific prose -- so "reranking is
a wash" was, on that run alone, entangled with "this reranker is out of
domain". `--rerank-model` exists to separate the two. Two more
candidates, same 256 queries, same arms:

Arm 2 (dense, reranked before the cap), against arm 1's un-reranked
baseline of recall@3 129/256, recall@5 156/256, nDCG@5 0.4949,
`distinct@5` 3.590:

| reranker | recall@3 | recall@5 | nDCG@5 | distinct@5 | lost / gained |
|---|---|---|---|---|---|
| *(none -- arm 1 baseline)* | 129 | 156 | 0.4949 | 3.590 | -- |
| `cross-encoder/ms-marco-MiniLM-L6-v2` | 139 | 156 | **0.5281** | 3.574 | 20 / 20 |
| `cross-encoder/ms-marco-MiniLM-L12-v2` | 138 | 152 | 0.5107 | 3.570 | 22 / 18 |
| `BAAI/bge-reranker-base` | **144** | **157** | 0.5175 | 3.531 | 16 / 17 |

**The confound is resolved, and the conclusion survives it.**
`bge-reranker-base` is a strong general-purpose reranker from a
different training lineage, and it moves recall@5 by **one query**, from
156 to 157. `ms-marco-MiniLM-L12-v2` -- the larger sibling of the
default -- moves it *down* four. Whatever reranking is doing here, no
reranker in this set makes the dense path find papers it was not already
finding.

**What all three do agree on** is the shallow-ordering gain: recall@3
rises for every one of them, by 9, 10 and 15 queries. That is the real
effect, and it is consistent across models.

**And none of them moves `distinct@5`** -- 3.590 -> 3.574, 3.570, 3.531.
All three drift very slightly *down*, none by enough to matter. The
structural argument above says why: the cap, not the ordering, sets
source diversity.

**Reranking BM25 gets worse the stronger the reranker is**, which is the
one pattern here worth flagging as odd rather than explaining. Arm 5's
nDCG@5: 0.6886 (L6), 0.6800 (L12), 0.6533 (bge), against arm 4's
un-reranked 0.7321; recall@5 203, 199, 196 against 206. With three
points this is a direction, not a law -- but the direction is that a
better cross-encoder damages BM25's ordering *more*, and no candidate
came close to leaving it alone. Whatever BM25 is ranking on for these
keyword queries, a cross-encoder over a 500-character window disagrees
with it, and is wrong to.

One architecture note, because `docs/CONFIG.md` warns about this family
for the *embedding* slot: `BAAI/bge-reranker-base` is
`XLMRobertaForSequenceClassification` with `num_labels=1`, scoring a
`(query, passage)` pair jointly in a single forward pass, exactly as
`ms-marco-MiniLM-L6-v2` (`BertForSequenceClassification`,
`num_labels=1`) does. CONFIG.md's `"query: "` / `"passage: "` prefix
warning is about bi-encoders, which encode the two sides independently
and need a role marker. It does **not** carry over to the reranker, and
no prefix was added for it here.

### What this does not measure

- **A second ground truth.** One query set, and a self-retrieval one:
  its task rewards paper-level similarity, the same property [the
  2026-08-16 keyword section](#2026-08-16-retrieval-quality-with-a-ground-truth-no-retrieval-method-built)
  already notes lifted the SPECTER2 cascade there. Direction, not
  magnitude, is what should be quoted from this table.
- **Arm 2 and arm 5 are not apples-to-apples.** Arm 5 hands the
  cross-encoder BM25's `_snippet()` output -- query-term-anchored
  windows -- while arm 2 hands it raw chunk prefixes (`doc[:500]`). The
  reranker is scoring differently-shaped text in the two arms. Compare
  each against its own un-reranked baseline; do not read arm 5 against
  arm 2.
- **Wall clock.** No arm is timed. A reranker's cost per query is a real
  input to whether it is affordable in a drafting loop, and it is not
  measured here.
- **A deeper pool, or a different cap.** `_OVERFETCH_MULTIPLIER` = 4 and
  cap = 3 throughout, both at their shipped values.
- **Precision.** As every retrieval section here: a plausible substitute
  paper in the top 5 counts as a miss, the same as an irrelevant one.

### Reproducing

```bash
CHITRAGUPTA_PROJECT=/workspace /workspace/.venv-full/bin/python \
    bench/bench_rerank_position.py --tag 2026-08-26-rerank-position

# The other two rerankers in the sweep above.
for m in cross-encoder/ms-marco-MiniLM-L12-v2 BAAI/bge-reranker-base; do
    CHITRAGUPTA_PROJECT=/workspace /workspace/.venv-full/bin/python \
        bench/bench_rerank_position.py --rerank-model "$m" \
        --tag "2026-08-26-rerank-position-$(basename "$m")"
done
```

Read-only against `content/`; writes only
`bench/results/<tag>/rerank_position.json`.

## 2026-08-26b: what cross-encoding the over-fetched passages costs

The section above measures whether reranking helps. It does not time
anything, and `plans/b4-cross-encoder-rerank.md` was blocked on cost: a
reranker runs inside a drafting loop, once per `search()` call, so
affordability is decided by *added latency per call*, not by the model's
size on disk.

`bench/bench_rerank_cost.py`. 20 real queries x up to 50 real passages
(500 chars each, the shipped `snippet_chars`), median of 3 passes after
an untimed warm-up. The baseline is the shipped `embed_index.search()`
path -- query encode plus Chroma query -- timed **in the same process on
the same device**, so both halves of every ratio come from one run.

| device | baseline `search()` |
|---|---|
| cuda | 12.4 ms/query |
| cpu | 44.2 ms/query |

Rerank cost, and what it does to a search call:

| device | reranker | pool 5 | pool 20 (shipped) | pool 50 |
|---|---|---|---|---|
| cuda | `ms-marco-MiniLM-L6-v2` | 5.7 ms (1.46x) | **18.9 ms (2.52x)** | 41.2 ms (4.31x) |
| cuda | `ms-marco-MiniLM-L12-v2` | 9.8 ms (1.78x) | 34.3 ms (3.76x) | 71.6 ms (6.75x) |
| cuda | `BAAI/bge-reranker-base` | 16.6 ms (2.33x) | 67.0 ms (6.39x) | 156.8 ms (13.61x) |
| cpu | `ms-marco-MiniLM-L6-v2` | 40.7 ms (1.92x) | **210.2 ms (5.75x)** | 513.9 ms (12.62x) |
| cpu | `ms-marco-MiniLM-L12-v2` | 100.5 ms (3.27x) | 401.7 ms (10.08x) | 856.3 ms (20.36x) |
| cpu | `BAAI/bge-reranker-base` | 170.2 ms (4.85x) | 1001.4 ms (23.64x) | 2202.1 ms (50.78x) |

Model construction, paid once per process by a lazy loader: 1.8-2.0 s
for either MiniLM, 2.6-3.5 s for `bge-reranker-base`.

**At the shipped pool of 20, the cheapest reranker makes a search call
2.5x more expensive on a GPU and 5.75x on a CPU.** Read that against
what the section above found it buys: recall@5 unchanged, `distinct@5`
unchanged, recall@3 up ten queries in 256. This is the number that turns
"default off" from a courtesy into the only defensible setting.

**The quality winner and the cost winner are not the same model, and the
gap is not small.** `bge-reranker-base` had the best recall@3 and
recall@5 above; here it is **3.5x** the cost of `ms-marco-MiniLM-L6-v2`
on a GPU and **4.8x** on a CPU. For five extra correct answers in 256, on
one document-level ground truth, that is not a trade this measurement
supports.

**CPU is where this decides itself.** The `enrich` extra installs torch
either way and nothing requires a GPU, so a laptop drafting session with
`bge-reranker-base` would pay **one full second per search call**, and
over 2 seconds if anyone widened the pool. A genre skill issues many
searches per draft.

**Pool depth is superlinear-ish in practice.** 5 -> 20 -> 50 costs
roughly 1x -> 3.3x -> 7.2x (cuda, L6), so "just over-fetch deeper so the
reranker has more to work with" -- the obvious response to the 27% of
correct papers that never enter the pool -- is the most expensive knob
here, not a free one.

### What this does not measure

- **Batching across queries.** Every timing scores one query's pairs per
  `predict()` call, which is what `search()` would do. A caller reranking
  many queries at once would amortise better, and no skill does.
- **Throughput under contention.** One process, one idle GPU. A parallel
  sync or a second session is not modelled.
- **Quantised or ONNX runtimes**, which are the standard answer to
  cross-encoder latency and would change every row here.
- **This host only.** One CPU, one GPU model. The ratios travel better
  than the absolute figures, which is why the ratio is the headline.

### Reproducing

```bash
CHITRAGUPTA_PROJECT=/workspace /workspace/.venv-full/bin/python \
    bench/bench_rerank_cost.py --tag 2026-08-26-rerank-cost
```

## 2026-08-27: does claim-support checking (#C2) separate supported claims from unsupported ones on this corpus?

Extraction ran 2026-08-26 (tag `2026-08-26-claim-support-measurement`,
below); the human read the shortlist and this section was written
2026-08-27 — same measurement, two dates, no second run.

`bench/bench_claim_support.py --extract`, run against the four real
drafts of `digital-twins-for-software-engineers`
(`survey.md`, `book-chapter.md`, `tutorial.md`, `deep-research.md`):
71 findings scored (of 73; one citekey, `talasila_composable_2025`, is
not yet in the ledger), score range 0.004-0.989, median 0.526. The 20
lowest-scored and 20 highest-scored are shortlisted into
`bench/results/2026-08-26-claim-support-measurement/candidates.md`
(gitignored — it carries claim text and source excerpts straight out of
the real drafts; regenerate with the command in that file's own header).

A human read all 40 shortlisted candidates against their matched
passage. **No structured per-id `labels.json` was produced and
`--crosscheck` was not run** — this section reports that qualitative
read, not a labelled separation statistic. Do not read a number into
this section; there isn't one to cite beyond the score range above.

The read: most of the 20 lowest-scored candidates look "unrelated"
rather than "contradicted" — but reading the actual matched passages
shows why. The dominant failure is retrieval, not entailment: the
passage-matching step frequently hands the scorer the wrong passage from
an otherwise-relevant paper, and the low score is doing exactly what it
should with the input it was given. Examples, verbatim from
`candidates.md`:

- `survey.md#f3c9b7cd2405` (score 0.014, citekey `kamburjan_greenhousedt_2024`):
  claim about GreenhouseDT's extensible architecture, matched passage is
  the two words "light sensor".
- `survey.md#fee1e7705e0e` (score 0.027, citekey `bhandal_conceptualising_2024`):
  claim about the Digital Twin Consortium's definition, matched passage
  is a paragraph about supply chains and COVID-19 shopping habits from
  the same paper's introduction.
- `survey.md#c06663bef58f` (score 0.028, citekey `bellavista_exploiting_2024`):
  claim about commercial platforms vs. research treating twins as
  orchestrated microservices, matched passage is the single word
  "Outpost".
- `book-chapter.md#c920f22c9b23` (score 0.103, citekey `gil_survey_2024`):
  claim about comparing open-source frameworks, matched passage is a
  bibliography entry (another paper's reference-list line).

Where the matched passage genuinely was the right one, separation was
clean: `survey.md#7074fe8f5cd9` (score 0.988, citekey
`kulik_security_2024`) matches a claim about twin traffic and attack
surface against a passage that says exactly that, almost verbatim.
`book-chapter.md#61a033a68a98` (score 0.967, citekey
`committee_on_foundational_research_gaps_and_future_directions_for_digital_twins_foundational_2024`)
matches a claim about bidirectional physical/virtual interaction against
a passage stating "the bidirectional interaction between the virtual and
the physical is central to the digital twin." The risk is not absent at
the high end either: the single highest-scored candidate
(`survey.md#70430a377482`, 0.989, citekey `barbie_toward_2024`) matches
a claim naming a specific CI-pipeline/smart-farming case study against a
passage about RAMI 4.0's "Business" layer — the same paper, the wrong
section, scored high on shared digital-twin vocabulary alone.

### What this does not measure

- **A precision or recall number for the scorer itself.** That needs a
  structured `labels.json` pass this run did not do — see above.
- **Whether the low-scored claims are actually supported somewhere else
  in their cited source.** Checking that would mean reading the whole
  paper for each of the 20, not just the matched passage; not done here.
- **Passage-matching's own precision**, independent of entailment. This
  section names the pattern from the 40 shortlisted candidates; it does
  not count how often it happens across all 71.

### Conclusion

This is not evidence the entailment scorer fails to discriminate — every
spot check where the matched passage was actually on-topic showed a
clean, wide separation between genuine support and not. The weak link
this run surfaces is upstream, in which passage gets handed to the
scorer, which is exactly the risk
[`docs/PLAGIARISM-DESIGN.md`](../docs/PLAGIARISM-DESIGN.md)'s tier 3
argument already names for wording overlap and
`chitragupta/review/_claim_support_render.py`'s own caveat paragraph
already states for this aid ("retrieval already selected these passages
by similarity"). The aid ships as designed — ranked, no verdict, no
threshold — per that same argument; this result does not change what it
should say, only confirms it with a real example. See
[`docs/REVIEW.md`](../docs/REVIEW.md)'s "Three limits worth knowing" for
the shipped wording.

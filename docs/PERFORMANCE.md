# ⚡ Performance

Status: **measurements.**

**Written for** anyone choosing settings on their own hardware and
wanting the measured cost rather than a guess. **Assumed:**
[CONFIG.md](CONFIG.md) for what each setting does. **Not covered here:**
the parallelism design behind these numbers, which is
[PARALLELISM.md](PARALLELISM.md), written for someone changing it.

What each setting in [CONFIG.md](CONFIG.md) costs, measured rather than
estimated. [PDF-PARSER.md](PDF-PARSER.md) compares the backends on
fidelity, and [REVIEW.md](REVIEW.md) says what the review aids priced
below do. The raw record, with per-PDF timings, is
[bench/RESULTS.md](https://github.com/prasadtalasila/chitragupta/blob/main/bench/RESULTS.md),
which is in the repository but not in a downloaded release.

## 📊 Read the numbers with the machine in mind

**Every figure below is one machine's, and yours will differ.** Use them
for ratios and orders of magnitude ("OCR roughly halves throughput"),
not as absolute times to plan against. Two reference machines are used;
[README.md](../README.md#-hardware-requirements) has the sizing guidance
that follows from them.

| Name used below | What it is |
| --- | --- |
| **the small machine** | 4 cores, 9.7 GB RAM (~3 GB of it free), no GPU |
| **the multi-GPU machine** | 96 logical cores (48 available to the process), 251 GB RAM, 4x NVIDIA A40 46 GB, driver 555.42.02, CUDA 12.5. Verified 2026-07-30 |

The corpus is this project's own bibliography: **501 PDFs, 13,400 pages,
1.54 GB**, median 16 pages, with one 675-page book that is 5% of all
pages by itself. Software: docling 2.117.0, torch 2.7.1+cu126,
Python 3.12.3. Reproduce any of it with the harness in `bench/`; see
`bench/README.md`.

## 🔧 Install-time costs and traps

Two costs land at install time, before any setting matters.

**No GPU, disk tight: several GB of CUDA you will never use.** The
default torch wheel pulls a full set of `nvidia-*` CUDA packages whether
or not a GPU is present, most of the venv's 6.0 GB. On a CPU-only host,
install torch from the CPU-only index *before* running the installer:

```bash
.venv-full/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
bash scripts/install_full_pipeline.sh python-deps
```

**GPU present, but `torch.cuda.is_available()` is `False`: silently
CPU-only.** This costs the entire 4.70x below while looking like a
working install. `scripts/install_full_pipeline.sh`'s `ensure_gpu_torch`
catches it on every `python-deps`/`dev-deps` install: it reads the
driver's CUDA ceiling from `nvidia-smi` and reinstalls torch from a
matching wheel index. It is idempotent and safe to re-run. Check with:

```bash
.venv-full/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

If it still reports `False`, the driver may predate every wheel tag the
script knows; that function's comments have the manual fallback.

## ⚙ `[parser].backend` -- pdftotext or docling

Measured cold on 5 real bibliography PDFs:

| Backend | Total, 5 PDFs | Words extracted | Ratio |
| --- | --- | --- | --- |
| `pdftotext` | 1.43s | 68,888 | 1x |
| `docling` (OCR on) | 60.77s | 69,565 | ~42x |

Per document the ratio ranged **~18x-102x**, so budget against the
total. Word counts stay within ~3.5% of each other: the reason to pick
docling is structure (reading order, sections, tables), and the reason
to pick `pdftotext` is speed. [PDF-PARSER.md](PDF-PARSER.md) has the full
comparison. The ~42x is enough to choose a backend and useless for
planning a run, which is what the rest of this page is for.

## 👁 `[parser].ocr` -- the largest single lever, and a trade

**OCR's cost grows with worker count**, because OCR is CPU-bound and
competes with the parallelism you added. Over the whole 501-PDF corpus
(2026-08-04):

| Workers | OCR off | OCR on | Cost of OCR |
| --- | --- | --- | --- |
| 1 | 3330.4s | 6941.4s | **2.08x** |
| 12 | 310.2s | 1213.9s | **3.91x** |
| 24 | 237.6s | 1139.0s | **4.79x** |

Equivalently, **turning OCR on roughly halves how well the pipeline
parallelises**: 1 to 24 workers is a 14.02x speedup with OCR off and
**6.09x** with it on, when 93% of the available CPU is busy. A
2026-08-30 re-measure on a host with 96 allowed CPUs moved every ratio
(serial 2.87x); see
[bench/RESULTS.md](https://github.com/prasadtalasila/chitragupta/blob/main/bench/RESULTS.md).

**It cannot be moved to the GPU by configuration.** docling's OCR runs
on the CPU (RapidOCR on onnxruntime): the installed `onnxruntime` wheel
offers no `CUDAExecutionProvider`, and docling's `RapidOcrModel` sets
`use_cuda` on the paddle and torch engines but not the onnxruntime one.
On one PDF with one worker on `cuda:0`, OCR was **79% of the wall
clock** (5.31s on against 1.13s off), all on the CPU. Moving it would
mean `RapidOcrOptions(backend="torch")` plus a config key; the 1.79x
below is not a ceiling on that gain, and it needs measuring.

**Turning OCR off loses some content.** OCR only reads text stored as an
image. Off changed the extracted text of **8 of 16 sampled documents**,
mostly publisher furniture and figure sub-captions, but one document
lost **10.1% of its characters**, including two tables embedded as
images.

**So `false` suits born-digital papers.** Set `true` for scans, from
which docling extracts almost nothing without OCR, or where
tables-as-images matter more than parse time. The parse-quality guard
will not catch a wrong choice here.

## ⚖ GPU vs CPU -- it depends entirely on OCR

**With OCR off (the default), a GPU is worth 4.70x**, measured serially
on the same PDFs through both devices with model loading excluded
(2026-08-05):

| Documents | Pages | GPU | CPU | Aggregate |
| --- | --- | --- | --- | --- |
| 10 | 75 | 0.222 s/page | 0.975 s/page | 4.39x |
| 25 | 394 | 0.174 s/page | 0.948 s/page | 5.43x |
| 50 | 798 | 0.211 s/page | 0.985 s/page | 4.67x |
| **100** | **2,529** | **0.205 s/page** | **0.965 s/page** | **4.70x** |

Per document the median was 4.31x (quartiles 3.46x and 6.56x), and only
one document of the hundred came in under 2x. The gain grows with
document size, from 3.49x under 10 pages to 5.78x at 30 or more, because
layout and table inference scale with page count while the fixed
per-document costs do not.

**With OCR on, it is worth 1.79x**: 0.43 against 1.37 s/page, about 1.6
against 5.1 hours for the corpus. OCR runs on the CPU either way, so it
adds the same seconds to both sides and drags the ratio toward 1. During
that run the GPU averaged ~7% SM utilisation and 1.7 GB of 46 GB. Read
1.79x as what a GPU is worth on an OCR run and 4.70x as what it is worth
on a default run.

docling is still CPU-bound overall, which is why the parallelism work
went after CPU-level document concurrency first. A GPU is worth having;
it is not what makes a corpus parse fast.

## ⚙ `[parser].workers` -- document-level parallelism

**The largest lever on a multi-core machine, and the code caps it well
below where the curve flattens.** The real `sync` over the whole
501-PDF corpus, docling, OCR off, 4 GPUs (2026-08-04), each run from an
empty ledger with 501 parsed and 0 failed:

| Workers | Wall clock | Speedup | Efficiency | |
| --- | --- | --- | --- | --- |
| 1 | 3330.4s | 1.00x | -- | |
| 4 | 799.2s | 4.17x | 104% | |
| 8 | 428.6s | 7.77x | 97% | |
| 12 | 310.2s | 10.74x | 89% | <- **the most `worker_ceiling()` allows** |
| 16 | 268.1s | 12.42x | 78% | |
| 24 | 235.0s | 14.17x | 59% | median of 3 |
| **32** | **223.4s** | **14.91x** | 47% | median of 3 |
| 48 | 221.4s | 15.04x | 31% | median of 3 |

A 2026-08-30 re-measure with 96 allowed CPUs ran every arm ~21% faster
with the same efficiency curve; treat it as a different machine
configuration
([bench/RESULTS.md](https://github.com/prasadtalasila/chitragupta/blob/main/bench/RESULTS.md)).

- **The knee is past 24, not at 12.** `worker_ceiling()` caps at
  `allowed_cpus // 4`, 12 here, and 32 workers run **~1.4x faster**.
  Asking for 16 resolves to 12, so the clamp costs 1.43x.
- **32 to 48 is a plateau, not a reversal**: medians of three runs are
  0.9% apart, inside the 86.8s spread of the 32-worker runs alone.
- **The divisor of 4 is too large.** At 32 workers the host CPU is only
  ~70% busy (host-wide `/proc/stat`, so an upper bound): with OCR off a
  worker uses closer to one CPU than four. The useful statement is "much
  smaller than 4", not a specific value from one machine and one corpus.

Past ~24 workers two costs flatten the curve together:

| Workers | Startup (to 1st document) | Tail (after last) | CPU busy |
| --- | --- | --- | --- |
| 24 | 18.6s (**7.9%** of the run) | 4.9s (2.1%) | 56% |
| 32 | 21.8s (**8.9%**) | 5.9s (2.6%) | 70% |
| 48 | 28.5s (**12.7%**) | 7.9s (3.6%) | 78% |

Every worker pays its own ~8.5s model load, so startup is a growing tax,
and the CPU is heading for saturation. The long-document tail is small
throughout.

**Corpus size decides whether raising this is worth anything.** Over 8
documents, 4 workers gave 1.90x and 8 gave nothing more, because the
per-worker model load has too little work to amortise over. That is why
the resolved count is also capped by the number of documents to parse.

## 🖥 Multi-GPU -- nothing to configure

Each docling worker claims one CUDA device round-robin, since docling's
own `AcceleratorDevice.AUTO` would put every worker on `cuda:0`. Over the
whole corpus (2026-08-04, OCR off):

| Workers | 1 GPU | 2 GPUs | 4 GPUs | 1->2 | 2->4 |
| --- | --- | --- | --- | --- | --- |
| 12 | 518.4s | 339.7s | 310.2s | 1.53x | 1.10x |
| 24 | 535.8s | 298.6s | 237.6s | **1.79x** | 1.26x |

**The second card is worth far more than the third and fourth**, and
GPUs matter more as more workers share each card; at 24 workers one GPU
is *slower* than at 12. Restrict the cards with `CUDA_VISIBLE_DEVICES`.
**On a small corpus it is worth nothing**: 60 documents took 122.4s at 4
workers and 123.0s at 12, since per-worker startup dominates.

## ⚙ `[parser].start_method` -- per-worker startup

A cold docling worker needs about **8.5s** before its first page on the
multi-GPU machine:

| Stage | Time |
| --- | --- |
| `import torch` | 1.16s |
| `import docling` | 2.08s |
| Build the `DocumentConverter` | 0.13s |
| First `convert()` (docling loads its models here) | 5.17s |
| **Total before the first parsed page** | **8.5s** |
| A later `convert()`, models warm | 0.33s |

Only the ~3.2s of imports can be shared between processes, which is what
`forkserver` does, and since `sync` starts the forkserver while it reads
the bibliography, the pool is ready sooner (four workers at 4.40s
instead of 6.90s). End to end that is a roughly constant **1.3-2.2s**
off pool startup: 9.6% of an 8-document run, 2.5% of a 60-document one,
and well under 1% of the full corpus. **It does not make a bulk parse
meaningfully faster**; it helps when a handful of documents is the run.

## ⏱ `[parser].document_timeout` -- what a safe value looks like

The value has to clear the slowest document you legitimately have. In
this corpus that is a 675-page book taking **246s** on its own, so a
value safe here may not be safe on a corpus with a longer document.
Measure before setting it. `[parser].stall_timeout`'s 1800s default is
7x that figure, loose on purpose: it catches a run that will never
finish, not a slow one.

## 💾 `[enrich].docling_images` -- disk, and a full re-parse

Turning it on has two costs:

- **It invalidates the whole docling cache**, so the next run re-parses
  every PDF: the existing `.md` files have no figure references.
- **The PNGs are real disk**: a 17-page paper produced 13.
  `docling_image_scale = 2.0` is roughly 144 DPI.

### 🧠 Memory: bounded per document

docling retains every crop it produces (as a PIL bitmap and a base64
URI) until the end of the parse, so its memory grows with a document's
figure count. The pipeline instead takes the bounding boxes docling
reports anyway, and `chitragupta/enrich/_docling_crops.py` renders each
one with pypdfium2, writes it, and releases it. Peak RSS, one document
per process, on the worst document (a 99-page slide deck, 280 figures)
and the longest (the 675-page OMG SysML specification):

| Document | `docling_images` | Peak RSS | Figure term | Wall |
| --- | --- | --- | --- | --- |
| 99-page deck | `false` | 4.12 GiB | -- | 104.6 s |
| 99-page deck | `true`, docling crops | 13.07 GiB | **+8.95 GiB** | 270.0 s |
| 99-page deck | `true`, **pypdfium2 crops** | 4.14 GiB | **+0.02 GiB** | **158.9 s** |
| 675-page spec | `false` | 4.20 GiB | -- | 82.6 s |
| 675-page spec | `true`, docling crops | 9.13 GiB | +4.93 GiB | 114.1 s |
| 675-page spec | `true`, **pypdfium2 crops** | 4.24 GiB | +0.04 GiB | 93.8 s |

That is **450x less memory for figure extraction on the deck, at 1.70x
the speed**, because docling renders a whole page to crop from and this
renders only the box.

- **`docling_image_scale` is safe to raise.** At 6.0 the docling-crop
  path reached **74.31 GiB and then failed** on docling_core's 20 MiB
  decoded-image guard. With pypdfium2 crops the same document completes
  in 439 s with a figure term of +0.06 GiB: high scales cost CPU, not
  RAM.
- **The figure term does not depend on the corpus**: not on document
  length, page geometry, scale, or accelerator. That is what lets
  `[parser].workers` be sized from CPUs alone; see `docs/PARALLELISM.md`'s
  "How the worker count is decided".

## 🗑 `[source_pdfs] dir` -- retired

The enrichment corpus is the bibliography alone, so there is nothing to
measure. A config file still naming the key is ignored;
`chitragupta/enrich/corpus.py` has the reasoning.

## 🏁 Where it all ended up

Measured end to end on 2026-08-04 over the full 501-PDF corpus:

| Change | Kind | Full 501-PDF corpus |
| --- | --- | --- |
| Baseline: serial, OCR on | -- | **1h 56m** |
| OCR off | not parallelism | 55m 30s |
| 12 workers, 4 GPUs (today's cap) | CPU + GPU | 5m 10s |
| 32 workers, 4 GPUs (needs the clamp raised) | CPU | **3m 43s** |

That is **22x with the shipped defaults and 31x with the clamp raised**.
The largest single contribution is turning OCR off; the GPU's is the
smallest.

## 🔍 What a review pass costs

This is the **review layer** ([REVIEW.md](REVIEW.md)). Eight aids are
deterministic Python with no model call. The ninth, `support`, scores
every citation with an NLI entailment model ([CONFIG.md](CONFIG.md)); it
uses no LLM, so **the token cost of every figure here is zero**, but it
has a real wall-clock and memory floor. `digest` reads a digest, not a
draft, and is not timed. **`union` is not in any figure below**: it
reads an assembled book rather than a draft, so it has no place in a
per-draft pass, and it has not been measured. It parses one document and
one small JSON per unit with no corpus read and no model, the same class
as `uncited`.

Five real drafts of 1,258 to 18,061 words, with and without a dossier,
at `--formats md` (2026-08-27), in milliseconds:

| words | dossier | prov | verbatim | cover | synth | figure | uncited | quote | agenda | support | all nine |
| ---: | :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,258 | no | 180 | 447 | 303 | 90 | 87 | 88 | 89 | 575 | 33,464 | **35,323** |
| 2,448 | no | 366 | 474 | 303 | 90 | 89 | 92 | 92 | 577 | 40,832 | **42,915** |
| 5,723 | yes | 144 | 19,737 | 310 | 95 | 486 | 99 | 88 | 508 | 21,160 | **42,627** |
| 10,003 | yes | 332 | 41,019 | 314 | 96 | 818 | 109 | 88 | 1,017 | 62,292 | **106,085** |
| 18,061 | yes | 277 | 35,698 | 315 | 98 | 641 | 121 | 90 | 1,282 | 45,902 | **84,424** |

Corpus at the time: 642 ledger items, 994 parsed sidecars, 6.4 million
parsed words, a 547 MB overlap index. A 2026-09-04 re-timing after a
finer re-parse put `support` at +65% to +95% on the same drafts, for the
reason in [the section below](#-what-supports-cost-actually-tracks); the
two are not comparable row by row.

### 📐 Two aids set the floor, for different reasons

**`verbatim`'s tier 3 decides its cost.** It needs the `enrich` group,
`content/chroma/`, the Docling sidecars, the draft's dossier and a
synced ledger ([PLAGIARISM.md](PLAGIARISM.md)). With any missing the
scan is **447 ms**; with all present it is **19.7-41.0 s**. It fetches
each source once, so its cost tracks *distinct citekeys*, roughly
**1.0-1.5 s per distinct citekey**
([PLAGIARISM.md](PLAGIARISM.md#-how-the-tiers-were-chosen)), and so does
`provenance`'s. **Estimate them from the citekey count, not the word
count.**

**`support` has no off switch.** It always loads the model and scores
every citation, costing **21.2-62.3 s on every draft measured**: ~95% of
the row where tier 3 cannot run, and 59% beside `verbatim`'s 39% on the
10,003-word draft. So the layer's cheapest-to-dearest spread is a factor
of **3**, not 23.

Everything else is flat and nearly free. `coverage` holds ~305 ms, a
corpus query rather than a draft scan. `synthesis`, `uncited` and
`quotation` sit near the **~86 ms** interpreter-startup floor every
`python -m` invocation pays. `figure` is ~88 ms without figures and
486-818 ms with them.

### 🧮 What `support`'s cost actually tracks

`chitragupta/review/claim_support.py`'s `_score_claim` scores **one
entailment pair per quotable passage of the cited source**, for every
citation, so the work is

```text
sum over citations of |quotable passages of that citation's source|
```

and the second factor is set by how finely the parse segmented the
corpus, which no draft controls. Measured 2026-09-07:

| draft | words | citations | entailment pairs | pairs per citation |
| --- | ---: | ---: | ---: | ---: |
| deep-research.md | 1,258 | 23 | 20,402 | **887** |
| survey.md | 2,448 | 43 | 29,738 | **725** |

Against the passage sidecars from before the 2026-09-04 re-parse, the
pair count grew **1.67x** and **1.49x** on the same drafts citing the
same sources over an unchanged 497-document corpus: a re-segmentation
effect. `verbatim` barely moved over that period because it fetches each
source once, while `support` iterates the passages. **So estimate
`support` from the pair count**, and treat any milliseconds-per-citation
figure (835-962 ms on 2026-08-27) as valid only for the passages it was
measured against.

**The pair count is settable, and not set by default.**
`[enrich].support_premise_topk` ([CONFIG.md](CONFIG.md)) sends the model
only the top *k* premises by lexical overlap. Every figure above, and
every dated entry in `bench/RESULTS.md`, is the uncapped default. The
cap buys 5.3x to 102x fewer pairs (62 s of scoring down to 4 s), but
**it is off because it damaged the report**: at k = 128 the lexical
pre-ranker agrees with the entailment model on the supporting passage
for only **56.5%** of citations (14.6% at k = 8), and claims scoring
0.995 uncapped came back at 0.138 (`bench/bench_support_topk.py`,
2026-09-09). That rules out lexical pre-ranking at every k measured, not
a cap in principle: a semantic pre-rank is the untested candidate, and
precision needs the human ratings issue #757 tracks.

### 💾 Peak memory, which is what bounds parallelism

| Aid | Peak RSS |
| --- | ---: |
| `verbatim` | **1,492 MB** |
| `support` | **1,477 MB** |
| `coverage`, `agenda` | 73 MB |
| `provenance` | 32 MB |
| `synthesis`, `uncited`, `quotation` | 23 MB |

`verbatim` and `support` hold nearly all of both the wall-clock (97% on
the worst row) and the memory, so running the nine concurrently saves
little and costs close to 3 GB from those two processes alone.

### 📄 Only three aids render

`--formats md` against the default `md,tex,pdf` on the 5,723-word
chapter saves **about 2.5 s a run**: `provenance` 1,502 to 140 ms,
`coverage` 1,390 to 304, `agenda` 1,822 to 525. The other six write a
report only under `--write`.

### ⚠ Three figures to read carefully

- **`quotation`'s ~90 ms is unmeasured, not cheap.** No dossier on this
  host carried a `quote:` line, so it found no work; it needs
  re-measuring on a draft that has them.
- **Tier 3 is not cached, deliberately**
  ([PLAGIARISM.md](PLAGIARISM.md#-how-the-tiers-were-chosen)): three
  scans of an unchanged draft measured 20,172 / 20,141 / 20,340 ms.
  Tiers 1 and 2 are cached and sub-second after the first run.
- **`support`'s 21-62 s does not warm up.** Each invocation is a fresh
  process that loads the model again; there is no cheaper second run.

## ⚡ What a drift sweep costs

`python -m chitragupta.draft dossier status --all` is meant to run
**after every sync**, so it has to be cheap enough to be habitual. It
builds a BM25 index in memory and discards it rather than calling
`chitragupta.retrieval.search()`, which would rewrite
`content/retrieval_index.json` on every inspection;
[DRAFT-ITERATION.md](DRAFT-ITERATION.md#-why-the-new-papers-are-not-found-with-search)
is the argument, and this is the price.

Bare `python` (it is stdlib-only), medians of 5 runs over 646 ledger
rows and 47.4 MB of parsed text. It never opens a PDF:

| Dossiers swept | Cold (no index cache) | Warm (cache from a prior `search()`) |
| --- | --- | --- |
| 1 | 2.032s | 0.218s |
| 10 | 2.036s | 0.257s |
| 50 | 2.227s | 0.436s |

**Fifty dossiers cost 0.19s more than one**, ~4ms each, because the
corpus is tokenised once per sweep. Dossiers that logged no retrieval
queries never build an index (0.040s for 50). Cold cost is linear in
corpus size (5.857s on a generated 2000-document corpus), and a warm
cache is 5.1-9.3x faster. **About two seconds after a sync, and it does
not grow with your drafts.**
[bench/RESULTS.md](https://github.com/prasadtalasila/chitragupta/blob/main/bench/RESULTS.md)
has the spread and what the measurement excludes.

## 🔁 What raising the worker count costs in reproducibility

The one cost of parallelism not measured in seconds: **the more workers,
the less reproducible the parse.** Docling groups dense reference blocks
differently under contention, which changes the parsed text and the
passage spans quoted from it. Over all 501 documents ~1.4% came back
with different text and ~1.0% with a different quotable passage; two
runs of the *same* configuration differ at roughly a third of that rate
(5 of 572 comparisons in bytes, 2 in passage text). **One GPU lowers the
rate but does not remove it**, and serial parsing has not been observed
to vary. All of this was measured with `[parser].ocr` and
`[parser].formulas` off; neither has a measured rate. Count differing
passages, not bytes, when comparing runs.

**The full contract is
[ARCHITECTURE.md's "What is reproducible, and what is not"](ARCHITECTURE.md#-what-is-reproducible-and-what-is-not)**.

### 🎲 Why there is no reproducibility *rate* here, only an order of magnitude

A single pair of runs cannot tell two rates apart: eight pairs at one
fixed configuration returned **0, 1, 3, 4, 4, 4, 5 and 6** differing
documents of 300 (2026-09-08). Read every percentage above as an order
of magnitude ("about one document in a hundred, more with more GPUs").
Showing that a rate has moved needs several pairs per arm on both sides
of the change; `bench/RESULTS.md`'s "Power, stated plainly" section
carries the rule.

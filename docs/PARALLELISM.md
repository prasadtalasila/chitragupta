# ⚡ Parallelism: design and roadmap

Status: **implemented.** Written 2026-08-03. Updated 2026-08-24.

**Written for** someone changing how the parse path schedules work.
**Assumed:** [ARCHITECTURE.md](ARCHITECTURE.md). **Not covered here:**
which worker count to choose on your own machine -- that is
[PERFORMANCE.md](PERFORMANCE.md), written for someone running it.

How the PDF parse path runs work in parallel, what each component is for,
and what is planned next.

This is a **design document, not a history.** It describes the code as it
is. For what any of it *costs*, see [PERFORMANCE.md](PERFORMANCE.md); for
how a setting is spelled, [CONFIG.md](CONFIG.md); for the measurements
themselves — and the conclusions later ones overturned — `bench/RESULTS.md`
and `git log`.

## 🧭 Table of contents

- [Two words for two different things](#-two-words-for-two-different-things)
- [Where parallelism lives](#-where-parallelism-lives)
- [The parse path, end to end](#-the-parse-path-end-to-end)
- [Components](#-components)
- [Worker lifecycle](#-worker-lifecycle)
- [How the worker count is decided](#-how-the-worker-count-is-decided)
- [Failure and interruption](#-failure-and-interruption)
- [Concurrency control: one writer at a time](#-concurrency-control-one-writer-at-a-time)
- [What is deliberately serial](#-what-is-deliberately-serial)
- [Roadmap](#-roadmap)

## 🏷 Two words for two different things

This repository uses **parallelism** and **concurrency control** for
different mechanisms, and keeps them apart on purpose.

| Term | What it means here | Where it lives |
| --- | --- | --- |
| **Parallelism** | Several documents parsed at the same instant across several CPUs and GPUs, to cut the wall clock of **one** run | `chitragupta/sync_pool.py`'s worker pool, `chitragupta/pdf_text/` |
| **Concurrency control** | Stopping two **separate** runs from corrupting `content/` when they overlap | `chitragupta/runlock.py` |

Unrelated problems, unrelated solutions. Parallelism is an opt-in speed
feature, off by default; concurrency control is always on and exists
purely for safety. A reader who conflates them goes looking for the run
lock inside the worker pool and finds nothing.

Where no distinction is needed, "concurrent" is used loosely for "more
than one thing in flight" — matching `concurrent.futures`, the stdlib
module all of this is built on.

## 📍 Where parallelism lives

Only the PDF parse is parallel. Everything else is fast enough to be
serial, and is.

```text
  bib file ──► ledger ──► PARSE ──► retrieval ──► drafting ──► render
                            ▲
                            └── the only parallel stage
```

Two entry points reach it, sharing the same machinery:

```text
  python -m chitragupta.corpus sync                     python -m chitragupta.enrich
  (corpus layer: bib ──► text)           (enrichment layer, opt-in)
          │                                        │
          │ chitragupta/sync_pool.py                       │ chitragupta/enrich/docling_parse.py
          │ _parse_parallel()                      │ parse_corpus()
          │ _executor_for()                        │ chitragupta/enrich/_docling_pool.py
          │                                        │ _executor_for()
          └────────────────┬───────────────────────┘
                           ▼
                   chitragupta/pdf_text/
        resolve_workers · worker_ceiling · docling_threads
   process_pool_context · prestart_pool · init_worker · usable_devices
```

`chitragupta/enrich/_docling_pool.py` keeps its own `_executor_for` rather than
importing `sync_pool`'s, so `chitragupta/enrich/` never depends on the core
entry point — the dependency runs the other way everywhere else. Both
delegate every *policy* decision to `pdf_text`, so "how many workers, which
start method, which GPU" is answered in exactly one place.

**The two entry points disagree on what `[parser].backend` means to them.**
`chitragupta/sync.py` follows it: a `pdftotext`-configured sync never touches
GPU or docling-worker sizing at all. `chitragupta/enrich/` always runs
Docling — it has no other backend — regardless of what `[parser].backend`
says, since that setting governs the corpus layer's own parse, not
enrichment's. `resolve_workers`, `worker_ceiling`, `gpu_count` and
`usable_devices` therefore all take an explicit `docling: bool` argument
rather than reading `config.PARSER` themselves: `chitragupta/sync.py` passes
`config.PARSER == "docling"`, `chitragupta/enrich/` always passes `True`. A
version of this that read `config.PARSER` directly made every GPU on a
`pdftotext`-configured host (the shipped default) invisible to enrichment's
own pool — see #502.

## 🔄 The parse path, end to end

```text
                     ┌────────────────────────────────────────────┐
  MAIN PROCESS       │ 1. prestart_pool()                         │
  holds:             │    forkserver begins importing torch       │
   · the run lock    │    + docling in the background             │
   · the ledger      │ 2. read bibliography (~2.5s) ◄── overlaps  │
     (sqlite, both   │ 3. ledger: which documents need a parse?   │
      single-writer) │ 4. resolve_workers(n_docs)                 │
                     └─────────────────────┬──────────────────────┘
                                           ▼
                     ┌────────────────────────────────────────────┐
                     │ submit biggest-file-first (LPT)            │
                     │ one 675-page book picked up last would set │
                     │ the wall clock by itself                   │
                     └─────────────────────┬──────────────────────┘
                                           ▼
   ┌──────────────────── ProcessPoolExecutor ───────────────────────┐
   │ mp_context   = forkserver (or spawn)                           │
   │ initializer  = init_worker(counter, lock, usable_devices())    │
   │                                                                │
   │  ┌──────────┐  ┌──────────┐  ┌──────────┐    ┌──────────┐      │
   │  │ worker 0 │  │ worker 1 │  │ worker 2 │ …  │ worker N │      │
   │  │ cuda:d[0]│  │ cuda:d[1]│  │ cuda:d[2]│    │cuda:d[N%G│      │
   │  │converter │  │converter │  │converter │    │converter │      │
   │  │built once│  │built once│  │built once│    │built once│      │
   │  └────┬─────┘  └────┬─────┘  └────┬─────┘    └────┬─────┘      │
   └───────┼─────────────┼─────────────┼───────────────┼────────────┘
           └─────────────┴──────┬──────┴───────────────┘
                                │ (citekey, out_path | exception)
                                ▼
                     ┌────────────────────────────────────────────┐
  MAIN PROCESS ONLY  │ _as_they_land()  ── stall watchdog         │
                     │ ledger.mark_parsed / mark_parse_failed     │
                     │ results replayed in BIB ORDER, not         │
                     │ completion order                           │
                     └────────────────────────────────────────────┘
```

Only the extraction crosses the process boundary. Everything touching
shared state stays on the main process: **sqlite has a single writer**,
and replaying results in bibliography order is what makes two identical
runs print identically.

## 🧩 Components

All in `chitragupta/pdf_text/` unless noted.

### 🧮 `resolve_workers(n_docs, docling) -> (workers, complaint)`

```text
   what you asked for ──┐
   what the machine     ├──► min(…) ──► max(1, …) ──► workers
     can sustain      ──┤
   how many documents ──┘
     actually need it
```

The third ceiling matters more than it looks: standing up 12 workers to
parse 3 documents pays 12 model loads to save two documents' work.

An over-large request is **clamped and said out loud on stderr** — never
silently obeyed (which thrashes), never silently ignored (which leaves
someone believing they configured something they didn't).

### 📏 `worker_ceiling(docling)`

The machine ceiling alone: `allowed_cpus() // _CPUS_PER_DOCLING_WORKER`
when `docling` is true, `allowed_cpus()` otherwise. Separate from
`resolve_workers` because it is the one ceiling independent of the
document count, so `prestart_pool` can consult it before the bibliography
has been read.

`allowed_cpus()` counts the CPUs **this process may run on**
(`os.sched_getaffinity`), not the machine's. On a container the two
differ, and sizing off the machine's total oversubscribes.

> **The divisor of 4 is measurably too conservative** — 32 workers beat
> the 12 it permits by ~1.4x. Not yet changed; see [Roadmap](#-roadmap).

### 🧵 `docling_threads(workers)`

Divides docling's own `num_threads` down so `workers × threads` still
fits the machine. Capped at docling's default of 4, so a single-worker
run gets exactly what docling would have picked on its own.

Measured to matter far less than it looks: forcing 1/2/4/8 at 12 workers
moves a full-corpus run by 1.9% -- and 8 was only reachable by patching
the cap for the experiment, not through any setting. Kept because
dividing down is still the
correct thing to do when the product would exceed the machine, not
because it buys throughput.

### 🔀 `process_pool_context()`

Chooses the start method and configures it:

```text
   auto ──► forkserver, if the platform has it and CUDA is untouched
        └─► spawn otherwise (Windows, or CUDA already initialised)
```

**Never plain `fork`.** By the time the pool is built, this process holds
the run lock and the ledger open as live sqlite connections, and SQLite's
own documentation says not to carry an open connection across `fork()`.
It also measured no faster than `forkserver`.

### 🚀 `prestart_pool()`

Starts the forkserver *before* the caller reads the bibliography, so its
torch/docling import overlaps work that has to happen anyway.

```text
   without:  ├─ read bib 2.5s ─┤├─ preload 3.4s ─┤├─ pool ready
   with:     ├─ read bib 2.5s ─┤├─ pool ready
             ├─ preload 3.4s (background) ──┤
```

Declines when no pool is coming: not docling, `workers = 1`, or a machine
whose ceiling is 1 regardless of what was asked for.

### 🔧 `init_worker(counter, lock, devices)`

Pool initialiser. Each worker claims one CUDA device round-robin:

```text
   shared counter ──(under lock)──► i ──► cuda:devices[i % len(devices)]
```

From a shared counter rather than a PID or position, because a pool
creates workers lazily and numbers none of them. Without this, docling's
`AcceleratorDevice.AUTO` resolves to `cuda:0` in *every* process and every
worker piles onto one card.

`devices` is a **list of cards**, not a count, which is what keeps a card
that has no memory free out of the rotation entirely.

### 🖥 `usable_devices(docling)`

`gpu_count(docling)` narrowed to the cards with at least 2.5 GiB free
(`nvidia-smi --query-gpu=index,memory.free`), which is a docling worker's
~1.7 GiB of models plus its CUDA context, plus room to be wrong.

This exists because of a real run. GPU 0 was holding 44.4 GiB of a
previous run's orphaned workers when a 24-worker sync started. Four
workers were assigned to it, could not load a model at all, and — because
a worker that fails takes ~19s where a working one takes minutes, and the
pool hands the next document to whoever is free first — **those four
claimed and failed 334 of the corpus's 456 documents**. A poisoned worker
is not merely useless; it is an attractor for the whole queue.

Two details that matter:

- **`CUDA_VISIBLE_DEVICES` is applied to the mapping, not just the
  count.** nvidia-smi reports *physical* indices; `CUDA_VISIBLE_DEVICES=3,1`
  makes physical card 3 into this process's `cuda:0`. Checking free memory
  at index 0 would read the wrong card and skip the wrong one.
- **Every unknown means "usable".** No nvidia-smi, a reading it won't
  give, or a device list naming UUIDs (which can't be resolved to an index
  without torch) all leave the full list in place. Refusing a GPU on the
  strength of a measurement we don't have is the worse mistake, and the
  fallback below recovers from a bad assignment anyway.

If *every* card is full the list is empty and the run parses on the CPU —
measured 4.7x slower with OCR off, 1.8x with it on (OCR is CPU work
either way, so it narrows the gap). Slower, but a run that finishes.

### 🛟 CUDA-OOM fallback — `_extract_docling()`

The backstop for what `usable_devices()` can't see: another process can
fill a card in the second between the check and the model load. A parse
that fails with either OOM message shape — `CUDA out of memory` (torch's
own allocator) or `CUDA error: out of memory` (the driver refusing
underneath it; 240 of the 334 failures above, and the one with no
dedicated exception type) — demotes that worker to `cpu` for the rest of
the run and retries the document immediately. The converter cache is keyed
on the device, so moving it is what rebuilds it.

A CUDA OOM that survives the CPU retry is marked `transient`, so the
ledger retries it next run rather than writing the document off as
unparseable. It was the machine's fault, not the PDF's.

### 🔢 `gpu_count(docling)`

`0` outright when `docling` is false — this pool has no GPU path.
Otherwise reads `nvidia-smi --list-gpus`, applying `CUDA_VISIBLE_DEVICES`
by hand since nvidia-smi ignores it and torch does not. Falls back to
torch only where the driver's CLI is absent — the point is to answer the
question without importing torch into the parent.

### ⏱ `_as_they_land()` — `chitragupta/sync_pool.py`

Yields futures as they complete, abandoning the run if the **whole pool**
goes silent for `[parser].stall_timeout`.

Deliberately not a per-document deadline: with several workers,
completions arrive constantly, so silence across the entire pool
distinguishes a hung worker from a merely slow document far better than
any per-document number could — which matters when the slowest legitimate
document takes 246s. A warning fires at half the budget first.

## ♻ Worker lifecycle

What a cold worker pays before producing anything:

```text
  forkserver:  fork ──► imports inherited ──► build converter ──► 1st convert
               ~0s          ~0s                    0.13s            5.17s
                                                              └─ models load here

  spawn:       exec ──► import torch+docling ──► build converter ──► 1st convert
               ~0.3s        3.24s                    0.13s            5.17s
```

The converter is **built once per worker and reused** across that
worker's whole shard: `DocumentConverter.initialized_pipelines` is an
*instance* attribute, so one converter per document reloads every model
per document.

The ~5s model load is per process and shareable by no start method, which
is why `forkserver` is worth a fixed 1–2s rather than a multiple.

## ⚖ How the worker count is decided

```text
  [parser].workers = 1       ──► strictly serial: no pool, no subprocess,
                                  no pickling. The default.
  [parser].workers = <int>   ──┐
  [parser].workers = "auto"  ──┴─► min(requested, worker_ceiling(docling), n_docs)
```

`1` is not "a pool of one" — it is a different code path. A routine sync
re-parses zero-to-few documents, since the ledger skips anything whose
bytes have not changed, so pool setup would cost more than it saves.
Parallelism is for first-time and bulk runs.

Each backend gets the concurrency it can use:

| Backend | Executor | Why |
| --- | --- | --- |
| `docling` | `ProcessPoolExecutor` | in-process, holds the GIL |
| `pdftotext` | `ThreadPoolExecutor` | external subprocess, releases the GIL |

### 🧠 Why there is no memory term

Those three ceilings are CPU and workload; **RAM is not one of them**,
and that is now a decision rather than an omission. #585 reported the
gap: `"auto"` resolves to 24 workers on a 96-CPU host whatever the
machine's memory, and a docling worker extracting figures was measured in
the tens of GB, so the resolved width's worst case exceeded RAM by an
order of magnitude.

A memory ceiling was the obvious fix and is not the right one, because it
**cannot** be sufficient: the ceiling floors at one worker, and a single
worker parsing a large enough figure-heavy document exceeds RAM at any
width. Capping the pool would have made the failure rarer without making
it impossible.

The cause was per-document, not per-pool. Docling held every figure crop
until the end of the parse, so peak RSS scaled with a document's figure
count -- +8.95 GiB on one 99-page deck, and a 74.31 GiB failure at
`docling_image_scale = 6.0`. `chitragupta/enrich/_docling_crops.py` renders
each crop and releases it instead, which takes that term to +0.02 GiB and
makes it independent of document length, page size, image scale and
accelerator (`docs/PERFORMANCE.md` has the table; #600 has the
measurements).

With the per-document cost bounded at ~4.2 GiB, the arithmetic the issue
objected to comes out fine on the host that raised it: 24 workers is
~101 GiB against 251 GB. Under the old path the same 24 workers was
~313 GiB, which did not fit. So the width was a symptom, and no
`available_bytes // per_worker_estimate` term exists -- deliberately. Any
such term would need a per-worker byte estimate, which could only be
fitted from one corpus on one machine, and would then serialise runs on
smaller hosts that were never at risk. The same reasoning that keeps
`_CPUS_PER_DOCLING_WORKER` at 4 (see the roadmap below) applies to a
number nobody has measured across machines.

What remains true, and is not covered: a cgroup CPU *quota*
(`docker --cpus=2`) still throttles without narrowing the affinity mask,
so an explicit `[parser].workers` is still the answer there.

## 🐛 Failure and interruption

| Event | Behaviour |
| --- | --- |
| One document fails | Reported, marked `parse_failed` as **deterministic** — the backend read this PDF and could not parse it, so it is **not** retried until the file changes or `--reparse`. The batch continues |
| One document runs out of time | `[parser].document_timeout` expired: reported, marked `parse_failed`, and **named in the summary on its own line** — the fix is that setting, not the PDF, so it is **not** retried until `--reparse`. The batch continues |
| A worker dies (OOM killer) | `BrokenProcessPool` is handled: it takes the whole pool, so **every document without a result yet** is marked a transient failure -- the run still writes its ledger, prints its summary, and exits nonzero |
| The pool goes silent | Watchdog warns at half `stall_timeout`, then abandons the outstanding documents as **transient** failures — they were never given a fair attempt, so they are retried next run |
| Ctrl+C | `interrupt_guard` terminates workers (SIGTERM, grace period, then kill) and `os._exit`s |

**The enrichment pool answers a dead worker differently, and the rows
above are the corpus layer's.** Since #584,
`chitragupta/enrich/_docling_pool.py` rebuilds the pool and hands the
unfinished jobs back to it, up to `_MAX_POOL_REBUILDS` (2) more times --
halving `workers` each time, because memory pressure is the realistic
cause of a death and retrying at the same width reproduces it, and
handing the jobs over smallest-first, because the document that killed
the pool cannot be identified but is disproportionately the one
biggest-first submitted first. Only what no pool landed is reported
failed. A rebuilt pool that lands nothing at all ends the loop early
rather than spending another build's model loads on the same answer.

`sync_pool.py` deliberately does not do this: its unfinished documents
are marked *transient* and retried on the next run, and one of its
documents costs seconds where a docling parse costs minutes -- so
abandoning a batch there is not the same size of mistake.

Ctrl+C needs an explicit SIGINT handler because `except KeyboardInterrupt`
around the result loop **does not work**: the loop stops consuming, the
handler never runs, and the process sits until in-flight workers finish —
minutes per document with docling.

Skipping interpreter shutdown is safe because the ledger commits
incrementally and synchronously: whatever finished is already on disk.

## 🔒 Concurrency control: one writer at a time

A separate mechanism for a separate problem — two *runs* overlapping, not
two documents.

```text
  run A ──► content/pipeline.lock.db ──► BEGIN IMMEDIATE ──► holds it
  run B ──► SQLITE_BUSY ──► exit 2, naming the holder's pid, host and age
  readers (citation_gate, retrieval, ledger) ──► unaffected throughout
```

A dedicated sqlite file rather than the ledger itself, so holding the
lock does not force the ledger's six commit points into one transaction
([DESIGN.md](DESIGN.md) has where they are, and why the one that batches
the bibliography-upsert loop still keeps finished rows on a crash).
`BEGIN IMMEDIATE` takes a RESERVED lock, which does not block readers, and
after `kill -9` it is released immediately — staleness handles itself,
with no PID liveness check and no platform-specific code.

Full conflict policy in [DESIGN.md](DESIGN.md).

## 🚫 What is deliberately serial

- **Ledger writes** — sqlite has a single writer.
- **Result application** — replayed in bibliography order, so output is
  reproducible run to run.
- **The default** — `workers = 1` until someone opts in.
- **Everything outside the parse** — retrieval, gating and rendering are
  fast enough that concurrency would add risk for no measurable gain.

## 🗺 Roadmap

Ordered by measured benefit over risk. Figures in
[PERFORMANCE.md](PERFORMANCE.md).

### ▶ 1. Stop hard-coding `_CPUS_PER_DOCLING_WORKER = 4`

**The largest known win: ~1.4x.** The constant models a docling worker as
occupying 4 CPUs; measured, it occupies closer to one. 32 workers beat
the 12 the constant permits, and docling's `num_threads` is worth 1.9%.

The target is a *region*, not a point: 32 and 48 workers land within 0.9%
of each other over three runs each, so the fix is "a much smaller
divisor", not a specific replacement number.

Blocked on generality rather than effort: validated on one machine and
one corpus, and a CPU-only machine — where the GPU does none of the work —
would likely want a different value. Wants a per-backend measured default,
or a short calibration run.

### ▶ 2. Selective OCR

OCR costs 2.08x serially and up to 4.79x in parallel, to recover content
in a minority of documents: of 16 sampled, 8 changed and ~2 materially.
Detecting bitmap-heavy pages cheaply and running OCR only there converts
a global tax into a per-document one.

### ▶ 3. Cache the model load across runs

~5s per worker per run, shareable by no start method. Irrelevant to a
bulk parse, dominant for a three-document top-up. Needs a resident pool,
which is a large change to a pipeline whose appeal is being a batch job.

### ▶ 4. Batch inference across documents

Each worker uses ~7% of a GPU. Batching would use the cards properly, but
docling exposes no batch API — upstream work, not local.

### 🚫 Not planned

- **Intra-document splitting.** The 675-page outlier looks like a
  critical-path problem and is not at this corpus size: its floor binds
  only beyond ~35x parallelism, and LPT scheduling already handles it.
- **Threads for docling.** It holds the GIL.
- **Bit-reproducible output under load.** docling exposes no determinism
  setting, and torch's *raises* rather than degrades on ops with no
  deterministic implementation. What that costs is stated artifact by
  artifact in
  [ARCHITECTURE.md](ARCHITECTURE.md#-what-is-reproducible-and-what-is-not);
  it is a real cost of raising `workers`, not only a curiosity.

### ❓ Open questions

Gaps, not tasks.

- **Does the clamp finding generalise** past one machine and one corpus?
  Blocks item 1 above.
- **Where is the OCR optimum?** Swept only to 24 workers, still improving
  there.

What *is* settled: past ~32 workers the curve **plateaus rather than
reversing** — 32 and 48 land within 0.9% of each other over three runs
each. Two costs flatten it, both growing with the pool: per-worker
startup rises to 12.7% of the run at 48 workers, and the CPU climbs from
56% to 78% busy host-wide. Neither the GPUs, `num_threads`, nor the long-document
tail is involved. So the divisor above is much too large — but which
smaller value to use is exactly what the first open question blocks.

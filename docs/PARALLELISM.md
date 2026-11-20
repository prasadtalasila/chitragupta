# ⚡ Parallelism: design and roadmap

Status: **implemented.**

**Written for** someone changing how the parse path schedules work.
**Assumed:** [ARCHITECTURE.md](ARCHITECTURE.md). **Not covered here:**
which worker count to choose on your own machine; that is
[PERFORMANCE.md](PERFORMANCE.md), written for someone running it.

## 🏷 Two words for two different things

This repository uses **parallelism** and **concurrency control** for
different mechanisms, and keeps them apart on purpose.

| Term | What it means here | Where it lives |
| --- | --- | --- |
| **Parallelism** | Several documents parsed at the same instant across several CPUs and GPUs, to cut the wall clock of **one** run | `chitragupta/sync_pool.py`'s worker pool, `chitragupta/pdf_text/` |
| **Concurrency control** | Stopping two **separate** runs from corrupting `content/` when they overlap | `chitragupta/runlock.py` |

Parallelism is an opt-in speed feature, off by default; concurrency
control is always on and exists purely for safety. Elsewhere,
"concurrent" loosely means "more than one thing in flight", as in
`concurrent.futures`.

## 📍 Where parallelism lives

Only the PDF parse is parallel.

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

`chitragupta/enrich/_docling_pool.py` keeps its own `_executor_for` so
that `chitragupta/enrich/` never depends on the core entry point. Both
delegate every *policy* decision to `pdf_text`, so "how many workers,
which start method, which GPU" is answered in one place.

**The two entry points disagree on what `[parser].backend` means.**
`chitragupta/sync.py` follows it; `chitragupta/enrich/` always runs
Docling. So `resolve_workers`, `worker_ceiling`, `gpu_count` and
`usable_devices` take an explicit `docling: bool` (sync passes
`config.PARSER == "docling"`, enrich passes `True`). Reading
`config.PARSER` directly would hide every GPU on a `pdftotext`-configured
host (the shipped default) from enrichment's pool.

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
and bibliography-order replay makes identical runs print identically.

## 🧩 Components

All in `chitragupta/pdf_text/` unless noted.

### 🧮 `resolve_workers(n_docs, docling) -> (workers, complaint)`

The minimum of what you asked for, what the machine can sustain and how many
documents need a parse, floored at 1. The last ceiling stops 12 workers paying
12 model loads to parse 3 documents. An over-large request is **clamped and said
out loud on stderr**, never silently obeyed (which thrashes) or silently
ignored.

### 📏 `worker_ceiling(docling)`

The machine ceiling alone: `allowed_cpus() // _CPUS_PER_DOCLING_WORKER`
when `docling` is true, `allowed_cpus()` otherwise. It is independent of
the document count, so `prestart_pool` can consult it before the
bibliography is read. `allowed_cpus()` counts the CPUs **this process may
run on** (`os.sched_getaffinity`), which in a container is fewer than the
machine's.

> **The divisor of 4 is measurably too conservative**: 32 workers beat
> the 12 it permits by ~1.4x. Not yet changed; see [Roadmap](#-roadmap).

### 🧵 `docling_threads(workers)`

Divides docling's `num_threads` down so `workers × threads` fits the
machine, capped at docling's default of 4. Forcing 1/2/4/8 at 12 workers
moves a full-corpus run by only 1.9%; it is kept because dividing down
is still correct when the product would exceed the machine.

### 🔀 `process_pool_context()`

Chooses `forkserver` if the platform has it and CUDA is untouched, `spawn`
otherwise. **Never plain `fork`.** This process holds the run lock and the
ledger as live sqlite connections, which SQLite's documentation says not to
carry across `fork()`. It also measured no faster than `forkserver`.

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

Pool initialiser. Each worker takes index `i` from a shared counter
under a lock and claims `cuda:devices[i % len(devices)]`, because a pool
creates workers lazily and numbers none of them. Without it, docling's `AcceleratorDevice.AUTO`
resolves to `cuda:0` in every process. `devices` is a **list of cards**,
not a count, so a card with no memory free stays out of the rotation.

### 🖥 `usable_devices(docling)`

`gpu_count(docling)` narrowed to the cards with at least 2.5 GiB free
(a docling worker's ~1.7 GiB of models, its CUDA context, and margin).

A worker on a full card fails in ~19s, and the pool hands the next
document to whoever is free first, so it draws in the whole queue: in
one real run, four such workers **claimed and failed 334 of 456
documents**.

Two details:

- **`CUDA_VISIBLE_DEVICES` is applied to the mapping, not just the
  count.** nvidia-smi reports *physical* indices, so with
  `CUDA_VISIBLE_DEVICES=3,1` this process's `cuda:0` is physical card 3.
- **Every unknown means "usable".** No nvidia-smi, an unreadable
  value, or a device list naming UUIDs all leave the full list in place.
  Refusing a GPU without a measurement is the worse mistake, and the
  fallback below recovers from a bad assignment anyway.

If *every* card is full the run parses on the CPU, 4.7x slower with OCR
off and 1.8x with it on, but it finishes.

### 🛟 CUDA-OOM fallback in `_extract_docling()`

The backstop for a card filled between the check and the model load. A
parse that fails with `CUDA out of memory` (torch's allocator) or
`CUDA error: out of memory` (the driver; 240 of the 334 failures above)
demotes that worker to `cpu` for the rest of the run, rebuilding its
device-keyed converter, and retries the document at once. An OOM that
survives the CPU retry is marked `transient`.

### 🔢 `gpu_count(docling)`

`0` when `docling` is false. Otherwise reads `nvidia-smi --list-gpus`,
applying `CUDA_VISIBLE_DEVICES` by hand since nvidia-smi ignores it, and
falls back to torch only where the driver's CLI is absent, so the parent
need not import torch.

### ⏱ `_as_they_land()` in `chitragupta/sync_pool.py`

Yields futures as they complete, abandoning the run if the **whole pool**
goes silent for `[parser].stall_timeout`. Deliberately not a
per-document deadline: with several workers, completions arrive
constantly, so pool-wide silence separates a hung worker from a slow
document (the slowest legitimate one takes 246s) better than any
per-document number. A warning fires at half the budget.

## ♻ Worker lifecycle

What a cold worker pays before producing anything:

```text
  forkserver:  fork ──► imports inherited ──► build converter ──► 1st convert
               ~0s          ~0s                    0.13s            5.17s
                                                              └─ models load here

  spawn:       exec ──► import torch+docling ──► build converter ──► 1st convert
               ~0.3s        3.24s                    0.13s            5.17s
```

The converter is **built once per worker and reused**:
`DocumentConverter.initialized_pipelines` is an *instance* attribute, so
one converter per document would reload every model per document. The
~5s model load is per process and shareable by no start method, which is
why `forkserver` saves a fixed 1-2s rather than a multiple.

## ⚖ How the worker count is decided

```text
  [parser].workers = 1       ──► strictly serial: no pool, no subprocess,
                                  no pickling. The default.
  [parser].workers = <int>   ──┐
  [parser].workers = "auto"  ──┴─► min(requested, worker_ceiling(docling), n_docs)
```

`1` is a different code path, not "a pool of one": a routine sync
re-parses few documents, so pool setup would cost more than it saves.

| Backend | Executor | Why |
| --- | --- | --- |
| `docling` | `ProcessPoolExecutor` | in-process, holds the GIL |
| `pdftotext` | `ThreadPoolExecutor` | external subprocess, releases the GIL |

### 🧠 Why there is no memory term

**RAM is not one of the ceilings**, by design: `"auto"` resolves to 24
workers on a 96-CPU host whatever its memory. A memory ceiling floors at
one worker, and a single worker whose memory grows with the document
exceeds RAM at any width, so it would make failure rarer without making
it impossible. The per-document term is bounded instead:
`chitragupta/enrich/_docling_crops.py` renders each figure crop and
releases it, so a docling worker peaks at about 4.2 GiB whatever the
document ([PERFORMANCE.md](PERFORMANCE.md#-memory-bounded-per-document)).
At that bound, 24 workers is ~101 GiB against 251 GB on that host.

No `available_bytes // per_worker_estimate` term exists: the estimate
could only be fitted from one corpus on one machine, and would serialise
runs on smaller hosts never at risk.

Not covered: a cgroup CPU *quota* (`docker --cpus=2`) throttles without
narrowing the affinity mask, so set `[parser].workers` explicitly there.

## 🐛 Failure and interruption

| Event | Behaviour |
| --- | --- |
| One document fails | Marked `parse_failed` as **deterministic**, **not** retried until the file changes or `--reparse`. The batch continues |
| One document runs out of time | `[parser].document_timeout` expired: marked `parse_failed` and **named in the summary on its own line**. The fix is that setting, so it is **not** retried until `--reparse`. The batch continues |
| Writing one document's output fails | An `OSError` (disk full, permissions) is the machine, not the PDF: a **transient** failure, retried next run. The batch continues |
| A worker dies (OOM killer) | `BrokenProcessPool` takes the whole pool, so **every document without a result yet** is a transient failure. The run still writes its ledger, prints its summary, and exits nonzero |
| The pool goes silent | Watchdog warns at half `stall_timeout`, then abandons the outstanding documents as **transient** failures, retried next run |
| Ctrl+C | `interrupt_guard` terminates workers (SIGTERM, grace period, then kill) and `os._exit`s |

These rows are the corpus layer's. **The enrichment pool answers a dead
worker differently:** `chitragupta/enrich/_docling_pool.py` rebuilds the
pool up to `_MAX_POOL_REBUILDS` (2) more times, halving `workers` each
time (memory pressure is the realistic cause) and resubmitting
smallest-first (the unidentifiable culprit was likely submitted early by
biggest-first). A rebuilt pool that lands nothing ends the loop early. `sync_pool.py`
deliberately does not do this: its unfinished documents are retried next
run, and each costs seconds where a docling parse costs minutes.

Ctrl+C needs an explicit SIGINT handler because `except KeyboardInterrupt`
around the result loop **does not work**: the loop stops consuming and
the process sits until in-flight workers finish. Skipping interpreter
shutdown is safe because the ledger commits incrementally: whatever
finished is already on disk.

## 🔒 Concurrency control: one writer at a time

A separate mechanism handles a separate problem: two *runs* overlapping,
as opposed to two documents.

```text
  run A ──► content/pipeline.lock.db ──► BEGIN IMMEDIATE ──► holds it
  run B ──► SQLITE_BUSY ──► exit 2, naming the holder's pid, host and age
  readers (citation_gate, retrieval, ledger) ──► unaffected throughout
```

The lock is a dedicated sqlite file, not the ledger, so holding it does
not force the ledger's six commit points into one transaction.
`BEGIN IMMEDIATE` takes a RESERVED lock, which does not block readers and
is released immediately after `kill -9`, so staleness needs no PID check
and no platform-specific code. [DESIGN.md](DESIGN.md) has the commit
points, why the batched bibliography-upsert loop still keeps finished
rows on a crash, and the full conflict policy.

## 🚫 What is deliberately serial

Ledger writes (sqlite has a single writer), result application (in
bibliography order, for reproducible output), the default
(`workers = 1`), and everything outside the parse, where concurrency
would add risk for no measurable gain.

## 🗺 Roadmap

Ordered by measured benefit over risk. Figures in
[PERFORMANCE.md](PERFORMANCE.md).

### ▶ 1. Stop hard-coding `_CPUS_PER_DOCLING_WORKER = 4`

The largest known win, at ~1.4x. The constant models a docling worker
as occupying 4 CPUs; measured, it is closer to one, and 32 workers beat
the 12 it permits. The target is a region: 32 and 48 workers land within
0.9% of each other over three runs each, so the fix is "a much smaller
divisor". What blocks it is generality: it was validated on one machine
and one corpus, and a CPU-only machine would likely want a different
value. It needs a per-backend measured default, or a short calibration
run.

### ▶ 2. Selective OCR

OCR costs 2.1x to 2.9x serially and 3.1x to 4.8x at 12 to 24 workers,
to recover content in a minority of documents (of 16 sampled, ~2
materially). Running it only on bitmap-heavy pages would make a global
tax per-document.

### ▶ 3. Cache the model load across runs

~5s per worker per run: irrelevant to a bulk parse, dominant for a
three-document top-up. Needs a resident pool, a large change to a batch
pipeline.

### ▶ 4. Batch inference across documents

Each worker uses ~7% of a GPU. Batching would use the cards properly, but
docling exposes no batch API, so this is upstream work.

### 🚫 Not planned

- **Intra-document splitting.** The 675-page outlier's floor binds only
  beyond ~35x parallelism, and LPT scheduling already handles it.
- **Threads for docling.** It holds the GIL.
- **Bit-reproducible output under load.** docling exposes no determinism
  setting, and torch's *raises* on ops with no deterministic
  implementation. The cost is stated in
  [ARCHITECTURE.md](ARCHITECTURE.md#-what-is-reproducible-and-what-is-not).

### ❓ Open questions

- **Does the clamp finding generalise** past one machine and one corpus?
  Blocks item 1 above.
- **Where is the OCR optimum?** Swept only to 24 workers, still improving
  there.

Settled: past ~32 workers the curve **plateaus rather than reversing**.
Per-worker startup (12.7% of the run at 48 workers) and host CPU (56% to
78% busy) flatten it; the GPUs, `num_threads` and the long-document tail
do not.

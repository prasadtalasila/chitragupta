# 🏗 Design

Status: **reasoning document.**

Why this pipeline refuses what it refuses.

**Written for** someone changing how runs interact, fail, or reject each
other (adding a stage, a failure mode, or a form of concurrency) who
needs the rule a change should be checked against rather than a map of
what exists.

**Not covered here:** what actually runs and what each part writes
([ARCHITECTURE.md](ARCHITECTURE.md)), what any of it costs
([PERFORMANCE.md](PERFORMANCE.md)), and how the parse path is built
([PARALLELISM.md](PARALLELISM.md)). This document is the *rationale*;
ARCHITECTURE.md is the map. Where they touch the same subject,
ARCHITECTURE.md states the behaviour and this states why it was chosen
over the alternative.

## 🧭 Table of contents

- [Repository constraints and operating model](#-repository-constraints-and-operating-model)
- [Concurrency and conflict policy](#-concurrency-and-conflict-policy)
- [Parallelism and resource design](#-parallelism-and-resource-design)
- [What happens to prose a person supplies](#-what-happens-to-prose-a-person-supplies)
- [Parser backends](#-parser-backends)

## 🎯 Repository constraints and operating model

The repository is designed around a few hard constraints that strongly shape the
architecture:

1. **Never fabricate a citekey**
   - Citekeys must come from `papers/bibliography.bib` and be synchronized into
     `content/ledger.sqlite`.
   - Drafts must pass `python -m chitragupta.draft gate` before being considered
     valid.
   - This is the repo's primary safety invariant.

2. **Four layers**
   - Corpus layer: deterministic content maintenance (`python -m
     chitragupta.corpus sync`).
   - Drafting layer: generative drafting via the Claude Code skills.
   - Enrichment layer: optional heavier processing (`python -m chitragupta.enrich`).
   - Review layer: advisory aids over a finished draft (`python -m chitragupta.review`),
     run by hand and never blocking. They stay outside the automatic chain.
   - [ARCHITECTURE.md](ARCHITECTURE.md#-the-four-layers) is the map; this
     lists them only to say what the constraint is.

3. **Config and host variability are first-class concerns**
   - `config.toml` is the single source of configuration.
   - Stages must probe for binaries/services rather than assume availability.
   - Missing dependencies should degrade to honest reporting, not crashes or
     silent success.

4. **Incremental processing is a load-bearing design goal**
   - `ledger_upsert.py` uses stat-before-hash skipping.
   - `retrieval_cache.py` caches term-frequency stats.
   - `embed_index.py` skips unchanged chunks, and `doc_vectors.py` caches
     the topic model's document embeddings.
   - `docling_parse.py` fingerprints each PDF by (size, mtime).
   - The intent is to avoid reprocessing unchanged material.

5. **Parallelism is opt-in, and bounded by the host rather than by the
   request**
   - [Parallelism and resource design](#-parallelism-and-resource-design)
     below has the rules.

## 🚦 Concurrency and conflict policy

The rule the rest of this section implements. Every change to how runs
interact, fail, or refuse each other should be checked against it, in
this order of precedence:

1. **Corpus integrity outranks availability.** When in doubt, fail
   visibly and record nothing. A visible failure costs a re-run; a silent
   wrong entry costs a false citation, which is the failure this whole
   repository exists to prevent.
2. **The ledger is the sole authority, and every state in it must be
   recoverable by re-running.** No failure may require hand-editing the
   ledger, and none may become permanently invisible: failures caused by
   the *run* are retried automatically; failures caused by the *document*
   are not re-parsed, but are reported with a nonzero exit on every run
   until resolved.
3. **Every abnormal exit releases the lock, kills its children, and
   leaves the ledger stating what did not complete.** A run may be
   refused, fail, or succeed; it may never end ambiguously.
4. **Because writers are serialised, no serial section may be
   unbounded.** Anything holding the lock must be observably making
   progress or be subject to a watchdog, and anything that kills work
   must warn before it acts.
5. **Exit codes are the API for unattended callers**: `0` corpus in sync;
   `1` a document failed to parse, human attention needed; `2` cycle
   skipped, no work lost; `3` everything parsed but the bibliography
   needs fixing. Exit 2 must not be able to persist indefinitely without
   escalation.
6. **The serial, default-configuration path does not change behaviour in
   a minor release.** Opt-in features may carry protective sub-defaults;
   anything else that changes what an existing invocation does is a major
   release.

Two worked examples of the precedence mattering. A document Docling only
half-parsed is discarded rather than stored (1 over availability). A
corrupt PDF is *not* retried, yet still fails the run every time (2:
never silent, but also never pointlessly expensive).

## ⚡ Parallelism and resource design

The parse path is the only part of this repository that runs work in
**parallel**: several documents at once, to cut the wall clock of a
single run. That is a different mechanism from the **concurrency
control** below, which stops two separate runs colliding; PARALLELISM.md
defines both and describes the components. This section states the
design rules the parse path settled on.

### ⚙ Opt-in, and clamped rather than obeyed

`[parser].workers` defaults to `1`, which takes a serial path with no
executor, no pickling and no subprocess. Incremental skipping means a
routine run has almost nothing to do, so pool setup would usually cost
more than it saves.

The resolved count is `min(requested, host ceiling, work available)`,
never below 1. Two parts of that are easy to get wrong:

- **The host ceiling counts `len(os.sched_getaffinity(0))`, not
  `os.cpu_count()`.** On a shared or containerised host these differ (96
  and 48 on the development machine), and sizing off the larger number
  spawns workers that only deschedule each other. `sched_getaffinity` is
  Linux-only, so there is a guarded fallback for the Windows CI leg.
  Neither sees a cgroup CPU *quota*, which throttles without narrowing
  the affinity mask; an explicit worker count is the answer there.
- **A worker is not one CPU.** One Docling worker was measured holding
  ~300% CPU, so the ceiling divides by 4, a divisor a later full-corpus
  sweep found too conservative by roughly 2.5x (see docs/PERFORMANCE.md).
  Docling's own thread count is then divided down to match, keeping
  workers x threads inside the host.

An over-large request is clamped *and reported*. Silently obeying
thrashes; silently ignoring leaves someone believing they configured
something they did not.

### 🚦 Each backend gets the concurrency it can use

Processes for `docling`, which runs in-process and holds the GIL; threads
for `pdftotext`, an external subprocess that releases it. A process pool
around `pdftotext` would add pickling and spawn cost to buy the same
OS-level concurrency; threads around `docling` would serialise the very
work being overlapped.

The Docling pool never uses plain `fork`, because counting GPUs
initialises CUDA in the parent and a forked child inherits a broken CUDA
context from such a parent. `[parser].start_method = "auto"` (the
default) picks `forkserver`, which imports torch and docling once for
all workers, and falls back to `spawn`, where each worker re-imports
them, on a platform without it. The per-worker start-up cost is why
parallelism buys nothing on a small corpus and a great deal on a large
one.

### 🧵 The parent keeps what only the parent can do

Every ledger and cache write stays on the parent process: sqlite has a
single writer, and the parent is the only place that can order results
deterministically. Workers receive `(path, citekey, threads)` and return
`(citekey, out_path, exception)`. The exception is *returned* instead of
raised so that both the value and its type survive pickling, since
`sync` reports `ExtractionError` and `BackendUnavailable` differently.

Work is submitted longest-file-first. One 675-page document in this
corpus is 5% of all its pages; picked up last it would define the wall
clock by itself. The order uses file size and not page count, because
counting pages needs a PDF library the corpus layer deliberately does
not depend on.

### 🖥 Device assignment

Docling's `AcceleratorDevice.AUTO` resolves to `cuda:0` in *every*
process, so N workers contend for one card while the rest idle. Each
worker claims a device round-robin from a shared counter handed out under
a lock in the pool initialiser, and not from a PID or a worker index,
because a `ProcessPoolExecutor` neither numbers its workers nor
guarantees it starts all of them.

### ⚠ Failure and interruption are part of the design

Five distinct failure modes, each handled where it can be:

- **A dead worker.** `BrokenProcessPool` is caught rather than the run
  being aborted. Results are collected with `as_completed`, not `map`, so
  a pool that dies while the largest document is still running keeps the
  smaller ones that already finished. In the enrichment pool the run then
  **rebuilds the pool and hands the unfinished documents back to it**, up
  to twice, narrower each time and smallest-document-first. A dead
  worker costs the document it was holding and not the rest of the
  corpus; without the rebuild, one death failed 460 of 642 documents,
  most of which had never been opened. Only what no pool landed is reported a
  failure. `chitragupta/sync_pool.py` does not rebuild: there an
  unfinished document is marked *transient* and retried on the next run,
  which costs seconds rather than the minutes a docling parse costs.
- **A hung pool.** A stall watchdog gives up when *no* document completes
  for `[parser].stall_timeout`. It is deliberately not a per-document
  deadline: no single threshold separates a hung worker from the legitimate 246s
  document, but with several workers, total silence does. It uses
  `wait(FIRST_COMPLETED)` rather than `as_completed(timeout=...)`, whose
  timeout is measured from the original call and would fire on a healthy
  long run. On firing it terminates the workers, since abandoning them
  leaves in-flight jobs writing files for documents already reported
  failed.
- **A slow document.** `[parser].document_timeout` is honoured by each
  backend's own mechanism, and they are not equally strong: a real kill
  for `pdftotext`, a cooperative between-stages check for `docling`.
  It is reported apart from the failure below, and named citekey by
  citekey in the summary, because the two want opposite fixes: this one
  is the setting being too low for the host, not the PDF being
  unreadable. When a run produces any, the deterministic line stops
  offering its usual "fix or remove the PDF" remedy and defers to the
  per-cause warning instead, since printing both would leave the reader
  with two instructions that contradict each other. Which of the two a
  failure is comes from
  the backend, not from parsing its message: `pdftotext`'s
  `TimeoutExpired` and `docling`'s `FailureCategory.TIMEOUT` both set a
  `timed_out` mark on the exception, the same idiom the `transient` mark
  already uses.
- **A document the backend cannot read.** Distinguished from the other
  four by *cause*, recorded as such, and deliberately not retried: the
  backend already read this PDF and could not parse it, so re-reading it
  every run would spend the same minutes to reach the same answer, and a
  run that exits nonzero forever trains its reader to ignore that. It
  stays reported, with a nonzero exit, until fixed or removed;
  `sync --reparse` is the override.
- **Ctrl+C.** Handled by an explicit SIGINT handler, because an
  `except KeyboardInterrupt` around `as_completed()` never fires. The
  handler terminates workers (with a grace period then `kill()`, since
  native code does not honour SIGTERM promptly) and calls `os._exit`,
  skipping the atexit hook that would *join* those workers. This is safe
  only because the ledger commits incrementally, so finished work is
  already on disk: each document's row is written the moment its result
  lands, on the pool path as on the serial one.

### ⚖ Partial success is a failure

`DocumentConverter.convert(raises_on_error=True)` raises only on
`FAILURE`. A `PARTIAL_SUCCESS` returns a document that stops early, and
writing it would give the citation gate a source that silently ends at
page k of n. Both call sites therefore check the status explicitly and
raise *before* anything is written, so a partial parse leaves no output
and never enters the incremental cache.

Correspondingly, a `parse_failed` document whose failure was not
deterministic (it is marked transient, as after a dead worker) is
retried on the next run instead of skipped until its bytes change;
otherwise one dead worker would remove documents from the corpus
permanently. A deterministic failure is not retried, as the failure list
above states.

### 🔒 One writer at a time

`sync` and the enrichment layer share a lock over `content/`, because the
unsafe overlap is any-writer-against-any-writer: `sync` rewrites the
parsed text the enrichment layer reads. Each `.txt` is replaced whole (a
temp sibling, then `os.replace`, under both backends), so no reader sees
a torn file, and a full disk is a transient failure and not an
unreadable PDF. But a document re-parsed mid-run would still reach an
enrichment run as two versions, one per stage.

It is a dedicated sqlite file held under `BEGIN IMMEDIATE`, chosen by
measurement. A `BEGIN IMMEDIATE` holder takes a RESERVED lock, which
**does not block readers**, so `citation_gate`, retrieval and the
drafting skills keep working during a run. A second
writer gets `SQLITE_BUSY`. And a killed holder releases the lock
immediately, so staleness needs no PID liveness check and no
platform-specific branch.

Two rejected alternatives: an `O_EXCL` lock file needs exactly that
staleness heuristic, and locking the ledger itself would force a run
into one transaction, discarding the incremental commit points on a
crash. There are six of those: three in `chitragupta/ledger.py`, one in
`chitragupta/ledger_paths.py` (`mark_parsed`), one in
`chitragupta/ledger_upsert.py`, and one in `chitragupta/sync_decide.py`
that closes the whole bibliography-upsert loop in a single transaction,
so a no-op sync commits once rather than once per bib entry. That last
one is a *batch*, not a run, and it commits in a `finally`, so the
guarantee this paragraph turns on still holds: what finished is on disk.
A row is written whole or not at all, and the parse phase that follows
still commits per document.

Contention is detected by `sqlite_errorcode ==
SQLITE_BUSY` and not by message, since `OperationalError` also covers a
full disk and a corrupt file. The lock file is never deleted: unlinking
an open file fails on Windows, and a delete-then-recreate race on POSIX
gives two processes locks on different inodes.

### 🚫 What this does not cover

The lock serialises writers only; readers see mid-run state by design.

Nor does serialising writers make output reproducible: Docling groups dense
reference blocks differently under load, so parsed text and the passage sidecar
both vary at high worker counts. What that costs, artifact by artifact, is
[ARCHITECTURE.md's reproducibility contract](ARCHITECTURE.md#-what-is-reproducible-and-what-is-not).
That is the single, measured statement of it.

## ✍ What happens to prose a person supplies

The concrete case: you hand the pipeline an outline and one of its
sections contains two paragraphs of your own prose. Are they a *brief*
(steering, to be read and written from) or text you want to appear? The
two are indistinguishable as prose, so a skill must guess, and either
guess is wrong half the time. The fix for that ambiguity is to have
intent declared rather than inferred.

### 🚫 Why the answer is not "record who wrote it"

The obvious fix is to mark your paragraphs as yours, with a provenance
span the review aids skip. It is the wrong fix, for a reason that
applies beyond this feature.

A draft is revised. The drafting layer rewrites, shortens, re-scopes and
copy-edits the prose inside those markers, and it does so legitimately:
that is what `draft-reviser` is *for*. After one revision the span is
part your wording and part the model's, after two nobody can say which
part, and the marker still asserts a single author. The record becomes
false while still looking authoritative, and a review aid instructed to
skip it would then be skipping the model's prose on the strength of a
stale claim.

This repository already treats that failure as serious.
`sections.md` is regenerated immediately before a scan instead of being
trusted, and `math.md` desyncing on a reworded span is called out as a
hazard, both for the same reason: **recorded state that a later edit can
silently falsify is worse than no record**, because the check that reads
it now reports confidently about a document that no longer exists.
Authorship is the least recoverable instance of it. A citekey can be
re-derived from the draft and a section map rebuilt from its headings,
but nothing can recompute who wrote a sentence after the fact.

So there is **no author provenance, and no aid exemption built on
one.** Every sentence in a draft is measured the same way regardless of
who typed it first, which is the only accurate position after any
revision.

### ✅ What is declared instead: a brief, or a claim

Intent is declared *about the input*, where it is checked once and then
discharged. It is not attached to the output, where it would have to
survive every later edit:

| Declared as | In the draft? | What the pipeline owes you |
| --- | --- | --- |
| a **brief** | no | write the section from it; your wording is not preserved |
| a **claim** | no; it is rewritten | find a citekey supporting each assertion, and **report every sentence that could not be grounded** rather than shipping it |

Neither leaves a marker behind, because neither needs to: a brief has
been consumed by the time the draft exists, and a claim's grounding is
**re-checkable at any point** against the ledger. Authorship lacks that
property, which is why this split survives revision.

`claim` turns your paragraphs into an obligation the pipeline can
discharge honestly: *"I could not ground your third sentence in this
corpus"* is the output this project exists to produce, and it is
unavailable if the same paragraphs are copied through as text to
preserve.

**If you want your exact words in the draft, put them in the draft.**
They are then draft prose like any other: the gate checks any citekey in
them, and the advisory aids measure them alongside everything else,
as they do every sentence in a revised document.

Both are built: a `brief:` or `claim:` block per section of the
dossier's optional `outline.md` ([DOSSIER.md](DOSSIER.md) has the
format).

## 🗺 Where proposed work lives

This document describes what the pipeline does and why. **Proposals for
what it should do next are tracked in
[a standing issue](https://github.com/prasadtalasila/chitragupta/issues/54)**,
not here. A design document that also carries a wish list stops being
readable as a statement of current behaviour, and the wish list goes
stale faster than the design does. The parse path's own roadmap, which
is narrower and measured, is in
[PARALLELISM.md](PARALLELISM.md#-roadmap).

## 📄 Parser backends

[PDF-PARSER.md](PDF-PARSER.md) owns the backend comparison: the
tradeoffs, the two backends evaluated and removed, and the measured
speed figures. It is not restated here.

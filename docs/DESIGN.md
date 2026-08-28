# 🏗 Design

Status: **reasoning document.** Written 2026-08-02. Updated 2026-08-28.

Why this pipeline refuses what it refuses.

**Written for** someone changing how runs interact, fail, or reject each
other -- adding a stage, a failure mode, or a form of concurrency -- who
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
- [Whose prose is it?](#-whose-prose-is-it)
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
   - `ledger.py` uses stat-before-hash skipping.
   - `retrieval.py` caches term-frequency stats.
   - `embed_index.py` and `topic_model.py` cache embeddings.
   - `docling_parse.py` fingerprints each PDF by (size, mtime).
   - The intent is to avoid reprocessing unchanged material.

5. **Parallelism is opt-in, and bounded by the host rather than by the
   request**
   - `[parser].workers` defaults to `1`, so the default run is strictly
     serial -- no pool, no subprocesses. Incremental skipping means a
     routine run has almost nothing to do, and pool setup would cost more
     than it saves.
   - The resolved count is `min(requested, host ceiling, work available)`.
     The host ceiling counts CPUs *this process* may run on, not the
     machine's, and divides by the CPUs one worker actually occupies.
   - Only the parse call is dispatched. Every ledger and cache write
     stays on the parent process, because sqlite has a single writer and
     because the parent is the only place that can order results
     deterministically.
   - Backends get the kind of parallelism they can use: threads for
     `pdftotext` (external subprocess, releases the GIL), processes for
     `docling` (in-process, holds it), with one CUDA device per worker.

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
   refused, fail, or succeed -- never end ambiguously.
4. **Because writers are serialised, no serial section may be
   unbounded.** Anything holding the lock must be observably making
   progress or be subject to a watchdog, and anything that kills work
   must warn before it acts.
5. **Exit codes are the API for unattended callers**: `0` corpus in sync;
   `1` corpus not in sync, human attention needed; `2` cycle skipped, no
   work lost. Exit 2 must not be able to persist indefinitely without
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
**parallel** -- several documents at once, to cut the wall clock of a
single run. That is a different mechanism from the **concurrency
control** below, which stops two separate runs colliding; PARALLELISM.md
defines both and describes the components. The design rules the parse
path settled on are worth stating here.

### ⚙ Opt-in, and clamped rather than obeyed

`[parser].workers` defaults to `1`, which takes a genuinely serial path
-- no executor, no pickling, no subprocess. Incremental skipping means a
routine run has almost nothing to do, so pool setup would usually cost
more than it saves.

The resolved count is `min(requested, host ceiling, work available)`,
never below 1. Two parts of that are easy to get wrong:

- **The host ceiling counts `len(os.sched_getaffinity(0))`, not
  `os.cpu_count()`.** On a shared or containerised host these differ --
  96 and 48 on the development machine -- and sizing off the larger
  number spawns workers that only deschedule each other. `sched_getaffinity`
  is Linux-only, so there is a guarded fallback for the Windows CI leg.
  Neither sees a cgroup CPU *quota*, which throttles without narrowing
  the affinity mask; an explicit worker count is the answer there.
- **A worker is not one CPU.** One Docling worker was measured holding
  ~300% CPU, so the ceiling divides by 4 -- a divisor a later
  full-corpus sweep found too conservative by roughly 2.5x (see
  docs/PERFORMANCE.md). Docling's own thread count is
  then divided down to match, keeping workers x threads inside the host.

An over-large request is clamped *and reported*. Silently obeying
thrashes; silently ignoring leaves someone believing they configured
something they did not.

### 🚦 Each backend gets the concurrency it can use

Processes for `docling`, which runs in-process and holds the GIL; threads
for `pdftotext`, an external subprocess that releases it. A process pool
around `pdftotext` would add pickling and spawn cost to buy the same
OS-level concurrency; threads around `docling` would serialise exactly
the work being overlapped.

The Docling pool uses the `spawn` start method, because counting GPUs
initialises CUDA in the parent and a forked child inherits a broken CUDA
context from such a parent. The cost -- each worker re-imports torch and
docling -- is why parallelism buys nothing on a small corpus and a great
deal on a large one.

### 🧵 The parent keeps what only the parent can do

Every ledger and cache write stays on the parent process: sqlite has a
single writer, and the parent is the only place that can order results
deterministically. Workers receive `(path, citekey, threads)` and return
`(citekey, out_path, exception)` -- the exception is *returned* rather
than raised so that both the value and its type survive pickling, since
`sync` reports `ExtractionError` and `BackendUnavailable` differently.

Work is submitted longest-file-first. One 675-page document in this
corpus is 5% of all its pages; picked up last it would define the wall
clock by itself. File size rather than page count, because counting pages
needs a PDF library the corpus layer deliberately does not depend on.

### 🖥 Device assignment

Docling's `AcceleratorDevice.AUTO` resolves to `cuda:0` in *every*
process, so N workers contend for one card while the rest idle. Each
worker claims a device round-robin from a shared counter handed out under
a lock in the pool initialiser -- not from a PID or a worker index,
because a `ProcessPoolExecutor` neither numbers its workers nor
guarantees it starts all of them.

### ⚠ Failure and interruption are part of the design

Five distinct failure modes, each handled where it can be:

- **A dead worker.** `BrokenProcessPool` is caught and the unfinished
  documents are reported as failures rather than the run being aborted.
  Results are collected with `as_completed`, not `map`, so a pool that
  dies while the largest document is still running keeps the smaller ones
  that already finished.
- **A hung pool.** A stall watchdog gives up when *no* document completes
  for `[parser].stall_timeout`. Deliberately not a per-document deadline:
  no single threshold separates a hung worker from the legitimate 246s
  document, but with several workers, total silence does. It uses
  `wait(FIRST_COMPLETED)` rather than `as_completed(timeout=...)`, whose
  timeout is measured from the original call and would fire on a healthy
  long run. On firing it terminates the workers, since abandoning them
  leaves in-flight jobs writing files for documents already reported
  failed.
- **A slow document.** `[parser].document_timeout` is honoured by each
  backend's own mechanism, and they are not equally strong: a real kill
  for `pdftotext`, a cooperative between-stages check for `docling`.
  Reported apart from the failure below, and named citekey by citekey in
  the summary, because the two want opposite fixes: this one is the
  setting being too low for the host, not the PDF being unreadable. When
  a run produces any, the deterministic line stops offering its usual
  "fix or remove the PDF" remedy and defers to the per-cause warning
  instead -- printing both would leave the reader with two instructions
  that contradict each other. Which of the two a failure is comes from
  the backend, not from parsing its message: `pdftotext`'s
  `TimeoutExpired` and `docling`'s `FailureCategory.TIMEOUT` both set a
  `timed_out` mark on the exception, the same idiom the `transient` mark
  already uses.
- **A document the backend cannot read.** Distinguished from the four
  below by *cause*, recorded as such, and deliberately not retried: the
  backend already read this PDF and could not parse it, so re-reading it
  every run would spend the same minutes to reach the same answer, and a
  run that exits nonzero forever trains its reader to ignore that. It
  stays reported, with a nonzero exit, until fixed or removed --
  `sync --reparse` is the override.
- **Ctrl+C.** Handled by an explicit SIGINT handler, because an
  `except KeyboardInterrupt` around `as_completed()` never fires. The
  handler terminates workers -- with a grace period then `kill()`, since
  native code does not honour SIGTERM promptly -- and calls `os._exit`,
  skipping the atexit hook that would *join* those workers. Safe only
  because the ledger commits incrementally, so finished work is already
  on disk.

### ⚖ Partial success is a failure

`DocumentConverter.convert(raises_on_error=True)` raises only on
`FAILURE`. A `PARTIAL_SUCCESS` returns a document that stops early, and
writing it would give the citation gate a source that silently ends at
page k of n. Both call sites therefore check the status explicitly and
raise *before* anything is written, so a partial parse leaves no output
and never enters the incremental cache.

Correspondingly, a `parse_failed` document is retried on the next run
rather than skipped until its bytes change -- otherwise one dead worker
would remove documents from the corpus permanently.

### 🔒 One writer at a time

`sync` and the enrichment layer share a lock over `content/`, because the
unsafe overlap is any-writer-against-any-writer: `sync` writes parsed
text non-atomically and the enrichment layer reads those same files.

It is a dedicated sqlite file held under `BEGIN IMMEDIATE`, chosen from
measurement rather than taste. A `BEGIN IMMEDIATE` holder takes a
RESERVED lock, which **does not block readers** -- so `citation_gate`,
retrieval and the drafting skills keep working during a run. A second
writer gets `SQLITE_BUSY`. And a killed holder releases the lock
immediately, so staleness needs no PID liveness check and no
platform-specific branch.

Two rejected alternatives: an `O_EXCL` lock file needs exactly that
staleness heuristic, and locking the ledger itself would force a run into
one transaction, discarding `chitragupta/ledger.py`'s five incremental commit
points on a crash. Contention is detected by `sqlite_errorcode ==
SQLITE_BUSY` rather than by message, since `OperationalError` also covers
a full disk and a corrupt file, and the lock file is never deleted --
unlinking an open file fails on Windows, and a delete-then-recreate race
on POSIX gives two processes locks on different inodes.

### 🚫 What this does not cover

The lock serialises writers only; readers see mid-run state by design.

Nor does serialising writers make output reproducible: Docling groups
dense reference blocks differently under load, so parsed text and the
passage sidecar both vary at high worker counts. What that costs, artifact
by artifact, is
[ARCHITECTURE.md's reproducibility contract](ARCHITECTURE.md#-what-is-reproducible-and-what-is-not)
-- the single statement of it, measured rather than asserted.

## ✍ Whose prose is it?

A draft is assumed throughout this pipeline to have been written by a
skill. Nothing marks a span as human-authored, and the assumption is
load-bearing in more places than it looks -- so this section states what
breaks when a person writes prose into a draft themselves, and the one
rule that has to hold when that is fixed.

**The concrete case.** You hand the pipeline an outline and one of its
sections contains two paragraphs of your own prose. What are they? A
*brief* -- steering, to be read and then written from -- or *seed text*
you want to appear? The two are indistinguishable as prose, so a skill
must guess, and either guess is wrong half the time. **That ambiguity is
the defect**, not the presence of prose: the pipeline cannot infer intent
from wording, so intent has to be declared rather than inferred.

**What happens to unmarked human prose that lands in a draft.** Six
mechanisms read it as the drafter's output, and four of them will try to
change it:

| Mechanism | What it does to your paragraph |
| --- | --- |
| `review verbatim scan` | scans it against the corpus. If you paraphrased a paper you had just read, it reports overlap with no attribution path -- and `overlap-reviser` exists to rewrite exactly that |
| `review synthesis` | flags it for closing on fewer than two citekeys ([WRITING-STANDARDS.md](WRITING-STANDARDS.md) §11) |
| `draft style` | flags your spelling against `scope.md`'s recorded dialect (§8) |
| `draft-reviser` copy-edit mode | rewrites it to a convention you never applied to it |
| an uncited-prose report | flags it as ungrounded |
| **`draft gate`** | **fails if you typed a citekey the ledger does not hold** |

**The last row is the asymmetry, and it gives the rule:**

> An advisory aid may exclude a human-authored span. **The gate never
> does.**

A fabricated citekey is fabricated whoever typed it --
[CLAUDE.md](../CLAUDE.md)'s invariant admits no author exemption, and
adding one would put the pipeline's only hard guarantee behind a marker
a person controls. The advisory aids are in the opposite position: they
measure *how the drafter behaved*, and running them over a human's own
sentences is a category error that produces findings nobody can act on.
This is also why the fix is a marker rather than a configuration switch
-- the aids need to know *which span*, not whether to run.

**Why three declared kinds rather than one.** Given that intent must be
declared, the useful question is what a person actually wants when they
put prose in front of this pipeline, and there are three answers, not
one:

| Declared as | Appears in the draft? | What the pipeline owes you |
| --- | --- | --- |
| a **brief** | no | write the section from it; your wording is not preserved |
| **seed** text | yes, verbatim, inside a provenance marker | preserve it exactly; exclude it from the advisory aids; still gate it |
| a **claim** | no -- it is rewritten | find a citekey supporting each assertion, and **report every sentence that could not be grounded** rather than shipping it |

The third is the one worth building deliberately, because it is the only
one that turns a person's paragraphs into an obligation the pipeline can
discharge honestly. "I could not ground your third sentence in this
corpus" is precisely the output this project exists to produce, and it is
unavailable if the same two paragraphs are silently copied through as
seed text.

There is a symmetry worth noting with a design
[FEATURE-ROADMAP.md](FEATURE-ROADMAP.md) already records: the OpenScholar
sample labels *ungrounded* sentences (`(LLM Memory)`, `(Model-Generated)`)
rather than mixing them silently into cited prose. Marking human-authored
spans is the same instinct pointed the other way -- and the reason both
are worth doing is the same one, that a reader cannot audit what a
document does not distinguish.

None of this is built. The proposal is
`plans/outline-driven-drafting-and-manual-edits.md`.

## 🗺 Where proposed work lives

This document describes what the pipeline does and why. **Proposals for
what it should do next are tracked in
[issue #54](https://github.com/prasadtalasila/chitragupta/issues/54)**,
not here -- a design document that also carries a wish list stops being
readable as a statement of current behaviour, and the wish list goes
stale faster than the design does.

An earlier revision of this file ended with five unowned improvement
recommendations. Four became sequenced items in that issue (splitting
`retrieval.py`, section-aware chunking over hierarchical document
representations, reranking, and platform portability) and the fifth --
preserving richer per-document metadata -- is partly delivered by
`chitragupta/passages.py` and the Docling sidecar. The parse path's own roadmap,
which is narrower and measured, is in
[PARALLELISM.md](PARALLELISM.md#-roadmap).

## 📄 Parser backends

[PDF-PARSER.md](PDF-PARSER.md) owns the backend comparison -- the
tradeoffs, the two backends evaluated and removed, and the measured
speed figures. It is not restated here.

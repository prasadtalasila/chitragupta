# 🏗 Design

Status: **reasoning document.**

Why this pipeline refuses what it refuses.

**Written for** someone changing how runs interact, fail, or reject each
other (adding a stage, a failure mode, or a form of concurrency) who
needs the rule a change should be checked against rather than a map of
what exists.

**Not covered here:** what actually runs and what each part writes
([ARCHITECTURE.md](ARCHITECTURE.md), the map; this page says why each
behaviour was chosen over the alternative), what any of it costs
([PERFORMANCE.md](PERFORMANCE.md)), and how the parse path is built
([PARALLELISM.md](PARALLELISM.md)).

## 🎯 Repository constraints and operating model

A few hard constraints shape the architecture:

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
   - Review layer: advisory aids over a finished draft
     (`python -m chitragupta.review`), run by hand, never blocking, and
     outside the automatic chain.
   - [ARCHITECTURE.md](ARCHITECTURE.md#-the-four-layers) is the map.

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

5. **Parallelism is opt-in, and bounded by the host rather than by the
   request**
   - [Parallelism and resource design](#-parallelism-and-resource-design)
     below has the rules.

## 🚦 Concurrency and conflict policy

Every change to how runs interact, fail, or refuse each other should be
checked against these rules, in this order of precedence:

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
**parallel**, several documents at once within one run. That is distinct
from the **concurrency control** below, which stops two runs colliding;
[PARALLELISM.md](PARALLELISM.md) describes the components. This section
states the design rules.

### ⚙ Opt-in, and clamped rather than obeyed

`[parser].workers` defaults to `1`, a serial path with no executor,
pickling or subprocess. A routine run has almost nothing to do, so pool
setup would usually cost more than it saves.

The resolved count is `min(requested, host ceiling, work available)`,
never below 1. Two parts of that are easy to get wrong:

- **The host ceiling counts `len(os.sched_getaffinity(0))`, not
  `os.cpu_count()`.** On a shared or containerised host these differ,
  and sizing off the larger number spawns workers that only deschedule
  each other. A guarded fallback covers the Windows CI leg. Neither sees
  a cgroup CPU *quota*; an explicit worker count is the answer there.
- **A worker is not one CPU.** One Docling worker was measured holding
  ~300% CPU, so the ceiling divides by 4, a divisor a later full-corpus
  sweep found too conservative by roughly 2.5x (see docs/PERFORMANCE.md).
  Docling's own thread count is then divided down to match, keeping
  workers x threads inside the host.

An over-large request is clamped *and reported*: silently obeying
thrashes, and silently ignoring misleads.

### 🚦 Each backend gets the concurrency it can use

Processes for `docling`, which runs in-process and holds the GIL; threads
for `pdftotext`, an external subprocess that releases it. A process pool
around `pdftotext` would add pickling and spawn cost to buy the same
OS-level concurrency; threads around `docling` would serialise the very
work being overlapped.

The Docling pool never uses plain `fork`, because counting GPUs
initialises CUDA in the parent and a forked child inherits a broken CUDA
context. `[parser].start_method = "auto"` picks `forkserver`, which
imports torch and docling once for all workers, and falls back to
`spawn` where the platform lacks it. That per-worker start-up cost is
why parallelism buys nothing on a small corpus.

### 🧵 The parent keeps what only the parent can do

Every ledger and cache write stays on the parent process: sqlite has a
single writer, and the parent is the only place that can order results
deterministically. Workers receive `(path, citekey, threads)` and return
`(citekey, out_path, exception)`. The exception is *returned* instead of
raised so that both the value and its type survive pickling, since
`sync` reports `ExtractionError` and `BackendUnavailable` differently.

Work is submitted longest-file-first, because one 675-page document
picked up last would define the wall clock by itself. The order uses
file size, not page count, because counting pages needs a PDF library
the corpus layer deliberately does not depend on.

### 🖥 Device assignment

Docling's `AcceleratorDevice.AUTO` resolves to `cuda:0` in *every*
process. Each worker therefore claims a device round-robin from a shared
counter under a lock, not from a PID or worker index, because a
`ProcessPoolExecutor` neither numbers its workers nor guarantees it
starts all of them.

### ⚠ Failure and interruption are part of the design

Five distinct failure modes:

- **A dead worker.** `BrokenProcessPool` is caught rather than the run
  being aborted. Results are collected with `as_completed`, not `map`, so
  a pool that dies while the largest document is still running keeps the
  smaller ones that already finished. The enrichment pool then
  **rebuilds the pool and hands the unfinished documents back to it**, up
  to twice, narrower each time and smallest-document-first, so a dead
  worker costs only the document it held (without the rebuild, one death
  failed 460 of 642 documents). `chitragupta/sync_pool.py` does not
  rebuild: its unfinished documents are *transient* and retried next
  run, which costs seconds rather than a docling parse's minutes. Only
  what no pool landed is reported a failure.
- **A hung pool.** A stall watchdog gives up when *no* document
  completes for `[parser].stall_timeout`. It is deliberately not a
  per-document deadline: no threshold separates a hung worker from the
  legitimate 246s document, but pool-wide silence does. It uses
  `wait(FIRST_COMPLETED)`, not `as_completed(timeout=...)`, whose timeout
  runs from the original call and would fire on a healthy long run. On
  firing it terminates the workers, so no in-flight job writes files for
  a document already reported failed.
- **A slow document.** `[parser].document_timeout` is a real kill for
  `pdftotext` and a cooperative between-stages check for `docling`. It
  is reported apart from an unreadable document, citekey by citekey,
  because the fix is the setting, not the PDF; when a run has any, the
  deterministic line drops its "fix or remove the PDF" remedy so the two
  instructions do not contradict. The backend decides which it is, not
  message parsing: `pdftotext`'s `TimeoutExpired` and `docling`'s
  `FailureCategory.TIMEOUT` both set a `timed_out` mark on the exception,
  like the `transient` mark.
- **A document the backend cannot read.** Recorded by *cause* and
  deliberately not retried: re-reading it every run would spend the same
  minutes to reach the same answer, and a run that exits nonzero forever
  trains its reader to ignore that. It stays reported, with a nonzero
  exit, until fixed or removed; `sync --reparse` is the override.
- **Ctrl+C.** Handled by an explicit SIGINT handler, because an
  `except KeyboardInterrupt` around `as_completed()` never fires. The
  handler terminates workers (a grace period, then `kill()`, since native
  code does not honour SIGTERM promptly) and calls `os._exit`, skipping
  the atexit hook that would *join* them. This is safe only because the
  ledger writes each document's row the moment its result lands.

### ⚖ Partial success is a failure

`DocumentConverter.convert(raises_on_error=True)` raises only on
`FAILURE`. A `PARTIAL_SUCCESS` returns a document that stops early, and
writing it would give the citation gate a source that silently ends at
page k of n. Both call sites therefore check the status explicitly and
raise *before* anything is written, so a partial parse leaves no output
and never enters the incremental cache.

Correspondingly, a `parse_failed` document marked transient (as after
a dead worker) is retried on the next run instead of skipped until its
bytes change; otherwise one dead worker would remove documents from the
corpus permanently.

### 🔒 One writer at a time

`sync` and the enrichment layer share a lock over `content/`, because
`sync` rewrites the parsed text the enrichment layer reads. Each `.txt`
is replaced whole (a temp sibling, then `os.replace`), so no reader sees
a torn file and a full disk is a transient failure, not an unreadable
PDF. But a document re-parsed mid-run would still reach an enrichment
run as two versions, one per stage.

It is a dedicated sqlite file held under `BEGIN IMMEDIATE`, chosen by
measurement. The RESERVED lock **does not block readers**, so
`citation_gate`, retrieval and the drafting skills keep working during a
run. A second writer gets `SQLITE_BUSY`, and a killed holder releases
the lock immediately, so staleness needs no PID liveness check and no
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

Nor does serialising writers make output reproducible: Docling groups
dense reference blocks differently under load. What that costs is
[ARCHITECTURE.md's reproducibility contract](ARCHITECTURE.md#-what-is-reproducible-and-what-is-not).

## ✍ What happens to prose a person supplies

You hand the pipeline an outline whose section contains two paragraphs
of your own prose. Are they a *brief* (steering) or text you want to
appear? The two are indistinguishable as prose, so intent must be
declared rather than inferred.

### 🚫 Why the answer is not "record who wrote it"

The obvious fix is a provenance span marking your paragraphs as yours,
which the review aids skip. It is wrong, for a reason that applies
beyond this feature.

`draft-reviser` legitimately rewrites, shortens and copy-edits the prose
inside those markers. After one revision the span is part yours and part
the model's, after two nobody can say which, and the marker still
asserts a single author, so an aid told to skip it skips the model's
prose on a stale claim.

**Recorded state that a later edit can silently falsify is worse than no
record**, because the check that reads it reports confidently about a
document that no longer exists. That is why `sections.md` is regenerated
before a scan and `math.md` desync is called out as a hazard. Authorship
is the least recoverable case: a citekey can be re-derived from the
draft and a section map from its headings, but nothing can recompute who
wrote a sentence.

So there is **no author provenance, and no aid exemption built on
one.** Every sentence is measured the same way regardless of who typed
it first.

### ✅ What is declared instead: a brief, or a claim

Intent is declared *about the input*, where it is checked once and
discharged, not attached to the output, where it would have to survive
every later edit:

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
corpus"* is the output this project exists to produce, and copying the
paragraphs through would make it unavailable.

**If you want your exact words in the draft, put them in the draft.**
They are then draft prose like any other, gated and measured like every
sentence.

Both are built: a `brief:` or `claim:` block per section of the
dossier's optional `outline.md` ([DOSSIER.md](DOSSIER.md) has the
format).

## 🗺 Where proposed work lives

**Proposals for what the pipeline should do next are tracked in
[a standing issue](https://github.com/prasadtalasila/chitragupta/issues/54)**,
not here: a design document that carries a wish list stops reading as a
statement of current behaviour, and the wish list goes stale faster. The
parse path's narrower, measured roadmap is in
[PARALLELISM.md](PARALLELISM.md#-roadmap).

## 📄 Parser backends

[PDF-PARSER.md](PDF-PARSER.md) owns the backend comparison, including
the two backends evaluated and removed.

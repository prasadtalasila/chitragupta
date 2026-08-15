# Embedding Model Benchmark, Arm A (tier-3 overlap) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Benchmark the three documented drop-in embedding models
(`all-MiniLM-L6-v2`, `all-mpnet-base-v2`, `multi-qa-mpnet-base-dot-v1`)
against tier-3 overlap detection's existing capability and recall
harnesses, and record a comparison in `bench/RESULTS.md`.

**Architecture:** One new orchestrator script,
`bench/bench_embed_model_compare.py`, that shells out to the two harnesses
that already exist (`bench_overlap_embed.py`, `bench_paraphrase_hunt.py`)
once per candidate model via the `EMBEDDING_MODEL` environment variable,
then merges their JSON output into one comparison table. Neither existing
script is modified.

**Tech Stack:** Python stdlib (`subprocess`, `json`, `argparse`) in
`bench/`; the real `enrich` Poetry group venv (`.venv-full`) to run the
scripts being orchestrated.

**Spec:** [docs/superpowers/specs/2026-08-15-embedding-model-benchmark-design.md](../specs/2026-08-15-embedding-model-benchmark-design.md)
— this plan implements that spec's "Arm A" and "Sequencing" sections only.
Arm B (retrieval + reranking + SPECTER2) is a separate plan.

## Global Constraints

- No new dependency (matches the spec's "Plan 1: no new dependency").
- `bench/` is excluded from `tests/test_code_standards_scan.py`'s
  statement/module-length ratchets and from
  `[tool.coverage.run].source` — no pytest suite is required for this
  script, and none should be added. Verification instead follows every
  other file in this directory: a `self_check()` function, run
  automatically at the top of `main()`, asserting the script's own
  fixed inputs are what the rest of the script assumes — plus running
  the real command end-to-end as the functional check. This plan's
  "test" steps are shaped around that convention, not a red/green
  pytest cycle, because none exists here to follow.
- Every subprocess call into `.venv-full/bin/python` needs
  `poetry install --with enrich` already run on this host (`chromadb`,
  `sentence-transformers`, torch) and a synced ledger
  (`content/ledger.sqlite`) — both already present on this host.
- `--stages embed` has **no** `--for-draft` narrowing
  (`src/enrich/__main__.py`'s `SCOPE_REFUSED`) — every candidate model
  not already built costs one full ~501-document re-embed. Task 1 below
  measures that cost for real before Task 4 runs the full sweep.
- `content/chroma` already holds a built collection for
  `sentence-transformers/all-mpnet-base-v2` (confirmed via
  `sqlite3 content/chroma/chroma.sqlite3 "SELECT name FROM collections"`
  — one row, `corpus-sentence-transformers-all-mpnet-base-v2`). Only the
  other two candidates need a fresh embed.

---

## Task 1: Restore the book, regenerate its dossiers' `sections.md`, measure one fresh model's embed cost

This task produces no new code. It gets the real 15-chapter book onto
this host (needed by both harnesses' precision arms) and answers the one
open question that gates whether Task 4's three-model sweep is cheap or
expensive, before any code is written against an assumed cost.

**Files:**
- None created or modified. Restores `content/drafts/books/` and
  `content/dossiers/books/` from the committed backup archive (both
  gitignored, per-host content — restoring them is not a git change).

- [ ] **Step 1: Restore the book's drafts and dossiers from the committed backup**

```bash
cd /workspace
unzip -o content/backup/content-20260809.zip \
    "content/drafts/books/digital-twins-for-software-engineers/*" \
    "content/dossiers/books/digital-twins-for-software-engineers/*"
ls content/drafts/books/digital-twins-for-software-engineers/*.md | wc -l
```

Expected: 15 (one file per chapter, e.g.
`09-connecting-the-physical.md`).

- [ ] **Step 2: Regenerate every chapter's `sections.md`**

`bench/RESULTS.md`'s 2026-08-15 embedding section already documents why:
the restored dossiers predate the current `sections.md` heading
convention, and tier-3 matches no section without it.

```bash
cd /workspace
for f in content/drafts/books/digital-twins-for-software-engineers/*.md; do
    .venv-full/bin/python -m src.draft dossier sections "$f" --citekeys --write
done
```

Expected: 15 lines of output, one `sections.md written` (or equivalent
confirmation) per chapter, no errors.

- [ ] **Step 3: Confirm the dossiers are current**

```bash
.venv-full/bin/python -m src.draft dossier status --all
```

Expected: no chapter reports a corpus-digest mismatch severe enough to
block a scan (a stale digest warning is fine — `bench/RESULTS.md`'s own
2026-08-15 entries ran under one; a `sections.md` read error is not).

- [ ] **Step 4: Measure one fresh model's real embed cost**

`all-MiniLM-L6-v2` is not yet built in `content/chroma` (only
`all-mpnet-base-v2` is). Time building it for real, against the real
501-document corpus:

```bash
cd /workspace
du -sh content/chroma
time EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2 \
    .venv-full/bin/python -m src.enrich --stages embed
du -sh content/chroma
```

Record the wall-clock time and the disk delta.

- [ ] **Step 5: Report the cost and confirm before proceeding**

One candidate (`multi-qa-mpnet-base-dot-v1`) still needs the same
treatment in Task 4 — roughly the same cost again, since it is the same
size class as `all-mpnet-base-v2` (768-dim, ~109M parameters) rather than
`all-MiniLM-L6-v2`'s smaller 384-dim/~22M. State both the measured
`all-MiniLM-L6-v2` number and that extrapolation in the task's commit
message or PR notes. **Do not proceed to Task 4 silently if the measured
time is large enough to change how the sweep should be run** (e.g. worth
doing overnight, or worth reducing corpus scope for a first pass) — this
is the "genuinely ambiguous, no clear tie-breaker" case
DEVELOPER-AGENTS.md's Role section reserves for pausing rather than
proceeding autonomously.

- [ ] **Step 6: Commit**

Nothing to commit from this task — it restores gitignored content and
records a measurement. Note the restore and the measured cost in the PR
description once Task 4 opens the PR.

---

## Task 2: `bench/bench_embed_model_compare.py` — the orchestrator, self-check only

Write the script's structure, constants, and `self_check()` first, and
confirm `self_check()` actually catches a broken assumption before
building the parts that depend on it — the same red/green discipline the
rest of this codebase applies via pytest, adapted to how this directory
verifies itself.

**Files:**
- Create: `bench/bench_embed_model_compare.py`

**Interfaces:**
- Produces: `CANDIDATES` (tuple of 3 model name strings), `self_check()`
  (raises `AssertionError` on a bad candidate list), used by Task 3's
  `main()`.

- [ ] **Step 1: Write `self_check()` and `CANDIDATES`, and a call that should fail**

```python
"""Compares the three documented drop-in embedding models
(docs/CONFIG.md "Choosing an embedding model") against tier-3 overlap
detection's existing capability and recall harnesses.

Drives bench_overlap_embed.py and bench_paraphrase_hunt.py unmodified,
once per candidate model, via the EMBEDDING_MODEL environment variable
-- the same override every config.py setting already supports. Neither
script is touched: this is an orchestrator, not a fork.

SPECTER2 does not appear here. It cannot: the four graded-ladder rungs
this arm scores all restate the *same* paper's *same* claim at
different paraphrase distances, and a paper-level title+abstract vector
is identical across all four by construction -- there is nothing for it
to discriminate with. See the design spec's Arm A section.

    .venv-full/bin/python bench/bench_embed_model_compare.py \\
        --tag 2026-08-16-model-compare
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

# The three models docs/CONFIG.md documents as safe, symmetric drop-ins
# for embed_index.py's un-prefixed encode() call. Order matters only for
# the printed table, not for correctness -- code default first, then the
# two others in the order docs/CONFIG.md lists them.
CANDIDATES = (
    "sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers/all-mpnet-base-v2",
    "sentence-transformers/multi-qa-mpnet-base-dot-v1",
)

DRAFTS_DIR = "content/drafts/books/digital-twins-for-software-engineers"

# The already-labelled ground truth bench_paraphrase_hunt.py's
# 2026-08-15 run produced. Copied per model into that model's own tagged
# results directory before --crosscheck runs, since crosscheck() writes
# tiers back into whatever labels.json its --tag resolves to -- reusing
# one shared file across three models would have each overwrite the last.
ORGANIC_LABELS = BENCH_DIR / "results" / "2026-08-15-organic-paraphrase-hunt" / "labels.json"


def model_slug(model):
    return model.rsplit("/", maxsplit=1)[-1]


def self_check():
    """CANDIDATES really are the three docs/CONFIG.md documents, and the
    organic ground truth this arm depends on is really on disk.

    Without this, a typo'd model string would run a real (expensive)
    embed against a model nobody meant to benchmark, and a missing
    ORGANIC_LABELS would fail deep inside a subprocess call with a
    message that does not say why.
    """
    assert len(CANDIDATES) == 3, f"expected 3 candidates, got {len(CANDIDATES)}"
    assert "all-MiniLM-L6-v2" in CANDIDATES[0], "code default should be listed first"
    assert len(set(CANDIDATES)) == 3, "a candidate is listed twice"
    assert ORGANIC_LABELS.exists(), (
        f"no {ORGANIC_LABELS} -- run bench_paraphrase_hunt.py --extract/--crosscheck "
        "first, or restore it from git"
    )


if __name__ == "__main__":
    self_check()
    print("self_check() passed")
```

- [ ] **Step 2: Run it against a deliberately broken candidate list to confirm the check actually catches something**

```bash
cd /workspace/.claude/worktrees/bridge-cse_01Snq32sGD7GtN7Fco3wPwDG
python3 -c "
import sys
sys.path.insert(0, 'bench')
import bench_embed_model_compare as m
m.CANDIDATES = ('sentence-transformers/all-mpnet-base-v2',) * 3
try:
    m.self_check()
    print('BUG: self_check did not catch a duplicated candidate list')
except AssertionError as e:
    print('correctly caught:', e)
"
```

Expected: `correctly caught: a candidate is listed twice`.

- [ ] **Step 3: Run the real self_check() to confirm it passes against the actual constants**

```bash
cd /workspace/.claude/worktrees/bridge-cse_01Snq32sGD7GtN7Fco3wPwDG
.venv-full/bin/python bench/bench_embed_model_compare.py
```

Expected: `self_check() passed` (or a clear failure naming exactly which
assumption broke, if `ORGANIC_LABELS` isn't present yet — restore it
from git with `git checkout bench/results/2026-08-15-organic-paraphrase-hunt/labels.json`
if so; it's a committed file and should already be there on a clean
checkout).

- [ ] **Step 4: Commit**

```bash
git add bench/bench_embed_model_compare.py
git commit -m "Add self_check() and constants for the embedding model comparison"
```

---

## Task 3: The per-model sweep — build, scan, crosscheck

Add the functions that do the real work, driven off the constants and
`self_check()` Task 2 already verified.

**Files:**
- Modify: `bench/bench_embed_model_compare.py`

**Interfaces:**
- Consumes: `CANDIDATES`, `DRAFTS_DIR`, `ORGANIC_LABELS`, `model_slug()`
  from Task 2.
- Produces: `run_model(model, tag, out_dir) -> dict` (one model's
  results), used by Task 4's `main()`.

- [ ] **Step 1: Write `run_model()` and its subprocess helper**

```python
def _run(cmd, env_extra=None):
    """One subprocess call, with EMBEDDING_MODEL (or nothing) layered
    onto this process's own environment -- never a bare os.environ
    replacement, which would drop PATH and silently break every
    .venv-full/bin/python call downstream of it."""
    import os
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"{' '.join(cmd)} exited {result.returncode}")
    return result


def run_model(model, tag, out_dir):
    """Builds `model`'s Chroma collection if it isn't already current,
    scans the fixture and the real book with it, and cross-checks
    against the organic ground truth. Returns the three JSON payloads
    this model produced.

    Each step shells out to the real command a human would run --
    bench_overlap_embed.py and bench_paraphrase_hunt.py are never
    imported, only invoked -- so this script measures exactly what
    `bench/README.md` tells a person to run, not an approximation of it.
    """
    slug = model_slug(model)
    py = ".venv-full/bin/python"
    env = {"EMBEDDING_MODEL": model}

    print(f"\n=== {model} ===", flush=True)
    print("  building/confirming the Chroma collection ...", flush=True)
    _run([py, "-m", "src.enrich", "--stages", "embed"], env_extra=env)

    model_tag = f"{tag}-{slug}"
    print("  running the capability + precision arms ...", flush=True)
    _run([py, "bench/bench_overlap_embed.py", "--fixture",
          "--drafts", DRAFTS_DIR, "--tag", model_tag], env_extra=env)

    model_out = BENCH_DIR / "results" / model_tag
    capability = json.loads((model_out / "embed_capability.json").read_text(encoding="utf-8"))
    precision = json.loads((model_out / "embed_precision.json").read_text(encoding="utf-8"))

    organic_tag = f"{model_tag}-organic"
    organic_out = BENCH_DIR / "results" / organic_tag
    organic_out.mkdir(parents=True, exist_ok=True)
    organic_labels_copy = organic_out / "labels.json"
    organic_labels_copy.write_text(ORGANIC_LABELS.read_text(encoding="utf-8"), encoding="utf-8")

    print("  cross-checking against the 22 organic close-paraphrase pairs ...", flush=True)
    _run([py, "bench/bench_paraphrase_hunt.py", "--crosscheck",
          "--drafts", DRAFTS_DIR, "--tag", organic_tag,
          "--embed-record", str(model_out / "embed_precision.json")])

    organic = json.loads(organic_labels_copy.read_text(encoding="utf-8"))
    caught_by_embedding = sum(
        1 for row in organic["candidates"]
        if row["judgment"] == "paraphrase" and "embedding" in row["tiers"]
    )
    total_paraphrase = sum(1 for row in organic["candidates"] if row["judgment"] == "paraphrase")

    return {
        "model": model,
        "grades_caught": {row["grade"]: row["tiers"] for row in capability["grades"]},
        "embedding_findings": precision["embedding_findings"],
        "organic_recall": f"{caught_by_embedding}/{total_paraphrase}",
    }
```

- [ ] **Step 2: Smoke-test `run_model()` against the already-built model only**

`all-mpnet-base-v2` needs no fresh embed (already built), so this step
exercises the whole function -- subprocess calls, JSON parsing, the
labels.json copy -- at close to zero embed cost, before Task 4 spends
real time on the other two.

```bash
cd /workspace/.claude/worktrees/bridge-cse_01Snq32sGD7GtN7Fco3wPwDG
python3 -c "
import sys
sys.path.insert(0, 'bench')
import bench_embed_model_compare as m
result = m.run_model('sentence-transformers/all-mpnet-base-v2', '2026-08-16-smoketest', None)
print(result)
assert result['organic_recall'].split('/')[1] != '0', 'no paraphrase rows found -- labels.json copy or crosscheck is broken'
print('smoke test passed')
"
```

Expected: a dict with `grades_caught`, `embedding_findings` (a positive
int) and `organic_recall` (e.g. `"8/22"`), then `smoke test passed`. If
`--stages embed` reports building a fresh collection here, something is
wrong — `all-mpnet-base-v2` should already be current; investigate before
continuing rather than assuming the smoke test is merely slow.

- [ ] **Step 3: Commit**

```bash
git add bench/bench_embed_model_compare.py
git commit -m "Add run_model(): build, scan and crosscheck one candidate model"
```

---

## Task 4: `main()`, the comparison table, and the real three-model sweep

**Files:**
- Modify: `bench/bench_embed_model_compare.py`
- Modify: `bench/RESULTS.md` (new dated section)
- Modify: `bench/README.md` ("Which tool to reach for" table and "What
  each file is" table)

**Interfaces:**
- Consumes: `run_model()` from Task 3, `CANDIDATES` from Task 2.
- Produces: `bench/results/<tag>/comparison.json`, the CLI entry point.

- [ ] **Step 1: Write `main()`**

```python
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tag", required=True,
                    help="names bench/results/<tag>/ for this run's comparison table "
                         "(per-model results also land under bench/results/<tag>-<model-slug>/)")
    args = ap.parse_args(argv)

    self_check()
    out_dir = BENCH_DIR / "results" / Path(args.tag).name
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = [run_model(model, args.tag, out_dir) for model in CANDIDATES]

    print(f"\n{'model':40}  {'embedding findings':>19}  organic recall  grades caught")
    for row in rows:
        caught = sum(1 for tiers in row["grades_caught"].values() if tiers)
        print(f"{row['model']:40}  {row['embedding_findings']:>19}  "
              f"{row['organic_recall']:>14}  {caught}/4")

    record = out_dir / "comparison.json"
    record.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"\nRecord: {record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Remove the earlier `if __name__ == "__main__": self_check(); print(...)`
block from Task 2's Step 1 — this replaces it.

- [ ] **Step 2: Run `--help` to confirm the CLI parses**

```bash
cd /workspace/.claude/worktrees/bridge-cse_01Snq32sGD7GtN7Fco3wPwDG
.venv-full/bin/python bench/bench_embed_model_compare.py --help
```

Expected: usage text naming `--tag`, no traceback.

- [ ] **Step 3: Run the real three-model sweep**

This is the expensive step Task 1 measured the cost of. Run it for real:

```bash
cd /workspace/.claude/worktrees/bridge-cse_01Snq32sGD7GtN7Fco3wPwDG
time .venv-full/bin/python bench/bench_embed_model_compare.py \
    --tag 2026-08-16-model-compare 2>&1 | tee /tmp/model-compare.log
```

Expected: three `=== model ===` sections, each completing all three
subprocess stages, ending in the printed comparison table and
`bench/results/2026-08-16-model-compare/comparison.json`.

- [ ] **Step 4: Write up `bench/RESULTS.md`**

Add a new dated section (`## 2026-08-16: which drop-in embedding model
does tier-3 overlap detection see the most with?`, or the actual run
date), in the same shape as the existing 2026-08-15 embedding section:
what was measured, the comparison table from Step 3's actual output
(real numbers, not placeholders — copy them from
`comparison.json`/the printed table), an honest "what this does not
measure" (precision — `embedding_findings` is a volume proxy, not
`tp`/`fp`, since none of the three models' findings are hand-labelled;
that labelling is out of scope here, same as the 2026-08-15 baseline),
and the reproduction command from Step 3.

- [ ] **Step 5: Add this script to `bench/README.md`**

Add one row to the "Which tool to reach for" table (a question like "Which
drop-in embedding model gives tier-3 the best recall on this corpus, at
what finding-volume cost?" → `bench_embed_model_compare.py`) and one row
to the "What each file is" table, in the same one-line style as the
existing 15 rows.

- [ ] **Step 6: Commit**

```bash
git add bench/bench_embed_model_compare.py bench/RESULTS.md bench/README.md \
    bench/results/2026-08-16-model-compare
git commit -m "Add bench_embed_model_compare.py and its first three-model sweep"
```

---

## Task 5: Ship it

Per DEVELOPER-AGENTS.md's "Shipping a code change" cycle.

- [ ] **Step 1: Decide the version bump**

A new `bench/` script with no `src/` change is closest to "a new script"
under MINOR — bump `pyproject.toml`'s `[tool.poetry].version` accordingly
and commit that as part of this branch.

- [ ] **Step 2: Run the OpenCodeReview plugin** (`/open-code-review:delegate-review`
  preferred) over the branch, or record in the PR that it was unavailable.

- [ ] **Step 3: Open the PR**

Note explicitly in the PR description: this is Arm A of #194's benchmark;
Arm B (SPECTER2, retrieval + reranking) is a separate, stacked PR per the
design spec's "Sequencing" section. Include Task 1's measured embed-cost
numbers in the test plan.

- [ ] **Step 4: Wait for CI, request Copilot review, iterate, squash-merge**

Per DEVELOPER-AGENTS.md's standard cycle — this plan does not repeat those
steps' detail.

---

## Self-Review Notes

- **Spec coverage:** Arm A's harness reuse (Task 3), the "no scratch
  directory" correction (Task 1 restores into the real content dir, Task
  3 relies on `collection_name()`'s existing per-model namespacing), the
  stated embed cost (Task 1), and the reporting shape (Task 4) are all
  covered. SPECTER2's exclusion from this arm is stated in the script's
  own docstring (Task 2 Step 1) rather than only in the spec, so a reader
  of the code sees the reason without cross-referencing.
- **Type consistency:** `run_model()` returns a `dict` with
  `model`/`grades_caught`/`embedding_findings`/`organic_recall`, and
  `main()`'s printing/serialization in Task 4 uses exactly those four
  keys — no drift between Task 3's producer and Task 4's consumer.
- **Placeholder scan:** every code step is complete, runnable code, not
  a description of code. Task 4 Step 4 (the `RESULTS.md` write-up) is
  necessarily written from Step 3's actual measured output rather than
  containing invented numbers here — that is a data-reporting step, not
  a code placeholder, and it names exactly what shape and content to
  produce.

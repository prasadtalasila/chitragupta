# bench/'s self-check convention and its four exclusions (#356)

Status: **draft**, written 2026-08-23, implementing issue #356.

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to run this task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Written for** whoever picks up #356: someone who has read
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) and
[CODE-STANDARDS.md](../docs/CODE-STANDARDS.md) but has not necessarily
read `bench/README.md`'s self-check section or
`docs/TECHNICAL-DEBT.md` §3.1 -- both are quoted in full below, so this
plan does not require opening either first.

**Assumed:** `bench/repro_check.py`, `bench/bench_drift.py` and
`bench/sweep_sync.py` as the three worked examples of the convention
(`bench/README.md`'s "`self_check()`: what a script here owes a number it
publishes" section) -- copy their *shape* (a `self_check()` function,
called from `main()` before any real work, that fabricates a difference
its own comparison/aggregation logic is supposed to see and asserts it
does), never their specific assertions.

**Not covered here:** actually wiring `pylint`/`ruff` over `bench/`. This
plan's Task 8 reaffirms that exclusion as a decision, on measured
evidence, rather than schedules the work -- see that task for the
measurement and why it does not belong in this PR.

**Spec:** [issue #356](https://github.com/prasadtalasila/chitragupta/issues/356)
and its own comment naming the ten-issue batch. No separate design doc
exists; the "Decisions this plan makes explicit" section below **is**
the design, derived from reading `docs/TECHNICAL-DEBT.md` §3.1,
`bench/README.md`, `tests/test_technical_debt_scan.py`, and running
`pylint` against `bench/` directly (Task 8).

## Global constraints

- **The citekey invariant does not apply here.** Nothing in this plan
  touches `chitragupta/` or a citekey; every change is in `bench/`, `docs/`,
  `DEVELOPER-AGENTS.md` and `tests/test_technical_debt_scan.py`.
- **Every `self_check()` runs from its script's `main()`, before any real
  work**, per `bench/README.md`'s convention. It costs microseconds and
  needs no corpus, no GPU and (for four of the six scripts below) not
  even the `enrich` Poetry group.
- **No new dependency.** Every assertion below uses only what its script
  already imports (`json`, `tempfile`, `Path` -- all stdlib) or what its
  `main()` already imports lazily (`numpy`, for the two `enrich`-group
  scripts).
- **Version bump: PATCH**, `6.20.12` -> `6.20.13`
  (`pyproject.toml`'s `[tool.poetry].version`). Nothing here changes what
  the shipped pipeline does or how it is invoked -- `bench/` is dev
  tooling, excluded from the release archive already (Task 8's release
  exclusion).
- **Check tags, not just `main`**, before opening the PR and again before
  merging (`git tag --sort=-v:refname | head -1`) -- `v6.20.12` is the
  latest as of this writing, so `6.20.13` is the number to land, but
  re-check if another of the batch's nine sibling PRs (#353, #354, #355,
  #357-#362) has landed first.

## Decisions this plan makes explicit

### 1. The eight scripts without a `self_check()`

Measured 2026-08-23 (`for f in bench/*.py; do grep -q "def self_check" $f
|| echo $f; done`), same command `docs/TECHNICAL-DEBT.md` §3.1 already
uses:

| Script | Verdict | Why |
|---|---|---|
| `bench_collection_scope.py` | **needs one** (Task 6) | `_pool_usage()`'s max-vs-first aggregation across streaming partials is the exact shape of bug that already cost this script a real, silent 5x undercount (its own docstring records it); `_hash_check()`'s `replay_sound` flag is what every other figure in the script's output depends on being true |
| `bench_docling.py` | **exempt** | Every published number (`seconds`, `s_per_page`, `md_chars`) is a direct, honestly-labelled measurement of one real `conv.convert()` call -- no comparison or aggregation of its own that could silently read a real difference as none |
| `bench_overlap.py` | **needs one** (Task 1) | `findings = warm_out.count("tier=exact")` is a plain substring count over another module's printed output -- the same failure class `sweep_sync.py`'s own `self_check()` guards (a regex/string match that stops matching reports the same `0` a clean run does) |
| `bench_topic_depth.py` | **needs one** (Task 3) | `measure()`'s outlier-share/median-size aggregation is exactly the "flat curve reads as a finding, not an absence of one" failure `bench/README.md`'s convention names -- an all-outlier fit and a real clustering must not print the same shape by accident |
| `bench_topic_membership.py` | **needs one** (Task 2) | `score()`'s own docstring records a near-miss: "assuming [`columns`] scored the winning mechanism at 1% agreement" -- a wrong topic-id mapping between HDBSCAN and BERTopic has already produced a plausible-looking wrong number once |
| `estimate.py` | **needs one** (Task 4) | `linfit()` and `measured_efficiency()` are real derived-number logic (a linear fit, a piecewise interpolation) whose output is quoted directly in `RESULTS.md` and used for capacity planning -- exactly "a number a reader would act on" |
| `make_corpus.py` | **exempt** | `rank_sample()`'s `dict.fromkeys` dedup could in principle under-fill a sample, but that failure is not silent: `main()`'s own `print(f"sample16 : {len(sample16)} PDFs, ...")` reports the real count directly, so a bad dedup shows up as a wrong number in the first line anyone reads, not as a zero hidden behind a comparison |
| `run_parallel.py` | **needs one** (Task 5) | `lpt_shards()`'s load-balancing is exactly what the round-robin GPU assignment and the published `pages_per_s` throughput figure depend on; an unbalanced shard reads as bad GPU throughput, not as a bad split -- the same shape of bug the module's own comment about `CUDA_VISIBLE_DEVICES` already flags as a real, previously-hit failure |

Six need one, two are exempt. `bench/README.md`'s self-check section
(Task 7) states both halves of this table -- the six by name where their
`self_check()` lives, the two exempt ones by name and reason -- rather
than leaving "which is which" for the next reader to re-derive.

### 2. The four exclusions

| Exclusion | Decision | Reason |
|---|---|---|
| **C1/C2** (`tests/test_code_standards_scan.py`'s `STATEMENT_ROOTS`/`CODE_LINE_ROOTS`) | **Reaffirmed, unchanged** | Already stated and defended in `docs/CODE-STANDARDS.md` ("bench/ is out of scope for both... one-shot analysis code whose main() reads top to bottom on purpose"). Nothing in this issue's own investigation gives a reason to revisit it |
| **Coverage** (`pyproject.toml`'s `[tool.coverage.run].source = ["chitragupta", "scripts", ".claude/hooks"]`) | **Reaffirmed, unchanged** | `bench/` is never imported by the shipped pipeline; `self_check()` is its substitute regression guard, run on every invocation rather than once in CI |
| **Release archive** (`scripts/release.py`'s `EXCLUDE_TOP_LEVEL`) | **Reaffirmed, unchanged** | `bench/` is dev tooling that measures this checkout, not something a `pip install`ed or unzipped-release consumer runs |
| **Linter** (`ci.yml`'s `pylint --rcfile=.pylintrc chitragupta scripts .claude/hooks` / `ruff check chitragupta scripts .claude/hooks`) | **Reaffirmed, on measured evidence** (Task 8) | The issue's own framing -- "pylint over bench/ costs nothing" -- does not hold: measured directly, it is **78 findings** across 22 files. Not free, and not this PR's job to pay down; see Task 8 |

### 3. What closes in `docs/TECHNICAL-DEBT.md`

§3.1 and "What to take first" item 1 are **deleted**, per the register's
own rule ("coming off means the section is deleted, not marked done and
kept") and the issue's "Done when". Tier 3 keeps its heading and gains
the same one-line "holds no subsections" statement Tier 1 and Tier 2
already carry, once their own named entries closed. See Task 8 for the
exact edit, and Task 11 for the test-file consequence this has --
**not obvious from the issue text**, found by reading
`tests/test_technical_debt_scan.py` directly: it pins the "**N** scripts
still hold no assertion at all" sentence against the real tree
(`test_the_bench_self_check_count_matches_the_tree`), and deleting the
sentence without also deleting that test leaves a hard-failing pin
pointed at prose that no longer exists.

---

## Task 1: `bench_overlap.py` -- factor out the finding count, add `self_check()`

**Files:**

- Modify: `bench/bench_overlap.py`

**Interfaces:**

- Produces: `_count_exact_findings(scan_output: str) -> int`, `self_check() -> None`

- [ ] **Step 1: Factor the inline count into a named function**

Replace the `findings = warm_out.count("tier=exact")` line inside `run()`
(currently line 72) with a call to a new module-level function, added
just above `run()`:

```python
def _count_exact_findings(scan_output: str) -> int:
    """Findings `cmd_scan` printed at `tier=exact` -- a plain substring
    count over another module's printed output, so a wording change in
    that tier's output would silently read as "0 findings" rather than
    raise. Factored out so self_check can prove the count still fires
    before a real 0 is believed.
    """
    return scan_output.count("tier=exact")
```

`run()`'s line becomes `findings = _count_exact_findings(warm_out)`.

- [ ] **Step 2: Add `self_check()`**

Add just below the new function:

```python
def self_check() -> None:
    """Prove `_count_exact_findings` still counts before trusting a real
    scan's 0 to mean "no findings" rather than "the tier's output format
    moved and the substring stopped matching".

    `bench/` sits outside CI's coverage targets (--cov=chitragupta
    --cov=scripts), so nothing in the test suite will ever catch a
    regression here. This runs on every invocation instead.
    """
    sample = "tier=exact span=12 words\ntier=skip-gram span=9 words\ntier=exact span=5 words\n"
    assert _count_exact_findings(sample) == 2, "did not count both tier=exact findings"
    assert _count_exact_findings("tier=skip-gram span=9 words\n") == 0, (
        "a sample with no tier=exact line must count zero, not raise or miscount")
```

- [ ] **Step 3: Call it from `main()`**

In `main()`, immediately after `args = parser.parse_args(argv)` and
before the `draft = Path(args.draft)` line, insert:

```python
    self_check()
```

- [ ] **Step 4: Run it for real**

```bash
python3 -c "import sys; sys.path.insert(0, 'bench'); import bench_overlap; bench_overlap.self_check(); print('ok')"
```

Expected: `ok`, no assertion error.

- [ ] **Step 5: Commit**

```bash
git add bench/bench_overlap.py
git commit -m "Add self_check() to bench_overlap.py"
```

## Task 2: `bench_topic_membership.py` -- add `self_check()` for `score()`'s mapping

**Files:**

- Modify: `bench/bench_topic_membership.py`

**Interfaces:**

- Consumes: `score(name, weights, labels, columns, ratio=0.5) -> dict`
  (already defined, unchanged)
- Produces: `self_check() -> None`

- [ ] **Step 1: Add `self_check()`**

Add directly above `def main(argv=None):`:

```python
def self_check() -> None:
    """Prove `score()` reads doc-to-topic agreement through `columns`,
    not by assuming `columns == sorted(set(labels))`.

    The documented failure (this module's own docstring): passing the
    wrong mapping once scored the winning mechanism at 1% agreement
    instead of its true value, because HDBSCAN's cluster ids and
    BERTopic's topic ids are renumbered relative to each other. `columns`
    below is deliberately [5, 2], not sorted to [2, 5], so a regression
    that assumes sorted order would mis-map every row and this would
    silently score a real mechanism as disagreeing with the clustering
    it describes.

    `bench/` sits outside CI's coverage targets, so nothing in the test
    suite will ever catch a regression here. This runs on every
    invocation instead.
    """
    weights = [[0.9, 0.1], [0.2, 0.8], [0.5, 0.5]]
    labels = [5, 2, 5]
    columns = [5, 2]
    result = score("fixture", weights, labels, columns)
    assert result["agreement"] == 1.0, (
        f"a correct column mapping over a clean 3-document fixture must "
        f"score full agreement, got {result['agreement']}")
    assert result["is_top"] == 1.0, (
        f"the top-ranked topic must match the assigned one here, got {result['is_top']}")
    # The mapping this guards against: sorted(set(labels)) == [2, 5],
    # not [5, 2] -- using it instead degrades agreement to 1/3 on this
    # same fixture, verified directly rather than asserted from memory.
    wrong = score("wrong-mapping", weights, labels, sorted(set(labels)))
    assert wrong["agreement"] < result["agreement"], (
        "the wrong column mapping did not degrade agreement on this fixture -- "
        "the fixture no longer exercises the bug this check exists for")
```

`score()` does `import numpy as np` internally already, so this needs no
new import at module scope -- `self_check()` needs `numpy` importable
(part of the `enrich` group) but nothing else `main()` needs (no corpus,
no GPU, no UMAP/HDBSCAN fit).

- [ ] **Step 2: Call it from `main()`**

In `main()`, immediately after `args = parser.parse_args(argv)`, insert:

```python
    self_check()
```

- [ ] **Step 3: Run it for real** (needs the `enrich` Poetry group for `numpy`)

```bash
.venv-full/bin/python -c "import sys; sys.path.insert(0, 'bench'); import bench_topic_membership; bench_topic_membership.self_check(); print('ok')"
```

Expected: `ok`. If `numpy` is not installed, this fails on import inside
`score()` -- the same dependency `main()` already requires, just hit
earlier and with a clearer message than a UMAP import failure would give.

- [ ] **Step 4: Commit**

```bash
git add bench/bench_topic_membership.py
git commit -m "Add self_check() to bench_topic_membership.py"
```

## Task 3: `bench_topic_depth.py` -- factor out label summarising, add `self_check()`

**Files:**

- Modify: `bench/bench_topic_depth.py`

**Interfaces:**

- Produces: `_summarize_labels(labels: list[int]) -> dict`, `self_check() -> None`
- `measure()` (existing) now calls `_summarize_labels` instead of
  inlining the same computation.

- [ ] **Step 1: Factor the pure aggregation out of `measure()`**

`measure()` currently (lines 105-126) computes `ids`, the early-return
for `not ids`, `sizes`, `outlier_share` and `median_size` inline before
moving on to the soft-membership computation that needs `numpy`/HDBSCAN.
Extract the label-only part, which needs neither, into a new function
placed just above `measure()`:

```python
def _summarize_labels(labels: "list[int]") -> dict:
    """Topic count, outlier share and median cluster size from HDBSCAN's
    raw labels alone -- factored out of measure() so self_check can
    fabricate labels without a real UMAP/HDBSCAN fit.

    An all-outlier fit (no id besides -1) must report zero topics
    explicitly, not raise or silently drop the row: a degenerate fit and
    a real one must never print the same shape by accident.
    """
    ids = sorted(set(labels) - {-1})
    if not ids:
        return {"topics": 0, "outlier_share": 1.0, "median_size": 0}
    sizes = sorted(labels.count(topic_id) for topic_id in ids)
    return {
        "topics": len(ids),
        "outlier_share": labels.count(-1) / len(labels),
        "median_size": sizes[len(sizes) // 2],
    }
```

Then rewrite `measure()`'s opening to use it:

```python
def measure(reduced, min_cluster_size, min_samples, repeats=1):
    import numpy as np
    from hdbscan import all_points_membership_vectors

    labels, clusterer = fit_labels(reduced, min_cluster_size, min_samples)
    summary = _summarize_labels(labels)
    if summary["topics"] == 0:
        return {**summary, "topics_per_doc": 0.0, "stability": None}

    soft = np.atleast_2d(np.asarray(all_points_membership_vectors(clusterer)))
    keep = (soft >= 0.5 * soft.max(axis=1, keepdims=True)) & (soft > 0)
    counts = keep.sum(axis=1)
    live = counts[counts > 0]
    return {
        **summary,
        "topics_per_doc": float(live.mean()) if len(live) else 0.0,
        "stability": stability(reduced, min_cluster_size, min_samples, repeats),
    }
```

This is a pure refactor -- `measure()`'s return value is unchanged for
every input; only where the topic/outlier/median-size numbers come from
moves.

- [ ] **Step 2: Add `self_check()`**

Add directly above `def main(argv=None):`:

```python
def self_check() -> None:
    """Prove `_summarize_labels` reports an all-outlier fit as zero
    topics explicitly, and counts a real multi-cluster fit correctly --
    the two shapes `measure()`'s docstring warns a flat curve can hide.

    `bench/` sits outside CI's coverage targets, so nothing in the test
    suite will ever catch a regression here. This runs on every
    invocation instead, and needs no UMAP/HDBSCAN fit -- pure list
    arithmetic over fabricated labels.
    """
    all_outliers = _summarize_labels([-1, -1, -1])
    assert all_outliers == {"topics": 0, "outlier_share": 1.0, "median_size": 0}, (
        f"an all-outlier fit must report zero topics explicitly, got {all_outliers}")

    mixed = _summarize_labels([0, 0, 1, 1, 1, -1])
    assert mixed["topics"] == 2, f"did not count both real clusters: {mixed}"
    assert mixed["outlier_share"] == 1 / 6, f"outlier share miscomputed: {mixed}"
    assert mixed["median_size"] == 3, (
        f"median of cluster sizes [2, 3] should be 3 (the upper of the pair), got {mixed}")
```

- [ ] **Step 3: Call it from `main()`**

In `main(argv=None)`, immediately after
`args = parser.parse_args(argv)`, insert:

```python
    self_check()
```

- [ ] **Step 4: Run it for real** (stdlib only -- no `enrich` group needed)

```bash
python3 -c "import sys; sys.path.insert(0, 'bench'); import bench_topic_depth; bench_topic_depth.self_check(); print('ok')"
```

Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
git add bench/bench_topic_depth.py
git commit -m "Add self_check() to bench_topic_depth.py"
```

## Task 4: `estimate.py` -- add `self_check()` for `linfit()`/`measured_efficiency()`

**Files:**

- Modify: `bench/estimate.py`

**Interfaces:**

- Produces: `self_check() -> None`

- [ ] **Step 1: Add `self_check()`**

Add directly above `def main() -> None:`:

```python
def self_check() -> None:
    """Prove `linfit` recovers a known line and `measured_efficiency`
    interpolates between measured points rather than silently returning
    a neighbour's value -- both are quoted directly in RESULTS.md and
    used for capacity planning, so a wrong slope or a wrong efficiency
    reads as real advice.

    `bench/` sits outside CI's coverage targets, so nothing in the test
    suite will ever catch a regression here. This runs on every
    invocation instead.
    """
    a, b = linfit([0.0, 1.0, 2.0, 3.0], [1.0, 3.0, 5.0, 7.0])
    assert abs(a - 1.0) < 1e-9 and abs(b - 2.0) < 1e-9, (
        f"linfit did not recover y = 2x + 1 from its own points: a={a}, b={b}")

    eff_mid, interpolated_mid = measured_efficiency(6)
    assert interpolated_mid, "6 workers sits between two measured points and must interpolate"
    assert abs(eff_mid - 1.005) < 1e-9, (
        f"expected the midpoint of the measured 4- and 8-worker efficiencies, got {eff_mid}")

    eff_exact, interpolated_exact = measured_efficiency(8)
    assert not interpolated_exact and eff_exact == 0.97, (
        "a directly-measured worker count must return its own value, not interpolate")

    eff_over, interpolated_over = measured_efficiency(1000)
    assert interpolated_over and eff_over == _MEASURED_EFFICIENCY[48], (
        "a worker count past the measured range must clamp to the highest point, "
        "not extrapolate past it")
```

- [ ] **Step 2: Call it from `main()`**

In `main()`, immediately after `args = ap.parse_args()` and before the
two `if args.workers < 1` / `if args.efficiency is not None` guards,
insert:

```python
    self_check()
```

- [ ] **Step 3: Run it for real**

```bash
python3 -c "import sys; sys.path.insert(0, 'bench'); import estimate; estimate.self_check(); print('ok')"
```

Expected: `ok`. (Verified against the real functions while writing this
plan: `linfit` returns exactly `(1.0, 2.0)`; `measured_efficiency(6)`
returns exactly `(1.005, True)`; `measured_efficiency(1000)` returns
exactly `(0.31, True)`.)

- [ ] **Step 4: Commit**

```bash
git add bench/estimate.py
git commit -m "Add self_check() to estimate.py"
```

## Task 5: `run_parallel.py` -- add `self_check()` for `lpt_shards()`

**Files:**

- Modify: `bench/run_parallel.py`

**Interfaces:**

- Produces: `self_check() -> None`

- [ ] **Step 1: Add `self_check()`**

Add directly above `def main() -> None:`:

```python
def self_check() -> None:
    """Prove `lpt_shards` balances load across workers rather than
    silently packing them in file order.

    The module's own docstring claims "page counts land evenly", and the
    round-robin GPU assignment plus the published pages_per_s throughput
    figure both depend on that being true -- an unbalanced shard reads
    as bad GPU throughput, not as a bad split.

    `bench/` sits outside CI's coverage targets, so nothing in the test
    suite will ever catch a regression here. This runs on every
    invocation instead.
    """
    items = [{"pages": p} for p in [100, 1, 1, 1, 1, 1, 1, 1]]
    shards = lpt_shards(items, 4)
    loads = [sum(item["pages"] for item in shard) for shard in shards]
    assert loads == [100, 3, 2, 2], (
        f"LPT shard loads drifted from the known trace for this fixture: {loads}")
    assert sum(len(shard) for shard in shards) == len(items), (
        "a shard split must not drop or duplicate items")
```

- [ ] **Step 2: Call it from `main()`**

In `main()`, immediately after `args = ap.parse_args()`, insert:

```python
    self_check()
```

- [ ] **Step 3: Run it for real**

```bash
python3 -c "import sys; sys.path.insert(0, 'bench'); import run_parallel; run_parallel.self_check(); print('ok')"
```

Expected: `ok`. (Verified against the real function while writing this
plan: the trace above produces exactly `[100, 3, 2, 2]`.)

- [ ] **Step 4: Commit**

```bash
git add bench/run_parallel.py
git commit -m "Add self_check() to run_parallel.py"
```

## Task 6: `bench_collection_scope.py` -- add `self_check()` for `_pool_usage()`/`_hash_check()`

**Files:**

- Modify: `bench/bench_collection_scope.py`

**Interfaces:**

- Consumes: `_pool_usage(session_file, start, end) -> dict`,
  `_hash_check(hashes_path) -> dict` (both already defined, unchanged)
- Produces: `self_check() -> None`

- [ ] **Step 1: Add `self_check()`**

Add directly above `def run(args):`:

```python
def self_check() -> None:
    """Prove the two aggregations this script's headline figures depend
    on most.

    `_pool_usage`: a streaming request's usage must be read from its
    *final* (maximum) entry, not its first. This module's own docstring
    records the real bug: first-per-requestId once summed to 8,259
    output tokens against a true 41,573, a silent 5x undercount that
    nothing caught because a wrong total looks exactly like a right one.

    `_hash_check`: `replay_sound` must go False the moment any checkpoint
    hash moves, because every surfaced/selected/rejected figure in this
    script's output is a *replay* and is void if the ledger or index
    moved underneath it.

    `bench/` sits outside CI's coverage targets, so nothing in the test
    suite will ever catch a regression here. This runs on every
    invocation instead: it costs microseconds against a throwaway
    tempfile, no real transcript or corpus involved.
    """
    import tempfile

    lines = [
        json.dumps({"timestamp": "2026-01-01T00:00:00Z", "requestId": "r1",
                    "message": {"model": "m", "usage": {"output_tokens": 10}}}),
        json.dumps({"timestamp": "2026-01-01T00:00:01Z", "requestId": "r1",
                    "message": {"model": "m", "usage": {"output_tokens": 50}}}),
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                     encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
        path = Path(fh.name)
    try:
        usage = _pool_usage(path, "", "~")
    finally:
        path.unlink()
    assert usage["output_tokens"] == 50, (
        f"a streaming request's usage must be read from its final (max) entry, "
        f"not its first -- got {usage['output_tokens']}, the documented undercount bug")
    assert usage["streaming_partials_present"] is True, (
        "two usage entries for one requestId must be flagged as streaming "
        "partials, not silently agreeing")

    same = {"point": "p", "retrieval_index": {"md5": "a", "bytes": 1},
            "ledger": {"md5": "x"}, "utc": "t"}
    moved = {**same, "retrieval_index": {"md5": "b", "bytes": 1}}
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(json.dumps(same) + "\n" + json.dumps(moved) + "\n")
        hash_path = Path(fh.name)
    try:
        checked = _hash_check(hash_path)
    finally:
        hash_path.unlink()
    assert checked["replay_sound"] is False, (
        "a run whose retrieval_index hash changed between checkpoints must not "
        "be reported as a sound replay")
```

- [ ] **Step 2: Call it from `main()`**

In `main(argv=None)`, immediately after
`args = _build_parser().parse_args(argv)`, insert:

```python
    self_check()
```

- [ ] **Step 3: Run it for real**

```bash
python3 -c "import sys; sys.path.insert(0, 'bench'); import bench_collection_scope; bench_collection_scope.self_check(); print('ok')"
```

Expected: `ok`. (Verified against the real functions while writing this
plan: `_pool_usage` returns `output_tokens: 50`,
`streaming_partials_present: True`; `_hash_check` returns
`replay_sound: False` for the moved-hash fixture.)

- [ ] **Step 4: Commit**

```bash
git add bench/bench_collection_scope.py
git commit -m "Add self_check() to bench_collection_scope.py"
```

## Task 7: `bench/README.md` -- exempt set, stale quote fix, exclusions home

**Files:**

- Modify: `bench/README.md`

- [ ] **Step 1: Fix the stale coverage-source quote**

The self-check section currently reads (in the paragraph starting "The
reason is the first line of every such function"):

```text
C1/C2, coverage (`source = ["src", "scripts"]`), the release archive
```

`pyproject.toml`'s real value is
`source = ["chitragupta", "scripts", ".claude/hooks"]` (confirmed by
reading `pyproject.toml` directly while writing this plan). Replace with:

```text
C1/C2, coverage (`source = ["chitragupta", "scripts", ".claude/hooks"]`
in `pyproject.toml`), the release archive
```

- [ ] **Step 2: Replace the dangling §3.1 link with the full four-exclusions record**

The same paragraph currently ends:

```text
and the linter (`docs/TECHNICAL-DEBT.md` §3.1). Nothing in the test suite
will ever catch a regression in these files, so the check runs on every
invocation instead. It costs microseconds.
```

`docs/TECHNICAL-DEBT.md` §3.1 is deleted in Task 8, so this becomes the
authoritative record instead of a pointer to one. Replace with:

```text
and the linter. Nothing in the test suite will ever catch a regression
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
```

- [ ] **Step 3: Name the exempt set in the self-check section itself**

The self-check section's second paragraph currently ends:

```text
`repro_check.py`, `bench_drift.py` and `sweep_sync.py` have one; a new
script that publishes a number is expected to follow, and one that only
prints what it read back is not.
```

Replace with:

```text
`repro_check.py`, `bench_drift.py`, `sweep_sync.py`,
`bench_embed_model_compare.py`, `bench_overlap_df.py`,
`bench_overlap_embed.py`, `bench_overlap_gate.py`,
`bench_overlap_skipgram.py`, `bench_paraphrase_hunt.py`,
`bench_retrieval_compare.py`, `bench_retrieval_ground_truth.py`,
`bench_retrieval_keyword_selfretrieval.py`, `bench_retrieval_live_logs.py`,
`embed_models.py`, `bench_collection_scope.py`, `bench_overlap.py`,
`bench_topic_depth.py`, `bench_topic_membership.py`, `estimate.py` and
`run_parallel.py` each have one -- 20 of the 22 scripts here. The
exceptions are `bench_docling.py` and `make_corpus.py`: both publish
only real, directly-observed measurements (a per-PDF timing; a corpus or
sample size) with no comparison or aggregation logic of their own that
could silently read a real difference as none. `make_corpus.py`'s
`rank_sample()` does dedup its evenly-spaced indices, but a bad dedup
shows up as a wrong number in `main()`'s own
`sample16 : N PDFs` line, not as a zero hidden behind a comparison --
the failure this convention exists to catch.
```

- [ ] **Step 4: Update the re-measurement note further down**

If `bench/README.md` still carries the "Re-measured" language from
§3.1 being quoted elsewhere in this file (check for any other "14 of the
22" or "8 scripts" phrasing while editing), update it to "20 of the 22"
/ "the two exempt scripts" consistently with Step 3.

- [ ] **Step 5: Commit**

```bash
git add bench/README.md
git commit -m "Document the bench/ self-check exempt set and the four exclusion decisions"
```

## Task 8: `docs/TECHNICAL-DEBT.md` -- delete §3.1, close take-first item 1

**Files:**

- Modify: `docs/TECHNICAL-DEBT.md`

- [ ] **Step 1: Delete §3.1 entirely**

Delete lines 151-207 (`### ⚠ 3.1 \`bench/\` is outside every check in the
repository` through the paragraph ending "...not a plan to bring
`bench/` under the ratchet.").

- [ ] **Step 2: Give Tier 3 the same "holds no subsections" statement Tier 1
  and Tier 2 already carry**

Tier 1 (`## 🧱 Tier 1: the debt the ratchet already holds`) and Tier 2
both state, once their own named entries closed: "This tier holds no
subsections at all". Tier 3's heading and its one-line intro currently
read:

```text
## 🧱 Tier 3: found by review, tracked nowhere

New in this review. Each names a call site.

### ⚠ 3.1 `bench/` is outside every check in the repository
...
```

Replace the intro line with (keeping the `## 🧱 Tier 3: found by review,
tracked nowhere` heading itself, so nothing that links to the Tier 3
heading breaks):

```text
## 🧱 Tier 3: found by review, tracked nowhere

**This tier holds no subsections at all.** Its one entry, `bench/`'s
exclusion from C1/C2, coverage, the release archive and the linter, was
reaffirmed as a decision rather than arrears in #356 -- see
`bench/README.md`'s self-check section for the reasoning behind each of
the four, and the current self-check count.
```

- [ ] **Step 3: Delete "What to take first" item 1**

Delete:

```text
1. **[3.1] The rest of `bench/`.** 8 of its 22 scripts still carry no
   self-check, and the directory remains outside C1/C2, coverage, the
   release archive and the linters. Open and accepted rather than
   scheduled: the convention is a floor for a script that publishes a
   number, not a plan to bring `bench/` under the ratchet. Tracked in
   #356.
```

Since this was the section's only remaining item, update the
introductory sentence just above it (currently: "Everything the
2026-08-18 reconciliation found open is resolved as of #295's batch
(PRs #290, #292, #293, #237 and #291), and §3.1's 'pattern of one' closed
in PR #294...") to close the loop, e.g. append: "...and #356 closed the
list's last item by reaffirming `bench/`'s exclusions as a decision
rather than scheduling further work." Leave no numbered list under
"What to take first" -- an empty list under the heading is the same
shape `_take_first_claims` (Task 11) already tolerates for Tier 1.

- [ ] **Step 4: Fix the self-referencing §3.1 link inside the 5.4 ruff section**

Around line 491, the ruff-baseline section currently reads:

```text
`bench/` itself is not in `ci.yml`'s `ruff` invocation -- [Tier
3.1](#-31-bench-is-outside-every-check-in-the-repository) excludes it
from every check in the repository, unchanged by this adoption, so the
tag is inert in practice (nothing runs `ruff` over `bench/`) but correct
on the evidence, which is the more honest state than stripping a
suppression a real check would still need.
```

Replace the link with a reference to `bench/README.md` instead of the
now-deleted anchor:

```text
`bench/` itself is not in `ci.yml`'s `ruff` invocation -- `bench/README.md`
records that exclusion as a decision (#356), unchanged by this adoption,
so the tag is inert in practice (nothing runs `ruff` over `bench/`) but
correct on the evidence, which is the more honest state than stripping a
suppression a real check would still need.
```

- [ ] **Step 5: Commit**

```bash
git add docs/TECHNICAL-DEBT.md
git commit -m "Close TECHNICAL-DEBT.md §3.1: reaffirm bench/'s exclusions as a decision"
```

## Task 9: `docs/CODE-STANDARDS.md` -- fix the dangling §3.1 link

**Files:**

- Modify: `docs/CODE-STANDARDS.md`

- [ ] **Step 1: Reword the "for the current count" sentence**

Around line 244-248, currently:

```text
Stating that plainly is better than the alternative reading, which is
that its long functions (a growing number, as `bench/` grows -- see
[TECHNICAL-DEBT.md §3.1](TECHNICAL-DEBT.md#-31-bench-is-outside-every-check-in-the-repository)
for the current count) were quietly not counted.
```

`docs/TECHNICAL-DEBT.md` no longer tracks a "current count" for this --
Task 8 turned it from a re-measured register item into a stated
decision. Replace with:

```text
Stating that plainly is better than the alternative reading, which is
that its long functions were quietly not counted -- see
[bench/README.md](../bench/README.md) for the current self-check count
and the reasoning behind each of the four things `bench/` sits outside.
```

- [ ] **Step 2: Commit**

```bash
git add docs/CODE-STANDARDS.md
git commit -m "Fix CODE-STANDARDS.md's dangling link to the deleted TECHNICAL-DEBT.md §3.1"
```

## Task 10: `DEVELOPER-AGENTS.md` -- fix the dangling §3.1 link

**Files:**

- Modify: `DEVELOPER-AGENTS.md`

- [ ] **Step 1: Reword the bench-markers bullet**

Around lines 462-469 (the ruff-adoption bullet list, "One of the 12
existing `# noqa: BLE001` markers..."), currently ends:

```text
bench/`'s two markers were checked the same way and are genuine --
[Tier 3.1](docs/TECHNICAL-DEBT.md#-31-bench-is-outside-every-check-in-the-repository)
leaves `bench/` outside every check including this one, unchanged, so
they stay inert in practice but correct on the evidence.
```

Replace the link with:

```text
`bench/`'s two markers were checked the same way and are genuine --
`bench/README.md` records `bench/`'s exclusion from every check
including this one as a decision (#356), unchanged, so they stay inert
in practice but correct on the evidence.
```

- [ ] **Step 2: Commit**

```bash
git add DEVELOPER-AGENTS.md
git commit -m "Fix DEVELOPER-AGENTS.md's dangling link to the deleted TECHNICAL-DEBT.md §3.1"
```

## Task 11: `tests/test_technical_debt_scan.py` -- remove the self-check pin

**Files:**

- Modify: `tests/test_technical_debt_scan.py`

This file already documents its own precedent for this exact situation:
the comment above `TestTheOtherDriftProneClaimsArePinned` (lines
365-381) explains that when #354 and #355 closed their own
`docs/TECHNICAL-DEBT.md` sections outright (rather than merely
re-measuring them), their pin functions were removed from this file
too -- "a second, weaker prose pin ... would be exactly the two-debt-lists
problem the register warns against." #356 is the third instance of the
same shape.

- [ ] **Step 1: Delete the bench-self-check regex, helper and both its tests**

Delete:

- `_BENCH_SELF_CHECK_RE` (the module-level regex, currently ~line 404)
- `_bench_scripts_without_self_check()` (currently ~lines 429-436)
- `test_the_bench_self_check_count_matches_the_tree` from
  `TestTheOtherDriftProneClaimsArePinned` (currently ~lines 487-493)
- `test_a_reworded_bench_self_check_sentence_fails_loudly` from
  `TestTheNewPinsFailLoudlyWhenReworded` (currently ~lines 502-504)

- [ ] **Step 2: Update the precedent comment to name #356 as the third instance**

The comment block starting `# --- #353: the other drift-prone claims the issue
asked to pin ---` (currently ~lines 365-381) says: "Two of the claims the issue
named are not pinned here... The noqa-marker count is #354's... The annotation
ratio is #355's..." Add a third sentence in the same shape: "The bench
self-check count is #356's: the exclusion moved from a re-measured register
item to a stated decision, and `bench/README.md`, not this test, is now where
that count is checked by a human reading it directly."

- [ ] **Step 3: Update `TestTheOtherDriftProneClaimsArePinned`'s docstring**

Currently: `"""Two of the four claims #353's own "What to build" list
named, each checked against the real document -- the other two (the
annotation ratio and the noqa marker count) are #355's and #354's now,
not this file's; see the comment above."""`

Replace with: `"""Two of the four claims #353's own "What to build" list
named, each checked against the real document -- the other two (the
annotation ratio and the noqa marker count) are #355's and #354's now,
and the bench self-check count that used to be a third is #356's; see
the comment above."""`

- [ ] **Step 4: Run the affected test module**

```bash
.venv-full/bin/python -m pytest tests/test_technical_debt_scan.py -v
```

Expected: all remaining tests pass. `test_no_entry_named_as_open_has_left_its_register`
and `test_the_stated_register_sizes_match_the_registers` must still pass
unaffected (they read Tier 1, which Task 8 does not touch).
`test_the_two_sections_the_parsers_read_are_still_there` must still pass
-- both `## Tier 1` and `## What to take first` headings still exist
after Task 8, just with empty bodies where §3.1's content and item 1
used to be.

- [ ] **Step 5: Commit**

```bash
git add tests/test_technical_debt_scan.py
git commit -m "Remove the bench self-check count pin, closed outright by #356"
```

## Task 12: Bump the version

**Files:**

- Modify: `pyproject.toml`

- [ ] **Step 1: Re-check the latest tag** (per the memory: PR stacking can
  silently pick the same version as a sibling in this batch)

```bash
git fetch origin --tags -q
git tag --sort=-v:refname | head -1
```

If it is still `v6.20.12`, proceed with `6.20.13`. If not, use the next
PATCH after whatever it now is.

- [ ] **Step 2: Edit `pyproject.toml`**

```toml
version = "6.20.13"
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "Bump version to 6.20.13"
```

## Task 13: Full local check suite

**Files:** none (verification only)

- [ ] **Step 1: Run every new `self_check()` directly**

```bash
python3 -c "import sys; sys.path.insert(0, 'bench'); import bench_overlap; bench_overlap.self_check(); print('bench_overlap ok')"
python3 -c "import sys; sys.path.insert(0, 'bench'); import bench_topic_depth; bench_topic_depth.self_check(); print('bench_topic_depth ok')"
python3 -c "import sys; sys.path.insert(0, 'bench'); import estimate; estimate.self_check(); print('estimate ok')"
python3 -c "import sys; sys.path.insert(0, 'bench'); import run_parallel; run_parallel.self_check(); print('run_parallel ok')"
python3 -c "import sys; sys.path.insert(0, 'bench'); import bench_collection_scope; bench_collection_scope.self_check(); print('bench_collection_scope ok')"
.venv-full/bin/python -c "import sys; sys.path.insert(0, 'bench'); import bench_topic_membership; bench_topic_membership.self_check(); print('bench_topic_membership ok')"
```

This **is** the end-to-end smoke test DEVELOPER-AGENTS.md's "Before
claiming a task complete" asks for, for these six files specifically --
`bench/` has no pytest module of its own by design, and `self_check()`
run for real (not mocked) is what stands in for one, the same shape
`repro_check.py` already established.

- [ ] **Step 2: Full test suite with coverage**

```bash
.venv-full/bin/python -m pytest --cov --cov-report=term-missing
```

Expected: 100% (or `--cov-fail-under=0` if this host lacks
pandoc/TeX Live/poppler -- check which applies before reading the
number). A worktree checkout can lack `config.toml`, which fails 15
tests on a clean `git status` for a reason unrelated to any change; if
that count appears, confirm with `git stash` and a rerun before
attributing it to this branch.

- [ ] **Step 3: All three linters**

```bash
pylint --rcfile=.pylintrc chitragupta scripts .claude/hooks
ruff check chitragupta scripts .claude/hooks
markdownlint-cli2 "*.md" "docs/**/*.md" ".claude/**/*.md" "plans/**/*.md"
```

None of these paths include `bench/` (Task 8's reaffirmed decision), so
this PR's `bench/*.py` changes are not linted by either Python linter --
expected, not an oversight. `markdownlint` **does** cover this plan file
itself (`plans/**/*.md`) and the three edited docs.

- [ ] **Step 4: `poetry check`**

```bash
poetry check
```

- [ ] **Step 5: OpenCodeReview**

Run `/open-code-review:delegate-review` over the branch per
DEVELOPER-AGENTS.md's shipping cycle step 3. Note in the PR's test plan
which mode ran, or that the plugin was unavailable.

- [ ] **Step 6: Read `tests/test_technical_debt_scan.py`'s full module once
  more, green**

```bash
.venv-full/bin/python -m pytest tests/test_technical_debt_scan.py tests/test_code_standards_scan.py -v
```

Both must stay green -- Task 11 already targeted the one file Task 8's
edit could break, this is the final confirmation with both changes
landed together.

# Test-suite small items (#868)

Watchdog timing, the real-content test, inert pragmas, counter edges.

Status: **implemented** in the PR that carries this line, together
with #866. Written 2026-10-01. What changed on the way: Task 2's mutation
check passed against a plain copy of the sample tutorial, because the
sample has never had a `#` line inside a fenced block (not since #53
added it). So the old test never guarded the fence bug. The fixture is
the sample with a `#` line added at the top of each of its twelve
fenced blocks, and the test asserts the exact heading list.

**Written for** the implementer of issue #868's four items. One PR is
enough: the items share no code. They are filed together because one
review found them, and they ship together because each is too small to
pay for its own CI round.

**Assumed:** the dev venv from DEVELOPER-AGENTS.md (`.venv-full`),
`pytest`, and `markdownlint-cli2`. Commands below use
`.venv-full/bin/python`.

**Not covered here:** changes to `chitragupta/sync_pool.py`'s behaviour
(the watchdog is right; only its tests are fragile), and any change to
`scripts/code_standards.py`'s counting. Item 4 is documentation only, as
the issue asks.

## What the issue gets wrong, checked before planning

- **Item 1's line numbers have moved.** The tests are now
  `tests/test_sync.py::TestStallWatchdog` (from line 1765) and
  `::TestStallWarning` (from line 2283). The stall tests that block on
  `blocked.wait(30)` against a 0.3 s timeout have a 100x margin and are
  not fragile. Three tests are:
  - `test_progress_resets_the_clock`: 0.2 s jobs against a 0.5 s
    timeout, 2.5x. It is also **vacuous**: 6 documents on 4 workers
    finish in about 0.4 s, under the 0.5 s timeout, so the run passes
    whether or not a completion resets the clock.
  - `test_a_run_that_finishes_between_warning_and_kill_is_not_killed`:
    0.4 s jobs against a 0.6 s timeout. It needs a job longer than half
    the timeout and shorter than the whole, so it is under 2x by
    construction. Widening the ratio cannot fix it.
  - `test_a_stall_cancels_jobs_that_never_started`: `time.sleep(0.5)` to
    "give a still-queued job a chance to start". On a loaded runner the
    job may not start inside 0.5 s, so the test **passes falsely**
    rather than failing.
- **Item 2's premise is wrong.**
  `content/drafts/digital-twins-for-software-engineers/tutorial.md` is
  tracked: `.gitignore` re-includes that directory as the shipped
  sample. The test runs on every fresh clone and on CI. Its skip branch
  is dead code. The real problem is different: the test pins the
  **current wording of a sample draft**, so a `draft-reviser` pass on
  that tutorial (retitle it, rename a step) reddens the suite for a
  content reason.
- **Item 3 has more sites than the issue lists.** There are 11 bare
  markers. Three are in measured code: `chitragupta/__main__.py:115`,
  `scripts/strip_tikz_load_workarounds.py:141`, and
  `scripts/render_diagrams.py:103`, which landed after the issue. Eight
  are under `tests/`. `tests/` is outside `[tool.coverage.run].source`,
  so a pragma there is inert as well.

## Global constraints

- Tests only, plus one CODE-STANDARDS table cell. No change to anything
  under `chitragupta/` other than deleting one comment.
- Coverage stays at `fail_under = 100` on both legs. Deleting a pragma
  must not uncover a line. Each deletion is verified below.
- C1 (25 statements per function) applies to `tests/`. Every new test
  function stays under it.
- PATCH version bump: "test-only additions" in DEVELOPER-AGENTS.md's
  "Versioning and releases".
- No citekey is typed anywhere. The fixture in Task 2 is a verbatim
  copy of a tracked draft, so the one citekey it carries
  (`feng_model-based_2023`) is the real one from that draft.

## Review focus

1. **A scripted `wait` that drifts from the real one.** `_as_they_land`
   calls `wait(pending, timeout=half, return_when=FIRST_COMPLETED)` and
   unpacks `(done, pending)`. The fake must take the same arguments and
   return two sets. If `sync_pool` ever imports `wait` differently, the
   monkeypatch stops reaching it. Task 1's timeout assertion catches
   that, because the real `wait` would not record anything.
2. **Join-instead-of-sleep must really join.** `ThreadPoolExecutor.shutdown(wait=True)`
   after an earlier `shutdown(wait=False)` still joins the worker
   threads. Task 1 Step 6 asserts that `executor._threads` are all dead
   afterwards, so a CPython change there fails loudly instead of
   bringing back the false pass.
3. **The pragma guard matching itself.** The guard's own source must not
   contain the bare marker as one contiguous string, or it flags its own
   file. Task 3 builds the pattern from two pieces.
4. **A pragma deletion that uncovers a line on Windows only.** The
   Windows leg has a different `exclude_lines`. All three measured sites
   are either `__main__` guards, which both configs exclude, or covered
   by a test that runs on both legs. Task 3 Step 5 checks the second
   claim.

---

### Task 1: Watchdog tests without timing margins

**Files:**

- Modify: `tests/test_sync.py` (`TestStallWatchdog`, `TestStallWarning`)

**Interfaces:**

- Consumes: `sync_pool._as_they_land(futures, executor, stalled) -> Iterator[Future]`,
  the module-level name `sync_pool.wait`, `pdf_text.terminate_workers(executor)`,
  and `config.PARSER_STALL_TIMEOUT`.
- Produces: `_ScriptedWait` and `_RecordingExecutor`, test-local helpers.

- [ ] **Step 1: Add the scripted helpers and the reset test** at the end
  of `TestStallWarning`'s section, as a new class:

```python
class _ScriptedWait:
    """Stands in for `concurrent.futures.wait` inside `sync_pool`: each
    call consumes one entry of `script`, the number of pending futures
    that complete in that window (0 is a silent window). Deterministic,
    so the reset logic is tested without a clock."""

    def __init__(self, script):
        self.script = list(script)
        self.timeouts = []

    def __call__(self, pending, timeout=None, return_when=None):
        self.timeouts.append(timeout)
        ordered = sorted(pending)
        n = self.script.pop(0)
        return set(ordered[:n]), set(ordered[n:])


class _RecordingExecutor:
    def __init__(self):
        self.calls = []

    def shutdown(self, wait=True, *, cancel_futures=False):
        self.calls.append(("shutdown", cancel_futures))


class TestTheWatchdogClock:
    """The between-completions rule, driven window by window. These
    replace the wall-clock versions, which could not be made to hold a
    3x margin (#868)."""

    @pytest.fixture(autouse=True)
    def _record_terminate(self, monkeypatch):
        monkeypatch.setattr(config, "PARSER_STALL_TIMEOUT", 10.0)
        monkeypatch.setattr(
            pdf_text, "terminate_workers", lambda ex: ex.calls.append(("terminate",))
        )

    def _run(self, monkeypatch, script):
        wait = _ScriptedWait(script)
        monkeypatch.setattr(sync_pool, "wait", wait)
        executor, stalled = _RecordingExecutor(), []
        landed = list(sync_pool._as_they_land(range(6), executor, stalled))
        return landed, executor, stalled, wait

    def test_a_completion_after_the_warning_resets_it(self, monkeypatch, caplog):
        landed, executor, stalled, wait = self._run(monkeypatch, [0, 1, 0, 1, 0, 4])
        assert sorted(landed) == list(range(6))
        assert stalled == [] and executor.calls == []
        assert wait.timeouts == [5.0] * 6
        assert caplog.text.lower().count("no completions in") == 3

    def test_two_silent_windows_in_a_row_stall_the_pool(self, monkeypatch, caplog):
        landed, executor, stalled, _ = self._run(monkeypatch, [1, 0, 0])
        assert landed == [0]
        assert stalled == [True]
        assert executor.calls == [("terminate",), ("shutdown", True)]
        assert "giving up on the 5 still outstanding" in caplog.text
```

The third test replaces
`test_a_run_that_finishes_between_warning_and_kill_is_not_killed`:

```python
    def test_a_run_that_finishes_between_warning_and_kill_is_not_killed(
        self, monkeypatch
    ):
        landed, executor, stalled, _ = self._run(monkeypatch, [0, 6])
        assert sorted(landed) == list(range(6))
        assert stalled == [] and executor.calls == []
```

- [ ] **Step 2: Prove the reset test is not vacuous.** Temporarily
  delete the `if done: warned = False` lines in
  `chitragupta/sync_pool.py` and run:

  `.venv-full/bin/python -m pytest tests/test_sync.py::TestTheWatchdogClock -v`

  Expected: `test_a_completion_after_the_warning_resets_it` FAILS. The
  third silent window then reaches the kill branch, so `stalled == [True]`.
  Restore the lines with `git checkout chitragupta/sync_pool.py`.

- [ ] **Step 3: Delete the wall-clock version** of
  `test_a_run_that_finishes_between_warning_and_kill_is_not_killed` from
  `TestStallWarning`. The scripted test in Step 1 replaces it under the
  same name.

- [ ] **Step 4: Widen `test_progress_resets_the_clock` to 15x, and say
  what it still proves.** Set the timeout to `3.0` (jobs stay at
  `0.2`). A passing run still lasts about 0.4 s, because the timeout
  only costs time when the test fails. Replace the docstring:

```python
        """A slow-but-moving run completes end to end through the real
        pool. The between-completions reset itself is pinned without a
        clock by TestTheWatchdogClock; this is the smoke check that the
        real `wait` and real threads agree with it."""
```

- [ ] **Step 5: Write the failing version of the join-based cancel
  check.** In `test_a_stall_cancels_jobs_that_never_started`, capture
  the executor through the `_executor_for` factory and replace both
  `time.sleep` calls:

```python
        executors = []

        def factory(workers):
            executors.append(thread_executor(workers))
            return executors[-1]

        monkeypatch.setattr(sync_pool, "_executor_for", factory)
        ...
        try:
            sync.run()
            at_stall = list(started)
        finally:
            blocked.set()
            # Joins every worker thread, so a job left queued (not
            # cancelled) has run by the time this returns. Deterministic
            # where the old sleep(0.5) was a race the test could lose by
            # passing.
            executors[0].shutdown(wait=True)
        assert not any(t.is_alive() for t in executors[0]._threads)
```

  Drop the now-unused `import time`.

- [ ] **Step 6: Prove it catches the bug.** Temporarily change
  `cancel_futures=True` to `False` in `sync_pool._as_they_land` and run
  the test. Expected: FAIL with "job(s) started after the stall".
  Restore with `git checkout chitragupta/sync_pool.py`.

- [ ] **Step 7: Run both classes and time them.**

  ```bash
  .venv-full/bin/python -m pytest tests/test_sync.py -k "Stall or WatchdogClock" -v --durations=10
  ```

  Expected: all pass. No test sleeps against a margin under 3x. The
  slowest test is still a 0.3 s stall test.

- [ ] **Step 8: Commit.** "Drive the stall watchdog's reset logic
  window by window instead of by wall clock"

### Task 2: Pin the fence regression to a fixture, not the sample draft

**Files:**

- Create: `tests/fixtures/dossier/fence-heavy-tutorial.md`, a verbatim
  copy of `content/drafts/digital-twins-for-software-engineers/tutorial.md`
  at this commit
- Modify: `tests/test_dossier.py:203-215`

- [ ] **Step 1:** Run:

  ```bash
  mkdir -p tests/fixtures/dossier && cp content/drafts/digital-twins-for-software-engineers/tutorial.md tests/fixtures/dossier/fence-heavy-tutorial.md
  ```

- [ ] **Step 2: Repoint the test and drop the skip:**

```python
    def test_a_fence_heavy_tutorial_outlines_cleanly(self):
        """Regression guard against the fence bug on real content: a
        frozen copy of the shipped sample tutorial, which is mostly shell
        and Python whose comments start with `#`. A copy, so that
        revising the sample draft cannot redden this test for a content
        reason (#868)."""
        fixture = Path(__file__).parent / "fixtures" / "dossier" / "fence-heavy-tutorial.md"
        titles = [s.title for s in dossier.sections(fixture.read_text(encoding="utf-8"))]
        assert titles[0] == "Build a Digital Twin for a Potted Plant"
        assert "Step 1: Create the project folder" in titles
        assert not any(t.startswith("!") or t.startswith("/") for t in titles)
```

  Add `from pathlib import Path` if the module lacks it.

- [ ] **Step 3: Prove it guards the bug.** Temporarily make
  `dossier.sections` treat every `#` line as a heading. The simplest
  way is to skip its fence tracking. Run
  `.venv-full/bin/python -m pytest tests/test_dossier.py -k fence_heavy -v`.
  Expected: FAIL on the `startswith("!")`/`"/"` assertion, because
  shebang and path comments come back as titles. Restore.

- [ ] **Step 4: Commit.** "Pin the fence regression to a frozen
  tutorial fixture instead of the live sample draft"

### Task 3: Delete the inert pragmas and keep them from coming back

**Files:**

- Modify: `chitragupta/__main__.py:115`, `scripts/strip_tikz_load_workarounds.py:141`,
  `scripts/render_diagrams.py:103`
- Modify (comment only): `tests/test_ledger_read.py:115,136`,
  `tests/test_enrich_topic_graph.py:280`, `tests/test_pdf_text.py:1809`,
  `tests/test_path_confinement.py:102`, `tests/test_review.py:196`,
  `tests/test_verbatim_check.py:2204`. The `test_dossier.py` site is
  already gone with Task 2.
- Test: `tests/test_coverage_configs_agree.py`

- [ ] **Step 1: Write the guard.** Append to
  `tests/test_coverage_configs_agree.py`:

```python
# Built from two pieces so this file does not match itself.
_BARE_PRAGMA = re.compile("pragma: no " + r"cover(?!-windows)")
_SCANNED = ("chitragupta", "scripts", ".claude/hooks", "tests", "bench")


def test_no_bare_no_cover_pragma_is_left_in_the_tree():
    """Both configs set `exclude_lines`, which *replaces* coverage's
    default list, so a bare no-cover pragma is honoured on neither leg
    (#868). It reads as an exclusion and is not one. Under `tests/` and
    `bench/` it is inert twice over, because neither is measured."""
    found = [
        f"{path.relative_to(REPO_ROOT)}:{n}"
        for root in _SCANNED
        for path in sorted((REPO_ROOT / root).rglob("*.py"))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if _BARE_PRAGMA.search(line)
    ]
    assert not found, "inert coverage pragma(s):\n  " + "\n  ".join(found)


def test_the_bare_pragma_pattern_spares_the_windows_marker():
    assert _BARE_PRAGMA.search("x  # pragma: no " + "cover - why")
    assert not _BARE_PRAGMA.search("x  # pragma: no " + "cover-windows")
```

- [ ] **Step 2: Run it and see the 10 sites listed.**
  `.venv-full/bin/python -m pytest tests/test_coverage_configs_agree.py -v`.
  Expected: FAIL naming the 10 remaining sites (11 before Task 2).

- [ ] **Step 3: Delete the three measured markers.** The two `__main__`
  guards are excluded by the `if __name__ == .__main__.:` rule in both
  configs. In `chitragupta/__main__.py:115`, drop the comment entirely:
  `tests/test_package_entrypoint.py::test_an_uninstalled_distribution_is_not_fatal`
  covers the line.

- [ ] **Step 4: Reword the seven test-side comments** so each keeps its
  reason without the marker, for example
  `# pragma: no cover - the point is it is never called` becomes
  `# never called: that is the point of the test`, and
  `# pragma: no cover  # Windows without developer mode` becomes
  `# Windows without developer mode`.

- [ ] **Step 5: Run the guard, then full coverage on the measured
  roots:**

  ```bash
  .venv-full/bin/python -m pytest tests/test_coverage_configs_agree.py -v
  ```

  It should pass. Then run full coverage:

  ```bash
  .venv-full/bin/python -m pytest --cov --cov-branch --cov-report=term-missing:skip-covered -q
  ```

  Expected: TOTAL 100.00%, and no `__main__.py`,
  `strip_tikz_load_workarounds.py` or `render_diagrams.py` line in the
  missing column. Confirm that `test_package_entrypoint.py` has no
  Windows skip on the covering test with
  `grep -n "skipif\|win32" tests/test_package_entrypoint.py`.

- [ ] **Step 6: Commit.** "Delete the inert no-cover pragmas and fail
  the suite if one comes back"

### Task 4: State the counter edges in CODE-STANDARDS

**Files:**

- Modify: `docs/CODE-STANDARDS.md:230-231` (the "Counted as" cells)

- [ ] **Step 1: Edit the two cells:**

  C1: "`ast` statement nodes in the body, not descending into nested
  definitions. A docstring is one statement (an `Expr`); a lambda or
  comprehension is an expression and counts zero however large it is"

  C2: "Physical lines that are neither blank nor a whole-line comment.
  A line inside a triple-quoted string that begins with `#` is dropped
  as though it were a comment"

- [ ] **Step 2: Check that nothing pins the old cell text.**
  `grep -rn "not descending into nested" tests/` should return nothing.
  Then run `markdownlint-cli2 docs/CODE-STANDARDS.md`, which should be
  clean. `MD013` ignores tables.

- [ ] **Step 3: Commit.** "State the docstring-costs-one and
  comprehension-is-free counting rules"

### Task 5: Finish

- [ ] Bump the PATCH version in `pyproject.toml`.
- [ ] Run `scripts/check_local.sh` and the full suite.
- [ ] Open the PR with the `## Commit message` fence that
  `merge_pr.py --check` accepts. The test plan says that item 2's
  premise was corrected and why, and lists the 11 pragma sites against
  the issue's 2.

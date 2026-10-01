# Split the prose pins by what they pin, and give the diagram list one source (#866)

Status: **implemented** in the PR that carries this line, together
with #868. Written 2026-10-01. What changed on the way: the old
`test_it_stops_at_the_next_top_level_trigger` was dropped rather than
ported. It pinned a failure mode only an indentation reader has, and
the mixed-filter fixture still carries a `pull_request:` block after
`push:`. The new reader also reads the three reformatted triggers
correctly, where the old one could only report them as unreadable.

**Written for** the implementer of issue #866. The issue says "tests
only". The goal is that a red test's file name says why it went red: a
doc sentence that no longer matches its source, or a workflow whose
shape broke a rule.

**Assumed:** `pyyaml` is a direct dev-group dependency
(`pyproject.toml`: `pyyaml = ">=6.0,<7.0"`), and
`tests/test_check_local.py` already does `import yaml`. The reason
`_push_trigger_filters`'s docstring gives for not using a YAML parser
(that pyyaml "reaches this venv only as a transitive dependency of the
docs group") is **no longer true**, so nothing has to be relocked.

**Not covered here:** rewording any pinned sentence. The issue says the
pinned sentences stay. Also not covered: DIAGRAMS.md's prose count ("The
same thirteen are also checked in"), which nothing pins today; that is
a separate pin if anyone wants one.

## Decisions an implementer would otherwise invent

1. **The register checks stay in `test_technical_debt_scan.py`.** Its
   docstring, `docs/TECHNICAL-DEBT.md:92,119` and
   `docs/CODE-STANDARDS.md:549` all describe it as *the* check that
   TECHNICAL-DEBT.md describes the C1/C2 register correctly. That part
   (lines 1-365) is what the name promises, so it does not move. Only
   the #353 and #512 additions move out. The split produces three files
   rather than the issue's two, and no doc that names the module goes
   stale.
2. **Where each moved check lands.** The rule: a value restated by hand
   somewhere (a doc sentence, a config comment) goes to
   `test_docs_pins.py`. A structural rule about a workflow file goes to
   `test_workflow_pins.py`.

   | Check | From | To |
   | --- | --- | --- |
   | `_regex_pin` and its twin | `:395` | `test_docs_pins.py` |
   | quoted lint target matches `ci.yml` (+2 twins) | `:486` | `test_docs_pins.py` |
   | quoted coverage source matches pyproject (+2 twins) | `:493` | `test_docs_pins.py` |
   | bench self-check count matches the tree (+1 twin) | `:498` | `test_docs_pins.py` |
   | `.pylintrc` py-version matches pyproject | `:581` | `test_docs_pins.py` |
   | `.pylintrc` does not call itself unenforced | `:597` | `test_docs_pins.py` |
   | no branch filter mixed with a tag filter | `:604` | `test_workflow_pins.py` |
   | venv cache has no prefix fallback | `:632` | `test_workflow_pins.py` |
   | `TestThePushTriggerReaderItself` (6 cases) | `:649` | rewritten for the YAML reader, `test_workflow_pins.py` |

3. **The diagram list's one source is DIAGRAMS.md's own `<name>`
   table.** The issue says to "derive `NAMES` from
   `docs/diagrams/*.mmd`", but a glob has no order, and order is what
   ties fenced block *i* to export *i*. Matching blocks to files by
   content was considered and rejected: a drifted block then matches no
   file, and the failure can no longer say which export drifted, which
   is the message the test exists to give. The "Editing these" table
   (DIAGRAMS.md:1131) is ordered, is already the list readers use, and
   already has to be kept. The test reads its order from the table and
   then requires the `*.mmd` glob and `svg/sources.json` to hold exactly
   the same set. The hand-typed list in the test disappears. A
   hand-maintained list remains only where a reader needs it.
4. **The `fail_under` pin is already done.** #863 added
   `tests/test_coverage_configs_agree.py::test_developer_agents_states_the_configs_floor`
   with both twins (`test_the_pre_863_sentence_is_caught`,
   `test_a_reworded_sentence_fails_loudly`). Nothing to add. The PR says
   so.

## Global constraints

- Tests only, plus the one-sentence update to `DEVELOPER-AGENTS.md:850`
  in Task 3.
- No test is weakened. Each existing assertion and its "fails when
  reworded" twin moves together, with the same message text, so that
  `pytest.raises(match=...)` twins keep matching.
- `encoding="utf-8"` on every `read_text`, because the Windows leg's
  locale codec is cp1252.
- PyYAML reads the bare key `on:` as the boolean `True` (YAML 1.1). The
  reader handles both keys.
- PATCH version bump (test-only).

## Review focus

1. **`on:` parsed as `True`.** A reader that does `doc["on"]` raises
   `KeyError` on every real workflow. Task 2's first fixture test uses a
   real-shaped file, so it fails loudly in that case and does not pass
   silently.
2. **The trigger forms YAML allows.** `on: push`,
   `on: [push, pull_request]`, `push:` with a null body, and
   `push: {branches: [main]}` all appear in real workflows. Each needs a
   defined answer. Task 2 pins all of them.
3. **A table row added without its `.mmd`, or the reverse.** Task 4's
   set-equality test names the missing side in its message.
4. **A reformatted `<name>` table that parses to zero rows.** It must
   fail loudly. It must not produce an empty `NAMES`, because that would
   make every parametrised test vanish while the run stays green. Task 4
   has the twin for this.
5. **Lost tests during the move.** Task 3 Step 3 compares the
   collected node ids before and after.

---

### Task 1: Move the doc pins into `tests/test_docs_pins.py`

**Files:**

- Create: `tests/test_docs_pins.py`
- Modify: `tests/test_technical_debt_scan.py`, deleting lines 370-647,
  which hold the #353 block and `TestTheToolingConfigDoesNotDriftFromWhatItConfigures`.
  The workflow half goes to Task 2.

**Interfaces:**

- Produces: `_regex_pin(pattern, text, what) -> tuple[str, ...]`, now
  importable from `test_docs_pins`. The #353 comment invites #348/#345
  to reuse it, so its new home is the place to import it from.

- [ ] **Step 1: Record the baseline node ids.**

  ```bash
  .venv-full/bin/python -m pytest tests/test_technical_debt_scan.py --collect-only -q | grep :: | sed 's/.*:://' | sort > /tmp/866-before.txt
  ```

- [ ] **Step 2: Create `tests/test_docs_pins.py`** with a module
  docstring saying what belongs in it:

```python
"""Values restated by hand in prose or in a config comment, each pinned
to the file that owns the value.

A failure here means a sentence (or a comment) has drifted from the
fact it quotes. Fix the sentence, or teach the pattern the new wording;
it does not mean CI is misconfigured. Workflow-shape rules are
`tests/test_workflow_pins.py`; the C1/C2 register's description is
`tests/test_technical_debt_scan.py`. Split by what reddens (#866) so a
docs-only PR goes red for a docs reason.
"""

import ast
import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DEBT_DOC = REPO_ROOT / "docs" / "TECHNICAL-DEBT.md"
CODE_STANDARDS_DOC = REPO_ROOT / "docs" / "CODE-STANDARDS.md"
BENCH_README = REPO_ROOT / "bench" / "README.md"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PYPROJECT_TOML = REPO_ROOT / "pyproject.toml"
PYLINTRC = REPO_ROOT / ".pylintrc"
```

  Below it, move these **verbatim** from `test_technical_debt_scan.py`:
  the #353 history comment (`:370-392`), `_regex_pin`, the three
  `_..._RE` patterns, `_ci_lint_target`, `_bench_self_check_counts`, the
  two `_assert_..._matches` helpers,
  `TestTheOtherDriftProneClaimsArePinned`,
  `TestTheNewPinsFailLoudlyWhenReworded`, and the two `.pylintrc` tests
  as a class `TestThePylintrcDoesNotDriftFromWhatItConfigures`. Keep
  their docstrings, which carry the m-83 history. Copy the
  `debt_doc`/`code_standards_doc`/`bench_readme` fixtures as well,
  including the cp1252 comment. Both modules use `debt_doc`.

- [ ] **Step 3: Replace the one regex that reads TOML.** Change
  `_pyproject_coverage_source` to:

```python
def _pyproject_coverage_source() -> list[str]:
    """`[tool.coverage.run].source`, read from `pyproject.toml` rather
    than typed."""
    with open(PYPROJECT_TOML, "rb") as f:
        return tomllib.load(f)["tool"]["coverage"]["run"]["source"]
```

  The old `^source =` regex matched the first `source =` line in
  any table.

- [ ] **Step 4: Prune `test_technical_debt_scan.py`'s imports.**
  `ast`, `tomllib` and `CI_WORKFLOW`/`PYPROJECT_TOML`/`BENCH_README`/`CODE_STANDARDS_DOC`
  should now be unused. Check with
  `.venv-full/bin/ruff check tests/test_technical_debt_scan.py tests/test_docs_pins.py`.

- [ ] **Step 5: Run both modules.**

  ```bash
  .venv-full/bin/python -m pytest tests/test_technical_debt_scan.py tests/test_docs_pins.py -v
  ```

  Expected: all pass.

- [ ] **Step 6: Prove one moved pin still bites.** Temporarily change
  `bench/README.md`'s "N of the M scripts here" to a wrong N, run
  `test_docs_pins.py`, and expect FAIL with "self-check count no longer
  matches". Restore.

- [ ] **Step 7: Commit.** "Move the hand-restated-value pins out of
  the technical-debt scan into test_docs_pins.py"

### Task 2: Workflow rules with a real YAML reader, in `tests/test_workflow_pins.py`

**Files:**

- Create: `tests/test_workflow_pins.py`
- Modify: `tests/test_technical_debt_scan.py`, deleting the rest of the
  old line range 545-695: `PYLINTRC`/`DOCS_WORKFLOW`, `_push_trigger_filters`,
  the two workflow tests, and `TestThePushTriggerReaderItself`

**Interfaces:**

- Produces: `_push_filters(workflow: Path) -> set[str] | None`. It
  returns `None` when the workflow has no push trigger, and the filter
  keys (possibly empty) when it has one.
  `_workflow(path: Path) -> dict` returns the parsed workflow with the
  `on`/`True` key normalised.

- [ ] **Step 1: Write the reader's tests first.** These replace
  `TestThePushTriggerReaderItself`. The three reformat cases used to
  read as "unreadable". Under a YAML loader they read correctly, which
  is the point of the change.

```python
"""Structural rules about `.github/workflows/*.yml`, read with a YAML
loader rather than by indentation (#866). A failure here means a
workflow broke a rule its own header documents, not that a document
drifted; that is `tests/test_docs_pins.py`."""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
CI_WORKFLOW = WORKFLOWS / "ci.yml"
DOCS_WORKFLOW = WORKFLOWS / "docs.yml"


def _workflow(path: Path) -> dict:
    """The parsed workflow. PyYAML follows YAML 1.1, where a bare `on`
    is the boolean True, so the trigger block can arrive under either
    key; it is normalised to "on" here, once."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if True in doc:
        doc["on"] = doc.pop(True)
    return doc


def _push_filters(workflow: Path) -> "set[str] | None":
    """Filter keys under the workflow's push trigger: None if there is no
    push trigger at all, an empty set if push is unfiltered. The caller
    tells those apart. Collapsing them is how a drift guard turns into a
    silent pass (#509)."""
    on = _workflow(workflow).get("on")
    if on == "push" or (isinstance(on, list) and "push" in on):
        return set()
    if not isinstance(on, dict) or "push" not in on:
        return None
    return set(on["push"] or {})


def _write(tmp_path, body: str) -> Path:
    path = tmp_path / "w.yml"
    path.write_text(f"name: W\non:\n{body}jobs: {{}}\n", encoding="utf-8")
    return path


class TestThePushTriggerReader:
    def test_it_sees_a_mixed_filter(self, tmp_path):
        workflow = _write(
            tmp_path,
            "  push:\n    branches: [main]\n    tags-ignore:\n      - 'v*'\n"
            "  pull_request:\n    branches: [main]\n",
        )
        assert _push_filters(workflow) == {"branches", "tags-ignore"}

    @pytest.mark.parametrize(
        "block",
        [
            "  push:  # main only\n    branches: [main]\n",
            "  push: {branches: [main]}\n",
            "   push:\n     branches: [main]\n",
        ],
        ids=["trailing-comment", "inline-mapping", "different-indent"],
    )
    def test_a_reformatted_trigger_still_reads_correctly(self, tmp_path, block):
        """Each of these defeated the old indentation reader."""
        assert _push_filters(_write(tmp_path, block)) == {"branches"}

    @pytest.mark.parametrize(
        "on", ["on: push\n", "on: [push, pull_request]\n", "on:\n  push:\n"]
    )
    def test_an_unfiltered_push_reads_as_empty_not_none(self, tmp_path, on):
        path = tmp_path / "w.yml"
        path.write_text(f"name: W\n{on}jobs: {{}}\n", encoding="utf-8")
        assert _push_filters(path) == set()

    def test_no_push_trigger_reads_as_none(self, tmp_path):
        assert _push_filters(_write(tmp_path, "  workflow_dispatch:\n")) is None
```

- [ ] **Step 2: Run them before the helpers exist.** Put the helpers
  in only after this run. Expected: FAIL with `NameError`. Then add the
  helpers, run again, and expect PASS. Then delete the
  `if True in doc` normalisation, run again, and expect
  `test_it_sees_a_mixed_filter` to FAIL, which proves Review Focus 1.
  Put it back.

- [ ] **Step 3: Move the two rules onto the parsed form:**

```python
class TestTheWorkflowsKeepTheirOwnRules:
    def test_no_workflow_mixes_a_branch_filter_with_a_tag_filter(self):
        """m-84: under a `branches:`-filtered push trigger a tag push
        already matches nothing, so `tags-ignore` there does not narrow
        the trigger. It re-enables builds for every tag the ignore list
        does not name. `ci.yml`'s own header documents the rule."""
        for workflow in (CI_WORKFLOW, DOCS_WORKFLOW):
            filters = _push_filters(workflow)
            # Both are known to filter their push trigger, so None or an
            # empty set means the trigger changed shape under this check.
            # Refused loudly rather than passed over.
            assert filters, (
                f"{workflow.name} no longer has a filtered push trigger, so the "
                "branch/tag check below did not run. Do not delete this assertion."
            )
            if {"branches", "branches-ignore"} & filters:
                assert not {"tags", "tags-ignore"} & filters, (
                    f"{workflow.name}'s push trigger mixes a branch filter with a tag "
                    f"filter ({sorted(filters)}), which widens it rather than narrowing it."
                )

    def test_the_venv_cache_has_no_prefix_fallback(self):
        """m-87: `restore-keys` restored an older lock's venv, and
        `poetry install` without `--sync` never uninstalls, so a package
        removed from the lock stayed importable. CI would keep passing on
        an import a clean install cannot satisfy."""
        steps = [
            (job, step.get("name", step.get("uses", "?")))
            for job, spec in _workflow(CI_WORKFLOW)["jobs"].items()
            for step in spec.get("steps", [])
            if "restore-keys" in (step.get("with") or {})
        ]
        assert steps == [], (
            f"ci.yml restores a cache by key prefix again: {steps}. "
            "See #512/m-87 for why that carries a removed package forward forever."
        )
```

- [ ] **Step 4: Add the twin for the cache rule.** A YAML-walk version
  could miss a step nested where the walk does not look:

```python
    def test_the_cache_rule_sees_a_restore_keys_step(self, tmp_path):
        path = tmp_path / "ci.yml"
        path.write_text(
            "on: push\njobs:\n  t:\n    steps:\n      - uses: actions/cache@v4\n"
            "        with:\n          key: k\n          restore-keys: k-\n",
            encoding="utf-8",
        )
        assert any(
            "restore-keys" in (s.get("with") or {})
            for spec in _workflow(path)["jobs"].values()
            for s in spec["steps"]
        )
```

  To avoid a second copy of the comprehension, factor it into
  `_restore_keys_steps(path) -> list[tuple[str, str]]`, used by both
  this test and Step 3.

- [ ] **Step 5: Delete the old workflow half** from
  `test_technical_debt_scan.py`. Then run:

  ```bash
  .venv-full/bin/python -m pytest tests/test_workflow_pins.py tests/test_technical_debt_scan.py -v
  ```

  Expected: all pass. Then run
  `grep -n "startswith(\"    \")\|_push_trigger_filters" tests/*.py`,
  which should find nothing. That meets success criterion 1.

- [ ] **Step 6: Commit.** "Read workflow triggers with a YAML loader
  and move the workflow rules to test_workflow_pins.py"

### Task 3: Account for every moved test, and point the docs at the new homes

**Files:**

- Modify: `DEVELOPER-AGENTS.md:850`

- [ ] **Step 1: Update the one sentence that calls the module "the
  doc-drift test".** Change `` `tests/test_technical_debt_scan.py`, the
  doc-drift test, for the one class of factual claim that has a
  machine-readable source of truth`` to name
  `tests/test_technical_debt_scan.py` and `tests/test_docs_pins.py`, the
  doc-drift tests, for the claims that have a machine-readable source
  of truth. `docs/TECHNICAL-DEBT.md:92,119` and
  `docs/CODE-STANDARDS.md:549` describe only the register check, which
  did not move, and need no edit.

- [ ] **Step 2: Grep for any other stale reference.**
  `grep -rn "test_technical_debt_scan" --include=*.md . | grep -v "^./plans/\|^./.claude/worktrees"`.
  Every hit should still be about the register. `plans/` is allowed to
  go stale (`plans/README.md`).

- [ ] **Step 3: Diff the node ids.**

```bash
.venv-full/bin/python -m pytest tests/test_technical_debt_scan.py tests/test_docs_pins.py \
  tests/test_workflow_pins.py --collect-only -q | grep :: | sed 's/.*:://' | sort > /tmp/866-after.txt
diff /tmp/866-before.txt /tmp/866-after.txt
```

  Expected: the only removed ids are the six `TestThePushTriggerReaderItself`
  cases. The only added ids are the Task 2 reader and cache-twin tests.
  Every `fails_loudly`/`twin` id is present on both sides, which meets
  success criterion 3.

- [ ] **Step 4: Commit.** "Name test_docs_pins.py beside the
  technical-debt scan as the doc-drift tests"

### Task 4: One source for the diagram list

**Files:**

- Modify: `tests/test_diagrams_in_sync.py:40-77`

- [ ] **Step 1: Write the table reader and its loud-failure twin:**

```python
_EDITING_HEADING = "## ✏ Editing these"
_NAME_ROW = re.compile(r"^\| [^|]+ \| `([\w-]+)` \|$", re.MULTILINE)


def _export_names(text: str) -> list[str]:
    """The `<name>` column of DIAGRAMS.md's "Editing these" table, in
    order. That table is the one hand-kept list of diagrams (#866), and
    its order is what ties fenced block i to export i. Refuses to return
    an empty list: an empty NAMES would make every parametrised test
    below vanish while the run stayed green."""
    _, found, tail = text.partition(_EDITING_HEADING)
    names = _NAME_ROW.findall(tail) if found else []
    assert names, (
        f"docs/DIAGRAMS.md no longer has a {_EDITING_HEADING!r} table this test can "
        "read. Rewording it is fine; teach _NAME_ROW the new shape in the same change."
    )
    return names


NAMES = _export_names(DIAGRAMS_TEXT)
```

  Delete the hand-typed `NAMES` list and the comment above it. That
  comment's point, that order ties a block to a file, moves into the
  docstring above.

```python
class TestTheNameListReadsTheTable:
    def test_a_reworded_table_fails_loudly(self):
        with pytest.raises(AssertionError, match="no longer has"):
            _export_names("# Diagrams\n\nno table here\n")

    def test_it_reads_names_in_order(self):
        text = f"{_EDITING_HEADING}\n\n| Diagram | `<name>` |\n| --- | --- |\n| B | `b-two` |\n| A | `a-one` |\n"
        assert _export_names(text) == ["b-two", "a-one"]
```

  The header row `` | Diagram | `<name>` | `` does not match, because
  `<` is not in `[\w-]`. The second test pins that.

- [ ] **Step 2: Replace the count test with the set-agreement test**
  in `TestTheScanIsNotVacuous`:

```python
    def test_the_table_the_exports_and_the_blocks_agree(self):
        on_disk = sorted(p.stem for p in DIAGRAMS_DIR.glob("*.mmd"))
        assert sorted(NAMES) == on_disk, (
            "docs/DIAGRAMS.md's 'Editing these' table and docs/diagrams/*.mmd disagree. "
            f"Only in the table: {sorted(set(NAMES) - set(on_disk))}; "
            f"only on disk: {sorted(set(on_disk) - set(NAMES))}."
        )
        assert len(BLOCKS) == len(NAMES), (
            f"docs/DIAGRAMS.md has {len(BLOCKS)} fenced blocks but its 'Editing these' "
            f"table lists {len(NAMES)}. Add or remove the row with the diagram."
        )
```

  `test_every_export_is_in_the_manifest` stays as it is. It now
  compares the manifest against the table rather than against a third
  copy.

- [ ] **Step 3: Prove it bites both ways.** Temporarily (a) delete the
  `t2-topic-graphs` row from the table and (b) separately rename
  `docs/diagrams/t2-topic-graphs.mmd`. Run
  `.venv-full/bin/python -m pytest tests/test_diagrams_in_sync.py -v`
  each time. Expected: FAIL naming the missing side each time. Restore
  with `git checkout docs/`.

- [ ] **Step 4: Run it clean, then grep for the old list.**
  `grep -n '"v1-overview"' tests/` should find nothing, which meets
  success criterion 2.

- [ ] **Step 5: Commit.** "Read the diagram list from DIAGRAMS.md's
  own table instead of a copy in the test"

### Task 5: Finish

- [ ] Bump the PATCH version in `pyproject.toml`.
- [ ] Run `scripts/check_local.sh` and the full suite under `.venv-full`.
- [ ] Open the PR with the `## Commit message` fence that
  `merge_pr.py --check` accepts. Record three things in the
  description: the three-file split (Decision 1), the table rather than
  the glob as the diagram list's source (Decision 3), and that the
  `fail_under` pin already shipped with #863 (Decision 4).

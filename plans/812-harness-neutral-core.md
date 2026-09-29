# 🔌 Claude Code, Codex and OpenCode on one core: implementation plan (#812, #900)

> **For agentic workers:** REQUIRED SUB-SKILL: use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to carry out this plan task by task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

Status: **Tasks 1-9 built, in one PR; Task 0 measured for Codex and in
part for OpenCode; Task 10's local-model runs outstanding.** Written
2026-09-26, rescoped and built 2026-09-29.
The maintainer asked for a single PR rather than one per group. Task 0
was run afterwards against Codex and OpenCode with a stand-in model; see
"Measured" below, and [docs/HARNESS.md](../docs/HARNESS.md) for what is
still not. See "What changed along the way" at the end.

**Goal:** Drive the pipeline from Claude Code, Codex and OpenCode, with
the citekey gate just as strong on all three. The model checks its own
draft, a check it cannot skip runs on every write, and `draft render`
refuses an unknown key in every format.

**Architecture:** One gate, `chitragupta/citation_gate.py`, sits under
two layers:

- **Self-check (asked).** The skill's existing "run
  `python -m chitragupta.draft gate` before presenting" step. It is
  already in every skill; this plan only makes its wording
  harness-neutral.
- **Mandatory check (enforced).** A thin per-harness launcher runs the
  existing hook scripts in `.claude/hooks/` on every write to a draft:
  - Claude Code: `.claude/settings.json`, unchanged.
  - Codex: a new `.codex/hooks.json`.
  - OpenCode: a new plugin that passes each write to the same hook
    script on stdin.

  The hooks learn one new payload shape: `apply_patch` patch text.
  Codex and OpenCode use the same patch format.

`draft render` runs the gate before producing any format, as the last
check.

**Tech stack:** Python 3 standard library for everything under
`chitragupta/` and `.claude/hooks/`. Plain ES-module JavaScript (no
dependencies, no TypeScript) for the OpenCode plugin, tested with
`node --test`. pytest for everything else.

**Spec:** issues
[#812](https://github.com/prasadtalasila/chitragupta/issues/812) and
[#900](https://github.com/prasadtalasila/chitragupta/issues/900), plus
the scope decisions in
[#812's comment of 2026-09-29](https://github.com/prasadtalasila/chitragupta/issues/812#issuecomment-5886389084).

**Out of scope:**

- Continue ([#901](https://github.com/prasadtalasila/chitragupta/issues/901)).
- The MCP server. It moves to #901, where it is Continue's enforcement;
  neither Codex nor OpenCode needs it.
- Developing chitragupta *itself* from Codex or OpenCode.
  `code_standards_hook.py` is not registered for either.
- A container image for a second harness.
- Judging whether a local model writes *good* prose.

## Global constraints

Every task inherits these.

- **The invariant.** A citekey may be used only if it is in the
  human's `.bib` export *and* in the ledger from a real PDF parse.
  - No task generates, guesses or rewrites a citekey.
  - A refusal names the bad key and its line, and **never suggests a
    "closest" ledger key**.
  - Refusal tests use a self-evidently fake key such as
    `not_a_real_citekey_2026`, following `tests/test_citation_gate.py`
    and `session_start_hook.py`'s
    `preflight_probe_not_a_real_citekey`. Keys a test needs to *pass*
    are inserted into a temporary ledger with `make_reference`
    (`tests/conftest.py:243`).
- **No new gate.** Every enforcement point calls the existing gate.
  Nothing new is promoted into a gate, and there is no flag or config
  key that disables one (`docs/HOOKS.md`, "Deliberately not done").
- **Tier 1.** `chitragupta.draft` and everything the gate chain imports
  stay standard-library only (`docs/ARCHITECTURE.md:640-652`).
- **Size limits** (`docs/CODE-STANDARDS.md`), enforced by
  `tests/test_code_standards_scan.py`:
  - at most **25 statements** per function;
  - at most **250 code lines** per module in `chitragupta/` and
    `scripts/`;
  - cognitive complexity at most 25.

  Current headroom, measured with `scripts/code_standards.py`:

  | Module | Code lines | Tightest function |
  | --- | --- | --- |
  | `render_output/__init__.py` | **250/250** | `render` at **24/25** statements |
  | `citation_gate.py` | 247 | |
  | `hook_launchers.py` | 246 | |
  | `init.py` | 205 | |
  | `render_output/_cli.py` | 157 | |
  | `.claude/hooks/citation_gate_hook.py` | 153 | |

- **Annotations and lint.**
  - Every `def` under `chitragupta/` has a return annotation
    (`tests/test_annotation_scan.py`).
  - Zero messages from
    `pylint --rcfile=.pylintrc chitragupta scripts .claude/hooks`,
    `ruff check` and `ruff format --check`.
  - Line length is 100.
- **Coverage.** 100% line and branch, including `.claude/hooks`
  (`pyproject.toml:327`). The Windows leg also holds 100%. The only
  allowed carve-out is `# pragma: no cover-windows` on pandoc-only
  lines.
- **Comments.** "Why" comments only, never "what". Match the existing
  modules' prose-docstring style.
- **Versioning.**
  - Every PR bumps `[tool.poetry].version`, checked by
    `scripts/check_version_bump.py`.
  - Task 1 (render) is **MINOR**, by maintainer decision on
    2026-09-29.
  - Tasks 2-9 are MINOR, since they add backward-compatible
    functionality.
  - Task 10 (docs and recorded runs) is PATCH.
  - Branch every PR off the latest `origin/main`.
- **Hooks stay in `.claude/hooks/`.** Codex's and OpenCode's launchers
  point there. Moving them would churn about 28 test files and the
  coverage source for no behavioural gain.
- **Skills stay in `.claude/skills/`.** Claude Code and OpenCode read
  that folder natively. If Codex cannot be pointed at it, `init` copies
  it (Task 9).
- **The launcher contract** (`docs/HOOKS.md:423-518`) holds for every
  new launcher:
  - the interpreter is `python`;
  - subprocesses use `sys.executable`;
  - stdout is one JSON document or nothing;
  - only the gate may block.

## Review focus

Each of these has a pinning test in the task that owns it.

1. **A patch that touches several drafts.** Every draft it adds,
   updates or moves is gated, not just the first (Task 3).
2. **A patch-shaped payload whose headers cannot be read but which
   mentions `content/drafts/`.** It is blocked, not let through. This
   is the one deliberate reversal of "malformed stdin fails open"
   (Task 3).
3. **A Codex relative path while the session's working directory is a
   subfolder.** It resolves against the payload's `cwd`, not the
   project root (Task 3).
4. **Codex project hooks that were never trusted.** A draft changed
   with no hook firing makes the skill's own `draft gate` run print a
   warning, instead of the gate staying off silently (Task 6).
5. **OpenCode with no working `python`.** A write to a draft is
   refused with "the citation gate could not run". A write to any other
   file is left alone (Task 7).

---

## 🗺 File map

| File | Status | Responsibility |
| --- | --- | --- |
| `chitragupta/render_output/_gate.py` | create | Gate the draft text before any render, and raise `UngatedDraft` |
| `chitragupta/render_output/__init__.py` | modify | Call `_gate.gated_warnings` in place of `_draft_warnings`, so the code-line count does not grow |
| `chitragupta/render_output/_cli.py` | modify | Report `UngatedDraft` as `[error]` and return 1 |
| `.claude/hooks/patch_paths.py` | create | Which files an `apply_patch` envelope writes (Add, Update, Move to) |
| `.claude/hooks/draft_target.py` | modify | `targets_from_stdin`: every draft in a payload, for `file_path` or patch payloads; fail closed on an unreadable patch that mentions drafts |
| `.claude/hooks/citation_gate_hook.py` | modify | Gate every targeted draft in one gate call; block on `UnreadablePatch`; tell the gate a hook called it |
| `.claude/hooks/style_check_hook.py` | modify | Check every targeted draft |
| `.codex/hooks.json` | create | Codex launcher for the gate, style and session-start hooks |
| `chitragupta/launcher_configs.py` | create | The launcher configs each harness uses, and dead-launcher faults across all of them |
| `chitragupta/gate_liveness.py` | create | Record drafts a hook gated; warn when a draft changed with no hook firing |
| `chitragupta/citation_gate.py` | modify | Replace the fault-printing loop in `run` with one `gate_liveness.observe(paths)` call |
| `.claude/hooks/session_start_hook.py` | modify | Report launcher faults from every config, via `launcher_configs` |
| `.opencode/plugins/chitragupta-gate.js` | create | The OpenCode plugin. It exports only the plugin function |
| `.opencode/chitragupta/gate.js` | create | Helpers the plugin uses: build the payload, run a hook, decide what to deliver |
| `tests/opencode/gate.test.mjs` | create | `node --test` unit tests for `gate.js` |
| `.claude/skills/*/SKILL.md`, `deep-research/reference.md` | modify | Harness-neutral wording; Agent Skills-conformant frontmatter |
| `chitragupta/init.py` | modify | `--agent claude\|codex\|opencode` (repeatable) |
| `chitragupta/doctor.py` | modify | Report launcher faults for every harness configured in the project |
| `pyproject.toml` | modify | Ship `.codex` and `.opencode` in the wheel and sdist |
| `AGENTS.md`, `docs/HOOKS.md`, `docs/PACKAGING.md`, `docs/FEATURES.md`, `docs/LOCAL-MODELS.md` | modify or create | Document what each harness enforces, as measured |

## 🔀 Order of work, and what runs in parallel

```text
Task 0 (measure Codex + OpenCode)  ─┐
Task 1 (render gate)  ──────────────┼─> Task 2-4 (patch payloads in the hooks) ─┬─> Task 5-6 (Codex)    ─┐
                                    │                                           ├─> Task 7 (OpenCode)    ─┼─> Task 9 (init --agent, doctor) ─> Task 10 (docs + recorded runs)
                                    └─> Task 8 (skills: neutral wording) ───────┴───────────────────────────┘
```

- **Task 0** can run at the same time as Task 1: it changes no code.
  It records real payloads that Tasks 3, 5 and 7 turn into test
  fixtures.
- **Once Tasks 2-4 land,** the Codex tasks (5-6), OpenCode (7) and
  skills (8) touch disjoint files and can proceed in parallel.
- **One PR per group:**
  1. Task 1
  2. Tasks 2-4
  3. Tasks 5-6
  4. Task 7
  5. Task 8
  6. Task 9
  7. Task 10

---

### Task 0: Measure Codex and OpenCode before writing code against them

The payload shapes below are from documentation and third-party write-ups
dated 2026. `docs/HOOKS.md`'s rule is that a hook contract is measured,
not assumed. This task records the real thing.

**Files:**

- Create: `tests/fixtures/harness_payloads/codex_apply_patch.json`
- Create: `tests/fixtures/harness_payloads/codex_apply_patch_multi.json`
- Create: `tests/fixtures/harness_payloads/opencode_write_args.json`
- Create: `tests/fixtures/harness_payloads/opencode_edit_args.json`
- Create: `tests/fixtures/harness_payloads/opencode_apply_patch_args.json`
- Create: `tests/fixtures/harness_payloads/README.md` (the date, the
  harness versions, and how each payload was captured)

**Interfaces:**

- Produces:
  - the fixture files Tasks 3, 5 and 7 load;
  - the answers to M1-M12 below, written into this plan's "Measured"
    section before Task 3 starts.

- [ ] **Step 1: Capture Codex payloads.**
  1. In a scratch copy of `docs/examples/sample-project/`, write
     `.codex/hooks.json` with a `PostToolUse` hook, matcher
     `apply_patch|Edit|Write|Bash`, running
     `python -c "import sys,pathlib; pathlib.Path('/tmp/codex-payload.json').write_text(sys.stdin.read())"`.
  2. Start Codex there. Ask it to create `content/drafts/probe.md`, then
     to edit it, then to edit two drafts in one change.
  3. Save each payload as a fixture. Before saving, replace any real
     absolute home path with `/project`.

- [ ] **Step 2: Answer the Codex questions.** Record each answer, with
  the evidence (payload excerpt or transcript line).
  - **M1.** Is `tool_input.command` a string, or a list such as
    `["apply_patch", "<patch>"]`?
  - **M2.** Does the payload carry `cwd`? Are patch paths relative to
    it?
  - **M3.** Does the hook's stdout `{"decision": "block", "reason": R}`
    reach the model, and does the model act on `R`? Use a hook that
    always blocks with a unique sentence, then ask the model to quote
    the sentence.
  - **M4.** Does `hookSpecificOutput.additionalContext` reach the
    model on `PostToolUse` and on `SessionStart`?
  - **M5.** What working directory and environment is a hook command
    run with? Is there a project-directory variable, the way Claude Code
    has `${CLAUDE_PROJECT_DIR}`? Does Codex accept the exec form
    (`command` plus `args`)?
  - **M6.** On first run in a fresh clone, do project hooks run without
    a trust step? If not, what does the user see, and what command
    trusts them?
  - **M7.** Does Codex read `.claude/skills/`, or can `config.toml`
    point it there? If not, it reads only `.agents/skills/`.
  - **M8.** Does Codex load a skill whose `description` is over 1,024
    characters, or one with a `tags:` key?

- [ ] **Step 3: Capture OpenCode payloads.**
  1. In the same scratch copy, write
     `.opencode/plugins/probe.js`:

     ```js
     import { appendFileSync } from "node:fs";
     export const Probe = async () => ({
       "tool.execute.before": async (input, output) => {
         appendFileSync("/tmp/opencode-probe.jsonl", JSON.stringify({ at: "before", input, args: output.args }) + "\n");
       },
       "tool.execute.after": async (input, output) => {
         appendFileSync("/tmp/opencode-probe.jsonl", JSON.stringify({ at: "after", input, output }) + "\n");
       },
     });
     ```

  2. Ask OpenCode to create, edit and patch drafts. Patch through a
     model that uses `apply_patch`, e.g. a GPT model.
  3. Save the `args` of each tool as a fixture.

- [ ] **Step 4: Answer the OpenCode questions.**
  - **M9.** Which tool names write files (`write`, `edit`,
    `apply_patch`, `multiedit`, others), and what are their argument
    keys? Expected: `filePath`, `content`, `oldString`, `newString`,
    `patchText`.
  - **M10.** Does a `throw` from `tool.execute.after` reach the model
    as an error it acts on? Does a `throw` from `tool.execute.before`
    stop the write? Test both with a unique sentence, as in M3.
  - **M11.** When a skill with the same `name` is in both
    `.claude/skills/` and `.agents/skills/`, does OpenCode load it once
    or twice?
  - **M12.** Does OpenCode read `AGENTS.md` natively? Does it load
    every exported function of a plugin file as a separate plugin?

- [ ] **Step 5: Record and commit.** Fill in the "Measured" section at
  the end of this plan, then commit the fixtures on the Task 1 branch
  or on their own branch:

  ```bash
  git add tests/fixtures/harness_payloads plans/812-harness-neutral-core.md
  git commit -m "Record real Codex and OpenCode tool payloads for the hook adapters"
  ```

**Decision rules that follow from Task 0:**

- **M3 (Codex blocking).** If the block reason does not reach the
  model, Codex cannot carry the mandatory check. Stop and raise that on
  #812 before Task 5.
- **M4 (Codex advisory output).** If `additionalContext` does not
  arrive, the style hook's advisory output does not reach Codex. That
  is acceptable, since only the gate must reach the model; record it in
  `docs/HOOKS.md` (Task 10). Do **not** add a second output field:
  HOOKS.md records that Claude Code delivers every field it
  recognises, so the payload would arrive twice.
- **M5 (launcher form).** This decides the Codex `command` string in
  Task 5.
- **M6 (trust).** This decides the wording of Task 6's warning.
- **M7 (skills path).** This decides whether Task 9 writes
  `.agents/skills/`.
- **M10 (OpenCode delivery).** This decides `deliver()` in Task 7:
  either throw, or rewrite the tool output.
- **M11 (duplicate skills).** If OpenCode loads duplicates, Task 9
  must not write `.agents/skills/` into a project that also has
  OpenCode configured. Codex and OpenCode together then need M7 to
  succeed.

---

### Task 1: `draft render` refuses an unknown key in every format

**Files:**

- Create: `chitragupta/render_output/_gate.py`
- Modify: `chitragupta/render_output/__init__.py`
  - the import block, L138-142:
    `from chitragupta.render_output._substitution import (... _draft_warnings ...)`
  - L249: `for prefix, warning in _draft_warnings(draft_text, input_path):`
- Modify: `chitragupta/render_output/_cli.py`, in `main`'s `except`
  chain, around L180-203.
- Test: `tests/test_render_output_gate.py` (new)
- Test: `tests/test_render_output_cli.py`, which gains a docx and a
  fragment case.

**Interfaces:**

- Consumes:

  ```python
  citation_gate.check_text(path: Path, text: str, known_citekeys: set[str]) -> GateResult
  citation_gate.extract_citekeys(text: str, *, latex: bool = False) -> list[tuple[int, str]]
  ledger.reading()
  ledger.known_citekeys(con) -> set[str]
  ledger.NoLedger
  _substitution._draft_warnings(draft_text: str, input_path: Path) -> list[tuple[str, str]]
  ```

- Produces:
  - `render_output._gate.UngatedDraft(ValueError)`. Its `str()` is the
    gate's report.
  - `render_output._gate.gated_warnings(draft_text, input_path)`, returning
    `list[tuple[str, str]]`. It raises `UngatedDraft` on an unknown key,
    and otherwise returns exactly what `_draft_warnings` returns.

**Why the call goes where it does:**

- **Placement.** It sits right after `draft_text` is read, before the
  md early return, so md, docx, pdf, tex, `--fragment` (natbib) and
  every format pandoc infers from the extension are covered by one
  statement.
- **Size.** It replaces the `_draft_warnings` call, so `render` stays
  at 24 statements. Moving `_draft_warnings` out of `__init__`'s
  import block and adding one `_gate` import keeps `__init__.py` at 250
  code lines.
- **No ledger.** A citation-free draft never opens the ledger, which
  preserves `tests/test_ledger_readers.py::TestTheGateStillRuns`'s
  no-ledger property.

- [ ] **Step 1: Write the failing tests** in
  `tests/test_render_output_gate.py`:

```python
"""`draft render` gates the draft before any format is produced (#812)."""

import pytest

from chitragupta import ledger
from chitragupta.render_output import _gate
from tests.conftest import content_draft, make_reference


def _known(cfg, *keys):
    con = ledger.connect()
    for key in keys:
        ledger.upsert_reference(con, make_reference(citekey=key))
    con.commit()
    con.close()


class TestGatedWarnings:
    def test_an_unknown_key_raises_naming_the_key_and_line(self, isolated_config):
        _known(isolated_config, "smith2024")
        draft = content_draft(isolated_config, "drafts/x.md")
        text = "Fine [@smith2024].\nBad [@not_a_real_citekey_2026].\n"
        with pytest.raises(_gate.UngatedDraft) as exc:
            _gate.gated_warnings(text, draft)
        assert "not_a_real_citekey_2026" in str(exc.value)
        assert ":2:" in str(exc.value)

    def test_a_known_key_returns_the_draft_warnings_unchanged(self, isolated_config):
        _known(isolated_config, "smith2024")
        draft = content_draft(isolated_config, "drafts/x.md")
        assert _gate.gated_warnings("Fine [@smith2024].\n", draft) == []

    def test_a_citation_free_draft_needs_no_ledger(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/x.md")
        assert _gate.gated_warnings("No citations here.\n", draft) == []
        assert not isolated_config.LEDGER_PATH.exists()

    def test_a_cited_key_with_no_ledger_is_refused(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/x.md")
        with pytest.raises(_gate.UngatedDraft) as exc:
            _gate.gated_warnings("Bad [@not_a_real_citekey_2026].\n", draft)
        assert "not_a_real_citekey_2026" in str(exc.value)
        assert not isolated_config.LEDGER_PATH.exists()

    def test_a_tex_draft_is_read_as_latex(self, isolated_config):
        _known(isolated_config, "smith2024")
        draft = content_draft(isolated_config, "drafts/x.tex")
        with pytest.raises(_gate.UngatedDraft):
            _gate.gated_warnings("\\citep{not_a_real_citekey_2026}\n", draft)

    def test_the_refusal_suggests_no_other_key(self, isolated_config):
        _known(isolated_config, "not_a_real_citekey_2025")
        draft = content_draft(isolated_config, "drafts/x.md")
        with pytest.raises(_gate.UngatedDraft) as exc:
            _gate.gated_warnings("Bad [@not_a_real_citekey_2026].\n", draft)
        assert "not_a_real_citekey_2025" not in str(exc.value)
```

  Add to `tests/test_render_output_cli.py::TestMainCli`, next to
  `test_a_citekey_missing_from_the_ledger_prints_and_returns_1` (L85):

```python
    @pytest.mark.parametrize("fmt", ["docx", "pdf", "tex"])
    @pytest.mark.parametrize("fragment", [False, True])
    def test_every_format_refuses_an_unknown_key_before_pandoc(
        self, isolated_config, ledger_con, monkeypatch, capsys, fmt, fragment
    ):
        draft = content_draft(isolated_config, "drafts/bad.md")
        draft.write_text("A claim [@not_a_real_citekey_2026].\n")
        ran = []
        monkeypatch.setattr(
            "chitragupta.render_output._run_pandoc", lambda *a, **k: ran.append(a)
        )
        argv = ["render_output.py", str(draft), "--format", fmt]
        monkeypatch.setattr(sys, "argv", argv + (["--fragment"] if fragment else []))
        assert render_output.main() == 1
        out = capsys.readouterr().out
        assert "[error]" in out and "not_a_real_citekey_2026" in out
        assert ran == []  # refused before pandoc, so it needs no pandoc to pass
```

- [ ] **Step 2: Run the tests and confirm they fail.**
  Run:

  ```bash
  pytest tests/test_render_output_gate.py tests/test_render_output_cli.py -q
  ```

  Expected: an `ImportError` for `_gate`, and the docx, pdf and tex
  cases fail with rc 0.

- [ ] **Step 3: Implement `chitragupta/render_output/_gate.py`.**

```python
"""The citation gate, run on the text `draft render` is about to render (#812).

`--format md` used to be the only format that refused a key missing from
the ledger, and only as a side effect of numbering the reference list;
docx, pdf and tex went to pandoc, whose citeproc prints a warning and
writes the document anyway. This runs the one gate on every draft before
any format is chosen, so no harness, hook or model can render around it.

It is the existing gate at a second point, not a new check: the same
`citation_gate.check_text`, the same report. There is deliberately no
flag to skip it (docs/HOOKS.md, "Deliberately not done").
"""

import contextlib
import io
from pathlib import Path

from chitragupta import citation_gate, ledger
from chitragupta.render_output._substitution import _draft_warnings


class UngatedDraft(ValueError):
    """The draft cites a key the ledger does not hold; str() is the gate's report."""


def gated_warnings(draft_text: str, input_path: Path) -> "list[tuple[str, str]]":
    """`_draft_warnings(draft_text, input_path)`, once the gate has passed the draft.

    A citation-free draft never opens the ledger, so a pre-sync teaching
    draft still renders with no ledger at all -- the property HOOKS.md
    measured for the gate itself. A cited key with no ledger fails closed,
    as the gate does.
    """
    latex = input_path.suffix.lower() == ".tex"
    if citation_gate.extract_citekeys(draft_text, latex=latex):
        result = citation_gate.check_text(input_path, draft_text, _known())
        if not result.ok:
            raise UngatedDraft(_report(input_path, result))
    return _draft_warnings(draft_text, input_path)


def _known() -> "set[str]":
    try:
        with ledger.reading() as con:
            return ledger.known_citekeys(con)
    except ledger.NoLedger:
        return set()


def _report(input_path: Path, result: "citation_gate.GateResult") -> str:
    # The gate's own wording, not a paraphrase, so a skill that already
    # reacts to a gate failure reads the same sentence here.
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        citation_gate.report(str(input_path), result)
    return "the citation gate refuses this draft, so it was not rendered.\n" + buffer.getvalue()
```

- [ ] **Step 4: Wire it into `render()`.**
  1. In the `_substitution` import block of
     `chitragupta/render_output/__init__.py`, delete the
     `_draft_warnings,` line.
  2. After that block, add
     `from chitragupta.render_output._gate import gated_warnings`.
  3. At L249, change the call to:

```python
    for prefix, warning in gated_warnings(draft_text, input_path):
```

  1. If any test reaches `render_output._draft_warnings` as an
     attribute, keep it re-exported by adding `_draft_warnings` to
     `_gate`'s import line and to `__init__`'s `_gate` import. Check
     with `grep -rn "render_output._draft_warnings" tests`.
  2. In `_cli.py`, add this branch next to the `references.MissingCitekey`
     one:

```python
    except UngatedDraft as exc:
        # The gate refused the draft (#812): reported like every other
        # render failure, `[error]` and the gate's own report naming each
        # key and line, so a skill reacts to it as it does to a gate run.
        print(f"[error] {exc}")
        return 1
```

  Import `UngatedDraft` lazily next to the existing lazy `render`
  import, since `_cli.main` imports `render` lazily to avoid a circular
  import.

- [ ] **Step 5: Run the tests and confirm they pass, and the limits
  hold.**
  Run:

  ```bash
  pytest tests/test_render_output_gate.py tests/test_render_output_cli.py \
    tests/test_render_output.py tests/test_ledger_readers.py tests/test_references.py -q
  python scripts/code_standards.py chitragupta/render_output
  pytest tests/test_code_standards_scan.py tests/test_annotation_scan.py -q
  ```

  Expected: PASS, with no C1 or C2 finding.
  `test_a_citekey_missing_from_the_ledger_prints_and_returns_1` still
  passes: the error now comes from the gate, and still has `[error]`
  and the key.

- [ ] **Step 6: Check against real pandoc,** if it is installed.
  Render a draft citing `not_a_real_citekey_2026` with
  `--format docx`. Expected: rc 1, `[error] the citation gate refuses
  ...`, and no `.docx` written.

- [ ] **Step 7: Update the docs in this PR.**
  - `docs/CLI.md`'s `draft render` entry: every format refuses a key
    the gate rejects.
  - `docs/ARCHITECTURE.md:202` ("Grounding is enforced, not
    requested"): the gate now also runs at render.
  - Bump MINOR.

- [ ] **Step 8: Run the full suite and commit.**
  Run: `pytest -q`, then `pylint --rcfile=.pylintrc chitragupta`, then
  `ruff check && ruff format --check`.

```bash
git add chitragupta/render_output tests/test_render_output_gate.py tests/test_render_output_cli.py docs pyproject.toml
git commit -m "Refuse to render a draft the citation gate rejects, in every format"
```

---

### Task 2: Read which files an `apply_patch` envelope writes

**Files:**

- Create: `.claude/hooks/patch_paths.py`
- Test: `tests/test_patch_paths.py`

**Interfaces:**

- Produces:
  - `patch_paths.BEGIN = "*** Begin Patch"`
  - `class patch_paths.UnreadablePatch(ValueError)`
  - `patch_paths.written_paths(text: str) -> list[str]`. It returns the
    paths the patch adds, updates or moves to, in order and
    deduplicated. It returns `[]` when `text` holds no envelope, or
    only deletions. It raises `UnreadablePatch` on an envelope that
    names no file operation at all.

The grammar is taken from OpenAI's `apply_patch` (V4A) format:

```text
Patch  := "*** Begin Patch" NL { FileOp } "*** End Patch" NL
FileOp := "*** Add File: " path
        | "*** Delete File: " path
        | "*** Update File: " path [ NL "*** Move to: " path ]
```

OpenCode's `apply_patch` tool uses the same envelope. The recorded
fixtures from Task 0 confirm both.

- [ ] **Step 1: Write the failing tests.**

```python
"""patch_paths: the files an apply_patch envelope writes (#812, #900)."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = REPO_ROOT / ".claude" / "hooks"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "harness_payloads"


def load(name):
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


patch_paths = load("patch_paths")

PATCH = """*** Begin Patch
*** Add File: content/drafts/new.md
+A claim.
*** Update File: content/drafts/old.md
*** Move to: content/drafts/renamed.md
@@
-before
+after
*** Delete File: content/drafts/gone.md
*** Update File: content/drafts/new.md
@@
+again
*** End Patch
"""


def test_every_written_path_in_order_once():
    assert patch_paths.written_paths(PATCH) == [
        "content/drafts/new.md",
        "content/drafts/old.md",
        "content/drafts/renamed.md",
    ]


def test_a_deletion_is_not_a_write():
    text = "*** Begin Patch\n*** Delete File: content/drafts/gone.md\n*** End Patch\n"
    assert patch_paths.written_paths(text) == []


def test_text_with_no_envelope_is_not_a_patch():
    assert patch_paths.written_paths("ls content/drafts") == []


def test_crlf_line_endings_do_not_leak_into_the_path():
    text = PATCH.replace("\n", "\r\n")
    assert patch_paths.written_paths(text)[0] == "content/drafts/new.md"


def test_an_envelope_with_no_file_operation_is_unreadable():
    with pytest.raises(patch_paths.UnreadablePatch):
        patch_paths.written_paths("*** Begin Patch\n*** Frobnicate: x\n*** End Patch\n")


def test_a_header_that_is_only_a_body_line_is_not_read():
    # A `+` line quoting a header is content, not an operation.
    text = "*** Begin Patch\n*** Add File: a.md\n+*** Add File: b.md\n*** End Patch\n"
    assert patch_paths.written_paths(text) == ["a.md"]


@pytest.mark.parametrize(
    "fixture", ["codex_apply_patch.json", "codex_apply_patch_multi.json"]
)
def test_the_recorded_codex_payloads_parse(fixture):
    payload = json.loads((FIXTURES / fixture).read_text())
    command = payload["tool_input"]["command"]
    text = command if isinstance(command, str) else "\n".join(command)
    assert all("content/drafts/" in p for p in patch_paths.written_paths(text))


def test_the_recorded_opencode_patch_parses():
    args = json.loads((FIXTURES / "opencode_apply_patch_args.json").read_text())
    assert patch_paths.written_paths(args["patchText"])
```

- [ ] **Step 2: Run the tests and confirm they fail.**
  Run: `pytest tests/test_patch_paths.py -q`
  Expected: an error saying `patch_paths.py` does not exist.

- [ ] **Step 3: Implement.**

```python
"""Which files does an apply_patch envelope write? -- read from its own headers.

Codex edits files through `apply_patch`, and OpenCode's `apply_patch`
tool takes the same envelope. Neither payload carries a `file_path`: the
targets are named inside the patch text, one header per file operation
(OpenAI's V4A grammar). This module reads those headers and nothing else
-- it never applies a patch, and never reads a hunk, because the gate
checks the file on disk after the write, not the diff.

`Delete File` is not a write: a deleted draft has no text to gate.
An envelope naming no operation at all is `UnreadablePatch`, so the
caller can fail closed when that envelope concerns a draft
(draft_target.py). Standard library only, like every hook helper here.
"""

from __future__ import annotations

import re

BEGIN = "*** Begin Patch"
_WRITE_HEADER = re.compile(r"^\*\*\* (?:Add File|Update File|Move to): (.+?)\r?$", re.MULTILINE)
_ANY_HEADER = re.compile(r"^\*\*\* (?:Add File|Update File|Move to|Delete File): ", re.MULTILINE)


class UnreadablePatch(ValueError):
    """A patch envelope that names no file operation this module can read."""


def written_paths(text: str) -> list[str]:
    """Every path the patch in `text` adds, updates or moves to, in order, once each."""
    if BEGIN not in text:
        return []
    if not _ANY_HEADER.search(text):
        raise UnreadablePatch("an apply_patch envelope with no file header")
    return list(dict.fromkeys(m.group(1).strip() for m in _WRITE_HEADER.finditer(text)))
```

- [ ] **Step 4: Run the tests and confirm they pass,** with full
  coverage of the module.
  Run: `pytest tests/test_patch_paths.py -q --cov=.claude/hooks --cov-branch --cov-report=term-missing`
  Expected: PASS, and `patch_paths.py` at 100%.

- [ ] **Step 5: Commit.**

```bash
git add .claude/hooks/patch_paths.py tests/test_patch_paths.py
git commit -m "Read the files an apply_patch envelope writes, for Codex and OpenCode hooks"
```

---

### Task 3: `draft_target` returns every draft in a payload

**Files:**

- Modify: `.claude/hooks/draft_target.py`
  - replace `from_stdin` and `_file_path` (L45-72);
  - `target` (L75-110) stays as it is;
  - the module docstring gains the patch rules.
- Test: `tests/test_draft_target.py`. Rename the `from_stdin` tests to
  `targets_from_stdin`; each single-path case now expects `[path]`
  instead of `path`, and `[]` instead of `None`.

**Interfaces:**

- Consumes: `patch_paths.written_paths(text) -> list[str]` and
  `patch_paths.UnreadablePatch`.
- Produces:
  - `draft_target.targets_from_stdin(stream, repo_root: Path | None = None) -> list[Path]`.
    It returns every resolved draft the payload writes, deduplicated
    and in order, or `[]`.
  - It raises `draft_target.UnreadablePatch` (a re-export of
    `patch_paths.UnreadablePatch`) only when the payload carries a
    patch envelope that cannot be read **and** that mentions
    `content/drafts/` or `content\drafts\`.
  - `draft_target.target(raw_path, repo_root) -> Path | None`, as
    before.

**Payload rules, all from Task 0's measurements:**

- **`file_path` payloads** (Claude Code; OpenCode through Task 7):
  `tool_input.file_path`, as today.
- **Patch payloads:**
  - Codex `apply_patch`: patch text in `tool_input.command`, as a
    string, or as a list whose parts are joined.
  - OpenCode `apply_patch`: Task 7 passes `patchText` in the same
    field.
- **Relative paths** resolve against the payload's `cwd` when there is
  one (M2), and against the repo root otherwise.
- **Malformed JSON, or a payload of the wrong shape,** still fails
  open (`[]`), in the three shapes HOOKS.md records.

- [ ] **Step 1: Write the failing tests** in `tests/test_draft_target.py`:

```python
PATCH = "*** Begin Patch\n*** Add File: content/drafts/a.md\n+x\n*** Update File: content/drafts/b.md\n@@\n+y\n*** End Patch\n"


def feed(payload):
    return io.StringIO(json.dumps(payload))


class TestPatchPayloads:
    def test_every_draft_in_a_patch_is_returned(self, tmp_path):
        (tmp_path / "content" / "drafts").mkdir(parents=True)
        got = draft_target.targets_from_stdin(
            feed({"tool_name": "apply_patch", "tool_input": {"command": PATCH}}), tmp_path
        )
        assert [p.name for p in got] == ["a.md", "b.md"]

    def test_a_list_shaped_command_is_joined(self, tmp_path):
        (tmp_path / "content" / "drafts").mkdir(parents=True)
        got = draft_target.targets_from_stdin(
            feed({"tool_input": {"command": ["apply_patch", PATCH]}}), tmp_path
        )
        assert len(got) == 2

    def test_a_relative_path_resolves_against_the_payload_cwd(self, tmp_path):
        (tmp_path / "content" / "drafts").mkdir(parents=True)
        (tmp_path / "sub").mkdir()
        patch = "*** Begin Patch\n*** Add File: ../content/drafts/a.md\n+x\n*** End Patch\n"
        got = draft_target.targets_from_stdin(
            feed({"cwd": str(tmp_path / "sub"), "tool_input": {"command": patch}}), tmp_path
        )
        assert got == [(tmp_path / "content" / "drafts" / "a.md").resolve()]

    def test_non_draft_paths_in_a_patch_are_dropped(self, tmp_path):
        (tmp_path / "content" / "drafts").mkdir(parents=True)
        patch = "*** Begin Patch\n*** Add File: README.md\n+x\n*** End Patch\n"
        assert draft_target.targets_from_stdin(feed({"tool_input": {"command": patch}}), tmp_path) == []

    @pytest.mark.parametrize("where", ["content/drafts/x.md", "content\\drafts\\x.md"])
    def test_an_unreadable_patch_that_mentions_drafts_fails_closed(self, tmp_path, where):
        patch = f"*** Begin Patch\n*** Frobnicate: {where}\n*** End Patch\n"
        with pytest.raises(draft_target.UnreadablePatch):
            draft_target.targets_from_stdin(feed({"tool_input": {"command": patch}}), tmp_path)

    def test_an_unreadable_patch_elsewhere_fails_open(self, tmp_path):
        patch = "*** Begin Patch\n*** Frobnicate: src/x.py\n*** End Patch\n"
        assert draft_target.targets_from_stdin(feed({"tool_input": {"command": patch}}), tmp_path) == []

    def test_a_shell_command_with_no_envelope_is_not_our_business(self, tmp_path):
        payload = {"tool_input": {"command": "echo x > content/drafts/a.md"}}
        assert draft_target.targets_from_stdin(feed(payload), tmp_path) == []

    def test_the_recorded_codex_payload_targets_its_drafts(self, tmp_path):
        payload = json.loads((FIXTURES / "codex_apply_patch_multi.json").read_text())
        payload["cwd"] = str(tmp_path)
        (tmp_path / "content" / "drafts").mkdir(parents=True)
        assert len(draft_target.targets_from_stdin(feed(payload), tmp_path)) >= 2
```

  Keep the existing malformed-stdin cases, now expecting `[]`. Add
  `FIXTURES = REPO_ROOT / "tests" / "fixtures" / "harness_payloads"`
  to the test module's constants.

- [ ] **Step 2: Run the tests and confirm they fail.**
  Run: `pytest tests/test_draft_target.py -q`
  Expected: an `AttributeError` for `targets_from_stdin`.

- [ ] **Step 3: Implement.** Replace `from_stdin` and `_file_path`
  with:

```python
import patch_paths
from patch_paths import UnreadablePatch  # re-exported for the gate hook

_DRAFT_MARKERS = ("content/drafts/", "content\\drafts\\")


def targets_from_stdin(stream, repo_root: Path | None = None) -> list[Path]:
    """Every draft this PostToolUse payload wrote, in order, once each; [] otherwise.

    `[]` covers every "not our business" case, as `None` did when a
    payload could name only one file. The one exception is an
    apply_patch envelope that mentions a draft but whose headers cannot
    be read: that raises UnreadablePatch, because failing open there is
    the silently inert gate docs/HOOKS.md exists to prevent.
    """
    payload = _payload(stream)
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []  # missing, null, or the wrong shape -- same as "no file named"
    base = payload.get("cwd")
    found: list[Path] = []
    for raw in _raw_paths(tool_input):
        if isinstance(base, str) and base and not Path(raw).is_absolute():
            raw = str(Path(base) / raw)  # Codex patch paths are relative to its cwd
        path = target(raw, repo_root)
        if path is not None and path not in found:
            found.append(path)
    return found


def _payload(stream) -> dict:
    try:
        payload = json.load(stream)
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return {}  # can't identify a target file from this -- fail open, not loud
    return payload if isinstance(payload, dict) else {}


def _raw_paths(tool_input: dict) -> list[str]:
    raw = tool_input.get("file_path")
    if isinstance(raw, str) and raw:
        return [raw]
    text = _patch_text(tool_input.get("command"))
    try:
        return patch_paths.written_paths(text)
    except UnreadablePatch:
        if any(marker in text for marker in _DRAFT_MARKERS):
            raise
        return []


def _patch_text(command) -> str:
    if isinstance(command, str):
        return command
    if isinstance(command, list):
        return "\n".join(part for part in command if isinstance(part, str))
    return ""
```

- [ ] **Step 4: Update the module docstring.**
  - Add a bullet on patch payloads and `cwd`.
  - Change "Malformed stdin fails open in all three shapes" to
    exempt an unreadable patch that mentions a draft, and say why.

- [ ] **Step 5: Run the tests and confirm they pass.**
  Run: `pytest tests/test_draft_target.py -q --cov=.claude/hooks --cov-branch --cov-report=term-missing`
  Expected: PASS. Every other test in the suite that called
  `from_stdin` now fails, and is fixed in Task 4.

- [ ] **Step 6: Commit,** on the same branch as Task 4. The tree is not
  green until Task 4 is done.

```bash
git add .claude/hooks/draft_target.py tests/test_draft_target.py
git commit -m "Find every draft in a hook payload, including apply_patch envelopes"
```

---

### Task 4: The gate and style hooks check every draft in a payload

**Files:**

- Modify: `.claude/hooks/citation_gate_hook.py`, `main` (L127-197)
- Modify: `.claude/hooks/style_check_hook.py`, `main` (L56-72)
- Test: `tests/test_hook_modules.py`, `tests/test_citation_gate_hook.py`,
  `tests/test_style_check_hook.py`

**Interfaces:**

- Consumes: `draft_target.targets_from_stdin` and
  `draft_target.UnreadablePatch`.
- Produces:
  - **Gate hook:** one gate subprocess over all targeted drafts:
    `[sys.executable, "-m", "chitragupta.draft", "gate", *drafts]`,
    run with `env[GATE_CALLER_ENV] = "hook"`.
  - **`GATE_CALLER_ENV = "CHITRAGUPTA_GATE_CALLER"`**, a module
    constant that Task 6 reads.
  - **Style hook:** one `draft style --json` subprocess over all
    drafts. `draft style` already takes several paths; check with
    `python -m chitragupta.draft style --help`.

- [ ] **Step 1: Write the failing tests** in
  `tests/test_hook_modules.py::TestCitationGateHookModule`:

```python
    def test_every_draft_in_a_patch_is_gated_in_one_call(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        drafts = root / "content" / "drafts"
        (drafts / "a.md").write_text("x\n")
        (drafts / "b.md").write_text("y\n")
        calls = []

        def run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return completed(0)

        monkeypatch.setattr(hook.subprocess, "run", run)
        patch = "*** Begin Patch\n*** Update File: content/drafts/a.md\n*** Update File: content/drafts/b.md\n*** End Patch\n"
        self.feed(monkeypatch, {"tool_name": "apply_patch", "tool_input": {"command": patch}, "cwd": str(root)})
        assert hook.main() == 0
        cmd, kwargs = calls[0]
        assert cmd[-2:] == [str(drafts / "a.md"), str(drafts / "b.md")]
        assert kwargs["env"][hook.GATE_CALLER_ENV] == "hook"
        assert capsys.readouterr().out == ""

    def test_an_unreadable_patch_on_a_draft_blocks(self, rooted, monkeypatch, capsys):
        hook, _ = rooted
        patch = "*** Begin Patch\n*** Frobnicate: content/drafts/a.md\n*** End Patch\n"
        self.feed(monkeypatch, {"tool_input": {"command": patch}})
        assert hook.main() == 0
        response = emitted(capsys)
        assert response["decision"] == "block"
        assert "could not be read" in response["reason"]

    def test_the_line_bound_is_the_sum_over_every_draft(self, rooted, monkeypatch, capsys):
        hook, root = rooted
        drafts = root / "content" / "drafts"
        half = "x\n" * (hook.MAX_GATED_LINES // 2 + 1)
        (drafts / "a.md").write_text(half)
        (drafts / "b.md").write_text(half)
        patch = "*** Begin Patch\n*** Update File: content/drafts/a.md\n*** Update File: content/drafts/b.md\n*** End Patch\n"
        self.feed(monkeypatch, {"tool_input": {"command": patch}, "cwd": str(root)})
        hook.main()
        assert "too large to gate" in emitted(capsys)["reason"]
```

  Add a subprocess test to `tests/test_citation_gate_hook.py`:

- use a `HookRepo` that also copies `patch_paths.py`;
- write one draft citing `not_a_real_citekey_2026` and one clean
    draft;
- feed a Codex-shaped payload built from
    `codex_apply_patch_multi.json`, with its paths pointed at the two
    drafts;
- assert `decision == "block"`, and that the reason names the fake
    key.

  Update `HookRepo` (L100-146): its copy loop becomes
  `("draft_target.py", "safe_path.py", "patch_paths.py")`.

- [ ] **Step 2: Run the tests and confirm they fail.**
  Run: `pytest tests/test_hook_modules.py tests/test_citation_gate_hook.py -q`

- [ ] **Step 3: Implement the gate hook.**
  1. Add `GATE_CALLER_ENV = "CHITRAGUPTA_GATE_CALLER"`.
  2. Replace the head of `main`:

```python
def main() -> int:
    try:
        drafts = draft_target.targets_from_stdin(sys.stdin)
    except draft_target.UnreadablePatch:
        _block(
            "This patch changes something under content/drafts/, but its file "
            "headers could not be read, so no draft was checked. It is blocked "
            "rather than let through. Run `python -m chitragupta.draft gate` on "
            "each draft it changed."
        )
        return 0
    if not drafts:
        return 0  # not a genre-skill draft -- nothing to gate
```

  1. Replace the line bound with the total over all drafts:
     `lines = sum(n for n in map(_line_count, drafts) if n is not None)`.
  2. Build the env as
     `env = {**safe_path.child_env(draft_target.REPO_ROOT), GATE_CALLER_ENV: "hook"}`.
  3. The subprocess command becomes
     `[sys.executable, "-m", "chitragupta.draft", "gate", *map(str, drafts)]`.
  4. In the two failure reasons, change "this draft" and "this file"
     to "the draft(s) this write changed".
  5. `main` must stay at or under 25 statements. If it does not, move
     the line-bound block into `_too_large(drafts) -> bool`, which
     blocks and returns True.

- [ ] **Step 4: Implement the style hook.**

```python
def main() -> int:
    try:
        drafts = [d for d in draft_target.targets_from_stdin(sys.stdin) if d.is_file()]
    except draft_target.UnreadablePatch:
        return 0  # the gate blocks this one; an advisory hook stays silent
    if not drafts:
        return 0  # not a draft, or gone between the write and this check
    payload = _findings(drafts)
    ...
```

  `_findings` takes `drafts: list` and runs
  `draft style --json *drafts`. The `report["drafts"]` parsing already
  loops over drafts.

- [ ] **Step 5: Run the hook tests, then the whole suite.**
  Run:

  ```bash
  pytest tests/test_hook_modules.py tests/test_citation_gate_hook.py \
    tests/test_style_check_hook.py tests/test_draft_target.py tests/test_patch_paths.py -q
  pytest -q --cov --cov-branch
  ```

  Expected: PASS at 100% coverage. Also fix the stale docstring at
  `tests/test_citation_gate_hook.py:26-30`, which says the hook
  "doesn't pass env=".

- [ ] **Step 6: Check Claude Code still works.** Run HOOKS.md's trials
  2 and 3 on Claude Code: `Edit` and `Write` of a draft citing
  `not_a_real_citekey_2026`. Expected: the block arrives, as before.

- [ ] **Step 7: Commit, bump MINOR, and open the PR.**

```bash
git add .claude/hooks tests pyproject.toml
git commit -m "Gate every draft a write changes, including multi-file patches"
```

---

### Task 5: Codex runs the hooks

**Files:**

- Create: `.codex/hooks.json`
- Create: `chitragupta/launcher_configs.py`
- Modify: `.claude/hooks/session_start_hook.py`, `launcher_faults`
  (L77-87)
- Test: `tests/test_launcher_configs.py` (new)
- Test: `tests/test_settings_launchers.py`, extended to `.codex/hooks.json`

**Interfaces:**

- Consumes:
  - `hook_launchers.faults(settings_path: Path) -> list[str]`,
    unchanged. It already reads any `{"hooks": {event: [entry]}}`
    document, and parses both the exec form and the string form of
    `command` (`_program_name`, L178).
- Produces:
  - `launcher_configs.CONFIGS: tuple[str, ...] = (".claude/settings.json", ".codex/hooks.json")`
  - `launcher_configs.present(root: Path) -> list[Path]`: the configs
    that exist under `root`.
  - `launcher_configs.faults(root: Path) -> list[str]`: every present
    config's faults, each prefixed with the config's relative path,
    deduplicated.

**`.codex/hooks.json`.** The `command` form is fixed by M5.

- **Default**, if M5 shows Codex runs hooks with the working directory
  at the project root and accepts a command string:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "apply_patch|Edit|Write",
        "hooks": [
          {"type": "command", "command": "python .claude/hooks/citation_gate_hook.py", "timeout": 30},
          {"type": "command", "command": "python .claude/hooks/style_check_hook.py", "timeout": 30}
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "startup|clear",
        "hooks": [
          {"type": "command", "command": "python .claude/hooks/session_start_hook.py", "timeout": 30}
        ]
      }
    ]
  }
}
```

- **If M5 finds a project-directory variable,** use it braced, exactly
  as `.claude/settings.json` uses `${CLAUDE_PROJECT_DIR}`.
- **If M5 shows the working directory can be a subfolder and there is
  no variable,** Task 9's `init` writes the absolute path, and the
  checked-in file keeps the relative form with a note in
  `docs/HOOKS.md`.
- **Matcher.** Add `Bash` to the matcher only if Task 0 shows Codex
  still issues `apply_patch` through the shell tool.
  `draft_target` already handles a patch envelope in any `command`.

- [ ] **Step 1: Write the failing tests** in
  `tests/test_launcher_configs.py`:

```python
"""launcher_configs: dead-launcher faults across every harness's config (#812)."""

import json

from chitragupta import launcher_configs


def write(root, rel, program):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    hooks = {"PostToolUse": [{"hooks": [{"type": "command", "command": f"{program} x.py"}]}]}
    path.write_text(json.dumps({"hooks": hooks}))


def test_only_configs_that_exist_are_read(tmp_path):
    write(tmp_path, ".codex/hooks.json", "python")
    assert launcher_configs.present(tmp_path) == [tmp_path / ".codex" / "hooks.json"]


def test_a_dead_codex_launcher_is_named_with_its_config(tmp_path):
    write(tmp_path, ".codex/hooks.json", "no-such-interpreter-812")
    faults = launcher_configs.faults(tmp_path)
    assert len(faults) == 1
    assert faults[0].startswith(".codex/hooks.json: ")
    assert "no-such-interpreter-812" in faults[0]


def test_no_configs_means_no_faults(tmp_path):
    assert launcher_configs.faults(tmp_path) == []
```

  In `tests/test_settings_launchers.py`, parametrize
  `registered_hooks()` over both `.claude/settings.json` and
  `.codex/hooks.json`. For every registered script, assert that it
  exists and that its interpreter is `python`. Also assert that
  `.codex/hooks.json` registers `citation_gate_hook.py` on
  `PostToolUse` with a matcher that includes `apply_patch`.

- [ ] **Step 2: Run the tests and confirm they fail.**
  Run: `pytest tests/test_launcher_configs.py tests/test_settings_launchers.py -q`

- [ ] **Step 3: Implement `chitragupta/launcher_configs.py`.**

```python
"""Which launcher configs a project carries, one per harness (#812).

`hook_launchers.faults` reads one `{"hooks": {...}}` document -- the shape
Claude Code's settings.json and Codex's hooks.json share -- and says what
would stop a hook from starting. This is the list of those documents, so
the preflight, the gate and `doctor` report a dead launcher on every
harness a project is set up for, not only on Claude Code. OpenCode's
launcher is a plugin, not a config; its own failure to start the gate
refuses the write (.opencode/chitragupta/gate.js).

Standard library only, and it reads a launcher config, never a payload:
the one layer-1 exception docs/HOOKS.md names, kept in one place.
"""

from pathlib import Path

from chitragupta import hook_launchers

CONFIGS = (".claude/settings.json", ".codex/hooks.json")


def present(root: Path) -> list[Path]:
    return [root / rel for rel in CONFIGS if (root / rel).is_file()]


def faults(root: Path) -> list[str]:
    found = [
        f"{path.relative_to(root).as_posix()}: {fault}"
        for path in present(root)
        for fault in hook_launchers.faults(path)
    ]
    return list(dict.fromkeys(found))
```

  `session_start_hook.launcher_faults()` becomes
  `return launcher_configs.faults(REPO)`, with
  `from chitragupta import hook_launchers, launcher_configs` at L71-72.
  Update the preflight tests that pinned the old unprefixed message.

- [ ] **Step 4: Write `.codex/hooks.json`** as decided above.

- [ ] **Step 5: Run the tests and confirm they pass.**
  Run:

  ```bash
  pytest tests/test_launcher_configs.py tests/test_settings_launchers.py \
    tests/test_session_start_hook.py tests/test_hook_modules.py -q
  ```

- [ ] **Step 6: Measure on a real Codex session** in a scratch copy of
  the sample project, and record each trial in `docs/HOOKS.md`'s table
  in Task 10.
  - `apply_patch` adds a draft citing `not_a_real_citekey_2026`.
    Expected: blocked, the reason names the key, and the model fixes
    it.
  - `apply_patch` updates two drafts, one with a bad key. Expected:
    blocked, naming that draft.
  - A clean draft. Expected: no block.
  - The style hook's advisory output arrives, per M4.
  - A dead launcher (`command` set to `pythonx ...`). Expected: the
    preflight or `draft gate` reports
    `.codex/hooks.json: pythonx ...`.

- [ ] **Step 7: Commit,** on the same branch as Task 6.

```bash
git add .codex chitragupta/launcher_configs.py .claude/hooks/session_start_hook.py tests
git commit -m "Run the citation gate and style hooks on Codex's apply_patch"
```

---

### Task 6: Warn when a draft changed with no hook firing

This closes a gap Codex introduces. Codex skips project hooks until the
user trusts them (M6), and records that trust against the hook's hash.
An untrusted hook looks exactly like a gate that passed. The skill's own
`draft gate` run happens after every drafting session, so it is the
place that notices. This also catches a draft written through the
shell, on any harness.

**Files:**

- Create: `chitragupta/gate_liveness.py`
- Modify: `chitragupta/citation_gate.py`, `run` (L400-454). Replace
  the `hook_launchers.faults()` warning loop at L409-415 with one call.
- Test: `tests/test_gate_liveness.py` (new)
- Test: `tests/test_citation_gate.py::TestDeadLauncherWarning` (L632),
  which is re-pointed at `gate_liveness`.

**Interfaces:**

- Consumes:
  - `launcher_configs.present(root)` and `launcher_configs.faults(root)`
    from Task 5;
  - `GATE_CALLER_ENV` (`"CHITRAGUPTA_GATE_CALLER"`), which the gate
    hook sets from Task 4;
  - `config.CONTENT_DIR`.
- Produces: `gate_liveness.observe(paths: list[str]) -> None`.
  - **Called from a hook** (the env variable is `"hook"`): it records
    `{relative path: sha256 of content}` for each path in
    `content/.gate-seen.json`, whatever the verdict.
  - **Called by hand or by a skill:** it prints launcher faults, and
    for each path whose current hash is not the recorded one, a warning
    to stderr. This happens only when the project has a launcher config
    or `.opencode/plugins/chitragupta-gate.js`.

**This is detection, never enforcement.**

- It never changes the gate's exit code.
- A spoofed env variable or a hand-edited `.gate-seen.json` hides the
  warning, and nothing more.
- The project root is `config.CONTENT_DIR.parent`, not the working
  directory, so tests whose `CONTENT_DIR` is a temporary directory see
  no launcher and print no warning.

- [ ] **Step 1: Write the failing tests.**

```python
"""gate_liveness: notice a draft that changed with no hook gating it (#812)."""

import json

from chitragupta import gate_liveness
from tests.conftest import content_draft


def configure(root):
    (root / ".codex").mkdir()
    (root / ".codex" / "hooks.json").write_text(json.dumps({"hooks": {}}))


def test_a_hook_call_records_the_draft(isolated_config, monkeypatch):
    draft = content_draft(isolated_config, "drafts/a.md")
    draft.write_text("x\n")
    monkeypatch.setenv("CHITRAGUPTA_GATE_CALLER", "hook")
    gate_liveness.observe([str(draft)])
    seen = json.loads((isolated_config.CONTENT_DIR / ".gate-seen.json").read_text())
    assert list(seen) == ["drafts/a.md"]


def test_a_draft_no_hook_saw_warns(isolated_config, monkeypatch, capsys):
    configure(isolated_config.CONTENT_DIR.parent)
    monkeypatch.delenv("CHITRAGUPTA_GATE_CALLER", raising=False)
    draft = content_draft(isolated_config, "drafts/a.md")
    draft.write_text("x\n")
    gate_liveness.observe([str(draft)])
    err = capsys.readouterr().err
    assert "no automatic gate has checked" in err and "drafts/a.md" in err


def test_a_draft_the_hook_saw_is_quiet(isolated_config, monkeypatch, capsys):
    configure(isolated_config.CONTENT_DIR.parent)
    draft = content_draft(isolated_config, "drafts/a.md")
    draft.write_text("x\n")
    monkeypatch.setenv("CHITRAGUPTA_GATE_CALLER", "hook")
    gate_liveness.observe([str(draft)])
    monkeypatch.delenv("CHITRAGUPTA_GATE_CALLER")
    gate_liveness.observe([str(draft)])
    assert capsys.readouterr().err == ""


def test_an_edit_after_the_hook_warns_again(isolated_config, monkeypatch, capsys):
    configure(isolated_config.CONTENT_DIR.parent)
    draft = content_draft(isolated_config, "drafts/a.md")
    draft.write_text("x\n")
    monkeypatch.setenv("CHITRAGUPTA_GATE_CALLER", "hook")
    gate_liveness.observe([str(draft)])
    draft.write_text("changed through a shell\n")
    monkeypatch.delenv("CHITRAGUPTA_GATE_CALLER")
    gate_liveness.observe([str(draft)])
    assert "no automatic gate has checked" in capsys.readouterr().err


def test_a_project_with_no_harness_configured_is_quiet(isolated_config, capsys):
    draft = content_draft(isolated_config, "drafts/a.md")
    draft.write_text("x\n")
    gate_liveness.observe([str(draft)])
    assert capsys.readouterr().err == ""


def test_a_corrupt_record_is_treated_as_empty(isolated_config, capsys):
    configure(isolated_config.CONTENT_DIR.parent)
    draft = content_draft(isolated_config, "drafts/a.md")  # creates CONTENT_DIR too
    draft.write_text("x\n")
    (isolated_config.CONTENT_DIR / ".gate-seen.json").write_text("{not json")
    gate_liveness.observe([str(draft)])
    assert "no automatic gate has checked" in capsys.readouterr().err
```

- [ ] **Step 2: Run the tests and confirm they fail.**
  Run: `pytest tests/test_gate_liveness.py -q`

- [ ] **Step 3: Implement `chitragupta/gate_liveness.py`.**

```python
"""Did a hook gate this draft? -- noticed by the gate a skill runs by hand (#812).

A PostToolUse hook that never fires looks exactly like one that passed.
Codex makes that the default state of a fresh project: project hooks
are skipped until the user trusts them, and trust is recorded against a
hash, so editing a hook makes it untrusted again. A draft written through
a shell command is never seen by any harness's hook either.

So the gate hook records what it gated (`CHITRAGUPTA_GATE_CALLER=hook`,
set by .claude/hooks/citation_gate_hook.py), and the gate a skill runs
before presenting compares. A draft whose current text no hook has seen
gets a warning naming the likely cause. This is detection, never
enforcement: it never changes the gate's verdict, and a spoofed record
hides only this warning.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

from chitragupta import config, launcher_configs

GATE_CALLER_ENV = "CHITRAGUPTA_GATE_CALLER"
PLUGIN = ".opencode/plugins/chitragupta-gate.js"
UNSEEN = (
    "WARNING: no automatic gate has checked {path} since it last changed. "
    "Either it was written outside the agent's file tools (a shell command), "
    "or the harness is not running this project's hooks -- on Codex, project "
    "hooks run only after you trust them (see docs/HOOKS.md). This run checked it."
)


def observe(paths: list[str]) -> None:
    root = config.CONTENT_DIR.parent
    record_path = config.CONTENT_DIR / ".gate-seen.json"
    seen = _read(record_path)
    current = {_key(p): _digest(p) for p in paths}
    if os.environ.get(GATE_CALLER_ENV) == "hook":
        record_path.write_text(json.dumps({**seen, **current}, indent=0, sort_keys=True))
        return
    if not (launcher_configs.present(root) or (root / PLUGIN).is_file()):
        return  # no harness configured here, so no hook was ever expected to fire
    for fault in launcher_configs.faults(root):
        print(f"WARNING: {fault} See docs/HOOKS.md.", file=sys.stderr)
    for key, digest in current.items():
        if digest is not None and seen.get(key) != digest:
            print(UNSEEN.format(path=key), file=sys.stderr)


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}  # missing or corrupt: as if no hook had ever fired
    return data if isinstance(data, dict) else {}


def _key(path: str) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(config.CONTENT_DIR.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _digest(path: str) -> "str | None":
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None  # the gate itself reports an unreadable draft
```

  `GATE_CALLER_ENV` is defined twice: here, and in the hook, which is
  layer 2 and must not import layer 1 at load time. Add a test that
  asserts the two are equal.

- [ ] **Step 4: Wire it into `citation_gate.run`.** Replace the
  `for fault in hook_launchers.faults(): print(...)` block (L409-415)
  with `gate_liveness.observe(paths)`, and change the `hook_launchers`
  import to `gate_liveness`. Code lines go down, from 247.
  - Update `TestDeadLauncherWarning`. It monkeypatches
    `citation_gate.hook_launchers.faults` at L658 and L672; it should
    now monkeypatch `gate_liveness.launcher_configs.faults`, with a
    `.claude/settings.json` in the project root.
  - The old message said "This gate ran because something invoked it,
    but it is no longer running automatically after every write". Move
    that clause into the fault line here, so a person still reads why a
    dead launcher matters.

- [ ] **Step 5: Add `content/.gate-seen.json` to `.gitignore`.**
  `content/` is ignored already; check with
  `git check-ignore content/.gate-seen.json`. Then confirm that
  `review`, `dossier` and every other content scan skip dotfiles:
  `grep -rn "CONTENT_DIR.*glob\|rglob" chitragupta`.

- [ ] **Step 6: Run the tests and confirm they pass.**
  Run:

  ```bash
  pytest tests/test_gate_liveness.py tests/test_citation_gate.py \
    tests/test_ledger_readers.py tests/test_feature_workflows.py -q
  pytest -q --cov --cov-branch
  ```

  Expected: PASS at 100%. Every gate test uses `isolated_config`, so
  its project root holds no launcher config and prints no warning. If a
  test does see one, give it an `isolated_config`; do not relax the
  check.

- [ ] **Step 7: Measure M6 on Codex.**
  1. In an untrusted fresh copy, have the model write a draft.
  2. Run `python -m chitragupta.draft gate` on it. Expected: the
     `UNSEEN` warning.
  3. Trust the hooks and write again. Expected: quiet.

  Record the result in HOOKS.md (Task 10). Adjust the Codex clause of
  `UNSEEN` to the exact trust command M6 found.

- [ ] **Step 8: Commit, bump MINOR, and open the PR for Tasks 5-6.**

```bash
git add chitragupta/gate_liveness.py chitragupta/citation_gate.py tests pyproject.toml
git commit -m "Warn when a draft changed without any hook gating it"
```

---

### Task 7: OpenCode runs the same hooks through a plugin (#900)

**Files:**

- Create: `.opencode/plugins/chitragupta-gate.js`. It exports only the
  plugin, since M12 may show OpenCode loads every export as a plugin.
- Create: `.opencode/chitragupta/gate.js` (the helpers)
- Create: `tests/opencode/gate.test.mjs`
- Create: `tests/test_opencode_plugin.py`. It runs
  `node --test tests/opencode`, skipped when `node` is absent, plus one
  end-to-end case through the real Python hook.
- Modify: `.github/workflows/ci.yml`. Add a `node --test tests/opencode`
  step to the existing Node 20 job (L532-557).

**Interfaces:**

- Consumes:
  - the hook contract from Task 4: a JSON payload on stdin, and one
    JSON document or nothing on stdout;
  - `.claude/hooks/citation_gate_hook.py` and `style_check_hook.py`.
- Produces, from `gate.js`:
  - `WRITERS: Set<string>`: the tool names from M9.
  - `payloadFor(tool, args, root) -> object`. For `apply_patch` it
    returns `{tool_name, tool_input: {command: patchText}, cwd: root}`.
    For every other tool it returns
    `{tool_name, tool_input: {file_path: filePath}, cwd: root}`.
  - `touchesDrafts(payload) -> boolean`
  - `runHook(script, payload, spawn = spawnSync) -> {failed: true, detail} | object`
  - `deliver(output, message)`: throws, or rewrites `output.output`,
    as M10 decides.

**Why this shape:**

- **The plugin holds no gate logic.** It turns OpenCode's tool
  arguments into the payload shape the hooks already read, and passes
  the payload to them. So "which writes are drafts", the line bound,
  the timeout, the fail-closed rules and the `safe_path` import rule
  are the same code on all three harnesses.
- **`after`, not `before`.**
  - The hooks gate the file on disk.
  - OpenCode's `edit` does its own fuzzy matching of `oldString`, so
    reproducing the post-edit text in the plugin would be a second
    implementation that could drift.
  - `before` only remembers the arguments by `callID`, because M10 may
    show `after` does not receive them.
- **Fail closed only for drafts.** If `python` cannot run, a write
  whose payload mentions `content/drafts/` is refused. Any other write
  is left alone, just as a dead launcher on Claude Code blocks nothing
  that isn't a draft.

- [ ] **Step 1: Write the failing `node --test` tests** in
  `tests/opencode/gate.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { payloadFor, touchesDrafts, runHook, WRITERS } from "../../.opencode/chitragupta/gate.js";

test("write and edit pass the file path, as Claude Code's hooks read it", () => {
  const p = payloadFor("edit", { filePath: "/p/content/drafts/a.md", oldString: "x", newString: "y" }, "/p");
  assert.deepEqual(p, { tool_name: "edit", tool_input: { file_path: "/p/content/drafts/a.md" }, cwd: "/p" });
});

test("apply_patch passes the patch text where Codex's hooks read it", () => {
  const p = payloadFor("apply_patch", { patchText: "*** Begin Patch\n*** End Patch\n" }, "/p");
  assert.equal(p.tool_input.command, "*** Begin Patch\n*** End Patch\n");
});

test("only writes that mention a draft count as touching drafts", () => {
  assert.equal(touchesDrafts(payloadFor("write", { filePath: "content/drafts/a.md" }, "/p")), true);
  assert.equal(touchesDrafts(payloadFor("write", { filePath: "content\\drafts\\a.md" }, "/p")), true);
  assert.equal(touchesDrafts(payloadFor("write", { filePath: "README.md" }, "/p")), false);
});

test("a hook that cannot start is a failure, not a pass", () => {
  const spawn = () => ({ error: new Error("ENOENT"), status: null, stdout: "", stderr: "" });
  assert.equal(runHook("citation_gate_hook.py", {}, spawn).failed, true);
});

test("a hook that prints nothing passes", () => {
  const spawn = () => ({ status: 0, stdout: "", stderr: "" });
  assert.deepEqual(runHook("citation_gate_hook.py", {}, spawn), {});
});

test("a hook that prints non-JSON is a failure", () => {
  const spawn = () => ({ status: 0, stdout: "Traceback ...", stderr: "" });
  assert.equal(runHook("citation_gate_hook.py", {}, spawn).failed, true);
});

test("the recorded OpenCode tool names are all watched", () => {
  for (const tool of ["write", "edit", "apply_patch"]) assert.ok(WRITERS.has(tool));
});
```

- [ ] **Step 2: Run the tests and confirm they fail.**
  Run: `node --test tests/opencode`
  Expected: a module-not-found error.

- [ ] **Step 3: Implement `.opencode/chitragupta/gate.js`.**

```js
// The OpenCode side of chitragupta's hooks (#900): turn a file tool's
// arguments into the payload .claude/hooks/*.py already read, run the
// hook, and hand its verdict back. No citekey logic lives here -- which
// writes are drafts, the size bound, the timeout and the fail-closed
// rules are the Python hooks', shared with Claude Code and Codex.
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const HOOKS = join(ROOT, ".claude", "hooks");
const HOOK_TIMEOUT_MS = 30_000; // the same bound .claude/settings.json gives each hook
export const WRITERS = new Set(["write", "edit", "multiedit", "apply_patch"]); // from M9

export function payloadFor(tool, args, root = ROOT) {
  if (tool === "apply_patch") {
    return { tool_name: tool, tool_input: { command: String(args?.patchText ?? "") }, cwd: root };
  }
  return { tool_name: tool, tool_input: { file_path: String(args?.filePath ?? "") }, cwd: root };
}

export function touchesDrafts(payload) {
  const text = JSON.stringify(payload.tool_input);
  return text.includes("content/drafts/") || text.includes("content\\\\drafts\\\\");
}

export function runHook(script, payload, spawn = spawnSync) {
  // `python`, as every launcher here names it (docs/HOOKS.md's launcher contract).
  const result = spawn("python", [join(HOOKS, script)], {
    input: JSON.stringify(payload),
    encoding: "utf8",
    timeout: HOOK_TIMEOUT_MS,
  });
  if (result.error || result.status !== 0) {
    return { failed: true, detail: String(result.error ?? result.stderr ?? "") };
  }
  const out = (result.stdout ?? "").trim();
  if (!out) return {};
  try {
    return JSON.parse(out);
  } catch {
    return { failed: true, detail: out.slice(0, 500) };
  }
}

// From M10: a throw from tool.execute.after reaches the model as the tool's error.
// If M10 shows it does not, replace the body with
// `output.output = `${message}\n\n${output.output ?? ""}`;` and say so in docs/HOOKS.md.
export function deliver(output, message) {
  throw new Error(message);
}
```

  Of the `deliver` alternatives, keep only the one M10 measured, and
  delete the other and its comment before committing.

- [ ] **Step 4: Implement `.opencode/plugins/chitragupta-gate.js`.**

```js
// chitragupta's citation gate on OpenCode (#900). The helpers are in
// ../chitragupta/gate.js so this file exports exactly one plugin.
import { WRITERS, deliver, payloadFor, runHook, touchesDrafts } from "../chitragupta/gate.js";

export const ChitraguptaGate = async () => {
  const pending = new Map();
  return {
    "tool.execute.before": async (input, output) => {
      if (WRITERS.has(input.tool)) pending.set(input.callID, output.args);
    },
    "tool.execute.after": async (input, output) => {
      if (!pending.has(input.callID)) return;
      const payload = payloadFor(input.tool, pending.get(input.callID));
      pending.delete(input.callID);
      const gate = runHook("citation_gate_hook.py", payload);
      if (gate.failed) {
        if (touchesDrafts(payload)) {
          deliver(output, `chitragupta: the citation gate could not run, so this draft was not checked and is refused. ${gate.detail}`);
        }
        return;
      }
      if (gate.decision === "block") deliver(output, gate.reason);
      const note = runHook("style_check_hook.py", payload).hookSpecificOutput?.additionalContext;
      if (note) output.output = `${output.output ?? ""}\n\n${note}`;
    },
  };
};
```

- [ ] **Step 5: Write the end-to-end pytest** in
  `tests/test_opencode_plugin.py`:
  - **Unit tests:** run `node --test tests/opencode` and assert rc 0.
  - **End to end:**
    1. Build a `HookRepo`-style temporary tree: copy `.claude/hooks/*`
       and `.opencode/`, set `CONTENT_DIR`, and add a draft citing
       `not_a_real_citekey_2026`.
    2. Run a small Node driver that imports the plugin, calls `before`
       and then `after` with
       `{tool: "write", callID: "1"}` / `{args: {filePath: <draft>}}`.
    3. Assert the driver exits non-zero with the fake key on stderr.
  - Skip with `pytest.mark.skipif(shutil.which("node") is None, ...)`,
    the way `pandoc_available` gates pandoc tests.

- [ ] **Step 6: Run the tests and confirm they pass.**
  Run: `node --test tests/opencode && pytest tests/test_opencode_plugin.py -q`

- [ ] **Step 7: Measure on a real OpenCode session** in a scratch copy
  of the sample project, as in Task 5, Step 6:
  - `write`, `edit` and `apply_patch` each add
    `not_a_real_citekey_2026`. Expected: refused, naming the key, and
    the model fixes it.
  - A clean draft. Expected: not refused.
  - `PATH` without `python`. Expected: a draft write is refused, and a
    `README.md` write goes through.

- [ ] **Step 8: Commit, bump MINOR, and open the PR.** Close #900 only
  when Task 9 scaffolds the plugin.

```bash
git add .opencode tests/opencode tests/test_opencode_plugin.py .github/workflows/ci.yml pyproject.toml
git commit -m "Run the citation gate on OpenCode's file tools through a plugin"
```

---

### Task 8: Skills in harness-neutral wording, with conformant frontmatter

**Files:**

- Modify: all nine `.claude/skills/*/SKILL.md`, and
  `.claude/skills/deep-research/reference.md`
- Test: `tests/test_skill_frontmatter.py` (new)
- Test: `tests/test_skill_harness_neutral.py` (new)

**Interfaces:**

- Consumes: nothing from other tasks.
- Produces: skills that Claude Code, Codex and OpenCode each load
  unchanged.

**What changes, and what does not:**

- The self-check stays exactly where it is: each skill's existing
  `python -m chitragupta.draft gate` step. No `scripts/` folder is
  added to any skill. The check is already one CLI call, and a script
  in each of nine skills would be nine copies of it.
- `.claude/agents/*.md` stays. The skills already say "if no named
  subagent, dispatch a general one with the protocol from
  `.claude/agents/<name>.md`". That is a file any harness can read, so
  the wording change below is all Codex and OpenCode need.
- The `test_skill_*_step.py` scans keep passing unchanged, because no
  pinned step leaves `SKILL.md`.

**Frontmatter** (Agent Skills specification):

- `name` matches the folder name and the pattern
  `^[a-z0-9]+(-[a-z0-9]+)*$`.
- `description` is 1-1,024 characters.
- The only keys allowed are `name`, `description`, `license`,
  `compatibility`, `metadata` and `allowed-tools`.
- The existing `tags:` key is read by nothing (checked with
  `grep -rn tags tests chitragupta scripts`), so it is deleted.
- Four descriptions are over the limit. Their replacements are below,
  each measured under 1,024.
  - Every clause dropped from a description is already stated in that
    skill's body. Check each with `grep` before deleting it.
  - The STORM and hadufer/claude-storm (MIT) attribution dropped from
    deep-research's description must stay in its body. Confirm the
    body carries it, and add it there if not.

| Skill | New `description` (characters) |
| --- | --- |
| agenda-reviser | 987 |
| draft-reviser | 912 |
| deep-research | 890 |
| tutorial-writer | 950 |

agenda-reviser:

```text
Repairs the unattended findings on an existing draft's review agenda, one item at a time. Reads `python -m chitragupta.review agenda <draft>` and acts only on items whose `unattended` field says so; every other class is surfaced for a person to decide. One R4 cycle is one command, `review agenda <draft> --baseline <stem>.agenda.json --json`; passes continue only while `objective_class_count` strictly falls, and stop at `pass_bound`. Every repair must re-pass `python -m chitragupta.draft gate` and the same baseline recheck before it is kept, and every attempt is logged in revisions.md. Triggers when the user asks to work the review agenda, fix what an agenda run found, or act on unattended findings -- before rendering or submitting, after a sync moved the corpus, or on returning to a draft after weeks away. Judgement calls go to draft-reviser or the human. Never edits the allowlist, never adds a claim, never fabricates a citekey, and never runs unless a person asked for it.
```

draft-reviser:

```text
Revises an existing draft in content/drafts/ from its dossier instead of re-running the genre skill that produced it: reads the recorded scope, reader, glossary, kept evidence and rejected candidates, edits only the affected sections, and logs what changed. Triggers when the user asks to revise, shorten, expand, restructure or correct an existing draft, including in a session that did not write it. Also covers copy-editing that touches no evidence ("fix the grammar", "convert this to British English", "make it en-GB") and re-grounding after the corpus moves ("re-ground", "a cited paper left the corpus", a `dossier status --all` report naming a draft). The cheap, scoped default for any change. A whole-corpus re-search ("search everything, cost regardless") is corpus-reviser; a NEW draft is a genre skill's job. Must pass `python -m chitragupta.draft gate` before presenting and never invents a citekey.
```

deep-research:

```text
Runs a multi-perspective, corpus-grounded deep-research pipeline over the synced bibliography -- perspective discovery, parallel simulated interviews, contradiction mapping, outline, cited section writing, synthesis briefing, and self peer-review -- citing only real citekeys from content/ledger.sqlite, never a URL and never an invented key. Triggers when the user asks for "deep research", a multi-perspective analysis, or an in-depth grounded report on a topic, as distinct from survey-writer's single-pass literature survey. To change a report that already exists in content/drafts/, use draft-reviser instead -- never re-run this skill to make a change. Heavier and slower than survey-writer by design. Must run `python -m chitragupta.draft gate` before presenting. Stops and tells the user to run `python -m chitragupta.corpus sync` if the ledger is empty, rather than syncing itself.
```

tutorial-writer:

```text
Drafts a Diataxis-style tutorial -- a hands-on lesson a learner follows at a keyboard, start to finish, to a working result they can see -- verified to actually run before it is presented. Not a textbook chapter and not a how-to guide; if the reader is studying rather than doing, use `textbook-chapter-writer`, and if they only need the steps, say so rather than writing a tutorial. May cite the synced corpus (content/ledger.sqlite via chitragupta.retrieval.search()) only in a closing "Where to go next" section, never mid-lesson. Triggers when the user asks for a tutorial, a hands-on lesson, a getting-started walkthrough, a lab exercise, or a "teach someone X by having them build Y" document. To change a tutorial that already exists in content/drafts/, use draft-reviser instead -- never re-run this skill to make a change. Any citation must pass `python -m chitragupta.draft gate` before the draft is presented -- never a fabricated citekey.
```

**Wording replacements.** Every occurrence was located by the
2026-09-29 survey; re-run the `grep` in Step 1 to confirm the list.

| Where | Now | Becomes |
| --- | --- | --- |
| deep-research:182 | "Create a TodoWrite list with the 7 phases below" | "Keep a checklist of the 7 phases below" |
| deep-research:329-330, 834 | "multiple Agent calls in a single message" / "Dispatch same-phase subagents in one message" | "dispatch them in parallel if your harness can run subagents in parallel; otherwise one after another" |
| deep-research:331, 445-446, 515-516; survey-writer:301-302 | "use `general-purpose` and give it the protocol from `.claude/agents/<x>.md` (or tell it to `Read` that" | "if your harness has no subagent named `<x>`, dispatch a general-purpose subagent and give it the protocol in `.claude/agents/<x>.md` (or tell it to read that file" |
| deep-research:611; survey-writer:581; textbook:539; thesis:522; tutorial:582 | "Edit with `Edit`" | "Edit the passage in place" |
| draft-reviser:262-263 | "(`Read` with `offset=<start>`, `limit=<lines>`)" | "(read only lines `<start>` to `<start>+<lines>`)" |
| draft-reviser:334, 523, 593; corpus-reviser:136; agenda-reviser:114-115, 479 | "`Edit`, never `Write`" / "Use `Edit` on the specific passage. Do not `Write` the whole file" | "Edit the passage in place; never rewrite the whole file" |
| agenda-reviser:95, 271 | "the `draft_text` an `Edit`'s `old_string` needs" / "use it as `Edit`'s" | "the exact `draft_text` an in-place edit replaces" / "use it as the text to replace" |

- [ ] **Step 1: Write the failing tests.**

```python
"""Every skill loads on Claude Code, Codex and OpenCode alike (#812)."""

import re
from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parent.parent / ".claude" / "skills"
SKILL_FILES = sorted(SKILLS.glob("*/SKILL.md"))
ALLOWED = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Harness tool names a skill must not prescribe. Plain English ("Read the
# dossier", "Write the section") is fine; a backticked tool name, or a
# harness-only mechanism, is not.
FORBIDDEN = [r"`Edit`", r"`Write`", r"`Read`", r"\bTodoWrite\b", r"\bAgent calls?\b",
             r"in (?:a single|one) message", r"`old_string`"]


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    block = text.split("---", 2)[1]
    return dict(line.split(":", 1) for line in block.strip().splitlines() if re.match(r"^[a-z-]+:", line))


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.parent.name)
def test_frontmatter_follows_the_agent_skills_spec(path):
    fields = {k.strip(): v.strip() for k, v in frontmatter(path).items()}
    assert set(fields) <= ALLOWED, set(fields) - ALLOWED
    assert fields["name"] == path.parent.name and NAME_RE.match(fields["name"])
    assert 1 <= len(fields["description"]) <= 1024, len(fields["description"])


@pytest.mark.parametrize(
    "path", SKILL_FILES + sorted(SKILLS.glob("*/reference.md")), ids=lambda p: p.parent.name
)
def test_no_skill_prescribes_one_harness_tools(path):
    text = path.read_text(encoding="utf-8")
    hits = [pattern for pattern in FORBIDDEN if re.search(pattern, text)]
    assert not hits, f"{path.parent.name}: {hits}"
```

  Confirm the list with:

  ```bash
  grep -rnE '`(Edit|Write|Read)`|TodoWrite|Agent calls?' .claude/skills
  grep -rnE 'in (a single|one) message|`old_string`|`general-purpose`' .claude/skills
  ```

- [ ] **Step 2: Run the tests and confirm they fail.**
  Run:

  ```bash
  pytest tests/test_skill_frontmatter.py tests/test_skill_harness_neutral.py -q
  ```

  Expected: failures listing four descriptions, nine `tags` keys, and
  the wording hits.

- [ ] **Step 3: Apply the four descriptions,** delete `tags:` from all
  nine skills, and make the wording replacements in the table. One
  commit per skill keeps the review readable.

- [ ] **Step 4: Run every skill scan.**
  Run:

  ```bash
  pytest tests/test_skill_*.py tests/test_features_doc.py \
    tests/test_command_depth_scan.py tests/test_removed_command_scan.py -q
  ```

  Expected: PASS.

- [ ] **Step 5: Check the skills load.**
  - On Claude Code, start a session and confirm all nine skills are
    listed, with their new descriptions.
  - Repeat on OpenCode.
  - Repeat on Codex, once M7 says where Codex reads skills.

- [ ] **Step 6: Commit, bump MINOR, and open the PR.**

```bash
git add .claude/skills tests/test_skill_frontmatter.py tests/test_skill_harness_neutral.py pyproject.toml
git commit -m "Word the skills for any harness, and fit their frontmatter to the Agent Skills spec"
```

---

### Task 9: `chitragupta init --agent claude|codex|opencode`, and `doctor`

**Files:**

- Modify: `chitragupta/init.py`
  - `COPY_VERBATIM` (L71-80)
  - `TOP_LEVEL` (L135)
  - `DESCRIPTION` (L143-146)
  - `scaffold` (L251)
  - `build_parser` (L305)
  - `main` (L319)
- Modify: `chitragupta/doctor.py`, which gains a launcher check
- Modify: `pyproject.toml`: `[tool.poetry].include` (L33-48) gains
  `.codex` and `.opencode`
- Modify: `docs/PACKAGING.md`: the `init` row (L101-106)
- Modify: `AGENTS.md`: L43-59, the hook paragraph
- Test: `tests/test_init.py`, `tests/test_doctor.py`,
  `tests/test_release.py`

**Interfaces:**

- Consumes:
  - `launcher_configs.faults(root)` from Task 5;
  - `.codex/hooks.json` and `.opencode/` from Tasks 5 and 7.
- Produces:
  - `init.AGENT_TREES`, a `dict[str, tuple[str, ...]]`: `"claude": ()`,
    `"codex": (".codex",)`, `"opencode": (".opencode",)`
  - `scaffold(dest, *, force=False, dry_run=False, agents=("claude",)) -> list[str]`
  - The CLI takes `--agent NAME`, repeatable, choosing from
    `sorted(AGENT_TREES)`, with the default `["claude"]`.

**Rules:**

- **`.claude/` is scaffolded for every agent.** It holds the skills
  and the hooks that all three harnesses run. `CLAUDE.md` is scaffolded
  as today; it is a router, harmless elsewhere.
- **The default is unchanged.** `--agent claude` produces the same tree
  as today, byte for byte, so this is MINOR.
- **`.agents/skills/`** is written only for `codex`, and only if M7
  shows Codex cannot read `.claude/skills/`. It is a copy of
  `.claude/skills/`.
  - If M11 shows OpenCode loads duplicates, `init` refuses
    `--agent codex --agent opencode` together until M7 is solved. The
    refusal is a `ScaffoldTargetUnsafe`-style error naming why.
  - `doctor` reports a `.agents/skills/` that differs from
    `.claude/skills/`, since the copy goes stale after an upgrade.
- **Manifest parity.** `TOP_LEVEL` gains `.codex` and `.opencode`.
  `TestManifestAgreesWithTheReleaseZip` (`tests/test_init.py:218-230`)
  then still holds, because both are tracked and ship in the release
  zip. `.agents` is generated, not tracked, so it stays out of
  `TOP_LEVEL`.
- **`doctor`.**
  - It runs `launcher_configs.faults(Path.cwd())` and prints each fault
    as `[warn]`.
  - It reports `[warn] OpenCode plugin missing` when `.opencode/`
    exists but `.opencode/plugins/chitragupta-gate.js` does not.
  - It still always exits 0 (`doctor.py`'s contract).

- [ ] **Step 1: Write the failing tests** in `tests/test_init.py`:

```python
class TestAgents:
    def test_the_default_is_claude_and_unchanged(self, source_tree, tmp_path):
        assert init.scaffold(tmp_path / "a") == init.scaffold(tmp_path / "b", agents=("claude",))
        assert not (tmp_path / "a" / ".codex").exists()
        assert not (tmp_path / "a" / ".opencode").exists()

    def test_codex_adds_its_hooks(self, source_tree, tmp_path):
        init.scaffold(tmp_path, agents=("codex",))
        assert (tmp_path / ".codex" / "hooks.json").is_file()
        assert (tmp_path / ".claude" / "hooks" / "citation_gate_hook.py").is_file()

    def test_opencode_adds_its_plugin(self, source_tree, tmp_path):
        init.scaffold(tmp_path, agents=("opencode",))
        assert (tmp_path / ".opencode" / "plugins" / "chitragupta-gate.js").is_file()
        assert (tmp_path / ".opencode" / "chitragupta" / "gate.js").is_file()

    def test_agents_repeat(self, source_tree, tmp_path):
        assert init.main([str(tmp_path), "--agent", "codex", "--agent", "opencode"]) == 0
        assert (tmp_path / ".codex").is_dir() and (tmp_path / ".opencode").is_dir()

    def test_an_unknown_agent_is_a_usage_error(self, tmp_path):
        with pytest.raises(SystemExit) as exc:
            init.main([str(tmp_path), "--agent", "continue"])
        assert exc.value.code == 2

    def test_dry_run_names_the_agent_trees(self, source_tree, tmp_path, capsys):
        init.main([str(tmp_path), "--dry-run", "--agent", "codex"])
        assert ".codex/hooks.json" in capsys.readouterr().out
        assert not tmp_path.joinpath(".codex").exists()
```

  `source_tree` is the existing fixture that builds a fake
  `SOURCE_ROOT`; extend it to include `.codex/hooks.json` and the two
  `.opencode` files. In `tests/test_doctor.py`, add a case with a
  `.codex/hooks.json` whose command is `no-such-interpreter-812`,
  asserting a `[warn]` line naming it and exit 0.

- [ ] **Step 2: Run the tests and confirm they fail.**
  Run: `pytest tests/test_init.py tests/test_doctor.py -q`

- [ ] **Step 3: Implement `init`.**

```python
# Which trees each harness adds on top of the shared core. `.claude/` is
# in COPY_VERBATIM for every harness: it holds the skills all three read
# and the hooks all three launch (#812).
AGENT_TREES = {"claude": (), "codex": (".codex",), "opencode": (".opencode",)}
```

  1. In `scaffold`, after the `COPY_VERBATIM` loop:

```python
    for name in dict.fromkeys(tree for agent in agents for tree in AGENT_TREES[agent]):
        report.extend(_write_tree(SOURCE_ROOT / name, dest / name, force=force, dry_run=dry_run))
```

  1. Include the agent trees in the `missing` check, so a wheel built
     without `.codex/` refuses rather than scaffolding a Codex project
     with no gate. That is the #509 lesson in `scaffold`'s own comment.
  2. `build_parser` gains:

```python
    parser.add_argument(
        "--agent", action="append", choices=sorted(AGENT_TREES), dest="agents",
        help="Harness to set up: claude (default), codex, opencode; repeat for several",
    )
```

  1. `main` passes `agents=tuple(args.agents or ["claude"])`.

  If M7 requires it, add the `.agents/skills/` copy as one more
  `_write_tree` call, from `SOURCE_ROOT / ".claude" / "skills"` to
  `dest / ".agents" / "skills"`, when `"codex" in agents`, with its own
  test.

- [ ] **Step 4: Implement the `doctor` check** as described above,
  keeping `main` under 25 statements.

- [ ] **Step 5: The packaging sweep, in the same PR.**
  - `pyproject.toml` includes `.codex` and `.opencode`.
    `tests/test_pyproject_extras.py` or `tests/test_release.py` should
    assert both are in the wheel.
  - `docs/PACKAGING.md`'s `init` row reads
    `chitragupta init [DIR] [--force] [--dry-run] [--agent NAME]`. The
    leaf-command count does not change.
  - `init.DESCRIPTION` mentions `--agent`.
  - `AGENTS.md:55-59` says the gate hook runs on Claude Code (Write or
    Edit), Codex (`apply_patch`) and OpenCode (the plugin), and that
    `draft render` refuses in every format.

- [ ] **Step 6: Run the tests and confirm they pass.**
  Run:

  ```bash
  pytest tests/test_init.py tests/test_doctor.py tests/test_release.py \
    tests/test_packaging_command_table.py -q
  pytest -q --cov --cov-branch
  ```

- [ ] **Step 7: Check from a built wheel.**
  1. `poetry build`
  2. `pip install dist/*.whl` into a fresh venv
  3. `chitragupta init /tmp/p --agent codex --agent opencode`
  4. Confirm both launchers are present.
  5. Run `chitragupta doctor` in `/tmp/p`.

- [ ] **Step 8: Commit, bump MINOR, and open the PR.** It closes #900
  together with Task 7.

```bash
git add chitragupta/init.py chitragupta/doctor.py pyproject.toml docs/PACKAGING.md AGENTS.md tests
git commit -m "Scaffold Codex and OpenCode launchers with chitragupta init --agent"
```

---

### Task 10: Document what each harness enforces, and record local-model runs

**Files:**

- Modify: `docs/HOOKS.md`
  - the measured-trials table (L584-596), with a Harness column added;
  - "Emit only the field this host consumes" (L573-580);
  - the open questions (L839-861).
- Modify: `docs/ARCHITECTURE.md:202`
- Create: `docs/LOCAL-MODELS.md`
- Modify: `docs/FEATURES.md` if its hook description names only Claude
  Code. `tests/test_features_doc.py` checks the links resolve.
- Modify: `mkdocs.yml` nav, to add `LOCAL-MODELS.md`

- [ ] **Step 1: Write up HOOKS.md.**
  - Add the Codex and OpenCode trials from Task 5 Step 6, Task 6 Step 7
    and Task 7 Step 7, each dated, with the harness version.
  - Add a per-harness enforcement table:

    | Harness | Self-check | Mandatory check | Last check |
    | --- | --- | --- | --- |
    | Claude Code | the skill runs `draft gate` | `PostToolUse` hook (Write or Edit), after the write | `draft render` |
    | Codex | the skill runs `draft gate` | `PostToolUse` hook on `apply_patch`, after the write, once the project hooks are trusted | `draft render` |
    | OpenCode | the skill runs `draft gate` | plugin on `tool.execute.after`, after the write | `draft render` |

  - State plainly that a shell write passes the mandatory check on all
    three, that `draft render` catches it, and that `gate_liveness`
    warns about it.

- [ ] **Step 2: Record the local-model runs.**
  - On Codex (`--oss` or `--local-provider`, with Ollama or LM Studio)
    and on OpenCode (an Ollama provider), draft one survey end to end
    over `docs/examples/sample-project/`.
  - In `docs/LOCAL-MODELS.md`, record:
    - the date, model, quantisation and context size;
    - the harness version;
    - where the self-check and the mandatory check fired, and what
      they caught;
    - whether the skill fitted in context.

    Make no general quality claim.
  - If a skill did not fit, file a follow-up issue to split its body
    into `references/`, citing the measured overflow. That split is
    deliberately not done before a run shows it is needed.

- [ ] **Step 3: Run the docs checks.**
  Run: `pytest tests/test_features_doc.py -q` and
  `markdownlint-cli2 "docs/**/*.md"`, using whatever
  `.markdownlint.yaml` CI runs.

- [ ] **Step 4: Commit, bump PATCH, and open the PR.** It closes #812.

```bash
git add docs mkdocs.yml pyproject.toml
git commit -m "Document the gate on Codex and OpenCode, with measured local-model runs"
```

---

## ✅ Success criteria, and the task that meets each

| Criterion (#812 / #900) | Task |
| --- | --- |
| A draft with a fabricated key cannot be rendered on any harness, and the refusal names the key | 1 |
| On Codex, an `apply_patch` touching `content/drafts/` runs the gate and blocks on a fabricated key (measured) | 3, 4, 5 |
| On OpenCode, a write or edit with a fabricated key is refused, naming the key (measured) | 7 |
| If the gate cannot run, a draft write is refused, not let through | 4 (Codex, via the existing hook), 7 (OpenCode) |
| `init --agent <harness>` scaffolds a working project for each, and `doctor` reports a dead launcher | 9 |
| Skills have one source of truth | 8 (one copy in `.claude/skills/`), 9 (the `.agents/skills/` copy, if any, checked by `doctor`) |
| One survey drafted end to end on a local model through each non-Claude harness, with the run recorded | 10 |
| Line and branch coverage stays at 100% | every task |
| No citekey is generated, guessed or rewritten, and no new check becomes a gate | every task; `gate_liveness` is a warning, never a verdict |

## 📏 Measured

2026-09-29, Codex 0.159.0 and OpenCode 1.18.33, in a project scaffolded
from the built wheel, each driven by a local stand-in model that answered
with scripted tool calls and logged what the harness handed back.
[docs/HARNESS.md](../docs/HARNESS.md) has the prose.

- **M1.** `tool_input.command` is a plain string.
- **M2.** The payload carries `cwd`, and patch paths are relative to it.
- **M3.** Yes: the block's `reason` replaces the tool output the model
  reads, naming the key and line.
- **M4.** `SessionStart` `additionalContext` arrives as a developer
  message. `PostToolUse` advisory: not measured (no prose finding).
- **M5.** A hook runs in the session's working directory, with no
  project-directory variable. The relative launcher failed from a
  subfolder; the walk-up `python -P -c` launcher replaced it.
- **M6.** Project hooks are skipped, silently, until trusted
  (`--dangerously-bypass-hook-trust` exists for the non-interactive
  case). The liveness warning fired on the untrusted write.
- **M7.** `.agents/skills/` only, never `.claude/skills/`; `init --agent
  codex` now copies them. `AGENTS.md` is read natively.
- **M8.** A `tags:` key loads. A description over 1,024 characters is
  cut at 1,024 in the model's view.
- **M9.** From source: `tool.execute.after` receives `{tool, sessionID,
  callID, args}`, so the `before` hook is not needed to see the
  arguments. Argument keys per the docs; no live call.
- **M10.** From source: a throw from either hook fails the tool call
  (`Effect.promise` around the hook); a throw in `before` precedes the
  write. Not observed live: OpenCode's agent loop never sent its main
  model request in this container.
- **M11.** One copy per name, chosen arbitrarily across
  `.opencode/skills/`, `.claude/skills/` and `.agents/skills/`; only
  `OPENCODE_DISABLE_EXTERNAL_SKILLS=1` (environment only) restricts it.
- **M12.** Not measured.

## 🔁 What changed along the way

Recorded while building Tasks 1-9, 2026-09-29.

- **Render with no ledger raises `NoLedger`, not `UngatedDraft`.** A
  citing draft with no ledger at all used to say "No ledger at ... run
  `sync`", which is more use than every key listed as unknown, and
  `tests/test_ledger_readers.py` pins it. `_gate.gated_warnings` lets
  `NoLedger` through to the error the CLI already prints.
- **The `MissingCitekey` handler in `render_output/_cli.py` stays.** The
  gate now refuses such a draft first, so the handler is reached only
  when a sync commits between the gate's read and the numbering step's.
  It is kept for that race, with a test.
- **The OpenCode plugin delivers a refusal on both channels.** M10 is
  unmeasured, so `deliver()` rewrites the tool output *and* throws;
  whichever OpenCode honours, the model sees the refusal. Keep only the
  measured one once Task 0 runs.
- **`gate_liveness` reports dead launchers from the project the command
  runs in, and unseen drafts only in the project the drafts live in.**
  The first is where `hook_launchers` always looked; the second keeps a
  test whose `CONTENT_DIR` is a temporary directory from seeing this
  checkout's own launchers.
- **One liveness record per draft, not one shared JSON file.** The code
  blocks in Task 6 above show `content/.gate-seen.json`; what was built
  is `content/.gate-seen/<hash of the draft's path>`, holding a hash of
  the text. A shared file is read and rewritten by every gate hook, so
  two hooks gating different drafts at once -- parallel subagents writing
  sections -- could lose one record and raise a false warning. Found in
  the OpenCodeReview pass.
- **The `doctor` check reports `[launcher]` lines**, and one `[ok]` line
  when every launcher it found can start.
- **The skills scan also forbids a backticked `general-purpose`**, the
  Claude Code subagent type; a skill now says "a general-purpose
  subagent" in plain words.
- **Two bugs found by Task 0, and fixed.** The relative Codex launcher
  failed from any subfolder (M5), and a Codex project got no skills
  (M7). Both are fixed and pinned by tests.
- **`docs/LOCAL-MODELS.md` was not written.** It is a record of runs,
  and no run has been made; it arrives with the first one.

## 📚 Sources for the harness facts assumed above

Every one of these is re-checked by Task 0.

- [Codex hooks](https://developers.openai.com/codex/hooks): event
  names, project `.codex/hooks.json`, `apply_patch` in
  `tool_input.command`, and trust by hash.
- [Codex skills](https://developers.openai.com/codex/skills):
  `.agents/skills/`.
- [The V4A `apply_patch` format](https://codex.danielvaughan.com/2026/03/31/codex-cli-apply-patch-v4a-diff-format/).
- [OpenCode plugins](https://opencode.ai/docs/en/plugins/):
  `tool.execute.before` and `tool.execute.after`.
- [OpenCode skills](https://opencode.ai/docs/it/skills/): reads
  `.opencode/skills`, `.claude/skills` and `.agents/skills`.
- [OpenCode tools](https://opencode.ai/docs/tools/): `edit` arguments,
  and `apply_patch`'s `patchText`.
- [Agent Skills specification](https://agentskills.io).

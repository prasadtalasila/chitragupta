# Shrinking every skill to its budget, by deduplication (#1091)

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

Status: **plan, PR 0 open.** Written 2026-11-13 against `9aa75085`
(6.170.2), branched from `a76b9ba1` (6.172.0), for
issue [1091](https://github.com/prasadtalasila/chitragupta/issues/1091).
Each PR below has a sub-issue under #1091; the last one closes it.

**Written for** whoever builds any PR in this series, on whichever
machine: the A40 server clones each PR and runs the bench there.
**Assumed:** [plans/997-1091-skill-budget.md](997-1091-skill-budget.md)
(the budget test, the link tests, `skills-common/`), and
[docs/HARNESS.md](../docs/HARNESS.md) (three `SKILL.md` copies per skill,
every other file once under `.claude/`). **Not covered here:** the
`research-paper-writer` skill (#1178), which inherits what this series
builds, and any change to a skill's frontmatter `description`.

**Goal:** every skill's `SKILL.md` holds its steps, its commands and the
judgement calls only a model can make, with no meaning written twice
across skills or harness copies, so that no step is long enough to skim
past.

**Architecture:** writing rules move to a layered
`docs/writing-standards/`; procedure the genre writers share moves to one
`.claude/skills-common/references/genre-steps.md`; what one skill alone
needs moves to that skill's single `references/<genre>.md`. A
developer-only `skill-bench` skill measures each shrink on all three
harnesses before and after.

**Tech stack:** Markdown skills on three harnesses (Claude Code, Codex,
OpenCode); pytest text scans; `bench/bench_skill_harnesses.py`;
llama.cpp with CUDA on the A40 server.

## Handoff: where this stands, and what the A40 server needs

All work from PR 0 on happens on the A40 server. This plan was
brainstormed, grilled and reviewed in an earlier session, and that
session's context does not travel, so this section carries what it knew.

**Done:**

- the sub-issues, #1196–#1205 under #1091, and #1206 outside the series;
- the note on #1091 about what #1173 dropped;
- cross-links on #1181, #1157, #1128, #1199 and #1203;
- a Fable-model review of this plan, all 17 findings applied.

PR 0's branch, `feat-1091-skill-bench`, holds only this plan and the
version bump to 6.173.0 (MINOR: PR 0 adds a script and a developer
skill, `DEVELOPER-AGENTS.md:1149-1151`). Tasks 1–3 are not started, and
the execution method (subagent-driven or native) is for the user to
choose.

**Line numbers are from `9aa75085` and are already stale in places.**
After it, #1193 and #1195 (`a76b9ba1`):

- changed the `SKILL.md` of textbook-chapter-writer, agenda-reviser,
  corpus-reviser and draft-reviser;
- added about 44 lines to `docs/WRITING-STANDARDS.md` before §10;
- raised two caps: agenda-reviser to 29,000 and draft-reviser to
  30,000, each with reason `"#1091: ...; draft diff closing step
  (#1194)"`. PRs 4 and 5 must absorb that new closing step.

Find each cited passage by its text, and treat a line number as a hint.

**Reproducing the #1068 bench setup.** The earlier host kept these
under `~/bench-tools/`:

| Item | Exact version |
| --- | --- |
| Codex, OpenCode | npm `@openai/codex@0.159.3`, `opencode-ai@1.18.34` |
| llama.cpp | release `b11321`; build it with `-DGGML_CUDA=ON` here (the earlier host ran the CPU build) |
| Model file | `Qwen3.6-35B-A3B-UD-Q4_K_M.gguf`, 22,134,528,992 bytes, SHA-256 `ac0e2c1189e055faa36eff361580e79c5bd6f8e76bffb4ce547f167d53e31a61`. `install_tools.sh --check` verifies the hash |
| Served name | `qwen3.6-35b-a3b` (the bench's `MODEL` default), OpenAI-compatible at `http://127.0.0.1:18080/v1` (`BASE_URL` default) |

The earlier host ran 24k context on CPU. On the A40 server, use up to
the 131,072 that `docs/examples/opencode/opencode-provider.json`
declares, and record the `llama-server` flags you used in
`docs/HARNESS.md`. Claude Code runs need `claude` logged in on the
server.

**Running the suite on a fresh machine:**

1. Install TeX Live with `scripts/install_full_pipeline.sh os-deps`.
2. Make a venv with every extra and `pytest-xdist`.
3. Copy `config.toml.example` to `config.toml` in the checkout. Don't
   pass a relative `CONFIG_PATH`: about 20 subprocess tests run in
   other directories.
4. If the venv is an editable install of a different checkout, set
   `PYTHONPATH` to this checkout as an absolute path.
5. Run `pytest -n auto --cov`, about 5 minutes. Never run two coverage
   runs in one tree at once: they share `.coverage.*` files.

**Merging:**

- **Version bump:** every PR raises the version
  (`scripts/check_version_bump.py`). main moves several times a day,
  and identical version lines merge silently, so re-read
  `git show origin/main:pyproject.toml` just before merging. If main
  has moved, merge main in rather than amending.
- **How to merge:** run `scripts/merge_pr.py N` with `GH_TOKEN` set.
  The PR body's "Commit message" fence is the squash body.
- **Reviews:** each PR gets a Fable-model review. Copilot review cannot
  be requested with the repository's token, so each PR says so rather
  than claiming it.

## Decisions (user, 2026-11-11 to 11-13)

1. **The byte cap is a guard, not the goal.** The goal is deduplication
   and one wording per rule. The targets are 12,000 bytes for a genre
   writer and 8,000 for any other skill. Never compress prose to fit:
   that is how #1173 lost six passages
   ([noted on #1091](https://github.com/prasadtalasila/chitragupta/issues/1091#issuecomment-6849659277)).
   Where the two pull apart, no compression wins: a genre writer that
   real deduplication leaves above 12,000 stops and goes back to the
   user before its PR opens; any other skill records the reason in its
   cap row.
2. **Commands stay in `SKILL.md`** (#1091 item 3): every
   `python -m chitragupta...` line, every marker a draft must carry, and
   every phrase a test reads from the raw file. Output samples (the
   `text` fences in thesis step 9) may move.
3. **What moves is decided by branch:** inline what every run needs;
   move behind a pointer what only some runs reach.
4. **Every step ends on a one-line `Done when`.** Every pointer states
   the condition for reading it ("when you decide a figure is warranted,
   read ..."). "Never" stays only on guardrails, each paired with the
   positive target. Behaviour the CLI's `--help` or `docs/CLI.md` already
   states is cut. Issue numbers and "since #N" history leave skill text.
5. **Where text goes:**

   | Kind of text | Home |
   | --- | --- |
   | A writing rule | `docs/writing-standards/` (PR 0b) |
   | Procedure shared by the genre writers | `.claude/skills-common/references/genre-steps.md` |
   | What one skill alone needs | `.claude/skills/<skill>/references/<genre>.md`, one file |

6. **Step numbers other files cite stay fixed**: survey 1, 2, 2a, 9, 10;
   textbook 4; thesis 9, 12. Only tail steps after them may merge. Any
   number that does change is updated in the same PR (list in PR 1,
   Task 6).
7. **Descriptions are not touched** until `skill-bench` can measure
   triggering.
8. **One PR per row of the series table.** Each shrink PR is a PATCH
   bump. PR 0 is MINOR, because it adds a script and a developer skill.
   One MINOR release follows the last PR, so PyPI gets the series at
   once.
9. **Reviews:** a Fable-model review of this plan, then of each PR.
   Copilot cannot be requested with this repository's token; each PR
   says so.
10. **Bench every shrink PR** on the A40 server: 3 runs before and 3
    after, per harness, on the skill changed. PR 0b gets Tier 1 only.
    With 3 runs a one-run drop is noise, so the pass rule (PR 0 Task 2)
    calls it inconclusive and reruns rather than failing. Results are
    comparable within this series only: #1068 ran the same GGUF on the
    CPU host with one slot.

## The series

| PR | Issue | Scope | Version |
| --- | --- | --- | --- |
| 0 | #1196 SK-0 | this plan, `skill-bench`, bench `--source`, `--jobs`, `--base-url`, `--runs`, per-command scoring, `--compare` | minor (a new script, `DEVELOPER-AGENTS.md:1149-1151`; #1189 did the same) |
| 0b | #1197 SK-0b | `docs/WRITING-STANDARDS.md` split into `docs/writing-standards/` | patch |
| 1 | #1198 SK-1 | `genre-steps.md`, survey-writer, `genres/survey.md` | patch |
| 2 | #1199 SK-2 | textbook, thesis, tutorial; `placement.md` §4; tutorial captions | patch |
| 3 | #1200 SK-3 | review-digest, restoring what #1173 dropped | patch |
| 4 | #1201 SK-4 | draft-reviser | patch |
| 5 | #1202 SK-5 | agenda-reviser | patch |
| 6 | #1203 SK-6 | book-assembler | patch |
| 7 | #1204 SK-7 | corpus-reviser | patch |
| 8 | #1205 SK-8 | deep-research; closes #1091; then the MINOR release | patch, then minor |

Each PR says "Closes #<its issue>" and "Part of #1091"; only PR 8 also
closes #1091. #1206 (demo-recorder's install sources) is outside the
series.

Every PR bumps the patch version from `origin/main` as it stands at
merge time. main moves several times a day and identical version lines
merge without conflict, so re-read `git show origin/main:pyproject.toml`
right before merging and merge main rather than amend.

## Global constraints

- A citekey is never generated, guessed or rewritten, in a skill, a
  reference, a test fixture or an example (CLAUDE.md, SOUL.md).
- No new check becomes a gate.
- Line and branch coverage stays at 100% (`bench/` is outside it).
- A reference file holds no backticked skill name and no harness tool
  word (`tests/test_skill_references.py:70-74`); handoffs and harness
  phrases (`survey_subagents`, `critique_edit_tool` in
  `tests/fixtures/skill_harness_phrases.toml`) stay in `SKILL.md`.
- A shared reference names no step number and contains no command.
- Every `## N.` section of a reference is cited as `` `path` §N `` by
  some `SKILL.md`, identically in all three copies; sections are joined
  only by ", " or " and " (`tests/skill_text.py` `_CITED`).
- A cap drops in the same commit as its skill, to within 1,000 bytes of
  the largest copy (the `.opencode` copy, usually by about 130 bytes).
- Edit all three copies of a `SKILL.md`; the `.opencode` copy suffixes
  skill names with `-opencode` and re-wraps.

## Review focus

The failures most likely to reach a user that no task's own test
exercises, each pinned by a test in the task named:

1. **A rider leaves its window.** `expanded()` splices a whole reference
   at each citation, so a new citation placed just before the critique,
   prose-check or verbatim-scan pointer pushes that step's riders past
   their 1,400, 2,000 or 5,900-character windows. Pinned by running
   `tests/test_skill_pregate_feedback_step.py`,
   `tests/test_skill_style_check_step.py` and
   `tests/test_skill_verbatim_scan_step.py` in PR 1 Task 5 and PR 2.
   No citation goes inside those three steps.
2. **A model reads a pointer and skips the step.** Pinned by
   `skill-bench`'s per-command scoring (PR 0 Task 2) and the
   before/after rule in every shrink PR.
3. **A moved passage escapes a check that scanned it before.**
   `tests/test_install_remedies.py` and
   `tests/test_pdf_requirement_wording.py` do not scan
   `.claude/skills-common/`. Extended in PR 1 Task 1.
4. **A `§N` citation stops resolving after the split.** Skills cite
   `docs/WRITING-STANDARDS.md` §N 134 times across their three copies,
   `chitragupta/style_*` prints §9, §10, §12, §13, §14, §15, §16 and
   "section 8", 34 links use anchors (27 to `#-sources-and-attribution`),
   and three links inside the moving sections are same-file anchors.
   Pinned by the resolution test in PR 0b Task 1 and by
   `mkdocs build --strict`.
5. **A sentence goes missing in a move.** Pinned by the move ledger each
   shrink PR keeps (PR 1 Task 3): every paragraph removed from a
   `SKILL.md` is listed with where it went or why it was cut.

---

## PR 0: the plan, and a skill that benchmarks skills

Branch `feat-1091-skill-bench`. Opened first so the A40 server can clone
it and measure every baseline on `main` before any skill changes.

### Task 1: the bench measures any skill, from any checkout, in parallel

**Files:**

- Modify: `bench/bench_skill_harnesses.py` (`scaffold` :150, `run` :209,
  `tier2` :374, `self_check` :403, `main` :494)
- Modify: `bench/README.md`

**Interfaces:**

- Produces, as command-line flags of `bench_skill_harnesses.py`:
  - `--source DIR` (default `REPO_ROOT`): the checkout whose skills are
    scaffolded. `scaffold` runs `python -m chitragupta.init` with
    `cwd=DIR` (`init.py:59-60` takes `SOURCE_ROOT` from its own
    `__file__`, and `-m` imports from the working directory first). Only
    the scaffold comes from `DIR`: the corpus sync, the gate, the hooks
    and every command a model runs use the installed `chitragupta`, the
    same for both arms. That is sound because this series changes no
    `chitragupta/` code; a PR that does must be benched from its own
    venv instead, and `skill-bench` says so.
  - `--base-url URL`, repeatable (default `[BASE_URL]`): each Codex or
    OpenCode job takes the next URL in turn (Claude Code jobs take none:
    they run on the API), sets `BASE_URL` in its own environment
    (overriding `harness_env()`:118), and passes it to `command()`, which
    takes the URL as a parameter instead of the module constant (:200).
    OpenCode reads it through `opencode-provider.json`'s
    `{env:BASE_URL}`.
  - `--jobs N` (default 1): runs up to *N* (harness, skill, run) jobs at
    once with `concurrent.futures.ThreadPoolExecutor`, each in its own
    `out/<harness>/<skill>/run-<k>/project`.
  - `--runs N` (default 1): repeats each Tier 2 task.
  - `--skill` choices and default become `USER_SKILLS` from
    `tests/test_skill_harness_copies.py`, not `SKILLS`: `init` never
    scaffolds a developer-only skill (`init.py:296-302`), so Tier 1 on
    `demo-recorder` or `skill-bench` fails by construction.
  - `--skill` now selects the Tier 2 task too. `TIER2_TASKS`, a dict
    from skill name to a task (prompt, draft path, and the task it runs
    after, if any), holds one task for every user skill but
    figure-drawer, which the genre writers call:

    | Skill | Task | Runs after |
    | --- | --- | --- |
    | survey-writer | the existing `TIER2_SURVEY` on `docs/examples/codex` | — |
    | textbook-, thesis-chapter-, tutorial-writer | one topic the codex corpus covers each | — |
    | review-digest | a digest on the survey's topic | — |
    | deep-research | a report on the survey's topic | — |
    | draft-reviser | the existing `TIER2_COPYEDIT` | survey-writer |
    | corpus-reviser | re-check the survey against the whole corpus | survey-writer |
    | agenda-reviser | work the survey's review agenda | survey-writer |
    | book-assembler | assemble `docs/examples/sample-project`'s `twin-basics` spec and its units | — |

    A chained task runs its prerequisite in the same job and scores only
    its own transcript.

- [ ] **Step 1:** Add the four flags, the `USER_SKILLS` default and
  `TIER2_TASKS`. Write each new prompt in the shape of `TIER2_SURVEY`:
  the skill named, its input, "follow the skill through to the end,
  including its self-check with draft gate". For book-assembler, check
  that `twin-basics`' units carry acceptance records; if not, the task
  scaffolds them as the fixture, never by editing the example.
- [ ] **Step 2:** `self_check()` gains a check that `--source` points at a
  directory holding `chitragupta/init.py`, and that `--jobs` above
  `len(--base-url)` warns that jobs will share a server slot.
- [ ] **Step 3:** Run `python bench/bench_skill_harnesses.py --tier 1
  --harness claude --skill survey-writer --source .`. Done when it
  prints `tier 1: 1/1 passed`.
- [ ] **Step 4:** Commit.

### Task 2: score each run against the skill's own commands, and compare

**Files:**

- Modify: `bench/bench_skill_harnesses.py`
- Modify: `docs/HARNESS.md` (section "Measured, and what is still not")

**Interfaces:**

- Produces:
  - `expected_commands(source: Path, harness: str, name: str) -> list[str]`:
    every distinct `chitragupta.<module> <sub>` the harness's copy of
    `SKILL.md` names, inline or fenced, in order of first appearance
    (pattern `python (?:-P )?-m chitragupta\.(\w+)(?: ([a-z][\w-]*))?`),
    minus `FORBIDDEN = {"corpus sync", "corpus enrich"}`: skills name
    those only as what never to run (survey-writer's description and its
    read-only section), so counting them would mark every correct run.
    A forbidden command a run did execute is reported as `forbidden_ran`.
  - Each Tier 2 result gains `expected`, `ran` (the subset found in
    `tool_inputs(log)`, in the order first run), `missed` and
    `forbidden_ran`. `RENDER_STEP` and its use in `self_check()`
    (:479-480) are replaced by this.
  - `--compare BEFORE.json AFTER.json`: prints one table per (harness,
    skill), with each command's run count before and after, the gate
    pass count, and `forbidden_ran`. The command set is the union of
    both arms' `expected`. Verdict per (harness, skill):
    - **fail** (exit 1): a command ran in two or more fewer runs after
      than before; or a command ran in every before run and no after
      run; or the gate passed before and never after; or a forbidden
      command ran after and not before.
    - **inconclusive** (exit 3): a one-run drop in any command or in the
      gate. `skill-bench` then runs 3 more on both arms and compares the
      6 against 6, where the fail thresholds double.
    - **pass** (exit 0): otherwise.

- [ ] **Step 1:** `self_check()` gains five cases, checked on a fixture
  `SKILL.md` string and fixture JSONL transcripts: a fenced and an inline
  command are both found; `python -P -m` matches like `python -m`; a
  command named in the skill but absent from the tool calls lands in
  `missed`; `corpus sync` named in the skill is not `expected`; and
  `--compare` on 3-vs-3 fixtures gives pass for an equal pair,
  inconclusive for a one-run drop and fail for a 3-to-0 drop.
- [ ] **Step 2:** Implement `expected_commands`, the result fields and
  `--compare`.
- [ ] **Step 3:** Run `python bench/bench_skill_harnesses.py --compare
  a.json a.json` on any recorded `tier2.json`. Done when it exits 0 and
  prints every command as unchanged.
- [ ] **Step 4:** In `docs/HARNESS.md`, record the pass rule above and
  why a one-run drop is not a failure at 3 runs: at a true per-run rate
  of 0.8, a 3-of-3 baseline followed by 2-of-3 happens about a quarter
  of the time per command, and a skill has about nine commands on each
  of three harnesses.
- [ ] **Step 5:** Commit.

### Task 3: the `skill-bench` developer skill

**Files:**

- Create: `.claude/skills/skill-bench/SKILL.md`,
  `.agents/skills/skill-bench/SKILL.md`,
  `.opencode/skills/skill-bench-opencode/SKILL.md`
- Create: `.claude/skills/skill-bench/scripts/install_tools.sh` (with
  `--check`, in the shape of
  `.claude/skills/demo-recorder/scripts/install_tools.sh`)
- Create: `.claude/skills/skill-bench/scripts/serve_models.sh`
- Create: `tests/test_skill_bench_install_tools.py`, in the shape of
  `tests/test_demo_recorder_install_tools.py` (#1190)
- Modify: every file #1189 (`fa9dae41`) touched to add `demo-recorder`
  and that names developer skills:
  - `.opencode/opencode.json` (the deny rule)
  - prose that says "only `demo-recorder`": `docs/HARNESS.md:213`,
    `docs/ARCHITECTURE.md:192`, `docs/PACKAGING.md:244-247`,
    `docs/GENRE.md:12`, `DEVELOPER.md:321`, `scripts/release.py:21`
    (docstring), `bench/README.md`
  - `tests/test_developer_skills.py:105-110`: rename
    `test_demo_recorder_is_developer_only_on_every_harness` to cover both
    skills and add `skill-bench`'s three paths to the set
  - `tests/test_release.py:135-138`, `tests/test_skill_size.py`
    (`"skill-bench": (<cap>, None)`, under 8,000),
    `tests/test_skill_frontmatter.py:42` (the count),
    `tests/test_skill_harness_copies.py`
- Not modified, on purpose: `pyproject.toml`'s `include` list gets no
  `skill-bench` entry (`test_pyproject_ships_every_harness_file_but_the_developer_skills`
  would fail if it did), and `[tool.coverage.run].source`
  (`pyproject.toml:396`, `coveragerc-windows.toml:20`) needs nothing,
  because the scripts are bash. `docs/FEATURES.md` counts
  `USER_SKILLS` (`tests/test_features_doc.py:29,36`) and is unchanged.

**Interfaces:**

- Consumes: Task 1's flags and Task 2's `--compare`.
- Produces: `serve_models.sh N` starts one `llama-server` per GPU,
  `CUDA_VISIBLE_DEVICES=i`, on port `18080+i`, and prints the
  `--base-url` arguments for the bench.

The skill's frontmatter carries `metadata:` / `audience: developer`. Its
steps, each with a `Done when`:

1. Check the tools: `bash .claude/skills/skill-bench/scripts/install_tools.sh --check`,
   which pins Codex 0.159.3, OpenCode 1.18.34, llama.cpp b11321 built
   with `-DGGML_CUDA=ON`, and the Qwen3.6-35B-A3B `UD-Q4_K_M` GGUF (the
   same file as #1068, so results stay comparable). Without `--check` it
   installs them. Done when it exits 0.
2. Start the servers: `bash .claude/skills/skill-bench/scripts/serve_models.sh <gpus>`.
   Done when every port answers `/v1/models`.
3. Make two worktrees: the base (`origin/main` at the PR's merge base)
   and the PR head. If the PR changes `chitragupta/`, also make a venv
   for each, since `--source` swaps only the scaffold. Done when
   `git -C <worktree> rev-parse HEAD` prints the two expected commits.
4. Run the bench from the PR head's checkout, so both runs use the same
   bench code, once per worktree:

   ```bash
   python bench/bench_skill_harnesses.py --tier 2 --skill <name> \
     --runs 3 --jobs <n> --source <worktree> --out <dir> <base-urls>
   ```

   Done when both `tier2.json` files exist with 3 runs per harness.
5. Compare them:

   ```bash
   python bench/bench_skill_harnesses.py --compare \
     <before>/tier2.json <after>/tier2.json
   ```

   On exit 3 (inconclusive), run 3 more on both arms and compare the
   merged files. Done when it exits 0 (pass) or 1 (fail, reported as
   such, never rerun until it passes).
6. Record the table, the host (GPUs, driver, llama.cpp build) and the
   verdict in `docs/HARNESS.md`, and post it on the PR. Done when the PR
   comment links the commit that records it.

Claude Code runs on the API, so step 4 needs `claude` logged in on the
server; the skill says so up front.

- [ ] **Step 1:** Run the skill tests against the new skill:

  ```bash
  pytest -q tests/test_developer_skills.py tests/test_skill_size.py \
    tests/test_skill_frontmatter.py tests/test_skill_harness_copies.py \
    tests/test_skill_references.py
  ```

  Expected: failures naming each file still to
  update.
- [ ] **Step 2:** Write the skill, its scripts and every update the
  failures name.
- [ ] **Step 3:** Run the full suite with coverage
  (`-n auto`, absolute `PYTHONPATH`, real `config.toml`). Done when it is
  green at 100%.
- [ ] **Step 4:** Commit, together with this plan, and open PR 0 with
  "Closes #1196" and "Part of #1091".

---

## PR 0b: WRITING-STANDARDS becomes four layers

Branch `feat-1091-writing-standards-layers`. Moves text and changes no
rule.

| Layer | Files | Holds |
| --- | --- | --- |
| Core | `docs/WRITING-STANDARDS.md` (same path) | §1–9, §11, §15, §16; the index; precedence; Sources and attribution |
| Elements | `docs/writing-standards/figures.md` (§10), `mathematics.md` (§12, with "Not mathematics" and "Symbols" as `###` under it), `tables.md` (§13), `page.md` (§14) | one file per thing a draft contains, each owned by its `chitragupta/style_*` checker |
| Genres | `docs/writing-standards/genres/<genre>.md` | what the genre owes its reader, its reread checklist, how rare figures and numbered equations are, its §11 unit. PR 0b creates the folder and its README only; PR 1 and later fill it |
| Styles | `docs/writing-standards/styles/README.md` | house styles to come; points at #1181 for the per-draft `style.md`, which stays in the dossier; no style yet |

Rules that keep it from going piecemeal, written into the index:

- **Section numbers are global and never reused.** `figures.md` is still
  §10, and its sub-headings keep their titles, so a citation reads
  `docs/writing-standards/figures.md` §10.
- **The core keeps a stub heading for each moved section**, with its
  emoji, number and title unchanged (`## 📐 10. Figures`), so every
  existing anchor (`#-10-figures`, `#-12-mathematics`) and every
  `WRITING-STANDARDS.md §10` citation still lands on a line that links to
  the new file. One `###` stub is kept as well:
  `### 📖 Symbols: what each mapped symbol means` (WS:836), which
  `docs/book/REGISTRIES.md:103` links to. Citations then move to direct
  paths one PR at a time.
- **Links inside a moved section are rewritten**, because they are
  same-file anchors today: WS:659 and :794 (`(#-10-figures)` inside §12,
  moving to `mathematics.md`) and WS:1076 (`(#-12-mathematics)` inside
  §14, moving to `page.md`) point at the new files.
- **User-facing messages land on stubs until changed.**
  `chitragupta/style_equations.py:105,132` print §12 and
  `style_typeset.py:176,197` print §14, both moved; they still resolve
  through the stub, and change to the new paths in the same PR.
- **Precedence is #1181's, not a new one:** the citekey invariant; the
  venue (`paper.md`, for a research paper); the writing standards, core,
  element and genre files alike, unless a recorded conflict is resolved
  to `profile`; the learnt style. A `style.md` conflict names a section
  by its global number, which the split keeps stable.
- **Each file opens with "Assumes the core, §1–9"**, repeats no other
  file's text, and is at least about 3 KB; a smaller one merges into its
  neighbour. The two folder READMEs are exempt.

### Task 1: a test that every cited section resolves

**Files:**

- Create: `tests/test_writing_standards_layers.py`

- [ ] **Step 1:** Write the tests:
  - `test_every_file_is_in_the_index`: every `.md` under
    `docs/writing-standards/` is linked from the index table in
    `docs/WRITING-STANDARDS.md`.
  - `test_every_cited_section_resolves`: every `§N` or `section N`
    cited after `WRITING-STANDARDS.md` or a `docs/writing-standards/*.md`
    path, anywhere in `.claude/`, `.agents/`, `.opencode/`, `docs/`,
    `chitragupta/`, `AGENTS.md` and `SOUL.md`, names a numbered heading
    in the core or in the named file. Today that is 134 citations in the
    skills' three copies alone, and `style_report.py:33`'s "section 8".
  - `test_every_anchor_resolves`: every `WRITING-STANDARDS.md#<anchor>`
    link names a heading in the core.
  - `test_section_numbers_are_unique`: no number heads two sections
    across the layer files.
- [ ] **Step 2:** Run it against today's single file. Expected: the
  index test fails (there is no index yet), and the other three pass.
- [ ] **Step 3:** Commit.

### Task 2: move the element sections and write the index

**Files:**

- Create: `docs/writing-standards/{figures,mathematics,tables,page}.md`,
  `docs/writing-standards/genres/README.md`,
  `docs/writing-standards/styles/README.md`
- Modify: `docs/WRITING-STANDARDS.md`
- Modify: `tests/test_style_assets_match_the_standard.py` only if the
  section it reads (§2, which stays in the core) moves; expected
  unchanged

- [ ] **Step 1:** Move §10, §12, §13 and §14 verbatim, and demote §12's
  two unnumbered `##` headings to `###`. Leave the stubs, rewrite the
  three in-section links, update the two `style_*` messages, and write
  the index. `tests/test_render_output_math*.py` only name "Not
  mathematics" and read nothing from the file, so they are unaffected.
- [ ] **Step 2:** Run `pytest tests/test_writing_standards_layers.py
  tests/test_style_assets_match_the_standard.py tests/test_skill_table_step.py -q`.
  Done when it is green.
- [ ] **Step 3:** Run the full suite and `mkdocs build --strict`, the
  docs workflow's link check (`.github/workflows/docs.yml:97`). Done
  when both are green.
- [ ] **Step 4:** Bench Tier 1 for all skills on the server
  (`skill-bench`, Tier 1 only). Done when it passes as on main.
- [ ] **Step 5:** Commit, PR with its sub-issue. After merge, comment on
  #1178 and update `plans/1179-research-paper-genre.md`'s "The writing
  rules": research-paper's rules go in
  `docs/writing-standards/genres/research-paper.md`, what only the skill
  needs goes in `research-paper-writer/references/`, and the skill cites
  `genre-steps.md`.

---

## PR 1: the shared genre steps, and survey-writer

Branch `feat-1091-survey-writer`. Before any edit, `skill-bench` has
recorded survey-writer's baseline from `main`.

### Task 1: tests that keep moved text covered and say what may move

**Files:**

- Modify: `tests/test_install_remedies.py:45-58`,
  `tests/test_pdf_requirement_wording.py:18` (scan
  `.claude/skills-common/` too)
- Modify: `tests/test_skill_size.py` (docstring and the
  `test_each_copy_is_under_its_cap` message: "move prose to references/;
  commands stay in SKILL.md")

- [ ] **Step 1:** Make the changes. Run both remedy tests. Done when they
  pass, now covering `skills-common/`.
- [ ] **Step 2:** Commit.

### Task 2: `genre-steps.md`

**Files:**

- Create: `.claude/skills-common/references/genre-steps.md`

Seven numbered sections, all cited by survey-writer in Task 4, none
naming a step number, a skill or a command:

| § | Title | From (survey step unless noted) |
| --- | --- | --- |
| 1 | The corpus is read-only | the read-only paragraph all four share; the ledger and parsed bullets |
| 2 | What the dossier is for | "owns that state", "half of what this run produces" |
| 3 | Opening the dossier | slug, `scope.md`, dialect, acronyms, fingerprint, with a generic `<topic>/<genre>.<ext>` example |
| 4 | Following an `outline.md` | survey 1, thesis 2; one sentence for genres where citing is optional: a `claim:` block is a steer |
| 5 | Judging a candidate and recording it | survey 2: the `evidence.md` and `rejected.md` formats, the `check-evidence` warnings |
| 6 | Thin results and disagreement | survey 3 and 5 |
| 7 | Stamping and handing over | what the fingerprint means, why the dossier is gitignored, why export |

The figure section the comparison proposed is not here: what it held is
`docs/writing-standards/figures.md` §10 ("Every figure has two forms",
"What the pair requires", "A caption, and no number you write
yourself"), so skills cite that. A section for LaTeX fragments (thesis
now, research-paper later) is left for the PR that needs it twice.

- [ ] **Step 1:** Write the file. Its first line is distinct from every
  other reference's, because Tier 1 scores a read by it.
- [ ] **Step 2:** No commit yet: `tests/test_skill_references.py`
  fails on an uncited section until Task 4 cites it, so Tasks 2–4 land
  as one commit.

### Task 3: `survey-writer/references/survey.md` and `genres/survey.md`

**Files:**

- Create: `.claude/skills/survey-writer/references/survey.md`
- Create: `docs/writing-standards/genres/survey.md`
- Create: `plans/1091-ledger-survey-writer.md`, the move ledger

What goes where:

| Text in survey-writer today | Goes to |
| --- | --- |
| "What a survey owes its reader"; the reread checklist (step 14); how rare figures are and when an equation is numbered (step 9's last two paragraphs) | `genres/survey.md` |
| Step 2a's rationale (the dispatch sentence stays: it is a harness phrase); the comparison table and gap analysis beyond what `tables.md` §13 holds; the sidecar choice (step 13); Sources' detail | `survey.md` §1–§4 |
| Shared corpus layer, the dossier, steps 0, 1, 2, 3, 5, 18 | citations of `genre-steps.md` |
| Step 6's multi-source rule, step 9's pair and caption rules | citations of WRITING-STANDARDS §11 and `figures.md` §10 |
| When to invoke | one line naming the sibling skills; the description already routes |

The ledger lists every paragraph removed from `SKILL.md`, one row each:
its first words, where it went (file and §), or "cut" with the reason
(a duplicate of X, a restatement of `--help`, history). A row with no
destination fails review.

- [ ] **Step 1:** Write both files and the ledger. No commit yet (see
  Task 2).

### Task 4: the new survey-writer `SKILL.md`, in all three copies

**Files:**

- Modify: `.claude/skills/survey-writer/SKILL.md`,
  `.agents/skills/survey-writer/SKILL.md`,
  `.opencode/skills/survey-writer-opencode/SKILL.md`
- Modify: `tests/test_skill_size.py` (`"survey-writer": (<cap>, None)`,
  with the cap at or under 12,000)

Each step keeps: its title, its commands and fences, the literals a
test reads, its judgement call in one or two sentences, a conditional
pointer, and `Done when`.

**The tests define what must stay, not this plan.** Before rewriting,
list every pinned phrase, window and absence for survey-writer from
`tests/test_skill_references.py`, `tests/test_skill_harness_copies.py`
(including `:140-144`, every phrase-map entry survives in some copy),
`tests/test_skill_figure_step.py` (including the six `_RIDERS` at
`:25-32`, which must stay *absent*), `tests/test_skill_table_step.py`,
`tests/test_skill_acronym_step.py`,
`tests/test_skill_pregate_feedback_step.py` (`:86-130`, `:174-182`,
`:211-378`), `tests/test_skill_style_check_step.py` (`:62-65`, `:87`,
`:128-168`), `tests/test_skill_verbatim_scan_step.py` (`:80-139`,
`:168-287`) and `tests/test_skill_retrieval_logging.py`, and put the
list at the top of the move ledger. Note for each whether the test reads
the raw file or `expanded()`: only a phrase read through `expanded()`
may move into a cited reference.

- [ ] **Step 1:** Rewrite the `.claude` copy. Merge only tail steps 14 and
  15 (reread, record steering); steps 1, 2, 2a, 9 and 10 keep their
  numbers.
- [ ] **Step 2:** Port to the other two copies, keeping every phrase-map
  difference. Run `pytest tests/test_skill_harness_copies.py -q`. Done
  when it is green.
- [ ] **Step 3:** Lower the cap. Run `pytest tests/test_skill_*.py
  tests/test_init.py tests/test_tikz_scaffolds.py -q`. Done when it is
  green and all three copies are at or under 12,000 bytes.
- [ ] **Step 4:** Commit.

### Task 5: docs, step references and the bench

**Files:**

- Modify, where they name a survey step that moved or merged:
  `docs/TOKENS.md`, `docs/DRAFT-ITERATION.md:187`, `docs/PROMPTS.md`,
  `docs/VERBATIM-DIGEST.md:112-121` (by name), `chitragupta/review/_claims.py:30`,
  `.claude/skills/{draft-reviser,corpus-reviser,review-digest}/SKILL.md`
  (all copies)
- Modify: `docs/GENRE.md:456-460` and `DEVELOPER.md:323-324`, the two
  lists of shared references: both gain `genre-steps.md`, and
  DEVELOPER.md's, which names only four of the eight today, catches up
- Modify: `pyproject.toml` (patch bump)

- [ ] **Step 1:** Update every reference, then run
  `grep -rn "survey-writer.*step\|step [0-9]*.*survey" docs chitragupta .claude`
  and check each hit. Done when every hit names the right step.
- [ ] **Step 2:** Run the full suite with coverage. Done when it is green
  at 100%.
- [ ] **Step 3:** Push and open PR 1 with "Part of #1091". On the
  server, `skill-bench` for survey-writer. Done when `--compare` exits 0
  and its table is on the PR and in `docs/HARNESS.md`.
- [ ] **Step 4:** Fable-model review, then merge.

---

## PR 2: textbook, thesis and tutorial

Branch `feat-1091-genre-writers`. Same pattern as PR 1 Tasks 3–5, once
per skill, with these differences. Baselines for all three come from
`main` before the branch starts.

### Task 1: settle the two inconsistencies first

**Files:**

- Modify: `.claude/skills/figure-drawer/references/placement.md` §4
- Modify: `.claude/skills/tutorial-writer/SKILL.md` step 9 (all copies)

- [ ] **Step 1:** `placement.md` §4 says the pdf render is LuaLaTeX with
  `chitragupta-lualatex.tex` (#1037), as thesis step 9 does, and carries
  the `\resizebox` note (#1046); `chitragupta-unicode.sty` is named only
  where it still applies. Run `pytest tests/test_skill_figure_router.py
  tests/test_figure_rule_ids.py -q`.
- [ ] **Step 2:** Tutorial step 9 loses "most of this genre's rare
  figures need no caption at all": every figure has a caption, as
  `figures.md` §10 and `FigureNoCaption` (#421) say.
- [ ] **Step 3:** Commit.

### Task 2: textbook-chapter-writer

- Coordinate with the TB epic (#1128): TB-2 to TB-6 (#1130–#1134) and
  TB-11 (#1139) add to this skill. Whichever lands second rebases onto
  the first; TB-5's planned `references/exercise-types.md` stays a
  topical file of its own beside `textbook.md`.
- Writing rules to `genres/textbook.md`: Audience first, House style for
  this genre, the reread (step 9), figure and equation density.
- Own reference `textbook.md`: objectives and motivation (steps 1–3),
  section-level source diversity beyond §11 (step 4), worked examples
  and exercises (steps 5–6), thin evidence and pedagogical rejects (the
  dossier section), the thin sidecar (step 14).
- Steps 1–8 each keep their title, check, one judgement sentence and
  `Done when`. Step 4 keeps its number.
- "Read `.claude/skills-common/references/mathematical-prose.md` now"
  stays verbatim (`tests/test_skill_references.py:128-136`).

### Task 3: thesis-chapter-writer

- Writing rules to `genres/thesis.md`: what a thesis chapter owes, the
  examiner reread (step 13), equation density.
- Own reference `thesis.md`: the LaTeX carve-outs for tables, figure
  floats and equations; `provenance.json` (step 7); the previews,
  sidecar and absent References section (step 12); step 9's two
  `text` output samples.
- Step 9's three preamble bullets become a citation of `placement.md`
  §4 (Task 1). Steps 9 and 12 keep their numbers. `%figure:
  figures/<name>` stays and the Markdown marker stays absent
  (`tests/test_skill_figure_step.py`); `\label{tab:` and
  `Table~\ref{tab:` stay (`tests/test_skill_table_step.py`).
- Update `docs/RENDERING-FLOW.md:223,535` if either step's wording
  changes what they quote.

### Task 4: tutorial-writer

- Writing rules to `genres/tutorial.md`: the writing half of "What this
  genre is not", Self-check, the beginner reread (step 10).
- Own reference `tutorial.md`: task analysis and front matter (2–3),
  writing the steps (4), "Where to go next" and its citing (6), verifying
  it runs (8), why there is no sidecar (15).
- "Run it" (step 8) keeps its commands and its `Done when`: the lesson
  ran start to finish.

### Task 5: close PR 2

Tail merges: thesis merges its reread (13) and "Record any steering"
(14), which are adjacent, as survey does with 14 and 15; its later steps
renumber, and `:306`'s "step 12" is before them and stays. Textbook and
tutorial merge nothing: their reread sits mid-process (textbook 9,
tutorial 10), away from steering, so their internal references
(textbook `:315` "step 14", tutorial `:361` "step 15") stay valid.

- [ ] **Step 1:** Each skill at or under 12,000 bytes in all three
  copies; caps lowered with reason `None`. A skill that real
  deduplication leaves above 12,000 goes back to the user (Decision 1).
- [ ] **Step 2:** Update `docs/WRITING-STANDARDS.md:561`,
  `chitragupta/review/synthesis.py:48`, `chitragupta/review/_units.py:22`
  and `docs/PROMPTS.md:76` ("19-step") where a step changed.
- [ ] **Step 3:** Full suite at 100%; `skill-bench` for all three, each
  `--compare` exiting 0; results on the PR and in `docs/HARNESS.md`.
- [ ] **Step 4:** Fable-model review, merge, then comment on #1178: cite
  `genre-steps.md`, write the rules in `genres/research-paper.md`, add
  the skill to `GENRES` in `tests/test_skill_size.py`, start at or under
  12,000 bytes.

---

## PRs 3–8, in outline

Each follows PR 1's pattern: a move ledger, writing rules to
`docs/writing-standards/`, the skill's own text to its single reference,
citations of shared files, `Done when` on every step, `skill-bench`
before and after, the cap lowered. Each gets its detailed section in
this file when it starts.

| PR | Skill | Target | Must also |
| --- | --- | --- | --- |
| 3 | review-digest | 12,000 (it is now survey-shaped, #1173; add it to `GENRES`) | restore all six passages noted on #1091: the `python -m chitragupta.review support` command and "Never guess a key, never rewrite one." in `SKILL.md`; the figures-not-a-precondition note, the render path, "Pandoc-style citations only" and "the page is a hint" in `SKILL.md` or `digest-copying.md`. Fix `:121`'s "same steps as survey-writer" and `:223`'s step reference |
| 4 | draft-reviser | 8,000; floor is about 5.3 KB, so a reason is likely | decide whether it cites `mathematical-prose.md` |
| 5 | agenda-reviser | 8,000 | — |
| 6 | book-assembler | 8,000 | settle the four "the conventions say" pointers #1158 and #1170 left (`SKILL.md:150`, `:158`, `:230`, `:354`; `:150` is a whole step, the other three are asides): each states when to read the conventions, and record the trims #1170 made only in `plans/1168-book-index.md`. Build the shared book-steps reference in the shape #1157 (edited volume) needs, so that skill cites it rather than writing a second one |
| 7 | corpus-reviser | 8,000 | — |
| 8 | deep-research | 8,000; floor about 6.4 KB, likely 10–12 KB with a reason | decide whether it cites `mathematical-prose.md`; consider splitting phases across its subagent boundary; `Closes #1091`; then the MINOR release |

Separate from this series: demo-recorder's install table lost its
manual sources in #1190; #1206 restores them.

## After the series

The front-matter descriptions (about 1,000 characters each, all loaded
in every session) are the next lever, measured with `skill-bench`
before any change. That is a new issue, opened when PR 8 merges.

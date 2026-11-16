# Shrinking every skill to its budget, by deduplication (#1091)

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [x]`) syntax for tracking.

Status: **built.** Every PR of the series is merged; "How it ended"
below has what each became, where the plan was wrong, and what is left
open.
Written 2026-11-13 against `9aa75085`
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
- a Fable-model review of this plan, all 17 findings applied;
- PR 0's Tasks 1-3, built on the A40 server (2026-11-13, inline
  execution) on `feat-1091-skill-bench` at 6.173.0 (MINOR: a script and
  a developer skill, `DEVELOPER-AGENTS.md:1149-1151`), with a
  whole-branch review whose 1 critical and 6 important findings were
  fixed test-first;
- the first baseline of every user skill on all three harnesses,
  `bench/results/2026-11-13-skill-bench-baseline/`, written up in
  `docs/HARNESS.md` ("Measuring a skill change");
- #1210, for the two local harnesses' noise that baseline found.

Where PR 0 was built differently from the tasks below, each task says
so under **As built**. The A40 host already has the pinned tools under
`~/bench-tools/`; `install_tools.sh --check` confirms them.

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

## Decisions (user, 2026-11-11 to 11-14)

1. **The byte cap is a guard, not the goal.** The goal is deduplication
   and one wording per rule. The targets are 12,000 bytes for a genre
   writer and 8,000 for any other skill. Never compress prose to fit:
   that is how #1173 lost six passages
   ([noted on #1091](https://github.com/prasadtalasila/chitragupta/issues/1091#issuecomment-6849659277)).
   Where the two pull apart, no compression wins: a genre writer that
   real deduplication leaves above 12,000 stops and goes back to the
   user before its PR opens; any other skill records the reason in its
   cap row.
   **Answered for survey-writer, 2026-11-14:** the cap is a guideline.
   The goal is less duplication and better compliance, so a skill that
   real deduplication leaves above its target keeps that size, records
   the reason in its cap row, and does not stop its PR.
2. **Commands stay in `SKILL.md`** (#1091 item 3): every
   `python -m chitragupta...` line, every marker a draft must carry, and
   every phrase a test reads from the raw file. Output samples (the
   `text` fences in thesis step 9) may move. **Two steps are measured
   exceptions**, whose commands live in a shared reference behind a
   pointer: the render step (`render-and-references.md`, measured
   2026-10-30 to 11-02), and the critique loop (`critique.md`), decided
   2026-11-15 on PR 0c's result for the four genre writers and
   deep-research. A critique step moves in its own skill's PR, benched
   for that skill. Its pointer says the step is not done until the loop
   the reference describes has run, and
   `tests/test_skill_pregate_feedback_step.py`'s `_POINTER_FORM` lists
   the skills that have moved. survey-writer moved first.
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
    CPU host with one slot. The baseline showed that only Claude Code is
    steady enough at 3 runs to gate on, so the shrink PRs gate on
    Claude Code alone (user, 2026-11-14) and report Codex and OpenCode
    as advisory until #1210 steadies them.
11. **Shared procedures: a pointer or a skill handoff? Measured first**
    (user, 2026-11-14). Decision 5 sends procedure the genre writers
    share to `.md` files behind "read this now and follow it" pointers.
    The repository already has a second way to share a procedure: a
    genre writer hands a step to another skill and takes it back, as all
    four do with `figure-drawer`. The question is whether that handoff
    should carry shared *procedures* instead of pointers. It is settled by
    an experiment, PR 0c, before PR 1 starts. **Rule:** if the handoff
    arm does not fail against the inline arm, the four `skills-common`
    procedures the genre writers call with "Read ... now and follow it"
    (critique, render-and-references, prose-check, verbatim-scan) and
    the procedural sections §3 and §7 of the planned `genre-steps.md`
    become skills, and only writing rules stay as `.md`. If it fails,
    this plan stands as merged. Writing rules stay in `docs/` either way.

## The series

| PR | Issue | Scope | Version |
| --- | --- | --- | --- |
| 0 | #1196 SK-0 | this plan, `skill-bench`, bench `--source`, `--jobs`, `--base-url`, `--runs`, per-command scoring, `--compare` | minor (a new script, `DEVELOPER-AGENTS.md:1149-1151`; #1189 did the same) |
| 0b | #1197 SK-0b | `docs/WRITING-STANDARDS.md` split into `docs/writing-standards/` | patch |
| 0c | #1213 SK-0c | experiment: survey-writer's critique step inline, as a pointer, and as a handoff to a new `critique-loop` skill; the bench scores handoffs; decides Decision 11 | patch (the bench rule and this plan; the arm branches are never merged) |
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
- A shared reference names no skill, no harness tool and no step
  number of a step that points at it. A reference that holds a
  procedure numbers its own steps, ends each on a `Done when`, and
  returns to the step that sent the reader. A command a step requires
  stays in that step's `SKILL.md`, except in the steps Decision 2
  names; a reference may also repeat a command its caller carries.
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
   their 1,400, 2,000 or 6,800-character windows. Pinned by running
   `tests/test_skill_pregate_feedback_step.py`,
   `tests/test_skill_style_check_step.py` and
   `tests/test_skill_verbatim_scan_step.py` in PR 1 Task 5 and PR 2.
   No citation goes inside those three steps. A critique step in the
   pointer form (Decision 2) is read whole, the step and then the
   reference, so a spliced reference cannot push its riders out of a
   window.
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

    **As built** (`bench/skill_bench_tasks.py`): figure-drawer has a task
    too (a second figure on the survey, after survey-writer), so every
    user skill is covered. Each prompt pre-answers its skill's questions
    and asks for the branches the five-paper corpus can reach (an outline
    on one genre, sub-themes on another, a figure, a numbered equation,
    steering, the render with its sidecar, the prose check, the verbatim
    scan, the stamp). The revisers start from a fresh `dt/survey` and a
    `seed` hook then plants the defects their branches exist for (US
    spellings and an unstamped section for draft-reviser, which converts
    to en-GB; short unquoted source runs and prose findings for
    agenda-reviser). review-digest syncs with Docling for its passage
    sidecars; book-assembler accepts a second chapter so the book
    composes. Local jobs take a server from a queue, one job a server.
    survey-writer's task has its own prompt, not `TIER2_SURVEY` (which is
    gone). Every task's prompt is a body (the answers and what the user
    wants) and a tail naming the closing steps; `--skill-only` drops the
    tail for every task, and that is the arm a shrink is gated on, since
    a prompt that names a step masks a skill that stopped asking for it
    (Fable review of PR 0).

- [x] **Step 1:** Add the four flags, the `USER_SKILLS` default and
  `TIER2_TASKS`. Write each new prompt in the shape of `TIER2_SURVEY`:
  the skill named, its input, "follow the skill through to the end,
  including its self-check with draft gate". For book-assembler, check
  that `twin-basics`' units carry acceptance records; if not, the task
  scaffolds them as the fixture, never by editing the example.
- [x] **Step 2:** `self_check()` gains a check that `--source` points at a
  directory holding `chitragupta/init.py`, and that `--jobs` above
  `len(--base-url)` warns that jobs will share a server slot.
- [x] **Step 3:** Run `python bench/bench_skill_harnesses.py --tier 1
  --harness claude --skill survey-writer --source .`. Done when it
  prints `tier 1: 1/1 passed`.
- [x] **Step 4:** Commit.

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

  **As built** (`bench/skill_commands.py`; `docs/HARNESS.md`, "Measuring
  a skill change", owns the rule and its arithmetic):
  - The rule above would fail an unchanged skill most of the time
    (`docs/HARNESS.md` has the numbers). So 3 runs only screen: at
    3 against 3 a row fails only when it went all the way the wrong way
    (a command or the gate in every before run and no after run, a
    forbidden command in no before run and every after run), and any
    other move is inconclusive; 6 against 6 fails on a move of 4 or
    more and passes otherwise. The gate and forbidden rows follow the
    commands' rule.
  - Expected commands come from `SKILL.md` and every file it names, in
    the harness's own folder, since survey-writer's render step already
    lives only in a reference; `--compare` counts from every command a
    run executed, so a command a shrink moves out still counts.
  - A command is `module sub [sub]`, its subcommands read from the
    module's own `--help`. `FORBIDDEN` is `corpus sync` and `enrich`
    (`corpus enrich` is not a command).
  - A run counts a command only in command position: never a `grep`,
    an `echo`, a heredoc body or a `--help` call.
  - Runs that timed out, raised, or started from a prerequisite that
    never passed its gate are left out; an arm with fewer than 3 usable
    runs is inconclusive; a (harness, skill) in one arm only is skipped.
  - Two Tier 1 scorer bugs were fixed on the way: a first line ending
    in a backtick, and a path printed absolute, had failed 9 real reads
    of 14 measured failures.

- [x] **Step 1:** `self_check()` gains five cases, checked on a fixture
  `SKILL.md` string and fixture JSONL transcripts: a fenced and an inline
  command are both found; `python -P -m` matches like `python -m`; a
  command named in the skill but absent from the tool calls lands in
  `missed`; `corpus sync` named in the skill is not `expected`; and
  `--compare` on 3-vs-3 fixtures gives pass for an equal pair,
  inconclusive for a one-run drop and fail for a 3-to-0 drop.
- [x] **Step 2:** Implement `expected_commands`, the result fields and
  `--compare`.
- [x] **Step 3:** Run `python bench/bench_skill_harnesses.py --compare
  a.json a.json` on any recorded `tier2.json`. Done when it exits 0 and
  prints every command as unchanged.
- [x] **Step 4:** In `docs/HARNESS.md`, record the pass rule and why a
  one-run drop is not a failure at 3 runs. (As built: the rule changed,
  see above; `docs/HARNESS.md` records the rule actually used and its
  arithmetic.)
- [x] **Step 5:** Commit.

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
  `--base-url` arguments for the bench. **As built:** `serve_models.sh
  N [FIRST]` takes GPUs FIRST..FIRST+N-1, runs the servers detached so
  they outlive a long baseline, and `--stop` ends them.

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

- [x] **Step 1:** Run the skill tests against the new skill:

  ```bash
  pytest -q tests/test_developer_skills.py tests/test_skill_size.py \
    tests/test_skill_frontmatter.py tests/test_skill_harness_copies.py \
    tests/test_skill_references.py
  ```

  Expected: failures naming each file still to
  update.
- [x] **Step 2:** Write the skill, its scripts and every update the
  failures name.
- [x] **Step 3:** Run the full suite with coverage
  (`-n auto`, absolute `PYTHONPATH`, real `config.toml`). Done when it is
  green at 100%.
- [x] **Step 4:** Commit, together with this plan, and open PR 0 with
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

- [x] **Step 1:** Write the tests:
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
- [x] **Step 2:** Run it against today's single file. Expected: the
  index test fails (there is no index yet), and the other three pass.
- [x] **Step 3:** Commit.

### Task 2: move the element sections and write the index

**Files:**

- Create: `docs/writing-standards/{figures,mathematics,tables,page}.md`,
  `docs/writing-standards/genres/README.md`,
  `docs/writing-standards/styles/README.md`
- Modify: `docs/WRITING-STANDARDS.md`
- Modify: `tests/test_style_assets_match_the_standard.py` only if the
  section it reads (§2, which stays in the core) moves; expected
  unchanged

- [x] **Step 1:** Move §10, §12, §13 and §14 verbatim, and demote §12's
  two unnumbered `##` headings to `###`. Leave the stubs, rewrite the
  three in-section links, update the two `style_*` messages, and write
  the index. `tests/test_render_output_math*.py` only name "Not
  mathematics" and read nothing from the file, so they are unaffected.
- [x] **Step 2:** Run `pytest tests/test_writing_standards_layers.py
  tests/test_style_assets_match_the_standard.py tests/test_skill_table_step.py -q`.
  Done when it is green.
- [x] **Step 3:** Run the full suite and `mkdocs build --strict`, the
  docs workflow's link check (`.github/workflows/docs.yml:97`). Done
  when both are green.
- [x] **Step 4:** Bench Tier 1 for all skills on the server
  (`skill-bench`, Tier 1 only). Done when it passes as on main.

  **Tier 1 does not yet see this move.** On `main` it scores only the
  files a `SKILL.md` names under `.claude/skills` (`NAMED_PATH`, and the
  Tier 1 prompt asks for exactly those), and every file PR 0b creates
  or splits is under `docs/`. So Tier 1 would pass PR 0b without testing
  whether a model follows a `docs/writing-standards/` citation. It is
  being extended to score the `docs/` files a skill names as well, on
  branch `feat-1091-tier1-docs-reads` (2026-11-14), and Step 4 runs with
  that extension, on `main` and on this branch alike. Until it merges,
  a Tier 1 pass here says nothing about the moved sections.
- [x] **Step 5:** Commit, PR with its sub-issue. After merge, comment on
  #1178 and update `plans/1179-research-paper-genre.md`'s "The writing
  rules": research-paper's rules go in
  `docs/writing-standards/genres/research-paper.md`, what only the skill
  needs goes in `research-paper-writer/references/`, and the skill cites
  `genre-steps.md`.

---

## PR 0c: does a skill handoff hold a mandatory step?

Branch `feat-1091-routing-experiment` (this plan's section and the
bench rule below). Runs before PR 1, because its result decides what
PR 1 builds (Decision 11). Issue #1213.

**What is already known.** With survey-writer's critique step cut to
"read `critique.md` and follow it", one Claude Code run skipped the step
outright: no baseline, no recheck, no `revisions.md` entry
(`docs/HARNESS.md`, "Only `SKILL.md` is per harness"). That is one run,
and it is why every genre writer keeps the loop's commands inline. A
mandatory step handed to another skill has never been measured: the
only handoff in use, to `figure-drawer`, is a step the genre writers
reach because the task asks for a figure.

**What a skill costs that a reference does not:**

- three `SKILL.md` copies, kept in step by
  `tests/test_skill_harness_copies.py`;
- a phrase-map entry for every harness-specific phrase it carries;
- a row in `.opencode/opencode.json`'s deny list, which
  `chitragupta doctor` checks;
- a frontmatter description that every harness loads in every session,
  whether or not the skill runs (Decision 7 leaves descriptions alone
  until they can be measured; a new skill adds one);
- on Codex, nothing a reference does not already cost the model: Codex
  has no skill tool, so a handoff there is a read of
  `.agents/skills/<name>/SKILL.md`, as a pointer is a read of a `.md`.

What it buys: a skill may name harness tools and other skills, which a
shared reference may not (`tests/test_skill_references.py`), so a
phrase such as `critique_edit_tool` could live in the one skill that
needs it instead of in every caller.

### The three arms

Each arm is a branch off the same `main` commit, and only survey-writer's
step 10 (the pre-gate self-feedback loop that
`tests/test_skill_pregate_feedback_step.py` pins) differs between them.

| Arm | Branch | Step 10 holds | Where the loop's commands are |
| --- | --- | --- | --- |
| inline | `main` | the loop's commands, as today | `SKILL.md`, all three copies |
| pointer | `exp-1091-critique-pointer` | a pointer at an `.md` reference | that reference, once under `.claude/` |
| handoff | `exp-1091-critique-handoff` | a handoff to a new skill that runs the loop and returns | `critique-loop` (`critique-loop-opencode` in the OpenCode copy), three copies |

The arm branches are built elsewhere and are never merged; the step-10
tests fail on them by construction, since the commands leave the step.
The handoff arm words its step the way the genre writers word the
figure handoff ("Hand ... to `critique-loop`, and come back to this
step"), because that is the sentence the bench follows (below).

### Files on this branch

- Modify: `bench/skill_commands.py`: `HANDOFF`, `handoffs`,
  `handed_off`, `skill_files`
- Modify: `bench/bench_skill_harnesses.py`: `score_run` (Tier 2 only),
  `skill_load`, and their `self_check()` cases; the Tier 1 path is not
  touched (`feat-1091-tier1-docs-reads` changes it)
- Modify: `bench/README.md`, `docs/HARNESS.md` ("Measuring a skill
  change")
- Modify: this plan

### The bench rule: a handoff's commands are expected

Without it the bench could not score the handoff arm: `expected` held
the commands of a harness's `SKILL.md` and of the files it names by
path, so a step moved into another skill would leave the expected set.
`--compare` would still count the commands (it counts every command a
run executed, `ran_all`), but only for keys some arm expected.

- **The rule.** A sentence that hands something to `` `<skill>` `` and
  says "and come back" is a handoff, when `<skill>` is a folder in the
  same harness's skills folder. That skill's commands, and those of the
  files it names, are expected of the caller, and so on for any skill
  it hands to in turn. The OpenCode copies write the suffixed name,
  which is the folder looked up, so no suffix logic is needed.
- **Why so narrow.** A skill that only names a sibling ("use
  `draft-reviser` instead", "Hand off to `corpus-reviser`", "drawn
  through `figure-drawer`") must not take on its commands, or every
  skill's expected set would grow by its siblings' steps and the
  recorded baselines would change meaning. The return clause is what
  separates a sub-procedure from a route away.
- **What it changes on `main`'s skills**, computed for every user skill
  on every harness before and after: the four genre writers gain 5
  commands each (`draft figures`, `figure new`, `figure sync`,
  `figure check`, `figure look`) and draft-reviser 4 (it already named
  `draft figures`), on all three harnesses, from their `figure-drawer`
  handoffs. No other set changed. Comparing a new arm against the
  recorded baselines in `bench/results/` stays sound, because those rows
  carry `ran_all` and `--compare` judges the union of both arms'
  expected sets; re-scoring the 2026-11-14 skill-only rows with the new
  sets and comparing them with the originals passes. The "Named
  commands run" share in `docs/HARNESS.md` was taken over the old sets.
- **Whether the run loaded the skill** is recorded per run as
  `handoffs_loaded`: `"skill"` (Claude Code's `Skill` or OpenCode's
  `skill` tool named it), `"read"` (a tool call opened that harness's
  copy of its `SKILL.md`), or `null`. Codex can only show `"read"`. In
  the 36 recorded Claude Code genre-writer transcripts, `figure-drawer`
  was loaded by reading its `SKILL.md` in 22 and through `Skill` in 14,
  so a Claude Code handoff is not always a `Skill` call either.

### Running it

Bench code from this branch for all three arms, `chitragupta` from the
same venv, Claude Code only, the skill-only prompt (survey-writer's
task names no critique step even in its full prompt, so only the skill
can make a model run it), 6 runs an arm, all three arms on the same
day:

```bash
for arm in inline pointer handoff; do
  python bench/bench_skill_harnesses.py --tier 2 --skill survey-writer \
    --harness claude --skill-only --runs 6 --jobs 6 \
    --source <worktree of that arm> --out <dir>/$arm
done
python bench/bench_skill_harnesses.py --compare \
  <dir>/inline/tier2.json <dir>/pointer/tier2.json
python bench/bench_skill_harnesses.py --compare \
  <dir>/inline/tier2.json <dir>/handoff/tier2.json
```

The inline arm is run fresh rather than reusing the 2026-11-14
skill-only rows, which have 3 runs and were scaffolded from an older
`main`.

### What is measured, and what is not

- **Measured:** for each run, whether each command key ran at least once,
  whether the draft passed the gate, timeouts and errors, and, on the
  handoff arm, how `critique-loop` was loaded.
- **Not seen by the per-command rows:** most of step 10's commands
  (`draft dossier sections`, `review verbatim scan`, `draft style`,
  `draft gate`) also run in steps 11, 16 and 17, so a run that skips step
  10 still runs them, and `draft dossier status` runs only when the
  dossier has an `outline.md`, which the task does not give it. The one
  key only step 10 runs is `review verbatim recheck`, and only once a
  repair is attempted. In the recorded Claude Code survey runs it ran in
  3 of 3 skill-only runs and 4 of 6 full-prompt runs. So the verdict
  rests on that row, the gate and the clock.
- **Read by hand, recorded beside the verdict, never a gate:** whether
  each run's dossier `revisions.md` holds a critique entry, and whether
  the baseline (`review verbatim scan --write`) ran before the first
  recheck. Both sit in the run's project under `--out`.
- **Not measured at all:** Codex and OpenCode (advisory everywhere in
  this series, #1210, and not run here); a handoff the task does not
  ask for anywhere but the skill, in any genre but the survey; and the
  description cost of a new skill.

### The decision

- **`--compare` inline vs handoff exits 0:** the handoff holds. Decision
  11's first branch applies, and PRs 1-8 change as below.
- **It exits 1:** the handoff dropped the step. This plan stands as
  merged; `critique-loop` is not built; the result is recorded in
  `docs/HARNESS.md` beside the 2026-10 pointer finding.
- **It exits 3:** at 6 against 6 that comes only from fewer than 3
  usable runs, mixed prompts or a single new timeout. Rerun what was
  left out and compare again; read it as neither outcome.

The inline vs pointer comparison is recorded with it. It does not enter
the rule: it says whether the 2026-10 single-run skip reproduces at 6
runs.

**If the handoff holds, what changes in PRs 1-8:**

- Decision 5's table gains a row: a procedure several skills run is its
  own skill, handed to and taken back. `skills-common/references/`
  keeps only what is not a procedure.
- Decision 2 reads "every command stays in a `SKILL.md`": the called
  skill's, not necessarily the caller's.
- PR 1: `genre-steps.md` keeps §1, §2, §4, §5 and §6; §3 (opening the
  dossier) and §7 (stamping and handing over) become skills. The
  critique, render-and-references, prose-check and verbatim-scan
  procedures become skills, each with its three copies, deny-list row,
  phrase-map entries (`critique_edit_tool` moves into the critique
  skill), cap in `tests/test_skill_size.py`, `pyproject.toml` include
  lines, and frontmatter count. survey-writer hands steps 10, 12-13, 16
  and 17 to them, and the dossier opening and the stamp to the two
  `genre-steps.md` skills; the step numbers stay (Decision 6).
- PR 1 Task 4: the step tests that read a step's riders
  (`tests/test_skill_pregate_feedback_step.py`,
  `tests/test_skill_style_check_step.py`,
  `tests/test_skill_verbatim_scan_step.py`) follow the handoff into the
  called skill instead of `expanded()`'s spliced references; review
  focus 1 changes with them.
- The bench: each new skill joins `USER_SKILLS`, so it needs a Tier 2
  task or an exemption like `figure-drawer`'s, and the
  `TIER2_TASKS`-covers-`USER_SKILLS` check in `self_check()` widens to
  match; `docs/FEATURES.md`'s skill count moves with
  `tests/test_features_doc.py`.
- PRs 2-8: every skill that names one of the four references today
  hands off to its skill instead: textbook, thesis, tutorial and
  deep-research all four; review-digest prose-check; draft-reviser,
  corpus-reviser and book-assembler prose-check and verbatim-scan;
  agenda-reviser verbatim-scan (counted on `main` at `9cbaf678`).
- PR 0b is unchanged: writing rules stay in `docs/` either way.

**If it fails:** nothing in PRs 1-8 changes.

- [x] **Step 1:** The bench rule, `handoffs_loaded`, their
  `self_check()` cases, and the docs. Done when the self-check passes
  and the before/after expected sets differ only as listed above.
- [x] **Step 2:** File the issue; put its number in the series table.
- [x] **Step 3:** With both arm branches built, run the three arms and
  both comparisons on the server. Done when both `--compare` outputs,
  each run's `handoffs_loaded` and the hand-read `revisions.md` check are
  recorded in `docs/HARNESS.md` and on the issue. (As run: recorded
  under "Result" below, with the rows in `bench/results/`.)
- [x] **Step 4:** Apply the decision to this plan (the list above), and
  only then start PR 1.

### Result, 2026-11-14

Run in a cloud container, not on the A40 server: Claude Code only
(`claude -p --model sonnet`, as the bench launches it), 6 skill-only
survey-writer runs an arm, 3 at a time, all three arms at once, each
capped at 3600 seconds. The inline arm is `9cbaf678`; the arms are
`exp-1091-critique-pointer` (`0f3cd674`) and
`exp-1091-critique-handoff` (`a4a2eae3`). The rows, rescored with this
branch's bench, are in
`bench/results/2026-11-14-skill-handoff-experiment/`.

| | Inline | Pointer | Handoff |
| --- | ---: | ---: | ---: |
| Usable runs, none timed out | 6 | 6 | 6 |
| Gate passed | 6 | 6 | 6 |
| Reached the loop's text | 6 (read `critique.md`) | 6 (read the reference) | 6 (5 by the skill tool, 1 by reading its `SKILL.md`) |
| `revisions.md` has a critique entry | 6 | 6 | 6 |
| `review verbatim recheck` ran | 5 | 5 | 5 |
| Baseline scan before the first recheck, where one ran | 5 of 5 | 5 of 5 | 5 of 5 |
| `draft dossier status` ran | 6 | 4 | 5 |
| Median run | 414 s | 350 s | 368 s |

Both comparisons exit 0. Every other command row is equal across the
arms or moves within the rows only a branch reaches
(`draft dossier outline` 3, 1, 1; `review synthesis` 2, 3, 3).

**What it shows.** The handoff held the step in 6 of 6 runs. So did
the pointer: the 2026-10 single-run skip did not reproduce at 6 runs
with a pointer step that says the step is not done until the loop has
run. On this evidence the handoff is no more reliable than the pointer
on Claude Code, and it costs what "What a skill costs" lists. The
decision rule above was written expecting the pointer to be the weaker
arm, so its first branch is met in letter and its premise is not.
Step 4 therefore went to the owner.

**Decided, 2026-11-15.** Shown these results and the Codex and
OpenCode runs below, the owner said to proceed with the merges on the
conclusion that this plan stands as merged: shared procedures move
behind `.md` pointers, `critique-loop` is not built, and PRs 1-8 do
not change. A pointer removes the same duplicate text as a handoff,
holds the step as well on Claude Code, and adds no skill to keep in
three copies.

**What it does not show.** Codex and OpenCode were not run. One step
of one skill was measured, on one model, with the two moved steps
worded alike; a pointer without the "not done until" sentence was not
an arm.

**The same three arms with an outline, 2026-11-14.** In the runs above
no dossier had an `outline.md`, so `draft dossier status` was optional
in the critique step and a run that skipped it had followed the step;
counted only where it ran at or before the baseline scan, it ran in 5,
4 and 3 runs. The arms were run again with `--outline`, which gives the
task five outlined sections with declared queries and so makes the
command required. Rows: `inline-outline.json`, `pointer-outline.json`
and `handoff-outline.json` in the same folder.

| | Inline | Pointer | Handoff |
| --- | ---: | ---: | ---: |
| Usable runs, gate passed, `outline.md` written | 6 | 6 | 6 |
| `draft dossier status` at or before the baseline scan | 6 | 6 | 6 |
| `review verbatim recheck` ran | 6 | 6 | 6 |
| `revisions.md` has a critique entry | 6 | 6 | 6 |
| Reached the loop's text | 6 | 6 | 6 (all by the skill tool) |
| Median run | 334 s | 386 s | 329 s |

Both comparisons exit 0, with every command row equal but
`review synthesis` (3, 4, 3) and `figure sync` (1, 0, 0). Where the
command is required, all three arms ran it in every run. No declared
query came back `no evidence`: the security query returned candidates,
so what a run does with a `no evidence` sub-theme was not exercised.

**Codex and OpenCode, 2026-11-15, advisory.** The outline task again,
6 skill-only runs an arm on each harness, Codex 0.159.3 and OpenCode
1.18.34 on the Qwen3.6-35B-A3B `UD-Q4_K_M` file, one `llama-server`
(b11321, CUDA) per A40 as `serve_models.sh` starts it, two servers an
arm, each run capped at 1500 seconds. Rows: `inline-outline-local.json`,
`pointer-outline-local.json` and `handoff-outline-local.json`. Counts
are runs of 6, read from each transcript and project by hand:

| | Codex inline | Codex pointer | Codex handoff | OpenCode inline | OpenCode pointer | OpenCode handoff |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gate passed | 6 | 5 | 5 | 2 | 5 | 3 |
| Opened the loop's text | 0 | 1 | 5 | 0 | 3 | 2 |
| `draft dossier status` ran | 0 | 0 | 0 | 1 | 0 | 2 |
| `review verbatim scan` ran | 3 | 5 | 1 | 2 | 1 | 2 |
| `review verbatim recheck` ran | 0 | 0 | 1 | 0 | 0 | 0 |
| `revisions.md` has a critique entry | 0 | 0 | 0 | 0 | 0 | 0 |
| `draft render` ran | 4 | 5 | 2 | 2 | 3 | 2 |

The local model does not work the critique loop in any arm: no run of
36 logged a critique entry, and the inline arm, with the commands in
front of it, ran `draft dossier status` once in 12 runs. With nothing
to lose, these runs cannot show whether moving the step loses it. Two
things they do suggest, at 6 runs and far inside this harness's noise:
a handoff got Codex to open the loop's text in 5 runs against 0 inline,
and the Codex handoff arm then reached `draft render` in 2 runs against
4 and 5, which is the return risk a handoff carries.

`--compare` calls both harnesses inconclusive, for a reason of this
launch's own: the bench was started with `PYTHONPATH` set to its
checkout, the model's `python -m chitragupta` then resolved there, and
a run that read the package's source named that path, which the bench
reads as a run outside its project (21 of 36). Those reads were of
`chitragupta/`, never of a skill, so the hand count above keeps them.
Start the bench without `PYTHONPATH` to avoid it.

**A scorer bug found on the way.** The first scoring flagged `enrich`
as run in 3 pointer runs. No run ran it: each had written a note to
`revisions.md` through a quoted heredoc whose text named the command
in backticks, and the scorer read backticks inside a heredoc body as a
substitution. Fixed here, with a `self_check()` case.

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

- [x] **Step 1:** Make the changes. Run both remedy tests. Done when they
  pass, now covering `skills-common/`.
- [x] **Step 2:** Commit.

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

- [x] **Step 1:** Write the file. Its first line is distinct from every
  other reference's, because Tier 1 scores a read by it.
- [x] **Step 2:** No commit yet: `tests/test_skill_references.py`
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

- [x] **Step 1:** Write both files and the ledger. No commit yet (see
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

- [x] **Step 1:** Rewrite the `.claude` copy. Merge only tail steps 14 and
  15 (reread, record steering); steps 1, 2, 2a, 9 and 10 keep their
  numbers.
- [x] **Step 2:** Port to the other two copies, keeping every phrase-map
  difference. Run `pytest tests/test_skill_harness_copies.py -q`. Done
  when it is green.
- [x] **Step 3:** Lower the cap. Run `pytest tests/test_skill_*.py
  tests/test_init.py tests/test_tikz_scaffolds.py -q`. Done when it is
  green and all three copies are at or under 12,000 bytes.
- [x] **Step 4:** Commit.

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

- [x] **Step 1:** Update every reference, then run
  `grep -rn "survey-writer.*step\|step [0-9]*.*survey" docs chitragupta .claude`
  and check each hit. Done when every hit names the right step.
- [x] **Step 2:** Run the full suite with coverage. Done when it is green
  at 100%.
- [x] **Step 3:** Push and open PR 1 with "Part of #1091". On the
  server, `skill-bench` for survey-writer. Done when `--compare` exits 0
  and its table is on the PR and in `docs/HARNESS.md`.
- [x] **Step 4:** Fable-model review, then merge.

---

## PR 2: textbook, thesis and tutorial

Branch `feat-1091-genre-writers`. Same pattern as PR 1 Tasks 3–5, once
per skill, with these differences. Baselines for all three come from
`main` before the branch starts.

### Task 1: settle the two inconsistencies first

**Files:**

- Modify: `.claude/skills/figure-drawer/references/placement.md` §4
- Modify: `.claude/skills/tutorial-writer/SKILL.md` step 9 (all copies)

- [x] **Step 1:** `placement.md` §4 says the pdf render is LuaLaTeX with
  `chitragupta-lualatex.tex` (#1037), as thesis step 9 does, and carries
  the `\resizebox` note (#1046); `chitragupta-unicode.sty` is named only
  where it still applies. Run `pytest tests/test_skill_figure_router.py
  tests/test_figure_rule_ids.py -q`.
- [x] **Step 2:** Tutorial step 9 loses "most of this genre's rare
  figures need no caption at all": every figure has a caption, as
  `figures.md` §10 and `FigureNoCaption` (#421) say.
- [x] **Step 3:** Commit.

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

- [x] **Step 1:** Each skill at or under 12,000 bytes in all three
  copies; caps lowered with reason `None`. A skill that real
  deduplication leaves above 12,000 goes back to the user (Decision 1).
- [x] **Step 2:** Update `docs/WRITING-STANDARDS.md:561`,
  `chitragupta/review/synthesis.py:48`, `chitragupta/review/_units.py:22`
  and `docs/PROMPTS.md:76` ("19-step") where a step changed.
- [x] **Step 3:** Full suite at 100%; `skill-bench` for all three, each
  `--compare` exiting 0; results on the PR and in `docs/HARNESS.md`.
- [x] **Step 4:** Fable-model review, merge, then comment on #1178: cite
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

## How it ended

Recorded 2026-11-16, when the last PR merged. The tasks above are as
planned; each skill's ledger (`plans/1091-ledger-<skill>.md`) says how
it was built and why.

| PR | Merged as | `SKILL.md`, bytes (Claude Code copy) | Bench on Claude Code |
| --- | --- | --- | --- |
| 0, SK-0 | #1209 | none shrunk | baselines recorded |
| 0b, SK-0b | #1212 | none shrunk | Tier 1, 10 of 11 |
| 0c, SK-0c | #1214 | none shrunk | pointer and handoff both held |
| 1, SK-1 | #1215, #1217 | survey-writer 31,779 to 13,688 | pass |
| 2, SK-2 | #1223 | textbook 32,215 to 15,380; thesis 33,773 to 14,933; tutorial 33,562 to 16,809 | pass, pass, one optional row |
| 3, SK-3 | #1220 | review-digest 16,881 to 16,765 | pass |
| 4, SK-4 | #1219 | draft-reviser 29,016 to 22,600 | pass |
| 5, SK-5 | #1221 | agenda-reviser 28,097 to 18,521 | pass at 6 against 6 |
| 6, SK-6 | #1218 | book-assembler 19,704 to 13,806 | pass |
| 7, SK-7 | #1222 | corpus-reviser 12,762 to 10,945 | pass at 6 against 6 |
| 8, SK-8 | #1224 | deep-research 40,760 to 19,303 | pass at 6 against 6 |

Sizes are as the series closes, after the review fixes below put some
text back. Two small PRs sit beside the rows: #1216 (the two checker
messages that still named the old path, and Tier 1's strictness about
an emoji) and the wrap-up PR that carries this section.

**Where the plan was wrong.**

- **No skill reached its byte target**, and the owner ruled on
  2026-11-14 that the targets are guidelines (Decision 1). What stays
  is commands, guardrails, text the tests read, and one `Done when` a
  step. Two estimates were far off: draft-reviser's 5.3 KB floor, since
  agenda-reviser and corpus-reviser follow its loop by step number and
  every step has to stay whole; and deep-research's 10 to 12 KB, since
  three dispatch sites and the transcription of every packet stay with
  the main run.
- **"One reference file per skill" does not fit a skill with modes.**
  draft-reviser keeps its five mode references and agenda-reviser its
  three repair references, each read only on its own branch.
- **A genre file is named by the genre's `--genre` value**:
  `textbook-chapter.md` and `thesis-chapter.md`, not `textbook.md` and
  `thesis.md`.
- **The plan's Task 2 for §12's two `##` headings** would have changed
  a rule, and was not done (PR #1212).
- **The critique loop's commands did move behind its pointer**, in all
  five skills that run it, reversing Decision 2 for that step
  (Decision 2 as amended; #1217, #1223, #1224).
- **Codex and OpenCode never became usable for judging a shrink.**
  Every Codex run ends when it sends a rendered figure to the local
  model, which has no vision projector (#1210). The series gated on
  Claude Code alone.

**What the benches found, beyond pass and fail.** Each was a defect in a
skill's wording that no unit test could see, and each is fixed:

- agenda-reviser read `pass_bound` as a limit on repairs and stopped
  with items open (#1221);
- deep-research never handed its interviewers their section's declared
  queries (#1224);
- a tutorial figure was allowed to go without a caption while the style
  check flagged it (#1223).

One optional command fell wherever the critique loop moved behind its
pointer: `draft dossier status`, which the loop runs only where the
dossier has an `outline.md`. With the commands in front of it a model
ran it anyway; behind the pointer it follows the condition. With an
outline it ran in every run.

**The review before the release.** Two reviewers who had not built
anything compared every skill with its text before the series
(`a9c69d74`), walking each ledger. No guardrail on citekeys, the
read-only corpus or the gate was lost. They found fifteen things, fixed
in the wrap-up PR; the ones that matter most:

- three figure rules had been left to a bare citation in the four genre
  writers (the 7-bit text form, the caption in the draft, no hand-written
  "Figure" or number);
- review-digest pointed at a shared section whose drafting rules forbid
  how a digest is written;
- agenda-reviser no longer sent re-grounding to draft-reviser, and had
  lost the sentence that stops it at `pass_bound`;
- survey-writer's evidence step no longer named the `quote:` field, and
  the reason a survey emits an evidence sidecar sat behind a pointer
  read only on request. Runs of the shrunk skill wrote a quoted passage
  less often (1 of 6 against 3 of 6), which is the one measured cost of
  moving text out of sight. Both are back in the step.

**Also done in the wrap-up PR.** corpus-reviser's cost sentence now
opens its loop and is written to `revisions.md` before the first
search, after two wordings that only asked for it to be said left it in
the model's reasoning in six runs of six. Every thesis figure is a
captioned float. `docs/FIGURE-DRAWER.md` gives the LuaLaTeX advice.
No skill file names an issue or a pull request, and a test holds that.

**Left open.**

- A thesis run never renders with `--fragment`, so the `[tikz-libraries]`,
  `[unicode]` and `[floats]` lines the thesis skill is told to quote are
  never printed. Settling it adds a render to every thesis run.
- A direct request to figure-drawer enters draft-reviser's loop at step
  6, so no revision is marked and "Show what changed" has no baseline
  for that pass.
- agenda-reviser runs one pass an invocation, so `pass_bound` can never
  be reached within one.
- `latex-conventions.md` §5 says the bibliography is built by `bibtex`
  where the build runs `bibtexu`.
- The overlap checks in `docs/WRITING-STANDARDS.md` have not been rerun
  since the prose moved, and the sentences written during the move have
  had none.
- The front-matter descriptions are untouched, as planned.

## After the series

The front-matter descriptions (about 1,000 characters each, all loaded
in every session) are the next lever, measured with `skill-bench`
before any change. That is a new issue, opened when PR 8 merges.

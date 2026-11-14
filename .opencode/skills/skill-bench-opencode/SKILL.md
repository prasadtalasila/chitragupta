---
name: skill-bench-opencode
description: Measures whether a change to a skill changes what a model does with it, for this repository's developers -- runs every user skill's Tier 2 task on Claude Code, Codex and OpenCode (local Qwen3.6 on llama-server, one per GPU), before and after the change, and compares which chitragupta commands each run executed and whether its draft passed the gate. Triggers when a developer asks to bench, benchmark or measure a skill change, a skill-shrink PR, or a baseline of the skills. Writes no draft and cites nothing. Developer-only -- no wheel, release zip or `chitragupta init` project carries it.
tags: [developer, benchmark, skills]
metadata:
  audience: developer
---

# skill-bench

A developer tool. You are changing or exercising this repository, so
`DEVELOPER-AGENTS.md` governs the session, not `AGENTS.md`. Paths in
this skill are from the project root. The `audience: developer` line
above keeps this skill and its `scripts/` out of every distribution
(see `chitragupta/developer_skills.py`). Keep that line.

The bench is `bench/bench_skill_harnesses.py`; `bench/README.md` says
what it runs and `docs/HARNESS.md` ("Measuring a skill change") says how
`--compare` judges. Run it only on a disposable machine with NVIDIA
GPUs: it turns every harness's sandbox and approval prompts off.

## What you need

| Tool | For |
| --- | --- |
| Codex 0.159.3, OpenCode 1.18.34 | the two local-model harnesses |
| llama.cpp `b11321`, built with CUDA | one `llama-server` per GPU |
| `Qwen3.6-35B-A3B-UD-Q4_K_M.gguf`, SHA-256 pinned | the local model, the same file as every earlier baseline |
| `claude`, logged in | the Claude Code arm, which runs on the API |
| TeX Live, poppler (this repository's os-deps) | the sync and the render every task ends on |

`bash .claude/skills/skill-bench/scripts/install_tools.sh --check` lists
each one and exits 1 if any is missing. Without `--check` it installs
what is missing under `~/bench-tools` (apt packages through sudo), and
its last line is the `PATH` to export. It cannot log `claude` in; the
person does that.

## Steps

1. **Check the tools.**
   `bash .claude/skills/skill-bench/scripts/install_tools.sh --check`.
   *Done when* it exits 0.
2. **Start the servers.**
   `bash .claude/skills/skill-bench/scripts/serve_models.sh <gpus>`
   starts one server per GPU on ports 18080 and up, detached, and its
   last line is the `--base-url` arguments for step 4. *Done when* it
   prints them; every port has answered `/v1/models` by then.
3. **Make the two checkouts.** The base: a worktree at the PR's merge
   base with `origin/main`. The head: the PR branch. Only the scaffold
   comes from `--source`; every command a model runs uses the installed
   `chitragupta`. So if the PR changes `chitragupta/`, make a venv for
   each worktree and run each arm with its own. *Done when*
   `git -C <worktree> rev-parse HEAD` prints the two expected commits.
4. **Run both arms** from the PR head's checkout, so both use the same
   bench code:

   ```bash
   python bench/bench_skill_harnesses.py --tier 2 --skill-only --skill <name> \
     --runs 3 --jobs <n> --timeout 1500 --source <worktree> --out <dir> <base-urls>
   ```

   `--skill-only` keeps the closing steps out of the prompt, so only the
   skill asks for them: the arm a shrink is gated on. Put `--out`
   outside every checkout; a run whose transcript names one is left
   out. Give `--jobs` the number of servers plus 4 for Claude Code.
   Leave out `--skill` for a baseline of every user skill. A task that revises a
   draft runs survey-writer first in the same project; its own score
   covers only its own transcript, and `prerequisite_gate` says whether
   it started from a passing draft. *Done when* both `tier2.json` files
   hold 3 runs per harness and skill.
5. **Compare.**

   ```bash
   python bench/bench_skill_harnesses.py --compare \
     <before>/tier2.json <after>/tier2.json
   ```

   Only Claude Code sets the exit code; Codex and OpenCode tables are
   marked advisory (`--gate` adds them once #1210 steadies them).
   Exit 3 is inconclusive: 3 runs screen, they do not convict. Run 3 more
   on both arms, each into a fresh `--out` (the bench overwrites its
   own), join each arm's two files into one JSON list, and compare
   again; 6 against 6 settles. A fail stands: report it,
   never rerun it until it passes. *Done when* it exits 0 or 1.
6. **Stop the servers and record.**
   `bash .claude/skills/skill-bench/scripts/serve_models.sh --stop`.
   Put the `--compare` table, the host (GPUs, driver, llama.cpp build)
   and the verdict in `docs/HARNESS.md` and on the PR. *Done when* the
   PR comment links the commit that records it.

`--compare` leaves out a run that started from a prerequisite that
never passed its gate, or that loaded the wrong checkout, and says how
many; it judges timeouts and errors on a row of their own. Name those
runs in the record too.

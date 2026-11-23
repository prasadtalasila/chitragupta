# Steady Codex and OpenCode on the skill bench, without changing a skill

Status: **built**, pending review; "What the measurement found" below
has where it went beyond the design. Written 2026-11-21 against `9862c8cb`
(6.177.1), for issue
[1210](https://github.com/prasadtalasila/chitragupta/issues/1210).

**Written for** whoever builds or reviews this on the A40 host.
**Assumed:** [docs/HARNESS.md](../docs/HARNESS.md), "Measuring a skill
change", and the `skill-bench` developer skill. **Not covered here:**
any change to a user skill's text. The owner ruled on 2026-11-21 that
issue 1210 is done without one; a skill edit the evidence calls for goes to
a follow-up issue and is benched there.

## Design (approved 2026-11-21)

**Intent.** `skill-bench --compare` can only gate on Claude Code,
because the two local harnesses lose whole tails of steps for reasons
outside the skills. Fix those reasons in the bench's own setup, measure
the local harnesses again on the skills as they now stand, and say how
often an unchanged skill would fail a comparison on them.

**The three causes, and their fixes:**

| Cause | Seen in | Fix |
| --- | --- | --- |
| `llama-server` has no vision projector, so Codex's first figure PNG gets `500 image input is not supported` and the run exits 1 | every Codex run that drew a figure (#1210 comment, 2026-11-15) | serve the model's own `mmproj-F16.gguf` (unsloth, 899,283,680 bytes, SHA-256 `8971ee4f…829e887f`), pinned and checked like the model |
| `opencode run` auto-rejects an `external_directory` request and the run ends | OpenCode's tutorial, deep-research and reviser runs | the bench gives OpenCode its own config, the provider example plus `"permission": {"external_directory": "allow"}`, written beside each run; the user-facing example in `docs/examples/opencode/` stays as it is |
| a `PYTHONPATH` naming the checkout makes a model's `python -m chitragupta` read the checkout, and the run is left out as outside its project | 21 of 36 local runs in SK-0c | `harness_env()` drops `PYTHONPATH` |

**Approaches considered.** (1) Fix the harness setup: chosen, since two
of three causes are setup. (2) Make the figure `look` step text-only
where the model has no vision: rejected, it changes a skill. (3) More
runs per arm: rejected by the issue, it buys power without fixing the
causes.

**Measurement.** One `--skill-only` Tier 2 baseline of every user skill
on Codex and OpenCode, 3 runs each, from a non-editable install of this
branch in a venv outside every checkout. Evidence that the fixes took:
no `image input is not supported` in any server log, and no
`auto-rejecting` in any OpenCode transcript.

**Codex and `draft dossier init`.** Read the new Codex transcripts. If
the genre writers now run it, the item closes on that evidence; if not,
name the step and the transcript lines on #1210 and open a follow-up
issue with a proposed wording.

**False-fail rate.** A committed `bench/simulate_false_fail.py`
resamples each (harness, skill)'s measured runs, with replacement, into
two arms of 3 and judges them with `skill_commands.judge`, the same
rule `--compare` applies. Whole runs are resampled, so a run that
derails takes all its commands with it. Claude Code's rows are each
skill's newest Claude Code rows from the #1091 series.

**Not done:** no skill file changes, no new check promoted to a gate,
no change to `GATED` (the numbers decide that later, in its own PR).

## Tasks

1. **Vision projector.** `install_tools.sh` checks and fetches
   `mmproj-F16.gguf` with a pinned size and hash and a `.verified`
   stamp (the model's `model_ok` generalised to a `pinned_file NAME
   FILE BYTES SHA256`); `serve_models.sh` passes `--mmproj
   "$MMPROJ_FILE"` and refuses to start without it. Tests in
   `tests/test_skill_bench_install_tools.py`: the check names
   `mmproj: missing` when it is absent or the wrong size, and the fake
   server is started with `--mmproj`.
2. **Bench environment.** In `bench/bench_skill_harnesses.py`:
   `harness_env()` drops `PYTHONPATH`; `opencode_config(folder: Path)
   -> Path` writes the provider example plus the permission to
   `folder/opencode.json`, and `run()` points `OPENCODE_CONFIG` at it
   for OpenCode. `self_check()` asserts both. A smoke run: one Codex
   figure-drawer run and one OpenCode tutorial run, checked for the two
   failure strings.
3. **Baseline.** `serve_models.sh 6`, then
   `bench_skill_harnesses.py --tier 2 --skill-only --harness codex
   --harness opencode --runs 3 --jobs 6 --timeout 1500 --out
   ~/bench-runs/1210/baseline <6 base urls>`, run with the bench venv's
   python. Copy `tier2.json` to
   `bench/results/2026-11-21-local-harness-rebaseline/`.
4. **Read and simulate.** The Codex dossier finding; the simulation
   script and its output, per harness and over all three.
5. **Record and ship.** `docs/HARNESS.md` ("Measuring a skill change":
   the new rows, the false-fail rate, the fixes), `bench/README.md`
   (the new script), a PATCH bump, OpenCodeReview, the PR. The PR waits
   for the owner.

## What the measurement found

- **A fourth setup cause.** Codex has no metadata for a local model, so
  it never compacted, and two survey runs ended on a 400 at 131,625
  tokens. The bench now passes `model_context_window` and a compact
  limit at 75% of it, and the Codex arm was run again whole, so all its
  rows come from one setup.
- **A broken scorer.** The click-style `--help` that every command now
  prints carries no `{a,b}` usage group, so `skill_commands.subcommands`
  found no subcommands on `main`. It reads the `Commands:` block now.
- **A cause no setting reaches.** The model sometimes writes a tool call
  whose arguments are not JSON; `llama-server` answers 500 and Codex
  retries the same history five times and exits. 2 runs in the first
  arm, none in the recorded one.
- **The baseline ran in three pieces.** A 2-hour tool limit stopped the
  first arm at 56 of 66 runs; its rows were recovered from the bench's
  log, OpenCode's 6 missing runs were rerun into their slots, and Codex
  was run again whole (above), its run 3 in a second process on the
  idle GPUs. Long benches now run detached (`setsid nohup`).
- **Two versions of the skills.** The checkout was rebased onto
  `main` while the first arm ran, and the bench scaffolds from the
  checkout at each run's start: 16 OpenCode runs have the skills of
  `9862c8cb`, the other 50 those of `0fd52e29a` (the style step's
  wording only). The results README records which.
- **The false-fail rate fell less than the gate pass rate rose.** Every
  usable local run passed the gate, but over all three harnesses an
  unchanged skill still fails `--compare` 0% to 15% (whole runs) or 0%
  to 20% (each command) of the time, against 0% to 7% on Claude Code
  alone. The rest is command-level, so `GATED` stays `("claude",)`.
- **Codex and `draft dossier init`.** Every genre writer's run ran it; no
  review-digest run did (0 of 6 over both Codex arms). The step and the
  transcript lines went to a follow-up issue with a proposed wording.

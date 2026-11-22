# Local harness rebaseline, 2026-11-21

The skill-only Tier 2 arm of every user skill on Codex 0.159.3 and
OpenCode 1.18.34, 3 runs each, against Qwen3.6-35B-A3B Q4_K_M served
with its `mmproj-F16.gguf` by llama.cpp `b11321` (CUDA), one
`llama-server` per A40, `-c 131072 -np 1`. Every command ran on a
non-editable install of the branch as of `9862c8cb`, in a venv outside
every checkout, with no `PYTHONPATH`. `docs/HARNESS.md`, "Measuring a
skill change", reads the numbers.

**Two versions of the skills.** The bench scaffolds each run's skills
from its checkout when the run starts, and the checkout was rebased
onto `main` at 19:30:30 UTC while the first arm ran. The 16 OpenCode
runs that started before then have the skills of `9862c8cb`; the other
17 OpenCode runs and all 33 Codex runs have those of `0fd52e29a`. The
two differ in 29 skill files (68 lines in, 86 out), all of it the
wording of the style step and a removed attribution link: no step is
added or removed and no command changes. A later bench pins its
`--source` to one commit instead.

| File | What it holds |
| --- | --- |
| `tier2.json` | the 66 rows, Codex then OpenCode |
| `false-fail-runs.json` | `simulate_false_fail.py --model runs` |
| `false-fail-commands.json` | `simulate_false_fail.py --model commands` (20,000 trials, seed 1210) |

**How the rows were collected.** The first arm ran all 66 jobs and was
stopped at 56 by a 2-hour tool limit. Its finished rows came from the
JSON line the bench prints per job. OpenCode's 6 missing jobs were rerun
on their own; those rows carry `"rerun": true` and the run number they
fill. Codex was then run again whole after Codex was told the context
window, its runs 1 and 2 in one process and run 3 in a second on the
other three GPUs, so every Codex row comes from that setup.

**The simulations** take each skill's Claude Code rows from the newest
skill-only file of the #1091 series, listed oldest first so the newest
wins, then this `tier2.json`:

```bash
cd bench
python3 simulate_false_fail.py --model runs --json results/2026-11-21-local-harness-rebaseline/false-fail-runs.json \
  results/2026-11-14-skill-bench-skill-only/tier2.json \
  results/2026-11-15-book-assembler-shrink/tier2.json \
  results/2026-11-15-draft-reviser-shrink/tier2.json \
  results/2026-11-15-deep-research-shrink/after.json \
  results/2026-11-15-textbook-chapter-writer-shrink/after.json \
  results/2026-11-15-thesis-chapter-writer-shrink/tier2.json \
  results/2026-11-15-tutorial-writer-shrink/after.json \
  results/2026-11-15-agenda-reviser-shrink/tier2.json \
  results/2026-11-16-wrap-up/agenda-reviser.json \
  results/2026-11-16-wrap-up/corpus-reviser.json \
  results/2026-11-16-wrap-up/review-digest.json \
  results/2026-11-16-wrap-up/survey-writer.json \
  results/2026-11-21-local-harness-rebaseline/tier2.json
```

`--model commands` with the same files gives the other JSON.

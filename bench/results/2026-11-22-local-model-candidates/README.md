# Local model candidates, 2026-11-22

The skill-only Tier 2 arm of every user skill on Codex 0.159.3 and
OpenCode 1.18.34, 3 runs each, for three local models served by
llama.cpp `b11321` (CUDA), one `llama-server` per A40, `-c 131072 -np 1`,
each with its own vision projector. `docs/MODEL-COMPLIANCE.md`,
"Stronger local models", reads the numbers.

| File | Model | Every row's `model` |
| --- | --- | --- |
| `qwen3.6-35b-a3b.json` | Qwen3.6-35B-A3B UD-Q4_K_M, the control | `qwen3.6-35b-a3b` |
| `gemma-4-31b.json` | Gemma 4 31B it, Q8_0 | `gemma-4-31b` |
| `qwen3.6-27b.json` | Qwen3.6-27B, Q8_0 | `qwen3.6-27b` |
| `false-fail-<runs\|commands>-<model>.json` | `simulate_false_fail.py` on that model's rows alone | |

**One commit for every run.** `--source` was a detached worktree at
`387bd334a` (`main` at `823176a93` with PR 1246 and this branch's
bench changes), and every command ran on a non-editable install of it
(chitragupta 6.179.1) in a venv outside every checkout, with no
`PYTHONPATH`. The bench script ran from that worktree too, so no later
rebase could change a run's skills.

**The model files**, from `unsloth/*-GGUF` at the revisions named, each
checked against its SHA-256:

| File | Revision | SHA-256 |
| --- | --- | --- |
| `Qwen3.6-35B-A3B-UD-Q4_K_M.gguf` and its `mmproj-F16.gguf` | as pinned in `install_tools.sh` | as pinned there |
| `gemma-4-31B-it-Q8_0.gguf` | `c1ac76e9` | `d5808e5874e660a85ab45b2da00c9e3b4a003621249a333772232d1a703e4d67` |
| `gemma-4-31B-it` `mmproj-F16.gguf` | `c1ac76e9` | `6edcca228213c28d3567a35d22f849eea52d8360875093851959adf5d2f270eb` |
| `mtp-gemma-4-31B-it.gguf` (the MTP draft, Q8_0) | `c1ac76e9` | `5ae8b0117bed601e8924c6305bd5b0585de361d51f0e77091bcb4252cf1f27de` |
| `Qwen3.6-27B-Q8_0.gguf` from `Qwen3.6-27B-MTP-GGUF` (MTP head built in) | `5cb35eb3` | `9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8` |
| `Qwen3.6-27B` `mmproj-F16.gguf` | `82d411ac` | `eacf610d1ee4bd5ed0197a0777dd8f4fceb8eefa27009067c7d496cb68fbde45` |

**How each was served**, through `serve_models.sh` with `MODEL_FILE`,
`MMPROJ_FILE`, `MODEL_ALIAS` and `LLAMA_EXTRA`, and the bench run with
`MODEL=<alias> --timeout 3600 --jobs 6`:

| Model | `LLAMA_EXTRA` |
| --- | --- |
| Qwen3.6-35B-A3B | none |
| Gemma 4 31B | `-md mtp-gemma-4-31B-it.gguf -ngld 99 --spec-type draft-mtp --spec-draft-n-max 2` |
| Qwen3.6-27B | `--spec-type draft-mtp --spec-draft-n-max 2` |

Measured on one 700-token reply before the runs, MTP took Qwen3.6-27B
from 19.5 to 36.5 tokens a second (393 of 610 drafted tokens accepted)
and Gemma 4 31B from 16.3 to 34.0 (389 of 620). Before each model's arm
the driver sent one image and one tool call through `/v1/responses`;
both models read the image ("Red") and called the tool.

**Order and one restart.** Gemma 4 31B ran first (10:33 to 13:30 UTC),
then the control (13:41 to 16:32). Qwen3.6-27B was meant to run second,
but three of its six servers aborted at load when all six started at
once; started one GPU at a time and each waited for, all six came up,
and its arm ran 16:33 to 21:38. Nothing of that first attempt is in
these rows.

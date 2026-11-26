---
name: ai-images
description: Generates an image from a text prompt with FLUX.2 klein 4B (Apache-2.0, ungated) on this machine's GPU, for this repository's developers -- builds a virtualenv outside the checkout on first use, then runs one script that takes the prompt and a model and writes a PNG. Triggers when a developer asks to generate, draw, render or make an image, picture, illustration, title artwork or figure background from a prompt, or to try another diffusers model on the same prompt. Writes no draft and cites nothing. Developer-only -- no wheel, release zip or `chitragupta init` project carries it.
tags: [developer, images, flux]
metadata:
  audience: developer
---

# ai-images

A developer tool. You are changing or exercising this repository, so
`DEVELOPER-AGENTS.md` governs the session, not `AGENTS.md`. Paths in
this skill are from the project root. The `audience: developer` line
above keeps this skill and its `scripts/` out of every distribution
(see `chitragupta/developer_skills.py`). Keep that line, and put any
new code under `.claude/skills/ai-images/scripts/` so it is left out
with them.

It makes pictures, not drafts: nothing here is a source, and no image
is evidence for a claim. It never touches a citekey.

## What you need

| Need | Why |
| --- | --- |
| an NVIDIA GPU with about 13 GB free, or Apple silicon | klein 4B in bf16; with neither, `gen.py` refuses rather than starting a run that takes hours |
| `uv`, or `python3` with `venv` | `setup.sh` builds the environment |
| about 15 GB of disk in `~/.cache/huggingface` | the model's weights, fetched from huggingface.co on the first run |
| network access to `huggingface.co` and PyPI | the first run only |

The environment lives in `$AI_IMAGES_HOME` (default
`~/.cache/ai-images`), never inside a checkout.

## Licence

FLUX.2 klein 4B, `diffusers` and `gen.py` are Apache-2.0, so the default
needs no token, no licence click-through and no restriction on what the
image is used for. **Other FLUX.2 models are not like it.** FLUX.2 [dev]
and klein 9B are gated on the Hub (both answered 401 without a token on
2026-11-26), and their licences differ from Apache-2.0: read each before
use. Running one needs `HF_TOKEN` in the environment and the person's
own acceptance of its licence on the Hub. Do not accept a licence on
their behalf, and do not write a token into a file, a command line you
echo, or a commit.

## Steps

1. **Set up the environment.**
   `PY="$(bash .claude/skills/ai-images/scripts/setup.sh)"`. It reuses
   what exists, so run it every time; `--check` reports without
   changing anything. *Done when* it prints an interpreter path and
   exits 0. The first run installs torch, a multi-GB download.
2. **Write the prompt.** Use the person's words. If a word is
   ambiguous (a name that is a person, a place and a deity), add the
   detail that picks the meaning and tell them what you added. Do not
   add style words they did not ask for.
3. **Generate.**

   ```bash
   "$PY" .claude/skills/ai-images/scripts/gen.py "<prompt>" --out <path>.png
   ```

   Pass an `--out` the person named. If they named none, use a folder
   outside every tracked directory, never `content/` or `papers/`.
   `--seed N` repeats a result; without it the seed is random and the
   last line prints it. `--model <hub id>` or `$AI_IMAGES_MODEL`
   picks another diffusers model. *Done when* the last line starts
   `saved` and names a file that exists.
4. **Show it.** Open the PNG with whatever your harness offers for
   reading an image file, and give the person the absolute path from
   the `saved` line, the model and the seed. If you cannot display an
   image, say so and give the path. Describe only what you can see.

A klein checkpoint that is not a `base` one is step-distilled, so
`gen.py` runs it at 4 steps and guidance 1.0: 11 seconds, model load
included, on one A40 with the weights cached (measured 2026-11-26).
`--steps` overrides that. Every other model keeps the pipeline's own
defaults.

## When it stops

- `no CUDA or Metal device`: the machine cannot run the model. Say so;
  do not retry on the CPU.
- `401` or `gated repo` from the Hub: the model needs a token and an
  accepted licence. Name both and stop; the default model needs
  neither.
- Out of memory: close other GPU work, or set `CUDA_VISIBLE_DEVICES` to
  a free card, before changing the model.

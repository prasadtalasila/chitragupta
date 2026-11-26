---
name: ai-images
description: Generates one image from a text prompt with FLUX.2 klein 4B (Apache-2.0, ungated) on this machine's GPU -- runs a script in the project's `.venv-full` that takes the prompt and a model and writes a PNG, and installs the `images` extra there first if it is missing. Triggers when the user asks to generate, draw, render or make an image, picture, illustration, cover or title artwork from a prompt, or to try another diffusers model on the same prompt. For a figure inside a draft, use figure-drawer instead, since that is a TikZ picture and not a generated one. Writes no draft and cites nothing, and a generated image is never evidence for a claim.
tags: [images, flux, diffusion]
---

# ai-images

Makes a picture from a prompt, on this machine. It is not a drafting
skill: nothing it makes is a source, and it never touches a citekey. A
figure that belongs in a draft is `figure-drawer`'s. Paths in this skill
are from the project root.

## What you need

| Need | Why |
| --- | --- |
| `.venv-full` with the `images` extra | torch, diffusers and transformers; step 1 installs it if missing |
| an NVIDIA GPU with about 18 GB free, or Apple silicon | klein 4B in bf16 peaked at 17.3 GiB on an A40; with neither, `gen.py` refuses rather than start a run that takes hours |
| about 15 GB in `~/.cache/huggingface` | the model's weights, fetched from huggingface.co on the first run into the Hugging Face default cache, never into the project |

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

1. **Check the environment.**
   `.venv-full/bin/python -c "import torch, diffusers, accelerate"`.
   *Done when* it exits 0. If it fails, install the extra into the same
   venv, then check again:
   - in a git checkout: `VIRTUAL_ENV="$PWD/.venv-full" uv sync --active
     --inexact --locked --extra images`, which keeps what is there and
     adds the extra at the versions `uv.lock` pins;
   - in a project made by `chitragupta init`: `.venv-full/bin/python -m
     pip install 'chitragupta-cli[images]'`.

   No `.venv-full` yet: the install section of `README.md` makes it.
   On a CUDA host a plain pip install can leave a CPU-only torch;
   `chitragupta doctor` says so and names the fix.
2. **Write the prompt.** Use the person's words. If a word is
   ambiguous (a name that is a person, a place and a deity), add the
   detail that picks the meaning and tell them what you added. Do not
   add style words they did not ask for.
3. **Generate.**

   ```bash
   .venv-full/bin/python .claude/skills/ai-images/scripts/gen.py "<prompt>" --out <path>.png
   ```

   Pass an `--out` the person named. If they named none, use a folder
   outside every tracked directory, and never `content/` or `papers/`:
   a generated image is not a draft, and a committed one is rarely
   wanted. `--seed N` repeats a result; without it the seed is random
   and the last line prints it. `--model <hub id>` or `$AI_IMAGES_MODEL`
   picks another diffusers model. *Done when* the last line starts
   `saved` and names a file that exists.
4. **Show it.** Open the PNG with whatever your harness offers for
   reading an image file, and give the person the absolute path from
   the `saved` line, the model and the seed. If you cannot display an
   image, say so and give the path. Describe only what you can see.

A klein checkpoint that is not a `base` one is step-distilled, so
`gen.py` runs it at 4 steps and guidance 1.0: about 10 seconds, model
load included, on one A40 with the weights cached (measured
2026-11-26). `--steps` overrides that. Every other model keeps the
pipeline's own defaults.

## When it stops

- `no CUDA or Metal device`: the machine cannot run the model. Say so;
  do not retry on the CPU.
- `401` or `gated repo` from the Hub: the model needs a token and an
  accepted licence. Name both and stop; the default model needs
  neither.
- Out of memory: close other GPU work, or set `CUDA_VISIBLE_DEVICES` to
  a free card, before changing the model.

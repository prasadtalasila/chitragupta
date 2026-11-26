#!/usr/bin/env python3
"""Send one prompt to a diffusers text-to-image model and save a PNG.

Run it with the interpreter `setup.sh` prints, not the system one:

    "$PY" .claude/skills/ai-images/scripts/gen.py "a lighthouse at dusk" --out lighthouse.png

The model is `--model`, else $AI_IMAGES_MODEL, else FLUX.2 klein 4B
(Apache-2.0, ungated). A gated model such as black-forest-labs/FLUX.2-dev
needs HF_TOKEN in the environment and its licence accepted on the Hub.
"""

import argparse
import os
import random
import sys
from pathlib import Path

DEFAULT_MODEL = "black-forest-labs/FLUX.2-klein-4B"


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("prompt")
    parser.add_argument("--model", default=os.environ.get("AI_IMAGES_MODEL", DEFAULT_MODEL))
    parser.add_argument("--out", default="ai-image.png", type=Path)
    parser.add_argument("--seed", type=int, help="random, and printed, when omitted")
    parser.add_argument("--steps", type=int, help="the model's own default when omitted")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    return parser.parse_args(argv)


def pick_device(torch):
    """CUDA, else Metal; a CPU run of a 4B model is hours, so refuse it."""
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    sys.exit("ai-images: no CUDA or Metal device, and a CPU run would take hours")


def sampler_settings(model):
    """The step count and guidance a step-distilled klein is built for.

    The `base` klein checkpoints are not distilled and keep the
    pipeline's own defaults.
    """
    name = model.lower()
    if "klein" in name and "base" not in name:
        return {"num_inference_steps": 4, "guidance_scale": 1.0}
    return {}


def main(argv=None):
    args = parse_args(argv)
    # Imported late so `--help` and an argument error do not wait on torch.
    import torch  # pylint: disable=import-outside-toplevel
    from diffusers import DiffusionPipeline  # pylint: disable=import-outside-toplevel

    device = pick_device(torch)
    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(2**32)
    settings = sampler_settings(args.model)
    if args.steps:
        settings["num_inference_steps"] = args.steps
    pipe = DiffusionPipeline.from_pretrained(args.model, dtype=torch.bfloat16).to(device)
    image = pipe(
        prompt=args.prompt,
        width=args.width,
        height=args.height,
        generator=torch.Generator(device).manual_seed(seed),
        **settings,
    ).images[0]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.out)
    print(f"saved {args.out.resolve()} (model {args.model}, seed {seed})", flush=True)


if __name__ == "__main__":
    main()

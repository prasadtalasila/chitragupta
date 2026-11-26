#!/usr/bin/env bash
# Build, or reuse, the virtualenv gen.py runs in, and print its python.
#
#   PY="$(bash .claude/skills/ai-images/scripts/setup.sh)"
#   bash .claude/skills/ai-images/scripts/setup.sh --check   # report, change nothing
#
# The environment lives outside the checkout, in $AI_IMAGES_HOME (default
# ~/.cache/ai-images), on purpose: it holds torch and a CUDA stack, and a
# second venv inside a checkout is what DEVELOPER-AGENTS.md warns against.
# stdout carries only the interpreter path, so the command substitution
# above is safe; everything else goes to stderr.
set -euo pipefail

HOME_DIR="${AI_IMAGES_HOME:-$HOME/.cache/ai-images}"
PY="$HOME_DIR/venv/bin/python"
# The versions gen.py was run against on 2026-11-26 (FLUX.2 klein 4B,
# 2x NVIDIA A40, CUDA 13.2). torch is left to the resolver so pip picks
# the wheel that matches the host's driver.
PACKAGES=(
  torch
  "diffusers==0.43.0"
  "transformers==5.24.1"
  "accelerate==1.16.0"
  "sentencepiece==0.2.3"
  "protobuf==7.36.2"
)

ready() {
  [ -x "$PY" ] && "$PY" -c "import torch, diffusers" 2>/dev/null
}

if [ "${1:-}" = "--check" ]; then
  if ready; then
    echo "ai-images: ready, $PY" >&2
    exit 0
  fi
  echo "ai-images: not set up; run this script without --check" >&2
  exit 1
fi

if ready; then
  echo "$PY"
  exit 0
fi

echo "ai-images: creating $HOME_DIR/venv (torch is a multi-GB download)" >&2
mkdir -p "$HOME_DIR"
# --clear: reaching here means the venv is absent or unusable, for example an
# install that was interrupted, and uv refuses to replace one without it.
if command -v uv >/dev/null 2>&1; then
  uv venv --clear "$HOME_DIR/venv" >&2
  uv pip install --python "$PY" "${PACKAGES[@]}" >&2
else
  python3 -m venv --clear "$HOME_DIR/venv" >&2
  "$PY" -m pip install --quiet "${PACKAGES[@]}" >&2
fi

if ! ready; then
  echo "ai-images: install finished but torch and diffusers do not import" >&2
  exit 1
fi
echo "$PY"

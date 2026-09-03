# Optional heavier toolchain for the research pipeline, per the original
# design (Ubuntu LTS + Claude Code with full permissions in an isolated
# container). Unlocks TeX Live (compiling generated .tex chapters to
# PDF), Pandoc, and the embeddings/clustering stack
# (sentence-transformers + Chroma + BERTopic)
# for hosts that don't have root, TeX Live, or Pandoc available
# directly. `pip install` outside a venv is blocked by PEP 668 regardless
# of root, though -- see AGENTS.md's "Environment constraints" section for
# what is and isn't conditional on root access.
#
# **There are two images in this directory, and this is the heavy one.**
# `docker/Dockerfile.claude` beside it hosts a `claude remote-control`
# agent instead: it installs the *published* chitragupta-cli from PyPI
# rather than building this stack from the checkout, so it is ~2.5GB and
# builds in seconds, and it leaves TeX Live/Pandoc/torch to
# `chitragupta install os-deps` at runtime. Neither replaces the other
# -- this one is what you want when you need the whole toolchain
# resolved up front, or when you are working on a checkout rather than
# on a release. DOCKER.md leads with a table of the two.
#
# One thing worth carrying across if you edit either: both put their
# venv first on PATH (here /opt/venv, there the same path) precisely so
# that the bare `python` in `.claude/settings.json`'s hook commands can
# import chitragupta. A private, hidden venv breaks the citation gate --
# see Dockerfile.claude's own comment on the pipx attempt that proved it.
#
# Built and verified manually (docker build, both TORCH_VARIANT values,
# both produced a working /opt/venv) -- see DOCKER.md's build-arg table
# for the two variants and their measured sizes.
#
# CI *does* build this image -- ci.yml's `docker-build` job, on the cpu
# variant, added in #302 -- so a break in the build is caught. Nothing
# execs into it, though: the image is built and discarded, so anything
# it does at runtime is still hand-verified only. (This comment said
# "not exercised by CI" until #302 made that false and did not update
# it; corrected here while the header was being edited anyway.)
#
# Build (GPU-capable torch, the default -- see TORCH_VARIANT below):
#   docker build -t chitragupta -f docker/Dockerfile .
# Run (mount persistent volumes -- see note at the bottom):
#   docker run -it --rm \
#     -v "$(pwd)":/workspace/chitragupta \
#     -v chitragupta-content:/workspace/chitragupta/content \
#     chitragupta

# Pinned to an LTS rather than `ubuntu:latest`: this image's package set
# (TeX Live, Pandoc, poppler, python3-poetry, OpenCV's runtime libs) is
# resolved by apt from whatever the base ships, and the base also
# decides the Python version the venv below is built with -- so a base
# bump is a thing to take deliberately and re-verify, not to pick up
# silently on a rebuild.
#
# **26.04 was tried and does not build. Do not bump this line on its
# own.** Ubuntu 26.04 LTS ships Python 3.14, and poetry.lock pins torch
# 2.7.1 / torchvision / triton 3.3.1, none of which publish cp314
# wheels. `poetry install` gets all the way through the rest of the
# dependency set and then fails per package with "Unable to find
# installation candidates for triton (3.3.1) ... 6 wheel(s) were
# skipped as your project's environment does not support the identified
# abi tags" -- measured on a --no-cache build, 2026-09-03.
#
# What unblocks it, if someone wants 26.04: torch publishes cp314 wheels
# from 2.9.0 onward (checked against PyPI: 2.9.0, 2.9.1, 2.12.x, 2.13.0,
# 2.14.0), so the base bump needs a torch/torchvision/triton
# re-resolution in poetry.lock first. That is a dependency change
# affecting both CI legs and every enrich test, not a Dockerfile change,
# and belongs in its own PR with its own test run -- tracked in issue
# #607, which carries the measured failure and the shape of the fix.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /workspace/chitragupta

# Single script also used on a bare host -- one source of truth for
# dependency versions/order/logic instead of separate, divergent copies
# of that logic here. Note this COPY precedes both stages
# below, so editing this script invalidates both of their layers -- the
# per-stage caching below only protects against edits to *later*
# Dockerfile lines or unrelated repo files, not to this script.
COPY scripts/install_full_pipeline.sh scripts/install_full_pipeline.sh
RUN chmod +x scripts/install_full_pipeline.sh

# Stage 1: OS packages (TeX Live, Pandoc, poppler-utils, git/curl/unzip,
# and OpenCV's runtime libraries -- this base image is
# --no-install-recommends, so nothing else drags libGL/GLib in, and the
# docling backend fails every document without them; the script's own
# comment has the full reckoning). Its own cached layer -- rarely changes.
RUN scripts/install_full_pipeline.sh os-deps && rm -rf /var/lib/apt/lists/*

# Stage 2: Python deps -- same script + pyproject.toml/poetry.lock as
# the host (Poetry itself came from stage 1's os-deps, which apt-installs
# python3-poetry). python -m chitragupta.draft gate doesn't need any of this
# and still runs with the bare python3 from stage 1; python -m chitragupta.corpus sync
# needs bibtexparser, the one dependency the rest of the core pipeline
# can't avoid.
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
ENV VIRTUAL_ENV=/opt/venv
COPY pyproject.toml poetry.lock poetry.toml ./

# torch itself isn't pinned in pyproject.toml (see its own comment on
# why) -- poetry.lock resolves whatever plain PyPI's default Linux wheel
# is, which bundles the full CUDA runtime as separate nvidia-* packages
# (cublas, cudnn, nccl, triton, ...) regardless of whether the build host
# or eventual container has a GPU at all. Measured on this image:
# GPU-capable venv 6.2GB (nvidia/ alone is 2.7GB) vs. CPU-only 2.0GB.
#
# TORCH_VARIANT=gpu (default) keeps that wheel as resolved -- for a real
# `docker run --gpus` deployment, since the bundled CUDA runtime is
# enough on its own (no host CUDA toolkit needed, just a driver).
# TORCH_VARIANT=cpu delegates to the install script's `cpu-torch` stage,
# which reinstalls torch/torchvision from PyTorch's own cpu-only wheel
# index at the same version poetry.lock resolved, then drops the
# now-orphaned nvidia-*/triton packages pip's --force-reinstall doesn't
# remove on its own. That logic used to be written out here; it moved to
# scripts/install_full_pipeline.sh so this image and CI call one
# implementation rather than two copies that drift
# (DEVELOPER-AGENTS.md: dependency facts have a single home).
#
# It stays chained inside this one RUN, and that is not cosmetic: the
# swap and the uninstall must land in the same layer or the CUDA wheels
# appear in a committed layer first. A later, separate RUN would only
# mark them deleted, not shrink the image -- checked by hand, and a
# later-layer uninstall left the image *larger* than doing nothing,
# because the deleted files' layer is still stored.
ARG TORCH_VARIANT=gpu
RUN SKIP_VENV=1 scripts/install_full_pipeline.sh python-deps && \
    if [ "$TORCH_VARIANT" = "cpu" ]; then \
        SKIP_VENV=1 scripts/install_full_pipeline.sh cpu-torch; \
    fi && \
    rm -rf /root/.cache/pypoetry /root/.cache/pip

CMD ["/bin/bash"]

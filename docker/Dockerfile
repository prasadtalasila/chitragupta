# Optional heavier toolchain for the research pipeline, per the original
# design (Ubuntu 24.04 + Claude Code with full permissions in an isolated
# container). Unlocks TeX Live (compiling generated .tex chapters to
# PDF), Pandoc, and the embeddings/clustering stack
# (sentence-transformers + Chroma + BERTopic)
# for hosts that don't have root, TeX Live, or Pandoc available
# directly. `pip install` outside a venv is blocked by PEP 668 regardless
# of root, though -- see AGENTS.md's "Environment constraints" section for
# what is and isn't conditional on root access.
#
# Built and verified manually (docker build, both TORCH_VARIANT values,
# both produced a working /opt/venv) -- see DOCKER.md's build-arg table
# for the two variants and their measured sizes. Not exercised by CI: no
# workflow under .github/ builds this image, so a break here still won't
# be caught automatically.
#
# Build (GPU-capable torch, the default -- see TORCH_VARIANT below):
#   docker build -t chitragupta -f docker/Dockerfile .
# Run (mount persistent volumes -- see note at the bottom):
#   docker run -it --rm \
#     -v "$(pwd)":/workspace/chitragupta \
#     -v chitragupta-content:/workspace/chitragupta/content \
#     chitragupta

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
# TORCH_VARIANT=cpu reinstalls torch/torchvision from PyTorch's own
# cpu-only wheel index, at the *same* version poetry.lock resolved (read
# back via `pip show` rather than hand-pinned here, so this never drifts
# from a `poetry lock` re-resolution the way a second pinned copy would),
# then drops the now-orphaned nvidia-*/triton packages pip's
# --force-reinstall doesn't remove on its own. Both the swap and the
# uninstall happen inside this one RUN so the CUDA wheels never appear in
# a committed layer to begin with -- doing it as a later, separate RUN
# would only mark them deleted, not shrink the image (this was checked by
# hand: a later-layer uninstall left the image *larger* than doing
# nothing, because the deleted files' layer is still stored).
ARG TORCH_VARIANT=gpu
RUN SKIP_VENV=1 scripts/install_full_pipeline.sh python-deps && \
    if [ "$TORCH_VARIANT" = "cpu" ]; then \
        torch_ver="$(/opt/venv/bin/pip show torch | sed -n 's/^Version: //p' | cut -d+ -f1)" && \
        tv_ver="$(/opt/venv/bin/pip show torchvision | sed -n 's/^Version: //p' | cut -d+ -f1)" && \
        /opt/venv/bin/pip install --no-cache-dir --force-reinstall \
            --index-url https://download.pytorch.org/whl/cpu \
            "torch==${torch_ver}" "torchvision==${tv_ver}" && \
        /opt/venv/bin/pip uninstall -y \
            nvidia-cublas-cu12 nvidia-cuda-cupti-cu12 nvidia-cuda-nvrtc-cu12 \
            nvidia-cuda-runtime-cu12 nvidia-cudnn-cu12 nvidia-cufft-cu12 \
            nvidia-cufile-cu12 nvidia-curand-cu12 nvidia-cusolver-cu12 \
            nvidia-cusparse-cu12 nvidia-cusparselt-cu12 nvidia-nccl-cu12 \
            nvidia-nvjitlink-cu12 nvidia-nvtx-cu12 triton; \
    fi && \
    rm -rf /root/.cache/pypoetry /root/.cache/pip

CMD ["/bin/bash"]

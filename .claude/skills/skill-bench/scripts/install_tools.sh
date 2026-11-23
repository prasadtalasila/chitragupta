#!/usr/bin/env bash
# Checks for, and installs, what the skill-bench skill's steps need
# (SKILL.md, "What you need"). Debian and Ubuntu with an NVIDIA GPU only:
# it installs with apt and builds llama.cpp with CUDA.
#
#   bash install_tools.sh          check, install what is missing, check again
#   bash install_tools.sh --check  check only; exit 1 if anything is missing
#
# Everything lands under BENCH_TOOLS (default ~/bench-tools): Codex and
# OpenCode in its npm/ prefix, llama.cpp in llama.cpp-b11321/, the model
# and its vision projector in models/. Only apt packages (cmake, a
# compiler, the CUDA compiler and the repository's own os-deps) go
# system-wide, through sudo unless run as root. The versions are pinned to the #1068 bench, so results stay
# comparable across the #1091 series: change one and every earlier
# baseline is void.
#
# The model's SHA-256 takes about a minute over 22 GB, so a verified hash
# is cached in models/<file>.verified with the file's size and mtime, and
# trusted only while both still match. The vision projector is pinned
# and checked the same way: without it llama-server answers Codex's
# first figure PNG with a 500 and the run ends there.
#
# The check uses bash builtins and the tools it looks for, nothing else,
# so tests/test_skill_bench_install_tools.py can run it against fakes.
set -uo pipefail

BENCH_TOOLS=${BENCH_TOOLS:-$HOME/bench-tools}
CODEX=0.159.3
OPENCODE=1.18.34
LLAMA=b11321
MODEL_REPO=unsloth/Qwen3.6-35B-A3B-GGUF
MODEL_NAME=Qwen3.6-35B-A3B-UD-Q4_K_M.gguf
MODEL_BYTES=22134528992
MODEL_SHA256=ac0e2c1189e055faa36eff361580e79c5bd6f8e76bffb4ce547f167d53e31a61
MODEL_FILE=${MODEL_FILE:-$BENCH_TOOLS/models/$MODEL_NAME}
MMPROJ_NAME=mmproj-F16.gguf
MMPROJ_BYTES=899283680
MMPROJ_SHA256=8971ee4f331ff0a4c609374f32984b3d4e6dc086c0aa35f1d637fad1829e887f
MMPROJ_FILE=${MMPROJ_FILE:-$BENCH_TOOLS/models/$MMPROJ_NAME}
LLAMA_DIR=$BENCH_TOOLS/llama.cpp-$LLAMA
PATH=$BENCH_TOOLS/npm/bin:$PATH

missing=()

found() { printf '%s: %s\n' "$1" "$2"; }
lacking() {
  printf '%s: missing%s\n' "$1" "${2:+, $2}"
  missing+=("$1")
}

# `pinned NAME WANT CMD...`: CMD's version output must contain WANT.
pinned() {
  local name=$1 want=$2 v
  shift 2
  v=$("$@" 2>/dev/null)
  if [[ $v == *"$want"* ]]; then found "$name" "$want"; else lacking "$name" "or not $want${v:+ ($v)}"; fi
}

# `pinned_file NAME FILE BYTES SHA256`: FILE must have that size and hash.
pinned_file() {
  local name=$1 file=$2 bytes=$3 want=$4 size mtime stamp sum
  [[ -f $file ]] || { lacking "$name" "$file"; return; }
  size=$(stat -c %s "$file")
  [[ $size == "$bytes" ]] || { lacking "$name" "$size bytes, not $bytes"; return; }
  mtime=$(stat -c %Y "$file")
  stamp="$file.verified"
  if [[ -f $stamp && $(<"$stamp") == "$size $mtime $want" ]]; then
    found "$name" "$file (sha256 verified)"
    return
  fi
  sum=$(sha256sum "$file" | cut -d' ' -f1)
  if [[ $sum == "$want" ]]; then
    printf '%s %s %s\n' "$size" "$mtime" "$sum" >"$stamp"
    found "$name" "$file (sha256 verified)"
  else
    lacking "$name" "sha256 $sum, not $want"
  fi
}

check() {
  missing=()
  pinned codex "$CODEX" codex --version
  pinned opencode "$OPENCODE" opencode --version
  if [[ -x $LLAMA_DIR/build/bin/llama-server ]]; then
    if [[ -e $LLAMA_DIR/build/bin/libggml-cuda.so ]]; then
      found llama-server "$LLAMA_DIR/build/bin/llama-server (CUDA)"
    else
      lacking llama-server "built without CUDA ($LLAMA_DIR)"
    fi
  else
    lacking llama-server "$LLAMA_DIR/build/bin/llama-server"
  fi
  pinned_file model "$MODEL_FILE" "$MODEL_BYTES" "$MODEL_SHA256"
  pinned_file mmproj "$MMPROJ_FILE" "$MMPROJ_BYTES" "$MMPROJ_SHA256"
  if [[ $(claude auth status 2>/dev/null) == *'"loggedIn": true'* ]]; then
    found claude "logged in"
  else
    lacking claude "or not logged in (run: claude, then /login)"
  fi
  for v in pdftotext lualatex; do
    if command -v "$v" >/dev/null; then found "$v" "$(command -v "$v")"; else lacking "$v"; fi
  done
  [[ ${#missing[@]} -eq 0 ]]
}

wants() { [[ " ${missing[*]} " == *" $1 "* ]]; }

# The NVIDIA apt repository for this distribution, and the newest CUDA
# toolkit the installed driver can run (`nvidia-smi` prints that).
install_cuda() {
  local sudo=$1 distro cuda tmp rc
  command -v nvcc >/dev/null && return 0
  ls /usr/local/cuda*/bin/nvcc >/dev/null 2>&1 && return 0
  # shellcheck source=/dev/null
  . /etc/os-release
  distro="$ID${VERSION_ID//./}"
  cuda=$(nvidia-smi | sed -n 's/.*CUDA Version: \([0-9]*\)\.\([0-9]*\).*/\1-\2/p')
  [[ -n $cuda ]] || { echo "nvidia-smi names no CUDA version: is the driver installed?" >&2; return 1; }
  # A private directory, never a fixed /tmp path: the package is
  # installed as root, so a file another user planted there first
  # would be what dpkg installs.
  tmp=$(mktemp -d) || return 1
  curl -fsSL -o "$tmp/cuda-keyring.deb" \
    "https://developer.download.nvidia.com/compute/cuda/repos/$distro/x86_64/cuda-keyring_1.1-1_all.deb" ||
    { rm -rf "$tmp"; return 1; }
  $sudo dpkg -i "$tmp/cuda-keyring.deb"
  rc=$?
  rm -rf "$tmp"
  [[ $rc -eq 0 ]] || return 1
  $sudo apt-get update -q || return 1
  $sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y -q \
    "cuda-nvcc-$cuda" "cuda-cudart-dev-$cuda" "libcublas-dev-$cuda" "cuda-cccl-$cuda"
}

install_llama() {
  local sudo=$1 nvcc arch
  $sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y -q cmake build-essential curl || return 1
  install_cuda "$sudo" || return 1
  nvcc=$(command -v nvcc || find /usr/local -maxdepth 3 -path '/usr/local/cuda*/bin/nvcc' | sort -V | tail -1)
  arch=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1 | tr -d .)
  mkdir -p "$BENCH_TOOLS" && rm -rf "$LLAMA_DIR"
  curl -fsSL "https://codeload.github.com/ggml-org/llama.cpp/tar.gz/refs/tags/$LLAMA" |
    tar xz -C "$BENCH_TOOLS" || return 1
  PATH=$(dirname "$nvcc"):$PATH cmake -S "$LLAMA_DIR" -B "$LLAMA_DIR/build" -DGGML_CUDA=ON \
    -DCMAKE_CUDA_ARCHITECTURES="$arch" -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release >/dev/null || return 1
  PATH=$(dirname "$nvcc"):$PATH cmake --build "$LLAMA_DIR/build" -j "$(nproc)" --target llama-server >/dev/null
}

install() {
  local sudo=""
  if ! command -v apt-get >/dev/null; then
    echo "no apt-get here: install what is missing by hand (SKILL.md, \"What you need\")" >&2
    return 1
  fi
  [[ $EUID -eq 0 ]] || sudo=sudo
  if wants codex || wants opencode; then
    npm install -g --prefix "$BENCH_TOOLS/npm" "@openai/codex@$CODEX" "opencode-ai@$OPENCODE" || return 1
  fi
  if wants llama-server; then install_llama "$sudo" || return 1; fi
  if wants model; then
    mkdir -p "$(dirname "$MODEL_FILE")"
    curl -fL -C - -o "$MODEL_FILE" "https://huggingface.co/$MODEL_REPO/resolve/main/$MODEL_NAME" || return 1
  fi
  if wants mmproj; then
    mkdir -p "$(dirname "$MMPROJ_FILE")"
    curl -fL -C - -o "$MMPROJ_FILE" "https://huggingface.co/$MODEL_REPO/resolve/main/$MMPROJ_NAME" || return 1
  fi
  if wants pdftotext || wants lualatex; then
    bash "$(dirname "$0")/../../../../scripts/install_full_pipeline.sh" os-deps || return 1
  fi
  if wants claude; then
    echo "claude is not logged in: run claude and /login yourself; this script cannot" >&2
  fi
}

if [[ ${1:-} == --check ]]; then
  check || exit 1
elif ! check; then
  echo "installing: ${missing[*]}"
  install && check || exit 1
fi
# The literal $PATH is the point: the line is pasted into a shell.
# shellcheck disable=SC2016
printf 'PATH=%s:$PATH\n' "$BENCH_TOOLS/npm/bin"

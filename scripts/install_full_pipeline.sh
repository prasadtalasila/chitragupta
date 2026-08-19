#!/usr/bin/env bash
# Single install path for both a bare host and the Docker image -- one
# source of truth for how every dependency gets installed (OS packages
# and the Python venv), so a fix discovered on one target
# automatically applies to both, instead of drifting between a hand-run
# host command and separate Dockerfile RUN lines.
#
# Usage: bash scripts/install_full_pipeline.sh [STAGE ...]
#
#   python-deps  (default if no STAGE given) -- venv + `poetry install
#                --with enrich` (see pyproject.toml/poetry.lock). What
#                every host needs regardless of which OS packages are
#                present. Poetry is a dependency/lockfile manager here
#                only -- package-mode = false in pyproject.toml, nothing
#                is published or pip-installable from this repo.
#   os-deps      -- apt-get the system packages the full pipeline needs
#                (TeX Live, Pandoc, poppler-utils, Poetry itself,
#                git/curl/unzip, and OpenCV's runtime libraries). Needs
#                root; auto-sudo's if not already root. Opt-in -- not
#                everyone wants this script touching apt.
#   dev-deps     -- `poetry install --with dev` (pytest, pytest-cov) into
#                the same venv as python-deps. Only needed to run the
#                test suite, not the pipeline itself -- opt-in, and not
#                part of `all`. Run `python-deps` first.
#   all          -- os-deps + python-deps.
#
# Host usage:
#   bash scripts/install_full_pipeline.sh all
#   bash scripts/install_full_pipeline.sh dev-deps   # optional, to run tests
#   then: .venv-full/bin/python -m src.corpus sync
#         .venv-full/bin/python -m src.enrich
#         .venv-full/bin/python -m pytest
#
# Docker usage: docker/Dockerfile calls this once per stage as separate
# RUN lines (os-deps, then python-deps with SKIP_VENV=1 into the
# /opt/venv it creates) so each stage is its own cached layer -- editing
# later Dockerfile content or repo files doesn't force earlier ones to
# rebuild.
#
# Why Poetry doesn't need its own venv-creation step, in either target:
# `poetry.toml` (committed, project-local) sets `virtualenvs.create =
# false`, so Poetry always installs into whatever venv `VIRTUAL_ENV`
# points at rather than making its own -- this script still creates that
# venv itself (python3 -m venv on a bare host; already done by
# docker/Dockerfile via a separate RUN line for /opt/venv), then exports
# VIRTUAL_ENV before calling `poetry install`. One mechanism for both
# targets, instead of Poetry inventing a second, differently-named venv
# convention (its own in-project mode always calls the directory
# `.venv`, which would silently orphan the existing `.venv-full` this
# script and every doc already reference).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"


sudo_if_needed() {
    if [[ "$(id -u)" == "0" ]]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        echo "Need root to run: $*" >&2
        echo "Re-run this script as root, or install sudo." >&2
        exit 1
    fi
}

install_os_deps() {
    echo "Installing OS packages (TeX Live, Pandoc, poppler-utils, OpenCV runtime, Poetry) ..."
    sudo_if_needed apt-get update
    # GLib's package was renamed in the 64-bit-time_t transition
    # (libglib2.0-0 -> libglib2.0-0t64 in Ubuntu 24.04 / Debian 13), and
    # apt-get takes no alternatives on the command line -- so pick
    # whichever name this release actually has rather than hardcoding one
    # and breaking every host on the other side of the rename.
    # `policy` rather than `show`: after the rename the old name survives
    # in the index as a record with no installation candidate, so `show`
    # succeeds on a name `install` then refuses. The candidate line is
    # the thing that actually answers "can this be installed here" --
    # measured on Debian 13, where libglib2.0-0 reports
    # "Candidate: (none)" and libglib2.0-0t64 reports a version.
    #
    # Captured into a variable rather than piped into grep, because this
    # script runs under `set -o pipefail` and `grep -q` exits at its
    # first match: apt-cache then takes SIGPIPE, the pipeline reports
    # failure, and the fallback fires on the release where the probe
    # just *succeeded*. Caught by testing the branch rather than by
    # reading it -- it selects the wrong name every time.
    glib_pkg="libglib2.0-0t64"
    glib_policy="$(apt-cache policy "$glib_pkg" 2>/dev/null || true)"
    case "$glib_policy" in
        ""|*"Candidate: (none)"*) glib_pkg="libglib2.0-0" ;;
    esac
    sudo_if_needed apt-get install -y --no-install-recommends \
        python3 python3-venv python3-pip \
        python3-poetry \
        poppler-utils \
        git curl ca-certificates unzip zip \
        pandoc \
        texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended latexmk \
        lmodern texlive-pictures \
        texlive-binaries texlive-publishers \
        libgl1 "$glib_pkg"
    # python3-poetry (apt), not `pip install poetry`: PEP 668 blocks bare
    # pip on this host regardless of root (see AGENTS.md), and Poetry is
    # itself the thing python-deps below shells out to -- it can't
    # bootstrap itself via the same pip it's meant to replace.
    # lmodern (the LaTeX package providing lmodern.sty) is a separate
    # Debian package from fonts-lmodern (just the OTF font files) --
    # texlive-latex-recommended pulls in the latter but not the former.
    # Pandoc's default LaTeX template \usepackage{lmodern}s unconditionally,
    # so without it every pandoc/pdflatex render fails with "File
    # `lmodern.sty' not found", not a docling-side problem. Found
    # by hand rendering a real draft after the rest of the toolchain
    # reported fine.
    # texlive-pictures ships tikz.sty (Debian/Ubuntu, confirmed via
    # `dpkg -S`) -- src/render_output.py loads it conditionally for a
    # draft with a \input/\include'd TikZ figure (#222), and none of the
    # packages above pull it in.
    # texlive-binaries owns /usr/bin/bibtex (confirmed via `dpkg -S` on
    # the alternative's target) and texlive-publishers ships IEEEtran.bst.
    # Named explicitly rather than relied on transitively, because the
    # thing that needs them is a *book*: a LaTeX-side bibliography, in
    # IEEE style, for a document assembled from many units
    # (docs/BOOKS.md). Nothing else here needs either -- every ordinary
    # render resolves citations with pandoc's citeproc against
    # assets/csl/ieee.csl and emits no \cite at all -- which is exactly
    # why they were missing until a real book was built.
    # natbib is deliberately not preferred: its default author-year
    # markers are not this project's house citation style, and every
    # other genre skill produces IEEE numeric.
    # zip/unzip: scripts/release.py itself only needs stdlib zipfile,
    # not these binaries -- they're here so a human can inspect/repack a
    # release archive by hand.
    # libgl1 + GLib are for OpenCV, which nothing here asks for directly:
    # the enrich group's `docling` pulls `docling-slim[standard]`, which
    # pulls `rapidocr`, which requires the `opencv-python` distribution by
    # name -- the GUI-linked wheel, not `opencv-python-headless`. Its
    # cv2.abi3.so vendors Qt but *not* libGL.so.1, libglib-2.0.so.0 or the
    # X libraries libgl1 pulls in -- ldd resolves those to the system, and
    # a base image installed with --no-install-recommends
    # (docker/Dockerfile's ubuntu:24.04, and any host provisioned only by
    # this stage) has none of them, so `import cv2` fails.
    # That error is never the one you see. src/pdf_text.py's forkserver
    # preloads docling, `forkserver.main()` catches ImportError and
    # discards it, and cv2's own loader leaves `sys.OpenCV_LOADER` set
    # when its bootstrap dies partway -- so every worker forked afterwards
    # reports 'recursion is detected during loading of "cv2" binary
    # extensions' instead, and `python -m src.corpus sync` fails every document
    # with a message naming neither PDFs nor the missing library. See
    # docs/PDF-PARSER.md's troubleshooting entry.
    # Pinning opencv-python-headless instead does not work: rapidocr
    # requires opencv-python by distribution name, so both would install
    # and clobber the same cv2/ directory.

    install_vale
}

# Vale, the prose linter `python -m src.draft style` shells out to. Not in
# the Debian/Ubuntu archives, so this is a release tarball rather than an
# apt package -- the one binary this script fetches by hand, and the
# reason it verifies a checksum before unpacking anything.
#
# Pinned, not "latest", for the reason assets/vale/README.md gives: a Vale
# release can change how a format is scoped, which silently moves the
# quoted-span exemptions the checks depend on. Moving this pin means
# re-running bench/ against the shipped drafts, not just bumping a number.
#
# Absent Vale is not an error here or anywhere else: `src.draft style`
# probes for it and reports missing-binary, exactly as render does for
# pandoc, so a host that skips this keeps every other capability.
VALE_VERSION="3.9.1"
VALE_SHA256="fbc2eb47d0b8c50220ed1a2c5c611fbe0904ed567d638143d482016a18fd2db0"

install_vale() {
    if command -v vale >/dev/null 2>&1; then
        echo "vale already installed: $(vale --version)"
        return 0
    fi
    case "$(uname -m)" in
        x86_64|amd64) vale_arch="64-bit" ;;
        *)
            echo "WARNING: no pinned Vale build for $(uname -m); skipping." >&2
            echo "         python -m src.draft style will report it as missing." >&2
            return 0
            ;;
    esac
    vale_tmp="$(mktemp -d)"
    vale_url="https://github.com/errata-ai/vale/releases/download/v${VALE_VERSION}/vale_${VALE_VERSION}_Linux_${vale_arch}.tar.gz"
    if ! curl -fsSL -o "${vale_tmp}/vale.tar.gz" "$vale_url"; then
        echo "WARNING: could not download Vale from $vale_url; skipping." >&2
        rm -rf "$vale_tmp"
        return 0
    fi
    # Verified before it is unpacked, not after: this is the only file
    # this script takes from outside the distribution's archives.
    if ! echo "${VALE_SHA256}  ${vale_tmp}/vale.tar.gz" | sha256sum -c --status; then
        echo "ERROR: Vale checksum mismatch -- refusing to install." >&2
        echo "       expected ${VALE_SHA256}" >&2
        echo "       got      $(sha256sum "${vale_tmp}/vale.tar.gz" | cut -d' ' -f1)" >&2
        rm -rf "$vale_tmp"
        return 1
    fi
    tar xzf "${vale_tmp}/vale.tar.gz" -C "$vale_tmp" vale
    sudo_if_needed install -m 0755 "${vale_tmp}/vale" /usr/local/bin/vale
    rm -rf "$vale_tmp"
    echo "installed $(vale --version)"
}

check_poetry() {
    if ! command -v poetry >/dev/null 2>&1; then
        echo "poetry not found. Run '$0 os-deps' first (installs python3-poetry)," >&2
        echo "or install Poetry manually: https://python-poetry.org/docs/#installation" >&2
        exit 1
    fi
}

# POSIX venvs (python3 -m venv on Linux/macOS) put the interpreter/pip
# under bin/; a native Windows Python's venv module uses Scripts/
# instead -- this script's own callers (below) and CI
# (.github/workflows/ci.yml's windows-latest leg) both need to work with
# either layout, so every bin/-hardcoded path goes through this instead.
venv_bin_dir() {
    local venv_dir="$1"
    if [[ -x "$venv_dir/bin/python" || -x "$venv_dir/bin/python3" ]]; then
        echo "$venv_dir/bin"
    else
        echo "$venv_dir/Scripts"
    fi
}

# Resolves (and creates, unless SKIP_VENV=1) the venv this script's
# `poetry install` calls target, and exports VIRTUAL_ENV so Poetry uses
# it -- poetry.toml's `virtualenvs.create = false` means Poetry will
# never make its own, by design (see the header comment for why).
resolve_venv_dir() {
    if [[ "${SKIP_VENV:-0}" == "1" ]]; then
        VENV_DIR="${VIRTUAL_ENV:-/opt/venv}"
    else
        if [[ "$(id -u)" == "0" ]]; then
            echo "Warning: running as root (e.g. via sudo) will create a root-owned" >&2
            echo ".venv-full/ that your normal user can't later modify or remove" >&2
            echo "without sudo. Re-run without sudo, or set SKIP_VENV=1 if this is" >&2
            echo "intentional (e.g. inside Docker, where /opt/venv is already root-owned)." >&2
        fi
        VENV_DIR="${VENV_DIR:-$REPO_ROOT/.venv-full}"
        if [[ ! -d "$VENV_DIR" ]]; then
            python3 -m venv "$VENV_DIR"
        fi
    fi
    export VIRTUAL_ENV="$VENV_DIR"
}

install_python_deps() {
    check_poetry
    resolve_venv_dir

    # Sonar (S8541) flags every `poetry install` here because an sdist in
    # the resolution runs its setup script at build time. A wheels-only
    # refusal (`installer.only-binary :all:`, as docs.yml now sets for its
    # own group) is not available to *this* install: bibtexparser 1.4.x --
    # a main-group runtime dependency -- ships no wheel at all, so
    # forcing wheels breaks the resolve outright. What stands in its
    # place is the lockfile: every package, sdists included, is
    # hash-pinned in poetry.lock, so the archive whose setup script runs
    # is byte-exact the one that was locked, not whatever the index
    # serves that day.
    (cd "$REPO_ROOT" && poetry install --with enrich)
    local bin_dir
    bin_dir="$(venv_bin_dir "$VENV_DIR")"
    ensure_gpu_torch "$bin_dir/pip" "$bin_dir/python"

    echo
    echo "Installed. Run pipeline scripts via:"
    echo "  $bin_dir/python -m src.corpus sync"
    echo "  $bin_dir/python -m src.enrich"
}

# pip's default torch wheel is built against whatever CUDA major version
# is current upstream (cu130 as of torch 2.13) -- it silently falls back
# to CPU-only at runtime (`torch.cuda.is_available() == False`, no error)
# on any host whose NVIDIA driver predates that CUDA version, which is
# common: driver upgrades lag well behind PyTorch releases, and a driver
# reporting e.g. "CUDA Version: 12.5" (`nvidia-smi`'s ceiling, not a
# minimum) cannot run a cu130 wheel. Found by hand on an A40 host with
# driver 555.42.02: sentence-transformers/docling/bertopic all installed
# clean, but silently ran on CPU. Older CUDA-tagged wheels (e.g. cu124)
# work fine on newer drivers -- CUDA is backward compatible within a
# driver's supported range -- so on a GPU host we detect the driver's
# ceiling and reinstall from the newest wheel tag at or under it, instead
# of leaving a GPU host silently CPU-bound.
ensure_gpu_torch() {
    local pip="$1"
    local python_bin="$2"

    if ! command -v nvidia-smi >/dev/null 2>&1; then
        return  # no GPU on this host -- default (CPU) wheel is correct as-is
    fi

    if "$python_bin" -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
        echo "torch already sees the GPU (driver supports its bundled CUDA build)."
        return
    fi

    local driver_cuda
    driver_cuda="$(nvidia-smi 2>/dev/null | grep -oP 'CUDA Version:\s*\K[0-9]+\.[0-9]+' | head -1)"
    if [[ -z "$driver_cuda" ]]; then
        echo "Warning: nvidia-smi is present but its CUDA ceiling couldn't be" >&2
        echo "parsed -- leaving torch as installed (may be CPU-only)." >&2
        return
    fi

    # Only the single newest tag at or under the driver's ceiling is
    # attempted, not a cascade down through older ones: this is a
    # reinstall, so an attempt that "succeeds" (exit 0) but still doesn't
    # detect the GPU would otherwise leave torch progressively
    # downgraded, one tag older each time -- worse than the CPU-only
    # default it started from, while still printing a "just CPU" warning
    # that undersells how far it drifted.
    local tag tag_ver best_tag="" best_ver=""
    for tag in cu130 cu129 cu128 cu126 cu124 cu121 cu118; do
        tag_ver="${tag#cu}"
        tag_ver="${tag_ver:0:-1}.${tag_ver: -1}"
        if [[ "$(awk -v a="$driver_cuda" -v b="$tag_ver" 'BEGIN{print (b<=a)?1:0}')" == "1" ]]; then
            best_tag="$tag"
            best_ver="$tag_ver"
            break
        fi
    done

    if [[ -z "$best_tag" ]]; then
        echo "Warning: driver's CUDA ceiling (${driver_cuda}) is older than every" >&2
        echo "torch CUDA wheel tag this script knows about. Leaving the default" >&2
        echo "wheel installed (CPU-only on this driver) -- upgrade the NVIDIA" >&2
        echo "driver, or install a matching torch build by hand from" >&2
        echo "https://pytorch.org/get-started/locally/." >&2
        return
    fi

    echo "GPU present but torch can't see it (driver's CUDA ceiling is" \
         "${driver_cuda}, older than the default wheel's build). Reinstalling" \
         "from the ${best_tag} wheel index (needs driver CUDA <= ${best_ver}) ..."

    # --force-reinstall, and no --extra-index-url: pip's "upgrade only if
    # needed" logic otherwise compares bare version numbers (e.g. 2.13.0
    # vs 2.6.0+cu124) and treats the already-installed default wheel as
    # newer, silently keeping it -- discovered by hand when the first cut
    # of this reported success without ever actually swapping the wheel.
    # Restricting to a single cu-tagged index is also required, not just
    # tidy: it's what forces pip to resolve torch's own pure-Python deps
    # (numpy, sympy, jinja2, ...) from that same CUDA-tagged set rather
    # than drifting back to plain PyPI's higher-numbered ones. Output is
    # left unsilenced (unlike the rest of this script's pip calls aren't
    # either) -- an install failure here needs to be as debuggable as any
    # other, not swallowed just because it's a fallback path.
    if "$pip" install --force-reinstall \
        --index-url "https://download.pytorch.org/whl/${best_tag}" \
        "torch" "torchvision" \
        && "$python_bin" -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
        echo "torch now sees the GPU via the ${best_tag} wheel."
        return
    fi

    echo "Warning: reinstalling torch from ${best_tag} didn't make the GPU" >&2
    echo "visible. Restoring the default wheel via 'poetry install --with enrich'" >&2
    echo "(CPU-only on this driver, but at least back to a known, lockfile-" >&2
    echo "tracked state) ..." >&2
    (cd "$REPO_ROOT" && poetry install --with enrich)
}

install_dev_deps() {
    check_poetry
    local venv_dir="${VENV_DIR:-$REPO_ROOT/.venv-full}"
    local bin_dir
    bin_dir="$(venv_bin_dir "$venv_dir")"
    if [[ ! -x "$bin_dir/pip" ]]; then
        echo "No venv at ${venv_dir} -- run '$0 python-deps' first." >&2
        exit 1
    fi
    export VIRTUAL_ENV="$venv_dir"

    (cd "$REPO_ROOT" && poetry install --with dev)
    # `poetry install --with dev` re-resolves the whole lock file, not
    # just the newly-added group -- it's additive against what's already
    # installed (verified by hand: running this after `python-deps` did
    # not remove the enrich group), but it can still touch transitive
    # packages shared with the enrich group, torch included. Re-run the
    # same GPU check as python-deps rather than assume it's still fine.
    ensure_gpu_torch "$bin_dir/pip" "$bin_dir/python"

    echo
    echo "Installed. Run the test suite via:"
    echo "  ${bin_dir}/python -m pytest --cov=src --cov=scripts --cov-report=term-missing"
}

STAGES=("$@")
if [[ ${#STAGES[@]} -eq 0 ]]; then
    STAGES=("python-deps")
fi

for stage in "${STAGES[@]}"; do
    case "$stage" in
        os-deps) install_os_deps ;;
        python-deps) install_python_deps ;;
        dev-deps) install_dev_deps ;;
        # Vale alone, without the TeX Live and poppler that os-deps also
        # brings. os-deps installs it too; this target exists because CI's
        # lint job wants the prose linter and nothing else, and because
        # sourcing this script to reach the function runs the dispatcher
        # below with no stage -- which defaults to python-deps and fails
        # on a runner that has no poetry.
        vale) install_vale ;;
        all) install_os_deps; install_python_deps ;;
        *)
            echo "Unknown stage: $stage" >&2
            echo "Expected one of: os-deps, python-deps, dev-deps, vale, all" >&2
            exit 1
            ;;
    esac
done

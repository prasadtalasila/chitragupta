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
#                present. Poetry is a dependency/lockfile manager here,
#                for a checkout, Docker and CI -- `pip install
#                'chitragupta-cli[enrich]'` is the equivalent for someone
#                who installed the package rather than cloned it (#265;
#                `chitragupta install` refuses this stage by name and
#                prints that command, rather than running it a second way).
#   os-deps      -- apt-get the system packages the full pipeline needs
#                (TeX Live, Pandoc, poppler-utils, Poetry itself,
#                git/curl/unzip, OpenCV's runtime libraries, and
#                python-is-python3 -- the name `python`, which the
#                Claude Code hooks are launched by). Needs
#                root; auto-sudo's if not already root. Opt-in -- not
#                everyone wants this script touching apt. Also reachable
#                as `chitragupta install os-deps` (#265), unmodified.
#   dev-deps     -- `poetry install --with dev` (pytest, pytest-cov) into
#                the same venv as python-deps, plus the two things needed
#                to *change* this repository rather than run it: the
#                pinned `actionlint` binary, and `core.hooksPath` pointed
#                at git-hooks/ so the tracked pre-commit hook fires. Only
#                needed to run the test suite and commit, not the pipeline
#                itself -- opt-in, and not part of `all`. Run
#                `python-deps` first.
#   actionlint   -- the workflow linter alone, without the venv dev-deps
#                also builds. CI's lint job wants exactly this, the same
#                reason `vale` is a stage of its own.
#   gpu-torch    -- calls ensure_gpu_torch (below) directly, pointed at
#                CHITRAGUPTA_PIP/CHITRAGUPTA_PYTHON rather than this
#                script's own venv -- what `chitragupta install gpu-torch`
#                (#265) reaches, for someone who pip-installed rather than
#                cloned. Not part of `all` or `python-deps`, which already
#                call ensure_gpu_torch themselves against their own venv.
#   all          -- os-deps + python-deps.
#
# Host usage:
#   bash scripts/install_full_pipeline.sh all
#   bash scripts/install_full_pipeline.sh dev-deps   # optional, to run tests
#   then: .venv-full/bin/python -m chitragupta.corpus sync
#         .venv-full/bin/python -m chitragupta.enrich
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

# Can this release actually install PKG? Two callers in install_os_deps
# need it -- the GLib 64-bit-time_t rename picks between two names, and
# python-is-python3 is dropped entirely where it does not exist -- and
# both exist because `apt-get install` takes no alternatives on the
# command line: one absent name fails the whole stage, TeX Live and
# Pandoc with it.
#
# `policy` rather than `show`: after a rename the old name survives in the
# index as a record with no installation candidate, so `show` succeeds on
# a name `install` then refuses. The candidate line is the thing that
# actually answers "can this be installed here" -- measured on Debian 13,
# where libglib2.0-0 reports "Candidate: (none)" and libglib2.0-0t64
# reports a version.
#
# Captured into a variable rather than piped into grep, because this
# script runs under `set -o pipefail` and `grep -q` exits at its first
# match: apt-cache then takes SIGPIPE, the pipeline reports failure, and
# the caller's fallback fires on the release where the probe just
# *succeeded*. Caught by testing the branch rather than by reading it --
# it selects the wrong name every time.
apt_has_candidate() {
    local policy
    policy="$(apt-cache policy "$1" 2>/dev/null || true)"
    case "$policy" in
        ""|*"Candidate: (none)"*) return 1 ;;
    esac
    return 0
}

install_os_deps() {
    echo "Installing OS packages (TeX Live, Pandoc, poppler-utils, OpenCV runtime, Poetry,"
    echo "the python-is-python3 launcher name) ..."
    sudo_if_needed apt-get update
    # GLib's package was renamed in the 64-bit-time_t transition
    # (libglib2.0-0 -> libglib2.0-0t64 in Ubuntu 24.04 / Debian 13), and
    # apt-get takes no alternatives on the command line -- so pick
    # whichever name this release actually has rather than hardcoding one
    # and breaking every host on the other side of the rename.
    glib_pkg="libglib2.0-0t64"
    apt_has_candidate "$glib_pkg" || glib_pkg="libglib2.0-0"
    # `python-is-python3` is what puts the *name* `python` on PATH. It is
    # here rather than in a doc because nothing else can put it there:
    # `.claude/settings.json` launches every hook this repository
    # registers as `python` (docs/HOOKS.md records why that name and not
    # `python3` -- a venv guarantees `python` on every platform and
    # `python3` only on POSIX), and on Debian and Ubuntu that name does
    # not exist outside an activated venv. A launcher that does not
    # resolve produces *nothing at all* -- no error, no log line, measured
    # on 2026-08-15 and recorded in chitragupta/hook_launchers.py -- so the
    # citation gate stops running while settings.json still lists it and
    # every test still passes. Drafts then land ungated, which is the one
    # failure CLAUDE.md's binding rule exists to prevent.
    #
    # Probed rather than named outright, for the reason apt_has_candidate
    # states: a release that does not carry this package would otherwise
    # fail the whole stage -- TeX Live and Pandoc included -- over one
    # convenience symlink. Emptied rather than left set, so the expansion
    # below contributes no argument at all on such a host.
    launcher_pkg="python-is-python3"
    if ! apt_has_candidate "$launcher_pkg"; then
        echo "Note: $launcher_pkg is unavailable on this release -- skipping." >&2
        echo "If \`python\` is not on your PATH, Claude Code's hooks cannot" >&2
        echo "start (docs/HOOKS.md); symlink it to python3 by hand." >&2
        launcher_pkg=""
    fi
    sudo_if_needed apt-get install -y --no-install-recommends \
        python3 python3-venv python3-pip ${launcher_pkg:+"$launcher_pkg"} \
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
    # `dpkg -S`) -- chitragupta/render_output.py loads it conditionally for a
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
    # That error is never the one you see. chitragupta/pdf_text.py's forkserver
    # preloads docling, `forkserver.main()` catches ImportError and
    # discards it, and cv2's own loader leaves `sys.OpenCV_LOADER` set
    # when its bootstrap dies partway -- so every worker forked afterwards
    # reports 'recursion is detected during loading of "cv2" binary
    # extensions' instead, and `python -m chitragupta.corpus sync` fails every document
    # with a message naming neither PDFs nor the missing library. See
    # docs/PDF-PARSER.md's troubleshooting entry.
    # Pinning opencv-python-headless instead does not work: rapidocr
    # requires opencv-python by distribution name, so both would install
    # and clobber the same cv2/ directory.

    install_vale
}

# Vale, the prose linter `python -m chitragupta.draft style` shells out to. Not in
# the Debian/Ubuntu archives, so this is a release tarball rather than an
# apt package -- one of the two binaries this script fetches by hand
# (`install_actionlint` below is the other), and the reason it verifies a
# checksum before unpacking anything.
#
# Pinned, not "latest", for the reason assets/vale/README.md gives: a Vale
# release can change how a format is scoped, which silently moves the
# quoted-span exemptions the checks depend on. Moving this pin means
# re-running bench/ against the shipped drafts, not just bumping a number.
#
# Absent Vale is not an error here or anywhere else: `chitragupta.draft style`
# probes for it and reports missing-binary, exactly as render does for
# pandoc, so a host that skips this keeps every other capability.
# actionlint checks .github/workflows/. Pinned and digest-verified for
# the same reason Vale is: these two are the only files this script takes
# from outside the distribution's archives. 5.8 MB as a released binary --
# fetching it through a pre-commit framework instead builds a full Go
# toolchain to compile it from source, measured at 340-370 MB of cache,
# which is why this is a curl and not a framework.
ACTIONLINT_VERSION="1.7.12"
ACTIONLINT_SHA256="8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8"

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
            echo "         python -m chitragupta.draft style will report it as missing." >&2
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
    # Verified before it is unpacked, not after: this and the actionlint
    # tarball are the two files this script takes from outside the
    # distribution's archives (#512/m-86 -- this said "the only file"
    # until actionlint became the second).
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

install_actionlint() {
    if command -v actionlint >/dev/null 2>&1; then
        echo "actionlint already installed: $(actionlint --version | head -1)"
        return 0
    fi
    # Every path below warns and returns 0 rather than exiting, because
    # this is called from `dev-deps` -- which the Windows CI leg runs to
    # get pytest, and which a developer runs to get the test suite. A
    # workflow linter that cannot install is a reason to skip the commit
    # hook, never a reason to fail the install of everything else. The
    # one exception is a checksum mismatch, which stays fatal.
    #
    # `install_vale` has no such guard, and the reason is *not* that it
    # runs somewhere harmless -- it is reached from `install_os_deps` as
    # well as from the `vale` stage, so on the Linux leg a checksum
    # mismatch there fails `os-deps` and takes the whole test job with it,
    # not just the lint job (#512/m-86, correcting a comment that said
    # otherwise). That is the intended severity for a tampered download.
    # What this function must not do is fail on a host where it cannot
    # install at all: adding it to `dev-deps` is what put it on Windows,
    # and the first CI run said so -- `install -m 0755 ... /usr/local/bin`
    # needs root, Git Bash has no sudo, and the whole step failed before
    # pytest ran.
    if [[ "$(uname -s)" != "Linux" ]]; then
        echo "NOTE: only a Linux actionlint build is pinned here; skipping on $(uname -s)." >&2
        echo "      git-hooks/pre-commit will report it as missing, and CI still checks workflows." >&2
        return 0
    fi
    case "$(uname -m)" in
        x86_64|amd64) actionlint_arch="amd64" ;;
        aarch64|arm64) actionlint_arch="arm64" ;;
        *)
            echo "WARNING: no pinned actionlint build for $(uname -m); skipping." >&2
            echo "         git-hooks/pre-commit will report it as missing." >&2
            return 0
            ;;
    esac
    # Only the amd64 digest is pinned, so an arm64 host is told rather
    # than silently given an unverified binary. Verifying one archive
    # against another architecture's digest would fail confusingly.
    if [[ "$actionlint_arch" != "amd64" ]]; then
        echo "WARNING: only the amd64 actionlint digest is pinned; skipping $actionlint_arch." >&2
        return 0
    fi
    actionlint_tmp="$(mktemp -d)"
    actionlint_url="https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_linux_${actionlint_arch}.tar.gz"
    if ! curl -fsSL -o "${actionlint_tmp}/actionlint.tar.gz" "$actionlint_url"; then
        echo "WARNING: could not download actionlint from $actionlint_url; skipping." >&2
        rm -rf "$actionlint_tmp"
        return 0
    fi
    # Verified before it is unpacked, not after -- the same rule, and the
    # same reason, install_vale states below.
    if ! echo "${ACTIONLINT_SHA256}  ${actionlint_tmp}/actionlint.tar.gz" | sha256sum -c --status; then
        echo "ERROR: actionlint checksum mismatch -- refusing to install." >&2
        echo "       expected ${ACTIONLINT_SHA256}" >&2
        rm -rf "$actionlint_tmp"
        return 1
    fi
    tar xzf "${actionlint_tmp}/actionlint.tar.gz" -C "$actionlint_tmp" actionlint
    # Not sudo_if_needed: that exits 1 where it cannot elevate, which is
    # right for os-deps and wrong here (see the note above). A host with
    # no root gets the warning and keeps its test suite.
    if [[ "$(id -u)" == "0" ]] || command -v sudo >/dev/null 2>&1; then
        sudo_if_needed install -m 0755 "${actionlint_tmp}/actionlint" /usr/local/bin/actionlint
        echo "actionlint installed: $(actionlint --version | head -1)"
    else
        echo "NOTE: no root and no sudo, so actionlint was not installed to /usr/local/bin." >&2
        echo "      Put it on PATH by hand to enable the commit hook:" >&2
        echo "      $actionlint_url" >&2
    fi
    rm -rf "$actionlint_tmp"
}

install_git_hooks() {
    # A hook directory git does not know about is inert, and inert is the
    # failure docs/HOOKS.md exists to prevent -- the settings file still
    # lists it, the tests still pass, and nothing runs. Pointing
    # core.hooksPath at the tracked directory is what makes the checked-in
    # hook actually fire, and it is per-clone config, so it has to be set
    # by an install step rather than committed.
    if ! git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
        echo "Not a git checkout -- skipping the pre-commit hook." >&2
        return 0
    fi
    git -C "$REPO_ROOT" config core.hooksPath git-hooks
    echo "git hooks enabled: core.hooksPath=git-hooks"
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

# Can the *harness's* hook launchers start on this host? Not a question
# about the venv this script just built -- `.claude/settings.json` names
# `python`, and Claude Code starts it from the shell the user launched the
# session in, not from here.
#
# `os-deps` above installs the package that fixes the Debian case, but it
# needs apt and root and is opt-in, so a host that ran `python-deps` alone
# still has the fault and -- because a dead launcher is silent -- no way
# to find out. That asymmetry is why this report exists at all: it is the
# half that reaches every host.
#
# The check is chitragupta/hook_launchers.py's own `faults()`, called rather
# than reimplemented in shell. It already answers both halves of the
# question (is the name on PATH, and can that interpreter import the
# package), it is standard-library-only and imports no other chitragupta
# module, and a second copy here would be a second place for the answer to
# drift -- the invariant DEVELOPER-AGENTS.md states for this script
# generally. The settings path is passed explicitly rather than left to
# that module's own cwd walk, because this script may be run from
# anywhere.
#
# Run through the venv's interpreter, which is the one that can import the
# package; what it *measures* is this script's own un-activated PATH,
# which is the closest thing available to the harness's view.
report_launcher_faults() {
    local python_bin="$1"
    local faults fault
    # `|| true` and a discarded stderr: this is a courtesy report at the
    # end of a *successful* install. A probe that itself fails -- an
    # interpreter too old, a settings file mid-edit -- must not turn a
    # working venv into a failed run, which `set -e` would otherwise do.
    # Spelled as `if !` rather than `... || true`, which is what this was:
    # rule SC2015 rejects `A && B || C`, because C also runs when A
    # succeeds and B fails, and CI holds this file at a zero-findings bar.
    # The explicit form says the intended thing anyway -- a probe that
    # cannot run reports nothing and the install still succeeds.
    #
    # (Note for whoever edits this comment: a line whose first word after
    # `#` is the linter's own name parses as a *directive*, not a comment,
    # and fails the file with SC1073. Hence the circumlocution above.)
    #
    # `cd "$REPO_ROOT"` is load-bearing twice over, and both halves were
    # found by running this rather than reading it. `python -` takes its
    # script on stdin and puts the *current directory* on `sys.path`, and
    # `poetry install` above does not put this package into the venv's
    # site-packages -- so from any other directory the import below fails,
    # `|| true` swallows it, and the report silently finds nothing. That
    # is the exact failure mode this function exists to warn about, which
    # would have made it a courtesy that never fires. It also fixes what
    # the *child* probe sees: `faults()` spawns `<launcher> -c "import
    # chitragupta"`, which inherits this directory, so in a checkout the
    # bare interpreter resolves the package the same way tier 1 does
    # (docs/CLI.md) instead of reporting a fault a real hook would not hit.
    # `-c` with a quoted variable rather than a here-document. The
    # heredoc-inside-`$( )` form this started as parses under `bash -n`
    # and then fails at *run* time ("syntax error near unexpected token
    # `||'"), because bash defers parsing a command substitution's body --
    # so the syntax check every other line here is covered by does not
    # cover that one. Found by running the function, not by reading it.
    local probe='import sys
from pathlib import Path

from chitragupta import hook_launchers

sys.stdout.write("\n".join(hook_launchers.faults(Path(sys.argv[1]))))'
    if ! faults="$(cd "$REPO_ROOT" \
        && "$python_bin" -c "$probe" "$REPO_ROOT/.claude/settings.json" 2>/dev/null)"; then
        return 0
    fi
    [[ -n "$faults" ]] || return 0
    echo >&2
    echo "Warning: Claude Code's hooks cannot start on this host as launched:" >&2
    # Read line by line rather than `printf '  - %s\n' "$faults"`: a
    # multi-line variable is still *one* argument, so that form bullets
    # the first fault and leaves the rest flush left, which reads as one
    # long sentence instead of a list. `faults()` can return two.
    while IFS= read -r fault; do
        echo "  - $fault" >&2
    done <<< "$faults"
    echo "The install itself succeeded. This is about the shell you start" >&2
    echo "Claude Code from -- see docs/HOOKS.md. The citation gate is one of" >&2
    echo "those hooks, and a launcher that does not resolve fails silently." >&2
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
    echo "  $bin_dir/python -m chitragupta.corpus sync"
    echo "  $bin_dir/python -m chitragupta.enrich"

    report_launcher_faults "$bin_dir/python"
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
    # Pinned to what is already installed, exactly as `ensure_cpu_torch`
    # pins (#512/m-85). Unpinned, this resolves whatever the CUDA index
    # currently offers, so the GPU swap could quietly land a *different*
    # torch version from the one `poetry.lock` resolved -- the same drift
    # its documented mirror pins against, and harder to notice here
    # because the swap is a fallback path nobody watches. Falls back to
    # unpinned only when the version cannot be read, which means torch is
    # not installed and there is nothing to preserve.
    local torch_ver tv_ver torch_spec torchvision_spec
    torch_ver="$("$pip" show torch 2>/dev/null | sed -n 's/^Version: //p' | cut -d+ -f1 || true)"
    tv_ver="$("$pip" show torchvision 2>/dev/null | sed -n 's/^Version: //p' | cut -d+ -f1 || true)"
    torch_spec="torch${torch_ver:+==${torch_ver}}"
    torchvision_spec="torchvision${tv_ver:+==${tv_ver}}"

    if "$pip" install --force-reinstall \
        --index-url "https://download.pytorch.org/whl/${best_tag}" \
        "$torch_spec" "$torchvision_spec" \
        && "$python_bin" -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
        echo "torch now sees the GPU via the ${best_tag} wheel."
        return
    fi

    echo "Warning: reinstalling torch from ${best_tag} didn't make the GPU" >&2
    echo "visible. Restoring the default wheel ..." >&2
    # `poetry install --with enrich` only makes sense from a checkout --
    # REPO_ROOT is site-packages when this runs via `chitragupta install
    # gpu-torch` (#265), which has no pyproject.toml and no poetry.lock to
    # pin against. Fall back to reinstalling with $pip directly there --
    # PyPI's current default wheel, not a lockfile-pinned one, so it's a
    # restore to *a* CPU-only state, not necessarily the one that was
    # installed before this function ran (#369: the previous unconditional
    # `poetry install` failed outright in that case, with "Poetry could
    # not find a pyproject.toml file").
    if [[ -f "$REPO_ROOT/pyproject.toml" ]] && command -v poetry >/dev/null 2>&1; then
        echo "Via 'poetry install --with enrich' (CPU-only on this driver," >&2
        echo "but at least back to a known, lockfile-tracked state) ..." >&2
        (cd "$REPO_ROOT" && poetry install --with enrich)
    else
        # Reuse the specs read back at the top of this function: the
        # restore should land the version that was installed before the
        # swap, not whatever PyPI currently serves (#641) -- an unpinned
        # restore on this rarely-exercised path was the one place the
        # torch version could silently drift from everything the rest of
        # this script pins. Unpinned only if the version could not be
        # read, which means torch was not installed and there is nothing
        # to preserve.
        echo "Via '$pip install --force-reinstall $torch_spec $torchvision_spec'" >&2
        echo "(CPU-only on this driver; no checkout/poetry.lock here, so pinned" >&2
        echo "to the previously installed version read back above) ..." >&2
        "$pip" install --force-reinstall "$torch_spec" "$torchvision_spec"
    fi
}

# The mirror of ensure_gpu_torch, and deliberately not a variant of it.
# That one asks "does this host have a GPU the default wheel cannot
# drive?" and *upgrades* to a CUDA-matched index. This one asserts the
# opposite -- there is no GPU and there never will be, which is true of a
# CI runner and of a CPU-only container -- and swaps down to PyTorch's
# cpu-only index, then removes the CUDA runtime the default wheel dragged
# in behind it.
#
# Worth roughly 4GB, measured rather than estimated: docker/Dockerfile
# records 6.2GB for the GPU-capable venv against 2.0GB for the cpu-only
# one, and a dev host's .venv-full breaks down as nvidia/ 2.7GB + torch
# 1.6GB + triton 539MB + cusparselt 227MB out of 6.4GB total. A hosted CI
# runner has no GPU, so all of that is downloaded, installed and thrown
# away on every run.
#
# The version is read back with `pip show` rather than pinned here, so
# this never drifts from a `poetry lock` re-resolution the way a second
# pinned copy would. docker/Dockerfile did it that way inline before this
# function existed; the logic lives here now so Docker and CI call one
# implementation, per DEVELOPER-AGENTS.md's rule that dependency facts
# have a single home.
ensure_cpu_torch() {
    local pip="$1"
    local python_bin="$2"
    local torch_ver tv_ver orphans

    # `|| true` is load-bearing under this script's `set -euo pipefail`:
    # `pip show` exits 1 for a package that is not installed, pipefail
    # propagates that out of the substitution, and `set -e` then kills the
    # script *before* the refusal below can be printed. Found by running
    # it -- the stage exited 1 with no message at all, which is precisely
    # the silent failure the message exists to prevent.
    torch_ver="$("$pip" show torch 2>/dev/null | sed -n 's/^Version: //p' | cut -d+ -f1 || true)"
    if [[ -z "$torch_ver" ]]; then
        echo "torch is not installed, so there is no variant to swap." >&2
        echo "Run the python-deps stage first." >&2
        return 1
    fi
    tv_ver="$("$pip" show torchvision 2>/dev/null | sed -n 's/^Version: //p' | cut -d+ -f1 || true)"

    echo "Swapping torch ${torch_ver} to the cpu-only wheel index ..."
    if [[ -n "$tv_ver" ]]; then
        "$pip" install --no-cache-dir --force-reinstall \
            --index-url https://download.pytorch.org/whl/cpu \
            "torch==${torch_ver}" "torchvision==${tv_ver}"
    else
        "$pip" install --no-cache-dir --force-reinstall \
            --index-url https://download.pytorch.org/whl/cpu \
            "torch==${torch_ver}"
    fi

    # Asked of pip rather than hardcoded. docker/Dockerfile carried a
    # literal list of fifteen nvidia-* names, and a literal list silently
    # stops removing whatever a later torch release adds -- the failure
    # mode being an image or cache that is quietly bigger than it should
    # be, which nothing reports.
    orphans="$("$pip" list --format=freeze \
               | sed -n 's/^\(nvidia-[a-z0-9-]*\|triton\)==.*/\1/p' || true)"
    if [[ -n "$orphans" ]]; then
        echo "Removing the CUDA runtime the default wheel brought in ..."
        # Deliberate word splitting: one package name per line is
        # exactly the argument list pip wants here.
        # shellcheck disable=SC2086
        "$pip" uninstall -y $orphans
    fi

    # Reported, never asserted. A cpu-only torch that still claims CUDA is
    # worth saying out loud, but this script installs things; deciding
    # that a toolchain is wrong is the caller's business, and
    # `chitragupta doctor` is where that judgement is going to live.
    "$python_bin" -c 'import torch; print("torch.cuda.is_available():", torch.cuda.is_available())' \
        2>/dev/null || echo "Warning: torch could not be imported after the swap." >&2
}


install_cpu_torch() {
    local venv_dir bin_dir
    resolve_venv_dir
    venv_dir="${VENV_DIR:-$REPO_ROOT/.venv-full}"
    bin_dir="$(venv_bin_dir "$venv_dir")"
    ensure_cpu_torch "$bin_dir/pip" "$bin_dir/python"
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

    # The developer-side checks that are not Python packages: the
    # workflow linter CI's lint job also runs, and the git hook that
    # calls it. Both belong to dev-deps rather than python-deps -- they
    # are needed to *change* this repository, never to run the pipeline.
    install_actionlint
    install_git_hooks

    echo
    echo "Installed. Run the test suite via:"
    echo "  ${bin_dir}/python -m pytest --cov --cov-report=term-missing"
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
        # Opt-in, and never part of `all`: it is only correct where a GPU
        # is known to be absent for good (a hosted CI runner, a cpu-only
        # container image), which this script cannot infer -- a laptop
        # with no GPU today may be a workstation with one tomorrow.
        cpu-torch) install_cpu_torch ;;
        # Vale alone, without the TeX Live and poppler that os-deps also
        # brings. os-deps installs it too; this target exists because CI's
        # lint job wants the prose linter and nothing else, and because
        # sourcing this script to reach the function runs the dispatcher
        # below with no stage -- which defaults to python-deps and fails
        # on a runner that has no poetry.
        vale) install_vale ;;
        # actionlint alone, for the same reason `vale` is a stage: CI's
        # lint job wants the workflow linter and nothing else, and it must
        # not drag in poetry or a venv to get it.
        actionlint) install_actionlint ;;
        # `chitragupta install gpu-torch` (#265) reaches ensure_gpu_torch
        # the same way vale above reaches install_vale -- a stage of its
        # own, for the same reason the comment above vale gives: sourcing
        # this script to call the function directly would also run the
        # dispatcher below with no stage, defaulting to python-deps.
        # CHITRAGUPTA_PIP/CHITRAGUPTA_PYTHON name the environment
        # `chitragupta` is actually installed into -- not .venv-full,
        # which is a checkout concept a pip install has no equivalent of,
        # so resolve_venv_dir/venv_bin_dir are deliberately not used here.
        gpu-torch)
            if [[ -z "${CHITRAGUPTA_PIP:-}" || -z "${CHITRAGUPTA_PYTHON:-}" ]]; then
                echo "gpu-torch needs CHITRAGUPTA_PIP and CHITRAGUPTA_PYTHON set to" >&2
                echo "the target environment's pip and python (chitragupta install sets both)." >&2
                exit 1
            fi
            ensure_gpu_torch "$CHITRAGUPTA_PIP" "$CHITRAGUPTA_PYTHON"
            ;;
        all) install_os_deps; install_python_deps ;;
        *)
            echo "Unknown stage: $stage" >&2
            echo "Expected one of: os-deps, python-deps, dev-deps, cpu-torch, vale, gpu-torch, all" >&2
            exit 1
            ;;
    esac
done

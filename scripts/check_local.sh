#!/usr/bin/env bash
# Run ci.yml's `lint` job locally: the same steps, in the same order,
# stopping at the first one that fails (#865).
#
#   bash scripts/check_local.sh
#
# Run it with your dev venv active, so `python`, `pylint` and `ruff`
# resolve to the pinned ones -- PATH is the only thing it reads them from.
# The test suite is not in here: that is ci.yml's `test` job, and
# DEVELOPER-AGENTS.md's "Before claiming a task complete" names it beside
# this script.
#
# **Why a list of CI's own commands rather than a summary of them.** A
# green run here is only worth something if it predicts a green CI run,
# and DEVELOPER-AGENTS.md's hand-kept checklist had already dropped five
# of the lint job's steps when this was written -- four red CI runs in
# one session came from that gap. So every `run:` step of the lint job
# appears below by its CI name, and tests/test_check_local.py reads both
# files and fails when they part: a step added, renamed, reordered or
# changed in either place without the other.
#
# Each line is one of three shapes, and the test gives them their
# meaning:
#
#   run "<name>" <command>   -- CI's exact command. `off_main` in front
#                               is CI's `if: github.event_name ==
#                               'pull_request'`, spelled for a checkout.
#   need "<name>" <tool>...  -- an install step. CI installs into a
#                               runner it throws away; here that would
#                               write into your own environment, so it
#                               checks the tool is on PATH instead, and
#                               warns if its version is not CI's pin.
#                               actionlint and Vale have no pin here:
#                               CI's pin for them is inside
#                               install_full_pipeline.sh, which installs
#                               exactly that version when either is
#                               missing.
#
# `npm ci` is the one install that runs as CI runs it: it writes only
# this checkout's node_modules/, from package-lock.json, so it needs the
# network but touches nothing of yours outside the tree.
#   instead "<name>" <cmd>   -- CI's form would do harm here; the reason
#                               is beside the line.
#
# What it cannot reproduce: CI lints under Python 3.13, and pylint's
# inference can differ across interpreters on an unchanged line, so
# a pylint run under another version is weaker evidence, not equal.

set -euo pipefail

cd "$(dirname "$0")/.."

warnings=()

# Said at once and again in the summary: a run that fails never reaches
# the summary, and that is the run where a version mismatch matters.
warn() {
    printf 'check_local: warning: %s\n' "$1" >&2
    warnings+=("$1")
}

run() {
    local name="$1"
    shift
    printf '\n==> %s\n' "$name"
    if ! "$@"; then
        printf '\ncheck_local: FAILED at "%s". CI would fail at the same step.\n' "$name" >&2
        exit 1
    fi
}

# A tool's version is read from `<tool> --version`, which every tool
# checked this way prints with its number in it. `py:<package>` is a
# library rather than a command -- bibtexparser, which pylint needs
# importable -- so it is asked of `python` instead.
need() {
    local name="$1" spec tool pin found
    shift
    printf '\n==> %s (checking, not installing)\n' "$name"
    for spec in "$@"; do
        tool="${spec%%[=@]*}"
        pin="${spec#"$tool"}"
        pin="${pin#==}"
        pin="${pin#@}"
        if [[ "$tool" == py:* ]]; then
            tool="${tool#py:}"
            found="$(python -c 'import importlib.metadata as m, sys; print(m.version(sys.argv[1]))' "$tool" 2>/dev/null)" || found=""
        elif command -v "$tool" >/dev/null 2>&1; then
            found="$("$tool" --version 2>&1)" || true
        else
            found=""
        fi
        if [ -z "$found" ]; then
            printf 'check_local: %s is not installed here. ci.yml installs it in "%s".\n' "$tool" "$name" >&2
            exit 1
        fi
        if [ -n "$pin" ] && [[ "$found" != *"$pin"* ]]; then
            warn "$tool is not CI's $pin -- its verdict may differ from CI's"
        fi
    done
}

instead() {
    local name="$1"
    shift
    run "$name (local form)" "$@"
}

# On a push to main CI skips the version check, because main compared
# with itself always fails. The same holds for a checkout sitting on
# origin/main's commit.
off_main() {
    if [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ]; then
        warn "HEAD is origin/main, so the version-bump check was skipped, as CI skips it on main"
        return 0
    fi
    "$@"
}

# CI's `cp` would overwrite a per-host config.toml, which is gitignored
# data rather than a copy of the example.
copy_config_if_absent() {
    [ -f config.toml ] || cp config.toml.example config.toml
}

# CI's `--depth=1` would turn a full clone into a shallow one.
fetch_main_and_tags() {
    git fetch --quiet origin "+refs/heads/main:refs/remotes/origin/main" "+refs/tags/*:refs/tags/*"
}

instead "Create config.toml from the tracked example" copy_config_if_absent
need "Install pylint and the runtime dependency" pylint==4.0.7 py:bibtexparser==1.4.4
need "Install ruff" ruff==0.16.4
instead "Fetch main and tags for the version check" fetch_main_and_tags
run "Version bump has not been lost to a collision" off_main python3 scripts/check_version_bump.py
run "pylint" pylint --rcfile=.pylintrc chitragupta scripts .claude/hooks
run "ruff" ruff check chitragupta scripts .claude/hooks
run "ruff format --check" ruff format --check chitragupta scripts tests bench .claude/hooks
run "shellcheck" shellcheck scripts/*.sh git-hooks/pre-commit docker/*.sh
need "Install actionlint" actionlint
run "actionlint" actionlint
need "Install markdownlint-cli2" markdownlint-cli2@0.23.2
run "markdownlint" markdownlint-cli2 "*.md" "docs/**/*.md" ".claude/**/*.md" ".agents/**/*.md" ".opencode/**/*.md" "plans/**/*.md" "!docs/examples/sample-project" "!.claude/worktrees"
run "Install webapp dev dependencies (acorn)" npm ci --ignore-scripts
run "Test the webapp modules" node --test tests/webapp/*.test.js
run "Test the OpenCode plugin helpers" node --test tests/opencode/*.test.mjs
need "Install Vale" vale
run "Vale config parses and the exemptions hold" bash scripts/check_style_exemptions.sh

printf '\ncheck_local: every step of ci.yml'"'"'s lint job passed.\n'
# The `+` form, because bash 3.2 (macOS) treats an empty array as unset under -u.
for warning in ${warnings[@]+"${warnings[@]}"}; do
    printf 'check_local: warning: %s\n' "$warning" >&2
done

#!/usr/bin/env bash
# Checks for, and installs, what the demo-recorder skill's steps need
# (SKILL.md, "What you need"). Ubuntu and Debian only: it installs with
# apt.
#
#   bash install_tools.sh          check, install what is missing, check again
#   bash install_tools.sh --check  check only; exit 1 if anything is missing
#
# Installs system-wide: apt packages, and agg into /usr/local/bin, through
# sudo unless run as root; npm packages with `npm install -g`, through
# sudo only when the global prefix is not writable. A Chrome is used from
# CHROME_PATH or Puppeteer's cache when it can start; otherwise this
# installs chrome-headless-shell with its system libraries. The last line
# printed is the CHROME_PATH for SKILL.md's capture step.
#
# The check uses bash builtins and the tools it looks for, nothing else,
# so tests/test_demo_recorder_install_tools.py can run it against fakes.
set -uo pipefail

missing=()

found() { printf '%s: %s\n' "$1" "$2"; }
lacking() {
  printf '%s: missing%s\n' "$1" "${2:+, $2}"
  missing+=("$1")
}

# A Chrome counts only if it can start: the cached Puppeteer one on
# Ubuntu 26.04 was present, executable, and lacked libcups.so.2.
starts() {
  [[ -x $1 ]] || return 1
  command -v ldd >/dev/null || return 0
  [[ $(ldd "$1" 2>&1) != *"not found"* ]]
}

find_chrome() {
  local c
  for c in "${CHROME_PATH:-}" \
    "$HOME"/.cache/puppeteer/chrome/*/chrome-linux64/chrome \
    "$HOME"/.cache/puppeteer/chrome-headless-shell/*/chrome-headless-shell-linux64/chrome-headless-shell; do
    if [[ -n $c ]] && starts "$c"; then
      printf '%s\n' "$c"
      return 0
    fi
  done
  return 1
}

check() {
  missing=()
  local v chrome
  v=$(asciinema --version 2>/dev/null)
  if [[ $v == "asciinema 2."* ]]; then found asciinema "$v"; else lacking asciinema "or not 2.x${v:+ ($v)}"; fi
  for v in ffmpeg agg svg-term; do
    if command -v "$v" >/dev/null; then found "$v" "$(command -v "$v")"; else lacking "$v"; fi
  done
  if command -v node >/dev/null && command -v npm >/dev/null; then
    found node/npm "$(command -v node)"
    if [[ -d $(npm root -g 2>/dev/null)/puppeteer-core ]]; then
      found puppeteer-core "$(npm root -g)/puppeteer-core"
    else
      lacking puppeteer-core
    fi
  else
    lacking node/npm
    lacking puppeteer-core
  fi
  if chrome=$(find_chrome); then found chrome "$chrome"; else lacking chrome; fi
  [[ ${#missing[@]} -eq 0 ]]
}

wants() { [[ " ${missing[*]} " == *" $1 "* ]]; }

install() {
  if ! command -v apt-get >/dev/null; then
    echo "no apt-get here: install what is missing by hand (SKILL.md, \"What you need\")" >&2
    return 1
  fi
  local sudo="" npm_sudo="" packages=() arch
  [[ $EUID -eq 0 ]] || sudo=sudo
  wants asciinema && packages+=(asciinema)
  wants ffmpeg && packages+=(ffmpeg)
  wants node/npm && packages+=(nodejs npm)
  wants agg && packages+=(curl ca-certificates)
  wants chrome && packages+=(unzip) # @puppeteer/browsers extracts with it
  if [[ ${#packages[@]} -gt 0 ]]; then
    $sudo apt-get update -q || return 1
    $sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y -q "${packages[@]}" || return 1
  fi
  if wants agg; then
    arch=$(uname -m)
    curl -fsSL -o /tmp/agg "https://github.com/asciinema/agg/releases/latest/download/agg-$arch-unknown-linux-gnu" || return 1
    $sudo install -m 755 /tmp/agg /usr/local/bin/agg || return 1
    rm -f /tmp/agg
  fi
  if wants svg-term || wants puppeteer-core; then
    [[ -w $(npm prefix -g) ]] || npm_sudo=$sudo
    $npm_sudo npm install -g svg-term-cli puppeteer-core || return 1
  fi
  if wants chrome; then
    # --install-deps runs apt for the libraries it needs, so it needs root.
    $sudo env HOME="$HOME" npx -y @puppeteer/browsers install chrome-headless-shell@stable \
      --path "$HOME/.cache/puppeteer" --install-deps || return 1
    [[ -z $sudo ]] || $sudo chown -R "$(id -u):$(id -g)" "$HOME/.cache/puppeteer"
  fi
}

if [[ ${1:-} == --check ]]; then
  check || exit 1
elif ! check; then
  echo "installing: ${missing[*]}"
  install && check || exit 1
fi
printf 'CHROME_PATH=%s\n' "$(find_chrome)"

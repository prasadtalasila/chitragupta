#!/usr/bin/env bash
# Re-run this example: one survey drafted end to end by OpenCode on a
# local model. Needs chitragupta-cli (pip install chitragupta-cli), the
# opencode CLI, and an OpenAI-compatible chat-completions server at
# BASE_URL (the recorded run used llama.cpp's llama-server). README.md
# has the setup.
#
#   bash run.sh [WORKDIR]
#
# The project is scaffolded fresh in WORKDIR (default: a new temporary
# directory), never in this directory, so the committed outputs here
# stay the recorded run's. The provider comes from opencode-provider.json
# through OPENCODE_CONFIG, so the project's own .opencode/opencode.json
# stays as `chitragupta init` wrote it.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
work="${1:-$(mktemp -d)}/project"
# `chitragupta init` leaves an existing project as it is, so a second
# run into the same WORKDIR would draft over the first run's ledger,
# dossier and draft. Refuse instead of mixing two runs.
if [ -e "$work" ]; then
  echo "run.sh: $work already exists; pass a new WORKDIR" >&2
  exit 1
fi
export BASE_URL="${BASE_URL:-http://127.0.0.1:18080/v1}"
export OPENCODE_CONFIG="$here/opencode-provider.json"

chitragupta init --agent opencode "$work" > /dev/null
cp -r "$here/papers/." "$work/papers/"
cp "$here/config.toml" "$work/config.toml"
cd "$work"
python -m chitragupta.corpus sync

opencode run --format json --title "survey on a local model" \
  "$(cat "$here/prompt.txt")" < /dev/null > content/events.jsonl
echo "Done: $work/content/drafts/dt-survey.md (events in $work/content/events.jsonl)"

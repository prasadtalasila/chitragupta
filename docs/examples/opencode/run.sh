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
export BASE_URL="${BASE_URL:-http://127.0.0.1:18080/v1}"
export OPENCODE_CONFIG="$here/opencode-provider.json"

chitragupta init --agent opencode "$work" > /dev/null
cp -r "$here/papers/." "$work/papers/"
cp "$here/config.toml" "$work/config.toml"
cd "$work"
python -m chitragupta.corpus sync

opencode run --format json --title "survey on a local model" \
  "$(cat "$here/prompt.txt")" < /dev/null > events.jsonl
echo "Done: $work/content/drafts/dt-survey.md (events in $work/events.jsonl)"

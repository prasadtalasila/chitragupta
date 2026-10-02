#!/usr/bin/env bash
# Re-run this example: one survey drafted end to end by Codex on a local
# model. Needs chitragupta-cli (pip install chitragupta-cli), the codex
# CLI, and a server speaking OpenAI's Responses API at BASE_URL (the
# recorded run used llama.cpp's llama-server). README.md has the setup.
#
#   bash run.sh [WORKDIR]
#
# The project is scaffolded fresh in WORKDIR (default: a new temporary
# directory), never in this directory, so the committed outputs here
# stay the recorded run's. Codex runs with its sandbox and approvals
# off and the project's hooks trusted for this one invocation, because
# the recorded host could not run Codex's sandbox (README.md says why).
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
BASE_URL="${BASE_URL:-http://127.0.0.1:18080/v1}"
MODEL="${MODEL:-qwen3.6-35b-a3b}"

chitragupta init --agent codex "$work" > /dev/null
cp -r "$here/papers/." "$work/papers/"
cp "$here/config.toml" "$work/config.toml"
cd "$work"
python -m chitragupta.corpus sync

codex exec --json --skip-git-repo-check \
  --dangerously-bypass-approvals-and-sandbox --dangerously-bypass-hook-trust \
  -c model_provider=local \
  -c "model_providers.local={name=\"local\",base_url=\"$BASE_URL\",wire_api=\"responses\"}" \
  -m "$MODEL" "$(cat "$here/prompt.txt")" < /dev/null > events.jsonl
echo "Done: $work/content/drafts/dt-survey.md (events in $work/events.jsonl)"

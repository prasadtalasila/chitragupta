#!/bin/bash
# Entrypoint for docker/Dockerfile.claude: bring up `claude remote-control`
# under rc-daemon.sh, in a detached tmux session, and then stay alive.
#
# Why a supervisor rather than a bare `claude remote-control`: Claude Code
# gives up after 10 minutes of persistent errors ("Persistent errors for 10
# minutes, giving up."), a limit hardcoded in the CLI. rc-daemon.sh restarts
# it with backoff, so a network blip no longer leaves a container that
# reports `Up` with no agent in it. It also keeps the agent in tmux, so
# `docker exec -it <container> tmux attach -t claude` gets you back to the
# live session as often as you like, from as many terminals as you like.
set -euo pipefail

export RC_DIR="${RC_DIR:-/workspace}"
# The name the agent registers under, which is what you pick from in the
# remote-control UI. docker-compose.yml sets both CLAUDE_AGENT_NAME and
# `hostname`; the hostname fallback is for a bare `docker run`.
export RC_NAME="${RC_NAME:-${CLAUDE_AGENT_NAME:-$(hostname)}}"
# TMUX_SESSION comes from the image's ENV ("claude"), so a later
# `docker exec ... rc-daemon.sh status` sees the same session name.

# This container keeps its own ~/.claude.json: only the ~/.claude directory
# is mounted, so the file is recreated on every container build and every
# one-time answer is lost with it. `claude remote-control` stops at three
# interactive prompts otherwise: onboarding, the Remote Control consent, and
# trust for the workspace. rc-daemon.sh's preflight refuses to start without
# the last two, and a detached tmux pane has nobody to answer them. Seed
# them here. Login is separate: the token comes from the mounted
# ~/.claude/.credentials.json and the account record from the host's
# ~/.claude.json, below. (The spawn-mode prompt is the fourth; rc-daemon.sh
# answers it by always passing --spawn.)
python3 - <<'PY'
import json, os
p = os.path.expanduser("~/.claude.json")
try:
    c = json.load(open(p))
except (OSError, ValueError):
    c = {}
# The account record (which organization the login belongs to). Without it
# `claude remote-control` exits with "Unable to determine your organization".
# docker-compose.yml mounts the host's ~/.claude.json here when
# CHITRAGUPTA_CLAUDE_JSON is set, and /dev/null otherwise, which fails to
# parse and is skipped. Copied on every start, so a re-login on the host
# reaches the container at its next restart.
host = os.path.expanduser("~/.claude.host.json")
if os.path.isfile(host) and os.path.getsize(host):
    try:
        c["oauthAccount"] = json.load(open(host))["oauthAccount"]
        print("entrypoint: account record copied from the host's ~/.claude.json")
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"entrypoint: WARNING -- CHITRAGUPTA_CLAUDE_JSON has no usable account record ({type(e).__name__}: {e}); log in on the host first")
c["hasCompletedOnboarding"] = True
c["remoteDialogSeen"] = True
c.setdefault("projects", {}).setdefault(os.environ["RC_DIR"], {})["hasTrustDialogAccepted"] = True
json.dump(c, open(p, "w"), indent=2)
PY

# --permission-mode bypassPermissions is the whole point of running in a
# container: the isolation is the boundary, so the agent does not stop to
# ask (RC_PERMISSION_MODE overrides it). Do not lift it onto a host.
#
# Reported rather than exited on, deliberately: the commonest first-start
# fault is a missing login, and the fix is to `docker exec` in and `/login`,
# which needs the container still running. The supervisor retries on its
# own once the login exists, backing off up to 5 minutes; `rc-daemon.sh
# restart` retries at once.
rc-daemon.sh start || echo "entrypoint: WARNING -- rc-daemon did not start; see the message above"

sleep 2
if rc-daemon.sh status >/dev/null 2>&1; then
  echo "entrypoint: agent supervised as '${RC_NAME}'"
  echo "entrypoint: attach with: docker exec -it $(hostname) tmux attach -t ${TMUX_SESSION}"
  echo "entrypoint: restart it with: docker exec $(hostname) rc-daemon.sh restart"
  echo "entrypoint: last output from the agent:"
  # `|| true`: this is only a courtesy printout, and under `set -e` with
  # pipefail a failed capture would otherwise end PID 1 and the container.
  { tmux capture-pane -p -J -t "${TMUX_SESSION}" 2>/dev/null | sed '/^$/d;s/^/entrypoint:   /' | tail -n 8; } || true
fi

# tmux daemonises, so without this the entrypoint would return, PID 1 would
# exit, and the container would stop with the agent inside it.
tail -f /dev/null

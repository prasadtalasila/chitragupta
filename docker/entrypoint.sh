#!/bin/bash
# Entrypoint for docker/Dockerfile.claude: bring up one detached
# `claude remote-control` session and then stay alive.
#
# Why tmux rather than running the agent as PID 1 directly: a session
# inside tmux survives whatever happens to the connection that started
# it, and `docker exec -it <container> tmux attach -t claude` gets you
# back to the same live session as many times as you like. As PID 1 the
# agent's terminal is the container's stdio, so `docker attach` is the
# only way in, detaching from it is a way to kill the container by
# accident, and a second viewer is not possible at all.
set -euo pipefail

SESSION=claude

# The name the agent registers under, which is what you pick from in the
# remote-control UI. docker-compose.yml sets both CLAUDE_AGENT_NAME and
# `hostname` from CHITRAGUPTA_CONTAINER_NAME; the hostname fallback is
# for a bare `docker run`, where it is the container's short id -- ugly
# but unique, which is the property that matters when two of these are
# up. This was a hardcoded operator's machine name until it turned out
# to be sitting in a file everyone else was expected to run.
AGENT_NAME="${CLAUDE_AGENT_NAME:-$(hostname)}"

# remain-on-exit is what makes the failure below observable at all.
# Without it, a session whose command exits is reaped along with the
# tmux server and there is nothing left to read: the container reports
# `Up`, `docker logs` is empty, and the agent is simply not there. With
# it the pane stays in place, dead, and its output can still be
# captured.
#
# Written to a config file rather than set with `tmux set-option`, and
# both of the obvious alternatives were tried first. `new-session` then
# `set-option` loses a race the agent wins easily -- it exits in
# milliseconds on the unauthenticated path. `tmux start-server &&
# set-option -g` looks race-free and is worse: a server with no sessions
# exits immediately, so the `set-option` hits "no server running", and
# under `set -e` that took PID 1 with it -- an entrypoint that failed on
# every start, turning a silent problem into a restart loop. A server
# reads this file when it starts, however it was started.
#
# It is `-g` only for as long as it takes to create the agent's session,
# and the narrowing below is not tidiness -- left global it breaks every
# *other* pane in the container. A person who runs `tmux` inside here
# and types `exit` gets "Pane is dead" and a session that will not close,
# which is a worse bug than the silent one this option exists to fix,
# and it was reported from real use.
mkdir -p "$HOME/.config/tmux"
echo "set -g remain-on-exit on" > "$HOME/.config/tmux/tmux.conf"

# A dead pane from a previous start would otherwise satisfy has-session
# and stop this from ever retrying -- and retrying is the whole point of
# `restart: unless-stopped` plus a login that has since been fixed.
if tmux has-session -t "$SESSION" 2>/dev/null; then
  if [ "$(tmux display-message -p -t "$SESSION" '#{pane_dead}')" = "1" ]; then
    echo "entrypoint: clearing the dead '${SESSION}' pane from the last start"
    tmux kill-session -t "$SESSION"
  fi
fi

# --permission-mode bypassPermissions is the whole point of running in a
# container: the isolation is the boundary, so the agent does not stop
# to ask. Do not lift this flag onto a host.
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux new-session -d -s "$SESSION" \
    "claude remote-control --permission-mode bypassPermissions --name ${AGENT_NAME}"
fi

# The option has done its job the moment the session exists, so put it
# back: `off` globally, `on` for this one session, which no longer races
# anything because the session is already there. Any interactive `tmux`
# a person starts in this container from here on behaves normally --
# `exit` closes the pane and ends the session.
#
# The config file goes too. If the agent's session is ever killed and
# the tmux server exits with it, the next `tmux` starts a fresh server,
# and a fresh server re-reads that file -- reintroducing the global
# setting for an interactive user long after this script ran.
tmux set-option -g remain-on-exit off
tmux set-option -t "$SESSION" remain-on-exit on
rm -f "$HOME/.config/tmux/tmux.conf"

# Then say whether it actually came up, because this failure is silent
# and it is the state every *first* start is in: `claude remote-control`
# exits immediately when the mounted /home/prasad/.claude carries no
# login ("You must be logged in to use Remote Control"). PID 1 stays
# healthy either way, so `restart: unless-stopped` never fires and
# nothing else would ever mention it.
#
# Reported rather than exited on, deliberately: the fix is to `docker
# exec` in and log in, and that needs the container still running. A
# crash loop would take away the one route to recovery.
sleep 2
if [ "$(tmux display-message -p -t "$SESSION" '#{pane_dead}')" = "1" ]; then
  echo "entrypoint: WARNING -- the agent exited immediately. Its output was:"
  tmux capture-pane -p -t "$SESSION" | sed '/^$/d;s/^/entrypoint:   /'
  echo "entrypoint: the container stays up so you can fix this in place:"
  echo "entrypoint:   docker exec -it $(hostname) claude   # then /login, then restart"
else
  echo "entrypoint: agent is up as '${AGENT_NAME}'"
  echo "entrypoint: attach with: docker exec -it $(hostname) tmux attach -t ${SESSION}"
fi

# tmux daemonises, so without this the entrypoint would return, PID 1
# would exit, and the container would stop with the agent inside it.
tail -f /dev/null

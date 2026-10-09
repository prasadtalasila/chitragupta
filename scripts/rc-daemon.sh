#!/usr/bin/env bash
# Keep `claude remote-control` running: restart it whenever it exits
# (e.g. "Persistent errors for 10 minutes, giving up." — that 10-minute
# give-up is hardcoded in Claude Code and cannot be changed by a setting).
#
# Usage: rc-daemon.sh start|stop|restart|status|attach|log
#   start   - launch the supervisor in a detached tmux session (idempotent)
#   attach  - attach to the tmux session (detach with Ctrl-b d)
#
# Settings live in rc-daemon.env next to this script (RC_ENV_FILE points
# elsewhere); env vars override them, e.g. RC_DIR=/other/dir rc-daemon.sh start
set -u

SELF="$(readlink -f "$0")"
RC_ENV_FILE="${RC_ENV_FILE:-${SELF%.sh}.env}"
# shellcheck source=rc-daemon.env
. "$RC_ENV_FILE" || { echo "cannot read $RC_ENV_FILE" >&2; exit 1; }
: "${RC_DIR:?} ${RC_NAME:?} ${RC_PREFIX:?} ${RC_PERMISSION_MODE:?} ${TMUX_SESSION:?} ${RC_LOG:?}"
LOG="$RC_LOG"

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*" | tee -a "$LOG"; }

# The restart loop itself; runs inside tmux so claude gets a real TTY.
supervise() {
  local backoff=5
  cd "$RC_DIR" || { log "cannot cd to $RC_DIR"; exit 1; }
  while true; do
    log "starting claude remote-control --name $RC_NAME in $RC_DIR"
    local started=$SECONDS
    claude remote-control \
      --name "$RC_NAME" \
      --permission-mode "$RC_PERMISSION_MODE" \
      --remote-control-session-name-prefix "$RC_PREFIX"
    local rc=$? ran=$((SECONDS - started))
    log "claude remote-control exited with code $rc after ${ran}s"
    # Reset backoff after a healthy run; otherwise back off up to 5 minutes.
    if (( ran > 300 )); then backoff=5; else backoff=$(( backoff * 2 > 300 ? 300 : backoff * 2 )); fi
    log "restarting in ${backoff}s"
    sleep "$backoff"
  done
}

running() { tmux has-session -t "$TMUX_SESSION" 2>/dev/null; }

# claude remote-control needs two one-time interactive answers, both stored in
# ~/.claude.json: workspace trust for RC_DIR (else it exits 1 immediately, and the
# loop would retry forever) and the "Enable Remote Control?" consent (else it waits
# at a y/n prompt inside the detached pane). Refuse to start until both are given.
preflight() {
  command -v python3 >/dev/null || return 0   # can't check; let claude report it
  python3 - "$RC_DIR" <<'EOF'
import json, os, sys
try:
    cfg = json.load(open(os.path.expanduser("~/.claude.json")))
except (OSError, ValueError):
    cfg = {}
missing = []
if not cfg.get("projects", {}).get(sys.argv[1], {}).get("hasTrustDialogAccepted"):
    missing.append("workspace trust for " + sys.argv[1])
if not cfg.get("remoteDialogSeen"):
    missing.append("Remote Control consent")
if missing:
    print("not started; missing one-time setup: " + ", ".join(missing))
    print("fix: cd %s && claude remote-control   (answer the prompts, Ctrl-C, then start again)" % sys.argv[1])
    sys.exit(1)
EOF
}

case "${1:-}" in
  start)
    if running; then echo "already running (tmux session '$TMUX_SESSION')"; exit 0; fi
    preflight || exit 1
    tmux new-session -d -s "$TMUX_SESSION" \
      "RC_DIR='$RC_DIR' RC_NAME='$RC_NAME' RC_PREFIX='$RC_PREFIX' RC_PERMISSION_MODE='$RC_PERMISSION_MODE' RC_LOG='$LOG' '$SELF' _supervise"
    # claude's own output (errors, prompts) only reaches the pane; mirror it to a
    # side log so failures like "Workspace not trusted" are visible without attaching.
    tmux pipe-pane -t "$TMUX_SESSION" -o "cat >> '${LOG%.log}.pane.log'"
    echo "started in tmux session '$TMUX_SESSION'; log: $LOG"
    ;;
  stop)
    # Ctrl-C lets claude shut down cleanly, then kill the session/loop.
    running && { tmux send-keys -t "$TMUX_SESSION" C-c; sleep 3; tmux kill-session -t "$TMUX_SESSION" 2>/dev/null; }
    log "stopped"
    ;;
  restart) "$SELF" stop; "$SELF" start ;;
  status)
    if running; then echo "running (tmux session '$TMUX_SESSION')"; else echo "not running"; exit 1; fi
    ;;
  attach) exec tmux attach -t "$TMUX_SESSION" ;;
  log) exec tail -n 50 -f "$LOG" ;;
  _supervise) supervise ;;
  *) echo "usage: $0 start|stop|restart|status|attach|log"; exit 2 ;;
esac

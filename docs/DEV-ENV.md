# 🛰️ Development environment: the Remote Control daemon

Status: **reference.** Written 2026-10-09.

**Written for** a developer who wants a long-lived `claude remote-control`
session on a development host, so they can drive this checkout from
claude.ai or the mobile app. **Assumed:** Claude Code is installed and
logged in, and `tmux` and `python3` are on `PATH`.

## 🧭 Table of contents

- [What it does](#-what-it-does)
- [The settings file](#-the-settings-file)
- [One-time setup](#-one-time-setup)
- [Running it](#-running-it)
- [Running a second daemon](#-running-a-second-daemon)

## 🔁 What it does

`scripts/rc-daemon.sh` keeps `claude remote-control` running. Claude Code
gives up after ten minutes of persistent errors, and no setting changes
that, so the script runs it in a restart loop inside a detached `tmux`
session. After a run shorter than five minutes the restart delay
doubles, up to a cap of five minutes. A run longer than that resets the
delay to five seconds.

## 🔧 The settings file

The script reads its settings from `scripts/rc-daemon.env`, which it
sources at startup:

```bash
cp scripts/rc-daemon.env.example scripts/rc-daemon.env
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `RC_DIR` | `/workspace` | Directory the session runs in. It must be a trusted workspace |
| `RC_NAME` | `chitragupta-dtl1` | Remote Control session name, as claude.ai shows it |
| `RC_PREFIX` | `chitragupta-dtl1` | Name prefix for sessions spawned from it |
| `RC_PERMISSION_MODE` | `bypassPermissions` | Permission mode for those sessions |
| `TMUX_SESSION` | `rc-chitragupta-dtl1` | `tmux` session the loop runs in |
| `RC_LOG` | `~/claude-daemon/rc-chitragupta-dtl1.log` | The loop's log; the pane output goes to `<name>.pane.log` beside it |

Every line in the file is written as `VAR="${VAR:-default}"`, so a
variable already set in the environment wins. That gives you a one-off
override without editing the file:

```sh
RC_NAME=scratch scripts/rc-daemon.sh start
```

To use a different file altogether, set `RC_ENV_FILE`:

```sh
RC_ENV_FILE=~/my-rc.env scripts/rc-daemon.sh start
```

## 🔑 One-time setup

`claude remote-control` asks two questions once and stores the answers
in `~/.claude.json`: whether to trust `RC_DIR` and whether to enable
Remote Control. The detached pane cannot answer them, so `start` checks
both first and refuses to start without them. To answer them:

```sh
cd /workspace && claude remote-control
```

Answer both prompts, press Ctrl-C, then start the daemon.

## 🚀 Running it

```sh
scripts/rc-daemon.sh start     # launch in a detached tmux session; a no-op if already running
scripts/rc-daemon.sh status    # "running" or "not running" (exit 1)
scripts/rc-daemon.sh log       # follow the loop's log
scripts/rc-daemon.sh attach    # watch the pane; detach with Ctrl-b d
scripts/rc-daemon.sh restart   # stop, then start
scripts/rc-daemon.sh stop      # Ctrl-C claude, then kill the tmux session
```

Run `restart` after editing `rc-daemon.env`. A running loop does not
re-read the file.

When something goes wrong, read the pane log
(`~/claude-daemon/rc-chitragupta-dtl1.pane.log` by default) first. It
captures claude's own output, such as "Workspace not trusted", which the
loop's log does not.

## 👯 Running a second daemon

Each daemon needs its own `TMUX_SESSION` and `RC_LOG`. `start` decides
whether a daemon is already running only by checking for its `tmux`
session, so two daemons that share a session name block each other, and
two that share a log write into the same file. Give the second one its
own settings file and change all six values:

```sh
cp scripts/rc-daemon.env ~/rc-other.env    # then edit it
RC_ENV_FILE=~/rc-other.env scripts/rc-daemon.sh start
```

Pass the same `RC_ENV_FILE` to every later command for that daemon,
`stop` and `status` included. Without it they act on the default
daemon.

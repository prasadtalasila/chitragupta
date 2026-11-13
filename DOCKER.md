# 🐳 Running with Docker

There are two images, for two different jobs. Neither is a variant of
the other, and neither replaces the other:

| File | What it is | Size | Needs a checkout |
| --- | --- | --- | --- |
| `docker/Dockerfile` | The **toolchain image**. Builds the full TeX Live/Pandoc/Poetry/torch stack from this repository's own `scripts/install_full_pipeline.sh`, for hosts where you don't hold root. Ubuntu 26.04 LTS / Python 3.14, with the C headers and compiler triton JITs against. Mount your checkout, get a shell with everything resolved. | 5.09GB (cpu) / 11.6GB (gpu, measured on an earlier base image) | Yes: it is the checkout you mount and work in |
| `docker/Dockerfile.claude` | The **agent image**. Node, Claude Code, and a `/opt/venv` install of the published `chitragupta-cli` package, driven by `docker/docker-compose.yml` as a long-lived `claude remote-control` host. The toolchain is *not* baked in; you add what you need at runtime with `chitragupta install`. | ~2.5GB | No, it installs from PyPI |

`docker/Dockerfile` is documented first, then the agent image under
["The agent container"](#-the-agent-container-dockerdockerfileclaude).

No piece of the toolchain image is Docker-exclusive:
`scripts/install_full_pipeline.sh` is the single install path for both
the host and the image.

**Getting `docker/` without a checkout.** `chitragupta init` doesn't
scaffold `docker/`, and a `pip install chitragupta-cli` doesn't carry it
either. Every tagged [GitHub
Release](https://github.com/prasadtalasila/chitragupta/releases) attaches
a standalone `chitragupta-docker-<version>.zip` (`docker/` plus this
page) for that case. That is enough on its own for the agent image:
`Dockerfile.claude`'s build context is `docker/` alone (see
["Build and run"](#-build-and-run) below) and it installs from PyPI, so
the commands under ["The agent container"](#-the-agent-container-dockerdockerfileclaude)
work with nothing else present. The toolchain image still needs a
checkout however you got `docker/`, as the table above says, because its
`Dockerfile` `COPY`s `scripts/install_full_pipeline.sh` and its `Run`
section mounts your own working copy for `config.toml` to resolve from.
`DOCKER-DEVELOPER.md` at the repository root is this project's own
record of how these two images are verified before a release; a Docker
user does not need to read it.

## 🔧 Build

```bash
docker build -t chitragupta -f docker/Dockerfile .
```

This runs `scripts/install_full_pipeline.sh` twice as separate,
independently cached layers: `os-deps`, then `python-deps` (via Poetry,
with `SKIP_VENV=1` so it installs into `/opt/venv` instead of creating
its own). Editing later Dockerfile lines or unrelated repo files
therefore doesn't force earlier layers to rebuild. Two exceptions: the
script itself is `COPY`'d once before either stage runs, so editing
`scripts/install_full_pipeline.sh` invalidates both layers; and
`pyproject.toml`, `poetry.lock`, `poetry.toml` and `README.md` are
`COPY`'d before the `python-deps` layer, so editing any of them
rebuilds that layer.
Docker's cache keys each layer on the exact command *and* any files that
command's `COPY` depends on, and this file feeds both of them. The
`python-deps` layer pulls torch and Docling's models; expect a long
first build.

### ⚖ CPU-only vs. GPU-capable: `TORCH_VARIANT`

`torch` isn't pinned in `pyproject.toml` (it's a transitive dependency of
`sentence-transformers`/`docling`/`accelerate`; see that file's own
comment). `poetry.lock` resolves whatever plain PyPI's default Linux
wheel currently is, and that wheel bundles the full CUDA runtime as
separate `nvidia-*` packages (`cublas`, `cudnn`, `nccl`, `triton`, ...)
regardless of whether the build host or the eventual container ever sees
a GPU. The `docker/Dockerfile` build arg `TORCH_VARIANT` controls which
one you get:

| `TORCH_VARIANT` | Build command | Measured image size | When to use it |
| --- | --- | --- | --- |
| `gpu` (default) | `docker build -t chitragupta -f docker/Dockerfile .` | 11.6GB (earlier base image) | `docker run --gpus` deployments. The bundled CUDA runtime is enough on its own: no host CUDA toolkit is needed, only a matching driver |
| `cpu` | `docker build -t chitragupta -f docker/Dockerfile --build-arg TORCH_VARIANT=cpu .` | 5.09GB | Everything else. Embeddings/clustering/rendering all run fine on CPU, and this is what you want for build-verification or a host with no GPU at all |

The `cpu` variant reinstalls `torch`/`torchvision` from PyTorch's own
CPU-only wheel index, at the exact version `poetry.lock` resolved (read
back via `pip show` rather than pinned a second time in the Dockerfile,
so it can't drift from a `poetry lock` re-resolution), then removes the
now-orphaned `nvidia-*`/`triton` packages. Both the swap and the removal
happen inside the same `RUN` as the original `poetry install`, so the
CUDA wheels never end up committed to a layer in the first place.
Doing this as a later, separate `RUN` only marks them deleted and leaves
the image *larger*, since the earlier layer's bytes are still stored.

Sizes above also depend on the Poetry/pip download cache being purged in
that same layer (`rm -rf /root/.cache/pypoetry /root/.cache/pip`, at the
end of the `python-deps` `RUN`). Without it, every build leaves the
full set of downloaded wheel archives sitting in the final image on top
of the installed packages (measured: 24.9GB for the `gpu` variant with
the cache left in place, more than double its 11.6GB with it purged).

## 🚀 Run

Mount your repo and a volume for `content/` so it survives container
restarts:

```bash
docker run -it --rm \
    -v "$(pwd)":/workspace/chitragupta \
    -v chitragupta-content:/workspace/chitragupta/content \
    chitragupta
```

The image deliberately mounts the repo instead of baking it in, so the
`config.toml` the container reads is the one in *your* working copy. That
file is gitignored, so create it before the first run or `chitragupta.config`
will refuse to import:

```bash
cp config.toml.example config.toml
```

## ✅ Verify the toolchain

Inside the running container, check that the render and enrichment
dependencies resolved:

```bash
command -v latexmk pandoc pdftotext
python -c "import sentence_transformers, chromadb, bertopic, docling; print('enrich group OK')"
```

## 🤖 The agent container (`docker/Dockerfile.claude`)

A second, much thinner image. Its job is to host one long-lived
`claude remote-control` session with this pipeline installed, kept alive by
`rc-daemon.sh` (see [below](#-the-supervisor-rc-daemonsh)); it does
not build the toolchain. It installs the *published* `chitragupta-cli`
package from PyPI into `/opt/venv` and copies no part of this repository
in. That is the whole difference from the toolchain image: an image built
from a checkout has to be rebuilt to follow a release, and this one only
has to be restarted.

The build takes seconds instead of tens of minutes, and the image is
~2.5GB instead of 5.09GB, because TeX Live, Pandoc and torch are not in
it. The cost is that you add whatever the work needs on first run, with
`chitragupta install`, which is why the image gives its user
passwordless `sudo` (see below).

The shell you land in is **zsh with Oh My Zsh**, pinned to a commit
rather than installed by piping an unpinned script from the network, and
`neovim` is there for fixing config by hand. The venv reaches zsh
through `/etc/zsh/zshenv`, because Debian's zsh does not read
`/etc/profile.d`; getting that wrong brings back the failure the next
section describes.

### 🧩 One environment, and why it is not `pipx`

`chitragupta-cli` goes into a venv at `/opt/venv` which is first on
`PATH` (the same arrangement `docker/Dockerfile` uses), so `python`,
`python3`, `pip`, `chitragupta` and `cg` are all the same environment.

The hooks depend on this. `.claude/settings.json`, the one
`chitragupta init` scaffolds, launches every hook as `command:
"python"`. Install the package into a *private* venv, as `pipx` does,
and that `python` is the system interpreter, which cannot import it, so
the citation gate returns

```text
{"decision": "block", "reason": "The citation gate could not run --
this is an environment fault, not a bad citekey ..."}
```

on every draft write: the container comes up looking healthy and
refuses to let anything be drafted in it. The gate is right to block,
since it will not pass a draft it could not check, so the fix belongs
in the image and not in the hook.

A `/etc/profile.d/` snippet carries the same `PATH` for login shells,
which source `/etc/profile` and rebuild `PATH` from scratch, discarding
what `ENV PATH` set. (A `pipx` install can appear to survive a login
shell only because Debian's `~/.profile` re-adds `$HOME/.local/bin`,
where pipx's shims live; that is luck, not a design.)

### 🔧 Build and run

Build with a temporary tag while you are changing anything here, so
an existing `:latest` that other containers are running survives a
failed attempt:

```bash
docker build -t chitragupta-claude:tmp -f docker/Dockerfile.claude docker/
```

The build context is `docker/`, not the repository root: nothing
outside that directory is needed, and a root context would send the
whole tree (worktrees included) to the daemon.

Then run it through compose, from inside `docker/` so its relative
defaults and its `.env` resolve:

```bash
cd docker
cp .env.example .env          # then edit the four CHITRAGUPTA_* variables
mkdir -p /path/to/workspace/papers   # the CHITRAGUPTA_WORKSPACE you set
docker compose up -d          # .env's COMPOSE_PROFILES picks cpu or gpu
docker exec -it chitragupta-claude bash
```

`docker/.env.example` is the tracked documentation of every variable
the compose file reads; `docker/.env` is gitignored. Four variables have
no default and must be set: `CHITRAGUPTA_WORKSPACE`, `CHITRAGUPTA_USER`,
`CHITRAGUPTA_UID` and `CHITRAGUPTA_GID`.

Do not skip that `mkdir`. The Docker daemon silently creates a missing
bind-mount source itself, owned by `root:root`. For the read-only papers
mount the result is a directory nobody can put a PDF in: read-only
inside the container, root-owned outside it. Create both directories
first and they stay yours.

### 🎛 Two profiles: `cpu` and `gpu`

Neither service starts without a profile, on purpose. `docker
compose up` with none selected prints `no service selected` and exits
having done nothing:

```bash
docker compose --profile cpu up -d   # no GPU handed to the container
docker compose --profile gpu up -d   # every GPU on the host
```

or set `COMPOSE_PROFILES` in `.env` (the example ships `cpu`) and plain
`docker compose up -d` works.

The two services are identical apart from a `deploy:` reservation, and
they share the YAML anchor that says so, so they cannot drift. They also
share a container name, since only one runs at a time.

The file uses profiles instead of one service that adapts because a
reservation naming the `nvidia` driver makes `up` fail outright on a
host without the NVIDIA Container Toolkit
(`could not select device driver`) instead of starting without a GPU.
Compose has no conditional for a volume or a reservation, so two
services under two profiles is the only shape that lets one file serve
both machines. Verified both ways on a host with the toolkit:
`--profile gpu` reaches every GPU on the host and `nvidia-smi` inside the
container, `--profile cpu` shows no `/dev/nvidia*` at all.

### ⚙ What compose reads from the environment

Every path and name is a variable, so the file carries no one
developer's home directory and no release number. Set these in
`docker/.env` or in the environment:

| Variable | Default | What it does |
| --- | --- | --- |
| `CHITRAGUPTA_WORKSPACE` | **required** | Host directory mounted at `/workspace`, where `chitragupta init` scaffolds and where drafts land. Compose refuses to start without it instead of mounting something arbitrary |
| `CHITRAGUPTA_CONTAINER_NAME` | `chitragupta-claude` | The container's name, so `docker exec -it <name> bash` works. Also becomes the container hostname and the agent's name in the remote-control UI |
| `CHITRAGUPTA_PROJECT_NAME` | `chitragupta` | Compose's project name, which prefixes the network. Set it per workspace to run two of these side by side |
| `CHITRAGUPTA_IMAGE_TAG` | `latest` | Which tag to run. This is how you point one workspace at a `:tmp` build without disturbing the `:latest` everything else uses |
| `CHITRAGUPTA_CLAUDE_HOME` | `./claude` | Host directory for `/home/$CHITRAGUPTA_USER/.claude`. This is what persists the login, so a restart is not a re-authentication |
| `CHITRAGUPTA_CLAUDE_JSON` | none | The host's `~/.claude.json`, mounted read-only. The entrypoint copies its account record (`oauthAccount`) into the container's own `~/.claude.json` on every start. Set it when `CHITRAGUPTA_CLAUDE_HOME` is the host's `~/.claude`: that carries the token but not the account, and remote-control then fails with `Unable to determine your organization`. The whole file is readable by the agent, so point it at a copy holding only `oauthAccount` if yours carries secrets |
| `RC_NAME` / `RC_PREFIX` | container name | The agent's name in the remote-control UI, and the prefix for sessions it spawns |
| `RC_PERMISSION_MODE` | `bypassPermissions` | Permission mode `claude remote-control` runs with. The container is the isolation boundary |
| `RC_SPAWN` | `worktree` | What a session started from the app runs in: `worktree` (its own git worktree of the workspace; falls back to `same-dir`, with a log line, when the workspace is not a git repository), `same-dir` or `session`. Always passed, because unset, `claude` waits at a prompt nobody can answer |
| `RC_VENV` | none (`/opt/venv`) | A venv inside the container to run the agent from instead of `/opt/venv` |
| `CHITRAGUPTA_WORKSPACE_DIR` | `/workspace` | The path the workspace is mounted at inside the container, and the directory the agent runs in. Give each container its own when several share one `CHITRAGUPTA_CLAUDE_HOME`: Claude Code keys the remote-control session on this path, so two containers on the same path take over each other's session. `RC_VENV` and a venv's own scripts must use the same prefix |
| `CHITRAGUPTA_PAPERS` | `$CHITRAGUPTA_WORKSPACE/papers` | Host directory of PDFs, mounted **read-only** at `<workspace dir>/papers`. Point it elsewhere to share one corpus across workspaces |
| `COMPOSE_PROFILES` | none | `cpu` or `gpu`; see below. Compose's own variable, not one of ours |
| `CHITRAGUPTA_USER` | **required** | The unprivileged account inside the image: your own login name (`id -un`). A **build** arg as well as a runtime setting, so changing it needs `docker compose build`, not just a restart |
| `CHITRAGUPTA_UID` / `CHITRAGUPTA_GID` | **required** | That account's numeric ids, which are your own (`id -u`, `id -g`). They decide who owns a file the container writes into the workspace. Avoid 1000: the Node base image has already taken it for its own `node` account |

Nothing in the image hardcodes an account name, and the three account
settings have no defaults anywhere, neither in `docker-compose.yml` nor
in `Dockerfile.claude`. `docker compose` refuses to start
without them, naming the variable and the file; a bare `docker build`
that forgets the matching `--build-arg` fails on an explicit guard
rather than creating an account called `""`.

The account belongs to *your machine*, not to this project, and a
default that is wrong for almost everyone is worse than
no default at all: it works just well enough to write files owned by the
wrong uid into your workspace, which you then cannot edit from outside
the container. Copy `.env.example` to `.env` and fill in the three
values it shows you how to read off your own account.

`CHITRAGUPTA_USER` alone reaches the `useradd`, the
`/etc/sudoers.d/<user>` file, `$HOME`, the `PATH` entry the venv
installs into, and the mount point for `CHITRAGUPTA_CLAUDE_HOME`. These
five places cannot disagree because they read one value. The entrypoint
lives at
`/usr/local/bin/entrypoint.sh` rather than in the home directory for the
same reason.

### 🛡 The supervisor: `rc-daemon.sh`

`claude remote-control` gives up after 10 minutes of persistent errors,
and that limit is hardcoded in Claude Code. The entrypoint therefore runs
the agent under `docker/rc-daemon.sh`, which restarts it with backoff
(5 seconds, doubling to 5 minutes, reset after a healthy run) inside the
`claude` tmux session. Both it and `rc-daemon.env` are installed in
`/usr/local/bin`, and the agent runs from the image's `/opt/venv`, which
it inherits from `ENV PATH`.

Every setting in `rc-daemon.env` is overridable from the environment, so
nothing needs editing in a running container. Set `RC_NAME`,
`RC_PREFIX`, `RC_PERMISSION_MODE`, `RC_SPAWN` or `RC_VENV` in
`docker/.env`. `RC_VENV` points at another venv *inside the container*,
for example one in the workspace;
`/opt/venv` is the default. The entrypoint also records the workspace
trust and the Remote Control consent in the container's `~/.claude.json`,
because the supervisor will not start without them.

```bash
docker exec chitragupta-claude rc-daemon.sh status    # also the healthcheck
docker exec chitragupta-claude rc-daemon.sh restart   # retry at once, e.g. after /login
docker exec chitragupta-claude tail -f /home/$CHITRAGUPTA_USER/rc-daemon.log
```

### 🚀 First run

The container deliberately starts before it can do anything useful. Set
it up in this order:

```bash
docker exec -it chitragupta-claude claude   # then /login
docker exec chitragupta-claude rc-daemon.sh restart   # the agent picks up the login at once
docker exec -it chitragupta-claude bash
chitragupta install os-deps                 # TeX Live, Pandoc, poppler, Vale
chitragupta init                            # scaffold /workspace
chitragupta doctor                          # what is still missing
```

`chitragupta install os-deps` is what the passwordless `sudo` in this
image exists for: it `apt-get install`s the toolchain that the image
does not ship. (`chitragupta install` still refuses `all`, `dev-deps`
and `python-deps` by name, naming what reaches them instead; those are
checkout-shaped stages with no analogue here.)

The enrichment stack is a separate step, not part of the image,
because it is torch and would take this from ~2.5GB past 6GB:

```bash
chitragupta install enrich   # into /opt/venv, no sudo needed
```

The CLI does this, so you need not know the pip command: it resolves
`'chitragupta-cli[enrich]'` pinned to the version already running, so
adding the extra cannot silently upgrade the tool.
`pip install 'chitragupta-cli[enrich]'` is the equivalent by hand.

### ✅ Verify the container

```bash
docker exec chitragupta-claude bash -lc '
  whoami                          # $CHITRAGUPTA_USER, uid $CHITRAGUPTA_UID
  sudo -n true && echo "sudo ok"  # what `chitragupta install os-deps` needs
  claude --version                # must work as this account, not just root
  chitragupta --version
  tmux ls                         # the "claude" session, with the agent in it
'
```

### 🔍 When the agent is not there

The container can report `Up` with no agent running in it, and the
common cause is the first-run one: `claude remote-control` exits
immediately if the mounted `.claude` carries no login. `entrypoint.sh`
reports that in `docker logs` rather than leaving it silent:

```text
entrypoint: agent supervised as 'chitragupta-claude'
entrypoint: last output from the agent:
entrypoint:   Error: You must be logged in to use Remote Control.
entrypoint:   claude remote-control exited with code 1 after 0s
entrypoint:   restarting in 10s
```

The supervisor keeps retrying, so once you `/login` the agent comes up
on its own within the backoff (at most 5 minutes);
`rc-daemon.sh restart` skips the wait. The entrypoint does not exit
non-zero on purpose: the fix needs a running container to `docker exec`
into, and a crash loop would take that away. The compose healthcheck
reports `unhealthy` only if the supervisor itself is gone, not for a
missing login. `docker logs <name>` is therefore the first thing to read
when the remote-control UI does not list your agent, not `docker ps`,
which will say `Up` either way.

Two other lines you may find there:

- `Error: Unable to determine your organization for Remote Control
  eligibility.` The login is there but the account record is not. That
  happens when `CHITRAGUPTA_CLAUDE_HOME` is the host's `~/.claude`,
  because the record lives in `~/.claude.json` beside it. Set
  `CHITRAGUPTA_CLAUDE_JSON` (see the table above) and recreate the
  container.
- `RC_SPAWN=worktree needs git in /workspace, using same-dir; git said:
  ...`. Sessions from the app then share `/workspace` instead of getting a
  worktree each. If git's message is `detected dubious ownership`, the
  workspace's owner is not `CHITRAGUPTA_UID`; fix the ownership, or add
  `git config --global --add safe.directory /workspace` inside the
  container.

Attach to the live session with:

```bash
docker exec -it chitragupta-claude tmux attach -t claude
```

## ⌨ Running pipeline commands inside the container

The same commands as the main README's Quickstart work directly with no
venv prefix, since `/opt/venv` is already on `PATH` (and exported as
`VIRTUAL_ENV`, so Poetry installs into it rather than creating its own)
inside the container:

```bash
python -m chitragupta.corpus sync
python -m chitragupta.enrich --stages embed,bertopic
python -m chitragupta.draft gate content/drafts/<slug>.md
```

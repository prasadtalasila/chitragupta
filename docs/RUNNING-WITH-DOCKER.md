# 🐳 Running with Docker

Two images, for two different jobs. Neither is a variant of the other
and neither replaces the other:

| File | What it is | Size | Needs a checkout |
| --- | --- | --- | --- |
| `docker/Dockerfile` | The **toolchain image**. Builds the full TeX Live/Pandoc/Poetry/torch stack from this repository's own `scripts/install_full_pipeline.sh`, for hosts where you don't hold root. Mount your checkout, get a shell with everything resolved. | 4.38GB (cpu) / 11.6GB (gpu) | Yes -- it is the checkout you mount and work in |
| `docker/Dockerfile.claude` | The **agent image**. Node, Claude Code, and a `/opt/venv` install of the published `chitragupta-cli` package, driven by `docker/docker-compose.yml` as a long-lived `claude remote-control` host. The toolchain is *not* baked in; you add what you need at runtime with `chitragupta install`. | ~2.5GB | No -- it installs from PyPI |

`docker/Dockerfile` is documented first, then the agent image under
["The agent container"](#-the-agent-container-dockerdockerfileclaude).

There's nothing Docker-exclusive about any individual piece of the
toolchain image -- `scripts/install_full_pipeline.sh` is the single
install path for both the host and it.

**Getting `docker/` without a checkout.** `chitragupta init` doesn't
scaffold `docker/` (it has nothing to mount into a toolchain image built
from a pip install), and a `pip install chitragupta-cli` doesn't carry
it either. Every tagged [GitHub
Release](https://github.com/prasadtalasila/chitragupta/releases) attaches
a standalone `chitragupta-docker-<version>.zip` -- `docker/` plus this
page -- for exactly that case: unzip it and the commands below work with
no other part of the repository present. `DOCKER.md` at the repository
root is this project's own record of how these two images are verified
before a release, not something a Docker user needs to read.

## 🔧 Build

```bash
docker build -t chitragupta -f docker/Dockerfile .
```

This runs `scripts/install_full_pipeline.sh` twice as separate,
independently cached layers -- `os-deps`, then `python-deps` (via
Poetry, with `SKIP_VENV=1` so it installs into `/opt/venv` instead of
creating its own) -- so editing later Dockerfile lines or unrelated repo
files doesn't force earlier layers to rebuild.
**Exception**: the script itself is `COPY`'d once, before either of the
two stages runs, so editing `scripts/install_full_pipeline.sh`
invalidates both layers --
Docker's cache keys each layer on the exact command *and* any files that
command's `COPY` depends on, and this file feeds both of them. The
`python-deps` layer pulls torch and Docling's models; expect a long
first build.

### ⚖ CPU-only vs. GPU-capable: `TORCH_VARIANT`

`torch` isn't pinned in `pyproject.toml` (it's a transitive dependency of
`sentence-transformers`/`docling`/`accelerate`; see that file's own
comment) -- `poetry.lock` resolves whatever plain PyPI's default Linux
wheel currently is, and that wheel bundles the full CUDA runtime as
separate `nvidia-*` packages (`cublas`, `cudnn`, `nccl`, `triton`, ...)
regardless of whether the build host or the eventual container ever sees
a GPU. The `docker/Dockerfile` build arg `TORCH_VARIANT` controls which
one you get:

| `TORCH_VARIANT` | Build command | Measured image size | When to use it |
| --- | --- | --- | --- |
| `gpu` (default) | `docker build -t chitragupta -f docker/Dockerfile .` | 11.6GB | `docker run --gpus` deployments -- the bundled CUDA runtime is enough on its own, no host CUDA toolkit needed, only a matching driver |
| `cpu` | `docker build -t chitragupta -f docker/Dockerfile --build-arg TORCH_VARIANT=cpu .` | 4.38GB | Everything else -- embeddings/clustering/rendering all run fine on CPU, and this is what you want for build-verification or a host with no GPU at all |

The `cpu` variant reinstalls `torch`/`torchvision` from PyTorch's own
CPU-only wheel index, at the exact version `poetry.lock` resolved (read
back via `pip show` rather than pinned a second time in the Dockerfile,
so it can't drift from a `poetry lock` re-resolution), then removes the
now-orphaned `nvidia-*`/`triton` packages. Both the swap and the removal
happen inside the same `RUN` as the original `poetry install`, so the
CUDA wheels never end up committed to a layer in the first place --
doing this as a later, separate `RUN` only marks them deleted and leaves
the image *larger*, since the earlier layer's bytes are still stored.

Sizes above also depend on the Poetry/pip download cache being purged in
that same layer (`rm -rf /root/.cache/pypoetry /root/.cache/pip`, at the
end of the `python-deps` `RUN`) -- without it, every build leaves the
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

The image deliberately doesn't bake the repo in -- it mounts it -- so the
`config.toml` the container reads is the one in *your* working copy. That
file is gitignored, so create it before the first run or `chitragupta.config`
will refuse to import:

```bash
cp config.toml.example config.toml
```

## ✅ Verify the toolchain

Inside the running container, check that the render and enrichment
dependencies actually resolved:

```bash
command -v latexmk pandoc pdftotext
python -c "import sentence_transformers, chromadb, bertopic, docling; print('enrich group OK')"
```

## 🤖 The agent container (`docker/Dockerfile.claude`)

A second, much thinner image whose job is to host **one long-lived
`claude remote-control` session** with this pipeline installed, rather
than to build the toolchain. It installs the *published*
`chitragupta-cli` package from PyPI into `/opt/venv` and copies no part of
this repository in, which is the whole difference: an image built from a
checkout has to be rebuilt to follow a release, and this one only has to
be restarted.

What that buys, and what it costs: the build is seconds rather than
tens of minutes and the image is ~2.5GB rather than 4.38GB, because
TeX Live, Pandoc and torch are **not** in it. You add whatever the work
actually needs on first run, with `chitragupta install` -- which is why
the image gives its user passwordless `sudo` (see below).

### 🧩 One environment, and why it is not `pipx`

`chitragupta-cli` goes into a venv at `/opt/venv` which is first on
`PATH` -- the same arrangement `docker/Dockerfile` uses -- so `python`,
`python3`, `pip`, `chitragupta` and `cg` are all the same environment.

That is not a style preference. `.claude/settings.json`, the one
`chitragupta init` scaffolds, launches every hook as `command:
"python"`. Install the package into a *private* venv, as `pipx` does,
and that `python` is the system interpreter, which cannot import it --
so the citation gate returns

```text
{"decision": "block", "reason": "The citation gate could not run --
this is an environment fault, not a bad citekey ..."}
```

on **every draft write**. This image was built with `pipx` first and
that is exactly what happened: a container that came up looking healthy
and refused to let anything be drafted in it. The gate is right to
block — it will not pass a draft it could not check — which is why the
fix belongs here rather than in the hook.

A `/etc/profile.d/` snippet carries the same `PATH` for **login**
shells, which source `/etc/profile` and rebuild `PATH` from scratch,
discarding what `ENV PATH` set. Worth knowing that the `pipx` version
appeared to survive a login shell only because Debian's `~/.profile`
re-adds `$HOME/.local/bin`, where pipx's shims happen to live -- luck,
not design.

### 🔧 Build and run

Build with a **temporary tag** while you are changing anything here, so
an existing `:latest` that other containers are running survives a
failed attempt:

```bash
docker build -t chitragupta-claude:tmp -f docker/Dockerfile.claude docker/
```

Note the build context is `docker/`, not the repository root -- nothing
outside that directory is needed, and a root context would send the
whole tree (worktrees included) to the daemon.

Then run it through compose, from inside `docker/` so its relative
defaults and its `.env` resolve:

```bash
cd docker
cp .env.example .env          # then edit CHITRAGUPTA_WORKSPACE
mkdir -p "$CHITRAGUPTA_WORKSPACE/papers"
docker compose up -d          # .env's COMPOSE_PROFILES picks cpu or gpu
docker exec -it chitragupta-claude bash
```

`docker/.env.example` is the tracked documentation of every variable
the compose file reads; `docker/.env` is gitignored. Nothing has to be
edited but `CHITRAGUPTA_WORKSPACE`.

That `mkdir` is not optional politeness. The Docker daemon creates a
missing bind-mount source itself, owned by `root:root` -- and for the
read-only papers mount the result is a directory nobody can put a PDF
in: read-only inside the container, root-owned outside it, silently.
Create both directories first and they stay yours.

### 🎛 Two profiles: `cpu` and `gpu`

**Neither service starts without a profile**, on purpose. `docker
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

Why a profile rather than one service that adapts: a reservation naming
the `nvidia` driver makes `up` **fail outright** on a host without the
NVIDIA Container Toolkit -- `could not select device driver` -- rather
than starting without a GPU. Compose has no conditional for a volume or
a reservation, so two services under two profiles is the only shape that
lets one file serve both machines. Verified both ways on a host with the
toolkit: `--profile gpu` reaches all three A40s and `nvidia-smi` inside
the container, `--profile cpu` shows no `/dev/nvidia*` at all.

### ⚙ What compose reads from the environment

Every path and name is a variable. The first version of this file
carried one developer's home directory and a release number in its own
filename, which made it unusable to anyone else and stale on the next
release. Set these in `docker/.env` or in the environment:

| Variable | Default | What it does |
| --- | --- | --- |
| `CHITRAGUPTA_WORKSPACE` | **required** | Host directory mounted at `/workspace` -- where `chitragupta init` scaffolds and where drafts land. Compose refuses to start without it rather than mounting something arbitrary |
| `CHITRAGUPTA_CONTAINER_NAME` | `chitragupta-claude` | The container's name, so `docker exec -it <name> bash` works. Also becomes the container hostname and the agent's name in the remote-control UI |
| `CHITRAGUPTA_PROJECT_NAME` | `chitragupta` | Compose's project name, which prefixes the network. Set it per workspace to run two of these side by side |
| `CHITRAGUPTA_IMAGE_TAG` | `latest` | Which tag to run. This is how you point one workspace at a `:tmp` build without disturbing the `:latest` everything else uses |
| `CHITRAGUPTA_CLAUDE_HOME` | `./claude` | Host directory for `/home/prasad/.claude`. This is what persists the login, so a restart is not a re-authentication |
| `CHITRAGUPTA_PAPERS` | `$CHITRAGUPTA_WORKSPACE/papers` | Host directory of PDFs, mounted **read-only** at `/workspace/papers`. Point it elsewhere to share one corpus across workspaces |
| `COMPOSE_PROFILES` | none | `cpu` or `gpu` -- see below. Compose's own variable, not one of ours |
| `CHITRAGUPTA_USER` | `chitragupta` | The unprivileged account inside the image. A **build** arg as well as a runtime setting, so changing it needs `docker compose build`, not just a restart |
| `CHITRAGUPTA_UID` / `CHITRAGUPTA_GID` | `1001` | That account's numeric ids. Set them to your own (`id -u`, `id -g`): they decide who owns a file the container writes into the workspace. 1001 rather than 1000 because the Node base image has already taken 1000 for its own `node` account |

Nothing in the image hardcodes an account name. `CHITRAGUPTA_USER`
reaches the `useradd`, the `/etc/sudoers.d/<user>` file, `$HOME`, the
`PATH` entry the venv installs into, and the mount point for
`CHITRAGUPTA_CLAUDE_HOME` -- one variable, so those five cannot
disagree. The entrypoint lives at `/usr/local/bin/entrypoint.sh` rather
than in the home directory for the same reason.

### 🚀 First run

The container starts before it can do anything useful, deliberately, and
in this order:

```bash
docker exec -it chitragupta-claude claude   # then /login
docker compose restart                      # the agent picks up the login
docker exec -it chitragupta-claude bash
chitragupta install os-deps                 # TeX Live, Pandoc, poppler, Vale
chitragupta init                            # scaffold /workspace
chitragupta doctor                          # what is still missing
```

`chitragupta install os-deps` is what the passwordless `sudo` in this
image exists for: it `apt-get install`s the toolchain that the image
does not ship. `chitragupta install` refuses `all`, `dev-deps` and
`python-deps` by name and prints the `pip` command that reaches them
instead -- including the enrichment stack, which is a separate step
because it is torch and would take the image past 6GB:

```bash
pip install 'chitragupta-cli[enrich]'   # /opt/venv, no sudo needed
```

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
entrypoint: WARNING -- the agent exited immediately. Its output was:
entrypoint:   Remote Control is only available with claude.ai subscriptions.
entrypoint:   Pane is dead (status 1, ...)
entrypoint: the container stays up so you can fix this in place:
entrypoint:   docker exec -it chitragupta-claude claude   # then /login, then restart
```

It reports rather than exiting non-zero on purpose: the fix needs a
running container to `docker exec` into, and a crash loop would take
that away. `docker logs <name>` is therefore the first thing to read
when the remote-control UI does not list your agent -- not `docker ps`,
which will say `Up` either way.

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

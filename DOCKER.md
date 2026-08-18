# Running with Docker

`docker/Dockerfile` builds the same TeX Live/Pandoc/Poetry stack inside
a container, for hosts where the user doesn't hold root permissions.
There's nothing Docker-exclusive about any individual piece --
`scripts/install_full_pipeline.sh` is the single install path for both
the host and this image.

**Built and verified manually** (`docker build`, both `TORCH_VARIANT`
values below, each image's `/opt/venv` confirmed to import
`sentence_transformers`/`chromadb`/`bertopic`/`docling`/`torch`
correctly). Not exercised by CI -- no workflow under `.github/` builds
this image, so a break here won't be caught automatically; re-verify by
hand after changing `docker/Dockerfile`, `scripts/install_full_pipeline.sh`,
or `poetry.lock`.

## Build

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

### CPU-only vs. GPU-capable: `TORCH_VARIANT`

`torch` isn't pinned in `pyproject.toml` (it's a transitive dependency of
`sentence-transformers`/`docling`/`accelerate`; see that file's own
comment) -- `poetry.lock` resolves whatever plain PyPI's default Linux
wheel currently is, and that wheel bundles the full CUDA runtime as
separate `nvidia-*` packages (`cublas`, `cudnn`, `nccl`, `triton`, ...)
regardless of whether the build host or the eventual container ever sees
a GPU. The `docker/Dockerfile` build arg `TORCH_VARIANT` controls which
one you get:

| `TORCH_VARIANT` | Build command | Measured image size | When to use it |
|---|---|---|---|
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

## Run

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
file is gitignored, so create it before the first run or `src.config`
will refuse to import:

```bash
cp config.toml.example config.toml
```

## Verify the toolchain

Inside the running container, check that the render and enrichment
dependencies actually resolved:

```bash
command -v latexmk pandoc pdftotext
python -c "import sentence_transformers, chromadb, bertopic, docling; print('enrich group OK')"
```

## Running pipeline commands inside the container

The same commands as the main README's Quickstart work directly with no
venv prefix, since `/opt/venv` is already on `PATH` (and exported as
`VIRTUAL_ENV`, so Poetry installs into it rather than creating its own)
inside the container:

```bash
python -m src.corpus sync
python -m src.enrich --stages embed,bertopic
python -m src.draft gate content/drafts/<slug>.md
```

To run the test suite inside the container, add the `dev` group:

```bash
SKIP_VENV=1 bash scripts/install_full_pipeline.sh dev-deps
python -m pytest --cov=src --cov=scripts --cov-report=term-missing
```

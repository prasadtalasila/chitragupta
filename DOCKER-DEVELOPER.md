# 🐳 Docker: how these images are built and verified

For "how do I run this in a container" (building an image, running it,
the agent container's compose profiles, first-run steps), see
[DOCKER.md](DOCKER.md) instead. That file ships wherever the pipeline
does: in the pip package, in `chitragupta init`'s scaffold, and in every
release's standalone `chitragupta-docker-<version>.zip`. This file is
this repository's own record of how the two images (`docker/Dockerfile`,
the toolchain image; `docker/Dockerfile.claude`, the agent image) are
verified before a release. It is for someone changing either Dockerfile;
someone running one does not need it.

What CI does and does not build:

| Image | Built by CI | Run by CI |
| --- | --- | --- |
| `docker/Dockerfile` | **Yes**: `ci.yml`'s `docker-build` job runs `docker build --build-arg TORCH_VARIANT=cpu` on every push and PR (#302) | No. It builds and is thrown away; nothing execs into it |
| `docker/Dockerfile.claude` | No; no workflow builds it | No |

So a break in the toolchain image's *build* is caught automatically; a
break in anything it does at runtime is not, and nothing about the agent
image is. `shellcheck docker/*.sh` in the `lint` job is the only other
automated check that reaches this directory, and it sees `entrypoint.sh`
alone.

Because CI only builds the `cpu` variant, the toolchain image is also
verified by hand: `docker build` with both `TORCH_VARIANT` values, and
each image's `/opt/venv` confirmed to import
`sentence_transformers`/`chromadb`/`bertopic`/`docling`/`torch`
correctly. Re-verify after changing `docker/Dockerfile`,
`scripts/install_full_pipeline.sh`, or `poetry.lock`; the agent image
has its own hand-run checks, under
["Verify the container"](DOCKER.md#-verify-the-container) in that file.

Since the base moved to Ubuntu 26.04 LTS / Python 3.14, that
`docker-build` job is also the only automated check that installs
`poetry.lock` under Python 3.14 at all; the test matrix runs 3.12 and
3.13. A re-lock that drifts back below the cp314 wheel line (the failure
mode issue #607 documents, which leaves CI otherwise green) fails there
instead of on a user's machine. `pyproject.toml`'s comment on the
`python` range explains why that drift is possible in the first place, and
[docs/UV-MIGRATION.md](docs/UV-MIGRATION.md) has the measurements
behind it.

## 🧪 Running the test suite inside the toolchain container

This is not part of running the pipeline. It checks that a change to
`docker/Dockerfile` or `scripts/install_full_pipeline.sh` also resolves
the dev dependencies:

```bash
SKIP_VENV=1 bash scripts/install_full_pipeline.sh dev-deps
python -m pytest --cov=chitragupta --cov=scripts --cov-report=term-missing
```

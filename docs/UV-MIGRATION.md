# 📦 Poetry, uv, and the lockfile that would not regenerate

A decision record. It exists because `poetry lock --regenerate` stopped
finishing on this project, the investigation that followed produced
numbers worth keeping, and "should we move to uv?" is a question that
will be asked again by someone who does not have those numbers.

**The short version:** the resolver problem is real and measured, the
cheap fix is a script rather than a migration, and uv's advantage is
almost entirely in *resolution* rather than installation -- which is the
opposite of the usual reason people cite for switching.

## 🔍 The problem

`poetry lock --regenerate` does not terminate on this dependency set.
Measured 2026-09-05: over 600 seconds before being killed, and on an
earlier attempt with a wider Python range, **22 hours** without
producing a lock.

That is not merely slow. A lockfile that cannot be regenerated cannot be
audited, and a security bump needing a full re-resolution has no route
at all.

### Where the time goes

A running resolve was sampled every 30 seconds:

```text
  t=30s  cpu=86.2%  rss=544MB  downloaded=+0MB
  t=60s  cpu=93.1%  rss=568MB  downloaded=+0MB
  ...
  t=240s cpu=98.2%  rss=568MB  downloaded=+0MB
```

**Nothing is downloaded, CPU is pegged, memory is flat.** This is
backtracking inside the resolver, not metadata fetching -- which rules
out every index, mirror or cache setting. `solver.lazy-wheel` was
already on.

### Which dependencies cost it

| Dependency set | Locked packages | `poetry lock --regenerate` |
| --- | --- | --- |
| core + dev + docs (no `enrich` group) | 38 | **3 seconds** |
| everything | 202 | **>600s, killed** |

The optional `enrich` group -- 164 of the 202 packages, the
torch/docling/chromadb/BERTopic stack -- is the entire cost. The core
package has exactly one runtime dependency.

### Two things that are *not* the cause

Both were tested, because both look guilty:

- **`adapters` is not it.** It carries a single-patch pin
  (`transformers~=4.57.6`) that looks like an obvious resolver trap.
  Removing it entirely and regenerating still ran **581 seconds** before
  being killed. It *does* cap `sentence-transformers` at 5.x, which is a
  real and separate problem, but it is not the resolution cost.
- **The Python range is not it either.** Narrowing from `^3.12` to
  `>=3.12,<3.14.1 || >3.14.1,<3.15` was a *correctness* fix: `<4.0`
  forced the resolver to reject any `triton` (which declares
  `requires_python <3.15`), so it silently selected a torch with no
  wheels for Python 3.14 and produced a lock that could not install in
  this project's own container. It reduced the pathology; it did not
  remove it.

### What still works

With `poetry.lock` present, targeted operations are fine:

| Operation | Time |
| --- | --- |
| `poetry lock` after editing one constraint | ~40s |
| `poetry update --lock <one package>` | ~43s |
| `poetry update --lock` (everything) | >500s, killed |
| `poetry lock --regenerate` (from nothing) | >600s, killed |

So day-to-day dependency work is unaffected. What is broken is every
operation that re-resolves the whole graph at once.

## ⚖ uv measured against Poetry

Same machine, same container image (Ubuntu 26.04, Python 3.14.4), same
network, same resolved versions (`torch 2.14.0+cu130` verified importable
from both installs).

| Operation | Poetry | uv |
| --- | --- | --- |
| Resolve the enrich set from scratch | **>600s, killed** | **1.7s** (175 packages) |
| Install, cold cache | 60s | 37s |
| Install, warm cache | 23s | 1s |

**Read this table carefully, because the headline is not the one people
expect.** Installation is 1.6x faster cold -- worth having, not worth a
migration. The warm-cache figure (23s to 1s) matters mainly to CI, which
installs on every run. The number that justifies anything is
**resolution**, where the difference is not a factor but a change of
kind: seconds against "does not finish".

## 💰 What migrating would cost

Measured against the tree as it stands.

**Breadth.** 86 tracked files mention Poetry. The load-bearing ones:

| File | Occurrences |
| --- | --- |
| `scripts/install_full_pipeline.sh` | 43 |
| `pyproject.toml` | 40 |
| `.github/workflows/ci.yml` | 24 |
| `docker/Dockerfile` | 15 |
| `DEVELOPER-AGENTS.md` | 11 |
| `.github/workflows/release.yml` | 8 |
| `.github/workflows/docs.yml` | 8 |

**`pyproject.toml` is entirely Poetry-native** -- 10 `[tool.poetry*]`
tables and no `[project]` table at all. Migrating means a full PEP 621
conversion, which changes the *published wheel metadata* of a package
already on PyPI. That deserves a before-and-after comparison of the built
artifacts, not just a green test run.

**Version plumbing moves.** `scripts/release.py` and
`scripts/check_version_bump.py` read `[tool.poetry].version`, which
becomes `[project].version`. Both are covered by tests, so the tests move
with them. Ten test files mention Poetry.

**Two installation paths change.** Poetry arrives here as
`python3-poetry` from apt (in the `os-deps` stage) and as
`pipx install poetry==2.4.1` in the release workflow. This is the
cheapest cost to absorb: `scripts/install_full_pipeline.sh` already
downloads pinned, **SHA256-verified** binaries by `curl` for `actionlint`
and `vale`, verifying the digest before unpacking. A pinned uv binary
fits that established pattern exactly.

**Lock format maturity.** `poetry.lock`'s format is stable and old.
`uv.lock`'s is younger and has changed more. For a repository that pins
`ruff` to an exact version specifically because an unpinned bump could
move a verdict, that is a real consideration rather than a theoretical
one.

**The Windows CI leg needs revalidation.** uv supports Windows, but that
leg carries a lower coverage floor and platform-specific skips that were
tuned against the current toolchain.

**Documentation debt.** `DEVELOPER-AGENTS.md`, `DEVELOPER.md`,
`DOCKER.md`, `PACKAGING.md`, `README.md`, nine skill documents under
`.claude/`, the pull-request and issue templates, and
`.opencodereview/rule.json` all name Poetry.

## 🎁 What migrating would gain

**Resolution stops being a problem**, permanently -- see the table
above. This is the only reason that stands on its own.

**A whole class of duplication disappears.** `tests/test_pyproject_extras.py`
exists to keep two lists in agreement, and its own docstring says why:

> two lists that must agree, because they are declared in two unrelated
> places **for a Poetry limitation, not by choice**: a group dependency
> never reaches a built wheel's metadata

That is 17 `optional = true` mirror entries plus a guard test, all of it
compensating for Poetry groups not reaching wheel metadata. Under PEP 621
`[project.optional-dependencies]` each extra is declared once, and the
mirroring, the drift risk and the test guarding it all go away.

**Possibly the most delicate part of the install script.**
`pyproject.toml` records that `ensure_gpu_torch` exists because *"poetry
has no concept of 'pick a different index based on the host's GPU
driver'"*. uv has first-class torch index selection. **This has not been
verified on a GPU host here** -- it is the strongest remaining reason to
run an experiment before deciding.

## ✅ Recommendation

**Do not migrate to fix the lockfile.** That is a multi-pull-request
change deployed against a problem a script solves in under two minutes.
`scripts/relock.py` is that script:

```bash
python3 scripts/relock.py            # regenerate poetry.lock
python3 scripts/relock.py --check    # resolve and report, write nothing
```

What it does, and why each step is there:

1. Resolve the declared constraints with `uv pip compile`.
2. Write those exact versions back into `pyproject.toml` as temporary
   `==` pins.
3. `poetry lock` -- fast, because nothing is left to search.
4. Restore the original `pyproject.toml`.
5. `poetry lock` again. Not decoration: step 3's lock is correct but its
   `content-hash` belongs to the pinned file about to be discarded, so
   this re-locks against the real one, keeping the versions step 3 found
   because a lock is now present.

Measured on a full run: **uv 1.4s, pinned lock 63s, restoring lock 40s
-- 103 seconds in total**, against a `poetry lock --regenerate` that does
not finish. It changes nothing about how the project is built or
installed, and keeps `pip install 'chitragupta-cli[enrich]'` working
exactly as it does now. On any failure -- including `Ctrl-C` -- it puts
`pyproject.toml` and `poetry.lock` back as it found them, because a
half-pinned `pyproject.toml` left behind looks like a hand edit later.

**Separately, move `adapters` out of the shipped dependency set.** It has
zero imports under `chitragupta/` and one under `bench/`, and
[CONFIG.md](CONFIG.md) lists SPECTER2 under "Not without a code change
first". It is a benchmark dependency living in the published package's
metadata, and it is what caps `sentence-transformers` at 5.x. This is
worth doing on its own merits and will **not** speed up resolution.

**Migrate only if the dependency set keeps growing.** The honest case for
uv here is not speed; it is that two of this project's documented
workarounds -- the extras mirroring and `ensure_gpu_torch`'s index
juggling -- exist because of Poetry limitations that uv does not have. If
the enrich stack keeps expanding, that tax is paid repeatedly. If the set
is roughly stable, Poetry plus a relock script is the cheaper
equilibrium.

**If you do migrate, sequence it** rather than attempting one change:
the PEP 621 conversion and the version scripts first (self-contained and
testable), then the install script and the container images, then CI and
the documentation.

## ❓ What has not been verified

Stated so nobody mistakes this document for a completed evaluation:

- ~~The relock procedure has not been run end to end.~~ It has:
  `scripts/relock.py` regenerated this repository's own lock in 103
  seconds, and the lock it produced is the one this project ships.
- uv's torch index handling has **not** been tried on a GPU host, so
  whether it could replace `ensure_gpu_torch` is unknown.
- Whether the built wheel is **metadata-equivalent** after a PEP 621
  conversion has not been checked, and it is the thing most likely to
  surprise a published package.
- The install timings above are single runs on one machine and one
  network. The resolution figures are reproducible and lopsided enough
  that variance does not matter; the install figures are close enough
  that it might.

# 📦 Packaging: the installable distribution and its command surface

Status: **reference.** Written 2026-08-19. Updated 2026-08-24.

What `chitragupta-cli` installs, what you type once it is installed, and
which of the three names that look identical is actually registered
anywhere.

**Written for** anyone installing this without a git checkout, and anyone
about to change a command name.

**Not covered here:** what each command *does* -- [CLI.md](CLI.md) is the
exhaustive per-flag reference and stays so. This file is the surface and
the naming, not the semantics.

> **Status of this document.** The distribution is real as of 6.0.0, and
> #258's whole series has now landed: the import package is
> `chitragupta`, `pyproject.toml` declares a `[build-system]`, and
> `poetry build` produces `chitragupta_cli-<version>-py3-none-any.whl`,
> which installs the `chitragupta` and `cg` commands. Every row in the
> table below is live -- the four layers, and `init`/`doctor`/`install`
> alike -- and `chitragupta-cli` is published to PyPI via Trusted
> Publishing (#269), on every major or minor release -- a PATCH release
> still gets a GitHub Release with the wheel attached, but does not also
> reach PyPI, since a published version can never be reused if one had
> to be spent again for a documentation or CI-only fix. [CLI.md](CLI.md)
> carries the exhaustive per-flag reference; this table is the surface.

## 🧭 Table of contents

- [Three names, one of them registered](#-three-names-one-of-them-registered)
- [The command surface](#-the-command-surface)
- [The module form, and why it survives](#-the-module-form-and-why-it-survives)
- [What the decision answers](#-what-the-decision-answers)
- [Why the zip ships too](#-why-the-zip-ships-too)
- [What a shipped command name costs](#-what-a-shipped-command-name-costs)

## 🏷 Three names, one of them registered

They read as one name and are three unrelated things. Only the first is
globally unique; the other two are directories any distribution may write
into.

| | Value | Uniqueness enforced by |
| --- | --- | --- |
| Distribution (the PyPI project) | `chitragupta-cli` | **PyPI, globally** |
| Import package (`site-packages/`) | `chitragupta` | nobody -- first writer, then overwrite |
| Console scripts (venv `bin/`) | `chitragupta`, `cg` | nobody -- same |

`pip install chitragupta` does **not** reach this project. That name
belongs to an unrelated package (`chitragupta` 0.1.1, "Pytest for your
prompts", uploaded 2026-05-07), whose own wheel declares a `chitragupta`
console script and a `chitragupta` import package. `chitragupta-cli` was
free; the command you type stays `chitragupta`, because the command name
is not a PyPI name and never was.

```bash
pip install chitragupta-cli
```

Published from a tagged major or minor release by **Trusted
Publishing** -- GitHub's OIDC token exchanged for a short-lived PyPI
one -- so there is no long-lived API token in repository settings to
leak or rotate. **A PATCH release is not published here.** PyPI never
accepts a re-upload of a version number, not even a deleted or yanked
one, so `.github/workflows/release.yml`'s `publish-pypi` job only runs
for a tag ending `.0` (X.0.0 or X.Y.0); a PATCH tag still gets a GitHub
Release with the wheel attached, just not a PyPI upload. The publish job
runs *after* the GitHub Release is created, so a PyPI failure would
leave a complete, downloadable release behind rather than a tag with
nothing attached -- the ordering that mattered on the first tag,
`v6.7.0`, before the publisher was registered on PyPI against this
repository; every major or minor tag since has published cleanly.

`cg` is likewise **not** a second PyPI project. One distribution declares
both executables against one entry point:

```toml
[tool.poetry.scripts]
chitragupta = "chitragupta.__main__:main"
cg          = "chitragupta.__main__:main"
```

The residual collision -- both distributions in one environment overwrite
each other's `site-packages/chitragupta/` and `bin/chitragupta`, which pip
does not refuse -- is accepted, on one condition: `chitragupta doctor`
detects the competing distribution and names it. An overwritten command is
survivable; an *undetected* one running the wrong program under the right
name is the failure class
[HOOKS.md](HOOKS.md#-the-launcher-contract) exists to prevent.

## ⌨ The command surface

Four layers, unchanged from what `python -m chitragupta.<layer>` already exposes,
plus four commands that only make sense once the code is installed rather
than cloned. Every flag, exit code and subcommand name is the one that
command already has -- this is a front door, not a redesign.

### 📦 The package itself

| Command | What it does |
| --- | --- |
| `chitragupta init [DIR] [--force] [--dry-run]` | Scaffold a project directory -- `config.toml`, `.claude/` skills and hooks, `papers/`, `content/`, `assets/`, the prose docs. What the release zip ships today |
| `chitragupta doctor` | Probe and report: OS binaries, the `enrich` extra, torch against the GPU driver, a competing `chitragupta` distribution. Exits 0 on findings -- an aid, never a gate |
| `chitragupta install os-deps\|gpu-torch` | Run the shipped `install_full_pipeline.sh` for the stages pip cannot do. Other stages are refused by name with the pip equivalent |
| `chitragupta --version` | The installed distribution's version, from `importlib.metadata` |

### 📚 `corpus` -- the deterministic run

| Command | Flags |
| --- | --- |
| `chitragupta corpus sync` | `--reparse`, `--remove-stale` |
| `chitragupta corpus ledger` | `--list`, `--status`, `--citekey`, `--collection`, `--collections` |
| `chitragupta corpus topics` | `--topic` |

### ✍ `draft` -- work on one draft

| Command | Subcommands / flags |
| --- | --- |
| `chitragupta draft gate <file>...` | -- (takes no options; this is the hard gate) |
| `chitragupta draft references <file>` | `--heading` |
| `chitragupta draft evidence <file>` | `--format`, `--output-dir` |
| `chitragupta draft render <file>` | `--format`, `--documentclass`, `--fontsize`, `--papersize`, `--margin`, `--csl`, `--output-dir`, `--fragment`, `--no-collapse-citations` |
| `chitragupta draft style <draft>...` | `--language`, `--json` |
| `chitragupta draft retrieve` | `search`, `evidence` |
| `chitragupta draft dossier` | `init`, `status`, `mark-revision`, `stamp`, `sections`, `outline`, `brief`, `set-language`, `acronyms-suggest`, `check-evidence`, `list`, `export`, `restore` |
| `chitragupta draft spec` | `init`, `show`, `sign`, `status` |
| `chitragupta draft unit` | `contract`, `accept`, `status` |
| `chitragupta draft registry` | `build`, `check`, `excerpt` |
| `chitragupta draft tldr` | `write`, `show` |

### 🔍 `review` -- read-only aids, no gate

| Command | Subcommands / flags |
| --- | --- |
| `chitragupta review provenance <draft>` | `--json`, `--formats` |
| `chitragupta review verbatim` | `overlap`, `scan`, `recheck`, `locate` |
| `chitragupta review coverage <draft>` | `--query` (required, repeatable), `--k`, `--json`, `--write`, `--formats` |
| `chitragupta review synthesis <draft>` | `--unit`, `--json`, `--write`, `--formats` |
| `chitragupta review figure <draft>` | `--json`, `--write`, `--formats` |
| `chitragupta review uncited <draft>` | `--genre`, `--json`, `--write`, `--formats` |
| `chitragupta review quotation <draft>` | `--json`, `--write`, `--formats` |
| `chitragupta review agenda <draft>` | `--json`, `--formats` |
| `chitragupta review support <draft>` | `--json`, `--write`, `--formats` |

### 🧠 `enrich` -- optional, whole-corpus

| Command              | Flags                                                                                                                                         |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `chitragupta enrich` | `--stages docling,embed,bertopic,seed-topics,converge`, `--for-draft PATH`, `--target host\|docker` (informational only -- the probes decide) |

That is 4 layers and 24 verbs and aids (3 + 11 + 9 + 1), plus 3
package-level commands, giving **51 invocable leaf commands**: 3 + 3 +
(5 + 27) + (8 + 4) + 1. The counts are stated because a table is easy to
extend and easy to forget to extend; #267 pins them with a test that
walks the live parsers, so a verb added without a row here fails the
suite.

One thing is deliberately absent. `chitragupta/sync.py` still carries a
`__main__` block, which makes it look like a fifth entry point; it is a
**tombstone**, refusing with exit 64 because the corpus layer's old
direct invocation was removed in 5.2.0. After the rename it must keep
refusing, with its message updated to name the current command. This
paragraph deliberately does not spell that old invocation out --
`tests/test_removed_command_scan.py` fails any document that hands a
reader a command which no longer works, and it decides by path rather
than by reading the surrounding sentence.

## 💡 The module form, and why it survives

Every row above has an exact equivalent:

```text
chitragupta <layer> <verb> ...   ==   python -m chitragupta.<layer> <verb> ...
```

Both are supported, deliberately, and they are for different callers:

- **The console script is for humans.**
- **The module form is what `.claude/hooks/` and the genre skills use**,
  and that is not a style preference. A console script lives in one venv's
  `bin/`; the module form resolves from any interpreter that can import
  the package. [CLI.md](CLI.md#-which-interpreter) records why tier 1
  exists at all -- the gate chain must not be blockable by a broken venv
  -- and `chitragupta/hook_launchers.py` records the measurement behind it: a hook
  launcher that does not resolve produces *nothing at all*, no error and
  no log entry. Routing the citation gate through a `PATH` lookup that can
  silently miss is the one change in this whole series that would be worse
  than not doing it.

So the two forms are not redundancy to be tidied away later. Keep both.

## ⚖ What the decision answers

`pyproject.toml` used to say packaging was "a separate, larger decision
this project explicitly isn't making", and pointed at a **packaging
pros/cons write-up that never existed**. Searched before this file was
written: every tracked `.md`, git history including deleted paths, all
6,537 issue comments and every PR review comment, and
[TECHNICAL-DEBT.md](TECHNICAL-DEBT.md)'s "What is not debt" table. The
reasoning was a conversation, not an artefact. This section is the
artefact it should have been, and it is written as the objections rather
than as a conclusion, because three of them survive.

| The objection | Where it was written | What happened to it |
| --- | --- | --- |
| Needs renaming the `src` layout | `pyproject.toml` header | **Retired by doing it.** A top-level `src` in `site-packages` claims the most generic name on the index; it is unshippable at any price |
| "Don't add a second install path" | `DEVELOPER-AGENTS.md` (git checkout only) | **Survives as an invariant, not as a mechanism.** The goal was one place a dependency fact can be written. There are now two front doors to one `install_full_pipeline.sh` and one `pyproject.toml` |
| Tier 1 must not be blockable by a broken venv | [CLI.md](CLI.md#-which-interpreter) | **Retired by keeping the module form** -- see above. The hooks never move to the console script |
| pip cannot pick a wheel index from the GPU driver | `pyproject.toml`'s torch note | **Survives, reduced.** `pip install …[enrich]` still lands CPU-only torch on a CUDA host. `chitragupta doctor` detects it and `chitragupta install gpu-torch` fixes it -- but neither is automatic |
| Command names can be renamed freely because nothing external holds them | the PR closing #123 | **Survives, sharpened** -- see [the last section](#-what-a-shipped-command-name-costs) |
| The deliverable is the docs and skills, not the code | `scripts/release.py`'s docstring | **Retired by `chitragupta init`.** This was the strongest objection and the reason a bare wheel would have been the wrong shape |
| Everything is anchored to where the *code* lives | `chitragupta/config.py`'s `REPO_ROOT` | **Retired by splitting it** into a discovered project root and a package-data root |

## 🗜 Why the zip ships too

The release archive does not go away. It is built by a **denylist** --
`scripts/release.py` ships every git-tracked file except a named few, so
a new root-level file ships unless someone excludes it. `chitragupta
init` is an **allowlist**: a new root-level file is *not* scaffolded
unless someone adds it.

Two lists that must agree drift, and this repository has already had that
bug once (a root-level CI file entered the archive silently and was caught
by review rather than by a check). So the two are pinned against each
other by a test, with the deliberate differences -- `bench/`, `tests/`,
`.github/`, and the CI config that is actively wrong outside this
repository -- held in one named set that both sides read.

## ⚡ What a shipped command name costs

Worth stating where the next person renaming a verb will read it.

Until this package ships, renaming a command is nearly free: the strings
live only in this repository's own docs, skills and tests, so a rename is
a sweep plus a migration-table row. That freedom has been spent twice --
`chitragupta.heavy.*` abandoned in 3.0.0, and the flat provenance/coverage paths
folded into `chitragupta.review` in 5.0.0.

An installed console script ends it. After `chitragupta` exists in users'
`bin/`, the name also lives in shell scripts, Makefiles, CI configs, cron
jobs and muscle memory -- places `git grep` cannot reach. A verb rename
becomes a MAJOR bump with a deprecation window, and breaks somebody's
setup anyway.

The verb vocabulary was chosen once and argued for at the time (`chitragupta/draft.py`'s
own docstring sets out why `retrieve` rather than `retrieval`). From the
first published release it is chosen for good.

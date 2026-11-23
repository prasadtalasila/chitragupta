# 📦 Packaging: the installable distribution and its command surface

Status: **reference.**

What `chitragupta-cli` installs, what you type once it is installed, and
which of three look-alike names is registered anywhere. It is for anyone
installing without a git checkout, and anyone about to change a command
name. [CLI.md](CLI.md) is the per-flag reference for what each command
does.

`uv build` produces `chitragupta_cli-<version>-py3-none-any.whl`,
which installs the import package `chitragupta` and the `chitragupta`
and `cg` commands. Only a major or minor version is released, on GitHub
and PyPI together.

## 🏷 Three names, one of them registered

Only the first is globally unique; the other two are directories any
distribution may write into.

| | Value | Uniqueness enforced by |
| --- | --- | --- |
| Distribution (the PyPI project) | `chitragupta-cli` | **PyPI, globally** |
| Import package (`site-packages/`) | `chitragupta` | nobody: first writer, then overwrite |
| Console scripts (venv `bin/`) | `chitragupta`, `cg` | nobody, same as above |

`pip install chitragupta` does **not** reach this project. That name
belongs to an unrelated package (`chitragupta` 0.1.1, "Pytest for your
prompts"), whose wheel also declares a `chitragupta` console script and
import package. The command you type stays `chitragupta`, because a
command name is not a PyPI name.

```bash
pip install chitragupta-cli
```

It is published by Trusted Publishing (GitHub's OIDC token exchanged
for a short-lived PyPI one), so no long-lived API token sits in
repository settings. **A PATCH version is not released, here or on
GitHub.** PyPI never accepts a re-upload of a version number, even a
deleted or yanked one, and a PATCH changes nothing about what the
pipeline does, so it merges to `main` and ships with the next major or
minor release. `.github/workflows/release.yml` runs only for a tag
shaped `vX.Y.0`, so every version on the releases page is on PyPI, and
the reverse. The publish job runs *after* the GitHub Release is
created, so a PyPI failure leaves a complete release behind rather than
a bare tag.

`cg` is **not** a second PyPI project. One distribution declares both
executables against one entry point:

```toml
[project.scripts]
chitragupta = "chitragupta.__main__:main"
cg          = "chitragupta.__main__:main"
```

The residual collision is accepted on one condition. Both distributions
in one environment overwrite each other's `site-packages/chitragupta/`
and `bin/chitragupta`, and pip allows it; `chitragupta doctor` detects
the competing distribution and names it. An overwritten command is
survivable; an *undetected* one running the wrong program under the
right name is the failure class
[HOOKS.md](HOOKS.md#-the-launcher-contract) exists to prevent.

## ⌨ The command surface

The four layers `python -m chitragupta.<layer>` exposes, plus commands
that only make sense once the code is installed. Every flag, exit code
and subcommand is the layer's own; the console script adds a front
door and redesigns nothing.

### 📦 The package itself

| Command | What it does |
| --- | --- |
| `chitragupta init [DIR] [--force] [--dry-run] [--agent NAME]` | Scaffold a project directory: `config.toml`, `.claude/` skills and hooks, `papers/`, `content/`, `assets/`, the prose docs. `--agent codex` or `opencode` (repeatable, default `claude`) adds that harness's launcher and copy of each `SKILL.md`; `.claude/` is always written, as it holds the hooks and each skill's references ([LLM-AGENTS.md](LLM-AGENTS.md), [HARNESS.md](HARNESS.md)) |
| `chitragupta doctor` | Probe OS binaries, the `enrich` extra, torch against the GPU driver, a competing `chitragupta` distribution, and hook launchers that cannot start. Exits 0 on findings; never a gate |
| `chitragupta install os-deps\|gpu-torch\|enrich` | Run the shipped `install_full_pipeline.sh` for stages pip cannot do, or install the `enrich` extra at the running version. `all`, `dev-deps` and `python-deps` are refused with the pip equivalent |
| `chitragupta figure sync [PATH ...] [--check]` | Stamp or refresh the house figure-style block in each figure file, never touching a hand-edited block ([TIKZ-STYLE.md](TIKZ-STYLE.md#-the-house-figure-style)). Exits 0; `--check` writes nothing and exits 1 if a file is not current; 2 if the installed block cannot be read |
| `chitragupta figure check <figure.tex> [--page article\|book] [--width PT] [--layout NAME] [--json]` | Report every rule one figure breaks, its `% cg-allow:` exceptions, and its size beside its layout's reference ranges ([figure-checks/README.md](figure-checks/README.md)). Exits 0 whatever it finds; 2 on a usage error or with no `lualatex` or `tikz.sty` |
| `chitragupta figure new <figures-dir> <name> --layout ID` | Start a figure from a layout's scaffold in `assets/tikz/`, never overwriting one ([CLI.md](CLI.md#-chitragupta-figure-new)). Exits 0 once written; 2 on a refusal or an unreadable install |
| `chitragupta figure look <figure.tex> [--draft DRAFT] [--output-dir DIR]` | Set one figure on the page it prints on, cropped, as a PDF and a 300 dpi PNG under `content/rendered/` or `DIR`; `--draft` also pictures the draft's page that holds it ([CLI.md](CLI.md#-chitragupta-figure-look)). Exits 0 whatever it finds; 2 on an unreadable figure or a missing tool |
| `chitragupta --help` | Every layer and package command with its verbs under it; each command's own `--help` has its flags ([CLI.md](CLI.md#-every-command-and-flag)) |
| `chitragupta --version` | The installed distribution's version, from `importlib.metadata` |

### 📚 `corpus` -- the deterministic run

| Command | Flags |
| --- | --- |
| `chitragupta corpus sync` | `--reparse`, `--remove-stale` |
| `chitragupta corpus ledger` | `--list`, `--status`, `--citekey`, `--collection`, `--collections` |
| `chitragupta corpus topics` | `--topic` |
| `chitragupta corpus discover` | `[PHRASE ...]`, `--paper CITEKEY`, `--json`, `--out FILE`, `--k`, `--html FILE`, `--app DIR`, `--why`, `--groups`, `--compare`, `--hops`, `--clusters`, `--inflation`, `--path`, `--family`, `--origins` |

### ✍ `draft` -- work on one draft

| Command | Subcommands / flags |
| --- | --- |
| `chitragupta draft gate <file>...` | -- (takes no options; this is the hard gate) |
| `chitragupta draft references <file>` | `--heading` |
| `chitragupta draft evidence <file>` | `--format`, `--output-dir` |
| `chitragupta draft render <file>` | `--format`, `--documentclass`, `--fontsize`, `--papersize`, `--margin`, `--csl`, `--output-dir`, `--fragment`, `--no-collapse-citations` |
| `chitragupta draft style <draft>...` | `--language`, `--json` |
| `chitragupta draft retrieve` | `search`, `evidence` |
| `chitragupta draft dossier` | `init`, `status`, `mark-revision`, `apply-renames`, `snapshot`, `versions`, `stamp`, `sections`, `prune`, `outline`, `brief`, `set-language`, `acronyms-suggest`, `check-evidence`, `list`, `export`, `restore` |
| `chitragupta draft spec` | `init`, `show`, `sign`, `status`, `align`, `seed` |
| `chitragupta draft unit` | `contract`, `accept`, `status` |
| `chitragupta draft registry` | `build`, `check`, `excerpt`, `index` |
| `chitragupta draft tldr` | `write`, `show` |
| `chitragupta draft figures` | *(none; takes a citekey)* |
| `chitragupta draft diff <draft>` | `--against`, `--format`, `--json` |

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
| `chitragupta review agenda <draft>` | `--json`, `--formats`, `--accept ID`, `--baseline PATH` |
| `chitragupta review support <draft>` | `--json`, `--write`, `--formats` |
| `chitragupta review union <book>/book.tex` | `--json`, `--write`, `--formats` |
| `chitragupta review digest <draft>` | `--json`, `--formats`, `--baseline PATH` |

### 🧠 `enrich` -- optional, whole-corpus

| Command              | Flags                                                                                                                                                                      |
|----------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `chitragupta enrich` | `--stages docling,embed,bertopic,extract-keywords,seed-topics,converge,topic-graph`, `--for-draft PATH`, `--target host\|docker` (informational only; the probes decide)   |

That is 4 layers and 29 verbs and aids (4 + 13 + 11 + 1), plus 4
package-level commands, giving **67 invocable leaf commands**: 7 + 4 +
(7 + 34) + (10 + 4) + 1. A test pins these counts by walking the live
parsers, so a verb added without a row here fails the suite.

`chitragupta/sync.py` carries a `__main__` block that looks like a fifth
entry point; it is a **tombstone** that refuses with exit 64 and names
the current command (`chitragupta corpus sync`). This page deliberately
does not spell the refused invocation out:
`tests/test_removed_command_scan.py` fails any document that hands a
reader a command that does not work, and decides by path, not context.

---

Everything below is for maintainers: why the surface is shaped and
named as it is, and what a shipped name costs to change.

## 💡 The module form, and why it survives

Every row above has an exact equivalent:

```text
chitragupta <layer> <verb> ...   ==   python -m chitragupta.<layer> <verb> ...
```

Both are supported deliberately; keep both, neither is redundancy to
tidy away. The console script is for humans. The module form is what
`.claude/hooks/` and the genre skills use: a console script lives in one
venv's `bin/`, while the module form resolves from any interpreter that
can import the package. [CLI.md](CLI.md#-which-interpreter) records why
the gate chain must not be blockable by a broken venv, and
`chitragupta/hook_launchers.py` records that a hook launcher that does
not resolve produces *nothing at all*, no error and no log entry.
Routing the citation gate through a `PATH` lookup that can silently miss
would be worse than not packaging at all.

The module form has one cost. `python -m` puts its working directory
first on `sys.path`, and a hook's child runs from the project root; in
an `init`-ed project a committed `chitragupta/` would shadow the
installed package. Three things close it: the hooks run the child with
`PYTHONSAFEPATH=1` in an installed-package project ([HOOKS.md](HOOKS.md)
has how, and the one case it cannot close); `chitragupta init` refuses
a directory that already holds `chitragupta/` or `chitragupta.py`, even
with `--force`; and the prose `init` scaffolds says `python -P -m`,
which keeps the working directory off `sys.path`. That is still the
module form.

## ⚖ What the decision answers

Making this a published package answered a set of objections, three of
which survive.

| The objection | Where it was written | What happened to it |
| --- | --- | --- |
| Needs renaming the `src` layout | `pyproject.toml` header | **Retired by doing it.** A top-level `src` in `site-packages` is unshippable |
| "Don't add a second install path" | `DEVELOPER-AGENTS.md` (git checkout only) | **Survives as an invariant**: one place a dependency fact is written, with two front doors onto it |
| Tier 1 must not be blockable by a broken venv | [CLI.md](CLI.md#-which-interpreter) | **Retired by keeping the module form.** The hooks never move to the console script |
| pip cannot pick a wheel index from the GPU driver | `pyproject.toml`'s torch note | **Survives, reduced.** `pip install …[enrich]` lands CPU-only torch on a CUDA host; `chitragupta doctor` detects it and `chitragupta install gpu-torch` fixes it, neither automatically |
| Command names can be renamed freely | the PR that shipped an early rename | **Survives, sharpened**: see [the last section](#-what-a-shipped-command-name-costs) |
| The deliverable is the docs and skills, not the code | `scripts/release.py`'s docstring | **Retired by `chitragupta init`**, without which a bare wheel would be the wrong shape |
| Everything is anchored to where the *code* lives | `chitragupta/config.py`'s `REPO_ROOT` | **Retired by splitting it** into a discovered project root and a package-data root |

## 🗜 Why the zip ships too

The release archive stays. `scripts/release.py` builds it by a
**denylist**: every git-tracked file ships except a named few.
`chitragupta init` is an **allowlist**: a new root-level file is not
scaffolded unless someone adds it. A test pins the two against each
other, and the deliberate differences (`bench/`, `tests/`, `.github/`,
and CI config that is wrong outside this repository) are one named set
both sides read.

A developer-only skill, such as `demo-recorder` or `skill-bench`, is
left out of the zip, the wheel and the scaffold alike. Poetry cannot
exclude a path inside an `include`d folder, so `pyproject.toml` lists
the harness folders entry by entry;
[HARNESS.md](HARNESS.md#developer-only-skills) has the mechanism.

## ⚡ What a shipped command name costs

Once `chitragupta` is in users' `bin/`, a command name also lives in
shell scripts, Makefiles, CI configs, cron jobs and muscle memory, where
`git grep` cannot reach. A verb rename becomes a MAJOR bump with a
deprecation window, and breaks somebody's setup anyway. The verb
vocabulary is therefore permanent (`chitragupta/draft.py`'s docstring
sets out why `retrieve` rather than `retrieval`).

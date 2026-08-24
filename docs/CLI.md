# ⌨ Command reference

Status: **reference.** Written 2026-08-03. Updated 2026-08-24.

**Written for** anyone running this pipeline, at any level of
familiarity: it is the reference you keep open beside a terminal.
**Assumed:** nothing beyond [README.md](../README.md)'s Quickstart.
**Not covered here:** why any of it is built the way it is.
[ARCHITECTURE.md](ARCHITECTURE.md) has the shape and
[DESIGN.md](DESIGN.md) the constraints. Both are written for someone
changing the code rather than running it.

Every command this repository provides, every flag it accepts, and which
interpreter each one needs. [README.md](../README.md)'s Quickstart is the
short path; this is the full set.

## 🧭 Table of contents

- [Installing](#-installing)
- [Which interpreter](#-which-interpreter)
- [The full first run, step by step](#-the-full-first-run-step-by-step)
- [Every command and flag](#-every-command-and-flag)
  - [`chitragupta corpus sync`](#-chitragupta-corpus-sync)
  - [When `sync` re-parses a document it already parsed](#-when-sync-re-parses-a-document-it-already-parsed)
  - [`chitragupta corpus ledger`](#-chitragupta-corpus-ledger)
  - [`chitragupta corpus topics`](#-chitragupta-corpus-topics)
  - [`chitragupta draft gate`](#-chitragupta-draft-gate)
  - [`chitragupta draft references`](#-chitragupta-draft-references)
  - [`chitragupta draft evidence`](#-chitragupta-draft-evidence)
  - [`chitragupta draft dossier`](#-chitragupta-draft-dossier)
  - [`chitragupta draft retrieve`](#-chitragupta-draft-retrieve)
  - [`chitragupta review coverage`](#-chitragupta-review-coverage)
  - [`chitragupta review figure`](#-chitragupta-review-figure)
  - [`chitragupta review provenance`](#-chitragupta-review-provenance)
  - [`chitragupta review synthesis`](#-chitragupta-review-synthesis)
  - [`chitragupta review uncited`](#-chitragupta-review-uncited)
  - [`chitragupta review verbatim`](#-chitragupta-review-verbatim)
  - [`chitragupta draft render`](#-chitragupta-draft-render)
  - [`chitragupta draft style`](#-chitragupta-draft-style)
  - [`chitragupta draft spec`](#-chitragupta-draft-spec)
  - [`chitragupta draft unit`](#-chitragupta-draft-unit)
  - [`chitragupta draft registry`](#-chitragupta-draft-registry)
  - [`chitragupta draft tldr`](#-chitragupta-draft-tldr)
  - [`chitragupta enrich`](#-chitragupta-enrich)
  - [`scripts/install_full_pipeline.sh`](#-scriptsinstall_full_pipelinesh)
  - [`scripts/release.py`](#-scriptsreleasepy)
- [Running sync on a schedule](#-running-sync-on-a-schedule)
- [Environment variables](#-environment-variables)

## 🔧 Installing

Two paths, both landing in a venv named `.venv-full`, and everything
below this section is identical either way:

```bash
mkdir my-project && cd my-project
python3 -m venv .venv-full && source .venv-full/bin/activate
pip install chitragupta-cli
chitragupta init
```

or, from a git checkout (for working on the pipeline itself --
`DEVELOPER-AGENTS.md`):

```bash
git clone https://github.com/prasadtalasila/chitragupta && cd chitragupta
pipx install poetry
bash scripts/install_full_pipeline.sh all
source .venv-full/bin/activate
```

**Same venv name on purpose, not just a checkout habit carried over.**
`.venv-full` is what keeps a bare `pip install` from hitting Debian/
Ubuntu's PEP 668 `externally-managed-environment` error, and what keeps
Claude Code's hooks -- which launch as bare `python` resolved from
`PATH` ([HOOKS.md](HOOKS.md#-the-launcher-contract)) -- able to import
`chitragupta`, for as long as `.venv-full` stays activated in whatever
shell you launch Claude Code from. Nothing in the installed package
special-cases that name; it's a plain `python3 -m venv` either way, and
the checkout path's own `install_full_pipeline.sh` already creates
`.venv-full` if it doesn't exist and reuses it unchanged if it does
(`poetry.toml`'s `virtualenvs.create = false`).

`chitragupta init DIR` writes the same project directory a checkout
gives you -- `config.toml` from `config.toml.example`, `.claude/`,
`papers/`, `content/{drafts,dossiers,specs,review,rendered}/`, `assets/`
and the prose docs -- so everything from
[step 1](#-the-full-first-run-step-by-step) onward reads the same
regardless of which path got you here.

**The base `pip install chitragupta-cli` above already covers tiers 1
and 2** ([Which interpreter](#-which-interpreter) below) -- everything
except the enrichment layer. `chitragupta install <stage>` refuses
three stage names by pointing at the pip command that actually reaches
them, rather than running something with a different meaning than the
argument implies; run these directly instead of the refused stage, once
`.venv-full` above is activated:

```bash
# chitragupta install python-deps refuses, naming this:
pip install chitragupta-cli[enrich]   # tier 3 -- chitragupta enrich (docling, embeddings, topic clustering)

# chitragupta install dev-deps refuses, naming this. There is no
# pip-installed equivalent of tests/ to run pytest against, though --
# only a checkout ships the test suite itself, so this extra is not
# useful outside one.
pip install chitragupta-cli[dev]

# chitragupta install all refuses, naming pip install chitragupta-cli[enrich]
# (above) plus this, run separately -- os-deps is the one stage that
# actually runs (Debian/Ubuntu + root; `chitragupta doctor` reports what
# it's missing on any other host):
chitragupta install os-deps
```

[PACKAGING.md](PACKAGING.md) has the full command-surface table;
[NAME.md](NAME.md) has why the distribution is `chitragupta-cli` while
the command stays `chitragupta` (`cg` for short).

## ⚖ Which interpreter

Three tiers. Commands below are written with the interpreter they need.

`python` throughout means "your Python 3 interpreter". Nothing here
inspects the name, so `python3` is equally correct if that is what your
machine provides -- on Debian and Ubuntu without `python-is-python3`,
it is the only one. What the tiers distinguish is not the *name* but
**which environment**: a bare interpreter from `PATH` for tier 1,
against the project's venv for tiers 2 and 3.

One place is not free to choose: `.claude/settings.json` launches the hooks
by a name that has to resolve without a human present, and a name that does
not resolve there fails silently. It says `python`, and
[HOOKS.md](HOOKS.md#-the-launcher-contract) records why.

| Tier | Interpreter | Commands |
| --- | --- | --- |
| 1 | **`python`** -- stdlib only, no venv | `chitragupta.draft` (all eleven commands), `chitragupta.corpus ledger`, `chitragupta.corpus topics`, `chitragupta.review` (all six aids) |
| 2 | **`.venv-full/bin/python`** -- venv, for `bibtexparser` | `chitragupta.corpus sync` |
| 3 | **`.venv-full/bin/python`** -- venv with the `enrich` group | `python -m chitragupta.enrich` |

Tier 1 is deliberate, not incidental. The chain that enforces the one
rule -- `chitragupta.draft gate` -> `chitragupta.draft references` ->
`chitragupta.draft render`
-- imports nothing outside the standard library. A broken, missing or
wrong-Python virtual environment therefore cannot block it.
`docs/ARCHITECTURE.md` has the
[full reasoning](ARCHITECTURE.md#-which-interpreter-and-why).

**For a `pip install`ed reader, there is one environment, not three**, and
the tiers collapse to a different distinction: which commands need the
`enrich` extra and which don't. `chitragupta <layer> <verb>` -- the
console script -- reaches every command below exactly as
`python -m chitragupta.<layer> <verb>` does, because both resolve to the
same installed package; the difference tier 1 protects against (a
missing or broken venv) still cannot happen to it. That is *why* the
module form is kept working at all rather than replaced -- the hooks and
every genre skill invoke `python -m chitragupta.draft gate` specifically
because it is the one command that must survive a broken environment,
console script included, and `chitragupta/hook_launchers.py` is what
checks that it still can (#264). So: a bare `pip install chitragupta-cli`
covers tiers 1 and 2 (`bibtexparser` is a main, non-optional dependency
-- `chitragupta corpus sync` needs nothing extra); only tier 3
(`chitragupta enrich`) needs `pip install chitragupta-cli[enrich]`, the
same as `python-deps` needing the enrich group from a checkout.
`chitragupta doctor` reports which you have. Use whichever form you like
by hand, but don't change what a hook or a skill invokes.

Two commands look like they belong in a higher tier and don't:

- `chitragupta.draft render` (`chitragupta/render_output/`) needs only stdlib
  plus
  `chitragupta.config`/`chitragupta.citation_gate`/`chitragupta.references`. It
  shells out to the
  `pandoc`/`pdflatex` binaries, which are OS packages rather than Python
  dependencies.
- `chitragupta.review`'s `coverage` and `verbatim` aids are built on
  `chitragupta.retrieval` and `chitragupta.config`, both stdlib. `verbatim`
  calls the
  `pdftotext` binary, again an OS package.

Using the wrong interpreter is the most likely first error you will hit:
`ModuleNotFoundError: No module named 'bibtexparser'` means you ran
`python -m chitragupta.corpus sync` instead of `.venv-full/bin/python -m
chitragupta.corpus sync`.

## 🚀 The full first run, step by step

Every command this project exposes appears below at least once, in the
order a first run reaches it. Flags are shown only where a first run
would want one -- [Every command and flag](#-every-command-and-flag) is
the exhaustive reference, and each command's own section links from the
table of contents.

Two parts, same sequence, same steps, differing only in which of the two
equivalent forms invokes each command -- see [Which
interpreter](#-which-interpreter) for why both exist and when each one
resolves. Pick whichever you'll actually type; nothing else in this
walkthrough depends on which you use, and the module form works either
way if you switch mid-session.

### ⌨ As the `chitragupta` command

Once the package is installed, with `.venv-full/bin/activate` sourced
either way (see [Installing](#-installing)).

```bash
# 1. Install, and get a project directory -- see Installing above for
#    both paths (pip install + chitragupta init, or a git checkout).
#    Nothing below this step differs by which one you took.

# 2. Export your reference manager's library to BibTeX at
#    papers/bibliography.bib (create papers/ if needed -- it's gitignored,
#    so neither path above populates it). Skipping this makes step 4 fail
#    immediately with a FileNotFoundError telling you to do exactly this.
#    Zotero specifics, including the attachment-path trap that silently
#    leaves every entry without a PDF, are in ZOTERO.md.
mkdir -p papers && cp /path/to/your/exported-library.bib papers/bibliography.bib

# 3. Create your config, if step 1 didn't already: config.toml is
#    gitignored per-host data, so a git checkout has none -- chitragupta
#    init already wrote it from the same template, from an installed
#    package. chitragupta/config.py refuses to import without it (naming
#    this exact command). Every key in it is optional -- see CONFIG.md.
cp config.toml.example config.toml   # git checkout only

# 4. Sync the corpus layer from papers/bibliography.bib. Tier 2: needs the
#    venv, and holds the write lock.
chitragupta corpus sync
# chitragupta corpus sync --reparse         # re-extract text even if the PDF is unchanged
# chitragupta corpus sync --remove-stale    # only after reading the stale list it prints

# 5. Inspect what it found. Read-only, takes no lock (so it works while a
#    sync is running), and needs no venv.
chitragupta corpus ledger
# chitragupta corpus ledger --list
# chitragupta corpus ledger --status parse_failed
# chitragupta corpus ledger --citekey talasila_composable_2025
# chitragupta corpus ledger --collections    # your Zotero collection names, if the export kept them

# 5b. Optional: name the topics you care about, in your own words, in
#     content/seed_topics.toml (start from assets/style/topics.toml.example),
#     match them against the corpus, and read which papers landed under
#     each. A paper can appear under several topics at once; the report
#     also names the papers no topic of yours describes. The matching
#     needs the venv, reading the result does not.
# chitragupta enrich --stages seed-topics
chitragupta corpus topics
# chitragupta corpus topics --topic "digital twin"

# 6. Optional, and only when you want it: the enrichment layer.
#    Layout-aware parsing, semantic search and topic clustering over the
#    whole corpus. Nothing below needs it, and no skill builds it for you
#    -- RETRIEVAL.md says which stage is worth your time. Takes the same
#    write lock as sync.
chitragupta enrich --stages docling,embed
# chitragupta enrich --stages docling --for-draft content/drafts/<slug>.md

# 7. Search the corpus yourself, the same way a skill does. Read-only.
#    `--log` takes the draft whose dossier records the call, so retrieval
#    cost can be totalled later -- omit it for a one-off look.
chitragupta draft retrieve search "digital twin composability" --k 15
chitragupta draft retrieve evidence "calibration" --citekey talasila_composable_2025 \
    --log content/drafts/<slug>.md

# 8. In Claude Code, ask for a draft, e.g.:
#    "write a survey section on digital twin composability"
#    "draft a thesis chapter on runtime verification for autonomous robots"
#    "write a textbook chapter introducing digital twin asset reuse"
#    "write a tutorial that builds a minimal digital twin asset from scratch"
# The matching skill in .claude/skills/ picks this up automatically,
# including its own gate -> references -> render chain (chitragupta draft <verb>),
# and writes a dossier beside the draft as it goes.

# 9. Re-run any step of that chain by hand (no venv needed for these).
#    All three read only under content/ -- a draft kept outside it is
#    refused, so that one directory stays the whole record of the work.
chitragupta draft gate content/drafts/<slug>.md
chitragupta draft references content/drafts/<slug>.md --heading "References"   # --heading default: "References"
chitragupta draft render content/drafts/<slug>.md --format pdf   # also: --csl, --no-collapse-citations,
chitragupta draft render content/drafts/<slug>.md --format tex   #       --documentclass, --fontsize,
chitragupta draft render content/drafts/<slug>.md --format docx  #       --margin (--help for all)
chitragupta draft render content/drafts/<slug>.md --format md    # numbered Markdown copy, no pandoc needed

# 10. Read and maintain the draft's dossier -- what was kept, what was
#    rejected and why, and whether the corpus has moved under it since.
chitragupta draft dossier list
chitragupta draft dossier brief content/drafts/<slug>.md
chitragupta draft dossier sections content/drafts/<slug>.md --citekeys --write
chitragupta draft dossier status --all --json
chitragupta draft dossier export <slug>

# 11. Check the draft against its sources. Review aids, not gates: a skill
#     runs the verbatim scan for you, and none of them can block a draft.
chitragupta review provenance content/drafts/<slug>.md            # what in each source supports the claim citing it
chitragupta review verbatim overlap content/drafts/<slug>.md <citekey>  # wording shared with that one source
chitragupta review verbatim scan content/drafts/<slug>.md        # ...with *any* parsed source, cited or not
chitragupta review verbatim locate <citekey> "a phrase to find"  # which pdf page a phrase is on
chitragupta review coverage content/drafts/<slug>.md --query "digital twin composability"
chitragupta review synthesis content/drafts/<slug>.md            # how many sources each unit rests on
chitragupta review figure content/drafts/<topic>/<slug>.md   # what the TikZ figures' geometry says
chitragupta review uncited content/drafts/<slug>.md              # which sentences carry no citation at all
# add --write to any of these to file the report under content/review/,
# mirroring the draft's path -- printing stays the default
```

Two commands are not part of a first run at all, and are listed here only
so this walkthrough is complete. Both are for working *on* this
repository rather than drafting with it, so only their checkout form
exists -- there is no console-script equivalent of either:

```bash
bash scripts/install_full_pipeline.sh dev-deps   # pytest + pytest-cov, only to run the test suite
python -m pytest                                 # the suite itself

python3 scripts/release.py                       # bundles release/chitragupta-<version>.zip
```

### 🐍 As the module form (`python -m chitragupta.<layer>`)

The exact same eleven steps -- what's below explains nothing a second
time; see the numbered comments above for that. This is what hooks and
skills invoke, and the one form guaranteed to work regardless of how the
package got here (checkout with an active venv, or `pip install`). Steps
1-3 (install, export, config) don't change at all -- reproduced here only
so the numbering matches:

```bash
# 1. Install, and get a project directory -- see Installing above.

# 2. Export your reference manager's library.
mkdir -p papers && cp /path/to/your/exported-library.bib papers/bibliography.bib

# 3. Create your config, if step 1 didn't already.
cp config.toml.example config.toml   # git checkout only

# 4.
python -m chitragupta.corpus sync
# python -m chitragupta.corpus sync --reparse
# python -m chitragupta.corpus sync --remove-stale

# 5.
python -m chitragupta.corpus ledger
# python -m chitragupta.corpus ledger --list
# python -m chitragupta.corpus ledger --status parse_failed
# python -m chitragupta.corpus ledger --citekey talasila_composable_2025

# 6.
python -m chitragupta.enrich --stages docling,embed
# python -m chitragupta.enrich --stages docling --for-draft content/drafts/<slug>.md

# 7.
python -m chitragupta.draft retrieve search "digital twin composability" --k 15
python -m chitragupta.draft retrieve evidence "calibration" --citekey talasila_composable_2025 \
    --log content/drafts/<slug>.md

# 8. (In Claude Code -- the matching skill invokes this form itself.)

# 9.
python -m chitragupta.draft gate content/drafts/<slug>.md
python -m chitragupta.draft references content/drafts/<slug>.md --heading "References"
python -m chitragupta.draft render content/drafts/<slug>.md --format pdf
python -m chitragupta.draft render content/drafts/<slug>.md --format tex
python -m chitragupta.draft render content/drafts/<slug>.md --format docx
python -m chitragupta.draft render content/drafts/<slug>.md --format md

# 10.
python -m chitragupta.draft dossier list
python -m chitragupta.draft dossier brief content/drafts/<slug>.md
python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
python -m chitragupta.draft dossier status --all --json
python -m chitragupta.draft dossier export <slug>

# 11.
python -m chitragupta.review provenance content/drafts/<slug>.md
python -m chitragupta.review verbatim overlap content/drafts/<slug>.md <citekey>
python -m chitragupta.review verbatim scan content/drafts/<slug>.md
python -m chitragupta.review verbatim locate <citekey> "a phrase to find"
python -m chitragupta.review coverage content/drafts/<slug>.md --query "digital twin composability"
python -m chitragupta.review synthesis content/drafts/<slug>.md
python -m chitragupta.review figure content/drafts/<topic>/<slug>.md
python -m chitragupta.review uncited content/drafts/<slug>.md
```

### 📦 Migrating a checkout to `pip install`

Nothing about an existing checkout changes -- this only matters if
you're switching from one path to the other, or explaining the
difference to someone else. Old, on the left, is still there and still
correct; new is what an installed package gives you that a checkout has
no equivalent of, or where a checkout's own equivalent is a script this
package now ships as a runnable command instead.

| Old (git checkout) | New (`pip install chitragupta-cli`) |
| --- | --- |
| `cp config.toml.example config.toml`, then create `.claude/`, `papers/`, `content/` by hand or by cloning | `chitragupta init DIR` -- writes all of it at once (#263) |
| `pipx install poetry && bash scripts/install_full_pipeline.sh all` | `pip install chitragupta-cli[enrich]` |
| `bash scripts/install_full_pipeline.sh os-deps` | `chitragupta install os-deps` -- the same script, reached a different way (#265) |
| `python-deps`'s `ensure_gpu_torch` reinstall step | `chitragupta install gpu-torch` |
| Checking pandoc/pdflatex/vale/the enrich group by hand | `chitragupta doctor` |
| `.venv-full/bin/python -m chitragupta.<layer> <verb>` | `chitragupta <layer> <verb>` -- the module form still works too, and is what hooks and skills keep using ([Which interpreter](#-which-interpreter)) |
| `python scripts/release.py` (build the zip) | Not needed -- `pip install` already gives you the wheel |

## ⌨ Every command and flag

Defaults shown are the value used when the flag is omitted.

**Examples below show the installed package's console script** --
`chitragupta <layer> <verb>`. From a git checkout without the package
installed, `python -m chitragupta.<layer> <verb>` reaches the exact same
command; [Which interpreter](#-which-interpreter) has which form needs
which environment, and why both are kept working on purpose rather than
one replacing the other. Either way, `source .venv-full/bin/activate`
once first (as in [the full first run](#-the-full-first-run-step-by-step))
so the right interpreter is already on `PATH`. Two sections below this
one -- [Running sync on a schedule](#-running-sync-on-a-schedule) and
[Environment variables](#-environment-variables) -- spell out
`.venv-full/bin/python` in full instead, because a cron job or a systemd
unit has no shell to have activated anything in.

### 🔄 `chitragupta corpus sync`

Bibliography -> ledger -> parsed text. **Needs the venv.** Takes the
write lock, so only one run at a time; a second run exits **2** rather
than waiting.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `--reparse` | off | Re-extract every PDF, ignoring the ledger's record of what is already parsed. For when output is recorded as fine but you have reason to doubt it |
| `--remove-stale` | off (report only) | Delete ledger rows for citekeys no longer in the bib file. Without it they are only *reported* |

```bash
chitragupta corpus sync
# chitragupta corpus sync --reparse
# chitragupta corpus sync --remove-stale
# chitragupta corpus sync --reparse --remove-stale

# Exit codes: 0 = clean, 1 = at least one parse failed,
#             2 = another run holds the lock.
```

### ♻ When `sync` re-parses a document it already parsed

A PDF whose bytes haven't changed is not re-parsed -- that is what makes
the second run nearly free. There is one exception, and it is deliberate:
`sync` treats a document it calls `parsed` whose **passage sidecar is
missing** as one that needs parsing again.

That covers two cases. A corpus parsed with `[parser].backend = "docling"`
before this project kept Docling's page breaks and passage records would
otherwise be skipped forever, its PDFs being unchanged; instead the next
run upgrades exactly those documents and nothing else. And a `.txt` or a
sidecar you delete by hand is restored by the same check.

It costs one re-parse each, once (6.65s per PDF serial, 0.62s at twelve
workers -- see [PERFORMANCE.md](PERFORMANCE.md)), and the run reports
them the way it reports any other parse. Nothing to do, in other words --
but `chitragupta corpus sync --reparse` forces it all at once if you
would rather not wait for the next run.

### 🗄 `chitragupta corpus ledger`

Read-only view of the corpus layer. **Takes no lock**, so it works while
a sync is running. With no flags it prints a summary.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `--list` | off | List every item |
| `--status STATUS` | -- | List only items with this status: `parsed`, `no_pdf`, `discovered`, `parse_failed` |
| `--citekey CITEKEY` | -- | Show one item in full |
| `--collections` | off | List every Zotero collection the corpus holds, and stop |
| `--collection NAME` | -- | List only items in this collection, or one beneath it |

```bash
chitragupta corpus ledger
# chitragupta corpus ledger --list
# chitragupta corpus ledger --status parse_failed
# chitragupta corpus ledger --status no_pdf
# chitragupta corpus ledger --citekey talasila_composable_2025
# chitragupta corpus ledger --collections
# chitragupta corpus ledger --collection "Digital twins"
```

Collections need a Better BibTeX export with JabRef fields enabled --
Zotero's own exporter drops them, in which case `--collections` prints
nothing and says why. See
[ZOTERO.md](ZOTERO.md#-keeping-your-collections-optional). Asking for a
parent collection selects everything beneath it, matching is
case-insensitive, and it is per-segment rather than by substring.

### 🏷 `chitragupta corpus topics`

Read-only view of which papers matched each of your seed topics.
**Takes no lock and needs no venv**, though what it reads is written by a
stage that needs both. With no flags it prints every topic.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `--topic PHRASE` | -- | Show only this seed topic's papers |

```bash
chitragupta corpus topics
# chitragupta corpus topics --topic "digital twin"
```

Exits `1` when no report has been written yet, or when `--topic` names a
phrase the report does not hold -- the same "you asked about something
that isn't there" exit `ledger --citekey` already uses.

Seed topics are phrases you write yourself in `content/seed_topics.toml`
(start from `assets/style/topics.toml.example`), matched against the
corpus by `chitragupta enrich --stages seed-topics`. **A phrase
is one topic and is never split into words**, and a paper is listed under
every topic it matched rather than only its closest -- so this report is
many-to-many, unlike `content/topics.json`, where BERTopic gives each
document exactly one topic id. The papers that matched no topic at all
are listed too; that list is the point of the report when you are
deciding what to draft next. See
[CONFIG.md](CONFIG.md#-seed-topics-organising-the-corpus-by-phrases-you-wrote).

### ✅ `chitragupta draft gate`

The hard gate: fails if a draft cites a citekey the ledger doesn't hold.
**Takes no options** -- every argument is a file to check.

| Argument | What it does |
| --- | --- |
| `-h`, `--help` | Show usage and exit 0 |
| `<file> [<file> ...]` | One or more drafts to check |

```bash
chitragupta draft gate content/drafts/survey.md
# chitragupta draft gate content/drafts/*.md      # several at once

# Exit codes: 0 = every citation verified,
#             1 = at least one unresolved citekey, or a file outside content/,
#             2 = no files given.
```

A file that resolves outside `content/` is reported as a `FAIL` for that
document, and the remaining files are still checked. The contract is that
you hand this command several drafts and get a verdict on each, so one
unusable path must not hide the others. It exits 1 rather than the usage
code 2 for the same reason: this is a document that did not pass,
alongside the rest.

**Check the spelling in any script or CI step that runs this.**
`chitragupta/citation_gate.py` carries no `__main__` block -- the drafting layer
has one entry point, and this is it (see
[ARCHITECTURE.md](ARCHITECTURE.md#-which-interpreter-and-why)). So
`python -m chitragupta.citation_gate <draft>` does not error: it imports the
module and exits **0** with empty stdout. For every other command in this
layer that trap is a harmless no-op, but for the gate it means an
automated caller gets a **silent, unconditional pass** on a draft nothing
ever checked. `chitragupta draft` with no arguments prints the layer's
usage and exits 0, which is the fastest way to confirm a spelling.

### 📚 `chitragupta draft references`

Append or replace a `References` section built from a draft's own cited
citekeys.

Entries are IEEE-style and numbered by first appearance in the draft --
the order pandoc's citeproc numbers citations in, so this list and the
rendered PDF's bibliography agree on which source is `[1]`. Each entry
ends with its citekey in a code span, because the draft's own inline
markers are still `[@citekey]`:

```text
[1] J. Doe and R. Roe, "A Paper," *IEEE Trans. Testing*, vol. 3, pp. 1–9, 2024. `doe_paper_2024`
```

Authors, venue, volume and pages come from the ledger's `bib_fields`
column, which `sync` populates from the bib file. A row synced before
that column existed has no fields to format, so its entry degrades to
title and year until the next `chitragupta corpus sync`.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<input>` | required | The draft file (Markdown) |
| `--heading HEADING` | `References` | Heading text, e.g. `"6. References"` to match a draft's own numbered headings |

```bash
chitragupta draft references content/drafts/survey.md
# chitragupta draft references content/drafts/thesis.md --heading "6. References"
```

### 🧾 `chitragupta draft evidence`

Render the **evidence sidecar** beside a draft: each cited source, and
the verbatim spans its dossier marked quotable, grouped by the section
that leans on them.

```text
## Approaches to model synchronisation

### J. Doe and R. Roe, "A Paper," *IEEE Trans. Testing*, 2024. `doe_paper_2024`

> "the verbatim span, exactly as evidence.md's quote: field holds it"
```

It lands beside the render rather than inside the draft:
`content/drafts/dt/survey.md` produces
`content/rendered/dt/survey.evidence.{md,tex,pdf}`, next to
`survey.{md,tex,pdf}`. A sidecar is **never committed** --
`.gitignore` excludes `content/rendered/**/*.evidence.*` even under the
example topic whose renders are otherwise tracked, because a sidecar
carries verbatim wording from copyrighted sources.

Four things it will not do, each of them structural rather than checked:

- **It prints only `quote:`.** Not `claim:`, which is the drafter's own
  words, and above all not a legacy `support:`, which in practice holds a
  raw 600-character retrieval window. A skill meeting a `support:`-only
  block reads it as a quote (see
  [DRAFT-ITERATION.md](DRAFT-ITERATION.md)); a command that *prints* the
  field deliberately does not.
- **It cannot introduce a citekey.** Its universe is the draft's own
  citations, so a source the dossier holds but the draft never cites is
  dropped -- the same rule `references` follows.
- **It adds no citations to anything.** Every citekey it prints sits in a
  code span, which the gate blanks, so
  `chitragupta draft gate` over a sidecar reports
  `0 citations ... OK` and the draft's own `[1]`, `[2]` numbering is
  untouched.
- **It writes nothing when there is nothing to show.** No dossier, or no
  `quote:` anywhere in it, and it prints `no quoted evidence recorded`
  and exits **0**. That is the expected answer for a tutorial, and for
  any dossier still carrying only pre-A2 blocks -- not a failure.

Reading both `[@citekey]` and `\citep{...}`, so a `thesis-chapter-writer`
`.tex` fragment gets a sidecar too. The sidecar is a standalone document
with its own preamble, never something a thesis `\input`s, which is why
that genre emits one rather than declining.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<input>` | required | The draft file (Markdown or LaTeX) |
| `--format FORMAT` | `md` | Output format, passed to `render` for anything but `md`. Exactly one -- a comma-separated list is a usage error (`exit 2`) |
| `--output-dir DIR` | mirrored | Write here instead of `content/rendered/<mirrored path>`; confined to `content/` |

```bash
chitragupta draft evidence content/drafts/dt/survey.md --format pdf
# leaves survey.evidence.md beside survey.evidence.pdf -- the Markdown is
# the sidecar's own source, and the only diffable form of it
```

### 🗂 `chitragupta draft dossier`

The working state behind a draft: create it, inspect it, back it up,
restore it. A dossier lives at `content/dossiers/` plus the draft's path
relative to `content/drafts/`, minus the suffix -- so
`content/drafts/dt/survey.md` gets `content/dossiers/dt/survey/`.

It holds eight Markdown files. `README.md` explains the other seven to
whoever opens the directory next; those seven are:

- `scope.md` -- the reader, the dialect, the scope, the glossary.
- `evidence.md` -- the kept evidence.
- `rejected.md` -- the rejected candidates, and why.
- `sections.md` -- which section cites which citekey.
- `steering.md` -- the user's steering.
- `revisions.md` -- a revision log.
- `retrieval.md` -- every retrieval call, the Zotero collection it was
  scoped to (empty for a corpus-wide call), plus a `mark-revision`
  boundary per revision pass.

[DRAFT-ITERATION.md](DRAFT-ITERATION.md) is the design.

Stdlib only, and never a gate: it takes no lock and only ever opens the
ledger read-only.

Two "missing" cases are deliberately different, because one is actionable
and the other isn't:

| Situation | `status` does |
| --- | --- |
| No ledger, or an unreadable one | Reports the dossier as usual, says the drift check is unavailable, **exits 0** |
| No dossier for this draft | Prints the `init` command to create one, **exits 1** |

So `chitragupta draft dossier status <draft> >/dev/null` is a usable
test for
"does this draft have a dossier yet", while a machine with no corpus built
still gets a full report of what it has.

That test only works without `--json`. Adding it puts the command on the
machine-readable path, which reports a missing dossier as an almost-empty
entry and **exits 0**, like every other `--json` call. That is consistent
with "the caller branches on the contents", but worth knowing if you were
relying on the exit code. Check `recorded` and `draft` in the payload
instead.

`status --all` is the other direction: one drift report over *every*
dossier, for after a `sync` that added or removed papers. It **always
exits 0** -- some drafts having drifted is the normal state of a live
corpus, not a failure -- so a caller branches on the contents, not the
status code. It reports two different things per dossier:

- **missing** -- a citekey the draft cites (`evidence.md` / `sections.md`)
  that has left the ledger, listed with the sections citing it. A defect.
- **candidates** -- papers now in the ledger that one of the dossier's own
  `retrieval.md` queries would surface in its top 15, minus everything
  already kept *or rejected*. A query recorded against a Zotero
  collection is re-ranked over that collection only, matching what the
  call actually searched -- a collection-scoped draft is not reported
  drift against papers outside the shelf it was scoped to. A decision,
  not a defect.
- **reconsider** -- papers the draft already declined that those queries
  still reach, carried with the recorded reason. Not drift (it is true on
  every sweep), so it never marks a dossier stale and prints only
  alongside a real finding; `--json` always carries it.

Like every other read here it takes no lock and writes nothing: the
ledger is opened read-only and the BM25 index used for matching is built
in memory and discarded, leaving `content/retrieval_index.json`
untouched. A sweep costs about 2s cold and 0.2-0.4s warm on this
project's own corpus, and 50 dossiers cost only 0.19s more than one --
see [PERFORMANCE.md](PERFORMANCE.md#-what-a-drift-sweep-costs) and
[DRAFT-ITERATION.md](DRAFT-ITERATION.md#-drift-across-every-dossier).

`brief` is the one subcommand written for a *subagent* rather than a
person. A skill that dispatches parallel section writers has to give each
one its evidence, and pasting that evidence into the dispatch prompt
spends it as output -- the 5x direction, once per writer. `brief` is what
the prompt points at instead: the writer runs it in its own context, and
that context is discarded when it exits. It selects by citekey, or by a
section named in `sections.md`, and refuses to dump the whole of
`evidence.md` -- a caller reaching for it is trying not to read that.
See [DRAFT-ITERATION.md](DRAFT-ITERATION.md#-dispatching-from-the-dossier)
and [TOKENS.md](TOKENS.md).

Its exit code is the contract, because a dispatch prompt cannot read a
paragraph. **0 when it printed at least one block, 1 when it could not
print any.** It prints none in four cases:

- there is no dossier;
- the section is unknown;
- the section's row assigns no citekeys;
- none of the asked-for citekeys was transcribed.

The last three are different gaps, and the message says which.

Everything except the evidence itself goes to stderr, so stdout is only
ever the blocks. A citekey with no block is named in a warning rather
than dropped: the run that found it never transcribed it, so that
material is gone rather than mislaid.

| Subcommand | What it does |
| --- | --- |
| `init <draft> --genre G` | Create the skeleton. Only ever adds missing files -- safe to re-run |
| `status <draft>` | What each file holds, the draft's section count, and whether the corpus moved since |
| `status --all` | Corpus drift over every dossier: broken citations and new candidates. Always exits 0 |
| `sections <draft>` | Heading -> line range, for reading and editing one section instead of the file |
| `sections <draft> --citekeys` | The dossier's `sections.md` table, derived from the draft: each heading with the citekeys cited under it. `--write` puts it in the dossier |
| `mark-revision <draft>` | Record a revision-session boundary in `retrieval.md`, so `status` can total retrieval cost per revision instead of only as one lifetime figure |
| `set-language <draft> <language>` | Record the draft's dialect (a BCP-47 tag: `en-GB`, `en-US`, `en-IN`) in `scope.md`, so `chitragupta.draft style` can check it |
| `acronyms-suggest <draft>` | Acronyms this draft's glossary or prose defines that aren't in `[style].acronyms` yet. Prints only -- writes nothing |
| `acronyms-suggest <draft> --apply` | The same, then writes the new entries to your acronyms file (creating it if absent). Refuses if `[style].acronyms` is unset, rather than writing into the vendored `assets/style/acronyms.toml` |
| `brief <draft> [citekey ...]` | The kept-evidence blocks for a section or a citekey list, for a subagent to read. **Exits 1 if nothing resolves** |
| `check-evidence <draft>` | Advisory: does any `claim:` in `evidence.md` read like its own `quote:` with the words moved? Never blocks a draft from being read -- exits 1 if the target has no dossier yet (same convention as `brief`/`status`), 0 otherwise |
| `list` | Every dossier on this machine |
| `export [<name> ...]` | Bundle drafts + dossiers to a `.tar.gz` |
| `restore <archive>` | Unpack a bundle. **Dry run unless `--force`** |

| Flag | Applies to | What it does |
| --- | --- | --- |
| `--genre GENRE` | `init` | Required: `survey`, `thesis-chapter`, `textbook-chapter`, `tutorial`, `deep-research` |
| `--all` | `status` | Report every dossier instead of one draft. Mutually exclusive with a draft path |
| `--json` | `status` | Emit the drift report as JSON, for `draft-reviser` rather than a terminal |
| `--label TEXT` | `mark-revision` | Short name for this revision. Optional -- an unlabelled marker is numbered by order instead (`revision 1`, `revision 2`, ...) |
| `--citekeys` | `sections` | Print the derived `sections.md` table instead of the outline. A citekey cited above the first heading is reported on stderr, never filed under a section that doesn't contain it |
| `--write` | `sections` | With `--citekeys`: write the table into the dossier's `sections.md`, replacing what is there. Refused without `--citekeys`, and refused when the dossier doesn't exist |
| `--section NAME` | `brief` | Take the citekeys from that `sections.md` row. Matches without the section's numbering; an ambiguous name matches nothing rather than guessing |
| `--check` | `brief` | Report what resolves, and what doesn't, without printing the blocks -- what an orchestrator runs before dispatching |
| `--score` | `check-evidence` | Also print each warning's overlap score. Off by default, so there is nothing to reword against until it drops |
| `--out FILE` | `export` | Archive path (default `drafts-<name>-<date>.tar.gz`) |
| `--with-rendered` | `export` | Include `content/rendered/` too -- large, it holds the PDFs |
| `--force` | `restore` | Actually write, overwriting what is already there |

```bash
chitragupta draft dossier init content/drafts/survey.md --genre survey
chitragupta draft dossier status content/drafts/survey.md
chitragupta draft dossier sections content/drafts/survey.md
# Derive the section -> citekey map instead of writing it by hand
chitragupta draft dossier sections content/drafts/survey.md --citekeys --write

# Before a revision session's first retrieval call
chitragupta draft dossier mark-revision content/drafts/survey.md --label "shorten intro"

# New acronyms this draft's glossary or prose defines; --apply writes them to
# your [style].acronyms file (see docs/CONFIG.md)
chitragupta draft dossier acronyms-suggest content/drafts/survey.md
chitragupta draft dossier acronyms-suggest content/drafts/survey.md --apply

# Before dispatching a section writer: do this section's rows resolve?
chitragupta draft dossier brief content/drafts/survey.md --section "2. Failure modes" --check
# What the writer itself runs
chitragupta draft dossier brief content/drafts/survey.md --section "2. Failure modes"
chitragupta draft dossier brief content/drafts/survey.md talasila_composable_2025

# After writing evidence.md: does any claim: just restate its own quote:?
chitragupta draft dossier check-evidence content/drafts/survey.md

# After a sync: which drafts went stale, and what specifically
chitragupta draft dossier status --all
chitragupta draft dossier status --all --json

# Back up everything, then one topic with its PDFs
chitragupta draft dossier export
chitragupta draft dossier export digital-twins-for-software-engineers --with-rendered

# Restore: look first, then commit to it
chitragupta draft dossier restore drafts-all-2026-08-06.tar.gz
chitragupta draft dossier restore drafts-all-2026-08-06.tar.gz --force
```

A bundle carries `drafts/`, `dossiers/` and optionally `rendered/`, with
paths relative to `content/` so it restores into a checkout whose
`[content].dir` points elsewhere. It does **not** carry
`content/ledger.sqlite` (regenerate with `chitragupta corpus sync`) or
`papers/bibliography.bib` (your reference manager's export, which
AGENTS.md keeps as the source of truth rather than something this
pipeline copies). Restore refuses the whole archive -- rather than
skipping a member -- if any entry is a link or device node, escapes the
extraction directory, or sits outside those three directories.

### 🔎 `chitragupta draft retrieve`

BM25 retrieval over the synced corpus. Read-only, takes no lock, needs no
venv. [RETRIEVAL.md](RETRIEVAL.md) has the ranking details.

| Subcommand | What it does |
| --- | --- |
| `search "<query>"` | Rank the corpus and return a snippet per candidate |
| `evidence "<query>" --citekey KEY` | The passages of that one document that bear on the query (`--windows`, 2 by default) |

`search` also takes `--collection NAME`, which restricts the ranking to a
Zotero collection or one beneath it -- the curated-subset case from #195,
where a chapter on modelling retrieves only from the modelling shelf.
Scoring stays corpus-wide, so a filtered result carries the same score it
would unfiltered; only the candidate set narrows. Needs the export
described in [ZOTERO.md](ZOTERO.md#-keeping-your-collections-optional).
Combined with `--log`, the collection is written to `retrieval.md` too,
so a scoped call and a corpus-wide one no longer write identical rows.

`evidence` is a lookup, not a stage: use it when a `search` snippet is not
enough to judge a source you are minded to cite. Nothing is obliged to
call it. [REJECTION.md](REJECTION.md) explains why an earlier arrangement,
which made a cheap first pass mandatory and used it to *reject*, was
withdrawn.

| Flag | Applies to | Default | What it does |
| --- | --- | --- | --- |
| `--k N` | `search` | 5 | How many candidates to rank |
| `--chars N` | all | 600 / 500 | Window size (evidence / search) |
| `--citekey KEY` | `evidence` | required | Which document to read |
| `--windows N` | `evidence` | 2 | How many passages to return |
| `--log DRAFT` | all | -- | Record the call and its payload size in DRAFT's dossier |

```bash
chitragupta draft retrieve search "digital twin architecture" --k 15 \
    --log content/drafts/survey.md
chitragupta draft retrieve evidence "digital twin architecture" \
    --citekey ferko_architecting_2022 --log content/drafts/survey.md
```

`--log` appends to `retrieval.md` in that draft's dossier, which is what
turns "retrieval is where the tokens go" into a number for a particular
draft (`chitragupta draft dossier status` totals it). A `--log` path that
isn't under `content/drafts/`, or a filesystem error while writing, is
reported on stderr and skipped -- the measurement never fails the search
it was measuring.

Exits 1 with the fix if there is no ledger; an empty result set is not an
error.

### 📐 `chitragupta review figure`

What a draft's TikZ figures' own geometry says about them.
**Informational, not a gate** -- it exits 0 whatever it finds -- and like
the other five aids nothing it reports can block a draft.
[TIKZ-STYLE.md](TIKZ-STYLE.md) is the standard it checks against, and it
reaches only the part of that checklist geometry can decide.

| Check | Kind | Needs `pdflatex` |
| --- | --- | --- |
| Node text over 15 words | binary | no |
| Edge list, reported for confirmation | binary | no |
| Node overlap | binary | yes |
| Content protrusion | binary | yes |
| Emptiness | **continuous, human-read only** | yes |

Two things about that table are deliberate. **Emptiness is reported and
consumed by nothing** -- [AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)'s R3
forbids a continuous score from being what anything unattended optimises,
so it is labelled advisory everywhere it appears rather than left to be
inferred. And the two static checks need no TeX at all, so on a host
without `tikz.sty` this still reports them and says the geometry was
skipped, rather than refusing to run.

**Arrow crossings are not checked**, deliberately: not cheaply reachable
from node geometry, and a bad approximation would be worse than its
absence. That one stays a human judgement.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<draft>` | required | The draft whose figures to check |
| `--json` | off | Print the findings as JSON instead of as text. `--write` files it beside the report either way |
| `--write` | off | Also write the report to `content/review/`, mirroring the draft's path. Printing stays the default |
| `--formats FORMATS` | `md,tex,pdf` | With `--write`, the additional formats to render beside the Markdown report. The `.md` is always written -- it *is* the report |

```bash
chitragupta review figure content/drafts/<topic>/survey.md
# ... --write
# ... --json > figure.json
```

**Read the edge list closely.** It is the one output here that no check
over a rendered picture could produce: in TikZ an edge is
`\draw (a) -- (b);`, so what the figure *claims* connects to what is
recoverable from source. Nothing here knows which edges *should* exist,
which is exactly why confirming them against the prose is the author's
job and not the aid's.

A figure that does not compile is a finding on that figure, not a crash:
the draft's other figures are still checked, and the command still exits
0.

### 📊 `chitragupta review coverage`

How much of what retrieval surfaced actually made it into a draft's
citations. **Informational, not a gate** -- unlike the gate, nothing it
reports can block a draft. Stdlib-only, like `citation_gate` and `references` --
it reuses `chitragupta.retrieval`, which is itself stdlib.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<draft>` | required | The draft to check |
| `--query QUERY` | required, repeatable | A retrieval query to check coverage against. Give it more than once |
| `--k K` | `5` | Top-k results per query |
| `--json` | off | Print the findings as JSON instead of as text (see below). `--write` files it beside the report either way |
| `--write` | off | Also write the report to `content/review/`, mirroring the draft's path. Printing stays the default -- the usual use is a question asked and answered in one sitting |
| `--formats FORMATS` | `md,tex,pdf` | With `--write`, the additional formats to render beside the Markdown report. The `.md` is always written -- it *is* the report -- so `--formats pdf` still produces it. `tex`/`pdf` need `pandoc`/`pdflatex` on `PATH` |

```bash
chitragupta review coverage content/drafts/survey.md \
    --query "digital twin composability" \
    --query "runtime verification"
# ... --k 10
# ... --write --formats md
# ... --json > coverage.json
```

A written report records the whole invocation in its header, queries
included: a coverage figure means nothing without knowing 62% *of what*.

**`--json`** follows the same contract `verbatim scan --json` does (see
below): the envelope every review aid's JSON carries, plus `queries`,
`k`, `coverage_pct`, `candidates_total`, `cited_candidates_total`, and
one `findings` object per citekey the printed report itemises --
`id`, `citekey`, `title` (`null` for a citation outside the candidate
set), and `status` (`uncited_candidates` or `cited_outside_candidates`).
An additional serialisation of what `format_report` already prints,
never a second computation.

### 📖 `chitragupta review provenance`

Reports what in each cited source actually supports the claim citing it,
quoting a real passage. Layer 4, the review layer: advisory, not a gate.

Unlike the other five it writes by default -- reading a provenance report
in a terminal was never the point. The report lands in
`content/review/<topic>/<stem>.provenance.md`, mirroring the draft's path,
with its `.tex`/`.pdf` renders and its `.json` sibling beside it, all
filed whether or not `--json` is given.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<draft>` | required | The Markdown draft to check |
| `--formats FORMATS` | `md,tex,pdf` | Additional formats to render beside the Markdown report. The `.md` is always written -- it *is* the report, and `tex`/`pdf` are renders of it, so `--formats pdf` still produces the `.md`. `tex`/`pdf` need `pandoc`/`pdflatex` on `PATH` |
| `--json` | off | Print the findings as JSON instead of just the written-files summary (see below). The `.json` sibling is filed either way |

```bash
chitragupta review provenance content/drafts/survey.md
# chitragupta review provenance content/drafts/survey.md --formats md
# chitragupta review provenance content/drafts/survey.md --formats md,tex,pdf
# chitragupta review provenance content/drafts/survey.md --json > provenance.json
```

**`--json`** carries the same envelope every review aid's JSON does, plus
one `findings` object per citing sentence, worst-match-first like the
Markdown report -- `id`, `line`, `citekey`, `claim`, `score`, `band`,
`passage` (`page`/`quotable`/`text`, `null` when nothing matched) and
`note` (why a source was unreadable, when one was). An additional
serialisation of what `render_markdown` already prints, never a second
computation. Unlike the other five aids, the `.json` is filed
unconditionally -- matching the `.md`'s own always-write policy -- and
`--json` only decides whether it is *also* printed to stdout, with the
written-files summary moving to stderr in that case.

### 🧩 `chitragupta review synthesis`

How many sources each unit of a draft rests on, **at the unit that
draft's genre binds at**. Prose required to fuse two or more sources
cannot be a transcription of any one of them; this is what makes that
rule observable rather than merely written down. See
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) §11 for the rule itself.
**Advisory, exits 0 whatever it finds**, and it blocks no draft.

The unit comes from the genre recorded in the draft's dossier
`scope.md`, so the usual invocation takes no flags:

| Genre | Unit |
| --- | --- |
| `survey`, `thesis-chapter`, `deep-research` | paragraph |
| `textbook-chapter` | section -- its paragraphs are free to be single-source, its *consecutive* paragraphs are not free to be the same single source |
| `tutorial` | document -- the body carries no citations by design, so the floor is on the lesson's derivation |

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<draft>` | required | The draft to check |
| `--unit {paragraph,section,document}` | from `scope.md` | Measure at this unit instead. For a draft with no dossier, or to look at one deliberately at another scale |
| `--json` | off | Print the findings as JSON instead of as text. `--write` files it beside the report either way |
| `--write` | off | Also write the report to `content/review/`, mirroring the draft's path. Printing stays the default |
| `--formats FORMATS` | `md,tex,pdf` | With `--write`, the additional formats to render beside the Markdown report. `tex`/`pdf` need `pandoc`/`pdflatex` on `PATH` |

```bash
chitragupta review synthesis content/drafts/survey.md
# ... --unit section          # a draft whose dossier records no genre
# ... --write --formats md
# ... --json > synthesis.json
```

Two numbers, because one is not enough. **Spread** is how many distinct
citekeys a unit cites. For a section, the report also gives the
**longest run of consecutive paragraphs resting on the same single
citekey** -- a section citing two papers by running one out before
starting the next spans two sources and fuses neither, and spread alone
cannot tell that apart from a section that interleaves them.

**A thin corpus legitimately produces single-source units.** The report
counts them and does not judge them: there is no threshold here, no
target proportion, and no per-genre bar. A human reads it and nothing
acts on it unattended, which is
[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)'s R3. A unit citing *nothing*
is counted but is never itemised -- original prose is three of the five
genres working correctly.

A single-source unit can be declared deliberate, in the draft, adjacent
to the unit with no blank line between them:

```markdown
<!-- single-source: Foo2019 is the only paper in the corpus covering X -->
```

```latex
% single-source: Foo2019 is the only paper in the corpus covering X
```

The report then counts declared and undeclared separately and lists the
undeclared first. A marker separated from its unit by a blank line
declares nothing -- it becomes a block of its own -- and one inside a
fenced code block is ignored.

**`--json`** carries the envelope every review aid's JSON carries, plus
`genre`, `unit`, `unit_source` (`scope.md`, `--unit` or `nothing`),
`units_total`, `uncited`, `single_source`, `multi_source`, `declared`,
`undeclared`, `single_source_pct`, and one `findings` object per unit
itemised -- `id`, `kind` (`single_source` or `single_key_run`), `line`,
`unit`, `citekeys`, `declared` and `longest_run`.

### 🔍 `chitragupta review uncited`

Which sentences of a draft carry **no citation at all**. This is the
prose-side question, and it is the one nothing answered before:
[`coverage`](#-chitragupta-review-coverage) looks like it
answers this and does not -- it reports which *surfaced candidates* got
cited, which is about the corpus. **Advisory, exits 0 whatever it
finds**, and it blocks no draft. Alone among the six aids it reads
no corpus: no ledger, no sync, no `enrich` extra, only the draft.

**Most of a draft carries no citation, and most of that is fine.** So
the report's real work is what it declines to raise. Two things narrow
it, and both are measured rather than assumed -- see
`plans/c1-uncited-prose-report.md`.

**Structural exclusions.** The reference list, headings, captions, a
table's header row, comment-only blocks (including §11's
`<!-- single-source: ... -->` marker), fenced code, and anything left
empty once its list marker is stripped. Table *rows* are not excluded: a
citekey in backticks is not a citation the gate can see, so a comparison
table that attributes rows that way genuinely rests on nothing.

**The genre decides whether uncited prose is a finding at all.**

| Genre | Uncited prose is | Findings |
| --- | --- | --- |
| `survey`, `thesis-chapter`, `deep-research` | exceptional | one per uncited sentence |
| `textbook-chapter`, `tutorial` | ordinary -- most prose is original by design, per [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §11 | none. The counts are still reported |
| not recorded in `scope.md` | exceptional | raised, and the report says the genre was not recorded |

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<draft>` | required | The draft to check |
| `--genre {deep-research,survey,textbook-chapter,thesis-chapter,tutorial}` | from `scope.md` | Read the draft under this genre instead. For a draft with no dossier, or to read one strictly on purpose |
| `--json` | off | Print the findings as JSON instead of as text. `--write` files it beside the report either way |
| `--write` | off | Also write the report to `content/review/`, mirroring the draft's path. Printing stays the default |
| `--formats FORMATS` | `md,tex,pdf` | With `--write`, the additional formats to render beside the Markdown report. `tex`/`pdf` need `pandoc`/`pdflatex` on `PATH` |

```bash
chitragupta review uncited content/drafts/survey.md
# ... --genre survey          # a draft whose dossier records no genre
# ... --write --formats md
# ... --json > uncited.json
```

**A finding is a sentence, and its block is an attribute, not a
filter.** Each finding carries `block_cites` -- whether anything in the
paragraph it sits in cites a source. A sentence whose paragraph cites
nothing rests on nothing at all and is listed first; one whose paragraph
cites something sits beside evidence that may or may not cover it.
Suppressing the second kind would be simpler and would miss the failure
this aid is for: a paragraph with one citation at the end and four
unrelated assertions before it.

**The fix for an uncited claim is evidence, not wording**, so nothing
repairs these findings for you. Rewording one would make it look
supported without making it supported, which is the failure class this
project exists to prevent -- so unlike a verbatim finding, this is
surfaced and never repaired unattended.

**`--json`** carries the envelope every review aid's JSON carries, plus
`genre`, `genre_source` (`scope.md`, `--genre` or `nothing`),
`standing` (`exceptional` or `ordinary`), `sentences_total`, `uncited`,
`bare`, and one `findings` object per uncited sentence -- `id`, `line`,
`sentence` and `block_cites`.

### 📋 `chitragupta review verbatim`

Layer 4, the review layer, with four subcommands: verbatim overlap
between a draft and one cited source, a whole-draft x whole-corpus scan,
a re-scan compared against a recorded one, and page location for a
phrase. Stdlib-only -- but `locate` shells out to the `pdftotext` binary,
so that subcommand needs poppler-utils on `PATH`. `overlap`, `scan` and
`recheck` read already-parsed text via `chitragupta/overlap_index.py`'s cache
instead. Run with no arguments to print its usage.

[PLAGIARISM.md](PLAGIARISM.md) is the conceptual companion to this
section. It covers what `overlap` and `scan` catch and what they do not,
the severity buckets and the allowlist, and a measured
`docling`-vs-`pdftotext` backend comparison.
[PLAGIARISM-DESIGN.md](PLAGIARISM-DESIGN.md) has the fingerprinting
technique and its literature sources.

| Subcommand | Arguments | What it does |
| --- | --- | --- |
| `overlap` | `<draft> <citekey> [--n N]` | Longest verbatim word-n-gram runs shared between the draft's sentences citing `<citekey>` and that source's parsed text. `--n` defaults to `8` |
| `scan` | `<draft> [--min-run N] [--gap N] [--limit N] [--json] [--write] [--formats F]` | Slides the whole draft across the whole corpus index -- catches verbatim reuse `overlap` structurally cannot: an uncited source, or connective prose that cites nothing. `--min-run` (default `8`, floor is the corpus index's own n-gram size) is the reporting length floor; `--gap` (default `1`) tolerates that many non-matching words inside a run, recovering a lightly-edited near-verbatim lift; `--limit` caps how many findings print (default: all of them). `--json` prints the findings as data instead of as text (see below). `--write` also files the report under `content/review/`, mirroring the draft's path, beside the same draft's provenance and coverage reports; printing stays the default. `--formats` (default `md,tex,pdf`) names the *additional* formats rendered beside the Markdown report -- the `.md` is always written |
| `recheck` | `<draft> --baseline PATH [--json]` | Re-scans the draft and compares it against a payload `scan --write` filed earlier, reporting each finding as resolved, persisting or new plus the change in the objective count. `--baseline` is required and its `--min-run`/`--gap` are reused, so the two scans are comparable. Prints only; there is no `--write` |
| `locate` | `<citekey> "<phrase>" [more...]` | Which PDF page each phrase (or its distinctive words) appears on |

**Exit codes**, shared with the other five review aids. `0` on every
successful invocation, findings or not: these are advisory, never a gate.
That includes `recheck` -- a draft that got worse still exits 0.

`1` is a draft this layer will not read, because it is missing or
resolves outside `content/`. `2` is a malformed invocation, the usual
CLI-usage error rather than a verdict. `recheck` also uses `2` for a
baseline it cannot compare against.

```bash
chitragupta review verbatim overlap content/drafts/survey.md talasila_composable_2025
# chitragupta review verbatim overlap content/drafts/survey.md talasila_composable_2025 --n 12
chitragupta review verbatim scan content/drafts/survey.md
# chitragupta review verbatim scan content/drafts/survey.md --min-run 12 --gap 2 --limit 10
# chitragupta review verbatim scan content/drafts/survey.md --write --formats md
# chitragupta review verbatim scan content/drafts/survey.md --json > findings.json
# chitragupta review verbatim recheck content/drafts/survey.md --baseline content/review/survey.verbatim.json
# chitragupta review verbatim locate talasila_composable_2025 "a digital twin is"
```

**`--json`, and who it is for.** Until 5.4.0 the findings were text and
nothing else. Any programmatic consumer -- a remediation loop, an
eventual overlap gate -- had to regex the printed lines back into data.
`--json` prints the same findings as a payload instead.

The payload carries four things:

- The envelope every review aid's JSON carries: a notice that this is not
  a verdict, the aid, the draft, the exact command, the version.
- The three flags that set the reporting floor: `min_run`, `gap`,
  `limit`.
- How many findings the allowlist suppressed (`suppressed`), and which
  tiers did not run at all and why (`tiers_not_run`). Both are described
  below.
- One object per finding, with `id`, `citekey`, `page`, `end_page`,
  `tier`, `span_words`, `matched_words`, `start`, `line`, `char_start`,
  `char_end`, `draft_text`, `fragment`, `context`, `cites_source`,
  `quoted`, `score` and `severity`.

`severity` is the same `long`/`short`/`quoted` bucket the written report
groups by, so the payload and a human reviewer read the same severity.

The payload serialises what `scan` already computed. It never recomputes,
so it cannot disagree with the two printed forms about what was found. A
clean draft emits `"findings": []` and still exits 0 -- "nothing found"
is data too.

`cites_source: false` is the printed form's `UNCITED SOURCE`, and
`quoted: true` its `quoted`: booleans rather than those labels, because a
caller that has to match display text is back where it started.

`tier` names which detection tier produced the finding -- `exact`,
`skip-gram` or `embedding` (see
[PLAGIARISM-DESIGN.md](PLAGIARISM-DESIGN.md#-where-this-sits-in-a-bigger-plan)).
`score` is the embedding tier's alignment strength, and `null` on the two
deterministic tiers, which have no similarity to report. It ranks within
a section. It is not a probability, and not comparable to anything the
other tiers publish.

`tiers_not_run` is one `{"tier", "reason"}` object per detection tier
that could not run at all, and `[]` when every tier ran. Only the
embedding tier can appear there today. It needs four things: the optional
enrichment layer, a built `content/chroma/`, the Docling passage
sidecars, and the draft's own dossier. A healthy checkout can be missing
any of them.

That is what the field is for. `findings: []` alone cannot distinguish a
draft that was checked and is clean from one a tier never looked at. The
printed and written reports say the same thing in prose.

`page` and `end_page` are the lowest and highest page an n-gram in the
run actually *starts* on (#131). They are equal for an ordinary
single-page run. `end_page > page` means the run spans a source page
break, and the printed forms render that as `p.N-M` rather than picking
one side.

It does not work the other way. A remainder shorter than the index's own
n-gram size has no gram starting on its page, so `scan` recovers it into
the merged run's word content without moving `end_page`. `page` ==
`end_page` therefore does not by itself mean every word in the run sits
on one page.

`start`, `fragment` and `context` describe the **normalised word stream**
-- the draft masked (code and the References section blanked), citation
markers blanked, lowercased, punctuation dropped -- not the draft file
as written. `start` is a word offset into that stream, not a character
offset and not a line number, and `fragment` is those words
space-joined. Those three locate a passage for a *reader*.

`line`, `char_start`, `char_end` and `draft_text` locate it for an
*editor*. They index the draft as written, so
`draft[char_start:char_end] == draft_text` exactly -- which is what makes
`draft_text` usable as an `Edit` `old_string` without searching the file
for the passage and risking the wrong match. `line` is 1-based.

The span covers **every original character between the run's first and
last matched word**, those two words included. That means original
casing, interior punctuation, line breaks, and any citation marker
sitting inside the run.

It ends at the last word rather than at the end of the sentence, so a
trailing period or closing quote falls just outside `char_end`. That is
what you want: a rewrite substituted for `draft_text` should leave the
sentence's own punctuation alone. Leading punctuation is outside the span
for the same reason.

`id` names the finding: a 12-hex-character digest of `(citekey, page,
fragment)`, and deliberately not of its position. An identity built on
`start` would rename every remaining finding the moment the first one was
repaired, so nothing could decide whether a finding had survived a
revision -- which is precisely what `recheck` below has to decide.

Two identical runs from the same source page therefore share an `id`, and
`recheck` understates progress in that case rather than overstating it.

For a run spanning a page break (`end_page > page`, #131), `id` is keyed
on `page`, the lower of the two, where the run starts. If a later scan
merges a run differently -- a wider gap-tolerant run absorbing a
previously-separate one, say -- the merged run's `page` can change, and
with it the `id`. That is the correct read, since a run whose extent
changed really is a different finding to `recheck`. But it means `id`
stability holds across re-runs at the same `--gap`/`--min-run`, not
across every possible one.

`--write` files the payload as `content/review/<topic>/<stem>.verbatim.json`,
beside the Markdown report, whether or not `--json` was also given -- it
is written for whatever reads it later, not for whoever ran the command.
What `--json` prints is byte-for-byte what `--write` files, so redirecting
stdout and reading the sibling give the same bytes, and neither carries a
timestamp: two runs over an unchanged draft and corpus produce identical
payloads. With both flags, the written-files summary goes to stderr so
stdout stays a valid JSON file. `dossier export` carries the payload with
the report.

All six review aids emit one now (#309, #341, #314, #311) -- `provenance` and `coverage`
follow the same envelope, above. [AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)'s
planned `agenda` aid still treats each aid's JSON as optional, though: not
every draft has had every aid run against it, and `coverage`'s sibling is
only ever filed under `--write`.

**`recheck`, and what it is for.** `scan` says what a draft borrows.
`recheck` says what changed since a particular scan. That is the question
anyone repairing those findings actually has: *did that rewrite fix the
finding, and did it break anything else?* Reading two reports side by
side makes that a judgement. It should not be one, so `recheck` makes it
arithmetic.

Given a baseline payload, `recheck` re-scans and reports each finding as
`resolved` (in the baseline, gone now), `persisting` or `new`. It also
reports `objective_before`, `objective_after` and `objective_delta`.

"Objective" means the `long` and `short` buckets. A run that is both
quoted and cited is excluded, because converting a lift into a properly
attributed quotation is one of the two repairs available, and it must not
score as no improvement. A rewrite that resolves its own finding by
lifting from a *different* source shows up as a `new` finding and a delta
that did not fall, which is the case the count exists to catch.

The floor comes from the baseline, not from a flag. Two scans are only
comparable at the same `--min-run`/`--gap`, and the baseline's already
happened; a `--min-run` here would let a strict run be compared against a
lax one and the difference read as progress.

It refuses, with exit 2, a baseline it cannot compare against, always
naming the remedy:

- another aid's payload. The review layer's aids share an envelope, so a
  coverage report is also JSON with a `findings` key, and comparing
  against one would report every verbatim finding as new.
- one written under `--limit`. Truncation happens after sorting, so
  "absent" cannot be distinguished from "cut".
- one missing a field the comparison prints, or otherwise not shaped like
  a findings list. This is the likeliest of the five: a payload filed by
  an earlier version sits at exactly the path a caller is told to look
  at.

  The check names the fields it needs rather than probing for `id` alone.
  `resolved` findings are printed straight out of the baseline and never
  rescanned. So a payload can carry an `id` and still be missing
  something the output line reads, which is exactly what one written
  between `id` and `end_page` landing does.
- one from a **different release series** (`major.minor`). What counts as
  one finding changes between releases -- #131 made a run that used to
  report as two merge into one, giving wording nobody touched a different
  `id` -- so the comparison would report repairs that never happened. A
  *patch* difference is accepted silently, because
  `DEVELOPER-AGENTS.md`'s versioning rules define
  a patch release as changing nothing about what the pipeline does, so a
  finding-shape change cannot land in one.
- one that is unreadable or not JSON.

The last two overlap and neither covers the other: a payload can be the
right shape and mean something different, or claim this series and still
be missing a field.

Refusing rather than warning costs nothing here: `recheck` re-scans
anyway, so if it can run at all then `scan --write` can too, and against
a warm index that is a sub-second re-take. The payload still carries
`baseline_version` as provenance for the comparison it did make.

There is no `--write`. A scan report is kept beside the draft because it
is read again months later; a comparison against one particular baseline
is consumed by whoever asked for it and stale the next time the draft is
touched.

The `overlap-reviser` skill
([GENRE.md](GENRE.md#-repairing-overlap-overlap-reviser)) is the intended
caller: it takes a baseline, repairs findings one at a time, and keeps a
repair only when `recheck` and `chitragupta draft gate` both come back
clean. Nothing obliges you to use it -- `recheck` is as free and as
advisory as every other command here.

**What `scan` does not see, and why that matters more than it sounds.**
`scan` runs all three detection tiers, and each finding names the one
that produced it in `--json` output.

The **exact** tier matches word n-grams, so a single substituted word
breaks it by construction. The **skip-gram** tier (#133) tolerates that,
catching a synonym swap or inflection change. Neither sees genuine
restatement -- the same claim in a different sentence structure. The
**embedding** tier (#134/#164) does, but it runs only where the optional
enrichment layer, the Docling sidecars and the draft's own dossier are
all present, and it compares a section only against the sources that
section already cites.

So the gap has narrowed rather than closed. Read a clean run as "nothing
found by the tiers that ran", never "no borrowed wording found". `scan`
names any tier that did not run, and why, in every form of its output.

Both paraphrase tiers ship advisory-only. Skip-gram's real-corpus
precision **has been measured** (`bench/RESULTS.md`, 2026-08-14): over a
real 15-chapter book, 2 of 27 findings were reuse a reviewer would act
on, and the exact tier already reported both passages. Treat its findings
with *more* scrutiny than the exact tier's, not less.

See [PLAGIARISM.md](PLAGIARISM.md) for how to read them, and
[PLAGIARISM-DESIGN.md](PLAGIARISM-DESIGN.md) for the three-tier design.

**The disk cache, and what the first run costs.** `scan` builds a
corpus-wide index the first time it runs -- `content/overlap/index.bin`
plus an `index.json` header -- merged from the per-document fingerprints
in `content/overlap/docs/<citekey>.fpr`. That first build is the only
slow part -- ~27s over this project's 497-document corpus. Every later
scan over an unchanged corpus reloads the merged index and is sub-second.

The header key covers the n-gram size, the tokenizer version and, per
document, its `pdf_hash` *together with the parsed file's own size and
mtime*. A `sync` that changes one PDF therefore re-fingerprints that one
document and re-merges, rather than rebuilding from scratch.

Both halves of that per-document key earn their place. Re-parsing the
corpus under a different `[parser].backend` rewrites the text without
touching the PDF, and the parsed-file stat is the only part that notices.

The whole directory is a cache, not an output: delete it and the next run
rebuilds whatever it needs.

The skip-gram tier keeps its own pair of files in the same directory --
`skipgram_index.bin`/`.json`, and `docs/<citekey>.skipgram.fpr` -- under
its own tokenizer version, so the two tiers never cross-invalidate.

**5.11.0 bumps that version.** The first `scan` after upgrading therefore
re-fingerprints the corpus for tier 2, at roughly the same cost again as
the tier-1 build above. It is paid once. See
[ARCHITECTURE.md](ARCHITECTURE.md#-what-is-reproducible-and-what-is-not).

`scan` groups a match by its `(citekey, diagonal)`. The diagonal is the
source position minus the draft position, which holds constant across a
run; the source position is global across the whole document rather than
reset per page (#131). `scan` then merges runs on the same diagonal that
sit within `--gap` words of each other.

Two things survive that merge as one finding. A single edited word inside
an otherwise-verbatim passage still reports as one run. So does a genuine
lift spanning a source page break, which used to report as two or more
shorter findings -- and a short remainder stranded on the far side of the
break fell under `--min-run` and vanished entirely.

A finding's `page`/`end_page` name every page an n-gram in the run
actually *starts* on. That is usually the full range, but not always: a
remainder shorter than the index's own n-gram size has no gram starting
on its page, because nothing that short can start one. `scan` recovers it
into the merged run's word content without moving `end_page` to cover it.

Each finding also reports two bits: whether the containing draft
paragraph cites that source (`UNCITED SOURCE` if not), and whether the
run sits inside quote delimiters. Both are informational on stdout.
`--write`'s report goes further and *groups* findings most-damning-first
-- long runs, then short, then quoted -- so a reviewer reads the worst
one first. The underlying findings are the same ones `scan` produces, for
a later gate to be tuned against.

**The allowlist.** `scan` also consults `content/verbatim_allowlist.toml`
if present -- a per-host, gitignored list of acronyms, phrases,
definitions and whole paragraphs its owner has decided are boilerplate,
never a project-tracked file. A finding is dropped only when discounting
its allowlisted words leaves less than `--min-run`; a short allowlisted
phrase sitting inside a much longer, otherwise-unexplained lift is kept.
See [PLAGIARISM.md](PLAGIARISM.md#-the-boilerplate-allowlist) for the file
format and the reasoning.

`locate` reports page numbers by splitting on the form-feed characters
between pages. Both backends emit them, so a page number here is a page
you can turn to whichever one parsed the citekey -- see
[CONFIG.md](CONFIG.md#-backend-pdftotext-or-docling). One limit: `docling`
writes a break between consecutive pages that carry text, so a page with
no extracted items at all shifts the numbering after it. The passage
sidecar records each item's own page and is not affected; where the two
disagree, believe `chitragupta review provenance`.

### 📄 `chitragupta draft render`

Render a Pandoc-Markdown or LaTeX draft. Needs `pandoc` (and `pdflatex`
for PDF) on `PATH`, but no Python package from the enrich group.

Citations render IEEE-style -- `[1]`, and `[3]–[6]` for a consecutive run
-- over a numbered bibliography of complete entries, via the CSL style
vendored at `assets/csl/ieee.csl`. In the copy handed to pandoc, the
draft's own References section -- if `chitragupta draft references`
added one -- keeps its heading, but its entries are replaced by
citeproc's placement anchor. The output therefore carries exactly one
bibliography, citeproc's, which is the one that can be numbered
consistently with the inline markers. It appears under the draft's own
heading, including a numbered heading like `## 6. References`. The draft
file itself is never modified.

**Where the output lands.** `<slug>` may itself contain directories --
`content/drafts/dt-for-engineers/survey.md`, or
`content/drafts/books/software-engineering/chapter.md` -- and every
format is written **beside the draft**, mirroring its path under
`content/drafts/` into `content/rendered/`:

```text
content/drafts/dt-for-engineers/survey.md
   -> content/rendered/dt-for-engineers/survey.{md,tex,pdf,docx}
```

This is the same mirroring rule `content/dossiers/` follows (see
[DRAFT-ITERATION.md](DRAFT-ITERATION.md#-the-dossier)), so one topic
directory names a draft, its dossier and its renders together -- which
is what lets `dossier export <topic> --with-rendered` find them. A flat
`content/drafts/<slug>.md` renders to `content/rendered/<slug>.*`, as it
always has, and an input under `content/` but outside `content/drafts/`
(`content/loose.md`, say) has no path to mirror and lands flat too.

**Both reading and writing are confined to `content/`.** The input must
resolve under the content directory. A draft kept outside it is refused
by name rather than rendered, so that one directory stays the whole
record of the work.

Every path this command *writes* resolves inside `content/` too. Only the
part of a draft's path below `content/drafts/` is ever carried over, and
both sides are resolved before they are compared. No argument -- a `..`,
a symlinked draft -- mirrors anywhere else.

A write could still escape three ways, all configuration or symlinks
rather than arguments. Each is refused with `[error]` rather than
redirected:

- a `content/rendered` that resolves out of the content directory;
- a `content/drafts` that does the same;
- a topic directory under `content/rendered/` that is a symlink pointing
  off-tree.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<input>` | required | The draft file (Markdown or LaTeX) |
| `--format FORMAT` | `pdf` | Output format -- e.g. `pdf`, `tex`, `docx`, `md`. Exactly one -- a comma-separated list is a usage error (`exit 2`), not rendered as several formats. Render each needed format with its own `--format`; a review aid's plural `--formats` is the one that takes a list |
| `--documentclass CLASS` | `article` | LaTeX documentclass |
| `--fontsize SIZE` | `12pt` | LaTeX font size |
| `--papersize SIZE` | `a4` | LaTeX paper size, **without** the `paper` suffix pandoc appends itself -- so `a4`, `letter` |
| `--margin MARGIN` | `1in` | Page margin, passed to the `geometry` package |
| `--csl PATH` | `assets/csl/ieee.csl` | CSL style for citations and the bibliography. A relative path is looked for under the current directory first (like `<input>`), then the project directory, then the shipped assets -- so both your own style and the vendored one are found from anywhere |
| `--no-collapse-citations` | off | Render a run as `[3], [4], [5], [6]` instead of `[3]–[6]`, i.e. leave the style exactly as it is on disk |

`--format md` on a **Markdown** draft is a special case, and the one
output you can read without a PDF viewer. It writes a `.md` beside the
draft's other renders, with the citekeys replaced by the same IEEE
numbers the PDF uses (`[1]`, `[3]–[6]`) over a reference list built from
the ledger.

It needs no `pandoc`, because pandoc's Markdown writer is the wrong tool
for it. That writer escapes every marker -- `\[1\]`, since `[1]` could be
a link reference -- and emits the bibliography as `:::` fenced divs full
of `[...]{.csl-left-margin}` spans. None of that renders anywhere except
pandoc.

The draft itself is never modified: it keeps its `[@citekey]` markers,
which are what `citation_gate` verifies and what `--citeproc` resolves
when rendering. A `.tex` input still goes through pandoc for `md`, since
converting a thesis fragment's `\citep{...}` genuinely is a format
conversion.

```bash
chitragupta draft render content/drafts/survey.md --format pdf
# chitragupta draft render content/drafts/survey.md --format tex
# chitragupta draft render content/drafts/survey.md --format docx
# chitragupta draft render content/drafts/survey.md --format md   # numbered Markdown, no pandoc needed
# chitragupta draft render content/drafts/thesis.md \
#     --documentclass report --fontsize 11pt --papersize letter --margin 1.5in
```

### 🎨 `chitragupta draft style`

Report where a draft's prose departs from
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) -- §2's defect markers, §8's
recorded dialect, and a glossary acronym whose recorded expansion has
drifted from the current `[style].acronyms` vocabulary (§9;
`chitragupta/style_acronym_drift.py`, the one finding here not sourced from
Vale). **A review aid: it exits 0 whatever it finds**, and nothing in
this pipeline reads its output back or blocks on it.

```bash
chitragupta draft style content/drafts/<path>
chitragupta draft style content/drafts/<path> --json
```

It is not a gate and cannot be made one, not even behind a flag. The gate
is measured against the ledger, which is ground truth. This is measured
against a `language:` line someone typed into `scope.md`, which can be
wrong, stale, or deliberately overridden -- so blocking on it would
refuse a correct draft on a bad target. [ARCHITECTURE.md](ARCHITECTURE.md)'s
"Layer 4" has the axis, and DEVELOPER-AGENTS.md bars promoting any new
check into a gate beside the citation gate.

**Which dialect it checks is declared, never inferred.** Three sources,
most specific first, and the report names which one was used:

1. `--language en-GB`, for this run only. Writes nothing.
2. The `language:` line in the dossier's `scope.md` -- the draft's own
   property, settled with the reader when it was drafted.
3. `[style].language` in `config.toml`, a standing preference for this
   machine.

Record a draft's dialect with:

```bash
chitragupta draft dossier set-language content/drafts/<path> en-GB
```

With none of the three set -- the shipped "not settled" placeholder, or
any dossier written before 5.12.0 -- **no dialect rules run**, and the
command measures the draft both ways and proposes one:

```text
dialect: not checked -- no `language:` in scope.md and no [style].language
it reads as en-GB (en-GB: 0, en-US: 13). To record that:
  chitragupta draft dossier set-language content/drafts/<path> en-GB
```

It proposes and never writes: [HOUSE-STYLE.md](HOUSE-STYLE.md)'s rule is
that the machine offers and the human accepts.

**Repeated findings collapse.** A chapter that never expands "AI" reports
it once with a count, not once per occurrence.

Needs the `vale` binary on `PATH`; without it the command reports
missing-binary and changes nothing, the same bargain `render` makes with
pandoc. `bash scripts/install_full_pipeline.sh os-deps` installs the
pinned version. The rules live in `assets/vale/`, vendored rather than
fetched, and `assets/vale/README.md` documents what they deliberately
leave out -- `licence`/`license` and `practice`/`practise` are decided by
part of speech, `program`/`programme` by domain, and no string match
settles any of them.

#### 📕 Assembling a book: `--fragment` and `--output-dir`

```bash
chitragupta draft render content/drafts/<book>/<unit>.md \
    --format tex --fragment --output-dir content/drafts/<book>
```

`--fragment` emits an `\input`-able LaTeX fragment instead of a
standalone document: no preamble, the draft's own top heading becomes a
`\chapter`, and code blocks are left unhighlighted (pandoc's
`Shaded`/`Highlighting` environments are defined only by the standalone
template, so a highlighted fragment fails to compile inside the book).
Citations, the IEEE style and the citekey aliasing are unchanged, so each
fragment carries its own numbered reference list.

`--output-dir` writes the result somewhere other than the mirrored
`content/rendered/` path -- for a book unit, the directory `book.tex`
`\input`s it from. Confined to `content/` like every other path this
command writes. [BOOKS.md](BOOKS.md) is the assembly procedure both exist
for.

### 🎯 `chitragupta draft spec`

The outline a book is generated from, and the human sign-off on it --
the book-scale track's first artefact ([BOOKS.md](BOOKS.md)). Stdlib
only, no venv needed. Writes only under `content/specs/`, mirroring the
book's own directory under `content/drafts/`.

```bash
chitragupta draft spec init content/drafts/<book> --title "<title>"
chitragupta draft spec show content/drafts/<book>
chitragupta draft spec show content/drafts/<book> --unit sec-1
chitragupta draft spec sign content/drafts/<book> --by "<name>"
chitragupta draft spec status content/drafts/<book>
```

| Command | Does | Exit |
| --- | --- | --- |
| `init` | write an outline skeleton (refuses to overwrite one) | 1 if a spec is already there |
| `show` | the outline as a tree, or `--unit <id>` for one unit's slice | 1 on an unknown unit or a spec that does not parse |
| `sign` | record that a human approved this outline, by digest | 1 on a spec that does not parse |
| `status` | what the outline holds, and whether it is signed off | 1 when unsigned or changed since sign-off |

Four heading levels: `#` the book, `##` a part, `###` a chapter, `####` a
section -- and the section is the generation unit. Every part, chapter
and section needs an explicit `{#id}`, because a derived id changes when
someone rewords a heading and orphans the units written against it.

`status`'s exit code is **not a gate**. It reads back a record of a
person's decision -- did a human approve this outline? -- rather than
judging any draft's content, and nothing it says can refuse a write.
[BOOKS.md](BOOKS.md#-what-statuss-exit-code-is-and-is-not) has that
reconciliation against [ARCHITECTURE.md](ARCHITECTURE.md)'s "Layer 4".

### 🧱 `chitragupta draft unit`

One section's generation contract, and the record of its acceptance --
the book-scale track's second artefact ([BOOKS.md](BOOKS.md)). Reads the
outline `spec` owns; writes only `content/specs/<book>/units/<id>.json`.

```bash
chitragupta draft unit contract content/drafts/<book> <unit-id> [--source CITEKEY]...
chitragupta draft unit contract content/drafts/<book> <unit-id> --json
chitragupta draft unit accept   content/drafts/<book> <unit-id> [--source CITEKEY]...
chitragupta draft unit status   content/drafts/<book>
```

| Command | Does | Exit |
| --- | --- | --- |
| `contract` | the inputs one unit is generated from, and their digest | 1 on an unknown unit, a part/chapter, or a spec that does not parse |
| `accept` | record a generated unit, once `chitragupta.draft gate` passes on it | 1 if the outline is unsigned, the draft is missing, or the gate refuses it |
| `status` | where every unit in the book stands | 1 while any unit is not accepted and current |

`--source` is repeatable and is part of the input digest, so grounding a
unit in a different set of papers is a different unit to generate. The
digest covers the inputs only -- never the unit's own prose, which is why
it can answer "does this need regenerating?".

`accept` **invokes the citation gate, it does not replace it**: a unit
the gate refuses cannot be accepted, and nothing here is a second gate.

### 📇 `chitragupta draft registry`

Terminology, claims and cross-references over a book's **accepted** units
([BOOKS.md](BOOKS.md)). Three registries, built by a deterministic pass
and written under `content/specs/<book>/registries/`.

```bash
chitragupta draft registry build   content/drafts/<book>
chitragupta draft registry check   content/drafts/<book>
chitragupta draft registry excerpt content/drafts/<book> <unit-id>
```

| Command | Does | Exit |
| --- | --- | --- |
| `build` | rebuild `terms.md`, `claims.md`, `xrefs.md` from accepted units | 1 only if the book has no readable outline |
| `check` | what the registries disagree on | **always 0** |
| `excerpt` | what one unit's generation should be told the rest of the book settled | 1 only if the book has no readable outline |

**`check` is a review aid and exits 0 whatever it finds**, like the three
`chitragupta.review` aids and unlike `spec status`/`unit status`. Those two report
whether a *human decided* something; this reports a *machine's reading of
prose*, which is judgement however mechanical the arithmetic. There is no
flag that makes it block --
[BOOKS.md](BOOKS.md#-why-registry-check-exits-0-when-the-two-status-commands-do-not)
has the argument, and [ARCHITECTURE.md](ARCHITECTURE.md)'s "Layer 4" the
rule behind it.

Every report says how many units it could read and names the ones it
skipped, because a registry over half a book is a different claim from
one over all of it. Contradiction between claims is **not** detected --
only duplication, which is what a machine can decide.

### 🔭 `chitragupta draft tldr`

A one-paragraph, human-authored summary per citekey, so skimming a large
corpus does not mean opening every PDF. `write` never generates the
summary itself -- it reads one on stdin, from a person or a skill -- and
persists it under `content/tldr/<citekey>.json`, keyed to a fingerprint
of that citekey's current parsed text. `show` recomputes the fingerprint
every time and reports the summary **stale** rather than silently
describing a paper that has since been re-parsed; it never rewrites the
sidecar itself.

```bash
echo "This paper proposes ..." | chitragupta draft tldr write smith2024
chitragupta draft tldr show smith2024
chitragupta draft tldr show smith2024 --json
```

| Command | Does | Exit |
| --- | --- | --- |
| `write <citekey>` | store stdin as `<citekey>`'s summary | 1 if the citekey isn't in the ledger, has no parsed text yet, or stdin is empty |
| `show <citekey> [--json]` | print the summary and whether it's stale | **always 0** -- no summary recorded is not an error |

Never touches `content/ledger.sqlite`: the summary is LLM output, so it
stays in this drafting-layer sidecar rather than the corpus plane, and
`chitragupta corpus ledger` is unchanged.

### 🧠 `chitragupta enrich`

Orchestrates the enrichment layer: docling -> embeddings/Chroma ->
BERTopic -> seed topics -> converge. **Needs the venv.** Each stage probes
its own prerequisites and reports a real per-stage status. A
`skipped/missing-binary` result on a machine without TeX Live is
therefore a correct answer rather than a bug.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `--target {host,docker}` | `host` | **Informational only** -- stages self-probe regardless |
| `--stages STAGES` | all five, or `docling` alone with `--for-draft` | Comma-separated subset of `docling,embed,bertopic,seed-topics,converge` |
| `--for-draft PATH` | -- | Scope `docling` to the papers this draft cites. Refused with an explicit `--stages embed`, `bertopic`, `seed-topics` or `converge` |

```bash
chitragupta enrich
# chitragupta enrich --stages docling
# chitragupta enrich --stages embed,bertopic
# chitragupta enrich --stages seed-topics   # skipped with no content/seed_topics.toml
# chitragupta enrich --for-draft content/drafts/digital-twins.md

# A review report and a draft render are tier-1 commands, not stages --
# no venv, no lock:
# chitragupta review provenance content/drafts/survey.md
# chitragupta draft render content/drafts/survey.md --format pdf
```

#### 📚 Enriching one draft's papers

By default the unit of work is the corpus: every ledger item, whether a
draft cites it or not. `--for-draft` narrows that to the papers one draft
cites. It reads them out of the draft with the same reader the citation
gate uses, `chitragupta.citation_gate.extract_citekeys`. A draft resting on
twenty-three papers therefore costs twenty-three parses rather than the
whole library:

```console
$ chitragupta enrich --for-draft content/drafts/digital-twins.md
Target: host
Corpus: 23 of 642 doc(s) from papers/bibliography.bib -- scoped to content/drafts/digital-twins.md

=== docling ===
[ok] {
  "ali_modeling_2024": "ok: content/docling/ali_modeling_2024.md",
  ...
}

=== Summary ===
  docling    ok
```

With no `--stages` of its own it runs `docling` alone -- the stage the
scope actually reaches, and the one that produces the quotable passages
this is usually for. To carry on into the draft's own review report, run
`chitragupta review provenance <draft>` afterwards: it is a tier-1
command, so it needs no venv and waits on no lock.

Two stages refuse the scope rather than honouring it:

```console
$ chitragupta enrich --for-draft content/drafts/digital-twins.md --stages embed
  --for-draft cannot scope embed: it builds one whole-corpus artefact, and a partial one is indistinguishable from a complete one. Run them as separate commands:
      chitragupta enrich --for-draft content/drafts/digital-twins.md --stages docling
      chitragupta enrich --stages embed
```

That is a tier, not a ladder ([LADDERS.md](LADDERS.md)). `embed` writes a
Chroma collection carrying no record of how much of the corpus it covers.
Every skill that reads it decides by asking only whether
`content/chroma/` exists, so a collection holding eleven papers would
answer as though it held 642. `bertopic` overwrites `content/topics.json`
whole, so a scoped run would replace a corpus-wide topic model with an
eleven-document one. Neither is worth a silently smaller answer, so the
run stops and names the command to use instead (exit status 3).

A citekey the draft cites and the ledger has never heard of is named, not
quietly dropped. A scope matching nothing at all stops rather than
reporting `ok` over zero documents.

The Docling cache is per-document and never rewritten to match the scope,
so a scoped run and a full run do no duplicate work in either order.
Narrow first and widen later, or the reverse: nothing is parsed twice.

The `embed` stage names each document as it reaches it, so a run over a
real corpus is legible rather than silent for its whole duration:

```text
=== embed ===
  [1/646] abbiati_modelling_2024 -- embedded, 92 chunk(s)
  [2/646] abduvakhobov_scalable_2024 -- unchanged, 65 chunk(s)
  [3/646] adhikari_digital_2023 -- no text to embed
  ...
  646 document(s): 102 embedded, 399 unchanged, 145 with no text -- 32033 chunk(s) in the index
```

`unchanged` is the incremental skip (same text as last run, not
re-encoded); `no text to embed` is a bib entry with no parsed text behind
it, which stays searchable by title through `chitragupta/retrieval.py` and not by
meaning. Ctrl+C is safe: every chunk upserted before the interrupt is
already in `content/chroma/`, the stage says how far it got, and re-running
picks up from there.

### 🔧 `scripts/install_full_pipeline.sh`

One install path for both a bare machine and the Docker image. Takes
**stage names as positional arguments**, not flags.

| Stage | What it does |
| --- | --- |
| `python-deps` | **Default when no stage is given.** Creates the venv and runs `poetry install --with enrich`. `chitragupta install` refuses this by name; the pip equivalent is `pip install chitragupta-cli[enrich]` (#265) |
| `os-deps` | `apt-get` the system packages (TeX Live, Pandoc, poppler-utils, Poetry, git/curl/unzip, and OpenCV's runtime libraries -- see [PDF-PARSER.md](PDF-PARSER.md#-docling-fails-every-document-with-an-opencv-recursion-error)). Needs root; auto-sudo's. Opt-in -- not everyone wants a script touching apt. Also reachable as `chitragupta install os-deps` (#265), unmodified |
| `dev-deps` | `poetry install --with dev` (pytest, pytest-cov) into the same venv. Needed only to run the test suite. Run `python-deps` first. `chitragupta install` refuses this by name; the pip equivalent is `pip install chitragupta-cli[dev]` |
| `cpu-torch` | Swaps torch to the CPU-only wheel index and removes the CUDA runtime the default wheel pulled in. Opt-in and never part of `all` -- it asserts a GPU is absent *for good* (a hosted CI runner, a CPU-only container), which the script cannot infer about a host that might grow one later |
| `gpu-torch` | Reaches `ensure_gpu_torch` (below) directly, pointed at `CHITRAGUPTA_PIP`/`CHITRAGUPTA_PYTHON` rather than this script's own venv -- what `chitragupta install gpu-torch` (#265) reaches for someone who pip-installed rather than cloned. Not part of `all` or `python-deps`, which already call `ensure_gpu_torch` against their own venv |
| `vale` | Installs Vale alone, without the TeX Live and poppler `os-deps` also brings -- what CI's `lint` job and a bare `python-deps` run (which needs no `poetry`) both want |
| `all` | `os-deps` + `python-deps`. **Does not include `dev-deps`** |

```bash
bash scripts/install_full_pipeline.sh              # = python-deps
# bash scripts/install_full_pipeline.sh all
# bash scripts/install_full_pipeline.sh os-deps
# bash scripts/install_full_pipeline.sh dev-deps
# bash scripts/install_full_pipeline.sh os-deps python-deps dev-deps

# SKIP_VENV=1 installs into the active environment instead of creating
# .venv-full/ -- what docker/Dockerfile uses for its own /opt/venv.
# SKIP_VENV=1 bash scripts/install_full_pipeline.sh python-deps
```

`python-deps` and `dev-deps` also run `ensure_gpu_torch`, which detects
the NVIDIA driver's supported CUDA ceiling and reinstalls torch from a
matching wheel index if the default one would silently run CPU-only. It
is idempotent and safe to re-run, and prints what it decided -- `torch
already sees the GPU (driver supports its bundled CUDA build)` when no
reinstall was needed.

**Poetry is a prerequisite, not something `python-deps` installs.** It is
in the `os-deps` package list, so `all` covers it; if you run
`python-deps` on its own, install Poetry first (`pipx install poetry`).
Each stage ends by printing the exact interpreter path to use afterwards,
which is `.venv-full/bin/python` on a normal host.

### 📦 `scripts/release.py`

Builds the release archive under `release/`. A maintainer tool.

**Takes no arguments and parses none** -- including `-h`/`--help`, which
it ignores while building the archive anyway. Run it bare:

```bash
python3 scripts/release.py
```

`tests/`, `bench/`, `.github/` and `.gitignore` are excluded from the
archive. Every prose document ships: `docs/`, `README.md`, `SOUL.md`,
`AGENTS.md`, `DEVELOPER-AGENTS.md` and `DEVELOPER.md`, plus `.claude/`.

## ⏰ Running sync on a schedule

`python -m chitragupta.corpus sync` is deterministic, idempotent, and takes its
own write lock (`chitragupta.runlock`), so it was already safe to run unattended.
Two other things make it worth *actually* putting on a schedule: exit
codes an unattended caller can branch on without parsing any text, and
`logs/pipeline.log` as a persistent transcript to check afterwards. That
log is rotated -- see `[logging]` in `config.toml.example`.

`chitragupta/enrich/__main__.py` writes to the same file, so a host that schedules
both has one transcript rather than two. Each line names its source in
`%(name)s` -- the module, so `sync` logs as `chitragupta.sync` whatever the
command that started it is spelled -- and either layer can be narrowed
back out:

```bash
grep 'src\.sync' logs/pipeline.log      # just the corpus layer
grep 'src\.enrich' logs/pipeline.log    # just the enrichment layer
```

The interleaved view is often the useful one, though, since the
enrichment layer's docling stage reuses whatever the corpus layer
already parsed.

**Don't hand-roll a log redirect for most of this.** `logs/pipeline.log`
carries almost every warning, per-document progress line, and the run
summary, at the level `[logging].level` sets. A cron or systemd wrapper
around these commands does not need its own `>> some.log 2>&1` to get a
durable record of those. Three messages stay terminal-only by
design. A docling worker's GPU-OOM fallback runs in a child process with
no route back to the file. The Ctrl+C interrupt notice runs in a signal
handler, deliberately kept to a bare `print`. The "another run already
holds the lock" refusal comes from the losing side of a race, which must
not touch a file the winner is writing. All three are rare
and none is the kind of thing a schedule needs to recover from
unattended.

**Exit codes are the API**, not the printed text:

| Exit code | Meaning | What an unattended caller should do |
| --- | --- | --- |
| `0` | Clean -- everything that needed parsing, parsed | Nothing |
| `1` | At least one document failed, or a prior deterministic failure is still unresolved | Alert; `logs/pipeline.log`'s FAILED/WARNING lines name which citekey and why |
| `2` | Another run already holds the write lock | Nothing -- expected under any schedule tight enough to overlap a slow run. The skipped cycle costs nothing; the next one picks up whatever this one would have |

**A schedule written before 5.2.0 now fails instead of lying.** That
release moved this command behind `python -m chitragupta.corpus sync` and left
the old spelling importing a module and exiting **0**. An unedited
crontab therefore kept reporting success while syncing nothing, for a
release.

It now prints the line above and exits **64**, deliberately none of the
three codes in the table: a caller that reads `2` as "expected, do
nothing" must not read this as that. If a schedule of yours starts
failing after upgrading, the message names the replacement. That is the
whole fix.

### 🕰 cron

```bash
# crontab -e -- runs hourly, on the hour. cd into the repo first: sync
# resolves config.toml and papers/bibliography.bib relative to it.
0 * * * * cd /path/to/chitragupta && .venv-full/bin/python -m chitragupta.corpus sync
```

cron's own default, with no `MAILTO` set, is to mail stdout/stderr to
the crontab's owner -- which needs a working local MTA to go anywhere,
and most hosts don't have one configured. `logs/pipeline.log` doesn't depend
on any of that: it's a plain file, written every run regardless of mail
setup.

### 🐧 systemd (service + timer)

Two unit files, not one -- systemd's usual split between "what" and
"when":

```ini
# /etc/systemd/system/chitragupta-sync.service
[Unit]
Description=Chitragupta corpus sync

[Service]
Type=oneshot
WorkingDirectory=/path/to/chitragupta
ExecStart=/path/to/chitragupta/.venv-full/bin/python -m chitragupta.corpus sync
# Exit 2 (another run still holds the lock) is an expected, harmless
# outcome under this schedule, not a service failure -- don't let
# systemd treat it as one.
SuccessExitStatus=2
```

```ini
# /etc/systemd/system/chitragupta-sync.timer
[Unit]
Description=Run chitragupta-sync.service hourly

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now chitragupta-sync.timer
journalctl -u chitragupta-sync.service   # systemd's own transcript,
                                          # alongside logs/pipeline.log
```

Both assume a host where `.venv-full/` is already built (see
[`scripts/install_full_pipeline.sh`](#-scriptsinstall_full_pipelinesh)
above) -- scheduling only runs what's already installed, it doesn't
install anything itself.

## ⚙ Environment variables

Every `config.toml` setting has a matching environment variable that
overrides it for one run. The full list, with accepted values, is in
[CONFIG.md](CONFIG.md#-every-setting). The ones that most often appear on
a command line:

```bash
# Point at a different bibliography or output directory for one run
# BIB_FILE=/path/to/other.bib .venv-full/bin/python -m chitragupta.corpus sync
# CONTENT_DIR=/tmp/scratch-content .venv-full/bin/python -m chitragupta.corpus sync

# Keep config.toml somewhere else entirely
# CONFIG_PATH=/etc/research/config.toml .venv-full/bin/python -m chitragupta.corpus sync

# Try the higher-fidelity parser with some parallelism, without editing the file
# PARSER=docling PARSER_WORKERS=auto .venv-full/bin/python -m chitragupta.corpus sync

# Confine a docling run to one GPU (no config setting for this, by design)
# CUDA_VISIBLE_DEVICES=0 .venv-full/bin/python -m chitragupta.corpus sync
```

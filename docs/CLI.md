# Command reference

Status: **reference.** Written 2026-08-03.

Every command this repository provides, every flag it accepts, and which
interpreter each one needs. [README.md](../README.md)'s Quickstart is the
short path; this is the full set.

## Table of contents

- [Which interpreter](#which-interpreter)
- [The full first run, step by step](#the-full-first-run-step-by-step)
- [Every command and flag](#every-command-and-flag)
  - [`src.corpus sync`](#python--m-srccorpus-sync)
  - [When `sync` re-parses a document it already parsed](#when-sync-re-parses-a-document-it-already-parsed)
  - [`src.corpus ledger`](#python--m-srccorpus-ledger)
  - [`src.draft gate`](#python--m-srcdraft-gate)
  - [`src.draft references`](#python--m-srcdraft-references)
  - [`src.draft dossier`](#python--m-srcdraft-dossier)
  - [`src.draft retrieve`](#python--m-srcdraft-retrieve)
  - [`src.review coverage`](#python--m-srcreview-coverage)
  - [`src.review provenance`](#python--m-srcreview-provenance)
  - [`src.review verbatim`](#python--m-srcreview-verbatim)
  - [`src.draft render`](#python--m-srcdraft-render)
  - [`src.enrich`](#python--m-srcenrich)
  - [`scripts/install_full_pipeline.sh`](#scriptsinstall_full_pipelinesh)
  - [`scripts/release.py`](#scriptsreleasepy)
- [Running sync on a schedule](#running-sync-on-a-schedule)
- [Environment variables](#environment-variables)

## Which interpreter

Three tiers. Commands below are written with the interpreter they need.

`python` throughout means "your Python 3 interpreter". Nothing here
inspects the name, so `python3` is equally correct if that is what your
machine provides -- on Debian and Ubuntu without `python-is-python3`,
it is the only one. What the tiers distinguish is not the *name* but
**which environment**: a bare interpreter from `PATH` for tier 1,
against the project's venv for tiers 2 and 3.

| Tier | Interpreter | Commands |
|---|---|---|
| 1 | **`python`** -- stdlib only, no venv | `src.draft` (all five commands), `src.corpus ledger`, `src.review` (all three aids) |
| 2 | **`.venv-full/bin/python`** -- venv, for `bibtexparser` | `src.corpus sync` |
| 3 | **`.venv-full/bin/python`** -- venv with the `enrich` group | `python -m src.enrich` |

Tier 1 is deliberate, not incidental. The chain that enforces the one rule
-- `src.draft gate` -> `src.draft references` -> `src.draft render` --
imports nothing outside the standard library, so it cannot be blocked by
a virtual environment that is broken, missing, or built for a different
Python. `docs/ARCHITECTURE.md` has the [full
reasoning](ARCHITECTURE.md#which-interpreter-and-why).

Two commands look like they belong in a higher tier and don't:

- `src.draft render` (`src/render_output.py`) needs only stdlib plus
  `src.config`/`src.citation_gate`/`src.references`. It shells out to the
  `pandoc`/`pdflatex` binaries, which are OS packages rather than Python
  dependencies.
- `src.review`'s `coverage` and `verbatim` aids are built on
  `src.retrieval` and `src.config`, both stdlib. `verbatim` calls the
  `pdftotext` binary, again an OS package.

Using the wrong interpreter is the most likely first error you will hit:
`ModuleNotFoundError: No module named 'bibtexparser'` means you ran
`python -m src.corpus sync` instead of `.venv-full/bin/python -m src.corpus sync`.

## The full first run, step by step

Every command this project exposes appears below at least once, in the
order a first run reaches it. Flags are shown only where a first run
would want one -- [Every command and flag](#every-command-and-flag) is
the exhaustive reference, and each command's own section links from the
table of contents.

```bash
# 1. Export your reference manager's library to BibTeX at
#    papers/bibliography.bib (create papers/ if needed -- it's gitignored,
#    so a fresh clone never has it). Skipping this makes step 3 fail
#    immediately with a FileNotFoundError telling you to do exactly this.
#    Zotero specifics, including the attachment-path trap that silently
#    leaves every entry without a PDF, are in ZOTERO.md.
mkdir -p papers && cp /path/to/your/exported-library.bib papers/bibliography.bib

# 1b. Create your config from the tracked example. config.toml is
#     gitignored per-host data, so a fresh clone has none, and
#     src/config.py refuses to import without it (naming this exact
#     command). Every key in it is optional -- see CONFIG.md.
cp config.toml.example config.toml

# 2. Install. scripts/install_full_pipeline.sh is the only install path;
#    it takes stage names as positional arguments (see its own section
#    below for the full table). Poetry must exist before python-deps
#    runs -- install it yourself, or let the os-deps stage do it.
pipx install poetry
bash scripts/install_full_pipeline.sh os-deps      # root; pdftotext, Pandoc, TeX Live
bash scripts/install_full_pipeline.sh python-deps  # .venv-full/ + the enrich group

# `all` is os-deps + python-deps in one call, and deliberately excludes
# dev-deps (which only the test suite needs -- see the last block below):
# bash scripts/install_full_pipeline.sh all

# 3. Sync the corpus layer from papers/bibliography.bib. Tier 2: needs the
#    venv, and holds the write lock.
.venv-full/bin/python -m src.corpus sync
# .venv-full/bin/python -m src.corpus sync --reparse         # re-extract text even if the PDF is unchanged
# .venv-full/bin/python -m src.corpus sync --remove-stale    # only after reading the stale list it prints

# 4. Inspect what it found. Read-only, takes no lock (so it works while a
#    sync is running), and needs no venv.
python -m src.corpus ledger
# python -m src.corpus ledger --list
# python -m src.corpus ledger --status parse_failed
# python -m src.corpus ledger --citekey talasila_composable_2025

# 5. Optional, and only when you want it: the enrichment layer.
#    Layout-aware parsing, semantic search and topic clustering over the
#    whole corpus. Nothing below needs it, and no skill builds it for you
#    -- RETRIEVAL.md says which stage is worth your time. Takes the same
#    write lock as sync.
.venv-full/bin/python -m src.enrich --stages docling,embed
# .venv-full/bin/python -m src.enrich --stages docling --for-draft content/drafts/<slug>.md

# 6. Search the corpus yourself, the same way a skill does. Read-only.
#    `--log` takes the draft whose dossier records the call, so retrieval
#    cost can be totalled later -- omit it for a one-off look.
python -m src.draft retrieve search "digital twin composability" --k 15
python -m src.draft retrieve evidence "calibration" --citekey talasila_composable_2025 \
    --log content/drafts/<slug>.md

# 7. In Claude Code, ask for a draft, e.g.:
#    "write a survey section on digital twin composability"
#    "draft a thesis chapter on runtime verification for autonomous robots"
#    "write a textbook chapter introducing digital twin asset reuse"
#    "write a tutorial that builds a minimal digital twin asset from scratch"
# The matching skill in .claude/skills/ picks this up automatically,
# including its own gate -> references -> render chain (python -m src.draft <verb>),
# and writes a dossier beside the draft as it goes.

# 8. Re-run any step of that chain by hand (no venv needed for these).
#    All three read only under content/ -- a draft kept outside it is
#    refused, so that one directory stays the whole record of the work.
python -m src.draft gate content/drafts/<slug>.md
python -m src.draft references content/drafts/<slug>.md --heading "References"   # --heading default: "References"
python -m src.draft render content/drafts/<slug>.md --format pdf   # also: --csl, --no-collapse-citations,
python -m src.draft render content/drafts/<slug>.md --format tex   #       --documentclass, --fontsize,
python -m src.draft render content/drafts/<slug>.md --format docx  #       --margin (--help for all)
python -m src.draft render content/drafts/<slug>.md --format md    # numbered Markdown copy, no pandoc needed

# 9. Read and maintain the draft's dossier -- what was kept, what was
#    rejected and why, and whether the corpus has moved under it since.
python -m src.draft dossier list
python -m src.draft dossier brief content/drafts/<slug>.md
python -m src.draft dossier sections content/drafts/<slug>.md --citekeys --write
python -m src.draft dossier status --all --json
python -m src.draft dossier export <slug>

# 10. Check the draft against its sources. Review aids, not gates: none of
#     these runs automatically, and none of them can block a draft.
python -m src.review provenance content/drafts/<slug>.md            # what in each source supports the claim citing it
python -m src.review verbatim overlap content/drafts/<slug>.md <citekey>  # wording shared with that one source
python -m src.review verbatim scan content/drafts/<slug>.md        # ...with *any* parsed source, cited or not
python -m src.review verbatim locate <citekey> "a phrase to find"  # which pdf page a phrase is on
python -m src.review coverage content/drafts/<slug>.md --query "digital twin composability"
# add --write to any of the three to file the report under content/review/,
# mirroring the draft's path -- printing stays the default
```

Two commands are not part of a first run at all, and are listed here only
so this walkthrough is complete. Both are for working *on* this
repository rather than drafting with it:

```bash
bash scripts/install_full_pipeline.sh dev-deps   # pytest + pytest-cov, only to run the test suite
.venv-full/bin/python -m pytest                  # the suite itself

python scripts/release.py                       # bundles release/chitragupta-<version>.zip
```

## Every command and flag

Defaults shown are the value used when the flag is omitted.

### `python -m src.corpus sync`

Bibliography -> ledger -> parsed text. **Needs the venv.** Takes the
write lock, so only one run at a time; a second run exits **2** rather
than waiting.

| Flag | Default | What it does |
|---|---|---|
| `-h`, `--help` | -- | Show help and exit |
| `--reparse` | off | Re-extract every PDF, ignoring the ledger's record of what is already parsed. For when output is recorded as fine but you have reason to doubt it |
| `--remove-stale` | off (report only) | Delete ledger rows for citekeys no longer in the bib file. Without it they are only *reported* |

```bash
.venv-full/bin/python -m src.corpus sync
# .venv-full/bin/python -m src.corpus sync --reparse
# .venv-full/bin/python -m src.corpus sync --remove-stale
# .venv-full/bin/python -m src.corpus sync --reparse --remove-stale

# Exit codes: 0 = clean, 1 = at least one parse failed,
#             2 = another run holds the lock.
```

### When `sync` re-parses a document it already parsed

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
but `python -m src.corpus sync --reparse` forces it all at once if you
would rather not wait for the next run.

### `python -m src.corpus ledger`

Read-only view of the corpus layer. **Takes no lock**, so it works while
a sync is running. With no flags it prints a summary.

| Flag | Default | What it does |
|---|---|---|
| `-h`, `--help` | -- | Show help and exit |
| `--list` | off | List every item |
| `--status STATUS` | -- | List only items with this status: `parsed`, `no_pdf`, `discovered`, `parse_failed` |
| `--citekey CITEKEY` | -- | Show one item in full |

```bash
python -m src.corpus ledger
# python -m src.corpus ledger --list
# python -m src.corpus ledger --status parse_failed
# python -m src.corpus ledger --status no_pdf
# python -m src.corpus ledger --citekey talasila_composable_2025
```

### `python -m src.draft gate`

The hard gate: fails if a draft cites a citekey the ledger doesn't hold.
**Takes no options** -- every argument is a file to check.

| Argument | What it does |
|---|---|
| `-h`, `--help` | Show usage and exit 0 |
| `<file> [<file> ...]` | One or more drafts to check |

```bash
python -m src.draft gate content/drafts/survey.md
# python -m src.draft gate content/drafts/*.md      # several at once

# Exit codes: 0 = every citation verified,
#             1 = at least one unresolved citekey, or a file outside content/,
#             2 = no files given.
```

A file that resolves outside `content/` is reported as a `FAIL` for that
document and the remaining files are still checked -- this command's
contract is that you hand it several drafts and get a verdict on each, so
one unusable path must not hide the others. It exits 1 rather than the
usage code 2 for the same reason: it is a document that did not pass,
alongside the rest.

**Check the spelling in any script or CI step that runs this.**
`src/citation_gate.py` carries no `__main__` block -- the drafting layer
has one entry point, and this is it (see
[ARCHITECTURE.md](ARCHITECTURE.md#which-interpreter-and-why)). So
`python -m src.citation_gate <draft>` does not error: it imports the
module and exits **0** with empty stdout. For every other command in this
layer that trap is a harmless no-op, but for the gate it means an
automated caller gets a **silent, unconditional pass** on a draft nothing
ever checked. `python -m src.draft` with no arguments prints the layer's
usage and exits 0, which is the fastest way to confirm a spelling.

### `python -m src.draft references`

Append or replace a `References` section built from a draft's own cited
citekeys.

Entries are IEEE-style and numbered by first appearance in the draft --
the order pandoc's citeproc numbers citations in, so this list and the
rendered PDF's bibliography agree on which source is `[1]`. Each entry
ends with its citekey in a code span, because the draft's own inline
markers are still `[@citekey]`:

```
[1] J. Doe and R. Roe, "A Paper," *IEEE Trans. Testing*, vol. 3, pp. 1–9, 2024. `doe_paper_2024`
```

Authors, venue, volume and pages come from the ledger's `bib_fields`
column, which `sync` populates from the bib file. A row synced before
that column existed has no fields to format, so its entry degrades to
title and year until the next `python -m src.corpus sync`.

| Flag | Default | What it does |
|---|---|---|
| `-h`, `--help` | -- | Show help and exit |
| `<input>` | required | The draft file (Markdown) |
| `--heading HEADING` | `References` | Heading text, e.g. `"6. References"` to match a draft's own numbered headings |

```bash
python -m src.draft references content/drafts/survey.md
# python -m src.draft references content/drafts/thesis.md --heading "6. References"
```

### `python -m src.draft dossier`

The working state behind a draft: create it, inspect it, back it up,
restore it. A dossier lives at `content/dossiers/` plus the draft's path
relative to `content/drafts/`, minus the suffix -- so
`content/drafts/dt/survey.md` gets `content/dossiers/dt/survey/`. Seven
Markdown files: `scope.md` (the reader, the scope, the glossary),
`evidence.md` (the kept evidence), `rejected.md` (the rejected candidates
and why), `sections.md` (which section cites which citekey), `steering.md`
(the user's steering), `revisions.md` (a revision log), and `retrieval.md`
(every retrieval call, plus a `mark-revision` boundary per revision pass).
[DRAFT-ITERATION.md](DRAFT-ITERATION.md) is the design.

Stdlib only, and never a gate: it takes no lock and only ever opens the
ledger read-only.

Two "missing" cases are deliberately different, because one is actionable
and the other isn't:

| Situation | `status` does |
|---|---|
| No ledger, or an unreadable one | Reports the dossier as usual, says the drift check is unavailable, **exits 0** |
| No dossier for this draft | Prints the `init` command to create one, **exits 1** |

So `python -m src.draft dossier status <draft> >/dev/null` is a usable test for
"does this draft have a dossier yet", while a machine with no corpus built
still gets a full report of what it has.

That test only works without `--json`. Adding it puts the command on the
machine-readable path, which reports a missing dossier as an almost-empty
entry and **exits 0** like every other `--json` call -- consistent with
"the caller branches on the contents", but worth knowing if you were
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
  already kept *or rejected*. A decision, not a defect.
- **reconsider** -- papers the draft already declined that those queries
  still reach, carried with the recorded reason. Not drift (it is true on
  every sweep), so it never marks a dossier stale and prints only
  alongside a real finding; `--json` always carries it.

Like every other read here it takes no lock and writes nothing: the
ledger is opened read-only and the BM25 index used for matching is built
in memory and discarded, leaving `content/retrieval_index.json`
untouched. A sweep costs about 2s cold and 0.2-0.4s warm on this
project's own corpus, and 50 dossiers cost only 0.19s more than one --
see [PERFORMANCE.md](PERFORMANCE.md#what-a-drift-sweep-costs) and
[DRAFT-ITERATION.md](DRAFT-ITERATION.md#drift-across-every-dossier).

`brief` is the one subcommand written for a *subagent* rather than a
person. A skill that dispatches parallel section writers has to give each
one its evidence, and pasting that evidence into the dispatch prompt
spends it as output -- the 5x direction, once per writer. `brief` is what
the prompt points at instead: the writer runs it in its own context, and
that context is discarded when it exits. It selects by citekey, or by a
section named in `sections.md`, and refuses to dump the whole of
`evidence.md` -- a caller reaching for it is trying not to read that.
See [DRAFT-ITERATION.md](DRAFT-ITERATION.md#dispatching-from-the-dossier)
and [TOKENS.md](TOKENS.md).

Its exit code is the contract, because a dispatch prompt cannot read a
paragraph: **0 when it printed at least one block, 1 when it could not
print any** -- no dossier, an unknown section, a section whose row
assigns no citekeys, or not one of the asked-for citekeys transcribed.
The last three are different gaps and the message says which. Everything
except the evidence itself goes to stderr, so stdout is only ever the
blocks. A citekey with no block is
named in a warning rather than dropped: it means the run that found it
never transcribed it, and that material is gone rather than mislaid.

| Subcommand | What it does |
|---|---|
| `init <draft> --genre G` | Create the skeleton. Only ever adds missing files -- safe to re-run |
| `status <draft>` | What each file holds, the draft's section count, and whether the corpus moved since |
| `status --all` | Corpus drift over every dossier: broken citations and new candidates. Always exits 0 |
| `sections <draft>` | Heading -> line range, for reading and editing one section instead of the file |
| `sections <draft> --citekeys` | The dossier's `sections.md` table, derived from the draft: each heading with the citekeys cited under it. `--write` puts it in the dossier |
| `mark-revision <draft>` | Record a revision-session boundary in `retrieval.md`, so `status` can total retrieval cost per revision instead of only as one lifetime figure |
| `brief <draft> [citekey ...]` | The kept-evidence blocks for a section or a citekey list, for a subagent to read. **Exits 1 if nothing resolves** |
| `list` | Every dossier on this machine |
| `export [<name> ...]` | Bundle drafts + dossiers to a `.tar.gz` |
| `restore <archive>` | Unpack a bundle. **Dry run unless `--force`** |

| Flag | Applies to | What it does |
|---|---|---|
| `--genre GENRE` | `init` | Required: `survey`, `thesis-chapter`, `textbook-chapter`, `tutorial`, `deep-research` |
| `--all` | `status` | Report every dossier instead of one draft. Mutually exclusive with a draft path |
| `--json` | `status` | Emit the drift report as JSON, for `draft-reviser` rather than a terminal |
| `--label TEXT` | `mark-revision` | Short name for this revision. Optional -- an unlabelled marker is numbered by order instead (`revision 1`, `revision 2`, ...) |
| `--citekeys` | `sections` | Print the derived `sections.md` table instead of the outline. A citekey cited above the first heading is reported on stderr, never filed under a section that doesn't contain it |
| `--write` | `sections` | With `--citekeys`: write the table into the dossier's `sections.md`, replacing what is there. Refused without `--citekeys`, and refused when the dossier doesn't exist |
| `--section NAME` | `brief` | Take the citekeys from that `sections.md` row. Matches without the section's numbering; an ambiguous name matches nothing rather than guessing |
| `--check` | `brief` | Report what resolves, and what doesn't, without printing the blocks -- what an orchestrator runs before dispatching |
| `--out FILE` | `export` | Archive path (default `drafts-<name>-<date>.tar.gz`) |
| `--with-rendered` | `export` | Include `content/rendered/` too -- large, it holds the PDFs |
| `--force` | `restore` | Actually write, overwriting what is already there |

```bash
python -m src.draft dossier init content/drafts/survey.md --genre survey
python -m src.draft dossier status content/drafts/survey.md
python -m src.draft dossier sections content/drafts/survey.md
# Derive the section -> citekey map instead of writing it by hand
python -m src.draft dossier sections content/drafts/survey.md --citekeys --write

# Before a revision session's first retrieval call
python -m src.draft dossier mark-revision content/drafts/survey.md --label "shorten intro"

# Before dispatching a section writer: do this section's rows resolve?
python -m src.draft dossier brief content/drafts/survey.md --section "2. Failure modes" --check
# What the writer itself runs
python -m src.draft dossier brief content/drafts/survey.md --section "2. Failure modes"
python -m src.draft dossier brief content/drafts/survey.md talasila_composable_2025

# After a sync: which drafts went stale, and what specifically
python -m src.draft dossier status --all
python -m src.draft dossier status --all --json

# Back up everything, then one topic with its PDFs
python -m src.draft dossier export
python -m src.draft dossier export digital-twins-for-software-engineers --with-rendered

# Restore: look first, then commit to it
python -m src.draft dossier restore drafts-all-2026-08-06.tar.gz
python -m src.draft dossier restore drafts-all-2026-08-06.tar.gz --force
```

A bundle carries `drafts/`, `dossiers/` and optionally `rendered/`, with
paths relative to `content/` so it restores into a checkout whose
`[content].dir` points elsewhere. It does **not** carry
`content/ledger.sqlite` (regenerate with `python -m src.corpus sync`) or
`papers/bibliography.bib` (your reference manager's export, which
AGENTS.md keeps as the source of truth rather than something this
pipeline copies). Restore refuses the whole archive -- rather than
skipping a member -- if any entry is a link or device node, escapes the
extraction directory, or sits outside those three directories.

### `python -m src.draft retrieve`

BM25 retrieval over the synced corpus. Read-only, takes no lock, needs no
venv. [RETRIEVAL.md](RETRIEVAL.md) has the ranking details.

| Subcommand | What it does |
|---|---|
| `search "<query>"` | Rank the corpus and return a snippet per candidate |
| `evidence "<query>" --citekey KEY` | The passages of that one document that bear on the query (`--windows`, 2 by default) |

`evidence` is a lookup, not a stage: use it when a `search` snippet is not
enough to judge a source you are minded to cite. Nothing is obliged to
call it. [REJECTION.md](REJECTION.md) explains why an earlier arrangement,
which made a cheap first pass mandatory and used it to *reject*, was
withdrawn.

| Flag | Applies to | Default | What it does |
|---|---|---|---|
| `--k N` | `search` | 5 | How many candidates to rank |
| `--chars N` | all | 600 / 500 | Window size (evidence / search) |
| `--citekey KEY` | `evidence` | required | Which document to read |
| `--windows N` | `evidence` | 2 | How many passages to return |
| `--log DRAFT` | all | -- | Record the call and its payload size in DRAFT's dossier |

```bash
python -m src.draft retrieve search "digital twin architecture" --k 15 \
    --log content/drafts/survey.md
python -m src.draft retrieve evidence "digital twin architecture" \
    --citekey ferko_architecting_2022 --log content/drafts/survey.md
```

`--log` appends to `retrieval.md` in that draft's dossier, which is what
turns "retrieval is where the tokens go" into a number for a particular
draft (`python -m src.draft dossier status` totals it). A `--log` path that
isn't under `content/drafts/`, or a filesystem error while writing, is
reported on stderr and skipped -- the measurement never fails the search
it was measuring.

Exits 1 with the fix if there is no ledger; an empty result set is not an
error.

### `python -m src.review coverage`

How much of what retrieval surfaced actually made it into a draft's
citations. **Informational, not a gate**, and unlike the gate it never
runs automatically. Stdlib-only, like `citation_gate` and `references` --
it reuses `src.retrieval`, which is itself stdlib.

| Flag | Default | What it does |
|---|---|---|
| `-h`, `--help` | -- | Show help and exit |
| `<draft>` | required | The draft to check |
| `--query QUERY` | required, repeatable | A retrieval query to check coverage against. Give it more than once |
| `--k K` | `5` | Top-k results per query |
| `--write` | off | Also write the report to `content/review/`, mirroring the draft's path. Printing stays the default -- the usual use is a question asked and answered in one sitting |
| `--formats FORMATS` | `md,tex,pdf` | With `--write`, the additional formats to render beside the Markdown report. The `.md` is always written -- it *is* the report -- so `--formats pdf` still produces it. `tex`/`pdf` need `pandoc`/`pdflatex` on `PATH` |

```bash
python -m src.review coverage content/drafts/survey.md \
    --query "digital twin composability" \
    --query "runtime verification"
# ... --k 10
# ... --write --formats md
```

A written report records the whole invocation in its header, queries
included: a coverage figure means nothing without knowing 62% *of what*.

### `python -m src.review provenance`

Reports what in each cited source actually supports the claim citing it,
quoting a real passage. Layer 4, the review layer: advisory, not a gate.

Unlike the other two it writes by default -- reading a provenance report
in a terminal was never the point. The report lands in
`content/review/<topic>/<stem>.provenance.md`, mirroring the draft's path,
with its `.tex`/`.pdf` renders beside it.

| Flag | Default | What it does |
|---|---|---|
| `-h`, `--help` | -- | Show help and exit |
| `<draft>` | required | The Markdown draft to check |
| `--formats FORMATS` | `md,tex,pdf` | Additional formats to render beside the Markdown report. The `.md` is always written -- it *is* the report, and `tex`/`pdf` are renders of it, so `--formats pdf` still produces the `.md`. `tex`/`pdf` need `pandoc`/`pdflatex` on `PATH` |

```bash
python -m src.review provenance content/drafts/survey.md
# python -m src.review provenance content/drafts/survey.md --formats md
# python -m src.review provenance content/drafts/survey.md --formats md,tex,pdf
```

### `python -m src.review verbatim`

Layer 4, the review layer, with three subcommands: verbatim overlap
between a draft and one cited source, a whole-draft x whole-corpus scan,
and page location for a phrase. Stdlib-only -- but `locate` shells out to
the `pdftotext` binary, so that subcommand needs poppler-utils on `PATH`.
`overlap` and `scan` read already-parsed text via `src/overlap_index.py`'s
cache instead. Run with no arguments to print its usage.

[PLAGIARISM.md](PLAGIARISM.md) is the conceptual companion to this
section: what `overlap`/`scan` catch and don't (verbatim only --
paraphrase is a later, unbuilt detection tier), the fingerprinting
technique and its literature sources, and a measured
`docling`-vs-`pdftotext` backend comparison.

| Subcommand | Arguments | What it does |
|---|---|---|
| `overlap` | `<draft> <citekey> [--n N]` | Longest verbatim word-n-gram runs shared between the draft's sentences citing `<citekey>` and that source's parsed text. `--n` defaults to `8` |
| `scan` | `<draft> [--min-run N] [--gap N] [--limit N] [--json] [--write] [--formats F]` | Slides the whole draft across the whole corpus index -- catches verbatim reuse `overlap` structurally cannot: an uncited source, or connective prose that cites nothing. `--min-run` (default `8`, floor is the corpus index's own n-gram size) is the reporting length floor; `--gap` (default `1`) tolerates that many non-matching words inside a run, recovering a lightly-edited near-verbatim lift; `--limit` caps how many findings print (default: all of them). `--json` prints the findings as data instead of as text (see below). `--write` also files the report under `content/review/`, mirroring the draft's path, beside the same draft's provenance and coverage reports; printing stays the default. `--formats` (default `md,tex,pdf`) names the *additional* formats rendered beside the Markdown report -- the `.md` is always written |
| `locate` | `<citekey> "<phrase>" [more...]` | Which PDF page each phrase (or its distinctive words) appears on |

**Exit codes**, shared with the other two review aids: `0` on every
successful invocation, findings or not -- advisory, never a gate. `1` for
a draft this layer will not read (missing, or resolving outside
`content/`). `2` for a malformed invocation, the usual CLI-usage error,
not a verdict.

```bash
python -m src.review verbatim overlap content/drafts/survey.md talasila_composable_2025
# python -m src.review verbatim overlap content/drafts/survey.md talasila_composable_2025 --n 12
python -m src.review verbatim scan content/drafts/survey.md
# python -m src.review verbatim scan content/drafts/survey.md --min-run 12 --gap 2 --limit 10
# python -m src.review verbatim scan content/drafts/survey.md --write --formats md
# python -m src.review verbatim scan content/drafts/survey.md --json > findings.json
# python -m src.review verbatim locate talasila_composable_2025 "a digital twin is"
```

**`--json`, and who it is for.** The findings were text and nothing else
until 5.4.0, so a programmatic consumer external to this module --
a remediation loop, an eventual overlap gate -- had to regex the printed
lines back into data. `--json` prints the same findings list as a payload
instead: the envelope every review aid's JSON carries (a notice that this
is not a verdict, the aid, the draft, the exact command, the version),
the three flags that set the reporting floor (`min_run`, `gap`, `limit`),
how many findings the allowlist suppressed (`suppressed`, see below), and
one object per finding with `citekey`, `page`, `end_page`, `tier`,
`span_words`, `matched_words`, `start`, `fragment`, `context`,
`cites_source`, `quoted`, and `severity` -- the same `long`/`short`/`quoted` bucket the
written report groups by (see below), so a consumer of the payload reads
the same severity a human reviewer sees. It is an additional
serialisation of what `scan` already computed, never a second
computation, so the payload and the two printed forms cannot disagree
about what was found. A clean draft emits `"findings": []` and still
exits 0 -- "nothing found" is data too.

`cites_source: false` is the printed form's `UNCITED SOURCE`, and
`quoted: true` its `quoted`: booleans rather than those labels, because a
caller that has to match display text is back where it started.

`page` and `end_page` are equal for an ordinary single-page run;
`end_page > page` means the run spans a source page break (#131) -- the
printed forms render that as `p.N-M` instead of picking one side.

`start`, `fragment` and `context` describe the **normalised word stream**
-- the draft masked (code and the References section blanked), citation
markers stripped, lowercased, punctuation dropped -- not the draft file
as written. `start` is a word offset into that stream, not a character
offset and not a line number, and `fragment` is those words
space-joined. So a finding *locates* a passage for a reader; a consumer
that means to edit the draft has to find the real span itself.

`--write` files the payload as `content/review/<topic>/<stem>.verbatim.json`,
beside the Markdown report, whether or not `--json` was also given -- it
is written for whatever reads it later, not for whoever ran the command.
What `--json` prints is byte-for-byte what `--write` files, so redirecting
stdout and reading the sibling give the same bytes, and neither carries a
timestamp: two runs over an unchanged draft and corpus produce identical
payloads. With both flags, the written-files summary goes to stderr so
stdout stays a valid JSON file. `dossier export` carries the payload with
the report.

Only `verbatim` emits one so far; `provenance` and `coverage` follow in
their own issues, which is why
[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)'s planned `agenda` aid treats
each aid's JSON as optional.

**What `scan` does not see, and why that matters more than it sounds.**
`scan` is the **exact tier** of three planned detection tiers, and the
other two are not built. It matches word n-grams, so literal
paraphrase -- the same sentence skeleton with a synonym swapped every few
words -- is invisible to it *by construction*, not by omission. Because
the drafts this pipeline produces are LLM-written, and that is an LLM's
normal failure mode when it drifts too close to a source, the reuse mode
`scan` cannot see is the dominant one. Read a clean run as "no exact or
near-exact copying found", never "no borrowed wording found". An
unbuilt tier contributes nothing and nothing in the output says so -- see
[PLAGIARISM.md](PLAGIARISM.md) and
[discussion #115](https://github.com/prasadtalasila/chitragupta/discussions/115)
for the three-tier plan.

**The disk cache, and what the first run costs.** `scan` builds a
corpus-wide index the first time it runs -- `content/overlap/index.bin`
plus an `index.json` header -- merged from the per-document fingerprints
in `content/overlap/docs/<citekey>.fpr`. That first build is the only
slow part (~27s over this project's 497-document corpus); every later
scan over an unchanged corpus reloads the merged index and is
sub-second. The header key covers the n-gram size, the tokenizer version
and, per document, its `pdf_hash` *together with the parsed file's own
size and mtime* -- so a `sync` that changes one PDF re-fingerprints that
one document and re-merges, rather than rebuilding from scratch. Both
halves of that per-document key earn their place: re-parsing the corpus
under a different `[parser].backend` rewrites the text without touching
the PDF, and the parsed-file stat is the only part that notices. The
whole directory is a cache, not an output:
delete it and the next run rebuilds whatever it needs. See
[ARCHITECTURE.md](ARCHITECTURE.md#what-is-reproducible-and-what-is-not).

`scan` groups a match's `(citekey, diagonal)` -- the source position minus
the draft position, held constant across a run, where the source position
is global across the whole document rather than reset per page (#131) --
and merges runs on the same diagonal within `--gap` words of each other,
so a single edited word inside an otherwise-verbatim passage still
reports as one run, and so does a genuine lift that spans a source page
break: it used to report as two (or more) shorter findings, with a short
remainder stranded alone on the far side of the break falling under
`--min-run` and vanishing entirely; it now merges into one finding whose
`page`/`end_page` cover the full range. Each finding reports whether the containing draft paragraph
actually cites that source (`UNCITED SOURCE` if not) and whether the run
sits inside quote delimiters -- both informational on stdout; `--write`'s
report goes one step further and *groups* findings most-damning-first
(long runs, then short, then quoted) so a reviewer reads the worst one
first, though the underlying findings are the same ones `scan` produces
for a later gate to be tuned against.

**The allowlist.** `scan` also consults `content/verbatim_allowlist.toml`
if present -- a per-host, gitignored list of acronyms, phrases,
definitions and whole paragraphs its owner has decided are boilerplate,
never a project-tracked file. A finding is dropped only when discounting
its allowlisted words leaves less than `--min-run`; a short allowlisted
phrase sitting inside a much longer, otherwise-unexplained lift is kept.
See [PLAGIARISM.md](PLAGIARISM.md#the-boilerplate-allowlist) for the file
format and the reasoning.

`locate` reports page numbers by splitting on the form-feed characters
between pages. Both backends emit them, so a page number here is a page
you can turn to whichever one parsed the citekey -- see
[CONFIG.md](CONFIG.md#backend-pdftotext-or-docling). One limit: `docling`
writes a break between consecutive pages that carry text, so a page with
no extracted items at all shifts the numbering after it. The passage
sidecar records each item's own page and is not affected; where the two
disagree, believe `python -m src.review provenance`.

### `python -m src.draft render`

Render a Pandoc-Markdown or LaTeX draft. Needs `pandoc` (and `pdflatex`
for PDF) on `PATH`, but no Python package from the enrich group.

Citations render IEEE-style -- `[1]`, and `[3]–[6]` for a consecutive run
-- over a numbered bibliography of complete entries, via the CSL style
vendored at `assets/csl/ieee.csl`. In the copy handed to pandoc, the
draft's own References section (if `python -m src.draft references` added one)
keeps its heading but has its entries replaced by citeproc's placement
anchor, so the output carries exactly one bibliography -- citeproc's,
the one that can be numbered consistently with the inline markers --
under the draft's own heading, including a numbered one like
`## 6. References`. The draft file itself is never modified.

**Where the output lands.** `<slug>` may itself contain directories --
`content/drafts/dt-for-engineers/survey.md`, or
`content/drafts/books/software-engineering/chapter.md` -- and every
format is written **beside the draft**, mirroring its path under
`content/drafts/` into `content/rendered/`:

```
content/drafts/dt-for-engineers/survey.md
   -> content/rendered/dt-for-engineers/survey.{md,tex,pdf,docx}
```

This is the same mirroring rule `content/dossiers/` follows (see
[DRAFT-ITERATION.md](DRAFT-ITERATION.md#the-dossier)), so one topic
directory names a draft, its dossier and its renders together -- which
is what lets `dossier export <topic> --with-rendered` find them. A flat
`content/drafts/<slug>.md` renders to `content/rendered/<slug>.*`, as it
always has, and an input under `content/` but outside `content/drafts/`
(`content/loose.md`, say) has no path to mirror and lands flat too.

**Both reading and writing are confined to `content/`.** The input must
resolve under the content directory -- a draft kept
outside it is refused by name rather than rendered, so that one directory
stays the whole record of the work. Every path this command *writes*,
resolves inside `content/`: only the part of a draft's path below
`content/drafts/` is ever carried over, and both sides are resolved
before they are compared, so no argument -- a `..`, a symlinked draft --
mirrors anywhere else. The three ways a write could still escape are
configuration or symlinks rather than arguments, and each is refused
with `[error]` rather than redirected: a `content/rendered` or
`content/drafts` that resolves out of the content directory, and a
topic directory under `content/rendered/` that is a symlink pointing
off-tree.

| Flag | Default | What it does |
|---|---|---|
| `-h`, `--help` | -- | Show help and exit |
| `<input>` | required | The draft file (Markdown or LaTeX) |
| `--format FORMAT` | `pdf` | Output format -- e.g. `pdf`, `tex`, `docx`, `md` |
| `--documentclass CLASS` | `article` | LaTeX documentclass |
| `--fontsize SIZE` | `12pt` | LaTeX font size |
| `--papersize SIZE` | `a4` | LaTeX paper size, **without** the `paper` suffix pandoc appends itself -- so `a4`, `letter` |
| `--margin MARGIN` | `1in` | Page margin, passed to the `geometry` package |
| `--csl PATH` | `assets/csl/ieee.csl` | CSL style for citations and the bibliography. A relative path is looked for under the current directory first (like `<input>`), then the repo root -- so the repo-relative form `[render] csl` uses works from anywhere |
| `--no-collapse-citations` | off | Render a run as `[3], [4], [5], [6]` instead of `[3]–[6]`, i.e. leave the style exactly as it is on disk |

`--format md` on a **Markdown** draft is a special case, and the one
output you can read without a PDF viewer: it writes a `.md` beside the
draft's other renders, with the citekeys replaced by the same IEEE
numbers the PDF uses (`[1]`, `[3]–[6]`) over a reference list built from
the ledger. It needs no `pandoc`, because pandoc's Markdown writer is the
wrong tool for it -- that writer escapes every marker (`\[1\]`, since
`[1]` could be a link reference) and emits the bibliography as `:::`
fenced divs full of `[...]{.csl-left-margin}` spans, none of which render
anywhere except pandoc.

The draft itself is never modified: it keeps its `[@citekey]` markers,
which are what `citation_gate` verifies and what `--citeproc` resolves
when rendering. A `.tex` input still goes through pandoc for `md`, since
converting a thesis fragment's `\citep{...}` genuinely is a format
conversion.

```bash
python -m src.draft render content/drafts/survey.md --format pdf
# python -m src.draft render content/drafts/survey.md --format tex
# python -m src.draft render content/drafts/survey.md --format docx
# python -m src.draft render content/drafts/survey.md --format md   # numbered Markdown, no pandoc needed
# python -m src.draft render content/drafts/thesis.md \
#     --documentclass report --fontsize 11pt --papersize letter --margin 1.5in
```

### `python -m src.enrich`

Orchestrates the enrichment layer: docling -> embeddings/Chroma -> BERTopic
-> provenance -> render. **Needs the venv.** Each stage probes its own
prerequisites and reports a real per-stage status, so a
`skipped/missing-binary` result on a machine without TeX Live is a
correct answer rather than a bug.

| Flag | Default | What it does |
|---|---|---|
| `-h`, `--help` | -- | Show help and exit |
| `--target {host,docker}` | `host` | **Informational only** -- stages self-probe regardless |
| `--stages STAGES` | all three, or `docling` alone with `--for-draft` | Comma-separated subset of `docling,embed,bertopic` |
| `--for-draft PATH` | -- | Scope `docling` to the papers this draft cites. Refused with an explicit `--stages embed` or `bertopic` |

```bash
.venv-full/bin/python -m src.enrich
# .venv-full/bin/python -m src.enrich --stages docling
# .venv-full/bin/python -m src.enrich --stages embed,bertopic
# .venv-full/bin/python -m src.enrich --for-draft content/drafts/digital-twins.md

# A review report and a draft render are tier-1 commands, not stages --
# no venv, no lock:
# python -m src.review provenance content/drafts/survey.md
# python -m src.draft render content/drafts/survey.md --format pdf
```

#### Enriching one draft's papers

By default the unit of work is the corpus: every ledger item, whether a
draft cites it or not. `--for-draft` narrows that to the papers one draft
cites, read out of the draft with the same reader the citation gate uses
(`src.citation_gate.extract_citekeys`), so a draft resting on twenty-three
papers costs twenty-three parses rather than the whole library:

```console
$ .venv-full/bin/python -m src.enrich --for-draft content/drafts/digital-twins.md
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
`python -m src.review provenance <draft>` afterwards: it is a tier-1
command, so it needs no venv and waits on no lock.

Two stages refuse the scope rather than honouring it:

```console
$ .venv-full/bin/python -m src.enrich --for-draft content/drafts/digital-twins.md --stages embed
  --for-draft cannot scope embed: it builds one whole-corpus artefact, and a partial one is indistinguishable from a complete one. Run them as separate commands:
      python -m src.enrich --for-draft content/drafts/digital-twins.md --stages docling
      python -m src.enrich --stages embed
```

That is a tier, not a ladder ([LADDERS.md](LADDERS.md)): `embed` writes a
Chroma collection carrying no record of how much of the corpus it covers,
and every skill that reads it decides by asking only whether
`content/chroma/` exists -- so a collection holding eleven papers would
answer as though it held 642. `bertopic` overwrites `content/topics.json`
whole, so a scoped run would replace a corpus-wide topic model with an
eleven-document one. Neither is worth a silently smaller answer, so the
run stops and names the command to use instead (exit status 3).

A citekey the draft cites and the ledger has never heard of is named, not
quietly dropped, and a scope matching nothing at all stops rather than
reporting `ok` over zero documents. The Docling cache is per-document and
never rewritten to match the scope, so a scoped run and a full run do no
duplicate work in either order -- narrow first and widen later, or the
reverse, and nothing is parsed twice.

The `embed` stage names each document as it reaches it, so a run over a
real corpus is legible rather than silent for its whole duration:

```
=== embed ===
  [1/646] abbiati_modelling_2024 -- embedded, 92 chunk(s)
  [2/646] abduvakhobov_scalable_2024 -- unchanged, 65 chunk(s)
  [3/646] adhikari_digital_2023 -- no text to embed
  ...
  646 document(s): 102 embedded, 399 unchanged, 145 with no text -- 32033 chunk(s) in the index
```

`unchanged` is the incremental skip (same text as last run, not
re-encoded); `no text to embed` is a bib entry with no parsed text behind
it, which stays searchable by title through `src/retrieval.py` and not by
meaning. Ctrl+C is safe: every chunk upserted before the interrupt is
already in `content/chroma/`, the stage says how far it got, and re-running
picks up from there.

### `scripts/install_full_pipeline.sh`

One install path for both a bare machine and the Docker image. Takes
**stage names as positional arguments**, not flags.

| Stage | What it does |
|---|---|
| `python-deps` | **Default when no stage is given.** Creates the venv and runs `poetry install --with enrich` |
| `os-deps` | `apt-get` the system packages (TeX Live, Pandoc, poppler-utils, Poetry, git/curl/unzip, and OpenCV's runtime libraries -- see [PDF-PARSER.md](PDF-PARSER.md#docling-fails-every-document-with-an-opencv-recursion-error)). Needs root; auto-sudo's. Opt-in -- not everyone wants a script touching apt |
| `dev-deps` | `poetry install --with dev` (pytest, pytest-cov) into the same venv. Needed only to run the test suite. Run `python-deps` first |
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

### `scripts/release.py`

Builds the release archive under `release/`. A maintainer tool.

**Takes no arguments and parses none** -- including `-h`/`--help`, which
it ignores while building the archive anyway. Run it bare:

```bash
.venv-full/bin/python scripts/release.py
```

`tests/`, `bench/`, `.github/` and `.gitignore` are excluded from the
archive. Every prose document ships: `docs/`, `README.md`, `SOUL.md`,
`AGENTS.md`, `DEVELOPER-AGENTS.md` and `DEVELOPER.md`, plus `.claude/`.

## Running sync on a schedule

`python -m src.corpus sync` is deterministic, idempotent, and takes its own
write lock (`src.runlock`) -- it was already safe to run unattended.
What makes it worth *actually* putting on a schedule is the other two
things: exit codes an unattended caller can branch on without parsing
any text, and `logs/pipeline.log` (rotated; see `[logging]` in
`config.toml.example`) as a persistent transcript to check afterwards.

`src/enrich/__main__.py` writes to the same file, so a host that schedules
both has one transcript rather than two. Each line names its source in
`%(name)s` -- the module, so `sync` logs as `src.sync` whatever the
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
summary, at the level `[logging].level` sets -- a cron or systemd
wrapper around these commands doesn't need its own `>> some.log 2>&1` to
get a durable record of those. Three messages are the exception and stay
terminal-only by design: a docling worker's GPU-OOM fallback (runs in a
child process with no route back to the file), the Ctrl+C interrupt
notice (runs in a signal handler, deliberately kept to a bare `print`),
and the "another run already holds the lock" refusal (the losing side of
a race must not touch a file the winner is writing). All three are rare
and none is the kind of thing a schedule needs to recover from
unattended.

**Exit codes are the API**, not the printed text:

| Exit code | Meaning | What an unattended caller should do |
|---|---|---|
| `0` | Clean -- everything that needed parsing, parsed | Nothing |
| `1` | At least one document failed, or a prior deterministic failure is still unresolved | Alert; `logs/pipeline.log`'s FAILED/WARNING lines name which citekey and why |
| `2` | Another run already holds the write lock | Nothing -- expected under any schedule tight enough to overlap a slow run. The skipped cycle costs nothing; the next one picks up whatever this one would have |

**A schedule written before 5.2.0 now fails instead of lying.** That
release moved this command behind `python -m src.corpus sync` and left
the old spelling importing a module and exiting **0** -- so an unedited
crontab kept reporting success while syncing nothing, for a release. It
now prints the line above and exits **64**, which is deliberately none of
the three codes in the table: a caller that reads `2` as "expected, do
nothing" must not read this as that. If a schedule of yours starts
failing after upgrading, the message names the replacement; that is the
whole fix.

### cron

```bash
# crontab -e -- runs hourly, on the hour. cd into the repo first: sync
# resolves config.toml and papers/bibliography.bib relative to it.
0 * * * * cd /path/to/chitragupta && .venv-full/bin/python -m src.corpus sync
```

cron's own default, with no `MAILTO` set, is to mail stdout/stderr to
the crontab's owner -- which needs a working local MTA to go anywhere,
and most hosts don't have one configured. `logs/pipeline.log` doesn't depend
on any of that: it's a plain file, written every run regardless of mail
setup.

### systemd (service + timer)

Two unit files, not one -- systemd's usual split between "what" and
"when":

```ini
# /etc/systemd/system/chitragupta-sync.service
[Unit]
Description=Chitragupta corpus sync

[Service]
Type=oneshot
WorkingDirectory=/path/to/chitragupta
ExecStart=/path/to/chitragupta/.venv-full/bin/python -m src.corpus sync
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
[`scripts/install_full_pipeline.sh`](#scriptsinstall_full_pipelinesh)
above) -- scheduling only runs what's already installed, it doesn't
install anything itself.

## Environment variables

Every `config.toml` setting has a matching environment variable that
overrides it for one run. The full list, with accepted values, is in
[CONFIG.md](CONFIG.md#every-setting). The ones that most often appear on
a command line:

```bash
# Point at a different bibliography or output directory for one run
# BIB_FILE=/path/to/other.bib .venv-full/bin/python -m src.corpus sync
# CONTENT_DIR=/tmp/scratch-content .venv-full/bin/python -m src.corpus sync

# Keep config.toml somewhere else entirely
# CONFIG_PATH=/etc/research/config.toml .venv-full/bin/python -m src.corpus sync

# Try the higher-fidelity parser with some parallelism, without editing the file
# PARSER=docling PARSER_WORKERS=auto .venv-full/bin/python -m src.corpus sync

# Confine a docling run to one GPU (no config setting for this, by design)
# CUDA_VISIBLE_DEVICES=0 .venv-full/bin/python -m src.corpus sync
```

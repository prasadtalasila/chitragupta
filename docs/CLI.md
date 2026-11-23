# ⌨ Command reference

Status: **reference.**

**Written for** anyone running this pipeline: it is the reference you
keep open beside a terminal. **Assumed:** nothing beyond
[README.md](../README.md)'s Quickstart. **Not covered here:** why any of
it is built the way it is; [ARCHITECTURE.md](ARCHITECTURE.md) has the
shape and [DESIGN.md](DESIGN.md) the constraints.

Every command this repository provides, every flag it accepts, and which
interpreter each one needs.

## 🔧 Installing

**On Windows or WSL2, read [WINDOWS.md](WINDOWS.md) first.** Both work,
and CI runs a blocking `windows-latest` leg, but native Windows needs a
POSIX shell and three OS binaries installed by hand, and WSL2 has one
filesystem-layout trap. Everything else on this page applies unchanged.

There are two install paths. Both land in a venv named `.venv-full`, and
everything below this section is identical either way:

```bash
mkdir my-project && cd my-project
python3 -m venv .venv-full && source .venv-full/bin/activate
pip install chitragupta-cli
chitragupta init
```

or, from a git checkout (for working on the pipeline itself; see
`DEVELOPER-AGENTS.md`):

```bash
git clone https://github.com/prasadtalasila/chitragupta && cd chitragupta
pipx install poetry
bash scripts/install_full_pipeline.sh all
source .venv-full/bin/activate
```

A venv keeps `pip install` clear of Debian/Ubuntu's PEP 668
`externally-managed-environment` error, and while it is activated in
the shell you launch Claude Code from, the hooks can import
`chitragupta` ([HOOKS.md](HOOKS.md#-the-launcher-contract)).

`chitragupta init DIR` writes the same project directory a checkout
gives you (`config.toml`, `.claude/`, `papers/`,
`content/{drafts,dossiers,specs,review,rendered}/`, `assets/` and the
prose docs). Add `--agent codex` or `--agent opencode`, repeatable, to
write that harness's folders too ([LLM-AGENTS.md](LLM-AGENTS.md)).

The base `pip install chitragupta-cli` covers tiers 1 and 2
([Which interpreter](#-which-interpreter)), everything except the
enrichment layer. `chitragupta install <stage>` refuses three stage
names by pointing at the pip command that reaches them:

```bash
# chitragupta install python-deps refuses, naming `chitragupta install enrich`,
# whose pip equivalent is:
pip install 'chitragupta-cli[enrich]'   # tier 3 -- chitragupta enrich (docling, embeddings, topic clustering)

# chitragupta install dev-deps refuses, naming this. Only a checkout ships
# the test suite, so this extra is not useful outside one.
pip install 'chitragupta-cli[dev]'

# The enrich extra, pinned to the chitragupta already running, so asking
# for an extra cannot upgrade the tool underneath the command that asked.
chitragupta install enrich

# chitragupta install all refuses, naming `chitragupta install enrich`
# plus this (Debian/Ubuntu + root; `chitragupta doctor` reports what is
# missing on any other host):
chitragupta install os-deps
```

[PACKAGING.md](PACKAGING.md) has the full command-surface table;
[NAME.md](NAME.md) has why the distribution is `chitragupta-cli` while
the command stays `chitragupta` (`cg` for short).

## ⚖ Which interpreter

Three tiers. `python` means your Python 3 interpreter; `python3` is
equally correct. The tiers distinguish environments, not names. The
one place the name is fixed is `.claude/settings.json`, which launches
the hooks as `python` ([HOOKS.md](HOOKS.md#-the-launcher-contract) says
why).

| Tier | Interpreter | Commands |
| --- | --- | --- |
| 1 | **`python`**: stdlib only, no venv | `chitragupta.draft` (all thirteen commands), `chitragupta.corpus ledger`, `chitragupta.corpus topics`, `chitragupta.corpus discover` (its semantic rung upgrades itself when tier 3 is installed), `chitragupta.review` (all eleven aids; `support` needs the `enrich` extra and exits 0 with a notice without it) |
| 2 | **`.venv-full/bin/python`**: venv, for `bibtexparser` | `chitragupta.corpus sync` |
| 3 | **`.venv-full/bin/python`**: venv with the `enrich` group | `python -m chitragupta.enrich` |

Tier 1 is deliberate. The chain that enforces the one rule
(`chitragupta.draft gate` -> `chitragupta.draft references` ->
`chitragupta.draft render`) imports nothing outside the standard
library, so a broken, missing or wrong-Python virtual environment
cannot block it.
[ARCHITECTURE.md](ARCHITECTURE.md#-which-interpreter-and-why) has the
full reasoning. `draft render` shells out to `pandoc` and LuaLaTeX, and
`review verbatim` to `pdftotext`, but those are OS packages, not Python
dependencies.

For a `pip install`ed project there is one environment, and the tiers
collapse to whether a command needs the `enrich` extra: only tier 3
does. `chitragupta <layer> <verb>` and `python -m chitragupta.<layer>
<verb>` reach the same command once that interpreter is the venv's own.
The module form is kept because the hooks and every genre skill invoke
`python -m chitragupta.draft gate`; use either form by hand, but don't
change what a hook or a skill invokes.

In an `init`-ed project, tier 1's promise covers the code, not finding
the interpreter. A checkout's `-m` finds `chitragupta/` beside it from
any `python`; an installed project has none, so
`python -m chitragupta.draft gate` needs the venv's `bin/` on `PATH`.
Without it, `citation_gate_hook.py` reports an environment fault,
distinct from a bad citekey.

The most likely first error is the wrong interpreter:
`ModuleNotFoundError: No module named 'bibtexparser'` means you ran
`python -m chitragupta.corpus sync` instead of `.venv-full/bin/python -m
chitragupta.corpus sync`.

## 🚀 The full first run, step by step

Every command appears below at least once, in the order a first run
reaches it; [Every command and flag](#-every-command-and-flag) is the
exhaustive reference.

### ⌨ As the `chitragupta` command

With `.venv-full/bin/activate` sourced (see [Installing](#-installing)):

```bash
# 1. Install, and get a project directory -- see Installing above.

# 2. Export your library to BibTeX at papers/bibliography.bib (gitignored,
#    so no install path populates it). ZOTERO.md has Zotero specifics.
mkdir -p papers && cp /path/to/your/exported-library.bib papers/bibliography.bib

# 3. Create your config (`chitragupta init` already did). See CONFIG.md.
cp config.toml.example config.toml   # git checkout only

# 4. Sync the corpus. Needs the venv; only one sync (or enrichment run)
#    can write at a time -- a second one exits 2 at once.
chitragupta corpus sync
# chitragupta corpus sync --reparse         # re-extract text even if the PDF is unchanged
# chitragupta corpus sync --remove-stale    # only after reading the stale list it prints

# 5. Inspect what it found. Read-only, takes no lock, needs no venv.
chitragupta corpus ledger
# chitragupta corpus ledger --list
# chitragupta corpus ledger --status parse_failed
# chitragupta corpus ledger --citekey talasila_composable_2025
# chitragupta corpus ledger --collections    # your collections, if chitragupta-importer wrote the bib

# 5b. Optional: name your topics in content/seed_topics.toml and see
#     which papers match each.
# chitragupta enrich --stages seed-topics
chitragupta corpus topics
# chitragupta corpus topics --topic "digital twin"

# 6. Optional: the enrichment layer. Nothing below needs it --
#    RETRIEVAL.md says which stage is worth your time.
chitragupta enrich --stages docling,embed
# chitragupta enrich --stages docling --for-draft content/drafts/<slug>.md

# 7. Search the corpus the way a skill does. Read-only.
chitragupta draft retrieve search "digital twin composability" --k 15
chitragupta draft retrieve search "digital twin composability" --unit passage
chitragupta draft retrieve evidence "calibration" --citekey talasila_composable_2025 \
    --log content/drafts/<slug>.md

# 8. In your coding agent (Claude Code, Codex or OpenCode), ask for a draft, e.g.:
#    "write a survey section on digital twin composability"
#    "draft a thesis chapter on runtime verification for autonomous robots"
# The matching skill runs its own gate -> references -> render chain and
# writes a dossier beside the draft. LLM-AGENTS.md has each agent's setup.

# 9. Re-run that chain by hand (no venv needed). `render` runs the gate
#    first and refuses a draft citing a key the ledger does not hold.
chitragupta draft gate content/drafts/<slug>.md
chitragupta draft references content/drafts/<slug>.md --heading "References"
chitragupta draft render content/drafts/<slug>.md --format pdf
chitragupta draft render content/drafts/<slug>.md --format tex
chitragupta draft render content/drafts/<slug>.md --format docx
chitragupta draft render content/drafts/<slug>.md --format md    # numbered Markdown copy, no pandoc needed

# 10. Read and maintain the draft's dossier.
chitragupta draft dossier list
chitragupta draft dossier brief content/drafts/<slug>.md
chitragupta draft dossier sections content/drafts/<slug>.md --citekeys --write
chitragupta draft dossier status --all --json
chitragupta draft dossier export <slug>

# 11. Check the draft against its sources. Review aids, not gates.
chitragupta review provenance content/drafts/<slug>.md            # what in each source supports the claim citing it
chitragupta review verbatim overlap content/drafts/<slug>.md <citekey>  # wording shared with that one source
chitragupta review verbatim scan content/drafts/<slug>.md        # ...with *any* parsed source, cited or not
chitragupta review verbatim locate <citekey> "a phrase to find"  # which pdf page a phrase is on
chitragupta review coverage content/drafts/<slug>.md --query "digital twin composability"
chitragupta review synthesis content/drafts/<slug>.md            # how many sources each unit rests on
chitragupta review figure content/drafts/<topic>/<slug>.md   # what the TikZ figures' geometry says
chitragupta review uncited content/drafts/<slug>.md              # which sentences carry no citation at all
chitragupta review quotation content/drafts/<slug>.md            # is each quoted span really in that source?
chitragupta review agenda content/drafts/<slug>.md               # merges the eight draft-level aids into one worklist
chitragupta review support content/drafts/<slug>.md              # does the cited source actually entail this claim?
chitragupta review union content/rendered/<book>/book.tex          # did assembling the book lose a unit's citekey?
# add --write to any of these to file the report under content/review/,
# mirroring the draft's path -- printing stays the default
```

Two commands are for working *on* this repository, so only their
checkout form exists:

```bash
bash scripts/install_full_pipeline.sh dev-deps   # pytest, pytest-cov, actionlint and the git hooks
python -m pytest                                 # the suite itself

python3 scripts/release.py                       # bundles release/chitragupta-<version>.zip
```

### 🐍 As the module form (`python -m chitragupta.<layer>`)

Every command above is also `python -m chitragupta.<layer> <verb>`, for
example `python -m chitragupta.corpus sync` or
`python -m chitragupta.draft gate content/drafts/<slug>.md`. This is the
form hooks and skills invoke, and it works however the package got here.

### 📦 Checkout and `pip install` side by side

A checkout and an installed package run the same commands. Where a
checkout copies `config.toml.example` and runs
`scripts/install_full_pipeline.sh`, an installed package runs
`chitragupta init`, `chitragupta install` and `chitragupta doctor`
([PACKAGING.md](PACKAGING.md) has the command table).

## ⌨ Every command and flag

Defaults shown are the value used when the flag is omitted. Examples
use the console script; `python -m chitragupta.<layer> <verb>` reaches
the same command. Activate `.venv-full` first. The scheduling and
environment-variable sections spell out `.venv-full/bin/python`
because a cron job or systemd unit has activated nothing.

Run `chitragupta --help` for every layer and verb, and
`<command> --help` (for example `chitragupta draft gate --help`) for
every flag.

Three commands set a project up rather than work in one: `init`,
`doctor` and `install`. [PACKAGING.md](PACKAGING.md) has the design
behind them.

### 🏗 `chitragupta init`

Scaffolds a project directory: `config.toml` (from
`config.toml.example`), `.claude/`, `papers/`,
`content/{drafts,dossiers,specs,review,rendered}/`, `assets/` and the
prose docs. Exits `1`, writing nothing, when the source files are
missing or the target is unsafe.

| Flag | Default | What it does |
| --- | --- | --- |
| `[DIR]` | `.` | Where to write the project |
| `--force` | off | Overwrite existing files, named one by one |
| `--dry-run` | off | Print the tree that would be written; write nothing |
| `--agent {claude,codex,opencode}` | `claude` | Harness to set up; repeat for several ([LLM-AGENTS.md](LLM-AGENTS.md)) |

### 🩺 `chitragupta doctor`

Probes and reports: OS binaries, the enrich extra, torch against the GPU
driver, a competing distribution, and the hook launchers. Takes no
flags, installs nothing and always exits `0`.

### 🔧 `chitragupta install`

Runs the stage of `scripts/install_full_pipeline.sh` that a pip install
cannot do itself. Takes one stage name.

| Stage | What it does |
| --- | --- |
| `os-deps` | Runs the script's `os-deps` stage (needs root) |
| `gpu-torch` | Reinstalls torch from a wheel index matching the GPU driver, when the default wheel would run CPU-only |
| `enrich` | Installs the `enrich` extra, pinned to the running version |
| `all`, `dev-deps`, `python-deps` | Refused by name; prints the pip command that reaches them instead (exit `1`) |

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

# Exit codes: 0 = clean, 1 = documents this host could not parse,
#             2 = another run holds the lock,
#             3 = everything parsed, but the bibliography has a hole in it.
```

The exit code is the whole API an unattended caller has. The two
nonzero completion codes split by *remedy*:

- **1**: this host could not produce documents it was asked for: a
  parse failure in this run, a deterministic one left by a previous run
  (not retried, so it stays nonzero until you deal with it), or the
  parse backend being unavailable. The remedy is on this machine.
- **3**: everything asked for was parsed, but the bibliography
  promises something that is not there: the bib file yielded no
  references against a non-empty ledger, a PDF it points at is missing
  or unreadable, two entries share one citekey, the BibTeX parser
  dropped an entry (usually unbalanced braces), or a citekey was
  skipped because it cannot be a filename. The remedy is in the bib
  file or on the disk it points at.

`1` wins when both hold; `!= 0` means "anything went wrong". After a
dropped entry or unusable citekey, `--remove-stale` deletes nothing and
prints `Refusing to prune: ...`, since the run read less than the bib
file holds. A shared citekey is named in a `WARNING` and *none* of its
entries is synced, because the pipeline does not guess which paper the
key means. An entry type outside BibTeX's standard list (`@software`,
`@online` and the rest of biblatex's) is ignored by design, silently.

Three of the summary's `no-PDF breakdown` reasons set the exit code:

| `no-PDF breakdown` reason | Exit | Why |
| --- | --- | --- |
| `PDF path no longer exists on disk` | **3** | The bib file claims a PDF the disk does not have. `chitragupta/bib_reader.py` calls it "a silent data-loss failure". Fix the path, or drop the `file` field |
| `PDF is on disk but could not be read` | **3** | Permissions, or a failing device. The file is there, so fixing the path is *not* the remedy; check the mode, the mount, the disk |
| `PDF path resolves outside the bib file's own directory` | **3** | The bib file claims an attachment this corpus will not open (see below). Move it beside the `.bib`, point `[bib] path` at the tree it is really in, or drop the `file` field |
| `no file field in bib entry` | 0 | An item with no attachment saved. An ordinary state of a bibliography |
| `non-PDF attachment only` | 0 | Typically an HTML snapshot saved instead of the PDF. Invisible to retrieval, but not a hole |
| `malformed file field` | 0 | This project could not parse the `file` field's `Desc:path:mimetype` shape |

There is deliberately no flag to suppress the first three; fix the path
or drop the `file` field.

#### 📎 Why an attachment has to live beside the bib file

A `.bib` export is data someone else's tool wrote, and its `file` field
may name any file on the host. Without a limit, `/etc/passwd` or
`~/.ssh/id_rsa` could be parsed into `content/parsed/` and quoted into
a draft. So an attachment is accepted only where it *resolves* inside
the directory the `.bib` lives in (`papers/` by default, or wherever
`[bib] path` points); the refusal names the path on stderr. Symlinking
the whole of `papers/` elsewhere is fine; symlinking a subdirectory of
it (to a Zotero storage directory, say) is refused. Point `[bib] path`
at the real location instead.

The same rule applies on the way out. A ledger row whose `parsed_path`
does not resolve inside `content/parsed/` reads as having no parsed
text: `search`, `evidence`, `tldr`, `verbatim` and the enrichment
stages decline it, and the next `corpus sync` re-parses it. Both path
columns are stored relative, so moving a project or its `content/`
directory re-parses nothing ([MIGRATION.md](MIGRATION.md)).

### 🧾 What else still references a citekey you are about to remove

Whenever a run has stale citekeys to report (in report-only mode, and
again just before `--remove-stale` deletes anything), `sync` names what
else in the corpus and enrichment layers still points at each one:

| Artefact | Where it lives | Counted as |
| --- | --- | --- |
| overlap index | `content/overlap/docs/<citekey>.fpr` and `.skipgram.fpr`, plus the citekey list in `index.json` and `skipgram_index.json` | files, each named |
| topic graph | `content/topic_graph.json`'s `edges_overlap`, `edges_withheld` and `edges_semantic` | edges |
| topic membership | `content/topic_set.json`'s `topics[].members[].citekey` and `uncovered`, plus `content/topics.json`'s `assignments` and `memberships` | memberships, per file |
| chroma vectors | the chunk collection under `content/chroma/` | vectors |

```text
  stale   smith_example_2024 (no longer in bibliography.bib)
  Checking what else still references the 1 stale citekey(s) ...
    smith_example_2024: still referenced by 2 artefact class(es)
      overlap index    2 file(s): .../content/overlap/docs/smith_example_2024.fpr, ...
      topic graph      3 edge(s): .../content/topic_graph.json
    Reported, not repaired -- nothing above is touched by this run.
    Drafts and dossiers citing these: chitragupta draft dossier status --all
Review the 1 stale item(s) above, then re-run with --remove-stale ...
```

The scan only reports; `--remove-stale` removes only the ledger row.
Drafts and dossiers are the drafting layer's, so sync does not read
them: it records the stale keys in the ledger, and
`chitragupta draft dossier status --all` lists every draft citing one,
as `missing` or `renamed`, before the prune as well as after it. That is
the list to act on; topic hits expire at the next enrichment run.
Citekeys match exactly. A class that could not be scanned (no
`content/chroma/`, no `enrich` extra, a truncated file) gets a `NOTE:`
line rather than a silent zero.

### 🔁 When a citekey is renamed

A key that leaves the bib while the same paper arrives under another key
is a **rename**, not a removal plus an addition. `sync` recognises one in
two ways:

| Source | When it applies |
| --- | --- |
| The importer's `@comment{cg-renames v1 ...}` block (`old<TAB>new` rows) | the new key is in the bib; the two PDFs may differ |
| A matching `pdf_hash` | exactly one key still in the bib has the stale key's PDF, byte for byte, and that key is new to the ledger this sync |

A PDF that several keys share, or that a key already in the ledger had
before this sync (a book and its chapter, one of them deleted), is
reported as `same PDF as a, b`, never guessed to be a rename. The stale
line names the new key, in report-only and `--remove-stale` runs alike:

```text
  stale   lehner_pattern_2023-1 (no longer in bibliography.bib; renamed to lehner_pattern_2023, same PDF)
```

`sync` writes two things to the ledger, and nothing else:

- `renames`: each `old -> new`, recorded **before** `--remove-stale`
  can prune the old row, so the mapping outlives it.
- `stale_citekeys`: every key the last whole read of the bib no longer
  has.

Nothing is recorded from a read that lost entries, for the reason
`--remove-stale` refuses on one. `sync` never opens a draft or a
dossier; the drafting layer reads both tables to report and swap the
keys
([DRAFT-ITERATION.md](DRAFT-ITERATION.md#-swapping-a-renamed-citekey)).

### ♻ When `sync` re-parses a document it already parsed

A PDF whose bytes haven't changed is not re-parsed. The one exception:
a `parsed` document whose passage sidecar is missing or unreadable is
parsed again, so a `.txt` or sidecar deleted or damaged by hand is
restored. An *empty* sidecar is what a parse that found no prose writes,
and does not trigger a re-parse. It costs one parse each, once
([PERFORMANCE.md](PERFORMANCE.md)); `--reparse` forces all of them now.

### 🗄 `chitragupta corpus ledger`

Read-only view of the corpus layer. **Takes no lock**, so it works while
a sync is running. With no flags it prints a summary.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `--list` | off | List every item |
| `--status STATUS` | -- | List only items with this status: `parsed`, `no_pdf`, `discovered`, `parse_failed` |
| `--citekey CITEKEY` | -- | Show one item in full |
| `--collections` | off | List every collection the corpus holds, with its slug path, display path and paper count, and stop |
| `--collection PATH` | -- | List only items in this collection or one beneath it: a slug path or a `/` display path. An unknown or ambiguous one exits 2 |

```bash
chitragupta corpus ledger
# chitragupta corpus ledger --list
# chitragupta corpus ledger --status parse_failed
# chitragupta corpus ledger --status no_pdf
# chitragupta corpus ledger --citekey talasila_composable_2025
# chitragupta corpus ledger --collections
# chitragupta corpus ledger --collection digital-twin
```

Exits `0` with no ledger yet, or one that needs a sync to migrate it,
printing the instruction. Exits `3` with the cause on stderr when SQLite
will not read the ledger (an interrupted write's journal, a lock held
past the timeout, a damaged file). A stale ledger still exits `0` here,
unlike the gate.

Collections come from a bib written by chitragupta-importer
([ZOTERO.md](ZOTERO.md#-keeping-your-collections-optional)); without
them `--collections` prints nothing and says why. `--collections` prints
each collection's slug path, display path and paper count, counting the
papers beneath it. `--collection` takes a slug path or a `/` display
path, and a parent selects everything beneath it. A value that names no
collection, or several, **exits 2** with the choices on stderr.

### 🏷 `chitragupta corpus topics`

Read-only view of which papers matched each of your seed topics.
**Takes no lock and needs no venv**, though what it reads is written by
`chitragupta enrich --stages seed-topics`. With no flags it prints every
topic.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `--topic PHRASE` | -- | Show only this seed topic's papers |

```bash
chitragupta corpus topics
# chitragupta corpus topics --topic "digital twin"
```

Exits `1` when no report has been written yet, or when `--topic` names a
phrase the report does not hold. A paper is listed under every topic it
matched, and the papers that matched none are listed too. See
[CONFIG.md](CONFIG.md#-seed-topics-organising-the-corpus-by-phrases-you-wrote).

### 🕸 `chitragupta corpus discover`

Resolve a phrase to a topic the corpus has, list a topic's papers and
linked topics, or invert the question with `--paper`. **Takes no lock.**
The relations come from `content/topic_graph.json`, written by
`chitragupta enrich --stages topic-graph`.
[TOPIC-DISCOVERY.md](TOPIC-DISCOVERY.md) explains each relation and the
resolution ladder; [EXPLORE-CLI.md](EXPLORE-CLI.md) walks the views.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `PHRASE ...` | -- | A topic to look up: a known label, a near-miss, or any free phrase. Omitted, every topic is listed |
| `--paper CITEKEY` | -- | Show this paper's topics instead of resolving a phrase |
| `--groups N` | -- | Cut the stored merge tree into as close to N groups as it allows. Composes with `--json` only; exits `2` below one, `1` when the artefact stores no hierarchy |
| `--compare TOPIC TOPIC ...` | -- | Compare two to six topics: shared citekeys, bridge papers, and the edges among them. Composes with `--json` only; exits `2` past six topics, `1` when the phrases collapse onto fewer than two topics |
| `--clusters` | -- | The stored MCL partitions of both edge families and where they disagree. Composes with `--inflation` and `--json` only; exits `1` when the inflation has no partition or the artefact predates the field |
| `--inflation X` | `2.0` | Which stored inflation `--clusters` reads (1.2 to 4.0 by 0.1) |
| `--path TOPIC TOPIC` | -- | The strongest chain between two topics over one family, each hop with its evidence. Requires `--family`; "no path" exits `0`. Composes with `--json` only; exits `1` when the artefact predates the matrices |
| `--family F` | -- | `overlap` or `semantic`, never one fused weight. Required by `--path`; optional on `--hops` |
| `--why TOPIC TOPIC` | -- | Why there is no overlap edge between two topics, with the stored threshold. Composes with `--json` only; exits `1` when a name resolves to no topic or both to the same one |
| `--hops N` | -- | With a phrase: the topic's neighbourhood as rings by hop distance. `N` is a positive count or `all`; add `--family F` to walk one family |
| `--origins LIST` | every class | Only topics of these origins: `seed`, `keyword`, `corroborated`, `emergent`. **`seed` and `keyword` each include the corroborated topics**, so `corroborated` alone asks for that intersection. Composes with every view; `--path` refuses a narrowing `--origins` (exit `2`). Exits `1` on an unknown class |
| `--json` | off | Machine-readable output |
| `--out FILE` | -- | Also write the topic view as a Markdown overview: papers, linked topics, and verbatim member-paper snippets |
| `--k N` | `5` | Results to show when falling back to paper search. With `[retrieval].spelling_correction` on, that search notes any correction on stderr |
| `--html FILE` | -- | Write the whole topic graph as one self-contained HTML page and exit. With `--json`, reports the write as `{"written": FILE}` |
| `--app DIR` | -- | Write the topic graph as an interactive app directory, openable from `file://` ([EXPLORE-WEB.md](EXPLORE-WEB.md)). Composes with `--json` as `--html` does |

```bash
chitragupta corpus discover
# chitragupta corpus discover "digital twin"
# chitragupta corpus discover "digital twin" --out overview.md
# chitragupta corpus discover --paper kritzinger_digital_2018
# chitragupta corpus discover --compare "digital twin" "physical twin" "application"
# chitragupta corpus discover --path "digital twin" "devops" --family overlap
# chitragupta corpus discover --app topicapp/ --origins emergent
```

Exits `1` when the graph artefact is missing (naming the stage to run),
when `--paper` names a citekey in no topic, when a phrase resolves
nowhere and even the paper-search fallback finds nothing, and when an
`--out`, `--html` or `--app` target cannot be written. The write
failure goes to **stderr**. For `--out` it comes after the view has
printed, so check the exit status; `--html` and `--app` print nothing
before the write.

### ✅ `chitragupta draft gate`

The hard gate: fails if a draft cites a citekey the ledger doesn't hold
as a parsed source. A key with no ledger row fails as `not found in
ledger`; one whose PDF never parsed (`no_pdf`, `discovered`,
`parse_failed`) fails naming its status.
**Takes no options**: every argument is a file to check.

| Argument | What it does |
| --- | --- |
| `-h`, `--help` | Show usage and exit 0 |
| `<file> [<file> ...]` | One or more drafts to check |

```bash
chitragupta draft gate content/drafts/survey.md
# chitragupta draft gate content/drafts/*.md      # several at once

# Exit codes: 0 = every citation verified,
#             1 = at least one unresolved citekey, or a file outside content/,
#             2 = no files given,
#             3 = the ledger could not be read, so nothing was checked.
```

A file outside `content/` is a `FAIL` for that document and the rest
are still checked, so one bad path cannot hide the others; it exits 1,
not the usage code 2, because it is a document that did not pass.

**Exit 3 is never a verdict.** The ledger is there but could not be
read (an interrupted write's journal, another process holding the
lock, a damaged file, or one needing a sync to migrate). The gate then
checks nothing, prints nothing on stdout, and says on stderr what to
do. It never repairs: `chitragupta corpus sync` rolls back an
interrupted write when it opens the ledger. A *missing* ledger is
different: a cited key fails with exit 1 and a citation-free draft
passes.

**Check the spelling in any script or CI step that runs this.**
`chitragupta/citation_gate.py` has no `__main__` block
([ARCHITECTURE.md](ARCHITECTURE.md#-which-interpreter-and-why)), so
`python -m chitragupta.citation_gate <draft>` imports the module and
exits **0** with empty stdout: a **silent, unconditional pass** on a
draft nothing checked. `chitragupta draft` with no arguments prints the
layer's usage, the fastest way to confirm a spelling.

### 📚 `chitragupta draft references`

Append or replace a `References` section built from a draft's own cited
citekeys. Entries are IEEE-style, numbered by first appearance (the
order citeproc numbers in, so this list and the PDF agree on `[1]`),
and each ends with its citekey in a code span:

```text
[1] J. Doe and R. Roe, "A Paper," *IEEE Trans. Testing*, vol. 3, pp. 1–9, 2024. `doe_paper_2024`
```

Authors, venue, volume and pages come from the ledger's `bib_fields`
column; a row synced before that column existed degrades to title and
year until the next `chitragupta corpus sync`.

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
that leans on them. `content/drafts/dt/survey.md` produces
`content/rendered/dt/survey.evidence.{md,tex,pdf}`. A sidecar is
**never committed** (`.gitignore` excludes
`content/rendered/**/*.evidence.*`), because it carries verbatim
wording from copyrighted sources.

It prints only `quote:` fields, never `claim:` or a legacy `support:`
([DOSSIER.md](DOSSIER.md)); a block with several prints each, in order,
under its source's one heading. Its universe is the draft's own citations,
so it cannot introduce a citekey, and every citekey it prints sits in a
code span the gate blanks, so it adds no citation. With no dossier or
no `quote:` it prints `no quoted evidence recorded` and exits **0**.
It reads both `[@citekey]` and `\citep{...}`, so a thesis `.tex`
fragment gets a standalone sidecar too.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<input>` | required | The draft file (Markdown or LaTeX) |
| `--format FORMAT` | `md` | Output format, passed to `render` for anything but `md`. Exactly one; a comma-separated list is a usage error (`exit 2`) |
| `--output-dir DIR` | mirrored | Write here instead of `content/rendered/<mirrored path>`; confined to `content/` |

```bash
chitragupta draft evidence content/drafts/dt/survey.md --format pdf
# leaves survey.evidence.md beside survey.evidence.pdf -- the Markdown is
# the sidecar's own source, and the only diffable form of it
```

### 🗂 `chitragupta draft dossier`

The working state behind a draft: create it, inspect it, back it up,
restore it. `content/drafts/dt/survey.md` gets
`content/dossiers/dt/survey/`. [DOSSIER.md](DOSSIER.md) describes every
file in it (including the opt-in `outline.md`) and
[DRAFT-ITERATION.md](DRAFT-ITERATION.md) the design. Stdlib only, never
a gate: it takes no lock and opens the ledger read-only.

| Subcommand | What it does |
| --- | --- |
| `init <draft> --genre G` | Create the skeleton. Only adds missing files, so it is safe to re-run |
| `status <draft>` | What each file holds, the section count, and whether the corpus moved since; with an `outline.md`, which declared queries ran, returned nothing (`no evidence`) or were never issued |
| `status --all` | Corpus drift over every dossier: broken citations (including keys the last sync found stale, before `--remove-stale` prunes them), citekeys sync recorded as renamed, recorded collections that no longer resolve, and new candidates. Always exits 0 |
| `sections <draft>` | Heading -> line range, for editing one section instead of the file |
| `sections <draft> --citekeys` | The `sections.md` table derived from the draft: each heading with the citekeys cited under it |
| `outline <draft>` | Read and validate `outline.md` (sections are `##`-or-deeper headings). **Exits 1** if there's no `outline.md`, or a section has neither a `brief:` nor a `claim:` |
| `mark-revision <draft>` | Record a revision boundary in `retrieval.md`, so `status` totals retrieval cost per revision, and keep a numbered snapshot of the draft and its figures under `versions/` (skipped when unchanged) |
| `apply-renames <draft>` | Swap every citekey sync recorded as renamed for its replacement, in the draft, `evidence.md`, `sections.md` and `rejected.md`, and log it in `revisions.md`. Refuses, changing nothing for it, a key whose recorded renames form a cycle or whose replacement is not citable (a parsed row sync did not find stale), swaps the rest, and **exits 1** naming each refused key. **Exits 1** too for a draft path that does not exist. Names the `review quotation` re-check when a renamed paper's PDF changed |
| `snapshot <draft> --label TEXT` | Keep the draft and its figures as a named version (`002-sent-to-supervisor`) for `draft diff --against`. Always taken |
| `versions <draft>` | Every snapshot, oldest first: number, date, trigger, label |
| `stamp <draft>` | Record the draft's text digest in `scope.md`, so `status` reports `CHANGED since last stamp` after a hand edit. Run after `gate` passes, never before |
| `set-language <draft> <language>` | Record the draft's dialect (a BCP-47 tag: `en-GB`, `en-US`, `en-IN`) in `scope.md` for `draft style` |
| `acronyms-suggest <draft>` | Acronyms this draft defines that aren't in `[style].acronyms` yet. Prints only |
| `acronyms-suggest <draft> --apply` | The same, then writes them to your acronyms file. Refuses if `[style].acronyms` is unset, rather than writing into the vendored `assets/style/acronyms.toml` |
| `brief <draft> [citekey ...]` | The kept-evidence blocks for a section or citekeys, for a subagent to read. **Exits 1 if nothing resolves** |
| `check-evidence <draft>` | Advisory: a citekey with **more than one block** (readers get only the first), a block that repeats `claim:`, `relevance:` or `support:` (only the first is read), and a `claim:` that reads like one of its block's `quote:` lines with the words moved. Exits 1 only when there is no dossier |
| `prune <draft>` | A **dry run** listing the `evidence.md` blocks for citekeys the draft no longer cites. Exits 0 |
| `prune <draft> --apply` | The same, and removes them by line span, from `evidence.md` only, never `sections.md` or `rejected.md` |
| `prune <draft> --citekey <key>` | Restrict to one citekey (repeatable). Exits **1** if a named citekey was refused (still cited, unrecorded, `sections.md`-only, or with more than one block) |
| `list` | Every dossier on this machine |
| `export [<name> ...]` | Bundle drafts + dossiers to a `.tar.gz` |
| `restore <archive>` | Unpack a bundle. **Dry run unless `--force`** |

| Flag | Applies to | What it does |
| --- | --- | --- |
| `--genre GENRE` | `init` | Required: `survey`, `thesis-chapter`, `textbook-chapter`, `tutorial`, `deep-research`, `digest`, `research-paper` (which also gets a `paper.md`) |
| `--outline` | `init` | Also create `outline.md`. Opt-in |
| `--all` | `status` | Report every dossier. Mutually exclusive with a draft path |
| `--json` | `status`, `versions`, `apply-renames` | Emit JSON, for `draft-reviser` rather than a terminal |
| `--label TEXT` | `mark-revision` | Optional name for this revision; unlabelled markers are numbered (`revision 1`, ...) |
| `--label TEXT` | `snapshot` | Required: the milestone's name. Not all digits, unique within the draft, with at least one ASCII letter or digit |
| `--citekeys` | `sections` | Print the derived `sections.md` table. A citekey cited above the first heading is reported on stderr |
| `--write` | `sections` | With `--citekeys`: replace the dossier's `sections.md`. Refused without `--citekeys` or a dossier |
| `--check` | `outline`, `brief` | Report shape problems, or what resolves, without printing the content. What an orchestrator runs before dispatching |
| `--section NAME` | `brief` | Take the citekeys from that `sections.md` row, matched without numbering; an ambiguous name matches nothing |
| `--score` | `check-evidence` | Also print each warning's overlap score. Off by default, so there is nothing to reword against |
| `--out FILE` | `export` | Archive path (default `drafts-<name>-<date>.tar.gz`) |
| `--with-rendered` | `export` | Include `content/rendered/` and the non-Markdown review renders (large) |
| `--force` | `restore` | Actually write, overwriting what is there |

```bash
chitragupta draft dossier init content/drafts/survey.md --genre survey --outline
chitragupta draft dossier sections content/drafts/survey.md --citekeys --write
chitragupta draft dossier mark-revision content/drafts/survey.md --label "shorten intro"
chitragupta draft dossier snapshot content/drafts/survey.md --label "sent to supervisor"
chitragupta draft dossier brief content/drafts/survey.md --section "2. Failure modes" --check
chitragupta draft dossier prune content/drafts/survey.md --apply
chitragupta draft dossier status --all --json                  # after a sync
chitragupta draft dossier export digital-twins-for-software-engineers --with-rendered
chitragupta draft dossier restore drafts-all-2026-08-06.tar.gz --force
```

**Exit codes.** `status` on a draft with no dossier prints the `init`
command and **exits 1**; with no ledger, or an unreadable one, it
reports the dossier without the drift check and **exits 0**. So
`status <draft> >/dev/null` tests "does this draft have a dossier yet",
but only without `--json`, which exits 0 either way (check `recorded`
in the payload). `status --all` always exits 0, because drift is the
normal state of a live corpus; it reports `missing` citekeys,
`candidates` and `reconsider`
([DRAFT-ITERATION.md](DRAFT-ITERATION.md#-drift-across-every-dossier)).
`brief` exits 1 when it printed no block (no dossier, unknown section,
a row with no citekeys, nothing transcribed), with everything but the
blocks on stderr
([DRAFT-ITERATION.md](DRAFT-ITERATION.md#-dispatching-from-the-dossier)).

A bundle carries `drafts/`, `dossiers/`, and the `.md` and `.json`
files under `review/` (`--with-rendered` adds `rendered/`), paths
relative to `content/`. It does **not**
carry `content/ledger.sqlite` (regenerate with `chitragupta corpus
sync`) or `papers/bibliography.bib` (your export stays the source of
truth). Restore refuses the whole archive if any entry is a link or
device node, escapes the extraction directory, or sits outside those
four directories. [MIGRATION.md](MIGRATION.md) covers backups.

### 🔎 `chitragupta draft retrieve`

BM25 retrieval over the synced corpus. Read-only, takes no lock, needs no
venv. [RETRIEVAL.md](RETRIEVAL.md) has the ranking details.

| Subcommand | What it does |
| --- | --- |
| `search "<query>"` | Rank the corpus and return a snippet per candidate |
| `evidence "<query>" --citekey KEY` | The passages of that one document that bear on the query (`--windows`, 2 by default) |

`evidence` is a lookup, not a stage: use it when a `search` snippet is
not enough to judge a source. Nothing is obliged to call it
([REJECTION.md](REJECTION.md) has why a mandatory first pass was
withdrawn).

| Flag | Applies to | Default | What it does |
| --- | --- | --- | --- |
| `--k N` | `search` | 5 | How many candidates to rank |
| `--unit document\|passage` | `search` | `document` | What a result is: `passage` ranks paragraphs and returns the scoring paragraph with its page. Scores are not comparable across units |
| `--collection PATH` | `search` | -- | Rank only inside this collection or one beneath it: a slug path or a `/` display path (see `ledger --collections`). An unknown or ambiguous one exits 2. Scoring stays corpus-wide; only the candidate set narrows |
| `--chars N` | all | 600 / 500 | Window size (evidence / search) |
| `--citekey KEY` | `evidence` | required | Which document to read |
| `--windows N` | `evidence` | 2 | How many passages to return |
| `--log DRAFT` | all | -- | Record the call, its collection and its payload size in DRAFT's dossier `retrieval.md` |
| `--origin declared\|extended\|reground` | all | -- | With `--log`: whether this query came from `outline.md` verbatim, extended a section that came up thin, or re-ran a section's query with `--y-prev` after a hand edit |
| `--y-prev TEXT` | `search` | -- | Append this text (bounded to 1500 characters) to the query for a second retrieval round, merged with the first and capped back to `--k` (FEATURE-ROADMAP.md's E4). The text is never spelling-corrected |

```bash
chitragupta draft retrieve search "digital twin architecture" --k 15 \
    --log content/drafts/survey.md
chitragupta draft retrieve evidence "digital twin architecture" \
    --citekey ferko_architecting_2022 --log content/drafts/survey.md
chitragupta draft retrieve search "digital twin architecture" \
    --y-prev "the drift compensator now recomputes offset every cycle" \
    --k 15 --origin reground --log content/drafts/survey.md
```

A `--log` path outside `content/drafts/`, or a filesystem error while
writing it, is reported on stderr and skipped; the measurement never
fails the search. Exits 1 with the fix if there is no ledger, one that
needs a sync to migrate, or one that cannot be read; an empty result is
not an error. A single-character query word never ranks, so either
subcommand warns, naming it; two-character words (`AI`, `5G`) do rank
([RETRIEVAL.md](RETRIEVAL.md#-where-the-token-length-floor-came-from)).

Words added to the query before ranking are noted on stderr, and `--log`
records them in the `expanded` column: an acronym's expansion
(`dt -> digital twin`) and, with `[retrieval].spelling_correction` on, a
spelling correction (`strucutral ~> structural`)
([RETRIEVAL.md](RETRIEVAL.md#-a-misspelled-query-word-can-reach-its-corpus-spelling)).

### 📄 `chitragupta draft render`

Render a Pandoc-Markdown or LaTeX draft. Needs `pandoc` (and, for PDF,
LuaLaTeX with `texlive-luatex` and the fonts `os-deps` installs) on
`PATH`, but no Python package from the enrich group. `chitragupta doctor`
says whether each font is there. [RENDERING-FLOW.md](RENDERING-FLOW.md)
explains what happens inside a render: citation resolution, the
References section citeproc replaces, fonts, mathematics, and figure,
table and equation numbering.

Citations render IEEE-style (`[1]`, and `[3]–[6]` for a consecutive
run) via `assets/csl/ieee.csl`, under the draft's own References
heading. The draft file itself is never modified.

**Where the output lands.** Every format is written mirroring the
draft's path under `content/drafts/` into `content/rendered/`, the same
rule `content/dossiers/` follows:

```text
content/drafts/dt-for-engineers/survey.md
   -> content/rendered/dt-for-engineers/survey.{md,tex,pdf,docx}
```

An input under `content/` but outside `content/drafts/` lands flat.

**Both reading and writing are confined to `content/`.** A draft
outside it is refused by name, and so is a configured or symlinked
output directory that resolves off-tree, or a figure symlink landing
outside the draft's directory. A `pdf` render runs LuaLaTeX without
shell escape and behind a read fence, which needs a `TMPDIR` with no
dot-directory in its path; a `.bib` field's raw TeX is printed, never
run. Lua in the draft's own TeX or figures is not fenced:
[SECURITY.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/SECURITY.md)
has what this does and does not cover.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<input>` | required | The draft file (Markdown or LaTeX) |
| `--format FORMAT` | `pdf` | Output format, e.g. `pdf`, `tex`, `docx`, `md`. Exactly one; a comma-separated list is a usage error (`exit 2`), not rendered as several formats. Render each needed format with its own `--format`; a review aid's plural `--formats` is the one that takes a list |
| `--documentclass CLASS` | `article` | LaTeX documentclass |
| `--fontsize SIZE` | `12pt` | LaTeX font size |
| `--papersize SIZE` | `a4` | LaTeX paper size, **without** the `paper` suffix pandoc appends itself, so `a4`, `letter` |
| `--margin MARGIN` | `1in` | Page margin, passed to the `geometry` package |
| `--csl PATH` | `assets/csl/ieee.csl` | CSL style for citations and the bibliography. A relative path is looked for under the current directory first (like `<input>`), then the project directory, then the shipped assets, so both your own style and the vendored one are found from anywhere |
| `--no-collapse-citations` | off | Render a run as `[3], [4], [5], [6]` instead of `[3]–[6]`, i.e. leave the style exactly as it is on disk |
| `--fragment` | off | Emit an `\input`-able LaTeX fragment (no preamble) whose top heading is a chapter, for assembling a book; see [below](#-assembling-a-book---fragment-and---output-dir) |
| `--output-dir DIR` | mirrored | Write here instead of `content/rendered/<mirrored path>`, a `pdf`'s figure looks included; confined to `content/` |
| `--index-terms PATH` | off | With `--fragment` only: place the book index's entries from the term table `registry build --index` wrote, and write `<unit>.index.json` beside the fragment; see [the index](book/BOOK-INDEX.md) |

```bash
chitragupta draft render content/drafts/survey.md --format pdf
# chitragupta draft render content/drafts/survey.md --format tex
# chitragupta draft render content/drafts/survey.md --format docx
# chitragupta draft render content/drafts/survey.md --format md   # numbered Markdown, no pandoc needed
# chitragupta draft render content/drafts/thesis.md \
#     --documentclass report --fontsize 11pt --papersize letter --margin 1.5in
```

**`--format md` on a Markdown draft** needs no `pandoc`: it writes a
`.md` with the PDF's IEEE numbers and reference list, dropping raw
LaTeX. A `.tex` input still goes through pandoc.

**Unicode reaches the output as written**; no NFKC fold is applied,
because it would turn `m²` into `m2`. A `pdf` render uses LuaLaTeX with
STIX Two and a fallback font chain; there is no pdflatex option. A
`tex` or `--fragment` output gets `chitragupta-unicode.sty` beside it
when needed, for a template that compiles with pdflatex. A character no
font has fails the `pdf` build by name; write it as LaTeX, or add a
`\DeclareUnicodeCharacter{<hex>}{...}` line to
`content/unicode-extra.tex`
([RENDERING-FLOW.md](RENDERING-FLOW.md#-the-pdf-engine-and-its-fonts)).

**Floats.** Standalone renders include
`assets/latex/chitragupta-floats.tex` (`\floatpagefraction` 0.8), so a
half-page figure stays on a text page; a `--fragment` gets the file
copied beside it. A figure still alone on a page is reported as a
`[float-page]` note.

**Figure looks.** After a `pdf` render, every figure gets the pictures
[`figure look`](#-chitragupta-figure-look) writes, under `figures/`
beside the PDF, reported as `[figure-look]` notes; they never fail the
render.

#### 📕 Assembling a book: `--fragment` and `--output-dir`

```bash
chitragupta draft render content/drafts/<book>/<unit>.md \
    --format tex --fragment
```

`--fragment` emits an `\input`-able fragment: no preamble, the top
heading becomes a `\chapter` (minus any `Chapter 1:` prefix, since the
`book` class numbers chapters), code unhighlighted, and citations left
as `\citep{...}` with the corpus `.bib` beside it, so one source has
one number across the book.
[RENDERING-FLOW.md](RENDERING-FLOW.md#-three-rewrites-only-a-fragment-gets)
has the rewrites.

A unit already lands in `content/rendered/<book>/`, where `book.tex`
is composed, so `--output-dir` is only for output that belongs
elsewhere under `content/`. [WRITE-A-BOOK.md](WRITE-A-BOOK.md) is the
assembly procedure.

### 🎨 `chitragupta draft style`

Report where a draft's prose departs from
[WRITING-STANDARDS.md](WRITING-STANDARDS.md): Vale's prose rules, the
recorded dialect, acronym drift, and checks computed in plain Python
(listed in `chitragupta/style_rules.py`'s `PYTHON_CHECKS`). **A review
aid: it exits 0 whatever it finds**, and nothing blocks on it.

| Rule | What it means |
| --- | --- |
| `chitragupta.TableNoCaption`, `TableNoId`, `TableDuplicateId`, `TableMalformedId`, `TableUnreferenced`, `TableUnknownRef`, `TableRefOutsideSection` | A table with no caption, no `<!-- table: <id> -->`, a duplicate or malformed id, no reference, a `tableref` to nothing, or references only from another section (§13) |
| `chitragupta.FigureNoCaption`, `FigureDuplicateId`, `FigureMalformedId`, `FigureUnreferenced`, `FigureUnknownRef`, `FigureRefOutsideSection` | The same contract for `<!-- figure: -->` markers and `figureref`s (§10) |
| `chitragupta.EquationOrphanMarker`, `EquationDuplicateId`, `EquationMalformedId`, `EquationUnreferenced`, `EquationUnknownRef`, `EquationRefOutsideSection` | The same for an equation opted in with `<!-- equation: id -->`; an orphan marker has no `<!-- math -->` block below it (§12) |
| `chitragupta.AcronymCase` | An acronym's expansion written in a different case from `content/acronyms.toml`. A capital at a sentence, line or heading start is accepted. Always `review` |
| `chitragupta.BareCitekey` | A ledger citekey a reader would see printed raw: in prose without its `@`, or set as code. A parsed key in prose may be repaired unattended to `[@key]`; a code span or a key with no parsed PDF is `review` (WRITING-STANDARDS.md §16) |
| `chitragupta.BareUrl` | A URL is printed raw where a `[text](https://…)` link would read better and give the pdf something to click. A code span that is *only* a URL counts; one holding a command that contains a URL does not |
| `chitragupta.WideCodeLine` | A code line is wider than the page fits. In a Markdown draft the render wraps it, so this is a quality note; in a `.tex` fragment nothing can wrap it and it runs into the margin |
| `chitragupta.ChapterSelfNumbered` | A `.tex` unit's `\chapter{}` states its own number or appendix letter (`Chapter 1: …`), so the book prints it twice. A Markdown unit's `--fragment` render drops the prefix, so nothing is reported for one |

[WRITING-STANDARDS.md](WRITING-STANDARDS.md#-9-what-is-checked-mechanically-and-what-is-not)
maps every rule to its standard. §14's third rule (a breakable form for a very
long token) is deliberately **not** checked: TeX hyphenates long English words
correctly, so there is no overflow to prevent. Terms in
`content/style_exceptions.toml` are never reported by a prose rule other than
`Acronyms`. Repeated findings collapse to one with a count.

```bash
chitragupta draft style content/drafts/<path>
chitragupta draft style content/drafts/<path> --json
```

It cannot be made a gate, not even behind a flag: it measures against
a `language:` line someone typed, which can be wrong
([ARCHITECTURE.md](ARCHITECTURE.md)'s "Layer 4"). The dialect is
declared, never inferred; the report names which source it used:

1. `--language en-GB`, for this run only. Writes nothing.
2. The `language:` line in the dossier's `scope.md`.
3. `[style].language` in `config.toml`.

```bash
chitragupta draft dossier set-language content/drafts/<path> en-GB
```

With none set, **no dialect rules run**, and the command measures the
draft both ways and proposes one:

```text
dialect: not checked -- no `language:` in scope.md and no [style].language
it reads as en-GB (en-GB: 0, en-US: 13). To record that:
  chitragupta draft dossier set-language content/drafts/<path> en-GB
```

It proposes and never writes ([HOUSE-STYLE.md](HOUSE-STYLE.md)).

**Vale's findings need the `vale` binary on `PATH`** (`chitragupta
install os-deps`); without it the header says so and the Python checks
still run. `assets/vale/README.md` lists what the vendored rules
deliberately leave out, such as `licence`/`license`, which no string
match settles.

### 🎯 `chitragupta draft spec`

The outline a book is generated from, and the human sign-off on it
([WRITE-A-BOOK.md](WRITE-A-BOOK.md)). Stdlib only. Writes only under
`content/specs/`, mirroring the book's directory under
`content/drafts/`.

```bash
chitragupta draft spec init content/drafts/<book> --title "<title>" [--author "<name>"]
chitragupta draft spec show content/drafts/<book>
chitragupta draft spec show content/drafts/<book> --unit sec-1
chitragupta draft spec sign content/drafts/<book> --by "<name>"
chitragupta draft spec status content/drafts/<book>
chitragupta draft spec align  content/drafts/<book> [--json]
chitragupta draft spec seed   content/drafts/<book> --genre <genre> [--dry-run]
```

| Command | Does | Exit |
| --- | --- | --- |
| `init` | write an outline skeleton with front and back matter, a preface template (`content/drafts/<book>/preface.md`), a copyright page template (`content/specs/<book>/copyright.tex`) and the index's exceptions (`content/specs/<book>/index.toml`); `--author` writes the outline's `- author:` line. Never overwrites the three templates | 1 if a spec is already there |
| `show` | the outline as a tree, under its title and `author:` line, or `--unit <id>` for one unit's slice | 1 on an unknown unit or a spec that does not parse |
| `sign` | record that a human approved this outline, by whole-file digest and one per chapter; and, while `copyright.tex` still holds its `<year>` placeholder, write the current year over it (in practice once, at the first sign-off) | 1 on a spec that does not parse |
| `status` | what the outline holds, whether it is signed off, and which chapters moved | 1 when unsigned or changed since sign-off |
| `align` | whether each authored chapter still matches the sections the outline declares | 1 on any finding, or on a chapter file symlinked out of its book |
| `seed` | write each chapter's declared sections into its dossier `outline.md`, as bare headings | 1 on an unsigned or unparseable outline, or on a chapter file symlinked out of its book |

Four heading levels: `#` the book, `##` a part, `###` a chapter, `####`
a section, each with an explicit `{#id}`, because a derived id changes
when a heading is reworded. The reserved part and generated-page ids
are covered in [front matter](book/FRONT-MATTER.md),
[appendices](book/APPENDICES.md), [back matter](book/BACK-MATTER.md)
and [the index](book/BOOK-INDEX.md).

`status`'s exit code is **not a gate**: it reads back a record of a
person's decision and refuses no write
([the book design notes](book/DESIGN-NOTES.md#-what-statuss-exit-code-is-and-is-not)).

### 🧱 `chitragupta draft unit`

One section's generation contract, and the record of its acceptance
([WRITE-A-BOOK.md](WRITE-A-BOOK.md)). Reads the outline `spec` owns;
writes only `content/specs/<book>/units/<id>.json`.

```bash
chitragupta draft unit contract content/drafts/<book> <unit-id> [--source CITEKEY]...
chitragupta draft unit contract content/drafts/<book> <unit-id> --json
chitragupta draft unit accept   content/drafts/<book> <unit-id> [--source CITEKEY]...
chitragupta draft unit status   content/drafts/<book>
```

| Command | Does | Exit |
| --- | --- | --- |
| `contract` | the inputs one unit is generated from, and their digest | 1 on an unknown unit, a part/chapter, or a spec that does not parse |
| `accept` | record a generated unit, once the citation gate passes on it | 1 if the unit's own chapter is unsigned or misaligned, the draft is missing, a `--source` is not in the ledger, or the gate refuses it |
| `status` | where every unit stands, and what its dossier says about the same prose (`--json`); then any acceptance record whose unit has left the outline, as `accepted, but no longer in the outline: <ids>` (`"orphaned"` in `--json`), deleting nothing | 1 while any unit is not accepted and current; orphaned records do not count |

`--source` is repeatable and part of the input digest, which covers the
inputs only, never the unit's prose. `accept` **invokes the citation
gate, it does not replace it**: nothing here is a second gate.

### 📇 `chitragupta draft registry`

Terminology, claims and cross-references over a book's **accepted**
units ([WRITE-A-BOOK.md](WRITE-A-BOOK.md)), written under
`content/specs/<book>/registries/`.

```bash
chitragupta draft registry build   content/drafts/<book> [--glossary PATH] [--notation PATH] [--index PATH]
chitragupta draft registry check   content/drafts/<book>
chitragupta draft registry excerpt content/drafts/<book> <unit-id>
chitragupta draft registry index   content/drafts/<book> --idx content/rendered/<book>/book.idx
```

| Command | Does | Exit |
| --- | --- | --- |
| `build` | rebuild `terms.md`, `claims.md`, `xrefs.md` from accepted units; with `--glossary`/`--notation`, also write the book's Glossary and List of Symbols as LaTeX from the units' `scope.md` glossaries | 1 if the book has no readable outline; with either flag, also 1 if a glossary bullet cannot be printed or pandoc is missing, and then no page is written |
| `check` | what the registries disagree on | **always 0** |
| `excerpt` | what one unit's generation should be told the rest of the book settled | 1 only if the book has no readable outline |
| `build --index PATH` | also write the index's term table, `index-terms.json`, from the glossaries and `content/specs/<book>/index.toml` | 1 if `index.toml` is malformed or names a term, chapter or target that does not exist, and then nothing is written |
| `index` | after the book's third `lualatex` pass: turn `book.idx` into `book.ind` through `upmendex`, and write `index.md` and `index.json` beside the other registries, each finding with the `index.toml` line that fixes it | 1 on a stale build (a chapter rendered without, or against an older, term table), a `book.idx` older than the table or a sidecar, a missing `upmendex` or pandoc, or an `upmendex` failure; no `book.ind` and no report are written then |

**`check` is a review aid and exits 0 whatever it finds**: it reports a
machine's reading of prose, not a human's decision, and no flag makes
it block
([the book design notes](book/DESIGN-NOTES.md#-why-registry-check-exits-0-when-the-two-status-commands-do-not)).
Every report names the units it skipped. Contradiction between claims
is **not** detected, only duplication, because a machine can decide
that.

### 🔭 `chitragupta draft tldr`

A one-paragraph summary per citekey. `write` never generates one: it
stores what a person or skill passes on stdin under
`content/tldr/<citekey>.json`, keyed to a fingerprint of the current
parsed text, and `show` reports it **stale** after a re-parse. With
none written, `show` falls back to the authors' own abstract from the
passage sidecar, re-derived on every read. It never touches
`content/ledger.sqlite`, since a summary may be LLM output.
[TLDR.md](TLDR.md) has the design and measurements.

```bash
echo "This paper proposes ..." | chitragupta draft tldr write smith2024
chitragupta draft tldr show smith2024
chitragupta draft tldr show smith2024 --json
```

| Command | Does | Exit |
| --- | --- | --- |
| `write <citekey>` | store stdin as `<citekey>`'s summary | 1 if the citekey isn't in the ledger, has no parsed text yet, or stdin is empty |
| `show <citekey> [--json]` | print the best available summary, its `source`, and whether it's stale | **always 0**; nothing recorded is not an error |

| `source` | Meaning |
| --- | --- |
| `human` | somebody wrote a TL;DR; `stale` reports it against the current parse |
| `abstract` | nobody did, so the authors' own abstract stands in; never stale |
| `none` | nobody did, and this paper has no abstract ("abstract not available") |
| `unknown` | nobody did, and there is no passage sidecar, so nothing can tell; a re-parse with `[parser].backend = "docling"` fixes it |

### 🖼 `chitragupta draft figures`

One paper's figures: caption, page, the exact string to cite each by,
and the path to the crop, so a drafting session can look at a figure
while grounding a claim about it.

```bash
chitragupta draft figures smith2024
chitragupta draft figures smith2024 --json
```

| Command | Does | Exit |
| --- | --- | --- |
| `<citekey> [--json]` | list that paper's figures | 1 if the citekey isn't in the ledger, or its figure index names an image outside `content/docling/`; **0** otherwise |

**Consider, never replicate.** Having a paper in your library grants no
right to reproduce its figures; the `cite` string is what belongs in a
draft.

| What you see | Means |
| --- | --- |
| a list of figures | that paper's figures, from its docling parse |
| `no figures recorded in its docling parse` | the paper has none |
| `no figure index for <citekey> …` | the docling stage has not run for it; run `chitragupta enrich --stages docling`, with `[enrich].docling_images` on |

It reads `content/docling/<citekey>.figures.json` as a path, never by
importing the enrichment layer.
[CONFIG.md](CONFIG.md#-docling_images) says what the index excludes.

### 🔀 `chitragupta draft diff`

What changed in a draft since a snapshot of it. The baseline is the
latest snapshot (`dossier mark-revision` takes one each pass), or
`--against` a snapshot number, label, or any file. The output is a
review copy: never gated, never a deliverable, never a source.
[DRAFT-ITERATION.md](DRAFT-ITERATION.md#-reviewing-a-revision) has how
to use it.

```bash
chitragupta draft diff content/drafts/survey.md
chitragupta draft diff content/drafts/survey.md --against "sent to supervisor" --format pdf
chitragupta draft diff content/drafts/survey.md --against 2 --json
```

| Flag | Default | What it does |
| --- | --- | --- |
| `<draft>` | required | The draft, under `content/drafts/` |
| `--against REF` | the latest snapshot | A snapshot number (`2`, `002`), a snapshot label, or a path. A path wins when it exists as a file; a file with no `figures/` beside it leaves the figures uncompared |
| `--format md\|pdf` | `md` | `md` writes the change report; `pdf` also writes a redline, built with latexdiff from both versions rendered with their citations deferred |
| `--json` | off | Print the report as JSON instead of Markdown. Both files are written either way |

The report lists sections added, removed, moved or changed (each with
the `revisions.md` entries naming it), citekeys added and dropped,
figures changed, and any changed section no log entry explains. A
changed References section is listed as `regenerated`. It is written to
`content/review/<topic>/<stem>.diff.{md,json}` before any PDF work;
`pdf` adds `<stem>.diff.tex` and `<stem>.diff.pdf`. A baseline citation
that is no longer citable becomes `(citation withdrawn)` in the
redline.

| Situation | Exit |
| --- | --- |
| Report written, including `No changes.` (no PDF then, and an older redline is removed) | 0 |
| No snapshot yet, an unknown `--against`, a `.md` draft against a `.tex` baseline, or a draft outside `content/drafts/` | 1 |
| Either version cites a key and there is no ledger yet (before the first `corpus sync`). A draft citing nothing is diffed without one, as `draft render` renders it | 1, naming the sync to run |
| `--format pdf` without latexdiff, LuaLaTeX or bibtexu, a side the gate refuses, or a redline that does not compile after one retry | 1, the report already written |

Each refusal is reported on stderr as an `[error]` line.

### 🗺 `chitragupta review agenda`

One ranked, deduplicated worklist merged across the other eight aids'
`.json`, `chitragupta.draft style --json`'s prose findings, and the
dossier's drift report. Advisory, not a gate. In its bare form it
**reads, never runs, an aid**: an aid's `.json` that does not exist yet
is named as absent in the header. Each item carries a `class`, a
section anchor, and whether it is `unattended` (safe for an automated
pass) or surfaced for a person. [AGENDA.md](AGENDA.md) walks through an
agenda file section by section, including the JSON sibling, and
[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md) has the item classes.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<draft>` | required | The Markdown draft to check |
| `--formats FORMATS` | `md,tex,pdf` | Extra formats beside the Markdown report, which is always written; `tex` needs `pandoc`, `pdf` also LuaLaTeX |
| `--json` | off | Print the worklist as JSON instead of just the written-files summary. The `.json` sibling is filed either way |
| `--accept ID` | unset | Record this item id as considered and accepted, keeping it off the worklist while the finding's identity is unchanged. Repeatable. Only `claim-support`, `uncited-claim` and `unsupported-claim` may be accepted; every other class is refused with exit code 2 |
| `--baseline PATH` | unset | Re-run the eight aids at `--formats md`, rebuild, and report `resolved`/`persisting`/`new`/`accepted` against the agenda `.json` at `PATH`, with the objective count before and after. **The one mode that runs another aid** (the bare command above never does), so it costs seconds rather than milliseconds |

```bash
chitragupta review agenda content/drafts/survey.md
# chitragupta review agenda content/drafts/survey.md --formats md
# chitragupta review agenda content/drafts/survey.md --json > agenda.json
# chitragupta review agenda content/drafts/survey.md --accept 3f2a91c40b7e
# chitragupta review agenda content/drafts/survey.md \
#     --baseline content/review/survey.agenda.json --json
```

`--accept` stores identities only, in
`content/review/<topic>/<stem>.accepted.json`; an edit to the span
raises a new id and the item returns by itself. Defect classes cannot
be accepted, `misquoted` included;
[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md) has why. Under `--baseline
--json`, stdout carries the comparison payload, not the worklist.
`--baseline` needs a ledger: with none it exits 1 having changed
nothing; a bad baseline exits 2. The `.md` and `.json` are filed on
every run (there is no `--write`).

### 📐 `chitragupta review figure`

What a draft's TikZ figures' own geometry says about them.
**Informational, not a gate**: it exits 0 whatever it finds. It reads
the same geometry as [`figure check`](#-chitragupta-figure-check) over
every figure the draft references, and keeps its own report.
[figure-checks/README.md](figure-checks/README.md) has the rules and
how to read a report. Without `tikz.sty` it still runs the static
checks and says the geometry was skipped; a figure that does not
compile is a finding on that figure.

#### 📏 It measures; it never places

**Nothing here computes where a node should go.** TikZ does the layout,
and this reads back the boxes TikZ decided. Fix a finding by changing
what you asked TikZ for (a `sibling distance`, a `row sep`), not by
nudging a coordinate until the number moves; when a finding and your
own eyes disagree, the eyes win ([TIKZ-STYLE.md](TIKZ-STYLE.md)). A
picture that names no nodes reports `nothing-measurable` rather than a
clean result, so name the nodes you draw. The edge list is recovered
from the source; confirming it against the prose is the author's job.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<draft>` | required | The draft whose figures to check |
| `--json` | off | Print the findings as JSON; `--write` files the `.json` either way |
| `--write` | off | Also file the report under `content/review/`, mirroring the draft's path |
| `--formats FORMATS` | `md,tex,pdf` | With `--write`, extra formats beside the Markdown report, which is always written |

```bash
chitragupta review figure content/drafts/<topic>/survey.md
# ... --write
# ... --json > figure.json
```

### 📊 `chitragupta review coverage`

How much of what retrieval surfaced made it into a draft's citations.
**Informational, not a gate.** Stdlib-only. A written report records
the whole invocation, queries included, since a coverage figure means
nothing without knowing 62% *of what*.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<draft>` | required | The draft to check |
| `--query QUERY` | required, repeatable | A retrieval query to check coverage against. Give it more than once |
| `--k K` | `5` | Top-k results per query |
| `--json` | off | Print the findings as JSON; `--write` files the `.json` either way |
| `--write` | off | Also file the report under `content/review/`, mirroring the draft's path |
| `--formats FORMATS` | `md,tex,pdf` | With `--write`, extra formats beside the Markdown report, which is always written; `tex` needs `pandoc`, `pdf` also LuaLaTeX |

```bash
chitragupta review coverage content/drafts/survey.md \
    --query "digital twin composability" \
    --query "runtime verification"
# ... --k 10
# ... --write --formats md
# ... --json > coverage.json
```

**`--json`**: the shared envelope plus `queries`, `k`, `coverage_pct`,
`candidates_total`, `cited_candidates_total`, and one `findings` object
per itemised citekey (`id`, `citekey`, `title`, `status`:
`uncited_candidates` or `cited_outside_candidates`). With
`[retrieval].spelling_correction` on, a `corrections` object maps each
corrected query to what was added; both reports list them too. The key
is absent when nothing was corrected.

### 📖 `chitragupta review provenance`

Reports what in each cited source supports the claim citing it,
quoting a real passage. Advisory, not a gate. Like `agenda`, it writes
by default, to `content/review/<topic>/<stem>.provenance.md` with its
`.tex`/`.pdf` renders and `.json` sibling, whether or not `--json` is
given.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<draft>` | required | The Markdown draft to check |
| `--formats FORMATS` | `md,tex,pdf` | Extra formats beside the Markdown report, which is always written; `tex` needs `pandoc`, `pdf` also LuaLaTeX |
| `--json` | off | Print the findings as JSON instead of just the written-files summary. The `.json` sibling is filed either way |

```bash
chitragupta review provenance content/drafts/survey.md
# chitragupta review provenance content/drafts/survey.md --formats md
# chitragupta review provenance content/drafts/survey.md --formats md,tex,pdf
# chitragupta review provenance content/drafts/survey.md --json > provenance.json
```

**`--json`**: the shared envelope plus one `findings` object per citing
sentence, worst match first: `id`, `line`, `citekey`, `claim`, `score`,
`band`, `passage` (`page`/`quotable`/`text`, or `null`) and `note`.
With `--json`, the written-files summary moves to stderr.

### 🔬 `chitragupta review support`

Does the cited source entail the claim citing it? Scored with an NLI
entailment model rather than [`provenance`](#-chitragupta-review-provenance)'s
lexical overlap, and ranked rather than banded. **Advisory, exits 0
whatever it finds.** Needs the `enrich` extra; without it, it prints a
notice on stderr and still exits 0.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<draft>` | required | The draft to check |
| `--json` | off | Print the findings as JSON; `--write` files the `.json` either way |
| `--write` | off | Also file the report under `content/review/`, mirroring the draft's path |
| `--formats FORMATS` | `md,tex,pdf` | With `--write`, extra formats beside the Markdown report; `tex` needs `pandoc`, `pdf` also LuaLaTeX |

```bash
chitragupta review support content/drafts/survey.md
# ... --write --formats md
# ... --json > support.json
```

**`--json`**: the shared envelope plus `scored`, `unscoreable`, and one
`findings` object per citation (`id`, `line`, `citekey`, `claim`,
`score`, `note`). `scored` counts findings; `unscoreable` counts
citekeys with no passage to score against, either because no passage
has readable text or because every readable one is a section heading.
Headings are excluded from the premises because a heading asserts
nothing.

### 🧾 `chitragupta review union`

Does an assembled book still carry every citekey its accepted units stand on?
The one aid that reads a **book**. **Advisory, exits 0 whatever it finds.**
Stdlib-only set arithmetic over the assembly's resolved includes. A *dropped*
finding is an accepted unit the assembly never includes; an *appeared* finding
is a citekey in an included file no unit owns. It refuses, with exit 1, a path
in no book and a path that is one of the book's own units.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<draft>` | required | The assembled document, e.g. `content/rendered/<book>/book.tex` |
| `--json` | off | Print the findings as JSON; `--write` files the `.json` either way |
| `--write` | off | Also file the report under `content/review/`, mirroring the book's path |
| `--formats FORMATS` | `md,tex,pdf` | With `--write`, extra formats beside the Markdown report; `tex` needs `pandoc`, `pdf` also LuaLaTeX |

```bash
chitragupta review union content/rendered/twins/book.tex
# ... --write --formats md
# ... --json > union.json
```

**`--json`**: the shared envelope plus `units_checked`,
`units_unchecked`, `units_omitted`, `includes_outside_units`,
`includes_unresolved`, `citekeys_outside_units`,
`appeared_determinable`, and one `findings` object per citekey (`id`,
`citekey`, `status`, `units`). **Read `appeared_determinable` before
trusting an empty `appeared`**: while any unit is unwritten, unaccepted
or edited since acceptance, that direction is withheld and the field is
`false`. `includes_unresolved` lists includes that could not be opened,
so a report with entries there covers less than it appears to.

### 🧩 `chitragupta review synthesis`

How many sources each unit of a draft rests on, at the unit its genre
binds at ([WRITING-STANDARDS.md](WRITING-STANDARDS.md) §11). **Advisory,
exits 0 whatever it finds.** The unit comes from the genre in the
dossier's `scope.md`:

| Genre | Unit |
| --- | --- |
| `survey`, `thesis-chapter`, `deep-research`, `research-paper` | paragraph |
| `textbook-chapter` | section: its paragraphs are free to be single-source, its *consecutive* paragraphs are not free to be the same single source |
| `tutorial` | document: the body carries no citations by design, so the floor is on the lesson's derivation |

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<draft>` | required | The draft to check |
| `--unit {paragraph,section,document}` | from `scope.md` | Measure at this unit instead. For a draft with no dossier, or to look at one deliberately at another scale |
| `--json` | off | Print the findings as JSON; `--write` files the `.json` either way |
| `--write` | off | Also file the report under `content/review/`, mirroring the draft's path |
| `--formats FORMATS` | `md,tex,pdf` | With `--write`, extra formats beside the Markdown report; `tex` needs `pandoc`, `pdf` also LuaLaTeX |

```bash
chitragupta review synthesis content/drafts/survey.md
# ... --unit section          # a draft whose dossier records no genre
# ... --write --formats md
# ... --json > synthesis.json
```

The report gives **spread** (distinct citekeys per unit) and, for a
section, the **longest run of paragraphs on one citekey**. It counts
and does not judge: no threshold, nothing acts on it unattended. A
marker directly above a unit (no blank line) declares it deliberately
single-source:

```markdown
<!-- single-source: Foo2019 is the only paper in the corpus covering X -->
```

```latex
% single-source: Foo2019 is the only paper in the corpus covering X
```

**`--json`**: the shared envelope plus `genre`, `unit`, `unit_source`,
`units_total`, `uncited`, `single_source`, `multi_source`, `declared`,
`undeclared`, `single_source_pct`, and one `findings` object per
itemised unit (`id`, `kind`, `line`, `unit`, `citekeys`, `declared`,
`longest_run`).

### 🔍 `chitragupta review uncited`

Which sentences of a draft carry **no citation at all**.
**Advisory, exits 0 whatever it finds.** It reads only the draft.
Headings, captions, references, comments and code are excluded; table
*rows* are not, since a citekey in backticks is not a citation.

| Genre | Uncited prose is | Findings |
| --- | --- | --- |
| `survey`, `thesis-chapter`, `deep-research` | exceptional | one per uncited sentence |
| `textbook-chapter`, `tutorial`, `research-paper` | ordinary: most prose is original by design, per [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §11 | none. The counts are still reported |
| not recorded in `scope.md` | exceptional | raised, and the report says the genre was not recorded |

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<draft>` | required | The draft to check |
| `--genre {deep-research,digest,research-paper,survey,textbook-chapter,thesis-chapter,tutorial}` | from `scope.md` | Read the draft under this genre instead. For a draft with no dossier, or to read one strictly on purpose |
| `--json` | off | Print the findings as JSON; `--write` files the `.json` either way |
| `--write` | off | Also file the report under `content/review/`, mirroring the draft's path |
| `--formats FORMATS` | `md,tex,pdf` | With `--write`, extra formats beside the Markdown report; `tex` needs `pandoc`, `pdf` also LuaLaTeX |

```bash
chitragupta review uncited content/drafts/survey.md
# ... --genre survey          # a draft whose dossier records no genre
# ... --write --formats md
# ... --json > uncited.json
```

Nothing repairs these findings for you: the fix for an uncited claim is
evidence, and rewording one would make it look supported without making
it supported.

**`--json`**: the shared envelope plus `genre`, `genre_source`,
`standing`, `sentences_total`, `uncited`, `bare`, and one `findings`
object per uncited sentence (`id`, `line`, `sentence`, `block_cites`).

### 📖 `chitragupta review quotation`

Does each **quoted span** in a draft's dossier appear in the source it
is attributed to? A misattributed quotation is the one part of the
fabricated-citekey failure class
[`chitragupta draft gate`](#-chitragupta-draft-gate) cannot see,
because the citekey *is* real. **Advisory, exits 0 whatever it finds.**
It checks exactly the `quote:` fields
[`draft evidence`](#-chitragupta-draft-evidence) would print, never a
legacy `support:` block. A block with several quotes has each checked
on its own, and the report names it as `quote N of M`.

| Outcome | Means | A finding? |
| --- | --- | --- |
| found | The span is in the source. The report gives the page and the tier that matched | no |
| absent | It is not, and the source *was* readable in reading order. Carries the page its distinctive words concentrate on, so you can tell a fabrication from an edited quotation | **yes** |
| not checkable | The source has no reading-ordered passages, only `pdftotext -layout` text, whose column splicing makes a correct quotation non-contiguous. Reporting it absent would accuse a draft of something it did not do | no |

Matching is exact over a normalised `[a-z0-9]` stream, with elided
fragments required **in order**; there is no similarity score. The
report's `- Universe:` line is `no-dossier`, `no-quotes` or `checked`;
only `checked` means a quote was looked at.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<draft>` | required | The draft to check |
| `--json` | off | Print the verdicts as JSON; `--write` files the `.json` either way |
| `--write` | off | Also file the report under `content/review/`, mirroring the draft's path |
| `--formats FORMATS` | `md,tex,pdf` | With `--write`, extra formats beside the Markdown report; `tex` needs `pandoc`, `pdf` also LuaLaTeX |

```bash
chitragupta review quotation content/drafts/survey.md
# ... --write --formats md
# ... --json > quotation.json
```

**`--json`**: the shared envelope plus `universe`, `quotes_total`,
`found`, `absent`, `unverifiable`, a `quotes` object per checked span
(`id`, `citekey`, `verdict`, `tier`, `pages`, `reason`, `index`, `of`)
and a `findings` object per absent one (`id`, `citekey`, `quote`,
`near_miss_page`, `near_miss_score`, `index`, `of`). `index` is the
quote's place among its block's `quote:` lines and `of` their count,
an identical repeat counted once;
`quotes_total` counts quotes, not sources. `tier` is `exact`, `exact-pair`,
`elided` or `elided-pair`.

### 📋 `chitragupta review digest`

How much of a **verbatim digest** is not the sources' own words, and
what every such sentence is. [VERBATIM-DIGEST.md](VERBATIM-DIGEST.md)
explains digests, the report's fractions and classes, page notes, and
the repair loop. It uses [`review quotation`](#-chitragupta-review-quotation)'s
matcher, so it needs the Docling sidecars `chitragupta enrich --stages
docling` writes; a source without one is reported as not checkable.
**Advisory, exits 0 whatever it finds.** Any draft can be given to it;
one that is not a digest simply reports most of its prose as not
copied. Its finding classes are `unsupported-text`, `copy-mismatch`,
`dangling-reference`, `repeated-text` and `unquoted-text`, each item
`[surfaced]`. The report and its `.json` are filed on every run,
because the `.json` is the next pass's baseline.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `<draft>` | required | The digest to check |
| `--formats FORMATS` | `md,tex,pdf` | Extra formats beside the Markdown report; the `.md` and `.json` are always written. `tex` needs `pandoc`, `pdf` also LuaLaTeX |
| `--json` | off | Print the payload (or, with `--baseline`, the comparison) as JSON instead of the summary |
| `--baseline PATH` | -- | Compare this run against a previously filed `<stem>.digest.json`: resolved, persisting and new items, counts and fractions before and after, and whether unsupported text fell |

```bash
chitragupta review digest content/drafts/<topic>/notes.md --formats md
chitragupta review digest content/drafts/<topic>/notes.md --json > digest.json
chitragupta review digest content/drafts/<topic>/notes.md \
    --baseline content/review/<topic>/notes.digest.json
```

**`--json`**: the shared envelope plus the three fractions
(`unsupported_fraction`, `copied_fraction`, `unverifiable_fraction`),
word counts, a `counts` object per class, an `items` list, a `spans`
list per copied span and an `unverifiable` list. Under `--baseline` the
printed payload carries `resolved`, `persisting`, `new`, the before and
after counts and fractions, and `fell`; the filed `.json` is always the
bare report.

### 📋 `chitragupta review verbatim`

Verbatim overlap with one cited source, a whole-draft x whole-corpus
scan, a re-scan against a recorded one, and page location for a
phrase. Stdlib-only; `locate` uses `pdftotext` when present and falls
back to `content/parsed/` (page-level) without it. Run with no
arguments to print its usage.

[PLAGIARISM.md](PLAGIARISM.md) covers what each tier catches and
misses, severity buckets, cost, the `--json` fields, repair, and
[how the tiers were chosen](PLAGIARISM.md#-how-the-tiers-were-chosen).

| Subcommand | Arguments | What it does |
| --- | --- | --- |
| `overlap` | `<draft> <citekey> [--n N]` | Longest verbatim word-n-gram runs shared between the draft's sentences citing `<citekey>` and that source's parsed text. `--n` defaults to `8` |
| `scan` | `<draft> [--min-run N] [--gap N] [--limit N] [--json] [--write] [--formats F]` | Slides the whole draft across the whole corpus index, catching reuse `overlap` cannot: an uncited source, or prose that cites nothing. `--min-run` (default `8`) is the reporting length floor; `--gap` (default `1`) tolerates that many non-matching words inside a run; `--limit` caps how many findings print (default all). `--json`, `--write` and `--formats` (default `md,tex,pdf`) as for the other aids |
| `recheck` | `<draft> --baseline PATH [--json]` | Re-scans the draft and compares it against a payload `scan --write` filed earlier, reporting each finding as resolved, persisting or new plus the change in the objective count. `--baseline` is required and its `--min-run`/`--gap` are reused, so the two scans are comparable. Prints only; there is no `--write` |
| `locate` | `<citekey> "<phrase>" [more...]` | Which PDF page each phrase (or its distinctive words) appears on |

**Exit codes**, shared with the other ten review aids. `0` on every
successful invocation, findings or not: these are advisory, never a
gate. That includes `recheck`: a draft that got worse still exits 0.
`1` is a draft this layer will not read, because it is missing or
resolves outside `content/`. `2` is a malformed invocation; `recheck`
also uses `2` for a baseline it cannot compare against.

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

**A clean scan is not a clean bill of health.** The exact tier cannot
see a substituted word, the skip-gram tier cannot see restatement, and
the embedding tier runs only where the enrichment layer, the Docling
sidecars and the draft's dossier are all present. Read a clean run as
"nothing found by the tiers that ran"; every form of the output names
any tier that did not run, and why (`tiers_not_run` in `--json`). Both
paraphrase tiers are advisory only; treat skip-gram findings with
*more* scrutiny than exact ones.

**`--json`** serialises what `scan` computed, never recomputing; a
clean draft emits `"findings": []` and exits 0. `start` is a word
offset into the normalised word stream, not a character offset or line
number; `line`, `char_start`, `char_end` and `draft_text` index the
draft as written, from the first matched word to the last, interior
punctuation included and a trailing period excluded, so `draft_text`
can be used as an `Edit` `old_string`. `id` is a digest of
`(citekey, page, fragment)`, not of position, so it survives the repair
of another finding. `--write` files the same bytes as
`content/review/<topic>/<stem>.verbatim.json`, with no timestamp; with
both flags, the written-files summary goes to stderr.
[PLAGIARISM.md](PLAGIARISM.md#-repairing-what-the-scan-found) has every
field.

**`recheck`** reports `resolved`, `persisting`, `new`, and the change
in the objective count (the `long` and `short` buckets, excluding a
quoted-and-cited run and every `embedding` finding). Read `new` as well
as the delta: one finding resolved and another introduced leaves the
delta at 0. The floor comes from the baseline, never a flag. It refuses
(exit 2, naming the remedy) a baseline it cannot compare against:
another aid's payload, one written under `--limit`, one missing a
field, one from a different `major.minor` release, or one that is not
JSON. There is no `--write`: a comparison is stale the next time the
draft is touched. The `agenda-reviser` skill
([GENRE.md](GENRE.md#-working-the-agenda-agenda-reviser)) is the
intended caller.

**The disk cache.** The first `scan` builds a corpus-wide index under
`content/overlap/` (about 27s over a 497-document corpus); later scans
over an unchanged corpus are sub-second, and a changed document is
re-fingerprinted alone. Delete the directory and the next run rebuilds
it. `scan` also honours a per-host, gitignored
`content/verbatim_allowlist.toml`
([PLAGIARISM.md](PLAGIARISM.md#-the-boilerplate-allowlist)).

`locate` numbers pages by form feeds. Under `docling`, a page with no
extracted text shifts the numbering after it; where the two disagree,
believe `chitragupta review provenance`.

### 🎨 `chitragupta figure sync`

Keeps the house figure-style block
([TIKZ-STYLE.md](TIKZ-STYLE.md#-the-house-figure-style)) current inside
every figure file. Each figure file carries its own copy between two
marker comments, so it compiles under `\usepackage{tikz}` alone.

```bash
chitragupta figure sync                       # every content/drafts/**/figures/*.tex
chitragupta figure sync content/drafts/twin   # a directory: every figures/*.tex beneath it
chitragupta figure sync --check assets/tikz/*.tex   # files as named; report only
```

A directory contributes only the `*.tex` files directly inside a
`figures/` directory beneath it, so a draft's own `.tex` is never
stamped. A file named on the command line is taken as given.

| What it finds | What it does |
| --- | --- |
| no block | stamps one above the first `\usetikzlibrary` or `tikzpicture` line (`stamped`) |
| a block this project released earlier | replaces it with the installed one (`refreshed`) |
| the installed block | nothing (`current`) |
| a block that matches no release: edited, or stamped by a newer chitragupta | leaves it alone and prints the diff (`modified`) |
| markers unpaired or repeated | leaves it alone (`malformed`) |
| no picture to stamp above, a symlink, not UTF-8, read-only or unwritable | reports it and carries on (`no-picture`, `skipped`) |

Everything outside the markers is left byte for byte, and a second run
changes nothing.

| Flag | Exit |
| --- | --- |
| *(none)* | **0** whatever it found; it is an aid |
| `--check` | writes nothing; **1** if any file is not current, else 0 |
| either | **2** on a usage error, or when the installed block or its version register cannot be read (`chitragupta doctor`) |

`chitragupta draft render` reports a stale or missing block as a
`[figure]` warning naming this command, and renders anyway. In a
developer checkout, `git-hooks/pre-commit` runs `--check` on staged
figure files without blocking the commit ([HOOKS.md](HOOKS.md)).

### 🔎 `chitragupta figure check`

Reports every rule one figure file breaks, by rule id, and every
deliberate exception the file records. One compile, in the render's
fonts at 12pt with the figure's TikZ libraries loaded. The
`figure-drawer` skill runs this as its geometry step.
[figure-checks/README.md](figure-checks/README.md) has every rule, the
`% cg-allow:` form, and how to read the report.

```bash
chitragupta figure check content/drafts/rag/figures/flow.tex
chitragupta figure check figures/flow.tex --width 345    # a narrower target, in pt
chitragupta figure check figures/flow.tex --layout map   # read sizes against another layout
chitragupta figure check figures/flow.tex --json
```

| Flag | Default | What it does |
| --- | --- | --- |
| `--page article\|book` | `book` for a figure under a book's drafts directory (one with a `content/specs/<book>/spec.md`), else `article` | The page to check against. `article` is `draft render`'s page, 453pt by 700.5pt; `book` is `book-assembler`'s, 437.5pt by 685pt. Its text width is `size-width`'s target, and its text height is what `size-height` reports a share of. The report's second line names the page and why it was chosen |
| `--width PT` | the page's text width | Target text width in pt for `size-width`, overriding the page's alone: the height stays the page's |
| `--layout NAME` | the figure's `% cg-layout:` line | Read the advisory size reports against this layout's reference ranges. One of the layouts with a file under `.claude/skills/figure-drawer/references/layouts/`; any other name is a usage error |
| `--json` | off | The same report as JSON: `width_pt`, `page` (`name`, `text_width_pt`, `text_height_pt`, `why`), `layout` (or `null`), `findings` and `advisory` (each with `rule`, `class`, `scope`, `target`, `measurement`), `allowed` (each with the `measurement` it set aside), `stale` and `unchecked` (each with `why`), `malformed`, `not_measured` and `diagnostics` |

| Exit | When |
| --- | --- |
| **0** | after any run, whatever it found; it is an aid |
| **2** | a usage error, a path that is not a readable file, or no `lualatex` or `tikz.sty` on the host. It then checks nothing rather than report the source-only rules, whose silence would read as a clean figure (`chitragupta doctor`) |

### 🌱 `chitragupta figure new`

Starts a figure from a layout's scaffold in `assets/tikz/`: copies it
to `<figures-dir>/<name>.tex`, copies the layout's ASCII twin to
`<name>.txt`, and runs [`figure sync`](#-chitragupta-figure-sync) on the
copy. It never overwrites: an existing `<name>.tex` or `<name>.txt`, or
a symlink at either, is refused and nothing is written. The
`figure-drawer` skill starts every figure with it.

```bash
chitragupta figure new content/drafts/rag/figures flow --layout zoned-spine
```

```text
created  content/drafts/rag/figures/flow.tex   (from zoned-spine)
created  content/drafts/rag/figures/flow.txt   (from zoned-spine)
figure sync: 1 current
```

| Argument | What it is |
| --- | --- |
| `<figures-dir>` | A directory named `figures`, the name `figure sync`'s walk and the render's markers look in. Created if its parent exists |
| `<name>` | The figure's file stem: no path, no suffix |
| `--layout ID` | A scaffold whose own `% cg-layout:` line names its file stem: `branching-tree`, `comparison`, `control-loop`, `hub-and-spoke-network`, `layered-stack`, `map`, `pipeline`, `sequence`, `state-machine`, `timeline` or `zoned-spine` |

| Exit | When |
| --- | --- |
| **0** | the figure was written |
| **2** | a refusal (a name with a path in it, a directory not named `figures`, an unknown layout, a file already there), or an installed scaffold or house block that cannot be read (`chitragupta doctor`). Nothing is written |

### 👁 `chitragupta figure look`

Shows one figure as it will print, alone on its page in the render's
fonts (the page `figure check` picks), for the defects no rule
measures: a badly wrapped label, an arrow through a zone title. It
writes:

| File | What it is |
| --- | --- |
| `<name>.look.pdf` | The page, cropped to the figure plus 10pt (so the soft shadow survives). A figure wider than the text width gets a red line at the text width |
| `<name>.look.png` | That page at 300 dpi, never scaled |
| `<name>.look.json` | A digest of what the look was built from, and what was measured |
| `<name>.page.png` | With `--draft`: the draft's page that holds the figure, at 300 dpi |

They go under `content/rendered/`, mirroring the figure's place under
`content/drafts/`, or into `--output-dir DIR`, which a figure outside
`content/drafts/` requires. An unchanged figure is not recompiled.

```bash
chitragupta figure look content/drafts/rag/figures/flow.tex
chitragupta figure look content/drafts/rag/figures/flow.tex --draft content/drafts/rag/survey.md
chitragupta figure look ~/scratch/figures/flow.tex --output-dir content/scratch
```

```text
wrote    content/rendered/rag/survey.pdf
current  content/rendered/rag/figures/flow.look.pdf   (336 x 114pt; text width 453pt)
current  content/rendered/rag/figures/flow.look.png   (1488 x 567 px at 300 dpi)
wrote    content/rendered/rag/figures/flow.page.png   (page 1 of survey.pdf; 2481 x 3508 px)
```

With `--draft` it renders the draft as
[`draft render`](#-chitragupta-draft-render) does and finds the
figure's page from an invisible PDF destination (`cgfig:<marker
base>`); a `.tex` draft's figures get no page picture. A figure that
does not compile prints TeX's first error, and its old look files are
deleted.

| Flag | Default | What it does |
| --- | --- | --- |
| `--draft DRAFT` | none | Also render this draft and write `<name>.page.png` |
| `--output-dir DIR` | mirrored | Write the look (and with `--draft`, the render) here instead of `content/rendered/<mirrored path>`; required for a figure outside `content/drafts/`; confined to `content/` |

| Exit | When |
| --- | --- |
| **0** | after any look, a figure that does not compile and a draft that does not render included |
| **2** | a figure that is not a readable UTF-8 file, no `lualatex`, `tikz.sty` or `pdftoppm` (or `pandoc`, with `--draft`), a rendered directory or `--output-dir` that resolves outside the content directory, or a figure outside `content/drafts/` with no `--output-dir`. Nothing is written (`chitragupta doctor`) |

### 🧠 `chitragupta enrich`

Orchestrates the enrichment layer: docling -> embeddings/Chroma ->
BERTopic -> declared keywords -> seed topics -> converge -> topic
graph. **Needs the venv.** Each stage probes its own prerequisites and
reports `ok`, `partial`, `skipped` or `error`, so `skipped` on a machine
without the enrich extra is a correct answer.

| Flag | Default | What it does |
| --- | --- | --- |
| `-h`, `--help` | -- | Show help and exit |
| `--target {host,docker}` | `host` | **Informational only**: stages self-probe regardless |
| `--stages STAGES` | all seven, or `docling` alone with `--for-draft` | Comma-separated subset of `docling,embed,bertopic,extract-keywords,seed-topics,converge,topic-graph` |
| `--for-draft PATH` | -- | Scope `docling` to the papers this draft cites. Refused with an explicit `--stages embed`, `bertopic`, `extract-keywords`, `seed-topics`, `converge` or `topic-graph` |

**Exit code**, which is all a schedule can read: `1` when any stage
reports `error` or there is no ledger, `2` when another run holds the
lock (as for `sync`), `3` when `--for-draft` is refused, `0` otherwise,
including `partial` and `skipped`. A `docling` run that gave up on
documents through a repeatedly-dying worker pool reports `error`, so
it exits `1`.

```bash
chitragupta enrich
# chitragupta enrich --stages docling
# chitragupta enrich --stages embed,bertopic
# chitragupta enrich --stages extract-keywords   # writes content/keywords.toml
# chitragupta enrich --stages seed-topics   # skipped with no content/seed_topics.toml
# chitragupta enrich --for-draft content/drafts/digital-twins.md
```

The `embed` stage prints one line per document (`embedded`,
`unchanged` or `no text to embed`) and a closing total. Ctrl+C is
safe: every chunk upserted so far is kept, and a re-run picks up from
there.

#### 📚 Enriching one draft's papers

`--for-draft` narrows `docling` from the whole corpus to the papers one
draft cites, read with the citation gate's own
`chitragupta.citation_gate.extract_citekeys`, so a draft resting on
twenty-three papers costs twenty-three parses:

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

Follow it with `chitragupta review provenance <draft>`, a tier-1
command needing no venv and no lock. The other six stages refuse the
scope (exit 3) and name the two commands to run instead, because each
builds one whole-corpus artefact and a partial one is indistinguishable
from a complete one ([LADDERS.md](LADDERS.md)). A cited citekey the
ledger has never heard of is named, and a scope matching nothing stops.
The Docling cache is per-document, so scoped and full runs never parse
a document twice.

### 🔧 `scripts/install_full_pipeline.sh`

One install path for both a bare machine and the Docker image. Takes
**stage names as positional arguments**, not flags.

| Stage | What it does |
| --- | --- |
| `python-deps` | **Default when no stage is given.** Creates the venv and runs `poetry install --with enrich`. `chitragupta install` refuses it, naming `chitragupta install enrich` |
| `os-deps` | `apt-get` the system packages (TeX Live with LuaLaTeX, the render's fonts, Pandoc, poppler-utils, Poetry, git/curl/unzip, OpenCV's runtime libraries ([PDF-PARSER.md](PDF-PARSER.md#-docling-fails-every-document-with-an-opencv-recursion-error)), and `python-is-python3`, which puts the hooks' `python` on `PATH`), plus STIX Two. Needs root; auto-sudo's. Opt-in. Also `chitragupta install os-deps` |
| `dev-deps` | `poetry install --with dev` into the same venv, plus the pinned `actionlint` and `core.hooksPath` pointed at `git-hooks/`. For running the tests and committing; run `python-deps` first. Pip equivalent: `pip install 'chitragupta-cli[dev]'` |
| `cpu-torch` | Swaps torch to the CPU-only wheel and removes the CUDA runtime. Never part of `all`: it asserts a GPU is absent *for good*, which the script cannot infer |
| `gpu-torch` | Runs `ensure_gpu_torch` (below) against `CHITRAGUPTA_PYTHON` rather than the script's venv; what `chitragupta install gpu-torch` reaches |
| `actionlint` | Installs the pinned workflow linter alone, without the venv `dev-deps` also builds |
| `vale` | Installs Vale alone, without the rest of `os-deps` |
| `stix-two` | Installs the pinned STIX Two font alone, for a host whose TeX Live and Noto fonts came from somewhere else |
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

`python-deps` and `dev-deps` also run `ensure_gpu_torch`, which
reinstalls torch from a wheel index matching the NVIDIA driver if the
default one would silently run CPU-only. It is idempotent and prints
what it decided.

**Poetry is a prerequisite, not something `python-deps` installs.** It
is in the `os-deps` package list, so `all` covers it; run on its own,
`python-deps` needs `pipx install poetry` first. Each stage ends by
printing the interpreter path to use afterwards.

### 📦 `scripts/release.py`

Builds the release archive under `release/`. A maintainer tool.
**Takes no arguments and parses none**, including `-h`/`--help`, which
it ignores while building the archive anyway:

```bash
python3 scripts/release.py
```

`tests/`, `bench/`, `plans/`, `.github/`, `.gitignore` and a few
root-level tooling files are excluded (`EXCLUDE_TOP_LEVEL`). Every
prose document ships: `docs/`, `README.md`, `SOUL.md`, `AGENTS.md`,
`DEVELOPER-AGENTS.md` and `DEVELOPER.md`, plus `.claude/`, `.agents/`,
`.codex/` and `.opencode/`.

## ⏰ Running sync on a schedule

`python -m chitragupta.corpus sync` is deterministic, idempotent, and
takes its own write lock (`chitragupta.runlock`), so it is safe to run
unattended. An unattended caller branches on exit codes and checks
`logs/pipeline.log` afterwards (rotated; see `[logging]` in
`config.toml.example`).

`chitragupta enrich` writes to the same file. Each line names its source
module (`sync` logs as `chitragupta.sync` whatever the command that
started it is spelled), so either layer can be narrowed back out:

```bash
grep 'chitragupta\.sync' logs/pipeline.log      # just the corpus layer
grep 'chitragupta\.enrich' logs/pipeline.log    # just the enrichment layer
```

**Don't hand-roll a log redirect**: the log carries the warnings,
progress and summary. Only three rare messages stay terminal-only by
design: a docling worker's GPU-OOM fallback, the Ctrl+C notice, and the
lock refusal (the losing side of a race must not touch the winner's
file).

**Exit codes are the API**, not the printed text:

| Exit code | Meaning | What an unattended caller should do |
| --- | --- | --- |
| `0` | Clean: everything that needed parsing, parsed | Nothing |
| `1` | **Documents this host could not parse**: the conditions [`corpus sync`](#-chitragupta-corpus-sync) lists under code 1, deliberately neither restated nor counted here | Alert; `logs/pipeline.log`'s FAILED/WARNING lines name which citekey and why |
| `2` | Another run already holds the write lock | Nothing; this is expected under any schedule tight enough to overlap a slow run. The skipped cycle costs nothing; the next one picks up whatever this one would have |
| `3` | **Everything parsed, but the bibliography has a hole in it**: a stale `file` path, an unreadable PDF, an export that yielded no references, or a bib file the parser read only part of (a dropped entry, an unusable or shared citekey) | Alert, but not at the same urgency: no document was lost by this host. The remedy is in the bib file or on the disk it points at |

Running the `chitragupta.sync` module directly syncs nothing. It names
`chitragupta corpus sync` on stderr and exits **64**, deliberately none
of the four codes in the table, so a caller that reads `2` as "expected,
do nothing" cannot mistake it for a skipped cycle.

### 🕰 cron

```bash
# crontab -e -- runs hourly, on the hour. cd into the repo first: sync
# resolves config.toml and papers/bibliography.bib relative to it.
0 * * * * cd /path/to/chitragupta && .venv-full/bin/python -m chitragupta.corpus sync
```

Without `MAILTO`, cron mails output to the crontab's owner, which needs
a local MTA most hosts lack; `logs/pipeline.log` is written every run
regardless.

### 🐧 systemd (service + timer)

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

Both assume `.venv-full/` is already built
([`scripts/install_full_pipeline.sh`](#-scriptsinstall_full_pipelinesh));
scheduling installs nothing.

## ⚙ Environment variables

Every `config.toml` setting has a matching environment variable that
overrides it for one run; [CONFIG.md](CONFIG.md#-every-setting) has the
full list. The ones that most often appear on a command line:

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

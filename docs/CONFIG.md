# Configuration

Status: **reference.** Written 2026-08-03.

**Written for** anyone setting this pipeline up on their own machine.
**Assumed:** [CLI.md](CLI.md) for the commands these settings change.
**Not covered here:** what each setting *costs*, which is measured in
[PERFORMANCE.md](PERFORMANCE.md), and why the defaults are what they are,
which is [DESIGN.md](DESIGN.md)'s job.

Every setting, what values it accepts, and what it defaults to.

What each setting *costs* lives in [PERFORMANCE.md](PERFORMANCE.md), so
this document can stay a reference rather than an argument.

## Table of contents

- [How configuration is loaded](#how-configuration-is-loaded)
- [A minimal config.toml](#a-minimal-configtoml)
- [Every setting](#every-setting)
  - [Paths](#paths)
  - [`[render]` -- citation style](#render----citation-style)
  - [`[style]` -- prose conformance and the acronym vocabulary](#style----prose-conformance-and-the-acronym-vocabulary)
  - [`[parser]` -- PDF text extraction](#parser----pdf-text-extraction)
  - [`[logging]` -- the pipeline log file](#logging----the-pipeline-log-file)
  - [`[provenance]` -- citation-support bands](#provenance----citation-support-bands)
  - [`[enrich]` -- the optional enrichment layer](#enrich----the-optional-enrichment-layer)
- [How values are parsed](#how-values-are-parsed)
- [Notes on individual settings](#notes-on-individual-settings)
- [Choosing an embedding model](#choosing-an-embedding-model)
- [Seed topics: organising the corpus by phrases you wrote](#seed-topics-organising-the-corpus-by-phrases-you-wrote)

## How configuration is loaded

`config.toml` is not in the repository -- you create it, once:

```bash
cp config.toml.example config.toml
```

`chitragupta/config.py` reads it at import time and **fails with that exact
command** if it is missing, rather than silently falling back to the
example: a machine quietly running settings its owner never chose is a
worse failure than one that refuses to start.

- The file is read **once, at import**, into plain module-level
  constants. They are fixed for the life of the process; editing
  `config.toml` mid-run changes nothing until the next run.
- Every setting can be overridden per-run by an **environment variable**
  of the same name, without editing the file:
  `BIB_FILE=/path/to/other.bib python -m chitragupta.corpus sync`. The environment
  always wins.
- Set **`CONFIG_PATH`** to keep the file elsewhere:
  `CONFIG_PATH=/etc/research/config.toml python -m chitragupta.corpus sync`. This
  names *which file to read* and nothing else -- a relative `[bib] path`
  still resolves against the project directory, not against wherever the
  config file happens to sit.
- The **project directory** is what relative paths below resolve against:
  your `papers/`, `content/` and `logs/`. It is found by walking up from
  the working directory for the nearest `config.toml`, so any command
  works from anywhere inside the project. Set **`CHITRAGUPTA_PROJECT`** to
  say so explicitly instead. Files that ship with the code rather than
  with your project -- the CSL style, the Vale rules, the default acronym
  list -- resolve from the installation instead, and
  [PACKAGING.md](PACKAGING.md) says why the two are separate.
- **Every key is optional.** Anything absent falls back to the default in
  the tables below, so your file only needs the settings you want to
  change.

`config.toml.example` is the tracked template, carrying the same settings
with longer commentary. This document is the authoritative list of
accepted values.

## A minimal config.toml

Because every key is optional, the smallest valid file is an **empty
file** -- that runs the whole pipeline on defaults, expecting your
bibliography at `papers/bibliography.bib`.

The smallest *useful* file names the one thing that genuinely varies
between machines:

```toml
# Minimal config.toml -- everything else falls back to its default.
[bib]
path = "papers/bibliography.bib"
```

A realistic small config, opting into the slower/higher-fidelity parser
and some parallelism:

```toml
[bib]
path = "papers/bibliography.bib"

[parser]
backend = "docling"   # "pdftotext" (default) or "docling"
workers = "auto"      # as many as this machine can sustain
```

## Every setting

Paths resolve **relative to the repository root**; an absolute path is
used as given.

### Paths

| Key | Env var | Accepts | Default |
|---|---|---|---|
| `[bib] path` | `BIB_FILE` | path | `papers/bibliography.bib` |
| `[bib] collections_field` | `BIB_COLLECTIONS_FIELD` | field name | `groups` |
| `[content] dir` | `CONTENT_DIR` | path | `content` |

- **`[bib] path`** -- the BibTeX export `chitragupta/bib_reader.py` parses. The
  only source of citekeys; nothing in the pipeline invents or renames
  one. Gitignored per-host data.
- **`[bib] collections_field`** -- which BibTeX field carries Zotero
  collection membership, read by `chitragupta/bib_collections.py` and used by
  `python -m chitragupta.corpus ledger --collection` and
  `python -m chitragupta.draft retrieve search --collection` to scope a draft to
  a curated subset of the library. `groups` is JabRef's field and what
  Better BibTeX writes under *Export JabRef-specific fields*. **Zotero's
  own BibTeX exporter drops collections**, so on a plain export the field
  is simply absent, nothing is in any collection, and no command changes
  behaviour -- see [ZOTERO.md](ZOTERO.md#keeping-your-collections-optional)
  for how to keep them and what that costs. Lower-cased on read, since
  BibTeX field names are case-insensitive.
- **`[content] dir`** -- everything every layer writes: `sync`'s
  `ledger.sqlite` and `parsed/`, the drafting layer's `drafts/`,
  `dossiers/` and `rendered/`, the review layer's `review/`, and
  `docling/`, `chroma/` and `topics.json` from the enrichment stages.
  One exception lives here too, hand-edited rather than pipeline-written:
  `verbatim_allowlist.toml`, the per-host boilerplate allowlist
  `chitragupta.review verbatim scan` consults -- see
  [PLAGIARISM.md](PLAGIARISM.md#the-boilerplate-allowlist). Fixed at
  `<dir>/verbatim_allowlist.toml`, not independently configurable, same
  as the enrichment caches below it. It is also what every tier-1 command
  that takes a path will *accept*:
  `citation_gate`, `references` and `render_output` each refuse a path
  that resolves outside it, and so do all three of `chitragupta.review`'s aids.
  `ledger` is the one that takes no path argument at all -- its CLI only
  ever addresses rows by citekey or status -- so the rule applies to it
  vacuously rather than needing a check. This one
  directory is then the whole record of the work, and a copy of it is
  complete.

The enrichment layer's artefacts keep the names above --
`content/docling/`, `content/chroma/`, `content/topics.json`, and every
`DOCLING_*` environment variable -- and are not derived from the `[enrich]`
table's name. Renaming them would invalidate work already on disk for no
conceptual gain.

There is no key for "extra PDFs to enrich": the enrichment layer indexes
the bibliography and nothing else, so everything it can retrieve is
something a draft may cite. To add a paper, catalogue it in your
reference manager, re-export, and re-run `sync` -- see
[ZOTERO.md](ZOTERO.md).

### `[render]` -- citation style

Used only by `chitragupta/render_output.py`, never by `sync` or the
citation gate.

| Key | Env var | Accepts | Default |
|---|---|---|---|
| `csl` | `CSL_STYLE` | path | `assets/csl/ieee.csl` |
| `collapse_citations` | `RENDER_COLLAPSE_CITATIONS` | boolean | `true` |

- **`csl`** -- the CSL style pandoc's `--citeproc` formats citations and
  the bibliography with. The IEEE style ships with this repo (vendored,
  not fetched: rendering has to work with no network, and a style that
  changed underneath a draft would renumber one already reviewed). Point
  it at any other `.csl` file to use a different style;
  [the CSL project](https://github.com/citation-style-language/styles)
  publishes several thousand. Without this, pandoc falls back to Chicago
  author-date. Relative to the project directory here, as with every
  other path setting -- so your own `house-style.csl` is found where you
  keep it, while the shipped `assets/csl/ieee.csl` is found wherever this
  code is installed. `render_output`'s `--csl` flag additionally accepts
  a path relative to the current directory, since that is what a
  shell-typed path means.
- **`collapse_citations`** -- whether a run of consecutive numbers
  collapses: `[3]–[6]` rather than `[3], [4], [5], [6]`. The IEEE
  Reference Guide's own examples use the collapsed form, but upstream
  `ieee.csl` does not produce it, so `render_output.py` injects the one
  CSL attribute that does (`collapse="citation-number"`) into a temp copy
  of the style. Set `false` to render whatever the style on disk says,
  unmodified. A style that already sets `collapse` itself is never
  overridden. See `assets/csl/README.md`.

### `[style]` -- prose conformance and the acronym vocabulary

`vale_config` and `language` are used only by `python -m chitragupta.draft
style`, which is a **review aid**: it exits 0 whatever it finds, and
nothing in this pipeline blocks on it. `acronyms`, below, is the one key
in this section that command does not read -- it is read directly by the
five genre-writing skills at drafting time (`docs/GENRE.md`), not by
`chitragupta.draft style`.

| Key | Env var | Accepts | Default |
|---|---|---|---|
| `vale_config` | `VALE_CONFIG` | path | `assets/vale/vale.ini` |
| `language` | `STYLE_LANGUAGE` | BCP-47 tag | unset |
| `acronyms` | `ACRONYMS` | path | `assets/style/acronyms.toml` |

- **`vale_config`** -- the Vale configuration and rule package a draft's
  prose is checked against. Vendored for the same two reasons `csl` is:
  the check has to work with no network, and a rule set that changed
  underneath a draft would report a document that had already been
  reviewed. Point it at your own house style to override what ships;
  `assets/vale/README.md` documents each rule,
  which section of
  [WRITING-STANDARDS.md](WRITING-STANDARDS.md) it implements, and the word
  pairs it deliberately leaves out.
- The `vale` binary itself is **not** configured here -- it is looked up
  on `PATH`. Without it the command reports missing-binary and every
  other command is unaffected, the same bargain `render` makes with
  pandoc. `bash scripts/install_full_pipeline.sh os-deps` installs the
  pinned version.
- **`language`** -- a fallback dialect for a draft whose dossier records
  none. **A fallback, never an override**: the `language:` line in a
  draft's own `scope.md` wins, because a thesis at an Indian university
  and an IEEE submission legitimately differ, and only the per-draft
  record knows which this is. The report names which source a dialect came
  from, so a draft checked against this one never reads like a draft that
  declared its own.
- The order is: `--language` on the command line, then the draft's
  `scope.md`, then this key. With none of the three set, the command
  measures the draft both ways and **proposes** a tag with the
  `dossier set-language` command that would record it -- it never writes
  one itself.
- **`acronyms`** -- a genre skill's acronym vocabulary at step 0, read
  alongside the dialect. `assets/style/acronyms.toml` is the vendored
  floor (`PDF`, `CPU`, `URL`, `API`, `HTML`) and always loads; point this
  at your own file to merge your field's vocabulary over it -- your
  definition wins if you redefine one of the vendored five, and every
  vendored entry you don't redefine still applies. Copy
  `assets/style/acronyms.toml.example` to `content/acronyms.toml`
  (gitignored, per-host, the same footing as `config.toml` itself) and
  point this key there -- not back at `assets/style/acronyms.toml`,
  which is the vendored file this one merges *over*, not a template to
  edit in place. `assets/style/README.md` has the file's shape and
  provenance.

  `python -m chitragupta.draft dossier acronyms-suggest <draft>` proposes new
  entries for it from a draft's glossary *and* its own prose (a term
  coined and expanded inline but never glossaried is exactly the lapse
  this catches) without writing anything; add
  `--apply` to write the proposed entries to your file (creating it if
  it doesn't exist yet), merged without duplicating what is already
  there. `--apply` refuses if this key is unset, rather than writing
  into the vendored floor. `python -m chitragupta.draft style` separately
  reports when a draft's own glossary has drifted from the current
  vocabulary (`docs/WRITING-STANDARDS.md` §9); `draft-reviser`'s
  acronym-realignment mode fixes what that reports.

### `[parser]` -- PDF text extraction

| Key | Env var | Accepts | Default |
|---|---|---|---|
| `backend` | `PARSER` | `"pdftotext"` \| `"docling"` | `"pdftotext"` |
| `ocr` | `PARSER_OCR` | boolean | `false` |
| `workers` | `PARSER_WORKERS` | positive integer, or `"auto"` | `1` |
| `start_method` | `PARSER_START_METHOD` | `"auto"` \| `"forkserver"` \| `"spawn"` | `"auto"` |
| `document_timeout` | `PARSER_DOCUMENT_TIMEOUT` | positive number of seconds, or `"off"` | `"off"` |
| `stall_timeout` | `PARSER_STALL_TIMEOUT` | positive number of seconds, or `"off"` | `1800` |
| `long_word_chars` | `PARSE_LONG_WORD_CHARS` | number, used as an integer | `20` |
| `long_word_ratio` | `PARSE_LONG_WORD_RATIO` | number, a fraction 0.0-1.0 | `0.01` |
| `min_tokens` | `PARSE_MIN_TOKENS` | number, used as an integer | `200` |

The values in full:

- **`backend`** -- `"pdftotext"` needs the `pdftotext` binary on `PATH`
  and no Python package; `"docling"` needs the `enrich` dependency group.
  Any other value is rejected, naming the valid ones. See
  [notes](#backend-pdftotext-or-docling).
- **`ocr`** -- only `docling` has an OCR stage; `pdftotext` ignores this.
- **`workers`** -- `1` takes a strictly serial path: no pool, no
  subprocesses, nothing about a run changes. An integer above 1, or
  `"auto"`, opts into a worker pool. The resolved count is **clamped**
  rather than obeyed blindly -- see
  [notes](#workers-and-how-it-is-clamped). `0`, negative numbers, and
  `true`/`false` are rejected at load.
- **`start_method`** -- consulted only when `workers > 1` **and**
  `backend = "docling"`; nothing else here uses a process pool.
  - `"auto"` -- `forkserver` where the platform has it (Linux, macOS),
    `spawn` where it does not (Windows).
  - `"forkserver"` -- one helper process imports torch and docling; every
    worker is forked from it.
  - `"spawn"` -- a fresh interpreter per worker, importing everything
    itself.
  - `"fork"` is **not** accepted -- see [notes](#why-fork-is-not-an-option).
- **`document_timeout`** / **`stall_timeout`** -- a positive number of
  seconds, or one of `"off"`, `"none"`, `"false"`, or an empty string,
  all meaning "no limit". `0` and negative numbers are **rejected**
  rather than read as "off", because "zero seconds" is the opposite of
  what someone writing it means. Integers and floats both work
  (`stall_timeout = 90.5` is valid).
- **`long_word_chars`** / **`min_tokens`** -- any number; the fractional
  part is truncated.
- **`long_word_ratio`** -- a fraction between 0.0 and 1.0. The range is
  not enforced, so a value above 1.0 loads fine and disables the
  warning, since no document can exceed it.

### `[logging]` -- the pipeline log file

| Key | Env var | Accepts | Default |
|---|---|---|---|
| `level` | `LOGGING_LEVEL` | `"DEBUG"` \| `"INFO"` \| `"WARNING"` \| `"ERROR"` \| `"CRITICAL"` | `"INFO"` |

- **`level`** -- how much the pipeline writes to `logs/pipeline.log`
  (rotated at 5 MB, 5 backups kept -- fixed in code, not configurable).
  Case-insensitive; any other value is rejected, naming the valid ones.
  Only affects the file: terminal output is the same regardless of this
  setting. This is the only `[logging]` key -- rotation size and backup
  count haven't needed to vary per host. See
  [CLI.md's "Running sync on a schedule"](CLI.md#running-sync-on-a-schedule).

  **One file, shared.** Both `python -m chitragupta.corpus sync` and
  `chitragupta/enrich/__main__.py` write here, and each line names its source
  (`chitragupta.sync`, `chitragupta.enrich`,
  `chitragupta.enrich.docling_parse`), so
  `grep 'src\.sync' logs/pipeline.log` recovers a per-command view. The
  file is shared rather than split per command because that is what
  makes it safe: a rotating file can only have one writer process at a
  time, and these two already exclude each other through the pipeline
  write lock. Commands that don't take that lock -- `chitragupta.draft` (all six
  drafting-layer CLIs: gate, dossier, retrieve, references, render) --
  write to stdout only and are not logged.

The log file's own location, `logs/` beside the repo root, has no
`config.toml` key -- but does still honor a `LOGS_DIR` environment
variable, the same escape hatch every path in this file gets, for a
script (or a test) that needs it somewhere else.

### `[provenance]` -- citation-support bands

| Key | Env var | Accepts | Default |
|---|---|---|---|
| `weak_score` | `PROVENANCE_WEAK_SCORE` | number, a fraction 0.0-1.0 | `0.20` |
| `good_score` | `PROVENANCE_GOOD_SCORE` | number, a fraction 0.0-1.0 | `0.50` |

`chitragupta/review/citation_provenance.py` (the review layer) bands the
fraction of a
citing sentence's
distinctive words found in the best-matching source passage. Below
`weak_score` a finding reads "no support found", which means *go look at
this one first* -- never "this citation is wrong". At or above
`good_score` it is banded "supported".

Round numbers on purpose: the report sets a reading order for a human,
not a pass/fail line, so tuning them precisely would be false precision.
Neither is range-checked, and nothing enforces
`weak_score < good_score`.

### `[enrich]` -- the optional enrichment layer

Used only by `chitragupta/enrich/*` (the `enrich` dependency group), never by
`sync` or the citation gate.

| Key | Env var | Accepts | Default in code | In `config.toml.example` |
|---|---|---|---|---|
| `embedding_model` | `EMBEDDING_MODEL` | a sentence-transformers model id | `sentence-transformers/all-MiniLM-L6-v2` | `sentence-transformers/all-mpnet-base-v2` |
| `embed_max_passages_per_source` | `EMBED_MAX_PASSAGES_PER_SOURCE` | integer | `3` | `3` |
| `docling_images` | `DOCLING_IMAGES` | boolean | `false` | `false` |
| `docling_image_scale` | `DOCLING_IMAGE_SCALE` | number | `2.0` | `2.0` |
| `seed_topic_max_papers` | `SEED_TOPIC_MAX_PAPERS` | integer | `25` | `25` |
| `seed_topic_min_similarity` | `SEED_TOPIC_MIN_SIMILARITY` | number, cosine similarity | `0.15` | `0.15` |
| `topic_distribution` | `TOPIC_DISTRIBUTION` | boolean | `true` | `true` |
| `topic_converge_similarity` | `TOPIC_CONVERGE_SIMILARITY` | number, cosine similarity | `0.45` | `0.45` |
| `topic_exclude_author_names` | `TOPIC_EXCLUDE_AUTHOR_NAMES` | boolean | `true` | `true` |
| `topic_min_cluster_size` | `TOPIC_MIN_CLUSTER_SIZE` | integer | `3` | `3` |
| `topic_min_samples` | `TOPIC_MIN_SAMPLES` | integer | `2` | `2` |
| `topic_neighbors` | `TOPIC_NEIGHBORS` | integer | `5` | `5` |
| `topic_membership_ratio` | `TOPIC_MEMBERSHIP_RATIO` | number, 0-1 | `0.5` | `0.5` |
| `topic_membership_max` | `TOPIC_MEMBERSHIP_MAX` | integer | `8` | `8` |

**The two `embedding_model` columns differ on purpose, and the
distinction matters.** The code's fallback is the smaller, faster
MiniLM -- what you get if the key is absent. The shipped example sets the
larger, more accurate mpnet, so anyone who copied `config.toml.example`
is running mpnet. Check your own file rather than assuming either. See
[Choosing an embedding model](#choosing-an-embedding-model).

**`embed_max_passages_per_source`** caps how many chunks of one citekey
`chitragupta.enrich.embed_index.search()` will return among its top `k`
(#305) -- BM25's `chitragupta.retrieval.search()` is already one-per-citekey
by construction and has no matching key. Raise it for a corpus where a
single, unusually thorough paper legitimately deserves more of the
result than three chunks; lower it (to `1`) to force maximal source
diversity per query.

## How values are parsed

Worth knowing, because two of these will surprise you.

**Booleans from the environment.** In TOML, write `true` / `false`. From
an environment variable, only `1`, `true`, `yes`, `on`
(case-insensitive) mean true -- **anything else is false**, including
typos. That is deliberate: `bool("false")` is `True` in Python, so
without it every documented way of turning a setting off via the
environment would silently turn it on.

**A wrong TOML type falls back silently.** String and boolean settings
return their default when the value has the wrong type, rather than
raising. So `ocr = "true"` -- a string, not a boolean -- is read as the
default `false`, with no complaint. Quote strings; don't quote booleans
or numbers.

**Four settings are validated at load and fail loudly:** `workers`,
`start_method`, `document_timeout`, `stall_timeout`. A bad value raises
immediately, naming the key, the environment variable, and what was
expected -- rather than surfacing much later as a nonsense pool size or a
strange timeout.

## Notes on individual settings

### `backend`: pdftotext or docling

`chitragupta/pdf_text.py` dispatches through a table, so adding a backend is one
function plus one entry -- and two candidates were added and later
removed through that same seam.

| Backend | Dependency | Page boundaries? | Quotable passages? | Speed |
|---|---|---|---|---|
| `pdftotext` (default) | `poppler-utils` on `PATH` | **Yes** -- form feeds between pages | No -- reading order is lost | Fastest |
| `docling` | `docling`, `enrich` group | **Yes** -- form feeds between pages | **Yes** -- writes a passage sidecar | ~42x slower; see [PERFORMANCE.md](PERFORMANCE.md#parserbackend----pdftotext-or-docling) |

**Page boundaries are not cosmetic, which is why both backends now keep
them.** `chitragupta/review/verbatim_check.py` reports which PDF page a verbatim
run came from by splitting on those form feeds. Before `docling` asked
for them, a citekey parsed that way reported `pdf p.1` for every hit,
regardless of where the text sat.

**What separates the two backends now is quoting, not paging.**
`pdftotext -layout` preserves a page's visual arrangement rather than its
reading order, so an excerpt cut from it can splice two columns together.
The passage ladder therefore refuses to quote from it, and reports a page
number instead.

`docling` resolves reading order, and the corpus layer keeps that
resolution as `content/parsed/<citekey>.passages.json`. Choosing it here
therefore buys real quotable passages without running the enrichment
layer at all.

The mechanism is in
[CITATION-PROVENANCE.md](CITATION-PROVENANCE.md#what-the-corpus-layer-keeps-when-it-uses-docling),
and the ladder it feeds is in
[LADDERS.md](LADDERS.md#ladder-1-evidence-passages).

[PDF-PARSER.md](PDF-PARSER.md) has the full fidelity comparison.

**Setting `backend = "docling"` does not fold docling into the
enrichment layer, and does not make `chitragupta/enrich/docling_parse.py` redundant.**
They are two consumers of the same library, with different scopes:

- **`chitragupta/pdf_text.py`** (the corpus layer, on `sync`) extracts plain
  text per
  citekey into `content/parsed/<citekey>.txt` for BM25 retrieval, plus the
  passage sidecar beside it. docling here is a higher-fidelity substitute
  for `pdftotext`'s job.
- **`chitragupta/enrich/docling_parse.py`** (the enrichment layer, opt-in) produces
  structured
  Markdown for the whole corpus into `content/docling/`, feeding the
  embedding and topic stages that need real reading order and section
  boundaries. It **always** uses docling regardless of this setting, over
  exactly the same ledger documents -- it has no corpus of its own.

They no longer duplicate the parse, though. When this setting is
`docling`, the enrichment stage adopts the corpus layer's output for a
citekey instead of parsing the PDF a second time -- a file copy in place
of 6.65s per document.

It falls back to a real parse in three cases. First, for a citekey the
corpus layer wrote no text for -- a PDF whose parse failed at sync time,
say. Second, for a run with `[enrich].docling_images` on, because the
corpus layer writes no figure bitmaps to adopt. Third, when the artefacts
are older than the PDF, which means the PDF has been replaced since the
corpus
layer read it. The dependency only ever runs that way round: the
enrichment layer reads the corpus layer's files, and the corpus layer is
not shaped by this at all.

### `workers`, and how it is clamped

The resolved count is the smallest of three ceilings, never below 1:

1. what you asked for,
2. what the machine can sustain,
3. how many documents actually need parsing.

The third matters more than it looks: standing up 12 docling workers to
parse 3 documents pays 12 model loads to save two documents' work.

"What the machine can sustain" counts the CPUs **this process may run
on** -- not the machine's total, which on a shared or containerised
machine can be far larger. For `docling` that count is divided by 4:

| CPUs available to the process | 4 | 8 | 16 | 48 |
|---|---|---|---|---|
| `workers = "auto"` resolves to | 1 | 2 | 4 | 12 |

**That divisor of 4 is measurably too conservative.** It models a docling
worker as occupying about 4 CPUs, and a full-corpus sweep does not
support that. At 32 workers the CPU is only ~70% busy, and 32 workers run
**1.41x faster** than the 12 this table allows. 48 workers are no worse.

The honest reading is "much smaller than 4" rather than a specific
replacement. Changing it is a behaviour change and has not been made --
see
[PERFORMANCE.md](PERFORMANCE.md#parserworkers----document-level-parallelism).

So a four-core desktop resolves to 2, and asking for 15 there still gets
2 -- **clamped and said out loud on stderr**, rather than silently obeyed
(which thrashes) or silently ignored. docling's own internal thread count
is divided down to match, so workers x threads still fits.

**Two things the clamp cannot see:** a cgroup CPU *quota*
(`docker --cpus=2`) throttles without changing which CPUs are permitted,
and RAM is not considered at all. Set an explicit number on either.

Each backend gets the concurrency it can use: processes for `docling`
(in-process, holds the GIL), threads for `pdftotext` (an external
subprocess that releases it). Ledger writes always stay on the main
process -- sqlite has a single writer -- and results are reported in
bibliography order regardless of which worker finished first, so two
identical runs still print identically.

### Using more than one GPU

Nothing to configure. With `docling` and more than one worker, each
worker claims one CUDA device round-robin -- docling's own
`AcceleratorDevice.AUTO` resolves to `cuda:0` in *every* process, so
without this every worker would pile onto card 0 while the rest idle.

Restrict which cards are used with `CUDA_VISIBLE_DEVICES`; the pool only
ever sees what that leaves visible. Figures in
[PERFORMANCE.md](PERFORMANCE.md#multi-gpu----nothing-to-configure).

**A card someone else is already using is skipped**, and the run says so
on stderr:

```text
  WARNING skipping cuda:0 (0.6 GiB free) -- under 2.5 GiB free, which is
  not enough for a docling worker. Parsing on cuda:1,2,3.
```

That threshold is a worker's ~1.7 GiB of models plus its CUDA context.
The check matters more than it sounds: a worker that cannot get device
memory fails a document in seconds where a working one takes minutes, and
the pool hands the next document to whichever worker is free first — so
without this, the broken workers take most of the corpus. If every card
is busy the run parses on the CPU (slower, but it finishes), and a worker
that runs out of device memory *during* a run falls back to the CPU for
its remaining documents rather than failing them.

Nothing to configure here either — but if you would rather wait for a
card than parse on the CPU, the warning is your cue to stop and re-run
later.

### Why `fork` is not an option

Not an oversight. By the time the pool is built, the process holds two
live sqlite connections -- the run lock and the ledger -- and SQLite's
own documentation says not to carry an open connection across `fork()`.
`forkserver` starts its server as a fresh interpreter, so workers inherit
the preloaded modules and nothing else. It also measured **no slower**
than plain `fork`, so nothing is given up.

Both available start methods re-import the calling program's `__main__`
in each worker, so a script of your own driving `sync` or `parse_corpus`
must guard its top level with `if __name__ == "__main__":`.

### The two timeouts are not the same guard

- **`document_timeout`** bounds one document, and the two backends
  enforce it with unequal strength. For `pdftotext` it is a subprocess
  timeout -- a real kill, the one case where a wedged parse can actually
  be stopped. For `docling` it is that library's own check *between*
  pipeline stages: it bounds a pathologically slow document but will not
  interrupt a hang inside a single stage.
- **`stall_timeout`** bounds a *parallel run*, by asking whether **any**
  document at all has completed recently. With several workers,
  completions arrive constantly, so total silence across the whole pool
  separates a hung worker from a merely slow document far better than any
  per-document number could. It applies only when `workers > 1`; a serial
  run has no pool to go silent.

`stall_timeout` is on by default, unlike most safety valves here, because
the failure it catches is one a user actually hit: a run that never
finishes. A false positive is cheap -- outstanding documents are marked
failed and retried next run, not lost -- and a warning is printed at half
the budget before anything is given up on.

Either way a timed-out document is **reported as a failure, not silently
truncated** -- but what happens next differs, because the two guards
blame different things:

- A **`document_timeout`** casualty is named on its own line in `sync`'s
  summary (`WARNING: 2 document(s) hit the 120.0s
  [parser].document_timeout and were not parsed: <citekeys>`), and is
  **not** retried. The limit that expired is a setting, so the next run
  under the same setting would spend the same minutes to reach the same
  answer. Raise `document_timeout` and re-run with `--reparse`.
- A **`stall_timeout`** casualty *is* retried, automatically: those
  documents were never given a fair attempt, so they are recorded as
  transient failures and come back next run.

Choosing a safe value means knowing your slowest legitimate document; see
[PERFORMANCE.md](PERFORMANCE.md#parserdocument_timeout----what-a-safe-value-looks-like).

### The parse-quality guard

`sync` warns when an implausible share of a freshly extracted document's
words are unusually long -- the signature of a backend that has lost the
spaces between words. That is easy to miss by eye and expensive
downstream: `chitragupta/retrieval.py` tokenises on runs of `[a-z0-9]`, so two
words that lost the space between them become a single token and neither
one matches a query for it any more.

`long_word_chars`, `long_word_ratio` and `min_tokens` are its thresholds.
It is **a warning, never a failure** -- the text is still usable, and an
unusual corpus could trip it legitimately. It will not catch a bad `ocr`
choice: it looks for run-together words, not for content that never
arrived.

### `docling_images`

Extracts figure bitmaps into `content/docling/<doc>_artifacts/`, plus a
`<doc>.figures.json` giving each figure's page, caption, and the exact
string to cite it by.

Those images are a **reading aid** for checking a draft against its
sources. They are never inserted into a draft: a figure's copyright is
not the paper's citekey to grant. See
[DEVELOPER.md](../DEVELOPER.md#figures-and-copyright).

Changing this invalidates the whole docling cache, so the next run
re-parses the corpus from scratch. Costs in
[PERFORMANCE.md](PERFORMANCE.md#enrichdocling_images----disk-and-a-full-re-parse).

## Choosing an embedding model

### What is embedded, and what is thrown away first

Documents are cleaned before they are chunked: the reference list is
dropped, along with bare emails, URLs, DOIs, copyright lines and page
numbers. Nothing else -- no stop-word removal, no lowercasing, no
low-frequency filtering, all of which destroy the multiword domain terms
a scientific corpus is discriminated by.

A reference list is a paper's densest block of *other people's* names, so
including it makes two papers similar for citing the same work rather
than for being about the same thing. Before this, the ninth largest topic
on this project's corpus was `werner kritzinger, fraunhofer austria` --
an author cluster, formed by papers citing one famous digital-twin paper.
A `References` heading is detectable in 451 of 497 documents (91%), and
the text after it is a median 15% of the document. The other 9% keep
their whole text rather than having a boundary guessed for them.

`chitragupta/enrich/embed_index.py` calls
`SentenceTransformer(config.EMBEDDING_MODEL).encode(...)`
**symmetrically** -- the same call embeds a 200-word document chunk
(40-word overlap) and a search query, with no prefix or instruction text
added on either side.

That one fact decides which models are drop-in and which are not.

### Drop-in

| Model | Dimensions | Relative cost | Best for | Tradeoff |
|---|---|---|---|---|
| `sentence-transformers/all-MiniLM-L6-v2` (code default) | 384 | Lowest -- ~22M params, fast even on CPU | Small corpora, quick iteration, CPU-only machines | Least semantic nuance of the three; general-purpose training data, nothing science-specific |
| `sentence-transformers/all-mpnet-base-v2` (example default) | 768 | ~4-5x MiniLM -- comfortable on a GPU, noticeably slower CPU-only | Meaningfully better general-purpose semantic quality | More RAM/VRAM and slower indexing/search, for a gain that may not matter at a small corpus size |
| `sentence-transformers/multi-qa-mpnet-base-dot-v1` | 768 | Same class as `all-mpnet-base-v2` | Trained specifically on short-query-vs-long-passage retrieval -- the closest match to what `search()` actually does | Slightly weaker on generic sentence similarity outside retrieval |

What each one is:

- **`all-MiniLM-L6-v2`** -- a 6-layer transformer distilled from a larger
  model, then fine-tuned on roughly a billion general sentence pairs with
  contrastive learning, so semantically similar sentences land close
  together. That symmetric objective is exactly what the prefix-free
  `encode()` call needs, which is why it is the code default. ~22M
  parameters, fast on CPU alone.
- **`all-mpnet-base-v2`** -- the same recipe on a larger 12-layer MPNet
  backbone (~109M parameters). Generally the strongest all-around
  sentence-transformers model for semantic similarity with no domain
  specialisation. The extra quality costs roughly 4-5x the compute and
  doubles the vector dimensionality, which doubles per-chunk storage in
  Chroma and slows similarity search somewhat.
- **`multi-qa-mpnet-base-dot-v1`** -- the same MPNet backbone, fine-tuned
  on ~215M question/answer and query/passage pairs for dot-product
  retrieval rather than generic similarity. Conceptually the closest
  match to a short query against a longer chunk, and it needs no prefix,
  so it stays a clean drop-in. Same cost profile as `all-mpnet-base-v2`.

### Not without a code change first

- **`allenai/specter` / `specter2`** -- a SciBERT-based model trained on
  scientific title+abstract pairs using citation graphs as the signal. It
  is built for whole-paper similarity, not passage retrieval, and expects
  a specific input shape (title `[SEP]` abstract) that does not match the
  arbitrary 200-word body chunks this pipeline produces. Using it well
  means feeding it titles and abstracts -- a real code change -- and even
  then it answers "which papers are alike", a different question than
  "which chunk answers this query".
- **BAAI `bge-*` and `intfloat e5-*` families** -- strong on public
  retrieval benchmarks, but they expect literal `"query: "` /
  `"passage: "` prefixes baked into the input so the model knows which
  role each side plays. Nothing here adds one. Feeding either in as-is
  **will not error -- it will silently underperform**, which is the worst
  failure mode of the set. Adopting one means pairing it with matching
  prefix-handling code, not a config-only swap.

### Switching

Edit `[enrich].embedding_model`, or set `EMBEDDING_MODEL=...` for a single
run, then rebuild the index:

```bash
python -m chitragupta.enrich --stages embed
```

The model downloads on first use (needs network), and Chroma's existing
collection is **not** re-embedded automatically -- switch only when you
are prepared to rebuild the index.

## Seed topics: organising the corpus by phrases you wrote

`content/seed_topics.toml` is a list of topic phrases in your own words.
It is optional and absent by default; with no such file the enrichment
layer behaves exactly as it did before the feature existed -- the
`bertopic` stage clusters without steering, and the `seed-topics` stage
reports itself skipped rather than failing.

```toml
# content/seed_topics.toml -- start from assets/style/topics.toml.example
topics = [
    "digital twin",
    "structural health monitoring",
]
```

**A phrase is one topic and is never split into words.** "structural
health monitoring" is embedded whole and compared as a single point
against each document, rather than looked up as three separate terms in a
bag-of-words vocabulary -- which is what would happen under BERTopic's
older `seed_topic_list`, where "monitoring" alone would match every paper
with a monitoring section. Write the phrase you mean.

### Where the phrases come from

Yours to write. If your Zotero export carries collection labels
([ZOTERO.md](ZOTERO.md)), your own collection names are the best starting
point, since they are groupings you already trust:

```bash
chitragupta corpus ledger --collections
```

Paste in the ones that read as topics and leave out the ones that read as
shelves. "Digital twins" is a topic; "Reading list", "To read" and "2024
submissions" are not, and nothing can tell them apart mechanically --
which is why this file is written by hand rather than generated. That is
[HOUSE-STYLE.md](HOUSE-STYLE.md)'s "it proposes; the human accepts",
applied to the one decision a heuristic would get wrong.

### Running it, and reading the result

```bash
chitragupta enrich --stages seed-topics   # needs the enrich group
chitragupta corpus topics                 # stdlib only, no venv, no GPU
chitragupta corpus topics --topic "digital twin"
```

The match report is written to `content/topic_seeds.json` and read back
by `chitragupta corpus topics`, which needs neither the venv nor a GPU --
the same split [#204](https://github.com/prasadtalasila/chitragupta/issues/204)
made for collections, where matching is expensive and reading what it
decided is not.

**A paper appears under every topic it matched, not just its closest
one.** That is deliberate and is the difference between this artefact and
`content/topics.json`: BERTopic assigns each document exactly one topic
id, but a library grouped by hand does not work that way -- a paper on
digital twins in manufacturing genuinely belongs under both. Both
artefacts are written, from the same embeddings, and neither replaces the
other.

The report also lists every document that matched **no** topic. That list
is the useful half for planning a draft: it is the part of your own
corpus your own topic list does not yet describe. Add a phrase, run it
again, and watch it shrink.

### How many papers a topic lists, and why it is a ranking

`[enrich].seed_topic_max_papers` (default `25`) is the selection rule:
each phrase is ranked against **its own** scores and the best N kept.
`[enrich].seed_topic_min_similarity` (default `0.15`) is only a noise
floor beneath that.

That ordering was a correction, not the first design, and a real corpus
forced it. Measured over 497 documents against 14 real Zotero collection
names, every phrase had its own score scale:

| phrase | corpus-wide max | median |
|---|---|---|
| `Standards` | 0.295 | 0.069 |
| `Digital Twin` | 0.669 | 0.338 |

Under a single absolute cutoff of `0.35`, `Standards` -- a genuine
25-paper collection -- returned **nothing at all**, while `Digital Twin`
returned 238 papers, half the corpus. Both are useless answers and no
single number fixes both, because the two distributions barely overlap.
Ranking each phrase against itself is immune to that.

The report always prints how many papers were *considered*, so a
truncated list ("25 of 340 papers") never reads like a short one.

What the floor does and does not do: of four deliberately shelf-like
collection names in that run, the two with no semantic content --
`Others` and a person's name, `Karen Wilcox` -- peaked at 0.143 and
0.112 and correctly returned nothing. The other two, `Reviews and
Surveys` and `opinions`, clear the floor and do return papers. A shelf
label that is *also* a description of a paper is not distinguishable
from a topic by score, and this floor does not try to be. Which names go
in your list stays your decision.

### How many seed topics may I write?

**As many as you like, and they cost nothing.** There is no setting for
this and no limit in the code: matching is one cosine per phrase per
document, so hundreds of phrases against a corpus of thousands is still
arithmetic you would not notice.

More importantly, seeds no longer compete with discovery. They are
matched against the same document vectors *after* clustering, never fed
into it, so naming a topic does not consume the documents an emergent
topic would have been made of. That was not always true: routing seeds
through BERTopic's `zeroshot_topic_list` took this corpus from 81
emergent topics to 53 with only nine phrases -- roughly three discovered
topics traded away per named one -- and enough seeds starved HDBSCAN of
points entirely and killed the stage inside sklearn. That path is gone.

The practical consequence is the one worth knowing: **write the topics you
care about, then read what the corpus had that you did not name.** The
`unmatched` list in `chitragupta corpus topics` and the emergent topics in
`content/topics.json` are both answers to that question, and neither
shrinks because your seed list grew.

### One topic set, from your phrases and the corpus's own

`content/topic_set.json` is the join of the two topic answers, written by
the `converge` stage. Until it existed, `content/topic_seeds.json` held
the phrases you wrote and `content/topics.json` held the topics
clustering found, and nothing related them -- a seed phrase and an
emergent topic covering the same papers appeared as two unrelated things
and you reconciled them by eye.

A topic here has one shape whatever it came from:

```json
{"label": "structural health monitoring", "provenance": "seed",
 "topic_id": 41, "members": [{"citekey": "...", "score": 0.62}]}
```

**Convergence is your name winning.** An emergent topic whose descriptor
sits within `[enrich].topic_converge_similarity` of one of your phrases
is *renamed* by it rather than listed separately. That is what "seeds are
a starting point" has to mean once it reaches a file: having written
"structural health monitoring", you should not then have to notice that
emergent topic 41 is the same thing under a derived name.

Two collisions are resolved deliberately:

- **Several phrases match one topic** -- the closest wins, ties broken on
  the phrase text so a run is diffable against the last.
- **Several topics match one phrase** -- each keeps its own row and its
  own members. A phrase can legitimately name a family of neighbouring
  clusters, and merging them would discard granularity the clustering
  just found.

A phrase that matches no emergent topic still appears, carrying the
papers it matched and `"topic_id": null`. That is the useful case rather
than a leftover: it is you naming something the clustering did not
separate out, and seeing it with no cluster behind it is the signal that
the corpus does not organise the way you assumed. The `uncovered` list at
the end names the papers no topic of either kind reached.

**The stage re-runs nothing.** It reads the two artefacts, recomputes
only the topic descriptors -- arithmetic over vectors already cached, no
clustering -- and joins. Run it after `bertopic` and `seed-topics`; on
its own it reports itself skipped rather than quietly clustering for you.

### What a topic is called

A topic's name comes from the terms BERTopic finds most distinguishing
within it. Two things are excluded from that vocabulary, and neither
touches which papers are grouped together:

- **This corpus's own author names**, read from the ledger's `bib_fields`
  -- your bibliography, not a general name list.
  `[enrich].topic_exclude_author_names` turns it off.
- **Citation and URL scaffolding** (`et al`, `doi`, `www`, `arxiv`),
  which survives content preprocessing because it appears mid-sentence
  rather than on lines of its own.

Both fix labels that were measurably wrong on a real corpus. Before this,
BERTopic's own names were function words (`0_the_and_of_to`, because
nothing configured a stop-word list); with those removed, the top-ranked
topic by membership was named `werner kritzinger, fraunhofer austria` --
a person and their institution. `et al` and a DOI fragment named two more
of the twenty largest.

That was never a clustering failure. Those papers are a real topic: they
survey a taxonomy, and they name its author because they are discussing
his work. `kritzinger` appears in 101 of 497 documents and 55 still carry
it after the reference list is removed, so dropping back matter cannot
fix it -- the name is in the prose, and the prose *is* the topic.

**The cost, measured:** of 1,277 distinct surnames in this corpus's
bibliography, five are also ordinary English words (`black`, `brown`,
`can`, `park`, `wood`) and leave the label vocabulary with the rest.

**What it cannot reach:** the list holds authors of papers *in* the
corpus. A person these papers cite whose own work is not in your library
is still eligible to name a topic -- measured, `drath` and `kockmann`
both survive for that reason. Widening it would mean inferring names from
reference prose; the bibliography is the one place a name is asserted
rather than guessed.

### How many topics, and how deep

`[enrich].topic_min_cluster_size` (3), `topic_min_samples` (2) and
`topic_neighbors` (5) decide the granularity of the emergent topic
structure. They are settings rather than constants because the right
depth is a property of a corpus and its owner, not of this code.

The values they replaced were not a tuning choice but a **ceiling**:
every clustering parameter saturated at `n_docs >= 20`, so a 497-paper
corpus received the settings written for a 20-paper one, and a 5000-paper
corpus would have received them too. Measured on this project's own
corpus, holding everything else fixed:

| `topic_min_cluster_size` | topics | outliers | median topic size |
|---|---|---|---|
| 10 (the old hardcoded value) | 13 | 27% | 19 |
| 5 | 25 | 19% | 13 |
| 3 | 50 | 12% | 6 |
| 3, with `topic_min_samples = 2` | 75 | 10% | 5 |

Note the outlier rate **falls** as the topics get finer: the coarse
setting was both under-clustering and discarding more of the corpus, so
this is a defect corrected rather than a preference expressed.

The small-corpus clamps survive and only ever reduce these values --
UMAP's spectral initialisation genuinely fails when `n_neighbors >=
n_samples`, which is what the original formula existed for. What it never
did was scale *up*.

### Topics a paper belongs to, beyond the one it is assigned

`content/topics.json` records `assignments` -- one topic id per document,
which is all `fit_transform` has ever returned -- and, when
`[enrich].topic_distribution` is on, a `memberships` map giving every
topic each document belongs to with its strength. On this project's own
corpus **140 of 497 papers belong to more than one topic**, and the
scalar discards 222 such memberships.

**`assignments` and `memberships` are not the same claim**, and the file
records which is which:

- `assignments` is **which cluster a document was put in** -- density,
  one id, whatever HDBSCAN decided.
- `memberships` is **what the paper is about** -- similarity to each
  topic's descriptor, as many topics as clear the bar.

They can differ, and that is not a defect: a density cluster can be
elongated or hollow, so "the region this point sits in" and "the subjects
this paper is close to" are different questions. What would be a defect
is the file implying otherwise, so **the assigned topic is always present
in a document's memberships**, whatever its similarity.

The strengths are cosine to each topic's descriptor -- its members'
centroid, on mean-centred embeddings -- recorded as
`membership_mechanism` in the artefact so a reader can tell which
arithmetic produced them. Centring is load-bearing: in a corpus about one
subject every document and centroid share a large common component, so
raw cosines bunch together. Measured over 76 topics, raw gave a mean
top-share of 0.20 against a uniform baseline of 0.01, where centred gives
0.60.

This replaced HDBSCAN's own soft clustering, which answered the *density*
question and for a core point answers it nearly binarily: it reported
1.64 topics per paper with 25% of papers plural, on a library where 637
of 642 papers carry hand-made Zotero collection labels across 95
collections. Two other mechanisms were measured and rejected: BERTopic's
`approximate_distribution` separated almost nothing (top-share 0.03
against a uniform 0.01), and a Gaussian mixture returned near-certain
single assignments, which is hard clustering again. `bench/RESULTS.md`
has the table.

`topic_membership_ratio` (default `0.5`) is how strong a topic must be
relative to that document's strongest, and `topic_membership_max`
(default `8`) caps the list. The cap exists for a document similar to
almost everything; the ratio is meant to do the deciding for the rest. It
was `3` until a corpus producing 76 topics put 387 of 497 documents at
exactly that number -- the cap deciding, and the ratio never speaking.

**Memberships are recorded for every run.** They were once available only
for an unseeded one, because BERTopic swaps its clusterer for a
placeholder carrying no labels in zero-shot mode and there was then
nothing to ask. Removing that mode -- so seeds no longer steer the
clustering at all -- retired the restriction along with it.

None of these gate anything: no run fails on them and no draft is
blocked by one (`docs/HOUSE-STYLE.md` R3).

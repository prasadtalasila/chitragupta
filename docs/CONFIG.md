# ⚙ Configuration

Status: **reference.**

**Written for** anyone setting this pipeline up on their own machine.
**Assumed:** [CLI.md](CLI.md) for the commands these settings change.
**Not covered here:** what each setting *costs*, which is measured in
[PERFORMANCE.md](PERFORMANCE.md), and why the defaults are what they are,
which is [DESIGN.md](DESIGN.md)'s job.

Every setting, what values it accepts, and what it defaults to.

## 📥 How configuration is loaded

`config.toml` is not in the repository. `chitragupta init` writes it
for an installed project; in a git checkout you create it, once:

```bash
cp config.toml.example config.toml
```

`chitragupta/config.py` reads it at import time and **fails with that exact
command** if it is missing, instead of silently falling back to the
example: a machine running settings its owner never chose is a worse
failure than one that refuses to start.

- The file is read **once, at import**, into module-level constants.
  Editing `config.toml` mid-run changes nothing until the next run.
- Every setting can be overridden per run by the **environment variable**
  named beside it in the tables below:
  `BIB_FILE=/path/to/other.bib python -m chitragupta.corpus sync`. The
  environment always wins.
- Set **`CONFIG_PATH`** to keep the file elsewhere:
  `CONFIG_PATH=/etc/research/config.toml python -m chitragupta.corpus sync`.
  It names *which file to read* and nothing else: a relative
  `[bib] path` still resolves against the project directory.
- The **project directory**, which relative paths resolve against, is
  the nearest directory holding a `config.toml` above the working
  directory, or **`CHITRAGUPTA_PROJECT`** if set. Files that ship with the
  code (the CSL style, the Vale rules, the default acronym list) resolve
  from the installation; [PACKAGING.md](PACKAGING.md) says why.
- **Every key is optional.** An absent key takes the default below.

`config.toml.example` is the tracked template, with longer commentary;
this page is the authoritative list of accepted values.

## 📝 A minimal config.toml

The smallest valid file is an **empty file**: the whole pipeline runs on
defaults, expecting your bibliography at `papers/bibliography.bib`. A
realistic small config opts into the higher-fidelity parser and some
parallelism:

```toml
[bib]
path = "papers/bibliography.bib"

[parser]
backend = "docling"   # "pdftotext" (default) or "docling"
workers = "auto"      # as many as this machine can sustain
```

## 📋 Every setting

Paths resolve **relative to the project directory** (the one holding
`config.toml`); an absolute path is used as given.

### 📁 Paths

| Key | Env var | Accepts | Default |
| --- | --- | --- | --- |
| `[bib] path` | `BIB_FILE` | path | `papers/bibliography.bib` |
| `[bib] collections_field` | `BIB_COLLECTIONS_FIELD` | field name | `groups` |
| `[content] dir` | `CONTENT_DIR` | path | `content` |

- **`[bib] path`**: the BibTeX export `chitragupta/bib_reader.py` parses.
  The only source of citekeys; nothing in the pipeline invents or renames
  one. Gitignored per-host data.
- **`[bib] collections_field`**: which BibTeX field carries Zotero
  collection membership, used by
  `python -m chitragupta.corpus ledger --collection` and
  `python -m chitragupta.draft retrieve search --collection` to scope a
  draft to a curated subset of the library. `groups` is JabRef's field
  and what Better BibTeX writes under *Export JabRef-specific fields*.
  **Zotero's own BibTeX exporter drops collections**, so on a plain
  export nothing is in any collection and no command changes behaviour.
  [ZOTERO.md](ZOTERO.md#-keeping-your-collections-optional) says how to
  keep them. Lower-cased on read.
- **`[content] dir`**: everything every layer writes (`ledger.sqlite`,
  `parsed/`, `drafts/`, `dossiers/`, `rendered/`, `review/`, and the
  enrichment stages' `docling/`, `chroma/` and `topics.json`), plus two
  hand-edited files at fixed paths: the per-host
  `verbatim_allowlist.toml`
  ([PLAGIARISM.md](PLAGIARISM.md#-the-boilerplate-allowlist)) and
  `style_exceptions.toml`, project data listing terms no prose rule
  reports
  ([WRITING-STANDARDS.md](WRITING-STANDARDS.md#-9-what-is-checked-mechanically-and-what-is-not)),
  which `chitragupta init` does not create. Every tier-1 command that
  takes a path, including all eleven `chitragupta.review` aids, refuses
  one outside this directory, so a copy of it is the complete record of
  the work.

The enrichment layer's artefacts (`content/docling/`, `content/chroma/`,
`content/topics.json`) and every `DOCLING_*` environment variable keep
those names and are not derived from the `[enrich]` table's name:
renaming them would invalidate work already on disk.

There is no key for "extra PDFs to enrich": the enrichment layer indexes
the bibliography and nothing else, so everything it can retrieve is
something a draft may cite. To add a paper, catalogue it in your
reference manager, re-export, and re-run `sync`; see
[ZOTERO.md](ZOTERO.md).

### 📐 `[render]` -- citation style

Used only by `chitragupta/render_output/`, never by `sync` or the
citation gate.

| Key | Env var | Accepts | Default |
| --- | --- | --- | --- |
| `csl` | `CSL_STYLE` | path | `assets/csl/ieee.csl` |
| `collapse_citations` | `RENDER_COLLAPSE_CITATIONS` | boolean | `true` |

- **`csl`**: the CSL style pandoc's `--citeproc` formats citations and
  the bibliography with. The IEEE style is vendored, not fetched:
  rendering has to work with no network, and a style that changed
  underneath a draft would renumber one already reviewed. Point it at any
  other `.csl` file to use a different style;
  [the CSL project](https://github.com/citation-style-language/styles)
  publishes several thousand. `render_output`'s `--csl` flag also
  accepts a path relative to the current directory.
- **`collapse_citations`**: whether a run of consecutive numbers
  collapses: `[3]–[6]` instead of `[3], [4], [5], [6]`. The IEEE
  Reference Guide uses the collapsed form but upstream `ieee.csl` does
  not produce it, so `render_output` injects `collapse="citation-number"`
  into a temp copy of the style. Set `false` to render the style on disk
  unmodified. A style that sets `collapse` itself is never overridden.
  See `assets/csl/README.md`.

### 🏷 `[style]` -- prose conformance and the acronym vocabulary

`vale_config` and `language` are used only by `python -m chitragupta.draft
style`, a **review aid** that exits 0 whatever it finds. `acronyms` is
also read by the genre-writing skills (`docs/GENRE.md`) and by
`[retrieval].acronym_expansion`.

| Key | Env var | Accepts | Default |
| --- | --- | --- | --- |
| `vale_config` | `VALE_CONFIG` | path | `assets/vale/vale.ini` |
| `language` | `STYLE_LANGUAGE` | BCP-47 tag | unset |
| `acronyms` | `ACRONYMS` | path | `assets/style/acronyms.toml` |

- **`vale_config`**: the Vale configuration and rule package a draft's
  prose is checked against, vendored for the same reasons as `csl`;
  `assets/vale/README.md` documents each rule. The `vale` binary is
  looked up on `PATH` (`chitragupta install os-deps` installs it), and
  without it only this command is affected.
- **`language`**: a fallback dialect for a draft whose dossier records
  none. **A fallback, never an override**: the `language:` line in a
  draft's own `scope.md` wins, because a thesis at an Indian university
  and an IEEE submission legitimately differ. The order is `--language`,
  then `scope.md`, then this key. With none set, the command **proposes**
  a `dossier set-language` command and never writes one itself.
- **`acronyms`**: the acronym vocabulary. `assets/style/acronyms.toml` is
  the vendored floor (`PDF`, `CPU`, `URL`, `API`, `HTML`) and always
  loads; point this key at your own file to merge your field's vocabulary
  over it, your definition winning on a clash. Copy
  `assets/style/acronyms.toml.example` to `content/acronyms.toml`
  (gitignored, per-host) and point this key there, never at the vendored
  floor itself. `assets/style/README.md` has the file's shape.

  `python -m chitragupta.draft dossier acronyms-suggest <draft>` proposes
  entries from a draft's glossary and prose; `--apply` merges them into
  your file and refuses if this key is unset. `draft style` reports when
  a glossary has drifted from the vocabulary
  (`docs/WRITING-STANDARDS.md` §9).

### 📄 `[parser]` -- PDF text extraction

| Key | Env var | Accepts | Default |
| --- | --- | --- | --- |
| `backend` | `PARSER` | `"pdftotext"` \| `"docling"` | `"pdftotext"` |
| `ocr` | `PARSER_OCR` | boolean | `false` |
| `formulas` | `PARSER_FORMULAS` | boolean | `false` |
| `workers` | `PARSER_WORKERS` | positive integer, or `"auto"` | `1` |
| `start_method` | `PARSER_START_METHOD` | `"auto"` \| `"forkserver"` \| `"spawn"` | `"auto"` |
| `document_timeout` | `PARSER_DOCUMENT_TIMEOUT` | positive number of seconds, or `"off"` | `"off"` |
| `stall_timeout` | `PARSER_STALL_TIMEOUT` | positive number of seconds, or `"off"` | `1800` |
| `long_word_chars` | `PARSE_LONG_WORD_CHARS` | number, used as an integer | `20` |
| `long_word_ratio` | `PARSE_LONG_WORD_RATIO` | number, a fraction 0.0-1.0 | `0.01` |
| `min_tokens` | `PARSE_MIN_TOKENS` | number, used as an integer | `200` |

The values in full:

- **`backend`**: `"pdftotext"` needs the `pdftotext` binary on `PATH`
  and no Python package; `"docling"` needs the `enrich` dependency group.
  Case-insensitive; any other value is rejected at load, naming the
  valid ones. See [notes](#-backend-pdftotext-or-docling).
- **`ocr`**: only `docling` has an OCR stage; `pdftotext` ignores this.
  [PERFORMANCE.md](PERFORMANCE.md#-parserocr----the-largest-single-lever-and-a-trade)
  has what it costs and buys.
- **`formulas`**: only `docling` recognises formulae, writing them as
  LaTeX; `pdftotext` ignores this. See
  [notes](#-formulas-and-why-it-is-not-the-enrich-key).
- **`workers`**: `1` is strictly serial, with no pool. An integer above
  1, or `"auto"`, opts into a worker pool whose size is **clamped**; see
  [notes](#-workers-and-how-it-is-clamped). `0`, negative numbers, and
  `true`/`false` are rejected at load.
- **`start_method`**: consulted only when `workers > 1` **and**
  `backend = "docling"`. `"forkserver"` forks every worker from one
  helper process that has imported torch and docling; `"spawn"` starts a
  fresh interpreter per worker; `"auto"` picks `forkserver` where the
  platform has it (Linux, macOS) and `spawn` elsewhere. `"fork"` is
  **not** accepted; see [notes](#-why-fork-is-not-an-option).
- **`document_timeout`** / **`stall_timeout`**: a positive number of
  seconds, or one of `"off"`, `"none"`, `"false"`, or an empty string,
  all meaning "no limit". Floats work. `0` and negative numbers are
  **rejected**, since "zero seconds" is the opposite of "off". See
  [notes](#-the-two-timeouts-are-not-the-same-guard).
- **`long_word_chars`** / **`min_tokens`**: any number; the fractional
  part is truncated. See [notes](#-the-parse-quality-guard).
- **`long_word_ratio`**: a fraction between 0.0 and 1.0. The range is
  not enforced, so a value above 1.0 loads fine and disables the
  warning, since no document can exceed it.

### 🪵 `[logging]` -- the pipeline log file

| Key | Env var | Accepts | Default |
| --- | --- | --- | --- |
| `level` | `LOGGING_LEVEL` | `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"` | `"INFO"` |

- **`level`**: how much the pipeline writes to `logs/pipeline.log`
  (rotated at 5 MB, 5 backups kept). Case-insensitive; any other value is
  rejected. Terminal output is unaffected. See
  [CLI.md's "Running sync on a schedule"](CLI.md#-running-sync-on-a-schedule).

  `python -m chitragupta.corpus sync` and `chitragupta/enrich/__main__.py`
  share the file, and each line names its source (`chitragupta.sync`,
  `chitragupta.enrich`, `chitragupta.enrich.docling_parse`), so
  `grep 'chitragupta\.sync' logs/pipeline.log` recovers a per-command
  view. One file is safe because these two already exclude each other
  through the pipeline write lock. The `chitragupta.draft` CLIs write to
  stdout only and are not logged.

The log directory, `logs/` beside the repo root, has no `config.toml`
key but honours a `LOGS_DIR` environment variable.

### 📖 `[provenance]` -- citation-support bands

| Key | Env var | Accepts | Default |
| --- | --- | --- | --- |
| `weak_score` | `PROVENANCE_WEAK_SCORE` | number, a fraction 0.0-1.0 | `0.20` |
| `good_score` | `PROVENANCE_GOOD_SCORE` | number, a fraction 0.0-1.0 | `0.50` |

`chitragupta/review/citation_provenance.py` bands the share of a citing
sentence's distinctive words found in the best-matching source passage. Below
`weak_score` a finding reads "no support found", which means *go look at this
one first*, never "this citation is wrong". At or above `good_score` it is
banded "supported". The defaults are round on purpose: the report sets a reading
order for a human, not a pass/fail line. Neither is range-checked, and nothing
enforces `weak_score < good_score`.

### 🔎 `[retrieval]` -- BM25's field weights, cap and floor

Tier 1: stdlib only, no venv and no model, which is why these are not
`[enrich]` keys.

| Key | Env var | Accepts | Default |
| --- | --- | --- | --- |
| `weight_title` | `RETRIEVAL_WEIGHT_TITLE` | number, finite and at least 0 | `1.0` |
| `weight_abstract` | `RETRIEVAL_WEIGHT_ABSTRACT` | number, finite and at least 0 | `1.0` |
| `k1` | `RETRIEVAL_K1` | number, finite and at least 0 | `1.5` |
| `b` | `RETRIEVAL_B` | number between 0 and 1 | `0.75` |
| `acronym_expansion` | `RETRIEVAL_ACRONYM_EXPANSION` | boolean | `true` |
| `spelling_correction` | `RETRIEVAL_SPELLING_CORRECTION` | boolean | `false` |
| `max_passages_per_source` | `MAX_PASSAGES_PER_SOURCE` | positive integer | `3` |
| `min_passage_tokens` | `MIN_PASSAGE_TOKENS` | positive integer | `20` |

- **`weight_title`** / **`weight_abstract`**: how much a query term
  counts when it appears in a paper's title or abstract instead of its
  body. The weight is a delta on the ordinary frequency, so **1.0 leaves
  the ranking exactly as it is**. A negative or infinite value is
  rejected at load. `weight_abstract` needs a structural passage sidecar,
  so on the shipped `[parser].backend = "pdftotext"` it is silently
  inert. Both apply to the *document* unit only and are inert on the
  passage unit, which carries no field counts: a title is a property of
  the paper, and the passage unit exists to stop a paragraph being scored
  on its paper's behalf.
- **`k1`** / **`b`**: Okapi BM25's own parameters, how fast a term's
  frequency saturates and how strongly length normalises a score. They
  apply to both units. `b` past 1 flips the sign of BM25's denominator
  for a short document, so it is rejected at load.
- **`acronym_expansion`**: adds an acronym's expansion to a query (`DT`
  also searching for "digital twin"), counting as much as a typed term.
  The vocabulary is the `[style].acronyms` one and nothing else. On the
  vendored five alone it changes nothing measurable. Query-side only: a
  query spelling a term out still cannot reach a document that only
  abbreviates it.
- **`spelling_correction`**: a query word of five or more letters that
  no paper contains also searches for the corpus word one typing slip
  away (`strucutral` also searching for "structural"). The typed word
  stays, and every correction is announced and logged. Off by default,
  because turning it on re-ranks every draft's recorded queries in
  `dossier status`. See
  [RETRIEVAL.md](RETRIEVAL.md#-a-misspelled-query-word-can-reach-its-corpus-spelling).
- **`max_passages_per_source`**: passage unit only. Stops one
  well-matched paper filling every slot; lower it to 1 for maximal
  source diversity.
- **`min_passage_tokens`**: passage unit only. Keeps short passages out
  of the index, because BM25's length normalisation *rewards* a short
  match and a one-line bibliography entry would otherwise outrank real
  paragraphs. Excluding `section_header` and `title` passages is the
  structural half of that and is not configurable.

[RETRIEVAL.md](RETRIEVAL.md) has the sweeps behind every default,
including [k1 and b](RETRIEVAL.md#-k1-and-b-are-settings-and-the-defaults-were-swept),
and [the passage unit](RETRIEVAL.md#-the-passage-unit).

**There is deliberately no over-fetch multiplier here**, unlike
`[enrich].embed_overfetch_multiplier`: BM25 scores every passage in
memory, so the cap already walks the fully ranked list.

### 🧠 `[enrich]` -- the optional enrichment layer

Used only by `chitragupta/enrich/*` (the `enrich` dependency group),
never by `sync` or the citation gate.

| Key | Env var | Accepts | Default in code | In `config.toml.example` |
| --- | --- | --- | --- | --- |
| `embedding_model` | `EMBEDDING_MODEL` | a sentence-transformers model id | `sentence-transformers/all-MiniLM-L6-v2` | `sentence-transformers/all-mpnet-base-v2` |
| `embed_top_k` | `EMBED_TOP_K` | integer >= 1 | `5` | `5` |
| `embed_max_passages_per_source` | `EMBED_MAX_PASSAGES_PER_SOURCE` | integer >= 1 | `3` | `3` |
| `embed_overfetch_multiplier` | `EMBED_OVERFETCH_MULTIPLIER` | integer >= 1 | `4` | `4` |
| `rerank` | `RERANK` | boolean | `false` | `false` |
| `rerank_model` | `RERANK_MODEL` | a sentence-transformers **cross-encoder** id | `cross-encoder/ms-marco-MiniLM-L6-v2` | `cross-encoder/ms-marco-MiniLM-L6-v2` |
| `entailment_model` | `ENTAILMENT_MODEL` | a `sentence_transformers.CrossEncoder` model id | `cross-encoder/nli-deberta-v3-small` | `cross-encoder/nli-deberta-v3-base` |
| `support_premise_topk` | `SUPPORT_PREMISE_TOPK` | integer >= 1, or `"off"` | `off` (uncapped) | `off` (uncapped) |
| `docling_images` | `DOCLING_IMAGES` | boolean | `false` | `false` |
| `docling_image_scale` | `DOCLING_IMAGE_SCALE` | number | `2.0` | `2.0` |
| `docling_formulas` | `DOCLING_FORMULAS` | boolean | `false` | `false` |
| `keywords_path` | `KEYWORDS_PATH` | a path, resolved under `content/` unless absolute | `keywords.toml` | `keywords.toml` |
| `keyword_top_n` | `KEYWORD_TOP_N` | integer | `40` | `40` |
| `keyword_min_df` | `KEYWORD_MIN_DF` | integer | `2` | `2` |
| `seed_topic_max_papers` | `SEED_TOPIC_MAX_PAPERS` | integer | `25` | `25` |
| `seed_topic_min_similarity` | `SEED_TOPIC_MIN_SIMILARITY` | number, cosine similarity | `0.15` | `0.15` |
| `topic_distribution` | `TOPIC_DISTRIBUTION` | boolean | `true` | `true` |
| `topic_converge_similarity` | `TOPIC_CONVERGE_SIMILARITY` | number, cosine similarity | `0.45` | `0.45` |
| `topic_exclude_author_names` | `TOPIC_EXCLUDE_AUTHOR_NAMES` | boolean | `true` | `true` |
| `topic_graph_neighbors` | `TOPIC_GRAPH_NEIGHBORS` | integer | `5` | `5` |
| `topic_graph_p_value` | `TOPIC_GRAPH_P_VALUE` | number, significance level | `0.01` | `0.01` |
| `topic_min_cluster_size` | `TOPIC_MIN_CLUSTER_SIZE` | integer | `3` | `3` |
| `topic_min_samples` | `TOPIC_MIN_SAMPLES` | integer | `2` | `2` |
| `topic_neighbors` | `TOPIC_NEIGHBORS` | integer | `5` | `5` |
| `topic_membership_ratio` | `TOPIC_MEMBERSHIP_RATIO` | number, 0-1 | `0.5` | `0.5` |
| `topic_membership_max` | `TOPIC_MEMBERSHIP_MAX` | integer | `8` | `8` |

**The two `embedding_model` and `entailment_model` columns differ on
purpose.** The code's fallback is the smaller, faster model, which is
what you get if the key is absent; the shipped example sets the larger,
more accurate one, so anyone who copied `config.toml.example` runs that.
Check your own file. See
[Choosing an embedding model](#-choosing-an-embedding-model) and
[Choosing an entailment model](#-choosing-an-entailment-model).

**`docling_formulas` is not the only formula switch, and probably not the
one you want first.** It configures the *enrichment* parse, which writes
`content/docling/`. The corpus parse, the one `chitragupta/retrieval.py`
indexes and a drafting skill reads, has its own
[`[parser].formulas`](#-formulas-and-why-it-is-not-the-enrich-key).

**`keywords_path` names a generated artefact, not a file you write.**
The `extract-keywords` stage regenerates it on every run from the papers'
own `Keywords:`/`Index Terms` lines, so a hand-edit is overwritten. Promote
a phrase worth keeping into `content/seed_topics.toml`
([Seed topics](#-seed-topics-organising-the-corpus-by-phrases-you-wrote)).

### 🔭 The three that size a search

`embed_top_k`, `embed_max_passages_per_source` and
`embed_overfetch_multiplier` are the stages of
`chitragupta.enrich.embed_index.search()`, in order:

```text
over-fetch (k x multiplier)  ->  [rerank]  ->  cap per citekey  ->  keep k
```

[CORPUS-SEARCH.md](CORPUS-SEARCH.md) draws that and explains the order.

- **`embed_top_k`**: how many passages come back when a caller does not
  say. A **default, not a ceiling**: the CLI's `--k` and a skill's own
  `k` win.
- **`embed_max_passages_per_source`**: how many chunks of one citekey
  may appear among those `k`. **This, not reranking, is the lever for
  source diversity**: lower it to `1` for maximal diversity, or raise it
  when one thorough paper deserves more than three chunks.
- **`embed_overfetch_multiplier`**: how much deeper than `k` Chroma is
  asked, so that dropping a dominant paper's excess chunks *promotes*
  another paper's chunk instead of only shortening the list. Raise it
  when the right paper never comes back at all. It is the expensive knob
  when `rerank` is on, since the reranker scores the whole pool.

**All three are validated at load**: a value below 1 raises, because
`embed_top_k = 0` would otherwise read like an empty corpus.

**`rerank`** turns on a cross-encoder that reorders the over-fetched
passages **before** the cap. Off by default because it leaves recall@5
and diversity unchanged at 2.5x a search call's cost on a GPU (5.75x on
a CPU); recall@3 rises from 129 to 139 of 256, so turn it on if you read
only the top three hits. It rebuilds nothing. It also gates
`python -m chitragupta.corpus discover`'s precision tier: off, that tier
is skipped and the model is never loaded; on, but with a model that will
not load, the fused order stands with a note.

**`rerank_model`** names that cross-encoder, and is read only when
`rerank` is on. The `bge-*` / `e5-*` prefix warning under the embedding
model does not apply here, because a reranker scores both texts jointly.
[CORPUS-SEARCH.md](CORPUS-SEARCH.md#-choosing-a-reranker) has the
measured candidates and the rejected ones.

**`support_premise_topk`** caps how many premises `review support`
scores per citation. Uncapped, the entailment model sees one pair per
quotable passage, **725-887 pairs per citation**, which is what a review
pass costs
([PERFORMANCE.md](PERFORMANCE.md#-what-supports-cost-actually-tracks)).
A number pre-ranks premises by the lexical overlap `[provenance]` bands
and sends only the top *k*, 5.3x to 102x fewer pairs. **It is off
because it was measured and damages the report**: over two real drafts
the pre-ranker agreed with the entailment model on the supporting
passage for only **56.5% of citations at k = 128** (14.6% at k = 8), and
claims scoring 0.995 uncapped came back at 0.138, the draft's worst
finding (`bench/RESULTS.md`, 2026-09-09). There is no recommended value;
`bench/bench_support_topk.py` compares a capped run with the uncapped
one on your drafts, which is not the same as being right (issue #757).

### 🧭 `[discover]` -- from a phrase to a topic

Read by `python -m chitragupta.corpus discover`'s resolution ladder.

| Key | Env var | Accepts | Default in code | In `config.toml.example` |
| --- | --- | --- | --- | --- |
| `min_similarity` | `DISCOVER_MIN_SIMILARITY` | number, cosine similarity | `0.35` | `0.35` |

How close the best topic centroid must sit to a free phrase before the
hybrid rung claims the phrase for that topic instead of falling back to
paper search. It gates only the semantic evidence: a BM25 hit on the
topic's own vocabulary claims the phrase regardless, and without the
`enrich` group the floor has no effect. 0.35 is a starting point, not a
measurement; [TOPIC-DISCOVERY.md](TOPIC-DISCOVERY.md) has the ladder and
the gold set meant to tune it.

## 🔤 How values are parsed

**Booleans from the environment.** In TOML, write `true` / `false`. From
an environment variable, `1`, `true`, `yes` and `on` mean true, and `0`,
`false`, `no`, `off` and an empty value mean false (case-insensitive).
**Any other word raises**, naming the setting, so `PARSER_OCR=ture` is
reported rather than read as false. The words are parsed, not cast,
because `bool("false")` is `True` in Python.

**A wrong TOML type raises, once a value is present.** A missing key
takes its default, but `ocr = "true"` (a string), `path = 123`, or
`timeout = "9.5"` and `timeout = true` raise, naming the key, the
environment variable and what was expected. Quote strings; don't quote
booleans or plain numbers.

**Whole-number settings reject a fractional value but tolerate a quoted
whole number.** `topic_min_cluster_size = 3.9` raises instead of
truncating; `topic_min_cluster_size = "3"` works, the same as `workers`
and the three search-sizing settings.

## 🗒 Notes on individual settings

### ⚖ `backend`: pdftotext or docling

| Backend | Dependency | Page boundaries? | Quotable passages? | Speed |
| --- | --- | --- | --- | --- |
| `pdftotext` (default) | `poppler-utils` on `PATH` | **Yes**: form feeds between pages | No: reading order is lost | Fastest |
| `docling` | `docling`, `enrich` group | **Yes**: form feeds between pages | **Yes**: writes a passage sidecar | ~42x slower; see [PERFORMANCE.md](PERFORMANCE.md#-parserbackend----pdftotext-or-docling) |

Both keep page boundaries, which `chitragupta/review/verbatim_check/`
splits on to report a verbatim run's page. What separates them is
quoting: `pdftotext -layout` loses reading order, so an excerpt can
splice two columns and the passage ladder refuses to quote from it.
`docling` keeps reading order in `content/parsed/<citekey>.passages.json`,
so this setting alone buys quotable passages
([CITATION-PROVENANCE.md](CITATION-PROVENANCE.md#-what-the-corpus-layer-keeps-when-it-uses-docling),
[LADDERS.md](LADDERS.md#-ladder-1-evidence-passages));
[PDF-PARSER.md](PDF-PARSER.md) has the full comparison.

**`backend = "docling"` does not fold docling into the enrichment
layer.** The corpus layer (`chitragupta/pdf_text/`, on `sync`) writes
`content/parsed/` for BM25; the opt-in
`chitragupta/enrich/docling_parse.py` writes structured Markdown into
`content/docling/`, **always** with docling, over the same ledger
documents. With this setting on `docling`, the enrichment stage adopts
the corpus layer's output, a file copy in place of 6.65s per document,
and parses for real only when the corpus layer wrote no text, when
`[enrich].docling_images` is on, or when the PDF is newer than the
artefacts.

### 👷 `workers`, and how it is clamped

The resolved count is the smallest of what you asked for, what the
machine can sustain, and how many documents need parsing, never below 1.
"What the machine can sustain" counts the CPUs **this process
may run on**, and for `docling` divides it by 4:

| CPUs available to the process | 4 | 8 | 16 | 48 |
| -------------------------------- | - | - | -- | -- |
| `workers = "auto"` resolves to | 1 | 2 | 4 | 12 |

**That divisor of 4 is measurably too conservative**: 32 workers run
**1.41x faster** than the 12 it allows on 48 CPUs, and 48 are no worse.
The data supports "much smaller than 4", not a specific value, so it has
not been changed; see
[PERFORMANCE.md](PERFORMANCE.md#-parserworkers----document-level-parallelism).

Asking for more than the machine allows is **clamped and said out loud
on stderr**, never silently obeyed or ignored. docling's internal thread
count is divided down to match. **The clamp cannot see** a cgroup CPU
*quota* (`docker --cpus=2`) or RAM; set an explicit number for either.

`docling` gets processes and `pdftotext` threads. Ledger writes stay on
the main process, and results print in bibliography order.

### 🖥 Using more than one GPU

There is nothing to configure. With `docling` and more than one worker,
each worker claims one CUDA device round-robin; without this, docling's
`AcceleratorDevice.AUTO` would put every worker on `cuda:0`. Restrict
the cards with `CUDA_VISIBLE_DEVICES`. Figures in
[PERFORMANCE.md](PERFORMANCE.md#-multi-gpu----nothing-to-configure).

**A card with under 2.5 GiB free is skipped** (a worker's ~1.7 GiB of
models plus its CUDA context), and the run says so on stderr:

```text
  WARNING skipping cuda:0 (0.6 GiB free) -- under 2.5 GiB free, which is
  not enough for a docling worker. Parsing on cuda:1,2,3.
```

Without the check, workers that cannot get device memory fail documents
in seconds and so take most of the corpus. If every card is busy the run
parses on the CPU, as does a worker that runs out of device memory
mid-run.

### 🚫 Why `fork` is not an option

By the time the pool is built the process holds two live sqlite
connections (the run lock and the ledger), and SQLite's documentation
says not to carry an open connection across `fork()`. `forkserver`
starts its server as a fresh interpreter and measured **no slower** than
`fork`, so nothing is given up.

Both available start methods re-import the calling program's `__main__`
in each worker, so a script of your own driving `sync` or `parse_corpus`
must guard its top level with `if __name__ == "__main__":`.

### ⏱ The two timeouts are not the same guard

- **`document_timeout`** bounds one document. For `pdftotext`, here and
  in its runs outside `sync`, it is a real subprocess kill. For
  `docling` it is the library's own check *between* pipeline stages: it
  bounds a slow document but cannot interrupt a hang inside one stage.
  A casualty is named in `sync`'s summary (`WARNING: 2 document(s) hit the 120.0s
  [parser].document_timeout and were not parsed: <citekeys>`) and **not**
  retried, since the same setting would reach the same answer. Raise it
  and re-run with `--reparse`.
- **`stall_timeout`** bounds a *parallel run* by asking whether **any**
  document has completed recently, which separates a hung worker from a
  slow document far better than a per-document number. It applies only
  when `workers > 1`. It is on by default because the failure it catches
  (a run that never finishes) is one a user hit, and a false positive is
  cheap: a warning prints at half the budget, and casualties are recorded
  as transient failures and **retried** next run.

Either way a timed-out document is reported as a failure, never silently
truncated. Choosing a safe value means knowing your slowest legitimate
document; see
[PERFORMANCE.md](PERFORMANCE.md#-parserdocument_timeout----what-a-safe-value-looks-like).

### ⚠ The parse-quality guard

`sync` warns when an implausible share of a freshly extracted document's
words are unusually long, the signature of a backend that lost the
spaces between words. `chitragupta/retrieval.py` tokenises on runs of
`[a-z0-9]`, so two run-together words become one token that matches
neither. `long_word_chars`, `long_word_ratio` and `min_tokens` are its
thresholds. It is **a warning, never a failure**, and it will not catch a
bad `ocr` choice: it finds run-together words, not content that never
arrived.

### 🧮 `formulas`, and why it is not the `[enrich]` key

Docling drops an equation's content unless its formula-recognition model
runs, leaving the literal `<!-- formula-not-decoded -->` where the
mathematics was:

```text
…we define the Network Overhead (NO) metric as… More formally:

<!-- formula-not-decoded -->

We clarify that the NO(tk) metric above quantifies…
```

On a 497-document corpus with this key off, 148 documents carried the
marker. `chitragupta/retrieval.py` indexes `content/parsed/*.txt` and
**nothing else**
([RETRIEVAL.md](RETRIEVAL.md#-a-papers-own-bibliography-is-not-indexed)),
so with this off an equation is absent from the only artefact a drafting
skill reads. On, it is LaTeX, which the index already handles.

**Why this is not `[enrich].docling_formulas`.** The two keys set the
same docling option on **two different parses**: this one writes
`content/parsed/`, the `[enrich]` one `content/docling/`. They are
deliberately separate: the corpus parse matters to someone who never
installs the enrichment group, and `chitragupta/pdf_text/` reading an
`[enrich]` setting would cross the layer boundary
[ARCHITECTURE.md](ARCHITECTURE.md) draws. Set both for decoded formulae
in both places.

Off by default for the same economics as `ocr`: an extra model download
and an extra pass per page. Run
`python -m chitragupta.corpus sync --reparse` after changing it.

**On a GPU host it can fail silently** without `python3-dev` and `gcc`
(installed by the `os-deps` stage): every formula comes out as the
marker on a run that reported success.
[PDF-PARSER.md](PDF-PARSER.md#-docling-silently-empties-every-formula-on-a-gpu-host)
has the diagnosis and the recovery for both keys, which differ.

### 🖼 `docling_images`

Extracts figure bitmaps into `content/docling/<doc>_artifacts/`, plus a
`<doc>.figures.json` giving each figure's page, caption, bounding box and
the exact string to cite it by. The box is in **page points**, exact and
independent of the render scale; a crop's pixel size is that box times
`docling_image_scale`.

**It indexes figures, not every picture.** A picture both caption-less
and under 33 points (about 12mm) on either side gets no record and no
PNG: publisher logos, ORCID icons and badges, **38.5% of the 8,769
crops** across 497 papers. Both tests apply together because neither
alone discriminates, and the floor is in page points, so changing the
scale does not reclassify the corpus.

The images are a **reading aid** for checking a draft against its
sources. They are never inserted into a draft: having a paper in your
library grants no right to reproduce its figures, and a figure's
copyright is not the paper's citekey to grant. See `DEVELOPER.md`'s
"Figures and copyright" (git checkout only).

Changing this invalidates the whole docling cache, so the next run
re-parses the corpus. Costs in
[PERFORMANCE.md](PERFORMANCE.md#-enrichdocling_images----disk-and-a-full-re-parse).

## 🧠 Choosing an embedding model

Documents are cleaned before they are chunked: the reference list, which
makes two papers similar for citing the same work, is dropped along with
bare emails, URLs, DOIs, copyright lines and page numbers. Nothing else
is removed: stop-word removal and lowercasing destroy multiword domain
terms. A document with no detectable `References` heading (9% here)
keeps its whole text.

`chitragupta/enrich/embed_index.py` calls
`SentenceTransformer(config.EMBEDDING_MODEL).encode(...)`
**symmetrically**: the same call embeds a 200-word chunk (40-word
overlap) and a query, with no prefix on either side. That decides which
models are drop-in.

### ✅ Drop-in

| Model | Dimensions | Cost | Best for |
| --- | --- | --- | --- |
| `sentence-transformers/all-MiniLM-L6-v2` (code default) | 384 | ~22M params, fast even on CPU | Small corpora, quick iteration, CPU-only machines |
| `sentence-transformers/all-mpnet-base-v2` (example default) | 768 | ~109M params, ~4-5x MiniLM; slower on CPU | Better general-purpose semantic quality |
| `sentence-transformers/multi-qa-mpnet-base-dot-v1` | 768 | Same as `all-mpnet-base-v2` | Short query against long passage, the closest match to `search()`; slightly weaker on generic similarity |

All three are trained for prefix-free use, which is what the symmetric
call needs. The 768-dimension models double per-chunk storage in Chroma.

### 🚫 Not without a code change first

- **`allenai/specter` / `specter2`**: built for whole-paper similarity
  from title `[SEP]` abstract, not for 200-word body chunks. Using it
  well means feeding it titles and abstracts, and it then answers "which
  papers are alike", not "which chunk answers this query".
- **BAAI `bge-*` and `intfloat e5-*` families**: they expect literal
  `"query: "` / `"passage: "` prefixes, which nothing here adds. As-is
  they **will not error; they will silently underperform**, the worst
  failure of the set. Adopting one needs prefix-handling code.

### 🔄 Switching

Edit `[enrich].embedding_model`, or set `EMBEDDING_MODEL=...` for one
run, then rebuild the index:

```bash
python -m chitragupta.enrich --stages embed
```

The model downloads on first use (needs network), and Chroma's existing
collection is **not** re-embedded automatically.

## 🧠 Choosing an entailment model

`chitragupta/entailment.py` scores `(premise, hypothesis)` pairs with
`CrossEncoder(config.ENTAILMENT_MODEL).predict(pairs)`: a citing
sentence's claim against a passage of the cited source (never a
`section_header`, which asserts nothing). It reads the probability by
looking up `"entailment"`, case-insensitively, in the model's own
`id2label`, not by column index, which makes every candidate below a
drop-in.

**A checkpoint that names no entailment label is refused, not guessed
at.** `LABEL_0`/`LABEL_1`/`LABEL_2`, or a non-NLI cross-encoder such as
a reranker, raises `entailment.EntailmentLabelError` naming this
setting, the model and its labels. Which column is entailment is not
recoverable from `LABEL_2`, and guessing would decide on a coin flip
whether a claim reads as supported.

### ✅ Drop-in cross-encoders

All three were loaded via `sentence_transformers.CrossEncoder` (no extra
install beyond the `enrich` group) and timed on a batch of 8 pairs;
accuracy is the published MNLI-mismatched figure.

| Model | Parameters | Batch of 8 | MNLI-mm |
| --- | --- | --- | --- |
| `cross-encoder/nli-deberta-v3-small` (code default) | 141,897,219 | 0.337s | 87.55 |
| `cross-encoder/nli-deberta-v3-base` (example default) | 184,424,451 | 0.346s / 0.351s | 90.04 |
| `cross-encoder/nli-MiniLM2-L6-H768` | 82,120,707 | 0.234s | 86.89 |

At this batch size fixed overhead dominates, so `-base` costs memory and
download, not latency, for +2.49 points. MiniLM2 suits a CPU-constrained
machine but is not the default: the accuracy it gives up is real on a
citation-integrity aid. `cross-encoder/nli-deberta-v3-xsmall` publishes
87.77 but was not measured, so it stays an open question.

### 🚫 Not without a code change first, for entailment

**`facebook/bart-large-mnli` and the `MoritzLaurer/*` zero-shot-MNLI
models** are `transformers.pipeline("zero-shot-classification")` models
(per their model-card metadata), not `CrossEncoder`-wrapped ones. Using
one would mean a second ML code path beside the `CrossEncoder` path
`chitragupta/entailment.py` and `chitragupta/overlap_chroma.py` share.
This is an API-shape rejection; no claim is made about their accuracy.

### 🔄 Switching entailment models

Edit `[enrich].entailment_model`, or set `ENTAILMENT_MODEL=...` for one
run. There is no index to rebuild: the model loads lazily and nothing it
produces is cached, so a switch takes effect on the next claim-support
check. It downloads on first use, like an embedding model.

## 🌱 Seed topics: organising the corpus by phrases you wrote

`content/seed_topics.toml` is an optional list of topic phrases in your
own words. Without it, the `bertopic` stage clusters unsteered and the
`seed-topics` stage reports itself skipped.

```toml
# content/seed_topics.toml -- start from assets/style/topics.toml.example
topics = [
    "digital twin",
    "structural health monitoring",
]
```

**A phrase is one topic and is never split into words**: it is embedded
whole and compared against each document, unlike BERTopic's
`seed_topic_list`, where "monitoring" alone would match every paper with
a monitoring section.

**You write them.** Your Zotero collection names
(`chitragupta corpus ledger --collections`) are a good start, minus
shelves such as "To read": nothing can tell those apart mechanically,
which is why the file is hand-written.

**Two files feed the matching.** The `seed-topics` and `converge` stages
read the union of `content/seed_topics.toml` (yours, never overwritten)
and `content/keywords.toml` (the `extract-keywords` stage's output,
regenerated on every run), deduplicated case-insensitively with your
spelling winning. On this project's 497 documents your list alone
reached 69.4% coverage and the union 98.6% (`bench/RESULTS.md`,
2026-09-03c). With neither file the stage reports itself skipped.

**There is no limit** to the number of phrases, and they cost one cosine
per document each. Seeds are matched *after* clustering, never fed into
it, so naming a topic does not consume an emergent one. Feeding them in
through BERTopic's `zeroshot_topic_list` was measured and rejected: nine
phrases took the corpus from 81 emergent topics to 53.

### ▶ Running it, and reading the result

```bash
chitragupta enrich --stages seed-topics   # needs the enrich group
chitragupta corpus topics                 # stdlib only, no venv, no GPU
chitragupta corpus topics --topic "digital twin"
```

The report goes to `content/topic_seeds.json`. **A paper appears under
every topic it matched**, unlike `content/topics.json`, where BERTopic
assigns one id. The report also lists every document that matched **no**
topic: the part of your corpus your list does not yet describe.

`[enrich].seed_topic_max_papers` (`25`) is the selection rule: each
phrase is ranked against **its own** scores and the best N kept.
`seed_topic_min_similarity` (`0.15`) is only a noise floor. A single
absolute cutoff was rejected because every phrase has its own score
scale: at `0.35`, `Standards` (a real 25-paper collection, max 0.295)
returned nothing while `Digital Twin` (median 0.338) returned half the
corpus. The report prints how many papers were *considered* ("25 of 340
papers"). The floor drops labels with no semantic content but not a
shelf label that also describes papers, such as `Reviews and Surveys`.

### 🔗 One topic set, from your phrases and the corpus's own

The `converge` stage writes `content/topic_set.json`, joining your
phrases and the emergent topics into one shape:

```json
{"label": "structural health monitoring", "provenance": "seed",
 "topic_id": 41, "members": [{"citekey": "...", "score": 0.62}]}
```

**Your name wins**: an emergent topic within
`[enrich].topic_converge_similarity` of one of your phrases is renamed by
it. When several phrases match one topic the closest wins (ties broken
on the phrase text); when several topics match one phrase each keeps its
own row, since merging would discard granularity the clustering found.
A phrase matching no topic still appears with `"topic_id": null`, and
`uncovered` names papers no topic reached. The stage re-runs no
clustering; run it after `bertopic` and `seed-topics`.

### 🕸 The topic graph

The `topic-graph` stage writes `content/topic_graph.json` after
`converge`; only display reads it. [TOPIC-DISCOVERY.md](TOPIC-DISCOVERY.md)
has the reasoning behind its two settings:

- `[enrich].topic_graph_p_value`: how surprising a shared-member count
  must be (hypergeometric tail against the corpus size) before two
  topics get an overlap edge. A significance level, so it needs no
  re-tuning as the corpus grows.
- `[enrich].topic_graph_neighbors`: semantic edges survive only between
  mutual top-k neighbours, because a global floor floods the dense region
  of the topic space or starves the sparse one.

### 🏷 What a topic is called

A topic's name comes from its most distinguishing terms. Two things are
excluded from that vocabulary, without changing which papers group
together:

- **This corpus's own author names**, read from the ledger's
  `bib_fields`. `[enrich].topic_exclude_author_names` turns it off.
- **Citation and URL scaffolding** (`et al`, `doi`, `www`, `arxiv`).

Without them the top-ranked topic was named
`werner kritzinger, fraunhofer austria`, a name in the prose of papers
discussing his work, which dropping the reference list cannot fix. The
cost: 5 of 1,277 surnames are ordinary words (`black`, `brown`, `can`,
`park`, `wood`). A cited author not in your library (`drath`,
`kockmann`) can still name a topic, since widening the list would mean
guessing names from reference prose.

### 🔬 How many topics, and how deep

`[enrich].topic_min_cluster_size` (3), `topic_min_samples` (2) and
`topic_neighbors` (5) set the granularity of the emergent topics,
measured on this project's 497-paper corpus with everything else fixed:

| `topic_min_cluster_size` | topics | outliers | median topic size |
| --- | --- | --- | --- |
| 10 | 13 | 27% | 19 |
| 5 | 25 | 19% | 13 |
| 3 | 50 | 12% | 6 |
| 3, with `topic_min_samples = 2` | 75 | 10% | 5 |

The outlier rate **falls** as topics get finer. Small-corpus clamps only
ever reduce these values, since UMAP's spectral initialisation fails
when `n_neighbors >= n_samples`.

### 🧩 Topics a paper belongs to, beyond the one it is assigned

`content/topics.json` records `assignments` (one topic id per document)
and, with `[enrich].topic_distribution` on, `memberships`: every topic a
document belongs to, with its strength. Here **140 of 497 papers belong
to more than one topic**, and the scalar discards 222 memberships.

`assignments` is **which cluster a document was put in** (density, what
HDBSCAN decided); `memberships` is **what the paper is about**
(similarity to each topic's descriptor). They can differ, so **the
assigned topic is always present in a document's memberships**.

The strengths are cosine to each topic's descriptor (its members'
centroid, on mean-centred embeddings, since raw cosines bunch together
in a one-subject corpus), recorded as `membership_mechanism`. Three
alternatives were measured and rejected: HDBSCAN's own soft clustering
answers the density question nearly binarily for a core point (1.64
topics per paper, 25% of papers plural, on a library where 637 of 642
papers carry hand-made labels across 95 collections); BERTopic's
`approximate_distribution` separated almost nothing (top-share 0.03);
and a Gaussian mixture returned near-certain single assignments
(`bench/RESULTS.md` has the table).

`topic_membership_ratio` (`0.5`) is how strong a topic must be relative
to the document's strongest, and `topic_membership_max` (`8`) caps the
list for a document similar to almost everything. A cap of `3` was
measured too low: it put 387 of 497 documents at exactly 3, so the cap
decided instead of the ratio.

None of these gate anything: no run fails on them and no draft is
blocked by one (`docs/HOUSE-STYLE.md` R3).

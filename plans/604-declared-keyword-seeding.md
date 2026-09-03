# Declared-keyword extraction and seeding (#604, #605, #606)

Status: **done.** Written 2026-09-03. Issue #604 landed in PR #629
(6.65.0), issue #605 in PR #630 (6.66.0), and issue #606's verification
-- recorded as
`bench/RESULTS.md`'s 2026-09-03e entry -- in the PR that carries this
line (6.66.1). What changed on the way: the shipped extractor detects
253 of 497 declarations against the scratch script's 262 and keeps a
slightly different phrase tail (34 of 40 shared at the defaults); the
benchmarked coverage figures reproduced exactly for the topics-only and
keywords-only arms and 0.4pp lower for the combined one.

**Written for** the implementer of issues #604 (an `extract-keywords`
enrichment stage sourcing each paper's own declared
`Keywords:`/`Index Terms` line), #605 (unioning the extracted phrases
with `content/seed_topics.toml` in the `seed-topics` and `converge`
stages), and #606 (confirming the shipped pipeline reproduces
`bench/RESULTS.md`'s 2026-09-03c coverage figures). One plan for the
three because they share one contract -- the shape of
`content/keywords.toml` -- and deciding it three times would invite it
to drift.

**Assumed**: the issues' own Problem Statements and bench entries
(2026-09-03c/d) are correct as measured; `content/topic_keywords.toml`
in this project's own corpus is the reference output the shipped stage
must reproduce at the defaults; TF-IDF extraction is out of scope (built,
benchmarked, rejected -- `bench/extract_keywords.py` stays as the record
of that).

**Not covered here**: consuming the phrases anywhere beyond
`seed-topics`/`converge` (the topic graph inherits the effect through
`content/topic_set.json` and needs no change -- #605 confirmed that by
reading it); any fallback extraction for a paper with no detectable
declaration (skipping is the design, not a gap).

## The contract the three issues share

`content/keywords.toml` is a **generated artifact, regenerated fresh on
every `extract-keywords` run** -- machine output like
`content/topics.json`, not a hand-curated file like
`content/seed_topics.toml`. It is written in the exact `topics = [...]`
shape `chitragupta/seed_topics.py:load()` already reads, so #605 needs
no parser change: `seed_topics.load(config.KEYWORDS_PATH)` on a missing
file returns `()`, which is the no-op every caller already handles. A
phrase someone wants to keep permanently is promoted by hand into their
own `seed_topics.toml`.

## #604: the `extract-keywords` stage

New module `chitragupta/enrich/keyword_extract.py`, pure text
processing over `doc_vectors.corpus_texts()` -- no model, no GPU, no
enrich-group import (the parsed text is read by the same
`embed_text.get_text()` path every stage uses).

Extraction, per document (constants from `bench/RESULTS.md`
2026-09-03c, which measured them on this corpus):

- Scan the first **200 lines** for the first line whose text opens with
  `keywords` or `index terms` (case-insensitive, leading Markdown
  decoration and whitespace allowed) -- the window is what keeps a
  References-section false positive out.
- Truncate the payload after the marker to **300 characters** before
  splitting -- Docling occasionally flattens a whole PDF column
  (declaration + affiliations + abstract) into one line.
- Split on the first separator the line itself uses, in priority
  order: middle dot (`·`), pipe (`|`), semicolon, comma. Fall back to a
  lowercase-to-uppercase word-boundary split only when none is present
  (27% of detected declarations on this corpus had no separator at
  all); the fallback is lossy on multi-word phrases and accepted as
  such.
- Lowercase each phrase, collapse internal whitespace, drop any phrase
  longer than **60 characters** or empty after cleaning.
- A document with no detectable declaration contributes nothing and is
  not an error; the stage's report counts how many documents had one.

Aggregation, across the corpus:

- Count **distinct documents** declaring each phrase (a paper repeating
  a phrase never inflates it).
- Keep phrases declared by at least `keyword_min_df` documents, rank by
  that count (ties alphabetical), keep the top `keyword_top_n`.
- Write the survivors **sorted alphabetically** (the artifact is read
  by a person; rank decided membership, not presentation), with a
  header comment saying the file is generated and will be overwritten.

Config, declared exactly like `SEED_TOPIC_MAX_PAPERS`/`ACRONYMS_PATH`:

| Key | Env var | Default |
| --- | --- | --- |
| `[enrich] keyword_top_n` | `KEYWORD_TOP_N` | `40` |
| `[enrich] keyword_min_df` | `KEYWORD_MIN_DF` | `2` |
| `[enrich] keywords_path` | `KEYWORDS_PATH` | `"keywords.toml"`, resolved under `CONTENT_DIR` unless absolute (`CONTENT_DIR / value`, the rule `CONTENT_DIR` itself uses) |

Stage plumbing: register in `stages.py`'s `STAGE_FUNCS` and
`__main__.py`'s `STAGE_ORDER` **between `bertopic` and `seed-topics`**
(the issue's "before seed-topics"; it needs only parsed text, but the
slot documents what consumes it); add to `_scope.py`'s `SCOPE_REFUSED`
and `CORPUS_STAGES` (whole-corpus artifact, same bucket as `bertopic`).

Status vocabulary (docs/LADDERS.md owns the exit-code contract):

- `skipped` -- no document has any parsed text at all (nothing to scan;
  same word `seed-topics` uses for "nothing to do").
- `ok` -- otherwise, **including** a corpus where no document declared
  anything: the stage then writes an *empty* `topics = []` file, and the
  report's counts (`documents`, `with_declaration`, `phrases`) say so.
  Not `partial`: a paper without a declaration is the ordinary state of
  half this corpus, not a failure to parse it.
- `error` is left to the orchestrator's blanket exception handler; the
  stage abandons nothing by design.

## #605: union at the two call sites

`stages.py`'s `stage_seed_topics` and `stage_converge` each pass
`seed_topics.load()` today; both change to a shared local helper that
unions `seed_topics.load()` with `seed_topics.load(config.KEYWORDS_PATH)`
-- case-insensitive, first spelling wins, order preserved (the
hand-written list is loaded first, so its spellings win), the rule
`bench/bench_keyword_seed_topics.py:_dedup()` already implements and
`load()` itself applies within one file. `seed_topics.py` is untouched:
its contract stays "the author's own list", and the union lives where
"which phrases flow into this run" is decided.

`topic_seeding.run_stage()`'s skip message stops naming
`config.SEED_TOPICS_PATH` alone and reports that neither source had
phrases.

## #606: verification, no production code

Run the real `chitragupta enrich --stages extract-keywords,seed-topics,converge`
against this project's own synced corpus (`CONTENT_DIR=/workspace/content`)
and compare:

- `content/keywords.toml` at the defaults vs
  `content/topic_keywords.toml`'s 40 phrases (same set, order aside).
- `content/topic_seeds.json` coverage vs the 2026-09-03c figures
  (69.4% / 97.6% / 98.6%), embedding-model rounding tolerated, logic
  differences treated as findings.

Record the confirmation (or correction) as a new dated `bench/RESULTS.md`
entry, and update `bench/extract_keywords.py`'s docstring to say plainly
that the shipped stage extracts from declared keywords, not TF-IDF, so
the script reads as the measured alternative rather than the
implementation.

## Shipping order

Three PRs, one per issue, each independently green: #604 (minor bump --
new stage, new config keys), #605 (minor bump -- behavior change in two
stages), #606 (patch bump -- bench/docs only). The docs sweep for #604
is the wide one: the stage count ("six stages") is stated in
`README.md`, `docs/CLI.md`, `docs/LADDERS.md`, `DEVELOPER-AGENTS.md`,
the enrich `--help` text, and the architecture diagrams' `.mmd`/`.svg`
exports.

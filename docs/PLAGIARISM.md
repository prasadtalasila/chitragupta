# Plagiarism / verbatim-reuse detection

Status: **implemented, one detection tier of a planned three.** Written
2026-08-10.

**Written for** someone deciding whether `src/review/verbatim_check.py`'s
`overlap`/`scan` modes are enough review before presenting a draft, or
tuning `--min-run`/`--gap`, or choosing `[parser].backend`. **Assumed:**
a synced corpus (`python -m src.corpus sync`) and a citekey-verified draft
(`python -m src.draft gate`). **Not covered:** how to invoke the tools
day to day -- that is [CLI.md](CLI.md)'s job.

The three tiers below are the one **tier set** in this project whose
options are not mutually exclusive ([ARCHITECTURE.md](ARCHITECTURE.md#ladders-and-tiers)):
nobody picks one, every built tier runs, and the findings are unioned
with each labelled by the tier that produced it. That matters for how a
result is read -- an unbuilt tier contributes nothing and says nothing,
so the gap between "what tier 1 found" and "what is actually borrowed"
is the subject of the next section rather than a footnote to it.

## What "plagiarism" means here, and what it deliberately doesn't

This pipeline draws citekeys from a synced bibliography and gates on
them (`src/citation_gate.py`): a draft cannot cite a source that isn't
real. That answers "is every citation genuine" and says nothing about
"does the wording around a citation actually belong to whoever it credits,
or to someone else". `src/review/verbatim_check.py`'s two modes exist to
answer the second question, mechanically, over what is currently checked
verbatim word-n-gram reuse.

**Verbatim reuse only.** Paraphrase -- the same sentence skeleton, a
synonym swapped every few words, function words shuffled -- is invisible
to an exact n-gram match by construction. That matters more than it would
elsewhere in this project because **the drafts this pipeline produces are
LLM-written**, and literal paraphrase is an LLM's default failure mode
when it drifts too close to a source, not an edge case. Treat a clean
`scan` as "no exact or near-exact copying found", never as "no borrowed
wording found" -- see [Where this sits in a bigger plan](#where-this-sits-in-a-bigger-plan)
for the tiers that close that gap. That is this tier set's
characteristic failure: the missing tiers do not announce themselves, so
a thin result and a thorough one look identical.

## The two tools, and when each is right

| | `overlap` | `scan` |
|---|---|---|
| Compares against | One citekey's own source, in paragraphs citing it | The whole corpus, against the whole draft |
| Sees an uncited source's wording? | No -- structurally cannot, by design | Yes |
| Sees connective prose citing nothing? | No | Yes |
| Typical use | Quick check on one citation while drafting | Full-draft pass before presenting |
| Cost | Sub-second, even cold | ~27s first run on this corpus (497 docs); sub-second every run after |

Both belong to the **review layer** and are advisory, not gates: a successful run exits 0 whether it
found anything or not, and neither is wired into a hook or blocks a
draft. (A malformed invocation -- a bad flag, a missing argument --
exits 2, ordinary CLI-usage error handling, not a verdict on the draft.)
Whether long verbatim runs should gate is a later, deliberately separate
decision (issue #110's Phase 2) -- these tools only produce the findings
that decision would be tuned against.

## How it works

### Fingerprinting: word n-grams, hashed deterministically

Both tools run on top of `src/overlap_index.py`'s corpus-wide fingerprint
index. Every parsed document is tokenized into lowercase `[a-z0-9]+`
words, and every 8-word sliding window ("gram", `n=8`, the smallest unit
either tool can detect) is hashed to a 64-bit integer with a rolling
polynomial hash over each word's `blake2b` digest -- deterministic across
processes and runs, unlike Python's built-in `hash()`, which is
per-process-salted and could not be cached to disk at all. At the
corpus's real scale (~7,000,000 grams), the birthday-bound collision
probability at 64 bits is on the order of 1e-6: real, but small enough
not to matter in practice.

Two disk caches, both under `content/overlap/` (gitignored, regenerable):
a per-document fingerprint (`docs/<citekey>.fpr`, keyed by the ledger's
`pdf_hash` plus the parsed file's own stat -- so a `sync --reparse` or a
backend switch invalidates it, a `pdf_hash`-only key would not), and a
merged, binary-searchable corpus-wide index (`index.bin`/`index.json`,
sorted gram hashes with parallel citekey/page/position postings arrays).
`overlap` only ever needs the first; `scan` builds and reuses the second.

### `overlap`: one citekey, exact-match runs

For one citekey, builds a `{gram_hash: page}` map from that document's
fingerprint and slides the draft's own paragraphs (that cite the
citekey) across it, reporting maximal verbatim runs -- `n` or more words
in an unbroken match. Fast because it never looks past the one source
named.

### `scan`: the whole draft against the whole corpus

Normalizes the entire draft once (masking code fences/inline code the
same way `src/citation_gate.py` does, and the generated References
section, so a source's own title page never reads as "overlap with
itself"), then for every draft position looks up **every** posting for
that position's gram hash across **every** parsed document -- not just
ones the surrounding paragraph cites.

`--write` also files the findings as
`content/review/<topic>/<stem>.verbatim.md`, beside the same draft's
provenance and coverage reports -- printing stays the default, since the
usual use is a question asked and answered in one sitting. The written
report opens with a banner saying it is not a verdict and repeats the
"not a clean bill of health" caveat above, so a file found on disk months
later cannot be read as a clearance. It carries no timestamp, so two runs
over an unchanged draft and corpus diff to nothing.

`--json` prints the same findings as data instead of as text, and
`--write` files them as the report's `.json` sibling; both carry the same
not-a-verdict notice and the same absence of a timestamp. Each payload
finding also carries `severity` -- the same `long`/`short`/`quoted`
bucket the written report below groups by, derived the same way, so a
programmatic consumer -- the remediation loop below, an eventual gate --
reads the same severity a human reviewer sees, rather than regex-parsing
the printed lines or recomputing the threshold itself. It also carries
`id`, a position-free name for the finding, and four fields that locate
it in the draft as written. The fields, and the one that is easy to
misread (`start` is a word offset into the normalised stream, not a
position in the draft file, and the locators are what to use instead),
are in [CLI.md](CLI.md#python--m-srcreview-verbatim).

Matches are grouped by `(citekey, diagonal)`, where `diagonal =
source_position - draft_position` and `source_position` is a *global*
token position in the source document, not reset at each page break
(`src/overlap_index.py`, #131). Two matches on the same diagonal are "in
step" with each other even with non-matching words between them, so a
**gap-tolerant merge** -- same idea as seed-and-extend alignment in the
plagiarism-detection literature (below) -- collapses same-diagonal hits
within `--gap` non-matching words (default 1) into one run, whether or
not a source page break falls inside it. A single edited word inside an
otherwise-verbatim passage still reports as one finding instead of two
truncated ones, which matters because a single-word edit is exactly what
an LLM's light editing of a lifted passage tends to look like -- and the
same merge now recovers a lift that a source page break would otherwise
have split, including a remainder shorter than `--min-run` stranded alone
on one side of the break that used to be silently dropped.

Each finding reports the run's total span and its matched-word count
(so a gapped run is distinguishable from a pure one), the citekey and
page range (`page`/`end_page` -- equal for an ordinary single-page run,
`end_page > page` for one that spans a source page break), whether the
containing paragraph actually cites that source (`UNCITED SOURCE` if
not), whether the run sits inside quote delimiters (straight/curly double
quotes or a Markdown blockquote line -- a deterministic bit, not a
severity judgment), and `tier: "exact"` -- one key now, reserved for the
tiers below.

## Severity buckets, and the boilerplate allowlist

Two additions from issue #128, both aimed at the same goal as any future
gate built on top of `scan`: a tolerable false-positive rate.

**Severity buckets, in the written report only.** stdout stays
longest-first, unchanged -- it's read once, in a terminal, mid-review.
`--write`'s Markdown report instead groups findings **most-damning-first**
into three sections: *long* verbatim runs (`LONG_RUN_WORDS`, currently
15 words, is the boundary), *short* ones, and *quoted* ones. A run demotes to the low-priority *quoted* group only when
it is **both** inside quote delimiters **and** cites the source it
matched -- a quoted run from a source the paragraph does *not* cite is
still the finding `overlap` structurally cannot make, so it is grouped by
length like any other uncited run, not buried under `quoted` just for
sitting in quote marks. `--limit` truncates the longest-first list
*before* grouping, so a capped report can show only the `long` section
with `short`/`quoted` empty or absent; the report says so when `--limit`
is set, rather than letting an empty section read as "none exist."

### The boilerplate allowlist

Every corpus accumulates boilerplate a verbatim scan will always flag
and a reviewer will always wave through -- a standard's own name, an
acronym expansion, a field's fixed defined-term sentence, a dataset's
boilerplate methodology paragraph. Re-reviewing the same non-finding in
every draft is friction with no signal in it.

`scan` reads `content/verbatim_allowlist.toml` if present -- **per-host,
gitignored data**, like `config.toml`: never committed, never shared
across clones, and absent on a fresh clone is the normal state, not an
error (no suppressions configured). The file has four categories, purely
for whoever edits it to record *why* something is allowlisted -- all four
feed the same suppression mechanism:

```toml
# content/verbatim_allowlist.toml -- per-host, gitignored.
acronyms = [
    "IoT",
]
phrases = [
    "software defined networking",
]
definitions = [
    "A digital twin is a virtual representation of a physical asset that is kept synchronized with it.",
]
paragraphs = [
    """
    This dataset was collected in accordance with the methodology
    described in ISO/IEC 25010, using a stratified sampling approach
    across three sites.
    """,
]
```

**Suppression is mask-and-remeasure, not exact-match.** `scan` cannot
simply drop a finding whose text equals an allowlisted phrase: the
gap-tolerant merge above means the same boilerplate phrase produces a
different-length fragment depending on what non-matching prose happens
to sit next to it, so exact equality would rarely fire twice, and it
could never touch the common real case -- a short standard's name sitting
*inside* a much longer, otherwise-unexplained lift. Instead, every word
in a finding covered by a contiguous allowlisted phrase is masked out,
and the finding is dropped only if what's *left* would no longer clear
`--min-run` on its own. A 40-word lift that happens to contain a 3-word
defined term still shows up -- the allowlist only excuses a finding that,
once boilerplate is discounted, is nothing.

A present-but-malformed allowlist file (bad TOML, or a category that
isn't a list of strings) is a usage error (`scan` exits 2), not a silent
fallback to "no suppressions" -- a policy file that quietly stopped
working is the kind of failure that surfaces months later as "why did
this stop suppressing," not as a clean scan.

The written report records the allowlist's path and how many findings it
suppressed as a header line, since the allowlist isn't part of the
recorded, re-runnable command (it's per-host config, not a flag) -- a
report has to say what it consulted, or "what was waved through" stops
being visible from the report's own side.

## Repairing what the scan found

Detection without remediation leaves the human doing the tedious part.
Issue #129 adds the other half: the `overlap-reviser` skill
([GENRE.md](GENRE.md#repairing-overlap-overlap-reviser)) works a scan's
findings one at a time, and `python -m src.review verbatim recheck`
decides whether each repair may be kept.

**The scan payload locates a finding for an editor, not just a reader.**
`start`/`fragment`/`context` describe the normalised word stream, which
cannot be seeked to in the file. Alongside them each finding carries
`line`, `char_start`, `char_end` and `draft_text` -- the passage exactly
as written, citation markers and line breaks included -- plus `id`, a
digest of `(citekey, page, fragment)`. `id` is deliberately
position-free: an identity built on `start` would rename every remaining
finding the moment the first was repaired, and nothing could then say
whether a finding had survived a revision.

**`recheck` is an acceptance test, not a second scan.** Given a baseline
payload it re-scans at that baseline's own floor -- comparing a strict
run against a lax one would read as progress -- and reports each finding
as `resolved`, `persisting` or `new`, plus the change in the count of
*objective* findings, meaning the `long` and `short` buckets. A run that
is both quoted and cited is excluded from that count, or converting a
lift into a properly attributed quotation would score as no improvement.
It refuses a baseline it cannot compare against: another aid's payload,
one written under `--limit` (truncation makes "absent" ambiguous), one
missing a field the comparison prints (`id` or a locator, or `end_page`
from a build before #131), one from a different release series (what
counts as one finding can change between them), or one that is
unreadable or not JSON.

**What may be repaired without asking is decided by the buckets above,
not by the model.** A `short` run is reworded unattended; a `long` one
stops and asks the human whether to paraphrase or to quote; a `quoted`
one is reported as already correct. The paraphrase-or-quote choice is
authorial -- some things the field states one particular way -- and
[SOUL.md](../SOUL.md) puts deciding that for someone under *what you will
not do*.

**None of this is a gate.** `recheck` exits 0 whatever it finds, like
every other review command. `python -m src.draft gate` remains the only
thing in this pipeline that blocks, and whether a long allowlist-filtered
run should ever join it is still [#130](AUTO-IMPROVEMENT.md#build-order)'s
question, to be decided against real reports rather than guessed.

And the caveat that governs the whole section: repairing every finding
the exact tier can see leaves untouched everything it cannot. Paraphrase
is not detected. An empty findings list is not a clean bill of health.

## Measured: does the corpus's parser backend change the answer?

`[parser].backend` (`config.toml`) is `pdftotext` or `docling`. Both
backends' output gets the same `\f` page-break convention
(`src/pdf_text.py`), so nothing about `overlap`/`scan`'s page-locating
breaks either way -- but the two backends extract genuinely different
text, and this project's own corpus is configured for `docling`. Measured
directly rather than assumed, against the same 26 real papers cited by
this project's two full-length benchmark chapters
(`content/drafts/recalibration-of-models-for-digital-twins.md`,
`content/drafts/cloud-computing-for-digital-twins.md`): the same PDFs,
extracted fresh with `pdftotext -layout`, against the corpus's existing
`docling`-parsed text, with `scan` run over both.

**Page counts matched exactly for all 26 documents.** `src/pdf_text.py`'s
own comment warns that docling can under-count pages relative to
pdftotext when a page contributes no extracted item at all (a blank
page, a pure-image page) -- a real risk in principle, not observed on
this sample. Worth knowing before trusting it blind on a corpus with
more image-only pages than this one has.

**docling produced zero false positives from running headers; pdftotext
produced seven, from one document alone.** `gigli_next_2024` (an IEEE
Transactions paper) has a running header on every even page --
`"GIGLI et al.: NEXT GENERATION EDGE-CLOUD CONTINUUM ARCHITECTURE FOR
STRUCTURAL HEALTH MONITORING"` -- which repeats the paper's own title.
`pdftotext -layout` extracts running headers as literal page-top text, so
that 8-word phrase (`edge cloud continuum architecture for structural
health monitoring`, close paraphrase of the paper's own title, which
naturally shows up when a draft discusses the paper) matched once per
even page: **8 findings instead of 1** on the cloud-computing chapter
alone, all the same non-finding repeated. `docling`'s structural parsing
recognizes running headers as page furniture and drops them; the single
`docling` finding for the same citekey came from the paper's own Markdown
title heading on page 1 -- a genuine, single, legitimate echo.

The planted-reuse fixture told the same story in miniature: the real
finding (an uncited source's genuinely reused sentence) was found by
both backends, but `pdftotext`'s corpus carried the same 7 header
artifacts alongside it, `docling`'s did not.

Where a document has no running-header artifact, the two backends agreed
exactly: the recalibration chapter's one genuine finding (a 22-word
verbatim quote from `gomes_calibration_2024`, planted deliberately to
prove parity, not left to chance) reported identical span, matched-word
count and page under both backends. The divergence is specific to the
running-header failure mode, not a general instability between backends.

**Conclusion: keep `docling`.** For this measurement's purpose the
choice is not close. A reviewer working through `pdftotext`-backed
`scan` output on a corpus with running headers -- common in IEEE/ACM
journal templates -- has to notice and mentally discard a repeating
artifact before trusting the rest of the list, which is exactly the kind
of alarm fatigue that makes a reviewer start skimming past real findings
too. This was measured on 26 of ~500 corpus documents, one of which
carried the artifact; it is evidence the failure mode is real, not a
census of how common it is corpus-wide.

Reproduce: both fixture chapters are committed at
`bench/fixtures/recalibration-of-models-for-digital-twins.md` and
`bench/fixtures/cloud-computing-for-digital-twins.md` (the same ones
`bench/bench_overlap.py` uses for the #110/#111 timing measurements in
`bench/RESULTS.md`). The backend-comparison script itself is not -- a
one-off investigation, not a permanent bench tool. The method: for each
cited citekey, extract fresh `pdftotext -layout` text from the real PDF,
build a throwaway ledger pointing at it, run `scan` against that ledger
and against one pointing at the corpus's existing `docling`-parsed text
(unshared `OVERLAP_DIR`s so neither run's cache contaminates the other),
and diff the findings.

## Tuning, given the stated priority: catch more, and checking time is not the constraint

Two knobs, both defaults, both worth reconsidering once wall-clock is not
the limiting factor:

- **`--gap` (default 1).** Recovers a single-edited-word near-verbatim
  run. Raising it to 2 -- inside the "default 1-2" range named when this
  was scoped -- tolerates two edited words per gap at the cost of a
  slightly higher chance of bridging two unrelated short matches into one
  false run. Worth trying at 2 first, given the priority is recall over
  speed; the merge cost is negligible either way (a constant-factor
  addition per diagonal group, not separated out in the measurements
  above).
- **`--min-run` (default 8, the index's own n-gram size -- the reporting
  floor, not something lower can be served without rebuilding the whole
  index at a different `n`).** Cannot be lowered without a corpus-wide
  reindex at smaller `n`, which raises the birthday-bound collision odds
  and, more importantly, raises the false-positive rate: shorter
  n-grams match by coincidence far more often over a ~7M-gram corpus.
  Not recommended to change casually; if a shorter floor is genuinely
  needed, treat it as a deliberate reindex decision, not a flag.

The larger recall gap given the stated priority is the **page-boundary
limitation** above, not either flag: a real lift split by a page break
can be entirely missed regardless of `--gap`/`--min-run`, and no CLI
setting reaches it. If catching more matters enough to justify slower
checks, that global-token-position fix is the next lever worth pulling,
ahead of tuning either flag further.

## Where this sits in a bigger plan

The corpus's own contributor discussion ([discussion #115](https://github.com/prasadtalasila/chitragupta/discussions/115),
written before implementing #110) surveyed the plagiarism-detection
benchmark literature before choosing an approach, rather than building by
habit. Summary, for anyone deciding what to build next:

| Source | What it established | Where it lands here |
|---|---|---|
| Torrejón & Ramos, [CoReMo 2.1](https://www.semanticscholar.org/paper/Text-Alignment-Module-in-CoReMo-2.1-Plagiarism-for-Torrej%C3%B3n-Ramos/84e09d5dc31e01f070c7dfb31170142e6e038414) (PAN 2013 winner, quality and runtime) | Contextual n-grams with odd/even skip-grams -- exact-matching family, well-engineered n-gram methods beat fancier ones on speed at comparable quality; skip-grams + stemming tolerate single-word edits | The exact tier here (`overlap`/`scan`) is this family. Skip-grams are the named tier-2 upgrade, not yet built |
| Sánchez-Pérez et al., [PAN 2014/2015 winner](https://ceur-ws.org/Vol-1180/CLEF2014wn-Pan-SanchezPerezEt2014.pdf) | TF-IDF sentence similarity + recursive passage extension -- the fuzzy-match family wins only on *obfuscated* reuse | Not used: built for obfuscation the exact tier doesn't target, and competes with skip-grams for tier 2 on determinism-adjacent simplicity |
| [PAN 2025 generated-plagiarism task](https://arxiv.org/abs/2510.06805) | Measured the LLM case directly: exact-matching approaches miss LLM-paraphrased reuse, and detection degrades further as paraphrase complexity rises; embedding-based alignment (SBERT + local alignment, e.g. Smith-Waterman) is the validated answer for that tier | This is exactly why this document's [scope section](#what-plagiarism-means-here-and-what-it-deliberately-doesnt) insists a clean `scan` is not "no borrowed wording" |
| Schleimer, Wilkerson & Aiken, [winnowing / MOSS](https://theory.stanford.edu/~aiken/publications/papers/sigmod03.pdf) | Keep the minimum hash per window of size w; detection of any match >= w+n-1 is still *guaranteed*, index shrinks to ~2/(w+1) of full size | Deferred: a real lever at book scale, unnecessary at ~500 papers where the full index already fits in RAM. The cache-key design (`tokenizer_version`) leaves room for it later |

**The dividing line for what may ever block a draft: only deterministic
checks may.** Exact and skip-gram matching are deterministic and
gate-eligible in principle (a later, separate decision). Embedding
similarity is never deterministic across a config edit -- the chroma
collection is namespaced per embedding model precisely because vectors
change when `[enrich].embedding_model` does -- so it can never gate, only
advise.

That produces **three detection tiers** -- cumulative, not a menu you
pick one option from -- of which this document covers tier 1:

1. **Exact tier (here).** Inverted word-8-gram index, whole-corpus `scan`,
   gap-tolerant merge. Built (#110, #111).
2. **Deterministic light-paraphrase tier (proposed, not built).**
   Stemmed, stopword-filtered odd/even skip-grams in the same index
   framework -- the CoReMo design. Catches synonym swaps and inflection
   changes while staying objective enough to gate eventually.
3. **Embedding literal-paraphrase tier (proposed, not built).** Embed
   draft segments, k-NN against the existing `content/chroma/` collection
   (already built by the optional enrichment layer; reuses its
   incremental-by-text-hash embedding cache), flag high-cosine +
   low-lexical-overlap pairs. Advisory only, by construction, and gated
   on the enrichment layer being installed at all -- a blocking check
   cannot depend on an optional layer.

Because the drafts this pipeline produces are LLM-written and literal
paraphrase is their normal failure mode, tiers 2-3 are prioritized
immediately after the exact tier rather than parked indefinitely.

**Not on this roadmap, deliberately:** BERTopic (`content/topics.json`)
-- topic granularity is far too coarse for overlap, and prefiltering
candidates is worthless at ~500 documents where the exact index already
checks every source in one lookup. Suffix arrays / Greedy String Tiling
-- pairwise algorithms; a 1-vs-500 corpus needs the inverted index
regardless, so a pairwise method adds cost without adding a capability
the index doesn't already have.

## See also

- [CLI.md](CLI.md) -- `overlap`/`scan` flags and usage, and the
  review-aid step of [The full first run, step by
  step](CLI.md#the-full-first-run-step-by-step). `scan` is also offered
  by each of the seven skills' own final-check steps.
- [LADDERS.md](LADDERS.md) -- *ladder*, *rung* and *tier* as this project
  uses them, and the other three tier sets these sit beside.
- [ARCHITECTURE.md](ARCHITECTURE.md) -- `content/overlap/`'s place in the
  reproducibility contract, and where `scan` sits against the citation
  gate.
- `bench/RESULTS.md` -- wall-clock measurements for `overlap`/`scan`
  against this project's real corpus (separate from the backend
  comparison above, which is about detection quality, not speed).

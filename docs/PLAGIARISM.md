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

Both belong to the **review layer** and are advisory, not gates: a successful
run exits 0 whether it
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
page range (`page`/`end_page` -- the lowest and highest page an n-gram in
the run actually *starts* on, equal for an ordinary single-page run,
`end_page > page` for one that spans a source page break -- though not
the converse: a remainder shorter than the index's own n-gram size has no
gram starting on its page, so it is recovered into the run's word content
without moving `end_page`), whether the containing paragraph actually cites that
source (`UNCITED SOURCE` if
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
15 words, is the boundary), *short* ones, and *quoted* ones. A run demotes to
the low-priority *quoted* group only when
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
cannot be located in the file by position. Alongside them each finding carries
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
thing in this pipeline that blocks. Whether a long allowlist-filtered run
should ever join it is [#130](AUTO-IMPROVEMENT.md#build-order)'s question;
it has now been measured rather than guessed, and
[the section below](#measured-what-a-blocking-overlap-gate-would-block-130)
is what the measurement found.

And the caveat that governs the whole section: repairing every finding
the exact tier can see leaves untouched everything it cannot. Paraphrase
is not detected. An empty findings list is not a clean bill of health.

## Measured: what a blocking overlap gate would block (#130)

[#130](AUTO-IMPROVEMENT.md#build-order) asks whether a long verbatim run
should block a draft the way the citation gate blocks an unresolvable
citekey, and forbids guessing the threshold. `bench/bench_overlap_gate.py`
measured it against this project's own 15-chapter book
(178,077 words) and the same 497-document corpus the book was written
from -- organic prose with no planted reuse, which is what makes a
false-positive rate measurable at all. `bench/RESULTS.md` owns the
numbers; this section owns what they mean for the tool.

**Terms.** A **true positive** is a blocked finding that really is
uncredited reuse; a **false positive** is one no reviewer would act on --
a standard's own wording, a field's fixed definition, an attributed
quotation. **T** is the candidate threshold, a run length in words.

### The measurement first had to fix a masking bug

`_mask_for_scan` blanks the draft's own References section before
scanning, because two documents citing the same paper share its title and
venue verbatim. `references.section_start` matched only single-level
heading numbers, so a book numbering headings per chapter --
`## 1.14 References` -- was never masked, and the whole bibliography was
scanned against the corpus. On one chapter that was 97.7% of all findings
and **100%** of its long-run bucket. Fixed; the numbers below are from
the corrected behaviour. It is the first thing to check if a `scan`
result looks implausibly noisy: findings clustered at the end of the
draft, all naming different sources, are its reference list.

### The threshold is not a discriminating variable

With References masked, the whole book yields **16** runs of 15 words or
more, of which **14** the predicate could act on. Every one is a false
positive. The false positives run **15 to 29 words**; the only true
positive available anywhere in this repository -- the planted lift in
`bench/fixtures/` -- is **18 words**, inside that range rather than above
it.

So a threshold low enough to catch the genuine lift admits nine false
positives longer than it, and a threshold high enough to clear the false
positives misses the genuine lift. **No T separates them.** #130's
premise is that a generous span threshold makes a gate tolerable; on this
evidence the variable it proposes to tune does not discriminate.

### Why the false positives are structural, not tunable

The findings reduce to seven passages, dominated by two canonical
definitions -- ISO 23247's, and VanDerHorn & Mahadevan's. Several corpus
papers quote *and attribute* each one, verified in the parsed text. The
draft quotes and attributes it too, and can cite only one source for it.

That is the structural part, and `cites_source` cannot fix it: **a
definition reproduced by N corpus papers can be cited to one, so the
other N-1 report as `UNCITED SOURCE`.** The sharpest form is a
blockquote correctly cited to the work that first stated the taxonomy,
matched against a second paper reproducing it: `quoted` is true but
`cites_source` is false, so [`_bucket`](#severity-buckets-and-the-boilerplate-allowlist)
keeps it in `long` and #130's own `quoted and cites_source` exemption
does not reach it. **A correctly quoted, correctly credited passage would
block.**

The boilerplate allowlist is the mechanism meant to make this tolerable,
and it works: five entries take the 14 to **1**, and that one is an
attributed quotation. But `content/verbatim_allowlist.toml` is per-host
and gitignored by design, so a fresh clone has no suppression at all --
a gate's tolerability would depend on a file that does not exist until
someone writes it.

### What this does not license

The exact tier sees no verbatim reuse in this book. It does not follow
that the book borrows no wording: paraphrase is invisible here, and is an
LLM's normal failure mode. A gate built on this tier would block the
honest cases -- a quoted definition -- and miss the paraphrased ones.

Two further limits worth stating before anyone generalises: this is one
book, one topic, one generator; and because it contains no organic true
positives, the measurement establishes how often the gate fires *wrongly*
far better than it establishes how often it would fire *rightly*.

## Measured: document frequency, and what a single-field corpus changes

The measurement above ends on an unfinished observation. Having shown
that span length does not separate the two populations, it notes that
something else partly does: the large false-positive clusters are each
matched by **4 distinct citekeys**, where the one true positive available
anywhere in this repository -- the planted `aguzzi_cloud_2020` lift --
matches exactly **1**. That accounted for 8 of the 14 gateable findings
and no more.

`bench/bench_overlap_df.py` finishes it, and the result changes the order
tiers 2 and 3 should be built in.

### The corpus this pipeline is pointed at is single-field by design

That is not incidental to detection; it is the governing fact. This
project is built to be aimed at a deep corpus on one topic, and the
drafts are written *from* it: `src.retrieval` hands a skill the nearest
passages and the skill writes from those. Two consequences follow, and
they pull in opposite directions.

**It makes semantic similarity a weak discriminator.** Cosine distance
tells reuse from coincidence only when topical similarity is low by
default. Here it is high by default, and the pipeline's own retrieval
step guarantees that a draft segment's nearest neighbours are the
passages it was legitimately grounded in. A tier-3 rule of the form
"embed, k-NN, threshold" would rediscover its own retrieval step and
report it as a finding. Separation between "similar because same field"
and "similar because copied" does not vanish, but it narrows, and the
number of pairs a whole-draft scan generates amplifies whatever tail
remains.

**It makes document frequency a strong one.** An 8-gram in one corpus
paper is distinctive shared wording; an 8-gram in thirty is how the field
writes. A deep single-field corpus is exactly the sample that can tell
those apart, so the signal *improves* as the corpus grows -- the opposite
of what corpus depth does to cosine.

### DF is already stored, and it explains 12 of the 14

`overlap_index.postings_for_gram` returns every `(citekey, page,
position)` posting for a gram, so the count of distinct citekeys in those
postings *is* that gram's document frequency. No model, no new artefact,
no second index: DF is a projection of the index #110 already built.

Scoring each finding by the **median** DF over its 8-grams, against the
same corpus, the same book and the same hand labels as the #130
measurement:

| `median_df >= D` | Suppressed, of 14 gateable | True positives lost, of 1 |
|---|---|---|
| 2 | 12 | 0 |
| 3 | 11 | 0 |
| 4 | 8 | 0 |
| 5 | 0 | 0 |

`D = 4` reproduces the earlier 8 exactly, which is the check that this is
the same feature measured one level down -- per gram against the whole
index, rather than per finding against the citekeys that happened to
report.

Grouped by the labeller's own classes, DF turns out to measure what they
were seeing by eye:

| Class | Findings | median DF |
|---|---|---|
| `canonical-definition` | 4 | 3-4 |
| `third-party-echo` | 9 | 1-4 |
| `attributed-quotation` | 3 | 1 |

The first two are the classes whose written rationale is "many corpus
papers reproduce this", and DF finds them. The third sits at exactly 1,
and DF is blind to it -- correctly, because an attributed quotation *is*
verbatim from a single source. That class is already exempt from #130's
predicate through `quoted and cites_source`, so the two mechanisms cover
disjoint populations rather than competing for the same one.

### What the DF result does not license

- **A threshold.** The evidence supports "DF is the discriminating
  feature, at gram granularity"; it does not support shipping a `D`. The
  target is a region measured on one corpus and one book, in the same
  sense [PARALLELISM.md](PARALLELISM.md#roadmap) means it for
  `_CPUS_PER_DOCLING_WORKER`.
- **A recall claim.** The recall arm is **one planted finding**. "0 of 1
  true positive lost" is the whole of what was measured; it is not a
  false-negative rate, and no phrasing that implies one is supportable
  from this data.
- **Escape from the paraphrase caveat.** DF is computed over exact-tier
  findings and inherits that tier's blindness entirely.
- **A gate.** DF moves whenever the corpus does: `index.json`'s key is a
  sha256 over every document's own change-detection key, so adding a
  paper or re-parsing one shifts every number above, and a run that was
  clean can turn dirty with no draft edit. That is deterministic *given a
  corpus state* -- a weaker guarantee than `src.draft gate`'s, and the
  same shape as the per-host allowlist below. #130 is where that trade is
  priced, not here.

The measurement is in
[bench/RESULTS.md](../bench/RESULTS.md#2026-08-13b-does-a-grams-corpus-document-frequency-separate-boilerplate-from-reuse),
including the two profile artefacts that force the median rather than the
minimum, and the `fragment`-versus-`draft_text` trap that makes a wrong
implementation of this fail silently.

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

**Between the two, tier 2 goes first**, and [the DF
measurement](#measured-document-frequency-and-what-a-single-field-corpus-changes)
is why. Three things follow from it, all recorded in #133 and #134:

- Skip-grams are lexically anchored, so the topical similarity that
  saturates a single-field corpus does not inflate them, and they live in
  the same index framework -- which means they inherit a DF-derived
  boilerplate suppression for free rather than needing their own.
- Tier 3's stated form -- k-NN against the whole corpus, thresholded --
  is the form the same measurement argues against. The redesign in #134
  scopes it to the citekeys a section's dossier already records and ranks
  rather than thresholds.
- Tier 3 also needs a step this list never named: a **local alignment**,
  because a cosine score is not a finding. That is #164, and it changes
  the tier's dependency list from `content/chroma/` alone to chroma plus
  the Docling passage sidecars.

A **cross-encoder reranker** over tier-1 and tier-2 candidates is the
obvious fourth option and is deliberately not a tier. It cannot search --
one forward pass per pair, no index possible -- so it can only reorder
findings something else produced, never generate one. That is what would
make it safe here (the gate stays deterministic because the reranker
cannot change the finding set, only its order), and also what makes it
hard to justify: it adds a torch dependency and a model download to
improve the ranking of a population DF already suppresses deterministically
and for free.

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
  comparison above, which is about detection quality, not speed), and the
  two label-scored sections behind #130 and the document-frequency
  result.

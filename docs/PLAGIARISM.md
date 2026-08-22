# Plagiarism / verbatim-reuse detection

Status: **implemented, three detection tiers of a planned three.** The
second and third shipped advisory-only. The third runs only where the
optional enrichment layer, the Docling passage sidecars and the draft's
own dossier are all present. Written 2026-08-10; tier 2 added 2026-08-13
(#133), tier 3 added 2026-08-15 (#134/#164).

**Written for** someone deciding whether `chitragupta/review/verbatim_check.py`'s
`overlap`/`scan` modes are enough review before presenting a draft, or
tuning `--min-run`/`--gap`, or choosing `[parser].backend`. **Assumed:**
a synced corpus (`python -m chitragupta.corpus sync`) and a citekey-verified draft
(`python -m chitragupta.draft gate`).

**Not covered here, deliberately:**

- **How to invoke the tools day to day** -- that is [CLI.md](CLI.md)'s
  job: the flags, the JSON payload's fields, the exit codes.
- **How the detection works, and what was measured** -- that is
  [PLAGIARISM-DESIGN.md](PLAGIARISM-DESIGN.md): the fingerprinting
  scheme, the three tiers' mechanisms, the gate and document-frequency
  measurements, why a similarity threshold cannot work in a single-field
  corpus, and which further tiers were considered and rejected. You do
  not need any of it to read a report; you need all of it to change one.

**The three tiers, in one paragraph.** Findings come from three
detectors, and every finding names the one that produced it:

- **exact** is a verbatim word-run.
- **skip-gram** is a tolerant stemmed match. It also catches a passage
  with a handful of words substituted.
- **embedding** matches meaning rather than wording. It is the only one
  that sees a genuine restatement.

That third tier is also the narrowest. It runs only where the optional
enrichment layer, the Docling passage sidecars and the draft's own
dossier are all present, and it compares a section only against the
sources that section already cites.

This is the one **tier set** in this project whose options
are not mutually exclusive
([ARCHITECTURE.md](ARCHITECTURE.md#ladders-and-tiers)): nobody picks one,
every available tier runs, and the findings are unioned. A tier that
could not run says so, by name, in every form of the report.

## What "plagiarism" means here, and what it deliberately doesn't

This pipeline draws citekeys from a synced bibliography and gates on
them (`chitragupta/citation_gate.py`): a draft cannot cite a source that isn't
real. That answers "is every citation genuine" and says nothing about
"does the wording around a citation actually belong to whoever it credits,
or to someone else". `chitragupta/review/verbatim_check.py`'s two modes exist to
answer the second question, mechanically, over what is currently checked
verbatim word-n-gram reuse.

**Verbatim and light-paraphrase reuse only.** Tier 2's stemmed
skip-grams (`chitragupta/overlap_skipgram.py`, #133) catch a synonym swapped
every few words, or an inflection changed. Genuine restatement in new
sentence structure -- the same claim, said differently -- is invisible to
both deterministic tiers by construction.

That matters more here than it would elsewhere, because **the drafts this
pipeline produces are LLM-written**. Literal paraphrase is an LLM's
default failure mode when it drifts too close to a source, not an edge
case.

Treat a clean `scan` as "no exact or near-exact copying, no word-swapped
paraphrase, and -- where tier 3 ran -- no close restatement of a source a
section's dossier records". Never as "no borrowed wording found".

None of this is a license to leave borrowed wording in place because a
tier didn't catch it. A clean `scan` reports what the tooling could see,
not what's acceptable to publish -- copying a source's wording into a
draft without quoting it doesn't stop being that because it slipped past
three detectors.

Tier 3 below closes the restatement gap, but only within each section's
own recorded citekeys, and only where the optional stack it needs is
installed. A lift from a source a section never cited remains tiers 1 and
2's business alone.

That is this tier set's characteristic failure and the reason `scan`
now names the tiers that **did not run**, with the reason, in both its
printed and written forms and as `tiers_not_run` in the JSON payload.
An unbuilt or unavailable tier does not otherwise announce itself, so a
thin result and a thorough one look identical.

## The two tools, and when each is right

| | `overlap` | `scan` |
|---|---|---|
| Compares against | One citekey's own source, in paragraphs citing it | The whole corpus, against the whole draft |
| Sees an uncited source's wording? | No -- structurally cannot, by design | Yes |
| Sees connective prose citing nothing? | No | Yes |
| Typical use | Quick check on one citation while drafting | Full-draft pass before presenting |
| Cost | Sub-second, even cold | ~27s first run on this corpus (497 docs); sub-second every run after -- **but minutes rather than seconds wherever tier 3 runs**, since it embeds each shortlisted source's sentences. Measured: ~100s for one chapter of the 15-chapter book, dominated by that. See below |

Both belong to the **review layer**, so both are advisory and neither
blocks -- [REVIEW.md](REVIEW.md) has what that guarantees, and what it
does not. The one detail specific to these two: a malformed invocation --
a bad flag, a missing argument -- exits 2, which is ordinary CLI-usage
error handling rather than a verdict on the draft.

Whether long verbatim runs should gate is a later and deliberately
separate decision, issue #110's Phase 2. These tools only produce the
findings that decision would be tuned against.

## How it works

Both modes compare the draft against a **fingerprint** of each source:
its text reduced to hashed, overlapping word n-grams, cached under
`content/overlap/` and rebuilt only when the source changes. That is
enough to read the rest of this page; the scheme itself, and why the
hash is what it is, are in
[PLAGIARISM-DESIGN.md](PLAGIARISM-DESIGN.md#fingerprinting-word-n-grams-hashed-deterministically).

### `overlap`: one citekey, exact-match runs

For one citekey, builds a `{gram_hash: page}` map from that document's
fingerprint and slides the draft's own paragraphs (that cite the
citekey) across it, reporting maximal verbatim runs -- `n` or more words
in an unbroken match. Fast because it never looks past the one source
named.

### `scan`: the whole draft against the whole corpus

Normalizes the entire draft once, masking code fences and inline code the
same way `chitragupta/citation_gate.py` does, and masking the generated
References section so a source's own title page never reads as "overlap
with itself". Then, for every draft position, it looks up **every**
posting for that position's gram hash across **every** parsed document --
not just the ones the surrounding paragraph cites.

`--write` also files the findings as
`content/review/<topic>/<stem>.verbatim.md`, beside the same draft's
provenance and coverage reports -- printing stays the default, since the
usual use is a question asked and answered in one sitting. The written
report opens with a banner saying it is not a verdict and repeats the
"not a clean bill of health" caveat above, so a file found on disk months
later cannot be read as a clearance. It carries no timestamp, so two runs
over an unchanged draft and corpus diff to nothing.

`--json` prints the same findings as data instead of as text, and
`--write` files them as the report's `.json` sibling. Both carry the same
not-a-verdict notice and the same absence of a timestamp.

Each payload finding also carries `severity`: the same
`long`/`short`/`quoted` bucket the written report groups by, derived the
same way. A programmatic consumer -- the remediation loop below, an
eventual gate -- therefore reads the same severity a human reviewer sees,
rather than regex-parsing the printed lines or recomputing the threshold.

It also carries `id`, a position-free name for the finding, and four
fields that locate it in the draft as written. One of those is easy to
misread: `start` is a word offset into the normalised stream, not a
position in the draft file, and the locators are what to use instead. All
of them are in [CLI.md](CLI.md#python--m-chitraguptareview-verbatim).

Matches are grouped by `(citekey, diagonal)`, where `diagonal =
source_position - draft_position`. That `source_position` is a *global*
token position in the source document, not reset at each page break
(`chitragupta/overlap_index.py`, #131).

Two matches on the same diagonal are "in step" with each other even with
non-matching words between them. So a **gap-tolerant merge** collapses
same-diagonal hits within `--gap` non-matching words (default 1) into one
run, whether or not a source page break falls inside it. It is the same
idea as seed-and-extend alignment in the plagiarism-detection
literature. A single edited word inside an
otherwise-verbatim passage therefore reports as one finding, not two
truncated ones. That matters because a single-word edit is exactly what
an LLM's light editing of a lifted passage tends to look like.

The same merge recovers a lift that a source page break would otherwise
have split -- including a remainder shorter than `--min-run`, stranded
alone on one side of the break, which used to be dropped silently.

Each finding reports five things:

- **The run's total span and its matched-word count**, so a gapped run is
  distinguishable from a pure one.
- **The citekey and page range.** `page`/`end_page` are the lowest and
  highest page an n-gram in the run actually *starts* on. They are equal
  for an ordinary single-page run, and `end_page > page` for one spanning
  a source page break.
- **Whether the containing paragraph cites that source**, shown as
  `UNCITED SOURCE` if it does not.
- **Whether the run touches quote delimiters** -- straight or curly
  double quotes, or a Markdown blockquote line. A deterministic bit, not
  a severity judgment.
- **`tier`**, naming the detector that produced it.

The page range does not run the other way. A remainder shorter than the
index's own n-gram size has no gram starting on its page, so `scan`
recovers it into the run's word content without moving `end_page`.

**`quoted` reads as overlap, not containment**, and the difference is not
cosmetic. A matched run is wider than the quotation that evidences it and
routinely opens a word or two before the opening mark, in the draft's own
framing prose. Requiring the *whole* run to sit inside the marks -- the
original reading -- therefore reported `quoted: false` on correctly quoted,
correctly credited passages, which is precisely the material the flag
exists to let a reader skip (#189). Four hand-labelled
`attributed-quotation` findings across tiers 1 and 2 had that shape, two
of them with the quoted words a minority of the span, so a
majority-of-span rule does not reach them either.

## Severity buckets, and the boilerplate allowlist

Two additions from issue #128, both aimed at the same goal as any future
gate built on top of `scan`: a tolerable false-positive rate.

**Severity buckets, in the written report only.** stdout stays
longest-first, unchanged: it is read once, in a terminal, mid-review.

`--write`'s Markdown report instead groups findings
**most-damning-first**, into three sections: *long* verbatim runs,
*short* ones, and *quoted* ones. `LONG_RUN_WORDS`, currently 15 words, is
the boundary.

A run demotes to the low-priority *quoted* group only when it is **both**
touching quote delimiters **and** citing the source it matched. A quoted run
from a source the paragraph does *not* cite is still the finding
`overlap` structurally cannot make. It is grouped by length like any
other uncited run, rather than buried under `quoted` for sitting in quote
marks.

`--limit` truncates the longest-first list *before* grouping, so a capped
report can show only the `long` section with `short`/`quoted` empty or
absent. The report says so when `--limit` is set, rather than letting an
empty section read as "none exist."

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
drop a finding whose text equals an allowlisted phrase. The gap-tolerant
merge above means the same boilerplate phrase produces a different-length
fragment depending on what non-matching prose sits next to it, so exact
equality would rarely fire twice. It could never touch the common real
case at all: a short standard's name sitting *inside* a much longer,
otherwise-unexplained lift. Instead, every word
in a finding covered by a contiguous allowlisted phrase is masked out,
and the finding is dropped only if what's *left* would no longer clear
`--min-run` on its own. A 40-word lift that happens to contain a 3-word
defined term still shows up -- the allowlist only excuses a finding that,
once boilerplate is discounted, is nothing.

A present-but-malformed allowlist file -- bad TOML, or a category that
isn't a list of strings -- is a usage error, and `scan` exits 2. It does
not fall back silently to "no suppressions". A policy file that quietly
stopped working surfaces months later as "why did this stop
suppressing", not as a clean scan.

The written report records the allowlist's path and how many findings it
suppressed, as a header line. The allowlist is per-host config rather
than a flag, so it is not part of the recorded, re-runnable command. A
report has to say what it consulted, or "what was waved through" stops
being visible from the report's own side.

## Repairing what the scan found

Detection without remediation leaves the human doing the tedious part.
Issue #129 adds the other half: the `overlap-reviser` skill
([GENRE.md](GENRE.md#repairing-overlap-overlap-reviser)) works a scan's
findings one at a time, and `python -m chitragupta.review verbatim recheck`
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
payload, it re-scans at that baseline's own floor, because comparing a
strict run against a lax one would read as progress. It reports each
finding as `resolved`, `persisting` or `new`, plus the change in the
count of *objective* findings -- the `long` and `short` buckets.

A run that is both quoted and cited is excluded from that count.
Otherwise converting a lift into a properly attributed quotation would
score as no improvement.

It refuses a baseline it cannot compare against:

- another aid's payload;
- one written under `--limit`, where truncation makes "absent" ambiguous;
- one missing a field the comparison prints, such as `id`, a locator, or
  `end_page` from a build before #131;
- one from a different release series, since what counts as one finding
  can change between them;
- one that is unreadable or not JSON.

**What may be repaired without asking is decided by the buckets above,
not by the model.** A `short` run is reworded unattended. A `long` one
stops and asks the human whether to paraphrase or to quote. A `quoted`
one is reported as already correct.

The paraphrase-or-quote choice is authorial -- some things the field
states one particular way -- and [SOUL.md](../SOUL.md) puts deciding that
for someone under *what you will not do*.

**None of this is a gate.** `recheck` exits 0 whatever it finds, like
every other review command. `python -m chitragupta.draft gate` remains the only
thing in this pipeline that blocks. Whether a long allowlist-filtered run
should ever join it is [#130](AUTO-IMPROVEMENT.md#build-order)'s question;
it has now been measured rather than guessed, and
[the gate measurement](PLAGIARISM-DESIGN.md#measured-what-a-blocking-overlap-gate-would-block-130)
is what the measurement found.

And the caveat that governs the whole section: repairing every finding
the exact tier can see leaves untouched everything it cannot. Paraphrase
is not detected. An empty findings list is not a clean bill of health.

## Measured: does the corpus's parser backend change the answer?

`[parser].backend` (`config.toml`) is `pdftotext` or `docling`. Both
backends' output gets the same `\f` page-break convention
(`chitragupta/pdf_text.py`), so nothing about `overlap`/`scan`'s page-locating
breaks either way. But the two extract genuinely different text, and this
project's own corpus is configured for `docling`.

Measured directly rather than assumed, against the 26 real papers cited
by this project's two full-length benchmark chapters
(`content/drafts/recalibration-of-models-for-digital-twins.md` and
`content/drafts/cloud-computing-for-digital-twins.md`). The same PDFs
were extracted fresh with `pdftotext -layout` and compared against the
corpus's existing `docling`-parsed text, with `scan` run over both.

**Page counts matched exactly for all 26 documents.** `chitragupta/pdf_text.py`'s
own comment warns that docling can under-count pages relative to
pdftotext when a page contributes no extracted item at all -- a blank
page, or a pure-image one. That is a real risk in principle, and was not
observed on this sample. Worth knowing before trusting it blind on a
corpus with more image-only pages than this one has.

**docling produced zero false positives from running headers; pdftotext
produced seven, from one document alone.** `gigli_next_2024`, an IEEE
Transactions paper, has a running header on every even page:
`"GIGLI et al.: NEXT GENERATION EDGE-CLOUD CONTINUUM ARCHITECTURE FOR
STRUCTURAL HEALTH MONITORING"`. It repeats the paper's own title.

`pdftotext -layout` extracts running headers as literal page-top text.
That 8-word phrase is `edge cloud continuum architecture for structural
health monitoring`, which naturally shows up when a draft discusses the
paper. It therefore matched once per even page: **8 findings instead of
1** on the cloud-computing chapter alone, all the same non-finding
repeated.

`docling`'s structural parsing recognizes running headers as page
furniture and drops them. Its single finding for the same citekey came
from the paper's own Markdown title heading on page 1: a genuine,
single, legitimate echo.

The planted-reuse fixture told the same story in miniature: the real
finding (an uncited source's genuinely reused sentence) was found by
both backends, but `pdftotext`'s corpus carried the same 7 header
artifacts alongside it, `docling`'s did not.

Where a document has no running-header artifact, the two backends agreed
exactly. The recalibration chapter's one genuine finding -- a 22-word
verbatim quote from `gomes_calibration_2024`, planted deliberately to
prove parity rather than left to chance -- reported identical span,
matched-word count and page under both. The divergence is specific to the
running-header failure mode, not a general instability.

**Conclusion: keep `docling`.** For this measurement's purpose the choice
is not close. A reviewer working through `pdftotext`-backed `scan` output
on a corpus with running headers -- common in IEEE/ACM journal templates
-- has to notice and mentally discard a repeating artifact before
trusting the rest of the list. That is exactly the alarm fatigue which
makes a reviewer start skimming past real findings too.

This was measured on 26 of ~500 corpus documents, one of which carried
the artifact. It is evidence that the failure mode is real, not a census
of how common it is corpus-wide.

Reproduce: both fixture chapters are committed at
`bench/fixtures/recalibration-of-models-for-digital-twins.md` and
`bench/fixtures/cloud-computing-for-digital-twins.md`. They are the same
ones `bench/bench_overlap.py` uses for the #110/#111 timing measurements
in `bench/RESULTS.md`. The backend-comparison script itself is not
committed -- a one-off investigation, not a permanent bench tool.

The method, for each cited citekey: extract fresh `pdftotext -layout`
text from the real PDF, build a throwaway ledger pointing at it, then run
`scan` twice -- against that ledger, and against one pointing at the
corpus's existing `docling`-parsed text -- and diff the findings. The two
runs use unshared `OVERLAP_DIR`s, so neither cache contaminates the
other.

## Tuning, given the stated priority: catch more, and checking time is not the constraint

Two knobs, both defaults, both worth reconsidering once wall-clock is not
the limiting factor:

- **`--gap` (default 1).** Recovers a single-edited-word near-verbatim
  run. Raising it to 2 -- inside the "default 1-2" range named when this
  was scoped -- tolerates two edited words per gap. The cost is a
  slightly higher chance of bridging two unrelated short matches into one
  false run. Worth trying at 2 first, given the priority is recall over
  speed. The merge cost is negligible either way: a constant-factor
  addition per diagonal group, not separated out in the measurements
  above.
- **`--min-run` (default 8, the index's own n-gram size -- the reporting
  floor, not something lower can be served without rebuilding the whole
  index at a different `n`).** Cannot be lowered without a corpus-wide
  reindex at smaller `n`. That raises the birthday-bound collision odds,
  and -- more importantly -- the false-positive rate: shorter n-grams
  match by coincidence far more often over a ~7M-gram corpus. Not
  recommended casually. If a shorter floor is genuinely needed, treat it
  as a deliberate reindex decision rather than a flag.

The larger recall gap given the stated priority is the **page-boundary
limitation** above, not either flag: a real lift split by a page break
can be entirely missed regardless of `--gap`/`--min-run`, and no CLI
setting reaches it. If catching more matters enough to justify slower
checks, that global-token-position fix is the next lever worth pulling,
ahead of tuning either flag further.

## See also

- [PLAGIARISM-DESIGN.md](PLAGIARISM-DESIGN.md) -- the developer-facing
  half: the fingerprinting scheme, each tier's mechanism, the gate and
  document-frequency measurements, and the tiers deliberately not built.
- [CLI.md](CLI.md) -- `overlap`/`scan` flags and usage, and the
  review-aid step of [The full first run, step by
  step](CLI.md#the-full-first-run-step-by-step). `scan` is also offered
  by each of the nine skills' own final-check steps.
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

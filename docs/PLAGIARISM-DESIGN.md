# Plagiarism detection: how the three tiers work, and what was measured

Status: **three detection tiers, all built; the second and third
advisory-only.** Written 2026-08-15, splitting the design half out of
[PLAGIARISM.md](PLAGIARISM.md), which had grown to carry both.

**Written for** someone changing `src/overlap_index.py`,
`src/overlap_skipgram.py`, `src/overlap_embed.py` or
`src/review/verbatim_check.py` -- or deciding whether a proposed fourth
tier is worth building. **Assumed:**
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) for the process around a
change, and [ARCHITECTURE.md](ARCHITECTURE.md) for where the review
layer sits.

**Not covered here:** what the tools report and how to read it. That is
[PLAGIARISM.md](PLAGIARISM.md), which is the user-facing half and the
one a person reaches for before presenting a draft. Nothing is restated
across the two -- where this document needs a term the other defines, it
links rather than repeats, for the reason
[CODE-STANDARDS.md](CODE-STANDARDS.md#where-these-rules-come-from) gives:
a rule stated twice is a rule that will eventually be stated two
different ways.

**Why this file exists at all.** The two halves have opposite readers.
Someone deciding whether to trust a clean scan needs the flags, the
allowlist and the caveat; someone deciding whether to build a fourth
tier needs the measurements, the rejected alternatives, and the argument
about what a single-field corpus does to a similarity threshold. Kept
together, each reader pages past the other's document -- and the
measurements are the part most likely to be skimmed and then
re-litigated.

## Table of contents

- [Fingerprinting: word n-grams, hashed deterministically](#fingerprinting-word-n-grams-hashed-deterministically)
- [Measured: what a blocking overlap gate would block (#130)](#measured-what-a-blocking-overlap-gate-would-block-130)
- [Measured: document frequency, and what a single-field corpus changes](#measured-document-frequency-and-what-a-single-field-corpus-changes)
- [Where this sits in a bigger plan](#where-this-sits-in-a-bigger-plan)

## Fingerprinting: word n-grams, hashed deterministically

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
`cites_source` is false, so [`_bucket`](PLAGIARISM.md#severity-buckets-and-the-boilerplate-allowlist)
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

The measurement is `bench/RESULTS.md`'s `2026-08-13b` section -- not
linked, because `bench/` is one of the trees the documentation site does
not publish. It carries the two profile artefacts that force the median
rather than the minimum, and the `fragment`-versus-`draft_text` trap that
makes a wrong implementation of this fail silently.

## Where this sits in a bigger plan

The corpus's own contributor discussion ([discussion #115](https://github.com/prasadtalasila/chitragupta/discussions/115),
written before implementing #110) surveyed the plagiarism-detection
benchmark literature before choosing an approach, rather than building by
habit. Summary, for anyone deciding what to build next:

| Source | What it established | Where it lands here |
|---|---|---|
| Torrejón & Ramos, [CoReMo 2.1](https://www.semanticscholar.org/paper/Text-Alignment-Module-in-CoReMo-2.1-Plagiarism-for-Torrej%C3%B3n-Ramos/84e09d5dc31e01f070c7dfb31170142e6e038414) (PAN 2013 winner, quality and runtime) | Contextual n-grams with odd/even skip-grams -- exact-matching family, well-engineered n-gram methods beat fancier ones on speed at comparable quality; skip-grams + stemming tolerate single-word edits | The exact tier here (`overlap`/`scan`) is this family. Skip-grams are the tier-2 upgrade, built in `src/overlap_skipgram.py` (#133) |
| Sánchez-Pérez et al., [PAN 2014/2015 winner](https://ceur-ws.org/Vol-1180/CLEF2014wn-Pan-SanchezPerezEt2014.pdf) | TF-IDF sentence similarity + recursive passage extension -- the fuzzy-match family wins only on *obfuscated* reuse | Not used: built for obfuscation the exact tier doesn't target, and competes with skip-grams for tier 2 on determinism-adjacent simplicity |
| [PAN 2025 generated-plagiarism task](https://arxiv.org/abs/2510.06805) | Measured the LLM case directly: exact-matching approaches miss LLM-paraphrased reuse, and detection degrades further as paraphrase complexity rises; embedding-based alignment (SBERT + local alignment, e.g. Smith-Waterman) is the validated answer for that tier | This is exactly why this document's [scope section](PLAGIARISM.md#what-plagiarism-means-here-and-what-it-deliberately-doesnt) insists a clean `scan` is not "no borrowed wording" |
| Schleimer, Wilkerson & Aiken, [winnowing / MOSS](https://theory.stanford.edu/~aiken/publications/papers/sigmod03.pdf) | Keep the minimum hash per window of size w; detection of any match >= w+n-1 is still *guaranteed*, index shrinks to ~2/(w+1) of full size | Deferred: a real lever at book scale, unnecessary at ~500 papers where the full index already fits in RAM. The cache-key design (`tokenizer_version`) leaves room for it later |

**The dividing line for what may ever block a draft: only deterministic
checks may.** Exact and skip-gram matching are deterministic and
gate-eligible in principle (a later, separate decision). Embedding
similarity is never deterministic across a config edit -- the chroma
collection is namespaced per embedding model precisely because vectors
change when `[enrich].embedding_model` does -- so it can never gate, only
advise.

That produces **three detection tiers** -- cumulative, not a menu you
pick one option from -- of which this document covers tier 1 in depth;
tier 2's own mechanism is documented in `src/overlap_skipgram.py`'s
module docstring and tier 3's in `src/overlap_embed.py`'s, and their
measurements are in `bench/RESULTS.md`'s 2026-08-13 skip-gram and
2026-08-15 embedding sections:

1. **Exact tier (here).** Inverted word-8-gram index, whole-corpus `scan`,
   gap-tolerant merge. Built (#110, #111).
2. **Deterministic light-paraphrase tier.** Stemmed, stopword-filtered
   odd/even skip-grams in the same index framework -- the CoReMo design.
   Catches synonym swaps and inflection changes while staying objective
   enough to gate eventually. Built (#133), `src/overlap_skipgram.py`,
   findings carry `tier: "skip-gram"`. Shipped **advisory only**
   (discussion #115: "start advisory, promote with evidence") -- nothing
   in `scan` decides gate-eligibility for it; that is #130's decision,
   unchanged by this tier existing. **Measured 2026-08-14 (#180), and it
   stays advisory on the strength of it**: over a real 15-chapter book,
   2 of 27 findings were reuse a reviewer would act on, and the exact
   tier already reported both of those passages -- so tier 2 contributed
   nothing tier 1 had not. That number is only trustworthy because the
   same measurement first found two mechanical bugs behind 163 of the
   190 raw findings (bare numbers treated as distinctive content, and
   the same finding emitted once per diagonal group). One book whose
   reuse happens to be verbatim is not evidence tier 2 cannot work, but
   it is not the evidence discussion #115 asks for before promoting it.
   See `bench/RESULTS.md`'s #180 section before trusting a clean `scan`
   on this tier any more than on tier 1.
3. **Embedding paraphrase tier.** Built (#134/#164, 2026-08-15),
   `src/overlap_embed.py` with `src/overlap_align.py`,
   `src/overlap_segments.py` and `src/overlap_chroma.py`; findings carry
   `tier: "embedding"` and a `score`. **Not** the k-NN-against-the-whole-
   corpus-and-threshold shape this list originally proposed -- that form
   is the one [the DF measurement](#measured-document-frequency-and-what-a-single-field-corpus-changes)
   argues against, and it was replaced before any of it was written. What
   shipped instead:

   - **Scoped to the dossier.** Each section is compared against the
     citekeys its `sections.md` records that section as written from,
     never against the whole corpus. The chroma collection ranks that
     handful (one `collection.query()` per section, read at citekey
     granularity only); the alignment then runs against the Docling
     passage sidecars, which are the only source text carrying the page
     a finding must report.
   - **Windowed, not sentence-level.** Segments are ~20-word overlapping
     windows on both sides. This is the measurement the tier turns on:
     the one hand-verified organic paraphrase in chapter 1 of the real
     book scores **0.55** against the source sentence it restates while
     three unrelated sentences *of that same paper* score 0.59-0.61 --
     so at sentence granularity the true pair sits below the topical
     noise and no threshold recovers it. The same prose windowed scores
     **0.71** against the true source and 0.40 against the same noise.
   - **Local alignment, not a cosine.** Smith-Waterman over the windowed
     cosine matrix (#164): a bi-encoder gives a number per pair and a
     finding needs a span.
   - **Ranked, not thresholded.** The strongest alignment per section,
     with its score, always -- no cutoff to tune and no pretence of a
     verdict, exactly as #134's redesign asks. The ranking is per
     *section* because scores are not comparable across sections; a
     draft-wide top-N dropped the one hand-verified paraphrase in
     chapter 1, which is the strongest alignment in its own section.
   - **Deduplicated against the deterministic tiers by checking, not by
     guessing.** #134 asks for a low-lexical-overlap filter so tier 3
     does not re-report what tier 1 or 2 already caught. That goal is
     kept and the mechanism is not: `scan_findings` drops any alignment
     a real exact or skip-gram finding overlaps. A lexical ceiling is an
     a-priori guess at the same thing, and a measured one -- it threw
     away the strongest alignment in `bench/`'s graded fixture, which
     neither deterministic tier caught, because substituting words also
     moved them.

   **Advisory only, permanently and by construction.** `content/chroma/`
   is namespaced per `[enrich].embedding_model` because vectors change
   when that setting does, so a finding here is not reproducible across a
   config edit and can never satisfy the "only deterministic checks may
   block" line above. It is also gated on an optional layer, which a
   blocking check must never be. The structural guarantee lives in
   `bench/bench_overlap_gate.py::eligible()`, which admits `exact` and
   nothing else and whose own self-test asserts a `tier: "embedding"`
   finding is ineligible.

   **Unavailable, and says so.** The tier needs the `enrich` Poetry
   group, a built `content/chroma/`, Docling sidecars, and the draft's
   dossier. Any of those missing and it reports *which*, rather than
   contributing nothing silently.

   **What it costs, and what is not cached.** The enrichment layer's
   incremental-by-text-hash cache does *not* cover this tier's vectors,
   and a reader who assumes it does will misjudge the cost. That cache
   holds `content/chroma/`'s 200-word *chunk* embeddings, which tier 3
   uses only to rank citekeys -- its alignment runs over ~20-word
   windows of the passage sidecars, which are embedded on demand and
   held only for the duration of one `scan`. Each source is therefore
   embedded once per scanned draft, not once per corpus. On the
   15-chapter book that is ~100s per chapter. A persistent
   window-level cache is the obvious next step and is deliberately not
   in this change: nothing has yet measured whether the tier is worth
   running often enough to need one.

Because the drafts this pipeline produces are LLM-written and literal
paraphrase is their normal failure mode, tiers 2-3 were prioritized
immediately after the exact tier rather than parked indefinitely.

**Tier 2 went first**, and [the DF
measurement](#measured-document-frequency-and-what-a-single-field-corpus-changes)
is why. Three things followed from it, all recorded in #133 and #134,
and all three held up when tier 3 was finally built:

- Skip-grams are lexically anchored, so the topical similarity that
  saturates a single-field corpus does not inflate them, and they live in
  the same index framework -- which means they inherit a DF-derived
  boilerplate suppression for free rather than needing their own.
- Tier 3's stated form -- k-NN against the whole corpus, thresholded --
  is the form the same measurement argues against. The redesign in #134
  scopes it to the citekeys a section's dossier already records and ranks
  rather than thresholds. That is what shipped, and building it produced
  a second, sharper version of the same finding: not only is a
  corpus-wide threshold wrong, a *sentence-level* comparison is too. In
  this corpus a draft sentence's framing is enough topic to outweigh the
  claim inside it, so the true pair scores below the noise from the very
  paper it restates. Windows, not sentences, are what make the tier work
  at all.
- Tier 3 also needs a step this list never named: a **local alignment**,
  because a cosine score is not a finding. That was #164, and it changed
  the tier's dependency list from `content/chroma/` alone to chroma plus
  the Docling passage sidecars -- plus, once the tier was scoped to the
  dossier, the draft's dossier as well. All three are why tier 3 reports
  itself unavailable rather than running on a checkout that has only
  some of them.

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

- [PLAGIARISM.md](PLAGIARISM.md) -- the user-facing half: what `overlap`
  and `scan` report, how to read a finding, the severity buckets and the
  boilerplate allowlist, and what a clean scan does and does not rule
  out.
- [CLI.md](CLI.md) -- the flags themselves, and the JSON payload's
  fields.
- [ARCHITECTURE.md](ARCHITECTURE.md) -- where the review layer sits, and
  `content/overlap/`'s place in the reproducibility contract.
- [LADDERS.md](LADDERS.md) -- *ladder*, *rung* and *tier* as this project
  uses them.
- `bench/RESULTS.md` -- every measurement quoted here, with the raw data
  under `bench/results/` and the command that produced it.

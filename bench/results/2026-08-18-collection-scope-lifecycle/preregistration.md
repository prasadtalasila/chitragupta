# Pre-registration: what a `--collection` filter buys a drafting run (Lifecycle replication)

Written **2026-08-18, before either arm ran.** Everything below was fixed
in advance; nothing in it was chosen after seeing a result.

This is a **replication** of `bench/results/2026-08-18-collection-scope/`,
which ran the same design earlier the same day against the
`DT Platforms` shelf and a platforms chapter. The design is deliberately
unchanged so the two runs can be read side by side; what varies is the
collection (`Lifecycle`, 19 items rather than 28), the chapter topic, and
one thing the first run got wrong and this one fixes -- see
"What this replication changes" below.

## The question

`src/retrieval.py`'s `search()` grew a `collection` argument (#195): a
draft can be retrieved against the subset of the library its owner
already curated for it, rather than against all 642 items. The feature's
claimed advantage is cheaper, better-targeted retrieval. This measures
whether that is true, and at what cost.

## The two arms

Both write the same chapter, to the same skeleton, for the same reader,
to the same word budget, with the same genre skill
(`textbook-chapter-writer`).

| | Arm F | Arm C |
|---|---|---|
| Draft | `content/drafts/book-chapters/digital-twin-life-cycle-considerations/digital-twin-life-cycle-considerations-full-corpus.md` | `content/drafts/book-chapters/digital-twin-life-cycle-considerations/digital-twin-life-cycle-considerations.md` |
| Retrieval | whole corpus (642 ledger items) | `--collection "Lifecycle"` (19 items) |
| Runs | **first** | second |

`Lifecycle` holds **19** items, verified through
`bib_collections.matches()` rather than by tallying exact path strings,
because matching is prefix-by-segment and a subcollection would fold in.
There are no `Lifecycle > …` subcollections; 19 is both the exact-path
count and the subtree count.

## Execution order is deliberately the reverse of the interesting one

Both arms run inline in one agent session. **No subagents are
dispatched** -- the user's standing instruction forbids it here, and that
constraint is what creates the ordering bias this section exists to
handle.

An agent session's context is append-only, so the **second** arm re-sends
the first arm's context on every turn and is structurally more expensive
whatever it does. Arm F therefore runs **first**, so that bias works
*against* the hypothesis. If the collection-scoped arm still measures
cheaper while carrying the full-corpus arm's context, that saving is a
lower bound.

The presentation order is the opposite -- Arm C is the deliverable the
user asked for, Arm F is the control.

## Held fixed

- **Reader, scope, glossary and learning objectives** -- written below,
  copied verbatim into both `scope.md` files.
- **Section skeleton and per-section word budget** -- the eleven sections
  below, same order, same budget.
- **Query set** -- the ten queries below, in this order, `--k 15
  --chars 500`, `--log`ged to each arm's own dossier.
- **Ledger** -- no `sync` between the two arms or before the benchmark
  replays the queries. BM25 is deterministic over a fixed ledger; that
  is what makes the replay in `bench_collection_scope.py` reproduce what
  each arm actually saw. Hashed three times to prove it (below).

## Varied

The `--collection` flag. That is the whole of it.

Either arm may issue **extra** queries beyond the ten if its first pass
turns up nothing usable -- the skill's step 3 tells it to reformulate,
and forbidding that would measure a crippled pipeline. Every extra query
is logged like any other and is reported as a **separate line**, never
folded into the pre-registered ten.

## What this replication changes

Three corrections to the first run's method, all fixed here in advance:

1. **A word budget is pre-registered.** The first run reported output
   tokens as the headline without constraining chapter length, so
   "arm C used fewer output tokens" was not separable from "arm C wrote
   a shorter chapter". Both arms here target **10,000 words** with the
   per-section budget below, actual word counts are reported beside the
   token figures, and **tokens per 1,000 words** is the normalised
   comparison.
2. **The index and the ledger are hashed three times** -- before Arm F,
   between the arms, and after Arm C -- rather than once after both arms
   had already run. That turns the "the filter never rebuilds the index"
   claim and the "the ledger did not move" precondition into evidence
   instead of a caveat.
3. **The model is checked for mid-arm switches before any token figure is
   reported.** The first run had an Opus 5 -> Sonnet 5 switch land inside
   Arm F's window, which made its arm-level totals uninterpretable. This
   session opened with `/model claude-opus-5`; the transcript is grepped
   for `"model":` values per arm rather than assumed.

## The reader (identical in both arms)

An experienced software engineer who has read *Digital Twins for
Software Engineers* end to end. They know Chapter 3's seven components
and four cross-cutting concerns, Chapter 11's twin services, Chapter 12's
build/buy/assemble decision, Chapter 14's deployment mechanics, operating
loop and expiry register, and Chapter 15's fleets and ecosystems. They
are fluent in distributed systems, release engineering, data retention
and API design; nothing about software engineering needs teaching.

What the book has **not** given them is the whole-of-life frame. Chapter
14 is the *operating* chapter: it starts with a twin already deployed and
tells them how to keep it honest. It does not answer "what happens to
this twin before it is deployed and after it stops being worth running",
nor "what happens when the asset it mirrors is replaced and the twin is
not".

## Covers

The twin's life as a life cycle: the phase model from conception to
retirement; the two-clock coupling between the physical asset's life
cycle and the twin's own, and what happens when they drift apart; the
design-time decisions that bind the twin's later life; commissioning as
the binding of a twin to one physical instance; phase-transition gates;
purpose expiry as a life-cycle event rather than an operational one; and
decommissioning -- data, models, obligations and what is owed after the
twin stops running.

## Does not cover

Deployment mechanics and release engineering (Chapter 14.2), the
operating loop's recalibration and re-validation workflows (14.3), the
operating bill (14.4), fleets and populations (Chapter 15), platform
selection (Chapter 12), the seven components themselves (Chapter 3), and
any named product.

## Learning objectives

By the end of this chapter the reader will be able to:

1. **Distinguish** the physical asset's life cycle from the twin's own,
   and **identify** which of the two governs each life-cycle decision.
2. **Derive** a twin's phase model from the commitments its purpose
   makes, and **name** the gate that has to pass at each transition.
3. **Compute** a twin's whole-of-life cost from its per-phase profile,
   and **determine** which phase decides whether it is worth building.
4. **Design** a commissioning procedure that binds a twin to one physical
   instance, and **predict** which bindings break when the asset is
   replaced.
5. **Evaluate** a twin at end-of-life, and **decide** what must be
   retained, archived or destroyed, and on whose authority.

## Section skeleton and word budget

Identical in both arms. Budgets are targets, not gates; the total is what
is compared.

| # | Section | Words |
|---|---|---|
| 1 | Before you start | 600 |
| 2 | Two clocks: the asset's life and the twin's | 900 |
| 3 | The twin's phase model, derived not assumed | 1,100 |
| 4 | Gates: what has to be true to move a phase | 900 |
| 5 | Design-time decisions that bind the whole life | 1,000 |
| 6 | Commissioning: binding a twin to one instance (fully worked) | 1,500 |
| 7 | The whole-of-life cost, worked (faded) | 1,300 |
| 8 | Expiry as a life-cycle event | 900 |
| 9 | Decommissioning and what is owed afterwards | 1,000 |
| 10 | Posed problem: the asset is replaced, the twin is not | 400 |
| 11 | Summary and exercises | 400 |
| | **Total** | **10,000** |

## The ten pre-registered queries

Derived from the skeleton above, before any retrieval ran.

| # | Query | Section it serves |
|---|---|---|
| 1 | digital twin lifecycle phases model | 3 |
| 2 | product lifecycle BOL MOL EOL digital twin | 2 |
| 3 | physical twin digital twin lifecycle synchronization coupling | 2, 10 |
| 4 | digital twin requirements engineering design phase decisions | 5 |
| 5 | digital twin commissioning handover acceptance validation | 6 |
| 6 | digital twin evolution model update maintenance over time | 8 |
| 7 | digital twin decommissioning end of life retirement archival | 9 |
| 8 | digital twin lifecycle management framework architecture | 3, 4 |
| 9 | digital twin lifecycle cost total cost of ownership | 7 |
| 10 | digital twin lifecycle industrial case study deployment | 6, 7 |

## What gets measured

| Metric | Where it comes from | Honest about |
|---|---|---|
| Tokens per arm | this session's own transcript JSONL, windowed by timestamp (`docs/TOKENS.md`) | **output** tokens and turns are the comparison; input tokens are dominated by cache-reads of the other arm and are reported with that caveat. Normalised as tokens per 1,000 drafted words |
| Words per arm | `wc -w` on each draft | the normaliser the first run lacked |
| Retrieval payload | each dossier's `retrieval.md` (`chars` column) | deterministic, and the only figure that is purely the feature's |
| Index cost | md5 of `content/retrieval_index.json` **and** `content/ledger.sqlite` at three points | expected to be *identical* throughout -- `search()` scores corpus-wide and filters the ranking, so the cache is shared and never rebuilt |
| Surfaced / selected / rejected | `bench_collection_scope.py` replays each logged query at its logged `k`, with and without the filter | `retrieval.md` records a result *count*, never which citekeys came back -- the replay reconstructs them, sound only because the ledger did not move. Selection ratio = cited / surfaced; rejection ratio = 1 - selection |
| Common papers | intersection of the two arms' cited sets and of their surfaced sets | -- |
| Verbatim overlap | `python -m src.review verbatim scan --json` per arm, same tiers both times | tier availability is reported; a clean scan is not a clean bill of health. A draft-vs-draft comparison is reported separately as an extra |

## Known confounds, stated in advance

1. **One session wrote both chapters.** The second chapter's prose is
   influenced by the first in a way two independent runs would not be.
   This inflates draft-to-draft similarity and it gets *worse*, not
   better, at 10,000 words per arm. It does **not** affect each arm's
   overlap against the *corpus*, which is what the verbatim scan
   measures.
2. **The shelf is small -- smaller than the first run's.** `Lifecycle`
   holds 19 items against `DT Platforms`' 28, so **two** `--k 15` calls
   very nearly exhaust it. Arm C's `surfaced_distinct_citekeys` is capped
   at 19 by construction while Arm F's keeps growing per query. Surfaced
   counts are therefore **not comparable as raw counts, only as ratios**,
   and Arm C's selection ratio is inflated by a denominator that cannot
   grow. This is stated here so it is not read as a finding later.
3. **This genre makes citations optional.** `evidence.md` may be thin in
   both arms, so the selection ratio rests on a small denominator.
4. **The genre skill targets undergraduates; this reader is an
   experienced engineer.** The user named the skill and the reader
   explicitly. The deviation is recorded in both `scope.md` files rather
   than resolved by switching skills, exactly as the first run did.


---

## Addendum, 2026-08-18: the brief changed mid-run

Recorded here rather than edited into the text above, so the pre-registration
stays a record of what was fixed in advance and what was not.

After Arm F's first full draft was written, the user restricted the use of
`draft/books/digital-twins-for-software-engineers`, first to nothing at all and
then, on refinement, to two named exceptions: the plant/pot/pump demonstrator
as the running example, and the book's seven twin components -- with **nothing
from Chapter 14** permitted. Arm F's draft was rewritten to that brief and the
reader/scope statement above was superseded by the corrected one now in both
arms' `scope.md`.

**What this does and does not affect:**

- **Queries: unaffected.** All ten pre-registered queries had already run
  against the full corpus before the steering arrived, and none of them
  mentions the book. The retrieval measurement -- payload, surfaced set,
  selection ratio -- is untouched.
- **Skeleton, word budget, reader level: unaffected.** The eleven sections and
  the 10,000-word target stand. The reader is the same experienced engineer.
- **Arm F's token count: affected, and quarantined.** Arm F paid for one
  complete rewrite that Arm C never pays, because Arm C was drafted once
  against the corrected brief. That cost is reported as a **separate phase**
  and is excluded from the arm-to-arm comparison, in the same way extra queries
  are reported separately rather than folded into the pre-registered ten.
  Reporting Arm F's raw total against Arm C's would overstate the collection
  filter's saving, which is the opposite of this design's bias, and is not
  reported that way.
- **Arm ordering: unaffected and still conservative.** Arm F still runs first
  and Arm C still inherits its context.

One measurement note, unrelated to the steering: the payload for Arm F's
queries 6--10 was piped to `tail` on its first execution and so never entered
the drafting context. Those five queries were re-issued **without** `--log` and
read in full, so `retrieval.md` records each of the ten exactly once and the
payload entered context exactly once. Roughly 3 KB of tail output entered
context twice; no other double-counting occurred.

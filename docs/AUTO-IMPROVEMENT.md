# Proposal: an auto-improvement loop over an existing draft

Status: **a proposal, not a plan.** Written 2026-08-11.

Nothing described here is built. `python -m src.review agenda` is not a
command that exists, and no review aid emits JSON. This document argues a case,
names where each piece would sit, and records the one documented rule it
cannot satisfy without an amendment the user has to approve. The decision
has not been taken.

**Written for** someone weighing whether this repository should be able
to improve a draft on its own, rather than only tell a human what is
wrong with it. It assumes [ARCHITECTURE.md](ARCHITECTURE.md) for the four
layers, [DRAFT-ITERATION.md](DRAFT-ITERATION.md) for the dossier and the
drift sweep, and [PLAGIARISM.md](PLAGIARISM.md) for the detection tiers.

**Not covered here:** growing the corpus. Nothing proposed reaches
outside `content/ledger.sqlite`, fetches a paper, or writes
`bibliography.bib`. Papers still enter through the reference manager
([SOUL.md](../SOUL.md)), and every improvement this loop makes is a
re-arrangement of evidence the ledger already holds.

## Table of contents

- [The gap: detection is built, remediation is not](#the-gap-detection-is-built-remediation-is-not)
- [Four signals, four dead ends](#four-signals-four-dead-ends)
- [Where the loop sits, and the cycle that decides it](#where-the-loop-sits-and-the-cycle-that-decides-it)
- [Proposed design](#proposed-design)
- [Respecting the invariants](#respecting-the-invariants)
- [The amendment this needs](#the-amendment-this-needs)
- [Ordering, on #126's own rule](#ordering-on-126s-own-rule)
- [The software half](#the-software-half)
- [What it would cost](#what-it-would-cost)
- [What this does not change](#what-this-does-not-change)
- [Open questions](#open-questions)

## The gap: detection is built, remediation is not

This repository is unusually good at noticing that a draft has a problem
and unusually bad at doing anything about it. Every quality signal it
produces terminates in prose that a human must read, hold in their head,
and hand-translate into a revision request.

That is a deliberate posture, not an oversight -- the review layer is
advisory by construction, and [SOUL.md](../SOUL.md) is explicit that
"does this source support this sentence" is not a question a machine gets
to settle. But *deciding* is not the same as *assembling*. The tedious
part of acting on a review report is not the judgement; it is reading
three prose documents, reconciling them against the section map, dropping
the ones `rejected.md` already declined, and dispatching a reviser per
survivor. None of that is a judgement call, and all of it is currently
manual.

The claim of this proposal is narrow: **the pipeline should assemble the
worklist, attempt the mechanical repairs, and re-verify them -- and the
human should still decide.**

Issue #129 already scopes exactly this loop for one signal (verbatim
runs). What follows is that shape generalised to the other three, plus
the class of improvement none of them cover.

## Four signals, four dead ends

Four commands carry every quality signal this repository has, and each
one is a dead end. The fifth row is not a signal at all -- its absence is
the point, and the `prose` item class below is what would fill it.

| Signal | What it finds | What it emits | Who acts on it |
|---|---|---|---|
| `draft dossier status --all` | a cited citekey that has left the ledger; a newly reachable paper the dossier never weighed | text, or `--json` | human, by hand |
| `review provenance` | a citation whose source does not visibly support it | Markdown report | human, by hand |
| `review verbatim scan` | wording shared with a parsed source | Markdown report | human, by hand |
| `review coverage` | a source retrieval surfaced that the draft never cited | Markdown report | human, by hand |
| *nothing* | a sentence that is simply badly written | -- | human, by hand |

Two things stand out. **Only the drift sweep is machine-readable** --
`--json` on `dossier status --all` is the single machine-readable output
in the whole quality surface (`grep -rn '\-\-json' src/` returns one
file). And **prose quality has no signal at all**: `draft-reviser` is
section-and-evidence-shaped, and #103 records that a copy-edit touching
no evidence has no sanctioned path through it.

## Where the loop sits, and the cycle that decides it

The obvious placement is a new drafting-layer verb -- `python -m
src.draft agenda <draft>` -- reading the review reports and emitting a
worklist. **That placement is wrong, and the reason is the one cycle this
repository already removed.**

[ARCHITECTURE.md](ARCHITECTURE.md#the-four-layers) states the dependency
graph as acyclic and artefact-mediated, with exactly one edge into the
review layer:

```
corpus ──ledger, parsed/──▶ drafting ──draft──▶ review
```

Review has no outgoing edge, and that is load-bearing: until 4.0.0 the
enrichment layer hosted `provenance` and `render` stages that imported
the review and drafting layers, and removing them is recorded in both
[AGENTS.md](../AGENTS.md) and ARCHITECTURE.md as closing "the one cycle
in this picture". A drafting-layer command reading `content/review/*.json`
re-opens it in the other direction.

**The edge that matters is the artefact edge, not the import.** Review
already imports drafting-layer code -- `citation_provenance` imports
`citation_gate` and `ledger`, `citation_coverage` imports `retrieval`,
and `review/__init__.py` imports `render_output` -- and that is fine,
because those are tier-1 modules being *called*, downhill, by the layer
that reads their output. The acyclicity ARCHITECTURE.md claims is of the
artefact graph: who writes a file that whom reads. `content/review/*.json`
is a layer-4 artefact, and a layer-2 command consuming it is a new edge
in that graph, which nothing else in the repository has.

The alternative has no such problem. `review.AIDS` is an explicit,
guarded extension point -- `src/review/__main__.py` raises a
`RuntimeError` (not an assert, deliberately) if its subcommands drift
from that dict, which exists so a fourth aid can be added safely. An
agenda is "evidence for a human judgement, never a verdict", which is the
review layer's charter word for word, and as an aid it inherits
`report_dir`, `report_path`, `write` and the exits-0-always posture for
free. Reading the other three aids' output is an edge *within* layer 4.

So: **the deterministic half is a fourth review aid; the generative half
is a skill; and the human, not code, closes the loop between them.** That
last clause is what keeps the graph acyclic -- a skill reading a review
report is the same act as a human reading one, which the layer already
expects.

## Proposed design

Four pieces, in dependency order.

### 1. `--json` on all three review aids

`src/review/__init__.py` owns one output contract for the layer; extend
it with a JSON sibling beside the Markdown, at
`content/review/<topic>/<stem>.<aid>.json`. This is #127's change
(currently scoped to `verbatim_check` alone) applied to the layer rather
than to one aid, so the report contract does not fork.

The JSON is an additional serialisation of the same findings list, never
a second computation -- #127's wording, and the property that keeps the
printed form authoritative and the existing tests load-bearing. The
Markdown stays the default output.

The same no-timestamp rule applies for the same reason: two runs over an
unchanged draft and corpus produce byte-identical JSON, so the agenda
below is diffable across revisions.

### 2. `python -m src.review agenda <draft>` -- the fourth aid

Deterministic, stdlib-only, no LLM, exits 0 whatever it finds. It reads:

- the three aids' `.json` for this draft, each optional and skipped with
  a note if absent (the layer's standing probe-don't-assume rule);
- `src.dossier.status(draft)` for missing citekeys and candidates;
- `rejected.md`, so a candidate the dossier already turned down with a
  reason is **never re-proposed** -- `corpus-reviser` already honours
  this and an agenda that did not would re-offer the same papers every
  run;
- `sections.md`, so every item carries a section anchor and the reviser
  can stay scoped.

It emits `<stem>.agenda.md` and `<stem>.agenda.json`: an ordered,
deduplicated worklist. One finding may appear in two aids' output (an
uncited source is both a coverage finding and, if quoted, a verbatim
one); the agenda merges them into one item, which is the cross-signal
work no individual aid can do.

**Item classes**, each with a different licence to act:

| Class | Source | Kind | May be attempted unattended? |
|---|---|---|---|
| `missing-citekey` | drift | defect -- the gate will fail on it | yes |
| `verbatim-run` | verbatim scan | defect above a span threshold | yes, per #129's constrained rewrite |
| `prose` | style check (#107), user request | no evidence delta | yes |
| `unsupported-claim` | provenance | judgement | no -- surfaced |
| `uncited-source` | coverage | judgement | no -- surfaced |
| `candidate` | drift | a decision, usually correct to decline | no -- surfaced |

The split is [DRAFT-ITERATION.md](DRAFT-ITERATION.md#two-findings-and-they-are-not-the-same-kind-of-thing)'s
defect-versus-decision distinction, extended across all four signals. It
is the whole safety argument: **the loop only ever acts unattended on the
classes where the correct outcome is not a matter of opinion**, and the
rest it ranks and hands over.

The `prose` class is in the table because "improve the draft" is broader
than "fix the citations", and an agenda that could not carry a badly
written sentence would be structurally unable to do half the job. It has
no consumer until #103's copy-edit branch and #107's `style_check.py`
land; until then it is an empty list, which is honest rather than absent.

### 3. A `draft-improver` skill -- the generative half

A skill, not a `src/` module: it is generative, it needs a model, and
this repository intentionally ships no API key. It consumes
`<stem>.agenda.json` and, per item:

- dispatches the existing `draft-reviser` discipline -- read `scope.md`
  and `steering.md` first, edit inside the named section with `Edit`,
  never a whole-file `Write`;
- re-runs `python -m src.draft gate` **and** the aid that produced the
  finding, and accepts the edit only if both come back clean;
- writes one `revisions.md` entry naming the item, what changed, and
  which check confirmed it -- so edit provenance is as auditable as
  citation provenance (#129's phrasing).

**Termination is a rule, not a hope.** Each item is attempted at most
twice; a second failure escalates it to the human as a surfaced item and
the loop moves on. The loop never adds a claim -- it edits, removes, or
re-grounds existing ones -- so it cannot grow the draft indefinitely. And
it stops at the end of one agenda pass; a second pass is a second
invocation, by a human.

### 4. Acceptance and rollback

The loop runs against a `python -m src.draft dossier backup` taken first,
so the existing backup/restore path is the rollback story and no new
mechanism is needed. What the human is presented with at the end is a
diff plus the `revisions.md` entries, not a fait accompli -- **the loop
proposes and repairs; the human accepts.**

## Respecting the invariants

- **The citekey invariant is untouched.** Every item names citekeys the
  ledger already holds. The loop cannot introduce a citekey, because the
  only classes it acts on unattended are *removals* and *rewordings*.
- **`src.draft gate` stays the only gate.** No finding is promoted to
  blocking by anything here. #130 explicitly defers the gating decision
  until the remediation loop has produced real reports, and this proposal
  keeps that ordering rather than short-cutting it -- including for
  `missing-citekey`, which is tempting precisely because the gate will
  fail on it anyway.
- **The review layer still never blocks.** `agenda` exits 0 with a full
  worklist, exactly as the other three aids do with findings.
- **No machine outranks a human on a judgement call.** Three of the six
  item classes are surfaced rather than acted on, and `rejected.md` --
  the human's recorded "no" -- is consulted before anything is proposed.

## The amendment this needs

One documented rule this cannot satisfy. It is about *who may invoke* a
review aid, and the loop's driver invokes them. This sweep surfaces the
candidates:

```bash
grep -rniE "never automatic|never invoked|reads it back|runs automatically" \
  --include='*.md' --include='*.mmd' --include='*.py' .
```

It is a starting point rather than the answer -- it also hits phrases
that have nothing to do with the review layer (`AGENTS.md`'s "reads it
back out of the ledger", a `tests/test_sync.py` docstring's "never
invoked"), and it hits this document. **Twelve** of its matches are real
statements of the rule:

| Site | Wording |
|---|---|
| `src/review/__init__.py`, `BANNER` | "Nothing in this pipeline reads it back" |
| `src/review/__init__.py`, docstring | "None gates, none runs automatically" |
| `src/review/__main__.py`, docstring | "nothing invokes them automatically" |
| `src/review/citation_provenance.py`, docstring | "never automatically, never a gate" |
| `src/review/citation_coverage.py`, docstring | "never automatically, never a gate" |
| `src/review/verbatim_check.py`, docstring | "never automatically, never a gate" |
| [AGENTS.md](../AGENTS.md), Layer 4 | "run by hand on a finished draft, never invoked automatically" |
| [ARCHITECTURE.md](ARCHITECTURE.md#layer-4-the-review-layer), §Layer 4 | "Nothing invokes them automatically" |
| [ARCHITECTURE.md](ARCHITECTURE.md), inline mermaid label | "advisory, never automatic, never a gate" |
| [LADDERS.md](LADDERS.md), the layer table | "never automatic, never a gate" |
| [CLI.md](CLI.md), the first-run walkthrough | "none of these runs automatically" |
| [CLI.md](CLI.md), §coverage | "unlike the gate it never runs automatically" |

**No diagram needs regenerating.** The `.mmd` sources say only "never a
gate" and "you run these" -- both still true -- so the committed SVGs
under `docs/diagrams/svg/` are unaffected. The one mermaid label that
does carry "never automatic" is inline in ARCHITECTURE.md, so it is a
text edit like the rest.

The surviving invariant is the one that was always doing the work, and it
is narrower than the current wording: **a review finding may be read, may
be invoked by a driver, and may never block a draft.** Advisory versus
blocking, not manual versus automatic. `src.draft gate` remains the only
gate.

That is a coherent rule and the loop obeys it -- but it is a change to
the review layer's stated posture in the user-facing rules file, and
[SOUL.md](../SOUL.md) reserves that kind of call for the user. **It is
the first thing to settle, before any code.** If it is declined, the
agenda aid can still be written and run by hand, and only step 3's
automation is lost.

## Ordering, on #126's own rule

This is not a new track. #126 already states the dependency argument for
exactly this shape:

> findings must be machine-readable before anything can consume them,
> buckets and an allowlist must exist before a gate threshold can be
> tuned without alarm fatigue, and the remediation loop should produce
> real reports before the gating decision is made

The proposal is that #126's ordering is right and its *scope* is one aid
too narrow. Interleaved:

1. **Settle the amendment above.** Not a coding task.
2. **#127, widened** -- `--json` for all three aids, in the shared
   contract. Hard prerequisite for everything below.
3. **#128** -- severity buckets and the boilerplate allowlist, so the
   agenda's `verbatim-run` items are not mostly noise.
4. **`agenda`, the fourth aid.** New. Deterministic, testable to the
   repo's 100% bar, and useful on its own the day it lands -- a human
   with a ranked worklist is better off than a human with three reports,
   whether or not step 5 is ever built.
5. **#129, widened** -- the `draft-improver` skill, over all defect
   classes rather than verbatim runs alone.
6. **#103 and #107** -- the copy-edit branch and `style_check.py`, which
   give the `prose` class a producer and a consumer.
7. **#130** -- the gating decision, still last, still tuned against real
   reports from step 5 rather than guessed.

Steps 4 and 5 are the only new work. Everything else is already an open
issue.

## The software half

The user's question also asked whether the same idea can improve the
software. It can, but it is the smaller half, and the honest verdict is
that **the gap is signal, not permission.**

[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) already grants an agent the
whole cycle -- "implementing features, writing tests first, running the
full local check suite, opening PRs, watching CI, merging, and cutting
releases [...] proceed autonomously". CI runs on two platforms with a
coverage floor. The backlog is labelled and dependency-ordered. Nothing
is missing on the authorisation side.

What is missing is an objective signal an unattended agent could act on:

- **`bench/` records results but never compares them.**
  `bench/results/*/` holds real timings from named machines, and nothing
  reads them back to say a change made the parse slower. A
  compare-to-baseline step -- same host, same fixture corpus, a
  tolerance -- would turn performance from something a human notices into
  something a run reports. That is the single highest-value piece, and it
  is the same "measurement before mechanism" principle #63 already states
  for retrieval.
- **A backlog groomer that stops at proposing.** A scheduled agent can
  read the open `enhancement, parked` issues plus CI and coverage state
  and propose the next rung with its dependency edges checked. It should
  not open the PR: every PR here bumps `pyproject.toml`, so two
  concurrent PRs always conflict on the version line, which forces the
  work serial regardless of how much of it an agent could parallelise.

Both are `bench/`, `.github/` and `.claude/` changes. Neither is a
pipeline layer, and neither should acquire one.

## What it would cost

- **Steps 2-4 are cheap and additive.** JSON serialisation of an existing
  findings list, plus one new stdlib-only aid reading files that already
  exist. No new dependency, no venv requirement, tier 1, no lock.
- **Step 5 is where the tokens go.** One reviser dispatch per agenda item
  plus a re-check per attempt. It is bounded -- two attempts per item, one
  pass per invocation -- but a long agenda on a long draft is a real run.
  [TOKENS.md](TOKENS.md) has the arithmetic this would extend; the
  saving to weigh it against is that today the same work happens as a
  human-driven sequence of full `draft-reviser` invocations, each paying
  its own start-up read of the dossier.
- **The risk is alarm fatigue, not correctness.** An agenda that is
  mostly boilerplate verbatim hits gets ignored, which is why #128
  precedes the aid rather than following it.

## What this does not change

- No new gate. `src.draft gate` is still the only one, and #130 is still
  the place that decision gets made.
- No corpus growth. The loop never fetches, never writes the ledger, and
  never proposes a paper that is not already in it.
- No new layer. Four layers, one new aid in the fourth, one new skill in
  the second.
- No new entry point. `python -m src.review agenda <draft>` is one verb
  under an existing front door, at depth 1, as #144's CLI invariant
  requires.

## Open questions

- **Does `agenda` strain the aid vocabulary?** `review.AIDS` values are
  both report titles and filename suffixes, so this ships as
  `survey.agenda.md`. It reads as a report and it is evidence for a human
  judgement -- but it is the first aid that reads other aids, and whether
  that belongs in the same dict is a real question.
- **Should `missing-citekey` be acted on unattended at all?** Removing a
  citation the corpus no longer supports is objective in the sense that
  the gate will fail either way, but *what replaces the sentence* is not.
  The conservative alternative is to surface it with a suggested edit
  rather than apply one.
- **How does the agenda behave on a draft with no dossier?** Every aid
  degrades honestly today; the agenda would lose `rejected.md` and the
  section map, which are the two things keeping it scoped and
  non-repetitive. Refusing may be the right answer here even though no
  other aid refuses.
- **Does the loop belong to `draft-reviser` as a branch instead of a new
  skill?** It is "a change to an existing draft", which is that skill's
  charter -- the argument for separation is that its input is a file
  rather than a person.

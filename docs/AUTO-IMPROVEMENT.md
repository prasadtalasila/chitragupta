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
- [The method, in autoresearch's own terms](#the-method-in-autoresearchs-own-terms)
- [Mapping the method onto this pipeline](#mapping-the-method-onto-this-pipeline)
- [What can improve without supervision](#what-can-improve-without-supervision)
- [Across many drafts: what accumulates](#across-many-drafts-what-accumulates)
- [The amendment this needs](#the-amendment-this-needs)
- [Ordering, on #126's own rule](#ordering-on-126s-own-rule)
- [The software half](#the-software-half)
- [What it would cost](#what-it-would-cost)
- [What this does not change](#what-this-does-not-change)
- [Open questions](#open-questions)
- [Naming, and the register the review layer may not use](#naming-and-the-register-the-review-layer-may-not-use)

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
| `python -m src.draft dossier status --all` | a cited citekey that has left the ledger; a newly reachable paper the dossier never weighed | text, or `--json` | human, by hand |
| `python -m src.review provenance` | a citation whose source does not visibly support it | Markdown report | human, by hand |
| `python -m src.review verbatim scan` | wording shared with a parsed source | Markdown report | human, by hand |
| `python -m src.review coverage` | a source retrieval surfaced that the draft never cited | Markdown report | human, by hand |
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

**Every finding needs a stable identity.** The merge above, the
"is this finding gone?" re-check in step 3, and the diffability the
no-timestamp rule buys are all impossible without a key that survives a
re-run: `(aid, class, section anchor, citekey, a hash of the matched
span)` or similar. The aid is billed as deterministic and testable to
this repository's 100% bar, so the key belongs in the JSON schema rather
than in a consumer's head.

**The order is a rule, not a preference**, for the same reason: class
order as the table below lists it, then #128's severity bucket within a
class, then position in the draft. Written down, it is testable; left
implicit, two runs can disagree.

**Item classes**, each with a different licence to act:

| Class | Source | Kind | May be attempted unattended? |
|---|---|---|---|
| `missing-citekey` | drift | defect -- the gate will fail on it | yes |
| `verbatim-run` | verbatim scan | defect above a span threshold | yes, except the long runs #129 reserves |
| `prose` | style check (#107), `steering.md` | no evidence delta | only what #107 can mechanically re-check |
| `unsupported-claim` | provenance | judgement | no -- surfaced |
| `uncited-source` | coverage | judgement | no -- surfaced |
| `candidate` | drift | a decision, usually correct to decline | no -- surfaced |

The split is [DRAFT-ITERATION.md](DRAFT-ITERATION.md#two-findings-and-they-are-not-the-same-kind-of-thing)'s
defect-versus-decision distinction, extended across all four signals. It
is the whole safety argument: **the loop only ever acts unattended on the
classes where the correct outcome is not a matter of opinion**, and the
rest it ranks and hands over.

Two of the "yes" cells are narrower than they look, and the safety
argument is why:

- **`verbatim-run` inherits #129's carve-out.** That issue reserves the
  paraphrase-or-quote choice for the human on long runs, "not decided
  silently". A blanket yes here would misquote the issue this step is
  widening. Short runs are rewritten; long ones are surfaced with both
  options.
- **`prose` splits.** "A sentence that is badly written" is the
  definition of a matter of opinion, so free-form prose quality is
  surfaced like any other judgement. What the loop may fix unattended is
  the mechanically re-checkable subset #107's `style_check.py` would
  produce -- a dialect convention, a banned construction, a house-style
  rule -- where "did the fix work?" has one answer. The class is in the
  table at all because "improve the draft" is broader than "fix the
  citations", and an agenda structurally unable to carry a sentence
  would be doing half the job. It has no producer until #103 and #107
  land; until then it is an empty list, which is honest rather than
  absent.

### 3. An `agenda-reviser` skill -- the generative half

A skill, not a `src/` module: it is generative, it needs a model, and
this repository intentionally ships no API key.

**Named for its input, like the two revisers it joins.** `draft-reviser`
revises from the dossier and `corpus-reviser` from a whole-corpus
re-search; this one revises from the agenda, so the family's prefix
keeps naming the evidence a revision works from. Not `draft-improver`:
"improver" presumes the outcome, which is the verdict shape this layer
refuses. Not `auto-reviser` either -- see [The
amendment](#the-amendment-this-needs), which argues the axis that
matters is advisory-versus-blocking, not manual-versus-automatic. A name
built on `auto-` would re-enshrine in the vocabulary the very
distinction the amendment dissolves, and would overclaim autonomy in a
design where a human still accepts every diff.

It consumes `<stem>.agenda.json` and, per item:

- dispatches the existing `draft-reviser` discipline -- read `scope.md`
  and `steering.md` first, edit inside the named section with `Edit`,
  never a whole-file `Write`;
- re-runs `python -m src.draft gate` **and** the aid that produced the
  finding, and accepts the edit only if both come back clean;
- logs the attempt in `revisions.md` -- **including the ones that
  failed**, naming the item, what was tried, and which check refused it.
  A log of only the accepted edits hides where the loop is weak, which is
  the half worth reading.

**Termination is a rule, not a hope.** Each item is attempted at most
twice; a second failure escalates it to the human as a surfaced item and
the loop moves on. The loop never adds a claim, and on the unattended
classes it only removes or rewords existing ones, so it cannot grow the
draft indefinitely. And it stops at the end of one agenda pass; a second
pass is a second invocation, by a human.

### 4. Acceptance and rollback

**Two levels, because they undo different things.** Before the pass, one
`python -m src.draft dossier export <slug>` -- the existing bundle path,
and the only one available, since `content/drafts/` and
`content/dossiers/` are both gitignored, so a user's own drafts are not
in git and a branch-per-run has nothing to branch. Within the pass, the
skill holds each section's pre-edit text and re-applies it when an item
fails, because the export is a whole-tree snapshot: restoring it after
item four fails would also throw away the three repairs that worked.
Saying "no new mechanism is needed" would be overclaiming -- per-item
revert is new, and it is what makes the bundle a belt rather than the
only brace.

**Nothing the loop learns is written where it becomes permanent.** A
failed attempt goes in `revisions.md`, never into `rejected.md`:
[REJECTION.md](REJECTION.md) is explicit that writing an unpursued
candidate there manufactures a judgement that later runs then trust
forever. A source the human turned down and an edit the machine could
not land are different ledgers.

What the human is presented with at the end is a diff plus the
`revisions.md` entries, not a fait accompli -- **the loop proposes and
repairs; the human accepts.**

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
- **The checks are ground truth, and the loop may not touch them.** The
  skill may edit the draft and append to `revisions.md`. It may not edit
  an aid, the gate, #128's boilerplate allowlist, `rejected.md`,
  `scope.md`, or anything under the corpus layer. This is the one rule
  the design would otherwise be missing, and the failure mode is
  concrete rather than theoretical: a rewrite that keeps failing the
  re-scan can always be "fixed" by adding its phrase to the allowlist,
  and a loop that can suppress its own findings is not improving a draft
  but gaming a metric. Borrowed directly from
  [autoresearch](#the-method-in-autoresearchs-own-terms), whose
  agent may edit exactly one file and is told the evaluation harness is
  read-only.
- **A repair may not make the draft worse somewhere else.** A per-finding
  re-check only proves the finding it was aimed at is gone. After each
  accepted edit the loop re-runs *every* aid and requires the total count
  of objective-class findings to be non-increasing; if it rose, the edit
  is reverted and the item escalated. That is the nearest thing this
  design has to a scalar that must go down, and the reason it is needed
  is in the section below.

## The method, in autoresearch's own terms

[karpathy/autoresearch](https://github.com/karpathy/autoresearch) (MIT,
per its README) is the nearest published thing to what this proposes, and
it is worth stating properly rather than gesturing at, because the parts
that make it work are not the parts it is famous for.

**Three files, and the split between them is the design.**
`prepare.py` holds the constants, the data preparation and -- decisively
-- the evaluation function; it is read-only. `train.py` holds the model,
the optimiser and the training loop; it is the *only* file the agent
edits, and within it everything is fair game. `program.md` holds the
agent's instructions, and it is the only file the *human* edits. The
README is explicit that this inversion is the point: "you're not touching
any of the Python files like you normally would as a researcher. Instead,
you are programming the `program.md` Markdown files that provide context
to the AI agents and set up your autonomous research org." `program.md`
is, in its own words, "essentially a super lightweight skill".

**One number, one budget.** Training always runs for exactly five minutes
of wall clock, and the score is `val_bpb` -- validation bits per byte,
lower better, and vocabulary-size-independent so that architectural
changes compare fairly. The fixed budget is a control variable, not a
resource cap: it is what makes two experiments answers to the same
question rather than to different ones.

**The loop, as `program.md` states it.** Branch (`autoresearch/<tag>`);
establish a baseline by running the code unmodified; then repeat: hack
`train.py` with one idea, commit, run redirecting all output to a log
(explicitly *not* to the terminal, so the transcript does not flood the
agent's context), grep two numbers back out of that log, and decide. If
`val_bpb` fell, advance the branch and keep the commit. If it did not,
`git reset` back to where the iteration started. Every attempt gets one
row in `results.tsv`: commit, score, memory, `status` of
**`keep` / `discard` / `crash`**, and a one-line description of what was
tried. Crashes are diagnosed from the log's tail, fixed if the fault is
trivial, abandoned if the idea itself is broken. A run exceeding double
its budget is killed and treated as a failure.

**Two rules that are easy to miss.** The first is a tie-breaker: *all
else being equal, simpler is better* -- an improvement bought with twenty
lines of hacky code is probably not worth it, while an equal result from
*deleting* code is a win outright. The second is the posture: **"NEVER
STOP"** -- once the loop has begun, do not ask the human whether to
continue, because "the human might be asleep", and the loop runs "until
the human interrupts you, period".

## Mapping the method onto this pipeline

Component for component, the correspondence is close enough to be useful
and different enough to be dangerous.

| autoresearch | Here | Note |
|---|---|---|
| `train.py` -- the one file the agent edits | the draft under `content/drafts/` | Same discipline: one artefact, reviewable diffs |
| `prepare.py` + `evaluate_bpb` -- read-only ground truth | the three review aids, `src.draft gate`, #128's allowlist | The loop may run them and may not edit them |
| `program.md` -- edited by the human, not the agent | `.claude/skills/`, `scope.md`, `steering.md`, `docs/WRITING-STANDARDS.md` | See [Across many drafts](#across-many-drafts-what-accumulates) |
| `val_bpb` -- one global scalar | the count of objective-class findings over all aids | Coarser, and the reason for the binary rule below |
| the fixed five-minute budget | *nothing, deliberately* | Its runs compete; agenda items do not |
| `results.tsv`, one row per attempt | `revisions.md`, including refused attempts | Same keep/discard/crash discipline, existing file |
| branch advance-or-`git reset` | `dossier export` + per-item revert | Drafts are gitignored; the granularity is what transfers |
| "NEVER STOP" | two attempts per item, one pass, hand back | Inverted, for the reasons below |

| Its design choice | Transfers? |
|---|---|
| **The evaluation harness is read-only ground truth** -- the agent edits `train.py` and may not touch `prepare.py` or `evaluate_bpb` | **Yes, and it is the rule this proposal most needed.** See the invariant above |
| **Keep / discard / crash, one row per attempt** in `results.tsv` | **Yes, as discipline.** The failure rows outnumber the keeps and are where the learning is, which is why `revisions.md` logs refused attempts too. Not as a file: `revisions.md` already exists |
| **Simplicity as the tie-breaker** -- "removing something and getting equal or better results is a great outcome" | **Yes.** Where a deletion and a rewrite both pass re-check, prefer the smaller diff, and prefer cutting a redundant claim to rewording it. That is [SOUL.md](../SOUL.md)'s substantive-editor posture already |
| **Baseline first** -- the first run establishes the number everything else is measured against | **Yes.** The agenda taken before the pass is that baseline |
| **One scalar metric that must go down (`val_bpb`)** | **Partly, and the gap is real.** The asymmetry is not boolean-versus-scalar, it is local-versus-global: `val_bpb` catches a regression *anywhere*, while a per-finding re-check cannot see that fixing one verbatim run introduced another. Hence the non-increasing objective-finding-count rule above -- a coarse scalar, but a global one |
| **A fixed per-iteration budget** (five minutes, so runs are comparable) | **No, and it is not needed.** Its experiments are competing alternatives on one leaderboard, so they must be comparable. Agenda items are independent repairs that do not compete |
| **A dedicated git branch, advanced or reset per experiment** | **No -- structurally unavailable.** `content/drafts/` and `content/dossiers/` are gitignored, so a user's drafts are not in git. What must transfer is its *granularity*: one experiment reverts alone, which is why step 4 adds per-item revert rather than relying on the whole-tree bundle |
| **"NEVER STOP ... do NOT pause to ask the human"** | **No, and the opposite is correct here.** Four reasons, below |

**On never stopping.** It is the most quotable thing in `program.md` and
the least transferable. A discarded training run costs five GPU-minutes
and the metric catches it; a wrong scholarly claim is silent and ships.
Unattended looping is only safe under a metric that catches compounding
damage, and this design's is coarse. Three of six item classes need a
human whatever the loop does, so an indefinite loop either starves or
creeps into judgement. And its per-iteration cost is fixed where this
one's token cost is not. The bounded design is argued, not timid.

Where this proposal may genuinely be too cautious is narrower: "one pass
per invocation". A bounded-convergence variant -- keep passing while the
objective-class count strictly falls, to a hard maximum -- still
terminates deterministically and is closer to advance-while-improving.
It is declined here for legibility, not safety, and could be revisited.

### The requirements that follow

Everything above lands as nine obligations on whoever builds this. Each
is stated so that a reviewer can tell whether it has been met, and each
comes from a row of the mapping table rather than from taste.

| | Requirement | From |
|---|---|---|
| **R1** | The skill's write-set is exactly the draft and `revisions.md`. It may execute an aid, the gate and `style_check`; it may not edit them, nor #128's allowlist, `rejected.md`, `scope.md`, or anything under the corpus layer. | read-only harness |
| **R2** | Every finding carries an identity stable across runs, so "this finding is gone" and cross-aid dedup are both decidable. | `val_bpb` is re-computable; a finding must be too |
| **R3** | An unattended item's check is **binary**. No continuous score is ever the thing being optimised. | see below |
| **R4** | After each accepted edit, every aid re-runs and the total objective-class count must not rise, else the edit reverts. | `val_bpb` is global |
| **R5** | Reverting one item leaves every earlier accepted item intact. | `git reset` granularity |
| **R6** | Every attempt is logged with its outcome, refusals included, and no machine outcome is ever written to `rejected.md`. | `results.tsv`; [REJECTION.md](REJECTION.md) |
| **R7** | Two attempts per item, one pass per invocation, then hand back. | "NEVER STOP", inverted |
| **R8** | Where a deletion and a rewrite both pass, the smaller diff wins. | the simplicity tie-breaker |
| **R9** | The agenda taken before the pass is the recorded baseline, and the closing report is stated against it. | baseline-first |

## What can improve without supervision

The honest answer is that it depends entirely on one property of the
check, and naming that property is more useful than any list.

> **An unsupervised loop may only be pointed at a check whose
> satisfaction is binary.** A continuous score invites the loop to
> optimise the score instead of the draft.

This is why "improve the readability" is a trap and "apply §2" is not.
A readability index -- Flesch-Kincaid and its relatives -- is a number to
be maximised, and a loop maximising it will shorten sentences past sense
and strip the technical vocabulary that made the draft accurate, scoring
better while reading worse. [WRITING-STANDARDS.md](WRITING-STANDARDS.md)
§2 and §4, by contrast, are conformance rules: "obviously" is present or
it is not; an acronym is expanded at first use or it is not; a paragraph
leads with its point or it does not. Nothing is being maximised, so there
is nothing to game. R3 exists to keep that line, and it is the same
reason R4 counts findings rather than scoring quality.

**Language is therefore the axis that autoresearches best**, which is
the reverse of the intuition that prose is the soft part. The repository
is already most of the way there: §2's defect markers ("obviously",
"simply", "just", "of course", "clearly", "easy") and §4's rules are
written as mechanical tests, #104 would record the draft's dialect in
`scope.md` where a later pass can read it, and #107 would compute
dialect consistency and banned-word counts in stdlib, exit-0, as a review
aid. That is a detector, a recorded target and a re-check -- the whole
apparatus an unattended loop needs, and none of it costs a token.

**Provenance is the axis that cannot, and the reason is mechanical
rather than principled.** It is tempting to say a machine may not judge
whether a source supports a sentence because SOUL.md forbids it. The
stronger reason is that **the loop cannot detect its own failure here.**
A paraphrase that subtly misstates what a paper claims passes the gate,
because the citekey is still real; passes the verbatim scan, because the
wording now differs -- which is precisely what "fixing" an overlap
*means*; and passes provenance, if the source remains topically related.
Every check the loop owns returns clean on its worst output. What can
improve unattended on that axis is ordering and surfacing -- which
sections are least supported, which citations rest on the thinnest
passage -- never the fix.

Between those poles:

| Property | Binary? | Unattended? |
|---|---|---|
| Dialect conformance against `scope.md`'s `language:` | yes | yes (#104, #107) |
| §2's defect markers | yes | yes |
| Acronym expanded at first use; term defined once | yes, given the dossier glossary | yes |
| Terminology and notation used consistently | yes, given a registry | yes (#138's detectors) |
| Cross-references resolve | yes | yes (#138) |
| Duplicate or near-duplicate sentences across sections | yes, at a threshold | yes (`src/overlap_index.py` already indexes n-grams) |
| A section citing nothing at all | yes | surfaced -- the fix is evidence, not wording |
| Reference-list consistency | yes | already deterministic (`src/references.py`) |
| Verbatim overlap with a source | yes, at a threshold | yes, minus #129's long runs |
| Sentence length, hedging density, passive voice | **no -- these are scores** | surfaced only |
| Readability index | **no** | never an objective |
| Does this source support this claim | no | never |

**One reconciliation.** #138 proposes those registries as "deterministic,
**blocking** global checks ... beside the citation gate". This proposal
borrows its *detectors* and declines its blocking posture: nothing here
becomes a gate, and #130 remains the only place that decision is taken.
If #138 lands as specified the two must be squared, and the squaring is
that a registry may block a *book assembly* without any review aid
blocking a *draft*.

## Across many drafts: what accumulates

The request that autoresearch answers best is not the one about a single
draft. Its real inversion is that **the human edits `program.md`, not the
Python** -- the thing iterated over a lifetime is the research org, not
any one experiment. Here the draft is `train.py`; `program.md` is the
skills plus the standing preferences, and today almost nothing flows back
into them.

Five things a user writing many documents already generates and nobody
reads across drafts:

- **Which retrieval queries paid.** The dossier's `retrieval.md` logs
  every call; `evidence.md` and `rejected.md` say which candidates were
  kept and turned down. Across drafts that is a record of which query
  shapes yield kept evidence, which is exactly the evidence #63's parked
  evaluation harness wants and currently has to synthesise.
- **Which item classes the human accepts.** Every pass produces
  accepted and reverted items by class -- a labelled record of the
  loop's own reliability. **This is the highest-value item here**,
  because #130 says the gating threshold must be tuned against real
  reports rather than guessed, and this is those reports.
- **Recurring refusals becoming a standing preference.** A user who
  declines the same kind of source in four drafts has a policy, not four
  coincidences. #104 already establishes the precedent that a preference
  belongs on disk rather than being restated every session.
- **The allowlist and the glossary crossing drafts.** A phrase waved
  through #128's allowlist once should not be re-flagged in the next
  draft, and an author writing a thesis, a survey and a textbook chapter
  should not define "digital twin" three different ways -- the dossier
  glossary exists per draft and nothing reconciles them.
- **Where the money went.** `dossier status` already totals retrieval
  cost per revision; across drafts that is the measurement
  [TOKENS.md](TOKENS.md) currently has to estimate.

**The asymmetry has to survive the altitude change.** Karpathy's human
edits `program.md`; the agent never does. The same rule holds here, and
more strongly: a loop that rewrote its own skills, standards or standing
preferences from its own accepted-edit statistics would be a machine
revising the terms of its own supervision. It proposes; the human
accepts. That is the same sentence as everywhere else in this document,
one level up.

## The amendment this needs

One documented rule this cannot satisfy. It is about *who may invoke* a
review aid, and the loop's driver invokes them. This sweep surfaces the
candidates:

```bash
grep -rniE "never automatic|never invoked|invokes them automatically|reads it back|runs automatically" \
  --include='*.md' --include='*.mmd' --include='*.py' .
```

It is a starting point rather than the answer. It hits phrases with
nothing to do with the review layer -- `AGENTS.md`'s "reads it back out
of the ledger", `docs/CLI.md`'s "nothing reads it back" about drafting
state, a `tests/test_sync.py` docstring's "never invoked" -- and it hits
this document. **Twelve** of its matches are real statements of the
rule:

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

**Two diagrams are borderline, and the honest answer is that they are in
scope.** No `.mmd` source states the rule outright -- the one label that
says "never automatic" is inline in ARCHITECTURE.md, so it is a text
edit like the rest. But `00-main-workflow.mmd`'s "REVIEW AIDS -- you run
these" and `g1-corpus-led.mmd`'s "afterwards, **by you**" are
manual-invocation claims on exactly the axis the amendment abolishes.
They are the cheapest possible fix ("run these afterwards"), and each
costs a re-render of its committed SVG under `docs/diagrams/svg/`. The
"never a gate" text in both stays true and untouched.

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
5. **#129, widened** -- the `agenda-reviser` skill, over all defect
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

### Tokens are not free, so the loop is a ladder

autoresearch can afford to be indifferent to the cost of a wrong idea:
five GPU-minutes, on hardware the user already owns, at a price fixed
before the run starts. A wrong idea here is billed per token, and the
bill scales with the draft. That makes cost a design constraint rather
than an afterthought, and [LADDERS.md](LADDERS.md) already names the
shape of the answer: **do the free thing first, and pay only for what it
could not decide.**

Three rungs, cheapest first:

1. **Detection and rejection, at zero tokens.** Every aid, `style_check`
   and the gate are stdlib, deterministic and modelless. This is the rung
   that matters most, and the reason is easy to miss: a deterministic
   check does not only *find* the problem for free, it **refuses a bad
   rewrite for free**. Without it, deciding whether an edit worked means
   paying a model to judge -- and paying a model to grade its own
   homework, which is worth even less than it costs.
2. **A single-shot edit** for an item whose fix is local and whose
   re-check is binary -- a dialect slip, a defect marker, an acronym.
   No subagent, no retrieval, no dossier read: the finding already names
   the section and the span.
3. **A dispatched reviser** only for items needing the surrounding
   argument in context. This is the expensive rung and it should be the
   short list.

Two consequences worth stating. **Rung 1 must run to exhaustion before
rung 2 starts**, or the loop pays a model to find what a `grep` would
have. And the classes that autoresearch best -- the language ones -- are
exactly the classes that sit on rungs 1 and 2, so the axis with the
strongest safety argument is also the cheapest. That is a happy
coincidence rather than a design achievement, but it is the reason to
build the language half first.

#75, parked, is the fourth rung this would eventually want: route the
mechanical stages to a cheaper model tier. It is explicitly blocked on
measurement (#76), and this loop would generate exactly that.

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
  `survey.agenda.md`. What remains against it is real: the other three
  keys name an observed property of the draft, while this one names
  what to do next. It is also the first aid that reads other aids, and
  whether that belongs in the same dict is its own question. The
  alternatives are weighed in the section below.
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

## Naming, and the register the review layer may not use

Recorded because settling it turned up a constraint that outlives this
proposal.

The obvious names for a report of everything still wrong with a draft
come from the audit register: `audit` itself, `reckoning`, `arrears`.
`audit` is the strongest candidate in the language for this repository
-- it is the project's own defining verb ([SOUL.md](../SOUL.md): "keeps
a ledger of every citekey and *audits* citations against it"), it is
dialect-neutral, and it is unused as an identifier anywhere in the tree.

**It is still wrong, and [NAME.md](NAME.md) is why.** That document maps
the myth onto the code, and it spends its third and fourth points
mapping exactly this register onto the **citation gate**: "a draft's
claims are checked against the ledger at the moment of reckoning, and a
`FAIL` is final -- a gate, not a suggestion", then "The audit is
incorruptible, not well-intentioned." Naming a never-blocking aid
`audit` would file the review layer's softest output under the word this
project reserves for its hardest check.

So there is a rule here, and it binds any future aid as much as this one:

> **The judgement register belongs to the gate.** Audit, reckoning,
> verdict, ruling -- an advisory aid may not borrow them, however well
> they fit the myth. NAME.md's fifth point gives the review layer its
> own slot instead: "Evidence, quoted" -- the deeds are *read out*, and
> the reading is not the ruling.

That disposes of a whole family at once, and what survives has to come
from the deliberation register rather than the judgement one. Against
`agenda`, the rest were weighed and each is worse: `worklist` and
`backlog` presume the items are accepted work, when three of six classes
are undecided; `remediation` names only the half the aid does not do;
`findings` is what all three existing aids already emit; `digest`
suggests condensing rather than prioritising; `snags` is exact but
colloquial, and opaque outside British usage; `docket` reads as a
delivery note in that same British usage; and `triage` is spoken for --
[REJECTION.md](REJECTION.md) records a retrieval stage of that name
built and withdrawn, and reusing it here would collide with a
documented refusal.

`agenda` wins on register: the ordered list of matters put before a
decision-maker, none of them decided by the person who drew it up. That
is the review layer's charter in one word.

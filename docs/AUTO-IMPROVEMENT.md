# The auto-improvement loop: what would be built

Status: **specification of unbuilt work.** Written 2026-08-11.

Nothing here exists. `python -m src.review agenda` is not a command, no
review aid emits JSON, and no skill consumes either. This document states
*what* would be built and *what it must satisfy*, in the order it would
be built.

**It contains no argument.** Every "why" -- why the aid sits in the review
layer rather than the drafting one, why three of six item classes may not
be acted on, why the loop stops instead of running overnight, and the one
documented rule it cannot satisfy without the user's approval -- is in
[AUTO-IMPROVEMENT-RATIONALE.md](AUTO-IMPROVEMENT-RATIONALE.md). Read that
first if you are deciding whether to build this; read this one if you are
building it.

**Written for** someone implementing it. It assumes
[ARCHITECTURE.md](ARCHITECTURE.md) for the four layers and
[DRAFT-ITERATION.md](DRAFT-ITERATION.md) for the dossier and the drift
sweep.

**Not covered here:** the prose and house-style half, which has its own
detectors, its own persistence and its own roadmap --
[HOUSE-STYLE.md](HOUSE-STYLE.md). Corpus growth is out of scope entirely:
nothing specified below fetches a paper, writes `bibliography.bib`, or
writes the ledger.

## Table of contents

- [The shape](#the-shape)
- [1. `--json` on all three review aids](#1---json-on-all-three-review-aids)
- [2. The `agenda` aid](#2-the-agenda-aid)
- [3. The `agenda-reviser` skill](#3-the-agenda-reviser-skill)
- [4. Acceptance and rollback](#4-acceptance-and-rollback)
- [The requirements](#the-requirements)
- [How the loop is reached](#how-the-loop-is-reached)
- [The cost ladder](#the-cost-ladder)
- [What accumulates across drafts](#what-accumulates-across-drafts)
- [Build order](#build-order)
- [What this does not change](#what-this-does-not-change)

## The shape

Three sentences.

- The **deterministic half** is a fourth review aid: it reads the other
  three aids' findings plus the dossier's drift report and emits one
  ranked, deduplicated worklist.
- The **generative half** is a skill: it consumes that worklist, repairs
  what may be repaired unattended, re-verifies each repair, and hands the
  rest to the human.
- The **human closes the loop**: they accept the diff, and no code path
  runs the skill automatically.

## 1. `--json` on all three review aids

`src/review/__init__.py` owns one output contract for the layer. Extend
it with a JSON sibling beside the Markdown, at
`content/review/<topic>/<stem>.<aid>.json`.

- The JSON is an additional serialisation of the same findings list, never
  a second computation. The printed Markdown stays the default and stays
  authoritative.
- No timestamp, per the layer's existing rule: two runs over an unchanged
  draft and corpus produce byte-identical JSON.
- This is #127's change applied to the layer rather than to
  `verbatim_check` alone, so the report contract does not fork.

## 2. The `agenda` aid

`python -m src.review agenda <draft>` -- a fourth key in `review.AIDS`.
Deterministic, stdlib-only, no LLM, tier 1, takes no lock, exits 0 whatever
it finds.

**Reads:**

- the three aids' `.json` for this draft -- each optional, and skipped
  with a note when absent;
- `src.dossier.status(draft)`, for missing citekeys and candidates;
- `rejected.md` -- a candidate already turned down with a reason is never
  re-proposed;
- `sections.md`, so every item carries a section anchor.

**Writes:** `<stem>.agenda.md` and `<stem>.agenda.json` under
`content/review/<topic>/`, via the layer's existing `write()`.

**Merges.** One finding may appear in two aids' output; the agenda emits
one item. This cross-signal merge is the work no individual aid can do.

**Every finding carries a stable identity** -- `(aid, class, section
anchor, citekey, hash of the matched span)` or equivalent -- so that "this
finding is gone" and cross-aid dedup are both decidable across runs.

**Order:** class order as the table below lists it, then #128's severity
bucket within a class, then position in the draft.

### Item classes

| Class | Source | Kind | Unattended? |
|---|---|---|---|
| `missing-citekey` | drift | defect -- the gate will fail on it | yes |
| `verbatim-run` | verbatim scan | defect above a span threshold | yes, except the long runs #129 reserves for the human |
| `prose` | `style_check` (#107), `steering.md` | no evidence delta | only the mechanically re-checkable subset -- [HOUSE-STYLE.md](HOUSE-STYLE.md) |
| `unsupported-claim` | provenance | judgement | no -- surfaced |
| `uncited-source` | coverage | judgement | no -- surfaced |
| `candidate` | drift | a decision, usually correct to decline | no -- surfaced |

The `prose` class has no producer until #103 and #107 land; until then it
is an empty list.

## 3. The `agenda-reviser` skill

A skill, not a `src/` module. Named for its input, like the two revisers
it joins: `draft-reviser` works from the dossier, `corpus-reviser` from a
whole-corpus re-search, this one from the agenda.

Per item:

1. Dispatch the existing `draft-reviser` discipline -- read `scope.md` and
   `steering.md` first, edit inside the named section with `Edit`, never a
   whole-file `Write`.
2. Re-run `python -m src.draft gate` **and** the aid that raised the
   finding. Accept only if both come back clean.
3. Re-run every other aid. If the total count of objective-class findings
   rose, revert the edit and escalate the item.
4. Log the attempt in `revisions.md` -- outcome included, refusals
   included.

**Termination:** at most two attempts per item; a second failure escalates
the item and the loop moves on. One agenda pass per invocation. The loop
never adds a claim, and on the unattended classes only removes or rewords
existing ones.

## 4. Acceptance and rollback

Two levels.

- **Before the pass:** one `python -m src.draft dossier export <slug>`.
- **Within the pass:** the skill holds each section's pre-edit text and
  re-applies it when an item fails. Reverting one item leaves every
  earlier accepted item intact.

A failed attempt is logged in `revisions.md` and **never** in
`rejected.md`.

The human is presented with a diff plus the `revisions.md` entries. The
loop proposes and repairs; the human accepts.

## The requirements

Nine obligations, each phrased so a reviewer can tell whether it has been
met. [AUTO-IMPROVEMENT-RATIONALE.md](AUTO-IMPROVEMENT-RATIONALE.md#mapping-the-method-onto-this-pipeline)
says where each comes from.

| | Requirement |
|---|---|
| **R1** | The skill's write-set is exactly the draft and `revisions.md`. It may *execute* an aid, the gate and `style_check`; it may not edit them, nor #128's allowlist, `rejected.md`, `scope.md`, or anything under the corpus layer. |
| **R2** | Every finding carries an identity stable across runs. |
| **R3** | An unattended item's check is **binary**. No continuous score is ever the thing being optimised. |
| **R4** | After each accepted edit, every aid re-runs and the total objective-class count must not rise, else the edit reverts. |
| **R5** | Reverting one item leaves every earlier accepted item intact. |
| **R6** | Every attempt is logged with its outcome, refusals included, and no machine outcome is ever written to `rejected.md`. |
| **R7** | Two attempts per item, one pass per invocation, then hand back. |
| **R8** | Where a deletion and a rewrite both pass, the smaller diff wins. |
| **R9** | The agenda taken before the pass is the recorded baseline, and the closing report is stated against it. |
| **R10** | The aid is registered in both `review.AIDS` and `__main__.AIDS`; the skill's `description` names its triggers; and both appear in AGENTS.md's layer bullets, CLI.md, the README tables and `mkdocs.yml`. |

## How the loop is reached

Nothing here is discovered by scanning the filesystem. Each half is
reached by a different mechanism, and a piece that is built but not
registered is dead code.

| Piece | How it is found | Consequence of omitting it |
|---|---|---|
| The `agenda` aid | a fourth key in `review.AIDS` (`src/review/__init__.py`) **and** in `__main__.AIDS` | `src/review/__main__.py` raises `RuntimeError` if the two dicts disagree, so a half-registered aid fails loudly at import rather than writing a report nothing can find |
| The `agenda-reviser` skill | its `SKILL.md` frontmatter `name` and `description` | This is the *only* trigger mechanism. A skill whose description does not match how a user phrases the request is never invoked, however correct its body |
| Both, for an agent working on a draft | [AGENTS.md](../AGENTS.md)'s layer bullets, which enumerate the aids (Layer 4) and the skills (Layer 2) | An agent following AGENTS.md would not know either exists |
| Both, for a human | [CLI.md](CLI.md) for the command and its flags; [GENRE.md](GENRE.md) for which reviser handles what; README's review-aid block | Undiscoverable outside the source |
| The docs themselves | `mkdocs.yml` nav and the README documentation tables | Absent from nav is a `--strict` build failure |

**Two of those are load-bearing rather than administrative.** The
`review.AIDS` / `__main__.AIDS` pair is what makes the aid exist as far as
the code is concerned -- the report suffix and the subcommand come from the
same dict by design, so registering in one place and not the other is
caught at import. And the skill's `description` *is* its invocation
contract: the only way a genre or reviser skill ever runs is a user's
phrasing matching it, which is why the existing seven carry such long,
trigger-heavy descriptions.

**[SOUL.md](../SOUL.md) is deliberately not on that list.** It states the
one invariant and what each layer may not do, and the loop changes neither:
its review bullet -- the layer "never blocks, and must not be made to" --
already covers the loop and survives the amendment intact
([why](AUTO-IMPROVEMENT-RATIONALE.md#the-amendment-this-needs)). A proposal
that has not been built has no business in the file the assistant treats as
its memory. If the loop ships, the sentence worth adding there is about the
propose-and-accept asymmetry, not about the aid.

## The cost ladder

Do the free thing first, and pay only for what it could not decide --
[LADDERS.md](LADDERS.md)'s existing shape.

1. **Detection and rejection, at zero tokens.** Every aid, `style_check`
   and the gate are stdlib, deterministic and modelless. This rung must
   run to exhaustion before rung 2 begins.
2. **A single-shot edit** where the fix is local and the re-check binary:
   a dialect slip, a defect marker, an acronym. No subagent, no
   retrieval, no dossier read -- the finding already names the span.
3. **A dispatched reviser**, only for items needing the surrounding
   argument in context. The expensive rung, and the short list.

#75 is the fourth rung this would eventually want -- route the mechanical
stages to a cheaper model tier. It is blocked on measurement (#76), which
this loop would generate.

## What accumulates across drafts

Instrumentation the loop would produce that outlives any one draft. None
of it is built, and none of it is read today.

- **Which retrieval queries paid.** `retrieval.md` logs every call;
  `evidence.md` and `rejected.md` record what was kept and turned down.
  Across drafts, that is which query shapes yield kept evidence -- the
  evidence #63's parked evaluation harness would otherwise have to
  synthesise.
- **Which item classes the human accepts.** Accepted and reverted items
  per class, across drafts, is a labelled record of the loop's own
  reliability. #130 requires the gating threshold to be tuned against
  real reports rather than guessed; this is those reports.
- **Where the tokens went.** `dossier status` already totals retrieval
  cost per revision. Across drafts, that is the measurement
  [TOKENS.md](TOKENS.md) currently estimates.

The house-style counterpart -- standing preferences, the glossary, the
allowlist -- is in [HOUSE-STYLE.md](HOUSE-STYLE.md).

## Build order

#126 already fixes this order; the change is to its scope, not its
sequence.

1. **Settle the amendment.** Not a coding task --
   [AUTO-IMPROVEMENT-RATIONALE.md](AUTO-IMPROVEMENT-RATIONALE.md#the-amendment-this-needs).
2. **#127, widened** to all three aids. Hard prerequisite for everything
   below.
3. **#128** -- severity buckets and the boilerplate allowlist.
4. **`agenda`, the fourth aid.** New. Useful on its own the day it lands,
   whether or not step 5 follows.
5. **#129, widened** -- the `agenda-reviser` skill, over all defect
   classes rather than verbatim runs alone.
6. **#103 and #107** -- the copy-edit branch and `style_check.py`, giving
   the `prose` class a producer and a consumer.
7. **#130** -- the gating decision, last, tuned against real reports from
   step 5.

Steps 4 and 5 are the only new work; the rest are open issues.

## What this does not change

- **No new gate.** `src.draft gate` remains the only one. #130 remains
  the only place that decision is taken.
- **No corpus growth.** The loop never fetches, never writes the ledger,
  and never proposes a paper that is not already in it.
- **No new layer.** Four layers, one new aid in the fourth, one new skill
  in the second.
- **No new entry point.** `python -m src.review agenda <draft>` is one
  verb under an existing front door, at depth 1.
- **The review layer still never blocks.** `agenda` exits 0 with a full
  worklist, exactly as the other three aids do with findings.

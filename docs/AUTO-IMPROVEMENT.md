# 🗺 The auto-improvement loop: what would be built

Status: **specification of mostly unbuilt work.** Written 2026-08-11. Updated 2026-08-26;
step 1 built in 5.4.0 and 6.16.0, step 3 in 5.5.0, step 4 in #381, and
step 5 built narrow (verbatim runs only) in 5.7.0 -- see
[Build order](#-build-order).

`python -m chitragupta.review agenda <draft>` is a command now (#381), though
no skill consumes it yet -- that is step 5's widening, still open. Of the
review aids, all seven now emit JSON: `verbatim scan` as of 5.4.0 (#127),
`provenance` and `coverage` as of 6.16.0 (#309), `synthesis` and `uncited`
from the day each landed (#341, #311), and `agenda` itself from #381.
This document states *what* would be built and *what it must satisfy*, in
the order it would be built.

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

## 🧭 Table of contents

- [The shape](#-the-shape)
- [1. `--json` on every review aid](#-1---json-on-every-review-aid)
- [2. The `agenda` aid](#-2-the-agenda-aid)
- [3. The `agenda-reviser` skill](#-3-the-agenda-reviser-skill)
- [4. Acceptance and rollback](#-4-acceptance-and-rollback)
- [The requirements](#-the-requirements)
- [Who calls it, and when](#-who-calls-it-and-when)
- [How the loop is reached](#-how-the-loop-is-reached)
- [The cost ladder](#-the-cost-ladder)
- [What accumulates across drafts](#-what-accumulates-across-drafts)
- [Build order](#-build-order)
- [B5 is a separate mechanism, not a widening of this one](#-b5-is-a-separate-mechanism-not-a-widening-of-this-one)
- [What this does not change](#-what-this-does-not-change)

## 🏗 The shape

Three sentences.

- The **deterministic half** is a further review aid: it reads the other
  eight aids' findings plus the dossier's drift report and emits one
  ranked, deduplicated worklist.
- The **generative half** is a skill: it consumes that worklist, repairs
  what may be repaired unattended, re-verifies each repair, and hands the
  rest to the human.
- The **human closes the loop**: they accept the diff, and no code path
  runs the skill automatically.

## ▶ 1. `--json` on every review aid

**Built (5.4.0, 6.16.0).** `chitragupta/review/__init__.py` owns one output
contract for the layer. Extend it with a JSON sibling beside the
Markdown, at `content/review/<topic>/<stem>.<aid>.json`.

- The JSON is an additional serialisation of the same findings list, never
  a second computation. The printed Markdown stays the default and stays
  authoritative.
- No timestamp, per the layer's existing rule: two runs over an unchanged
  draft and corpus produce byte-identical JSON.
- This is #127's change applied to the layer rather than to
  `verbatim_check` alone, so the report contract does not fork.

What 5.4.0 built, per #127's scope: the layer-level plumbing --
`review.envelope()` (the payload's provenance, and the not-a-verdict
notice, as data) and `review.write_json()` -- plus `verbatim scan
--json`, which prints the payload and files it under `--write`.

What 6.16.0 added, per #309's scope: `provenance --json` and
`coverage --json`, reusing that same plumbing. `provenance` files its
`.json` unconditionally, matching the `.md`'s own always-write policy;
`coverage` files its `.json` only under `--write`, matching the `.md`'s.
So the `agenda` below can still find an aid's JSON missing for a given
draft -- not because an aid has yet to reuse the plumbing, but because
that aid was never run against this draft, or `coverage` was run without
`--write` -- which is the case step 2 already accounts for.

## ▶ 2. The `agenda` aid

`python -m chitragupta.review agenda <draft>` -- a fourth key in `review.AIDS`.
Deterministic, stdlib-only, no LLM, tier 1, takes no lock, exits 0 whatever
it finds.

**Reads:**

- the eight aids' `.json` for this draft -- each optional, and skipped
  with a note when absent;
- `chitragupta.dossier.drift(dossier_dir)`, for missing citekeys and candidates;
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

### 🏷 Item classes

| Class | Source | Kind | Unattended? |
| --- | --- | --- | --- |
| `missing-citekey` | drift | defect -- the gate will fail on it | yes |
| `verbatim-run` | verbatim scan | defect above a span threshold | yes, except the long runs #129 reserves for the human. Built: `agenda-reviser` |
| `prose` | `style_check` (#107), `steering.md` | no evidence delta | **yes**, for the whole class -- decided in #421. `style_check` already emits only the decidable rules of [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §9, so every prose item *is* the mechanically re-checkable subset, and the repair is an edit to the draft, which is R1's write-set |
| `unsupported-claim` | provenance | judgement | no -- surfaced |
| `claim-support` | support | judgement | no -- surfaced. Unfiltered by design -- a cutoff would claim a precision this corpus does not support ([REVIEW.md](REVIEW.md)) -- so `_order.severity_rank` ranks worst-score-first inside the class instead, and the item's own summary states the score is not a verdict |
| `uncited-source` | coverage | judgement | no -- surfaced |
| `uncited-claim` | uncited | judgement | no -- surfaced. Binary per finding, so the agenda may rank it; the fix is evidence, not wording, and a reviser rewording one would make it *look* supported without making it supported |
| `misquoted` | quotation | defect -- the span is not in the source it cites | no -- surfaced. Binary and deterministic, so R3 is satisfied and the agenda may rank it; but the defect is in `evidence.md`, and `agenda-reviser` edits drafts. There is no unattended repair for a bad `quote:` |
| `candidate` | drift | a decision, usually correct to decline | no -- surfaced |

`support` (C2) asks the same underlying question as `provenance` --
does the source support this claim? -- but was never wired in as a
second source for `unsupported-claim`: its score is ranked, never
banded, by design ([REVIEW.md](REVIEW.md)), and that class's extractor
(`unsupported_claim_items`) decides membership by a `band`, a field
this aid deliberately does not emit. #427 gave it its own class instead,
`claim-support`, ranked-but-unfiltered rather than thresholded -- a
percentile cutoff would claim the same false precision a band would.
Findings the entailer could not score at all (`note` set, no quotable
passage) are excluded, since there is no score there to rank or act on.

The `prose` class had no producer when this was written. It has both a
producer and a consumer now: #107 shipped the detector in 5.13.0 and
its automatic invocation (#183) landed in 5.19.0, and `chitragupta/style_check.py`
emits `--json` -- so build-order step 6 below is **done**, and this class
is live rather than an empty list.

## ▶ 3. The `agenda-reviser` skill

A skill, not a `chitragupta/` module. Named for its input, like the two revisers
it joins: `draft-reviser` works from the dossier, `corpus-reviser` from a
whole-corpus re-search, this one from the agenda.

Per item:

1. Dispatch the existing `draft-reviser` discipline -- read `scope.md` and
   `steering.md` first, edit inside the named section with `Edit`, never a
   whole-file `Write`.
2. Re-run `python -m chitragupta.draft gate` **and** the aid that raised the
   finding. Accept only if both come back clean.
3. Re-run every other aid. If the total count of objective-class findings
   rose, revert the edit and escalate the item.
4. Log the attempt in `revisions.md` -- outcome included, refusals
   included.

**Termination:** at most two attempts per item; a second failure escalates
the item and the loop moves on. One agenda pass per invocation. The loop
never adds a claim, and on the unattended classes only removes or rewords
existing ones.

## ▶ 4. Acceptance and rollback

Two levels.

- **Before the pass:** one `python -m chitragupta.draft dossier export <slug>`.
- **Within the pass:** the skill holds each section's pre-edit text and
  re-applies it when an item fails. Reverting one item leaves every
  earlier accepted item intact.

A failed attempt is logged in `revisions.md` and **never** in
`rejected.md`.

The human is presented with a diff plus the `revisions.md` entries. The
loop proposes and repairs; the human accepts.

## 🎯 The requirements

Eleven obligations, each phrased so a reviewer can tell whether it has been
met. [AUTO-IMPROVEMENT-RATIONALE.md](AUTO-IMPROVEMENT-RATIONALE.md#-mapping-the-method-onto-this-pipeline)
says where each comes from.

| | Requirement |
| --- | --- |
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
| **R11** | No hook, no scheduled job and no other skill invokes the `agenda-reviser` skill. Its only trigger is a person asking. |

## 👥 Who calls it, and when

The two halves have different answers, and conflating them is how this
design would go wrong.

**The aid: anyone, at any time.** `python -m chitragupta.review agenda <draft>`
is
free, deterministic, read-only and exits 0. It has exactly the standing of
the other eight aids -- you run it because you want to know. No occasion is
privileged and none is required. That describes the bare command, which
is the one every caller here means; its `--baseline` mode re-runs the
eight aids before comparing (`chitragupta/review/agenda/_recheck.py`), so
that mode alone is neither free nor read-only.

**The skill: only a person, and only on a draft they consider finished.**
Its `SKILL.md` description is the whole trigger, so in practice it runs
when a user says something like "clean up this draft" or "what is left to
fix here". Three occasions to name in that description:

- before rendering or submitting;
- after a `sync` moved the corpus, when `dossier status --all` has named
  this draft;
- on picking a draft back up after weeks away.

**Nothing else may call it** (R11): not a PostToolUse hook, not a
scheduled job, not a genre skill at the end of its own run, and not
`draft-reviser` on its own initiative.
[Why each](AUTO-IMPROVEMENT-RATIONALE.md#-why-only-a-person-may-start-it).

**A stale input is reported, not merged.** Reports carry no timestamp --
deliberately, so they diff cleanly -- so the check is file mtime. An aid
report older than the draft is named as stale in the agenda's header and
its findings marked, rather than presented as current; the header says to
re-run that aid.

## 🪝 How the loop is reached

Nothing here is discovered by scanning the filesystem. Each half is
reached by a different mechanism, and a piece that is built but not
registered is dead code.

| Piece | How it is found | Consequence of omitting it |
| --- | --- | --- |
| The `agenda` aid | a fourth key in `review.AIDS` (`chitragupta/review/__init__.py`) **and** in `__main__.AIDS` | `chitragupta/review/__main__.py` raises `RuntimeError` if the two dicts disagree, so a half-registered aid fails loudly at import rather than writing a report nothing can find |
| The `agenda-reviser` skill | its `SKILL.md` frontmatter `name` and `description` | This is the *only* trigger mechanism. A skill whose description does not match how a user phrases the request is never invoked, however correct its body |
| Both, for an agent working on a draft | [AGENTS.md](../AGENTS.md)'s layer bullets, which enumerate the aids (Layer 4) and the skills (Layer 2) | An agent following AGENTS.md would not know either exists |
| Both, for a human | [CLI.md](CLI.md) for the command and its flags; [GENRE.md](GENRE.md) for which reviser handles what; README's review-aid block | Undiscoverable outside the source |
| The docs themselves | `mkdocs.yml` nav and the README documentation tables | Invisible in the site nav. Not a build failure: `nav.omitted_files` is INFO-level, and `mkdocs build --strict` still passes |

The first two rows are load-bearing rather than administrative, and
[SOUL.md](../SOUL.md) is deliberately absent from the list --
[why](AUTO-IMPROVEMENT-RATIONALE.md#-why-only-a-person-may-start-it).

## ⚡ The cost ladder

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

Model tiering is the fourth rung. #75 settled the policy and #76 the
measurement behind it, both closed; what is left is applying that policy
to whatever mechanical stages this loop adds, which is a question for the
build rather than a blocker on it.

## 🗄 What accumulates across drafts

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

## 🗺 Build order

Issue #126 already fixes this order; the change is to its scope, not its
sequence.

1. **Settle the amendment.** Not a coding task --
   [AUTO-IMPROVEMENT-RATIONALE.md](AUTO-IMPROVEMENT-RATIONALE.md#-the-amendment-this-needs).
   *Approved by the user on 2026-08-21 and applied in 6.20.1 by #312,
   which needed it to make the verbatim scan a required step in the genre
   skills. The surviving invariant is advisory-versus-blocking: a review
   finding may be read, may be invoked by a driver, and may never block a
   draft.*
2. **#127, widened** to every aid. Hard prerequisite for everything
   below. *Done: `verbatim scan` in 5.4.0, then `provenance` and
   `coverage` in 6.16.0 (#309), and `synthesis`/`uncited` from the day
   each landed (#341, #311) -- all six aids now emit JSON on the same
   layer-level plumbing.*
3. **#128** -- severity buckets and the boilerplate allowlist. *Done in
   5.5.0 -- the allowlist shipped as per-host, gitignored data (like
   `config.toml`), not version-controlled as first framed in
   [HOUSE-STYLE.md](HOUSE-STYLE.md); the constraints above (read-only to
   the loop, etc.) hold either way.*
4. **`agenda`, one aid further.** *Done in #381 -- useful on its own,
   independently of whether step 5 follows.*
5. **#129, widened** -- the `agenda-reviser` skill, over all defect
   classes rather than verbatim runs alone. *Built narrow first, in
   5.7.0: `overlap-reviser` (renamed `agenda-reviser` in #435) is #129
   as filed, over the `verbatim-run` class alone, consuming `verbatim
   scan --json` directly rather than an agenda. It did not wait for
   steps 2 and 4 because it did not need to
   -- one aid's JSON already existed, and a loop that repairs one class
   is the report step 7 has to be tuned against. Widening it is now a
   matter of giving it the agenda as an input and the other classes as
   work; the write-set, the two-attempt limit, the binary re-check and
   the person-only trigger are already what R1-R11 ask for.*

   Two pieces of that step landed with it, both in the review layer
   rather than the skill: the scan payload's `id` (R2's stable identity,
   for the `verbatim-run` class) and `verbatim recheck`, which is R3's
   binary check and R4's did-anything-else-break count made
   deterministic. `agenda` should reuse both rather than restate them.
6. **#103 and #107** -- the copy-edit branch and `style_check.py`, giving
   the `prose` class a producer and a consumer.
7. **#130** -- the gating decision, last, tuned against real reports from
   step 5.

Step 5's widening is the only work left live. Steps 1, 2, 3, 4 and 6
are shipped, and step 7 (#130) is a closed, declined decision rather
than an open issue -- see [REQUIREMENTS.md §5.1](REQUIREMENTS.md#-51-current-position).

## 🚧 B5 is a separate mechanism, not a widening of this one

The five genre skills' own pre-gate self-feedback step (roadmap item
[B5](FEATURE-ROADMAP.md#-b5-pre-gate-self-feedback-loop), designed in
`plans/b5-pregate-self-feedback.md`) is easy to misfile as part of this
track, since both critique a draft
against a deterministic count before accepting an edit. They are not
the same mechanism, and R11 ("no other skill invokes the
`agenda-reviser` skill... only trigger is a person asking") does not
cover B5:

- B5's step runs **inside** a genre skill, at generation time, on the
  draft that skill itself is producing. It is not `agenda-reviser` --
  R11 governs when a person may start a *reviser* skill, not what a
  genre skill's own step does to its own output before the gate.
- It does not widen step 5 above and is not a build-order step in this
  track; it is a sibling mechanism the roadmap tracks separately, under
  B5.
- It calls `verbatim scan`/`recheck`, `draft style` and `dossier status`
  directly, the same commands `agenda-reviser` and every genre skill's
  own later steps already call. It never calls `review agenda`, so there
  is no overlap with this track's own machinery to exempt it from.
- Its termination condition is the **declared query list**, not a round
  count (#481): `outline.md`'s list is finite, so "every declared query
  ran and none came back empty" is decidable. That is a report the step
  prints, never a bound on how much it may edit and never a condition of
  presenting -- the three-repair cap is what bounds the editing, and R3
  is why exhaustion is reported as a binary rather than a proportion.

## 🚫 What this does not change

- **No new gate.** `chitragupta.draft gate` remains the only one. #130 remains
  the only place that decision is taken.
- **No corpus growth.** The loop never fetches, never writes the ledger,
  and never proposes a paper that is not already in it.
- **No new layer.** Four layers, one new aid in the fourth, one new skill
  in the second.
- **No new entry point.** `python -m chitragupta.review agenda <draft>` is one
  verb under an existing front door, at depth 1.
- **The review layer still never blocks.** `agenda` exits 0 with a full
  worklist, exactly as the other eight aids do with findings.

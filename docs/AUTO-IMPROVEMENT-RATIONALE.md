# Why an auto-improvement loop, and where its line falls

Status: **reasoning document.** Written 2026-08-11.

Why this repository should be able to repair a draft on its own, what it
must never repair, and the one documented rule that stands in the way.

**Written for** someone deciding whether to accept the proposal -- and, in
particular, whether to grant the amendment in
[The amendment this needs](#the-amendment-this-needs), which is the only
part of it the user has to settle personally.

**Not covered here:** what would actually be built. That is
[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md), which is normative and carries
no argument; where a claim here and a requirement there touch, that file
states the obligation and this one says why it exists. The prose and
house-style axis has its own document,
[HOUSE-STYLE.md](HOUSE-STYLE.md).

Assumes [ARCHITECTURE.md](ARCHITECTURE.md) for the four layers,
[DRAFT-ITERATION.md](DRAFT-ITERATION.md) for the dossier and the drift
sweep, and [PLAGIARISM.md](PLAGIARISM.md) for the detection tiers.

## Table of contents

- [The gap: detection is built, remediation is not](#the-gap-detection-is-built-remediation-is-not)
- [Four signals, four dead ends](#four-signals-four-dead-ends)
- [Where the loop sits, and the cycle that decides it](#where-the-loop-sits-and-the-cycle-that-decides-it)
- [The method, in autoresearch's own terms](#the-method-in-autoresearchs-own-terms)
- [Mapping the method onto this pipeline](#mapping-the-method-onto-this-pipeline)
- [Why provenance is excluded](#why-provenance-is-excluded)
- [Why only a person may start it](#why-only-a-person-may-start-it)
- [The amendment this needs](#the-amendment-this-needs)
- [The software half](#the-software-half)
- [What it would cost](#what-it-would-cost)
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

The claim is narrow: **the pipeline should assemble the worklist, attempt
the mechanical repairs, and re-verify them -- and the human should still
decide.**

Issue #129 already scopes exactly this loop for one signal (verbatim
runs). The proposal is that shape generalised to the other three, plus the
class of improvement none of them cover.

## Four signals, four dead ends

Four commands carry every quality signal this repository has, and each one
is a dead end. The fifth row is not a signal at all -- its absence is the
point.

| Signal | What it finds | What it emits | Who acts on it |
|---|---|---|---|
| `python -m src.draft dossier status --all` | a cited citekey that has left the ledger; a newly reachable paper the dossier never weighed | text, or `--json` | human, by hand |
| `python -m src.review provenance` | a citation whose source does not visibly support it | Markdown report | human, by hand |
| `python -m src.review verbatim scan` | wording shared with a parsed source | Markdown report, or `--json` | human, by hand |
| `python -m src.review coverage` | a source retrieval surfaced that the draft never cited | Markdown report | human, by hand |
| *nothing* | a sentence that is simply badly written | -- | human, by hand |

Two things stand out. **Most of the surface is still text only.** When
this was written, `--json` on `dossier status --all` was the single
machine-readable output in the whole quality surface; 5.4.0 added the
second, on `verbatim scan` (#127), and `provenance` and `coverage` follow
in their own issues. Until they do, three of the five signals above can
only be consumed by parsing prose. And **prose quality has no signal at
all**: `draft-reviser` is section-and-evidence-shaped, and #103 records
that a copy-edit touching no evidence has no sanctioned path through it.

## Where the loop sits, and the cycle that decides it

The obvious placement is a new drafting-layer verb -- `python -m src.draft
agenda <draft>` -- reading the review reports and emitting a worklist.
**That placement is wrong, and the reason is the one cycle this repository
already removed.**

[ARCHITECTURE.md](ARCHITECTURE.md#the-four-layers) states the dependency
graph as acyclic and artefact-mediated, with exactly one edge into the
review layer:

```
corpus ──ledger, parsed/──▶ drafting ──draft──▶ review
```

Review has no outgoing edge, and that is load-bearing: until 4.0.0 the
enrichment layer hosted `provenance` and `render` stages that imported the
review and drafting layers, and removing them is recorded in both
[AGENTS.md](../AGENTS.md) and ARCHITECTURE.md as closing "the one cycle in
this picture". A drafting-layer command reading `content/review/*.json`
re-opens it in the other direction.

**The edge that matters is the artefact edge, not the import.** Review
already imports drafting-layer code -- `citation_provenance` imports
`citation_gate` and `ledger`, `citation_coverage` imports `retrieval`, and
`review/__init__.py` imports `render_output` -- and that is fine, because
those are tier-1 modules being *called*, downhill, by the layer that reads
their output. The acyclicity ARCHITECTURE.md claims is of the artefact
graph: who writes a file that whom reads. `content/review/*.json` is a
layer-4 artefact, and a layer-2 command consuming it is a new edge in that
graph, which nothing else in the repository has.

The alternative has no such problem. `review.AIDS` is an explicit, guarded
extension point -- `src/review/__main__.py` raises a `RuntimeError` (not
an assert, deliberately) if its subcommands drift from that dict, which
exists so a fourth aid can be added safely. An agenda is "evidence for a
human judgement, never a verdict", which is the review layer's charter
word for word, and as an aid it inherits `report_dir`, `report_path`,
`write` and the exits-0-always posture for free. Reading the other three
aids' output is an edge *within* layer 4.

So the aid belongs in layer 4. The clause that matters is the last one in
the specification's shape -- that the human, not code, closes the loop --
because that is what keeps the graph acyclic: a skill reading a review
report is the same act as a human reading one, which the layer already
expects.

## The method, in autoresearch's own terms

[karpathy/autoresearch](https://github.com/karpathy/autoresearch) (MIT,
per its README) is the nearest published thing to what this proposes, and
it is worth stating properly rather than gesturing at, because the parts
that make it work are not the parts it is famous for.

**Three files, and the split between them is the design.** `prepare.py`
holds the constants, the data preparation and -- decisively -- the
evaluation function; it is read-only. `train.py` holds the model, the
optimiser and the training loop; it is the *only* file the agent edits,
and within it everything is fair game. `program.md` holds the agent's
instructions, and it is the only file the *human* edits. The README is
explicit that this inversion is the point: "you're not touching any of the
Python files like you normally would as a researcher. Instead, you are
programming the `program.md` Markdown files that provide context to the AI
agents and set up your autonomous research org." `program.md` is, in its
own words, "essentially a super lightweight skill".

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

**Two rules that are easy to miss.** The first is a tie-breaker: *all else
being equal, simpler is better* -- an improvement bought with twenty lines
of hacky code is probably not worth it, while an equal result from
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
| `program.md` -- edited by the human, not the agent | `.claude/skills/`, `scope.md`, `steering.md`, `docs/WRITING-STANDARDS.md` | [HOUSE-STYLE.md](HOUSE-STYLE.md) is where this half is worked out |
| `val_bpb` -- one global scalar | the count of objective-class findings over all aids | Coarser, and the reason for the binary rule |
| the fixed five-minute budget | *nothing, deliberately* | Its runs compete; agenda items do not |
| `results.tsv`, one row per attempt | `revisions.md`, including refused attempts | Same keep/discard/crash discipline, existing file |
| branch advance-or-`git reset` | `dossier export` + per-item revert | Drafts are gitignored; the granularity is what transfers |
| "NEVER STOP" | two attempts per item, one pass, hand back | Inverted, for the reasons below |

| Its design choice | Transfers? | Requirement |
|---|---|---|
| **The evaluation harness is read-only ground truth** | **Yes, and it is the rule this proposal most needed.** A rewrite that keeps failing the re-scan could otherwise be "fixed" by adding its phrase to #128's allowlist, and a loop that can suppress its own findings is gaming a metric rather than improving a draft | R1 |
| **Keep / discard / crash, one row per attempt** | **Yes, as discipline.** The failure rows outnumber the keeps and are where the learning is. Not as a file: `revisions.md` already exists | R6 |
| **Simplicity as the tie-breaker** | **Yes.** Where a deletion and a rewrite both pass, prefer the smaller diff. That is [SOUL.md](../SOUL.md)'s substantive-editor posture already | R8 |
| **Baseline first** | **Yes.** The agenda taken before the pass is that baseline | R9 |
| **One scalar metric that must go down** | **Partly, and the gap is real.** The asymmetry is not boolean-versus-scalar but local-versus-global: `val_bpb` catches a regression *anywhere*, while a per-finding re-check cannot see that fixing one verbatim run introduced another | R4 |
| **A fixed per-iteration budget** | **No, and it is not needed.** Its experiments are competing alternatives on one leaderboard, so they must be comparable. Agenda items are independent repairs that do not compete | -- |
| **A dedicated git branch, advanced or reset per experiment** | **No -- structurally unavailable.** `content/drafts/` and `content/dossiers/` are gitignored, so a user's drafts are not in git. What transfers is the *granularity*: one experiment reverts alone | R5 |
| **"NEVER STOP"** | **No, and the opposite is correct here** | R7 |

**On never stopping.** It is the most quotable thing in `program.md` and
the least transferable. A discarded training run costs five GPU-minutes
and the metric catches it; a wrong scholarly claim is silent and ships.
Unattended looping is only safe under a metric that catches compounding
damage, and this design's is coarse. Three of six item classes need a
human whatever the loop does, so an indefinite loop either starves or
creeps into judgement. And its per-iteration cost is fixed where this
one's token cost is not. The bounded design is argued, not timid.

Where the proposal may genuinely be too cautious is narrower: one pass per
invocation. A bounded-convergence variant -- keep passing while the
objective-class count strictly falls, to a hard maximum -- still terminates
deterministically and is closer to advance-while-improving. It is declined
for legibility, not safety, and could be revisited.

## Why provenance is excluded

It is tempting to say a machine may not judge whether a source supports a
sentence because SOUL.md forbids it. The stronger reason is that **the
loop cannot detect its own failure here.**

A paraphrase that subtly misstates what a paper claims passes the gate,
because the citekey is still real; passes the verbatim scan, because the
wording now differs -- which is precisely what "fixing" an overlap
*means*; and passes provenance, if the source remains topically related.
Every check the loop owns returns clean on its worst output. The exclusion
is therefore a property of the mechanism, not a policy that could be
relaxed by a more permissive rule.

What can improve unattended on that axis is ordering and surfacing --
which sections are least supported, which citations rest on the thinnest
passage -- never the fix.

**One reconciliation.** #138 proposes terminology, claim and
cross-reference registries as "deterministic, **blocking** global checks
... beside the citation gate". This proposal borrows its *detectors* and
declines its blocking posture: nothing here becomes a gate, and #130
remains the only place that decision is taken. If #138 lands as specified,
the squaring is that a registry may block a *book assembly* without any
review aid blocking a *draft*.

## Why only a person may start it

The specification says the aid may be run by anyone at any time, that the
skill's only trigger is a person asking, and that no hook, schedule or
other skill may start it (R11). Each half of that has its own reason.

**Why the aid is unrestricted.** It is free, deterministic, read-only and
exits 0. There is no occasion on which running it is a mistake, so there
is nothing to restrict.

**Why not a PostToolUse hook.** One already exists, running the gate on
every write under `content/drafts/`. The objection is not cost -- the
agenda reads the aids' JSON rather than executing them, so a hooked
agenda would run one command, not four. The objection is that it would
put a review report in the path of a write. The gate belongs in that path
*because it is a gate*; nothing in the review layer does, and a report
that a write waits on is one short step from a report that blocks it.

**Why not a genre skill at the end of its own run.** A draft just written
has no review reports to read, so the agenda would be empty. More
importantly, a skill repairing its own output is marking its own
homework, which is why the existing gate loop discards an unsupported
claim and writes again rather than "fixing" it.

**Why not cron.** `sync` is safely scheduled because it is deterministic
and idempotent. The skill is neither, and a scheduled reviser is the
overnight posture
[rejected above](#mapping-the-method-onto-this-pipeline).

**Why R11 is a convention, not a mechanism.** Skills already hand off to
one another in prose -- `draft-reviser` to `corpus-reviser` and back --
and nothing enforces that mechanically. R11 is enforceable exactly as
every other skill rule in this repository is, which is worth knowing
rather than pretending otherwise. The hook half *is* mechanical: it
requires an entry in `.claude/settings.json`, and not adding one is a
decision someone would have to reverse deliberately.

**Why SOUL.md is not part of the wiring.** It states the one invariant
and what each layer may not do, and the loop changes neither. Its review
bullet -- the layer "never blocks, and must not be made to" -- already
covers the loop and survives the amendment intact. A proposal that has
not been built also has no business in the file the assistant treats as
its memory. If the loop ships, the sentence worth adding there is about
the propose-and-accept asymmetry, not about the aid.

## The amendment this needs

One documented rule this cannot satisfy. It is about *who may invoke* a
review aid, and the loop's driver invokes them. This sweep surfaces the
candidates:

```bash
grep -rniE "never automatic|never invoked|invokes them automatically|reads it back|runs automatically" \
  --include='*.md' --include='*.mmd' --include='*.py' .
```

It is a starting point rather than the answer. It hits two phrases with
nothing to do with the review layer -- `AGENTS.md`'s "reads it back out of
the ledger" and a `tests/test_sync.py` docstring's "never invoked" -- and
it hits these documents. **Twelve** of its matches are real statements of
the rule:

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
| [CLI.md](CLI.md), the first-run walkthrough | "these runs automatically, and none of them can block a draft" |
| [CLI.md](CLI.md), §coverage | "unlike the gate it never runs automatically" |

**Three diagrams are borderline, and the honest answer is that they are
in scope.** No `.mmd` source states the rule outright -- the one label
that says "never automatic" is inline in ARCHITECTURE.md, so it is a text
edit like the rest. But `00-main-workflow.mmd`'s "REVIEW AIDS -- you run
these", `g1-corpus-led.mmd`'s "afterwards, **by you**" and
`extra-sequence.mmd`'s "optional afterwards", which draws *You* invoking
the aids, are manual-invocation claims on exactly the axis the amendment
abolishes. They are the cheapest
possible fix ("run these afterwards"), and each costs a re-render of its
committed SVG under `docs/diagrams/svg/`. The "never a gate" text in both
stays true and untouched.

The surviving invariant is the one that was always doing the work, and it
is narrower than the current wording: **a review finding may be read, may
be invoked by a driver, and may never block a draft.** Advisory versus
blocking, not manual versus automatic. `src.draft gate` remains the only
gate.

**[SOUL.md](../SOUL.md) does not need amending, and that is the point.**
Its review bullet says the layer "never blocks, and must not be made to" --
no claim about who invokes it -- and its "let a machine outrank a human on
a judgment call" prohibition is satisfied by the three surfaced item
classes. The rule that has to change is stated only in the layer's
implementation and in the documents describing it, never in the soul. That
is what makes the amendment approvable rather than a rewrite of the
project's premises.

It is still a change to the review layer's stated posture in the
user-facing rules file, and SOUL.md reserves that kind of call for the
user. **It is the first thing to settle, before any code.** If it is
declined, the agenda aid can still be written and run by hand, and only
the skill's automation is lost.

## The software half

Whether the same idea can improve the software rather than the drafts. It
can, but it is the smaller half, and the honest verdict is that **the gap
is signal, not permission.**

[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) already grants an agent the
whole cycle -- "implementing features, writing tests first, running the
full local check suite, opening PRs, watching CI, merging, and cutting
releases [...] proceed autonomously". CI runs on two platforms with a
coverage floor. The backlog is labelled and dependency-ordered. Nothing is
missing on the authorisation side.

What is missing is an objective signal an unattended agent could act on:

- **`bench/` records results but never compares them.**
  `bench/results/*/` holds real timings from named machines, and nothing
  reads them back to say a change made the parse slower. A
  compare-to-baseline step -- same host, same fixture corpus, a tolerance
  -- would turn performance from something a human notices into something
  a run reports. That is the single highest-value piece, and it is the
  same "measurement before mechanism" principle #63 already states for
  retrieval.
- **A backlog groomer that stops at proposing.** A scheduled agent can
  read the open `enhancement, parked` issues plus CI and coverage state
  and propose the next rung with its dependency edges checked. It should
  not open the PR: every PR here bumps `pyproject.toml`, so two concurrent
  PRs always conflict on the version line, which forces the work serial
  regardless of how much of it an agent could parallelise.

Both are `bench/`, `.github/` and `.claude/` changes. Neither is a
pipeline layer, and neither should acquire one.

## What it would cost

- **Steps 1-2 of the build order are cheap and additive.** JSON
  serialisation of an existing findings list, plus one new stdlib-only aid
  reading files that already exist. No new dependency, no venv
  requirement, tier 1, no lock.
- **The skill is where the tokens go.** One reviser dispatch per agenda
  item plus a re-check per attempt. It is bounded -- two attempts per
  item, one pass per invocation -- but a long agenda on a long draft is a
  real run. [TOKENS.md](TOKENS.md) has the arithmetic this would extend;
  the saving to weigh it against is that today the same work happens as a
  human-driven sequence of full `draft-reviser` invocations, each paying
  its own start-up read of the dossier.
- **Tokens are not free, which is why the loop is a ladder.**
  autoresearch can be indifferent to the cost of a wrong idea: five
  GPU-minutes, on hardware already owned, at a price fixed before the run
  starts. A wrong idea here is billed per token and scales with the draft.
  The rungs are in
  [AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md#the-cost-ladder); the reason
  the first one matters most is easy to miss -- a deterministic check does
  not only *find* a problem for free, it **refuses a bad rewrite for
  free**. Without it, deciding whether an edit worked means paying a model
  to grade its own homework, which is worth less than it costs.
- **The risk is alarm fatigue, not correctness.** An agenda that is mostly
  boilerplate verbatim hits gets ignored, which is why #128 precedes the
  aid rather than following it.

## Open questions

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
- **Does `agenda` strain the aid vocabulary?** A `review.AIDS` key is both
  the subcommand and the report's filename suffix -- the values are the
  human-readable titles -- so this ships as `survey.agenda.md`. What remains against it is real: the other three
  keys name an observed property of the draft, while this one names what
  to do next. It is also the first aid that reads other aids.

## Naming, and the register the review layer may not use

Recorded because settling it turned up a constraint that outlives this
proposal.

The obvious names for a report of everything still wrong with a draft come
from the audit register: `audit` itself, `reckoning`, `arrears`. `audit` is
the strongest candidate in the language for this repository -- it is the
project's own defining verb ([SOUL.md](../SOUL.md): "keeps a ledger of
every citekey and *audits* citations against it"), it is dialect-neutral,
and it is unused as an identifier anywhere in the tree.

**It is still wrong, and [NAME.md](NAME.md) is why.** That document maps
the myth onto the code, and it spends its third and fourth points mapping
exactly this register onto the **citation gate**: "a draft's claims are
checked against the ledger at the moment of reckoning, and a `FAIL` is
final -- a gate, not a suggestion", then "The audit is incorruptible, not
well-intentioned." Naming a never-blocking aid `audit` would file the
review layer's softest output under the word this project reserves for its
hardest check.

So there is a rule here, and it binds any future aid as much as this one:

> **The judgement register belongs to the gate.** Audit, reckoning,
> verdict, ruling -- an advisory aid may not borrow them, however well
> they fit the myth. NAME.md's fifth point gives the review layer its own
> slot instead: "Evidence, quoted" -- the deeds are *read out*, and the
> reading is not the ruling.

That disposes of a whole family at once, and what survives has to come
from the deliberation register rather than the judgement one. Against
`agenda`, the rest were weighed and each is worse: `worklist` and
`backlog` presume the items are accepted work, when three of six classes
are undecided; `remediation` names only the half the aid does not do;
`findings` is what all three existing aids already emit; `digest` suggests
condensing rather than prioritising; `snags` is exact but colloquial, and
opaque outside British usage; `docket` reads as a delivery note in that
same British usage; and `triage` is spoken for --
[REJECTION.md](REJECTION.md) records a retrieval stage of that name built
and withdrawn, and reusing it here would collide with a documented
refusal.

`agenda` wins on register: the ordered list of matters put before a
decision-maker, none of them decided by the person who drew it up. That is
the review layer's charter in one word.

The same test applies to the skill. `draft-improver` was rejected because
"improver" presumes the outcome; `auto-reviser` because a name built on
`auto-` would re-enshrine in the vocabulary the manual-versus-automatic
distinction the amendment exists to dissolve. `agenda-reviser` names its
input, which is what `draft-reviser` and `corpus-reviser` already do.

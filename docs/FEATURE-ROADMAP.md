# Feature roadmap: what would be built, and in what order

Status: **plan for unbuilt work.** Written 2026-08-20. Nothing below is
built; no issue numbers are claimed yet.

Drafts out of this pipeline carry too much of their sources' wording.
This document says why that happens -- it is a property of how evidence
reaches the drafter, not a failure of the detectors -- what to build to
stop it, and in what order. It then does the same for TikZ figure
layout, and closes with one nice-to-have.

Two upstreams are drawn on, both Apache-2.0:
[OpenScholar](https://github.com/AkariAsai/OpenScholar) for the
synthesis half, [PaperBanana](https://github.com/dwzhu-pku/PaperBanana)
for the figure half.

> **Nothing is copied from either.** Both are taken as inspiration and
> attributed in [INSPIRATION.md](INSPIRATION.md), under that file's
> existing rule -- *"Attribute the idea, and never copy the text."*

That is a settled decision, not an open option: copying was offered and
declined once the cost of declining had been measured at roughly one PR.
[The borrowing posture](#the-borrowing-posture-inspiration-or-copy) has
the working. Every item below is written to it -- where an upstream
artefact is quoted in this document, it is quoted to say *what to learn
from it*, never as text to paste.

**Written for** someone picking the next PR up. It assumes
[ARCHITECTURE.md](ARCHITECTURE.md) for the four layers,
[DRAFT-ITERATION.md](DRAFT-ITERATION.md) for the dossier, and
[PLAGIARISM.md](PLAGIARISM.md) for the three detection tiers that
already exist.

**Not covered here:** how the existing detectors work
([PLAGIARISM-DESIGN.md](PLAGIARISM-DESIGN.md)), and the book-scale
track ([REQUIREMENTS.md](REQUIREMENTS.md) §5.2), which is independent of
everything below.

## Table of contents

- [The diagnosis](#the-diagnosis-where-a-sources-wording-actually-enters-a-draft)
- [The baseline](#the-baseline-measured-before-proposing-anything)
- [The borrowing posture](#the-borrowing-posture-inspiration-or-copy)
- [The decision that gates part of this](#the-decision-that-gates-part-of-this)
- [What the OpenScholar sample demonstrates](#what-the-openscholar-sample-demonstrates)
- [Four constraints every item respects](#four-constraints-every-item-respects)
- [Theme A: close the leak](#theme-a-close-the-leak)
- [Theme B: make synthesis structural](#theme-b-make-synthesis-structural)
- [Theme C: verify faithful use](#theme-c-verify-faithful-use)
- [Theme D: figure layout](#theme-d-figure-layout)
- [Theme F: the auto-improvement loop](#theme-f-the-auto-improvement-loop)
- [Theme E: nice to have](#theme-e-nice-to-have)
- [Theme G: topic modelling](#theme-g-topic-modelling)
- [Build order](#build-order)
- [What is deliberately not proposed](#what-is-deliberately-not-proposed)

## The diagnosis: where a source's wording actually enters a draft

The detectors are not the problem. The path evidence takes to the
drafter is. Traced through the current code:

1. `chitragupta/retrieval.py::search()` returns a **500-character raw
   snippet** per candidate (`snippet_chars=500`).
2. `chitragupta/retrieval.py::evidence()` returns **two 600-character
   raw windows** of the source (`EVIDENCE_CHARS = 600`,
   `EVIDENCE_WINDOWS = 2`).
3. `survey-writer` step 2 tells the skill to record, per kept citekey, a
   `support:` line holding *"the quote or paraphrase"*. In practice that
   is the retrieved window: [TOKENS.md](TOKENS.md) documents its own
   measurement corpus as one `evidence.md` block per citekey *"whose
   `support:` line is a real 600-character evidence window"*.
4. The drafter then writes prose with those source sentences sitting in
   its context.
5. The only defence is post-hoc and optional. `survey-writer` step 16
   reads: *"**Offer the verbatim scan.** Before presenting, offer this
   -- don't run."*

An LLM asked to write a paragraph while a source's own sentences are in
front of it will track those sentences. [PLAGIARISM.md](PLAGIARISM.md)
already says as much -- *"Literal paraphrase is an LLM's default failure
mode when it drifts too close to a source, not an edge case"* -- and
then leaves the drafting layer arranged so that drifting close is the
default posture.

So the fix is upstream of detection: **the drafter must not be holding
source wording at the moment it writes.** Everything in Theme A follows
from that one sentence.

## The baseline, measured before proposing anything

The diagnosis above is read off the code. This is what the existing
detector actually reports today, run against the four real drafts in
`content/drafts/digital-twins-for-software-engineers/` on the 501-paper
corpus. `verbatim scan` is read-only and takes no lock, so this is safe
to reproduce at any time.

| Draft | Words | Findings | Longest run | From an **uncited** source | Already quoted |
|---|---|---|---|---|---|
| `survey.md` | 2,448 | 9 | 13w | 3 | 2 |
| `tutorial.md` | 1,144 | 6 | 14w | 6 | 0 |
| `book-chapter.md` | 1,453 | 3 | 8w | 3 | 0 |
| `deep-research.md` | 1,258 | **0** | -- | -- | -- |

Three things follow, and the third is the one that matters most.

**1. Every finding is `short` severity.** The longest verbatim run in
any of these drafts is fourteen words. So the deterministic tiers do
*not* currently report the "numerous verbatim copies" this work was
requested to address. Two thirds of the findings (12 of 18) are wording
shared with a source the draft **never cites**, which is the more
serious half and the half `overlap` mode structurally cannot see -- but
they are still short runs.

**2. The tier that would see the reported problem never ran.**
On all four drafts, `tiers_not_run` reports the embedding tier skipped,
because the dossier's `sections.md` records no citekeys. Tier 3 is the
**only** tier that detects genuine restatement -- the same claim in new
sentence structure -- and [PLAGIARISM.md](PLAGIARISM.md) is explicit
that restatement is "invisible to both deterministic tiers by
construction" and is "an LLM's default failure mode".

So the most likely reading is that the reported copying **is
restatement**, and that nothing currently measures it on these drafts.
That does not weaken the case for Theme A -- claim-first drafting is
the remedy for restatement specifically, more than for exact runs -- but
it does change what "done" looks like, and it adds a precondition:
[A1a](#a1a-make-the-verbatim-scan-a-required-step) must
also ensure the dossier is populated enough for tier 3 to run, or the
mandatory scan will keep reporting two tiers of three and looking clean.

**3. `deep-research` scored zero, and it is the one genre that already
records claims.** Its SKILL.md writes "kept claims and their citekeys"
into `evidence.md`; `survey-writer` and `tutorial-writer` are the two
that specify a `support:` line, and they are the two with the most
findings. That is exactly the correlation
[A2](#a2-split-support-into-claim-and-quote) predicts.

**Treat it as suggestive and not as proof.** It is four drafts on one
topic; `deep-research` is also the shortest and cites the fewest
sources; and the dossiers for these drafts no longer hold `evidence.md`
files, so the shape their evidence actually took cannot be verified
after the fact. It is a reason to build A2 and measure, not evidence
that A2 is already validated. A1 should report this same table before
and after, which costs one command.

## What the OpenScholar sample demonstrates

The sample output supplied with this request (Asta, "Open Challenges in
Verification and Validation of Digital Twin Systems") is worth reading
structurally rather than as prose. Four properties do the work, and
none of them is "paraphrase harder":

1. **Body prose is multi-source.** Paragraphs close on three or four
   citations at once -- `(Menon et al., 2023) (Leng et al., 2021)
   (Waters, 2025) (Hua et al., 2022)`. This is the load-bearing one.
   **You cannot transcribe two sources simultaneously**; a paragraph
   required to fuse four is structurally unable to be a copy of any one
   of them. Copying stops being forbidden and starts being unavailable.
2. **Verbatim text is quarantined, not eliminated.** Each section ends
   with an `Evidence` block: per citation, the title and a quoted,
   attributed span in quotation marks. Source wording appears exactly
   where it is legitimate -- inside quotation marks, with a name on it
   -- and nowhere else.
3. **Sections open with a synthesised thesis and a source count** -- an
   italic one-sentence claim followed by `(8 sources)`. That count is a
   visible, checkable commitment to breadth.
4. **Ungrounded sentences are labelled**, `(LLM Memory)` and
   `(Model-Generated)`, rather than silently mixed with cited prose.

Properties 1 and 2 together are the whole anti-verbatim mechanism.
This pipeline currently has neither.

**One correction, so nobody goes looking for code that is not there.**
That output shape comes from Asta, the hosted product, **not** from the
`OpenScholar` repository. The repository emits a single flat blob with
positional `[n]` markers and *actively strips* any reference list the
model produces (`generate_response` splits on `"References:"`; `run()`
splits again on `"\n### References"`), because its own generation prompt
says *"you do not need to add Reference list by yourself"*. So
[A4](#a4-the-evidence-appendix) is **our design, read off the sample
output** -- there is nothing upstream to port for it. What the repository
does supply is a prompt that demonstrably asks for property 1, which is
why [B2](#b2-require-multi-source-paragraphs) can point at prior art for
the behaviour it wants rather than arguing for it from scratch.

## The borrowing posture: inspiration, or copy?

**Decided: inspiration only, nothing copied.** This section is kept
because the decision was a measured one and the measurement is the
useful part -- not to leave the question open.

Copying from both Apache-2.0 upstreams was offered. The question asked
was what it would cost to decline, and keep
[INSPIRATION.md](INSPIRATION.md)'s standing rule intact -- *"Attribute
the idea, and never copy the text."*

**Answer: about one PR's worth of work, concentrated almost entirely in
one item** -- and it was judged worth paying. The reason is that very
little of what this roadmap takes is *text or code* in the first place.
What it mostly takes is architecture, ordering and defect vocabulary,
and an idea is inspiration by definition. Priced item by item:

| Item | What would be copied | Cost of writing it instead |
|---|---|---|
| [A0](#a0-record-the-attribution-done) | -- | **Negative.** No `NOTICE`, no per-file provenance headers; two INSPIRATION.md entries instead, in the pattern that file already uses for its CC-BY-NC precedent |
| [A2](#a2-split-support-into-claim-and-quote) | Two prompt sentences | **~0.** They are generic ("summarize rather than copy"); house style differs anyway |
| [B1](#b1-cap-passages-per-source) | ~12 lines of dict-counting | **~0.** Already being rewritten -- keyed on citekey rather than title, and with the off-by-one fixed. Only the cap-then-truncate *ordering* has value, and that is an idea |
| [B2](#b2-require-multi-source-paragraphs) | `prompts_w_references` | **Small.** Its citation mechanics are positional `[n]` against a flat blob, so a substantial rewrite was required regardless. What is lost is validated wording |
| [B4](#b4-cross-encoder-reranking) | "reranking code" | **~0.** The shipped reranker is one `compute_score` library call. Everything around it is dead code this roadmap already declines |
| [D1](#d1-the-metaphor-rule-and-a-layout-checklist) | Style guide + ~40 enumerated vetoes | **The whole delta.** ~1 PR |
| [D4](#d4-optional-vision-critique) | Loop shape + calibration clause | **~0.** Loop shape is architecture; the clause is two sentences |

### Why D1 carries all of it, and why that is acceptable

The veto lists are the one substantial *text* asset, and rewriting them
means producing our own catalogue of figure defects. Two routes were
considered:

- **(a) Write TikZ-native rules directly.** Recommended. The upstream
  guide is written for raster output and much of it does not survive the
  translation -- emoji iconography, "3D isometric cubes", fill-opacity
  advice expressed in image terms. A LaTeX-native catalogue is a better
  artefact, not merely a legally safer one, and this roadmap already
  argues that its most valuable single rule (veto 6, on non-rectangular
  composition) is valuable *because* it is about LaTeX.
- **(b) Re-run their synthesis method** -- 50 venue figures through
  three vision calls and one synthesis call -- to generate our own
  guide. A method is not text, so this stays within the
  inspiration-only decision, and it is cheap. Declined as the default
  because its output is a generated artefact checked into `docs/`, which
  then needs a provenance line to avoid reading as hand-authored rules. Worth
  revisiting if (a)'s catalogue comes out thin.

### The outcome

**Inspiration only.** The delta is one PR, the licence surface goes to
zero, and [SOUL.md](../SOUL.md)'s objection to manufacturing support is
pointed at this project's own provenance as much as at a draft's --
[INSPIRATION.md](INSPIRATION.md) says so explicitly. Relaxing that rule
to save roughly one PR would be a bad trade for a project whose entire
proposition is that it does not cut this kind of corner.

Concretely, for whoever builds these: **you may read either upstream,
and you may not paste from it.** Where this document quotes a prompt, a
veto list or a cap, the quotation is evidence for a design claim -- this
is what they found worth saying -- and the implementation is written
here from scratch. D1 is the one item where that costs real effort, and
it says so.

## The decision that gates part of this

One item cannot be built until a person decides something, and it is the
item this roadmap otherwise wanted to do first.

[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)'s build order opens with a
step that is *"Not a coding task"*: an amendment to the review layer's
stated posture. Today that layer is documented as **manual** as well as
advisory -- *"run by hand on a finished draft, never invoked
automatically"* -- and
[AUTO-IMPROVEMENT-RATIONALE.md](AUTO-IMPROVEMENT-RATIONALE.md) counts
where that claim is written: **twelve places** across the aid docstrings,
`review/__init__.py`'s banner, [AGENTS.md](../AGENTS.md),
[ARCHITECTURE.md](ARCHITECTURE.md), [LADDERS.md](LADDERS.md) and
[CLI.md](CLI.md), plus **three diagrams** whose committed SVGs would need
re-rendering.

The proposed replacement invariant:

> a review finding may be read, may be invoked by a driver, and may never
> block a draft.

-- advisory versus blocking, rather than manual versus automatic.
[SOUL.md](../SOUL.md) is deliberately *not* amended, because the rule
that changes is stated only in the layer's implementation and in the
documents describing it, never in the soul.

**Why it lands here.** [A1](#a1a-make-the-verbatim-scan-a-required-step)
makes `verbatim scan` run without a person asking. That is exactly the
rule above. So A1's real dependency is a user decision, and its real cost
includes those twelve sites and three re-renders -- not the "no Python"
change this roadmap first estimated. The rationale is explicit that this
call is the user's and comes first: *"It is the first thing to settle,
before any code."*

**If the amendment is declined**, nothing here dies. The scan stays
offered rather than run, [F2](#f2-the-agenda-aid)'s agenda aid is still
written and still useful by hand, and only the automation is lost.

**One counter-precedent, pre-empted.** `style_check` already runs
automatically -- a PostToolUse hook per write, and a step in all nine
skills (#183). It does not transfer: `style_check` is
`python -m chitragupta.draft style`, a **drafting-layer** command, and
the never-automatic rule is stated only about layer 4.

## Four constraints every item respects

Named up front because each one has already killed an obvious design.

**1. No LLM output may reach the corpus plane.** [SOUL.md](../SOUL.md):
the corpus layer "has no LLM and no judgment calls"; the enrichment
layer "reads the ledger and never writes it" and "nothing in it is
generative". So extracted claims live in the **dossier**, and the
per-citekey TL;DR ([E1](#e1-per-citekey-tldr)) gets an explicitly
named home that is neither `corpus` nor `enrich`. Writing either into
the ledger would break "same bibliography in, same citekeys out".

**2. No second gate.** `chitragupta.draft gate` means exactly one thing
-- a fabricated citekey fails -- and
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10 says giving it a second
meaning "would blunt the first". A blocking overlap gate was separately
declined on measured evidence (#130). Everything below is therefore
either a **mandatory step in a skill** or an **advisory review aid**.
The distinction matters: making the existing scan a required step costs
nothing architecturally, because the tool still exits 0 either way.

**3. Anything with a torch/transformers dependency goes behind an
extra.** `pyproject.toml` makes `bibtexparser` the single core
dependency a point of design, with all ML quarantined in `enrich`.
Copied OpenScholar code inherits that rule -- and cannot be copied as
*files* regardless, because its import graph pulls `torch`, `vllm`,
`FlagEmbedding` and `spacy` at module top before any branch, loads a
spaCy model at import that the module never uses, and reads
`os.environ["S2_API_KEY"]` at module scope. Port the functions and the
prompt strings; rewrite the imports. Of everything proposed here, only
[B4](#b4-cross-encoder-reranking) genuinely needs the ML stack.

**4. Attribution is owed for the idea, not for the text.** Nothing is
copied, so Apache-2.0 §4's notice obligations never attach --
[INSPIRATION.md](INSPIRATION.md) carries both upstreams instead, which
is what that file exists for.

**5. `R1`-`R11` bind every new review aid and every unattended edit.**
[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md) states eleven obligations,
*"each phrased so a reviewer can tell whether it has been met"*. Four
reach items in this roadmap and are easy to breach by accident:

- **R2** -- every finding carries an identity stable across runs, so
  "this finding is gone" is decidable. Any aid added by Theme C must
  emit one.
- **R3** -- *"An unattended item's check is **binary**. No continuous
  score is ever the thing being optimised."* This is the one most
  likely to be broken here, and [B5](#b5-pre-gate-self-feedback-loop) broke
  it in the first draft of this document. Every aid below is therefore
  annotated **binary** (an agenda may consume it and a loop may act on
  it) or **continuous** (a human reads it; nothing acts on it
  unattended).
- **R4** -- after an accepted edit, every aid re-runs and the total
  objective-class count must not rise, else the edit reverts.
- **R10** -- a new aid is registered in *both* `review.AIDS` and
  `__main__.AIDS`, and appears in AGENTS.md, CLI.md, the README tables
  and `mkdocs.yml`. `review/__main__.py` raises `RuntimeError` when the
  two dicts disagree, so a half-registered aid fails at import; the
  `mkdocs.yml` omission is the silent one, since missing nav is INFO
  rather than a `--strict` failure.

One naming rule comes with them, and it outlives the proposal that
states it: **the judgement register belongs to the gate.** An advisory
aid may not be called `audit`, `reckoning`, `verdict` or `ruling`
however well the name fits. `triage` is separately blocked --
[REJECTION.md](REJECTION.md) records a retrieval stage of that name
built and withdrawn.

## Theme A: close the leak

The highest-value theme, and the one the request is actually about.
A1 is cheap and immediate; A2-A4 are the structural fix.

### A0: record the attribution (done)

[INSPIRATION.md](INSPIRATION.md) carries both upstreams under its
existing rule, in the same shape it already uses for its CC-BY-NC
precedent: what was taken, and what was deliberately not.

**No `NOTICE` file and no per-file provenance headers**, because nothing
is copied -- Apache-2.0 §4's notice obligations attach to
redistribution, and reading a repository and writing your own
implementation is not that. That is the whole of what the
inspiration-only decision saves here, and it is why this item shrank
from a PR to two entries.

Size: none, shipped with this document. Listed so the sequence still
reads correctly, and so nobody re-adds a `NOTICE` on the assumption one
was forgotten.

### A1a: make the verbatim scan a required step

Flip the step every genre skill already carries -- *"**Offer the
verbatim scan.** Before presenting, offer this -- don't run"* -- so the
scan actually runs before a draft is presented.

**Verified scope:** all **nine** skills carry that step, eight in
near-identical words (`book-assembler` phrases it per unit). One
mechanical edit repeated nine times, not nine judgement calls.

This is **not** a new gate: the scan exits 0 regardless, and nothing
blocks. But it *is* a review aid running without a person asking, which
is the rule [the amendment](#the-decision-that-gates-part-of-this)
governs. So the honest cost is nine SKILL.md edits **plus** the twelve
documentation sites and three diagram re-renders that carry the
never-automatic wording.

Should also populate the dossier's `sections.md` well enough for tier 3
to run -- per [the baseline](#the-baseline-measured-before-proposing-anything),
it currently never does -- and report the before/after table.

Size: S for the skills, M once the documentation sweep is counted.
Depends on: **the amendment.** Not on code.

### A1b: auto-route findings into `overlap-reviser` -- declined

The first draft of this roadmap paired A1a with automatic routing of
findings into the existing `overlap-reviser` skill. **That half is
withdrawn**, on the project's own reasoning rather than on new grounds.

[AUTO-IMPROVEMENT-RATIONALE.md](AUTO-IMPROVEMENT-RATIONALE.md) refuses a
genre skill repairing its own output: *"a skill repairing its own output
is marking its own homework, which is why the existing gate loop
discards an unsupported claim and writes again rather than 'fixing'
it."* The amendment does not touch this argument -- it is about
self-marking, not about who may invoke an aid.

It also falsifies two written claims at once: `overlap-reviser`'s own
description ends *"never runs unless a person asked for it"*, and
[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)'s build-order step 5 asserts
that skill's *"person-only trigger"* is already what R1-R11 ask for.
Auto-invoking it from nine genre skills would make both sentences false,
which is a documentation change nobody proposed and a rule change
smuggled in as a convenience.

**What replaces it:** the scan runs (A1a), the findings are surfaced,
and the person decides whether to invoke the repair loop. That is one
extra deliberate act, and it is the act the whole design is built
around.

### A2: split `support:` into `claim:` and `quote:`

*Planned in detail: [`plans/a2-claim-quote-split.md`](../plans/a2-claim-quote-split.md).*

The core fix. One `evidence.md` block currently carries a `support:`
line that is, in practice, raw source text. Replace it with two fields
whose contract differs:

- **`claim:`** -- what the source establishes, in the drafter's own
  words. This is the only field the drafting step may write prose from.
- **`quote:`** -- an optional verbatim span, explicitly marked as
  quotable-only: usable in the draft *solely* inside quotation marks
  with an attribution, never as raw material for prose.

The drafter is then never in the position that produces copying,
because the field it drafts from was written in its own words at a
point where it was not yet composing sentences.

**This is less invention than it looks, and one genre already does
half of it.** `deep-research` records "kept claims and their citekeys"
into `evidence.md` today; only `survey-writer` and `tutorial-writer`
specify the `relevance:`/`support:` pair, and `textbook-chapter-writer`
keeps `evidence.md` thin or empty by design. So A2 is better described
as **making the existing best practice universal and naming the
`quote:` contract** than as adding two new fields -- and per the
baseline above, the genre that already does it is the one that scored
zero.

`chitragupta/dossier/_citekeys.py::evidence_blocks()` is already
deliberately shape-agnostic -- its docstring says what a genre skill
puts under a heading "varies… and this module does not own that shape"
-- so the code burden is small and the work is mostly skill
instructions plus [DRAFT-ITERATION.md](DRAFT-ITERATION.md).

Worth adding in the same PR: a deterministic self-check that `claim:`
is not merely `quote:` with words moved, reusing
`chitragupta/overlap_skipgram.py`, which already does stemmed
near-match. Advisory, printed at dossier-write time.

Upstream has two sentences worth lifting into the instruction for
`claim:`, both from `src/instructions.py`:

> avoid copying entire passages; instead, summarize the key information
> from the suggested papers
>
> Do not directly insert text from the relevant evidence.

The second is the stronger of the two and sits in a prompt variant
upstream defines but never wires up -- so it is available, unused, and
exactly the instruction this project needs.

Those two sentences are quoted here as evidence that the instruction
is worth giving, and as a target to beat. Write this project's own, in
its own register; do not paste theirs.

Size: M. Depends on: nothing.

### A3: extraction at the retrieval boundary

`survey-writer` step 2a already dispatches one subagent per sub-theme
and already tells it to return "**only** the kept-evidence packet…
never the raw candidates". The packet, however, still contains
`support:` -- so raw windows reach the orchestrator anyway.

With A2's fields defined, tighten the contract: the subagent returns
`claim:` lines it wrote, plus `quote:` spans only where it judges a
quotation genuinely warranted. **Raw retrieval windows then never enter
the orchestrator's context at all.**

This is also a token win, and [TOKENS.md](TOKENS.md) already measures
this exact boundary at 2.45x, so the PR can report a real before/after
number rather than an estimate.

Size: S-M, mostly SKILL.md. Depends on: A2.

### A4: the Evidence appendix

Adopt the sample's property 2: a rendered `Evidence` section listing,
per citekey, the title and the attributed quoted spans drawn from A2's
`quote:` fields. Body prose then holds no verbatim material at all,
because it has somewhere legitimate to live.

This changes what a draft *looks like*, so it is a genre decision per
skill rather than one global switch -- a survey and a tutorial should
not answer it identically, and `thesis-chapter-writer`'s `.tex`
fragment is `\input` into someone else's document and may need to
decline entirely.

Size: M. Depends on: A2. Touches the genre skills and
`chitragupta/references.py`'s neighbourhood.

## Theme B: make synthesis structural

Theme A stops wording leaking. Theme B removes the *opportunity* by
changing what a paragraph is required to be.

### B1: cap passages per source

OpenScholar's `--max_per_paper` (`src/open_scholar.py:615-630`). Add a
per-citekey cap to `retrieval.search()` so a single document cannot
dominate a sub-theme's evidence set. Cheap, deterministic, stdlib-only,
no new dependency -- and it is the precondition that makes B2 achievable
rather than aspirational, because a drafter cannot cite two sources per
paragraph if retrieval handed it six passages from one paper.

**The ordering is the whole trick, and it is the part worth learning.**
Upstream applies the cap to the *full reranked list*, before truncating
to the top *n*. Dropping paper A's 4th-best passage therefore *promotes*
a passage from paper B into the window the drafter sees. Cap-then-truncate
produces source diversity; truncate-then-cap merely produces a shorter
list.

**Two upstream defects to fix rather than inherit**, both found by
reading the source:

- Off-by-one: the counter is 0-based and the test is `>`, so
  `--max_per_paper 3` admits **four** passages. Use `>=`.
- The bucket key is the title string, defaulting to `""`, so every
  untitled passage collapses into one bucket and is capped as though all
  untitled passages were the same paper. Key on the citekey -- which
  this project has and upstream does not.

Size: S. Depends on: nothing. Highest value-per-line in this document.

### B2: require multi-source paragraphs

*Planned in detail: [`plans/b2-multi-source-synthesis.md`](../plans/b2-multi-source-synthesis.md),
which settles the unit the rule binds at -- paragraph for a survey, a
thesis chapter and a deep-research report; the section for a textbook
chapter; the whole document for a tutorial, whose body carries no
citations by design. The guarantee is the same in all five.*

The sample's property 1, made into a rule: a body paragraph cites **two
or more citekeys wherever the evidence set allows**, and a
single-source paragraph is a deliberate choice the drafter states
rather than a default.

Pair it with a deterministic report -- citekeys per paragraph, and the
proportion of single-source paragraphs -- so the rule is observable
instead of merely written down. **Continuous: a human reads this;
nothing acts on it unattended** (R3). A proportion is exactly the shape
R3 exists to keep out of a loop. Note honestly in the
report that a thin corpus legitimately produces single-source
paragraphs; this counts, it does not judge.

**Prior art, quoted as evidence rather than as source.**
`src/instructions.py::prompts_w_references` already instructs exactly
this behaviour, and its key sentence shows the shape the instruction
has to take:

> Rather than simply summarizing multiple papers one by one, try to
> organize your answers based on similarities and differences between
> papers.

together with *"Base your answer on multiple pieces of evidence and
references, rather than relying on a single reference for a short
response."* Adapt the citation mechanics, though: upstream cites by
**positional index into a truncated list**, so reordering the list
silently changes what every citation means. This project has real
citekeys and must keep using them.

Size: M. Depends on: B1 in practice. The prompt is written here, not
lifted; [INSPIRATION.md](INSPIRATION.md) carries the credit.

### B3: section thesis with source count

The sample's property 3: each section opens with a one-sentence
synthesised claim and the number of distinct sources behind it. Cheap,
and the count is deterministically checkable against the section's own
citations, which makes it the rare stylistic feature that can be
verified rather than trusted.

Size: S. Depends on: nothing.

### B4: cross-encoder reranking

OpenScholar's `--ranking_ce` / `--reranker`. `retrieval.py`'s own
docstring already anticipates the swap, and
`chitragupta/enrich/embed_index.py` already has a matching
`search(query, k)` shape. Better-ordered passages mean fewer passages
are needed, which compounds with B1.

Behind the `enrich` extra per constraint 3. Nothing is taken from
upstream here in any case: what ships there is a single
`compute_score` call against a library, and the surrounding machinery is
the dead code this roadmap already declines. The work is choosing a
cross-encoder and wiring it to the existing `search(query, k)` shape.

Size: M-L. Depends on: B1.

### B5: pre-gate self-feedback loop

OpenScholar's `--feedback`: before running the citation gate, the skill
critiques its own draft against the evidence packet and repairs gaps.
Cheaper than the redraft cycle a gate failure currently triggers, and
it composes with A1's scan -- one repair pass, two classes of finding.

**Smaller than "loop" suggests.** Upstream is not iterative: one
feedback call producing a prioritised list, then at most three
single-pass edits, with no re-critique.

**Its safety mechanism cannot be copied, and the first draft of this
roadmap copied it anyway.** Upstream accepts an edit if the result is
more than 90% the length of the original. That is a continuous score,
and **R3** forbids one as an acceptance criterion: *"An unattended
item's check is **binary**. No continuous score is ever the thing being
optimised."* The correct acceptance test here already exists -- **R4**'s
*"the total objective-class count must not rise, else the edit
reverts"*, made deterministic by `verbatim recheck`, which shipped in
5.7.0. Keep the length ratio only as a secondary sanity check against
gutting a draft, never as the thing being satisfied.

This item is also self-marking in the sense
[A1b](#a1b-auto-route-findings-into-overlap-reviser----declined) declines,
and it needs the amendment. It sits late for both reasons rather than
one.

Size: M. Depends on: the amendment, A2, and `verbatim recheck`.

## Theme C: verify faithful use

Detection, after Theme A and B have reduced what there is to detect.
All three are review-layer aids: advisory, exit 0, never gates.

### C1: uncited-prose report

Which sentences carry no citation at all. **Verified as a genuine gap:**
`chitragupta/review/citation_coverage.py` answers a different question
(which *surfaced* candidates got cited), not which prose is
unsupported. This is the machinery behind the sample's property 4
labels, and it is deterministic -- citation extraction already exists in
`citation_gate.extract_citekeys_from_line`.

**Binary** per finding (a sentence either carries a citation or does
not), so an agenda may consume it -- but its findings are of
*judgement* kind, so they are surfaced and never repaired unattended:
the fix for an uncited claim is evidence, not wording. As a new aid it
carries R2 (a stable finding `id`), `--json`, and R10's dual
registration plus the AGENTS.md/CLI.md/README/`mkdocs.yml` sweep.

Size: S for the detector, M with R10's registration sweep. Depends on:
nothing. Best value in this theme.

### C2: claim-support checking

Does the cited source actually support the sentence citing it? Closes
[REQUIREMENTS.md](REQUIREMENTS.md) §1.2, which is on record as unbuilt.

**Do not plan this as a port.** OpenScholar's posthoc citation
attribution looks like the thing to copy and is not: it is a **pure LLM
prompt** -- no entailment model, no embeddings, not even string overlap
-- that asks a model to insert citation numbers, and whose live prompt
variant pressures it toward citing with *"but do your best to insert
citation"*. It also silently returns the original text when its output
markers are missing, so its failure mode is invisible. It can only cite
passages already in the generation window, making it a repair pass
rather than a verification.

A real support check therefore has to be **built**, against an
entailment model, not ported. That is why this is an L and why it is
late: it is the most expensive item here and the one whose value is
least certain in a corpus where retrieval already selected passages by
similarity -- the same weak-discriminator problem
[PLAGIARISM-DESIGN.md](PLAGIARISM-DESIGN.md) records for tier 3.

**Surfaced permanently, and the reason is a mechanism rather than a
policy.** [AUTO-IMPROVEMENT-RATIONALE.md](AUTO-IMPROVEMENT-RATIONALE.md)
already settles this axis, and its argument is stronger than SOUL.md's:
a paraphrase that subtly misstates a paper *"passes the gate, because
the citekey is still real; passes the verbatim scan, because the wording
now differs -- which is precisely what 'fixing' an overlap means; and
passes provenance, if the source remains topically related."* So

> Every check the loop owns returns clean on its worst output.

That is why this can never become an unattended repair, however good the
model gets: *"The exclusion is therefore a property of the mechanism,
not a policy that could be relaxed by a more permissive rule."* What
*is* allowed unattended on this axis is ordering and surfacing -- which
sections are least supported, which citations rest on the thinnest
passage -- never the fix.

Feeds the agenda's `unsupported-claim` class. **Continuous** (an
entailment score), so it is read by a human and consumed by nothing.
Behind the `enrich` extra, and carrying R2 and R10 like any aid.

Size: L. Depends on: C1 for the sentence-splitting it shares.

### C3: quotation and page integrity

Given A2's `quote:` and A4's appendix, verify each quoted span appears
verbatim in the cited source at the cited page. Deterministic, and
`chitragupta/passages.py` already owns the quotable-paragraph/page
ladder. Also §1.2.

**Binary**, and deterministic -- a quoted span either appears at the
cited page or does not -- so unlike C1 and C2 this one is a legitimate
candidate for an unattended class. Carries R2 and R10.

Size: M. Depends on: A2, A4.

## Theme D: figure layout

The second thing the request asks for. PaperBanana generates **raster**
images through image-generation APIs; this pipeline generates **TikZ
source**, compiled to vector art, plus an ASCII twin
([WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10). So its *architecture*
does not transfer, and several of its *artefacts* do -- but not the ones
its README points at.

An image-generation path is rejected outright, for two independent
reasons: it is non-deterministic, against this project's "byte-identical
output over unchanged input" product rule, and a raster figure cannot
satisfy the two-form TikZ/ASCII contract.

**PaperBanana's own published evidence is the third reason, and it is
the strongest.** Its [project page](https://dwzhu-pku.github.io/PaperBanana/)
publishes a side-by-side of the same figures generated as images and as
code, with its own case analysis. Read honestly, it says: the image
route is prettier and the code route is correct.

| Case | Image route | Code route |
|---|---|---|
| Line plot, heatmap | correct; "looks more visually appealing" | correct |
| Radar chart | **inverts the relationship** between two series, plotting one at ~0.9 against ~0.6 | correct |
| Business dashboard | **duplicates a category** | correct |
| Bar chart | **draws a bar visibly taller than its own 0.4 gridline** | correct |

A generator that draws a bar taller than its value is fabricating data.
That is the same class of failure as a fabricated citekey -- a plausible
artefact with nothing real behind it -- and it is the failure this whole
project exists to make impossible. Adopting it for figures while gating
it for citations would be incoherent.

The published failure cases for *diagrams* point the same way and add
something useful. Every one of them is a **semantic wiring error** --
edges drawn from the wrong node, a required connection missing, a skip
connection replacing the one the method describes -- and **none** is a
layout or aesthetic defect. The layouts are good. What breaks is what
the diagram *claims*.

That is worth dwelling on, because it is a capability argument in this
project's favour rather than merely a rejection. A wrong edge is
invisible to any check over pixels, which is all PaperBanana has. In
TikZ an edge is `\draw (a) -- (b);` -- **the edge list is recoverable
from the source**, so it can be checked against what the author said the
figure shows. [D2](#d2-deterministic-tikz-layout-check) should exploit
that; it is the one thing generating source buys that generating images
cannot.

**Read this before opening `style_guides/`.** The obvious artefact to
take is the synthesised style guide, and for *layout* it is the wrong
one. Its generator prompt asks the model for a `Layout & Composition`
section covering "element arrangement patterns, information density,
whitespace usage" -- and the checked-in
`neurips2025_diagram_style_guide.md` **does not contain one**. The
section was silently dropped during synthesis; what shipped is colour,
shapes, lines and typography. The layout material is instead in
`prompts/diagram_eval_prompts.py`, the *evaluation* rubric, which was
never advertised as a style artefact.

### D1: the metaphor rule, and a layout checklist

Two prompt-side changes into the five genre skills' TikZ instructions
and [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10. No code, no
dependencies, and between them they address the cause and give the
author something to check against.

**1. Commit to a layout metaphor before drawing.** PaperBanana's
planner supplement asks for "a compact visual metaphor that can organize
the diagram's layout and relationships, such as a pipeline, map, layered
stack, control loop, branching tree, or hub-and-spoke network."

This is the single instruction most likely to fix the reported problem
at its source. Sprawl -- boxes placed near other boxes, arrows added as
needed -- is what ad-hoc composition produces. Each metaphor in that
list also maps onto a TikZ idiom the author should then actually use:
chains with `positioning`, `matrix`, stacked `fit` layers, cyclic edges
with `bend`, a tree, a star. Choosing one first converts "place these
nine things" into a constrained problem.

**2. Write a pre-flight defect checklist, informed by the rubric's
readability vetoes.** **This is the one item the inspiration-only
decision actually costs**, and the cost is the catalogue: upstream's
vetoes are an enumerated list of concrete defects, and ours has to be
enumerated too, in our own words and for LaTeX rather than for raster
output. Much of theirs would not survive the translation anyway -- emoji
iconography, "3D isometric cubes", fill-opacity expressed in image
terms -- so the rewrite is a better artefact and not merely a safer one.

Their vetoes are quoted below to show what the finished catalogue has to
cover. They are concrete defects rather than taste:
occlusion and overlap; "chaotic routing" (arrows forming spaghetti loops
or crossing unnecessarily); illegible or inconsistently varying font
sizes; low contrast; and -- the one worth quoting -- inefficient
non-rectangular composition:

> Since LaTeX treats figures as rectangular boxes, any element
> protruding above the main block forces text to wrap around the highest
> point, wasting vertical space in publications.

That veto was written **for a LaTeX pipeline**, which is exactly the
situation here and not the situation PaperBanana itself is in. It is
also mechanically checkable, which is what [D2](#d2-deterministic-tikz-layout-check)
does with it.

Cover the *conciseness* vetoes in the same pass. One is a hard number --
a node whose text runs past about fifteen words is flagged -- and one is
"literal copying", a "box-ified copy-paste of the Method Section text
with no visual abstraction". That second one is Theme A's problem
wearing a different hat, and it is worth noticing that a figure can
launder borrowed wording past every detector in
[PLAGIARISM.md](PLAGIARISM.md), because §10 already keeps citekeys out
of figure files and the gate does not follow `\input`.

The colour/shape/typography guide is still worth reading, for what it
teaches rather than for its words: it suggests a vocabulary of TikZ
style keys (zone fills at 10-15% opacity via
the `backgrounds` layer, dashed for auxiliary flow against solid for
forward flow, sans-serif labels against serif-italic maths). The
sans/serif split is free in LaTeX and is a rule PaperBanana's own raster
path cannot enforce at all.

Size: S. Depends on: nothing. **Do this first in the theme** -- it is
prevention, where D2 is detection.

**Shipped in 6.16.1 (#308), as [`TIKZ-STYLE.md`](TIKZ-STYLE.md) linked
from [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10, rather than
inline in §10 itself.** This document's own status line above ("Nothing
below is built") is stale for D1 specifically; D2-D4 and every other
theme remain unbuilt work.

### D2: deterministic TikZ layout check

*Planned in detail: [`plans/d2-tikz-layout-check.md`](../plans/d2-tikz-layout-check.md).*

A new review-layer aid: compile the figure and report overlapping nodes,
protruding content, over-long node text and page-width overflow.

**This was probed on this host before being proposed, and it works.** A
`standalone` + `tikz` document with `\pgfpointanchor` writing node corner
coordinates through `\typeout` yields machine-readable geometry from an
ordinary `pdflatex` run:

```text
CGBOX a -42.87912pt -7.97742pt 42.87912pt 7.97742pt
CGBOX b -8.73592pt -6.94963pt 77.02232pt 6.94963pt
CGBOX c -20.78996pt -63.85512pt 20.78996pt -49.95586pt
```

Nodes `a` and `b` overlap by 51.6pt horizontally and overlap vertically
too -- a real collision, detected deterministically, with no model in the
loop and no dependency beyond the TeX stack the pipeline already
requires. `tikz.sty` and `standalone.cls` are both present on this host.

From those coordinates, three of D1's vetoes become arithmetic:

- **Occlusion** -- pairwise box intersection, as above.
- **Inefficient composition** (veto 6) -- compare the picture's overall
  bounding box against the union of node boxes, and report protrusion
  and disproportionately empty corners as numbers.
- **Text overload** -- word count per node, against the rubric's
  fifteen-word line.

Arrow crossings ("chaotic routing") are the one veto not cheaply
reachable this way and should be left out rather than approximated
badly.

**Binary where it counts, continuous where it does not.** Node overlap
and text-overload are binary and safe for a loop to act on; "corner
emptiness" is a proportion and is **human-read only**, per R3. Report
both, and label which is which -- an unlabelled mixture is how a
continuous score ends up being optimised by something that should not
be optimising anything.

**Add one check that has no PaperBanana counterpart: the edge list.**
Parse `\draw`/`\path` node-to-node connections out of the figure source
and report them back to the author as a plain list -- *a -> b, b -> c* --
for confirmation against the prose the figure illustrates. Every
published PaperBanana diagram failure is of exactly this kind, and every
one would be visible in such a list. It is also the cheapest possible
implementation of the rubric's *faithfulness* dimension, needs no model,
and is only available because this pipeline generates source.

This is PaperBanana's Critic agent's *function* implemented in this
project's own idiom -- determinism where it is possible
([SOUL.md](../SOUL.md)) -- rather than a vision model asked for an
opinion. It composes with `_figures.py`'s existing `_require_tikz()`
probe, and it reports; it does not block.

Size: M-L. Depends on: D1 for the thresholds to check against.

### D3: known-good layout scaffolds

A small library of TikZ patterns, **one per metaphor in D1's list** --
pipeline, layered stack, branching tree, hub-and-spoke, control loop --
with spacing that satisfies D2 by construction. D1 tells an author to
choose a metaphor; this gives them something to choose *from*, so the
choice is a starting file rather than a blank `tikzpicture`.

PaperBanana's retriever ranks reference figures by a rule worth keeping
-- *"Structure is more important than Topic for drawing"* -- but its
reference corpus is not in the repository (it needs a separate
Hugging Face download) and is a set of raster images regardless. Building
this from accepted TikZ sources in this project is strictly better,
because the retrieved artefact is then editable source rather than
pixels.

Size: M. Depends on: D1, D2.

### D4: optional vision critique

Only for what D2 cannot judge: whether the figure communicates its
point, and the arrow-routing veto D2 deliberately skips. Opt-in,
advisory, never in a default path, and explicitly outside the
byte-identical rule -- which is why it is last. Skip it entirely if
D1-D3 prove sufficient.

If it is built, PaperBanana's loop *shape* is sound and worth learning
from -- at most three rounds, a structured `{critique, revised}` payload,
an early exit on an explicit "nothing to change" sentinel, and keeping
the last good render on failure. That is architecture, which is the
kind of thing this roadmap takes. Two further lessons matter more than
they look:

- **The calibration clause.** *"Readability is a baseline requirement,
  not a differentiator… Only severe violations of the Veto Rules
  constitute failures. Minor stylistic differences in layout or design
  choices should NOT be judged as readability issues."* Without
  something like it, an LLM judge nitpicks every figure indefinitely.
  PaperBanana also ships an explicit de-biasing list of judge failure
  modes someone evidently observed in practice; a TikZ equivalent will
  have to be written from our own observations.
- **Its error handling, inverted.** PaperBanana's code-generating path
  is the closest analogue to ours and is a cautionary tale: it catches
  the execution exception, prints the traceback, **discards it**, and
  hands the critic a fixed `[SYSTEM NOTICE]` string. The critic is then
  asked to debug code it cannot see from an error it was never told, and
  the artefact it revises is the prose description rather than the code.
  Do the opposite: feed `pdflatex`'s log back verbatim, iterate on the
  `.tex` source, and retry with the error rather than rolling back.

We also have an advantage PaperBanana structurally lacks -- its critic
sees only the rendered raster, where ours can see the render **and** the
TikZ source that produced it.

Size: M. Depends on: D1-D3, and evidence that they left a real gap.

## Theme F: the auto-improvement loop

[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md) specifies a seven-step track
that predates this roadmap and overlaps it at three points. Its items
are folded in here rather than restated, and **that document remains
the owner of every contract below** -- what follows is placement and
ordering, not a second specification.

Its own status line is stale, which matters for anyone costing this:
it says the `prose` class *"has no producer until #103 and #107 land"*,
but [HOUSE-STYLE.md](HOUSE-STYLE.md) records #107 shipped in 5.13.0 and
its automatic invocation (#183) in 5.19.0, and `chitragupta/style_check.py`
carries `--json` today. **Build-order step 6 has shipped.** Steps 3 and
6 are done; 1, 2, 4, 5 and 7 are the live work.

### F1: `--json` on the other two review aids

Step 2 (#127, widened). `verbatim scan` and `verbatim recheck` emit
`--json` today; `citation_provenance` and `citation_coverage` do not.
The layer-level plumbing they would reuse -- `review.envelope()` and
`review.write_json()` -- already exists.

A *"hard prerequisite for everything below"* in its own document, and a
prerequisite for this roadmap's Theme C too: an aid that cannot emit
JSON cannot feed an agenda, and C1's report is the fourth thing that
would want to.

The contract is worth restating because it is easy to get wrong: the
JSON is *"an additional serialisation of the same findings list, never a
second computation"*, the printed Markdown stays authoritative, and
there is no timestamp, so two runs over unchanged input are
byte-identical.

Size: M. Depends on: nothing. **The best-value item in this theme** --
small, unblocks four other things.

### F2: the `agenda` aid

Step 4, and the largest genuinely new piece of the track. A fourth key
in `review.AIDS`: deterministic, stdlib-only, no LLM, takes no lock,
exits 0 whatever it finds. It reads the other four aids' JSON plus the
dossier's drift report and emits **one ranked, deduplicated worklist**
-- *"This cross-signal merge is the work no individual aid can do."*

Six item classes, of which **three are surfaced and never acted on**
(`unsupported-claim`, `uncited-source`, `candidate` -- all judgement),
one is unattended (`missing-citekey`), and two are partial
(`verbatim-run` except the long runs reserved for a human; `prose` only
where mechanically re-checkable).

Two questions the document leaves open, and this roadmap does not close:
whether `missing-citekey` should be acted on unattended at all, and how
the agenda should behave on a draft with no dossier -- where *"refusing
may be the right answer here even though no other aid refuses."*

This roadmap adds a producer: [C1](#c1-uncited-prose-report) is either a
seventh class or folds into `unsupported-claim`. Either way it is
surfaced, not unattended.

Size: L. Depends on: F1. Also wants #128's severity buckets, which
shipped in 5.5.0 -- ordering is by class, then bucket, then position,
and the stated risk is *"alarm fatigue, not correctness"*.

### F3: widen `overlap-reviser` into `agenda-reviser`

Step 5. `overlap-reviser` shipped in 5.7.0 as #129-as-filed: the
`verbatim-run` class alone, consuming `verbatim scan --json` directly.
Widening it means *"giving it the agenda as an input and the other
classes as work"* -- the write-set, the two-attempt limit, the binary
re-check and the person-only trigger are already what R1-R11 ask for.

Two pieces landed with it that this work should reuse rather than
rebuild: the scan payload's `id` (R2's stable identity) and
`verbatim recheck` (R3's binary check and R4's count, made
deterministic). [B5](#b5-pre-gate-self-feedback-loop) in particular should
take its acceptance test from here rather than from upstream.

Size: L. Depends on: F2, and the amendment only for automation --
person-triggered widening needs no amendment at all.

### F4: the gating decision -- already answered

Step 7 (#130), and it is worth recording that this one is **closed, not
pending**. It was measured against this project's own 178,000-word book
and declined: no span-length threshold separated the one genuine
violation from correctly-quoted passages several corpus papers share.
[What is deliberately not proposed](#what-is-deliberately-not-proposed)
carries it. Revisitable only on new evidence -- a corpus of real rather
than planted reuse, or a version-controlled seed allowlist.

Size: none. Depends on: nothing. Listed so it is not re-opened by
someone reading step 7 and assuming it is outstanding.

## Theme E: nice to have

### E1: per-citekey TL;DR

A one-paragraph summary per citekey, so skimming a large corpus does not
mean opening every PDF.

**The placement is the whole design decision.** The natural UX --
showing it in `python -m chitragupta.corpus ledger` output -- is
architecturally wrong twice over under constraint 1: the summary is LLM
output, so it cannot be written to the ledger, and having the corpus
layer read a generative artefact would invert the layer order.

Proposed instead: summaries are generative, so they belong to the
drafting layer; they are written to a sidecar under `content/tldr/` by a
drafting-layer command, and read back by that same command. `corpus
ledger` is not touched. A summary is keyed to the parsed text's
fingerprint so it can report itself stale rather than silently
describing a paper that has since been re-parsed.

Size: M. Depends on: nothing. Genuinely last -- it improves browsing,
where everything above improves what gets published.

## Theme G: topic modelling

**The one theme here with shipped work in it**, which is why it reads
differently from A-F above. Those propose; this one records what landed
in [#287](https://github.com/prasadtalasila/chitragupta/pull/287) and
what it left undone. The evidence -- which published finding argued for
each decision, and which measurement on this project's own corpus
confirmed or contradicted it -- is in
[TOPIC-MODELLING.md](TOPIC-MODELLING.md); the numbers are in
`bench/RESULTS.md` under 2026-08-21.

It also breaks this document's "no ML dependency in the core" line only
in appearance: every part of it lives in the optional enrichment layer,
which has had `bertopic` and `sentence-transformers` since long before
this.

### Built

| Feature | What it does |
|---|---|
| Seed topics | Hand-authored `content/seed_topics.toml`. A phrase is one topic and is never split -- `structural health monitoring` is embedded whole, not as three unigrams |
| Unlimited seed lists | Seeds never enter the clustering, so naming topics costs no discovered ones. Routing nine phrases through BERTopic's zero-shot mode had cost 28 emergent topics (81 down to 53) |
| Per-phrase ranking | Each phrase ranked against *its own* scores. `Standards` peaked at 0.295 corpus-wide while `Digital Twin` had a median of 0.338, so one absolute cutoff returned nothing for the first and half the corpus for the second |
| Many-to-many matching | A paper is listed under every seed topic it matched, not only its closest |
| Emergent memberships | Every topic a document belongs to, from HDBSCAN's own soft clustering -- the only one of five mechanisms measured that agrees with the clustering it describes |
| Configurable depth | `topic_min_cluster_size`, `topic_min_samples`, `topic_neighbors`. Their hardcoded predecessors saturated at 20 documents, capping any corpus at ~13 topics |
| Whole-document embedding | Chunk-and-pool rather than truncate: a 512 word-piece limit against 22,000-token papers was embedding ~2% of each |
| Content preprocessing | Reference lists and boilerplate dropped before chunking. Nothing else -- no stop-word or low-frequency filtering, which would destroy the domain terms the corpus is discriminated by |
| A reader | `chitragupta corpus topics`, tier 1: no venv, no GPU. Ends with the papers no seed matched |

### Next

| # | Item | Size | Why | Depends on |
|---|---|---|---|---|
| G1 | [#297](https://github.com/prasadtalasila/chitragupta/issues/297) domain-term topic labels | M | Labels are stopwords (`0_the_and_of_to`) or author names -- `werner kritzinger, fraunhofer austria` is a top-three topic. Dropping bibliographies did **not** fix it: the name is in 55 documents' body text. The cluster is right; only the label is wrong | -- |
| G2 | [#298](https://github.com/prasadtalasila/chitragupta/issues/298) descriptor-based membership | M | 1.64 topics/paper and 25% plural, against 5.03 and 92% for the descriptor mechanism measured beside it. HDBSCAN soft membership answers "which density region", which is near-binary for core points | -- |
| G3 | [#299](https://github.com/prasadtalasila/chitragupta/issues/299) converged topic set | M | Seed and emergent topics are two artefacts describing one corpus, joined by nobody | G2 |
| G4 | [#300](https://github.com/prasadtalasila/chitragupta/issues/300) stability validation | M | Nothing measures whether a topic set reproduces. One swept setting moved from 13 topics to 5 across an upstream change, with `random_state=42` throughout | -- |

### What Theme G is deliberately not doing

| Not proposed | Why |
|---|---|
| Abstractive topic summaries | Abstractive models carry factual inconsistencies in up to 30% of outputs. A topic summary asserting a claim no paper made is the same failure class as a fabricated citekey ([SOUL.md](../SOUL.md)). Extractive first, behind a human gate |
| An LLM transcribing document structure | Span *selection* (offsets to keep) is safe; span *transcription* is not, because a transcribed reference can be a fabricated one. See [#301](https://github.com/prasadtalasila/chitragupta/issues/301) |
| Topic ids treated as stable | They are not, and the stage's own docstring says so. Anything downstream must key on labels or citekeys |
| DocBank-grade structural extraction ([#301](https://github.com/prasadtalasila/chitragupta/issues/301), closed) | Filed because artefact clusters dominated the topic list; G1 removed all of them with no new dependency, which is what that issue said would retire it. If structural extraction is wanted later, [GROBID-CITATION-GRAPH.md](GROBID-CITATION-GRAPH.md) is the better starting point -- purpose-built for the author block and reference list, structured records rather than token classes, and sequence labelling rather than layout inference |

## Build order

Highest value first. "One PR" is the unit throughout. Items needing
**the amendment** need a person's decision, not engineering time, and
are marked.

| # | PR | Theme | Size | Depends on |
|---|---|---|---|---|
| 1 | [B1](#b1-cap-passages-per-source) per-source passage cap | B | S | -- |
| 2 | [A2](#a2-split-support-into-claim-and-quote) `claim:` / `quote:` split | A | M | -- |
| 3 | [A3](#a3-extraction-at-the-retrieval-boundary) extraction at retrieval | A | S-M | A2 |
| 4 | [D1](#d1-the-metaphor-rule-and-a-layout-checklist) metaphor rule + layout checklist | D | S | -- |
| 5 | [F1](#f1---json-on-the-other-two-review-aids) `--json` on the other two aids | F | M | -- |
| 6 | [B2](#b2-require-multi-source-paragraphs) multi-source paragraphs | B | M | B1 |
| 7 | [C1](#c1-uncited-prose-report) uncited-prose report | C | M | F1 |
| 8 | [A1a](#a1a-make-the-verbatim-scan-a-required-step) mandatory verbatim scan | A | M | **amendment** |
| 9 | [A4](#a4-the-evidence-appendix) Evidence appendix | A | M | A2 |
| 10 | [D2](#d2-deterministic-tikz-layout-check) deterministic TikZ layout check | D | M-L | D1 |
| 11 | [B3](#b3-section-thesis-with-source-count) section thesis + count | B | S | -- |
| 12 | [A0](#a0-record-the-attribution-done) borrowing position | A | XS | before any borrowing |
| 13 | [B4](#b4-cross-encoder-reranking) cross-encoder reranking | B | M-L | B1 |
| 14 | [F2](#f2-the-agenda-aid) the `agenda` aid | F | L | F1 |
| 15 | [D3](#d3-known-good-layout-scaffolds) layout scaffolds | D | M | D1, D2 |
| 16 | [C3](#c3-quotation-and-page-integrity) quotation integrity | C | M | A2, A4 |
| 17 | [F3](#f3-widen-overlap-reviser-into-agenda-reviser) widen to `agenda-reviser` | F | L | F2 |
| 18 | [B5](#b5-pre-gate-self-feedback-loop) pre-gate self-feedback | B | M | **amendment**, A2, F3 |
| 19 | [C2](#c2-claim-support-checking) claim-support checking | C | L | C1 |
| 20 | [E1](#e1-per-citekey-tldr) per-citekey TL;DR | E | M | -- |
| 21 | [D4](#d4-optional-vision-critique) vision critique | D | M | D1-D3 |

Withdrawn: [A1b](#a1b-auto-route-findings-into-overlap-reviser----declined).
Already answered: [F4](#f4-the-gating-decision----already-answered).

**What changed from the first draft of this document, and why it
matters.** A1 was PR #1 and "Depends on: nothing". Reading the
auto-improvement track moved it to #8 behind a user decision, and split
off its second half as declined. The lesson generalises: **every item
here that makes something run automatically, or repairs a draft without
being asked, is gated on the amendment or refused by the self-marking
argument.** Check a new proposal against both before costing it.

**Three items have written plans.** `plans/` holds the implementation
plan for a roadmap item whose design is genuinely underdetermined --
[A2](#a2-split-support-into-claim-and-quote),
[B2](#b2-require-multi-source-paragraphs) and
[D2](#d2-deterministic-tikz-layout-check) have one each, as worked
examples of the convention. Most items do not need one: the entry above
already names the files, the size and the dependencies, and for a
mechanical change that is the whole plan.
[plans/README.md](../plans/README.md) has the three tests for when a
plan earns its place. That directory does not ship.

**The first four PRs need no decision and no new dependency**, and
between them they do the thing that was actually asked for -- move the
pipeline from detecting verbatim reuse afterwards to not producing it.
B1 and A2 are the whole spine; A3 closes the context leak; D1 addresses
the figure complaint at its source.

## What is deliberately not proposed

Recorded so each is not re-proposed as an oversight.

| Not proposed | Why |
|---|---|
| A blocking overlap gate | Declined on measured evidence (#130), and a second meaning would blunt the gate's one meaning ([WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10) |
| Claim extraction cached in the corpus or enrichment layer | LLM output on the corpus plane; breaks "same bibliography in, same citekeys out" ([SOUL.md](../SOUL.md)) |
| TL;DR shown in `corpus ledger` output | Same, plus it inverts the layer order -- see [E1](#e1-per-citekey-tldr) |
| Image-generated figures | Non-deterministic, and cannot satisfy §10's two-form contract |
| Any ML dependency in the core | `bibtexparser` as sole core dependency is a design decision in `pyproject.toml`, not an accident |
| Fetching papers from arXiv or anywhere else | Admission is the reference manager's job alone ([AGENTS.md](../AGENTS.md)) |
| Copying from zotero-arxiv-daily | AGPLv3, and excluded by the project owner |
| Positional `[n]` citation numbering | Upstream's scheme; reordering the passage list silently changes every citation's meaning. This project has real citekeys |
| OpenScholar's dead code paths | Its LLM reranker (`process_ranking_results`), `final_processing`, and `--use_abstract` are defined and never called; its `--norm_cite` adds a bounded `[0,1]` bonus to an unbounded cross-encoder logit |

# 🗺 Feature roadmap: what would be built, and in what order

Status: **plan for unbuilt work.** Written 2026-08-20. Updated 2026-08-30.
**Eighteen of the original twenty-one items have shipped and have been
removed from this document** rather than marked as done. One more has
been removed without shipping: B3, section thesis with a source count,
closed unbuilt as *"not a priority now"*
([#379](https://github.com/prasadtalasila/chitragupta/issues/379)) and
recorded under [the build order](#-build-order) so it is not re-proposed
as an oversight. Everything below is still outstanding, which is what
makes the list usable -- with one item **partly** built, [B5](#-b5-pre-gate-self-feedback-loop),
whose entry says which half shipped and which did not.

**For what the pipeline does today, read [FEATURES.md](FEATURES.md).**
That is this document's counterpart: the capability surface as built,
pinned to the code by a test. This one is what *would* be built, and is
allowed to age. Where a `Depends on` entry below names an item that is no
longer here -- A2, C1 -- that dependency has shipped and is satisfied;
FEATURES.md describes it and `plans/` has how it was built.

Drafts out of this pipeline carry too much of their sources' wording.
This document says why that happens -- it is a property of how evidence
reaches the drafter, not a failure of the detectors -- what to build to
stop it, and in what order. It then does the same for TikZ figure
layout.

Two upstreams are drawn on, both Apache-2.0:
[OpenScholar](https://github.com/AkariAsai/OpenScholar) for the
synthesis half, [PaperBanana](https://github.com/dwzhu-pku/PaperBanana)
for the figure half.

> **Nothing is copied from either.** Both are taken as inspiration and
> attributed in [INSPIRATION.md](INSPIRATION.md), under that file's
> existing rule -- *"Attribute the idea, and never copy the text."*

That is a settled decision, not an open option: copying was offered and
declined once the cost of declining had been measured at roughly one PR.
[The borrowing posture](#-the-borrowing-posture-inspiration-or-copy) has
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

## 🧭 Table of contents

- [The diagnosis](#-the-diagnosis-where-a-sources-wording-actually-enters-a-draft)
- [The baseline](#-the-baseline-measured-before-proposing-anything)
- [The borrowing posture](#-the-borrowing-posture-inspiration-or-copy)
- [The decision that gated part of this (taken)](#-the-decision-that-gated-part-of-this-taken)
- [What the OpenScholar sample demonstrates](#-what-the-openscholar-sample-demonstrates)
- [Four constraints every item respects](#-four-constraints-every-item-respects)
- [Theme A: close the leak](#-theme-a-close-the-leak)
- [Theme B: make synthesis structural](#-theme-b-make-synthesis-structural)
- [Theme C: verify faithful use](#-theme-c-verify-faithful-use)
- [Theme D: figure layout](#-theme-d-figure-layout)
- [Theme E: the human's own structure](#-theme-e-the-humans-own-structure)
- [Theme F: the auto-improvement loop](#-theme-f-the-auto-improvement-loop)
- [Theme G: topic modelling](#-theme-g-topic-modelling)
- [Build order](#-build-order)
- [What is deliberately not proposed](#-what-is-deliberately-not-proposed)

## 🩺 The diagnosis: where a source's wording actually enters a draft

The detectors are not the problem. The path evidence takes to the
drafter is. Traced through the current code:

1. `chitragupta/retrieval.py::search()` returns a **500-character raw
   snippet** per candidate (`snippet_chars=500`).
2. `chitragupta/retrieval_cli.py::evidence()` returns **two 600-character
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

## 📊 The baseline, measured before proposing anything

The diagnosis above is read off the code. This is what the existing
detector actually reports today, run against the four real drafts in
`content/drafts/digital-twins-for-software-engineers/` on the 501-paper
corpus. `verbatim scan` is read-only and takes no lock, so this is safe
to reproduce at any time.

| Draft | Words | Findings | Longest run | From an **uncited** source | Already quoted |
| --- | --- | --- | --- | --- | --- |
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
it does change what "done" looks like, and it added a precondition:
A1a had to
ensure the dossier is populated enough for tier 3 to run, or the
mandatory scan would keep reporting two tiers of three and looking
clean. **These four drafts turned out to have no dossier at all** -- the
skipped-tier message names a `sections.md` that was never there -- so
what A1a actually built is a regeneration of the table immediately
before the scan, in every skill.

**3. `deep-research` scored zero, and it is the one genre that already
records claims.** Its SKILL.md writes "kept claims and their citekeys"
into `evidence.md`; `survey-writer` and `tutorial-writer` are the two
that specify a `support:` line, and they are the two with the most
findings. That is exactly the correlation
A2 predicts.

**Treat it as suggestive and not as proof.** It is four drafts on one
topic; `deep-research` is also the shortest and cites the fewest
sources; and the dossiers for these drafts no longer hold `evidence.md`
files, so the shape their evidence actually took cannot be verified
after the fact. It is a reason to build A2 and measure, not evidence
that A2 is already validated. A1 should report this same table before
and after, which costs one command.

## 🔬 What the OpenScholar sample demonstrates

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
A4 is **our design, read off the sample
output** -- there is nothing upstream to port for it. What the repository
does supply is a prompt that demonstrably asks for property 1, which is
why B2 can point at prior art for
the behaviour it wants rather than arguing for it from scratch.

## ⚖ The borrowing posture: inspiration, or copy?

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
| --- | --- | --- |
| A0 | -- | **Negative.** No `NOTICE`, no per-file provenance headers; two INSPIRATION.md entries instead, in the pattern that file already uses for its CC-BY-NC precedent |
| A2 | Two prompt sentences | **~0.** They are generic ("summarize rather than copy"); house style differs anyway |
| B1 | ~12 lines of dict-counting | **~0.** Already being rewritten -- keyed on citekey rather than title, and with the off-by-one fixed. Only the cap-then-truncate *ordering* has value, and that is an idea |
| B2 | `prompts_w_references` | **Small.** Its citation mechanics are positional `[n]` against a flat blob, so a substantial rewrite was required regardless. What is lost is validated wording |
| B4 | "reranking code" | **~0.** The shipped reranker is one `compute_score` library call. Everything around it is dead code this roadmap already declines |
| D1 | Style guide + ~40 enumerated vetoes | **The whole delta.** ~1 PR |
| [D4](#-d4-optional-vision-critique) | Loop shape + calibration clause | **~0.** Loop shape is architecture; the clause is two sentences |

### 💡 Why D1 carries all of it, and why that is acceptable

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

### 🏁 The outcome

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

## ⚖ The decision that gated part of this (taken)

**Approved by the user on 2026-08-21, applied in 6.20.1 by #312.** Kept
because it is the one decision in this roadmap that was never an
engineering call, and the next person to propose driving a review aid
should find the reasoning rather than re-open it.

[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)'s build order opened with a
step that is *"Not a coding task"*: an amendment to the review layer's
stated posture, which was documented as **manual** as well as advisory --
*"run by hand on a finished draft, never invoked automatically"*. The
surviving invariant:

> a review finding may be read, may be invoked by a driver, and may never
> block a draft.

-- advisory versus blocking, rather than manual versus automatic.
[SOUL.md](../SOUL.md) is deliberately *not* amended, because the rule
that changed is stated only in the layer's implementation and in the
documents describing it, never in the soul.
`python -m chitragupta.draft gate` remains the only gate.

**Why it landed here.** A1a
makes `verbatim scan` run without a person asking, which is exactly the
rule above -- so A1a's real dependency was a user decision, and its real
cost included the wording sweep and three diagram re-renders rather than
the "no Python" change this roadmap first estimated.
[AUTO-IMPROVEMENT-RATIONALE.md](AUTO-IMPROVEMENT-RATIONALE.md#-the-amendment-this-needs)
has the sweep, and the lesson that outlived it: the count grew from
twelve to twenty-two while the decision was pending, because three aids
landed in between and each brought its own copy of the sentence.

**One counter-precedent, pre-empted.** `style_check` already ran
automatically before this -- a PostToolUse hook per write, and a step in
all nine skills (#183). It did not transfer: `style_check` is
`python -m chitragupta.draft style`, a **drafting-layer** command, and
the never-automatic rule was stated only about layer 4.

## 🔑 Four constraints every item respects

Named up front because each one has already killed an obvious design.

**1. No LLM output may reach the corpus plane.** [SOUL.md](../SOUL.md):
the corpus layer "has no LLM and no judgment calls"; the enrichment
layer "reads the ledger and never writes it" and "nothing in it is
generative". So extracted claims live in the **dossier**, and the
per-citekey TL;DR (`chitragupta draft tldr`, [FEATURES.md](FEATURES.md))
got an explicitly named home that is neither `corpus` nor `enrich`.
Writing either into the ledger would break "same bibliography in, same
citekeys out".

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
prompt strings; rewrite the imports. Of everything proposed here, none
needs the ML stack -- B4, cross-encoder reranking, was the one item
that did, and it shipped behind `enrich` per this rule.

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
  likely to be broken here, and [B5](#-b5-pre-gate-self-feedback-loop) broke
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

## 💧 Theme A: close the leak

The highest-value theme, and the one the request is actually about.
A1-A4 have all shipped; what remains is the one half declined below.

### 🚫 A1b: auto-route findings into `agenda-reviser` -- declined

The first draft of this roadmap paired A1a with automatic routing of
findings into the existing `agenda-reviser` skill. **That half is
withdrawn**, on the project's own reasoning rather than on new grounds.

[AUTO-IMPROVEMENT-RATIONALE.md](AUTO-IMPROVEMENT-RATIONALE.md) refuses a
genre skill repairing its own output: *"a skill repairing its own output
is marking its own homework, which is why the existing gate loop
discards an unsupported claim and writes again rather than 'fixing'
it."* The amendment does not touch this argument -- it is about
self-marking, not about who may invoke an aid.

It also falsifies two written claims at once: `agenda-reviser`'s own
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

## 🧩 Theme B: make synthesis structural

Theme A stops wording leaking. Theme B removes the *opportunity* by
changing what a paragraph is required to be.

### 🔁 B5: pre-gate self-feedback loop

**The step shipped ([#438](https://github.com/prasadtalasila/chitragupta/pull/438),
2026-08-28); four amendments written the day after did not.** Each of
the five genre skills that drafts fresh prose from an evidence packet now
critiques that draft against `evidence.md` before gating -- up to five
gaps listed, the top three repaired, one edit each, no retry and no
second critique pass -- and keeps an edit only if `draft gate`,
`verbatim recheck --baseline` and `draft style` all say it made nothing
worse. `tests/test_skill_pregate_feedback_step.py` pins it, and
**`plans/b5-pregate-self-feedback.md` is the authoritative design for
both halves**: what shipped, and what is left. This section is the
ticket, not a second specification.

What is left is what **a 2026-08-28 read of four upstreams (Theme E's
research) left owed**. It was written down by #439, merged the day after
the step did, so none of it reached what shipped. One line each, and
their status:

- The length-ratio rejection is **confirmed from source** (OpenScholar
  accepts an edit iff it is ≥90% as long as the original, so a longer
  and wronger answer is always accepted). **Already satisfied**: the
  shipped step keeps the ratio as a secondary sanity floor and never as
  the acceptance test, which is what **R3** requires.
- Coverage must be marked on **evidence retrieved, never on query
  issued**. **Open, and it names a located defect rather than a
  preference**: `dossier/_outline.py::declared_vs_actual` computes its
  `run` set from a logged call's *origin*, never from that row's
  `results` count, so a declared query that ran and returned nothing
  reads exactly like one that returned twelve. That is the upstream
  failure mode, inside this repository.
- A **fixed corpus makes a declared query list exhaustible**, so a real
  termination condition is available here and is in none of the four
  upstreams. **Open**, and it is the one place this design beats every
  one of them.
- **An empty result set is informative** -- it means the claim cannot be
  grounded, so the sentence is cut rather than cited. **Open**: no
  skill's text says this today.

Filed as [#480](https://github.com/prasadtalasila/chitragupta/issues/480)
(the defect) and
[#481](https://github.com/prasadtalasila/chitragupta/issues/481)
(the two skill-text amendments); the fourth needs no issue, and closes
by being cited in #481's PR.

Size: S (three amendments; the fourth needs no work). Depends on:
nothing. The amendment it once waited on was
[taken](#-the-decision-that-gated-part-of-this-taken) and applied in
6.20.1 by #312, and A2 and `verbatim recheck` both shipped before the
step did.

## ✅ Theme C: verify faithful use

Detection, after Theme A and B have reduced what there is to detect.
Both are review-layer aids: advisory, exit 0, never gates.

### 🔢 C4: a numeral in prose is a claim too

The gate proves a **citekey** is real. Nothing proves a **magnitude**
came from anywhere -- a draft may state "throughput rose 43%" with a
perfectly real citation beside it and no check anywhere relates the
number to the source. Invented magnitudes are the second-most dangerous
fabrication class after invented references, and they are currently
unguarded.

The mechanism is deterministic and needs no model: **report a prose line
that contains a numeral and no traceable origin.** Credited to
[K-Dense-AI/scientific-agent-skills](INSPIRATION.md), whose writing
skill errors on exactly that condition.

Three things this project already has make it cheaper here than there.
`math.md` (WRITING-STANDARDS.md §12) is keyed on the exact span text of
every quantity a draft states, so a mapped quantity already has a
record; the sentence splitter exists; and the review layer's report
shape is settled. The work is deciding what counts as traceable -- a
`math.md` row, an adjacent citekey, a `quote:` in `evidence.md` -- and
being honest that a year, a section number and a figure reference are
numerals that are not claims.

**Advisory, and the false-positive rate decides whether it is usable at
all**: a survey is full of legitimate bare numerals. Ship it reporting
what it finds and let a real draft say whether the signal survives.
Carries R2 and R10 like any aid.

Size: M. Depends on: C1's sentence splitting.

### 🙅 C6: measure the refusal

Gao's survey (arXiv:2312.10997) lists **negative rejection** among the
four abilities a RAG system should be evaluated on -- whether a system
declines to answer when the retrieved material does not support an
answer. **This project is designed around that behaviour and does not
measure it.** Every genre skill is told to report thin coverage rather
than pad it; E4 (shipped, #456) sharpens it further with "an empty
result means the claim cannot be grounded, so the sentence is cut".
Nothing tests whether any of that actually happens.

The instrument is buildable without a model and without labels, because
the corpus is closed and this repository already owns the trick:
`bench_retrieval_keyword_selfretrieval.py` uses a paper's own
author-assigned keywords as a query whose right answer is known. The
negative case is its complement -- **a query whose correct answer is
that the corpus holds nothing** -- and one honest way to build it is to
take keyword sets from entries that are *in the bib file but not
parsed*, or from a held-out shelf excluded by `--collection`, so the
topic is real and the supporting text genuinely absent.

What it reports is a rate, not a verdict: how often a draft asserts a
claim on a sub-theme the corpus cannot support, against how often it
says so. **Advisory, and the harder half is the ground truth rather than
the check** -- a sub-theme the corpus covers thinly is not the same as
one it does not cover, and conflating them would manufacture failures.

Size: M. Depends on: nothing, though it reads best beside E4 (shipped, #456).

## 📐 Theme D: figure layout

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
| --- | --- | --- |
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
figure shows. D2 should exploit
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

### 👁 D4: optional vision critique

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

**Skipped by evidence, 2026-08-26 (#388).** The evidence this section
already asked for, gathered before writing any critic: `review figure`,
plus per-host scripts measuring label-fit and figure width the same
way, run over all 43 figures in this project's own drafted book -- not
`assets/tikz/`'s six scaffolds, which report zero findings **by
construction** (#382's own acceptance test)
and so cannot answer whether D1-D3 left a gap. Two mechanical findings
came back, a `content-protrusion` in `15-2-mesh-versus-hub` and a
`stranded-arrowhead` in `2-2-model-simulator-simulation` -- and both are
already inside `review figure`'s own remit: `figure_layout/_source.py`'s
own docstring names the `2-2` case as the exact true positive found
when that check was built. Neither is a D4 finding.

A full visual pass over all 43 renders -- the part only a vision judge
can do: does the figure communicate its point, is the routing chaotic,
is the type illegible or inconsistent, does a `fill` occlude anything --
found nothing beyond those same two. No figure had crossed or spaghetti
arrows, box-ified prose, or type a reader would call inconsistent; every
one communicated its stated point. **D1-D3 already leave nothing on
this corpus for D4 to catch, so it is skipped rather than built,** which
this section already said was the legitimate outcome.

Worth stating plainly rather than overclaiming: the vision judge here
was one LLM, one pass, and this book's figures are technical-diagram
simple -- boxes, arrows, at most one axis -- rather than the dense
multi-panel case a vision critic's argument is strongest for. If a
future book's figures are denser and `review figure` plus this
checklist again come back clean where a reader disagrees, that is new
evidence and reopens the question; this run is not a permanent proof,
only the specific answer on the specific corpus asked about.

Size: none. Depends on: nothing. Revisitable only on new evidence -- a
future book whose figures are denser than this corpus's, where
`review figure` and this section's checklist come back clean but a
reader still disagrees.

### 📏 D5: two checks `review figure` could compute from source

The pre-flight list in [TIKZ-STYLE.md](TIKZ-STYLE.md) *names* two
defects it cannot decide, and both are recoverable from the TikZ source
that `review figure` already parses:

- **Type size at final scale.** "Illegible type" is currently a human
  judgement. It is arithmetic: a `\footnotesize` node inside a picture
  carrying `scale=0.8`, set in a document at a known width, has a
  computable final point size. `figure_layout/_source.py` already splits
  picture and node options, so the parse is in place and the check is
  not.
- **Two palette colours a greyscale print cannot separate.** Colour is
  house-standard and carries meaning freely
  ([TIKZ-STYLE.md](TIKZ-STYLE.md)); what it may not do is carry the
  figure's *main* point alone, because a black-and-white print
  greyscales the TikZ form and `cgFlow` and `cgAlt` land at similar
  lightness. A screen over *declared* colours (`\definecolor` and named
  colours, not pixels) for pairs that differ in hue but not lightness
  would report it. The idea is
  [K-Dense-AI/scientific-agent-skills](INSPIRATION.md)'s palette audit,
  which reads declarations rather than rendering; note their own caveat,
  that a lightness heuristic is not colour-vision simulation. **Advisory
  and easy to over-fire** -- a secondary distinction living only in
  colour is legitimate, so this reports a pair, not a verdict.

Both fit the existing aid: deterministic, source-parsing, advisory,
exit 0. Neither needs the vision critic
[D4](#-d4-optional-vision-critique) declined.

Size: M. Depends on: nothing.

## 🧭 Theme E: the human's own structure

Themes A-D are about what the pipeline does with what it retrieved. This
theme was about two places a **person** could not get a word in:
supplying the structure before drafting, and hand-editing a draft
afterwards. Both were already solved at *book* scale and neither at
single-draft scale -- both have now shipped at single-draft scale too:
supplying the structure (`outline.md`, #455) and noticing a hand edit
(the draft fingerprint, #462) -- and so has the item that used the
second of those, letting a hand-edited section's own prose drive one
extra retrieval round (`chitragupta/retrieval_iterative.py`, #456).
Nothing in Theme E remains open.
`plans/outline-driven-drafting-and-manual-edits.md` and
`plans/e4-draft-is-the-query.md` carry the measurements.

Researched against four upstreams for this theme
([OpenScholar](https://github.com/AkariAsai/OpenScholar),
[RAGFlow](https://github.com/infiniflow/ragflow),
[papersgpt-for-zotero](https://github.com/papersgpt/papersgpt-for-zotero),
[local-deep-research](https://github.com/LearningCircuit/local-deep-research)).
**The result was mostly negative and that is the useful part: three of
the four manufacture no queries at all**, and none verifies a citation --
RAGFlow's only check on a model-emitted marker is `i < len(chunks)`, an
array-bounds test. Nothing here is ported as text
([INSPIRATION.md](INSPIRATION.md)).

### 🧾 C5: the citekeys out must be the citekeys in

A deterministic invariant for any synthesis that combines evidence:
**after every combining step, the union of citekeys in the inputs must
equal the union in the output.** Set arithmetic, no model, no judgement.

The shapes this guards against are catalogued in
[RAG.md](RAG.md#-the-synthesis-shape-how-n-passages-become-one-section):
of LlamaIndex's five synthesis modes, four can drop a source with no
error and no log -- by truncating the tail, by declining to fold a
passage into a running answer, or by attrition across summarisation
levels. Only the one that keeps a fixed-length slot per input can say
which input a missing output belongs to.

Here the relevant surfaces are `deep-research`'s Phase 5, where each
writer is dispatched with the citekeys its section will stand on, and
`book-assembler`, which composes accepted units. In both, the expected
set is already recorded before generation, so the check is a comparison
against something on disk rather than a reconstruction.

**Advisory, and it reports both directions**: a citekey dropped, and a
citekey that appeared from nowhere. The second is the gate's business and
the gate will catch it; reporting it here is how a *located* failure
("section 4 lost `smith_2024`") reaches a person instead of a diff.

Size: S-M. Depends on: nothing.

## 🔄 Theme F: the auto-improvement loop

[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md) specifies a seven-step track
that predates this roadmap and overlaps it at three points. Its items
are folded in here rather than restated, and **that document remains
the owner of every contract below** -- what follows is placement and
ordering, not a second specification.

Its own status line is stale, which matters for anyone costing this:
it says the `prose` class *"has no producer until #103 and #107 land"*,
but [HOUSE-STYLE.md](HOUSE-STYLE.md) records #107 shipped in 5.13.0 and
its automatic invocation (#183) in 5.19.0, and `chitragupta/style_check.py`
carries `--json` today. **Build-order step 6 has shipped, so has step
4 (#381), and so has step 5's widening (#384, #435).** Steps 1 through 6
are done, and step 7 (#130) is a closed, declined decision rather than
an open issue. Nothing in Theme F remains open.

### ⚖ F4: the gating decision -- already answered

Step 7 (#130), and it is worth recording that this one is **closed, not
pending**. It was measured against this project's own 178,000-word book
and declined: no span-length threshold separated the one genuine
violation from correctly-quoted passages several corpus papers share.
[What is deliberately not proposed](#-what-is-deliberately-not-proposed)
carries it. Revisitable only on new evidence -- a corpus of real rather
than planted reuse, or a version-controlled seed allowlist.

Size: none. Depends on: nothing. Listed so it is not re-opened by
someone reading step 7 and assuming it is outstanding.

## 🏷 Theme G: topic modelling

**The one theme here that is entirely built**, which is why it reads
differently from A-F above: not a list of what to build next, but a
record of what landed and the evidence behind each decision.
[#287](https://github.com/prasadtalasila/chitragupta/pull/287) shipped
the mechanism, and G1-G4 -- issues
[#297](https://github.com/prasadtalasila/chitragupta/issues/297)-[#300](https://github.com/prasadtalasila/chitragupta/issues/300),
closed 2026-08-21 -- closed every gap it left open. Nothing in Theme G
remains outstanding. The evidence -- which published finding argued for
each decision, and which measurement on this project's own corpus
confirmed or contradicted it -- is in
[TOPIC-MODELLING.md](TOPIC-MODELLING.md); the numbers are in
`bench/RESULTS.md` under 2026-08-21.

It also breaks this document's "no ML dependency in the core" line only
in appearance: every part of it lives in the optional enrichment layer,
which has had `bertopic` and `sentence-transformers` since long before
this.

### ✅ Built

| Feature | What it does |
| --- | --- |
| Seed topics | Hand-authored `content/seed_topics.toml`. A phrase is one topic and is never split -- `structural health monitoring` is embedded whole, not as three unigrams |
| Unlimited seed lists | Seeds never enter the clustering, so naming topics costs no discovered ones. Routing nine phrases through BERTopic's zero-shot mode had cost 28 emergent topics (81 down to 53) |
| Per-phrase ranking | Each phrase ranked against *its own* scores. `Standards` peaked at 0.295 corpus-wide while `Digital Twin` had a median of 0.338, so one absolute cutoff returned nothing for the first and half the corpus for the second |
| Many-to-many matching | A paper is listed under every seed topic it matched, not only its closest |
| Emergent memberships | Descriptor-based: cosine to each topic's own corpus-mean-centred centroid, not HDBSCAN's soft-clustering probabilities -- 4.64 topics/paper and 92% plural in the shipped configuration, against 1.64 and 25% before ([#298](https://github.com/prasadtalasila/chitragupta/issues/298)) |
| Domain-term labels | Topic names come from the corpus's own recognised terms rather than raw frequent words, with every bibliography surname (1,277 of them) excluded from the label vocabulary -- fixes both stopword names (`0_the_and_of_to`) and author-name names (`werner kritzinger, fraunhofer austria`, present in 55 documents' body text) ([#297](https://github.com/prasadtalasila/chitragupta/issues/297)) |
| Configurable depth, stability-checked | `topic_min_cluster_size`, `topic_min_samples`, `topic_neighbors`. Their hardcoded predecessors saturated at 20 documents, capping any corpus at ~13 topics, and scored an adjusted Rand index of 0.14 under bootstrap resampling -- barely more stable than chance. The shipped defaults score 0.80 ([#300](https://github.com/prasadtalasila/chitragupta/issues/300)) |
| Whole-document embedding | Chunk-and-pool rather than truncate: a 512 word-piece limit against 22,000-token papers was embedding ~2% of each |
| Content preprocessing | Reference lists and boilerplate dropped before chunking. Nothing else -- no stop-word or low-frequency filtering, which would destroy the domain terms the corpus is discriminated by |
| A reader | `chitragupta corpus topics`, tier 1: no venv, no GPU. Ends with the papers no seed matched |
| A converged topic set | `content/topic_set.json` joins seed and emergent topics into one artefact -- an emergent topic within `topic_converge_similarity` of a seed phrase is renamed by it rather than listed beside it, with the closest match winning each side of the collision ([#299](https://github.com/prasadtalasila/chitragupta/issues/299)) |

### 🚫 What Theme G is deliberately not doing

| Not proposed | Why |
| --- | --- |
| Abstractive topic summaries | Abstractive models carry factual inconsistencies in up to 30% of outputs. A topic summary asserting a claim no paper made is the same failure class as a fabricated citekey ([SOUL.md](../SOUL.md)). Extractive first, behind a human gate |
| An LLM transcribing document structure | Span *selection* (offsets to keep) is safe; span *transcription* is not, because a transcribed reference can be a fabricated one. See [#301](https://github.com/prasadtalasila/chitragupta/issues/301) |
| Topic ids treated as stable | They are not, and the stage's own docstring says so. Anything downstream must key on labels or citekeys |
| DocBank-grade structural extraction ([#301](https://github.com/prasadtalasila/chitragupta/issues/301), closed) | Filed because artefact clusters dominated the topic list; G1 removed all of them with no new dependency, which is what that issue said would retire it. If structural extraction is wanted later, [GROBID-CITATION-GRAPH.md](GROBID-CITATION-GRAPH.md) is the better starting point -- purpose-built for the author block and reference list, structured records rather than token classes, and sequence labelling rather than layout inference |

## ▶ Build order

Highest value first. "One PR" is the unit throughout. Items needing
**the amendment** need a person's decision, not engineering time, and
are marked.

**Only unbuilt work appears here.** Eighteen items have shipped and have
been removed from this document rather than marked -- what they became is
described in [FEATURES.md](FEATURES.md), and how each was built is in the
PR that closed it and in `plans/`. A roadmap that accumulates its own
history stops being a list of what to do next, which is the only thing it
is for.

| # | PR | Theme | Size | Depends on |
| --- | --- | --- | --- | --- |
| 1 | [B5](#-b5-pre-gate-self-feedback-loop) the four amendments to the shipped step | B | S | -- |
| 2 | [D5](#-d5-two-checks-review-figure-could-compute-from-source) two figure checks from source | D | M | -- |
| 3 | [C4](#-c4-a-numeral-in-prose-is-a-claim-too) numeral as a claim | C | M | C1 |
| 4 | [C5](#-c5-the-citekeys-out-must-be-the-citekeys-in) citekey union invariant | C | S-M | -- |
| 5 | [C6](#-c6-measure-the-refusal) measure the refusal | C | M | -- |

Withdrawn: [A1b](#-a1b-auto-route-findings-into-agenda-reviser----declined).
Already answered: [F4](#-f4-the-gating-decision----already-answered).
Skipped by evidence: [D4](#-d4-optional-vision-critique).
Deprioritised unbuilt, and removed from this document rather than
carried as a permanent number 1: **B3**, section thesis with a source
count -- issue
[#379](https://github.com/prasadtalasila/chitragupta/issues/379), closed
2026-08-26 with *"Not a priority now"*. Its design survives in that
issue, which is where to start if it is ever wanted; nothing else in
this roadmap depended on it.

**What changed from the first draft of this document, and why it
matters.** A1 was PR #1 and "Depends on: nothing". Reading the
auto-improvement track moved it to #8 behind a user decision, and split
off its second half as declined. The lesson generalises: **every item
here that makes something run automatically, or repairs a draft without
being asked, is gated on the amendment or refused by the self-marking
argument.** Check a new proposal against both before costing it.

**Some items have written plans, and the entry says so where one
exists.** `plans/` holds the implementation plan for a roadmap item whose
design is genuinely underdetermined. Of the items still listed here,
[B5](#-b5-pre-gate-self-feedback-loop) has one. Several more
sit there for items that have since shipped, kept as worked examples of
the convention. Most items need none: the entry above already names the
files, the size and the dependencies, and for a mechanical change that is
the whole plan. `plans/README.md` has the three tests for when a plan
earns its place. That directory does not ship.

**Where an item names its own plan, the plan governs.** B5's entry says
so explicitly, and the entry is the ticket rather than a second
specification -- so a design decision recorded in a plan file is not
repeated here, and the two cannot drift.

**The leading PR needs no decision and no new dependency.** B5's
amendments need neither the amendment (taken in #312, and the step they
amend has already shipped under it), a new model, nor a decision from
anyone -- and one of the four asks for no work at all, while a second is
a located one-function defect rather than a design.

## 🚫 What is deliberately not proposed

Recorded so each is not re-proposed as an oversight.

| Not proposed | Why |
| --- | --- |
| A blocking overlap gate | Declined on measured evidence (#130), and a second meaning would blunt the gate's one meaning ([WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10) |
| Claim extraction cached in the corpus or enrichment layer | LLM output on the corpus plane; breaks "same bibliography in, same citekeys out" ([SOUL.md](../SOUL.md)) |
| TL;DR shown in `corpus ledger` output | Same, plus it inverts the layer order -- see [FEATURES.md](FEATURES.md)'s per-citekey TL;DR section |
| Image-generated figures | Non-deterministic, and cannot satisfy §10's two-form contract |
| Any ML dependency in the core | `bibtexparser` as sole core dependency is a design decision in `pyproject.toml`, not an accident |
| Fetching papers from arXiv or anywhere else | Admission is the reference manager's job alone ([AGENTS.md](../AGENTS.md)) |
| Copying from zotero-arxiv-daily | AGPLv3, and excluded by the project owner |
| Positional `[n]` citation numbering | Upstream's scheme; reordering the passage list silently changes every citation's meaning. This project has real citekeys |
| OpenScholar's dead code paths | Its LLM reranker (`process_ranking_results`), `final_processing`, and `--use_abstract` are defined and never called; its `--norm_cite` adds a bounded `[0,1]` bonus to an unbounded cross-encoder logit |

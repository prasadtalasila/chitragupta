# House style: the prose axis, and what persists across drafts

Status: **proposal, not a plan.** Written 2026-08-11.

Prose is the axis an unattended loop can improve *best*, which is the
reverse of the usual intuition that language is the soft part and citations
the hard one. This document says why, what the objective function already
is, and which of a user's preferences ought to outlive the draft that
prompted them.

**Written for** someone weighing the language-and-style half of
[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md), or working on #102's roadmap.
It assumes [WRITING-STANDARDS.md](WRITING-STANDARDS.md), which is the
standard being checked against, and
[DRAFT-ITERATION.md](DRAFT-ITERATION.md) for the dossier.

**Not covered here:** the loop's own machinery -- the agenda aid, the
skill, the requirements -- which is
[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md), and why the line falls where it
does, which is
[AUTO-IMPROVEMENT-RATIONALE.md](AUTO-IMPROVEMENT-RATIONALE.md). Nothing
here is built; #103, #104 and #107 are the open issues that would build it.

## Table of contents

- [The rule that decides everything](#the-rule-that-decides-everything)
- [Why a readability index is a trap](#why-a-readability-index-is-a-trap)
- [The objective function already exists](#the-objective-function-already-exists)
- [What is binary, and what only looks it](#what-is-binary-and-what-only-looks-it)
- [What persists across drafts](#what-persists-across-drafts)
- [Relationship to #102's roadmap](#relationship-to-102s-roadmap)

## The rule that decides everything

> **R3:** "An unattended item's check is **binary**. No continuous score
> is ever the thing being optimised."
>
> -- [AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md#the-requirements), which
> owns the wording

The reason behind it is that a continuous score invites the loop to
optimise the score instead of the draft -- and that is the whole reason
prose can carry an unattended loop at all. It is also why the
specification counts findings rather than scoring quality: a count of
binary conformance failures is safe to drive to zero, and a quality score
is not safe to maximise.

Applied to language, the rule cuts the axis cleanly in two. "Apply §2" is
binary -- "obviously" is present or it is not. "Improve the readability" is
not, and no amount of care in the prompt makes it so.

## Why a readability index is a trap

Flesch-Kincaid and its relatives look like the `val_bpb` this pipeline is
missing: one number, cheaply computed, no model needed, comparable across
revisions. They are the wrong number, and the failure is not subtle.

The indices are functions of sentence length and syllable count. A loop
minimising grade level will split sentences past the point where the
argument survives the break, and will replace precise technical
vocabulary with shorter, vaguer words -- because a polysyllabic term is
indistinguishable, to the metric, from bad writing. The result scores
better and reads worse, and every one of those edits passes its own
re-check.

That is Goodhart's law with a specific mechanism, and it is worth stating
because the index is otherwise such an attractive candidate: it is exactly
the sort of check that would be adopted for being *measurable* rather than
for being *right*.

An index may still be **reported**. A grade level that moves sharply
between revisions is worth a human's attention. It may never be the thing
being optimised.

## The objective function already exists

[WRITING-STANDARDS.md](WRITING-STANDARDS.md) is it, and it was written that
way before any of this was contemplated. Its §2 and §4 are not aspirations;
they are conformance rules with a decidable answer:

| Rule | Source in WRITING-STANDARDS | Decidable because |
|---|---|---|
| No defect markers: "obviously", "simply", "just", "of course", "clearly", "easy" | §2 | a literal string search -- though #107 adds the caveat, which §2 itself does not, that "just" needs a human eye (adverb versus adjective) |
| Each term defined once, then used consistently | §2 | the dossier already carries a glossary |
| Acronym expanded at first use, then not re-expanded | §2 | first occurrence is computable |
| Short sentences, one idea each | §4 | *not* decidable -- see the next section |
| Active voice with a named actor | §4 | detectable, but a judgement to fix |
| Each paragraph leads with its point | §4 | detectable as a heuristic, a judgement to fix |
| Hedging that carries no information is cut | §4 | detectable, a judgement to fix |

That table is the honest version of "language is autoresearchable": the
*top* of it is, and the bottom is a review aid's output for a human.

The apparatus around it is already specified in open issues, and none of it
needs a model:

- **#104** would record the draft's dialect as a `language:` line in the
  dossier's `scope.md` (BCP-47: `en-GB`, `en-IN`, `en-US`), so the target
  is on disk rather than restated in chat each session. That is the
  *recorded target* an unattended pass needs, and #104 notes that
  `draft-reviser` already reads `scope.md` before any edit, so the
  preference reaches every future revision with no new tooling.
- **#107** would add `scripts/style_check.py` -- dialect consistency
  against that line, plus §2's banned words -- stdlib-only, exit 0 always,
  a review aid and explicitly never a gate. That is the *detector* and the
  *re-check*.
- **#103** would give `draft-reviser` a copy-edit branch: the sanctioned
  path for a whole-document edit that touches no evidence, which the skill
  has no shape for today.

Detector, recorded target, re-check, and a sanctioned edit path -- the
whole loop, and every deterministic part of it costs zero tokens. This is
also why the language half sits on the cheap rungs of
[the cost ladder](AUTO-IMPROVEMENT.md#the-cost-ladder), and therefore why
it is the half worth building first.

**One caution #104 already records.** §2's list is English literals and
§4's voice rules are an Anglophone convention. A non-English draft needs
them adapted, not transliterated -- so none of this generalises to #108's
multilingual track for free.

## What is binary, and what only looks it

| Property | Binary? | Unattended? |
|---|---|---|
| Dialect conformance against `scope.md`'s `language:` | yes | yes (#104, #107) |
| §2's defect markers | yes, minus "just" | yes |
| Acronym expanded at first use; term defined once | yes, given the dossier glossary | yes |
| Terminology and notation used consistently | yes, given a registry | yes (#138's detectors) |
| Cross-references resolve | yes | yes (#138) |
| Duplicate or near-duplicate sentences across sections | yes, at a threshold | yes -- `src/overlap_index.py` already indexes n-grams |
| Reference-list consistency | yes | already deterministic (`src/references.py`) |
| A section citing nothing at all | yes | surfaced -- the fix is evidence, not wording |
| Sentence length, hedging density, passive-voice ratio | **no -- these are scores** | surfaced only |
| Readability index | **no** | reported, never optimised |
| Whether a paragraph leads with its point | heuristic | surfaced |
| Whether a source supports a claim | no | never -- [why](AUTO-IMPROVEMENT-RATIONALE.md#why-provenance-is-excluded) |

## What persists across drafts

A user of this pipeline writes many documents over years -- a survey, a
thesis chapter, a textbook chapter, tutorials -- and today each one starts
from a blank slate on everything except the corpus. Their house style is
re-derived, or re-stated in chat, every time.

The relevant precedent is #104's framing: a preference "had nowhere on disk
to live", so it silently reverted to the model's default. Four more
preferences have the same shape, and all four already have a per-draft
artefact that nothing reconciles across drafts:

- **Dialect and house style.** #104's `language:` line is per-draft by
  design, because a thesis at an Indian university and an IEEE submission
  legitimately differ. But a user who has chosen `en-GB` four times has a
  default, and re-choosing it is friction rather than a decision.
- **The glossary.** Every dossier carries one. An author writing a thesis,
  a survey and a textbook chapter on the same subject should not define
  "digital twin" three different ways, and nothing today notices that they
  have.
- **The boilerplate allowlist.** #128 built this one already, and not
  quite as first framed here: `content/verbatim_allowlist.toml` is
  per-host, gitignored data, the same footing as `config.toml`, not
  version-controlled. A phrase waved through once still does not get
  re-flagged in the next draft on the *same* host -- the file is one
  per clone, not one per draft, so it persists across everything that
  clone drafts -- but "auditable" now means "in this host's own file,"
  not "visible in the project's git history to every contributor." See
  [PLAGIARISM.md](PLAGIARISM.md#the-boilerplate-allowlist) for the
  shipped design and why.
- **Recurring refusals.** A user who declines the same kind of source in
  four drafts has a policy, not four coincidences. `rejected.md` records
  each refusal with a reason; nothing reads those reasons across drafts to
  notice the pattern.

**The asymmetry has to survive the altitude change.** In autoresearch the
human edits `program.md` and the agent never does; here `program.md` is the
skills, `docs/WRITING-STANDARDS.md`, and these standing preferences. A
loop that rewrote its own standards from its own accepted-edit statistics
would be a machine revising the terms of its own supervision. It proposes;
the human accepts -- the same sentence as everywhere else in this
proposal, one level up.

What that means concretely: a cross-draft pass may *report* that `en-GB`
was chosen four times out of four, or that a term is defined three ways,
and may offer the edit. It may not write the preference file itself.

## Relationship to #102's roadmap

Issue #102 already sequences the language work as six PRs, ranked by who
is blocked today. Nothing here reorders it; this document adds the reason
the first three matter more than their size suggests.

| #102's PR | What it is | Why it matters here |
|---|---|---|
| #103 | copy-edit mode in `draft-reviser` | the sanctioned edit path -- without it there is nowhere for a prose fix to go |
| #104 | dialect as a first-class draft property | the recorded target |
| #105, #106 | render-language plumbing, localisable references | unrelated to this loop; the non-English track |
| #107 | `scripts/style_check.py` | the detector and the re-check |
| #108 | multilingual corpus support | out of scope, and see the caution above |

Issue #102 ranks #107 fifth, as "a nice-to-have consistent with the
project's review-aid posture". That ranking is right for a human-driven
workflow and wrong for an unattended one: without #107 there is no binary
check, and
without a binary check the prose class of
[the agenda](AUTO-IMPROVEMENT.md#item-classes) cannot be acted on at all.
If the loop is built, #107 moves up.

# ✍ House style: the prose axis, and what persists across drafts

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
[AUTO-IMPROVEMENT-RATIONALE.md](AUTO-IMPROVEMENT-RATIONALE.md).

**Partly built, as of 5.12.0.** #103 shipped the sanctioned edit path
(`draft-reviser`'s copy-edit mode) and #104 the recorded target
(`scope.md`'s `language:` line, and
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) §8), so what this document
called *the objective function* is now normative in that file's §9 rather
than proposed here. The detector (#107) shipped in 5.13.0, and its automatic
invocation (#183) in 5.19.0 -- a PostToolUse hook per write and a step in
all nine skills.

What remains unbuilt is **part** of the machinery under "What persists
across drafts" below -- not all of it, as this paragraph previously
said. Two of its four items have since been built and that section says
so in its own body: the boilerplate allowlist (#128, as per-host
gitignored data rather than the version-controlled file first framed
here) and the acronym-shaped slice of the glossary (#190). Genuinely
unbuilt, and covered by no issue: the cross-draft dialect default,
plain-term glossary reconciliation, and recurring refusals.

## 🧭 Table of contents

- [The rule that decides everything](#-the-rule-that-decides-everything)
- [Why a readability index is a trap](#-why-a-readability-index-is-a-trap)
- [The objective function already exists](#-the-objective-function-already-exists)
- [What is binary, and what only looks it](#-what-is-binary-and-what-only-looks-it)
- [What persists across drafts](#-what-persists-across-drafts)
- [Relationship to #102's roadmap](#-relationship-to-102s-roadmap)

## 🔑 The rule that decides everything

> **R3:** "An unattended item's check is **binary**. No continuous score
> is ever the thing being optimised."
>
> -- [AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md#-the-requirements), which
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

## ⚠ Why a readability index is a trap

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

## 🎯 The objective function already exists

[WRITING-STANDARDS.md](WRITING-STANDARDS.md) is it, and it was written that
way before any of this was contemplated. Its §2 and §4 are not aspirations;
they are conformance rules with a decidable answer.

**The rule-by-rule triage used to live here and no longer does.** It is
[WRITING-STANDARDS.md §9](WRITING-STANDARDS.md#-9-what-is-checked-mechanically-and-what-is-not),
which names for each rule whether it is decidable and whether a machine
may act on it unattended. That move was deliberate: this document is a
proposal, and nothing may be built against a proposal, so the normative
copy belongs in the file whose status is *reference* -- and in one place,
so the two cannot drift into disagreeing about the same rule. What §9
says, in one line: the *top* of that list is genuinely autoresearchable,
and the bottom is a review aid's output for a human.

The apparatus around it, and none of it needs a model:

- **#104, shipped.** The draft's dialect is a `language:` line in the
  dossier's `scope.md` (BCP-47: `en-GB`, `en-IN`, `en-US`), so the target
  is on disk rather than restated in chat each session. That is the
  *recorded target* an unattended pass needs, and it needed no new
  tooling: `draft-reviser` already read `scope.md` before any edit.
- **#103, shipped.** `draft-reviser` has a copy-edit branch -- the
  sanctioned path for a whole-document edit that touches no evidence,
  which the skill had no shape for.
- **#107, open.** `python -m chitragupta.draft style` -- dialect consistency
  against that line, plus §2's banned words -- stdlib-only, exit 0 always,
  a review aid and explicitly never a gate. That is the *detector* and the
  *re-check*. (Re-homed from the `scripts/style_check.py` this document
  first named; `scripts/` holds dev tooling and no layer entry point.)
- **#183, open.** What invokes the detector once it exists, so a prose
  finding arrives without a human remembering to ask for it.

Detector, recorded target, re-check, and a sanctioned edit path -- the
whole loop, and every deterministic part of it costs zero tokens. This is
also why the language half sits on the cheap rungs of
[the cost ladder](AUTO-IMPROVEMENT.md#-the-cost-ladder), and therefore why
it is the half worth building first.

**One caution #104 already records.** §2's list is English literals and
§4's voice rules are an Anglophone convention. A non-English draft needs
them adapted, not transliterated -- so none of this generalises to #108's
multilingual track for free.

## ⚖ What is binary, and what only looks it

Wider than §9, and for a different purpose: §9 is normative over
`WRITING-STANDARDS.md`'s own rules, and this is the inventory of
everything an unattended loop might reach for, most of which that document
never mentions. Where the two overlap, **§9 is the one that governs**; the
rows below restate its verdicts only so the inventory reads as one list.

| Property | Binary? | Unattended? |
|---|---|---|
| Dialect conformance against `scope.md`'s `language:` | yes | yes (#104, #107) |
| §2's defect markers | yes, minus "just" | yes |
| Acronym expanded at first use; term defined once | yes, given the dossier glossary | yes |
| Terminology and notation used consistently | yes, given a registry | yes (#138's detectors) |
| Cross-references resolve | yes | yes (#138) |
| Duplicate or near-duplicate sentences across sections | yes, at a threshold | yes -- `chitragupta/overlap_index.py` already indexes n-grams |
| Reference-list consistency | yes | already deterministic (`chitragupta/references.py`) |
| A section citing nothing at all | yes | surfaced -- the fix is evidence, not wording |
| Sentence length, hedging density, passive-voice ratio | **no -- these are scores** | surfaced only |
| Readability index | **no** | reported, never optimised |
| Whether a paragraph leads with its point | heuristic | surfaced |
| Whether a source supports a claim | no | never -- [why](AUTO-IMPROVEMENT-RATIONALE.md#-why-provenance-is-excluded) |

## 🗄 What persists across drafts

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
  have -- for an ordinary term. #190 built the narrower, acronym-shaped
  slice of this: `[style].acronyms` in `config.toml` gives a user's own
  expansions a per-host home (`content/acronyms.toml`, the same
  gitignored footing as the boilerplate allowlist below), every genre
  skill drafts from it, and `python -m chitragupta.draft style` now reports when
  a draft's own glossary has drifted from it
  (`chitragupta/style_acronym_drift.py`, `draft-reviser`'s acronym-realignment
  mode fixes what that reports). Reconciliation for a plain term --
  "digital twin" spelled three ways with no acronym in sight -- is still
  nothing.
- **The boilerplate allowlist.** #128 built this one already, and not
  quite as first framed here: `content/verbatim_allowlist.toml` is
  per-host, gitignored data, the same footing as `config.toml`, not
  version-controlled. A phrase waved through once still does not get
  re-flagged in the next draft on the *same* host, because the file is
  one per clone rather than one per draft and persists across everything
  that clone drafts. But "auditable" now means "in this host's own
  file,"
  not "visible in the project's git history to every contributor." See
  [PLAGIARISM.md](PLAGIARISM.md#-the-boilerplate-allowlist) for the
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

`python -m chitragupta.draft dossier acronyms-suggest --apply` looks like an
exception and is not one: it writes `content/acronyms.toml` only when a
person at a terminal types `--apply`, for the draft they named, in that
one run. Nothing here runs it on a schedule, inside a revision loop, or
because a threshold was crossed -- the human typing the flag *is* the
acceptance this rule requires, not a bypass of it.

## 🗺 Relationship to #102's roadmap

Issue #102 already sequences the language work as six PRs, ranked by who
is blocked today. Nothing here reorders it; this document adds the reason
the first three matter more than their size suggests.

| #102's PR | What it is | Why it matters here |
|---|---|---|
| #103, shipped | copy-edit mode in `draft-reviser` | the sanctioned edit path -- without it there is nowhere for a prose fix to go |
| #104, shipped | dialect as a first-class draft property | the recorded target |
| #105, #106 | render-language plumbing, localisable references | unrelated to this loop; the non-English track |
| #107 | `python -m chitragupta.draft style` | the detector and the re-check |
| #108 | multilingual corpus support | out of scope, and see the caution above |
| #183 | automatic invocation of the detector | what makes the loop a loop rather than a command someone remembers |

Issue #102 ranks #107 fifth, as "a nice-to-have consistent with the
project's review-aid posture". That ranking is right for a human-driven
workflow and wrong for an unattended one: without #107 there is no binary
check, and
without a binary check the prose class of
[the agenda](AUTO-IMPROVEMENT.md#-item-classes) cannot be acted on at all.
Issue #183 takes that reading and moves #107 ahead of #105 and #106.

**One thing #183 settled that this document left open**: the check is
decidable, so the question of gating it was live. It is not gateable, and
the reason is narrower than "prose is soft" -- the gate is measured
against the ledger, which is ground truth, and a dialect check is measured
against a line someone typed, which can be wrong or stale. See
[ARCHITECTURE.md](ARCHITECTURE.md)'s "Layer 4".

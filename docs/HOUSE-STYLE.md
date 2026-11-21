# ✍ House style: the prose axis, and what persists across drafts

Status: **reference.**

Prose is the axis an unattended loop can improve *best*. This page says
why, what the objective function is, and which of a user's preferences
outlive the draft that prompted them.

**Written for** someone weighing the language-and-style half of
[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md), which owns the loop's
machinery. It assumes [WRITING-STANDARDS.md](WRITING-STANDARDS.md), the
standard being checked against, and [DRAFT-ITERATION.md](DRAFT-ITERATION.md)
for the dossier. Why the line falls where it does is
[AUTO-IMPROVEMENT-RATIONALE.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/AUTO-IMPROVEMENT-RATIONALE.md).

What is built: the sanctioned edit path (`draft-reviser`'s copy-edit
mode), the recorded target (`scope.md`'s `language:` line), the detector
(`python -m chitragupta.draft style`) and its automatic invocation, the
per-host boilerplate allowlist and the per-host acronym vocabulary. What
is open, and covered by no issue, is listed under [What persists across
drafts](#-what-persists-across-drafts).

## 🔑 The rule that decides everything

> **R3:** "An unattended item's check is **binary**. No continuous score
> is ever the thing being optimised."
>
> From [AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md#-the-requirements),
> which owns the wording.

A continuous score invites the loop to optimise the score instead of the
draft. That is why the specification counts findings rather than scoring
quality: a count of binary conformance failures is safe to drive to zero,
and a quality score is not safe to maximise.

Applied to language, the rule cuts the axis in two. "Apply §2" is binary:
"obviously" is present or it is not. "Improve the readability" is not, and
no amount of care in the prompt makes it so.

## ⚠ Why a readability index is a trap

Flesch-Kincaid and its relatives look like the `val_bpb` this pipeline is
missing: one number, cheaply computed, comparable across revisions. They
are functions of sentence length and syllable count. A loop minimising
grade level will split sentences past the point where the argument
survives the break, and will replace precise technical vocabulary with
shorter, vaguer words, because to the metric a polysyllabic term is
indistinguishable from bad writing. The result scores better and reads
worse, and every one of those edits passes its own re-check. That is
Goodhart's law with a specific mechanism.

An index may still be reported: a grade level that moves sharply between
revisions is worth a human's attention. It may never be the thing being
optimised.

## 🎯 The objective function already exists

[WRITING-STANDARDS.md](WRITING-STANDARDS.md) is the objective function.
Its §2 and §4 are conformance rules with a decidable answer. The
rule-by-rule triage is
[WRITING-STANDARDS.md §9](WRITING-STANDARDS.md#-9-what-is-checked-mechanically-and-what-is-not),
which names for each rule whether it is decidable and whether a machine
may act on it unattended. It lives there, in one place, so the two pages
cannot drift into disagreeing about the same rule.

The apparatus around it, none of which needs a model:

- **The recorded dialect.** A `language:` line in the dossier's
  `scope.md` (BCP-47: `en-GB`, `en-IN`, `en-US`) puts the target on disk
  instead of in chat. `draft-reviser` reads `scope.md` before any edit.
- **The copy-edit mode.** `draft-reviser`'s sanctioned path for a
  whole-document edit that touches no evidence.
- **The detector.** `python -m chitragupta.draft style` checks dialect
  consistency, §2's defect markers, §4's and §7's fixed phrases,
  acronyms, table, figure and equation ids and references, and what has
  to fit the page (§9 lists every rule). It always exits 0, and is a
  review aid, never a gate.
- **Automatic invocation.** A `PostToolUse` hook
  (`.claude/hooks/style_check_hook.py`) runs the detector on every write,
  and every drafting and revising skill runs it before presenting.

Every deterministic part of that loop costs zero tokens, which is why the
language half sits on the cheap rungs of
[the cost ladder](AUTO-IMPROVEMENT.md#-the-cost-ladder) and is the half
worth building first.

One caution: §2's list is English literals and §4's voice rules are an
Anglophone convention. A non-English draft needs them adapted, not
transliterated, so none of this generalises to the multilingual track
for free.

## ⚖ What is binary, and what only looks it

This is the inventory of everything an unattended loop might reach for,
most of which `WRITING-STANDARDS.md` never mentions. Where the two
overlap, **§9 is the one that governs**.

| Property | Binary? | Unattended? |
| --- | --- | --- |
| Dialect conformance against `scope.md`'s `language:` | yes | yes when the dialect comes from `scope.md` or `--language`; a person decides when it comes from `config.toml` |
| §2's defect markers other than "just" | yes | yes |
| "just" | no: the adjective ("a just outcome") is correct prose | no; a person decides |
| §4's and §7's fixed phrases: clichés, hype, wordy stock phrases, machine-prose habits, statistics reporting | yes, for a fixed list | no; a person decides |
| Acronym expanded at first use, and matching the vocabulary | yes | yes |
| A plain term defined once and used consistently | yes, given the dossier glossary | not checked |
| Terminology and notation used consistently | yes, given a registry | no: the book-scale `registry check` reports for a person, and no agenda class carries it |
| Cross-references resolve | yes | no for a book's registries (as above); yes for table, figure and equation references inside one draft (`draft style`) |
| Duplicate or near-duplicate sentences across sections | yes, at a threshold | could be, since `chitragupta/overlap_index.py` indexes n-grams; no aid checks it |
| Reference-list consistency | yes | already deterministic (`chitragupta/references.py`) |
| A section citing nothing at all | yes | surfaced; the fix is evidence, not wording |
| Sentence length, hedging density, passive-voice ratio | **no: these are scores** | surfaced only |
| Readability index | **no** | reported, never optimised |
| Whether a paragraph leads with its point | heuristic | surfaced |
| Whether a source supports a claim | no | never ([why](https://github.com/prasadtalasila/chitragupta/blob/main/docs/AUTO-IMPROVEMENT-RATIONALE.md#-why-provenance-is-excluded)) |

## 🗄 What persists across drafts

A user writes many documents over years, and each starts from a blank
slate on everything except the corpus, so their house style is
re-derived or re-stated in chat every time. A preference with "nowhere on
disk to live" silently reverts to the model's default. Four preferences
have that shape; two are reconciled across drafts and two are open:

- **Dialect and house style (open).** The `language:` line is per-draft
  by design, because a thesis at an Indian university and an IEEE
  submission legitimately differ. But a user who has chosen `en-GB` four
  times has a default, and re-choosing it is friction rather than a
  decision.
- **The glossary (acronyms built, plain terms open).** An author writing
  a thesis, a survey and a textbook chapter on one subject should not
  define "digital twin" three ways. `[style].acronyms` in `config.toml`
  gives a user's own expansions a per-host home (`content/acronyms.toml`,
  gitignored like the allowlist below), every genre skill drafts from it,
  `python -m chitragupta.draft style` reports when a draft's glossary has
  drifted from it (`chitragupta/style_acronym_drift.py`), and
  `draft-reviser`'s acronym-realignment mode fixes what that reports. A
  plain term with no acronym still has no reconciliation.
- **The boilerplate allowlist (built).** `content/verbatim_allowlist.toml`
  is per-host, gitignored data on the same footing as `config.toml`. A
  phrase waved through once is not re-flagged in the next draft on the
  *same* host. "Auditable" means "in this host's own file," not "visible
  in the project's git history." See
  [PLAGIARISM.md](PLAGIARISM.md#-the-boilerplate-allowlist).
- **Recurring refusals (open).** A user who declines the same kind of
  source in four drafts has a policy. `rejected.md` records each refusal
  with a reason; nothing reads those reasons across drafts.

The asymmetry between proposing and accepting holds at this level too. In
autoresearch the human edits `program.md` and the agent never does; here
`program.md` is the skills, `docs/WRITING-STANDARDS.md`, and these
standing preferences. A loop that rewrote its own standards from its own
accepted-edit statistics would be a machine revising the terms of its
own supervision. The loop proposes and the human accepts, one level up.

So a cross-draft pass may *report* that `en-GB` was chosen four times out
of four, or that a term is defined three ways, and may offer the edit. It
may not write the preference file itself.
`python -m chitragupta.draft dossier acronyms-suggest --apply` follows
the same rule: it writes `content/acronyms.toml` only when a person at a
terminal types `--apply`, for the draft they named, in that one run, and
never on a schedule, inside a revision loop or because a threshold was
crossed. The human typing the flag *is* the acceptance.

## 🗺 Relationship to the language roadmap

Three of the language roadmap's items serve this loop and are built: the
copy-edit mode, the recorded dialect, and the detector with its automatic
invocation. Without the detector there is no binary check, and without
one the prose class of [the agenda](AUTO-IMPROVEMENT.md#-item-classes)
could not be acted on at all. The render-language items and multilingual
corpus support are unrelated to this loop.

The detector is decidable but not a gate, for a narrower reason than
"prose is soft": the gate is measured against the ledger, which is ground
truth, and a dialect check against a line someone typed, which can be
wrong or stale. See [ARCHITECTURE.md](ARCHITECTURE.md)'s "Layer 4".

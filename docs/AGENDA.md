# 🗺 The agenda file, section by section

Status: **reference.** Written 2026-09-15.

**Written for** anyone reading an agenda report for the first time and
wanting to know what each part of it means before acting on any of it.
**Assumed:** nothing. **Not covered here:** the flags
([CLI.md](CLI.md#-chitragupta-review-agenda)), what each individual aid
measures ([REVIEW.md](REVIEW.md)), and the unattended-repair loop's
design ([AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)).

An agenda is **one ranked, deduplicated worklist merged across every
other review aid**, so you read one document instead of nine. Produce
one with:

```bash
chitragupta review agenda content/drafts/dt/survey.md
```

It writes `content/review/dt/survey.agenda.md` and a `.json` sibling,
mirroring the draft's own path.

**It is a review aid, not a gate.** It exits 0 whatever it finds, blocks
nothing, and takes no lock. Nothing in it can stop a draft being
rendered, submitted or read.

## 🧭 Table of contents

- [The one thing to know before reading one](#-the-one-thing-to-know-before-reading-one)
- [A complete agenda](#-a-complete-agenda)
- [Section by section](#-section-by-section)
- [The item line](#-the-item-line)
- [The classes](#-the-classes)
- [Unattended versus surfaced](#-unattended-versus-surfaced)
- [Two sections that appear only sometimes](#-two-sections-that-appear-only-sometimes)
- [The JSON sibling](#-the-json-sibling)
- [Acting on an agenda](#-acting-on-an-agenda)

## ⚠ The one thing to know before reading one

**The agenda reads the other aids' filed JSON. It does not run them.**

An aid whose report has never been written is listed as absent in
`## Sources`, not computed on the fly. So the usual sequence is: run the
aids you want with `--write`, then run the agenda.

```bash
chitragupta review verbatim scan content/drafts/dt/survey.md --write
chitragupta review uncited content/drafts/dt/survey.md --write
chitragupta review support content/drafts/dt/survey.md --write
chitragupta review agenda content/drafts/dt/survey.md
```

There is exactly one exception, `--baseline`, which re-runs the aids
itself -- see [Acting on an agenda](#-acting-on-an-agenda).

## 📄 A complete agenda

This is the whole file, from a real run over the sample project's survey
([the committed original](examples/sample-project/content/review/dt-overview/survey.agenda.md)),
abridged only by dropping repeated item lines. Its `Command:` line is
quoted exactly as the committed report records it, in the module form --
`chitragupta review agenda <draft>` is the same command and is what this
documentation uses everywhere else:

```markdown
# Agenda: content/drafts/dt-overview/survey.md

> **Review aid, not a gate.** This report is evidence for a human
> judgement, never a verdict. A driver may read it back; no draft is
> blocked by what it says. See SOUL.md, and docs/ARCHITECTURE.md's
> "Layer 4: the review layer".

- Draft: `content/drafts/dt-overview/survey.md`
- Command: `python -m chitragupta.review agenda content/drafts/dt-overview/survey.md`
- chitragupta 6.61.7

## How to read this

This is a **review aid, not a gate**: every item below is evidence
for a human judgement, ranked by class and then severity, never a
verdict. `unattended` items are ones a future `agenda-reviser` may
act on without asking first; every other item is surfaced for a
person to decide.

## Sources

- Citation provenance: read
- Verbatim scan: read
- Citation coverage: read
- Multi-source synthesis: read, no item class defined
- TikZ layout check: not run
- Uncited prose: read
- Quotation integrity: read
- Claim support: read
- Prose (style_check): read
- Dossier drift: read

## Summary

- 11 verbatim-run
- 8 unsupported-claim
- 8 uncited-claim

## Findings

### verbatim-run

- `6bdcbebedc51` [unattended] (1. Introduction): 13-word verbatim run
  citing `sample_dt_overview_2024`
- `91bce1eac368` [unattended] (2. Keeping the twin true): 13-word
  verbatim run citing `sample_dt_factory_2022`, 5 matched

### unsupported-claim

- `401e348db58b` [surfaced] (6. Conclusion):
  `[@sample_dt_factory_2022]` scores no support found: Across the sample
  corpus, the recurring finding is that twins succeed on honesty
- `289df3c9be7c` [surfaced] (5. Gaps): `[@sample_dt_overview_2024]`
  scores weak: Fidelity is argued to be purchased "decision by
  decision", yet no paper offers a

### uncited-claim

- `89452ab2d5ad` [surfaced] (2. Keeping the twin true): A twin is only
  as trustworthy as its last synchronisation.
- `13645296d189` [surfaced] (5. Gaps): Three gaps stand out.
```

## 🔍 Section by section

| Section | What it is | What to do with it |
| --- | --- | --- |
| `# Agenda: <draft>` | the heading, naming the draft this is about | check it is the draft you meant -- an agenda for a stale path is the commonest confusion |
| The `>` notice | the review-layer contract, repeated in every aid's report | it is there because a file outlives the session that made it; a reader months later must not mistake it for a verdict |
| `- Draft:` / `- Command:` / `- chitragupta <version>` | provenance: what was read, by what command, at what version | re-run the `Command:` line verbatim to reproduce the report |
| `## How to read this` | the same contract in prose, plus the `unattended` rule | read once; it is identical in every agenda |
| `## Sources` | one line per aid, saying whether its report was **read**, **not run**, or read but contributing no items | **read this before the findings.** A short agenda with four aids "not run" is not a clean draft |
| `## Summary` | counts per class, worst class first | tells you the shape of the work before you read a single item |
| `## Findings` | the items themselves, grouped by class, ranked by class then severity | the worklist |

**`## Sources` is the section people skip and should not.** Three
different things can appear there:

- **read** -- the aid's report was found and merged.
- **not run** -- no report exists. Nothing from that aid is in this
  agenda, and its absence is not evidence of anything.
- **read, no item class defined** -- the aid ran and was read, but its
  findings do not map to an agenda class. `synthesis` is the standing
  example: it is reported for a human, and deliberately contributes no
  worklist item.

## 📌 The item line

Every finding is one line with four parts:

```text
- `289df3c9be7c` [surfaced] (5. Gaps): `[@sample_dt_overview_2024]` scores weak: Fidelity is argued to be ...
   └─ id         └─ disposition └─ section anchor  └─ summary
```

| Part | Meaning |
| --- | --- |
| **id** (`289df3c9be7c`) | a stable 12-character handle for this finding. It is what `--accept` takes, and what a repair skill uses to look the finding's full payload up in the raising aid's own JSON |
| **disposition** | `[unattended]` or `[surfaced]` -- see below |
| **section anchor** | which heading of the draft the finding sits under, so you can go straight there. Absent for a finding that is not about one section |
| **summary** | one line of what was found. Deliberately thin: the full payload lives in the raising aid's own report, keyed by the id |

The id is stable while the finding's identity is unchanged. Edit the
sentence and it becomes a different finding with a different id -- which
is exactly what makes `--accept` safe: an acceptance cannot silently
carry over to text you have since rewritten.

## 🏷 The classes

| Class | Raised by | Means |
| --- | --- | --- |
| `verbatim-run` | verbatim scan | a run of words the draft shares with a parsed source |
| `unsupported-claim` | citation provenance | the cited source does not lexically support the claim citing it (`no support found` / `weak`) |
| `claim-support` | claim support | the same question asked by an entailment model, ranked rather than banded |
| `uncited-claim` | uncited prose | a sentence that reads as a factual claim with no citation |
| `misquoted` | quotation integrity | a quoted span that does not match the source it cites |
| `missing-citekey` | dossier drift | the draft cites a citekey the corpus no longer holds |
| `recorded-but-uncited` | dossier drift | `evidence.md` keeps a source the draft cites nowhere |
| `prose` | `draft style` | a defect marker, an unexpanded acronym, or dialect drift against `scope.md` |

## ⚖ Unattended versus surfaced

This is the distinction the whole file is organised around.

| | Meaning | Classes |
| --- | --- | --- |
| `[unattended]` | mechanically re-checkable: a future automated pass may repair it **without asking first** | `prose`, `verbatim-run` at severity `short`, `missing-citekey` |
| `[surfaced]` | a judgement about meaning that only a person can make | `unsupported-claim`, `claim-support`, `uncited-claim`, `recorded-but-uncited`, `misquoted` |

The line is not "easy versus hard". It is **"is the repair verifiable by
re-running a check?"** A defect marker either is or is not still in the
sentence. Whether a source really supports a claim is not settled by any
re-run, so no loop may close it on your behalf.

One class repays a closer look: a `missing-citekey` is unattended, but
its repair is to **de-cite the sentence** -- which then surfaces as an
`uncited-claim` on the next agenda, for you. Nothing is quietly resolved;
the problem is moved to the column where a person decides.

## 🔁 Two sections that appear only sometimes

**`## Refused as stale`.** An item whose exact draft text has changed
since the aid found it is dropped from the worklist and listed here
instead, with its id, class, section, summary and the reason. It is a
refusal, not a failure: repairing a finding against text that no longer
exists is worse than not repairing it. Refused items are not counted in
the objective, and the finding is re-derived on the next run against the
current text.

This is different from an aid marked `stale` in `## Sources`, which is
an mtime comparison saying a whole report predates the draft.

**Accepted items.** An item you have considered and decided stands is
recorded, and is then absent from the worklist while the finding's
identity is unchanged:

```bash
chitragupta review agenda content/drafts/dt/survey.md --accept 289df3c9be7c
```

Only `claim-support`, `uncited-claim` and `unsupported-claim` may be
accepted. Every other class is refused with **exit code 2** -- you cannot
accept away a misquotation or a missing citekey.

## 🧾 The JSON sibling

The `.json` is an additional serialisation of exactly what the Markdown
prints, never a second computation. It carries the envelope every aid's
JSON carries, plus:

| Key | What it holds |
| --- | --- |
| `sources` | per aid: `available` and `stale`; the prose check adds `partial`; dossier drift adds `corpus_available`; the acceptance record adds `count` |
| `items` | one object per worklist entry: `id`, `class`, `section`, `citekey`, `line`, `unattended`, `summary`, and a `detail` object whose shape is specific to the class |
| `objective_class_count` | how many `unattended` items this agenda holds -- what a repair loop watches fall |
| `pass_bound` | the backstop on how many repair passes may be taken |
| `stale_spans` | what this run refused as stale |
| `accepted` | each stored acceptance, with a `suppressed` flag saying whether this run's worklist was shorter for it |

`objective_class_count` and `pass_bound` are carried **as data** rather
than as constants in a skill's prose, because a skill cannot import a
Python constant and a hardcoded number goes stale silently.

One item, in full:

```json
{
  "id": "6bdcbebedc51",
  "class": "verbatim-run",
  "section": "1. Introduction",
  "citekey": "sample_dt_overview_2024",
  "line": 7,
  "unattended": true,
  "summary": "13-word verbatim run citing `sample_dt_overview_2024`",
  "detail": {
    "severity": "short",
    "verbatim_id": "de3edb3b5268"
  }
}
```

Note `detail.verbatim_id`: the agenda's own detail is **thin by design**.
The full repair payload lives in the raising aid's report
(`survey.verbatim.json` here), keyed by that id. A tool acting on an item
looks it up there rather than expecting the agenda to carry everything.

## 🛠 Acting on an agenda

**Read `## Sources` first**, then `## Summary`, then the `[surfaced]`
items -- those are the ones needing your judgement and the ones a machine
will never close for you.

**Hand the `[unattended]` ones off.** Ask to "work the review agenda"
and `agenda-reviser` repairs them one at a time, re-running
`chitragupta draft gate` and a baseline recheck after each, and logging
every attempt -- refusals and reverts included -- in the dossier's
`revisions.md`.

**Check that a round of edits actually helped:**

```bash
chitragupta review agenda content/drafts/dt/survey.md \
    --baseline content/review/dt/survey.agenda.json
```

This is the one mode that re-runs the aids (at `--formats md`, so each
aid's `.tex`/`.pdf` goes stale against its `.md` until a full-format run
follows). It reports every finding as `resolved`, `persisting`, `new` or
`accepted`, with `objective_before`, `objective_after` and
`objective_delta`.

**Read the `new` list, not just the delta.** A repair that resolves one
finding and introduces another leaves `objective_delta` at 0, which is
indistinguishable from having changed nothing unless you look at what is
in `new`.

Under `--baseline --json`, stdout carries the comparison payload and no
`items` key at all; the worklist still lands in the filed `.json` report
as usual.

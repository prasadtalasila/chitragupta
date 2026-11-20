# 🗺 The agenda file, section by section

Status: **reference.**

**Written for** anyone reading an agenda report for the first time.
**Assumed:** nothing. **Not covered here:** the flags
([CLI.md](CLI.md#-chitragupta-review-agenda)), what each individual aid
measures ([REVIEW.md](REVIEW.md)), and the unattended-repair loop's
design ([AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)).

An agenda is one ranked, deduplicated worklist merged from eight review
aids: every aid except itself, `union` (which reads a book) and
`digest` (whose classes describe a verbatim digest only; for the same
reason `agenda-reviser` must never run on a digest, where its
`verbatim-run` repair would paraphrase the whole text,
[VERBATIM-DIGEST.md](VERBATIM-DIGEST.md)).

```bash
chitragupta review agenda content/drafts/dt/survey.md
```

This writes `content/review/dt/survey.agenda.md` and a `.json` sibling,
mirroring the draft's path. **It is a review aid, not a gate:** it exits
0 whatever it finds, blocks nothing and takes no lock.

## ⚠ The one thing to know before reading one

**The agenda reads the other aids' filed JSON. It does not run them.**

An aid with no written report is listed as absent in `## Sources`, so
run the aids you want with `--write` first:

```bash
chitragupta review verbatim scan content/drafts/dt/survey.md --write
chitragupta review uncited content/drafts/dt/survey.md --write
chitragupta review support content/drafts/dt/survey.md --write
chitragupta review agenda content/drafts/dt/survey.md
```

Only `--baseline` re-runs the aids
([Acting on an agenda](#-acting-on-an-agenda)).

## 📄 A complete agenda

A real run over the sample project's survey
([the committed original](examples/sample-project/content/review/dt-overview/survey.agenda.md)),
with repeated item lines dropped. Its `Command:` uses the module form of
`chitragupta review agenda <draft>`:

```markdown
# Agenda: content/drafts/dt-overview/survey.md

> **Review aid, not a gate.** This report is evidence for a human
> judgement, never a verdict. A driver may read it back; no draft is
> blocked by what it says. See SOUL.md, and docs/ARCHITECTURE.md's
> "Layer 4: the review layer".

- Draft: `content/drafts/dt-overview/survey.md`
- Command: `python -m chitragupta.review agenda content/drafts/dt-overview/survey.md`
- chitragupta 6.166.1

## How to read this

This is a **review aid, not a gate**: every item below is evidence
for a human judgement, ranked by class and then severity, never a
verdict. `unattended` items are ones `agenda-reviser` may
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
- Recorded-but-uncited citekeys: read
- Accepted items: none recorded for this draft

## Summary

- 11 verbatim-run
- 8 unsupported-claim
- 8 uncited-claim

## Findings

### verbatim-run

- `6bdcbebedc51` [unattended] (1. Introduction): 13-word verbatim run
  citing `sample_dt_overview_2024`

    *source p.1, draft line 7, paragraph 3*

    > a digital model exchanges data with its physical counterpart only through manual steps

- `91bce1eac368` [unattended] (2. Keeping the twin true): 13-word
  skip-gram match citing `sample_dt_factory_2022`, 5 matched

    *source p.1, draft line 37, paragraph 7*

    > **draft** -- **showing** supervisors agreeing with the twin in over ninety five percent **of cases**

    > **source** -- **showed** supervisors agreeing with the twin’*s choice* in over ninety-five percent


### unsupported-claim

- `289df3c9be7c` [surfaced] (5. Gaps): `[@sample_dt_overview_2024]`
  scores weak: Fidelity is argued to be purchased "decision by
  decision", yet no paper offers a

### uncited-claim

- `13645296d189` [surfaced] (5. Gaps): Three gaps stand out.
```

## 🔍 Section by section

| Section | What it is | What to do with it |
| --- | --- | --- |
| `# Agenda: <draft>` | the draft | check it is the one you meant; a stale path is the commonest confusion |
| The `>` notice | the review-layer contract | there so a later reader does not take the file for a verdict |
| `- Draft:` / `- Command:` / `- chitragupta <version>` | provenance | re-run the `Command:` line to reproduce the report |
| `## How to read this` | the same contract, plus the `unattended` rule | identical in every agenda |
| `## Sources` | per input (each aid, the prose check, dossier drift, recorded-but-uncited citekeys, the acceptance record): whether it was read, and its state | **read this before the findings.** A short agenda with four aids "not run" is not a clean draft |
| `## Summary` | counts per class, worst first | the shape of the work |
| `## Findings` | the items, grouped and ranked by class then severity | the worklist |

An aid's line in `## Sources` says one of:

- **read**: its report was found and merged.
- **not run**: no report exists; its absence is not evidence of
  anything.
- **read, no item class defined**: its findings map to no agenda class.
  `synthesis` and `figure` are for a human and deliberately add no item.
- **read, nothing checked**: the quotation aid had no dossier, or no
  quote the draft cites.
- **stale**: the report is older than the draft. Re-run that aid.
- **not refreshed**: under `--baseline`, its refresh failed, so its
  findings are an earlier run's and are not counted.

The prose check is **partial** without `vale` on `PATH`. Dossier drift
and recorded-but-uncited citekeys are **not available** without a
dossier, and drift is read without the ledger when the corpus is
unavailable. The accepted items line gives the count of acceptances,
or says the record is **unreadable**, in which case nothing is
suppressed.

## 📌 The item line

Every finding is one line with four parts:

```text
- `289df3c9be7c` [surfaced] (5. Gaps): `[@sample_dt_overview_2024]` scores weak: Fidelity is argued to be ...
   └─ id         └─ disposition └─ section anchor  └─ summary
```

| Part | Meaning |
| --- | --- |
| **id** (`289df3c9be7c`) | a stable 12-character handle: what `--accept` takes, and the key to the full payload in the raising aid's JSON |
| **disposition** | `[unattended]` or `[surfaced]`; see below |
| **section anchor** | the draft heading the finding sits under; absent if it concerns no one section |
| **summary** | one deliberately thin line; the full payload is in the raising aid's report |

A `verbatim-run` line is followed by its excerpt: its place in source
and draft, then the copied words. A skip-gram match shows both sides
with the differing words marked ([the example](#-a-complete-agenda)
has one of each). The id is stable while the finding's identity is.
Edit the sentence and it gets a new id, so an acceptance cannot carry
over to rewritten text.

## 🏷 The classes

In rank order; within a class, items rank by severity.

| Class | Raised by | Means |
| --- | --- | --- |
| `missing-citekey` | dossier drift | the draft cites a citekey the corpus does not hold |
| `recorded-but-uncited` | dossier | `evidence.md` or `sections.md` records a source the draft cites nowhere |
| `verbatim-run` | verbatim scan | a run of words the draft shares with a parsed source |
| `prose` | `draft style` | a defect marker, an unexpanded acronym, or dialect drift against `scope.md` |
| `unsupported-claim` | citation provenance | the cited source does not lexically support the claim citing it (`no support found` / `weak`) |
| `claim-support` | claim support | the same question asked by an entailment model, ranked rather than banded |
| `uncited-claim` | uncited prose | a sentence that reads as a factual claim with no citation |
| `misquoted` | quotation integrity | a quoted span that does not match the source it cites |

[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md#-item-classes) gives the
reason behind each class's disposition.

## ⚖ Unattended versus surfaced

| | Meaning | Classes |
| --- | --- | --- |
| `[unattended]` | mechanically re-checkable: an automated pass may repair it **without asking first** | `prose`, except findings marked `repair: "review"` (`WideCodeLine`, `AcronymCase`, a `BareCitekey` set as code or naming a key with no parsed PDF, and dialect findings when the dialect came from `config.toml` or the match starts with a capital); `verbatim-run` at severity `short` from the `exact` or `skip-gram` tier (an `embedding`-tier run, or one marked `names`, mostly proper names, is surfaced); `missing-citekey` |
| `[surfaced]` | a judgement about meaning only a person can make | `unsupported-claim`, `claim-support`, `uncited-claim`, `recorded-but-uncited`, `misquoted` |

The line is whether a re-run of a check can verify the repair, not
whether it is easy. A defect marker is or is not still in the sentence;
whether a source supports a claim is settled by no re-run, so no loop
may close it for you.

A `missing-citekey` is unattended, but its repair is to **de-cite the
sentence**, which surfaces as an `uncited-claim` on the next agenda for
you to decide. The `missing-citekey` item, and the
`recorded-but-uncited` item the removed marker leaves, persist while
`evidence.md` or `sections.md` hold the key. The author clears them
with `dossier prune` for an `evidence.md` block, or `dossier sections
--citekeys --write` for a key only in `sections.md`, which `prune`
refuses.

## 🔁 Two sections that appear only sometimes

**`## Refused as stale`.** An item whose draft text has changed since
the aid found it is listed here (id, class, section, summary, reason)
instead of in the worklist, because repairing text that no longer
exists is worse than not repairing it. It is not counted in the
objective and is re-derived on the next run. An aid marked `stale` in
`## Sources` is different: an mtime check that a whole report predates
the draft.

**Accepted items.** An item you decide stands is recorded, and is
absent from the worklist while the finding's identity is unchanged:

```bash
chitragupta review agenda content/drafts/dt/survey.md --accept 289df3c9be7c
```

Only `claim-support`, `uncited-claim` and `unsupported-claim` may be
accepted. Any other class exits **2**, so you cannot accept away a
misquotation or a missing citekey.

## 🧾 The JSON sibling

The `.json` serialises exactly what the Markdown prints, never a second
computation: every aid's envelope, plus:

| Key | What it holds |
| --- | --- |
| `sources` | per aid: `available` and `stale`; the prose check adds `partial`; dossier drift adds `corpus_available`; the acceptance record adds `count` |
| `items` | per entry: `id`, `class`, `section`, `citekey`, `line`, `unattended`, `summary`, and a class-specific `detail` object |
| `objective_class_count` | how many `unattended` items there are; a repair loop watches it fall |
| `pass_bound` | the backstop on repair passes |
| `stale_spans` | what this run refused as stale |
| `accepted` | each stored acceptance, with a `suppressed` flag for whether it shortened this worklist |

The count and bound are data, not constants in a skill's prose, because
a skill cannot import a Python constant and a hardcoded number goes
stale silently. One item:

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

The detail is thin by design: the full repair payload is in the raising
aid's report (`survey.verbatim.json`), keyed by `detail.verbatim_id`.

## 🛠 Acting on an agenda

Read `## Sources`, then `## Summary`, then the `[surfaced]` items,
which need your judgement. To hand off the `[unattended]` ones, ask to
"work the review agenda": `agenda-reviser` repairs them one at a time,
re-running `chitragupta draft gate` and a baseline recheck after each,
and logs every attempt (refusals and reverts included) in
`revisions.md`. To check that a round of edits helped:

```bash
chitragupta review agenda content/drafts/dt/survey.md \
    --baseline content/review/dt/survey.agenda.json
```

This re-runs the aids (at `--formats md`, so their `.tex`/`.pdf` go
stale until a full-format run) and reports each finding as `resolved`,
`persisting`, `new` or `accepted`, with `objective_before`,
`objective_after` and `objective_delta`. Without a synced ledger it
says to run `chitragupta corpus sync` and exits 1, changing nothing;
plain `review agenda` needs no ledger.

Read `not_refreshed` first: the aids whose refresh failed (a refusal,
an exit 0 that wrote nothing, as `support` does without the enrich
stack, or an exception). Their `.json` is an earlier run's, so their
items are left out of all four groups and both counts, on both sides,
and the filed report marks them `refreshed: false` under `sources.aids`
and **not refreshed** in its header. A driver must stop or surface such
an aid, never count its missing items as progress; `verbatim` matters
most, being the only aid with unattended items. An aid that raised does
not stop the run: `refresh_errors` (and
`sources.aids.<aid>.refresh_error`) gives the exception's one-line
reason.

Read `objective_new` too: a repair that resolves one finding and adds
another leaves `objective_delta` at 0, but `objective_new` (the
unattended items in `new`) shows 1, as in `3 -> 3 (+0), 1 new`. Under
`--baseline --json`, stdout carries the comparison payload with no
`items` key; the worklist still lands in the filed `.json`.

---
name: agenda-reviser
description: Repairs the unattended findings on a draft's review agenda, one item at a time, in a draft that already exists in content/drafts/. Reads `python -m chitragupta.review agenda <draft>`, whose per-item `unattended` field -- never re-derived here -- decides what may be acted on without asking: a `verbatim-run` at severity `short`, every `prose` finding, and a `missing-citekey` (repaired by de-citing the sentence, which escalates it as an uncited claim on the next agenda). Every other class is surfaced for a person to decide. Looks up each item's repair payload in the raising aid's own filed JSON, keyed by the id `detail` carries -- the agenda's own `detail` is thin by design and does not carry it. One R4 cycle is one command, `review agenda <draft> --baseline <stem>.agenda.json --json`, which refreshes all eight aids itself; the skill never hand-rolls the refresh and never reads a bare `review agenda` after an edit. Continues passing only while `objective_class_count`, read from the payload rather than hardcoded, strictly falls, and stops at `pass_bound` (also read from the payload) as a backstop against a miscounting bug. Every repair must re-pass `python -m chitragupta.draft gate` and the same `--baseline` recheck before it is kept, and every attempt is logged in the dossier's revisions.md, refusals and reverts included. Triggers when the user asks to work the review agenda, fix what an agenda run found, or act on unattended findings -- and on the three occasions that raise the question: before rendering or submitting, after a sync moved the corpus, and on picking a draft back up after weeks away. Anything the agenda surfaces rather than marks unattended is a judgement call for draft-reviser or the human, not this skill; hand off and say so. Never edits the allowlist (now including assets/vale/styles/chitragupta/*.yml), never adds a claim, never fabricates a citekey, and never runs unless a person asked for it.
tags: [revision, review, agenda, dossier, citation]
---

# agenda-reviser

`python -m chitragupta.review agenda <draft>` merges every review aid's own report
-- provenance, verbatim, coverage, synthesis, figure layout, uncited prose,
quotation integrity, claim support -- plus the dossier's own drift, into one
ranked, deduplicated worklist. Each item carries an `unattended` field,
decided once by the aid that produced it and never re-derived here: a
`verbatim-run` at severity `short`, every `prose` finding, and a
`missing-citekey` may be repaired without asking; everything else is
surfaced for a person. The agenda stops there, because it is a review aid
and review aids report. Everything after that -- reading an unattended
item, finding its repair payload, applying it without losing the claim,
checking the repair did not make something else worse -- was left to a
person. That is the tedious half, and the half that gets skipped.

That scan runs two deterministic tiers -- exact and word-swap-tolerant
skip-gram -- plus an embedding tier that only runs where the optional
enrichment layer, the Docling sidecars and the draft's own dossier are
all present, and that only ever compares a section against the sources
that section already cites. So **genuine restatement is only detected
where the embedding tier can run**, and even there not from a source the
section never cited -- while these drafts are LLM-written, which makes
literal paraphrase the *likely* reuse mode rather than an edge case. The
scan names the tiers that did not run; read that line. An empty findings
list is not an achievement, and repairing every finding is not a clean
bill of health. Say so when you present, every time.

This skill does the half that was left over. It is not a better agenda
and it does not decide anything the agenda was careful not to decide --
`unattended` is read, never recomputed. What it adds is the repair, the
`--baseline` recheck that says whether the repair worked, and a written
record of both.

**A finding is not a verdict.** A run of shared wording is a place to
look. A defined term, a standard's name and a correctly attributed
quotation all show up as findings, and rewriting one of those would make
the draft worse. Read `docs/PLAGIARISM.md` before deciding that a finding
is a defect.

## When to invoke

| Situation | Action |
| --- | --- |
| User asks to work the review agenda, fix an unattended finding, or clean up what an agenda run found | Invoke this skill |
| An agenda was just run and the user asks "what do I do about these" | Invoke this skill |
| The user wants the draft's agenda **run** but says nothing about fixing it | Run `review agenda <draft>` and show them. Do not start repairing |
| The finding is real but the user disagrees that it needs changing | They are right by default -- record it and move on. `SOUL.md`: a machine does not outrank a person on a judgment call |
| Any other change to an existing draft -- shorten, expand, restructure, re-ground | Use `draft-reviser` |
| User asks to re-check the whole draft against the corpus | Use `corpus-reviser` |
| User asks for a **new** draft | Use the matching genre skill |
| The draft has no dossier | Bootstrap one as `draft-reviser` describes, then continue here. `revisions.md` is where this skill's record goes, so it has to exist |
| The ledger is empty or absent | Stop and say so. A repair that converts a lift into a quotation needs a citekey the gate will accept |

**Read-only over the corpus layer.** Never run `python -m chitragupta.corpus
sync` and never run `python -m chitragupta.enrich`; both take the pipeline's
write lock and are the user's to run.

## What may be repaired unattended, and what may not

Every agenda item carries its own `unattended` field. That field is the
line, decided once by the aid that produced the item -- **this skill
never re-derives it from `class` or from anything else in the item.**
Three classes carry `unattended: true` on this checkout:

| Class | What it is | This skill |
| --- | --- | --- |
| `verbatim-run`, severity `short` | Under 15 words of borrowed wording, not a marked quotation | Repair unattended |
| `verbatim-run`, severity `long` | 15 words or more, not a marked quotation | **Stop and ask** -- surfaced, not unattended |
| `verbatim-run`, `quoted` | Touching quote marks **and** citing the source | Already correct. Do not touch it |
| `prose` | A `draft style` finding -- an unexpanded acronym, a drifted glossary term, a dialect slip, an uncaptioned table or figure | Repair unattended |
| `missing-citekey` | A citekey the draft cites that the corpus no longer has | Repair unattended -- by removing the `[@citekey]` marker, per "Repair a `missing-citekey` item" below |
| Every other class (`unsupported-claim`, `claim-support`, `uncited-source`, `uncited-claim`, `misquoted`, `candidate`) | Judgement calls | Surfaced. Report and do not touch |

**The agenda's own `detail` field is thin by design and is not the repair
payload.** A `verbatim-run` item's `detail` carries `verbatim_id`, not
the `draft_text` an `Edit`'s `old_string` needs. **Look the id up in the
raising aid's own filed JSON** instead:

| Class | `detail` key | Look it up in |
| --- | --- | --- |
| `verbatim-run` | `verbatim_id` | `content/review/<topic>/<stem>.verbatim.json`'s `findings`, matched on `id` -- gives `draft_text`, `min_run`, `citekey`, page range |
| `prose` | (none needed) | The item's own `summary`/`detail.message` names the rule and the match; `draft style content/drafts/<path>` reproduces the full finding if more context is needed |
| `missing-citekey` | (none needed) | The item's own `citekey` and `section` are the whole repair payload -- there is nothing else to look up |

A long `verbatim-run` is still where the choice actually matters, for the
same reason it always did: paraphrasing a sentence the field states one
particular way makes the prose worse to no benefit, and quoting a passage
that was never meant to be quoted pads the draft. That is an authorial
decision, asked rather than taken.

## The loop

Follow `.claude/skills/draft-reviser/SKILL.md`'s `## The loop` for the
parts this skill does not restate -- reading `scope.md` and `steering.md`
first, mapping a change onto sections, editing with `Edit` rather than
`Write`, and writing the dossier back. Read that file; do not reconstruct
it from memory.

### 1. Snapshot, and mark the revision

Before the first edit:

```bash
python -m chitragupta.draft dossier export <name>
python -m chitragupta.draft dossier mark-revision content/drafts/<path> --label "agenda remediation"
```

`<name>` is the draft's path under `content/drafts/` with the suffix
dropped -- `dt-for-engineers/survey`, not the full path and not the bare
stem. `python -m chitragupta.draft dossier list` prints the names it will match.

The export is the way back if the pass as a whole turns out wrong. The
marker is what lets `dossier status` attribute this session's cost
separately from the drafting run's.

Then read `scope.md` and `steering.md`. A rewrite is still a rewrite: the
reader is already fixed, and so is the terminology.

### 2. Take the baseline agenda

```bash
python -m chitragupta.review agenda content/drafts/<path> --json
```

Unlike `verbatim scan`, `agenda` has no `--write` flag: the `.md`/`.json`
report is filed unconditionally on every run, `--json` only decides what
prints to stdout. This files the payload at
`content/review/<topic>/<stem>.agenda.json`.

Read `pass_bound` and `objective_class_count` off it now -- both are
carried precisely so a skill never hardcodes them (`pass_bound` lives
only as a Python constant, `objective_class_count` only as a property,
and neither serialises anywhere a `SKILL.md` could import it). This is
the file every later `--baseline` in this pass points at, and the
closing report is stated against it, not against a re-scan taken later.

If the agenda reports no unattended items, say so and stop. There is
nothing here for this skill to do -- report the surfaced items and hand
off, same as ever.

Take a fresh one at the start of every pass. `agenda` reads the eight
aids' `.json` off disk and marks a report older than the draft as stale
via an mtime comparison, so an existing payload may already predate the
draft's last edit.

### 3. Triage

Read the baseline agenda's `items`. Group by `class`, then by
`unattended`. Tell the user the counts before you start editing: how
many of each unattended class will be repaired, how many surfaced items
exist (report, do not touch), and `objective_class_count`/`pass_bound`
from the payload. Work `missing-citekey` and `prose` first -- both are
single-field lookups with no external payload to fetch -- then
`verbatim-run` at `short`, collecting any `long` ones into one question
rather than interrupting per finding.

### 4. Repair one item

Read only the section that owns it -- `python -m chitragupta.draft dossier
sections content/drafts/<path>` gives the line ranges. Keep the pre-edit
text; step 5 needs it if the repair is rejected.

**Repair a `missing-citekey` item.** The only unattended repair available
is a deletion: this skill may not run `corpus sync` (the user's write
lock) and may not fabricate a citekey. Remove the `[@citekey]` marker with
`Edit`, leaving the sentence standing -- never delete the sentence itself.
**Also drop the citekey from `evidence.md`** (and from `sections.md`'s row
for the section, on the next `dossier sections --citekeys --write`) --
`missing-citekey` is detected off the dossier's own record of what it
cites, not off the draft's live markers, so a repair that only edits the
draft leaves the item unresolved on the next agenda. This is the "writing
the dossier back" half of `draft-reviser`'s loop, referenced above, made
explicit here because it is easy to miss for this one class. The now-
uncited claim becomes an `uncited-claim` item on the next agenda, a
**surfaced** class, so it is reported rather than silently dropped. Where
the sentence carries another surviving citation, only the marker for the
missing one goes, and `evidence.md` keeps that citekey's entry.

**Repair a `prose` item.** Apply the fix `draft style`'s rule names: expand
an acronym at first use, add the `<!-- table: -->` or `<!-- figureref: -->`
marker a `TableNoCaption`/`FigureNoCaption`/`FigureUnreferenced` finding
names, correct a glossary term drifted from `scope.md`'s vocabulary, fix
a dialect slip against `scope.md`'s `language:` line. `Edit` the exact
span `detail.message` or the item's `summary` names.

**Repair a `verbatim-run` item at severity `short`.** Look up
`detail.verbatim_id` in `content/review/<topic>/<stem>.verbatim.json`'s
`findings` for `draft_text`, the exact passage including casing,
punctuation and any mid-run citation marker -- use it as `Edit`'s
`old_string`. If it does not match, the draft almost certainly has CRLF
line endings and the run spans a line break: the payload carries the
`\n` the file was read with, not the `\r\n` on disk. Re-read the line and
edit it by hand rather than widening the search.

**Paraphrase** -- the default, and the only option for a `short` run:

- Preserve the claim. This is a rewording, not a retraction.
- Preserve the citation.
- Leave no run of `min_run` consecutive source words (the looked-up
  finding's own field).
- Prefer the smaller diff.

A `long` verbatim-run is surfaced, not unattended -- it is never repaired
here without the human first choosing paraphrase or quotation, same as
before. **Never add a claim** on any of these three classes: every repair
is a rewording, an attribution, a marker removal or a caption addition,
never new ground.

### 5. Accept or revert

After every repair, one command does the whole R4 cycle -- it refreshes
all eight aids itself, so **never hand-roll this as a bare `review agenda`
read**: that reads the pre-edit aid `.json` still on disk and reports a
finding resolved that is not.

```bash
python -m chitragupta.review agenda content/drafts/<path> \
    --baseline content/review/<topic>/<stem>.agenda.json --json
```

Accept the repair only if **all** of:

- `python -m chitragupta.draft gate content/drafts/<path>` exits 0;
- the item's `id` appears in the comparison's `resolved`;
- `objective_delta` is not positive -- **this now couples classes that
  used to be independent.** A `verbatim-run` repair that introduces an
  unexpanded acronym or a `Just` raises the `prose` count, and the total
  rising is exactly what this check exists to catch, so the verbatim
  repair reverts even though it fixed its own finding;
- **if the draft's dossier has a `math.md`**, a repaired quantity still
  matches it (docs/WRITING-STANDARDS.md §12) -- this skill is the
  likeliest of all of them to break that mapping and the least likely to
  notice, since it is reasoning about wording or markers, not quantities.

Otherwise revert the item from the pre-edit text kept in step 4. **Before
trying again, re-file the baseline against the true reverted state**:

```bash
python -m chitragupta.review agenda content/drafts/<path> --json
```

`--baseline`'s target is also what every `agenda` call refiles on exit,
failed attempt included -- so skipping this bare re-file before a second
attempt would compare it against the first attempt's inflated count
instead of the pass's real starting point, silently reporting a retry as
progress it never made. Then try once more. **Two attempts per item.** A
second failure escalates to the human and the loop moves on; a reverted
item leaves every earlier accepted one intact.

**The pass loop.** After each accepted repair, re-read
`objective_class_count` from the same `--baseline` response (its
`objective_after`). Continue to the next item only while that count
**strictly falls** pass over pass; that is the terminator, read from the
payload rather than carried as a literal. Stop at `pass_bound` (also
read from the baseline agenda's payload, taken in step 2) as a backstop
against a miscounting bug -- said in those words if this stop is ever
reached, since it is a backstop and not a budget.

**One pass per invocation.** When the worklist is done, stop and hand
back. Do not re-run the agenda and start again on whatever the repairs
surfaced.

### 6. Log every attempt

Append to the dossier's `revisions.md`: the date, each item by `id` and
`class`, what was done, and what happened -- accepted, reverted,
escalated, or declined by the user. Refusals are the entries most worth
having, because they are what stops the next session re-attempting
something that was already decided against.

**Never write any of this to `rejected.md`.** That file is about sources
that were retrieved and turned down, not repairs that did not work.

### 7. Present

Show the diff and the `revisions.md` entries, and state the outcome
against the baseline agenda from step 2: `objective_class_count` before
and after, what was repaired per class, what was escalated and why.

The human accepts. Nothing here merges, commits or renders on its own.

### Prose is now this skill's work, not merely surfaced

```bash
python -m chitragupta.draft style content/drafts/<path>
```

Already run as part of the baseline agenda in step 2 -- `agenda` reads
it as one of its eight sources. Under Decision 1 of
`plans/f3-agenda-reviser.md`, every `prose` finding carries
`unattended: true` and is repaired in step 4, the same as any other
unattended class. **This is the one skill of the nine where that
finding list is a work list rather than only a report** -- every other
skill that runs this command stops at reporting; this one goes on to
repair. Your own repairs are new prose, written under pressure to avoid
someone else's wording on the `verbatim-run` items, which is exactly
where a defect marker or a dialect slip gets back in, so re-run the
check as part of every `--baseline` cycle in step 5 rather than only
once at the end.

**It checks only what `docs/WRITING-STANDARDS.md` §9 marks decidable**
-- §2's defect markers, an acronym never expanded at first use, a
glossary acronym whose expansion has drifted, §8's dialect against
`scope.md`'s `language:` line, and (since #435) an uncaptioned table or
figure. It cannot tell a quotation from the draft's own voice, and a
clean report on the classes it does not check says nothing about them.
A review aid, not a gate -- it exits 0 whatever it finds.

### Run the verbatim scan

The baseline in step 2 is that scan, so it has already run. Two things
still have to happen before you present: rebuild the section map --
which this skill has just invalidated, because rewording a finding is
exactly what moves wording between citekeys -- and say what the scan
does **not** cover.

```bash
python -m chitragupta.draft dossier sections content/drafts/<path> --citekeys --write
python -m chitragupta.review verbatim scan content/drafts/<path>
```

Take the step-2 baseline the same way, so the baseline and the final
scan are measured against the same table. If the first command exits 1
for a missing dossier, say so and scan anyway.

It reports verbatim and near-verbatim reuse against any parsed source, cited or
not, and **genuine restatement is only detected where the embedding tier can
run** -- these drafts are LLM-written and literal paraphrase is an LLM's normal
failure mode -- so a clean scan, and a clean `recheck`, is not a clean bill of
health (`docs/PLAGIARISM.md`). Say that plainly rather than letting a zero read
as an all-clear. **Say what it did not check:** if `tiers_not_run` is not
empty, quote each reason as the scan wrote it, and where the reason names a
fix (`poetry install --with enrich`, `python -m chitragupta.enrich`) pass that
on once -- on this skill above all, because a repair loop reporting "all
findings fixed" from two tiers of three is the most misleading sentence in
this pipeline. **A review aid, not a gate: it exits 0 either way, and it is
never a condition of presenting.**

### Close the pass with one full-format run

Every `--baseline` refresh in step 5 ran at `--formats md` (Decision 6 --
only three of the eight aids render anything beyond Markdown, and
skipping the other formats saves about 2.5 seconds a cycle). Each aid's
`.tex`/`.pdf` is therefore stale against its own `.md` until the pass
ends. Before presenting, run one more `review agenda content/drafts/<path>
--json` (its default `--formats md,tex,pdf`, and still no `--baseline`),
so the final artefacts on disk are the ones the human reads.

`agenda-reviser` repairs a style finding **that appears as an agenda
item**; every other change to wording -- including `draft-reviser`'s own
copy-edit mode, which also edits prose -- belongs to `draft-reviser`.

## Guardrails

- **Never start this on your own initiative.** Not from a hook, not from
  a scheduled job, not at the end of a genre skill's run, and not from
  `draft-reviser`. A person asking is the only trigger.
- **Never edit anything but the draft and `revisions.md`.** Not
  `content/verbatim_allowlist.toml`, not `assets/vale/styles/chitragupta/*.yml`
  (prose became work under Decision 1, which puts the Vale rule
  definitions within reach of the same failure for the first time), not
  `rejected.md`, not `scope.md`, not `evidence.md`, and nothing under the
  corpus layer. Suppressing a finding by allowlisting it is the user's
  call about their own project, and a loop that could silence its own
  detector is not a loop anyone should trust.
- **Never decide paraphrase-or-quote on a long run.** Ask.
- **Never `Write` the whole draft.** `Edit` the passage.
- **Never add a claim, and never fabricate a citekey.** A fabricated
  citekey is the one failure this whole pipeline exists to prevent, and a
  repair that needs a page-anchored citation is exactly where the
  temptation shows up.
- **Never run `python -m chitragupta.corpus sync` or `python -m chitragupta.enrich`.**
- **Never present a draft that has not passed
  `python -m chitragupta.draft gate`.**
- **Never report a repair you did not verify.** If `recheck` was not run,
  say so rather than describing the edit as accepted.

## Sources

The prose standards this skill inherits are documented, with
per-principle attribution, in
[`docs/WRITING-STANDARDS.md`](../../../docs/WRITING-STANDARDS.md#-sources-and-attribution).
What the verbatim tiers catch and what they structurally cannot is in
[`docs/PLAGIARISM.md`](../../../docs/PLAGIARISM.md). The requirements
this loop is built to satisfy -- the write-set, the binary re-check, the
two-attempt limit and the rule that only a person may start it -- are
R1-R11 in
[`docs/AUTO-IMPROVEMENT.md`](../../../docs/AUTO-IMPROVEMENT.md#-the-requirements),
with the reasoning in
[`docs/AUTO-IMPROVEMENT-RATIONALE.md`](../../../docs/AUTO-IMPROVEMENT-RATIONALE.md).

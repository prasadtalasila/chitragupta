---
name: agenda-reviser-opencode
description: Repairs the unattended findings on an existing draft's review agenda, one item at a time. Reads `python -m chitragupta.review agenda <draft>` and acts only on items whose `unattended` field says so; every other class is surfaced for a person to decide. One R4 cycle is one command, `review agenda <draft> --baseline <stem>.agenda.json --json`; passes continue only while `objective_class_count` strictly falls, and stop at `pass_bound`. Every repair must re-pass `python -m chitragupta.draft gate` and the same baseline recheck before it is kept, and every attempt is logged in revisions.md. Triggers when the user asks to work the review agenda, fix what an agenda run found, or act on unattended findings -- before rendering or submitting, after a sync moved the corpus, or on returning to a draft after weeks away. Judgement calls go to draft-reviser-opencode or the human. Never edits the allowlist, never adds a claim, never fabricates a citekey, and never runs unless a person asked for it.
tags: [revision, review, agenda, dossier, citation]
---

# agenda-reviser-opencode

`python -m chitragupta.review agenda <draft>` merges the review aids'
reports, the dossier's drift and its recorded-but-uncited citekeys into
one ranked, deduplicated worklist. Each item carries an `unattended`
field, decided once by the aid that raised it, saying whether it may be
repaired without asking. The agenda stops at reporting. This skill does
the repair, the `--baseline` recheck that says whether the repair worked,
and a written record of both, and decides nothing the agenda left
undecided.

**A finding is not a verdict.** A defined term, a standard's name and a
correctly attributed quotation all show up as findings, and rewriting
one makes the draft worse. Read `docs/PLAGIARISM.md` before deciding that
a finding is a defect.

## When to invoke

| Situation | Action |
| --- | --- |
| User asks to work the review agenda, fix an unattended finding, or clean up what an agenda run found | Invoke this skill |
| An agenda was just run and the user asks "what do I do about these" | Invoke this skill |
| The user wants the agenda **run** but says nothing about fixing it | Run `review agenda <draft>` and show them. Do not start repairing |
| The finding is real but the user disagrees that it needs changing | They are right by default: record it and move on (`SOUL.md`: a machine does not outrank a person on a judgment call) |
| Any other change to an existing draft, including re-grounding after a sync moved the corpus and wording no agenda item names (that is copy-edit mode) | Use `draft-reviser-opencode` |
| User asks to re-check the whole draft against the corpus | Use `corpus-reviser-opencode` |
| User asks for a **new** draft | Use the matching genre skill |
| The draft has no dossier | Bootstrap one as `draft-reviser-opencode` describes, then continue here. `revisions.md` is where this skill's record goes, so it has to exist |
| The ledger is empty or absent | Stop and say so. A repair that converts a lift into a quotation needs a citekey the gate will accept |

## What may be repaired unattended

Read each item's `unattended` field and act on it as written; **never
re-derive it from `class` or from anything else in the item.** On this
checkout it can be true for three classes:

| Class | Unattended when | Otherwise |
| --- | --- | --- |
| `missing-citekey` | always: a citekey the draft cites that the corpus no longer has | -- |
| `prose` | a `draft style` finding whose rule did not mark it `repair: "review"` | surfaced: leave it |
| `verbatim-run` | severity `short` (under 15 words), `exact` or `skip-gram` tier, not `names` | `long`: **stop and ask** paraphrase or quotation. `names: true`: surfaced, a person declares it in `content/style_exceptions.toml`. `embedding` tier, any length: surfaced, advisory only. `quoted` (quote marks and the source cited): already correct, do not touch |

Every other class is a judgement call, surfaced for a person: report it
and do not touch it. `recorded-but-uncited` is the person's to clear with
`dossier prune` or `dossier sections --citekeys --write`;
`unsupported-claim`, `claim-support`, `uncited-claim` and `misquoted` are
about meaning, which no re-run settles. A long run's choice is authorial:
paraphrasing a sentence the field states one way makes the prose worse,
and quoting a passage never meant to be quoted pads the draft.

## The loop

Paths in this skill are from the project root, not from this skill's
own folder.

Follow `.opencode/skills/draft-reviser-opencode/SKILL.md`'s `## The loop` for four
of its parts -- reading `scope.md` and `steering.md` first, mapping a
change onto sections, editing with `edit` rather than `write`, and
writing the dossier back. Read that file; do not reconstruct it from
memory. Its steps map onto this loop like this:

| Its step | Here |
| --- | --- |
| 1, read `scope.md` and `steering.md`, `mark-revision` | Step 1, after a `dossier export` |
| 3, map onto sections | Step 4: only the section that owns the item |
| 4, search | Never: a repair adds no source |
| 5, edit in place | Step 4: the exact span the item names |
| 6, write the dossier back | Step 6: `revisions.md` only, the one dossier file this skill writes by hand; the section map it rebuilds in steps 2 and 7 is derived from the draft |
| 7, gate | Step 5, after every repair. No `references`, no `render`, and never `dossier stamp` |
| prose check, verbatim scan, draft diff | Step 5 refreshes the prose check each cycle; step 7 runs the scan and the diff |

### 1. Snapshot, and mark the revision

Before the first edit:

```bash
python -m chitragupta.draft dossier export <name>
python -m chitragupta.draft dossier mark-revision content/drafts/<path> --label "agenda remediation"
```

`<name>` is the draft's path under `content/drafts/` with the suffix
dropped (`dt-for-engineers/survey`); `python -m chitragupta.draft dossier
list` prints the names it matches. The export is the way back if the
pass as a whole turns out wrong. Then read `scope.md` and `steering.md`:
a rewrite is still a rewrite, and the reader and the terminology are
already fixed.

Done when the export exists, the revision is marked, and both files are
read.

### 2. Take the baseline agenda

Rebuild the section map first, with step 7's `dossier sections
--citekeys --write`, so the baseline and the final scan read the same
table. Then:

```bash
python -m chitragupta.review agenda content/drafts/<path> --json
```

`agenda` files its report on every run, at
`content/review/<topic>/<stem>.agenda.json`; `--json` only decides what
prints. This is the file every later `--baseline` in this pass points at,
and the closing report is stated against it (R9). Read `pass_bound` and
`objective_class_count` off it now and never hardcode either. Take a
fresh one at the start of every pass: a payload already on disk may
predate the draft's last edit.

If it holds no unattended items, say so, report the surfaced ones, and
stop.

Done when the baseline is filed and you have its two numbers.

### 3. Triage

Group the baseline's `items` by `class`, then by `unattended`. Before
editing, tell the user how many of each unattended class will be
repaired, how many surfaced items exist, and `objective_class_count` and
`pass_bound`. Work `missing-citekey` and `prose` first, then
`verbatim-run` at `short`, and collect every `long` run into one
question rather than interrupting per finding.

Done when the user has the counts and the order.

### 4. Repair one item

**First, refuse a stale span.** The author may have edited the draft
since the baseline, and a repair applied to text that is gone destroys
their work. Before the first repair of the pass, and after any pause in
which the draft may have been touched, take a fresh bare read:

```bash
python -m chitragupta.review agenda content/drafts/<path> --json
```

The aid drops an item whose exact draft text changed and lists it in
`stale_spans` with its section (R12). **Repair only an item that is in
the fresh `items`**: never one listed in `stale_spans` or gone from
`items`, and never relocated by similarity, merged or applied near where
it used to be. Log the refusal in step 6 and name it in step 7, or a
dropped item reads as a repaired one. This re-file overwrites
`<stem>.agenda.json`, so the refreshed file is now the baseline step 7
reports against; and the count it shows fell without a repair, so it is
not progress.

Then read only the section that owns the item, by the line ranges
`python -m chitragupta.draft dossier sections content/drafts/<path>`
prints, and keep its pre-edit text for step 5.

**The agenda's `detail` is thin by design and is not the repair
payload.** A `verbatim-run` item carries `verbatim_id`, not
the `draft_text` an `edit`'s `oldString` needs. **Then repair by class**,
reading only the reference for the class of the item in hand, now:

- a `missing-citekey` item:
  `.claude/skills/agenda-reviser/references/repair-missing-citekey.md`
- a `prose` item: `.claude/skills/agenda-reviser/references/repair-prose.md`
- a `verbatim-run` item at severity `short`:
  `.claude/skills/agenda-reviser/references/repair-verbatim-run.md`

Remove a marker with `edit`, leaving the sentence standing. `edit` the
exact span an item names. For a verbatim run, look up `draft_text` as
its reference says and use it as `edit`'s `oldString`. **Never add a
claim**: every repair is a rewording, an attribution, a marker removal or
a caption, never new ground.

A `prose` finding is work here, the one skill where the prose check's
list is a work list rather than a report. When the item's `summary` and
`detail.message` are not enough, reproduce the full finding:

```bash
python -m chitragupta.draft style content/drafts/<path>
```

It checks only what `docs/WRITING-STANDARDS.md` §9 marks decidable:
§2's defect markers, an acronym never expanded at first use, a drifted
glossary acronym, §8's dialect against `scope.md`'s `language:` line,
an uncaptioned table or figure, and the fixed phrases §4 and §7 name:
clichés, hype, wordy stock phrases, the habits of machine-written prose,
and how a statistic is reported. It cannot tell a quotation from the
draft's own voice, and a clean report says nothing about what it does
not check. A review aid, not a gate: it exits 0 whatever it finds.

Done when the edit is made and the pre-edit text is kept. The item is
not repaired until step 5 accepts it.

### 5. Accept or revert

After every repair, one command runs the whole R4 cycle: it refreshes
the aids itself, the prose check included, which matters because your
own rewording is where a defect marker or a dialect slip gets back in.
**Never hand-roll it as a bare `review agenda` read**, which reads the
pre-edit reports still on disk and calls an unresolved finding resolved.

```bash
python -m chitragupta.review agenda content/drafts/<path> \
    --baseline content/review/<topic>/<stem>.agenda.json --json
```

**If it exits 1 with the sync instruction, stop the pass**: revert this
repair, keep every earlier accepted one, and tell the user to run
`python -m chitragupta.corpus sync`.

**Read `not_refreshed` first.** It names each aid whose refresh failed
this cycle (a refusal, an exit 0 that wrote nothing, as `support` does
without the enrich stack, or an exception); an aid that raised is also a
key in `refresh_errors`, with its reason. Their items are an earlier
run's, left out of `resolved`, `persisting`, `new` and both counts, so a
quiet list is no evidence they went away.

**An aid in `refresh_errors` comes first**, since the edit may have
caused it, and one retry cannot tell that from a host fault. Revert the
repair, re-file the baseline as below, and run the recheck once on the
reverted draft:

- **It no longer raises:** keep the repair reverted and count the
  attempt. Report the aid, its reason, and that it raised after the edit
  but not without it: the edit, or a fault that cleared.
- **It still raises:** the edit is not the cause. Record the aid as a
  standing failure for this pass, do not count the attempt, and try the
  repair again, handling that aid by the rules below from then on.

Then, for every aid still in `not_refreshed`: **`verbatim` listed, stop
the pass and surface it**, reverting an unverified repair rather than
keeping it, since no `verbatim-run` repair can be verified this cycle.
**Any other aid: carry on**, never act on or count its items, and name it
in step 7.

Accept the repair only if **all** of these hold:

- `python -m chitragupta.draft gate content/drafts/<path>` exits 0;
- the item's `id` is in `resolved`;
- `objective_delta` is not positive. A `verbatim-run` repair that adds
  an unexpanded acronym or "simply" raises the `prose` count and reverts,
  even though it fixed its own finding;
- `objective_new` is 0. A total holds level when a repair resolves its
  own finding and introduces another objective one: that swap reverts.
  A `new` item that is not unattended is reported in step 7, not
  reverted;
- if the dossier has a `math.md`, a repaired quantity still matches it
  (`docs/writing-standards/mathematics.md` §12).

Otherwise revert from the pre-edit text, and **before trying again,
re-file the baseline against the reverted draft**:

```bash
python -m chitragupta.review agenda content/drafts/<path> --json
```

Every `agenda` call refiles the `--baseline` target, a failed attempt's
included, so a retry without this compares against the failed attempt
and reports progress it never made. **Two attempts per item**: a second
failure escalates to the human and the loop moves on, every earlier
accepted repair intact.

**The pass.** One pass works every unattended item on the worklist.
After each accepted repair, read `objective_after` from the same
response, and continue only while `objective_class_count` **strictly
falls**. `pass_bound` counts passes, never repairs: an accepted repair
does not count against it. Stop at `pass_bound` if it is ever reached,
and say it is a backstop against a miscounting bug, not a budget. **One pass per
invocation**: when the worklist is done, hand back rather than re-run
the agenda on what the repairs surfaced.

Done when each item is accepted, reverted, escalated or refused, and the
pass has stopped.

### 6. Log every attempt

Append to the dossier's `revisions.md`, dated: each item by `id` and
`class`, what was done, and the outcome (accepted, reverted, escalated,
refused as stale, or declined by the user), then a closing `Sections:`
line naming every section edited. Refusals are the entries most worth
having: they stop the next session re-attempting what was decided
against. **Never write any of this to `rejected.md`**, which records
sources turned down, not repairs.

Done when every attempt of the pass has its entry.

### 7. Close the pass and present

Rebuild the section map, which rewording has just invalidated, and run
the scan:

```bash
python -m chitragupta.draft dossier sections content/drafts/<path> --citekeys --write
python -m chitragupta.review verbatim scan content/drafts/<path>
```

Read `.claude/skills-common/references/verbatim-scan.md` now and follow
it. Its "say what it did not check" matters most here: a repair loop
reporting "all findings fixed" from two tiers of three is the most
misleading sentence in this pipeline, and a clean `--baseline` recheck
is no more a clean bill of health than a clean scan. **A review aid, not
a gate: it is never a condition of presenting.**

Every `--baseline` cycle refreshed the aids at `--formats md` only, so
run one more bare agenda, at its default formats, so the `.tex` and
`.pdf` reports on disk match:

```bash
python -m chitragupta.review agenda content/drafts/<path> --json
```

Last, show what changed, against step 1's snapshot:

```bash
python -m chitragupta.draft diff content/drafts/<path> --format pdf
```

Read `.claude/skills/draft-reviser/references/draft-diff.md` now and
show what it says to. Then state the outcome against the baseline:
`objective_class_count` before and after, what was repaired per class,
what was escalated, refused as stale or left surfaced and why, and every
aid any cycle's `not_refreshed` named, with a note that its items went
unverified. For an aid that raised, quote its `refresh_errors` reason
and which of step 5's two outcomes it had. The human accepts: nothing
here merges, commits or renders.

Done when the user has the diff and the report.

## Guardrails

Each is one of R1-R12 in
[`docs/AUTO-IMPROVEMENT.md`](../../../docs/AUTO-IMPROVEMENT.md#-the-requirements),
argued in
[`docs/AUTO-IMPROVEMENT-RATIONALE.md`](../../../docs/AUTO-IMPROVEMENT-RATIONALE.md).

- **Never run this on a verbatim digest.** Its `verbatim-run` repair
  paraphrases copied text unattended, and on a digest that is the whole
  text. Say so and stop.
- **Never start this on your own initiative**: not from a hook, a
  scheduled job, the end of a genre skill's run, or `draft-reviser-opencode`. A
  person asking is the only trigger.
- **Never edit anything but the draft and `revisions.md`**: not
  `content/verbatim_allowlist.toml`, not anything under `assets/vale/`
  (a rule file or `vale.ini`), not `rejected.md`, `scope.md`
  or `evidence.md`, and nothing under the corpus layer. A loop that could
  silence its own detector is not one anyone should trust; suppressing a
  finding is the user's call.
- **Never run `review agenda --accept`.** It records a person's judgement
  that a surfaced item may stand. Report the item and tell them
  `--accept <id>` keeps it off later worklists.
- **Never repair an item the fresh agenda refused as stale**, or one no
  longer in `items`. The author's own edit wins by default (R12).
- **Never decide paraphrase-or-quote on a long run.** Ask.
- **Never `write` the whole draft.** `edit` the passage.
- **Never add a claim, and never fabricate a citekey.** A repair that
  needs a page-anchored citation is exactly where the temptation shows
  up. Remove a missing key's marker instead.
- **Never run `python -m chitragupta.corpus sync` or `python -m chitragupta.enrich`.**
  Both take the pipeline's write lock and are the user's to run; if one
  is needed, say so and stop.
- **Never present a draft that has not passed
  `python -m chitragupta.draft gate`.**
- **Never report a repair you did not verify.** If its `--baseline`
  recheck did not run, say so rather than calling the edit accepted.
- **Never run `dossier stamp`.** It writes `scope.md`. The stale
  fingerprint the next `dossier status` reports is the honest signal that
  an automated pass touched the draft, and an orphaned `evidence.md`
  block a repair left is a finding a person should see.

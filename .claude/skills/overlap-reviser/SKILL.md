---
name: overlap-reviser
description: Repairs the verbatim overlap a scan found, one finding at a time, in a draft that already exists in content/drafts/. Reads `python -m chitragupta.review verbatim scan --json`, rewrites each short uncited run to preserve the claim and the citation while breaking the borrowed wording, and stops to ask the human paraphrase-or-quote on every long run rather than deciding silently. Repairs only what that scan's deterministic tiers can see: genuine restatement is only detected where the embedding tier can run, so finishing this loop is never a clean bill of health. Every repair must re-pass `python -m chitragupta.draft gate` and `python -m chitragupta.review verbatim recheck` before it is kept, and every attempt is logged in the dossier's revisions.md, refusals and reverts included. Triggers when the user asks to fix, clean up or remediate verbatim overlap, borrowed wording, a plagiarism report or the findings of a verbatim scan -- and on the three occasions that raise the question: before rendering or submitting, after a sync moved the corpus, and on picking a draft back up after weeks away. Anything that is not a verbatim finding is draft-reviser, not this skill; hand off and say so. Never edits the allowlist, never adds a claim, never fabricates a citekey, and never runs unless a person asked for it.
tags: [revision, plagiarism, verbatim, dossier, citation]
---

# overlap-reviser

`python -m chitragupta.review verbatim scan` finds every run of borrowed wording
in a draft, buckets it by severity and files it as JSON. Then it stops,
because it is a review aid and review aids report. Everything after that
-- reading the report, finding the passage, rewriting it without losing
the claim, checking the rewrite did not make things worse -- was left to
a person. That is the tedious half, and the half that gets skipped.

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

This skill does the half that was left over. It is not a better scan and
it does not decide anything the scan was careful not to decide: what it
adds is the repair, the re-check that says whether the repair worked, and
a written record of both.

**A finding is not a verdict.** A run of shared wording is a place to
look. A defined term, a standard's name and a correctly attributed
quotation all show up as findings, and rewriting one of those would make
the draft worse. Read `docs/PLAGIARISM.md` before deciding that a finding
is a defect.

## When to invoke

| Situation | Action |
|---|---|
| User asks to fix, clean up or remediate verbatim overlap, borrowed wording or a plagiarism report | Invoke this skill |
| A scan was just run and the user asks "what do I do about these" | Invoke this skill |
| The user wants the draft **scanned** but says nothing about fixing it | Run the scan and show them. Do not start repairing |
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

The scan already buckets every finding by severity. That bucket is the
line, so this skill does not invent a second threshold:

| Bucket | What it is | This skill |
|---|---|---|
| `quoted` | Touching quote marks **and** citing the source | Report it as already correct. Do not touch it |
| `short` | Under 15 words, not a marked quotation | Repair unattended |
| `long` | 15 words or more, not a marked quotation | **Stop and ask.** Present paraphrase and quotation as two options and let the human choose |

A long run is where the choice actually matters. Paraphrasing a sentence
the field states one particular way makes the prose worse to no benefit;
quoting a passage that was never meant to be quoted pads the draft and
signals a claim the author did not make. That is an authorial decision,
so it is asked, not taken.

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
python -m chitragupta.draft dossier mark-revision content/drafts/<path> --label "overlap remediation"
```

`<name>` is the draft's path under `content/drafts/` with the suffix
dropped -- `dt-for-engineers/survey`, not the full path and not the bare
stem. `python -m chitragupta.draft dossier list` prints the names it will match.

The export is the way back if the pass as a whole turns out wrong. The
marker is what lets `dossier status` attribute this session's cost
separately from the drafting run's.

Then read `scope.md` and `steering.md`. A rewrite is still a rewrite: the
reader is already fixed, and so is the terminology. Introducing a second
name for a concept while breaking up a borrowed phrase is the exact seam
a reader notices.

### 2. Take the baseline

```bash
python -m chitragupta.review verbatim scan content/drafts/<path> --write --json
```

Uncapped -- **never pass `--limit` to a baseline**. A capped payload lists
only the longest findings, so it cannot say what was absent, and
`recheck` refuses it for that reason.

If the scan reports nothing, say so and stop. There is nothing here to do --
and the draft is not thereby clean, because **genuine restatement is only
detected where the embedding tier can run** by either deterministic tier this
baseline came from.

This files the payload at `content/review/<topic>/<stem>.verbatim.json`.
That file is the recorded baseline: every claim you make at the end is
stated against it, not against a re-scan you took later.

Take a fresh one at the start of every pass rather than reusing whatever
is already at that path. An existing payload may predate the draft's last
edit, and one from an earlier release series `recheck` will refuse
outright -- what counts as a single finding changes between releases.
Re-scanning is a sub-second cache hit, so there is nothing to save by
reusing an old one.

### 3. Triage

Read the payload's `findings`. Each carries `severity` (the bucket
above), `cites_source`, `quoted`, and enough to locate itself.

Sort into the three buckets and tell the user the counts before you start
editing: how many will be repaired unattended, how many need their
decision, and how many are already correct. Then work the `short` bucket,
and collect the `long` ones into one question rather than interrupting
per finding.

### 4. Repair one finding

Read only the section that owns it -- `python -m chitragupta.draft dossier
sections content/drafts/<path>` gives the line ranges -- and edit with
`Edit`, using the finding's own `draft_text` as `old_string`. That field
is the passage exactly as written, casing, punctuation, line breaks and
any citation marker sitting mid-run included; it is there so you do not
have to search the draft for the passage and risk matching the wrong one.

If an `Edit` built from `draft_text` does not match, the draft almost
certainly has CRLF line endings and the run spans a line break: the
payload carries the `\n` the file was read with, not the `\r\n` on disk.
Re-read the line and edit it by hand rather than widening the search.

Keep the pre-edit text. You will need it in step 5 if the repair is
rejected.

**Paraphrase** -- the default, and the only option for a `short` run:

- Preserve the claim. This is a rewording, not a retraction.
- Preserve the citation. Breaking up borrowed wording while dropping the
  attribution converts a citation problem into a worse one.
- Leave no run of `min_run` consecutive source words. The payload's
  `min_run` is the number.
- Prefer the smaller diff. Where deleting a redundant clause and
  rewriting the sentence both work, delete.

**Quotation** -- only for a `long` run, and only when the human chose it:

- Wrap the passage in quote marks and anchor the citation to the
  finding's own page: `[@citekey, p. 12]`, or `[@citekey, pp. 12-13]`
  when `end_page` is greater than `page` -- a quotation lifted from a run
  spanning a source page break (#131) is misattributed if the citation
  names only where it starts.
- Check the source can actually be quoted first. `chitragupta/passages.py` gives
  a page-level passage no text at all when the source was parsed by
  `pdftotext -layout`, because an excerpt cut from a two-column paper is
  a collage of two arguments rather than a quotation. If it is not
  quotable, say so and paraphrase instead -- do not quote from a page
  number alone.

**Never add a claim.** On these findings you are only ever rewording,
attributing or removing something the draft already said. New ground is a
different request and belongs to `draft-reviser`.

### 5. Accept or revert

Both of these, after every repair:

```bash
python -m chitragupta.draft gate content/drafts/<path>
python -m chitragupta.review verbatim recheck content/drafts/<path> \
    --baseline content/review/<topic>/<stem>.verbatim.json --json
```

Accept the repair only if **all** of:

- the gate exits 0;
- the finding's `id` appears in `recheck`'s `resolved`;
- `objective_delta` is not positive.

That last one is the check worth having. A rewrite that fixes its own
finding by lifting from a different source resolves the item and leaves
the draft no better, and the delta is what catches it.

Otherwise revert the passage from the text you kept in step 4 and try
once more. **Two attempts per finding.** A second failure means the item
is escalated to the human and the loop moves on -- reverting one finding
leaves every earlier accepted one intact.

**One pass per invocation.** When the list is done, stop and hand back.
Do not re-scan and start again on whatever the repairs surfaced.

### 6. Log every attempt

Append to the dossier's `revisions.md`: the date, each finding by `id`
and citekey, what was done, and what happened -- accepted, reverted,
escalated, or declined by the user. Refusals are the entries most worth
having, because they are what stops the next session re-attempting
something that was already decided against.

**Never write any of this to `rejected.md`.** That file is about sources
that were retrieved and turned down. A rewrite that did not work is not a
rejected source, and putting it there would teach the next revision to
skip a paper for a reason that has nothing to do with the paper.

### 7. Present

Show the diff and the `revisions.md` entries, and state the outcome
against the baseline from step 2: findings before, findings now, what was
repaired, what was escalated and why.

The human accepts. Nothing here merges, commits or renders on its own.

### Run the prose check

Before you present:

```bash
python -m chitragupta.draft style content/drafts/<path>
```

Your repairs are new prose, written under pressure to avoid someone
else's wording, which is where a defect marker or a dialect slip gets in.
**It checks only what `docs/WRITING-STANDARDS.md` §9 marks decidable** --
§2's defect markers, an acronym never expanded at first use, a glossary
acronym whose expansion has drifted from the vocabulary, and §8's
dialect against `scope.md`'s `language:` line. It knows nothing about
overlap, and it cannot tell a quotation from the draft's own voice, so a
clean report says nothing about the findings you just repaired.

**Report every finding and fix none of them.** This skill's write-set is
the draft's overlap findings and `revisions.md`; a spelling fix is not a
verbatim finding, and anything that is not a verbatim finding is
`draft-reviser` -- hand it off and say so. Report the header lines too:
`dialect: not checked` means nobody ever recorded one. A review aid, not
a gate -- it exits 0 whatever it finds, and a missing `vale` binary is a
one-line warning that blocks nothing.

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

## Guardrails

- **Never start this on your own initiative.** Not from a hook, not from
  a scheduled job, not at the end of a genre skill's run, and not from
  `draft-reviser`. A person asking is the only trigger.
- **Never edit anything but the draft and `revisions.md`.** Not
  `content/verbatim_allowlist.toml`, not `rejected.md`, not `scope.md`,
  not `evidence.md`, and nothing under the corpus layer. Suppressing a
  finding by allowlisting it is the user's call about their own project,
  and a loop that could silence its own detector is not a loop anyone
  should trust.
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

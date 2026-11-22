---
name: deep-research
description: Runs a multi-perspective, corpus-grounded deep-research pipeline over the synced bibliography -- perspective discovery, parallel simulated interviews, contradiction mapping, outline, cited section writing, synthesis briefing, and self peer-review -- citing only real citekeys from content/ledger.sqlite, never a URL and never an invented key. Triggers when the user asks for "deep research", a multi-perspective analysis, or an in-depth grounded report on a topic, as distinct from survey-writer's single-pass literature survey. To change a report that already exists in content/drafts/, use draft-reviser instead -- never re-run this skill to make a change. Heavier and slower than survey-writer by design. Must run `python -m chitragupta.draft gate` before presenting. Stops and tells the user to run `python -m chitragupta.corpus sync` if the ledger is empty, rather than syncing itself.
tags: [deep-research, multi-perspective, storm, citation]
---

# deep-research

Every claim resolves to a real citekey from `content/ledger.sqlite`,
cited `[@citekey]`, or is stated plainly as "not found in the corpus":
never invented, never smoothed over. Paths in this skill are from the
project root, not from this skill's own folder. The method is Stanford
OVAL's STORM by way of hadufer/claude-storm (MIT), retooled for a closed
corpus; `.claude/skills/deep-research/references/report.md` carries the
attribution and the adaptation, and
`.claude/skills/deep-research/references/report.md` §6 the honesty rules
the report is held to.

## Before you start

**The corpus is read-only: never run `python -m chitragupta.corpus sync`
or `python -m chitragupta.enrich`.** Before the first retrieval, read
`.claude/skills-common/references/genre-steps.md` §1: what the corpus
holds, and why those are the user's to run. **If the ledger is empty,
stop.** Check before drafting anything:

```bash
python -m chitragupta.corpus ledger
```

If it reports nothing `parsed`, say what you checked and found, and stop.
Tell the user to run `.venv-full/bin/python -m chitragupta.corpus sync`
and come back.

## When to invoke

A standard literature survey is `survey-writer`'s (faster, single-pass), a
thesis chapter `thesis-chapter-writer`'s, a textbook chapter
`textbook-chapter-writer`'s, a hands-on tutorial `tutorial-writer`'s, and
a change to a report in `content/drafts/` is `draft-reviser`'s: never
re-run this skill to make one. Tell the user up front that this is a
heavy, multi-phase run that dispatches several subagents. Keep a checklist
of the 7 phases below in your replies and work through them in order.

## Collection scoping: deliberately not used here

Search the whole corpus, always: no `--collection`, here or in any
agent this skill dispatches. A curated shelf would narrow every
perspective to one pre-agreed subset and hide the disagreements Phase 3
exists to map. If a user asks for a collection-scoped report, say that
cost and let them decide; `.claude/skills/deep-research/references/report.md`
§3 has the reasoning and its measurement.

## The dossier

Read `.claude/skills-common/references/genre-steps.md` §2 before Phase 1:
what the dossier holds and why it is filled in as you go.

**The main run owns the dossier. A subagent never writes it.**
`deep-research-interviewer`, `deep-research-writer` and `peer-reviewer`
each run in their own context, return a packet instead of writing a
file, and lose that context when they exit. Whatever of theirs is worth
keeping is yours to transcribe, in the phase that dispatched them,
before you move on: Phases 2, 3 and 5 say what goes where. Never ask a
subagent to write into `content/dossiers/`, and do not treat a packet as
durable because you can still see it. The `peer-reviewer` packets are
the one exception: Phase 7(a)'s reconciled scorecard ships in the report
and is their record, so it keeps the concerns logged and left
unaddressed.

Phase 5 then dispatches from the file rather than from your context:
pasted claims cost output tokens once per writer (`docs/TOKENS.md`), and
`brief` exits non-zero naming a citekey whose block is missing.

## Prose standards

Follow `docs/WRITING-STANDARDS.md` for the rules every genre shares, and
`docs/writing-standards/genres/deep-research.md` for what this report owes
its reader: read it before Phase 4. This genre uses no figures
(`docs/writing-standards/figures.md` §10). Every table carries a caption
line, an `<!-- table: <id> -->` marker and an inline `<!-- tableref: <id>
-->` (`docs/writing-standards/tables.md` §13); a quantity follows
`docs/writing-standards/mathematics.md` §12, with a row in the dossier's
`math.md`.
If asked what bears on this genre, read
`.claude/skills/deep-research/references/report.md` §9.

## Depth presets

| Depth | Perspectives | Interview rounds | Section writers |
| --- | --- | --- | --- |
| quick | 3 + basic | 2 | inline (no subagents) |
| **standard** (default) | **5 + basic** | **3** | parallel subagents |
| deep | 6-7 + basic | 4 | parallel subagents |

"+ basic" = always include the **Basic fact writer** generalist pass.

## Phase 1 -- Perspective discovery

**Before any retrieval, name the reader and the scope, and open the
dossier.** Read `.claude/skills-common/references/genre-steps.md` §3
first: the path, `scope.md`, the dialect, the acronym vocabulary and the
fingerprint. Settle the path with the user; the flat
`content/drafts/deep-research-<slug>.md` is the default. Whichever you
choose, use it verbatim everywhere below: every `--log`, each subagent's
`DRAFT PATH`, the gate and Phase 7(d), since the dossier mirrors it.

```bash
python -m chitragupta.draft dossier init content/drafts/deep-research-<slug>.md --genre deep-research
```

Then check for an `outline.md`:

```bash
python -m chitragupta.draft dossier outline content/drafts/deep-research-<slug>.md --check
```

If it passes, read `.claude/skills-common/references/genre-steps.md` §4.
Its sections are the report's declared structure, its declared
`queries:` are what Phase 2's interviewers run verbatim
(`--origin declared`; a thin section's reformulations are
`--origin extended`), and its headings name the personas.
`python -m chitragupta.review uncited` is the backstop for a `claim:`
you could not ground. With no `outline.md`, or one that fails `--check`,
read `.claude/skills/deep-research/references/report.md` §2 and derive
the personas from 1-2 broad retrieval calls on the topic.

Always add the **Basic fact writer**, and state the final persona list
before dispatching. Done when `scope.md` records the reader, the scope
and `language:`, and the persona list is stated.

## Phase 2 -- Multi-perspective grounded interviews (parallel)

Dispatch one `deep-research-interviewer` subagent per persona, **all in
parallel** if your session offers subagent tools; otherwise run each
interview yourself, one after another, following the protocol from
`.claude/agents/deep-research-interviewer.md`, which holds the whole
interview: the rounds, the searches, judging each hit and the packet it
returns. Give each its `TOPIC`, its `PERSPECTIVE` (name and focus),
`ROUNDS` (per depth) and the `DRAFT PATH`, which it passes to `--log` on
every retrieval call. With an outline, also give it its section's
declared `queries:`, to run verbatim with `--origin declared`, and say
that any reformulation is `--origin extended`.

**Transcribe every packet before starting Phase 3**: each kept claim
into `evidence.md`, one ``## `citekey` `` block with a `relevance:`
line, the packet's claim as `claim:` and a `quote:` line per passage
the packet singled out, none otherwise; each discarded citekey into `rejected.md`
with the query that surfaced it and why it did not hold up. That list
exists nowhere but the packet. Read
`.claude/skills-common/references/genre-steps.md` §5 for both formats
and the warnings of the self-check:

```bash
python -m chitragupta.draft dossier check-evidence content/drafts/deep-research-<slug>.md
```

A perspective that found nothing after real reformulation is a
thin-coverage finding to report
(`.claude/skills-common/references/genre-steps.md` §6). Done when every
packet is transcribed and `check-evidence` has run.

## Phase 3 -- Contradiction map

From the transcribed packets, map:

1. **Direct contradictions** -- the conflicting claims, both sides by
   citekey.
2. **Strongest vs weakest evidence** -- which perspective's claims the
   corpus supports best and worst.
3. **The resolving question** -- what the corpus would need to answer to
   settle the biggest contradiction.
4. **Universal agreement** -- what every perspective agrees on.
5. **The blind spot** -- what no perspective's searches turned up.

Record each contradiction in `evidence.md` beside the citekeys it
concerns, and the blind spot in `scope.md`'s **Does not cover**: a
revision that doesn't know about them will smooth them over. Done when
both are recorded.

## Phase 4 -- Outline

Sketch an outline from general topic knowledge, then refine it with the
interviews and the contradiction map. No "Summary" or "Introduction"
heading: the lead comes in Phase 6. Fix two things the parallel writers
would otherwise get wrong: **the reader**, one concrete sentence
(`docs/WRITING-STANDARDS.md` §1), and **the glossary**, each recurring
term with the one definition every writer uses. Write both into
`scope.md` over Phase 1's versions; the writers get the glossary from
that file.

**Then write the plan into `sections.md`**: one row per outline section,
with the kept citekeys it will stand on. `dossier brief --section`
resolves a section through these rows, so a section with no evidence yet
gets a row with an empty citekey cell, never no row: an empty cell is a
gap to fill, a missing row reads as a mistyped section name. Phase 7(e)
replaces this plan with what the report cites. Done when `scope.md` and
`sections.md` hold the reader, the glossary and a row per section.

## Phase 5 -- Cited section writing (parallel)

Before dispatching, check that each section's rows resolve to
transcribed evidence, without reading the evidence back into your own
context:

```bash
python -m chitragupta.draft dossier brief content/drafts/deep-research-<slug>.md \
  --section "<section heading>" --check
```

Fix a gap now: a writer dispatched against an empty brief writes an
ungrounded section that reads exactly like a grounded one.

For `standard`/`deep`, dispatch `deep-research-writer` subagents **in
parallel** (one per section), each given `TOPIC`, `READER`, `GLOSSARY`,
its section outline fragment, and the one line that stands in for the
evidence:

```bash
Your evidence: python -m chitragupta.draft dossier brief content/drafts/deep-research-<slug>.md --section "<heading>"
```

**Do not paste the kept claims into the prompt.** Give a writer only what
the rows don't carry (a term, a constraint from the user's steering). If
you cannot spawn `deep-research-writer`, write each section yourself with
`.claude/agents/deep-research-writer.md`'s instructions, and the `brief`
line for its section. For `quick`, write each section inline: you are the
writer, the packets are already in your context, so skip `brief` and
follow that file's "Writing standards", "Citation protocol" and "If a
subpoint is thin" yourself. Cap concurrency per
`.claude/skills/deep-research/references/report.md` §1.

When the writers return, copy each `### Sources added` block into
`evidence.md` yourself, as a `relevance:`/`claim:` block per citekey in
the writer's words (a `quote:` line per passage the block singled out),
and each `### Candidates discarded` block into `rejected.md`. These
citekeys never passed through Phase 2, so nothing else in the run has
them; at `quick` depth, record what you found the same way. Done when
every section is written and every block is transcribed.

## Phase 6 -- Polish + synthesis briefing

**(a) Lead:** `## Summary`, <=4 cited paragraphs, opening with a scope
statement: what this report covers, what it doesn't, and which
sub-questions the corpus couldn't answer. Remove repetition across
sections.

**(a2) Reconcile across sections.** Fix the seams parallel writers leave
(`docs/writing-standards/genres/deep-research.md`, "The reread"), then
read the assembled draft once as the Phase 4 reader. Collect every
writer's `math.md` rows into one, `## Symbols` included, and check table
and equation ids for collisions; number an equation only here, adding
`<!-- equation: <id> -->` and `<!-- equationref: <id> -->`. A body
paragraph closes on two or more citekeys wherever the packet allows, or
carries `<!-- single-source: why -->` beside it
(`docs/WRITING-STANDARDS.md` §11);
`python -m chitragupta.review synthesis <draft>` reports it.

**(b) Synthesis briefing**, in the shape of
`.claude/skills/deep-research/references/report.md` §5's template: an
executive summary, 5 key findings ranked by reliability, the hidden
connection visible only across perspectives combined, the actionable
insight for the user's role, and the frontier question.

Done when the lead, the reconciled body and the briefing are written.

## Phase 7 -- Peer review + assembly

**(a) Peer review.** For `standard`/`deep`, dispatch four `peer-reviewer`
subagents **in parallel**, one per role -- `domain-accuracy`,
`methodology-rigor`, `clarity-completeness`, `devils-advocate` -- each
given the full draft, the `DRAFT PATH` (for `--log`) and its `ROLE`, and
nothing else: no reviewer sees another's critique. If you cannot spawn
subagents, review in turn yourself, with
`.claude/agents/peer-reviewer.md`'s instructions for the assigned role.
Then act as the reconciling editor under
`.claude/skills/deep-research/references/report.md` §7's concession
threshold: any `high` concern, or any `medium` or `high` one raised by two
or more reviewers, is revised or stated in the scorecard as unresolved,
never silently dropped. For `quick`, critique inline yourself, as §7 ends
by describing. Done when the scorecard is recorded.

**(b) Assemble** per `.claude/skills/deep-research/references/report.md`
§5's template: Title -> Summary -> Synthesis briefing -> article body ->
Contradiction map -> Peer-review scorecard -> References. Citekeys need
no renumbering (`.claude/skills/deep-research/references/report.md` §4).
Done when the report is assembled.

**(c) Save, log provenance, critique, and gate.** Save the assembled
report to `content/drafts/deep-research-<slug>.md` first: the gate reads
a file. Then write
`content/dossiers/<draft path minus suffix>/provenance.json`, mapping
every section to its citekeys for tooling. It is not the dossier, which
holds the working state a later revision reads: write both.

**Then critique against the evidence packet, before gating.** Read the
dossier's `evidence.md` -- the `relevance:`/`claim:`/`quote:` blocks
Phases 2 and 5 recorded -- against the assembled report's own prose,
section by section, and list in priority order up to five places where
the prose claims more than its `claim:` supports, omits a kept `claim:`,
or drifts from its wording. One inline judgement call: not a subagent
dispatch, not a deterministic check, and narrower than (a)'s peer
review, which judges rigor and coverage for a human to read.

Read `.claude/skills-common/references/critique.md` now, before listing
anything, and follow it with `content/drafts/deep-research-<slug>.md` as
`<draft>`; make each edit with an `apply_patch` hunk.
**This step is not done until the loop the reference describes has
run**: the baseline, then at most three repairs, each checked and logged
in the dossier's `revisions.md`. It is never a condition of presenting.
Come back with the list, each repair kept or reverted, the scan's
`tiers_not_run` reason if it gave one, and whether the declared queries
are exhausted. Done when the loop has returned and every attempt is
logged, or you have said that nothing cleared the bar.

**Then gate:**

```bash
python -m chitragupta.draft gate content/drafts/deep-research-<slug>.md
```

Fix and re-run until `OK`. Never present a draft that hasn't passed.
Done when it reports `OK`.

**(d) Save and render.** The draft saved in (c) is the canonical,
source-of-truth format. Follow
`.claude/skills-common/references/render-and-references.md` §1, §2 and
§3 for it: fill in the `## References` heading the template left
bare from exactly the gated citekeys, render tex, pdf and md, then the
evidence sidecar in pdf and md. If the user asks why this report emits a
sidecar, or why the closing checks below matter more here, read
`.claude/skills/deep-research/references/report.md` §5 and §8. Done when
`draft references`, `draft render` and `draft evidence` have run, or
each warning is reported.

**(e) Close the dossier.** Replace Phase 4's plan in `sections.md` with
what the finished report actually cites, derived rather than corrected
by hand:

```bash
python -m chitragupta.draft dossier sections content/drafts/deep-research-<slug>.md \
    --citekeys --write
```

**Only here, never before Phase 5**: deriving from a report not yet
written replaces the plan with an empty table, which `brief` cannot tell
from a mistyped section name. Read its stderr: a citekey cited above
the first heading is reported, not filed. If the user shaped this run in
chat, append that to `steering.md`, dated
(`.claude/skills-common/references/genre-steps.md` §2). Done when both
are done.

**(f) Run the prose check.** After the gate passes and before presenting:

```bash
python -m chitragupta.draft style content/drafts/deep-research-<slug>.md
```

Read `.claude/skills-common/references/prose-check.md` now and follow it.
If the user wants any finding acted on, that is `draft-reviser`'s
copy-edit mode, never an edit made here. Done when every finding is
reported.

**(g) Run the verbatim scan.** Before presenting, rebuild the section map
and scan:

```bash
python -m chitragupta.draft dossier sections content/drafts/deep-research-<slug>.md \
    --citekeys --write
python -m chitragupta.review verbatim scan content/drafts/deep-research-<slug>.md
```

The first command is not optional and not a repeat of (e) or (c): a
section map written before an edit describes a report you have since
changed. **A review aid, not a gate: it cannot block the report, and it
is never a condition of presenting.** Read
`.claude/skills-common/references/verbatim-scan.md` now and follow it.
Repairing a finding is `agenda-reviser`'s job, and only if the user
asks. Done when the findings are shown.

**(h) Stamp the draft fingerprint, then present.** Read
`.claude/skills-common/references/genre-steps.md` §7 first, then:

```bash
python -m chitragupta.draft dossier stamp content/drafts/deep-research-<slug>.md
```

Give the user: the headline finding, the single most important
contradiction, the actionable insight, the overall grade, any unresolved
peer-review concern, the citekey count, the saved path and the render
outcome. Changes go through `draft-reviser`, not another run of this
skill, and `python -m chitragupta.draft dossier export deep-research-<slug>`
backs the report and its dossier up. Done when the user has the report.

---
name: corpus-reviser
description: Revises an existing draft in content/drafts/ by re-searching the whole corpus, instead of working from the dossier alone as draft-reviser does -- re-searches every sub-theme the dossier records, reads the whole draft, and says what it will cost before it starts. Triggers ONLY when the user explicitly asks for a whole-corpus pass ("re-check the entire draft against the corpus", "search everything, cost regardless"), when a scope change they agreed to has invalidated the recorded queries, or when a draft is being re-targeted at a different reader. For every other change to an existing draft -- including repairing citations after a sync moved the corpus -- use draft-reviser instead, which is far cheaper and is the right default. Never re-runs the genre skill, never discards the dossier, honours rejected.md, and must pass `python -m chitragupta.draft gate` before presenting.
tags: [revision, dossier, citation, corpus]
---

# corpus-reviser

A wide revision pass: `draft-reviser`'s loop, with a search of every
sub-theme the dossier records in place of its search of only the one a
change touches. It keeps the dossier -- every rejection and its reason,
the recorded reader, the glossary, the steering -- and spends tokens only
on what is still unknown. Paths in this skill are from the project root,
not from this skill's own folder. If the user asks why the wide pass is a
separate skill rather than a mode, `docs/DRAFT-ITERATION.md` ("The scoped
default, and the way out of it") has the answer.

## When to invoke

| Situation | Action |
| --- | --- |
| User asks in as many words for a whole-corpus pass, cost regardless | Invoke this skill |
| A scope change the user agreed to has invalidated the recorded queries | Invoke this skill -- the old queries were chosen for the old scope |
| The draft is being re-targeted at a different reader | Invoke this skill -- what counts as support changes with the reader |
| Any other change to an existing draft | Use `draft-reviser` |
| A sync moved the corpus and citations broke | Use `draft-reviser`'s re-grounding mode -- repairing what broke is not a wide pass |
| User asks for a **new** draft | Use the matching genre skill |
| You are not sure which of the two this is | Use `draft-reviser`, and say you did |

## Say what it costs, before you start

One sentence, before the first search, and let the user stop you. A wide
pass re-searches every sub-theme the dossier records and reads the whole
draft, so it costs roughly what the original drafting run did, minus the
clustering and the writing. If `scope.md` carries a `collection:` line,
the same sentence names that collection as the one this pass searches
past (below).

If the ledger is empty or absent, stop and say so rather than revising
around it: this skill is defined by going back to the corpus, so there is
nothing to fall back on.

Done when the user has the cost sentence, or you have stopped on an
empty ledger.

## Collection scoping: say you are widening it

`scope.md` may carry a `collection:` line, written by the genre skill
that produced this draft; a missing line, or
`- collection: (whole corpus)`, means it already searches everything. A
whole-corpus pass *is* a widening, and that is what the user asked for,
so its searches carry no `--collection`. A draft grounded in one curated
shelf and re-checked against the whole library has changed what it is
made of, and nothing in the diff shows it: the citekeys are all real and
the gate still passes. So say so in the cost sentence, record the
widening in `revisions.md`, and leave the `collection:` line as it
stands: the user chose it, and only the user unchooses it.

## The loop

Follow `.claude/skills/draft-reviser/SKILL.md`'s `## The loop`, steps 1
through 7, unchanged except for the two steps below. Read that file; do
not reconstruct it from memory. Then run this skill's own three closing
steps, which follow.

**Step 3 becomes a whole-draft read.** `python -m chitragupta.draft dossier sections
content/drafts/<path>` still gives the outline, but here it is a work
list rather than a filter: you read every section, because a wide pass
is judging the whole draft against the corpus, not one claim. Done when
every section is read.

**Step 4 stops being a decision.** In `draft-reviser` the question is
whether to search at all, and the answer is usually no. Here it is
already answered.

Take the sub-themes from `retrieval.md`'s recorded queries -- those are
the questions this draft was actually built by asking -- and fall back to
the section headings in `sections.md` where it records none. Read
`rejected.md` first: a candidate listed there with a reason is not
re-retrieved and re-judged, because a wide search finds what was never
weighed and is no licence to re-litigate what was. If a recorded reason
has genuinely stopped holding (usually because the scope moved), say
which one and why before re-opening it. Then one search each:

```bash
python -m chitragupta.draft retrieve search "<sub-theme>" --k 15 --log content/drafts/<path>
# no --collection: a whole-corpus pass is a widening -- see "Collection scoping" above
python -m chitragupta.draft retrieve evidence "<sub-theme>" --citekey <key> --log content/drafts/<path>
```

`evidence` is optional: reach for it when a snippet cannot settle a
source you are minded to cite. Before recording what you kept and what
you turned down, read `.claude/skills-common/references/genre-steps.md`
§5. A block from before this run that carries only `support:` is read as
`quote:` and left exactly as it stands.

Done when every sub-theme has had its search, each with `--log`, and both
outcomes are recorded in `evidence.md` and `rejected.md`.

**Steps 5 to 7 hold as written, and three of their rules bind harder
here:**

- **`Edit`, never `Write`.** A wide *search* does not imply a wide
  *rewrite*: most sections survive a re-check untouched.
- **Step 6's `revisions.md` entry says plainly that this pass was wide
  and why**, names any collection it searched past, and its `Sections:`
  line names every section touched. A wide rewrite rewords more
  quantities than a scoped one, so keep `math.md` in step if the draft
  has one (`.claude/skills-common/references/figures-tables-equations.md`
  §6), and when the pass adds or rewords a symbol, a condition or a
  derivation, read `.claude/skills-common/references/mathematical-prose.md`
  before writing it.
- **When the pass touches a figure, a table or an equation**, read the
  matching section of
  `.claude/skills-common/references/figures-tables-equations.md` §1, §2,
  §3, §4 and §5 before editing it. Figures follow the draft's own genre,
  read from `scope.md`'s `genre:` line, and a `deep-research` draft gets
  none, wide pass or not. A figure's two forms change together. Only
  ids matter for tables, captioned figures and numbered equations, and a
  wide pass is the one most likely to move one into another section.

### Run the prose check

After step 7, and the stamp it ends on, before presenting:

```bash
python -m chitragupta.draft style content/drafts/<path>
```

Read `.claude/skills-common/references/prose-check.md` now and follow it.
A wide pass is the one most able to import another author's spelling
along with their point, and the one least entitled to tidy prose nobody
asked about: findings go to `draft-reviser`'s copy-edit mode, not into
this pass.

Done when every finding is reported and none is fixed.

### Run the verbatim scan

Before presenting, rebuild the section map and scan:

```bash
python -m chitragupta.draft dossier sections content/drafts/<path> --citekeys --write
python -m chitragupta.review verbatim scan content/drafts/<path>
```

The first command is not optional. A wide pass rewrites against sources
the draft may never have cited, so it is the pass most likely to have
changed which section leans on which paper, and most able to import
someone else's phrasing into a paragraph that credits no one. **A review
aid, not a gate: it is never a condition of presenting.** Read
`.claude/skills-common/references/verbatim-scan.md` now and follow it.
Repairing a finding is `agenda-reviser`'s job, and only if the user asks.

Done when the findings are shown.

### Show what changed

Last, once the `revisions.md` entry is written:

```bash
python -m chitragupta.draft diff content/drafts/<path> --format pdf
```

Read `.claude/skills/draft-reviser/references/draft-diff.md` now and
follow it.

Done when the user has the report.

## Guardrails

- **Never invoke this skill on your own initiative.** It is the user's
  choice, and an unrequested wide pass is the most expensive thing that
  can happen without anyone asking for it. When unsure, use
  `draft-reviser` and say so: being wrongly narrow costs one clarifying
  sentence; being wrongly wide costs tokens the user did not agree to
  spend.
- **Never re-run the genre skill.** It discards the dossier and pays to
  rediscover a worse version of it. If the request truly needs a new
  draft, say that and hand off explicitly.
- **Never run `python -m chitragupta.corpus sync` or `python -m chitragupta.enrich`.**
  The corpus is read-only: both take the pipeline's write lock, can run
  for tens of minutes, and are the user's to run.
- **Never treat a wide search as permission to re-judge `rejected.md`.**
  Honour it, and re-open a rejection only by saying which and why.
- **Never write a citekey** that isn't already in the draft, in
  `evidence.md`, or in a `search()` result you just read. A long run is
  exactly where the temptation shows up.
- **Never silently change scope, reader or terminology.** Change them
  only as the user agreed in step 2, and record it in `scope.md`.
- **The gate is the exit.** Never present a draft that hasn't passed
  `python -m chitragupta.draft gate`.
- **Report what the pass actually changed** -- including the sections you
  re-checked and left alone, which is the evidence that the cost bought
  something. Say how many sub-themes were searched and how many sources
  changed.

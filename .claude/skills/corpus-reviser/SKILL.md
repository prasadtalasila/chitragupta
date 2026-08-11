---
name: corpus-reviser
description: Revises an existing draft in content/drafts/ by re-searching the whole corpus, instead of working from the dossier alone as draft-reviser does -- re-searches every sub-theme the dossier records, reads the whole draft, and says what it will cost before it starts. Triggers ONLY when the user explicitly asks for a whole-corpus pass ("re-check the entire draft against the corpus", "search everything, cost regardless"), when a scope change they agreed to has invalidated the recorded queries, or when a draft is being re-targeted at a different reader. For every other change to an existing draft -- including repairing citations after a sync moved the corpus -- use draft-reviser instead, which is far cheaper and is the right default. Never re-runs the genre skill, never discards the dossier, honours rejected.md, and must pass `python -m src.draft gate` before presenting.
tags: [revision, dossier, citation, corpus]
---

# corpus-reviser

`draft-reviser` reads the dossier instead of the corpus, and re-searches
only the sub-theme a change actually touches. That is the right default,
and it is an economy rather than a rule about what anyone is allowed to
ask for. This skill is the way out of it.

It exists as a separate skill so the choice is yours and is made once,
out loud. `draft-reviser` contains no instructions for a wide search, so
it cannot drift into one; invoking this skill is how you say the cost is
worth it. `SOUL.md` is why the distinction is a door rather than a gate:
how wide a revision should be is a judgment about your draft, and a
machine does not outrank you on one of those.

**What this is not is a re-run of the genre skill.** That remains the one
thing that is never right. It throws away the dossier -- every rejection
and the reason for it, the recorded reader, the glossary, the steering
you gave in chat -- and then pays to rediscover a worse version of it.
This keeps all of that and spends tokens only on what is genuinely
unknown.

## When to invoke

| Situation | Action |
|---|---|
| User asks in as many words for a whole-corpus pass, cost regardless | Invoke this skill |
| A scope change the user agreed to has invalidated the recorded queries | Invoke this skill -- the old queries were chosen for the old scope |
| The draft is being re-targeted at a different reader | Invoke this skill -- what counts as support changes with the reader |
| Any other change to an existing draft | Use `draft-reviser` |
| A sync moved the corpus and citations broke | Use `draft-reviser`'s re-grounding mode -- repairing what broke is not a wide pass |
| User asks for a **new** draft | Use the matching genre skill |
| You are not sure which of the two this is | Use `draft-reviser`, and say you did |

That last row is not modesty. Being wrongly narrow costs one clarifying
sentence; being wrongly wide costs the tokens, and the user did not
agree to spend them.

**Read-only over the corpus layer**, exactly as everywhere else. Never
run `python -m src.sync` and never run `python -m src.enrich`: both take the
pipeline's write lock and can run for tens of minutes, and they are the
user's to run.

## Say what it costs, before you start

One sentence, before the first search, and let them stop you. A wide pass
re-searches every sub-theme the dossier records and reads the whole draft,
so it costs roughly what the original drafting run did, minus the
clustering and the writing.

If the ledger is empty or absent, stop and say so rather than revising
around it. This skill is defined by going back to the corpus, so there is
nothing to fall back on.

## The loop

Follow `.claude/skills/draft-reviser/SKILL.md`'s `## The loop`, steps 1
through 7, unchanged except for the two steps below. Read that file; do
not reconstruct it from memory. It is the same scope check, the same
edit discipline, the same dossier write-back and the same exit.

**Step 3 becomes a whole-draft read.** `python -m src.draft dossier sections
content/drafts/<path>` still gives the outline, but here it is a work
list rather than a filter: you read every section, because a wide pass
is judging the whole draft against the corpus, not one claim.

**Step 4 stops being a decision.** In `draft-reviser` the question is
whether to search at all, and the answer is usually no. Here it is
already answered.

Take the sub-themes from `retrieval.md`'s recorded queries where the
dossier has them -- those are the questions this draft was actually built
by asking. Fall back to the section headings in `sections.md` where it
doesn't, which is the case for any draft written before `--log` was
passed. One search each:

```bash
python -m src.draft retrieve search "<sub-theme>" --k 15 --log content/drafts/<path>
python -m src.draft retrieve evidence "<sub-theme>" --citekey <key> --log content/drafts/<path>
```

`evidence` stays optional and stays for deepening an acceptance -- reach
for it when a snippet is not enough to decide on a source you are minded
to cite. Score what you keep the way `survey-writer` step 2 describes,
and record both outcomes: kept into `evidence.md`, turned down into
`rejected.md`.

## What does not relax

The cost is the only thing this skill changes. Everything that makes a
revision cheaper *to repeat* still holds, and dropping any of it would
turn a wide pass into the re-run this skill exists to avoid.

- **`rejected.md` is still consulted first, and still honoured.** A
  candidate listed there with a reason is not re-retrieved and
  re-judged. A wide search finds what was never weighed; it is not a
  licence to re-litigate what was. If a recorded reason has genuinely
  stopped holding -- usually because the scope moved -- say which one and
  why before re-opening it.
- **Every call carries `--log`.** The point of choosing the expensive
  path deliberately is that the cost lands in `retrieval.md` and can be
  looked at afterwards, instead of being guessed at.
- **`Edit`, never `Write`.** A wide *search* does not imply a wide
  *rewrite*. Most sections survive a re-check untouched, and rewriting
  those costs thousands of output tokens to produce a diff nobody can
  review.
- **Never write a citekey** that isn't already in the draft, in
  `evidence.md`, or in a `search()` result you just read. A fabricated
  citekey is the one failure this whole pipeline exists to prevent, and
  a long run is exactly where the temptation shows up.
- **The dossier is written back** -- `scope.md` only if the user agreed
  to a scope change, plus `evidence.md`, `rejected.md`, `sections.md`,
  `steering.md`, and a `revisions.md` entry saying plainly that this pass
  was wide and why.
- **The gate is the exit.** Never present a draft that hasn't passed
  `python -m src.draft gate`.
- **Offer the verbatim scan** -- `python -m src.review verbatim scan
  content/drafts/<path>` -- before presenting. Don't run it silently and
  never make it a condition of presenting. It reports wording the draft
  shares with **any** parsed source, cited or not, which earns its place
  after a wide pass in particular: this skill re-reads the whole corpus
  and rewrites against sources the draft may never have cited, so it is
  the pass most able to import someone else's phrasing into a paragraph
  that credits no one. A review aid, not a gate: it exits 0 either way.
  Say what it misses when you offer it -- verbatim and near-verbatim
  reuse only, and **paraphrase is not detected**, so a clean scan is not
  a clean bill of health (`docs/PLAGIARISM.md`).
  If the user wants the finding kept, add `--write`: the report
  goes to `content/review/`, mirroring the draft's path, beside any
  provenance and coverage reports for the same draft.

## Guardrails

- **Never invoke this skill on your own initiative.** It is the user's
  choice, and an unrequested wide pass is the most expensive thing that
  can happen without anyone asking for it.
- **Never re-run the genre skill.** If the request truly needs a new
  draft, say that and hand off explicitly.
- **Never run `python -m src.sync` or `python -m src.enrich`.**
- **Never treat a wide search as permission to re-judge `rejected.md`.**
- **Never silently change scope, reader or terminology.**
- **Report what the pass actually changed** -- including the sections you
  re-checked and left alone, which is the evidence that the cost bought
  something. Say how many sub-themes were searched and how many sources
  changed.

## Sources

The prose standards this skill inherits are documented, with
per-principle attribution, in
[`docs/WRITING-STANDARDS.md`](../../../docs/WRITING-STANDARDS.md#sources-and-attribution).
The reasoning for why the scoped default exists, and why the way out of
it is a separate skill rather than a paragraph, is in
[`docs/DRAFT-ITERATION.md`](../../../docs/DRAFT-ITERATION.md).

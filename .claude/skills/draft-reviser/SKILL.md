---
name: draft-reviser
description: Revises an existing draft in content/drafts/ from its dossier (content/dossiers/<same path>/) instead of re-running the genre skill that produced it -- reads the recorded scope, reader, glossary, kept evidence and rejected candidates, edits only the affected sections, and logs what changed. Triggers when the user asks to revise, shorten, expand, restructure or correct a draft that already exists, including in a session that did not write it. Also covers whole-document copy-editing that touches no evidence -- triggers on "fix the grammar", "fix the spelling", "convert this to British English", "make it en-GB/en-IN", or rephrasing to meet a style guideline -- in a copy-edit mode that reads scope.md's recorded dialect, skips retrieval and evidence entirely, edits section by section rather than rewriting the file, and logs one revisions.md entry naming the convention applied; it refuses to change a claim, add or drop a citation, or reorder an argument under cover of a style pass. Also handles re-grounding after the corpus moves -- triggers on "re-ground", "the corpus moved", "a cited paper left the corpus", "this draft has drifted", or a `dossier status --all` report naming a draft, and consumes that report as JSON to propose a scoped fix rather than a re-draft. This is the cheap, scoped path and the right default for any change. If the user explicitly wants the whole corpus re-searched -- "re-check the entire draft against the corpus", "search everything, cost regardless" -- that is corpus-reviser, not this skill; hand off and say so. Use the genre skill (survey-writer, thesis-chapter-writer, textbook-chapter-writer, tutorial-writer, deep-research) for a NEW draft, never for a change to an existing one. Must pass `python -m src.draft gate` before presenting and never invents a citekey.
tags: [revision, dossier, citation]
---

# draft-reviser

Revising a draft by re-running the genre skill that wrote it is the most
expensive mistake available in this repository. A fresh run re-retrieves,
re-scores every candidate, re-clusters and rewrites the whole file --
to change one paragraph. This skill exists so that never has to happen.

The reason it can work is that the judgment behind a draft is on disk:
`content/dossiers/<draft path minus suffix>/` holds the reader, the
scope, the glossary, the kept evidence, the rejected candidates and the
steering the user gave in chat. See `docs/DRAFT-ITERATION.md` for why it
is shaped that way.

## When to invoke

| Situation | Action |
|---|---|
| User asks to shorten, expand, restructure, correct or update an existing draft | Invoke this skill |
| User asks for a grammar pass, a spelling fix, a dialect conversion (en-US -> en-GB/en-IN), or rephrasing to meet a style guideline | This skill, in **copy-edit mode** (below) -- the loop's search and evidence steps short-circuit |
| User asks to re-target the draft at a **different reader** | Hand off to `corpus-reviser` -- what counts as support changes with the reader, so the kept set has to be re-judged, not extended |
| User asks for a **new** draft on a topic | Use the matching genre skill |
| The draft exists but has no dossier | Bootstrap one (below), then continue here |
| A sync moved the corpus, or `dossier status --all` names this draft | Re-grounding mode (below), not the ordinary loop |
| User asks to re-check the **whole** draft against the corpus, cost regardless | Hand off to `corpus-reviser` -- not this skill, and never the genre skill |
| User asks for a different genre of the same topic | That's a new draft -- use the genre skill |
| Ledger is empty or absent | Revise anyway if the change touches no citations; say so. **Never** run `python -m src.corpus sync`. In re-grounding mode, stop instead -- the ledger *is* the request |

**Read-only over the corpus layer.** Never run `python -m src.corpus sync` and
never run `python -m src.enrich`. Both take the pipeline's write lock and
can run for tens of minutes; they are the user's to run.

## Prose standards

`docs/WRITING-STANDARDS.md` applies unchanged. Two of its rules bind
harder here than in a fresh draft, because a revision is the moment they
break:

- **The reader is already fixed.** `scope.md` names them. A revision that
  quietly writes for someone else produces a draft with two audiences.
- **Terminology is already fixed.** `scope.md`'s glossary is the
  definition the rest of the draft uses. Introducing a second name for a
  concept in the one section you touched is the exact seam a reader
  notices.

## The loop

### 1. Locate the draft and read its state

```bash
python -m src.draft dossier status content/drafts/<path>
```

This prints which dossier files are filled in, the draft's section count,
and whether the corpus has moved since the draft was written. A missing
or unreadable ledger is reported rather than raised -- it still tells you
what the dossier holds. A missing *dossier* is the one thing this command
treats as an error: it prints the `init` line and exits 1, which is your
cue to go to "When there is no dossier" below. (Only the plain form does
that; `--json`, used in re-grounding, exits 0 and reports it in the
payload instead.)

Then read `scope.md` and `steering.md`. **Always both, always first.**
They are small, and they are what stops a revision from undoing an
earlier decision the user already made.

Mark the start of this revision session in `retrieval.md`, before any
retrieval call:

```bash
python -m src.draft dossier mark-revision content/drafts/<path> --label "<one phrase, e.g. what the user asked for>"
```

`retrieval.md` rows otherwise carry only a date, and two revisions on the
same day are indistinguishable by it -- the marker is what lets
`dossier status` total a draft's retrieval cost per revision instead of
only as one lifetime figure. Costs nothing if step 4 below decides no
search is needed: an empty revision segment isn't reported.

### 2. Check the request against the recorded scope

If the change contradicts `scope.md`'s "Covers"/"Does not cover", say so
in one sentence and ask -- do not silently widen the draft. "You asked
for adoption economics; scope.md excludes it. Add it and update the scope
statement, or leave it out?" A scope change is a legitimate answer; a
scope change made without saying so is not.

### 3. Map the change onto sections

```bash
python -m src.draft dossier sections content/drafts/<path>
```

Read **only** the sections the change touches, using the printed line
ranges (`Read` with `offset=<start>`, `limit=<lines>`). Do not read the
whole draft to change one section. Consult `sections.md` when you need to
know which section owns a citation without reading anything.

Two exceptions, and only two. A change that alters the draft's argument
(restructuring, or a claim that other sections lean on) needs a read of
the whole draft, and so does a copy-edit pass, which touches every section
by definition -- see "Copy-edit mode" below for the rest of what that
changes. Recognise either case and pay for it deliberately, rather than
defaulting to it. Note that reading the whole draft is still not
re-searching it -- if the evidence also has to be re-judged, that is
`corpus-reviser`.

### 4. Decide whether you need to search at all

Most revisions don't, and a copy-edit pass never does -- if you are in
that mode, skip to it now rather than working through this step.

Before any retrieval call:

- Check `evidence.md` -- the supporting quote may already be recorded.
- Check `rejected.md` -- if a candidate is listed there with a reason,
  **do not retrieve and re-judge it**. That list exists precisely to stop
  the most expensive repeated work in the pipeline.

Search only when the change opens genuinely new ground. If it does:

```bash
python -m src.draft retrieve search "<query>" --k 15 --log content/drafts/<path>
python -m src.draft retrieve evidence "<query>" --citekey <key> --log content/drafts/<path>
```

(or `src.enrich.embed_index.search()` in place of `search` where the
embedding stack has been built). `evidence` is optional -- reach for it
when a snippet is not enough to decide on a source you are minded to
cite. Score what you keep as `survey-writer` step 2 describes, and record
both outcomes: kept into `evidence.md`, turned down into `rejected.md`.

`--log` keeps `retrieval.md` honest about what this revision actually
cost, which is the number that tells you whether revising from the
dossier is paying off.

If `status` reported corpus drift, read the named citekeys only if they
bear on the sub-theme you are changing. **Drift is not itself a reason to
redraft**, and a revision request is not a mandate to refresh the whole
draft against a corpus that grew. That holds for a corpus that *gained*
papers. It does not hold for one that lost a paper the draft cites --
that is a broken citation, the gate will fail on it, and it is fixed
whether or not anyone asked. See "Re-grounding after the corpus moves".

### 5. Edit in place, inside the section

Use `Edit` on the specific passage. Do not `Write` the whole file: a
whole-file rewrite of a survey-length draft costs thousands of output
tokens, re-runs the citation-gate hook over everything, and produces a
diff the user cannot review.

Never write a citekey that isn't already in the draft, in `evidence.md`,
or in a `search()` result you just read. AGENTS.md's invariant is
unchanged here: **a fabricated citekey is the one failure this whole
pipeline exists to prevent.**

### 6. Write the dossier back

Update only what actually changed:

- `evidence.md` -- new kept citekeys, with relevance and support
- `rejected.md` -- anything newly retrieved and turned down. Bear in mind
  that a later revision is told to trust this file rather than re-judge
  what is in it, so a reason worth reading later is worth writing now
  (`docs/REJECTION.md`)
- `retrieval.md` -- nothing by hand; `--log` appends to it for you
- `sections.md` -- if headings or their citations moved
- `scope.md` -- the scope statement itself only if the user agreed to a
  change in step 2. Its bookkeeping lines are a separate matter: a
  tutorial's `## Verified environment` block records what the lesson was
  last run on, and goes stale the moment you edit a step without
  refreshing it
- `steering.md` -- append the instruction that prompted this revision,
  dated. This is the part with nowhere else to live; skipping it is how
  the next session loses the thread.
- `revisions.md` -- append one entry: date, what changed, which sections,
  and why. A copy-edit pass logs one entry for the whole document and
  updates nothing else in this list; see "Copy-edit mode".

### 7. Gate, reference, render

```bash
python -m src.draft gate content/drafts/<path>
python -m src.draft references content/drafts/<path>          # .md drafts; see --heading below
python -m src.draft render content/drafts/<path> --format tex
python -m src.draft render content/drafts/<path> --format pdf
python -m src.draft render content/drafts/<path> --format md
```

Fix and re-run until the gate reports `OK`. **Never present a draft that
hasn't passed.** A `[missing-binary]` or `[error]` from `render_output`
is a one-line warning in chat and does not block presenting.

Two things the genre decides, which a reviser has to look up rather than
assume:

- **`--heading`, if the draft's references section isn't called
  "References".** `src.draft references` finds the existing section by heading
  and replaces it; miss it and you append a second one. A tutorial calls
  it `## Further reading` (pass `--heading "Further reading"`), and a
  numbered textbook chapter calls it `## N. References` (pass
  `--heading "N. References"`, or the numbering is silently dropped).
  Look at the draft's own heading before running this. Skip the command
  entirely for a `.tex` fragment, which manages its own bibliography.
- **A tutorial must still run.** `tutorial-writer`'s governing rule is
  that a tutorial which doesn't work is worse than none, because a
  learner who follows it exactly and hits an error concludes they are the
  problem. The citation gate does not check that -- a tutorial often has
  no citekeys for it to check at all. If you edited a step, a command, a
  version or an expected output, run the lesson from the top before
  presenting it, and update `scope.md`'s `## Verified environment` block
  with what you actually ran on. **Never present an unrun tutorial as if
  it were tested**; if you could not run it, say exactly that.

### Offer the verbatim scan

Before presenting, offer this -- don't run it silently, and never make it
a condition of presenting:

```bash
python -m src.review verbatim scan content/drafts/<path>
```

It reports wording the draft shares with **any** parsed source, cited or
not. Worth offering after a revision specifically: text you rewrote to
sit closer to a source is exactly the text most likely to have drifted
into its wording, and a revision that moved a claim between sections can
strand borrowed phrasing in a paragraph that no longer cites anything. A
review aid, not a gate: it exits 0 either way and cannot block the draft.
Say what it misses when you offer it -- it sees verbatim and
near-verbatim reuse only, and **genuine restatement is only detected where the embedding tier can run**, so a clean
scan is not a clean bill of health (`docs/PLAGIARISM.md`).
If the user wants the finding kept, add `--write`: the report
goes to `content/review/`, mirroring the draft's path, beside any
provenance and coverage reports for the same draft.

## Copy-edit mode

A grammar pass, a spelling fix, a dialect conversion, or rephrasing to
meet a style guideline is still a change to a draft that already exists,
so it is still this skill. But it is orthogonal to every axis the loop
above is organised around: it touches *every* section, and changes no
citekey, no evidence, no section map and no argument.

Recognise it from the request -- "fix the grammar", "convert this to
British English", "the hedging is too heavy throughout" -- and **say you
are in this mode before you start**, naming the convention you are about
to apply. That sentence is what lets the user stop you if they meant a
change of substance.

What changes, relative to the loop above:

| Step | In copy-edit mode |
|---|---|
| 1. Locate and read state | Unchanged, and load-bearing. `scope.md`'s `language:` line is the target a dialect pass converts *to*, and `steering.md` may already carry a house-style decision. Skip this and you apply your own default instead of the user's recorded one |
| 2. Check against recorded scope | Not applicable -- wording is not scope |
| 3. Map the change onto sections | Read the whole draft. This is precisely the case step 3's exception exists for, and it is paid for deliberately |
| 4. Decide whether to search | **No, and never.** A copy-edit that needs a retrieval call has stopped being one; see "Where the line is" below |
| 5. Edit in place | Unchanged, and load-bearing for a second reason -- below |
| 6. Write the dossier back | `revisions.md` only, one entry. There is no evidence delta, no new rejection and no moved section to record |
| 7. Gate, reference, render | Unchanged. Run the gate even though you changed no citation: that is the point |

If `scope.md`'s `language:` still says `not settled`, ask which dialect
before converting, and write the answer to that line as part of the pass.
A conversion applied against an unrecorded target is one the next session
cannot repeat or check.

**Still `Edit`, never `Write`, and now for a second reason.** Every
objection in step 5 holds. The new one is that the PostToolUse citation
gate runs per write, so editing section by section gives you a mechanical
check that the rewrite has not mangled a citekey or a `\citep{}` -- the
safety net that makes an aggressive whole-document rewrite safe to attempt
at all. One `Write` of the whole file trades that away exactly where the
risk is highest.

**One `revisions.md` entry for the whole pass**, not one per section, and
it names the convention rather than the sections:

```text
2026-08-14 -- copy-edit: converted to en-GB per scope.md's `language:`
(-ise, -our, -re endings); whole document; no claim, citation, section
order or citekey changed.
```

One entry because the log's later reader wants to know *what convention
now governs this draft*; forty entries reading "converted section 4" do
not answer that. `docs/DRAFT-ITERATION.md` has the shape and why it
carries no evidence delta.

### Where the line is

If the rephrasing wants to change what a sentence claims, add or drop a
citation, or reorder an argument, that is an ordinary revision. Finish the
copy-edit, then say what you found and ask -- never take a substantive
change under cover of a style pass, where it arrives in a diff the user is
reviewing for spelling.

Two things this mode refuses outright:

- **Never change a claim to make a sentence read better.** Hedging that
  carries real uncertainty is information (`docs/WRITING-STANDARDS.md`
  §4), and "X may be a factor" flattened to "X is a factor" is a new claim
  with an old citation behind it.
- **Never touch quoted material, a cited title, a proper noun, or a
  dataset or code identifier.** The recorded dialect governs the draft's
  own prose only (`docs/WRITING-STANDARDS.md` §8), and "organization"
  inside a quoted abstract or a venue's name stays as the source spelled
  it. Nothing downstream catches this one: the citation gate checks
  citekeys, not the words around them.

## Re-grounding after the corpus moves

When `python -m src.corpus sync` adds papers or drops stale ones, every existing
draft moves with it and nothing says so. `dossier status --all` is what
notices; this is what acts on it. It is the same loop entered from a
report instead of a request, so steps 5, 6 and 7 above still apply
verbatim -- what changes is how the work is found.

### R1. Read the report as data

```bash
python -m src.draft dossier status content/drafts/<path> --json
```

Or take the payload from a `--all --json` sweep the user already has. The
envelope is always `{"dossiers": [...]}`, so a single draft comes back as
a one-element list: read `.dossiers[0]`, not a bare object.

### R2. Branch on the payload, never on the exit code

This command exits 0 almost unconditionally -- that is deliberate, so the
caller reads the contents rather than a status. Two cases to check before
anything else:

- **`corpus_available` is `false`.** The ledger could not be read, so
  every finding list is empty because the check never ran, not because
  there is nothing to find. Say what you checked, point the user at
  `python -m src.corpus sync`, and stop. Do not report the draft as current.
- **The dossier does not exist.** `--json` returns an almost-empty entry
  and still exits 0. Go to "When there is no dossier", bootstrap, and
  come back.

### R3. Act on the three lists -- they are not the same kind of thing

Flattening them into one list of "papers to look at" is the failure mode
this section exists to prevent.

**`missing` is a defect.** The draft stands on a paper the corpus no
longer has; `citation_gate` already disagrees with the draft. Always
actioned, whatever else the revision is about. Each entry maps a citekey
to the sections citing it, and `python -m src.draft dossier sections
content/drafts/<path>` turns those into line ranges, so the edit stays as
scoped as any other. Look for the replacement in this order, and stop at
the first that supports the claim:

1. `evidence.md` -- another paper you already kept may support it, at no
   retrieval cost at all.
2. The report's own `candidates` -- a paper that arrived matching the
   same query that once produced the broken citation is the likeliest
   replacement there is.
3. A fresh search -- here it *is* right, unlike the candidate path,
   because a claim left unsupported is genuinely new ground:

   ```bash
   python -m src.draft retrieve search "<the claim>" --k 15 --log content/drafts/<path>
   ```

If none of the three supports it, **remove the claim** and say so. Not a
reworded sentence that keeps the assertion and quietly drops the
citation. Never leave the citekey in place, and never replace it with a
key you have not seen in the ledger.

**`candidates` are a decision, not a defect.** New papers that this
dossier's own recorded queries reach. Pursue only the ones whose
`queries` touch the sub-theme actually in play; the rest are reported to
the user and left in the report for the next revision to weigh. Do not
work through the list.

For the ones you do pursue, go straight to the passage. The report
already carries the citekey, the title and the query that surfaced it, so
re-running `search` for that query pays for fifteen snippets to be handed
back the same fifteen citekeys:

```bash
python -m src.draft retrieve evidence "<the query from the report>" \
    --citekey <candidate> --log content/drafts/<path>
```

What the report lacks is text to judge on, and that is what `evidence` is
for. Keep `python -m src.draft retrieve search "<query>" --k 15 --log <draft>`
for the case where the revision opens ground the dossier never covered --
a query not already in `retrieval.md`, which by definition could not have
produced a candidate.

**`reconsider` is not re-judged.** These are papers the draft already
read and turned down, which its queries still reach. `rejected.md` has
already been subtracted from `candidates`; these are carried separately
*with the recorded reason* so you can weigh the reason without paying to
re-judge the paper. Report citekey, title and reason. Re-open one only
when the recorded reason no longer holds -- typically a scope change the
user agreed to in step 2. Re-judging these by default is precisely the
cost `rejected.md` exists to prevent (`docs/REJECTION.md`).

### R4. Edit, write back, and re-stamp

Step 5 unchanged. Step 6 unchanged except for two of its bullets, which
were written for a revision someone asked for:

- **`steering.md` -- usually nothing.** A re-grounding pass has no
  instruction to record; the corpus moved, the user did not steer.
  Append only if they actually said something here. Inventing a steering
  entry to fill the file is the same failure as inventing an evidence
  one.
- **`scope.md` -- the fingerprint line only.** The rule that the scope
  statement changes only by agreement is untouched; the corpus line
  below is bookkeeping, and is the one thing this mode always writes.

Then two things specific to this mode.

**Re-stamp the corpus fingerprint** in `scope.md`, after the gate passes,
from the report's `current` field -- it is the record that this draft was
re-grounded against that corpus:

```text
- corpus: 503 citekeys, digest `f6e5d4c3b2a1`
```

Rewrite the line; do not reshape it. Anything that no longer matches the
recorded form makes `recorded_corpus()` return nothing, and the dossier
silently downgrades to "records no corpus fingerprint" instead of
erroring.

**Append a `revisions.md` entry** naming this as a re-grounding: what was
swapped, what was dropped, what was added, and -- with the same weight --
which candidates were reported and *not* pursued. The Guardrails rule
about reporting what you didn't do binds hardest here, because the user
did not ask for this revision and cannot infer its edges.

### R5. The gate is the exit, not the report

Finish with step 7 and change nothing about it. `missing` is computed
from the dossier's own `evidence.md` and `sections.md`, not from the
draft body, so a citekey the draft cites that was never recorded in the
dossier will not appear in the report at all. `python -m
src.draft gate` is the check that reads the draft, and it is what
decides the draft is presentable. A clean drift report never does.

Expect the draft to keep showing candidates in the next sweep, and say
so. A query returns fifteen hits and a revision accepts one or two;
"still has candidates" is the normal state of a healthy draft. What
re-grounding promises is that the *missing* list is empty. Do not clear
the candidate list by writing unpursued papers into `rejected.md` -- a
rejection recorded from a title alone is a judgment you did not make, and
`rejected.md` is trusted permanently by every revision after this one.

## When a whole-corpus pass is what's wanted

Everything above optimises for the common case: a change touches one
sub-theme, so one sub-theme gets re-searched. That default is right often
enough to be the default, and wrong often enough to need a way out.

The way out is a different skill. **`corpus-reviser`** re-searches every
sub-theme in `sections.md` and reads the whole draft, and it keeps the
dossier while doing it. Hand off to it when the user asks for a wide pass
in as many words, when a scope change they agreed to in step 2 has
invalidated the recorded queries, or when the draft is being re-targeted
at a different reader.

The rule was never "never re-search widely" -- it is **never do it
silently, and never in this skill**. Deliberately, nothing above tells
you how to run a wide search, so following this skill cannot produce one
by drift. Say what you think the request needs and let the user choose.

What stays never, in either skill, is re-running the genre skill. That
discards the dossier and pays to rediscover a worse version of it.

## When there is no dossier

Drafts written before `src/dossier.py` existed have none, and so do
drafts written by hand. Bootstrap rather than refusing:

```bash
python -m src.draft dossier init content/drafts/<path> --genre <genre>
```

Then fill in what the draft itself can tell you -- `sections.md` from
`python -m src.draft dossier sections`, and `scope.md`'s reader/covers/excludes
from the draft's own scope paragraph if it has one. Leave `evidence.md`
and `rejected.md` empty and **say so in chat**: the first revision of a
bootstrapped draft cannot check a claim against recorded evidence, and
may have to re-retrieve for a sub-theme that a real dossier would have
answered from disk. It gets cheaper from the second revision on.

Do not invent evidence entries to fill the file. An empty `evidence.md`
is honest; a fabricated one is the same failure class as a fabricated
citekey.

## Guardrails

- **Never re-run the genre skill to make a change.** If the request truly
  needs a new draft, say that and hand off explicitly. Wanting a wide
  re-search is not that case -- that is `corpus-reviser`, which keeps the
  dossier.
- **Never turn this into a wide pass.** Searching every sub-theme because
  the change felt big is the failure this skill is scoped to prevent, and
  it is why the instructions for doing so live in another skill. Say what
  you think the request needs and let the user pick.
- **Never refuse a wide pass either.** The scoped default is an economy,
  not a rule about what the user is allowed to want. Hand off to
  `corpus-reviser` rather than arguing.
- **Never run `python -m src.corpus sync` or `python -m src.enrich`.**
- **Never fabricate a citekey**, and never "fix" a gate failure by
  inventing a plausible-looking key -- correct it or remove the claim.
- **Never silently change scope, reader or terminology.**
- **Never let a copy-edit change a claim.** A style pass that quietly
  strengthens a hedge, drops a citation or reorders an argument is a
  substantive revision arriving in a diff the user is reading for
  spelling. Finish the wording, then say what you found and ask.
- **Never record a rejection you did not make.** Writing an unpursued
  candidate into `rejected.md` to tidy a drift report turns a title into
  a permanent judgment that every later revision trusts.
- **Report what you didn't do.** If the change requires re-searching a
  sub-theme and you judged it out of scope for this revision, say so
  rather than leaving a half-updated draft that looks finished.

## Sources

The prose standards this skill inherits are documented, with per-principle
attribution, in
[`docs/WRITING-STANDARDS.md`](../../../docs/WRITING-STANDARDS.md#sources-and-attribution).
What bears on revision specifically is Google's *Technical Writing
Courses* (CC-BY 4.0) rule that one concept keeps one name: in a fresh
draft that is a style preference, but a revision touching one section of
a document written weeks ago is exactly where a second name for an
existing concept gets introduced, which is why `scope.md`'s glossary is
read before anything is edited rather than checked afterwards.

---
name: draft-reviser-opencode
description: Revises an existing draft in content/drafts/ from its dossier instead of re-running the genre skill that produced it -- reads the recorded scope, reader, glossary, kept evidence and rejected candidates, edits only the affected sections, and logs what changed. Triggers when the user asks to revise, shorten, expand, restructure or correct an existing draft, including in a session that did not write it. Also covers copy-editing that touches no evidence ("fix the grammar", "convert this to British English", "make it en-GB") and re-grounding after the corpus moves ("re-ground", "a cited paper left the corpus", a `dossier status --all` report naming a draft). The cheap, scoped default for any change. A whole-corpus re-search ("search everything, cost regardless") is corpus-reviser-opencode; a NEW draft is a genre skill's job. Must pass `python -m chitragupta.draft gate` before presenting and never invents a citekey.
tags: [revision, dossier, citation]
---

# draft-reviser-opencode

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
| --- | --- |
| User asks to shorten, expand, restructure, correct or update an existing draft | Invoke this skill |
| User asks for a grammar pass, a spelling fix, a dialect conversion (en-US -> en-GB/en-IN), or rephrasing to meet a style guideline | This skill, in **copy-edit mode** (below) -- the loop's search and evidence steps short-circuit |
| User asks to re-target the draft at a **different reader** | Hand off to `corpus-reviser-opencode` -- what counts as support changes with the reader, so the kept set has to be re-judged, not extended |
| User asks for a **new** draft on a topic | Use the matching genre skill |
| The draft exists but has no dossier | Bootstrap one (below), then continue here |
| A sync moved the corpus, or `dossier status --all` names this draft | Re-grounding mode (below), not the ordinary loop |
| User asks to re-check the **whole** draft against the corpus, cost regardless | Hand off to `corpus-reviser-opencode` -- not this skill, and never the genre skill |
| User asks for a different genre of the same topic | That's a new draft -- use the genre skill |
| Ledger is empty or absent | Revise anyway if the change touches no citations; say so. **Never** run `python -m chitragupta.corpus sync`. In re-grounding mode, stop instead -- the ledger *is* the request |

**Read-only over the corpus layer.** Never run `python -m chitragupta.corpus
sync` and
never run `python -m chitragupta.enrich`. Both take the pipeline's write lock and
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
- **Figures follow the draft's own genre, not a fixed rule of this
  skill's own.** `scope.md`'s `genre:` line records one of `survey`,
  `thesis-chapter`, `textbook-chapter`, `tutorial` or `deep-research-opencode` --
  the matching skill's own drafting process (`survey-writer-opencode`,
  `thesis-chapter-writer-opencode`, `textbook-chapter-writer-opencode`, `tutorial-writer-opencode`,
  or `deep-research-opencode`) says how freely that genre calibrates
  `docs/WRITING-STANDARDS.md` §10's figures, from most (`tutorial`) to
  least (`survey`) to none at all (`deep-research-opencode`).
- **You may consult a source figure before redrawing one of your own.**
  `python -m chitragupta.draft figures <citekey>` lists a synced paper's
  figures -- caption, page, the string to cite each by, and the path to a
  crop -- for any citekey the section already cites. Worth running twice
  over: before revising a sentence that asserts what a paper's figure
  *shows* (the caption is retrievable as text and routinely says less
  than the picture), and before reworking a diagram of the draft's own.
  The source image never enters the draft and its layout is not yours to
  copy; the `cite` string is the part that belongs in prose. AGENTS.md
  has the boundary in full, and it is the same one `quote:` draws for
  wording.
- **Touch a figure, touch both forms.** Every figure exists twice -- as
  a TikZ picture in `figures/<name>.tex`, and as the plain-ASCII diagram
  in `figures/<name>.txt`, the same pair of files in every genre. Find
  them from the marker (`<!-- figure: ... -->` in a Markdown draft,
  `%figure:` in a `.tex` one), which is greppable precisely so this is
  not a reading exercise. Relabel a box, add an arrow, rename a
  component in one form and you must make the same change in the other.
  **A panelled figure's letters are part of that pair**: adding,
  dropping or re-ordering a panel re-letters every panel after it, in
  the picture *and* in the ASCII twin, and lettering an unlettered
  figure is a figure edit like any other -- log it in `revisions.md`.
  Which lettering to use is `scope.md`'s to say, not yours: it is a
  house-style decision under `docs/WRITING-STANDARDS.md` §8, read before
  the edit rather than re-decided during it.
  **One difference survives by genre, and it is not about where the
  files are**: `thesis-chapter-writer-opencode`'s TikZ additionally stays inline
  via a real `\input` -- that fragment is what the user `\input`s
  directly into their own thesis, so editing it means editing the
  fragment itself, not just `figures/<name>.tex` beside it. Every other
  form, in every genre, lives only in `figures/`.
  **Nothing checks any of this.** No gate, no style rule and no render
  error can tell that a picture and a diagram have stopped depicting
  the same thing,
  so a half-done edit leaves the pdf and the Markdown preview
  disagreeing about the same figure, silently, until a reader notices.
  **To redraw or fix the picture, hand it to `figure-drawer-opencode`** and
  come back to step 6 to log it: that skill owns the scaffolds, the
  compile probe and the geometry review, and it re-verifies the TikZ
  compiles before you keep it -- a figure that no longer compiles fails
  the whole pdf render, not just the figure. If the two forms
  have drifted too far to reconcile, say so and drop the figure rather
  than shipping a pair that disagrees.

- **Tables renumber themselves; ids do not.** `docs/WRITING-STANDARDS.md`
  §13 has the renderer assign every number, so inserting a table above
  another one is safe and there is nothing to renumber by hand -- if you
  find a literal "Table 3" in the prose of a draft you are revising,
  that is the defect, and the fix is an inline
  `<!-- tableref: <id> -->`. What a revision *can* break is an id:
  deleting a table whose id something still refers to, or copying a
  table into another section and copying its id with it. Both are
  reported by the prose check this skill already runs at its own step
  (§13's table findings, over the `<!-- table: <id> -->` markers beneath
  each caption) -- read those rather than eyeballing the markers. A
  table you add is a table you also introduce and read a pattern off; a
  table left standing with no sentence pointing at it is a
  `TableUnreferenced` finding and a reader's problem.

- **A captioned figure renumbers itself too; its id does not.** Issue
  411 gives a *captioned* figure the same contract, over the same
  `<!-- figure: ... -->` marker this skill already reads for "touch both
  forms" above -- a literal "Figure 2" in the prose is the defect, and
  the fix is an inline `<!-- figureref: <id> -->`. An **uncaptioned**
  figure has no id to protect and no number to write, but since #421 it
  is a finding of its own (`FigureNoCaption`) rather than an accepted
  state; the fix is a caption line, and it is the reader's gain, not a
  tidy-up. What a revision can still break for a captioned one is the
  id: deleting a figure something still refers to, or copying a figure
  into another section along with its id. Both are reported by this
  skill's own prose-check step (`FigureUnreferenced`, `FigureUnknownRef`,
  `FigureDuplicateId`) -- read those rather than eyeballing the markers.

- **An equation renumbers itself; its id does not.** #457 gives the same
  contract to a *numbered* equation, over the `<!-- equation: id -->`
  marker docs/WRITING-STANDARDS.md §12 has the renderer resolve -- a
  literal "Equation 3" in the prose is the defect, and the fix is an
  inline `<!-- equationref: <id> -->`. Unlike a table or a captioned
  figure, most equations in a draft are correctly **unnumbered**: §12's
  rule is standalone, final-of-a-derivation, or reused elsewhere, not
  every displayed equation, and deciding whether an equation you are
  revising now meets that bar is a judgment call this skill makes, not
  one `draft style` can make for it (§9 has no mechanical proxy for it).
  What a revision can still break for an already-numbered one is the
  id: deleting an equation something still refers to, or copying a
  numbered equation into another section along with its id. Both are
  reported by this skill's own prose-check step
  (`EquationUnreferenced`, `EquationUnknownRef`, `EquationDuplicateId`)
  -- read those rather than eyeballing the markers. An unattached
  `<!-- equation: id -->` left behind by a deleted or reflowed `<!--
  math -->` block is `EquationOrphanMarker`; delete the stray marker,
  the same conservative repair `agenda-reviser-opencode` uses, rather than
  guessing which block it meant.

## Collection scoping (#195): inherit it, do not re-ask

`scope.md` may carry a `collection:` line, written by the genre skill
that produced this draft. If it does, **every retrieval call in this pass
carries the same `--collection`**, and the user is not asked again.

This matters more here than it does at drafting time. A draft grounded
in one curated shelf that is then revised against the whole library has
silently changed what it is made of, and the change is invisible in the
diff: the citekeys are all real, the gate still passes, and nothing in
`retrieval.md` records that the scope moved (#254).

A missing line, or `- collection: (whole corpus)`, means search
everything -- exactly as this skill behaved before this section existed.

## The loop

### 1. Locate the draft and read its state

```bash
python -m chitragupta.draft dossier status content/drafts/<path>
```

This prints which dossier files are filled in, the draft's section count,
and whether the corpus has moved since the draft was written. A missing
or unreadable ledger is reported rather than raised -- it still tells you
what the dossier holds. A missing *dossier* is the one thing this command
treats as an error: it prints the `init` line and exits 1, which is your
cue to go to "When there is no dossier" below. (Only the plain form does
that; `--json`, used in re-grounding, exits 0 and reports it in the
payload instead.)

**If `status` reports the draft fingerprint `CHANGED since last stamp`**,
the draft was hand-edited since the last time this skill (or a human)
ran `dossier stamp` -- #454, FEATURE-ROADMAP.md's E3. That is not itself
a problem: a digest changing is expected of a draft anyone edits. What it
means is that the five findings under it, if any are listed, may be
real drift between the draft and the rest of the dossier rather than
something this revision is about to introduce. Offer each one to the
user **one at a time**, in your own words, and act only on what they
agree to -- never apply a repair unasked, and never block the revision
on an unanswered one:

| Finding | What to offer |
| --- | --- |
| a citekey is cited with no `evidence.md` block | add a block for it (treat it like a newly kept citation in step 6), or say why it doesn't need one |
| an `evidence.md` block for a citekey no longer cited | offer `python -m chitragupta.draft dossier prune <draft> --citekey <key> --apply`, the repair primitive that now exists for this (dry-run without `--apply`) -- or note that the citation belongs back in the draft. Log the run in `revisions.md`: the command deliberately does not, being a primitive, exactly as `dossier sections --citekeys --write` does not |
| a heading with no row in `sections.md` | run `dossier sections --citekeys --write`, the repair primitive that already exists for this |
| a `sections.md` row with no matching heading | the same command; a rename and a deletion both show up here |
| a `math.md` row appearing nowhere in the draft | update the row's key to the reworded span, or drop it if the quantity was cut |

A `not recorded` fingerprint means this draft has never been stamped --
say so once, and don't treat it as drift to chase. Note what that does
*not* excuse any more: a recorded-but-uncited citekey is now reported
by `review agenda` without a stamp baseline (#701), as a surfaced
`recorded-but-uncited` item and over `sections.md` as well as
`evidence.md`, so an unstamped draft is no longer silent about it.

**A `CHANGED` fingerprint is also FEATURE-ROADMAP.md's E4 trigger**: "a
draft fingerprint is what says the query moved." Once the five
findings above are settled -- never before, and never folded into the
same offer -- and only for a section `outline.md` declares one or more
`queries:` for, offer one more thing: *"Since you hand-edited
`<heading>`, I can also re-run that section's own declared query --
currently `<query, read fresh from outline.md>` -- with your new
wording appended: ITER-RETGEN with you in the generation slot, not a
model. Want me to?"* Always show the query text verbatim in the offer,
not just its existence -- `outline.md` is read fresh every time (never
cached), so if it was edited alongside the draft, this is the only
place that edit becomes visible before a real retrieval call spends
on it. If they agree, carry that section's current prose into step 4
below as `--y-prev`. If they decline, the section has no declared
query, or there is no `outline.md` for this draft **-- the common
case, since `outline.md` is opt-in --** say so and move on: there is
no declared query for round 2 to anchor to, so no offer is made at
all, not a silently degraded one. Never run this more than once per
section per revision session; two rounds is the whole mechanism, not
a loop to repeat. (Editing `outline.md`'s `queries:` alone, with the
draft untouched, is not itself a trigger -- see `plans/e4-draft-is-the-query.md`.)

Then read `scope.md` and `steering.md`. **Always both, always first.**
They are small, and they are what stops a revision from undoing an
earlier decision the user already made.

Mark the start of this revision session in `retrieval.md`, before any
retrieval call:

```bash
python -m chitragupta.draft dossier mark-revision content/drafts/<path> --label "<one phrase, e.g. what the user asked for>"
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
python -m chitragupta.draft dossier sections content/drafts/<path>
```

Read **only** the sections the change touches, using the printed line
ranges (`read` with `offset=<start>`, `limit=<lines>`). Do not read the
whole draft to change one section. Consult `sections.md` when you need to
know which section owns a citation without reading anything.

Two exceptions, and only two. A change that alters the draft's argument
(restructuring, or a claim that other sections lean on) needs a read of
the whole draft, and so does a copy-edit pass, which touches every section
by definition -- see "Copy-edit mode" below for the rest of what that
changes. Recognise either case and pay for it deliberately, rather than
defaulting to it. Note that reading the whole draft is still not
re-searching it -- if the evidence also has to be re-judged, that is
`corpus-reviser-opencode`.

### 4. Decide whether you need to search at all

Most revisions don't, and a copy-edit pass never does -- if you are in
that mode, skip to it now rather than working through this step.

Before any retrieval call:

- Check `evidence.md` -- the claim (or, in an older dossier, the
  `support:` quote) may already be recorded. `support:`-only blocks are
  never rewritten to the new shape -- read one as `quote:`, the
  conservative reading, since that is usually what it is.
- Check `rejected.md` -- if a candidate is listed there with a reason,
  **do not retrieve and re-judge it**. That list exists precisely to stop
  the most expensive repeated work in the pipeline.

Search only when the change opens genuinely new ground. If it does:

```bash
python -m chitragupta.draft retrieve search "<query>" --k 15 --collection "<from scope.md>" --log content/drafts/<path>
python -m chitragupta.draft retrieve evidence "<query>" --citekey <key> --log content/drafts/<path>
```

**If step 1's offer was accepted**, run that section's query as a
re-grounding round instead of a plain search:

```bash
python -m chitragupta.draft retrieve search "<the section's declared query>" \
    --y-prev "<the section's current, hand-edited prose>" \
    --k 15 --collection "<from scope.md>" --log content/drafts/<path> --origin reground
```

The CLI bounds `--y-prev` itself (1500 characters, on a word boundary,
and reports it if anything was cut) and merges the two rounds' results
before capping back to `--k` -- nothing here hand-truncates or
hand-merges. `--origin reground` is what lets `dossier status` count
this as the section's declared query having run, distinct from an
ordinary `declared` or `extended` call.

(or `chitragupta.enrich.embed_index.search()` in place of `search` where the
embedding stack has been built). `evidence` is optional -- reach for it
when a snippet is not enough to decide on a source you are minded to
cite. Score what you keep as `survey-writer-opencode` step 2 describes, and record
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

Use `edit` on the specific passage. Do not `write` the whole file: a
whole-file rewrite of a survey-length draft costs thousands of output
tokens, re-runs the citation-gate hook over everything, and produces a
diff the user cannot review.

Never write a citekey that isn't already in the draft, in `evidence.md`,
or in a `search()` result you just read. AGENTS.md's invariant is
unchanged here: **a fabricated citekey is the one failure this whole
pipeline exists to prevent.**

### 6. Write the dossier back

Update only what actually changed:

- `evidence.md` -- new kept citekeys, with `relevance:`, a `claim:` in your
  own words, and `quote:` only where a quotation earns its place
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
- `math.md` -- **only if the draft has one.** It maps the draft's ASCII to
  the LaTeX it renders as (docs/WRITING-STANDARDS.md §12), keyed on the
  exact span text, so any edit that adds, removes or *rewords* a quantity
  desyncs it. Add a row for a new one, drop the row for a deleted one,
  and change the key when you reword one. `render` reports what you
  missed -- `[math]` warnings for a gap or an orphan, and a hard failure
  for a `<!-- math -->` marker it cannot resolve -- so run step 7 and read
  its output rather than trusting this list.
- `revisions.md` -- append one entry: date, what changed, which sections,
  and why. A copy-edit pass logs one entry for the whole document and
  updates nothing else in this list; see "Copy-edit mode".

### 7. Gate, reference, render

```bash
python -m chitragupta.draft gate content/drafts/<path>
python -m chitragupta.draft references content/drafts/<path>          # .md drafts; see --heading below
python -m chitragupta.draft render content/drafts/<path> --format tex
python -m chitragupta.draft render content/drafts/<path> --format pdf
python -m chitragupta.draft render content/drafts/<path> --format md
```

Fix and re-run until the gate reports `OK`. **Never present a draft that
hasn't passed.** A `[missing-binary]` or `[error]` from `render_output`
is a one-line warning in chat and does not block presenting.

Once the gate passes, re-stamp the draft fingerprint -- the same point
`scope.md`'s corpus line is re-stamped at in re-grounding mode, and for
the same reason: stamping before the gate passes would record a
fingerprint for a draft that was never actually accepted.

```bash
python -m chitragupta.draft dossier stamp content/drafts/<path>
```

Two things the genre decides, which a reviser has to look up rather than
assume:

- **`--heading`, if the draft's references section is number-prefixed.**
  `chitragupta.draft references` finds the existing section by heading
  and replaces it; miss it and you append a second one. A numbered
  textbook chapter calls it `## N. References` (pass
  `--heading "N. References"`, or the numbering is silently dropped);
  every other genre, tutorials included, uses the bare `## References`
  default (#699 aligned the tutorial genre, whose earlier drafts say
  `## Further reading` -- rename that heading to `## References` before
  running this, or the command appends a second section and the render
  carries two bibliographies). Look at the draft's own heading before
  running this. Skip the command entirely for a `.tex` fragment, which
  manages its own bibliography.
- **A tutorial must still run.** `tutorial-writer-opencode`'s governing rule is
  that a tutorial which doesn't work is worse than none, because a
  learner who follows it exactly and hits an error concludes they are the
  problem. The citation gate does not check that -- a tutorial often has
  no citekeys for it to check at all. If you edited a step, a command, a
  version or an expected output, run the lesson from the top before
  presenting it, and update `scope.md`'s `## Verified environment` block
  with what you actually ran on. **Never present an unrun tutorial as if
  it were tested**; if you could not run it, say exactly that.

### Run the prose check

After step 7 and before presenting:

```bash
python -m chitragupta.draft style content/drafts/<path>
```

Paths in this skill are from the project root, not from this skill's
own folder.

Read `.claude/skills-common/references/prose-check.md` now and follow it:
what the check can and cannot see, and how to report what it finds.

**Say which findings are yours.** The check reads the whole file, so most
of what it reports predates this revision; a reviser who tidies all of it
has made a whole-document change nobody asked for. If the user wants them
acted on, that is **copy-edit mode** below: this same skill, one
`revisions.md` entry naming the convention.

### Run the verbatim scan

Before presenting, rebuild the section map and scan:

```bash
python -m chitragupta.draft dossier sections content/drafts/<path> --citekeys --write
python -m chitragupta.review verbatim scan content/drafts/<path>
```

The first command matters more here than in any writing skill, and it is
the one this skill never had: a revision is exactly what makes
`sections.md` wrong. Moving a claim between sections, dropping a citation
or adding one all change the heading-to-citekey relation, and the
embedding tier compares each section against the citekeys that section's
row records. Scanning against the pre-revision table checks the draft you
started with.

It earns its place after a revision specifically: text you rewrote to sit
closer to a source is exactly the text most likely to have drifted into its
wording, and a revision that moved a claim between sections can strand
borrowed phrasing in a paragraph that no longer cites anything. **A review
aid, not a gate: it is never a condition of presenting.**

Read `.claude/skills-common/references/verbatim-scan.md`
now and follow it: what to show, what the scan could not check, and
how to keep the report. Repairing a finding is `agenda-reviser-opencode`'s
job, and only if the user asks.

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

Then read `.claude/skills/draft-reviser/references/copy-edit.md` now and
follow it: what changes relative to the loop above, the dialect target,
the single `revisions.md` entry, and where a copy-edit stops being one.

**Still `edit`, never `write`, and now for a second reason.** Every
objection in step 5 holds. The new one is that the citation-gate plugin's
gate runs per write, so editing section by section gives you a mechanical
check that the rewrite has not mangled a citekey or a `\citep{}` -- the
safety net that makes an aggressive whole-document rewrite safe to attempt
at all. One `write` of the whole file trades that away exactly where the
risk is highest.

## Acronym-realignment mode

The prose check above (§9's newest row -- `chitragupta/style_acronym_drift.py`)
can report a glossary acronym whose recorded expansion has drifted from
the current vocabulary (`content/acronyms.toml` merged over the vendored
floor). Recognise a request to fix that finding -- "align this draft's
acronyms with my vocabulary", "the DT definition is stale", or the
finding itself pasted in -- and say you are in this mode before you
start, naming the term(s) involved.

Then read `.claude/skills/draft-reviser/references/acronyms.md` now and
follow it. Same guardrails as copy-edit mode, and `edit`, never `write`,
for the same gate-plugin reason step 5 above gives.

## Re-grounding after the corpus moves

When `python -m chitragupta.corpus sync` adds papers or drops stale ones, every
existing
draft moves with it and nothing says so. `dossier status --all` is what
notices; this is what acts on it. It is the same loop entered from a
report instead of a request, so steps 5, 6 and 7 above still apply
verbatim -- what changes is how the work is found.

Read `.claude/skills/draft-reviser/references/re-grounding.md` now and
work through its R1 to R5 in order.

## When a whole-corpus pass is what's wanted

Everything above optimises for the common case: a change touches one
sub-theme, so one sub-theme gets re-searched. That default is right often
enough to be the default, and wrong often enough to need a way out.

The way out is a different skill. **`corpus-reviser-opencode`** re-searches every
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

Drafts written before `chitragupta/dossier/` existed have none, and so do
drafts written by hand. Bootstrap rather than refusing:

```bash
python -m chitragupta.draft dossier init content/drafts/<path> --genre <genre>
```

Then fill in what the draft itself can tell you -- `sections.md` from
`python -m chitragupta.draft dossier sections`, and `scope.md`'s reader/covers/excludes
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
  re-search is not that case -- that is `corpus-reviser-opencode`, which keeps the
  dossier.
- **Never turn this into a wide pass.** Searching every sub-theme because
  the change felt big is the failure this skill is scoped to prevent, and
  it is why the instructions for doing so live in another skill. Say what
  you think the request needs and let the user pick.
- **Never refuse a wide pass either.** The scoped default is an economy,
  not a rule about what the user is allowed to want. Hand off to
  `corpus-reviser-opencode` rather than arguing.
- **Never run `python -m chitragupta.corpus sync` or `python -m chitragupta.enrich`.**
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
[`docs/WRITING-STANDARDS.md`](../../../docs/WRITING-STANDARDS.md#-sources-and-attribution).
What bears on revision specifically is Google's *Technical Writing
Courses* (CC-BY 4.0) rule that one concept keeps one name: in a fresh
draft that is a style preference, but a revision touching one section of
a document written weeks ago is exactly where a second name for an
existing concept gets introduced, which is why `scope.md`'s glossary is
read before anything is edited rather than checked afterwards.

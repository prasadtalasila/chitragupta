# ✏ Hand-editing a draft, and handing it back

Status: **reference.** Written 2026-09-22.

**Written for** an author who wants to open `content/drafts/<slug>.md`
in their own editor -- fixing a sentence, tightening a paragraph,
rewording something they already know how they want phrased -- rather
than asking a skill to do it, and then wants the pipeline to pick the
edit up cleanly on the next revision. **Assumed:** you already have a
finished, gated draft with a dossier under `content/dossiers/` --
[WRITING-PROCESS.md](WRITING-PROCESS.md#-phase-2-write-a-first-draft)
if you don't yet. **Not covered here:** the mechanism this rests on
([DOSSIER.md](DOSSIER.md#-the-draft-fingerprint-feature-roadmapmds-e3)),
or asking a skill to make the change for you instead of doing it by hand
([WRITING-PROCESS.md](WRITING-PROCESS.md#-phase-3-revise-a-draft)).

Related reading:

- [WRITING-PROCESS.md](WRITING-PROCESS.md#-handing-a-hand-edited-draft-back-for-the-next-iteration)
  -- the short version of this page, inside the full write/revise
  walkthrough.
- [DOSSIER.md](DOSSIER.md#-the-draft-fingerprint-feature-roadmapmds-e3) --
  the draft fingerprint's format and the five drift classes it checks,
  which this page walks through from the user's side.
- [DRAFT-ITERATION.md](DRAFT-ITERATION.md#-revising-a-draft) -- the
  reasoning behind `draft-reviser`'s loop, for whoever is changing the
  drafting layer itself rather than using it.
- [WRITING-STANDARDS.md](WRITING-STANDARDS.md) -- the prose, figure,
  table and equation rules a hand edit is just as bound by as a skill's
  own edit.

## 🧭 Table of contents

- [Why hand-edit at all](#-why-hand-edit-at-all)
- [Step 1: edit the file, at the same path](#-step-1-edit-the-file-at-the-same-path)
- [Step 2: leave the dossier alone](#-step-2-leave-the-dossier-alone)
- [Step 3: hand it back](#-step-3-hand-it-back)
- [What `draft-reviser` finds, and offers one at a time](#-what-draft-reviser-finds-and-offers-one-at-a-time)
- [The one thing it offers separately: re-grounding your new wording](#-the-one-thing-it-offers-separately-re-grounding-your-new-wording)
- [Traps specific to a hand edit](#-traps-specific-to-a-hand-edit)
- [What this is not](#-what-this-is-not)
- [Worked example](#-worked-example)

## 🎯 Why hand-edit at all

Nothing about this pipeline requires you to route every change through
a skill. Asking `draft-reviser` for "shorten the third paragraph" costs
a model turn and, if the change opens new ground, a retrieval call. If
you already know the three words you want changed, opening the file and
changing them is strictly cheaper -- there is no drafting-layer step
that only a skill can perform on plain prose.

What you give up by doing it yourself is the bookkeeping a skill does as
it edits: nothing updates `sections.md`, `evidence.md` or `steering.md`
for you, and nothing tells the citation gate your edit happened until
you ask for something next. That bookkeeping is what the rest of this
page is about -- not because you have to restore it by hand, but because
knowing what's now out of sync is what makes the *next* revision cheap
again instead of confused.

## ✅ Step 1: edit the file, at the same path

Open `content/drafts/<slug>.md` and change it directly, with whatever
editor you like. Two constraints, both load-bearing:

- **Keep the path.** There is no `dossier rename`. Saving the same
  content under a different filename orphans its dossier --
  `content/dossiers/<the old path minus its suffix>/` still exists, but
  nothing will ever find it from the new path again, and a
  fresh `dossier init` on the new path starts from nothing.
- **Ordinary prose changes are unconditionally safe.** Nothing checks
  your wording as you type, and nothing needs to. The one mechanical
  gate in this pipeline is `citation_gate`, and it runs on the file you
  saved regardless of who wrote the last sentence.

Nothing runs automatically when you save. You do not have to open a
terminal, run a command, or tell the pipeline anything at this point --
the next section covers when that changes.

## 🗂 Step 2: leave the dossier alone

Do not hand-edit anything under `content/dossiers/<slug>/` --
`evidence.md`, `rejected.md`, `sections.md`, `scope.md`,
`steering.md`, `retrieval.md` or `revisions.md`. Three reasons, in
order of how often they bite:

- **A fabricated `evidence.md` block is the same failure class as a
  fabricated citekey.** Writing a `claim:`/`quote:` pair for a source
  you have not actually re-checked against `content/ledger.sqlite` is
  exactly what [CLAUDE.md](../CLAUDE.md)'s one rule exists to prevent,
  even though nothing enforces it the way `citation_gate` enforces a
  citekey.
- **The bookkeeping is generated, and hand-writing it just gets
  overwritten or contradicted.** `sections.md` is rebuilt wholesale by
  `python -m chitragupta.draft dossier sections <draft> --citekeys
  --write`; a hand edit to it survives only until the next run.
- **It's the wrong layer for what you're trying to say.** If you want to
  record *why* you made a change, that belongs in `steering.md`, and the
  right way to get it there is to say it in the request you hand the
  draft back with (Step 3) -- not to type an entry into the file
  yourself. `draft-reviser` appends it, dated, in your own words.

The only file this page asks you to touch is the draft itself.

## 🔁 Step 3: hand it back

You don't need a special phrase. Ask for whatever you actually want
next, the same way you would for a change you hadn't already started by
hand:

- "I tightened the intro -- can you check the rest reads consistently
  with it?"
- "I fixed a typo in section 3, no other changes."
- "I reworded the claim about latency in section 2 -- can you find a
  source for the new number?"

Or run the status check yourself first, if you want to see what the
pipeline noticed before asking for anything:

```bash
python -m chitragupta.draft dossier status content/drafts/<slug>.md
```

Either way, the first thing that happens -- inside `draft-reviser`, or
in the output of that command -- is a comparison between a digest of
the draft's current text and the one recorded at the last
`dossier stamp`. That comparison is what the rest of this page walks
through.

## 🔍 What `draft-reviser` finds, and offers one at a time

A changed digest by itself only means *the draft moved since it was last
stamped* -- most hand edits are prose a reviser has no reason to act on,
so a changed digest alone is not itself a problem, and `status` doesn't
chase it as one. It gates five more specific checks
([DOSSIER.md](DOSSIER.md#-the-draft-fingerprint-feature-roadmapmds-e3)
has the full format):

| What changed by hand | What `status` reports | What `draft-reviser` offers |
| --- | --- | --- |
| You added a citation | a citekey cited with no `evidence.md` block | add a block for it -- treated like a newly kept citation, so you'll be asked what the source actually says |
| You removed a citation | an `evidence.md` block whose citekey is no longer cited | `python -m chitragupta.draft dossier prune content/drafts/<slug>.md --citekey <key> --apply` (dry-run without `--apply`), or note that the citation belongs back in the draft |
| You added, renamed or moved a heading | a heading with no row in `sections.md` | `python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write`, which rebuilds the map from the draft itself |
| You deleted a heading | a `sections.md` row with no matching heading | the same command -- a rename and a deletion both show up here, so `draft-reviser` reads the diff to tell which one happened |
| You reworded or deleted a numbered equation | a `math.md` row appearing nowhere in the draft | update the row's key to the new span text, or drop the row if the quantity was cut |

Two things about how these are offered, not just what they are:

- **One at a time, in the reviser's own words**, and it acts only on
  what you agree to. It never applies a repair unasked, and it never
  blocks the rest of your revision on a finding you haven't answered
  yet -- you can say "leave that one, just do what I originally asked"
  and it will.
- **`not recorded` is not the same as `CHANGED`.** If the draft has
  never been stamped, `status` says so once and doesn't treat it as
  drift to chase -- there is nothing to compare against yet.

Nothing here is a gate. A hand-edited draft that's never handed back for
a stamp just makes the *next* revision a little less efficient -- the
skill re-derives what it would otherwise have read straight off
`sections.md` -- it cannot make the draft wrong, because
`python -m chitragupta.draft gate` still stands between any draft and
its citekeys, on every render, regardless of how the draft got to its
current state.

## 🎯 The one thing it offers separately: re-grounding your new wording

If the section you hand-edited has a `queries:` line declared for it in
`outline.md`, `draft-reviser` makes a second, separate offer once the
five findings above are settled -- never folded into the same prompt as
those:

> *"Since you hand-edited `<heading>`, I can also re-run that section's
> own declared query -- currently `<query, shown to you verbatim>` --
> with your new wording appended: ITER-RETGEN with you in the generation
> slot, not a model. Want me to?"*

Accepting runs the section's query a second time, `--y-prev` set to your
new prose (the retrieval CLI bounds this at 1500 characters on a word
boundary and reports if anything was cut), merges the two rounds by
citekey, and caps back to `--k`. This is
[ITER-RETGEN](RAG.md) (Shao et al., *Findings of EMNLP 2023*) with a
person standing in the generation slot instead of a model -- the same
mechanism a skill would use to refine its own draft against feedback,
running here because *your* rewrite is the feedback.

Declining, or having no `outline.md` at all, is the common case --
`outline.md` is opt-in, most sections have no declared query, and
`draft-reviser` says so and moves on rather than degrading silently into
something else. This runs at most once per section per revision session;
it is two rounds, not a loop.

## ⚠ Traps specific to a hand edit

Everything in [WRITING-STANDARDS.md](WRITING-STANDARDS.md) binds a hand
edit exactly as hard as it binds a skill's own edit -- nothing about
typing the change yourself relaxes a rule, and nothing mechanical is
watching for these while you type:

- **A figure exists twice.** Every figure is a TikZ picture in
  `figures/<name>.tex` and a plain-ASCII diagram in
  `figures/<name>.txt`, found from the same `<!-- figure: ... -->`
  marker. Relabel a box or rename a component in the draft's prose and
  you've usually also touched what the figure depicts -- update both
  forms, or the PDF and the Markdown preview silently disagree about the
  same figure until a reader notices. A panelled figure's letters are
  part of the pair too: adding or reordering a panel re-letters every
  panel after it, in both forms.
- **Table, figure and equation ids don't renumber themselves the way
  their displayed numbers do.** The renderer assigns every number, so a
  literal "Table 3" or "Figure 2" typed into your new prose is already
  wrong the moment another one is inserted above it -- write
  `<!-- tableref: <id> -->` / `<!-- figureref: <id> -->` instead. What a
  hand edit can break is the id itself: deleting a table, figure or
  numbered equation that something else still points at, or copying one
  into another section along with its id.
- **These are caught, but only after you hand the draft back.**
  `python -m chitragupta.draft style` is what surfaces
  `TableUnreferenced`, `TableUnknownRef`, `TableDuplicateId`,
  `FigureUnreferenced`, `FigureUnknownRef`, `FigureDuplicateId`,
  `EquationUnreferenced`, `EquationUnknownRef` and
  `EquationDuplicateId`, and `python -m chitragupta.draft render` prints
  the `[math]` warnings -- none of it runs while you're editing in your
  own editor, only once `draft-reviser` (or you, by hand) runs the same
  commands it would.
- **A whole-document pass -- grammar, dialect, hedging -- is still worth
  asking a skill for rather than doing by hand.** `draft-reviser`'s
  copy-edit mode reads `scope.md`'s recorded `language:` line so the
  convention it applies is the one already agreed, and it refuses to let
  a wording pass quietly change a claim
  ([DRAFT-ITERATION.md](DRAFT-ITERATION.md#-the-copy-edit-pass-and-the-entry-it-leaves)).
  A hand edit has no such guardrail -- it's on you not to let "read
  better" turn into "claims something new."

## 🚫 What this is not

- **Not a way to add a new claim for free.** Typing a new sentence with
  a fact in it and no citation is exactly what
  [REVIEW.md](REVIEW.md)'s uncited-claim aid and
  `python -m chitragupta.review agenda` are for catching on the next
  pass -- a hand edit doesn't get a pass on being grounded just because
  no skill wrote it.
- **Not a way to introduce a citekey.** `citation_gate` reads the draft
  file itself, not who last edited it, and refuses one that was never
  synced from your own `.bib` export -- see [CLAUDE.md](../CLAUDE.md)'s
  one rule. If the fact you're adding needs a source, ask `draft-reviser`
  for it rather than typing a citekey you remember from somewhere else.
- **Not a substitute for the gate before presenting.** Whatever you
  changed by hand, run (or have `draft-reviser` run)
  `python -m chitragupta.draft gate`,
  `python -m chitragupta.draft references` and
  `python -m chitragupta.draft render` before treating the draft as
  finished again.

## 🧪 Worked example

You open `content/drafts/dt/survey.md`, reword the topic sentence of
section 2 so it leads with the claim more directly, and delete a
citation to a paper you decided doesn't actually support that sentence.
You save the file and nothing else.

Later, you ask: *"I tightened section 2 and cut the Doe 2024 citation --
can you check the rest of the draft still reads consistently?"*

`draft-reviser` runs `dossier status`, sees `CHANGED since last stamp`,
and reports one finding: `doe_x_2024` has an `evidence.md` block with no
matching citation in the draft. It offers to prune the block. You agree.
If section 2 has a declared query in `outline.md`, it then offers, once,
to re-run that query with your new topic sentence as `--y-prev`. You
decline -- you're confident the paragraph is fine as reworded. It reads
the rest of the draft for the consistency check you actually asked for,
edits nothing else, appends one line to `steering.md` dated today, runs
the gate, and re-stamps the fingerprint once it passes.

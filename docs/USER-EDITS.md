# ✏ Hand-editing a draft, and handing it back

Status: **reference.**

**Written for** an author who wants to edit `content/drafts/<slug>.md`
in their own editor instead of asking a skill, and then have the
pipeline pick the edit up cleanly on the next revision. **Assumed:** you
already have a finished, gated draft with a dossier under
`content/dossiers/`
([WRITING-PROCESS.md](WRITING-PROCESS.md#-phase-2-write-a-first-draft)
if you don't yet). **Not covered here:** the draft fingerprint this
rests on and the drift classes it checks
([DOSSIER.md](DOSSIER.md#-the-draft-fingerprint-feature-roadmapmds-e3)),
or asking a skill to make the change for you
([WRITING-PROCESS.md](WRITING-PROCESS.md#-phase-3-revise-a-draft)).

[WRITING-PROCESS.md](WRITING-PROCESS.md#-handing-a-hand-edited-draft-back-for-the-next-iteration)
has the short version of this page.
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) binds a hand edit as much
as a skill's own edit.

## 🎯 Why hand-edit at all

Asking `draft-reviser` for a change costs a model turn and sometimes a
retrieval call. If you already know the three words you want changed,
changing them yourself is cheaper; no step on plain prose needs a skill.

What you give up is the bookkeeping a skill does as it edits: nothing
updates `sections.md`, `evidence.md` or `steering.md` for you. You do
not have to restore it by hand, but knowing what is out of sync keeps
the *next* revision cheap.

## ✅ Step 1: edit the file, at the same path

Open `content/drafts/<slug>.md` and change it directly, with whatever
editor you like.

- **Keep the path.** There is no `dossier rename`. Saving under a
  different filename orphans the dossier at
  `content/dossiers/<the old path minus its suffix>/`, and a fresh
  `dossier init` on the new path starts from nothing.
- **Ordinary prose changes are unconditionally safe.** The one
  mechanical gate, `citation_gate`, runs on the file you saved
  regardless of who wrote the last sentence.

Nothing runs automatically when you save, and you need not tell the
pipeline anything yet.

## 🗂 Step 2: leave the dossier alone

Do not hand-edit anything under `content/dossiers/<slug>/`:
`evidence.md`, `rejected.md`, `sections.md`, `scope.md`,
`steering.md`, `retrieval.md`, `revisions.md`, and `math.md` or
`outline.md` where the draft has them:

- **A fabricated `evidence.md` block is the same failure class as a
  fabricated citekey.** A `claim:`/`quote:` pair for a source you have
  not re-checked is what [CLAUDE.md](../CLAUDE.md)'s one rule exists to
  prevent, even though nothing enforces it the way `citation_gate`
  enforces a citekey.
- **The bookkeeping is generated.** `sections.md` is rebuilt wholesale
  by `python -m chitragupta.draft dossier sections <draft> --citekeys
  --write`, so a hand edit to it survives only until the next run.
- **It's the wrong layer.** To record *why* you made a change, say it
  in the request you hand the draft back with (Step 3), and
  `draft-reviser` appends it to `steering.md`, dated, in your words.

## 🔁 Step 3: hand it back

You don't need a special phrase. Ask for whatever you want next:

- "I tightened the intro. Can you check the rest reads consistently
  with it?"
- "I fixed a typo in section 3, no other changes."
- "I reworded the claim about latency in section 2. Can you find a
  source for the new number?"

Or run the status check yourself first:

```bash
python -m chitragupta.draft dossier status content/drafts/<slug>.md
```

Either way, the first step compares a digest of the draft's current
text with the one recorded at the last `dossier stamp`.

## 🔍 What `draft-reviser` finds, and offers one at a time

A changed digest only means *the draft moved since it was last
stamped*, which is not a problem by itself. It gates five more specific
checks:

| What changed by hand | What `status` reports | What `draft-reviser` offers |
| --- | --- | --- |
| You added a citation | a citekey cited with no `evidence.md` block | add a block for it, treated like a newly kept citation, so you'll be asked what the source actually says |
| You removed a citation | an `evidence.md` block whose citekey is no longer cited | `python -m chitragupta.draft dossier prune content/drafts/<slug>.md --citekey <key> --apply` (dry-run without `--apply`), or note that the citation belongs back in the draft |
| You added or renamed a heading | a heading with no row in `sections.md` | `python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write`, which rebuilds the map from the draft itself |
| You deleted or renamed a heading | a `sections.md` row with no matching heading | the same command; a rename shows up as one row of each kind and a deletion as this row alone, so `draft-reviser` reads the diff to tell which one happened |
| You moved a section or subsection without renaming it | nothing: the check compares the set of heading titles, not their order | nothing is needed; the same command puts the `sections.md` rows back in draft order, and each citekey follows the lines it moved with |
| You reworded or deleted text `math.md` maps to LaTeX | a `math.md` row appearing nowhere in the draft | update the row's key to the new span text, or drop the row if the quantity was cut |

How these are offered:

- **One at a time, in the reviser's own words**, acting only on what you
  agree to. It never applies a repair unasked and never blocks the rest
  of your revision on an unanswered finding.
- **`not recorded` is not the same as `CHANGED`.** An unstamped draft
  has nothing to compare against, so `status` says so once and runs none
  of the five checks. `python -m chitragupta.review agenda <draft>`
  still notices a removed citation: its `recorded-but-uncited` item needs
  no stamp.
- **`dossier status --json` leaves the fingerprint out.** It reports
  corpus drift only. Read the plain-text output for the five findings.

Nothing here is a gate. A hand-edited draft never re-stamped only makes
the next revision less efficient. It cannot make the draft wrong, because
`python -m chitragupta.draft gate` still checks its citekeys on every
render.

## 🎯 The one thing it offers separately: re-grounding your new wording

If the section you hand-edited has a `queries:` line in `outline.md`,
`draft-reviser` makes a second, separate offer once the five findings
are settled:

> *"Since you hand-edited `<heading>`, I can also re-run that section's
> own declared query (currently `<query, shown to you verbatim>`)
> with your new wording appended: ITER-RETGEN with you in the generation
> slot, not a model. Want me to?"*

Accepting runs the section's query a second time with `--y-prev` set
to your new prose (bounded at 1500 characters on a word boundary, with a
report if anything was cut), merges the two rounds by citekey, and caps
back to `--k`. This is
[ITER-RETGEN](https://github.com/prasadtalasila/chitragupta/blob/main/docs/RAG.md)
(Shao et al., *Findings of EMNLP 2023*) with your rewrite as the
feedback.

Declining, or having no `outline.md`, is the common case, and
`draft-reviser` says so and moves on. It runs at most once per section
per revision session: two rounds, not a loop.

## 🗺 Edit by edit: what the dossier records and what notices

Only a skill or a repair command writes the dossier. Which records
each kind of edit leaves behind, and what reports them:

| Your edit | What the dossier records about it | What notices | The repair |
| --- | --- | --- | --- |
| Delete a sentence or passage that cites a source | the citekey's `evidence.md` block and its `sections.md` entry; both stay | `dossier status` (stamped draft only) and `review agenda` (any draft). `draft gate` does not: it checks citekeys against the ledger and never reads the dossier | `dossier prune --citekey <key> --apply`, then `dossier sections --citekeys --write`. `rejected.md` is never touched |
| Move a section or a subsection | `sections.md` rows, keyed by heading title alone; `evidence.md` has no section field | nothing, if the titles are unchanged. A rename or deletion shows in `dossier status`. A figure, table or equation moved away from the sentence that refers to it shows as `*RefOutsideSection` in `draft style` | optional `dossier sections --citekeys --write`; `outline.md` headings by hand, since nothing checks them |
| Add, delete or change a figure | nothing: a figure lives in the draft's `<!-- figure: name -->` marker and `figures/<name>.tex` / `figures/<name>.txt`, not in the dossier | `draft style` (`FigureNoCaption`, `FigureUnreferenced`, `FigureUnknownRef`, `FigureDuplicateId`) and `draft render` (a marker whose file is missing). Nothing checks that the two forms still show the same thing, or reports a figure file no marker uses | update both forms by hand, or ask for the change in words: `draft-reviser` logs it and `figure-drawer` redraws it ([FIGURE-DRAWER.md](FIGURE-DRAWER.md)) |
| Add, delete or change an equation | `math.md` rows mapping exact span text to LaTeX; numbered equations are draft markers, not dossier rows | `dossier status` reports a `math.md` row whose span is gone. `draft render` warns on that and on a span with no row, and fails outright on a displayed `<!-- math -->` block with no row or no `math.md` at all. `draft style` checks `<!-- equation: id -->` markers | edit the `math.md` row; there is no command for it |

Two limits apply to the whole table. The `draft style` checks cover
Markdown drafts only: a `.tex` fragment's `\label`/`\eqref` pairs are
not checked. And the book track's `python -m chitragupta.draft spec align
<book>` is the only check that notices a reordering, comparing a
chapter's headings against the sections its signed `spec.md` declares;
it does not run on an ordinary draft in `content/drafts/`.

## ⚠ Traps specific to a hand edit

Typing the change yourself relaxes no rule, and nothing watches for
these while you type:

- **A figure exists twice**, as TikZ in `figures/<name>.tex` and ASCII
  in `figures/<name>.txt`, found from the same `<!-- figure: ... -->`
  marker. Relabel a component in the prose and you have usually touched
  what the figure depicts. Update both forms, or the PDF and the
  Markdown preview silently disagree. Adding or reordering a panel
  re-letters every panel after it, in both forms.
- **Ids don't renumber themselves the way displayed numbers do.** A
  literal "Table 3" typed into your prose is wrong once another table is
  inserted above it; write `<!-- tableref: <id> -->` /
  `<!-- figureref: <id> -->` instead. What a hand edit can break is the
  id itself: deleting a table, figure or numbered equation something
  still points at, or copying one along with its id.
- **These are caught only after you hand the draft back.**
  `python -m chitragupta.draft style` surfaces `TableUnreferenced`,
  `TableUnknownRef`, `TableDuplicateId`, `FigureUnreferenced`,
  `FigureUnknownRef`, `FigureDuplicateId`, `EquationUnreferenced`,
  `EquationUnknownRef` and `EquationDuplicateId`, and
  `python -m chitragupta.draft render` prints the `[math]` warnings.
- **Ask a skill for a whole-document pass (grammar, dialect, hedging).**
  `draft-reviser`'s copy-edit mode applies `scope.md`'s recorded
  `language:` line and refuses to let a wording pass silently change a
  claim
  ([DRAFT-ITERATION.md](DRAFT-ITERATION.md#-the-copy-edit-pass-and-the-entry-it-leaves)).
  A hand edit has no such guardrail.

## 🚫 What this is not

- **Not a way to add a new claim for free.** A new uncited fact is what
  [REVIEW.md](REVIEW.md)'s uncited-claim aid and
  `python -m chitragupta.review agenda` catch on the next pass.
- **Not a way to introduce a citekey.** `citation_gate` refuses one that
  was never synced from your own `.bib` export (see
  [CLAUDE.md](../CLAUDE.md)'s one rule). If the fact needs a source, ask
  `draft-reviser` for it instead of typing a citekey you remember.
- **Not a substitute for the gate before presenting.** Whatever you
  changed by hand, run (or have `draft-reviser` run)
  `python -m chitragupta.draft gate`,
  `python -m chitragupta.draft references` and
  `python -m chitragupta.draft render` before treating the draft as
  finished again.

## 🧪 Worked example

You open `content/drafts/dt-overview/survey.md`, reword the topic
sentence of section 2, and delete every citation to a paper you decided
doesn't support the draft. You save the file and nothing else.

Later, you ask: *"I tightened section 2 and cut the factory paper's citations.
Can you check the rest of the draft still reads consistently?"*

`draft-reviser` runs `dossier status`, sees `CHANGED since last stamp`,
and reports one finding: `sample_dt_factory_2022` has an `evidence.md`
block with no matching citation in the draft. It offers to prune the
block. You agree. If section 2 has a declared query in `outline.md`, it
then offers, once, to re-run that query with your new topic sentence as
`--y-prev`; you decline. It reads the rest of the draft for the
consistency check you asked for, edits nothing else, appends one line to
`steering.md` dated today, runs the gate, and re-stamps the fingerprint
once it passes.

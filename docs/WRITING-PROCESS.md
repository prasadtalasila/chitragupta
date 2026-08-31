# ✍ Writing process: from a bare corpus to a finished draft or book

Status: **reference.** Written 2026-08-30. Updated 2026-08-31, with the
command surface for writing and revising a draft, and how a hand-edited
draft is picked back up.

**Written for** someone about to write with this pipeline, start to
finish -- the order the phases happen in, and which document has the
detail for each. **Assumed:** none of the setup has happened yet; if
your corpus is already synced, skip to whichever phase you're at.
**Not covered here:** which genre to pick, in detail
([GENRE.md](GENRE.md)); every flag and every command this pipeline
exposes ([CLI.md](CLI.md)); config knobs ([CONFIG.md](CONFIG.md)); how
to get your library into shape ([ZOTERO.md](ZOTERO.md)). This document
is the map between those; each has the depth this one deliberately
skips.

## 🧭 Table of contents

- [Phase 1: set up your corpus](#-phase-1-set-up-your-corpus)
- [Phase 2: write a first draft](#-phase-2-write-a-first-draft)
- [Phase 3: revise a draft](#-phase-3-revise-a-draft)
- [Handing a hand-edited draft back for the next iteration](#-handing-a-hand-edited-draft-back-for-the-next-iteration)
- [Phase 4: write book chapters](#-phase-4-write-book-chapters)
- [Phase 5: assemble the book](#-phase-5-assemble-the-book)

## 📚 Phase 1: set up your corpus

Everything downstream reads from one place: a BibTeX export with its
PDFs attached, turned into a ledger this pipeline can search.

1. **Export your Zotero library** as BibTeX with "Export Files" ticked,
   into `papers/bibliography.bib` (plus its companion
   `papers/bibliography/files/` folder). Do not rename or move that
   folder afterwards -- each entry's file path is relative to it.
   [ZOTERO.md](ZOTERO.md) has the full export walkthrough and the
   attachment-path trap that silently leaves an entry without a PDF.
2. **Sync the corpus layer**: `chitragupta corpus sync`. A citekey that
   later drops out of your `.bib` file is only reported, never deleted,
   unless you pass `--remove-stale` -- [ZOTERO.md](ZOTERO.md) says why
   the safer default is report-only.
3. **Inspect what it found**: `chitragupta corpus ledger` (read-only,
   takes no lock).
4. **Optional: the enrichment layer.** Layout-aware parsing, semantic
   search, topic clustering -- a second, deliberate pass over the same
   corpus. Nothing in Phase 2 needs it, and no skill builds it for you.
   `chitragupta enrich --stages docling,embed` when you want it; which
   stage is worth the cost is in [RETRIEVAL.md](RETRIEVAL.md).

## ✍ Phase 2: write a first draft

| Step | What | Command | Who runs it |
| --- | --- | --- | --- |
| 1 | Optional: declare your own structure | `chitragupta draft dossier init content/drafts/<slug>.md --genre <genre> --outline`, then edit the `outline.md` it writes | you |
| 2 | Ask for the draft, in plain words | e.g. "write a survey section on digital twin composability" | you |
| 3 | Retrieve evidence, write the draft, and run its own gate -> references -> render chain | `chitragupta draft gate`, `chitragupta draft references`, `chitragupta draft render` -- the same three commands as [CLI.md](CLI.md#-the-full-first-run-step-by-step) step 9, which you can also run by hand | the matching skill |
| 4 | Read what it wrote | the draft under `content/drafts/`, its dossier under `content/dossiers/`, and -- for four of the five genres -- its evidence sidecar | you |

**Ask for it in plain words.** You do not invoke a skill by name --
"write a survey section on digital twin composability", "draft a thesis
chapter on runtime verification for autonomous robots", "write a
textbook chapter introducing digital twin asset reuse", "write a
tutorial that builds a minimal digital twin asset from scratch", "do
deep research on fault injection for digital twin testbeds". The
matching skill picks the request up and runs step 3 above for you.

**Which of the five genres actually matches what you asked for** is
[GENRE.md](GENRE.md#-picking-one)'s whole job -- read it if you're not
sure whether what you want is a survey, a thesis chapter, a textbook
chapter, a tutorial, or a deep-research report. The short version: it
comes down to what your reader is doing while they read -- entering a
field, reading adversarially for a claim, studying worked examples,
following you at a keyboard, or reconciling several perspectives.

**Step 1 is optional, and is the only step before you ask.** It writes
`outline.md`, where you set out each section's `brief:`, one or more
`claim:` blocks, and optionally the exact `queries:` to search -- the
skill runs those verbatim instead of inventing sub-themes.
[DOSSIER.md](DOSSIER.md) has the format.

Every finished draft gets a **dossier** in `content/dossiers/` --
working state a later session reloads instead of re-running everything
-- and, for four of the five genres, an **evidence sidecar** listing
what each cited source actually said
([DOSSIER.md](DOSSIER.md#-the-evidence-sidecar-decided-per-genre)).
Neither is committed to git.

## 🔁 Phase 3: revise a draft

**Never re-run the genre skill that wrote it.** Ask for the change in
plain words -- "shorten the third section", "add adoption economics",
"fix the grammar" -- and the matching reviser picks it up, working from
the dossier instead of redoing the research:

| You want... | Ask for | What it does |
| --- | --- | --- |
| An ordinary change: shorten, expand, restructure, correct, copy-edit | `draft-reviser` (the default -- picked automatically) | Reads the dossier, edits only the affected sections, re-searches only when the change opens genuinely new ground. The cheapest path there is |
| The whole corpus re-searched, cost regardless | say so explicitly -- "re-check the entire draft against the corpus" | `corpus-reviser`. Re-runs every recorded sub-theme query against the current corpus, honouring what was already rejected and why |
| A repair queued by a review scan | "work the review agenda" | `agenda-reviser`. Fixes one unattended finding at a time -- a short verbatim run, a prose issue, an uncited claim -- never applies a repair unasked, and re-verifies every fix through the gate |

**The default path, step by step.**
[DRAFT-ITERATION.md](DRAFT-ITERATION.md#-revising-a-draft) has the full
reasoning behind each step; this is the command surface `draft-reviser`
runs:

| Step | What | Command | Who runs it |
| --- | --- | --- | --- |
| 1 | Check what's on disk, whether the corpus moved, and whether the draft itself moved since the last stamp | `chitragupta draft dossier status content/drafts/<slug>.md`, then `chitragupta draft dossier mark-revision content/drafts/<slug>.md` before any retrieval | skill |
| 2 | Read the recorded scope and steering, so the change stays inside what you already agreed | reads `scope.md`, `steering.md` | skill |
| 3 | Find the affected sections | `chitragupta draft dossier sections content/drafts/<slug>.md --citekeys --write` | skill |
| 4 | Edit only those sections, at their line ranges | -- | skill |
| 5 | Re-search only if the change opens genuinely new ground, honouring `rejected.md` first | `chitragupta draft retrieve search "<query>" --log content/drafts/<slug>.md` | skill |
| 6 | Update the dossier for whatever actually changed | writes `evidence.md`/`rejected.md`/`sections.md`, appends to `revisions.md`/`steering.md` | skill |
| 7 | Re-gate, rebuild references, re-render, then stamp -- only once the gate passes | `chitragupta draft gate`, `chitragupta draft references`, `chitragupta draft render`, `chitragupta draft dossier stamp content/drafts/<slug>.md` | skill |

The copy-edit pass -- a grammar fix, a dialect conversion, a rephrase to
meet a style guideline -- is the one exception: steps 3 and 5 never run,
it reads and edits the whole draft rather than one section, and it
leaves a single `revisions.md` entry naming the convention applied
rather than the sections touched.
[DRAFT-ITERATION.md](DRAFT-ITERATION.md#-the-copy-edit-pass-and-the-entry-it-leaves)
has why that inversion is still the cheap path.

`draft-reviser` also handles **re-grounding**: when a corpus sync
removes a paper your draft cites, or -- once you've hand-edited a
section -- when you want that section's own new wording to drive one
extra retrieval round (ITER-RETGEN with you standing in for the model,
[DOSSIER.md](DOSSIER.md#-the-fingerprint-as-a-retrieval-trigger-456-feature-roadmapmds-e4)).

### ✏ Handing a hand-edited draft back for the next iteration

You don't have to route a change through a skill at all. Open
`content/drafts/<slug>.md` in your own editor and change it directly, at
the same path -- there is no `dossier rename`, so saving it under a
different path orphans its dossier, and every equation in the draft
silently reverts to typewriter text on the next render
([DOSSIER.md](DOSSIER.md#-the-draft-fingerprint-454-feature-roadmapmds-e3)).

Nothing runs automatically when you save, and you don't have to tell the
pipeline you edited it. The next time you ask for a revision -- or run
`chitragupta draft dossier status content/drafts/<slug>.md` yourself --
step 1 above compares a digest of the draft's current text against the
one recorded at the last `dossier stamp`. A changed digest reports
`CHANGED since last stamp` and only then checks four more specific
things your edit might have caused: a citation you added with no
`evidence.md` block, an `evidence.md` block for a citation you removed,
a heading with no row in `sections.md`, and a `sections.md` row with no
matching heading. `draft-reviser` offers each finding to you one at a
time and acts only on what you agree to -- it never applies a repair
unasked, and it never blocks the revision on one going unanswered.
(`agenda-reviser` is the one exception: it may not touch `scope.md`, so a
repair it makes leaves the fingerprint deliberately stale -- the honest
signal that an automated pass, not your own revision session, touched
the draft since anyone last confirmed it.)

Nothing here is a gate. A hand-edited draft that never gets re-stamped
just makes the next revision less efficient -- it cannot make a draft
wrong, because `chitragupta draft gate` still stands between any draft
and its citekeys.

**Before you decide a draft is finished**, [REVIEW.md](REVIEW.md) is
the human-facing check -- ten advisory aids (verbatim overlap,
citation provenance, uncited claims, and more) that never block, only
report. None of them is a gate; the only mechanical gate is
`citation_gate`, and it only refuses a fabricated citekey.

## 📕 Phase 4: write book chapters

A book is the same pipeline at a larger scale: one outline you sign off
once, then one generation contract per chapter, each accepted on its
own. [BOOKS.md](BOOKS.md) is the authoritative walkthrough; the shape:

| Step | Command | Who runs it |
| --- | --- | --- |
| 1 | `spec init`, then edit `spec.md` | you |
| 2 | `spec sign` | **you, and only you** |
| 3 | `unit contract` -> a genre skill writes the prose | skill |
| 4 | `unit accept` | you, per unit |

Steps 3 and 4 repeat once per chapter. `spec sign` is the book track's
first of two human sign-offs -- nothing downstream can start without
it.

## 📖 Phase 5: assemble the book

Once every chapter is accepted:

| Step | Command | Who runs it |
| --- | --- | --- |
| 5 | `registry build`, `registry check` | you or the assembler |
| 6 | the `book-assembler` skill composes `book.tex` | skill |
| 7 | `pdflatex` x2 -- no bibliography pass | you or the assembler |
| 8 | read it | **you, and only you** |

Steps 5 to 7 are what `.claude/skills/book-assembler/` does in one run
when you ask it to assemble the book. Step 8 is the track's second
human sign-off -- [BOOKS.md](BOOKS.md) explains why it is a sibling
file rather than another flag, and what `registry check`'s exit code
does and does not promise.

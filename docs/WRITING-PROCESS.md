# ✍ Writing process: from a bare corpus to a finished draft or book

Status: **reference.** Written 2026-08-30.

**Written for** someone about to write with this pipeline, start to
finish -- the order the phases happen in, and which document has the
detail for each. **Assumed:** none of the setup has happened yet; if
your corpus is already synced, skip to whichever phase you're at.
**Not covered here:** which genre to pick, in detail
([GENRE.md](GENRE.md)); the exact command surface
([CLI.md](CLI.md)); config knobs ([CONFIG.md](CONFIG.md)); how to get
your library into shape ([ZOTERO.md](ZOTERO.md)). This document is the
map between those; each has the depth this one deliberately skips.

## 🧭 Table of contents

- [Phase 1: set up your corpus](#-phase-1-set-up-your-corpus)
- [Phase 2: write a first draft](#-phase-2-write-a-first-draft)
- [Phase 3: revise a draft](#-phase-3-revise-a-draft)
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

**Ask for it in plain words.** You do not invoke a skill by name --
"write a survey section on digital twin composability", "draft a thesis
chapter on runtime verification for autonomous robots", "write a
textbook chapter introducing digital twin asset reuse", "write a
tutorial that builds a minimal digital twin asset from scratch", "do
deep research on fault injection for digital twin testbeds". The
matching skill picks the request up and runs its own
gate -> references -> render chain for you.

**Which of the five genres actually matches what you asked for** is
[GENRE.md](GENRE.md#-picking-one)'s whole job -- read it if you're not
sure whether what you want is a survey, a thesis chapter, a textbook
chapter, a tutorial, or a deep-research report. The short version: it
comes down to what your reader is doing while they read -- entering a
field, reading adversarially for a claim, studying worked examples,
following you at a keyboard, or reconciling several perspectives.

**Optional, before you ask: declare your own structure.** `dossier init
<draft> --outline` creates `outline.md`, where you write each section's
`brief:`, `claim:`, and optionally the exact `queries:` to search --
the skill runs those verbatim instead of inventing sub-themes.
[DRAFT-ITERATION.md](DRAFT-ITERATION.md) has the format.

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

`draft-reviser` also handles **re-grounding**: when a corpus sync
removes a paper your draft cites, or -- once you've hand-edited a
section -- when you want that section's own new wording to drive one
extra retrieval round (ITER-RETGEN with you standing in for the model,
[DOSSIER.md](DOSSIER.md#-the-fingerprint-as-a-retrieval-trigger-456-feature-roadmapmds-e4)).

**Before you decide a draft is finished**, [REVIEW.md](REVIEW.md) is
the human-facing check -- nine advisory aids (verbatim overlap,
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

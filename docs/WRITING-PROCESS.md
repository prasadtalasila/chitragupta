# ✍ Writing process: from a bare corpus to a finished draft or book

Status: **reference.**

**Written for** someone about to write with this pipeline, start to
finish: the order the phases happen in, and which document has the
detail for each. If your corpus is already synced, skip to whichever
phase you're at. Genre choice is [GENRE.md](GENRE.md), every command is
[CLI.md](CLI.md), config knobs are [CONFIG.md](CONFIG.md), and getting
your library into shape is [ZOTERO.md](ZOTERO.md).

## 📚 Phase 1: set up your corpus

Everything downstream reads from one place: a BibTeX export with its
PDFs attached, turned into a ledger this pipeline can search.

1. **Export your Zotero library** as BibTeX with "Export Files" ticked,
   into `papers/bibliography.bib` (plus its companion
   `papers/bibliography/files/` folder). Do not rename or move that
   folder afterwards, because each entry's file path is relative to it.
   [ZOTERO.md](ZOTERO.md) has the walkthrough and the attachment-path
   trap that silently leaves an entry without a PDF.
2. **Sync the corpus layer**: `chitragupta corpus sync`. A citekey that
   later drops out of your `.bib` file is only reported, never deleted,
   unless you pass `--remove-stale`.
3. **Inspect what it found**: `chitragupta corpus ledger` (read-only).
4. **Optional: the enrichment layer.** Layout-aware parsing, semantic
   search and topic clustering are a second, deliberate pass that
   nothing in Phase 2 needs and no skill builds for you:
   `chitragupta enrich --stages docling,embed`. Which stage is worth the
   cost is in [RETRIEVAL.md](RETRIEVAL.md).

## ✍ Phase 2: write a first draft

| Step | What | Command | Who runs it |
| --- | --- | --- | --- |
| 1 | Optional: declare your own structure | `chitragupta draft dossier init content/drafts/<slug>.md --genre <genre> --outline`, then edit the `outline.md` it writes | you |
| 2 | Ask for the draft, in plain words | e.g. "write a survey section on digital twin composability" | you |
| 3 | Retrieve evidence, write the draft, and run its own gate -> references -> render chain | `chitragupta draft gate`, `chitragupta draft references`, `chitragupta draft render`: the same three commands as [CLI.md](CLI.md#-the-full-first-run-step-by-step) step 9, which you can also run by hand | the matching skill |
| 4 | Read what it wrote | the draft under `content/drafts/`, its dossier under `content/dossiers/`, and (for four of the six genres) its evidence sidecar | you |

You do not invoke a skill by name: "draft a thesis chapter on runtime
verification for autonomous robots" or "make me a digest of the
synchronisation papers in their own words" is enough, and the matching
skill runs step 3 for you. If you are unsure which of the six genres you
want, [GENRE.md](GENRE.md#-picking-one) matches it to what your reader is
doing while they read.

Step 1 writes `outline.md`, where you set out each section's `brief:`,
one or more `claim:` blocks, and optionally the exact `queries:` to
search; the skill runs those verbatim instead of inventing sub-themes.
[DOSSIER.md](DOSSIER.md) has the format.

Every finished draft gets a **dossier** in `content/dossiers/`, the
working state a later session reloads instead of re-running everything.
Four of the six genres also get an **evidence sidecar** listing what
each cited source said
([DOSSIER.md](DOSSIER.md#-the-evidence-sidecar-decided-per-genre)).
Neither is committed to git.

## 🔁 Phase 3: revise a draft

**Never re-run the genre skill that wrote it.** Ask for the change in
plain words ("shorten the third section", "fix the grammar") and the
matching reviser picks it up, working from the dossier:

| You want... | Ask for | What it does |
| --- | --- | --- |
| An ordinary change: shorten, expand, restructure, correct, copy-edit | `draft-reviser` (the default) | Edits only the affected sections from the dossier; re-searches only for new ground. The cheapest path |
| The whole corpus re-searched, cost regardless | say so explicitly, e.g. "re-check the entire draft against the corpus" | `corpus-reviser`. Re-runs every recorded sub-theme query, honouring what was already rejected |
| A repair queued by a review scan | "work the review agenda" | `agenda-reviser`. Fixes one unattended finding at a time and re-verifies every fix through the gate |

The default path is the command surface `draft-reviser` runs;
[DRAFT-ITERATION.md](DRAFT-ITERATION.md#-revising-a-draft) has the
reasoning behind each step:

| Step | What | Command | Who runs it |
| --- | --- | --- | --- |
| 1 | Check whether the corpus or the draft moved since the last stamp | `chitragupta draft dossier status content/drafts/<slug>.md`, then `chitragupta draft dossier mark-revision content/drafts/<slug>.md` before any retrieval | skill |
| 2 | Read the recorded scope and steering | reads `scope.md`, `steering.md` | skill |
| 3 | Find the affected sections | `chitragupta draft dossier sections content/drafts/<slug>.md --citekeys --write` | skill |
| 4 | Edit only those sections, at their line ranges | -- | skill |
| 5 | Re-search only if the change opens new ground, honouring `rejected.md` first | `chitragupta draft retrieve search "<query>" --log content/drafts/<slug>.md` | skill |
| 6 | Update the dossier for whatever changed | writes `evidence.md`/`rejected.md`/`sections.md`, appends to `revisions.md`/`steering.md` | skill |
| 7 | Re-gate, rebuild references, re-render, then stamp (only once the gate passes) | `chitragupta draft gate`, `chitragupta draft references`, `chitragupta draft render`, `chitragupta draft dossier stamp content/drafts/<slug>.md` | skill |

The copy-edit pass (grammar, dialect, a style rephrase) is the one
exception: steps 3 and 5 never run, it edits the whole draft, and it
leaves one `revisions.md` entry naming the convention applied
([DRAFT-ITERATION.md](DRAFT-ITERATION.md#-the-copy-edit-pass-and-the-entry-it-leaves)).

`draft-reviser` also handles **re-grounding**: when a corpus sync
removes a paper your draft cites, or, once you've hand-edited a
section, when you want that section's own new wording to drive one
extra retrieval round (ITER-RETGEN with you standing in for the model,
[DOSSIER.md](DOSSIER.md#-the-fingerprint-as-a-retrieval-trigger-feature-roadmapmds-e4)).

### ✏ Handing a hand-edited draft back for the next iteration

You can also edit `content/drafts/<slug>.md` in your own editor, at the
same path. There is no `dossier rename`, so saving it under a different
path orphans its dossier, and every equation in the draft silently
reverts to typewriter text on the next render
([DOSSIER.md](DOSSIER.md#-the-draft-fingerprint-feature-roadmapmds-e3)).

Nothing runs when you save. The next time you ask for a revision, or run
`chitragupta draft dossier status content/drafts/<slug>.md` yourself,
step 1 above compares a digest of the draft's text against the one
recorded at the last `dossier stamp`, and reports what your edit may have
left out of step with the dossier. `draft-reviser` offers each finding
one at a time and never applies a repair unasked;
[USER-EDITS.md](USER-EDITS.md) walks through them. None of this is a
gate: a draft never re-stamped only makes the next revision less
efficient, because `chitragupta draft gate` still stands between any
draft and its citekeys.

Before you decide a draft is finished, [REVIEW.md](REVIEW.md) is the
human-facing check: eleven advisory aids (verbatim overlap, citation
provenance, uncited claims, and more) that only report and never block.

## 📕 Phase 4: write book chapters

A book is the same pipeline at a larger scale: one outline you sign off
once, then one generation contract per chapter, each accepted on its
own. [WRITE-A-BOOK.md](WRITE-A-BOOK.md) is the authoritative
walkthrough:

| Step | Command | Who runs it |
| --- | --- | --- |
| 1 | `spec init`, then edit `spec.md` | you |
| 2 | `spec sign` | **you, and only you** |
| 3 | `spec seed`, then fill in each chapter's `outline.md` | you |
| 3b | `unit contract`, then a genre skill writes the chapter | you, then skill |
| 4 | `spec align`, then `unit accept` | you, per unit |

Steps 3b and 4 repeat once per chapter. `spec sign` is the book track's
first of two human sign-offs; nothing downstream can start without
it.

## 📖 Phase 5: assemble the book

Once every chapter is accepted:

| Step | Command | Who runs it |
| --- | --- | --- |
| 5 | `registry build`, `registry check` | you or the assembler |
| 6 | the `book-assembler` skill composes `book.tex` and runs `draft gate` on it | skill |
| 7 | `lualatex`, `bibtexu`, `lualatex` x2; with an index, `registry index` and one more `lualatex` | you or the assembler |
| 7b | `review union` | you |
| 8 | read it | **you, and only you** |

Steps 5 to 7 are what the `book-assembler` skill does in one run. Step 8
is the track's second human sign-off. [WRITE-A-BOOK.md](WRITE-A-BOOK.md)
says what `registry check`'s exit code does and does not promise.

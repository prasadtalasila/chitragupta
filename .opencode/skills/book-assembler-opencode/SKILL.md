---
name: book-assembler-opencode
description: Assembles accepted, gate-passed units into one LaTeX book -- front matter, parts, chapters, back matter -- from the outline `python -m chitragupta.draft spec` holds and the acceptance records `python -m chitragupta.draft unit` wrote. Triggers when the user asks to assemble, build, compose or "put together" a book from units already drafted, or asks for the whole book as one LaTeX document. Writes no prose of its own and drafts no unit -- a missing or unaccepted unit is the relevant genre skill's job, and this skill stops and says which. Runs `python -m chitragupta.draft registry check` and reports every finding before composing, runs `python -m chitragupta.draft gate` on what it composed, and stops at the second of the book track's two human sign-offs rather than declaring a book finished. Never fabricates a citekey and never edits a unit's prose.
tags: [book, latex, assembly, composition]
---

# book-assembler-opencode

The last step of the book-scale track (`docs/WRITE-A-BOOK.md`), and deliberately
the smallest. Everything this skill assembles has already passed every
gate per unit, so assembly is **deterministic composition plus a human
sign-off** -- not a drafting genre.

Read `docs/WRITE-A-BOOK.md` before the first run. This file is the procedure;
that one is why the procedure is shaped this way.

## What this skill is not

| Situation | Action |
| --- | --- |
| A unit named in the outline has no prose | Stop. Say which. Drafting it is `thesis-chapter-writer-opencode`'s job (or another genre's), not this skill's |
| A unit exists but nobody accepted it | Stop. `python -m chitragupta.draft unit accept` is a human's call, made per unit |
| The user wants a unit's wording changed | `draft-reviser-opencode`. Never edit a unit while assembling it |
| The outline itself is wrong | `python -m chitragupta.draft spec` and a fresh sign-off. Never rewrite an outline here |
| The user wants one chapter, not a book | The relevant genre skill. This skill composes what exists; it does not write |

**It writes no prose.** The only file it authors is the book document
itself -- a preamble, the structure, and one `\input` per unit. If you
find yourself writing a sentence that will be read by the book's reader,
you are in the wrong skill.

## Conventions as data

The whole of the composition is one table: the outline
(`content/specs/<book>/spec.md`) is planned top-down, and the book is
emitted bottom-up from what has been accepted. Read
`.claude/skills/book-assembler/references/latex-conventions.md` before
composing, and follow it exactly: the outline-to-LaTeX table and its
labels, the document skeleton, the `\setcounter` lines, an authored
preamble, the one bibliography, table captions, TikZ libraries, Unicode,
margins, and the two files this skill writes. A character the Unicode
package does not map is fixed by the author, in the book's `preamble.tex`
or in the unit through `draft-reviser-opencode` -- never by this skill.

## Process

1. **Confirm the outline is signed off.** The first of the track's two
   human gates. Do not compose anything until this exits 0:

   ```bash
   python -m chitragupta.draft spec status content/drafts/<book>
   ```

   Non-zero means nobody approved this outline, or it changed after
   somebody did. Either way, stop and say which -- approving it is the
   user's act, not yours, and `python -m chitragupta.draft spec sign` is theirs
   to run.

2. **Confirm every unit is accepted and current.**

   ```bash
   python -m chitragupta.draft unit status content/drafts/<book>
   ```

   Report the table as it stands. A unit reading `unwritten`, `drafted`
   or `stale: ...` is not assemblable, and the reason matters to the
   user: `stale: inputs changed` means the outline moved under prose
   somebody already accepted, which is a decision for them and not a
   thing to paper over by assembling the old text.

3. **Rebuild the registries and report every finding.** This step is not
   optional and is not summarised away:

   ```bash
   python -m chitragupta.draft registry build content/drafts/<book>
   python -m chitragupta.draft registry check content/drafts/<book>
   ```

   `check` exits 0 whatever it finds -- it is a machine's reading of
   prose, and `docs/ARCHITECTURE.md`'s "Layer 4" is why it may not
   block. **What is guaranteed is that it ran and that its findings were
   seen**, and this step is where that guarantee lives: print every
   finding to the user, in full, before composing. A term defined twice,
   the same claim made in two chapters, a cross-reference that resolves
   to nothing -- each is the user's call. Report the coverage line too:
   a registry built over units it could not read is a narrower claim
   than it looks.

4. **Convert each accepted unit to a fragment.** The default output
   directory is already the right one -- a draft's renders mirror its
   path, so `content/drafts/<book>/<unit-id>.md` renders to
   `content/rendered/<book>/<unit-id>.tex`, which is where `book.tex`
   goes too. So `\input` resolves without copying anything, and no
   `--output-dir` is needed:

   ```bash
   python -m chitragupta.draft render content/drafts/<book>/<unit-id>.md \
       --format tex --fragment
   ```

   **A unit's mathematics resolves per unit, and that is why this works.**
   Each unit has its own dossier, so `render` reads *its* `math.md`
   (docs/WRITING-STANDARDS.md §12) -- there is no book-level mapping to
   assemble and nothing to merge. Two units may map the same ASCII
   differently and both stay right. What this step must not do is move or
   rename a unit's `.md`: a dossier is found by path alone, so a renamed
   unit loses its mapping and every equation in that chapter silently
   becomes typewriter text. A `<!-- math -->` marker with no mapping fails
   this render outright, which is the loud half of that.

   `--fragment` is what makes it assemblable: no preamble, the unit's own
   `#` heading becomes the book's `\chapter`, and code blocks are left
   unhighlighted because `Shaded`/`Highlighting` are defined only by the
   standalone template. Everything else is the ordinary render -- citeproc,
   the IEEE style, and the citekey aliasing that stops a key containing
   `--` being truncated -- which is why this is one command and not a
   pandoc invocation restated here. A unit already drafted as `.tex` by
   `thesis-chapter-writer-opencode` needs no conversion.

   Then add the outline's ids as labels: pandoc emits its own `\label{}`
   from the heading text, and `\label{<unit-id>}` (plus the chapter's
   `\label{ch-NN}`) goes immediately after that, so a label binds to the
   chapter counter rather than to whatever sectioning command follows.

5. **Compose the book.** Write `content/rendered/<book>/book.tex` and
   `content/rendered/<book>/book.md` from the conventions above, in
   outline order, covering only units step 2 reported as `accepted`.
   **That directory is assembly output, not authored material**:
   `content/drafts/<book>/` holds the chapters a person wrote and nothing
   else, and step 4's fragments are already here beside what you are
   about to write.

   **Copy `content/specs/<book>/preamble.tex` beside `book.tex` if it
   exists**, and `\input` it as the last line of the generated preamble.
   If it does not exist, write no `\input` and say nothing about it --
   most books have none, and reporting its absence would read as a
   finding. Copy it rather than `\input` it across directories: the
   `\input` paths in `book.tex` are all relative to the book's own
   directory, and one that reached out of it would break the moment the
   book was built anywhere else. Ask the user
   for the author line rather than choosing for them; everything else is
   mechanical.

6. **Run the gate on what you composed.** Every unit passed it already;
   the assembled document is a new file, and the gate is this layer's
   only exit:

   ```bash
   python -m chitragupta.draft gate content/rendered/<book>/book.tex
   ```

   A `FAIL` here is a failing test, not a warning. Never "fix" one by
   inventing or altering a citekey -- correct the reference or take the
   claim out, in the unit it came from, via `draft-reviser-opencode`.

7. **Run the prose check over the units, not the skeleton.** `book.tex`
   is structure and holds no prose, so scanning it would report nothing
   and mean nothing. Run it per accepted unit:

   ```bash
   python -m chitragupta.draft style content/drafts/<book>/<unit-id>.md
   ```

   Read `.claude/skills-common/references/prose-check.md` now and follow
   it: what the check can and cannot see, and how to report what it finds.
   Acting on a finding is `draft-reviser-opencode`'s copy-edit mode, in the unit
   that owns the prose.

8. **Run the verbatim scan, per unit.** Assembly is the last moment
   before a whole book is read by somebody else, which makes it the
   right moment to run this. Per unit, rebuild the section map and scan:

   ```bash
   python -m chitragupta.draft dossier sections content/drafts/<book>/<unit-id>.md --citekeys --write
   python -m chitragupta.review verbatim scan content/drafts/<book>/<unit-id>.md
   ```

   The first command is not optional. The embedding tier compares each
   section against the citekeys that section's `sections.md` row records,
   and a unit accepted weeks ago may have been revised since.

   **A review aid, not a gate: it is never a condition of presenting** --
   a unit with findings is still an assembled unit, and this step reports
   rather than withholds. Read
   `.claude/skills-common/references/verbatim-scan.md` now and follow it
   for each unit. Repairing a finding is `agenda-reviser-opencode`'s job, one
   finding at a time, in the unit that owns the wording, and only if the
   user asks.

   Report the per-unit results as one table rather than a wall: the book
   has fifteen chapters, and fifteen separate scan reports is how a real
   finding gets skimmed past.

9. **Build the PDF, if the toolchain is there.** From the book's own
   directory, because the `\input` paths are relative to it:

   ```bash
   cd content/rendered/<book>
   pdflatex -interaction=nonstopmode book.tex
   bibtex book
   pdflatex -interaction=nonstopmode book.tex
   pdflatex -interaction=nonstopmode book.tex
   ```

   **Four passes, and the `bibtex` one is not optional.** The first
   `pdflatex` records which keys the document cites; `bibtex` turns those
   into `book.bbl`; the third pass pulls the bibliography in and the
   fourth resolves `\cref`, the table of contents and the citation
   numbers now that the entries exist. Skip `bibtex` and every citation
   renders as `[?]` -- with `pdflatex` still exiting 0.

   **Read `book.log` before believing the PDF.** A `pdflatex` run that
   exits 0 can still be missing something -- a dropped citation is
   reported as a warning, not an error:

   ```bash
   python3 -c "import re,pathlib; log=pathlib.Path('book.log').read_text(errors='replace'); \
       print(sorted(set(re.findall(r\"Citation \`([^']+)' on page\", log))))"
   ```

   Anything but `[]` means a citekey did not reach the bibliography --
   go back to the conversion step, do not hand over the PDF. This check
   became load-bearing when the bibliography moved to the end of the
   book: before that, citeproc had already resolved every citation and
   there was nothing for this warning to report.

   **A citekey containing `--` is the case worth knowing about.** The
   render aliases it (`state---art` becomes `state-x2d-x2d-art`) on both
   sides -- the `\citep{...}` and the copied `.bib` -- so it resolves.
   What breaks it is hand-editing either one.

   **Never run `draft gate` on a fragment.** The gate is for the
   assembled `book.tex` (step 6) and for a unit's authored `.md`, which
   is what every unit already passed. A fragment is render output: its
   citekeys may be aliased, and an alias is not a ledger key, so the gate
   would report a `FAIL` on a book that is perfectly correct. Python
   rather than `grep -c` deliberately: on the host this was first run,
   `grep -c` over that log printed nothing at all, and a check that
   silently reports nothing is worse than no check.

   **Table numbers are the book's, not a unit's, and one thing can break
   them.** A unit's tables carry
   `docs/WRITING-STANDARDS.md` §13's markers, which the conversion turns
   into `\caption{...\label{tab:<id>}}`, so the `book` class numbers them
   itself. **Which shape it uses follows the `\setcounter{secnumdepth}`
   the skeleton sets**, and both were measured with `pdflatex` rather
   than assumed: at the skeleton's `2`, tables read "1.1", "2.1", "2.2"
   -- reset per chapter, which is what a book gets by default; at `-2`
   (a book whose units number their own headings, overriding in
   `preamble.tex`), they read "1", "2", "3" -- flat and continuous.
   Either way the numbers are unique and every `\ref` resolves, so there
   is nothing to configure for the tables themselves. What does not
   survive is a **duplicate id**: two units that
   each wrote `<!-- table: comparison -->` become two `\label{}`s in one
   document, and every `\ref` to that id silently resolves to whichever
   LaTeX saw last. Check for it before composing, and send a collision
   back to `draft-reviser-opencode` rather than renaming a label here:

   ```bash
   grep -ho '<!-- table: [^ ]* -->' content/drafts/<book>/*.md | sort | uniq -d
   ```

   Anything printed is a collision. The per-unit prose check reports the
   same defect (`TableDuplicateId`) but sees one unit at a time -- across
   units, this is the check.

   **A captioned figure's number is the book's for the same reason, and
   the same collision risk applies.** Issue 411 gives a figure the same
   `\label{fig:<id>}` contract, so two units that each wrote
   `<!-- figure: figures/comparison -->` with a caption below it collide
   exactly as two same-id tables do. Check before composing:

   ```bash
   grep -ho '<!-- figure: [^ ]* -->' content/drafts/<book>/*.md | sort | uniq -d
   ```

   Anything printed is a collision, whether or not every copy is
   captioned -- an uncaptioned marker sharing the name is still worth
   catching before whichever unit adds a caption next collides silently.
   Since #421 an uncaptioned marker is also a `FigureNoCaption` finding
   in its own unit's prose check, so it should not survive this far.
   The per-unit prose check (`FigureDuplicateId`) sees one unit at a
   time; across units, this is the check.

   **A numbered equation's number is the book's for the same reason,
   and the same collision risk applies.** #457 gives a *numbered*
   equation the same `\label{eq:<id>}` contract, so two units that each
   wrote `<!-- equation: comparison -->` collide exactly as two same-id
   tables do -- most equations across a book carry no id at all, since
   most stay unnumbered by §12's own rule, so this collision is rarer
   than the table or figure one but not impossible when two units prove
   a similarly-named result. Check before composing:

   ```bash
   grep -ho '<!-- equation: [^ ]* -->' content/drafts/<book>/*.md | sort | uniq -d
   ```

   Anything printed is a collision. The per-unit prose check
   (`EquationDuplicateId`) sees one unit at a time; across units, this
   is the check.

   **If the units number their own *sections*, turn LaTeX's numbering
   off** -- `\setcounter{secnumdepth}{-2}` in
   `content/specs/<book>/preamble.tex`, which the skeleton `\input`s
   last and which therefore wins over its default of `2`. A book whose
   Markdown says `## 1.0 Before you start` otherwise renders "1.1 1.0
   Before you start", and worse further in ("10.1510.14"). Which
   numbering a book shows is a composition decision and belongs to the
   book; renumbering the author's headings does not, and is
   `draft-reviser-opencode`'s call rather than this skill's.

   **A self-numbered *chapter title* is a different clash, and this is
   the wrong lever for it** (#804). A unit headed `# Chapter 1: Why
   Anyone Pays` is numbered twice by the `book` class, but
   `secnumdepth{-2}` pays a document-level price for a chapter-level
   problem. Measured on one real book, four `pdflatex` passes each:

   | | `secnumdepth{2}` (the skeleton) | `secnumdepth{-2}` |
   | --- | --- | --- |
   | Chapter opening | `Chapter 1` / `Chapter 1: Why Anyone Pays` | correct |
   | ToC chapter line | `1 Chapter 1: Why Anyone Pays` | correct |
   | ToC section lines | `1.1`, `1.2`, ... `1.10` | **all numbers lost** |
   | Table captions | `Table 1.1`, `2.1`, ... | `Table 1`, `2`, ... flat |

   **Nothing is asked of you here: step 4's render drops the prefix
   already.** `draft render --fragment` emits `\chapter{Why Anyone
   Pays}` from that heading, so the number comes from the class alone
   and sections, tables and figures keep theirs. The authored `.md` is
   untouched, every unit stays `accepted`, and the unit's own standalone
   pdf keeps the prefix that titles it. If a book already carries
   `secnumdepth{-2}` for this reason, **remove it** -- it is now costing
   the section and table numbering for a clash that no longer exists.

   A unit drafted as `.tex` is the exception, because step 4 never
   converts it: there the prefix is in the file you `\input`, and
   `draft style` reports it as `chitragupta.ChapterSelfNumbered` in step
   3 for the author to delete.

   Without TeX Live, say so plainly and stop there rather than working
   around it -- the `.tex` is the deliverable either way.

10. **Stop at the sign-off.** This is the second of the two human gates,
   and there is no command for it. Present what you composed: how many
   units, which the registries could not read, every finding from step 3,
   and what the gate and the two review aids said. Then stop.

   **Do not say the book is finished.** Nothing here has read the
   argument. Every check in this pipeline verifies that the book is
   grounded, consistent and complete -- none of them verifies that it is
   any good, and that judgement is the user's, deliberately.

## What this skill does not write

**No dossier.** Every drafting skill writes one because it makes
judgement calls -- what to retrieve, what to keep, what to reject and
why -- that a later revision has to be able to read. This skill makes
none of those: it retrieves nothing and decides nothing. The record of a
book is already on disk, in the artefacts the earlier steps wrote:
`content/specs/<book>/spec.md` and its `signoff.md`, one acceptance
record per unit under `units/`, and the three registries under
`registries/`.

**No acronym vocabulary step**, for the same reason -- there is no prose
here to expand an acronym in. Each unit's own genre skill handled that
when the unit was drafted.

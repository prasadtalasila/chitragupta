---
name: book-assembler
description: Assembles accepted, gate-passed units into one LaTeX book -- front matter, parts, chapters, back matter -- from the outline `python -m chitragupta.draft spec` holds and the acceptance records `python -m chitragupta.draft unit` wrote. Triggers when the user asks to assemble, build, compose or "put together" a book from units already drafted, or asks for the whole book as one LaTeX document. Writes no prose of its own and drafts no unit -- a missing or unaccepted unit is the relevant genre skill's job, and this skill stops and says which. Runs `python -m chitragupta.draft registry check` and reports every finding before composing, runs `python -m chitragupta.draft gate` on what it composed, and stops at the second of the book track's two human sign-offs rather than declaring a book finished. Never fabricates a citekey and never edits a unit's prose.
tags: [book, latex, assembly, composition]
---

# book-assembler

Composes accepted, gate-passed units into one LaTeX book: the last step
of the book track (`docs/WRITE-A-BOOK.md`), deterministic composition
plus a human sign-off, and not a drafting genre. Paths in this skill are
from the project root, not from this skill's own folder.

**It writes no prose.** The only files it authors are the book document
itself -- a preamble, the structure, and one `\input` per unit -- and its
Markdown twin. It never fabricates a citekey and never edits a unit's
prose: every citekey in the book is one a unit already carried through
the gate, and every change of wording goes to the unit that owns it. A
unit that is missing or unaccepted stops the run, and the skill says
which unit and whose job it is. It stops at the second of the book
track's two human sign-offs rather than declaring a book finished: it
presents what it composed and leaves that verdict to the user.

Before step 1, read `.claude/skills-common/references/book-steps.md` §1
and §2: what the spec and the acceptance records are, and what each
sign-off covers.

## What this skill is not

| Situation | Action |
| --- | --- |
| A unit named in the outline has no prose | Stop. Say which. Drafting it is `thesis-chapter-writer`'s job (or another genre's; a preface is the author's), not this skill's |
| A unit exists but nobody accepted it | Stop. `python -m chitragupta.draft unit accept` is a human's call, made per unit |
| The user wants a unit's wording changed | `draft-reviser`. Never edit a unit while assembling it |
| The outline itself is wrong | `python -m chitragupta.draft spec` and a fresh sign-off. Never rewrite an outline here |
| The user wants one chapter, not a book | The relevant genre skill. This skill composes what exists; it does not write |

## Conventions as data

The composition is one table, from the outline
(`content/specs/<book>/spec.md`) to `book.tex`. Before step 5, read
`.claude/skills/book-assembler/references/latex-conventions.md` §1, §3,
§4 and §6, and follow them exactly: the composition table and
the skeleton, where the front matter, appendices and back matter go,
the title and copyright pages and an authored preamble, and which
skeleton lines the renders decide. Its other sections are read when a
step below says so. A character the fonts do not have is fixed by the
author, in the book's `preamble.tex` or in the unit through
`draft-reviser`, never by this skill.

## Process

1. **Confirm the outline is signed off.** The first of the track's two
   human gates. Do not compose anything until this exits 0:

   ```bash
   python -m chitragupta.draft spec status content/drafts/<book>
   ```

   Non-zero means nobody approved this outline, or it changed after
   somebody did. Either way, stop and say which: approving it is the
   user's act, and `python -m chitragupta.draft spec sign` is theirs to
   run. Done when it exits 0, or you have stopped and said why.

2. **Confirm every unit is accepted and current.**

   ```bash
   python -m chitragupta.draft unit status content/drafts/<book>
   ```

   Report the table as it stands. A unit reading `unwritten`, `drafted`
   or `stale: ...` is not assemblable: stop, and say which unit and why,
   as `.claude/skills-common/references/book-steps.md` §1 reads each
   status. Done when every unit reads `accepted`, or you have stopped
   and named each one that does not.

3. **Rebuild the registries and report every finding.** Before building,
   read `.claude/skills-common/references/book-steps.md` §3. This step is
   not optional and is not summarised away:

   ```bash
   python -m chitragupta.draft registry build content/drafts/<book> \
       --glossary content/rendered/<book>/glossary.tex \
       --notation content/rendered/<book>/notation.tex \
       --index content/rendered/<book>/index-terms.json   # only with {#index}
   python -m chitragupta.draft registry check content/drafts/<book>
   ```

   If `build` exits 1 on `[glossary]` bullets or `[notation]` symbol
   rows, **stop** and report them: the fix is `draft-reviser` on that
   unit's `scope.md` or `math.md`, never yours. On `[index]` problems
   the fix is the author's, in `index.toml`. When `build` wrote
   `glossary.tex` or `notation.tex`, read
   `.claude/skills/book-assembler/references/latex-conventions.md` §8
   before step 5 places them. `check` exits 0 whatever
   it finds, so print every finding to the user, in full, before
   composing, and its coverage line. Done when every finding is printed.

4. **Convert each accepted unit to a fragment.** Renders mirror the
   draft's path, so this lands in `content/rendered/<book>/` with no
   `--output-dir`:

   ```bash
   python -m chitragupta.draft render content/drafts/<book>/<unit-id>.md \
       --format tex --fragment
   ```

   With `{#index}`, add `--index-terms content/rendered/<book>/index-terms.json`
   for every chapter and appendix (never front or back matter). A unit
   already drafted as `.tex` by `thesis-chapter-writer` needs no
   conversion. Never move or rename a unit's `.md`: its dossier and its
   `math.md` are found by path alone. Keep every `[tikz-libraries]`,
   `[floats]` and `[unicode]` line the renders print, for step 5.

   Then put `\label{<unit-id>}` (plus `\label{ch-NN}`) immediately after
   each chapter's `\chapter`. If the user asks what `--fragment` changes,
   read `.claude/skills/book-assembler/references/latex-conventions.md`
   §1. Done when every accepted unit has its fragment and labels.

5. **Compose the book.** Before writing anything, read
   `.claude/skills-common/references/book-steps.md` §4, then check that
   no table, figure or equation id is used by two units (the markers of
   `docs/writing-standards/tables.md` §13 and its figure and equation
   twins):

   ```bash
   grep -ho '<!-- table: [^ ]* -->' content/drafts/<book>/*.md | sort | uniq -d
   grep -ho '<!-- figure: [^ ]* -->' content/drafts/<book>/*.md | sort | uniq -d
   grep -ho '<!-- equation: [^ ]* -->' content/drafts/<book>/*.md | sort | uniq -d
   ```

   Anything printed is a collision: send it back to `draft-reviser`
   rather than renaming a label here. Then write
   `content/rendered/<book>/book.tex` and `content/rendered/<book>/book.md`
   from `.claude/skills/book-assembler/references/latex-conventions.md`
   §1, in outline order, covering only units step 2 reported as
   `accepted`, with the skeleton lines §6 says the step 4 renders
   decide.

   Place the front matter, appendices and back matter by
   `.claude/skills/book-assembler/references/latex-conventions.md` §3,
   which you read before this step. **This step is not done until every
   outline entry, and every generated page, sits where §3 puts it**, and
   a generated page with nothing to show is left out and said nothing
   of. Come back with the list of what you placed and which generated
   pages printed.

   **Copy `content/specs/<book>/preamble.tex` beside `book.tex` if it
   exists**, and `\input` it as the last line of the generated preamble;
   `copyright.tex` likewise, after `\maketitle`. When either exists,
   read `.claude/skills/book-assembler/references/latex-conventions.md`
   §4 before copying it. If it does not exist, write no `\input` and say
   nothing about it -- most books have none. The author is the outline's
   `- author:` line, which `spec show` prints; ask the user only if it
   has none, never invent one. Done when both files are written and
   every entry is placed.

6. **Run the gate on what you composed.** Before running it, read
   `.claude/skills-common/references/book-steps.md` §5.

   ```bash
   python -m chitragupta.draft gate content/rendered/<book>/book.tex
   ```

   A `FAIL` here is a failing test, not a warning. Never "fix" one by
   inventing or altering a citekey -- correct the reference or take the
   claim out, in the unit it came from, via `draft-reviser`. Never run
   `draft gate` on a fragment. Done when it reports `OK`.

7. **Run the prose check over the units, not the skeleton.** `book.tex`
   is structure and holds no prose. Run it per accepted unit:

   ```bash
   python -m chitragupta.draft style content/drafts/<book>/<unit-id>.md
   ```

   Read `.claude/skills-common/references/prose-check.md` now and follow
   it. Acting on a finding is `draft-reviser`'s copy-edit mode, in the
   unit that owns the prose. Done when every unit's findings are
   reported.

8. **Run the verbatim scan, per unit.** Assembly is the last moment
   before a whole book is read by somebody else. Per unit, rebuild the
   section map and scan:

   ```bash
   python -m chitragupta.draft dossier sections content/drafts/<book>/<unit-id>.md --citekeys --write
   python -m chitragupta.review verbatim scan content/drafts/<book>/<unit-id>.md
   ```

   The first command is not optional: a unit accepted weeks ago may
   have been revised since. **A review aid, not a gate: it is never a
   condition of presenting.** Read
   `.claude/skills-common/references/verbatim-scan.md` now and follow it
   for each unit. Repairing a finding is `agenda-reviser`'s job, one
   finding at a time, in the unit that owns the wording, and only if the
   user asks. Report the per-unit results of this step and step 7 as one
   table. Done when that table is shown.

9. **Build the PDF, if the toolchain is there.** From the book's own
   directory, because the `\input` paths are relative to it:

   ```bash
   cd content/rendered/<book>
   lualatex -interaction=nonstopmode book.tex
   bibtexu book
   lualatex -interaction=nonstopmode book.tex
   lualatex -interaction=nonstopmode book.tex
   # only with {#index}:
   (cd - >/dev/null && python -m chitragupta.draft registry index \
       content/drafts/<book> --idx content/rendered/<book>/book.idx)
   lualatex -interaction=nonstopmode book.tex
   ```

   Tell the user the line `registry index` prints; its report's fixes go
   in `index.toml`. Exit 1 is a stale build: re-run steps 3 and 4. With
   `{#index}`, read
   `.claude/skills/book-assembler/references/latex-conventions.md` §9
   before this step.

   **Four passes, and the `bibtexu` one is not optional**: skip it and
   every citation renders as `[?]`, with `lualatex` still exiting 0.
   `bibtexu` exits 1 when the `.bib` has only warnings (an empty
   `booktitle`); read `book.blg` for an `error`, not the exit code. If a
   pass fails, or the user asks why LuaLaTeX and `bibtexu`, read
   `.claude/skills/book-assembler/references/latex-conventions.md` §7.

   **Read `book.log` before believing the PDF.** A dropped citation is
   reported as a warning, not an error:

   ```bash
   python3 -c "import re,pathlib; log=pathlib.Path('book.log').read_text(errors='replace'); \
       print(sorted(set(re.findall(r\"Citation \`([^']+)' on page\", log))))"
   ```

   Anything but `[]` means a citekey did not reach the bibliography --
   go back to the conversion step, do not hand over the PDF; read
   `.claude/skills/book-assembler/references/latex-conventions.md` §5
   to find where it was lost.

   **Then report any figure that landed on a float-only page.** The same
   log names each one:

   ```bash
   python3 -c "import re,pathlib; log=pathlib.Path('book.log').read_text(errors='replace'); \
       print(re.findall(r'chitragupta float page: .+', log))"
   ```

   Tell the user every line it prints, as a finding about the figure, not
   a failure of the build: the fix, if they want one, is a shorter
   figure, drawn through `figure-drawer`. Never edit
   `chitragupta-floats.tex` or a unit to make the list empty.

   If a unit's own headings carry numbers, or the PDF numbers a heading
   twice, read
   `.claude/skills/book-assembler/references/latex-conventions.md` §2
   before changing anything; renumbering the author's headings is
   `draft-reviser`'s call. Without TeX Live,
   say so plainly and stop there rather than working around it -- the
   `.tex` is the deliverable either way. Done when both log checks are
   reported, or you have said TeX Live is missing.

10. **Stop at the sign-off.** This is the second of the two human gates,
    and there is no command for it. Read
    `.claude/skills-common/references/book-steps.md` §2 again, then
    present what it says: how many units, which the registries could not
    read, every finding from step 3, and what the gate and the two review
    aids said. Then stop.

    **Do not say the book is finished.** Nothing here has read the
    argument; that judgement is the user's, deliberately. Done when the
    user has the book and you have stopped.

## Sources

The front matter, appendices and back matter follow BCcampus's
*Self-Publishing Guide*, "Textbook Outline" (CC BY 4.0). The citation
and what it supplies are in
[`docs/WRITING-STANDARDS.md`](../../../docs/WRITING-STANDARDS.md#-sources-and-attribution).

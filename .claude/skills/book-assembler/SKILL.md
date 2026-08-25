---
name: book-assembler
description: Assembles accepted, gate-passed units into one LaTeX book -- front matter, parts, chapters, back matter -- from the outline `python -m chitragupta.draft spec` holds and the acceptance records `python -m chitragupta.draft unit` wrote. Triggers when the user asks to assemble, build, compose or "put together" a book from units already drafted, or asks for the whole book as one LaTeX document. Writes no prose of its own and drafts no unit: a missing or unaccepted unit is the relevant genre skill's job, and this skill stops and says which. Runs `python -m chitragupta.draft registry check` and reports every finding before composing, runs `python -m chitragupta.draft gate` on what it composed, and stops at the second of the book track's two human sign-offs rather than declaring a book finished. Never fabricates a citekey and never edits a unit's prose.
tags: [book, latex, assembly, composition]
---

# book-assembler

The last step of the book-scale track (`docs/BOOKS.md`), and deliberately
the smallest. Everything this skill assembles has already passed every
gate per unit, so assembly is **deterministic composition plus a human
sign-off** -- not a drafting genre.

Read `docs/BOOKS.md` before the first run. This file is the procedure;
that one is why the procedure is shaped this way.

## What this skill is not

| Situation | Action |
| --- | --- |
| A unit named in the outline has no prose | Stop. Say which. Drafting it is `thesis-chapter-writer`'s job (or another genre's), not this skill's |
| A unit exists but nobody accepted it | Stop. `python -m chitragupta.draft unit accept` is a human's call, made per unit |
| The user wants a unit's wording changed | `draft-reviser`. Never edit a unit while assembling it |
| The outline itself is wrong | `python -m chitragupta.draft spec` and a fresh sign-off. Never rewrite an outline here |
| The user wants one chapter, not a book | The relevant genre skill. This skill composes what exists; it does not write |

**It writes no prose.** The only file it authors is the book document
itself -- a preamble, the structure, and one `\input` per unit. If you
find yourself writing a sentence that will be read by the book's reader,
you are in the wrong skill.

## Conventions as data

The whole of the composition is this table. The outline
(`content/specs/<book>/spec.md`) is planned top-down; the book is emitted
bottom-up from what has been accepted.

| Outline | LaTeX | Label |
| --- | --- | --- |
| `# Title` | `\title{...}` in the preamble | -- |
| `## Part {#part-i}` | `\part{...}` | `\label{part-i}` |
| `### Chapter {#ch-1}` | `\chapter{...}` | `\label{ch-1}` |
| `#### Section {#sec-1}` | `\input{sec-1.tex}` | the unit's own `\label{sec-1}` |

**The `{#id}` becomes the LaTeX label, unchanged.** That is what makes
the cross-references the registry checked actually resolve in the built
PDF: a unit's `\cref{ch-1}` points at the same id the outline declared
and `python -m chitragupta.draft registry check` verified. Never rename one on
the way through.

The document skeleton, in order:

```latex
\documentclass[11pt,a4paper]{book}
\usepackage[T1]{fontenc}\usepackage{lmodern}\usepackage{textcomp}
\usepackage[a4paper,margin=80pt]{geometry}   % see "Margins" below
\usepackage{longtable,booktabs,array,calc}   % what the converted units use
\usepackage{graphicx}
\usepackage[hidelinks]{hyperref}
\usepackage{cleveref}
\setcounter{secnumdepth}{-2}                 % if the units number themselves
\providecommand{\tightlist}{%
  \setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
% pandoc's citeproc definitions -- see below
\title{<the outline's own title>}
\author{<ask the user; never invent one>}
\date{}

\begin{document}
\frontmatter
\maketitle
\tableofcontents

\mainmatter
% \part / \input, in outline order

\backmatter
\end{document}
```

**There is no bibliography at the end, and no `natbib`, `bibtex` or
`biber` pass.** Citations are resolved per unit, by pandoc's citeproc
against this project's vendored IEEE style (`assets/csl/ieee.csl`), when
the unit is converted -- so each chapter carries its **own numbered IEEE
reference list**, under the chapter's own `References` heading, exactly
as every other genre skill produces one. That is the house citation style
and the reason natbib is not used: its author-year markers are not what
the rest of this pipeline emits. `bibtex` and `IEEEtran.bst` are
installed (`scripts/install_full_pipeline.sh`) for a document that
genuinely wants a LaTeX-side bibliography; a book assembled this way does
not.

**The book must supply pandoc's citeproc macros, in their own file.** A
converted unit uses the `CSLReferences` environment, which `--standalone`
would have defined in a preamble the fragment does not have. Write the
block to `citeproc-defs.def` beside `book.tex` and `\input` it --
**not inline**, because it contains `\cite{#1}`, `\citeproc{mm}` and
`\@`-internals that the citation gate reads as citekeys, and a false
`FAIL` on the one gate in this project is worse than one more file.
`.def` is LaTeX's own extension for a definitions file.

Take the block from the installed pandoc rather than hand-copying it, so
it matches the pandoc that did the conversion:

```bash
pandoc --print-default-template=latex | \
  python3 -c "import sys; t=sys.stdin.read(); s=t.index('\$if(csl-refs)\$'); \
    b=t[s:t.index('\$endif\$', s)+7]; \
    print('\n'.join(l for l in b.splitlines() if not l.strip().startswith('\$')))"
```

**Margins.** `margin=80pt` -- about 28mm, and this project's setting for
an assembled book. Arrived at by measurement rather than taste: the
`book` class at a4/11pt leaves 94pt inner and 143pt outer (measured with
`\the\oddsidemargin`), a 119pt mean, which is generous enough that a
15-chapter book ran to 546 pages. A third of that was tried first and
read too tight for a book meant to be printed -- 80pt is that doubled,
and is the number to keep unless someone measures a better one.

**The bibliography points at the user's own `.bib` file**, the same one
`python -m chitragupta.corpus sync` read -- not a copy, and never a file this
skill writes. `render` reads it for you when it converts a unit, so
nothing here names it: the reference manager is upstream, and this
pipeline is downstream of it.

**Two files, not one.** Beside `book.tex`, write `book.md`: the same
structure in Markdown, hyperlinking the chapter files that sit alongside
it. Parts become `##`; a chapter that is a single unit of the same name
becomes one link rather than a heading repeating its own link text
underneath; a chapter with several sections becomes `###` and a list.
It is the reading copy for anyone who is not building LaTeX.

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

4. **Convert each accepted unit to a fragment**, into the book's own
   directory so `\input` resolves without copying anything:

   ```bash
   python -m chitragupta.draft render content/drafts/<book>/<unit-id>.md \
       --format tex --fragment --output-dir content/drafts/<book>
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
   `thesis-chapter-writer` needs no conversion.

   Then add the outline's ids as labels: pandoc emits its own `\label{}`
   from the heading text, and `\label{<unit-id>}` (plus the chapter's
   `\label{ch-NN}`) goes immediately after that, so a label binds to the
   chapter counter rather than to whatever sectioning command follows.

5. **Compose the book.** Write `content/drafts/<book>/book.tex` and
   `content/drafts/<book>/book.md` from the conventions above, in outline
   order, covering only units step 2 reported as `accepted`. Ask the user
   for the author line rather than choosing for them; everything else is
   mechanical.

6. **Run the gate on what you composed.** Every unit passed it already;
   the assembled document is a new file, and the gate is this layer's
   only exit:

   ```bash
   python -m chitragupta.draft gate content/drafts/<book>/book.tex
   ```

   A `FAIL` here is a failing test, not a warning. Never "fix" one by
   inventing or altering a citekey -- correct the reference or take the
   claim out, in the unit it came from, via `draft-reviser`.

7. **Run the prose check over the units, not the skeleton.** `book.tex`
   is structure and holds no prose, so scanning it would report nothing
   and mean nothing. Run it per accepted unit:

   ```bash
   python -m chitragupta.draft style content/drafts/<book>/<unit-id>.md
   ```

   **It checks only what `docs/WRITING-STANDARDS.md` §9 marks decidable**
   -- §2's defect markers, an acronym never expanded at first use, a
   glossary acronym whose expansion has drifted from the vocabulary, and
   §8's dialect against `scope.md`'s `language:` line. It says nothing
   about whether a paragraph leads with its point. **Report every
   finding and fix none of them.** A finding is a place to look, not a
   defect, and acting on one is `draft-reviser`'s copy-edit mode, in the
   unit that owns the prose. A review aid, not a gate: it exits 0
   whatever it finds.

8. **Run the verbatim scan, per unit.** Assembly is the last moment
   before a whole book is read by somebody else, which makes it the
   right moment to run this. Per unit, rebuild the section map and scan:

   ```bash
   python -m chitragupta.draft dossier sections content/drafts/<book>/<unit-id>.md --citekeys --write
   python -m chitragupta.review verbatim scan content/drafts/<book>/<unit-id>.md
   ```

   The first command is not optional. The embedding tier compares each
   section against the citekeys that section's `sections.md` row records,
   and a unit accepted weeks ago may have been revised since. If it exits
   1 for a missing dossier, say so and scan that unit anyway.

   It reports wording a unit shares with **any** parsed source, cited or
   not. **A review aid, not a gate: it exits 0 either way, and it is
   never a condition of presenting** -- a unit with findings is still an
   assembled unit, and this step reports rather than withholds. Show what
   it found rather than summarising it away, and lead with the `long` and
   `short` buckets -- a `quoted` run that also cites its source is a
   legitimate attributed quotation, so give those a count rather than a
   list. **Say what it did not check:** if `tiers_not_run` is not empty,
   quote each reason as the scan wrote it, and where the reason names a
   fix (`poetry install --with enrich`, `python -m chitragupta.enrich`)
   pass that on once. It sees verbatim and
   near-verbatim reuse only, and **genuine restatement is only detected
   where the embedding tier can run**, so a clean scan is not a clean
   bill of health (`docs/PLAGIARISM.md`). Repairing a finding is
   `overlap-reviser`'s job, one finding at a time, in the unit that owns
   the wording, and only if the user asks.

   Report the per-unit results as one table rather than a wall: the book
   has fifteen chapters, and fifteen separate scan reports is how a real
   finding gets skimmed past.

9. **Build the PDF, if the toolchain is there.** From the book's own
   directory, because the `\input` paths are relative to it:

   ```bash
   cd content/drafts/<book>
   pdflatex -interaction=nonstopmode book.tex
   pdflatex -interaction=nonstopmode book.tex
   ```

   **Two passes, and no bibliography pass at all.** Citeproc resolved
   every citation when the units were converted, so the document contains
   no `\cite` for `bibtex` or `biber` to answer. The second pass is what
   resolves `\cref` and the table of contents.

   **Read `book.log` before believing the PDF.** A `pdflatex` run that
   exits 0 can still be missing something -- a dropped citation is
   reported as a warning, not an error:

   ```bash
   python3 -c "import re,pathlib; log=pathlib.Path('book.log').read_text(errors='replace'); \
       print(sorted(set(re.findall(r\"Citation \`([^']+)' on page\", log))))"
   ```

   Anything but `[]` means a citekey did not reach the bibliography --
   go back to the conversion step, do not hand over the PDF. Python
   rather than `grep -c` deliberately: on the host this was first run,
   `grep -c` over that log printed nothing at all, and a check that
   silently reports nothing is worse than no check.

   **If the units number their own headings, turn LaTeX's numbering
   off** -- `\setcounter{secnumdepth}{-2}` in the preamble. A book whose
   Markdown says `## 1.0 Before you start` otherwise renders "1.1 1.0
   Before you start", and worse further in ("10.1510.14"). Which
   numbering a book shows is a composition decision and belongs in
   `book.tex`; renumbering the author's headings does not, and is
   `draft-reviser`'s call rather than this skill's.

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

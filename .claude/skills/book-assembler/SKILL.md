---
name: book-assembler
description: Assembles accepted, gate-passed units into one LaTeX book -- front matter, parts, chapters, back matter -- from the outline `python -m src.draft spec` holds and the acceptance records `python -m src.draft unit` wrote. Triggers when the user asks to assemble, build, compose or "put together" a book from units already drafted, or asks for the whole book as one LaTeX document. Writes no prose of its own and drafts no unit: a missing or unaccepted unit is the relevant genre skill's job, and this skill stops and says which. Runs `python -m src.draft registry check` and reports every finding before composing, runs `python -m src.draft gate` on what it composed, and stops at the second of the book track's two human sign-offs rather than declaring a book finished. Never fabricates a citekey and never edits a unit's prose.
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
|---|---|
| A unit named in the outline has no prose | Stop. Say which. Drafting it is `thesis-chapter-writer`'s job (or another genre's), not this skill's |
| A unit exists but nobody accepted it | Stop. `python -m src.draft unit accept` is a human's call, made per unit |
| The user wants a unit's wording changed | `draft-reviser`. Never edit a unit while assembling it |
| The outline itself is wrong | `python -m src.draft spec` and a fresh sign-off. Never rewrite an outline here |
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
|---|---|---|
| `# Title` | `\title{...}` in the preamble | -- |
| `## Part {#part-i}` | `\part{...}` | `\label{part-i}` |
| `### Chapter {#ch-1}` | `\chapter{...}` | `\label{ch-1}` |
| `#### Section {#sec-1}` | `\input{sec-1.tex}` | the unit's own `\label{sec-1}` |

**The `{#id}` becomes the LaTeX label, unchanged.** That is what makes
the cross-references the registry checked actually resolve in the built
PDF: a unit's `\cref{ch-1}` points at the same id the outline declared
and `python -m src.draft registry check` verified. Never rename one on
the way through.

The document skeleton, in order:

```latex
\documentclass[11pt,a4paper]{book}
% packages the units actually need, and no others
\usepackage{cleveref}
% the bibliography stack -- probed, not assumed; see below

\title{<the outline's own title>}
\author{<ask the user; never invent one>}

\begin{document}
\frontmatter
\maketitle
\tableofcontents

\mainmatter
% \part / \chapter / \input, in outline order

\backmatter
% \printbibliography (biblatex) or \bibliography{...} (natbib)
\end{document}
```

**Probe for the bibliography stack; never assume one.** This is
`DEVELOPER-AGENTS.md`'s standing rule, and it is not hypothetical here:
the host this skill was first exercised on has `pdflatex` but no
`biblatex.sty` and no `biber`, so a document that assumed them failed at
`\usepackage` with nothing built.

```bash
kpsewhich biblatex.sty && command -v biber      # the biblatex path
kpsewhich natbib.sty                            # the fallback, near-universal
```

| Present | Preamble | Back matter | Build |
|---|---|---|---|
| `biblatex` **and** `biber` | `\usepackage[backend=biber]{biblatex}` + `\addbibresource{<bib>}` | `\printbibliography` | `pdflatex`, `biber`, `pdflatex` ×2 |
| otherwise | `\usepackage{natbib}` | `\bibliographystyle{plainnat}` + `\bibliography{<bib without .bib>}` | `pdflatex`, `bibtex`, `pdflatex` ×2 |

Say which one you used and why. `\citep`/`\citet` -- what
`thesis-chapter-writer` emits -- work under both, so the units need no
change either way.

Two rules about that skeleton, both from `AGENTS.md`:

- **The bibliography points at the user's own `.bib` file**, the same one
  `python -m src.corpus sync` read -- not a copy, and never a file this
  skill writes. The bib file is the source of truth; this pipeline is
  downstream of it.
- **A unit is `\input` as a fragment.** Units drafted by
  `thesis-chapter-writer` are already standalone `.tex` fragments with no
  preamble, which is exactly this shape. A Markdown unit is converted
  with pandoc directly:

  ```bash
  pandoc <unit-id>.md -t latex --natbib --no-highlight \
      --top-level-division=chapter -o <unit-id>.tex
  ```

  **Not `python -m src.draft render --format tex`**, which this file used
  to say and which cannot work: `render` is the publish step for *one
  draft*, so it emits `--standalone` with its own `\documentclass{article}`
  and resolves citations through `--citeproc` into a bibliography of its
  own. `\input` that into a book and LaTeX meets a second
  `\begin{document}`. Measured on the first real assembly (a 15-chapter
  book, 2026-08-19): the fragment form is what composes, and `--natbib`
  is what leaves one bibliography at the end of the book instead of
  fifteen.

  Two things the conversion has to get right, both learned from that same
  build:

  - **A citekey containing `--` is truncated by pandoc's citation
    tokenizer.** `@lim_state---art_2020` reaches LaTeX as `lim_state`,
    resolves to nothing, and renders as `[?]` -- a citation silently
    dropped from a 500-page book, which is exactly the failure this
    project exists to prevent. Before converting, rewrite the affected
    bracketed groups in a **temp copy** of the Markdown to raw LaTeX --
    `[@a; @b---c_2024]` becomes `\citep{a,b---c_2024}` -- which pandoc
    passes through untouched, so the key in the book stays byte-identical
    to the key in the `.bib`. Never alias the key and never edit the
    author's file. `src/render_output/_citeproc.py::_alias_for` solves
    the same problem the other way for the single-draft path; the raw
    form is preferable here because it invents nothing.
  - **The outline's ids go in as labels after conversion.** Pandoc emits
    its own `\label{}` from the heading text; add `\label{<unit-id>}` (and
    the chapter's `\label{ch-NN}`) immediately after the fragment's own
    `\chapter{...}\label{...}`, so a label binds to the chapter counter
    rather than to whatever sectioning command follows it.

## Process

1. **Confirm the outline is signed off.** The first of the track's two
   human gates. Do not compose anything until this exits 0:

   ```bash
   python -m src.draft spec status content/drafts/<book>
   ```

   Non-zero means nobody approved this outline, or it changed after
   somebody did. Either way, stop and say which -- approving it is the
   user's act, not yours, and `python -m src.draft spec sign` is theirs
   to run.

2. **Confirm every unit is accepted and current.**

   ```bash
   python -m src.draft unit status content/drafts/<book>
   ```

   Report the table as it stands. A unit reading `unwritten`, `drafted`
   or `stale: ...` is not assemblable, and the reason matters to the
   user: `stale: inputs changed` means the outline moved under prose
   somebody already accepted, which is a decision for them and not a
   thing to paper over by assembling the old text.

3. **Rebuild the registries and report every finding.** This step is not
   optional and is not summarised away:

   ```bash
   python -m src.draft registry build content/drafts/<book>
   python -m src.draft registry check content/drafts/<book>
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

4. **Compose the book.** Write `content/drafts/<book>/book.tex` from the
   conventions table above, in outline order, `\input`-ing only units
   step 2 reported as `accepted`. Ask the user for the author line and
   the document class options rather than choosing for them; everything
   else is mechanical.

5. **Run the gate on what you composed.** Every unit passed it already;
   the assembled document is a new file, and the gate is this layer's
   only exit:

   ```bash
   python -m src.draft gate content/drafts/<book>/book.tex
   ```

   A `FAIL` here is a failing test, not a warning. Never "fix" one by
   inventing or altering a citekey -- correct the reference or take the
   claim out, in the unit it came from, via `draft-reviser`.

6. **Run the prose check over the units, not the skeleton.** `book.tex`
   is structure and holds no prose, so scanning it would report nothing
   and mean nothing. Run it per accepted unit:

   ```bash
   python -m src.draft style content/drafts/<book>/<unit-id>.md
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

7. **Offer the verbatim scan, per unit.** Assembly is the last moment
   before a whole book is read by somebody else, which makes it the
   right moment to offer this -- don't run it silently, and never make
   it a condition of presenting:

   ```bash
   python -m src.review verbatim scan content/drafts/<book>/<unit-id>.md
   ```

   It reports wording a unit shares with **any** parsed source, cited or
   not. Say what it misses when you offer it: it sees verbatim and
   near-verbatim reuse only, and **genuine restatement is only detected
   where the embedding tier can run**, so a clean scan is not a clean
   bill of health (`docs/PLAGIARISM.md`). A review aid, not a gate: it
   exits 0 either way. Repairing a finding is `overlap-reviser`'s job,
   one finding at a time, in the unit that owns the wording.

8. **Build the PDF, if the toolchain is there.** A full book is a LaTeX
   document with its own bibliography pass, so build it directly, from
   the book's own directory -- the `\input` paths are relative to it:

   ```bash
   cd content/drafts/<book> && pdflatex -interaction=nonstopmode book.tex
   biber book        # or: bibtex book, per the probe above
   pdflatex -interaction=nonstopmode book.tex && pdflatex -interaction=nonstopmode book.tex
   ```

   Two passes after the bibliography, because that is what resolves
   `\cref` and the table of contents. `python -m src.draft render` is the
   renderer for a *single* draft and is the right tool for a unit
   preview; it is not a book build, and it does not run a bibliography
   pass.

   **Read `book.log` for undefined citations before believing the PDF.**
   A `pdflatex` run that exits 0 can still have dropped a citation --
   natbib reports it as a warning, not an error, and the book renders
   with `[?]` where the reference should be:

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

9. **Stop at the sign-off.** This is the second of the two human gates,
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

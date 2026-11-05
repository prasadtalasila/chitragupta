# 📦 Assemble, build and sign off the book

Status: **tutorial**, steps 6 to 8 of [Write a book](../WRITE-A-BOOK.md).

**Written for** anyone turning accepted chapters into one PDF.
**Assumed:** every unit accepted and the registries built
([step 5](registries.md)). **Not covered here:** what goes in the front
and back matter, which is the outline's call
([front matter](front-matter.md), [back matter](back-matter.md)).

## ▶ Step 6: assemble the book

Ask for the book and `.claude/skills/book-assembler/` runs steps 5 to 7:
it confirms both `status` commands, prints every registry finding, and
only then composes. Everything it assembles has already passed every gate
per unit, so assembly is deterministic composition plus a human
sign-off; there is no enforcement machinery here to write.

**The whole composition is one table**, and the ids carry through
unchanged:

| Outline | LaTeX | Label |
| --- | --- | --- |
| `# Title` | `\title{\BookTitle}`, on the title page and the copyright page | none |
| `- author: ...` | `\author{\BookAuthor}`, the same two pages | none |
| `## Part {#part-i}` | `\part{...}` | `\label{part-i}` |
| `### Chapter {#ch-1}` | `\input{ch-1.tex}`, the unit, whose own `#` heading becomes `\chapter{...}` | `\label{ch-1}` |
| `#### Section {#sec-1}` | a heading inside `ch-1.tex`, never a file of its own | `\label{sec-1}` |
| `## ... {#front}` | no `\part`; its chapters after `\tableofcontents`, under `\frontmatter` | each chapter's id |
| `## ... {#appendices}` | no `\part`; `\appendix`, then its chapters, numbered A, B, ... | each chapter's id |
| `## ... {#back}` | no `\part`; under `\backmatter`, its entries in outline order, then the bibliography | each chapter's id |
| `### ... {#glossary}`, `{#symbols}`, `{#figures}`, `{#tables}` | a generated page, where the outline puts it ([back matter](back-matter.md)) | none |

So the assembled book reads, in order: title page, your copyright page,
table of contents, front matter, the parts and their chapters, the
appendices, the back matter, the bibliography.

Because the `{#id}` becomes the LaTeX label unchanged, the
cross-references `registry check` verified resolve in the built PDF: the
outline, the registry and the document all name the same thing.

**The bibliography is one list at the end of the book.** Each unit is
converted with

```bash
chitragupta draft render <unit>.md --format tex --fragment
```

and `--fragment` changes the output: no preamble, the unit's own `#`
heading becomes a `\chapter`, and code blocks are left unhighlighted
because `Shaded`/`Highlighting` exist only in the standalone template.
It also **defers its citations**: the fragment emits `\citep{...}`
instead of a resolved `[1]`, and carries no reference list of its own.
`book.tex` then holds `\bibliographystyle{IEEEtran}` and
`\bibliography{bibliography}`, and one `bibtexu` pass numbers every
citation in the whole document at once.

**The resolution has to move along with the list.** Citeproc assigns
numbers in the same pass that builds the list. Resolve per unit and every
chapter restarts at `[1]`, so chapter 1's `[2]` and chapter 2's `[2]` are
different papers; collect those into one back-of-book list and half the
markers point at the wrong entry, in a book that compiles cleanly.
Deferred, a source cited in two chapters carries **one** number in both
and the sequence runs continuously (measured both ways on a real
two-chapter build).

The **citekey aliasing** applies on both sides: a key
containing `--` (`@lim_state---art_2020`) would otherwise reach LaTeX
truncated and render as `[?]`, so the render rewrites it to
`lim_state-x2d-x2d-art_2020` in the fragment *and* in the `.bib` it
copies beside `book.tex`. Never hand-edit either.

A **standalone** render (the same unit without `--fragment`) uses
citeproc, the vendored IEEE style, and its own numbered
reference list, exactly as every other genre skill produces one. The two
shapes exist because a chapter read alone wants its sources at the end of
the chapter, and the same chapter in a book wants them at the end of the
book.

### 🔠 Brace-protect acronyms in your `.bib` titles

Two IEEE implementations format your references: `assets/csl/ieee.csl`
for a standalone render, and `IEEEtran.bst` for the assembled book. They
agree, byte for byte, on every entry measured, **provided acronyms in a
title are wrapped in braces**:

```bibtex
title = {A Survey of {IoT} and {AI} Digital Twins: An {FMI}-Based Approach}
```

Unbraced, `bibtexu` lowercases them and the book's bibliography reads "a
survey of iot and ai digital twins". Citeproc preserves them, so the same
entry is correct in a standalone render and wrong in the book. Braced,
both produce the same line.

This is ordinary BibTeX practice (braces mean "do not change this
case"), and only the book build depends on it, because a book is the
one output this pipeline runs through a `.bst` style. It is a property
of **your own export**, so fix it in your reference manager, not in
`papers/bibliography.bib`, which a re-export overwrites. Nothing in the
pipeline rewrites your titles: it would have to guess which capitalised
word is an acronym and which is a proper noun, and this project does not
silently alter a human's bibliographic data.

The book also sets `margin=80pt`, about 28mm.
The `book` class's own margins are 94pt inner and 143pt outer (measured),
generous enough to run a 15-chapter book to 546 pages; a third of that
was tried and read too tight for print, so the setting is that doubled.

`book.md` is written beside `book.tex`, in
`content/rendered/<book>/`: the same structure in Markdown, hyperlinking
the chapter files alongside it, for anyone who is not building LaTeX.

**Where the registry proposal's "blocking" lives.** The skill must run
`registry check` and print every finding, in full, before composing.
That is the guaranteed *invocation* ARCHITECTURE.md permits, in place of
the conformance it does not. `tests/test_skill_book_assembly.py` pins
that, so a hand edit dropping either half fails the suite.

## ▶ Step 7: build the PDF

A book is built directly, from its own directory, because the `\input`
paths are relative to it:

```bash
cd content/rendered/twins
lualatex -interaction=nonstopmode book.tex
bibtexu book
lualatex -interaction=nonstopmode book.tex
lualatex -interaction=nonstopmode book.tex
```

**LuaLaTeX and `bibtexu`, as the pdf render is**: a chapter prints in
the same fonts in the book as in its own pdf, and `bibtexu` abbreviates
a first name by character, so an initial such as `Ö.` survives into the
bibliography. The four passes take about 86 s for a 287-page book.
`bibtexu` exits 1 when the `.bib` has only warnings; read `book.blg` for an
`error`.

**Four passes, and the `bibtexu` one is not optional**: the first
`lualatex` records which keys the document cites, `bibtexu` turns those
into `book.bbl`, the third pulls the bibliography in, and the fourth
resolves `\cref`, the table of contents and the citation numbers now that
the entries exist. Skip it and every citation renders `[?]` while
`lualatex` still exits 0.

**With an index, two more steps** ([the index](book-index.md)): once the
fourth pass has settled the page breaks, `registry index` turns
`book.idx` into `book.ind`, and a fifth pass prints it:

```bash
(cd - >/dev/null && chitragupta draft registry index \
    content/drafts/twins --idx content/rendered/twins/book.idx)
lualatex -interaction=nonstopmode book.tex
```

**Then read the log before trusting the PDF.** `lualatex` exits 0 on a
book that renders `[?]` where a reference should be, because natbib
reports a dropped citation as a warning, not an error:

```bash
python3 -c "import re,pathlib; log=pathlib.Path('book.log').read_text(errors='replace'); \
    print(sorted(set(re.findall(r\"Citation \`([^']+)' on page\", log))))"
```

Anything but `[]` means a citekey never reached the bibliography. The
check uses Python rather than `grep -c` because `grep -c` over that log
has been seen to print nothing at all, and a check that silently reports
nothing is worse than no check.

**`content/specs/<book>/preamble.tex` is the supported way to override
anything the assembled `book.tex` sets.** It is optional and most books
have none; if it exists, `book-assembler` copies it beside `book.tex` and
`\input`s it as the last line of the generated preamble, so it wins over
the defaults above it. **Do not hand-edit `book.tex` to do this.** That
file is regenerated every time the book is assembled, so an edit to it is
lost at the next run, while `preamble.tex` is yours and survives.

**If your units number their own sections** (`## 1.0 Before you start`),
put `\setcounter{secnumdepth}{-2}` in `content/specs/twins/preamble.tex`,
or LaTeX numbers them a second time ("1.1 1.0 Before you start", and
worse further in).

**A chapter title that carries its own number needs no preamble line.**
For a unit headed `# Chapter 1: Why Anyone Pays`, step 6's
`draft render --fragment` drops the `Chapter 1:` prefix from the
`\chapter{}` it emits, so the number comes from the `book` class alone
and every section and table keeps its numbering. Your `.md` is not
touched: it still titles that unit's own standalone pdf, and every unit
stays `accepted`. Do not use `secnumdepth{-2}` for this: it would take
away every section and table number in the book to fix one chapter
title.

A unit you drafted as `.tex` is the exception: step 6 does not convert
it, so the prefix reaches the book as you wrote it. `chitragupta draft
style` reports that one as `chitragupta.ChapterSelfNumbered`; delete the
prefix from the `\chapter{}` and let the book supply the number.

The default `book.tex` sets `\setcounter{secnumdepth}{2}` (the `book`
class's own default, restated so a book states its numbering rather than
inheriting it silently) and `\setcounter{tocdepth}{1}`, which stops the
table of contents at the section. Which numbering a book shows is a
composition decision and belongs to the book; renumbering your headings
does not, and is `draft-reviser`'s call.

## ▶ Step 7b: the one review aid that reads a book

Every other aid reads a draft; this one reads the **assembly**, and asks
a question only a book can be asked: does the assembled document still
carry every citekey its accepted units stand on?

```bash
chitragupta review union content/rendered/twins/book.tex
```

It is advisory: it exits 0 whatever it finds and blocks nothing. It
reports two findings, which mean opposite problems:

| Finding | What happened | Usually means |
| --- | --- | --- |
| `dropped` | an accepted unit the assembly never `\input`s, named with every citekey the book then holds nowhere else | a chapter left out of `book.tex` by accident, which a PDF that compiles does not show |
| `appeared` | a citekey in a file the assembly includes that no unit owns | a copyright page or preamble file citing something; fine if deliberate, a leak if not |

It resolves the assembly's `\input` chain instead of grepping
`book.tex` for citekeys, because each unit's `\citep{...}`
calls sit in that unit's fragment, so `book.tex`'s own text states no
citekey at all. An aid that read only `book.tex` would report every
source in a correct book as lost.

Two things it refuses, both exit 1: a path in no book (there is no
expected set to compare against), and a path that is itself one of the
book's units. Pointed at a unit, it would report every *other* unit's
citekeys as dropped.

Per-chapter aids still apply. Run them before assembly:

```bash
chitragupta review agenda content/drafts/twins/ch-fidelity.md
```

Its findings are the chapter author's, in the same `[unattended]` /
`[surfaced]` shape each genre tutorial describes.

## ▶ Step 8: the second sign-off

The assembler presents what it composed (the unit count, what the
registries could not read, every finding, and what the gate and the two
review aids said) and stops there. **It does not say the book is
finished**, and neither does anything else in this pipeline.

No check reads the argument. The checks establish that a book is
grounded, consistent and complete, not that it is any good; that
judgement is the second human gate, and it is yours.

The assembler has already run the prose check (`draft style`) and the
verbatim scan on every unit and reported both. If you change a unit after
assembly, run them again on that unit, not on `book.tex`, which holds no
prose. Both are review aids that exit 0 whatever they find. The scan sees
verbatim and near-verbatim reuse only; real restatement is only detected
where the embedding tier can run, so a clean scan does not rule
restatement out ([PLAGIARISM.md](../PLAGIARISM.md)). A change to a unit's
prose goes
through `draft-reviser`, and an unattended agenda finding through
`agenda-reviser`; then re-accept the unit (step 4) and reassemble.

## 📝 What one real book looked like

The first book assembled by this track was a 15-chapter textbook,
22,155 lines of Markdown, measured on 2026-08-19:

| | |
| --- | --- |
| outline | 3 parts, 15 chapters, 15 units |
| citations, gate-verified | 864 across the 15 units, 194 distinct citekeys |
| terminology registry | 15 definitions (read from the drafts' prose; since #1138 it reads the dossiers' glossaries) |
| claim register | 388 claims |
| cross-reference graph | 0 edges; the chapters refer to each other in English, not as links |
| `registry check` | 1 finding: one claim made in two chapters |
| the book | 430 pages, 1.7 MB, 0 undefined citations |

That build is also why the skill aliases citekeys containing `---`:
three such keys carried 10 citations that would otherwise have rendered
as `[?]`.

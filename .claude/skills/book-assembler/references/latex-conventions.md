# The book's LaTeX conventions

Read this before composing `book.tex`, and follow it exactly. Paths here
are from the project root.

The whole of the composition is this table. The outline
(`content/specs/<book>/spec.md`) is planned top-down; the book is emitted
bottom-up from what has been accepted.

| Outline | LaTeX | Label |
| --- | --- | --- |
| `# Title` | `\title{...}` in the preamble | -- |
| `## Part {#part-i}` | `\part{...}` | `\label{part-i}` |
| `### Chapter {#ch-1}` | `\input{ch-1.tex}`, the unit, whose own `#` heading becomes `\chapter{...}` | `\label{ch-1}` |
| `#### Section {#sec-1}` | a heading inside `ch-1.tex`, never a file of its own | `\label{sec-1}` |
| `## Front matter {#front}`, `## Appendices {#appendices}`, `## Back matter {#back}` | no `\part`: see "Front matter, appendices and back matter" | -- |

A chapter the outline describes only at chapter level (a book
retrofitted from older prose) has a single section, and that section is
the unit: `\input{<section-id>.tex}`.

**The `{#id}` becomes the LaTeX label, unchanged.** That is what makes
the cross-references the registry checked actually resolve in the built
PDF: a unit's `\cref{ch-1}` points at the same id the outline declared
and `python -m chitragupta.draft registry check` verified. Never rename one on
the way through.

The document skeleton is
`.claude/skills/book-assembler/assets/book-skeleton.tex`. Copy it into
`book.tex` rather than retyping it: replace each `<...>` placeholder
(the outline's own title; its `- author:` line, or an author you ask
the user for and never invent; the build line), keep the
`\input{preamble}` line only if the book has one (see "An authored
preamble" below), and put each outline entry where "Front matter,
appendices and back matter" below says. Each line's comment names the section below
that explains it.

**The two `\setcounter` lines, and which is which.** `secnumdepth{2}` is
the `book` class's own default, restated here so the book *states* its
numbering rather than inheriting it silently -- an outline's section
titles carry no numbers of their own, so LaTeX supplies them and nothing
is numbered twice. `tocdepth{1}` is the real setting: the class defaults
to 2, which lists every subsection, and a book's table of contents stops
at the section. Subsections are still numbered and still `\cref`-able;
they are simply not listed.

**A self-numbered *chapter title* is a different clash, and this is
the wrong lever for it** (#804). A unit headed `# Chapter 1: Why
Anyone Pays`, or an appendix headed `# Appendix A: The Mathematics You
Need` (#1137), is numbered twice by the `book` class, but
`secnumdepth{-2}` pays a document-level price for a chapter-level
problem. Measured on one real book, four passes each:

| | `secnumdepth{2}` (the skeleton) | `secnumdepth{-2}` |
| --- | --- | --- |
| Chapter opening | `Chapter 1` / `Chapter 1: Why Anyone Pays` | correct |
| ToC chapter line | `1 Chapter 1: Why Anyone Pays` | correct |
| ToC section lines | `1.1`, `1.2`, ... `1.10` | **all numbers lost** |
| Table captions | `Table 1.1`, `2.1`, ... | `Table 1`, `2`, ... flat |

**Nothing is asked of you here: SKILL.md's step 4 render drops the
prefix already.** `draft render --fragment` emits `\chapter{Why Anyone
Pays}` from that heading, so the number comes from the class alone
and sections, tables and figures keep theirs. The authored `.md` is
untouched, every unit stays `accepted`, and the unit's own standalone
pdf keeps the prefix that titles it. If a book already carries
`secnumdepth{-2}` for this reason, **remove it** -- it is now costing
the section and table numbering for a clash that no longer exists.

A unit drafted as `.tex` is the exception, because SKILL.md's step 4
never converts it: there the prefix is in the file you `\input`, and
`draft style` reports it as `chitragupta.ChapterSelfNumbered` in
SKILL.md's step 7 for the author to delete.

**Front matter, appendices and back matter** (#1137). Three part ids
are reserved, and `spec` refuses an outline that puts one out of
place: `{#front}` is the first part, `{#appendices}` follows every
other part, `{#back}` is the last. None of them prints a `\part` page;
each switches the `book` class into a mode instead:

| Outline | In `book.tex` |
| --- | --- |
| `## Front matter {#front}` | its entries, in outline order, after `\tableofcontents` and still under `\frontmatter`: roman page numbers, unnumbered chapters |
| `## Part ... {#part-i}` and its chapters | under `\mainmatter`, as the table above says |
| `## Appendices {#appendices}` | `\appendix\crefalias{chapter}{appendix}` after the last main-matter chapter, then each appendix's `\input` and labels exactly as a chapter's: they number A, B, ..., and `\Cref` prints "Appendix A" (without the alias cleveref says "Chapter A") |
| `## Back matter {#back}` | `\backmatter`, then its entries in outline order, then the bibliography, then the index if the outline has `{#index}`: the index is always last, the bibliography last before it |

A front- or back-matter chapter the author wrote (a preface, "About the
author") is a unit like any other: converted in step 4 and `\input`
where it stands. Five chapter ids are **generated pages** instead: no
file, no unit, nothing to convert. Each prints where the outline puts
it, only if it has something to show; one with nothing is left out and
said nothing of:

| Entry | Prints | Only if |
| --- | --- | --- |
| `### Glossary {#glossary}` | `\input{glossary}` | step 3 wrote `glossary.tex` |
| `### List of Symbols {#symbols}` | `\input{notation}` | step 3 wrote `notation.tex` |
| `### List of Figures {#figures}` | `\cleardoublepage\phantomsection\addcontentsline{toc}{chapter}{\listfigurename}\listoffigures` | a fragment holds `\begin{figure}` with a `\caption` |
| `### List of Tables {#tables}` | the same with `\listtablename` and `\listoftables` | a fragment holds a `longtable` with a `\caption` |
| `### Index {#index}` | `\printindex`, after the bibliography wherever the outline lists it | step 3 wrote `index-terms.json`; see "The index" below |

`\cleardoublepage` before `\phantomsection` puts the contents entry on
the list's own page; `\listoffigures` adds none of its own.

**An outline with none of the three reserved parts** is one written
before #1137, and assembles as it always did: `\input{glossary}` then `\input{notation}`
under `\backmatter`, each only if step 3 wrote it, then the
bibliography, and no list of figures or tables.

**The copyright page is the author's file**, `content/specs/<book>/copyright.tex`,
which `spec init` copies from `assets/book/copyright.tex`. If it
exists, copy it beside `book.tex` as you copy `preamble.tex`, and
`\input{copyright}` right after `\maketitle`; if it does not, write no
`\input` and say nothing. Never edit it: its wording, licence and year
are the author's. It uses three macros the skeleton defines:

- `\BookTitle`: the outline's `#` heading, which `\title` uses too;
- `\BookAuthor`: the outline's `- author:` line (`spec show` prints it),
  which `\author` uses too;
- `\BuildLine`: `Built <today, YYYY-MM-DD> \textperiodcentered{} outline
  <digest> \textperiodcentered{} chitragupta <version>`, the digest from
  `python -m chitragupta.draft spec status` ("signed off at digest ...")
  and the version from `chitragupta --version`. It names the approved
  outline and the tool that built it; it is not a copyright date.

**An authored preamble, if the book has one.** If
`content/specs/<book>/preamble.tex` exists, copy it beside `book.tex`
(copy, never `\input` across directories: every `\input` path in
`book.tex` is relative to the book's own directory, and one that reached
out of it would break the moment the book was built anywhere else) and
`\input` it as the **last line of the preamble**, immediately before
`\begin{document}`, so it overrides every default the skeleton sets. It has to
land there rather than later in the document: a `\setcounter` after
`\begin{document}` is read too late to change how the body was set. If it does not
exist, emit no `\input` at all and say nothing -- its absence is the
ordinary case, not a finding. That file is where a book that does number
its own headings puts `\setcounter{secnumdepth}{-2}`, and where anything
else this skeleton gets wrong for one book gets corrected without
editing the skeleton for every book.

Note the two senses of "preamble" this file uses: the **generated**
preamble is the skeleton, copied into `book.tex`; the
**authored** preamble is `preamble.tex`, a file the user owns.

**The bibliography is one list at the end of the book, built by one
`bibtex` pass.** A unit converted `--fragment` emits `\citep{...}` and no
reference list of its own; `bibtex` numbers every citation in the
assembled document at once, against `IEEEtran.bst` for IEEE numeric
markers. `chitragupta install os-deps` installs `bibtex` and
`IEEEtran.bst` for exactly this.

**Why not resolve per unit and move the list.** Citeproc assigns numbers
in the same pass that builds the list, so a per-unit resolution gives
chapter 1 and chapter 2 each their own `[1]`, `[2]`, `[3]` for different
sources. Collecting those into one back-of-book list would leave every
marker pointing at the wrong entry -- a book that compiles cleanly and
cites the wrong paper. Measured both ways: deferred, a source cited in
two chapters carries **one** number in both, and numbering runs
continuously across the book.

`natbib`'s `[numbers,sort&compress]` is what makes those markers IEEE
numeric rather than its author-year default, which is not this pipeline's
house style.

**The `.bib` is written beside `book.tex` by the render**, not by this
skill -- `draft render --fragment` copies the corpus bibliography into
`content/rendered/<book>/` with every `--`-bearing citekey aliased to
match the `\citep{...}` in the fragments. Do not hand-write or edit it.

Standalone renders are untouched by any of this: a draft rendered without
`--fragment` still resolves its citations with pandoc's citeproc against
`assets/csl/ieee.csl` and still carries its own reference list, which is
what every other genre skill produces.

**Wide code lines: the book must supply `fvextra` too**, and for the
same structural reason as the citeproc macros. A `verbatim` line is one
unbreakable box, so a code line wider than the page runs into the margin
-- measured on a real 428-page assembly, the largest single class of
`Overfull \hbox` warnings it produced. `draft render` loads `fvextra`
itself for a standalone Markdown draft, but a unit is converted
`--fragment`, which emits no preamble for that load to land in, so the
book's own preamble carries it. Only `verbatim` needs redefining here,
not `Highlighting`: `--fragment` travels with `--no-highlight`, so a
fragment's fences are always plain `verbatim`.

`breaklines` without `breakanywhere`, deliberately -- a break lands at a
space rather than mid-identifier, and each continuation is marked `,→`
so a wrapped line cannot be misread as two. A line over the limit is
reported as `chitragupta.WideCodeLine`
([docs/WRITING-STANDARDS.md](../../../../docs/WRITING-STANDARDS.md) §14);
shortening it avoids the marker, and this load is what stops it
overflowing when nobody does.

**Table captions: `\LTcapwidth`, for the same `--fragment` reason.**
`longtable.sty` initialises that register to a hardcoded **4in** rather
than to anything derived from the page, and pandoc writes every
Markdown table as a `longtable` -- so a caption wraps inside the middle
half of a 80pt-margin line while the prose around it runs the full
`\textwidth`. `draft render` sets it for a standalone draft; a unit
converted `--fragment` has no preamble for that to land in, so the book
sets it here. Unguarded, unlike the render's own `\ifdefined` form: the
skeleton's line above it loads `longtable` unconditionally, so the register always
exists by this point.

**TikZ libraries: the book must load them, and no figure file may.**
Same structural reason as `fvextra` and `\LTcapwidth` --
`draft render` puts the union of a draft's `\usetikzlibrary` names in its
own preamble, and a unit converted `--fragment` has no preamble for that
to land in.

It is not merely a convenience here. A figure file is `\input` **inside a
`figure` float**, and a float is a group: the library's macros are
defined locally and die with the float, while
`\tikz@library@<name>@loaded` is set globally -- so the second figure in
the book skips the load and finds no macros. Every per-figure workaround
for that is worse, because `tikzlibrarypositioning.code.tex` appends to
`\tikz@node@reset@hook` *globally* on every load, so N loads apply every
node's placement shift N times. Measured on a three-float document:
71.26pt, then 128.17pt, then 185.07pt, with the engine exiting 0 and
nothing but `Overfull \hbox` in the log. That is how figures that fit in
their single-chapter PDF spilled off the page of this project's own
assembled book (#781).

**Take the union from the renders, not by guessing.** Each
`draft render --fragment` prints one line per unit whose figures ask for
a library:

```text
[tikz-libraries] fit,positioning -- a fragment has no preamble; load these in the assembling document
```

Collect those across every unit, deduplicate, and write the result as the
single `\usetikzlibrary` line in the skeleton. Never write
`\usetikzlibrary{}` -- an empty comma list fails fatally rather than
skipping a name -- so a book whose units draw no figure omits both that
line and the skeleton's `\usepackage{tikz}` above it.

A unit's figure file still carries its own plain `\usetikzlibrary` line,
and that is correct: with the book's preamble load already done it is a
no-op that appends nothing, and it is what lets the same figure compile
in a thesis chapter's fragment and in `review figure`'s probe.
What a figure file must **never** contain is a hand-rolled load -- no
clearing of `\tikz@library@...@loaded`, no saving or restoring of
`\tikz@node@reset@hook`. `python -m chitragupta.review figure` reports
one as `loads-library-by-hand`.

**Figure placement: `chitragupta-floats.tex`, for the same `--fragment`
reason** (#1065). LaTeX's class defaults move a figure about half a
page tall onto a page of its own, centred with blank space above and
below. On this project's reference book that cost three pages, and
`draft render` now sets different float fractions for a standalone
draft. A unit rendered with `--fragment` that draws a figure prints one
line and gets the file copied beside it:

```text
[floats] chitragupta-floats.tex copied beside the fragment -- a fragment has no preamble; \input{chitragupta-floats} in the assembling document's preamble
```

If any unit printed it, keep the `\input{chitragupta-floats}` line in the
skeleton; if none did, drop it. Never edit the copied file, and
never give one figure `[H]` to get it out of a float page: the file's own
header says why each number is what it is, and a forced figure leaves a
ragged page bottom instead. A book that wants other fractions sets them
in its `preamble.tex`, which loads after.

**Unicode characters: the book is LuaLaTeX, with the render's fonts**
(#1037). A unit's text reaches LaTeX as its author wrote it (`H₂O`,
`𝑡`, `≤`, `Ⅳ`), and the book prints it from the same font chain as a
unit's own pdf (#996), so a chapter looks the same in both. Every unit
rendered with `--fragment` that contains such a character prints one
line and gets the font header copied beside it, into the book's
directory under `content/rendered/`:

```text
[unicode] chitragupta-lualatex.tex and chitragupta-unicode.sty copied beside the fragment -- a fragment has no preamble; in the assembling document, under lualatex: \usepackage{fontspec}\usepackage{unicode-math}\input{chitragupta-lualatex}; under pdflatex: \usepackage{chitragupta-unicode}
```

If any unit printed it, keep the `\input{chitragupta-lualatex}` line in
the skeleton; if none did, drop it, and the book sets in
LuaLaTeX's default Latin Modern. `amsmath` comes before `unicode-math`
because `unicode-math` must load after it. Never rewrite a unit's
characters to get the book through. A character no font in the chain
has stops the build and names itself. Ask the author which fix they
want: a font that has it, or the character written as LaTeX in the
unit, through the revising skill the step that sent you here names.

**Build the book with LuaLaTeX** (#1037): `lualatex`, `bibtexu`, then
`lualatex` twice, from the book's own directory, as SKILL.md's step 9
gives them; with `{#index}`, then `registry index` and a fifth pass.
Measured on the reference book (287 pages): the four passes take about
86 s against pdflatex's 26 s, and two things pdflatex got wrong come out
right. Classic `bibtex` abbreviates a first name by its first *byte*, so
`Ö. Babur` and `É. Poirier` lost their initials under pdflatex and are an
invalid-UTF-8 error under LuaLaTeX; `bibtexu` abbreviates by character.
Checking `book.log` for a dropped citation became load-bearing when the
bibliography moved to the end of the book: before that, citeproc had
already resolved every citation and there was nothing for the warning
to report. The skeleton is written for that engine and no
other: `fontspec` and `unicode-math` exist only under LuaLaTeX (and
XeLaTeX), and the font header is LuaLaTeX's.

`chitragupta-unicode.sty` and `\DeclareUnicodeCharacter` are pdflatex
tools, and a LuaLaTeX book uses neither. `\DeclareUnicodeCharacter` is
undefined under LuaLaTeX, so a line of it left in a book's
`preamble.tex` stops the build with "Undefined control sequence" and
then "Missing `\begin{document}`". The character prints from the fonts
without it: tell the author to delete the line, never guard it.

**No `citeproc-defs.def`, and no `CSLReferences` block.** A fragment
used to carry citeproc's own bibliography environment, which
`--standalone` defines and a fragment's absent preamble does not -- so
the book had to supply the macros itself, in their own file because the
block contains `\cite{#1}` and `\@`-internals that the citation gate
reads as citekeys. Deferred citations emit no `CSLReferences` at all, so
there is nothing left to define and no file to write. If you are looking
at an older `book.tex` that `\input`s `citeproc-defs.def`, drop both the
line and the file when you re-assemble.

**Margins.** `margin=80pt` -- about 28mm, and this project's setting for
an assembled book. Arrived at by measurement rather than taste: the
`book` class at a4/11pt leaves 94pt inner and 143pt outer (measured with
`\the\oddsidemargin`), a 119pt mean, which is generous enough that a
15-chapter book ran to 546 pages. A third of that was tried first and
read too tight for a book meant to be printed -- 80pt is that doubled,
and is the number to keep unless someone measures a better one. It
leaves a text block of 437.5pt by 685pt, narrower than a survey's 453pt,
and `figure check` measures every figure under the book's drafts
directory against it. `chitragupta/page.py` records that page, and a test
fails if these two skeleton lines and that record part, so change both
together.

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

**Glossary and List of Symbols: generated, never written.** Step 3's
`registry build --glossary --notation` writes `glossary.tex` and
`notation.tex` beside `book.tex` from the accepted units' `scope.md`
glossaries and `math.md` `## Symbols` tables (a symbol's meaning
lives in `math.md` since #1143, never in the glossary); each carries
its own `\chapter*` and `\addcontentsline`, so
`book.tex` holds one `\input` each, where the outline's `{#glossary}`
and `{#symbols}` entries put them (below). A page step 3 did not write
(no terms, or no symbols) gets no `\input`. The layout, for checking the PDF:

- a term with several definitions prints each, numbered, in outline
  order; identical definitions print once;
- every definition ends with `\Cref{<unit-id>}`, which resolves to
  "Chapter 3" only because step 4 puts `\label{<unit-id>}` right after
  each `\chapter`; an appendix unit reads "Appendix A", through the
  skeleton's `\crefalias`;
- a term's symbols are the `## Symbols` rows linking to it, in its
  heading, or before each numbered definition when the units use
  different ones;
- the List of Symbols is one `longtable` for the book, a row per symbol
  and meaning, listing every unit with a `## Symbols` row for it.

The build refuses, writing neither page, on a glossary bullet it cannot
print (a leftover symbol slot included), a link or `see` pointer that
does not resolve, and a `## Symbols` row with no mapping row or that is
empty, half bold or repeated; `registry check` lists each.

What neither page can catch is a qualifier inside a term or a definition
that only says "as before"; both print as written, which is why the
second sign-off reads them.

**The index** (#1168, docs/book/book-index.md). Only when the outline
has `### Index {#index}`; without it, none of this is written and the
build is the four passes above.

- **Preamble:** `\usepackage{imakeidx}` and
  `\makeindex[noautomatic,intoc]`, both *before* `hyperref`, as the
  skeleton places them. `noautomatic` because the pipeline's TeX runs
  have no shell escape, so `imakeidx` cannot start the indexer itself;
  `intoc` lists the index in the contents.
- **Where:** `\printindex` after `\bibliography{...}`, under
  `\backmatter`: the index is the book's last page.
- **Which units carry entries:** every chapter and appendix, rendered in
  step 4 with `--index-terms`. Front and back matter (a preface, "About
  the author") are not indexed and are rendered without it; `registry
  index` reads a sidecar for each numbered unit and refuses if one is
  missing.
- **Order:** `registry index` reads `book.idx` after the third
  `lualatex` pass, once citations, cross-references and the contents
  have settled the page breaks, and writes `book.ind` for the fifth.
  The index adds pages only after the bibliography, so it moves no page
  number it lists.
- **What it writes:** `book-index.idx` (each id turned into its printed
  entry), `book.ist` (the `upmendex` style) and `book.ind`, beside
  `book.tex`; and the report, `content/specs/<book>/registries/index.md`
  and `index.json`. A stale build (a chapter rendered against an older
  term table) refuses and writes nothing: re-run steps 3 and 4.
- **Fixing an entry** is never this skill's job: every finding in the
  report names the `index.toml` line that fixes it, and `index.toml` is
  the author's.

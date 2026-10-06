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
\setlength{\LTcapwidth}{\textwidth}          % see "Table captions" below
\usepackage{graphicx}
\usepackage{tikz}
\usetikzlibrary{positioning,fit}             % see "TikZ libraries" below
\usepackage{chitragupta-unicode}             % see "Unicode characters" below
\usepackage[hidelinks]{hyperref}
\usepackage{cleveref}
\usepackage{fvextra}                         % see "Wide code lines" below
\DefineVerbatimEnvironment{verbatim}{Verbatim}{breaklines}
\usepackage[numbers,sort&compress]{natbib}   % see "The bibliography" below
\setcounter{secnumdepth}{2}                  % see "Numbering" below
\setcounter{tocdepth}{1}                     % chapters and sections only
\providecommand{\tightlist}{%
  \setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\title{<the outline's own title>}
\author{<ask the user; never invent one>}
\date{}
\input{preamble}                             % only if the book has one

\begin{document}
\frontmatter
\maketitle
\tableofcontents

\mainmatter
% \part / \input, in outline order

\backmatter
\bibliographystyle{IEEEtran}
\addcontentsline{toc}{chapter}{Bibliography}
\bibliography{bibliography}                  % the .bib render wrote here
\end{document}
```

**The two `\setcounter` lines, and which is which.** `secnumdepth{2}` is
the `book` class's own default, restated here so the book *states* its
numbering rather than inheriting it silently -- an outline's section
titles carry no numbers of their own, so LaTeX supplies them and nothing
is numbered twice. `tocdepth{1}` is the real setting: the class defaults
to 2, which lists every subsection, and a book's table of contents stops
at the section. Subsections are still numbered and still `\cref`-able;
they are simply not listed.

**An authored preamble, if the book has one.** If
`content/specs/<book>/preamble.tex` exists, copy it beside `book.tex` and
`\input` it as the **last line of the preamble**, immediately before
`\begin{document}`, so it overrides every default set above it. It has to
land there rather than later in the document: a `\setcounter` after
`\begin{document}` is read too late to change how the body was set. If it does not
exist, emit no `\input` at all and say nothing -- its absence is the
ordinary case, not a finding. That file is where a book that does number
its own headings puts `\setcounter{secnumdepth}{-2}`, and where anything
else this skeleton gets wrong for one book gets corrected without
editing the skeleton for every book.

Note the two senses of "preamble" this file uses: the **generated**
preamble is the block above, written inline into `book.tex`; the
**authored** preamble is `preamble.tex`, a file the user owns.

**The bibliography is one list at the end of the book, built by one
`bibtex` pass.** A unit converted `--fragment` emits `\citep{...}` and no
reference list of its own; `bibtex` numbers every citation in the
assembled document at once, against `IEEEtran.bst` for IEEE numeric
markers. `scripts/install_full_pipeline.sh` installs `bibtex` and
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
line above it loads `longtable` unconditionally, so the register always
exists by this point.

**TikZ libraries: the book must load them, and no figure file may.**
Same structural reason as `fvextra` and `\LTcapwidth` above --
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
71.26pt, then 128.17pt, then 185.07pt, with `pdflatex` exiting 0 and
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
single `\usetikzlibrary` line in the skeleton above. Never write
`\usetikzlibrary{}` -- an empty comma list fails fatally rather than
skipping a name -- so a book whose units draw no figure omits both that
line and the `\usepackage{tikz}` above it.

A unit's figure file still carries its own plain `\usetikzlibrary` line,
and that is correct: with the book's preamble load already done it is a
no-op that appends nothing, and it is what lets the same figure compile
in a thesis chapter's fragment and in `review figure`'s probe.
What a figure file must **never** contain is a hand-rolled load -- no
clearing of `\tikz@library@...@loaded`, no saving or restoring of
`\tikz@node@reset@hook`. `python -m chitragupta.review figure` reports
one as `loads-library-by-hand`.

**Unicode characters: the book loads `chitragupta-unicode` once.** A
unit's text reaches LaTeX as its author wrote it (`H₂O`, `𝑡`, `≤`, `Ⅳ`),
and pdflatex's default fonts cannot print those (#948). The shipped
`chitragupta-unicode.sty` tells it how. Every unit rendered with
`--fragment` that contains such a character prints one line and gets
the file copied beside it, into the book's directory under
`content/rendered/`:

```text
[unicode] chitragupta-unicode.sty copied beside the fragment -- a fragment has no preamble; load it in the assembling document: \usepackage{chitragupta-unicode}
```

If any unit printed it, keep the `\usepackage{chitragupta-unicode}` line
in the skeleton above; if none did, drop it. Under XeLaTeX or LuaLaTeX
the package does nothing, so it is safe to keep either way. A book
compiled with `lualatex` instead of `pdflatex` prints these characters
from its fonts without the package, and Telugu or Chinese names in the
bibliography too; chitragupta's own pdf renders use LuaLaTeX for that
reason (#996). The engine is the author's choice: mention it, never
switch it for them. Never
rewrite a unit's characters to get the book through. A character the
package does not map still stops the build and names itself. Ask the
author which fix they want: a `\DeclareUnicodeCharacter` line in the
book's own `preamble.tex`, or the character written as LaTeX in the
unit, through the revising skill the step that sent you here names.

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

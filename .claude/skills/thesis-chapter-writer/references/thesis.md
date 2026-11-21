# Thesis chapter: what a LaTeX fragment alone needs

Read a section of this file when the step that sent you here cites it;
each section opens with when it applies. Paths here are from the project
root.

## 1. Tables, figure floats and equations, written as real LaTeX

Read this before you write a table, a figure float or a numbered
equation into the fragment.

**The fragment carries no marker vocabulary.** It is `\input` into the
person's own thesis, where their own LaTeX numbers every table, figure
and equation consistently with their other chapters. A Markdown marker
would be dropped by their build, leaving an unnumbered object in a
chapter whose prose refers to a number. So a table is a real
`table` float with its own `\caption` and `\label`
(`docs/writing-standards/tables.md` §13, "The `.tex` fragment writes its
own"), and every figure is a real `figure` float, with its own
`\caption` and `\label`, around the inline `\input`
(`docs/writing-standards/figures.md` §10). Neither carries a
number written by hand: a hand-typed number, or a `\renewcommand` of a
counter, is wrong the moment a chapter before this one changes length.

**An equation gets the same carve-out, without a pair of files.** Most
displayed mathematics in a chapter needs no number at all:
`docs/writing-standards/mathematics.md` §12's rule (standalone, the
final step of a derivation, or reused later) applies here exactly as
everywhere else. Write ordinary mathematics with `\[...\]` or `\(...\)`,
as in any other LaTeX document. When one does earn a number, it is a
real `equation` environment with a `\label`, for the same reason as a
table: a bare `\[...\]` for a result the prose later calls "Equation 3"
breaks as soon as an earlier chapter changes. Introduce the result
before the display and read it in the sentence that follows; a number
is not a reading.

## 2. Provenance and the section map

Read this before you write `provenance.json` or map sections to
citekeys.

**Two shapes, for two readers, in one directory.** `provenance.json` is
the machine-readable section-to-citekey record, kept for audit; the
dossier's Markdown is the working state a later revision reads (reader,
scope, glossary, rejected candidates and why, steering). Both sit in
the dossier directory because both are state this run produced. A
report generated from the finished draft is a different thing: it goes
to the review layer's `content/review/`, which no drafting run writes.

**The section map is the same mapping, derived.** The sections command
reads `\citep`/`\citet` as readily as `[@key]`, and tracks the
`verbatim`, `lstlisting` and `minted` environments, so a
`\section`-like line inside a code environment is neither a heading nor
a citation. A citekey cited above the first `\section` belongs to no
section and is reported on stderr: fix the fragment, not the map.

## 3. What a render prints about the thesis preamble

Read this when a render prints a line beginning `[tikz-libraries]`,
`[unicode]` or `[floats]`, to recognise it. What to tell the person
about each is in the figure reference the step names.

A fragment has no preamble, so a render that produces one names what
the assembling document must load instead, one line each. The
libraries the fragment's figures ask for:

```text
[tikz-libraries] fit,positioning -- a fragment has no preamble; load these in the assembling document
```

The fonts for any Unicode character the fragment carries (`H₂O`, `𝑡`,
`≤`, `Ⅳ`), which pdflatex's default fonts cannot print:

```text
[unicode] chitragupta-lualatex.tex and chitragupta-unicode.sty copied beside the fragment -- a fragment has no preamble; in the assembling document, under lualatex: \usepackage{fontspec}\usepackage{unicode-math}\input{chitragupta-lualatex}; under pdflatex: \usepackage{chitragupta-unicode}
```

The library names, and the character in a `[unicode]` line that names
one, vary with the fragment; the rest of each line is fixed. Quote the
line as printed. Never rewrite the fragment's characters to get a build
through: the fix belongs in the preamble.

## 4. The previews, the evidence sidecar, and no References section

Read this if the person asks why the chapter has no References section,
why the sidecar is rendered, or why the preview's citations look
different from their thesis's.

**The fragment is the deliverable; the previews are not.** The md and
pdf previews are rendered from the fragment as it stands, and pandoc's
LaTeX reader handles a fragment with no preamble. Neither is ever
`\input`, and nothing downstream reads them back.

**No References section, by design.** The fragment inherits the
thesis's own document-wide `\addbibresource` (biblatex) or
`\bibliography` (bibtex), which should point at `papers/bibliography.bib`
directly rather than at a copy. A per-chapter list would duplicate it.
The References builder takes Markdown and finds its section by a
Markdown heading, which a fragment never has, so it could not run here
anyway. The pdf preview still gets a real bibliography: citeproc
resolves `\citep`/`\citet` against the same `.bib` and appends one.

**The preview is in IEEE style, with numeric `[1]` markers**, because
that is the style the render passes. That styles the preview only. The
real thesis renders the same citations in whatever style its own
document class and `\bibliographystyle` set, so never rewrite
`\citep`/`\citet` to match the preview.

**A thesis chapter emits the evidence sidecar, and it is safe to.** The
sidecar is a separate, standalone document with its own preamble, never
something the thesis `\input`s, so none of the objections to a
References section apply: nothing lands mid-chapter, nothing competes
with the thesis-wide bibliography, and the fragment handed over is
byte for byte what it was. It is also the genre that most wants one:
the examiner reads adversarially for the claim that outruns its
evidence, and the sidecar lets them check a claim against what the
source said. It carries no bibliography of its own, since every citekey
in it sits in a code span, and `\citep`/`\citet` are read as `[@key]`
is, so its contents come from this fragment's own citations.

## 5. Where this genre's rules come from

Read this when asked where a thesis chapter's writing rules come from,
or when deciding whether a Diátaxis rule applies to one.

The prose standards a thesis chapter inherits are not original to this
project. Full citations, licences and a per-principle attribution table
are in `docs/INSPIRATION.md`, "The writing standards' sources". All
three works are openly licensed (CC-BY or CC-BY-SA) and require credit.
What bears on a thesis chapter specifically:

- **Google, *Technical Writing Courses* (CC-BY 4.0)**: the curse of
  knowledge, consistent terminology, and defining each term once.
  Settling what an examiner already knows before searching is audience
  analysis in the form this genre needs.
- **Last, *Technical Writing Essentials* (CC-BY 4.0)**: scope and
  assumed background stated up front, and the argument against passive
  voice.
- **Procida, *Diátaxis* (CC-BY-SA 4.0)**: the genre-separation principle
  behind the warning that a chapter which only summarises papers in
  sequence is a survey with a chapter heading. A thesis chapter is not a
  Diátaxis quadrant; only that insight transfers.

# 📐 Figures

Status: **reference.** An element file of the
[writing standards](../WRITING-STANDARDS.md), listed in the core's index.

Assumes the core, §1–9 of [WRITING-STANDARDS.md](../WRITING-STANDARDS.md).
This file holds §10, under the number it had in the core, so a
citation reads `docs/writing-standards/figures.md` §10.
`chitragupta/style_figures.py` reports its decidable part as
`draft style` findings.

## 📐 10. Figures

A draft may include a figure only if it is wholly original. A figure
extracted from a source paper carries that paper's own copyright, and
citing the paper grants no right to reproduce it. Inserting one into a
draft, or closely redrawing one from memory, is the same violation.
Reading a source figure for understanding is fine; the boundary is
what ends up in the draft.

A figure's ASCII form is a diagram in a code block: box characters,
arrows and labels built from `+ - | / \ > < ^ v`, 7-bit characters only.
Keep it to about 70 columns so it survives the rendered PDF's monospace
block without wrapping.

A code block, not specifically a fenced one. In a Markdown draft you
write a fence and the `md` render keeps it. Where the renderer inlines
the ASCII form into a `.tex`-sourced `.md` preview, pandoc emits a
4-space indented block instead. That is verified, and it is the shape to
expect rather than a defect: every line is shifted by the same four
spaces, so the diagram's alignment is intact and `^ \ < >` come through
literally.

Unicode box-drawing (`┌─┐│└─┘`) is excluded.
chitragupta's own pdf render runs LuaLaTeX and prints them, but a
`.tex` output or a `--fragment` is compiled later by the author's own
document, and a `pdflatex` build has no such glyphs set up: it fails the
whole build with `Unicode character ┌ (U+250C) not set up for use with
LaTeX`. That is verified against a `pdflatex` build of this project's
own render output, and is not a general pandoc claim. One such diagram
breaks the build for every other figure in the same draft.

### 🎨 TikZ layout and style

[TIKZ-STYLE.md](../TIKZ-STYLE.md) is the full guide to drawing a good TikZ
figure: which layout metaphor to commit to before placing a node, the
pre-flight defect checklist to check the result against, and the type
and line-weight conventions that keep a figure consistent with the
surrounding document. Much of it is checked by `chitragupta figure
check`, which reports and is never gated; the rules it applies, and how
to read its report, are in
[figure-checks/README.md](../figure-checks/README.md).

### 🖼 Every figure has two forms

ASCII is what a Markdown reader should see; it is not what a thesis
wants. So a figure in this pipeline exists twice: once as a TikZ
picture, which sets as vector art at the consuming document's own font
and line width, and once as the plain-ASCII diagram above.

The `figure-drawer` skill draws both forms, for any genre that hands it
a figure and for a direct request ([FIGURE-DRAWER.md](../FIGURE-DRAWER.md)).
This section is the contract it follows, and stays the contract for a
figure drawn by hand.

**Both forms are always sibling files, in every genre, and a draft
carries only a marker naming them**, with one exception, which is not
about figures. `thesis-chapter-writer`'s `.tex` fragment is what the user
`\input`s directly into their own real thesis, never touched by this
pipeline again once it leaves `content/drafts/`; a marker-only TikZ would
render fine through this pipeline's own renderer and then vanish without
warning when the user `\input`s the fragment into their thesis. So that
genre's TikZ stays inline, via the `\input` a real thesis resolves for
itself; its ASCII, like every other form in every other genre, is a file
named by a marker.

```text
content/drafts/<topic>/<draft>.md          marker only
content/drafts/<topic>/figures/<name>.tex  the TikZ picture   (every genre)
content/drafts/<topic>/figures/<name>.txt  the ASCII form     (every genre)

content/drafts/<topic>/<draft>.tex         TikZ inline, via \input   (thesis-chapter-writer only)
content/drafts/<topic>/figures/<name>.tex  the TikZ picture
content/drafts/<topic>/figures/<name>.txt  the ASCII form
```

**A topic directory is mandatory for a draft that carries a figure.** A
flat `content/drafts/<slug>.md` puts its figures in
`content/drafts/figures/`, shared with every other flat draft, where two
drafts that each name a figure `fig1` silently overwrite each other in
`content/rendered/`. Each genre skill settles the draft's path at the
start of its process, before a figure is on anyone's mind; deciding on a
figure later is a reason to move the draft and its dossier, not a reason
to `mkdir` beside a flat one.

Every draft names both forms with a marker comment. `thesis-chapter-writer`
additionally keeps its TikZ inline, for the reason above, but still marks
its ASCII the same way everyone else marks both. The marker is what lets
a reader of the draft see that a form exists off the page, and what lets
a reviser find every figure by `grep` rather than by parsing the draft.

**One marker, one vocabulary, in both genres: `figure:`, naming the
figure's base name without a suffix.** The renderer derives `<base>.tex`
and `<base>.txt` from it. The two spellings below differ only because a
comment in Markdown and a comment in LaTeX are written differently; what
you write is the same either way, and no draft names one figure twice.

**Markdown drafts** (`tutorial-writer`, `textbook-chapter-writer`,
`survey-writer`) carry the marker alone, with no fence beside it:

```html
<!-- figure: figures/<name> -->
```

For `--format tex` and `--format pdf` the renderer replaces that marker
with `\input{figures/<name>.tex}`. For every other format, including the
Markdown draft's own `--format md`, it replaces the marker with the
`.txt` contents in a fence. There is no inline diagram left to fall
back on, so this substitution runs even when the output format matches
the draft's own language.

**The `.tex` draft** (`thesis-chapter-writer`, this pipeline's one
LaTeX-sourced genre) keeps its TikZ inline, via the `\input` a real
thesis resolves for itself, with the ASCII marker following it:

```latex
\input{figures/<name>.tex}
%figure: figures/<name>
```

For `--format md` the renderer substitutes the `.txt` contents for that
`\input`, in a temp copy. The author does not write a `verbatim` block
by hand: the fragment on disk stays exactly what the user
`\input`s into their own thesis, and the ASCII appears only in the
preview that needs it.

**The marker must be a comment, never a second `\input`.** A literal
`\input{figures/<name>.txt}` makes pdflatex read the ASCII art *as LaTeX
source*, and the alphabet above is full of math-mode-only characters:

```text
! Missing $ inserted.        exit=1
```

That failure lands in the user's own thesis build, where we never see
it, because our own render substitutes the line away first. A LaTeX comment is
inert to pdflatex, dropped by pandoc, and meaningful only to this
pipeline.

### 🎯 What the pair requires

- **Both forms, or no figure.** A figure is not finished until both
  sibling files exist and the marker is in the draft. A pair with a
  missing half renders in one format and disappears in the other, and a
  draft that refers in prose to a figure the reader cannot see is worse
  than one with no figure at all.
- **The TikZ form is in colour; the ASCII form is not, and that is
  accepted.** Figures here use a house palette
  ([TIKZ-STYLE.md](../TIKZ-STYLE.md)), and the 7-bit twin cannot reproduce
  it; `md`, `docx` and `html` render only the twin. The pair contract
  therefore covers what the figure shows, not how it looks: **both forms
  must work as figures, and they need not carry the same secondary
  distinctions.**
  Keep the argument legible through position, arrow direction and
  labels, which the twin can express, and let colour make the picture
  quick to read rather than possible to read.
- **Originality binds the TikZ identically.** A TikZ picture redrawn
  from a source paper's figure is the same violation, and that a vector
  redraw is easier to produce than a traced
  bitmap changes nothing about whose figure it is. Reading a source
  figure for understanding is fine; the boundary is the same one as
  above.
- **No figure number inside a figure file either, and for the same
  reason.** The renderer assigns every number
  ([below](#-a-caption-and-no-number-you-write-yourself)), so a literal
  "Figure 3" written into a node label or a `\node` caption inside
  `figures/<name>.tex` is a second, unmanaged number that nothing
  renumbers and nothing checks; it survives into the PDF beside the
  real one. In general, **the figure file carries the picture and the
  draft carries its number and caption.**
- **No citekeys inside a figure file.** `python -m chitragupta.draft gate` reads
  the draft and does not follow `\input`, so a citekey in a node label
  or a caption inside `figures/<name>.tex` is invisible to the one check
  standing between this pipeline and a fabricated reference. Cite in the
  draft's prose, where the gate can see it. This is stated and not
  gated, deliberately: `docs/CODE-STANDARDS.md` keeps `chitragupta.draft gate`
  as the project's only gate, meaning exactly one thing (a fabricated
  citekey fails), and giving it a second meaning would blunt the first.
- **Verify the TikZ compiles before keeping it.** A figure that does not compile
  fails the *whole* pdf render, not just the figure. Probe `kpsewhich tikz.sty`
  first; if it is absent, write only the ASCII form and no marker, and say so in
  chat. Do this at drafting time: a marker written on a host without `tikz.sty`
  makes every later `tex`/`pdf` render of that draft fail with
  `[missing-binary]`, because the renderer refuses rather than silently falling
  back: the same draft has to produce the same output on every host. If it is
  present, run `chitragupta figure check figures/<name>.tex`. It compiles the
  figure under LuaLaTeX, the pdf render's engine, with the figure's own
  `\usetikzlibrary` libraries loaded in the preamble as the renderer loads
  them, and reports `does-not-compile` along with every other rule it
  measures. Never keep a figure that fails. `chitragupta figure look
  figures/<name>.tex` writes the figure cropped as it will print, for what no
  rule measures. [TIKZ-STYLE.md](../TIKZ-STYLE.md) says where the
  `\usetikzlibrary` line goes in the figure file.
- **Plain 7-bit ASCII in the ASCII form**, wherever it lives, same
  alphabet and same reasoning as the Unicode exclusion above. It is
  what every non-LaTeX render emits, and a draft with no TikZ figure at
  all still renders its fence straight into the pdf, where one Unicode
  box character fails the whole document.
- **Panels are lettered, in both forms, however many there are.** A
  figure showing the same thing under several conditions is one figure
  with panels (one marker, one pair, whatever the count), and each
  panel carries a sub-caption reading `(<letter>) <short title>`, where
  the letter is the panel's place in reading order: `(a)` for the first,
  `(b)` for the second, on through the alphabet. The letters have to be
  in the ASCII form too: every format except `tex`/`pdf` renders the `.txt`
  and never sees the picture, so a figure lettered only in its TikZ
  ships a `docx` and an `html` whose panels are unlabelled. `figure
  check` reports that as `t3-panels`. [TIKZ-STYLE.md](../TIKZ-STYLE.md) has
  the worked example, how to letter an ASCII diagram without sliding
  every title off its panel, and why `subcaption` is not the answer.
- **A figure is captioned in the draft, not in the figure file**;
  "A caption, and no number you write yourself" below has the contract.
  A marker with no caption below it renders unnumbered and uncaptioned,
  and `draft style` reports it (`chitragupta.FigureNoCaption`).
  Which lettering a venue wants for panels (`(a)`,
  `(i)`, `A`, or titles with no letters) is a §8 house-style decision:
  record it in the dossier's `scope.md` beside the dialect, where
  `draft-reviser` reads it before every edit, rather than settling it
  again per figure.

### 🔖 A caption, and no number you write yourself

A figure has the number-and-reference contract §13 gives a table. A
Markdown draft writes the `figure:` marker, then its caption
directly below it with no blank line between, the same adjacency §11's
`<!-- single-source: -->` and §13's own caption-then-marker pair both
use:

```markdown
<!-- figure: figures/delivery-modes -->
One reading path under three delivery modes.
```

Prose points at it with an inline marker, which stands in for the whole
reference phrase; the author writes neither the word "Figure" nor a
number:

```markdown
<!-- figureref: delivery-modes --> shows the same request handled three ways.
```

**The id is derived, not written.** The marker's own value already names
the figure's base name, so the id is that name with no `figures/` prefix:
`delivery-modes` from `figures/delivery-modes`, the same base name
`\label{fig:delivery-modes}` agrees with. There is no second field to
keep in sync with the file name.

**A figure with no caption line below it renders unchanged**: a bare
`\input` or a bare ASCII fence, no float, no number, and invisible to
`figureref` resolution. The renderer accepts it and the standard does
not: `draft style` reports it as `chitragupta.FigureNoCaption`.

**Never write the number.** [RENDERING-FLOW.md](../RENDERING-FLOW.md)'s
"Figure numbering" has the per-format cases: LaTeX-bound output wraps
the marker in a real `figure` float and lets LaTeX's own counter number
it (no `\renewcommand{\thefigure}` is ever written), and every other
format gets a number counted at render time, mirroring how §13
numbers a table outside LaTeX.

The `.tex` fragment carries neither marker: `thesis-chapter-writer`
hand-authors a real `\begin{figure}...\caption{}...\label{fig:<id>}`
around its inline `\input`, the same carve-out §13 gives a hand-written
`\begin{table}`. There too, never write
`\renewcommand{\thefigure}{N.M}`: the consuming thesis's own counter has
to agree with its own chapter numbering, which is why a number never
belongs in a draft.

`python -m chitragupta.draft style` reports the decidable part of this:
a figure marker carrying no caption, a captioned figure no sentence
refers to, a `figureref` naming a figure that does not exist or is not
captioned, two figures sharing one id, and a reference sitting outside
the figure's own section.

There is no `FigureNoId`: a figure marker always carries an id by
construction, since the id *is* the base name the marker names, so
there is no state for it to catch.

Where `tikz.sty` is absent, the fallback is the same in every genre and
is the ASCII form alone: the ASCII goes
inline, in whatever form the draft's own language carries natively (a
fenced code block in a Markdown draft, a `verbatim` environment in a
`.tex` fragment), with no marker and no `figures/` files at all. Both
forms survive every format such a host can produce: a fence renders
straight through Markdown's own formats and, via pandoc, into `tex`/`pdf`
too; a `verbatim` block survives pandoc's LaTeX reader into both
`--format pdf` and `--format md`. Both were verified into both formats
through this pipeline's own render path.

There is no equivalent of `citation_gate` for a figure's originality.
Whether a diagram is original, and whether a source figure's own
licence would even permit reproducing it, stays a judgement call.

Agreement between the two forms is checked in part by `chitragupta
figure check`, which reports and is never gated. It reports a figure
with no `.txt` beside it (`twin-missing`), a name in the TikZ that the
twin does not carry (`t1-labels`), an edge tag missing from the twin
(`t2-tags`), and panel letters that differ between the two
(`t3-panels`). Arrow topology is not checked: nothing compares which
box an arrow joins in one form against the other, so a rewired arrow
leaves the pdf and the Markdown preview disagreeing until someone looks.
[figure-checks/README.md](../figure-checks/README.md) has the rules.
`draft-reviser` carries the rest of the defence: touch a figure, touch
both forms, panel letters included.

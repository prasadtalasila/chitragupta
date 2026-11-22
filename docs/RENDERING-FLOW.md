# 🖨 Rendering flow

Status: **reference.**

How `python -m chitragupta.draft render` turns a draft into
`.md`/`.tex`/`.pdf`/`.docx`, where a rendered draft's bibliography comes
from, and what happens to a figure on the way through.

**Written for** someone changing `chitragupta/render_output/`, or tracing
which store on disk a rendered file's bibliography or figure came from.
**Assumed** you have read [ARCHITECTURE.md's drafting
layer](ARCHITECTURE.md#-layer-2-the-drafting-layer). **Not covered here:**
every render flag ([CLI.md](CLI.md)), the TikZ style rules
([TIKZ-STYLE.md](TIKZ-STYLE.md)), and book assembly's single `bibtex`
pass ([WRITE-A-BOOK.md](WRITE-A-BOOK.md)).

## 🔀 The two paths through `render()`

`render()` (`chitragupta/render_output/__init__.py`) takes one of two
routes, decided by `output_format` and the draft's own suffix:

- **`--format md` on a Markdown draft never reaches pandoc.** It is a
  citation-numbering job: `references.write_numbered` renumbers `[@key]`
  markers and appends an IEEE list in place, because pandoc's Markdown
  writer would escape every marker to `\[1\]` and wrap the bibliography
  in `::: {#refs}` fenced divs that read as literal punctuation outside
  pandoc. This path also drops the draft's raw LaTeX itself
  (`_raw_tex.py`): each ```` ```{=latex} ```` or `{=tex}` block and each
  `` `...`{=latex} `` span, as pandoc's `docx` and `html` writers do,
  leaving no stray blank line. A raw block shown inside a longer code
  fence is an example and stays, and `{=html}` is kept.
- **Every other combination goes through pandoc**, against
  `config.BIB_FILE_PATH`, and (for `pdf`) LuaLaTeX. The rest of this page
  covers this path, including a `.tex` fragment rendered to `.md`, which
  is a real format conversion.

Output lands mirrored under `content/rendered/`: a draft at
`content/drafts/<topic>/<name>.tex` renders to
`content/rendered/<topic>/<name>.{md,pdf,...}`.

## 📚 Citation resolution: resolve now, or defer to the consuming document

Every genre-skill draft cites with `[@citekey]` markers (or, for
`thesis-chapter-writer`'s `.tex` fragment, `\citep{}`/`\citet{}`).
`_pandoc_command` picks one of two strategies:

| Render | Flags | Who numbers the citations |
| --- | --- | --- |
| Ordinary (the default) | `--citeproc --bibliography <bib> --csl <ieee.csl>` | pandoc, here and now, into the output |
| `--fragment` | `--natbib --bibliography <bib>` | the document that `\input`s it, via one `bibtex` pass |

**Why a fragment must defer.** Citeproc numbers as it builds the list,
so a fragment resolving its own citations would restart at `[1]` in
every chapter, and a book would have half its markers pointing at the
wrong entry while compiling cleanly. A thesis fragment wants the same.

A redline (`draft diff --format pdf`) defers too: resolved citations are
text, so one new citation would renumber every later one and latexdiff
would mark each as a change. Both sides render to `.tex` with
`defer_citations=True`, latexdiff compares them, and the result compiles
with LuaLaTeX, `bibtexu` (only when the first pass found a citation),
then LuaLaTeX twice more. A LuaLaTeX failure is retried once with
`--math-markup=whole` (`chitragupta/draft_diff/_redline.py`).

The deferred path writes `config.BIB_FILE_PATH` beside the output as well
(`_assets._copy_book_bibliography`), because `bibtex` resolves
`\bibliography{...}` against the directory it runs in.

Two fixups run first, on temp copies only (`_safe_render_inputs`,
`chitragupta/render_output/_citeproc.py`). A citekey containing `--` is
aliased, because pandoc's tokenizer otherwise truncates it and silently
drops the citation (under `--natbib` it emits
`\citep[art_2019]{tygesen_state}`, a truncated key plus a spurious
optional argument). Control characters are stripped and decomposed
accents joined (NFC), since `content/parsed/` text can carry them and
LaTeX cannot. Neither the draft nor `papers/bibliography.bib` is ever
written to; the `.bib` beside a fragment aliases every `--`-bearing key,
not just one draft's, so the result does not depend on which unit
rendered last. Every other character reaches pandoc as written.

## 🔤 The pdf engine and its fonts

A `pdf` render runs **LuaLaTeX**, the only engine for this project's own
pdfs. It reads UTF-8 and OpenType fonts natively. The fonts are in
`chitragupta/pdf_fonts.py`: STIX Two Text and Math, Latin Modern Mono for
code, and a `luaotfload` fallback chain (STIX Two Math, Noto Serif,
DejaVu Sans, Noto Sans Symbols 2, Noto Serif Telugu, Devanagari and CJK
SC, Unifont and Unifont Upper; the code font's chain puts DejaVu Sans
Mono first). The chain is set in the shipped header
`assets/latex/chitragupta-lualatex.tex` rather than pandoc's
`mainfontfallback` variable, which older pandoc templates (Ubuntu 24.04's
pandoc 3.1.3) silently drop. It prints every one of the 1,873 characters
`chitragupta-unicode.sty` prints under pdflatex
(`tests/test_render_output_fonts.py`), plus Telugu, Devanagari and
Chinese.

A character no font in the chain has stops the build, by name: the
header sets `\tracinglostchars=3` and a `glyph_not_found` callback whose
error pandoc shows (`! Missing character: There is no X (U+XXXX) ...`),
and the CLI adds a `[unicode]` hint. Without it LuaTeX drops the glyph
with only a log warning, silently changing what the PDF says.

The exception is Unicode private-use code points (U+E000 to U+F8FF and
planes 15 and 16) in a review report or evidence sidecar, which quote
the sources' text layers: `chitragupta/_private_use.py` writes each as a
visible `[U+E230]` in the `.md` the render reads, with a `note:` line
naming them. A report's `.json` keeps the original.

`_unicode.py` copies `assets/latex/chitragupta-unicode.sty` beside a
`tex` or `--fragment` output whose draft has a character it maps,
because the document that `\input`s it may use pdflatex; a `pdf` render
does not load it. A project's `content/unicode-extra.tex` goes into
every LaTeX-bound preamble behind a shim defining
`\DeclareUnicodeCharacter` via `newunicodechar` where the kernel lacks
it, so one line works under both engines.

A `.bib` field's raw TeX prints as text: `bib_raw_tex_as_text.lua` runs
just before citeproc and turns raw TeX in every bibliography entry into
literal text, as it does for a `$...$` math node holding a code-running
primitive, because LuaLaTeX would run a `\directlua` in either. Plain
mathematics stays math. It rewrites the entries rather than citeproc's
output, because citeproc merges the author's own citation prefix and
suffix (`[\emph{cf.} @key, p. 3]`) into the same node, and those are the
author's to keep. TeX in the draft body, in a citation's prefix or
suffix, and in figure files still runs; that is an accepted residual, set
out in
[SECURITY.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/SECURITY.md).

**Build time** (TeX Live 2023, a 170-page document, warm cache):
pdflatex 5.2 s, this LuaLaTeX setup 27.3 s (38.6 s on the first run,
which builds the font cache).

## 🔢 Mathematics: substituted on the pandoc path only

`chitragupta/render_output/_math.py` runs on the same temp copy, between
the figure swap and `_safe_render_inputs`, and turns a draft's ASCII into
mathematics pandoc can read (`` `tau` `` into `$\tau$`, a
`<!-- math -->` fence into `$$…$$`), using the table in the dossier's
`math.md` ([DOSSIER.md](DOSSIER.md),
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) §12).

A render that reaches pandoc gets the substitution; `--format md` is a
byte-perfect no-op, which is why the LaTeX lives outside the draft. A
span with no row is left as it was, so `as_of` stays
`\texttt{as\_of}` by construction.

**It writes `$…$`, never `\(…\)`.** Pandoc's Markdown reader does not
read `\(…\)` as mathematics: handed `A $k = 4$ and B \(k = 4\)` it emits
`A \(k = 4\) and B (k = 4)`, silently dropping the backslashes. `$…$` is
the native inline form, which each writer renders in its own idiom.

Two conditions fail the render, because the pdf would carry verbatim
text where the author said an equation goes: a `<!-- math -->` marker
with no row, and one with no `math.md` at all (what renaming a draft
looks like, since a dossier is found by path). Heuristic gaps print
`[math]` warnings and carry on (none for a review report, which has no
`math.md`), as do the `## Symbols` findings: a symbol with no meaning, a
meaning with no row, a malformed row. `## Symbols` is cut out before the
mapping is read; glossary spans count as uses of a row, though
substitution never touches the glossary.

## 🗂 Five places a rendered bibliography can live

A render's citations involve five stores, only one of them this
pipeline's own. Confusing them is the easiest way to misread what a
rendered draft proves:

| What | Where | Who reads it |
| --- | --- | --- |
| The bibliographic data | `papers/bibliography.bib` (`config.BIB_FILE_PATH`), your Zotero/JabRef export | pandoc's `--citeproc`; for `--fragment`, an aliased copy beside the output, for `bibtex` |
| The verification record | `content/ledger.sqlite` | `draft gate`, `references.py`, retrieval; never the render |
| The rendered bibliography | generated fresh into `content/rendered/...` | a preview artefact; nothing reads it back |
| The real bibliography, for a `.tex` fragment | your thesis's `\bibliography{...}`/biblatex resource, outside this repository | your own `pdflatex`+`bibtex` run |
| The real bibliography, for an assembled book | `content/rendered/<book>/`, copied there by the fragment render | `book.tex`'s `\bibliography{...}`, one `bibtex` pass |

For every genre but the thesis chapter (row four) and book units (row
five), the rendered draft's citeproc list is the one a reader sees. A
fragment's `\citep{<citekey>}` is left for your thesis's bibliography run
to number with your other chapters. Its `.md`/`.pdf` preview
(`thesis-chapter-writer` step 12) still uses rows one and three, because
a preview must resolve citations to be readable; the deliverable is the
fragment on disk, unresolved markers and all.

## 📄 The manual References section, and why citeproc replaces it

Five of the six prose genres run `python -m chitragupta.draft references
<draft>` after the gate, writing a citekey-labelled `## References`
section. At render time `_swap_manual_refs_for_citeproc`
(`chitragupta/render_output/_citeproc.py`) replaces its entries with
pandoc's placement anchor (`::: {#refs}\n:::\n`), keeping the heading,
so citeproc's numbered list lands there instead of as a second, untitled
list at the end.

`references_section.py`'s `section_start` finds the section by any
title `REFERENCE_TITLE` names (References, Bibliography, Works cited),
numbered or not, so a hand-titled `## Bibliography` is swapped too and
`draft references` replaces it rather than adding a second list. The
uncited-prose report and the typeset check use the same pattern.

`thesis-chapter-writer` skips the `references` step by design
([ARCHITECTURE.md's drafting
layer](ARCHITECTURE.md#-layer-2-the-drafting-layer)), and could not run
it anyway: `references.py` takes a Markdown draft, and a `.tex` fragment
has no Markdown heading. `section_start` returns `None` and the swap
returns the text unchanged, so that genre needs no exemption.

## 🖼 Figure substitution: four combinations, one left to LaTeX

`_with_figures_for` (`chitragupta/render_output/_figures.py`) switches
every figure marker to the form the target format can draw, depending on
the draft's kind and whether the output is LaTeX-bound
(`tex`/`latex`/`pdf`):

| Draft carries | Output wants | What happens |
| --- | --- | --- |
| Markdown `figure:` marker + ASCII twin | LaTeX-bound | `_substitute_tikz_for_ascii`: marker becomes `{\centering\input{figures/<name>.tex}\par}`; for `pdf`, with a page mark before the `\par` (below) |
| Markdown `figure:` marker + ASCII twin | non-LaTeX | `_substitute_ascii_for_marker`: marker becomes a fenced ASCII block |
| `.tex` fragment's inline `\input` + ASCII twin | non-LaTeX (`.md` preview) | `_substitute_ascii_for_tikz`: `\input{...}` becomes a `\begin{verbatim}` block of the ASCII twin |
| `.tex` fragment's inline `\input` | LaTeX-bound (`tex`/`pdf`) | left as written: pandoc reads the draft with `latex+raw_tex`, so the `\input` reaches LuaLaTeX (see [a `.tex` draft's own preview](#-a-tex-drafts-own-preview)) |

The third row exists because pandoc's default LaTeX reader, which a
non-LaTeX render still uses, resolves the `\input` but drops the
`tikzpicture` environment, so without the swap a fragment's figure would
silently vanish from its `.md` preview.

What sits beside the table:

- **The substitution adds no `figure` float or `\caption`.** A float and
  a number come only from a caption line under the marker, which the
  [caption pass](#-figure-numbering-a-caption-wraps-the-marker-in-two-passes)
  wraps in `\begin{figure}`.
- **Only `tex`/`latex`/`pdf` draw the TikZ.** `md`, `html` and `docx`
  render the ASCII twin, so a panelled figure's `(a)`/`(b)` sub-captions
  must exist in the `.txt` as well as in the picture.
- **The TikZ libraries are loaded in the preamble, not in the figure
  file.** `_pandoc_command` takes the union of `\usetikzlibrary` names
  across the draft's figure files (`_tikz_libraries.py`) and emits it
  beside `\usepackage{tikz}`. Loading inside a `figure` float would
  define the macros locally but set the loaded flag globally, so the
  second figure would find no macros. A `--fragment` render has no
  preamble and prints the union instead, for the book that `\input`s it
  ([WRITE-A-BOOK.md](WRITE-A-BOOK.md)).
- **Float placement is set in the preamble too.** Standalone
  `tex`/`latex`/`pdf` renders include
  `assets/latex/chitragupta-floats.tex`, whose float fractions keep a
  figure that fits on a text page off a page of its own; a `--fragment`
  gets the file copied beside it and a `[floats]` line. Under LuaLaTeX
  it records each figure still on a float-only page in the pdf's Info
  dictionary (pandoc has deleted the log by then), and `_run_pandoc`
  prints a `[float-page]` line for each.
- **A `pdf` render marks each figure's page.** In a Markdown draft the
  `\input` is followed, inside the figure's paragraph, by a PDF named
  destination `cgfig:<marker base>` (`render_output/_figure_anchor.py`):
  no ink, no bookmark, no word moved. `draft render` reads the marks with
  `pdfinfo -dests` and writes each figure's `figure look` pictures and a
  PNG of its page beside the PDF, as `[figure-look]` notes that never fail
  the render. A `.tex` draft gets no mark, since pandoc's LaTeX reader
  would print it as text.

## 🔢 Figure numbering: a caption wraps the marker, in two passes

A captioned figure gets the same "author writes no number" contract §13
gives a table, via `chitragupta/render_output/_figure_captions.py`. The
Markdown contract is a `figure:` marker followed directly by its caption,
no blank line between (`_FIGURE_CAPTION_PAIR_RE`):

```markdown
<!-- figure: figures/delivery-modes -->
One reading path under three delivery modes.
```

Two passes run before `_with_figures_for`, in `_substituted`
(`chitragupta/render_output/_substitution.py`), because both read the
original `[marker, caption]` adjacency that substitution destroys:

| Pass | What it resolves | LaTeX-bound (`tex`/`latex`/`pdf`) | Everything else |
| --- | --- | --- | --- |
| `substitute_captions` | The `[marker, caption]` pair | Wraps the untouched marker in `\begin{figure}`/`\end{figure}`, each its own raw `` ```{=latex} `` block; LaTeX's counter numbers it. The caption stays pandoc text, with `` `\caption{`{=latex} `` and `` `}\label{fig:<id>}`{=latex} `` spans around it (reason below) | `<marker>\n**Figure N:** <caption>`, N counted in document order among captioned figures only |
| `substitute_refs` | An inline `<!-- figureref: <id> -->` | `` `Figure~\ref{fig:<id>}`{=latex} ``, for the same raw-attribute-span reason `_tables._reference_for` needs for `~` | `Figure N` |

**Why `\begin{figure}` and `\end{figure}` are separate raw blocks.**
Pandoc copies a bare `\begin{env}...\end{env}` span as one opaque block.
A caption inside it would go unescaped: a `&` breaks the build, a `%`
silently truncates the line (the `\label` included), and a `[@key]`
reaches the PDF unresolved. With two raw blocks the caption passes
through the Markdown reader. `_tables._caption_for` has the same shape.

An uncaptioned marker renders as ["Figure substitution"
above](#-figure-substitution-four-combinations-one-left-to-latex)
describes: no float, no number, no `\label`. A `figureref` naming an
uncaptioned or undeclared figure is left as written;
`python -m chitragupta.draft style` (`chitragupta/style_figures.py`)
reports it, and the render does not fail.

The `.tex` fragment carries neither marker and hand-authors a real
`\begin{figure}`, as it does a `\begin{table}`. Nothing writes a
`\renewcommand{\thefigure}`, so the thesis's own counter numbers it.

**The renderer never scales a figure, and is not to gain a way to.** It
`\input`s a figure bare, at its natural size, with no `\resizebox`,
`\scalebox` or width option. A scaled figure prints its type at whatever
the factor happens to be: six figures wrapped in
`\resizebox{\textwidth}{!}{...}` printed their smallest type between
5.5pt and 7.1pt against a 9pt body, with `pdflatex` exiting 0
([TIKZ-STYLE.md](TIKZ-STYLE.md#-draw-for-the-width-it-will-be-printed-at)).
An overflowing figure is answered by its layout, which
[`figure check`](figure-checks/README.md)'s `size-width` reports, never
by a scale knob; this is written down because an absence gets filled. A
scale in a thesis that `\input`s a fragment is outside every check here;
the drafting skills tell the author not to add one.

## 🔢 Table numbering: four cases, and pandoc numbers in only one

`_tables.substitute` (`chitragupta/render_output/_tables.py`) resolves
[WRITING-STANDARDS.md §13](WRITING-STANDARDS.md)'s two markers (the
`<!-- table: <id> -->` under a caption line, and the inline
`<!-- tableref: <id> -->`) into whatever the target format can count
with. Measured on pandoc 3.1.11.1:

| Draft | Output | Caption becomes | Reference becomes |
| --- | --- | --- | --- |
| `.md` | `tex`, `latex`, `pdf` | `: <caption>\label{tab:<id>}`; LaTeX counts it | `` `Table~\ref{tab:<id>}`{=latex} `` |
| `.md` | `md` | `**Table N:** <caption>`, a paragraph, since this path never reaches pandoc | `Table N` |
| `.md` | `docx`, `html`, ... | `: Table N: <caption>`, a real caption carrying a number pandoc will not supply | `Table N` |
| `.tex` | any | untouched; the fragment writes `\caption{}\label{}` itself | untouched |

Three things in that table are not guessable:

- **The docx writer numbers nothing**, so the number has to be in the
  text pandoc is handed.
- **`\label` survives a Markdown caption; `~` does not.** A bare
  `Table~\ref{tab:x}` in prose arrives as
  `Table\textasciitilde{}\ref{tab:x}`, because pandoc's Markdown reader
  escapes `~`. Hence the raw-attribute span in the first row.
- **Pandoc has no caption-attribute syntax**: `: Caption {#tbl:x}` sets
  the literal text `\{\#tbl:x\}`. Nor is pandoc-crossref's `@tbl:x`
  available, since `citation_gate.py` reads a bare `@key` as a citekey.

The order in `_substituted` is figures, tables, mathematics, equations: a
figure substitution can insert a fenced ASCII block, and `_math`'s
displayed-equation rule reads fences; equation numbering must follow
mathematics, for the reason the next section gives. On the `--format md`
path for a Markdown draft, `_raw_tex.dropped` runs after all four, where
it would catch a raw span if a pass ever emitted one.

## 🔢 Equation numbering: the one pass that reads what `_math` left behind

A marked equation gets the same "author writes no number" contract via
`chitragupta/render_output/_equation_captions.py`. An author opts an
equation in with `<!-- equation: id -->` directly above its
`<!-- math -->` marker (`docs/WRITING-STANDARDS.md` §12); an unmarked
block (a derivation step) is untouched.

It runs last, after `_math.substitute`, because the marker sits above
content `_math.py` rewrites into `$$...$$` on the pandoc path only, so it
recognises two shapes of a marked block, keyed on format:

| Draft | Output | A marked block becomes | An `equationref` becomes |
| --- | --- | --- | --- |
| `.md` | `tex`, `latex`, `pdf` | `\begin{equation}\n<latex>\n\label{eq:<id>}\n\end{equation}`; LaTeX counts it | `` `Equation~\ref{eq:<id>}`{=latex} `` |
| `.md` | `docx`, `html` | `**Equation N:**` above the kept `$$...$$`; pandoc numbers nothing outside LaTeX | `Equation N` |
| `.md` | `md` (never reaches pandoc) | `**Equation N:**` above the **untouched** `<!-- math -->` marker and fence | `Equation N` |
| `.tex` | any | untouched; the fragment writes `\[...\]` directly and has no markers | untouched |

Being last, it needs no precomputed `declared` list: nothing earlier
moves one equation marker relative to another.

**Numbering breaks the "the `md` path is a no-op" rule, on purpose and
only for numbering.** The content stays untouched on the `md` path, but
the number is written there as `**Equation N:**`, as `**Table N:**` is.
`python -m chitragupta.draft style` (`chitragupta/style_equations.py`)
reports a numbered equation nobody refers to, or an id problem; unlike
`style_tables.py`/`style_figures.py` it does not blank fenced code first,
because a marked equation is itself a fence.

## ✂ Three rewrites only a fragment gets

`_substituted` (`chitragupta/render_output/_substitution.py`) makes two
changes to the temp copy of a `--fragment` render, never to the draft on
disk:

- **The manual References section is dropped**, heading included, with
  any text after it kept (`_citeproc.drop_manual_refs`). The document
  that `\input`s the fragment resolves citations once, so a per-chapter
  list would be a second, differently numbered answer.
- **A chapter number the top heading states is dropped**
  (`chitragupta/render_output/_chapter_number.py`), in Markdown or
  `\chapter{}` spelling, since the `book` class supplies "Chapter 1" too.
  The draft on disk keeps it, for the unit's standalone pdf.

Both sit in `_substituted` because that function is the one answer to
"what does the writer actually see".

The third happens inside pandoc, because the labels it changes do not
exist until pandoc's reader has run:

- **A derived heading label is prefixed with the unit id**
  (`assets/pandoc/unit_labels.lua`, loaded by
  `chitragupta/render_output/_unit_labels.py`). pandoc labels a heading
  without `{#id}` from its text, so units that each have a "Summary"
  section all define `\label{summary}`, and a `\ref` resolves to
  whichever chapter LaTeX read last. `u1.md`'s Summary becomes
  `u1-summary`, and an in-unit link follows. A label the author wrote
  (`{#id}` or `\label{id}`) is left alone, because the outline and the
  registry resolve against it. pandoc's `--id-prefix` is ignored by its
  LaTeX writer. On a seven-chapter book: 10 labels defined in more than
  one unit before, none after.

## 🧾 A `.tex` draft's own preview

A thesis-chapter fragment's `tex`/`pdf` render is the only place its
author sees it typeset before building the thesis. Pandoc's LaTeX reader
used to lose four things on the way, each with exit `0`, so
`chitragupta/render_output/_tex_preview.py` changes the non-fragment
render of a `.tex` draft, and nothing else (a Markdown draft and every
`--fragment` render are as they were):

| What | How | Formats |
| --- | --- | --- |
| The figure | read with `-f latex+raw_tex`, so `\input{figures/x.tex}` reaches LuaLaTeX, through `TEXINPUTS` and the #823 read fence | `tex`, `latex`, `pdf` |
| A float's `\centering` | dropped from the copy pandoc reads: under `raw_tex` it is a block of its own, so pandoc would set a figure as two half-width minipages, and leave a table's bare after its `longtable`, centring every paragraph that follows | `tex`, `latex`, `pdf` |
| `\ref` numbers | `--number-sections`; LaTeX now resolves the raw `\ref` from the counters that number the headings, so "Section 1.1" names a heading that reads "1.1" | `tex`, `latex`, `pdf` |
| Absolute column widths | `p{2.6cm}` (and `m`, `b`; `cm`, `mm`, `in`, `pt`, `bp`) becomes `p{0.1633\linewidth}` against the house page's text width, before pandoc reads it; `em` and `ex` are left alone | every format |
| The references heading | `--metadata reference-section-title=References` | every format |

What `raw_tex` costs: a command pandoc does not know now reaches
LuaLaTeX, where it used to be dropped. One the thesis's preamble defines
stops the pdf, so the preview loads **the author's preamble file**,
`content/drafts/<topic>/<slug>.preamble.tex` beside the draft or, failing
that, a `preamble.tex` its chapters share, with `--include-in-header`,
before the font header, which stays last. The render names the file it
loads (`[preamble] <path>`), and refuses one that is a symlink out of the
draft's directory, as it refuses such a figure: pandoc reads the file
with no fence. When the pdf stops on an undefined command, the error
names the command and the file to define it in, and says an agent leaves
the file to the author. A citation inside a command pandoc keeps raw is
not resolved; the error says to move it out instead. `draft diff` copies
the draft's preamble beside each of its two sides.

## 🕳 Open gaps

- **A `.tex` fragment's `.md` preview prints section numbers its headings
  do not show.** Its `md` render keeps pandoc's default reader (a raw
  `\ref` would print as text there), which resolves
  `Section~\ref{sec:framing}` to "Section 1.1" while the Markdown
  writer ignores `--number-sections`, so the heading reads "Framing".
  The `tex`/`pdf` preview numbers both ([a `.tex` draft's own
  preview](#-a-tex-drafts-own-preview)). Left as is: the issue it came
  from was about the pdf.
- **A `.tex` fragment's own `tex`/`pdf` preview resolves citations with
  `--citeproc`, not `--natbib`.** `--natbib` is used for `--fragment`
  renders of Markdown units (see [citation
  resolution](#-citation-resolution-resolve-now-or-defer-to-the-consuming-document)),
  but a thesis fragment's preview bakes in citeproc's numbering, which
  `thesis-chapter-writer` relies on as the only place the fragment's
  citations are shown resolved. Switching would need
  `-f latex+raw_tex-auto_identifiers` (the reader the `tex`/`pdf`
  preview now uses, plus no auto-generated `\label` to collide across
  chapters).

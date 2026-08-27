# 🖨 Rendering flow

Status: **reference.** Written 2026-08-24. Updated 2026-08-26.

How `python -m chitragupta.draft render` turns a draft into `.md`/`.tex`/`.pdf`/`.docx`,
where a rendered draft's bibliography actually comes from, and what happens
to a figure on the way through.

**Written for** someone changing `chitragupta/render_output/`, or trying to
work out -- for a specific rendered file -- which of several places on
disk its bibliography or its figure actually came from. **Assumed** you
have read [ARCHITECTURE.md's drafting
layer](ARCHITECTURE.md#-layer-2-the-drafting-layer). **Not covered here:**
every render flag ([CLI.md](CLI.md)), the TikZ style rules a figure is
held to ([TIKZ-STYLE.md](TIKZ-STYLE.md)), and book assembly's own
citeproc pass over a composed book ([BOOKS.md](BOOKS.md)).

## 🧭 Table of contents

- [The two paths through `render()`](#-the-two-paths-through-render)
- [Citation resolution: `--citeproc` is the only mode there is](#-citation-resolution---citeproc-is-the-only-mode-there-is)
- [Mathematics: substituted on the pandoc path only](#-mathematics-substituted-on-the-pandoc-path-only)
- [Four places a rendered bibliography can live](#-four-places-a-rendered-bibliography-can-live)
- [The manual References section, and why citeproc replaces it](#-the-manual-references-section-and-why-citeproc-replaces-it)
- [Figure substitution: four combinations, one real no-op](#-figure-substitution-four-combinations-one-real-no-op)
- [Figure numbering: a caption wraps the marker, in two passes](#-figure-numbering-a-caption-wraps-the-marker-in-two-passes)
- [Table numbering: four cases, and pandoc numbers in only one](#-table-numbering-four-cases-and-pandoc-numbers-in-only-one)
- [Known defect: the fourth combination isn't a no-op on this host](#-known-defect-the-fourth-combination-isnt-a-no-op-on-this-host)
- [Unbuilt: a natbib-style mode for thesis fragments](#-unbuilt-a-natbib-style-mode-for-thesis-fragments)

## 🔀 The two paths through `render()`

`render()` (`chitragupta/render_output/__init__.py`) takes one of two routes,
decided by `output_format` and the draft's own suffix:

- **`--format md` on a Markdown draft never reaches pandoc.** This is a
  citation-*numbering* job, not a format conversion --
  `references.write_numbered` renumbers `[@key]` markers and appends an
  IEEE list in place, because pandoc's own Markdown writer would escape
  every marker to `\[1\]` and wrap the bibliography in `::: {#refs}`
  fenced divs that render as literal punctuation anywhere that isn't
  pandoc.
- **Every other combination goes through pandoc** -- `--citeproc` against
  `config.BIB_FILE_PATH`, the vendored IEEE CSL style, and (for `pdf`)
  `pdflatex`. This is the path the rest of this document is about,
  including a `.tex` fragment rendered to `.md`: converting
  `\citep{...}` to Markdown is a real format conversion, so it does not
  qualify for the first bullet's shortcut.

Output always lands mirrored under `content/rendered/`: a draft at
`content/drafts/<topic>/<name>.tex` renders to
`content/rendered/<topic>/<name>.{md,pdf,...}`.

## 📚 Citation resolution: `--citeproc` is the only mode there is

Every genre-skill draft cites with Pandoc-style `[@citekey]` markers (or,
for `thesis-chapter-writer`'s `.tex` fragment, `\citep{citekey}`/
`\citet{citekey}`). `_pandoc_command` always passes `--citeproc
--bibliography <bib> --csl <ieee.csl>` -- there is no flag or code path
that renders a citation any other way. Two fixups run first, on temp
copies only (`_safe_render_inputs`, `chitragupta/render_output/_citeproc.py`):
aliasing a citekey containing `--` (pandoc's tokenizer truncates it
mid-key otherwise, silently dropping the citation), and stripping control
characters / folding math-alphanumeric Unicode that `content/parsed/`
text can carry and pdflatex cannot. Neither the draft nor
`papers/bibliography.bib` is ever written to.

## 🔢 Mathematics: substituted on the pandoc path only

`chitragupta/render_output/_math.py` runs on the same temp copy, between
the figure swap and `_safe_render_inputs`, and turns a draft's ASCII into
mathematics pandoc can read -- `` `tau` `` into `$\tau$`, and a
`<!-- math -->` fence into `$$…$$` -- using the ASCII-to-LaTeX table in
the dossier's `math.md` ([DOSSIER.md](DOSSIER.md),
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) §12).

It turns on **the same predicate as the two paths above**: a render that
reaches pandoc gets the substitution, and `--format md` -- which does not
-- is a byte-perfect no-op, which is the whole reason the LaTeX lives
outside the draft. A span with no row is left exactly as it was, so
`as_of` stays `\texttt{as\_of}` by construction rather than by heuristic.

**It writes `$…$`, never `\(…\)`.** Pandoc's *Markdown reader* does not
read `\(…\)` as mathematics: handed `A $k = 4$ and B \(k = 4\)` it emits
`A \(k = 4\) and B (k = 4)`, silently dropping the second one's
backslashes. `$…$` is the native inline form, and each writer then
renders it in its own idiom -- which is what makes the output
format-native rather than LaTeX-shaped.

Two conditions **fail the render** rather than warning, because both mean
the pdf would carry verbatim text where the author said an equation goes:
a `<!-- math -->` marker with no row, and one with no `math.md` at all.
The second is what renaming a draft looks like -- a dossier is found by
path alone. Heuristic gaps print `[math]` warnings and carry on.

## 🗂 Four places a rendered bibliography can live

A render's citations don't resolve against a single file; four different
stores are involved, and confusing one for another -- only one of them is
this pipeline's own -- is the easiest way to misread what a rendered
draft actually proves:

| What | Where | Who reads it |
| --- | --- | --- |
| The bibliographic data | `papers/bibliography.bib` -- `config.BIB_FILE_PATH` (`chitragupta/config.py:221`), your own Zotero/JabRef export | pandoc's `--citeproc`, at render time only |
| The verification record | `content/ledger.sqlite` | `python -m chitragupta.draft gate`, `references.py`, retrieval -- never the render itself |
| The rendered bibliography | generated fresh into `content/rendered/...` on every render | a preview artefact; nothing downstream reads it back |
| The real bibliography, for a `.tex` fragment specifically | your own thesis's `\bibliography{...}`/biblatex resource, outside this repository entirely | your own `pdflatex`+`bibtex` run, at submission |

The fourth row only applies to `thesis-chapter-writer`'s output. Every
other genre's rendered draft *is* the bibliography-bearing artefact --
its citeproc-built reference list is the one a reader sees. A `.tex`
fragment's `\citep{doe_x_2024}` is deliberately left for the surrounding
thesis to resolve: `\input`ed into your own document, your own
`\bibliography{}`/biblatex run numbers it consistently with your other
chapters. The `.md`/`.pdf` preview this pipeline renders from that same
fragment (`--format md`/`--format pdf`, both run by
`thesis-chapter-writer` step 11) still goes through row three -- citeproc
against `papers/bibliography.bib` -- because a preview has to resolve
citations to be readable at all. That preview is not the deliverable and
nothing downstream reads it back; the fragment on disk, unresolved
`\citep{}` markers and all, is.

## 📄 The manual References section, and why citeproc replaces it

Four of the five prose genres run `python -m chitragupta.draft references
<draft>` after the gate, which writes a citekey-labelled `## References`
section built from exactly the citekeys the draft cites
(`references.py:90`'s `section_start` finds it by heading text). At
render time, `_swap_manual_refs_for_citeproc`
(`chitragupta/render_output/_citeproc.py:142`) replaces that section's
*entries* with pandoc's own placement anchor (`::: {#refs}\n:::\n`) while
keeping the heading -- so citeproc's bibliography, which is the one
numbered consistently with the inline markers and the one with authors
and venues in it, lands under the draft's own heading instead of a second,
untitled list appearing at the end.

`thesis-chapter-writer` skips the `references` step entirely
([ARCHITECTURE.md:192](ARCHITECTURE.md)) -- both by design, and mechanically
it could not run anyway: `references.py:529`'s CLI takes "Path to the draft
file (Markdown)", and `section_start` scans for a Markdown heading a `.tex`
fragment never has. Because the fragment carries no `## References`
section, `section_start` returns `None` and
`_swap_manual_refs_for_citeproc` returns the text unchanged -- the
function is citeproc-specific by construction, but it is harmless for a
genre that never reaches the case it exists to fix, rather than needing
its own exemption.

## 🖼 Figure substitution: four combinations, one real no-op

`_with_figures_for` (`chitragupta/render_output/_figures.py:324`) switches
every figure marker to the form the target format can draw, one of four
ways depending on the draft's own kind and whether the output is
LaTeX-bound (`tex`/`latex`/`pdf`):

| Draft carries | Output wants | What happens |
| --- | --- | --- |
| Markdown `figure:` marker + ASCII twin | LaTeX-bound | `_substitute_tikz_for_ascii`: marker becomes `\input{figures/<name>.tex}` |
| Markdown `figure:` marker + ASCII twin | non-LaTeX | `_substitute_ascii_for_marker`: marker becomes a fenced ASCII block |
| `.tex` fragment's inline `\input` + ASCII twin | non-LaTeX (`.md` preview) | `_substitute_ascii_for_tikz`: `\input{...}` becomes a `\begin{verbatim}` block of the ASCII twin |
| `.tex` fragment's inline `\input` | LaTeX-bound (`tex`/`pdf`) | **documented no-op** -- the TikZ is real and already inline, so nothing is substituted |

The third row exists because pandoc's LaTeX reader "resolves the `\input`
but then drops the `tikzpicture` environment, and keeps dropping it under
`-t markdown+raw_attribute`" (`_substitute_ascii_for_tikz`'s own
docstring) -- so without the swap, a `.tex` fragment's figure would
silently vanish from its own `.md` preview.

Two consequences of that table worth stating outright, because both
surprise people who have only read the code:

- **Nothing here adds a `figure` float or a `\caption`.** The
  substitution is a bare `\input`, so a captioned, numbered figure is one
  whose *figure file* carries the float --
  [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10.
- **Only `tex`/`latex`/`pdf` ever draw the TikZ.** `md`, `html` and
  `docx` all take row two and render the ASCII twin, which is why a
  panelled figure's `(a)`/`(b)` sub-captions have to exist in the `.txt`
  as well as in the picture: for three of the five formats the twin is
  the only thing the reader sees.

## 🔢 Figure numbering: a caption wraps the marker, in two passes

Issue 411 gives a *captioned* figure the same "author writes no number"
contract §13 gives a table, via
`chitragupta/render_output/_figure_captions.py` -- a sibling of
`_figures.py`, not a part of it, split out once the combined module
crossed `docs/CODE-STANDARDS.md`'s 250-code-line ratchet.

The Markdown contract is a `figure:` marker followed directly by its
caption, no blank line between (`_FIGURE_CAPTION_PAIR_RE`):

```markdown
<!-- figure: figures/delivery-modes -->
One reading path under three delivery modes.
```

Two passes run *before* `_with_figures_for`'s own substitution, in
`_substituted` (`chitragupta/render_output/__init__.py`), because both
read `figures()` off the original `[marker, caption]` text -- after
`_with_figures_for` replaces the marker with real content, that adjacency
is gone:

| Pass | What it resolves | LaTeX-bound (`tex`/`latex`/`pdf`) | Everything else |
| --- | --- | --- | --- |
| `substitute_captions` | The `[marker, caption]` pair | Wraps the untouched marker in `\begin{figure}...\caption{}\label{fig:<id>}...\end{figure}` -- LaTeX's own counter numbers it, no `\thefigure` override ever written | `<marker>\n**Figure N:** <caption>`, N counted in document order among captioned figures only |
| `substitute_refs` | An inline `<!-- figureref: <id> -->` | `` `Figure~\ref{fig:<id>}`{=latex} `` -- the same raw-attribute-span reason `_tables._reference_for` needs for `~` | `Figure N` |

An **uncaptioned** marker matches neither pass's regex and renders
exactly as ["Figure substitution" above](#-figure-substitution-four-combinations-one-real-no-op)
already describes -- no float, no number, no `\label`. A `figureref`
naming an uncaptioned figure's id, or one no figure declares at all, is
left exactly as written; `python -m chitragupta.draft style`
(`chitragupta/style_figures.py`) is what reports it, not a failed render.

The `.tex` fragment (`thesis-chapter-writer`) carries neither marker and
is untouched by either pass -- it hand-authors a real `\begin{figure}`
inline, the same carve-out the table section below states for a
`\begin{table}`. The only change there is one line removed:
`\renewcommand{\thefigure}{N.M}` is no longer written, so the user's own
thesis-wide `figure` counter numbers it instead.

## 🔢 Table numbering: four cases, and pandoc numbers in only one

`_tables.substitute` (`chitragupta/render_output/_tables.py`) resolves
[WRITING-STANDARDS.md §13](WRITING-STANDARDS.md)'s two markers -- the
`<!-- table: <id> -->` under a caption line, and the inline
`<!-- tableref: <id> -->` -- into whatever the target format can count
with. Every row was measured on this host's pandoc 3.1.11.1, because the
obvious assumption (pandoc numbers a captioned table) is true in exactly
one of them:

| Draft | Output | Caption becomes | Reference becomes |
| --- | --- | --- | --- |
| `.md` | `tex`, `latex`, `pdf` | `: <caption>\label{tab:<id>}` -- LaTeX counts it | `` `Table~\ref{tab:<id>}`{=latex} `` |
| `.md` | `md` | `**Table N:** <caption>` -- a paragraph, since this path never reaches pandoc | `Table N` |
| `.md` | `docx`, `html`, ... | `: Table N: <caption>` -- a real caption carrying a number pandoc will not supply | `Table N` |
| `.tex` | any | untouched -- the fragment writes `\caption{}\label{}` itself | untouched |

Three things in that table are not guessable and cost a render each to
find out:

- **The docx writer numbers nothing.** A captioned table round-trips out
  of `.docx` as a bare caption paragraph, so the number has to be in the
  text pandoc is handed.
- **`\label` survives a Markdown caption; `~` does not.** A raw
  `\label{tab:x}` written into a caption line reaches
  `\caption{...\label{tab:x}}` intact, but a bare `Table~\ref{tab:x}` in
  prose arrives as `Table\textasciitilde{}\ref{tab:x}` -- pandoc's
  Markdown reader owns `~` and escapes it. Hence the raw-attribute span
  in the first row, which is not decoration.
- **Pandoc has no caption-attribute syntax**, so an id cannot ride along
  in the caption: `: Caption {#tbl:x}` sets the literal text
  `\{\#tbl:x\}`. Nor is pandoc-crossref's `@tbl:x` available, since
  `citation_gate.py` reads a bare `@key` as a citekey and would fail the
  gate on `tbl`.

The substitution order in `_substituted` is figures, then tables, then
mathematics, and it is not arbitrary: a figure substitution can insert a
fenced ASCII block, and `_math`'s displayed-equation rule reads fences.

## 🐛 Known defect: the fourth combination isn't a no-op on this host

The fourth row's no-op rests on one assumption: that pandoc, asked to
render a `.tex` fragment to `tex`/`pdf`, hands the TikZ straight through
to `pdflatex` untouched. It does not, on pandoc 3.1.11.1 (this host,
2026-08-24) -- and nothing in `_with_figures_for` or `_pandoc_command`
intercepts it, because the fourth row is coded as "nothing to do here."

`_pandoc_command` (`chitragupta/render_output/__init__.py`) never passes
`-f`/`--from`. Without it, pandoc guesses the reader from the input
file's extension, and for `.tex` that guess is the **LaTeX** reader, not
Markdown -- confirmed by reproducing the render directly (not a mock):

```bash
$ printf '\\begin{tikzpicture}\\draw[blue] (0,0) circle (1);\\end{tikzpicture}\n' > figures/fig1.tex
$ printf '\\section{Framing}\nPrior work established Y.\n\n\\input{figures/fig1.tex}\n\nText after the figure.\n' > chapter.tex
$ pandoc chapter.tex --standalone -o out.tex; echo "exit=$?"
exit=0
```

`out.tex` contains `\section{Framing}\label{framing}` (the auto-generated
`\label` only the LaTeX reader's `auto_identifiers` extension produces),
`Prior work established Y.`, and `Text after the figure.` -- the
`\input` is resolved and the `tikzpicture` environment inside it is
gone. No warning, exit `0`. This is the same failure mode
`_substitute_ascii_for_tikz`'s docstring already names for the `.tex`→`.md`
path -- pandoc's LaTeX reader drops an environment it doesn't
understand -- except that combination has a swap guarding it and this one
does not, because `_with_figures_for`'s docstring treats `.tex`→`tex`/`pdf`
as the one genuinely inline case needing no substitution. The file on
disk is inline; what pandoc's reader does with it before `pdflatex` ever
sees the result is not.

**This contradicts `thesis-chapter-writer/SKILL.md`'s own claim** (step
9: "`--format tex` and `--format pdf` get the TikZ") for any figure that
uses `\input`, which is the shape that skill's own step 9 tells the
genre to write. Passing `-f latex+raw_tex` instead of the bare default
reader leaves `\input{...}` as a raw command rather than resolving it --
confirmed to restore the figure, since `pdflatex` (with `TEXINPUTS`
already set for the `pdf` format, `chitragupta/render_output/__init__.py`)
then reads the real file itself. **Not applied anywhere in this
codebase as of this writing** -- flagged here rather than fixed, since
fixing it is a separate, scoped change.

## 🧾 Unbuilt: a natbib-style mode for thesis fragments

A change discussed but not built: rendering a `.tex` fragment's `tex`/`pdf`
preview with `--natbib` instead of `--citeproc`, so the preview defers
citation resolution to `bibtex` the same way the fragment's real,
`\input`-ing thesis eventually will, rather than baking citeproc's own
numbering into a document that only ever wants to demonstrate the
fragment compiles. `--citeproc` and `--natbib` are rival strategies for
the same job -- one resolves now and writes a formatted bibliography into
the output, the other emits `\citep{key}` plus
`\bibliographystyle{}`/`\bibliography{}` for the *consuming* document's
own `bibtex` to resolve later -- and pandoc accepts both flags together
without erroring, silently letting `--natbib` win. Nothing in this
codebase passes `--natbib` today; `_pandoc_command` always passes
`--citeproc`, unconditionally, for every format.

Two things worth recording about that unbuilt mode, in case it is picked
up later: it would need `-f latex+raw_tex-auto_identifiers` on the LaTeX
reader (the previous section's fix, plus turning off `auto_identifiers`
so a fragment's own `\section{Introduction}` doesn't collide with another
chapter's), and `--variable biblio-style=IEEEtran` (pandoc's own default
under `--natbib` is `plainnat`, author-year, which would render this
project's one numeric-citation genre in the wrong style; `IEEEtran.bst`
is present on this host at
`/usr/share/texlive/texmf-dist/bibtex/bst/ieeetran/`). It would also need
`_swap_manual_refs_for_citeproc` (see above) to keep refusing to run
under `--natbib` -- which it already does, since a thesis fragment has no
`## References` section for `section_start` to find, but that safety is
currently incidental rather than asserted, and a future change wiring
`--natbib` into a genre that *does* write a References section should
make the refusal explicit rather than relying on the same accident.

# A `.tex` draft's preview shows what the thesis will show

Status: **built**, on branch `fix-1120-1164-tex-preview` (v6.179.1,
PATCH, not released). Changed on the way: the never-write rule rides in
the error hint, not the skill (a skill edit needs a bench); every
alignment or size declaration inside a group is dropped, not only a
figure's `\centering` (a real chapter's table leaked one); widths are
rewritten only in an all-`p`/`m`/`b` spec, and `em`/`ex` are left alone;
a preamble symlinked out of the draft's directory is refused, and the
one loaded is named.
Written 2026-11-21 for
[issue 1164](https://github.com/prasadtalasila/chitragupta/issues/1164)
(item 6 of [issue 1108](https://github.com/prasadtalasila/chitragupta/issues/1108))
and [issue 1120](https://github.com/prasadtalasila/chitragupta/issues/1120),
in one pull request, as both issues ask.

**Written for** whoever builds or reviews it. **It assumes**
[docs/RENDERING-FLOW.md](../docs/RENDERING-FLOW.md) for the render path,
and [plans/823-tex-read-hardening.md](823-tex-read-hardening.md) for the
read fence. **Not covered here:** book units and every Markdown draft.
They never go through pandoc's LaTeX reader (the owner's scope comment on
issue 1120). Also not covered: the `.tex` preview's citeproc against natbib
choice, which stays as it is (RENDERING-FLOW.md, "Open gaps", second
bullet).

## Why

`thesis-chapter-writer` delivers a `.tex` fragment the author `\input`s
into their thesis. Its `tex`/`pdf` preview (`draft render --format pdf
<slug>.tex`) is the only place the author sees the chapter typeset before
they build the thesis. Today that preview differs from the thesis in
four ways, all with exit 0 and no warning:

1. The figure is gone (#1164). Pandoc's LaTeX reader follows
   `\input{figures/x.tex}` and drops the `tikzpicture` inside it.
2. A table with absolute column widths (`p{2.6cm}`) runs off the page
   (#1120 item 1). The reader turns `p{...}` into `l`.
3. `Section~\ref{sec:framing}` prints a number no heading shows (#1120
   item 2). Pandoc resolves the `\ref` itself while the template leaves
   the headings unnumbered.
4. The reference list has no heading (#1120 item 3).

## Decisions (user, 2026-11-21)

1. **One pull request** for #1164 and #1120.
2. **Reader: `-f latex+raw_tex`** for a `.tex` draft's LaTeX-bound renders
   (`tex`, `latex`, `pdf`), as RENDERING-FLOW.md's open gap suggests.
   Picked over passing only the figure `\input`s through, knowing that
   every command pandoc does not know then reaches LuaLaTeX.
3. **Thesis-only commands: option 3.**
   - **A preamble file:** a `.tex` draft's preview loads a preamble file
     kept beside the draft, modelled on the book track's
     `content/specs/<book>/preamble.tex`.
   - **A hint:** when LuaLaTeX stops on an undefined command in a `.tex`
     preview, one added line names the command and that file.
4. **The preamble file is the author's** (2026-11-22). The skill quotes
   the hint and names the missing command; it never writes or edits the
   file, the same rule as never editing the thesis.
5. **The Markdown preview's section numbers are out of scope**
   (2026-11-22). #1120 is about the PDF. The md preview still reads
   "Section 1.1" under an unnumbered heading, because pandoc's Markdown
   writer ignores `--number-sections`; RENDERING-FLOW.md's "Open gaps"
   records it.

## Measured before the change (pandoc 3.1.11, 2026-11-21)

On #1120's reproduction plus a figure (`th.tex`) and an author macro
(`m.tex`):

| | `-f latex` (today) | `-f latex+raw_tex` |
| --- | --- | --- |
| `\input{figures/fig1.tex}` | dropped with its `tikzpicture` | kept raw |
| `Section~\ref{sec:framing}` | `\hyperref[sec:framing]{1.1}` | `\ref{sec:framing}` kept raw |
| `p{2.6cm}p{4.5cm}p{6cm}` | `longtable` `lll` | `longtable` `lll` (unchanged) |
| reference list | `\label{refs}` with no heading | the same |
| `\todo{fix this}` | dropped silently | kept raw, so LuaLaTeX stops |

## The changes

### 1. The reader (#1164, and half of #1120 item 2)

When the input is a `.tex` draft and the output is LaTeX-bound, pandoc
is called with `-f latex+raw_tex`.

- **md, html and docx keep the default reader.** They cannot draw TikZ
  and already swap each figure for its ASCII twin
  (`_substitute_ascii_for_tikz`). A raw `\ref` in a Markdown preview
  would print as `\ref{...}` text.
- **The fourth row of RENDERING-FLOW.md's figure-substitution table**
  stops being a no-op that loses the figure. The `\input` now reaches
  LuaLaTeX, which reads `figures/x.tex` through `TEXINPUTS` and the #823
  read fence as it already does for a Markdown draft's figures.
- **The fence must still refuse a read outside the draft's directory.**
  A test shows a raw `\input{/etc/hostname}` in a `.tex` draft is
  refused under the new reader.
- **The `--fragment` render is unchanged.** It is the deliverable, and it
  never had a reader problem.
- **A figure's own `\centering` is dropped from the preview's copy**
  (my call, measured). Under `raw_tex`, `\begin{figure}\centering
  \input{...}\caption{...}` reaches the writer as two blocks, an empty
  one and the `\input`, and pandoc sets them as two `0.45\linewidth`
  minipages side by side, so the figure prints at half width. Without
  the `\centering`, pandoc writes its own and keeps one block. A Lua
  filter (or the same pre-pass as the width rewrite) removes a raw block
  that is only `\centering` inside a figure.
- **A citation inside a command pandoc keeps raw stays raw** (my call).
  `\todo{x \citep{a}}` reaches LuaLaTeX with `\citep` undefined, since
  a citeproc render loads no natbib. The hint below names that case
  ("a citation inside a command pandoc does not know is not resolved;
  move it out") instead of telling the author to define `\citep`. No
  fallback `\citep` is defined: it would print a key, not a citation,
  and leave the source out of the list.
- **`draft diff` takes the same path** (my call). It renders both sides
  of a `.tex` draft as non-fragment `tex` with `defer_citations=True`
  (`draft_diff/_cli.py`), so the reader, numbering and width rewrite
  apply to both sides alike. Its preamble file is found from the real
  draft's path, the way `math_mapping_path(draft)` is, not from the
  review directory the sides are written to.

### 2. Numbered headings (#1120 item 2)

A `.tex` draft's non-fragment `tex`/`pdf` render passes
`--number-sections`. The thesis numbers its chapters, and with the raw
`\ref` LaTeX now resolves each reference from the same counters that
number the headings, so "Section 1.1" names a heading that reads
"1.1 Framing". The preview's numbers start at 1, where the thesis's
start at the chapter's place; that is expected. Markdown drafts are
unchanged.

### 3. Absolute column widths (#1120 item 1)

The reader drops `p{...}` widths before any filter sees them, so the fix
rewrites the source first. In a `.tex` draft's column spec, each `p{}`,
`m{}` or `b{}` width given in an absolute unit (`cm`, `mm`, `in`, `pt`,
`em`, `ex`) becomes a fraction of `\linewidth` against the preview's own
text width (`chitragupta.page`, which `figure check` uses for the same
number; 452.97pt for the house article page). For example,
`p{2.6cm}` becomes `p{0.1636\linewidth}`. Pandoc keeps fractional widths
(issue 1120: `p{0.2\linewidth}` survives).

- **Every format of a `.tex` draft's non-fragment render** gets the
  rewrite, since docx and html use column widths too.
- **The draft on disk is never changed.** The rewrite rides in the text
  handed to pandoc, as the figure substitutions already do.
- **No scaling.** A table whose widths add up past the text width
  overflows in the preview as it would in a thesis of the same width.

### 4. The references heading (#1120 item 3)

A `.tex` draft's non-fragment render passes
`--metadata reference-section-title=References`. A Markdown draft
already writes its own `## References`, and adding a title there would
print two headings. The fragment has no list at all (`--natbib`).

### 5. The thesis preamble file, and the hint

- **The file:** for a `.tex` draft `content/drafts/<slug>.tex`, the
  preview of a non-fragment `tex`/`pdf` render includes
  `content/drafts/<slug>.preamble.tex` if it exists. If it does not, it
  includes `preamble.tex` in the same directory, which one thesis's
  chapters can share. It is passed with `--include-in-header`,
  after every other header except the font header, which stays last on
  purpose (`_pandoc.py`: it sets the fonts and the missing-character
  stop). So the author's `\newcommand`s and `\usepackage`s apply, and a
  font or `fontenc` line in it cannot undo the font chain (my call). A
  package that clashes with one the template loads (`geometry`,
  `hyperref` with options) is the author's to resolve; the docs say so,
  and the hint does not try to read option clashes.
  - It is the author's own LaTeX, trusted like the draft. The read fence
    still governs any file it `\input`s.
  - Nothing else reads it: it is not a draft, and the gate, `draft
    render` and `dossier status` already ignore files they are not
    pointed at. (Verify while building.)
- **The hint:** when a `.tex` draft's pdf render fails and pandoc's
  stderr has `Undefined control sequence`, the error gets one more line
  beside `_figure_repair_hint` and `_unicode_repair_hint` in
  `render_output/_cli.py`. The line names the command from the log line
  after the error, says the preview loads none of the thesis's
  preamble, and names the preamble file to define it in.
  - If the command cannot be read from the log, the line still names
    the file.

## Docs

- **RENDERING-FLOW.md:** drop the first "Open gaps" bullet; turn the
  figure table's fourth row into what now happens; add the reader, the
  numbering, the width rewrite, the references title and the preamble
  file to the `.tex` draft's path.
- **thesis-chapter-writer** (`SKILL.md` step 12, or `references/thesis.md`):
  one line on the preamble file and the hint: quote the hint, name the
  command, and leave the file to the user. Never write or edit it.
- **RENDERING-FLOW.md, "Open gaps":** add the md preview's section
  numbers (decision 5).
- **WRITE-A-THESIS-CHAPTER.md:** the preamble file, where the book guide
  documents `preamble.tex`. The owner's limit on editing the WRITE-A-*
  guides was for the docs cut; a change a code change requires is
  outside it.

## Left to the builder

- Where the width rewrite lives: a small module beside `_tables.py`, or
  in it.
- The exact hint wording.
- Version: PATCH (fixes to an existing preview, plus an optional file).
  Re-read `main`'s version before bumping.

## Acceptance

- #1164's reproduction: the `tikzpicture` is in the rendered `.tex`, and
  the PDF draws the circle.
- #1120's reproduction: the table wraps inside the text width; the
  headings are numbered and `\ref` names one of them; "References" heads
  the list.
- A `.tex` draft using `\todo` fails with the hint. With
  `\newcommand{\todo}[1]{}` in `<slug>.preamble.tex` it renders.
- A Markdown draft's renders and every `--fragment` render are byte for
  byte what they were. Check the repository's own sample drafts and one
  book unit.
- The two `.tex` drafts in the sample project, if any, still render.

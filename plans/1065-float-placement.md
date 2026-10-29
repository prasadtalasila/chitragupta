# 1065: keep figures that fit in the text out of float-only pages

Status: **in progress.** Written 2026-10-29 for
[#1065](https://github.com/prasadtalasila/chitragupta/issues/1065), item
1f of [fig-xii-figure-drawer-v3.md](fig-xii-figure-drawer-v3.md).

**Written for** whoever changes where a rendered figure lands: the
standalone `draft render` preamble, or the book skeleton
`book-assembler` writes.

**Assumed:** every pdf is LuaLaTeX (#996, #1037); the book is built by
the commands in `.claude/skills/book-assembler/SKILL.md`, not by Python.

**Not covered here:** a thesis document's own preamble. A thesis
fragment gets the file copied beside it, and including it is that
document's choice. No figure file changes, and no new gate.

## What the reference book showed

Measured on the reference book of #1045 (the LuaLaTeX build of
2026-10-28: 287 pages, 40 figures, every one a bare `\begin{figure}`
under the `book` class defaults). A float-only page is one shipped
while the kernel's `\if@fcolmade` is true, read at `shipout/before` and
crossed with each figure's label page in `book.aux`; the text of each
flagged page was checked by hand.

| Preamble | Float-only pages | Figures on them | Pages |
| --- | --- | --- | --- |
| `book` defaults (`tbp`, `\floatpagefraction` .5) | 3 | 2.1 (p. 23), 2.5 (p. 36), 4.5 (p. 96) | 287 |
| The fractions below, `tbp` | 0 | -- | 287 |
| The fractions below, `htbp` | 0 | -- | 287 |

Six figures changed page under the new settings (2.2, 2.3, 2.5, 5.3,
5.6, 7.2), each by one page and each **earlier**, nearer its text. None
moved later.

The cause was `\floatpagefraction` .5. LaTeX tries a float page before
it tries the top of a text page, so a figure half a page tall qualified
for a page of its own even though `\topfraction` .7 would have let it
sit above text.

## The settings

One shipped file, `assets/latex/chitragupta-floats.tex`:

| Parameter | LaTeX default | Here | Why |
| --- | --- | --- | --- |
| `\floatpagefraction` | .5 | .8 | a float page must be mostly figure |
| `\topfraction` | .7 | .85 | a tall figure may still sit above text; must exceed the line above |
| `\bottomfraction` | .3 | .5 | the same at the foot of a page |
| `\textfraction` | .2 | .1 | let a page be mostly figure and still hold text |
| `topnumber`, `totalnumber` | 2, 3 | 3, 4 | a run of small figures need not queue |
| placement default | `tbp` | `htbp` | what pandoc's own template already gives an image figure |

`htbp` measured the same as `tbp` on this book. It is kept so a TikZ
figure and an image figure place alike.

## The report

The same file, under LuaLaTeX only (`\ifdefined\directlua`), notes every
figure shipped on a float-only page. A `shipout/before` hook copies
`\if@fcolmade` into Lua. An `env/figure/end` hook puts a `\latelua` node
holding the figure's number (frozen when the figure is set) into the
float, and that node runs when the page ships. It writes
`chitragupta float page: <page> holds Figure <n>` to the log.

- **The book** reads `book.log`, in SKILL.md's existing "read the log
  before believing the PDF" step.
- **A `draft render` pdf** cannot read the log: pandoc deletes it on
  success. The first design had LuaLaTeX write a file the render named,
  but kpathsea's `openout_any=p` refuses LuaLaTeX an absolute path
  outside the `TEXMFOUTPUT` pandoc sets (measured: `io.open` answers
  `nil`), and loosening that would undo #823. pandoc passes on no LaTeX
  warning but `Missing character`, and `--verbose` mixes the log into
  the whole source dump. So after the last page the same lines go into
  the pdf's own Info dictionary as `/ChitraguptaFloatPages`, hex-encoded,
  and only when there is one. LuaTeX writes that dictionary
  uncompressed. `_run_pandoc` reads it once pandoc returns and prints one
  `[float-page]` line per page on stderr. The exit status is unchanged,
  and the template's own Info entries (the title) survive it.

## Wiring

- `chitragupta/render_output/_floats.py` owns the file's name, the
  include for a standalone LaTeX-bound render, the copy beside a
  figure-bearing `--fragment` (with a `[floats]` notice, the shape
  `[unicode]` already prints), and the report.
- `_pandoc.py` calls it from `_pandoc_command` and `_run_pandoc`.
  `render_output/__init__.py` is at the 250-line ceiling and is not
  touched.
- The book skeleton in `references/latex-conventions.md` gains
  `\input{chitragupta-floats}`, and SKILL.md's build step greps the log.

## Checked on the reference book with the shipped file

- With `\input{chitragupta-floats}` in the skeleton: 0 float-only pages,
  287 pages, and the skill's grep prints `[]`.
- With the class defaults put back after it: the file's own report names
  Figures 2.1 (p. 23), 2.5 (p. 36) and 4.5 (p. 96), the same three the
  measurement above found, in `book.log` and through
  `_floats.print_report` on the pdf.

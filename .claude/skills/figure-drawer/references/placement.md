# figure-drawer: where a figure goes

Read a section when the procedure in `SKILL.md` points at it.
`docs/WRITING-STANDARDS.md` §10 is the contract for every figure; where
the two ever disagree, that document wins and this file is the bug.

## 1. Where the pair goes

| Draft | In the draft | Files |
| --- | --- | --- |
| `.md` (survey, tutorial, textbook chapter) | a line of its own, `<!-- figure: figures/<name> -->`; its caption line directly below it (no blank line), and an inline `<!-- figureref: <name> -->` wherever prose points at it | `figures/<name>.tex` and `figures/<name>.txt` |
| `.tex` (thesis chapter) | `\input{figures/<name>.tex}` then `%figure: figures/<name>` on the next line; a captioned figure goes inside a hand-written `figure` float with `\caption{...}` and `\label{fig:<id>}` | the same pair |

Both files sit under the draft's topic directory,
`content/drafts/<topic>/figures/`. A flat draft has no topic directory of
its own: the caller's figure step says what to do about that, and on
direct use §3 does. Never write the word "Figure" or a number yourself.
The renderer, or the thesis's own LaTeX, assigns both.

The caller places the marker and the caption in its own shape. On direct
use the caller is the revision loop, which has no figure step of its
own, so §2 to §4 are this skill's to state.

## 2. No TikZ on the host

When `kpsewhich tikz.sty` finds nothing, write no pair. Write the ASCII
inline instead, in a fence in a `.md` draft or in a `verbatim`
environment in a `.tex` one, with no marker, and say so in chat. A
genre's own figure step names the same fallback for its drafts.

## 3. A flat draft

A flat draft is `content/drafts/<slug>.md` or `.tex`, with no topic
directory. Figures beside it would land in `content/drafts/figures/`,
shared with every other flat draft. Ask whether to move the draft and
its dossier into a topic directory first, or to drop the figure.

## 4. A thesis fragment

The fragment is `\input` into the person's own thesis, whose preamble
this pipeline never touches, so some things are theirs to know. A
render made with `--fragment` names them, one line each; the md and pdf
previews of a fragment have preambles of their own and print none of
these lines.

- **The engine.** chitragupta's own pdf render runs LuaLaTeX, with the
  fonts `chitragupta-lualatex.tex` sets, and LuaLaTeX is the
  recommended engine for their thesis too. When the render prints a
  `[unicode]` line, it has copied `chitragupta-lualatex.tex` and
  `chitragupta-unicode.sty` beside the fragment. Tell them to copy
  `chitragupta-lualatex.tex` next to their thesis and `\input` it after
  `fontspec` and `unicode-math`, so every such character prints from the
  fonts the preview used. `chitragupta-unicode.sty` applies only if
  their template forces pdflatex: copied next to the thesis and loaded
  with `\usepackage{chitragupta-unicode}`, it teaches pdflatex those
  characters, never overrides a glyph their preamble already gives one,
  and does nothing under LuaLaTeX. The engine is their template's to
  choose; never edit their thesis to change it.
- **TikZ libraries.** When the render prints a `[tikz-libraries]` line,
  quote it and tell them that `\usetikzlibrary{...}` with those names
  belongs in their thesis preamble, beside `\usepackage{tikz}`. Their
  figures are `\input` inside `figure` floats, and a float is a group: a
  library loaded there defines its macros locally but sets its loaded
  flag globally, so the second figure skips the load and finds no
  macros. Never work around it inside a figure file: clearing the flag
  makes `positioning` append its placement transform to a global hook
  once per figure, so the Nth figure shifts every node N times, with the
  engine exiting 0. The preamble load also saves the width of a figure
  they set in `\resizebox`, `\sbox` or inline: a library loaded there
  prints its own line ends as 135pt to 147pt of blank space before the
  picture, and since that band is inside the box, `\resizebox` scales
  it along with the picture.
- **Float placement.** A `[floats]` line is optional for them:
  `\input{chitragupta-floats}` in their thesis preamble gives the float
  placement the pdf preview used, and leaving it out keeps their
  template's own. It is a choice, not a fix, so never add it yourself.
- Never write `\renewcommand{\thefigure}`: their thesis's own counter
  numbers the figure.

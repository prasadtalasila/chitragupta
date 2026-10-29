# figure-drawer: where a figure goes

Read a section when the procedure in `SKILL.md` points at it.
`docs/WRITING-STANDARDS.md` §10 is the contract for every figure; where
the two ever disagree, that document wins and this file is the bug.

## 1. Where the pair goes

| Draft | In the draft | Files |
| --- | --- | --- |
| `.md` (survey, tutorial, textbook chapter) | a line of its own, `<!-- figure: figures/<name> -->`; if the figure warrants a caption, a caption line directly below it (no blank line), and an inline `<!-- figureref: <name> -->` wherever prose points at it | `figures/<name>.tex` and `figures/<name>.txt` |
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

The fragment is `\input` into the person's own thesis, so some things
are theirs to know:

- When the render prints a `[tikz-libraries]` line, quote it and tell
  them that `\usetikzlibrary{...}` with those names belongs in their
  thesis preamble. Never work around it inside a figure file.
- When it prints a `[unicode]` line, tell them to copy
  `chitragupta-unicode.sty` beside their thesis and load it.
- A `[floats]` line is optional for them: `\input{chitragupta-floats}`
  gives their thesis the float placement the pdf preview used, and
  leaving it out keeps their template's own.
- Never write `\renewcommand{\thefigure}`: their thesis's own counter
  numbers the figure.

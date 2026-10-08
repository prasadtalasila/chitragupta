---
name: figure-drawer-opencode
description: Draws one figure for a draft in content/drafts/ -- a TikZ picture in figures/<name>.tex and its ASCII twin in figures/<name>.txt -- from the house scaffolds in assets/tikz/, then compiles and reviews it. Handed off to by survey-writer-opencode, tutorial-writer-opencode, textbook-chapter-writer-opencode and thesis-chapter-writer-opencode once they have decided a figure is warranted, and by draft-reviser-opencode to redraw or fix one. Also triggers directly when the user asks to draw, add, redraw or fix a figure or diagram in an existing draft. Owns how a figure is drawn, never whether a genre wants one. Never presents a draft -- it returns to the skill that called it, which gates and renders. Never puts a citekey in a figure file.
tags: [figure, tikz, drafting]
---

# figure-drawer

This skill owns *how* a figure is drawn. Whether a draft wants one, and
what shape it takes in that draft, belongs to the genre skill that
called you; its figure step has already decided both.
`docs/WRITING-STANDARDS.md` §10 is the contract for every figure, and
`docs/TIKZ-STYLE.md` is the detail behind each step below.

This skill **never presents a draft.** When the figure is drawn and
checked, return to the step that sent you here.

## Who called you

- **A genre skill** (`survey-writer-opencode`,
  `tutorial-writer-opencode`, `textbook-chapter-writer-opencode` or
  `thesis-chapter-writer-opencode`). It has decided a figure is
  warranted and named its shape. Draw, check, and return to
  its next step.
- **`draft-reviser-opencode`**, redrawing or fixing one figure. The same, and it
  logs the change when you return.
- **The user, directly** ("draw a figure for section 3 of
  rag/survey.md showing how a query moves through retrieval"). That
  changes an existing draft, so it is a revision. Read the draft's
  `scope.md` for its genre and house style, and the draft's extension
  for its shape (the table below). Draw and check. Then continue in
  `draft-reviser-opencode`'s loop at "6. Write the dossier back" and its
  "7. Gate, reference, render" onward: those log the change in
  `revisions.md`, run the gate, render, and re-stamp the fingerprint.
  The genre's when-to-draw threshold does not apply here, because the
  person asked for the figure. A `deep-research-opencode` draft takes no figure
  (its skill says why); say so and stop. With no draft to put it in,
  there is nothing for this skill to place a figure into; say so.

## Where it goes

| Draft | In the draft | Files |
| --- | --- | --- |
| `.md` (survey, tutorial, textbook chapter) | a line of its own, `<!-- figure: figures/<name> -->`; if the figure warrants a caption, a caption line directly below it (no blank line), and an inline `<!-- figureref: <name> -->` wherever prose points at it | `figures/<name>.tex` and `figures/<name>.txt` |
| `.tex` (thesis chapter) | `\input{figures/<name>.tex}` then `%figure: figures/<name>` on the next line; a captioned figure goes inside a hand-written `figure` float with `\caption{...}` and `\label{fig:<id>}` | the same pair |

Both files sit under the draft's topic directory,
`content/drafts/<topic>/figures/`. A flat draft has no topic directory
of its own; the caller's figure step says what to do about that, and on
direct use the section below does. Never write the word "Figure" or a
number yourself: the renderer, or the thesis's own LaTeX, assigns both.

### On direct use

A genre skill's figure step covers the cases below for its own drafts.
On direct use the caller is `draft-reviser-opencode`, which has no figure step,
so they are this skill's to state:

- **No TikZ** (step 7's probe finds nothing): write no pair. Write the
  ASCII inline instead, in a fence in a `.md` draft or in a `verbatim`
  environment in a `.tex` one, with no marker, and say so in chat.
- **A flat draft** (`content/drafts/<slug>.md` or `.tex`, no topic
  directory): figures beside it would land in `content/drafts/figures/`,
  shared with every other flat draft. Ask whether to move the draft and
  its dossier into a topic directory first, or drop the figure.
- **A thesis fragment.** The fragment is `\input` into the user's own
  thesis, so two things are theirs to know. When the render prints a
  `[tikz-libraries]` line, quote it and tell them that
  `\usetikzlibrary{...}` with those names belongs in their thesis
  preamble; never work around it inside a figure file. When it prints a
  `[unicode]` line, tell them to copy `chitragupta-unicode.sty` beside
  their thesis and load it. And never write `\renewcommand{\thefigure}`:
  their thesis's own counter numbers the figure.

## The procedure

1. **Look before you draw.** `python -m chitragupta.draft figures
   <citekey>` lists a synced paper's figures and hands back a crop of
   each, for any citekey the draft already cites. Seeing how a concept
   is conventionally drawn, and seeing several versions of it, is
   legitimate input to a diagram you then draw yourself. It is not a
   licence to reproduce one: the source image never enters the draft,
   and a close redraw of any single one is the same violation, per
   `docs/WRITING-STANDARDS.md` §10. AGENTS.md states the boundary in
   full.

2. **Commit to a layout metaphor before drawing, and start from the
   scaffold for it rather than from an empty picture.** `assets/tikz/`
   holds one known-good file per metaphor `docs/TIKZ-STYLE.md` names --
   pipeline, map, layered stack, control loop, branching tree,
   hub-and-spoke, zoned spine. Copy the one that fits and re-label it,
   leaving the house style block it carries unedited. Then run
   `python -m chitragupta.figure sync <the figure file>`, which
   refreshes the block if the scaffold's copy is older than the
   installed one, and reports instead of overwriting if you edited
   inside it. Each places its
   nodes relative to one another, which is the property worth keeping:
   a figure laid out in hand-computed millimetres re-opens every
   adjacency in it the moment any label changes length. Then check the
   result against that document's pre-flight defect list (occlusion,
   chaotic routing, illegible type, non-rectangular protrusion, an
   overlong node, literal copying) before keeping the figure. No label
   goes below the body size, and the figure is `\input` bare, never
   inside `\resizebox`: if it does not fit, change the layout, not the
   scale. For which metaphor fits, see
   `.claude/skills/figure-drawer/references/figures.md` §1 (paths in this
   skill are from the project root); for a figure that does not fit the
   width, `.claude/skills/figure-drawer/references/figures.md` §3; for
   what the house block's zone cards, badges and legend are for,
   `.claude/skills/figure-drawer/references/figures.md` §4.

   ```bash
   cp assets/tikz/zoned-spine.tex content/drafts/rag/figures/flow.tex
   python -m chitragupta.figure sync content/drafts/rag/figures/flow.tex
   ```

3. **Panels get lettered sub-captions, in both forms.** A figure with
   more than one panel is still one figure and one marker; each panel
   carries a `(<letter>) <short title>` node -- `(a)` for the first
   panel in reading order, `(b)` for the second, on through the
   alphabet -- and the same letters appear in the `.txt` -- `docx`,
   `html` and `md` render only that form, so letters left out of it are
   letters the reader never sees. Which lettering to use is `scope.md`'s
   to say, when it records one. The worked three-panel example, the
   row-wrapping rule for a row that stops fitting, and why the
   `subcaption` package is not the answer are in
   `.claude/skills/figure-drawer/references/figures.md` §2.

4. **Write the ASCII twin** in `figures/<name>.txt`, in
   `docs/WRITING-STANDARDS.md` §10's 7-bit alphabet, depicting the same
   thing as the TikZ: the same boxes, the same arrows, the same panel
   letters. A Unicode box character hard-fails `pdflatex`. Nothing
   checks that the two forms agree, so check it yourself before going
   on.

5. **No citekey inside either figure file.** The gate reads the draft
   and does not follow `\input`, so a citekey in a node label evades the
   one check this pipeline exists for. Attribute in the prose beside the
   figure, where the gate can see the key.

6. **The TikZ must be as original as the ASCII.** A picture redrawn from
   a source paper's figure is the same violation in different pixels,
   whichever notation it is drawn in.

7. **Verify the TikZ compiles before keeping it.** Run
   `kpsewhich tikz.sty` first. **If it finds nothing, write no pair:
   return to the caller, whose figure step names its inline ASCII
   fallback (on direct use, "On direct use" above), and say so in
   chat.** If it is present, wrap
   `figures/<name>.tex` in a minimal `\documentclass{article}` +
   `\usepackage{tikz}` document and run `pdflatex` on it. A malformed
   figure fails the *whole* pdf render, not just the figure. If the
   figure uses `positioning`, `matrix`, `fit` or `tree`, put its
   `\usetikzlibrary` line at the top of `figures/<name>.tex` and copy
   that line into the probe too: the probe's own preamble loads `tikz`
   and no library, so a picture that relies on one errors there whether
   or not it is sound. Keep the line in the figure file and write
   nothing else about loading -- no clearing of
   `\tikz@library@...@loaded`, no saving or restoring of
   `\tikz@node@reset@hook`. The renderer collects those lines and loads
   the union in its own preamble (#781); a load *inside* the figure
   float is the bug that multiplied node spacing in this project's own
   book. `docs/TIKZ-STYLE.md` has the detail.

   ```bash
   kpsewhich tikz.sty
   pdflatex probe.tex   # \documentclass{article}\usepackage{tikz} + \input{figures/flow}
   ```

8. **Read what the geometry says.** `python -m chitragupta.review figure
   <draft>` reports what each figure's own geometry shows: overlaps,
   protrusions, a library loaded by hand. It is a review aid, never a
   gate. Read each finding, fix the ones that are real defects against
   the pre-flight list, and leave the rest. It measures only nodes the
   source names, so name every node you draw.

9. **Look at it in the real render.** The probe is a bare article class
   under `pdflatex`; the pipeline's own pdf is LuaLaTeX at the draft's
   body font, where labels wrap and the gaps between layers close
   differently, so a figure that passes the probe can still print with
   a hyphenated label or an arrow through a zone title. Once the draft
   carries the figure's marker, render it and look at the page that
   holds the figure:

   ```bash
   python -m chitragupta.draft render <draft> --format pdf
   pdftoppm -png -r 100 -f <page> -l <page> -singlefile <the rendered pdf> page
   ```

   Rendering writes only under `content/rendered/`, never the draft.
   Check the page against the same pre-flight list, fix the layout
   (wider boxes, more room, a moved edge, never a smaller scale), and
   render again until it reads cleanly. Edit only below the house style
   block: a change inside it makes the render warn that the block was
   hand-edited. If the marker is not in the draft yet, tell the caller
   to make this check right after its own render. If the render reports
   `[missing-binary]`, `pdftoppm` is not installed, or you cannot view
   an image, skip the look: keep the probe and `review figure` results,
   and say so in chat. The look is a check, never a condition of
   keeping the figure; `chitragupta install os-deps` brings the tools.

10. **Return.** Tell the caller the two paths, whether the probe
    passed and whether you checked the rendered page. The caller places
    the marker and the caption in its own shape, then gates and renders
    the draft. None of that is this skill's.

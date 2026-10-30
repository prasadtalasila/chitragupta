# figure-drawer: reference

Read a section only when the procedure in `SKILL.md` points at it. Each
one condenses a section of `docs/TIKZ-STYLE.md`, which is the authority:
where the two ever disagree, that document wins and this file is the
bug.

## 1. Choosing a metaphor

Decide what the figure argues first: `patterns.md`, beside this file,
routes a pattern (a bottleneck, a lifecycle, a trust boundary, a
comparison) to a layout. Each layout then has one file under `layouts/`
with its anti-patterns and the node count, edge count, width, height
and slack a typical figure of it has.

Every scaffold's first line names its layout, `% cg-layout: pipeline`.
Keep that line when you copy a scaffold, and change it if you change the
layout: `figure check` reads it to print your figure's numbers beside
that layout's (see `check.md`).

The scaffolds in `assets/tikz/`, from `assets/tikz/README.md` (which
wins if the two disagree):

| File | Metaphor | Reach for it when |
| --- | --- | --- |
| `pipeline.tex` | Pipeline | the thing is a sequence and the question is "what happens next" |
| `map.tex` | Map | the point is how things compare on two named axes, not how they connect |
| `layered-stack.tex` | Layered stack | the question is what is allowed to depend on what |
| `control-loop.tex` | Control loop | the whole claim is that the cycle closes |
| `branching-tree.tex` | Branching tree | one thing divides into cases and no case rejoins another |
| `hub-and-spoke-network.tex` | Hub-and-spoke network | everything going through one place *is* the claim |
| `zoned-spine.tex` | Zoned spine | one storyline, with parallel commentaries on points along it |
| `state-machine.tex` | State machine | it is in one state at a time, and a state can recur, stay put or be sent back |
| `comparison.tex` | Comparison | two things made of the same parts, and the point is the part that differs |

The choices people get wrong:

- **Pipeline or control loop?** Does the last stage feed the first? If
  the cycle closing is the point, it is a loop. A pipeline with a retry
  arrow drawn on is still a pipeline; the retry is one back edge.
- **Pipeline or zoned spine?** A zoned spine is a pipeline with
  something commenting on points along it: which stages are
  deterministic, which are gated. If nothing comments on the path, it is
  a pipeline.
- **Branching tree or hub-and-spoke?** A tree divides and never rejoins.
  If the branches all route back through one centre, the centre is the
  claim and it is a hub.
- **Layered stack or zoned spine?** A stack answers "what may depend on
  what" and reads top to bottom. A spine answers "what happens, in
  order" and reads left to right.

Settle the width the figure will be printed at *before* choosing
(section 3): a hub-and-spoke needs horizontal room a single column of a
two-column paper does not have, and a layered stack degrades gracefully
into a narrow column.

Name every node you draw, `\node (a)` or `child { node (a) ... }`.
`python -m chitragupta.figure check` measures only named nodes, so a
picture that names nothing reports no overlap because nothing was
measurable, which reads exactly like a clean figure.

## 2. Panels

A figure that shows the same thing under two or three conditions is
**one figure with panels**: one marker, one `.tex`/`.txt` pair. Each
panel carries a drawn `(<letter>) <short title>` node, lettered by its
position in reading order (left to right, then top to bottom), so moving
a panel moves its letter with the position. Prose refers to the panel
by typing the letter after the figure reference.

A three-panel figure, relative placement throughout. It is the
example `docs/TIKZ-STYLE.md` carries, which
`tests/test_tikz_subcaptions.py` compiles:

```latex
\usetikzlibrary{positioning,fit}
\begin{tikzpicture}[thick,
                    box/.style={draw,align=center,
                                minimum width=17mm,minimum height=8mm}]
  \node[box] (senseA) {sensor};
  \node[box,below=6mm of senseA] (storeA) {store};
  \draw[->] (senseA) -- (storeA);
  \node[fit=(senseA)(storeA),draw=none] (panelA) {};
  \node[below=2mm of panelA] (labelA) {(a) polled};

  \node[box,right=12mm of senseA] (senseB) {sensor};
  \node[box,below=6mm of senseB] (storeB) {store};
  \draw[->] (senseB) -- (storeB);
  \node[fit=(senseB)(storeB),draw=none] (panelB) {};
  \node[below=2mm of panelB] (labelB) {(b) pushed};

  \node[box,right=12mm of senseB] (senseC) {sensor};
  \node[box,below=6mm of senseC] (storeC) {store};
  \draw[->] (senseC) -- (storeC);
  \node[fit=(senseC)(storeC),draw=none] (panelC) {};
  \node[below=2mm of panelC] (labelC) {(c) buffered};
\end{tikzpicture}
```

and its ASCII twin, with the same letters:

```text
  +--------+      +--------+      +--------+
  | sensor |      | sensor |      | sensor |
  +--------+      +--------+      +--------+
      |               |               |
      v               v               v
  +--------+      +--------+      +--------+
  | store  |      | store  |      | store  |
  +--------+      +--------+      +--------+
(a) polled     (b) pushed      (c) buffered
```

The `.txt` is the only form `md`, `html` and `docx` ever render, so
letters left out of it are letters three of the five formats never
show. Take each letter's four columns from the gap to the left of its
title rather than inserting them, or every later title slides off its
panel; the letters then overhang by four columns, which is intended and
keeps §10's ~70-column cap.

**When a row stops fitting, wrap into another row; never scale.** Three
panels of about 48mm each overflow an ordinary text block by 71.8pt, and
TeX only warns (`Overfull \hbox`). Four of the same panels as a
2x2 grid fit with no warning.

**Do not reach for `subcaption`, `subfig` or `subfigure`.** A figure
file can load its own TikZ library but never its own package
(`\usepackage` is preamble-only), and a thesis chapter's
fragment is `\input` into a thesis whose preamble this project never
sees. Drawn letters work in every genre and change no preamble.

## 3. Fit without scaling

Never wrap a figure in `\resizebox` or `\scalebox`, and never set
`scale=` on the picture. The scale lives in the draft that `\input`s the
figure, not in the figure file, which is why it is the rule that gets
broken. Measured on six hand-written figures in one acmart sigconf paper
(9pt body), each wrapped in `\resizebox{\textwidth}{!}{...}` (#1012):

| Figure | Natural width | Scale applied | Smallest type printed at |
| --- | --- | --- | --- |
| `architecture` | 462.8pt | 1.094 | 6.6pt |
| `rag-stages` | 548.9pt | 0.922 | **5.5pt** |
| `retrieval` | 519.5pt | 0.975 | 5.9pt |
| `coauthoring` | 520.8pt | 0.972 | 5.8pt |
| `prompt` | 425.6pt | 1.118 | 6.7pt |
| `revision` | 420.6pt | 1.180 | 7.1pt |

Six figures, six type sizes, none of them chosen. Laid out again to fit
506.3pt unscaled, every label printed at 8.97pt or above, and the floor
changed layouts, not just sizes: `rag-stages` went from two rows to
three, and `retrieval`'s dense route wrapped. Three of those redrawn
figures are `assets/tikz/exemplars/`, since laid out again to the
render's 453pt (#1050).

So, in order:

1. Settle the target width first. The scaffolds are laid out to the
   `article` class's 345pt text width; a thesis or a two-column paper
   differs.
2. Lay the figure out to that width.
3. `\input` it bare.
4. If it does not fit, change the layout: wrap a row, cut a gloss, drop
   a stage. A box with too many words needs fewer words, never smaller
   type. Nothing goes below `\normalsize`, the body size.

## 4. An annotated exemplar

`assets/tikz/exemplars/architecture.tex` is the house style at work.
Read it, but start your own figure from a scaffold, not from an
exemplar: the exemplars come close to the render's full 453pt text
width, wider than the scaffolds' 345pt, and carry one paper's content.

What its parts are for:

- **The house block, left byte-identical.** Everything between
  `% >>> chitragupta figure style v1 ... <<<` and
  `% >>> end chitragupta figure style <<<` is a verbatim copy of
  `assets/tikz/cg-figstyle.tex`. It travels inside the figure file
  because the renderer injects only `\usepackage{tikz}` and a thesis
  fragment is `\input` into a document that has never heard of this
  project. Every definition in it is idempotent, so N figures carrying N
  copies change nothing. Do not edit it; re-label nodes instead.
- **The spine, placed relatively.**

  ```latex
  \node[cgbox, text width=23mm] (bib) {\cglab{Curate}{.bib export + PDFs}};
  \node[cgbox, right=7mm of bib, text width=23mm] (sync) {\cglab{Corpus}{parse, ledger}};
  ```

  `\cglab{name}{gloss}` gives the two-tier label: a bold name over a
  muted gloss, both at body size. Every node is named, so
  `figure check` can measure it.
- **Node roles, not colours.** `cgbox`, `cgalt`, `cgkey` and `cgopt`
  mark what a node *is* (ordinary, generative, the gate, optional), and
  the palette follows from the role. Pick a role; never set a colour on
  a node by hand.
- **Zone cards, drawn behind everything.**

  ```latex
  \begin{scope}[on background layer]
    \node[cgzone=cgFlow, fit=(ibib)(bib)(isync)(sync)(enrich)] (z1) {};
  \end{scope}
  \cgzonelabel{z1}{cgFlow}{Deterministic ---\\no model is called}
  ```

  The card is a `fit` node on the background layer, so it never paints
  over a member, and re-wording a member widens the card instead of
  escaping it. The zone titles carry the figure's claim, which a flat
  version leaves to the caption. A title longer than its card breaks
  onto a second line (the picture sets `cgzonetitle/.append
  style={align=left}`) rather than running into the next card's title.
- **Step badges** (`\cgstep{1}{bib}{cgFlow}`) number the reading path,
  so the prose can say "step 3" and the reader finds it.
- **Edge tags and edge weights.** `cgedge` for the main path, `cgweak`
  for what happens off to the side, `cgback` for the one loop. A
  `cgtag` node on an edge names what crosses it. An edge alone on a
  node's side meets it at the side's middle; two edges on one side take
  a third of it each, which is why `draft` and `gate` name their
  `1/3` and `2/3` points as coordinates and place `review` and `pub`
  under the edges that reach them.

## 5. Looking at a source's figures

`python -m chitragupta.draft figures <citekey>` lists a synced paper's
figures and hands back a crop of each, for any citekey the draft already
cites. Seeing how a concept is conventionally drawn, and seeing several
versions of it, is legitimate input to a diagram you then draw yourself.
It is not a licence to reproduce one. The source image never enters the
draft, and a close redraw of any single one is the same violation, per
`docs/WRITING-STANDARDS.md` §10: the TikZ must be as original as the
ASCII, whichever notation it is drawn in. AGENTS.md states the boundary
in full.

## 6. Libraries and compiling

A malformed figure fails the *whole* pdf render, not just the figure.
`figure check` compiles it once with LuaLaTeX, the engine the pdf render
uses, in the render's fonts at 12pt, and reports `does-not-compile`
when a `tikzpicture` fails. Fix that first: until it compiles, the
rules that need the compiled geometry are listed as not measured. A bare
`\tikz` is not compiled at all, and its geometry rules are listed the
same way.

If the figure uses `positioning`, `matrix`, `fit` or `tree`, put its
`\usetikzlibrary` line at the top of `figures/<name>.tex`. Keep the line
in the figure file and write nothing else about loading: no clearing of
`\tikz@library@...@loaded`, and no saving or restoring of
`\tikz@node@reset@hook`. The renderer collects those lines and loads the
union in its own preamble (#781). A load *inside* the figure float is
the bug that multiplied node spacing in this project's own book.
`docs/TIKZ-STYLE.md` has the detail.

Before keeping the figure, read it against that document's pre-flight
defect list: occlusion, chaotic routing, illegible type, non-rectangular
protrusion, an overlong node, literal copying. No label goes below the
body size, and the figure is `\input` bare, never inside `\resizebox`.
If it does not fit, change the layout, not the scale (§3).

## 7. Looking at the render

`figure check` measures geometry. It cannot see a hyphenated label, or
an arrow through a zone title, in the page the reader gets. The
pipeline's own pdf is LuaLaTeX over the draft's whole document, with its
floats, captions and neighbouring text, where labels wrap and the gaps
between layers close differently.

`python -m chitragupta.figure look figures/<name>.tex` sets the figure
alone on the render's own page (12pt, its fonts, its text width),
cropped to the figure, as `<name>.look.png` at 300 dpi and
`<name>.look.pdf`, with a red line at the text width if the figure is
wider. Once the draft carries the figure's marker, `--draft <draft>`
renders the draft too and writes `<name>.page.png`, the page that holds
the figure. It writes only under `content/rendered/`, never the draft.

Open the PNGs and read them against the pre-flight list (§6). Fix the
layout (wider boxes, more room, a moved edge, never a smaller scale),
and look again until it reads cleanly. Edit only below the house style
block: a change inside it makes the render warn that the block was
hand-edited. If the marker is not in the draft yet, look at the figure
alone and tell the caller to look at its page after its own render,
which refreshes these pictures.

If `figure look` exits 2 for a missing tool (`lualatex`, `tikz.sty`,
`pdftoppm`, or `pandoc` with `--draft`), if the render reports
`[missing-binary]`, or if you cannot view an image, skip the look. Keep
the `figure check` result, and say so in chat. The look is a check,
never a condition of keeping the figure; `chitragupta install os-deps`
brings the tools.

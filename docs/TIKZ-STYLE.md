# 📐 TikZ figure style: layout, typography, and the pre-flight checklist

Status: **standard, not mechanically checked.** Written 2026-08-21. Updated
2026-08-24. A future review-layer aid
([FEATURE-ROADMAP.md](FEATURE-ROADMAP.md)'s D2) may check some of the binary
items below by compiling the figure; nothing here is gated today.

This is the TikZ-specific half of
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10's figure contract:
that section owns the two-form (TikZ + ASCII) pair, the marker syntax,
and originality. This document is what makes the TikZ half of the pair
good, before it is kept.

**Written for** whichever of `survey-writer`, `tutorial-writer`,
`thesis-chapter-writer` or `textbook-chapter-writer` is about to draw a
figure -- each links here from its own figure step. `deep-research`
does not draw §10 figures at all, so it has no reason to link here.

**Not covered here:** the two-form pair contract, the marker syntax and
originality, all of which stay in
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10; the ASCII form's own
7-bit alphabet and column limit, also §10.

## 🏗 Commit to a layout metaphor before you draw

TikZ figures out of this pipeline sprawl when nothing asks for a plan
before the first `\node` -- boxes placed near other boxes, arrows added
as needed. Committing to one metaphor before placing a node turns
"place these nine things" into a constrained problem, which is the
single change most likely to fix sprawl at its source. Each metaphor
maps onto a TikZ idiom to actually use:

| Metaphor | TikZ idiom |
| --- | --- |
| Pipeline | a chain, via the `positioning` library |
| Map | `matrix` |
| Layered stack | stacked `fit` layers |
| Control loop | cyclic edges with `bend` |
| Branching tree | `tree` |
| Hub-and-spoke network | a star |

(The metaphor list is PaperBanana's planner supplement, read and not
copied -- [INSPIRATION.md](INSPIRATION.md) carries the credit.)

**There is a starting file for every row of that table, in
`assets/tikz/`.** One per metaphor, named for it, each compiling on its
own and each reporting no binary finding from
`python -m chitragupta.review figure`. Copy the one whose metaphor fits
and re-label it; the point of the choice above is that it hands you a
file rather than a blank `tikzpicture`. `assets/` is copied into a
project by `chitragupta init`, so they are already beside a scaffolded
draft and there is nothing to download. `assets/tikz/README.md` says
what each one is for.

**Every scaffold places its nodes relative to one another, and none of
them writes a coordinate in millimetres.** That is the property to keep
when you edit one. A figure laid out in hand-computed absolute
millimetres cannot express "do not collide": re-wording one label, or
setting the figure at a different type size, re-opens every adjacency in
the picture at once and each of them has to be re-checked by eye.
Relative placement and `fit` layers make most of those collisions
impossible instead of merely detectable.

One departure to know about, recorded here rather than left to be
rediscovered: `assets/tikz/branching-tree.tex` uses `positioning`, not
the `tree` idiom the table names. `child` syntax spells a node's name
without a leading backslash, which is the one spelling `review figure`
recognises, so a tree drawn with it reports one node of seven and the
aid reads the six it cannot see as a tall empty band -- a protrusion
finding on a figure that has none. `tree` is still fine to use; just
confirm that one by compiling and looking, because the aid will not.

**Every idiom in that table needs a `\usetikzlibrary` line, and the
figure file has to carry it itself.** The renderer adds
`\usepackage{tikz}` to the preamble and nothing else
(`chitragupta/render_output/__init__.py`), so a picture that reaches for
`below=4mm of store` without loading `positioning` does not fall back --
it fails the whole render with a message that names neither the library
nor the figure:

```text
! Package PGF Math Error: Unknown operator `o' or `of' (in '4mm of a').
```

Put the load at the top of `figures/<name>.tex`, above the
`tikzpicture`:

```latex
\usetikzlibrary{positioning}
\begin{tikzpicture}[thick,x=1mm,y=1mm]
```

That works because the renderer emits `\input{figures/<name>.tex}` into
the body, and `\usetikzlibrary` is legal there -- inside a `figure`
float included. Both verified by compiling on this host.

Two things to know before you reach for one:

- **A missing name takes the whole call down.** `\usetikzlibrary{}` fails
  fatally on the comma list rather than skipping the name it cannot
  resolve, so one typo reads exactly like several missing packages. Probe
  a library by compiling a two-line document that loads it -- **not**
  with `kpsewhich tikzlibrary<name>.code.tex`, which only sees
  tikz-layer files and so misses every pgf-layer library (`arrows.meta`
  is `pgflibraryarrows.meta.code.tex`, and resolves fine).
- **`shapes.geometric`, not `shapes.geometry`.** The second is not a PGF
  library at all.

`texlive-pictures`, which `scripts/install_full_pipeline.sh` already
installs, ships all of these -- there is no extra package to add for any
of them.

## ✅ Check the drawn figure against this list

Concrete defects, not taste:

- **Occlusion and overlap** -- no two nodes' boxes intersect.
- **A `fill` erases everything under it, not just the line you aimed
  it at.** Filling a label white and drawing it last is the standard
  way to make a line break at the text instead of striking through it,
  and it works -- but the fill is a rectangle the height of the whole
  node and the width of the whole label, and it paints out every
  arrowhead, border and rule that rectangle happens to cover. A one-line
  label 139mm wide, filled to interrupt one vertical arrow at *x*=24,
  also deleted an arrowhead and the top edge of a box at *x*=70: the
  edge rendered as a stub going nowhere and the box as three sides. Ask
  what else is in the band before reaching for `fill=white`, and note
  that shrinking the band rarely rescues it -- `inner ysep=0pt` bought
  0.06mm in that case, and breaking the label over two lines makes the
  band *taller*, not narrower.
- **One arrow is one `\draw`.** Two colinear segments that meet, each
  carrying `->`, render as an arrowhead where they join as well as at
  the end -- a second head pointing at nothing in the middle of the
  line. If a line needs to be built in pieces, put the `->` on the last
  piece only.
- **Chaotic routing** -- arrows should not cross unnecessarily or form
  spaghetti loops. Left off the mechanical checks that may eventually
  exist; a bad approximation of "does this route look chaotic" would be
  worse than not checking it at all, so this one stays a human
  judgement.
- **Illegible or inconsistent type, and low contrast** -- one font size
  per role, held consistent across every node in the figure. See "Type
  and line weight" below for what size that should actually be.
- **Inefficient non-rectangular composition** -- LaTeX treats a figure
  as a rectangular box, so anything protruding above the main block
  forces the surrounding text to wrap around the highest point, wasting
  vertical space. Keep the picture's bounding box close to the union of
  its node boxes.
- **Conciseness** -- a node whose text runs past 15 words is too long
  for a box; cut it or split the node. Shrinking the font to fit more
  words in is not a fix -- see "Type and line weight" below.
- **Literal copying** -- a box-ified copy-paste of prose, with no
  visual abstraction, is not a figure. This is
  [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10's originality rule
  wearing a different hat, and it matters more than it looks: a figure
  can launder borrowed wording past every detector in
  [PLAGIARISM.md](PLAGIARISM.md), because a citekey is already kept out
  of figure files and the gate does not follow `\input`.

## 🔤 Type and line weight

Two conventions, both about a figure looking like a native part of the
document rather than something pasted in:

- **Node text matches the document's own font size.** Don't shrink a
  node's label with `\footnotesize`, `\scriptsize` or similar to cram
  more words into a box -- that is a symptom of the conciseness defect
  above, not a fix for it. A figure whose labels run smaller than the
  surrounding paragraph reads as an afterthought.
- **Lines are distinctly thicker than TikZ's own default.**
  `\pgflinewidth` defaults to 0.4pt, TikZ's `thin` key -- verified with
  `\typeout{\the\pgflinewidth}` on this host. Draw node borders and
  arrows at `thick` (0.8pt, double the default, same probe) instead --
  a figure left at the bare default reads as faint next to a document's
  normal text weight. Set it as a picture option, not a restated style:
  `\begin{tikzpicture}[thick]`. **Do not** reach for
  `\tikzset{every node/.style={thick}}` to do this -- `/.style=`
  *replaces* whatever `every node` already held, so a figure with its
  own node style (`draw`, `circle`, a fill colour) silently loses all of
  it the moment this line runs after that one. Verified on this host: a
  circular node's bounding box, forced through exactly that sequence,
  came out identical to a plain undecorated node's -- the circle and the
  border were both gone. `\begin{tikzpicture}[thick]` cannot clobber
  anything, because it never touches `every node` at all.

## 🎨 Free once you are in TikZ

Style keys unavailable to a raster path, worth using once the layout
and type are settled: zone fills at 10-15% opacity via the
`backgrounds` layer, dashed lines for auxiliary flow against solid for
forward flow, sans-serif labels against serif-italic maths.

## 🚫 Nothing here is a gate

This is a checklist an author checks a figure against, not something
enforced mechanically today.

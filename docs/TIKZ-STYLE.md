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

**Name every node you draw**, in whichever idiom. `review figure`
measures a node's geometry only where the source gives it an explicit
`(name)`, so a picture that names nothing reports no overlap and no
protrusion because nothing was measurable -- which reads exactly like a
clean figure and is not one. Both spellings count: `\node (a)` and
`child { node (a) ... }`.

One thing the `tree` idiom costs, since it is not visible in the output:
`child` draws its edges internally rather than as `\draw` statements, so
the edge list `review figure` reports for such a figure is empty rather
than short. Confirm a tree's wiring from the source's own nesting.

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

## 🔠 Panels in one figure, and the letters they need

A figure that shows the same thing under two or three conditions is one
figure with panels, not two or three figures. **However many panels it
has, it stays one figure, one `figure:` marker and one `.tex`/`.txt`
pair** -- one marker per panel would give you separate floats with
separate numbers, which is a row of figures rather than a panelled one.
Nothing here is specific to two: letter as far as the figure goes.

**Every panel carries a label node reading `(<letter>) <short title>`,
and the letter is the panel's position in reading order** -- `(a)` for
the first panel, `(b)` for the second, `(c)` for the third, and on
through the alphabet. Reading order is left to right, then top to
bottom, so it is the panel's *place in the picture* that decides its
letter, not the order you happened to draw the nodes in: move a panel
and its letter moves with the position, not with the panel. Draw the
label as an ordinary node under the panel it names; a panel with a bold
title and no letter cannot be pointed at from the prose, which is what
the letter is for. Prose then refers to `Figure~\ref{fig:x}(b)` for the
second panel, with the letter typed, since these letters are drawn
rather than counted by LaTeX.

**Put the same letters in the ASCII twin.** Every format except
`tex`/`pdf` -- `md`, `html` and `docx` alike -- renders the `.txt` and
never sees the picture, so for three of the five formats the ASCII form
is the only place the sub-captions exist. Letter it by taking the four
columns from the gap to the *left* of each title rather than by
inserting them, or every title after the first slides off the panel it
labels; the letters then overhang their panels by four columns, which
is the intended look and keeps §10's ~70-column cap intact.

**When a row stops fitting, wrap into another row -- never scale the
picture.** Three panels of about 48mm each overflow an ordinary text
block by 71.8pt, and pdflatex only *warns*: `Overfull \hbox`, in a log
nobody reads, with the figure quietly in the margin. Four of the same
panels as a 2x2 grid fit with no warning at all. Reaching for
`\resizebox` or `scale=` instead would shrink the node text below the
document's own size, which "Type and line weight" below forbids for
exactly this reason.

**Where the figure is captioned, write the caption in the draft, not in
the figure file.** Issue 411 moved that half out of `TikZ style`'s reach:
a Markdown draft writes its caption directly below the `figure:` marker
(WRITING-STANDARDS.md §10), and the renderer -- not the figure file --
wraps the marker in a `figure` float with `\caption`/`\label`, so LaTeX's
own counter numbers it. The figure file itself stays a bare
`tikzpicture` fragment, same shape as `assets/tikz/`'s own scaffolds --
copying one is no longer a step of wrapping it in a float by hand.

`thesis-chapter-writer`'s `.tex` fragment keeps the older shape, because
it carries no marker for the renderer to wrap: it hand-authors its own
`\begin{figure}...\caption{}...\label{fig:<id>}...\end{figure}` around
the inline `\input`. The one change there too: never write
`\renewcommand{\thefigure}{N.M}`. The `figure` counter it would override
is exactly what makes `\ref` agree with the consuming thesis's own
numbering; a hand-typed number is wrong the moment that thesis renumbers
a chapter, which is the defect issue 411 exists to remove.

**Do not reach for `subcaption`, `subfig` or `subfigure`.** The package
is installed on a typical TeX stack, so this is a choice rather than a
limit. `\usetikzlibrary` is legal in the document body and
`\usepackage` is not (`! LaTeX Error: Can be used only in preamble.`),
so a figure file can load its own TikZ library but never its own
package -- and the preamble that would have to load it is not always
ours. `thesis-chapter-writer`'s fragment is `\input` into the user's own
thesis, whose preamble we never see, so a figure needing `subcaption`
compiles here and fails there. Drawn letters work in every genre and
change no preamble. The whole cost is `\subref` and automatic "Figure 1a"
numbering, which is one typed letter per reference.

**Record the convention, don't re-decide it.** Which letters a venue
wants -- `(a)`, `(i)`, `A`, or titles alone -- is a house-style decision
in [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §8's sense, and belongs
in the dossier's `scope.md` beside the dialect. `draft-reviser` reads
that file before every edit; a convention agreed in chat is gone by the
next session.

A three-panel figure, relative placement throughout, verified on this
host -- it compiles, every node it names comes back measured, and
`python -m chitragupta.review figure` reports nothing:

```latex
\usetikzlibrary{positioning,fit}
\begin{figure}
\centering
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
\caption{One reading path under three delivery modes.}
\label{fig:delivery-modes}
\end{figure}
```

`tests/test_tikz_subcaptions.py` reads that example out of this file and
compiles it, so it cannot drift into something that no longer works.
The empty `fit` nodes are what give each panel an extent to hang its
label under; they are grouping boxes, which `review figure` excludes
from its overlap check by design, and any other way of finding the same
point is equally fine. What the rule asks for is the label and its
letter.

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
  piece only. This one *is* mechanically checked, where the pieces meet
  at a bare coordinate: chaining head-to-tail through a **named** node
  is how a pipeline is normally drawn and is not a defect, because TikZ
  clips each path at the node's boundary so the head points at the node
  rather than at empty space.
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
- **A distinction carried by colour alone** -- if the only thing
  separating two node classes, two arrow kinds or two zones is their
  colour, the distinction **does not exist for most of your readers**.
  Not principally for the usual accessibility reason, though that holds
  too: in this pipeline the figure has an
  [ASCII twin](WRITING-STANDARDS.md#-every-figure-has-two-forms) in a
  7-bit alphabet, and `md`, `docx` and `html` render *only that form*.
  So colour-only meaning is information the Markdown reader is
  structurally incapable of receiving, and nothing warns you -- both
  files exist, both render, and the two quietly say different things.
  **Carry every distinction redundantly**: shape, line style (solid
  against dashed), border weight, or an explicit label. Then colour is
  what it should be, an accent on a distinction already legible without
  it. The test is quick -- read the `.txt` twin and ask whether the
  point still arrives.
  **There is a second reader with the same problem, and the `.txt` twin
  does not stand in for them.** A thesis printed in black and white
  renders the *TikZ* form, greyscaled -- so two fills that differ in hue
  but not in lightness merge into one shade there, while the ASCII form
  is fine. The twin is not a mono preview of the picture; the two
  failures are independent, and passing the `.txt` test says nothing
  about the printed one.
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

**Two of those three are colour-free, and that is why they are the ones
to reach for.** Dashed-against-solid and a font-family change both
survive into the ASCII twin's alphabet, or can be annotated there;
a fill opacity cannot. The checklist above states the rule -- no
distinction carried by colour alone -- and this is the practical
consequence: **prefer the encodings that survive the round trip**, and
treat a zone fill as an accent on grouping the layout already makes
obvious, never as the thing that establishes it.

There is no house palette here, deliberately. A figure sets in the
consuming document's own colours as often as not, and a palette this
project could not enforce across a thesis it never sees would be advice
pretending to be a standard. What *is* stated is the constraint that
survives every venue: the figure has to work in one colour.

## 📏 Draw for the width it will be printed at

The six layout metaphors have no width dimension, and a figure drawn
without one in mind is a figure whose type size is decided by accident.
A single-column figure in a two-column paper sets at roughly half a page
width; the same picture dropped into a thesis sets at nearly double
that. **Nothing in the picture changes -- but the type does**, because
`scale=` and the consuming document's own width between them decide the
final physical size of every label.

So settle the target width *before* choosing a metaphor: a
hub-and-spoke needs horizontal room a single column does not have, and
is the wrong metaphor there however well it fits the content. A layered
stack degrades gracefully to a narrow column; a wide map does not.

**No venue table is bundled here, deliberately.** Column widths are
per-publisher, differ between initial and revised submission, and go
stale -- a table checked into this repository would be read as current
long after it stopped being. If you keep one, keep it the way a
maintained one is kept: a date it was accessed, a source URL per entry,
and the standing caveat that **a passing check is not compliance** --
re-read the publisher's live page before you submit.

## 🧿 Rules that are not universal

Figure guidance is mostly written for raster images, and several rules
that sound authoritative do not transfer to a TikZ picture at all.
Named here so nobody spends an afternoon satisfying one:

- **"Line art must be 600 or 1000 dpi."** A TikZ figure is vector and
  has **no DPI**. There is nothing to set and nothing to check. The
  requirement that *does* transfer is physical width, above.
- **"Convert everything to CMYK / everything to RGB."** A colour-space
  question about exported raster assets. It reaches a `\input`-ed TikZ
  picture only through whatever the consuming document does at export,
  which this pipeline does not control and should not pretend to.
- **"Make the figure bigger so the text is readable."** Backwards.
  Enlarging the picture enlarges the type *and everything else*, so it
  overflows the column and gets scaled back down. Type size at final
  scale is the quantity that matters, and `\footnotesize` inside a
  picture that is then scaled to 0.8 is the actual defect.
- **"A colourblind-safe palette makes the figure accessible."**
  Necessary and not sufficient here. Two readers of a draft from this
  pipeline receive **no colour whatever** -- anyone reading the `md`,
  `docx` or `html` render, which shows only the ASCII twin, and anyone
  reading the PDF in black and white. Working in one colour is the
  binding constraint; a safe palette is what you do afterwards.
- **"A vector figure is resolution-independent, so size does not
  matter."** True of fidelity, false of legibility, and the second is
  what a reader notices.

## 🚫 Nothing here is a gate

This is a checklist an author checks a figure against, not something
enforced mechanically today.

`python -m chitragupta.review figure` reaches the part of it that
geometry can decide, and it is a **user-driven aid**: a person runs it
over a finished figure, it exits 0 whatever it finds, and nothing
downstream blocks on it. Three things follow, and they are the ones an
author gets wrong:

- **It measures; it never places.** TikZ computes the layout, and the
  aid compiles the figure and reads back where things actually landed.
  So the fix for a finding is to change what you asked TikZ for -- a
  `sibling distance`, a `row sep`, a different library -- and never to
  nudge a coordinate until the number moves. `assets/tikz/` is the
  starting point for exactly that, and none of its six scaffolds writes
  a coordinate at all.
- **Its thresholds are the checker's, not this document's.** "An empty
  band worth more than a third of the height" is a number chosen so
  ordinary layouts pass; it is not a rule from the list above. It does
  shape what passes -- a two-row diagram spread out generously trips it
  with nothing wrong -- so when a finding and your own eyes disagree,
  the eyes win and the figure stays.
- **A clean report is not a checked figure -- and the report now says
  which it is.** The geometry checks measure only nodes the source
  names, so a picture that names none has nothing to measure. That used
  to print as `No layout findings`, identical to a figure where every
  check ran and found nothing; it now prints as its own finding, with
  the declared names that did not come back listed beside it. Name the
  nodes you draw, in whichever idiom -- `\node (a)` and
  `child { node (a) ... }` both count.

[REVIEW.md](REVIEW.md) has the aid among the other five;
[CLI.md](CLI.md#-chitragupta-review-figure) has its flags and the full
statement of the boundary.

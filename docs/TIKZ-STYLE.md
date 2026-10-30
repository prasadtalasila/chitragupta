# 📐 TikZ figure style: layout, typography, and the pre-flight checklist

Status: **standard, not mechanically checked.** Written 2026-08-21. Updated
2026-10-05 (#1012: the house figure-style block, the type floor, the zoned
spine). A future review-layer aid
([FEATURE-ROADMAP.md](FEATURE-ROADMAP.md)'s D2) may check some of the binary
items below by compiling the figure; nothing here is gated today.

This is the TikZ-specific half of
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10's figure contract:
that section owns the two-form (TikZ + ASCII) pair, the marker syntax,
and originality. This document is what makes the TikZ half of the pair
good, before it is kept.

**Written for** the `figure-drawer` skill, which `survey-writer`,
`tutorial-writer`, `thesis-chapter-writer` and `textbook-chapter-writer`
hand a figure to, and for anyone drawing one by hand.
[FIGURE-DRAWER.md](FIGURE-DRAWER.md) says how the skill applies this
document. `deep-research` does not draw §10 figures at all, so it has no
reason to link here.

**Not covered here:** the two-form pair contract, the marker syntax and
originality, all of which stay in
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10; the ASCII form's own
7-bit alphabet and column limit, also §10.

## 🏗 Commit to a layout metaphor before you draw

TikZ figures out of this pipeline sprawl when nothing asks for a plan
before the first `\node`: boxes placed near other boxes, arrows added
as needed. Committing to one metaphor before placing a node turns
"place these nine things" into a constrained problem, which is the
single change most likely to fix sprawl at its source. Each metaphor
maps onto a TikZ idiom to use:

| Metaphor | TikZ idiom |
| --- | --- |
| Pipeline | a chain, via the `positioning` library |
| Map | `matrix` |
| Layered stack | stacked `fit` layers |
| Control loop | cyclic edges with `bend` |
| Branching tree | `tree` |
| Hub-and-spoke network | a star |
| Zoned spine | `fit` plus `backgrounds` |
| State machine | circles (`cgstate`) with `bend` and `loop` |
| Comparison | two `fit` panels, matched parts on shared rows |
| Sequence | thin lifeline nodes, with level messages between them |

(The first six are PaperBanana's planner supplement, read and not
copied; [INSPIRATION.md](INSPIRATION.md) carries the credit.)

**The zoned spine** is one left-to-right path that carries the argument,
with each zone card a tinted region behind a group of members and its
title outside the card's top-left corner. Reach for it when the figure
has one storyline and several parallel commentaries on points along it.
The card is a `fit` node drawn `on background layer`, so it never paints
over a member and re-wording a member widens the card instead of
escaping it. If nothing comments on the path, it is a pipeline.

**The comparison** is two lettered panels side by side, made of the
same parts, with each part on the same row as its match. Reach for it
for a before and an after, or two approaches to one job, where the point
is the part that differs: that part is the `cgkey`, and a part one side
lacks keeps its row as `cgnone`. Panel (b)'s first part sets its
column, and every other part is placed `at (<column> |- <match>)`
rather than beside or below a neighbour, so re-wording a part cannot
move it off its match's row. Nothing is drawn
between the panels; if the two sides share a pair of named axes instead,
it is a map.

**The sequence** is parties side by side with time running down the
page, and messages passing between them. Reach for it for a protocol, a
handshake or a request and its replies, where the order of the
exchanges is the claim. Each party hangs a lifeline: a thin, undrawn
node with a dotted line down its middle, so every message is a
connector between two lifelines that `figure check` measures. Each
message is level, drawn at a named moment (`(a-l.east |- t1) --
(b-l.west |- t1)`), and a reply is dashed. `c4-attach` and `c5-transit`
are not evaluated for it (see below). If each party only hands work on
to the next and nothing comes back, it is a pipeline.

**There is a starting file for every row of that table, in
`assets/tikz/`.** One per metaphor, named for it, each compiling on its
own and each reporting no binary finding from
`python -m chitragupta.review figure`. Copy the one whose metaphor fits
and re-label it; the choice above exists to hand you a file rather than
a blank `tikzpicture`. `assets/` is copied into a
project by `chitragupta init`, so they are already beside a scaffolded
draft and there is nothing to download. `assets/tikz/README.md` says
what each one is for.

**Choose the pattern before the layout.** What a figure argues (a
bottleneck, a lifecycle, a trust boundary, a comparison) is not the same
choice as how it is laid out, and several patterns share one layout.
The `figure-drawer` skill's
`.claude/skills/figure-drawer/references/patterns.md` routes a pattern
to the nearest layout, and each layout has one reference file,
`.claude/skills/figure-drawer/references/layouts/<layout>.md` (the
layout's name as its scaffold spells it), with its anti-patterns and the
reference ranges measured from its scaffold and exemplars.
A new pattern never adds a layout; only a new way of placing nodes does.

**Every scaffold places its nodes relative to one another, and none of
them places a node at a coordinate in millimetres.** That is the property
to keep when you edit one. A figure laid out in hand-computed absolute
millimetres cannot express "do not collide": re-wording one label, or
setting the figure at a different type size, re-opens every adjacency in
the picture at once and each of them has to be re-checked by eye.
Relative placement and `fit` layers make most of those collisions
impossible, not merely detectable.

**The millimetre rule governs composition, not objects.** Every node in
a figure is placed relative to another node, and that does not change.
Inside a `pic` definition, explicit millimetre coordinates are correct
and expected: a `pic` is a fixed object drawn once, whose internal
geometry does not reflow when a sibling's label changes. The boundary
is the `pic`, not the authoring method: a shape generated by a
derivation gets the same carve-out as a hand-drawn one. Hand-placing a
whole figure is still the defect the rule exists to prevent.

**Name every node you draw**, in whichever idiom. `review figure` measures a
node's geometry only where the source gives it an explicit `(name)`, so a
picture that names nothing reports no overlap and no protrusion because nothing
was measurable. That output reads exactly like a clean figure, but the figure
was never checked. Both spellings count: `\node (a)` and `child { node (a) ... }`.
That includes the well a `pic` is drawn into: draw a `pic` only `at` a
named `cgwell` (see [House shapes](#-house-shapes-and-the-well-they-sit-in)).

The `tree` idiom has one cost that is not visible in the output:
`child` draws its edges internally rather than as `\draw` statements, so
the edge list `review figure` reports for such a figure is empty rather
than short. Confirm a tree's wiring from the source's own nesting.

**Every idiom in that table needs a `\usetikzlibrary` line, and the
figure file carries it at the top, above the `tikzpicture`:**

```latex
\usetikzlibrary{positioning}
\begin{tikzpicture}[thick,x=1mm,y=1mm]
```

**The renderer collects those lines and loads the union in the preamble**
(`chitragupta/render_output/_tikz_libraries.py`, #781), so by the time
your figure is `\input` the library is already there and your own line is
a no-op. Keep the line anyway: it is what lets the same file compile in
the two documents this pipeline does not write, which are
`thesis-chapter-writer`'s fragment inside a user's own thesis and the
minimal probe document [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10
tells you to build around one figure. Without any load at all, a picture
that reaches for `below=4mm of store` does not fall back; it fails the
whole render with a message that names neither the library nor the
figure:

```text
! Package PGF Math Error: Unknown operator `o' or `of' (in '4mm of a').
```

**Write nothing else about loading.** No clearing of
`\tikz@library@<name>@loaded`, no saving or restoring of
`\tikz@node@reset@hook`, no `\ifdefined` guard around the load. Those
workarounds exist in older figure files and they are the bug, not the
fix. `\usetikzlibrary` is legal in the document body, but a figure file
is `\input` *inside a `figure` float*, and a float is a group: the load
defines the library's macros **locally** while setting the loaded flag
**globally**, so the next float skips the load and finds no macros.
Clearing the flag to force a reload is worse: `positioning` appends its
placement transform to a **global** hook on every load, so the Nth figure
shifts every node N times. Measured on a three-float document: 71.26pt,
then 128.17pt, then 185.07pt, with `pdflatex` exiting 0 and nothing but
`Overfull \hbox` in the log. That is how figures that fit in their
single-chapter PDF spilled off the page of this project's own assembled
book. `python -m chitragupta.review figure` reports one as
`loads-library-by-hand`.

**A load while TeX is setting a line prints as blank width (#1046).**
A library file's own line ends are spaces. Load it where the figure is
set in a box (`\sbox`, `\hbox`, `\resizebox`), inline in running text,
or as the body of a `standalone` preview, which boxes its content, and
those spaces become glue ahead of the picture: 135pt for the house
line on the render's page (12pt, LuaLaTeX), about 30% of its 453pt text
width, and 147pt with `matrix` or `trees` added. Loaded in the
preamble, the same spaces fall in vertical mode and are dropped. So is
a load at the top of a `figure` float, which is why the renderer's
figures and `review figure` never show it. Ending the figure's line
with `%` or `\ignorespaces` does not help, since the spaces come from
inside the library files. The fix is the same hoist: a document that
sets a figure in a box loads the figure's libraries in its preamble,
as the documents `figure check` and `figure look` compile do.
`tests/test_figure_stray_width.py` pins the in-box half on every
scaffold, and `figure check`'s `size-stray` the preloaded one.

Before you reach for a library:

- **A missing name takes the whole call down.** `\usetikzlibrary{}` fails
  fatally on the comma list rather than skipping the name it cannot
  resolve, so one typo reads exactly like several missing packages. Probe
  a library by compiling a two-line document that loads it, **not**
  with `kpsewhich tikzlibrary<name>.code.tex`, which only sees
  tikz-layer files and so misses every pgf-layer library (`arrows.meta`
  is `pgflibraryarrows.meta.code.tex`, and resolves fine).
- **`shapes.geometric`, not `shapes.geometry`.** The second is not a PGF
  library at all.

`texlive-pictures`, which `scripts/install_full_pipeline.sh` already
installs, ships all of these; there is no extra package to add for any
of them.

## 🔠 Panels in one figure, and the letters they need

A figure that shows the same thing under two or three conditions is one
figure with panels, not two or three figures. **However many panels it
has, it stays one figure, one `figure:` marker and one `.tex`/`.txt`
pair**. One marker per panel would give you separate floats with
separate numbers, which is a row of figures rather than a panelled one.
Nothing here is specific to two: letter as far as the figure goes.

**Every panel carries a label node reading `(<letter>) <short title>`,
and the letter is the panel's position in reading order**: `(a)` for
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
`tex`/`pdf` (`md`, `html` and `docx` alike) renders the `.txt` and
never sees the picture, so for three of the five formats the ASCII form
is the only place the sub-captions exist. Letter it by taking the four
columns from the gap to the *left* of each title rather than by
inserting them, or every title after the first slides off the panel it
labels; the letters then overhang their panels by four columns, which
is the intended look and keeps §10's ~70-column cap intact.

**When a row stops fitting, wrap into another row; never scale the
picture.** Three panels of about 48mm each overflow an ordinary text
block by 71.8pt, and pdflatex only *warns*: `Overfull \hbox`, in a log
nobody reads, with the figure in the margin. Four of the same
panels as a 2x2 grid fit with no warning at all. Reaching for
`\resizebox` or `scale=` instead would shrink the node text below the
document's own size, which "Type and line weight" below forbids for
exactly this reason.

**Where the figure is captioned, write the caption in the draft, not in
the figure file.** Issue 411 moved that half out of `TikZ style`'s reach:
a Markdown draft writes its caption directly below the `figure:` marker
(WRITING-STANDARDS.md §10), and the renderer, not the figure file,
wraps the marker in a `figure` float with `\caption`/`\label`, so LaTeX's
own counter numbers it. The figure file itself stays a bare
`tikzpicture` fragment, same shape as `assets/tikz/`'s own scaffolds,
and copying one no longer includes wrapping it in a float by hand.

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
package, and the preamble that would have to load it is not always
ours. `thesis-chapter-writer`'s fragment is `\input` into the user's own
thesis, whose preamble we never see, so a figure needing `subcaption`
compiles here and fails there. Drawn letters work in every genre and
change no preamble. The whole cost is `\subref` and automatic "Figure 1a"
numbering, which is one typed letter per reference.

**Record the convention, don't re-decide it.** Which letters a venue
wants (`(a)`, `(i)`, `A`, or titles alone) is a house-style decision
in [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §8's sense, and belongs
in the dossier's `scope.md` beside the dialect. `draft-reviser` reads
that file before every edit; a convention agreed in chat is gone by the
next session.

A three-panel figure, relative placement throughout, verified on this
host: it compiles, every node it names comes back measured, and
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

- **Occlusion and overlap:** no two nodes' boxes intersect.
- **A `fill` erases everything under it, not just the line you aimed
  it at.** Filling a label white and drawing it last is the standard
  way to make a line break at the text instead of striking through it,
  and it works, but the fill is a rectangle the height of the whole
  node and the width of the whole label, and it paints out every
  arrowhead, border and rule that rectangle happens to cover. A one-line
  label 139mm wide, filled to interrupt one vertical arrow at *x*=24,
  also deleted an arrowhead and the top edge of a box at *x*=70: the
  edge rendered as a stub going nowhere and the box as three sides. Ask
  what else is in the band before reaching for `fill=white`, and note
  that shrinking the band rarely rescues it: `inner ysep=0pt` bought
  0.06mm in that case, and breaking the label over two lines makes the
  band *taller*, not narrower.
- **One arrow is one `\draw`.** Two colinear segments that meet, each
  carrying `->`, render as an arrowhead where they join as well as at
  the end, a second head pointing at nothing in the middle of the
  line. If a line needs to be built in pieces, put the `->` on the last
  piece only. This one *is* mechanically checked, where the pieces meet
  at a bare coordinate: chaining head-to-tail through a **named** node
  is how a pipeline is normally drawn and is not a defect, because TikZ
  clips each path at the node's boundary so the head points at the node
  rather than at empty space.
- **Chaotic routing:** arrows should not cross unnecessarily or form
  spaghetti loops. Left off the mechanical checks that may eventually
  exist; a bad approximation of "does this route look chaotic" would be
  worse than not checking it at all, so this one stays a human
  judgement.
- **Illegible or inconsistent type, and low contrast:** one font size
  per role, held consistent across every node in the figure. See "Type
  and line weight" below for what size that should be.
- **Inefficient non-rectangular composition:** LaTeX treats a figure
  as a rectangular box, so anything protruding above the main block
  forces the surrounding text to wrap around the highest point, wasting
  vertical space. Keep the picture's bounding box close to the union of
  its node boxes.
- **Conciseness:** a node whose text runs past 15 words is too long
  for a box; cut it or split the node. Shrinking the font to fit more
  words in is not a fix (see "Type and line weight" below).
- **The figure's main point resting on colour alone.** Colour is
  house-standard here and carries meaning freely (see "The house
  palette" below). What it may not do is carry the *whole* point on its
  own, because two readers get none of it: the ASCII twin is 7-bit, and
  `md`, `docx` and `html` render only that form; and a black-and-white
  print greyscales the TikZ form, where `cgFlow` and `cgAlt` land at
  similar lightness. Position, arrow direction and node labels should
  still deliver the argument; colour should make it fast. The test is
  quick: read the `.txt` twin and ask whether the point still arrives.
  A *secondary* distinction living only in colour is fine and expected.
- **Literal copying:** a box-ified copy-paste of prose, with no
  visual abstraction, is not a figure. This is
  [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10's originality rule
  applied to figures, and it matters more than it looks: a figure
  can launder borrowed wording past every detector in
  [PLAGIARISM.md](PLAGIARISM.md), because a citekey is already kept out
  of figure files and the gate does not follow `\input`.

## 🔤 Type and line weight

Two conventions, both about a figure looking like a native part of the
document rather than something pasted in:

- **Every word in a figure is set at the document's body size.** Nothing
  in a picture is smaller than the paragraph beside it, and nothing is
  larger either: node names and zone titles are told apart from glosses,
  tags and notes by weight and colour (bold names, muted glosses), not
  by size. Set the size explicitly as a picture option
  (`\begin{tikzpicture}[cg]` does it), rather than inheriting it, so a
  picture that lands inside a float, a table cell or a `\small` group
  does not quietly drop below it. House block v4 made this one size
  (#1054): v3 set names and titles a step up, at `\large\bfseries`,
  and the figures then read louder than the text around them, and a
  zone title grew past its zone into the next one.

  Shrinking type is never the fix for a box with too many words in it:
  that is the conciseness defect, and the fixes are fewer words or a
  wider box.
  Two exceptions, both automatic and both correct: a mathematical
  subscript or superscript set by TeX's own script style, and the
  `\caption`, which is the document's, not the figure's.
  `tests/test_tikz_scaffolds.py` holds every file in `assets/tikz/` to
  this by reading each glyph's printed size back out of the compiled
  PDF, not by reading the source, because the size that breaks it
  usually arrives from somewhere the figure file cannot see.
- **Lines are distinctly thicker than TikZ's own default.**
  `\pgflinewidth` defaults to 0.4pt, TikZ's `thin` key (verified with
  `\typeout{\the\pgflinewidth}` on this host). Draw node borders and
  arrows at `thick` (0.8pt, double the default, same probe) instead;
  a figure left at the bare default reads as faint next to a document's
  normal text weight. Set it as a picture option, not a restated style:
  `\begin{tikzpicture}[thick]`, which the house block's `[cg]` already
  includes. **Do not** reach for
  `\tikzset{every node/.style={thick}}` to do this: `/.style=`
  *replaces* whatever `every node` already held, so a figure with its
  own node style (`draw`, `circle`, a fill colour) silently loses all of
  it the moment this line runs after that one. Verified on this host: a
  circular node's bounding box, forced through exactly that sequence,
  came out identical to a plain undecorated node's; the circle and the
  border were both gone. `\begin{tikzpicture}[thick]` cannot clobber
  anything, because it never touches `every node` at all.

## 🎨 The house palette

**Figures here are in colour, and they use one palette.** Five named
colours with a role each, and four more that a zoned figure needs. A
figure that invents its own hues reads as imported from somewhere else,
which a house palette exists to prevent.

```latex
\definecolor{cgInk}{HTML}{1A1A1A}     % borders, labels, default strokes
\definecolor{cgFlow}{HTML}{0072B2}    % the primary path through the figure
\definecolor{cgAccent}{HTML}{D55E00}  % the one thing the figure is about
\definecolor{cgAlt}{HTML}{009E73}     % a second class of node or edge
\definecolor{cgAux}{HTML}{56B4E9}     % auxiliary, secondary, "also happens"
\definecolor{cgWarm}{HTML}{E69F00}    % a third zone
\definecolor{cgRose}{HTML}{CC79A7}    % a fourth zone
\definecolor{cgPaper}{HTML}{FAFAF8}   % card ground, one step off white
\definecolor{cgMute}{HTML}{8A8A8A}    % muted ink, as a name
```

(Inside `assets/tikz/cg-figstyle.tex` each of these lines ends its
`}` with a `%`, so the block sets no stray space; see "The house figure
style" below.)

**`cgWarm` and `cgRose` are one hue per zone.** They are Okabe-Ito's
remaining qualitative members, so the extension is the same palette
rather than a second one: a zoned figure needs one hue per zone, and five
roles do not stretch to six zones without reusing one, which reads as a
claim the figure is not making. **`cgMute` is a *named* grey** because
the house styles take a colour as an argument and paste it into a tint
(`fill=#1!11`): `cgInk!55` passed in becomes `cgInk!55!11`, which xcolor
rejects with "Undefined color". Every role that needs muted ink
therefore needs a name. `cgPaper` is the card ground, one step off white
for the same reason `cgInk` is not black.

The values are Okabe-Ito's colourblind-safe qualitative set (Okabe &
Ito, 2008), the usual choice for this purpose, and it costs nothing to
adopt. `cgInk` is a near-black rather than `black`, because a pure
black border next to body text set in the same ink reads heavier than
the text does.

**Each colour has a role.** Use `cgAccent` for one thing per figure: if
two things are accented, neither is. `cgFlow` carries the spine; `cgAux`
is for what happens off to the side, usually dashed as well as coloured.
`cgAlt` exists so a figure with two node classes does not have to reach
outside the palette.

**A palette name fills; a `Line` or `Text` name draws.** `fill=cgFlow!8`
is a zone wash that text still reads through; `fill=cgFlow` is a block of
solid blue with your label lost inside it. Between 6 and 12 is the band
the house block's cards and zones use. Strokes and coloured text do not
take the palette colour at all, because several hues are too light to be
seen as a line on their own tint (`cgWarm` on `cgWarm!12` is 1.9:1,
where WCAG 2 asks 3:1 of a line) and none but `cgFlow` reaches the
4.5:1 that text needs. So each hue, and `cgMute`, has two darker shades
mixed towards `cgInk`:

| Hue | Border, edge, rule | Coloured text |
| --- | --- | --- |
| `cgFlow` | `cgFlowLine` (100%) | `cgFlowText` (95%) |
| `cgAccent` | `cgAccentLine` (100%) | `cgAccentText` (75%) |
| `cgAlt` | `cgAltLine` (95%) | `cgAltText` (70%) |
| `cgAux` | `cgAuxLine` (75%) | `cgAuxText` (55%) |
| `cgWarm` | `cgWarmLine` (75%) | `cgWarmText` (55%) |
| `cgRose` | `cgRoseLine` (90%) | `cgRoseText` (65%) |
| `cgMute` | `cgMuteLine` (95%) | `cgMuteText` (70%) |

Each percentage is the share of the hue in the mix, and is the largest
multiple of 5 that clears the threshold over white, `cgPaper` and every
tint the block fills with, of any hue, since an edge can cross another
zone. `tests/test_figure_contrast.py` recomputes every one from the hex
values above, and fails a stroke or label in the block or a scaffold that
draws in a bare palette name. Every house style already draws this way,
so the rule only binds what you write yourself: `draw=cgAltLine`, not
`draw=cgAlt`; `text=cgAccentText`, not `text=cgAccent`. A style that
takes a colour argument (`cgzone=cgAlt`) takes the palette name and
finds the shade itself.

### 📎 The palette travels inside the figure

**The palette travels as part of the house block** (next section), which
every figure carries whole. Not in a
shared file the figure `\input`s, and not in a preamble: the
renderer injects `\usepackage{tikz}` and nothing else, and
`thesis-chapter-writer`'s fragment is `\input` directly into the user's
own thesis, which has never heard of this project. A figure that depends
on a colour defined elsewhere compiles here and fails there, which is
the worst of the two orders to fail in.

This is the same discipline the `\usetikzlibrary` line already follows,
for the same reason, and it means the definitions are duplicated across
figures on purpose. The ten scaffolds in `assets/tikz/` all carry the
block, so copying one gets it for free.

### 🧱 The house figure style

`assets/tikz/cg-figstyle.tex` is the palette grown into the rest of the
vocabulary a figure needs to look drawn rather than assembled, so a
figure stops re-deciding corner radius, rule weight, tint depth,
arrowhead and label structure from nothing each time:

| Group | Keys |
| --- | --- |
| Palette | the nine colours above, and the `Line` and `Text` shade of each hue and of `cgMute` |
| Picture default | `cg`: `thick`, round caps and joins, `font=\normalsize`, ink colour, `node distance=6mm` |
| Node roles | `cgbox` `cgalt` `cgaux` `cgwarm` `cgrose` `cgplain` `cgkey` `cgnone` `cgopt` |
| Shadow | `cgsoft` (on in every filled role) and `cgflat` (cancels it; `cgnone` and `cgopt` use it) |
| Zone card | `cgzone=<colour>` (3mm inner sep) and `\cgzonelabel{<fit node>}{<colour>}{<text>}` (1.5mm above the card) |
| States | `cgstate` (a circle, 18mm, bold name), `cgaccept` (double ring), `cgkeystate` (the accented state), `cgstart` (the initial arrow); pure TikZ, no `automata` library |
| Edges | `cgedge` `cgweak` `cgback` `cglead=<colour>` |
| Annotation | `cgtag` (a word beside an arrow, never on it), `cgnote` |
| Badges | `cgbadge=<colour>` and `\cgstep{<n>}{<node>}{<colour>}` |
| Legend | `cgswatch=<colour>`, `\cglegenditem{...}` |
| Label ramp | `\cglab{<name>}{<gloss>}` |
| Icon well | `cgwell`: a named, invisible, fixed-size node a `pic` is drawn into |

It also defines five house `pic`s, each drawn into a `cgwell`; see
[House shapes](#-house-shapes-and-the-well-they-sit-in).

**Its spacing is compact by default.** Two members of one zone sit 6mm
apart, which `cg`'s `node distance` gives you for `right=of`. Two zones
sit 8mm apart card to card, which is 14mm member to member once each
card's 3mm inner sep is counted; say that distance where a placement
crosses zones. Stacked zones need the lower card's title in the gap as
well, about 5mm more (`assets/tikz/layered-stack.tex` works the sum).
The type is not part of this: the floor in "Type and line weight" above
is what stops a compact figure becoming a squashed one.

**An edge tag sits beside its line.** `cgtag` is unfilled and placed
with `auto`, on the left of the direction of travel, about 1mm clear of
the segment; add `swap` to put it on the right. A tag filled over its
line breaks the line exactly where the eye is following it.

The block needs one library line, at the top of the figure with the
picture's own:

```latex
\usetikzlibrary{arrows.meta,positioning,fit,backgrounds,calc,shadows.blur}
```

All six ship with `texlive-pictures`. `shadows.blur` comes from the
`pgf-blur` package but is reached by `\usetikzlibrary`, not
`\usepackage`, which is what lets the soft shadow travel into a thesis
preamble this project never sees: a figure file cannot load a package.

**The block travels between its two marker comments, and
`python -m chitragupta figure sync` keeps it current.** The command
stamps the block into a figure file that lacks one, above its first
`\usetikzlibrary` or `tikzpicture` line, and replaces a block from an
older release with the installed one. Everything outside the markers
stays byte for byte as it was. With no paths it walks every
`content/drafts/**/figures/*.tex`; `--check` writes nothing and exits 1
if any file is not current. `chitragupta draft render` reports a stale
or missing block as a `[figure]` warning naming the command, and renders
anyway: it never rewrites a figure itself.

**Never edit inside the markers.** A style one figure needs goes in that
picture's own options, or in a `\tikzset` below the end marker. `figure
sync` recognises every block this project has released by its digest, so
a region that matches none of them was edited by hand. It leaves that
region alone and prints the diff against the house block, for a person
to move the edit out. A style that three or more figures need is a pull
request against `cg-figstyle.tex`, not a local override.

**Changing the block means a new version.** Bump the `v<N>` in its first
line and add that version's digest to
`assets/tikz/cg-figstyle.versions.toml`, never editing an existing line
there. `tests/test_figure_block.py` fails when the block and the register
disagree, so an edit without a version bump cannot reach `main`. Then
run `python -m chitragupta figure sync assets/tikz/*.tex
assets/tikz/exemplars/*.tex` to refresh every scaffold and exemplar,
which `tests/test_tikz_scaffolds.py` still checks byte for byte.

**Repeating it once per figure is safe**, by the same argument #781
makes for `\usetikzlibrary`. `\tikzset` re-defines the same keys to the
same values, and every macro is `\providecommand`, so N figures in one
document carrying N copies cost N definitions and change nothing. No
global hook is appended to and no loaded flag is set. The one construct
without this property is `\tikzset{every node/.style=...}` (see "Type and
line weight" above), and the block touches `every node` only through
`.append style` inside the `cg` picture option, scoped to one picture.

### 🧰 House shapes, and the well they sit in

The block defines five `pic`s: small conventional shapes drawn in the
house line weight.

| `pic` | Stands for | Twin says |
| --- | --- | --- |
| `cgstore` | a drum: any persistent store, such as the ledger, the vector store or a forward index | `[ledger]` |
| `cgdocs` | a stack of pages: a document, or a set of them | `[PDFs]` |
| `cgfunnel` | any place the set gets smaller: a cap, a top-*k*, a filter | `[cap 3 per source]` |
| `cgchip` | anything that computes: a model, an encoder, a reranker | `[bi-encoder]` |
| `cgshield` | the one blocking check, at most once per figure, if at all | `[gate]` |

Each passes the ASCII twin's test by construction. It sits directly
above a node whose label already says the same thing, so the shape is a
rendering choice and never a proposition, and the twin loses nothing by
dropping it.

**Draw every `pic` into a well.** A `pic` is a path, not a node, so it
has no name, and two things break quietly without one. `review figure`
measures only named nodes, so an icon colliding with a label reports
clean. And a zone card can `fit` only named nodes, so an icon placed
above a node pokes through the top of its own zone. `cgwell` is an
invisible, fixed-size (10mm), named node that the `pic` is drawn into:

```latex
\node[cgwell, above=2.5mm of sync] (isync) {};
\pic[cg pic colour=cgFlow] at (isync) {cgstore};
```

Every house `pic` fits inside its well, and
`tests/test_tikz_scaffolds.py` measures that, so an edit that makes one
overflow fails there. `pipeline.tex` shows the idiom.

**Colour.** `cg pic colour` takes a palette name and applies to that
one `\pic`. Give it the hue of the zone the shape sits in: the same
drum is green in the lexical zone and blue in the dense route.

**This is not an icon set, and it should not become one by accretion.**
A shape is added only when a metaphor in the
[layout table](#-commit-to-a-layout-metaphor-before-you-draw) wants it,
and only when the node's own label already carries the proposition.
Five is the ceiling for now. A sixth needs the same argument made again,
in writing, in its pull request, and a row in the table above;
`tests/test_tikz_scaffolds.py` fails if the block and the table name
different shapes.

### 🖨 What the other two forms do with it

Two readers receive no colour at all, and this is accepted rather than
designed around:

- The **ASCII twin** is 7-bit, so `md`, `docx` and `html` get none of
  it. The twin still has to work as a figure (that is
  [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10's two-form contract,
  and it is unchanged), but it is not required to reproduce the colour
  form's every distinction.
- A **black-and-white print** greyscales the TikZ form, where
  `cgFlow` and `cgAlt` land at similar lightness.

So the practical rule is weaker than "never encode meaning in colour"
and stronger than nothing: **colour may carry meaning, and should not be
the only thing carrying the figure's main point.** Keep the spine
legible through position and arrow direction, which every layout
metaphor above already gives you, and let colour do the work of making
the figure quick to read rather than possible to read.

## 📏 Draw for the width it will be printed at

The six layout metaphors have no width dimension, and a figure drawn
without one in mind is a figure whose type size is decided by accident.
A single-column figure in a two-column paper sets at roughly half a page
width; the same picture dropped into a thesis sets at nearly double
that. **Nothing in the picture changes, but the type does**, because
`scale=` and the consuming document's own width between them decide the
final physical size of every label.

So settle the target width *before* choosing a metaphor: a
hub-and-spoke needs horizontal room a single column does not have, and
is the wrong metaphor there however well it fits the content. A layered
stack degrades gracefully to a narrow column; a wide map does not.

**Never wrap a figure in `\resizebox` or `\scalebox`, and never set
`scale=` on the picture.** A picture drawn at its natural size and then
scaled to fit prints its type at whatever the scale factor happens to
be, so the floor in "Type and line weight" becomes a number nobody
chose. Settle the target width first, lay the figure out to it, and
`\input` it bare. If it does not fit, change the layout (wrap a row, cut
a gloss, drop a stage), never the scale. The row count following from
the type size is the right direction for that decision to run.

This is the rule that actually gets broken, because the scale is
**invisible in the figure file**: it lives in the draft that `\input`s
it. Measured on six hand-written figures in one acmart sigconf paper
(9pt body), each wrapped in `\resizebox{\textwidth}{!}{...}`:

| Figure | Natural width | Scale applied | Smallest type printed at |
| --- | --- | --- | --- |
| `architecture` | 462.8pt | 1.094 | 6.6pt |
| `rag-stages` | 548.9pt | 0.922 | **5.5pt** |
| `retrieval` | 519.5pt | 0.975 | 5.9pt |
| `coauthoring` | 520.8pt | 0.972 | 5.8pt |
| `prompt` | 425.6pt | 1.118 | 6.7pt |
| `revision` | 420.6pt | 1.180 | 7.1pt |

Six figures, six effective type sizes, none of them chosen. Laid out
again to fit 506.3pt unscaled, every label printed at 8.97pt or above.
Expect the floor to *change layouts*, not just sizes: `rag-stages` went
from two rows to three, and `retrieval`'s dense route wrapped. Three of
those redrawn figures ship as `assets/tikz/exemplars/`, since laid out
again to the render's 453pt (#1050).

The renderer is already clean here: `render_output/_figure_captions.py`
emits a bare `\begin{figure}` around the marker with no scale knob, so a
pipeline-rendered figure is drawn at natural size. The defect is what a
*hand-written* document does, which is exactly `thesis-chapter-writer`'s
case: its fragment is `\input` into a thesis this project never sees.
The ten scaffolds are each laid out to the `article` class's 345pt
text width, and a test compiles each one there and fails on an
`Overfull \hbox`.

**No venue table is bundled here, deliberately.** Column widths are
per-publisher, differ between initial and revised submission, and go
stale; a table checked into this repository would be read as current
long after it stopped being. If you keep one, keep it the way a
maintained one is kept: a date it was accessed, a source URL per entry,
and the standing caveat that **a passing check is not compliance**.
Re-read the publisher's live page before you submit.

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
  picture that is then scaled to 0.8 is the real defect.
- **"Pick a colourblind-safe palette and accessibility is handled."**
  Necessary, and not the end of it. The house palette is already
  Okabe-Ito, so the hue question is settled and you should not be
  re-deciding it per figure. What a safe palette does *not* address is
  the two readers who receive no colour at all (the ASCII twin's
  audience and anyone printing in black and white), which is a
  redundancy question rather than a palette one.
- **"A vector figure is resolution-independent, so size does not
  matter."** True of fidelity, false of legibility, and the second is
  what a reader notices.

## 🚫 Nothing here is a gate

This is a checklist an author checks a figure against, not something
enforced mechanically today.

`python -m chitragupta.review figure` reaches the part of it that
geometry can decide, and it is a **user-driven aid**: a person runs it
over a finished figure, it exits 0 whatever it finds, and nothing
downstream blocks on it. Three consequences follow, and they are the
ones authors get wrong:

- **It measures; it never places.** TikZ computes the layout, and the
  aid compiles the figure and reads back where things landed. So the
  fix for a finding is to change what you asked TikZ for (a
  `sibling distance`, a `row sep`, a different library), and never to
  nudge a coordinate until the number moves. `assets/tikz/` is the
  starting point for that, and none of its ten scaffolds places
  a node at a coordinate.
- **Its thresholds are the checker's, not this document's.** "An empty
  band worth more than a third of the height" is a number chosen so
  ordinary layouts pass; it is not a rule from the list above. It does
  shape what passes (a two-row diagram spread out generously trips it
  with nothing wrong), so when a finding and your own eyes disagree,
  the eyes win and the figure stays.
- **A clean report is not a checked figure, and the report now says
  which it is.** The geometry checks measure only nodes the source
  names, so a picture that names none has nothing to measure. That used
  to print as `No layout findings`, identical to a figure where every
  check ran and found nothing; it now prints as its own finding, with
  the declared names that did not come back listed beside it. Name the
  nodes you draw, in whichever idiom; `\node (a)` and
  `child { node (a) ... }` both count.

[REVIEW.md](REVIEW.md) has the aid among the other ten;
[CLI.md](CLI.md#-chitragupta-review-figure) has its flags and the full
statement of the boundary.

## 🔎 The rules `figure check` reports

`python -m chitragupta figure check <figure.tex>` checks one figure
file against the rules below and reports each one it breaks, one line
per finding: `<rule-id> <target> <measurement>`. The id is the contract.
A finding, a `% cg-allow:` line, this table and the `figure-drawer`
skill's `references/check.md` all quote it, and a test fails if they
stop naming the same set. [CLI.md](CLI.md#-chitragupta-figure-check)
has the flags and the report's layout.

Like `review figure`, it exits 0 whatever it finds. **Objective** is
what the skill does with a finding (resolve it, or allow it with a
reason), not an exit code; **advisory** findings are read, not
resolved. **Scope** is what an allow has to name: a figure-scope rule
is about the whole picture, an element-scope rule about one node, pair
or point.

A node the figure's source does not name is shown by its centre,
`(x,y)` in mm, wherever a target or a measurement names a node: one
left unnamed, and one TikZ names itself, `tikz@f@<n>` (a pin, an
`alias`, an unnamed node followed by `edge` or `child`) (#1087).

| Id | Scope | Class | What it reports |
| --- | --- | --- | --- |
| `does-not-compile` | figure | objective | The figure's own TikZ fails, with TeX's first error line. The geometry rules are then listed as not measured. Cannot be allowed |
| `nothing-measurable` | figure | objective | The figure names no node, so the geometry rules had nothing to measure. Name the nodes you draw |
| `size-width` | figure | objective | The picture is wider than the target text width: 453pt by default, the render's A4 at 1in margins, or `--width`. Several pictures in one file are measured together, as they print side by side |
| `size-stray` | figure | objective | The figure, set as one box, is wider than its picture by more than 0.5pt: a line outside the picture that ends without `%` sets a space when the figure is `\input` inline or measured with `\sbox` (the float the renderer uses drops it). Not measured for a file with several pictures, whose spacing is deliberate |
| `focal-count` | figure | objective | More than one accented node, `cgkey` or `cgkeystate`: if two things are accented, neither is. Read from the source, so an accent reached only through a style the figure defines itself is not seen |
| `content-protrusion` | figure | objective | An empty horizontal band taller than a third of the figure ("Check the drawn figure against this list" above) |
| `loads-library-by-hand` | figure | objective | A library loaded through its internal macro instead of `\usetikzlibrary` (#781) |
| `node-overlap` | element | objective | Two nodes' boxes intersect; the target is the pair, `a+b`. A zone containing its nodes is not an overlap. Every node TikZ drew is measured, an unnamed one (a zone title, a note) named by its centre, `(x,y)` in mm; a tag on a line is `c6`'s, and a round node under 7mm (a step badge) is left out |
| `node-text-overload` | element | objective | A node's text runs past 15 words; the target is the node |
| `stranded-arrowhead` | element | objective | An arrowhead lands mid-line where another path continues; the target is the point, `(x,y)` |
| `c1-orthogonal` | element | objective | A connector between nodes whose ends differ by more than 1mm in both x and y is drawn straight or bent instead of as an elbow (`-\|`, `\|-`); the target is the edge, `a->b`. Not evaluated for the `hub-and-spoke-network` and `state-machine` layouts; a tree is held to it |
| `c2-tag-clearance` | element | objective | A tag's text is under 0.8mm or over 3mm from its own line. Measured from the text, not the node box, which `above` and the rest put on the line; the house `cgtag` sits 1mm clear. A `sloped` tag is not measured |
| `c3-coincident` | element | objective | Two connectors run together for more than 2mm, so one hides the other; the target is the pair, `a->b+c->d`. Two that share an end point are a fork, and are not counted |
| `c4-attach` | element | objective | One end on a side over 1mm off its midpoint, several over 1mm off even spacing (`L*k/(N+1)`) or under 2mm apart; the target is the side, `a.north`. Measured only where a straight connector meets the side square on, so an angled or bent end is left to `c1`. Round nodes and zones are not measured. Not evaluated for the layouts `c1` exempts, nor for `sequence`, whose messages meet a lifeline wherever time puts them |
| `c5-transit` | element | objective | A connector crosses a node that is neither of its ends. A zone containing an end, a marker under 2mm and an unframed group (an undrawn `fit`) are not counted. Not evaluated for `sequence`, where a message passes over the lifelines between its ends |
| `c6-tag-covered` | element | objective | A tag overlaps a node. A zone containing the tag and an unframed group are not counted |
| `c7-dangling-tip` | element | objective | An arrow leaving a node has its tip land more than 1mm from any node or other line; the target is the point, `(x,y)` in mm. An axis or a two-headed dimension line, which leaves no node, is not read |
| `k1-stroke` | element | objective | A box's border, or a connector, under WCAG's 3:1 against its ground; the target is the node or the edge, `a->b`, and the measurement names both colours and the ratio. The ground is the box's own fill, else the innermost filled box that contains it, else white; a connector's, the innermost filled box that holds both its ends. Colours are what pgf drew with, so a style or `#1` argument is resolved. The fix is the hue's `Line` shade. A translucent fill is read as opaque, a shadow is not a ground, and a connector crossing a third zone is measured against its ends' ground |
| `k2-text` | element | objective | A run of a node's text under 4.5:1 against the same ground, or under 3:1 where it is WCAG's large text (14pt bold, 18pt), measured from the typeset size; the target is the node, or `tag on a->b`. Read from the glyphs, so `text=`, `\textcolor`, `\color` and a macro are all seen. The fix is the hue's `Text` shade |
| `w4-pictograph` | element | objective | An emoji or pictograph (U+1F000 to U+1FAFF, U+2600 to U+27BF, U+2B00 to U+2BFF, U+FE0F) in a label; the target is the node, or `figure` for one outside any label. The render prints it from a fallback font unlike the rest, and a thesis without that font chain drops it. Arrows, `©`, `™`, math and icon commands are not read |
| `twin-missing` | figure | objective | No `<name>.txt` beside the figure: the `md`, `docx` and `html` renders have nothing to show. `t1` to `t3` are then listed as not measured. Cannot be allowed: write the twin |
| `t1-labels` | element | objective | A name in the TikZ is not in the twin: a node label's first line (`\cglab`'s name), a zone title or a legend entry. Every word of it must appear in the twin, as a whole word and in any order, case aside; markup is stripped and maths dropped first. A gloss is not compared. The target is the node, or the name's text for an unnamed node |
| `t2-tags` | element | objective | A line of a node placed on a `\draw` or `\path` (a tag, whatever its style) is not in the twin, word for word as `t1`; the target is the edge, `a->b`, or the tag's text where it joins no two names |
| `t3-panels` | figure | objective | The panel letters opening a label line in the TikZ, `(a)`, `(b)`, are not the set of `(<letter>)` tokens in the twin |
| `size-height` | figure | advisory | The picture's height as a share of the 700pt text height, beside the layout's reference range |
| `size-slack` | figure | advisory | `1 -` the area of the nodes that enclose no other node, over the picture's area (a zone card is not filled area), beside the layout's reference range |
| `size-squash` | element | advisory | Two nodes joined by an edge are under 3mm apart edge to edge, so the arrow is too short to read; the target is the pair, `a+b`. A pair that overlaps, a zone and its child, and a bend coordinate are not measured; a path with an `edge` operator or a named node on it, or a point built from two nodes (`b.north \|- a`), is listed as not measured rather than guessed at |
| `budget-nodes` | figure | advisory | The named node count, beside the layout's reference range. Never a cap |
| `budget-edges` | figure | advisory | The count of edges the source parser reads, beside the layout's reference range. Never a cap |
| `w1-case` | element | advisory | A `\cglab` name that starts lower-case, or is in Title Case (every later word of four letters or more capitalised); the target is the name. Acronyms, `\texttt{}`, math and a program name that is lower-case by convention (`pdflatex`) are left alone, so `Extended Kalman filter` passes |
| `w2-tag` | element | advisory | A tag on a `\draw` or `\path` that joins two points, over three words or with a capitalised word (acronyms aside); the target is the tag's text |
| `w3-gloss` | element | advisory | A `\cglab` gloss over six words; the target is its name. A formula counts as one word |

Of the objective rules, all but `size-width`, `size-stray`,
`focal-count`, the connector rules `c1` to `c7`, `k1`, `k2`, `w4` and
the twin rules (`twin-missing`, `t1` to `t3`) are `review figure`'s
findings, under the ids its `--json` has always used. The
edge list, the declared names that were not measured, the emptiness
proportion and the count of lines not between two nodes are printed
beside the findings as diagnostics, never as findings.

**The eight advisory rules are reports, not findings** (#1057, #1055).
They print under their own heading, never change the "No findings"
line and cannot be allowed. The wording ones (`w1` to `w3`) are matters
of house style for the author to weigh, read only from `\cglab`, where
a name and a gloss are certain. For the size ones FIGURE-ROADMAP VI.3 is
why: a bare count means little, so each sits beside the range its
layout's scaffold and exemplars measure, and a range describes those
figures and never caps yours. A forty-cell DP trace is not over budget.
The range is read from the `## Reference ranges` table in
`.claude/skills/figure-drawer/references/layouts/<layout>.md`, and the
layout from the figure's own `% cg-layout: <layout>` line, on a line
of its own (`--layout` overrides it). Every scaffold and exemplar
carries one; a figure without one gets the numbers and no range.

The seventeen rules that need the compiled geometry (`nothing-measurable`,
`size-width`, `size-stray`, `content-protrusion`, `node-overlap`, `c1`
to `c7`, `k1`, `k2`, `size-height`, `size-slack`, `size-squash`) are listed under
"not measured", with the reason, whenever there is none to read: the figure
does not compile, the file has no `tikzpicture` environment for the
probe to sit in (a bare `\tikz` is not compiled at all), or its last
`tikzpicture` is inside a macro body that never runs. A rule that could
not run is never reported as a pass. A file with several pictures has
its height, slack and squash listed there too, since the probe reads
only the last picture's extent, and so is each edge `size-squash`
cannot read: one on a path with an `edge` operator or a named node on
it, whose consecutive tokens are not the two ends of one line, and one
with an end that is no measured node (`chan -| gate.west`). The edges it
could read are still measured, so `size-squash` can appear both among
the advisory reports and under "not measured" in one report.

**The connector rules measure the lines TikZ drew**, not the source:
the probe logs every stroked line and every node, a `\foreach` body's,
a `child`'s and a tag's included, so a computed end such as
`(a.north |- b.south)` is measured where it landed. A connector is a
line whose two ends touch two different nodes; a line that does not
(an axis, a plot, a bus line, a self-loop) is not checked, and the
report counts it. They are listed as not measured where a line and the
node boxes are not in one frame: a file with several `tikzpicture`s, or
one that uses `transform canvas`. Their thresholds were set over this
repository's own figures (`bench/RESULTS.md`, 2026-10-29).

**The layout line also decides which connector rules apply.** A rule a
layout exempts is not evaluated for a figure that declares it (or is
given it with `--layout`): a hub's spokes are diagonal by design and an
automaton's transitions curve, so `c1-orthogonal` and `c4-attach` are
exempt for `hub-and-spoke-network` and `state-machine`. A tree is not:
the house tree fans its edges out orthogonally. A `sequence` keeps
`c1-orthogonal`, since its messages are level, but is exempt from
`c4-attach` and `c5-transit`: many messages meet one lifeline at the
heights time sets, and a message may pass over the lifelines between
its ends.

### ✍ Recording a deliberate exception: `cg-allow`

A figure that breaks a rule on purpose says so in its own file, which
travels with it into the draft, the render and a thesis:

```latex
% cg-allow: size-width -- a five-stage pipeline the chapter compares stage by stage
% cg-allow: node-overlap legend+pot -- the legend sits on the pot on purpose
```

The form is `% cg-allow: <rule-id> [<target>] -- <reason>`, on a line
of its own.

- **The reason is required.** An allow without one is reported as
  malformed and allows nothing, so an exception is always a claim
  someone can read and disagree with.
- **A figure-scope rule takes no target, and an element-scope rule
  requires one**, so "allow every overlap" cannot be written.
- **An element-scope allow covers its one target**, spelt as the
  finding prints it (`decide.south`, not `decide`), so a later defect
  of the same kind elsewhere is still found. A pair matches in either
  order. A target with a space in it is written in double quotes, as
  the report prints it: `k2-text "tag on parse->ledger"`.
- **Every honoured allow is listed in the report**, with the
  measurement it set aside, so an exception is never invisible.
- **An allow that sets nothing aside is stale**, whatever its scope:
  its target is gone (`no node named decide`) or no longer breaks its
  rule. Delete it, or fix its target. An allow whose rule could not run
  (the figure does not compile, or its layout exempts the rule) is
  listed as unchecked instead, since nothing was measured.

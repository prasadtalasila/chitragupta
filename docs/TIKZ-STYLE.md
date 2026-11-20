# 📐 TikZ figure style: layout, typography, and the pre-flight checklist

Status: **reference.**

This is the TikZ-specific half of
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10's figure contract. That
section owns the two-form (TikZ + ASCII) pair, the marker syntax,
originality, and the ASCII form's 7-bit alphabet and column limit; this
document is what makes the TikZ half good.

**Written for** the `figure-drawer` skill, which `survey-writer`,
`tutorial-writer`, `thesis-chapter-writer` and `textbook-chapter-writer`
hand a figure to, and for anyone drawing one by hand.
[FIGURE-DRAWER.md](FIGURE-DRAWER.md) says how the skill applies this
document. `deep-research` does not draw §10 figures. The parts of this
standard that geometry, colour and text can decide are measured by
`python -m chitragupta figure check`
([figure-checks/README.md](figure-checks/README.md)), an aid that blocks
nothing.

## 🏗 Commit to a layout metaphor before you draw

TikZ figures sprawl when nothing asks for a plan before the first
`\node`. Committing to one metaphor first turns "place these nine
things" into a constrained problem. Each metaphor maps onto a TikZ
idiom:

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
| Timeline | ticks placed by fraction along one chained axis, eras as banded cards |

(The first six are PaperBanana's planner supplement, read and not
copied;
[INSPIRATION.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/INSPIRATION.md)
carries the credit.)

The last four rows need a word each; each layout's reference file
(below) has the detail.

- **Zoned spine:** one storyline, with zone cards (a `fit` node drawn
  `on background layer`, titled outside its top-left corner) for the
  commentaries along it. If nothing comments on the path, it is a
  pipeline.
- **Comparison:** a before and an after, or two approaches to one job,
  in two lettered panels of the same parts. The part that differs is the
  `cgkey`; a part one side lacks keeps its row as `cgnone`; panel (b)'s
  parts are placed `at (<column> |- <match>)` so each stays on its
  match's row.
- **Sequence:** parties side by side, time running down, each hanging a
  thin undrawn lifeline so every message is a measurable connector. A
  message is level at a named moment
  (`(a-l.east |- t1) -- (b-l.west |- t1)`) and a reply is dashed;
  `c4-attach` and `c5-transit` are not evaluated for it.
- **Timeline:** each event a tick at its own fraction of one axis,
  `($(t0)!<f>!(tend.west)$)`, so a gap on the page is a gap in time.
  The event the figure is about takes `cgfocus`. If only the order
  matters, it is a pipeline.

**There is a starting file for every row of that table, in
`assets/tikz/`**, each compiling on its own with no `figure check`
finding. Copy the one whose metaphor fits and re-label it.
`chitragupta init` copies `assets/` into a project, and
`assets/tikz/README.md` says what each file is for.

**Choose the pattern before the layout.** What a figure argues (a
bottleneck, a lifecycle, a trust boundary, a comparison) is a different
choice from how it is laid out, and several patterns share one layout.
The `figure-drawer` skill's
`.claude/skills/figure-drawer/references/patterns.md` routes a pattern
to the nearest layout, and each layout has one reference file,
`.claude/skills/figure-drawer/references/layouts/<layout>.md` (the
layout's name as its scaffold spells it), with its anti-patterns and the
reference ranges measured from its scaffold and exemplars.
A new pattern never adds a layout; only a new way of placing nodes does.

**Every scaffold places its nodes relative to one another, never at a
coordinate in millimetres.** Keep that when you edit one. In
hand-computed millimetres, re-wording one label or changing the type
size re-opens every adjacency at once; relative placement and `fit`
layers make most collisions impossible. Inside a `pic` definition,
explicit millimetre coordinates are correct: a `pic` is a fixed object
whose geometry does not reflow, whether drawn by hand or generated.

**Name every node you draw.** A finding names a node by its `(name)`;
an unnamed one is shown only by its centre in millimetres. A picture
that names no node is reported as `nothing-measurable`. `\node (a)` and
`child { node (a) ... }` both count, and so does the `cgwell` a `pic` is
drawn into ([House shapes](#-house-shapes-and-the-well-they-sit-in)).
The `tree` idiom draws its edges internally, so the edge list and the
`budget-edges` count are empty for it; confirm a tree's wiring from the
source's nesting.

**Every idiom in that table needs a `\usetikzlibrary` line, and the
figure file carries it at the top, above the `tikzpicture`:**

```latex
\usetikzlibrary{positioning}
\begin{tikzpicture}[thick,x=1mm,y=1mm]
```

The renderer collects those lines and loads their union in the preamble
(`chitragupta/render_output/_tikz_libraries.py`), so your own line is a
no-op there. Keep it anyway: it lets the same file compile inside a
user's own thesis (`thesis-chapter-writer`'s fragment) and in the
minimal probe document §10 tells you to build. Without any load, a
picture using `below=4mm of store` fails the whole render with a message
that names neither the library nor the figure:

```text
! Package PGF Math Error: Unknown operator `o' or `of' (in '4mm of a').
```

**Write nothing else about loading.** No clearing of
`\tikz@library@<name>@loaded`, no saving or restoring of
`\tikz@node@reset@hook`, no `\ifdefined` guard. A figure file is
`\input` inside a `figure` float, which is a group: the load defines the
library's macros locally but sets the loaded flag globally, and clearing
the flag to force a reload appends `positioning`'s transform to a global
hook again, so the Nth figure shifts every node N times while `pdflatex`
exits 0. `figure check` reports one as
[`loads-library-by-hand`](figure-checks/BUILD.md).

**A load while TeX is setting a line prints as blank width.** Inside a
box (`\sbox`, `\hbox`, `\resizebox`), inline in text, or in a
`standalone` preview, the library files' line ends become 135pt to 147pt
of glue ahead of the picture, so a document that sets a figure in a box
loads its libraries in the preamble
([`size-stray`](figure-checks/SIZE.md)).

Before you reach for a library:

- **A missing name takes the whole call down.** `\usetikzlibrary{}` fails
  fatally on the comma list, so one typo reads like several missing
  packages. Probe a library by compiling a two-line document that loads
  it, **not** with `kpsewhich`, which misses every pgf-layer library
  such as `arrows.meta`.
- **`shapes.geometric`, not `shapes.geometry`.** The second is not a PGF
  library at all.

`texlive-pictures`, which `scripts/install_full_pipeline.sh` installs,
ships all of these.

## 🔠 Panels in one figure, and the letters they need

A figure that shows the same thing under two or more conditions is one
figure with panels. **However many panels it has, it stays one figure,
one `figure:` marker and one `.tex`/`.txt` pair**; one marker per panel
would give separate floats with separate numbers.

**Every panel carries a label node reading `(<letter>) <short title>`,
and the letter is the panel's position in reading order**: left to
right, then top to bottom, so moving a panel moves its letter with the
position. Draw the label as an ordinary node under the panel it names.
Prose refers to `Figure~\ref{fig:x}(b)`, with the letter typed, since
these letters are drawn rather than counted by LaTeX.

**Put the same letters in the ASCII twin.** `md`, `html` and `docx`
render only the `.txt`, so for three of the five formats it is the only
place the sub-captions exist. Take the four columns for each letter from
the gap to the *left* of its title rather than inserting them, or every
later title slides off its panel; the letters then overhang by four
columns and §10's ~70-column cap holds.

**When a row stops fitting, wrap into another row; never scale the
picture.** Three panels of about 48mm each overflow an ordinary text
block, and pdflatex only warns. Four of the same panels as a 2x2 grid
fit. `\resizebox` or `scale=` would shrink the text below the body size
("Type and line weight" below).

**Where the figure is captioned, write the caption in the draft, not in
the figure file.** A Markdown draft writes its caption below the
`figure:` marker (WRITING-STANDARDS.md §10), and the renderer wraps the
marker in a `figure` float with `\caption`/`\label`. The figure file
stays a bare `tikzpicture` fragment, like the scaffolds.
`thesis-chapter-writer`'s `.tex` fragment has no marker, so it writes
its own `\begin{figure}...\caption{}...\label{fig:<id>}...\end{figure}`
around the `\input`, and never `\renewcommand{\thefigure}{N.M}`: the
counter is what keeps `\ref` in step with the thesis's own numbering.

**Do not reach for `subcaption`, `subfig` or `subfigure`.** A figure
file can load a TikZ library in the document body but never a package
(`! LaTeX Error: Can be used only in preamble.`), and
`thesis-chapter-writer`'s fragment goes into a preamble we never see, so
a figure needing `subcaption` compiles here and fails there. Drawn
letters work in every genre; the cost is `\subref` and automatic
"Figure 1a" numbering.

**Record the convention, don't re-decide it.** Which letters a venue
wants (`(a)`, `(i)`, `A`, or titles alone) is a house-style decision in
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) §8's sense, and belongs in
the dossier's `scope.md`, which `draft-reviser` reads before every edit.

A three-panel figure, relative placement throughout. It compiles, every
node it names comes back measured, and `figure check` reports no
overlap and no connector finding:

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

`tests/test_tikz_subcaptions.py` compiles that example out of this file.
The empty `fit` nodes give each panel an extent to hang its label under;
`figure check` excludes such grouping boxes from its overlap check, and
any other way of finding the same point is fine.

## ✅ Check the drawn figure against this list

Concrete defects, not taste. Each rule `figure check` measures is
explained, with a faulty and a fixed figure, on the page linked.

- **Occlusion and overlap** ([`node-overlap`](figure-checks/NODES.md)).
- **A `fill` erases everything under it.** A label filled white to break
  a line paints out every arrowhead, border and rule its whole rectangle
  covers, not just the line you aimed at. Ask what else is in the band
  before reaching for `fill=white`.
- **One arrow is one `\draw`.** Two colinear segments that meet, each
  carrying `->`, leave a second head pointing at nothing where they join;
  put the `->` on the last piece only. Chaining through a **named** node
  is fine, because TikZ clips each path at the node
  ([`stranded-arrowhead`](figure-checks/NODES.md)).
- **Chaotic routing.** The geometric parts are the connector rules `c1`
  to `c7` ([connectors](figure-checks/CONNECTORS.md)); whether the
  routing as a whole reads clearly stays a human judgement.
- **Illegible or inconsistent type, and low contrast**: one size per
  role, held across the figure
  ([colour and type](figure-checks/COLOUR-AND-TYPE.md)).
- **Inefficient non-rectangular composition.** LaTeX treats a figure as
  a rectangle, so anything protruding above the main block wastes
  vertical space ([`content-protrusion`](figure-checks/SIZE.md)).
- **Conciseness:** a node whose text runs past 15 words is too long for
  a box; cut it or split the node, never shrink the font
  ([`node-text-overload`](figure-checks/NODES.md)).
- **The main point resting on colour alone.** Colour may carry meaning,
  but the ASCII twin (all that `md`, `docx` and `html` render) and a
  black-and-white print get none of it, and `cgFlow` and `cgAlt` grey to
  similar lightness. Position, arrow direction and labels should deliver
  the argument; colour should make it fast. Read the `.txt` twin and ask
  whether the point still arrives. A secondary distinction in colour
  alone is fine.
- **Literal copying:** a box-ified copy of prose is not a figure. This
  is §10's originality rule, and it matters because a figure can launder
  borrowed wording past every detector in [PLAGIARISM.md](PLAGIARISM.md):
  the gate does not follow `\input`.

## 🔤 Type and line weight

- **Every word in a figure is set at the document's body size**, never
  smaller and never larger. Names and zone titles are told apart from
  glosses and tags by weight and colour (bold names, muted glosses), not
  by size. Set the size as a picture option (`\begin{tikzpicture}[cg]`
  does it) so a float, table cell or `\small` group cannot lower it.
  Shrinking type is never the fix for a box with too many words. The two
  exceptions are TeX's own script-style sub- and superscripts and the
  document's `\caption`. `tests/test_tikz_scaffolds.py` holds every file
  in `assets/tikz/` to this by reading each glyph's printed size out of
  the compiled PDF. `figure check` reports text below the body size as
  [`type-below-floor`](figure-checks/COLOUR-AND-TYPE.md).
- **Lines are drawn `thick`** (0.8pt, double TikZ's 0.4pt default), set
  as a picture option, which the house block's `[cg]` includes. **Do
  not** write `\tikzset{every node/.style={thick}}`: `/.style=`
  *replaces* whatever `every node` held, so a figure's own node style
  (`draw`, `circle`, a fill) silently vanishes.

## 🎨 The house palette

**Figures here are in colour, and they use one palette.** Five named
colours with a role each, and four more that a zoned figure needs.
`figure check` reports an invented hue as `colour-off-palette`, and a
card filled outside the band below as `tint-outside-band`
([colour and type](figure-checks/COLOUR-AND-TYPE.md), which also lists
the fill, line and text name for each hue).

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
`}` with a `%`, so the block sets no stray space.)

The values are Okabe-Ito's colourblind-safe qualitative set (Okabe &
Ito, 2008). `cgWarm` and `cgRose` are its remaining members, one hue per
zone, so a zoned figure need not reuse a role colour. `cgInk` is a
near-black because pure black reads heavier than body text, and
`cgPaper` is one step off white for the same reason. **`cgMute` is a
*named* grey** because the house styles paste a colour argument into a
tint (`fill=#1!11`), and `cgInk!55!11` is rejected by xcolor.

**Each colour has a role.** Use `cgAccent` for one thing per figure: if
two things are accented, neither is. `cgFlow` carries the spine; `cgAux`
is for what happens off to the side, usually dashed as well; `cgAlt` is
a second node class.

**A palette name fills; a `Line` or `Text` name draws.** `fill=cgFlow!8`
is a wash text reads through; `fill=cgFlow` is solid blue. Between 6 and
12 is the band the house block's cards and zones use. Strokes and
coloured text take a darker shade, because several hues are too light as
a line on their own tint (`cgWarm` on `cgWarm!12` is 1.9:1, where WCAG 2
asks 3:1) and only `cgFlow` reaches the 4.5:1 text needs. Each hue, and
`cgMute`, has two shades mixed towards `cgInk`:

| Hue | Border, edge, rule | Coloured text |
| --- | --- | --- |
| `cgFlow` | `cgFlowLine` (100%) | `cgFlowText` (95%) |
| `cgAccent` | `cgAccentLine` (100%) | `cgAccentText` (75%) |
| `cgAlt` | `cgAltLine` (95%) | `cgAltText` (70%) |
| `cgAux` | `cgAuxLine` (75%) | `cgAuxText` (55%) |
| `cgWarm` | `cgWarmLine` (75%) | `cgWarmText` (55%) |
| `cgRose` | `cgRoseLine` (90%) | `cgRoseText` (65%) |
| `cgMute` | `cgMuteLine` (95%) | `cgMuteText` (70%) |

Each percentage is the hue's share of the mix: the largest multiple of 5
that clears the threshold over white, `cgPaper` and every tint the block
fills with, since an edge can cross another zone.
`tests/test_figure_contrast.py` recomputes them from the hex values
above. Every house style already draws this way, so the rule binds only
what you write yourself: `draw=cgAltLine`, not `draw=cgAlt`. A style that
takes a colour argument (`cgzone=cgAlt`) takes the palette name and
finds the shade itself.

### 📎 The palette travels inside the figure

**The palette travels as part of the house block** (next section),
which every figure carries whole, never in a shared file or a preamble.
The renderer injects `\usepackage{tikz}` and nothing else, and
`thesis-chapter-writer`'s fragment is `\input` into a thesis that has
never heard of this project, so a colour defined elsewhere compiles here
and fails there. The duplication across figures is deliberate; the
eleven scaffolds in `assets/tikz/` all carry the block.

### 🧱 The house figure style

`assets/tikz/cg-figstyle.tex` grows the palette into the rest of the
vocabulary a figure needs, so a figure stops re-deciding corner radius,
rule weight, tint depth, arrowhead and label structure each time:

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
apart (`cg`'s `node distance`). Two zones sit 8mm apart card to card,
14mm member to member once each card's 3mm inner sep is counted; say
that distance where a placement crosses zones. Stacked zones need about
5mm more for the lower card's title (`assets/tikz/layered-stack.tex`
works the sum).

**An edge tag sits beside its line.** `cgtag` is unfilled and placed
with `auto`, left of the direction of travel, 1.5mm off the segment's
centre; add `swap` for the right. A tag filled over its line breaks the
line where the eye is following it. Set it beside the shaft, not the
2.1mm arrowhead: `c2-tag-clearance` measures from the head too.

The block needs one library line, at the top of the figure with the
picture's own:

```latex
\usetikzlibrary{arrows.meta,positioning,fit,backgrounds,calc,shadows.blur}
```

All six ship with `texlive-pictures`. `shadows.blur` is reached by
`\usetikzlibrary`, not `\usepackage`, so the soft shadow travels into a
thesis preamble this project never sees.

**The block travels between its two marker comments, and
`python -m chitragupta figure sync` keeps it current.** It stamps the
block into a figure file that lacks one, above its first
`\usetikzlibrary` or `tikzpicture` line, and replaces a block from an
older release, leaving everything outside the markers byte for byte.
With no paths it walks every `content/drafts/**/figures/*.tex`;
`--check` writes nothing and exits 1 if any file is not current.
`chitragupta draft render` reports a stale or missing block as a
`[figure]` warning naming the command, and never rewrites a figure.

**Never edit inside the markers.** A style one figure needs goes in that
picture's own options, or in a `\tikzset` below the end marker. `figure
sync` knows every released block by its digest, so it leaves a
hand-edited region alone and prints the diff against the house block,
for a person to move the edit out. A style that three or more figures
need is a pull request against `cg-figstyle.tex`.

**Changing the block means a new version.** Bump the `v<N>` in its first
line and add that version's digest to
`assets/tikz/cg-figstyle.versions.toml`, never editing an existing line;
`tests/test_figure_block.py` fails when the two disagree. Then run
`python -m chitragupta figure sync assets/tikz/*.tex
assets/tikz/exemplars/*.tex` to refresh every scaffold and exemplar,
which `tests/test_tikz_scaffolds.py` checks byte for byte.

**Repeating it once per figure is safe.** `\tikzset` re-defines the same
keys to the same values and every macro is `\providecommand`, so N
copies in one document change nothing; no global hook is appended to.
The block touches `every node` only through `.append style` inside the
`cg` picture option, scoped to one picture.

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

Each sits directly above a node whose label already says the same thing,
so the shape is a rendering choice, never a proposition, and the ASCII
twin loses nothing by dropping it.

**Draw every `pic` into a well.** A `pic` is a path with no name, so no
rule measures it and a zone card cannot `fit` it: an icon can collide
with a label and report clean, or poke out of its own zone. `figure
check` reports a `pic` outside a well as
[`unnamed-pic`](figure-checks/NODES.md). `cgwell` is an invisible,
fixed-size (10mm), named node that the `pic` is drawn into:

```latex
\node[cgwell, above=2.5mm of sync] (isync) {};
\pic[cg pic colour=cgFlow] at (isync) {cgstore};
```

`tests/test_tikz_scaffolds.py` measures that every house `pic` fits its
well. `pipeline.tex` shows the idiom. `cg pic colour` takes a palette
name for that one `\pic`; give it the hue of the zone the shape sits in.

**This is not an icon set, and it should not become one by accretion.**
A shape is added only when a metaphor in the
[layout table](#-commit-to-a-layout-metaphor-before-you-draw) wants it,
and only when the node's own label already carries the proposition.
Five is the ceiling for now. A sixth needs the argument made again, in
writing, in its pull request, and a row in the table above;
`tests/test_tikz_scaffolds.py` fails if the block and the table name
different shapes.

## 📏 Draw for the width it will be printed at

A single-column figure in a two-column paper sets at roughly half a page
width; the same picture in a thesis sets at nearly double that. Nothing
in the picture changes, but the type does. So settle the target width
*before* choosing a metaphor: a hub-and-spoke needs room a single column
does not have, while a layered stack degrades gracefully to a narrow
column.

**Never wrap a figure in `\resizebox` or `\scalebox`, and never set
`scale=` on the picture.** A scaled picture prints its type at whatever
the scale factor happens to be, a size nobody chose. Lay the figure out
to the target width and `\input` it bare; if it does not fit, change the
layout (wrap a row, cut a gloss, drop a stage), never the scale. The
scale is invisible in the figure file, because it lives in the draft
that `\input`s it: six figures wrapped in `\resizebox` in one paper
printed at six type sizes, the smallest 5.5pt, and laid out again
unscaled every label printed at the body size, at the cost of changed
layouts. Three of those redrawn figures ship in
`assets/tikz/exemplars/`. `figure check` reports a picture wider than
the page as [`size-width`](figure-checks/SIZE.md).

The renderer emits a bare `\begin{figure}` with no scale knob, so the
defect is what a *hand-written* document does, which is exactly
`thesis-chapter-writer`'s case. The eleven scaffolds are each laid out
to the `article` class's 345pt text width, and a test fails any that
overflows it.

**No venue table is bundled here, deliberately.** Column widths are
per-publisher, differ between initial and revised submission, and go
stale; a table checked into this repository would be read as current
long after it stopped being. If you keep one, give each entry an access
date and a source URL, and remember that **a passing check is not
compliance**. Re-read the publisher's live page before you submit.

## 🧿 Rules that are not universal

Several rules written for raster images do not transfer to a TikZ
picture:

- **"Line art must be 600 or 1000 dpi."** A TikZ figure is vector and
  has **no DPI**. What transfers is physical width, above.
- **"Convert everything to CMYK / everything to RGB."** A question about
  exported raster assets, which this pipeline does not control.
- **"Make the figure bigger so the text is readable."** Backwards: it
  overflows the column and gets scaled back down. Type size at final
  scale is what matters.
- **"Pick a colourblind-safe palette and accessibility is handled."**
  The house palette is already Okabe-Ito, so do not re-decide hue per
  figure. It does not help the two readers who get no colour at all,
  which is a redundancy question (see the checklist).
- **"A vector figure is resolution-independent, so size does not
  matter."** True of fidelity, false of legibility.

## 🔎 Checking a figure against this standard

`chitragupta figure check <figure.tex>` measures width, overlaps,
connector routing, contrast, type size, the palette, the ASCII twin and
more, 36 rules in all. It exits 0 whatever it finds; the only gate in
this project is the citation gate. It never places anything: fix a
finding by changing what the figure asks TikZ for (a `node distance`, a
`row sep`, an anchor, a layout), never by nudging a coordinate. When a
finding and your own eyes disagree about a figure that is right, keep
the figure and record why with a `% cg-allow:` line.
[figure-checks/README.md](figure-checks/README.md) explains how to read
a report and links each rule to its page.

# 🧱 Figure checks: build

Status: **reference.**

The rules about whether the figure can be measured at all: a figure
that does not compile, one that names no node, and one that loads a
TikZ library by hand. [README.md](README.md) explains how to read a
report and how to record a deliberate exception.

Each rule below shows a faulty figure, the line `figure check` prints
for it, and the fixed figure. Both are real files in
[examples/](examples/), and `tests/test_figure_check_examples.py`
compiles them, so the report lines on this page are what the check
prints today. The listings show the picture only, unless the defect is
outside it; every file also carries the house style block above it.

The figures on this page look the same faulty and fixed, or do not
render at all, so there are no pictures. The code is the difference.

## 🧭 Rules on this page

- [`does-not-compile`](#does-not-compile)
- [`nothing-measurable`](#nothing-measurable)
- [`loads-library-by-hand`](#loads-library-by-hand)

### `does-not-compile`

**Catches.** The figure's own TikZ fails to compile. The target is
`figure`, and the measurement is TeX's first error line. Every rule
that needs the compiled geometry is then listed under "not measured",
with the reason. The rules read from the source, such as
`focal-count` and the twin rules, still run.
[README.md](README.md#-what-needs-a-compiled-figure) lists which rules
need a compiled figure. This rule cannot be allowed: there is no
deliberate reason for a figure that does not build.

**Why it matters.** A figure that does not compile takes the whole PDF
render down with it. Nothing else in the report can be trusted either,
because the geometry rules did not run, and a rule that did not run is
not a pass.

Faulty: the arrow names `indx`, a node the figure never declares.

```latex
\node[cgbox, text width=26mm] (parse) {\cglab{Parse}{read the PDF}};
\node[cgkey, text width=26mm, right=8mm of parse] (index) {\cglab{Index}{store passages}};
\draw[cgedge] (parse) -- (indx);
```

```text
  does-not-compile      figure     ! Package pgf Error: No shape named `indx' is known.
```

Fixed: the arrow names `index`.

```latex
\draw[cgedge] (parse) -- (index);
```

**Fix.** Fix the TeX error it quotes; nothing else was measured.
Cannot be allowed.

### `nothing-measurable`

**Catches.** The figure compiles but names no node, so the geometry
rules had nothing to measure. The target is `figure`. Without it, a
figure where nothing ran would print the same "No findings" line as a
figure where everything ran and passed.

**Why it matters.** The checks read a figure through its named nodes.
In a figure placed entirely by coordinates, an arrow between two
coordinates is not a connector, so the connector rules skip it, and the
node and edge counts read zero. The arrow also stays where it is when a
box moves, so the next edit leaves it pointing at nothing.

Faulty: both boxes are placed `at` a coordinate, and the arrow runs
between two more.

```latex
\node[cgbox, text width=26mm] at (0,0) {\cglab{Parse}{read the PDF}};
\node[cgkey, text width=26mm] at (4,0) {\cglab{Index}{store passages}};
\draw[cgedge] (1.6,0) -- (2.4,0);
```

```text
  nothing-measurable    figure     names no node, so nothing was measured
```

Fixed: the boxes are named, and the arrow joins them by name.

```latex
\node[cgbox, text width=26mm] (parse) at (0,0) {\cglab{Parse}{read the PDF}};
\node[cgkey, text width=26mm] (index) at (4,0) {\cglab{Index}{store passages}};
\draw[cgedge] (parse) -- (index);
```

**Fix.** Name the nodes you draw (`\node (a)`, `child { node (a) ... }`).

### `loads-library-by-hand`

**Catches.** A TikZ library loaded through one of its internal macros
instead of through `\usetikzlibrary`: a test, a clear or a save of
`\tikz@library@<name>@loaded` or `\tikz@node@reset@hook`. The target is
`figure`, and the measurement names the internals the file touches. It
is read from the source, so it holds whether or not the figure
compiles, and a commented-out line is not counted.

**Why it matters.** A figure file is `\input` inside a `figure` float,
and a float is a group. A library loaded there defines its macros
locally but sets its loaded flag globally, so the next figure skips the
load and finds no macros. Clearing the flag to force a reload is worse:
`positioning` adds its placement shift to a global hook on every load,
so the Nth figure in a document shifts every node N times. A
single-chapter render shows nothing wrong; the assembled book does.
The renderer already loads the libraries in the preamble, so the plain
`\usetikzlibrary` line is all a figure needs.

Faulty: a guard tests the internal flag before the house library line.

```latex
\expandafter\ifx\csname tikz@library@positioning@loaded\endcsname\relax%
  \usetikzlibrary{positioning}%
\fi%
\usetikzlibrary{arrows.meta,positioning,fit,backgrounds,calc,shadows.blur}%
```

```text
  loads-library-by-hand figure     tikz@library@positioning@loaded
```

Fixed: the guard is gone, and the house library line stays.

```latex
\usetikzlibrary{arrows.meta,positioning,fit,backgrounds,calc,shadows.blur}%
```

**Fix.** Delete the internal macro; keep the plain `\usetikzlibrary`
line.

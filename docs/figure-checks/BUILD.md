# 🧱 Figure checks: build

Status: **reference.**

The rules about whether a figure can be measured at all.
[README.md](README.md) explains how to read a report and record an
exception. Each rule shows a faulty figure, its report line and the
fixed figure, all real files in [examples/](examples/) that
`tests/test_figure_check_examples.py` compiles. Listings show the
picture only, unless the defect is outside it. The figures look the
same faulty and fixed, or do not render, so there are no pictures.

## 🧭 Rules on this page

Each rule below says what it catches and how to fix it.

### `does-not-compile`

**Catches.** The figure's own TikZ fails to compile. Target: `figure`;
the measurement is TeX's first error line. Every rule that needs the
compiled geometry is then listed under "not measured"
([README.md](README.md#-what-needs-a-compiled-figure) lists them);
source rules such as `focal-count` and the twin rules still run. It
cannot be allowed: there is no deliberate reason for a figure that
does not build, and it takes the whole PDF render down with it.

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
rules had nothing to measure. Target: `figure`. Without it, a figure
where nothing ran would print the same "No findings" line as one that
passed everything. An arrow between bare coordinates is not a
connector, and it stays put when a box moves.

Faulty: boxes and arrow placed by coordinates.

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

**Catches.** A TikZ library loaded through its internal macros instead
of `\usetikzlibrary`: a test, a clear or a save of
`\tikz@library@<name>@loaded` or `\tikz@node@reset@hook`. Target:
`figure`; the measurement names the internals touched. It is read from
the source, and a commented-out line is not counted.

A float is a group, so a library loaded inside one defines its macros
locally but sets its loaded flag globally, and the next figure finds no
macros. Clearing the flag to force a reload is worse: `positioning`
adds its shift to a global hook on every load, so the Nth figure in a
book shifts every node N times, though a single-chapter render looks
fine. The renderer loads the libraries in the preamble, so the plain
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

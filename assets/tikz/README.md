# 📐 TikZ layout scaffolds

One known-good starting file per layout metaphor in
[docs/TIKZ-STYLE.md](../../docs/TIKZ-STYLE.md). That document tells an
author to commit to a metaphor before placing a node; these are what the
choice hands you, so a figure starts from a file rather than from an
empty `tikzpicture`.

| File | Metaphor | Reach for it when |
| --- | --- | --- |
| `pipeline.tex` | Pipeline | the thing is a sequence and the question is "what happens next" |
| `map.tex` | Map | the point is how things compare on two named axes, not how they connect |
| `layered-stack.tex` | Layered stack | the question is what is allowed to depend on what |
| `control-loop.tex` | Control loop | the whole claim is that the cycle closes |
| `branching-tree.tex` | Branching tree | one thing divides into cases and no case rejoins another |
| `hub-and-spoke-network.tex` | Hub-and-spoke network | everything going through one place *is* the claim |

## 🚀 Using one

Copy it beside the draft that needs it and re-label the nodes:

```bash
cp assets/tikz/pipeline.tex content/drafts/<topic>/figures/<name>.tex
```

## 🎨 The palette comes with the file

Every scaffold carries the five `\definecolor` lines of the house
palette ([TIKZ-STYLE.md](../../docs/TIKZ-STYLE.md)) and uses them,
so a copied file is already in house colours and you re-label rather than
re-decide. Keep the block **inside** the figure when you edit it: the
renderer injects only `\usepackage{tikz}`, and a `thesis-chapter-writer`
fragment is `\input` into the user's own thesis, which has never heard
of this project. A figure depending on a colour defined elsewhere
compiles here and fails there.

The roles, in one line each: `cgInk` borders and labels, `cgFlow` the
primary path, `cgAccent` the one thing the figure is about, `cgAlt` a
second class, `cgAux` what happens off to the side. Fills are tints
(`cgFlow!8`); strokes take the colour undiluted.

Then write the ASCII twin at `figures/<name>.txt` and reference the pair
from the draft with a single marker line -- `docs/WRITING-STANDARDS.md`
§10 owns that contract, and your genre skill's figure step spells the
marker for your draft's language.

**A panelled figure is still one file.** Copy the same scaffold once per
panel into a single `tikzpicture` -- or two different ones, if the panels
are different shapes -- and give each panel a `(<letter>) <short title>`
label node, lettered by its position in reading order: `(a)` first,
`(b)` next, on through the alphabet. `docs/TIKZ-STYLE.md`'s "Panels in one figure" section has the
worked example and the rule for a row that stops fitting. These files
carry no `figure` float, so the float and the `\caption` are added to
your copy, not found in it.

Each file carries its own `\usetikzlibrary` line at the top. Keep it:
the renderer's preamble loads `tikz` and no library at all, so a picture
that reaches for `below=4mm of store` without loading `positioning`
fails the *whole* render, with a message naming neither the library nor
the figure.

## ✅ What "known-good" means here

Every scaffold compiles on its own and reports **no binary finding**
from the layout aid:

```bash
python -m chitragupta.review figure content/drafts/<topic>/<draft>.md
```

no node overlap, no protrusion, no node text past the 15-word line. That
is checked by `tests/test_tikz_scaffolds.py` on every run, so a scaffold
cannot quietly rot into one that fails the check it exists to pass. The
same test reads the metaphor table in `docs/TIKZ-STYLE.md`, so adding a
row there without adding a file here fails.

**Every node is named**, and that is load-bearing rather than tidy. The
aid measures geometry only for a node with an explicit `(name)`, so a
picture that names nothing reports zero findings because nothing was
measurable -- which looks exactly like a clean figure and is not one.
Keep the names when you re-label.

## ✏ Editing one without breaking it

The scaffolds place every node relative to another node. None of them
writes a coordinate in millimetres, and that is the property to preserve:
a figure laid out in hand-computed absolute millimetres cannot express
"do not collide", so changing one label's length re-opens every
adjacency in the picture at once.

Three limits worth knowing before you edit:

- **Gaps are bounded by the protrusion check.** A tall empty horizontal
  band -- more than a third of the figure's height with no node in it --
  is reported, because LaTeX sets a figure as a rectangular box and one
  element stranded above the rest wastes every inch beside it. Spreading
  a two-row layout out generously is the usual way to trip this.
- **A containing box is not a collision.** `layered-stack.tex` relies on
  it: a `fit` layer wholly enclosing its members is grouping, which the
  aid exempts, whereas two layers *partially* overlapping is a finding.
- **A tree reports no edges.** `branching-tree.tex` uses `child`, which
  draws its edges internally rather than as `\draw` statements, so the
  aid's edge list comes back empty for it. That is the aid being silently
  short, not the figure being unwired; confirm a tree's structure from
  the source's own nesting.

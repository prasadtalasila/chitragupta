# Comparison

What it argues: **what differs between two things, part by part**. A
before and an after, two approaches to one job, a system with and
without one component.

## When it is the layout

- **Reach for it when** both sides are made of the same parts, so each
  part has a match on the other side, and the point is the row where
  the two differ.
- **Not when** the two sides share a pair of named axes (use [the
  map](map.md)); the parts do not match one for one (that is two
  figures, or a table); or only one part differs and the rest is
  context (a sentence does it, or one pipeline with that part marked
  `cgkey`).

## Anti-patterns

- **Lines between the panels.** The shared row is the match. A line
  across the gap reads as a flow from one approach into the other.
- **Placing panel (b) by its own neighbours.** A part placed `below=`
  the part above it, or `right=` of its match, drifts off its match's
  row as soon as one part is re-worded. Place each at
  `(<column> |- <match>)`, as the scaffold does.
- **Dropping a missing part.** A part one side lacks keeps its row as
  `cgnone`, or every row below it slides out of line and the gap the
  figure is about disappears.
- **More than one accent.** `cgkey` goes on the one part that differs.
  If several differ, the figure is about the whole side, and the panel
  letter already says which side that is.
- **Panels stacked to save width.** Two panels on top of each other
  take twice the height and lose the row the eye reads across. Stack
  only when two columns overflow the target width, and say so in a
  comment in the figure file.
- **A card that fits only the ends.** Fit every part of the panel, or a
  wider part in the middle sticks out of its card.

## Reference ranges

What a typical figure of this layout contains, measured from its
scaffold and its exemplar by the `review figure` probe. This is a
reference for "is mine far from typical?", never a cap.
`tests/test_tikz_scaffolds.py` re-measures every number, so a row moves
only when its source file, or the probe, does; when it fails it prints
the row to paste back.

Nodes counts every named node, zone cards and icon wells included. Edges
counts the `\draw` segments between named nodes that the source parser
reads: a `\foreach` body and a `child` are not read, and a bent path
counts once per leg.

Width and height are fractions of the render's 453pt text width and
700pt text height, and slack is the share of the picture no named node
fills, zone cards excluded. The probe sets the figure in the `article`
class at 12pt in the render's own LuaLaTeX fonts (#1037), so the
fractions are the ones that print.

| Source | Nodes | Edges | Width | Height | Slack |
| --- | --- | --- | --- | --- | --- |
| `assets/tikz/comparison.tex` | 10 | 4 | 0.49 | 0.25 | 0.54 |
| `assets/tikz/exemplars/grounding.tex` | 12 | 6 | 0.60 | 0.38 | 0.47 |

The node counts include the two panel cards and the two letter nodes.
Both figures stay well inside the text width: two panels of one column
each are narrow by nature. The exemplar is set at the render's 453pt
and carries one paper's content; start from the scaffold.

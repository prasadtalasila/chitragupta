# Branching tree

What it argues: **one thing divides into cases and no case rejoins
another**. A taxonomy, a decision, a cascade of alternatives.

## When it is the layout

- **Reach for it when** the structure is a hierarchy and each leaf is
  reached by exactly one path.
- **Not when** the branches route back through one centre (use [the
  hub-and-spoke network](hub-and-spoke-network.md)).

## Anti-patterns

- **A cross-link between branches.** Once two branches meet it is a
  graph; redraw it or drop the link.
- **A fifth leaf in one row at the type floor.** Add a level, not a
  smaller box.
- **Unnamed children.** Name every `child` node or `review figure`
  measures nothing.

## Reference ranges

What a typical figure of this layout contains, measured from its
scaffold by the `review figure` probe. This is a reference for "is mine
far from typical?", never a cap. `tests/test_tikz_scaffolds.py`
re-measures every number, so a row moves only when its source file, or
the probe, does; when it fails it prints the row to paste back. Width
and height are fractions of the render's 453pt text width and 700pt text
height. Slack is the share of the picture no named node fills, zone
cards excluded.

| Source | Nodes | Edges | Width | Height | Slack |
| --- | --- | --- | --- | --- | --- |
| `assets/tikz/branching-tree.tex` | 7 | 0 | 0.62 | 0.20 | 0.65 |

`child` draws its edges internally, so the edge count of a tree is 0
here and the wiring is read from the nesting.

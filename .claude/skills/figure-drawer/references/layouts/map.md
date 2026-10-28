# Map

What it argues: **how things compare on two named axes**, not how they
connect. A trade-off, a quadrant, a classification by two properties.

## When it is the layout

- **Reach for it when** the point is where each thing sits relative to
  the others and every cell is named by its row and its column.
- **Not when** things connect or flow (use [the pipeline](pipeline.md));
  there is only one axis that matters (a sentence or a list does it).

## Anti-patterns

- **Arrows in a map.** A `matrix` draws no edges; if an arrow is needed
  the figure is not a map.
- **Empty cells that are not the point.** An empty quadrant is a finding
  only if the prose says so.
- **Axis heads left out.** The row and column names are what make it a
  map.

## Reference ranges

What a typical figure of this layout contains, measured from its
scaffold by the `review figure` probe. This is a reference for "is mine
far from typical?", never a cap. `tests/test_tikz_scaffolds.py`
re-measures every number, so a row moves only when its source file, or
the probe, does; when it fails it prints the row to paste back.

Nodes counts every named node, zone cards and icon wells included. Edges
counts the `\draw` segments between named nodes that the source parser
reads: a `\foreach` body and a `child` are not read, and a bent path
counts once per leg.

Width and height are fractions of the render's 453pt text width and
700pt text height, and slack is the share of the picture no named node
fills, zone cards excluded. The probe sets the figure in the `article`
class at 10pt Computer Modern, smaller than the render's 12pt, so the
fractions are a lower bound until the probe moves to the render's engine
and fonts (#1037).

| Source | Nodes | Edges | Width | Height | Slack |
| --- | --- | --- | --- | --- | --- |
| `assets/tikz/map.tex` | 9 | 0 | 0.50 | 0.18 | 0.47 |

The scaffold draws no edges, so its edge count is 0 by construction
(`matrix` rows are not `\draw` paths).

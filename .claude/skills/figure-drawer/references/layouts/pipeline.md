# Pipeline

What it argues: **a sequence, and the question is "what happens next"**.
A bottleneck, a lifecycle with a start and an end, a build, a request's
path through a system.

## When it is the layout

- **Reach for it when** the reader follows one path from left to right
  and each stage hands something to the next.
- **Not when** the last stage feeds the first (use [the control
  loop](control-loop.md)), or something comments on points along the
  path (use [the zoned spine](zoned-spine.md)).

## Anti-patterns

- **A retry arrow drawn on a pipeline.** One back edge does not make a
  loop; if closing the cycle is the claim, change the layout.
- **A fifth stage in one row at the type floor.** Wrap a second row;
  never shrink a label.
- **Two accented nodes.** `cgkey` marks the one thing the figure is
  about.

## Reference ranges

What a typical figure of this layout contains, measured from its
scaffold and its exemplars by the `review figure` probe. This is a
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
| `assets/tikz/pipeline.tex` | 5 | 3 | 0.68 | 0.10 | 0.55 |
| `assets/tikz/exemplars/rag-stages.tex` | 11 | 4 | 1.09 | 0.35 | 0.71 |

A bottleneck is the stage the pipeline narrows at; mark it `cgkey` and
say why in the stage's gloss, not in a callout.

`rag-stages` is eleven stages wrapped into three rows of a chain, set at
acmart's 506pt text width: what a long pipeline looks like once it wraps
rather than shrinks. Its eight in-row edges are drawn in a `\foreach`,
which the source parser does not read, so its edge count is the two
wraps, each counted once per leg.

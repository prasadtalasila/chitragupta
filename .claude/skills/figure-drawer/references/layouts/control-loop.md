# Control loop

What it argues: **the cycle closes**. Feedback, a repeating process,
plan-act-observe.

## When it is the layout

- **Reach for it when** the whole claim is that the last step feeds the
  first.
- **Not when** the process has an end (use [the pipeline](pipeline.md));
  the return is a rare retry (it is a pipeline with one back edge).

## Anti-patterns

- **Bending the horizontal edges inward.** The curves then lean into the
  middle and read as a lens, not a cycle; bend them away from the
  centre.
- **A feedback edge as heavy as the forward path.** Draw it `cgweak` so
  the forward path reads first.
- **More than about six nodes.** A loop that long stops reading as one;
  split it.

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
| `assets/tikz/control-loop.tex` | 4 | 4 | 0.50 | 0.13 | 0.53 |

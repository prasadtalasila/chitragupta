# Hub-and-spoke network

What it argues: **everything goes through one place, and that is the
claim**. A broker, a gateway, a single point of failure.

## When it is the layout

- **Reach for it when** removing the centre would disconnect the rest.
- **Not when** branches only divide (use [the branching
  tree](branching-tree.md)); the spokes also talk to each other (the
  centre is not the claim).

## Anti-patterns

- **Spoke-to-spoke edges.** They undo the claim that all traffic crosses
  the hub.
- **A hub that is not `cgkey`.** The centre is the one accented node.
- **Too many spokes for the width.** It needs horizontal room a narrow
  column lacks; check the width first.

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
| `assets/tikz/hub-and-spoke-network.tex` | 5 | 4 | 0.59 | 0.21 | 0.73 |

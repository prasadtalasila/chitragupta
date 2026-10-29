# Layered stack

What it argues: **what is allowed to depend on what**. An architecture
of layers, a protocol stack, abstraction levels.

## When it is the layout

- **Reach for it when** the question is a dependency rule and the figure
  reads top to bottom, each layer calling only the one below it.
- **Not when** the figure is a sequence in time (use [the
  pipeline](pipeline.md) or [the zoned spine](zoned-spine.md)).

## Anti-patterns

- **An arrow from every member to every member.** One arrow between
  layers states the rule; many arrows restate the code.
- **Too little gap between layers.** The lower layer's title sits in it
  and the arrow needs room.
- **A layer of one.** Merge it or say why it stands alone.

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
class at 12pt in the render's own LuaLaTeX fonts (#1037), so the
fractions are the ones that print.

| Source | Nodes | Edges | Width | Height | Slack |
| --- | --- | --- | --- | --- | --- |
| `assets/tikz/layered-stack.tex` | 6 | 1 | 0.42 | 0.21 | 0.65 |

The scaffold's edge count is one: the rule is drawn once, layer to
layer.

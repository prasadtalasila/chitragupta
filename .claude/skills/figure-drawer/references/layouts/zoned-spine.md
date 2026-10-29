# Zoned spine

What it argues: **one storyline, with parallel commentaries on points
along it**. A trust boundary, which stages are deterministic and which
are gated, an architecture with a single entrance and a single exit.

## When it is the layout

- **Reach for it when** a path carries the argument and zone cards say
  something about groups of its members.
- **Not when** nothing comments on the path (use [the
  pipeline](pipeline.md)); the zones are the whole claim and nothing
  flows (use [the layered stack](layered-stack.md)).

## Anti-patterns

- **Zone titles that name a category, not a claim.** The card exists to
  carry what the caption would otherwise say.
- **Overlapping zone cards.** A member belongs to one zone.
- **A card painted over a member.** Cards go on the background layer.
- **A wide grid at the render's full width pasted into a narrow column.** The
  exemplars are set at 453pt; re-lay them out, never scale.

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
| `assets/tikz/zoned-spine.tex` | 8 | 5 | 0.74 | 0.16 | 0.68 |
| `assets/tikz/exemplars/architecture.tex` | 14 | 9 | 0.99 | 0.35 | 0.72 |
| `assets/tikz/exemplars/retrieval.tex` | 15 | 12 | 0.98 | 0.51 | 0.76 |

The exemplars are set at the render's 453pt text width, which is why
they come close to the full width here, and they carry one paper's content.
Start from the scaffold; read the exemplars for what a figure of this
size holds. `retrieval` is the two-storyline edge case: two zones, each
with its own route, that never meet.

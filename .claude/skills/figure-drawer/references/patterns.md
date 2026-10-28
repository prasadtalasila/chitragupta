# figure-drawer: patterns

Choose what the figure *argues* before choosing how it is laid out. A
pattern is the claim; a layout is the grammar that draws it. Name the
pattern first, find its row below, and read that layout's reference file
before copying its scaffold.

A pattern routes to the **nearest existing layout** and never adds one.
A new layout is justified only by a new layout grammar (a new way of
placing nodes), not by a new pattern: a bottleneck, a lifecycle and a
request path are three patterns and one grammar, the pipeline. Where no
layout is near enough, say so to the caller and consider whether the
figure is warranted at all.

## Pattern to layout

| Pattern: the figure argues... | Layout | Tell |
| --- | --- | --- |
| a lifecycle with a start and an end | [Pipeline](layouts/pipeline.md) | each stage hands something to the next |
| a bottleneck in a sequence | [Pipeline](layouts/pipeline.md) | one stage is the narrow one, marked `cgkey` |
| a request's or a build's path | [Pipeline](layouts/pipeline.md) | the reader asks "what happens next" |
| a cycle that closes, a feedback | [Control loop](layouts/control-loop.md) | the last step feeds the first |
| a trust boundary | [Zoned spine](layouts/zoned-spine.md) | a path crosses from one zone to another |
| which stages are fixed and which are generated or gated | [Zoned spine](layouts/zoned-spine.md) | zone cards comment on points along one path |
| a dependency rule | [Layered stack](layouts/layered-stack.md) | each layer calls only the one below |
| levels of abstraction | [Layered stack](layouts/layered-stack.md) | reads top to bottom |
| a taxonomy, a decision, cases | [Branching tree](layouts/branching-tree.md) | one thing divides and no case rejoins another |
| a single point everything crosses | [Hub-and-spoke network](layouts/hub-and-spoke-network.md) | removing the centre disconnects the rest |
| a trade-off on two axes | [Map](layouts/map.md) | where things sit matters, not how they connect |
| two alternatives compared | [Map](layouts/map.md), or two panels | one shared pair of axes; else panels (`figures.md` §2) |

## Three that look alike

- **Bottleneck or hub?** A bottleneck is one narrow stage in a sequence
  (a pipeline). A hub is a place every path crosses with no sequence
  (a hub-and-spoke).
- **Lifecycle or loop?** A lifecycle ends. If the last state returns to
  the first, the loop is the claim.
- **Trust boundary or layers?** A trust boundary is crossed in time along
  a path (a spine). A layered stack states what may call what, with no
  path.

## When no row fits

A figure whose pattern has no row is often not one figure: an overview
and a detail drawn together want two. It may also be a sentence or a
table, which `SKILL.md` asks about before any drawing. Tell the caller
rather than forcing the nearest layout.

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
| a lifecycle with a start and an end | [Pipeline](layouts/pipeline.md) | each stage hands something to the next; at most one retry goes back |
| a lifecycle where a state stays put, or is sent back by more than one event | [State machine](layouts/state-machine.md) | it is in one state at a time, and events move it |
| an automaton, a protocol's states, a Markov chain | [State machine](layouts/state-machine.md) | every arrow is an event or a probability |
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
| two alternatives compared on shared axes | [Map](layouts/map.md) | one pair of named axes places both |
| a before and an after, or two approaches part by part | [Comparison](layouts/comparison.md) | each part has a match on the other side, and one differs |

## Two that look alike

- **Bottleneck or hub?** A bottleneck is one narrow stage in a sequence
  (a pipeline). A hub is a place every path crosses with no sequence
  (a hub-and-spoke).
- **Loop or state machine?** A loop's nodes are stages that all run on
  every pass. A state machine's nodes are conditions, and only one holds
  at a time.
- **Pipeline or state machine?** One retry arrow drawn back is still a
  pipeline (`figures.md` §1). A state that stays put, or several ways
  back, make it a state machine: the moves are the claim, not the path.

The layout pairs people confuse (pipeline or loop, pipeline or spine,
tree or hub, stack or spine) are in `figures.md` §1.

## When no row fits

A figure whose pattern has no row is often not one figure: an overview
and a detail drawn together want two. It may also be a sentence or a
table, which `SKILL.md` asks about before any drawing. Tell the caller
rather than forcing the nearest layout.

# Sequence

What it argues: **the order of the exchanges between parties is the
claim**. A protocol, a handshake, a cache miss, a request and the calls
it sets off, who waits on whom.

## When it is the layout

- **Reach for it when** two or more parties pass messages and the
  reader's question is "who says what to whom, and in what order". Time
  runs down the page; each party keeps its own column.
- **Not when** each party only hands work on to the next and nothing
  comes back (use [the pipeline](pipeline.md)), or what matters is the
  state a system is in rather than who talks to it (use [the state
  machine](state-machine.md)), or when things happen and how far apart
  is the claim, with no one talking to anyone (use [the
  timeline](timeline.md)).

## Anti-patterns

- **A message drawn on a slant to show delay.** Every message is level
  at its own moment; a delay is a gap between moments, or a `cgnote`.
- **More than four parties at the type floor.** Three fit the article
  class's 345pt and four the render's 453pt; past that, split the
  exchange into two figures. Never shrink a head.
- **A self-message loop where a note would do.** A loop from a lifeline
  back to itself joins a node to itself, so no connector rule measures
  it; a `cgnote` beside the lifeline says the same and is checked.
- **Lifelines drawn as bare lines with messages between coordinates.**
  The figure then passes `figure check` only because nothing in it is a
  connector. Keep the scaffold's lifeline nodes.

## Reference ranges

What a typical figure of this layout contains, measured from its
scaffold and its exemplars by the `review figure` probe. This is a
reference for "is mine far from typical?", never a cap.
`tests/test_tikz_scaffolds.py` re-measures every number, so a row moves
only when its source file, or the probe, does; when it fails it prints
the row to paste back.

Nodes counts every named node, the lifeline nodes included, so a
sequence counts each party twice. Edges counts the `\draw` segments
between named nodes that the source parser reads, which here are the
lifelines and the messages.

Width and height are fractions of the render's 453pt text width and
700pt text height, and slack is the share of the picture no named node
fills, zone cards excluded. A sequence is mostly empty by design: the
messages run through space, not through boxes, so its slack is high.
The probe sets the figure in the `article` class at 12pt in the
render's own LuaLaTeX fonts (#1037), so the fractions are the ones that
print.

| Source | Nodes | Edges | Width | Height | Slack |
| --- | --- | --- | --- | --- | --- |
| `assets/tikz/sequence.tex` | 6 | 8 | 0.74 | 0.26 | 0.85 |
| `assets/tikz/exemplars/figure-check.tex` | 8 | 10 | 0.93 | 0.30 | 0.84 |

`figure check` waives `c4-attach` and `c5-transit` for this layout:
messages meet a lifeline wherever time puts them, and a message may
pass over the lifelines between its ends. It still holds every message
to `c1-orthogonal`, `c2-tag-clearance`, `c3-coincident` and
`c7-dangling-tip`.

`figure-check` is one `figure check` run with four parties at the
render's 453pt: the figure-drawer skill, the check, the LuaLaTeX probe
and the ASCII twin. Every head takes one text width, so each sets on two
lines and the lifelines start level.

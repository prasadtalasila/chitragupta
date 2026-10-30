# State machine

What it argues: **it is in one state at a time, and events move it**.
A lifecycle that can go back, a protocol's states, an automaton, a
Markov chain.

## When it is the layout

- **Reach for it when** a state can recur, stay put, or be sent back,
  and each move has an event or a probability that names it.
- **Not when** nothing goes back but one retry (use [the
  pipeline](pipeline.md));
  every node runs on every pass (use [the control loop](control-loop.md):
  its nodes are stages, a state machine's are conditions).

## Anti-patterns

- **A state named with a verb.** A state is a condition the thing is
  in (`review`), not an action it does; the action is the transition.
- **An unlabelled transition.** The event or probability is what the
  figure says; an arrow without one says nothing.
- **Both directions of a pair on one line.** Draw two transitions, bent
  apart with `bend left` on each, so each has its own arrowhead and tag.
- **More than about six states.** At that size the transition table,
  the twin, is the clearer figure; put the table in the text instead.
- **Two accented states.** At most one `cgkeystate`, and only when the
  figure is about that state.

## The twin is a table

The `.txt` twin is a transition table, `from | on | to`, under a line
naming the initial and accepting states, not an ASCII drawing of the
circles. A self-loop or a curved pair draws badly in characters, and
the table is the more precise form of the same information.

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
| `assets/tikz/state-machine.tex` | 4 | 6 | 0.68 | 0.27 | 0.82 |
| `assets/tikz/exemplars/pump-markov-chain.tex` | 3 | 7 | 0.47 | 0.31 | 0.83 |

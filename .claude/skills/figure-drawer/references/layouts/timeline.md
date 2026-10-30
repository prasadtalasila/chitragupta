# Timeline

What it argues: **when things happen, and how far apart, is the
claim**. An incident from fault to all clear, a simulation clock that
jumps from event to event, a release history, the stretches a system
spends in one mode before the next.

## When it is the layout

- **Reach for it when** the reader's question is "when, and how long
  between": the gaps carry the argument, so each event sits at its own
  fraction of one time axis, and eras mark stretches of time in a band
  below it.
- **Not when** only the order matters and nothing is said about how far
  apart (use [the pipeline](pipeline.md)), or parties pass messages to
  each other in turn (use [the sequence](sequence.md)).

## Anti-patterns

- **One axis line drawn under the ticks.** It crosses every tick, and
  `figure check` reports `c5-transit` once per event. Draw the axis tick
  to tick, as the scaffold does, so each piece is a connector.
- **Events placed with `right=` or at even steps.** The gaps then say
  nothing, which is the one thing the layout is for. Place each tick at
  its fraction, `($(t0)!<f>!(tend.west)$)`; for a log-scaled axis,
  compute the fractions from `log10` of the times.
- **Eras fitted around the events in them.** A card's edges then sit
  wherever a label ends and disagree with the axis. Fit each card
  between two times, `fit=(b1 |- band)(b2 |- band)`.
- **A label turned the other way.** TikZ counts angles anticlockwise:
  `rotate=90, anchor=east` reads bottom to top and ends at its tick;
  `rotate=-90` reads top to bottom and is the wrong one.
- **A label touching its tick.** Hang it 1mm below
  (`at ([yshift=-1mm]e3.south)`). `node-overlap` reports a label set
  into its own tick, but not one that only touches it, so keeping the
  gap is up to you.
- **An era title wider than its card.** `node-overlap` reports it
  against its card and the next one. Give a narrow era a short title,
  or move its title to a second row under the band; never turn a title
  or shrink it.
- **Two accented events.** A tick cannot take `cgkey`, a 24mm card, so
  the scaffold's `cgfocus` accents the one event the figure is about;
  `focal-count` counts it with `cgkey`, so a second one is reported.
- **More than about eight events at the type floor.** Five fit the
  article class's 345pt with room between labels, and six the render's
  453pt; past that, split the span into two figures.

## Reference ranges

What a typical figure of this layout contains, measured from its
scaffold and its exemplars by the `review figure` probe. This is a
reference for "is mine far from typical?", never a cap.
`tests/test_tikz_scaffolds.py` re-measures every number, so a row moves
only when its source file, or the probe, does; when it fails it prints
the row to paste back.

Nodes counts every named node: the ticks, the axis ends, the labels,
the era cards and their titles. Edges counts the `\draw` segments
between named nodes that the source parser reads, which here are the
pieces of the axis.

Width and height are fractions of the render's 453pt text width and
700pt text height, and slack is the share of the picture no named node
fills, zone cards excluded. A timeline is mostly empty by design: the
gaps between events are the content. The probe sets the figure in the
`article` class at 12pt in the render's own LuaLaTeX fonts (#1037), so
the fractions are the ones that print.

| Source | Nodes | Edges | Width | Height | Slack |
| --- | --- | --- | --- | --- | --- |
| `assets/tikz/timeline.tex` | 16 | 6 | 0.74 | 0.14 | 0.87 |
| `assets/tikz/exemplars/next-event.tex` | 20 | 7 | 0.94 | 0.19 | 0.89 |

`figure check` exempts no rule for this layout. The axis is drawn tick
to tick, so `c1` to `c7` hold every piece of it, and a label turned a
quarter is measured like any other node.

`next-event` is next-event time advance for one server and one queue at
the render's 453pt: six events, three eras that change only at an
event, and a narrow idle era whose title is one word so that it fits
its card.

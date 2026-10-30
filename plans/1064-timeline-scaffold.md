# ⏱️ XII-3e: the timeline scaffold

Status: **built** in this PR. Written 2026-10-30 against `main` at `dad488b`, from
a brainstorming session on issue
[#1064](https://github.com/prasadtalasila/chitragupta/issues/1064). It
ships in the same PR as the code, as #1063's plan did. Decisions marked
*user* were agreed in that session. The rest are the session's proposal.

**Written for** whoever builds #1064: a session that changes
`chitragupta/figure/`, `chitragupta/review/figure_layout/`,
`assets/tikz/`, the three copies of the `figure-drawer` skill, `tests/`
and `docs/`. That session is governed by `DEVELOPER-AGENTS.md` and
`docs/CODE-STANDARDS.md`.

**Assumed:** `plans/fig-xii-figure-drawer-v3.md` (Phase 3),
`plans/1054-connector-rules.md` (c1 to c7, `node-overlap` over every
drawn node), `plans/1057-figure-check-size.md` (`% cg-layout:` and
reference ranges) and `plans/1063-sequence-scaffold.md` (the shape of a
scaffold PR, and the lists it keeps in step).

**Not covered here:** a duration bracket between two events (the
`|<-- detection gap -->|` of `decision-latency`), a log-scaled axis, a
vertical timeline, and turning an era title by hand or by macro (see
"Left out"). The other phase-3 scaffolds are done or closed: quadrant
(#1060, closed not planned), comparison (#1095), state machine (#1096)
and sequence (#1100).

## What it is for

The v3 plan ranks this for chapter 7's time-axis figures. In the
reference book's `two-time-advances`, `three-windows`, `decision-latency`
and `rtf-regimes`, **the size of the gaps is the argument**: "the clock
jumps; the gaps cost nothing" needs the gap from e2 to e3 to look longer
than the one from e3 to e4. No current layout places a node by time. A
figure drawn today starts from a pipeline, loses the proportions, and is
then hand-placed in millimetres, which is the defect this epic removes.

## What the probe found

Before the design, throwaway figures were run through
`figure check --width 345`, declared as `pipeline` so every connector
rule applied, and pictured with `figure look` (scripts in the session's
scratchpad, not kept):

1. **Fraction placement is read.** An event placed
   `at ($(t0)!0.58!(tend.west)$)` is declared and measured; nothing is
   reported unmeasured. Proportional placement is relative placement,
   so TIKZ-STYLE's "no node at a coordinate in millimetres" holds with
   no change to the rule.
2. **The axis must be a chain.** Drawn tick to tick
   (`t0 -- e1 -- ... -- e5 -- tend`), it is six connectors and reports
   no c1 to c7 finding, c4 included, on 0.9mm ticks. Drawn as one line
   under the ticks, it fires `c5-transit` once per tick. So no rule
   exemption is needed, unlike `sequence`.
3. **Level labels of close events collide, and the collision is
   caught.** Labels "arrival" and "departure" at 0.58 and 0.66 of the
   axis fire `node-overlap e3-n+e4-n`. Moving one below the axis clears
   it and fires `node-overlap` against the era band instead.
4. **Turned labels are not measured at all.** With the labels turned a
   quarter, two labels set over each other and into the band report
   nothing, and a clean turned figure reports a false
   `content-protrusion`. `_overlap.py` and `_clearance_rules.py` set
   aside every node whose transform turns it, and the probe logs a
   quarter-turned node's box as a single point (see "The measurement
   fixes").
5. **An era title that leaves its card is not reported.** A narrow era
   (0.02 to 0.10 of the axis) titled "start-up phase" ran across the
   next card and `figure check` said nothing. The cause:
   `_connectors.zones()` classes any node whose box contains another as
   a zone card, and the title's box covered the zero-size `band`
   coordinate, so `_overlap._is_ink` dropped the title as "an unframed
   node that only groups others". Any unframed label that happens to
   cover a `\coordinate` goes unchecked the same way.
6. **Width.** A 108mm axis and its "time" label fit 345pt; 112mm went
   1.6pt over.

TikZ counts angles anticlockwise. `rotate=-90` turns text clockwise, so
it reads top to bottom; the probe's first try did that by mistake. The
turn agreed here reads bottom to top, as a chart's axis labels do:
`rotate=90, anchor=east`, the word ending at its tick.

## Decisions

| # | Decision | Why |
| --- | --- | --- |
| D1 | Events are placed in proportion to time, by fraction between the axis ends (*user*) | The gaps carry the argument in every chapter 7 figure; fraction placement keeps the figure relative |
| D2 | An era is an interval with its own boundaries at fractions, not a `fit` around events (*user*) | Its edges are then times, so they agree with the axis |
| D3 | Eras sit in a band of cards below the axis, not around it (*user*) | Time and eras read as two layers, and the figure stays distinct from a zoned spine |
| D4 | The exemplar draws next-event time advance (*user*) | The figure that motivated the layout, and close events are its hardest case |
| D5 | Every event label is turned to read bottom to top, `rotate=90, anchor=east` (*user*) | Close events with long labels collide when level; one orientation keeps the axis uniform |
| D6 | Era titles stay level and must fit their card; a narrow era takes a short title or its title moves to a second row under the band (*user*, option A) | Turning a title makes the band as tall as the longest title; turning only some mixes orientations |
| D7 | `figure check` measures quarter-turned nodes, and `zones()` ignores coordinates. Both ship in this PR (*user*) | Without them D5 and D6 pass because nothing is measured |
| D8 | The axis is a chain of segments; `timeline` exempts no rule | Probe finding 2 |
| D9 | The tick, axis and label styles live in the picture's options | No house-block bump and no `figure sync` churn, as #1063's D4 |
| D10 | No `\foreach` in the scaffold or the exemplar | The source parser reads a loop variable as a name (#1063, finding 3) |
| D11 | MINOR version bump | A new layout `figure new` offers, and a measurement change |

## The scaffold

`assets/tikz/timeline.tex`:

- **Header.** `% cg-layout: timeline`. The metaphor paragraph says: when
  things happen, and the gaps between them, are the claim; if only the
  order matters, it is a pipeline. The idiom paragraph says that each
  event is a tick placed by fraction of the axis, that the axis is drawn
  tick to tick, that labels read bottom to top below their ticks, and
  that each era is a card fitted between two times in a band below.
- **House block** v6, copied verbatim.
- **Picture options:**
  - `cgtick`: `inner sep=0pt, outer sep=0pt, minimum width=0.9mm,
    minimum height=3.2mm, fill=cgInk, draw=none`.
  - `cgaxis`: `draw=cgInk, line width=0.85pt, shorten <=0pt,
    shorten >=0pt`, so the segments meet at each tick.
  - `cgevent`: `font=\normalsize, inner sep=1pt, text=cgInk`.
- **Content.**
  - `t0`, a tick, and `tend`, the word "time", placed
    `right=108mm of t0`.
  - Five events `e1` to `e5`, each
    `\node[cgtick] (e3) at ($(t0)!0.58!(tend.west)$) {};`, with uneven
    gaps and two events close together.
  - Each label
    `\node[cgevent, rotate=90, anchor=east] (e3-n) at ([yshift=-1mm]e3.south) {...};`.
  - The axis, `\draw[cgaxis] (t0) -- (e1);` and so on, the last segment
    `(e5) -- (tend)` carrying the arrowhead with `shorten >=1.5pt`.
  - Era boundaries `\coordinate (b1) at ($(t0)!0.02!(tend.west)$);`, a
    `band` coordinate below the longest label, and on the background
    layer one `cgzone` per era,
    `fit=(b1 |- band)(b2 |- band), inner xsep=0pt, inner ysep=4mm`, with
    a gap between neighbouring cards. Each title is a `cgevent` node at
    its card's centre, in the card's `Text` shade.
- **Width.** Fits the article class's 345pt, as every scaffold must; the
  exemplar takes the render's 453pt.

`assets/tikz/timeline.txt` is in the style of `two-time-advances`: an
axis `----|-----|---...---> time` with each tick at its proportional
column, the labels on staggered rows above it (ASCII cannot turn text),
and the band as `[== busy ==]` at matching columns. It is 7-bit ASCII
and at most 72 columns, and every name and title appears in it word for
word (t1).

`assets/tikz/exemplars/next-event.tex` and `.txt` draw next-event time
advance for a single-server queue at 453pt, `% cg-layout: timeline`:
six events at uneven times (three arrivals, three departures, two of
them close), and eras "server busy" and "server idle", one of them
short enough that its title has to be checked against its card. Labels
are at most three words and titles at most two. The wording is checked
against the queue's own semantics when it is drawn: a departure never
precedes the arrival it serves, and the server is idle exactly when the
queue is empty.

### Left out

- **A duration bracket** between two events. It is a two-headed
  connector under the axis; the probe did not test it against c1 to c7,
  and no scaffold needs it. A reference-file note says to state a gap in
  a `cgnote` until one is built.
- **A log-scaled or broken axis.** Fractions are linear; a log axis
  places its ticks by `log10` fractions the author computes, which the
  reference file mentions and the scaffold does not draw.
- **Turning an era title**, by hand or by a house macro. Considered as
  option C and set aside: one turned title makes the whole band 20 to
  25mm tall, and a macro means a house-block bump and a two-pass layout.

## The measurement fixes (D7)

**Quarter turns.** Measured on the probe figure, a label set
`rotate=90` is logged today as a point: its box is
`[179.0, -25.3, 179.0, -25.3]`, and its text box sits beside the tick,
not below it. The cause is in `assets/latex/cg-figure-probe.tex`'s
`\cgdumpnodes`: it keeps only the x of the `west` and `east` anchors and
the y of `south` and `north`. Turned a quarter, `west` and `east` share
an x and `south` and `north` share a y.

- **The probe** logs both coordinates of all four side anchors. The
  grammar in `_drawn.py`'s docstring changes with it.
- **`_drawn._node`** takes the box as the min and max over those four
  points. For an unturned node this is the box it reads today; for a
  quarter turn it is exact.
- **The text box** is turned about the `text` anchor by the node's
  rotation entries, where `b` and `c` are ±1 within 1e-4 (a quarter
  turn either way).
- Such a node is no longer `rotated`. Any other angle (`sloped`) keeps
  `rotated=True` and stays set aside, as today, because the min and max
  of a slanted box is larger than its ink.

Consumers that read `rotated` need no change: `_overlap._is_ink` and
`_clearance_rules._tags` now see a quarter-turned node as ordinary.
`content-protrusion` fired on the clean turned probe figure; the
implementation confirms that the false positive is gone once the box is
right, and traces it if it is not.

**Coordinates are not members.** `chitragupta/figure/_connectors.py`'s
`zones()` skips any `other` whose shape is `coordinate` when it decides
whether a node contains another. A point inside a box does not make the
box a group.

**Ripple.** Both fixes change what `review figure` and `figure check`
report on figures that exist. Before merging, `figure check` runs over
every scaffold and exemplar and `review figure` over the 49 reference
drafts, before and after, and the PR body lists every finding that
appears or disappears. A finding that appears is real by construction
(something that was unmeasured is now measured), and is left for the
figure's next redraw, as the v3 plan's Migration section says.

## Tests

- **Must-fire fixtures** under `tests/fixtures/figure/check/`:
  - `turned-collide.tex`: two quarter-turned labels at nearly the same
    time, running into the band. Fires `node-overlap` on the two labels
    and on the label and card. Fails today.
  - `title-over-coordinate.tex`: a level title wider than its card,
    covering a coordinate. Fires `node-overlap` with its own card and
    its neighbour. Fails today.
- **Must-not-fire fixture**, `turned-clean.tex`: quarter-turned labels
  clear of each other and of the band report no `node-overlap` and no
  `content-protrusion`.
- **A sloped tag stays set aside**: a unit test on `_node` that a
  45-degree transform still sets `rotated`.
- `tests/test_figure_check.py`: `timeline` added to the hard-coded
  scaffold lists, as #1063 added `sequence`.
- Picked up by their globs with no edit: `test_tikz_scaffolds.py` (the
  table and directory cross-check, reference ranges re-measured, source,
  geometry, glyph size and twin properties), `test_figure_new.py`,
  `test_figure_sync.py`, `test_figure_contrast.py`,
  `test_figure_reference_ranges.py` and `test_figure_stray_width.py`.
- `test_figure_rule_gallery.py` re-run: the gallery's panels must not
  change verdict under D7.
- Line and branch coverage stay at 100%. The full suite runs, because
  the repo-wide scans run inside it.

## Docs and lists kept in step

- `docs/TIKZ-STYLE.md`:
  - a metaphor-table row, `| Timeline | ticks placed by fraction along
    one chained axis, eras as banded cards |` (no `\|` in a cell; it
    breaks `test_tikz_scaffolds.py`'s parser), and a prose paragraph
    beside the sequence's;
  - in the rules section, that a quarter-turned node is measured and a
    sloped one is not, and that a coordinate never makes a card.
- `.claude/skills/figure-drawer/references/layouts/timeline.md`:
  - What it argues: when things happen, and the gaps between them;
  - When it is the layout (Not when: only the order matters, use the
    pipeline; parties exchange messages, use the sequence);
  - Anti-patterns: one axis line under the ticks; events placed with
    `right=`, which loses the proportions; eras fitted around events;
    labels turned clockwise; an era title wider than its card; more
    than about eight events at 345pt;
  - Reference ranges, measured, with two rows, the scaffold and the
    exemplar.
- `references/patterns.md`: the route row "when things happen, and how
  far apart → Timeline".
- `references/layouts/pipeline.md` and `sequence.md`: Not when links to
  timeline.
- `references/check.md`: the quarter-turn and coordinate sentences where
  it describes what `node-overlap` skips.
- `references/figures.md` and `assets/tikz/README.md`: the layout tables
  and counts (eleven layouts, and the exemplar count).
- The three `figure-drawer` SKILL.md copies: the layout list, under the
  8,000-byte cap `tests/test_skill_figure_router.py` holds.
- `docs/FIGURE-DRAWER.md`: an eleventh column in the rule-relevance
  table, every cell "applies".
- `docs/CLI.md`: `timeline` in `--layout`'s values.
- `plans/fig-xii-figure-drawer-v3.md`: a 3e paragraph under Phase 3,
  beside 3b and 3d.

## Shipping

One PR off `main` holds this plan and the code. Its body says
`Closes #1064` and lists the ripple. Before opening it, and again before
merging, fetch `main` and re-check the version and the files that
overlap, because parallel sessions land v3 items there. If the version
collides, merge `origin/main` in and bump again; never amend or
force-push.

## Success criteria

- [ ] Row in TIKZ-STYLE.md's metaphor table, cross-checked by
      `tests/test_tikz_scaffolds.py`
- [ ] Scaffold and exemplar clean under `figure check`, with no
      `cg-allow`
- [ ] Both must-fire fixtures fire, and fail on `main`
- [ ] Ripple over the scaffolds, exemplars and 49 reference drafts
      recorded in the PR body
- [ ] Line and branch coverage stay at 100%
- [ ] No citekey generated, guessed or rewritten, and no check promoted
      into a gate

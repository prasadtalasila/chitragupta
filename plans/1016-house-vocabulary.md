# 🏠 #1016: teach `figure check` the house vocabulary

Status: **built.** Written 2026-10-30 against `main` at `520dac7` (#1058
merged as #1102), from a brainstorming session on issue
[#1016](https://github.com/prasadtalasila/chitragupta/issues/1016) and
the bench and spike recorded under **What the bench found**. Implemented
in the same PR as this plan. Decisions marked *user* were agreed in that
session; the rest was the session's proposal. What changed on the way
goes under **Changed in the build** at the end.

**Written for** whoever builds #1016: a session that changes
`chitragupta/figure/`, `chitragupta/review/figure_layout/`,
`assets/latex/cg-figure-probe.tex`, the `figure-drawer` skill, `tests/`
and `docs/`, and is therefore governed by `DEVELOPER-AGENTS.md` and
`docs/CODE-STANDARDS.md`.

**Assumed:** `plans/fig-xii-figure-drawer-v3.md` (the rules),
`plans/1053-figure-check-skeleton.md` (the registry, `cg-allow`, the
report), `plans/1055-contrast-and-wording.md` (the probe's `CGPAINT` and
`CGTEXT` lines this reads) and `plans/1058-element-allow.md` (element
targets, quoted targets, stale allows).

**Not covered here:** redrawing the draft figures the new rules fire on,
and every finding listed under **Dropped**.

## The problem, in one example

```latex
\begin{tikzpicture}[cg]
  \node[cgbox, fill=cgFlow!45] (parse) {\scriptsize Parse};
  \node[draw=blue, right=of parse] (index) {Index};
  \pic at (0,1.5) {cgstore};
\end{tikzpicture}
```

The house block (`assets/tikz/cg-figstyle.tex`) gives a figure named
colours, tints between 6 and 12, one type size and a well for every
`pic`. Nothing reported a figure that loads it and then writes past it:
a dark tint the label drowns in, a hue nobody chose, type below the
floor, and a drum `node-overlap` cannot see because no node holds it.
The issue listed thirteen findings like these; most have since shipped under
other names, and this item builds the four that had not.

## How #1016's findings stand

| #1016 finding | Where it is now |
| --- | --- |
| `accent-not-unique` | `focal-count` (#1080) |
| `gloss-too-long` | `w3-gloss` (#1055), six words, advisory |
| `zone-member-protrudes`, `zone-overlap`, `title-collision` | `node-overlap`, which since #1054 runs over every drawn node, zone titles included, and exempts containment only; fixtures here prove each case |
| the protrusion relaxation | already holds: a zone's own box counts as filled, so the channel inside a zoned layout is not an empty band; fixtures here prove a two-row zoned layout is silent and a stranded node is not |
| `type-below-floor` | **built here** |
| `colour-off-palette` | **built here** |
| `raw-node-in-styled-figure` | **built here**, folded into `colour-off-palette` (*user*) |
| `tint-outside-band` | **built here** |
| `unnamed-pic` | **built here** |
| `figure-scaled`, `effective-type-size` | **dropped** (*user*) |
| `shadowed-dash`, `legend-swatch-mismatch` | **dropped** (*user*) |
| `\centering` | shipped as #1085 |

## Decisions

- **Four rules in `figure check`, keeping #1016's names** (*user*), so
  the issue, the docs and a finding say one thing. Each is objective,
  element-scope and allowable. The command still exits 0, and the house
  block stays at v6.
- **`type-below-floor` reads the size TeX set, not the source.** The
  probe's `CGTEXT` runs carry each glyph run's size from the typeset box,
  so `\scriptsize`, a size inherited from a group and a macro that
  expands to one are all seen. The floor is the probe document's body,
  12pt (`_probe.py`'s `[12pt]`), the size the render sets.
- **A math run is exempt, unless it is all the node has.** A subscript
  in `$k_1$` sets at script size, and that is typesetting, not a shrunk
  label. The probe's Lua walk marks a run as math when its glyphs come
  from a font with math constants, a new field on `CGTEXT`. A node fires
  when a text run is below the floor, or when its largest run is, so a
  label set all in math under `\scriptsize` still fires.
- **"House colour" is read from the figure's own block**: every
  `\definecolor` and `\colorlet` inside its
  `% >>> chitragupta figure style` region, plus `white`.
- **Both colour rules decide by the colour pgf used, not by what was
  written.** A colour is on the palette when it is a house colour, or a
  house colour mixed with white at a whole-number share, which is what
  every tint is. The written expression is only how a finding names it.
  This is one rule for every spelling: `\c Text` (a `\foreach`
  variable) and `\cgPicColour!55` reach the log unexpanded, and need no
  fallback. `black` is off the palette (the house black is `cgInk`), and
  so is a hue darkened by hand (`cgFlow!45!cgInk`): a shade nobody chose.
- **A framed node with an unwritten stroke is a raw node.** The
  `raw-node-in-styled-figure` case: `\node[draw]` strokes in the current
  colour, which the log shows as no expression. Reported under
  `colour-off-palette` as `border (current colour)`.
- **What `colour-off-palette` reads:** a node's border, fill and text
  runs, and every stroked line, a `pic`'s outline included. A line is
  named by its connector name where it joins two nodes, and by its first
  point otherwise. A path's fill outside a node is not logged per line,
  so a raw `\fill[red]` is not seen: a stated limit.
- **A figure without the house block** has both colour rules listed as
  not measured ("no house block"), not a finding on every colour it uses.
- **`tint-outside-band` reads framed node fills only.** A fill that is a
  house hue (a name with `Line` and `Text` shades) mixed with white
  outside 6 to 12, the bare hue, or its `Line` or `Text` shade, fires,
  read from the fill's colour as the palette rule reads it.
  A `pic`'s inner fills are texture, and a round node under 7mm (the
  step badge, a `Text`-shade disc) is exempt, as in `node-overlap`.
- **`unnamed-pic` reads the source.** A `\pic` fires unless it is placed
  `at` a node the figure declares with `cgwell`. Its target is the pic
  and where it was put, `"cgstore at (0,1.5)"`, quoted in an allow.
- **`focal-count` moves into the same module** (`_house.py`), because
  `_check.py` sits at 249 of its 250 code lines and the new wiring has
  to come from somewhere. It is house vocabulary too: the accent.
- **MINOR bump.** New rules; nothing removed.

## Dropped, and why

- **`figure-scaled` and `effective-type-size`** (*user*: "a corner
  case"). The pipeline's render never scales; `figures.md` §3 and
  TIKZ-STYLE.md tell every drafting skill never to; `size-width` already
  reports the overflow that tempts a scale. What is left is a person
  wrapping a figure by hand, in a document the figure's compile never
  sees. `docs/RENDERING-FLOW.md` records the renderer's side as a
  decision: it never gains a scale knob.
- **`shadowed-dash`**: the block's dashed styles (`cgnone`, `cgopt`)
  already cancel the shadow, and the log carries neither dash nor
  shadow, so it would mean extending the probe for a cosmetic defect.
- **`legend-swatch-mismatch`**: cosmetic, and no figure has shown it.

## What the bench found

Run 2026-10-30 over the 10 scaffolds, the 4 exemplars and 5 draft
figures, reading the probe's log directly:

- Every scaffold and exemplar sets its text at 12pt, except
  `exemplars/retrieval.tex`'s `$k_1{=}1.5$`, whose subscript sets at
  8.4pt. A rule blind to math would fire on a shipped exemplar.
- Draft figures set `\small` (10.95pt) labels with 8pt and 6pt
  subscripts beside them.
- Every scaffold and exemplar fill is a tint between 6 and 11, `white`,
  `cgPaper`, or a `Text` shade on a step badge.
- `rag-stages.tex` logs `\c Text` as its written colour: a `\foreach`
  variable, unexpanded.
- With the math flag (spike, same day), the retrieval subscript logs as
  `8.40 0 1` (math) and a `\scriptsize` label as `8.00 0 0`.

## Testing

- Each rule: a fixture that fires it and one that does not, through
  `apply()` on hand-built `Drawn` objects where geometry is involved,
  and through the real probe once per rule on the Linux leg.
- `type-below-floor`: a subscript (silent), `\scriptsize` (fires), a
  `\small` set from an enclosing group with no size command in the node
  (fires), and a label all in math under `\scriptsize` (fires).
- `node-overlap` fires on a member half outside its zone, on two zones
  partly overlapping, and on a zone title running into a node.
  `content-protrusion` is silent on a two-row zoned layout and fires on
  a stranded node.
- The scaffold and exemplar tests report none of the four rules.
- 100% line and branch coverage; real-TeX lines carry
  `no cover-windows` as today.

## Changed in the build

- **The band is 6 to 12, not #1016's 6 to 15.** docs/TIKZ-STYLE.md
  already says "between 6 and 12 is the band the house block's cards
  and zones use", and the block's darkest card is `cgWarm!12`; #1016
  itself defers to the documented band.
- **A colour is matched to the nearest house tint within 1.5/255 a
  channel**, the share solved on the channel farthest from white.
  xcolor keeps five decimal places and this check mixes from the hex, so
  an exact match first called the house's own shades (`cgAuxLine`,
  `cgAccentText`) off the palette on 6 of 14 shipped figures, and the
  review then found 381 of the 2,100 `cg*!1..100` tints a step off,
  `cgWarm!6` among them. All 2,300 tints of every block colour, as real
  xcolor logs them, now match, with every hue's band verdict right.
- **Text inside a subscript fires.** `$k_{\text{in}}$` sets `in` from
  the text font at script size; `\mathrm` is the fix, and the rule's row
  says so rather than guessing which small text runs are subscripts.
- **`focal-count` moved with `FIGURE`.** `FIGURE` now lives in
  `_rules.py` beside `Finding`, so `_house.py` can name a figure-scope
  target without importing `_check.py`, which imports it.

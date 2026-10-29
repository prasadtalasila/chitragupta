# 🔀 XII-2c: connector rules from the lines TeX draws

Status: **built.** Written 2026-10-29 against `main` at `d1ab339`,
after a spike on issue
[#1054](https://github.com/prasadtalasila/chitragupta/issues/1054) whose
findings are recorded there and in `plans/fig-xii-figure-drawer-v3.md`
("What the 2c spike found"). Implemented in the same PR as this plan.
Decisions marked *user* were agreed in that session; the rest was the
session's proposal. What changed on the way is under **Changed in the
build** at the end.

**Written for** whoever builds #1054: a session that changes
`chitragupta/figure/`, `chitragupta/review/figure_layout/`,
`assets/latex/`, `assets/tikz/`, the `figure-drawer` skill, `bench/`,
`tests/` and `docs/`, and is therefore governed by `DEVELOPER-AGENTS.md`
and `docs/CODE-STANDARDS.md`.

**Assumed:** `plans/fig-xii-figure-drawer-v3.md` ("The rules", 2c and the
spike findings), `plans/1053-figure-check-skeleton.md` (the rule
registry, `cg-allow` and the report this extends), and
`docs/TIKZ-STYLE.md`.

**Not covered here:** element-scope `cg-allow` (#1058; an element-scope
allow is recognised and deferred, as today), clearing the scaffolds and
exemplars the bench finds firing (#1050, 1e), and the `state-machine`
layout itself (#1062).

## Decisions

- **Measure what TeX draws, not the source** (*user*). `figure check`'s
  probe wraps `\pgfusepath` and `\pgfmultipartnode` and logs every
  stroked segment and every node. The spike measured 279 lines between
  two nodes over 59 figures, against 218 at best for a source parser.
- **The hook goes in `figure check`'s compile only.** `review figure`'s
  document changes only by the circle fix below, so the risk of wrapping
  two pgf internals stays with the new command.
- **Fix the circle box in this PR** (*user*). Both probes read a node's
  box from its `west`, `east`, `south` and `north` anchors, not `south
  west` and `north east`, which on a circle lie on the curve.
- **Add `c7-dangling-tip`** (*user*): an arrow tip that lands on no node
  and no other line. `paper-twin-loop.tex` has two.
- **`c2` measures the text box**, the node's `text` anchor plus the text's
  width, height and depth. 141 of 160 node boxes touch their line by
  construction.
- **`c1` exempts `branching-tree`** as well as `state-machine` and
  `hub-and-spoke-network`, and a figure declares its layout with a
  `% cg-layout: <id>` line, which every scaffold and exemplar carries.
  The id names a file under the skill's `references/layouts/`.
- **`c4` does not measure round nodes** (circle, ellipse, diamond and the
  like), which have no sides; they are listed as not measured.
- **The connector rules are not measured**, with the reason, where the
  file has several `tikzpicture`s or uses `transform canvas`: in both
  cases a line's coordinates and the node boxes are not in one frame.
- **Lines not between two nodes are counted** as a diagnostic, so an
  axis, a plot or a bus line is visibly not checked rather than silently
  passed.
- One PR: this plan, the v3 plan's table, the bench and the code. MINOR,
  6.143.0.

## Constraints

- C1 at most 25 statements per function; C2 at most 250 code lines per
  module. Headroom when this was written: `_probe.py` 223, `_check.py`
  170, `figure_layout/__init__.py` 240, so new code goes in new modules.
- The probe runs under the `openin_any=p` read fence (#823), so the hook
  is inlined into the generated document, never `\input` by path.
- One `\typeout` per segment, so no log line nears `max_print_line`.
- 1mm is 72.27/25.4pt. The starting thresholds are the v3 plan's: `c1`
  off by more than 1mm in both x and y; `c2` a text-box gap under 0.8mm
  or over 3mm; `c3` collinear within 0.5pt over more than 2mm; `c4` a
  lone end within 0.5mm of its side's midpoint, N ends at `L*k/(N+1)`
  within 1mm and at least 2mm apart; `c5` crossing a box shrunk by 1pt;
  `c6` overlapping a box shrunk by 0.5pt; an end attaches within 1.5pt.
  The bench (task 8) confirms or moves each before the rules land.

## Inputs the tests must cover

1. A file with several pictures, and one using `transform canvas`: the
   connector rules are not measured, with the reason.
2. A standalone `\node` just before a `\draw` is not that draw's label: a
   node belongs to the next path event, and a standalone node's own empty
   path consumes it.
3. A label with no fill or draw still has a text box.
4. An end inside a zone card attaches to the member node, and `c5` does
   not fire for the zone.
5. Must-not-fire cases are the majority of each rule's tests: an elbow, a
   curve, a legitimate crossing, a bus line, evenly spaced ends, a
   self-loop, a tag set beside its line.

## Tasks

Each task is test-first: the test is written, seen to fail, then made to
pass, and the task ends in a commit.

1. **Circles at their true size.** `_probe.scaffold` reads four side
   anchors per name; `CGBOX`'s format is unchanged. Tests: the scaffold
   names the four anchors; a 2cm circle measures 2cm wide.
2. **The hook and the drawn-lines model.** `assets/latex/cg-figure-probe.tex`
   logs `CGNODE <shape> <name> <wd> <ht> <dp>` at node creation,
   `CGPATH <index> <N|E> <stroked> <start-tip> <end-tip>` and one
   `CGSEG <index> M|L|C|Z <x> <y>` per point at `\pgfusepath`, and
   `CGNB <name> <w> <s> <e> <n> <tx> <ty>` at the end of the picture.
   Unnamed nodes are logged as `cgu-<n>`. `review/figure_layout/_drawn.py`
   parses this into `Drawn(nodes, lines)`: `DrawnNode(name, shape, box,
   text_box)` and `DrawnLine(index, points, curved, start_tip, end_tip,
   labels)`, with curves flattened. `FigureResult.drawn` carries it.
3. **Connectors.** `chitragupta/figure/_connectors.py`: `solid()` nodes
   (not labels, not coordinates, not degenerate), `attach()` to the
   smallest box within 1.5pt, `connectors()` returning the connectors and
   every other stroked line, and the segment geometry the rules share.
4. **Layouts.** `Rule.exempt` and the seven rule ids registered. The
   `% cg-layout:` reader and the line in every scaffold and exemplar
   came from #1057 (#1084), which merged first.
5. **Routing rules** `c1`, `c3`, `c4`, `c7` in
   `chitragupta/figure/_route_rules.py`.
6. **Clearance rules** `c2`, `c5`, `c6` in
   `chitragupta/figure/_clearance_rules.py`.
7. **Wiring.** `_check.evaluate` reports the connector rules, lists them
   as not measured with a reason, and the report adds the
   lines-not-between-nodes diagnostic, in text and JSON.
8. **Bench.** `bench/bench_connector_rules.py` over the drafts, the
   scaffolds and the exemplars; firings on the scaffolds and exemplars,
   and a sample of the rest, checked against the rendered figure; the
   numbers, the classification and any threshold moved in
   `bench/RESULTS.md`.
9. **Docs and release.** The v3 plan's rules table, `docs/TIKZ-STYLE.md`,
   the skill's `references/check.md`, `docs/CLI.md`, `assets/tikz/README.md`,
   the version, the docs sweep and the local checks.

## Changed in the build

The bench (task 8) was run four times, and each false positive read in
the rendered figure became a must-not-fire test before the rule changed.
`bench/RESULTS.md` (2026-10-29) has the counts and the figures. In
order:

- **`c1` also fires on a bent connector** between offset nodes, as the
  v3 plan's "not a straight or bent segment" says; this plan's test list
  had said "not on a curve", which contradicted it.
- **`c3` skips two connectors that share an end point**: a fork from one
  trunk (`retrieval.tex`) is read, not hidden.
- **`c4` narrowed sharply**, from 79 findings to 10. It measures only a
  straight connector whose last piece meets its side square on, counts
  ends at one point once, skips zones, is exempt where `c1` is, and takes
  a 1mm lone-end tolerance instead of 0.5mm, which contradicted `c1`'s
  1mm. Ends of diagonal and bent edges land off a midpoint by geometry.
- **`c5` and `c6` skip markers under 2mm and unframed groups**; `c2` and
  `c6` skip a turned (`sloped`) tag. The hook therefore also logs each
  node's transform, and the parser which nodes had a frame painted. A
  first attempt read "visible" from the node's text width; a `fit` node's
  text box is its whole area, so that could not work.
- **`c7` reads only an arrow that leaves a node**, landing within 1mm, not
  1.5pt: axes, dimension lines and arrows that stop short of the line
  they point at were 11 of its 12 findings.
- **The hook logs a node before building it**, so its text box can be
  read first, which puts its frame paths after its own `CGNODE` line. The
  synthetic parse tests had them before, and passed; the real compile
  is what showed the order.
- **The bench's record names figures by relative path**, so it commits no
  host's home directory.
- **`node-overlap` measures every node `figure check` drew** (*user*,
  after seeing `architecture.tex`'s zone titles collide unreported). It
  runs `review figure`'s own `overlaps()` over the hook's boxes, names an
  unnamed node by its centre, and leaves out tags on lines (`c6`'s),
  turned nodes and round nodes under 7mm, the step badges `\cgstep` sets
  over a node's corner, which were all 16 of its first house findings.
- **House block v4: every word in a figure at the body size** (*user*).
  v3 set names and titles at `\large\bfseries`; a figure read louder
  than its text and a zone title grew into the next zone. Names and
  titles are now bold at `\normalsize`, and `tests/test_tikz_scaffolds.py`
  holds every house file to a ceiling as well as a floor.
- **#1057 (#1084) merged first** with its own `% cg-layout:` reader,
  `declared_layout()`, and the same line in every scaffold and exemplar,
  so this item's reader was dropped in the rebase and the connector
  exemptions read #1084's, honouring `--layout` like its size reports.
  The rebase pushed `_check.py` and `figure_layout/__init__.py` past
  C2: the connector wiring moved to `_connector_check.py` (a split the
  merge forced), and one docstring paragraph of `__init__.py` became a
  comment.

# 🖍 figure-drawer v3: compact figures, numbered rules, one check command

Status: **design, not built.** Written 2026-10-24 against `main` at
`12302d2`, from a brainstorming session that read two outside skills
(below) and measured the scaffolds on this host. Part XII of
[docs/FIGURE-ROADMAP.md](../docs/FIGURE-ROADMAP.md) summarises it and
places it in the build order. Tracked by epic
[#1044](https://github.com/prasadtalasila/chitragupta/issues/1044)
and the sub-issues listed under [Tracking](#tracking).

**Written for** whoever builds any phase of this: a session that changes
`assets/tikz/`, `chitragupta/figure/`, `chitragupta/review/figure_layout/`,
the three copies of the `figure-drawer` skill, `tests/` and `docs/`, and
is therefore governed by `DEVELOPER-AGENTS.md` and
`docs/CODE-STANDARDS.md`.

**Assumed:** `docs/TIKZ-STYLE.md`, `docs/FIGURE-DRAWER.md`,
`docs/FIGURE-ROADMAP.md` Parts II, VI and "Borrowed, with attribution",
`plans/1027-figure-drawer-skill.md`, and open issues #1016 (F4, teach
`review figure` the house vocabulary) and #1037 (run the figure probe on
LuaLaTeX).

**Integration branch.** All of this work was to land on
`improve-figures`, one PR per item, with CI enabled for PRs into that
branch and docs never published from it. **From #1053 on, items branch
off `main` and PR into `main`** (user, 2026-10-28), once `main` carried
everything the integration branch had. An item's issue is not closed
when its PR merges; it gets a comment recording the lessons and
decisions that bear on the items after it.

**Not covered here:** Part X output targets (this plan uses the render's
default text width and a `--width` override until Part X lands), Part XI
rendered images in `md`/`html`/`docx`, any vision critique (Part VIII),
and the existing 43 figures in the drafted book, which are flagged, not
migrated (see [Migration](#migration)).

## Why

Three defects were reported by the person who uses the pipeline:

1. **Figures sprawl.** A figure that could sit in a quarter page takes a
   half or a whole page. The opposite failure, squashing everything into
   the smallest possible box, is equally unwanted.
2. **Layout defects reach the rendered PDF.** Slanted connectors, an
   edge tag sitting on its own line, a lone arrow leaving a box near its
   corner instead of its centre.
3. **Figures carry too much or too little.** Overloaded boxes, or a
   figure where a sentence would do.

`docs/images/figure-drawer/twin-loop.png`, the skill's own documentation
figure, shows all three: two slanted connectors (`forecast`, `reading`),
two tags on their lines (`water`, `ingest`), the `Decide -> Pot` arrow
leaving `Decide` near its right corner although it is the only arrow on
that edge, and an inter-zone gap as tall as a zone, so four nodes take
roughly half a page.

## The reference book

The sample book attached to
[#1045](https://github.com/prasadtalasila/chitragupta/issues/1045)
("Digital Twins for Software Engineers", 294 A4 pages, 37 figures in
chapters 1 to 7, built with pdfTeX before #996) is the reference every
item measures against. What it shows:

- **Narrow, stacked layouts.** Most figures use 35% to 50% of the text
  width and grow downwards: Fig. 2.5 stacks its two panels vertically
  where side by side would take a third of the height; Figs. 2.1, 4.2
  and 4.5 are single tall columns.
- **Float-only pages.** A tall figure is moved to a page of its own and
  centred, with blank space above it (Fig. 2.5 on p. 38). That is the
  render's float placement, not the figure, and is item 1f.
- **Off-centre lone arrows** (Fig. 4.5's "state, digital events").
- **Type below the body size**, from before the type floor existed.

### The reference sources

The drafts behind that PDF are on the development host under
`content/drafts/` (gitignored, never committed), with their pdfTeX
renders of 2026-09-17 under `content/rendered/`. Every item measures on
them, not only on the scaffolds:

| Draft | Figure pairs (`.tex` + `.txt`) |
| --- | --- |
| `books/digital-twins-for-software-engineers` (chapters 1 to 7, appendix A1) | 40 |
| `tutorials/digital-twins-for-software-engineers` | 6 |
| `book-chapters/state-estimator` | 3 |

None of the 49 carries the house style block: they predate it, which
makes them an honest "before" set. `review figure` on them, 2026-10-28:
8 `nothing-measurable` (unnamed nodes or plots), 6 `content-protrusion`,
2 `node-overlap`, 3 `stranded-arrowhead`, and 1 `does-not-compile`
(`run-modes`, chapter 7), which is #1037's first test case.

**Baseline extents**, from `review figure`'s own probe (pdflatex, 10pt
Computer Modern, so a lower bound for the 12pt STIX render), as fractions
of the render's 453pt text width and 700pt text height, over the 48 that
compile. Slack is `1 - leaf node area / picture area`, zone cards
excluded:

| Measure | Median | Min | Max |
| --- | --- | --- | --- |
| Width | 0.81 | 0.44 | 1.03 |
| Height | 0.24 | 0.13 | 0.50 |
| Slack | 0.70 | 0.27 | 0.95 |
| Named nodes | 8 | 0 | 16 |
| Edges | 6 | 0 | 18 |

Over the width: `ensemble-fan` (1.03). Narrow and tall (under 0.6 wide,
over 0.3 high): `watering-strategies` (Fig. 2.5, 0.44 by 0.45),
`two-transport-layers` (0.59 by 0.41), `pump-markov-chain` (0.51 by
0.33). Nine figures have slack above 0.75. These numbers are what 1b's
compact defaults, 2f's reference ranges and 1f's float placement are
judged against, re-measured with the LuaLaTeX probe once #1037 lands.

## Inputs, and what was taken from each

Two outside skills were read. Nothing is vendored from either; both are
re-implemented here, for the reason FIGURE-ROADMAP's "Borrowed, with
attribution" already gives for the first: their checkers read SVG or
drawio geometry, and a TikZ figure has neither. Our probe reads named
node boxes out of the TeX log, which is the right substrate.

- **`cathrynlavery/diagram-design`** (MIT), already partly mined in
  2026-09. New this time: the six connector rules stated as numbered,
  checkable rules, including fanned attach points with the lone-arrow
  case at the edge midpoint; ADR 0005's "a rule only in prose ships
  broken", which means every rule ships with a checker and fixtures in
  both polarities; ADR 0002's "semantic patterns route to layouts and
  never add one"; ADR 0004's SKILL.md as a router under a byte cap.
  **Explicitly not taken:** the 4px grid and absolute coordinates, and
  "shadows are out" (the house `cgsoft` shadow stays).
- **`INTO-CPS-Association/DTaaS` `update-docs-diagrams`**: one command
  per step, each idempotent, with the skill text reduced to "run this,
  read what it prints"; exceptions recorded with a reason instead of
  rules silently skipped; contrast thresholds of 4.5:1 for text and 3:1
  for lines; and a last look at every changed image by eye.

## Decisions

Each was put to the user and answered, except where marked.

| Question | Decision |
| --- | --- |
| Palette | The eight `\definecolor` hex values are unchanged and remain the fills. Strokes and coloured text use derived shades (below) |
| Shadows, grid | Keep `cgsoft`; keep relative placement. No grid |
| Size | Advisory: report height as a fraction of `\textheight`, and *slack*, against each layout's reference range (FIGURE-ROADMAP VI.3). The `\normalsize` floor and a minimum gap prevent the opposite failure. Width overflow is objective |
| Who owns what goes in a figure | `figure-drawer`. The genre still decides *whether* a figure is warranted; the skill owns the pattern, layout, budget, remove test, and may tell the caller "this is two figures" or "a sentence does this" |
| New layouts | Quadrant, side-by-side comparison, state machine (II.4), sequence (II.2), timeline. Twelve in total |
| Label case | Sentence case node names; lowercase edge tags of at most three words; glosses of at most six words; a node of at most fifteen words |
| Twin agreement | Labels and panel letters checked; edge topology stays an eyeball check |
| Migration | `figure sync` moves the block to v3; findings in old figures are fixed when someone redraws them |
| Delivery | Three phases, one epic |
| Exception scope | Element-level for element rules, figure-level only for rules about the whole figure; **figure-level lands first** |
| Enforcement (*not put to the user; settled by SOUL.md*) | `figure check` exits 0 whatever it finds, like every review aid. The skill's procedure tells the agent to resolve each objective finding or record a reasoned `cg-allow`, and to report the rest to the caller. Nothing blocks a draft |

The last row overrides a default proposed during the session ("objective
rules gate inside the skill"). SOUL.md: *"There is exactly one citation
gate. Every other check over a draft ... is advisory wherever in the
tree it lives, and none grows a flag that blocks."* A procedure step in a
skill is guidance a person can overrule; an exit code is a flag.

## Measurements behind the design

Taken on this host on 2026-10-24 with TeX Live from
`scripts/install_full_pipeline.sh os-deps`, LuaLaTeX, article class.

**Scaffold extents** (11pt, libraries preloaded in the preamble, as the
renderer does after #781). The render default is 12pt A4 with 1in
margins, a text width of 453pt and a text height of about 700pt.

| File | Width (pt) | Height (pt) |
| --- | --- | --- |
| pipeline | 307 | 70 |
| zoned-spine | 322 | 121 |
| branching-tree | 283 | 140 |
| hub-and-spoke-network | 269 | 148 |
| map | 226 | 126 |
| control-loop | 225 | 95 |
| layered-stack | 203 | 175 |
| exemplars/architecture | 435 | 234 |
| exemplars/retrieval | 447 | 352 |
| exemplars/rag-stages | **475** | 224 |

So the scaffolds do not sprawl; sprawl enters when a figure is drawn by
hand around them. `rag-stages` overflows the text width at 11pt, before
the 12pt body widens it further.

**Stray width from loading a library in horizontal mode.** A figure file
`\input` inside a box or paragraph, with its `\usetikzlibrary` line *not*
already satisfied by the preamble, adds blank width before the picture:

| Library loaded in the body | Added width |
| --- | --- |
| `arrows.meta` | 0pt |
| `positioning`, `fit`, `backgrounds`, `calc` | about 13pt each |
| `shadows.blur` | about 120pt |
| the house line, all six | about 175pt |

Preloaded, every one adds 0pt, and the house style block itself adds 0pt.
**Corrected 2026-10-28:** the spaces are set only in horizontal mode. A
figure `\input` in vertical mode, which is where the skill's step-7 probe
(`\documentclass{article}\usepackage{tikz}` then `\input`) and every
`figure` float put it, loses them: measured, the leftmost glyph lands at
the same x with and without the libraries preloaded. An earlier version
of this plan, and #1046, said the step-7 probe over-reports width by
about 40%; that was wrong. What is affected is narrower: a `standalone`
preview (which boxes its content), a width measured with `\sbox` or
`\hbox`, and an `\input` inline in running text. The renderer and
`review figure` are unaffected.

**Remeasured 2026-10-30 (#1046)** on `figure check`'s boxed probe, the
render's page (12pt, LuaLaTeX, the render's fonts): the house line adds
135pt, and 147pt with `matrix` (`map`) or `trees` (`branching-tree`)
added. The table above was measured on a different page. Preloaded,
every scaffold adds 0.00pt. `tests/test_figure_stray_width.py` pins
the in-box half; `test_figure_check.py`'s scaffold test already pinned
the preloaded one.

**Palette contrast**, WCAG 2 relative luminance, against white, `cgPaper`
and every zone tint the house block defines:

| Role | As a stroke on its own tint | Needs |
| --- | --- | --- |
| `cgFlow` | 4.70 | 3.0 |
| `cgAccent` | 3.37 | 3.0 |
| `cgAlt` | 3.08 | 3.0 |
| `cgRose` | 2.78 | 3.0 |
| `cgAux` | 2.14 | 3.0 |
| `cgWarm` | 2.04 | 3.0 |
| `cgMute` text (glosses) on white | 3.45 | 4.5 |
| `cgAccent` text (edge tags) on white | 3.87 | 4.5 |
| `cgInk` text on any tint | 15 to 16 | 4.5 |

## The rules

Every rule has an id, a scope and a class. The id is what a finding, a
`cg-allow` line, TIKZ-STYLE.md and the skill all quote, so they cannot
drift apart (a test cross-checks the four). **Objective** rules are ones
the skill must resolve or allow; **advisory** rules are reported for
judgement.

### Connector rules

Metaphor-aware: a layout declares itself with a `% cg-layout: <id>` line
that every scaffold carries, and `figure new` keeps. A rule a layout
exempts is not evaluated for it. **Corrected by issue #1050**, which
added the line: an id is the scaffold's file stem, so the hub's is
`hub-and-spoke-network`, not the `hub-and-spoke` this table first said,
and an exemplar's is the layout whose reference file measures it.

| Id | Rule | Scope | Class |
| --- | --- | --- | --- |
| `c1-orthogonal` | An edge between nodes whose ends differ in both x and y by more than 1mm is an elbow (`-\|`, `\|-`), not a straight or bent segment. Exempt: `state-machine` (curved transitions and self-loops are its convention), `hub-and-spoke-network` (radial spokes) | edge | objective |
| `c2-tag-clearance` | An edge tag's text sits beside its segment, 0.8mm to 3mm clear of it: not on the line, not floating away from it. A `sloped` tag is not measured | edge | objective |
| `c3-coincident` | No two edges share a collinear stretch longer than 2mm, unless they share an end point (a fork) | edge pair | objective |
| `c4-attach` | A lone edge on a node side attaches at that side's midpoint, within 1mm. N edges on one side attach at `L*k/(N+1)`, within 1mm, and at least 2mm apart. Only a straight edge meeting its side square on; round nodes and zones are not measured; exempt where `c1` is | node side | objective |
| `c5-transit` | No edge crosses the box of a node that is neither of its ends. Zone cards that contain an end, markers under 2mm and unframed groups are not counted | edge | objective |
| `c6-tag-covered` | No edge tag overlaps a node box, a zone containing the tag or an unframed group aside | edge | objective |
| `c7-dangling-tip` | An arrow that leaves a node lands its tip within 1mm of a node or another line | point | objective |

**Changed by issue #1054** (2026-10-29), where the bench over this
repository's figures found the plan's first statement firing on sound
figures: `c2` measures the tag's text, `c3`
skips a fork, `c4` narrowed to square ends of straight edges with a 1mm
lone-end tolerance (the plan's 0.5mm contradicted `c1`'s 1mm), `c5` and
`c6` skip markers and unframed groups, and `c7` was added for the arrow
that points at nothing. `bench/RESULTS.md` has each with the figure that
prompted it.

The existing findings keep the names `review figure --json` already
ships as its `kind` strings (`does-not-compile`, `nothing-measurable`,
`node-overlap`, `node-text-overload`, `stranded-arrowhead`,
`loads-library-by-hand`, `content-protrusion`) and their current
classes; emptiness stays a diagnostic, not a finding. **Corrected by
issue #1053**, which found that this list had named them differently
from the shipped ids.

### Contrast, focal and wording

| Id | Rule | Scope | Class |
| --- | --- | --- | --- |
| `k1-stroke` | A box's border or a connector clears 3:1 against its ground (its own fill, or the innermost filled box holding it, or white; a connector's, the innermost filled box holding both ends), as pgf drew it. **Changed by #1055** from "a `draw=` colour", and to take connectors in (*user*) | element | objective |
| `k2-text` | Each run of a node's typeset text clears 4.5:1 against its ground; WCAG's large text (14pt bold, 18pt, measured from the glyphs) clears 3:1. **Changed by #1055** from "a `text=` colour" and "`\large`": block v4 has no `\large`, and `\cglab` colours its gloss with `\textcolor` | element | objective |
| `focal-count` | At most one `cgkey` node per figure (TIKZ-STYLE.md: "if two things are accented, neither is"; #1016's `accent-not-unique`) | figure | objective |
| `w1-case` | A `\cglab` name is in sentence case (only `\cglab` is read, *user*, #1055). `\texttt{}`, math and a name whose first word is all lower-case by convention (`tikz`, `pdflatex`) are left alone | node | advisory |
| `w2-tag` | An edge tag is lower-case and at most three words | edge | advisory |
| `w3-gloss` | A gloss is at most six words (this supersedes the eight in #1016's `gloss-too-long`) | node | advisory |
| `w4-pictograph` | No emoji or pictographic character in any label | element | objective |

### Size

| Id | Rule | Scope | Class |
| --- | --- | --- | --- |
| `size-width` | The picture is no wider than the target text width: 453pt by default (the render's 12pt A4 1in), `--width` to override | figure | objective |
| `size-stray` | The `\input` box is no wider than the picture: any difference is stray space, almost always a library loaded in horizontal mode | figure | objective |
| `size-height` | Height as a fraction of `\textheight`, reported beside the layout's reference range | figure | advisory |
| `size-slack` | `1 - (sum of named non-zone node areas) / (picture area)`, reported beside the layout's reference range | figure | advisory |
| `size-squash` | Two nodes joined by an edge are less than 3mm apart edge to edge, so the arrow is too short to read | edge | advisory |
| `budget-nodes`, `budget-edges` | Node and edge counts, against the layout's reference range. Never a cap: FIGURE-ROADMAP's "Considered and set aside" declines numeric caps, since a forty-cell DP trace is not over budget | figure | advisory |

Reference ranges come from the scaffold and the exemplar of each layout
(VI.3, VI.4), written down in that layout's reference file, so a range
moves only when an exemplar does.

### Twin agreement

| Id | Rule | Scope | Class |
| --- | --- | --- | --- |
| `t1-labels` | Every node name in the `.tex` appears in the `.txt`, compared case-insensitively with TeX markup stripped and whitespace collapsed | node | objective |
| `t2-tags` | Every edge tag in the `.tex` appears in the `.txt` | edge | objective |
| `t3-panels` | The panel letters in the two files are the same set | figure | objective |

**Corrected by issue #1056.** `t1` compares names only (a label's first
line, a zone title, a legend entry), never a gloss, and a name is present
when each of its words is, in any order: on the reference book's 49
pairs, whole-line matching missed 140 of 651 lines on the ASCII's
reflow alone. Maths is dropped before comparing. A fourth rule,
`twin-missing` (figure, objective, not allowable), reports a figure with
no `.txt`; `t1` to `t3` are then not measured.
`plans/1056-twin-agreement.md` has the rest.

## Exceptions: `cg-allow`

A figure that breaks an objective rule on purpose says so in its own
file, which travels with the draft and into a thesis:

```latex
% cg-allow: c1-orthogonal twin->decide -- curved on purpose: the feedback edge reads as a loop
% cg-allow: size-width -- a five-stage pipeline the chapter compares stage by stage
```

- The form is `% cg-allow: <rule-id> [<target>] -- <reason>`. The reason
  is required. A target names a node (`decide`), an edge by its ends
  (`decide->pot`), a pair (`legend+pot`) or a node side
  (`decide.south`).
- **A figure-scope rule takes no target. An element-scope rule requires
  one.** A target-less allow for an element rule is reported as
  malformed, so "allow every slanted edge" cannot be written.
- `figure check` lists every allow it honoured in its report, so an
  exception is always visible.
- An allow whose target no longer exists, or no longer breaks its rule,
  is reported as stale.
- Order of build: **figure-scope allows land first**, with the check
  skeleton (phase 2b). Element-scope allows and stale detection follow
  (phase 2g), once edge geometry exists to name targets with.

## The commands

All three live in `chitragupta/figure/`, beside `sync`, and all exit 0
whatever they find, except on a usage error or a missing toolchain.

- **`chitragupta figure new <figures-dir> <name> --layout <id>`.** Copies
  the scaffold to `<figures-dir>/<name>.tex` and its twin to `<name>.txt`,
  then runs `sync`. Refuses to overwrite. Replaces step 2's `cp` and
  `sync`.
- **`chitragupta figure check <figure.tex> [--width PT] [--json]`.** One
  report: the compile probe (libraries preloaded, so `size-stray` is the
  only place stray width can show), every rule above, the existing
  `review figure` findings for that one file, and the honoured allows.
  One line per finding, `<rule-id> <target> <measurement>`, objective
  findings first. Replaces steps 4 to 8.
- **`chitragupta figure look <figure.tex> [--draft <draft>]`.** Compiles
  the figure alone in the render's own preamble (class, 12pt, fonts, text
  width), draws a hairline at the text width, and writes a PNG under
  `content/rendered/`. With `--draft`, renders the draft instead and
  crops the page that holds the figure. Replaces step 9.

The probe engine is LuaLaTeX with the render's fonts, which #1037 (done
in phase 1) makes true before these commands land.

## The skill

`SKILL.md` becomes a router, in all three harness copies:

1. Who called you, and where the figure goes (unchanged in substance).
2. **Pattern, then layout.** What does the figure argue? Route through
   the pattern table in `references/patterns.md` to one of the twelve
   layouts. A new layout is justified only by a new layout grammar,
   never by a new pattern (diagram-design ADR 0002).
3. **The taste gate, before drawing.** Would a sentence or a table do
   this? Can a node, an edge or a label go? Do two nodes always travel
   together? Is there one focal node? Is this one figure or two
   (overview and detail)? Push back to the caller when the answer says
   so.
4. `figure new`, then draw below the house block.
5. Write the twin.
6. `figure check`; resolve every objective finding or add a `cg-allow`
   with its reason; read the advisory ones.
7. `figure look`, and look at it.
8. Return: the two paths, what `check` reported and what was allowed,
   and whether the look was done.

The prose that today explains each step moves to `references/`, which
issue #1039 keeps once under `.claude/`. A test holds each `SKILL.md` under a
byte cap of 8,000 (it is 11,705 today) and fails if a section moved out
loses its link, as diagram-design's `verify-docs-sync.py` does.

## The house block, v3

- **Derived shades.** For each hue `H`, `cgHLine` (strokes) and `cgHText`
  (coloured text) are `cgH!p!cgInk` with the largest `p` that clears the
  threshold over white, `cgPaper` and every zone tint. Starting values,
  which a test recomputes from the hex values rather than trusting:

  | Hue | `Line` share | `Text` share |
  | --- | --- | --- |
  | Flow | 100 | 95 |
  | Accent | 100 | 80 |
  | Alt | 95 | 70 |
  | Aux | 75 | 55 |
  | Warm | 75 | 55 |
  | Rose | 90 | 65 |

  Plus `cgMuteText = cgInk!65` for glosses and notes. The rule a reader
  remembers: **a palette name fills; a `Line` or `Text` name draws.**
- **Edge tags beside the line.** `cgtag` stops filling over its edge and
  is placed beside the segment (`c2-tag-clearance`), in `cgMuteText`.
- **Compact defaults.** Zone inner sep 3mm, zone title gap 1.5mm, node
  distance 6mm within a zone and 8mm between zones. Type is not touched.
  Every scaffold's slack must not rise and no `size-squash` may appear.
- **Version.** The marker line becomes `v3`;
  `cg-figstyle.versions.toml` records it, so `figure sync` upgrades a v2
  block in place and the render's hand-edit warning keeps working.

## Phases

### Phase 1: foundations

- **1a (bug).** Shipped 2026-10-30, closing #1046. The probe and
  `figure look` already preloaded (#1053, #1052), so what landed is the
  test and the note in TIKZ-STYLE.md, `figures.md` and the thesis skill.
  Stray width, narrowed (see the correction above):
  TIKZ-STYLE.md says a preview or a box measurement must preload the
  libraries, and a characterization test pins both halves (a body load
  inside a box adds width; a preloaded one adds none), so `figure look`
  (2a) cannot reintroduce it.
- **1b.** House block v3: derived shades, `cgtag` beside the line,
  compact defaults, a contrast test over the palette and every scaffold,
  and `figure sync` to v3.
- **1c.** `SKILL.md` as a router with the taste gate, the three harness
  copies, the byte-cap and link tests.
- **1d.** `references/patterns.md` (pattern to layout routing) and one
  reference file per layout with its reference ranges. This is
  FIGURE-ROADMAP II.0's split, and VI.6's checklist and anti-pattern
  table land here.
- **1e.** Fix the scaffolds and exemplars that break a rule today:
  `rag-stages`' width, and every lone edge re-anchored to a side
  midpoint.
- **1f.** Float placement: measure which figures land on float-only
  pages in the reference book, and set the render preamble's placement
  default and float fractions so a figure that fits stays in the text.
- **#1037, whole.** Move every remaining pdflatex path to LuaLaTeX: the
  figure-layout probe (so `check` and `look` measure in the fonts that
  print), the thesis-chapter path and the book build. It lands before
  phase 2, which measures with the probe. It starts with a regression
  found on the development host: under TeX Live 2025, `openin_any=p`
  (#823) restricts absolute paths to `$TEXMFOUTPUT`, and `luaotfload`
  opens `ScriptExtensions.txt` by absolute path, so every LuaLaTeX
  render fails there (CI's older TeX Live hides it). The fix keeps
  `openin_any=p` and lets only the TeX distribution's own trees through,
  with a regression test.

### Phase 2: `figure new`, `check` and `look`

- **2a.** `figure new` and `figure look`.
- **2b.** `figure check` skeleton: probe, existing findings, report
  format, figure-scope rules (`size-width`, `size-stray`, `focal-count`)
  and figure-scope `cg-allow`.
- **2c.** Edge geometry and `c1` to `c7` (#1054, built; see
  `plans/1054-connector-rules.md`). **Bench first**, per VI.5:
  run each rule over the scaffolds, the exemplars and the 49 draft
  figures before fixing thresholds, with the must-not-fire cases (a
  legitimate crossing, an automaton self-loop, a lifeline with many
  arrows at one x) as the majority of the fixtures.
- **2d.** `k1`, `k2`, `w1` to `w4` (#1055, built; see
  `plans/1055-contrast-and-wording.md`). Coordinate with #1016, which
  proposes overlapping source findings; whichever lands second reuses the
  first's parser. #1055 landed first: its colours come from the probe
  (`CGPAINT`, `CGTEXT`), not a source parser, so #1016's colour findings
  should read those; its `accent-not-unique` is `focal-count` and its
  `gloss-too-long` is `w3-gloss`.
- **2e.** Twin agreement `t1` to `t3`, and a `.txt` twin for every
  existing scaffold, which the fixtures need. Built by #1056, which
  added `twin-missing` and gave the three exemplars twins too; its plan,
  `plans/1056-twin-agreement.md`, records the matching it settled on.
- **2f.** Size: `size-height`, `size-slack`, `size-squash`, the budgets
  and the reference ranges from 1d. Built by #1057; its plan,
  `plans/1057-figure-check-size.md`, records where it parted from this
  list (the reports are kept out of the findings, and none is allowable).
- **2g.** Element-scope `cg-allow` and stale-allow detection.

How edges are measured: **TeX reports the lines it draws**, rather
than Python re-deriving them from the source. `figure check`'s probe
wraps `\pgfusepath` and `\pgfmultipartnode`, so the compile logs every
stroked path's segments in canvas coordinates, flagged when it is part
of a node, and every node it creates, labels on a path included. A
connector is a line whose two ends touch two different nodes. A stroked
line that does not is listed as not between two nodes, the same honesty
as the measured-nothing rule, never silently skipped. This replaces the
earlier design, a source parser over `\draw`; the spike below is why.

#### What the 2c spike found (2026-10-29)

A throwaway spike compared the two designs over the 49 draft figures,
the 7 scaffolds and the 3 exemplars. The source parser was scored at its
best case: an edge counted if both its ends named a declared node, even
though the parser would still have to evaluate the path between them.

- **TeX-reported lines measure more, and are never wrong where the
  parser is right.** All 59 figures compiled with the hook. It found
  279 lines between two nodes, against the parser's 218 at best, and
  more on 17 figures: `\foreach` loops (`run-modes.tex`, 10 against 0),
  `child` trees, `pic`s and curves. Each of the 5 figures where it found
  fewer is explained: a `\path` the parser listed that draws nothing (2
  figures), self-loops counted separately (1), lines that end on a bus
  line rather than a node (1), and arrows that end in empty space (1).
  A computed end such as `(pot.north |- twin.south)` comes back as the
  exact point drawn, with no TikZ grammar in Python.
- **A label's node box touches its line by construction.** 141 of the
  160 labels on a stroked line have a node-box gap of 0.0mm: `above`,
  `left` and the rest anchor the box edge on the line, and the space a
  reader sees is the inner sep inside it. `c2-tag-clearance` measured
  on the node box would fire on almost every label, so it must measure
  the text box (the node box less its inner and outer sep). This is the
  box-against-paint question VI.5 raised, answered for labels.
- **`c1-orthogonal` fires on a scaffold.** `branching-tree` has 6
  diagonal edges by design, which the exemptions above do not cover.
  Across the drafts, 33 straight lines between nodes on 12 figures are
  diagonal. No figure carries a `% cg-layout:` line yet, so this item
  is the first to read one. (#1083 since redrew the tree with fanned
  orthogonal edges, so trees are held to `c1` after all.)
- **The shipped probe under-measures circles.** It reads a node's box
  from its `south west` and `north east` anchors, which on a circle lie
  on the curve, not at the corners, so a circle's box is about 30% too
  small. The spike read `west`, `east`, `south` and `north` instead.
  `review figure`'s overlap and protrusion checks have the same gap
  today.
- **One defect is outside c1 to c6.** In `paper-twin-loop.tex` the
  `reading` and `dose` arrows end at the twin's height but about 13mm
  beside its box, pointing at nothing.
- **What the hook costs and risks.** No second compile: it rides the
  probe `figure check` already runs. It wraps two pgf internals, so a
  pgf release that renames either breaks it, which a test against the
  installed TeX Live catches. `transform canvas` moves a line outside
  the canvas coordinates the hook reads, and `\graph` was not in the
  corpus; both need a fixture. Long plotted paths need a raised
  `max_print_line`, or their log line wraps.

### Phase 3: five scaffolds

One scaffold per layout, each with its twin, its `% cg-layout:` line,
its reference file and an exemplar, and each clean under `figure check`:
`quadrant`, `comparison`, `state-machine` (II.4), `sequence` (II.2) and
`timeline`. `tests/test_tikz_scaffolds.py`'s table-to-directory
cross-check covers them.

- **3b, `comparison`.** Built by #1061. Panel (a) is one column; each
  part of panel (b) is placed `at (<column> |- <match>)`, centre on
  centre, because `right=` of its match shifted with the match's width
  and `below=` its neighbour with the neighbour's height: the first
  exemplar draft slanted two edges (`c1`) that way. Each card fits every
  part of its panel, not just the ends (`node-overlap` caught a wider
  middle part). Nothing is drawn between the panels. A part one side
  lacks keeps its row as `cgnone`. The exemplar is
  `assets/tikz/exemplars/grounding.tex`. Left open: `cgnone` and `cgopt`
  on a tinted card show a pale offset box where `cgflat` fails to cancel
  the shadow; `retrieval.tex` shows it too.

## Dependencies and value

An arrow reads "must land before". Value is to the person who reported
the problem: how much of the sprawl, the defects reaching the PDF, and
the too-much-or-too-little each item removes from the reference book.

```mermaid
flowchart LR
  L37["#1037 LuaLaTeX + TL2025 fix"]
  I1b["1b #1047 house block v3"]
  I1d["1d #1049 patterns + ranges"]
  I1a["1a #1046 stray width"]
  I1e["1e #1050 scaffolds clean"]
  I1f["1f #1065 float placement"]
  I1c["1c #1048 SKILL.md router"]
  I2a["2a #1052 new + look"]
  I2b["2b #1053 check skeleton"]
  I2c["2c #1054 connector rules"]
  I2d["2d #1055 contrast + wording"]
  I2e["2e #1056 twin agreement"]
  I2f["2f #1057 size reporting"]
  I2g["2g #1058 element cg-allow"]
  S3["3a-3e #1060-#1064 five scaffolds"]
  L37 --> I1f
  L37 --> I2a
  L37 --> I2b
  I1b --> I1e
  I1d --> I1e
  I1b --> I2d
  I1d --> I2f
  I2b --> I2c
  I2b --> I2d
  I2b --> I2e
  I2b --> I2f
  I2a --> I1c
  I2b --> I1c
  I1d --> I1c
  I2c --> I2g
  I2d --> I2g
  I1e --> S3
  I2c --> S3
  I2e --> S3
  I2f --> S3
```

| Rank | Item | Why it is worth this much | Depends on |
| --- | --- | --- | --- |
| 1 | #1037 LuaLaTeX everywhere, with the TL2025 `openin_any` fix | Every render fails on a current distribution; every measurement after it needs the fonts that print | none |
| 2 | 1b #1047 house block v3 | Compact spacing attacks the sprawl directly; derived shades fix five contrast failures | none |
| 3 | 2b #1053 `figure check` skeleton | Carries every rule after it; on its own, width overflow and focal count | #1037 |
| 4 | 2c #1054 connector rules | The defects that reach the PDF today: slants, tags on lines, off-centre arrows | 2b |
| 5 | 2f #1057 size reporting | Makes the sprawl visible per figure against a range: 9 drafts above 0.75 slack | 2b, 1d |
| 6 | 1f #1065 float placement | Whole pages lost to float-only placement, with no figure change | #1037 |
| 7 | 3b #1061 comparison scaffold | Fig. 2.5's stacked panels are the book's worst sprawl case | 1e, 2c, 2e, 2f |
| 8 | 1d #1049 patterns and reference ranges | Too much or too little: what a figure should hold, per layout | none |
| 9 | 2a #1052 `figure new` and `look` | The look that catches what geometry cannot | #1037 |
| 10 | 1c #1048 SKILL.md router and taste gate | The remove test acts before a figure is drawn | 1d, 2a, 2b |
| 11 | 2e #1056 twin agreement | The md, docx and html readers' only figure | 2b |
| 12 | 1e #1050 scaffolds and exemplars clean | Copying a scaffold no longer imports a defect | 1b, 1d |
| 13 | 2d #1055 contrast and wording | Consistency; overlaps #1016 | 2b, 1b |
| 14 | 3c #1062 state machine | Ch. 6's automata; curved transitions by convention | 1e, 2c, 2e, 2f |
| 15 | 3d #1063 sequence | Protocol figures | 1e, 2c, 2e, 2f |
| 16 | 3e #1064 timeline | Ch. 7's time-axis figures | 1e, 2c, 2e, 2f |
| 17 | 3a #1060 quadrant | No figure in the reference book needs it yet | 1e, 2c, 2e, 2f |
| 18 | 2g #1058 element-scope `cg-allow` | Precision for exceptions; figure-scope already works | 2c, 2d |
| 19 | 1a #1046 stray width | Narrowed by the correction above to previews and box measurements | none |

The build order follows the ranks wherever the dependencies allow: issue
1037, then 1b, 2b, 2c, 1d, 2f, 1f, 2a, 2e, 1e, 3b, 1c, 2d, 3c, 3d, 3e,
3a, 2g and 1a.

## Migration

`figure sync` upgrades the block in every figure that carries one. A
figure body is never rewritten. `figure check` reports what the old
body breaks, and `draft-reviser` fixes it when it next touches the
figure. No sweep of `content/drafts/` is part of this work.

## Tracking

Filed 2026-10-24 as one epic,
[#1044](https://github.com/prasadtalasila/chitragupta/issues/1044),
with a sub-issue per phase and a sub-issue per item under each phase.

| Phase | Issue | Items |
| --- | --- | --- |
| 1 Foundations | [#1045](https://github.com/prasadtalasila/chitragupta/issues/1045) | 1a [#1046](https://github.com/prasadtalasila/chitragupta/issues/1046) (bug), 1b [#1047](https://github.com/prasadtalasila/chitragupta/issues/1047), 1c [#1048](https://github.com/prasadtalasila/chitragupta/issues/1048), 1d [#1049](https://github.com/prasadtalasila/chitragupta/issues/1049), 1e [#1050](https://github.com/prasadtalasila/chitragupta/issues/1050), 1f [#1065](https://github.com/prasadtalasila/chitragupta/issues/1065), [#1037](https://github.com/prasadtalasila/chitragupta/issues/1037) (LuaLaTeX everywhere) |
| 2 `figure new`, `check`, `look` | [#1051](https://github.com/prasadtalasila/chitragupta/issues/1051) | 2a [#1052](https://github.com/prasadtalasila/chitragupta/issues/1052), 2b [#1053](https://github.com/prasadtalasila/chitragupta/issues/1053), 2c [#1054](https://github.com/prasadtalasila/chitragupta/issues/1054), 2d [#1055](https://github.com/prasadtalasila/chitragupta/issues/1055), 2e [#1056](https://github.com/prasadtalasila/chitragupta/issues/1056), 2f [#1057](https://github.com/prasadtalasila/chitragupta/issues/1057), 2g [#1058](https://github.com/prasadtalasila/chitragupta/issues/1058) |
| 3 Five scaffolds | [#1059](https://github.com/prasadtalasila/chitragupta/issues/1059) | 3a [#1060](https://github.com/prasadtalasila/chitragupta/issues/1060), 3b [#1061](https://github.com/prasadtalasila/chitragupta/issues/1061), 3c [#1062](https://github.com/prasadtalasila/chitragupta/issues/1062), 3d [#1063](https://github.com/prasadtalasila/chitragupta/issues/1063), 3e [#1064](https://github.com/prasadtalasila/chitragupta/issues/1064) |

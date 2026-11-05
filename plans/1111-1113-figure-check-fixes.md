# Three `figure check` defects found in a drafts update

Status: **built**, on branch `fix-1111-1113-figure-check` (v6.166.0).
Changed on the way, mostly from the implementation review: c2 counts a
head only where the tag sits *beside* it; the block reaches pgf's layer
macros by `\csname` (a `\pgf@name` read as a Pandoc citation); heads
come from pgf's tip hull rather than an assumed width; and the version
is MINOR, as every earlier block bump was.
Written 2026-11-05 for
[issue 1111](https://github.com/prasadtalasila/chitragupta/issues/1111),
[issue 1112](https://github.com/prasadtalasila/chitragupta/issues/1112) and
[issue 1113](https://github.com/prasadtalasila/chitragupta/issues/1113),
which ship in one pull request with this plan. All three were found
while updating a user's drafts to v6.156.0.

**Written for** whoever builds or reviews it. **It assumes**
[plans/fig-xii-figure-drawer-v3.md](fig-xii-figure-drawer-v3.md) for
`figure check`, its boxed probe and the drawing hook (#1053, #1054).

## Decisions (user, 2026-11-05)

1. **One pull request for the three issues**, so users see one house
   block bump rather than two (#1111 and #1113 both change the block).
2. **#1113 option A:** c2 measures from the ink, not the centreline: the
   stroke's edge, and the arrowhead's outline beside a tipped end. The
   floor is 1.0mm from the ink, and the house `cgtag` moves out to
   `outer sep=1mm` so a house tag passes it.
3. **#1112 item 2 option A:** a declared node name holding a macro
   (`s\i`) is measured from the drawn nodes whose names it matches
   (`s.+`), and only those. Every other drawn name stays unmeasured as
   today, so no figure that passes now changes its numbers.

## #1111: a shadowed node after a background scope

**Cause** (read in pgf 3.1.10's source, then reproduced). `blur shadow`
declares a fading for each shadow (`tikzlibraryshadows.blur.code.tex`,
`render blur shadow`), and `\pgfdeclarefading` typesets the fading's
picture in a box (`pgfcoretransparency.code.tex`). That picture is a
`\pgfpicture` of its own, and once a layer is declared,
`\endpgfpicture` runs `\pgf@insertlayers`, which takes every declared
layer box into the picture being closed. The background layer's box is
global, so the fading's picture takes the outer figure's background
content into the fading mask, and the outer picture later finds it
empty. `\pgfinterruptpicture` guards against exactly this with
`\pgf@savelayers` / `\pgf@restorelayers`; `\pgfdeclarefading` does not.

**Fix:** the house block wraps `\pgfdeclarefading` in the same pair,
once per document (`\ifx` guard on the saved original). Reproduced and
fixed under both `lualatex` and `pdflatex` before the plan was written.

**No `figure check` rule.** The probe logs paths before they reach a
layer box, so it cannot see the loss, and with the block fixed there is
nothing left to detect. A figure carrying an older block is reported
`STALE` already, and `figure sync` replaces it.

**Test:** a TeX test compiles the issue's ordering (a `cgkey` node after
the scope) with the shipped block, rasterises it, and checks the zone
card's fill is painted.

## #1112: four valid spellings misread

1. **Name after `at`.** `_source.py` gains a declaration scanner, the
   one `figure/_labels.py` already had (options nest, a group after `at`
   is a position, a calc `($...$)` read to its close), moved down so
   `overlong_nodes`, the probe's `node_names` and `_labels.nodes` share
   it. `\node at (0,-2) (b) {beta}` declares `b`.
2. **`\foreach` nodes.** After `figure check`'s boxed compile, each
   declared name holding a macro becomes a pattern: literal parts kept,
   each control sequence `.+`. The drawn nodes it matches (not a hook
   name, not already declared) are added to the boxes from the hook's
   own box, and replace the macro name in the declared list. A name
   with no literal part (`(\i)`) matches everything and stays
   unmeasured. `review figure` has no hook and keeps reporting `s\i` as
   declared but not measured.
3. and 4. **`(` and `;` in a tag.** `\draw`/`\path` statements are read
   by a scanner that ends a statement at the first `;` outside a brace
   group, and every brace group in the body is blanked to `{}` before
   the parenthesised tokens are read. `edge_list`, `ambiguous_edges`,
   `stranded_arrowheads` and `_wording._tags` read through it.

## #1113: tag clearance from the ink

- **Probe.** Two new log lines, so a log without them still reads:
  `CGLW <path> <width>`, the path's `\pgflinewidth`, and
  `CGTIP <path> <tip> <x> <y>`, one per point of each arrowhead's convex
  hull. That hull is the one pgf keeps for the picture's bounding box
  (`\pgf@arrows@rigid@hull`, reading `pgf@ar@hull@<id>`), transformed
  as pgf transforms it, so the head's real outline is logged, width
  included. Found while building it; the design had assumed the house
  `Latex` ratio, because the tip's painting is cached PDF code that
  never reaches `\pgfusepath`.
- **c2.** A tag's gap is the least of: its text box to each segment,
  less half the line width; and its text box to each head's outline
  (the hull, ordered by Andrew's monotone chain, since pgf promises no
  order). A head counts only where the tag is beside it: the tag's
  text and the head overlap when both are projected onto the stretch
  of line the head sits on. Measured to any nearby head, a midway tag
  on a short edge failed where its corner merely came near a barb
  (the review found two shipped exemplars and the state machine doing
  this). Floor 1.0mm, ceiling 3.0mm, both from the ink.
- **Heads go to the subpath that carries the tip**, as `end_tip`
  already does, and the hook stops the compile if pgf renames the hull
  macro rather than go quiet. A core `->` without `arrows.meta` keeps
  no hull, so its line is measured by the stroke only.
- **House block.** `cgtag` takes `outer sep=1mm`: its text then sits
  1.5mm from the centreline, about 1.35mm from a 0.85pt stroke's edge.

## Shipping

- One house-block bump: the old block's digest goes into
  `assets/tikz/cg-figstyle.versions.toml`, and the scaffolds and
  exemplars are restamped.
- Docs: c2 in `docs/FIGURE-DRAWER.md` and the figure-drawer skill's
  `check.md`; `cgtag` in `docs/TIKZ-STYLE.md`; `edge_list`'s stated
  limits.
- Figures moved by the new c2: `control-loop`'s bend tag keeps an
  `outer sep=1.5mm` of its own; `architecture`'s `ledger` tag goes to
  `pos=0.47` and its `finished` tag to `pos=0.45`; `retrieval`'s
  `cap` sits 9mm from `rr` with its `off` tag at `pos=0.35`; the
  `w2-tag`/`t2-tags` examples set `ledger` 38mm from `index`.
  `architecture`'s `ledger` tag still crosses two zone cards (c6),
  as it did before; that is not this change's.
- `node-text-overload` now reads a node's whole braced label, so a
  `\cglab` gloss counts toward the 15 words: the regex it replaced
  stopped at the title's `}`.
- `figure/_focal.declaration`, used by focal-count, `unnamed-pic` and
  the wording rules, keeps its own scanner because it also collects a
  node's options, but takes the shared one's two fixes: a calc position
  reads to its `$)`, and `at` is a keyword only as a whole word. Before,
  `\node[cgkey] at ($(a)!0.5!(b)$) (m) {mid}` was read as a node `b`.
- MINOR version (6.166.0): the block bumps and c2's verdict changes on
  figures that passed, as v5 (6.147.0) and v6 (6.150.0) did.

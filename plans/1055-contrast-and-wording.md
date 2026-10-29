# 🎨 XII-2d: contrast and wording rules

Status: **planned.** Written 2026-10-29 against `main` at `060b424`
(#1054 merged as #1086), from a brainstorming session on issue
[#1055](https://github.com/prasadtalasila/chitragupta/issues/1055) and a
spike recorded under **What the spike found**. Implemented in the same PR
as this plan. Decisions marked *user* were agreed in that session; the
rest was the session's proposal. What changed on the way goes under
**Changed in the build** at the end.

**Written for** whoever builds #1055: a session that changes
`chitragupta/figure/`, `chitragupta/review/figure_layout/`,
`assets/latex/`, `assets/tikz/`, the `figure-drawer` skill, `bench/`,
`tests/` and `docs/`, and is therefore governed by `DEVELOPER-AGENTS.md`
and `docs/CODE-STANDARDS.md`.

**Assumed:** `plans/fig-xii-figure-drawer-v3.md` ("The rules", 2d),
`plans/1053-figure-check-skeleton.md` (the registry, `cg-allow`, the
report), `plans/1054-connector-rules.md` (the probe hook this extends)
and `tests/test_figure_contrast.py` (the house block's WCAG proof).

**Not covered here:** element-scope `cg-allow` (#1058), #1016's
remaining findings (`colour-off-palette`, `tint-outside-band` and the
rest), and redrawing the 49 draft figures the new rules fire on.

## The problem, in one example

```latex
\node[fill=cgAccent!10, text=cgAccent] {decide};
```

Orange text on a pale orange fill is 3.4:1. WCAG 2 asks 4.5:1 of text
and 3:1 of a line, and a reader with weak sight or a greyscale printout
loses the word. The house block (#1047) already gives every hue a darker
`cg<Hue>Text` and `cg<Hue>Line` shade that clears both, and
`tests/test_figure_contrast.py` proves it, but nothing stops a figure
drawing in the plain hue. 30 of the 49 draft figures do (`text=cgAccent`
19 times, `draw=cgAux` 18, `text=cgAux` 8, `text=cgAlt` 4), because they
predate the shades.

## Decisions

- **k1 and k2 are objective everywhere** (*user*), house block or not.
  The fix is a rename (`cgAccent` to `cgAccentText`), and the drafts are
  fixed as they are redrawn.
- **k1 measures box borders and connectors** (*user*). A connector's
  ground is the innermost filled box holding both its ends, or white. An
  arrow crossing a third zone is measured against the wrong ground; that
  is stated in the rule's documentation, not fixed. Lines that are not
  connectors (axes, plots, self-loops) are not measured, and the report's
  existing "lines not between two nodes" count already says so.
- **Colours come from the probe, not the source** (*user*: approach 1).
  The source spells colours through styles, `#1` arguments, `\colorlet`
  and macros; by the time pgf strokes a path, TikZ has resolved them.
- **Text colour is read from the typeset glyphs.** At `\pgfmultipartnode`
  the node's text is already a box; a Lua walk over it reports runs of
  glyphs sharing a colour, size and weight. This catches `text=`,
  `\textcolor` (how `\cglab` colours its gloss), `\color` and macros, and
  gives k2 the real size and weight for WCAG's large-text exception: 3:1
  at 14pt bold or 18pt, where WCAG's points are PostScript points
  (72.27/72 TeX pt each).
- **The ground** of a box's text and border is its own fill, else the
  innermost filled box that contains it, else white. Translucent fills
  are read as opaque and shadows ignored, both stated as limits.
- **w1 and w3 read only `\cglab`** (*user*). There, name and gloss are
  certain. 215 of the drafts' 434 boxes write two lines by hand, and some
  of those are one phrase wrapped, not a name and a gloss.
- **w2 reads tags from the source**: a `node` inside a `\draw` or `\path`
  statement that joins two points. TikZ never keeps a label's tokens, so
  the probe cannot log a tag's words.
- **w1** flags a name that starts lower-case, or whose every later word of
  four or more letters is capitalised (Title Case). Mixed names
  (`Extended Kalman filter`) pass; acronyms never count as capitalised; a
  short list holds words lower-case by convention (`tikz`, `pdflatex`).
- **w4 is objective**: the house fonts lack emoji, so LuaLaTeX drops the
  glyph with a log warning and the reader sees a gap. It flags U+1F000 to
  U+1FAFF, U+2600 to U+27BF, U+2B00 to U+2BFF and U+FE0F in any label;
  arrows, `©`, `™` and math symbols pass; `\ding` and fontawesome commands
  are out of scope, since they print when their package is loaded.
- **#1016 is reconciled in this plan and one comment** (*user*): its
  `accent-not-unique` is `focal-count` (#1080) and its `gloss-too-long`
  is w3; its colour findings should read the `CGPAINT` lines this item
  adds. The comment is posted after merge, and only once the user agrees.
- **The style block goes to v5** for one word: its `\cglab` comment says
  "about eight words", which w3 makes six. v4 shipped in 6.145.0, so the
  word cannot change without a version (the user had preferred fixing it
  on #1054's branch, which merged before this began).
- One PR: this plan, the code, the bench and the docs. MINOR, 6.146.0.
  The PR body says "Part of #1055", never "Closes".

## What the spike found

Compiled through `_probe.scaffold(boxed=True)` with throwaway hooks:

- **pgf's `pgfstrokecolor` goes stale.** `\node[draw, red]` set the
  current colour, not pgf's stroke colour, and the frame logged black. So
  the stroke and fill are resolved from TikZ's own `\tikz@strokecolor` and
  `\tikz@fillcolor`, and from the current colour `.` where TikZ set none.
  xcolor's `\extractcolorspecs` and `\convertcolorspec` give RGB, and both
  must run before `\typeout`, since neither expands.
- **A box's real frame is its last painted node path.** `cgsoft`'s blur
  shadow draws twenty `stroke` and `fill` node paths before the frame's
  `fill,draw`; the last one with `fill` or `draw` in its action is the
  frame.
- **The glyph walk works**: `\cglab{Feature store}{holds vectors}` gave
  12 bold glyphs in `cgInk` and 12 regular in `cgMuteText`; a macro-set
  `\textcolor{cgAccent}` word and `\textbf` both came out as their own
  run. Colour changes are `pdf_colorstack` whatsits (push, pop, set) and
  pgf's `pdf_literal` `rg` operators; the run's starting colour is `.`
  at the node, passed in from TeX.
- **The Lua must be inlined with `%` and `#` at catcode 12**, or TeX eats
  Lua's patterns as comments, and it must hold no `~` (active) and no Lua
  comment (TeX joins lines, so one would swallow the rest).
- An unnamed node's name has to be the hook's `cgu-<n>`, not pgf's empty
  `#3`, or its runs are logged under no name.

## Constraints

- C1 at most 25 statements per function; C2 at most 250 code lines per
  module. Headroom: `_check.py` 218, `_drawn.py` 195, `_probe.py` 239,
  `figure_layout/__init__.py` 247, so the rules go in new modules and
  `_check.py` gains only calls.
- The probe runs under the `openin_any=p` read fence, so the hook and its
  Lua stay inlined.
- One `\typeout` per path's paint and one per text run, each far under
  `max_print_line`.

## Inputs the tests must cover

1. k2 fires on faint text set by `text=`, by `\textcolor`, and by a macro
   that expands to one. A version that only reads `text=` was built the
   cheap way.
2. Must-not-fire: a `cg<Hue>Text` shade; a step badge's white digit on
   its Text fill; large bold text at 3.4:1 (and the same colour at 12pt
   fires); an unfilled box inside a zone, measured against the zone.
3. k1 fires on `draw=cgAux` on its own tint and on a `cgAux` arrow on
   white; it does not on `cgAuxLine`, nor on a connector inside a zone
   whose Line shade clears the zone's tint.
4. k1 and k2 are not measured, with the reason, where the figure does not
   compile, the probe logged nothing, the file has several pictures or it
   uses `transform canvas`.
5. w1 to w3 must-not-fire: `Extended Kalman filter`, `RAG pipeline`,
   `\texttt{pdflatex} run`, a `$x_k$` formula counted as one word, a
   three-word lower-case tag.
6. w4 fires on `✓` and an emoji with its variation selector; not on `→`,
   `©` or `\ding{51}`.

## Tasks

Each task is test-first, and ends in a commit.

1. **`_colour.py`.** WCAG luminance and contrast, xcolor mixing and the
   two thresholds, moved out of `tests/test_figure_contrast.py`, which
   then imports them.
2. **The probe logs paint and text.** `cg-figure-probe.tex` adds
   `CGPAINT <index> <stroke> <fill> <stroke-expr>|<fill-expr>` before each
   `CGPATH`, RGB as `r,g,b` or `-`, and `CGTEXT <r,g,b> <size-pt> <0|1>
   <glyphs> <name>` per run plus `CGTEXTCOLOR <expr>` before each
   `CGNODE`. `_drawn.py` gives `DrawnNode` `fill`, `stroke`, their
   expressions and `runs`, and `DrawnLine` `stroke` and its expression.
   A TeX test compiles a known figure and checks the values.
3. **k1 and k2.** `chitragupta/figure/_contrast.py`: the ground, the two
   rules, the measurement strings and the not-measured reasons. A colour
   is named by its expression, else by the figure's own `\definecolor`
   of that hex, else as hex.
4. **w1 to w4.** `chitragupta/figure/_wording.py` over the source:
   `\cglab` arguments, tags, pictographs.
5. **Wiring.** The six ids in `_rules.py`, `_check.py` calling both
   modules, w1 to w3 under the advisory heading, k1, k2 and w4 as
   findings.
6. **Bench.** `bench/bench_contrast_wording.py` over the drafts, the
   scaffolds and the exemplars, recorded in `bench/RESULTS.md`; the
   scaffolds and exemplars must report no objective finding.
7. **Block v5, docs and release.** The `\cglab` comment's six words, v5
   in `cg-figstyle.versions.toml`, `figure sync` over every carrier; the
   v3 plan, `docs/TIKZ-STYLE.md`, the skill's `references/check.md`,
   `docs/CLI.md`, the roadmaps; the version, the docs sweep and the local
   checks.

## Changed in the build

*(Filled in as the build goes.)*

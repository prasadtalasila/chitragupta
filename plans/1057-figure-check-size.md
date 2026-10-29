# 📏 XII-2f: size and budget reporting in `figure check`

Status: **built.** Written 2026-10-29 against `main` at `aaf3c47`, from
a brainstorming session on issue
[#1057](https://github.com/prasadtalasila/chitragupta/issues/1057), and
implemented in the same PR as this plan, as #1053 was. The decisions
marked *user* were agreed in that session; the rest was the session's
proposal.

**Written for** whoever builds #1057: a session that changes
`chitragupta/figure/`, `chitragupta/review/figure_layout/_geometry.py`,
the `figure-drawer` skill's references, `assets/tikz/`, `tests/` and
`docs/`, and is therefore governed by `DEVELOPER-AGENTS.md` and
`docs/CODE-STANDARDS.md`.

**Assumed:** `plans/fig-xii-figure-drawer-v3.md` ("The rules", Size
table), `plans/1053-figure-check-skeleton.md` (the registry, report and
allow grammar this plugs into), FIGURE-ROADMAP VI.3 and "Considered and
set aside", and the layout reference files #1049 added under
`.claude/skills/figure-drawer/references/layouts/`.

**Not covered here:** connector rules (#1054), contrast and wording
(#1055), twin agreement (#1056), element-scope `cg-allow` (#1058),
`figure new` (#1052), and the five Phase 3 layouts, which bring their
own reference files.

## What it is for

A drafting agent sees sprawl and squash before a reader does. `figure
check` prints the figure's height, slack, node count and edge count
beside the reference range of the figure's layout, and flags an arrow
too short to read. All five are advisory: read, never resolved, never
allowed, never a gate, and a range is never a cap.

## Decisions

| Question | Decision |
| --- | --- |
| How check knows a figure's layout | **A `% cg-layout: <name>` line in the figure, and `--layout NAME` to override it** (*user*). Added now to the seven scaffolds and three exemplars, so a figure copied from a scaffold carries it. Phase 3 had already named the line. No declared layout: the numbers print bare and say so. An undeclared name with no reference file: the numbers print and say that. Never a guess from structure |
| Where the ranges come from | **The layout file's `## Reference ranges` table, min to max over its rows** (scaffold and exemplars). `tests/test_tikz_scaffolds.py` already re-measures every row against the probe, so a range moves only when its source does. The table parser moves from that test into `chitragupta/figure/_layout.py`, and the test uses it, so the check and the guard read the table one way |
| Where the advisory reports go | **Their own list, `CheckResult.advisory`, not `findings`.** VI.3: a range "does not authorise a finding when a figure exceeds it". `findings` stays what the skill must resolve or allow, so every existing "clean" assertion keeps its meaning. Text gets an "advisory (read; never resolved, allowed or capped)" section, JSON an `advisory` key with the findings' shape |
| Which advisory reports always print | The four range reports print whenever measurable, inside or outside the range, with no "over" or "under" wording: the reader judges. `size-squash` prints only for a pair it finds |
| Allowable | **No.** An advisory report is read, so an allow has nothing to set aside; `% cg-allow: size-slack -- ...` is reported as malformed, "cannot be allowed", like `does-not-compile` |
| Slack | `1 - (leaf node area) / (picture area)`, where a leaf is a node that wholly encloses no other (a zone card is not filled area). This is the reference tables' definition; `_geometry.leaves()` is the one implementation both use. `review figure`'s emptiness diagnostic, which counts zones, is unchanged |
| Height | Picture height over 700pt, the render's 12pt A4 1in text height that the reference tables already divide by. `--width` does not move it |
| Squash | A pair joined by an edge whose boxes are under 3mm (8.54pt) apart, edge to edge (Euclidean between the boxes). Skipped: a self-edge, a zero-area endpoint (a coordinate, a bend point), a pair where one box encloses the other (a zone and its child), and a pair whose boxes intersect (`node-overlap` already reports that). An endpoint carrying a leading option (`[xshift=6mm]a.south`) or an anchor resolves to its node |
| Unreadable edges | Listed under "not measured" for `size-squash`, never silently skipped: an edge with an end that resolves to no measured box, a point built from two nodes (`b.north -\| a`, a calc `$...$`), which is neither of them, and every pair from a path with an `edge` operator or a named node on it, since `edge_list` pairs consecutive tokens and `(hub) edge (s1) edge (s2)` would otherwise read as `s1` joined to `s2`. `edge_list` itself, and so `budget-edges`, is unchanged, because the reference tables were measured with it |
| Several pictures | Height, slack and squash are not measured, with the reason, as `size-stray` already is: the probe reads the last picture's extent, and an earlier picture's boxes are in another frame. The counts are read from source and still print |

## Bench

Run over the seven scaffolds, three exemplars and 49 draft figures of
the reference book (`content/drafts/`, local) before the threshold was
fixed:

- No scaffold or exemplar squashes; the smallest edge gap among them is
  6mm (`pipeline`, `zoned-spine`).
- One draft figure squashes: `three-layers` (`mgr`/`core`, 2.9mm), a
  short arrow a reader would squint at. The first cut also reported
  `timer`/`gap` in `demonstrator-today` (0.3mm) and `dosing-today`
  (2.0mm); `gap` is a label placed on the `store -> timer` path, so
  both were pairs nothing joins (see "Changed in the build").
- The next-smallest draft gap is 3.7mm (`model-anatomy`), so 3mm does
  not sit on a cluster.
- 18 of the 59 files list at least one edge under "not measured" for
  `size-squash`: perpendicular coordinates (`chan -| gate.west`), loop
  macros (`s\i`), math the parser took for a node (`z_1 \mid x_1`),
  and paths with `edge` or a named label. Listed, as the v3 plan asks,
  rather than skipped.

## Changed in the build

An independent review of the first cut found three defects, each fixed
with a test before the PR: an empty picture's placeholder extent
(`(16000,16000,-16000,-16000)`, negative on both axes) passed a
`width * height <= 0` test and printed a negative height; a perpendicular
coordinate `b.north |- c` resolved to `b`; and an `edge` chain or a named
mid-path label made `size-squash` measure pairs nothing joins. The last
is `ambiguous_edges()` in `review/figure_layout/_source.py`.

## Components

| Unit | Does |
| --- | --- |
| `chitragupta/figure/_layout.py` | `declared_layout(source)`, `layout_names()`, `RangeRow`, `range_rows(text)` and `reference(layout)`: the reference file's rows, or `None` where there is no file |
| `chitragupta/figure/_advisory.py` | `advise(figure, source, layout, rows, unmeasurable)`: the five advisory reports and what could not be measured. `TEXT_HEIGHT_PT`, `SQUASH_PT`, `slack(boxes)` |
| `chitragupta/figure/_rules.py` | Five advisory rules, not allowable; `Finding` moves here so `_advisory` and `_check` share it without a cycle |
| `chitragupta/figure/_check.py` | `apply()` and `check()` take `layout`; `CheckResult` gains `advisory` and `layout` |
| `chitragupta/figure/_check_report.py` | The advisory section and JSON key, and the layout used |
| `chitragupta/figure/__main__.py` | `--layout NAME`, its choices the reference files present |
| `chitragupta/review/figure_layout/_geometry.py` | `leaves(boxes)` and `edge_gap(one, other)`, beside `_contains` and `_intersects`, which they reuse |
| `chitragupta/review/figure_layout/_source.py` | `ambiguous_edges(source)`: the `edge_list` pairs from a path with `edge` or a named node on it |

## Tests

- `_layout`: the declared line (full-line comment only, first wins, an
  empty name is none), the table parse, `None` for an unknown layout.
- `_advisory`: each report from hand-built `FigureResult`s; the
  must-not-fire squash cases (coordinate endpoint, zone and child,
  overlapping pair, self-edge, far pair); anchor and option resolution;
  unreadable edges listed; several pictures; no geometry.
- Report and JSON: the section, the key, the layout line, and that an
  advisory report never changes the "No findings" line.
- Cross-check: every scaffold declares its own layout, and every
  exemplar declares the layout whose file measures it.
- Real LuaLaTeX: a scaffold reports its own range; a fixture squashes.

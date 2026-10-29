# 🧹 XII-1e: the scaffolds and exemplars, clean under the v3 rules

Status: **built.** Written 2026-10-29 against `main` at `d1ab339`,
from a brainstorming session on issue
[#1050](https://github.com/prasadtalasila/chitragupta/issues/1050), and
implemented in the same PR as this plan, the way #1080 was. The
decisions marked *user* were put to the user in that session and
answered; the rest is the session's proposal, which the user approved
as a whole. What changed on the way is in **Changed in the build** and
**Outcome** at the end.

**Written for** whoever builds #1050: a session that changes
`assets/tikz/`, the `figure-drawer` skill's layout reference files and
`tests/test_tikz_scaffolds.py`, and is therefore governed by
`DEVELOPER-AGENTS.md` and `docs/CODE-STANDARDS.md`.

**Assumed:** `plans/fig-xii-figure-drawer-v3.md` (the v3 design this is
item 1e of, especially "The rules" and "Connector rules"),
`plans/1053-figure-check-skeleton.md`, `docs/TIKZ-STYLE.md`, and the
layout reference files under
`.claude/skills/figure-drawer/references/layouts/` that #1073 (1d)
shipped.

**Not covered here:** the `c1` to `c6` checkers themselves (#1054),
`figure new` keeping the `% cg-layout:` line (#1052), a `.txt` twin for
every scaffold (#1056), and any figure in `content/drafts/` (the v3
plan's "Migration": no sweep).

## Where it lands

`main`. Branch `fig-xii-1e-scaffolds-clean` off `origin/main`, PR into
`main`. The PR is not merged until the user approves it (*user*).

## What it is for

A drafting agent copies a scaffold or an exemplar and starts from
something already clean under the rules `figure check` holds it to.
Today it can import three kinds of defect it would then be told to fix:
a figure wider than the text, an edge that lands off its side's
midpoint, and (in the tree) diagonal edges.

## What is wrong today

Measured 2026-10-29 on `d1ab339`, LuaLaTeX, article class at 12pt, the
render's fonts.

**Width.** `figure check` over all ten files: one finding.

| File | Width | Target |
| --- | --- | --- |
| `exemplars/rag-stages.tex` | 495.0pt | 453.0pt |

The two other wide files clear the target with little to spare:
`exemplars/retrieval` at 445.1pt and `exemplars/architecture` at
433.1pt. Nothing below may push either past 453pt.

The stage grid itself is 411.5pt: with the legend removed, or stacked
one entry per row, the picture measures 411.5pt. What overflows is the
legend's first row, "a guarantee none of the six compared systems has"
followed 8mm later by "the one blocking check". The file's header says
it was laid out to acmart sigconf's 506.3pt text width, which is the
wrong target; the render's is 453pt.

**Edge attachment.** No `c4-attach` checker exists yet (#1054), so this
was measured with a throwaway probe built on the #1054 spike: it
compiles the figure with a hook that logs every path TikZ strokes and
every named node box, assigns each stroke end to the smallest box it
lands on (within 1.5pt), takes the nearest side of that box, and
reports the end's offset from that side's midpoint. Only strokes whose
two ends land on two different named nodes count as edges. Every node
involved is a rectangle, so the probe's known shrinkage of circle boxes
does not apply.

A *lone* edge is the only edge on its side; `c4-attach` wants it within
0.5mm of the midpoint. A side with N edges wants them at `L*k/(N+1)`,
within 1mm, at least 2mm apart.

| File | Side | Edges | Offsets from midpoint (mm) | Side length (mm) |
| --- | --- | --- | --- | --- |
| `control-loop` | `control.E` | 1 | +2.90 | 11.3 |
| `control-loop` | `estimate.W` | 1 | +2.93 | 11.3 |
| `control-loop` | `plant.E` | 1 | -2.93 | 11.4 |
| `control-loop` | `sensor.W` | 1 | -2.92 | 11.3 |
| `exemplars/architecture` | `enrich.E` | 1 | -0.67 | 18.7 |
| `exemplars/architecture` | `review.W` | 1 | +0.67 | 17.8 |
| `exemplars/architecture` | `review.N` | 1 | -6.0 | 30.4 |
| `exemplars/architecture` | `draft.S` | 2 | -6.0, +7.0 | 26.4 |
| `exemplars/architecture` | `gate.S` | 2 | 0.0, -5.0 | 30.6 |
| `exemplars/retrieval` | `q.E` | 2 | 0.0, 0.0 | 11.3 |
| `branching-tree` | `source.S` | 2 | -7.8, +7.8 | 21.6 |
| `branching-tree` | `batch.S`, `live.S` | 2 each | -3.86, +3.86 | 21.4 |
| `branching-tree` | each of the 6 children's `.N` | 1 | ±3.86 or ±7.72 | 21.4 |

`pipeline`, `zoned-spine`, `hub-and-spoke-network`, `map`,
`layered-stack` and `rag-stages` are clean.

**Diagonals.** The same probe counts two-point straight edges whose ends
differ by more than 1mm in both x and y, the shape `c1-orthogonal`
objects to: `branching-tree` has 6, every other file 0.

**Edge tags.** Nothing to fix. Since #1078 (1b), `cgtag` is `auto` with
0.5mm inner and outer sep, so every tag already sits beside its line,
which is what the issue's "adopt v3's tag placement" asks for.

**`% cg-layout:`.** No file carries one.

## Decisions

- **Scope: all of `c4`, and the tree redrawn orthogonal** (*user*). The
  issue's checklist names lone edges only. The two-edge sides and the
  tree's diagonals are the same kind of defect a copier imports, so
  every file is brought clean under `c4` and `c1` as the v3 plan states
  them, and #1054 needs no tree exemption.
- **Verification: the probe now, #1054 pins it** (*user*). The
  attachment and diagonal numbers are measured with the throwaway probe
  before and after, and the table goes in this plan and the PR body. No
  attachment test is added here: #1054's bench runs `c4` over the
  scaffolds and its fixtures pin them clean, and nothing in 1e
  duplicates #1054's geometry. The probe stays outside the repository.
- **`rag-stages`: two grid-aligned legend columns** (*user*), not a
  stacked legend (about 13mm taller) and not shorter wording (edits the
  exemplar's content). The wording is kept.
- **Before/after images go to the user in the session** (*user*), not
  into the repository or an orphan branch. The PR body lists the files
  and their measured numbers.
- **A layout id is its scaffold's file stem.** The v3 plan's `c1` row
  exempts `hub-and-spoke`; the scaffold, its reference file and the
  routing table all say `hub-and-spoke-network`, so the stem wins and
  the v3 plan's row is corrected, the way #1053 corrected the finding
  names there.

## The change

### 1. The `% cg-layout:` line

Every scaffold and exemplar carries `% cg-layout: <id>` as its **first
line**, where #1052's `figure new` and #1054's rule exemptions can find
it without reading past the style block.

| File | Id |
| --- | --- |
| `pipeline`, `zoned-spine`, `branching-tree`, `hub-and-spoke-network`, `map`, `control-loop`, `layered-stack` | its own stem |
| `exemplars/architecture`, `exemplars/retrieval` | `zoned-spine` |
| `exemplars/rag-stages` | `pipeline` |

An exemplar's id is the layout whose reference file already measures
it, so the line and the reference table cannot disagree. `cg-figstyle.tex`
is not a figure and carries none.

Tests, in `tests/test_tikz_scaffolds.py`:

- each scaffold carries exactly one `% cg-layout:` line, on line 1,
  naming its own stem;
- each exemplar carries exactly one, on line 1, naming the layout whose
  reference file lists it (the existing
  `test_every_exemplar_is_measured_under_exactly_one_layout` already
  guarantees there is exactly one such file);
- a doctored id is caught (the polarity rule: every check has a
  must-fire case).

### 2. `rag-stages`: the legend

Keep the two-by-two legend and the wording. Column one's swatches stay
under `s9`, as today. Column two's swatches move to `s3.west`'s x (the
third card column) instead of sitting 8mm after column one's text. Each
column's text gets a `text width` ending one `node distance` short of
the next column, or at `s4.east` for column two, so the legend can never
be wider than the grid. Both long entries ("a guarantee none of the six
compared systems has", "absent or partial, and named as such") then wrap
to two lines. The 6.5mm row pitch grows to clear a two-line entry, so
the figure gets slightly taller. Target: `figure check` clean at 453pt,
expected to be the grid's 411.5pt, with no `\resizebox`.

Rewrite the header's WIDTH paragraph for the render's 453pt text width,
keeping its argument (the grid is four cards because six do not fit at
the type floor). `retrieval`'s header and `layouts/pipeline.md`'s prose
make the same 506pt claim; correct both.

### 3. `control-loop`: anchors on the bends

`(plant.east) to[bend right=12] ... (sensor.west)` and
`(estimate.west) to[bend right=12] (control.east)`. The bend stays: it
is the scaffold's idiom for the cycle closing, and `c1` does not apply
to it because the two ends share a y.

### 4. `architecture`: three sides

The picture is 433.1pt wide at 12pt, so about 7mm of headroom.

- **`enrich` to `review`.** Place `review` at `(draft |- enrich)`
  rather than `below=18mm of draft`, so its centre shares `enrich`'s y
  and the edge between them is level. Anchoring the ends instead would
  leave the line slanted.
- **`draft.S`.** The `finished` edge leaves at `L/3` and the `FAIL`
  return arrives at `2L/3` (about 4.4mm either side of centre, against
  -6mm and +7mm today), replacing the hand-picked `xshift`s.
- **`review.N`.** `review` cannot move left under `finished`'s start:
  `enrich` must stay centred under `sync` (its own lone edge), and the
  zone cards round `enrich` and `review` are 3mm apart today, so a 4.4mm
  shift would overlap them. `finished` is therefore an elbow: down from
  `draft`'s `L/3` point to the channel's y, 4.4mm across, down into
  `review.north` at its midpoint. Its horizontal leg ends where the
  `FAIL` return's begins, so the two never share a stretch.
- **`gate.S`.** The `OK` edge leaves at `2L/3` and `FAIL` at `L/3`.
  `pub` moves right by `L/6` of `gate` (about 5mm) so `OK` stays a
  straight vertical into `pub.north`'s midpoint. That costs about 14pt
  of width, an estimated 447pt, which `figure check` confirms is under
  453pt. If it is not, `OK` takes the same elbow `finished` does.

### 5. `retrieval`: the fork out of `q`

The two edges leaving `q.east` start at `L/3` and `2L/3` of that side
(about 3.8mm apart) instead of from one point. Today both run the same
first 7mm out of `q` before they split, which `c3-coincident` would also
flag. With separate start points each takes its own 7mm run and then
turns: the upper one up to `bm.west`, the lower one down to `emb.west`.
The picture is 445.1pt wide and this does not change its width.

### 6. `branching-tree`: orthogonal edges, fanned

Keep the `child` idiom, which the scaffold's header explains, and give
it an `edge from parent path`: leave the parent's south side at
`k/(N+1)` of its width, using `\tikznumberofcurrentchild` and
`\tikznumberofchildren` with `calc`'s partway syntax between
`\tikzparentnode.south west` and `.south east`; drop to half-way to the
child; run across; come down into `\tikzchildnode.north`. Every edge is
then orthogonal (`c1`), no two siblings share a stretch (`c3`), every
child's north side has one edge at its midpoint and every parent's
south side has its two at `L/3` and `2L/3` (`c4`). The header's idiom
paragraph says what the path does and why.

### 7. The reference files

Each changed file's row in `layouts/pipeline.md`, `zoned-spine.md`,
`branching-tree.md` and `control-loop.md` is re-measured:
`test_extents_match_the_probe` prints the row to paste back. A range
moves because its exemplar did, which is the rule #1049 set. Prose that
describes a changed figure (`branching-tree.md` on how the edges are
drawn, `pipeline.md` on the legend and the 506pt width) is brought into
line.

## Verification

- `figure check` over all ten files: no finding.
- The probe, after: every lone edge within 0.5mm of its side's
  midpoint, every two-edge side at `L/3` and `2L/3` within 1mm and at
  least 2mm apart, no diagonal. The after table replaces "What is wrong
  today" as this plan's outcome record.
- `tests/test_tikz_scaffolds.py` in full, then the whole suite. No
  product code changes, so line and branch coverage stay at 100% with
  nothing to add.
- markdownlint over the changed Markdown.
- A before/after PNG of each of the five changed figures, sent to the
  user in the session after the PR opens.

Nothing here generates, guesses or rewrites a citekey, and no check is
promoted into a gate.

## Implementation plan

> **For agentic workers:** run this in order in one session (the user
> chose to proceed directly). Steps use checkbox (`- [ ]`) syntax.

**Goal:** every file in `assets/tikz/` fits 453pt at 12pt, every edge
end sits where `c4-attach` wants it, no tree edge is diagonal, and each
file names its layout.

**Architecture:** figure-source edits only, plus one new test class.
No product code changes.

**Tech stack:** TikZ (`positioning`, `calc`, `trees` via `child`),
LuaLaTeX through `python -m chitragupta.figure check`, pytest.

**Spec:** the sections above.

### Global constraints

- Width at most 453pt at 12pt, measured by `figure check`; never
  `\resizebox`, never a smaller font.
- A lone edge within 0.5mm of its side's midpoint; N edges on a side at
  `L*k/(N+1)` within 1mm and at least 2mm apart; no straight edge whose
  ends differ by more than 1mm in both x and y.
- The house block stays byte-identical to `assets/tikz/cg-figstyle.tex`
  (`test_carries_the_block_once_and_verbatim`).
- `% cg-layout: <id>` is line 1 of every scaffold and exemplar.
- No citekey anywhere in a figure file.

### Review focus

- **`figure sync` on a file whose first line is `% cg-layout:`.** The
  start marker must still be found and the block upgraded in place;
  `_block.py` searches for it anywhere, so add a sync round-trip over
  every carrier to Task 1's tests.
- **A copier adds a third child to the tree.** The `edge from parent
  path` must fan at `L/4`, `L/2`, `3L/4` without edits; check it once
  with the probe on a throwaway three-child copy in Task 6.
- **A draft started from a scaffold** still reports no finding
  (`test_a_draft_that_starts_from_a_scaffold_reports_no_finding` covers
  it; it must stay green).
- **`size-stray`.** A leading comment line adds no width; `figure check`
  over all ten files in Task 7 shows it.
- **Rendered PDF, not only the probe.** The before/after PNGs are
  rendered from the real files, so a fix that the probe accepts but that
  looks wrong is caught by eye.

### Task 1: the `% cg-layout:` line

**Files:** every `assets/tikz/*.tex` except `cg-figstyle.tex`, every
`assets/tikz/exemplars/*.tex`; test in `tests/test_tikz_scaffolds.py`.

- [ ] Write `class TestEveryFigureNamesItsLayout` with
  `test_each_scaffold_names_its_own_layout` (parametrized over
  `_scaffolds()`: `lines[0] == f"% cg-layout: {path.stem}"` and the
  marker occurs once), `test_each_exemplar_names_the_layout_that_measures_it`
  (the stem of the one layout file whose range rows list the exemplar),
  `test_a_doctored_layout_line_is_caught` (the helper rejects
  `% cg-layout: pipeline` for `branching-tree.tex`), and
  `test_sync_still_finds_the_block_below_it` (`_block.region` state is
  `CURRENT` for every carrier).
- [ ] Run them: the first two fail on every file.
- [ ] Add the line to all ten files.
- [ ] Run `tests/test_tikz_scaffolds.py`: pass. Commit.

### Task 2: `rag-stages` legend and header

**Files:** `assets/tikz/exemplars/rag-stages.tex`,
`.claude/skills/figure-drawer/references/layouts/pipeline.md`,
`assets/tikz/exemplars/retrieval.tex` (header only).

- [ ] Re-lay the legend as section 2 says; rewrite both headers' WIDTH
  paragraphs to the render's 453pt.
- [ ] `figure check` it: no finding. Probe: still clean.
- [ ] Paste the re-measured row and fix the 506pt prose in `pipeline.md`;
  `TestTheReferenceRangesAreMeasured` passes. Commit.

### Task 3: `control-loop` anchors

- [ ] Anchor both bends as section 3 says; probe: four ends within
  0.5mm. Re-measure the `control-loop.md` row if it moved. Commit.

### Task 4: `retrieval` fork

- [ ] Split the two `q.east` starts as section 5 says; probe: `q.E` at
  about ±1.9mm, no shared run. Re-measure the `zoned-spine.md` row.
  Commit.

### Task 5: `architecture`

- [ ] Apply section 4; `figure check` under 453pt; probe: every side
  clean. Re-measure the `zoned-spine.md` row. Commit.

### Task 6: `branching-tree`

- [ ] Add the `edge from parent path` as section 6 says and rewrite the
  idiom paragraph; probe: 0 diagonals, every side clean; check a
  three-child throwaway copy. Re-measure `branching-tree.md` and fix its
  edge prose. Commit.

### Task 7: verification and records

- [ ] Correct the v3 plan's `c1` row to `hub-and-spoke-network`.
- [ ] `figure check` over all ten files; probe over all ten; write the
  after table into this plan's status and outcome.
- [ ] Full suite (`.venv-full`, `PYTHONPATH` set to the worktree), ruff,
  markdownlint, `scripts/` local checks DEVELOPER-AGENTS.md names.
  Commit, push, open the PR into `main`, send the before/after PNGs,
  and wait for the user's approval before merging and releasing.

## Changed in the build

- **`architecture` went further than section 4.** Rendered in the
  render's own fonts (STIX Two, 12pt), it had three defects no rule
  measures, because zone titles and tags are unnamed nodes: the zone
  title "Deterministic --- no model is called" (83.0mm) ran 9mm into
  "Generative" over a 71.2mm card; "Enrichment" broke as "Enrich-ment"
  in its 27mm box (the name is 28.9mm); and the `finished` and FAIL
  tags overlapped. All three are fixed, since the figure was being
  re-laid there anyway: the title breaks onto two lines (a picture-local
  `cgzonetitle/.append style={align=left}`, the block untouched),
  `enrich` is 29.5mm, and the two tags sit either side of the FAIL
  channel inside the `Generative` card.
- **`finished` is straight, not an elbow.** Section 4's elbow crowded
  the 18mm channel once both tags were inside the card. Instead
  `review` narrows to 24mm and sits under `finished`'s third of
  `draft`, level with `enrich`; `bib` to `sync` closes from 10mm to 7mm
  and `sync` to `draft` opens from 13mm to 17mm, so the zone cards stay
  apart. `pub` still moves under `gate`'s right third. Width 433.1pt
  becomes 448.8pt.
- **`rag-stages`' legend breaks by hand, not by `text width`.** A
  62mm text width hyphenated "com-pared" and left "such" on a line of
  its own; a `\\` where the sense breaks, with `align=left`, keeps the
  entries whole and the legend inside the grid's width.
- **A width test for every file.** `TestDrawnAtFinalWidth` held only
  the scaffolds, to the article class's 345pt; it now also runs
  `figure check`'s `size-width` over every scaffold and exemplar at the
  render's 453pt, which is the issue's first criterion pinned.
- **The firing case #1080 pinned on `rag-stages` moved.**
  `tests/test_figure_check.py` used the exemplar's overflow as its real
  figure that breaks `size-width`, and `docs/CLI.md` quoted that report.
  Both now check it against the article class's 345pt with `--width`,
  which it still overflows (411.5pt). `assets/tikz/README.md` says to
  keep the `% cg-layout:` line when copying a scaffold.
- **Left for #1054's bench.** Two tag placements in the exemplars still
  cross a zone border or touch a card in the render's fonts:
  `architecture`'s "ledger" spans the 3mm gap between two zone cards,
  and `retrieval`'s "off" touches the cross-encoder card. They are
  `c2-tag-clearance` and `c6-tag-covered` cases, outside this item's
  scope, and the bench will measure them.

## Outcome

Measured on the PR branch with the same probe and `figure check`:

- `figure check` over all ten files: no finding.
- Widths at 12pt: `rag-stages` 495.0pt to 411.5pt, `architecture`
  433.1pt to 448.8pt, `retrieval` 445.1pt (unchanged).
- Edge attachment: 94 node sides carry an edge across the ten files;
  every lone edge is within 0.5mm of its side's midpoint and every
  two-edge side is at `L/3` and `2L/3` within 1mm. The 19 off-rule
  sides in the table above are all fixed.
- Diagonals: 0 in every file (the tree's 6 are gone). A throwaway
  three-child copy of the tree fans at `L/4`, `L/2` and `3L/4` with no
  edit.
- Reference rows re-measured: `rag-stages` (width 1.09 to 0.91) and
  `architecture` (10 edges to 9, the FAIL route now one source-parser
  leg fewer; width 0.96 to 0.99).

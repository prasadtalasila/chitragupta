# Timeline scaffold (#1064) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `timeline` layout (scaffold, twin, reference file,
exemplar) and the two measurement fixes it depends on, then release it.

**Architecture:** Two fixes come first, because without them the
timeline passes only because nothing is measured. The probe measures a
quarter-turned node's real box, and `zones()` stops treating a node that
covers a coordinate as a card. Then the scaffold and the exemplar are
added the way #1063 added `sequence`, through the globs and lists that
pick up every layout.

**Tech Stack:** Python 3.14 (`.venv-full`), LuaLaTeX/TikZ (TeX Live
2025), pytest with pytest-cov.

**Spec:** `plans/1064-timeline-scaffold.md`. Read it first; this plan
argues from its decisions D1 to D11 and does not repeat them.

## Global Constraints

- Governed by `DEVELOPER-AGENTS.md` and `docs/CODE-STANDARDS.md`.
- No citekey is generated, guessed or rewritten anywhere, fixtures
  included. No check becomes a gate: `figure check` still exits 0.
- Every scaffold fits 345pt; every exemplar fits 453pt.
- No node at a millimetre coordinate. Events are placed by fraction,
  `($(t0)!<f>!(tend.west)$)`; `right=108mm of t0` is relative, and allowed.
- Event labels are `rotate=90, anchor=east`: they read bottom to top and
  end at the tick. `rotate=-90` is wrong (it reads top to bottom).
- Era titles stay level and must fit inside their card.
- No `\foreach` in the scaffold or the exemplar. No `\|` in a
  TIKZ-STYLE table cell.
- The house block (v6) is copied verbatim; the new styles (`cgtick`,
  `cgaxis`, `cgevent`) go in the picture's options.
- `timeline` exempts no rule.
- Version: MINOR, from `6.151.2` to `6.152.0`, unless `main` has moved
  past it by PR time.
- Line and branch coverage stay at 100%.
- Commit messages follow `DEVELOPER-AGENTS.md`'s Commit messages section and end
  with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never
  amend or force-push; a version collision is fixed by merging
  `origin/main` and bumping again.

**Running things.** In this worktree:

```bash
W=/home/prasad/git/chitragupta-freja/.claude/worktrees/bridge-cse_013sgX9dHBDd2QHVYcGKihNT
PY=/home/prasad/git/chitragupta-freja/.venv-full/bin/python
cd $W && export PYTHONPATH=$W     # absolute; a relative one breaks test_init
$PY -m pytest tests/test_figure_drawn.py -q
$PY -m chitragupta figure check assets/tikz/timeline.tex --width 345
```

`config.toml` is already copied from `config.toml.example`. Never pass a
relative `CONFIG_PATH`.

## Review Focus

1. **An unturned node's box must not move.** The four-anchor min/max
   has to equal today's west/south/east/north box for every unturned
   shape: circle, `circle split`, `cylinder`, rectangle. Pinned by Task 1's
   `test_an_unturned_node_keeps_its_box`, and checked over every
   scaffold by Task 5's ripple.
2. **A turned label that ends at its tick must not overlap the tick.**
   `anchor=east` plus `yshift=-1mm` leaves a gap; a label set flush
   would fire `node-overlap` against its own tick, and the reference
   file has to say so. Pinned by Task 3's clean scaffold.
3. **`rotate=-90` must measure the same way as `rotate=90`.** An author
   will make the same direction mistake the probe made. Pinned by Task
   1's parametrised turn test (`b=1,c=-1` and `b=-1,c=1`).
4. **A scaled node (`scale=2`, no turn) must not be read as turned.**
   Its `b` and `c` are 0, so it stays unturned. A `rotate=90, scale=2`
   node has `|b| = 2` and stays `rotated`, set aside. Pinned in Task 1.
5. **A zone card that really does contain a coordinate and a member**
   (a `cgzone` fitted to `(b1 |- band)`, which is the spec's own idiom,
   holding a title) must still be a zone. Pinned by Task 2's
   `test_a_card_holding_a_title_and_a_coordinate_is_still_a_zone`.

---

### Task 1: Measure quarter-turned nodes

**Files:**

- Modify: `chitragupta/review/figure_layout/_probe.py` (`scaffold()`
  preamble and its `probes` string, lines 160-195)
- Modify: `assets/latex/cg-figure-probe.tex` (`\cgdumpnodes`, lines
  142-163)
- Modify: `chitragupta/review/figure_layout/_drawn.py` (`_node`, the
  module docstring's `CGNB` paragraph, `DrawnNode.rotated`'s comment)
- Modify: `chitragupta/figure/_overlap.py` and
  `chitragupta/figure/_clearance_rules.py` docstrings ("a turned node"
  becomes "a node turned other than a quarter")
- Create: `tests/fixtures/figure/check/turned-collide.tex`, `turned-clean.tex`
  and `unturned-shapes.tex`, each with its `.txt`
- Test: `tests/test_figure_drawn.py`, `tests/test_figure_check.py`

**Interfaces:**

- Produces: TeX macro `\cgsides{<node name>}`, defined in the probe
  preamble, which sets the dimens `\cgx`, `\cgy`, `\cgxx`, `\cgyy` to the
  min x, min y, max x, max y over the points of the `west`, `south`,
  `east` and `north` anchors. The `CGBOX` and `CGNB` log grammars are
  unchanged; only the numbers in them change for a turned node.
- Produces: `DrawnNode.rotated` is `True` only for a turn that is not a
  quarter turn. A quarter turn is `abs(abs(b) - 1) < 1e-4` and
  `abs(b + c) < 1e-4`, where `b` and `c` are the logged transform entries.

- [ ] **Step 1: Write the failing parse tests** in
      `tests/test_figure_drawn.py`, class `TestParse`:

```python
@pytest.mark.parametrize(
    ("turn", "text_box"),
    [("1.0 -1.0", (-6.0, 0.0, 2.0, 20.0)), ("-1.0 1.0", (-2.0, -20.0, 6.0, 0.0))],
)
def test_a_quarter_turned_text_box_is_turned_about_its_anchor(self, turn, text_box):
    """`rotate=90` reads bottom to top, `rotate=-90` top to bottom; both
    are measured, and neither is set aside (#1064)."""
    drawn = parse_drawn(
        _log("CGNODE 20.0pt 6.0pt 2.0pt rectangle/e3-n",
             f"CGNB -7.0 -1.0 3.0 21.0 0.0 0.0 {turn} e3-n")
    )
    node = drawn.nodes["e3-n"]
    assert node.rotated is False
    assert node.text_box == text_box

@pytest.mark.parametrize("turn", ["0.70711 -0.70711", "2.0 -2.0"])
def test_a_slanted_or_scaled_turn_is_still_set_aside(self, turn):
    drawn = parse_drawn(_log("CGNODE 20.0pt 6.0pt 2.0pt rectangle/t",
                             f"CGNB 0 0 10 10 0.0 0.0 {turn} t"))
    assert drawn.nodes["t"].rotated is True
```

(With `b=1, c=-1`, a point `(x, y)` of the text, relative to the text
anchor, lands at `(-y, x)`. With `b=-1, c=1`, it lands at `(y, -x)`. The
text spans `x` in `[0, wd]` and `y` in `[-dp, ht]`.)

- [ ] **Step 2: Run them; expect FAIL** (`rotated is True`):
  `$PY -m pytest tests/test_figure_drawn.py -k "quarter or slanted" -q`

- [ ] **Step 3: Implement in `_drawn._node`.** The text box is the min
  and max of the four turned corners when the turn is a quarter one;
  otherwise it is as today. `rotated = turn != (0, 0) and not quarter`.
  Rewrite the `CGNB` docstring paragraph: the box is the bounding box of
  the four side anchors' points.

- [ ] **Step 4: Run them; expect PASS.**

- [ ] **Step 5: Write the failing compile tests** in
  `tests/test_figure_check.py`, a new class under `@needs_tikz`:
  - `test_turned_labels_that_collide_fire_node_overlap`:
    `turned-collide.tex` holds two `rotate=90, anchor=east` labels on
    ticks 1mm apart, and a `cgzone` band whose top lies above the
    labels' feet. Asserts that `node-overlap` targets include
    `"e1-n+e2-n"` and one target pairing a label with `band-card`.
  - `test_turned_labels_clear_of_each_other_fire_nothing`:
    `turned-clean.tex` is the same picture with the ticks 40mm apart and
    the band below the labels. Asserts no `node-overlap` and no
    `content-protrusion` finding.
  - `test_an_unturned_node_keeps_its_box`: the fixture
    `unturned-shapes.tex` sets a `circle` with `minimum size=10mm`, a
    `rectangle` with `minimum width=20mm, minimum height=10mm`, a `circle
    split` and a `cylinder`, all with `inner sep=0pt, outer sep=0pt`.
    Asserts that the circle's and the rectangle's boxes from
    `measure(path, boxed=True).boxes` measure 28.45pt by 28.45pt and
    56.91pt by 28.45pt, within 0.05pt. For the other two shapes, assert
    the box `figure check` reported on `main`, captured once from an
    `origin/main` worktree and written into the test as literals.

  Each fixture carries a `% cg-layout: pipeline` line, the house block
  (copy `tests/fixtures/figure/check/lifelines.tex`'s preamble) and an
  ASCII twin that names every label.

- [ ] **Step 6: Run them; expect the collide test and the clean test to FAIL**
  (nothing measured; a false `content-protrusion`). The unturned test
  passes on `main`'s code by construction.

- [ ] **Step 7: Implement `\cgsides`.** Define it in `scaffold()`'s
  preamble after the `\newdimen` line, so both probes share one
  definition. It reads each of the four anchors with `\pgfpointanchor` +
  `\pgfgetlastxy` and keeps the min and max with `\ifdim`. Replace the
  four-anchor block in `probes` with `\cgsides{name}` and the same
  `\typeout{CGBOX ...}`. In `\cgdumpnodes`, replace the four
  `\pgfpointanchor` lines with `\cgsides{##1}` and
  `\edef\cgw{\strip@pt\cgx}` (and likewise for the other three). Keep
  the comment about four sides not two corners (#1054), and add one line
  on why min and max: a quarter turn swaps which anchor is outermost.

- [ ] **Step 8: Run** `$PY -m pytest tests/test_figure_drawn.py
      tests/test_figure_check.py tests/test_figure_overlap*.py
      tests/test_figure_clearance_rules.py tests/test_tikz_scaffolds.py -q`.
  Expect PASS. If `content-protrusion` still fires on `turned-clean`,
  trace `_result.protruding`'s inputs before changing anything.

- [ ] **Step 9: Docs.** `docs/TIKZ-STYLE.md`'s rules section and
  `.claude/skills/figure-drawer/references/check.md`: a quarter-turned
  node is measured like any other; a slanted (`sloped`) one is not.

- [ ] **Step 10: Commit** `Measure a quarter-turned node's real box in figure
      check`.

### Task 2: A coordinate never makes a card

**Files:**

- Modify: `chitragupta/figure/_connectors.py` (`zones()`, line 88)
- Create: `tests/fixtures/figure/check/title-over-coordinate.tex` and `.txt`
- Test: `tests/test_figure_connectors.py`, `tests/test_figure_check.py`

**Interfaces:**

- Produces: `zones(nodes) -> set[str]` ignores any `other` whose
  `shape == "coordinate"`. The signature is unchanged.

- [ ] **Step 1: Write the failing tests.** In `tests/test_figure_connectors.py`:

```python
def test_a_title_covering_a_coordinate_is_not_a_zone():
    title = node("busy-t", (-18.7, -37.1, 55.7, -23.2), framed=False,
                 text_box=(-18.7, -37.1, 55.7, -23.2))
    band = node("band", (0, -30.2, 0, -30.2), shape="coordinate")
    assert zones({n.name: n for n in (title, band)}) == set()

def test_a_card_holding_a_title_and_a_coordinate_is_still_a_zone():
    card = node("quiet", (39.7, -42.0, 302.8, -18.3))
    title = node("quiet-t", (156.9, -36.9, 185.6, -23.4), framed=False)
    band = node("band", (100, -30.2, 100, -30.2), shape="coordinate")
    assert zones({n.name: n for n in (card, title, band)}) == {"quiet"}
```

  In `tests/test_figure_check.py`'s `TestOverlapOfEveryDrawnNode`,
  `test_a_title_wider_than_its_card_is_reported`: the three nodes of the
  first test plus `busy` (`(5.7, -42.0, 31.3, -18.3)`) and `quiet`.
  Assert that `"busy+busy-t"` and `"busy-t+quiet"` are both among
  `self._overlaps(...)`. The names are sorted within a pair, as
  `overlaps()` reports them.

  The compile fixture `title-over-coordinate.tex` is the probe's `p8`: a
  chained axis, a narrow era from 0.02 to 0.10 titled "start-up phase",
  and a `band` coordinate under the title. Add
  `test_a_title_leaving_its_card_fires_node_overlap` to Task 1's compile
  class.

- [ ] **Step 2: Run; expect FAIL** (`zones` returns `{"busy-t"}`; no overlap).
- [ ] **Step 3: Implement** the one condition in `zones()`, and add a
      docstring line saying why: a point inside a box does not make the box a
      group (#1064).
- [ ] **Step 4: Run** the two test files; expect PASS.
- [ ] **Step 5: Commit** `Stop counting a coordinate as a card's member`.

### Task 3: The timeline scaffold and its layout everywhere

**Files:**

- Create: `assets/tikz/timeline.tex`, `assets/tikz/timeline.txt`
- Create: `.claude/skills/figure-drawer/references/layouts/timeline.md`
- Modify: `docs/TIKZ-STYLE.md` (metaphor row after Sequence, a prose
  paragraph beside the sequence's, "ten scaffolds" to "eleven" at lines
  522, 730 and 787)
- Modify: `.claude/skills/figure-drawer/references/patterns.md`,
  `figures.md`, `layouts/pipeline.md`, `layouts/sequence.md`;
  `assets/tikz/README.md`; `.claude/skills/figure-drawer/SKILL.md`,
  `.agents/skills/figure-drawer/SKILL.md`,
  `.opencode/skills/figure-drawer-opencode/SKILL.md`; `docs/CLI.md`
  (line 3176's list, and "ten scaffolds" at line 1562);
  `docs/FIGURE-DRAWER.md` (the rule-relevance table gains a Timeline
  column, every cell "applies")
- Modify: `tests/test_figure_check.py` (the hard-coded scaffold lists at
  lines ~413 and ~731 gain `"timeline"`)

**Interfaces:**

- Consumes: Tasks 1 and 2. Without them the scaffold's labels and band
  titles are unmeasured.
- Produces: the layout id `timeline`, and the node names `t0`, `tend`,
  `e1`..`e5`, `e<n>-n`, `b1`..`b4`, `band` and the era cards, which
  the twin and the reference file name.

- [ ] **Step 1: Add `timeline` to the two lists in `test_figure_check.py`; run
      them; expect FAIL** (no such file).
- [ ] **Step 2: Write `timeline.tex`** to the spec's "The scaffold"
  section. Start from `sequence.tex`: copy its header shape and the
  block (lines 14-356). The geometry values come from the probe:
  - ticks at 0.08, 0.22, 0.58, 0.66 and 0.92;
  - eras "busy" from 0.02 to 0.40 and "quiet" from 0.44 to 0.98;
  - labels one or two short words each, `(e3-n) at ([yshift=-1mm]e3.south)`;
  - `band` placed `below=` the label row by enough that the longest
    turned label clears the cards' tops.

  Keep exactly one `cgkey`: the scaffold test requires one focal node.
  Put it on the event the figure is about.
- [ ] **Step 3: Write `timeline.txt`**: 7-bit ASCII, at most 72 columns,
  every label and era title word for word, ticks at proportional
  columns, the band as `[== busy ==]`.
- [ ] **Step 4: Run** `$PY -m chitragupta figure check
      assets/tikz/timeline.tex --width 345`.
  Expect no finding. `size-*` and `budget-*` are advisory and may print.
  Then `$PY -m chitragupta figure look assets/tikz/timeline.tex`, and
  Read the PNG. Labels must read bottom to top, ending at their ticks.
  Delete `content/rendered/` afterwards.
- [ ] **Step 5: Write `layouts/timeline.md`** with the sections of
  `layouts/sequence.md`, and the anti-patterns the spec lists. Add one
  for a label flush with its tick (Review Focus 2). Leave the
  reference-ranges table with a placeholder row; Step 7 replaces it.
- [ ] **Step 6: Edit the docs and lists** named under Files. Afterwards
  run `grep -rn "ten scaffolds\|ten layouts" docs .claude .agents .opencode
  assets`
  and expect nothing. Keep each SKILL.md under 8,000 bytes.
- [ ] **Step 7: Run** `$PY -m pytest tests/test_tikz_scaffolds.py
      tests/test_figure_check.py tests/test_figure_new.py
      tests/test_figure_sync.py tests/test_figure_contrast.py
      tests/test_figure_reference_ranges.py tests/test_skill_figure_router.py
      tests/test_figure_rule_ids.py -q`.
  The ranges test fails and prints the measured row: paste it into
  `timeline.md`, then re-run and expect PASS.
- [ ] **Step 8: Commit** `Add a timeline scaffold that places events by
      fraction of the axis`.

### Task 4: The next-event exemplar

**Files:**

- Create: `assets/tikz/exemplars/next-event.tex` and `.txt`
- Modify: `layouts/timeline.md` (second ranges row, and an exemplar
  paragraph like sequence's); the exemplar counts in `figures.md` and
  `assets/tikz/README.md`

**Interfaces:**

- Consumes: Task 3's styles and idiom, copied (not shared). An exemplar
  is a standalone figure.

- [ ] **Step 1: Write `next-event.tex`** at 453pt with
  `% cg-layout: timeline`:
  - a single-server queue with six events: arrivals A1 to A3 and
    departures D1 to D3, in an order the queue allows;
  - two of the events at most 3% of the axis apart;
  - eras "server busy" and "server idle" alternating, one of them short;
  - labels of at most three words, titles of at most two.

  Check the semantics: no Dk before Ak, and the server is idle exactly
  when no customer is in the system.
- [ ] **Step 2: Write `next-event.txt`** under the same rules as Task 3 Step 3.
- [ ] **Step 3: Run** `figure check` (default width 453) and `figure look`.
      Expect no finding, and labels that read bottom to top.
- [ ] **Step 4: Run** `tests/test_tikz_scaffolds.py`; paste the printed row;
      re-run; expect PASS.
- [ ] **Step 5: Commit** `Add a next-event exemplar for the timeline layout`.

### Task 5: Ripple, plan records, version

**Files:**

- Modify: `plans/fig-xii-figure-drawer-v3.md` (a 3e paragraph under
  Phase 3, beside 3b and 3d); `plans/1064-timeline-scaffold.md` (Status
  becomes "built in #<PR>"; success boxes ticked as they hold)
- Modify: `pyproject.toml` (`version = "6.152.0"`)

- [ ] **Step 1: The ripple.** Run `git worktree add $SCRATCH/main origin/main`.
  Then run `figure check --json` over every `assets/tikz/**/*.tex` and
  every `figures/*.tex` under
`/home/prasad/git/chitragupta-freja/content/drafts/{books/digital-twins-for-software-engineers,tutorials/digital-twins-for-software-engineers,book-chapters/state-estimator}`,
  once with `PYTHONPATH=$SCRATCH/main` and once with `PYTHONPATH=$W`.
  Diff the `(file, rule, target)` sets. Save the diff in the scratchpad
  for the PR body. Expected: new `node-overlap` findings only where a
  turned node or a coordinate-covering title really collides, and
  `content-protrusion` gone only where a turned node caused it. Treat
  any other change as a bug in Task 1 or 2: fix it there before going
  on. Remove the worktree afterwards.
- [ ] **Step 2: Bump the version.** Run `git fetch origin main`, then
  `git show origin/main:pyproject.toml | grep -m1 '^version'`. Set the
  next MINOR above it.
- [ ] **Step 3: Full suite with coverage:**
  `$PY -m pytest --cov --cov-report=term-missing -q` (about 15 minutes).
  Expect all pass, at 100% line and branch. Host-only failures named in
  memory (#1037-era LuaLaTeX renders) must match `main`'s.
- [ ] **Step 4: Review.** Run `ocr delegate preview --from origin/main --to
      HEAD`
  and act on the findings. Then run an agent review of the whole branch
  covering `.tex`, `.md` and `tests/`, which `ocr` skips.
- [ ] **Step 5: Commit** `Record 3e in the v3 plan and bump to 6.152.0`.

### Task 6: PR, merge, release

- [ ] **Step 1:** Push `feat-1064-timeline-scaffold`
  (`git push -u origin feat-1064-timeline-scaffold`). Open the PR via the
  REST API, using the token from `origin`'s URL; never print it.
  - Title: `Add a timeline scaffold, and measure turned labels and titles over
    coordinates`.
  - Body: the repo's PR template headings, a `## Commit message`
    section, `Closes #1064`, the ripple diff, and which reviews ran.
    End with the Claude Code line.
- [ ] **Step 2:** Wait for every CI job to be green. Fetch `main` again;
  if it moved, merge `origin/main` in, re-check the version, and push.
- [ ] **Step 3:** `GH_TOKEN=<token> scripts/merge_pr.py <N>`. It refuses
  if the version collides.
- [ ] **Step 4:** Run `git fetch origin -q --tags` and confirm `main`'s
  version is ours. Then run `git tag -a v6.152.0 -m v6.152.0 <merge sha>`
  and `git push origin v6.152.0`.
- [ ] **Step 5:** Wait for `release.yml`, including `publish-pypi`, since
  this is a `.0` tag. PATCH the release body from
  `.github/RELEASE_TEMPLATE.md`.
- [ ] **Step 6:** Confirm #1064 closed. Ask before posting a lessons
  comment on it.

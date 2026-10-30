# 🔁 XII-3c: the state-machine scaffold

Status: **designed.** Written 2026-10-30 against `main` at `4857f1a`,
from a brainstorming session on issue
[#1062](https://github.com/prasadtalasila/chitragupta/issues/1062). It
ships in the same PR as the code, as #1053, #1056 and #1057 did. The
decisions marked *user* were agreed in that session; the rest was the
session's proposal.

**Written for** whoever builds #1062: a session that changes
`assets/tikz/`, `chitragupta/figure/`, the three copies of the
`figure-drawer` skill, `tests/` and `docs/`, and is therefore governed by
`DEVELOPER-AGENTS.md` and `docs/CODE-STANDARDS.md`.

**Assumed:** `plans/fig-xii-figure-drawer-v3.md` (Phase 3, and the
`c1-orthogonal` row that already exempts `state-machine`),
`plans/1056-twin-agreement.md` (how a twin is compared),
`plans/1057-figure-check-size.md` (the `% cg-layout:` line and reference
ranges), `plans/1055-contrast-and-wording.md` (the last house-block bump,
v4 to v5, which this one follows), and FIGURE-ROADMAP II.4.

**Not covered here:** the other four Phase 3 scaffolds. 3b (#1061,
comparison) ranks above 3c in the v3 plan's build order and is still
open; the two share no file but the lists every scaffold is named in,
so whichever merges second rebases those lines. Deriving a figure from
a transition table (FIGURE-ROADMAP Part III). Redrawing the reference
book's `hidden-markov-model.tex`.

## What it is for

No current layout draws an automaton. The book's `pump-markov-chain.tex`
was drawn free-hand as "a control loop, drawn as boxes and arrows", and
neither the tree nor the hub-and-spoke scaffold can express a self-loop,
an initial state or an accepting one (FIGURE-ROADMAP II.4). A lifecycle
whose states recur is today routed to the pipeline and drawn with a
back-arrow. This item adds the layout, the house vocabulary it needs,
and the routing that sends those figures to it.

## Decisions

| Question | Decision |
| --- | --- |
| Twin form | **A transition table** (*user*), not an ASCII tracing: a `from \| on \| to` table, with one line above it naming the initial and accepting states. FIGURE-ROADMAP II.4: more precise than the picture and what a screen reader wants. It is the first twin that is not a drawing, so `figures.md` gains the general rule: a twin is the clearest 7-bit form of the same information, not necessarily a tracing. Twin agreement (#1056) matches words, so `t1-labels` and `t2-tags` hold for a table unchanged |
| Where the state styles live | **In the house block, which goes from v5 to v6** (*user*), not in the scaffold's picture options. Any figure can then draw a state, a book's states agree, and `figure sync` carries a later change. The cost was accepted: every carrier is re-stamped, and a v5 figure in a draft reports stale until `figure sync` |
| State shape | A **circle**, the automaton's convention. All the state styles are pure TikZ: self-loops use core `loop above/below/left/right`, so the `automata` library is **not** loaded and the block's six-library line is unchanged |
| The v6 styles | `cgstate`: circle, `cgFlowLine` rule, `cgFlow!7` fill, bold `\normalsize`, `cgsoft`, one fixed `minimum size`, so the states of one machine are the same size (start near 14mm; the scaffold's longest name sets it). `cgaccept`: `cgstate` with a double ring. `cgstart`: the initial arrow, a `cgedge` drawn from a point beside the state. `cgkeystate`: the accented state, on the `cgkey` rule and tint |
| An accented state | **`cgkeystate` is in v6 and `focal-count` counts it** (*user*). `cgkey` cannot be combined with `cgstate`: `cgkey` is built on `cgbox`, so `[cgstate, cgkey]` takes the card's 24mm text width and balloons the circle, and `[cgkey, cgstate]` resets the tint. A hand-written accent would be invisible to `focal-count`. The exemplar needs one: the book's figure accents Faulted |
| `focal-count` | `_focal.py`'s whole-word match is extended from `cgkey` to `cgkey` or `cgkeystate`, so one of each in a figure is two accents. Its report says "accented nodes" rather than "cgkey nodes", and its TIKZ-STYLE.md row names both |
| Scaffold | `assets/tikz/state-machine.tex`, `% cg-layout: state-machine`: a generic four-state lifecycle (draft, review, revise, merged) using each part of the grammar once: an initial arrow, a pair of transitions bent apart (`bend left` both ways, so the two curves do not meet in a lens), one self-loop with its tag, one transition back, one accepting state. Its header comment says what the layout argues and names the slips (which way a pair bends, where a loop's tag goes) |
| Exemplar | `assets/tikz/exemplars/pump-markov-chain.tex`, `% cg-layout: state-machine`: the reference book's pump chain (appendix A1, not Ch. 6 as the v3 plan says) redrawn in the house style. Off, On and Faulted; probabilities as tags; three self-loops; Faulted as `cgkeystate`. A Markov chain has no initial or accepting state, which is what shows the markers are optional. Its twin keeps the "the numbers leaving each state sum to one" sentence below the table |
| `c1-orthogonal`, `c4-attach` | Already exempt for `state-machine` (`chitragupta/figure/_rules.py`). Nothing to change |
| Clean under `figure check` | Both new carriers report no objective finding. `c2-tag-clearance` on a loop's apex and `c7-dangling-tip` on a circle are measured on the compiled figure and fixed in the drawing. A `% cg-allow:` only with its reason, and shown to the person before it goes in |
| Routing | **Split by return** (*user*). "a lifecycle with a start and an end" stays with the pipeline, its tell now "nothing goes back". New rows to the state machine: "a lifecycle where a state recurs, stays put or is sent back" and "an automaton, a protocol's states, a Markov chain", tell "it is in one state at a time, and events move it". "Two that look alike" gains *Loop or state machine?* (a loop's nodes are stages that all run each cycle; a state machine's are conditions, one at a time) and *Pipeline or state machine?* (anything goes back or stays put) |
| Version | MINOR: a new scaffold, a new block version and a widened rule. Read from `main` at PR time; parallel sessions land v3 items concurrently |
| Issue | The PR body says `Closes #1062`. A lessons comment is posted on the closed issue after merge, once the person says so |

## Components

| File | Change |
| --- | --- |
| `assets/tikz/cg-figstyle.tex` | Marker v5 to v6; a `--- States ---` group with `cgstate`, `cgaccept`, `cgstart`, `cgkeystate`, commented in the block's own voice |
| `assets/tikz/cg-figstyle.versions.toml` | A `v6` digest line. Existing lines untouched |
| 7 scaffolds, 3 exemplars | Re-stamped to v6 by `figure sync`; nothing else in them moves |
| `assets/tikz/state-machine.tex`, `.txt` | New scaffold and its table twin |
| `assets/tikz/exemplars/pump-markov-chain.tex`, `.txt` | New exemplar and its table twin |
| `assets/tikz/README.md` | Scaffold row |
| `chitragupta/figure/_focal.py`, `_check.py` | `cgkeystate` counted; report wording |
| `.claude/skills/figure-drawer/references/layouts/state-machine.md` | New: what it argues, when it is the layout and when not, anti-patterns (a state named with a verb, an unlabelled transition, both directions of a pair on one line, more than about six states, two accented states), a note that the twin is a table, and the reference-range rows for the scaffold and the exemplar |
| `.claude/skills/figure-drawer/references/patterns.md` | The routing above |
| `.claude/skills/figure-drawer/references/figures.md` | Scaffold-table row; the two confusable pairs in §1; the twin sentence |
| `.claude/`, `.agents/`, `.opencode/` `SKILL.md` | Only where a copy lists layouts; each stays under the 8,000-byte cap `tests/test_skill_figure_router.py` holds |
| `docs/TIKZ-STYLE.md` | Metaphor-table row "State machine \| circles (`cgstate`) with `bend` and `loop`"; a "States" row in the vocabulary table; `focal-count`'s row names `cgkeystate` |
| `docs/CLI.md` | `figure new --layout`'s list of ids |
| `plans/fig-xii-figure-drawer-v3.md` | 3c marked built, the exemplar's chapter corrected, the block at v6 |
| `pyproject.toml` | MINOR bump |

## Tests

- `tests/test_tikz_scaffolds.py` takes the new scaffold and exemplar
  without a change of its own: metaphor table to directory, a reference
  file per layout, routing to every layout, each carrier's twin, its
  geometry, its `% cg-layout:` line, and the range rows re-measured.
- `tests/test_figure_block.py`: v6 is the current registered version.
- Focal count: `cgkeystate` counts; one `cgkey` and one `cgkeystate` is
  two; `cgkeystateish` and `my-cgkeystate` are not counted.
- `tests/test_figure_contrast.py` covers the new styles' rule and tint.
- `tests/test_figure_new.py` and `tests/test_figure_check.py`: their
  layout lists gain `state-machine`.
- Line and branch coverage stays at 100%.

## Verification before the PR

- The full suite on `.venv-full` with an absolute `PYTHONPATH` (the
  repo scans run in the suite, so not just the touched files).
- `figure check` on all twelve carriers: no objective finding.
- `figure look` on the scaffold and the exemplar, the PNGs shown to the
  person through a `pr-assets/<N>` orphan branch and a PR comment.

## Implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `figure new --layout state-machine` copies a scaffold that
draws an automaton in the house style, routed to by `patterns.md`, with
a v6 block every carrier shares and a `focal-count` that sees an
accented state.

**Architecture:** No new module. One regex in `_focal.py`, four styles
in the house block, and two new carriers that the existing scaffold
tests pick up by directory. Everything else is prose.

**Tech Stack:** TikZ (core only), Python 3.12+, pytest, LuaLaTeX.

**Spec:** the Decisions table above.

## Global Constraints

- No rule becomes a gate; `figure check` still exits 0 on findings.
- No citekey anywhere: not in a figure, a twin, a fixture or a doc.
- Line and branch coverage stays at 100%.
- Twins are 7-bit ASCII, at most 72 columns (WRITING-STANDARDS §10).
- All figure text `\normalsize`; no `\resizebox`; libraries line stays
  `arrows.meta,positioning,fit,backgrounds,calc,shadows.blur`.
- PR body says `Closes #1062`. MINOR bump read from `main` at PR time.
- Tests: `/home/prasad/git/chitragupta-freja/.venv-full/bin/python -m pytest`
  with an absolute `PYTHONPATH=<worktree>` and `config.toml` copied
  from the example.

## Review Focus

1. `[cgkeystate]` plus `[cgkey]` in one figure: two accents, one
   finding. Test in Task 1.
2. A state style used in a figure that also carries an older v5 block:
   `figure sync` refreshes it to v6 and nothing else moves. Covered by
   the existing stale-block tests once v6 is registered; checked in
   Task 2 by running `figure sync --check` on all carriers.
3. A state name longer than the fixed size: the circle grows and
   `figure check` still reports no overlap. Checked in Task 3 by the
   scaffold's longest name, "review", fitting the chosen size.
4. A loop's tag at the apex too close to the curve (`c2-tag-clearance`).
   Checked in Tasks 3 and 4 by `figure check` on the compiled carrier.
5. A table twin that misses a transition's tag: `t2-tags` fires. The
   existing twin tests cover it; Tasks 3 and 4 run them on the new pair.

---

### Task 1: `focal-count` counts an accented state

**Files:** Modify `chitragupta/figure/_focal.py`, `chitragupta/figure/_check.py`;
test `tests/test_figure_check.py` (`TestFocalCount`).

- [ ] **Step 1: Failing tests.** In `TestFocalCount`: the existing
  measurement becomes `f"2 accented nodes: {named}"`; new parametrized
  cases `\node[cgkeystate] (a) {A}; \node[cgkeystate] (b) {B};` and
  `\node[cgkey] (a) {A}; \node[cgkeystate] (b) {B};` each fire with
  `a, b`; `\node[cgkeystateish] (a) {A}; \node[cgkey] (b) {B};` and
  `my-cgkeystate` do not fire.
- [ ] **Step 2: Run** `pytest tests/test_figure_check.py -k Focal`; expect
  the new cases to fail.
- [ ] **Step 3: Implement.** `_CGKEY_RE` becomes
  `(?<![\w-])cgkey(?:state)?(?![\w-])`; docstrings say "an accent
  (`cgkey` or `cgkeystate`)"; `_check.py`'s message is
  `f"{len(keyed)} accented nodes: ..."`.
- [ ] **Step 4: Run** again; pass, `_focal.py` at 100%.
- [ ] **Step 5: Commit** `Count an accented state in focal-count (#1062)`.

### Task 2: House block v6

**Files:** `assets/tikz/cg-figstyle.tex`, `cg-figstyle.versions.toml`,
the 10 carriers, `docs/TIKZ-STYLE.md` (vocabulary table and
`focal-count` row), `docs/CLI.md` only if it quotes the block version.

- [ ] **Step 1:** Add the `--- States ---` group after the zone card:
  `cgstate` (circle, `draw=cgFlowLine`, `fill=cgFlow!7`, `align=center`,
  `inner sep=1.5pt`, `minimum size=` the measured value,
  `font=\normalsize\bfseries`, `cgsoft`), `cgaccept` (`cgstate`,
  `double=cgFlow!7`, `double distance=1.2pt`), `cgkeystate` (`cgstate`,
  `draw=cgAccentLine`, `fill=cgAccent!11`, `line width=1.15pt`) and
  `cgstart` (`cgedge`, `shorten <=0pt`). Comment why circles, why no
  `automata`, and why `cgkeystate` is not `cgkey`.
- [ ] **Step 2:** Marker to v6; append `v6 = "<digest>"` computed by
  `chitragupta.figure.digest` over the region.
- [ ] **Step 3:** `python -m chitragupta.figure sync assets/tikz/*.tex
  assets/tikz/exemplars/*.tex`; then `sync --check` reports all current.
- [ ] **Step 4:** TIKZ-STYLE.md: a "States" row in the vocabulary table;
  the `focal-count` row says "more than one `cgkey` or `cgkeystate` node".
- [ ] **Step 5: Run** `tests/test_figure_block.py tests/test_figure_contrast.py
  tests/test_tikz_scaffolds.py`; pass.
- [ ] **Step 6: Commit** `Add state styles to the house figure block, v6 (#1062)`.

### Task 3: The scaffold, its twin, its reference and its routing

**Files:** create `assets/tikz/state-machine.tex`, `.txt`,
`.claude/skills/figure-drawer/references/layouts/state-machine.md`;
modify `patterns.md`, `figures.md`, `assets/tikz/README.md`,
`docs/TIKZ-STYLE.md` (metaphor table), `docs/CLI.md` (`--layout` ids),
the SKILL.md copies where they list layouts, and the two layout lists in
`tests/test_figure_check.py`.

- [ ] **Step 1: Failing test.** Add the TIKZ-STYLE.md metaphor row;
  `test_every_metaphor_has_a_scaffold` and
  `test_every_metaphor_has_a_reference_file` fail.
- [ ] **Step 2:** Draw the scaffold: states `draft` (initial), `review`,
  `revise`, `merged` (`cgaccept`); `submit` draft to review, `approve`
  review to merged, `changes` review to revise and `resubmit` back as a
  pair bent apart, `comment` as review's self-loop above. Header comment
  in control-loop's voice. Twin: `initial: draft    accepting: merged`
  over a `from | on | to` table.
- [ ] **Step 3:** The reference file, sections as `hub-and-spoke-network.md`;
  its range row pasted from the test's failure message.
- [ ] **Step 4:** Routing and doc rows as the Decisions table says.
- [ ] **Step 5:** `figure check assets/tikz/state-machine.tex`: no
  objective finding; fix in the drawing.
- [ ] **Step 6: Run** `tests/test_tikz_scaffolds.py tests/test_figure_new.py
  tests/test_figure_check.py tests/test_skill_figure_router.py`; pass.
- [ ] **Step 7: Commit** `Add the state-machine scaffold and route lifecycles that go back to it (#1062)`.

### Task 4: The pump exemplar

**Files:** create `assets/tikz/exemplars/pump-markov-chain.tex`, `.txt`;
modify `layouts/state-machine.md` (second range row), `figures.md` if it
lists exemplars.

- [ ] **Step 1:** Redraw from the book's figure: Off, On, Faulted
  (`cgkeystate`); Off to On 0.3, On to Off 0.4, On to Faulted 0.02,
  Faulted to Off 0.1 (`cgback`, tag "0.1 repaired"); self-loops 0.7, 0.58,
  0.9. Twin: the table, then the sum-to-one sentence.
- [ ] **Step 2:** `figure check` clean; range row from the test.
- [ ] **Step 3: Run** `tests/test_tikz_scaffolds.py`; pass.
- [ ] **Step 4: Commit** `Add the pump Markov chain as the state-machine exemplar (#1062)`.

### Task 5: Release prep

- [ ] **Step 1:** `figure look` on both new carriers; inspect the PNGs.
- [ ] **Step 2:** v3 plan: 3c built, exemplar chapter corrected, block v6.
  This plan's Status to **built**, ticks set.
- [ ] **Step 3:** Fetch `main`; MINOR bump in `pyproject.toml` from its version.
- [ ] **Step 4:** Full suite; coverage 100%; `ocr delegate preview`; a
  fresh agent review of the `.tex`/`.md` the OCR skips.
- [ ] **Step 5:** Push, open the PR (`Closes #1062`), wait for CI, merge
  with `scripts/merge_pr.py`, tag, release, patch the release body.

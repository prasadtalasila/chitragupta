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

To be written from this design once it is reviewed.

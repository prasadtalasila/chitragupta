# 🪜 XII-3d: the sequence scaffold

Status: **built** in #1100. Written 2026-10-30 against `main` at `4857f1a`, from
a brainstorming session on issue
[#1063](https://github.com/prasadtalasila/chitragupta/issues/1063), and
built in the same PR as this plan, as #1056 was. Decisions marked *user*
were agreed in that session. The rest are the session's proposal.

**Written for** whoever builds #1063: a session that changes
`chitragupta/figure/`, `assets/tikz/`, the three copies of the
`figure-drawer` skill, `tests/` and `docs/`. That session is governed by
`DEVELOPER-AGENTS.md` and `docs/CODE-STANDARDS.md`.

**Assumed:** `plans/fig-xii-figure-drawer-v3.md` (Phase 3),
`docs/FIGURE-ROADMAP.md` II.2, `plans/1054-connector-rules.md` (c1 to
c7 and the `Rule.exempt` mechanism), and `plans/1057-figure-check-size.md`
(`% cg-layout:` and reference ranges).

**Not covered here:** activation bars, self-messages and UML packages
(see "Left out"). The other phase-3 scaffolds are out of scope too:
quadrant (#1060) and timeline (#1064), and the comparison (#1061) and
state machine (#1062), which landed as #1095 and #1096 while this was
being built.

## What it is for

A protocol drawn today has to start from a pipeline or a control loop
and be bent into lifelines by hand. That free-hand drawing is where the
defects this epic removes come from. A known-good scaffold carries a
layout that already passes `figure check`, has a twin that agrees with
it, and comes with reference ranges to read the size reports against.

## What the probe found

Before the design, throwaway figures were run through `figure check`
(scripts in `/tmp/spike-1063`, not kept):

1. **Lifelines as plain `\draw` lines, with messages between
   coordinates.** The figure passes only because nothing is measured. A
   message that ends on a point is not a connector (`_connectors.solid`
   drops degenerate boxes), so c1 to c7 never see it. Separately,
   `cgweak` carries an arrowhead, so every lifeline drew a
   `c7-dangling-tip` at its foot.
2. **Lifelines as thin, tall named nodes, with messages node to node.**
   Messages become connectors, and c1, c2, c3 and c7 measure them. Two
   rules then fire on a correct diagram. `c4-attach` reported every
   lifeline side ("3 ends up to 10.0mm off even spacing"), because many
   messages meet one lifeline at heights set by time, not by spacing.
   `c5-transit` reported a message that skips the middle lifeline
   ("cli-l->db-l crosses srv-l"), which is ordinary in a sequence
   diagram.
3. A `\foreach` over lifelines shows up as "declared but not measured:
   `\p-l`", because the source parser reads the loop variable.

## Decisions

| # | Decision | Why |
| --- | --- | --- |
| D1 | Lifelines are thin, tall named nodes, and messages run node to node (*user*) | The only drawing under which c1, c2, c3 and c7 check every message |
| D2 | `sequence` joins `c4-attach`'s and `c5-transit`'s `exempt` sets. `c1-orthogonal` keeps its current set (*user*) | Uses the mechanism `state-machine` and `hub-and-spoke-network` already use. A lifeline-aware geometric rule was the alternative, but it needs a threshold benched over the 49 drafts |
| D3 | The exemplar draws a `figure check` run (*user*) | Lifelines: figure-drawer skill, `figure check` (`cgkey`), LuaLaTeX probe, ASCII twin |
| D4 | The lifeline styles live in the picture's own options, not in the house block | No house-block version bump, no `figure sync` churn. The house block's own rule is "a style this figure alone needs goes in the picture's options" |
| D5 | No `\foreach` in the scaffold or the exemplar | Probe finding 3; a scaffold is copied line by line anyway |
| D6 | The c1 to c7, k1 and k2 rules get a section in `docs/FIGURE-DRAWER.md`: a short explanation of each rule, its relevance to each layout, and a rendered bad/good gallery whose panels a test re-checks. It ships in this PR (*user*) | A person reading the figure guide sees what each rule catches. The test keeps the pictures true as thresholds move |
| D7 | MINOR version bump | A new layout `figure new` offers, and a rule change |

## The scaffold

`assets/tikz/sequence.tex`:

- **Header.** `% cg-layout: sequence`. The metaphor paragraph says: the
  order of exchanges between parties is the whole claim, and if one party
  only hands work to the next, it is a pipeline. The idiom paragraph says
  that lifelines are thin nodes and every message is a horizontal
  straight line between two of them, at a fixed step down the page.
- **House block** v5, copied verbatim.
- **Picture options:**
  - `cglife`: `inner sep=0pt, minimum width=2mm, minimum height=<depth>,
    anchor=north, outer sep=0pt`, drawn with no border. One per party,
    placed `at (<party>.south)`.
  - `cglifeline`: `cgweak` with `arrows=-`, drawn
    `(<p>-l.north) -- (<p>-l.south)`.
- **Content.** Three parties: Client, Cache (`cgkey`) and Server. Five
  messages, top to bottom: `get` (Client to Cache), `miss` (Cache to
  Client, `cgweak`), `fetch` (Client to Server, crossing Cache's
  lifeline), `data` (Server to Client, `cgweak`) and `put` (Client to
  Cache).
  - A call is `cgedge`; a reply is `cgweak`, dashed and light, as the
    control loop's return is.
  - Each message is written as
    `(a-l.east |- 0,-<y>) -- node[cgtag, above] {<tag>} (b-l.west |- 0,-<y>)`,
    with `east`/`west` swapped for a leftward message.
- **Width.** Fits the article class's 345pt, as every scaffold must;
  the four-party exemplar takes the render's 453pt. The depth is set so the last
  message sits one step above the lifelines' feet.

`assets/tikz/sequence.txt` is an RFC-style twin: party names across the
top, `|` lifelines, and arrows such as `|----get---->|` and
`|<---miss-----|`. It is 7-bit ASCII and at most 72 columns, and every
name and tag appears in it word for word (t1, t2).

`assets/tikz/exemplars/figure-check.tex` and `.txt` draw D3 at 453pt in
the same idiom, with `% cg-layout: sequence` and about six messages:
`check fig.tex`, `compile once`, `boxes and lines`, `read labels`,
`words`, `findings`. The wording is checked against `_check.py` when it
is drawn.

### Left out

- **Self-messages.** A loop from a lifeline back to itself joins one
  node to itself, so it is not a connector and nothing measures it. The
  reference file's anti-patterns say a note on the lifeline usually does
  the job.
- **Activation bars.** A bar is a node that several messages end on, so
  it brings back the case D2 exempts, on a node no exemption names. Left
  out until a figure in the reference book needs one.

## The rule change

- `chitragupta/figure/_rules.py`:
  - `c1-orthogonal` keeps `_NOT_ORTHOGONAL`.
  - `c4-attach` takes `_NOT_ORTHOGONAL | {"sequence"}`.
  - `c5-transit` takes `{"sequence"}`.
  - A comment says why: many messages meet one lifeline at heights time
    sets, and a message that skips a lifeline is the diagram's grammar.
- `chitragupta/figure/_clearance_rules.py`: `transit()` gains a `layout`
  argument and the same guard `orthogonal()` and `attach_points()` have.
- `chitragupta/figure/_connector_check.py` passes the layout through.

## The rule gallery (D6)

Two figures under `docs/images/figure-drawer/`. Each is a TikZ source,
carrying the house block, and its render produced by
`chitragupta figure look`:

- `connector-rules.tex` / `.png`: one row per rule from c1 to c7, with
  a "bad" panel and a "good" panel side by side. Each panel is two or
  three nodes.
- `contrast-rules.tex` / `.png`: k1 (a border and a connector under
  3:1) and k2 (text under 4.5:1). Each comes as a bad/good pair, the
  good one using the hue's `Line` and `Text` shades.

Node names carry their panel (`c3bad-a`, `c3good-a`, ...), so a
finding's target says which panel it came from.

The **new section in `docs/FIGURE-DRAWER.md`** ("What `figure check`
looks for in lines and colours") embeds both images. Each rule gets the
following (*user*):

- **The rule, briefly.** One or two plain sentences on what it measures,
  for example: "c4: an arrow meets a box at the middle of a side, or,
  when several meet one side, at even spacing along it."
- **Why it matters in print.** The defect a reader sees in the PDF.
- **Its relevance to different figures.** Which layouts it matters
  most for, and which it does not apply to. For example, c4 governs
  the stage-to-stage arrows of a pipeline, layered stack or zoned spine;
  a hub's diagonal spokes, an automaton's curves and a sequence's
  lifelines are exempt, and the section says why for each. c5 bites
  hardest in a zoned spine or a map, where a line has to find a way
  round cards, and it is lifted for a sequence, where a message
  skipping a lifeline is the grammar. k1 and k2 apply to every figure,
  but matter most where a layout leans on tinted cards: zones, the
  focal `cgkey` node, `cgback` return edges.
- **The fix.** The same sentence `references/check.md` gives, so the
  two cannot drift. `tests/test_figure_rule_ids.py`, which already
  holds the rule ids to one set in three places, is extended to cover
  this section's c and k ids.

A short table before the per-rule text sums up the layout relevance:
rules down the side, the ten layouts across, and each cell marked
"applies", "exempt" or "rarely arises". The thresholds and the
measurement wording stay in `docs/TIKZ-STYLE.md`'s table, the
authoritative list, which the section links to instead of copying, so a
threshold is still stated in one place. The section ends with how to
re-render the images.

`tests/test_figure_rule_gallery.py` runs `figure check` on both sources
where LuaLaTeX is present, and skips like the other compile tests where
it is not. It asserts:

- every bad panel fires its own rule, with a target inside that panel;
- no `c*` or `k*` rule fires on a good panel.

Other findings, such as `twin-missing` on a doc image, are ignored. The
gallery is not a draft figure.

## Tests

- `tests/test_figure_rule_exemptions.py`: one expected set per rule
  instead of the shared `NOT_ORTHOGONAL`. The rules that exempt a layout
  are now `{c1-orthogonal, c4-attach, c5-transit}`.
- **Must-not-fire fixture**, `tests/fixtures/figure/check/lifelines.tex`.
  It has three message ends on one lifeline side, one message crossing a
  lifeline, and tipless lifelines. Declared `sequence`, it reports no
  c4, c5 or c7. Checked with `--layout pipeline`, it reports both c4 and
  c5, which proves the exemption is what holds it clean.
- `tests/test_figure_check.py` lines 407 and 722 add `sequence` to the
  hard-coded scaffold lists.
- Picked up by their globs with no edit: `test_tikz_scaffolds.py` (the
  table and directory cross-check, the reference ranges re-measured, the
  source, geometry and twin properties), `test_figure_new.py`,
  `test_figure_sync.py`, `test_figure_contrast.py` and
  `test_figure_reference_ranges.py`.
- Line and branch coverage stay at 100%. The full suite is run, because
  the repo-wide scans run inside it.

## Docs and lists kept in step

- `docs/TIKZ-STYLE.md`:
  - a metaphor-table row, `| Sequence | thin lifeline nodes, with level
    messages between them |` (a `\|` in the cell breaks the table's
    parser in `test_tikz_scaffolds.py`), and a prose paragraph beside
    the comparison's;
  - the exemption prose near line 869;
  - the `c4-attach` and `c5-transit` rows name the exemption.
- `.claude/skills/figure-drawer/references/layouts/sequence.md`:
  - What it argues;
  - When it is the layout (Not when: pipeline, state machine);
  - Anti-patterns: a diagonal message to show delay, more than four
    parties (three fit 345pt, four 453pt), a self-loop where a note
    would do, bare-line lifelines;
  - Reference ranges, measured with two rows, the scaffold and the
    exemplar.
- `references/check.md` (line 80): the exemption sentence.
- `references/patterns.md`: the route row "an exchange between parties,
  in order → Sequence".
- `references/figures.md` and `assets/tikz/README.md`: the layout
  tables, and the exemplar count, which is five once #1095's
  comparison exemplar is counted.
- `references/layouts/pipeline.md`: Not when links to sequence.
- The three `figure-drawer` SKILL.md copies: the layout list, kept under
  the 8,000-byte cap `tests/test_skill_figure_router.py` holds.
- `docs/CLI.md`: `sequence` in `--layout`'s values.

## Shipping

One PR off `main` holds this plan and the code. Its body says
`Closes #1063`. Before opening it, and again before merging, fetch
`main` and re-check the version and the files that overlap, because
parallel sessions land v3 items there. If the version collides, merge
`origin/main` in and bump again; never amend or force-push.

## Success criteria

- [x] Row in TIKZ-STYLE.md's metaphor table, cross-checked by
      `tests/test_tikz_scaffolds.py`
- [x] Scaffold and exemplar clean under `figure check`, with no
      `cg-allow`
- [x] Must-not-fire fixture holds; the same fixture under `pipeline`
      fires
- [x] Rule gallery rendered, embedded and re-checked by its test
- [x] Line and branch coverage stay at 100%
- [x] No citekey generated, guessed or rewritten, and no check promoted
      into a gate

# 🔎 Figure checks: what `figure check` reports, and how to fix it

Status: **reference.**

**Written for** anyone holding a `figure check` report and wondering
what a line in it means, and anyone who wants to know what the check
holds a figure to before drawing one. **Assumed:** you have a figure
file, usually `content/drafts/<topic>/figures/<name>.tex`, drawn by the
`figure-drawer` skill or by hand ([FIGURE-DRAWER.md](../FIGURE-DRAWER.md)).
**Not covered here:** what makes a figure good beyond what can be
measured. That is the style guide, [TIKZ-STYLE.md](../TIKZ-STYLE.md).

## 🧭 Table of contents

- [Running it](#-running-it)
- [Reading a report](#-reading-a-report)
- [Every rule, and where it is explained](#-every-rule-and-where-it-is-explained)
- [What needs a compiled figure](#-what-needs-a-compiled-figure)
- [The layout line](#-the-layout-line)
- [Recording a deliberate exception: `cg-allow`](#-recording-a-deliberate-exception-cg-allow)
- [`figure check` and `review figure`](#-figure-check-and-review-figure)
- [The example figures](#-the-example-figures)

## 🏃 Running it

```bash
chitragupta figure check content/drafts/rag/figures/flow.tex
```

It compiles the figure once, in the render's fonts at 12pt, and reads
back where TikZ put everything. Flags:

- `--width PT` sets the target width. The default is 453pt, the text
  width of the render's A4 page at 1in margins. Use a smaller number for
  a column or a thesis text block.
- `--layout NAME` reads the advisory reports against another layout
  than the one the figure's `% cg-layout:` line names.
- `--json` prints the same report as data.

It exits 0 whatever it finds. Exit 2 means it checked nothing: a usage
error, or a host with no `lualatex` or `tikz.sty`. Read exit 2 as "not
checked", never as "clean". [CLI.md](../CLI.md#-chitragupta-figure-check)
has the full flag reference.

`figure check` is an aid, not a gate. Nothing downstream blocks on what
it finds. The only gate in this project is
`python -m chitragupta.draft gate`, and it checks citekeys
([SOUL.md](../../SOUL.md)).

## 📖 Reading a report

```text
figures/flow.tex
  size-width            figure     475.2pt wide, target 453.0pt
  node-overlap          legend+pot boxes intersect
advisory (read; never resolved, allowed or capped)
  size-height           figure     0.24 of the text height (168pt); pipeline reference 0.10 to 0.37
  size-squash           load+parse 1.2mm apart edge to edge, under 3mm
  budget-nodes          figure     9 nodes; pipeline reference 5 to 11
diagnostics (not findings)
  edges (confirm against the prose): load -> parse, parse -> index
  24% of the figure's box is empty (advisory, human-read only -- nothing consumes this)
figure check: 2 findings, 0 allowed, 0 stale, 0 unchecked, 0 malformed
```

Each finding is one line: `<rule-id> <target> <measurement>`.

- **The rule id** names the rule. The id is what a `% cg-allow:` line
  quotes, and what the rule's section on these pages is headed by.
- **The target** is what broke the rule. A figure-scope rule names
  `figure`. An element-scope rule names one node (`decide`), a pair
  (`legend+pot`), an edge (`decide->pot`), a side (`decide.south`) or a
  point (`(3.0,2.0)`, in mm). A node the source does not name is shown
  by its centre, `(x,y)` in mm, and a node TikZ names itself appears as
  `tikz@f@<n>` (a pin, an `alias`, an unnamed node followed by `edge` or
  `child`).
- **The measurement** says by how much.

The sections of the report:

- **Findings** come first. Every one is **objective**: either fix it,
  or record why it is deliberate with a `% cg-allow:` line. Never leave
  one unanswered, and never shrink or scale the figure to make a number
  move.
- **advisory** reports are read, not resolved. They never count as
  findings and cannot be allowed. The size and budget reports sit
  beside the reference range of the figure's layout.
- **not measured** lists every rule that could not run, with the
  reason. A rule that could not run is never reported as a pass.
- **diagnostics** are printed for a person and are never findings. Read
  the edge list against the prose the figure illustrates: no rule checks
  that the arrows join the boxes the text says they join.
- **The last line** counts findings, honoured allows, stale allows,
  allows for rules that did not run, and malformed allows.

`No findings. This is not a verdict on the figure.` means every rule
that ran passed. It does not mean the figure is good: look at it
(`chitragupta figure look`, [CLI.md](../CLI.md#-chitragupta-figure-look)).

## 📋 Every rule, and where it is explained

The 36 rules, in report order. **Scope** is what a `cg-allow` line has
to name. **Class** is what to do with a finding: resolve or allow an
objective one, read an advisory one. **What it catches** is the rule in
one sentence. Each page has the exact threshold, a faulty figure, the
line `figure check` prints for it, and the fixed figure.

| Id | Scope | Class | What it catches | Page |
| --- | --- | --- | --- | --- |
| `does-not-compile` | figure | objective | The figure's TikZ fails to compile, so nothing else can be measured. | [build](build.md#does-not-compile) |
| `nothing-measurable` | figure | objective | The figure names no node, so the geometry rules had nothing to measure. | [build](build.md#nothing-measurable) |
| `size-width` | figure | objective | The picture is wider than the text width it will print at (453pt by default). | [size](size.md#size-width) |
| `size-stray` | figure | objective | A line outside the picture that does not end in `%` adds a stray space beside the figure. | [size](size.md#size-stray) |
| `focal-count` | figure | objective | More than one node is accented, so none of them stands out. | [nodes](nodes.md#focal-count) |
| `content-protrusion` | figure | objective | An empty horizontal band taller than a third of the figure strands part of it. | [size](size.md#content-protrusion) |
| `loads-library-by-hand` | figure | objective | A TikZ library is loaded through an internal macro instead of `\usetikzlibrary`. | [build](build.md#loads-library-by-hand) |
| `node-overlap` | element | objective | Two nodes' boxes intersect. | [nodes](nodes.md#node-overlap) |
| `node-text-overload` | element | objective | A node's label runs past 15 words. | [nodes](nodes.md#node-text-overload) |
| `stranded-arrowhead` | element | objective | A line drawn in pieces leaves an arrowhead in the middle of the line. | [nodes](nodes.md#stranded-arrowhead) |
| `c1-orthogonal` | element | objective | A line between offset nodes cuts across on a slant or curve instead of turning a corner. | [connectors](connectors.md#c1-orthogonal) |
| `c2-tag-clearance` | element | objective | A line's tag sits on the line or more than 3mm away from it. | [connectors](connectors.md#c2-tag-clearance) |
| `c3-coincident` | element | objective | Two lines run on top of each other for more than 2mm. | [connectors](connectors.md#c3-coincident) |
| `c4-attach` | element | objective | A line meets a side away from its midpoint, or several lines bunch on one side. | [connectors](connectors.md#c4-attach) |
| `c5-transit` | element | objective | A line passes through a node that is neither of its ends. | [connectors](connectors.md#c5-transit) |
| `c6-tag-covered` | element | objective | A line's tag lies over a node. | [connectors](connectors.md#c6-tag-covered) |
| `c7-dangling-tip` | element | objective | An arrow ends in empty space instead of on a node or another line. | [connectors](connectors.md#c7-dangling-tip) |
| `k1-stroke` | element | objective | A border or line is too pale against what is behind it (under 3:1). | [colour and type](colour-and-type.md#k1-stroke) |
| `k2-text` | element | objective | Text is too pale against its fill (under 4.5:1, or 3:1 for large text). | [colour and type](colour-and-type.md#k2-text) |
| `w4-pictograph` | element | objective | A label contains an emoji or pictograph that prints from a fallback font. | [wording](wording.md#w4-pictograph) |
| `type-below-floor` | element | objective | Text is set smaller than the 12pt body size. | [colour and type](colour-and-type.md#type-below-floor) |
| `colour-off-palette` | element | objective | A colour is used that the house block does not define. | [colour and type](colour-and-type.md#colour-off-palette) |
| `tint-outside-band` | element | objective | A labelled node is filled with a tint outside the 6 to 12 band, or with a solid hue. | [colour and type](colour-and-type.md#tint-outside-band) |
| `unnamed-pic` | element | objective | A house shape is placed at a coordinate instead of in a named `cgwell`, so nothing measures it. | [nodes](nodes.md#unnamed-pic) |
| `twin-missing` | figure | objective | The figure has no ASCII twin, so the `md`, `html` and `docx` renders show nothing. | [twin](twin.md#twin-missing) |
| `t1-labels` | element | objective | A node name, zone title or legend entry in the TikZ is missing from the twin. | [twin](twin.md#t1-labels) |
| `t2-tags` | element | objective | A line's tag in the TikZ is missing from the twin. | [twin](twin.md#t2-tags) |
| `t3-panels` | figure | objective | The panel letters in the TikZ and the twin differ. | [twin](twin.md#t3-panels) |
| `size-height` | figure | advisory | The figure's height, as a share of the page, beside its layout's usual range. | [size](size.md#size-height) |
| `size-slack` | figure | advisory | How much of the figure no node fills, beside its layout's usual range. | [size](size.md#size-slack) |
| `size-squash` | element | advisory | Two joined nodes sit under 3mm apart, so the arrow between them is too short to read. | [size](size.md#size-squash) |
| `budget-nodes` | figure | advisory | The number of named nodes, beside its layout's usual range; never a cap. | [size](size.md#budget-nodes) |
| `budget-edges` | figure | advisory | The number of edges, beside its layout's usual range; never a cap. | [size](size.md#budget-edges) |
| `w1-case` | element | advisory | A `\cglab` name is not in sentence case. | [wording](wording.md#w1-case) |
| `w2-tag` | element | advisory | A line's tag is over three words or capitalised. | [wording](wording.md#w2-tag) |
| `w3-gloss` | element | advisory | A `\cglab` gloss is over six words. | [wording](wording.md#w3-gloss) |

Two objective rules cannot be allowed: `does-not-compile`, because
nothing else can be measured until it is fixed, and `twin-missing`,
because a figure without its twin shows nothing in the `md`, `html` and
`docx` renders. No advisory report can be allowed, because there is
nothing to set aside.

The id is the contract between four places: a finding, a `cg-allow`
line, this table and the `figure-drawer` skill's
`references/check.md`. `chitragupta/figure/_rules.py` is the registry,
and `tests/test_figure_rule_ids.py` fails if the four stop naming the
same set.

## 🧪 What needs a compiled figure

Twenty rules read the compiled geometry: `nothing-measurable`, the size
rules (`size-width`, `size-stray`, `content-protrusion`, `size-height`,
`size-slack`, `size-squash`), `node-overlap`, the connector rules `c1`
to `c7`, the contrast rules `k1` and `k2`, and the house-vocabulary
rules `type-below-floor`, `colour-off-palette` and `tint-outside-band`.
They are listed under "not measured", with the reason, when there is no
geometry to read:

- the figure does not compile;
- the file has no `tikzpicture` environment for the probe to sit in (a
  bare `\tikz` is not compiled);
- its last `tikzpicture` is inside a macro body that never runs.

A file with several pictures is measured as one figure for its width,
since the pictures print side by side. Its height, slack and squash are
listed as not measured, because the probe reads only the last picture's
extent. The connector rules are also not measured where a line and the
node boxes are not in one frame: a file with several `tikzpicture`s, or
one that uses `transform canvas`.

The geometry rules measure what TikZ drew, not what the source says. A
computed end point such as `(a.north |- b.south)` is measured where it
landed. So the fix for a finding is to change what you ask TikZ for (a
`node distance`, a `row sep`, a different anchor), never to nudge a
coordinate until the number moves. When a finding and your own eyes
disagree about a figure that is right, record the exception with
`cg-allow` and say why.

## 🗺 The layout line

Every scaffold in `assets/tikz/` starts with a line such as
`% cg-layout: pipeline`. Keep it. It does two things:

- **It names the reference ranges** the advisory size reports are read
  against, from the `## Reference ranges` table in
  `.claude/skills/figure-drawer/references/layouts/<layout>.md`. A
  figure with no layout line gets the numbers and no range.
- **It exempts a layout from the connector rules its grammar breaks on
  purpose.** A hub's spokes are diagonal and an automaton's transitions
  curve, so `c1-orthogonal` and `c4-attach` are not evaluated for
  `hub-and-spoke-network` and `state-machine`. A `sequence` is exempt
  from `c4-attach` and `c5-transit`. The full matrix is on the
  [connectors page](connectors.md).

`--layout NAME` overrides the line for one run.

## ✍ Recording a deliberate exception: `cg-allow`

A figure that breaks a rule on purpose says so in its own file, which
travels with it into the draft, the render and a thesis:

```latex
% cg-allow: size-width -- a five-stage pipeline the chapter compares stage by stage
% cg-allow: node-overlap legend+pot -- the legend sits on the pot on purpose
```

The form is `% cg-allow: <rule-id> [<target>] -- <reason>`, on a line
of its own.

- **The reason is required.** An allow without one is reported as
  malformed and allows nothing, so an exception is always a claim
  someone can read and disagree with.
- **A figure-scope rule takes no target, and an element-scope rule
  requires one**, so "allow every overlap" cannot be written.
- **An element-scope allow covers its one target**, spelt as the
  finding prints it (`decide.south`, not `decide`), so a later defect
  of the same kind elsewhere is still found. A pair matches in either
  order. A target with a space in it is written in double quotes, as
  the report prints it: `k2-text "tag on parse->ledger"`.
- **Every honoured allow is listed in the report**, with the
  measurement it set aside, so an exception is never invisible.
- **An allow that sets nothing aside is stale**: its target is gone
  (`no node named decide`) or no longer breaks its rule. Delete it, or
  fix its target. An allow whose rule could not run (the figure does
  not compile, or its layout exempts the rule) is listed as unchecked
  instead, since nothing was measured.

## ⚖ `figure check` and `review figure`

| | `chitragupta figure check <figure.tex>` | `chitragupta review figure <draft>` |
| --- | --- | --- |
| Reads | one figure file | every figure a draft draws |
| Rules | all 36 | seven of them: `does-not-compile`, `nothing-measurable`, `content-protrusion`, `loads-library-by-hand`, `node-overlap`, `node-text-overload`, `stranded-arrowhead` |
| Overlap | every node TikZ drew | named nodes only |
| Who runs it | the `figure-drawer` skill, after every change | a person, over a finished draft |
| Writes | nothing; prints the report | a report under `content/review/` with `--write` |

The shared rules have the same ids in both, but `figure check` measures
more: its `node-overlap` also sees unnamed nodes, zone titles and notes.
Use `figure check` while drawing a figure. Use `review figure` for a
quick pass over a whole draft, and run `figure check` on any figure it
flags. [REVIEW.md](../REVIEW.md) has `review figure` among the other
review aids.

## 🖼 The example figures

Every faulty and fixed figure on these pages is a real file under
[examples/](examples/), one directory per rule:
`examples/<rule-id>/faulty.tex` and `fixed.tex`, each with its ASCII twin
beside it. `tests/test_figure_check_examples.py` compiles them all and
holds each pair to two promises: the faulty figure breaks its own rule
and no other, and the fixed figure breaks nothing and leaves nothing
unmeasured. If a threshold moves, that test fails before a page can
show a defect the check no longer reports.

To check one pair, or re-render its pictures after changing it:

```bash
chitragupta figure check docs/figure-checks/examples/node-overlap/faulty.tex
chitragupta figure look docs/figure-checks/examples/node-overlap/faulty.tex
cp content/rendered/faulty.look.png docs/figure-checks/examples/node-overlap/faulty.png
```

After a change to the house style block, refresh every example's copy
with `chitragupta figure sync docs/figure-checks/examples`.

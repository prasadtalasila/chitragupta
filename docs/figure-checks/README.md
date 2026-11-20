# 🔎 Figure checks: what `figure check` reports, and how to fix it

Status: **reference.**

**Written for** anyone reading a `figure check` report, or wanting to
know what the check holds a figure to. **Assumed:** a figure file,
usually `content/drafts/<topic>/figures/<name>.tex`, drawn by the
`figure-drawer` skill or by hand ([FIGURE-DRAWER.md](../FIGURE-DRAWER.md)).
**Not covered here:** what makes a figure good beyond what can be
measured ([TIKZ-STYLE.md](../TIKZ-STYLE.md)).

## 🏃 Running it

```bash
chitragupta figure check content/drafts/rag/figures/flow.tex
```

It compiles the figure once, in the render's fonts at 12pt, and reads
back where TikZ put everything:

- `--page article|book` picks the page. By default a figure under a
  book's drafts directory (one with a `content/specs/<book>/spec.md`)
  is checked against the book's page (437.5pt by 685pt), any other
  against `draft render`'s A4 article page (453pt by 700.5pt). The
  report's second line names the page and why.
- `--width PT` overrides the width alone (a column, a thesis).
- `--layout NAME` overrides the `% cg-layout:` line.
- `--json` prints the report as data.

It exits 0 whatever it finds; exit 2 (a usage error, or no `lualatex`
or `tikz.sty`) means "not checked", never "clean"
([CLI.md](../CLI.md#-chitragupta-figure-check)). It is an aid, not a
gate: the only gate is `python -m chitragupta.draft gate`, which checks
citekeys ([SOUL.md](../../SOUL.md)).

## 📖 Reading a report

```text
figures/flow.tex
page     article (453.0pt x 700.5pt), not under content/drafts
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

Each finding is one line: `<rule-id> <target> <measurement>`. The id is
what `% cg-allow:` quotes and what heads the rule's section here. The
target is `figure` for a figure-scope
rule; for an element-scope rule it is a node (`decide`), a pair
(`legend+pot`), an edge (`decide->pot`), a side (`decide.south`) or a
point (`(3.0,2.0)`, in mm). An unnamed node shows as its centre in mm,
and a node TikZ names itself as `tikz@f@<n>` (a pin, an `alias`, an
unnamed node followed by `edge` or `child`). The measurement says by
how much.

- **Findings** come first, and all are **objective**: fix each one or
  record why it is deliberate with `% cg-allow:`. Never shrink or scale
  the figure to move a number.
- **advisory** reports are read, never resolved or allowed; size and
  budget reports sit beside the layout's reference range.
- **not measured** lists each rule that could not run, with the
  reason; it is never reported as a pass.
- **diagnostics** are for a person. Read the edge list against the
  prose: no rule checks that the arrows join the boxes the text says.
- **The last line** counts findings and honoured, stale, unchecked and
  malformed allows.

`No findings. This is not a verdict on the figure.` means every rule
that ran passed, not that the figure is good: look at it
(`chitragupta figure look`, [CLI.md](../CLI.md#-chitragupta-figure-look)).

## 📋 Every rule, and where it is explained

The 36 rules, in report order. **Scope** is what a `cg-allow` line
names; **class** says whether to resolve or allow (objective) or read
(advisory). Each page has the threshold, a faulty figure, the line
`figure check` prints, and the fixed figure.

| Id | Scope | Class | What it catches | Page |
| --- | --- | --- | --- | --- |
| `does-not-compile` | figure | objective | The TikZ does not compile, so nothing else can be measured. | [build](BUILD.md#does-not-compile) |
| `nothing-measurable` | figure | objective | No node is named, so the geometry rules measure nothing. | [build](BUILD.md#nothing-measurable) |
| `size-width` | figure | objective | Wider than the text width it prints at (453pt, or 437.5pt in a book). | [size](SIZE.md#size-width) |
| `size-stray` | figure | objective | A line outside the picture not ending in `%` adds a stray space. | [size](SIZE.md#size-stray) |
| `focal-count` | figure | objective | More than one node is accented, so none stands out. | [nodes](NODES.md#focal-count) |
| `content-protrusion` | figure | objective | An empty band taller than a third of the figure strands part of it. | [size](SIZE.md#content-protrusion) |
| `loads-library-by-hand` | figure | objective | A TikZ library is loaded by an internal macro, not `\usetikzlibrary`. | [build](BUILD.md#loads-library-by-hand) |
| `node-overlap` | element | objective | Two nodes' boxes intersect. | [nodes](NODES.md#node-overlap) |
| `node-text-overload` | element | objective | A node's label runs past 15 words. | [nodes](NODES.md#node-text-overload) |
| `stranded-arrowhead` | element | objective | A line drawn in pieces leaves an arrowhead mid-line. | [nodes](NODES.md#stranded-arrowhead) |
| `c1-orthogonal` | element | objective | A line between offset nodes slants or curves instead of turning a corner. | [connectors](CONNECTORS.md#c1-orthogonal) |
| `c2-tag-clearance` | element | objective | A line's tag sits on the line or more than 3mm away from it. | [connectors](CONNECTORS.md#c2-tag-clearance) |
| `c3-coincident` | element | objective | Two lines run on top of each other for more than 2mm. | [connectors](CONNECTORS.md#c3-coincident) |
| `c4-attach` | element | objective | A line meets a side off its midpoint, or lines bunch on one side. | [connectors](CONNECTORS.md#c4-attach) |
| `c5-transit` | element | objective | A line passes through a node that is not one of its ends. | [connectors](CONNECTORS.md#c5-transit) |
| `c6-tag-covered` | element | objective | A line's tag lies over a node. | [connectors](CONNECTORS.md#c6-tag-covered) |
| `c7-dangling-tip` | element | objective | An arrow ends in empty space, not on a node or line. | [connectors](CONNECTORS.md#c7-dangling-tip) |
| `k1-stroke` | element | objective | A border or line is too pale against its background (under 3:1). | [colour and type](COLOUR-AND-TYPE.md#k1-stroke) |
| `k2-text` | element | objective | Text is too pale against its fill (under 4.5:1, or 3:1 for large text). | [colour and type](COLOUR-AND-TYPE.md#k2-text) |
| `w4-pictograph` | element | objective | A label holds an emoji or pictograph from a fallback font. | [wording](WORDING.md#w4-pictograph) |
| `type-below-floor` | element | objective | Text is set smaller than the 12pt body size. | [colour and type](COLOUR-AND-TYPE.md#type-below-floor) |
| `colour-off-palette` | element | objective | Uses a colour the house block does not define. | [colour and type](COLOUR-AND-TYPE.md#colour-off-palette) |
| `tint-outside-band` | element | objective | A labelled node's tint is outside the 6 to 12 band, or a solid hue. | [colour and type](COLOUR-AND-TYPE.md#tint-outside-band) |
| `unnamed-pic` | element | objective | A house shape sits at a coordinate, not in a named `cgwell`, so is unmeasured. | [nodes](NODES.md#unnamed-pic) |
| `twin-missing` | figure | objective | No ASCII twin, so the `md`, `html` and `docx` renders show nothing. | [twin](TWIN.md#twin-missing) |
| `t1-labels` | element | objective | A TikZ node name, zone title or legend entry is missing from the twin. | [twin](TWIN.md#t1-labels) |
| `t2-tags` | element | objective | A TikZ line tag is missing from the twin. | [twin](TWIN.md#t2-tags) |
| `t3-panels` | figure | objective | The panel letters in the TikZ and the twin differ. | [twin](TWIN.md#t3-panels) |
| `size-height` | figure | advisory | Height as a share of the page, beside the layout's usual range. | [size](SIZE.md#size-height) |
| `size-slack` | figure | advisory | How much of the figure no node fills, beside the layout's range. | [size](SIZE.md#size-slack) |
| `size-squash` | element | advisory | Two joined nodes under 3mm apart leave too short an arrow to read. | [size](SIZE.md#size-squash) |
| `budget-nodes` | figure | advisory | Named nodes, beside the layout's usual range; never a cap. | [size](SIZE.md#budget-nodes) |
| `budget-edges` | figure | advisory | Edges, beside the layout's usual range; never a cap. | [size](SIZE.md#budget-edges) |
| `w1-case` | element | advisory | A `\cglab` name is not in sentence case. | [wording](WORDING.md#w1-case) |
| `w2-tag` | element | advisory | A line's tag is over three words or capitalised. | [wording](WORDING.md#w2-tag) |
| `w3-gloss` | element | advisory | A `\cglab` gloss is over six words. | [wording](WORDING.md#w3-gloss) |

Two objective rules cannot be allowed: `does-not-compile` (nothing
else can be measured) and `twin-missing` (the `md`, `html` and `docx`
renders would show nothing). No advisory report can be allowed. The id
ties together a finding, a `cg-allow` line, this table and the skill's
`references/check.md`; `chitragupta/figure/_rules.py` is the registry,
and `tests/test_figure_rule_ids.py` fails if they diverge.

## 🧪 What needs a compiled figure

Twenty rules read the compiled geometry: `nothing-measurable`, the size
rules (`size-width`, `size-stray`, `content-protrusion`, `size-height`,
`size-slack`, `size-squash`), `node-overlap`, the connector rules `c1`
to `c7`, the contrast rules `k1` and `k2`, and `type-below-floor`,
`colour-off-palette` and `tint-outside-band`. They are listed as not
measured, with the reason, when the figure does not compile, has no
`tikzpicture` (a bare `\tikz` is not compiled), or its last
`tikzpicture` sits in a macro body that never runs.

Several pictures in one file are measured together for width (they
print side by side); height, slack, squash and the connector rules are
not measured for them, nor connectors under `transform canvas`.

The rules measure what TikZ drew: `(a.north |- b.south)` is measured
where it landed. So fix a finding by changing what you ask TikZ for (a
`node distance`, a `row sep`, an anchor), never by nudging a coordinate
until the number moves. When a figure is right and a finding disagrees,
record a `cg-allow` and say why.

## 🗺 The layout line

Every scaffold in `assets/tikz/` starts with a line such as
`% cg-layout: pipeline`. Keep it: it names the reference ranges the
advisory size reports use (the `## Reference ranges` table in
`.claude/skills/figure-drawer/references/layouts/<layout>.md`; with no
line you get numbers and no range), and it exempts a layout from the
connector rules its grammar breaks on purpose. `c1-orthogonal` and
`c4-attach` are not evaluated for `hub-and-spoke-network` (diagonal
spokes) and `state-machine` (curved transitions), and a `sequence` is
exempt from `c4-attach` and `c5-transit`; the
[connectors page](CONNECTORS.md) has the full matrix. `--layout NAME`
overrides the line for one run.

## ✍ Recording a deliberate exception: `cg-allow`

A figure that breaks a rule on purpose says so in its own file, which
travels with it:

```latex
% cg-allow: size-width -- a five-stage pipeline the chapter compares stage by stage
% cg-allow: node-overlap legend+pot -- the legend sits on the pot on purpose
```

The form is `% cg-allow: <rule-id> [<target>] -- <reason>`, on its own
line.

- **The reason is required**; without one the allow is malformed and
  allows nothing.
- **A figure-scope rule takes no target, and an element-scope rule
  requires one**, so "allow every overlap" cannot be written.
- **An element-scope allow covers its one target**, spelt as the
  finding prints it (`decide.south`, not `decide`); a pair matches in
  either order, and a target with a space is double-quoted as printed:
  `k2-text "tag on parse->ledger"`.
- **Every honoured allow is reported** with what it set aside.
- **An allow that sets nothing aside is stale** (its target is gone, or
  no longer breaks the rule): delete or fix it. An allow whose rule
  could not run (no compile, or a layout exemption) is listed as
  unchecked.

## ⚖ `figure check` and `review figure`

| | `chitragupta figure check <figure.tex>` | `chitragupta review figure <draft>` |
| --- | --- | --- |
| Reads | one figure file | every figure in a draft |
| Rules | all 36 | `does-not-compile`, `nothing-measurable`, `content-protrusion`, `loads-library-by-hand`, `node-overlap`, `node-text-overload`, `stranded-arrowhead` |
| Overlap | every node, zone title and note TikZ drew | named nodes only |
| Who runs it | the `figure-drawer` skill, after every change | a person, over a finished draft |
| Writes | nothing | a report under `content/review/` with `--write` |

Use `review figure` ([REVIEW.md](../REVIEW.md)) for a quick pass over a
draft, then `figure check` on what it flags.

## 🖼 The example figures

Every faulty and fixed figure on these pages is a real file under
[examples/](examples/): `examples/<rule-id>/faulty.tex` and
`fixed.tex`, each with its ASCII twin. `tests/test_figure_check_examples.py`
compiles them all and fails unless each faulty figure breaks its own
rule and no other, and each fixed one breaks nothing and leaves nothing
unmeasured, so a moved threshold fails before a page goes wrong.

To check one pair, or re-render its pictures after changing it:

```bash
chitragupta figure check docs/figure-checks/examples/node-overlap/faulty.tex
chitragupta figure look docs/figure-checks/examples/node-overlap/faulty.tex --output-dir content/scratch
cp content/scratch/faulty.look.png docs/figure-checks/examples/node-overlap/faulty.png
```

After a change to the house style block, refresh every example's copy
with `chitragupta figure sync docs/figure-checks/examples`.

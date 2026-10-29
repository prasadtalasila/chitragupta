# figure-drawer: checking a figure

`python -m chitragupta.figure check figures/<name>.tex` compiles the
figure once, in the render's fonts at 12pt, and prints one line per rule
it breaks:

```text
figures/flow.tex
  size-width            figure     475.2pt wide, target 453.0pt
  node-overlap          legend+pot boxes intersect
advisory (read; never resolved, allowed or capped)
  size-height           figure     0.24 of the text height (168pt); pipeline reference 0.10 to 0.37
  size-slack            figure     0.82; pipeline reference 0.55 to 0.68
  size-squash           load+parse 1.2mm apart edge to edge, under 3mm
  budget-nodes          figure     9 nodes; pipeline reference 5 to 11
  budget-edges          figure     8 edges; pipeline reference 3 to 4
figure check: 2 findings, 0 allowed, 0 deferred, 0 malformed
```

Each line is `<rule-id> <target> <measurement>`. It exits 0 whatever it
finds; exit 2 means it checked nothing (a usage error, or no `lualatex`
or `tikz.sty`), so report that to the caller instead of reading it as
clean. `--width PT` sets a narrower target when the caller has one (a
column, a thesis text block); `--layout NAME` reads the advisory
reports against another layout than the figure's own `% cg-layout:`
line; `--json` prints the same report as data.

## What to do with each finding

Every rule below down to `stranded-arrowhead` is **objective**: resolve
it, or record why it is deliberate. Never leave one unanswered and never
shrink or scale the figure to make a number move. Change what the figure
asks TikZ for. The last five are **advisory**: they print under their
own heading, never count as findings and cannot be allowed.

| Rule | Scope | Usual fix |
| --- | --- | --- |
| `does-not-compile` | figure | Fix the TeX error it quotes; nothing else was measured. Cannot be allowed |
| `nothing-measurable` | figure | Name the nodes you draw (`\node (a)`, `child { node (a) ... }`) |
| `size-width` | figure | Wrap a row, cut a gloss, stack panels; see section 3 of `.claude/skills/figure-drawer/references/figures.md` |
| `size-stray` | figure | End every line outside the picture with `%` |
| `focal-count` | figure | Keep `cgkey` on the one node the figure is about |
| `content-protrusion` | figure | Pull the stranded element back into the main block |
| `loads-library-by-hand` | figure | Delete the internal macro; keep the plain `\usetikzlibrary` line |
| `node-overlap` | element | More room between the pair (`node distance`, a gap) |
| `node-text-overload` | element | Cut the label to 15 words or split the node |
| `stranded-arrowhead` | element | Put the `->` on the last piece of the line only |
| `size-height` | figure | Advisory. Read it beside the reference: far taller than its layout's figures usually means a row to wrap or a stage to drop |
| `size-slack` | figure | Advisory. The share no node fills, zone cards excluded; well above the reference, pull the nodes closer or cut the empty zone |
| `size-squash` | element | Advisory. The pair's arrow is under 3mm, too short to read; give the pair more room |
| `budget-nodes` | figure | Advisory. Never a cap: a DP trace has forty cells. Far above the reference, ask whether this is two figures |
| `budget-edges` | figure | Advisory. As `budget-nodes`, for the edges the source parser reads (not a `\foreach` body or a `child`) |

The advisory reports read the figure's layout from its
`% cg-layout: <name>` line, which every scaffold carries. With none,
the numbers print bare and say so.

The edge list, the names declared but not measured and the emptiness
percentage are printed under "diagnostics (not findings)". Read the edge
list against the prose the figure illustrates: it is the check nothing
else makes.

## Recording a deliberate exception

When breaking a rule is the right call, say so in the figure file, on a
line of its own:

```latex
% cg-allow: size-width -- a five-stage pipeline the chapter compares stage by stage
% cg-allow: node-overlap legend+pot -- the legend sits on the pot on purpose
```

- The reason after `--` is required; without one the line is reported
  under "malformed allows" and allows nothing.
- A figure-scope rule takes no target. An element-scope rule needs one:
  a node (`decide`), a pair (`legend+pot`) or a point (`(3,2)`).
- An honoured allow is listed under "allowed" with the measurement it
  set aside, or `did not fire`. An element-scope allow is listed under
  "not honoured until #1058" and its finding still prints; leave it in
  place, it is honoured once that lands.

Run `check` again after every change until each objective finding is
fixed or allowed, then tell the caller what was allowed and why.

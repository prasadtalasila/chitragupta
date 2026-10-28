# figure-drawer: checking a figure

`python -m chitragupta.figure check figures/<name>.tex` compiles the
figure once, in the render's fonts at 12pt, and prints one line per rule
it breaks:

```text
figures/flow.tex
  size-width            figure     475.2pt wide, target 453.0pt
  node-overlap          legend+pot boxes intersect
figure check: 2 findings, 0 allowed, 0 deferred, 0 malformed
```

Each line is `<rule-id> <target> <measurement>`. It exits 0 whatever it
finds; exit 2 means it checked nothing (a usage error, or no `lualatex`
or `tikz.sty`), so report that to the caller instead of reading it as
clean. `--width PT` sets a narrower target when the caller has one (a
column, a thesis text block); `--json` prints the same report as data.

## What to do with each finding

Every rule below is **objective**: resolve it, or record why it is
deliberate. Never leave one unanswered and never shrink or scale the
figure to make a number move. Change what the figure asks TikZ for.

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

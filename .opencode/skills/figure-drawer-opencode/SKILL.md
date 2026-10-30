---
name: figure-drawer-opencode
description: Draws one figure for a draft in content/drafts/ -- a TikZ picture in figures/<name>.tex and its ASCII twin in figures/<name>.txt -- from the house scaffolds in assets/tikz/, then compiles and reviews it. Handed off to by survey-writer-opencode, tutorial-writer-opencode, textbook-chapter-writer-opencode and thesis-chapter-writer-opencode once they have decided a figure is warranted, and by draft-reviser-opencode to redraw or fix one. Also triggers directly when the user asks to draw, add, redraw or fix a figure or diagram in an existing draft. Owns how a figure is drawn, never whether a genre wants one. Never presents a draft -- it returns to the skill that called it, which gates and renders. Never puts a citekey in a figure file.
tags: [figure, tikz, drafting]
---

# figure-drawer

This skill owns *how* a figure is drawn. Whether a draft wants one, and
its shape there, is the calling genre skill's. `docs/WRITING-STANDARDS.md`
§10 is the contract for every figure. Paths in this skill are from the
project root. This skill **never presents a draft**: it returns to the
step that sent it.

## Who called you

- **A genre skill** (`survey-writer-opencode`,
  `tutorial-writer-opencode`, `textbook-chapter-writer-opencode` or
  `thesis-chapter-writer-opencode`): draw, check, and return to its next
  step.
- **`draft-reviser-opencode`**, redrawing or fixing one figure: the
  same, and it logs the change.
- **The user, directly.** That is a revision. Read the draft's
  `scope.md` for its genre and house style, then draw and check, and
  continue in `draft-reviser-opencode`'s loop at "6. Write the dossier back" and
  "7. Gate, reference, render". The genre's when-to-draw threshold does
  not apply: the person asked. A `deep-research-opencode` draft takes no figure,
  and with no draft there is nowhere to put one: say so and stop.

## Where it goes

A `.md` draft takes `<!-- figure: figures/<name> -->` on a line of its
own; a `.tex` one takes `\input{figures/<name>.tex}` then
`%figure: figures/<name>`. The pair, `figures/<name>.tex` and `.txt`,
sits in `content/drafts/<topic>/figures/`. The caption, the
`figureref` marker, and on direct use no TikZ, a flat draft or a thesis
fragment: `.claude/skills/figure-drawer/references/placement.md` §1,
§2, §3 and §4.

## The procedure

1. **Look, never copy (optional).** `python -m chitragupta.draft figures
   <citekey>` shows a cited paper's figures. They are input to a diagram
   you draw yourself; the TikZ must be as original as the ASCII:
   `.claude/skills/figure-drawer/references/figures.md` §5.

2. **Pattern, then layout.** Commit to a layout metaphor before drawing.
   Name what the figure argues, route it through
   `.claude/skills/figure-drawer/references/patterns.md`, then read that
   layout's file:
   `.claude/skills/figure-drawer/references/layouts/pipeline.md`,
   `.claude/skills/figure-drawer/references/layouts/map.md`,
   `.claude/skills/figure-drawer/references/layouts/layered-stack.md`,
   `.claude/skills/figure-drawer/references/layouts/control-loop.md`,
   `.claude/skills/figure-drawer/references/layouts/branching-tree.md`,
   `.claude/skills/figure-drawer/references/layouts/hub-and-spoke-network.md`,
   `.claude/skills/figure-drawer/references/layouts/state-machine.md`
   or `.claude/skills/figure-drawer/references/layouts/zoned-spine.md`.
   Metaphors, panels, fit and the exemplar:
   `.claude/skills/figure-drawer/references/figures.md` §1, §2, §3 and §4.

3. **The taste gate.** Before anything is written, answer, in
   `.claude/skills/figure-drawer/references/taste.md` §1, §2, §3, §4, §5
   and §6:
   - Would a sentence or a table do this?
   - The remove test: which node, edge or label can go?
   - Which two nodes always travel together, and become one?
   - Is there one focal node?
   - Is this one figure or two figures (overview and detail)?

   Make the trims yourself. A structural verdict (a sentence, a table, or
   two figures): draw nothing, and return the verdict and its reason to
   the caller, who decides. On direct use, ask the user.

4. **Start from the scaffold.** `kpsewhich tikz.sty`: if it finds
   nothing, write no pair (`.claude/skills/figure-drawer/references/placement.md`
   §2) and return. Otherwise:

   ```bash
   python -m chitragupta.figure new content/drafts/rag/figures flow --layout zoned-spine
   ```

   It copies the scaffold and its twin, keeps `% cg-layout:`, brings the
   house block up to date as `python -m chitragupta.figure sync` would,
   and never overwrites a figure.

5. **Draw below the house block**, never inside it. Re-label; name every
   node; nodes placed relative to one another. More than one panel gets
   lettered sub-captions, `(a)`, `(b)`, in both forms, or the lettering
   `scope.md` records. A library goes in
   one `\usetikzlibrary` line at the top and nothing else about loading:
   `.claude/skills/figure-drawer/references/figures.md` §6, §7.
   **No citekey inside either figure file**: the gate does not follow
   `\input`, so attribute in the prose beside the figure.

6. **Redraw the ASCII twin** at `figures/<name>.txt`, in
   `docs/WRITING-STANDARDS.md` §10's 7-bit alphabet: the same boxes,
   arrows and panel letters, named in the TikZ's own words (a state
   machine's twin is its transition table instead: its layout file says
   how). `figure check`
   reports `twin-missing`, `t1-labels`, `t2-tags` and `t3-panels`;
   whether the arrows join the same boxes is yours to see.

7. **Check it.**

   ```bash
   python -m chitragupta.figure check content/drafts/rag/figures/flow.tex
   ```

   Resolve each objective finding, or record why it is deliberate with
   `% cg-allow: <rule-id> -- <reason>`, and run it again until none is
   unanswered. Read the advisory lines; they are references, not
   findings. If it exits 2 it checked nothing: say so. It never blocks.
   Rules, fixes and the allow form:
   `.claude/skills/figure-drawer/references/check.md`.

8. **Look at it.**

   ```bash
   python -m chitragupta.figure look content/drafts/rag/figures/flow.tex
   python -m chitragupta.figure look content/drafts/rag/figures/flow.tex --draft content/drafts/rag/survey.md
   ```

   Open the PNGs and read them against the pre-flight defect list
   (`.claude/skills/figure-drawer/references/figures.md` §6); fix the
   layout, never the scale. If it exits 2 or you cannot
   view an image, skip the look and say so in chat.

9. **Return.** Tell the caller the two paths, or the gate's verdict;
   what the taste gate cut; what `figure check` reported and allowed;
   and whether the look was done. The caller places the marker and the
   caption, then gates and renders.

# 🔬 Deep research: what the genre owes its reader

Assumes the core, §1–9 of [WRITING-STANDARDS.md](../../WRITING-STANDARDS.md).
This file holds the writing rules that apply to a multi-perspective
deep-research report alone: what the genre is for, why it uses no
figures, how its tables and mathematics survive being written in
parallel, and what its reread looks for. The element rules are in
[figures.md](../figures.md), [mathematics.md](../mathematics.md) and
[tables.md](../tables.md); this file repeats none of them.

## 🎯 What a deep-research report owes its reader

A deep-research report reconciles several perspectives on one question
and says **where the corpus disagrees with itself**. Its reader wants
the disagreement, not a smoothed consensus: a contradiction map, the
evidence ranked by how well the corpus supports it, and a blind spot
named as plainly as a finding. A single-pass literature survey organises
a field; this genre interrogates one question from several sides, and a
report that reads as one voice has usually lost what it was for.

Two rules apply with particular force, because the report is written by
parallel section writers who each see one slice:

- **Terminology is fixed at outline time, not at polish time.** Every
  recurring term has one definition, in one glossary, which every
  section uses as written. Four writers who each named the same concept
  differently produce a reconciliation problem that the outline could
  have prevented ([WRITING-STANDARDS.md](../../WRITING-STANDARDS.md) §2).
- **Scope is stated in the report, not held in the author's head.** The
  lead says what the report covers and what it doesn't, including which
  sub-questions the corpus could not answer
  ([WRITING-STANDARDS.md](../../WRITING-STANDARDS.md) §3 and §7).

A deep-research report's unit for multi-source synthesis is the
paragraph ([WRITING-STANDARDS.md](../../WRITING-STANDARDS.md) §11): a
body paragraph closes on two or more citekeys wherever the evidence
allows, organised around what its sources agree and disagree about.

## 📐 No figures, by design

Every other genre calibrates how freely it uses
[figures.md](../figures.md) §10; this one uses none. If a section
genuinely needs a visual, say so in the report rather than adding one.

## 📊 Tables carry this genre's shape

[tables.md](../tables.md) §13 applies, and matters here more than
elsewhere: a contradiction map or a per-perspective comparison is this
genre's natural shape. Because sections are written in parallel, two
writers can pick the same table id: two sections that both wrote
`<!-- table: comparison -->` produce one broken cross-reference in the
assembled report. Ids are therefore checked for collisions when the
sections are joined, not per section.

## 🔢 Mathematics: carried over, reconciled once

[mathematics.md](../mathematics.md) §12 applies, unlike §10. A quantity
carried over from a source (a threshold, an effect size, a bound) goes
in a code span as ASCII with a row in the dossier's `math.md`, so the
pdf sets it as mathematics and the `.md` stays readable. Each writer
sees only its own slice, so the rows are collected into one `math.md`
when the sections are joined, `## Symbols` meanings included, and a
symbol two sections spelled differently is reconciled to one spelling
rather than kept twice.

**Number sparingly, and only when the sections are joined.** §12's
numbering rule (standalone, the final step of a derivation, or reused
elsewhere) rarely fires within one writer's slice. It is more likely to
fire *across* sections, when two writers independently reported the
same bound and a later section reuses it. The equation's marker and
its reference are added then, and its id is checked for collisions the
same way as the table ids: two writers working in parallel can pick the
same short id for unrelated results.

## 👓 The reread

Read the assembled report once as its reader before presenting it
([WRITING-STANDARDS.md](../../WRITING-STANDARDS.md) §6): a pass over the
whole document, which no individual section writer was in a position to
make. Parallel writers leave specific, predictable seams; check for:

- the same concept named two ways, or one name used for two concepts;
- a term defined independently in two sections;
- notation that shifts between sections;
- the same finding stated at different strengths in two places;
- a claim one section assumes but only a later section establishes.

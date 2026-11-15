# 🗺 Survey: what the genre owes its reader

Assumes the core, §1–9 of [WRITING-STANDARDS.md](../../WRITING-STANDARDS.md).
This file holds the writing rules that apply to a literature survey, a
background section, a related-work section or a "state of the art"
alone: what the genre is for, how rare its figures and numbered
equations are, and what its reread looks for. The element rules are in
[figures.md](../figures.md), [mathematics.md](../mathematics.md) and
[tables.md](../tables.md); this file repeats none of them.

## 🎯 What a survey owes its reader

A survey's job is to **organize a field and locate the gaps in it**: not
to teach the topic and not to advocate a position. Name which reader
first ([WRITING-STANDARDS.md](../../WRITING-STANDARDS.md) §1): a thesis
reader, a grant reviewer, a paper's related-work section. There are two
failure directions:

- **Drifting into a textbook chapter.** You start explaining the
  concepts for a reader who doesn't know them. A survey's reader is a
  researcher entering the area; they need the map, not the lesson. If
  the user actually wants the lesson, the textbook-chapter writer
  exists: say so.
- **Drifting into an argument.** You start defending one approach as
  correct. Weighing alternatives is the deliverable here; picking a
  winner is the thesis chapter's job, and doing it in a survey hides the
  disagreement the reader came for.

Unlike the tutorial genre, **alternatives and options are the point**.
Never collapse them for the sake of a cleaner narrative.

A survey's unit for multi-source synthesis is the paragraph
([WRITING-STANDARDS.md](../../WRITING-STANDARDS.md) §11): a body
paragraph closes on two or more citekeys wherever the evidence allows.

## 📐 Figures are the rarest of any genre

The comparison table already carries a survey's structural work, so a
figure earns its place only for a relationship the table cannot
express, such as a taxonomy no comparison row shows, and sits beside
the relationship it captures. Absence is the default, not an oversight.
When a survey does draw one, the whole of [figures.md](../figures.md)
§10 applies to it.

This is also the genre most likely to want a citekey inside a figure,
because a taxonomy naturally attributes each branch. That is exactly the
wrong place for it: the citation gate reads the draft and does not
follow `\input`, so a key in a node label evades the one check this
pipeline exists for. Attribute in the prose or the comparison table,
where the gate can see the key. A taxonomy redrawn from a source
survey's own figure is the same violation as copying the figure, in
different pixels, whichever notation it is drawn in.

## 🔢 Mathematics: rare, and mostly unnumbered

A survey rarely has much mathematics, but a threshold or an error bound
quoted from a source is a quantity, and
[mathematics.md](../mathematics.md) §12 applies to it like any other: a
bare `` `k = 4` `` renders as typewriter text.

Most of that mathematics stays unnumbered. §12 gives a displayed
equation a number only if it is standalone, the final step of a
derivation, or reused later, and a survey, which reports results rather
than proving them, rarely has a derivation at all. Number one when a
comparison across sources genuinely needs it: restating a formula two
papers define differently before contrasting them, say. The numbered
form then has a sentence that refers to it and explains what it shows,
like a table or a figure.

## 👓 The reread

Read the draft once as its reader before presenting it
([WRITING-STANDARDS.md](../../WRITING-STANDARDS.md) §6). In a survey,
check specifically for:

- a term used before it is defined;
- a theme heading that doesn't match what the subsection actually
  argues;
- a comparison-table row that repeats prose already above it;
- any paragraph whose first sentence doesn't carry its point.

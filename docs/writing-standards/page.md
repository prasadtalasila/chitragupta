# 📄 What has to fit the page

Status: **reference.** An element file of the
[writing standards](../WRITING-STANDARDS.md), listed in the core's index.

Assumes the core, §1–9 of [WRITING-STANDARDS.md](../WRITING-STANDARDS.md).
This file holds §14, under the number it had in the core, so a
citation reads `docs/writing-standards/page.md` §14.
`chitragupta/style_typeset.py` reports its decidable part as
`draft style` findings.

## 📄 14. What has to fit the page

A draft is read on paper, or on a screen shaped like paper. Three
things run into the margin there and nowhere else, so they are invisible
until someone opens the PDF, which is usually after the draft has been
reviewed. A fourth, a matrix set inline, is [§12's](mathematics.md#-12-mathematics)
rule, because it is mathematics before it is layout.

### 🔗 Link the text, don't print the URL

Write **`[descriptive text](https://…)`**, not the URL itself. A bare URL is
worse on three counts: it reads as noise mid-sentence, it gives the PDF
nothing to click, and a long one is a single unbreakable token.

```markdown
See [the plant-controller repository](https://github.com/INTO-CPS-Association/plant-controller).
```

not

```markdown
See https://github.com/INTO-CPS-Association/plant-controller.
```

A code span that is *only* a URL counts as a bare one; the monospace
font changes nothing about how it reads. A code span with a URL among
other tokens (`curl https://…`) is a command, and is left alone: making
it a link would corrupt the thing it prints.

### 📏 Keep a code block inside the page

**76 columns**, measured rather than chosen: at this project's book
geometry (11pt, 80pt margins) a `verbatim` line fits 79, and at `draft
render`'s own defaults (12pt, 1in margins) it fits 76. A draft may be
rendered either way, so the tighter one is the limit. Both numbers were
measured through pandoc's own template, which loads `lmodern`;
measuring against a bare `\documentclass` gives 76/73, three columns
tight, because Computer Modern's typewriter face is wider.

**A Markdown draft's blocks wrap rather than overflow**, so this is
a quality rule rather than a defect one. `draft render` loads `fvextra`
and redefines `verbatim`/`Highlighting` with `breaklines` for any draft
that has a fenced block, so an over-wide line breaks at a space and
marks the continuation with `,→`. Keeping the line short avoids that
marker, which a reader copying the command out of the pdf would
otherwise pick up.

**A `.tex` fragment is the case that cannot be repaired at render
time**, and is why the check exists at all. `thesis-chapter-writer` emits a fragment
`\input` into the user's own thesis, whose preamble this pipeline may
not touch (§13's carve-out), so nothing can load `fvextra` on its
behalf, and a wide `verbatim` line there runs into the margin. Shorten
it: break the pipeline, drop the aligned comment column,
abbreviate the path.

A book is the third case: its units are rendered `--fragment`, which
emits no preamble, so its `book.tex` carries the `fvextra` load itself
(see `.claude/skills/book-assembler/references/latex-conventions.md`).

`chitragupta.WideCodeLine` reports a line over the limit with `repair:
"review"`, so a person decides rather than an unattended pass. A wide
line may be deliberate: a URL, or a literal in a block verified to run.
The repair edits a code sample rather than prose, and dropping an
argument to fit the width leaves a command that still reads plausibly
and does not work.

### 🔤 Prefer a breakable form for a very long token

Where a choice exists, prefer a token under about **15 characters**, or
one with an internal `-`, `/` or `_` to break at.

No check backs this, because TeX hyphenates a long English word in a
roman font well: `interoperability` sets as `in-teroperability` even in
a 4cm column, and so does a camelCase identifier written in prose.
Measured across this project's own 428-page book, no prose word caused
an overflow, and a rule flagging every token over 15 characters raised
36 candidates (`interoperability`, `indistinguishable`,
`microcontrollers`), none of which has a repair that is not a worse
word. So it stays advice to an author choosing between two phrasings,
and never becomes a finding. §9's table records it beside the other row
with no mechanical proxy.

`python -m chitragupta.draft style` reports the decidable part of this
section: a bare URL, and a code line over the column limit. The
third rule is not checked, deliberately, per the paragraph above.

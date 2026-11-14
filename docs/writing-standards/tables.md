# 🔢 Tables

Status: **reference.** An element file of the
[writing standards](../WRITING-STANDARDS.md), listed in the core's index.

Assumes the core, §1–9 of [WRITING-STANDARDS.md](../WRITING-STANDARDS.md).
This file holds §13, under the number it had in the core, so a
citation reads `docs/writing-standards/tables.md` §13.
`chitragupta/style_tables.py` reports its decidable part as
`draft style` findings.

## 🔢 13. Tables

A table is evidence arranged for comparison. It needs a **caption**, so
the rendered document can number it, and a **sentence that reads it**,
so the reader is not left to work out what the arrangement was for.

Without a caption, a survey's comparison table renders as an unnumbered
`longtable` that no sentence can name.

### 🏷 A caption, an id, and no number you write yourself

A Markdown draft writes the table, pandoc's own caption line, and an id
marker directly under it, with no blank line between the two (the same
adjacency §11's `<!-- single-source: -->` uses):

```markdown
| Starting point | Core idea | Stated limitation |
|---|---|---|
| DTaaS platform | One tenant-facing platform | Reuse needs components |

: Where to start when building a first twin.
<!-- table: start-here -->
```

Prose points at it with an inline marker, which stands in for the whole
reference phrase; you write neither the word "Table" nor a number:

```markdown
The platforms in <!-- tableref: start-here --> differ mainly in what
they ask you to bring.
```

**Never write the number.** `: Table 1: Where to start.` renders as
"Table 1: Table 1: Where to start.", because LaTeX supplies its own
prefix; and a number typed into a chapter is wrong the moment that
chapter is assembled into a book, where the same table numbers "2.1",
or something else again, since a book that suppresses chapter numbering
counts its tables flat from the front. `render` resolves both markers
per format ([RENDERING-FLOW.md](../RENDERING-FLOW.md) has the four cases): LaTeX-bound
output gets a `\label` and numbers itself, and every other format gets a
number counted at render time, because pandoc numbers nothing outside
LaTeX.

**The caption is visible text; only the id hides.** A caption may cite,
and `python -m chitragupta.draft gate` reads the draft, so the caption
stays where a reader and the gate can both see it. The id is not prose
and nobody reads it, which is why it is the half in a comment.

**Ids are kebab-case and unique within a draft.** Two tables sharing one
id become two `\label{}`s in one LaTeX document, where a duplicate
resolves silently to the wrong table, which is a real risk for a book
unit, since [WRITE-A-BOOK.md](../WRITE-A-BOOK.md)'s assembly puts fifteen
units in one document.

### 📄 The `.tex` fragment writes its own

`thesis-chapter-writer` carries no marker. It writes a real LaTeX table
with its own `\caption` and `\label`, and refers to it with
`Table~\ref{tab:start-here}`:

```latex
\begin{table}
\caption{Where to start when building a first twin.}\label{tab:start-here}
\begin{tabular}{lll}
...
\end{tabular}
\end{table}
```

Same carve-out as §10's inline TikZ, and the same reason: that fragment
is `\input` into the user's own thesis, where their own LaTeX
numbers it consistently with their other chapters. Nothing this pipeline
does may get between them.

### 👓 The sentence that reads the table

A caption says what a table *is*. It does not say what it *shows*, and a
table dropped into a section with neither a lead-in nor a reading is
work handed to the reader.

- **Introduce it before it appears**: what is being compared, and on
  what axis.
- **Read a pattern off it afterwards**: the row that is the exception,
  the column where everything agrees, the trade-off the arrangement
  makes visible. If nothing can be read off it, the table is decoration.
- **Keep the reference beside the table.** A table in §6 whose only
  mention is in §2 is one the reader meets unannounced.
- **Say it once.** Prose that re-states every row is a table set twice;
  the point of the arrangement is that it does not need narrating.

`python -m chitragupta.draft style` reports the decidable part of this:
a table with no caption, no id, an id that is not kebab-case, a
duplicate id, a reference to a table
that does not exist, a table no sentence refers to, and a table
referenced only from another section. Whether the sentence that refers
to it *explains* it is a judgement, and stays one; §9's table
records the split.

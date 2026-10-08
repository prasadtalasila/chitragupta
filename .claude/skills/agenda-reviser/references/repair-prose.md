# Repairing a `prose` item

Read this when the item in hand is of class `prose`. The step that sent
you here says which edit tool to use. Paths here are from the project
root.

**Repair a `prose` item.** Apply the fix `draft style`'s rule names: expand
an acronym at first use, add the `<!-- table: -->`, `<!-- tableref: -->` or
`<!-- figureref: -->` marker a `TableNoCaption`/`TableUnreferenced`/
`FigureNoCaption`/`FigureUnreferenced` finding names, correct a glossary
term drifted from `scope.md`'s vocabulary, fix a dialect slip against
`scope.md`'s `language:` line. Change only the exact span
`detail.message` or the item's `summary` names.

**`ChapterSelfNumbered`** (a `.tex` draft only) is the one rule whose
repair is a deletion rather than an addition: drop the `Chapter N:`
prefix from inside the `\chapter{...}` braces and leave the title, so
the document the fragment is `\input` into supplies the number once. Do
not touch the heading's `\label`, and do not reach for
`\setcounter{secnumdepth}{-2}` -- that is a book-wide decision belonging
to `content/specs/<book>/preamble.tex`, and it would cost every section
and table number in the book (docs/WRITING-STANDARDS.md §15).

Two equation rules repair differently from their table/figure siblings.
**`EquationOrphanMarker`** -- delete the stray `<!-- equation: id -->`
marker rather than hunting for a `<!-- math -->` block to reattach it to:
the marker's own text cannot tell this skill which block the author
meant, and guessing wrong either drops intended numbering or leaves the
finding standing, so deletion is the one repair that is never wrong.
**`EquationUnreferenced`** -- the fix is not a marker addition but a
sentence: insert prose that names the equation via
`<!-- equationref: id -->` (docs/WRITING-STANDARDS.md §12). This is a
larger edit than a caption line, and the likeliest of this section's
repairs to trip the `objective_delta` check in step 5 by introducing its
own new acronym or wording drift -- treat that as the check doing its
job, not a reason to loosen it.

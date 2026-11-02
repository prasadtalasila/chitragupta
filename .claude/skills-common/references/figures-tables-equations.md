# Figures, tables and equations in a revision

Read the section a revision needs, when it touches a figure, a table, a
numbered equation or a quantity written as math. The rule each one
enforces is stated in the step that sends you here; this file has the
detail. Paths here are from the project root.

## 1. Consult a source figure before redrawing one

`python -m chitragupta.draft figures <citekey>` lists a synced paper's
figures -- caption, page, the string to cite each by, and the path to a
crop -- for any citekey the section already cites. It is worth running
twice over: before revising a sentence that asserts what a paper's
figure *shows* (the caption is retrievable as text and routinely says
less than the picture), and before reworking a diagram of the draft's
own. The source image never enters the draft and its layout is not
yours to copy; the `cite` string is the part that belongs in prose.
AGENTS.md has the boundary in full, and it is the same one `quote:`
draws for wording.

## 2. Touch a figure, touch both forms

Every figure exists twice: as a TikZ picture in `figures/<name>.tex`,
and as the plain-ASCII diagram in `figures/<name>.txt`, the same pair of
files in every genre. Find them from the marker (`<!-- figure: ... -->`
in a Markdown draft, `%figure:` in a `.tex` one), which is greppable
precisely so this is not a reading exercise. Relabel a box, add an
arrow, rename a component in one form and you must make the same change
in the other.

**A panelled figure's letters are part of that pair.** Adding, dropping
or re-ordering a panel re-letters every panel after it, in the picture
*and* in the ASCII twin, and lettering an unlettered figure is a figure
edit like any other: log it in `revisions.md`. Which lettering to use is
`scope.md`'s to say: it is a house-style decision under
`docs/WRITING-STANDARDS.md` §8, read before the edit rather than
re-decided during it.

**One difference survives by genre, and it is not about where the files
are.** A thesis chapter's TikZ additionally stays inline via a real
`\input`: that fragment is what the user `\input`s directly into their
own thesis, so editing it means editing the fragment itself, not just
`figures/<name>.tex` beside it. Every other form, in every genre, lives
only in `figures/`.

**Nothing checks any of this.** No gate, no style rule and no render
error can tell that a picture and a diagram have stopped depicting the
same thing, so a half-done edit leaves the pdf and the Markdown preview
disagreeing about the same figure, silently, until a reader notices. A
redrawn picture must still compile: a figure that no longer compiles
fails the whole pdf render, not just the figure.

## 3. Tables renumber themselves; ids do not

`docs/WRITING-STANDARDS.md` §13 has the renderer assign every number, so
inserting a table above another one is safe and there is nothing to
renumber by hand. A literal "Table 3" in the prose of a draft you are
revising is the defect, and the fix is an inline
`<!-- tableref: <id> -->`.

What a revision *can* break is an id: deleting a table whose id
something still refers to, or copying a table into another section and
copying its id with it. Both are reported by the prose check (§13's
table findings, over the `<!-- table: <id> -->` markers beneath each
caption); read those rather than eyeballing the markers. A table you add
is a table you also introduce and read a pattern off; a table left
standing with no sentence pointing at it is a `TableUnreferenced`
finding and a reader's problem.

## 4. A captioned figure renumbers itself too; its id does not

Issue 411 gives a *captioned* figure the same contract, over the same
`<!-- figure: ... -->` marker §2 reads: a literal "Figure 2" in the
prose is the defect, and the fix is an inline
`<!-- figureref: <id> -->`. An **uncaptioned** figure has no id to
protect and no number to write, but since #421 it is a finding of its
own (`FigureNoCaption`) rather than an accepted state; the fix is a
caption line, and it is the reader's gain, not a tidy-up.

What a revision can still break for a captioned one is the id: deleting
a figure something still refers to, or copying a figure into another
section along with its id. Both are reported by the prose check
(`FigureUnreferenced`, `FigureUnknownRef`, `FigureDuplicateId`); read
those rather than eyeballing the markers.

## 5. An equation renumbers itself; its id does not

Issue 457 gives the same contract to a *numbered* equation, over the
`<!-- equation: id -->` marker `docs/WRITING-STANDARDS.md` §12 has the
renderer resolve: a literal "Equation 3" in the prose is the defect, and
the fix is an inline `<!-- equationref: <id> -->`.

Unlike a table or a captioned figure, most equations in a draft are
correctly **unnumbered**: §12's rule is standalone, final-of-a-derivation,
or reused elsewhere, not every displayed equation. Deciding whether an
equation you are revising now meets that bar is a judgment call, not one
`draft style` can make for you (§9 has no mechanical proxy for it).

What a revision can still break for an already-numbered one is the id:
deleting an equation something still refers to, or copying a numbered
equation into another section along with its id. Both are reported by
the prose check (`EquationUnreferenced`, `EquationUnknownRef`,
`EquationDuplicateId`); read those rather than eyeballing the markers.
An unattached `<!-- equation: id -->` left behind by a deleted or
reflowed `<!-- math -->` block is `EquationOrphanMarker`: delete the
stray marker, the conservative repair, rather than guessing which block
it meant.

## 6. Keep `math.md` in step with the prose

Only if the draft has one. `math.md` maps the draft's ASCII to the LaTeX
it renders as (`docs/WRITING-STANDARDS.md` §12), keyed on the exact span
text, so any edit that adds, removes or *rewords* a quantity desyncs it.
Add a row for a new one, drop the row for a deleted one, and change the
key when you reword one. `render` reports what you missed -- `[math]`
warnings for a gap or an orphan, and a hard failure for a
`<!-- math -->` marker it cannot resolve -- so render and read its
output rather than trusting this list.

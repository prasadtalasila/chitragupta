# ✍ Hand-drawn figures: correcting or adding a figure on paper

Status: **how-to.**

**Written for** an author who would rather mark a figure with a pen
than describe the change in words: a correction on a printed page, a
figure redrawn by hand, or a sketch of a figure the draft does not have
yet. **Assumed:** you have a draft under `content/drafts/` in a topic
directory of its own, and an agent whose model can view images.
**Not covered here:** what the `figure-drawer` skill does once it knows
what to draw, which is [FIGURE-DRAWER.md](FIGURE-DRAWER.md); what a
good figure looks like, which is [TIKZ-STYLE.md](TIKZ-STYLE.md); and
the two-file contract every figure follows, which is
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10.

## 🧭 Table of contents

- [Three things a photo can be](#-three-things-a-photo-can-be)
- [What to hand over](#-what-to-hand-over)
- [The read-back](#-the-read-back)
- [Correcting a printed figure](#-correcting-a-printed-figure)
- [Redrawing a figure by hand](#-redrawing-a-figure-by-hand)
- [Adding a new figure from a sketch](#-adding-a-new-figure-from-a-sketch)
- [Marking a page so it reads the first time](#-marking-a-page-so-it-reads-the-first-time)
- [What it never does](#-what-it-never-does)
- [When something goes wrong](#-when-something-goes-wrong)

## 🗂 Three things a photo can be

| You photograph | It is treated as | What changes in the draft |
| --- | --- | --- |
| a printed figure of the draft with pen marks on it | a correction | the existing `figures/<name>.tex` and `.txt`, only where you marked |
| a figure of the draft redrawn by hand | a redraw | the same pair, rebuilt under the same name |
| a sketch of a figure the draft does not have | a new figure | a new pair, a marker and a caption in the draft |

A photograph or a scan both work. The image is an instruction, like a
sentence typed in chat. It is never copied into the draft.

## 📨 What to hand over

Give the image and say which draft it belongs to. For a correction or a
redraw that is enough, as long as the page shows which figure it is:

```text
content/drafts/dt/architecture.md: the photo in proofs/fig-4-5.jpg
has my corrections to the three-layer figure.
```

A new figure needs three more things: where in the draft it goes, what
it shows in one sentence, and what any abbreviation in it stands for.

```text
Add the sketch in proofs/stack.jpg as a new figure in section 4.2 of
content/drafts/dt/architecture.md. It shows the three layers a twin
sits between. TS is the twin system and AS is the asset system.
```

You never name a skill. `draft-reviser` takes the request, hands the
drawing to `figure-drawer`, and takes the draft back afterwards.

## 🔁 The read-back

Before any file changes, you get your marks read back, one row per
mark:

| Field | What it holds |
| --- | --- |
| `now:` | the label or arrow as the figure has it today, or `none` for something you added |
| `mark:` | what you drew or wrote, transcribed as written |
| `edit:` | what will be done: reword, delete, add a box, add an arrow, add a group, move |

For a redraw or a new sketch the rows are its boxes, arrows and groups.

Some marks cannot be tied to an instruction. They go on a separate
**unclear list**, each with a question:

- a word beside the figure with no arrow or strike joining it to
  anything;
- a bracket, an underline or a wavy line with no word saying what to do;
- a word written and then struck through;
- an abbreviation the draft does not define;
- handwriting that reads two ways.

A proof page carries notes to yourself as well as corrections, and the
two look alike. So an unclear mark is never applied on a guess.

What happens next depends on that list:

- **Nothing unclear:** the rows are posted and the edit goes ahead.
- **Anything unclear:** nothing is applied until you answer, the clear
  rows included, because one answer often changes the row beside it.
- **Nobody to ask** (an unattended run): the clear rows are applied and
  the unclear list comes back unapplied.

The rows you confirmed are recorded in the dossier's `steering.md`, as
the instruction that prompted the change.

## 🖊 Correcting a printed figure

1. Print the page and mark the figure.
2. Photograph or scan it and hand it over with the draft's path.
3. Read the read-back and answer any question on the unclear list.
4. The existing pair is edited in place. Only what you marked changes:
   a label you did not touch keeps its wording, and the layout stays.
5. The figure is checked and rendered, and the render is compared with
   your photo row by row.
6. A reworded label is carried into the rest of the draft. If you
   renamed a box, the caption, the prose, the glossary and `math.md`
   are brought into line with it.
7. The change is logged in `revisions.md`, and the draft is gated and
   rendered.

If your marks add so much that the figure no longer fits its layout, or
it now argues something else, you are told so and it is handled as a
redraw.

## 🔄 Redrawing a figure by hand

Draw the whole figure the way you want it and photograph the sheet.
Write "Fig N" on it so the pair it replaces is not in doubt.

Your sketch supplies the boxes, the arrows and the grouping. It does
not supply the positions: you drew to fit the paper, and the figure has
to fit the page. The layout comes from the house scaffolds
([FIGURE-DRAWER.md](FIGURE-DRAWER.md#-the-eleven-layouts)), keeping your
reading direction and your groups.

The existing pair is edited under its own name, so the draft's marker
and every reference to the figure still resolve. Anything the old figure
had that your sketch leaves out comes back as a question, not as a
silent deletion.

## ➕ Adding a new figure from a sketch

1. Sketch the figure and photograph it. Keep one figure to a photo.
2. Hand it over with the draft, the section, a one-sentence statement
   of what it shows, and the meaning of any abbreviation.
3. Read the read-back. Here it lists every box, arrow and group.
4. A new pair is written beside the draft: `figures/<name>.tex` in TikZ
   and `figures/<name>.txt` in ASCII.
5. The draft gets `<!-- figure: figures/<name> -->` on a line of its
   own with a caption below it, and `<!-- figureref: <name> -->` where
   the prose points at the figure. A thesis chapter gets a `figure`
   float instead ([FIGURE-DRAWER.md](FIGURE-DRAWER.md#-what-you-get)).
   Nobody writes "Figure 3" by hand; the renderer numbers it.
6. The change is logged in `revisions.md`, and the draft is gated and
   rendered. You see the page with the figure on it.

The skill may suggest dropping or merging a box. On a sketch of yours
that is a question to you, never a cut it makes on its own.

## 💡 Marking a page so it reads the first time

- **Name the figure.** Leave the printed caption in the photo, or write
  "Fig N" on the sheet.
- **Strike and replace.** Strike what goes, and write what replaces it
  beside the strike.
- **Tie a new word to its place.** Draw an arrow from it to the box or
  the arrow it belongs to.
- **Keep notes to yourself apart.** Circle them, or keep them off the
  page.
- **Spell out abbreviations** the draft has not defined yet.
- **Write the way the figure reads.** A label is set as you wrote it,
  apart from the capitalisation the figure already uses.

## 🚫 What it never does

- It never copies or traces the photo into the draft.
- It never changes a label you did not mark.
- It never applies a mark it could not tie to an instruction.
- It never redraws a figure from a paper or a book. A printed figure
  that is not one of the draft's own is treated as a source figure,
  which may be looked at and never reproduced
  ([WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10).
- It never puts a citekey inside a figure file.

## 🩹 When something goes wrong

| What you see | Why | What to do |
| --- | --- | --- |
| "I cannot view images" | the agent's model has no vision | type the corrections, or use a model that can view images |
| It asks which figure the photo is | no caption or "Fig N" in the photo, or two figures share the labels it could read | name the figure |
| A long unclear list | notes and corrections are mixed on the page | answer the questions; next time, circle the notes |
| The redrawn figure is not laid out like your sketch | positions come from the house layout | say what must sit where, and why, as a follow-up revision |
| It asks to move the draft first | a flat draft has no topic directory to hold `figures/` | agree to the move, or drop the figure |
| It refuses a figure in a deep-research report | that genre takes no figures | put the figure in another draft |

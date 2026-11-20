# figure-drawer: a figure marked up by hand

Read this when the person gives you a photo or a scan instead of
words: a printed figure with pen corrections on it, a figure redrawn by
hand, or a hand sketch of a new one. Read it before step 1 of the
procedure in `SKILL.md`. Paths here are from the project root.

The image is an instruction, like a sentence in chat. It is never a
figure: it is not copied into `figures/`, not embedded in the draft and
not traced.

## 1. Open it and find its pair

Open each image with the tool your harness reads files with. If you
cannot view an image, stop: say so, and ask the person to type the
corrections. Never work from the file's name alone.

Say which of three things each image is:

| The image shows | It is | Go to |
| --- | --- | --- |
| a printed figure of this draft with pen marks on it | a correction | §2, then §3 |
| an existing figure of this draft redrawn by hand | a redraw | §2, then §4 |
| a sketch that matches no figure of this draft | a new figure | §2, then §4 |

Find the pair a correction or a redraw belongs to before reading the
marks. A printed caption, or a "Fig N" the person wrote, names the Nth
figure marker in the draft. Without one, search the labels you can read
in `content/drafts/<topic>/figures/*.txt`. One pair must match. If two
match or none does, ask which figure it is.

A printed figure that matches no pair of this draft may be someone
else's. Ask where it is from. If it is from a paper or a book, it is a
source figure, and `.claude/skills/figure-drawer/references/figures.md`
§5 applies: look, never redraw.

## 2. Read the marks back before editing

Write one row for each mark, in chat, before any file changes:

| Field | What it holds |
| --- | --- |
| `now:` | the label or edge as the pair has it, copied from `figures/<name>.txt`; `none` for an addition |
| `mark:` | what the person drew or wrote, transcribed as written |
| `edit:` | one of: reword, delete, add node, add edge (from, to, direction, label), add container, move |

For a redraw or a new sketch the rows are its nodes, its edges and its
containers, and `now:` is `none`.

Transcribe; never tidy. A word that is not in the figure's labels or in
`scope.md`'s glossary stays as you read it and goes on the unclear
list. Do not swap it for the nearest known term.

A mark goes on the **unclear list**, with a question, when it is any of:

- a word or symbol beside the figure with no arrow or strike tying it
  to a node or an edge;
- a bracket, an underline or a wavy line with no word saying what to do;
- a word written and then struck through;
- an abbreviation the draft does not define;
- handwriting you can read two ways. Give both readings.

A person writes notes to themself on a proof. An unclear mark is as
likely to be a note as an instruction, so it is never applied on a
guess.

Then:

- **No unclear rows:** post the rows and carry on.
- **Any unclear row:** post the rows and the questions, and wait for the
  answers. Apply nothing until they come, the clear rows included: one
  answer often changes a clear row beside it.
- **Nobody to ask** (an unattended run): apply the clear rows only, and
  return the unclear list unapplied.

The read-back is not done until the rows are in chat. The caller records
them, as confirmed, in `steering.md`: they are the instruction that
prompted the change.

## 3. A correction: edit the pair in place

Skip steps 1 to 4 of the procedure. The figure has a layout and a
scaffold already, and `figure new` never overwrites a pair.

- Change what the rows say and nothing else. A label the person did not
  mark keeps its wording, even one you would write differently.
- Keep the layout: leave `% cg-layout:` and the house block alone, and
  place an added node relative to its neighbours, as step 5 says.
- Make every change in `figures/<name>.txt` too (step 6).
- Then run steps 7 and 8. Read the look PNG against the photo, row by
  row: every row shows, and nothing else moved.

If the rows add so much that `figure check` reports the layout's
reference ranges exceeded, or the figure now argues something else,
that is a redraw: say so and go to §4.

A reworded label is rarely only in the figure. Return each old and new
wording to the caller. The caption, the prose, `scope.md`'s glossary
and `math.md` are the caller's to bring into line, never yours.

## 4. A redraw or a new sketch: take the content, not the positions

A hand sketch says what the nodes are, what joins them and what groups
them. It does not say where they sit: the person drew to fit the paper.
Run the procedure from step 2, with the rows from §2 as the content.

- **The layout comes from the pattern**, as for any figure. Keep the
  sketch's reading direction and its grouping; let the scaffold set the
  spacing.
- **The taste gate proposes; it does not cut.** The person drew each
  node on purpose. A trim the gate suggests goes back as a question,
  beside the unclear list.
- **A redraw replaces a pair.** Edit the existing `figures/<name>.tex`
  and `.txt` under their own names, so the draft's marker and every
  `figureref` still resolve. Start a second scaffold only if the layout
  changes, and then under the same name, once the person agrees to lose
  the old picture.
- **A new sketch needs a place.** If the person did not say which draft
  and which section it belongs to, ask before drawing.

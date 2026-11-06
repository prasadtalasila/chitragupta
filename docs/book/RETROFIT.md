# 🛠 Retrofitting a book drafted before this track

Status: **workflow**, part of [Write a book](../WRITE-A-BOOK.md).

**Written for** someone whose chapters already exist, written without
an outline. **Assumed:** the chapters sit in one directory under
`content/drafts/`. **Not covered here:** the steps after the outline is
signed, which are the same as for any book ([step 3 on](CHAPTERS.md)).

A book whose chapters already exist can be brought under the track
without rewriting a word. You derive the outline from the book:

1. Take the parts and their chapter numbering from whatever table of
   contents the book already has.
2. Take each chapter's title from that chapter's own `#` heading (what
   the prose says, not the table of contents' paraphrase).
3. Make each unit id the chapter's **filename stem**, so
   `unit accept` finds the prose where it already lives.

One chapter is then one unit: a `####` section whose id is the filename,
under a `###` chapter entry that carries the same title. The chapter
heading stays inside the unit file, so `book.tex` emits `\part` and
`\input` and lets the fragment's own `\chapter{}` supply the title;
emitting one here as well would print every title twice.

Say in the spec that the outline was retrofitted, and from what. A
sign-off records a person's decision; one recorded on an outline nobody
has read is a record of the wrong thing.

A retrofitted book can take front and back matter like any other: add
`## Front matter {#front}` and `## Back matter {#back}` to its outline
([the reserved parts](OUTLINE.md#-front-matter-appendices-and-back-matter)).
Until it does, it assembles as it always has.

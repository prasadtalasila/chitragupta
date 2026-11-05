# Book assets

The two files `python -m chitragupta.draft spec init` copies into a new
book (#1137). Each is copied once and never overwritten: from then on it
is the author's.

## `preface.md`

Copied to `content/drafts/<book>/preface.md`, the unit the default
outline's `### Preface {#preface}` names. A preface is the author's own
voice, so no genre skill drafts it; the comments say what it is for and
how to accept it.

## `copyright.tex`

Copied to `content/specs/<book>/copyright.tex`. `book-assembler` copies
it beside `book.tex` and `\input`s it right after `\maketitle`; with no
file there is no copyright page. It defaults to "All rights reserved".
`spec sign` replaces the `<year>` placeholder once, at the first
sign-off. `\BookTitle`, `\BookAuthor` and `\BuildLine` are defined by the
assembled `book.tex`, not here.

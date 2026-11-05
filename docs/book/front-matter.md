# 📜 Front matter: the preface and the copyright page

Status: **workflow**, part of [Write a book](../WRITE-A-BOOK.md).

**Written for** an author setting up the pages before chapter 1.
**Assumed:** an outline from `spec init`
([step 1](outline.md)). **Not covered here:** the Glossary, List of
Symbols and the lists of figures and tables, which are
[back matter](back-matter.md) by default.

Before chapter 1 a printed book carries, in order:

| Page | Where it comes from | Who writes it |
| --- | --- | --- |
| title page | the outline's `#` title and `- author:` line | nobody: it is generated |
| copyright page | `content/specs/<book>/copyright.tex` | you |
| table of contents | the book | nobody: it is generated |
| the front-matter chapters (a preface, "How to use this book", acknowledgements) | `## Front matter {#front}` in the outline | you |

Front-matter pages are numbered i, ii, iii, so chapter 1 still starts
on page 1, and their chapters carry no chapter number.

## ✍ The preface

`spec init` puts it in the outline and writes a template for it:

```markdown
## Front matter {#front}

### Preface {#preface}

Why this book exists and who it is for. You write this page yourself.
```

The template is `content/drafts/<book>/preface.md`: a `# Preface`
heading and a comment saying what a preface usually covers. **No skill
drafts it**, because it is the one page in the book written in your own
voice rather than grounded in the corpus. Write it, then accept it like
any chapter:

```bash
chitragupta draft unit accept content/drafts/twins preface
```

`accept` runs the citation gate, which a page citing nothing passes, and
it needs no dossier. If the preface does cite a paper, the citekey is
held to the same rule as every other chapter's: it must be in your
`.bib` and in the ledger.

**More front-matter pages** are more chapters under `{#front}`, each a
file you write and accept the same way:

```markdown
## Front matter {#front}

### Preface {#preface}

### How to use this book {#how-to-use}

### Acknowledgements {#acknowledgements}
```

They print in outline order, after the table of contents.

**No preface?** Delete the `### Preface {#preface}` line from the
outline, and the whole `## Front matter {#front}` part if nothing is
left in it. Re-sign the outline. `preface.md` stays on disk and
`unit status` names it if you had accepted it
([changing the outline](changing-the-outline.md)).

**Lists in the front.** The List of Figures and List of Tables sit in
the back matter by default. To print them after the table of contents
instead, move their lines under `{#front}`:

```markdown
## Front matter {#front}

### List of Figures {#figures}

### List of Tables {#tables}

### Preface {#preface}
```

## 📄 The copyright page

`spec init` copies a template to `content/specs/<book>/copyright.tex`.
The file is yours: edit it freely, and the assembler prints it as you
left it, on the back of the title page. Delete the file and the book has
no copyright page.

By default it prints:

```text
Composable Twins

© 2026 Prasad Talasila. All rights reserved.

No part of this book may be reproduced, stored in a retrieval system or
transmitted in any form or by any means without the prior written
permission of the author.

Built 2026-11-05 · outline 7cfc6678f261 · chitragupta 6.164.0
```

Each part comes from one place:

| On the page | In the file | Comes from |
| --- | --- | --- |
| the title | `\BookTitle` | the outline's `#` heading |
| the author | `\BookAuthor` | the outline's `- author:` line |
| the year | a plain number | written once, by the first `spec sign` |
| the licence | the two sentences after the year | the template; yours to change |
| the build line | `\BuildLine` | the assembler, on every build |

**The title and author live in the outline**, so the title page and the
copyright page cannot disagree. Set the author with
`spec init --author "Prasad Talasila"`, or by adding the line yourself
near the top of `spec.md`, before the first `##` heading:

```markdown
# Composable Twins

- author: Prasad Talasila
```

`spec show` prints it under the title. Changing it changes the outline,
so `spec status` asks you to sign again; no chapter's acceptance is
affected, because the line belongs to no chapter. With no `- author:`
line, the assembler asks you for a name when it composes the book and
never invents one.

**The year is written once.** The template holds a `<year>` placeholder,
and the first `spec sign` replaces it with the current year
([sign-off](sign-off.md)). From then on the file is never touched by any
command: a copyright year is the year of first publication, so a book
rebuilt in 2027 still says 2026 until you change it.

**"All rights reserved" is the default.** It means nobody may copy the
book without your permission; you hold the copyright automatically, and
the notice tells readers so. To publish under a Creative Commons licence
instead, replace the two licence sentences; the template carries the CC
BY 4.0 wording as a comment to start from:

```latex
\noindent\copyright\ 2026 \BookAuthor. This work is licensed under
the Creative Commons Attribution 4.0 International licence (CC BY
4.0), https://creativecommons.org/licenses/by/4.0/.
```

Either way, the notice covers your own words. A figure or passage
adapted from someone else's work keeps that work's licence, and needs
the credit that licence asks for, in the chapter that uses it.

**The build line** says which build a printed copy came from: the date
the book was assembled, the digest of the outline it was assembled from
(the one `spec status` prints), and the pipeline version. Two copies with
the same line were built from the same approved outline by the same
pipeline. Delete `\BuildLine` from the file if you do not want it
printed.

**Do not put the copyright page in the outline.** It is not a chapter:
it has no heading and no line in the table of contents, which is why it
is a LaTeX file beside the outline, the way
[`preamble.tex`](assemble.md#-step-7-build-the-pdf) is, rather than an
entry in it. Editing it needs no re-sign.

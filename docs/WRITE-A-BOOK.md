# ✍ Write a book, start to finish

Status: **tutorial.**

**Written for** someone drafting a document larger than a chapter with
this pipeline. **Assumed:** nothing about this pipeline, though a book is
the one genre where doing a single chapter first
([a textbook chapter](WRITE-A-TEXTBOOK-CHAPTER.md) is the usual one) will
save you a false start. [AGENTS.md](../AGENTS.md) has the drafting
layer's contract and [ARCHITECTURE.md](ARCHITECTURE.md) the four layers,
but you do not need either to follow the steps below.

Sister tutorials, for the chapters this book is made of:
[a survey](WRITE-A-SURVEY.md),
[a thesis chapter](WRITE-A-THESIS-CHAPTER.md),
[a textbook chapter](WRITE-A-TEXTBOOK-CHAPTER.md),
[a tutorial](WRITE-A-TUTORIAL.md),
[a deep-research report](WRITE-A-DEEP-RESEARCH-REPORT.md).

A book is a signed outline, one authored chapter per `{#id}`, an
acceptance record per chapter, three derived registries, and an assembly
step, with **two human sign-offs**: one before any prose is generated
and one before the book is called finished. Neither sign-off can be
automated.

This page is the map. The steps themselves are on their own pages, in
the order you run them, each with a real book's output; the workflows
cover the parts of a book that are not chapters; the design notes give
the reasoning, and each step links to the part it rests on.

## 🗺 The pages of this tutorial

**The steps**, in the order you run them:

| Page | Steps | What you do there |
| --- | --- | --- |
| [Plan the outline](book/OUTLINE.md) | 1 | write `spec.md`: parts, chapters, sections, and the front and back matter |
| [Sign the outline off](book/SIGN-OFF.md) | 2 | the first human gate |
| [Write and accept the chapters](book/CHAPTERS.md) | 3, 3b, 4 | hand each chapter to its author or genre skill, then accept it |
| [Build the registries](book/REGISTRIES.md) | 5 | terminology, claims, cross-references, the Glossary and List of Symbols |
| [Assemble, build and sign off the book](book/ASSEMBLE.md) | 6, 7, 7b, 8 | `book.tex`, the PDF, the one book-level review aid, the second human gate |

**The workflows**, for the parts of a book that are not ordinary
chapters, and for the book changing under you:

| Page | When you need it |
| --- | --- |
| [Front matter: preface and copyright page](book/FRONT-MATTER.md) | writing the preface, setting the author and licence, the build line |
| [Appendices](book/APPENDICES.md) | material numbered A, B, ... after the last chapter |
| [Back matter: glossary, symbols, lists and the index](book/BACK-MATTER.md) | which reference pages print, in what order, and how to drop one |
| [The index](book/BOOK-INDEX.md) | how the index is built from the glossary, and how `index.toml` and its report tune it |
| [Changing the outline after sign-off](book/CHANGING-THE-OUTLINE.md) | adding, removing or moving a chapter once prose exists |
| [Retrofitting a book drafted before this track](book/RETROFIT.md) | chapters that already exist, written without an outline |

**The reasoning** behind all of it is on one page:
[Design notes](book/DESIGN-NOTES.md).

## 🔑 The constraint everything here answers

> A book does not fit in a context window, and generation quality
> degrades long before the limit.

So cross-chapter consistency cannot live in a model's memory of an
earlier call. It lives in explicit on-disk artefacts, injected as
relevant excerpts into each unit's generation, and checked
deterministically afterwards, the same two-plane discipline as the rest
of the project: the artefacts are written by deterministic
passes, never by an LLM writing to the corpus plane.

There are exactly two human sign-offs: **the outline** and **the
finished book**. No automated check verifies that an argument is good, only that
it is grounded, consistent and complete. Everything between the two
sign-offs is mechanical.

## 🔭 The steps, at a glance

| Step | Command | Who runs it | Page |
| --- | --- | --- | --- |
| 1 | `spec init`, then edit `spec.md` | you | [outline](book/OUTLINE.md) |
| 2 | `spec sign` | **you, and only you** | [sign-off](book/SIGN-OFF.md) |
| 3 | `spec seed`, then fill in each chapter's `outline.md` | you | [chapters](book/CHAPTERS.md) |
| 3b | `unit contract`, then a genre skill writes the chapter (you write the preface) | you, then skill | [chapters](book/CHAPTERS.md) |
| 4 | `spec align`, then `unit accept` | you, per unit | [chapters](book/CHAPTERS.md) |
| 5 | `registry build`, `registry check` | you or the assembler | [registries](book/REGISTRIES.md) |
| 6 | the `book-assembler` skill composes `book.tex` | skill | [assemble](book/ASSEMBLE.md) |
| 7 | `lualatex`, `bibtexu`, `lualatex` x2; with an index, `registry index` and one more `lualatex` | you or the assembler | [assemble](book/ASSEMBLE.md) |
| 7b | `review union` | you | [assemble](book/ASSEMBLE.md) |
| 8 | read it | **you, and only you** | [assemble](book/ASSEMBLE.md) |

Steps 3b and 4 repeat per chapter. Steps 5 to 7 are what
`.claude/skills/book-assembler/` does in one run.

A real spec partway through this ladder is committed: the sample project
holds a signed two-chapter outline
([`spec.md`](examples/sample-project/content/specs/twin-basics/spec.md)),
its sign-off record
([`signoff.md`](examples/sample-project/content/specs/twin-basics/signoff.md)),
and one accepted unit
([`units/ch-staleness.json`](examples/sample-project/content/specs/twin-basics/units/ch-staleness.json))
whose authored chapter sits at
[`content/drafts/twin-basics/ch-staleness.md`](examples/sample-project/content/drafts/twin-basics/ch-staleness.md).
The second chapter is marked `unwritten`, because a spec is allowed to be
ahead of its book and the registries report that.

## 🔧 Before you start

You need a synced corpus, because every unit is grounded in it:

```bash
chitragupta corpus ledger        # non-empty, items `parsed`
```

> Every command on this page also works as
> `python -m chitragupta.<layer> ...`: `python -m chitragupta.draft
> spec init` is the same as `chitragupta draft spec init`. Use whichever
> your install gives you; the console script is used throughout below.

A book lives in one directory under `content/drafts/`, one file per
**chapter**, named for that chapter's own `{#id}`. Nothing needs to exist
there yet; the outline comes first, and the prose is written into it
afterwards:

```text
content/drafts/twins/<chapter-id>.md  the book's chapters land here
content/drafts/twins/preface.md       your preface, from a template -- step 1
content/specs/twins/spec.md           the outline -- step 1
content/specs/twins/copyright.tex     your copyright page, from a template -- step 1
content/specs/twins/signoff.md        your approval -- step 2
content/specs/twins/units/*.json      one acceptance record -- step 4
content/specs/twins/registries/*.md   terminology, claims, xrefs -- step 5
content/specs/twins/preamble.tex      your own LaTeX, optional -- step 6
content/rendered/twins/<id>.tex       each chapter as a fragment -- step 6
content/rendered/twins/book.tex       the assembled book -- step 6
content/rendered/twins/book.md        the same structure in Markdown
content/rendered/twins/book.pdf       the built book -- step 7
```

**`content/drafts/twins/` holds only chapters a person wrote.**
Everything the assembly produces is output and lands under
`content/rendered/twins/`, which is where a chapter's own render goes
anyway, so the fragments arrive there without being told to, and
`book.tex` is composed beside them.

`content/specs/` mirrors the book's own directory under `content/drafts/`,
the same rule `content/dossiers/`, `content/rendered/` and
`content/review/` follow, read one level up. Those mirror a single
*draft*, so they carry the draft's parent directory; a book is a
*directory* of drafts, so its own path carries over. Everything under
`content/` is gitignored: it is your data, not the pipeline's.

## ➡ Where to start

With a synced corpus, go to [Plan the outline](book/OUTLINE.md). If the
chapters already exist, start with
[Retrofitting a book drafted before this track](book/RETROFIT.md)
instead.

# 📐 Plan the outline

Status: **tutorial**, step 1 of [Write a book](../WRITE-A-BOOK.md).

**Written for** someone starting a book with this pipeline. **Assumed:**
a synced corpus ([before you start](../WRITE-A-BOOK.md#-before-you-start)).
**Not covered here:** writing the chapters; that is
[step 3](chapters.md).

## ▶ Step 1: write the outline

```bash
chitragupta draft spec init content/drafts/twins --title "Composable Twins" --author "Prasad Talasila"
```

```text
Wrote content/specs/twins/spec.md. Edit it, then approve it with `python -m chitragupta.draft spec sign content/drafts/twins`.
Wrote content/drafts/twins/preface.md: the preface is yours to write.
Wrote content/specs/twins/copyright.tex: the copyright page is yours to edit.
```

That writes three files, and never overwrites one that already exists:

| File | What it is | Whose |
| --- | --- | --- |
| `content/specs/twins/spec.md` | the outline skeleton, with a front and back matter already in it ([below](#-front-matter-appendices-and-back-matter)) | yours to edit, then sign |
| `content/drafts/twins/preface.md` | a preface template: a `# Preface` heading and a comment saying what goes there | yours to write ([front matter](front-matter.md)) |
| `content/specs/twins/copyright.tex` | the copyright page, "All rights reserved" by default | yours to edit ([front matter](front-matter.md#-the-copyright-page)) |

`--author` is optional. It writes an `- author: Prasad Talasila` line at
the top of the outline, which the title page and the copyright page
both print; without it, add the line by hand, or the assembler asks you
for a name when it composes the book.

Edit the outline into the book you mean to write,
planned top-down and generated bottom-up. Four heading levels, and no more:

| Markdown | Is | Generates |
| --- | --- | --- |
| `# Title` | the book | nothing |
| `## Part {#part-i}` | a part | nothing |
| `### Chapter {#ch-1}` | a **chapter** | one authored document, and what `unit accept` records |
| `#### Section {#sec-1}` | a section | one heading inside it: structure, never a file |

Nothing sits below a section: a level deeper would describe structure the
outline has no business owning. Text beneath a heading is that heading's
**brief**: what it must establish, and what it leaves to another. Text
before the first heading belongs to nothing and is never handed to a
generator; it is the preamble for whoever opens the file.

**A chapter is one authored document, and its sections are the headings
inside it.** The outline stops at the sections of a chapter; the
sub-headings an author writes underneath are theirs, not the spec's.
Choosing the chapter over the section is what lets `spec align` mean
anything ([why](design-notes.md#-why-a-chapter-is-the-authored-document)).

Every part, chapter and section needs an explicit `{#id}`, and a heading
without one is refused rather than guessed at
([why](design-notes.md#-why-an-id-is-required-on-every-heading)).

An id also becomes a filename: `unit accept` writes
`content/specs/<book>/units/<id>.json`. It is held to the same rule a
citekey is, therefore: no `/ \ : * ? " < > |`, no control character,
not `.` or `..`, and not a name Windows reserves. An id that breaks it
is named as a parse problem and never silently rewritten into one that
does.

A worked `spec.md`, short enough to read whole and showing all four
levels, the briefs, and the preamble that belongs to nobody. The sample
output in steps 1 to 4 is what the commands print for this outline,
grounded in the sample project's corpus. A longer version, with a third
part, is at
[`examples/dossiers/book/spec.md`](../examples/dossiers/book/spec.md):

```markdown
# Composable Twins {#book}

This outline is signed before any prose is generated. Text up here is
the preamble: it belongs to no heading, is never handed to a generator,
and exists for whoever opens the file next. Audience: practising
engineers who have built one twin and are now asked for five.

## Part I: Foundations {#part-i}

### What a twin is, and is not {#ch-what}

Establish the vocabulary the rest of the book leans on, and settle the
twin/shadow distinction early -- later chapters assume it. Must not
drift into architecture; that is Part II's job.

#### The model half {#sec-model}

What the model must reproduce, and the fidelity question stated but not
answered. The answer is `ch-fidelity`.

#### The data half {#sec-data}

Synchronisation, sampling and staleness, as vocabulary only.

### What a twin costs {#ch-cost}

The honest chapter. Build cost, maintenance cost, and the cost of a
twin nobody trusts. Leans on `ch-what`'s vocabulary and nothing else.

## Part II: Building one {#part-ii}

### Choosing fidelity {#ch-fidelity}

Answers the question `sec-model` raised. This is the book's technical
core and the chapter most likely to need two passes.

#### Fidelity against a decision {#sec-decision}

#### When more fidelity makes things worse {#sec-worse}

### Keeping it in step {#ch-sync}

Staleness, dropped links, and what an operator should see when the twin
is behind. Cross-references `sec-data` for the vocabulary.
```

Three things that example shows:

- **The brief is the text under a heading**, in your own words. It says
  what the chapter must establish *and what it must leave to another*,
  which is what stops two chapters writing the same section.
- **Ids are stable names, not numbers.** `ch-fidelity`, not `ch-3`. A
  chapter that moves keeps its id, and every `\cref{ch-fidelity}` in
  every other chapter still resolves.
- **Cross-references are declared in the brief** ("answers the question
  `sec-model` raised"), which is what makes step 5's registry check able
  to tell you when one dangles.

Check what you wrote:

```bash
chitragupta draft spec show content/drafts/twins
```

```text
Composable Twins
  [part-i] Part I: Foundations
    [ch-what] What a twin is, and is not
      [sec-model] The model half
      [sec-data] The data half
    [ch-cost] What a twin costs
  [part-ii] Part II: Building one
    [ch-fidelity] Choosing fidelity
      [sec-decision] Fidelity against a decision
      [sec-worse] When more fidelity makes things worse
    [ch-sync] Keeping it in step
```

`spec show`, `spec sign` and `spec status` all refuse a spec that does
not parse, and print **every** problem at once, so fixing an outline
takes one round trip instead of one per missing id.

## 📚 Front matter, appendices and back matter

The skeleton `spec init` writes already has the parts of a book that are
not chapters:

```markdown
# Composable Twins

<!-- ... what the outline is, and how to approve it ... -->

- author: Prasad Talasila
- reader: who this book is for, and what they already know
- scope: what it covers, and what it deliberately leaves out

## Front matter {#front}

### Preface {#preface}

Why this book exists and who it is for. You write this page yourself.

## Part I {#part-i}

### Chapter 1 {#ch-1}

#### First section {#sec-1}

What this section must establish, and what it leaves to another.

## Back matter {#back}

### Glossary {#glossary}

### List of Symbols {#symbols}

### List of Figures {#figures}

### List of Tables {#tables}
```

Three part ids are **reserved**. Each is optional, and none prints a
"Part" page:

| Part | Must sit | In the book |
| --- | --- | --- |
| `## ... {#front}` | first, before every other part | after the table of contents, pages numbered i, ii, iii; its chapters are unnumbered |
| `## ... {#appendices}` | after every ordinary part, before `{#back}` | after the last chapter, numbered Appendix A, B, ... |
| `## ... {#back}` | last, after every other part | after the appendices, unnumbered; the bibliography always comes after it |

The heading text is yours (`## Before the book {#front}` is fine); the
id is what the parser and the assembler read.

Five chapter ids are reserved too: `{#glossary}`, `{#symbols}`,
`{#figures}`, `{#tables}` and `{#index}` are **generated pages**. You
write no file for them, `unit status` does not list them, and they take
no `####` sections. They may sit only in `{#front}` or `{#back}`, and
`{#index}` only in `{#back}` ([the index](book-index.md)).

`spec show`, `spec sign` and `spec status` refuse an outline that breaks
these rules, with every problem named at once, like any other parse
problem:

- `{#front}` is not the first part, or `{#back}` is not the last;
- `{#appendices}` is not after every ordinary part and before `{#back}`;
- a generated page is somewhere other than a section-less chapter of
  `{#front}` or `{#back}`;
- `{#index}` is anywhere but `{#back}`;
- a reserved id is used at the wrong heading level (`### Intro {#front}`).

An outline without any of them (every outline written before this
existed) assembles as it always did: no front matter, and the Glossary
and List of Symbols at the end, before the bibliography.

What each part holds, and how you write it:

| Workflow | Page |
| --- | --- |
| the preface, the author line, the copyright page and its build line | [Front matter](front-matter.md) |
| appendices | [Appendices](appendices.md) |
| the Glossary, List of Symbols, List of Figures, List of Tables | [Back matter](back-matter.md) |

Next: [sign the outline off](sign-off.md).

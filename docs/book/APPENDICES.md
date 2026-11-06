# 📎 Appendices

Status: **workflow**, part of [Write a book](../WRITE-A-BOOK.md).

**Written for** an author with material that supports the chapters but
would interrupt them: an installation guide, a proof, a data set's
description. **Assumed:** a working outline ([step 1](OUTLINE.md)).
**Not covered here:** reference pages such as the glossary, which are
[back matter](BACK-MATTER.md), not appendices.

## 🧭 Where appendices go

After the last chapter and before the back matter. That is the order
the *Chicago Manual of Style* and BCcampus's textbook outline both give:
an appendix is still the book's content, moved out of a chapter so the
chapter reads straight through, while the glossary, the lists and the
bibliography are reference pages about the whole book and come after
it.

## 📝 In the outline

Appendices are chapters of one reserved part, `{#appendices}`, which
sits after every ordinary part and before `{#back}`:

```markdown
## Part III: Living with one {#part-iii}

### Where this goes next {#ch-next}

## Appendices {#appendices}

### Installing the toolchain {#app-install}

What a reader needs installed to run chapter 4's examples.

### Proofs {#app-proofs}

#### The fidelity bound {#sec-bound}

#### The staleness bound {#sec-stale-bound}

## Back matter {#back}
```

An appendix is a chapter in every respect but its number: it has a
brief, it may declare sections, and with no sections it is a unit by
itself. `spec init` writes no `{#appendices}` part, since most books
need none; add it when you need it. Put it anywhere else, before an
ordinary part or after `{#back}`, and `spec show` names the problem.

## ✍ Writing and accepting one

Exactly as for any chapter ([steps 3 to 4](CHAPTERS.md)): hand it to a
genre skill with `unit contract`, or write it yourself, then

```bash
chitragupta draft unit accept content/drafts/twins app-install
```

It goes through the same gate, its glossary goes into the book's
Glossary, and its citations into the one bibliography.

## 🔢 How it prints

The assembler emits `\appendix` after the last chapter and `\input`s
each appendix in outline order. The `book` class then numbers them A,
B, C, so:

| You write | The book prints |
| --- | --- |
| the appendix's `# Installing the toolchain` heading | "Appendix A Installing the toolchain" |
| `\cref{app-install}` in any chapter | "Appendix A" |
| a section inside it | "A.1", "A.2" |
| a table or figure inside it | "Table A.1", "Figure A.1" |
| a glossary term defined in it | the definition ends "Appendix A" |

There is no "Part" page for the appendices; the table of contents lists
them after the last chapter.

**Do not letter the heading yourself, and it does no harm if you do.**
A unit headed `# Appendix A: The Mathematics You Need` would print
"Appendix A" twice, once from the class and once from the title, so the
book's conversion drops a leading `Appendix A:` (or `Appendix A --`,
`Appendix A.`) exactly as it drops `Chapter 1:` from a chapter. Your
`.md` keeps it, and so does the appendix's own standalone pdf, where
nothing else supplies the letter. The prefix is dropped wherever the
unit sits, so an "Appendix A: Proofs" unit left in an ordinary part (a
book outlined before `{#appendices}` existed) prints as "Chapter 7 /
Proofs": move it under `## Appendices {#appendices}` and it prints as
"Appendix A / Proofs". A `.tex` unit is not converted, so
`draft style` reports the prefix there as
`chitragupta.ChapterSelfNumbered` for you to delete.

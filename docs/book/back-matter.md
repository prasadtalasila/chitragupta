# 📚 Back matter: glossary, symbols, lists and the index

Status: **workflow**, part of [Write a book](../WRITE-A-BOOK.md).

**Written for** an author deciding which reference pages close the
book. **Assumed:** a working outline ([step 1](outline.md)). **Not
covered here:** what goes into the Glossary and List of Symbols, and how
to fix an entry; that is [step 5](registries.md#-the-glossary-and-the-list-of-symbols).

## 🧭 The default

`spec init` ends every outline with:

```markdown
## Back matter {#back}

### Glossary {#glossary}

### List of Symbols {#symbols}

### List of Figures {#figures}

### List of Tables {#tables}

### Index {#index}
```

The book prints them in that order, after the last chapter and any
[appendices](appendices.md), with the bibliography after the lists and
the index after the bibliography: the index is always last.

## ⚙ Generated pages

Those five ids are reserved. Each names a page the assembler generates,
not one you write:

| Id | Page | Printed when |
| --- | --- | --- |
| `{#glossary}` | Glossary | `registry build --glossary` wrote it: at least one accepted unit has a glossary term |
| `{#symbols}` | List of Symbols | `registry build --notation` wrote it: at least one `math.md` `## Symbols` row |
| `{#figures}` | List of Figures | at least one chapter has a captioned figure |
| `{#tables}` | List of Tables | at least one chapter has a captioned table |
| `{#index}` | Index | always, once `registry build --index` wrote the term table; built from the glossary, tuned by `index.toml` ([the index](book-index.md)) |

A generated page has **no file, no unit and no sections**: there is
nothing to write or accept, `unit status` does not list it, and a
`####` under it is a parse problem. A page with nothing to show is left
out rather than printed empty, and the assembler does not report it
missing. Each one it prints is listed in the table of contents.

## ✂ Changing the order, or dropping a page

The outline is the switch:

- **Drop a page:** delete its line. A book with no figures worth
  listing does without `### List of Figures {#figures}`.
- **Reorder:** move the lines. The back matter prints in outline order.
- **Move a page to the front:** put its line under `## Front matter
  {#front}` ([front matter](front-matter.md)). Not the index, which
  only `{#back}` may hold. The lists are the usual
  candidates; the *Chicago Manual of Style* puts them after the table of
  contents.
- **Add your own pages:** any other chapter under `{#back}` is a unit you
  write and accept ("About the author", "Further reading", "Version
  history"). It prints where you put it, unnumbered.

Each is an edit to the outline, so re-sign it afterwards
([changing the outline](changing-the-outline.md)).

## 🔢 Back-matter pages carry no number

LaTeX does not number chapters under `\backmatter`, which is what a
reader expects of a glossary or an "About the author" page. It has one
consequence: a back-matter (or front-matter) chapter cannot be pointed
at by number. So **glossary terms belong in numbered chapters**: a
glossary definition ends "Chapter 3" or "Appendix A", and a term defined
in an unnumbered page would end with a reference to nothing.
`registry check` reports a front- or back-matter unit that defines
glossary terms, as a `[glossary]` finding. Such a unit with no glossary
at all is not reported: a hand-written page has no dossier, and needs
none.

## ↩ Outlines without reserved parts

An outline with none of `{#front}`, `{#appendices}` and `{#back}`
(every book outlined before #1137) assembles exactly as before: the
Glossary and then the List of Symbols, each if `registry build` wrote
it, then the bibliography, and no lists of figures or tables and no
index. Add
`## Back matter {#back}` with the lines you want when you want control
over them. Once an outline has any of the three reserved parts, the
outline decides: a Glossary or List of Symbols prints only where an
entry for it stands.

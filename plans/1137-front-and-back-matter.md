# TB-9: front matter, appendices and back matter from the outline

Status: **built, in [PR 1158](https://github.com/prasadtalasila/chitragupta/pull/1158)
(v6.164.0).** Changed on the way: an assembly of the digital-twins book
showed `Appendix A: ...` titles printing the letter twice, so the #804
prefix rule now drops a leading `Appendix A:` too; `spec align` and
`spec status` treat generated pages as pages, and the registry gives
them no anchor (review); issue 1129 (TB-1, source credits) was folded
into the same pull request at the user's request. Written 2026-11-05, for
[issue 1137](https://github.com/prasadtalasila/chitragupta/issues/1137),
part of [epic 1128](https://github.com/prasadtalasila/chitragupta/issues/1128).

**Written for** whoever builds it. **It assumes**
[docs/WRITE-A-BOOK.md](../docs/WRITE-A-BOOK.md) for the outline, the two
sign-offs and the unit records, and
[plans/tb-10-book-glossary.md](tb-10-book-glossary.md) for the glossary
and List of Symbols pages.

**Not covered here:** chapter-level authors (an edited volume: `editor:`,
a per-chapter `author:` line, a List of Contributors). It adds to this
design without changing it, and is a genre of its own:
[issue 1157](https://github.com/prasadtalasila/chitragupta/issues/1157).
Rewriting the digital-twins book in `chitragupta-drafts` is content work
after the release.

## The problem, measured

`book-skeleton.tex` emits `\maketitle`, `\tableofcontents`, the chapters,
the glossary and notation pages and a bibliography. A textbook also has a
copyright page, a preface, appendices and lists of figures and tables
(BCcampus, *Self-Publishing Guide*, "Textbook Outline", CC BY 4.0).

Two facts found while planning:

- `spec.parse` already accepts `## Front matter {#front}` / `### Preface
  {#preface}`: they parse as a part and a chapter. But
  `unit.acceptance_units` makes a unit only of a chapter that declares at
  least one `####` section, so a preface (no sections) is **no unit** and
  can never be accepted. The same silently drops `ch-trust` and `ch-next`
  in `docs/examples/dossiers/book/spec.md`.
- `spec sign` records no date by design, so "the outline's sign-off date"
  in the issue does not exist. The build line carries the outline digest
  instead.

## Decisions (user, 2026-11-05)

1. **Three reserved parts**, each optional: `{#front}` (must be the first
   part), `{#appendices}` (after every other part, before `{#back}`) and
   `{#back}` (must be the last part). None prints a `\part` page.
2. **Removing an entry from the outline removes it from the book** on the
   next sign-off and assembly. `unit status` lists acceptance records no
   longer in the outline ("accepted, but no longer in the outline") and
   never deletes them or the prose; its exit code ignores them.
3. **The author writes the preface by hand.** `spec init` puts `###
   Preface {#preface}` in the default outline and copies
   `assets/book/preface.md` to `content/drafts/<book>/preface.md`, never
   overwriting. No untouched-template safeguard on `unit accept`.
4. **A chapter with no sections is its own unit** (the bug above).
5. **The copyright page is the author's file**, `content/specs/<book>/copyright.tex`,
   copied from `assets/book/copyright.tex` by `spec init`. Default: the
   title, "(c) <year> <author>. All rights reserved.", the usual
   no-reproduction sentence, and `\BuildLine`. A CC alternative is a
   comment. The assembler copies it beside `book.tex` and `\input`s it
   right after `\maketitle`; no file, no page.
6. **The title and author come from the outline.** `\BookTitle` is the
   `#` heading. `\BookAuthor` is a new `- author: <name>` line in the
   outline's preamble, written by `spec init --author`, printed by
   `spec show`. The assembler asks only when it is missing. Editing it
   moves the whole-book digest (re-sign) but no chapter digest.
7. **The year is written once, at the first `spec sign`**: `sign`
   replaces `<year>` in `copyright.tex` with the current year if the
   placeholder is still there, and never touches the file again.
8. **`\BuildLine`** = "Built <date> · outline <spec digest> · chitragupta
   <version>", defined by the assembler in `book.tex`.
9. **Back matter default order** in the `spec init` outline: `### Glossary
   {#glossary}`, `### List of Symbols {#symbols}`, `### List of Figures
   {#figures}`, `### List of Tables {#tables}`. These four ids are
   **generated pages**: no file, no unit, no sections; allowed only as
   chapters of `{#front}` or `{#back}`. Moving one under `{#front}` prints
   it there; deleting the line drops it. A glossary/symbols page prints
   only if `registry build` wrote it; a list only if some fragment has a
   captioned figure/table. The bibliography is always last.
10. **Appendices** are in scope: `\appendix` after the main matter, so
    they number A, B, ... and `\cref` prints "Appendix A".
11. **Compatibility:** an outline with none of the three reserved
    parts (widened from "no `{#back}`" in review) assembles as
    before (glossary, then notation, under `\backmatter`, before the
    bibliography; no lists).

## Design

### Code

- `chitragupta/spec/_matter.py` (new; `spec/__init__.py` is at 232 of
  250 code lines): the reserved ids, `author(text)`, `problems(units)`
  (placement of the three parts; generated ids only as section-less
  chapters of front/back; reserved ids at any other level) and
  `matter(entry)`. `spec.parse` adds `author` and these problems.
- `spec/_cli.py`: `init --author`, the new default outline, the two asset
  copies; `sign` stamps the year; `show` prints `author:`.
- `unit/__init__.py`: `acceptance_units` makes a section-less chapter its
  own unit and skips generated pages. `unit/_cli.py`: `status` lists
  orphaned records (JSON key `orphaned`).
- `registry`: a front/back unit with no dossier glossary is not a
  `[glossary] has no ## Glossary` finding; one that *does* define terms is
  a finding, since an unnumbered chapter cannot be `\Cref`'d.

### Skill

`book-assembler/SKILL.md` must not grow. Step 5's author sentence and
glossary sentence are replaced by shorter ones pointing at the
conventions; step 9's #804 block (self-numbered chapter titles, "nothing
is asked of you here") moves to `latex-conventions.md` under the
numbering paragraph. The cap in `tests/test_skill_size.py` drops with it.
`latex-conventions.md` gains "Front matter, appendices and back matter"
and "The copyright page"; the skeleton gains `\BookTitle`, `\BookAuthor`,
`\BuildLine`, `\input{copyright}`, and the three matter slots.

### Docs

"Tutorial: write a book" becomes a nav subgroup: `docs/WRITE-A-BOOK.md`
stays the overview (every inbound link keeps working), and the phases and
workflows move to `docs/book/`. Nav changes asked for at the same time:
"Decisions" becomes "Packaging" under "Working on it" before
"Auto-improvement"; "The name" moves under "Getting started" after "What
it does"; "Figure checks" becomes a subgroup of "Review drafts".

## Tests

- `test_spec_matter.py`: placement problems, generated-page rules, author
  line, default outline parses clean.
- `test_spec.py`: `init --author` and asset copies, never overwriting;
  `sign` stamps the year once; `show` prints the author.
- `test_acceptance_unit.py` / `test_unit.py`: section-less chapter is a
  unit; generated pages are not; orphaned records listed, exit unchanged.
- `test_registry.py`: front/back glossary findings.
- `test_skill_book_assembly.py` / `test_skill_size.py`: the skeleton and
  conventions carry the new slots; the cap is lowered.

Version: MINOR, 6.161.0.

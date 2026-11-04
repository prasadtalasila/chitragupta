# TB-10: the book's glossary, generated from the dossiers

Status: **designed, unbuilt.** Written 2026-11-04, for
[issue 1138](https://github.com/prasadtalasila/chitragupta/issues/1138),
part of [epic 1128](https://github.com/prasadtalasila/chitragupta/issues/1128).

**Written for** whoever builds TB-10. **It assumes**
[docs/WRITE-A-BOOK.md](../docs/WRITE-A-BOOK.md) for the registries and
the book track's two sign-offs,
`.claude/skills/book-assembler/SKILL.md` for the assembly steps, and
[SOUL.md](../SOUL.md) for why exactly one gate exists.

**Not covered here:** rewriting existing dossiers into the format below.
There is deliberately no converter (a user decision, not an omission):
the check lists every off-format bullet and a person or `draft-reviser`
rewrites it. For the digital-twins book in `chitragupta-drafts` that is
one commit in that repository, made before `--glossary` is run on it.
Nor is a `draft style` rule or a review-agenda class: the glossary is
book-only, and the book track has no agenda.

## What the issue assumed, and what is on disk

The issue says `registry build` "already collects" the dossiers'
glossaries. It does not, and the measurement is worse than the gap
suggests:

1. **The registry reads the drafts, not the dossiers.**
   `chitragupta/registry/__init__.py`'s `_read_unit` matches
   `- **Term** -- definition` bullets in the unit's *prose*. The
   digital-twins book's eight accepted drafts hold none, so its
   `registries/terms.md` is a header row and nothing else.
2. **The dossiers use a shape nothing parses.** Their eight `scope.md`
   glossaries hold 209 bullets, every one `- **Term**: definition`.
   `_GLOSSARY_TERM` (`chitragupta/dossier/_citekeys.py`) and every
   `WRITE-A-*.md` example require ` -- `, so `dossier.glossary_terms()`
   returns `{}` for every unit of that book.
3. **Terms are redefined on purpose.** Chapter 3 replaces Chapter 1's
   working definition of *digital twin*. The issue's "carry the first
   with a marker" would print the superseded one.

Counted with:

```bash
for f in content/dossiers/books/digital-twins-for-software-engineers/*/scope.md; do
  awk '/^## Glossary/{g=1;next} /^## /{g=0} g' "$f" | grep -c '^- \*\*'
done
```

## Decisions

Each was taken with the user on 2026-11-03/04.

| # | Question | Decision |
| --- | --- | --- |
| 1 | Accept `**Term**:` as well as `**Term** --`? | **No.** One shape. `_GLOSSARY_TERM` stays as it is |
| 2 | How does the agent learn the shape? | A worked example in the `## Glossary` comment `dossier init` writes |
| 3 | Qualifiers ("working definition for Part I", "as before")? | Not part of a definition. The template says so; the check cannot see them (below) |
| 4 | A term defined in more than one unit? | **All** definitions printed, numbered, each with its chapter in brackets |
| 5 | Off-format bullet: report or block? | `registry check` reports it (exit 0); `registry build --glossary` **refuses** |
| 6 | Mandatory as a gate? | No. SOUL.md: exactly one citation gate, and no other check grows a flag that blocks. The build refusing is "atomic, or not at all", as `render` refusing an unmapped `<!-- math -->` marker is |
| 7 | Terms source | The dossier glossary **replaces** the prose bullets as the terminology registry's source |
| 8 | A converter for old dossiers? | **None** |
| 9 | A citekey in a glossary definition? | Off-format. The glossary never cites, so the gate need not read `glossary.tex` |
| 10 | Markdown definition to LaTeX | Each unit's own `math.md` mapping, then pandoc |

## 1. The format, and how it is read

The shape: `- **Term** -- definition`. A definition may wrap onto
indented continuation lines. A symbol or abbreviation goes inside the
bold. One term per bullet.

`chitragupta/dossier/_create.py`'s `## Glossary` comment becomes:

```markdown
## Glossary

<!-- One bullet per recurring term, in exactly this shape:

     - **Digital shadow (DS)** -- an automated flow from PT to DO, and a
       return flow from DO to PT that exists but is carried by a person.
     - **Baseline (`M_0`)** -- the measured present-day value of the value
       metric, before anything is built.

     The term in bold, a space, two hyphens, a space, then the definition.
     A symbol or abbreviation goes inside the bold. One term per bullet.
     The definition only: no "working definition for Part I", no "as
     before". A book's glossary prints this text as written, and never
     a citation. -->
```

**`glossary_terms()` keeps every bullet.** Today it returns
`{term: definition}`, so a unit defining a term twice loses the first
silently. It becomes `glossary_entries(draft) -> list[(term,
definition, line)]` in file order; `glossary_terms()` stays as the
dict view built on it (last definition wins, as now), so the acronym
drift check and `dossier/_acronyms.py` do not change.

**`glossary_problems(draft) -> list[(line, text, reason)]`**, beside it.
A problem is a top-level bullet under `## Glossary` that
`_GLOSSARY_TERM` does not match (reason: not `- **Term** --
definition`), or a matching one whose definition holds a citekey by
`citation_gate.extract_citekeys_from_line` (reason: holds a citekey). A
plain paragraph (Chapter 3's "Chapters 1 and 2's terms carry forward
unchanged (...)") is not a bullet and is not a problem.

The variations measured on the real book, and what each is:

| | Bullet | Read as |
| --- | --- | --- |
| a | `- **Residual**: the difference...` | problem |
| b | `- **Digital twin (DT)**, definition for the rest of the book: a DO...` | problem |
| c | `- **Digital twin (DT), working definition for Part I**: software...` | problem (the colon); after a rewrite to ` -- ` it would match with the qualifier in the term, see below |
| d | `- **Baseline** (`M_0`): the measured...` | problem |
| e | `- **Solver**: ... **Event scheduler**: ...` (one bullet) | problem, once, at the bullet |
| f | `- **Physical twin (PT)**: as before, and in this chapter...` | problem (the colon); "as before" itself is invisible |
| g | `**Solver**` twice in one unit, both well-formed | two entries; a `[term]` finding |

**What the check cannot see**, said in the code and in WRITE-A-BOOK.md
rather than left implied: a qualifier inside a well-formed bold term,
and a well-formed definition that reads "as before". Both are text a
person reads on the generated page. No heuristic is proposed: a comma in
a term and the words "as before" are both legitimate.

## 2. The registry

- **Source.** `_read_unit` takes terms from
  `dossier.glossary_entries(unit.draft_path(book, unit_id))`.
  `registry.definitions()` is removed. `_prose()` keeps dropping
  definition-shaped lines from the claim register.
- **Kind.** `notation` when the whole term is code or maths, as now;
  `Baseline (`M_0`)` is a `term`.
- **`terms.md`** keeps its four columns, one row per entry, outline
  order. "defined in" stays the unit id.
- **Term identity** for duplicates: lowercased, whitespace collapsed,
  one trailing parenthetical dropped. `Digital twin (DT)` and
  `digital twin` are one term.
- **`[term]` finding** covers a repeat inside one unit as well as
  across units (today's `_repeats` counts distinct units only):

  ```text
  [term] `Digital twin (DT)` is defined in 01-why-anyone-pays-for-a-digital-twin, 03-model-simulation-shadow-twin
  [term] `Solver` is defined in 07-simulators, a1-the-mathematics-you-need (2x)
  ```

- **`[glossary]` finding**, new, one per problem:

  ```text
  [glossary] 03-model-simulation-shadow-twin scope.md:116 `- **Physical twin (PT)**: as before, ...` -- not "- **Term** -- definition"
  ```

- **`check`** still exits 0 whatever it finds. **`build`** without
  `--glossary` still writes the three registries over problems.
- **`excerpt`** now hands a unit the other units' dossier terms.

## 3. `registry build --glossary <path>`

Written after the three registries, only when the flag is given.

- **Refusal.** Any problem in any accepted unit: print every one, exit
  1, write nothing, leave an existing file at `<path>` untouched.
- **No terms.** No accepted unit has an entry: write nothing, say so,
  exit 0. The assembler then writes no `\input`.
- **Order.** Alphabetical, case-insensitive, by the term identity; the
  heading is the first spelling met in outline order.
- **One definition** prints inline; **several** print as an
  `enumerate`, outline order. Each ends `(\Cref{<unit-id>})`, which the
  assembler's `\label{<unit-id>}` after each `\chapter` resolves to
  "Chapter 3" or "Appendix A": no numbering is computed here.
- **Conversion.** A unit's definitions get that unit's
  `render_output._math.load_mapping()` applied by
  `_math.substitute()`, then pandoc Markdown-to-LaTeX. Per unit,
  because two units may map the same ASCII differently and both stay
  right (SKILL.md step 4). Missing pandoc is the same error `render`
  gives.
- **Deterministic.** No timestamp; rebuilding over unchanged units is
  byte-identical.

The file:

```latex
% Generated by `python -m chitragupta.draft registry build --glossary`
% from the accepted units' scope.md glossaries. Edit those, not this.
\chapter*{Glossary}
\addcontentsline{toc}{chapter}{Glossary}
\begin{description}
\item[Digital twin (DT)]
  \begin{enumerate}
  \item software that keeps a model of one specific physical system ...
        (\Cref{01-why-anyone-pays-for-a-digital-twin})
  \item a DO paired with a specific PT, with automated data flow ...
        (\Cref{03-model-simulation-shadow-twin})
  \end{enumerate}
\item[Event scheduler] the part that advances a discrete-event model to
  the next event. (\Cref{07-simulators})
\end{description}
```

## 4. The book-assembler

`SKILL.md` is 20,219 bytes against a 21,000 cap
(`tests/test_skill_size.py`). It gets only:

- **Step 3**: `registry build` gains
  `--glossary content/rendered/<book>/glossary.tex`. On a refusal,
  **stop** and report every bullet; the fix is `draft-reviser` on that
  unit's `scope.md`, never an edit by this skill.
- **Step 5**: if `glossary.tex` exists, `\input` it under `\backmatter`
  before the bibliography; if not, write no `\input` and say nothing
  (the `preamble.tex` rule's wording).

`assets/book-skeleton.tex` gains, between `\backmatter` and
`\bibliographystyle`:

```latex
\input{glossary}                             % latex-conventions.md, "The glossary"; only if registry build wrote one
```

`references/latex-conventions.md` gains "The glossary": the entry
layout, numbered definitions, `\Cref`, and what the check cannot see.

## 5. Tests and docs

Tests first, in `tests/test_dossier.py` and `tests/test_registry.py`:

- each row a-g above as a fixture; a carry-forward paragraph is not a
  problem; `[@key]` and `\citep{}` in a definition are problems;
- two `Solver` entries in one unit both returned, in file order; the
  acronym drift tests pass unchanged;
- terms come from `scope.md`; a definition bullet in the prose is not
  read (the three `definitions()` tests are rewritten, not deleted);
- `Digital twin` and `Digital twin (DT)` are one term; a repeat inside
  one unit is a `[term]` finding; `[glossary]` findings print and
  `check` exits 0; `excerpt` carries dossier terms;
- `--glossary`: alphabetical; inline vs numbered; `\Cref{<unit-id>}`;
  byte-identical rebuild; refusal exits 1 and leaves an earlier file
  alone; no terms, no file; a unit's `math.md` turns `` `M_0` `` into
  maths. Pandoc-dependent cases skip as the render tests do;
- `tests/test_skill_size.py` passes for `book-assembler`.

Docs, same PR: `docs/WRITE-A-BOOK.md` (the registry table's
terminology row names `scope.md`; the real-book counts are re-measured
or dated; a short "Glossary" subsection), the `dossier init` template,
SKILL.md, `latex-conventions.md`, the skeleton, and the version bump
and changelog per `DEVELOPER-AGENTS.md`. The PR says `Closes #1138`.

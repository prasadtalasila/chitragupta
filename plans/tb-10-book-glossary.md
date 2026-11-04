# TB-10: the book's glossary and list of symbols, generated from the dossiers

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

**Not covered here either:** TB-7's (#1135) notation-discipline rules,
which read a chapter's prose; the `[notation]` findings below compare
only glossary symbols across units, so the two do not overlap.

**Beyond the issue:** the list of symbols (section 4) is not in #1138's
text. It was added during design because the same bullets already carry
each symbol, so one reading yields both pages.

## What the issue assumed, and what is on disk

The issue says `registry build` "already collects" the dossiers'
glossaries. It does not, and the measurement is worse than the gap
suggests:

1. **The registry reads the drafts, not the dossiers.**
   `chitragupta/registry/__init__.py`'s `_read_unit` matches
   `- **Term** -- definition` bullets in the unit's *prose*. The
   digital-twins book's eight accepted drafts hold none (their 68
   bold-led bullets are points such as `- **Worst case.** The model
   diverges...`, not definitions), so its `registries/terms.md` is a
   header row and nothing else.
2. **The dossiers use a shape nothing parses.** Their eight `scope.md`
   glossaries hold 209 bullets, every one `- **Term**: definition`.
   `_GLOSSARY_TERM` (`chitragupta/dossier/_citekeys.py`) and every
   `WRITE-A-*.md` example require ` -- `, so `dossier.glossary_terms()`
   returns `{}` for every unit of that book.
3. **Terms are redefined on purpose.** Chapter 3 replaces Chapter 1's
   working definition of *digital twin*. The issue's "carry the first
   with a marker" would print the superseded one.
4. **Symbols are already recorded there.** About 44 of the 209 bullets
   name a symbol, almost all as `**Name** (`sym`)`: `**Baseline**
   (`M_0`)`, `**Pump time** (`t`)`.

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
| 1 | Accept `**Term**:` as well as `**Term** --`? | **No.** The separator is ` -- ` |
| 2 | How does the agent learn the shape? | A worked example in the `## Glossary` comment `dossier init` writes |
| 3 | Qualifiers ("working definition for Part I", "as before")? | Not part of a definition. The template says so; the check cannot see them (below) |
| 4 | A term defined in more than one unit? | **All** definitions printed, numbered, each with its chapter in brackets |
| 5 | Off-format bullet: report or block? | `registry check` reports it (exit 0); `registry build --glossary`/`--notation` **refuses** |
| 6 | Mandatory as a gate? | No. SOUL.md: exactly one citation gate, and no other check grows a flag that blocks. The build refusing is "atomic, or not at all", as `render` refusing an unmapped `<!-- math -->` marker is |
| 7 | Where do the glossary's terms come from? | `scope.md`'s `## Glossary`. It **replaces** the definition bullets in the draft prose as the terminology registry's source |
| 8 | A converter for old dossiers? | **None** |
| 9 | A citekey in a glossary definition? | Off-format. The glossary never cites, so the gate need not read `glossary.tex` |
| 10 | Markdown definition to LaTeX | Each unit's own `math.md` mapping, then pandoc |
| 11 | How is a symbol told apart from a term? | An optional symbol slot in the bullet: `- **Name** (`sym`) -- definition` |
| 12 | Which existing shapes stay valid? | `- **Term** -- definition` (no symbol), and the symbol inside the bold, `- **Baseline (`M_0`)** -- ...`. The colon form does not |
| 13 | Collect the symbols in one place? | Yes: a list of symbols from the same `scope.md` bullets, in the back matter **right after the glossary** |
| 14 | One table or one per chapter? | **One consolidated table**; rows merge by meaning |
| 15 | Drafting notes in a definition ("the user's correction of 2026-09-08") | Left as is: printed as written. Fixed in the dossiers when they are rewritten (below) |
| 16 | The same definition text in several units | Printed **once**, with all its chapters; `registry check` still reports the repeat |
| 17 | Title of the second page | "List of Symbols" |
| 18 | One PR or two? | **One PR**, glossary and list of symbols together |
| 19 | The issue's text | Edited to match this plan |
| 20 | The digital-twins dossiers | Rewritten after this merges, unit 3's `scope.md` included (see "After the merge") |

## 1. The format, and how it is read

```markdown
- **Term** -- definition
- **Term** (`symbol`) -- definition
- **`symbol`** -- definition
```

The separator is ` -- ` after the closing bold or the symbol slot. A
definition may wrap onto indented continuation lines. One term per
bullet. The symbol is in backticks, so `**Digital shadow (DS)**` keeps
`(DS)`, an abbreviation, as part of its name.

Also read, for compatibility (decision 12): the symbol inside the bold,
`- **Baseline (`M_0`)** -- ...`, read as term *Baseline*, symbol
`M_0`: a bold term ending in a backticked parenthetical is split there.

`chitragupta/dossier/_create.py`'s `## Glossary` comment becomes:

```markdown
## Glossary

<!-- One bullet per recurring term or symbol, in exactly one of these
     shapes:

     - **Digital shadow (DS)** -- an automated flow from PT to DO, and a
       return flow from DO to PT that exists but is carried by a person.
     - **Baseline** (`M_0`) -- the measured present-day value of the value
       metric, before anything is built.
     - **`x_k`** -- the state at step k.

     The term in bold, its symbol in backticks and brackets if it has
     one, a space, two hyphens, a space, then the definition. One term
     per bullet. The definition only: no "working definition for Part
     I", no "as before". A book's glossary and list of symbols print
     this text as written, and never a citation. -->
```

**`_GLOSSARY_TERM` gains the optional symbol group** and keeps matching
every bullet it matches today, so the acronym drift check and
`dossier/_acronyms.py` read the same terms they read now.

**`glossary_terms()` keeps every bullet.** Today it returns
`{term: definition}`, so a unit defining a term twice loses the first
silently. It becomes `glossary_entries(draft) -> list[Entry]`, where an
`Entry` is `(term, symbol | None, definition, line)` in file order;
`glossary_terms()` stays as the dict view built on it (last definition
wins, as now), so its two callers do not change.

**`glossary_problems(draft) -> list[(line, text, reason)]`**, beside it.
A problem is a top-level bullet under `## Glossary` that the pattern
does not match (reason: not `- **Term** -- definition`), or a matching
one whose definition holds a citekey by
`citation_gate.extract_citekeys_from_line` (reason: holds a citekey). A
plain paragraph (Chapter 3's "Chapters 1 and 2's terms carry forward
unchanged (...)") is not a bullet and is not a problem.

The variations measured on the real book, and what each is:

| | Bullet | Read as |
| --- | --- | --- |
| a | `- **Residual**: the difference...` | problem (the colon) |
| b | `- **Digital twin (DT)**, definition for the rest of the book: a DO...` | problem |
| c | `- **Digital twin (DT), working definition for Part I**: software...` | problem (the colon); after a rewrite to ` -- ` it would match with the qualifier in the term, see below |
| d | `- **Baseline** (`M_0`): the measured...` | problem (the colon); `- **Baseline** (`M_0`) -- ...` is term + symbol |
| e | `- **Gain** (`k`), **cap** (`V_max`), **check interval** (`T_c`): ...` (16 such bullets) | problem, once, at the bullet: one term per bullet |
| f | ``- **Step size** `h`, **macro step** `H`: ...`` (Chapter 7, symbol without brackets) | problem |
| g | `- **Physical twin (PT)**: as before, and in this chapter...` | problem (the colon); "as before" itself is invisible |
| h | `**Solver**` twice in one unit, both well-formed | two entries; a `[term]` finding |

**What the check cannot see**, said in the code and in WRITE-A-BOOK.md
rather than left implied: a qualifier inside a well-formed bold term,
and a well-formed definition that reads "as before". Both are text a
person reads on the generated page. No heuristic is proposed: a comma in
a term and the words "as before" are both legitimate.

## 2. The registry

Decision 7 in concrete terms: `registry build` writes `terms.md`, and
`registry check` and `registry excerpt` read the same rows. Today those
rows come from `- **Term** -- definition` lines anywhere in each
accepted unit's draft. After this change they come from that unit's
`scope.md` `## Glossary`, and a definition-shaped line in the prose is
no longer a term. On the digital-twins book that takes `terms.md` from
zero rows to one per glossary bullet, once the dossiers are rewritten.

- **Source.** `_read_unit` takes terms from
  `dossier.glossary_entries(unit.draft_path(book, unit_id))`.
  `registry.definitions()` is removed. `_prose()` keeps dropping
  definition-shaped lines from the claim register.
- **`terms.md`** gains a symbol column: term, symbol, kind, defined in,
  definition, one row per entry, outline order. "defined in" stays the
  unit id. `kind` is `notation` for a symbol-only entry, `term`
  otherwise.
- **Term identity** for duplicates: lowercased, whitespace collapsed,
  one trailing non-backticked parenthetical dropped. `Digital twin
  (DT)` and `digital twin` are one term.
- **`[term]` finding** covers a repeat inside one unit as well as
  across units (today's `_repeats` counts distinct units only):

  ```text
  [term] `Digital twin (DT)` is defined in 01-why-anyone-pays-for-a-digital-twin, 03-model-simulation-shadow-twin
  [term] `Solver` is defined in 07-simulators, a1-the-mathematics-you-need (2x)
  ```

- **`[notation]` findings**, new, two kinds:

  ```text
  [notation] `k` names different terms: gain (unit-a), rate constant (unit-b)
  [notation] `m_t` is typeset differently: m_\mathrm{t} (unit-a), m_t (unit-b)
  ```

  The first compares term identities for one symbol across units; the
  second compares each unit's `math.md` mapping for that symbol. Both
  examples are illustrative: measured on the digital-twins book, the
  bracketed symbols its glossaries record today clash nowhere (`RTF`
  appears twice, with one meaning), and no bare symbol is mapped two
  ways across its eight `math.md` files. Symbols used only in equations
  and never glossaried are outside both checks.
- **`[glossary]` finding**, new, one per problem:

  ```text
  [glossary] 03-model-simulation-shadow-twin scope.md:116 `- **Physical twin (PT)**: as before, ...` -- not "- **Term** -- definition"
  ```

- **`check`** still exits 0 whatever it finds. **`build`** without
  `--glossary`/`--notation` still writes the three registries over
  problems.
- **`excerpt`** now hands a unit the other units' dossier terms and
  symbols.

## 3. `registry build --glossary <path>`

Written after the three registries, only when the flag is given.

- **Refusal.** Any problem in any accepted unit: print every one, exit
  1, write nothing, leave an existing file at `<path>` untouched.
- **No terms.** No accepted unit has a named entry: write nothing, say
  so, exit 0. The assembler then writes no `\input`.
- **Entries.** Every entry with a name; a symbol-only entry goes only to
  the list of symbols. A symbol is shown after the name: **Baseline
  ($M_0$)**.
- **Order.** Alphabetical, case-insensitive, by the term identity; the
  heading is the first spelling met in outline order.
- **One definition** prints inline; **several** print as an
  `enumerate`, outline order. Definitions whose text is identical
  (whitespace collapsed) are one definition listing every chapter it
  appears in: `(\Cref{a}, \Cref{b})`. Each ends `(\Cref{<unit-id>})`, which the
  assembler's `\label{<unit-id>}` after each `\chapter` resolves to
  "Chapter 3" or "Appendix A": no numbering is computed here.
- **Conversion.** A unit's definitions and symbols get that unit's
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
\item[Baseline ($M_0$)] the measured present-day value of the value
  metric, before anything is built.
  (\Cref{01-why-anyone-pays-for-a-digital-twin})
\item[Digital twin (DT)]
  \begin{enumerate}
  \item software that keeps a model of one specific physical system ...
        (\Cref{01-why-anyone-pays-for-a-digital-twin})
  \item a DO paired with a specific PT, with automated data flow ...
        (\Cref{03-model-simulation-shadow-twin})
  \end{enumerate}
\end{description}
```

## 4. `registry build --notation <path>`: the list of symbols

The same entries, those with a symbol, under the same refusal,
no-entries and determinism rules as `--glossary`.

- **One consolidated table** for the whole book, never one per
  chapter.
- **Rows.** Symbol, meaning (the term's name, or the definition for a
  symbol-only entry), chapters as `\Cref{<unit-id>}`. Rows merge **by
  meaning**: a symbol with the same term identity in several units is
  one row listing those chapters in outline order (`RTF`, real-time
  factor, Chapter 7, Appendix A); a symbol naming different terms gets
  one row per meaning, so a clash is visible on the page as well as in
  `[notation]`.
- **Typesetting.** Each symbol through its own unit's `math.md`, as in
  section 3. A symbol with no mapping stays as the code span it is in
  the chapter.
- **Order.** By the ASCII symbol, case-insensitive; Greek names
  (`alpha` ... `omega`, leading the symbol) after the Latin letters.

```latex
% Generated by `python -m chitragupta.draft registry build --notation`
% from the accepted units' scope.md glossaries. Edit those, not this.
\chapter*{List of Symbols}
\addcontentsline{toc}{chapter}{List of Symbols}
\begin{longtable}{@{}l p{0.6\textwidth} l@{}}
$M_0$ & baseline & \Cref{01-why-anyone-pays-for-a-digital-twin} \\
$m_\mathrm{t}$ & target moisture & \Cref{02-plant-demonstrator} \\
$\theta$ & parameter & \Cref{06-models} \\
\end{longtable}
```

## 5. The book-assembler

`SKILL.md` is 20,219 bytes against a 21,000 cap
(`tests/test_skill_size.py`). It gets only:

- **Step 3**: `registry build` gains
  `--glossary content/rendered/<book>/glossary.tex --notation
  content/rendered/<book>/notation.tex`. On a refusal, **stop** and
  report every bullet; the fix is `draft-reviser` on that unit's
  `scope.md`, never an edit by this skill.
- **Step 5**: for each of `glossary.tex` and `notation.tex` that exists,
  `\input` it under `\backmatter`, glossary first, before the
  bibliography; for one that does not, write no `\input` and say
  nothing (the `preamble.tex` rule's wording).

`assets/book-skeleton.tex` gains, between `\backmatter` and
`\bibliographystyle`:

```latex
\input{glossary}                             % latex-conventions.md, "Glossary and symbols"; only if registry build wrote it
\input{notation}                             % the same; right after the glossary
```

`references/latex-conventions.md` gains "Glossary and symbols": the
entry layout, numbered definitions, `\Cref`, symbol order, and what the
check cannot see.

## 6. Tests and docs

Tests first, in `tests/test_dossier.py` and `tests/test_registry.py`:

- each row a-h above as a fixture; the three valid shapes and the
  symbol-inside-the-bold shape parse to the right term and symbol;
  `(DS)` stays in the name; a carry-forward paragraph is not a problem;
  `[@key]` and `\citep{}` in a definition are problems;
- two `Solver` entries in one unit both returned, in file order; the
  acronym drift tests pass unchanged;
- terms come from `scope.md`; a definition bullet in the prose is not
  read (the three `definitions()` tests are rewritten, not deleted);
- `Digital twin` and `Digital twin (DT)` are one term; a repeat inside
  one unit is a `[term]` finding; both `[notation]` kinds; `[glossary]`
  findings print and `check` exits 0; `excerpt` carries dossier terms;
- `--glossary`: alphabetical; inline vs numbered; identical
  definitions in two units print once with both chapters; symbol after the
  name; symbol-only entries absent; `\Cref{<unit-id>}`;
- `--notation`: only entries with a symbol; same meaning merges into one row
  listing its chapters, different meanings stay separate rows; Greek
  after Latin;
- both flags: byte-identical rebuild; refusal exits 1 and leaves an
  earlier file alone; nothing to write, no file; a unit's `math.md`
  turns `` `M_0` `` into maths. Pandoc-dependent cases skip as the
  render tests do;
- `tests/test_skill_size.py` passes for `book-assembler`.

Docs, same PR: `docs/WRITE-A-BOOK.md` (the registry table's
terminology row names `scope.md`; the real-book counts are re-measured
or dated; a short "Glossary and symbols" subsection), the five
`WRITE-A-*.md` glossary examples gain one symbol bullet, the `dossier
init` template, SKILL.md, `latex-conventions.md`, the skeleton, and the
version bump and changelog per `DEVELOPER-AGENTS.md`. The PR says
`Closes #1138`.

## After the merge: the digital-twins dossiers

A separate commit in `chitragupta-drafts`, after this ships, driven by
`registry check`'s `[glossary]` findings:

- every `## Glossary` bullet rewritten into a valid shape (all eight
  units, unit 3's `scope.md` included; the unit 3 *draft* is not
  touched);
- each definition checked against the chapter's own text and brought
  into line with it, the draft being the authority; drafting notes and
  qualifiers dropped while doing so;
- then `registry build --glossary --notation` and `registry check` run,
  and every remaining finding reported to the user.

## Amendments from review

A review of this plan against the code (2026-11-04) changed these, and
they override anything above that reads otherwise.

1. **Modules.** `chitragupta/dossier/_citekeys.py` is at 246 of 250 code
   lines, so `_GLOSSARY_HEADING`, `_GLOSSARY_TERM`, `glossary_terms` and
   the new `glossary_entries`/`glossary_problems` move to
   `chitragupta/dossier/_glossary.py` (a split the change forces; the
   importers in `_acronyms.py`, `style_acronym_drift.py` via
   `dossier.glossary_terms`, and `registry/__init__.py` follow). The two
   page writers go in `chitragupta/registry/_pages.py`, called by
   `_cli.py`.
2. **Where a definition ends.** A bullet is `^[-*+]\s` at column 0. Its
   definition is the bullet line plus every following line indented by
   at least one space; it ends at the first blank line or column-0
   line. So an off-format bullet or a paragraph after a good bullet is
   never absorbed into the definition before it. A bullet with an empty
   definition (`- **DTaaS** --`) is still skipped by `glossary_terms()`
   and is a `[glossary]` problem (reason: no definition).
3. **Symbols are not sent through pandoc.** A mapped symbol is written
   as `$<latex>$` straight from the unit's `math.md`; an unmapped one
   goes through the same conversion as a definition (a code span).
   Pandoc writes inline maths in a definition as `\(...\)`, and the
   tests assert that. `\item[{...}]` wraps its term in braces, so a `]`
   in a term cannot end the optional argument.
4. **One pandoc helper, one call.** `render_output.markdown_to_latex(texts:
   list[str]) -> list[str]` in `_pandoc.py`: `-f markdown -t latex
   --wrap=none --no-highlight` with `breakable_inline_code.lua`, through
   `programs.require_program` as `_run_pandoc` does. The texts are
   joined by a sentinel paragraph (a fixed token that cannot occur in a
   definition, checked before joining) and split after, so a whole book
   is one process. The math mapping is applied per unit *before*
   joining, which is why one call is still per-unit-correct.
5. **Exit codes.** `build --glossary/--notation` always writes
   `terms.md`, `claims.md` and `xrefs.md` first. Then, on any problem
   or a missing pandoc, it prints them (`[glossary] ...` /
   `[missing-binary] ...`) and exits 1, and neither page is written. A
   page is written to a temporary file and renamed, so it is never left
   half-written. `_cli.py`'s `except` gains `MissingBinary`.
6. **The words "never blocks".** SOUL.md's "none grows a flag that
   blocks", `_cli.py`'s parser description and docs/WRITE-A-BOOK.md's
   "why check exits 0" gain one clause each: a *check* never blocks; a
   *build* that cannot write a correct file refuses, as `render` refuses
   an unmapped `<!-- math -->` marker. `registry check` itself is
   unchanged.
7. **The symbol-inside-the-bold split changes a key.** `glossary_terms()`
   keys `**Baseline (`M_0`)**` as `Baseline`, not ``Baseline (`M_0`)``.
   Harmless for acronym detection (`acronyms._candidate` needs
   `[A-Z]{2,6}`), and pinned by a test.
8. **A unit with no glossary is reported.** An accepted unit with no
   `scope.md`, or no `## Glossary` in it, is one `[glossary]` finding
   (`<unit> has no ## Glossary`), never a refusal: a chapter with no
   terms is legitimate.
9. **Appendices.** "Appendix A" from `\Cref` depends on `\appendix`
   preceding the unit's `\input`; latex-conventions.md says so.
   `longtable`, `cleveref` and `description`/`enumerate` are already
   loaded by the skeleton.
10. **Sort keys.** Glossary: term identity, then outline order, then
    file line. List of Symbols: the symbol lowercased; a symbol is Greek
    when it starts with a `_math._GREEK_NAMES` word followed by the end
    or `_`/`^`; Latin first, then Greek, then anything else.

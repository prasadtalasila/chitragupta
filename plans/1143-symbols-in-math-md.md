# One home for a unit's symbols: `math.md`'s `## Symbols`

Status: **built, in [PR 1147](https://github.com/prasadtalasila/chitragupta/pull/1147)
(v6.159.0).** Changed on the way, from the implementation review: the
List of Symbols typesets a row as its defining unit does, never as a
unit pointing at it; a table line under `## Symbols` that is no row is
`malformed`; the glossary-maths rule runs the context rules only for a
unit that has a `math.md`; `excerpt` passes on resolved rows only. No
`CHANGELOG.md` exists, so the migration note is in the release body.
Written 2026-11-05, for
[issue 1143](https://github.com/prasadtalasila/chitragupta/issues/1143),
with [issue 1142](https://github.com/prasadtalasila/chitragupta/issues/1142)
folded into the same pull request. Part of
[epic 1128](https://github.com/prasadtalasila/chitragupta/issues/1128).

**Written for** whoever builds it. **It assumes**
[plans/tb-10-book-glossary.md](tb-10-book-glossary.md) for the glossary
and List of Symbols as #1141 shipped them,
[plans/1115-1116-math-shape-rules.md](1115-1116-math-shape-rules.md) for
the span rules and the "Not mathematics" table #1146 added, and
[docs/WRITE-A-BOOK.md](../docs/WRITE-A-BOOK.md) for the registries.

**Not covered here:** rewriting the digital-twins book's dossiers in
`chitragupta-drafts`. That is content work after the release (last
section). There is no converter, a user decision, as for #1141.

## The problem, measured

After #1141 a unit's notation lives in two files that do not refer to
each other: `math.md` maps each ASCII span to LaTeX and is the complete
list of what the unit typesets, but carries no meaning; `scope.md`'s
glossary slot `- **Term** (`sym`) -- ...` carries the meaning, but only
for the symbols an author put there. A third, unread copy sits in
`scope.md`'s House style ("this chapter adds `T_s` (sampling interval),
...") in five of the eight units. On the digital-twins book
(2026-11-04/05): 70 mapped bare symbols are in no glossary and so are
missing from the List of Symbols unreported; 16 maths spans in glossary
definitions print in typewriter type, and their rows cannot be added
because the orphan check calls a glossary-only row stale; and chapters
share symbols only by a prose convention nobody checks (`P` and `mu`
already clash).

## Decisions (user, 2026-11-05)

1. **Meanings live per draft**, in that draft's `math.md`, not in a
   book-level file: a standalone survey or thesis chapter records them
   too.
2. **`math.md` gains an optional `## Symbols` table** below the mapping
   table. The mapping table is unchanged and remains the only source of
   a symbol's LaTeX; `## Symbols` has no LaTeX column.
3. **A Meaning cell has three forms:** a **bold glossary term**, which is
   a link (`**Target moisture**`), optionally followed by a note after a
   comma (`**Moisture thresholds**, lower`); `see <unit-id>`, a pointer
   to another unit's row for the same symbol; or free text.
4. **A bold link resolves against any glossary in the book** (chapter 3
   may write `**Residual**`, defined in chapters 1 and 2); in a
   standalone draft nothing resolves links, since nothing prints them.
5. **Several symbols for one term** (A1): one row per symbol, told apart
   by the note. **One term with different symbols in different units**
   (B1): each numbered definition carries its own unit's symbols.
6. **The glossary symbol slot is retired with a finding**, all three of
   #1141's spellings: ``**Term** (`s`)``, ``**Term `s`**`` and the
   symbol-only bullet `**`s`** -- ...`. `registry check` reports;
   `registry build --glossary/--notation` refuse.
7. **House style symbol inventories** are dropped in the content pass
   and replaced by a pointer; nothing parses House style.
8. **Completeness is reported by both** `render` (every draft) and
   `registry check` (the book).
9. **#1142 is done in the same PR**, describing the final shape.

## 1. The format, and how it is read

```markdown
# Mathematics

| ASCII in the draft | LaTeX |
| --- | --- |
| `m_t` | `m_\mathrm{t}` |
| `m_lo` | `m_\mathrm{lo}` |
| `T_r` | `T_\mathrm{r}` |
| `T_r = 10` | `T_\mathrm{r} = 10` |

## Not mathematics

| `404` |

## Symbols

| Symbol | Meaning |
| --- | --- |
| `m_t` | **Target moisture** |
| `m_lo` | **Moisture thresholds**, lower |
| `T_c` | see 02-plant-demonstrator |
| `e_q` | quantisation error |
```

**Sections.** `## Symbols` runs from its heading to the next `##`
heading or the end of the file, so it may sit before or after
`## Not mathematics`. `mapping_rows()` and `not_math()` read
the file with that section removed, so a free-text meaning written as a
backticked span (`` | `f_s` | `1 / T_s` | ``) is never read as a mapping
row. The other two tables keep their #1146 behaviour exactly.

**Rows.** ``| `<symbol>` | <meaning> |``; the header row has no backticked
first cell and is skipped. The meaning is matched in this order:
`see <unit-id>`; `**<term>**` then optionally `,` and a note; anything
else is free text. An empty meaning is malformed, and so is a symbol
with two rows. A `|` inside a meaning is written `\|`, as the
registry's own tables escape it.

**Which mapping keys need a meaning.** A *bare symbol*: an identifier,
letters and digits with optional `_` subscripts (`m`, `T_oil`,
`omega_r`, `x_hat`, `C_build`). Anything else is an expression and is
skipped: `T_c = 6`, `10^9`, `h^2`, `1 / T_s`, and every function
application (`m(0)`, `f(T_k)`, `P(A)`; design review: an "identifier
arguments" rule had no principled line in appendix A). A `## Symbols`
row may still name any mapping key, so chapter 1 records
`` | `r(t)` | **Residual** | `` and the List of Symbols prints it; the
completeness finding just does not ask for one.

**Code.** A new stdlib-only module
`chitragupta/render_output/_math_symbols.py` (`_math.py` is at 207 of
C2's 250 lines): `symbols_section(text)`, `load_symbols(text)` returning
`{symbol: Meaning(kind, text, note, line)}` with `kind` in
`link`/`see`/`text`, `is_bare_symbol(key)`, `glossary_section(text)` and
`glossary_spans(draft)`. It may not import `chitragupta/dossier/`, the
same boundary `_math.py` keeps. **One section reader:**
`glossary_section(text)` (heading to next `##`, HTML comments blanked,
line numbers kept) moves here from `dossier/_glossary._section`, which
calls it (dossier -> render_output is the allowed direction).
`glossary_spans` reads `scope.md` beside `math.md` through it. The
`- draft digest:` line `dossier stamp` appends inside `## Glossary` is
dropped by `glossary_spans`: an all-digit or `1e5`-shaped digest would
otherwise read as a quantity on some stamps and not others. The pattern
is duplicated from `_draft_fingerprint._DRAFT_DIGEST_LINE`, which this
module may not import, with a comment naming its owner.

## 2. Findings

### The orphan rule (render and `dossier status`)

A mapping row is used when:

- **any key** appears exactly as a span or displayed block in the
  draft, *or* as a span in the glossary;
- **a bare-symbol key** also when it occurs as a whole token
  (`(?<![A-Za-z0-9_])` + `re.escape(key)` + `(?![A-Za-z0-9_])`) inside a
  **mapped** span or block, of the draft or the glossary. So `T_r` is
  used through `T_r = 10`, and becomes an orphan again once the last
  formula holding it goes; a code span such as `range(n)` or
  `sleep(t)` keeps no single-letter row alive (design review).

A `## Symbols` row does **not** count as a use; if it did, a symbol
deleted from the draft would keep both rows alive forever.
`_math_findings.findings()` gains a `glossary` argument (the spans) and
`_draft_fingerprint._math_desync` passes it, so a glossary-only row is
not desync.

### `render`: `[math]` warnings, never fatal

| Kind | Message |
| --- | --- |
| `meaning` | `` `T_oil` is mapped in math.md but has no meaning in its ## Symbols `` |
| `meaning` (no section) | `` math.md has no ## Symbols: 68 mapped symbols have no meaning `` (one line) |
| `unmapped` | `` `T_r` has a meaning in ## Symbols but no row in the mapping table, so it cannot be typeset `` |
| `malformed` | `` ## Symbols row `x` has no meaning `` / `` `x` has two ## Symbols rows `` |

`dossier status` keeps selecting `orphan` only. These print wherever
`[math]` findings print today, `_checked_math_mapping`, which runs for
the formats that reach pandoc (pdf, tex, docx, html), not for
`--format md`; "every draft" in decision 8 means standalone drafts as
well as units, not every format.

### `registry check`: `[notation]` and `[glossary]`, exits 0

- the per-unit `meaning`, `unmapped` and `malformed` findings, prefixed
  with the unit id;
- ``03 math.md `r` links to **Residuall**, which no glossary in the book defines``;
- ``03 math.md `m_lo` points at 02-plant-demonstrator, which ...``: is not
  an accepted unit / has no ## Symbols row for it / points on itself
  (no chains: a pointer must land on a link or free-text row);
- the existing "`x` names different things" and "`x` is typeset
  differently" findings, now over the resolved Symbols rows: the meaning
  is the linked term's `term_key` or the free text lowercased, **plus
  the lowercased note**, the same key the List of Symbols groups rows
  by, so the page and the check cannot disagree; LaTeX is each unit's
  own mapping;
- **glossary maths**: a glossary span with no row in its own unit's
  mapping, not in its "Not mathematics" table, that
  `_math_shapes.rule_for(span, symbols, True)` calls mathematics:
  ``01 glossary span `(M_0 - M_1) * c` looks like a quantity (...) but has
  no row in 01's math.md, so it prints as code``. No new rule; rows are
  never borrowed from another unit;
- `[glossary]` for a retired spelling, with the replacement row:
  ``05 scope.md:19 `- **Event time** (`t_e`) -- ...` -- symbols live in
  math.md now: add | `t_e` | **Event time** | under ## Symbols`` (for a
  symbol-only bullet: as free text, and drop the bullet).

### `registry build --glossary/--notation` refuse on

any `[glossary]` problem (as today, now including retired spellings),
an unresolved link or pointer, an `unmapped` symbol (it would print as
code), and a `malformed` row (with two rows, which meaning prints is
undefined). A pointer to a unit not yet accepted therefore refuses
until it is; WRITE-A-BOOK's migration note says so. A missing meaning
does **not** refuse: the symbol is absent from the List of Symbols and
`check` has said so.

## 3. The pages

`_terms.read_unit` stops reading a symbol from the glossary and reads the
unit's `## Symbols` into `built["symbols"]`: `{symbol, unit, kind, text,
note, line, typeset, symbol_markdown, text_markdown}`, where `typeset` and
the Markdown come from the unit's own mapping. A new
`chitragupta/registry/_symbols.py` resolves them: a link to the matching
`term_key` among all units' terms, a pointer to its target's row (taking
the target's meaning). It returns the resolved rows and the findings
above, and is where `_terms`' notation findings move.

- **Glossary.** A definition carries the symbols its **own unit** links
  to its term. When every definition of a term carries the same symbols
  (or there is one definition), they print once in the heading:
  `Moisture thresholds (m_lo, m_hi)`. Otherwise each numbered
  definition starts with its own: `1. (r(t)) the difference ...
  (Chapter 1)`, `2. (r) in this chapter ... (Chapter 2)`. Identical
  definitions merged across units carry the union of their units'
  symbols, in outline order. A unit that
  links a term without defining it adds nothing to the Glossary. A term
  no row links to prints as it does today.
- **List of Symbols.** One row per (symbol, meaning key), in the
  existing order; its units are the units holding a `## Symbols` row
  for that symbol whose resolved meaning key matches (link, free text
  or pointer), in outline order. A unit that only defines the term in
  its glossary contributes nothing: chapter 1 is listed under `r(t)`,
  not under `r`; the symbol is typeset from the first defining
  unit's mapping; the label is the term as the glossary spells it, plus
  `, note`, or the free text through its unit's mapping. A symbol with
  two meanings gets two rows, as today, and is reported.
- **`registry excerpt`** also returns the other units' resolved Symbols
  rows, so a unit being drafted sees the notation already settled.

**`dossier/_glossary.py`.** `_GLOSSARY_TERM` and `_entry` keep matching
all three spellings, so `_reason` can quote the replacement row and
`registry._prose()` still drops definition bullets from the claim
register; only `Entry.symbol` goes from the public shape. The
glossary-maths rule (`rule_for` over glossary spans) lives in
`registry/_symbols.py`, keeping `_math_findings.py` (179 code lines)
clear of C2 once the token rule is added.

## 4. Skills and docs

- `.claude/skills-common/references/figures-tables-equations.md` §6: a
  short subsection on `## Symbols` (one row per mapped bare symbol;
  bold link, note, `see`, free text; no symbols in the glossary or House
  style). Every genre skill already points there.
- SKILL.md edits only where a sentence becomes false: `draft-reviser`'s
  finding table (`meaning`, `unmapped`, the orphan row);
  `book-assembler` and its `references/latex-conventions.md` (the List
  of Symbols reads `math.md`); `deep-research`'s merge of `math.md` rows
  at synthesis also merges `## Symbols`. The `.agents/` and `.opencode/`
  copies follow; `tests/test_skill_size.py` stays green.
- `dossier init`'s `scope.md` template: the glossary example loses its
  slot bullet.
- `docs/WRITING-STANDARDS.md` §12: the Symbols table, its forms, the
  token rule. `docs/WRITE-A-BOOK.md`: the registry row and "The Glossary
  and the List of Symbols", with a migration note. `docs/RENDERING-FLOW.md`
  if it describes what `math.md` holds.
- **`docs/DOSSIER.md` (#1142):** a section for each file that has none:
  `README.md`, `scope.md`, `rejected.md`, `steering.md`, `revisions.md`,
  `retrieval.md`, `outline.md`, `math.md`. Each: who writes and reads it,
  its format with a short example, what a drafting step may and may not
  do with it, what goes wrong when it is missing or stale. `scope.md`'s
  covers the glossary shapes and states the slot's retirement;
  `math.md`'s the three tables; `steering.md`'s the "Moved from the
  glossary" use. The summary table stays.
- `CHANGELOG.md` with a migration section; version **6.159.0**.

## 5. Tests

Test first, `fail_under = 100`.

- `tests/test_render_output_math.py` (or a new
  `test_render_output_math_symbols.py`, one per source module): section
  splitting, a backticked meaning not read as a mapping row, the three
  forms and the note, empty meaning, duplicate row, bare-symbol rule
  (`r(t)` yes, `m(0)` no), the token orphan rule both ways, glossary
  spans as uses, the summary line, the import-boundary pin.
- `tests/test_dossier_glossary.py`: `Entry` has no symbol; the three
  retired spellings are problems with the replacement row.
- `tests/test_registry.py`: cross-unit link, unresolved link, pointer
  to a missing unit / missing row / another pointer, LaTeX mismatch
  through a pointer, `P` clash on meaning keys, glossary maths flagged
  and code quiet, `build` refusals and the non-refusal on a missing
  meaning, `excerpt` symbols.
- `tests/test_registry_pages.py`: A1, B1, a linking non-defining unit,
  a pointer unit in the List of Symbols, EC unchanged, two `P` rows.
- the staleness tests: glossary-only and token-used rows are not desync.

**Real-data smoke** (not committed): `registry check` on a scratch copy
of the digital-twins dossiers lists the retired slots, the House-style
symbols as missing meanings and the 16 glossary spans; units 02 and 03
migrated by hand then build both pages, every symbol as maths in the
PDF.

## After the release: the digital-twins dossiers

In `chitragupta-drafts`, per unit: slots and symbol bullets become
`## Symbols` rows; House style inventories become rows plus a one-line
pointer; missing meanings, `unmapped` rows and glossary-maths rows are
added; the pages are rebuilt. Unit 3's draft is not touched; its
`scope.md` and `math.md` may be. A lessons comment goes on #1143.

## Design review

Reviewed 2026-11-05 by an independent agent; verdict "changes required",
fourteen findings, none reopening a decision. All are folded in above:
the token rule counts only mapped spans and escapes the key; function
applications are expressions; the clash key includes the note;
`malformed` refuses `build`; the render path's format scope is stated;
List of Symbols units are defined by `## Symbols` rows; one glossary
section reader; `_GLOSSARY_TERM` keeps matching the slot; ordering of
`## Symbols`, `\|` escaping, pointers to unaccepted units and merged
definitions' symbols are stated.

Re-review the same day: **sign-off**, with one should-fix folded in
(`glossary_spans` drops the `- draft digest:` line).

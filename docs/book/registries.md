# 📖 Build the registries

Status: **tutorial**, step 5 of [Write a book](../WRITE-A-BOOK.md).

**Written for** anyone about to assemble a book, or checking one that
is half written. **Assumed:** at least one accepted unit
([step 4](chapters.md#-step-4-accept-the-unit)). **Not covered here:**
why a registry finding never blocks; that is in the
[design notes](design-notes.md#-why-registry-check-exits-0-when-the-two-status-commands-do-not).

## ▶ Step 5: build and read the registries

```bash
chitragupta draft registry build content/drafts/twins
chitragupta draft registry check content/drafts/twins
```

On the 15-chapter book described [below](assemble.md#-what-one-real-book-looked-like),
`check` printed:

```text
Consistency check -- evidence for a judgement, not a verdict.
  15 of 15 unit(s) accepted and read.
  [claim] the same claim is made in 13-standards, 14-running: "Diagnostic
          twins of this shape run on operational assets [@stadtmann_2024]..."

  1 finding(s). Nothing here blocks anything.
```

Three registries, written under `content/specs/<book>/registries/` by a
deterministic pass over **accepted units only**:

| Registry | Written from | Flags |
| --- | --- | --- |
| terminology and notation | each unit's `scope.md` `## Glossary` (`- **Term** -- definition`) and its `math.md` `## Symbols` table | a term defined more than once, a symbol naming two things or typeset two ways, a symbol link or `see` pointer that resolves to nothing, a mapped symbol with no meaning, a glossary span that is mathematics with no row, a glossary bullet in another shape, a unit with no glossary |
| claims | every sentence that cites something | the same claim made in more than one unit |
| cross-references | `[text](#id)` and `\ref{id}`/`\cref{id}` | a reference no unit or outline entry defines |

Three properties hold for all of them:

- **Built from accepted units only**, and the count is printed, naming
  the ones it could not see. A registry over half a book is not the same
  claim as one over all of it.
- **Nothing here is written by an LLM.** They are a deterministic reading
  of accepted units and their dossiers' glossaries and `math.md`
  files, which is why they
  can be trusted: the same standing
  `chitragupta/ledger.py` has as a reading of a real bib file.
- **The conventions are borrowed.** The glossary parser is the one
  the acronym checks use (`chitragupta/dossier/_glossary.py`), the
  sentence splitter is the provenance aid's,
  and everything from a `## References` heading onward is cut the way
  `chitragupta/acronyms.py` cuts it, measured there against the real
  15-chapter book, because a rendered reference list is all
  citation-bearing lines and would otherwise fill the claim register with
  bibliography.

**A cross-reference is never spelled `@id`.** That is a citekey position:
a section id reaching it would put something the ledger has never seen
where only a real bibliography entry may go. `tests/test_registry.py`
pins that the citation gate reads neither supported reference syntax as a
citekey.

`check` exits 0 however much it finds
([why](design-notes.md#-why-registry-check-exits-0-when-the-two-status-commands-do-not)),
and there are things it structurally cannot see
([which](design-notes.md#-what-the-registries-cannot-see)).

### 📖 The Glossary and the List of Symbols

The same pass writes the book's two reference pages when asked:

```bash
chitragupta draft registry build content/drafts/<book> \
    --glossary content/rendered/<book>/glossary.tex \
    --notation content/rendered/<book>/notation.tex
```

Both are read from the units' `scope.md` glossaries and `math.md`
`## Symbols` tables and nothing else, so every word on them is a
definition or meaning a unit's author pinned. Since #1143 a symbol
lives only in `math.md`, the file that already says how to typeset it:

```markdown
## Symbols

| Symbol | Meaning |
| --- | --- |
| `M_0`  | **Baseline** |
| `m_lo` | **Moisture thresholds**, lower |
| `T_c`  | see 02-plant-demonstrator |
| `x_k`  | the state at step k |
```

A bold term links to the glossary entry that defines it, in any
accepted unit; text after a comma tells two symbols of one term apart;
`see <unit>` reuses that unit's row for the same symbol, and must
typeset it the same way; anything else is the meaning in words.
[WRITING-STANDARDS.md §12](../WRITING-STANDARDS.md#-symbols-what-each-mapped-symbol-means)
has the rules.

- **Glossary:** alphabetical. A term with several definitions prints
  each, numbered, in outline order; each definition ends with its
  chapter as `\Cref{<unit-id>}`; identical definitions print once with
  every chapter. A term's symbols are the `## Symbols` rows linking to
  it from the unit whose definition it is: in the heading,
  "Moisture thresholds (*m*<sub>lo</sub>, *m*<sub>hi</sub>)", or before
  each numbered definition when units use different ones (`r(t)` in one
  chapter, `r` in another).
- **List of Symbols:** one table for the whole book. A symbol with one
  meaning is one row listing every chapter with a `## Symbols` row for
  it; a symbol naming different things gets a row per meaning.
- **Typesetting:** each definition and symbol goes through its own
  unit's `math.md` mapping, then pandoc, so `M_0` looks the same on the
  page as in the chapter.

**A glossary bullet in another shape stops the build.** `--glossary`
and `--notation` write the three registries, then refuse (exit 1, no
page written) if any accepted unit's glossary holds a bullet they cannot
print: `**Term**:` instead of `**Term** --`, several terms in one
bullet, a definition that is empty or carries a citekey, or a symbol in
the bullet. So does a `## Symbols` row whose link or pointer resolves
to nothing (a pointer to a unit not yet accepted included), that has no
mapping row and would print as code, or that is empty or repeated. A
mapped symbol with no meaning does not stop it: it is missing from the
List of Symbols, and `check` says so. `check` reports all of these and
still exits 0. That is a build refusing to write a
page it would have to leave terms out of, the way `render` refuses an
unmapped `<!-- math -->` marker, not a check blocking; the fix is the
unit's `scope.md`, through `draft-reviser`.

**Moving a book written before #1143.** The glossary symbol slot
(`- **Baseline** (`M_0`) -- ...`, `- **Baseline (`M_0`)** -- ...`) and
the symbol-only bullet (`- **`x_k`** -- ...`) are retired. `registry
check` names each with the row to write instead; move it into the
unit's `math.md` `## Symbols`, add a mapping row for any symbol that has
none, and give every other mapped symbol a meaning. A symbol list kept
in `scope.md`'s House style is no longer read by anything: move it into
the table too and leave a one-line pointer.

**Glossary terms belong to numbered chapters.** Each definition ends
with `\Cref{<unit-id>}`, which prints "Chapter 3" or "Appendix A". A
front- or back-matter page carries no number, so a term defined there
would print a reference to nothing. A front- or back-matter unit with no
`## Glossary` is therefore not reported (a hand-written preface has no
dossier at all), and one that *does* define terms is a `[glossary]`
finding: move the term to the chapter that introduces it.

Where these two pages print, and how to leave one out, is the outline's
call: [back matter](back-matter.md).

**What the pages cannot catch:** a qualifier inside a well-formed term
(`**Digital twin (DT), working definition for Part I** -- ...`) and a
definition that only says "as before". Both print as written, so read
both pages before the second sign-off.

Next: [assemble, build and sign off the book](assemble.md).

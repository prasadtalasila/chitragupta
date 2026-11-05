# 🔎 The index

Status: **workflow**, part of [Write a book](../WRITE-A-BOOK.md).

**Written for** an author whose book should end with a subject index,
and anyone reading the report it leaves. **Assumed:** a working outline
([step 1](outline.md)) whose chapters have glossaries
([step 5](registries.md#-the-glossary-and-the-list-of-symbols)).
**Not covered here:** where the index sits among the other reference
pages ([back matter](back-matter.md)), and the LaTeX the assembler
writes for it (`.claude/skills/book-assembler/references/latex-conventions.md`,
"The index").

## 🧭 What you get

A back-of-book index, the book's last page, built from the terms your
chapters already define. Every glossary term is an entry. Its page
numbers are:

- the page where its **defining chapter** first mentions it, in **bold**;
- and, in any other chapter or appendix that mentions it at least twice,
  the page of that chapter's first mention.

A term mentioned once in passing in another chapter gets no page there,
because a passing mention is not where a reader should be sent. An
abbreviation in the glossary ("Digital twin (DT)") becomes a
cross-reference: "DT, *see* digital twin".

Nothing comes from the corpus or a keyword extractor: only your
glossaries, plus what you add in `index.toml`. Front and back matter (a
preface, "About the author") are not indexed, and neither are headings,
figure and table captions, code, maths, citations, or the sections named
"Exercises" and "Solutions".

## 🗺 How it is built

```text
scope.md glossaries ─┐
math.md ## Symbols ──┼─► registry build --index ─► rendered/<book>/index-terms.json
specs/<book>/index.toml ┘        (validates; exit 1 on bad toml)
                                              │
<unit>.md ─► render --fragment --index-terms ─┤─► <unit>.tex   (\index{t017} …)
                (Lua: match, count, place)    └─► <unit>.index.json  (sidecar: counts, casing)

book.tex ─► lualatex ─► bibtexu ─► lualatex ─► lualatex ─► book.idx
                                                 │
            registry index book.idx ◄────────────┘  (Python: ids → sort@printed, see/parents,
                 │                                    quoting; runs upmendex -s .ist)
                 ├─► book.ind ─► lualatex ─► book.pdf
                 └─► specs/<book>/registries/index.md + index.json  (report)
```

Three stages, each talking to the next only through a file:

1. **The term table.** `registry build --index` reads every accepted
   chapter's `scope.md` glossary and `math.md` `## Symbols`, applies
   `content/specs/<book>/index.toml`, and writes `index-terms.json`: one
   id per term (`t` and eight hex digits, a hash of the term), the
   spellings that count as it, and the chapters that define it. A
   `index.toml` that names a term, chapter or target that does not exist
   refuses the build and writes nothing.
2. **The chapters.** Each chapter and appendix is rendered with
   `--index-terms`. A pandoc filter, `assets/pandoc/index_terms.lua`,
   finds every mention, counts them, and places one `\index{t017}` at
   the first mention of each term that qualifies in that chapter. It
   writes only the id, never the term: an entry can fall inside a
   footnote, where a `%` or `&` in a printed term would break the
   LaTeX. Beside each fragment it leaves a sidecar,
   `<unit>.index.json`: the counts, which terms it placed, and how each
   mention was capitalised.
3. **The index.** LuaLaTeX writes each `\index{}` to `book.idx` with
   its page. After the pages have settled (the fourth pass, once the
   bibliography and cross-references are in), `registry index` turns
   each id into the printed entry, writes `book-index.idx` and
   `book.ist`, and runs `upmendex`, which sorts and groups them into
   `book.ind`. A last `lualatex` pass prints it. The same step writes
   the report.

The split is why the index can be both safe and tidy: the filter, which
sees one chapter at a time, decides only *where* a term is; how it
prints (its casing, sort order and sub-entries) needs the whole book,
so it is decided once, after typesetting.

The book-assembler skill runs all of it when the outline has
`### Index {#index}`, and none of it when the line is gone.

### 🔤 Matching

A mention counts across a line break, inside emphasis, links and
quotes, with a hyphen or dash for the space ("digital-twin"), with a
possessive ("the twin's state"), and in either grammatical number on its
last word ("lifecycle phase" for "lifecycle phases"). At each word the
longest term wins and mentions never overlap, so "the digital twin" is
a mention of *digital twin* and not of *twin*. An irregular plural
("analyses") needs a `[variants]` line.

### 🖨 How a term prints

- **Casing is the book's own.** A glossary line starts with a capital
  ("Decision"); the index prints a word the way most of its
  mid-sentence mentions do, so "decision" but "Markov chain". A tie, or
  no mid-sentence mention, lowercases a first word that is just a
  capital and lowercase letters ("Ecological twin", not "MODBUS RTU"),
  and the report names each such guess, since a proper noun the prose
  never uses mid-sentence ("Kalman filter") is the one it gets wrong.
  `[print]` overrides all of it.
- **A leading article is inverted**: "The four criteria" prints as
  "four criteria, the" and sorts under F.
- **Symbols** follow the term, as in the Glossary: "state vector (*x*)".
- **Sorting** is word by word, the *Chicago Manual of Style* default;
  `sort = "letter"` switches to letter by letter. Greek sorts by its
  name, so ε-greedy files under E.
- **Sub-entries** exist only where `[parent]` declares them; the parent
  prints once, with its children under it.
- **A footnote's page** prints as a plain page number, not "12n".

## ✏ `index.toml`

`spec init` copies a commented sample to `content/specs/<book>/index.toml`;
only `[settings]` is live in it, so out of the box the index is the
glossary alone. Every table is optional. Terms are named the way the
glossary matches them: case-insensitive, spacing collapsed, a trailing
"(DT)" dropped. Chapters are named by their outline id. Editing the
file after the outline is signed needs no new sign-off: the index
changes no prose.

```toml
[settings]
min_mentions = 2          # outside the defining chapter
sort = "word"             # or "letter"
letter_headings = false   # true: a bold A, B, C between groups
skip_sections = ["Exercises", "Solutions"]

[variants]                # extra spellings that count as the term
"analysis" = ["analyses"]

[restrict]                # an everyday word: count only these phrases
"service" = ["digital twin service", "twin service"]

[always]                  # chapters that get a page below min_mentions
"staleness" = ["a1-the-mathematics-you-need"]

[print]                   # the printed form, when the casing rule is wrong
"i2c" = "I²C"

[parent]                  # sub-entries; children keep their own entries too
"stage" = ["stage 0", "stage 1", "stage 2", "stage 3"]

[parent_only]             # ...unless their parent is listed here
"stage" = true

[see]                     # entries with no page numbers of their own
"shadow" = "digital shadow"

[see_also]
"digital shadow" = ["digital model", "digital twin"]

[drop]                    # glossary terms kept out of the index
terms = ["two-question test"]

[add]                     # terms in no glossary, indexed like glossary terms
terms = ["Kalman filter"]
```

`registry build --index` refuses, listing every problem and writing
nothing, when:

- a table or key is unknown (`[variant]`), or a value has the wrong
  shape, or `min_mentions` is below 1;
- a table names a term in no glossary and not in `[add]`, or `[add]`
  repeats a glossary term;
- one spelling belongs to two terms;
- an `[always]` chapter is not an accepted unit;
- a `[see]` source is itself an indexed term (a *see* entry has no page
  numbers, *Chicago* 15.16), or a target does not exist;
- a `[parent]` child is dropped, or `[parent_only]` names no parent.

## 📋 The report

Every `registry index` writes `content/specs/<book>/registries/index.md`
and `index.json`, beside the other registries, and prints one line:

```text
index: 523 entries, 7 findings -> content/specs/<book>/registries/index.md (+ .json)
```

`index.md` lists the findings, each with the `index.toml` line that
answers it, then every term with the chapters that got a page and the
ones that mentioned it too rarely. `index.json` holds the same, for an
agent asked to "apply the index findings for service and staleness".
Nothing in it blocks anything:

| Finding | Means | The fix it prints |
| --- | --- | --- |
| `no-locator` | the term occurs nowhere in the indexed chapters | `[drop]`, or a `[variants]` spelling |
| `generic` | the term has pages in at least three quarters of the chapters | `[drop]` or `[restrict]` |
| `below-threshold` | a chapter mentions it, but fewer than `min_mentions` times | `[always]` |
| `mixed-case` | its mid-sentence mentions are capitalised more than one way | `[print]` |
| `casing-guessed` | no mid-sentence mention, so its first word was lowercased on no evidence | `[print]`, if it is a proper noun |
| `family` | three or more terms share a first or last word | `[parent]` |
| `unused` | an `index.toml` spelling or `[always]` chapter matched nothing | remove it |
| `not-indexable` | the glossary term holds maths, which prose cannot match | `[variants]` |
| `dangling-see` | a cross-reference points at a term with no page | fix or remove it |

`registry index` refuses, writing nothing, on a stale build: a chapter
rendered without `--index-terms`, or against an older term table, or a
`book.idx` holding an id the table no longer has. Rebuilding the table
and re-rendering the chapters (the assembler's steps 3 and 4) fixes it.

## ✂ Turning it off

Delete `### Index {#index}` from the outline. The assembler then builds
no term table, renders no chapter with `--index-terms`, loads no
`imakeidx` and runs no `upmendex`: the build is the four passes it
always was. Outlines written before #1168 have no such line, so they
are unchanged.

## 🧰 What it needs

`upmendex` (TeX Live's `texlive-binaries`) and `imakeidx.sty`
(`texlive-latex-extra`). `chitragupta install os-deps` installs both and
fails, naming the missing one, if either is absent; `chitragupta doctor`
reports `upmendex`. On Windows, MiKTeX ships `upmendex` as its own
package, `miktex-upmendex-bin-x64` ([WINDOWS.md](../WINDOWS.md)).

## 🚧 What it does not do

- **Page ranges.** A long discussion gets the page of its first
  mention, not "41-47".
- **Locators from headings.** A section titled with the term is not
  preferred over its first mention in prose.
- **Choose terms for you.** Statistical keyword extraction was weighed
  and set aside: on this project's own corpus it produced generic words
  and body-text noise (`chitragupta/enrich/keyword_extract.py`'s
  docstring). A term worth indexing that no glossary defines goes in
  `[add]`.

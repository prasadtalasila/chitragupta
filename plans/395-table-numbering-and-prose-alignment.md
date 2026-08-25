# 🔢 Table numbers, and prose that reads them

Status: **plan.** Written 2026-08-25, for issue 395.

A draft's tables carry no number and no caption today, so a rendered
`.tex` or `.pdf` has nothing a sentence can point at -- and no sentence
points at one. This is the contract that fixes both halves: where a
caption lives, where a number comes from, and what reports a table
nobody explains.

**Written for** whoever implements it -- `chitragupta/render_output/`,
`chitragupta/style_check.py`, `chitragupta/review/_claims.py` and the
genre skills all move together, and the order matters.
**Assumed** you have read
[docs/RENDERING-FLOW.md](../docs/RENDERING-FLOW.md), whose "two paths
through `render()`" is the fact the whole design turns on, and
[docs/WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md) §10, whose
figure pair this deliberately imitates. **Not covered here:** figure
numbering, which has the same defect and is not in scope (see "What
this deliberately leaves alone").

## 🧭 Table of contents

- [The defect, measured](#-the-defect-measured)
- [What was verified before choosing](#-what-was-verified-before-choosing)
- [The contract](#-the-contract)
- [What the renderer does, per format](#-what-the-renderer-does-per-format)
- [The `.tex` fragment carve-out](#-the-tex-fragment-carve-out)
- [What reports a table nobody explains](#-what-reports-a-table-nobody-explains)
- [Where the review layer would start lying](#-where-the-review-layer-would-start-lying)
- [Rejected alternatives](#-rejected-alternatives)
- [What this deliberately leaves alone](#-what-this-deliberately-leaves-alone)
- [Build order](#-build-order)

## 📊 The defect, measured

`content/drafts/digital-twins-for-software-engineers/survey.md:131` is
this pipeline's flagship comparison table. It is a bare pipe table: no
caption line, no id, no number. Rendered,
`content/rendered/digital-twins-for-software-engineers/survey.tex:235`
opens `\begin{longtable}` with no `\caption` -- LaTeX numbers what it is
given a caption for, so the table is unnumbered in `.tex` and in the
`.pdf` built from it.

The second half of the issue is the same absence read from the prose
side. Across every real draft in `content/drafts/`, the string "Table"
followed by a number appears **nowhere**; the closest any prose comes is
"a comparison table" as a figure of speech
(`book-chapters/digital-twin-platforms/digital-twin-platforms.md:62`).
A reader meets a nine-row table with no sentence saying what it is for
and no sentence reading a pattern off it.

## 🔬 What was verified before choosing

Run against this host's pandoc 3.1.11.1 and pdflatex, not inferred:

| Question | Answer |
| --- | --- |
| Does a pandoc caption line number a table? | Yes. `: Where to start.` under the table emits `\caption{Where to start.}` inside `longtable`, and the pdf reads "Table 1: Where to start." |
| Can the caption carry an id, pandoc-crossref style? | **No.** `: Caption {#tbl:start}` puts the literal `\{\#tbl:start\}` *inside* `\caption{}`. Pandoc has no table-attribute syntax in its Markdown reader |
| Does raw LaTeX in a Markdown caption survive? | Yes. `: Where to start.\label{tab:start}` emits `\caption{Where to start.\label{tab:start}}`, and `Table~\ref{tab:start}` in prose resolves to "Table 1" in the built pdf |
| Does the docx writer number a table? | **No.** A captioned table round-trips as a bare "Where to start." paragraph -- pandoc numbers nothing outside LaTeX |
| Does a `.tex` fragment's `\ref` survive to a `.md` preview? | Yes. Pandoc's LaTeX reader resolves it itself: `\ref{tab:s}` becomes `[1](#tab:s)`, and the caption is kept |

Two consequences fall straight out. Numbers cannot be typed into the
caption text -- `: Table 1: Where to start.` renders as "Table 1: Table
1: Where to start." And numbering cannot be left to pandoc outside the
LaTeX-bound formats, because outside them pandoc does not number.

## 📐 The contract

**The caption is visible text in the draft; only the id hides in a
marker.** A Markdown draft writes the table, then a native pandoc
caption line, then the marker on its own line directly below it -- no
blank line between, the same adjacency
[WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md) §11 already uses
for `<!-- single-source: -->`:

```markdown
| Starting point | Citekey | Core idea | Stated limitation |
|---|---|---|---|
| DTaaS platform | `talasila_realising_2024` | ... | ... |

: Where to start when building a first twin.
<!-- table: start-here -->
```

Prose points at it with an inline marker, which expands to the whole
reference phrase -- the author writes no number and no word "Table":

```markdown
The platforms in <!-- tableref: start-here --> differ mainly in what
they ask you to bring.
```

**Why the caption is not inside the marker.** A caption may cite, and
`chitragupta/citation_gate.py` is the one gate this project has. Text
inside an HTML comment is still text the gate reads, but a caption is
prose a reader is meant to see -- burying it in a comment would make
the draft on disk misleading about what the rendered document says. The
id is not prose and nobody reads it, so the id is what hides.

**Ids are kebab-case and unique within a draft** (`[a-z0-9][a-z0-9-]*`).
Uniqueness is per draft, not per book: `book-assembler` composes units
that were each numbered independently, and two units may not share an
id, because both become `\label{}`s in one LaTeX document and a
duplicate label silently resolves to the wrong table.

**Numbers are never written by an author.** They are assigned by
document order of `table:` markers, which is the order LaTeX's own
counter runs in, so the two agree on order. They do not agree on
*format*, and that is deliberate rather than a defect to fix: an
`article` render numbers "Table 3"; the same unit inside an assembled
`book` numbers "Table 2.1" where chapters are numbered, and "Table 5" --
flat, book-wide -- where `book-assembler` has suppressed chapter
numbering with `\setcounter{secnumdepth}{-2}` for units that number
their own headings. Both measured with `pdflatex`. The consuming
document's convention wins, which is the whole reason numbering is not
baked into the draft.

## 🖨 What the renderer does, per format

`chitragupta/render_output/_tables.py`, beside `_figures.py` and
`_math.py`, substituting into the temp copy only. Unlike `_math.py`'s
single "does this reach pandoc?" predicate, this needs three cases,
because the md path never reaches pandoc and pandoc numbers nothing
outside LaTeX:

| Draft | Output | Caption line becomes | `tableref` becomes |
| --- | --- | --- | --- |
| `.md` | `tex`, `latex`, `pdf` | `: <caption>\label{tab:<id>}` -- LaTeX numbers it | `` `Table~\ref{tab:<id>}`{=latex} `` |
| `.md` | `md` (never reaches pandoc) | `**Table N:** <caption>`, an ordinary paragraph | `Table N` |
| `.md` | `docx`, `html`, anything else | `: Table N: <caption>` -- still a real caption, with a literal number pandoc will not supply | `Table N` |
| `.tex` | any | untouched | untouched |

The marker line is removed in every case; it is vocabulary for this
pipeline, not content for a reader.

Warnings print with a `[table]` prefix on stderr, beside `[figure]` and
`[math]`, and -- like `_figure_warnings` -- they are emitted **before**
`render()`'s Markdown-to-Markdown early return, so the one path that
skips pandoc still reports a marker with no caption above it.

## 📄 The `.tex` fragment carve-out

`thesis-chapter-writer`'s `.tex` fragment writes a real LaTeX table and
carries no marker at all:

```latex
\begin{table}
\caption{Where to start when building a first twin.}\label{tab:start-here}
\begin{tabular}{llll}
...
\end{tabular}
\end{table}
```

Nothing is substituted, for the same reason §10 keeps that genre's TikZ
inline: the fragment is what the user `\input`s into their own thesis,
where their own `pdflatex` numbers the table consistently with their
other chapters. The `.md` preview needs no help either -- pandoc's
LaTeX reader numbers `\ref` itself (verified above).

So the marker vocabulary is Markdown-only. There is no `%table:`
spelling, and that asymmetry with `figure:` is the point rather than an
oversight: a figure marker exists because a TikZ picture cannot render
in Markdown, and a LaTeX table has no equivalent problem.

## ✅ What reports a table nobody explains

`python -m chitragupta.draft style` grows table findings, in a new
`chitragupta/style_tables.py` reached from `style_check.check()` --
advisory, exits 0 whatever it finds, like everything else in that
command. `chitragupta/style_acronym_drift.py` is the precedent: a
finding computed in plain Python rather than by Vale, because the fact
it checks is not in Vale's reach.

| Finding | What it catches |
| --- | --- |
| `chitragupta.TableNoCaption` | A pipe table with no caption line -- the state every draft is in today |
| `chitragupta.TableNoId` | A caption with no `table:` marker under it, so nothing can refer to it |
| `chitragupta.TableDuplicateId` | Two tables claiming one id; in a book unit this is a silently wrong `\ref` |
| `chitragupta.TableMalformedId` | An id that is not kebab-case |
| `chitragupta.TableUnreferenced` | **The issue's second half**: a table no sentence points at |
| `chitragupta.TableUnknownRef` | A `tableref` naming an id no table declares |
| `chitragupta.TableRefOutsideSection` | The only reference to a table sits in a different section than the table |

`chitragupta.TableUnreferenced` and
`chitragupta.TableRefOutsideSection` are the prose-alignment half, and
they are as far as a machine can go: that a sentence *points
at* a table is decidable, and whether it *explains* the table is not.
The genre skills carry the judgement half -- introduce the table, then
read a pattern off it -- and WRITING-STANDARDS.md §9's decidable /
not-decidable table gets a row saying exactly that.

**One related fix in the same file.** `style_check.check()` calls
`run_vale()` first, so on a host without the `vale` binary the
`MissingBinary` it raises loses the Python-side findings too --
`style_acronym_drift`'s today, the table findings tomorrow. The Python
findings move ahead of the probe, so a vale-less host gets them and a
warning rather than nothing.

## ⚠ Where the review layer would start lying

Adding a caption line to every draft changes what three review modules
see, and none of them would error -- they would quietly report wrong
things:

- **`chitragupta/review/_claims.py:63`'s `CAPTION`** recognises a
  `Table 2:` lead-in and `\caption{}`, but not a `:`-led pandoc caption
  line. Without a new alternative there, `python -m chitragupta.review
  uncited` reports every caption in every draft as a sentence carrying
  no citation -- a false finding per table, on the aid whose whole
  design problem is alarm fatigue.
- **The inline `tableref` marker** lands mid-sentence, which is new:
  `_claims.COMMENT` only recognises a block that *starts* with `<!--`.
  Inline comments are stripped before sentences are split, so a
  reference neither breaks a sentence in two nor reaches a report as
  markup.
- **`review verbatim`** now sees caption text as prose. That is correct
  -- a caption borrowed verbatim from a source is exactly the kind of
  overlap that scan exists to find -- and needs no change beyond
  knowing it is intended.

## 🚫 Rejected alternatives

- **Type the number into the caption** (`: Table 1: Where to start.`).
  Renders as "Table 1: Table 1: Where to start." in the pdf, because
  LaTeX supplies its own prefix. It also makes every insertion a manual
  renumber, and gives an assembled 15-chapter book fifteen "Table 1"s.
- **pandoc-crossref's `@tbl:id` syntax.** Barred by this project's own
  gate, not by taste: `citation_gate.py:80` matches a bare `@key`, so
  `@tbl:start-here` reads as the citekey `tbl` and fails
  `python -m chitragupta.draft gate` as a fabricated reference. A
  reference syntax that trips the citation gate is not available here at
  any price.
- **A markdown link, `[Table](#tbl:start-here)`.** Degrades more
  gracefully in an unrendered draft than a comment does, and was the
  closest rival. Rejected for vocabulary: this pipeline already has one
  way to name a thing the renderer resolves -- an HTML comment marker
  (`figure:`, `math`, `single-source:`) -- and a second, differently
  shaped one would have to be learned, grepped for and explained
  separately in six skills.
- **Caption text inside the marker.** Hides prose from the reader of the
  draft, and hides a citation from the gate's reader. See "The
  contract".
- **A seventh review aid.** The check is prose conformance measured
  against WRITING-STANDARDS.md, which is `draft style`'s stated job. A
  new aid would also mean editing "six aids" in roughly fifteen places
  (`review.AIDS`, the report-suffix contract, `docs/REVIEW.md`'s "The
  six aids", `ARCHITECTURE.md`, `CLI.md`, `LADDERS.md`) for a check that
  reads no corpus.

## 🧊 What this deliberately leaves alone

**Figures have the same defect and are not fixed here.** A figure marker
becomes a bare `\input{figures/x.tex}` with no `\begin{figure}`, no
`\caption` and so no number -- verified at
`content/rendered/book-chapters/digital-twin-life-cycle-considerations/digital-twin-life-cycle-considerations.tex:499`.
Issue 395 is about tables, the fix is a different one (a float
environment, not a caption line), and bundling them would double a diff
that already spans four layers. Worth its own issue.

**Existing drafts are not migrated.** Every draft in `content/drafts/`
predates this contract and will report `chitragupta.TableNoCaption` on the first
run of `draft style`. That is the finding working, not a regression:
the fix per draft is a `draft-reviser` pass, and the user's own drafts
are not this repository's to rewrite.

## 🧾 What building it taught, that reading could not

Three things were found by rendering a real draft in all four formats,
and each changed the design after this plan was first written:

- **A bare `Table~\ref{}` does not survive.** Pandoc's Markdown reader
  owns `~` -- its subscript syntax -- and escapes it, so the reference
  reaches the LaTeX writer as `Table\textasciitilde{}\ref{...}` and sets
  with a literal tilde. The reference is therefore emitted inside
  pandoc's raw-attribute span, `` `Table~\ref{tab:<id>}`{=latex} ``. The
  `\label` beside it needs no such wrapper and does survive bare, which
  is why this was not obvious from the caption working.
- **Captions must be numbered by position, not by id.** A draft that
  reuses an id would otherwise give its *first* table the second one's
  number -- two "Table 2"s and no "Table 1" -- on top of the duplicate
  the check already reports.
- **A book's table numbers are not one shape.** With chapter numbering
  on, an assembled book reads "1.1", "2.1", "2.2"; with
  `\setcounter{secnumdepth}{-2}`, which `book-assembler` applies for
  units that number their own headings, it reads "1", "2", "3" -- flat
  across the whole book. Both are correct and unique, and both were
  measured rather than reasoned about.

One thing the plan missed and review caught: the style check reads the
draft with fenced code **blanked** (`citation_gate._blank_code`, the same
call `review/_claims.py` makes). Without it, a tutorial showing a pipe
table as an example -- including one demonstrating this section's own
markup -- reports as a real table with no caption.

## 🔨 Build order

Test-first at each step, per DEVELOPER-AGENTS.md:

1. `chitragupta/render_output/_tables.py` -- parsing, numbering,
   substitution, warnings. `tests/test_render_output_tables.py`.
2. Wire into `render_output/__init__.py`: warnings before the early
   return, substitution on both paths, inside `_math.substitute`'s
   existing composition.
3. `chitragupta/style_tables.py` plus the `style_check.check()`
   re-order. `tests/test_style_check_tables.py`.
4. `chitragupta/review/_claims.py`: the caption alternative and the
   inline-comment strip, with the existing claim tests extended.
5. Prose: WRITING-STANDARDS.md's new §13 (appended, not inserted --
   §10 and §11 have 52 cross-references between them), RENDERING-FLOW.md's
   format matrix, CLI.md's `draft style` findings.
6. The skills: the five Markdown genres and `book-assembler` learn the
   marker and the explain-the-table rule; `thesis-chapter-writer` learns
   the LaTeX form; `draft-reviser` learns that numbers renumber
   themselves and ids must not be reused.
7. One real end-to-end render of a scratch draft to `md`, `tex`, `pdf`
   and `docx`, checked for the number in each.

# ✍ Write a book, start to finish

Status: **tutorial.**

**Written for** someone drafting a document larger than a chapter with
this pipeline. **Assumed:** nothing about this pipeline, though a book is
the one genre where doing a single chapter first
([a textbook chapter](WRITE-A-TEXTBOOK-CHAPTER.md) is the usual one) will
save you a false start. [AGENTS.md](../AGENTS.md) has the drafting
layer's contract and [ARCHITECTURE.md](ARCHITECTURE.md) the four layers,
but you do not need either to follow the steps below.

Sister tutorials, for the chapters this book is made of:
[a survey](WRITE-A-SURVEY.md),
[a thesis chapter](WRITE-A-THESIS-CHAPTER.md),
[a textbook chapter](WRITE-A-TEXTBOOK-CHAPTER.md),
[a tutorial](WRITE-A-TUTORIAL.md),
[a deep-research report](WRITE-A-DEEP-RESEARCH-REPORT.md).

A book is a signed outline, one authored chapter per `{#id}`, an
acceptance record per chapter, three derived registries, and an assembly
step, with **two human sign-offs**: one before any prose is generated
and one before the book is called finished. Neither sign-off can be
automated.

The first half walks through the steps in the order you run them, with
a real book's output at each step. The second half gives the reasoning,
and each step links to the part it rests on.

## 🧭 Table of contents

- [The constraint everything here answers](#-the-constraint-everything-here-answers)
- [The steps, at a glance](#-the-steps-at-a-glance)
- [Before you start](#-before-you-start)
- [Step 1: write the outline](#-step-1-write-the-outline)
- [Step 2: sign the outline off](#-step-2-sign-the-outline-off)
- [Step 3: hand each chapter to its author](#-step-3-hand-each-chapter-to-its-author)
- [Step 3b: generate one unit](#-step-3b-generate-one-unit)
- [Step 4: accept the unit](#-step-4-accept-the-unit)
- [Step 5: build and read the registries](#-step-5-build-and-read-the-registries)
- [Step 6: assemble the book](#-step-6-assemble-the-book)
- [Step 7: build the PDF](#-step-7-build-the-pdf)
- [Step 7b: the one review aid that reads a book](#-step-7b-the-one-review-aid-that-reads-a-book)
- [Step 8: the second sign-off](#-step-8-the-second-sign-off)
- [What one real book looked like](#-what-one-real-book-looked-like)
- [Retrofitting a book drafted before this track](#-retrofitting-a-book-drafted-before-this-track)
- [Why an id is required on every heading](#-why-an-id-is-required-on-every-heading)
- [Why sign-off is a sibling file](#-why-sign-off-is-a-sibling-file)
- [Why sign-off is recorded per chapter](#-why-sign-off-is-recorded-per-chapter)
- [Why a chapter is the authored document](#-why-a-chapter-is-the-authored-document)
- [Structure and artifact are different units](#-structure-and-artifact-are-different-units)
- [What `status`'s exit code is, and is not](#-what-statuss-exit-code-is-and-is-not)
- [What the input digest covers, and what it must not](#-what-the-input-digest-covers-and-what-it-must-not)
- [Why `registry check` exits 0, when the two `status` commands do not](#-why-registry-check-exits-0-when-the-two-status-commands-do-not)
- [What the registries cannot see](#-what-the-registries-cannot-see)
- [Why a registry excerpt is not hashed into a unit's contract](#-why-a-registry-excerpt-is-not-hashed-into-a-units-contract)

## 🔑 The constraint everything here answers

> A book does not fit in a context window, and generation quality
> degrades long before the limit.

So cross-chapter consistency cannot live in a model's memory of an
earlier call. It lives in explicit on-disk artefacts, injected as
relevant excerpts into each unit's generation, and checked
deterministically afterwards, the same two-plane discipline as the rest
of the project: the artefacts are written by deterministic
passes, never by an LLM writing to the corpus plane.

There are exactly two human sign-offs: **the outline** and **the
finished book**. No automated check verifies that an argument is good, only that
it is grounded, consistent and complete. Everything between the two
sign-offs is mechanical.

## 🔭 The steps, at a glance

| Step | Command | Who runs it |
| --- | --- | --- |
| 1 | `spec init`, then edit `spec.md` | you |
| 2 | `spec sign` | **you, and only you** |
| 3 | `spec seed`, then fill in each chapter's `outline.md` | you |
| 3b | `unit contract`, then a genre skill writes the chapter | you, then skill |
| 4 | `spec align`, then `unit accept` | you, per unit |
| 5 | `registry build`, `registry check` | you or the assembler |
| 6 | the `book-assembler` skill composes `book.tex` | skill |
| 7 | `lualatex`, `bibtexu`, `lualatex` x2 | you or the assembler |
| 7b | `review union` | you |
| 8 | read it | **you, and only you** |

Steps 3b and 4 repeat per chapter. Steps 5 to 7 are what
`.claude/skills/book-assembler/` does in one run.

A real spec partway through this ladder is committed: the sample project
holds a signed two-chapter outline
([`spec.md`](examples/sample-project/content/specs/twin-basics/spec.md)),
its sign-off record
([`signoff.md`](examples/sample-project/content/specs/twin-basics/signoff.md)),
and one accepted unit
([`units/ch-staleness.json`](examples/sample-project/content/specs/twin-basics/units/ch-staleness.json))
whose authored chapter sits at
[`content/drafts/twin-basics/ch-staleness.md`](examples/sample-project/content/drafts/twin-basics/ch-staleness.md).
The second chapter is marked `unwritten`, because a spec is allowed to be
ahead of its book and the registries report that.

## 🔧 Before you start

You need a synced corpus, because every unit is grounded in it:

```bash
chitragupta corpus ledger        # non-empty, items `parsed`
```

> Every command on this page also works as
> `python -m chitragupta.<layer> ...`: `python -m chitragupta.draft
> spec init` is the same as `chitragupta draft spec init`. Use whichever
> your install gives you; the console script is used throughout below.

A book lives in one directory under `content/drafts/`, one file per
**chapter**, named for that chapter's own `{#id}`. Nothing needs to exist
there yet; the outline comes first, and the prose is written into it
afterwards:

```text
content/drafts/twins/<chapter-id>.md  the book's chapters land here
content/specs/twins/spec.md           the outline -- step 1
content/specs/twins/signoff.md        your approval -- step 2
content/specs/twins/units/*.json      one acceptance record -- step 4
content/specs/twins/registries/*.md   terminology, claims, xrefs -- step 5
content/specs/twins/preamble.tex      your own LaTeX, optional -- step 6
content/rendered/twins/<id>.tex       each chapter as a fragment -- step 6
content/rendered/twins/book.tex       the assembled book -- step 6
content/rendered/twins/book.md        the same structure in Markdown
content/rendered/twins/book.pdf       the built book -- step 7
```

**`content/drafts/twins/` holds only chapters a person wrote.**
Everything the assembly produces is output and lands under
`content/rendered/twins/`, which is where a chapter's own render goes
anyway, so the fragments arrive there without being told to, and
`book.tex` is composed beside them.

`content/specs/` mirrors the book's own directory under `content/drafts/`,
the same rule `content/dossiers/`, `content/rendered/` and
`content/review/` follow, read one level up. Those mirror a single
*draft*, so they carry the draft's parent directory; a book is a
*directory* of drafts, so its own path carries over. Everything under
`content/` is gitignored: it is your data, not the pipeline's.

## ▶ Step 1: write the outline

```bash
chitragupta draft spec init content/drafts/twins --title "Composable Twins"
```

That writes a skeleton. Edit it into the book you mean to write,
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
anything ([why](#-why-a-chapter-is-the-authored-document)).

Every part, chapter and section needs an explicit `{#id}`, and a heading
without one is refused rather than guessed at
([why](#-why-an-id-is-required-on-every-heading)).

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
[`examples/dossiers/book/spec.md`](examples/dossiers/book/spec.md):

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

## ▶ Step 2: sign the outline off

The first of the two human gates. Nothing generates prose from an
unsigned outline, and no command can do this for you:

```bash
chitragupta draft spec sign content/drafts/twins --by "Your Name"
chitragupta draft spec status content/drafts/twins
```

```text
content/specs/twins/spec.md: Composable Twins
  2 parts, 4 chapters, 4 sections
  signed off at digest 7cfc6678f261.
```

`sign` records a twelve-hex digest of `spec.md` in a sibling file
([why a sibling](#-why-sign-off-is-a-sibling-file)), so `status` can tell
three states apart:

| State | Exit | Means |
| --- | --- | --- |
| signed off at digest `x` | 0 | the approved outline is the one on disk |
| not signed off | 1 | nobody has approved this outline yet |
| changed since sign-off | 1 | approved at one digest, now another |

That non-zero exit is not a new gate
([what it is](#-what-statuss-exit-code-is-and-is-not)).

It records **one digest per chapter as well**, and `status` names the
chapters that moved. After a reword of `ch-cost`'s brief:

```text
content/specs/twins/spec.md: Composable Twins
  2 parts, 4 chapters, 4 sections
  changed since sign-off: approved at 7cfc6678f261, now 6246a85473b1.
  chapters changed: ch-cost
```

Recording per chapter keeps a revision to one chapter from freezing the
other fourteen ([why](#-why-sign-off-is-recorded-per-chapter)).

## ▶ Step 3: hand each chapter to its author

The spec owns the book's structure; the genre skills own its content. This
is the handover:

```bash
chitragupta draft spec seed content/drafts/twins --genre textbook-chapter
```

```text
  ch-what                  What a twin is, and is not
    added: The model half
    added: The data half
  ch-fidelity              Choosing fidelity
    added: Fidelity against a decision
    added: When more fidelity makes things worse
```

`ch-cost` and `ch-sync` declare no sections, so there is nothing to
seed for them. For each chapter the outline describes at section
level, it writes that chapter's section names into its dossier's
`outline.md` as bare `##` headings and stops. Every `brief:`, `claim:`
and `queries:` line beneath them is left for whoever drafts the
chapter; a brief the spec invented would be the book track writing
content.

It **refuses an unsigned outline**, because seeding from a structure
nobody approved puts unsettled section names in front of an author as
though they were decided. It **never rewrites a heading**, so it is safe
to re-run once the spec grows a section; `--dry-run` says what it would
add. The write itself is done by `dossier init`, so the package that owns
`content/dossiers/` stays the one creating files in it.

A freshly seeded outline has headings and no briefs, so
`dossier outline <draft> --check` will report each as "neither a brief:
nor a claim: block". That is expected, since nobody has filled it in yet.

**Filling it in is the chapter author's job, and it is the same
`outline.md` every other genre uses.** Per section: `brief:` (steering,
never printed), `claim:` (your prose, grounded or reported back),
`queries:` (run verbatim). Each chapter also gets its own `scope.md`:
the reader, what the chapter covers, what it defers to another chapter,
and the glossary.

Fill in the glossary most carefully. Chapter authors working in parallel will
define the same term three ways unless each chapter's `scope.md` pins
it, and step 5's terminology registry catches them when they do.

Whichever genre a chapter is, its tutorial has the field-by-field
walkthrough and a complete filled-in example:

| Chapter is | Follow |
| --- | --- |
| teaching material, worked examples, exercises | [WRITE-A-TEXTBOOK-CHAPTER.md](WRITE-A-TEXTBOOK-CHAPTER.md) |
| a hands-on lab the reader follows at a keyboard | [WRITE-A-TUTORIAL.md](WRITE-A-TUTORIAL.md) |
| a literature map or state-of-the-art chapter | [WRITE-A-SURVEY.md](WRITE-A-SURVEY.md) |
| an RQ-driven argument | [WRITE-A-THESIS-CHAPTER.md](WRITE-A-THESIS-CHAPTER.md) |
| a multi-perspective, contradiction-mapped report | [WRITE-A-DEEP-RESEARCH-REPORT.md](WRITE-A-DEEP-RESEARCH-REPORT.md) |

A book may mix them: a textbook whose third chapter is a survey and
whose fifth is a lab is a normal shape, and the unit record does not care
which genre wrote a chapter.

## ▶ Step 3b: generate one unit

Ask for the contract, which is what the unit is generated *from*:

```bash
chitragupta draft unit contract content/drafts/twins ch-what --source sample_dt_overview_2024
chitragupta draft unit contract content/drafts/twins ch-what --json   # for a skill
```

```text
# What a twin is, and is not
- unit: ch-what
- in: Part I: Foundations
- draft: content/drafts/twins/ch-what.md
- sources: sample_dt_overview_2024
- input digest: 6308a33dca71
- outline: signed off

Establish the vocabulary the rest of the book leans on, and settle the
twin/shadow distinction early -- later chapters assume it. Must not
drift into architecture; that is Part II's job.
```

The contract is explicit in both directions:

| In | Out |
| --- | --- |
| the spec slice (title, brief, the part and chapter above it) | the unit's prose at `content/drafts/<book>/<unit-id>.md` |
| the sources it is grounded in, given as `--source <citekey>` | the citekeys it cites, recorded |
| registry excerpts, injected at generation time | the claims the register picks up |

`--source` is repeatable and is part of the input digest, so grounding a
unit in a different set of papers is a different unit to generate
([what else the digest covers](#-what-the-input-digest-covers-and-what-it-must-not)).
Registry excerpts are handed to the generator but deliberately left out
of that digest
([why](#-why-a-registry-excerpt-is-not-hashed-into-a-units-contract)).

Then write the unit. This is the one step this track does not own: a
genre skill drafts it (`thesis-chapter-writer` for a `.tex` fragment,
another genre for Markdown, handing any figure to `figure-drawer`),
grounded in the sources, and saves it as
`content/drafts/twins/ch-what.md`. From step 5 on you can hand that skill
what the rest of the book already settled:

```bash
chitragupta draft registry excerpt content/drafts/twins ch-what
```

A part has no contract, and neither does a section inside a chapter that
declares sections, because that chapter is the unit. Asking for either is
refused rather than answered with an empty contract, and the refusal names
the units that do exist.

## ▶ Step 4: accept the unit

Before accepting, check that what was written still matches what you
approved:

```bash
chitragupta draft spec align content/drafts/twins
```

```text
content/specs/twins/spec.md: Composable Twins
  ch-what                  What a twin is, and is not
    not authored: The model half
    renamed: The data half -> The data half, revisited
  ch-cost                  What a twin costs
    described at chapter level; nothing to align.
  ch-fidelity              Choosing fidelity
    not written yet: content/drafts/twins/ch-fidelity.md
  ch-sync                  Keeping it in step
    described at chapter level; nothing to align.
```

It compares the sections your outline declares for a chapter against the
`##` headings that chapter's author wrote, and reports four
things: a declared section **not authored**, an authored section **not
declared**, a **renamed** heading, and sections all present but **out of
order**. A reworded heading is one finding rather than two, because "you
renamed this" is what happened. Numbering is ignored, so `3.1 The model half` and
`The model half` are the same section: a genre skill numbers what it
writes and the outline does not.

`align` **reads and refuses nothing**, and exits non-zero on a finding the
way `spec status` does. It is silent on a chapter the outline describes
only at chapter level; see
[why a chapter is the authored document](#-why-a-chapter-is-the-authored-document)
for the scoping rule and what it is protecting against.

```bash
chitragupta draft unit accept content/drafts/twins ch-what --source sample_dt_overview_2024
```

```text
OK    content/drafts/twins/ch-what.md: 2 citation(s), all verified against the ledger.
Accepted ch-what at input digest 6308a33dca71.
Wrote content/specs/twins/units/ch-what.json.
```

`accept` writes the record only after the project's one gate passes on
the draft. It refuses five ways, each for a stated reason:

1. **This unit's chapter is not signed off.** There is nothing to accept
   a unit against until a human has approved the structure. Asked of the
   unit's own chapter, not of the whole book, so revising chapter 7 does
   not stop you accepting a unit in chapter 3
   ([why](#-why-sign-off-is-recorded-per-chapter)).
2. **The unit's chapter does not match the outline.** Acceptance
   records that a human approved *this prose against that outline*, and a
   chapter whose headings have drifted makes the record say something
   untrue. `spec align` lists what moved. A chapter nobody has written yet
   is deliberately not a refusal: a book is drafted unit by unit, and
   holding the first unit until the whole chapter exists would make it
   impossible to accept.
3. **There is no draft.** Generate the unit from its contract first.
4. **A `--source` is not in the ledger.** `--source` names the
   papers this unit claims to be grounded in, and the acceptance record
   keeps that claim permanently, so it is checked against the ledger
   before anything is written. A record asserting grounding in a citekey
   no real parse ever produced is exactly the fabricated reference
   [CLAUDE.md](../CLAUDE.md)'s one rule exists to prevent. It is
   reported with the argument-shaped faults above, not beside the gate's
   findings, where it would read as a defect in the prose.
5. **The citation gate refuses the draft.** `accept` runs the project's
   one gate rather than re-implementing or replacing it: it reads the
   draft once and hands *that string* to `citation_gate.check_text`,
   reporting through `citation_gate.report`, which is the same printer
   `chitragupta draft gate` itself uses, so the two read
   identically. It reads the file once on purpose, so the prose it
   hashes and records is exactly the prose the gate checked, even if a
   write lands while it runs. A unit that fails the gate cannot be
   assembled into a book, and `accept` adds no second gate.

The record holds the input digest the prose was generated against, the
sources, what it cites, and a digest of the prose itself. It carries
**no timestamp**, so accepting an unchanged unit twice produces
byte-identical files and a diff of `content/specs/` is a diff of what was
accepted.

Repeat steps 3b and 4 per unit. `unit status` is the board, and it names
what the *dossier* says about the same prose beside what this layer
recorded:

```text
  ch-what                  accepted                               dossier: agrees
  ch-fidelity              stale: draft changed since accepted    dossier: disagrees

  1 of 2 unit(s) accepted and current.
```

The two records of the same text answer different questions:
`accept`'s `output_digest` is "has this changed since a human accepted
it", the dossier's fingerprint is "has it changed since the sidecars were
reconciled". Different commands refresh them (`unit accept` and
`dossier stamp`), so they can disagree, and `unit status` prints both.
`no dossier`, `not stamped`, `agrees`, `disagrees` and
`stamped, no draft` are the five answers. The comparison is reported and
never enforced, because this layer does not judge a dossier.

```bash
chitragupta draft unit status content/drafts/twins
```

| State | Means |
| --- | --- |
| `unwritten` | no draft on disk |
| `drafted` | prose exists, nobody accepted it (also what an unreadable record reads as) |
| `accepted` | the record matches both the current contract and the prose |
| `stale: inputs changed` | the outline moved under an accepted unit |
| `stale: draft changed since accepted` | the prose moved after acceptance |

It re-derives all three digests rather than trusting them, and exits 0
only when every unit is accepted and current, the same standing as
`spec status`.

## ▶ Step 5: build and read the registries

```bash
chitragupta draft registry build content/drafts/twins
chitragupta draft registry check content/drafts/twins
```

On the 15-chapter book described [below](#-what-one-real-book-looked-like),
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
| terminology and notation | `- **Term** -- definition` bullets | a term defined in more than one unit |
| claims | every sentence that cites something | the same claim made in more than one unit |
| cross-references | `[text](#id)` and `\ref{id}`/`\cref{id}` | a reference no unit or outline entry defines |

Three properties hold for all of them:

- **Built from accepted units only**, and the count is printed, naming
  the ones it could not see. A registry over half a book is not the same
  claim as one over all of it.
- **Nothing here is written by an LLM.** They are a deterministic reading
  of accepted prose, which is why they can be trusted: the same standing
  `chitragupta/ledger.py` has as a reading of a real bib file.
- **The conventions are borrowed.** The definition bullet is
  the dossier glossary's, the sentence splitter is the provenance aid's,
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
([why](#-why-registry-check-exits-0-when-the-two-status-commands-do-not)),
and there are things it structurally cannot see
([which](#-what-the-registries-cannot-see)).

## ▶ Step 6: assemble the book

Ask for the book and `.claude/skills/book-assembler/` runs steps 5 to 7:
it confirms both `status` commands, prints every registry finding, and
only then composes. Everything it assembles has already passed every gate
per unit, so assembly is deterministic composition plus a human
sign-off; there is no enforcement machinery here to write.

**The whole composition is one table**, and the ids carry through
unchanged:

| Outline | LaTeX | Label |
| --- | --- | --- |
| `# Title` | `\title{...}` | none |
| `## Part {#part-i}` | `\part{...}` | `\label{part-i}` |
| `### Chapter {#ch-1}` | `\input{ch-1.tex}`, the unit, whose own `#` heading becomes `\chapter{...}` | `\label{ch-1}` |
| `#### Section {#sec-1}` | a heading inside `ch-1.tex`, never a file of its own | `\label{sec-1}` |

Because the `{#id}` becomes the LaTeX label unchanged, the
cross-references `registry check` verified resolve in the built PDF: the
outline, the registry and the document all name the same thing.

**The bibliography is one list at the end of the book.** Each unit is
converted with

```bash
chitragupta draft render <unit>.md --format tex --fragment
```

and `--fragment` changes the output: no preamble, the unit's own `#`
heading becomes a `\chapter`, and code blocks are left unhighlighted
because `Shaded`/`Highlighting` exist only in the standalone template.
It also **defers its citations**: the fragment emits `\citep{...}`
instead of a resolved `[1]`, and carries no reference list of its own.
`book.tex` then holds `\bibliographystyle{IEEEtran}` and
`\bibliography{bibliography}`, and one `bibtexu` pass numbers every
citation in the whole document at once.

**The resolution has to move along with the list.** Citeproc assigns
numbers in the same pass that builds the list. Resolve per unit and every
chapter restarts at `[1]`, so chapter 1's `[2]` and chapter 2's `[2]` are
different papers; collect those into one back-of-book list and half the
markers point at the wrong entry, in a book that compiles cleanly.
Deferred, a source cited in two chapters carries **one** number in both
and the sequence runs continuously (measured both ways on a real
two-chapter build).

The **citekey aliasing** applies on both sides: a key
containing `--` (`@lim_state---art_2020`) would otherwise reach LaTeX
truncated and render as `[?]`, so the render rewrites it to
`lim_state-x2d-x2d-art_2020` in the fragment *and* in the `.bib` it
copies beside `book.tex`. Never hand-edit either.

A **standalone** render (the same unit without `--fragment`) uses
citeproc, the vendored IEEE style, and its own numbered
reference list, exactly as every other genre skill produces one. The two
shapes exist because a chapter read alone wants its sources at the end of
the chapter, and the same chapter in a book wants them at the end of the
book.

### 🔠 Brace-protect acronyms in your `.bib` titles

Two IEEE implementations format your references: `assets/csl/ieee.csl`
for a standalone render, and `IEEEtran.bst` for the assembled book. They
agree, byte for byte, on every entry measured, **provided acronyms in a
title are wrapped in braces**:

```bibtex
title = {A Survey of {IoT} and {AI} Digital Twins: An {FMI}-Based Approach}
```

Unbraced, `bibtexu` lowercases them and the book's bibliography reads "a
survey of iot and ai digital twins". Citeproc preserves them, so the same
entry is correct in a standalone render and wrong in the book. Braced,
both produce the same line.

This is ordinary BibTeX practice (braces mean "do not change this
case"), and only the book build depends on it, because a book is the
one output this pipeline runs through a `.bst` style. It is a property
of **your own export**, so fix it in your reference manager, not in
`papers/bibliography.bib`, which a re-export overwrites. Nothing in the
pipeline rewrites your titles: it would have to guess which capitalised
word is an acronym and which is a proper noun, and this project does not
silently alter a human's bibliographic data.

The book also sets `margin=80pt`, about 28mm.
The `book` class's own margins are 94pt inner and 143pt outer (measured),
generous enough to run a 15-chapter book to 546 pages; a third of that
was tried and read too tight for print, so the setting is that doubled.

`book.md` is written beside `book.tex`, in
`content/rendered/<book>/`: the same structure in Markdown, hyperlinking
the chapter files alongside it, for anyone who is not building LaTeX.

**Where the registry proposal's "blocking" lives.** The skill must run
`registry check` and print every finding, in full, before composing.
That is the guaranteed *invocation* ARCHITECTURE.md permits, in place of
the conformance it does not. `tests/test_skill_book_assembly.py` pins
that, so a hand edit dropping either half fails the suite.

## ▶ Step 7: build the PDF

A book is built directly, from its own directory, because the `\input`
paths are relative to it:

```bash
cd content/rendered/twins
lualatex -interaction=nonstopmode book.tex
bibtexu book
lualatex -interaction=nonstopmode book.tex
lualatex -interaction=nonstopmode book.tex
```

**LuaLaTeX and `bibtexu`, as the pdf render is**: a chapter prints in
the same fonts in the book as in its own pdf, and `bibtexu` abbreviates
a first name by character, so an initial such as `Ö.` survives into the
bibliography. The four passes take about 86 s for a 287-page book.
`bibtexu` exits 1 when the `.bib` has only warnings; read `book.blg` for an
`error`.

**Four passes, and the `bibtexu` one is not optional**: the first
`lualatex` records which keys the document cites, `bibtexu` turns those
into `book.bbl`, the third pulls the bibliography in, and the fourth
resolves `\cref`, the table of contents and the citation numbers now that
the entries exist. Skip it and every citation renders `[?]` while
`lualatex` still exits 0.

**Then read the log before trusting the PDF.** `lualatex` exits 0 on a
book that renders `[?]` where a reference should be, because natbib
reports a dropped citation as a warning, not an error:

```bash
python3 -c "import re,pathlib; log=pathlib.Path('book.log').read_text(errors='replace'); \
    print(sorted(set(re.findall(r\"Citation \`([^']+)' on page\", log))))"
```

Anything but `[]` means a citekey never reached the bibliography. The
check uses Python rather than `grep -c` because `grep -c` over that log
has been seen to print nothing at all, and a check that silently reports
nothing is worse than no check.

**`content/specs/<book>/preamble.tex` is the supported way to override
anything the assembled `book.tex` sets.** It is optional and most books
have none; if it exists, `book-assembler` copies it beside `book.tex` and
`\input`s it as the last line of the generated preamble, so it wins over
the defaults above it. **Do not hand-edit `book.tex` to do this.** That
file is regenerated every time the book is assembled, so an edit to it is
lost at the next run, while `preamble.tex` is yours and survives.

**If your units number their own sections** (`## 1.0 Before you start`),
put `\setcounter{secnumdepth}{-2}` in `content/specs/twins/preamble.tex`,
or LaTeX numbers them a second time ("1.1 1.0 Before you start", and
worse further in).

**A chapter title that carries its own number needs no preamble line.**
For a unit headed `# Chapter 1: Why Anyone Pays`, step 6's
`draft render --fragment` drops the `Chapter 1:` prefix from the
`\chapter{}` it emits, so the number comes from the `book` class alone
and every section and table keeps its numbering. Your `.md` is not
touched: it still titles that unit's own standalone pdf, and every unit
stays `accepted`. Do not use `secnumdepth{-2}` for this: it would take
away every section and table number in the book to fix one chapter
title.

A unit you drafted as `.tex` is the exception: step 6 does not convert
it, so the prefix reaches the book as you wrote it. `chitragupta draft
style` reports that one as `chitragupta.ChapterSelfNumbered`; delete the
prefix from the `\chapter{}` and let the book supply the number.

The default `book.tex` sets `\setcounter{secnumdepth}{2}` (the `book`
class's own default, restated so a book states its numbering rather than
inheriting it silently) and `\setcounter{tocdepth}{1}`, which stops the
table of contents at the section. Which numbering a book shows is a
composition decision and belongs to the book; renumbering your headings
does not, and is `draft-reviser`'s call.

## ▶ Step 7b: the one review aid that reads a book

Every other aid reads a draft; this one reads the **assembly**, and asks
a question only a book can be asked: does the assembled document still
carry every citekey its accepted units stand on?

```bash
chitragupta review union content/rendered/twins/book.tex
```

It is advisory: it exits 0 whatever it finds and blocks nothing. It
reports two findings, which mean opposite problems:

| Finding | What happened | Usually means |
| --- | --- | --- |
| `dropped` | an accepted unit the assembly never `\input`s, named with every citekey the book then holds nowhere else | a chapter left out of `book.tex` by accident, which a PDF that compiles does not show |
| `appeared` | a citekey in a file the assembly includes that no unit owns | a title page, appendix or preamble file citing something; fine if deliberate, a leak if not |

It resolves the assembly's `\input` chain instead of grepping
`book.tex` for citekeys, because each unit's `\citep{...}`
calls sit in that unit's fragment, so `book.tex`'s own text states no
citekey at all. An aid that read only `book.tex` would report every
source in a correct book as lost.

Two things it refuses, both exit 1: a path in no book (there is no
expected set to compare against), and a path that is itself one of the
book's units. Pointed at a unit, it would report every *other* unit's
citekeys as dropped.

Per-chapter aids still apply. Run them before assembly:

```bash
chitragupta review agenda content/drafts/twins/ch-fidelity.md
```

Its findings are the chapter author's, in the same `[unattended]` /
`[surfaced]` shape each genre tutorial describes.

## ▶ Step 8: the second sign-off

The assembler presents what it composed (the unit count, what the
registries could not read, every finding, and what the gate and the two
review aids said) and stops there. **It does not say the book is
finished**, and neither does anything else in this pipeline.

No check reads the argument. The checks establish that a book is
grounded, consistent and complete, not that it is any good; that
judgement is the second human gate, and it is yours.

The assembler has already run the prose check (`draft style`) and the
verbatim scan on every unit and reported both. If you change a unit after
assembly, run them again on that unit, not on `book.tex`, which holds no
prose. Both are review aids that exit 0 whatever they find. The scan sees
verbatim and near-verbatim reuse only; real restatement is only detected
where the embedding tier can run, so a clean scan does not rule
restatement out ([PLAGIARISM.md](PLAGIARISM.md)). A change to a unit's prose goes
through `draft-reviser`, and an unattended agenda finding through
`agenda-reviser`; then re-accept the unit (step 4) and reassemble.

## 📝 What one real book looked like

The first book assembled by this track was a 15-chapter textbook,
22,155 lines of Markdown, measured on 2026-08-19:

| | |
| --- | --- |
| outline | 3 parts, 15 chapters, 15 units |
| citations, gate-verified | 864 across the 15 units, 194 distinct citekeys |
| terminology registry | 15 definitions |
| claim register | 388 claims |
| cross-reference graph | 0 edges; the chapters refer to each other in English, not as links |
| `registry check` | 1 finding: one claim made in two chapters |
| the book | 430 pages, 1.7 MB, 0 undefined citations |

That build is also why the skill aliases citekeys containing `---`:
three such keys carried 10 citations that would otherwise have rendered
as `[?]`.

## 🛠 Retrofitting a book drafted before this track

A book whose chapters already exist can be brought under the track
without rewriting a word. You derive the outline from the book:

1. Take the parts and their chapter numbering from whatever table of
   contents the book already has.
2. Take each chapter's title from that chapter's own `#` heading (what
   the prose says, not the table of contents' paraphrase).
3. Make each unit id the chapter's **filename stem**, so
   `unit accept` finds the prose where it already lives.

One chapter is then one unit: a `####` section whose id is the filename,
under a `###` chapter entry that carries the same title. The chapter
heading stays inside the unit file, so `book.tex` emits `\part` and
`\input` and lets the fragment's own `\chapter{}` supply the title;
emitting one here as well would print every title twice.

Say in the spec that the outline was retrofitted, and from what. A
sign-off records a person's decision; one recorded on an outline nobody
has read is a record of the wrong thing.

## 💡 Why an id is required on every heading

Every part, chapter and section carries an explicit `{#some-id}`, and a
heading without one is a parse problem rather than something the parser
guesses at.

A derived id (slugified from the heading text, say) changes the
moment someone rewords the heading, and every unit already written
against the old spelling silently becomes an orphan. At chapter scale a
person notices; across 300 pages nobody does. The same ids are what the
cross-reference graph resolves against, so they have to outlive an edit
to the words around them.

## 💡 Why sign-off is a sibling file

`spec sign` records a twelve-hex digest of `spec.md`, the same shape as
the dossier's corpus fingerprint, and for the same reason: enough to
answer "is this the same document?", short enough to sit on one line.

It goes in `signoff.md` rather than into `spec.md` itself because writing
the digest into the file would change the file it just measured, and no
later read could ever match. The digest covers `spec.md` alone.

`signoff.md` carries **no timestamp**, the same rule the review layer's
reports follow: two sign-offs of an unchanged outline produce
byte-identical files, so "did this change?" is a diff. *When* it was
approved is not a question any check asks; *what* was approved is.

## 💡 Why sign-off is recorded per chapter

`signoff.md` records the whole-file digest **and one digest per chapter**,
each taken over that chapter's `###` heading and everything under it.

The whole-file digest alone cannot answer the question `accept` asks.
Measured on a fifteen-chapter book: editing a single character in
one chapter's brief moved the file's digest, so **every one of the 672
sections that outline declared, across all fifteen chapters**, reported
`signed_off: False`, and `accept` refused across the entire book while one
chapter sat half-revised. A book is revised chapter by chapter over weeks;
a book-wide answer makes every in-flight revision a book-wide freeze.

The escape, re-running `spec sign`, was worse than the freeze. It
re-approves all fifteen chapters at once, so the record could not
tell "a human read this" from "a human re-approved it as collateral while
fixing something else." The principle stated for the retrofit case
applies here unchanged: *a sign-off recorded on
an outline nobody has read is a record of the wrong thing.*

Keyed by chapter **id**, not title, for the reason ids exist at all: a
reworded heading must not orphan the record of its own approval.

**A `signoff.md` with no chapter lines falls back to the whole-book
digest.** Nothing writes chapter digests into one on a human's behalf:
that would be this project inventing an approval, which is the one thing
a record of a person's decision may never do. Re-run `spec sign` to
record them.

## 💡 Why a chapter is the authored document

A chapter is one file; its sections are the headings inside it.

**That is what makes `spec align` mean anything.** Under one file
per section, every file *is* a section by construction: there is no way
for what was written to disagree with what was approved, so there is
nothing to check. Only when a chapter is a single document can its
headings drift from the outline a human signed.

It also matches the real book. `digital-twins-for-software-engineers`
is one file per chapter, brought under the track by
[retrofitting](#-retrofitting-a-book-drafted-before-this-track) each
chapter as a single `####` section carrying the filename.

**Alignment is scoped to chapters the outline describes at section
level**: two or more declared sections, or one whose title differs from
the chapter's own. Anything else reports "described at chapter level;
nothing to align", with no finding.

Measured on the real book: its
retrofitted outline declares one section per chapter while its author
wrote about forty headings under each: **4 declared sections against 161
authored headings** across the first four chapters. Without the rule,
`align` would put roughly 225 findings on a book that is not wrong, only
described at chapter granularity, and a check like that is the first thing
anyone turns off.

## 💡 Structure and artifact are different units

`spec.md` declares **structure**: headings a human approves before any
prose exists, and what `spec align` checks a draft against. `unit accept`
records an **artifact**: a file the citation gate runs on, whose whole
text is hashed into `output_digest` and whose citekeys are extracted. A
heading has no independent existence on disk.

The two coincide only when a book is one file per section, and
alignment only has content while the outline is finer than the file.
Collapse them in either direction (declare only chapters, or go back to
one file per section) and "did you write what you said you would?"
becomes a question with no possible answer.

So `unit contract|accept|status` resolve against **acceptance units**: a
chapter the outline describes at section level *is* one; a chapter
described only at chapter level leaves its single section as one, which
is every retrofitted book and why they keep working unchanged.

A third sense of the word lives in `chitragupta/review/_units.py`: the
scale the multi-source rule binds at, which is **genre-dependent**
(paragraph for a thesis chapter, section for a textbook one). That one is
about evidence and this one about artifacts, so they are not expected to
agree.

## ✅ What `status`'s exit code is, and is not

`spec status` and `unit status` exit non-zero on an outline nobody has
signed or a unit nobody has accepted. That exit code is not a new
gate.

[ARCHITECTURE.md](ARCHITECTURE.md)'s "Layer 4" draws the line by **what a
check is measured against**: the citation gate is measured against the
ledger, which is ground truth, while a check measured against a recorded
preference reports and never blocks, however mechanical its answer. These
two are measured against neither. They read back a record of a *person's
decision* (did a human approve this outline, accept this unit?) and
report it. They judge no draft's content, refuse no write, and block no
draft: `chitragupta draft gate` remains the only gate in this project,
and `.claude/hooks/citation_gate_hook.py` remains the only automatic
refusal.

What the exit code buys is that a skill can ask the question without
parsing prose. What it does with the answer (stop and ask you to
approve the outline first) is the human gate itself.

## 🔒 What the input digest covers, and what it must not

`input_digest` is what makes an unchanged unit free to re-run. It covers
the spec slice, the sorted set of sources, and a `registries:` field
that is always empty
([why](#-why-a-registry-excerpt-is-not-hashed-into-a-units-contract)),
and deliberately nothing else:

- **Not the unit's own prose.** A digest that moved when the output moved
  could never answer the question it exists for, which is "does this unit
  need regenerating?".
- **Not the sign-off state**, and not the draft's path. Neither is an
  input to the writing; folding either in would make a unit look stale
  for a reason that changes nothing about what should be written.
- **Not the order the sources were given in.** The set is sorted and
  de-duplicated first, so a unit grounded in the same papers hashes the
  same however the caller listed them.

Each part is labelled before hashing (`sources:`, `registries:`), so a
citekey and a registry line cannot collide into the same text.

## 💡 Why `registry check` exits 0, when the two `status` commands do not

`spec status` and `unit status` exit non-zero. `registry check` never
does, however much it finds, and the difference is deliberate.

[ARCHITECTURE.md](ARCHITECTURE.md)'s "Layer 4" is explicit that a check
measured against a recorded preference "reports and never blocks,
**whichever layer it lives in**", and that what may be enforced is
*invocation* rather than conformance: "a harness may guarantee that it
runs and that its findings are seen, never that they were obeyed."

The two `status` commands report whether a **human decided** something.
This one reports a **machine's reading of prose**: which term it thinks
was defined where, which sentences it thinks match, which reference it
thinks dangles. That is judgement however mechanical the arithmetic, so
it is evidence and never a verdict. No flag changes this:
DEVELOPER-AGENTS.md bars promoting a new check into a gate
outright rather than leaving it to an argument about how precise the
check is.

What the registry proposal calls a "blocking global check" is therefore
delivered as guaranteed invocation in step 6, ahead of the human sign-off
in step 8. That is a stronger reading of the requirement than an exit
code would be: an exit code can be ignored by a caller; a sign-off
cannot be given by one.

## 🚫 What the registries cannot see

**Contradiction.** The registry proposal asks for "duplicate and contradicting
claims across chapters flagged". Duplicates are decidable and are flagged; two
chapters asserting opposite things are not, and nothing here claims to detect
them. This project names what a check cannot see
([PLAGIARISM.md](PLAGIARISM.md) does the same for the tier that needs an
optional stack), and the final human sign-off covers the rest.

Two smaller limits, for the same reason: a definition that does not use
the bullet shape is not registered, and "used consistently" is checked
only in the sense that a term is *defined* once; no attempt is made to
decide whether a later paragraph used it the way the definition meant.

## 💡 Why a registry excerpt is not hashed into a unit's contract

`registry excerpt <book> <unit-id>` prints what a unit's generation
should be told about the rest of the book: the terminology the *other*
accepted units settled, and the ids it may point at. A unit is never told
to conform to itself.

That excerpt is deliberately **not** part of the unit's input digest. A
registry grows with every acceptance, so hashing it in would mark every later
unit stale each time an earlier one was accepted, which destroys the property
the contract exists for, that an unchanged unit costs nothing to re-run.
Instead the excerpt is injected at generation time, and inconsistency is
caught afterwards by `registry check` over the whole book. `registries` stays
in the contract's shape, empty and labelled, so a caller that does want to pin
one has somewhere to put it.

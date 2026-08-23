# ✍ Book-scale drafting: the outline, the units, and the registries

Status: **built.** All four pieces of the track are here -- the outline
(#136), the generation unit (#137), the three registries (#138) and the
assembly skill (#139). Each section below describes something that
exists; nothing here is a plan.

**Written for** someone drafting a document larger than a chapter with
this pipeline, and for whoever builds the next piece of the track. It
assumes [AGENTS.md](../AGENTS.md) for the drafting layer and
[ARCHITECTURE.md](ARCHITECTURE.md) for the four layers.

**The walkthrough is the first half of this document**, in the order you
run it, with a real book's output at each step. The second half is the
reasoning: each step links to the argument behind it, so a decision is
stated once and read where you need it.

## 🧭 Table of contents

- [The constraint everything here answers](#-the-constraint-everything-here-answers)
- [The steps, at a glance](#-the-steps-at-a-glance)
- [Before you start](#-before-you-start)
- [Step 1: write the outline](#-step-1-write-the-outline)
- [Step 2: sign the outline off](#-step-2-sign-the-outline-off)
- [Step 3: generate one unit](#-step-3-generate-one-unit)
- [Step 4: accept the unit](#-step-4-accept-the-unit)
- [Step 5: build and read the registries](#-step-5-build-and-read-the-registries)
- [Step 6: assemble the book](#-step-6-assemble-the-book)
- [Step 7: build the PDF](#-step-7-build-the-pdf)
- [Step 8: the second sign-off](#-step-8-the-second-sign-off)
- [What one real book looked like](#-what-one-real-book-looked-like)
- [Retrofitting a book drafted before this track](#-retrofitting-a-book-drafted-before-this-track)
- [Why an id is required on every heading](#-why-an-id-is-required-on-every-heading)
- [Why sign-off is a sibling file](#-why-sign-off-is-a-sibling-file)
- [What `status`'s exit code is, and is not](#-what-statuss-exit-code-is-and-is-not)
- [What the input digest covers, and what it must not](#-what-the-input-digest-covers-and-what-it-must-not)
- [Why `registry check` exits 0, when the two `status` commands do not](#-why-registry-check-exits-0-when-the-two-status-commands-do-not)
- [What the registries cannot see](#-what-the-registries-cannot-see)
- [Why a registry excerpt is not hashed into a unit's contract](#-why-a-registry-excerpt-is-not-hashed-into-a-units-contract)

## 🔑 The constraint everything here answers

> A book does not fit in a context window, and generation quality
> degrades long before the limit.

So cross-chapter consistency cannot live in a model's memory of an
earlier call. It has to live in explicit on-disk artefacts, injected as
relevant excerpts into each unit's generation, and checked
deterministically afterwards. That is the same two-plane discipline as
the rest of the project: the artefacts are written by deterministic
passes, never by an LLM writing to the corpus plane.

Two human sign-offs, and no more: **the outline** and **the finished
book**. No automated check verifies that an argument is good -- only that
it is grounded, consistent and complete. Everything between the two
sign-offs is mechanical.

## 🔭 The steps, at a glance

| Step | Command | Who runs it |
|---|---|---|
| 1 | `spec init`, then edit `spec.md` | you |
| 2 | `spec sign` | **you, and only you** |
| 3 | `unit contract` -> a genre skill writes the prose | skill |
| 4 | `unit accept` | you, per unit |
| 5 | `registry build`, `registry check` | you or the assembler |
| 6 | the `book-assembler` skill composes `book.tex` | skill |
| 7 | `pdflatex` x2 -- no bibliography pass | you or the assembler |
| 8 | read it | **you, and only you** |

Steps 3 and 4 repeat per section. Steps 5 to 7 are what
`.claude/skills/book-assembler/` does in one run.

## 🔧 Before you start

You need a synced corpus, because every unit is grounded in it:

```bash
.venv-full/bin/python -m chitragupta.corpus ledger        # non-empty, items `parsed`
```

A book lives in one directory under `content/drafts/`, one file per
section. Nothing needs to exist there yet -- the outline comes first, and
the prose is generated into it afterwards:

```text
content/drafts/twins/                 the book (units land here)
content/specs/twins/spec.md           the outline -- step 1
content/specs/twins/signoff.md        your approval -- step 2
content/specs/twins/units/*.json      one acceptance record -- step 4
content/specs/twins/registries/*.md   terminology, claims, xrefs -- step 5
```

`content/specs/` mirrors the book's own directory under `content/drafts/`
-- the same rule `content/dossiers/`, `content/rendered/` and
`content/review/` follow, read one level up. Those mirror a single
*draft*, so they carry the draft's parent directory; a book is a
*directory* of drafts, so its own path carries over. Everything under
`content/` is gitignored: it is your data, not the pipeline's.

## ▶ Step 1: write the outline

```bash
python -m chitragupta.draft spec init content/drafts/twins --title "Composable Twins"
```

That writes a skeleton. Edit it into the book you mean to write --
planned top-down, generated bottom-up. Four heading levels, and no more:

| Markdown | Is | Generates |
|---|---|---|
| `# Title` | the book | -- |
| `## Part {#part-i}` | a part | -- |
| `### Chapter {#ch-1}` | a chapter | -- |
| `#### Section {#sec-1}` | a **section** | one unit of prose |

The section is the generation unit, which is why nothing sits below it: a
level deeper would be a unit nothing generates. Text beneath a heading is
that unit's **brief** -- what it must establish, and what it leaves to
another unit. Text before the first heading belongs to no unit and is
never handed to a generator; it is the preamble for whoever opens the
file.

Every part, chapter and section needs an explicit `{#id}`, and a heading
without one is refused rather than guessed at --
[why](#-why-an-id-is-required-on-every-heading). Check what you wrote:

```bash
python -m chitragupta.draft spec show content/drafts/twins
```

```text
Composable Twins
  [part-i] Part I: Foundations
    [ch-1] Chapter 1: What a twin is
      [sec-1] The model half
```

`spec show`, `spec sign` and `spec status` all refuse a spec that does
not parse, and print **every** problem rather than the first: someone
fixing an outline wants the whole list, not one round trip per missing
id.

## ▶ Step 2: sign the outline off

The first of the two human gates. Nothing generates prose from an
unsigned outline, and no command can do this for you:

```bash
python -m chitragupta.draft spec sign content/drafts/twins --by "Your Name"
python -m chitragupta.draft spec status content/drafts/twins
```

```text
content/specs/twins/spec.md: Composable Twins
  1 part, 1 chapter, 2 sections
  signed off at digest bbf00d09be54.
```

`sign` records a twelve-hex digest of `spec.md` in a sibling file --
[why a sibling](#-why-sign-off-is-a-sibling-file) -- so `status` can tell
three states apart:

| State | Exit | Means |
|---|---|---|
| signed off at digest `x` | 0 | the approved outline is the one on disk |
| not signed off | 1 | nobody has approved this outline yet |
| changed since sign-off | 1 | approved at one digest, now another |

That non-zero exit is not a new gate --
[what it is](#-what-statuss-exit-code-is-and-is-not).

## ▶ Step 3: generate one unit

Ask for the contract, which is what the unit is generated *from*:

```bash
python -m chitragupta.draft unit contract content/drafts/twins sec-1 --source smith_2024
python -m chitragupta.draft unit contract content/drafts/twins sec-1 --json   # for a skill
```

```text
# The model half
- unit: sec-1
- in: Part I: Foundations > Chapter 1: What a twin is
- draft: content/drafts/twins/sec-1.md
- sources: smith_2024
- input digest: 6524fd365003
- outline: signed off

Establish that a twin is a model plus a live data link.
```

The contract is explicit in both directions:

| In | Out |
|---|---|
| the spec slice (title, brief, the part and chapter above it) | the unit's prose at `content/drafts/<book>/<unit-id>.md` |
| the sources it is grounded in, given as `--source <citekey>` | the citekeys it actually cites, recorded |
| registry excerpts, injected at generation time | the claims the register picks up |

`--source` is repeatable and is part of the input digest, so grounding a
unit in a different set of papers is a different unit to generate --
[what else the digest covers](#-what-the-input-digest-covers-and-what-it-must-not).
Registry excerpts are handed to the generator but deliberately left out
of that digest --
[why](#-why-a-registry-excerpt-is-not-hashed-into-a-units-contract).

Then write the unit. This is the one step this track does not own: a
genre skill drafts it (`thesis-chapter-writer` for a `.tex` fragment,
another genre for Markdown), grounded in the sources, and saves it as
`content/drafts/twins/sec-1.md`. From step 5 on you can hand that skill
what the rest of the book already settled:

```bash
python -m chitragupta.draft registry excerpt content/drafts/twins sec-1
```

A part or a chapter has no contract, and asking for one is refused rather
than answered with an empty contract: those levels name no prose of their
own.

## ▶ Step 4: accept the unit

```bash
python -m chitragupta.draft unit accept content/drafts/twins sec-1 --source smith_2024
```

```text
OK    content/drafts/twins/sec-1.md: 12 citation(s), all verified against the ledger.
Accepted sec-1 at input digest 6524fd365003.
Wrote content/specs/twins/units/sec-1.json.
```

`accept` writes the record only after the project's one gate passes on
the draft. It refuses three ways, each for a stated reason:

1. **The outline is not signed off** -- there is nothing to accept a unit
   against until a human has approved the structure.
2. **There is no draft** -- generate the unit from its contract first.
3. **The citation gate refuses the draft.** `accept` *invokes*
   `python -m chitragupta.draft gate` rather than re-implementing or replacing
   it. A unit nobody may cite from is not a unit a book may assemble
   from, and this is the existing gate doing its existing job -- not a
   second one.

The record holds the input digest the prose was generated against, the
sources, what it cites, and a digest of the prose itself. It carries
**no timestamp**, so accepting an unchanged unit twice produces
byte-identical files and a diff of `content/specs/` is a diff of what was
accepted.

Repeat steps 3 and 4 per section. `unit status` is the board:

```bash
python -m chitragupta.draft unit status content/drafts/twins
```

| State | Means |
|---|---|
| `unwritten` | no draft on disk |
| `drafted` | prose exists, nobody accepted it (also what an unreadable record reads as) |
| `accepted` | the record matches both the current contract and the prose |
| `stale: inputs changed` | the outline moved under an accepted unit |
| `stale: draft changed since accepted` | the prose moved after acceptance |

It re-derives all three digests rather than trusting them, and exits 0
only when every unit is accepted and current -- the same standing as
`spec status`.

## ▶ Step 5: build and read the registries

```bash
python -m chitragupta.draft registry build content/drafts/twins
python -m chitragupta.draft registry check content/drafts/twins
```

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
|---|---|---|
| terminology and notation | `- **Term** -- definition` bullets | a term defined in more than one unit |
| claims | every sentence that cites something | the same claim made in more than one unit |
| cross-references | `[text](#id)` and `\ref{id}`/`\cref{id}` | a reference no unit or outline entry defines |

Three properties hold for all of them:

- **Built from accepted units only**, and the count is printed, naming
  the ones it could not see. A registry over half a book is not the same
  claim as one over all of it.
- **Nothing here is written by an LLM.** They are a deterministic reading
  of accepted prose, which is the whole reason they can be trusted --
  the same standing `chitragupta/ledger.py` has as a reading of a real bib file.
- **The conventions are borrowed, not invented.** The definition bullet is
  the dossier glossary's, the sentence splitter is the provenance aid's,
  and everything from a `## References` heading onward is cut the way
  `chitragupta/acronyms.py` cuts it -- measured there against the real 15-chapter
  book, because a rendered reference list is nothing but citation-bearing
  lines and would otherwise fill the claim register with bibliography.

**A cross-reference is never spelled `@id`.** That is a citekey position:
a section id reaching it would put something the ledger has never seen
where only a real bibliography entry may go. `tests/test_registry.py`
pins that the citation gate reads neither supported reference syntax as a
citekey.

`check` exits 0 however much it finds --
[why](#-why-registry-check-exits-0-when-the-two-status-commands-do-not) --
and there are things it structurally cannot see --
[which](#-what-the-registries-cannot-see).

## ▶ Step 6: assemble the book

Ask for the book and `.claude/skills/book-assembler/` runs steps 5 to 7:
it confirms both `status` commands, prints every registry finding, and
only then composes. Everything it assembles has already passed every gate
per unit, so assembly is deterministic composition plus a human sign-off
-- there is no enforcement machinery here to write.

**Conventions as data, not code.** The whole composition is one table,
and the ids carry through unchanged:

| Outline | LaTeX | Label |
|---|---|---|
| `# Title` | `\title{...}` | -- |
| `## Part {#part-i}` | `\part{...}` | `\label{part-i}` |
| `### Chapter {#ch-1}` | `\chapter{...}` | `\label{ch-1}` |
| `#### Section {#sec-1}` | `\input{sec-1.tex}` | the unit's own `\label{sec-1}` |

That the `{#id}` becomes the LaTeX label unchanged is what makes the
cross-references `registry check` verified actually resolve in the built
PDF -- the outline, the registry and the document all name the same
thing.

**There is no bibliography at the end of the book.** Each unit is
converted with

```bash
python -m chitragupta.draft render <unit>.md --format tex --fragment \
    --output-dir content/drafts/<book>
```

and `--fragment` is the whole difference: no preamble, the unit's own `#`
heading becomes a `\chapter`, and code blocks are left unhighlighted
because `Shaded`/`Highlighting` exist only in the standalone template.
Everything else is the ordinary render -- pandoc's citeproc against the
vendored IEEE style, and the citekey aliasing that stops a key containing
`--` being truncated (`@lim_state---art_2020` would otherwise reach LaTeX
as `lim_state` and render as `[?]`). So every chapter carries **its own
numbered IEEE reference list**, under its own heading, exactly as every
other genre skill produces one -- and a bibliography at the end would be
a second, differently numbered answer to the same question. No `natbib`,
no `bibtex`, no `biber`, and nothing for either to resolve.

Two consequences for the book itself. It must supply pandoc's `csl-refs`
macro block, taken from `pandoc --print-default-template=latex` so it
matches the pandoc that did the conversion -- written to
`citeproc-defs.def` and `\input`, not inline, because that block contains
`\cite{#1}` and `\@`-internals which the citation gate reads as citekeys
and would fail the assembled book on. And `margin=80pt` -- about 28mm.
The `book` class's own margins are 94pt inner and 143pt outer (measured),
generous enough to run a 15-chapter book to 546 pages; a third of that
was tried and read too tight for print, so the setting is that doubled.

**`book.md` is written beside `book.tex`**: the same structure in
Markdown, hyperlinking the chapter files alongside it, for anyone who is
not building LaTeX.

**Where #138's "blocking" actually lives.** The skill must run
`registry check` and print every finding, in full, before composing --
which is the guaranteed *invocation* ARCHITECTURE.md permits, in place of
the conformance it does not. `tests/test_skill_book_assembly.py` pins
that, so a hand edit dropping either half fails the suite.

## ▶ Step 7: build the PDF

A book is built directly, from its own directory -- the `\input` paths
are relative to it:

```bash
cd content/drafts/twins
pdflatex -interaction=nonstopmode book.tex
pdflatex -interaction=nonstopmode book.tex
```

**Two passes, and no bibliography pass at all**: citeproc resolved every
citation when the units were converted, so the document holds no `\cite`
for `bibtex` or `biber` to answer. The second pass is what resolves
`\cref` and the table of contents.

**Then read the log before believing the PDF.** `pdflatex` exits 0 on a
book that renders `[?]` where a reference should be -- natbib reports a
dropped citation as a warning, not an error:

```bash
python3 -c "import re,pathlib; log=pathlib.Path('book.log').read_text(errors='replace'); \
    print(sorted(set(re.findall(r\"Citation \`([^']+)' on page\", log))))"
```

Anything but `[]` means a citekey never reached the bibliography. Python
rather than `grep -c` deliberately: on the host this was first run,
`grep -c` over that log printed nothing at all, and a check that silently
reports nothing is worse than no check.

**If your units number their own headings** (`## 1.0 Before you start`),
put `\setcounter{secnumdepth}{-2}` in the preamble, or LaTeX numbers them
a second time -- "1.1 1.0 Before you start", and worse further in.
Which numbering a book shows is a composition decision and belongs in
`book.tex`; renumbering your headings does not, and is `draft-reviser`'s
call.

## ▶ Step 8: the second sign-off

The assembler presents what it composed -- the unit count, what the
registries could not read, every finding, and what the gate and the two
review aids said -- and stops there. **It does not say the book is
finished**, and neither does anything else in this pipeline.

Nothing here has read the argument. The checks establish that a book is
grounded, consistent and complete; none of them establishes that it is
any good. That judgement is the second human gate, and it is yours.

Worth running before you circulate it, per unit rather than over
`book.tex` (which holds no prose):

```bash
python -m chitragupta.draft style content/drafts/twins/<unit-id>.md
python -m chitragupta.review verbatim scan content/drafts/twins/<unit-id>.md
```

Both are review aids: they exit 0 whatever they find, and neither may
block. The scan sees verbatim and near-verbatim reuse only -- genuine
restatement is only detected where the embedding tier can run, so a clean
scan is not a clean bill of health ([PLAGIARISM.md](PLAGIARISM.md)).

## 📝 What one real book looked like

The first book assembled by this track, so the numbers are measured
rather than illustrative -- a 15-chapter textbook, 22,155 lines of
Markdown, re-measured on 2026-08-19 after the chapters were revised:

| | |
|---|---|
| outline | 3 parts, 15 chapters, 15 units |
| citations, gate-verified | 864 across the 15 units, 194 distinct citekeys |
| terminology registry | 15 definitions |
| claim register | 388 claims |
| cross-reference graph | 0 edges -- the chapters refer to each other in English, not as links |
| `registry check` | 1 finding: one claim made in two chapters |
| the book | 430 pages, 1.7 MB, 0 undefined citations |

Two things that build found, both now fixed in the skill: the Markdown
conversion step named the wrong command, and three citekeys containing
`---` were being silently truncated -- 10 citations that would have
rendered as `[?]` in a finished book.

## 🛠 Retrofitting a book drafted before this track

A book whose chapters already exist can be brought under the track
without rewriting a word. The outline is *derived*, not invented:

1. Take the parts and their chapter numbering from whatever table of
   contents the book already has.
2. Take each chapter's title from that chapter's own `#` heading -- what
   the prose actually says, not the table of contents' paraphrase.
3. Make each unit id the chapter's **filename stem**, so
   `unit accept` finds the prose where it already lives.

One chapter is then one unit: a `####` section whose id is the filename,
under a `###` chapter entry that carries the same title. The chapter
heading stays inside the unit file, so `book.tex` emits `\part` and
`\input` and lets the fragment's own `\chapter{}` supply the title --
emitting one here as well would print every title twice.

Say in the spec that the outline was retrofitted, and from what. A
sign-off records a person's decision; one recorded on an outline nobody
has read is a record of the wrong thing.

## 💡 Why an id is required on every heading

Every part, chapter and section carries an explicit `{#some-id}`, and a
heading without one is a parse problem rather than something the parser
guesses at.

A derived id -- slugified from the heading text, say -- changes the
moment someone rewords the heading, and every unit already written
against the old spelling silently becomes an orphan. At chapter scale a
person notices; across 300 pages nobody does. The same ids are what the
cross-reference graph resolves against, so they have to outlive an edit
to the words around them.

## 💡 Why sign-off is a sibling file

`spec sign` records a twelve-hex digest of `spec.md` -- the same shape as
the dossier's corpus fingerprint, and for the same reason: enough to
answer "is this the same document?", short enough to sit on one line.

It goes in `signoff.md` rather than into `spec.md` itself because writing
the digest into the file would change the file it just measured, and no
later read could ever match. The digest covers `spec.md` alone.

`signoff.md` carries **no timestamp**, the same rule the review layer's
reports follow: two sign-offs of an unchanged outline produce
byte-identical files, so "did this change?" is a diff. *When* it was
approved is not a question any check asks; *what* was approved is.

## ✅ What `status`'s exit code is, and is not

`spec status` and `unit status` exit non-zero on an outline nobody has
signed or a unit nobody has accepted. That is not a new gate, and the
distinction matters enough to state rather than leave to a reader.

[ARCHITECTURE.md](ARCHITECTURE.md)'s "Layer 4" draws the line by **what a
check is measured against**: the citation gate is measured against the
ledger, which is ground truth, while a check measured against a recorded
preference reports and never blocks, however mechanical its answer. These
two are measured against neither. They read back a record of a *person's
decision* -- did a human approve this outline, accept this unit? -- and
report it. They judge no draft's content, refuse no write, and block no
draft: `python -m chitragupta.draft gate` remains the only gate in this project,
and `.claude/hooks/citation_gate_hook.py` remains the only automatic
refusal.

What the exit code buys is that a skill can ask the question without
parsing prose. What it does with the answer -- stop and ask you to
approve the outline first -- is the human gate itself, not a machine
outranking anybody.

## 🔒 What the input digest covers, and what it must not

`input_digest` is what makes an unchanged unit free to re-run. It covers
the spec slice, the sorted set of sources, and the registry excerpts
field -- and deliberately nothing else:

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
does, however much it finds -- and the difference is not inconsistency.

[ARCHITECTURE.md](ARCHITECTURE.md)'s "Layer 4" is explicit that a check
measured against a recorded preference "reports and never blocks,
**whichever layer it lives in**", and that what may be enforced is
*invocation* rather than conformance: "a harness may guarantee that it
runs and that its findings are seen, never that they were obeyed."

The two `status` commands report whether a **human decided** something.
This one reports a **machine's reading of prose**: which term it thinks
was defined where, which sentences it thinks match, which reference it
thinks dangles. That is judgement however mechanical the arithmetic, so
it is evidence and never a verdict. There is no flag that changes this,
deliberately: DEVELOPER-AGENTS.md bars promoting a new check into a gate
outright rather than leaving it to an argument about how precise the
check is.

What #138 calls a "blocking global check" is therefore delivered as
guaranteed invocation in step 6, ahead of the human sign-off in step 8.
That is a stronger reading of the requirement than an exit code would be,
not a weaker one -- an exit code can be ignored by a caller; a sign-off
cannot be given by one.

## 🚫 What the registries cannot see

**Contradiction.** #138 asks for "duplicate and contradicting claims
across chapters flagged". Duplicates are decidable and are flagged; two
chapters asserting opposite things are not, and nothing here pretends
otherwise. Naming what a check cannot see is this project's house style
([PLAGIARISM.md](PLAGIARISM.md) does the same for the tier that needs an
optional stack), and the final human sign-off is what covers the rest.

Two smaller limits, for the same reason: a definition that does not use
the bullet shape is not registered, and "used consistently" is checked
only in the sense that a term is *defined* once -- no attempt is made to
decide whether a later paragraph used it the way the definition meant.

## 💡 Why a registry excerpt is not hashed into a unit's contract

`registry excerpt <book> <unit-id>` prints what a unit's generation
should be told about the rest of the book: the terminology the *other*
accepted units settled, and the ids it may point at. A unit is never told
to conform to itself.

That excerpt is deliberately **not** part of the unit's input digest, and
the reason is the cascade. A registry grows with every acceptance, so
hashing it in would mark every later unit stale each time an earlier one
was accepted -- which destroys exactly the property the contract exists
for, that an unchanged unit costs nothing to re-run. Instead the excerpt
is injected at generation time, and inconsistency is caught afterwards by
`registry check` over the whole book. `registries` stays in the
contract's shape, empty and labelled, so a caller that does want to pin
one has somewhere to put it.

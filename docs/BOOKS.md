# Book-scale drafting: the outline, the units, and the registries

Status: **built.** All four pieces of the track are here -- the outline
(#136), the generation unit (#137), the three registries (#138) and the
assembly skill (#139). Each section below describes something that
exists; nothing here is a plan.

**Written for** someone drafting a document larger than a chapter with
this pipeline, and for whoever builds the next piece of the track. It
assumes [AGENTS.md](../AGENTS.md) for the drafting layer and
[ARCHITECTURE.md](ARCHITECTURE.md) for the four layers.

## Table of contents

- [The constraint everything here answers](#the-constraint-everything-here-answers)
- [The spec artefact, and its sign-off](#the-spec-artefact-and-its-sign-off)
- [Why an id is required on every heading](#why-an-id-is-required-on-every-heading)
- [Why sign-off is a sibling file](#why-sign-off-is-a-sibling-file)
- [What `status`'s exit code is, and is not](#what-statuss-exit-code-is-and-is-not)
- [The generation unit, and its contract](#the-generation-unit-and-its-contract)
- [What the input digest covers, and what it must not](#what-the-input-digest-covers-and-what-it-must-not)
- [Acceptance is recorded, not asserted](#acceptance-is-recorded-not-asserted)
- [The three consistency registries](#the-three-consistency-registries)
- [Why `registry check` exits 0, when the two `status` commands do not](#why-registry-check-exits-0-when-the-two-status-commands-do-not)
- [What the registries cannot see](#what-the-registries-cannot-see)
- [Why a registry excerpt is not hashed into a unit's contract](#why-a-registry-excerpt-is-not-hashed-into-a-units-contract)
- [Assembling the book](#assembling-the-book)

## The constraint everything here answers

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

## The spec artefact, and its sign-off

`python -m src.draft spec` (`src/spec/`) owns one Markdown file per
book and a sign-off record beside it:

```text
content/drafts/twins/           the book's units, once they are drafted
  -> content/specs/twins/spec.md      the outline, edited by a human
     content/specs/twins/signoff.md   written by `spec sign`
```

That mirroring is the rule `content/dossiers/`, `content/rendered/` and
`content/review/` already follow, read one level up: those mirror a
single *draft*, so they carry the draft's parent directory. A book is a
*directory* of drafts, so its own path is what carries over.

The outline is four heading levels, and no more:

| Markdown | Is | Generates |
|---|---|---|
| `# Title` | the book | -- |
| `## Part {#part-i}` | a part | -- |
| `### Chapter {#ch-1}` | a chapter | -- |
| `#### Section {#sec-1}` | a **section** | one unit of prose |

The section is the generation unit (#137), which is why nothing sits
below it: a level deeper would be a unit nothing generates. Text beneath
a heading is that unit's **brief** -- what it must establish, and what it
leaves to another unit. Text before the first heading belongs to no unit
and is never handed to a generator; it is the preamble for whoever opens
the file.

Planned top-down, generated bottom-up. `spec show --unit <id>` prints one
unit's slice -- its title, its kind, the part and chapter above it, its
brief, and whether the outline is signed off -- and that slice is what a
genre skill generates from, instead of inventing structure per
invocation.

[CLI.md](CLI.md#python--m-srcdraft-spec) has the flags.

## Why an id is required on every heading

Every part, chapter and section carries an explicit `{#some-id}`, and a
heading without one is a parse problem rather than something the parser
guesses at.

A derived id -- slugified from the heading text, say -- changes the
moment someone rewords the heading, and every unit already written
against the old spelling silently becomes an orphan. At chapter scale a
person notices; across 300 pages nobody does. The same ids are what the
cross-reference graph (#138) resolves against, so they have to
outlive an edit to the words around them.

`spec show`, `spec sign` and `spec status` all refuse a spec that does
not parse, and print **every** problem rather than the first: someone
fixing an outline wants the whole list, not one round trip per missing
id.

## Why sign-off is a sibling file

`spec sign` records a twelve-hex digest of `spec.md` -- the same shape as
the dossier's corpus fingerprint, and for the same reason: enough to
answer "is this the same document?", short enough to sit on one line.

It goes in `signoff.md` rather than into `spec.md` itself because writing
the digest into the file would change the file it just measured, and no
later read could ever match. The digest covers `spec.md` alone, so
`spec status` can tell three states apart:

| State | Exit | Means |
|---|---|---|
| signed off at digest `x` | 0 | the approved outline is the one on disk |
| not signed off | 1 | nobody has approved this outline yet |
| changed since sign-off | 1 | approved at one digest, now another |

`signoff.md` carries **no timestamp**, the same rule the review layer's
reports follow: two sign-offs of an unchanged outline produce
byte-identical files, so "did this change?" is a diff. *When* it was
approved is not a question any check asks; *what* was approved is.

## What `status`'s exit code is, and is not

`spec status` exits non-zero on an outline that is unsigned or has
drifted. That is not a new gate, and the distinction matters enough to
state rather than leave to a reader.

[ARCHITECTURE.md](ARCHITECTURE.md)'s "Layer 4" draws the line by **what a
check is measured against**: the citation gate is measured against the
ledger, which is ground truth, while a check measured against a recorded
preference reports and never blocks, however mechanical its answer.
`spec status` is measured against neither. It reads back a record of a
*person's decision* -- did a human approve this outline? -- and reports
it. It judges no draft's content, refuses no write, and blocks no draft:
`python -m src.draft gate` remains the only gate in this project, and
`.claude/hooks/citation_gate_hook.py` remains the only automatic refusal.

What the exit code buys is that a genre skill can ask the question
without parsing prose. What a skill does with the answer -- stop and ask
the human to approve the outline first -- is the human gate itself, not a
machine outranking anybody.

## The generation unit, and its contract

`python -m src.draft unit` (`src/unit/`) fixes the unit of generation at
the **section**, not the chapter. Small enough that the spec slice, the
grounding sources and the genre instructions fit in a context budget with
room to spare -- which is what makes a unit independently regenerable,
and independent regeneration is what makes "regenerate one section fifty
times while 200 pages sit untouched" cheap.

The contract is explicit in both directions:

| In | Out |
|---|---|
| the spec slice (title, brief, the part and chapter above it) | the unit's prose at `content/drafts/<book>/<unit-id>.md` |
| the sources it is grounded in, given as `--source <citekey>` | the citekeys it actually cites, recorded |
| registry excerpts (#138; empty until then, and part of the digest) | the claims it registers (#138) |

```bash
python -m src.draft unit contract content/drafts/twins sec-model --source smith_2024
python -m src.draft unit contract content/drafts/twins sec-model --json
python -m src.draft unit accept   content/drafts/twins sec-model --source smith_2024
python -m src.draft unit status   content/drafts/twins
```

A part or a chapter has no contract, and asking for one is refused rather
than answered with an empty contract: those levels name no prose of their
own.

## What the input digest covers, and what it must not

`input_digest` is what makes an unchanged unit free to re-run. It covers
the spec slice, the sorted set of sources, and the registry excerpts --
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

## Acceptance is recorded, not asserted

`unit accept` writes `content/specs/<book>/units/<unit-id>.json`: the
input digest the prose was generated against, the sources, what it cites,
and a digest of the prose itself. It refuses three ways, each for a
stated reason:

1. **The outline is not signed off** -- there is nothing to accept a unit
   against until a human has approved the structure.
2. **There is no draft** -- generate the unit from its contract first.
3. **The citation gate refuses the draft.** `accept` *invokes*
   `python -m src.draft gate` rather than re-implementing or replacing
   it. A unit nobody may cite from is not a unit a book may assemble
   from, and this is the existing gate doing its existing job -- not a
   second one.

`unit status` re-derives all three digests, so it distinguishes:

| State | Means |
|---|---|
| `unwritten` | no draft on disk |
| `drafted` | prose exists, nobody accepted it (also what an unreadable record reads as) |
| `accepted` | the record matches both the current contract and the prose |
| `stale: inputs changed` | the outline moved under an accepted unit |
| `stale: draft changed since accepted` | the prose moved after acceptance |

It exits 0 only when every unit is accepted and current -- the same
standing as `spec status`: a report over on-disk artefacts and recorded
human decisions, which blocks no write and gates no draft.

Records carry **no timestamp**, so accepting an unchanged unit twice
produces byte-identical files and a diff of `content/specs/` is a diff of
what was accepted.

## The three consistency registries

`python -m src.draft registry` (`src/registry/`) is the artefact-management
answer to cross-chapter consistency. At thesis scale one can partly cheat
with a large context; at book scale it is entirely an artefact problem.

```bash
python -m src.draft registry build   content/drafts/twins
python -m src.draft registry check   content/drafts/twins
python -m src.draft registry excerpt content/drafts/twins sec-data
```

| Registry | Written from | Flags |
|---|---|---|
| terminology and notation | `- **Term** -- definition` bullets | a term defined in more than one unit |
| claims | every sentence that cites something | the same claim made in more than one unit |
| cross-references | `[text](#id)` and `\ref{id}`/`\cref{id}` | a reference no unit or outline entry defines |

Three properties hold for all of them:

- **Built from accepted units only**, and the count is printed: `3 of 12
  unit(s) accepted and read`, naming the ones it could not see. A registry
  over half a book is not the same claim as one over all of it.
- **Nothing here is written by an LLM.** They are a deterministic reading
  of accepted prose, which is the whole reason they can be trusted --
  the same standing `src/ledger.py` has as a reading of a real bib file.
- **The conventions are borrowed, not invented.** The definition bullet is
  the dossier glossary's, the sentence splitter is the provenance aid's,
  and everything from a `## References` heading onward is cut the way
  `src/acronyms.py` cuts it -- measured there against the real 15-chapter
  book, because a rendered reference list is nothing but citation-bearing
  lines and would otherwise fill the claim register with bibliography.

**A cross-reference is never spelled `@id`.** That is a citekey position:
a section id reaching it would put something the ledger has never seen
where only a real bibliography entry may go. `tests/test_registry.py`
pins that the citation gate reads neither supported reference syntax as a
citekey.

## Why `registry check` exits 0, when the two `status` commands do not

`spec status` and `unit status` exit non-zero. `registry check` never
does, however much it finds -- and the difference is not inconsistency.

[ARCHITECTURE.md](ARCHITECTURE.md)'s "Layer 4" is explicit that a check
measured against a recorded preference "reports and never blocks,
**whichever layer it lives in**", and that what may be enforced is
*invocation* rather than conformance: "a harness may guarantee that it
runs and that its findings are seen, never that they were obeyed."

The two `status` commands report whether a **human decided** something --
approved this outline, accepted this unit. This one reports a **machine's
reading of prose**: which term it thinks was defined where, which
sentences it thinks match, which reference it thinks dangles. That is
judgement however mechanical the arithmetic, so it is evidence and never
a verdict. There is no flag that changes this, deliberately:
DEVELOPER-AGENTS.md bars promoting a new check into a gate outright
rather than leaving it to an argument about how precise the check is.

What #138 calls a "blocking global check" is therefore delivered as
guaranteed invocation: the assembly step (#139) must run `registry check`
and surface what it says, and the second human sign-off is what decides.
That is a stronger reading of the requirement than an exit code would be,
not a weaker one -- an exit code can be ignored by a caller; a sign-off
cannot be given by one.

## What the registries cannot see

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

## Why a registry excerpt is not hashed into a unit's contract

`registry excerpt <book> <unit-id>` prints what a unit's generation
should be told about the rest of the book: the terminology the *other*
accepted units settled, and the ids it may point at. A unit is never told
to conform to itself.

That excerpt is deliberately **not** part of the unit's input digest, and
the reason is the cascade. A registry grows with every acceptance, so
hashing it in would mark every later unit stale each time an earlier one
was accepted -- which destroys exactly the property #137's contract
exists for, that an unchanged unit costs nothing to re-run. Instead the
excerpt is injected at generation time, and inconsistency is caught
afterwards by `registry check` over the whole book. `registries` stays in
the contract's shape, empty and labelled, so a caller that does want to
pin one has somewhere to put it.

## Assembling the book

The last step, and deliberately the smallest: `.claude/skills/book-assembler/`,
a skill rather than a module. Everything it assembles has already passed
every gate per unit, so assembly is deterministic composition plus a
human sign-off -- there is no enforcement machinery here to write.

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

The bibliography points at the user's own `.bib` file, never a copy: the
reference manager is upstream, and this pipeline is downstream of it.
Which stack loads it is **probed, not assumed** -- biblatex/biber where
both are installed, natbib/bibtex otherwise. That is not a hypothetical
courtesy: the host this was first exercised on has `pdflatex` and neither
`biblatex.sty` nor `biber`, and a document that assumed them built
nothing at all.

`thesis-chapter-writer`'s output is already an `\input`-able fragment. A
unit drafted in Markdown is converted with `pandoc --natbib
--top-level-division=chapter` -- **not** `python -m src.draft render
--format tex`, which is the publish step for one draft and emits a
standalone `article` with a bibliography of its own. The first real
assembly also found that pandoc truncates a citekey at `--`
(`@lim_state---art_2020` reaches LaTeX as `lim_state` and renders as
`[?]`), so those citations are rewritten to raw `\citep{}` in a temp
copy first, keeping the key byte-identical to the one in the `.bib`.

**Where #138's "blocking" actually lives.** The skill must run
`registry check` and print every finding, in full, before composing --
which is the guaranteed *invocation* ARCHITECTURE.md permits, in place of
the conformance it does not. `tests/test_skill_book_assembly.py` pins
that, so a hand edit dropping either half fails the suite.

The skill refuses in one direction only: it stops. A unit that is
missing, unaccepted or stale sends the user back to a genre skill or to
`draft-reviser`, and it never drafts or edits prose itself. It presents
what it composed -- the unit count, what the registries could not read,
every finding, what the gate and the two review aids said -- and stops
there. **It does not say the book is finished.** Nothing in this pipeline
has read the argument: the checks establish that a book is grounded,
consistent and complete, and never that it is any good. That judgement is
the second human gate, and it is the user's.

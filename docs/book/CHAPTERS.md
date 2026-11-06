# ✏ Write and accept the chapters

Status: **tutorial**, steps 3, 3b and 4 of [Write a book](../WRITE-A-BOOK.md).

**Written for** whoever writes the chapters: you, a co-author, or a
genre skill working from a contract. **Assumed:** a signed outline
([step 2](SIGN-OFF.md)). **Not covered here:** how each genre drafts a
chapter; the table in step 3 points at each genre's own tutorial.

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
seed for them; each is still a unit, written as one file named for the
chapter's id. For each chapter the outline describes at section
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
| teaching material, worked examples, exercises | [WRITE-A-TEXTBOOK-CHAPTER.md](../WRITE-A-TEXTBOOK-CHAPTER.md) |
| a hands-on lab the reader follows at a keyboard | [WRITE-A-TUTORIAL.md](../WRITE-A-TUTORIAL.md) |
| a literature map or state-of-the-art chapter | [WRITE-A-SURVEY.md](../WRITE-A-SURVEY.md) |
| an RQ-driven argument | [WRITE-A-THESIS-CHAPTER.md](../WRITE-A-THESIS-CHAPTER.md) |
| a multi-perspective, contradiction-mapped report | [WRITE-A-DEEP-RESEARCH-REPORT.md](../WRITE-A-DEEP-RESEARCH-REPORT.md) |

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
([what else the digest covers](DESIGN-NOTES.md#-what-the-input-digest-covers-and-what-it-must-not)).
Registry excerpts are handed to the generator but deliberately left out
of that digest
([why](DESIGN-NOTES.md#-why-a-registry-excerpt-is-not-hashed-into-a-units-contract)).

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

**Which entries are units**, so you know which files to write:

| The outline says | The unit is | Its file |
| --- | --- | --- |
| a chapter with two or more sections, or one section titled differently from the chapter | the chapter | `<chapter-id>.md` |
| a chapter with exactly one section carrying the chapter's own title (a [retrofitted](RETROFIT.md) book) | that section | `<section-id>.md` |
| a chapter with no sections (`ch-cost`, a preface, an appendix) | the chapter | `<chapter-id>.md` |
| `{#glossary}`, `{#symbols}`, `{#figures}`, `{#tables}` | none: generated at assembly | none |
| a part (`{#front}` and `{#back}` included) | none | none |

**Not every unit goes through a genre skill.** A preface, an
acknowledgements page or an "about the author" page is in your own
voice, so you write it by hand, and it is accepted exactly like a
chapter: `unit accept` needs only the citation gate to pass, which a page
citing nothing does. [Front matter](FRONT-MATTER.md) has the workflow.

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
[why a chapter is the authored document](DESIGN-NOTES.md#-why-a-chapter-is-the-authored-document)
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
   ([why](DESIGN-NOTES.md#-why-sign-off-is-recorded-per-chapter)).
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
   [CLAUDE.md](../../CLAUDE.md)'s one rule exists to prevent. It is
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
  ch-cost                  unwritten                              dossier: no dossier
  ch-fidelity              stale: draft changed since accepted    dossier: disagrees
  ch-sync                  unwritten                              dossier: no dossier

  1 of 4 unit(s) accepted and current.
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

**An acceptance record whose unit has left the outline is listed, not
deleted.** Remove `### What a twin costs {#ch-cost}` from `spec.md`
after accepting it, and `unit status` adds a line after its summary:

```text
  accepted, but no longer in the outline: ch-cost (records and prose are left on disk)
```

`--json` carries the same ids under `"orphaned"`. They do not count
towards the exit code, and nothing deletes `units/ch-cost.json` or
`ch-cost.md`: the prose is yours, and whether to keep it is your call.
[Changing the outline after sign-off](CHANGING-THE-OUTLINE.md) has the
rest of that workflow.

Next: [build the registries](REGISTRIES.md).

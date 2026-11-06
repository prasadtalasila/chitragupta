# 💡 Design notes: why the book track works this way

Status: **explanation**, part of [Write a book](../WRITE-A-BOOK.md).

**Written for** anyone who wants the reasoning behind a step, or is
about to change one. **Assumed:** the steps themselves, which each link
here for the part they rest on. **Not covered here:** how to run
anything; the step pages do that.

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
[retrofitting](RETROFIT.md) each
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
is every retrofitted book and why they keep working unchanged; and a
chapter that declares no sections at all (a preface, an appendix, a
chapter planned only by its brief) is one by itself. Before #1137 that
last kind produced no unit, so a section-less chapter could never be
accepted and was silently missing from the book.

A third sense of the word lives in `chitragupta/review/_units.py`: the
scale the multi-source rule binds at, which is **genre-dependent**
(paragraph for a thesis chapter, section for a textbook one). That one is
about evidence and this one about artifacts, so they are not expected to
agree.

## ✅ What `status`'s exit code is, and is not

`spec status` and `unit status` exit non-zero on an outline nobody has
signed or a unit nobody has accepted. That exit code is not a new
gate.

[ARCHITECTURE.md](../ARCHITECTURE.md)'s "Layer 4" draws the line by **what a
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

[ARCHITECTURE.md](../ARCHITECTURE.md)'s "Layer 4" is explicit that a check
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
check is. `registry build --glossary` exiting 1 is not such a flag: it
is a build declining to write a page with terms missing from it, and
`check` reports the same bullets and still exits 0
([the pages](REGISTRIES.md#-the-glossary-and-the-list-of-symbols)).

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
([PLAGIARISM.md](../PLAGIARISM.md) does the same for the tier that needs an
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

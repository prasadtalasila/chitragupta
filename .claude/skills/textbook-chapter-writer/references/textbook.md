# Textbook chapter: what this genre alone needs

Read a section of this file when the step that sent you here cites it;
each section opens with when it applies. Paths here are from the project
root. Writing rules for the genre are in
`docs/writing-standards/genres/textbook-chapter.md`; this file holds how
to build the chapter's teaching parts and how its dossier differs.

## 1. Objectives and motivation

Read this before you write the learning objectives, and again before the
motivation section.

**The objectives come first, and everything else serves them.** Write 3
to 5 "by the end of this chapter, students will be able to..."
statements, each with an observable verb (*derive*, *compare*,
*implement*, *predict*), never *understand* or *appreciate*, which no
exercise can assess. A section, example or exercise that serves none of
them is dropped.

**Scope and prerequisites sit near the top.** Say what the chapter
covers, what it deliberately leaves out, and what the student is assumed
to know already. A student who cannot tell whether they are equipped
for a chapter either bounces off it or loses an hour discovering the
background they lacked.

**Establish the need before the mechanism.** The motivation section is
short, says why the topic matters, and is pitched at an undergraduate
who has not read the literature. A chapter that presents mechanism
without ever answering "why would anyone need this" produces students
who can follow the steps and cannot transfer them.

**Searching the corpus for a motivating example is optional.** If you
already have a good example, you need not search at all. If you do,
over-fetch, read each 500-character snippet yourself rather than
trusting the score, and reformulate and search again if the first pass
turns up nothing genuinely useful: do not settle for a weak match
because it ranked first. Log every call to the draft, even here where
citing is optional: the dossier's status report re-asks the logged
queries against the corpus to say which newly synced papers this chapter
has never seen.

**Finding a good example does not oblige a citation.** Cite it only if
attributing it to a specific paper helps the student ("this is a real
system described in ..."); otherwise let it inform a well-chosen analogy
without a reference. Never manufacture a citation to have one. Anything
you do cite is a real citekey from a search result, never one you wrote
yourself.

## 2. Source diversity within a section

Read this when a section of the chapter cites more than one paper.

The floor is the core's §11 at this genre's unit, the section: a section
that cites at all spans two or more citekeys, and its consecutive
paragraphs do not rest on the same single citekey. This is how to get
there while searching, not a second rule.

**Do not let one citekey carry a section because it was the first good
hit.** When a search turns up more than one paper that plausibly
supports a paragraph, compare them and prefer the one that adds a
distinct angle, rather than defaulting to the key you used a paragraph
or two ago. Before reusing the same citekey a third time within one
section, search once more for a different paper covering the same
point; if there is one, cite it instead of, or beside, the first, so the
section's point of view does not narrow to one author's framing.

**One source that really is the only one is fine.** Do not force in a
second citation where none fits; mark the run with the single-source
marker instead. The failure to watch for is repeated, unexamined reuse
of one key across a section, not deliberate reliance on the source that
genuinely fits best each time.

## 3. Worked examples and exercises

Read this before you write the first worked example, and again before
the exercises.

**A worked example shows the reasoning, not only the steps.** Make it
concrete and step by step, with enough detail that a student could
reproduce it, and say at each step why this move and not another. An
example that shows only the steps teaches imitation; one that shows the
choice behind each step teaches the method.

**Construct the example for the course level.** Prefer an original
example suited to the reader over lifting a paper's treatment, which is
likely pitched at a more advanced reader.

**Fade the support.** Where the chapter has room for more than one
example, work the first fully, leave one step of the next to the
reader, and pose the last as a problem. Dropping a student straight
from a fully worked example to an unaided exercise is the standard
cliff, and fading is the standard fix.

**Exercises exercise the objectives, not recall of the reading.** Mix
the difficulty, using only the three grades the label allows; the grade
is a difficulty rating for the student, not a defect marker. Give either
solutions or hints, and say which. Every exercise maps to a stated
objective: say which, at least in your own notes, and cut any exercise
that maps to none.

**A table here is usually a table of symbols, units or parameter
values.** It is captioned, marked and read like any other table; a
student meeting a table with no lead-in has to guess what to compare.

## 4. The dossier in this genre

Read this before you record anything in the dossier's `evidence.md` or
`rejected.md`, and again if you are unsure whether something the user
said belongs in `steering.md`.

**The weight sits in `scope.md` and `rejected.md`, not `evidence.md`.**
This chapter is mostly original worked examples and exercises, so
`evidence.md` stays thin and may well be empty. There is no long
evidence table to build, and padding one out is not the job. What a
later revision needs is in `scope.md` (the reader, the prior knowledge
assumed, the covers and does-not-cover line, and the glossary that
keeps notation stable across a revision) and in `rejected.md`.

**A source worth recording gets the full block.** On the rare occasion
one is kept, it gets the same `relevance:`/`claim:`/optional `quote:`
block the citation-dense genres use: `claim:` in your own words, and
`quote:` only where a quotation is genuinely warranted, such as a
definition worth giving in its originator's exact words. Never a
shortcut `support:` line.

**`rejected.md` records pedagogical rejects here, not bibliographic
ones**: the worked example that turned out too advanced for the course
level, the analogy that broke down one step in, the exercise cut
because it mapped to no objective, the figure considered and dropped.
The file has no schema and nothing parses it beyond backticked
citekeys, so a row naming an example rather than a paper is exactly
what it is for. A row for each cut stops a later revision reintroducing
something already judged and dropped.

**A chapter with no citations at all still gets a dossier**, including
one drafted after the user was told the ledger is empty and said to
proceed uncited. The reader, the scope, the glossary and the rejected
examples exist whether or not a single citation does.

**Pedagogical steering is the kind that undoes most quietly.** "Second
years, not first years", "assume no probability", "more exercises and
fewer worked examples", "drop the compiler example": nothing in the
finished chapter shows that an easier example was ever on the table, so
a revision that has not read `steering.md` will undo it.

## 5. Why the evidence sidecar is often absent

Read this if the sidecar command prints `no quoted evidence recorded`,
or the user asks why the chapter has no sidecar.

That is the right outcome, not a gap to fill. It follows from what the
genre is rather than from a separate decision: the chapter is not
citation-dense, most of it is original worked examples and exercises,
and its `evidence.md` is thin by design. Sources here are cited for
motivation and background, and motivation is the last place a verbatim
quotation earns its keep, so most chapters capture no `quote:` at all.
Where a chapter does quote a source deliberately, the sidecar is where
a student can see the quotation attributed.

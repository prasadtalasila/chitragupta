# 📘 Write a textbook chapter, start to finish

Status: **tutorial.** Written 2026-09-15.

**Written for** a lecturer or course author who wants a chapter of
teaching material -- learning objectives, motivation, worked examples,
exercises -- and who has not used this pipeline before. **Assumed:**
nothing. This page repeats what other documents also say, deliberately.
**Not covered here:** why each prose rule exists
([WRITING-STANDARDS.md](WRITING-STANDARDS.md)) and how a whole book is
assembled from chapters ([WRITE-A-BOOK.md](WRITE-A-BOOK.md)).

Sister tutorials: [a survey](WRITE-A-SURVEY.md),
[a thesis chapter](WRITE-A-THESIS-CHAPTER.md),
[a tutorial](WRITE-A-TUTORIAL.md),
[a deep-research report](WRITE-A-DEEP-RESEARCH-REPORT.md).

## 🧭 Table of contents

- [Is this the genre you want?](#-is-this-the-genre-you-want)
- [What you will have at the end](#-what-you-will-have-at-the-end)
- [Before you start](#-before-you-start)
- [Step 1: the student, the objectives, the slug](#-step-1-the-student-the-objectives-the-slug)
- [Step 2: open the dossier](#-step-2-open-the-dossier)
- [Step 3: write an outline (optional, recommended)](#-step-3-write-an-outline-optional-recommended)
- [Step 4: ask for the chapter](#-step-4-ask-for-the-chapter)
- [Step 5: gate, references, render](#-step-5-gate-references-render)
- [Step 6: read the review aids](#-step-6-read-the-review-aids)
- [Step 7: change something](#-step-7-change-something)
- [Step 8: chapters into a book](#-step-8-chapters-into-a-book)
- [When something goes wrong](#-when-something-goes-wrong)

## ⚖ Is this the genre you want?

A textbook chapter is for a student who is **studying** the topic, not
yet doing it. It explains, then shows worked applications.

If your reader will be sitting at a keyboard following your steps to a
working result, you want [a tutorial](WRITE-A-TUTORIAL.md) instead.
If your reader is a researcher mapping a field, you want
[a survey](WRITE-A-SURVEY.md).

This genre is **not citation-dense**. Most of the content is your own
worked examples and exercises; the corpus is there for motivation and
background. Citations are still gated -- any that appear must be real --
but a chapter with three citations is normal, not thin.

## 🎯 What you will have at the end

For a chapter you decide to call `course/ch3-state-estimation`:

| Path | What it is |
| --- | --- |
| `content/drafts/course/ch3-state-estimation.md` | the chapter -- the canonical copy |
| `content/dossiers/course/ch3-state-estimation/` | scope, objectives, any evidence kept, every search run |
| `content/rendered/course/ch3-state-estimation.pdf` | the typeset chapter |
| `content/rendered/course/ch3-state-estimation.tex` | the same, as LaTeX, for your course template |
| `content/rendered/course/ch3-state-estimation.md` | a numbered Markdown copy |

## 🔧 Before you start

```bash
pip install chitragupta-cli
chitragupta init my-course
cd my-course

mkdir -p papers
cp /path/to/your-library.bib papers/bibliography.bib

chitragupta corpus sync
chitragupta corpus ledger
```

Or clone the repository and `cp config.toml.example config.toml` instead
of the first two lines.

A textbook chapter can be written against a small corpus -- you need
enough to motivate the topic and point students onward, not a full
literature map. If you have no library at all, the chapter can still be
drafted; it simply cites nothing, and the gate has nothing to check.

> Every command here also works as `python -m chitragupta.<layer> ...`.

## 🎓 Step 1: the student, the objectives, the slug

**The student** is your reader, stated concretely: "second-year
undergraduates who have had one linear-algebra course and no signals
course". Everything -- what is assumed, what is recapped, how fast the
worked examples move -- follows from that sentence.

**The learning objectives** are three to five, each concrete and
testable. "By the end of this chapter a student can..."

- ...state what a state estimator does and why a raw measurement is not
  enough.
- ...derive the one-dimensional Kalman update from the two variances.
- ...hand-compute two steps of the filter on given numbers.
- ...say when the assumptions fail and what happens then.

Write these before anything else. They are the chapter's contract, and
the exercises at the end are how a student checks they hold.

**The slug** is the path under `content/drafts/`:

| You are writing | Use |
| --- | --- |
| one chapter of a course | `course/ch3-state-estimation` |
| a chapter of a book being assembled | `books/control/ch3-state-estimation` |
| a standalone handout | `state-estimation-handout` |

## 🗂 Step 2: open the dossier

```bash
chitragupta draft dossier init \
    content/drafts/course/ch3-state-estimation.md --genre textbook-chapter
```

That writes eight files. **Exactly one is yours to fill in: `scope.md`.**
The rest -- `evidence.md`, `rejected.md`, `sections.md`, `retrieval.md`,
`steering.md`, `revisions.md`, `README.md` -- are written for you as the
chapter is produced.

### What goes in `scope.md`

`init` writes it with every heading present and empty. Five things are
yours:

| Field | What goes in it | Why it is asked for |
| --- | --- | --- |
| `- language:` | a BCP-47 tag: `en-GB`, `en-US`, `en-IN` | ships **unset**; a chapter whose dialect nobody chose silently gets the model's own |
| `## Reader` | the student, concretely, including the courses they have had | decides what is assumed, what is recapped, and how fast the worked examples move |
| `## Covers` | the chapter's content **and its learning objectives** | this genre has no other home for the objectives, and they are the chapter's contract |
| `## Does not cover` | what is deferred to a later chapter or a lab | students who see a term with no treatment assume they missed it |
| `## Glossary` | each recurring term with one definition | a term that drifts between sections is a student's lost afternoon |

Set the dialect with the command, so the format is right:

```bash
chitragupta draft dossier set-language \
    content/drafts/course/ch3-state-estimation.md en-GB
```

A filled-in textbook-chapter `scope.md` -- the whole file is at
[`examples/dossiers/textbook-chapter/scope.md`](examples/dossiers/textbook-chapter/scope.md):

```markdown
# Scope

- genre: textbook-chapter
- language: en-GB
- draft: content/drafts/course/ch3-state-estimation.md
- created: 2026-09-15
- corpus: 214 citekeys, digest `a31f0c4b77de`
- draft digest: not recorded (run `dossier stamp` once the draft is ready)

## Reader

Second-year undergraduates who have had one linear-algebra course and no
signals or probability course beyond a first module. They have seen a
mean and a variance; they have not seen a covariance matrix, and will
not in this chapter.

## Covers

Why a raw measurement is not enough; the one-dimensional estimator built
from two variances; two steps worked by hand; a faded example the
student finishes; and an honest section on which assumptions break.

Learning objectives -- by the end a student can:

1. state what a state estimator does and why a raw reading is not enough;
2. derive the one-dimensional update from the two variances;
3. hand-compute two steps on given numbers;
4. say when the assumptions fail and what happens then.

## Does not cover

The matrix form. That is chapter 4, and reaching for it here would cost
the derivation its arithmetic-only property.

Implementation. There is no code in this chapter -- students who want to
build one are pointed at the lab, which is a tutorial.

## Glossary

- **State** -- the quantity we want to know and cannot measure directly.
  Never "the system" or "the value".
- **Estimate** -- our current best guess of the state, always paired
  with its variance. A number without its variance is never called an
  estimate in this chapter.
- **Gain** -- the weight given to a new measurement against the current
  estimate, between 0 and 1.
```

Putting the objectives in `## Covers` is the convention for this genre:
they are scope, they are what the exercises test, and a later revision
that quietly drops one is then visible.

## 🗺 Step 3: write an outline (optional, recommended)

A textbook chapter has a shape students expect, and declaring it is
cheap:

```bash
chitragupta draft dossier init \
    content/drafts/course/ch3-state-estimation.md \
    --genre textbook-chapter --outline
```

Edit `content/dossiers/course/ch3-state-estimation/outline.md`. Three
fields per section:

| Field | What goes in it | What the skill does with it |
| --- | --- | --- |
| `brief:` | steering in your own words -- what to emphasise, what to leave out, how long | consumed once, **never appears in the chapter** |
| `claim:` | your own prose, where you want a specific statement made | rewritten and grounded; anything the corpus cannot support is reported rather than shipped |
| `queries:` | a `-` list of search terms | run **verbatim** instead of the skill inventing sub-themes |

A section needs at least a `brief:` or a `claim:`. **In this genre most
sections have only a `brief:` and no `queries:` at all** -- a worked
example and a set of exercises are yours to design, not the corpus'. An
outline here that is almost all briefs is correct, not thin.

A worked example -- the whole file is at
[`examples/dossiers/textbook-chapter/outline.md`](examples/dossiers/textbook-chapter/outline.md):

```markdown
## Learning objectives

brief: The four objectives, verbatim as agreed. No prose around them.

## Why a raw measurement is not enough

brief: Motivate before mechanism. One concrete scenario -- a robot whose
wheel encoder drifts -- carried through the whole chapter.

queries:

- state estimation sensor noise motivation

## The idea in one dimension

brief: Build the update from two variances. Arithmetic only, no matrix
algebra -- that is chapter 4.

## Worked example: two steps by hand

brief: Fully worked, every number shown. Then a faded version where the
student supplies the second step.

## When the assumptions fail

brief: Non-Gaussian noise and an unmodelled bias. Honest about what
breaks; this is where students who go on to research start.

queries:

- kalman filter assumption violation bias

## Exercises

brief: Six, mixed difficulty, hints for the last two. At least one that
cannot be done by pattern-matching the worked example.

## Summary and where to go next
```

Validate:

```bash
chitragupta draft dossier outline \
    content/drafts/course/ch3-state-estimation.md --check
```

## 🗣 Step 4: ask for the chapter

> Draft a textbook chapter on one-dimensional state estimation into
> `content/drafts/course/ch3-state-estimation.md`, for second-year
> undergraduates with one linear-algebra course. The objectives and
> outline are in the dossier.

"Textbook chapter", "lecture notes", "course reader" or "worked-examples
handout" selects `textbook-chapter-writer`.

What it does: establishes the objectives, states scope and
prerequisites, motivates the need before the mechanism, writes worked
then faded examples, writes exercises with hints or solutions, closes the
loop with a summary, and reads the whole thing back as the student before
handing it over. Where it cites, it cites real citekeys from your corpus
only.

## ✅ Step 5: gate, references, render

```bash
chitragupta draft gate content/drafts/course/ch3-state-estimation.md
```

If the chapter cites nothing, the gate passes trivially -- that is
expected for this genre, not a warning sign.

If it does cite, build the references section from exactly the gated
keys:

```bash
chitragupta draft references content/drafts/course/ch3-state-estimation.md
```

Render:

```bash
chitragupta draft render \
    content/drafts/course/ch3-state-estimation.md --format pdf
chitragupta draft render \
    content/drafts/course/ch3-state-estimation.md --format tex
chitragupta draft render \
    content/drafts/course/ch3-state-estimation.md --format md
```

Then stamp:

```bash
chitragupta draft dossier stamp \
    content/drafts/course/ch3-state-estimation.md
```

## 🔍 Step 6: read the review aids

All advisory, all exit 0.

```bash
chitragupta draft style content/drafts/course/ch3-state-estimation.md
chitragupta review verbatim scan \
    content/drafts/course/ch3-state-estimation.md
chitragupta review figure content/drafts/course/ch3-state-estimation.md
```

What each is for here:

| Aid | Reads for | Why it matters in teaching material |
| --- | --- | --- |
| `review verbatim` | wording shared with any parsed source, cited or not | **the one that matters most.** A chapter that reuses a source's wording is a copyright problem in a way a private research note is not |
| `draft style` | defect markers, an acronym never expanded at first use, dialect | a student meets every acronym for the first time; an unexpanded one costs them the paragraph |
| `review figure` | overlapping nodes, overlong labels, and the edge list | confirm the edge list against your own prose -- a diagram that wires the concepts up wrongly teaches the wrong thing convincingly |

`review uncited` is deliberately gentler on this genre: prose with no
citation is the normal state of a textbook, not a finding.

### The agenda: all of them as one worklist

[AGENDA.md](AGENDA.md) explains every section of an agenda file in
full; what follows is the short version for this genre.

```bash
chitragupta review agenda content/drafts/course/ch3-state-estimation.md
```

It **reads the aids' filed JSON and never runs an aid**, so run them
first with `--write`. Items are `[unattended]` (safe to repair
automatically: `prose`, short verbatim runs, `missing-citekey`) or
`[surfaced]` (yours to judge).

A chapter that cites lightly produces a short agenda, and that is the
expected shape here:

```markdown
# Agenda: content/drafts/course/ch3-state-estimation.md

> **Review aid, not a gate.** This report is evidence for a human
> judgement, never a verdict. No draft is blocked by what it says.

- Draft: `content/drafts/course/ch3-state-estimation.md`
- Command: `chitragupta review agenda content/drafts/course/ch3-state-estimation.md`

## Sources

- Citation provenance: read
- Verbatim scan: read
- Citation coverage: not run
- Multi-source synthesis: read, no item class defined
- TikZ layout check: read
- Uncited prose: read
- Quotation integrity: not run
- Claim support: read
- Prose (style_check): read
- Dossier drift: read

## Summary

- 3 prose
- 1 verbatim-run

## Findings

### prose

- `5a8bf91ec244` [unattended] (2. Why a raw measurement is not enough):
  chitragupta.AcronymNotExpanded: 'RMS' used before first expansion
- `c14d0b7e9a33` [unattended] (5. When the assumptions fail):
  chitragupta.DefectMarker: 'obviously' (1x)
- `7e2a55c1b09d` [unattended] (6. Exercises): chitragupta.DialectDrift:
  'analyze' -- scope.md records en-GB

### verbatim-run

- `1561cffaa101` [unattended] (2. Why a raw measurement is not enough):
  10-word verbatim run citing `bar_shalom_estimation_2001`
```

**How to read that as the author.** All four are `[unattended]`, which
is typical for a chapter whose content is mostly your own: an acronym a
student meets before its expansion, a hedge word, a US spelling in a
chapter that declared `en-GB`, and one phrase that matches a textbook you
cited. Hand them off -- ask to "work the review agenda" and
`agenda-reviser` repairs them one at a time, re-running the gate after
each and logging every attempt in `revisions.md`.

The `DialectDrift` finding is only possible because `scope.md` records
`language: en-GB`. Leave that line unset and this whole class of finding
silently does not exist.

To check a round of edits helped:

```bash
chitragupta review agenda content/drafts/course/ch3-state-estimation.md \
    --baseline content/review/course/ch3-state-estimation.agenda.json
```

That re-runs the aids and reports each finding as `resolved`,
`persisting`, `new` or `accepted` -- read the `new` list, not just the
count.

## 📝 Step 7: change something

Never re-run the genre skill. Ask for a revision:

> Exercise 4 is harder than the worked example prepares them for. Replace
> it with one that uses the same numbers as the worked example, and move
> the current one to the end as a challenge.

That selects `draft-reviser`, which edits only what is affected and logs
it in `revisions.md`.

After a hand edit:

```bash
chitragupta draft gate content/drafts/course/ch3-state-estimation.md
chitragupta draft dossier stamp \
    content/drafts/course/ch3-state-estimation.md
```

Back it up -- `content/drafts/` is gitignored:

```bash
chitragupta draft dossier export course/ch3-state-estimation
```

## 📗 Step 8: chapters into a book

If this chapter is one of many, the book track keeps them consistent: a
signed outline (`chitragupta draft spec`), per-chapter acceptance records
(`chitragupta draft unit`), a cross-reference check
(`chitragupta draft registry check`) and an assembly step that produces
one LaTeX book. Start at [WRITE-A-BOOK.md](WRITE-A-BOOK.md) before drafting chapter
two -- retrofitting the outline afterwards costs more than declaring it
now.

## 🚑 When something goes wrong

| What you see | What it means | What to do |
| --- | --- | --- |
| The chapter cites nothing | normal for this genre | nothing; the gate passes trivially |
| The chapter is citation-heavy and reads like a survey | the wrong genre ran | ask for a textbook chapter explicitly, or revise toward worked examples |
| Worked examples feel abstract | the motivating scenario was never fixed | give one concrete scenario and ask `draft-reviser` to carry it through |
| `gate` says `FAIL` | a citekey is not in the corpus | correct it or drop the claim |
| `[missing-binary]` from `render` | no `pandoc`/`pdflatex` | install them; the `.md` chapter is unaffected |
| Students need to *do* rather than study | you want the other genre | see [WRITE-A-TUTORIAL.md](WRITE-A-TUTORIAL.md) |

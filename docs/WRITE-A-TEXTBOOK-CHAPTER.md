# 📘 Write a textbook chapter, start to finish

Status: **tutorial.** Written 2026-09-15.

**Written for** a lecturer or course author who wants a chapter of
teaching material -- learning objectives, motivation, worked examples,
exercises -- and who has not used this pipeline before. **Assumed:**
nothing. This page repeats what other documents also say, deliberately.
**Not covered here:** why each prose rule exists
([WRITING-STANDARDS.md](WRITING-STANDARDS.md)) and how a whole book is
assembled from chapters ([BOOKS.md](BOOKS.md)).

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

Fill in `scope.md` by hand now: the reader, the prerequisites, what the
chapter covers, what it does not, and the glossary. For teaching
material the glossary is the chapter's vocabulary contract -- a term that
drifts between sections is a student's lost afternoon.

Set the dialect your course uses:

```bash
chitragupta draft dossier set-language \
    content/drafts/course/ch3-state-estimation.md en-GB
```

## 🗺 Step 3: write an outline (optional, recommended)

A textbook chapter has a shape students expect, and declaring it is
cheap:

```bash
chitragupta draft dossier init \
    content/drafts/course/ch3-state-estimation.md \
    --genre textbook-chapter --outline
```

Edit `content/dossiers/course/ch3-state-estimation/outline.md`. Sections
need a `brief:` and/or `claim:`; `queries:` are optional and, in this
genre, often absent -- most sections are your own explanation with
nothing to retrieve:

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

For teaching material, `review verbatim` is the one that matters most: a
chapter that reuses a source's wording is a copyright problem in a way a
private research note is not. It reports wording shared with any parsed
source, cited or not.

`review uncited` is deliberately gentler on this genre -- prose with no
citation is the normal state of a textbook, not a finding.

If the chapter has TikZ figures, `review figure` reports overlapping
nodes, overlong labels and the edge list to confirm against your prose.

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
one LaTeX book. Start at [BOOKS.md](BOOKS.md) before drafting chapter
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

# 🧪 Write a tutorial, start to finish

Status: **tutorial.** Written 2026-09-15.

**Written for** anyone who wants a hands-on lesson -- a lab exercise, a
getting-started walkthrough, a "build X to learn Y" -- that a learner
follows at a keyboard to a working result. **Assumed:** nothing. This
page repeats what other documents also say, deliberately. **Not covered
here:** why each prose rule exists
([WRITING-STANDARDS.md](WRITING-STANDARDS.md)).

Sister tutorials: [a survey](WRITE-A-SURVEY.md),
[a thesis chapter](WRITE-A-THESIS-CHAPTER.md),
[a textbook chapter](WRITE-A-TEXTBOOK-CHAPTER.md),
[a deep-research report](WRITE-A-DEEP-RESEARCH-REPORT.md).

## 🧭 Table of contents

- [Is this the genre you want?](#-is-this-the-genre-you-want)
- [What you will have at the end](#-what-you-will-have-at-the-end)
- [Before you start](#-before-you-start)
- [Step 1: name the destination artifact](#-step-1-name-the-destination-artifact)
- [Step 2: open the dossier](#-step-2-open-the-dossier)
- [Step 3: write an outline (optional)](#-step-3-write-an-outline-optional)
- [Step 4: ask for the lesson](#-step-4-ask-for-the-lesson)
- [Step 5: the run-it step, which is not optional](#-step-5-the-run-it-step-which-is-not-optional)
- [Step 6: gate, render](#-step-6-gate-render)
- [Step 7: read the review aids](#-step-7-read-the-review-aids)
- [Step 8: change something](#-step-8-change-something)
- [When something goes wrong](#-when-something-goes-wrong)

## ⚖ Is this the genre you want?

A tutorial is for someone **doing**, at a keyboard, right now. It is
concrete, single-path, minimally explained, and it ends with something
that visibly works.

- If your reader is studying rather than doing, you want
  [a textbook chapter](WRITE-A-TEXTBOOK-CHAPTER.md).
- If your reader already knows what they want and needs only the steps,
  they want a how-to guide -- say so rather than writing a tutorial
  around it.
- If your reader is mapping a field, they want
  [a survey](WRITE-A-SURVEY.md).

The distinguishing rule of this genre: **citations appear only in the
closing "Where to go next" section**, never mid-lesson. A learner
following steps does not stop to read a paper.

## 🎯 What you will have at the end

For a lesson you decide to call `labs/first-twin`:

| Path | What it is |
| --- | --- |
| `content/drafts/labs/first-twin.md` | the lesson -- the canonical copy |
| `content/dossiers/labs/first-twin/` | scope, the happy path you chose, and every path you rejected |
| `content/rendered/labs/first-twin.pdf` | the typeset lesson |
| `content/rendered/labs/first-twin.tex` | the same, as LaTeX |
| `content/rendered/labs/first-twin.md` | a numbered Markdown copy |

The dossier's `rejected.md` is unusually valuable in this genre. It
records every alternative path you walked away from and why -- "Docker
instead of a local interpreter: hides the thing being taught" -- so a
later revision does not re-argue a decision you already made.

## 🔧 Before you start

```bash
pip install chitragupta-cli
chitragupta init my-labs
cd my-labs

mkdir -p papers
cp /path/to/your-library.bib papers/bibliography.bib

chitragupta corpus sync
```

Or clone the repository and `cp config.toml.example config.toml`.

A tutorial needs the smallest corpus of any genre -- it cites only in its
closing section, if at all. You can write one against an almost empty
ledger.

> Every command here also works as `python -m chitragupta.<layer> ...`.

## 🎯 Step 1: name the destination artifact

One sentence, naming a thing that visibly works:

> "A running digital twin of a water tank that prints the estimated level
> once a second and reacts when you change the inflow."

Not "an understanding of digital twins". If you cannot name it in a
sentence, the lesson is not scoped yet, and everything downstream will
wander.

Then decide the slug:

| You are writing | Use |
| --- | --- |
| a lab for a course | `labs/first-twin` |
| a lesson beside other genres on one topic | `dt/tutorial` |
| a standalone walkthrough | `first-twin` |

And be honest about **how long it takes**. A tutorial should be
completable in one sitting; if your path is three hours, cut it into two
lessons now rather than after a class has failed to finish it.

## 🗂 Step 2: open the dossier

```bash
chitragupta draft dossier init content/drafts/labs/first-twin.md \
    --genre tutorial
```

Fill in `scope.md` by hand now:

- **Reader** -- the learner in one concrete sentence, *including what they
  already know*. "A second-year student who has written Python but never
  used a message queue."
- **Covers** -- the destination artifact and the capability it leaves
  behind.
- **Does not cover** -- the variations, edge cases and alternate
  environments you are deliberately refusing. Write these down; they are
  what stops a later revision quietly widening the lesson.
- **Glossary** -- each recurring term with the one definition the whole
  lesson uses.

Set the dialect:

```bash
chitragupta draft dossier set-language \
    content/drafts/labs/first-twin.md en-GB
```

Command output and file contents keep whatever spelling the tool
actually emits -- they are quoted material, not your prose.

## 🗺 Step 3: write an outline (optional)

Most tutorials do not need one: the steps *are* the outline, and they
come from walking the path. If you want to fix the shape first:

```bash
chitragupta draft dossier init content/drafts/labs/first-twin.md \
    --genre tutorial --outline
```

```markdown
## What you will build

brief: Show the end result first -- the printed output, verbatim. Seeing
the destination is what makes someone willing to start.

## What you need

brief: Exact versions. "Python 3.11+, Docker 24+", never "a recent
Python".

## Step 1 -- Install and check

brief: One action per step, imperative verb first. End with the command
that proves it worked.

## Step 2 -- Model the tank

brief: Smallest model that moves. No configuration file yet.

## Step 3 -- Feed it real readings

## Step 4 -- Watch it correct itself

brief: This is the payoff step. The learner must see the estimate
converge; if they cannot see it, the lesson has not landed.

## Where to go next

brief: The only place citations may appear. Point at the two corpus
papers that explain what we just did by hand.

queries:
- state estimation tutorial introduction
- digital twin synchronisation
```

## 🗣 Step 4: ask for the lesson

> Write a hands-on tutorial into `content/drafts/labs/first-twin.md`. The
> learner builds a running digital twin of a water tank that prints the
> estimated level every second. They know Python, not control theory.
> About 45 minutes.

"Tutorial", "hands-on lesson", "getting-started walkthrough" or "lab
exercise" selects `tutorial-writer`.

What it does: a task analysis (walking the whole path first, writing down
every command and decision -- including the ones an expert does without
noticing, which are exactly the ones a lesson omits and a learner fails
on), the front matter, the steps, the ending, and a "Where to go next"
that is the only place it may cite.

## 🏃 Step 5: the run-it step, which is not optional

The skill runs the lesson end to end before presenting it, in a scratch
directory, and fixes what does not work. **Do it yourself too**, on a
clean machine or a fresh container, because you are the one who knows
what your students actually have installed.

Two failures a run catches and a read-through never does:

- a step that assumes state an earlier step did not create;
- a command that works in your shell because of something in your
  environment that is not in the prerequisites.

If a step cannot be run here -- it needs hardware or an account you do
not have -- say so in the lesson rather than presenting an unverified
path as verified.

## ✅ Step 6: gate, render

```bash
chitragupta draft gate content/drafts/labs/first-twin.md
```

If the lesson cites nothing, the gate passes trivially. If "Where to go
next" cites, build the references section:

```bash
chitragupta draft references content/drafts/labs/first-twin.md
```

Render:

```bash
chitragupta draft render content/drafts/labs/first-twin.md --format pdf
chitragupta draft render content/drafts/labs/first-twin.md --format tex
chitragupta draft render content/drafts/labs/first-twin.md --format md
```

Stamp it:

```bash
chitragupta draft dossier stamp content/drafts/labs/first-twin.md
```

## 🔍 Step 7: read the review aids

```bash
chitragupta draft style content/drafts/labs/first-twin.md
chitragupta review verbatim scan content/drafts/labs/first-twin.md
```

`draft style` is the most useful one here: an acronym never expanded at
first use is a bigger problem for a learner mid-task than for any other
reader.

Note that a long code block in a lesson can be reported as a wide line by
the typesetting checks. The render wraps it with a continuation marker,
so it is a quality note rather than a broken page -- but a line a learner
has to retype is worth shortening anyway.

## 📝 Step 8: change something

Never re-run the genre skill. Ask for a revision:

> Step 3 assumes the queue is already running. Add the start command to
> step 2 and re-check that the lesson runs from a clean container.

That selects `draft-reviser`, which reads the dossier -- including the
rejected paths -- and edits only what is affected.

After a hand edit:

```bash
chitragupta draft gate content/drafts/labs/first-twin.md
chitragupta draft dossier stamp content/drafts/labs/first-twin.md
```

Back it up -- `content/drafts/` is gitignored:

```bash
chitragupta draft dossier export labs/first-twin
```

## 🚑 When something goes wrong

| What you see | What it means | What to do |
| --- | --- | --- |
| The lesson explains more than it instructs | it drifted toward a textbook chapter | ask for it to be cut back to actions; move explanation to "Where to go next" |
| Citations appear mid-lesson | the genre rule was missed | ask `draft-reviser` to move them to the closing section |
| A learner gets stuck at one step every time | a prerequisite is implicit | walk the path on a clean machine, then add what you find to "What you need" |
| The lesson takes twice the stated time | too much in one sitting | split it into two lessons, each with its own working result |
| `gate` says `FAIL` | a citekey in "Where to go next" is not in the corpus | correct it or drop it |
| `[missing-binary]` from `render` | no `pandoc`/`pdflatex` | install them; the `.md` lesson is unaffected |

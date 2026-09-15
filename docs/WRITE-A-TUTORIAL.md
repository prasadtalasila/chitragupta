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

That writes eight files. **Exactly one is yours to fill in now:
`scope.md`.** One other -- `rejected.md` -- is unusually important in
this genre and is described below.

### What goes in `scope.md`

| Field | What goes in it | Why it is asked for |
| --- | --- | --- |
| `- language:` | a BCP-47 tag: `en-GB`, `en-US`, `en-IN` | ships **unset**. Note that command output and file contents keep whatever the tool emits -- they are quoted material, not your prose |
| `## Reader` | the learner in one sentence, *including what they already know* | the prerequisites section follows directly from it |
| `## Covers` | **the destination artifact**, named concretely, plus the capability left behind | if you cannot write this sentence the lesson is not scoped yet |
| `## Does not cover` | the variations, edge cases and alternate environments you refuse | this is what stops a later revision quietly widening a 45-minute lesson |
| `## Glossary` | each recurring term with one definition | a lesson that calls the same thing three names loses a learner mid-step |

Set the dialect with the command:

```bash
chitragupta draft dossier set-language \
    content/drafts/labs/first-twin.md en-GB
```

A filled-in tutorial `scope.md` -- the whole file is at
[`examples/dossiers/tutorial/scope.md`](examples/dossiers/tutorial/scope.md):

```markdown
# Scope

- genre: tutorial
- language: en-GB
- draft: content/drafts/labs/first-twin.md
- created: 2026-09-15
- corpus: 214 citekeys, digest `a31f0c4b77de`
- draft digest: not recorded (run `dossier stamp` once the draft is ready)

## Reader

A second-year student who has written Python before, has never used a
message queue, and is sitting at a lab machine with 45 minutes. They
have read chapter 3, so they know what an estimate and a variance are.

## Covers

The destination artifact: **a running digital twin of a water tank that
prints the estimated level once a second and visibly corrects itself
when you change the inflow by hand.**

## Does not cover

Deployment, containers, or anything that runs on hardware. Deliberate:
every one adds an install before the lesson starts, and the lesson has
45 minutes.

Tuning. The gain is given as a constant with a one-line justification
and a pointer onward.

## Glossary

- **Tank** -- the simulated physical asset. Always "the tank", never
  "the system" or "the plant".
- **Twin** -- the Python process holding the estimate.
- **Reading** -- one noisy level measurement from the simulator.
- **Estimate** -- the twin's current best level, printed each second.
```

### The file this genre gets the most out of: `rejected.md`

In other genres `rejected.md` holds retrieved sources that were turned
down. A tutorial adds a second use, and it is the most valuable entry a
lesson's dossier holds -- a `## Rejected paths` section with its own
two-column table:

```markdown
## Rejected paths

| alternative | why not chosen |
| --- | --- |
| Poetry instead of a venv | one more install before the lesson starts |
| Docker instead of a local interpreter | hides the thing being taught |
| Real hardware instead of the simulator | 45 minutes, and half the lab has no board |
| Deriving the gain in step 3 | that is chapter 3; deriving it here stops the lesson dead |
```

The prose can only show the path you kept. Without this table a revision
re-argues every branch you already decided.

Command output and file contents keep whatever spelling the tool
actually emits -- they are quoted material, not your prose.

## 🗺 Step 3: write an outline (optional)

Most tutorials do not need one: the steps *are* the outline, and they
come from walking the path. If you want to fix the shape first:

```bash
chitragupta draft dossier init content/drafts/labs/first-twin.md \
    --genre tutorial --outline
```

Three fields per section:

| Field | What goes in it | What the skill does with it |
| --- | --- | --- |
| `brief:` | steering in your own words | consumed once, **never appears in the lesson** |
| `claim:` | your own prose | rewritten and grounded. **Rare in this genre** -- a tutorial makes few claims about the literature |
| `queries:` | a `-` list of search terms | run **verbatim**. In a tutorial these belong to the closing section only |

A section needs at least a `brief:` or a `claim:`. A tutorial's outline
is almost all briefs, with one `queries:` block at the end -- the only
place this genre may cite.

A worked example -- the whole file is at
[`examples/dossiers/tutorial/outline.md`](examples/dossiers/tutorial/outline.md):

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

| Aid | Reads for | Why it matters in a lesson |
| --- | --- | --- |
| `draft style` | defect markers, an acronym never expanded at first use, dialect | **the most useful one here.** An unexpanded acronym mid-task stops a learner who cannot look it up without losing their place |
| `review verbatim` | wording shared with any parsed source | a lesson quoting a source's prose reads as borrowed rather than taught |

A long code block can also be reported as a wide line by the typesetting
checks. The render wraps it with a `,→` continuation marker, so it is a
quality note rather than a broken page -- but a line a learner has to
retype is worth shortening anyway.

### The agenda: all of them as one worklist

```bash
chitragupta review agenda content/drafts/labs/first-twin.md
```

It **reads the aids' filed JSON and never runs an aid**, so run them
first with `--write`. Items are `[unattended]` (safe to repair
automatically) or `[surfaced]` (yours to judge).

A tutorial that cites only in its closing section produces the shortest
agenda of any genre:

```markdown
# Agenda: content/drafts/labs/first-twin.md

> **Review aid, not a gate.** This report is evidence for a human
> judgement, never a verdict. No draft is blocked by what it says.

- Draft: `content/drafts/labs/first-twin.md`
- Command: `chitragupta review agenda content/drafts/labs/first-twin.md`

## Sources

- Citation provenance: read
- Verbatim scan: read
- Citation coverage: not run
- Multi-source synthesis: not run
- TikZ layout check: not run
- Uncited prose: read
- Quotation integrity: not run
- Claim support: not run
- Prose (style_check): read
- Dossier drift: read

## Summary

- 2 prose

## Findings

### prose

- `5a8bf91ec244` [unattended] (Step 1 -- Get the simulator running):
  chitragupta.WideCodeLine: 'python -m tanksim --seed 42 --rate 1 --noise'
- `c14d0b7e9a33` [unattended] (Step 3 -- Add the estimate):
  chitragupta.AcronymNotExpanded: 'RMS' used before first expansion
```

**How to read that as the author.** Both are `[unattended]`. The wide
line is one a learner has to type, so shortening it is worth doing even
though the render would wrap it. The unexpanded acronym is the finding
this genre should take most seriously -- a learner three steps into a
lesson cannot pause to look one up.

Several aids read `not run` here, and that is correct rather than a gap:
a lesson with no claims has nothing for claim support to score, and one
with no figures has nothing for the TikZ check to measure. The agenda
names them as absent rather than pretending they passed.

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

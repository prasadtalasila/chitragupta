# 🛠 Tutorial: what the genre owes its learner

Assumes the core, §1–9 of [WRITING-STANDARDS.md](../../WRITING-STANDARDS.md).
This file holds the writing rules that apply to a tutorial alone: a
hands-on lesson, in the Diátaxis sense, that a learner follows at a
keyboard to a working result. It says what the genre is for, where it
may cite, how free it is with figures and how sparing with mathematics,
and what its reread and self-check look for. The element rules are in
[figures.md](../figures.md), [mathematics.md](../mathematics.md) and
[tables.md](../tables.md); this file repeats none of them.

## 🎯 What a tutorial owes its learner

A tutorial is a **lesson**: a learner does something under your guidance
and comes out with skill and confidence they didn't have before. The
governing analogy is a driving lesson. Its point is not getting from A
to B but that the student can drive afterwards; the route is a pretext.
Everything in a tutorial is chosen for what it teaches, not for what it
produces, and the instructor, not the student, is responsible for the
student arriving safely.

That responsibility is the whole discipline of the genre. **A tutorial
that doesn't work is worse than no tutorial**, because a learner who
follows your instructions exactly and gets an error concludes they are
the problem. Every rule below follows from that.

There are two failure directions, both common:

- **Drifting into explanation.** You get anxious that the learner should
  *know* things, and start explaining the architecture mid-step. The
  lesson stalls. Keep inline explanation minimal; link or defer the
  rest to "Where to go next".
- **Drifting into a how-to.** You start offering options ("you could
  also use X"), covering edge cases and handling alternate environments.
  A learner who does not yet know the domain cannot evaluate an option,
  and every choice you offer is a place to get lost. **One path. No
  branches.**

The core's §5, "don't let a document do two jobs", is strictest here.
The structural rules in this file (a single path, no options, minimal
explanation) are tutorial-only: carried into a survey, they would delete
the deliverable.

**Never write "simply", "just", "obviously" or "easy"** (the core's §2).
In a lesson the cost is sharper than anywhere else: when the step is not
simple, the learner concludes the failure is theirs.

## 📚 Citations: only in "Where to go next"

**Citations are rare in this genre and belong only in the closing
"Where to go next" section.** A `[@citekey]` inside a step is a
distraction from the task at hand: the learner is typing, not evaluating
literature. If corpus material shapes the lesson (a real system worth
imitating, a dataset worth using), let it inform your choices silently
and point at it at the end.

A tutorial's unit for multi-source synthesis is the document
([WRITING-STANDARDS.md](../../WRITING-STANDARDS.md) §11): the body
carries no citations, and two or more distinct citekeys in "Where to go
next" are the evidence that the lesson was derived from more than one
source rather than transcribed from one.

## 📐 Figures: the genre most free to use them

The core's original ASCII diagrams fit this genre more naturally than
any other, and a hands-on lesson can legitimately carry a lot of
figures: what the learner is about to build, how data moves through a
command, what the screen should look like at a checkpoint. A heavily
illustrated tutorial is a good tutorial, not an overgrown one. The test
is per figure and never a budget: does *this* step read more clearly as
a diagram than as text? Draw every one that passes, and none that
doesn't. A figure sits beside the step it serves, not in a section of
its own, and [figures.md](../figures.md) §10 applies to it whole,
caption included.

A tutorial rarely needs a table, and a comparison table almost never
belongs in one: weighing alternatives is a different genre's job. A
table of flags, or of the output each step should produce, is the kind
that does.

## 🔢 Mathematics: rare, and the keyboard wins

Mathematics is rare in this genre and easy to get wrong when it
appears. A value the learner *types* stays a plain code span, because
it is literal input, while a value the lesson *reasons about* is a
quantity under [mathematics.md](../mathematics.md) §12, with a row in
the dossier's `math.md`. `` `DRY_THRESHOLD = 35.0` `` in a config file is
code; "the threshold is `k = 4` reading units per hour" is mathematics.
When in doubt, prefer code: a tutorial's job is the keyboard, not the
derivation.

**Numbering one is rarer still.** §12 numbers an equation only if it is
standalone, the last step of a derivation, or reused later, and a
tutorial that keeps to the keyboard has no derivations to conclude. If a
genuine formula is reused across steps, number it and refer to it by its
marker, rather than restating "the formula from step 3" in prose.

## 👓 The beginner reread, and the self-check

Read the lesson once as someone who has never seen the topic, before
presenting it ([WRITING-STANDARDS.md](../../WRITING-STANDARDS.md) §6).
Flag:

- an undefined term;
- a step that assumes a prior action you never instructed;
- any point where the learner must decide something;
- any step with no way to tell whether it worked.

Then every one of these should be answerable "yes":

- Can the learner see, at the top, what they will have at the end?
- Does every step start with a verb they perform?
- Does every step that produces output state what they should see?
- Is there exactly one path, with no options and no "if you prefer"?
- Are all values concrete rather than placeholders?
- Is every warning placed before its step?
- Has the whole thing been run end to end, and does it work?
- Is all substantive explanation in "Where to go next", not in the
  steps?
- Would a beginner who follows it exactly succeed, without judgement
  calls?

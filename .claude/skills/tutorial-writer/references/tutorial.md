# Tutorial: what a hands-on lesson alone needs

Read a section of this file when the step that sent you here cites it;
each section opens with when it applies. Paths here are from the project
root.

## 1. The destination, and what a lesson's dossier records

Read this before opening the dossier.

**The destination is one concrete thing the learner will have working at
the end**: small, real and visibly functioning. "A working X that does Y
when you run it", not "an understanding of X". If you cannot name it in a
sentence, the tutorial is not scoped yet; ask the user rather than
inventing one.

**The dossier holds the lesson's design.** The lesson is only half of
what the run produces. The other half is who the learner is, what they
were assumed to know already, the one happy path you chose, **which
alternative paths you turned down and why**, and the environment the
steps were actually verified against. A tutorial is single-path by
definition, so the branches you refused are precisely the judgment the
finished prose cannot show. Without them on disk, the next revision has
to re-derive the whole lesson design to change one step.

None of this depends on the draft citing anything. A tutorial with zero
citations still gets a dossier, and an empty `evidence.md` is honest:
the lesson design is the part worth keeping either way.

What each `scope.md` field holds for a lesson:

- **Reader**: the learner in one concrete sentence, including what they
  are assumed to know already. The front matter's prerequisites follow
  from this.
- **Covers**: the destination artifact, and the capability the lesson
  leaves the learner with.
- **Does not cover**: the variations, edge cases and alternate
  environments you are deliberately refusing, so a later session can
  tell a scope decision from an oversight.
- **Glossary**: each recurring term with the one definition the whole
  lesson uses.
- **`language:`**: command output and file contents are quoted material,
  and keep whatever spelling the tool actually emits, whatever dialect
  the prose is in.

## 2. Task analysis and the front matter

Read this before the task analysis; it covers the front matter too.

**Walk the whole path before writing any of it**, actually running it,
and write down every command, file and decision it requires. The steps
you perform automatically are exactly the ones your draft will omit and
your learner will fail on.

**Record the outcome while you have it.** The single happy path goes in
the draft; every alternative you walked away from goes in `rejected.md`,
under a `## Rejected paths` section with its own two-column table,
`alternative | why not chosen`, below the citekey table, which stays for
retrieved candidates. For example: "Poetry instead of venv: one more
install before the lesson starts", or "Docker instead of a local
interpreter: hides the thing being taught". This is the most valuable
entry a tutorial's dossier holds, because the prose can only show the
path you kept; a revision without this list re-argues every branch you
already decided.

**The front matter is what the learner needs before starting:**

- **What you'll build**: one or two sentences, ideally with the end
  result shown up front (output, a description of the screen, a sample
  response). Seeing the destination is what makes someone willing to
  start.
- **What you'll learn**: phrased as a capability, not a curriculum.
- **What you need**: exact prerequisites, such as versions, installed
  tools, accounts and prior tutorials. Be specific ("Python 3.11+,
  Docker 24+"), not vague ("a recent Python").
- **How long it takes**: an honest estimate.

## 3. Writing the steps

Read this before writing the lesson's steps; it covers the ending too.
The rules, in priority order:

- **Every step is an action the learner takes.** If a step has no verb
  the learner performs, it is explanation: move it or cut it.
- **Start each step with an imperative verb.** One action per step.
- **Be concrete, never abstract.** Real filenames, real values, real
  commands: never `<your-project-name>` where a literal `demo-app` would
  do. A placeholder makes the learner make a decision, and decisions are
  where they stall.
- **Show the expected result after every step that produces one.** "You
  should see `Listening on port 8080`." This is the learner's only way to
  know they are still on the path, and the single highest-value thing you
  can add to a draft.
- **Guarantee results.** Nothing may depend on the learner's
  environment, prior state or judgement. If something can vary, pin it: a
  version, a seed, a container.
- **No options, no alternatives, no "depending on your setup".** Choose
  for them.
- **Minimal explanation inline.** One clause where it prevents confusion
  ("we use HTTPS here because it's safer"), then move on. The real
  explanation goes in "Where to go next".
- **Repetition is fine.** Don't refactor the lesson for elegance; a
  learner benefits from doing a thing three times.
- **Warnings go before the step they concern, not after.** A caution the
  learner reads after destroying their state is not a caution.
- **End by restating what the learner built** and what they can now do,
  tied back to the front matter's promises. A tutorial that stops at the
  last command leaves the learner unsure whether they succeeded.

## 4. "Where to go next" and its citing

Read this before you write the closing section or search for it.

**This is where everything the steps deferred lives**: link the concepts
you passed over quickly, name the how-to guides for the variations you
refused to cover, and, if the corpus genuinely has something, cite it
here and nowhere else.

**Search with the same discipline as any other genre**: over-fetch, log
every call to the draft, read each 500-character snippet yourself rather
than trusting the score, and reformulate rather than settling for a weak
top hit. The log matters even here, where citing is optional: it is what
a later dossier status check re-asks against the corpus to say which
newly synced papers this lesson has never seen.

**Citing remains optional.** A tutorial with zero citations is the
normal case, not a deficiency, and an empty citekey column in the
section map is the honest result. With an `outline.md`, a `claim:` block
for this section is a steer toward an assertion worth grounding if the
corpus supports it, not an obligation the way it is in the
citation-dense genres.

**The multi-source floor is the whole document, not the paragraph.**
The lesson's body carries no citations by design, so the thing that can
go wrong is one level up: the lesson being a walkthrough of a single
source's procedure from end to end, which is invisible at every scale
below the document. When you do cite, two or more distinct citekeys in
this section are the evidence that the lesson was derived rather than
transcribed. Where the corpus genuinely holds one relevant paper, or
none, that is not a deficiency either: say so with the single-source
marker the step names if you cited exactly one. The synthesis report
says `unit: document` on a tutorial; that is the measurement working,
not a missing paragraph-level check.

## 5. Why the lesson is run, and what the verified environment is for

Read this if asked why the lesson must run before it is presented, or
why the dossier records the environment it ran in.

A learner who follows your instructions exactly and gets an error
concludes they are the problem. An untested tutorial is the exact
artifact this genre exists to avoid, so the whole lesson is executed,
in order, in as clean an environment as you can reach, and run again
from the top after every fix, because a fix to one step routinely
breaks a later one.

**The front matter states what the tutorial supports; the dossier
states what was executed.** The `## Verified environment` section of
`scope.md` records the exact versions the run used ("verified
2026-08-07 on Python 3.11.9, Docker 24.0.7"), not the range the front
matter advertises. That is what a revision months later needs in order
to tell a rotted step from a mistyped one. The steps you could not
verify are named there too: it is the durable half of the disclosure
made in chat when presenting.

## 6. Why a tutorial emits no evidence sidecar

Read this if the user asks why no sidecar was rendered, or asks for one.

The citation-dense genres render one at the render step; a tutorial
does not, and would produce nothing if it did. It cites only in the
closing "Where to go next" section and never mid-lesson, so there is
almost nothing for a sidecar to be about. More to the point, a quotation
has no use in this genre: a learner at a keyboard needs the next
command, not what a paper said about the idea behind it, and pausing a
lesson to attribute a sentence to a source is precisely the digression
a tutorial exists to refuse. So no `quote:` is captured, and a sidecar
built from no quotes is no sidecar.

If you find yourself wanting one, that is a signal you have written a
textbook chapter, whose reader is studying rather than doing.

## 7. Where this genre's rules come from

Read this when asked where the tutorial's writing rules come from.

The principles are not original to this project. Full citations,
licences and a per-principle attribution table are in
`docs/WRITING-STANDARDS.md`, "Sources and attribution". In short: the
genre model is Procida's *Diátaxis*, and the audience and clarity
discipline is Google's *Technical Writing Courses* and Last's
*Technical Writing Essentials*. All three are openly licensed and
require attribution.

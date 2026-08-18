# Genres

Status: **reference.** Written 2026-08-08, describing `.claude/skills/`
as it stands.

**Written for** anyone choosing which skill to ask for, and anyone
wondering why a skill refused something. **Assumed:**
[AGENTS.md](../AGENTS.md), the drafting contract these skills work under.
**Not covered here:** how a skill is written or changed. That is
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md).

Which skill writes what, how to pick between them, and what each one
refuses to do. Eight skills live in `.claude/`: five write a new draft,
and three change an existing one. Of those three, one is cheap and
scoped, one goes back to the whole corpus when you ask it to, and one
repairs what a verbatim scan found.

You do not invoke any of them by name. Each has a `description` in its
frontmatter that names its triggers, and asking for the thing in ordinary
words -- "write a survey section on X", "draft a thesis chapter on Y" --
is what selects it. This document is for the two cases where that isn't
enough: when you want to know which genre you are actually asking for,
and when you want to know why the one that ran refused something.

Related reading:

- [WRITING-STANDARDS.md](WRITING-STANDARDS.md) -- the prose rules the
  eight prose-writing skills share, and where in the
  technical-communication literature they come from.
- [DRAFT-ITERATION.md](DRAFT-ITERATION.md) -- the dossier every skill
  writes, and why `draft-reviser` exists.
- [TOKENS.md](TOKENS.md) -- what a run costs, and why re-running a genre
  skill to make a change is the most expensive mistake available here.
- [ARCHITECTURE.md](ARCHITECTURE.md) -- the drafting layer these sit in,
  and the corpus layer they all read and none of them writes.

## Table of contents

- [Picking one](#picking-one)
- [At a glance](#at-a-glance)
- [The five drafting genres](#the-five-drafting-genres)
- [Assembling a book](#assembling-a-book)
- [Revising: draft-reviser](#revising-draft-reviser)
- [Revising widely: corpus-reviser](#revising-widely-corpus-reviser)
- [Repairing overlap: overlap-reviser](#repairing-overlap-overlap-reviser)
- [What all nine have in common](#what-all-nine-have-in-common)
- [The boundaries, and why they are enforced](#the-boundaries-and-why-they-are-enforced)
- [Genres this project does not have](#genres-this-project-does-not-have)

## Picking one

Two questions settle it almost always.

**Does the draft already exist in `content/drafts/`?** Then the answer is
`draft-reviser`, whatever the genre. Never re-run the skill that wrote
it. The one exception is when you want the whole corpus re-searched and
have said so -- that is `corpus-reviser`, and it is still not the genre
skill.

**Otherwise: what is the reader doing while they read?**

| The reader is... | Genre | Skill |
|---|---|---|
| entering a field and needs the map of it, and the gaps | organising literature | `survey-writer` |
| an examiner, reading adversarially for the claim that outruns its evidence | arguing toward a research question | `thesis-chapter-writer` |
| a student, studying the topic -- reading, not typing | explaining with worked examples | `textbook-chapter-writer` |
| a learner at a keyboard, following you to a working result | a hands-on lesson | `tutorial-writer` |
| someone who needs several perspectives on the topic reconciled, and where the corpus disagrees with itself | multi-perspective research report | `deep-research` |

The pair that gets confused is the teaching pair, and the skills say so
themselves. If the request is "write something teaching X", ask *will the
reader be reading this, or doing it?* Reading is
`textbook-chapter-writer`; doing is `tutorial-writer`.

They have opposite rules about explanation. Digression into *why* is a
feature of one and a defect in the other, so a wrong guess produces a
document that fails at both.

## At a glance

| | Output | Citation density | Subagents | Cost |
|---|---|---|---|---|
| `survey-writer` | `content/drafts/<slug>.md` | every claim | none | one run |
| `thesis-chapter-writer` | `content/drafts/<slug>.tex` fragment | every claim | none | one run |
| `textbook-chapter-writer` | `content/drafts/<slug>.md` | sparse -- background only | none | one run |
| `tutorial-writer` | `content/drafts/<slug>.md` | closing section only | none | one run, plus running the lesson |
| `deep-research` | `content/drafts/deep-research-<slug>.md` | every claim | 6 interviewers, N writers, 4 reviewers | heaviest by design |
| `draft-reviser` | edits an existing draft in place | inherits the draft's | none | cheapest path there is |
| `corpus-reviser` | edits an existing draft in place | inherits the draft's | none | a full retrieval pass -- by request only |
| `overlap-reviser` | edits an existing draft in place | inherits the draft's | none | one scan, then one edit per finding |
| `book-assembler` | `content/drafts/<book>/book.tex` | writes none of its own | none | one composition pass over accepted units |

All five drafting skills also write `content/dossiers/<draft path minus
suffix>/`; `deep-research` and `thesis-chapter-writer` additionally write
a machine-readable `provenance.json` in that same directory. Nothing under
`content/` is tracked by
git -- see [DRAFT-ITERATION.md](DRAFT-ITERATION.md#backup-and-restore)
for how a draft and its dossier get backed up.

## The five drafting genres

### `survey-writer`

Topic-clustered literature survey, background section, related-work
section, "state of the art". Retrieves broadly across two to four
sub-themes, judges every candidate, clusters what survives by theme, and
closes with a comparison table and a gap analysis.

Its job is to **organise a field and locate the gaps in it**, and it has
two named failure directions. Drifting into a textbook chapter -- starting
to teach the concepts, when the reader is a researcher who needs the map
rather than the lesson. And drifting into an argument -- defending one
approach as correct, which is the thesis chapter's job and which here
hides the disagreement the reader came for. Alternatives are the
deliverable, so they are never collapsed for a cleaner narrative.

This is the skill whose retrieval pass dominates its own token cost, and
the one whose economics are worked through in
[TOKENS.md](TOKENS.md#example-1-one-rejected-paper-followed-to-the-end-of-the-run).

### `thesis-chapter-writer`

A chapter tied to a specific research question, written for an examiner:
a domain expert reading adversarially. Unlike a survey, this genre **does
take a position** -- but every step of the argument has to trace to
something cited, and an honestly stated limitation is worth more than the
paragraph that hides it.

The output is a standalone `.tex` fragment using `\citep`/`\citet`, with
no document preamble, meant to be `\input` by your own thesis document.
It also renders `.md` and `.pdf` previews when pandoc and pdflatex are
present.

Its genre boundary: a chapter that only summarises papers in sequence is
a survey with a chapter heading. If the argument toward the research
question isn't visible in the section structure, the chapter isn't doing
its job.

### `textbook-chapter-writer`

An undergraduate chapter: learning objectives, motivation, worked
examples, exercises. Diátaxis-wise this is *explanation with worked
application*.

It is the least citation-dense of the five. Most of its content is
original worked examples; the corpus is cited for motivation and
background, and the citation gate still applies to whatever it does cite.

Its discipline is the **curse of knowledge**: you know this material and
the student does not, and the specific danger is the step that feels too
obvious to state. Terms are defined once at first use and then used
consistently; "obviously", "simply", "just" and "of course" mark a
sentence as a candidate for expansion rather than for the chapter.
Concrete instance first, generalise from it -- which matters more in this
genre than in any other.

### `tutorial-writer`

A Diátaxis tutorial: a lesson a learner follows at a keyboard, start to
finish, to a working result they can see. The governing analogy in the
skill is a driving lesson -- the point is not to get from A to B, the
point is that the student can drive afterwards. The route is a pretext.

Its rule, from which everything else follows: **a tutorial that doesn't
work is worse than no tutorial.** A learner who follows your instructions
exactly and gets an error concludes that they are the problem.

So the lesson is single-path, with no options or branches. Every value is
concrete rather than a placeholder. Every step that produces output says
what the learner should see. And the whole thing is run end to end before
it is presented. Citations appear only in a closing "Where to go next",
never mid-lesson.

Its two failure directions are drifting into explanation (the lesson
stalls while you explain the architecture) and drifting into a how-to
(you start offering alternatives, which a learner who doesn't yet know
the domain cannot evaluate).

### `deep-research`

Seven phases and a dozen subagents: perspective discovery, parallel
grounded interviews, contradiction mapping, outline, parallel cited
section writing, synthesis briefing, and a peer-review panel. It is
adapted from `hadufer/claude-storm`'s implementation of Stanford OVAL's
STORM method, retooled to cite only real citekeys from this project's
corpus instead of live web sources.

Four things no other genre produces:

- a **contradiction map**, showing where sources in your corpus disagree,
  both sides by citekey;
- a blind spot, naming what no perspective's searches turned up at all;
- findings ranked by how well the corpus actually supports them;
- a peer-review scorecard from four independent reviewers, including a
  dedicated adversarial one.

Three depth presets trade cost against breadth:

| Depth | Perspectives | Interview rounds | Section writers |
|---|---|---|---|
| `quick` | 3 + basic | 2 | inline, no subagents |
| `standard` (default) | 5 + basic | 3 | parallel subagents |
| `deep` | 6-7 + basic | 4 | parallel subagents |

It is the heaviest skill here and says so before it starts. If what you
want is a single-pass literature survey, `survey-writer` is faster and
the skill will point you there. Its own cost structure -- and the one
remaining thing that could reduce it -- is
[TOKENS.md](TOKENS.md#example-2-six-interview-packets-from-phase-3-to-phase-7f).

## Revising: `draft-reviser`

Not a genre. The skill that changes a draft one of the five already
wrote, including in a session that has never seen it.

It reads the dossier instead of the corpus. `scope.md` and `steering.md`
bound what the revision may change. `sections.md` maps the change onto
line ranges, so only the affected sections are read and edited. And
`rejected.md` is consulted before any new retrieval, so the same
candidates are not re-judged.

A request that contradicts the recorded scope is a scope change. It gets
said out loud rather than quietly applied.

It also runs the other way round, from the corpus rather than from a
request. When `dossier status --all` reports that a sync removed a paper
a draft cites, `draft-reviser` re-grounds it. It reads the drift report
as JSON and repairs the broken citations in the sections that carry them.
It weighs only the new candidates bearing on the sub-theme in play, and
leaves previously declined papers declined unless their recorded reason
has stopped holding. Once the gate passes, it re-stamps the corpus
fingerprint. What that promises is no *missing* citations, not an empty
candidate list -- see
[DRAFT-ITERATION.md](DRAFT-ITERATION.md#re-grounding-after-the-corpus-moves).

Drafts written before `src/dossier.py` existed have no dossier, and
neither do hand-written ones. It bootstraps rather than refusing:
`dossier init`, then fill in what the draft itself can tell you.

It says in chat that `evidence.md` and `rejected.md` are empty, so the
first revision may have to re-retrieve for a sub-theme a real dossier
would have answered from disk. It gets cheaper from the second revision
on.

It does not invent evidence entries to fill the file. An empty
`evidence.md` is honest; a fabricated one is the same failure class as a
fabricated citekey.

**Every one of the five drafting skills routes here for changes.** Each
carries the rule twice. Once as a row in its own routing table: *user
asks to change something that already exists -> use `draft-reviser`,
never re-run this skill*. Once as a clause in its frontmatter
`description`, which is the surface that decides which skill is picked in
the first place. The table alone is not enough: it is read only after a skill has
already been chosen. [TOKENS.md](TOKENS.md) is why the rule exists.

**It is a default, not a gate.** Nothing enforces it; no hook checks it,
and the only mechanical gate in the pipeline is `citation_gate`. That is
deliberate -- [SOUL.md](../SOUL.md) puts "let a machine outrank a human
on a judgment call" under *what you will not do*, and how wide a revision
should look is exactly such a call. So the way out is a door rather than
an exception: `corpus-reviser`, below.

## Revising widely: `corpus-reviser`

Also not a genre. The same act as `draft-reviser` -- changing a draft
that already exists -- with one thing different: it re-searches every
sub-theme in `sections.md` and reads the whole draft, instead of the one
sub-theme a change touches.

**It is a separate skill so that the choice is yours, and structural.**
`draft-reviser` contains no instructions for a wide search, so following
it cannot drift into one. Asking for `corpus-reviser` is how you say the
cost is worth it.

A rule that lived as a paragraph inside one skill would depend on the
model noticing it, which is exactly the kind of enforcement this project
does not trust.

Invoke it when you ask for a whole-corpus pass in as many words, when a
scope change you agreed to has invalidated the recorded queries, or when
the draft is being re-targeted at a different reader. Anything else --
including repairing citations after a sync moved the corpus -- is
`draft-reviser`. When it is genuinely unclear, the skills are told to
pick `draft-reviser` and say so: being wrongly narrow costs a clarifying
sentence, being wrongly wide costs the tokens.

What it does *not* relax is the point of doing it here rather than by
re-running the genre skill. It still consults and honours `rejected.md`.
It still logs every call to `retrieval.md`. It still edits section by
section rather than rewriting the file, because a wide *search* does not
imply a wide *rewrite*. It still writes the dossier back, and still exits
through the gate.

So it keeps the rejections and their reasons, the reader, the glossary
and the steering, and spends tokens only on what is genuinely unknown.

The thing that stays never, in both skills, is re-running the genre
skill: that discards all of that state and pays to rediscover a worse
version of it.

## Repairing overlap: `overlap-reviser`

Not a genre either, and narrower than both revisers above: its input is
one report rather than a request in prose. `python -m src.review verbatim
scan --json` lists every run of wording a draft shares with the corpus.
This skill works that list, repairing each finding and re-checking the
repair before keeping it.

**A genuine restatement is only detected where the embedding tier can
run**, so finishing the list is not a clean bill of health. See
[PLAGIARISM.md](PLAGIARISM.md).

**What it may do without asking is decided by the report, not by the
model.** #128's severity buckets are the line. A `short` run is reworded
unattended. A `long` one stops and asks the human whether to paraphrase
or to quote. A run that is both quoted and cited is reported as already
correct and left alone.

The paraphrase-or-quote choice on a long run is an authorial one, since
the field states some things one particular way.
[SOUL.md](../SOUL.md) puts deciding it for you under *what you will not
do*.

**Every repair is verified before it is kept.** `python -m src.draft
gate` and `python -m src.review verbatim recheck` both have to come back
clean, the finding has to be gone, and the count of objective findings
must not have risen. That last condition catches a rewrite that fixes its
own finding by lifting from a different source.

Two attempts per finding, one pass per invocation. Every attempt is
logged in `revisions.md` with its outcome, refusals included.

**Only a person starts it.** No hook, no scheduled job, no genre skill at
the end of its run, and not `draft-reviser` on its own initiative. The
loop proposes and repairs; you accept the diff.

Everything else about the draft is `draft-reviser`. A finding this skill
cannot repair is escalated, not worked around.

## Assembling a book

`book-assembler` is the ninth skill and the only one that writes no
prose. It composes units that are already accepted and gate-passed into
one LaTeX book -- front matter, `\part`, `\chapter`, one `\input` per
unit, back matter -- from the outline `python -m src.draft spec` holds
and the acceptance records `python -m src.draft unit` wrote.

It is the last step of the book-scale track and stops at that track's
second human gate: it presents what it composed, with every registry
finding, and does not say the book is finished. A unit that is missing,
unaccepted or stale sends it back to the genre skill or to
`draft-reviser`; it never drafts and never edits.

[BOOKS.md](BOOKS.md) is the track -- the outline, the generation unit,
the registries, and why the consistency check reports rather than
blocks.

## What all nine have in common

These are not per-skill choices. They are the same rules restated in
nine `SKILL.md` files, and a skill that broke one would be the bug.

One of the nine is not a drafting skill: `book-assembler` composes units
other skills already wrote, so where a rule below is about *writing* --
the dossier, the acronym vocabulary -- it says how that skill differs and
why, rather than being quietly exempt.

**One invariant.** A citekey may only be used if it appears in your `.bib`
export *and* was picked up into the ledger by a real parse of a real PDF.
No skill fabricates one, ever, and none may "fix" a gate failure by
inventing a plausible-looking key -- it corrects the key or removes the
claim.

**The gate is the only exit.** `python -m src.draft gate` runs on the
skill's own output, and no draft is presented until it reports `OK`.

**The corpus is read-only.** No skill runs `python -m src.corpus sync` or any
`python -m src.enrich` stage. Both take the pipeline's write lock and can
run for tens of minutes; they are yours to run. If the ledger is empty or
nothing is `parsed`, the skill says exactly what it checked and what it
found and stops, rather than drafting around it.

**Every run writes a dossier**, created before the first retrieval call
and filled in as the run goes -- not at the end, when what was rejected
has already fallen out of context. The exception is `book-assembler`,
which retrieves nothing and rejects nothing: a book's record is already
on disk as its signed outline, one acceptance record per unit, and the
three registries, all under `content/specs/<book>/`.

**Shared prose standards.** Name the reader before drafting, settle the
dialect with them and record it as `scope.md`'s `language:` line, read
the acronym vocabulary (`assets/style/acronyms.toml`, plus the user's own
`content/acronyms.toml` if `[style].acronyms` points at it) for a term's
canonical expansion rather than inventing one, define terms once, state
scope up front, active voice with a named actor, no
"obviously/simply/just", reread as the reader before presenting.
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) holds them and the
attribution -- Diátaxis, Last's *Technical Writing Essentials*, Google's
Technical Writing courses, all CC-licensed and all requiring credit. Its
§9 is the one to read before building anything that checks a draft: it
says which of these rules have a decidable answer and which are a
judgement, and the two must not be treated alike.

**Rendering never blocks.** `.tex`/`.pdf` rendering that fails for a
missing binary prints a one-line warning and the `.md` draft is presented
anyway.

**The verbatim scan is offered, never run silently and never a gate.**
Once the gate has passed and the renders are done, and before presenting,
each skill offers `python -m src.review verbatim scan
content/drafts/<path>`. That reports wording the draft shares with *any*
parsed source, cited or not. It cannot block a draft, and no skill treats
it as a condition of presenting. The offer carries its own
caveat, in every skill, because the drafter is the one it is about. Two
of the three detection tiers see wording only, so a genuine restatement
is invisible to them. The third sees one, but runs only where the
optional enrichment layer, the Docling sidecars and the draft's dossier
are all present. So a clean scan is not a clean bill of health.
[PLAGIARISM.md](PLAGIARISM.md) is what a drafter reads on that;
[PLAGIARISM-DESIGN.md](PLAGIARISM-DESIGN.md) has why each tier sees what
it sees.

**The prose check is run, reported, and never acted on.** Before
presenting, each skill runs `python -m src.draft style
content/drafts/<path>` and reports what it says -- the findings, and the
header lines naming which dialect was checked and on whose authority. It
measures only what [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §9 marks
decidable: §2's defect markers, an acronym never expanded at first use,
and §8's dialect against `scope.md`'s `language:` line. So it is silent
on whether a paragraph leads with its point, it cannot tell a quotation
from the draft's own voice, and `dialect: not checked` means nobody ever
recorded one rather than that nothing was wrong. **No skill fixes what it
finds.** A finding is a place to look -- the first pass of this check
over this repository's own docs kept 59 of its 73 marker hits after
inspecting each -- and the sanctioned fix path is `draft-reviser`'s
copy-edit mode, which reads the recorded dialect and logs one
`revisions.md` entry naming the convention. Like the scan it exits 0
whatever it finds; [ARCHITECTURE.md](ARCHITECTURE.md)'s "Layer 4" is why
it may never become a gate.

**Why one is offered and the other is run.** The scan can be read as an
accusation, and `--write` files a report, so the skill offers it and the
person decides. The prose check measures a draft against a preference
that same person recorded, writes nothing, and proposes rather than sets
a dialect -- so running it needs no permission, and only the reporting is
a judgement. A `PostToolUse` hook reports the same command per write, to
the agent, mid-loop; this step reports the finished draft once, to the
human. [HOOKS.md](HOOKS.md) has that split: invocation is enforced,
conformance is not.

## The boundaries, and why they are enforced

Every skill carries a "When to invoke" table whose rows are mostly
*other* skills. That looks like duplication and is not: the genre
boundary is the thing most likely to be crossed, because crossing it
feels helpful at the time.

The cost of crossing is that the rules are not merely different but
**opposite**. A tutorial's "one path, no branches" would delete a
survey's deliverable, because alternatives are what a survey is for. A
survey's "weigh both sides without picking a winner" would gut a thesis
chapter, whose job is to take a position. A textbook chapter's
digressions into *why* are the exact defect that stalls a tutorial. So a
skill that drifts into the neighbouring genre does not produce a slightly
off document -- it produces one that fails at both jobs, and the failure
is invisible until a reader tries to use it.

This is [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §5 -- don't let a
document do two jobs -- enforced at the point where it is easiest to
break.

## Genres this project does not have

Named here so a skill can tell you plainly rather than writing the wrong
thing:

| Genre | Reader's state | What happens |
|---|---|---|
| **How-to guide** | already competent, has a specific goal | No skill. Say so, and write it as a short procedure |
| **Reference** | needs a fact, fast | No skill |

Both are Diátaxis quadrants this repository has deliberately not built.
`tutorial-writer` names them explicitly so that a request for one is
answered with a short procedure rather than with a tutorial the asker
does not need.

# 🎭 Genres

Status: **reference.**

**Written for** anyone choosing which skill to ask for, and anyone
wondering why a skill refused something. **Assumed:**
[AGENTS.md](../AGENTS.md), the drafting contract these skills work under.
**Not covered here:** how a skill is written or changed. That is
`DEVELOPER-AGENTS.md` (git checkout only).

Eleven skills live in `.claude/`: six write a new draft,
three change an existing one, one assembles a book from units the
others wrote, and one draws the figures the others hand it. Of the
three revisers, one is cheap and scoped, one goes back to the whole
corpus when you ask it to, and one works the review agenda's
unattended findings.

You do not invoke any of them by name. Each has a `description` in its
frontmatter that names its triggers, and asking for the thing in ordinary
words ("write a survey section on X", "draft a thesis chapter on Y")
is what selects it. This page covers the two cases where that is not
enough: choosing which genre to ask for, and finding out why the skill
that ran refused something.

If you have picked your genre and want to be walked through it, each
one has a start-to-finish tutorial with every command from `dossier init`
to a gated, rendered draft, and an example outline:
[survey](WRITE-A-SURVEY.md),
[thesis chapter](WRITE-A-THESIS-CHAPTER.md),
[textbook chapter](WRITE-A-TEXTBOOK-CHAPTER.md),
[tutorial](WRITE-A-TUTORIAL.md),
[deep-research report](WRITE-A-DEEP-RESEARCH-REPORT.md). The verbatim
digest has its own page, [VERBATIM-DIGEST.md](VERBATIM-DIGEST.md), and
the book track, which assembles chapters into one book, is walked
through in [WRITE-A-BOOK.md](WRITE-A-BOOK.md).

Related reading:

- [WRITING-STANDARDS.md](WRITING-STANDARDS.md) has the prose rules the
  nine prose-writing skills (six genres, three revisers) share, and where in the
  technical-communication literature they come from.
- [DRAFT-ITERATION.md](DRAFT-ITERATION.md) covers the dossier every skill
  writes, and why `draft-reviser` exists.
- [TOKENS.md](TOKENS.md) covers what a run costs, and why re-running a genre
  skill to make a change is the most expensive mistake available here.
- [ARCHITECTURE.md](ARCHITECTURE.md) covers the drafting layer these sit in,
  and the corpus layer they all read and none of them writes.

## 🧭 Table of contents

- [Picking one](#-picking-one)
- [At a glance](#-at-a-glance)
- [The six drafting genres](#-the-six-drafting-genres)
- [Assembling a book](#-assembling-a-book)
- [Drawing a figure: figure-drawer](#-drawing-a-figure-figure-drawer)
- [Revising: draft-reviser](#-revising-draft-reviser)
- [Revising widely: corpus-reviser](#-revising-widely-corpus-reviser)
- [Working the agenda: agenda-reviser](#-working-the-agenda-agenda-reviser)
- [What all eleven have in common](#-what-all-eleven-have-in-common)
- [The boundaries, and why they are enforced](#-the-boundaries-and-why-they-are-enforced)
- [Genres this project does not have](#-genres-this-project-does-not-have)

## ⚖ Picking one

Two questions settle it almost always.

**Does the draft already exist in `content/drafts/`?** Then the answer is
`draft-reviser`, whatever the genre. Never re-run the skill that wrote
it. The one exception is when you want the whole corpus re-searched and
have said so. That is `corpus-reviser`, and it is still not the genre
skill. If what you want is the review agenda's findings repaired ("work
the review agenda"), that is `agenda-reviser`.

**Otherwise: what is the reader doing while they read?**

| The reader is... | Genre | Skill |
| --- | --- | --- |
| entering a field and needs the map of it, and the gaps | organising literature | `survey-writer` |
| an examiner, reading adversarially for the claim that outruns its evidence | arguing toward a research question | `thesis-chapter-writer` |
| a student, studying the topic (reading, not typing) | explaining with worked examples | `textbook-chapter-writer` |
| a learner at a keyboard, following you to a working result | a hands-on lesson | `tutorial-writer` |
| someone who needs several perspectives on the topic reconciled, and where the corpus disagrees with itself | multi-perspective research report | `deep-research` |
| someone studying privately, who wants the papers' own words with a citation on every run | verbatim digest | `review-digest` |

The pair that gets confused is the teaching pair, and the skills say so
themselves. If the request is "write something teaching X", ask *will the
reader be reading this, or doing it?* Reading is
`textbook-chapter-writer`; doing is `tutorial-writer`.

They have opposite rules about explanation. Digression into *why* is a
feature of one and a defect in the other, so a wrong guess produces a
document that fails at both.

## 🔭 At a glance

| | Output | Citation density | Subagents | Cost |
| --- | --- | --- | --- | --- |
| `survey-writer` | `content/drafts/<slug>.md` | every claim | one per sub-theme on a broad topic, otherwise none | one run |
| `thesis-chapter-writer` | `content/drafts/<slug>.tex` fragment | every claim | none | one run |
| `textbook-chapter-writer` | `content/drafts/<slug>.md` | sparse: background only | none | one run |
| `tutorial-writer` | `content/drafts/<slug>.md` | closing section only | none | one run, plus running the lesson |
| `deep-research` | `content/drafts/deep-research-<slug>.md` | every claim | 6 interviewers, N writers, 4 reviewers | heaviest by design |
| `review-digest` | `content/drafts/<topic>/<name>.md`, mostly the sources' own words | every copied run | none | one run, plus `review digest` |
| `draft-reviser` | edits an existing draft in place | inherits the draft's | none | cheapest path there is |
| `corpus-reviser` | edits an existing draft in place | inherits the draft's | none | a full retrieval pass, by request only |
| `agenda-reviser` | edits an existing draft in place | inherits the draft's | none | one agenda run, then one edit per unattended item |
| `book-assembler` | `content/rendered/<book>/book.tex` | writes none of its own | none | one composition pass over accepted units |
| `figure-drawer` | one `figures/<name>.tex` + `.txt` pair beside a draft | none: no citekey in a figure file | none | one figure, compiled and reviewed |

All six drafting skills also write `content/dossiers/<draft path minus
suffix>/`; `deep-research` and `thesis-chapter-writer` additionally write
a machine-readable `provenance.json` in that same directory. Nothing under
`content/` is tracked by
git; see [DRAFT-ITERATION.md](DRAFT-ITERATION.md#-backup-and-restore)
for how a draft and its dossier get backed up.

## ✍ The six drafting genres

Four of the six have a committed, gate-passed sample under a thousand
words each, drafted by the real pipeline over the five-paper sample
corpus, each with its dossier beside it under `content/dossiers/`:
[`survey.md`](examples/sample-project/content/drafts/dt-overview/survey.md)
(survey),
[`staleness-tutorial.md`](examples/sample-project/content/drafts/dt-overview/staleness-tutorial.md)
(tutorial; every step executed for real before being presented, as
the genre requires),
[`staleness-chapter.md`](examples/sample-project/content/drafts/dt-overview/staleness-chapter.md)
(textbook chapter) and
[`trust-chapter.tex`](examples/sample-project/content/drafts/dt-overview/trust-chapter.tex)
(thesis chapter fragment). Read them as samples of *shape*: the
sources are synthetic, but each draft has the shape its genre below
promises.

### 📚 `survey-writer`

Topic-clustered literature survey, background section, related-work
section, "state of the art". Retrieves broadly across two to four
sub-themes, judges every candidate, clusters what survives by theme, and
closes with a comparison table and a gap analysis.

Its job is to organise a field and locate the gaps in it, and it has
two named failure directions. One is drifting into a textbook chapter:
starting to teach the concepts, when the reader is a researcher who needs
the map rather than the lesson. The other is drifting into an argument:
defending one approach as correct, which is the thesis chapter's job and
which here hides the disagreement the reader came for. Alternatives are the
deliverable, so they are never collapsed for a cleaner narrative.

Its retrieval pass dominates its token cost, and
[TOKENS.md](TOKENS.md#-example-1-one-rejected-paper-followed-to-the-end-of-the-run)
works through the numbers.

### 🎓 `thesis-chapter-writer`

A chapter tied to a specific research question, written for an examiner:
a domain expert reading adversarially. Unlike a survey, this genre does
take a position, but every step of the argument has to trace to
something cited, and an honestly stated limitation is worth more than the
paragraph that hides it.

The output is a standalone `.tex` fragment using `\citep`/`\citet`, with
no document preamble, meant to be `\input` by your own thesis document.
It also renders `.md` and `.pdf` previews when pandoc and LuaLaTeX are
present.

Its genre boundary: a chapter that only summarises papers in sequence is
a survey with a chapter heading. If the argument toward the research
question isn't visible in the section structure, the chapter isn't doing
its job.

### 📘 `textbook-chapter-writer`

An undergraduate chapter: learning objectives, motivation, worked
examples, exercises. Diátaxis-wise this is *explanation with worked
application*.

It is the least citation-dense of the six. Most of its content is
original worked examples; the corpus is cited for motivation and
background, and the citation gate still applies to whatever it does cite.

Its discipline is the **curse of knowledge**: you know this material and
the student does not, and the specific danger is the step that feels too
obvious to state. Terms are defined once at first use and then used
consistently; "obviously", "simply", "just" and "of course" mark a
sentence as a candidate for expansion rather than for the chapter.
Concrete instance first, then generalise from it; that order matters
more in this genre than in any other.

### 🛠 `tutorial-writer`

A Diátaxis tutorial: a lesson a learner follows at a keyboard, start to
finish, to a working result they can see. The governing analogy in the
skill is a driving lesson: what matters is that the student can drive
afterwards, and getting from A to B is incidental.

Its rule, from which everything else follows: **a tutorial that doesn't
work is worse than no tutorial.** A learner who follows your instructions
exactly and gets an error concludes that they are the problem.

So the lesson follows one path with no options or branches, uses a
concrete value wherever a placeholder might go, and says what the
learner should see after every step that produces output. The whole
lesson is run end to end before it is presented. Citations appear only
in a closing "Where to go next" section.

Its two failure directions are drifting into explanation (the lesson
stalls while you explain the architecture) and drifting into a how-to
(you start offering alternatives, which a learner who doesn't yet know
the domain cannot evaluate).

### 🔬 `deep-research`

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
- findings ranked by how well the corpus supports them;
- a peer-review scorecard from four independent reviewers, including a
  dedicated adversarial one.

Three depth presets trade cost against breadth:

| Depth | Perspectives | Interview rounds | Section writers |
| --- | --- | --- | --- |
| `quick` | 3 + basic | 2 | inline, no subagents |
| `standard` (default) | 5 + basic | 3 | parallel subagents |
| `deep` | 6-7 + basic | 4 | parallel subagents |

It is the heaviest skill here and says so before it starts. If what you
want is a single-pass literature survey, `survey-writer` is faster and
the skill will point you there. Its own cost structure, and the one
remaining thing that could reduce it, is
[TOKENS.md](TOKENS.md#-example-2-six-interview-packets-from-phase-3-to-phase-7f).

### 📋 `review-digest`

The sixth genre reverses the first rule of the other five. A
verbatim digest is private study text: most of it is copied exactly from
parsed PDFs in the corpus, each copied run ends with a citation, there
are no quotation marks, and a few short sentences of the drafter's own
connect the runs. Its reader is the user, studying. It is never a
deliverable and never a source for any other draft.

It runs `survey-writer`'s draft-and-render workflow step for step and
inverts, in place, every step that exists to keep source wording out of
a draft: every passage to be copied is recorded as a `quote:` in the
dossier, one source per run replaces multi-source synthesis, and the
pre-gate critique, the verbatim scan and the evidence sidecar are
replaced by `python -m chitragupta.review digest`, which leads with the
unsupported fraction and lists every sentence that is not verified
source text. It does run the prose check, reporting and fixing nothing.
It is also the one genre that may place a source's figure in the draft,
beside the copied run it belongs to, where the Docling stage extracted
one. [VERBATIM-DIGEST.md](VERBATIM-DIGEST.md) has the whole of it,
including the one prohibition: never run `agenda-reviser` on a digest.

## ✏ Revising: `draft-reviser`

`draft-reviser` is not a genre. It changes a draft one of the six
already wrote, including in a session that has never seen it.

It reads the dossier instead of the corpus. `scope.md` and `steering.md`
bound what the revision may change. `sections.md` maps the change onto
line ranges, so only the affected sections are read and edited. And
`rejected.md` is consulted before any new retrieval, so the same
candidates are not re-judged.

A request that contradicts the recorded scope is a scope change. The
skill says so instead of applying it without comment.

It also runs the other way round, from the corpus instead of from a
request. When `dossier status --all` reports that a sync removed a paper
a draft cites, `draft-reviser` re-grounds it. It reads the drift report
as JSON and repairs the broken citations in the sections that carry them.
It weighs only the new candidates bearing on the sub-theme in play, and
leaves previously declined papers declined unless their recorded reason
has stopped holding. Once the gate passes, it re-stamps the corpus
fingerprint. What that promises is no *missing* citations, not an empty
candidate list; see
[DRAFT-ITERATION.md](DRAFT-ITERATION.md#-re-grounding-after-the-corpus-moves).

A draft with no dossier, such as one written by hand, is still
revisable: the skill runs `dossier init` and fills in what the draft
itself can tell it. It says in chat that `evidence.md` and
`rejected.md` are empty, so the first revision may have to re-retrieve
for a sub-theme a full dossier would have answered from disk. Later
revisions cost less.

It does not invent evidence entries to fill the file. An empty
`evidence.md` is honest; a fabricated one is the same failure class as a
fabricated citekey.

**Every one of the six drafting skills routes here for changes.** Each
carries the rule twice. Once as a row in its own routing table: *user
asks to change something that already exists -> use `draft-reviser`,
never re-run this skill*. Once as a clause in its frontmatter
`description`, which is the surface that decides which skill is picked in
the first place. The table alone is not enough: it is read only after a
skill has already been chosen. [TOKENS.md](TOKENS.md) explains why the
rule exists.

The rule is a default: nothing enforces it, no hook checks it, and the
only mechanical gate in the pipeline is `citation_gate`. That is
deliberate. [SOUL.md](../SOUL.md) puts "let a machine outrank a human
on a judgment call" under *what you will not do*, and how wide a revision
should look is such a call. So the wider option is a separate
skill instead of an exception: `corpus-reviser`, below.

## 🔁 Revising widely: `corpus-reviser`

`corpus-reviser` is not a genre either. Like `draft-reviser` it changes
a draft that already exists, with one difference: it re-searches every
sub-theme in `sections.md` and reads the whole draft, instead of the one
sub-theme a change touches.

It is a separate skill so that the choice is yours and is made by
structure. `draft-reviser` contains no instructions for a wide search,
so following it cannot drift into one. Asking for `corpus-reviser` is
how you say the cost is worth it. A rule kept as a paragraph inside one
skill would depend on the model noticing it, and this project does not
rely on that kind of enforcement.

Invoke it when you ask for a whole-corpus pass in as many words, when a
scope change you agreed to has invalidated the recorded queries, or when
the draft is being re-targeted at a different reader. Anything else,
including repairing citations after a sync moved the corpus, is
`draft-reviser`. When it is unclear, the skills are told to
pick `draft-reviser` and say so: being wrongly narrow costs a clarifying
sentence, being wrongly wide costs the tokens.

It keeps what makes it cheaper than re-running the genre skill. It
consults and honours `rejected.md`, logs every call to `retrieval.md`,
and edits section by section instead of rewriting the file, because a
wide *search* does not imply a wide *rewrite*. It writes the dossier
back and exits through the gate. So it keeps the rejections and their
reasons, the reader, the glossary and the steering, and spends tokens
only on what is still unknown.

Neither skill ever re-runs the genre skill: that discards all of that
state and pays to rediscover a worse version of it.

## 🩹 Working the agenda: `agenda-reviser`

`agenda-reviser` is narrower than both revisers above: its input is
one worklist instead of a request in prose. `python -m chitragupta.review
agenda <draft>` merges every review aid's report into one ranked,
deduplicated list, and each item's own `unattended` field (read, never
re-derived) says whether this skill may act on it without asking. Three
classes can qualify: `verbatim-run` at severity `short` (found by a
wording tier, not the embedding tier), `prose` (a style finding whose
rule marks it editable), and `missing-citekey`. Everything else is
surfaced for a person.

**A genuine restatement is only detected where the embedding tier can
run**, so finishing the list is not a clean bill of health. See
[PLAGIARISM.md](PLAGIARISM.md).

The report decides what it may do without asking, and the scan's
severity buckets draw the line. A `short` run is reworded unattended. A
`long` one stops and asks the human whether to paraphrase or to quote.
A run that is both quoted and cited is reported as already
correct and left alone.

The paraphrase-or-quote choice on a long run is an authorial one, since
the field states some things one particular way.
[SOUL.md](../SOUL.md) puts deciding it for you under *what you will not
do*.

Every repair is verified before it is kept. `python -m chitragupta.draft
gate` and the `python -m chitragupta.review agenda --baseline` recheck both
have to come back clean, the finding has to be gone, the count of objective
findings must not have risen, and no *new* objective finding may have
appeared. The last two conditions catch different things: a rewrite
that fixes its own finding by lifting from a different source leaves the
count exactly where it was, and is caught only by being listed as new.

Two attempts per finding, one pass per invocation. Every attempt is
logged in `revisions.md` with its outcome, refusals included.

Only a person starts it: no hook, no scheduled job, no genre skill at
the end of its run, and not `draft-reviser` on its own initiative. The
loop proposes and repairs; you accept the diff.

Everything else about the draft is `draft-reviser`. A finding this skill
cannot repair is escalated, not worked around.

## 📕 Assembling a book

`book-assembler` writes no prose. It composes units that are already
accepted and gate-passed into one LaTeX book (front matter, `\part`,
`\chapter`, one `\input` per unit, back matter) from the outline
`python -m chitragupta.draft spec` holds and the acceptance records
`python -m chitragupta.draft unit` wrote.

It is the last step of the book-scale track and stops at that track's
second human gate: it presents what it composed, with every registry
finding, and does not say the book is finished. A unit that is missing,
unaccepted or stale sends it back to the genre skill or to
`draft-reviser`; it never drafts and never edits.

[WRITE-A-BOOK.md](WRITE-A-BOOK.md) describes the track: the outline, the
generation unit, the registries, and why the consistency check reports
instead of blocking.

## 🖍 Drawing a figure: `figure-drawer`

`figure-drawer` owns *how* a figure is drawn:
the layout metaphor, the scaffold from `assets/tikz/`, panel letters,
the ASCII twin, the compile probe and the geometry review. It never
decides *whether* a draft gets a figure, and it never presents a draft.

Four genre skills hand off to it once they have decided a figure is
warranted: `survey-writer`, `tutorial-writer`,
`textbook-chapter-writer` and `thesis-chapter-writer`. `draft-reviser`
hands off to it to redraw or fix one. When the drawing is done, control
returns to the skill that called it, which places the figure in its own
shape, gates and renders. `deep-research` uses no figures.

It also triggers on its own: "draw a figure for section 3 of
rag/survey.md showing how a query moves through retrieval". That
changes an existing draft, so it is a revision: after drawing, the
session continues in `draft-reviser`'s write-back and gate steps, which
log the change, run the gate and re-stamp the draft.

**Why each genre skill still keeps a short figure step.** Skills here
are picked by their trigger descriptions, so a step that says "now use
`figure-drawer`" relies on the model actually loading it, in three
harnesses. Each genre's figure step therefore keeps what must hold even
if that handoff is skipped: its when-to-draw threshold, its output shape
(a marker line in Markdown, `\input` plus a `%figure:` comment in the
thesis fragment), and **no citekey inside either figure file**, because
the gate reads the draft and does not follow `\input`.
`tests/test_skill_figure_step.py` pins that stub in each genre and
fails if a rule that belongs to `figure-drawer` reappears in one.

[FIGURE-DRAWER.md](FIGURE-DRAWER.md) is the skill's own page: example
requests, what it writes, a worked figure, and what to do when one goes
wrong.

## 🔑 What all eleven have in common

These rules are the same in every skill. Each is stated in each
of the eleven `SKILL.md` files or, where several skills share the wording
(the critique loop, the prose check, the verbatim scan, collection
scoping), once in a reference under `.claude/skills-common/references/`
that each skill's step names. A skill that breaks one has a bug.

Each `SKILL.md` exists once per harness (`.claude/skills/`,
`.agents/skills/` and `.opencode/skills/*-opencode/`), differing only in
the tool phrases `tests/fixtures/skill_harness_phrases.toml` lists.
**Change every copy**, and add a phrase-map entry for any wording meant
to differ; `tests/test_skill_harness_copies.py` fails on anything else
and names the copy that moved ([HARNESS.md](HARNESS.md)). A reference
exists once, under `.claude/`, and names no skill and no harness tool.

Two of the eleven are not drafting skills. `book-assembler` composes units
other skills already wrote, so where a rule below is about *writing*
(the dossier, the acronym vocabulary), it says how that skill differs and
why. `figure-drawer` presents no
draft at all: it draws one figure and returns to the skill that called
it, so the gate, the prose check, the verbatim scan and the fingerprint
stamp below are that skill's, not its own. The one rule it carries
itself is the invariant: no citekey in a figure file.

One rule below is narrower still: the pre-gate self-feedback step
(designed in `plans/b5-pregate-self-feedback.md`) is shared by the five
genre skills that write fresh prose from an
evidence packet (`survey-writer`, `thesis-chapter-writer`,
`textbook-chapter-writer`, `tutorial-writer`, `deep-research`), and not
by `book-assembler` (writes no prose of its own) or the three revisers
(`draft-reviser`, `corpus-reviser`, `agenda-reviser`), which already
gate-and-recheck per section rather than critiquing a whole fresh draft.

**One invariant.** A citekey may only be used if it appears in your `.bib`
export *and* was picked up into the ledger by a real parse of a real PDF.
No skill fabricates one, ever, and none may "fix" a gate failure by
inventing a plausible-looking key. It corrects the key or removes the
claim.

**The gate is the only exit.** `python -m chitragupta.draft gate` runs on the
skill's own output, and no draft is presented until it reports `OK`.

**The corpus is read-only.** No skill runs
`python -m chitragupta.corpus sync` or any
`python -m chitragupta.enrich` stage. Both take the pipeline's write lock
and can run for tens of minutes; they are yours to run. If the ledger
is empty or nothing is `parsed`, the skill says exactly what it checked
and what it found and stops instead of drafting around it.

**Every run writes a dossier**, created before the first retrieval call and
filled in as the run goes. Filling it in at the end would be too late, because
what was rejected has already fallen out of context. The exception is
`book-assembler`, which retrieves nothing and rejects nothing: a book's record
is already on disk as its signed outline, one acceptance record per unit, and
the three registries, all under `content/specs/<book>/`.

**Shared prose standards.** Name the reader before drafting, settle the
dialect with them and record it as `scope.md`'s `language:` line, read
the acronym vocabulary (`assets/style/acronyms.toml`, plus the user's own
`content/acronyms.toml` if `[style].acronyms` points at it) for a term's
canonical expansion instead of inventing one, define terms once, state
scope up front, active voice with a named actor, no
"obviously/simply/just", reread as the reader before presenting.
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) holds them and the
attribution: Diátaxis, Last's *Technical Writing Essentials* and Google's
Technical Writing courses, all CC-licensed and all requiring credit. Its
§9 is the one to read before building anything that checks a draft: it
says which of these rules have a decidable answer and which are a
judgement, and the two must not be treated alike.

**Rendering never blocks.** `.tex`/`.pdf` rendering that fails for a
missing binary prints a one-line warning and the `.md` draft is presented
anyway.

**The verbatim scan is run, reported, and never a gate.** Once the gate
has passed and the renders are done, and before presenting, each skill
rebuilds the draft's section map and runs the scan:

```bash
python -m chitragupta.draft dossier sections content/drafts/<path> --citekeys --write
python -m chitragupta.review verbatim scan content/drafts/<path>
```

That reports wording the draft shares with *any* parsed source, cited or not.
One skill does not run it: `review-digest` presents a draft that is the
sources' wording by design, so the scan would flag every run, and
`python -m chitragupta.review digest` is the check that replaces it (and
the critique loop) there. It does run the prose check below.
**It cannot block a draft, and no skill treats it as a condition of
presenting**. A skill may invoke a review aid; no review aid may block a
draft. `python -m chitragupta.draft gate` is the only gate.

The caveat travels with it, in every skill, because the drafter is the
one it is about. Two of the three detection tiers see wording only, so a
genuine restatement is invisible to them. The third sees one, but runs
only where the optional enrichment layer, the Docling sidecars, a synced
ledger and the draft's dossier are all present. That is why the first
command above is not optional: rebuilding `sections.md` is the one of
those conditions a skill can satisfy for itself. Where a tier still could
not run, the skill quotes the `tiers_not_run` reason the scan gave
instead of presenting two tiers of three as a clean result. So a clean scan is
not a clean bill of health.
[PLAGIARISM.md](PLAGIARISM.md) is what a drafter reads on that;
[PLAGIARISM-DESIGN.md](PLAGIARISM-DESIGN.md) has why each tier sees what
it sees.

**The prose check is run, reported, and never acted on.** Before presenting,
each skill runs `python -m chitragupta.draft style content/drafts/<path>` and
reports what it says: the findings, and the header lines naming which
dialect was checked and on whose authority. It measures only what
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) §9 marks decidable: §2's defect
markers, an acronym never expanded at first use or drifted from the
acronym vocabulary, §8's dialect against `scope.md`'s `language:` line,
table, figure and equation captions, ids and references, a self-numbered
chapter heading, and a code line wider than the page. So it is silent
on whether a paragraph leads with its point, it cannot tell a quotation
from the draft's own voice, and
`dialect: not checked` means nobody ever recorded one rather than that nothing
was wrong. **No genre skill fixes what it finds.** A finding is a place to
look, and many are correct as they stand. The fix paths are
`draft-reviser`'s copy-edit mode, which reads the recorded dialect and logs
one `revisions.md` entry naming the convention, and `agenda-reviser` for
unattended `prose` items.
Like the scan it exits 0 whatever it finds;
[ARCHITECTURE.md](ARCHITECTURE.md)'s "Layer 4" is why it may never become a
gate.

**Both are run, and neither writes without being asked.** Running them
on every draft means no draft is presented unchecked. Neither passes
`--write` unless the person asks, because a filed report can read as an
accusation, and neither can block a draft. (The earlier critique step
does file a verbatim baseline under `content/review/`, for its own
recheck.) A `PostToolUse`
hook reports the prose check per write, to the agent, mid-loop; these
steps report the finished draft once, to the human.
[HOOKS.md](HOOKS.md) has that split: invocation is enforced, conformance
is not.

## 🚧 The boundaries, and why they are enforced

Every skill carries a "When to invoke" table whose rows are mostly
*other* skills. The rows are there because the genre boundary is the
thing most likely to be crossed: crossing it feels helpful at the time.

Crossing it is costly because neighbouring genres have opposite rules.
A tutorial's "one path, no branches" would delete a
survey's deliverable, because alternatives are what a survey is for. A
survey's "weigh both sides without picking a winner" would gut a thesis
chapter, whose job is to take a position. A textbook chapter's
digressions into *why* are the exact defect that stalls a tutorial. So a
skill that drifts into the neighbouring genre produces a document that
fails at both jobs, and the failure is invisible until a reader tries
to use it.

This is [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §5 (don't let a
document do two jobs), enforced at the point where it is easiest to
break.

## 🚫 Genres this project does not have

A skill asked for one of these says so plainly:

| Genre | Reader's state | What happens |
| --- | --- | --- |
| **How-to guide** | already competent, has a specific goal | No skill. Say so, and write it as a short procedure |
| **Reference** | needs a fact, fast | No skill |

Both are Diátaxis quadrants this repository has deliberately not built.
`tutorial-writer` names them so that a request for one is answered
with a short procedure instead of a tutorial the asker does not need.

# 🎭 Genres

Status: **reference.**

**Written for** anyone choosing which skill to ask for, and anyone
wondering why a skill refused something. **Assumed:**
[AGENTS.md](https://github.com/prasadtalasila/chitragupta/blob/main/AGENTS.md),
the drafting contract these skills work under.
**Not covered here:** how a skill is written or changed. That is
`DEVELOPER-AGENTS.md` (git checkout only).

Eleven user-facing skills live in `.claude/` (a git checkout also
holds `demo-recorder` and `skill-bench`, developer tools no project
receives): six write a new draft, three change an existing one, one
assembles a book from units the others wrote, and one draws the figures
the others hand it. Of the three revisers, one is cheap and scoped, one
goes back to the whole corpus when you ask it to, and one works the
review agenda's unattended findings.

You do not invoke any of them by name. Each has a `description` in its
frontmatter that names its triggers, and asking for the thing in ordinary
words ("write a survey section on X", "draft a thesis chapter on Y")
selects it. This page covers choosing which genre to ask for, and
finding out why the skill that ran refused something.

Each genre has a start-to-finish tutorial with every command from
`dossier init` to a gated, rendered draft, and an example outline:
[survey](WRITE-A-SURVEY.md),
[thesis chapter](WRITE-A-THESIS-CHAPTER.md),
[textbook chapter](WRITE-A-TEXTBOOK-CHAPTER.md),
[tutorial](WRITE-A-TUTORIAL.md),
[deep-research report](WRITE-A-DEEP-RESEARCH-REPORT.md). The verbatim
digest has [VERBATIM-DIGEST.md](VERBATIM-DIGEST.md), and the book track
is walked through in [WRITE-A-BOOK.md](WRITE-A-BOOK.md).

Related reading:

- [WRITING-STANDARDS.md](WRITING-STANDARDS.md) has the prose rules the
  nine prose-writing skills (six genres, three revisers) share, and where
  in the technical-communication literature they come from.
- [DRAFT-ITERATION.md](DRAFT-ITERATION.md) covers the dossier every skill
  writes, and why `draft-reviser` exists.
-
  [TOKENS.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/TOKENS.md)
  covers what a run costs, and why re-running a genre skill to make a
  change is the most expensive mistake available here.
- [ARCHITECTURE.md](ARCHITECTURE.md) covers the drafting layer these sit
  in, and the corpus layer they all read and none of them writes.

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

The pair that gets confused is the teaching pair. If the request is
"write something teaching X", ask *will the reader be reading this, or
doing it?* Reading is `textbook-chapter-writer`; doing is
`tutorial-writer`. They have opposite rules about explanation, so a
wrong guess produces a document that fails at both.

## 🔭 At a glance

| | Output | Citation density | Subagents | Cost |
| --- | --- | --- | --- | --- |
| `survey-writer` | `content/drafts/<slug>.md` | every claim | one per sub-theme on a broad topic, otherwise none | one run |
| `thesis-chapter-writer` | `content/drafts/<slug>.tex` fragment | every claim | none | one run |
| `textbook-chapter-writer` | `content/drafts/<slug>.md` | sparse: background only | none | one run |
| `tutorial-writer` | `content/drafts/<slug>.md` | closing section only | none | one run, plus running the lesson |
| `deep-research` | `content/drafts/deep-research-<slug>.md` | every claim | 6 interviewers, N writers, 4 reviewers | heaviest by design |
| `review-digest` | `content/drafts/<topic>/<name>.md`, a survey whose body is the sources' own words | every copied run | none | one run, plus `review digest` |
| `draft-reviser` | edits an existing draft in place | inherits the draft's | none | cheapest path there is |
| `corpus-reviser` | edits an existing draft in place | inherits the draft's | none | a full retrieval pass, by request only |
| `agenda-reviser` | edits an existing draft in place | inherits the draft's | none | one agenda run, then one edit per unattended item |
| `book-assembler` | `content/rendered/<book>/book.tex` | writes none of its own | none | one composition pass over accepted units |
| `figure-drawer` | one `figures/<name>.tex` + `.txt` pair beside a draft | none: no citekey in a figure file | none | one figure, compiled and reviewed |

All six drafting skills also write `content/dossiers/<draft path minus
suffix>/`; `deep-research` and `thesis-chapter-writer` additionally write
a machine-readable `provenance.json` there. Nothing under `content/` is
tracked by git; see
[DRAFT-ITERATION.md](DRAFT-ITERATION.md#-backup-and-restore) for backing
up a draft and its dossier.

## ✍ The six drafting genres

Four of the six have a committed, gate-passed sample under a thousand
words, drafted by the real pipeline over the five-paper sample corpus,
each with its dossier under `content/dossiers/`:
[`survey.md`](examples/sample-project/content/drafts/dt-overview/survey.md)
(survey),
[`staleness-tutorial.md`](examples/sample-project/content/drafts/dt-overview/staleness-tutorial.md)
(tutorial; every step executed before being presented),
[`staleness-chapter.md`](examples/sample-project/content/drafts/dt-overview/staleness-chapter.md)
(textbook chapter) and
[`trust-chapter.tex`](examples/sample-project/content/drafts/dt-overview/trust-chapter.tex)
(thesis chapter fragment). Read them as samples of *shape*: the
sources are synthetic.

### 📚 `survey-writer`

Topic-clustered literature survey, background section, related-work
section, "state of the art". Retrieves across two to four sub-themes,
judges every candidate, clusters what survives by theme, and closes with
a comparison table and a gap analysis.

Its job is to organise a field and locate the gaps. It has two failure
directions: drifting into a textbook chapter (teaching, when the reader
needs the map) and drifting into an argument (defending one approach,
which is the thesis chapter's job). Alternatives are the deliverable, so
they are never collapsed for a cleaner narrative. Its retrieval pass
dominates its token cost;
[TOKENS.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/TOKENS.md#-example-1-one-rejected-paper-followed-to-the-end-of-the-run)
works through the numbers.

### 🎓 `thesis-chapter-writer`

A chapter tied to a specific research question, written for an examiner
reading adversarially. Unlike a survey it takes a position, but every
step of the argument traces to something cited, and an honestly stated
limitation is worth more than the paragraph that hides it.

The output is a standalone `.tex` fragment using `\citep`/`\citet`, with
no preamble, meant to be `\input` by your own thesis. It also renders
`.md` and `.pdf` previews when pandoc and LuaLaTeX are present. A chapter
that only summarises papers in sequence is a survey with a chapter
heading: the argument toward the research question has to be visible in
the section structure.

### 📘 `textbook-chapter-writer`

An undergraduate chapter: learning objectives, motivation, worked
examples, exercises. Diátaxis-wise this is *explanation with worked
application*, and the least citation-dense of the six: the corpus is
cited for motivation and background, and the gate still applies to
whatever it cites.

Its discipline is the **curse of knowledge**: the danger is the step that
feels too obvious to state. Terms are defined once at first use;
"obviously", "simply", "just" and "of course" mark a sentence for
expansion. Concrete instance first, then generalise.

### 🛠 `tutorial-writer`

A Diátaxis tutorial: a lesson a learner follows at a keyboard to a
working result they can see ([its writing
rules](writing-standards/genres/tutorial.md)). Its rule: **a tutorial
that doesn't work is worse than no tutorial**, because a learner who
gets an error concludes that they are the problem.

So the lesson follows one path with no branches, uses a concrete value
wherever a placeholder might go, and says what the learner should see
after every step that produces output. The whole lesson is run end to
end before it is presented. Citations appear only in a closing "Where to
go next" section. Its failure directions are drifting into explanation
and drifting into a how-to that offers alternatives a learner cannot yet
evaluate.

### 🔬 `deep-research`

Seven phases and a dozen subagents: perspective discovery, parallel
grounded interviews, contradiction mapping, outline, parallel cited
section writing, synthesis briefing, and a peer-review panel. It adapts
`hadufer/claude-storm`'s implementation of Stanford OVAL's STORM method
to cite only real citekeys from this project's corpus. It alone produces
a **contradiction map** (both sides by citekey), a named blind spot,
findings ranked by corpus support, and a scorecard from four reviewers,
one adversarial.

| Depth | Perspectives | Interview rounds | Section writers |
| --- | --- | --- | --- |
| `quick` | 3 + basic | 2 | inline, no subagents |
| `standard` (default) | 5 + basic | 3 | parallel subagents |
| `deep` | 6-7 + basic | 4 | parallel subagents |

It is the heaviest skill here and says so before it starts; for a
single-pass survey it points you to `survey-writer`. Its cost structure
is in
[TOKENS.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/TOKENS.md#-example-2-six-interview-packets-from-phase-3-to-phase-7f).

### 📋 `review-digest`

A verbatim digest is a survey written in the sources' words: a survey's
reader, scope, theme sections, comparison table and gap analysis, with a
body copied exactly from parsed PDFs, each copied run closed by its
citation, equations typeset, and the drafter's own sentences few. Its
reader is the user, studying. It is never a deliverable and never a
source for any other draft.

It runs `survey-writer`'s workflow, replacing every step that keeps
source wording out of a draft: the main passages are recorded as
`quote:` entries, and the verbatim scan and critique loop are replaced by
`python -m chitragupta.review digest`, which reports every sentence no
source backs. It still runs the prose check, and alone may place a
source's figure beside its run. [VERBATIM-DIGEST.md](VERBATIM-DIGEST.md)
has the rest, including the one prohibition: never run `agenda-reviser`
on a digest.

## ✏ Revising: `draft-reviser`

`draft-reviser` changes a draft one of the six already wrote, including
in a session that has never seen it. It reads the dossier instead of the
corpus: `scope.md` and `steering.md` bound the change, `sections.md` maps
it onto line ranges, and `rejected.md` is consulted before any new
retrieval. A request that contradicts the recorded scope is a scope
change, and the skill says so.

It also re-grounds a draft when `dossier status --all` reports that a
sync removed a cited paper, repairing only the sections that carry the
broken citations and re-stamping the fingerprint once the gate passes;
see
[DRAFT-ITERATION.md](DRAFT-ITERATION.md#-re-grounding-after-the-corpus-moves).
A draft with no dossier gets one from `dossier init`, with `evidence.md`
left honestly empty rather than invented.

Every drafting skill routes changes here, in its body and in its
frontmatter `description`, which is what picks a skill in the first
place. Nothing enforces the rule; the only mechanical gate is
`citation_gate`, and how wide a revision should look is a judgement
[SOUL.md](../SOUL.md) keeps from machines. So the wider option is a
separate skill.

## 🔁 Revising widely: `corpus-reviser`

`corpus-reviser` re-searches every sub-theme the dossier records (the
queries in `retrieval.md`, or the headings in `sections.md`) and reads
the whole draft. It is a separate skill so that the choice is yours:
`draft-reviser` contains no instructions for a wide search, so it cannot
drift into one.

Invoke it when you ask for a whole-corpus pass in as many words, when an
agreed scope change has invalidated the recorded queries, or when the
draft is re-targeted at a different reader. Anything else, including
repairing citations after a sync, is `draft-reviser`; when unclear, the
skills pick `draft-reviser` and say so. It states the cost in
`revisions.md` before its first search, honours `rejected.md`, and edits
section by section, because a wide search does not imply a wide rewrite.
Neither reviser ever re-runs the genre skill, which would discard the
dossier's state.

## 🩹 Working the agenda: `agenda-reviser`

`agenda-reviser` takes one worklist: `python -m chitragupta.review
agenda <draft>`, every review aid's report merged and ranked. Each item's
own `unattended` field says whether the skill may act without asking.
Three classes can qualify: `verbatim-run` at severity `short`, `prose`
(where the rule marks it editable), and `missing-citekey`. A `long` run
stops and asks whether to paraphrase or quote, an authorial choice
[SOUL.md](../SOUL.md) leaves to you. Finishing the list is not a clean
bill of health; see [PLAGIARISM.md](PLAGIARISM.md).

Every repair must pass `python -m chitragupta.draft gate` and the
`python -m chitragupta.review agenda --baseline` recheck, with the
finding gone and no objective finding added. Two attempts per finding,
one pass per invocation, every attempt logged in `revisions.md`. Only a
person starts it, and a finding it cannot repair is escalated.

## 📕 Assembling a book

`book-assembler` writes no prose. It composes accepted, gate-passed units
into one LaTeX book (front matter, `\part`, `\chapter`, one `\input` per
unit, back matter) from the outline `python -m chitragupta.draft spec`
holds and the acceptance records `python -m chitragupta.draft unit`
wrote. It stops at the book track's second human gate, presenting every
registry finding without declaring the book finished. A missing,
unaccepted or stale unit goes back to the genre skill or `draft-reviser`.
[WRITE-A-BOOK.md](WRITE-A-BOOK.md) describes the track.

## 🖍 Drawing a figure: `figure-drawer`

`figure-drawer` owns *how* a figure is drawn: the scaffold from
`assets/tikz/`, panel letters, the ASCII twin, the compile probe and the
geometry review. It never decides *whether* a draft gets a figure, and
never presents a draft. `survey-writer`, `tutorial-writer`,
`textbook-chapter-writer` and `thesis-chapter-writer` hand off to it, as
does `draft-reviser`; control then returns to the caller, which gates and
renders. `deep-research` uses no figures. Invoked directly on an
existing draft, it is a revision and continues in `draft-reviser`'s
write-back and gate steps.

Each genre skill keeps a short figure step in case the handoff is
skipped: its when-to-draw threshold, its output shape, and **no citekey
inside either figure file**, because the gate does not follow `\input`.
`tests/test_skill_figure_step.py` pins that stub.
[FIGURE-DRAWER.md](FIGURE-DRAWER.md) is the skill's own page.

## 🔑 What all eleven have in common

These rules are the same in every skill, stated in each `SKILL.md` or,
where several share the wording, once in a reference under
`.claude/skills-common/references/` that the skill's step names. A skill
that breaks one has a bug. Each `SKILL.md` exists once per harness
(`.claude/skills/`, `.agents/skills/`, `.opencode/skills/*-opencode/`):
**change every copy**, and see [HARNESS.md](HARNESS.md) for the phrase
map `tests/test_skill_harness_copies.py` checks.

`book-assembler` writes nothing of its own, so the writing rules (the
dossier, the acronym vocabulary) say how it differs. `figure-drawer`
presents no draft, so the gate, the prose check, the verbatim scan and
the stamp belong to its caller; it carries only the invariant. The
pre-gate self-feedback step belongs to the five genre skills that write
fresh prose from an evidence packet (`survey-writer`,
`thesis-chapter-writer`, `textbook-chapter-writer`, `tutorial-writer`,
`deep-research`), and not to `book-assembler` or the three revisers,
which gate-and-recheck per section.

**One invariant.** A citekey may only be used if it appears in your `.bib`
export *and* was picked up into the ledger by a real parse of a real PDF.
No skill fabricates one, or "fixes" a gate failure by inventing one. It
corrects the key or removes the claim.

**The gate is the only exit.** `python -m chitragupta.draft gate` runs on
the skill's own output, and no draft is presented until it reports `OK`.

**The corpus is read-only.** No skill runs
`python -m chitragupta.corpus sync` or any `python -m chitragupta.enrich`
stage; they take the write lock and are yours to run. On an empty ledger
the skill says what it checked and stops.

**Every run writes a dossier**, created before the first retrieval call,
because what was rejected falls out of context by the end. A book's
record is instead its signed outline, acceptance records and registries
under `content/specs/<book>/`.

**Shared prose standards.** Name the reader, record the dialect as
`scope.md`'s `language:` line, take expansions from the acronym
vocabulary (`assets/style/acronyms.toml`, plus `content/acronyms.toml` if
`[style].acronyms` points at it), define terms once, active voice, no
"obviously/simply/just". [WRITING-STANDARDS.md](WRITING-STANDARDS.md)
holds them and their attribution; its §9 says which rules are decidable.

**Rendering never blocks.** A render that fails for a missing binary
prints a one-line warning and the `.md` draft is presented anyway.

**The verbatim scan is run, reported, and never a gate.** After the gate
and renders, each skill rebuilds the section map and runs the scan:

```bash
python -m chitragupta.draft dossier sections content/drafts/<path> --citekeys --write
python -m chitragupta.review verbatim scan content/drafts/<path>
```

It reports wording the draft shares with any parsed source, cited or
not. `review-digest` runs `python -m chitragupta.review digest` instead.
No review aid may block a draft. Each skill quotes any `tiers_not_run`
reason, since the tier that sees restatement runs only with enrichment,
a synced ledger and the dossier present, so a clean scan is not a clean
bill of health; see [PLAGIARISM.md](PLAGIARISM.md).

**The prose check is run, reported, and never acted on.** Each skill
runs `python -m chitragupta.draft style content/drafts/<path>` and
reports the findings and the dialect header. It measures only what
WRITING-STANDARDS.md §9 marks decidable, so `dialect: not checked` means
none was recorded. **No genre skill fixes what it finds**; the fix paths
are `draft-reviser`'s copy-edit mode and `agenda-reviser`. It exits 0
whatever it finds ([ARCHITECTURE.md](ARCHITECTURE.md)'s "Layer 4").
Neither check passes `--write` unless asked, because a filed report can
read as an accusation. A `PostToolUse` hook reports the prose check per
write to the agent; [HOOKS.md](HOOKS.md) has that split.

## 🚧 The boundaries, and why they are enforced

Every skill carries a "When to invoke" line that mostly names *other*
skills, because crossing a genre boundary feels helpful at the time.
Neighbouring genres have opposite rules: a tutorial's "one path" would
delete a survey's alternatives, a survey's even-handedness would gut a
thesis chapter's position, and a textbook's digressions stall a
tutorial. A drifted document fails at both jobs, invisibly until a reader
tries to use it. This is [WRITING-STANDARDS.md](WRITING-STANDARDS.md) §5
(don't let a document do two jobs).

## 🚫 Genres this project does not have

A skill asked for one of these says so plainly:

| Genre | Reader's state | What happens |
| --- | --- | --- |
| **How-to guide** | already competent, has a specific goal | No skill. Say so, and write it as a short procedure |
| **Reference** | needs a fact, fast | No skill |

Both are Diátaxis quadrants this repository has deliberately not built.
`tutorial-writer` names them so that a request for one is answered
with a short procedure instead of a tutorial the asker does not need.

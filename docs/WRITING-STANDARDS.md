# Writing standards for the drafting layer

Status: **reference.** Written 2026-08-03.

**Written for** anyone drafting with this pipeline, and for the skills
that draft on their behalf. **Assumed:** [GENRE.md](GENRE.md) for which
skill does what. **Not covered here:** the prose standard this
repository's *own* documentation is held to, which is
[HOUSE-STYLE.md](HOUSE-STYLE.md).

Shared prose standards for every skill in `.claude/skills/`. Each SKILL.md
points here rather than restating them, and adds only the rules specific to
its own genre.

These are drawn from the technical-communication literature -- primarily the
[Diátaxis](https://diataxis.fr/) framework, Google's
[Technical Writing courses](https://developers.google.com/tech-writing), and
Suzan Last's *Technical Writing Essentials* (BCcampus). What follows is the
part that transfers across all five genres. **Diátaxis's genre-specific rules
do not all transfer** -- "one path, no options, minimal explanation" is
correct for `tutorial-writer` and actively wrong for `survey-writer`, where
weighing alternatives *is* the deliverable. Take the audience discipline and
the sentence-level craft from these sources; take the structural rules only
from your own SKILL.md.

## 1. Decide the audience before drafting

*Source: Google, Technical Writing One ("Just enough writing" / audience
analysis); Last, TWE §7.7 "Do a careful audience and task analysis".*

Write down -- in working notes, not necessarily in the document -- who the
reader is and what they already know. Every downstream decision depends on
it: what can go unexplained, which background needs a recap, how much
notation is safe, how much hedging is appropriate.

A named reader beats a category. "A second-year undergraduate who has taken
one programming course" is usable; "students" is not. "A thesis examiner in
this subfield" is usable; "an academic audience" is not.

## 2. The curse of knowledge is the default failure

*Source: Google, Technical Writing One, which names the curse of knowledge
as the central hazard for engineer-writers. The term itself is Camerer,
Loewenstein and Weber (1989), popularised by Steven Pinker.*

You know the material and the reader does not. The specific danger is the
step that feels too obvious to state -- which is exactly the step you will
omit and the reader will fail on.

Concrete guards:

- Define each term once, at first use, then use it consistently. Never two
  names for one concept, never one name for two concepts.
- Expand an acronym at first use, then use the acronym. Don't reintroduce the
  expansion later, and don't drift back to the long form.
- Treat **"obviously", "simply", "just", "of course", "clearly", "easy"** as
  defect markers. When the thing isn't obvious, the reader concludes the
  failure is theirs. Delete the word; if the sentence then looks like it's
  asserting too much, that's the actual problem showing through.

## 3. State scope up front

*Source: Last, TWE §7.7, whose introduction checklist asks for the scope --
"what will and will not be covered" -- and the reader's assumed background.*

Say what the document covers, what it deliberately does not, and what the
reader is assumed to know already. A reader who can't tell whether they're
equipped for a document will either bounce off it or waste an hour finding
out they were missing background.

## 4. Sentence-level craft

*Source: Google, Technical Writing One (short sentences, active voice,
consistent terms, defining terms once); Last, TWE §2.2 "Communicating with
Precision" and §7.7 "Writing Style" on the passive-voice failure.*

- Short sentences, one idea each. If a sentence must be reread to parse,
  split it.
- Active voice with a named actor: "the scheduler discards the packet", not
  "the packet is discarded".
- Prefer a concrete instance over an abstract statement of the general case,
  then generalize from it. Readers build general rules from instances, not
  the reverse.
- Lead each paragraph with its point. A reader skimming only first sentences
  should still get the argument.
- Cut hedging that carries no information. "It may be argued that X is
  possibly a factor" says less than "X is a factor", and the difference is
  not caution -- it's noise. Real uncertainty gets stated, once, precisely.

## 5. Don't let a document do two jobs

*Source: Procida, Diátaxis -- the four-quadrant model and its claim that
each kind of documentation "needs to be written in a different way".*

This is Diátaxis's actual portable insight. A document that tries to be both
a survey and a tutorial is worse at each than either would be alone, because
the two have opposite obligations: a survey must present alternatives and
weigh them, a tutorial must eliminate every choice.

If, while drafting, you find yourself writing material that belongs to a
different genre, **stop and say so to the user** rather than absorbing it.
The routing tables in each SKILL.md's "When to invoke" section exist for
exactly this moment.

## 6. Read it once as the reader

*Source: Last, TWE §7.7, which names as a requirement of effective
instructions the "willingness to test your instructions on the kind of
person you wrote them for".*

Before presenting anything, reread the draft as the reader defined in §1 --
not as yourself. Flag every point where a term arrives undefined, a step
skips reasoning, notation changes meaning mid-document, or a claim assumes
something never established.

This pass catches more real problems than any other single step. The
technical-communication literature's stronger form of it is a usability
test with a real member of the audience. That is not available inside a
drafting run, so this reread is the substitute. Make it a genuine second
pass, not a skim of what you just wrote.

## 7. Say what you don't know

Every genre here shares one rule from AGENTS.md's citekey invariant: a gap
stated plainly is always better than a gap papered over. Thin corpus
coverage, an unresolved contradiction, a step you couldn't verify -- all of
these get reported to the user in prose. None of them get smoothed.

## 8. Dialect and house style

A draft is written in one dialect of English, and which one is a fact
about the reader rather than a habit of the writer. A thesis submitted at
an Indian university is en-IN or en-GB; an IEEE submission is en-US; a
European funder's deliverable is usually en-GB. Settle it in §1, with the
reader, and record it as the `language:` line in the dossier's `scope.md`
-- a BCP-47 tag, so `en-GB`, not "British".

Recording it is the point. A preference stated in chat is gone by the
next session, and the model's own default takes over the first revision
made weeks later, silently. `draft-reviser` reads `scope.md` before any
edit, so a tag on disk reaches every future revision with no further
instruction and no restating.

One dialect per draft, and it governs the draft's *own* prose. Quoted
material keeps its source's spelling, and so do a cited title, a proper
noun, and a dataset or code identifier: changing those is a misquotation,
not a correction.

**House style is the same field's second half.** A target venue may
impose conventions these standards do not settle: serial comma or not,
"Section 3" or "§3", how a figure is captioned. Record the decision
beside the dialect, rather than re-deciding it section by section.

**A caveat this section owns.** §2's defect-marker list is English
literals, and §4's voice rules are an Anglophone technical-writing
convention. A draft in another language needs them adapted rather than
transliterated, and nothing in this document should be read as claiming
they carry over unchanged.

## 9. What is checked mechanically, and what is not

Some rules above have a decidable answer and some do not. The split
matters in both directions, and getting it wrong fails in opposite ways.
Mechanising §4's "short sentences" builds a machine that splits sentences
past the point the argument survives. Leaving §2's literals to memory
means they are checked only when someone remembers to.

| Rule | Section | Decidable? | May a machine act on it unattended? |
|---|---|---|---|
| Dialect matches `scope.md`'s `language:` | §8 | yes | yes |
| No defect markers: "obviously", "simply", "of course", "clearly", "easy" | §2 | yes | yes |
| "just", specifically | §2 | no | no -- the adverb ("just add the flag") and the adjective ("a just outcome") are not separable by string match, so it is reported for a human eye |
| Each term defined once, then used consistently | §2 | yes, given the dossier's glossary | yes |
| Acronym expanded at first use, then not re-expanded | §2 | yes -- first occurrence is computable | yes |
| Active voice with a named actor | §4 | detectable | no -- the fix is a judgement |
| Each paragraph leads with its point | §4 | heuristic only | no -- surfaced, never applied |
| Hedging that carries no information | §4 | detectable | no -- the fix is a judgement |
| Short sentences, one idea each | §4 | **no: this is a score** | no |
| The reread as the reader | §6 | no | never |

**Nothing in the last column is a continuous score, deliberately.** A
readability index is the tempting exception, and the instructive one. A
loop minimising grade level splits sentences past the point the argument
survives, and replaces precise technical vocabulary with shorter, vaguer
words -- because a polysyllabic term is indistinguishable to the metric
from bad writing.

It may be reported. It may never be optimised.
[HOUSE-STYLE.md](HOUSE-STYLE.md) has that argument in full.

**Quoted spans are exempt from every row, and this is the one place that
needs saying.** Drafts produced by this pipeline contain source text by
construction, so "simply" inside a quoted abstract and an `-ize` inside a
cited title are correct rather than findings. No rule here has a
zero-exception form, which is also why none of them may become a gate --
see [ARCHITECTURE.md](ARCHITECTURE.md)'s "Layer 4" for the axis that
decides which checks may block, and [SOUL.md](../SOUL.md) for why there is
exactly one that does.

**Every verdict in the table is scoped to English**, for the reason §8
gives.

## Sources and attribution

Three openly licensed works supply the principles above. All three require
attribution under their licences; this section is that attribution.

1. **Daniele Procida, *Diátaxis: A systematic approach to technical
   documentation authoring***. <https://diataxis.fr/> — source repository
   <https://github.com/evildmp/diataxis-documentation-framework>.
   Licensed CC-BY-SA 4.0.
   Supplies: the four-quadrant genre model (tutorial / how-to / reference /
   explanation); the definition of a tutorial as a lesson in which the
   instructor is responsible for the learner's success; the driving-lesson
   analogy; the diagnosis of explanation-overload in tutorials; the
   narrative-of-expectations technique. `tutorial-writer` is built on this
   source more than any other.

2. **Suzan Last, *Technical Writing Essentials***, University of Victoria /
   BCcampus, 2019.
   <https://pressbooks.bccampus.ca/technicalwriting/> — §7.7 "Writing
   Instructions" is the chapter drawn on most. Licensed CC-BY 4.0. That
   chapter is itself adapted from David McMurrey's *Online Technical
   Writing* (<https://mcmassociates.io/textbook/>, CC-BY 4.0), which is
   therefore credited transitively.
   Supplies: audience and task analysis as a preliminary step; scope and
   assumed-background statements in the introduction; equipment and
   supplies lists; the placement and function of note/warning/caution
   notices; command-verb phrasing and the argument against passive voice in
   instructions; testing instructions on a real member of the audience.

3. **Google, *Technical Writing Courses for Engineers***.
   <https://developers.google.com/tech-writing>. Licensed CC-BY 4.0.
   Supplies: the curse of knowledge as the defining failure mode; defining
   each term once and using it consistently; expanding an acronym at first
   use and then not reverting; short sentences with one idea each; active
   voice with a named actor; leading a paragraph with its point.

### What is original here

The prose in this file and in every `.claude/skills/*/SKILL.md` is written
from scratch. A verbatim n-gram check against all three sources above
(107,272 words of source; the algorithm is `src/review/verbatim_check.py`'s
`cmd_overlap`) reports **0% overlap at an 8-word threshold**, and nothing
above five consecutive shared words anywhere. What is borrowed is the
*ideas*, credited above; what is added is their translation into
operational rules for this pipeline's five genres, the decision about which
principles transfer across genres and which do not (§5's warning), and the
handling of failure modes specific to multi-agent drafting.

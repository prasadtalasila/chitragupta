# ✍ Writing standards for the drafting layer

Status: **reference.**

**Written for** anyone drafting with this pipeline, and for the skills
that draft on their behalf. **Assumed:** [GENRE.md](GENRE.md) for which
skill does what. **Not covered here:** the prose standard this
repository's *own* documentation is held to, which is
[HOUSE-STYLE.md](HOUSE-STYLE.md).

Shared prose standards for every skill in `.claude/skills/`. Each drafting and
revising SKILL.md points here rather than restating them, and adds only the
rules specific to its own genre.

These are drawn from the technical-communication literature, primarily the
[Diátaxis](https://diataxis.fr/) framework, Google's
[Technical Writing courses](https://developers.google.com/tech-writing), and
Suzan Last's *Technical Writing Essentials* (BCcampus). What follows is the
part that transfers across all six genres. **Diátaxis's genre-specific rules
do not all transfer**: "one path, no options, minimal explanation" is
correct for `tutorial-writer` and actively wrong for `survey-writer`, where
weighing alternatives *is* the deliverable. Take the audience discipline and
the sentence-level craft from these sources; take the structural rules only
from your own SKILL.md.

## 🗂 The index: which file holds which rule

The standards are this file, the core, and the files under
`docs/writing-standards/` that it indexes. An element file holds the
rules for one thing a draft can contain, a genre file the rules for one
genre, and a style file one house style.

| Layer | File | Sections | Holds |
| --- | --- | --- | --- |
| Core | this file | §1–9, §11, §15, §16 | the rules every draft follows, this index, precedence, and sources and attribution |
| Element | [`writing-standards/figures.md`](writing-standards/figures.md) | §10 | figures, checked by `chitragupta/style_figures.py` |
| Element | [`writing-standards/mathematics.md`](writing-standards/mathematics.md) | §12 | mathematics, checked by `chitragupta/style_equations.py` and `render` |
| Element | [`writing-standards/tables.md`](writing-standards/tables.md) | §13 | tables, checked by `chitragupta/style_tables.py` |
| Element | [`writing-standards/page.md`](writing-standards/page.md) | §14 | what has to fit the page, checked by `chitragupta/style_typeset.py` |
| Genre | [`writing-standards/genres/README.md`](writing-standards/genres/README.md) | none yet | what each genre owes its reader; no genre file yet |
| Style | [`writing-standards/styles/README.md`](writing-standards/styles/README.md) | none | house styles to come; no style yet |

Five rules keep the layers from going piecemeal:

- **Section numbers are global and never reused.** A section that moves
  out of the core keeps its number, and its sub-headings keep their
  titles, so a citation reads `docs/writing-standards/figures.md` §10.
  A new section takes a number no file has used.
- **The core keeps a stub heading for each moved section**, with its
  emoji, number and title unchanged, so every existing anchor
  (`#-10-figures`) and every `WRITING-STANDARDS.md` §10 citation still
  lands on a line that links to the new file. Citations move to the
  direct path one change at a time.
- **Each layer file opens with "Assumes the core, §1–9"**, repeats no
  other file's text, and is at least about 3 KB; a smaller one merges
  into its neighbour. The two folder READMEs are exempt.
- **Every file under `docs/writing-standards/` is a row of the table
  above.** `tests/test_writing_standards_layers.py` fails on one that is
  not, on a cited section no heading carries, on an anchor no heading
  produces, and on a number that heads two sections.
- **Precedence is #1181's, not a new one.** Where two sources of
  guidance disagree, the order is: the citekey invariant; the venue (a
  research paper's `paper.md`); the writing standards, core, element
  and genre files alike, unless a recorded conflict is resolved to
  `profile`; the learnt style. A conflict recorded in a dossier's
  `style.md` names a section by its global number, which the split keeps
  stable. #1181's learnt style is not built yet; until it is, the first
  three are the whole order.

## 👥 1. Decide the audience before drafting

*Source: Google, Technical Writing One ("Just enough writing" / audience
analysis); Last, TWE §7.7 "Do a careful audience and task analysis".*

Write down (in working notes, not necessarily in the document) who the
reader is and what they already know. Every downstream decision depends on
it: what can go unexplained, which background needs a recap, how much
notation is safe, how much hedging is appropriate.

A named reader beats a category. "A second-year undergraduate who has taken
one programming course" is usable; "students" is not. "A thesis examiner in
this subfield" is usable; "an academic audience" is not.

## ⚠ 2. The curse of knowledge is the default failure

*Source: Google, Technical Writing One, which names the curse of knowledge
as the central hazard for engineer-writers. The term itself is Camerer,
Loewenstein and Weber (1989), popularised by Steven Pinker.*

You know the material and the reader does not. The specific danger is the
step that feels too obvious to state, which is exactly the step you will omit
and the reader will fail on.

Concrete guards:

- Define each term once, at first use, then use it consistently. Never two
  names for one concept, never one name for two concepts.
- Expand an acronym at first use, then use the acronym. Don't reintroduce the
  expansion later, and don't drift back to the long form.
- Treat **"obviously", "simply", "just", "of course", "clearly", "easy"** as
  defect markers. When the thing isn't obvious, the reader concludes the
  failure is theirs. Delete the word; if the sentence then looks like it's
  asserting too much, that's the actual problem showing through.
- Label each textbook exercise
  `**Exercise N (Objective M, easy|medium|hard).**`, where `M` is the
  learning objective it exercises. The grade in that label is a difficulty
  rating for the student, not a defect marker, and the prose check skips
  the label. The word "easy" in a sentence is still a marker.

## 📏 3. State scope up front

*Source: Last, TWE §7.7, whose introduction checklist asks for the scope,
"what will and will not be covered", and the reader's assumed background.*

Say what the document covers, what it deliberately does not, and what the
reader is assumed to know already. A reader who can't tell whether they're
equipped for a document will either bounce off it or waste an hour finding
out they were missing background.

## 🖋 4. Sentence-level craft

*Source: Google, Technical Writing One (short sentences, active voice,
consistent terms, defining terms once); Last, TWE §2.2 "Communicating with
Precision" and §7.7 "Writing Style" on the passive-voice failure. The
concrete-instance rule, which `textbook-chapter-writer` leans on hardest,
is Wilson's, TTT "Expertise and Memory", and the Carpentries' (a worked
example before the exercise that practises it).*

In a verbatim digest ([VERBATIM-DIGEST.md](VERBATIM-DIGEST.md)) these
rules bind the drafter's own sentences only; copied text keeps its
source's style.

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
  possibly a factor" says less than "X is a factor" and is no more
  cautious. State real uncertainty once, precisely.

## ✂ 5. Don't let a document do two jobs

*Source: Procida, Diátaxis: the four-quadrant model and its claim that
each kind of documentation "needs to be written in a different way".*

This is the part of Diátaxis that carries over to every genre. A document that
tries to be both a survey and a tutorial is worse at each than either would be
alone, because the two have opposite obligations: a survey must present
alternatives and weigh them, a tutorial must eliminate every choice.

If, while drafting, you find yourself writing material that belongs to a
different genre, **stop and say so to the user** rather than absorbing it.
The routing tables in each genre SKILL.md ("When to invoke", or "What
this genre is not" in `tutorial-writer`) exist for this case.

## 👓 6. Read it once as the reader

*Source: Last, TWE §7.7, which names as a requirement of effective
instructions the "willingness to test your instructions on the kind of
person you wrote them for".*

Before presenting anything, reread the draft as the reader defined in §1,
not as yourself. Flag every point where a term arrives undefined, a step
skips reasoning, notation changes meaning mid-document, or a claim assumes
something never established.

This pass catches more real problems than any other single step. The
technical-communication literature's stronger form of it is a usability
test with a real member of the audience. That is not available inside a
drafting run, so this reread is the substitute. Read the whole draft a
second time; do not skim it.

## ❓ 7. Say what you don't know

Every genre here shares one rule from AGENTS.md's citekey invariant: a gap
stated plainly is always better than a gap papered over. Thin corpus
coverage, an unresolved contradiction, a step you couldn't verify: report
each of these to the user in prose instead of smoothing it over.

## 🗣 8. Dialect and house style

A draft is written in one dialect of English, and which one is a fact
about the reader rather than a habit of the writer. A thesis submitted at
an Indian university is en-IN or en-GB; an IEEE submission is en-US; a
European funder's deliverable is usually en-GB. Settle it in §1, with the
reader, and record it as the `language:` line in the dossier's `scope.md`
(a BCP-47 tag, so `en-GB`, not "British").

Recording it matters because a preference stated in chat is gone by the
next session, and the model's own default takes over the first revision
made weeks later, silently. `draft-reviser` reads `scope.md` before any
edit, so a tag on disk reaches every future revision with no further
instruction and no restating.

One dialect per draft, and it governs the draft's *own* prose. Quoted
material keeps its source's spelling, and so do a cited title, a proper
noun, and a dataset or code identifier: changing those is a misquotation,
not a correction.

A dialect match that starts with a capital letter is reported for a
person to decide rather than repaired. "Modeling" in "Unified Modeling
Language" is a name, and a capital cannot tell a name from a sentence's
first word, so the cost of a wrong guess is one question. Declare the
name in `content/style_exceptions.toml` ([§9](#-9-what-is-checked-mechanically-and-what-is-not))
and it stops being reported.

House style belongs in the same field. A target venue may
impose conventions these standards do not settle: serial comma or not,
"Section 3" or "§3", how a figure is captioned. Record the decision
beside the dialect, rather than re-deciding it section by section.

§2's defect-marker list is English literals, and §4's voice rules are an
Anglophone technical-writing convention. A draft in another language needs
them adapted rather than transliterated; they do not carry over
unchanged.

## ✅ 9. What is checked mechanically, and what is not

Some rules above have a decidable answer and some do not, and putting a
rule on the wrong side fails either way. Mechanising §4's "short
sentences" builds a machine that splits sentences past the point the
argument survives; leaving §2's literals to memory means they are checked
only when someone remembers to.

| Rule | Section | Decidable? | Checked by, and may a machine repair it unattended? |
| --- | --- | --- | --- |
| Dialect matches `scope.md`'s `language:` | §8 | yes | `DialectGB`/`DialectUS`/`DialectIN`: yes when the dialect came from `scope.md` or `--language` and the match is lower case; no (`review`) when it came from `config.toml` or the match starts with a capital letter, which may be a name ([§8](#-8-dialect-and-house-style)) |
| No defect markers: "obviously", "simply", "of course", "clearly", "easy" | §2 | yes | `DefectMarkers`: yes |
| "just", specifically | §2 | no: the adverb ("just add the flag") and the adjective ("a just outcome") are not separable by string match | `Just`: no (`review`). The finding asks which one it is; only the adverb is a defect, so a person decides |
| Each term defined once, then used consistently | §2 | yes, given the dossier's glossary | not checked for a plain term; only acronyms are (next two rows) |
| Acronym expanded at first use, then not re-expanded | §2 | yes: first occurrence is computable | `Acronyms`: yes |
| An acronym's expansion is written in the case the vocabulary gives it | §2 | yes, given `[style].acronyms` | `AcronymCase`: no (`review`). Whether the vocabulary or the draft has the wrong case is a person's call |
| A glossary's acronym expansion still matches the current acronym vocabulary | §2 | yes, given the dossier's glossary and `[style].acronyms`; only the glossary is compared, not the draft's prose | `AcronymDrift`: yes |
| Active voice with a named actor | §4 | detectable | not checked: the fix is a judgement |
| Each paragraph leads with its point | §4 | heuristic only | not checked |
| Hedging that carries no information | §4 | detectable | not checked: the fix is a judgement |
| Short sentences, one idea each | §4 | **no: this is a score** | not checked |
| Citekeys per unit, and how many units rest on one source | §11 | yes | `review synthesis` counts it; never acted on, because a thin corpus legitimately produces single-source units |
| Whether a sentence carries a citation at all | §11 | yes, per sentence; *whether it needs one* is not | `review uncited` surfaces it; never acted on, because the fix is evidence, not wording |
| A table has a caption and an id, and every reference resolves | §13 | yes | `TableNoCaption`, `TableNoId`, `TableMalformedId`, `TableDuplicateId`, `TableUnknownRef`, `TableRefOutsideSection`: yes |
| Some sentence refers to each table | §13 | yes; **whether that sentence explains the table is not** | `TableUnreferenced`: yes, for the reference only |
| A captioned figure's id is unique and kebab-case, and every `figureref` resolves | §10 | yes | `FigureNoCaption`, `FigureMalformedId`, `FigureDuplicateId`, `FigureUnknownRef`, `FigureRefOutsideSection`: yes |
| Some sentence refers to each captioned figure | §10 | yes; whether that sentence explains the figure is not | `FigureUnreferenced`: yes, for the reference only |
| A numbered equation's id is unique and kebab-case, and every `equationref` resolves | §12 | yes | `EquationMalformedId`, `EquationDuplicateId`, `EquationUnknownRef`, `EquationRefOutsideSection`, `EquationOrphanMarker`: yes |
| Some sentence refers to each numbered equation | §12 | yes; whether that sentence explains the equation is not | `EquationUnreferenced`: yes, for the reference only |
| Whether an equation should have been numbered at all | §12 | **no** | not checked: there is no mechanical proxy |
| A matrix with two or more columns is displayed, not set inline | §12 | yes | not checked: whether one overflows depends on the math font ([§12](writing-standards/mathematics.md#-what-is-checked-and-what-you-still-have-to-look-for)) |
| A URL is written as a `[text](https://…)` link rather than printed raw | §14 | yes | `BareUrl`: yes |
| A citekey is cited as a marker, never printed as the key itself | §16 | yes | `BareCitekey`: yes for a parsed key in prose (the repair is `[@key]`); no (`review`) for a key set as code, or one with no parsed PDF ([§16](#-16-a-citation-is-always-a-marker)) |
| A code line fits the page's column limit | §14 | yes | `WideCodeLine`: no (`review`): a wide line may be deliberate ([§14](writing-standards/page.md#-keep-a-code-block-inside-the-page)) |
| A heading does not state its own chapter number | §15 | yes | `ChapterSelfNumbered`, `.tex` units only: yes ([§15](#-15-a-heading-does-not-number-itself)) |
| A very long token has a breakable form | §14 | yes | not checked: the proxy found no repair that was not a worse word ([§14](writing-standards/page.md#-prefer-a-breakable-form-for-a-very-long-token)) |
| The reread as the reader | §6 | no | never |

**How to read the last column.** A named rule is a `python -m
chitragupta.draft style` finding, reported as `chitragupta.<name>`. Each
finding carries a `repair` value. `edit`, the default,
lets the review agenda mark it `unattended`, so `agenda-reviser` may
repair it without asking; `review` puts it in front of a person. Only
these cases are `review`: `WideCodeLine`, `AcronymCase`, and a dialect
finding whose dialect came from `config.toml` or whose match starts with
a capital letter. `review synthesis` and `review uncited`
are review aids: they report, and no unattended repair acts on them.

**Nothing in the last column is a continuous score, deliberately.** A
readability index is the obvious candidate to add. A loop minimising
grade level splits sentences past the point the argument
survives, and replaces precise technical vocabulary with shorter, vaguer
words, because a polysyllabic term is indistinguishable to the metric
from bad writing.

An index may be reported but never optimised;
[HOUSE-STYLE.md](HOUSE-STYLE.md) has that argument in full.

**Quoted spans are exempt from every row.** Drafts produced by this
pipeline contain source text by construction, so "simply" inside a
quoted abstract and an `-ize` inside a cited title are correct rather
than findings. No rule here has a zero-exception form, which is also why
none of them may become a gate; see [ARCHITECTURE.md](ARCHITECTURE.md)'s
"Layer 4" for the axis that decides which checks may block, and
[SOUL.md](../SOUL.md) for why there is exactly one that does.

**The case of an acronym's expansion is authoritative.** The value in
`content/acronyms.toml` is the case a draft uses mid-sentence. A
capitalised value (`UML = "Unified Modeling Language"`) is a proper name.
A lower-case value (`SCADA = "supervisory control and data
acquisition"`) is a common noun, which is capitalised only where a
sentence, a line or a heading begins. `AcronymCase` reports the other
cases as `review`, and `dossier acronyms-suggest` reminds you of the rule
when it proposes entries. Write the vocabulary's case once and the
drafts follow it.

**Exceptions are declared, never guessed.** A term no prose rule should
report goes in `content/style_exceptions.toml`, a `terms` list that
applies to every draft in the project under every dialect. A term there
suppresses a prose finding that lies inside it, whole-word and ignoring
case, and the verbatim scan treats it like an allowlist phrase
([PLAGIARISM.md](PLAGIARISM.md#-the-boilerplate-allowlist)). Every
acronym expansion in the vocabulary counts as a term already, so list
only the rest. The one finding it never hides is `Acronyms`: a term
covering "Unified Modeling Language (UML)" must not excuse an unexpanded
`UML` elsewhere. The file is project data meant to be versioned with the
project; a missing file means no terms, and a malformed one is an
error, so a broken file cannot quietly turn suppressed findings back
into unattended edits.

**Every verdict in the table is scoped to English**, for the reason §8
gives.

## 📐 10. Figures

Moved, under the same number, to
[`docs/writing-standards/figures.md`](writing-standards/figures.md) §10:
a figure's originality, its two forms, its marker, its caption and the
number it never carries.

## 🧩 11. Multi-source synthesis, at your genre's unit

Prose that has to fuse two or more sources cannot be a transcription of
any one of them. You cannot transcribe two sources simultaneously. That
is a stronger mechanism than any instruction to paraphrase harder,
because it removes the opportunity instead of asking for restraint.

**The rule.** A unit cites **two or more citekeys wherever the evidence
set allows**, and a single-source unit is a deliberate choice you state
rather than a default.

**The unit differs by genre. The rule does not.**

| Genre | Unit | What that means |
| --- | --- | --- |
| `survey`, `thesis-chapter`, `deep-research`, `research-paper` | paragraph | A body paragraph closes on more than one citekey. In a research paper that binds the related work; a paragraph about the author's own software cites nothing and is not a finding |
| `textbook-chapter` | section | A section's citations span two or more citekeys, *and do not arrive in blocks* (see below). Individual paragraphs are free to be single-source; multi-source paragraphs are a distraction in a genre whose job is explanation |
| `tutorial` | document | The body carries no citations at all, by design. The floor is on the lesson's derivation: it must not be a walkthrough of one source's procedure, and two or more distinct citekeys in "Where to go next" are the evidence that it is not |
| `digest` | paragraph | As in a survey: a body paragraph braids copied runs from two or more papers. Each *run* is one source's own words, closed by its citation ([VERBATIM-DIGEST.md](VERBATIM-DIGEST.md)), so the paragraph is where a digest stops being a transcription of one paper |

**For the section unit, spread is not enough.** A section that cites
three papers by running one out before starting the next spans three
sources and fuses none of them; every paragraph in it is still a
candidate transcription. Interleave instead: don't let consecutive
paragraphs rest on the same single citekey. This is the same instruction
`textbook-chapter-writer` step 4 already gives, stated as a property of
the finished section rather than as advice about searching.

**Declaring a single-source unit.** Sometimes one paper is the
only source in the corpus for a point. That is fine, and forcing a
second citation where none fits is worse than the problem. Say so, in
the draft, immediately above or below the unit with **no blank line**
between them:

```markdown
<!-- single-source: Foo2019 is the only paper in the corpus covering X -->
```

```latex
% single-source: Foo2019 is the only paper in the corpus covering X
```

Both are invisible when rendered. A marker separated from its unit by a
blank line declares nothing; it becomes a block of its own.

`python -m chitragupta.review synthesis <draft>` counts citekeys per
unit, at the unit your genre binds at, and separates declared
single-source units from undeclared ones. It is **advisory**: it exits 0
whatever it finds, it blocks no draft, and a thin corpus legitimately
produces single-source units. There is no target proportion to drive
down, because a number a loop optimises stops measuring what it named
([AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)'s R3). A human reads the
report and decides.

The idea is adapted from [OpenScholar](https://github.com/AkariAsai/OpenScholar)'s
own drafting instruction, credited in [INSPIRATION.md](INSPIRATION.md)
and written here in our own words. Its *citation mechanics* are
deliberately not adapted: upstream cites by positional index into a
truncated list, so reordering that list silently changes what every
citation means. This project has real citekeys and keeps using them.

## 🔢 12. Mathematics

Moved, under the same number, to
[`docs/writing-standards/mathematics.md`](writing-standards/mathematics.md)
§12: the mapped and inline forms, what `render` checks, the meaning of
each mapped symbol, numbered equations and the prose around them.

### 📖 Symbols: what each mapped symbol means

Moved with §12, to
[its heading in `mathematics.md`](writing-standards/mathematics.md#-symbols-what-each-mapped-symbol-means).

## 🔢 13. Tables

Moved, under the same number, to
[`docs/writing-standards/tables.md`](writing-standards/tables.md) §13:
a table's caption and id, the `.tex` fragment's own form, and the
sentence that reads the table.

## 📄 14. What has to fit the page

Moved, under the same number, to
[`docs/writing-standards/page.md`](writing-standards/page.md) §14:
links rather than printed URLs, code blocks kept inside the page, and
breakable forms for very long tokens.

## 🔢 15. A heading does not number itself

The same rule §10, §12 and §13 already state for a figure, an equation
and a table, applied to the heading above them: **write the title, not
the number**. A unit is a chapter of something, and the something
numbers it: `\chapter` in an assembled book, the reader's own thesis
for a fragment. A heading that states its own number is printed twice,
once by each.

A unit headed `# Chapter 1: Why Anyone Pays` in a book set with the
`book` class opens

```text
Chapter 1

Chapter 1: Why Anyone Pays
```

and its table of contents reads `1 Chapter 1: Why Anyone Pays` to match.

**For a Markdown unit this is handled for you, and the heading stays
yours.** `python -m chitragupta.draft render --fragment` drops a
`Chapter N:` prefix from the `\chapter{}` it emits, so the book prints
the number once, from the class. The authored heading is untouched: a
unit rendered on its own has nothing supplying a chapter number, so the
prefix is what titles that standalone pdf, and the two artefacts want
opposite things from one line. There is nothing to repair and nothing is
reported.

**For a `.tex` unit it is yours to fix**, and it is the one heading
`python -m chitragupta.draft style` reports
(`chitragupta.ChapterSelfNumbered`, `chitragupta/style_headings.py`). A
unit already drafted as `.tex` needs no conversion to be assembled, so
it is `\input` exactly as written and no render runs over it. This is
the same carve-out §13's `.tex` fragment has for its tables, read the other way
round. Delete the prefix; the enclosing document supplies it.

**A self-numbered *section* is a different clash with a different
remedy.** `## 1.0 Before you start` under LaTeX's own numbering renders
"1.1 1.0 Before you start", and nothing above touches it. The fix is
`\setcounter{secnumdepth}{-2}` in the book's authored preamble, which is
a decision about the whole document. [WRITE-A-BOOK.md](WRITE-A-BOOK.md)
has what that costs and when it is the wrong lever.

## 🔖 16. A citation is always a marker

A cited paper is written as its citation marker, `[@key]` (`\citep{key}`
in a `.tex` fragment), and never as its citekey. Citations render in IEEE
style, so a paper used as a noun is still the marker: "In [@key], the
authors measure ..." renders as "In [3], the authors measure ...". A key
written without its `@` ("the frameworks gil_survey_2024 evaluates") or
set as code prints raw, and no reader can resolve it.

A sentence that is about the corpus rather than the subject, such as "the
corpus holds a duplicate entry for this paper", is not for the reader at
all. It belongs in the dossier's `revisions.md`.

`draft style` reports both as `BareCitekey`, reading only what a reader
sees: not the References section's key labels, comments, code blocks or
the citations themselves. A parsed key in prose is repaired unattended to
`[@key]`. A key set as code, or one whose PDF never parsed (which may not
be cited at all), is left to a person.

## 📖 Sources and attribution

Three openly licensed works supply the principles above, and three more
supply the pedagogy of `textbook-chapter-writer` and the book structure of
`book-assembler`. All six require attribution under their licences; this
section is that attribution. A seventh work, Wilkes's, supplies ideas only
and is credited after them.

1. **Daniele Procida, *Diátaxis: A systematic approach to technical
   documentation authoring***. <https://diataxis.fr/>; source repository
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
   <https://pressbooks.bccampus.ca/technicalwriting/>. §7.7 "Writing
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

4. **Greg Wilson, *Teaching Tech Together***, online edition.
   <https://teachtogether.tech/>; source repository
   <https://github.com/gvwilson/teachtogether.tech>. Licensed
   CC-BY-NC 4.0, not CC-BY: the NonCommercial clause binds copies and
   adaptations of the text, so this pipeline takes the ideas only and none
   of the text (see "What is original here" below).
   Supplies, for `textbook-chapter-writer`: backward design (objectives
   and assessments before content); learner personas; chunking to 7±2,
   or 4±1, items; concept maps; worked examples, then faded ones, with
   labelled subgoals; a formative check every 10 to 15 minutes; the
   catalogue of exercise types; the expertise-reversal effect; concrete
   instances before the general rule ("Expertise and Memory").

5. **The Carpentries, *Lesson Development Training***.
   <https://carpentries.github.io/lesson-development-training/>; source
   repository <https://github.com/carpentries/lesson-development-training>.
   Licensed CC-BY 4.0 ("Materials licensed under CC-BY 4.0 by the
   authors"). It replaces the retired *Curriculum Development Handbook*.
   Supplies, for `textbook-chapter-writer`: the lesson-design procedure;
   objectives written with an observable verb, two to four per episode;
   the questions-and-key-points frame around an episode; a worked example
   before the exercise that practises it; a check after every 15 to 20
   minutes of teaching; the accessibility checks.

6. **Lauri M. Aesoph, *Self-Publishing Guide***, BCcampus, 2018, chapter
   "Textbook Outline".
   <https://opentextbc.ca/selfpublishguide/chapter/textbook-outline/>.
   Licensed CC BY 4.0. The page notes that its front- and back-matter
   tables draw partly on Wikipedia's "Book design" (CC BY-SA 3.0), which
   is therefore credited transitively.
   Supplies, for `book-assembler` and `textbook-chapter-writer`: the
   front-matter, chapter-element and back-matter tables, which are where
   a book's front matter, appendices and back matter (#1137) come from.

**Ideas, not text, from one further work.** Gareth Wilkes, *A Brief
Guide to Mathematical Writing*, Department of Pure Mathematics and
Mathematical Statistics, University of Cambridge, revised 2023-10-08.
The guide states no licence, so nothing from it is quoted and none of its
examples is reused; the credit is given because the ideas are its.
Supplies, for §12's prose rules in
`.claude/skills-common/references/mathematical-prose.md`:
defining a symbol in its own sentence with a role word, and repeating the
role word on reuse; choosing letters by mnemonic and alphabet region, and
never overloading one (§2 "Notation and definitions"); writing the
"then", keeping the argument linear, checking a result's conditions
before applying it, and keeping diagrams for objects (§1 "General
tips"); stating the claim before a proof and a concluding sentence
after, one step per paragraph (§3 "Formatting and structuring
proofs"). `textbook-chapter-writer` reads that reference for a
maths-heavy chapter, so its symbol-definition and notation discipline is
Wilkes's too.

### 💡 What is original here

The prose in this file, in every `.claude/skills/*/SKILL.md` and in
`.claude/skills-common/references/` is written from scratch. A verbatim
n-gram check against the first three licensed sources above
(107,272 words of source; the algorithm is `chitragupta/review/verbatim_check/_overlap.py`'s
`cmd_overlap`) reports **0% overlap at an 8-word threshold**, and nothing
above five consecutive shared words anywhere. What is borrowed is the
*ideas*, credited above; what is added is their translation into
operational rules for this pipeline's six genres, the decision about which
principles transfer across genres and which do not (§5's warning), and the
handling of failure modes specific to multi-agent drafting.

Wilkes's guide (about 5,700 words) was checked the same way against this
file and `mathematical-prose.md` on 2026-11-05: no run of seven or more
words is shared with either, and the only six-word run is the guide's
own title, cited above.

Sources 4 to 6, and Wilkes's guide again, were checked on 2026-11-05
(#1129) against this file, `textbook-chapter-writer`'s and
`book-assembler`'s `SKILL.md`, `book-assembler`'s `references/` and
`assets/`, and every file in `.claude/skills-common/references/`. The
method is `cmd_overlap`'s: lowercase, keep `[a-z0-9]+` runs as words,
and compare 8-word shingles, here as the share of this side's 28,527
shingles found in the source. *Teaching Tech Together* was read from the
English LaTeX source in its repository (commit `0abb340`, commands
stripped; 72,644 words), *Lesson Development Training* from its
repository's episodes and index (commit `2bc8daf`; 26,408 words), and
"Textbook Outline" from the published page (1,755 words with its page
navigation). Every source reports **0% at the 8-word threshold**. The
longest shared run is six words for *Teaching Tech Together* and for
Wilkes, and both are citations in this section: the repository URL and
the guide's title. The other two sources share no run longer than five
words, and those are stock phrases ("at the end of the") or licence
names.

The element files under `docs/writing-standards/` were cut from this
file unchanged after these checks ran, so where a check above names
this file, it covers their text as it stood on the date given.

# ✍ Writing standards for the drafting layer

Status: **reference.**

**Written for** anyone drafting with this pipeline, and for the skills
that draft on their behalf. **Assumed:** [GENRE.md](GENRE.md) for which
skill does what. **Not covered here:** the prose standard this
repository's *own* documentation is held to, which is
[HOUSE-STYLE.md](HOUSE-STYLE.md).

Shared prose standards for every skill in `.claude/skills/`. Each
drafting and revising SKILL.md points here rather than restating them;
the rules specific to one genre are in that genre's file under
`writing-standards/genres/`.

They are drawn from [Diátaxis](https://diataxis.fr/), Google's
[Technical Writing courses](https://developers.google.com/tech-writing),
and Suzan Last's *Technical Writing Essentials* (BCcampus), credited in
[INSPIRATION.md](INSPIRATION.md#-the-writing-standards-sources). What follows
is the part that transfers across all six genres. **Diátaxis's
genre-specific rules do not all transfer**: "one path, no options" is
right for `tutorial-writer` and wrong for `survey-writer`, where weighing
alternatives *is* the deliverable. Take the structural rules only from
your own genre's file and SKILL.md.

## 🗂 The index: which file holds which rule

The standards are this file, the core, and the files under
`docs/writing-standards/`: an element file per thing a draft can
contain, a genre file per genre, and a style file per house style.

| Layer | File | Sections | Holds |
| --- | --- | --- | --- |
| Core | this file | §1–9, §11, §15, §16 | the rules every draft follows |
| Element | [`writing-standards/figures.md`](writing-standards/figures.md) | §10 | figures, checked by `chitragupta/style_figures.py` |
| Element | [`writing-standards/mathematics.md`](writing-standards/mathematics.md) | §12 | mathematics, checked by `chitragupta/style_equations.py` and `render` |
| Element | [`writing-standards/tables.md`](writing-standards/tables.md) | §13 | tables, checked by `chitragupta/style_tables.py` |
| Element | [`writing-standards/page.md`](writing-standards/page.md) | §14 | what has to fit the page, checked by `chitragupta/style_typeset.py` |
| Genre | [`writing-standards/genres/README.md`](writing-standards/genres/README.md) | none | the genre files, one per genre |
| Genre | [`writing-standards/genres/survey.md`](writing-standards/genres/survey.md) | none | the survey's obligations and reread |
| Genre | [`writing-standards/genres/deep-research.md`](writing-standards/genres/deep-research.md) | none | the deep-research report's obligations and reread |
| Genre | [`writing-standards/genres/digest.md`](writing-standards/genres/digest.md) | none | the verbatim digest's obligations and reread |
| Genre | [`writing-standards/genres/tutorial.md`](writing-standards/genres/tutorial.md) | none | the tutorial's obligations, where it may cite, and its reread |
| Genre | [`writing-standards/genres/textbook-chapter.md`](writing-standards/genres/textbook-chapter.md) | none | the textbook chapter's obligations, house style and reread |
| Genre | [`writing-standards/genres/thesis-chapter.md`](writing-standards/genres/thesis-chapter.md) | none | the thesis chapter's obligations and reread |
| Style | [`writing-standards/styles/README.md`](writing-standards/styles/README.md) | none | house styles to come; no style yet |

Section numbers are global and never reused: a section that moves out
of the core keeps its number, and the core keeps a stub heading with
the same emoji, number and title, so every anchor and §N citation still
lands. Each layer file assumes the core's §1–9 and repeats no other
file's text. `tests/test_writing_standards_layers.py` fails on a file
missing from the table, a cited section no heading carries, an anchor no
heading produces, or a number heading two sections. Where sources of
guidance disagree, the order is: the citekey invariant; the venue (a
research paper's `paper.md`); these standards, unless a recorded
conflict in a dossier's `style.md` is resolved to `profile`.

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
reader is assumed to know already, so a reader can tell whether they are
equipped for it.

## 🖋 4. Sentence-level craft

*Source: Google, Technical Writing One (short sentences, active voice,
consistent terms, defining terms once); Last, TWE §2.2 "Communicating with
Precision" and §7.7 "Writing Style" on the passive-voice failure. The
concrete-instance rule, which `textbook-chapter-writer` leans on hardest,
is Wilson's, TTT "Expertise and Memory", and the Carpentries' (a worked
example before the exercise that practises it). The habits of
machine-written prose are humanizer's, after Wikipedia's "Signs of AI
writing"; see
[INSPIRATION.md](INSPIRATION.md#-the-writing-standards-sources).*

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
- Cut words that add only emphasis or length: "very", a cliché, hype
  ("novel", "groundbreaking"), a stock phrase with a shorter form ("in
  order to" is "to"), and "serves as" where "is" will do.
- Report a number as it was measured. Give an exact p-value from 0.001
  up, write "p < 0.001" rather than "p = 0.000", keep one case for *p*,
  put a space between a number and its unit, and use the unit's symbol.

**Habits of machine-written prose.** A language model reaches for a few
moves that a careful writer makes only on purpose. Each one signals
weight or completeness without adding a fact, so when you find one,
rewrite the sentence around its claim rather than patching the phrase:

- A contrast whose negative half denies something no reader believed:
  "not just a cache but a coordination layer", including the version
  split over two sentences ("X is not the goal. Y is."). Keep a contrast
  when the reader really does hold the view it rejects.
- A line that closes a paragraph by repeating its point ("That
  distinction matters."), and a closing "In conclusion" or "Overall"
  that restates a verdict already given.
- A run-up before the point ("Here's the thing", "Let's break this
  down"), and a saying that only sounds deep ("At its core", "The real
  question is").
- A reply to an objection nobody raised ("This is not to say that ...",
  "One might be tempted to ...").
- Three items because three sounds complete, and a run of sentences that
  open the same way. Keep three when the meaning has three.
- Importance asserted instead of shown ("plays a pivotal role", "a
  testament to"), and an authority with no name ("experts argue"). The
  second is an uncited claim: name the source and cite it, or cut it.
- A statement of what is not known followed by a guess ("based on
  available information, it was likely ..."). Say what the sources do
  not show, as §7 asks, and stop there.
- A heading repeated as the first sentence under it.

Leave these be in a quotation, a title or a proper name, and where the
text talks about the phrase instead of using it.

## ✂ 5. Don't let a document do two jobs

*Source: Procida, Diátaxis: the four-quadrant model and its claim that
each kind of documentation "needs to be written in a different way".*

A document that tries to be both a survey and a tutorial is worse at
each, because the two have opposite obligations: a survey must weigh
alternatives, a tutorial must eliminate every choice.

If, while drafting, you find yourself writing material that belongs to a
different genre, **stop and say so to the user** rather than absorbing it.
The routing line or table in each genre SKILL.md ("When to invoke", or
"What this genre is not" in `tutorial-writer`) exists for this case.

## 👓 6. Read it once as the reader

*Source: Last, TWE §7.7, which names as a requirement of effective
instructions the "willingness to test your instructions on the kind of
person you wrote them for".*

Before presenting anything, reread the draft as the reader defined in §1,
not as yourself. Flag every point where a term arrives undefined, a step
skips reasoning, notation changes meaning mid-document, or a claim assumes
something never established.

This pass catches more real problems than any other single step. It
stands in for a usability test with a real reader, which a drafting run
cannot hold, so read the whole draft a second time; do not skim it.

## ❓ 7. Say what you don't know

Every genre here shares one rule from AGENTS.md's citekey invariant: a gap
stated plainly is always better than a gap papered over. Thin corpus
coverage, an unresolved contradiction, a step you couldn't verify: report
each of these to the user in prose instead of smoothing it over.

The same holds inside the draft. A result "shows" or "supports" a claim;
only a proof proves one. Call a difference significant only beside the
test that makes it so. And never leave a `TODO`, a `[cite]` or a `??`
standing in for a gap: say in prose what is missing.

## 🗣 8. Dialect and house style

A draft is written in one dialect of English, and which one is a fact
about the reader rather than a habit of the writer. A thesis submitted at
an Indian university is en-IN or en-GB; an IEEE submission is en-US; a
European funder's deliverable is usually en-GB. Settle it in §1, with the
reader, and record it as the `language:` line in the dossier's `scope.md`
(a BCP-47 tag, so `en-GB`, not "British").

A preference stated in chat is gone by the next session; `draft-reviser`
reads `scope.md` before any edit, so a tag on disk reaches every later
revision.

One dialect per draft, and it governs the draft's *own* prose. Quoted
material keeps its source's spelling, and so do a cited title, a proper
noun, and a dataset or code identifier: changing those is a misquotation,
not a correction.

A dialect match that starts with a capital letter is reported for a
person to decide, since "Modeling" in "Unified Modeling Language" is a
name. Declare the name in `content/style_exceptions.toml` ([§9](#-9-what-is-checked-mechanically-and-what-is-not))
and it stops being reported.

Record a venue's house style (serial comma, "Section 3" or "§3",
caption form) beside the dialect, rather than re-deciding it section by
section.

§2's defect markers and §4's voice rules are English conventions; a
draft in another language needs them adapted, not transliterated.

## ✅ 9. What is checked mechanically, and what is not

Some rules above have a decidable answer and some do not, and putting a
rule on the wrong side fails either way: mechanising §4's "short
sentences" over-splits sentences, and leaving §2's literals to memory
means they are rarely checked.

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
| Hedging that carries no information | §4 | detectable for fixed phrases only | `proselint.Hedging` (three fixed phrases, "so to speak") and `ai-tells.StackedHedges` (a doubled hedge, "could potentially"): no (`review`). A single modal is never flagged, since a research claim uses one deliberately |
| No emphasis or length that adds nothing: "very", clichés, hype, stock phrases with a shorter form, needless variants, malapropisms, non-words | §4 | yes, for a fixed list | proselint, `Journals.Hype`, `Microsoft.Wordiness`, `Plurals`, `Uppercase`, `chitragupta.PlainVerbs` (listed in `assets/vale/README.md`): no (`review`) |
| A number reported as measured: exact p-values, one case for *p*, units spaced and in symbols, "et al." | §4 | yes | `Journals.PValueZero`, `PValueCase`, `UnitSpacing`, `UnitSymbols`, `EtAl`, `PLOS.PValues`: no (`review`) |
| Habits of machine-written prose | §4 | detectable for fixed phrases; the split contrast, the repeated closer and the forced triad are not | ai-tells' formula rules and `chitragupta.RunUp`, `Strawman`, `DeepSaying`, `Inflated`, `BorrowedAuthority`: no (`review`) |
| A claim no stronger than its evidence, and no placeholder for a gap | §7 | detectable for fixed words | `Journals.Prove`, `Significant`, `Placeholder`, `chitragupta.KnowledgeLimit`: no (`review`) |
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
chitragupta.draft style` finding, reported as `chitragupta.<name>`, or
as `<package>.<name>` for a rule vendored from a third-party Vale package
(its message ends with the section it implements), with a `repair`
value. `edit`, the default for the house rules, lets the review agenda
mark it `unattended`, so `agenda-reviser` may repair it without asking;
`review` puts it in front of a person. A vendored rule is always
`review`, and words two rules both report are reported once
(`assets/vale/README.md` has which rule wins).
`review synthesis` and `review uncited` are review aids: they report,
and no unattended repair acts on them.

**Nothing in the last column is a continuous score, deliberately.** A
loop minimising a readability index splits sentences past the point the
argument survives and swaps precise terms for vaguer ones. An index may
be reported but never optimised ([HOUSE-STYLE.md](HOUSE-STYLE.md)).

**Quoted spans are exempt from every row**: "simply" inside a quoted
abstract and an `-ize` inside a cited title are correct. That holds for a
block quotation and for a quotation inside a sentence (`"..."`, curly
quotes, or LaTeX's ``` ``...'' ```), except for the acronym rule, since an
expansion the reader saw inside a quotation still counts. No rule here
has a zero-exception form, which is also why none may become a gate
([ARCHITECTURE.md](ARCHITECTURE.md)'s "Layer 4";
[SOUL.md](../SOUL.md)).

**The case of an acronym's expansion is authoritative.** The value in
`content/acronyms.toml` is the case a draft uses mid-sentence. A
capitalised value (`UML = "Unified Modeling Language"`) is a proper name.
A lower-case value (`SCADA = "supervisory control and data
acquisition"`) is a common noun, capitalised only where a sentence, a
line or a heading begins. `AcronymCase` reports the other cases as
`review`.

**Exceptions are declared, never guessed.** A term no prose rule should
report goes in `content/style_exceptions.toml`, a `terms` list that
applies to every draft in the project under every dialect. A term there
suppresses a prose finding that lies inside it, whole-word and ignoring
case, and the verbatim scan treats it like an allowlist phrase
([PLAGIARISM.md](PLAGIARISM.md#-the-boilerplate-allowlist)). Acronym
expansions in the vocabulary count as terms already. It never hides an
`Acronyms` finding. A missing file means no terms, and a malformed one
is an error, so a broken file cannot turn suppressed findings back into
unattended edits.

**Every verdict in the table is scoped to English**, for the reason §8
gives.

## 📐 10. Figures

Moved, under the same number, to
[`docs/writing-standards/figures.md`](writing-standards/figures.md) §10:
a figure's originality, its two forms, its marker, its caption and the
number it never carries.

## 🧩 11. Multi-source synthesis, at your genre's unit

Prose that fuses two or more sources cannot be a transcription of any
one of them. That removes the opportunity to copy instead of asking for
restraint.

**The rule.** A unit cites **two or more citekeys wherever the evidence
set allows**, and a single-source unit is a deliberate choice you state
rather than a default.

**The unit differs by genre. The rule does not.**

| Genre | Unit | What that means |
| --- | --- | --- |
| `survey`, `thesis-chapter`, `deep-research`, `research-paper` | paragraph | A body paragraph closes on more than one citekey. In a research paper that binds the related work; a paragraph about the author's own software cites nothing and is not a finding |
| `textbook-chapter` | section | A section's citations span two or more citekeys, *and do not arrive in blocks* (see below). Single-source paragraphs are fine in a genre whose job is explanation |
| `tutorial` | document | The body carries no citations at all, by design. The floor is on the lesson's derivation: it must not be a walkthrough of one source's procedure, and two or more distinct citekeys in "Where to go next" are the evidence that it is not |
| `digest` | paragraph | As in a survey: a body paragraph braids copied runs from two or more papers, each *run* closed by its citation ([VERBATIM-DIGEST.md](VERBATIM-DIGEST.md)) |

**For the section unit, spread is not enough.** A section that runs
out one paper before starting the next fuses none of them. Interleave
instead: don't let consecutive
paragraphs rest on the same single citekey.

**Declaring a single-source unit.** When one paper is the only source
in the corpus for a point, forcing a second citation is worse. Say so,
immediately above or below the unit with **no blank line** between
them:

```markdown
<!-- single-source: Foo2019 is the only paper in the corpus covering X -->
```

```latex
% single-source: Foo2019 is the only paper in the corpus covering X
```

Both are invisible when rendered. A marker separated from its unit by a
blank line declares nothing.

`python -m chitragupta.review synthesis <draft>` counts citekeys per
unit, at the unit your genre binds at, and separates declared
single-source units from undeclared ones. It is **advisory**: it exits 0
and blocks no draft. There is no target proportion to drive down
([AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)'s R3); a human reads the
report and decides.

The idea is adapted from
[OpenScholar](https://github.com/AkariAsai/OpenScholar)'s drafting
instruction. Its *citation mechanics* are deliberately not adapted:
upstream cites by positional index into a truncated list, so reordering
the list silently changes every citation. This project keeps real
citekeys.

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
the number**. The enclosing document numbers a unit, so a heading
that states its own number prints it twice. A unit headed
`# Chapter 1: Why Anyone Pays` in a `book`-class book opens

```text
Chapter 1

Chapter 1: Why Anyone Pays
```

and its table of contents reads `1 Chapter 1: Why Anyone Pays` to match.

**For a Markdown unit this is handled for you.** `python -m
chitragupta.draft render --fragment` drops a `Chapter N:` prefix from
the `\chapter{}` it emits; the authored heading is untouched, because a
unit rendered alone needs the prefix as its title. Nothing is reported.

**For a `.tex` unit it is yours to fix**, and it is the one heading
`python -m chitragupta.draft style` reports
(`chitragupta.ChapterSelfNumbered`, `chitragupta/style_headings.py`),
because a `.tex` unit is `\input` exactly as written. Delete the prefix.

**A self-numbered *section* is a different clash.** `## 1.0 Before you
start` renders "1.1 1.0 Before you start"; the fix is
`\setcounter{secnumdepth}{-2}` in the book's preamble, a whole-document
decision [WRITE-A-BOOK.md](WRITE-A-BOOK.md) discusses.

## 🔖 16. A citation is always a marker

A cited paper is written as its citation marker, `[@key]` (`\citep{key}`
in a `.tex` fragment), and never as its citekey. Citations render in IEEE
style, so a paper used as a noun is still the marker: "In [@key], the
authors measure ..." renders as "In [3], the authors measure ...". A key
written without its `@` ("the frameworks gil_survey_2024 evaluates") or
set as code prints raw, and no reader can resolve it.

A sentence about the corpus rather than the subject ("the corpus holds
a duplicate entry for this paper") belongs in the dossier's
`revisions.md`, not the draft.

`draft style` reports both as `BareCitekey`, reading only what a reader
sees. A parsed key in prose is repaired unattended to `[@key]`; a key
set as code, or one whose PDF never parsed, is left to a person.

# ✍ Writing standards for the drafting layer

Status: **reference.** Written 2026-08-03. Updated 2026-08-26.

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

## 👥 1. Decide the audience before drafting

*Source: Google, Technical Writing One ("Just enough writing" / audience
analysis); Last, TWE §7.7 "Do a careful audience and task analysis".*

Write down -- in working notes, not necessarily in the document -- who the
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

## 📏 3. State scope up front

*Source: Last, TWE §7.7, whose introduction checklist asks for the scope --
"what will and will not be covered" -- and the reader's assumed background.*

Say what the document covers, what it deliberately does not, and what the
reader is assumed to know already. A reader who can't tell whether they're
equipped for a document will either bounce off it or waste an hour finding
out they were missing background.

## 🖋 4. Sentence-level craft

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

## ✂ 5. Don't let a document do two jobs

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

## 👓 6. Read it once as the reader

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

## ❓ 7. Say what you don't know

Every genre here shares one rule from AGENTS.md's citekey invariant: a gap
stated plainly is always better than a gap papered over. Thin corpus
coverage, an unresolved contradiction, a step you couldn't verify -- all of
these get reported to the user in prose. None of them get smoothed.

## 🗣 8. Dialect and house style

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

## ✅ 9. What is checked mechanically, and what is not

Some rules above have a decidable answer and some do not. The split
matters in both directions, and getting it wrong fails in opposite ways.
Mechanising §4's "short sentences" builds a machine that splits sentences
past the point the argument survives. Leaving §2's literals to memory
means they are checked only when someone remembers to.

| Rule | Section | Decidable? | May a machine act on it unattended? |
| --- | --- | --- | --- |
| Dialect matches `scope.md`'s `language:` | §8 | yes | yes |
| No defect markers: "obviously", "simply", "of course", "clearly", "easy" | §2 | yes | yes |
| "just", specifically | §2 | no | no -- the adverb ("just add the flag") and the adjective ("a just outcome") are not separable by string match, so it is reported for a human eye |
| Each term defined once, then used consistently | §2 | yes, given the dossier's glossary | yes |
| Acronym expanded at first use, then not re-expanded | §2 | yes -- first occurrence is computable | yes |
| A glossary's acronym expansion still matches the current acronym vocabulary | §2 | yes, given the dossier's glossary and `[style].acronyms` -- but only the glossary is compared, not the draft's own prose | yes |
| Active voice with a named actor | §4 | detectable | no -- the fix is a judgement |
| Each paragraph leads with its point | §4 | heuristic only | no -- surfaced, never applied |
| Hedging that carries no information | §4 | detectable | no -- the fix is a judgement |
| Short sentences, one idea each | §4 | **no: this is a score** | no |
| Citekeys per unit, and how many units rest on one source | §11 | yes | no -- it is a **proportion**, and a thin corpus legitimately produces single-source units. Counted and read, never acted on |
| Whether a sentence carries a citation at all | §11 | yes, per sentence -- but *whether it needs one* is not, which is why the genre decides if it is a finding | no -- surfaced. The fix for an uncited claim is evidence, not wording, and a machine rewording one would make it look supported without making it supported |
| A table has a caption and an id, and every reference resolves | §13 | yes | no -- the fix is a caption someone has to write |
| Some sentence refers to each table | §13 | yes | no -- and **whether that sentence explains the table is not decidable at all**, which is the half that matters most. A machine can see that a reference exists; only a reader can see that the arrangement was worth making |
| A captioned figure's id is unique and kebab-case, and every `figureref` resolves | §10 | yes | no -- the fix is an author decision, same as a table's |
| Some sentence refers to each captioned figure | §10 | yes | no -- and **whether that sentence explains the figure is not decidable**, same split as a table's. An uncaptioned figure raises `chitragupta.FigureNoCaption` instead, so it is not exempt from §10, only from *this* row -- there is nothing yet for a sentence to refer to |
| A numbered equation's id is unique and kebab-case, and every `equationref` resolves | §12 | yes | no -- the fix is an author decision, same as a table's or figure's |
| Some sentence refers to each numbered equation | §12 | yes | no -- and **whether that sentence explains the equation is not decidable**, same split as a table's or figure's |
| Whether an equation should have been numbered at all -- standalone, final-of-derivation, reused | §12 | **no** | no -- unlike every other row in this table, there is no mechanical proxy for this one at all; only the reference half above is checked |
| A URL is written as a `[text](https://…)` link rather than printed raw | §14 | yes | yes -- the repair is the link, which is wording, and there is no evidential claim for it to misrepresent |
| A code line fits the page's column limit | §14 | yes | yes today, inherited from the `prose` class rather than argued for this rule -- and it is the row where that inheritance is worth re-examining, because the repair edits a code sample rather than prose, and dropping an argument to fit the width leaves a command that still reads plausibly and no longer works. In a Markdown draft the stake is only the `,→` a wrap leaves behind; in a `.tex` fragment, whose preamble this pipeline may not touch, it is a real overflow |
| A very long token has a breakable form | §14 | yes | **no, and it is not checked at all** -- unlike every other row, the mechanical proxy was built and then rejected: TeX hyphenates long English words correctly, so the rule raised 36 candidates on this project's own book and none of them had a repair that was not a worse word. §14 has the measurement |
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

## 📐 10. Figures

A draft may include a figure only if it is wholly original. A figure
extracted from a source paper carries that paper's own copyright, and
citing the paper grants no right to reproduce it -- inserting one into a
draft, or closely redrawing one from memory, is the same violation in
different pixels. Reading a source figure for understanding is fine; the
boundary is what ends up in the draft.

A figure's ASCII form is a diagram in a code block -- box characters,
arrows and labels built from `+ - | / \ > < ^ v`, 7-bit characters only.
Keep it to about 70 columns so it survives the rendered PDF's monospace
block without wrapping.

A code block, not specifically a fenced one. In a Markdown draft you
write a fence and the `md` render keeps it. Where the renderer inlines
the ASCII form into a `.tex`-sourced `.md` preview, pandoc emits a
4-space indented block instead -- verified, and it is the shape to
expect rather than a defect: every line is shifted by the same four
spaces, so the diagram's alignment is intact and `^ \ < >` come through
literally.

Unicode box-drawing (`┌─┐│└─┘`) is excluded, not merely discouraged:
this pipeline renders PDF with `pdflatex`, which does not have those
glyphs set up and fails the whole render with `Unicode character ┌
(U+250C) not set up for use with LaTeX` -- verified against this
project's own `render_output` call, not a general pandoc claim. A
diagram that renders one figure and breaks every other one downstream
in the same draft is worse than no diagram.

### 🎨 TikZ layout and style

[TIKZ-STYLE.md](TIKZ-STYLE.md) is the full guide to drawing a good TikZ
figure: which layout metaphor to commit to before placing a node, the
pre-flight defect checklist to check the result against, and the type
and line-weight conventions that keep a figure consistent with the
surrounding document. It is a checklist an author checks a figure
against, not a gate -- nothing in it is enforced mechanically today.

### 🖼 Every figure has two forms

ASCII is what a Markdown reader should see; it is not what a thesis
wants. So a figure in this pipeline exists twice -- once as a TikZ
picture, which sets as vector art at the consuming document's own font
and line width, and once as the plain-ASCII diagram above.

**Both forms are always sibling files, in every genre, and a draft
carries only a marker naming them** -- with one exception, and it is not
about figures. `thesis-chapter-writer`'s `.tex` fragment is what the user
`\input`s directly into their own real thesis, never touched by this
pipeline again once it leaves `content/drafts/`; a marker-only TikZ would
render fine through this pipeline's own renderer and then silently vanish
the moment the user does the one thing that genre exists for. So that
genre's TikZ stays inline, via the `\input` a real thesis resolves for
itself; its ASCII, like every other form in every other genre, is a file
named by a marker.

```text
content/drafts/<topic>/<draft>.md          marker only
content/drafts/<topic>/figures/<name>.tex  the TikZ picture   (every genre)
content/drafts/<topic>/figures/<name>.txt  the ASCII form     (every genre)

content/drafts/<topic>/<draft>.tex         TikZ inline, via \input   (thesis-chapter-writer only)
content/drafts/<topic>/figures/<name>.tex  the TikZ picture
content/drafts/<topic>/figures/<name>.txt  the ASCII form
```

**A topic directory is mandatory for a draft that carries a figure.** A
flat `content/drafts/<slug>.md` puts its figures in
`content/drafts/figures/`, shared with every other flat draft, where two
drafts that each name a figure `fig1` silently overwrite each other in
`content/rendered/`. Each genre skill settles the draft's path at the
start of its process, before a figure is on anyone's mind; deciding on a
figure later is a reason to move the draft and its dossier, not a reason
to `mkdir` beside a flat one.

Every draft names both forms with a marker comment -- `thesis-chapter-writer`
additionally keeps its TikZ inline, for the reason above, but still marks
its ASCII the same way everyone else marks both. The marker is what lets
a reader of the draft see that a form exists off the page, and what lets
a reviser find every figure by `grep` rather than by parsing the draft.

**One marker, one vocabulary, in both genres: `figure:`, naming the
figure's base name without a suffix.** The renderer derives `<base>.tex`
and `<base>.txt` from it. The two spellings below differ only because a
comment in Markdown and a comment in LaTeX are written differently --
the thing you write, and the rule you remember, is the same either way,
and no draft ever names one figure twice.

**Markdown drafts** -- `tutorial-writer`, `textbook-chapter-writer`,
`survey-writer` -- carry the marker alone, with no fence beside it:

```html
<!-- figure: figures/<name> -->
```

For `--format tex` and `--format pdf` the renderer replaces that marker
with `\input{figures/<name>.tex}`. For every other format, including the
Markdown draft's own `--format md`, it replaces the marker with the
`.txt` contents in a fence -- there is no inline diagram left to fall
back on, so this substitution runs even when the output format matches
the draft's own language.

**The `.tex` draft** -- `thesis-chapter-writer`, this pipeline's one
LaTeX-sourced genre -- keeps its TikZ inline, via the `\input` a real
thesis resolves for itself, with the ASCII marker following it:

```latex
\input{figures/<name>.tex}
%figure: figures/<name>
```

For `--format md` the renderer substitutes the `.txt` contents for that
`\input`, in a temp copy. Writing a `verbatim` block by hand is not the
author's job here: the fragment on disk stays exactly what the user
`\input`s into their own thesis, and the ASCII appears only in the
preview that needs it.

**The marker must be a comment, never a second `\input`.** A literal
`\input{figures/<name>.txt}` makes pdflatex read the ASCII art *as LaTeX
source*, and the alphabet above is full of math-mode-only characters:

```text
! Missing $ inserted.        exit=1
```

That failure lands in the user's own thesis build, where we never see
it -- our own render substitutes the line away first. A LaTeX comment is
inert to pdflatex, dropped by pandoc, and meaningful only to this
pipeline.

### 🎯 What the pair requires

- **Both forms, or no figure.** A figure is not finished until both
  sibling files exist and the marker is in the draft. A pair with a
  missing half renders in one format and disappears in the other, and a
  draft that refers in prose to a figure the reader cannot see is worse
  than one with no figure at all.
- **The TikZ form is in colour; the ASCII form is not, and that is
  accepted.** Figures here use a house palette
  ([TIKZ-STYLE.md](TIKZ-STYLE.md)), and the 7-bit twin cannot reproduce
  it -- `md`, `docx` and `html` render only the twin. The pair contract
  is therefore about the *point*, not the pixels: **both forms must work
  as figures, and they need not carry the same secondary distinctions.**
  Keep the argument legible through position, arrow direction and
  labels, which the twin can express, and let colour make the picture
  quick to read rather than possible to read.
- **Originality binds the TikZ identically.** A TikZ picture redrawn
  from a source paper's figure is the same violation in different
  pixels, and that a vector redraw is easier to produce than a traced
  bitmap changes nothing about whose figure it is. Reading a source
  figure for understanding is fine; the boundary is the same one as
  above.
- **No figure number inside a figure file either, and for the same
  reason.** The renderer assigns every number
  ([below](#-a-caption-and-no-number-you-write-yourself)), so a literal
  "Figure 3" written into a node label or a `\node` caption inside
  `figures/<name>.tex` is a second, unmanaged number that nothing
  renumbers and nothing checks -- it survives into the PDF beside the
  real one. The rule generalises: **the artifact carries the picture,
  the document carries its identity.**
- **No citekeys inside a figure file.** `python -m chitragupta.draft gate` reads
  the draft and does not follow `\input`, so a citekey in a node label
  or a caption inside `figures/<name>.tex` is invisible to the one check
  standing between this pipeline and a fabricated reference. Cite in the
  draft's prose, where the gate can see it. This is stated and not
  gated, deliberately: `docs/CODE-STANDARDS.md` keeps `chitragupta.draft gate`
  as the project's only gate, meaning exactly one thing -- a fabricated
  citekey fails -- and giving it a second meaning would blunt the first.
- **Verify the TikZ compiles before keeping it.** A figure that does not
  compile fails the *whole* pdf render, not just the figure. Probe
  `kpsewhich tikz.sty` first; if it is absent, write only the ASCII form
  and no marker, and say so in chat. Do this at drafting time: a marker
  written on a host without `tikz.sty` makes every later `tex`/`pdf`
  render of that draft fail with `[missing-binary]`, because the
  renderer refuses rather than silently falling back -- the same draft
  has to produce the same output on every host. If it is present, wrap the figure
  in a minimal `\documentclass{article}` + `\usepackage{tikz}` document,
  run `pdflatex` on it, and never keep one that fails. **Copy the
  figure's own `\usetikzlibrary` line into that probe**, or the check
  fails for a reason the figure does not have: the probe preamble loads
  no library, exactly as the renderer's does not, so anything using
  `positioning`, `matrix`, `fit` or `tree` errors there whether or not
  it is sound. [TIKZ-STYLE.md](TIKZ-STYLE.md) says where that line goes
  and why the figure file has to carry it.
- **Plain 7-bit ASCII in the ASCII form**, wherever it lives, same
  alphabet and same reasoning as the Unicode exclusion above. It is
  what every non-LaTeX render emits, and a draft with no TikZ figure at
  all still renders its fence straight into the pdf -- which is exactly
  the run where one Unicode box character takes the whole document down
  with it.
- **Panels are lettered, in both forms, however many there are.** A
  figure showing the same thing under several conditions is one figure
  with panels -- one marker, one pair, whatever the count -- and each
  panel carries a sub-caption reading `(<letter>) <short title>`, where
  the letter is the panel's place in reading order: `(a)` for the first,
  `(b)` for the second, on through the alphabet. The letters have to be
  in the ASCII form too, and not
  as a decoration: every format except `tex`/`pdf` renders the `.txt`
  and never sees the picture, so a figure lettered only in its TikZ
  ships a `docx` and an `html` whose panels are unlabelled, with nothing
  anywhere reporting it. [TIKZ-STYLE.md](TIKZ-STYLE.md) has the worked
  example, how to letter an ASCII diagram without sliding every title
  off its panel, and why `subcaption` is not the answer.
- **A figure is captioned in the draft, not in the figure file** --
  "A caption, and no number you write yourself" below has the contract.
  A marker with no caption below it still renders unnumbered and
  uncaptioned -- the renderer is unchanged -- but `draft style` now
  reports it (`chitragupta.FigureNoCaption`), because "captioned in the
  draft" is the contract and a marker without one has not met it.
  Which lettering a venue wants for panels -- `(a)`,
  `(i)`, `A`, or titles with no letters -- is a §8 house-style decision:
  record it in the dossier's `scope.md` beside the dialect, where
  `draft-reviser` reads it before every edit, rather than settling it
  again per figure.

### 🔖 A caption, and no number you write yourself

Issue 411 gives a figure the number-and-reference contract §13 gives a
table. A Markdown draft writes the `figure:` marker, then its caption
directly below it -- no blank line between, the same adjacency §11's
`<!-- single-source: -->` and §13's own caption-then-marker pair both
use:

```markdown
<!-- figure: figures/delivery-modes -->
One reading path under three delivery modes.
```

Prose points at it with an inline marker, which stands in for the whole
reference phrase -- the author writes neither the word "Figure" nor a
number:

```markdown
<!-- figureref: delivery-modes --> shows the same request handled three ways.
```

**The id is derived, not written.** The marker's own value already names
the figure's base name, so the id is that name with no `figures/` prefix
-- `delivery-modes` from `figures/delivery-modes`, the same base name
`\label{fig:delivery-modes}` already had to agree with before this
contract existed. There is no second field to keep in sync with the file
name.

**A figure with no caption line below it renders unchanged** -- a bare
`\input` or a bare ASCII fence, no float, no number, and invisible to
`figureref` resolution. What changed in issue 421 is that this is no
longer an *accepted* case: the render is the same, and `draft style`
now reports it. Nothing about the rendering path moved, which is worth
saying plainly, because the amendment is to the standard rather than to
the renderer.

**Never write the number.** [RENDERING-FLOW.md](RENDERING-FLOW.md)'s
"Figure numbering" has the per-format cases: LaTeX-bound output wraps
the marker in a real `figure` float and lets LaTeX's own counter number
it -- no `\renewcommand{\thefigure}` is ever written -- and every other
format gets a number counted at render time, exactly mirroring how §13
numbers a table outside LaTeX.

The `.tex` fragment carries neither marker: `thesis-chapter-writer`
hand-authors a real `\begin{figure}...\caption{}...\label{fig:<id>}`
around its inline `\input`, the same carve-out §13 gives a hand-written
`\begin{table}`. The one thing that changes there too: never write
`\renewcommand{\thefigure}{N.M}`. The consuming thesis's own counter is
what has to agree with its own chapter numbering, which is the whole
reason a number never belongs in a draft.

`python -m chitragupta.draft style` reports the decidable part of this --
a figure marker carrying no caption, a captioned figure no sentence
refers to, a `figureref` naming a figure that does not exist or is not
captioned, two figures sharing one id, and a reference sitting outside
the figure's own section.

`chitragupta.FigureNoCaption` arrived with issue 421 and reversed what
this paragraph used to say. There is still no `FigureNoId`, and that
half is unchanged rather than merely surviving: a figure marker always
carries an id by construction, since the id *is* the base name the
marker names, so there is no state for it to catch.

Where `tikz.sty` is absent, the fallback is the same in every genre and
is what this section required before the pair existed: the ASCII goes
inline, in whatever form the draft's own language carries natively -- a
fenced code block in a Markdown draft, a `verbatim` environment in a
`.tex` fragment -- with no marker and no `figures/` files at all. Both
forms survive every format such a host can produce: a fence renders
straight through Markdown's own formats and, via pandoc, into `tex`/`pdf`
too; a `verbatim` block survives pandoc's LaTeX reader into both
`--format pdf` and `--format md` -- verified through this pipeline's
actual render path both ways.

This is not gated mechanically -- there is no equivalent of
`citation_gate` for a figure's originality. Whether a diagram is
genuinely original, and whether a source figure's own licence would
even permit reproducing it, stays a judgement call. Nor is there one for
agreement between the two forms: nothing can check that a TikZ picture
and an ASCII diagram depict the same thing, so a revision that edits one
and not the other leaves the pdf and the Markdown preview disagreeing,
silently and indefinitely. `draft-reviser` carries the only defence
there is -- touch a figure, touch both forms, panel letters included.

## 🧩 11. Multi-source synthesis, at your genre's unit

Prose that has to fuse two or more sources cannot be a transcription of
any one of them. You cannot transcribe two sources simultaneously. That
is a stronger mechanism than any instruction to paraphrase harder,
because it does not ask for restraint -- it removes the opportunity.

**The rule.** A unit cites **two or more citekeys wherever the evidence
set allows**, and a single-source unit is a deliberate choice you state
rather than a default.

**The unit differs by genre. The rule does not.**

| Genre | Unit | What that means |
| --- | --- | --- |
| `survey`, `thesis-chapter`, `deep-research` | paragraph | A body paragraph closes on more than one citekey |
| `textbook-chapter` | section | A section's citations span two or more citekeys, *and do not arrive in blocks* -- see below. Individual paragraphs are free to be single-source; multi-source paragraphs are a distraction in a genre whose job is explanation |
| `tutorial` | document | The body carries no citations at all, by design. The floor is on the lesson's derivation: it must not be a walkthrough of one source's procedure, and two or more distinct citekeys in "Where to go next" are the evidence that it is not |

**For the section unit, spread is not enough.** A section that cites
three papers by running one out before starting the next spans three
sources and fuses none of them; every paragraph in it is still a
candidate transcription. Interleave instead: don't let consecutive
paragraphs rest on the same single citekey. This is the same instruction
`textbook-chapter-writer` step 4 already gives, stated as a property of
the finished section rather than as advice about searching.

**Declaring a single-source unit.** Sometimes one paper genuinely is the
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
blank line declares nothing -- it becomes a block of its own.

**What checks this, and what it will not do.** `python -m
chitragupta.review synthesis <draft>` counts citekeys per unit, at the
unit your genre binds at, and separates declared single-source units
from undeclared ones. It is **advisory**: it exits 0 whatever it finds,
it blocks no draft, and a thin corpus legitimately produces
single-source units. There is no target proportion to drive down --
[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)'s R3 is why, and it is not a
technicality: a number a loop optimises stops measuring what it named.
A human reads it and decides.

The idea is adapted from [OpenScholar](https://github.com/AkariAsai/OpenScholar)'s
own drafting instruction, credited in [INSPIRATION.md](INSPIRATION.md)
and written here in our own words. Its *citation mechanics* are
deliberately not adapted: upstream cites by positional index into a
truncated list, so reordering that list silently changes what every
citation means. This project has real citekeys and keeps using them.

## 🔢 12. Mathematics

**A quantity is never left as a bare code span. Backticks mean code, and
only code.** There are two ways to honour that, and a Markdown draft may
use either -- but only one of them per quantity, and consistently.

| | In the draft | Where the LaTeX lives |
| --- | --- | --- |
| **Mapped** (preferred for a new draft) | `` `k = 4` ``, ASCII | the dossier's `math.md` |
| **Inline** | `$k = 4$` / `$$…$$` | the draft itself |

A `.tex` draft -- `thesis-chapter-writer`'s -- writes `\(…\)` and `\[…\]`
directly and has no third option; the rest of this section still applies
to it.

This needs stating because the failure is invisible in the draft and
only appears downstream. Pandoc's Markdown reader turns a code span into
`\texttt{}` and escapes its spaces, so an unhandled `` `k = 4` `` becomes
`\texttt{k\ =\ 4}` in the rendered LaTeX -- upright, typewriter, with
`=` set as ordinary text -- while a real equation two paragraphs earlier
becomes `\[…\]`. Both look plausible in the Markdown source. Only the pdf
shows that the same symbol has been set two ways.

### 🗺 The mapped form, and why it is preferred

`$k = 4$` fixes the pdf and costs the Markdown. `--format md` never
reaches pandoc ([RENDERING-FLOW.md](RENDERING-FLOW.md)), so those
delimiters land verbatim in `content/rendered/` -- fine where the
Markdown is a step towards a pdf, wrong where somebody reads it.

The mapped form keeps the draft ASCII and puts the LaTeX in the
dossier's `math.md` ([DOSSIER.md](DOSSIER.md)):

```markdown
| ASCII in the draft | LaTeX |
| --- | --- |
| `k = 4`          | `k = 4` |
| `tau`            | `\tau` |
| `dW/dt = -W/tau` | `\frac{dW}{dt} = -\frac{W}{\tau}` |
```

`render` substitutes those into a temp copy for every format that reaches
pandoc, so `tex`, `pdf` and the rest get real mathematics while
`--format md` is a byte-perfect no-op. **The key is the span already in
the draft**, so nothing new is invented and nothing is guessed: a span
with a row is a quantity because the mapping says so, and `as_of` stays
code because it has no row.

A **displayed** equation is an untagged fence with a `<!-- math -->`
marker on the line above:

````markdown
<!-- math -->
```
dW/dt = -W/tau
```
````

The marker, not a ```` ```math ```` tag, for two reasons: GitHub and
GitLab typeset a `math`-tagged fence as LaTeX, so ASCII inside one is
rendered wrongly there; and every other fence in a draft holds code, so
something has to say which is which. It is the same device as
[§10's figure marker](#-10-figures), for the same reason -- inert to
pdflatex, dropped by pandoc, meaningful only to this pipeline.

**A marker with no row is a hard error, not a warning.** `render` exits
non-zero, because a marker is you stating that a displayed equation is
here, and rendering it as verbatim text is the whole defect this section
exists to prevent. A missing `math.md` for a draft that has markers
usually means the draft was renamed and its dossier did not follow: the
two are tied by path alone and there is no `dossier rename`.

### 📐 The rule in practice

Written below in the inline spelling; in the mapped form the same rules
govern the mapping's LaTeX column, which is the only place LaTeX appears.

- **A symbol is math wherever it appears.** If `\[ m(t) = m_0 - k\,t \]`
  defines `k`, then every later mention of it is a quantity too -- `$k$`,
  or `` `k` `` with a row. What is never right is a bare `` `k` `` with
  no row, and that is the shape a check cannot see from punctuation
  alone: `render` closes the world instead, flagging any span equal to a
  symbol your own mapped equations already use.
- **One form per draft.** Do not mix `$k$` in one section with a mapped
  `` `k` `` in another; a reader diffing two sections cannot tell whether
  the difference is deliberate.
- **Arithmetic is math too.** `$12 \times 2 \times 365 = 8{,}760$`, not
  `` `12 x 2 x 365 = 8,760` ``. ASCII `x` and `*` are not multiplication
  signs, and a thousands comma needs `{,}` or LaTeX sets it as a
  punctuation comma with the wrong spacing after it.
- **An equation is never a fenced code block.** A fence means code
  exactly as backticks do, and pandoc sets it as `\begin{verbatim}` --
  upright, monospace, `x` still a letter. A displayed equation is the
  marker plus fence above, or `$$…$$`; a *symbol legend* is a list, with
  each symbol set as math like every other mention of it. **A fence
  inside a blockquote is still a fence**, which is where the occurrence
  that prompted this was hiding (#406): one relation, set three ways in
  one chapter, and the fenced one was the odd one out.
- **A text subscript is upright.** `$k_\mathrm{day}$`, not `$k_{day}$` --
  the latter sets *d*, *a*, *y* as three italic variables multiplied
  together.
- **Backticks keep everything they were always for**: field names
  (`as_of`, `event_time`), endpoints, filenames, literal values,
  identifiers. A parameter named in an API *and* used in an equation is
  the genuinely ambiguous case; pick by which role the sentence is
  playing, and be consistent within the section.
- **Dates, versions and timestamps are not math.** `2026-02-01` in math
  mode sets its hyphens as minus signs.
- **A literal dollar sign must be escaped** (`\$`) once a draft uses
  `$…$`, or it opens math mode and swallows the rest of the paragraph.

### ⚖ Which form to choose

**A new draft should use the mapped form**, unless nobody will ever read
its `.md`. The inline form is not deprecated and needs no migration: a
draft already written with `$…$` keeps rendering exactly as it did, and
`_math.py` only ever touches a span that has a row.

Pick the inline form when the draft is a step on the way to a pdf and
the equation count is small -- one `$k$` is cheaper than a dossier file.
Pick the mapped form when the Markdown is read, when there are enough
equations that a table earns its keep, or when the ASCII should read
naturally: `` `t = tau * ln(2)` `` maps to `t = \tau \ln 2`, so the
source stays legible while the LaTeX stays typographically right.
Neither is a compromise, which is the point of holding both.

### 🔍 What is checked, and what you still have to look for

**Two certain things stop a render** (`render` exits non-zero): a
`<!-- math -->` marker with no row to resolve it, and a marker with no
mapping file at all. Both mean the pdf would carry verbatim text where
you said an equation goes.

**Three heuristics only warn**, because a wrong guess must not stop a
render: a span that looks like a quantity (`h = 9`) with no row, a span
equal to a symbol your own mapped equations already use, and an untagged
fence that looks like a displayed equation nobody marked. The second is
there because the first cannot see a bare `` `k` `` -- there is no
operator to key on -- and single symbols were the *dominant* shape when
this was measured, roughly 296 of 515 in one book.

The third names both remedies, because a bare fence leaves the question
open in both directions: mark it if it is an equation, tag it if it is
code. It fires on a fence of **at most four lines** holding an operator
and no underscore identifier -- `as_of` and `predicted_next` are code,
and length is what separates an equation from the other thing a bare
fence holds, an [§10 figure](#-10-figures), whose box borders are not
math-shaped but whose `->` arrows are. Measured over every untagged
fence in this repository's own drafts, the genuine equations run one to
four lines and the shortest false positive is a seven-line pseudocode
listing.

**Still not gated, deliberately.** `python -m chitragupta.draft gate`
means exactly one thing -- a fabricated citekey fails -- and
[docs/CODE-STANDARDS.md](CODE-STANDARDS.md) keeps it that way. `render`
refusing is a different thing from the gate, and refuses only what is
certain.

**What no check sees.** A quantity spelled out -- `slope`, `offset`,
`Assemble(N)` -- reads like an identifier, so unless it has a row it
looks like ordinary code to everything above. So does any expression
containing `/`, to a search written to skip file paths. And a draft using
the *inline* form has no mapping to close the world against, so it gets
the operator heuristic only. All three really happened in this
repository's own book; `plans/math-typesetting-convention.md` records
what each cost.

A long aligned array in an *unmarked* fence is past the four-line bar and
goes unreported too -- deliberately, since that is the shape whose marker
is worth writing by hand. And nothing here reads a rendered `.tex`: a
post-render grep for math-shaped `\texttt{}` is what reported this book
clean while a `\begin{verbatim}` equation sat in it, because a fence
never becomes a `\texttt{}`.

### 🔢 A number for a chosen few, not for every displayed equation

A table or a figure earns a number simply by existing; a displayed
equation does not. Numbering every step of a derivation is noise, so
this section leaves the choice to the author -- unlike everything else
`render` checks in this section, **nothing here can decide which
equations deserve one**. What follows is guidance for making that call,
not a rule a program executes.

Number an equation when:

- it is **standalone** -- not one step among several leading somewhere
  else;
- it is the **final result of a derivation or a chain of logically
  continuous equations** -- the steps that lead to it are not numbered,
  only the one that was proved;
- it is **reused by a later equation** -- substituted into it, referred
  back to -- regardless of the two rules above.

Every equation numbered by any of the three rules above must then be
**referenced and explained in the prose**. This is the one part of the
decision a machine can check: `chitragupta.EquationUnreferenced` reports a
numbered equation no sentence points at, the same way
`chitragupta.TableUnreferenced` does for §13. That a sentence *refers to*
a numbered equation is decidable; that the sentence *explains* it is not,
same as a table's or a figure's row in §9's table below.

An equation opts into a number with `<!-- equation: id -->` directly
above the `<!-- math -->` marker this section already uses:

````markdown
<!-- equation: energy -->
<!-- math -->
```
E = m * c^2
```
````

and prose reads it with `<!-- equationref: id -->`, mirroring §10's
`figureref` and §13's `tableref`:

```markdown
Substituting <!-- equationref: energy --> into the momentum relation
gives the result used throughout this section.
```

**Ids are kebab-case and unique within a draft**, the same rule §10 and
§13 state for a figure or table id. **Numbers are never written by an
author** -- assigned by document order of `equation:` markers, the same
reasoning §13 gives for a table: document order is LaTeX's own counting
order, so the number this pipeline writes for `md`/`docx` and the number
LaTeX assigns for `pdf` point at the same equation. Unlike a table's
caption, an equation carries no number in the *draft* on either path --
only in what each format renders to.

**A marked equation gets a number in every rendered format, `md`
included** -- matching the table/figure precedent above rather than this
section's own "the `md` path is a no-op" rule. That rule still holds for
an equation's *content*: the ASCII inside a marked fence is exactly as
untouched on the `md` path as an unmarked one always was. It does not
hold for the *number*: a marked equation gains a `**Equation N:**` label
there, the same way a table already gains `**Table N:**`. This is a
deliberate, narrow exception -- content substitution is still gated on a
real `math.md` mapping; equation numbering is not, and runs
unconditionally the way a table's or figure's numbering already does.

An unmarked `<!-- math -->` block -- a derivation step, or any equation
the author chose not to number -- is untouched by every check in this
subsection. There is no finding for "this equation should have been
numbered and was not": that would require the tool to tell a standalone
result from an intermediate step, which nothing here can do.

## 🔢 13. Tables

A table is evidence arranged for comparison. It needs two things this
section is about: a **caption**, so the rendered document can number it,
and a **sentence that reads it**, so the reader is not left to work out
what the arrangement was for.

Neither was true of any draft this pipeline had produced before this
section existed. A survey's comparison table rendered as an unnumbered
`longtable`, and the string "Table" followed by a number appeared in no
draft's prose at all.

### 🏷 A caption, an id, and no number you write yourself

A Markdown draft writes the table, pandoc's own caption line, and an id
marker directly under it -- no blank line between the two, the same
adjacency §11's `<!-- single-source: -->` uses:

```markdown
| Starting point | Core idea | Stated limitation |
|---|---|---|
| DTaaS platform | One tenant-facing platform | Reuse needs components |

: Where to start when building a first twin.
<!-- table: start-here -->
```

Prose points at it with an inline marker, which stands in for the whole
reference phrase -- you write neither the word "Table" nor a number:

```markdown
The platforms in <!-- tableref: start-here --> differ mainly in what
they ask you to bring.
```

**Never write the number.** `: Table 1: Where to start.` renders as
"Table 1: Table 1: Where to start.", because LaTeX supplies its own
prefix; and a number typed into a chapter is wrong the moment that
chapter is assembled into a book, where the same table numbers "2.1" --
or something else again, since a book that suppresses chapter numbering
counts its tables flat from the front. `render` resolves both markers per format
([RENDERING-FLOW.md](RENDERING-FLOW.md) has the four cases): LaTeX-bound
output gets a `\label` and numbers itself, and every other format gets a
number counted at render time, because pandoc numbers nothing outside
LaTeX.

**The caption is visible text; only the id hides.** A caption may cite,
and `python -m chitragupta.draft gate` reads the draft -- so the caption
stays where a reader and the gate can both see it. The id is not prose
and nobody reads it, which is why it is the half in a comment.

**Ids are kebab-case and unique within a draft.** Two tables sharing one
id become two `\label{}`s in one LaTeX document, where a duplicate
resolves silently to the wrong table -- which is a real risk for a book
unit, since [BOOKS.md](BOOKS.md)'s assembly puts fifteen units in one
document.

### 📄 The `.tex` fragment writes its own

`thesis-chapter-writer` carries no marker. It writes a real LaTeX table
with its own `\caption` and `\label`, and refers to it with
`Table~\ref{tab:start-here}`:

```latex
\begin{table}
\caption{Where to start when building a first twin.}\label{tab:start-here}
\begin{tabular}{lll}
...
\end{tabular}
\end{table}
```

Same carve-out as §10's inline TikZ, and the same reason: that fragment
is `\input` into the user's own thesis, where their own `pdflatex`
numbers it consistently with their other chapters. Nothing this pipeline
does may get between them.

### 👓 The sentence that reads the table

A caption says what a table *is*. It does not say what it *shows*, and a
table dropped into a section with neither a lead-in nor a reading is
work handed to the reader.

- **Introduce it before it appears** -- what is being compared, and on
  what axis.
- **Read a pattern off it afterwards** -- the row that is the exception,
  the column where everything agrees, the trade-off the arrangement
  makes visible. If nothing can be read off it, the table is decoration.
- **Keep the reference beside the table.** A table in §6 whose only
  mention is in §2 is one the reader meets unannounced.
- **Say it once.** Prose that re-states every row is a table set twice;
  the point of the arrangement is that it does not need narrating.

`python -m chitragupta.draft style` reports the decidable part of this --
a table with no caption, no id, a duplicate id, a reference to a table
that does not exist, a table no sentence refers to, and a table
referenced only from another section. Whether the sentence that refers
to it actually *explains* it is a judgement, and stays one; §9's table
records the split.

## 📄 14. What has to fit the page

A draft is read on paper, or on a screen shaped like paper. Three
things run into the margin there and nowhere else, so they are invisible
until someone opens the PDF -- which is usually after the draft has been
reviewed.

### 🔗 Link the text, don't print the URL

Write **`[descriptive text](https://…)`**, not the URL itself. A bare URL is
worse on three counts: it reads as noise mid-sentence, it gives the PDF
nothing to click, and a long one is a single unbreakable token.

```markdown
See [the plant-controller repository](https://github.com/INTO-CPS-Association/plant-controller).
```

not

```markdown
See https://github.com/INTO-CPS-Association/plant-controller.
```

A code span that is *only* a URL counts as a bare one -- the monospace
font changes nothing about how it reads. A code span with a URL among
other tokens (`curl https://…`) is a command, and is left alone: making
it a link would corrupt the thing it prints.

### 📏 Keep a code block inside the page

**76 columns**, measured rather than chosen: at this project's book
geometry (11pt, 80pt margins) a `verbatim` line fits 79, and at `draft
render`'s own defaults (12pt, 1in margins) it fits 76. A draft may be
rendered either way, so the tighter one is the limit. Both numbers were
measured through pandoc's own template, which loads `lmodern` --
measuring against a bare `\documentclass` gives 76/73, three columns
tight, because Computer Modern's typewriter face is wider.

**A Markdown draft's blocks now wrap rather than overflow**, so this is
a quality rule rather than a defect one. `draft render` loads `fvextra`
and redefines `verbatim`/`Highlighting` with `breaklines` for any draft
that has a fenced block, so an over-wide line breaks at a space and
marks the continuation with `,→`. Keeping the line short avoids that
marker -- which a reader copying the command out of the pdf would
otherwise pick up.

**A `.tex` fragment is the case that still cannot be repaired**, and is
why the check exists at all. `thesis-chapter-writer` emits a fragment
`\input` into the user's own thesis, whose preamble this pipeline may
not touch (§13's carve-out) -- so nothing can load `fvextra` on its
behalf, and a wide `verbatim` line there runs into the margin exactly as
before. Shorten it: break the pipeline, drop the aligned comment column,
abbreviate the path.

A book is the third case: its units are rendered `--fragment`, which
emits no preamble, so its `book.tex` carries the `fvextra` load itself
-- see `.claude/skills/book-assembler/SKILL.md`.

### 🔤 Prefer a breakable form for a very long token

Where a choice exists, prefer a token under about **15 characters**, or
one with an internal `-`, `/` or `_` to break at.

**Guidance, with no check behind it, and the reason is worth stating.**
TeX hyphenates a long English word in a roman font perfectly well:
`interoperability` sets as `in-teroperability` even in a 4cm column, and
so does a camelCase identifier written in prose. Measured across this
project's own 428-page book, no prose word caused an overflow, and a
rule flagging every token over 15 characters raised 36 candidates --
`interoperability`, `indistinguishable`, `microcontrollers` -- none of
which has a repair that is not a worse word. So it stays advice to an
author choosing between two phrasings, and never becomes a finding. §9's
table records it beside the other row with no mechanical proxy.

`python -m chitragupta.draft style` reports the decidable part of this
section -- a bare URL, and a code line over the column limit. The
third rule is not checked, deliberately, per the paragraph above.

## 📖 Sources and attribution

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

### 💡 What is original here

The prose in this file and in every `.claude/skills/*/SKILL.md` is written
from scratch. A verbatim n-gram check against all three sources above
(107,272 words of source; the algorithm is `chitragupta/review/verbatim_check/_overlap.py`'s
`cmd_overlap`) reports **0% overlap at an 8-word threshold**, and nothing
above five consecutive shared words anywhere. What is borrowed is the
*ideas*, credited above; what is added is their translation into
operational rules for this pipeline's five genres, the decision about which
principles transfer across genres and which do not (§5's warning), and the
handling of failure modes specific to multi-agent drafting.

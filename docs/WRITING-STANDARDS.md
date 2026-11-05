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
Precision" and §7.7 "Writing Style" on the passive-voice failure.*

In a verbatim digest ([VERBATIM-DIGEST.md](VERBATIM-DIGEST.md)) these
rules bind the drafter's connecting sentences only; copied text keeps
its source's style.

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
| Dialect matches `scope.md`'s `language:` | §8 | yes | `DialectGB`/`DialectUS`/`DialectIN`: yes when the dialect came from `scope.md` or `--language`; no (`review`) when it came from `config.toml` |
| No defect markers: "obviously", "simply", "of course", "clearly", "easy" | §2 | yes | `DefectMarkers`: yes |
| "just", specifically | §2 | no: the adverb ("just add the flag") and the adjective ("a just outcome") are not separable by string match | `Just`: no (`review`). The finding asks which one it is; only the adverb is a defect, so a person decides |
| Each term defined once, then used consistently | §2 | yes, given the dossier's glossary | not checked for a plain term; only acronyms are (next two rows) |
| Acronym expanded at first use, then not re-expanded | §2 | yes: first occurrence is computable | `Acronyms`: yes |
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
| A matrix with two or more columns is displayed, not set inline | §12 | yes | not checked: whether one overflows depends on the math font ([§12](#-what-is-checked-and-what-you-still-have-to-look-for)) |
| A URL is written as a `[text](https://…)` link rather than printed raw | §14 | yes | `BareUrl`: yes |
| A citekey is cited as a marker, never printed as the key itself | §16 | yes | `BareCitekey`: yes for a parsed key in prose (the repair is `[@key]`); no (`review`) for a key set as code, or one with no parsed PDF ([§16](#-16-a-citation-is-always-a-marker)) |
| A code line fits the page's column limit | §14 | yes | `WideCodeLine`: no (`review`): a wide line may be deliberate ([§14](#-keep-a-code-block-inside-the-page)) |
| A heading does not state its own chapter number | §15 | yes | `ChapterSelfNumbered`, `.tex` units only: yes ([§15](#-15-a-heading-does-not-number-itself)) |
| A very long token has a breakable form | §14 | yes | not checked: the proxy found no repair that was not a worse word ([§14](#-prefer-a-breakable-form-for-a-very-long-token)) |
| The reread as the reader | §6 | no | never |

**How to read the last column.** A named rule is a `python -m
chitragupta.draft style` finding, reported as `chitragupta.<name>`. Each
finding carries a `repair` value. `edit`, the default,
lets the review agenda mark it `unattended`, so `agenda-reviser` may
repair it without asking; `review` puts it in front of a person. Only
two cases are `review`: `WideCodeLine`, and a dialect finding whose
dialect came from `config.toml`. `review synthesis` and `review uncited`
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

**Every verdict in the table is scoped to English**, for the reason §8
gives.

## 📐 10. Figures

A draft may include a figure only if it is wholly original. A figure
extracted from a source paper carries that paper's own copyright, and
citing the paper grants no right to reproduce it. Inserting one into a
draft, or closely redrawing one from memory, is the same violation.
Reading a source figure for understanding is fine; the boundary is
what ends up in the draft.

A figure's ASCII form is a diagram in a code block: box characters,
arrows and labels built from `+ - | / \ > < ^ v`, 7-bit characters only.
Keep it to about 70 columns so it survives the rendered PDF's monospace
block without wrapping.

A code block, not specifically a fenced one. In a Markdown draft you
write a fence and the `md` render keeps it. Where the renderer inlines
the ASCII form into a `.tex`-sourced `.md` preview, pandoc emits a
4-space indented block instead. That is verified, and it is the shape to
expect rather than a defect: every line is shifted by the same four
spaces, so the diagram's alignment is intact and `^ \ < >` come through
literally.

Unicode box-drawing (`┌─┐│└─┘`) is excluded.
chitragupta's own pdf render runs LuaLaTeX and prints them, but a
`.tex` output or a `--fragment` is compiled later by the author's own
document, and a `pdflatex` build has no such glyphs set up: it fails the
whole build with `Unicode character ┌ (U+250C) not set up for use with
LaTeX`. That is verified against a `pdflatex` build of this project's
own render output, and is not a general pandoc claim. One such diagram
breaks the build for every other figure in the same draft.

### 🎨 TikZ layout and style

[TIKZ-STYLE.md](TIKZ-STYLE.md) is the full guide to drawing a good TikZ
figure: which layout metaphor to commit to before placing a node, the
pre-flight defect checklist to check the result against, and the type
and line-weight conventions that keep a figure consistent with the
surrounding document. Much of it is checked by `chitragupta figure
check`, which reports and is never gated; the rules it applies, and how
to read its report, are in
[figure-checks/README.md](figure-checks/README.md).

### 🖼 Every figure has two forms

ASCII is what a Markdown reader should see; it is not what a thesis
wants. So a figure in this pipeline exists twice: once as a TikZ
picture, which sets as vector art at the consuming document's own font
and line width, and once as the plain-ASCII diagram above.

The `figure-drawer` skill draws both forms, for any genre that hands it
a figure and for a direct request ([FIGURE-DRAWER.md](FIGURE-DRAWER.md)).
This section is the contract it follows, and stays the contract for a
figure drawn by hand.

**Both forms are always sibling files, in every genre, and a draft
carries only a marker naming them**, with one exception, which is not
about figures. `thesis-chapter-writer`'s `.tex` fragment is what the user
`\input`s directly into their own real thesis, never touched by this
pipeline again once it leaves `content/drafts/`; a marker-only TikZ would
render fine through this pipeline's own renderer and then vanish without
warning when the user `\input`s the fragment into their thesis. So that
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

Every draft names both forms with a marker comment. `thesis-chapter-writer`
additionally keeps its TikZ inline, for the reason above, but still marks
its ASCII the same way everyone else marks both. The marker is what lets
a reader of the draft see that a form exists off the page, and what lets
a reviser find every figure by `grep` rather than by parsing the draft.

**One marker, one vocabulary, in both genres: `figure:`, naming the
figure's base name without a suffix.** The renderer derives `<base>.tex`
and `<base>.txt` from it. The two spellings below differ only because a
comment in Markdown and a comment in LaTeX are written differently; what
you write is the same either way, and no draft names one figure twice.

**Markdown drafts** (`tutorial-writer`, `textbook-chapter-writer`,
`survey-writer`) carry the marker alone, with no fence beside it:

```html
<!-- figure: figures/<name> -->
```

For `--format tex` and `--format pdf` the renderer replaces that marker
with `\input{figures/<name>.tex}`. For every other format, including the
Markdown draft's own `--format md`, it replaces the marker with the
`.txt` contents in a fence. There is no inline diagram left to fall
back on, so this substitution runs even when the output format matches
the draft's own language.

**The `.tex` draft** (`thesis-chapter-writer`, this pipeline's one
LaTeX-sourced genre) keeps its TikZ inline, via the `\input` a real
thesis resolves for itself, with the ASCII marker following it:

```latex
\input{figures/<name>.tex}
%figure: figures/<name>
```

For `--format md` the renderer substitutes the `.txt` contents for that
`\input`, in a temp copy. The author does not write a `verbatim` block
by hand: the fragment on disk stays exactly what the user
`\input`s into their own thesis, and the ASCII appears only in the
preview that needs it.

**The marker must be a comment, never a second `\input`.** A literal
`\input{figures/<name>.txt}` makes pdflatex read the ASCII art *as LaTeX
source*, and the alphabet above is full of math-mode-only characters:

```text
! Missing $ inserted.        exit=1
```

That failure lands in the user's own thesis build, where we never see
it, because our own render substitutes the line away first. A LaTeX comment is
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
  it; `md`, `docx` and `html` render only the twin. The pair contract
  therefore covers what the figure shows, not how it looks: **both forms
  must work as figures, and they need not carry the same secondary
  distinctions.**
  Keep the argument legible through position, arrow direction and
  labels, which the twin can express, and let colour make the picture
  quick to read rather than possible to read.
- **Originality binds the TikZ identically.** A TikZ picture redrawn
  from a source paper's figure is the same violation, and that a vector
  redraw is easier to produce than a traced
  bitmap changes nothing about whose figure it is. Reading a source
  figure for understanding is fine; the boundary is the same one as
  above.
- **No figure number inside a figure file either, and for the same
  reason.** The renderer assigns every number
  ([below](#-a-caption-and-no-number-you-write-yourself)), so a literal
  "Figure 3" written into a node label or a `\node` caption inside
  `figures/<name>.tex` is a second, unmanaged number that nothing
  renumbers and nothing checks; it survives into the PDF beside the
  real one. In general, **the figure file carries the picture and the
  draft carries its number and caption.**
- **No citekeys inside a figure file.** `python -m chitragupta.draft gate` reads
  the draft and does not follow `\input`, so a citekey in a node label
  or a caption inside `figures/<name>.tex` is invisible to the one check
  standing between this pipeline and a fabricated reference. Cite in the
  draft's prose, where the gate can see it. This is stated and not
  gated, deliberately: `docs/CODE-STANDARDS.md` keeps `chitragupta.draft gate`
  as the project's only gate, meaning exactly one thing (a fabricated
  citekey fails), and giving it a second meaning would blunt the first.
- **Verify the TikZ compiles before keeping it.** A figure that does not compile
  fails the *whole* pdf render, not just the figure. Probe `kpsewhich tikz.sty`
  first; if it is absent, write only the ASCII form and no marker, and say so in
  chat. Do this at drafting time: a marker written on a host without `tikz.sty`
  makes every later `tex`/`pdf` render of that draft fail with
  `[missing-binary]`, because the renderer refuses rather than silently falling
  back: the same draft has to produce the same output on every host. If it is
  present, run `chitragupta figure check figures/<name>.tex`. It compiles the
  figure under LuaLaTeX, the pdf render's engine, with the figure's own
  `\usetikzlibrary` libraries loaded in the preamble as the renderer loads
  them, and reports `does-not-compile` along with every other rule it
  measures. Never keep a figure that fails. `chitragupta figure look
  figures/<name>.tex` writes the figure cropped as it will print, for what no
  rule measures. [TIKZ-STYLE.md](TIKZ-STYLE.md) says where the
  `\usetikzlibrary` line goes in the figure file.
- **Plain 7-bit ASCII in the ASCII form**, wherever it lives, same
  alphabet and same reasoning as the Unicode exclusion above. It is
  what every non-LaTeX render emits, and a draft with no TikZ figure at
  all still renders its fence straight into the pdf, where one Unicode
  box character fails the whole document.
- **Panels are lettered, in both forms, however many there are.** A
  figure showing the same thing under several conditions is one figure
  with panels (one marker, one pair, whatever the count), and each
  panel carries a sub-caption reading `(<letter>) <short title>`, where
  the letter is the panel's place in reading order: `(a)` for the first,
  `(b)` for the second, on through the alphabet. The letters have to be
  in the ASCII form too: every format except `tex`/`pdf` renders the `.txt`
  and never sees the picture, so a figure lettered only in its TikZ
  ships a `docx` and an `html` whose panels are unlabelled. `figure
  check` reports that as `t3-panels`. [TIKZ-STYLE.md](TIKZ-STYLE.md) has the worked
  example, how to letter an ASCII diagram without sliding every title
  off its panel, and why `subcaption` is not the answer.
- **A figure is captioned in the draft, not in the figure file**;
  "A caption, and no number you write yourself" below has the contract.
  A marker with no caption below it renders unnumbered and uncaptioned,
  and `draft style` reports it (`chitragupta.FigureNoCaption`).
  Which lettering a venue wants for panels (`(a)`,
  `(i)`, `A`, or titles with no letters) is a §8 house-style decision:
  record it in the dossier's `scope.md` beside the dialect, where
  `draft-reviser` reads it before every edit, rather than settling it
  again per figure.

### 🔖 A caption, and no number you write yourself

A figure has the number-and-reference contract §13 gives a table. A
Markdown draft writes the `figure:` marker, then its caption
directly below it with no blank line between, the same adjacency §11's
`<!-- single-source: -->` and §13's own caption-then-marker pair both
use:

```markdown
<!-- figure: figures/delivery-modes -->
One reading path under three delivery modes.
```

Prose points at it with an inline marker, which stands in for the whole
reference phrase; the author writes neither the word "Figure" nor a
number:

```markdown
<!-- figureref: delivery-modes --> shows the same request handled three ways.
```

**The id is derived, not written.** The marker's own value already names
the figure's base name, so the id is that name with no `figures/` prefix:
`delivery-modes` from `figures/delivery-modes`, the same base name
`\label{fig:delivery-modes}` agrees with. There is no second field to
keep in sync with the file name.

**A figure with no caption line below it renders unchanged**: a bare
`\input` or a bare ASCII fence, no float, no number, and invisible to
`figureref` resolution. The renderer accepts it and the standard does
not: `draft style` reports it as `chitragupta.FigureNoCaption`.

**Never write the number.** [RENDERING-FLOW.md](RENDERING-FLOW.md)'s
"Figure numbering" has the per-format cases: LaTeX-bound output wraps
the marker in a real `figure` float and lets LaTeX's own counter number
it (no `\renewcommand{\thefigure}` is ever written), and every other
format gets a number counted at render time, mirroring how §13
numbers a table outside LaTeX.

The `.tex` fragment carries neither marker: `thesis-chapter-writer`
hand-authors a real `\begin{figure}...\caption{}...\label{fig:<id>}`
around its inline `\input`, the same carve-out §13 gives a hand-written
`\begin{table}`. There too, never write
`\renewcommand{\thefigure}{N.M}`: the consuming thesis's own counter has
to agree with its own chapter numbering, which is why a number never
belongs in a draft.

`python -m chitragupta.draft style` reports the decidable part of this:
a figure marker carrying no caption, a captioned figure no sentence
refers to, a `figureref` naming a figure that does not exist or is not
captioned, two figures sharing one id, and a reference sitting outside
the figure's own section.

There is no `FigureNoId`: a figure marker always carries an id by
construction, since the id *is* the base name the marker names, so
there is no state for it to catch.

Where `tikz.sty` is absent, the fallback is the same in every genre and
is the ASCII form alone: the ASCII goes
inline, in whatever form the draft's own language carries natively (a
fenced code block in a Markdown draft, a `verbatim` environment in a
`.tex` fragment), with no marker and no `figures/` files at all. Both
forms survive every format such a host can produce: a fence renders
straight through Markdown's own formats and, via pandoc, into `tex`/`pdf`
too; a `verbatim` block survives pandoc's LaTeX reader into both
`--format pdf` and `--format md`. Both were verified into both formats
through this pipeline's own render path.

There is no equivalent of `citation_gate` for a figure's originality.
Whether a diagram is original, and whether a source figure's own
licence would even permit reproducing it, stays a judgement call.

Agreement between the two forms is checked in part by `chitragupta
figure check`, which reports and is never gated. It reports a figure
with no `.txt` beside it (`twin-missing`), a name in the TikZ that the
twin does not carry (`t1-labels`), an edge tag missing from the twin
(`t2-tags`), and panel letters that differ between the two
(`t3-panels`). Arrow topology is not checked: nothing compares which
box an arrow joins in one form against the other, so a rewired arrow
leaves the pdf and the Markdown preview disagreeing until someone looks.
[figure-checks/README.md](figure-checks/README.md) has the rules.
`draft-reviser` carries the rest of the defence: touch a figure, touch
both forms, panel letters included.

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
| `survey`, `thesis-chapter`, `deep-research` | paragraph | A body paragraph closes on more than one citekey |
| `textbook-chapter` | section | A section's citations span two or more citekeys, *and do not arrive in blocks* (see below). Individual paragraphs are free to be single-source; multi-source paragraphs are a distraction in a genre whose job is explanation |
| `tutorial` | document | The body carries no citations at all, by design. The floor is on the lesson's derivation: it must not be a walkthrough of one source's procedure, and two or more distinct citekeys in "Where to go next" are the evidence that it is not |
| `digest` | document | Every run is one source's own words, closed by its citation ([VERBATIM-DIGEST.md](VERBATIM-DIGEST.md)). The rule has no paragraph to bind at: a digest is a transcription by design, and `python -m chitragupta.review digest` is the check that applies |

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

**A quantity is never left as a bare code span. Backticks mean code, and
only code.** There are two ways to honour that, and a Markdown draft may
use either, but only one of them per quantity, and consistently.

| | In the draft | Where the LaTeX lives |
| --- | --- | --- |
| **Mapped** (preferred for a new draft) | `` `k = 4` ``, ASCII | the dossier's `math.md` |
| **Inline** | `$k = 4$` / `$$…$$` | the draft itself |

A `.tex` draft (`thesis-chapter-writer`'s) writes `\(…\)` and `\[…\]`
directly and has no third option; the rest of this section still applies
to it.

The failure is invisible in the draft and appears only downstream.
Pandoc's Markdown reader turns a code span into `\texttt{}` and escapes
its spaces, so an unhandled `` `k = 4` `` becomes `\texttt{k\ =\ 4}` in
the rendered LaTeX (upright, typewriter, with `=` set as ordinary text),
while a real equation two paragraphs earlier becomes `\[…\]`. Both look
plausible in the Markdown source. Only the pdf shows that the same
symbol has been set two ways.

### 🗺 The mapped form, and why it is preferred

`$k = 4$` fixes the pdf and costs the Markdown. `--format md` never
reaches pandoc ([RENDERING-FLOW.md](RENDERING-FLOW.md)), so those
delimiters land verbatim in `content/rendered/`. That is fine where the
Markdown is a step towards a pdf, and wrong where somebody reads it.

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
[§10's figure marker](#-10-figures), for the same reason: inert to
pdflatex, dropped by pandoc, meaningful only to this pipeline.

**A marker with no row is a hard error, not a warning.** `render` exits
non-zero, because a marker is you stating that a displayed equation is
here, and rendering it as verbatim text is the defect this section exists to
prevent. A missing `math.md` for a draft that has markers
usually means the draft was renamed and its dossier did not follow: the
two are tied by path alone and there is no `dossier rename`.

### 📐 The rule in practice

Written below in the inline spelling; in the mapped form the same rules
govern the mapping's LaTeX column, which is the only place LaTeX appears.

- **A symbol is math wherever it appears.** If `\[ m(t) = m_0 - k\,t \]`
  defines `k`, then every later mention of it is a quantity too: `$k$`,
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
  exactly as backticks do, and pandoc sets it as `\begin{verbatim}`:
  upright, monospace, `x` still a letter. A displayed equation is the
  marker plus fence above, or `$$…$$`; a *symbol legend* is a list, with
  each symbol set as math like every other mention of it. **A fence
  inside a blockquote is still a fence**. The case that prompted this
  rule was one relation set three ways in one chapter, and the wrong one
  was a fence inside a blockquote.
- **A matrix with two or more columns is displayed, not set inline.** TeX
  cannot break a line inside `\begin{bmatrix}`, so an inline matrix is
  one box the paragraph has to fit around, and two in a sentence leave
  it nowhere to break. Write the marker and fence above, with both
  matrices on one line if the sentence names two. Set inline,
  `F = [1, 0; 0, 0.7]` and `G = [1.0e-4, 0; 0, 3.0e-4]` ran 58pt into
  the margin of this repository's own book. A short column
  vector such as `x = [1.70; 48.0]` is narrow enough to stay inline.
- **A text subscript is upright.** `$k_\mathrm{day}$`, not `$k_{day}$`;
  the latter sets *d*, *a*, *y* as three italic variables multiplied
  together.
- **Backticks keep everything they were always for**: field names
  (`as_of`, `event_time`), endpoints, filenames, literal values,
  identifiers. A parameter named in an API *and* used in an equation is
  the ambiguous case; pick by which role the sentence is
  playing, and be consistent within the section.
- **Dates, versions and timestamps are not math.** `2026-02-01` in math
  mode sets its hyphens as minus signs.
- **A literal dollar sign must be escaped** (`\$`) once a draft uses
  `$…$`, or it opens math mode and swallows the rest of the paragraph.

### ⚖ Which form to choose

**A new draft should use the mapped form**, unless nobody will ever read
its `.md`. Both forms are supported: a draft written with `$…$` renders
as written, and `_math.py` only ever touches a span that has a row.

Pick the inline form when the draft is a step on the way to a pdf and
the equation count is small: one `$k$` is cheaper than a dossier file.
Pick the mapped form when the Markdown is read, when there are enough
equations that a table earns its keep, or when the ASCII should read
naturally: `` `t = tau * ln(2)` `` maps to `t = \tau \ln 2`, so the
source stays legible while the LaTeX stays typographically right.

### 🔍 What is checked, and what you still have to look for

**Two certain things stop a render** (`render` exits non-zero): a
`<!-- math -->` marker with no row to resolve it, and a marker with no
mapping file at all. Both mean the pdf would carry verbatim text where
you said an equation goes.

**Everything else only warns**, because a wrong guess must not stop a
render. A span with no row is a `[math]` gap when a named rule calls it
a quantity, and the warning names the rule
(`` `-1` looks like a quantity (signed-number) ``), so a false alarm
points at what fired. In order:

1. **Your own symbols.** A span that is, or is built from, a name your
   `math.md` already uses: `k`, `-k`, `T_k`, `EC_0`, `OCV(SoC)`,
   `(A, B, C)`. The names come from the LaTeX column (single letters,
   Greek control words) and from the ASCII column when they look like a
   symbol: one letter, a capital in it (`SoC`), or a Greek name.
   Lowercase words such as `level` never count. Single symbols were the
   *dominant* shape when this was first measured, roughly 296 of 515 in
   one book, and no operator rule can see them.
2. **Shape, anywhere.** A relation (`h = 9`), arithmetic between digits
   (`3 - 1`), a signed number (`-0.074`), a bracketed list of numbers
   (`[1 0]`) or a `;` matrix, `*` or `^` between operands
   (`A * P_est * A^T`), a spaced `+ - /` (`t + h`), a derivative
   (`dT/dt`), a conditional (`P(A | B)`), a subscripted Greek name
   (`sigma_2`), an index step (`x_{k+1}`), scientific notation
   (`1e-12`), or a list of numbers (`0, 3`). Before the rules that look
   *inside* a span, tokens that are plainly paths, file names, URL
   queries, `<placeholders>`, dates or versions are set aside, so
   `` `code/02-01-x/` `` and a command line naming `02-01-s.md` are not
   read as subtraction.
3. **Only in a draft with a `math.md`.** A single letter, a bare number
   (`0.5`) and a bare Greek name (`lambda`, `Pi`). These are as often
   code (`404`) as mathematics, so they count only for an author who
   declared mapped mathematics.

When one of these is code, say so once, in a one-column table anywhere
in the same `math.md`:

```markdown
## Not mathematics

| Code in the draft |
| --- |
| `404` |
```

A listed span is never a gap, and a listed span the draft no longer
contains is reported, as the orphan of a mapping row is. Two rows with
the same ASCII and different LaTeX are reported too (the last one is
what renders), and so is a span both mapped and listed.

An untagged fence that looks like a displayed equation nobody marked is
the last warning, judged line by line on shape alone.

A file that can have no `math.md`, such as a review report or anything
outside `content/drafts/`, gets none of these warnings, since each asks
for a row nobody can add. A `<!-- math -->` marker in one still fails.

The fence warning names both remedies, because a bare fence leaves the
question open in both directions: mark it if it is an equation, tag it
if it is code. It fires on a fence of **at most four lines** matching a
shape rule and no underscore identifier. `as_of` and `predicted_next`
are code, and length is what separates an equation from the other thing
a bare fence holds, an [§10 figure](#-10-figures), whose box borders are
not math-shaped but whose `->` arrows are. Measured over every untagged
fence in this repository's own drafts, the genuine equations run one to
four lines and the shortest false positive is a seven-line pseudocode
listing.

**Still not gated, deliberately.** `python -m chitragupta.draft gate`
means exactly one thing (a fabricated citekey fails), and
[docs/CODE-STANDARDS.md](CODE-STANDARDS.md) keeps it that way. `render`
refusing is a different thing from the gate, and refuses only what is
certain.

**What no check sees.** A quantity spelled out (`slope`, `offset`,
`Assemble(N)`) reads like an identifier, so unless it has a row it
looks like ordinary code to everything above, and so does a name such
as `SoC` that no other row of the draft's `math.md` mentions. Operators
between multi-letter names must be spaced to be seen: `EC - EC_0` is a
gap, `EC-EC_0` is set aside as a hyphenated word. A draft using the
*inline* form has no mapping to close the world against, so it gets the
shape rules only. The known false alarm the other way is SQL's
`SELECT * FROM t`, whose remedy is the table above.
`plans/math-typesetting-convention.md` records what the gaps cost this
repository's own book, and `plans/1115-1116-math-shape-rules.md` how the
rules were measured.

An inline matrix wide enough to overflow is not checked either. Whether
it fits depends on the math font as much as on the matrix: the hint
in that book set without overflow under Computer Modern and ran 58pt into
the margin under STIX Two Math. Flagging every inline matrix instead would
have been mostly noise: the same book has seven others, and none of them
overflows. The rule above is the guard, and it is stricter than the
overflow on purpose: the appendix's inline `A = [2, 1; 0, 3]` fits today
and breaks the rule, because a different font or a narrower page is all
it takes to push it past the margin.

A long aligned array in an *unmarked* fence is past the four-line bar and
goes unreported too, deliberately, since that is the shape whose marker
is worth writing by hand. And nothing here reads a rendered `.tex`: a
post-render grep for math-shaped `\texttt{}` is what reported this book
clean while a `\begin{verbatim}` equation sat in it, because a fence
never becomes a `\texttt{}`.

### 📖 Symbols: what each mapped symbol means

The mapping says how a symbol is set; `math.md`'s `## Symbols` says
what it means, and since #1143 it is the only place a symbol's meaning
is written. The glossary keeps terms, never symbols, and a symbol list
in `scope.md`'s House style is read by nothing.

```markdown
## Symbols

| Symbol | Meaning |
| --- | --- |
| `m_t`  | **Target moisture** |
| `m_lo` | **Moisture thresholds**, lower |
| `T_c`  | see 02-plant-demonstrator |
| `e_q`  | quantisation error |
```

- **A bold term is a link** to the glossary entry that defines it, so
  the definition is written once. In a book it may name a term any
  accepted unit defines. Text after a comma is a note, telling two
  symbols of one term apart.
- **`see <unit>` reuses another unit's row** for the same symbol, which
  is how a book's chapters share notation. The other unit must have a
  row that is a link or words (never another pointer), and the two
  units must map the symbol to the same LaTeX.
- **Anything else is the meaning in words.** Write a `|` inside it as
  `\|`.

The table runs from its heading to the next `##` heading, so it may come before
or after the "Not mathematics" table, and nothing under it is read as a
mapping row.

**Every bare symbol the mapping table holds needs a row**: a name of
letters and digits with `_` subscripts, such as `m`, `T_oil` or
`x_hat`. An expression, `T_c = 6`, `h^2` or a function application such
as `r(t)`, may have a row and needs none. The symbol's LaTeX stays in
the mapping table, so a meaning with no mapping row cannot be typeset.
`render` reports both, among its `[math]` warnings: a mapped symbol with
no meaning (one summary line for a `math.md` with no `## Symbols` at
all), a meaning with no mapping row, and a row that is empty, half bold
or repeated. A book's `registry check` adds the cross-unit half: a link
no glossary defines, a pointer that does not land, a symbol naming two
things or set two ways, and a glossary span that is mathematics with no
mapping row in its own unit, which would print as code.

**Glossary spans use rows too.** A definition such as "the reciprocal of
the sampling interval, `1 / T_s`" is typeset through the unit's own
mapping, so `1 / T_s` needs a row even when the draft never writes it,
and that row is not an orphan. A bare symbol is also used when it is a
whole token inside a mapped span or block (`T_r` inside `T_r = 10`), so
a symbol only ever written inside formulas can have the row its meaning
needs. Only *mapped* spans count: `range(n)` keeps no `n` row alive.

### 🔢 A number for a chosen few, not for every displayed equation

A table or a figure gets a number by existing; a displayed equation
does not. Numbering every step of a derivation is noise, so the choice
is the author's. Unlike everything else `render` checks in this
section, **nothing here can decide which equations deserve one**; the
list below is guidance for making that call.

Number an equation when:

- it is **standalone**: not one step among several leading somewhere
  else;
- it is the **final result of a derivation or a chain of logically
  continuous equations**: the steps that lead to it are not numbered,
  only the one that was proved;
- it is **reused by a later equation** (substituted into it, referred
  back to), regardless of the two rules above.

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
author**; they are assigned by document order of `equation:` markers, the same
reasoning §13 gives for a table: document order is LaTeX's own counting
order, so the number this pipeline writes for `md`/`docx` and the number
LaTeX assigns for `pdf` point at the same equation. Unlike a table's
caption, an equation carries no number in the *draft* on either path,
only in what each format renders to.

**A marked equation gets a number in every rendered format, `md`
included**, matching the table/figure precedent above rather than this
section's own "the `md` path is a no-op" rule. That rule still holds for
an equation's *content*: the ASCII inside a marked fence is exactly as
untouched on the `md` path as an unmarked one always was. It does not
hold for the *number*: a marked equation gains a `**Equation N:**` label
there, the same way a table already gains `**Table N:**`. This is a
deliberate, narrow exception: content substitution is still gated on a
real `math.md` mapping; equation numbering is not, and runs
unconditionally the way a table's or figure's numbering already does.

An unmarked `<!-- math -->` block (a derivation step, or any equation
the author chose not to number) is untouched by every check in this
subsection. There is no finding for "this equation should have been
numbered and was not": that would require the tool to tell a standalone
result from an intermediate step, which nothing here can do.

### ✍ Prose around the maths

This section says how a symbol is set; the sentences around it follow
`.claude/skills-common/references/mathematical-prose.md`,
which both chapter skills read on every run. In short: define each
symbol in its own sentence with its unit and a role word that agrees with
its `## Symbols` row, repeat the role word after a gap, give one letter
one meaning, write the "then", state a derivation's claim first and what
it showed last, keep the argument to one paragraph per step, and name the
condition checked before applying a result. None of it is checked by a
tool.

## 🔢 13. Tables

A table is evidence arranged for comparison. It needs a **caption**, so
the rendered document can number it, and a **sentence that reads it**,
so the reader is not left to work out what the arrangement was for.

Without a caption, a survey's comparison table renders as an unnumbered
`longtable` that no sentence can name.

### 🏷 A caption, an id, and no number you write yourself

A Markdown draft writes the table, pandoc's own caption line, and an id
marker directly under it, with no blank line between the two (the same
adjacency §11's `<!-- single-source: -->` uses):

```markdown
| Starting point | Core idea | Stated limitation |
|---|---|---|
| DTaaS platform | One tenant-facing platform | Reuse needs components |

: Where to start when building a first twin.
<!-- table: start-here -->
```

Prose points at it with an inline marker, which stands in for the whole
reference phrase; you write neither the word "Table" nor a number:

```markdown
The platforms in <!-- tableref: start-here --> differ mainly in what
they ask you to bring.
```

**Never write the number.** `: Table 1: Where to start.` renders as
"Table 1: Table 1: Where to start.", because LaTeX supplies its own
prefix; and a number typed into a chapter is wrong the moment that
chapter is assembled into a book, where the same table numbers "2.1",
or something else again, since a book that suppresses chapter numbering
counts its tables flat from the front. `render` resolves both markers
per format ([RENDERING-FLOW.md](RENDERING-FLOW.md) has the four cases): LaTeX-bound
output gets a `\label` and numbers itself, and every other format gets a
number counted at render time, because pandoc numbers nothing outside
LaTeX.

**The caption is visible text; only the id hides.** A caption may cite,
and `python -m chitragupta.draft gate` reads the draft, so the caption
stays where a reader and the gate can both see it. The id is not prose
and nobody reads it, which is why it is the half in a comment.

**Ids are kebab-case and unique within a draft.** Two tables sharing one
id become two `\label{}`s in one LaTeX document, where a duplicate
resolves silently to the wrong table, which is a real risk for a book
unit, since [WRITE-A-BOOK.md](WRITE-A-BOOK.md)'s assembly puts fifteen
units in one document.

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
is `\input` into the user's own thesis, where their own LaTeX
numbers it consistently with their other chapters. Nothing this pipeline
does may get between them.

### 👓 The sentence that reads the table

A caption says what a table *is*. It does not say what it *shows*, and a
table dropped into a section with neither a lead-in nor a reading is
work handed to the reader.

- **Introduce it before it appears**: what is being compared, and on
  what axis.
- **Read a pattern off it afterwards**: the row that is the exception,
  the column where everything agrees, the trade-off the arrangement
  makes visible. If nothing can be read off it, the table is decoration.
- **Keep the reference beside the table.** A table in §6 whose only
  mention is in §2 is one the reader meets unannounced.
- **Say it once.** Prose that re-states every row is a table set twice;
  the point of the arrangement is that it does not need narrating.

`python -m chitragupta.draft style` reports the decidable part of this:
a table with no caption, no id, an id that is not kebab-case, a
duplicate id, a reference to a table
that does not exist, a table no sentence refers to, and a table
referenced only from another section. Whether the sentence that refers
to it *explains* it is a judgement, and stays one; §9's table
records the split.

## 📄 14. What has to fit the page

A draft is read on paper, or on a screen shaped like paper. Three
things run into the margin there and nowhere else, so they are invisible
until someone opens the PDF, which is usually after the draft has been
reviewed. A fourth, a matrix set inline, is [§12's](#-12-mathematics)
rule, because it is mathematics before it is layout.

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

A code span that is *only* a URL counts as a bare one; the monospace
font changes nothing about how it reads. A code span with a URL among
other tokens (`curl https://…`) is a command, and is left alone: making
it a link would corrupt the thing it prints.

### 📏 Keep a code block inside the page

**76 columns**, measured rather than chosen: at this project's book
geometry (11pt, 80pt margins) a `verbatim` line fits 79, and at `draft
render`'s own defaults (12pt, 1in margins) it fits 76. A draft may be
rendered either way, so the tighter one is the limit. Both numbers were
measured through pandoc's own template, which loads `lmodern`;
measuring against a bare `\documentclass` gives 76/73, three columns
tight, because Computer Modern's typewriter face is wider.

**A Markdown draft's blocks wrap rather than overflow**, so this is
a quality rule rather than a defect one. `draft render` loads `fvextra`
and redefines `verbatim`/`Highlighting` with `breaklines` for any draft
that has a fenced block, so an over-wide line breaks at a space and
marks the continuation with `,→`. Keeping the line short avoids that
marker, which a reader copying the command out of the pdf would
otherwise pick up.

**A `.tex` fragment is the case that cannot be repaired at render
time**, and is why the check exists at all. `thesis-chapter-writer` emits a fragment
`\input` into the user's own thesis, whose preamble this pipeline may
not touch (§13's carve-out), so nothing can load `fvextra` on its
behalf, and a wide `verbatim` line there runs into the margin. Shorten
it: break the pipeline, drop the aligned comment column,
abbreviate the path.

A book is the third case: its units are rendered `--fragment`, which
emits no preamble, so its `book.tex` carries the `fvextra` load itself
(see `.claude/skills/book-assembler/references/latex-conventions.md`).

`chitragupta.WideCodeLine` reports a line over the limit with `repair:
"review"`, so a person decides rather than an unattended pass. A wide
line may be deliberate: a URL, or a literal in a block verified to run.
The repair edits a code sample rather than prose, and dropping an
argument to fit the width leaves a command that still reads plausibly
and does not work.

### 🔤 Prefer a breakable form for a very long token

Where a choice exists, prefer a token under about **15 characters**, or
one with an internal `-`, `/` or `_` to break at.

No check backs this, because TeX hyphenates a long English word in a
roman font well: `interoperability` sets as `in-teroperability` even in
a 4cm column, and so does a camelCase identifier written in prose.
Measured across this project's own 428-page book, no prose word caused
an overflow, and a rule flagging every token over 15 characters raised
36 candidates (`interoperability`, `indistinguishable`,
`microcontrollers`), none of which has a repair that is not a worse
word. So it stays advice to an author choosing between two phrasings,
and never becomes a finding. §9's table records it beside the other row
with no mechanical proxy.

`python -m chitragupta.draft style` reports the decidable part of this
section: a bare URL, and a code line over the column limit. The
third rule is not checked, deliberately, per the paragraph above.

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

Three openly licensed works supply the principles above. All three require
attribution under their licences; this section is that attribution.

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

**Ideas, not text, from one further work.** Gareth Wilkes, *A Brief
Guide to Mathematical Writing*, Department of Pure Mathematics and
Mathematical Statistics, University of Cambridge, revised 2023-10-08.
The guide states no licence, so nothing from it is quoted and none of its
examples is reused; the credit is given because the ideas are its.
Supplies, for §12's prose rules in
`.claude/skills-common/references/mathematical-prose.md`:
defining a symbol in its own sentence with a role word, and repeating the
role word on reuse; choosing letters by mnemonic and alphabet region, and
never overloading one ("Notation and definitions"); writing the "then",
stating the claim before a proof and its conclusion after, one step per
paragraph, and checking a result's conditions before applying it
("Formatting and structuring proofs"); keeping diagrams for objects,
not for the argument ("Diagrams").

### 💡 What is original here

The prose in this file and in every `.claude/skills/*/SKILL.md` is written
from scratch. A verbatim n-gram check against all three sources above
(107,272 words of source; the algorithm is `chitragupta/review/verbatim_check/_overlap.py`'s
`cmd_overlap`) reports **0% overlap at an 8-word threshold**, and nothing
above five consecutive shared words anywhere. What is borrowed is the
*ideas*, credited above; what is added is their translation into
operational rules for this pipeline's six genres, the decision about which
principles transfer across genres and which do not (§5's warning), and the
handling of failure modes specific to multi-agent drafting.

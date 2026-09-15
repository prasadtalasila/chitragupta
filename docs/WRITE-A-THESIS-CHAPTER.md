# 🎓 Write a thesis chapter, start to finish

Status: **tutorial.** Written 2026-09-15.

**Written for** a doctoral or master's student who wants a chapter of
their own thesis drafted from their own library, and who has not used
this pipeline before. **Assumed:** nothing. This page repeats what other
documents also say, deliberately -- you should be able to finish a
chapter without leaving it. **Not covered here:** how retrieval ranks
([RETRIEVAL.md](RETRIEVAL.md)) and why each prose rule exists
([WRITING-STANDARDS.md](WRITING-STANDARDS.md)).

Sister tutorials: [a survey](WRITE-A-SURVEY.md),
[a textbook chapter](WRITE-A-TEXTBOOK-CHAPTER.md),
[a tutorial](WRITE-A-TUTORIAL.md),
[a deep-research report](WRITE-A-DEEP-RESEARCH-REPORT.md).

## 🧭 Table of contents

- [What makes this genre different](#-what-makes-this-genre-different)
- [What you will have at the end](#-what-you-will-have-at-the-end)
- [Before you start](#-before-you-start)
- [Step 1: the research question, the examiner, the slug](#-step-1-the-research-question-the-examiner-the-slug)
- [Step 2: open the dossier](#-step-2-open-the-dossier)
- [Step 3: write an outline (optional, recommended)](#-step-3-write-an-outline-optional-recommended)
- [Step 4: ask for the chapter](#-step-4-ask-for-the-chapter)
- [Step 5: gate, render, sidecar](#-step-5-gate-render-sidecar)
- [Step 6: put it in your thesis](#-step-6-put-it-in-your-thesis)
- [Step 7: read the review aids](#-step-7-read-the-review-aids)
- [Step 8: change something](#-step-8-change-something)
- [When something goes wrong](#-when-something-goes-wrong)

## ⚖ What makes this genre different

The output is a **LaTeX fragment**, not a document: no
`\documentclass`, no `\begin{document}`, no preamble. It is written to be
`\input` into the thesis you already have, so your own template,
numbering and bibliography stay in charge.

Three consequences, all deliberate:

- **Citations are `\citep{...}`/`\citet{...}`**, not `[@citekey]`. The
  gate reads both, so the guarantee is unchanged.
- **The fragment carries no References section.** Your thesis has one
  thesis-wide bibliography, and a second one landing mid-chapter would
  compete with it.
- **Figures are inline `\input`s inside a hand-written `figure` float**,
  because the fragment has to stay self-contained once it leaves this
  pipeline.

## 🎯 What you will have at the end

For a chapter you decide to call `thesis/methods`:

| Path | What it is |
| --- | --- |
| `content/drafts/thesis/methods.tex` | the fragment -- the canonical copy, the thing you `\input` |
| `content/dossiers/thesis/methods/` | scope, kept evidence, rejected candidates, every search run |
| `content/rendered/thesis/methods.pdf` | a standalone preview, so you can read it before it is in the thesis |
| `content/rendered/thesis/methods.md` | a Markdown preview of the same |
| `content/rendered/thesis/methods.evidence.pdf` | the evidence sidecar: each cited source with the spans that justified it |

## 🔧 Before you start

Three things, once per machine.

**1. Install it and get a project directory.** Either

```bash
pip install chitragupta-cli
chitragupta init my-thesis
cd my-thesis
```

or clone the repository and `cp config.toml.example config.toml`.

**2. Export your library to BibTeX**, at `papers/bibliography.bib`, with
the PDF file paths attached:

```bash
mkdir -p papers
cp /path/to/your-library.bib papers/bibliography.bib
```

**3. Build the corpus:**

```bash
chitragupta corpus sync
chitragupta corpus ledger          # a summary: how many entries, how many parsed
```

If nothing is `parsed`, your export has no usable PDF paths. Fix that
first -- a chapter cannot be grounded in a corpus with no text in it.

> Every command here also works as `python -m chitragupta.<layer> ...`.

## 🔬 Step 1: the research question, the examiner, the slug

**The research question** is the one thing this genre will not proceed
sensibly without. A thesis chapter argues toward an RQ; it does not
summarise papers in sequence. Write it down in one sentence, e.g.
*"RQ2: under what conditions does a reduced-order surrogate remain
faithful enough to support a safety decision?"*

**The examiner** is your reader. Name what they already know, so
background is recapped where it is genuinely needed and nowhere else.
"An examiner in control engineering who has never worked with
digital twins" produces a very different chapter from "an examiner who
supervises three digital-twin students".

**The slug** is the path under `content/drafts/`, without the suffix:

| You are writing | Use |
| --- | --- |
| the methods chapter of one thesis | `thesis/methods` |
| a chapter that shares a topic with other genres | `dt/thesis-chapter` |
| a standalone chapter | `methods` |

## 🗂 Step 2: open the dossier

```bash
chitragupta draft dossier init content/drafts/thesis/methods.tex \
    --genre thesis-chapter
```

Note the `.tex` suffix -- this genre's draft is LaTeX.

That writes eight files. **Exactly one is yours to fill in: `scope.md`.**
The rest -- `evidence.md`, `rejected.md`, `sections.md`, `retrieval.md`,
`steering.md`, `revisions.md`, `README.md` -- are written for you as the
chapter is produced.

### What goes in `scope.md`

`init` writes it with every heading present and empty. Five things are
yours:

| Field | What goes in it | Why it is asked for |
| --- | --- | --- |
| `- language:` | a BCP-47 tag: `en-GB`, `en-US`, `en-IN` | ships **unset**; your institution decides it, and an unset one silently gets the model's own |
| `## Reader` | the examiner, in one sentence, including what they have just read | background gets recapped where it is needed and nowhere else |
| `## Covers` | the RQ this chapter serves, and nothing beyond it | keeps the chapter from absorbing the next one |
| `## Does not cover` | what belongs to other chapters, and any theme the corpus could not support | an examiner reads an unexplained absence as an oversight |
| `## Glossary` | each recurring term with its one pinned definition | **the field that matters most in this genre**: an examiner notices terminology drift, and this is what a later revision is held to |

Set the dialect with the command, so the format is right:

```bash
chitragupta draft dossier set-language content/drafts/thesis/methods.tex en-GB
```

A filled-in thesis-chapter `scope.md` -- the whole file is at
[`examples/dossiers/thesis-chapter/scope.md`](examples/dossiers/thesis-chapter/scope.md):

```markdown
# Scope

- genre: thesis-chapter
- language: en-GB
- draft: content/drafts/thesis/methods.tex
- created: 2026-09-15
- corpus: 214 citekeys, digest `a31f0c4b77de`
- draft digest: not recorded (run `dossier stamp` once the draft is ready)

## Reader

The external examiner: a control engineer who has supervised
reduced-order modelling work but has never built a digital twin, and who
will read adversarially for the claim that outruns its evidence. They
have just read chapters 1-3, so the motivation is established and must
not be re-argued here.

## Covers

RQ2 only: under what conditions a reduced-order surrogate stays faithful
enough to support a safety decision.

## Does not cover

The empirical evaluation. That is chapter 5, and moving any of it here
would leave chapter 5 as a results table with no argument.

Learned surrogates (neural). Deliberate: the thesis' contribution is in
projection-based reduction, and the two literatures have different
notions of error entirely.

## Glossary

- **Surrogate** -- any cheaper model standing in for the full-order
  simulation. Reserved for the projection-based kind; a learned stand-in
  is called an emulator.
- **Fidelity** -- error on the quantities the safety decision depends
  on, never a global norm. Pinned here because three cited papers use it
  the other way and the chapter must not drift into their sense.
- **Error bound** -- a guarantee that holds for every admissible input,
  as opposed to an observed maximum error on a test set, which is called
  an empirical fit throughout.
```

The two glossary entries that say "pinned here because the sources use
it differently" are doing the real work: that is how a chapter keeps its
own vocabulary while citing papers that do not share it.

## 🗺 Step 3: write an outline (optional, recommended)

For a chapter arguing toward an RQ, declaring the arc yourself is usually
better than letting it be inferred:

```bash
chitragupta draft dossier init content/drafts/thesis/methods.tex \
    --genre thesis-chapter --outline
```

Look at what the corpus holds before you commit to sections:

```bash
chitragupta draft retrieve search "surrogate model fidelity" --k 15
```

Then edit `content/dossiers/thesis/methods/outline.md`. Three fields per
section:

| Field | What goes in it | What the skill does with it |
| --- | --- | --- |
| `brief:` | steering in your own words | consumed once, **never appears in the chapter** |
| `claim:` | your own prose -- the argument you intend to make | rewritten and **grounded**; any sentence the corpus cannot support is reported back rather than shipped |
| `queries:` | a `-` list of search terms | run **verbatim** instead of the skill inventing sub-themes |

A section needs at least a `brief:` or a `claim:`; `queries:` is optional
even then. Sections may nest -- `###` under `##` -- which this genre uses
more than the others, because a chapter's technical core usually has two
or three families to treat separately.

**`claim:` is the field this genre gets the most out of.** A thesis
chapter argues; writing your intended argument as `claim:` blocks means
the skill either grounds each one or tells you it cannot -- which is
exactly the conversation you want before the examiner has it with you.

A worked example -- the whole file is at
[`examples/dossiers/thesis-chapter/outline.md`](examples/dossiers/thesis-chapter/outline.md):

```markdown
## Why the surrogate question arises here

brief: Connect back to RQ1's result. Two paragraphs, no literature dump
-- the reader has just read chapter 3.

## What "faithful enough" has meant in the literature

claim: Fidelity is defined against a decision, not in the abstract, and
the field has no shared threshold.

queries:

- surrogate model fidelity criterion
- reduced order model validation

## Methods that bound the error

brief: This is the chapter's technical core. Prefer sources that state
an error bound over ones that report an empirical fit.

queries:

- reduced order model error bound
- surrogate uncertainty quantification

## Why the existing bounds do not transfer to my setting

brief: The gap that motivates chapter 5. Be explicit that this is my
argument, grounded where the corpus supports it.

queries:

- error bound assumptions violated nonlinear
```

Validate it:

```bash
chitragupta draft dossier outline content/drafts/thesis/methods.tex --check
```

## 🗣 Step 4: ask for the chapter

Ask in ordinary words, in a session in this project directory:

> Draft the methods chapter of my thesis into
> `content/drafts/thesis/methods.tex`. RQ2 is: under what conditions does
> a reduced-order surrogate remain faithful enough to support a safety
> decision? The dossier and outline are there.

"Thesis chapter", "dissertation section" or "RQ-driven chapter" is what
selects `thesis-chapter-writer`. Give it the RQ in the same message --
it is the spine of everything it writes.

What it then does: clarifies the RQ if you did not give one, retrieves
broadly and filters, re-searches thin concepts, checks for disagreement
between kept sources, drafts the fragment with `\citep`/`\citet`, records
provenance, and maps each section to the citekeys it cites. It never
writes a citekey it did not get from a retrieval result.

## ✅ Step 5: gate, render, sidecar

The skill runs these. Run them yourself after any hand edit.

```bash
chitragupta draft gate content/drafts/thesis/methods.tex
```

`OK` means every `\citep{...}` key is real. `FAIL` names the line; fix
the key or drop the claim.

Previews -- the fragment stays canonical, these are for reading:

```bash
chitragupta draft render content/drafts/thesis/methods.tex --format pdf
chitragupta draft render content/drafts/thesis/methods.tex --format md
```

The evidence sidecar, which this genre should always emit -- your reader
is an examiner reading adversarially for the claim that outruns its
evidence, and the sidecar is exactly what lets them check one:

```bash
chitragupta draft evidence content/drafts/thesis/methods.tex --format pdf
```

It is a separate standalone document, never something your thesis
`\input`s.

Then stamp it, so a later drift report knows what it is comparing
against:

```bash
chitragupta draft dossier stamp content/drafts/thesis/methods.tex
```

## 📎 Step 6: put it in your thesis

Copy or symlink the fragment into your thesis tree and `\input` it:

```latex
\chapter{Methods}
\input{chapters/methods.tex}
```

Three things your thesis preamble must provide, because a fragment
carries no preamble of its own:

- **`natbib` or whatever supplies `\citep`/`\citet`** -- you almost
  certainly have this already.
- **Every citekey the chapter cites, in your thesis `.bib`.** They came
  from your own export, so this is normally already true.
- **`\usepackage{tikz}` and the TikZ libraries any figure needs**, if the
  chapter has figures. Each figure file names its libraries in a
  `\usetikzlibrary` line at the top; put those names in your preamble
  too.

The chapter deliberately writes no `\renewcommand{\thefigure}` and no
hand-typed figure numbers, so your thesis numbers everything
consistently.

## 🔍 Step 7: read the review aids

None of these can block anything; all exit 0.

```bash
chitragupta draft style content/drafts/thesis/methods.tex
chitragupta review verbatim scan content/drafts/thesis/methods.tex
chitragupta review uncited content/drafts/thesis/methods.tex
chitragupta review provenance content/drafts/thesis/methods.tex
chitragupta review support content/drafts/thesis/methods.tex
```

For a thesis chapter, two are worth more than the rest:

- **`review verbatim`** -- reuse of a source's wording is the failure with
  consequences at a viva. It reports wording shared with any parsed
  source, cited or not, in three buckets: `long`, `short` and `quoted`
  (the last being an attributed quotation, which is legitimate).
- **`review support`** -- whether each citation actually entails the
  claim it is attached to. This is the examiner's own reading habit,
  mechanised.

If the chapter has TikZ figures, also:

```bash
chitragupta review figure content/drafts/thesis/methods.tex
```

### The agenda: all of them as one worklist

```bash
chitragupta review agenda content/drafts/thesis/methods.tex
```

It **reads the aids' filed JSON and never runs an aid**, so run the aids
first with `--write`, then the agenda. Any aid whose report is absent is
named as absent rather than quietly skipped.

Each item carries a class, a section anchor, and whether it is
`[unattended]` -- safe for an automated pass to repair without asking
(`prose`, short verbatim runs, `missing-citekey`) -- or `[surfaced]`, a
judgement only you can make (`unsupported-claim`, `claim-support`,
`uncited-claim`, `recorded-but-uncited`, `misquoted`).

For the methods chapter we have been building:

```markdown
# Agenda: content/drafts/thesis/methods.tex

> **Review aid, not a gate.** This report is evidence for a human
> judgement, never a verdict. No draft is blocked by what it says.

- Draft: `content/drafts/thesis/methods.tex`
- Command: `chitragupta review agenda content/drafts/thesis/methods.tex`

## Sources

- Citation provenance: read
- Verbatim scan: read
- Citation coverage: not run
- Multi-source synthesis: read, no item class defined
- TikZ layout check: read
- Uncited prose: read
- Quotation integrity: read
- Claim support: read
- Prose (style_check): read
- Dossier drift: read

## Summary

- 5 unsupported-claim
- 3 verbatim-run
- 2 uncited-claim
- 1 misquoted

## Findings

### unsupported-claim

- `b7c2109af441` [surfaced] (4.3 Why the existing bounds do not
  transfer): `\citep{benner_survey_2015}` scores weak: The available
  a-priori bounds assume a linearity the water-network model does not
- `1c9e77d0a2b8` [surfaced] (4.2 Methods that bound the error):
  `\citep{rozza_reduced_2008}` scores no support found: and the bound
  degrades gracefully outside the training envelope

### verbatim-run

- `3e716e1cee1c` [unattended] (4.1 What "faithful enough" has meant):
  17-word verbatim run citing `benner_survey_2015`, 8 matched
- `dc32161a46ac` [unattended] (4.2 Methods that bound the error):
  13-word verbatim run citing `rozza_reduced_2008`

### misquoted

- `9f04b1e7c3a2` [surfaced] (4.1 What "faithful enough" has meant): the
  quoted span differs from the source at 3 words -- "error bound" for
  "error estimate"

### uncited-claim

- `a1971eb28d62` [surfaced] (4.4 What this chapter establishes):
  Projection-based reduction is the only family with a-priori guarantees
```

**How to read that as the author.** The `misquoted` item is the one to
fix first -- a quotation that says "bound" where the source said
"estimate" is exactly the error this chapter's own glossary exists to
prevent, and an examiner who spots it will doubt the rest. The two
`unsupported-claim` items are the sentences where your argument outruns
your sources: either soften them, or find the source that carries them.
The `uncited-claim` in the closing section is a claim you have made on
your own authority in a place the chapter said it would not.

The `[unattended]` verbatim runs can be handed off: ask to "work the
review agenda" and `agenda-reviser` repairs them one at a time, re-running
the gate after each and logging every attempt in `revisions.md`.

To check a round of edits actually helped:

```bash
chitragupta review agenda content/drafts/thesis/methods.tex \
    --baseline content/review/thesis/methods.agenda.json
```

That re-runs the aids and reports each finding as `resolved`,
`persisting`, `new` or `accepted`. Read the `new` list, not just the
count: a repair that resolves one finding and introduces another leaves
the total unchanged.

If you have considered a surfaced item and decided it stands as written:

```bash
chitragupta review agenda content/drafts/thesis/methods.tex \
    --accept b7c2109af441
```

Only `claim-support`, `uncited-claim` and `unsupported-claim` may be
accepted; anything else is refused with exit code 2.

## 📝 Step 8: change something

**Never re-run the genre skill to make a change.** Ask for a revision:

> The examiner will not accept the claim in section 2 without a bound.
> Soften it and cite whatever in the corpus actually states one.

That selects `draft-reviser`, which reads the dossier, edits only what is
affected, and logs it in `revisions.md`.

After any hand edit of your own:

```bash
chitragupta draft gate content/drafts/thesis/methods.tex
chitragupta draft dossier stamp content/drafts/thesis/methods.tex
```

Back it up -- `content/drafts/` is gitignored:

```bash
chitragupta draft dossier export thesis/methods
```

## 🚑 When something goes wrong

| What you see | What it means | What to do |
| --- | --- | --- |
| The skill refuses, saying the ledger is empty | no corpus | `chitragupta corpus sync` |
| `gate` says `FAIL` | a `\citep` key is not in the corpus | correct it or drop the claim -- never add it by hand |
| The preview PDF fails on a figure | the figure's TikZ does not compile | fix the figure file; a broken figure fails the whole render |
| Your thesis build fails on `\citep` | no `natbib` in your preamble | add it -- the fragment cannot |
| Your thesis build fails on `of` in a node position | the TikZ library is not loaded in *your* preamble | add `\usetikzlibrary{...}` with the names the figure file lists |
| The chapter reads like a summary, not an argument | the RQ was never stated | give the RQ and ask `draft-reviser` to re-frame around it |
| A cited paper left your library | the corpus moved | `chitragupta draft dossier status --all`, then ask for a re-grounding pass |

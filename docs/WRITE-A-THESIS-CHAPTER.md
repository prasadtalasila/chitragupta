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

Fill in `content/dossiers/thesis/methods/scope.md` by hand now: the
reader, what the chapter covers, what it does not, and the **glossary**.
The glossary matters more here than in any other genre: it is where the
chapter's terminology is pinned so a later revision cannot drift off it,
and an examiner notices drift.

Set the dialect your institution expects:

```bash
chitragupta draft dossier set-language content/drafts/thesis/methods.tex en-GB
```

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

Then edit `content/dossiers/thesis/methods/outline.md`. Each `##` heading
takes a `brief:` (steering, never printed), `claim:` blocks (your own
prose, which must be grounded or reported as unsupported), and optional
`queries:` run verbatim:

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
  source, cited or not.
- **`review support`** -- whether each claim's recorded evidence actually
  bears the weight the sentence puts on it.

One merged worklist across all of them:

```bash
chitragupta review agenda content/drafts/thesis/methods.tex
```

If the chapter has TikZ figures, also:

```bash
chitragupta review figure content/drafts/thesis/methods.tex
```

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

# 📚 Write a survey, start to finish

Status: **tutorial.** Written 2026-09-15.

**Written for** an author who wants a literature survey, a related-work
section or a "state of the art" chapter out of their own library, and who
has not used this pipeline before. **Assumed:** nothing. This page
repeats what other documents also say, deliberately -- you should be able
to finish a draft without leaving it. **Not covered here:** how the
retrieval ranking works ([RETRIEVAL.md](RETRIEVAL.md)) and why each rule
exists ([WRITING-STANDARDS.md](WRITING-STANDARDS.md)).

Sister tutorials: [a thesis chapter](WRITE-A-THESIS-CHAPTER.md),
[a textbook chapter](WRITE-A-TEXTBOOK-CHAPTER.md),
[a tutorial](WRITE-A-TUTORIAL.md),
[a deep-research report](WRITE-A-DEEP-RESEARCH-REPORT.md).

## 🧭 Table of contents

- [What you will have at the end](#-what-you-will-have-at-the-end)
- [Before you start](#-before-you-start)
- [Step 1: settle the slug, reader and scope](#-step-1-settle-the-slug-reader-and-scope)
- [Step 2: open the dossier](#-step-2-open-the-dossier)
- [Step 3: write an outline (optional, recommended)](#-step-3-write-an-outline-optional-recommended)
- [Step 4: ask for the draft](#-step-4-ask-for-the-draft)
- [Step 5: what the skill does while you wait](#-step-5-what-the-skill-does-while-you-wait)
- [Step 6: gate, references, render](#-step-6-gate-references-render)
- [Step 7: read the review aids](#-step-7-read-the-review-aids)
- [Step 8: change something](#-step-8-change-something)
- [Step 9: back it up](#-step-9-back-it-up)
- [When something goes wrong](#-when-something-goes-wrong)

## 🎯 What you will have at the end

For a draft you decide to call `dt/survey`:

| Path | What it is |
| --- | --- |
| `content/drafts/dt/survey.md` | the draft itself, with `[@citekey]` markers -- the canonical copy |
| `content/dossiers/dt/survey/` | why it says what it says: scope, kept evidence, rejected candidates, every search run |
| `content/rendered/dt/survey.pdf` | the typeset PDF, IEEE-numbered |
| `content/rendered/dt/survey.tex` | the same, as LaTeX |
| `content/rendered/dt/survey.md` | a numbered Markdown copy, for a reader who will not open a PDF |
| `content/rendered/dt/survey.evidence.pdf` | the evidence sidecar: each cited source with the verbatim spans that justified it |
| `content/review/dt/survey.*.md` | the review reports you chose to keep |

Every citekey in that draft appears in your own `.bib` export **and** was
picked up by a real parse of a real PDF. That is the one guarantee this
pipeline exists to make, and the gate in step 6 is what enforces it.

## 🔧 Before you start

Three things, once per machine.

**1. Install it and get a project directory.** Either

```bash
pip install chitragupta-cli
chitragupta init my-project
cd my-project
```

or clone the repository and `cp config.toml.example config.toml`.
Nothing on this page differs by which you chose.

**2. Export your library to BibTeX**, at `papers/bibliography.bib`:

```bash
mkdir -p papers
cp /path/to/your-library.bib papers/bibliography.bib
```

Your reference manager must export the PDF file paths with the entries,
or the sync below will record citekeys with no text behind them and
retrieval will find nothing. Zotero users: see
[EXPORT-ZOTERO-GROUPS.md](EXPORT-ZOTERO-GROUPS.md).

**3. Build the corpus.** This reads the bib, parses each PDF and writes
`content/ledger.sqlite`:

```bash
chitragupta corpus sync
```

It takes minutes on a small library and can be re-run any time. Check it
found text, not just entries -- with no flags, `ledger` prints a summary:

```bash
chitragupta corpus ledger
chitragupta corpus ledger --status no_pdf     # entries with no PDF attached
```

If nothing is `parsed`, the bib has no usable PDF paths -- fix that
before going further, because a survey cannot be written from a corpus
with no text in it.

> Every command on this page also works as
> `python -m chitragupta.<layer> ...` -- `python -m chitragupta.corpus
> sync` is the same thing. Use whichever your install gives you.

## 📐 Step 1: settle the slug, reader and scope

Decide three things before any searching happens. They are cheap now and
expensive later.

**The slug** is the draft's path under `content/drafts/`, without the
suffix. It may contain directories, and the dossier and every render
mirror it:

| You are writing | Use |
| --- | --- |
| a standalone survey | `survey` -> `content/drafts/survey.md` |
| one of several documents on one topic | `dt/survey` -> `content/drafts/dt/survey.md` |
| a chapter of a book | `books/digital-twins/survey` |

Moving it later means moving the dossier and the renders too, so pick
now.

**The reader** is one sentence: "a first-year PhD student who knows
control theory but not digital twins", "a grant reviewer outside the
field", "the related-work section of a paper for IEEE TSE". Everything
downstream -- how much is explained, which sources earn space -- follows
from this.

**The scope** is two lists: what the survey covers, and what it
deliberately does not. Write the second one. A reader who can tell an
omission from an oversight trusts the rest.

## 🗂 Step 2: open the dossier

The dossier is the draft's working memory. Create it before drafting:

```bash
chitragupta draft dossier init content/drafts/dt/survey.md --genre survey
```

That writes `content/dossiers/dt/survey/` with eight files. You fill in
one of them by hand, now:

- **`scope.md`** -- the reader, what is covered, what is not, the
  glossary, and the dialect.

Set the dialect explicitly. It ships unset, and an unset dialect means
the draft quietly gets whichever the model prefers:

```bash
chitragupta draft dossier set-language content/drafts/dt/survey.md en-GB
```

`en-US` for most IEEE and ACM venues, `en-GB` for most European funders,
`en-IN` where that is the house style.

The other seven files are written for you as the draft is produced:
`evidence.md` (what was kept and why), `rejected.md` (what was not),
`sections.md` (which section cites which citekey), `retrieval.md` (every
search that ran), `steering.md`, `revisions.md` and a `README.md`
explaining the rest.

Check it any time with:

```bash
chitragupta draft dossier status content/drafts/dt/survey.md
```

## 🗺 Step 3: write an outline (optional, recommended)

You can let the skill decide the sections. You will usually get a better
survey if you declare them yourself. Add the file:

```bash
chitragupta draft dossier init content/drafts/dt/survey.md \
    --genre survey --outline
```

Before filling it in, see what the corpus actually holds, so you do not
declare a section it cannot support:

```bash
chitragupta draft retrieve search "digital twin fidelity" --k 15
```

Then edit `content/dossiers/dt/survey/outline.md`. Each `##` heading gets
a `brief:` (steering for the skill, never printed in the draft) and/or
one or more `claim:` blocks (your own prose, which the skill must ground
in the corpus or report as unsupported), plus optional `queries:` that
are run verbatim instead of the skill inventing sub-themes.

A worked example for a survey of digital-twin literature:

```markdown
## What a digital twin is taken to mean

brief: Establish that the term is contested. Three or four definitional
families, not a list of every paper's phrasing.

queries:
- digital twin definition
- digital twin taxonomy classification

## Fidelity and when it matters

claim: Higher model fidelity is not uniformly better; it is chosen
against the decision the twin supports.

queries:
- digital twin model fidelity
- surrogate model accuracy tradeoff

## Synchronisation with the physical asset

brief: The data half. Sampling rate, staleness, and what happens when
the link drops. Skip vendor middleware.

queries:
- digital twin data synchronisation latency
- sensor sampling rate state estimation

## Validation, and why it is mostly unsolved

brief: This is the gap the survey is really for. Be blunt about how
little of the corpus validates against the physical asset.

queries:
- digital twin validation verification
- model validation physical experiment
```

Validate the shape before drafting:

```bash
chitragupta draft dossier outline content/drafts/dt/survey.md --check
```

It exits 1 if a section has neither a `brief:` nor a `claim:`.

## 🗣 Step 4: ask for the draft

You do not invoke the skill by name. Ask in ordinary words, in a session
whose working directory is this project:

> Write a literature survey on digital-twin fidelity and validation,
> into `content/drafts/dt/survey.md`. The dossier and outline are already
> there.

That phrasing -- "write a survey" / "literature review" / "related-work
section" -- is what selects `survey-writer`. If you name the draft path
and say the dossier exists, it will use yours rather than making a second
one.

Two things worth saying in the same breath if they matter to you: the
venue or length you are aiming at, and any source you already know must
be in there.

## ⏳ Step 5: what the skill does while you wait

Not a black box. In order:

1. **Retrieves broadly**, over-fetching on purpose, per sub-theme or per
   declared `queries:` line.
2. **Scores every candidate itself** before it counts as evidence, and
   writes both the keeps (`evidence.md`) and the rejects with reasons
   (`rejected.md`). A source you can see was considered and dropped is
   the point of that second file.
3. **Re-searches** any sub-theme that came up thin, with reformulated
   queries.
4. **Clusters by judgement** into themes, and checks for disagreement
   between sources before writing a word.
5. **Drafts** in Markdown with `[@citekey]` markers, a comparison table,
   and a gap analysis -- the part of a survey that is actually worth
   reading.
6. **Never writes a citekey it did not get from a retrieval result.**

You will see it working. Where the corpus is thin it says so rather than
filling the hole with a plausible sentence.

## ✅ Step 6: gate, references, render

The skill runs these itself. Run them yourself after any hand edit --
this is the sequence that turns a draft into a document.

**The gate** is the one hard check in this pipeline:

```bash
chitragupta draft gate content/drafts/dt/survey.md
```

`OK` means every `[@citekey]` in the draft is real. `FAIL` names the
offending line; the fix is to correct the key or drop the claim, never to
add the key to the bib by hand.

**The references section**, built from exactly the gated citekeys:

```bash
chitragupta draft references content/drafts/dt/survey.md
```

Leave the body's `[@citekey]` markers alone -- do not hand-number them.
Pandoc assigns `[1]`, `[2]` at render time.

**The renders:**

```bash
chitragupta draft render content/drafts/dt/survey.md --format pdf
chitragupta draft render content/drafts/dt/survey.md --format tex
chitragupta draft render content/drafts/dt/survey.md --format md
```

**The evidence sidecar**, which a survey should always emit:

```bash
chitragupta draft evidence content/drafts/dt/survey.md --format pdf
```

It lists each cited source with the verbatim spans that justified it,
grouped by the section that leans on them. If it prints `no quoted
evidence recorded`, the run captured no quotations -- that is a real
answer about the draft, not a broken command.

## 🔍 Step 7: read the review aids

None of these can block anything. All of them exit 0. They are there to
be read and disagreed with.

```bash
chitragupta draft style content/drafts/dt/survey.md
chitragupta review verbatim scan content/drafts/dt/survey.md
chitragupta review synthesis content/drafts/dt/survey.md
chitragupta review uncited content/drafts/dt/survey.md

# coverage needs the queries to check against -- give it the ones your
# outline declared, repeating the flag:
chitragupta review coverage content/drafts/dt/survey.md \
    --query "digital twin model fidelity" \
    --query "digital twin validation verification"
```

What each is for, in one line:

| Aid | Reads for |
| --- | --- |
| `draft style` | defect markers, an acronym never expanded, dialect against `scope.md` |
| `review verbatim` | wording shared with any parsed source, cited or not |
| `review coverage` | sections leaning on one source, or on none |
| `review synthesis` | paragraphs that summarise sources in sequence instead of synthesising them -- the classic survey failure |
| `review uncited` | claims that read like they need a source and have none |

Add `--write` to any of them to file the report under
`content/review/dt/`. For one merged worklist across all of them:

```bash
chitragupta review agenda content/drafts/dt/survey.md
```

## 📝 Step 8: change something

**Never re-run the genre skill to make a change.** It would re-search the
whole corpus and write a different draft. Ask for a revision instead:

> Shorten section 3 and drop the two 2019 sources in favour of the newer
> ones.

That selects `draft-reviser`, which reads the dossier, edits only the
affected sections, and logs what it changed in `revisions.md`. It is
cheap. Re-running the genre skill is the most expensive mistake available
here ([TOKENS.md](TOKENS.md)).

After a hand edit of your own, re-stamp so later drift reports know what
they are comparing against:

```bash
chitragupta draft gate content/drafts/dt/survey.md
chitragupta draft dossier stamp content/drafts/dt/survey.md
```

If you later re-sync the corpus and want to know whether any draft now
cites something that left:

```bash
chitragupta draft dossier status --all
```

## 💾 Step 9: back it up

`content/drafts/` and `content/dossiers/` are gitignored on purpose --
your writing is not this repository's to commit. Bundle them yourself:

```bash
chitragupta draft dossier export dt/survey
```

That writes a `.tar.gz` holding the draft and its dossier. Add
`--with-rendered` to include the PDFs.

## 🚑 When something goes wrong

| What you see | What it means | What to do |
| --- | --- | --- |
| `FileNotFoundError: papers/bibliography.bib` | no bib export | export your library there and re-run `corpus sync` |
| The ledger has entries but 0 parsed | the bib has no PDF paths | re-export with file paths attached, then `corpus sync` |
| The skill says the ledger is empty and refuses | no corpus yet | `chitragupta corpus sync` |
| `gate` says `FAIL` | a citekey is not in the corpus | correct it, or drop the claim -- never add it by hand |
| `[missing-binary]` from `render` | no `pandoc`/`pdflatex` | install them; the `.md` draft is unaffected |
| The survey reads thin in one theme | the corpus is thin there | add papers to the bib, `corpus sync`, then ask `corpus-reviser` for a whole-corpus pass |
| You want a change and are tempted to re-run the skill | -- | ask for a revision instead; see step 8 |

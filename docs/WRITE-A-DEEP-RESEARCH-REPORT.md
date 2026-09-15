# 🔬 Write a deep-research report, start to finish

Status: **tutorial.** Written 2026-09-15.

**Written for** an author who wants a multi-perspective, contradiction-
mapped report on a question their library can answer, and who has not
used this pipeline before. **Assumed:** nothing. This page repeats what
other documents also say, deliberately. **Not covered here:** how
retrieval ranks ([RETRIEVAL.md](RETRIEVAL.md)) and what a run costs in
detail ([TOKENS.md](TOKENS.md)).

Sister tutorials: [a survey](WRITE-A-SURVEY.md),
[a thesis chapter](WRITE-A-THESIS-CHAPTER.md),
[a textbook chapter](WRITE-A-TEXTBOOK-CHAPTER.md),
[a tutorial](WRITE-A-TUTORIAL.md).

## 🧭 Table of contents

- [Is this the genre you want?](#-is-this-the-genre-you-want)
- [What you will have at the end](#-what-you-will-have-at-the-end)
- [Before you start](#-before-you-start)
- [Step 1: the question, the reader, the depth](#-step-1-the-question-the-reader-the-depth)
- [Step 2: open the dossier](#-step-2-open-the-dossier)
- [Step 3: ask for the report](#-step-3-ask-for-the-report)
- [Step 4: the seven phases, and what you do during them](#-step-4-the-seven-phases-and-what-you-do-during-them)
- [Step 5: gate, references, render](#-step-5-gate-references-render)
- [Step 6: read the review aids](#-step-6-read-the-review-aids)
- [Step 7: change something](#-step-7-change-something)
- [When something goes wrong](#-when-something-goes-wrong)

## ⚖ Is this the genre you want?

Deep research is the heavy option. It runs seven phases, dispatches
several subagents in parallel, and does many retrieval calls. Reach for
it when the *disagreement in the corpus is the point*:

- "What does my library actually claim about X, and where does it
  contradict itself?"
- "I have to make a decision and want the strongest case for and against
  from the sources I hold."

If you want a topic-clustered map of a field, you want
[a survey](WRITE-A-SURVEY.md) -- faster, single-pass, and the right
default. Tell the difference this way: a survey answers *what has been
written*; deep research answers *what is in tension, and what nobody has
asked*.

It is adapted from Stanford OVAL's STORM method, retooled so every claim
cites a real citekey from your own corpus rather than a live web source.

## 🎯 What you will have at the end

For a report you decide to call `deep-research-fidelity`:

| Path | What it is |
| --- | --- |
| `content/drafts/deep-research-fidelity.md` | the report -- the canonical copy |
| `content/dossiers/deep-research-fidelity/` | the reader, scope, kept evidence per perspective, what was rejected, and where the corpus disagreed with itself |
| `content/rendered/deep-research-fidelity.pdf` | the typeset report |
| `content/rendered/deep-research-fidelity.evidence.pdf` | the evidence sidecar |

The dossier matters more in this genre than any other: without it,
changing one paragraph next month means re-running seven phases and a
dozen subagents.

## 🔧 Before you start

```bash
pip install chitragupta-cli
chitragupta init my-research
cd my-research

mkdir -p papers
cp /path/to/your-library.bib papers/bibliography.bib

chitragupta corpus sync
chitragupta corpus ledger
```

Or clone the repository and `cp config.toml.example config.toml`.

**This genre needs a real corpus.** Perspectives that cannot find
sources produce thin interviews, and the contradiction map needs enough
material to have contradictions in it. If `ledger` shows nothing
`parsed`, the skill will say so and stop -- it will not sync for you, by
design.

> Every command here also works as `python -m chitragupta.<layer> ...`.

## ❓ Step 1: the question, the reader, the depth

**The question** should be one a corpus can disagree about. "What is a
digital twin?" is a survey question. "Does the literature support
treating fidelity as a tunable parameter, or as a property fixed by the
decision the twin serves?" is a deep-research question.

**The reader** decides how much framing survives into the report: a
research group, a decision you have to make, or the background section of
something larger.

**The depth** is a dial you set when you ask:

| Depth | Perspectives | Interview rounds | Section writers |
| --- | --- | --- | --- |
| quick | 3 + basic | 2 | inline, no subagents |
| **standard** (default) | **5 + basic** | **3** | parallel subagents |
| deep | 6-7 + basic | 4 | parallel subagents |

Start at standard. Use quick when you want the shape of the disagreement
rather than the full argument; use deep only when a decision rests on it.

## 🗂 Step 2: open the dossier

```bash
chitragupta draft dossier init \
    content/drafts/deep-research-fidelity.md --genre deep-research
```

Fill in `scope.md` now -- reader, covers, does not cover, glossary -- and
set the dialect:

```bash
chitragupta draft dossier set-language \
    content/drafts/deep-research-fidelity.md en-GB
```

Give the skill this same path when you ask, so its phases write into the
dossier you just made rather than creating a second one.

## 🗣 Step 3: ask for the report

> Do a deep-research report into
> `content/drafts/deep-research-fidelity.md` on whether my corpus
> supports treating model fidelity as a tunable parameter or as fixed by
> the decision the twin serves. Standard depth. The dossier is there.

"Deep research", "multi-perspective analysis" or "in-depth report with
contradiction mapping" selects the `deep-research` skill.

Expect it to tell you up front that this is a heavy run. That is the
skill behaving correctly, not a warning about your question.

## 🔭 Step 4: the seven phases, and what you do during them

You are not idle here. Two phases have a decision in them that is yours.

| Phase | What happens | What you do |
| --- | --- | --- |
| **1. Perspective discovery** | Names the perspectives to interview -- typically the Practitioner, the Academic, the Skeptic, the Adoption/Incentives analyst, the Historian, plus a basic-fact pass | **Read the list and change it.** A perspective that does not fit your question wastes a whole interview; one you add can be the report's best section |
| **2. Grounded interviews** | One subagent per perspective, in parallel, each searching the corpus and citing only real citekeys | Nothing -- but watch for a perspective reporting that it found nothing |
| **3. Contradiction map** | Direct contradictions, strongest vs weakest evidence, the resolving question, universal agreement, and the blind spot nobody's searches reached | **Read this closely.** It is the most useful artefact of the whole run, whatever the report ends up saying |
| **4. Outline** | Turns the map into a section plan | **Approve or redirect it** before writing starts. Cheap now, expensive after five sections exist |
| **5. Cited section writing** | One writer per section, in parallel, from pre-vetted citekeys | Nothing |
| **6. Polish + synthesis briefing** | A synthesis pass over the assembled sections | Nothing |
| **7. Peer review + assembly** | A panel -- domain accuracy, methodology rigour, clarity, devil's advocate -- critiques the draft, then it is saved and gated | **Read the critiques**, including the ones not acted on |

Throughout, the main run writes the dossier; the subagents never do.
Their kept claims land in `evidence.md`, their rejects in `rejected.md`,
and the contradiction map's findings alongside.

## ✅ Step 5: gate, references, render

The skill runs these. Run them yourself after any hand edit.

```bash
chitragupta draft gate content/drafts/deep-research-fidelity.md
chitragupta draft references content/drafts/deep-research-fidelity.md
chitragupta draft render \
    content/drafts/deep-research-fidelity.md --format pdf
chitragupta draft evidence \
    content/drafts/deep-research-fidelity.md --format pdf
chitragupta draft dossier stamp content/drafts/deep-research-fidelity.md
```

The evidence sidecar is worth emitting here for the same reason the
contradiction map is worth reading: a report that claims the corpus
disagrees with itself should show you the spans it is comparing.

## 🔍 Step 6: read the review aids

```bash
chitragupta draft style content/drafts/deep-research-fidelity.md
chitragupta review verbatim scan content/drafts/deep-research-fidelity.md
chitragupta review synthesis content/drafts/deep-research-fidelity.md
chitragupta review support content/drafts/deep-research-fidelity.md
chitragupta review uncited content/drafts/deep-research-fidelity.md
```

Two deserve attention in this genre specifically:

- **`review synthesis`** -- a multi-phase run assembled from parallel
  section writers is exactly where paragraphs that summarise sources in
  sequence, instead of synthesising them, creep in.
- **`review support`** -- whether each citation actually entails the
  claim it is attached to. A contradiction map makes strong claims; this
  checks them.

One merged worklist:

```bash
chitragupta review agenda content/drafts/deep-research-fidelity.md
```

## 📝 Step 7: change something

**Never re-run this skill to make a change.** It is the most expensive
mistake available in this pipeline -- seven phases and a dozen subagents
to alter a paragraph. Ask for a revision instead:

> The Skeptic's section overstates the disagreement. Soften it to what
> the two cited sources actually support, and keep the rest.

That selects `draft-reviser`, which reads the dossier -- including the
contradiction map and what each perspective rejected -- and edits only
what is affected.

If you genuinely need the whole corpus re-searched (you added thirty
papers, or you are re-targeting the report at a different reader), say so
explicitly and `corpus-reviser` handles it. That is still cheaper than
re-running deep research.

Back it up -- `content/drafts/` is gitignored:

```bash
chitragupta draft dossier export deep-research-fidelity
```

## 🚑 When something goes wrong

| What you see | What it means | What to do |
| --- | --- | --- |
| The skill says the ledger is empty and stops | no corpus, and it will not sync for you | `chitragupta corpus sync`, then ask again |
| A perspective's interview comes back empty | the corpus has nothing for that angle | drop that perspective, or add papers and re-sync before re-running |
| The contradiction map is empty | the corpus agrees, or it is too small | that is a finding; say it in the report rather than manufacturing tension |
| The run feels too heavy for the question | it probably is | ask for a survey instead -- [WRITE-A-SURVEY.md](WRITE-A-SURVEY.md) |
| `gate` says `FAIL` after a hand edit | a citekey is not in the corpus | correct it or drop the claim |
| You want one section changed | -- | ask for a revision; never re-run the skill |

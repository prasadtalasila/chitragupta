# 📂 Examples

Status: **reference artefacts.** Written 2026-09-02.

**Written for** you, alongside the documentation: every file under
`sample-project/` is a real output of the real pipeline, run against
the five synthetic sample papers committed in
`sample-project/papers/`, so when a document says "a dossier looks like
this" it can show you one that actually passed the gate. The
documentation quotes these files throughout; this page is the map.

Two notes, so the samples cannot mislead:

- **The sources are synthetic.** The five "papers" were written purely
  as sample sources (each carries a notice; all are CC0). Their claims
  are illustrative only. The *machinery* is real: every artefact here
  came out of a real `corpus sync`, a real `draft gate` pass, real
  review aids and real renders.
- **The drafts were written the way the pipeline writes drafts**: from
  logged retrieval over this corpus, citing only citekeys the ledger
  holds, each under 1,000 words, with the dossier filled as drafting
  went. They show the *shape* of a draft; they are not scholarship.

A second directory sits beside `sample-project/` and is **not** pipeline
output: [`dossiers/`](dossiers/README.md) holds hand-written `scope.md`
and `outline.md` files, one pair per genre, plus a book's `spec.md`.
They are the files *you* fill in, shown filled in, for the five
start-to-finish tutorials under Writing. Nothing in them was produced by
a run, and they contain no citekeys.

Two more directories, [`codex/`](codex/README.md) and
[`opencode/`](opencode/README.md), each hold one survey drafted end to
end by that harness driving a local model, over the same five
papers. Each is self-contained: the inputs, the prompt, the script
that ran, and everything the run wrote, unedited. They record what one
real model did, including where it left the skill's path, so their
dossiers are less tidy than the sample project's.
[LOCAL-MODELS.md](../LOCAL-MODELS.md) compares them, and
[LLM-AGENTS.md](../LLM-AGENTS.md) says how to set up each agent.

## 🗺 The sample project, artefact by artefact

| Path (under `sample-project/`) | What it is | The document that explains it |
| --- | --- | --- |
| [`papers/bibliography.bib`](sample-project/papers/bibliography.bib) + `papers/files/*.pdf` | the whole input universe: five entries, five PDFs | [ZOTERO.md](../ZOTERO.md) |
| [`content/drafts/dt-overview/survey.md`](sample-project/content/drafts/dt-overview/survey.md) | a literature survey (gate-passed, referenced) | [GENRE.md](../GENRE.md) |
| [`content/drafts/dt-overview/staleness-tutorial.md`](sample-project/content/drafts/dt-overview/staleness-tutorial.md) | a hands-on tutorial; every step was executed for real before presenting | [GENRE.md](../GENRE.md) |
| [`content/drafts/dt-overview/staleness-chapter.md`](sample-project/content/drafts/dt-overview/staleness-chapter.md) | an undergraduate textbook chapter | [GENRE.md](../GENRE.md) |
| [`content/drafts/dt-overview/trust-chapter.tex`](sample-project/content/drafts/dt-overview/trust-chapter.tex) | a thesis chapter fragment (`\citep`, no preamble) | [GENRE.md](../GENRE.md), [RENDERING-FLOW.md](../RENDERING-FLOW.md) |
| `content/dossiers/dt-overview/<stem>/` | each draft's dossier: scope, kept evidence with `claim:`/`quote:`, rejected candidates, logged retrieval, sections, steering, revisions | [DOSSIER.md](../DOSSIER.md), [DRAFT-ITERATION.md](../DRAFT-ITERATION.md) |
| `content/review/dt-overview/<stem>.*.md` (+ `.json`) | the review layer's reports for each draft: provenance, verbatim, coverage, synthesis, uncited, quotation, support, and the merged agenda | [REVIEW.md](../REVIEW.md), [CITATION-PROVENANCE.md](../CITATION-PROVENANCE.md), [PLAGIARISM.md](../PLAGIARISM.md) |
| `content/rendered/dt-overview/` | rendered outputs: the survey as PDF and Markdown, the thesis fragment as `\input`-ready `.tex` | [RENDERING-FLOW.md](../RENDERING-FLOW.md) |
| `content/specs/twin-basics/` | a signed book outline, its sign-off record, and one accepted unit (`units/ch-staleness.json`); the second unit is still `unwritten` | [WRITE-A-BOOK.md](../WRITE-A-BOOK.md) |
| [`content/seed_topics.toml`](sample-project/content/seed_topics.toml), [`content/topics.json`](sample-project/content/topics.json), [`content/topic_seeds.json`](sample-project/content/topic_seeds.json), [`content/topic_set.json`](sample-project/content/topic_set.json), [`content/topic_graph.json`](sample-project/content/topic_graph.json) | the topic artefacts, from hand-written phrases through clustering to the derived graph | [TOPIC-MODELLING.md](../TOPIC-MODELLING.md), [TOPIC-DISCOVERY.md](../TOPIC-DISCOVERY.md) |
| [`content/topic_map.html`](sample-project/content/topic_map.html) | the whole topic map as one offline page | [TOPIC-DISCOVERY.md](../TOPIC-DISCOVERY.md) |
| [`content/topic_gold.toml`](sample-project/content/topic_gold.toml), [`content/topic_gold_results.json`](sample-project/content/topic_gold_results.json), [`content/discover_digital_twin.txt`](sample-project/content/discover_digital_twin.txt) | a gold query set, its measured scores per resolution rung, and one `corpus discover` transcript | [TOPIC-DISCOVERY.md](../TOPIC-DISCOVERY.md) |

## 🔄 Regenerating the machine state

The ledger, parsed text, embeddings and caches are deliberately not
committed, because the pipeline *rebuilds* them. From
`sample-project/`:

```bash
bash regenerate.sh
```

After that, every command the documentation demonstrates runs here
unchanged: `chitragupta corpus ledger`, `chitragupta corpus discover
"digital twin"`, `chitragupta draft gate content/drafts/dt-overview/survey.md`,
`chitragupta review agenda content/drafts/dt-overview/survey.md`, and
so on. This directory is also the cheapest safe playground: nothing in
it is anyone's real research.

## ⚠ One caveat worth reading before you copy numbers

Five papers is deliberately tiny. Some behaviour differs from a real
corpus at this size, and two differences are themselves instructive:
the topic graph has **no shared-member edges**, because sharing a paper
between topics of size 2 and 5 in a five-paper corpus is what chance
predicts (the hypergeometric gate refuses it; see
[TOPIC-DISCOVERY.md](../TOPIC-DISCOVERY.md)); and the gold-set scores in
`topic_gold_results.json` are visibly imperfect, which is the reason to
measure them rather than assume them.

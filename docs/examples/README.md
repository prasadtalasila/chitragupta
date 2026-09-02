# 📂 Examples

Status: **reference artefacts.** Written 2026-09-02.

**Written for** you, alongside the documentation: every file under
`sample-project/` is a real output of the real pipeline, run against
the five synthetic sample papers committed in
`sample-project/papers/`, so when a document says "a dossier looks like
this" it can show you one that actually passed the gate. The
documentation quotes these files throughout; this page is the map.

Two honesty notes, so the samples cannot mislead:

- **The sources are synthetic.** The five "papers" were written purely
  as sample sources (each carries a notice; all are CC0). Their claims
  are illustrative, not scholarship -- what is real is the *machinery*:
  every artefact here came out of a real `corpus sync`, a real
  `draft gate` pass, real review aids, real renders.
- **The drafts were written the way the pipeline writes drafts**: from
  logged retrieval over this corpus, citing only citekeys the ledger
  holds, each under 1,000 words, with the dossier filled as drafting
  went. They are samples of *shape*, not of scholarship.

## 🗺 The sample project, artefact by artefact

| Path (under `sample-project/`) | What it is | The document that explains it |
| --- | --- | --- |
| [`papers/bibliography.bib`](sample-project/papers/bibliography.bib) + `papers/files/*.pdf` | the whole input universe: five entries, five PDFs | [ZOTERO.md](../ZOTERO.md) |
| [`content/drafts/dt-overview/survey.md`](sample-project/content/drafts/dt-overview/survey.md) | a literature survey (gate-passed, referenced) | [GENRE.md](../GENRE.md) |
| [`content/drafts/dt-overview/staleness-tutorial.md`](sample-project/content/drafts/dt-overview/staleness-tutorial.md) | a hands-on tutorial -- every step executed for real before presenting | [GENRE.md](../GENRE.md) |
| [`content/drafts/dt-overview/staleness-chapter.md`](sample-project/content/drafts/dt-overview/staleness-chapter.md) | an undergraduate textbook chapter | [GENRE.md](../GENRE.md) |
| [`content/drafts/dt-overview/trust-chapter.tex`](sample-project/content/drafts/dt-overview/trust-chapter.tex) | a thesis chapter fragment (`\citep`, no preamble) | [GENRE.md](../GENRE.md), [RENDERING-FLOW.md](../RENDERING-FLOW.md) |
| `content/dossiers/dt-overview/<stem>/` | each draft's dossier: scope, kept evidence with `claim:`/`quote:`, rejected candidates, logged retrieval, sections, steering, revisions | [DOSSIER.md](../DOSSIER.md), [DRAFT-ITERATION.md](../DRAFT-ITERATION.md) |
| `content/review/dt-overview/<stem>.*.md` (+ `.json`) | the review layer's reports for each draft -- provenance, verbatim, coverage, synthesis, uncited, quotation, support, and the merged agenda | [REVIEW.md](../REVIEW.md), [CITATION-PROVENANCE.md](../CITATION-PROVENANCE.md), [PLAGIARISM.md](../PLAGIARISM.md) |
| `content/rendered/dt-overview/` | rendered outputs: the survey as PDF and Markdown, the thesis fragment as `\input`-ready `.tex` | [RENDERING-FLOW.md](../RENDERING-FLOW.md) |
| `content/specs/twin-basics/` | a signed book outline, its sign-off record, and one accepted unit (`units/ch-staleness.json`) -- with the second unit honestly `unwritten` | [BOOKS.md](../BOOKS.md) |
| [`content/seed_topics.toml`](sample-project/content/seed_topics.toml), [`content/topics.json`](sample-project/content/topics.json), [`content/topic_seeds.json`](sample-project/content/topic_seeds.json), [`content/topic_set.json`](sample-project/content/topic_set.json), [`content/topic_graph.json`](sample-project/content/topic_graph.json) | the topic artefacts, from hand-written phrases through clustering to the derived graph | [TOPIC-MODELLING.md](../TOPIC-MODELLING.md), [TOPIC-DISCOVERY.md](../TOPIC-DISCOVERY.md) |
| [`content/topic_map.html`](sample-project/content/topic_map.html) | the whole topic landscape as one offline page | [TOPIC-DISCOVERY.md](../TOPIC-DISCOVERY.md) |
| [`content/topic_gold.toml`](sample-project/content/topic_gold.toml), [`content/topic_gold_results.json`](sample-project/content/topic_gold_results.json), [`content/discover_digital_twin.txt`](sample-project/content/discover_digital_twin.txt) | a gold query set, its measured scores per resolution rung, and one `corpus discover` transcript | [TOPIC-DISCOVERY.md](../TOPIC-DISCOVERY.md) |

## 🔄 Regenerating the machine state

The ledger, parsed text, embeddings and caches are deliberately not
committed -- they are what the pipeline *rebuilds*. From
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
predicts (the hypergeometric gate refuses it -- see
[TOPIC-DISCOVERY.md](../TOPIC-DISCOVERY.md)); and the gold-set scores in
`topic_gold_results.json` are visibly imperfect, which is the point of
measuring rather than assuming.

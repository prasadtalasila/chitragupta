# 🧪 RAG, stage by stage: what everyone does, and what this does differently

Status: **reference.** Written 2026-08-28.

Retrieval-augmented generation is not one algorithm. It is a **pipeline
of eleven stages**, and almost every interesting difference between two
RAG systems is a different choice at one of them -- or a stage one of
them does not have at all.

This document walks the eleven stages, names the **algorithm** each
system actually uses at each, and states the **trade-off** the choice
buys and costs. Chitragupta is one column among seven, held to the same
scrutiny.

**Written for** someone deciding whether this pipeline's shape is the
right one, or wondering why it lacks something every other RAG system
has. **Assumed:** [ARCHITECTURE.md](ARCHITECTURE.md) for the four layers.
**Not covered here:** how to tune any of it
([CONFIG.md](CONFIG.md)), and what a single `search()` call does
internally, which is [CORPUS-SEARCH.md](CORPUS-SEARCH.md) at one more
level of detail.

## 🔍 The six systems compared, and the honesty of this comparison

| System | Licence | Read at |
| --- | --- | --- |
| [OpenScholar](https://github.com/AkariAsai/OpenScholar) | Apache-2.0 | source, 2026-08-28 |
| [RAGFlow](https://github.com/infiniflow/ragflow) | Apache-2.0 (verified unmodified) | source, 2026-08-28 |
| [papersgpt-for-zotero](https://github.com/papersgpt/papersgpt-for-zotero) | repo AGPL-3.0; **shipped engine proprietary** | source + unpacked build |
| [local-deep-research](https://github.com/LearningCircuit/local-deep-research) | MIT | source |
| [AutoRAG](https://github.com/Marker-Inc-Korea/AutoRAG) | **split**: root MIT, `legacy/` Apache-2.0 | source |
| [MiniRAG](https://github.com/HKUDS/MiniRAG) | MIT (a LightRAG fork; ~330 lines are its own) | source |

Two caveats a reader should hold throughout:

- **Read for architecture, never copied.** [INSPIRATION.md](INSPIRATION.md)'s
  standing rule -- *"Attribute the idea, and never copy the text."*
- **This is a snapshot, and several of these repositories disagree with
  their own documentation.** Where a claim below contradicts a project's
  README, the code was read and the code won. Named instances are called
  out in place.

## 🧭 Table of contents

- [Stage 1: ingestion](#-stage-1-ingestion-and-what-is-admitted)
- [Stage 2: chunking](#-stage-2-chunking-the-unit-of-retrieval)
- [Stage 3: indexing](#-stage-3-indexing-and-the-algorithms)
- [Stage 4: query manufacture](#-stage-4-query-manufacture-the-stage-most-systems-skip)
- [Stage 5: candidate retrieval](#-stage-5-candidate-retrieval)
- [Stage 6: fusion](#-stage-6-fusion-combining-lexical-and-dense)
- [Stage 7: reranking](#-stage-7-reranking)
- [Stage 8: capping and diversity](#-stage-8-capping-and-diversity)
- [Stage 9: context assembly](#-stage-9-context-assembly)
- [Stage 10: citation and verification](#-stage-10-citation-and-verification)
- [Stage 11: revision](#-stage-11-revision)
- [Evaluation, which is a stage too](#-evaluation-which-is-a-stage-too)
- [The trade-off table](#-the-trade-offs-in-one-table)

## 📥 Stage 1: ingestion, and what is admitted

| System | What may enter | Algorithm |
| --- | --- | --- |
| **Chitragupta** | **only** entries in the user's own `.bib` export | `bibtexparser`, then `pdftotext` (or Docling) to `content/parsed/` |
| OpenScholar | a prebuilt pes2o datastore, plus live web/Semantic Scholar | offline FAISS build |
| RAGFlow | any uploaded file | DeepDoc layout recognition, or MinerU / a vision LLM |
| papersgpt | the Zotero library | PDF.js (old) / native pdfium (shipped) |
| local-deep-research | web engines, or an uploaded private collection | LangChain loaders |
| MiniRAG | any text | tiktoken windows |

**The trade-off.** Chitragupta's entrance is the narrowest possible and
this is the whole design: a citekey that no `sync` put in the ledger
cannot survive to a rendered draft, so **fabrication is prevented
structurally rather than detected statistically**. The cost is real and
should be stated plainly -- *the pipeline cannot cite a paper you have
not catalogued*, there is no downloader, and "the corpus does not contain
this" is a frequent and deliberate answer. Every other system trades that
guarantee for reach.

## ✂ Stage 2: chunking, the unit of retrieval

| System | Unit | Algorithm |
| --- | --- | --- |
| **Chitragupta (BM25)** | **the whole document** | none -- BM25 scores documents |
| **Chitragupta (dense)** | 200 words, 40 overlap | fixed window, `chunk_text()` |
| RAGFlow | ~128 tokens, 15 templates | layout-aware, `naive_merge()` on delimiters |
| papersgpt | a paragraph (old) / a whole page (shipped) | font-size + y-gap clustering (old) |
| MiniRAG | 1,200 tokens, 100 overlap | tiktoken windows |
| AutoRAG | swept as a parameter | several, compared empirically |

**The trade-off, and it is the one that shapes everything downstream.**
Scoring whole documents makes chitragupta's BM25 **one-result-per-citekey
by construction** -- no paper can occupy two slots, so no cap is needed
and none exists. That is a structural guarantee of source diversity which
every chunk-ranking system has to reintroduce as a *filter*, and which
RAGFlow (see stage 8) never reintroduces at all. The cost is precision:
a 40-page paper matching in one paragraph scores as a document, so the
snippet chooser has to find the passage afterwards. papersgpt's
regression -- paragraphs with bounding boxes replaced by whole pages with
none -- is the same trade taken in the losing direction, and it cost that
project its ability to point at where a claim came from.

## 🗂 Stage 3: indexing, and the algorithms

| System | Lexical | Dense | Other |
| --- | --- | --- | --- |
| **Chitragupta** | **Okapi BM25**, `k1=1.5`, `b=0.75`, stdlib | optional Chroma, `all-MiniLM-L6-v2` | BERTopic (UMAP + HDBSCAN), read by humans only |
| RAGFlow | custom term weighting into an engine DSL | yes | knowledge graph, RAPTOR |
| AutoRAG | `rank_bm25`'s `BM25Okapi` | yes | -- |
| papersgpt | **none** | FAISS (HNSW / IVFPQ / IVFFlat) | -- |
| local-deep-research | none in the local path | FAISS | -- |
| MiniRAG | **none** | four collections, flat numpy | networkx entity graph |
| OpenScholar | -- | FAISS over pes2o | -- |

Two things are worth extracting from that table.

**Three of the six have no lexical retrieval at all.** papersgpt,
MiniRAG and local-deep-research are embedding-only. MiniRAG's paper
therefore **never benchmarks against BM25** -- its "NaiveRAG" baseline is
embedding-only chunk retrieval -- so "beats NaiveRAG" is not evidence
against a BM25 pipeline.

**RAGFlow's term weighting is the most interesting lexical algorithm
here, and its own weakness is instructive.** Each token gets
`(0.3·idf(term_freq) + 0.7·idf(doc_freq)) × ner(t) × postag(t)`,
normalised to sum to 1, with bigrams weighted above unigrams. But `freq()`
and `df()` read **static frequency dictionaries shipped in the repo**, so
the IDF is *corpus-independent by construction*. With 497 real parsed
PDFs, a locally computed IDF is strictly better and strictly cheaper --
which is why chitragupta computes its own and caches it against a
per-document fingerprint.

**The trade-off chitragupta takes here is stdlib-only by default.** BM25
needs no model download, no venv and no GPU, so retrieval works on a bare
`python`. The cost is that BM25 cannot match a paper that argues your
point in different words; the dense path exists for exactly that and is
opt-in because on a small, vocabulary-consistent corpus it does not pay
for itself.

## ❓ Stage 4: query manufacture, the stage most systems skip

**This is the emptiest column in the comparison, and the finding is
worth stating flatly: three of the six manufacture no queries at all.**

| System | Decomposition | Rewriting | HyDE | Default? |
| --- | --- | --- | --- | --- |
| OpenScholar | none | none | none | raw string |
| papersgpt | none | none | none | raw string |
| MiniRAG | none | one LLM call for keywords | none | -- |
| RAGFlow | yes, behind `thinking_mode` | 3 kinds | no | **all off** |
| AutoRAG | yes, as a candidate | yes | yes | optimizer picks |
| local-deep-research | fixed round counts | LLM per round | no | on |
| **Chitragupta** | **`deep-research` only** | -- | no | see below |

OpenScholar's only LLM query generator caps at three by splitting a
string on `", "`, at temperature 0.9 under a comment reading
`# greedy decoding`.

**Chitragupta's own answer is uneven and this document will not pretend
otherwise.** `deep-research` implements STORM -- one or two broad calls
to discover what the corpus actually holds, *then* corpus-specific
personas derived from that, then rounds of persona-driven interviews.
That is better query manufacture than any of the six. The other four
genre skills have nothing: `survey-writer` step 1 is the prose
instruction *"break the requested topic into 2-4 sub-themes"*. The gap is
distribution, not invention, and Theme E in
[FEATURE-ROADMAP.md](FEATURE-ROADMAP.md#-theme-e-the-humans-own-structure)
is the plan.

**One measured hazard belongs here.** BM25 over whitespace tokens with a
20-word stopword list containing **no interrogatives** scores `what`,
`why` and `does` as ordinary terms -- and because they are rare in
academic PDFs they carry high IDF and compete for the ranking. Against
author-assigned ground truth, phrasing a query as a question costs
**7.7 recall points at k=5**;
[CORPUS-SEARCH.md](CORPUS-SEARCH.md#-before-stage-1-the-shape-of-the-query)
has the table and the partial fix.

## 🎯 Stage 5: candidate retrieval

Chitragupta's dense path over-fetches `k × 4` and its BM25 path returns
one hit per citekey. The general shape everywhere else is
over-fetch-then-filter, and the sizes are what differ.

**The trade-off is that over-fetching is the only stage that can add
recall.** Nothing downstream can retrieve what stage 5 did not fetch --
measured here, **69 of 256 correct papers (27%) never entered the
20-chunk pool at all**, which puts a hard ceiling of 0.73 on dense
recall@5 that no reranker can lift. This is why the first question when a
paper does not come back is always "was it fetched?", never "was it
ranked well?".

## ⚗ Stage 6: fusion, combining lexical and dense

| System | Fusion |
| --- | --- |
| **Chitragupta** | **none. You pick one; nothing merges them** |
| RAGFlow | `w·tksim + (1−w)·vtsim`, one tunable knob |
| AutoRAG | RRF, or convex combination over min-max / z-score / DBSF normalised scores |
| everyone else | single route |

**RAGFlow's default is keyword-dominant (0.7 lexical / 0.3 vector)** --
worth knowing, because three different defaults live in three places in
that codebase and third-party write-ups routinely quote the wrong one.

**Chitragupta has no hybrid search, and that is a real gap rather than a
principled refusal.** The honest reason is that on this corpus BM25
outscores the dense path on every ground truth tried, so fusion has not
yet been worth building. AutoRAG's convex combination over normalised
scores is the shape to copy if it ever is -- one tunable weight, one
score scale, reproducible.

## 🔀 Stage 7: reranking

Chitragupta: a **cross-encoder** (`ms-marco-MiniLM-L6-v2`), off by
default. OpenScholar: BGE `FlagReranker`. AutoRAG: sixteen modules.
RAGFlow: a cross-encoder whose score *replaces* the vector term while the
lexical term survives.

**The trade-off is that reranking is the most over-recommended stage in
RAG.** Measured here over 256 queries: recall@3 rose 129 → 139, nDCG@5
0.4949 → 0.5281, and **recall@5 did not move at all** -- the correct
paper was lost 20 times and gained 20 times. It improves *ordering*, not
recall, and it cannot improve source diversity even in principle, because
with a cap of 3 and `k` of 5 the distinct-paper count is bounded by the
**cap**. It also costs 2.5× on GPU and 5.8× on CPU. Hence: off by
default, documented, and reached for only when the right paper comes back
fourth.

**Where it sits matters more than whether it runs.** Chitragupta reranks
**before** the per-citekey cap, so a promotion can change *which
document* survives; reranking after the cap can only permute what the
bi-encoder already chose. Measured, the two orders return a different set
of papers on **217 of 256 queries (85%)**, and a test pins the ordering
so a refactor cannot quietly swap them.

## 🧮 Stage 8: capping and diversity

| System | Per-document cap |
| --- | --- |
| **Chitragupta (BM25)** | **structural** -- one result per citekey |
| **Chitragupta (dense)** | `embed_max_passages_per_source`, default 3, applied before truncation |
| MiniRAG | per-anchor `max_chunks=3` |
| **RAGFlow** | **none** |
| AutoRAG | none, and no cross-query dedup either |

**This is where chitragupta is furthest ahead, and the reason is stage
2.** RAGFlow's `top_n` default is 6 with no cap, so all six chunks can
come from one paper -- which in a survey produces a section citing a
single source. AutoRAG's multi-query path is worse: results are combined
by a per-query quota with **no cross-query deduplication**, so a document
returned by two expanded queries occupies two of your slots.

**The trade-off chitragupta accepts:** capping costs relevance. Dropping
a dominant paper's fourth-best chunk to promote another paper's
tenth-best is a deliberate loss of per-passage quality, bought for source
breadth. That is the right trade *for a survey* and would be the wrong
one for factoid QA -- which is why the cap is a config key.

## 📦 Stage 9: context assembly

| System | What the generator receives |
| --- | --- |
| **Chitragupta** | **claims the drafter wrote**, from the dossier -- ideally never a raw window |
| OpenScholar | `[i] Title: … Text: …`, positional |
| RAGFlow | an ASCII tree, `ID: <i>` per chunk |
| MiniRAG | two CSV blocks -- **`id` is a loop index** |
| papersgpt | `[MAIN_TEXT]` + the paper's own `[BIBLIOGRAPHY]` |

**Two of these destroy provenance at the last step.** MiniRAG replaces
chunk identity with the enumeration index of a loop, so the model is
handed anonymous text. papersgpt injects each source paper's *own
reference list* and points the citation contract at it -- works that were
never parsed and need not be in the library, which is precisely the
fabrication this project exists to prevent.

**Chitragupta's trade-off here is the one it is least done with.** The
design intent is that the drafter holds `claim:` lines it wrote itself,
not 500-character source windows -- because a model writing with a
source's sentences in front of it will track those sentences.
[FEATURE-ROADMAP.md](FEATURE-ROADMAP.md)'s Theme A exists because the
current arrangement does not yet fully achieve this.

## ✅ Stage 10: citation and verification

**The sharpest result in this document: none of the six verifies a
citation.**

| System | What is checked |
| --- | --- |
| **Chitragupta** | **the citekey exists in the ledger -- a blocking gate, the only one** |
| RAGFlow | `i < len(chunks)` -- an array-bounds test |
| OpenScholar | nothing; posthoc attribution silently returns the original on missing markers |
| local-deep-research | nothing; an out-of-range `[42]` survives as literal text |
| papersgpt | one regex rewrites a marker into an anchor |
| MiniRAG | nothing, not even a prompt asking for references |

RAGFlow's fallback attributor multiplies a 0.63 similarity threshold by
0.8 **in a loop until something matches**; local-deep-research's own
benchmark **strips citation markers before grading**, so its citation
correctness is never measured at all.

**The trade-off, stated against this project rather than for it.** The
gate checks that a citekey is *real*, not that the sentence attached to
it is *right* -- a wrong claim with a real citekey passes. That is a
narrow guarantee, deliberately: [DESIGN.md](DESIGN.md) argues one check
that always means exactly one thing beats several that each mean
something fuzzy. Everything else here -- provenance, coverage, verbatim
overlap, quotation integrity, claim support -- is an **advisory aid that
exits 0** and may never block. The cost is that a reader must still read
the sources; the benefit is that `gate` never cries wolf.

**Overlap detection**, which most RAG systems lack entirely, runs three
tiers whose findings are unioned: an exact word-run match, a stemmed
skip-gram match tolerant of substituted words, and an embedding tier that
is the only one that sees genuine restatement. The third is also the
narrowest -- it needs the enrichment layer, the Docling sidecars and the
dossier all present -- so **a clean scan is never a clean bill of
health**, and the report names every tier that could not run.

## ♻ Stage 11: revision

**Zero of the six supports revising an existing document.** Regeneration
is the only model. Three look like exceptions and each fails differently:
OpenScholar's feedback loop runs *before* the artifact exists; RAGFlow's
regenerate button truncates and re-asks, destroying the prior answer;
local-deep-research's follow-up creates a *new child row*.

None detects a hand-edit. None supports section-scoped editing. And
**all of them persist far more than they consume** -- OpenScholar writes
a complete refinement audit trail and reads back only a row count.

**Chitragupta's dossier is the answer to exactly this**, and the
`draft-reviser` / `corpus-reviser` split -- a cheap scoped path that
contains no instructions for a wide search, so it cannot drift into one
-- has no equivalent in any of the six. **The trade-off is that the
dossier is only as good as what was written into it**, and a skill that
skips recording a rejection costs the next revision the most expensive
work in the pipeline. Its one real remaining gap is honest: nothing
fingerprints the draft, so on *hand-edit* detection this pipeline is no
better than the other six.

## 📏 Evaluation, which is a stage too

AutoRAG is the only one of the six built around evaluation, and its
central idea is worth taking: **label-by-construction** -- sample a
chunk, record its id as the ground truth, and only *then* generate a
question from it, so the label needs no judge.

**Its central hazard is worth taking even more seriously.** Because the
question is generated *from* the gold chunk, the query inherits that
chunk's vocabulary, so such a set **structurally favours lexical
retrieval**. A BM25 change measured on it looks better than it is, and
nothing upstream says so. AutoRAG also has no near-duplicate dedup, and
no train/test tooling -- its documentation warns about overfitting while
its code does nothing to prevent it.

Chitragupta's answer avoids the circularity by construction: the query is
a paper's **own author-assigned `keywords` field** and the answer is that
paper. No retrieval method's history chose it, and no LLM wrote it.

## ⚖ The trade-offs in one table

| Choice | Bought | Paid |
| --- | --- | --- |
| Bibliography is the only entrance | fabrication impossible, not merely detected | cannot cite what you have not catalogued; no downloader |
| BM25 over whole documents | one-result-per-citekey **for free**; stdlib, no GPU | no vocabulary matching; passage located after the fact |
| Dense retrieval opt-in | zero default cost | the recall it would add is off by default |
| No hybrid fusion | one score scale, nothing to tune | a real gap, not a principled refusal |
| Rerank off by default | no 2.5-5.8× tax | the right paper sometimes sits fourth |
| Rerank **before** the cap | promotion can change which *document* survives | -- |
| Per-citekey cap | source breadth, which a survey needs | per-passage relevance, which QA would want |
| One blocking gate, everything else advisory | `gate` never cries wolf | a wrong claim with a real citekey passes |
| Dossier instead of regeneration | scoped, cheap revision nobody else has | only as good as what was recorded |
| Author-keyword ground truth | no circularity, no LLM | only covers entries whose authors wrote keywords |

**The pattern.** Most of these are the same trade taken repeatedly:
**prefer a structural guarantee over a statistical one, and pay for it in
reach.** A citekey cannot be fabricated because the ledger is the only
source; a paper cannot monopolise a BM25 result because documents are the
unit; the gate means one thing because it only ever checks one thing.
Each buys a property you can state in a sentence and test, at the cost of
capability the other six have.

Where this pipeline is genuinely behind, the same honesty applies: no
hybrid fusion, query manufacture in one skill of five, no draft
fingerprint, and evidence that still reaches the drafter as raw windows
more often than as written claims.

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

**Two further sources are read for one stage each and are deliberately
not counted among the six**, because neither is a comparable end-to-end
system and folding them into the tallies below would make those tallies
mean less:

- **[LlamaIndex](https://github.com/run-llama/llama_index)** (MIT core,
  read at v0.14.24) is a *library*, and it is read only for
  [the synthesis shapes](#-the-synthesis-shape-how-n-passages-become-one-section)
  it ships -- the question of how N passages become one section, which
  none of the six answers explicitly.
- **ITER-RETGEN** (Shao, Gong, Shen, Huang, Duan, Chen, *"Enhancing
  Retrieval-Augmented Large Language Models with Iterative
  Retrieval-Generation Synergy"*, Findings of EMNLP 2023, pp. 9248-9274)
  is a *method paper*, read for
  [query manufacture](#-stage-4-query-manufacture-the-stage-most-systems-skip).
  It is the only source anywhere in this document whose iteration count
  is backed by a published measurement.

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
- [The synthesis shape](#-the-synthesis-shape-how-n-passages-become-one-section)
- [Stage 10: citation and verification](#-stage-10-citation-and-verification)
- [Stage 11: revision](#-stage-11-revision)
- [Evaluation, which is a stage too](#-evaluation-which-is-a-stage-too)
- [What a reproduction toolkit found](#-what-a-reproduction-toolkit-found-and-what-it-says-about-determinism)
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

**The one published method whose query costs no LLM call.**
ITER-RETGEN (Shao et al., *Findings of EMNLP 2023*) forms the next
query by **concatenating the previous generation with the original
question** -- `y_{t-1} || q` -- and retrieving on that. No model writes
the query; it is string concatenation over text that already exists, so
the retrieval path stays reproducible. Against a stdlib BM25 index that
makes the whole loop deterministic, which is the property every other
approach in this table gives up.

Its evidence is about retrieval rather than generation, and it is the
only *measured* termination condition in this document. Answer recall by
iteration, from the paper's own Table 6:

| Dataset | iter 1 | iter 2 | iters 3-7 |
| --- | --- | --- | --- |
| HotPotQA | 49.5 | **66.1** | 65.7 -> 67.1 |
| 2WikiMultiHopQA | 29.0 | **45.2** | ~46 |
| MuSiQue | 18.6 | **32.3** | ~33 |
| Bamboogle | 20.8 | **36.0** | ~36 |

**A shipped implementation exists and diverges from the paper.**
[FlashRAG](https://github.com/RUC-NLPIR/FlashRAG) (MIT) implements it in
about 45 lines as `IterativePipeline`, and four differences are worth
knowing before citing it as a reference: it runs **3 iterations, not 2**,
with the choice undocumented; it concatenates `{question} {generation}`
rather than the paper's `y_{t-1} || q` (**inert under BM25**, which is a
bag of words, but not under a dense retriever, where order changes the
embedding); it **discards the previous round's documents entirely**
rather than accumulating them; and it **overwrites the retrieval record
with the last round's**, so any recall computed from it describes round 3
alone rather than what the method actually consumed.

**Iteration 2 buys 13.7 to 16.6 points; iterations 3 through 7 buy about
one.** Two caveats the paper states itself and this document repeats
rather than buries: its error analysis finds 65% of failures are
retrieval-related and **76.9% of those are retrieval misled by wrong
reasoning from the first iteration** -- a bad draft becomes a bad query
and entrenches itself; and *"our experiments did not cover long-form
generation"*, which is the only thing this pipeline does. Its headline
metric is also an LLM judge.

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

**Across rounds, the same question returns and two implementations
answer it oppositely.** In FlashRAG, `IterativePipeline` keeps nothing
between rounds while `IRCoT` dedupes by document id, merges scores with
`max(old, new)` and re-sorts the accumulated pool -- **but never
truncates it**, so after N rounds the prompt carries up to N x k
documents. That is a live crash in their tracker, not a hypothetical.
The mechanism is right and the missing cap is the whole lesson: dedupe,
merge, re-sort, **then cap** -- which under a stdlib BM25 is a dict and
a `sorted()`.

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

### 🌲 The synthesis shape: how N passages become one section

Stage 9's table is about *what* the generator is handed. The other half
is **how many passages become one output**, and it is the stage a
long-form pipeline lives or dies at. LlamaIndex (MIT) is the useful
reference here because it ships five named shapes and they behave very
differently. Read as algorithms, for N retrieved passages:

| Shape | LLM calls | Can a source vanish silently? |
| --- | --- | --- |
| `simple_summarize` | 1 | **Yes, by construction** -- joins all passages, then keeps only what fits and discards the tail with no warning |
| `refine` | >= N | **Yes, twice over** -- a running answer is the only state carried forward, so anything a step declines to fold in is gone; and a failed call is caught, logged at warning level, and skipped |
| `compact` (the default) | k <= N | Yes, as `refine`, **plus source boundaries** -- passages are concatenated and re-split on token boundaries, so one prompt piece spans several papers with nothing marking where one ends |
| `tree_summarize` | k + 1 | **Yes, by attrition** -- leaves are query-conditioned summaries, and the root never sees source text, so a detail dropped at leaf time cannot be recovered |
| **`accumulate`** | N | **No** -- one independent call per passage into a fixed-length slot array; a failure materialises as a visible empty slot rather than an absence |

**`accumulate` is the only shape with a preservation guarantee**, and the
guarantee is positional: output slot *k* corresponds to input passage
*k*, so a missing answer is a *located* failure rather than a diff
against text nobody can align. Its sibling `compact_accumulate` packs the
inputs first and thereby destroys exactly that property -- the slots
survive but no longer name a source.

**What that implies for a citation-dense draft.** The shape worth
building is `accumulate`'s for the first stage -- one bounded call per
passage, emitting a claim that already carries its citekey -- and
`tree_summarize`'s *shape* for the fan-in, with one constraint its
default lacks: **after every level, check that the union of citekeys in
the children equals the union in the parent.** That check is arithmetic
over sets, not a judgement, and it converts tree summarisation's
characteristic failure from silent attrition into a caught error.
`refine` and `compact` are the wrong shape for anything citation-bearing
for the opposite reason: a running answer means every earlier citation
must survive re-derivation N-1 times.

**Where this pipeline currently sits.** `deep-research` fans *out* -- one
writer per outline section, each dispatched with
`dossier brief --section` rather than pasted evidence -- which is the
right shape at section granularity and has no fan-in problem, because
sections are assembled rather than summarised. The other four genres
write in a single context, which is `simple_summarize`'s shape with a
human-sized context window instead of a token budget: nothing truncates,
but nothing checks either. No genre currently verifies that the citekeys
it was handed are the citekeys it used --
[FEATURE-ROADMAP.md](FEATURE-ROADMAP.md)'s A3 and B2 are the nearest
existing items, and the union invariant above is the cheap deterministic
part neither of them names.

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

**ITER-RETGEN is the exception that clarifies the rule.** It *does*
feed a prior generation back in -- but as a **retrieval query**, not as
an artifact to edit, and it regenerates the answer from scratch each
iteration. So it is iterative *retrieval*, not revision, and it belongs
to stage 4 rather than here. What makes it interesting for this pipeline
is that `y_{t-1}` need not come from a model: **if a person writes the
draft, the person's draft is the query.** That turns "supply a starting
draft, revise it by hand later" into the same loop with a human in the
generation slot -- and it sidesteps the paper's own dominant failure
mode, since the wrong-first-reasoning problem is a property of a *model's*
first pass.

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

### 🔬 What a reproduction toolkit found, and what it says about determinism

[FlashRAG](https://github.com/RUC-NLPIR/FlashRAG) (MIT) exists to
re-implement published RAG methods under one uniform setting, which makes
its results the closest thing to an independent check on this whole
field. Three things it reports are worth more than any method it ships.

**Retrieval sometimes makes things worse, and the toolkit's own table
says so.** On 2WikiMultiHopQA, standard RAG scores *below* generation
with no retrieval at all, and **8 of 16 methods land under the
no-retrieval baseline** on that column. One widely-cited method
contributes nothing on three of six datasets. Whatever else a RAG
pipeline is, "retrieval helps" is a claim to measure rather than assume.

**It never compares against the published numbers.** The README is candid
that its uniform setting "may differ from the original setting of the
method" -- but there is no side-by-side against the source papers
anywhere in the repository, so *reproduction quality is unmeasured rather
than good*. Users attempting it report gaps of several points and, in one
thread, that most results could not be matched.

**Seeds are not sufficient for determinism, and this is the part that
generalises.** The toolkit seeds `random`, `numpy` and `torch`, and users
still observed **three runs at a fixed seed scoring 18.7, 17.1 and 17.4**.
Three causes, none of which a seed touches:

- **Sampling was on by default.** The shipped config left `do_sample`
  commented out, so the default generator fell through to the model's own
  `temperature: 0.6`. The documented experimental condition was not the
  default anyone got, and the published tables predate the fix.
- **Batch composition.** Everything is batched across the dataset, and
  continuous batching makes kernel reductions depend on what else is in
  the batch. A per-request seed cannot fix that.
- **Inference framework.** The same task scored 19.0 under one backend
  and 21.8 under another.

The clean part, and the one this pipeline shares: **retrieval itself is
deterministic** given an exact index -- they use a Faiss `Flat` index for
precisely that reason, rather than an approximate one.

**The lesson for a pipeline that promises reproducible inputs** is that
the guarantee has to be structural rather than seeded. This project's
retrieval path is deterministic because BM25 over a fingerprinted index
is arithmetic, not because anything is seeded -- and
[stage 4](#-stage-4-query-manufacture-the-stage-most-systems-skip)'s
preference for a query that costs no model call is the same argument one
step earlier. What a seed cannot make reproducible is best not put in the
path at all.

**One naming trap worth carrying away:** its `acc` metric is *substring
containment* -- whether the prediction contains the gold answer -- and it
sits in the default metric list. A verbose model scores well on it for
the wrong reason. Read what a metric computes, not what it is called.

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
